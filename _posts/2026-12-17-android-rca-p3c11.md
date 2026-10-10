---
layout: post
title: "integer overflow/underflow RCA"
date: 2026-12-17 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, IntegerOverflow, UBSan, ASan, RootCause]
excerpt: "정수 오버플로의 크래시는 memcpy에서 나지만 근본원인은 상류의 곱셈·절단이다. 함정: 부호 없는 wrap은 UB가 아니라서 ASan은 물론 UBSan 기본값으로도 산술 지점을 짚지 못한다 — 잡히는 건 언제나 다운스트림 접근이다."
---

정수 오버플로 버그를 처음 트리아지하면 거의 항상 같은 착각에 빠진다. ASan이 `heap-buffer-overflow ... in memcpy`를 뱉으니 "memcpy가 취약점"이라고 결론 내리고, 그 자리에 경계 검사를 하나 박는다. 그런데 그 memcpy는 죄가 없다. 죄는 그 위 어딘가, 크기를 계산하다 값을 잃어버린 산술 한 줄에 있다. 정수 오버플로 RCA의 전부는 이 두 지점을 갈라서, 툴이 가리키는 곳(폴트사이트)과 실제로 고쳐야 하는 곳(근본원인)이 다르다는 걸 증명하는 일이다.

이 글은 자작 최소 결함 함수 하나를 NDK로 빌드해 AVD에서 돌리면서, ASan과 UBSan이 **서로 다른 줄**을 가리키는 것을 보고 정수 오버플로/언더플로의 Symptom/Trigger/Fault Site/Root Cause를 분리해 본 기록이다.

> **한 줄 결론**: 정수 오버플로의 근본원인은 크래시가 난 memcpy(폴트사이트)가 아니라 그 위에서 크기를 잘못 만든 산술 한 줄이며, ASan은 폴트사이트를·UBSan(implicit-conversion)은 근본원인을 가리키므로 둘을 겹쳐야 4구분이 완성된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 정수 오버플로·언더플로·절단·부호혼동이 어떻게 크기 계산을 망가뜨려 힙 OOB write로 번지는지를, 자작 예시 하나로 4구분(증상/트리거/폴트사이트/근본원인)에 얹어 분석한다.

선수 지식은 세 가지다. 3부 1장에서 세운 Symptom/Trigger/Fault Site/Root Cause 4구분이 이 글의 뼈대다. 3부 2장의 Security Invariant — 여기서는 "할당에 쓴 크기 ≥ 접근에 쓴 크기"라는 불변식 — 가 깨지는 지점이 곧 근본원인이다. 3부 7장의 crash와 exploitability 구분은 마지막 영향 산정에서 다시 쓴다. 완화(ASLR·CFI 등)의 배경은 Atlas C37을 참고하면 된다.

전체 구조에서 이 장은 "메모리 안전 결함군"의 입구다. 정수 오버플로는 그 자체로는 메모리를 건드리지 않는다 — 잘못된 숫자를 만들 뿐이다. 그 숫자가 하류의 할당·복사·인덱싱으로 흘러가 OOB(12장)나 UAF(13장)로 발현한다. 그래서 정수 버그의 RCA는 언제나 "숫자가 어디서 틀렸나"를 상류로 거슬러 올라가는 작업이다.

## 핵심 개념 — 툴은 결과를 잡고, 원인은 거슬러 올라가야 한다

정수 버그의 네 유형과, 각 유형을 실제로 잡아 주는 도구를 갈라 두는 것이 출발점이다.

| 유형 | 예 | C에서의 지위 | 잡는 도구 |
|--|--|--|--|
| 부호 없는 wrap(곱셈·덧셈) | `n*elem`, `len+HDR`가 2^32로 감김 | **정의된 동작**(모듈로) — UB 아님 | UBSan `unsigned-integer-overflow`(기본 off·오탐 많음) |
| 부호 있는 오버플로 | `int`가 `INT_MAX` 넘음 | **UB** | UBSan `signed-integer-overflow` |
| 절단(narrowing) | `uint16_t n = (size_t)len` | 정의됨(값 손실) | UBSan `implicit-integer-truncation` |
| 부호 혼동 | 음수 `int`를 `size_t`로 | 정의됨(값 변함) | UBSan `implicit-integer-sign-change` |

여기서 제일 자주 틀리는 부분. 부호 없는 오버플로는 C 표준에서 모듈로 2^n으로 **정의된 동작**이라 UB가 아니다. `Source-confirmed` 그래서 ASan은 물론이고 UBSan도 기본 설정으로는 그 곱셈을 잡지 않는다 — 잡으려면 `unsigned-integer-overflow`를 명시적으로 켜야 하고, 해싱·의도적 랩어라운드까지 전부 걸려 오탐이 쏟아진다. `Source-confirmed` 반면 부호 있는 오버플로는 UB라서 `signed-integer-overflow`가 정확히 산술 지점을 짚는다. `Source-confirmed`

절단과 부호 혼동은 UBSan의 `implicit-conversion` 그룹으로 묶여 있고, 이 그룹이 `implicit-integer-truncation`과 `implicit-integer-sign-change`를 포함한다. `Source-confirmed` 이 두 검사는 UB가 아닌 "값이 바뀐 대입"을 잡아 주기 때문에, 크기 계산 버그의 근본원인 줄을 직접 가리키는 데 가장 쓸모가 많다.

ASan의 역할은 하나로 못 박아야 한다. ASan은 **다운스트림 메모리 접근**(읽기/쓰기)을 검사한다. 즉 잘못된 크기로 실제 OOB가 나는 순간을 잡을 뿐, 그 크기를 만든 산술은 보지 않는다. `Source-confirmed` 그래서 정수 오버플로에서 ASan 백트레이스의 최상단은 거의 항상 `memcpy`/루프 write — 폴트사이트다. 근본원인은 그보다 몇 프레임 위, 혹은 아예 다른 파일에 있다.

> **[그림 1]** 같은 실행에서 UBSan `implicit-conversion`이 `vuln.c`의 절단 대입(근본원인)을, ASan이 `memcpy`(폴트사이트)를 각각 다른 파일:줄로 지목하는 두 출력을 한 화면에 나란히 캡처 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 결함 함수**와 **로컬 AVD**(userdebug)로만 진행한다. 제3자 앱·실서비스·실기기는 없다. 목표는 무기화가 아니라 "프리미티브가 존재한다"까지의 관측 — 힙 OOB write가 발생한다는 사실과 그 근본원인의 위치까지다. 빌드는 NDK clang으로 aarch64 정적/동적, AVD는 계측 가능한 `google_apis` userdebug 이미지를 쓴다. 아래 빌드 명령의 `prebuilt/linux-x86_64` 경로는 **Linux/WSL 호스트 기준**이다 — Windows 호스트에선 `windows-x86_64`, macOS에선 `darwin-x86_64`로 바꿔야 그대로 돈다.

## 실습 절차와 관측

### 가설

- **가설 A** — plain 빌드는 크래시 지점이 실제 버그(`copy_chunk`)와 떨어져 있거나 아예 조용히 손상되어, 툼스톤만으로는 근본원인을 못 찾는다. `Inferred`
- **가설 B** — ASan은 `memcpy`(폴트사이트)를, UBSan `implicit-conversion`은 절단 대입(근본원인)을 가리킨다. 즉 한 버그를 두 도구가 서로 다른 줄로 지목한다. `Inferred`

### 절차

대상은 절단(truncation) 최소 예시다. 크기를 `size_t`(64비트)로 받아 놓고 `uint16_t`로 좁혀 할당한 뒤, 원래 크기로 복사한다.

```c
// vuln.c — 자작 결함, 개념 이해용 최소 예시
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// src, len 은 신뢰 경계 밖(파싱된 헤더 길이)에서 온다고 가정한다.
uint8_t *copy_chunk(const uint8_t *src, size_t len) {
    uint16_t n = len;          // (근본원인) 64→16bit 절단: len=0x10001 -> n=1
    uint8_t *buf = malloc(n);  // 절단된 크기로 할당 -> 1바이트
    if (!buf) return NULL;
    memcpy(buf, src, len);     // (폴트사이트) 원래 len 으로 복사 -> 힙 OOB write
    return buf;
}
```

```c
// harness.c — 트리거 입력 주입
#include <stdint.h>
#include <stddef.h>
uint8_t *copy_chunk(const uint8_t *src, size_t len);
int main(void) {
    static uint8_t src[0x10001];              // 65537 바이트
    return copy_chunk(src, sizeof src) ? 0 : 1; // len=0x10001 (트리거)
}
```

1. plain으로 빌드해 툼스톤/logcat의 크래시 위치를 기록한다(가설 A).
2. ASan+UBSan을 함께 켜서 빌드한다. UBSan은 기본이 recover 모드라 절단을 **경고만 하고 진행**하고, 그다음 `memcpy`에서 ASan이 치명적으로 abort한다 — 한 실행에서 두 진단이 다 뜬다.
3. 근본원인 줄(대입)과 폴트사이트 줄(memcpy)의 파일:줄 번호를 대조한다(가설 B).

```bash
NDK=$HOME/Android/Sdk/ndk/26.1.10909125
CC=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android34-clang

# (1) plain — 순수 툼스톤용
$CC -g -O0 vuln.c harness.c -o vuln_plain

# (2) ASan + UBSan(implicit-conversion, signed overflow) 동시
$CC -g -O0 -fno-omit-frame-pointer \
    -fsanitize=address,implicit-conversion,signed-integer-overflow \
    vuln.c harness.c -o vuln_san

# AVD(userdebug)로 푸시 후 실행. ASan 런타임 .so 는 같이 올린다.
adb push vuln_san /data/local/tmp/
# 경로의 <ver>은 설치된 NDK의 clang 버전에 맞게 치환
adb push $NDK/toolchains/llvm/prebuilt/linux-x86_64/lib/clang/<ver>/lib/linux/libclang_rt.asan-aarch64-android.so /data/local/tmp/
adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=. UBSAN_OPTIONS=print_stacktrace=1 ./vuln_san"
```

> **[그림 2]** plain 빌드(`vuln_plain`) 실행 시 나오는 툼스톤 또는 `malloc(): corrupted` 지연 abort — 크래시 지점이 실제 버그 `copy_chunk`와 떨어져 있음을 보여주는 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — UBSan이 근본원인을 먼저 경고하고, 진행 뒤 ASan이 폴트사이트에서 abort한다.

```
vuln.c:8:16: runtime error: implicit conversion from type 'size_t' (aka
'unsigned long') of value 65537 to type 'uint16_t' (aka 'unsigned short')
changed the value to 1

==7431==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...
WRITE of size 65537 at 0x... thread T0
    #0 ... memcpy
    #1 ... copy_chunk vuln.c:11
0x... is located 0 bytes after 1-byte region allocated by thread T0 here:
    #0 ... malloc
    #1 ... copy_chunk vuln.c:9
```

두 줄 번호가 핵심이다. UBSan은 `vuln.c:8`(대입 = 근본원인), ASan의 WRITE 프레임은 `vuln.c:11`(memcpy = 폴트사이트), 할당은 `vuln.c:9`(malloc = 잘못된 크기가 굳어진 지점). 한 버그가 세 줄에 걸쳐 있고, 도구마다 다른 줄을 준다.

`예시 출력(교체)` — plain 빌드는 결정성이 없다. 64KB 초과 write가 힙 메타데이터를 밟으면 엉뚱한 곳에서 지연 abort가 난다.

```
# ./vuln_plain
malloc(): corrupted top size
Aborted
```

이 abort 백트레이스는 `copy_chunk`가 아니라 **다음 malloc**을 가리킨다. 새니타이저 없이는 폴트사이트조차 어긋나는 것이다. ASan이 하는 일은 "가끔 크래시하고 가끔 조용히 손상되는" 하이젠버그를, 폴트사이트에서(=버그와 가까운 지점에서) **결정적으로** 멈추는 진단으로 바꾸는 것뿐이다. `Inferred`

## Root Cause

이 버그를 4구분에 얹으면 이렇게 갈린다.

- **증상(Symptom)** — ASan `heap-buffer-overflow (WRITE)`, 또는 plain 빌드의 비결정적 `malloc(): corrupted`/SIGSEGV.
- **트리거(Trigger)** — `len = 0x10001`. 정확히는 `len`의 상위 16비트가 하나라도 세워진 모든 값, 즉 `len >= 0x10000`(그때 `n = len & 0xFFFF < len`이 되어 할당<복사)(예: `0x10000`은 `n=0`, `0x10001`은 `n=1`).
- **폴트사이트(Fault Site)** — `memcpy(buf, src, len)`. ASan이 지목하는 곳. 여기서 실제 OOB가 난다.
- **근본원인(Root Cause)** — `uint16_t n = len`. `size_t`(64비트)를 16비트로 좁히면서 할당 크기가 접근 크기와 어긋났다. Security Invariant "할당 크기 ≥ 접근 크기"가 이 대입에서 깨진다.

폴트사이트에 경계 검사를 넣는 것(`if (len <= n) memcpy(...)`)은 **증상 패치**다. `n`이 이미 틀렸으므로 그 검사는 항상 통과하거나 항상 막아 버려, 정상 입력까지 깨뜨린다. 근본원인 패치는 절단이 일어나기 전, 크기가 아직 온전한 `size_t`일 때 할당·검증을 끝내는 것이다.

왜 도구가 근본원인을 자동으로 못 짚느냐가 이 장의 진짜 교훈이다. 절단·부호 없는 wrap은 UB가 아니라 **정의된 동작**이다. `Source-confirmed` 그래서 "값이 바뀐 대입"을 별도로 잡는 UBSan `implicit-conversion`을 켜지 않는 한, 컴파일러도 ASan도 그 산술을 오류로 보지 않는다. 정수 버그가 오래 살아남는 이유가 여기 있다 — 언어 규칙상 합법이라, 오직 하류에서 메모리를 밟아야 비로소 드러난다.

**Exploitability 정직 산정.** 이 PoC가 지금 보여준 것은 딱 두 가지다 — 크래시(관측된 DoS)와, 공격자 영향 하의 길이·내용으로 발생하는 힙 OOB write **프리미티브의 존재**. 힙 OOB write는 강한 프리미티브지만, 여기서 RCE로 부풀리면 안 된다. 실제 제어 흐름 탈취까지 가려면 힙 그루밍·완화 우회(CFI/MTE) 같은 별도 조건이 필요하고, 그건 이 글의 범위 밖이다. 정직한 결론: **발현 시 최소 DoS, 프리미티브로서 힙 OOB write까지 확인** — 무기화 없음.

## 방어와 회귀 검증

- **크기는 끝까지 넓게.** 신뢰 경계 밖 길이는 `size_t`로 받아 좁히지 않는다. 할당·검증·복사가 모두 같은 폭의 값을 봐야 한다.
- **오버플로 안전 산술.** 곱셈·덧셈은 `__builtin_mul_overflow`/`__builtin_add_overflow`로 감싸 넘침을 명시적으로 거부한다. `Source-confirmed` 이게 근본원인 패치다 — memcpy에 붙이는 경계 검사가 아니라.
- **Patch Invariant.** 패치 후 모든 입력에 대해 "할당 크기 ≥ 접근 크기"가 성립하는지로 검증한다(3부 16장 예고). 트리거 값(`0x10000`, `0x10001`, `0xFFFF`, `0x1_0000_0000` 경계)을 회귀 시드로 남긴다.
- **CI에 UBSan.** `implicit-conversion`·`signed-integer-overflow`를 CI에서 상시 켠다. 부호 없는 wrap 검사는 오탐 때문에 전역으로 켜기 어렵지만, 크기 계산 함수에 국한해 켜는 절충이 현실적이다.
- **Variant analysis.** 같은 모듈에서 형제 패턴(`(uintNN_t)` 좁힘, `* elem`, `+ HDR`)을 grep으로 훑는다(3부 17장 예고). 한 곳을 고치면 근본원인이 공유되는 형제 호출부도 같이 고쳐야 하고, 그건 호출부마다 검사를 다는 게 아니라 크기 계산을 한 군데로 모으는 리팩터가 더 작은 diff다.

**한계와 아키텍처 차이.** 오버플로 발생 여부 자체가 빌드에 종속된다. `(size_t)count * elem_size`처럼 곱셈 전에 넓히면 64비트에서 `uint32*uint32`는 감기지 않지만, `uint32_t total = count * elem_size`는 32비트 곱셈이라 감긴다. `Source-confirmed` 즉 같은 소스가 32비트 ABI에선 취약하고 64비트에선 아닐 수 있으니, RCA에 반드시 대상 ABI를 못박아야 한다. 커널 측 정수 오버플로는 KASAN이 하류 접근을 잡아 주지만, 원인 산술은 여전히 수동으로 거슬러야 한다. 실전 사례로는 Stagefright 계열 미디어 파서에서 정수 오버플로가 힙 오버플로로 번진 공개 버그군이 있다. `Reported` (구체 CVE·소스 줄 귀속은 원문 재확인 필요.)

## 정리

- 정수 오버플로 RCA의 핵심은 폴트사이트(ASan이 가리키는 memcpy)와 근본원인(크기를 만든 산술)을 갈라, 상류로 거슬러 원인 줄을 특정하는 것이다.
- 부호 없는 wrap·절단은 UB가 아니라 정의된 동작이라 기본 도구로는 안 잡힌다 — UBSan `implicit-conversion`/`signed-integer-overflow`를 명시적으로 켜야 근본원인을 짚는다.
- 근본원인 패치는 크기가 온전할 때 `__builtin_*_overflow`로 검증하는 것이고, memcpy 경계 검사는 증상 패치다.
- 영향은 정직하게: 관측된 것은 DoS와 힙 OOB write 프리미티브의 존재까지 — 무기화는 범위 밖.

**점검 질문** — (1) ASan 백트레이스 최상단의 memcpy가 근본원인이 아닌 이유는? (2) 부호 없는 곱셈 wrap을 UBSan 기본 설정이 못 잡는 이유는 무엇이고, 잡으려면 어떤 대가를 치르나? (3) 같은 소스가 32비트에선 취약하고 64비트에선 아닐 수 있는 이유는?

**참고** — [UndefinedBehaviorSanitizer(clang)](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) · [AddressSanitizer(clang)](https://clang.llvm.org/docs/AddressSanitizer.html) · [NDK sanitizers](https://developer.android.com/ndk/guides/asan) · [SEI CERT C INT30-C(부호 없는 wrap)](https://wiki.sei.cmu.edu/confluence/display/c/INT30-C.+Ensure+that+unsigned+integer+operations+do+not+wrap) · [INT32-C(부호 있는 오버플로)](https://wiki.sei.cmu.edu/confluence/display/c/INT32-C.+Ensure+that+operations+on+signed+integers+do+not+result+in+overflow)

*다음 글: [OOB·buffer size RCA](/posts/android-rca-p3c12/).*
