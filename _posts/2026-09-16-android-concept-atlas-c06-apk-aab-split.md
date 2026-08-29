---
layout: post
title: "Android Security Concept Atlas C06 | 가상 실습 보고서 — APK·AAB·Split APK, 설치 단위와 발행 포맷"
date: 2026-09-16 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, APK, AAB, AppBundle, SplitAPK, PlayAppSigning, bundletool, AXML, ConceptAtlas, 학습기록]
excerpt: "리버서가 앱을 분석할 때 처음 여는 게 APK인데, 그건 사실 ZIP 하나입니다 - AXML로 컴파일된 매니페스트, classes.dex, resources.arsc, lib/<abi>/, META-INF. 그런데 요즘 Play 앱은 개발자가 .aab(App Bundle)를 올리면 Play가 기기별로 split APK를 생성·서명하죠. 핵심 함정 셋: AAB는 설치되는 게 아니라 발행 포맷이고, 한 앱이 base + config split + 동적 기능으로 여러 APK로 설치되며(전부 같은 키·한 UID이라 base만 분석하면 코드를 놓친다), Play App Signing이면 기기에 실리는 서명 키는 개발자가 아니라 Google이 쥡니다. Tier 1 앱·패키징의 토대 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r` |
| 관측 결과 | 증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다. |
| 검증 한계 | AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다. |

![C06 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/apps.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C06 — APK·AAB·Split APK
> **계층**: Tier 1 (앱·패키징) · **난이도**: 기초 · **선수 개념**: 없음(패키징 토대)
> **성격**: 보완 편 — 경험 독자용 압축 리프레셔.

C08(서명)·C07(DEX)·C09(UID)가 전부 "APK"라는 단위를 전제합니다. 그 단위가 정확히 무엇이고, 요즘 왜 여러 조각으로 설치되는지가 이 편입니다.

한 문장으로: **APK는 설치·실행되는 ZIP 단위이고, AAB는 Play에 올리는 발행 포맷(설치 불가)이며, 한 앱은 같은 키로 서명된 여러 split APK로 설치되어 런타임에 하나로 합쳐진다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **APK**: ZIP 아카이브. **설치/실행 단위**.
- **AAB(App Bundle)**: `.aab` 발행 포맷. **설치 안 됨** — Play/bundletool이 기기별 split 생성·서명.
- **Split APK**: base + config split(ABI/밀도/언어) + 동적 기능. 한 패키지·한 UID·**같은 키**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**리버서가 처음 여는 단위**이자, C07(DEX)·C08(서명)·C09(패키지/UID)가 전부 스코프하는 그 ZIP입니다. 발행(AAB)과 설치(APK/split)를 혼동하는 게 이 영역 최대의 범주 오류입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **APK 내부**(ZIP 멤버): `AndroidManifest.xml`(**컴파일된 바이너리 XML=AXML**, 텍스트 아님), `classes.dex`(+`classes2.dex`… 멀티덱스), `resources.arsc`(컴파일된 리소스 테이블), `res/`(리소스), `assets/`(**원형 바이트**), `lib/<abi>/*.so`, `META-INF/`(v1 서명 파일 등).
- **설치**: `PackageInstaller`가 설치. split이면 `install-multiple`로 함께.
- **AAB→split**: 개발자가 `.aab` 업로드 → Play(또는 로컬 `bundletool build-apks`)가 기기 설정(밀도/ABI/언어)에 맞는 split만 생성·서명.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **신뢰할 것**: 한 앱의 모든 split은 **한 패키지·한 UID(C09)·같은 서명 인증서(C08)**입니다. 이게 공격자가 키 없이 넘을 수 없는 불변식.
- **신뢰하면 안 되는 것들**:
  - **"AAB는 설치 가능한 새 APK다"** — 발행 전용입니다. 기기엔 Play/bundletool이 유도한 split이 설치됩니다.
  - **"매니페스트·리소스를 APK에서 텍스트로 읽는다"** — `AndroidManifest.xml`과 XML 리소스는 **AXML로 컴파일**(aapt2/apktool 필요). 단 **래스터 리소스(PNG/WebP/JPEG/9-patch)는 원형**, `assets/`도 원형.
  - **"64K 한도는 앱이 정의한 메서드 수"** — 단일 DEX의 **메서드 참조** 상한(프레임워크/라이브러리 참조 포함)입니다.
  - **"v4 서명도 서명 블록에 있다"** — **v2/v3만** APK Signing Block에. v4는 **별도 `<apk>.apk.idsig` 사이드카**(C08).
  - **"base APK만 분석하면 된다"** — split이 코드/리소스를 나눠 갖습니다. **모든 split을 당겨** 재구성해야(`pm path`).
  - **"AAB면 개발자가 배포 서명 키를 쥔다"** — **Play 배포 경로**에선 Play App Signing으로 **Google이** 앱 서명 키를 쥐고, 개발자는 별도 업로드 키로 업로드만.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 소스 → 빌드 → APK **또는** AAB.
- **AAB 경로**: `.aab` → (Play 또는 `bundletool`) → 기기별 split → 서명. (로컬 `bundletool`은 **아무 키스토어로** 오프라인 서명 가능 — Play App Signing은 **Play 배포에서만** 필수.)
- **출력**: 설치된 `base.apk` + config/feature split들(런타임에 한 앱으로 병합).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **불완전 분석**: base만 보면 다른 split의 코드/리소스를 놓칩니다. 온디맨드 동적 기능은 **나중에 도착**해 설치 시점엔 없음.
- **AXML 무시**: 매니페스트를 텍스트로 grep하면 exported 컴포넌트·권한 선언을 놓칩니다.
- **신뢰 모델 이동(C49)**: Play App Signing으로 배포 서명 키가 Google로 이동 — 개발자 키 유출 영향은 줄지만, 공급망 신뢰가 Play로 집중.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **config split(다중 APK 설치 기반)**: A5.0/API21(Lollipop). 이전 기기는 유니버설 단일 APK.
- **App Bundle**: 2018 도입, **2021.8부터 신규 Play 앱 필수** → Play App Signing 사실상 필수.
- **동적 기능(Play Feature Delivery)**: 이후 추가(SplitInstallManager 온디맨드).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `unzip -l app.apk`(구조), `aapt2 dump`/`apktool`(AXML 매니페스트·리소스), `adb shell pm path <pkg>`(**모든 split 경로**), `dumpsys package <pkg>`(`splits=`·`codePath`), `pm install-multiple`, `bundletool build-apks`.
- **소스**: Android 개발자 문서 "About Android App Bundles"·"Play Feature Delivery", Play Console "Use Play App Signing"(C08/C49).

**주의**: APK/AAB 구조는 아키텍처 무관 → **에뮬레이터/데스크톱에서 unzip·apktool·pm path 실측 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C07(DEX)**: `classes.dex`가 이 ZIP 안에.
- **C08(서명)**: 서명이 이 APK/블록에 작동, split은 같은 키.
- **C09(UID)**: 패키지·UID가 이 설치 단위에 부여.
- **C49(공급망)**: Play App Signing·번들 배포가 공급망 신뢰의 축.
- 다음은 이 앱들이 서로를 보고 데이터를 넘기는 **C11(package visibility·URI permission)**로.

## 직접 그릴 수 있는 호출 흐름

```
[ APK(설치) vs AAB(발행), 그리고 split ]

  개발자 ── AAB(.aab, 설치 불가) ──▶ Play / bundletool
                                        │ 기기 설정(밀도/ABI/언어)별
                                        ▼ split 생성 + 서명
  설치된 앱(한 패키지·한 UID·같은 키):
     base.apk
     + split_config.arm64_v8a.apk (ABI)
     + split_config.xxhdpi.apk    (밀도)
     + split_config.en.apk        (언어)
     + <동적 기능>.apk (온디맨드, 나중 도착)
        → 런타임에 하나로 병합  (분석: pm path로 전부 당겨야)

  APK 내부(ZIP): AndroidManifest.xml(AXML) · classes.dex · resources.arsc
                 · res/ · assets/(원형) · lib/<abi>/ · META-INF/(v1)
```

## 오개념 판별 문제 5개

1. "AAB(.aab)는 기기에 직접 설치할 수 있는 새로운 형태의 APK다."
2. "APK 안의 `AndroidManifest.xml`은 텍스트라 바로 grep해 읽을 수 있다."
3. "멀티덱스 64K 한도는 앱이 정의한 메서드(또는 클래스) 개수다."
4. "config split이나 동적 기능은 다른 키로 서명될 수 있어, base APK만 분석하면 된다."
5. "App Bundle로 배포해도 기기에 실리는 서명은 개발자 키다."

<details><summary>판정 기준(펼치기)</summary>

1. **발행 포맷**입니다. Play/bundletool이 유도한 split이 설치됩니다.
2. **AXML로 컴파일**돼 있습니다(aapt2/apktool 필요). `assets/`·래스터 리소스만 원형.
3. **단일 DEX의 메서드 참조** 상한입니다(참조된 프레임워크/라이브러리 포함).
4. 모든 split은 **같은 키·한 UID**이고 코드/리소스를 나눠 가집니다 — **전부 당겨** 재구성해야.
5. **Play App Signing**이면 배포 서명 키는 **Google**이 쥡니다(개발자는 업로드 키만).
</details>

## 서술형 문제 3개

1. APK(설치 단위)와 AAB(발행 포맷)의 차이, 그리고 Play/bundletool이 어떻게 기기별 split을 생성·서명하는지 서술하세요.
2. 한 앱이 여러 split으로 설치될 때 "한 패키지·한 UID·같은 키"라는 불변식이 왜 보안적으로 중요한지, 그리고 정적 분석이 왜 모든 split을 당겨야 하는지 서술하세요.
3. Play App Signing이 배포 서명 키를 개발자에서 Google로 옮기는 것이 신뢰 모델(C49)에 어떤 변화인지 서술하세요.

## 소스·정적 검증 경로

- 임의 앱에 `adb shell pm path <pkg>`로 base와 모든 split 경로를 나열하고, `dumpsys package <pkg>`의 `splits=`와 대조하세요.
- 한 APK를 `apktool`로 풀어 `AndroidManifest.xml`이 AXML임을(텍스트 grep 실패) 확인하고, exported 컴포넌트를 나열하세요.
- `unzip -l`로 `classes.dex`·`resources.arsc`·`lib/<abi>/`·`META-INF/`를 식별하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **구조 실측**: `unzip -l`·`apktool`로 APK 멤버와 AXML을.
2. **split 실측**: `pm path`로 한 앱의 모든 split을.
3. **분석 서술**: base만 vs 전체 split을 대조해 왜 전부 필요한지.
4. **연결**: 서명자 해시(C08)가 모든 split에서 같은지 확인.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

APK는 설치·실행되는 ZIP 단위(AXML 매니페스트·`classes.dex`·`resources.arsc`·`lib/<abi>/`·`META-INF`)이고, AAB는 Play에 올리는 발행 포맷(설치 불가)입니다. 요즘 앱은 base + config split + 동적 기능으로 **여러 APK로 설치**되며, 전부 **같은 키·한 UID**라 base만 분석하면 코드를 놓칩니다. 그리고 Play App Signing이면 기기에 실리는 서명 키는 개발자가 아니라 **Google**이 쥡니다(신뢰 모델 이동, C49). 다음은 이 앱들이 서로를 **보고**(가시성) 데이터를 **넘기는**(URI 권한) **C11**로 이어집니다.
