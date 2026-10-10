---
layout: post
title: "apksigner·aapt2·bundletool로 APK triage 30초에 끝내기"
date: 2026-10-18 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, apksigner, aapt2, bundletool, APKTriage]
excerpt: "APK를 처음 받으면 세 가지를 빠르게 본다 — 서명 자세(apksigner: 어느 스킴 v1~v4·서명자 SHA-256), 매니페스트 공격면(aapt2 dump xmltree: exported·권한), AAB라면 bundletool로 split 유도. AndroidManifest.xml은 컴파일된 AXML이라 grep이 안 되고, AAB는 설치 자체가 안 된다는 게 핵심 함정이다."
---

앱 분석의 0단계는 triage다. APK 하나를 받았을 때 30초 안에 세 가지를 파악한다: 서명이 어떤 자세인지(무결성·정체성), 매니페스트가 어떤 공격면을 노출하는지, 구조가 split/네이티브 lib을 포함하는지. 이 세 축이 이후 정적·동적 분석의 지도를 그린다. 이 글은 그 triage를 정확한 도구·서브커맨드로 하는 방법과, 처음 부딪히는 두 함정(AXML은 grep 불가, AAB는 설치 불가)을 정리한 기록이다.

> **한 줄 결론**: `apksigner verify --print-certs`로 서명 스킴·서명자 해시를, `aapt2 dump xmltree`로 exported 공격면을, AAB라면 `bundletool`로 split을 유도한다. 매니페스트는 컴파일된 AXML이라 반드시 디코드해야 읽힌다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 세 도구(`apksigner`·`aapt2`·`bundletool`)로 APK/AAB의 서명·공격면·구조를 파악한다. 선수 개념은 [APK·AAB·Split(C06)](/posts/android-concept-atlas-c06-apk-aab-split/)의 ZIP·AXML·발행 포맷 구분, [서명 v1~v4(C08)](/posts/android-concept-atlas-c08-apk-signing/)의 서명자 정체성, 그리고 [2장](/posts/android-lab-p1c02-adb-evidence-collection/)에서 `pm path`로 APK 경로를 확보하는 법이다.

전체 구조에서 triage는 모든 앱 분석의 **입구**다. 서명 자세는 무결성/정체성을, 매니페스트는 exported 공격면([5부](/posts/android-security-mastery-series-index/))을, 구조는 split/네이티브 lib 유무를 알려준다.

## 핵심 개념 — 세 도구, 세 축

- **apksigner**(build-tools): `apksigner verify --verbose --print-certs <apk>` → 검증된 스킴(v1/v2/v3/v4)과 서명자 인증서 SHA-256. v2+는 `jarsigner`를 대체한다. `Source-confirmed`
- **aapt2**(build-tools): `aapt2 dump badging <apk>`(패키지명·versionCode/Name·`sdkVersion`=minSdk·`targetSdkVersion`·권한·launchable-activity), `aapt2 dump permissions <apk>`, `aapt2 dump xmltree <apk> --file AndroidManifest.xml`(디코드된 AXML = exported 컴포넌트·intent-filter). `--file`은 필수. `Source-confirmed`
- **bundletool**(별도 jar, github.com/google/bundletool): AAB 대상. `bundletool build-apks --bundle=app.aab --output=app.apks`, `bundletool install-apks --apks=app.apks`, `bundletool dump manifest --bundle=app.aab`. `--mode=universal`도 **`.apks`(ZIP) 안에 `universal.apk`**를 낼 뿐 바로 설치되는 `.apk`가 아니다. `Source-confirmed`

**신뢰 경계와 위협 모델.** 서명자 인증서 = 앱 정체성(C08). triage에서 서명자 SHA-256을 기록해 두면, 이후 "같은 개발자인가"(sharedUserId/서명 권한)·리패키징 여부([7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/))를 판단하는 기준이 된다. exported 컴포넌트(aapt2 xmltree)는 타 앱이 닿는 공격면(C21)이다.

> **[그림 1]** `apksigner verify --verbose --print-certs`로 검증된 스킴(v1~v4)과 서명자 SHA-256이 출력된 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱을 v1-only / v2+ 두 버전으로 서명해 triage 차이를 관측한다. AAB는 자작 프로젝트의 `bundleRelease` 산출물로 만든다. 데스크톱에서 전부 실측 가능(에뮬 불필요).

## 실습 절차와 관측

### 가설
자작 앱을 v2+로 서명하면 `apksigner verify`가 `Verified using v2 scheme: true`를 보고하고, `xmltree`에서 exported 컴포넌트가 드러난다. `Inferred`

### 절차
1. `pm path`로 대상 APK 경로를 얻어 `adb pull`.
2. `apksigner verify --print-certs`로 스킴·서명자 SHA-256을 기록.
3. `aapt2 dump badging`으로 패키지·SDK·권한을 확인.
4. `aapt2 dump xmltree ... --file AndroidManifest.xml`로 exported 컴포넌트를 나열.
5. AAB면 `bundletool build-apks` → `install-apks`.

```bash
apksigner verify --verbose --print-certs app.apk
aapt2 dump badging app.apk
aapt2 dump xmltree app.apk --file AndroidManifest.xml | grep -i -E 'exported|permission'
# AAB
bundletool build-apks --bundle=app.aab --output=app.apks
bundletool install-apks --apks=app.apks
```

> **[그림 2]** `aapt2 dump xmltree`로 디코드된 매니페스트에서 `android:exported`·`intent-filter`가 보이는 부분 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ apksigner verify --verbose --print-certs app.apk
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Signer #1 certificate SHA-256 digest: 1a2b...
```

## Root Cause — 왜 이렇게 되는가

`grep AndroidManifest`가 안 되는 것은 aapt2가 매니페스트/리소스를 컴파일하기 때문이다(AXML/resources.arsc, C06). 그래서 `aapt2 dump xmltree`나 apktool로 디코드해야 읽힌다. AAB가 설치되지 않는 것은 그것이 **발행 포맷**이라 Play/bundletool이 기기별 split을 유도하도록 설계됐기 때문이다. 그리고 v2/v3 서명을 META-INF에서 찾으면 없다 — v2/v3는 APK Signing Block(파일), v4는 별도 `.idsig`이고, META-INF엔 v1만 있다.

## 방어와 회귀 검증

- (개발자) 불필요한 `exported=true`·과도한 권한을 triage 단계에서 스스로 점검한다. CI에서 "exported 컴포넌트에 permission 가드가 있다"를 `xmltree` 파싱으로 회귀 검사할 수 있다.
- (연구자) 서명자 SHA-256을 기록해 리패키징(7장) 대조 기준으로 삼는다.

**흔한 실패와 처리.** `aapt2: unknown command` → aapt2는 build-tools에 있으니 PATH 확인. `bundletool install-apks` 실패 → 기기 미연결/서명 키 불일치. xmltree 출력이 비어 보임 → `--file AndroidManifest.xml` 누락.

## 버전 차이와 한계

- 서명 스킴 API 게이트: v2=API 24, v3=API 28, v4=API 30(+`.idsig`). 최신 기기는 v2+를 요구한다(C08 강등 방지).
- 최신 build-tools엔 `aapt2`·`apksigner`·`zipalign`·`d8`·`dexdump`와 legacy `aapt`도 아직 동봉(폐기 예정).
- bundletool은 SDK와 별도 릴리스(github)라 버전 표기가 필요하다. 실제 Play App Signing 재서명은 Play 배포 경로에서만 관측된다.

## 정리

- 서명 자세 = `apksigner verify --print-certs`, 공격면 = `aapt2 dump xmltree`, AAB = `bundletool`.
- 매니페스트는 컴파일된 AXML이라 디코드해야 읽힌다.
- AAB는 설치 불가 — split을 유도해야 한다.

**점검 질문** — (1) v2 서명은 왜 META-INF에서 안 보이나? (2) `aapt2 dump xmltree`에 `--file`이 필요한 이유는? (3) `build-apks --mode=universal` 산출물을 바로 `adb install`할 수 없는 이유는?

**참고** — [apksigner](https://developer.android.com/tools/apksigner) · [aapt2](https://developer.android.com/tools/aapt2) · [bundletool](https://github.com/google/bundletool) · [C06 APK·AAB·Split](/posts/android-concept-atlas-c06-apk-aab-split/) · [C08 서명](/posts/android-concept-atlas-c08-apk-signing/)

*다음 글: [jadx로 Java/Kotlin 정적 분석](/posts/android-lab-p1c04-jadx-static-analysis/).*
