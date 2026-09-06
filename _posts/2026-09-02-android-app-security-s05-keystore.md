---
layout: post
title: "[Android 앱 보안 S05] Android Keystore 실측"
date: 2026-09-02 13:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Keystore, AES-GCM, 암호화, 하드웨어보안, 비추출키, 학습기록]
excerpt: "S04에서 본 평문 저장의 대안이 Android Keystore입니다. 그런데 이번 대상 InsecureShop은 Keystore를 쓰지 않아서, Keystore의 성질을 직접 확인하려고 최소 데모 앱을 손으로 빌드했습니다. 비추출 AES 키를 만들어 getEncoded()가 null인지, 키 원문 없이 AES-GCM 암복호화가 도는지, 그리고 이 키가 하드웨어에 있는지 소프트웨어에 있는지까지 화면에 찍어 봤습니다. 에뮬레이터에서는 SOFTWARE였습니다."
---

> S04에서 InsecureShop은 비밀번호를 평문 SharedPreferences에 뒀습니다. 그 자리에 있어야 할 게 Keystore입니다. 다만 InsecureShop은 Keystore를 쓰지 않아, 이번엔 Keystore 자체를 확인하려고 작은 데모 앱을 직접 만들었습니다.

Keystore의 약속은 하나입니다. 키를 앱에 주지 않고, 키로 하는 일만 해 준다. 앱은 키 원문을 절대 못 보고, 암복호화 요청만 보내면 시스템이 대신 처리합니다. 이게 정말 그런지 눈으로 보고 싶었습니다. 이번 대상인 InsecureShop은 Keystore를 아예 안 쓰기 때문에, Keystore의 성질만 확인하는 최소 앱(KeystoreDemo)을 손으로 빌드해서 `aas-api33`에 올렸습니다.

---

## 실습 목표

- AndroidKeyStore에 비추출(non-extractable) AES 키를 생성한다.
- `SecretKey.getEncoded()`가 키 원문을 주는지(null인지) 확인한다.
- 키 원문 없이 AES-GCM 암복호화가 성립하는지 왕복으로 확인한다.
- 이 키가 하드웨어(TEE/StrongBox)에 있는지 소프트웨어에 있는지 확인한다.

---

## 윤리적 범위와 허가 조건

이번 편의 대상은 내가 직접 작성한 최소 데모 앱(`com.aas.keystoredemo`)입니다. 취약 앱을 공격하는 게 아니라, 안드로이드 Keystore라는 플랫폼 기능을 검증하는 편입니다. 모든 실행은 `aas-api33` 에뮬레이터 안에서만 했습니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01)
- 빌드: `aapt2` + `javac 26`(`--release 11`) + `d8` + `zipalign` + `apksigner` (build-tools 36.0.0). Gradle 없이 최소 구성으로 손빌드.
- 데모 앱: `com.aas.keystoredemo`, 액티비티 하나(결과를 화면에 출력)

---

## 위협 모델 — Keystore에 무엇을 기대하나

- 앱이 키 원문을 볼 수 있는가? → 볼 수 없어야 한다(비추출).
- 앱 저장소를 통째로 털어도 키가 나오는가? → 키는 저장소가 아니라 Keystore가 쥐고 있어야 한다.
- 키가 하드웨어에 격리돼 있는가? → 기기/환경에 따라 다르다. 이걸 실제로 확인한다.

---

## 재현 절차

### 1. 키 생성 코드

데모 앱의 핵심은 이 몇 줄입니다. AndroidKeyStore 공급자에 AES-256 키를 만들고, 용도를 암복호화로, 블록 모드를 GCM으로 지정합니다.

```java
KeyGenerator kg = KeyGenerator.getInstance(
    KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
kg.init(new KeyGenParameterSpec.Builder("demoKey",
        KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
        .setKeySize(256)
        .build());
SecretKey key = kg.generateKey();
```

키 원문을 담을 변수가 어디에도 없습니다. `generateKey()`가 돌려주는 `SecretKey`는 실제 키가 아니라 Keystore 안의 키를 가리키는 핸들입니다.

### 2. 손빌드

Gradle 없이 최소 도구만으로 APK를 만들었습니다.

```console
$ aapt2 link -o base.apk -I android.jar --manifest AndroidManifest.xml \
        --min-sdk-version 24 --target-sdk-version 33
$ javac --release 11 -classpath android.jar -d classes MainActivity.java
$ d8 --min-api 24 --lib android.jar --output . classes/com/aas/keystoredemo/MainActivity.class
# classes.dex 를 base.apk 루트에 넣고
$ zipalign -f 4 base.apk aligned.apk
$ apksigner sign --ks ~/.android/debug.keystore --ks-pass pass:android --out keystoredemo.apk aligned.apk
$ adb install -r keystoredemo.apk
Success
```

### 3. 실행 결과

앱을 실행하면 네 항목이 화면에 찍힙니다. 실제 출력은 이랬습니다.

```console
[1] AES-256 key generated in AndroidKeyStore (alias=demoKey)
[2] key.getEncoded() = null  -> RAW KEY NOT EXTRACTABLE
[3] plaintext  = MY_SECRET_42
    iv         = 84ef2b53e82c79470eac6a19
    ciphertext = 83e4cb048ed34f54eb7e30def5052bfc…
    decrypted  = MY_SECRET_42   (round-trip OK)
[4] isInsideSecureHardware() = false
    getSecurityLevel()     = SOFTWARE
```

`getEncoded()`가 `null`입니다. 키 원문을 달라는 요청에 시스템이 아무것도 주지 않습니다. 그런데도 같은 키로 AES-GCM 암호화와 복호화가 정확히 왕복합니다(`MY_SECRET_42` → 암호문 → `MY_SECRET_42`). 키 없이 키로 하는 일만 되는, Keystore의 약속이 그대로 성립했습니다.

마지막 줄이 이 편에서 가장 중요합니다. `getSecurityLevel()`이 `SOFTWARE`입니다.

---

## 스크린샷

데모 앱의 실제 실행 화면입니다. 위 네 항목이 그대로 찍혀 있습니다.

![KeystoreDemo 앱 실행 화면 — AndroidKeyStore에 AES-256 키 생성, getEncoded()=null(비추출), AES-GCM 왕복 OK, getSecurityLevel()=SOFTWARE 가 모노스페이스로 출력됨](/assets/img/android-app-security/S05/01-keystore.png)

데모 앱 소스와 출력 원문은 `assets/evidence/android-app-security/S05/`에 남겼습니다.

---

## 관측 결과

- AndroidKeyStore로 만든 AES 키는 `getEncoded()`가 `null`이다. 앱은 키 원문을 볼 수 없다.
- 그 키로 AES-GCM 암복호화가 왕복으로 성립한다. 키를 노출하지 않고 암호 연산만 위임된다.
- 이 에뮬레이터에서 키의 보안 수준은 `SOFTWARE`다(`isInsideSecureHardware()=false`). 하드웨어 격리가 아니다.

---

## 근본 원인과 보안 영향

- Keystore는 S04에서 본 문제(비밀번호 평문 저장)의 올바른 대안입니다. 저장소를 털어도 키 원문이 없으므로, 민감 값은 SharedPreferences가 아니라 Keystore가 보호하는 키로 다뤄야 합니다.
- 다만 "Keystore를 썼다"가 곧 "하드웨어에 안전하다"는 아닙니다. 이 에뮬레이터처럼 하드웨어 TEE가 없으면 키는 소프트웨어로 보호됩니다. 즉 에뮬레이터에서의 크립토 테스트는 하드웨어 격리를 증명하지 못합니다. 하드웨어 수준이 필요하면 실제 기기에서 `getSecurityLevel()`이 `TRUSTED_ENVIRONMENT`나 `STRONGBOX`인지 확인해야 합니다.
- 참고로 Keystore 키는 앱 UID에 묶여 있어, 앱을 삭제하면 그 앱의 키 항목도 함께 사라집니다. 재설치한 앱은 이전 키로 만든 암호문을 더는 풀 수 없습니다.

## 수정 방법 / 권고

- 민감 값은 Keystore 키로 보호하고, 편의가 필요하면 그 위에 `EncryptedSharedPreferences`(Jetpack Security)를 쓴다.
- 하드웨어 격리가 중요한 값은 `setIsStrongBoxBacked(true)`를 시도하고(미지원 시 폴백), 런타임에 `getSecurityLevel()`로 실제 수준을 확인한다.
- 인증이 필요한 키는 `setUserAuthenticationRequired(true)`로 생체/PIN 뒤에 둔다.

---

## 재검증

같은 키 핸들로 암호화한 값이 복호화로 정확히 원문으로 돌아왔고(`round-trip OK`), 그 사이 `getEncoded()`는 계속 `null`이었습니다. "키를 못 보는데 키로 하는 일은 된다"가 두 관측으로 함께 확인됩니다. 보안 수준이 `SOFTWARE`라는 것도 화면 값 그대로입니다.

---

## 참고 자료

- Android Developers — Android Keystore system, `KeyGenParameterSpec`, `KeyInfo`
- Android Developers — `getSecurityLevel()`(API 31+)와 하드웨어 보안 모듈
- Android Jetpack Security — `EncryptedSharedPreferences`
