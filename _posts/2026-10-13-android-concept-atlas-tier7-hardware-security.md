---
layout: post
title: "Android Security Concept Atlas — Tier 7: 하드웨어 기반 보안"
date: 2026-10-13 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier7, TEE, Keystore, 학습기록]
excerpt: "Rich OS가 아무리 뚫려도 지켜지는 신뢰의 하드웨어 뿌리입니다. TrustZone의 시큐어 월드가 Keystore의 비추출 키를 쥐고, Gatekeeper가 사용자 인증을, key attestation이 그 하드웨어 뿌리를 원격 증명하며, FBE가 사용자 자격증명에 데이터를 묶습니다."
---

> **Concept Atlas · Tier 7 — 하드웨어 기반 보안 (Domain 8)**
> 5개 모듈 · 이 계층은 **신뢰의 하드웨어 뿌리**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 6](/posts/android-concept-atlas-tier6-native-kernel/) · 다음 → [Tier 8 앱 보안 통제](/posts/android-concept-atlas-tier8-app-controls/)

Rich OS(Android)가 완전히 침해돼도 지켜져야 하는 것들의 계층입니다. TrustZone의 시큐어 월드(C39)가 Keystore의 비추출 키(C40)를 쥐고, Gatekeeper(C41)가 사용자 인증을, key attestation(C42)이 그 하드웨어 뿌리를 원격 증명하며, FBE(C43)가 데이터를 사용자 자격증명에 묶습니다. Atlas에서 판정이 가장 무거웠던(🔴) 계층이자 우선순위 Top 5 중 둘(C28은 Tier 5, C40은 여기)이 나온 곳입니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C39 | [TEE·Trusty·시큐어 월드](/posts/android-concept-atlas-c39-tee-trusty-secure-world/) | 🔴 | ✅ | EL3=secure state; Trusty는 GlobalPlatform이 아님 |
| C40 | [Keystore·KeyMint·StrongBox](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/) | 🔴 | ✅ | 키는 비추출·하드웨어 바운드; StrongBox가 반드시 off-SoC는 아님 |
| C41 | [Gatekeeper·Weaver·biometrics](/posts/android-concept-atlas-c41-gatekeeper-weaver-biometrics/) | 🔴 | ✅ | Gatekeeper=지식요소(PIN/패턴/비번), 생체는 별도 생체 HAL |
| C42 | [key attestation·root of trust](/posts/android-concept-atlas-c42-key-attestation/) | 🔴 | ✅ | 하드웨어 뿌리를 Google 루트로 증명; verifiedBootHash(v3~) |
| C43 | [FBE(파일기반 암호화)·Direct Boot](/posts/android-concept-atlas-c43-fbe-direct-boot/) | 🔴 | ✅ | 파일 단위 암호화; CE(첫 해제 후)/DE(부팅 시), 메타데이터 암호화 A11 |

## 이 계층의 서사

C39(TEE)가 시큐어 월드라는 격리된 실행 환경을 제공하고, 그 안에서 C40(Keystore)이 유저스페이스가 결코 볼 수 없는 비추출 키를 쥡니다. C41(Gatekeeper/생체)이 사용자를 인증해 그 키 사용을 게이트하고, C42(attestation)가 "이 키가 진짜 하드웨어에 있다"를 원격 relying party에 증명하며(Play Integrity의 STRONG이 여기 기댐), C43(FBE)이 사용자 자격증명으로 데이터를 암호화합니다. Rich OS가 뚫려도 이 뿌리는 남는다는 게 이 계층 전체의 약속입니다.

---

**다음** → [Tier 8 — 앱 보안 통제](/posts/android-concept-atlas-tier8-app-controls/) · [← Tier 6](/posts/android-concept-atlas-tier6-native-kernel/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
