---
layout: post
title: "sanitizer 기반 native 연구"
date: 2027-01-05 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ASan, HWASan, Sanitizer, libFuzzer, NDK]
excerpt: "네이티브 크래시가 곧 취약점은 아니다 — ASan은 유효한 인접 메모리로 새는 OOB 쓰기까지 접근 시점에 잡지만, 무한 루프 DoS는 어떤 sanitizer도 리포트하지 않고(`-timeout`의 몫), `NDEBUG`가 `assert`를 지워도 sanitizer 계측은 그대로 살아 있다."
---

퍼저를 붙여 입력을 수억 번 던져도, 그 입력이 무슨 규칙을 어겼는지 읽어 줄 계측이 없으면 남는 건 `Segmentation fault` 한 줄뿐이다. C/C++ 네이티브 코드에서 메모리 안전 위반의 대부분은 즉시 죽지 않는다 — 유효한 인접 힙/스택으로 몇 바이트 새는 OOB 쓰기, 해제 직후 아직 매핑돼 있는 청크를 다시 쓰는 UAF는 SIGSEGV를 내지 않고 조용히 지나간다. sanitizer는 이 "조용한 위반"을 접근이 일어나는 바로 그 순간에 붙잡는 판독기다.

이 글은 ASan·HWASan·UBSan을 native 취약점 연구 파이프라인에 붙여 크래시의 정체를 읽어 내는 방법을 정리하고, 고정 크기 스택 배열에 경계 검사 없이 쓰는 OOB 한 클래스를 자작 하네스로 감싸며 sanitizer가 무엇을 잡고 무엇을 못 잡는지 실습한 기록이다. (실습에 쓴 버그는 내가 이전 native 연구에서 직접 관측한 사례인데 **원저장소가 아카이브되어 아직 미패치이고 책임 공개도 끝나지 않았다.** 그래서 라이브러리·함수·정확한 트리거는 밝히지 않고 버그 클래스만 다룬다.)

> **한 줄 결론**: sanitizer는 "크래시가 나는 곳"이 아니라 "메모리 규칙을 어긴 순간"을 잡는다. 그래서 SIGSEGV로는 조용히 지나갈 인접-메모리 OOB 쓰기와 UAF를 접근 시점에 드러내지만, 무한 루프·논리 DoS는 잡지 못한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 (1) sanitizer 종류별로 무엇을 잡는지, (2) libFuzzer 하네스에 ASan/UBSan을 붙여 크래시를 판독하는 절차, (3) sanitizer 리포트를 취약점 등급으로 과장하지 않고 정확히 읽는 법을 다룬다. 무기화된 익스플로잇이나 실기기 공격은 다루지 않는다 — 전부 자작 하네스와 대표적 메모리 안전 버그 클래스, 에뮬레이터 범위다. 실습 대상 버그는 내가 이전에 관측한 미패치·책임 공개 진행 중 사례라, 재현 가능한 트리거는 싣지 않고 버그 클래스만 짚는다.

7장에서 세운 libFuzzer 하네스, 8장의 코퍼스·커버리지, 9장의 크래시 중복 제거·최소화가 밑에 깔린다. sanitizer는 이 파이프라인의 판독기다 — 퍼저가 입력을 만들고, 최소화가 방아쇠 입력을 줄이고, sanitizer가 그 입력이 무슨 규칙을 어겼는지 읽는다. 익스플로잇 완화(Atlas C37)를 알면 sanitizer가 잡는 버그 클래스(OOB·UAF·정수 오버플로)가 왜 실제로 위험한지 연결된다.

전체 구조에서 이 장은 4부(심화 취약점 연구)의 "판독" 축이다. 앞의 6~9장이 표면 선정·하네스·코퍼스·트리아지로 크래시를 만들어 냈다면, 여기서 그 크래시를 버그 클래스로 분류한다. 다음 11장(compatibility layer·중복 구현 버그)부터는 이 판독 능력을 특정 표면에 겨눈다.

## 핵심 개념 — sanitizer는 무엇을 잡고 무엇을 못 잡나

sanitizer는 컴파일 시점에 메모리 접근마다 계측 코드를 심고, 별도 shadow 메모리로 "이 주소를 지금 만져도 되는가"를 검사한다. 종류별로 잡는 버그와 제약이 다르다.

| sanitizer | 잡는 버그 | 아키텍처 | 오버헤드 | 비고 |
|--|--|--|--|--|
| ASan | heap/stack/global OOB, UAF, double-free, 일부 leak | x86_64·arm64 | CPU 약 2배 | redzone+shadow, 가장 범용 `Source-confirmed` |
| HWASan | ASan 클래스 + 더 넓은 OOB/UAF | **arm64 전용** | 메모리 오버헤드 ASan보다 낮음 | 주소 태깅(top-byte-ignore) `Source-confirmed` |
| UBSan | 정수 오버플로·정렬 위반·형변환 UB | 무관 | 낮음 | 개별 체크 선택(`signed-integer-overflow` 등) `Source-confirmed` |
| MSan | 초기화 안 된 메모리 읽기 | x86_64 위주 | 높음 | 전 의존 코드 계측 필요 → Android 실무 난이도 큼 `Source-confirmed` |
| TSan | 데이터 레이스 | x86_64·arm64 | 높음 | 멀티스레드 서비스용 |

핵심 세 가지를 짚는다.

- **ASan은 접근 시점에 잡는다.** 할당마다 앞뒤에 redzone(독 영역)을 두고, 접근 주소를 shadow로 조회한다. 그래서 OOB 쓰기가 유효한 인접 변수로 새더라도 — SIGSEGV가 안 나더라도 — 쓰기 명령에서 즉시 리포트한다. `Source-confirmed`
- **HWASan은 사실상 arm64에서만 산다.** 기본 스킴은 ARM64의 상위 바이트 무시(TBI) 기능으로 포인터에 태그를 심고 태그 불일치를 검사한다. x86_64엔 이 TBI가 없어, clang의 실험적 aliasing 모드를 빼면 실질적으로 쓰지 않는다. Android는 `aosp_arm64` HWASan 시스템 이미지를 제공한다. `Source-confirmed`
- **`assert`와 sanitizer는 직교한다.** `NDEBUG`로 빌드하면 `assert()`는 사라지지만, `-fsanitize=` 계측은 그대로다. 즉 "릴리스 빌드라 assert가 없어 조용한 버그"를 sanitizer는 여전히 잡는다. 이게 실무에서 가장 자주 오해되는 지점이다. `Source-confirmed`

> **[그림 1]** `-fsanitize=address` 유무로 같은 하네스를 두 번 빌드해 `nm`/`objdump`로 `__asan_` 계측 심볼이 실려 들어간 쪽과 아닌 쪽을 대조한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

호스트(WSL/Linux)에서 Clang libFuzzer로 진행한다. 대상은 고정 크기 스택 배열에 경계 검사 없이 쓰는 OOB 클래스를 학습용으로 재현하는 것뿐이다 — 내가 이전 native(VR) 연구에서 직접 관측한 사례인데, **원저장소가 아카이브되어 아직 미패치이고 책임 공개가 끝나지 않았다.** 그래서 라이브러리·함수·정확한 트리거는 밝히지 않고, 익명화한 자작 하네스로 버그 클래스만 감싼다. 제3자 프로덕션 앱, 무기화 익스플로잇, 실데이터는 없다. 온디바이스 HWASan은 arm64 AVD 범위에서 개념만 짚는다.

## 실습 절차와 관측

### 가설

- **가설 A** — 파서가 고정 크기 스택 배열에 인덱스 검사 없이 쓰므로, 한 줄에 배열 용량을 넘는 원소가 들어오면 스택 버퍼 오버플로가 난다. `NDEBUG`에선 `assert`가 없어 프로세스가 조용히 살아 있지만, ASan은 쓰기 시점에 잡는다. `Reported`
- **가설 B** — 정수 오버플로(예: 크기 계산 곱셈)는 ASan이 아니라 UBSan(`signed-integer-overflow`)이 잡는다. 즉 버그 클래스마다 담당 sanitizer가 다르다. `Inferred`
- **가설 C** — 무한 루프형 DoS(내 IrfanView `Dpx.dll` 사례처럼)는 어떤 sanitizer도 리포트하지 않는다. 이건 libFuzzer `-timeout`이 잡는다. `Reported`

### 절차

1. 버그 클래스만 익명화해 재구성한 학습용 파서를 자작 하네스로 감싼다(입력 → 파서 진입 함수 한 번 호출).
2. ASan+libFuzzer로 빌드해 최소화된 방아쇠 입력을 재실행한다.
3. UBSan으로도 별도 빌드해 정수 오버플로 체크를 켠다.
4. 무한 루프 입력에는 `-timeout`을 걸어 sanitizer 리포트와 타임아웃을 구분한다.

```bash
# (A) ASan + libFuzzer: 메모리 위반 판독
clang -g -O1 -fsanitize=address,fuzzer -fno-omit-frame-pointer \
      harness.c -o fuzz_asan
ASAN_OPTIONS=abort_on_error=1:detect_leaks=0 \
  ./fuzz_asan crash-min.bin          # 9장에서 최소화한 입력 재실행

# (B) UBSan: 정수 오버플로 판독 (같은 하네스, 다른 계측)
clang -g -O1 -fsanitize=signed-integer-overflow,fuzzer \
      -fno-sanitize-recover=all harness.c -o fuzz_ubsan
./fuzz_ubsan crash-min.bin

# (C) 무한 루프는 sanitizer가 아니라 timeout으로
./fuzz_asan hang-input -timeout=10   # 10초 넘으면 libFuzzer가 강제 종료
```

> **[그림 2]** `./fuzz_asan crash-min.bin` 실행 결과 — `stack-buffer-overflow ... WRITE of size 4`와 익명화한 파서 함수 프레임, 오버플로된 고정 크기 스택 배열이 표시된 ASan 리포트 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — 실제 실행으로 줄 번호·주소를 교체할 것:

```
==11894==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffd... 
WRITE of size 4 at 0x7ffd... thread T0
    #0 0x... in parse_line parser.c:<줄교체>
    #1 0x... in parse_input parser.c:<줄교체>
    #2 0x... in LLVMFuzzerTestOneInput harness.c:14
Address 0x7ffd... is located in stack of thread T0 at offset ... in frame
    #0 ... in parse_line
  This frame has object(s):
    [..., ...) 'buf' (line <줄교체>) <== Memory access overflows this variable
SUMMARY: AddressSanitizer: stack-buffer-overflow in parse_line
```

세 가지가 읽힌다. (1) ASan은 `WRITE` 방향과 접근 크기(`size 4`), 오버플로된 변수 이름(`'buf'`)까지 준다 — 최소화 입력과 합치면 근본 원인이 거의 확정된다. (2) 같은 입력을 UBSan 빌드로 돌리면 이 사례에선 조용하다 — OOB 쓰기는 UBSan의 관할이 아니다. 버그 클래스와 sanitizer가 1:1이 아님을 눈으로 확인한다. (3) IrfanView형 무한 루프 입력은 ASan에서 아무 리포트 없이 매달린다. `-timeout`이 없으면 퍼저 자체가 멈춘 것처럼 보인다 — DoS를 메모리 취약점으로 오분류하기 쉬운 함정이다.

## Root Cause — 왜 sanitizer가 assert·SIGSEGV보다 더 보나

일반 크래시(SIGSEGV)는 CPU가 **매핑되지 않은 페이지**를 건드릴 때만 난다. 고정 크기 스택 배열 `buf[N]`을 그 끝 너머로 몇 바이트 넘겨 쓰면 그 주소는 대개 같은 스택 프레임 안의 유효 메모리라 페이지는 매핑돼 있다 — 그래서 무해하게 넘어가고, 손상은 나중에 엉뚱한 곳에서 터진다. `assert(idx < N)`(N = 배열 용량) 검사가 있었다면 잡혔겠지만 `NDEBUG` 릴리스에선 그 검사가 컴파일 단계에서 통째로 사라진다.

ASan은 이 두 사각을 동시에 메운다. 배열/할당 둘레에 접근 불가로 표시된 redzone을 두고, **모든** 메모리 접근을 shadow 조회로 감싼다. 그래서 매핑 여부와 무관하게 "규칙상 만지면 안 되는 바이트"를 접근 명령에서 즉시 잡는다. HWASan은 페이지가 아니라 포인터 태그로 같은 일을 하되, arm64의 TBI 덕에 메모리 오버헤드가 훨씬 낮아 퍼징 대신 넓은 온디바이스 커버리지에 적합하다. `Source-confirmed` 요컨대 sanitizer가 잡는 건 "죽는 순간"이 아니라 "규칙 위반의 순간"이고, 그래서 조용한 버그를 잡는다.

## 방어와 회귀 검증

- **sanitizer 크래시는 곧바로 회귀 테스트로.** 9장에서 최소화한 방아쇠 입력을 ASan 빌드로 CI에 고정해 두면, 패치가 실제로 그 접근을 막았는지 재빌드마다 자동 확인된다. 리포트의 `SUMMARY` 한 줄이 dedup 키가 된다.
- **클래스별로 sanitizer를 갈아 끼운다.** OOB·UAF는 ASan/HWASan, 정수 UB는 UBSan, 초기화 미스는 MSan. 하나로 다 잡히지 않는다. wabt `wasm2c` 하네스도 ASan+UBSan을 함께 물려 돌렸다. `Reported`
- **등급을 부풀리지 않는다.** ASan 리포트 = 메모리 안전 버그이지 곧 RCE가 아니다. OOB **읽기**는 정보 노출/크래시에 가깝고, 무한 루프는 DoS다. 내 wabt 계열 버그가 공개 이후 3.3 LOW·DISPUTED로 분류된 선례가 이 절제의 이유다. `Reported`

## 버전 차이와 한계

- **HWASan은 arm64 전용**이고 온디바이스(또는 arm64 AVD·`aosp_arm64` HWASan 이미지)에서만 돈다. x86_64 호스트 퍼징엔 ASan을 쓴다. `Source-confirmed`
- **MTE(ARMv8.5)는 sanitizer가 아니라 하드웨어 완화**다. 프로덕션에서 상시 켤 수 있는 방어이지 연구용 판독기가 아니며, 별도 하드웨어/이미지 지원이 필요하다 — 이 글의 ASan/HWASan과 목적이 다르다. `Inferred`
- **MSan은 Android에서 실무 난도가 높다.** 초기화 미스 오탐을 피하려면 libc를 포함한 의존 코드 전체가 계측돼야 해서, 표준 NDK 앱엔 바로 쓰기 어렵다. `Source-confirmed`
- **재현 환경 차이.** Android 기본 네이티브 할당자는 Scudo인데 ASan은 할당자를 자체 교체한다. 호스트 ASan에서 난 크래시의 힙 배치가 온디바이스 Scudo에서 그대로 재현되지 않을 수 있으니, 힙 레이아웃 의존 재현은 "환경 확인 필요"로 남긴다. `Source-confirmed`
- **오버헤드는 처리량을 깎는다.** ASan은 CPU 약 2배라 8장의 커버리지-속도 균형에 직접 영향을 준다. 정확한 배수는 대상·플래그마다 다르니 문서화 시 실측을 표기한다. `Source-confirmed`

## 정리

- sanitizer는 크래시 지점이 아니라 규칙 위반 지점을 잡는다 — 그래서 SIGSEGV로는 조용한 인접-메모리 OOB·UAF를 접근 시점에 드러낸다.
- 버그 클래스마다 담당이 다르다: OOB/UAF는 ASan·HWASan, 정수 UB는 UBSan. 하나로 다 잡히지 않는다.
- HWASan은 arm64 전용, `NDEBUG`는 `assert`만 지우고 계측은 남으며, 무한 루프 DoS는 `-timeout`의 몫이다.
- ASan 리포트를 곧 RCE로 부풀리지 말 것 — 읽기 OOB·DoS와 쓰기 손상을 구분해 등급을 매긴다.

**점검 질문** — (1) 고정 크기 스택 배열의 끝을 한 칸 넘겨 쓰는 OOB가 SIGSEGV를 안 내는데 ASan은 어떻게 잡는가? (2) HWASan을 x86_64 호스트에서 못 쓰는 이유는? (3) 무한 루프 입력에 sanitizer가 침묵하면 무엇으로 잡아야 하는가?

**참고** — [AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) · [HWAddressSanitizer](https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html) · [Android NDK ASan 가이드](https://developer.android.com/ndk/guides/asan) · [source.android.com HWASan](https://source.android.com/docs/security/test/memory-safety/hwasan) · [UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) · [libFuzzer](https://llvm.org/docs/LibFuzzer.html)

*다음 글: [compatibility layer·중복 구현 버그](/posts/android-vulnresearch-p4c11/).*
