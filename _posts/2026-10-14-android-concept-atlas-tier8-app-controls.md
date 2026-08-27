---
layout: post
title: "Android Security Concept Atlas — Tier 8: 앱 보안 통제"
date: 2026-10-14 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier8, AppSecurity, 학습기록]
excerpt: "앱 개발자가 실제로 다루는 통제들입니다. 안전한 저장(하드코딩 키 금지)·인증(불변 sub+iss 바인딩)·전송(유저 CA 미신뢰·핀은 우회 가능)·무결성(클라 판정 무의미)·공급망(SDK가 앱 권한 상속)·개인정보(권한=폭발 반경). 내 버그바운티·인터셉션·RE 작업과 가장 많이 겹치는 계층입니다."
---

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
| C47 | WebView·딥링크·IPC 공격면 | 🟢 | 🧩 진단 | exported WebView·딥링크 URI 취급이 confused-deputy |
| C48 | [Play Integrity·앱 무결성](/posts/android-concept-atlas-c48-play-integrity/) | 🟡 | ✅ | 클라 판정은 무의미(패치로 우회)·서버 검증 필수; STRONG만 하드웨어 |
| C49 | [서드파티 SDK·SBOM·공급망](/posts/android-concept-atlas-c49-thirdparty-sdk-supplychain/) | 🔴 | ✅ | SDK가 앱 UID·전체 권한 상속; 하나 침해=O(N) 앱 |
| C50 | [개인정보 최소화·권한 모델 변화](/posts/android-concept-atlas-c50-privacy-minimization/) | 🟡 | ✅ | 권한 = 침해의 **폭발 반경**(진입점 아님); A6~A15 최소화 진화 |

## 이 계층의 서사

C44(저장)에서 하드코딩 키가, C45(인증)에서 mutable username 바인딩이(내 reporch ATO), C46(전송)에서 유저 CA 미신뢰가(내 인터셉션 벽), C48(무결성)에서 클라이언트 전용 검사가(내가 늘 우회하는 클래스) — 각 모듈이 대표 함정 하나로 압축됩니다. 그리고 C49(공급망)·C50(개인정보)이 그 모두를 관통하는 통찰을 줍니다: **SDK는 앱 권한을 그대로 상속하고**, **권한 하나하나가 침해의 폭발 반경**이라는 것. 최소권한(C02/C03)이 데이터·앱 층위에서 다시 나타납니다.

> **진단편**: C47(WebView·딥링크·IPC 공격면, 5~8주차·Toss)은 진단으로 대체합니다.

---

**다음** → [Tier 9 — 취약점 연구](/posts/android-concept-atlas-tier9-vuln-research/) · [← Tier 7](/posts/android-concept-atlas-tier7-hardware-security/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
