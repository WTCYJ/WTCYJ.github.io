---
layout: post
title: "Android Security Concept Atlas — Tier 3: IPC·프레임워크"
date: 2026-10-09 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier3, Binder, IPC, 학습기록]
excerpt: "프로세스들이 어떻게 대화하는가 — Binder가 커널이 각인한 위조 불가 호출자 UID로 트랜잭션을 나르고, handle 0의 servicemanager가 이름으로 서비스를 찾게 하며, 4대 컴포넌트가 그 위에서 연결됩니다. exported 게이트가 앱 펜테스트의 핵심 공격면입니다."
---

> **Concept Atlas · Tier 3 — IPC·프레임워크 (Domain 5)**
> 6개 모듈 · 이 계층은 **프로세스 간 대화와 그 신뢰**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 2](/posts/android-concept-atlas-tier2-runtime/) · 다음 → [Tier 4 플랫폼 격리](/posts/android-concept-atlas-tier4-platform-isolation/)

격리된 프로세스(Tier 2)가 서로 통신해야 할 때의 계층입니다. Binder(C17)가 그 채널이고, servicemanager/system_server(C19)가 서비스 레지스트리이며, AIDL/HIDL(C20)이 인터페이스를, 4대 컴포넌트(C21)가 그 위의 앱 표면을 이룹니다. 핵심 보안 자산은 **커널이 각인한 위조 불가 호출자 UID**입니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C17 | [Binder driver·handle·node·transaction](/posts/android-concept-atlas-c17-binder-driver/) | 🟡 | ✅ | 커널이 각인한 **effective** 호출자 UID; Bad Binder는 race 아닌 UAF |
| C18 | Parcel 직렬화·read/write 불일치 | 🟢 | 🧩 진단 | 쓰기/읽기 순서 불일치가 타입 혼동·메모리 손상으로 |
| C19 | [servicemanager·system_server](/posts/android-concept-atlas-c19-servicemanager-systemserver/) | 🟡 | ✅ | handle 0 신뢰 앵커; system_server=UID 1000(root 아님, SELinux 제한) |
| C20 | [AIDL·HIDL·HAL](/posts/android-concept-atlas-c20-aidl-hidl-hal/) | 🔴 | ✅ | 인터페이스 계약; vndbinder=벤더-대-벤더, HIDL 폐기 진행 |
| C21 | [4대 컴포넌트↔Binder 연결](/posts/android-concept-atlas-c21-components-binder/) | 🟡 | ✅ | exported가 절대 게이트(=false는 같은 UID만); 액티비티는 A10+ ATMS |
| C22 | caller UID/PID·identity clearing·confused deputy | 🟢 | 🧩 진단 | `clearCallingIdentity` 오용이 confused-deputy로 |

## 이 계층의 서사

C17(Binder)이 모든 IPC의 바닥이고, 그 위에서 C19(servicemanager)가 handle 0으로 서비스를 찾게 하며 system_server가 대부분의 프레임워크 서비스를 담습니다(뚫려도 root는 아님). C20(AIDL/HIDL)이 계약을, C21이 앱의 4대 컴포넌트를 그 IPC에 연결합니다 — 그리고 **exported+android:permission**이 그 문을 여닫는데, 이게 내 앱 펜테스트에서 제일 먼저 세는 공격면입니다. 이 모든 검사가 의미 있는 건 커널이 호출자 UID를 위조 불가로 각인하기 때문입니다.

> **진단편**: C18(Parcel read/write 불일치, CVE 재현 9)·C22(호출자 UID·confused deputy, 20~24주차)는 이미 다뤄 진단으로 대체합니다.

---

**다음** → [Tier 4 — 플랫폼 격리](/posts/android-concept-atlas-tier4-platform-isolation/) · [← Tier 2](/posts/android-concept-atlas-tier2-runtime/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
