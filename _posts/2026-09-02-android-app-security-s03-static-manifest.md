---
layout: post
title: "[Android 앱 보안 S03] APK 정적 분석과 공격 표면"
date: 2026-09-02 11:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, apktool, jadx, AndroidManifest, exported, deeplink, 정적분석, InsecureShop, 학습기록]
excerpt: "APK를 코드로 열기 전에 매니페스트부터 읽습니다. InsecureShop을 apktool과 jadx로 디코드해 exported 컴포넌트·intent-filter·딥링크·backup/debuggable/cleartext 설정을 뽑고, 두 도구의 결과를 맞대 봤습니다. 명시적으로 열어 둔 것보다, intent-filter 때문에 조용히 열려 버린 컴포넌트가 더 많았고, 로그인 없이 그중 하나를 그대로 띄워 확인했습니다."
---

> S02에서 신원을 확정한 `com.insecureshop`(SHA-256 `a83298…d1bd`)을 이제 정적으로 뜯습니다. 첫 표적은 매니페스트 — 앱이 바깥에 무엇을 열어 뒀는지가 여기 다 적혀 있습니다.

코드를 읽기 전에 매니페스트부터 보는 이유는 단순합니다. 공격 표면의 지도가 거기 있기 때문입니다. 어떤 컴포넌트가 바깥에서 호출 가능한지, 어떤 딥링크로 들어올 수 있는지, backup·debuggable·cleartext 같은 위험한 스위치가 켜져 있는지 — 이걸 먼저 그려 놓아야 뒤 챕터에서 어디를 팔지 정할 수 있습니다. InsecureShop을 apktool과 jadx로 각각 디코드해서, 두 도구가 같은 그림을 주는지 맞대 보며 표면을 그렸습니다.

---

## 실습 목표

- `apktool`로 바이너리 매니페스트를 사람이 읽을 XML로 디코드한다.
- exported 컴포넌트, intent-filter, 딥링크, 권한, `debuggable`/`allowBackup`/`usesCleartextTraffic`를 뽑는다.
- `jadx`로도 디코드해 매니페스트 사실이 일치하는지, 두 도구의 쓰임새가 어떻게 다른지 확인한다.
- 찾아낸 exported 컴포넌트 하나를 로그인 없이 실제로 띄워, 표면이 진짜 열려 있는지 확인한다.

---

## 윤리적 범위와 허가 조건

대상은 교육용 취약 앱 InsecureShop이고, 모든 조작은 `aas-api33` 에뮬레이터 안에서만 합니다. 이 편은 정적 분석과 소유 앱의 컴포넌트를 내 기기에서 직접 호출해 보는 데까지입니다.

---

## 환경 및 도구 버전

- `apktool` 3.0.2 — 바이너리 XML/리소스 디코드 + smali (재패키징 대비)
- `jadx` 1.5.5 — DEX → Java 디컴파일 + 리소스
- 대상 기기: `aas-api33` (S01)

---

## 위협 모델 — 무엇을 찾나

매니페스트에서 답할 것은 "바깥에서 이 앱의 무엇을 건드릴 수 있는가"입니다. 셋으로 나눠 봅니다.

- 외부에서 호출 가능한 컴포넌트(exported) — 명시적으로 연 것과, intent-filter 때문에 암묵적으로 열린 것.
- 외부 진입 경로 — 딥링크(scheme/host)와 커스텀 액션.
- 앱 전역 스위치 — `debuggable`, `allowBackup`, `usesCleartextTraffic`, 그리고 커스텀 권한의 보호 수준.

---

## 재현 절차

### 1. apktool로 디코드

```console
$ apktool d -f -o apktool_out InsecureShop.apk
I: Using Apktool 3.0.2 on InsecureShop.apk
I: Baksmaling classes.dex...
I: Decoding value resources...
I: Copying original files...
```

디코드된 `apktool_out/AndroidManifest.xml`을 읽으면 앱 태그의 스위치들이 한눈에 들어옵니다.

```xml
<application android:allowBackup="true"
             android:debuggable="true"
             android:usesCleartextTraffic="true"
             android:name="com.insecureshop.InsecureShopApp" ... >
```

세 스위치가 전부 켜져 있습니다. 백업 허용, 디버그 가능, 평문 통신 허용 — 하나씩 뒤 챕터의 실마리가 됩니다.

### 2. 권한과 커스텀 권한

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"/>
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"/>
<uses-permission android:name="android.permission.READ_CONTACTS"/>
<permission android:name="com.insecureshop.permission.READ"/>   <!-- protectionLevel 없음 -->
```

`com.insecureshop.permission.READ`라는 커스텀 권한을 선언했는데 `android:protectionLevel`이 없습니다. 지정하지 않으면 기본값이 `normal`이고, normal 권한은 설치 시 요청만 하면 사용자 확인 없이 자동으로 부여됩니다. 뒤에서 이 권한이 ContentProvider를 "보호"하는 데 쓰이는데, 보호가 사실상 없다는 뜻이 됩니다.

### 3. exported 컴포넌트 — 명시적인 것과 조용히 열린 것

명시적으로 `android:exported="true"`인 컴포넌트는 넷입니다.

```xml
<activity android:exported="true" android:name="com.insecureshop.AboutUsActivity"/>
<activity android:exported="true" android:name="com.insecureshop.ResultActivity"/>
<provider android:exported="true" android:authorities="com.insecureshop.provider"
          android:name="...InsecureShopProvider"
          android:readPermission="com.insecureshop.permission.READ"/>
<service android:exported="true" android:name="net.gotev.uploadservice.UploadService"/>
```

그런데 더 중요한 건 명시적으로 적지 않았는데 열려 버린 컴포넌트들입니다. targetSdk가 29라(31 미만) intent-filter를 가진 컴포넌트는 `android:exported`를 안 써도 자동으로 exported됩니다. 그런 액티비티가 넷 더 있습니다.

```xml
<activity android:name="com.insecureshop.ChooserActivity"> ... VIEW/SEND intent-filter ... </activity>
<activity android:name="com.insecureshop.WebViewActivity">
    <intent-filter>
        <action android:name="android.intent.action.VIEW"/>
        <category android:name="android.intent.category.BROWSABLE"/>
        <data android:host="com.insecureshop" android:scheme="insecureshop"/>
    </intent-filter>
</activity>
<activity android:name="com.insecureshop.WebView2Activity"> ... action com.insecureshop.action.WEBVIEW, BROWSABLE ... </activity>
```

`WebViewActivity`는 `insecureshop://com.insecureshop` 딥링크로 열립니다. BROWSABLE 카테고리가 붙어 있으니, 웹페이지의 링크 한 줄로도 이 액티비티가 뜬다는 뜻입니다. 실제로 이 WebView가 임의 URL을 로드하는 문제는 S09에서 따로 다룹니다. 여기서는 "이 진입점이 열려 있다"까지가 정적 발견입니다.

명시적으로 닫아 둔 건 둘뿐이었습니다.

```xml
<activity android:exported="false" android:name="com.insecureshop.PrivateActivity"/>
<provider android:exported="false" android:name="androidx.core.content.FileProvider" .../>
```

이름이 `PrivateActivity`인데 이것만 닫혀 있는 게 오히려 얄궂습니다. 로그인 뒤에나 보여야 할 화면들(AboutUs, Result 등)이 전부 열려 있으니까요.

### 4. jadx와 결과 비교

같은 APK를 jadx로도 디코드했습니다.

```console
$ jadx -d jadx_out InsecureShop.apk
INFO  - progress: 2530 of 2530 (100%)
ERROR - finished with errors, count: 3
```

jadx는 DEX를 Java로 디컴파일하면서 리소스 안에 `AndroidManifest.xml`도 함께 복원합니다(디컴파일 중 메서드 3개 실패는 일부 코드가 안 풀린 것으로, 매니페스트와는 무관). 두 도구가 뽑은 매니페스트의 핵심 사실을 맞대 보면 완전히 같습니다.

```console
# apktool 매니페스트         # jadx 매니페스트
allowBackup="true"    x1     allowBackup="true"    x1
debuggable="true"     x1     debuggable="true"     x1
usesCleartextTraffic  x1     usesCleartextTraffic  x1
exported="false"      x2     exported="false"      x2
exported="true"       x4     exported="true"       x4
```

매니페스트 사실은 동일합니다. 차이는 그 외에 무엇을 주느냐입니다. apktool은 smali와 전체 리소스를 줘서 고쳐서 다시 패키징하기에 좋고, jadx는 Java 소스를 줘서 로직을 읽기에 좋습니다. 정적 분석에서는 보통 둘을 같이 씁니다 — 표면은 매니페스트로, 그 안의 동작은 jadx의 Java로.

### 5. 열려 있는지 직접 확인

정적으로 "exported"라고 읽었으니, 실제로 열려 있는지 확인합니다. 로그인하지 않은 상태에서 exported 액티비티 하나를 셸로 바로 띄웠습니다.

```console
$ adb shell am force-stop com.insecureshop     # 로그인 화면 상태로 초기화
$ adb shell am start -n com.insecureshop/.AboutUsActivity
Starting: Intent { cmp=com.insecureshop/.AboutUsActivity }
```

로그인 절차를 전혀 거치지 않았는데 화면이 그대로 떴습니다.

---

## 스크린샷

로그인 화면 상태에서 `am start`로 exported 액티비티를 직접 호출한 결과입니다. 인증을 건너뛰고 앱 내부 화면이 그대로 열렸습니다. 정적으로 읽은 "exported"가 실제 열린 문이라는 확인입니다.

![로그인하지 않은 상태에서 adb am start 로 직접 띄운 InsecureShop의 exported AboutUsActivity — 노란 "About InsecureShop" 화면이 인증 없이 표시됨](/assets/img/android-app-security/S03/01-exported-aboutus.png)

디코드한 `AndroidManifest.xml` 원본은 `assets/evidence/android-app-security/S03/`에 남겼습니다.

---

## 관측 결과

- 앱 전역 스위치 셋(`allowBackup`·`debuggable`·`usesCleartextTraffic`)이 전부 켜져 있다.
- exported 표면: 명시적 4개(AboutUs·Result 액티비티, InsecureShopProvider, UploadService)에 더해, intent-filter로 암묵 exported된 4개(Chooser·WebView·WebView2·Launcher). 닫힌 건 PrivateActivity와 FileProvider뿐.
- 딥링크 `insecureshop://com.insecureshop`(BROWSABLE) → WebViewActivity. 웹 링크로도 진입 가능한 경로.
- 커스텀 권한 `com.insecureshop.permission.READ`에 protectionLevel이 없어 normal로 떨어진다. 이 권한으로 "보호"되는 exported ContentProvider는 사실상 아무 앱이나 읽을 수 있다.
- apktool과 jadx가 매니페스트 사실에서 완전히 일치. 둘의 쓰임은 재패키징(smali) 대 로직 읽기(Java)로 갈린다.

---

## 근본 원인과 보안 영향

- targetSdk 29에서는 intent-filter를 가진 컴포넌트가 `android:exported`를 명시하지 않아도 exported됩니다. 개발자가 "열었다"는 인식 없이 열리는 게 문제의 핵심입니다. 그래서 실제 공격 표면이 명시적 exported 목록보다 넓습니다.
- 커스텀 권한을 normal로 두면 보호가 사라집니다. 민감 컴포넌트를 지킬 권한은 `signature`(같은 키로 서명한 앱만) 수준이어야 합니다.
- `debuggable`은 `run-as`·디버거로 앱 내부를 열어 주고(S04에서 활용), `allowBackup`은 `adb backup`으로 데이터 반출을 허용하며, `usesCleartextTraffic`은 평문 HTTP를 허용합니다(S10에서 확인).

## 수정 방법

- 모든 컴포넌트에 `android:exported`를 명시하고, 외부에 열 필요가 없으면 `false`로 둔다(그리고 targetSdk를 31 이상으로 올려 명시를 강제받는다).
- 민감 컴포넌트를 지키는 커스텀 권한은 `android:protectionLevel="signature"`로 선언한다.
- `android:debuggable`은 릴리스에서 제거, `allowBackup="false"`, 그리고 평문 대신 Network Security Config로 HTTPS를 강제한다.

수정 전후의 매니페스트는 결국 이 한 줄들의 차이입니다.

```xml
<!-- 전 -->
<activity android:name=".AboutUsActivity" android:exported="true"/>
<permission android:name="com.insecureshop.permission.READ"/>
<!-- 후 -->
<activity android:name=".AboutUsActivity" android:exported="false"/>
<permission android:name="com.insecureshop.permission.READ" android:protectionLevel="signature"/>
```

## 재검증

이 편은 대상 앱을 고치는 게 아니라 표면을 확정하는 편이라, 재검증은 "정적으로 exported라고 읽은 것이 실제로 열려 있는가"였고, 위 스크린샷으로 확인했습니다. 실제 수정→재빌드→재검증은 뒤에서 특정 취약점을 다룰 때 그 컴포넌트를 대상으로 수행합니다.

---

## 참고 자료

- Android Developers — `android:exported` 기본값 변경(API 31)과 컴포넌트 노출
- Android Developers — 커스텀 권한과 `protectionLevel`
- Apktool / jadx 문서

