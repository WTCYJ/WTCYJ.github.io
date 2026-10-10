---
layout: post
title: "UAF·object lifetime RCA"
date: 2026-12-19 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, UAF, ASan, KASAN, 메모리안전]
excerpt: "UAF의 root cause는 크래시난 주소가 아니다. 크래시 주소는 fault site일 뿐이고, sanitizer가 없으면 즉시 재할당되어 크래시조차 안 나는 '조용한 성공'이 된다 — 안 터진다고 안전한 게 아니다."
---

Use-After-Free는 메모리 안전 결함군에서 가장 흔하고, 동시에 가장 자주 오독되는 클래스다. 크래시가 났으니 그 주소가 원인이라고 적고, 크래시가 안 나니 취약점이 아니라고 닫는다 — 둘 다 틀렸다. UAF는 **객체 수명(object lifetime)** 계약이 깨진 결과이고, 크래시는 그 계약 위반이 우연히 드러난 한 순간일 뿐이다. 이 글은 UAF를 증상/트리거/폴트사이트/근본원인으로 분해하고, ASan(유저스페이스)·KASAN(커널) 리포트를 판독해 lifetime의 어느 지점이 깨졌는지 짚는 방법을 자작 결함 프로그램으로 정리한 기록이다.

안전 범위는 앞 장들과 같다. 자작 결함 프로그램·에뮬레이터(AVD)·Cuttlefish·이미 공개·패치된 사례만 다루고, 프리미티브의 존재를 확인하는 데서 멈춘다. 무기화·힙 그루밍 레시피는 쓰지 않는다.

> **한 줄 결론**: UAF의 root cause는 크래시가 난 곳(fault site)이 아니라 객체를 free한 지점과 그 뒤에 다시 use한 lifetime 설계의 어긋남이다. KASAN/ASan 리포트의 `Allocated by`·`Freed by` 두 스택이 그 양끝을 직접 가리킨다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 scope는 세 가지다. (1) UAF를 RCA 4요소로 분해하는 틀, (2) ASan·KASAN 리포트에서 lifetime의 두 끝(할당·해제)을 읽어 fault site와 root cause를 분리하는 법, (3) 크래시를 DoS/정보노출/RCE 중 무엇으로 정직하게 산정할지의 경계.

선수 지식이 밑에 깔린다. 프로세스와 힙 메모리가 어떻게 재사용되는지(Atlas C04), 그리고 Android 네이티브가 객체 수명을 관리하는 관용구인 강/약 참조 카운팅(`sp<>`/`wp<>`, AOSP `RefBase`)을 알아야 한다. 방법론 쪽으로는 이 파트 1장의 증상/트리거/폴트사이트/근본원인 구분과 7장의 crash vs exploitability 구분을 그대로 쓴다. 여기서는 그 틀을 메모리 안전 결함에 특화한다.

전체 구조에서 이 장은 3부 RCA의 메모리 안전 결함 묶음(11장 integer overflow, 12장 OOB, 13장 UAF, 14장 race/TOCTOU)의 한 축이다. UAF는 특히 다음 장의 race와 붙어 다닌다 — 많은 커널 UAF의 진짜 트리거가 경합이기 때문이다.

## 핵심 개념 — object lifetime과 dangling pointer

객체 수명은 네 단계다. **할당(alloc) → 사용(use) → 해제(free) → (그 뒤 아직 남은 포인터 = dangling) → 다시 사용 = UAF**. UAF는 마지막 화살표 하나로 정의된다. 즉 "해제된 객체를 가리키는 포인터를 역참조"하는 것. 이 정의에서 두 가지가 곧바로 따라온다.

첫째, UAF는 두 지점의 문제다. free한 곳과 use한 곳. 리포트가 스택을 **두 개** 주는 이유가 이것이다. 둘째, 크래시는 필연이 아니다. free된 슬롯이 아직 재할당되지 않았고 sanitizer가 그 슬롯을 감시 중일 때만 터진다. 재할당이 먼저 일어나면 UAF는 조용히 성공한다 — 다른 객체의 메모리를 읽거나 덮어쓰는 silent corruption. `Reported`

RCA 4요소로 분해하면 UAF는 이렇게 배치된다.

| 요소 | UAF에서의 의미 | 어디서 읽나 |
|--|--|--|
| 증상(Symptom) | SIGSEGV, 또는 KASAN/ASan `use-after-free` 리포트 | 툼스톤·dmesg·stderr |
| 트리거(Trigger) | free를 부른 뒤 다시 use하게 만드는 입력·순서(종종 경합) | 재현 입력·호출 시퀀스 |
| 폴트사이트(Fault site) | dangling 포인터를 역참조한 그 명령/코드 라인 | 리포트 맨 위 스택(`#0`) |
| 근본원인(Root cause) | 소유권/refcount 계약이 깨져 조기 free 또는 잔존 포인터가 생긴 지점 | `Freed by`와 `Allocated by` 사이의 설계 |

흔한 착각: 리포트 맨 위 `#0`(폴트사이트)를 root cause로 적는 것. 그건 "누가 죽은 객체를 만졌나"일 뿐이고, root cause는 "누가·왜 이 객체를 너무 일찍 free했나(또는 왜 포인터가 살아남았나)"다. 둘은 다른 스택, 다른 코드에 있다.

> **[그림 1]** 자작 UAF 프로그램의 ASan `heap-use-after-free` 리포트에서 맨 위 접근 스택(`#0`, 폴트사이트)과 아래쪽 `freed by`·`previously allocated by` 두 스택을 각각 박스로 표시한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 자작 결함 프로그램으로만 진행한다. 유저스페이스 UAF는 clang `-fsanitize=address`로 컴파일한 최소 C 프로그램에서 관측한다(호스트/WSL clang이면 그대로 재현되고, Android용은 NDK clang으로 교차 컴파일해 AVD에 push). 커널 UAF는 인트리 진단 모듈 LKDTM으로 안전하게 유발해 KASAN 리포트를 읽는다 — 자작 익스플로잇이 아니라 커널이 스스로 제공하는 결함 유발기다. 어느 쪽도 제3자 앱·실서비스·실데이터를 건드리지 않는다.

## 실습 절차와 관측

### 가설

- **가설 A** — 해제 후 역참조하는 4바이트 read는 ASan에서 `heap-use-after-free`로, `freed by`·`previously allocated by` 두 스택과 함께 잡힌다. `Inferred`
- **가설 B** — sanitizer 없이 같은 프로그램을 `-O0`로 빌드하면 크래시 없이 종료하지만, 반환값은 비결정적(대개 할당자 메타데이터)이며 반드시 예전 값 `0x41`은 아니다. glibc `free()`는 청크 선두에 tcache 메타데이터(safe-linking으로 맹글링된 next 포인터·key)를 즉시 써 넣으므로, 사용자 레벨 재할당 이전에도 `*p`(오프셋 0, 4바이트)는 그 메타데이터를 읽는다. 스테일 데이터나 다른 객체의 값을 실제로 관측하려면 free 직후 같은 크기로 재할당해 슬롯을 채우는 단계가 필요하다(free 자체가 청크 선두를 덮어쓴다). 어느 쪽이든 "안 터짐"이 안전을 뜻하지 않는다. `Inferred`

### 절차

1. 아래 최소 UAF 프로그램을 저장한다(`uaf.c`).
2. ASan으로 빌드해 실행하고 리포트의 세 스택을 기록한다.
3. sanitizer 없이 다시 빌드해 실행, 크래시 여부를 대조한다.
4. (커널) KASAN 커널을 올린 AVD/Cuttlefish에서 LKDTM으로 UAF crashtype을 유발해 dmesg의 KASAN 리포트를 읽는다.

```c
/* uaf.c — 최소 개념 UAF (원리 이해용) */
#include <stdlib.h>
int main(void) {
    int *p = malloc(sizeof(int));  /* alloc: 여기가 lifetime 시작 */
    *p = 0x41;
    free(p);                        /* free: 여기서 lifetime 종료 */
    return *p;                      /* use-after-free: fault site */
}
```

```bash
# 유저스페이스: ASan으로 드러내기 (호스트/WSL clang 기준, 그대로 재현됨)
clang -fsanitize=address -g -O0 uaf.c -o uaf && ./uaf

# 대조: sanitizer 없이 — 크래시는 대개 안 나지만 반환값은 비결정적(free가 청크 선두를 덮어씀), 예전 값 보장 아님
clang -O0 uaf.c -o uaf_plain && ./uaf_plain; echo "exit=$?"

# Android용: NDK clang으로 교차 컴파일 후 AVD에서 실행 (ASan 런타임 동반 필요)
# $NDK/.../clang --target=aarch64-linux-android34 -fsanitize=address -g uaf.c -o uaf
# adb push uaf /data/local/tmp && adb shell /data/local/tmp/uaf

# 커널: KASAN 켠 이미지에서 LKDTM으로 UAF 유발 (crashtype 문자열은 버전별 lkdtm 목록으로 확인)
# adb shell "su 0 sh -c 'echo READ_AFTER_FREE > /sys/kernel/debug/provoke-crash/DIRECT'"
# adb shell dmesg | grep -A40 'KASAN'
```

> **[그림 2]** 같은 `uaf.c`를 ASan 빌드(리포트 출력)와 일반 빌드(`exit=` 정상 종료·비결정적 반환값)로 각각 실행해 나란히 놓은 대조 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
=================================================================
==12345==ERROR: AddressSanitizer: heap-use-after-free on address 0x602000000010
READ of size 4 at 0x602000000010 thread T0
    #0 0x... in main uaf.c:7              <- 폴트사이트(죽은 객체를 read)
0x602000000010 is located 0 bytes inside of 4-byte region ...
freed by thread T0 here:                  <- lifetime의 끝
    #0 0x... in free                       (각 보조 스택은 인터셉터 #0부터 독립 번호)
    #1 0x... in main uaf.c:6
previously allocated by thread T0 here:    <- lifetime의 시작
    #0 0x... in malloc
    #1 0x... in main uaf.c:4
SUMMARY: AddressSanitizer: heap-use-after-free uaf.c:7 in main
```

읽는 순서가 곧 RCA 순서다. `#0`(uaf.c:7)은 폴트사이트, `freed by`(uaf.c:6)와 `previously allocated by`(uaf.c:4)는 lifetime의 양끝. root cause는 이 셋이 아니라 "왜 :6에서 free했는데 :7에서 아직 그 포인터를 살려 뒀나"라는 설계 판단이다. `Source-confirmed`

커널 쪽 KASAN 리포트도 골격이 같다. 맨 위 `BUG: KASAN: use-after-free in <함수>`와 `Read/Write of size N at addr ...`가 증상·폴트사이트, 아래의 `Allocated by task`·`Freed by task` 두 스택이 lifetime 양끝이다. 유저스페이스 ASan과 완전히 대응된다. `Source-confirmed`

한 가지 더: 리포트의 접근 종류가 `READ`인지 `WRITE`인지, 크기가 얼마인지를 그대로 적어라. 이게 뒤에서 프리미티브를 산정할 때의 원자료다.

## Root Cause — 왜 이렇게 되는가

폴트사이트를 지나 진짜 원인으로 가면, UAF의 root cause는 거의 항상 아래 몇 가지 lifetime 계약 위반 중 하나로 수렴한다.

| 유형 | 무엇이 깨지나 | Android에서의 전형 |
|--|--|--|
| refcount 불균형 | incref/decref가 안 맞아 조기 free | `sp<>` 대신 raw 포인터 보관, 또는 decref 한 번 더 |
| 캐시된 raw 포인터 | free 이후에도 멤버·전역이 원시 포인터 잔존 | 콜백 객체가 상대의 raw `this`를 들고 있음 |
| 소유권 혼동 | 누가 free하는지 불명확 → 이중 소유·조기 free | 호출자와 피호출자가 서로 free 책임을 가정 |
| 비동기 콜백 | 객체 파괴 후에도 pending 메시지/콜백이 참조 | `Handler`/`Looper` 큐, Binder death 이후 지연 콜백 |
| 컨테이너 무효화 | `realloc`/`erase`로 내부 포인터·iterator dangling | 벡터 재할당 뒤 옛 원소 포인터 사용 |
| 에러 경로 | cleanup에서 free 후 fallthrough로 계속 사용 | goto err에서 free한 자원을 뒤에서 또 참조 |

Android 네이티브가 `sp<>`/`wp<>`(강/약 참조) 관용구를 두는 이유가 이 목록의 절반을 구조적으로 막기 위해서다. 강 참조는 자기가 사는 동안 객체를 살려 두고, 약 참조는 `promote()`가 실패하면 `null`을 돌려줘 죽은 객체 접근을 컴파일 아닌 런타임에 안전하게 걸러 준다. root cause가 "raw 포인터를 캐시했다"거나 "`wp` 대신 `sp`를 잘못 해제했다"로 자주 잡히는 것도 그래서다. `Reported`

**exploitability는 별도로, 정직하게 산정한다.** UAF 크래시 그 자체는 최소한 DoS(SIGSEGV)다. 그 위는 조건부다. free된 슬롯을 공격자가 제어하는 같은 크기의 할당으로 다시 채운 뒤 dangling 사용이 일어나면, 죽은 객체 자리에 새 데이터가 얹혀 type confusion → 읽기/쓰기 프리미티브 → 잠재적 코드 실행으로 이어질 수 있다. 그러나 이 사슬은 재할당 제어 가능성, 접근이 read인지 write인지, 크기·타이밍이 통제되는지에 전부 종속된다. RCA 보고서는 여기서 멈춘다: "UAF write, size 8, 재할당 창 제어 가능성 미검증 → RCE 잠재, 미확인". 크래시를 곧장 RCE로, DoS를 취약점 등급 상향으로 부풀리지 않는다. `Inferred`

그리고 quarantine의 존재 이유를 오해하지 말 것. KASAN·ASan은 free된 청크를 곧바로 재사용하지 않고 **격리(quarantine)**에 넣어 UAF가 잡히는 창을 인위적으로 넓힌다. 즉 sanitizer가 UAF를 만드는 게 아니라, 프로덕션이라면 조용히 지나갔을 결함을 **드러낼** 뿐이다. "sanitizer 없이는 안 터지니 괜찮다"는 정확히 거꾸로 된 결론이다 — 프로덕션에서 더 위험하다(재현이 비결정적이고 silent corruption이 된다). `Source-confirmed`

## 방어와 회귀 검증

- **재현을 결정화한다.** UAF는 재할당 타이밍에 종속돼 비결정적이다. sanitizer(ASan/KASAN/HWASan)를 켜 quarantine으로 창을 넓히고, 최소 입력으로 축소해(6장) "매번 같은 두 스택이 나오는" 결정적 재현을 먼저 만든다. 이게 없으면 root cause 주장이 흔들린다.
- **회귀 테스트는 lifetime을 겨눈다.** 패치 후 "크래시가 사라졌다"가 아니라 "free 지점과 use 지점 사이의 소유권 계약이 지켜진다"를 검증해야 한다. 원래 트리거를 sanitizer 빌드로 CI에 남겨, 회귀로 되살아나면 두 스택이 다시 뜨게 한다.
- **도구별 사정을 안다.** ASan은 레드존+quarantine으로 유저스페이스를 잡고(느리지만 정확), HWASan은 태그 기반이라 오버헤드가 낮아 Android 시스템 전반 빌드에 쓰이며, KASAN은 커널용이다. MTE(ARMv8.5 메모리 태깅)는 하드웨어 태그로 프로덕션에서도 UAF·OOB를 확률적으로 잡을 수 있어 성격이 다르다 — 단, MTE 관측은 지원 하드웨어/이미지에서만 되고 x86 AVD에선 안 보인다(이 환경 축은 1부에서 정리). `Reported`
- 무기화된 재할당·힙 그루밍 레시피는 방어 문서에 싣지 않는다. 프리미티브의 존재와 등급 산정까지가 이 글의 경계다.

## 정리

- UAF의 root cause는 폴트사이트가 아니라 free 지점과 use 지점 사이에서 깨진 객체 수명 계약이다. 리포트의 두 스택(할당·해제)이 그 양끝을 준다.
- 크래시는 우연이다. quarantine이 없으면 즉시 재할당되어 조용히 성공한다 — "안 터짐 = 안전"은 거꾸로 된 결론.
- UAF 크래시 등급은 DoS가 바닥, 그 위(정보노출·RCE)는 재할당 제어·접근 종류·크기/타이밍에 종속되는 조건부다. 프리미티브 존재까지만 정직하게 적는다.
- `sp<>`/`wp<>` 같은 refcount 관용구는 root cause 유형의 절반을 구조적으로 막으려는 장치다. 위반이 곧 원인 후보다.

**점검 질문** — (1) ASan 리포트에서 root cause를 가리키는 것은 `#0` 스택인가, `freed by`/`previously allocated by` 스택인가, 아니면 그 사이의 설계 판단인가? (2) sanitizer 없이 UAF 프로그램이 크래시 없이 종료했다면 무엇을 뜻하는가? (3) 같은 UAF 크래시를 DoS로 볼지, 그 이상으로 볼지를 가르는 조건 세 가지는?

**참고** — [KASAN(kernel.org)](https://www.kernel.org/doc/html/latest/dev-tools/kasan.html) · [LKDTM provoke-crashes(kernel.org)](https://www.kernel.org/doc/html/latest/fault-injection/provoke-crashes.html) · [AddressSanitizer(clang)](https://clang.llvm.org/docs/AddressSanitizer.html) · [HWAddressSanitizer(clang)](https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html) · [Android memory safety(source.android.com)](https://source.android.com/docs/security/test/memory-safety)

*다음 글: [race·TOCTOU RCA](/posts/android-rca-p3c14/).*
