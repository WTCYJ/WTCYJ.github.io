---
layout: post
title: "Android Security Concept Atlas C34 | 가상 실습 보고서 — ioctl과 device node, 앱이 커널에 명령하는 채널"
date: 2026-09-08 21:00:00 +0900
category: 블로그/기술문서
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

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "`ioctl`의 request가 `_IOR`이면 커널이 그 크기만큼 유저→커널로 데이터를 복사해준다."
2. "커널은 ioctl argp 구조체의 형식을 알고 검증한다."
3. "device node는 major 번호 하나로 드라이버가 정해진다."
4. "PAN이 켜져 있으면 드라이버의 ioctl은 메모리 안전하다."
5. "`isolated_app`(WebView 렌더러)도 GPU 노드를 열 수 있다."

<details><summary>판정 기준(펼치기)</summary>

1. request의 방향·크기는 **자문 메타데이터**입니다. 커널은 대신 복사해주지 않고, 드라이버가 `copy_from_user`하고 크기를 **직접 검증**해야 합니다.
2. 모릅니다. ioctl은 **드라이버별 불투명 RPC**로, 커널은 request와 argp를 넘길 뿐입니다.
3. **(major,minor)** 쌍입니다. 특히 `/dev/binder`는 공유 major 10(misc)에서 **minor**로 드라이버가 정해집니다.
4. PAN은 EL1이 EL0 포인터를 **직접 역참조**하는 것만 막습니다. 검증 안 된 size·정수 오버플로·박힌 포인터·TOCTOU·UAF 같은 **로직 버그**는 그대로 드라이버 책임입니다.
5. `isolated_app`은 가장 잠긴 도메인이라 GPU 노드를 **못 엽니다**. GPU 노드를 여는 건 `untrusted_app`입니다(렌더링).
</details>

## 서술형 문제 3개

1. ioctl이 왜 "불투명한 드라이버 RPC"이고, 그래서 왜 request의 크기 필드가 자문일 뿐 강제가 아닌지 서술하세요.
2. GPU 드라이버가 왜 유독 앱 도달 가능한 EL0→EL1 표적인지(렌더링·untrusted_app 접근·복잡도)와, `isolated_app`과의 차이를 서술하세요.
3. PAN이 막는 것과 막지 못하는 것을 구분하고, 그래서 왜 드라이버 저자가 여전히 모든 size/bounds/포인터 검사를 책임지는지 서술하세요.

## 소스·정적 검증 경로

- Android Emulator/Cuttlefish에서 `ls -l /dev`와 `ls -Z /dev`로 가상 character/block device, major/minor와 SELinux type을 확인하세요. OEM GPU node를 가정하지 말고 실제로 제공된 goldfish/virtio/binder device만 기록합니다.
- 앱 프로세스를 `strace`(가능하면)해 `ioctl(fd, 0x…, …)`의 인코딩된 request를 관측하고, 매크로(`_IOWR('b',1,…)`)로 디코딩하세요.
- 커널 `security/selinux/hooks.c`의 `ioctl_has_perm`에서 xperm이 어느 비트로 필터하는지 한 곳 인용하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **노드 실측**: `ls -l /dev`·`ls -Z /dev`·`cat /proc/devices`로 문자 장치·major/minor·SELinux 타입을 캡처.
2. **ioctl 관측**: `strace`로 실제 ioctl request를 잡아 인코딩을 디코딩.
3. **표면 서술**: GPU 노드가 왜 `untrusted_app`에 열려 있고 그것이 왜 위험한지를 `ls -Z`와 sepolicy로.
4. **연결**: C17(Binder=ioctl)과 CVE 시리즈(EL0 버그의 EL1 상승)를 이 채널로 엮기.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

`ioctl`은 `read`/`write`로 표현 못 하는 것을 위한 드라이버의 만능 명령 채널이고, 커널은 그 인자의 뜻을 모른 채 드라이버에 넘깁니다. 그래서 각 드라이버 핸들러가 공격자 입력을 EL1에서 파싱하는 최대 로컬 커널 공격 표면이 되고, 렌더링 때문에 평범한 앱조차 여는 GPU 드라이버(Mali kbase·Qualcomm KGSL)가 EL0→EL1 상승의 주 표적입니다. C17의 Binder도, 제 CVE 시리즈의 EL0 버그가 커널로 올라가는 그 단계도 전부 이 채널을 지납니다. 다음은 그 벤더 드라이버들이 왜 Android 최대 실전 공격 표면인지의 **C36(벤더 드라이버·HAL 공격 표면)**, 또는 그 커널 표면을 줄이는 **C35(GKI·KMI)**로 이어집니다.
