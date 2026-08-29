---
layout: post
title: "Android Security Concept Atlas C04 | 가상 실습 보고서 — 프로세스·가상메모리·시스템 콜, 모든 격리가 딛고 선 밑변"
date: 2026-09-12 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Process, VirtualMemory, Syscall, mm_struct, taskstruct, fork, exec, clone, vDSO, seccomp, ConceptAtlas, 학습기록]
excerpt: "Android 앱은 특별한 무언가가 아니라 평범한 Linux 프로세스입니다 - 주소공간(mm_struct) 하나 + 스레드(task_struct) 여럿, EL0에서 도는. 그리고 앱 간 격리는 커널이 매번 검사하는 소프트웨어 장치가 아니라, 프로세스마다 다른 페이지 테이블(TTBR0_EL1)을 MMU가 걷는 하드웨어입니다. 시스템 콜은 SVC 한 방으로 EL0→EL1을 넘고(x8=번호, x0-x5=인자), fork는 COW 복제, exec는 이미지 교체 - zygote는 그 fork를 exec 없이 씁니다. C05·C09·C12·C34가 전부 이 위에 서 있는, Atlas의 밑변 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `id`, `cat /proc/self/attr/current`, `/proc/self/status`, `uname -a` |
| 관측 결과 | 앱 UID 10174, `untrusted_app` 도메인, `CapEff=0`, `Seccomp=2`, Linux 5.15 커널을 확인했다. |
| 검증 한계 | AVD가 x86_64이므로 ARM64 EL·PAC·BTI·MTE는 런타임 관측 대신 공개 소스 경로로 판정한다. |

![C04 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C04 — 프로세스·가상메모리·시스템 콜
> **계층**: Tier 0 (보안·시스템 기초) · **난이도**: 기초 · **선수 개념**: 없음(밑변)
> **성격**: 공식 문서·공개 소스 기준 재검토 — 다만 경험 많은 독자를 위한 압축 리프레셔.

C05에서 EL0/EL1을 다뤘고, C09에서 UID 샌드박스를, C34에서 ioctl(=시스템 콜)을 다룹니다. 그 셋이 전부 **"프로세스가 주소공간을 갖고 EL0에서 돌며 SVC로 커널을 부른다"**는 이 밑변 위에 서 있습니다.

한 문장으로: **Android 앱은 평범한 Linux 프로세스(주소공간 mm_struct + 스레드 task_struct, EL0)이고, 격리의 실체는 프로세스별 페이지 테이블을 걷는 하드웨어 MMU이며, 커널 요청은 SVC로 EL0→EL1을 넘는 시스템 콜이다.**

## 배경 개념 - 세 축

- **프로세스**: 주소공간(`mm_struct`) + 하나 이상의 스레드(`task_struct`).
- **가상메모리**: 프로세스별 페이지 테이블 → MMU가 VA→PA 변환, 데맨드 페이징·COW.
- **시스템 콜**: `SVC #0`로 EL0→EL1, `x8`=번호, `x0-x5`=인자, `x0`=반환.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**모든 것의 밑변**입니다. Android 앱은 특별한 커널 객체가 아니라 평범한 Linux 프로세스이고, 그 위에 UID(C09)·SELinux(C23)·seccomp가 정책으로 얹힙니다. C05(EL0/EL1), C09(UID 격리), C12(zygote fork), C33(ELF 세그먼트가 VA 영역에 매핑), C34(ioctl=시스템 콜)가 전부 이 개념을 전제합니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **프로세스 vs 스레드**: 스케줄러에겐 둘 다 `task_struct`입니다. 차이는 **mm(주소공간)을 공유하느냐**뿐. 스레드 = `mm_struct`를 공유하는 task.
- **clone()이 밑에**: `fork()`·`pthread_create()` 둘 다 `clone()/clone3()`로 귀결. `fork` = `SIGCHLD`만(주소공간 복사), 스레드 = `CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_THREAD|CLONE_SETTLS`(mm·fd·시그널 공유). (단 `pthread_create`는 플래그 선택만이 아니라 스레드 스택·TLS 설정도 함.)
- **fork vs exec**: `fork()` = **COW 복제**(새 pid, 페이지 읽기전용 공유→쓰기 시 사본). `execve()` = **이미지 교체**(pid 유지, 새 mm 구축·옛 주소공간 파괴). 고전 관용구 = `fork` 후 자식에서 `exec`.
- 전부 **EL0**(유저스페이스).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **격리의 실체 = 하드웨어 MMU**: 커널이 접근마다 소프트웨어로 검사하는 게 아니라, **프로세스마다 다른 페이지 테이블**(arm64: 유저 하위 절반은 `TTBR0_EL1`, 커널 상위 절반은 `TTBR1_EL1`, 주소 최상위 비트로 둘을 선택)을 MMU가 걸어 VA→PA를 변환합니다. 페이지가 없으면 폴트→데맨드 페이징, 공유 읽기전용 페이지에 쓰면→COW.
- **신뢰하면 안 되는 것들**:
  - **"vDSO가 getcpu도 무-트랩으로 처리한다"** — arm64 vDSO의 무-트랩은 **시간 함수 3개**(`clock_gettime`/`gettimeofday`/`clock_getres`)뿐입니다. `getcpu` 무-트랩은 **x86-64** 얘기고, arm64에선 진짜 SVC를 탑니다. vDSO의 `__kernel_rt_sigreturn`도 무-트랩이 아니라 **시그널 복귀 트램폴린**(몸통이 `mov x8, #__NR_rt_sigreturn; svc #0`)이라 SVC를 탑니다.
  - **"arm64 유저 VA는 항상 48비트"** — **39비트**(3-level, 512 GiB 유저 절반, 4KiB)가 Android에서 오래 흔했고, 48비트는 신형/대용량 기기입니다. VA 폭은 `CONFIG_ARM64_VA_BITS` 빌드 선택이며 **페이지 크기와 무관**(48·39 둘 다 4KiB) — 52비트만 예외(pre-LPA2는 64KiB 필요, LPA2는 4/16KiB로).
  - **"fork가 새 프로그램을 로드한다 / exec가 프로세스를 만든다"** — 서로 직교입니다. fork는 로드 안 하고, exec는 프로세스를 안 만들고 성공 시 반환 안 함.
  - **"VSZ = 실제 메모리"** — 데맨드 페이징·COW 때문에 RSS≠VSZ. `smaps`의 Private_Dirty를 봐야 합니다.

## 질문 4 — 입력과 출력은 무엇인가

- **시스템 콜** = EL0가 커널(EL1) 서비스를 요청하는 통로. arm64: `x8`에 번호, `x0-x5`에 인자(최대 6), `SVC #0` → `VBAR_EL1`의 동기 예외 벡터(`el0_svc`)로 트랩, 커널이 `sys_call_table[x8]` 디스패치, `x0`에 반환(`[-4095,-1]`이면 `-errno`를 bionic 래퍼가 errno로 바꾸고 -1 반환). (x86-64와 다름: `syscall` 명령, 번호 rax, 인자 rdi/rsi/rdx/r10/r8/r9.)
- **bionic**이 유저스페이스 래퍼. **seccomp-bpf**가 진짜 진입 경로에서 `{번호, arch, ip, args}`를 보고(포인터는 역참조 안 함) 허용/거부/트랩/kill.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **SIGSEGV** = 프로세스가 **매핑 안 된/권한 없는 VA**를 건드린 것(유효 VMA 없음 or 권한 불일치) — 내가 연구하는 메모리 손상 버그의 raw 신호입니다. (dmesg의 "error 4/6/7" 숫자는 **x86 포맷**이고, arm64는 읽기/쓰기를 `ESR_EL1.WnR`에 담아 다른 메시지로 냅니다.)
- **fork COW vs 스레드 공유 mm**: 스레드는 mm을 공유하므로 한 스레드의 **UAF·힙 그루밍이 다른 스레드에 그대로 보입니다**. fork 자식은 COW로 분리됩니다 — 익스플로잇에서 "포크 너머" vs "스레드 간"을 가르는 핵심.

## 질문 6 — Android 버전/아키텍처에 따라 무엇이 달라졌는가

- **VA 폭**: 39/48/52비트가 `CONFIG_ARM64_VA_BITS` 선택. 52비트는 ARMv8.2-LVA(64KiB) 또는 LPA2(ARMv9.2, 4/16KiB).
- **seccomp**: 앱/시스템/글로벌 정책(`bionic/libc/seccomp`의 `app_arm64_policy` 등)이 **zygote 특화**(SpecializeCommon → SetUpSeccompFilter) 시 자식에 설치 — 앱 코드 실행 전.
- **메모리 압박**: 클래식 스왑 대신 **LMKD**가 압박 시 프로세스를 죽임.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `/proc/<pid>/maps`(VMA별 주소·권한 r-x/rw-·백킹 파일 = text/data/heap/stack/mmap 라이브 뷰), `/proc/<pid>/smaps`(Rss/Pss/Shared/Private_Dirty — zygote COW 귀속), `/proc/<pid>/status`(UID/GID·스레드·VmRSS).
- `ps -A -T`(스레드), `strace`/`simpleperf`/`ftrace`(시스템 콜), `dmesg`(OOM/segfault).
- **소스**: 커널 `kernel/fork.c`·`arch/arm64/kernel/{entry.S,syscall.c}`, `bionic/libc/seccomp`.

**주의**: 프로세스·시스템 콜은 아키텍처 무관 개념이라 **에뮬레이터로도 `/proc`·strace 실측 가능**(단 x86 AVD는 SVC가 아니라 x86 syscall 명령).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C05(EL·메모리 보호)**: EL0/EL1 경계와 TTBR0/TTBR1이 바로 이 프로세스 격리의 하드웨어.
- **C09(UID 샌드박스)**: DAC UID 격리가 이 프로세스 모델 위에 얹힙니다 — 다음 편.
- **C12(zygote)**: fork-without-exec COW 모델의 핵심.
- **C33(ELF·링커)**: ELF 세그먼트가 이 VA 영역(text/data)에 매핑됩니다.
- **C34(ioctl)**: ioctl은 결국 이 시스템 콜 경로.
- 다음은 이 프로세스에 정체성을 부여하는 **C09(UID·샌드박스)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 프로세스·주소공간·시스템 콜 ]

  fork() = clone(SIGCHLD)          exec() = 이미지 교체(pid 유지)
     └ COW 복제(새 pid, 새 mm)        └ 새 mm 구축, 옛 주소공간 파괴
  스레드 = clone(CLONE_VM|...THREAD) = 같은 mm 공유

  프로세스 주소공간(EL0, 낮은 절반, TTBR0_EL1):
    [text r-x][rodata r--][data/bss rw-][heap ↑][mmap: libs/anon][stack ↓]
        │  MMU가 프로세스별 페이지테이블을 걸어 VA→PA (격리의 실체)
        ▼
  시스템 콜:  x8=번호, x0-x5=인자 → SVC #0 ──trap──▶ EL1
        el0_svc → sys_call_table[x8] → 반환 x0([-4095,-1]=-errno)
        (seccomp-bpf가 이 진입에서 필터 / vDSO 시간3함수는 무-트랩)
```

## 오개념 판별 문제 5개

1. "프로세스와 스레드는 커널에서 서로 다른 종류의 객체다."
2. "fork()는 새 프로그램을 메모리에 로드하고, exec()는 새 프로세스를 만든다."
3. "arm64 Android 유저 가상주소는 항상 48비트다."
4. "arm64 vDSO는 getcpu와 rt_sigreturn을 트랩 없이 유저스페이스에서 처리한다."
5. "앱 간 격리는 커널이 매 메모리 접근마다 UID를 소프트웨어로 검사해 이뤄진다."

<details><summary>판정 기준(펼치기)</summary>

1. 둘 다 `task_struct`입니다. 차이는 **mm 공유 여부**뿐 — 스레드는 mm을 공유하는 task.
2. 정반대로 직교입니다. fork = COW 복제(로드 안 함, 새 pid), exec = 이미지 교체(프로세스 안 만듦, pid 유지·성공 시 반환 없음).
3. **39비트가 오래 흔했고**(3-level, 512GiB), 48비트는 신형입니다. `CONFIG_ARM64_VA_BITS` 선택이며 페이지 크기와 무관(52비트만 예외).
4. arm64 무-트랩은 **시간 3함수뿐**. getcpu는 x86-64 전용, rt_sigreturn은 트램폴린이라 SVC를 탑니다.
5. **하드웨어 MMU**가 프로세스별 페이지 테이블을 걸어 격리합니다. UID DAC(C09)는 그 위의 파일 접근 정책이지 매 메모리 접근 검사가 아닙니다.
</details>

## 서술형 문제 3개

1. `fork()`(COW)·`execve()`(교체)·`clone()`(스레드=mm 공유)의 차이를, zygote가 왜 fork를 exec 없이 쓰는지와 함께 서술하세요.
2. arm64에서 시스템 콜이 EL0→EL1을 넘는 경로(x8/x0-x5, SVC, sys_call_table, x0/-errno)를 서술하고, seccomp와 vDSO가 그 경로를 각각 어떻게 바꾸는지 설명하세요.
3. 앱 간 격리가 "소프트웨어 검사"가 아니라 "프로세스별 페이지 테이블 + MMU"라는 하드웨어임을 서술하고, 이것이 C05·C09와 어떻게 이어지는지 쓰세요.

## 소스·정적 검증 경로

- 임의 앱의 `/proc/<pid>/maps`를 떠서 text/lib/heap/stack/anon 영역과 권한(r-x/rw-)을 분류하고, `smaps`로 zygote와 COW-공유된 클린 페이지를 식별하세요.
- `strace`로 앱이 아닌 셸 바이너리 하나의 시스템 콜을 떠서 `SVC` 번호(x8)와 인자를 관찰하고, seccomp에 막히는 호출이 있는지 확인하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **주소공간 실측**: `/proc/<pid>/maps`·`smaps`로 VA 영역과 COW 공유를 캡처.
2. **시스템 콜 실측**: `strace`/`simpleperf`로 SVC 경로를.
3. **격리 서술**: 두 앱의 서로 다른 UID·서로 다른 주소공간을 근거로, MMU 격리와 UID DAC(C09)를 구분해 서술.
4. **연결**: SIGSEGV 하나를 유발해(예: 잘못된 포인터) 매핑 안 된 VA 접근이 신호로 이어지는 걸 확인.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

Android 앱은 평범한 Linux 프로세스입니다 — 주소공간(mm_struct) 하나에 스레드(task_struct) 여럿, EL0에서 돌며, `SVC`로 커널을 부르는. 격리는 커널이 매번 검사하는 소프트웨어가 아니라 **프로세스별 페이지 테이블을 걷는 MMU**라는 하드웨어이고, fork는 COW 복제·exec는 이미지 교체이며(zygote는 fork를 exec 없이 씀), 시스템 콜은 `x8`=번호·`SVC`로 EL0→EL1을 넘습니다. 이 밑변 위에 C05(EL)·C09(UID)·C12(zygote)·C34(ioctl)가 전부 서 있습니다. 다음은 이 프로세스에 **정체성(UID)**을 부여해 샌드박스를 만드는 **C09**로 이어집니다.
