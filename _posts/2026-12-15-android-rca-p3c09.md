---
layout: post
title: "Binder caller identity 오류 RCA"
date: 2026-12-15 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Binder, IPC, 권한우회, RCA]
excerpt: "clearCallingIdentity() 뒤에서 getCallingUid()로 권한을 확인하면 그 UID는 호출자가 아니라 시스템 자신이라 검사가 항상 통과한다. 크래시가 없어 조용히 우회되는 confused deputy — RCA는 툼스톤이 아니라 호출 순서를 읽는 데서 끝난다."
---

Android 시스템 서비스의 권한 검사는 대부분 "네가 누구냐"를 UID로 묻는다. 그런데 그 "누구냐"를 돌려주는 `Binder.getCallingUid()`는 문맥에 따라 답이 바뀐다. 신원을 한 번 지우고 나면 같은 함수가 호출자가 아니라 서비스 자신의 UID를 돌려준다. 이 미묘한 전환을 모르고 검사를 잘못된 위치에 두면, 아무 권한 없는 앱이 특권 동작에 성공하는데도 로그엔 예외 하나 남지 않는다. 크래시가 없으니 "취약점이 없다"고 착각하기 딱 좋다.

이 글은 Binder 호출자 신원(caller identity) 혼동으로 생기는 권한 우회를 RCA 관점에서 정리한 기록이다. 자작 결함 앱과 에뮬레이터로 증상→트리거→폴트 사이트→근본원인을 분리하고, 이 결함이 왜 EoP(권한 상승)이지 RCE가 아닌지, 영향을 어디까지 정직하게 산정해야 하는지를 다룬다.

> **한 줄 결론**: `clearCallingIdentity()` 이후의 `getCallingUid()`는 호출자가 아니라 프로세스 자신의 UID를 돌려준다. 권한 검사를 신원 삭제 뒤에 두면 검사 대상 주체가 바뀌어 항상 통과하는 confused deputy가 되고, 이 버그는 크래시가 없어 코드 순서를 읽어야만 잡힌다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 좁고 분명하다. `getCallingUid()`/`getCallingPid()`와 `clearCallingIdentity()`/`restoreCallingIdentity()`의 상호작용, 이 조합이 만드는 권한 우회의 폴트 사이트를 어떻게 특정하는지, 그리고 그 우회의 영향을 DoS/정보노출/EoP 경계에서 어떻게 매기는지다. 메모리 손상은 없다 — 이건 순수 로직 버그다.

선수 개념 셋. 첫째, Binder IPC의 기본(트랜잭션·프록시/스텁·`onTransact`)을 알아야 "누가 호출했는가"가 어디서 결정되는지 보인다(Atlas의 Binder/IPC 편). 둘째, Android 권한 모델이 시스템 서비스에서 UID/PID 기반 검사로 구현된다는 사실. 셋째, 이 파트 1장에서 세운 RCA 어휘 — 증상(Symptom)/트리거(Trigger)/폴트 사이트(Fault site)/근본원인(Root cause)의 구분. 이번 글은 그 어휘를 신원 혼동 버그 하나에 그대로 적용한다.

전체 구조에서 이 장은 "메모리 안 터지는 로직 버그도 RCA 대상"이라는 축의 대표 사례다. 바로 앞 장이 Java 예외·로직 버그의 RCA였다면, 여기서는 IPC 경계를 넘는 신원 문제로 한 단계 좁힌다. 다음 장은 Parcel의 read/write 불일치로 넘어간다.

## 핵심 개념 — getCallingUid()는 문맥 의존 함수다

세 API의 계약을 먼저 못 박는다. 이게 흔들리면 RCA 전체가 흔들린다.

| API | 반환/효과 | 함정 |
|--|--|--|
| `getCallingUid()` | **현재 트랜잭션을 보낸** 프로세스의 UID. 트랜잭션 실행 중이 아니면 **자기 자신의 UID** | 문맥 의존 — 같은 줄이 상황에 따라 다른 답 |
| `getCallingPid()` | 위와 같되 PID | 트랜잭션 밖에선 자기 PID |
| `clearCallingIdentity()` | 들어온 IPC 신원을 리셋. 이후 하위 호출은 **자기 프로세스** 신원으로 검사됨. 복원용 토큰 반환 | 리셋한 뒤 `getCallingUid()`는 자기 UID |
| `restoreCallingIdentity(token)` | 토큰으로 원래 신원 복원 | 안 부르면 신원이 샌다 |

핵심은 첫 줄과 셋째 줄이 만나는 지점이다. `clearCallingIdentity()`의 원래 용도는 정당하다 — 들어온 호출을 처리하다가 같은 프로세스 안의 다른 객체를 부를 때, 그 객체가 "원래 원격 호출자"가 아니라 "나(시스템 프로세스)"의 권한으로 검사하도록 신원을 잠시 내 것으로 바꾸는 것이다. `Source-confirmed`

문제는 이렇게 신원을 내 것으로 바꾼 상태에서 `getCallingUid()`를 다시 부르면, 그 값이 이제 원격 호출자가 아니라 내 UID(시스템 서비스면 SYSTEM/1000, 앱이면 자기 앱 UID)라는 점이다. `Source-confirmed`

즉 `getCallingUid()`는 상수 함수가 아니라 문맥 의존 함수다. "권한 검사를 어디에 두느냐"가 곧 "누구를 검사하느냐"를 정한다. 이 한 문장이 이 버그 클래스의 전부다.

> **[그림 1]** 자작 서비스에서 `clearCallingIdentity()` 앞뒤로 `getCallingUid()` 값을 찍은 logcat — 같은 함수 호출이 호출자 UID → 서비스 자신 UID로 바뀌는 장면 — *실측 스크린샷 자리*

**신뢰 경계와 위협 모델.** 신뢰 경계는 Binder 트랜잭션 그 자체다 — 경계 바깥의 저권한 앱이 경계 안(시스템 서비스/특권 앱)의 메서드를 부른다. 방어자가 지켜야 할 불변식은 하나다: **"이 특권 동작은 UID X만 호출할 수 있다"**. 위협 모델의 공격자는 임의 앱을 설치할 수 있는 로컬 저권한 주체다. 원격도, 물리 접근도 필요 없다. 공격자의 목표는 메모리를 터뜨리는 게 아니라, 검사가 자기 UID가 아닌 시스템 UID를 보게 만들어 불변식을 무력화하는 것이다.

## 실습 환경과 안전 범위

전부 **AVD(에뮬레이터)와 자작 앱 두 개**로만 진행한다. 제3자·실서비스 앱은 건드리지 않는다. 시스템 서비스의 SYSTEM UID 혼동을 그대로 재현하려면 플랫폼 빌드가 필요하지만, **원리(신원 삭제 후 UID가 바뀐다)는 앱 프로세스에서 100% 동일하게 관측된다**. 그래서 랩은 앱 대 앱으로 축소한다.

- **victim 앱**: exported 바운드 서비스 하나. 특권 메서드 안에서 `clearCallingIdentity()` 앞뒤로 `getCallingUid()`를 로깅한다(결함 위치를 눈으로 보기 위함).
- **attacker 앱**: victim 서비스에 바인딩해 그 메서드를 호출한다. 무기화 없음 — 원격 호출자 UID가 검사에서 어떻게 사라지는지 관측까지만.

PoC는 프리미티브 존재 확인 수준이다. 실데이터 탈취·지속성·전파는 없다.

## 실습 절차와 관측

### 가설
- **가설 A** — `clearCallingIdentity()` 호출 전 `getCallingUid()`는 attacker 앱의 UID를, 호출 후 `getCallingUid()`는 victim 서비스 자신의 UID를 돌려준다. `Inferred`
- **가설 B** — 따라서 "`getCallingUid() == 허용된_UID`" 형태의 검사를 신원 삭제 뒤에 두면, 검사가 원격 호출자를 보지 못하므로 불변식이 무력화된다. `Inferred`

### 절차
1. victim 서비스의 결함 메서드를 아래처럼 두 지점에서 로깅한다.
2. 두 앱을 AVD에 설치하고 attacker를 실행해 바인딩·호출을 트리거한다.
3. `adb logcat`으로 앞뒤 UID를 대조 기록한다.
4. `adb shell dumpsys package <attacker>`·`<victim>`으로 각 앱의 UID를 확인해 로그 값과 맞춰본다.

```java
// victim 앱 B — exported 바운드 서비스의 결함 메서드
@Override
public boolean privilegedAction() {
    Log.i(TAG, "before clear: uid=" + Binder.getCallingUid());  // 호출자 UID
    long token = Binder.clearCallingIdentity();
    Log.i(TAG, "after  clear: uid=" + Binder.getCallingUid());  // 서비스 자신 UID
    // 폴트 사이트: 신원을 지운 뒤에 검사 → 원격 호출자가 아니라 자기 자신을 검사
    boolean allowed = (Binder.getCallingUid() == TRUSTED_UID);
    Binder.restoreCallingIdentity(token);
    if (allowed) doReallyPrivilegedThing();
    return allowed;
}
```

```bash
# 두 앱 설치 후 attacker 실행, 앞뒤 UID 대조
adb install -r app-victim.apk
adb install -r app-attacker.apk
adb shell am start -n com.example.attacker/.MainActivity
adb logcat -s VictimService:I
# 각 앱의 실제 UID 확인(로그 값과 대조용)
adb shell dumpsys package com.example.attacker | grep userId
adb shell dumpsys package com.example.victim  | grep userId
```

> **[그림 2]** attacker 실행 후 `adb logcat`에 찍힌 before/after UID 대조 캡처 — before가 attacker UID, after가 victim UID로 바뀌어 `TRUSTED_UID` 검사가 엉뚱한 주체를 보는 장면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
I VictimService: before clear: uid=10199   # attacker 앱 UID
I VictimService: after  clear: uid=10200   # victim 서비스 자신 UID
```

`dumpsys`로 확인한 UID와 로그가 일치하면 가설 A가 선다: `clearCallingIdentity()` 한 줄이 `getCallingUid()`의 답을 호출자→자기 자신으로 바꿨다. 검사 대상 `TRUSTED_UID`가 victim 자신의 UID와 같았다면(시스템 서비스 시나리오의 SYSTEM=1000에 대응) 검사는 무조건 통과한다. 예외도, 크래시도, 툼스톤도 없다 — 이 버그가 조용한 이유다.

## Root Cause — 왜 이렇게 되는가

이 파트 1장의 어휘로 분해하면 결함의 위치가 정확히 한 줄로 좁혀진다.

- **증상(Symptom)** — 권한 없는 앱이 특권 메서드를 호출해 성공한다. 로그엔 `SecurityException`도 크래시도 없다.
- **트리거(Trigger)** — 임의 저권한 앱이 exported Binder 메서드를 정상 인자로 호출하는 것. 특수 입력·경합 불필요.
- **폴트 사이트(Fault site)** — `clearCallingIdentity()` **뒤에 놓인** `getCallingUid()` 기반 검사 그 한 줄. 다른 데가 아니다.
- **근본원인(Root cause)** — 신원을 시스템 것으로 바꾼 뒤에 "누가 불렀나"를 다시 물어서, 검사 대상 주체가 원격 호출자에서 프로세스 자신으로 바뀌었다. 전형적 **confused deputy(혼동된 대리자)** — 특권 프로세스가 자기 권한으로 남의 요청을 대신 수행한다.

여기서 반드시 구분할 것. 증상은 "우회"지만 근본원인은 "메모리 손상"이 아니라 **"검사의 순서/대상 오류"**다. 폴트 사이트를 `clearCallingIdentity()`(원래 정당한 API)로 오인하면 안 된다. 그 API는 죄가 없다. 죄는 그 뒤에 검사를 둔 순서에 있다. 같은 API를 순서만 바꿔 쓰면 안전하다.

## 크래시가 없는 버그의 exploitability와 영향 산정

메모리 버그의 RCA는 툼스톤·ASan/KASAN 로그가 반쯤 대신 써준다. 신원 혼동은 그런 신호가 **전혀 없다**. 증거는 (1) 코드 순서 읽기, (2) logcat의 UID 대조, (3) 저권한 UID로 호출했을 때 특권 동작이 성공한다는 차등 실험뿐이다. "크래시 없음 = 취약점 없음"이라는 오개념을 이 클래스가 정면으로 깬다.

영향은 **정직하게, 그리고 좁게** 매겨야 한다.

- 이 결함은 **EoP(권한 상승)** 클래스다. RCE가 아니다 — 임의 코드 실행을 주지 않는다. 우회된 검사가 가리던 딱 그 능력만큼만 얻는다.
- 그러므로 영향의 상한은 **우회된 검사가 보호하던 동작**이다. 그게 로그 한 줄을 남기는 동작이면 사실상 무해에 가깝고, 시스템 설정 변경이나 타 앱 데이터 접근이면 실질 EoP다. **"UID 검사를 우회했다"만으로 최악을 가정하지 말 것.** 무엇이 게이트되어 있었는지를 먼저 확인하고 그것만 영향으로 적는다.
- DoS/정보노출/EoP 경계: 이건 가용성 훼손(DoS)도, 단순 읽기(정보노출)도 아닌 **인가 우회(EoP)**다. 세 축을 뭉뚱그리지 않는다.

CVSS를 붙일 때도 벡터가 실제로 게이트된 능력을 반영해야 하고, 반사적으로 C:H/I:H/A:H를 찍지 않는다. 예를 들어 로컬 앱이 시스템 서비스의 검사를 우회해 기밀·무결성·가용성 모두에 큰 영향을 준다고 **입증됐을 때** 벡터는 `AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H` → 3.1 기준 **7.8(High)**다(ISS=0.9148, Impact=5.87, Exploitability=1.83, 합 7.71→올림 7.8). 게이트된 게 무결성뿐이라면 `C:N/I:H/A:N`으로 내려가고 점수도 그만큼 낮아진다. 벡터와 점수는 재계산 가능해야 하며, 영향 축은 관측으로 뒷받침한 것만 High로 올린다. `Inferred`

## 방어와 회귀 검증

수정은 근본원인 한 곳에서 끝난다 — 검사 대상 주체가 절대 바뀌지 않게 만든다.

1. **검사를 신원 삭제보다 먼저.** `getCallingUid()`를 지역 변수로 잡아 검사한 뒤에 `clearCallingIdentity()`를 부른다. 삭제 뒤에는 `getCallingUid()`를 신원 확인 목적으로 다시 부르지 않는다.

```java
@Override
public boolean privilegedAction() {
    final int callerUid = Binder.getCallingUid();   // (1) 지우기 전에 캡처
    if (callerUid != TRUSTED_UID) {                  // (2) 확인 먼저
        throw new SecurityException("uid " + callerUid + " denied");
    }
    final long token = Binder.clearCallingIdentity(); // (3) 그다음에만 삭제
    try {
        doReallyPrivilegedThing();
    } finally {
        Binder.restoreCallingIdentity(token);         // (4) 반드시 finally
    }
    return true;
}
```

2. **`restoreCallingIdentity()`는 항상 `finally`에.** 예외로 복원을 건너뛰면 신원이 새서 이후 호출까지 오염된다(별개의 변종). AOSP엔 이 짝을 강제하는 람다 헬퍼 `Binder.withCleanCallingIdentity(...)`가 있으니 있으면 그걸 쓴다. `Reported`(정확한 시그니처·가용 버전은 원문 재확인 필요)
3. **회귀 테스트는 차등으로.** 저권한 UID로 이 메서드를 호출했을 때 `SecurityException`이 나는지를 계측 테스트로 못 박는다. "허용 UID는 통과, 비허용 UID는 거부"라는 불변식 자체를 테스트가 지킨다. 크래시가 없는 버그라 이 차등 테스트가 유일한 자동 방어선이다.
4. **변종 분석(variant analysis).** 같은 코드베이스에서 `clearCallingIdentity()`와 `getCallingUid()`가 **같은 메서드 안에 함께** 나타나는 지점을 전부 훑는다(`grep`으로 파일 목록만 좁힌 뒤 순서를 눈으로 확인). 한 곳이 이랬으면 같은 저자·같은 패턴의 형제 메서드가 있기 쉽다. 별도 변종 하나 더: **트랜잭션 밖 in-process 경로**. `getCallingUid()`는 트랜잭션 실행 중이 아니면 자기 UID를 돌려주므로, 검사 메서드를 IPC가 아닌 직접 호출로 도달시킬 수 있으면 같은 우회가 성립한다. AOSP 내부의 `getCallingUidOrThrow()`류(트랜잭션 밖이면 예외)가 이 변종을 막지만, 가용 버전은 확인이 필요하다. `Reported`

## 정리

- `getCallingUid()`는 문맥 의존 함수다 — 트랜잭션 밖이나 `clearCallingIdentity()` 뒤에선 호출자가 아니라 자기 자신을 돌려준다.
- 권한 검사를 신원 삭제 뒤에 두면 confused deputy가 되고, 이 버그는 크래시가 없어 툼스톤이 아니라 코드 순서와 UID 대조로 잡는다.
- 영향은 우회된 검사가 보호하던 능력까지만 — EoP이지 RCE가 아니며, C/I/A는 관측으로 뒷받침한 것만 올린다.
- 수정은 "검사 먼저, 캡처한 UID로, 삭제는 그 뒤, 복원은 finally" 한 패턴으로 끝나고, 저권한 UID 거부를 차등 회귀 테스트로 못 박는다.

**점검 질문** — (1) `clearCallingIdentity()` 직후 `getCallingUid()`가 돌려주는 값은 무엇이고 왜인가? (2) 이 결함을 EoP로 부르고 RCE로 부르지 않는 근거는? (3) 크래시가 없는 이 버그의 RCA에서 폴트 사이트를 특정하는 증거 세 가지는?

**참고** — [android.os.Binder 레퍼런스](https://developer.android.com/reference/android/os/Binder) · [AOSP Binder.java](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/base/core/java/android/os/Binder.java) · [Android 권한 개요](https://developer.android.com/guide/topics/permissions/overview)

*다음 글: [Parcel read/write mismatch RCA](/posts/android-rca-p3c10/).*
