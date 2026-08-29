---
layout: post
title: "AFL 핵심 메커니즘 — afl-gcc.c, afl-as.c/h, afl-fuzz.c, technical_details.txt"
date: 2026-05-05
category: 블로그/기술
author: yejunkim2000
tags: [AFL, Fuzzing, 퍼징, 취약점분석, BugBounty, 보안연구, 소스코드분석]
---

> **분석 파일:** `afl-gcc.c`, `afl-as.c`, `afl-as.h`, `afl-fuzz.c`, `config.h`
> **저장소:** [google/AFL](https://github.com/google/AFL)

---

## 목차

1. [Instrumentation — 계측 코드가 심어지는 과정](#1-instrumentation--계측-코드가-심어지는-과정)
2. [Coverage — 커버리지 측정 방법](#2-coverage--커버리지-측정-방법)
3. [Fork Server — exec() 오버헤드 제거](#3-fork-server--exec-오버헤드-제거)
4. [Mutation — 입력 변이 전략](#4-mutation--입력-변이-전략)
5. [전체 흐름 종합](#5-전체-흐름-종합)

---

## 1. Instrumentation — 계측 코드가 심어지는 과정

**목표:** 타겟 바이너리가 실행될 때마다 어떤 경로를 밟았는지 기록하는 코드를 심는다.

### 1-1. 컴파일 파이프라인

AFL의 계측은 LLVM 패스가 아니라 **어셈블러(assembler) 단계**에서 이루어진다.

```
소스코드 (.c)
    ↓
[afl-gcc]     ← gcc를 래핑한 wrapper. -B 플래그로 어셈블러를 afl-as로 교체
    ↓
gcc           ← 소스 → 어셈블리 .s 파일 생성
    ↓
[afl-as]      ← ★ 이 단계에서 .s 파일을 파싱해 계측 코드 삽입
    ↓
계측된 바이너리
```

### 1-2. afl-gcc.c — 어셈블러 교체

`afl-gcc`의 핵심은 `-B` 플래그 하나다. gcc에게 "어셈블러를 이 경로에서 찾아라"고 지시해, 시스템 `as` 대신 `afl-as`를 끼워넣는다.

```c
// afl-gcc.c — edit_params()
static void edit_params(u32 argc, char** argv) {

    // 어셈블러를 afl-as로 교체
    cc_params[cc_par_cnt++] = "-B";
    cc_params[cc_par_cnt++] = as_path;

    // Clang은 내장 어셈블러를 비활성화해야 afl-as가 호출됨
    if (clang_mode)
        cc_params[cc_par_cnt++] = "-no-integrated-as";

    // AFL 마킹 플래그
    cc_params[cc_par_cnt++] = "-D__AFL_COMPILER=1";
    cc_params[cc_par_cnt++] = "-DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION=1";
}
```

### 1-3. afl-as.c — 어셈블리 파싱 및 계측 삽입

`afl-as`는 gcc가 생성한 `.s` 파일을 읽으면서 **기본 블록(Basic Block)의 시작 지점**을 감지해 계측 코드를 삽입한다.

삽입 조건은 두 가지다.

```c
// afl-as.c — add_instrumentation()

// 조건 1: 조건부 분기 명령어 (j로 시작하되 jmp는 제외)
if (line[1] == 'j' && line[2] != 'm' && R(100) < inst_ratio)
    fprintf(outf, trampoline_fmt_64, R(MAP_SIZE));

// 조건 2: 라벨 다음 첫 명령어 (새 기본 블록 시작)
if (instrument_next && line[0] == '\t' && isalpha(line[1]))
    fprintf(outf, trampoline_fmt_64, R(MAP_SIZE));
```

- `R(MAP_SIZE)`는 `random() % MAP_SIZE` — 각 기본 블록에 **컴파일 타임 랜덤 ID**를 배정한다.
- `.data`, `.bss` 섹션 / Intel syntax 블록 / `#APP`~`#NO_APP` 인라인 어셈블리는 계측을 건너뛴다.

### 1-4. afl-as.h — 삽입되는 어셈블리 (trampoline)

각 기본 블록 앞에 삽입되는 실제 어셈블리 코드다.

**32비트 trampoline:**

```asm
.align 4
leal -16(%%esp), %%esp
movl %%edi,  0(%%esp)    ; 레지스터 4개 저장 (edi/edx/ecx/eax)
movl %%edx,  4(%%esp)
movl %%ecx,  8(%%esp)
movl %%eax, 12(%%esp)
movl $0x%08x, %%ecx      ; ← R(MAP_SIZE) 값 = 이 블록의 ID
call __afl_maybe_log
movl 12(%%esp), %%eax    ; 레지스터 복원
movl  8(%%esp), %%ecx
movl  4(%%esp), %%edx
movl  0(%%esp), %%edi
leal 16(%%esp), %%esp
```

**64비트 trampoline:**

```asm
.align 4
leaq -(128+24)(%%rsp), %%rsp  ; 128 = x86-64 ABI 레드존, 24 = 레지스터 3개
movq %%rdx,  0(%%rsp)         ; rdx/rcx/rax 3개만 저장
movq %%rcx,  8(%%rsp)
movq %%rax, 16(%%rsp)
movq $0x%08x, %%rcx           ; 블록 ID → rcx
call __afl_maybe_log
movq 16(%%rsp), %%rax
movq  8(%%rsp), %%rcx
movq  0(%%rsp), %%rdx
leaq (128+24)(%%rsp), %%rsp
```

> **레드존(red zone)이란?**
> x86-64 ABI에서 `rsp` 아래 128바이트는 시그널 핸들러나 인터럽트가 건드리지 않는 영역이다. 계측 코드가 스택 포인터를 내리기 전에 이 영역을 보호해야 하기 때문에 `-(128+24)`를 빼는 것이다.

### 1-5. __afl_maybe_log — 실제 커버리지 기록

trampoline이 호출하는 함수. CPU 플래그를 보존하면서 비트맵을 업데이트한다.

```asm
__afl_maybe_log:
  lahf              ; CPU FLAGS 하위 8비트 → AH 저장
  seto %al          ; Overflow Flag → AL (lahf는 OF를 캡처 못함, 별도 처리)

  movl  __afl_area_ptr, %edx
  testl %edx, %edx
  je    __afl_setup   ; 공유 메모리 미초기화 시 설정 루틴으로

__afl_store:
  movl __afl_prev_loc, %edi
  xorl %ecx, %edi              ; edi = prev_loc XOR cur_loc (비트맵 인덱스)
  shrl $1, %ecx                ; ★ cur_loc >> 1
  movl %ecx, __afl_prev_loc    ; prev_loc = cur_loc >> 1 저장
  incb (%edx, %edi, 1)         ; trace_bits[prev_loc XOR cur_loc]++
```

**`shrl $1`이 핵심이다.**

시프트 없이 XOR만 쓰면 `A XOR B == B XOR A`라 A→B와 B→A 방향이 구분되지 않는다. `cur_loc`을 1비트 오른쪽으로 시프트한 뒤 `prev_loc`으로 저장하면 두 경로의 인덱스가 달라져 방향성이 보존된다. `A→A` 자기 루프도 `(A >> 1) XOR A != 0`으로 정상 처리된다.

---

## 2. Coverage — 커버리지 측정 방법

**목표:** 어떤 엣지(A→B 전이)를 밟았는지, 몇 번 밟았는지를 64KB 공유 메모리로 추적한다.

### 2-1. 공유 메모리 비트맵

```c
// config.h
#define MAP_SIZE_POW2   16
#define MAP_SIZE        (1 << MAP_SIZE_POW2)  // 65536 = 64KB
```

퍼저(`afl-fuzz`)와 타겟 바이너리가 `shmget()` / `shmat()`으로 이 64KB 배열을 공유한다. 타겟 실행 중 계측 코드가 직접 업데이트하고, 실행이 끝나면 퍼저가 읽어서 분석한다.

**64KB가 적당한 이유:**

| 분기 수 | 충돌 확률 | 대표 타겟 |
|---------|-----------|-----------|
| 1,000개 | 0.75% | giflib, lzo |
| 2,000개 | 1.5% | zlib, tar, xz |
| 5,000개 | 3.5% | libpng, libwebp |
| 10,000개 | 7% | libxml |
| 20,000개 | 14% | sqlite |

대부분의 타겟(2k~10k 분기)에서 충돌률이 낮으면서, L2 캐시에 들어갈 만큼 작아 비교 연산이 마이크로초 단위로 빠르다.

### 2-2. has_new_bits() — 새 커버리지 감지

```c
// afl-fuzz.c
static inline u8 has_new_bits(u8* virgin_map) {

#ifdef WORD_SIZE_64
    u64* current = (u64*)trace_bits;
    u64* virgin  = (u64*)virgin_map;
    u32  i = (MAP_SIZE >> 3);   // 65536 / 8 = 8192번 반복
#else
    u32* current = (u32*)trace_bits;
    u32* virgin  = (u32*)virgin_map;
    u32  i = (MAP_SIZE >> 2);
#endif

    u8 ret = 0;

    while (i--) {
        if (unlikely(*current) && unlikely(*current & *virgin)) {

            if (likely(ret < 2)) {
                u8* cur = (u8*)current;
                u8* vir = (u8*)virgin;

#ifdef WORD_SIZE_64
                // vir[n] == 0xff → 한 번도 밟힌 적 없는 엣지
                if ((cur[0] && vir[0] == 0xff) || (cur[1] && vir[1] == 0xff) ||
                    (cur[2] && vir[2] == 0xff) || (cur[3] && vir[3] == 0xff) ||
                    (cur[4] && vir[4] == 0xff) || (cur[5] && vir[5] == 0xff) ||
                    (cur[6] && vir[6] == 0xff) || (cur[7] && vir[7] == 0xff))
                    ret = 2;   // 진짜 새 경로
                else
                    ret = 1;   // 히트 카운트 버킷만 변화
#endif
            }

            *virgin &= ~*current;  // 방문한 비트 제거 (다음 비교 최적화)
        }
        current++;
        virgin++;
    }

    if (ret && virgin_map == virgin_bits) bitmap_changed = 1;
    return ret;
}
```

| 반환값 | 의미 | 처리 |
|--------|------|------|
| `0` | 변화 없음 | 버림 |
| `1` | 히트 카운트 버킷 변화 | 큐 추가 (낮은 우선순위) |
| `2` | 한 번도 밟은 적 없는 새 엣지 | 큐 추가 (높은 우선순위) |

- `unlikely()` 두 번 중첩: 대부분의 bitmap 슬롯이 0이라 브랜치 예측기에 힌트를 줘서 루프를 빠르게 돌린다.
- `*virgin &= ~*current`: 방문한 비트를 미리 제거해 다음 비교를 최적화한다.

### 2-3. 히트 카운트 버킷 — classify_counts()

단순히 밟았는가/안 밟았는가만 구분하면 정보가 너무 거칠다. AFL은 히트 카운트를 8개 버킷으로 분류한다.

```
실제 카운트: 1 | 2 | 3 | 4~7 | 8~15 | 16~31 | 32~127 | 128+
버킷값:      1 | 2 | 4 |  8  |  16  |  32   |   64   | 128
```

루프를 3번 도는 것과 7번 도는 것은 같은 버킷(4~7)이라 동일하게 취급한다. 3번 → 8번으로 바뀌면 버킷이 달라져 새로운 동작으로 감지한다. 오프-바이-원(off-by-one) 같은 미묘한 버그를 잡는 데 유효하다.

### 2-4. calibrate_case() — 새 seed 검증

새 seed를 큐에 추가하기 전에 반드시 거치는 검증 단계다.

```c
// afl-fuzz.c — calibrate_case()
static u8 calibrate_case(char** argv, struct queue_entry* q,
                         u8* use_mem, u32 handicap, u8 from_queue) {

    stage_max = fast_cal ? 3 : CAL_CYCLES;  // 기본 8번 실행

    for (stage_cur = 0; stage_cur < stage_max; stage_cur++) {

        write_to_testcase(use_mem, q->len);
        fault = run_target(argv, use_tmout);

        // 첫 실행에서 bitmap이 비어 있으면 계측이 안 된 것
        if (!dumb_mode && !stage_cur && !count_bytes(trace_bits)) {
            fault = FAULT_NOINST;
            goto abort_calibration;
        }

        cksum = hash32(trace_bits, MAP_SIZE, HASH_CONST);

        if (q->exec_cksum != cksum) {
            hnb = has_new_bits(virgin_bits);
            if (hnb > new_bits) new_bits = hnb;

            if (q->exec_cksum) {
                // 같은 입력인데 trace가 달라짐 → flaky input 감지
                for (i = 0; i < MAP_SIZE; i++) {
                    if (!var_bytes[i] && first_trace[i] != trace_bits[i]) {
                        var_bytes[i] = 1;
                        stage_max = CAL_CYCLES_LONG;  // 8회 → 40회로 확장
                    }
                }
                var_detected = 1;
            } else {
                q->exec_cksum = cksum;
                memcpy(first_trace, trace_bits, MAP_SIZE);
            }
        }
    }

    q->exec_us     = (stop_us - start_us) / stage_max;
    q->bitmap_size = count_bytes(trace_bits);
    update_bitmap_score(q);
}
```

같은 입력을 8번 실행해 trace가 달라지는 **flaky input**을 감지한다. flaky로 판정되면 40번으로 늘려 재관찰한다.

---

## 3. Fork Server — exec() 오버헤드 제거

**목표:** `execv()` 초기화 비용을 제거해서 초당 실행 횟수를 극대화한다.

### 3-1. 문제

매 테스트마다 `fork() + execv()`를 하면 다음 비용이 반복된다.

```
execv() 호출마다:
- 동적 라이브러리 로드 및 심볼 resolve
- C 런타임 초기화 (libc, global constructors)
- 프로그램 자체 초기화 코드
```

### 3-2. 해결 구조

타겟을 딱 **1번만** `execv()`로 실행한 뒤, 초기화된 상태에서 `fork()`만 반복한다.

```
[afl-fuzz]                          [fork server (타겟 내부)]
    │                                          │
    │── write(fd 199, prev_timed_out) ────────▶│ "실행해"
    │                                       fork()
    │◀── read(fd 198, child_pid) ────────────  │ 자식 PID 전달
    │                                  [자식: 실제 실행]
    │◀── read(fd 198, status) ──────────────   │ 종료 상태 전달
    │                                          │
    │── write(fd 199, ...) ───────────────────▶│ 다음 실행 ...
```

`FORKSRV_FD = 198`, `FORKSRV_FD + 1 = 199`로 고정이다.

### 3-3. init_forkserver() — 퍼저 측 초기화

```c
// afl-fuzz.c — init_forkserver()
EXP_ST void init_forkserver(char** argv) {

    int st_pipe[2], ctl_pipe[2];

    if (pipe(st_pipe) || pipe(ctl_pipe)) PFATAL("pipe() failed");

    forksrv_pid = fork();

    if (!forksrv_pid) {
        /* ── 자식 프로세스 (fork server가 될 프로세스) ── */

        // 파이프 재연결: ctl_pipe[0] → fd 198, st_pipe[1] → fd 199
        if (dup2(ctl_pipe[0], FORKSRV_FD) < 0)     PFATAL("dup2() failed");
        if (dup2(st_pipe[1],  FORKSRV_FD + 1) < 0) PFATAL("dup2() failed");

        // 심볼을 fork 전에 전부 resolve
        if (!getenv("LD_BIND_LAZY")) setenv("LD_BIND_NOW", "1", 0);

        setenv("ASAN_OPTIONS", "abort_on_error=1:detect_leaks=0:"
                               "symbolize=0:allocator_may_return_null=1", 0);

        execv(target_path, argv);  // 딱 1번
    }

    /* ── 부모 프로세스 (fuzzer) ── */
    close(ctl_pipe[0]); close(st_pipe[1]);
    fsrv_ctl_fd = ctl_pipe[1];
    fsrv_st_fd  = st_pipe[0];

    // 핸드셰이크: fork server 준비되면 4바이트 수신
    rlen = read(fsrv_st_fd, &status, 4);
    if (rlen == 4) { OKF("All right - fork server is up."); return; }
}
```

`LD_BIND_NOW=1`을 세팅하는 이유: 동적 라이브러리 심볼을 `fork()` **전에** 전부 resolve해두기 위해서다. 이후 fork된 자식들은 이미 resolve된 상태를 그대로 복사하므로 lazy binding 오버헤드가 없다.

### 3-4. __afl_forkserver — 타겟 내부 루프

Fork Server 코드는 `afl-as.h`에 의해 **타겟 바이너리 안에 직접 삽입**된다.

```asm
__afl_forkserver:
  pushl %eax / pushl %ecx / pushl %edx

  ; 준비 완료 신호 → fuzzer에게 4바이트 write
  pushl $4 / pushl $__afl_temp / pushl $FORKSRV_FD+1
  call  write
  addl  $12, %esp
  cmpl  $4, %eax
  jne   __afl_fork_resume   ; ★ write 실패 → 단독 실행 모드 폴백

__afl_fork_wait_loop:
  ; fuzzer로부터 "실행해" 신호 대기
  pushl $4 / pushl $__afl_temp / pushl $FORKSRV_FD
  call  read
  addl  $12, %esp
  cmpl  $4, %eax
  jne   __afl_die

  call fork

  cmpl $0, %eax
  jl   __afl_die
  je   __afl_fork_resume    ; 자식: 실제 실행으로

  ; 부모: 자식 PID 전송 후 종료 대기
  movl  %eax, __afl_fork_pid
  pushl $4 / pushl $__afl_fork_pid / pushl $FORKSRV_FD+1
  call  write / addl $12, %esp

  pushl $0 / pushl $__afl_temp / pushl __afl_fork_pid
  call  waitpid / addl $12, %esp

  pushl $4 / pushl $__afl_temp / pushl $FORKSRV_FD+1
  call  write / addl $12, %esp
  jmp __afl_fork_wait_loop

__afl_fork_resume:
  ; 자식: fd 198, 199 닫고 실제 실행
  pushl $FORKSRV_FD   / call close
  pushl $FORKSRV_FD+1 / call close
  addl  $8, %esp
  popl %edx / popl %ecx / popl %eax
  jmp  __afl_store
```

**폴백 동작:** `write` 실패 시 `__afl_fork_resume`으로 점프한다. 계측된 바이너리를 afl-fuzz 없이 단독 실행해도 정상 동작하는 이유가 이것이다.

### 3-5. run_target() — 매 테스트마다 일어나는 일

```c
// afl-fuzz.c — run_target()
static u8 run_target(char** argv, u32 timeout) {

    memset(trace_bits, 0, MAP_SIZE);  // 실행 전 bitmap 초기화
    MEM_BARRIER();                    // 컴파일러 재배치 방지

    // fork server에 4바이트 write → "실행해" 신호
    if ((res = write(fsrv_ctl_fd, &prev_timed_out, 4)) != 4)
        RPFATAL(res, "Unable to request new process from fork server (OOM?)");

    // 자식 PID 수신
    if ((res = read(fsrv_st_fd, &child_pid, 4)) != 4)
        RPFATAL(res, "Unable to request new process from fork server (OOM?)");

    // SIGALRM으로 타임아웃 설정
    it.it_value.tv_sec  = (timeout / 1000);
    it.it_value.tv_usec = (timeout % 1000) * 1000;
    setitimer(ITIMER_REAL, &it, NULL);

    // 자식 종료 상태 수신
    read(fsrv_st_fd, &status, 4);

    MEM_BARRIER();
    classify_counts((u64*)trace_bits);  // 히트 카운트 → 버킷 변환

    if (WIFSIGNALED(status)) {
        kill_signal = WTERMSIG(status);
        if (child_timed_out && kill_signal == SIGKILL) return FAULT_TMOUT;
        return FAULT_CRASH;
    }
    return FAULT_NONE;
}
```

`prev_timed_out`을 신호로 보내는 이유: fork server가 이전 실행이 타임아웃으로 kill됐는지 알아야 하기 때문이다.

---

## 4. Mutation — 입력 변이 전략

**목표:** 기존 seed를 변이시켜 새로운 경로를 탐색하는 입력을 만든다.

**실행 순서:** Deterministic(결정론적) → Havoc(비결정론적) → Splice(접합)

### 4-1. Deterministic 단계

처음 seed를 처리할 때 한 번씩 체계적으로 실행된다. 재현 가능하고, 모든 위치를 빠짐없이 건드린다.

#### FLIP_BIT 매크로

```c
// afl-fuzz.c
#define FLIP_BIT(_ar, _b) do { \
    u8* _arf = (u8*)(_ar); \
    u32 _bf = (_b); \
    _arf[(_bf) >> 3] ^= (128 >> ((_bf) & 7)); \
  } while (0)
```

`_b >> 3`으로 바이트 위치, `_b & 7`로 비트 위치를 계산한다. bitflip stage와 havoc stage 모두에서 사용된다.

#### Interesting Values

```c
// config.h
static s8  interesting_8[]  = { -128, -1, 0, 1, 16, 32, 64, 100, 127 };
static s16 interesting_16[] = { -32768, -129, 128, 255, 256, 512,
                                  1000, 1024, 4096, 32767 };
static s32 interesting_32[] = { -2147483648LL, -100663046, -32769,
                                  32768, 65535, 65536,
                                  100663045, 2147483647 };
```

`-100663046`처럼 이상해 보이는 값은 특정 해시/체크섬 함수에서 취약한 동작을 유발하는 비트 패턴이다.

#### 중복 스킵 로직 — could_be_arith()

deterministic 단계에서 동일한 결과를 내는 변이는 자동으로 건너뛴다.

```c
// afl-fuzz.c — could_be_arith()
static u8 could_be_arith(u32 old_val, u32 new_val, u8 blen) {
    u32 i, ov = 0, nv = 0, diffs = 0;
    if (old_val == new_val) return 1;

    for (i = 0; i < blen; i++) {
        u8 a = old_val >> (8 * i),
           b = new_val >> (8 * i);
        if (a != b) { diffs++; ov = a; nv = b; }
    }

    // 1바이트만 바뀌었고 차이가 ARITH_MAX(35) 이내면 중복
    if (diffs == 1) {
        if ((u8)(ov - nv) <= ARITH_MAX ||
            (u8)(nv - ov) <= ARITH_MAX) return 1;
    }
    return 0;
}
```

`could_be_bitflip()`, `could_be_interest()`도 동일한 방식으로 중복을 제거한다.

### 4-2. Havoc 단계 — 랜덤 조합

결정론적 단계가 끝나면 **Havoc**로 진입한다. 위의 변이들을 무작위 순서로, 무작위 횟수로 중첩 적용한다.

```c
// afl-fuzz.c — fuzz_one() 내 havoc 루프
// 딕셔너리(extras)가 있으면 17가지, 없으면 15가지 중 랜덤 선택
switch (UR(15 + ((extras_cnt + a_extras_cnt) ? 2 : 0))) {

    case 0:  FLIP_BIT(out_buf, UR(temp_len << 3)); break;        // 랜덤 비트 뒤집기
    case 1:  out_buf[UR(temp_len)] =
               interesting_8[UR(sizeof(interesting_8))]; break;  // interesting_8 삽입
    case 2:  /* interesting_16 삽입 (LE/BE 랜덤) */
    case 3:  /* interesting_32 삽입 (LE/BE 랜덤) */
    case 4:  out_buf[UR(temp_len)] -= 1 + UR(ARITH_MAX); break;  // 빼기
    case 5:  out_buf[UR(temp_len)] += 1 + UR(ARITH_MAX); break;  // 더하기
    case 8:  out_buf[UR(temp_len)] = UR(256); break;             // 완전 랜덤 바이트
    case 12: /* 랜덤 블록 삭제 */
    case 13: /* 랜덤 블록 복제 삽입 */
    case 14: /* 딕셔너리 extras로 덮어쓰기 (extras 있을 때만) */
    case 15: /* 딕셔너리 extras 삽입         (extras 있을 때만) */
}
```

#### 블록 크기 결정 — choose_block_len()

```c
// afl-fuzz.c — choose_block_len()
static u32 choose_block_len(u32 limit) {
    u32 min_value, max_value;
    u32 rlim = MIN(queue_cycle, 3);

    if (!run_over10m) rlim = 1;  // 초반 10분: 작은 블록(최대 32바이트)만

    switch (UR(rlim)) {
        case 0:  min_value = 1;
                 max_value = HAVOC_BLK_SMALL;    // 32
                 break;
        case 1:  min_value = HAVOC_BLK_SMALL;    // 32
                 max_value = HAVOC_BLK_MEDIUM;   // 128
                 break;
        default:
                 if (UR(10)) {
                     min_value = HAVOC_BLK_MEDIUM;  // 128
                     max_value = HAVOC_BLK_LARGE;   // 1500
                 } else {
                     min_value = HAVOC_BLK_LARGE;   // 1500
                     max_value = HAVOC_BLK_XL;      // 32768
                 }
    }
    return min_value + UR(MIN(max_value, limit) - min_value + 1);
}
```

큐 사이클이 쌓일수록 더 큰 블록을 다룰 확률이 높아진다. 초반에는 작은 변이로 빠르게 커버리지를 넓히고, 이후 큰 변이로 깊이 탐색한다.

### 4-3. Seed 우선순위 — calculate_score()

모든 seed가 동등하게 처리되지 않는다. 점수가 havoc의 `stage_max`(반복 횟수)로 직결된다.

```c
// afl-fuzz.c — calculate_score()
static u32 calculate_score(struct queue_entry* q) {

    u32 perf_score = 100;

    // 실행 속도 기반
    if      (q->exec_us * 0.1  > avg_exec_us) perf_score = 10;
    else if (q->exec_us * 4    < avg_exec_us) perf_score = 300;
    else if (q->exec_us * 3    < avg_exec_us) perf_score = 200;
    else if (q->exec_us * 2    < avg_exec_us) perf_score = 150;

    // 비트맵 크기 기반 (커버리지가 넓을수록 우대)
    if      (q->bitmap_size * 0.3  > avg_bitmap_size) perf_score *= 3;
    else if (q->bitmap_size * 3    < avg_bitmap_size) perf_score *= 0.25;

    // 핸디캡 보정 (나중에 발견된 seed에 유리)
    if (q->handicap >= 4) { perf_score *= 4; q->handicap -= 4; }
    else if (q->handicap)  { perf_score *= 2; q->handicap--;    }

    // 큐 깊이 기반 (변이를 거쳐 만들어진 seed일수록 우대)
    switch (q->depth) {
        case 0 ... 3:   break;
        case 4 ... 7:   perf_score *= 2; break;
        case 8 ... 13:  perf_score *= 3; break;
        case 14 ... 25: perf_score *= 4; break;
        default:        perf_score *= 5;
    }

    if (perf_score > HAVOC_MAX_MULT * 100)
        perf_score = HAVOC_MAX_MULT * 100;

    return perf_score;
}
```

**빠르고, 커버리지가 넓고, 깊이 있는 seed일수록 더 많이 변이된다.**

---

## 5. 전체 흐름 종합

```
━━━━━━━━━━━━━━━━━━━━ 컴파일 타임 ━━━━━━━━━━━━━━━━━━━━━━

소스코드
  └→ [afl-gcc]  (-B as_path, -no-integrated-as)
       └→ gcc로 .s 파일 생성
       └→ [afl-as]  add_instrumentation()
              └→ 각 기본 블록 앞: trampoline 삽입
                   leaq -(152)(rsp) → movq rcx, $블록ID → call __afl_maybe_log
                     └→ lahf + seto → XOR → shrl $1 → incb trace_bits[prev^cur]

━━━━━━━━━━━━━━━━━━━━ 실행 타임 ━━━━━━━━━━━━━━━━━━━━━━━━

[afl-fuzz 시작]
  └→ shmget() / shmat()  : 64KB 공유 메모리 생성
  └→ init_forkserver()   : 파이프 2개 생성, 타겟 최초 1회 execv()
       └→ LD_BIND_NOW=1  : 심볼 사전 resolve
       └→ fork server 루프 대기

메인 퍼징 루프 — fuzz_one():
  │
  ├─ 1. calculate_score(q) → perf_score → stage_max 결정
  │       실행속도 / 비트맵 크기 / 핸디캡 / 큐 깊이 반영
  │
  ├─ 2. Deterministic 변이
  │       bitflip → arithmetic(±35) → interesting values → extras
  │       could_be_*() 함수로 중복 결과 자동 스킵
  │
  ├─ 3. Havoc: switch(UR(15 or 17)) × stage_max 회
  │       choose_block_len()으로 블록 크기 동적 결정
  │
  ├─ 4. run_target() 호출
  │       write(fsrv_ctl_fd, 4) → fork()
  │       자식: __afl_fork_resume → trace_bits 업데이트
  │       classify_counts(trace_bits) → 히트 카운트 버킷 변환
  │
  ├─ 5. has_new_bits(virgin_bits) 분석
  │       ret 0 → 버림
  │       ret 1 → 큐 추가 (히트 버킷 변화)
  │       ret 2 → calibrate_case() → 큐 추가 (새 엣지)
  │                └→ 8회 실행, flaky 감지 시 40회로 확장
  │
  └─ 6. Splice: 다른 seed와 합치기 후 Havoc 재적용
```

### 실제 코드에서 확인한 핵심 포인트

| 항목 | 실제 코드 |
|------|-----------|
| `prev_loc` 저장 | `cur_loc` 그대로가 아니라 **`cur_loc >> 1`** (`shrl $1`) |
| 플래그 보존 | `lahf`만이 아니라 **`lahf` + `seto %al`** (Overflow Flag 별도 처리) |
| fork server 폴백 | write 실패 시 **`__afl_fork_resume`으로 자동 폴백** → 단독 실행 가능 |
| 중복 스킵 | `could_be_bitflip/arith/interest()`로 동일 결과 변이 **자동 생략** |
| havoc case 수 | 항상 15개가 아니라 **딕셔너리 유무에 따라 15 또는 17개** |
| 블록 크기 | 고정이 아니라 **큐 사이클 + 10분 기준으로 동적 결정** |
| flaky input | calibrate_case()에서 8번 → **40번으로 자동 확장** 후 재관찰 |

---

## 참고 자료

- [google/AFL — GitHub](https://github.com/google/AFL)
- [afl-fuzz.c](https://github.com/google/AFL/blob/master/afl-fuzz.c) — has_new_bits, run_target, init_forkserver, fuzz_one
- [afl-as.h](https://github.com/google/AFL/blob/master/afl-as.h) — trampoline, __afl_maybe_log, __afl_forkserver
- [afl-as.c](https://github.com/google/AFL/blob/master/afl-as.c) — add_instrumentation
- [afl-gcc.c](https://github.com/google/AFL/blob/master/afl-gcc.c) — edit_params, find_as
- [config.h](https://github.com/google/AFL/blob/master/config.h) — MAP_SIZE, ARITH_MAX, interesting values, FORKSRV_FD
- [technical_details.txt](https://github.com/google/AFL/blob/master/docs/technical_details.txt) — 작성자 Michal Zalewski의 공식 내부 문서
