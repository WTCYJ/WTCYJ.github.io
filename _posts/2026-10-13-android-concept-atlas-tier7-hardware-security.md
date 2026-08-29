---
layout: post
title: "Android Security Concept Atlas Tier 7 | 학습 로드맵 — 하드웨어 기반 보안"
date: 2026-10-13 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier7, TEE, Keystore, 학습기록]
excerpt: "Rich OS가 아무리 뚫려도 지켜지는 신뢰의 하드웨어 뿌리입니다. TrustZone의 시큐어 월드가 Keystore의 비추출 키를 쥐고, Gatekeeper가 사용자 인증을, key attestation이 그 하드웨어 뿌리를 원격 증명하며, FBE가 사용자 자격증명에 데이터를 묶습니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 7의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: AndroidKeyStore EC 키 생성, attestation challenge, `KeyInfo`, certificate chain 조회. EC 키 생성과 attestation 요청이 성공했고 인증서 체인 길이는 3이었다. 이 AVD의 키 보안 수준은 정확히 `SOFTWARE(0)`였다. TEE·StrongBox·Weaver는 물리 보안 하드웨어가 없는 AVD에서 증명할 수 없다. SOFTWARE 결과를 하드웨어 보안으로 해석하지 않는다.

![Tier 7 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 7 — 하드웨어 기반 보안 (Domain 8)**
> 5개 모듈 · 이 계층은 **신뢰의 하드웨어 뿌리**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 6](/posts/android-concept-atlas-tier6-native-kernel/) · 다음 → [Tier 8 앱 보안 통제](/posts/android-concept-atlas-tier8-app-controls/)

Rich OS(Android)가 침해됐을 때에도 별도의 신뢰 경계가 보호하도록 설계된 기능을 다루는 계층입니다. TrustZone/TEE(C39), Keystore·KeyMint·StrongBox(C40), Gatekeeper와 생체 인증(C41), key attestation(C42), FBE(C43)를 연결하되, 보호 수준은 구현·security level·threat model에 따라 달라짐을 전제로 합니다. 표의 색상은 Atlas 시작 당시의 학습 진단입니다.

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
