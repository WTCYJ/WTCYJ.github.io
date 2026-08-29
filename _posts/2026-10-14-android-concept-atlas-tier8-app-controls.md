---
layout: post
title: "Android Security Concept Atlas Tier 8 | 학습 로드맵 — 앱 보안 통제"
date: 2026-10-14 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier8, AppSecurity, 학습기록]
excerpt: "앱 개발자가 실제로 다루는 통제들입니다. 안전한 저장(하드코딩 키 금지)·인증(불변 sub+iss 바인딩)·전송(유저 CA 미신뢰·핀은 우회 가능)·무결성(클라 판정 무의미)·공급망(SDK가 앱 권한 상속)·개인정보(권한=폭발 반경). 내 버그바운티·인터셉션·RE 작업과 가장 많이 겹치는 계층입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 8의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: Android 개인정보·보안·네트워크 설정 캡처, `curl --tlsv1.3`, 패키지·AppOps 조회. 권한·개인정보 통제 화면과 TLS 1.3 HTTP 200 응답을 확인했다. 앱·호스트 네트워크 관측을 분리해 기록했다. Play Integrity의 프로덕션 verdict, 실제 OAuth 공급자, 제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다.

![Tier 8 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 8 — 앱 보안 통제 (Domain 9)**
> 7개 모듈 · 이 계층은 **앱 층위의 실전 통제**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 7](/posts/android-concept-atlas-tier7-hardware-security/) · 다음 → [Tier 9 취약점 연구](/posts/android-concept-atlas-tier9-vuln-research/)

플랫폼이 준 것(Tier 1~7) 위에서 앱 개발자가 직접 세우는 통제들이고, 내 버그바운티·인터셉션·RE 작업과 가장 많이 겹치는 계층입니다. 저장·인증·전송·무결성·공급망·개인정보 — 각각에 대표적 함정이 하나씩 있습니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C44 | [안전한 저장소·백업·키 관리](/posts/android-concept-atlas-c44-secure-storage-backup/) | 🟡 | ✅ | 하드코딩 키·allowBackup 유출; FBE는 BFU만, 비밀은 Keystore |
| C45 | [인증·세션·OAuth/OIDC·passkey](/posts/android-concept-atlas-c45-auth-session-oauth-passkey/) | 🟡 | ✅ | 계정은 불변 `sub+iss`에 바인딩(mutable username=ATO); code+PKCE |
| C46 | [TLS·Network Security Config·pinning](/posts/android-concept-atlas-c46-tls-nsc-pinning/) | 🟡 | ✅ | A24 유저 CA 미신뢰가 프록시 실패 원인; 핀은 클라 측 우회 가능 |
| C47 | [WebView·딥링크·IPC 공격면](/posts/android-concept-atlas-c47-webview-deeplink-ipc-attack-surface/) | 🟢 | ✅ | exported WebView·딥링크 URI 취급이 confused-deputy |
| C48 | [Play Integrity·앱 무결성](/posts/android-concept-atlas-c48-play-integrity/) | 🟡 | ✅ | 클라 판정은 무의미(패치로 우회)·서버 검증 필수; STRONG만 하드웨어 |
| C49 | [서드파티 SDK·SBOM·공급망](/posts/android-concept-atlas-c49-thirdparty-sdk-supplychain/) | 🔴 | ✅ | SDK가 앱 UID·전체 권한 상속; 하나 침해=O(N) 앱 |
| C50 | [개인정보 최소화·권한 모델 변화](/posts/android-concept-atlas-c50-privacy-minimization/) | 🟡 | ✅ | 권한 = 침해의 **폭발 반경**(진입점 아님); A6~A15 최소화 진화 |

## 이 계층의 서사

C44(저장)에서 하드코딩 키가, C45(인증)에서 mutable username 바인딩이(내 reporch ATO), C46(전송)에서 유저 CA 미신뢰가(내 인터셉션 벽), C48(무결성)에서 클라이언트 전용 검사가(내가 늘 우회하는 클래스) — 각 모듈이 대표 함정 하나로 압축됩니다. 그리고 C49(공급망)·C50(개인정보)이 그 모두를 관통하는 통찰을 줍니다: **SDK는 앱 권한을 그대로 상속하고**, **권한 하나하나가 침해의 폭발 반경**이라는 것. 최소권한(C02/C03)이 데이터·앱 층위에서 다시 나타납니다.

> **완성 보고서**: C47은 HTTPS 호스트 allowlist의 허용·거부 대조군으로 WebView·딥링크 입력 검증을 정리했습니다.

---

**다음** → [Tier 9 — 취약점 연구](/posts/android-concept-atlas-tier9-vuln-research/) · [← Tier 7](/posts/android-concept-atlas-tier7-hardware-security/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
