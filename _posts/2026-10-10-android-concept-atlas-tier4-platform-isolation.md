---
layout: post
title: "Android Security Concept Atlas Tier 4 | 학습 로드맵 — 플랫폼 격리"
date: 2026-10-10 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier4, SELinux, Sandbox, 학습기록]
excerpt: "UID 격리(Tier 1) 위에 겹치는 심층방어 층입니다. SELinux MAC이 매 접근을 강제하고, seccomp·capability·namespace가 리눅스 컨테이너 프리미티브로 반경을 더 좁히며, isolatedProcess가 최강 인앱 샌드박스를 만듭니다. 다만 caps를 비워도 커널 메모리 손상 익스플로잇은 못 막습니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 4의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: `id`, `cat /proc/self/attr/current`, `/proc/self/status`. 서로 다른 UID, `untrusted_app` SELinux 컨텍스트, 0 capability, seccomp 필터를 앱 프로세스 내부에서 확인했다. 정책 우회나 샌드박스 탈출은 수행하지 않았고, 접근 거부는 실패가 아니라 격리 통제가 작동한 대조군이다.

![Tier 4 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 4 — 플랫폼 격리 (Domain 6)**
> 4개 모듈 · 이 계층은 **UID 위에 겹치는 심층방어**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 3](/posts/android-concept-atlas-tier3-ipc-framework/) · 다음 → [Tier 5 부팅 체인](/posts/android-concept-atlas-tier5-boot-chain/)

C09의 UID DAC가 앱↔앱 1차 경계라면, 이 계층은 그 위에 겹치는 강제적 층입니다. SELinux MAC(C23)이 매 접근을 정책과 대조하고, seccomp·caps·namespace(C24)가 시스템 콜·능력·저장소 뷰를 좁히며, isolatedProcess(C25)가 그 프리미티브를 극단으로 조여 위험 코드를 담습니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C23 | [SELinux domain·type·allow·neverallow](/posts/android-concept-atlas-c23-selinux-policy/) | 🟡 | ✅ | MAC·deny-by-default; 앱-대-앱은 TE 아닌 **MLS 카테고리**로 |
| C24 | [seccomp·namespaces·cgroups·capabilities](/posts/android-concept-atlas-c24-seccomp-namespaces-cgroups-capabilities/) | 🔴 | ✅ | 심층방어 층; **caps 비움도 커널 메모리손상 익스는 못 막음** |
| C25 | [isolatedProcess·app zygote](/posts/android-concept-atlas-c25-isolatedprocess-appzygote/) | 🔴 | ✅ | 최강 인앱 샌드박스; 격리 UID 90000~99999, isolated_app 도메인 |
| C26 | [샌드박스 vs SELinux 역할 구분](/posts/android-concept-atlas-c26-uid-sandbox-vs-selinux/) | 🟢 | ✅ | DAC(임의)와 MAC(강제)은 별개 층 — 뭉뚱그리면 안 됨 |

## 이 계층의 서사

C23(SELinux)이 이 계층의 중심 — root조차 정책에 묶는 강제적 MAC이고, deny-by-default가 fail-safe defaults(C03)의 실현입니다. C24가 그 위에 리눅스 컨테이너 프리미티브(seccomp·caps 0·mount ns)를 겹치는데, 중요한 정직함은 "이건 심층방어지 대체가 아니고, caps를 비워도 커널 메모리 손상 익스플로잇(cred 덮어쓰기)은 못 막는다"는 것입니다. C25는 그 프리미티브를 극단화해 "뚫려도 쓸모없는" 격리 프로세스(WebView 렌더러)를 만듭니다.

> **완성 보고서**: C26은 UID 샌드박스와 SELinux가 서로 다른 계층에서 강제되는 모습을 앱 UID·도메인·접근 거부로 확인했습니다.

---

**다음** → [Tier 5 — 부팅·업데이트 체인](/posts/android-concept-atlas-tier5-boot-chain/) · [← Tier 3](/posts/android-concept-atlas-tier3-ipc-framework/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
