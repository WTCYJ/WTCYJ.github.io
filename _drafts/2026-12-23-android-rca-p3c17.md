---
layout: post
title: "불완전 패치·variant analysis"
date: 2026-12-23 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 패치분석, variant분석, nday, CodeQL]
excerpt: "패치가 머지되고 원래 PoC가 더는 안 터지면 사람은 '고쳐졌다'고 믿는다. 하지만 완전한 패치는 리포트된 경로가 아니라 폴트에 도달하는 '모든' 경로에서 Patch Invariant가 서야 성립한다. 형제 caller 하나가 가드를 안 거치면, 그 패치는 공격자에게 근본 원인의 지도만 넘겨준 셈이다."
---

패치가 머지되고 원래 재현 PoC가 더는 크래시를 내지 않으면, 사람은 반사적으로 "고쳐졌다"고 결론짓는다. 근본원인분석(RCA)의 마지막 함정이 정확히 여기에 있다. PoC가 안 터지는 것은 **리포트된 그 경로 하나**에서 오염이 막혔다는 사실만 말할 뿐, 같은 근본 원인에 도달하는 형제 경로·복제된 관용구·우회 가능한 가드가 그대로 남았는지에 대해서는 아무것도 말하지 않는다. 공격자는 이 빈틈을 산업적으로 캔다 — 공개된 패치를 diff해 근본 원인을 학습하고, 패치가 손대지 않은 이웃을 찾아 n-day를 0-day로 되판다.

이 글은 3부(RCA)에서 "패치가 완전한가"를 판정하는 절차와, 하나의 알려진 버그로부터 같은 결함의 다른 인스턴스를 체계적으로 뒤지는 **variant analysis**를 형식화한 기록이다. 재현·분석은 전부 자작 결함 앱과 이미 공개·패치된 CVE 위에서만 진행하고, 무기화 없이 "형제 경로가 아직 프리미티브를 준다"는 사실 확인까지만 간다.

> **한 줄 결론**: 패치의 완전성은 원래 PoC가 안 터지는 것이 아니라, 폴트에 도달하는 **모든 경로**에서 Patch Invariant가 서느냐로 판정한다. Variant analysis는 그 '모든 경로'를 형제 caller·복제 관용구·우회 가능한 가드·잘못된 레이어 네 축으로 나눠 뒤지는 일이다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 것은 두 가지다. 첫째, 하나의 패치가 **불완전**하다는 것을 어떻게 정의하고 판정하는가 — 불완전 패치의 네 유형과 각 유형을 잡아내는 검증 질문. 둘째, 알려진 근본 원인 하나를 씨앗으로 삼아 같은 클래스의 형제 버그를 **체계적으로** 찾는 variant analysis의 절차다. 다루지 않는 것은 무기화다. 형제 경로에서 프리미티브가 아직 존재한다는 것까지만 관측하고, 완성 익스플로잇은 만들지 않는다.

선수 지식은 앞 장들에서 쌓인 순서를 그대로 밟는다. 1장의 네 레이어(증상·트리거·폴트 사이트·근본 원인) 구분이 없으면 "패치가 폴트 사이트만 가렸다"는 진단을 내릴 수 없다. 2장의 불변식 작성법은 그대로 Patch Invariant를 언어로 적는 도구가 된다. 3장의 call graph·data-flow는 "폴트 함수의 모든 caller 열거"라는 variant analysis의 뼈대다. 바로 앞 16장에서 patch diff를 읽어 Patch Invariant를 추출하는 법을 다뤘고, 이 장은 그 Invariant가 **일부 경로에서만** 서는 경우를 정면으로 본다. 완화(Atlas C37)의 큰 그림은 형제 경로의 영향 산정에 다시 필요하다.

전체 구조에서 이 장은 3부의 **확장 단계**다. 앞 장들이 하나의 버그를 근본 원인까지 파고들었다면, 여기서는 그 근본 원인을 **코드베이스 전역으로 넓혀** 같은 결함의 이웃을 센다. 그리고 이 확장이 시간축으로 뒤집힌 형태 — 한 번 고친 버그가 나중에 되살아나는 회귀 — 는 다음 18장의 주제다.

## 핵심 개념 — 불완전 패치의 네 유형

패치의 완전성은 **Patch Invariant**로 판정한다(16장). Patch Invariant란 그 패치가 세우려는 불변식이다 — 예컨대 "복사 길이는 목적지 버퍼 크기를 넘지 않는다". 패치가 완전하다는 것은 이 불변식이 폴트에 도달하는 **모든 경로**에서 성립한다는 뜻이고, 불완전하다는 것은 **일부 경로에서만** 선다는 뜻이다. 불완전의 양태는 아래 네 유형으로 갈린다.

| 유형 | 정의 | 검증 질문 |
|--|--|--|
| **Sibling-path** | 같은 근본 원인에 도달하는 다른 호출 경로가 가드를 안 거침 | 폴트 함수의 **모든** caller가 가드 뒤에 있나? |
| **Copy-paste variant** | 같은 결함 관용구가 다른 파일·코덱에 복제됨 | 이 패턴을 코드베이스 전역에서 grep/CodeQL로 훑으면? |
| **Bypassable guard** | 가드 자체를 우회 가능(부호·타입 혼동, TOCTOU) | 가드의 전제가 공격자 통제 값·상태인가? |
| **Wrong-layer** | 폴트 사이트만 가리고 근본 원인은 그대로 | 패치가 오염 시점을 고쳤나, 소비 시점을 가렸나? |

핵심 착각을 콕 집는다. **"PoC가 안 터진다 = 완전한 패치"가 아니다.** PoC는 하나의 트리거이고, 하나의 경로다. 패치가 그 경로에 가드를 박으면 PoC는 당연히 죽는다 — 그러나 네 유형 중 어느 것도 배제되지 않았다. 특히 sibling-path는 원래 PoC로는 **절대** 관측되지 않는다. 그 형제 caller를 때리는 새 트리거를 따로 만들어야만 보인다. `Inferred`

Wrong-layer 유형은 1장에서 이미 예고됐다. 힙 오버플로의 폴트 사이트에 널 체크만 넣은 패치는 폴트 사이트를 가렸을 뿐 오염 시점(오버플로 write)을 그대로 둔다. `Inferred` 원래 PoC의 폴트 주소가 우연히 널 근처였다면 그 널 체크로 PoC는 죽지만, 오버플로 자체는 살아 있어 다른 오프셋에서 다시 터진다. 폴트 사이트에 붙은 패치는 언제나 이 의심을 받아야 한다.

> **[그림 1]** 이미 공개·패치된 CVE의 수정 커밋을 `git show`로 열어, 가드가 추가된 함수 한 곳을 강조하고, 그 함수의 caller 목록을 옆에 나란히 놓아 "패치가 손댄 경로 vs 손대지 않은 형제 경로"를 대조한 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

Variant analysis의 신뢰 경계는 1장과 동일하다 — 신뢰되지 않은 입력이 코드에 닿는 지점. 다른 점은 위협 모델의 **시점**이다. 패치가 공개되는 순간, 공격자의 정보 우위가 뒤집힌다. 패치 이전에는 공격자가 버그를 스스로 찾아야 했지만, 패치 이후에는 diff가 근본 원인의 **정확한 위치와 형태**를 무료로 알려 준다. 그래서 공개된 불완전 패치는 알려지지 않은 버그보다 더 위험할 수 있다 — 지도가 딸려 오기 때문이다. `Inferred`

영향 산정은 여기서도 정직해야 한다. 형제 경로에서 관측되는 것은 "프리미티브의 존재"이지 완성된 공격이 아니다. 같은 오버플로라도 형제 경로가 만드는 write의 **길이·위치·인접 객체**가 다르면 영향 등급이 달라진다. 원래 버그가 RCE로 분류됐다는 사실이 형제 경로도 자동으로 RCE라는 뜻은 아니다 — 형제 경로는 DoS에 그칠 수도, 정보 노출일 수도 있다. 이 장의 규율은 하나: **형제 경로에서 실제로 관측한 프리미티브만큼만 주장한다.** 크래시가 났다는 것만으로 원본 버그의 영향 등급을 그대로 상속시키지 않는다.

## 분석 — 형제 경로와 복제 관용구 떼어 보기

전부 로컬 에뮬레이터(google_apis userdebug)와 자작 결함 앱, 그리고 이미 패치된 공개 CVE의 재현으로만 진행한다. 제3자·실서비스 대상은 없다.

**최소 결함.** 두 메시지 핸들러가 경계 검사 없는 공유 helper를 함께 부른다. 근본 원인은 helper 안의 무검사 `memcpy` 하나다.

```c
// tlv.c — 개념 이해용 최소 결함 (자작)
static char   g_buf[64];

// 공유 choke point: len 바이트를 g_buf로 복사 (경계 검사 없음 = 근본 원인)
static void copy_field(const uint8_t *src, size_t len) {
    memcpy(g_buf, src, len);          // 오염 시점: len이 공격자 통제
}

static int handle_a(const uint8_t *p) {   // type 0x01
    size_t len = p[1];                    // 신뢰 경계: 입력이 길이를 정함
    copy_field(p + 2, len);
    return 0;
}
static int handle_b(const uint8_t *p) {   // type 0x02  (A의 관용구를 복제)
    size_t len = p[1];
    copy_field(p + 2, len);
    return 0;
}
```

**불완전 패치(sibling-path).** 원래 PoC는 `type=0x01`이었다고 하자. 개발자는 그 경로에만 가드를 박는다.

```c
static int handle_a(const uint8_t *p) {
    size_t len = p[1];
    if (len > sizeof(g_buf)) return -1;   // 패치: 여기'만' 가드
    copy_field(p + 2, len);
    return 0;
}
// handle_b 는 손대지 않음 → sibling-path 불완전 패치
```

이 패치의 Patch Invariant는 "`copy_field`로 들어가는 `len`은 `sizeof(g_buf)`를 넘지 않는다"다. 그런데 가드는 `handle_a`에만 있다. `handle_b`는 같은 Invariant를 위반하는 형제 경로로 그대로 남는다. `Inferred`

**관측 — 원래 트리거는 죽고, 형제 트리거는 산다.** 같은 소스를 `-fsanitize=address`로 빌드해 두 타입을 각각 던진다.

`예시 출력(교체)`(google_apis x86_64, ASan 빌드):

```
# type=0x01 (handle_a): 패치 후 거부 — 원래 PoC는 여기서 막힌다
$ ./tlv 01 ff <64+ bytes...>
rejected: len 255 > 64

# type=0x02 (handle_b): 형제 경로는 그대로 터진다
$ ./tlv 02 ff <64+ bytes...>
==4567==ERROR: AddressSanitizer: global-buffer-overflow on address 0x...
WRITE of size 255 at 0x... thread T0
    #0 ... in copy_field tlv.c:6          <- 폴트 사이트(공유 choke point)
    #1 ... in handle_b   tlv.c:17         <- 가드 없는 형제 caller = variant
```

원래 PoC(`0x01`)만 돌렸다면 "패치 확인 완료"라고 적고 넘어갔을 것이다. 형제 트리거(`0x02`)를 따로 만들어 던져야만 sibling-path variant가 드러난다. `Inferred` 여기서 관측된 프리미티브는 "`g_buf`(64B 전역) 뒤로 이어지는 길이-공격자-통제 선형 오버라이트"까지다. 이것이 제어 흐름에 닿는지는 인접 BSS 레이아웃·완화에 달렸고, 그 판정은 7장의 몫이다. 크래시를 곧바로 RCE로 부풀리지 않는다.

**완전한 패치는 choke point에 선다.** 근본 원인은 `copy_field`의 무검사 `memcpy`다. caller마다 가드를 복제하는 대신, 모든 경로가 통과하는 helper 안에 Invariant를 한 번 세우면 형제 경로가 남지 않는다.

```c
static int copy_field(const uint8_t *src, size_t len) {
    if (len > sizeof(g_buf)) return -1;   // 모든 caller가 여기로 흐른다
    memcpy(g_buf, src, len);
    return 0;
}
```

이것이 RCA가 "형제 caller마다 가드를 박는 것보다 공유 함수 한 곳을 고치는 것이 더 작은 diff이자 더 완전한 수정"이라고 말하는 이유다 — caller에 흩뿌린 가드는 하나를 빠뜨리면 곧 sibling-path를 남긴다.

**Copy-paste variant는 grep/CodeQL로 센다.** `handle_b`처럼 관용구가 복제된 경우, 폴트 함수의 caller를 기계적으로 열거하는 것이 variant analysis의 1차 그물이다.

`예시 출력(교체)`:

```
$ grep -rn "copy_field(" .
tlv.c:12:    copy_field(p + 2, len);   // handle_a  (가드 뒤)
tlv.c:17:    copy_field(p + 2, len);   // handle_b  (가드 없음)  <- variant
```

grep은 이름이 같은 복제만 잡는다. 관용구가 이름을 바꿔 흩어졌다면(예: 인라인된 `memcpy(dst, src, p[1])`) 의미 기반 질의가 필요하다. CodeQL/Semgrep으로 "신뢰 경계에서 온 값이 경계 검사 없이 `memcpy` 크기 인자로 흐르는 경로"를 data-flow 질의로 적어 코드베이스 전역에 돌린다. 규칙의 골격은 대략 이렇다.

```yaml
# semgrep 개념 스케치 (교체·검증 필요) — 무검사 memcpy 크기
rules:
  - id: unchecked-memcpy-size-from-input
    patterns:
      - pattern: memcpy($DST, $SRC, $LEN)
      - metavariable-comparison: {...}   # $LEN이 입력 파생·경계검사 부재
    message: "attacker-influenced length reaches memcpy without a bounds check"
```

실제 규칙은 소스(신뢰 경계)와 싱크(`memcpy` 크기)를 어떻게 정의하느냐로 정밀도가 갈린다 — 규칙 문법과 taint 설정은 원문 재확인이 필요하다. 요점은 도구 자체가 아니라 **근본 원인을 질의로 번역해 전역에 돌린다**는 절차다.

> **[그림 2]** 같은 tlv 앱에서 (1) `type=0x01`(패치된 경로, rejected)과 (2) `type=0x02`(형제 경로, ASan global-buffer-overflow)를 나란히 실행한 대조 캡처, 그리고 옆에 `grep`으로 잡은 두 번째 caller 라인 — *실측 스크린샷 자리*

## Root Cause — 왜 패치는 불완전해지는가

원리는 1장의 "폴트 사이트 패치"와 같은 뿌리다. **패치는 근본 원인이 아니라 재현 PoC를 향해 작성되기** 때문이다. 개발자 손에 들어오는 것은 크래시를 내는 하나의 입력·하나의 스택 트레이스다. 그 경로에 가드를 넣으면 PoC가 죽고 티켓이 닫힌다. Patch Invariant는 그 순간 **로컬로만** 강제된다 — 폴트에 도달하는 다른 경로는 리뷰어의 시야 밖이다. 근본 원인은 대개 한 지점이 아니라 서브시스템에 흩어진 누락된 불변식인데, 패치는 점(point) 수정으로 나간다. `Inferred`

여기에 두 가지 구조적 압력이 겹친다. 첫째, 릴리스 케이던스. Android Security Bulletin은 매월 발행되며, 한 번 실린 수정이 불완전해 이후 회차에서 후속 수정이 다시 실리는 일이 있다. `Source-confirmed` 월간 마감은 "리포트된 인스턴스를 막는" 최소 수정을 선호하게 만든다. 둘째, n-day 경제. 공격자는 공개 패치를 diff해 근본 원인을 학습하고 형제 경로를 캔다. Project Zero의 in-the-wild 0-day 추적에 따르면, 탐지된 in-the-wild 0-day의 상당 부분이 이전에 공개·패치된 버그의 variant로 분류돼 왔고, 그 비중은 연도에 따라 대략 4분의 1에서 절반 사이로 편차가 크다(예: 2020년 리뷰 약 25%, 2022년 약 40%). `Reported` 정확한 연도별 수치는 원문 재확인이 필요하다.

리포트된 대표 사례가 2015년 Stagefright다. libstagefright 미디어 파서의 초기 수정이 불완전해, 추가된 검사 자체에 결함이 있어 새로운 CVE로 다시 추적됐다(Exodus Intelligence의 후속 분석). `Reported` 정확한 CVE 귀속과 라인 세부는 원문 재확인이 필요하다. 교훈은 명확하다 — 패치를 짜는 손과 패치를 검증하는 손은 서로 다른 질문을 물어야 한다. 짜는 손은 "이 PoC가 죽는가"를, 검증하는 손은 "폴트에 도달하는 모든 경로에서 Invariant가 서는가"를 묻는다.

## 방어와 회귀 검증

- **Patch Invariant를 먼저 문장으로 적는다(2장).** "복사 길이는 목적지 크기를 넘지 않는다"처럼 한 줄로 못 박아야, 그 뒤에 "이 Invariant가 어느 경로에서 깨지나"를 기계적으로 물을 수 있다. Invariant 없이 diff만 보면 sibling-path를 영영 못 센다.
- **폴트 함수의 caller를 전부 열거한다(3장).** IDA/CodeQL의 caller 조회나 `grep`으로 폴트 함수의 모든 진입을 뽑고, 각각이 가드 뒤에 있는지 하나씩 확인한다. 가능하면 가드를 caller가 아니라 **공유 choke point**에 세워 열거 부담 자체를 없앤다.
- **근본 원인을 질의로 번역해 전역에 돌린다.** grep은 복제된 이름을, CodeQL/Semgrep의 taint 질의는 이름이 바뀐 의미적 복제를 잡는다. 이 variant 스캔을 회귀 게이트로 CI에 건다 — 새 코드가 같은 관용구를 다시 심으면 빌드가 깨지게.
- **형제 경로마다 회귀 테스트를 남긴다.** 원래 트리거뿐 아니라 형제 트리거(`type=0x02`)에 대한 케이스를 ASan 빌드로 CI에 넣는다. 이렇게 남긴 테스트가 없으면, 나중 리팩터가 가드를 다시 걷어내도 아무도 모른다 — 그것이 18장의 회귀다.
- **폴트 사이트 패치를 의심한다.** 가드가 크래시 지점(소비 시점)에 붙었다면 wrong-layer를 먼저 배제한다. 오염 시점(write/free/계산)이 그대로면, 다른 오프셋·다른 트리거로 되살아난다.

## 정리

- 패치의 완전성은 "원래 PoC가 안 터진다"가 아니라, 폴트에 도달하는 **모든 경로**에서 Patch Invariant가 서느냐로 판정한다.
- 불완전 패치는 sibling-path·copy-paste variant·bypassable guard·wrong-layer 네 유형으로 갈리고, 각 유형은 서로 다른 검증 질문으로 잡는다.
- Variant analysis는 근본 원인을 씨앗으로 caller 열거(grep·CodeQL)와 질의화(taint)로 형제 인스턴스를 센다. 완전한 수정은 대개 공유 choke point 한 곳에 Invariant를 세운다.
- 형제 경로에서 관측되는 것은 프리미티브의 존재까지다. 원본 버그의 영향 등급을 형제에 자동 상속시키지 않는다.

**점검 질문** — (1) "PoC가 더는 안 터진다"가 왜 완전한 패치의 증거가 아닌가? (2) sibling-path variant가 원래 PoC로는 절대 관측되지 않는 이유는? (3) caller마다 가드를 박는 패치보다 공유 helper 한 곳을 고치는 패치가 더 완전한 이유는?

**참고** — [Google Project Zero: 0day In-the-Wild 추적](https://googleprojectzero.github.io/0days-in-the-wild/) · [Project Zero 블로그(variant analysis·policy)](https://googleprojectzero.blogspot.com/) · [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [CodeQL 문서](https://codeql.github.com/docs/) · [Semgrep 규칙](https://semgrep.dev/docs/) · [NDK AddressSanitizer](https://developer.android.com/ndk/guides/asan)

*다음 글: [regression으로 되살아난 취약점](/posts/android-rca-p3c18/).*
