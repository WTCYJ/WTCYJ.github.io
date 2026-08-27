---
layout: post
title: "Android Security Concept Atlas — Tier 9: 취약점 연구"
date: 2026-10-15 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier9, VulnerabilityResearch, CVD, 학습기록]
excerpt: "Atlas의 마지막 계층 — 앞의 여덟 층을 이해해 발견한 것을 어떻게 다루느냐입니다. 크래시와 익스플로잇을 구분하고, CWE/CVE/불리틴을 판독하고, 패치 diff로 변종을 찾고, 재현성과 위협모델을 세운 뒤 — 책임 있는 공개(CVD)로 세상에 안전하게 돌려줍니다."
---

> **Concept Atlas · Tier 9 — 취약점 연구 (Domain 10)**
> 6개 모듈 · 이 계층은 **발견을 다루고 돌려주는 법**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 8](/posts/android-concept-atlas-tier8-app-controls/)

Atlas의 마지막 계층입니다. 앞의 여덟 층을 이해해 무언가를 발견하는 것은 절반이고, 나머지 절반은 그것이 무엇인지 정직히 판정하고(C51), 분류하고(C52), 변종을 찾고(C53), 재현·영향을 세운 뒤(C54·C55) — **세상에 안전하게 돌려주는 것**(C56)입니다. 대부분이 내 CVE 재현 10편·24주 스터디에서 이미 다룬 방법론이라 진단으로, 마지막 캡스톤 C56만 풀글로 썼습니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C51 | crash·bug·vuln·exploit 구분 | 🟢 | 🧩 진단 | 크래시 ≠ 익스플로잇 가능 취약점 — 과대주장 금지 |
| C52 | CWE·CVE·Security Bulletin 판독 | 🟢 | 🧩 진단 | 불리틴은 개정 표기 없이 바뀐다 · 링크 커밋만 신뢰 |
| C53 | patch diff·variant analysis | 🟢 | 🧩 진단 | 태그 diff를 CVE 수정으로 읽지 말 것 · 회귀도 봐야 |
| C54 | 재현성·대조군 설계 | 🟢 | 🧩 진단 | 범위 좁게 잡고 단언 금지 · 대조군이 결론을 만든다 |
| C55 | 위협모델·실제 영향 산정 | 🟢 | 🧩 진단 | "가능"과 "실제 영향"을 구분 · 정부확인 vs 업계추정 |
| C56 | [responsible disclosure](/posts/android-concept-atlas-c56-responsible-disclosure/) | 🟡 | ✅ | CVD=비공개 제보→수정 시간→조율 공개; 재현 가능 최소 PoC |

## 이 계층의 서사

C51(무엇을 가졌나 — 크래시냐 익스플로잇 가능 취약점이냐)이 정직한 출발점이고, C52(분류 어휘)·C53(변종)·C54(재현)·C55(영향)가 그 발견을 리포트 가능한 형태로 만듭니다. 그리고 C56(책임 있는 공개)이 그것을 유지자가 고칠 수 있는 것으로 바꿉니다 — Android 플랫폼 버그는 Google Bug Hunters로, 앱 버그는 HackerOne으로, 좋은 리포트는 언제나 재현 가능한 최소 PoC와 정직한 영향("가끔 크래시"는 지고, "6바이트→OOB write, ASan 트레이스, 버전 X–Y"는 이깁니다). C29/C30/C36의 패치 갭 때문에 불리틴에 CVE가 실려도 곧 사용자 보호는 아니라는 것 — 그 간극이 우리가 계속 찾고 제보하는 이유입니다.

> **진단편**: C51~C55는 내 CVE 재현 시리즈·18~24주차 스터디에서 이미 다룬 방법론이라 진단으로 대체합니다. (그 교훈들 — 불리틴은 개정 표기 없이 바뀐다, 태그 diff를 CVE 수정으로 읽지 말라, 범위 좁게 잡고 단언 말라 — 이 계층의 뼈대입니다.)

---

## Atlas를 닫으며

Tier 0(보안 원칙)에서 시작해 프로세스·UID·권한, 패키징·서명, 런타임, IPC, 플랫폼 격리, 부팅 체인, Native·커널, 하드웨어 보안, 앱 통제를 거쳐 여기 — 취약점 연구와 책임 있는 공개 — 로 왔습니다. 부팅 첫 바이트부터 책임 있는 공개까지, 56개 모듈이 하나의 시스템 지도가 되었습니다.

**[← 마스터 인덱스로 돌아가기](/posts/android-concept-atlas-index/)** · [← Tier 8](/posts/android-concept-atlas-tier8-app-controls/)
