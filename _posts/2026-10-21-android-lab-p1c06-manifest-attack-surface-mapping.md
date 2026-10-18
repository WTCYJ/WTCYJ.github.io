---
layout: post
title: "매니페스트 공격 표면 매핑 — exported만 세면 놓치는 것들"
date: 2026-10-21 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, AndroidManifest, AttackSurface, exported, apktool, NetworkSecurityConfig, DeepLink, IntentFilter]
excerpt: "exported가 true이고 권한이 없는 컴포넌트만 거르는 스크립트는 InsecureShop(targetSdk 29)에서 intent-filter로 열린 액티비티를 하나도 잡지 못했다. 파서 기본값과 권한 보호 수준을 반영한 매퍼로 다시 그린 지도대로, 다른 키로 서명한 앱이 alias를 거쳐 exported=false 액티비티를 띄웠다."
---

[지난 글](/posts/android-lab-p1c05-apktool-smali/)에서 apktool로 바이너리 매니페스트를 텍스트로 풀었다. 풀린 `AndroidManifest.xml`에는 다른 앱이 어느 컴포넌트까지 들어올 수 있는지가 거의 다 적혀 있어서 이번에는 그 목록을 스크립트로 뽑아 봤다.

손에 익은 기준은 `android:exported="true"`이면서 `android:permission`이 없는 컴포넌트다. 그 조건을 그대로 옮긴 스크립트를 교육용 취약 앱 InsecureShop에 돌렸더니 intent-filter를 달고 열려 있는 액티비티가 결과에서 통째로 빠졌다. 빠진 액티비티들에는 exported 값이 아예 적혀 있지 않았고 그 값은 설치할 때 패키지 파서가 채운다.

실험은 Android 13 에뮬레이터(API 33, x86_64, userdebug, 보안 패치 2024-03-01)와 호스트에서 했다. 호스트에서는 apktool 3.0.2, aapt2 2.20-13193326, Python 3.11(표준 라이브러리만), Android Gradle Plugin 8.5.2(Gradle 8.9)를 썼고 Java 도구는 Android Studio에 딸린 JBR 21.0.10에서 돌렸다. 소스 링크는 Android 13 태그인 frameworks/base `android-13.0.0_r84`로 건다. 화면에 나오는 `adb -s $S`의 `$S`는 에뮬레이터 시리얼(`emulator-5600`)이다.

## 시스템 서버가 다른 앱의 호출을 거르는 순서

매니페스트를 지도로 읽어도 되는 근거는 시스템 서버 쪽에 있다. 다른 앱이 컴포넌트에 닿는 길마다 시스템 서버가 권한 검사를 부르는 자리가 있다.

| 경로 | 검사를 부르는 곳 |
|--|--|
| 액티비티 시작 | [ActivityTaskSupervisor.java 1234행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#1234) |
| 서비스 바인드 | [ActiveServices.java 3538행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActiveServices.java#3538) |
| 매니페스트 리시버로 가는 브로드캐스트 | [BroadcastQueue.java 1585행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/BroadcastQueue.java#1585) |
| provider 연결 | [ContentProviderHelper.java 1532행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ContentProviderHelper.java#1532) |

어느 경로든 [`ActivityManagerService.checkComponentPermission()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActivityManagerService.java#5876)을 거쳐 [`ActivityManager.checkComponentPermission()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityManager.java#4216)에서 끝난다. 이때 넘어가는 값은 호출자 PID와 UID, 컴포넌트 주인 UID, 설치 때 매니페스트에서 파싱해 둔 permission과 exported다.

![android-13.0.0_r84 ActivityManager.java 4210~4250행. 4216행 checkComponentPermission(String permission, int uid, int owningUid, boolean exported) 선언, 4220행 ROOT_UID 또는 SYSTEM_UID 면 PERMISSION_GRANTED, 4224행 isolated 프로세스는 DENIED, 4229행 isSameApp 이면 GRANTED, 4233행 !exported 면 DENIED, 4242행 permission == null 이면 GRANTED, 4246~4247행 나머지는 checkUidPermission 으로 넘기는 코드](/assets/img/android-mastery/p1c06/08-src-checkcomponentpermission.png)

판정은 위에서 아래로 내려간다. 그 앞에서 AMS 쪽 래퍼가 시스템 서버 자신의 프로세스(`MY_PID`)는 바로 통과시키고 호출자 프로세스의 `deniedPermissions`에 그 권한이 들어 있으면 바로 거부한다([5878~5895행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActivityManagerService.java#5878)). 나머지가 위 화면이다. root와 system UID는 무조건 통과하고 isolated 프로세스는 막힌다. 같은 앱(같은 UID)이면 통과하는데, `android:sharedUserId`로 UID를 나눠 쓰는 앱끼리도 이 분기에서 exported 검사 없이 지나간다. 이번에 돌린 앱들에는 sharedUserId가 없었고 뒤에 나올 매퍼는 이 속성을 보면 INFO 줄만 찍는다. 그다음 exported가 false면 거부, permission이 비어 있으면 허용이고 남은 경우만 호출자가 그 권한을 가졌는지 본다. 앱 코드가 끼어들기 전에 매니페스트의 두 값으로 허용과 거부가 갈리니, 매니페스트를 제대로 읽기만 하면 다른 앱이 어디까지 닿는지 상당히 정확하게 예측할 수 있다. 컴포넌트와 Binder 호출의 큰 그림은 [Atlas C21](/posts/android-concept-atlas-c21-components-binder/)에 있다.

## exported가 true이고 권한이 없는 것만 거르면

이 기준을 코드로 옮기면 `naive_map.py`가 된다.

```python
# naive_map.py: exported="true" and no android:permission, nothing else
import sys
import xml.etree.ElementTree as ET
ns = '{http://schemas.android.com/apk/res/android}'
root = ET.parse(sys.argv[1]).getroot()
for tag in ('activity','service','receiver','provider'):
    for c in root.iter(tag):
        exported = c.get(ns+'exported')
        perm = c.get(ns+'permission')
        has_filter = c.find('intent-filter') is not None
        if exported == 'true' and not perm:
            print(f'[EXPORTED, NO PERMISSION] {tag} {c.get(ns+"name")}')
```

InsecureShop APK를 apktool로 디코드해서 돌렸다. `-s`는 smali 디스어셈블을 건너뛰고 `-p fw`는 apktool이 쓰는 프레임워크 리소스(`1.apk`)를 작업 폴더의 `fw/`에 두게 한다.

![apktool d -f -s -p fw -o decoded/insecureshop apps/edu/insecureshop.apk 의 디코드 로그(Using Apktool 3.0.2, Loading resource table from file: fw\1.apk), grep -c uses-sdk 를 디코드된 매니페스트에 돌린 결과 0, apktool.yml 의 sdkInfo 아래 minSdkVersion 16 과 targetSdkVersion 29, aapt2 dump xmltree 에서 뽑은 targetSdkVersion(0x01010270)=29, naive_map.py 가 AboutUsActivity, ResultActivity, net.gotev.uploadservice.UploadService, InsecureShopProvider 네 줄을 EXPORTED, NO PERMISSION 으로 찍은 터미널](/assets/img/android-mastery/p1c06/01-naive-insecureshop.png)

나온 건 `exported="true"`를 명시한 네 개뿐이다. 화면 가운데에 찍힌 `grep -c uses-sdk` 결과 0은 매퍼를 만들 때 문제가 된다. 디코드된 매니페스트에는 `<uses-sdk>`가 없다. apktool 3.0.2가 이 요소를 매니페스트에서 빼서 `apktool.yml`의 `sdkInfo`로 옮겼기 때문이다. APK 안의 바이너리 매니페스트를 aapt2로 덤프하면([3장](/posts/android-lab-p1c03-apk-triage/)에서 쓴 `aapt2 dump xmltree`) `targetSdkVersion(0x01010270)=29`가 그대로 있다. 디코드된 XML 하나만 읽는 스크립트는 targetSdk를 모르는데, 아래에서 보듯 기본값 규칙 대부분이 targetSdk에 따라 갈린다.

## 속성을 비워 두면 파서가 채우는 값

InsecureShop 매니페스트의 `WebViewActivity`는 이렇게 생겼다.

```xml
        <activity android:name="com.insecureshop.WebViewActivity">
            <intent-filter>
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:host="com.insecureshop" android:scheme="insecureshop"/>
            </intent-filter>
        </activity>
```

exported 속성이 없으니 값은 패키지 파서가 [`ParsedActivityUtils.java` 464~476행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedActivityUtils.java#464)에서 정한다.

![android-13.0.0_r84 ParsedActivityUtils.java 458~488행. 464행 if (!setExported) 아래 465행에서 hasIntentFilters 를 구하고, intent-filter 가 있으면 467~471행에서 "Targeting S+ (version " + Build.VERSION_CODES.S + " and above) requires that an explicit value for android:exported be defined when intent filters are present" 메시지와 DeferredError.MISSING_EXPORTED_FLAG 로 deferError 를 만든 뒤, 476행 activity.setExported(hasIntentFilters) 를 호출하는 코드](/assets/img/android-mastery/p1c06/04-src-implicit-exported.png)

속성이 없으면 intent-filter가 하나라도 있느냐가 곧 exported 값이 된다(476행). 리시버와 activity-alias도 같은 함수 `parseActivityOrAlias`를 거치고 서비스에는 [`ParsedServiceUtils.java` 166~178행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedServiceUtils.java#166)에 같은 코드가 있다. 467~471행의 `deferError`는 곧바로 오류가 되지 않는다. `MISSING_EXPORTED_FLAG`는 [`ParseInput.java` 80행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/parsing/result/ParseInput.java#80)에 `@EnabledAfter(targetSdkVersion = R)`로 묶인 호환성 변경이라 앱의 targetSdk가 31 이상일 때만 오류로 바뀐다. 흔히 "API 31부터 exported 명시가 필수"라고 줄여 말하는데, 기준은 기기 API가 아니고 앱의 targetSdk다. 플랫폼에서 거르는 쪽은 Android 12 이상 기기의 패키지 파서이고 시점은 설치할 때다(빌드 도구가 먼저 잡기도 하는데, 아래에서 본다). 설치 자체가 막힌다는 설명은 [Android 12 동작 변경 문서](https://developer.android.com/about/versions/12/behavior-changes-12#exported)에도 있다.

provider는 기본값 규칙이 다르다. 속성이 없으면 [`ParsedProviderUtils.java` 86~93행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedProviderUtils.java#86)이 `targetSdkVersion < JELLY_BEAN_MR1`, 곧 targetSdk 16 이하일 때만 true로 둔다. intent-filter와는 상관이 없다.

## 함정을 한 매니페스트에 모은 자작 앱

파서 기본값이 실제로 걸리는지 보려고 함정을 하나씩 넣은 자작 앱 `io.seika.surface`를 만들었다. exported를 비워 둔 컴포넌트 말고도 뒤에서 다룰 normal 권한, activity-alias, NSC, 한 필터에 섞은 딥링크를 넣었다. 매니페스트(`apps/surface/manifests/vuln.xml`)는 이렇다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="io.seika.surface"
    android:versionCode="1" android:versionName="1.0-vuln">

    <!-- no protectionLevel: the default is "normal" -->
    <permission android:name="io.seika.surface.permission.ADMIN"/>
    <permission android:name="io.seika.surface.permission.VAULT"
        android:protectionLevel="signature"/>
    <uses-permission android:name="android.permission.INTERNET"/>

    <application android:label="Surface Lab"
        android:debuggable="true"
        android:usesCleartextTraffic="false"
        android:networkSecurityConfig="@xml/nsc">

        <activity android:name=".MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>

        <activity android:name=".DebugActivity" android:exported="true"/>

        <activity android:name=".InternalActivity" android:exported="false"/>

        <activity-alias android:name=".ShareAlias"
            android:targetActivity=".InternalActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.SEND"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <data android:mimeType="text/plain"/>
            </intent-filter>
        </activity-alias>

        <activity android:name=".DisabledActivity"
            android:exported="true" android:enabled="false"/>

        <activity android:name=".LinkActivity">
            <intent-filter android:autoVerify="true">
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:scheme="seika" android:host="cb"/>
                <data android:scheme="https" android:host="app.seika.test"
                    android:pathPrefix="/open"/>
            </intent-filter>
        </activity>

        <receiver android:name=".SyncReceiver">
            <intent-filter>
                <action android:name="io.seika.surface.SYNC"/>
            </intent-filter>
        </receiver>

        <service android:name=".AdminService" android:exported="true"
            android:permission="io.seika.surface.permission.ADMIN"/>
        <service android:name=".VaultService" android:exported="true"
            android:permission="io.seika.surface.permission.VAULT"/>

        <provider android:name=".NotesProvider"
            android:authorities="io.seika.surface.notes"
            android:exported="true"
            android:readPermission="io.seika.surface.permission.VAULT"/>
        <provider android:name=".FilesProvider"
            android:authorities="io.seika.surface.files"
            android:exported="false"
            android:grantUriPermissions="true"/>
    </application>
</manifest>
```

`MainActivity`, `LinkActivity`, `SyncReceiver`는 exported 없이 intent-filter만 달았다. 위 규칙을 빌드 단계에서 잡는지는 빌드 경로마다 달랐다. 이 매니페스트를 targetSdk만 30과 33으로 바꿔 Gradle 없이 javac, d8, aapt, zipalign, apksigner를 직접 이어 붙여 두 번 빌드했다. 옛 aapt를 쓰는 이 경로는 두 빌드 모두 오류 없이 서명된 APK를 내놓았고(`apksigner verify` 통과), 바이너리 매니페스트를 비교하면 다른 곳은 targetSdk 한 줄이다. 빌드 명령은 `mkapk`로 묶어 두었고(프로브 앱도 뒤에서 같은 스크립트로 빌드한다) 변형마다 소스와 매니페스트를 새 폴더에 복사해 돌렸다.

```bash
for v in surface-t30:vuln.xml:30 surface-t33-implicit:vuln.xml:33 surface-fixed:fixed.xml:33; do
  IFS=: read name manifest target <<< "$v"
  rm -rf build/$name && mkdir -p build/$name out
  cp -r apps/surface/src apps/surface/res build/$name/
  cp apps/surface/manifests/$manifest build/$name/AndroidManifest.xml
  mkapk build/$name out/$name.apk --key debug --min 26 --target $target
done
```

`surface-fixed`는 뒤에서 다룰 방어 매니페스트(`fixed.xml`)로 만든 빌드다.

```text
$ diff <(aapt2 dump xmltree out/surface-t30.apk --file AndroidManifest.xml) <(aapt2 dump xmltree out/surface-t33-implicit.apk --file AndroidManifest.xml)
12c12
<         A: http://schemas.android.com/apk/res/android:targetSdkVersion(0x01010270)=30
---
>         A: http://schemas.android.com/apk/res/android:targetSdkVersion(0x01010270)=33
```

같은 매니페스트를 Android Gradle Plugin 프로젝트에 넣으면 결과가 다르다. AGP 8은 패키지 이름을 Gradle의 `namespace`에서 받으므로 매니페스트에서 `package` 한 줄만 지웠고 targetSdk는 명령줄 속성으로 바꿀 수 있게 했다.

```kotlin
// agp/app/build.gradle.kts
plugins { id("com.android.application") }
android {
    namespace = "io.seika.surface"
    compileSdk = 34
    defaultConfig {
        applicationId = "io.seika.surface"
        minSdk = 26
        targetSdk = (project.findProperty("target") as String? ?: "33").toInt()
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
```

![agp 폴더에서 diff ../apps/surface/manifests/vuln.xml app/src/main/AndroidManifest.xml 결과 3d2 package="io.seika.surface" 한 줄만 다름, grep 으로 본 build.gradle.kts 8행 targetSdk = (project.findProperty("target") ...), gradle --no-daemon --offline -q -Ptarget=33 assembleDebug 출력에서 AndroidManifest.xml 16:9-21:20, 40:9-49:20, 51:9-55:20 세 곳의 Error: android:exported needs to be explicitly specified for element activity#io.seika.surface.MainActivity, activity#io.seika.surface.LinkActivity, receiver#io.seika.surface.SyncReceiver 와 Execution failed for task ':app:processDebugMainManifest', Manifest merger failed with multiple errors, BUILD FAILED in 24s. 이어서 -Ptarget=30 빌드는 exit=0, aapt2 dump badging 은 package name='io.seika.surface' versionName='1.0-vuln' 과 targetSdkVersion:'30'](/assets/img/android-mastery/p1c06/12-agp-missing-exported.png)

targetSdk 33에서는 매니페스트 병합 단계(`processDebugMainManifest`)가 `android:exported needs to be explicitly specified` 오류를 MainActivity, LinkActivity, SyncReceiver에 하나씩 내고 빌드를 멈췄다. exported 없이 intent-filter만 단 세 컴포넌트 그대로다. intent-filter가 있어도 `exported="true"`를 적어 둔 `ShareAlias`는 걸리지 않았다. targetSdk만 30으로 내리면 같은 매니페스트가 `exit=0`으로 빌드되고 badging에 `targetSdkVersion:'30'`이 찍힌다. AGP 8.5.2로는 targetSdk 33과 30만 빌드해 봤고 다른 AGP 버전의 동작은 확인하지 않았다.

옛 aapt가 통과시킨 targetSdk 33 APK는 기기에서 막힌다. 먼저 `adb -s $S uninstall io.seika.prober`, `adb -s $S uninstall io.seika.surface`로 두 앱을 지워 두고 두 APK를 Android 13 에뮬레이터에 차례로 깔았다.

![에뮬레이터 대상 터미널. adb -s $S shell getprop ro.build.version.sdk 결과 33, adb -s $S install out/surface-t33-implicit.apk 는 Failure 뒤 대괄호 안에 INSTALL_PARSE_FAILED_MANIFEST_MALFORMED: Failed parse during installPackageLI: /data/app/vmdl1487434048.tmp/base.apk (at Binary XML file line #22): io.seika.surface.MainActivity: Targeting S+ (version 31 and above) requires that an explicit value for android:exported be defined when intent filters are present, 이어서 adb -s $S install out/surface-t30.apk 는 Success](/assets/img/android-mastery/p1c06/05-device-install-gate.png)

targetSdk 33 빌드는 `INSTALL_PARSE_FAILED_MANIFEST_MALFORMED`로 거부됐고 대괄호 안 끝부분은 467~471행이 만드는 메시지 그대로다. 이름이 찍힌 컴포넌트는 MainActivity 하나다. 472~474행이 처음 오류가 난 컴포넌트에서 파싱을 끝내서, AGP처럼 셋을 한꺼번에 알려 주지 않는다. targetSdk만 30인 같은 매니페스트는 `Success`로 깔렸다. 그래서 Android 12 이상 기기에 깔린 앱 가운데 암시적 export가 남는 것은 InsecureShop(targetSdk 29)처럼 targetSdk 30 이하인 앱이다.

## 기본값을 반영한 매퍼로 다시 본 InsecureShop

이 기본값들을 반영한 매퍼가 `map_surface.py`다. apktool이 디코드한 폴더를 받아 매니페스트와 `apktool.yml`, `res/`를 같이 읽고 플랫폼 권한의 보호 수준을 알아내려고 같은 태그의 `core/res/AndroidManifest.xml`도 넘겨받는다. `@bool/` 참조는 `res/values/bools.xml`에서 풀고 `values-v31` 같은 버전별 덮어쓰기는 보지 않는다. 플랫폼 매니페스트는 gitiles에서 base64로 받는다.

```bash
curl -s "https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/res/AndroidManifest.xml?format=TEXT" | base64 -d > aosp13-core-AndroidManifest.xml
python map_surface.py decoded/insecureshop --platform aosp13-core-AndroidManifest.xml
```

![map_surface.py 를 decoded/insecureshop 에 돌린 결과. com.insecureshop minSdk 16 targetSdk 29 (from apktool.yml), ChooserActivity, ProductListActivity, WebViewActivity, WebView2Activity 가 OPEN 에 exported=true (implicit: has intent-filter), AboutUsActivity 와 ResultActivity 와 UploadService 는 OPEN explicit, InsecureShopProvider 는 OPEN 에 read: com.insecureshop.permission.READ (normal, this app) write: - [open side: read/write], CartListActivity, LoginActivity, PrivateActivity, SendingDataViaActionActivity 는 INTERNAL, FileProvider 는 INTERNAL [grantUriPermissions], FLAG debuggable=true, allowBackup=true (explicit), usesCleartextTraffic=true (explicit), LINK .WebViewActivity autoVerify=false BROWSABLE insecureshop://com.insecureshop](/assets/img/android-mastery/p1c06/02-map-insecureshop.png)

`ChooserActivity`, `ProductListActivity`, `WebViewActivity`, `WebView2Activity`가 새로 OPEN에 올라왔다. 넷 다 exported 속성 없이 intent-filter만 달았고 targetSdk 29라 Android 13에도 문제없이 깔린다. 에뮬레이터에 깔고 띄워 봤다. 이 에뮬레이터의 `adb shell`은 root로 돌기 때문에, 위에서 본 root 분기를 피하려고 `su shell`을 붙여 셸 UID(2000)에서 실행했다.

```text
$ adb -s $S install apps/edu/insecureshop.apk
Performing Streamed Install
Success
$ adb -s $S shell su shell am start -W -n com.insecureshop/.WebViewActivity 2>&1 | grep -E "Status|Activity:|Exception" | cut -c1-200
Status: ok
Activity: com.insecureshop/.WebViewActivity
$ adb -s $S shell su shell am start -W -n com.insecureshop/.CartListActivity 2>&1 | grep -E "Status|Activity:|Exception" | cut -c1-200
Exception occurred while executing 'start':
java.lang.SecurityException: Permission Denial: starting Intent { flg=0x10000000 cmp=com.insecureshop/.CartListActivity } from null (pid=6702, uid=2000) not exported from uid 10186
```

intent-filter만 단 `WebViewActivity`는 열렸고 속성도 필터도 없는 `CartListActivity`는 `not exported`로 막혔다. `WebViewActivity`는 BROWSABLE 카테고리까지 달아 `insecureshop://com.insecureshop` 링크로 열리게 선언돼 있다. `naive_map.py`도 `has_filter`를 구하기는 하지만 판정에 쓰지 않으니 이 넷은 처음부터 빠질 수밖에 없었다.

## normal 권한과 provider의 읽기·쓰기 분리

같은 결과에서 provider 줄은 다른 이유로 OPEN이다. `InsecureShopProvider`에는 `android:readPermission="com.insecureshop.permission.READ"`가 걸려 있고 그 권한은 앱이 직접 선언했다.

```xml
    <permission android:name="com.insecureshop.permission.READ"/>
```

`protectionLevel`을 적지 않은 권한은 normal이다. [permission 요소 문서](https://developer.android.com/guide/topics/manifest/permission-element)는 normal 권한을 요청한 앱에 시스템이 설치 시점에 사용자 확인 없이 권한을 준다고 쓴다. 아무 앱이나 `<uses-permission>` 한 줄로 이 읽기 권한을 얻는다. 매퍼는 권한 이름이 있느냐 대신 그 권한의 보호 수준을 찾는다. 앱이 선언한 `<permission>`과 플랫폼 매니페스트를 뒤져서 signature 계열일 때만 GUARDED로 두고 사용자가 허용하면 그만인 dangerous는 normal과 함께 OPEN 쪽에 넣었다.

```python
# map_surface.py 105~113행
    def guard(perm):
        """-> (text, state) with state 'open' | 'guarded' | 'unknown'"""
        if not perm:
            return '-', 'open'
        if perm not in levels:
            return perm + ' (not declared here or in platform: level unknown)', 'unknown'
        lvl, where = levels[perm]
        state = 'guarded' if lvl.split('|')[0] in GUARDED_LEVELS else 'open'
        return '%s (%s, %s)' % (perm, lvl, where), state
```

`GUARDED_LEVELS`는 `signature`, `signatureOrSystem`, `internal`이다. AndroGoat에 같이 돌려 보니 `androidx.profileinstaller.ProfileInstallReceiver`가 `android.permission.DUMP`로 막혀 있었고 플랫폼 매니페스트에서 찾은 보호 수준(signature에 privileged, development 플래그)을 보고 GUARDED로 분류했다. 다른 앱이 선언한 권한처럼 두 매니페스트 어디에도 없는 이름은 보호 수준을 알 수 없어서 CHECK로 남긴다. 기기의 `dumpsys package`에서 찾아오는 기능은 넣지 않았다. 권한 보호 수준 자체는 [Atlas C10](/posts/android-concept-atlas-c10-permissions-appops/)에 정리돼 있다.

provider는 읽기와 쓰기 권한을 따로 갖는다. [`ParsedProviderUtils.java` 95~116행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedProviderUtils.java#95)을 보면 `readPermission`이 없으면 `permission`을, 그것도 없으면 `<application android:permission>`을 읽기 권한으로 쓰고 쓰기 쪽도 같은 순서를 밟는다. provider 연결을 허락하는 [`ContentProviderHelper.java` 1532~1541행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ContentProviderHelper.java#1532)은 읽기와 쓰기 중 한쪽만 통과해도 연결을 내준다. 연결된 뒤 쓰기 호출을 거르는 [`ContentProvider.java`의 `enforceWritePermissionInner()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/ContentProvider.java#885)는 쓰기 권한이 비어 있으면 기본적으로 쓰기를 허용한다(911행 `allowDefaultWrite`). `<path-permission>`에서 거부된 경로 권한은 이 기본 쓰기 허용을 거둬 가는데([925행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/ContentProvider.java#925)), 매퍼는 경로 권한까지는 따지지 않는다. 앞에서 본 InsecureShop 지도의 provider 줄 끝에 붙은 `[open side: read/write]`는 읽기 쪽이 normal 권한이고 쓰기 쪽은 비어 있어 양쪽이 다 열렸다는 표시다.

## 권한을 물려받지 않는 activity-alias

`<application android:permission>`도 상속된다. 컴포넌트에 자기 permission이 없으면 앱 전체의 값을 쓴다([`ParsedServiceUtils.java` 88~90행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedServiceUtils.java#88)). 액티비티 쪽 코드를 열어 보니 alias만 예외였다.

![android-13.0.0_r84 ParsedActivityUtils.java 327~346행. 333행에서 permission 속성을 읽고, 334행 if (isAlias) 안의 주석 An alias will override permissions to allow referencing an Activity through its alias without needing the original permission. If an alias needs the same permission, it must be re-declared. 아래 338행 activity.setPermission(permission), else 쪽 340행 activity.setPermission(permission != null ? permission : pkg.getPermission())](/assets/img/android-mastery/p1c06/09-src-alias-permission.png)

`<activity-alias>`는 자기가 선언한 permission만 쓰고 앱 전체 권한도, 대상 액티비티의 권한도 물려받지 않는다. alias 객체를 만드는 [`ParsedActivityImpl.java` 194~198행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedActivityImpl.java#194)에는 대상에서 `enabled`, `exported`, `permission`을 복사하는 줄이 주석 처리돼 있다. 대상 액티비티를 exported="false"로 잠가 두고 exported alias를 하나 달면, 다른 앱은 그 alias를 거쳐 대상 액티비티를 띄울 수 있다. alias의 permission이 대상의 권한을 대신하고 alias에 permission이 없으면 권한 없이 열린다는 내용은 [activity-alias 요소 문서](https://developer.android.com/guide/topics/manifest/activity-alias-element)에도 나온다.

`android:enabled="false"`인 컴포넌트는 반대 방향으로 헷갈린다. 지금은 시스템이 찾아 주지 않지만 앱이 런타임에 `PackageManager.setComponentEnabledSetting()`으로 켤 수 있다. 매퍼는 이런 줄을 지우지 않고 DISABLED로 따로 표시한다.

## 자작 앱에 두 스크립트를 돌린 결과

`naive_map.py`는 앞의 자작 앱 매니페스트에서 세 줄을 찍었다.

```text
[EXPORTED, NO PERMISSION] activity .DebugActivity
[EXPORTED, NO PERMISSION] activity .DisabledActivity
[EXPORTED, NO PERMISSION] provider .NotesProvider
```

꺼져 있는 `DisabledActivity`는 잘못 잡았고 `NotesProvider`는 맞게 잡았지만 `android:permission`이 없다는 엉뚱한 이유였다. 암시적으로 열린 `MainActivity`, `LinkActivity`, `SyncReceiver`와 alias인 `ShareAlias`, normal 권한으로 막아 둔 `AdminService`는 빠졌다. targetSdk 30으로 빌드한 APK를 `map_surface.py`로 돌린 결과다.

![apktool d -q -f -s -p fw -o decoded/surface-t30 out/surface-t30.apk 뒤 map_surface.py 를 돌린 결과. io.seika.surface minSdk 26 targetSdk 30, OPEN 에 MainActivity, LinkActivity, SyncReceiver(implicit: has intent-filter)와 DebugActivity, alias .ShareAlias(alias of .InternalActivity, target .InternalActivity itself has exported=false), AdminService(ADMIN normal, this app), NotesProvider(read: VAULT signature, write: -, open side: write), GUARDED VaultService(VAULT signature), INTERNAL InternalActivity 와 FilesProvider, DISABLED DisabledActivity(enabled=false), FLAG debuggable=true, allowBackup=true (attribute absent, default true), cleartext via @xml/nsc: base-config false, allowed for 10.0.2.2 (usesCleartextTraffic=false is ignored), LINK .LinkActivity autoVerify=true BROWSABLE 와 seika://cb/open* seika://app.seika.test/open* https://cb/open* https://app.seika.test/open*](/assets/img/android-mastery/p1c06/03-map-lab.png)

`map_surface.py`에서 컴포넌트 하나의 상태를 정하는 부분이다.

```python
# map_surface.py 124~162행
    for e in comps:
        name = full(at(e, 'name'))
        filters = e.findall('intent-filter')
        ex = as_bool(at(e, 'exported'), bools)
        if ex is None:
            if e.tag == 'provider':
                ex, how = target < 17, 'default for provider'
            elif filters:
                ex, how = True, 'implicit: has intent-filter'
                if target >= 31:
                    how += ', install fails on API 31+'
            else:
                ex, how = False, 'default'
        else:
            how = 'explicit' if isinstance(ex, bool) else 'unresolved ' + at(e, 'exported')
        exported_of[name] = ex
        enabled = as_bool(at(e, 'enabled'), bools) is not False

        if e.tag == 'provider':
            p = at(e, 'permission')
            perms = [('read', at(e, 'readPermission') or p or app_perm),
                     ('write', at(e, 'writePermission') or p or app_perm)]
        elif e.tag == 'activity-alias':
            perms = [('perm', at(e, 'permission'))]  # an alias never inherits a permission
        else:
            perms = [('perm', at(e, 'permission') or app_perm)]
        g = [(k,) + guard(v) for k, v in perms]
        states = {s for _, _, s in g}

        if not enabled:
            status = 'DISABLED'
        elif ex is not True:
            status = 'INTERNAL' if ex is False else 'CHECK'
        elif 'open' in states:
            status = 'OPEN'
        elif 'unknown' in states:
            status = 'CHECK'
        else:
            status = 'GUARDED'
```

targetSdk는 `apktool.yml`에서 읽고 매니페스트에 `<uses-sdk>`가 남아 있으면 그쪽을 쓴다. 둘 다 없으면 `--target`을 달라며 멈춘다. 같은 디코드 결과를 `--target 33`으로 판정하면 `MainActivity` 줄이 `implicit: has intent-filter, install fails on API 31+`로 바뀐다. 여기서 API 31+는 설치하는 기기 쪽(Android 12 이상)을 가리키고 이 문구는 앱의 targetSdk가 31 이상일 때만 붙는다. 매퍼와 함께 만든 `test_map_surface.py`가 자작 앱의 상태 분류 전부와 `<application android:permission>` 상속, alias 예외, targetSdk 16과 17에서 달라지는 provider 기본값을 assert로 확인하고 `map_surface self-check passed`를 찍는다.

## 다른 키로 서명한 앱으로 지도를 맞춰 보기

지도대로라면 다른 앱은 `ShareAlias`를 컴포넌트 이름으로 지정한 인텐트만으로(액션 없이) exported="false"인 `InternalActivity`를 띄운다. ADMIN을 요청하기만 하면 `AdminService`에 바인드하고, 읽기 권한이 없어도 `NotesProvider`에 insert한다. `VaultService`와 `NotesProvider` 읽기는 같은 키로 서명한 앱만 통과한다. 이걸 맞춰 보려고 프로브 앱 `io.seika.prober`를 만들었다. ADMIN과 VAULT를 둘 다 요청하고 자작 앱과 다른 키(`CN=Attacker Lab`)로 서명했다. 빌드는 자작 앱과 같은 javac, d8, aapt, zipalign, apksigner 경로를 묶어 둔 스크립트(`mkapk`)로 targetSdk 33에 맞췄고, 자작 앱(targetSdk 30)을 깐 다음 같은 에뮬레이터에 깔았다.

```bash
mkapk apps/prober out/prober.apk --key attacker --min 26 --target 33
adb -s $S install out/prober.apk
```

targetSdk 30 이상인 프로브는 패키지 가시성 규칙에 걸려 그냥은 다른 앱의 provider와 서비스를 찾지 못한다. 그래서 프로브 매니페스트에 대상 패키지를 적어 두었다([Atlas C11](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)).

```xml
    <queries>
        <package android:name="io.seika.surface"/>
    </queries>
```

깔고 나니 권한부터 갈렸다.

![adb -s $S shell dumpsys package io.seika.prober 에서 requested permissions: 와 install permissions: 아래 두 줄씩을 grep 으로 거른 결과. requested permissions 에 io.seika.surface.permission.ADMIN 과 io.seika.surface.permission.VAULT, install permissions 에 io.seika.surface.permission.ADMIN: granted=true 와 io.seika.surface.permission.VAULT: granted=false](/assets/img/android-mastery/p1c06/21-device-prober-permissions.png)

normal인 ADMIN은 `granted=true`, signature인 VAULT는 `granted=false`다. 프로브의 `ProbeActivity`는 자작 앱의 컴포넌트를 하나씩 건드리고 결과를 `PROBE` 태그로 남긴다. 자작 앱 쪽 클래스는 호출을 받으면 `SURFACE` 태그로 남긴다. logcat을 비우고(`adb -s $S logcat -c`) 프로브를 띄운 뒤 5초 기다렸다가 두 태그를 모았다.

![adb -s $S shell am start -W -n io.seika.prober/.ProbeActivity 결과 Status: ok 와 Activity: io.seika.surface/.MainActivity, 이어서 adb -s $S logcat -d -v tag -s PROBE SURFACE 출력을 grep -v "full message" 로 거른 결과. PROBE 줄은 target io.seika.surface (other signer), activity .MainActivity started, .DebugActivity started, .InternalActivity SecurityException, .ShareAlias started, .DisabledActivity ActivityNotFoundException, receiver .SyncReceiver sent, service .AdminService bindService=true 와 connected, .VaultService SecurityException, provider notes query SecurityException, notes insert -> content://io.seika.surface.notes/n/1, files query SecurityException. SURFACE 줄은 AdminService onBind, NotesProvider insert content://io.seika.surface.notes/n note=from-prober, SyncReceiver got action=io.seika.surface.SYNC who=prober, InternalActivity started (intent component=.ShareAlias, data=null), DebugActivity started, MainActivity started](/assets/img/android-mastery/p1c06/10-device-prober-logcat.png)

거부 사유는 시스템 서버 쪽 로그에 남는다. 이 캡처 뒤에 버퍼를 비우지 않고 `adb -s $S logcat -d -v time "*:W" | grep -E "Permission Denial|seika"` 결과를 파일로 저장해 두었다. 거기서 시스템 서버(pid 511)가 프로브(pid 4155)에 남긴 거부 줄을 옮긴다.

```text
10-15 02:19:46.854 W/ActivityTaskManager(  511): Permission Denial: starting Intent { cmp=io.seika.surface/.InternalActivity (has extras) } from ProcessRecord{c655ecd 4155:io.seika.prober/u0a180} (pid=4155, uid=10180) not exported from uid 10179
10-15 02:19:46.941 W/ActivityManager(  511): Permission Denial: Accessing service io.seika.surface/.VaultService from pid=4155, uid=10180 requires io.seika.surface.permission.VAULT
10-15 02:19:47.361 W/ContentProviderHelper(  511): Permission Denial: opening provider io.seika.surface.FilesProvider from ProcessRecord{c655ecd 4155:io.seika.prober/u0a180} (pid=4155, uid=10180) that is not exported from UID 10179
```

프로브 결과는 지도의 상태와 하나하나 맞았다. `ShareAlias`로 보낸 인텐트는 자작 앱 쪽에 `InternalActivity started (intent component=.ShareAlias, data=null)`로 찍혀, exported="false"인 액티비티가 alias 이름으로 열렸다. ADMIN 하나만 받은 프로브는 `AdminService`에 `connected`까지 갔고 `VaultService` 바인드는 `requires io.seika.surface.permission.VAULT`로 거부됐다. `NotesProvider`에서 막힌 건 읽기뿐이었다. query는 `SecurityException`으로 끝났지만 같은 프로브의 insert는 `content://io.seika.surface.notes/n/1`을 돌려받았고 자작 앱 쪽에도 insert 로그가 남았다. 읽기나 쓰기 한쪽만 통과해도 연결을 내주는 규칙과 비어 있는 쓰기 권한을 허용하는 `allowDefaultWrite`가 기기에서도 똑같이 작동한 결과다. 매니페스트에 선언만 한 `SyncReceiver`도 `who=prober`로 브로드캐스트를 받았다.

exported="false"인 `InternalActivity`를 직접 띄운 줄은 `SecurityException`이었고 위 로그 첫 줄이 그 거부(`not exported from uid 10179`)다. [activity 요소 문서](https://developer.android.com/guide/topics/manifest/activity-element)는 이 경우 `ActivityNotFoundException`이 난다고 쓰지만 Android 13에서 돌아온 건 [`ActivityTaskSupervisor.java` 1101~1113행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#1101)이 던지는 `SecurityException`이었다. `ActivityNotFoundException`은 꺼져 있는 `DisabledActivity`에서만 나왔다.

InsecureShop을 띄울 때 `su shell`을 붙인 이유를 자작 앱으로 확인했다. `adb root`가 켜진 userdebug 에뮬레이터에서는 `adb shell`이 root UID라 `checkComponentPermission()` 맨 위 분기에서 exported 검사를 건너뛴다.

![adb -s $S shell id -u 결과 0, adb -s $S shell am start -W -n io.seika.surface/.InternalActivity 는 Status: ok 와 Activity: io.seika.surface/.InternalActivity, adb -s $S shell su shell am start -W -n io.seika.surface/.InternalActivity 는 Exception occurred while executing 'start': java.lang.SecurityException: Permission Denial: starting Intent { flg=0x10000000 cmp=io.seika.surface/.InternalActivity } from null (pid=5218, uid=2000) not exported from uid 10179, adb -s $S shell su shell am start -W -n io.seika.surface/.ShareAlias 는 Status: ok 와 Activity: io.seika.surface/.InternalActivity](/assets/img/android-mastery/p1c06/11-device-am-root-shell.png)

root로 친 `am start`는 `InternalActivity`를 `Status: ok`로 열었다. 같은 명령을 `su shell`로 셸 UID(2000)에서 돌리면 `SecurityException: Permission Denial: … (pid=5218, uid=2000) not exported from uid 10179`로 막힌다. 셸 UID로 띄운 `ShareAlias`는 열렸고 `am start -W`의 `Activity:` 줄에는 대상인 `InternalActivity`가 찍혔다. 컴포넌트별 실제 공격은 [15장](/posts/android-lab-p1c15-activity-intent-injection/)에서 [18장](/posts/android-lab-p1c18-contentprovider-fileprovider/)까지 다룬다.

## debuggable·allowBackup 기본값과 NSC가 정하는 cleartext

앱 전체 플래그도 속성이 비었을 때가 문제다. Android 13 파서가 넣는 기본값은 이렇다.

| 속성 | 비어 있을 때 | 근거 |
|--|--|--|
| `debuggable` | false | [ParsingPackageUtils 2250행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java#2250) |
| `allowBackup` | true | [ParsingPackageUtils 2239행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java#2239) |
| `usesCleartextTraffic` | targetSdk 27 이하에서만 true | [ParsingPackageUtils 2275행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java#2275) |
| NSC의 기본 cleartext | targetSdk 27 이하에서만 허용 | [NetworkSecurityConfig 187행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/NetworkSecurityConfig.java#187) |

debuggable은 기본이 false라서 true로 적혀 있을 때만 FLAG가 된다. 켜져 있으면 셸에서 `run-as`로 앱 UID에 들어갈 수 있고 [`run-as.cpp` 229~231행](https://android.googlesource.com/platform/system/core/+/refs/tags/android-13.0.0_r84/run-as/run-as.cpp#229)은 debuggable이 아닌 패키지에 `package not debuggable`을 내고 끝난다.

allowBackup은 반대로 속성이 없으면 켜진 상태다. 자작 앱 지도의 `allowBackup=true (attribute absent, default true)`가 그 경우로, 매니페스트를 `allowBackup="true"`로 grep하면 놓친다. 기기에 깐 자작 앱(targetSdk 30)을 `dumpsys package`로 보면 두 값이 플래그로 붙어 있다.

![adb -s $S shell dumpsys package io.seika.surface 에서 targetSdk= 줄과 flags= 줄을 grep 으로 거른 결과 versionCode=1 minSdk=26 targetSdk=30 과 flags 목록 DEBUGGABLE HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP, 이어서 adb -s $S shell run-as io.seika.surface id -u 결과 10179](/assets/img/android-mastery/p1c06/20-device-flags-runas.png)

매니페스트에 allowBackup 속성이 없는데도 `ALLOW_BACKUP`이 붙었고 `DEBUGGABLE` 덕에 `run-as io.seika.surface id -u`는 앱 UID인 `10179`를 돌려줬다. debuggable을 빼고 `allowBackup="false"`를 적은 방어 빌드(뒤에서 CI 게이트에 넣는 `2.0-fixed`, targetSdk 33)에서는 flags가 `[ HAS_CODE ALLOW_CLEAR_USER_DATA ]`로 줄었고 `run-as`는 `run-as: package not debuggable: io.seika.surface`로 끝났다.

다만 allowBackup이 adb backup을 정하는 범위는 targetSdk 31부터 줄었다. [`BackupEligibilityRules.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/backup/java/com/android/server/backup/utils/BackupEligibilityRules.java#72)에서 72행 `RESTRICT_ADB_BACKUP`이 켜진 앱(targetSdk 31 이상)이 권한 있는 시스템 앱이 아니면 206행은 allowBackup 대신 debuggable 여부를 돌려준다. 81행 `IGNORE_ALLOW_BACKUP_IN_D2D`가 걸린 targetSdk 31 이상의 비시스템 앱은 기기 간 이전(D2D)에서 allowBackup을 아예 보지 않는다. targetSdk 31 이상 앱이면 매퍼가 allowBackup 줄에 이 사실을 덧붙인다. AndroGoat(targetSdk 33)에서는 이렇게 나왔다.

```text
FLAG     allowBackup=true (explicit; targetSdk>=31: adb backup follows debuggable (true), not this flag)
```

adb backup은 [13장](/posts/android-lab-p1c13-storage-log-clipboard-backup/)에서 다룬다.

cleartext는 플래그 하나만 봐서는 판정이 안 된다. `android:networkSecurityConfig`가 있으면 [`ManifestConfigSource.java` 60~69행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/ManifestConfigSource.java#60)이 NSC XML(`XmlConfigSource`)로 정책을 만들고 `usesCleartextTraffic` 값은 NSC가 없을 때만 읽는다(Android 7.0 이상에서는 NSC가 있으면 이 플래그를 무시한다, [application 요소 문서](https://developer.android.com/guide/topics/manifest/application-element)). 자작 앱은 `usesCleartextTraffic="false"`를 달아 놓고 NSC에서 에뮬레이터의 호스트 주소를 열어 두었다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false"/>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">10.0.2.2</domain>
    </domain-config>
</network-security-config>
```

매퍼는 이 XML을 읽어서 `cleartext via @xml/nsc: base-config false, allowed for 10.0.2.2 (usesCleartextTraffic=false is ignored)`를 찍었다. 기기에서 맞춰 보려고 자작 앱의 `MainActivity`가 `net` extra를 받으면 `HttpURLConnection`으로 `http://10.0.2.2:8086/`과 `http://127.0.0.1:8086/`에 GET을 보내게 해 두었다. `adb -s $S uninstall io.seika.prober`, `adb -s $S uninstall io.seika.surface`로 자작 앱과 프로브를 지우고 취약 빌드만 새로 깐 다음 호스트에 Python `http.server`를 띄웠다. 에뮬레이터 안에서 `10.0.2.2`는 호스트의 루프백으로 이어진다.

![adb -s $S install out/surface-t30.apk 는 Success, grep 으로 본 vuln.xml 의 android:usesCleartextTraffic="false" 와 android:networkSecurityConfig="@xml/nsc", nsc.xml 의 base-config cleartextTrafficPermitted="false", domain-config cleartextTrafficPermitted="true", domain includeSubdomains="false" 10.0.2.2. python -m http.server 8086 --bind 127.0.0.1 --directory raw/www 를 백그라운드로 띄우고 adb -s $S shell am start -n io.seika.surface/.MainActivity --ez net true, sleep 6 뒤 logcat 의 I/SURFACE : GET http://10.0.2.2:8086/ -> HTTP 200 과 I/SURFACE : GET http://127.0.0.1:8086/ -> IOException: Cleartext HTTP traffic to 127.0.0.1 not permitted, 서버 로그 127.0.0.1 - - "GET / HTTP/1.1" 200](/assets/img/android-mastery/p1c06/17-device-cleartext.png)

`10.0.2.2`로 간 요청은 `HTTP 200`을 받았고 호스트 서버 로그에도 GET 한 줄이 남았다. `127.0.0.1`로 가는 요청은 `IOException: Cleartext HTTP traffic to 127.0.0.1 not permitted`로 끝났다. 매니페스트에는 `usesCleartextTraffic="false"`가 적혀 있었지만 NSC가 연 주소로는 평문이 나갔다. 교육용 앱 두 개에서도 NSC가 결과를 바꿨다. AndroGoat는 `base-config`에 `cleartextTrafficPermitted="true"`를 둬서 모든 호스트가 열렸고 Allsafe(targetSdk 35)는 `base-config`가 없어 targetSdk 기본값(false)을 따르되 도메인 하나를 열어 둔다.

```text
FLAG     cleartext via @xml/network_security_config: base-config true, allowed for every host
FLAG     cleartext via @xml/network_security_config: base-config false (no base-config: targetSdk default), allowed for infosecadventures.io +subdomains
```

첫 줄이 AndroGoat, 둘째 줄이 Allsafe의 결과다. NSC 문법과 피닝은 [12장](/posts/android-lab-p1c12-network-security-config/)과 [Atlas C46](/posts/android-concept-atlas-c46-tls-nsc-pinning/)에서 이어진다.

## 한 intent-filter 안의 data는 서로 곱해진다

자작 앱의 `LinkActivity` 필터로 받으려던 링크는 `seika://cb`와 `https://app.seika.test/open...`였다. 그런데 [data 요소 문서](https://developer.android.com/guide/topics/manifest/data-element)는 한 `<intent-filter>` 안의 `<data>`가 전부 같은 필터에 기여한다고 적고 scheme 둘과 host 둘, path 하나를 각각 따로 적은 필터와 같다는 예까지 든다.

![developer.android.com data 요소 문서의 description 부분. URI 형식 scheme://host:port 뒤에 path, pathPrefix, pathPattern, pathAdvancedPattern, pathSuffix 중 하나, All the <data> elements contained within the same <intent-filter> element contribute to the same filter 문장, scheme="something" host="project1.example.com" 과 scheme="something-else" host="project2.example.com" path 를 적은 data 두 줄짜리 필터가 scheme 둘, host 둘, path="/page1" 을 따로 적은 data 다섯 줄 필터와 같다는 예시](/assets/img/android-mastery/p1c06/15-doc-data-element.png)

매칭 코드도 그렇게 생겼다.

![android-13.0.0_r84 IntentFilter.java 1599~1653행. 1604행 private int matchData(String type, String scheme, Uri data, boolean wildcardSupported) 선언, 1607행 schemes = mDataSchemes, 1616~1622행 schemes.contains(scheme) 이면 MATCH_CATEGORY_SCHEME 아니면 return NO_MATCH_DATA, 1631행 authorities = mDataAuthorities 와 1633행 matchDataAuthority, 1635행 paths = mDataPaths, 1636~1641행 paths == null 이면 match = authMatch, hasDataPath 이면 MATCH_CATEGORY_PATH, 아니면 return NO_MATCH_DATA 인 코드](/assets/img/android-mastery/p1c06/14-src-intentfilter-matchdata.png)

[`IntentFilter.matchData()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/IntentFilter.java#1604)에서 필터는 scheme, authority, path를 각각 평평한 목록(`mDataSchemes`, `mDataAuthorities`, `mDataPaths`)으로 갖는다. URI의 scheme이 scheme 목록에 있으면 authority를 보고(1616~1633행), 필터에 path가 하나라도 있으면 URI의 path가 그 목록과 맞아야 하며 아니면 `NO_MATCH_DATA`다(1635~1641행). 값이 어느 `<data>`에서 왔는지는 어디서도 따지지 않는다.

매퍼도 `<data>`마다 줄을 나누지 않고 scheme, host, path를 곱해서 찍는다.

```python
# map_surface.py 180~196행
        for f in filters:
            ds = f.findall('data')
            schemes = [at(x, 'scheme') for x in ds if at(x, 'scheme')]
            if not schemes:
                continue
            hosts = [at(x, 'host') + (':' + at(x, 'port') if at(x, 'port') else '')
                     for x in ds if at(x, 'host')] or ['*']
            paths = []
            for x in ds:
                for k, fmt in (('path', '%s'), ('pathPrefix', '%s*'), ('pathPattern', 'pattern:%s'),
                               ('pathAdvancedPattern', 'advanced:%s'), ('pathSuffix', '*%s')):
                    if at(x, k):
                        paths.append(fmt % at(x, k))
            cats = [at(c, 'name').rsplit('.', 1)[-1] for c in f.findall('category')]
            uris = ['%s://%s%s' % (s, h, p) for s in dict.fromkeys(schemes)
                    for h in dict.fromkeys(hosts) for p in (paths or [''])]
            links.append((short(name), at(f, 'autoVerify') == 'true', 'BROWSABLE' in cats, uris))
```

자작 앱 지도의 LINK 줄이 그 결과다. scheme 둘과 host 둘이 서로 섞여 `seika://app.seika.test/open*`과 `https://cb/open*`이 생겼고 `seika://cb`는 `/open*`이 붙은 꼴로만 나온다.

이건 매퍼가 소스를 읽고 내린 해석이라, 먼저 실제 매칭 코드에 같은 URI를 넣어 봤다. Android Studio에 들어 있는 `layoutlib.jar`는 레이아웃 미리보기용으로 Android 프레임워크를 호스트 JVM에서 돌게 빌드한 것이고 안에 진짜 `android.content.IntentFilter`, `android.net.Uri`, `android.os.PatternMatcher`가 있다. 매니페스트를 JDK의 DOM 파서로 읽어 `<data>` 속성을 필터에 넣고 `IntentFilter.match()`를 부르는 작은 하네스 `IfMatch.java`를 썼다. 속성을 넣는 방식은 [`ParsedIntentInfoUtils.parseData()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedIntentInfoUtils.java#166)를 따랐다(scheme은 190행 `addDataScheme`, host와 port는 242행 `addDataAuthority`, path·pathPrefix·pathPattern은 248·254·264행 `addDataPath`).

```java
// IfMatch.java 38~47행 (필터 만들기)
                    switch (c.getLocalName()) {
                        case "action": flt.addAction(a(c, "name")); break;
                        case "category": flt.addCategory(a(c, "name")); break;
                        case "data":
                            if (a(c, "scheme") != null) flt.addDataScheme(a(c, "scheme"));
                            if (a(c, "host") != null) flt.addDataAuthority(a(c, "host"), a(c, "port"));
                            if (a(c, "path") != null) flt.addDataPath(a(c, "path"), PatternMatcher.PATTERN_LITERAL);
                            if (a(c, "pathPrefix") != null) flt.addDataPath(a(c, "pathPrefix"), PatternMatcher.PATTERN_PREFIX);
                            if (a(c, "pathPattern") != null) flt.addDataPath(a(c, "pathPattern"), PatternMatcher.PATTERN_SIMPLE_GLOB);
                            break;
// IfMatch.java 59~66행 (매칭은 프레임워크 코드)
        for (int i = 2; i < args.length; i++) {
            Uri u = Uri.parse(args[i]);
            String hit = "NO MATCH";
            for (int j = 0; j < filters.size(); j++) {
                int r = filters.get(j).match("android.intent.action.VIEW", null, u.getScheme(), u, cats, null);
                if (r >= 0) { hit = "match filter#" + j + "  " + name(r); break; }
                hit = "NO MATCH  " + name(r);
            }
```

필터를 만드는 부분은 파서의 속성 매핑을 옮겨 적은 것이고 매칭은 프레임워크 코드 그대로다. layoutlib의 `build.prop`은 Android 16(API 36), 빌드 ID `BLR4.251003.038`이라 r84와 버전이 다르다.

그래서 [`android-16.0.0_r1`의 `IntentFilter.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/content/IntentFilter.java)를 받아 `matchData()`를 r84와 diff로 비교했다. 다른 곳은 API 35에서 들어온 `UriRelativeFilterGroup` 분기뿐이었다. 16.0.0_r1은 이 jar보다 앞선 태그라 jar 안의 클래스도 `javap -c -p`로 풀어 봤고 `matchData()`가 `mUriRelativeFilterGroups`를 읽고 `Flags.relativeReferenceIntentFilters()`로 갈라지는 16.0.0_r1 소스와 같은 모양이었다. 필터에 그 그룹이 없으면 두 분기 모두 r84와 같은 식(path 목록이 없으면 authority 결과, path가 맞으면 `MATCH_CATEGORY_PATH`, 아니면 `NO_MATCH_DATA`)으로 줄어들고 자작 앱 필터에는 그룹이 없다.

```bash
LL="C:/Program Files/Android/Android Studio/plugins/design-tools/lib/layoutlib.jar"
KX="C:/Program Files/Android/Android Studio/plugins/android/lib/kxml2-2.3.0.jar"
javac -cp "$LL" -d ifmatch ifmatch/IfMatch.java
java -cp "$LL;$KX;ifmatch" IfMatch apps/surface/manifests/vuln.xml .LinkActivity \
  seika://cb seika://cb/open https://cb/open/x seika://app.seika.test/open https://app.seika.test/open
java -cp "$LL;$KX;ifmatch" IfMatch apps/surface/manifests/fixed.xml .LinkActivity \
  seika://cb seika://cb/open https://cb/open/x https://app.seika.test/open
```

처음에는 `java.lang.NoClassDefFoundError: org/xmlpull/v1/XmlPullParserException`으로 죽었다. layoutlib에 xmlpull 클래스가 없어서 같은 Android Studio에 있는 `kxml2-2.3.0.jar`를 클래스패스에 더했다(`KX`). Windows의 `java`라서 클래스패스 구분자는 `;`다.

![호스트 터미널. layoutlib build.prop 의 ro.build.version.sdk=36, ro.build.version.release=16, javac -cp "$LL" -d ifmatch ifmatch/IfMatch.java, java IfMatch apps/surface/manifests/vuln.xml .LinkActivity 결과 filter#0 의 schemes 가 seika, https 이고 hosts 가 cb, app.seika.test, paths 가 PatternMatcher{PREFIX: /open} 하나, seika://cb 는 NO MATCH NO_MATCH_DATA (-2), seika://cb/open, https://cb/open/x, seika://app.seika.test/open, https://app.seika.test/open 은 match filter#0 MATCH_CATEGORY_PATH (0x508000). fixed.xml 에서는 filter#0 이 schemes https, hosts app.seika.test, paths PatternMatcher{PREFIX: /open} 이고 filter#1 은 schemes seika, hosts cb, paths 빈 목록, seika://cb 와 seika://cb/open 은 match filter#1 MATCH_CATEGORY_HOST (0x308000), https://cb/open/x 는 NO MATCH NO_MATCH_DATA (-2), https://app.seika.test/open 은 match filter#0 MATCH_CATEGORY_PATH](/assets/img/android-mastery/p1c06/16-host-intentfilter-match.png)

취약 빌드의 필터는 `schemes=[seika, https] hosts=[cb, app.seika.test] paths=[PatternMatcher{PREFIX: /open}]`로 들어갔다. `<data>` 두 줄이 목록 세 개로 녹은 모양이다. 의도했던 `seika://cb`는 path가 없어 `NO_MATCH_DATA (-2)`로 떨어졌고 아무도 선언하지 않은 `https://cb/open/x`와 `seika://app.seika.test/open`은 `MATCH_CATEGORY_PATH`로 맞았다. 결과 값 `0x508000`은 `MATCH_CATEGORY_PATH`(0x500000)에 `MATCH_ADJUSTMENT_NORMAL`(0x8000)을 더한 값이다([IntentFilter.java 217행과 241행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/IntentFilter.java#217)).

호스트에서 돌린 건 액티비티 하나의 필터다. 기기의 resolver는 설치된 모든 앱의 필터를 함께 본다. 그래서 같은 URI를 에뮬레이터의 `cmd package query-activities`에도 물었다.

![adb -s $S shell cmd package query-activities --components -a android.intent.action.VIEW -c android.intent.category.BROWSABLE 를 네 URI 로 돌린 결과. -d seika://cb 는 No activities found, -d seika://cb/open 은 io.seika.surface/.LinkActivity, -d https://cb/open/x 는 io.seika.surface/.LinkActivity 와 com.android.chrome/com.google.android.apps.chrome.IntentDispatcher, -d seika://app.seika.test/open 은 io.seika.surface/.LinkActivity](/assets/img/android-mastery/p1c06/19-device-query-activities.png)

`seika://cb`는 `No activities found`였고 `seika://cb/open`과 `seika://app.seika.test/open`은 `LinkActivity`로 갔다. `https://cb/open/x`에는 `LinkActivity`와 함께 Chrome의 `IntentDispatcher`가 나왔다. 이 질의에는 플래그를 주지 않았다. 링크를 눌렀을 때 `startActivity()`가 쓰는 `MATCH_DEFAULT_ONLY`(0x10000)를 붙이면 달라지는지 보려고, 의도한 `https://app.seika.test/open/x`를 함께 넣어 두 링크를 플래그 0과 0x10000으로 각각 물었다. 플래그 0에서는 `https://app.seika.test/open/x`도 `io.seika.surface/.LinkActivity`와 Chrome의 `IntentDispatcher`를 함께 돌려줬다. 아래는 0x10000을 붙인 결과다.

![취약 빌드 versionName=1.0-vuln 상태에서 for 루프로 query-activities --components --query-flags 0x10000 -a android.intent.action.VIEW -c android.intent.category.BROWSABLE 를 돌린 결과. https://cb/open/x 는 io.seika.surface/.LinkActivity 와 com.android.chrome/com.google.android.apps.chrome.IntentDispatcher, https://app.seika.test/open/x 는 com.android.chrome/com.google.android.apps.chrome.IntentDispatcher 하나](/assets/img/android-mastery/p1c06/23-device-default-only.png)

0x10000을 붙이자 결과가 거꾸로 갈렸다. 플래그 0에서는 `LinkActivity`도 받던 의도한 `https://app.seika.test/open/x`에 Chrome만 남았고 의도하지 않은 `https://cb/open/x`에는 여전히 `LinkActivity`가 나왔다.

웹 링크를 앱 승인 여부로 거르는 단계는 [`DomainVerificationUtils.isDomainVerificationIntent()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationUtils.java#51)가 true일 때만 돈다. host가 도메인 이름 패턴(`Patterns.DOMAIN_NAME`)에 맞아야 하고(57~64행), 카테고리가 BROWSABLE 하나면 `MATCH_DEFAULT_ONLY`가 있어야 한다(83~85행). `app.seika.test`는 이 조건을 채워 [`ComputerEngine.java` 1067~1085행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/ComputerEngine.java#1067)에서 승인된 앱만 남기는데, 취약 빌드는 이 도메인에 승인되지 않아 브라우저만 남았다. 점이 없는 `cb`는 도메인 이름이 아니라서 이 단계를 아예 거치지 않는다.

필터를 둘로 나눈 방어 빌드를 호스트 하네스에 넣으면 `seika://cb`가 둘째 필터에 `MATCH_CATEGORY_HOST`로 맞고 `https://cb/open/x`는 어느 필터에도 맞지 않는다. 예상하지 못한 줄이 하나 있었다. `seika://cb/open`도 둘째 필터에 맞았다. path를 하나도 적지 않은 필터는 `mDataPaths`가 null이라 1636행에서 authority 결과를 그대로 쓴다. 방어 빌드의 seika 필터가 바로 그런 모양이라 `seika://cb` 아래의 어떤 경로든 `LinkActivity`로 온다. 경로를 좁히려면 이 필터에도 path를 적어야 한다. 방어 빌드에서는 거기까지 손대지 않았다. 기기에서 `adb -s $S uninstall io.seika.surface`로 취약 빌드를 지우고 방어 빌드를 새로 깐 뒤 같은 질문을 해도 같았다.

![취약 빌드(versionCode=1 targetSdk=30 versionName=1.0-vuln)에서 adb -s $S shell pm get-app-links io.seika.surface 는 출력 없음, pm get-app-links --user 0 은 Selection state: Disabled: app.seika.test. 화면에 찍히지 않은 adb -s $S uninstall io.seika.surface 뒤 adb -s $S install out/surface-fixed.apk Success, sleep 15 뒤 pm get-app-links 는 Domain verification state: app.seika.test: 1024. for 루프 query-activities 결과 seika://cb 와 seika://cb/open 은 io.seika.surface/.LinkActivity, https://cb/open/x 는 com.android.chrome/com.google.android.apps.chrome.IntentDispatcher 하나](/assets/img/android-mastery/p1c06/18-device-applinks.png)

`seika://cb`와 `seika://cb/open`은 `LinkActivity`로, `https://cb/open/x`는 Chrome 하나로 갔다. 같은 화면 위쪽은 App Links 검증 상태다. 두 빌드 모두 https 링크를 받는 필터에 `autoVerify="true"`를 달았지만 취약 빌드에서는 `pm get-app-links`가 아무것도 찍지 않았다.

도메인 수집 규칙을 바꾸는 [`RESTRICT_DOMAINS`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationCollector.java#91)가 targetSdk 31부터 켜지는 호환성 변경이라, targetSdk 30 앱의 검증 대상은 [`DomainVerificationCollector.collectDomainsLegacy()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationCollector.java#165)가 고른다. 이 함수는 필터 하나라도 [`needsVerification()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/IntentFilter.java#684)을 통과해야 도메인을 모은다. `needsVerification()`은 autoVerify이면서 scheme이 전부 http나 https인 필터에만 true라서, seika가 섞인 필터는 검증 대상에 오르지도 못했다. 사용자 선택 상태(`--user 0`)에는 `app.seika.test`만 있고 점이 없는 `cb`는 같은 클래스의 [`isValidHost()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationCollector.java#309)에서 빠졌다.

https 필터를 따로 뗀 방어 빌드에서는 `app.seika.test: 1024`가 나왔다. 방어 빌드는 targetSdk 33이라 레거시 경로 대신 [`collectDomainsInternal()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationCollector.java#236)을 거치고 여기서는 253~260행이 필터마다 autoVerify와 DEFAULT 카테고리를 보고 `handlesWebUris(true)`로 scheme이 전부 웹 scheme인지 따진다. 소스대로라면 seika와 https를 한 필터에 섞은 매니페스트는 targetSdk 33에서도 그 필터를 건너뛴다. 1024는 [`DomainVerificationState`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/verify/domain/DomainVerificationState.java#97)의 `STATE_FIRST_VERIFIER_DEFINED`로 검증기가 정의해 쓰는 값이고 성공을 뜻하는 `verified`(1)는 아니다. `.test` 도메인에는 `assetlinks.json`을 올릴 수 없어서 검증이 성공한 앱으로 링크가 바로 가는 경로는 여기서 재 보지 못했다.

Allsafe의 `DeepLinkTask`는 다른 모양의 함정이다. `allsafe://infosecadventures/congrats*`(pathPrefix) 필터와 별도로 host 없이 `<data android:scheme="https"/>`만 둔 BROWSABLE 필터가 있어서 매퍼가 `https://*`를 찍었다. host가 없는 필터는 authority를 보지 않으니([matchData 1632행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/IntentFilter.java#1632)) 필터 하나만 놓고 보면 scheme만 https면 어떤 링크든 맞는다. 에뮬레이터에 깔린 Allsafe로 확인해 보니 resolver는 다르게 다뤘다.

![for 루프로 query-activities --components --query-flags 를 0, 0x10000, 0x20000 으로 바꿔 -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d https://example.com/any/path 를 돌린 결과. 0 과 0x10000 은 com.android.chrome/com.google.android.apps.chrome.IntentDispatcher 하나, 0x20000 에서만 Chrome 과 infosecadventures.allsafe/.challenges.DeepLinkTask](/assets/img/android-mastery/p1c06/22-device-allsafe-https.png)

`https://example.com/any/path`에는 플래그 0과 `MATCH_DEFAULT_ONLY`에서 Chrome만 나왔고 `DeepLinkTask`는 `MATCH_ALL`(0x20000)을 줬을 때만 목록에 올라왔다. authority 없이 웹 scheme만 받는 필터는 [`handleAllWebDataURI()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/IntentFilter.java#613)가 true라 브라우저 후보로 분류되고 `ComputerEngine`은 `MATCH_ALL`이 없으면 그 후보들 중 기본 브라우저 하나만 넣는다([1056~1061행과 1105~1140행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/ComputerEngine.java#1056)). `MATCH_ALL` 없이 Chrome만 남은 것으로 보아 이 에뮬레이터의 기본 브라우저는 Chrome이다(브라우저 역할 보유자를 따로 조회하지는 않았다).

기본 브라우저의 매치가 없으면 브라우저 후보를 전부 넣으니(1140행), 매퍼는 이 줄을 지우지 않는다. 딥링크 공격면은 [Atlas C47](/posts/android-concept-atlas-c47-webview-deeplink-ipc-attack-surface/)에서 더 다루고, `grantUriPermissions`로 넘기는 URI 권한은 [Atlas C11](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)에 있다.

## 방어 빌드와 CI 게이트

방어 빌드(`2.0-fixed`, targetSdk 33)는 매니페스트를 이렇게 바꿨다. targetSdk 33이라 NSC를 빼면 cleartext는 기본으로 꺼진다.

```text
$ diff apps/surface/manifests/vuln.xml apps/surface/manifests/fixed.xml
4c4
<     android:versionCode="1" android:versionName="1.0-vuln">
---
>     android:versionCode="2" android:versionName="2.0-fixed">
6,7c6,7
<     <!-- no protectionLevel: the default is "normal" -->
<     <permission android:name="io.seika.surface.permission.ADMIN"/>
---
>     <permission android:name="io.seika.surface.permission.ADMIN"
>         android:protectionLevel="signature"/>
13,15c13
<         android:debuggable="true"
<         android:usesCleartextTraffic="false"
<         android:networkSecurityConfig="@xml/nsc">
---
>         android:allowBackup="false">
17c15
<         <activity android:name=".MainActivity">
---
>         <activity android:name=".MainActivity" android:exported="true">
24,25c22
<         <activity android:name=".DebugActivity" android:exported="true"/>
< 
---
>         <activity android:name=".DebugActivity" android:exported="false"/>
28,41c25
<         <activity-alias android:name=".ShareAlias"
<             android:targetActivity=".InternalActivity"
<             android:exported="true">
<             <intent-filter>
<                 <action android:name="android.intent.action.SEND"/>
<                 <category android:name="android.intent.category.DEFAULT"/>
<                 <data android:mimeType="text/plain"/>
<             </intent-filter>
<         </activity-alias>
< 
<         <activity android:name=".DisabledActivity"
<             android:exported="true" android:enabled="false"/>
< 
<         <activity android:name=".LinkActivity">
---
>         <activity android:name=".LinkActivity" android:exported="true">
46d29
<                 <data android:scheme="seika" android:host="cb"/>
49a33,38
>             <intent-filter>
>                 <action android:name="android.intent.action.VIEW"/>
>                 <category android:name="android.intent.category.DEFAULT"/>
>                 <category android:name="android.intent.category.BROWSABLE"/>
>                 <data android:scheme="seika" android:host="cb"/>
>             </intent-filter>
52c41
<         <receiver android:name=".SyncReceiver">
---
>         <receiver android:name=".SyncReceiver" android:exported="false">
66c55
<             android:readPermission="io.seika.surface.permission.VAULT"/>
---
>             android:permission="io.seika.surface.permission.VAULT"/>
```

`map_surface.py`에 `--fail`을 주면 의도적으로 열어 둔 `--allow` 목록 밖에서 OPEN이나 CHECK가 나오거나 앱 플래그가 위험할 때 종료 코드 1을 낸다. 런처와 딥링크 액티비티만 허용하고 두 빌드에 돌렸다.

```bash
apktool d -q -f -s -p fw -o decoded/surface-fixed out/surface-fixed.apk
python map_surface.py decoded/surface-fixed --platform aosp13-core-AndroidManifest.xml --fail --allow .MainActivity --allow .LinkActivity; echo "exit=$?"
python map_surface.py decoded/surface-t30 --platform aosp13-core-AndroidManifest.xml --fail --allow .MainActivity --allow .LinkActivity | tail -1; echo "exit=${PIPESTATUS[0]}"
```

![방어 빌드 decoded/surface-fixed(targetSdk 33)에 map_surface.py --fail --allow .MainActivity --allow .LinkActivity 를 돌린 결과. OPEN 은 MainActivity 와 LinkActivity 뿐, DebugActivity, InternalActivity, SyncReceiver, FilesProvider 는 INTERNAL, AdminService(ADMIN signature), VaultService, NotesProvider(read/write: VAULT signature)는 GUARDED, ok debuggable=false, ok allowBackup=false, ok cleartext off (default for targetSdk 33), LINK https://app.seika.test/open* autoVerify=true 와 LINK seika://cb autoVerify=false, PASS, exit=0. 이어서 취약 빌드 surface-t30 에 같은 명령을 돌리면 FAIL: .DebugActivity, .ShareAlias, .SyncReceiver, .AdminService, .NotesProvider, debuggable, allowBackup, cleartext 와 exit=1](/assets/img/android-mastery/p1c06/07-ci-fixed.png)

방어 빌드는 `PASS`, `exit=0`이고 취약 빌드는 `FAIL` 뒤에 걸린 컴포넌트와 플래그를 늘어놓고 `exit=1`로 끝난다. 릴리스 APK를 디코드해 이 명령을 파이프라인에 넣어 두면 허용 목록 밖에서 OPEN이나 CHECK 컴포넌트가 나오거나 debuggable, allowBackup, cleartext 중 하나가 켜져 있을 때 빌드가 멈춘다. exported를 빠뜨린 쪽은 targetSdk 31 이상이면 앞에서 본 AGP 8.5.2의 병합 단계나 기기의 설치 단계가 먼저 잡는다. 딥링크가 필터별로 나뉘어 `seika://cb` 줄이 따로 생긴 것도 지도에서 보인다.

기기에서 두 앱을 지우고 게이트를 통과한 방어 빌드와 프로브를 새로 깐 뒤 프로브를 다시 돌렸다.

![방어 빌드에 다시 돌린 Prober 앱 화면. target io.seika.surface (other signer), activity .MainActivity started, .DebugActivity SecurityException, .InternalActivity SecurityException, .ShareAlias ActivityNotFoundException, .DisabledActivity ActivityNotFoundException, receiver .SyncReceiver sent, service .AdminService SecurityException, .VaultService SecurityException, provider notes query SecurityException, notes insert SecurityException, files query SecurityException](/assets/img/android-mastery/p1c06/13-device-prober-fixed.png)

런처인 `MainActivity`만 열렸다. 지운 `ShareAlias`와 `DisabledActivity`는 `ActivityNotFoundException`이고 나머지 액티비티와 서비스, provider는 `SecurityException`이다. signature로 올린 ADMIN은 프로브에 `granted=false`로 남아 `AdminService` 바인드도 막혔다. `android:permission`으로 바꾼 `NotesProvider`는 insert까지 `Permission Denial: opening provider io.seika.surface.NotesProvider … requires io.seika.surface.permission.VAULT or io.seika.surface.permission.VAULT`로 거부됐다. 화면의 `receiver .SyncReceiver sent`는 프로브가 보내기만 했다는 뜻이다. 시스템 로그에는 `Permission Denial: broadcasting Intent { act=io.seika.surface.SYNC … } … is not exported from uid 10181`이 남았고 자작 앱 쪽 수신 로그는 없었다.

게이트가 보지 못하는 곳도 있다. 허용 목록에 남긴 두 액티비티가 받은 인텐트를 안전하게 다루는지는 매니페스트에 드러나지 않고 그 검증은 [15장](/posts/android-lab-p1c15-activity-intent-injection/)에서 한다. 코드에서 `registerReceiver()`로 등록하는 리시버도 매니페스트에 없다. Android 13에서 `RECEIVER_EXPORTED`와 `RECEIVER_NOT_EXPORTED` 플래그가 생겼고 [Android 14 동작 변경](https://developer.android.com/about/versions/14/behavior-changes-14#runtime-receivers-exported)부터는 targetSdk 34 이상 앱이 시스템 브로드캐스트 전용이 아닌 컨텍스트 등록 리시버에 둘 중 하나를 꼭 넘겨야 하니, 이런 리시버는 jadx([4장](/posts/android-lab-p1c04-jadx-static-analysis/))로 `registerReceiver` 호출을 찾아 넘긴 플래그를 봐야 안다.

*다음 글: [APK 재서명과 zipalign](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)*
