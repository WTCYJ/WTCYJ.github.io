---
layout: post
title: "Jetpack Compose state·recomposition"
date: 2026-11-15 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, JetpackCompose, Recomposition, SnapshotState, 상태관리]
excerpt: "리컴포지션은 상태를 '읽은' 스코프만 다시 실행한다 — 그런데 mutableStateOf를 remember 없이 쓰면 매 프레임 상태가 초기화되고, 강한 스킵이 없으면 List 파라미터 하나가 스킵을 통째로 깨뜨린다. 그리고 리컴포지션은 보안 경계가 아니다."
---

Compose가 기존 View 시스템과 근본적으로 다른 점은 UI를 명령형으로 갱신하지 않는다는 것이다. 상태(state)를 선언하면 UI는 그 상태의 함수로 그려지고, 상태가 바뀌면 그 상태를 **읽은 컴포저블만** 다시 실행된다 — 이것이 리컴포지션(recomposition)이다. 문제는 "언제·무엇이·왜 다시 실행되는가"가 코드 표면에 드러나지 않는다는 점이다. 이 모델을 잘못 이해하면 성능 문제(불필요한 리컴포지션)와 정확성 문제(매 프레임 초기화되는 상태, 남아 있는 이전 사용자 값)가 동시에 터진다.

이 글은 Compose의 상태 시스템(스냅샷 기반 `mutableStateOf`)과 리컴포지션 엔진(Composer·슬롯 테이블·스킵)이 어떻게 맞물리는지를 AOSP androidx 소스와 공식 문서로 정리한 기록이다. 공격 실습이 아니라 App 계층 최상단의 구조·소스 이해가 목적이다.

> **한 줄 결론**: 리컴포지션은 상태를 **읽은 스코프**만 다시 실행하는데, 그 스킵(skip)은 타입 **안정성(stability)** 에 종속된다 — **강한 스킵(strong skipping)이 없으면**(또는 매 리컴포지션마다 새 인스턴스를 넘기면) `List` 파라미터 하나가 스킵을 통째로 깨고, `remember` 빠진 `mutableStateOf` 하나가 상태를 매 프레임 초기화한다. 그리고 리컴포지션은 보안 경계가 아니다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 넷이다. (1) 상태 보관 — `mutableStateOf`/`remember`/`rememberSaveable`가 각각 무엇을, 어디에 저장하는가. (2) 스냅샷 시스템 — `androidx.compose.runtime.snapshots`가 상태 읽기/쓰기를 어떻게 추적하고 스레드 안전을 보장하는가. (3) 리컴포지션 엔진 — Composer·슬롯 테이블·`RecomposeScope`가 "읽은 것만 다시 실행"을 어떻게 구현하는가. (4) 스킵과 안정성 — `@Stable`/`@Immutable`과 컴파일러의 스킵 판정. 마지막으로 이 모든 것이 왜 **보안 경계가 아닌지**를 신뢰 경계로 정리한다.

선수 지식이 셋 필요하다. 이 파트 1장(Kotlin·coroutine·structured concurrency)에서 다룬 코루틴은 Compose의 이펙트(`LaunchedEffect`)와 프레임 클록이 그 위에서 돈다는 점에서, 2장(Flow·StateFlow·lifecycle)의 Flow는 `collectAsState`가 Flow를 스냅샷 State로 다리 놓는다는 점에서 전제가 된다. Part 1 개념편의 프로세스·가상메모리(Atlas C04)는 이 전부가 **단일 앱 프로세스 안에서만** 일어난다는 사실을 뒷받침한다.

전체 구조에서 Compose는 **App 계층의 최상단**에 있다. 컴포저블 트리는 결국 하나의 `AndroidComposeView`(일반 View)로 붙고, 그 아래로 `ViewRootImpl`이 자기 `Surface`에 버퍼를 제출하고 SurfaceFlinger가 이를 합성하는 익숙한 렌더 경로를 그대로 탄다(창 자체의 배치·z-order는 WindowManagerService가 관리하지만, 버퍼 합성 경로에는 직접 끼지 않는다 — 13장 WMS). 즉 리컴포지션은 이 경로에 **오르기 전** 앱 메모리 안에서 UI 트리를 갱신하는 단계일 뿐이다. `Inferred`

## 핵심 개념 — 상태를 읽으면 구독한다

Compose 상태의 출발점은 `mutableStateOf(x)`다. 이건 평범한 변수가 아니라 스냅샷 시스템에 등록된 **관측 가능한 상태 객체**(`SnapshotMutableState`, `StateObject`)를 만든다. 컴포지션 중 `state.value`를 읽으면 런타임이 "이 `RecomposeScope`가 이 상태를 읽었다"를 기록하고, 나중에 그 상태가 바뀌면 **그 스코프만** 다시 실행 예약된다. `Source-confirmed`

세 가지 보관 함수를 혼동하면 안 된다.

| 함수 | 저장 위치 | 생존 범위 | 흔한 오해 |
|--|--|--|--|
| `mutableStateOf(x)` | 스냅샷 상태 객체 생성만 | 즉시(재실행마다 새로) | **그 자체로는 기억하지 않는다** |
| `remember { mutableStateOf(x) }` | 컴포지션의 슬롯 테이블(호출 위치 키) | 컴포지션에 남아있는 동안 | 화면 회전/프로세스 죽음엔 소실 |
| `rememberSaveable { mutableStateOf(x) }` | 슬롯 테이블 + `Bundle`(saved instance state) | 구성 변경·프로세스 죽음 넘어 복원 | **Bundle은 system_server 메모리로 나간다**(디스크는 `persistableMode` 시) |

가장 자주 터지는 함정: `remember` 없이 `var s = mutableStateOf(0)`를 컴포저블 안에 쓰면, 리컴포지션마다 함수 본문이 다시 실행되면서 상태 객체가 **매번 새로 만들어져 0으로 초기화**된다. 상태를 슬롯 테이블에 고정하는 것이 `remember`의 유일한 일이다. `Source-confirmed`

리컴포지션이 상태 읽기만 추적하는 게 아니라 **어느 단계에서 읽었는지**도 중요하다. Compose 프레임은 컴포지션(무엇을 그릴지) → 레이아웃(어디에) → 드로잉(어떻게)의 3단계로 진행되고, 상태를 드로잉/레이아웃 단계로 미뤄 읽으면(예: `Modifier.drawBehind { ... }`, `graphicsLayer { ... }`의 람다 안에서) 컴포지션을 건너뛴다. 스크롤 오프셋 같은 고빈도 값을 상위에서 읽으면 트리 전체가 리컴포지션되지만, 람다로 미뤄 읽으면 드로잉만 다시 돈다. `Source-confirmed`

> **[그림 1]** Android Studio Layout Inspector의 리컴포지션 카운트 패널 — 같은 화면에서 스크롤 오프셋을 상위 컴포저블에서 읽을 때와 `graphicsLayer` 람다로 미뤄 읽을 때의 카운트 차이를 대조한 캡처 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

여기서 못 박아야 할 오개념이 하나 있다: **리컴포지션은 보안 경계가 아니다.** Compose는 통째로 하나의 앱 프로세스 안에서 돈다. "상태를 false로 바꿔서 UI를 숨겼다"는 것은 렌더 트리에서 컴포저블을 뺀 것일 뿐, 데이터가 프로세스 밖으로 안 나갔다거나 메모리에서 지워졌다는 뜻이 전혀 아니다. `Inferred`

실제로 신경 써야 하는 경계는 셋이다.

- **`rememberSaveable` → 앱 프로세스 밖.** 여기 담은 값은 saved instance state `Bundle`로 들어가고, 표준 Bundle은 Binder로 넘어가 **system_server(ActivityTaskManager)의 태스크 레코드 메모리**에 보관된다 — 그래서 앱 프로세스가 죽어도 살아남지만, 동시에 앱 통제 밖(다른 프로세스)으로 나간다. 여기에 더해 `android:persistableMode`(persistAcrossReboots)로 `PersistableBundle`을 쓰면 재부팅을 넘기려 **디스크에도 기록**된다. 토큰·PII 같은 비밀을 여기에 넣으면 앱이 통제 못 하는 프로세스에(그리고 `persistableMode` 시 평문으로 저장 매체에) 남을 수 있다. 비밀은 `rememberSaveable`이 아니라 ViewModel/암호화 저장소에 둔다(구성 변경·프로세스 죽음 처리는 다음 장 주제). `Reported`
- **상태 스코핑 오류 → 이전 값 노출.** 재사용되는 컴포저블에서 상태를 사용자/항목 키로 구분하지 않으면(`key(...)` 누락), 리컴포지션 타이밍에 따라 이전 항목의 값이 잠깐 남아 보인다. 이는 Compose 취약점이 아니라 정확성 버그가 기밀성 문제로 번진 경우다. `Inferred`
- **스크린샷/최근 앱 노출은 Compose 문제가 아니다.** 민감 화면의 캡처 차단은 상태가 아니라 WindowManager의 `FLAG_SECURE`(13장 WMS·UI 보안)에서 처리한다. 상태로 숨긴 것과 창 수준에서 보호한 것을 혼동하면 안 된다. `Source-confirmed`

정리하면, 여기서 유효한 경계는 **프로세스 경계(그리고 `persistableMode` 시 저장 매체, data-at-rest)** 이지, 리컴포지션 타이밍이 아니다.

## 관측 — 무엇이 스킵되는가

리컴포지션이 눈에 안 보인다는 문제는 **컴파일러 메트릭 리포트**로 직접 들여다볼 수 있다. Compose 컴파일러에 `metricsDestination`/`reportsDestination`을 켜면, 컴파일러가 각 컴포저블을 "재시작 가능(restartable)/스킵 가능(skippable)"으로 분류한 텍스트를 뱉는다. `Source-confirmed`

```kotlin
// 자작 앱 module build.gradle.kts — Compose Compiler Gradle 플러그인 DSL
composeCompiler {
    metricsDestination = layout.buildDirectory.dir("compose_compiler")
    reportsDestination = layout.buildDirectory.dir("compose_compiler")
}
```

빌드 후 `*-composables.txt`를 열면 어떤 컴포저블이 왜 스킵 불가인지가 파라미터의 stable/unstable 라벨과 함께 찍힌다.

`예시 출력`(자작 앱 빌드로 교체 — 아래는 **강한 스킵(strong skipping)을 끈** 툴체인 기준):

```
restartable skippable fun Counter(
  stable count: Int
)
restartable fun UserPanel(
  unstable users: List<User>   // List 인터페이스 → unstable → (strong skipping OFF에선) NOT skippable
)
```

`Counter`는 `count: Int`가 stable이라 부모가 리컴포지션돼도 인자가 그대로면 건너뛴다. 반면 `UserPanel`은 `List<User>` 파라미터가 unstable로 추론되어 `skippable`이 사라졌다 — 이 컴포저블은 부모가 다시 돌 때마다 **아무것도 안 바뀌어도** 같이 리컴포지션된다. 다만 이 글 시점(2026-11)의 **기본 툴체인은 강한 스킵이 켜져 있어**, 같은 `UserPanel`도 `restartable skippable`로 찍히고 unstable `List`는 참조 동일성(`===`)으로 스킵된다 — 즉 위 `NOT skippable` 출력은 강한 스킵을 끈 경우다. 매 리컴포지션마다 리스트를 **새 인스턴스로 넘기면** 강한 스킵도 무력화되므로, `kotlinx.collections.immutable`의 `ImmutableList`로 바꾸거나 안정성 설정 파일로 stable 선언하는 편이 안전하다. `Source-confirmed`

> **[그림 2]** 자작 앱을 조작하며 Layout Inspector로 본 리컴포지션 카운트와, `*-composables.txt`에서 `restartable skippable` vs `restartable`(NOT skippable)로 갈린 컴포저블 목록을 나란히 둔 캡처 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

세 부품이 맞물려 "읽은 것만 다시 실행"이 성립한다.

첫째, **스냅샷 시스템**(`androidx.compose.runtime.snapshots`)이다. 각 상태 객체는 버전별 `StateRecord`의 연결 리스트를 갖는 MVCC 구조로, 스냅샷마다 자기 버전을 읽는다. 컴포지션은 `SnapshotStateObserver`로 감싸여 "이 스코프 실행 중 읽힌 상태 집합"을 수집하고, 상태 쓰기가 적용(apply)되면 전역 스냅샷이 전진하며 **바뀐 상태를 읽었던 스코프**에게만 리컴포지션을 예약한다. 스레드 안전과 격리가 여기서 나온다. `Source-confirmed`

둘째, **위치 기반 메모이제이션(슬롯 테이블)** 이다. Composer는 컴포지션의 구조와 `remember`된 값을 호출 위치(call-site position)를 키로 슬롯 테이블에 저장한다. 그래서 `remember`는 "같은 위치면 같은 값을 돌려준다"가 되고, 트리 모양이 유지되는 한 상태가 보존된다. `Reported`

셋째, **재시작 그룹(RecomposeScope)** 이다. Compose 컴파일러는 상태를 읽는 컴포저블 본문을 독립적으로 재실행 가능한 그룹으로 감싼다. 그래서 상태 하나가 바뀌어도 트리 전체가 아니라 그 그룹 하나만 다시 돈다. `Source-confirmed` 리컴포지션은 낙관적(optimistic)이라 자주, 임의 순서로 실행되고 취소될 수 있다 — 따라서 컴포저블은 부작용이 없어야 한다는 규칙이 여기서 강제된다. `Source-confirmed`

스킵 판정이 stability에 종속되는 이유도 이 구조 때문이다. 스코프를 건너뛰려면 런타임이 "인자가 안 바뀌었다"를 `equals`로 안전하게 판단할 수 있어야 하는데, 가변일 수 있는 타입(`List`/`Map` 인터페이스, 다른 모듈의 stability 정보 없는 클래스)은 이를 보장 못 하므로 컴파일러가 unstable로 보고 스킵을 포기한다. `@Immutable`/`@Stable`은 개발자가 이 보장을 명시적으로 서약하는 계약이다. `Source-confirmed`

## 버전 차이와 한계

- **Compose 컴파일러의 소속이 바뀌었다.** Kotlin 2.0부터 Compose 컴파일러가 Kotlin 저장소로 이동해 Kotlin 버전과 함께 배포되고, Gradle에서는 `org.jetbrains.kotlin.plugin.compose` 플러그인으로 적용한다. 예전 `composeOptions { kotlinCompilerExtensionVersion }` 방식은 구버전 기준이므로 문서화할 땐 툴체인 버전을 표기한다. `Source-confirmed`
- **강한 스킵(strong skipping) 모드.** 이 모드가 기본으로 켜진 뒤로는 unstable 파라미터를 가진 컴포저블도 인스턴스 동일성(`===`) 기준으로 스킵되고 람다가 자동 `remember`된다 — 앞의 "List면 무조건 스킵 불가"가 완화된다. 다만 활성화된 정확한 컴파일러/Compose 버전 경계는 **버전 확인 필요**(대략 Kotlin 2.0.2x 계열의 Compose 컴파일러). `Reported`
- **스냅샷·슬롯 테이블은 구현 세부다.** `StateRecord` 연결 리스트, 슬롯 테이블의 내부 자료구조(갭 버퍼 등)는 공개 API가 아니라 릴리스마다 바뀔 수 있으므로, 성능 판단은 내부 구조 추정이 아니라 컴파일러 리포트·Layout Inspector 같은 **관측 도구**에 근거해야 한다. `Inferred`
- **한계.** 이 글의 관측은 자작 앱·에뮬레이터 범위이며, 리컴포지션 최소화가 곧 보안은 아니다. 보안 결론은 앞의 신뢰 경계(프로세스·저장 매체)로 돌아간다.

## 정리

- 상태를 **읽으면 구독**된다. 리컴포지션은 그 상태를 읽은 `RecomposeScope`만 다시 실행하며, 스냅샷 시스템이 읽기/쓰기를 추적한다.
- `mutableStateOf`는 상태를 만들 뿐이고 `remember`가 슬롯 테이블에 고정한다. `remember` 누락이 "매 프레임 초기화"의 원인이다.
- 스킵은 **stability**에 달렸다 — **강한 스킵이 없으면** unstable 파라미터 하나가 스킵을 깬다(강한 스킵이 켜진 기본 툴체인에선 참조 동일성으로 스킵되고, 매 리컴포지션마다 새 인스턴스를 넘길 때 깨진다). 판정은 컴파일러 메트릭 리포트로 직접 확인한다.
- 리컴포지션은 보안 경계가 아니다. 유효한 경계는 프로세스 경계(그리고 `persistableMode` 시 저장 매체)이며, `rememberSaveable`에 비밀을 넣지 않는다.

**점검 질문** — (1) `remember` 없이 `mutableStateOf`를 쓰면 왜 값이 유지되지 않는가? (2) `List<T>` 파라미터가 컴포저블의 스킵을 깨는 이유와, 컴파일러 리포트에서 이를 어떻게 확인하는가? (3) "상태를 false로 바꿔 UI를 숨겼다"가 왜 기밀성 보장이 아닌가?

**참고** — [Thinking in Compose](https://developer.android.com/develop/ui/compose/mental-model) · [State and Jetpack Compose](https://developer.android.com/develop/ui/compose/state) · [Lifecycle of composables](https://developer.android.com/develop/ui/compose/lifecycle) · [Compose phases](https://developer.android.com/develop/ui/compose/phases) · [Compose stability](https://developer.android.com/develop/ui/compose/performance/stability) · [androidx compose/runtime 소스](https://android.googlesource.com/platform/frameworks/support/+/refs/heads/androidx-main/compose/runtime/runtime/src/commonMain/kotlin/androidx/compose/runtime/)

*다음 글: [ViewModel·SavedState·process death](/posts/android-expert-p2c04/).*
