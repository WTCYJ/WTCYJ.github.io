---
layout: post
title: "Flow·StateFlow·lifecycle"
date: 2026-11-14 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Kotlin, Flow, StateFlow, Coroutines]
excerpt: "화면이 꺼져도 lifecycleScope.launch { flow.collect } 는 계속 수집한다 — repeatOnLifecycle 로 STARTED 아래서 취소해야 한다. 그리고 StateFlow 는 equals() 로 같은 값을 버리므로, 가변 객체를 제자리에서 바꾸면 collector 는 그 변경을 못 본다."
---

Android UI는 결국 상태를 그린다. 그 상태를 어디서 만들어 어떻게 화면까지 흘려보내느냐가 현대 앱 아키텍처의 뼈대이고, 그 파이프라인이 코루틴 위의 Flow·StateFlow다. 문제는 이 파이프라인이 **화면이 꺼져도 조용히 계속 흐른다**는 것이다. 위치·센서·네트워크를 물고 있는 hot 소스에 lifecycle을 모르는 collector를 붙이면, 앱이 백그라운드로 내려가도 수집이 살아 있어 배터리를 갉아먹고, 때로는 보이지 않는 화면을 갱신하려다 크래시한다.

이 글은 Flow의 cold/hot 구분, StateFlow의 conflation·equality 동작, 그리고 lifecycle을 아는 안전한 수집(`repeatOnLifecycle`)이 왜 필요한지를 1차 문서와 함께 정리·분석한 기록이다. 공격 실습이 아니라, 상태 파이프라인이 신뢰 경계(화면의 STARTED/STOPPED)를 어떻게 넘나드는지를 구조로 이해하는 데 초점을 둔다.

> **한 줄 결론**: Flow는 cold(수집해야 흐른다)고 StateFlow는 hot(항상 값이 있다)이다. UI에서 수집할 땐 `repeatOnLifecycle(STARTED)`로 감싸 백그라운드에서 취소되게 하고, StateFlow는 `equals()`로 같은 값을 버리므로 상태는 항상 새 인스턴스로 갈아끼워야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 범위는 셋이다. (1) Flow(cold) vs StateFlow/SharedFlow(hot)의 구조적 차이, (2) StateFlow의 conflation과 `equals()` 기반 중복 제거가 만드는 대표적 함정, (3) UI 계층에서 lifecycle을 존중하며 수집하는 방법과 그 보안·자원 의미.

선수 지식은 2부 1장(Kotlin·코루틴·구조적 동시성)이다. `CoroutineScope`가 자식 Job의 생명주기를 묶고, 스코프 취소가 아래로 전파되며, `suspend` 함수가 취소 지점에서 협조적으로 멈춘다는 감각이 있어야 이 글의 "수집을 취소한다"가 와닿는다. 여기에 Android 쪽 선수 개념으로 Activity/Fragment의 lifecycle 상태(CREATED→STARTED→RESUMED)와, Fragment에서 뷰의 수명은 Fragment 자체보다 짧아 `viewLifecycleOwner`를 써야 한다는 점을 알아야 한다. 프로세스·메모리의 바닥 개념은 Atlas C04를 참고하면 된다.

전체 구조에서 이 장은 App 계층의 **상태 흐름**을 다룬다. 다음 장의 Compose recomposition은 바로 이 StateFlow/State를 구독해 화면을 다시 그리므로, 여기서 파이프라인을 잘못 깔면 그 위의 UI가 통째로 흔들린다.

## 핵심 개념 — cold vs hot, 그리고 conflation

Flow는 **cold**다. `flow { }` 빌더 안의 코드는 `collect`가 호출될 때 비로소 실행되고, collector가 둘이면 두 번 처음부터 실행된다 — 수집 전에는 아무것도 흐르지 않는다. `Source-confirmed` 반면 StateFlow·SharedFlow는 **hot**이라 collector 유무와 무관하게 존재하고, 특히 StateFlow는 언제나 현재 값 하나를 갖는다. `Source-confirmed`

StateFlow의 성격을 표로 못박으면 아래와 같다.

| 성질 | 동작 | 근거 |
|--|--|--|
| 초기값 필수 | `MutableStateFlow(initial)` — 값 없는 상태가 없다 | `Source-confirmed` |
| conflated | 느린 collector는 중간 값을 건너뛰고 항상 최신 값을 받는다 | `Source-confirmed` |
| equality 중복 제거 | 새 값이 `equals()`로 이전 값과 같으면 방출하지 않는다(내장 distinct) | `Source-confirmed` |
| lifecycle 무관 | LiveData와 달리 스스로 화면 상태를 모른다 | `Source-confirmed` |

여기서 가장 자주 밟는 지뢰가 equality 중복 제거다. 상태를 가변 객체로 두고 **제자리(in-place)에서 필드만 바꾼 뒤 같은 참조를 다시 대입**하면, `equals()`가 true라 StateFlow는 "값이 안 변했다"고 판단해 방출을 건너뛴다 → 화면이 갱신되지 않는다. `Inferred` 그래서 상태는 `data class`로 만들고 `state.value = state.value.copy(...)`처럼 **항상 새 인스턴스**로 갈아끼운다. `Source-confirmed` (StateFlow의 중복 제거는 `equals` 구현을 그대로 따르므로, `equals`가 부정확하면 방출 판정이 어긋날 수 있다.) `Inferred`

이벤트(일회성)에는 StateFlow가 아니라 SharedFlow를 쓴다. StateFlow는 개념상 replay=1의 conflated SharedFlow라 재구독 때 마지막 상태를 다시 준다 — "스낵바 한 번 보여주기" 같은 이벤트를 StateFlow에 담으면 화면 회전 후 그 이벤트가 되살아난다. `Inferred`

> **[그림 1]** 자작 앱에서 `MutableStateFlow`에 같은 값을 연달아 대입(예: `value = 1; value = 1`)했을 때 collector 쪽 `Log.d`가 한 번만 찍히는 logcat — 방출 conflation을 실측하는 자리 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

여기서 신뢰 경계는 외부 공격자가 아니라 **화면의 가시성 경계(STARTED 이상 vs STOPPED)**다. 위협 모델은 "백그라운드에서 조용히 살아 있는 파이프라인"이다. 세 가지가 이 경계를 넘어 새어 나간다.

- **자원·프라이버시**: 위치·센서·카메라·마이크 같은 hot 소스에 붙은 collector가 백그라운드에서도 살아 있으면, 사용자가 화면을 껐다고 믿는 동안에도 데이터가 계속 흐른다. 이건 배터리 문제이자, 민감 데이터가 불필요하게 백그라운드에서 유통되는 문제다.
- **STOPPED 상태 UI 갱신**: 화면이 멈춘 뒤 도착한 방출로 UI를 만지면(특히 FragmentManager 트랜잭션) `IllegalStateException`으로 크래시할 수 있다. `Reported`
- **누수**: lifecycle을 모르는 수집 Job이 `viewLifecycleOwner` 대신 잘못된 스코프에 묶이면, 파괴된 뷰를 참조한 채 살아남아 메모리 누수가 된다.

과장하지 말자. 이건 원격 코드 실행도, 권한 상승도 아니다. **자원 낭비·비의도적 백그라운드 활동·크래시·누수**의 범주다. 그러나 민감 데이터 파이프라인일수록 "언제 멈추는가"가 곧 노출 표면이므로, lifecycle 경계를 지키는 것은 성능이 아니라 위생의 문제다.

## 분석 — 안전한 수집은 무엇을 하는가

핵심은 세 가지 UI 수집 방식의 차이다.

```kotlin
// (1) 위험 — 백그라운드에서도 계속 수집. STOPPED에서 UI 갱신 시 크래시 가능
lifecycleScope.launch {
    viewModel.uiState.collect { render(it) }
}

// (2) 애매 — launchWhenStarted 는 수집을 '취소'가 아니라 '일시정지(suspend)'만 한다.
//     상류 producer 는 계속 돌아 자원을 붙든다. (lifecycle 2.6.x 에서 deprecated — 정확 버전 원문 확인)
lifecycleScope.launchWhenStarted {
    viewModel.uiState.collect { render(it) }
}

// (3) 권장 — STARTED 미만으로 내려가면 블록 전체를 '취소', 다시 올라오면 '재시작'
lifecycleScope.launch {
    repeatOnLifecycle(Lifecycle.State.STARTED) {
        viewModel.uiState.collect { render(it) }
    }
}
```

(2)와 (3)의 차이가 이 글의 심장이다. `launchWhenStarted`류는 코루틴을 **suspend**만 시키므로 collect 아래의 상류 flow는 계속 값을 만들고, hot 소스라면 그 자원이 백그라운드에서 그대로 붙잡힌다. `Source-confirmed` 반면 `repeatOnLifecycle(STARTED)`는 STARTED 미만에서 블록을 **취소**해 collect를 끊고, 상류 cold flow까지 정지시킨다 — 그리고 다시 STARTED로 올라오면 처음부터 재수집한다. `Source-confirmed`

`repeatOnLifecycle`은 `androidx.lifecycle:lifecycle-runtime-ktx`에 들어 있고 2.4.0에서 도입됐다. `Reported` 단일 flow만 lifecycle에 묶고 싶으면 연산자 형태인 `flowWithLifecycle(lifecycle, STARTED)`를 collect 앞에 붙이는 대안도 있다. `Source-confirmed` Fragment에서는 반드시 `viewLifecycleOwner.lifecycleScope`와 `viewLifecycleOwner.repeatOnLifecycle`을 쓴다 — Fragment 인스턴스의 스코프는 뷰보다 오래 살아 누수를 만든다. `Source-confirmed`

ViewModel 쪽에서 cold flow를 StateFlow로 노출할 때는 `stateIn`을 쓴다.

```kotlin
val uiState: StateFlow<UiState> =
    repository.observe()                       // cold flow
        .map { it.toUiState() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = UiState.Loading,
        )
```

`WhileSubscribed(5000)`은 구독자가 생기면 상류를 시작하고 **마지막 구독자가 사라진 뒤 5초 뒤에 멈춘다**. 이 5초 유예가 화면 회전 같은 짧은 구성 변경 동안 상류를 껐다 켜지 않게 해준다 — Android 아키텍처 가이드가 이 값을 권장한다. `Source-confirmed`

**관측(교체).** 자작 앱에 `repeatOnLifecycle` 버전과 위험한 `launch` 버전을 각각 넣고, 앱을 홈으로 내렸다가 다시 열며 로그를 본다.

```bash
adb logcat -s FlowLab   # 자작 앱 태그만 필터
```

`예시 출력(교체)`:

```
# repeatOnLifecycle(STARTED) 버전 — 백그라운드 진입 시 수집이 끊긴다
FlowLab: onStart -> repeatOnLifecycle block START
FlowLab: collect value=42
--- (홈 버튼으로 백그라운드) ---
FlowLab: onStop -> repeatOnLifecycle block CANCELLED
--- (다시 포그라운드) ---
FlowLab: onStart -> repeatOnLifecycle block START (재시작)

# 위험한 lifecycleScope.launch 버전 — 백그라운드에서도 계속 찍힌다
FlowLab: collect value=87   (앱이 보이지 않는데도 방출이 이어짐)
```

> **[그림 2]** 같은 자작 앱에서 위험한 `launch` 버전과 `repeatOnLifecycle` 버전을 나란히 두고, 앱을 백그라운드로 내렸을 때 전자는 로그가 계속 찍히고 후자는 CANCELLED 후 멈추는 대조 logcat — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

두 함정의 뿌리는 하나씩이다.

**수집이 안 멈추는 이유**는 코루틴 취소가 lifecycle과 자동으로 엮이지 않기 때문이다. `lifecycleScope`는 lifecycle이 DESTROYED가 될 때만 취소된다 — 즉 STOPPED로 내려가도 스코프는 살아 있고, 그 안의 `collect`는 상류가 값을 주는 한 계속 돈다. `Source-confirmed` LiveData는 옵저버가 lifecycle을 알고 STARTED 미만에서 스스로 콜백을 멈추지만, StateFlow는 그냥 flow라 그런 지능이 없다. 그래서 lifecycle 인식을 `repeatOnLifecycle`이라는 별도 장치로 **명시적으로** 얹어야 한다. `Inferred`

**같은 값이 안 보이는 이유**는 StateFlow가 방출 전에 `previous.equals(new)`로 중복을 거르기 때문이다. `Source-confirmed` 이건 성능을 위한 의도된 설계(불필요한 recomposition/렌더 방지)지, 버그가 아니다. 문제는 개발자가 상태를 **가변 객체 + 제자리 변경**으로 다루는 순간, 이전 값과 새 값이 같은 참조가 되어 `equals()`가 항상 true가 된다는 것이다. 설계(불변 상태 + copy)와 자료구조(가변 객체) 사이의 불일치가 원인이며, 해법은 상태를 불변 `data class`로 두고 매번 `copy()`하는 것이다. `Inferred`

## 방어와 회귀 검증

- UI 수집은 예외 없이 `repeatOnLifecycle(STARTED)`(또는 `flowWithLifecycle`)로 감싼다. `launchWhenStarted`/`launchWhenResumed`는 suspend만 하므로 상류 자원을 붙든다 — 새 코드에서 쓰지 않는다.
- Fragment에서는 `viewLifecycleOwner`를 쓴다. `this`(Fragment)로 묶으면 뷰가 파괴돼도 수집이 살아 누수·크래시가 된다.
- ViewModel의 상태는 `stateIn(WhileSubscribed(5000))`로 노출해, 구독자가 없을 때 상류를 멈추되 회전에는 견디게 한다.
- 상태는 불변 `data class`로 두고 `copy()`로만 갱신한다. `MutableStateFlow`에 가변 객체를 제자리 변경해 다시 넣지 않는다.
- 이벤트는 StateFlow가 아니라 SharedFlow(또는 채널)로 흘려 재구독 시 되살아나지 않게 한다.

**회귀 검증**은 두 층으로 한다. (1) 상태 로직은 `runTest` + `Turbine`의 `test { }`로 방출 시퀀스를 단언한다 — 같은 값을 두 번 넣었을 때 방출이 한 번인지, `copy()`한 뒤에는 방출되는지를 테스트로 고정하면 equality 함정이 회귀로 잡힌다. `Reported` (2) lifecycle 취소는 자작 앱에서 [그림 2]처럼 백그라운드 진입 시 로그가 멈추는지를 매 릴리스에 육안/logcat으로 확인한다. 안드로이드 스튜디오 lint의 `RepeatOnLifecycleWrongUsage` 계열 경고도 켜 둔다. `Reported`

한계도 분명하다. `repeatOnLifecycle`은 STOPPED에서 상류까지 **취소**하므로, 백그라운드에서도 계속 흘러야 하는 작업(예: 진행 중인 업로드 알림)은 UI 스코프가 아니라 별도의 애플리케이션 스코프나 WorkManager로 옮겨야 한다 — 이 경우 lifecycle에 묶는 것이 오히려 틀린 답이다. `Inferred`

## 정리

- Flow는 cold(수집해야 흐른다), StateFlow/SharedFlow는 hot(collector와 무관하게 산다). StateFlow는 항상 값 하나를 갖는다.
- UI 수집은 `repeatOnLifecycle(STARTED)`로 감싸 백그라운드에서 취소되게 한다. `launchWhenStarted`는 suspend만 해서 상류 자원을 붙든다.
- StateFlow는 `equals()`로 같은 값을 버린다 — 상태는 불변 `data class`로 두고 `copy()`로만 갱신한다.
- 신뢰 경계는 화면의 STARTED/STOPPED다. 잘못 수집하면 자원 낭비·비의도적 백그라운드 활동·크래시·누수가 새어 나온다(RCE·권한 상승이 아니다).

**점검 질문** — (1) `launchWhenStarted`와 `repeatOnLifecycle(STARTED)`가 상류 flow에 각각 무엇을 하는가(suspend vs cancel)? (2) `MutableStateFlow`에 같은 값을 두 번 대입하면 collector는 몇 번 받으며, 그 이유는? (3) Fragment에서 `viewLifecycleOwner` 대신 `this`로 수집을 묶으면 무엇이 잘못되는가?

**참고** — [Kotlin Flow](https://kotlinlang.org/docs/flow.html) · [StateFlow/SharedFlow](https://kotlinlang.org/docs/flow.html#stateflow-and-sharedflow) · [A safer way to collect flows](https://developer.android.com/topic/architecture/ui-layer/state-production#stateflow) · [Lifecycle-aware components (repeatOnLifecycle)](https://developer.android.com/topic/libraries/architecture/coroutines#restart)

*다음 글: [Jetpack Compose state·recomposition](/posts/android-expert-p2c03/).*
