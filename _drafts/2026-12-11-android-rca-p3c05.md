---
layout: post
title: "baseline·patched·negative control — 재현을 인과로 바꾸는 세 대조"
date: 2026-12-11 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RCA, 근본원인분석, 대조실험, ASan]
excerpt: "재현했다는 것과 근본원인을 안다는 것은 다르다. baseline에서 크래시를 재현해도 그건 상관일 뿐, negative control(입력 특이성)과 patched control(수정 국소화)이 붙어야 인과가 된다. 흔한 함정은 negative control을 트리거와 너무 다르게 잡아 변수를 하나로 못 좁히는 것이다."
---

크래시를 하나 재현했다고 치자. 입력을 넣었고, 앱이 죽었고, 툼스톤이 남았다. 여기서 대부분이 곧장 "원인은 X다"로 넘어간다. 그런데 방금 한 건 원인 규명이 아니라 **상관 하나를 관측한 것**이다 — 그 입력이 들어갔을 때 크래시가 같이 일어났다, 그뿐이다. 그 입력의 어느 특징이 문제였는지, 애초에 그 앱이 아무 입력에나 잘 죽는 건 아닌지, 내가 지목한 코드가 진짜 고장난 자리인지는 아직 하나도 증명되지 않았다.

이 간극을 메우는 게 대조(control)다. 근본원인분석(RCA)은 결국 통제된 실험이고, 통제된 실험에는 대조군이 필요하다. 이 글은 RCA에서 쓰는 세 가지 대조 — baseline(양성 대조), patched(수정 대조), negative control(입력 대조) — 를 자작 결함 앱과 AddressSanitizer로 세워 보고, 재현을 인과로 바꾸는 최소 조건을 정리한 기록이다.

> **한 줄 결론**: baseline 단독 재현은 상관일 뿐이다. 트리거 조건만 뺀 **negative control**(입력을 한 변수만 바꿈)과 동일 입력을 넣은 **patched control**(코드를 한 변수만 바꿈), 이 둘의 교집합이 있어야 "입력 F가 자리 S의 원인 R을 통해 결함을 일으킨다"는 인과 주장이 선다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 하나의 결함을 두고 **세 개의 빌드/입력 조합**을 세워 관측하는 방법을 다룬다. 범위는 자작 결함 앱과 이미 패치된 공개 CVE로 한정하고, 대조군을 어떻게 설계해야 인과 주장이 성립하는지, 어떤 교란(confounder)이 그 주장을 무너뜨리는지에 집중한다. 무기화나 완성 익스플로잇은 다루지 않는다 — 대조가 확정하는 건 결함 프리미티브의 존재까지다.

선수 지식은 세 가지다. 이 파트 1장의 증상/트리거/폴트사이트/근본원인 구분 — baseline이 재현하는 게 "증상"인지 "근본원인"인지 구분할 줄 알아야 한다. 2부 실습에서 다룬 ASan·KASAN 판독 — 대조의 결과를 읽으려면 새니타이저 리포트를 읽을 수 있어야 한다. 그리고 Atlas의 빌드 타입·ABI 개념 — baseline과 patched가 "패치 한 줄"만 다르고 나머지가 같아야 한다는 조건이 여기서 온다.

전체 구조에서 이 장은 RCA 방법론의 **척추**다. 앞 장들(증상 분리, security invariant, call graph, state machine)이 "무엇을 의심할지"를 세웠다면, 이 장은 그 의심을 **증명 가능한 형태**로 바꾼다. 다음 장(최소 재현·입력 축소)은 여기서 세운 트리거를 더 작게 깎는 작업이다.

## 핵심 개념 — 세 대조가 각각 증명하는 것

세 대조는 이름은 비슷해도 증명하는 대상이 전부 다르다. 하나라도 빠지면 인과 사슬에 구멍이 남는다.

| 대조 | 무엇을 바꾸나 | 무엇을 증명하나 | 빠지면 |
|--|--|--|--|
| **baseline** (양성 대조) | 미수정 빌드 + 트리거 입력 | 결함이 실재하고 재현된다 | 애초에 논의 불가 |
| **negative control** (입력 대조) | 트리거 조건만 제거한 근접 입력 | 그 **입력 특징**이 원인이다(특이성) | "이 앱은 그냥 잘 죽음"을 못 배제 |
| **patched control** (수정 대조) | 동일 입력 + 수정된 빌드 | 그 **코드 자리**가 원인이다(국소화) | 패치가 딴 걸 고쳤을 가능성 잔존 |

인과의 반사실(counterfactual) 정의로 보면 깔끔하다. "R이 원인이다"는 곧 "R을 빼면 그 일이 안 일어난다"는 것이다. negative control은 입력에서 트리거 특징 F를 빼고(F가 원인임을 봄), patched control은 코드에서 결함 R을 빼서(R이 원인임을 봄) 각각 반사실을 만든다. 두 반사실이 모두 "안 터진다"로 나올 때에만 인과가 닫힌다. `Inferred`

여기서 제일 흔한 함정 — **negative control을 트리거와 너무 다르게 잡는 것.** 트리거가 "길이 32짜리 입력"이고 negative control이 "완전히 다른 포맷의 짧은 입력"이면, 안 터지는 게 길이 때문인지 포맷 때문인지 분리되지 않는다. 통제 실험의 제1원칙은 **한 번에 한 변수**다. negative control은 트리거에서 딱 트리거 조건 하나만 뺀, 나머지가 최대한 같은 입력이어야 한다. 이 글의 예시가 쓰는 길이 8은 "길이가 원인이다"라는 특이성을 세우는 데는 충분하지만, 경계에서 딱 한 칸 떨어진 근접 입력(안전 최대인 16, 혹은 첫 초과인 17)은 아니다. 최소 차이의 이상(理想)과 variant analysis가 만나는 지점이 바로 그 경계(16/17)이고, 여기서는 길이 특이성만 세우고 경계는 뒤(17장)로 미룬다. `Inferred`

또 하나 — baseline과 patched는 **패치 외 모든 것이 같아야** 한다. 컴파일러 버전, 최적화 플래그, 새니타이저 유무, 실행 환경(같은 AVD·같은 시드)까지. 패치하면서 컴파일러도 올리면, 차이가 패치 때문인지 툴체인 때문인지 교란된다. `Inferred`

> **[그림 1]** `diff -u`로 baseline과 patched 소스의 단일 줄 차이(길이 가드 추가)를 보인 터미널 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 결함 코드 + 로컬 실행 + AddressSanitizer**로만 진행한다. 제3자·실서비스 앱은 없다. 결함은 교과서적인 힙 경계 넘침 하나로 고정하고, baseline과 patched는 소스 한 줄(길이 가드)만 다르게 둔다. ASan을 쓰는 이유는 결정성(determinism) 때문이다 — ASan은 잘못된 접근을 첫 접근에서 잡아, ASLR·힙 레이아웃 난수에 덜 흔들린다. 대조 실험에는 흔들림이 적은 검출기가 유리하다. `Source-confirmed`

같은 방법론은 이미 패치된 공개 CVE에도 그대로 적용된다: 수정 커밋 **이전 태그**로 baseline, **이후 태그**로 patched를 빌드하면 된다(Cuttlefish/AVD). 다만 특정 CVE 번호·태그 귀속은 원문 재확인이 필요하므로, 이 글의 실행 예시는 자작 앱으로만 든다.

## 실습 절차와 관측

### 가설
- **가설 A** — baseline에 트리거(길이 32)를 넣으면 ASan이 heap-buffer-overflow WRITE를 보고하고, 같은 baseline에 negative control(길이 8)을 넣으면 clean이다. → 길이 > 16이 원인임(특이성).
- **가설 B** — patched에 **동일** 트리거(길이 32)를 넣으면 clean이다. → 가드가 있는 그 자리가 원인임(국소화). patched에서도 터지면 가설이 틀린 것이다. `Inferred`

### 절차
1. 소스를 두 벌 만든다. `parse.c`는 `malloc(16)` 뒤 길이 검증 없이 `memcpy` — baseline. `parse_patch.c`는 앞에 `if (n > 16) { free(buf); return; }` 한 줄만 추가 — patched.
2. **같은 플래그**로 각각 ASan 빌드한다(패치 외 변수 고정).
3. 2×2 조합 중 정보를 주는 세 칸을 실행한다: baseline+32, baseline+8, patched+32. (네 번째 patched+8은 정상 동작 확인용 sanity 칸.)
4. 각 실행의 ASan 리포트 유무·폴트 사이트를 기록한다.

```c
// parse.c (baseline). parse_patch.c는 표시된 한 줄만 추가.
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static void parse(const uint8_t *in, size_t n) {
    char *buf = malloc(16);
    // patched 에만: if (n > 16) { free(buf); return; }
    memcpy(buf, in, n);          // baseline: 길이 미검증 (결함 자리)
    free(buf);
}
int main(int argc, char **argv) {
    size_t n = argc > 1 ? strtoul(argv[1], 0, 10) : 32;
    uint8_t x[256] = {0};
    parse(x, n);
    return 0;
}
```

```bash
# 패치 외 모든 플래그 동일 — 이게 교란 통제의 핵심이다
clang -fsanitize=address -O1 -g -o parse_base  parse.c
clang -fsanitize=address -O1 -g -o parse_patch parse_patch.c

./parse_base  32   # baseline + 트리거      → 재현 기대
./parse_base  8    # baseline + negative     → clean 기대 (특이성)
./parse_patch 32   # patched  + 동일 트리거  → clean 기대 (국소화)
```

> **[그림 2]** 동일 ASan 빌드에서 baseline+트리거(overflow 보고)·baseline+음성대조(clean)·patched+트리거(clean) 세 대조를 연속 실행한 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
$ ./parse_base 32
==11821==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...
WRITE of size 32 at 0x... thread T0
    #0 ... __asan_memcpy
    #1 ... parse parse.c:8
0x... is located 0 bytes to the right of 16-byte region
allocated by thread T0 here:
    #0 ... malloc
    #1 ... parse parse.c:6

$ ./parse_base 8
$ ./parse_patch 32
```

세 칸이 (보고 / clean / clean)으로 나오면 인과가 닫힌다. 표로 정리하면 이렇다.

| 빌드 \ 입력 | 트리거(32) | negative(8) |
|--|--|--|
| **baseline** | overflow 보고 (재현) | clean (특이성) |
| **patched** | clean (국소화) | clean (sanity) |

이 표의 대각선이 아니라 **세 모서리**가 결론이다. baseline+32는 "있다", baseline+8은 "길이 때문이다", patched+32는 "그 가드 자리 때문이다". 셋이 다 맞아야 "길이 > 16 입력이 `parse`의 미검증 `memcpy`에서 힙을 넘어 쓴다"가 증명된다. `Inferred`

## Root Cause — 왜 이렇게 되는가

왜 재현 하나로는 부족한가. 단일 재현은 두 변수(입력, 코드)를 동시에 고정한 채 결과 하나만 본 것이다. 관측점이 하나뿐이면 어떤 변수가 결과를 움직였는지 알 수 없다 — 이건 논리의 문제이지 노력의 문제가 아니다. 백 번 재현해도 baseline+트리거 한 칸만 채우면 여전히 관측점은 하나다.

대조는 **한 번에 한 변수를 움직여** 추가 관측점을 만든다. negative control은 코드를 고정한 채 입력을 움직이고, patched control은 입력을 고정한 채 코드를 움직인다. 이렇게 축을 나눠 각각의 반사실을 확보하면, "F를 빼도 코드는 그대로인데 안 터진다"(입력이 원인) + "코드를 빼도 입력은 그대로인데 안 터진다"(그 자리가 원인)가 겹쳐 원인이 특정된다. `Inferred`

patched에서 **여전히 터지는** 경우가 RCA에서 가장 값진 신호다. 이건 실패가 아니라 정보다 — 내가 지목한 자리가 진짜 원인이 아니거나(폴트 사이트 오인), 원인이 여럿이거나, 패치가 트리거 경로를 안 건드렸다는 뜻이다. 대조 없이 "고쳤겠지"로 넘어가면 이 신호를 통째로 놓친다. `Inferred`

한 가지 정직하게 — 이 대조가 확정한 건 **heap-buffer-overflow WRITE 프리미티브가 존재한다**는 것까지다. 이게 DoS인지 정보노출인지 RCE인지, 실제로 제어 데이터를 덮을 수 있는지는 전혀 다른 판정이고 7장(crash와 exploitability 구분)의 몫이다. 크래시를 취약점으로, 오버플로 검출을 익스플로잇으로 부풀리지 않는 게 이 단계의 규율이다.

## 방어와 회귀 검증

세 대조는 버리는 게 아니라 **회귀 테스트로 그대로 승격**된다.

- **patched control → 양성 회귀 테스트.** 트리거 입력을 "patched 빌드에서 ASan clean이어야 한다"는 단언으로 고정한다. 나중에 누가 그 가드를 지우면 CI가 빨간불을 켠다. 재발한 취약점(18장)의 상당수가 이 테스트가 없어서 생긴다.
- **negative control → 과잉 패치 탐지기.** 겁먹고 트리거 경로 자체를 없애는 식으로 "고치면"(예: 함수를 통째로 early-return), 결함은 사라져도 정상 기능이 깨진다. negative control(정상 입력)이 여전히 **정상 동작**하는지 확인하는 칸이 이걸 잡는다. clean만 보지 말고 "제 일을 하는가"를 봐야 한다.
- **교란 통제 체크리스트.** ① 컴파일러·플래그·새니타이저는 baseline/patched 동일. ② 같은 AVD·같은 스냅샷·같은 시드로 실행. ③ ASan/KASAN처럼 레이아웃 난수에 둔감한 검출기 사용. ④ 비결정 크래시라면 N회 반복해 발생률을 기록(0/N vs N/N).

이렇게 남긴 대조 세트는 나중에 variant analysis(17장)의 출발점도 된다. negative control을 조금씩 트리거 쪽으로 밀어 보며 "어디서부터 터지나"를 찾으면 경계 조건과 변종이 드러난다.

## 정리

- baseline 단독 재현은 **상관**이다. negative control(입력 특이성) + patched control(수정 국소화)이 붙어야 **인과**가 된다.
- 대조는 한 번에 한 변수만 움직여야 한다 — negative control은 트리거와 최소 차이, baseline/patched는 패치 한 줄 외 전부 동일.
- patched에서 여전히 터지면 실패가 아니라 신호다: 폴트 사이트 오인이거나 패치 귀속 오류다.
- 대조가 확정하는 건 프리미티브의 존재까지. 익스플로잇 가능성·영향은 별도 판정(7장)이다.

**점검 질문** — (1) baseline+트리거를 백 번 재현해도 근본원인을 못 정하는 이유는? (2) negative control을 트리거와 "많이 다르게" 잡으면 무엇이 무너지나? (3) patched 빌드에서 동일 트리거가 여전히 터졌다면, 무엇을 의심해야 하나?

**참고** — [AddressSanitizer(Clang)](https://clang.llvm.org/docs/AddressSanitizer.html) · [KASAN(Kernel docs)](https://docs.kernel.org/dev-tools/kasan.html) · [Android Security Bulletin(수정 커밋 전/후 태그 확인)](https://source.android.com/docs/security/bulletin)

*다음 글: [최소 재현·입력 축소](/posts/android-rca-p3c06/).*
