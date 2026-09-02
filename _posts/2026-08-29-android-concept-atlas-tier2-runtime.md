---
layout: post
title: "Android Security Concept Atlas Tier 2 | 학습 로드맵 — Android Runtime"
date: 2026-08-29 23:11:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier2, ART, Runtime, 학습기록]
excerpt: "앱이 실제로 어떻게 태어나고(Zygote) 실행되는가(ART) — 그리고 리버서에게 왜 DEX가 진실의 원천이며, '정적으로 보이는 것 ≠ 실제 실행'의 진짜 원인이 JIT/AOT가 아니라 동적 코드 로딩(패커)인가를 다룹니다. 내 상용 앱 패커 작업과 직결되는 계층입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 2의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: `getprop ro.zygote`, `getprop dalvik.vm.usejit`, `ps`. `zygote64`와 JIT 활성 상태를 확인했다. 비특권 앱의 전체 프로세스 열람 제한도 함께 관측했다. OAT/VDEX 생성 정책은 빌드와 프로파일 상태에 따라 달라지므로 이 한 번의 캡처를 모든 Android 버전에 일반화하지 않는다.

![Tier 2 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/evidence-runtime.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






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
| C15 | [JNI 경계·native lib loading](/posts/android-concept-atlas-c15-jni-native-library-loading/) | 🟢 | ✅ | 네이티브 `.so`는 DEX 파이프라인 밖의 별개 표면 |
| C16 | [JIT/AOT와 분석 결과 차이](/posts/android-concept-atlas-c16-jit-aot-analysis/) | 🟡 | ✅ | 세 실행 모드는 의미 동일; "정적≠실행"은 DCL/리플렉션/JNI 탓 |

## 이 계층의 서사

C12(Zygote)가 모든 앱 프로세스를 미리 로드된 템플릿에서 fork하고(그 specialization 순서가 보안의 핵심), C13(ART)이 그 안에서 DEX를 실행합니다. 리버서에게 중요한 세 사실이 여기 모입니다: **DEX가 원천**(C13)이고, **동적 코드 로딩이 정적 분석을 무력화**하며(C14), **JIT/AOT는 의미를 안 바꾸니 "정적≠실행"의 원인은 DCL/JNI**(C16)입니다. 내 상용 앱 패커 분석이 정확히 이 세 축 위에 섭니다.

> **완성 보고서**: C15는 Java→JNI→x86_64 네이티브 라이브러리 왕복 호출을 실제 앱으로 검증했습니다.

---

**다음** → [Tier 3 — IPC·프레임워크](/posts/android-concept-atlas-tier3-ipc-framework/) · [← Tier 1](/posts/android-concept-atlas-tier1-app-packaging/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
