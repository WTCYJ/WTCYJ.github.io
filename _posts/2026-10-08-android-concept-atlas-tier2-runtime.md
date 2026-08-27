---
layout: post
title: "Android Security Concept Atlas — Tier 2: Android Runtime"
date: 2026-10-08 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier2, ART, Runtime, 학습기록]
excerpt: "앱이 실제로 어떻게 태어나고(Zygote) 실행되는가(ART) — 그리고 리버서에게 왜 DEX가 진실의 원천이며, '정적으로 보이는 것 ≠ 실제 실행'의 진짜 원인이 JIT/AOT가 아니라 동적 코드 로딩(패커)인가를 다룹니다. 내 Toss 패커 작업과 직결되는 계층입니다."
---

> **Concept Atlas · Tier 2 — Android Runtime (Domain 4)**
> 5개 모듈 · 이 계층은 **앱의 탄생과 실행**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 1](/posts/android-concept-atlas-tier1-app-packaging/) · 다음 → [Tier 3 IPC](/posts/android-concept-atlas-tier3-ipc-framework/)

Tier 1의 앱(APK+UID)이 어떻게 살아 움직이는지의 계층입니다. Zygote가 프로세스를 찍어내고(C12), ART가 DEX를 실행하며(C13), ClassLoader가 코드를 로드하고(C14), 그 실행 형태(JIT/AOT)가 분석에 차이를 만듭니다(C16). 리버싱 방법론의 뼈대가 여기 있습니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C12 | [Zygote·앱 프로세스 생성](/posts/android-concept-atlas-c12-zygote/) | 🟡 | ✅ | fork-without-exec + COW; seccomp는 uid 드롭 *전*, 공유 ASLR 약점 |
| C13 | [ART: DEX→OAT→VDEX](/posts/android-concept-atlas-c13-art-dex-oat-vdex/) | 🟡 | ✅ | DEX가 진실의 원천(VDEX에 보존); OAT는 파생 캐시 |
| C14 | [class loading·reflection](/posts/android-concept-atlas-c14-classloader-reflection/) | 🟡 | ✅ | 동적 코드 로딩(패커)이 정적 APK 분석을 stub만 보게 만듦 |
| C15 | JNI 경계·native lib loading | 🟢 | 🧩 진단 | 네이티브 `.so`는 DEX 파이프라인 밖의 별개 표면 |
| C16 | [JIT/AOT와 분석 결과 차이](/posts/android-concept-atlas-c16-jit-aot-analysis/) | 🟡 | ✅ | 세 실행 모드는 의미 동일; "정적≠실행"은 DCL/리플렉션/JNI 탓 |

## 이 계층의 서사

C12(Zygote)가 모든 앱 프로세스를 미리 로드된 템플릿에서 fork하고(그 specialization 순서가 보안의 핵심), C13(ART)이 그 안에서 DEX를 실행합니다. 리버서에게 중요한 세 사실이 여기 모입니다: **DEX가 원천**(C13)이고, **동적 코드 로딩이 정적 분석을 무력화**하며(C14), **JIT/AOT는 의미를 안 바꾸니 "정적≠실행"의 원인은 DCL/JNI**(C16)입니다. 내 Toss 패커 분석이 정확히 이 세 축 위에 섭니다.

> **진단편**: C15(JNI 경계·native lib loading)는 13~14주차에서 다룬 개념이라 진단으로 대체합니다.

---

**다음** → [Tier 3 — IPC·프레임워크](/posts/android-concept-atlas-tier3-ipc-framework/) · [← Tier 1](/posts/android-concept-atlas-tier1-app-packaging/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
