---
layout: post
title: "Kotlin·coroutine·structured concurrency"
date: 2026-11-13 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Kotlin, Coroutine, StructuredConcurrency, 동시성]
excerpt: "코루틴은 스레드가 아니라 컴파일러가 만든 상태 기계다. 그리고 가장 흔한 보안 버그는 catch(Exception)이 CancellationException까지 삼켜 취소가 먹히지 않는 것 — 로그아웃 뒤에도 코루틴이 계속 돈다."
---

Part 2는 앱에서 커널까지의 세로 단면을 소스와 함께 내려가는 파트다. 그 첫 장을 커널이 아니라 **언어/런타임**에서 시작하는 이유는 분명하다. Android 앱 코드의 거의 전부가 코루틴 위에서 돌고, 이 계층에서 조용히 생기는 버그가 이후 프레임워크·Binder 계층의 관측을 통째로 흐리기 때문이다. "코루틴이 스레드처럼 취소될 것"이라는 착각 하나가 로그아웃 뒤에도 도는 작업을 만든다.

이 글은 Kotlin 코루틴이 컴파일 시 무엇으로 바뀌는지, structured concurrency가 부모-자식 Job 계층으로 어떻게 취소·예외를 전파하는지, 그리고 그 규칙을 깨는 대표적 함정 하나(`CancellationException` 삼키기)를 자작 코드로 분석·정리한 기록이다.

> **한 줄 결론**: 코루틴은 스레드가 아니라 컴파일러가 만든 상태 기계이고, 취소는 `CancellationException`으로 구현된 **협조적** 동작이다. 그래서 `catch (e: Exception)`으로 그 예외를 삼키면 structured concurrency의 취소가 그 지점에서 끊긴다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 세 가지를 다룬다 — (1) `suspend` 함수의 CPS(continuation-passing style) 변환과 상태 기계, (2) `CoroutineScope`/`Job`/`Dispatcher`로 이루어진 structured concurrency의 취소·예외 전파 규칙, (3) 그 규칙이 곧 앱 내부의 논리적 신뢰 경계라는 관점. 공격 실습이 아니라 구조와 소스 이해가 목적이다.

선수 지식은 얕게만 필요하다. 스레드와 프로세스의 차이, JVM/ART가 바이트코드를 실행한다는 사실(이 파트 8장 ART 장에서 더 판다), 그리고 기본 Kotlin 문법이면 충분하다. Atlas의 프로세스·가상메모리 편(C04)에서 "스레드는 커널 스케줄러가 보는 실행 단위"라는 그림을 이미 가졌다면, 코루틴은 그 위에 올라탄 **사용자 공간의 협조적 스케줄링**이라는 점만 새로 얹으면 된다.

전체 구조에서 이 계층의 위치는 App→Framework→Binder→system_server→HAL→Kernel 흐름의 맨 왼쪽, 앱 프로세스 안이다. 여기서 일어나는 일은 전부 한 프로세스 안의 논리이지 OS 권한 경계를 넘지 않는다 — 이 사실이 뒤의 위협 모델을 정확히 잡는 열쇠다.

## 핵심 개념 — suspend는 상태 기계로 컴파일된다

코루틴의 정체를 한 문장으로 줄이면 이렇다. **`suspend` 함수는 컴파일 시 `Continuation<T>` 파라미터가 추가되고, 반환형이 `Any?`로 바뀌며, 중단할 때 `COROUTINE_SUSPENDED` 센티넬을 반환하는 상태 기계로 변환된다.** `Source-confirmed` 즉 `suspend fun foo(): T`는 바이트코드에서 대략 `Object foo(Continuation<? super T> cont)`가 된다.

여기서 가장 흔한 오개념을 콕 집자. **코루틴은 스레드가 아니다.** 중단(suspend)된 코루틴은 스레드를 붙잡고 있지 않는다 — 지역 변수와 "다음에 실행할 상태 번호"가 `Continuation` 객체에 저장되고, 스레드는 반납된다. 그래서 수만 개의 코루틴이 소수의 스레드 위에서 돈다. `Source-confirmed`

| 개념 | 정체 | 오개념 |
|--|--|--|
| `suspend fun` | `Continuation` 인자를 받는 상태 기계 함수 | "가벼운 스레드 함수"가 아니다 |
| 중단(suspend) | 상태 저장 후 스레드 반납, `COROUTINE_SUSPENDED` 반환 | 블로킹이 아니다 |
| `Continuation` | 지역 변수 + 재개 지점(state)을 담은 객체 | 콜백의 컴파일러판이다 |
| `Dispatcher` | 재개를 어느 스레드(풀)에서 실행할지 결정 | 격리(isolation)를 주지 않는다 |

각 중단 지점(`delay`, `await`, 다른 `suspend` 호출)은 상태 기계의 한 상태가 된다. 컴파일러가 생성하는 클래스는 `ContinuationImpl`/`SuspendLambda`를 상속하고, `invokeSuspend`의 거대한 `switch(label)`로 상태를 오간다. `Source-confirmed` 콜백 지옥을 컴파일러가 대신 써 주는 것 — 그 이상도 이하도 아니다.

> **[그림 1]** IntelliJ/Android Studio의 Tools → Kotlin → Show Kotlin Bytecode → Decompile로, 간단한 `suspend fun`이 `Continuation` 파라미터와 `label` 스위치를 가진 상태 기계로 풀린 디컴파일 결과 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

먼저 경계를 정확히 긋자. 코루틴 디스패처는 **보안 경계가 아니다.** `Dispatchers.IO`로 옮긴 코드가 격리되거나 권한이 낮아지는 일은 없다 — 같은 프로세스, 같은 uid, 같은 주소 공간이다. 여기서의 "경계"는 OS 신뢰 경계가 아니라 **생명주기와 취소로 만들어지는 논리적 경계**다.

그럼 위협은 무엇인가. 이 계층에서 보안적으로 의미 있는 실패는 셋이다.

- **수명 초과(lifecycle overrun)** — 인증 컨텍스트나 화면이 끝났는데 코루틴이 계속 돈다. `GlobalScope.launch`로 띄운 작업은 어떤 생명주기에도 묶이지 않아, 로그아웃·Activity 종료 뒤에도 민감 데이터를 계속 처리한다. `Source-confirmed`
- **취소 불이행(cancellation swallowed)** — structured concurrency가 취소 신호를 보냈는데 코드가 이를 무시한다. 대표 원인이 `catch (e: Exception)`로 `CancellationException`까지 삼키는 것. 취소는 협조적이라, 협조를 거부한 코루틴은 멈추지 않는다. `Source-confirmed`
- **무제한 실행(unbounded launch)** — 입력마다 스코프에 코루틴을 무한정 launch하면, 부모 Job이 살아 있는 한 자식이 쌓여 자기 자신에 대한 자원 고갈(로컬 DoS)이 된다. `Inferred`

세 가지 모두 "메모리 손상"이나 "권한 상승"이 아니다. 과장하지 말자 — 이건 **정확성 결함이 곧 논리적 보안 결함이 되는** 사례이지 RCE가 아니다. 다만 로그아웃 뒤에도 도는 백그라운드 폴링, 취소되지 않는 위치 수집 같은 것은 실제 개인정보·수명 관점에서 문제가 된다.

## 분석 — structured concurrency의 취소는 어떻게 끊기는가

structured concurrency의 규칙은 `Job` 계층으로 정의된다. `CoroutineScope`의 `CoroutineContext`는 `Job`을 품고, `launch`/`async`는 그 `Job`의 **자식** `Job`을 만든다. 규칙은 셋이다. `Source-confirmed`

1. 부모 스코프는 모든 자식이 끝날 때까지 완료되지 않는다(`coroutineScope { }`가 이를 보장).
2. 부모가 취소되면 취소가 자식으로 **전파**된다.
3. 자식의 처리되지 않은 예외는 부모를 취소한다 — 단 `SupervisorJob`/`supervisorScope`에서는 형제·부모로 번지지 않는다.

취소의 실제 구현이 핵심이다. `job.cancel()`은 코루틴의 다음 중단 지점에서 `CancellationException`을 던지는 것으로 동작한다. kotlinx.coroutines의 모든 중단 함수(`delay`, `withContext`, `join` 등)는 재개 시 취소 여부를 확인하고 이 예외를 던진다. 그래서 **CPU 바운드 루프**처럼 중단 지점이 없는 코드는 스스로 `ensureActive()`/`yield()`/`isActive`로 확인하지 않으면 취소되지 않는다. `Source-confirmed`

그리고 `CancellationException`은 특별 취급된다 — structured concurrency는 이를 "정상적인 취소 신호"로 보고 `CoroutineExceptionHandler`로 전파하지 않는다. `Source-confirmed` 문제는 여기서 생긴다. 넓은 `catch (e: Exception)`은 `CancellationException`(이는 `Exception`의 하위형)까지 잡아 삼키고, rethrow하지 않으면 취소가 그 지점에서 소멸한다.

자작 최소 재현 코드다(JVM `runBlocking`, 안전 범위 내 개념 확인용):

```kotlin
import kotlinx.coroutines.*

fun main() = runBlocking {
    val job = launch(Dispatchers.Default) {
        repeat(1000) { i ->
            try {
                println("작업 $i")
                delay(100)               // 취소 확인 지점
            } catch (e: Exception) {     // 함정: CancellationException까지 삼킴
                println("삼킴: ${e::class.simpleName} — 계속 진행")
                // rethrow 없음 → 취소가 매 반복 무시된다
            }
        }
    }
    delay(350)
    println("cancel() 호출")
    job.cancel()                          // 취소 요청
    job.join()
    println("종료")
}
```

취소를 존중하는 올바른 형태는 세 갈래다 — (a) `CancellationException`을 다시 던지거나, (b) `catch (e: IOException)`처럼 잡을 예외를 좁히거나, (c) `catch` 안에서 `coroutineContext.ensureActive()`를 호출해 취소 시 재-throw하게 하는 것. `Source-confirmed`

한 가지 서브틀한 함정도 짚자. `async`의 예외는 항상 `await()`에서만 터진다고 흔히 오해하는데, **일반(비-supervisor) 스코프 안에서 실행된 `async`의 예외는 `await` 이전에 부모로 즉시 전파되어 스코프를 취소**한다. `await`는 그걸 다시 던질 뿐이다. (`supervisorScope`/`SupervisorJob` 하에서는 부모로 즉시 전파되지 않고 `await()`까지 지연된다 — 라인 60의 예외 규칙과 일관.) `Reported`

> **[그림 2]** 위 코드를 `-Dkotlinx.coroutines.debug`(또는 코루틴 이름 부여)로 실행해, `cancel()` 이후에도 "삼킴 … 계속 진행"과 "작업 N"이 계속 찍히는 콘솔 — 취소가 먹히지 않음을 보여주는 로그 — *실측 스크린샷 자리*

`예시 출력(교체)`(직접 실행으로 대체):

```
작업 0
작업 1
작업 2
작업 3
cancel() 호출
삼킴: JobCancellationException — 계속 진행
작업 4
삼킴: JobCancellationException — 계속 진행
작업 5
...
```

`cancel()` 뒤에도 루프가 계속 도는 것이 핵심 관측이다. `catch`를 좁히거나 rethrow하면 `cancel()` 직후 코루틴이 멈춘다.

## Root Cause — 왜 이렇게 되는가

근본 원인은 **취소가 예외 메커니즘 위에 얹혀 있다**는 설계 선택이다. 코루틴은 스레드가 아니므로 OS가 강제로 죽일 수 있는 `Thread.stop()` 같은 난폭한 수단이 없고(있어도 안전하지 않고), 대신 "다음 중단 지점에서 `CancellationException`을 던진다"는 협조적 방식을 택했다. `Source-confirmed` 협조적이라는 말은 곧 **코드가 협조를 거부할 수 있다**는 뜻이다.

`catch (e: Exception)`가 위험한 이유가 여기서 나온다. `CancellationException`은 취소를 나르는 **정상 신호**인데, 자바 세계의 관습("모든 예외는 잡아서 로깅한다")이 이 신호를 오류로 오인해 삼킨다. 신호가 삼켜지면 상태 기계는 다음 상태로 그냥 넘어가고, structured concurrency의 부모는 자식이 끝나기를 계속 기다린다. 취소가 "전파되다 만" 상태가 되는 것이다.

`GlobalScope` 문제도 같은 뿌리다. `GlobalScope`는 어떤 부모 `Job`에도 묶이지 않은 최상위 스코프라, 취소를 전파해 줄 부모가 애초에 없다. 그래서 화면·인증 컨텍스트가 사라져도 그 작업은 자기 수명을 스스로 산다. structured concurrency의 핵심 가치("부모가 자식의 수명을 책임진다")를 정면으로 버리는 API인 셈이다. `Source-confirmed`

## 방어와 회귀 검증

방어는 코드 리뷰로 잡을 수 있는 세 규칙으로 압축된다.

- **`CancellationException`을 절대 삼키지 말 것.** 넓은 `catch (e: Exception)` 안에서는 `if (e is CancellationException) throw e`를 첫 줄에 두거나, `ensureActive()`를 호출한다. Kotlin 표준 lint/detekt에 관련 규칙(예: `SwallowedException`, 코루틴용 규칙 세트)이 있으니 CI에 건다. `Reported`(정확한 규칙 ID는 사용하는 detekt 버전 확인 필요)
- **생명주기 있는 스코프를 쓸 것.** Android에선 `GlobalScope` 대신 `viewModelScope`/`lifecycleScope`를 쓴다. `viewModelScope`는 `SupervisorJob() + Dispatchers.Main.immediate`로 구성되어, ViewModel이 `onCleared`될 때 자식을 자동 취소한다. `Source-confirmed`(androidx 소스)
- **디스패처에 격리를 기대하지 말 것.** 민감 작업을 `Dispatchers.IO`로 옮겨도 신뢰 경계는 그대로다. 격리가 필요하면 프로세스 분리(별도 `:process`)나 실제 권한 경계로 가야 한다. `Inferred`

**회귀 검증(runnable check).** 위 재현 코드에서 `catch (e: Exception)`를 아래 한 줄로 좁히거나 rethrow를 추가한 뒤, `cancel()` 직후 출력이 멈추는지를 회귀 기준으로 삼는다.

```kotlin
} catch (e: Exception) {
    coroutineContext.ensureActive()   // 취소면 여기서 다시 throw → 루프 종료
    println("실오류 처리: ${e::class.simpleName}")
}
```

기준선은 단순하다 — **`cancel()` 이후 새 "작업 N" 로그가 0줄**이면 취소가 정상 전파된 것이고, 한 줄이라도 더 찍히면 어딘가 `CancellationException`이 삼켜지고 있다는 회귀 신호다. 스냅샷이나 별도 도구 없이 콘솔 로그 한 판으로 판정된다.

## 정리

- `suspend`는 컴파일러가 만든 상태 기계다. 코루틴은 스레드가 아니고, 중단은 블로킹이 아니며, 디스패처는 격리를 주지 않는다.
- structured concurrency는 `Job` 계층으로 취소·예외를 전파하고, 취소는 `CancellationException`을 던지는 협조적 동작이다.
- 이 계층의 보안은 권한이 아니라 **수명·취소의 정확성**이다. `CancellationException` 삼키기와 `GlobalScope`가 그 정확성을 깨는 두 축이다.
- Dispatcher 기본값·detekt 규칙 ID 등 세부 수치는 kotlinx.coroutines/도구 버전에 종속되니 문서화 시 버전을 표기한다.

**점검 질문** — (1) `catch (e: Exception)`가 코루틴 취소를 어떻게 무력화하는가, 이를 막는 최소 수정은? (2) 중단 지점이 없는 CPU 루프를 취소 가능하게 만들려면 무엇을 호출해야 하는가? (3) `Dispatchers.IO`로 옮긴 코드가 왜 보안 경계를 만들지 못하는가?

**참고** — [Kotlin Coroutines: Cancellation and timeouts](https://kotlinlang.org/docs/cancellation-and-timeouts.html) · [Coroutine exceptions handling](https://kotlinlang.org/docs/exception-handling.html) · [kotlinx.coroutines (GitHub)](https://github.com/Kotlin/kotlinx.coroutines) · [Android: Coroutines best practices](https://developer.android.com/kotlin/coroutines/coroutines-best-practices) · [androidx lifecycle-viewmodel 소스](https://cs.android.com/androidx/platform/frameworks/support)

*다음 글: [Flow·StateFlow·lifecycle](/posts/android-expert-p2c02/).*
