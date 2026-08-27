---
layout: post
title: "Android Security Concept Atlas — Tier 1: 앱·패키징"
date: 2026-10-07 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier1, 패키징, 학습기록]
excerpt: "앱이 무엇으로 만들어지고(APK/AAB), 무엇으로 신원을 증명하며(서명), 어떤 격리(UID)와 권능(권한)을 받고, 서로를 어떻게 보고 넘기는가(가시성·URI)를 다룹니다. 앱↔앱 1차 경계는 UID DAC이고, 서명자 인증서가 앱의 안정적 정체성입니다."
---

> **Concept Atlas · Tier 1 — 앱·패키징 (Domain 3)**
> 6개 모듈 · 이 계층은 **앱의 정체성과 격리**를 세웁니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 0](/posts/android-concept-atlas-tier0-foundations/) · 다음 → [Tier 2 런타임](/posts/android-concept-atlas-tier2-runtime/)

Tier 0의 프로세스(C04) 위에 정체성(UID)과 권능(권한)을 얹는 계층입니다. 앱이 무엇으로 포장되고(C06), 무엇으로 신원을 증명하며(C08), 어떤 UID 샌드박스(C09)와 권한(C10)을 받고, 서로를 어떻게 보고 데이터를 넘기는지(C11)를 순서대로 세웁니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C06 | [APK·AAB·Split APK](/posts/android-concept-atlas-c06-apk-aab-split/) | 🟡 | ✅ | APK=설치 ZIP, AAB=발행 포맷(설치 불가); split은 같은 키·한 UID |
| C07 | DEX·multidex·resources.arsc | 🟢 | 🧩 진단 | 단일 DEX의 64K 메서드 참조 한도·컴파일된 리소스 |
| C08 | [서명 v1~v4·키 순환](/posts/android-concept-atlas-c08-apk-signing/) | 🟡 | ✅ | 서명자 인증서=앱 정체성; v1 갭이 Janus, v2가 전체파일 |
| C09 | [UID·sharedUserId·샌드박스](/posts/android-concept-atlas-c09-uid-sandbox/) | 🟡 | ✅ | 앱↔앱 1차 경계는 UID DAC(SELinux는 그 위 별개 층) |
| C10 | [permission·signature perm·AppOps](/posts/android-concept-atlas-c10-permissions-appops/) | 🟡 | ✅ | 권한은 UID에 부여; `checkCallingOrSelfPermission`의 자기-폴백 함정 |
| C11 | [package visibility·URI permission](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) | 🟡 | ✅ | 가시성은 targetSdk30 게이트; URI 위임은 confused-deputy 벡터 |

## 이 계층의 서사

C06(포장)에서 시작해 C08(서명=정체성)이 "이 앱은 누구인가"를 확립하면, C09(UID)가 그 정체성에 격리를, C10(권한)이 권능을 얹습니다. sharedUserId(C09)·signature 권한(C10)·업데이트가 전부 "같은 서명 키"(C08)로 결정된다는 게 이 계층의 접착제입니다. 마지막으로 C11이 앱 간 관찰(가시성)과 위임(URI 권한)을 다루는데, 여기서 딥링크/WebView의 confused-deputy가 나옵니다.

> **진단편**: C07(DEX·multidex·resources.arsc)은 이미 다룬 개념이라 진단으로 대체합니다.

---

**다음** → [Tier 2 — Android Runtime](/posts/android-concept-atlas-tier2-runtime/) · [← Tier 0](/posts/android-concept-atlas-tier0-foundations/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
