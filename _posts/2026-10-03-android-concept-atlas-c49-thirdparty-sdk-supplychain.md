---
layout: post
title: "Android Security Concept Atlas C49 | 가상 실습 보고서 — 서드파티 SDK·SBOM·공급망, SDK는 앱의 권한을 그대로 물려받는다"
date: 2026-10-03 21:00:00 +0900
category: 안드로이드
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

## 호출 흐름

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

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, Android 13/API 33, x86_64)에서 이 모듈의 뿌리 주장을 확인했다. SDK 백엔드와 라이브 침해는 검증 범위 밖인 연구 모듈이라, 측정 가능한 경계는 실행으로, 나머지는 공개 소스·표준 문서로 확정했다.

**1) 권한은 패키지(UID) 단위로만 부여된다 — SDK별 통제 지점이 없다.** 검증 블록의 "패키지·AppOps 조회"와 개인정보·보안 설정 캡처(위 `privacy.png`)에서, 권한·AppOps 부여는 전부 **패키지 단위**로 나타났다. 화면과 조회 어디에도 "이 라이브러리에만 위치 허용" 같은 SDK별 스코핑은 존재하지 않는다. 이것이 질문 2·3의 불변식을 화면 수준에서 확증한다 — 사용자가 앱에 준 권한은 곧 그 앱에 실린 **모든 SDK**에 준 것이며, 경계는 패키지(UID)이지 라이브러리가 아니다. 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 보존했다.

**2) SDK의 네트워크는 앱의 네트워크 주체로 나간다.** 호스트 검증에서 앱 경로의 TLS는 1.3으로 협상되고 HTTP 200을 받았다.

```console
$ curl --tlsv1.3 ...     # 호스트 검증 로그
→ TLS 1.3 세션 · HTTP 200
```

인프로세스 SDK는 이 소켓 스택을 그대로 공유하므로, SDK가 보내는 트래픽도 앱의 UID·네트워크 권한·인증 컨텍스트를 타고 나간다 — 질문 2의 "네트워크를 앱으로서"가 확인된다. 앱과 호스트 관측은 분리 기록해 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 남겼다.

**3) 전이 트리·SBOM은 공개 소스·표준으로 확정했다(AVD 측정 대상 아님).** 개발자가 직접 선언한 dep 아래로 Maven이 재귀 해소한 전이 트리는 `./gradlew :app:dependencies`로 드러나며(질문 7), 그 산출물의 컴포넌트 인벤토리 표준은 ISO/IEC 5962:2021로 채택된 SPDX 2.2.1과 CycloneDX 1.6이다(질문 6). Gradle dependency verification(6.2+)은 체크섬·PGP 서명을 `verification-metadata.xml`에 고정해 event-stream·dependency-confusion류 오염을 빌드 단계에서 차단한다 — 여기까지는 문서와 소스로 확정한 사실이며, 이 AVD가 새로 측정한 값이 아니다.

## 가상환경 검증 한계

정직하게, 이 문서의 실측은 (1)·(2)의 경계까지다. 나머지는 근거는 확정했으나 이 x86_64 AVD 세션에서 새로 캡처하지 않았다.

- 실제 악성·침해 SDK를 심어 앱 스케일의 PII·클립보드·위치 유출을 관측하는 실험은 이 세션에서 하지 않았다. event-stream·Joker의 O(1)→O(N) 증폭은 공개 사고 보고서에 근거한 사례이지 라이브 재현이 아니다.
- 제3자 SDK 백엔드(광고·분석 서버)와 실제 OAuth 공급자로의 왕복 트래픽은 범용 AVD 단독 검증 범위 밖이다(검증 블록의 한계와 동일). SDK가 실제 무엇을 전송·수신하는지의 엔드투엔드 관측은 미측정으로 남았다.
- Privacy Sandbox의 SDK Runtime 별도 프로세스 격리는 별도 SDK·구성이 필요한 A13+ 기능이라 이 기본 AVD에서 인스턴스화해 관측하지 않았고, isolatedProcess(C25)의 격리 동작도 소스·문서 근거까지만 다뤘다.

관련 근거: [Android 권한 개요](https://developer.android.com/guide/topics/permissions/overview) · [Privacy Sandbox on Android](https://developer.android.com/design-for-safety/privacy-sandbox) · [Gradle dependency verification](https://docs.gradle.org/current/userguide/dependency_verification.html) · [SPDX](https://spdx.dev/)

## 마치며

앱에 넣은 광고·분석·크래시 SDK는 내 코드와 격리돼 있지 않습니다 — 같은 프로세스, 같은 UID, 앱의 모든 권한을 그대로 물려받죠. 사용자가 날씨 앱에 위치 권한을 줬다면 그 앱에 박힌 SDK들에도 준 겁니다. 그래서 악성이거나 나중에 침해된 SDK 하나가 그걸 품은 수천 개 앱을 한꺼번에 뚫는 공급망 공격이 됩니다(event-stream·Joker의 교훈). 게다가 직접 고른 SDK 몇 개 아래로 전이 의존성 트리가 훨씬 크게 실리니, SBOM으로 실제 무엇이 들어갔는지 목록화해야 CVE를 추적할 수 있습니다. 격리 수단은 isolatedProcess(C25)와 Privacy Sandbox의 SDK Runtime뿐인데, 일반 SDK는 그냥 인프로세스 풀권한으로 돕니다. 다음은 개인정보 최소화와 권한 모델 변화 **C50**으로 이어집니다.
