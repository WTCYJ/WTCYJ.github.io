---
layout: post
title: "Android Security Concept Atlas — Tier 0: 보안·시스템 기초"
date: 2026-10-06 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier0, 기초, 학습기록]
excerpt: "Atlas의 밑변입니다. 인증과 인가의 구분, 최소권한·완전중재·심층방어 같은 설계 원칙, 그리고 앱이 결국 평범한 Linux 프로세스(격리는 MMU 하드웨어)이며 ARM64 예외 수준이 모든 권한 경계의 바닥이라는 것 — 나머지 아홉 티어가 전부 이 다섯 개념 위에 섭니다."
---

> **Concept Atlas · Tier 0 — 보안·시스템 기초 (Domain 1)**
> 5개 모듈 · 이 계층은 Atlas 전체의 **좌표계**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · 다음 → [Tier 1 앱·패키징](/posts/android-concept-atlas-tier1-app-packaging/)

이 계층은 "무엇을 지키고, 누가 그 경계를 넘으며, 그 경계는 하드웨어의 어디에 있는가"를 정의합니다. 여기서 이름 붙인 원칙(인증/인가, 최소권한, 완전중재)과 기반(프로세스·가상메모리·예외 수준)은 이후 모든 모듈이 되풀이해 실현하는 것입니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C01 | 자산·주체·신뢰경계·공격표면 | 🟡 | 🧩 진단 | 무엇을 지키고 누가 넘나 — 나머지 전부의 좌표계 |
| C02 | [인증 vs 인가](/posts/android-concept-atlas-c02-authn-authz/) | 🟡 | ✅ | "누구인가"(AuthN)와 "무엇을 해도 되나"(AuthZ)는 별개 — 혼동이 곧 IDOR·BFLA |
| C03 | [최소권한·완전중재·심층방어](/posts/android-concept-atlas-c03-security-principles/) | 🟡 | ✅ | Atlas 전체가 실현해온 설계 원칙에 이름 붙이기(S&S 1975 + 심층방어) |
| C04 | [프로세스·가상메모리·시스템 콜](/posts/android-concept-atlas-c04-process-vm-syscall/) | 🔴 | ✅ | 앱은 평범한 Linux 프로세스, 격리는 MMU 하드웨어, `SVC`로 EL0→EL1 |
| C05 | [ARM64 예외 수준·메모리 보호](/posts/android-concept-atlas-c05-arm64-exception-levels/) | 🔴 | ✅ | EL0~EL3·TrustZone — 모든 권한 경계의 하드웨어 바닥 |

## 이 계층의 서사

C04(프로세스·MMU)와 C05(예외 수준)가 **하드웨어 바닥**을 깔고, 그 위에서 C02(인증 vs 인가)·C03(설계 원칙)이 **판단의 언어**를 세웁니다. C03은 특히 Atlas 전체의 메타 지도 — 앱마다 UID를 주는 건 최소권한, SELinux가 매 접근을 검사하는 건 완전중재, UID+SELinux+seccomp를 겹치는 건 심층방어입니다. C02의 "인증됐다고 인가된 건 아니다"는 이후 IDOR/OAuth 버그의 뿌리로 반복됩니다.

> **진단편**: C01(자산·주체·신뢰경계·공격표면)은 내 로드맵 글의 진단 10문으로 대체합니다 — 이미 다룬 개념이라 풀글 대신 문제로.

---

**다음** → [Tier 1 — 앱·패키징](/posts/android-concept-atlas-tier1-app-packaging/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
