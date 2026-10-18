---
layout: post
title: "ViewModel·SavedState·process death"
date: 2026-11-16 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ViewModel, SavedState, ProcessDeath, Jetpack]
excerpt: "ViewModel은 회전에는 살아남지만 시스템이 프로세스를 죽이면 같이 사라진다. 프로세스 사망을 견디는 건 SavedStateHandle·onSaveInstanceState 뿐이고, 그 저장 상태는 Binder를 넘어 system_server가 보관한다 — 여기 비밀정보를 넣으면 앱 샌드박스 밖으로, 심지어 디스크로 새어 나간다."
---

앱의 상태가 언제 살아남고 언제 사라지는가는 UX 문제로 보이지만, 사실은 신뢰 경계 문제다. "회전해도 값이 유지되니까 ViewModel이 상태를 지켜 준다"는 흔한 오해는 사용자가 앱을 몇 분 백그라운드에 두는 순간 깨진다. 시스템이 메모리를 회수하려고 앱 프로세스를 죽이면 ViewModel은 통째로 사라지고, 그때 값을 복원하는 건 전혀 다른 경로 — `onSaveInstanceState` 번들과 그 위에 얹힌 `SavedStateHandle` 뿐이다. 그리고 이 번들은 앱 프로세스를 떠나 Binder를 타고 system_server로 건너가 거기서 보관된다.

이 글은 세 가지 상태 소멸 시나리오(구성 변경 / 시스템 주도 프로세스 종료 / 사용자 주도 종료)에서 무엇이 살아남는지를 AOSP androidx 소스와 함께 정리하고, 저장 상태가 Binder 경계를 넘어 더 높은 권한 프로세스로 흘러가는 흐름을 분석한 기록이다. 실습 재현은 자작 앱과 에뮬레이터로만 한다.

> **한 줄 결론**: ViewModel은 "구성 변경"만 견디고 "프로세스 종료"에는 소멸한다. 프로세스 사망을 견디는 건 `SavedStateHandle`/`onSaveInstanceState` 번들뿐이며, 그 번들은 system_server가 보관하고 경우에 따라 디스크에 영속되므로 비밀정보를 담아선 안 된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 세 가지다. (1) `ViewModel`이 왜 회전엔 살고 프로세스 종료엔 죽는지의 메커니즘(`ViewModelStore` + `NonConfigurationInstances`), (2) `onSaveInstanceState` 번들과 `SavedStateHandle`이 프로세스 사망을 견디는 경로(`SavedStateRegistry`), (3) 그 저장 상태가 Binder를 통해 system_server로 마샬링되어 보관·영속되는 신뢰 경계다.

선수로 깔리는 것 세 가지. Binder IPC가 프로세스 경계를 넘어 Parcel을 나르는 방식은 이 시리즈 14장(Binder proxy/stub) 주제이고, 액티비티 레코드를 들고 상태를 저장하는 주체가 system_server의 ActivityTaskManagerService라는 점은 10장(AMS·ATMS) 주제다. 프로세스가 메모리 압박으로 언제 죽는지의 배경은 Atlas C04(프로세스·가상메모리)에 있다. 앞 3장(Compose state·recomposition)에서 본 `rememberSaveable`도 결국 여기서 다루는 저장 상태 레지스트리 위에 선다.

전체 구조에서 이 장은 **App → Framework** 사이, 즉 액티비티 생명주기가 시스템 서비스와 만나는 지점이다. 상태 저장 요청은 앱에서 시작하지만 실제 보관은 프레임워크와 system_server에서 일어난다.

## 핵심 개념 — 상태 생존의 세 시나리오

핵심은 "언제 상태가 사라지는가"가 하나가 아니라 세 가지 서로 다른 사건이라는 점이다. 이걸 뭉뚱그리면 오해가 시작된다.

| 상태 종류 | 구성 변경(회전) | 시스템 주도 프로세스 종료 | 사용자 주도 종료(스와이프·뒤로) |
|--|--|--|--|
| `ViewModel` 필드 | **생존** | 소멸 | 소멸 |
| `SavedStateHandle` | 생존 | **생존** | 소멸 |
| `onSaveInstanceState` 번들 | 생존 | **생존** | 소멸 |

`Source-confirmed` (Android "Save UI states" 가이드)

읽는 법은 이렇다. **구성 변경**은 액티비티만 파괴·재생성하고 프로세스는 살아 있다 — 그래서 셋 다 생존한다. **시스템 주도 프로세스 종료**는 사용자가 백그라운드로 보낸 뒤 시스템이 메모리를 회수하며 프로세스를 죽인 경우 — 프로세스 안에 있던 `ViewModel`은 사라지지만, 미리 번들로 떠 둔 저장 상태는 사용자가 돌아올 때 복원된다. **사용자 주도 종료**는 뒤로 가기·recents 스와이프처럼 사용자가 명시적으로 끝낸 경우 — 저장 상태도 폐기된다.

여기서 가장 자주 틀리는 지점: 두 번째 열이다. "ViewModel에 넣었으니 안전하다"는 두 번째 시나리오에서 무너진다. `SavedStateHandle`은 이름은 ViewModel에 붙어 다니지만 저장 경로가 완전히 다르다 — ViewModel 필드가 아니라 저장 상태 레지스트리에 얹혀 번들로 직렬화된다.

> **[그림 1]** 자작 상태 랩 앱에서 ViewModel 필드 카운터와 SavedStateHandle 카운터를 나란히 표시한 화면 — 회전 직후 둘 다 값을 유지하는 상태 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

저장 상태의 위협 모델은 외부 공격자가 아니라 **데이터가 어디로 흘러가는가**다. `onSaveInstanceState(Bundle)`이 채운 번들은 앱 프로세스에 머물지 않는다. 액티비티가 멈출 때 이 번들은 Parcel로 마샬링되어 Binder를 타고 system_server(ActivityTaskManagerService)로 건너가고, 거기서 액티비티 레코드에 `icicle` 필드로 보관된다. `Source-confirmed` (AOSP `com.android.server.wm.ActivityRecord`의 `icicle` 필드) 즉 저장 상태는 내 앱 UID의 샌드박스를 떠나 더 높은 권한의 system_server가 들고 있게 된다.

한 걸음 더. 액티비티에 `android:persistableMode="persistAcrossReboots"`를 주면 `onSaveInstanceState(Bundle, PersistableBundle)` 오버로드가 불리고, 이 `PersistableBundle`은 system_server가 디스크에 영속시켜 **재부팅까지** 살아남는다. `Source-confirmed` (Activity `onSaveInstanceState` 레퍼런스) 여기서 결론이 나온다 — 인증 토큰·PII 같은 비밀정보를 저장 상태에 넣으면, 그 값은 (1) 내 프로세스를 떠나 (2) system_server가 보관하고 (3) 설정에 따라 디스크에 남는다. 세 곳 다 앱이 통제하지 못하는 영역이다.

두 번째 위협은 견고성이다. Binder 트랜잭션 버퍼는 프로세스당 약 1MB를 공유한다. `Source-confirmed` (Binder/TransactionTooLargeException 문서) 저장 번들이 커지면 이 경계에서 `TransactionTooLargeException`이 터져 앱이 백그라운드로 가는 순간 크래시한다. 리스트처럼 크기가 자라는 데이터를 저장 상태에 통째로 담으면, 특정 상태에서만 재현되는 크래시를 만들어 낸다 — 이건 DoS로 부풀릴 건 아니고, 로컬 견고성 결함이다.

## 관측 — 프로세스 사망을 재현한다

### 가설
- **가설 A** — 백그라운드 앱을 `am kill`로 죽였다 되살리면, `SavedStateHandle` 값은 복원되고 `ViewModel` 필드는 초기값으로 돌아간다. `Inferred`
- **가설 B** — 같은 상태에서 recents 스와이프로 끝내면 둘 다 초기화된다(저장 상태 폐기). `Inferred`

### 절차
자작 앱 `com.wtcy.statelab`은 두 카운터를 둔다 — 하나는 순수 `ViewModel` 필드, 하나는 `SavedStateHandle["count"]`. 값을 올린 뒤 아래를 실행한다.

```bash
# 1) 홈으로 보내 앱을 백그라운드(캐시) 상태로
adb shell input keyevent KEYCODE_HOME

# 2) 시스템 주도 프로세스 종료 시뮬레이션.
#    am kill 은 "죽여도 안전한"(백그라운드) 프로세스만 종료한다.
adb shell am kill com.wtcy.statelab

# 3) 프로세스가 실제로 사라졌는지 확인
adb shell "ps -A | grep statelab"    # 아무것도 안 나오면 종료됨

# 4) recents에서 복귀(사용자가 돌아온 것처럼)
adb shell am start -n com.wtcy.statelab/.MainActivity

# 5) 앱이 복원 시점에 찍는 로그를 관찰
adb logcat -s StateLab
```

`am kill`이 백그라운드 프로세스만 죽인다는 점이 핵심이다 — 이게 "시스템이 메모리 회수로 죽인" 상황과 같은 경로다. `Source-confirmed` (`am` 도움말) 반대로 recents 스와이프는 사용자 주도 종료라 저장 상태까지 폐기된다.

> **[그림 2]** `adb shell am kill` 후 재실행했을 때 logcat에 `SavedStateHandle` 값은 복원(count=3)되고 `ViewModel` 필드는 0으로 초기화된 것을 대조한 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(실제 실행으로 교체):

```
# am kill 후 재실행 — StateLab 태그
StateLab: onCreate savedInstanceState=NON-NULL
StateLab: restored SavedStateHandle count = 3
StateLab: viewModel field count = 0     <-- 프로세스와 함께 소멸

# 같은 앱을 recents 스와이프로 끝낸 뒤 재실행
StateLab: onCreate savedInstanceState=null
StateLab: restored SavedStateHandle count = 0
StateLab: viewModel field count = 0
```

`savedInstanceState`가 `NON-NULL`이면 시스템 주도 종료(복원됨), `null`이면 사용자 주도 종료(폐기)다. 이 한 줄이 두 시나리오를 가르는 신호다.

## Root Cause — 왜 이렇게 되는가

`ViewModel`이 회전엔 살고 프로세스 종료엔 죽는 이유는 **어디에 저장되느냐**에 있다. androidx `ComponentActivity`는 구성 변경 직전에 `onRetainNonConfigurationInstance()`를 호출해 `ViewModelStore`를 `NonConfigurationInstances` 객체에 담아 반환하고, 재생성된 액티비티는 `getLastNonConfigurationInstance()`로 그 **같은 자바 객체 참조**를 도로 받아 온다. `Source-confirmed` (androidx `ComponentActivity`)

```java
// androidx ComponentActivity (요지)
public final Object onRetainNonConfigurationInstance() {
    NonConfigurationInstances nci = new NonConfigurationInstances();
    nci.viewModelStore = mViewModelStore;   // 스토어를 그대로 넘김
    return nci;
}
void ensureViewModelStore() {
    NonConfigurationInstances nc =
        (NonConfigurationInstances) getLastNonConfigurationInstance();
    if (nc != null) mViewModelStore = nc.viewModelStore;   // 참조 회수
    if (mViewModelStore == null) mViewModelStore = new ViewModelStore();
}
```

이 참조 전달은 **같은 프로세스 안에서만** 성립한다. 구성 변경은 프로세스를 유지하니 참조가 살아 있다. 그러나 프로세스가 죽으면 힙 전체가 사라지고 `NonConfigurationInstances`도, 그 안의 `ViewModelStore`도 없다 — 되살아난 새 프로세스에는 회수할 참조가 없어 `ViewModel`은 새로 만들어진다. 즉 ViewModel의 생존 범위는 설계상 "프로세스 수명"이지 "논리적 화면 수명"이 아니다.

저장 상태가 프로세스 사망을 견디는 건 경로가 아예 다르기 때문이다. `SavedStateHandle`은 `SavedStateRegistry`에 등록되고, `ComponentActivity.onSaveInstanceState`가 `SavedStateRegistryController.performSave(outState)`로 그 내용을 **번들에 직렬화**한다. 번들은 앞서 본 대로 Binder를 넘어 system_server가 보관하므로, 프로세스가 죽어도 값이 남아 `performRestore(savedInstanceState)`로 되살아난다. `Source-confirmed` (androidx `SavedStateRegistryController`) 참조를 넘기는 ViewModel과 값을 직렬화하는 SavedState의 이 차이가 두 시나리오의 갈림을 만든다.

## 방어와 회귀 검증

- **비밀정보를 저장 상태에 넣지 않는다.** 토큰·비밀번호·PII는 `Bundle`/`SavedStateHandle`이 아니라 Keystore 기반 저장소(Atlas C40)에 둔다. 저장 상태는 system_server로 건너가고 `PersistableBundle`은 디스크에 남기 때문이다. 저장 상태에는 "화면을 다시 그리는 데 필요한 식별자·스크롤 위치" 수준만 담는다.
- **저장 번들을 작게 유지한다.** 큰 객체·리스트는 번들이 아니라 Room/DataStore(다음 5장)에 두고, 저장 상태엔 키나 페이지 인덱스만 넣어 `TransactionTooLargeException`을 원천 차단한다.
- **프로세스 사망을 회귀 항목으로 넣는다.** 개발자 옵션 "활동 유지 안 함"(Don't keep activities)이나 위 `am kill` 절차로, 릴리스마다 "백그라운드 → 종료 → 복귀"에서 화면이 올바로 복원되는지 확인한다. 회전만 테스트하고 넘어가면 시스템 주도 종료 경로가 그대로 비어 있게 된다.
- **버전 차이 하나** — API 28(Android 9)부터 `onSaveInstanceState()`는 `onStop()` **이후**에 호출된다. `Source-confirmed` (Activity 생명주기 문서) 그 이전 버전은 `onStop()` 이전에 불렸으므로, onStop에서 만든 상태를 저장하려던 코드는 targetSdk에 따라 타이밍이 달라진다 — 문서화할 땐 대상 API를 표기한다.

## 정리

- `ViewModel`의 생존 범위는 프로세스 수명이다. 회전(구성 변경)은 견디지만 시스템 주도 프로세스 종료엔 소멸한다.
- 프로세스 사망을 견디는 건 `onSaveInstanceState` 번들과 그 위의 `SavedStateHandle`뿐이며, 사용자 주도 종료(스와이프·뒤로)에선 이마저 폐기된다.
- 저장 상태는 Binder를 넘어 system_server가 보관하고 `PersistableBundle`은 디스크에 영속된다 — 비밀정보 금지, 번들은 작게.
- 두 경로의 차이는 근본적이다. ViewModel은 **객체 참조 전달**(같은 프로세스), 저장 상태는 **값 직렬화**(프로세스 넘어 보관).

**점검 질문** — (1) 회전에는 값이 유지되는데 백그라운드에서 돌아오면 초기화된다면, 그 값은 어디에 저장돼 있었나? (2) `SavedStateHandle`과 순수 `ViewModel` 필드의 저장 경로는 각각 무엇이고, 왜 하나만 프로세스 사망을 견디는가? (3) 인증 토큰을 `savedInstanceState`에 담으면 그 값은 최종적으로 어느 프로세스·어느 저장소까지 도달할 수 있는가?

**참고** — [ViewModel 개요](https://developer.android.com/topic/libraries/architecture/viewmodel) · [UI 상태 저장](https://developer.android.com/topic/libraries/architecture/saving-states) · [SavedStateHandle](https://developer.android.com/reference/androidx/lifecycle/SavedStateHandle) · [Activity onSaveInstanceState](https://developer.android.com/reference/android/app/Activity#onSaveInstanceState(android.os.Bundle)) · [androidx ComponentActivity 소스](https://cs.android.com/androidx/platform/frameworks/support/+/androidx-main:activity/activity/src/main/java/androidx/activity/ComponentActivity.java) · Atlas C04(프로세스·가상메모리) · C40(Keystore)

*다음 글: [Room·DataStore·WorkManager](/posts/android-expert-p2c05/).*
