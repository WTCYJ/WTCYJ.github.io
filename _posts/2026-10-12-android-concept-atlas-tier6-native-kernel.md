---
layout: post
title: "Android Security Concept Atlas Tier 6 | 학습 로드맵 — Native·커널"
date: 2026-10-12 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier6, Kernel, Mitigations, 학습기록]
excerpt: "EL0에서 EL1로 내려가는 계층입니다. ELF/링커로 네이티브 코드가 실행되고, ioctl이 커널로 가는 문이며, GKI가 커널을 갈라 통일 패치하되 벤더 드라이버는 여전히 벤더 트랙이라 패치 갭이 남고, 완화(PAC/MTE)와 새니타이저가 그 위에서 익스플로잇을 막고 버그를 잡습니다. 내 CVE 시리즈의 EL0→EL1 서사가 여기 완성됩니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 6의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: `uname -a`, `/proc/cpuinfo`, NDK JNI 빌드, UBSan 패치 전·후 실행. Android 13 기반 Linux 5.15 x86_64 커널을 확인하고, NDK 27로 JNI 공유 라이브러리와 UBSan 대조군을 빌드·실행했다. 범용 AVD에 없는 벤더 드라이버와 KASAN 커널은 실행하지 않았으며, 해당 항목은 공개 소스·설정 분석 결과로 구분한다.

![Tier 6 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 6 — Native·커널 (Domain 7)**
> 6개 모듈 · 이 계층은 **EL0→EL1 공격 표면과 방어**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 5](/posts/android-concept-atlas-tier5-boot-chain/) · 다음 → [Tier 7 하드웨어 보안](/posts/android-concept-atlas-tier7-hardware-security/)

유저스페이스 네이티브 코드(ELF)에서 커널(ioctl)로 내려가는, 그리고 그 경계에서 익스플로잇을 막는 계층입니다. 내 CVE 재현 시리즈의 EL0→EL1 권한 상승 서사가 정확히 여기서 완성됩니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C33 | [ELF·linker·PLT/GOT](/posts/android-concept-atlas-c33-elf-linker-plt-got/) | 🟡 | ✅ | bionic 링커; lazy 바인딩 안 함 + full RELRO 기본 |
| C34 | [ioctl·device node](/posts/android-concept-atlas-c34-ioctl-device-node/) | 🔴 | ✅ | (major,minor)로 드라이버 라우팅; Binder도 결국 ioctl |
| C35 | [Android Common Kernel·GKI·KMI](/posts/android-concept-atlas-c35-gki-kmi/) | 🟡 | ✅ | 코어는 Google 통일 패치, **벤더 모듈은 여전히 벤더 트랙**(갭 지속) |
| C36 | [vendor driver·HAL 공격 표면](/posts/android-concept-atlas-c36-vendor-driver-attack-surface/) | 🔴 | ✅ | GPU Mali kbase/Qualcomm KGSL; 패치 갭이 n-day를 살림 |
| C37 | [ASLR·NX·canary·CFI·PAC·BTI·MTE](/posts/android-concept-atlas-c37-exploit-mitigations/) | 🔴 | ✅ | 메모리 안전은 **탐지기(MTE/HWASan)**와 **장벽(PAC/CFI)** 두 축 |
| C38 | [ASan·HWASan·KASAN·UBSan](/posts/android-concept-atlas-c38-sanitizers/) | 🟡 | ✅ | 탐지기(테스트/퍼징용); 유저 폰엔 MTE·최소 IntSan만 실림 |

## 이 계층의 서사

C33(ELF/링커)이 네이티브 코드 실행의 바닥이고, C34(ioctl)가 EL0에서 커널로 가는 문입니다 — 그 문 너머 C36의 벤더 드라이버(GPU)가 가장 큰 공격 표면이고, C35(GKI)는 커널을 갈라 코어는 통일 패치하되 **벤더 모듈은 여전히 벤더 트랙**이라 C36의 패치 갭이 지속됩니다. C37(완화)이 그 위에서 익스플로잇을 막고, C38(새니타이저)이 버그를 애초에 잡습니다 — C38은 내 퍼징·CVE 정수결함과 정면으로 만나, Atlas가 내 실측과 겹치는 지점입니다.

---

**다음** → [Tier 7 — 하드웨어 기반 보안](/posts/android-concept-atlas-tier7-hardware-security/) · [← Tier 5](/posts/android-concept-atlas-tier5-boot-chain/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
