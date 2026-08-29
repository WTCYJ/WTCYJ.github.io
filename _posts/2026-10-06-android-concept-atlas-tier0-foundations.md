---
layout: post
title: "Android Security Concept Atlas Tier 0 | 학습 로드맵 — 보안·시스템 기초"
date: 2026-10-06 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier0, 기초, 학습기록]
excerpt: "Atlas의 밑변입니다. 인증과 인가의 구분, 최소권한·완전중재·심층방어 같은 설계 원칙, 그리고 앱이 결국 평범한 Linux 프로세스(격리는 MMU 하드웨어)이며 ARM64 예외 수준이 모든 권한 경계의 바닥이라는 것 — 나머지 아홉 티어가 전부 이 다섯 개념 위에 섭니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 0의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: `id`, `cat /proc/self/attr/current`, `/proc/self/status`, `uname -a`. 앱 UID 10174, `untrusted_app` 도메인, `CapEff=0`, `Seccomp=2`, Linux 5.15 커널을 확인했다. AVD가 x86_64이므로 ARM64 EL·PAC·BTI·MTE는 런타임 관측 대신 공개 소스 경로로 판정한다.

![Tier 0 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 0 — 보안·시스템 기초 (Domain 1)**
> 5개 모듈 · 이 계층은 Atlas 전체의 **좌표계**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · 다음 → [Tier 1 앱·패키징](/posts/android-concept-atlas-tier1-app-packaging/)

이 계층은 "무엇을 지키고, 누가 그 경계를 넘으며, 그 경계는 하드웨어의 어디에 있는가"를 정의합니다. 여기서 이름 붙인 원칙(인증/인가, 최소권한, 완전중재)과 기반(프로세스·가상메모리·예외 수준)은 이후 모든 모듈이 되풀이해 실현하는 것입니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C01 | [자산·주체·신뢰경계·공격표면](/posts/android-concept-atlas-c01-assets-subjects-trust-boundaries/) | 🟡 | ✅ | 무엇을 지키고 누가 넘나 — 나머지 전부의 좌표계 |
| C02 | [인증 vs 인가](/posts/android-concept-atlas-c02-authn-authz/) | 🟡 | ✅ | "누구인가"(AuthN)와 "무엇을 해도 되나"(AuthZ)는 별개 — 혼동이 곧 IDOR·BFLA |
| C03 | [최소권한·완전중재·심층방어](/posts/android-concept-atlas-c03-security-principles/) | 🟡 | ✅ | Atlas 전체가 실현해온 설계 원칙에 이름 붙이기(S&S 1975 + 심층방어) |
| C04 | [프로세스·가상메모리·시스템 콜](/posts/android-concept-atlas-c04-process-vm-syscall/) | 🔴 | ✅ | 앱은 평범한 Linux 프로세스, 격리는 MMU 하드웨어, `SVC`로 EL0→EL1 |
| C05 | [ARM64 예외 수준·메모리 보호](/posts/android-concept-atlas-c05-arm64-exception-levels/) | 🔴 | ✅ | EL0~EL3·TrustZone — 모든 권한 경계의 하드웨어 바닥 |

## 이 계층의 서사

C04(프로세스·MMU)와 C05(예외 수준)가 **하드웨어 바닥**을 깔고, 그 위에서 C02(인증 vs 인가)·C03(설계 원칙)이 **판단의 언어**를 세웁니다. C03은 특히 Atlas 전체의 메타 지도 — 앱마다 UID를 주는 건 최소권한, SELinux가 매 접근을 검사하는 건 완전중재, UID+SELinux+seccomp를 겹치는 건 심층방어입니다. C02의 "인증됐다고 인가된 건 아니다"는 이후 IDOR/OAuth 버그의 뿌리로 반복됩니다.

> **완성 보고서**: C01은 자산·주체·신뢰경계·공격표면을 전용 글과 실행 증거로 정리했습니다.

---

**다음** → [Tier 1 — 앱·패키징](/posts/android-concept-atlas-tier1-app-packaging/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
