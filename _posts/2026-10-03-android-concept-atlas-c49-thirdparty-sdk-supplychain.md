---
layout: post
title: "Android Security Concept Atlas C49 | 가상 실습 보고서 — 서드파티 SDK·SBOM·공급망, SDK는 앱의 권한을 그대로 물려받는다"
date: 2026-10-03 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ThirdPartySDK, SupplyChain, SBOM, SPDX, CycloneDX, DependencyConfusion, SDKRuntime, ConceptAtlas, 학습기록]
excerpt: "앱에 넣은 광고·분석·크래시 SDK는 내 코드와 격리돼 있지 않습니다 - 같은 프로세스, 같은 UID, 앱의 모든 권한을 그대로 물려받죠. 사용자가 날씨 앱에 위치 권한을 줬다면, 그 앱에 박힌 SDK 15개에도 준 겁니다. 그래서 악성이거나 나중에 침해된 SDK 하나가 그걸 품은 수천 개 앱을 한꺼번에 뚫는 공급망 공격이 되고요(event-stream·Joker의 교훈). 게다가 개발자가 직접 고른 SDK 몇 개 아래로 전이 의존성 트리가 훨씬 크게 실리니, SBOM으로 실제 무엇이 들어갔는지 목록화해야 CVE를 추적할 수 있습니다. 격리 방법은 isolatedProcess(C25)와 Privacy Sandbox의 SDK Runtime뿐인데, 일반 SDK는 그냥 인프로세스 풀권한으로 돕니다. 내 의존성 감사 작업과 직결되는 Tier 8 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | Android 개인정보·보안·네트워크 설정 캡처, `curl --tlsv1.3`, 패키지·AppOps 조회 |
| 관측 결과 | 권한·개인정보 통제 화면과 TLS 1.3 HTTP 200 응답을 확인했다. 앱·호스트 네트워크 관측을 분리해 기록했다. |
| 검증 한계 | Play Integrity의 프로덕션 verdict, 실제 OAuth 공급자, 제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다. |

![C49 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C49 — 서드파티 SDK·SBOM·공급망
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 연구 · **선수 개념**: C06(APK/deps), C09(UID)
> **성격**: 공식 문서·공개 소스 기준 재검토.

C09에서 앱이 UID로 격리된다 했습니다. 그런데 그 UID **안에는** 격리가 없습니다 — 앱에 넣은 SDK는 내 코드와 같은 UID·권한을 씁니다. 그 함의가 이 편입니다.

한 문장으로: **in-process 서드파티 SDK는 일반적으로 host 앱의 UID와 허용된 권한 범위에서 실행되므로, SDK 결함과 공급망 침해가 host 앱의 데이터와 기능으로 이어질 수 있습니다.** 별도 프로세스·SDK Runtime 같은 예외도 함께 구분합니다.

## 배경 개념

- **핵심 통찰**: SDK = 앱의 **같은 UID·전체 권한**(라이브러리별 격리 없음).
- **공급망**: 전이 의존성 트리(Gradle/Maven 재귀) — 실린 코드 ≫ 직접 고른 것.
- **SBOM**: 컴포넌트+버전 인벤토리(SPDX/CycloneDX) — CVE 추적.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

앱 **공급망 위험**입니다. C06(APK/deps)·C09(SDK가 앱 UID 공유)·C10(SDK가 앱 권한 상속)이 여기서 만나고, 리버싱 시 의존성 트리 감사가 이 편.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **격리 없음**: dexing/링크 후 SDK의 클래스·네이티브 `.so`는 **같은 APK·같은 프로세스**에 로드. Android 샌드박스 경계는 **패키지당 UID**(C09) — 내 코드와 SDK 사이엔 권한 경계도 ClassLoader 벽도 없음.
- **권한 상속**: SDK는 앱의 런타임/설치 권한 **전체**(C10)를 씀. 위치·연락처·카메라·저장소를 별도 동의 없이.
- **접근 범위**: 앱 사설 데이터(`/data/data/<pkg>`), 프로세스 메모리(토큰/키), 네트워크를 **앱으로서**.
- **전이 의존성**: Gradle이 Maven에서 각 dep의 dep를 재귀 해소 → 실린 트리가 직접 선언보다 훨씬 큼.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **앱 실제 표면 = 자기 코드 ∪ 모든 SDK**. 사용자가 앱에 준 권한은 **모든 SDK에** 준 것.
- **신뢰하면 안 되는 것들**:
  - **"SDK는 내 코드와 격리돼 있다"** — 같은 프로세스·UID입니다. 라이브러리별 스코핑이 없습니다.
  - **"사용자가 앱에만 권한을 줬다"** — 그 앱의 **모든 SDK**에도 준 것(예: 날씨 앱 위치 = 그 앱 + 15개 SDK).
  - **"내가 선언한 SDK만 실린다"** — **전이 트리**가 훨씬 큽니다. 오염은 깊은 dep(typosquat·**dependency-confusion**·유지자 하이재크)에서 조용히.
  - **"Play Data Safety가 보장한다"** — **자기 신고**입니다(런타임 강제 아님). SDK는 신고보다 더 할 수 있습니다.
  - **"isolatedProcess가 유일한 격리법"** — 아닙니다. **Privacy Sandbox의 SDK Runtime**(A13+)이 광고/분석 SDK를 **별도 격리 프로세스**로 실행하는 두 번째 메커니즘. 단 일반 SDK는 여전히 **인프로세스 풀권한**(isolatedProcess C25는 파서/렌더러용이라 SDK엔 실용적이지 않음).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 개발자가 `build.gradle`에 직접 dep 선언 → Maven이 전이 재귀 해소 → APK에 큰 트리.
- **SBOM**: 산출물의 컴포넌트+정확한 버전 인벤토리(SPDX/CycloneDX) — CVE 추적·라이선스·프로버넌스.
- **방어**: Gradle dependency verification(체크섬+PGP를 `verification-metadata.xml`에 고정) · 버전 pinning(동적 `+` 금지) · SDK 최소화 · 재현 빌드.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **악성/침해 SDK**: 앱 스케일로 PII·클립보드·설치앱목록·위치 유출(스파이웨어 SDK 다수, **Joker/Bread**는 SDK형 페이로드+동적 로딩 C14).
- **전이 dep 오염**: **event-stream**(2018, 깊은 dep에 악성 주입) · **dependency-confusion**(Birsan 2021)이 Maven에도 그대로.
- **CVE 있는 번들 lib**: SBOM 없으면 log4shell식 스크램블 — 무엇을 실었는지 몰라 대응 불가.
- **증폭**: 공격 노력 O(1)(SDK 하나) → 영향 O(N)(수천 앱). "이 라이브러리 안전?"이 "이 벤더의 릴리스·업데이트 파이프라인 전체를 영원히 신뢰?"로.

## 질문 6 — Android/표준 버전에 따라 무엇이 달라졌는가

- **Gradle dependency verification**: 6.2+.
- **SBOM 표준**: **ISO/IEC 5962:2021 = SPDX 2.2.1**(2.3/3.0은 이후 non-ISO 개정), CycloneDX 1.6(2024). NTIA 최소요소는 SPDX·CycloneDX·**SWID** 3종 인정.
- **Privacy Sandbox SDK Runtime**: A13(2022 프리뷰)~확대 — 광고/분석 SDK 격리 실행.
- **Play App Signing**(C08): Google이 최종 재서명 → 프로버넌스는 그 단계까지 포함.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- **APK에서 SDK 열거**: 패키지 prefix(`com.google.firebase`·`com.facebook`·`com.applovin`…), `lib/<abi>/*.so`, **병합된 AndroidManifest**(SDK가 자기 컴포넌트/권한 추가).
- **소스 있으면**: `./gradlew :app:dependencies`(전이 트리 전체 — 선언과의 차이가 미감사 표면), `verification-metadata.xml`.
- **트래커**: Exodus Privacy(앱별 트래커 리포트), 알려진 취약 버전 정적 스캐너.

**주의**: 아키텍처 무관 → **에뮬레이터/데스크톱에서 apktool·패키지 prefix·gradle deps로 SDK 감사 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C06(APK/deps)**: SDK·전이 dep가 그 APK에.
- **C09(UID)·C10(권한)**: SDK가 그 UID·권한을 상속 — 이 편의 뿌리.
- **C08(Play App Signing)**: 최종 재서명이 프로버넌스에.
- **C25(isolatedProcess)** + SDK Runtime: 유이한 격리 수단.
- **C14(DCL)**: 침해 SDK가 런타임 코드 로딩과 결합.
- 다음은 개인정보 최소화 **C50** 등으로.

## 직접 그릴 수 있는 호출 흐름

```
[ SDK는 앱의 권한을 물려받는다 (격리 없음) ]

  앱 프로세스 (단일 UID, C09)
    ├ 내 코드
    ├ 광고 SDK ─┐
    ├ 분석 SDK  ├─ 전부 같은 UID + 앱 전체 권한(C10) 공유
    └ 크래시 SDK┘   /data/data · 메모리(토큰/키) · 네트워크를 앱으로서
        └ 라이브러리별 경계 없음 → 앱 표면 = 내코드 ∪ 모든 SDK

  공급망: build.gradle 직접 dep ─▶ Maven 전이 재귀 ─▶ 큰 트리
        오염: typosquat / dependency-confusion / 유지자 하이재크 (깊은 dep)
        방어: dependency verification(체크섬+PGP) · pinning · SBOM(CVE추적) · 최소화

  격리 수단(예외): isolatedProcess(C25, 파서용) · SDK Runtime(Privacy Sandbox)
     ✗ 일반 SDK는 인프로세스 풀권한
  증폭: O(1) SDK 침해 → O(N) 앱 (Joker/event-stream)
```

## 오개념 판별 문제 5개

1. "앱에 넣은 서드파티 SDK는 내 코드와 격리돼, 별도 권한 안에서만 동작한다."
2. "사용자가 앱에 위치 권한을 준 것은 그 앱에만 준 것이다."
3. "내가 build.gradle에 적은 SDK만 앱에 실린다."
4. "Play Data Safety 신고를 보면 SDK가 무슨 데이터를 쓰는지 확실히 알 수 있다."
5. "in-app 코드를 격리하는 방법은 isolatedProcess뿐이다."

<details><summary>판정 기준(펼치기)</summary>

1. **같은 프로세스·UID·전체 권한**입니다. 라이브러리별 격리가 없습니다.
2. 그 앱의 **모든 SDK**에도 준 것입니다(권한은 패키지 단위).
3. **전이 의존성 트리**가 훨씬 큽니다(`./gradlew :app:dependencies`로 확인).
4. Data Safety는 **자기 신고**입니다(런타임 강제 아님). 실제와 다를 수 있습니다.
5. **Privacy Sandbox의 SDK Runtime**(A13+)도 있습니다. 단 일반 SDK는 인프로세스 풀권한.
</details>

## 서술형 문제 3개

1. SDK가 앱과 같은 UID·권한으로 도는 것(격리 없음)이 왜 공급망 위험의 뿌리인지, "앱 표면 = 내코드 ∪ 모든 SDK"로 서술하세요.
2. 전이 의존성 트리가 왜 미감사 표면인지, event-stream/dependency-confusion을 예로 서술하고 SBOM·dependency verification이 무엇을 막는지 설명하세요.
3. 하나의 침해된 SDK가 왜 O(N) 앱 규모의 공격이 되는지, Joker 같은 사례와 함께 서술하세요.

## 소스·정적 검증 경로

- 소유/허가 앱을 apktool로 열어 패키지 prefix·`lib/<abi>`·병합 매니페스트로 임베디드 SDK를 열거하세요.
- (소스 있으면) `./gradlew :app:dependencies`로 전이 트리를 떠서 직접 선언과의 차이(미감사 표면)를 확인하세요.
- Exodus로 앱의 트래커를 조회하고, 각 SDK가 앱의 어떤 권한을 상속하는지 정리하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 출력·화면만** 붙입니다.

1. **열거 실측**: apktool/패키지 prefix로 임베디드 SDK 목록을.
2. **트리 실측**: `./gradlew :app:dependencies`의 전이 트리를(또는 Exodus 리포트).
3. **권한 서술**: SDK가 상속하는 앱 권한을 매핑해 "앱 표면 = 내코드 ∪ SDK"를.
4. **연결**: 침해 SDK가 왜 공급망 공격인지(event-stream/Joker).

각 단계는 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

앱에 넣은 광고·분석·크래시 SDK는 내 코드와 격리돼 있지 않습니다 — 같은 프로세스, 같은 UID, 앱의 모든 권한을 그대로 물려받죠. 사용자가 날씨 앱에 위치 권한을 줬다면 그 앱에 박힌 SDK들에도 준 겁니다. 그래서 악성이거나 나중에 침해된 SDK 하나가 그걸 품은 수천 개 앱을 한꺼번에 뚫는 공급망 공격이 됩니다(event-stream·Joker의 교훈). 게다가 직접 고른 SDK 몇 개 아래로 전이 의존성 트리가 훨씬 크게 실리니, SBOM으로 실제 무엇이 들어갔는지 목록화해야 CVE를 추적할 수 있습니다. 격리 수단은 isolatedProcess(C25)와 Privacy Sandbox의 SDK Runtime뿐인데, 일반 SDK는 그냥 인프로세스 풀권한으로 돕니다. 다음은 개인정보 최소화와 권한 모델 변화 **C50**으로 이어집니다.
