---
layout: post
title: "Parser용 libFuzzer harness"
date: 2027-01-02 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, libFuzzer, 퍼징, ASan, 파서]
excerpt: "파서 퍼징에서 libFuzzer 하네스는 20줄이면 된다. 하지만 하네스가 실제 호출 경로를 안 닮으면 나오는 크래시는 전부 가짜고, NDEBUG로 빌드하지 않으면 assert가 진짜 메모리 손상을 DoS로 위장한다."
---

미디어 파서는 Android 원격 공격 표면의 고전이다. 2015년 Stagefright는 MMS로 들어온 미디어 파일이 `mediaserver`에서 파싱되는 것만으로 원격 코드 실행에 이르렀고, 그 뒤 AOSP는 미디어 스택 전반에 퍼저를 심었다. `Source-confirmed` 사용자가 직접 열지 않아도 실행되는 파서 — 이미지·오디오·비디오·폰트·컨테이너 포맷 — 이 퍼징이 가장 값어치를 하는 지점이다.

이 글은 공개 소스(AOSP·자작 파서)에 libFuzzer 하네스를 붙여 파서를 커버리지 기반으로 두들기는 워크플로를, 안전 범위 안에서 실습한 기록이다. 목표는 무기화가 아니라 "하네스를 어떻게 써야 진짜 버그가 진짜 형태로 드러나는가"다.

> **한 줄 결론**: libFuzzer 하네스의 핵심은 20줄짜리 진입점이 아니라, 그 진입점이 실제 코드가 호출되는 방식을 그대로 닮게 만드는 것이다. 닮지 않으면 나오는 크래시는 전부 가짜다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 (1) libFuzzer 하네스의 계약(시그니처·결정론·무상태), (2) 자작 파서에 하네스를 붙여 ASan과 함께 빌드·실행하는 절차, (3) 나온 크래시를 "취약점"으로 부풀리지 않고 분류하는 기준을 다룬다. 코퍼스·딕셔너리·커버리지 최적화는 다음 장(corpus·dictionary·coverage)의 몫이라 여기선 최소한만 건드린다.

선수 지식은 세 가지다. 첫째, 이 파트 앞 장에서 세운 AOSP 소스 트리와 Clang/NDK 빌드 환경. 둘째, sanitizer의 존재 이유 — ASan은 메모리 손상을 크래시로 승격시키는 계측기이지 완화기가 아니다(Atlas C37 완화 참고). 셋째, C/C++에서 파서가 왜 위험한가 — 길이 필드를 신뢰하는 코드, 경계 검사 없는 `memcpy`, 부호 처리 실수가 전부 여기 모인다.

전체 구조에서 이 장은 "표면을 찾았다(앞 장의 시스템 서비스·Binder 표면)" 다음의 첫 능동 연구다. 하네스가 있어야 그 다음 장들(코퍼스·크래시 중복 제거·sanitizer 심화)이 성립한다.

## 핵심 개념 — libFuzzer 하네스의 계약

libFuzzer는 별도 프로세스를 띄우지 않는 **in-process, coverage-guided** 퍼저다. 대상 코드와 같은 바이너리 안에서 한 함수를 수만 번 재호출하며, 커버리지 계측(SanitizerCoverage)이 새 경로를 여는 입력을 코퍼스에 남긴다. 그래서 하네스는 몇 가지 계약을 반드시 지켜야 한다. `Source-confirmed`

| 요소 | 규칙 | 근거 |
|--|--|--|
| 진입점 | `int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size)`, `return 0` | `Source-confirmed` |
| 결정론 | 같은 입력 → 같은 실행 경로. 난수·시계·환경 의존 금지 | `Source-confirmed` |
| 무상태 | 한 프로세스에서 반복 호출됨. 전역 오염·누수 누적 금지 | `Source-confirmed` |
| 빠름 | 호출당 밀리초 단위. 파일 I/O·sleep·네트워크 금지 | `Source-confirmed` |
| 1회 초기화 | 전역 셋업은 `LLVMFuzzerInitialize(int*, char***)`에 | `Source-confirmed` |
| 빌드 | `clang -fsanitize=fuzzer,address` (라이브러리 링크 분리는 `fuzzer-no-link`) | `Source-confirmed` |

가장 흔한 오해: "libFuzzer가 알아서 구조를 만들어 준다"는 것이다. 진입점이 받는 건 **그냥 바이트 배열**이다. 헤더·길이·체크섬이 있는 포맷은 랜덤 바이트로는 유효 검사 초입에서 다 튕겨 나가 안쪽 파싱 로직에 도달하지 못한다. 이를 넘기는 두 도구가 있다 — 바이트를 타입 있는 값으로 소비하는 `FuzzedDataProvider.h`(compiler-rt 제공), 그리고 문법을 protobuf로 기술하는 libprotobuf-mutator다. `Source-confirmed` 딕셔너리와 시드 코퍼스로 이 문제를 더 싸게 푸는 법은 다음 장에서 다룬다.

> **[그림 1]** 자작 파서 소스와 `LLVMFuzzerTestOneInput` 하네스를 나란히 열어 두고 `clang -fsanitize=fuzzer,address`로 빌드가 성공한 터미널 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 파서와 로컬 빌드**로만 진행한다. 제3자·프로덕션 앱의 파서를 대상으로 하지 않고, 완성된 익스플로잇도 만들지 않는다. 실습 대상은 내가 의도적으로 버그를 심은 최소 TLV 파서다 — 원리를 이해하기 위한 개념 수준이다. AOSP 인트리 퍼저(`cc_fuzz`)와 이미 패치된 공개 CVE는 "실전에선 이 하네스가 어디에 어떻게 심기는가"의 참고로만 인용한다.

빌드는 리눅스 호스트의 Clang(또는 NDK의 Clang)에서 한다. Android 기기 대상 퍼징은 `cc_fuzz`로 크로스 컴파일해 기기에서 돌리지만, 파서 로직 자체는 아키텍처 무관이라 호스트에서 먼저 잡는 게 훨씬 빠르다. `Inferred`

## 실습 절차와 관측

### 가설

- **가설 A** — 길이 필드를 검사 없이 신뢰하는 파서는 경계를 넘는 읽기/쓰기를 하고, ASan이 이를 `stack-buffer-overflow`로 즉시 잡아 크래시 입력을 파일로 남긴다. `Inferred`
- **가설 B** — 같은 버그라도 코드에 `assert(len <= sizeof out)`가 있으면, assert가 살아 있는 빌드에선 abort(=DoS로 보임)로, `NDEBUG` 빌드에선 assert가 사라져 진짜 메모리 손상으로 드러난다. `Inferred`

### 절차

1. 버그를 심은 최소 파서(`toy_tlv.c`)와 20줄 하네스(`harness.c`)를 만든다.
2. `clang -fsanitize=fuzzer,address`로 함께 컴파일한다.
3. 빈 코퍼스 디렉터리를 주고 실행해 크래시가 날 때까지 둔다.
4. 떨어진 `crash-*` 입력을 하네스에 직접 물려 재현되는지 확인한다.
5. 같은 소스를 `-DNDEBUG` 유무로 두 번 빌드해 관측(가설 B)이 어떻게 갈리는지 대조한다.

```c
/* toy_tlv.c — 최소 TLV 파서: [tag:1][len:1][value:len] 반복 */
#include <stdint.h>
#include <string.h>
#include <assert.h>

int tlv_parse(const uint8_t *buf, size_t n) {
    size_t i = 0;
    uint8_t out[16];
    while (i + 2 <= n) {
        uint8_t len = buf[i + 1];
        if (i + 2 + len > n) break;       /* 소스 읽기는 입력 길이 n 안으로 묶는다 */
        assert(len <= sizeof out);        /* NDEBUG면 사라진다 */
        memcpy(out, &buf[i + 2], len);    /* len을 sizeof(out)와 대조하지 않음 → out[16] 넘어 씀 */
        i += 2 + len;
    }
    return 0;
}
```

```c
/* harness.c — libFuzzer 진입점 */
#include <stdint.h>
#include <stddef.h>
extern int tlv_parse(const uint8_t *buf, size_t n);

int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    tlv_parse(Data, Size);   /* 실제 코드가 호출하는 그대로 */
    return 0;
}
```

```bash
# 빌드 (libFuzzer가 main을 제공한다)
clang -g -O1 -fsanitize=fuzzer,address toy_tlv.c harness.c -o tlv_fuzz
# 실행
mkdir -p corpus && ./tlv_fuzz corpus/ -max_len=64
```

실전(AOSP 인트리)에선 같은 하네스가 `Android.bp`의 `cc_fuzz` 모듈로 들어가고, sanitizer는 빌드 규칙이 자동으로 엮는다. `Source-confirmed`

```
cc_fuzz {
    name: "tlv_fuzzer",
    srcs: ["harness.c", "toy_tlv.c"],
    // 나머지 속성은 Soong 문서에서 재확인
}
```

> **[그림 2]** `./tlv_fuzz` 실행 중 ASan이 `stack-buffer-overflow`를 리포트하고 `crash-<sha1>` 파일을 떨군 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — NDEBUG로 빌드해 assert가 사라진 경우, len이 `out` 크기(16)를 넘는 순간 `out[]` 뒤로 써서 스택 경계를 침범한다:

```
INFO: Running with entropic power schedule (0xFF, 100).
#2   INITED cov: 3 ft: 3 corp: 1/1b
=================================================================
==12345==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x...
WRITE of size 32 at 0x... thread T0
    #0 ... memcpy
    #1 ... tlv_parse toy_tlv.c:13
    #2 ... LLVMFuzzerTestOneInput harness.c:7
SUMMARY: AddressSanitizer: stack-buffer-overflow toy_tlv.c:13 in tlv_parse
==12345==ABORTING
MS: ...; base unit: ...
artifact_prefix='./'; Test unit written to ./crash-<sha1>
```

assert가 **살아 있는** 빌드에선 같은 입력이 `Assertion 'len <= sizeof out' failed`로 abort한다 — 크래시는 나지만 이건 메모리 손상이 아니라 방어적 종료다. 두 출력을 나란히 놓는 게 이 절차의 핵심이다.

## Root Cause — 왜 이렇게 되는가

버그의 뿌리는 파서가 **입력이 주는 길이 필드를 목적지 버퍼 크기와 무관하게 신뢰**한 데 있다. `len`은 최대 255인데 `out[]`은 16바이트고, `memcpy`는 그 차이를 모른다. 신뢰 경계는 "외부에서 온 바이트"와 "내가 잡은 스택 버퍼" 사이에 있는데, 코드가 그 경계에서 검사를 생략했다.

여기서 초보가 세 번 넘어진다.

첫째, **크래시 ≠ 취약점**. libFuzzer가 abort를 잡았다고 다 취약점이 아니다. 내 libsoup 연구에서 Range 헤더 정수 오버플로는 결국 `assert`를 때리는 DoS였고, IrfanView의 DPX 파서 버그는 메모리 손상이 아니라 무한 루프 DoS였다. `Reported` DoS를 RCE로 부풀리는 순간 리포트는 반려당한다. 승격 판단은 ASan이 무엇을 보고했는지(overflow의 방향·READ/WRITE·손상 크기)로 한다.

둘째, **NDEBUG가 결과를 뒤집는다**. 라이브러리를 릴리스 플래그(`-DNDEBUG`)로 빌드하면 `assert`가 통째로 사라진다. 그러면 "assert DoS"로 보이던 게 진짜 OOB write로 드러난다 — 내 tinyobjloader-c 연구에서 `parseLine`의 `f[16]` OOB write가 정확히 이 조건, 즉 NDEBUG에서 ASan으로 확정된 사례였다. `Reported` 배포 형상과 같은 플래그로 빌드하지 않으면, 실제 위험도를 정반대로 읽는다.

셋째, **하네스가 실제 호출을 안 닮으면 발견이 가짜다**. 프로덕션 코드가 그 파서를 절대 도달하지 못하는 상태로 호출하는데 하네스가 곧장 내부 함수를 때리면, 나오는 크래시는 실전에서 재현 불가능하다. 내 wabt 퍼징에서 기능 게이트(플래그로 막힌 미구현 경로) 뒤의 크래시를 걸러낸 트리아지가 이 함정을 정확히 겨눈 것이었다. `Reported` 하네스는 "실제 진입점이 받는 것과 같은 신뢰 수준의 입력"을 같은 순서로 넘겨야 한다.

## 방어와 회귀 검증

- **크래시는 회귀 코퍼스로 승격한다.** 잡은 `crash-*` 입력은 버리지 말고 회귀 셋에 넣어, 패치 뒤 `./tlv_fuzz crash-<sha1>`로 다시 물려 재현이 사라졌는지 확인한다. 이게 "고쳤다"의 유일한 증거다.
- **트리아지 라벨을 붙인다.** ASan 리포트를 (a) OOB write (b) OOB read (c) UAF (d) assert/abort(DoS) (e) 무한 루프/타임아웃(DoS)로 분류한다. (a)(c)가 메모리 손상 후보(쓰기·UAF)로 심각도가 높고, (b)는 정보 노출(info disclosure) 계열로 대체로 그보다 낮으며, (d)(e)는 가용성 문제로 따로 다룬다. 이 라벨 없이 "크래시 N건"만 세는 건 의미가 없다.
- **최소화는 다음 장.** libFuzzer의 `-minimize_crash=1`로 입력을 줄이고 중복을 제거하는 절차는 크래시 중복 제거·최소화 장에서 다룬다. 여기선 "재현되는 원본을 남긴다"까지가 목표다.
- **하네스 자체도 검증한다.** 하네스가 대상을 실제로 커버하는지는 커버리지로 확인한다 — 새 시드를 넣어도 `cov:`가 오르지 않으면 하네스가 로직에 도달하지 못하는 것이다(다음 장).

버그를 심지 않은 정상 파서에 같은 하네스를 붙이면 어떻게 되는지도 한 번 돌려 보라 — 크래시 없이 커버리지만 포화되는 게 정상이다. 이 대조가 하네스가 "버그를 못 찾는 것"과 "버그가 없는 것"을 구분하는 감을 준다.

## 정리

- libFuzzer 하네스의 계약은 `LLVMFuzzerTestOneInput` 시그니처·결정론·무상태·속도다. 어기면 재현 불가능한 잡음이 나온다.
- `-fsanitize=fuzzer,address`로 ASan과 함께 빌드해야 크래시가 메모리 손상의 형태로 드러난다. 배포 형상과 같은 플래그(특히 `NDEBUG`)로 빌드하라 — assert 유무가 위험도 판단을 뒤집는다.
- 크래시는 취약점이 아니다. ASan 리포트로 OOB write/read/UAF/DoS를 분류하고, 하네스가 실제 호출 경로를 닮았는지부터 의심하라.

**점검 질문** — (1) 하네스에서 전역 상태나 파일 I/O가 금지되는 이유는? (2) 같은 파서 버그가 `NDEBUG` 유무로 다르게 관측되는 까닭은? (3) libFuzzer가 잡은 abort를 "취약점 발견"이라 보고하기 전에 확인할 것 세 가지는?

**참고** — [libFuzzer 문서](https://llvm.org/docs/LibFuzzer.html) · [FuzzedDataProvider (compiler-rt)](https://github.com/llvm/llvm-project/blob/main/compiler-rt/include/fuzzer/FuzzedDataProvider.h) · [AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) · [Soong cc_fuzz](https://source.android.com/docs/security/test/fuzzing/libfuzzer) · Atlas C37 완화

*다음 글: [corpus·dictionary·coverage](/posts/android-vulnresearch-p4c08/).*
