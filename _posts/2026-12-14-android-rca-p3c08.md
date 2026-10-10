---
layout: post
title: "Java exception·logic bug RCA"
date: 2026-12-14 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RCA, Java, Exception, LogicBug]
excerpt: "스택 트레이스 맨 위 프레임은 폴트 사이트지 근본원인이 아니다. 그리고 로그캣에 아무것도 안 뜨는 logic bug — 안 죽었다고 버그가 없는 게 아니다."
---

네이티브 크래시는 툼스톤과 시그널로 요란하게 죽는다. 그래서 오히려 분석하기 쉽다. 반면 Java 쪽 결함은 두 얼굴이다. 하나는 `FATAL EXCEPTION`으로 앱을 강제 종료시키는 예외 — 시끄럽지만 메모리 안전한 런타임에서 나므로 위험 등급은 대개 낮다. 다른 하나는 아무것도 죽이지 않고 로그캣에 한 줄도 안 남기는 logic bug — 조용하지만 보안 불변식을 실제로 깨는 쪽이다. 이 두 얼굴을 같은 잣대로 다루면 심각도를 정반대로 매긴다.

이 글은 자작 결함 앱을 에뮬레이터에서 돌려, Java 예외와 logic bug의 근본원인을 각각 어떻게 분해하는지를 정리한 기록이다. 증상/트리거/폴트 사이트/근본원인의 4분할을 Java 맥락에 그대로 대입하고, "크래시 = 취약점"·"안 죽으면 안전"이라는 두 오개념을 콕 집는다.

> **한 줄 결론**: Java 예외는 메모리 안전한 런타임에서 나므로 (해당 프로세스) DoS이지 RCE가 아니다. 진짜 위험은 조용히 삼켜진 예외가 만드는 fail-open logic bug이고, 이건 스택 트레이스가 아니라 차등 테스트로만 잡힌다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 두 가지다. (1) 앱/시스템 컴포넌트에서 발생하는 uncaught Java 예외의 RCA와 익스플로잇 가능성 산정, (2) 크래시 없이 보안 판단만 틀리는 logic bug의 RCA. 대상은 전부 자작 결함 앱과 AVD 에뮬레이터로 한정한다. 제3자·프로덕션 앱은 건드리지 않고, PoC는 "프리미티브가 존재한다"까지만 — 무기화는 없다.

선수 개념 셋. 첫째, 이 파트 1장에서 세운 **증상/트리거/폴트 사이트/근본원인** 4분할 — 이 글은 그걸 Java에 대입하는 응용편이다. 둘째, Atlas의 **Intent·exported 컴포넌트** 개념 — 어떤 컴포넌트가 다른 앱에서 호출 가능한지가 신뢰 경계를 정한다. 셋째, 1부 실습에서 다룬 **logcat·`AndroidRuntime` 태그** 판독 — Java 크래시의 1차 증거가 여기 쌓인다. 이 세 개가 없으면 이 글은 겉돈다.

전체 구조에서 이 장의 위치는 "관리 런타임 쪽 RCA"다. 이후 장들이 다루는 네이티브 메모리 손상(OOB·UAF)과 대비되는 축이며, 바로 다음 장의 Binder caller identity 오류도 결국 Java 레벨 logic bug의 특수한 형태다.

## 핵심 개념 — Java 결함의 두 얼굴과 4분할

Java 결함을 볼 때 제일 먼저 갈라야 하는 건 "죽었나 안 죽었나"가 아니라 **불변식이 깨졌나**다. 아래 표가 두 얼굴을 나눈다.

| 구분 | uncaught 예외 | logic bug(fail-open 포함) |
|--|--|--|
| 증상 | `FATAL EXCEPTION`, 앱/프로세스 종료 | 없음 — 정상 동작처럼 보임 |
| 1차 증거 | logcat `AndroidRuntime` 스택 트레이스 | 없음 — 로그캣 무증상 |
| 발견 수단 | 크래시 로그·툼스톤 아님(Java) | 차등 테스트·불변식 검사 |
| 메모리 영향 | 없음(ART 관리 런타임) | 없음 |
| 통상 영향 | DoS(해당 프로세스) | 우회 대상에 따라 상승 가능 |

4분할을 Java에 대입하면 이렇게 된다. `Inferred`

- **증상(Symptom)** — 관측된 결과. `NullPointerException`으로 인한 강제 종료, 또는 "권한 없는 앱이 보호된 화면에 진입함" 같은 잘못된 상태.
- **트리거(Trigger)** — 그 증상을 만드는 최소 입력. action이 비어 있는 Intent, 또는 검사 함수를 예외로 몰아넣는 조작된 extra.
- **폴트 사이트(Fault site)** — 예외가 실제로 던져진 코드 위치. 스택 트레이스 **맨 위 앱 프레임**이 여기다.
- **근본원인(Root cause)** — 잘못된 값/가정이 처음 생긴 곳. 폴트 사이트보다 여러 프레임 위쪽이거나, 아예 다른 함수다.

여기서 가장 흔한 오독 하나 — 스택 트레이스 맨 위 프레임을 근본원인으로 적는 것. 예외는 "나쁜 값이 결국 규칙을 위반하는 지점"에서 던져질 뿐, 그 나쁜 값은 대개 위에서 만들어진다. 폴트 사이트는 증상의 좌표지 원인의 좌표가 아니다. `Inferred`

또 하나 — 체인된 예외에서 `Caused by:` 블록은 **아래로 갈수록 원래 원인**이다. Java `Throwable`은 생성자나 `initCause()`로 원인 예외를 감싸고 `getCause()`로 그 원인을 읽으며, 스택 출력은 감싼 예외를 위에, 원래 예외를 `Caused by:`로 아래에 찍는다. RCA에서 읽어야 할 첫 줄은 맨 위가 아니라 맨 아래 `Caused by:`인 경우가 많다. `Source-confirmed`

> **[그림 1]** 자작 앱을 크래시시킨 뒤 `adb logcat -b crash` 또는 `AndroidRuntime` 필터로 잡은 스택 트레이스에서, 맨 위 앱 프레임(폴트 사이트)과 `Caused by:` 최하단(원래 원인)을 각각 표시한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

에뮬레이터(`google_apis` userdebug, x86_64)와 자작 앱 하나로만 진행한다. 앱에는 exported 컴포넌트 둘을 둔다 — 하나는 null-action에 터지는 `CrashActivity`, 하나는 예외를 삼켜 fall-through하는 `GateActivity`. 둘 다 내가 만든 결함이고, 트리거는 로컬 `adb`로만 넣는다. 실기기·실서비스·타사 앱은 대상이 아니다.

## 실습 절차와 관측

### 가설
- **가설 A** — action 없는 Intent로 `CrashActivity`를 띄우면 `getAction()`이 null을 반환하고, 뒤이은 `.equals(...)` 호출이 `NullPointerException`으로 앱을 강제 종료시킨다. 이건 크래시(증상)지만 메모리 손상은 없다. `Inferred`
- **가설 B** — `GateActivity`의 권한 검사 함수를 예외로 몰면, `catch`가 예외를 삼켜 `allowed`가 허용 기본값(stale-true)인 채로 남고, 게이트가 그대로 열려 fail-open된다. 크래시는 없고 로그캣도 조용하다. `Inferred`

### 절차
자작 앱의 결함 코드는 아래 두 조각이다(개념 수준).

```java
// (A) CrashActivity.onCreate — 폴트 사이트는 여기, 근본원인은 getAction 쪽
String action = getIntent().getAction();
if (action.equals("com.wtcy.rcalab.DO")) {   // action == null 이면 NPE
    doStuff();
}

// (B) GateActivity.onCreate — swallowed exception = fail-open
boolean allowed = true;                       // 초기값이 '허용'이라 이미 위험
try {
    allowed = checkCaller(getIntent());       // 조작된 extra면 여기서 throw
} catch (Exception e) {
    // 로그도 없이 삼킴 → allowed 는 stale-true 인 채로 남음
}
// 예외로 검사가 건너뛰어지면 allowed 가 true 로 굳어 게이트를 통과
if (allowed) openProtectedScreen();           // 예외 경로에서만 fail-open
```

트리거는 각각 이렇게 넣는다.

```bash
# (A) action 을 생략 → getAction() == null → NPE 유도
adb shell am start -n com.wtcy.rcalab/.CrashActivity
adb logcat -b crash                         # 또는:  adb logcat *:S AndroidRuntime:E

# (B) checkCaller 를 예외로 모는 조작된 extra 를 넣고, 화면 진입 여부만 관측
adb shell am start -n com.wtcy.rcalab/.GateActivity --es token "%%%"
adb shell dumpsys activity activities | grep -i gateactivity   # 진입했는지 확인
```

> **[그림 2]** 같은 앱에 (A) null-action으로 크래시를 낸 로그캣과 (B) 조작된 extra로 `GateActivity`가 로그 한 줄 없이 보호 화면에 진입한 `dumpsys` 결과를 나란히 둔 대조 캡처 — *실측 스크린샷 자리*

### 관측 결과

(A)의 `예시 출력(교체)` — 실제 실행 로그로 교체:

```
E AndroidRuntime: FATAL EXCEPTION: main
E AndroidRuntime: Process: com.wtcy.rcalab, PID: 12345
E AndroidRuntime: java.lang.NullPointerException: Attempt to invoke virtual method
    'boolean java.lang.String.equals(java.lang.Object)' on a null object reference
E AndroidRuntime:     at com.wtcy.rcalab.CrashActivity.onCreate(CrashActivity.java:23)
E AndroidRuntime:     at android.app.Activity.performCreate(Activity.java:8000)
E AndroidRuntime:     at android.app.ActivityThread.performLaunchActivity(...)
```

여기서 폴트 사이트는 `CrashActivity.java:23`(맨 위 앱 프레임)이다. 하지만 근본원인은 그 줄이 아니라 **`getAction()`이 null을 반환할 수 있는데 가드가 없다**는 사실이다. 게다가 상수를 뒤에 두고 `action.equals("…")`로 호출한 순서 자체가 null-역참조를 부른다. `Source-confirmed`

(B)는 출력이 없다. 로그캣도 툼스톤도 없고, `dumpsys`에서 보호 화면이 떠 있다는 사실만 남는다. 증상이 "무증상"이라는 것 — 이게 logic bug RCA의 핵심 난점이다. 크래시 도구가 못 잡으니, "정상 호출 vs 예외 유발 호출"을 나란히 돌려 결과 차이로만 존재를 증명해야 한다. `Inferred`

## Root Cause — 왜 이렇게 되는가

(A)의 근본원인은 **nullable 계약 무시**다. `Intent.getAction()`은 action이 설정되지 않았으면 null을 반환하도록 문서화돼 있다. exported 컴포넌트는 아무 앱이나(또는 `am`) action 없이 호출할 수 있으므로, null은 예외 상황이 아니라 정상 입력의 일부다. 코드가 이 계약을 무시하고 곧장 역참조하면 폴트 사이트에서 NPE가 난다. `Source-confirmed` 고치는 지점은 폴트 사이트가 아니라 값이 들어오는 경계 — 상수를 앞에 둔 `"com.wtcy.rcalab.DO".equals(action)` 한 줄이면 null-안전과 순서 문제를 동시에 없앤다.

(B)의 근본원인은 **삼켜진 예외로 인한 fall-through**, 즉 fail-open이다. 보안 검사가 예외를 던지면 "검사 불가"인데, 코드는 이걸 "차단"으로 잇지 않고 catch로 조용히 삼킨 뒤 특권 동작을 그대로 실행한다. 검사 결과가 불확실할 때 안전한 기본값은 거부(fail-closed)여야 하는데, 이 코드의 기본값은 허용이다. `Inferred` 폴트(예외 발생)와 근본원인(예외를 허용으로 해석)이 다른 함수에 있다는 게 이 버그의 특징이다.

두 결함 모두 메모리를 건드리지 않는다는 점이 결정적이다. ART는 관리 런타임이라 배열 경계·타입을 런타임에 강제하고, 위반은 손상이 아니라 예외로 귀결된다. 그래서 Java 예외에는 네이티브에서 말하는 "쓰기 프리미티브"가 없다. `Inferred`

## 방어와 회귀 검증

**익스플로잇 가능성 정직 산정.** (A)는 로컬 co-located 앱이 내 exported 컴포넌트를 강제 종료시키는 DoS다. RCE가 아니다 — 손상 프리미티브가 없다. CVSS 3.1로 예시를 매기면 `AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L = 4.0(Medium)`이다(A:L 하나만 있는 로컬 벡터; 재계산 가능). 다만 크래시 나는 프로세스가 앱이 아니라 `system_server`면 이야기가 달라진다 — 그 예외는 시스템 소프트 리부트로 번져 영향이 커진다. `Reported` 즉 같은 NPE라도 **어느 신뢰 경계의 프로세스에서 터지느냐**가 심각도를 가른다.

(B)의 영향은 정해진 숫자가 없다. fail-open이 우회하는 대상이 권한 검사면 권한 상승, 데이터 게이트면 정보 노출로 매겨진다. 크래시가 아니라서 "죽지도 않는데 뭐가 문제냐"로 과소평가되기 쉽지만, 실제 보안 등급은 (A)보다 대개 높다. `Inferred`

**회귀 검증.** logic bug는 크래시 로그가 없으니 회귀 테스트로 못을 박아야 한다. "예외를 유발하는 입력을 넣었을 때 보호 화면이 뜨지 않는다"를 자동으로 확인하는 계측 테스트를 남기면, 패치가 풀리거나 리팩터가 다시 fail-open을 심었을 때 즉시 잡힌다. 반대로 (A)는 "null-action Intent에 크래시하지 않는다"는 테스트 한 줄이면 회귀를 막는다. `Inferred`

- 과장 금지 체크: 크래시를 취약점으로, DoS를 RCE로 부풀리지 않는다. Java 예외의 상한은 (해당 프로세스) 가용성이지 무결성·기밀성이 아니다.
- 무증상 우선 원칙: RCA 리포트에서 "로그캣 깨끗함"은 안전의 근거가 아니라 logic bug를 더 파보라는 신호다.

## 정리

- Java 결함은 두 얼굴 — 시끄러운 uncaught 예외(대개 DoS)와 조용한 logic bug(fail-open, 상승 가능). 심각도는 정반대로 붙는다.
- 스택 트레이스 맨 위 프레임은 폴트 사이트지 근본원인이 아니다. 체인 예외는 맨 아래 `Caused by:`가 원래 원인이다.
- 같은 예외라도 앱 프로세스면 로컬 DoS, `system_server`면 시스템 리부트 — 트리거보다 어느 신뢰 경계에서 터지는지가 등급을 정한다.
- logic bug는 크래시 도구로 안 잡힌다. 차등 테스트로 존재를 증명하고 계측 회귀 테스트로 못 박는다.

**점검 질문** — (1) 스택 트레이스에서 폴트 사이트와 근본원인이 다른 프레임일 수 있는 이유는? (2) 크래시 없는 logic bug의 존재를 무엇으로 증명하는가? (3) 같은 NPE가 앱과 `system_server`에서 심각도가 갈리는 근거는?

**참고** — Android `Intent.getAction()` 레퍼런스(developer.android.com/reference/android/content/Intent) · `java.lang.Throwable`/`getCause` (developer.android.com/reference/java/lang/Throwable) · 앱 보안 가이드(developer.android.com/privacy-and-security/security-tips) · CVSS 3.1 명세(first.org/cvss/v3-1/specification-document)

*다음 글: [Binder caller identity 오류 RCA](/posts/android-rca-p3c09/).*
