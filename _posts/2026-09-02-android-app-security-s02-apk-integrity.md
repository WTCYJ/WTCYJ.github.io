---
layout: post
title: "[Android 앱 보안 S02] APK 수집과 무결성 검증"
date: 2026-09-02 10:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, APK, apksigner, aapt, SHA256, 코드서명, InsecureShop, 학습기록]
excerpt: "실습을 시작하기 전에, 손에 쥔 APK가 정말 내가 생각한 그 앱인지부터 못 박습니다. InsecureShop APK 하나를 놓고 SHA-256으로 지문을 뜨고, apksigner로 서명 체계와 서명 인증서를 확인하고, aapt로 package name·타깃 SDK·권한을 뽑고, 압축을 열어 split 여부까지 봤습니다. 서명 인증서가 디버그 키였다는, 작지만 분명한 사실 하나가 이 앱의 성격을 그대로 말해 줍니다."
---

> S01에서 다진 `aas-api33` 환경 위에서 이제 대상 앱을 올립니다. 이번 편은 그 첫 단계 — 앱을 분석하기 전에 "이 APK가 무엇인지"를 지문·서명·매니페스트로 확정하는 일입니다.

분석에 들어가기 전에 늘 먼저 하는 게 있습니다. 지금 손에 있는 APK가 정말 내가 받으려던 그 앱인지, 누가 서명했는지, 무엇을 요구하는지 확인하는 일입니다. 이걸 건너뛰면 나중에 "이 결과가 어느 빌드에서 나온 거지?"라는 질문에 답할 수 없습니다. 그래서 이번 시리즈의 대상으로 쓸 InsecureShop APK 하나를 놓고, 지문부터 서명·매니페스트·구조까지 한 번에 못 박아 둡니다.

---

## 실습 목표

- 대상 APK의 SHA-256(과 보조 해시)을 기록해 이후 모든 실습이 같은 파일을 가리키게 한다.
- `apksigner`로 서명 체계(v1~v4)와 서명 인증서를 확인한다.
- `aapt`로 package name, 타깃 SDK, 권한, 디버그 여부를 뽑는다.
- 압축을 열어 단일 APK인지 split APK인지, 네이티브 라이브러리가 있는지 본다.
- 검증한 APK를 에뮬레이터에 설치해 "정말 그 앱"이 맞는지 눈으로 확인한다.

---

## 윤리적 범위와 허가 조건

대상은 공개된 교육용 취약 앱 InsecureShop입니다. 실제 서비스가 아니라 학습을 위해 일부러 취약하게 만든 앱이고, 모든 조작은 S01에서 만든 `aas-api33` 에뮬레이터 안에서만 합니다. 실기기·실서비스·타인 계정은 관여하지 않습니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01에서 구축, API 33 / Android 13 / userdebug)
- `aapt2`, `apksigner`: Android build-tools 36.0.0
- 해시: coreutils `sha256sum` / `sha1sum` / `md5sum`
- 구조 확인: `unzip -l`

---

## 대상 앱과 SHA-256

- 앱: InsecureShop (의도적 취약 Android 앱, 출처 `github.com/hax0rgb/InsecureShop`)
- 파일: `InsecureShop.apk`, 4,754,534 바이트
- 라이선스: 공개 배포된 교육용 취약 앱. 이 시리즈에서는 에뮬레이터 안 학습 용도로만 사용합니다.

```console
$ sha256sum InsecureShop.apk
a83298ae4a37fcab8101e8b41e513dd2199af71a94ea537d556a318e07d4d1bd  InsecureShop.apk
$ sha1sum InsecureShop.apk
eb665e44de4b6cf94786bb056996ab40fe32ed7e  InsecureShop.apk
$ md5sum InsecureShop.apk
c5d872355e43322f1692288e2c4e6f00  InsecureShop.apk
```

이 SHA-256이 앞으로 이 시리즈가 말하는 "InsecureShop"의 신원입니다. S03 이후 어떤 결과든 이 지문의 파일에서 나온 것입니다.

---

## 위협 모델 — 이 단계에서 답할 질문

S02의 관심사는 취약점 공격이 아니라 신원과 출처입니다. 세 가지를 확인합니다.

- 이 파일은 받은 뒤로 손대지 않은 원본인가? → 해시로 고정한다.
- 누가 서명했고, 어떤 서명 체계인가? → 서명 인증서와 v1~v4 확인.
- 이 앱은 무엇을 요구하고 어떤 성격의 빌드인가? → package name·권한·debuggable·targetSdk 확인.

---

## 재현 절차

### 1. 서명 검증

`apksigner`로 서명 체계와 서명자 수를 봅니다.

```console
$ apksigner verify -v InsecureShop.apk
Verified using v1 scheme (JAR signing): true
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): false
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Number of signers: 1
```

v1(JAR)과 v2로 서명돼 있고 v3 이상은 없습니다. 서명 자체는 유효합니다(변조되지 않음). 이어서 서명 인증서를 봅니다.

```console
$ apksigner verify --print-certs InsecureShop.apk
Signer #1 certificate DN: C=US, O=Android, CN=Android Debug
Signer #1 certificate SHA-256 digest: d16dff509803ba1123ec7c573cc18c58bde996ca05bae3efe852fb3c668cfca8
Signer #1 certificate SHA-1 digest: c56a7946caf6923ced4cf7f4c6b0e5b0e97df26b
```

서명 인증서의 이름이 `CN=Android Debug`입니다. 이 앱은 릴리스 키가 아니라 안드로이드 SDK가 자동으로 만드는 디버그 키로 서명됐다는 뜻입니다. 교육용 앱에서는 흔한 일이지만, 그냥 넘어갈 사실은 아닙니다 — 디버그 서명은 출처를 보증하지 못하고, 뒤에서 확인할 `debuggable` 플래그와 짝을 이룹니다.

### 2. 매니페스트 정보

`aapt2`로 package name, SDK, 권한, 디버그 여부를 뽑습니다.

```console
$ aapt2 dump badging InsecureShop.apk
package: name='com.insecureshop' versionCode='1' versionName='1.0' compileSdkVersion='29' ...
minSdkVersion:'16'
targetSdkVersion:'29'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.READ_EXTERNAL_STORAGE'
uses-permission: name='android.permission.WRITE_EXTERNAL_STORAGE'
uses-permission: name='android.permission.READ_CONTACTS'
uses-permission: name='android.permission.WAKE_LOCK'
application-label:'InsecureShop'
application-debuggable
```

package는 `com.insecureshop`, targetSdk 29(Android 10)입니다. 요즘 기준으론 낮은 타깃이라, scoped storage 같은 최신 정책이 강제되지 않는 옛 동작을 그대로 씁니다. 권한은 인터넷·외부저장 읽기/쓰기에 더해 연락처 읽기(`READ_CONTACTS`)까지 요구합니다. 그리고 `application-debuggable` — 디버그 가능 빌드라 나중에 `run-as`로 앱 저장소를 직접 열 수 있습니다.

### 3. APK 구조

압축을 열어 단일 APK인지, split이 있는지, 네이티브 라이브러리가 있는지 봅니다.

```console
$ unzip -l InsecureShop.apk
   8568  AndroidManifest.xml
7251624  classes.dex
 483140  resources.arsc
 112095  META-INF/CERT.SF
    765  META-INF/CERT.RSA
 ...
```

`classes.dex` 하나에 `resources.arsc`, 매니페스트, 그리고 v1 서명 흔적(`META-INF/CERT.*`)이 들어 있는 단일 APK입니다. `split_*.apk`도, `lib/` 아래 네이티브 라이브러리도 없습니다. 즉 ABI를 가리지 않고 어느 에뮬레이터에서나 설치됩니다. DEX가 하나뿐이라 정적 분석(S03)에서 다룰 코드 범위도 명확합니다.

### 4. 설치해서 신원 확인

검증한 그 파일을 에뮬레이터에 설치하고, 설치된 package와 버전이 일치하는지 확인합니다.

```console
$ adb install -r -g InsecureShop.apk
Performing Streamed Install
Success
$ adb shell pm path com.insecureshop
package:/data/app/~~.../com.insecureshop-.../base.apk
$ adb shell dumpsys package com.insecureshop | grep versionName
    versionName=1.0
```

설치된 package `com.insecureshop`, versionName `1.0` — 앞서 `aapt2`로 읽은 값과 같습니다. 실행하면 InsecureShop의 로그인 화면이 뜹니다.

---

## 스크린샷

검증한 APK를 설치해 실행한 화면입니다. 노란 배경에 장바구니 로고, "Log in." 화면이 InsecureShop이 맞다는 걸 눈으로 확인시켜 줍니다. 파일 지문·package·버전·화면이 모두 한 앱을 가리킵니다.

![aas-api33에 설치·실행한 InsecureShop — 노란 배경, 장바구니 로고, "Log in." 제목과 Email/Password 입력 필드, Log in 버튼](/assets/img/android-app-security/S02/01-installed.png)

해시·badging·apksigner·구조의 원시 출력은 `assets/evidence/android-app-security/S02/`에 남겼습니다.

---

## 관측 결과

- 대상은 `com.insecureshop` v1.0, SHA-256 `a83298…d1bd`로 고정됐다.
- 서명은 v1+v2로 유효하지만, 서명 인증서가 디버그 키(`CN=Android Debug`)다. 출처 보증이 없는 교육용 빌드라는 뜻.
- targetSdk 29 + `debuggable` — 옛 정책 동작에 더해, `run-as`로 앱 데이터에 접근할 길이 열려 있다(S04에서 활용).
- 권한에 `READ_CONTACTS`가 있다. 쇼핑 앱 치고는 눈에 띄는 요구라, 어디서 쓰는지 뒤 편에서 확인할 지점.
- 단일 APK, 네이티브 라이브러리 없음, DEX 1개.

---

## 근본 원인과 보안 영향(참고)

S02는 앱을 공격하는 편이 아니라, 검증에서 드러난 성격을 기록하는 편입니다. 정리하면 이렇습니다.

- 디버그 서명 + `debuggable=true`는 프로덕션 앱이라면 그 자체로 결함입니다. 디버그 서명은 서명자 신원을 보증하지 못하고, `debuggable`은 `run-as`·디버거 부착으로 앱 내부를 그대로 열어 줍니다. 릴리스 앱은 릴리스 키로 서명하고 `debuggable`을 꺼야 합니다.
- v3 서명이 없으면 키 교체(rotation)를 지원하지 못합니다. 프로덕션이라면 v2/v3(가능하면 v4)까지 갖추는 게 맞습니다.
- targetSdk 29는 최신 런타임 보호(강화된 scoped storage, 백그라운드 접근 제한 등)를 회피하는 셈이 됩니다. 실제 앱이라면 타깃을 현행으로 올려야 합니다.

교육용 앱이라 이 성격들이 오히려 실습을 쉽게 해 주지만, 실제 앱에서 같은 신호를 봤다면 그건 곧 지적할 항목입니다.

---

## 재검증

설치 뒤 원본 APK의 해시가 그대로인지 다시 떠 보면(`sha256sum InsecureShop.apk`) 앞의 값과 일치합니다. 이후 어느 실습에서든 이 지문으로 "같은 파일"임을 언제나 되짚을 수 있습니다.

---

## 참고 자료

- Android Developers — `apksigner` 및 APK Signature Scheme v1~v4
- Android Developers — `aapt2 dump badging`
- InsecureShop 프로젝트 (`github.com/hax0rgb/InsecureShop`)

