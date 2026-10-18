---
layout: post
title: "state machine·causal graph"
date: 2026-12-10 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RootCauseAnalysis, StateMachine, 인과분석]
excerpt: "상태기계 RCA의 가장 흔한 함정은 '크래시난 함수(폴트사이트)'를 근본원인으로 적는 것이다. 폴트사이트는 증상이 드러난 위치일 뿐, 근본원인은 가드 없는 전이를 허용한 설계 결정이다."
---

근본원인분석(RCA)에서 사람들이 가장 자주 미끄러지는 지점은 "어디서 터졌나"를 "왜 터졌나"로 착각하는 것이다. 스택 트레이스가 가리키는 함수를 그대로 근본원인 칸에 적으면, 패치는 그 함수만 막고 형제 경로는 그대로 열려 있게 된다. 이 부(部)의 앞 장들이 증상/트리거/폴트사이트/근본원인을 **분리**하라고 말했다면, 이 장은 그 분리를 **형식화**하는 두 도구 — 상태기계(state machine)와 인과그래프(causal graph) — 를 다룬다.

이 글은 자작 결함 앱을 상태기계로 모델링하고, 관측된 로그를 인과그래프로 되짚어 근본원인을 귀속(attribution)한 기록이다. 무기화는 없다. 프리미티브가 "어떤 불법 전이로 존재하는가"까지만 짚는다.

> **한 줄 결론**: 취약점은 대개 "상태기계의 가드 없는 전이"로 나타나고, 근본원인은 그 전이를 허용한 **설계 결정**이다. 폴트사이트(크래시난 곳)를 근본원인으로 적으면 형제 경로가 살아남는다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 두 가지 분석 렌즈를 다룬다. (1) **상태기계** — 컴포넌트의 상태 집합과 합법 전이를 그려 "일어나면 안 되는 전이"를 찾는다. (2) **인과그래프** — 증상에서 근본원인까지를 방향 있는 "왜"의 사슬로 재구성하고, 각 엣지를 반증 가능한 증거로 못 박는다. 이 둘은 경쟁이 아니라 짝이다. 상태기계가 **어디서** 규칙이 깨졌는지를, 인과그래프가 **왜** 깨졌는지를 준다.

선수 개념은 세 가지다. 이 부 1장의 증상/트리거/폴트사이트/근본원인 4분법(Atlas 기준 RCA 어휘), 2장의 Security Invariant — "결코 참이어선 안 되는 상태"를 명제로 적는 법, 그리고 3장의 call graph·data-flow — 상태를 바꾸는 코드 경로를 따라가는 법. 이 장은 그 흐름 분석 위에 "상태"라는 축을 하나 더 세운다. 전체 구조에서 이 장은 RCA 방법론의 **모델링 단계**에 놓인다. 재현(6장)과 crash/exploitability 구분(7장)은 여기서 세운 모델을 검증·산정하는 뒷 단계다.

## 핵심 개념 — 상태기계와 인과그래프, 두 개의 RCA 렌즈

**상태기계.** 어떤 컴포넌트든 유한한 상태와 그 사이의 전이로 그릴 수 있다. 보안에서 중요한 건 "합법 전이 집합"이다. 예컨대 인증 컴포넌트의 불변식은 이렇게 적힌다 — *AUTHORIZED는 AUTHENTICATING을 거쳐 유효 자격증명으로만 도달할 수 있다.* 취약점은 이 불변식을 깨는 전이, 즉 **가드 없는 전이**나 **도달 불가능해야 할 상태로의 점프**로 나타난다.

이건 은유가 아니다. AOSP 프레임워크는 Wi-Fi·텔레포니·커넥티비티의 상태 관리를 위해 명시적 계층형 상태기계 유틸(`com.android.internal.util.StateMachine`)을 실제로 쓴다(정확한 클래스 경로와 리네이밍 이력은 AOSP 태그별 확인 필요). 즉 프레임워크 컴포넌트의 상당수는 코드 자체가 이미 상태기계라, 결함도 상태 전이 언어로 읽는 게 자연스럽다. `Reported`

메모리 버그도 예외가 아니다. 객체 수명은 `allocated → in-use → freed → (reused)` 상태기계이고, UAF는 `freed` 상태에서 `use` 전이를, double-free는 `freed`에서 다시 `free` 전이를 발생시킨 것이다. 상태기계는 논리 버그와 메모리 버그를 같은 문법으로 묶는다. `Inferred`

**인과그래프.** 4분법을 노드로, "왜"를 방향 엣지로 놓은 방향 그래프다. 핵심 규율 두 가지 — 첫째, **상관은 인과가 아니다.** "X 직전에 Y가 있었다"는 엣지가 아니다. 대조군(negative control)으로 Y를 빼도 X가 나면 그 엣지는 가짜다. 둘째, **분기는 배제 대상이다.** 한 증상에 후보 원인이 둘이면 둘 다 그리고, 실험으로 하나를 지운다.

| 4분법 노드 | 정의 | 흔한 오귀속 |
|--|--|--|
| 증상(Symptom) | 관측된 나쁜 결과 | "크래시" 자체를 원인으로 적음 |
| 트리거(Trigger) | 증상을 유발한 입력·이벤트 | 트리거를 근본원인으로 착각 |
| 폴트사이트(Fault Site) | 결함이 **드러난** 코드 위치 | 스택 top을 근본원인으로 적음 |
| 근본원인(Root Cause) | 그 전이를 애초에 허용한 결정 | 여기서 멈추지 않고 더 파거나, 못 미치고 멈춤 |

근본원인은 "위 원인이 이 코드베이스 밖(설계·스펙·계약)으로 넘어가는 마지막 왜"에서 멈춘다. 더 파면 철학이 되고, 덜 파면 증상을 고친다. `Inferred`

> **[그림 1]** 자작 결함 앱의 상태 전이도 — IDLE/AUTHENTICATING/AUTHORIZED/ACTIVE 네 상태와, 정상 전이(실선)·공격자가 유발한 불법 전이(점선 IDLE→AUTHORIZED)를 한 화면에 대조 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

자작 앱의 신뢰 경계는 **exported 컴포넌트**다. 인증 상태를 관리하는 서비스가 있고, 외부에서 인텐트를 받는 `exported=true` 리시버가 상태 전이를 트리거한다. 위협 모델은 "같은 기기의 저권한 다른 앱이 임의 인텐트를 보낼 수 있다"는 것 — Android IPC의 기본 가정이다. 공격자가 넘는 경계는 프로세스 경계가 아니라 **상태 경계**다. 목표는 AUTHENTICATING을 건너뛰고 AUTHORIZED로 점프하는 것.

전부 로컬 에뮬레이터(AVD)와 자작 앱으로만 진행한다. 제3자·실서비스 앱은 없고, 프리미티브의 존재("가드 없는 전이가 실재한다")까지만 확인한다. 실데이터·지속성·전파는 다루지 않는다.

## 분석 — 상태기계로 결함을 짚고 인과그래프로 귀속하기

결함의 핵심은 전이 핸들러가 **현재 상태를 확인하지 않는다**는 데 있다. 최소 개념 수준으로 옮기면:

```java
// 자작 결함 앱 — 개념 축약. state는 전역/싱글턴 상태.
// exported=true 리시버가 아래 onReceive로 임의 인텐트를 받는다.
enum State { IDLE, AUTHENTICATING, AUTHORIZED, ACTIVE }

void onReceive(Context c, Intent i) {
    switch (i.getStringExtra("cmd")) {
        case "authenticate":
            state = State.AUTHENTICATING;          // IDLE -> AUTHENTICATING
            break;
        case "grant":
            // 결함: 현재 상태(가드)를 확인하지 않는다.
            // 불변식은 "AUTHENTICATING에서 유효 자격증명일 때만"인데
            // 어떤 상태에서든 grant가 먹는다.
            state = State.AUTHORIZED;              // *any* -> AUTHORIZED (불법)
            break;
        case "run":
            if (state == State.AUTHORIZED) { doPrivilegedThing(); state = State.ACTIVE; }  // AUTHORIZED -> ACTIVE
            break;
    }
}
```

정상 시나리오는 `authenticate → (자격증명 검증) → grant → run`이다. 그런데 리시버는 `grant`를 받으면 현재 상태를 보지 않고 무조건 AUTHORIZED로 놓는다. 그래서 공격 인텐트 순서 `grant → run` 하나로 IDLE에서 곧장 AUTHORIZED로 점프한다.

관측은 상태 로그로 한다. 앱이 전이마다 `Log.i("SM", "state=" + state)`를 남기면, `logcat`에서 전이 순서가 그대로 보인다.

```bash
# 자작 앱의 상태 로그만 필터
adb logcat -s SM:I
# 다른 창에서 공격 인텐트를 순서대로 주입(자작 앱 대상, 로컬 AVD)
# API 26+는 매니페스트 선언 리시버로의 '암시적' 브로드캐스트를 막으므로(sender가 am이어도 우회 안 됨)
# -n으로 대상 컴포넌트를 명시해 '명시적' 브로드캐스트로 보낸다(컴포넌트명은 자작 앱 기준 예시).
adb shell am broadcast -n com.example.lab/.CmdReceiver -a com.example.lab.CMD --es cmd grant
adb shell am broadcast -n com.example.lab/.CmdReceiver -a com.example.lab.CMD --es cmd run
```

`예시 출력(교체)` — 실제 실행 로그로 바꿀 것:

```
I SM: state=IDLE
I SM: state=AUTHORIZED        <- authenticate 없이 점프(불법 전이)
I SM: doPrivilegedThing() invoked   <- 증상
```

이 로그를 인과그래프로 되짚으면 사슬이 이렇게 선다.

```
[증상] 권한 동작 실행(doPrivilegedThing)
   ^  왜? run 시점 state==AUTHORIZED 였다
[트리거] grant→run 인텐트 순서 주입 (외부 앱)
   ^  왜? grant 핸들러가 AUTHORIZED로 놓았다
[폴트사이트] onReceive의 "grant" case (여기서 규칙이 깨져 보인다)
   ^  왜? 그 case가 현재 상태(가드)를 확인하지 않는다
[근본원인] 설계: 상태 전이에 가드가 없다
           = "AUTHENTICATING+유효 자격증명일 때만 AUTHORIZED" 불변식이
             코드로 강제되지 않음
```

> **[그림 2]** `adb logcat -s SM:I` 출력에서 IDLE 다음에 곧바로 AUTHORIZED가 찍힌 구간을 캡처하고, 그 옆에 증상→트리거→폴트사이트→근본원인 인과그래프를 겹쳐 놓은 화면 — *실측 스크린샷 자리*

여기서 **negative control**이 인과 엣지를 확정한다. `authenticate`를 먼저 보내고 자격증명 검증을 통과시킨 정상 순서에서는 같은 `run`이 권한 동작을 정당하게 실행한다 — 즉 "권한 동작 실행"이라는 증상은 grant의 가드 부재가 있을 때만 **부당하게** 난다. 트리거를 정상 순서로 바꿔도 부당 실행이 사라지면, `가드 부재 → 부당 실행` 엣지가 확정된다.

## Root Cause — 왜 이렇게 되는가

폴트사이트는 `onReceive`의 `grant` case다. 하지만 그건 규칙이 **드러난** 곳이지 근본원인이 아니다. 그 case에 `if (state == AUTHENTICATING && validCred)` 가드를 넣어 이 한 줄만 막으면, 오늘의 PoC는 죽지만 같은 결함 클래스는 살아 있다 — 예컨대 다른 전이 핸들러(`activate`, `resume` 등)가 똑같이 상태를 안 볼 수 있다. 근본원인은 **"상태 전이가 현재 상태를 전제하지 않고 목표 상태를 직접 대입한다"는 설계**다. `Inferred`

이걸 상태기계 언어로 정확히 적으면 — 이 기계는 사실상 "완전 그래프"다. 모든 상태에서 모든 상태로 갈 수 있다. 합법 전이 집합이 코드에 인코딩돼 있지 않기 때문이다. 안전한 상태기계는 전이 함수가 `f(현재상태, 이벤트, 가드) → 다음상태`로 정의되고, 정의되지 않은 (상태,이벤트) 쌍은 **거부**(무시하거나 예외)한다. 결함 앱은 이벤트만 보고 상태를 무시하므로, 공격자가 이벤트 순서를 임의로 짜서 원하는 상태로 몰 수 있다.

메모리 버그도 같은 구조다. UAF의 근본원인은 "use가 일어난 함수"(폴트사이트)가 아니라 "해당 객체가 `freed` 상태인데 그 상태를 use 경로가 전제하지 않는다"는 수명 설계다. 상태기계 렌즈는 논리·메모리 버그를 동일한 "가드 없는 전이" 문장으로 환원한다. `Inferred`

## 방어와 회귀 검증

- **불변식을 코드로 강제한다.** 전이 함수를 한 곳으로 모으고(3장의 call graph에서 상태를 바꾸는 모든 진입점을 찾아), 정의되지 않은 (상태,이벤트) 쌍을 명시적으로 거부한다. 개별 case마다 가드를 흩뿌리는 건 형제 경로를 놓친다 — 근본원인 수정은 전이 테이블 **한 곳**이다.
- **불변식을 회귀 테스트로 고정한다.** 2장에서 적은 Security Invariant("AUTHENTICATING 없이 AUTHORIZED 도달 금지")를 그대로 테스트로 만든다. `grant→run` 순서에서 권한 동작이 실행되면 실패하는 단언 하나면, 같은 불법 전이가 재발할 때 CI가 잡는다.
- **상태 로그를 관측 계측으로 남긴다.** 전이마다 상태를 로그로 찍는 습관은 인과그래프 재구성을 로그 읽기로 바꾼다. 배포 빌드에선 낮은 우선순위·민감정보 제외.
- **negative control을 재현 절차에 포함한다.** "정상 순서에선 증상이 없고, 공격 순서에서만 난다"를 매번 함께 보여야 인과 엣지가 유지된다. 한쪽만 보이면 상관에 불과하다.

## 정리

- 상태기계는 **어디서** 규칙이 깨졌는지(불법 전이)를, 인과그래프는 **왜** 깨졌는지(가드 부재라는 설계)를 준다. 둘은 짝이다.
- 폴트사이트 ≠ 근본원인. 스택 top이나 크래시난 case를 근본원인 칸에 적으면 형제 경로가 살아남는다. 근본원인은 "그 전이를 허용한 결정"까지 내려간다.
- negative control(정상 순서)로 인과 엣지를 확정하라. 상관을 인과로 승격시키지 않는 유일한 방법이다.
- 근본원인 수정은 전이 테이블 한 곳, 회귀 테스트는 Security Invariant 한 줄이다.

**점검 질문** — (1) 폴트사이트와 근본원인을 가르는 기준은 무엇인가? (2) `grant` case에 가드 한 줄만 넣는 수정이 왜 불완전한가? (3) UAF를 상태기계로 그리면 어떤 전이가 결함인가?

**참고** — AOSP `com.android.internal.util.StateMachine`(frameworks/base, 계층형 상태기계 유틸; 클래스 경로·리네이밍은 대상 태그에서 확인) · Android 앱 컴포넌트/인텐트 문서([Intents and Intent Filters](https://developer.android.com/guide/components/intents-filters)) · 이 부 1·2·3장(증상/트리거/폴트사이트/근본원인, Security Invariant, call graph·data-flow)

*다음 글: [baseline·patched·negative control](/posts/android-rca-p3c05/).*
