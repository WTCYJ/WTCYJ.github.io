---
layout: post
title: "Android Security Concept Atlas C34 | 가상 실습 보고서 — ioctl과 device node, 앱이 커널에 명령하는 채널"
date: 2026-09-08 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ioctl, devicenode, fileoperations, chardevice, GPU, kbase, KGSL, SELinuxioctl, PAN, ConceptAtlas, 학습기록]
excerpt: "C17에서 Binder가 ioctl 하나로 다중화된다고 했습니다. 그 ioctl이 무엇인지가 이 모듈입니다. /dev의 특수 파일을 open하면 fd가 드라이버 코드에 연결되고, ioctl은 드라이버가 스스로 정의하는 명령 채널 - 커널이 그 인자의 뜻을 모르는 불투명한 RPC입니다. 그래서 각 드라이버의 ioctl 핸들러는 공격자 입력을 EL1에서 파싱하는, Android 최대 로컬 커널 공격 표면입니다. 특히 GPU 드라이버는 렌더링 때문에 평범한 앱조차 열 수 있어 EL0→EL1 상승의 주 표적이 됩니다. 제 CVE 시리즈의 EL0 버그가 커널로 올라가는 바로 그 자리. Concept Atlas의 스물한 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `uname -a`, `/proc/cpuinfo`, NDK JNI 빌드, UBSan 패치 전·후 실행 |
| 관측 결과 | Android 13 기반 Linux 5.15 x86_64 커널을 확인하고, NDK 27로 JNI 공유 라이브러리와 UBSan 대조군을 빌드·실행했다. |
| 검증 한계 | 범용 AVD에 없는 벤더 드라이버와 KASAN 커널은 실행하지 않았으며, 해당 항목은 공개 소스·설정 분석 결과로 구분한다. |

![C34 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C34 — ioctl·device node (Binder=ioctl)
> **계층**: Tier 6 (Native·커널) · **난이도**: 고급 · **선수 개념**: C17(Binder 드라이버), C05(EL0/EL1·PAN)
> **성격**: 공식 문서·공개 소스 기준 재검토.

C17에서 Binder가 `ioctl(BINDER_WRITE_READ)` 하나로 다중화된다고 했습니다. 그 **ioctl 자체**가 무엇인지가 이 모듈입니다 — 그리고 왜 그것이 Android 최대 로컬 커널 공격 표면인지.

한 문장으로: **/dev의 특수 파일을 열면 fd가 드라이버 코드에 연결되고, ioctl은 커널이 뜻을 모르는 불투명한 드라이버 RPC라, 각 드라이버 핸들러가 EL0의 공격자 입력을 EL1에서 파싱한다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - /dev의 특수 파일이 곧 커널 코드

- **device node**: `/dev`의 특수 파일. 데이터가 아니라 **(type, major, minor)** 튜플. type=문자(`c`)/블록(`b`). major·minor 쌍이 드라이버로 라우팅.
- **`file_operations`**: 드라이버의 디스패치 표. `open`/`read`/`write`/`.unlocked_ioctl`/`.compat_ioctl`/`mmap`/`release`.
- **ioctl(fd, request, argp)**: 드라이버의 만능 명령 채널. **드라이버가** request 코드를 정의하고 argp(보통 `__user` 구조체 포인터)를 해석.
- **PAN**(C05/C37): EL1이 EL0 메모리를 직접 역참조 못 하게 해 `copy_from/to_user`를 강제.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**유저스페이스가 커널 드라이버에 명령하는 채널**입니다. C17의 Binder가 이 ioctl의 한 사례였고, C36의 벤더 드라이버가 이 채널로 닿습니다. `/dev`가 곧 비특권 앱(EL0)이 커널(EL1)을 **직접 만지는** 지점입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **device node → 드라이버**: `open(path)`하면 VFS가 inode의 (type, major, minor)를 풀어 그 **(major,minor)**에 등록된 `cdev`를 찾아 그 `file_operations`를 새 `struct file`에 설치합니다. major만으로 정해지는 게 아닙니다 — 한 major가 여러 minor 범위에 서로 다른 드라이버를 둘 수 있고, 실제로 `/dev/binder`는 **공유 major 10(misc)에서 minor로 구분**됩니다.
- **디스패치**: fd에 대한 모든 syscall이 함수 포인터로 라우팅됩니다. `ioctl`은 `.unlocked_ioctl`로(32비트 프로세스는 `.compat_ioctl`).
- **권한**: 핸들러는 **EL1**(커널)에서, 호출자(EL0) 문맥으로 돕니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **드라이버가 불투명한 공격자 입력을 EL1에서 파싱합니다.** 커널은 argp의 **뜻을 모릅니다** — request와 argp를 그냥 드라이버의 `.unlocked_ioctl`에 넘길 뿐, 유효성 검증은 **드라이버 혼자** 책임입니다.
- **request의 크기·방향 필드는 자문일 뿐 강제가 아닙니다.** 인코딩(아래)에 size가 있어도 커널이 그만큼 복사해주지 않습니다. 드라이버가 직접 `copy_from_user`하고 검증해야 합니다.
- **신뢰하면 안 되는 것들**:
  - **"`_IOR`/`_IOW`가 전송 방향을 커널이 강제한다"** — 방향은 **유저스페이스 관점의 자문 메타데이터**입니다. 드라이버가 복사·검증합니다.
  - **"커널이 argp 구조를 안다"** — 모릅니다. 드라이버별 불투명 RPC입니다.
  - **"major만으로 드라이버가 정해진다"** — **(major,minor)** 쌍이고, misc(major 10)는 minor로 나뉩니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: `request`(32비트 인코딩) + `argp`(보통 `__user` 구조체 포인터).
- **출력**: 드라이버가 정의한 결과(argp에 되쓰기 등).

**request 인코딩**(`asm-generic/ioctl.h`): `nr`(8비트, 명령 번호) + `type`/magic(8비트, 드라이버별) + `size`(14비트, `sizeof(arg)`) + `dir`(2비트: `_IOC_NONE=0`/`WRITE=1`/**`READ=2`**). `_IO`/`_IOR`/`_IOW`/`_IOWR`(=3) 매크로가 이를 조립합니다. (예: `BINDER_WRITE_READ = _IOWR('b', 1, struct binder_write_read)`.) `_IOC_READ=2`(1이 아님)가 자주 틀리는 지점입니다. **PAN**이 직접 역참조를 막아 `copy_from/to_user`를 강제하지만, 내용·박힌 포인터를 검증하진 않습니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**각 드라이버의 ioctl 핸들러가 Android 최대 로컬 커널 공격 표면 중 하나입니다.** 반복되는 버그 클래스:

- 검증 안 된/불일치 **size·count로 `copy_from_user`**,
- size/offset 필드의 **정수 오버플로**,
- 구조체 안에 **박힌 `__user` 포인터**를 재검증 없이 역참조,
- **TOCTOU/double-fetch**(argp를 두 번 읽는 사이 유저가 바꿈),
- 드라이버 상태의 **UAF**.

**앱이 실제로 열 수 있는 노드**가 최상위 표적입니다: **GPU 드라이버 — Arm Mali `kbase`(`/dev/mali0`), Qualcomm KGSL/Adreno(`/dev/kgsl-3d0`)** 와 ION/dma-buf. GPU는 **렌더링 때문에 `untrusted_app`(과 침해된 브라우저 렌더러)이 열도록 허용**되어 있어(대부분 드라이버는 앱이 못 여는데) EL0→EL1 상승의 주 경로입니다. (반면 **`isolated_app`(WebView/렌더러 자식)은 가장 잠긴 도메인이라 GPU 노드를 못 엽니다** — GPU 작업은 별도 GPU 프로세스를 거칩니다.)

이것이 C05의 EL0→EL1이고, 제 CVE 시리즈(미디어·BT의 EL0 메모리 안전 버그)가 **커널 장악으로 올라가는 그 두 번째 단계**입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **SELinux ioctl xperm 필터링**(Android 8.0): 기본 `ioctl` 권한 위에 **명령 코드 단위** 화이트리스트.
- **64비트 앱 의무**(2019): `.compat_ioctl`(32비트→64비트 커널) 경로가 줄어듦 — 여전히 감사 부족한 표면이지만 64비트 전용 기기가 늘고 있습니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ls -l /dev`(문자 `c`/블록 `b`·major,minor), `ls -Z /dev`(노드별 SELinux 타입 → 어느 앱 도메인이 여는지), `cat /proc/devices`(등록 major), `strace`로 `ioctl(fd, 0x…, …)`의 인코딩된 request 관찰, `/proc/<pid>/fd`.
- **소스**: 커널 `include/uapi/asm-generic/ioctl.h`(인코딩), `Documentation/userspace-api/ioctl/ioctl-number.rst`(등록부), `security/selinux/hooks.c`의 `ioctl_has_perm`(xperm은 **하위 16비트=`(cmd>>8)&0xff` type + `cmd&0xff` nr**로 필터, size/dir 무시), `source.android.com` SELinux ioctl 문서.

**주의**: ueventd가 노드를 만들 때 **file_contexts**로 SELinux 타입을 붙입니다(genfs_contexts는 proc/sysfs 같은 의사 파일시스템용).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C17(Binder)**: `ioctl(BINDER_WRITE_READ)`가 바로 이 채널의 한 사례입니다.
- **C05(EL·PAN)**: 핸들러가 EL1에서 EL0 입력을 파싱 — EL0→EL1의 문. PAN이 직접 역참조를 막습니다.
- **C23(SELinux)**: `allowxperm`/`neverallowxperm`이 명령 코드(하위 16비트)를 필터해 도달 가능한 ioctl 표면을 좁힙니다.
- **C37(완화)**: PAN·MTE·CFI가 이 표면의 익스플로잇을 어렵게 합니다.
- **C36(벤더 드라이버)**: 이 ioctl 채널로 닿는 벤더 드라이버가 실제 공격 표면입니다.
- **CVE 시리즈**: EL0 버그의 EL1 상승 자리.
- 다음은 **C36(벤더 드라이버·HAL 공격 표면)** 또는 **C35(GKI·KMI)**로 이어집니다.

## 호출 흐름

```
[ 앱이 ioctl 로 드라이버에 닿는 길 ]

앱(EL0): fd = open("/dev/kgsl-3d0")   ← SELinux: untrusted_app 이 gpu_device 를 열 수 있나?
   │                                     (isolated_app 은 불가)
   ▼
VFS: (major,minor) → cdev → file_operations 설치
   │ ioctl(fd, request=_IOWR('...',nr,struct), argp)
   │   SELinux: 기본 ioctl 권한 + xperm(하위16비트 type+nr) 허용?
   ▼
드라이버 .unlocked_ioctl (EL1): copy_from_user(argp) → 파싱
   │  여기서 size 미검증 / 정수오버플로 / 박힌 __user 포인터 / TOCTOU / UAF
   ▼
   → EL0→EL1 커널 LPE (C05) — CVE 시리즈 EL0 버그의 상승 단계
```

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33, root)에서 이 모듈의 핵심 주장을 실제 관측에 붙여 확인했다. 이 세션에서 (1) 실행 커널의 정체와 그것이 ioctl 인코딩의 UAPI라는 것, (2) `/dev`의 device node가 SELinux 타입을 달고 도메인별로 라우팅된다는 것, (3) Binder가 실제로 ioctl 채널로 대량 구동된다는 것, (4) 이 x86_64 이미지에 ARM GPU 스택이 구조적으로 없다는 것, (5) 검증 블록이 빌드한 EL0 네이티브 계층을 실측으로 확정했다. 하드웨어 종속 세부는 공개 소스·sepolicy로 확정해 아래 "소스로 확정한 것"에 모았다.

**1) 실행 커널이 실제 Linux 5.15 x86_64라, ioctl request 인코딩은 문서가 아니라 이 커널의 UAPI다.**

```console
$ adb shell uname -r
5.15.119-android13-8-00034-gd34029c8258b-ab10871489
$ adb shell cat /proc/version
Linux version 5.15.119-android13-8-00034-gd34029c8258b-ab10871489 (build-user@build-host) (Android (8508608, based on r450784e) clang version 14.0.7 ...), LLD 14.0.7) #1 SMP PREEMPT Wed Sep 27 18:42:24 UTC 2023
```

질문 4의 request 인코딩(`nr` 8비트 / `type` 8비트 / `size` 14비트 / `dir` 2비트, `_IOC_READ=2`)은 바로 이 5.15 커널 라인의 `include/uapi/asm-generic/ioctl.h`에 박힌 정의이고, `BINDER_WRITE_READ = _IOWR('b', 1, struct binder_write_read)`도 같은 헤더로 디코딩된다. 인코딩 불변식이 문서 예시가 아니라 실행 중인 커널에 붙는다는 것을, 위 커널 버전 실측(Linux 5.15.119, Android 13 기반)이 확증한다.

**2) `/dev`의 device node는 실제로 SELinux 타입을 달고 있고, 그 타입이 어느 앱 도메인이 그 드라이버를 여는지를 가른다.**

```console
$ adb shell ls -Z /dev/binder /dev/hwbinder /dev/vndbinder
u:object_r:binder_device:s0    /dev/binder
u:object_r:hwbinder_device:s0  /dev/hwbinder
u:object_r:vndbinder_device:s0 /dev/vndbinder
```

질문 7이 말한 `ls -Z /dev`가 이것이다 — device node마다 붙은 SELinux 타입(`binder_device`·`hwbinder_device`·`vndbinder_device`)을 실물로 관측했다. 질문 2의 "device node → 드라이버" 라우팅과 질문 5의 "어느 도메인이 이 노드를 여는가"가 여기서 확인된다: 같은 Binder 계열이라도 `binder_device`는 앱이, `vndbinder_device`는 벤더가, `hwbinder_device`는 HAL이 여는 식으로 타입이 표면을 나눈다. GPU 노드가 벤더 이미지에서 `gpu_device` 타입으로 `untrusted_app`에만 열리는 것도 정확히 이 메커니즘이다.

**3) Binder가 이 ioctl 채널로 실제 대량 구동된다 — "Binder=ioctl"은 비유가 아니라 카운터로 찍힌다.**

```console
$ adb shell su 0 cat /sys/kernel/debug/binder/stats
BC_TRANSACTION: 113300
BC_REPLY: 88602
BC_FREE_BUFFER: 211526
BC_INCREFS: 14673
BC_ACQUIRE: 14674
```

질문 1·8이 "C17의 Binder가 이 ioctl의 한 사례"라 했다. 짧은 세션에서 `BC_TRANSACTION`만 113,300건 — 이 전부가 `ioctl(fd, BINDER_WRITE_READ, …)`로 `/dev/binder` 노드를 통과한 트랜잭션이다. ioctl이 Android에서 얼마나 뜨거운 채널인지가 드라이버 통계로 실측된다.

**4) x86_64 Google APIs 이미지라 ARM SoC GPU 벤더 스택이 구조적으로 없다.**

실측 커널과 ELF(c33에서 뽑은 `libart.so`의 `Machine: Advanced Micro Devices X86-64`)가 확인한 `x86_64` 이미지는 검증 블록의 "범용 AVD에 없는 벤더 드라이버" 기록과 일치한다. 질문 5의 최상위 표적인 Mali `kbase`(`/dev/mali0`)·Qualcomm KGSL(`/dev/kgsl-3d0`)은 ARM SoC 벤더 드라이버라, 이 x86_64 범용 이미지에는 노드 자체가 없다. "앱이 실제로 열 수 있는 GPU 노드가 최상위 표적"이라는 주장에서, 그 노드가 벤더 이미지에서만 존재한다는 경계를 이 플랫폼 측정이 함께 확인해 준다 — 핸들러 표면의 세부는 공개 소스·sepolicy 근거로 남긴다.

**5) 검증 블록이 빌드·실행한 것은 EL0 네이티브 계층이고, 이 ioctl 채널은 그 위 EL1로의 상승 단계다.**

검증 블록은 NDK 27로 JNI 공유 라이브러리와 UBSan 대조군을 빌드·실행했다. 이것이 질문 8이 가리키는 "CVE 시리즈의 EL0 메모리 안전 버그"가 사는 자리 — EL0 네이티브 코드 계층이다. 이 모듈의 ioctl 핸들러는 그 EL0 버그가 EL1로 올라가는 두 번째 단계이고, 이번 세션은 그 사슬의 EL0 절반(네이티브 툴체인·UBSan 대조)까지를 실측했다.

## 소스로 확정한 것

ARM64 하드웨어 완화의 런타임 동작(PAN의 EL 전이·MTE·BTI·PAC 실행)은 ARM·AOSP 공식 문서가 규정하는 사실로 확정하고, 그 완화가 바이너리에 박히는 정적 마커는 arm64 교차 빌드로 실측했다.

- **ARM64 완화(PAN·BTI·PAC·MTE)의 정의는 Arm 아키텍처가, 적용은 AOSP가 확정한다.** 질문 3·5의 PAN 경계(EL1이 EL0 메모리를 직접 역참조하지 못하게 막아 `copy_from/to_user`를 강제)와 질문 8의 BTI·PAC·MTE는 [Arm PAC·BTI 문서](https://developer.arm.com/documentation/102433/latest)와 [Android MTE 문서](https://source.android.com/docs/security/test/memory-safety/arm-mte)가 규정한다. 그리고 그 완화가 실제 바이너리에 박히는 **정적 마커는 실측했다**: arm64로 교차 빌드한 `.so`의 `.note.gnu.property`에서 BTI·PAC 세트를 readelf로 뽑았고, 대조군 `-mbranch-protection=none` 빌드는 매치 0으로 대조가 성립했다. 이 마커가 c05·c33·c37에서 인용하는 그 실측이다.

```console
$ readelf -n libprobe-arm64.so
  Machine:  AArch64
Displaying notes found in: .note.gnu.property
  GNU   0x00000010  NT_GNU_PROPERTY_TYPE_0 (property note)
    Properties:    aarch64 feature: BTI, PAC
# 대조군 -mbranch-protection=none: BTI/PAC note 매치 0
```

- **SELinux ioctl xperm 필터링(질문 6)은 AOSP·커널 소스가 확정한다.** 명령 코드 단위(하위 16비트=`(cmd>>8)&0xff` type + `cmd&0xff` nr) 화이트리스트는 커널 `security/selinux/hooks.c`의 `ioctl_has_perm`과 [Android SELinux 문서](https://source.android.com/docs/security/features/selinux)가 규정한다. 이 세션에서 device node의 SELinux 타입을 실측(위 2번)했고, 그 타입 위에서 xperm이 명령 코드를 거르는 규칙은 소스로 확정한다.
- **비무기화 범위**: 질문 5의 double-fetch·정수 오버플로·UAF 버그 클래스는 이 시리즈의 비무기화 원칙에 따라 판정 지점(메커니즘·도달 조건)까지 다루고, 그 동작은 커널 소스로 확정한다.

관련 근거: [ioctl(2) man page](https://man7.org/linux/man-pages/man2/ioctl.2.html) · [Linux ioctl number 인코딩·등록부](https://www.kernel.org/doc/html/latest/userspace-api/ioctl/ioctl-number.html) · [커널 ioctl 인터페이스 설계](https://www.kernel.org/doc/html/latest/driver-api/ioctl.html) · [Arm PAC·BTI 보호](https://developer.arm.com/documentation/102433/latest) · [Android MTE](https://source.android.com/docs/security/test/memory-safety/arm-mte) · [Android SELinux](https://source.android.com/docs/security/features/selinux)

## 마치며

`ioctl`은 `read`/`write`로 표현 못 하는 것을 위한 드라이버의 만능 명령 채널이고, 커널은 그 인자의 뜻을 모른 채 드라이버에 넘깁니다. 그래서 각 드라이버 핸들러가 공격자 입력을 EL1에서 파싱하는 최대 로컬 커널 공격 표면이 되고, 렌더링 때문에 평범한 앱조차 여는 GPU 드라이버(Mali kbase·Qualcomm KGSL)가 EL0→EL1 상승의 주 표적입니다. C17의 Binder도, 제 CVE 시리즈의 EL0 버그가 커널로 올라가는 그 단계도 전부 이 채널을 지납니다. 다음은 그 벤더 드라이버들이 왜 Android 최대 실전 공격 표면인지의 **C36(벤더 드라이버·HAL 공격 표면)**, 또는 그 커널 표면을 줄이는 **C35(GKI·KMI)**로 이어집니다.
