---
layout: post
title: "Android Security Concept Atlas Tier 1 | 학습 로드맵 — 앱·패키징"
date: 2026-10-07 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier1, 패키징, 학습기록]
excerpt: "앱이 무엇으로 만들어지고(APK/AAB), 무엇으로 신원을 증명하며(서명), 어떤 격리(UID)와 권능(권한)을 받고, 서로를 어떻게 보고 넘기는가(가시성·URI)를 다룹니다. 앱↔앱 1차 경계는 UID DAC이고, 서명자 인증서가 앱의 안정적 정체성입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 1의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: `javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r`. 증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다. AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다.

![Tier 1 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/apps.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 1 — 앱·패키징 (Domain 3)**
> 6개 모듈 · 이 계층은 **앱의 정체성과 격리**를 세웁니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 0](/posts/android-concept-atlas-tier0-foundations/) · 다음 → [Tier 2 런타임](/posts/android-concept-atlas-tier2-runtime/)

Tier 0의 프로세스(C04) 위에 정체성(UID)과 권능(권한)을 얹는 계층입니다. 앱이 무엇으로 포장되고(C06), 무엇으로 신원을 증명하며(C08), 어떤 UID 샌드박스(C09)와 권한(C10)을 받고, 서로를 어떻게 보고 데이터를 넘기는지(C11)를 순서대로 세웁니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C06 | [APK·AAB·Split APK](/posts/android-concept-atlas-c06-apk-aab-split/) | 🟡 | ✅ | APK=설치 ZIP, AAB=발행 포맷(설치 불가); split은 같은 키·한 UID |
| C07 | [DEX·multidex·resources.arsc](/posts/android-concept-atlas-c07-dex-multidex-resources-arsc/) | 🟢 | ✅ | 단일 DEX의 64K 메서드 참조 한도·컴파일된 리소스 |
| C08 | [서명 v1~v4·키 순환](/posts/android-concept-atlas-c08-apk-signing/) | 🟡 | ✅ | 서명자 인증서=앱 정체성; v1 갭이 Janus, v2가 전체파일 |
| C09 | [UID·sharedUserId·샌드박스](/posts/android-concept-atlas-c09-uid-sandbox/) | 🟡 | ✅ | 앱↔앱 1차 경계는 UID DAC(SELinux는 그 위 별개 층) |
| C10 | [permission·signature perm·AppOps](/posts/android-concept-atlas-c10-permissions-appops/) | 🟡 | ✅ | 권한은 UID에 부여; `checkCallingOrSelfPermission`의 자기-폴백 함정 |
| C11 | [package visibility·URI permission](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) | 🟡 | ✅ | 가시성은 targetSdk30 게이트; URI 위임은 confused-deputy 벡터 |

## 이 계층의 서사

C06(포장)에서 시작해 C08(서명=정체성)이 "이 앱은 누구인가"를 확립하면, C09(UID)가 그 정체성에 격리를, C10(권한)이 권능을 얹습니다. sharedUserId(C09)·signature 권한(C10)·업데이트가 전부 "같은 서명 키"(C08)로 결정된다는 게 이 계층의 접착제입니다. 마지막으로 C11이 앱 간 관찰(가시성)과 위임(URI 권한)을 다루는데, 여기서 딥링크/WebView의 confused-deputy가 나옵니다.

> **완성 보고서**: C07은 DEX·multidex·resources.arsc를 APK 정적 분석 결과와 함께 정리했습니다.

---

**다음** → [Tier 2 — Android Runtime](/posts/android-concept-atlas-tier2-runtime/) · [← Tier 0](/posts/android-concept-atlas-tier0-foundations/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
