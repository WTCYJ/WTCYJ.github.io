---
layout: post
title: "퍼징(Fuzzing) 완전 정복 — AFL++, Jackalope, libFuzzer 비교 분석"
date: 2026-05-03
category: 블로그/기술
author: yejunkim2000
tags: [퍼징, Fuzzing, AFL++, Jackalope, libFuzzer, 버그바운티, 취약점분석]
---
 
> **예상 읽기 시간:** 약 15분
> **관련 링크:** [AFL++](https://github.com/AFLplusplus/AFLplusplus) · [Jackalope](https://github.com/googleprojectzero/Jackalope) · [Google Fuzzing](https://github.com/google/fuzzing)
---


## 목차

1. [퍼징이란 무엇인가?](#1-퍼징이란-무엇인가)
2. [퍼징의 종류](#2-퍼징의-종류)
3. [퍼징의 동작 원리 — 버그는 어떻게 잡히나?](#3-퍼징의-동작-원리--버그는-어떻게-잡히나)
4. [AFL++ 아키텍처 심층 분석](#4-afl-아키텍처-심층-분석)
5. [주요 퍼저 비교](#5-주요-퍼저-비교)
6. [AFL++ 사용법 상세](#6-afl-사용법-상세)
7. [Jackalope 상세](#7-jackalope-상세)
8. [libFuzzer & Google Fuzzing](#8-libfuzzer--google-fuzzing)
9. [퍼저 선택 가이드](#9-퍼저-선택-가이드)
10. [실전 팁 & 마무리](#10-실전-팁--마무리)

---

## 1. 퍼징이란 무엇인가?

퍼징(Fuzzing)은 프로그램에 **무작위 혹은 반자동으로 생성된 입력값**을 대량 주입해 크래시, 메모리 오류, 예외 동작 등의 버그를 찾아내는 자동화된 소프트웨어 테스트 기법이다.

> **역사:** 1988년 위스콘신대학의 Barton Miller 교수가 Unix 유틸리티들이 랜덤 입력에 얼마나 충돌하는지 실험한 것이 시초다. 당시 Unix 유틸리티의 **25~33%** 가 랜덤 입력으로 크래시됐다.

퍼징이 강력한 이유는 사람이 직접 작성하는 테스트 케이스로는 발견하기 어려운 **경계 조건(edge case)** 이나 예상치 못한 입력 조합을 자동으로 탐색하기 때문이다. 실제로 Google의 OSS-Fuzz 프로젝트는 수천 개의 오픈소스 프로젝트에서 **10,000개 이상의 버그**를 자동으로 발견했다.

### 퍼징이 찾는 버그 유형

| 유형 | 설명 | 예시 |
|------|------|------|
| **메모리 오류** | 메모리 손상 취약점 | 버퍼 오버플로, use-after-free, 힙 오버플로 |
| **미정의 동작** | C/C++ UB 범주의 버그 | 정수 오버플로, NULL 포인터 역참조, 범위 초과 접근 |
| **크래시 / DoS** | 프로그램 비정상 종료 | 무한 루프, 스택 오버플로, 분할 오류(segfault) |

---

## 2. 퍼징의 종류

### ① 입력 생성 방식에 따른 분류

**생성 기반 (Generation-based)**
- 입력 포맷의 문법·스펙을 정의하고 이를 기반으로 테스트케이스를 새로 생성한다.
- 구조화된 프로토콜(HTTP, TLS, DNS 등)에 효과적이다.
- 문법을 정의하는 초기 비용이 높지만, 유효한 입력 구조를 유지할 수 있다.

**변이 기반 (Mutation-based)**
- 기존의 유효한 입력(seed)을 조금씩 변형해 새 테스트케이스를 만든다.
- 현실적이고 구현이 간단해 가장 널리 쓰인다.
- AFL, AFL++, libFuzzer가 이 방식을 채택한다.

### ② 프로그램 분석 수준에 따른 분류

**블랙박스 (Blackbox)**
- 내부 구조를 전혀 모르는 채로 입력만 변형한다.
- 구현이 쉽지만 코드 커버리지가 낮다.
- 네트워크 프로토콜 퍼징(Boofuzz 등)에 주로 사용.

**그레이박스 (Greybox)**
- 코드 커버리지 정보를 수집해 새 경로를 탐색하는 입력을 우선시한다.
- AFL이 이 방식의 대표주자로, **현재 가장 널리 쓰이는 방식**이다.
- 빠른 실행 속도와 높은 커버리지를 동시에 달성한다.

**화이트박스 (Whitebox)**
- 소스코드 분석, 기호 실행(symbolic execution)으로 특정 분기 조건을 계산한다.
- 깊은 버그를 찾을 수 있지만 매우 느리다.
- KLEE, S2E, SAGE 등이 이 방식을 사용한다.

> **실무에서 가장 많이 쓰이는 방식:** **그레이박스 + 변이 기반**의 조합이다. AFL, AFL++, libFuzzer가 모두 이 방식을 채택한다. 커버리지 피드백으로 탐색 효율을 높이면서도 화이트박스처럼 무겁지 않아 대규모 자동화에 적합하다.

---

## 3. 퍼징의 동작 원리 — 버그는 어떻게 잡히나?

퍼저가 버그를 잡아내는 과정을 단계별로 이해하는 것이 중요하다. 단순히 "랜덤 입력을 넣는다"는 설명은 절반의 진실이다. 현대 퍼저는 훨씬 정교한 피드백 루프를 사용한다.

### 3-1. 커버리지 기반 그레이박스 퍼징(CGF) 루프

```
[Seed 코퍼스] → [입력 선택] → [변이(Mutation)] → [타겟 실행]
                    ↑                                    ↓
              [큐 업데이트] ← [새 커버리지?] ← [커버리지 측정]
                                   ↓ No
                             [크래시?] → Yes → [크래시 저장]
```

이 루프의 핵심은 **"새로운 코드 경로를 발견한 입력만 큐에 보존한다"** 는 것이다. 랜덤하게 생성된 입력이더라도 기존에 본 적 없는 분기(branch)를 통과했다면, 그 입력은 "흥미로운 입력"으로 저장돼 다음 변이의 재료가 된다.

### 3-2. 커버리지란 무엇인가?

퍼저에서 커버리지는 **엣지 커버리지(edge coverage)**, 즉 **"어떤 분기에서 어떤 분기로 점프했는가"** 를 기준으로 한다.

```c
// 예시 코드
void parse(char *buf) {
    if (buf[0] == 'A') {          // 분기 1
        if (buf[1] == 'B') {      // 분기 2  ← 여기까지 도달한 입력은 "흥미로움"
            if (buf[2] == 'C') {  // 분기 3  ← 더 깊이 들어갈수록 더 흥미로움
                trigger_bug();    // ← 퍼저가 찾고 싶은 곳
            }
        }
    }
}
```

AFL++은 각 (출발 분기 → 도착 분기) 쌍을 **엣지**로 정의하고, 공유 메모리의 비트맵(bitmap)에 실행 횟수를 기록한다. 실행이 끝난 후 이 비트맵을 이전 기록과 비교해 "새 엣지를 밟았는지" 판단한다.

```
bitmap[src_block_id XOR dst_block_id >> 1] += 1
```

### 3-3. 변이(Mutation) 전략 — 어떻게 입력을 바꾸나?

AFL++의 변이는 두 단계로 나뉜다.

**① 결정론적 단계 (Deterministic stage)**

처음 seed를 처리할 때 한 번씩 실행되는 체계적 변이다.

| 변이 종류 | 설명 | 예시 |
|-----------|------|------|
| `bitflip` | 비트를 1개씩 뒤집음 | `0x41` → `0x40` |
| `byteflip` | 바이트 단위로 뒤집음 | `\x41\x42` → `\x41\x43` |
| `arith` | 정수 덧셈/뺄셈 | `0x01` → `0xFF` (오버플로 유도) |
| `interesting` | 경계값 삽입 | `0`, `127`, `255`, `-1`, `INT_MAX` 등 |
| `dictionary` | 토큰 사전에서 값 삽입 | `"Content-Type:"`, `"<script>"` 등 |

**② 확률론적 단계 (Havoc stage)**

결정론적 단계 이후 무작위 조합으로 변이를 적용하는 단계다. 여러 변이를 동시에 적용하며, 변이의 수와 종류를 랜덤하게 선택한다. 이 단계에서 실제로 버그를 많이 발견한다.

### 3-4. 버그가 검출되는 순간 — Sanitizer의 역할

퍼저 단독으로는 **크래시(segfault)** 만 잡는다. 크래시 없이 조용히 발생하는 메모리 버그(힙 오버플로, use-after-free 등)는 퍼저만으론 감지 불가능하다. 이 문제를 **Sanitizer**가 해결한다.

```
[퍼저가 변이 입력 생성]
        ↓
[ASan이 컴파일 시 레드존(redzone) 삽입]
        ↓
[프로그램 실행 중 경계 외 메모리 접근 발생]
        ↓
[ASan이 즉시 감지 → 강제 abort()]  ← 크래시 없이 넘어갈 버그를 잡음
        ↓
[퍼저가 크래시로 인식 → crashes/ 디렉토리에 저장]
```

| Sanitizer | 탐지 대상 | 오버헤드 |
|-----------|-----------|----------|
| **ASan** (AddressSanitizer) | 버퍼 오버플로, use-after-free, 힙 오버플로 | ~2x 느림 |
| **UBSan** (UndefinedBehaviorSanitizer) | 정수 오버플로, NULL 역참조, 시프트 오류 | ~1.3x 느림 |
| **MSan** (MemorySanitizer) | 초기화되지 않은 메모리 읽기 | ~3x 느림 |
| **TSan** (ThreadSanitizer) | 데이터 레이스 (멀티스레드 버그) | ~5x 느림 |

> **핵심 요약:** 퍼저는 입력을 변이시키고, Sanitizer는 버그를 드러낸다. 둘의 조합이 핵심이다.

### 3-5. 크래시 분류 — 모든 크래시가 같은 버그는 아니다

퍼징을 오래 돌리면 수백 개의 크래시가 쌓인다. 이 중 실제 유니크한 버그는 몇 개뿐인 경우가 대부분이다. AFL++은 크래시를 **크래시 발생 시점의 커버리지 비트맵**으로 구분하는데, 완전히 동일한 코드 경로를 밟은 크래시는 같은 버그로 취급한다.

```bash
# afl-cmin으로 유니크 크래시만 남기기
afl-cmin -i ./out/crashes/ -o ./unique_crashes/ -- ./target @@

# GDB로 크래시 원인 분석
gdb ./target
(gdb) run < unique_crashes/id:000000,sig:11,...
```

---

## 4. AFL++ 아키텍처 심층 분석

AFL++을 이해하면 다른 퍼저들의 동작 방식도 자연스럽게 이해된다. AFL++의 전체 아키텍처는 크게 5개의 컴포넌트로 구성된다.

### 4-1. 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│                      AFL++ 퍼저                          │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │  Seed    │    │  Queue   │    │  Mutation Engine  │  │
│  │ Corpus   │───▶│ (코퍼스)  │───▶│  (변이 엔진)      │  │
│  └──────────┘    └──────────┘    └────────┬─────────┘  │
│                                           │             │
│  ┌──────────────────────────────────────┐ │             │
│  │           Shared Memory              │ │             │
│  │        (커버리지 비트맵 64KB)          │ │             │
│  └──────────────────┬───────────────────┘ │             │
│                     │                     ▼             │
│  ┌──────────────────┴───────────────────────────────┐  │
│  │              Target Binary (계측됨)               │  │
│  │   afl-clang-fast로 빌드 → 각 분기마다 카운터 삽입   │  │
│  └──────────────────────────────────────────────────┘  │
│                     │                                   │
│            ┌────────▼────────┐                          │
│            │  Coverage Check  │                          │
│            │  새 엣지? → 큐 추가│                         │
│            │  크래시? → 저장   │                          │
│            └─────────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

### 4-2. 컴포넌트 1 — 계측 컴파일러 (afl-clang-fast)

AFL++은 LLVM 패스를 이용해 컴파일 시 타겟 바이너리에 계측 코드를 삽입한다. 삽입되는 코드는 각 기본 블록(basic block)의 시작 지점에 위치하며, 실행 시마다 공유 메모리 비트맵을 업데이트한다.

```c
// 컴파일러가 각 분기마다 삽입하는 코드 (의사 코드)
// 실제 구현은 LLVM IR 수준에서 이루어짐
void __afl_trace(uint32_t x) {
    // x는 컴파일 타임에 각 블록마다 랜덤하게 할당된 ID
    __afl_area_ptr[x ^ __afl_prev_loc]++;  // 엣지 카운트 증가
    __afl_prev_loc = x >> 1;               // 현재 블록을 이전 블록으로
}
```

이 비트맵은 퍼저 프로세스와 타겟 프로세스가 **공유 메모리(shared memory)** 로 공유하기 때문에, 실행이 끝난 즉시 퍼저가 어떤 경로가 실행됐는지 알 수 있다.

### 4-3. 컴포넌트 2 — Fork Server

매 입력마다 프로세스를 처음부터 `exec()`하면 느리다. AFL++은 **Fork Server** 방식으로 이 문제를 해결한다.

```
[afl-fuzz] ←─ 파이프 ─→ [Fork Server (타겟 내부에 삽입됨)]
                              │
                  새 입력마다 fork() 호출
                              │
                    ┌─────────┴──────────┐
                    │   Child Process     │
                    │  (실제 입력 실행)    │
                    └────────────────────┘
```

타겟 바이너리는 `main()` 진입 전에 한 번만 초기화(라이브러리 로드, 환경 설정 등)되고, 이후 각 테스트케이스마다 이미 초기화된 상태에서 `fork()`만 한다. 이를 통해 **실행 오버헤드를 최소화**한다.

### 4-4. 컴포넌트 3 — 큐 스케줄러 (Queue Scheduler)

모든 seed가 동등하게 처리되지 않는다. AFL++은 각 큐 엔트리에 **에너지(energy)** 를 부여하고, 에너지가 높은 엔트리에 더 많은 변이 횟수를 할당한다.

에너지 계산에 영향을 주는 요소:
- **실행 속도:** 빠르게 실행되는 seed에 에너지를 더 줌
- **파일 크기:** 작은 seed를 선호 (변이 공간이 단순)
- **발견한 커버리지:** 더 많은 새 엣지를 발견한 seed 우대
- **발견 시간:** 최근에 발견된 seed 우대 (새로운 영역 탐색 중일 가능성)

AFL++에 추가된 **Power Schedule** 알고리즘(`-p explore`, `-p exploit` 등)은 이 에너지 배분을 더욱 정교하게 조정한다.

### 4-5. 컴포넌트 4 — CMPLOG (비교 연산 추적)

많은 파서는 매직 바이트나 체크섬을 검사하는 코드를 갖는다.

```c
if (memcmp(buf, "PNG\x89", 4) == 0) {  // 이 조건을 통과해야 내부 로직 실행
    parse_png(buf);
}
```

단순 변이로는 정확한 4바이트 매직 시퀀스를 맞히기 매우 어렵다. **CMPLOG**는 이 비교 연산의 양쪽 값을 모두 기록했다가, 해당 위치의 입력을 실제 비교 대상값으로 직접 치환해버린다. 마치 "정답지를 보고 쓰는 것"처럼 체크섬이나 매직 바이트 장벽을 자동으로 돌파한다.

### 4-6. 컴포넌트 5 — 커스텀 뮤테이터

AFL++은 Python이나 C로 작성한 커스텀 뮤테이터를 플러그인으로 연결할 수 있다. 예를 들어 JSON 파서를 퍼징할 때, 문법에 맞는 JSON을 생성하는 뮤테이터를 연결하면 파서 내부 깊숙이 도달하는 입력을 훨씬 빠르게 만들어낼 수 있다.

```python
# 커스텀 뮤테이터 예시 (Python)
import json, random

def fuzz(buf, add_buf, max_size):
    try:
        obj = json.loads(buf)
        # JSON 구조를 유지하면서 값만 변형
        mutate_json_values(obj)
        return json.dumps(obj).encode()
    except:
        return buf  # 파싱 실패 시 원본 반환
```

---

## 5. 주요 퍼저 비교

| 퍼저 | 방식 | 타겟 | 계측 | 언어 | 성숙도 |
|------|------|------|------|------|--------|
| **AFL++** | 그레이박스 | Linux 바이너리 | 컴파일 / QEMU / Frida | C/C++ | ★★★★★ |
| **Jackalope** | 그레이박스 | Windows / macOS / Linux | TinyInst (바이너리) | C/C++ | ★★★☆☆ |
| **libFuzzer** | 그레이박스 | 라이브러리 함수 | 컴파일 (LLVM SanitizerCoverage) | C/C++/Rust 등 | ★★★★★ |
| **Honggfuzz** | 그레이박스 | Linux / macOS / Android | 컴파일 / 하드웨어 PT | C/C++ | ★★★★☆ |
| **Syzkaller** | 그레이박스 | OS 커널 시스콜 | 커버리지 커널 모듈 | Go / C | ★★★★★ |
| **Boofuzz** | 블랙박스 | 네트워크 프로토콜 | 없음 (블랙박스) | Python | ★★★☆☆ |

---

## 6. AFL++ 사용법 상세

**AFL++ (American Fuzzy Lop Plus Plus)** 는 Google의 AFL을 커뮤니티가 포크해 대폭 개선한 업계 표준 퍼저다. 아키텍처는 섹션 4에서 다뤘으니, 여기서는 실제 사용법과 계측 방식을 정리한다.

### 계측 방식 비교

| 방식 | 설명 | 속도 | 소스 필요 |
|------|------|------|-----------|
| 컴파일 타임 (afl-clang-fast) | LLVM 패스로 빌드 시 브랜치 카운터 삽입 | 매우 빠름 | O |
| QEMU 모드 (-Q) | QEMU 에뮬레이션으로 런타임 계측 | 약 1/10 속도 | X |
| Frida 모드 (-O) | Frida 훅으로 런타임 계측 | QEMU보다 빠름 | X |
| 하드웨어 PT | Intel PT로 하드웨어 수준 트레이싱 | 거의 네이티브 | X |

### 기본 사용 예시

```bash
# 소스코드가 있는 경우 — 컴파일 계측
CC=afl-clang-fast CXX=afl-clang-fast++ ./configure && make

# 퍼징 실행
afl-fuzz -i ./seeds/ -o ./findings/ -- ./target_binary @@
# @@는 AFL이 생성한 파일 경로로 자동 치환됨

# 소스 없는 바이너리 — QEMU 모드
afl-fuzz -Q -i ./seeds/ -o ./findings/ -- ./target_binary @@
```

- **개발사:** 커뮤니티 (AFLplusplus)
- **라이선스:** Apache 2.0
- **GitHub Stars:** 17k+
- **저장소:** https://github.com/AFLplusplus/AFLplusplus

AFL++은 **커버리지 기반 변이 퍼징**의 사실상 표준이다.

### AFL++의 주요 개선점

- **CMPLOG:** 비교 연산자의 입력값을 추적해 매직 바이트 / 체크섬을 자동으로 우회한다.
- **MOpt / 커스텀 뮤테이터:** 변이 전략을 동적으로 최적화하거나 직접 구현할 수 있다.
- **Frida 모드:** 소스 없는 바이너리를 Frida로 런타임 계측한다.
- **Persistent 모드:** fork() 오버헤드 없이 루프 안에서 직접 퍼징한다. (속도 수백배↑)
- **병렬 퍼징:** Master/Slave 구조로 멀티코어를 활용한다.

### Persistent 모드 하네스 예시

```c
#include <stdint.h>
#include <stddef.h>

// AFL++ persistent mode entry point
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // 타겟 함수 직접 호출
    parse_input(data, size);
    return 0;  // 0이면 정상, -1이면 이 케이스를 큐에서 제외
}
```

```bash
# AddressSanitizer와 함께 빌드
afl-clang-fast -fsanitize=address -o fuzz_target harness.c target.c

# 병렬 퍼징 (Master 1개 + Slave 3개)
afl-fuzz -M master -i seeds/ -o out/ -- ./fuzz_target @@
afl-fuzz -S slave1 -i seeds/ -o out/ -- ./fuzz_target @@
afl-fuzz -S slave2 -i seeds/ -o out/ -- ./fuzz_target @@
afl-fuzz -S slave3 -i seeds/ -o out/ -- ./fuzz_target @@
```

### 장단점

**장점**
- 뛰어난 커버리지 탐색 효율
- 다양한 계측 모드 (소스/QEMU/Frida)
- 광범위한 커뮤니티와 문서
- libFuzzer 하네스와 호환
- 멀티코어 병렬 퍼징

**단점**
- Windows 미지원 (WSL 필요)
- QEMU 모드는 속도 10x 저하
- 초기 설정 학습 곡선 존재

---

## 7. Jackalope 상세

**Jackalope**는 Google Project Zero가 개발한 바이너리 전용 크로스플랫폼 퍼저다.

- **개발사:** Google Project Zero
- **라이선스:** Apache 2.0
- **지원 OS:** Windows / macOS / Linux
- **계측 도구:** TinyInst
- **저장소:** https://github.com/googleprojectzero/Jackalope

Jackalope의 핵심은 **TinyInst**라는 자체 동적 계측 라이브러리다. TinyInst는 DynamoRIO나 Pin보다 훨씬 가볍고, 특히 **Windows와 macOS**에서 소스코드 없이도 높은 성능으로 커버리지를 수집할 수 있다.

### Jackalope의 특징

- **바이너리 전용:** 소스코드 불필요 — 클로즈드소스 타겟에 적합하다.
- **크로스플랫폼:** Windows DLL, macOS dylib, Linux .so 모두 지원한다.
- **AFL 변이 엔진:** 내부적으로 AFL 방식의 변이 알고리즘을 사용한다.
- **확장성:** 커스텀 뮤테이터, 샘플 드라이버를 구현할 수 있다.

### Jackalope 사용 예시 (Windows)

```powershell
# Windows에서 PDF 파서 퍼징
fuzzer.exe -in seeds\ -out findings\ -t 5000
           -delivery samplecode -target_module pdfparser.dll
           -target_method ParseDocument -nargs 2
           -iterations 10000 -persist -loop
```

> **언제 Jackalope를 선택할까?** Windows 바이너리나 macOS 바이너리를 소스코드 없이 퍼징해야 할 때. 예: 벤더가 제공하는 폰트 파서, PDF 리더, 드라이버 등의 클로즈드소스 바이너리.

### 장단점

**장점**
- Windows/macOS 네이티브 지원
- 소스코드 불필요
- TinyInst로 낮은 오버헤드
- Google Project Zero의 신뢰성

**단점**
- AFL++보다 커뮤니티가 작음
- 소스 계측 불가 (바이너리 전용)
- 문서가 상대적으로 부족

---

## 8. libFuzzer & Google Fuzzing

**libFuzzer**는 LLVM에 내장된 인프로세스(in-process) 커버리지 기반 퍼징 엔진이다. 별도 바이너리가 아닌 **컴파일러 플래그 하나**로 활성화된다.

- **문서:** https://llvm.org/docs/LibFuzzer.html
- **Google Fuzzing 가이드:** https://github.com/google/fuzzing

### libFuzzer 빌드 및 실행

```bash
# AddressSanitizer + libFuzzer 함께 사용
clang -fsanitize=address,fuzzer target.c -o fuzz_target

# 실행 (코어 수, 최대 입력 크기 등 옵션)
./fuzz_target -jobs=4 -max_len=4096 corpus/

# Rust — cargo-fuzz 사용
cargo fuzz add fuzz_target_1
cargo fuzz run fuzz_target_1
```

### libFuzzer 하네스 구조

```c
// libFuzzer 엔트리포인트 — 항상 이 시그니처를 사용
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // 타겟 라이브러리 함수 호출
    MyParser parser;
    parser.parse(data, size);
    return 0;
}
```

### AFL++ ↔ libFuzzer 호환

libFuzzer 형식의 하네스(`LLVMFuzzerTestOneInput`)는 AFL++의 `-fsanitize=fuzzer-no-link` 빌드로도 바로 사용 가능하다. **하나의 하네스로 두 퍼저 모두 활용할 수 있어 효율적이다.**

```bash
# 동일한 하네스를 AFL++로 빌드
afl-clang-fast -fsanitize=address -fsanitize=fuzzer-no-link \
    harness.c target.c -o afl_fuzz_target

# libFuzzer로 빌드
clang -fsanitize=address,fuzzer \
    harness.c target.c -o libfuzz_target
```

### Google OSS-Fuzz

Google의 [OSS-Fuzz](https://google.github.io/oss-fuzz/)는 libFuzzer + AFL++ + Honggfuzz를 동시에 실행해 오픈소스 프로젝트를 24/7 퍼징한다. 발견된 버그는 90일 후 자동으로 공개된다.

---

## 9. 퍼저 선택 가이드

| 상황 | 추천 퍼저 | 이유 |
|------|-----------|------|
| 소스코드 있는 Linux C/C++ 라이브러리 | AFL++ + libFuzzer | 최고의 커버리지, OSS-Fuzz 호환 |
| Windows 클로즈드소스 바이너리 | Jackalope | TinyInst 기반 Windows 네이티브 지원 |
| macOS 바이너리 (dylib, 앱) | Jackalope | macOS 지원 퍼저 중 가장 성숙 |
| 소스 없는 Linux 바이너리 | AFL++ (QEMU/Frida 모드) | 바이너리 계측 모드 내장 |
| Linux 커널 / 시스콜 인터페이스 | Syzkaller | 시스콜 문법 명세 기반 생성 퍼징 |
| 네트워크 프로토콜 / IoT 장비 | Boofuzz | 프로토콜 모델 기반 블랙박스 퍼징 |
| Rust / Go 라이브러리 | libFuzzer (cargo-fuzz) | 언어 생태계 통합, 언어별 새니타이저 |

---

## 10. 실전 팁 & 마무리

### 효과적인 퍼징을 위한 체크리스트

**1. Sanitizer 함께 사용**

ASan, UBSan, MSan을 퍼저와 함께 빌드하면 크래시 없이 넘어가는 메모리 오류도 잡을 수 있다.

```bash
# AddressSanitizer + UndefinedBehaviorSanitizer 조합
afl-clang-fast -fsanitize=address,undefined -o target target.c
```

**2. 고품질 Seed 준비**

실제 프로그램이 처리하는 유효한 입력 파일(PDF, PNG, XML 등)을 seed로 사용하면 초기 커버리지가 크게 높아진다.

**3. 코퍼스 최소화**

```bash
# afl-cmin으로 중복 커버리지 seed 제거
afl-cmin -i ./corpus/ -o ./corpus_min/ -- ./target @@
```

**4. Persistent 모드 활용**

fork() 오버헤드를 없애 초당 실행 횟수를 10~100배 높일 수 있다.

**5. 크래시 트리아지**

```bash
# afl-triage로 유니크 크래시 분류
afl-triage -i ./findings/crashes/ -o ./unique/ -- ./target @@
```

### 버그바운티에서의 퍼징 전략

> 공개된 오픈소스 라이브러리를 대상으로 AFL++을 돌리는 것은 가장 접근하기 쉬운 시작점이다. GitHub의 취약점 히스토리를 보고 비슷한 파서 코드를 집중 퍼징하는 **타겟팅 전략**이 효과적이다.

1. 타겟 프로그램의 **입력 파서** 부분을 식별한다.
2. 관련 **CVE 히스토리**를 분석해 취약한 코드 패턴을 파악한다.
3. 해당 코드 경로를 집중적으로 실행하는 **Seed 코퍼스**를 구성한다.
4. ASan + AFL++으로 **장기 퍼징**을 돌린다 (최소 24시간 이상).
5. 크래시 발생 시 **익스플로잇 가능성**을 분석해 보고서를 작성한다.

---

## 참고 자료

- [1] [AFLplusplus/AFLplusplus — GitHub](https://github.com/AFLplusplus/AFLplusplus)
- [2] [googleprojectzero/Jackalope — GitHub](https://github.com/googleprojectzero/Jackalope)
- [3] [google/fuzzing — Fuzzing 가이드 & 튜토리얼](https://github.com/google/fuzzing)
- [4] [libFuzzer 공식 문서 — llvm.org](https://llvm.org/docs/LibFuzzer.html)
- [5] [OSS-Fuzz — Google 오픈소스 퍼징 플랫폼](https://google.github.io/oss-fuzz/)
- [6] [Honggfuzz — GitHub](https://github.com/google/honggfuzz)
- [7] [Syzkaller — GitHub](https://github.com/google/syzkaller)
