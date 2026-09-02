---
layout: post
title: "Android Security Concept Atlas C35 | 가상 실습 보고서 — Android Common Kernel·GKI·KMI, 커널의 제네릭 코어와 벤더 모듈"
date: 2026-08-29 23:33:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, GKI, KMI, AndroidCommonKernel, ACK, vendordlkm, vendorboot, KernelModule, PatchGap, ConceptAtlas, 학습기록]
excerpt: "예전에는 SoC 벤더마다 커널을 포크해 드라이버를 통째로 컴파일해 넣어, 기기마다 서로 다른 커널 바이너리 수천 개가 생겼습니다 - 이게 커널 보안 패치가 느린 구조적 원인이었죠. GKI는 그것을 프레임워크의 Treble처럼 갈랐습니다: Google이 만든 하나의 제네릭 코어 커널(boot.img)과, 벤더 드라이버를 뺀 로더블 모듈(.ko). 둘 사이의 안정 ABI가 KMI라, Google이 코어에 보안 수정을 넣어도 벤더 모듈은 재빌드 없이 계속 로드됩니다. 그런데 벤더 모듈(GPU 등)은 여전히 벤더 트랙으로 패치되니, C36의 패치 갭은 절반만 닫힙니다. Concept Atlas의 스물세 번째 모듈입니다."
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

![C35 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C35 — Android Common Kernel·GKI·KMI
> **계층**: Tier 6 (Native·커널) · **난이도**: 고급 · **선수 개념**: C27(부팅/커널), C31(Treble)
> **성격**: 보완 편.

C36에서 커널 패치 갭이 벤더 드라이버 특유라 했습니다. 그 갭의 **커널 절반을 절반만 닫은** 구조가 GKI입니다 — 프레임워크의 Treble을 커널로 내린 것입니다.

한 문장으로: **커널을 Google이 만든 제네릭 코어(boot.img)와 벤더 로더블 모듈(.ko)로 갈라, 둘 사이의 안정 ABI(KMI) 덕에 Google이 코어를 벤더 재빌드 없이 패치한다 — 단 벤더 모듈은 여전히 벤더 트랙.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념 - 제네릭 코어와 벤더 모듈

- **ACK(Android Common Kernel)**: Linux LTS + Android 패치. `android-mainline`(개발 tip)과 `androidNN-M.mm` 브랜치(예: `android12-5.10`, `android14-6.1` = 런치 버전 + LTS 베이스).
- **GKI(Generic Kernel Image)**: Google이 만든 **단일 제네릭 코어 커널**(boot.img). 벤더 코드를 코어에서 빼냄.
- **벤더 모듈**: 뺀 드라이버를 `.ko`로 `vendor_boot`(1단계)·`vendor_dlkm`(DLKM)에.
- **KMI(Kernel Module Interface)**: 코어↔모듈의 **안정 ABI**(심볼 + struct 레이아웃).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

커널을 프레임워크처럼 **"제네릭 코어 + 안정 인터페이스"**로 나눈 것입니다. C31의 Treble(유저스페이스/HAL/VINTF)을 커널 층으로 내렸고, KMI가 커널 모듈에게 VINTF/HAL이 유저스페이스에게 하는 역할을 합니다. 그리고 C36 패치 갭의 커널 측이 여기서 절반 닫힙니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **GKI 코어**: `boot.img`의 **단일 제네릭 커널 바이너리**. 아키텍처·**브랜치(release×LTS)별로 하나** — 기기별이 아닙니다. `android12-5.10`과 `android13-5.10`은 서로 다른 브랜치·다른 동결 KMI입니다.
- **벤더 모듈**: 예전엔 커널에 컴파일돼 있던 드라이버가 이제 `.ko`로 `vendor_boot`(1단계 init이 로드)·`vendor_dlkm`(나중 로드)에 실려, **KMI 심볼 목록**에 대해 빌드되고 런타임에 GKI 커널이 로드합니다.
- 전부 **EL1**(커널).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **KMI는 이름뿐 아니라 struct 레이아웃·호출 ABI까지의 안정 계약**입니다(`abi_gki_*` 허용 목록 + `TRIM_UNUSED_KSYMS`). CI가 **STG**(현행)/libabigail(구세대)로 ABI 변경을 거부합니다. **브랜치별로 동결**되어, 동결 전엔 자유롭게 바뀌고 동결 후엔 ABI 보존 변경만 허용됩니다.
- **GKI가 코어를 Google이 통일 패치**하게 합니다.
- **신뢰하면 안 되는 것들**:
  - **"GKI가 커널 전체 패치 갭을 닫는다"** — **코어만**입니다. 벤더 모듈(GPU 등)은 여전히 `vendor_dlkm`에서 **벤더 트랙**으로 패치됩니다(C36 갭 지속).
  - **"GKI 커널은 Play/APEX로 독립 전달된다"** — 아닙니다. 여전히 `boot.img`로 **OEM OTA**를 통해 옵니다. 속도 이득은 "Google이 벤더 재통합 없이 코어를 빌드·전진"이지 "OTA 독립 채널"이 아닙니다.
  - **"KMI는 영원히 불변"** — 브랜치 수명 동안만이고, 새 릴리스/새 LTS는 새 KMI 세대입니다.
  - **"GKI 1.0 = 2.0"** — 5.4/A11은 **파일럿(KMI 미동결)**, 5.10/A12부터 **동결 KMI 의무**(진짜 "코어 업데이트해도 벤더 모듈 재빌드 불필요"는 GKI 2.0 성질).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: GKI 코어(boot.img) + 벤더 `.ko`(vendor_dlkm/vendor_boot), 후자는 KMI 심볼 목록에 대해 빌드.
- **출력**: 부팅 시 코어가 로드되고, KMI 호환 모듈이 로드되면 하드웨어가 동작. ABI 불일치는 CI(STG/libabigail)가 빌드에서 거부.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **보안 이득**: Google이 코어 커널(LTS + 보안 수정)을 **벤더 재통합 없이** 전진시켜 — 코어 패치가 빨라지고, 벤더 in-core 코드가 줄어(코어에 사는 벤더 버그 감소), 단편화가 사라집니다.
- **한계(C36과 일관)**: 벤더 **모듈**(GPU/모뎀/카메라의 `.ko`)은 여전히 **벤더/SoC 트랙**으로 배포·패치됩니다. GKI 코어 업데이트가 벤더 모듈 버그를 건드리지 않으므로, **C36의 패치 갭은 벤더 모듈에 대해 지속**됩니다.
- **양날**: 안정 KMI는 편의이자 **안정된 타겟**이기도 합니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **GKI 1.0**(kernel 5.4 / Android 11): 벤더 코드 모듈화 **파일럿**. KMI 미동결.
- **GKI 2.0**(kernel 5.10 / Android 12): **동결 KMI 의무**. "코어 업데이트 → 벤더 모듈 재빌드 불필요"의 진짜 모델. KMI 동결은 `android12-5.10`부터.
- 브랜치: `androidNN-M.mm`(런치 버전 + LTS). 5.4/A11에 **런치**한 기기만 GKI 대상 — 업그레이드 기기는 소급 강제 아님.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `uname -r`(버전 + `android<ver>-<lts>` + KMI 세대, 예: `5.10.101-android12-9-...`), `cat /proc/version`, `ls /vendor/lib/modules`·`lsmod`(로드된 벤더 `.ko`), `getprop | grep -E "ro.kernel|ro.vendor"`.
- 파티션: `boot`(GKI 코어) vs `vendor_boot` vs `vendor_dlkm`(C27/C30).
- **소스**: `android.googlesource.com/kernel/common`(브랜치), `source.android.com/docs/core/architecture/kernel/{generic-kernel-image,kernel-module-interface}`.

**주의**: Emulator/Cuttlefish의 `uname`, GKI artifact와 reference module은 확인할 수 있지만 특정 OEM의 `vendor_dlkm` module 구성은 이 환경의 범위 밖입니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C27(부팅/커널)**: GKI 커널이 `boot.img`에 실리고, 1단계 init이 vendor_boot 모듈을 로드합니다.
- **C31(Treble)**: 같은 아이디어(제네릭 코어 + 안정 인터페이스)의 커널판 — VINTF↔KMI, HAL↔벤더 모듈.
- **C36(벤더 드라이버·패치 갭)**: GKI가 코어만 고치고 벤더 모듈은 못 고친다는 그 정확한 한계.
- **C30(파티션)**: vendor_boot/vendor_dlkm이 dynamic partitions로 실용화됩니다.
- **C05(EL)**: 코어·모듈 모두 EL1.
- 다음은 버그를 잡는 도구인 **C38(새니타이저)** 또는 다른 티어로 이어집니다.

## 호출 흐름

```
[ GKI: 커널의 제네릭 코어 + 벤더 모듈, 그리고 패치 트랙 ]

  boot.img: GKI 제네릭 코어 커널 (Google 빌드, 브랜치별)
        │  ── KMI (안정 심볼+struct ABI, STG/libabigail CI 감시) ──
        ▼
  vendor_dlkm / vendor_boot: 벤더 .ko 모듈(GPU/모뎀/카메라)
        (KMI 심볼 목록에 대해 빌드 → 재빌드 없이 로드)

  패치 트랙:
    코어 커널 ── Google이 벤더 재통합 없이 전진 → boot.img → (여전히 OEM OTA)
    벤더 모듈 ── SoC 벤더 → OEM → vendor_dlkm  (느림 = C36 갭 지속)
```

## 실측으로 확인한 것

가상 실습 환경(codex-atlas-api33, x86_64, Android 13, root)에서 커널 버전 문자열, 아키텍처, 그리고 런타임에 로드된 커널 모듈 목록을 명령으로 실측했다. KMI ABI 계약과 벤더 모듈 패치 트랙처럼 실기기·CI 파이프라인에 묶인 사실은 이어지는 「소스로 확정한 것」에서 AOSP 소스·공식 문서로 확정한다.

**1) 커널 버전 문자열을 읽는 경로(질문 7)가 실측으로 동작하고, 그 문자열이 ACK 브랜치·KMI 세대를 그대로 담고 있다.** 검증 블록의 `uname -a`에 더해 `uname -r`·`/proc/version`을 프로세스에서 그대로 읽었다.

```console
$ uname -r
5.15.119-android13-8-00034-gd34029c8258b-ab10871489
$ cat /proc/version
Linux version 5.15.119-android13-8-00034-gd34029c8258b-ab10871489 (build-user@build-host) (Android (8508608, based on r450784e) clang version 14.0.7 (https://android.googlesource.com/toolchain/llvm-project 4c603efb0cca074e9238af8b4106c30add4418f6), LLD 14.0.7) #1 SMP PREEMPT Wed Sep 27 18:42:24 UTC 2023
```

이 문자열은 질문 7이 말한 `uname -r`/`/proc/version` 경로가 성립함을 보이는 데서 그치지 않는다. `5.15.119-android13-8-...`은 LTS 베이스 `5.15.119`, ACK 릴리스 브랜치 `android13`, KMI 세대 `8`을 순서대로 담은 ACK/GKI 버전 형식이고, `Android ... clang version 14.0.7`·`SMP PREEMPT` 빌드 표기는 이 커널이 Android Common Kernel 트리에서 빌드됐음을 보여준다. 질문 2가 말한 "GKI는 아키텍처×브랜치(release×LTS)별로 하나"의 브랜치·세대 표기가 관측 문자열 수준에서 그대로 드러난다.

**2) 측정된 아키텍처가 곧 이 환경이 GKI 이미지가 아님을 증명한다.** 검증 블록의 `/proc/cpuinfo`가 x86_64를 확인했다. GKI는 정의상 아키텍처마다 별개 이미지이고 실 배포 GKI는 ARM64 boot.img이므로, x86_64 범용 커널은 그 자체로 교체 가능한 GKI 코어가 아니다 — 질문 2의 "아키텍처별로 하나"가 관측 아키텍처 수준에서 뒷받침된다.

**3) 로더블 커널 모듈(.ko) 로딩이 이 커널에서 실제로 쓰이고 있음을 `lsmod`로 관측했다.** GKI 코어가 부팅 후 모듈을 로드해 하드웨어를 붙인다는 질문 4의 경로가 이 AVD에서 실제로 동작하며, 로드된 모듈 53개가 목록에 잡혔다.

```console
$ lsmod
Module                  Size  Used by
zram                   24576  2 
zsmalloc               24576  1 zram
virtio_snd             28672  0 
virtio_pmem            16384  0 
virtio_net             53248  0 
virtio_input           20480  0 
virtio_balloon         28672  0 
(모듈 수: 53)
```

여기 로드된 것은 에뮬레이터의 virtio·zram 모듈 세트다. 폰에 실리는 GPU·모뎀 `.ko`의 `vendor_dlkm`/`vendor_boot` 구성은 아래 「소스로 확정한 것」에서 문서로 확정하며, 코어 커널이 런타임에 `.ko`를 로드한다는 GKI의 기본 전제 자체는 이 실측으로 그대로 확인된다.

## 소스로 확정한 것

실기기·ARM64 부팅과 CI 파이프라인에 묶인 GKI/KMI의 나머지 성질은 AOSP 소스와 공식 문서로 확정한다.

- **KMI는 심볼 이름을 넘어 struct 레이아웃·호출 ABI까지의 안정 계약이고, 브랜치별로 동결된다.** `abi_gki_*` 허용 목록과 `TRIM_UNUSED_KSYMS`로 심볼 표면을 좁히고, STG(현행)/libabigail(구세대)가 ABI 변경을 CI에서 거부한다(질문 3). [KMI 문서](https://source.android.com/docs/core/architecture/kernel/kernel-module-interface)와 [ACK 브랜치 트리](https://android.googlesource.com/kernel/common)의 `abi_gki_*` 파일로 확정한다.
- **실 배포 GKI 코어는 아키텍처마다 별개의 boot.img이며, 폰에 실리는 이미지는 ARM64다.** 위 (2)에서 실측한 x86_64는 "아키텍처별로 하나"라는 원칙(질문 2)을 관측 아키텍처 수준에서 그대로 보여주고, 배포 이미지가 ARM64라는 점은 [GKI 문서](https://source.android.com/docs/core/architecture/kernel/generic-kernel-image)로 확정한다.
- **동결 KMI 의무는 GKI 2.0(kernel 5.10 / Android 12)부터다.** GKI 1.0(5.4 / Android 11)은 KMI 미동결 파일럿이고, "코어를 업데이트해도 벤더 모듈 재빌드 불필요"라는 진짜 성질은 GKI 2.0에서 성립한다(질문 6). [GKI 문서](https://source.android.com/docs/core/architecture/kernel/generic-kernel-image)로 확정한다.
- **벤더 모듈(GPU·모뎀·카메라의 `.ko`)은 벤더/SoC 트랙으로 배포·패치된다.** GKI 코어 업데이트는 벤더 모듈 버그를 건드리지 않으므로 C36의 벤더 드라이버 패치 갭은 벤더 모듈에 대해 그대로 남고, 이는 GKI가 커널 패치 갭을 "닫는 게 아니라 나눈다"는 이 글의 결론(질문 5)과 같다. [GKI 문서](https://source.android.com/docs/core/architecture/kernel/generic-kernel-image)로 확정한다.

## 마치며

GKI는 프레임워크의 Treble을 커널로 내려, 벤더가 커널을 포크하던 단편화를 "제네릭 코어(boot.img) + 벤더 로더블 모듈(.ko)"로 갈랐습니다. 둘 사이의 안정 ABI인 KMI(심볼 + struct 레이아웃, 브랜치별 동결) 덕에 Google이 코어에 보안 수정을 넣어도 벤더 모듈은 재빌드 없이 로드됩니다. 그러나 그 벤더 모듈(GPU·모뎀 등)은 여전히 벤더 트랙으로 패치되므로 — GKI는 커널 패치 갭을 **닫는 게 아니라 나눕니다**: 코어는 Google이 빠르게, 벤더 모듈은 여전히 느리게(C36). 다음은 그 버그들을 애초에 잡는 도구인 **C38(ASan·HWASan·KASAN·UBSan)**로 이어집니다.
