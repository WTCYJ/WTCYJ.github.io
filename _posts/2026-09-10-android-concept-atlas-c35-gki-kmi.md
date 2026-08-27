---
layout: post
title: "Android Security Concept Atlas C35 - Android Common Kernel·GKI·KMI, 커널의 제네릭 코어와 벤더 모듈"
date: 2026-09-10 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, GKI, KMI, AndroidCommonKernel, ACK, vendordlkm, vendorboot, KernelModule, PatchGap, ConceptAtlas, 학습기록]
excerpt: "예전에는 SoC 벤더마다 커널을 포크해 드라이버를 통째로 컴파일해 넣어, 기기마다 서로 다른 커널 바이너리 수천 개가 생겼습니다 - 이게 커널 보안 패치가 느린 구조적 원인이었죠. GKI는 그것을 프레임워크의 Treble처럼 갈랐습니다: Google이 만든 하나의 제네릭 코어 커널(boot.img)과, 벤더 드라이버를 뺀 로더블 모듈(.ko). 둘 사이의 안정 ABI가 KMI라, Google이 코어에 보안 수정을 넣어도 벤더 모듈은 재빌드 없이 계속 로드됩니다. 그런데 벤더 모듈(GPU 등)은 여전히 벤더 트랙으로 패치되니, C36의 패치 갭은 절반만 닫힙니다. Concept Atlas의 스물세 번째 모듈입니다."
---

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

**주의**: 에뮬레이터도 커널이 있어 `uname`은 보이지만, GKI/벤더 모듈 분할의 실체(vendor_dlkm의 벤더 `.ko`)는 실기기에서.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C27(부팅/커널)**: GKI 커널이 `boot.img`에 실리고, 1단계 init이 vendor_boot 모듈을 로드합니다.
- **C31(Treble)**: 같은 아이디어(제네릭 코어 + 안정 인터페이스)의 커널판 — VINTF↔KMI, HAL↔벤더 모듈.
- **C36(벤더 드라이버·패치 갭)**: GKI가 코어만 고치고 벤더 모듈은 못 고친다는 그 정확한 한계.
- **C30(파티션)**: vendor_boot/vendor_dlkm이 dynamic partitions로 실용화됩니다.
- **C05(EL)**: 코어·모듈 모두 EL1.
- 다음은 버그를 잡는 도구인 **C38(새니타이저)** 또는 다른 티어로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "GKI는 커널 전체의 패치 갭을 닫아, 이제 Google이 커널 전부를 통일 패치한다."
2. "GKI 커널은 Mainline/Play 시스템 업데이트처럼 OTA와 독립으로 배포된다."
3. "KMI는 심볼 이름 목록일 뿐이다."
4. "KMI는 한번 정해지면 영원히 바뀌지 않는다."
5. "GKI는 Android 11(kernel 5.4)부터 동결 KMI로 코어 업데이트가 벤더 재빌드 없이 됐다."

<details><summary>판정 기준(펼치기)</summary>

1. **코어만**입니다. 벤더 모듈(GPU 등)은 여전히 `vendor_dlkm`에서 벤더 트랙으로 패치됩니다 — C36 갭이 그대로 남습니다.
2. 여전히 `boot.img`로 **OEM OTA**를 통해 옵니다. 이득은 Google이 벤더 재통합 없이 코어를 빌드하는 것이지 OTA 독립 채널이 아닙니다.
3. **심볼 + struct 레이아웃 + 호출 ABI**의 계약입니다. struct 레이아웃까지 안정해야 바이너리 호환이 보장됩니다.
4. **브랜치 수명 동안만** 동결이고, 새 릴리스/새 LTS는 새 KMI 세대입니다.
5. 5.4/A11은 **GKI 1.0 파일럿(KMI 미동결)**입니다. 동결 KMI 의무는 **GKI 2.0(5.10/A12)**부터입니다.
</details>

## 서술형 문제 3개

1. GKI 이전의 단편화 문제(벤더가 커널을 포크해 드라이버를 컴파일 → N개 커널 → 느린 패치)와, GKI가 그것을 어떻게 갈랐는지 서술하세요.
2. KMI가 왜 심볼 이름만이 아니라 struct 레이아웃까지의 ABI여야 하는지(바이너리 호환), 그리고 브랜치별 동결의 의미를 서술하세요.
3. GKI가 커널 패치 갭의 무엇을 고치고 무엇을 못 고치는지(코어 vs 벤더 모듈)를 C36과 일관되게 서술하세요.

## 소스 탐색 과제

- 실기기에서 `uname -r`로 `android<ver>-<lts>`와 KMI 세대를, `ls /vendor/lib/modules`·`lsmod`로 로드된 벤더 `.ko`를 확인하세요.
- 이 기기가 GKI 2.0(5.10+/A12+)인지 GKI 1.0/비-GKI인지 근거와 함께 판정하세요.
- `boot`(코어) vs `vendor_dlkm`(벤더 모듈) 파티션을 대조해, 코어와 벤더의 패치 트랙 분리를 서술하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **버전 실측**: `uname -r`·`/proc/version`으로 KMI 세대를 캡처.
2. **모듈 실측**: `lsmod`·`ls /vendor/lib/modules`로 벤더 `.ko`를.
3. **패치 트랙 서술**: 이 기기의 코어 커널 vs 벤더 SPL을 대조해 갭을 근거로.
4. **연결**: C36의 벤더 드라이버 CVE가 왜 GKI 코어 업데이트로 안 고쳐지는지 서술.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

GKI는 프레임워크의 Treble을 커널로 내려, 벤더가 커널을 포크하던 단편화를 "제네릭 코어(boot.img) + 벤더 로더블 모듈(.ko)"로 갈랐습니다. 둘 사이의 안정 ABI인 KMI(심볼 + struct 레이아웃, 브랜치별 동결) 덕에 Google이 코어에 보안 수정을 넣어도 벤더 모듈은 재빌드 없이 로드됩니다. 그러나 그 벤더 모듈(GPU·모뎀 등)은 여전히 벤더 트랙으로 패치되므로 — GKI는 커널 패치 갭을 **닫는 게 아니라 나눕니다**: 코어는 Google이 빠르게, 벤더 모듈은 여전히 느리게(C36). 다음은 그 버그들을 애초에 잡는 도구인 **C38(ASan·HWASan·KASAN·UBSan)**로 이어집니다.
