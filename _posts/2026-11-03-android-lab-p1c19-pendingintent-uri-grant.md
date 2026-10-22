---
layout: post
title: "PendingIntent와 URI grant — 피해자 이름으로 발급된 읽기 권한"
date: 2026-11-03 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, PendingIntent, URIGrant, FLAG_IMMUTABLE, ConfusedDeputy, ContentProvider, Android16]
excerpt: "무권한 앱이 mutable 암시적 PendingIntent에 data와 FLAG_GRANT_READ_URI_PERMISSION을 채워 보내자 피해자의 비공개 provider 읽기 grant가 공격자 UID 앞으로 기록됐고, Android 16에서도 targetSdk 33 피해자는 경고만 남긴 채 같은 결과가 났다. 받은 URI를 대신 읽어 주는 공유 대상은 고치다가 정상 공유까지 막았고, provider 소유 UID를 허용하는 줄을 더해 호출자 자신의 URI만은 다시 통과시켰다."
---

[앞 글](/posts/android-lab-p1c18-contentprovider-fileprovider/)에서는 provider를 export해 둔 탓에 생기는 유출을 봤다. provider를 export하지 않아도 `android:grantUriPermissions`를 켜 두면 주인이 URI 하나씩 남에게 읽기 권한을 내줄 수 있다. 그런데 그 grant는 누구 이름으로 나가는가. PendingIntent는 만든 앱의 신원으로 실행되는 토큰이고, URI grant는 Intent를 보내는 쪽의 신원으로 발급된다. 둘이 만나면 공격자가 피해자의 이름으로 피해자의 파일 읽기 권한을 자기에게 발급하게 할 수 있다. 반대 방향도 있다. 피해자가 공격자가 건넨 URI를 제 권한으로 열어 주면 피해자가 대리인 노릇을 한다(confused deputy).

선수 개념은 [Activity·Intent 주입(15장)](/posts/android-lab-p1c15-activity-intent-injection/), [패키지 가시성과 URI 권한(Atlas C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/), [컴포넌트와 Binder(Atlas C21)](/posts/android-concept-atlas-c21-components-binder/)다.

## 실습에 쓴 두 앱

피해자 `io.seika.pilab`과 공격자 `io.seika.piatk`를 직접 만들었다. 피해자는 비공개 provider 두 개를 가진다. `SecretProvider`는 export하지 않지만 `grantUriPermissions="true"`이고, `NoGrantProvider`는 grant도 허용하지 않는다. 내부용 `DoneActivity`는 export하지 않은 채 `io.seika.pilab.action.DONE` 필터만 걸려 있다.

```xml
<!-- apps/victim/AndroidManifest.xml 발췌 -->
<activity android:name=".DoneActivity" android:exported="false">
    <intent-filter>
        <action android:name="io.seika.pilab.action.DONE" />
        <category android:name="android.intent.category.DEFAULT" />
    </intent-filter>
</activity>
<activity android:name=".ImportActivity" android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.SEND" />
        <category android:name="android.intent.category.DEFAULT" />
        <data android:mimeType="text/plain" />
    </intent-filter>
</activity>
<activity android:name=".SafeImportActivity" android:exported="true" />
<provider android:name=".SecretProvider" android:authorities="io.seika.pilab.secret"
    android:exported="false" android:grantUriPermissions="true" />
<provider android:name=".NoGrantProvider" android:authorities="io.seika.pilab.nogrant"
    android:exported="false" />
```

공격자 앱은 권한을 하나도 요청하지 않는다. 피해자가 던지는 암시적 `HELP` Intent에 응답하는 `HelperActivity`, 피해자의 `DONE`과 같은 액션을 받는 `LeakActivity`, 실험 모드를 고르는 `AttackActivity`, 그리고 정상 공유를 시험할 때 쓰는 비공개 `FilesProvider`(authority `io.seika.piatk.files`, `grantUriPermissions="true"`)가 전부다. 두 APK는 Gradle 없이 javac, d8, aapt, apksigner를 묶은 실습용 스크립트 `mkapk`로 빌드했고, 피해자는 디버그 키, 공격자는 다른 키로 서명했다.

```bash
mkapk apps/victim out/pilab.apk --key debug --min 26 --target 33
mkapk apps/victim out/pilab-t34.apk --key debug --min 26 --target 34
mkapk apps/attacker out/piatk.apk --key attacker --min 26 --target 33
```

실험은 대부분 Android 13 에뮬레이터(API 33, 빌드 `TE1A.240213.009`, 보안 패치 2024-03-01, userdebug, SELinux Enforcing)에서 돌렸고, `adb unroot`로 셸을 uid 2000으로 내려 두었다. 버전 비교는 Android 16 에뮬레이터(API 36, `BE2A.250530.026.F3`)에서 했는데, 이쪽은 셸을 root로 둔 채 돌렸다(앱 간 grant와 BAL 판정은 셸 UID와 무관한 `am start` 경로다). 캡처에 나오는 `$S`는 `export S=emulator-5600`처럼 에뮬레이터 시리얼을 담은 변수다.

## 플래그 없이 만들면 생성부터 실패한다

먼저 `FLAG_IMMUTABLE`도 `FLAG_MUTABLE`도 주지 않고 `PendingIntent.getActivity`를 불렀다. 설치한 두 앱의 UID는 pilab 10179, piatk 10180이었다.

![두 APK 설치 Success, pm list packages -U 결과 io.seika.pilab uid:10179와 io.seika.piatk uid:10180, EmitActivity mode noflag 실행하고 sleep 5 뒤 logcat -s PILAB:I에 I/PILAB Emit flags=0x0 targetSdk=33 줄과 IllegalArgumentException "Targeting S+ (version 31 and above) requires that one of FLAG_IMMUTABLE or FLAG_MUTABLE be specified"](/assets/img/android-mastery/p1c19/03-device-noflag.png)

예외는 클라이언트 쪽 [`PendingIntent.checkFlags`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/PendingIntent.java#384)에서 던진다. 조건인 [`PENDING_INTENT_EXPLICIT_MUTABILITY_REQUIRED`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/PendingIntent.java#167)는 `@EnabledAfter(targetSdkVersion = R)`라서 targetSdk 31 이상인 앱에만 켜진다. 기준은 기기 버전보다 앱의 targetSdk다. 공식 [PendingIntent 위험 문서](https://developer.android.com/privacy-and-security/risks/pending-intent)는 이 요구를 "Android 11 (API level 30) and higher"로 적고 있는데, 소스와 예외 메시지는 31(S)을 가리킨다.

`logcat -s PILAB:I PILAB:W`처럼 같은 태그를 두 번 주면 뒤의 것이 이겨 `W` 줄만 남는다. 이 실험을 처음 찍었을 때 그래서 `Emit mode=noflag` 줄이 빠졌고, 위 캡처를 포함해 이후 캡처는 전부 `-s PILAB:I`처럼 태그마다 하나만 주고 찍었다(`I`를 주면 `W` 이상도 함께 나온다).

이제 개발자는 둘 중 하나를 꼭 골라야 한다. 아래는 `FLAG_MUTABLE`을 고른 경우다.

## 빈 칸을 채워 피해자 이름으로 보내기

피해자의 `EmitActivity`는 콜백용 PendingIntent를 만들어 암시적 `HELP` Intent에 실어 보낸다. base Intent에는 액션만 있고 컴포넌트도 패키지도 없다.

```java
// apps/victim/src/io/seika/pilab/EmitActivity.java 발췌
Intent base = new Intent(ACTION_DONE);              // io.seika.pilab.action.DONE
...
case "mutable-implicit":   flags = PendingIntent.FLAG_MUTABLE; req = 2; break;
...
pi = PendingIntent.getActivity(this, req, base, flags);
startActivity(new Intent("io.seika.pilab.action.HELP").putExtra("callback", pi));
```

`HELP`에 응답한 공격자의 `HelperActivity`는 PendingIntent를 꺼내 fill-in Intent를 만들고 `send`한다. 패키지를 자기로, data를 피해자 provider의 URI로, 플래그에 읽기 grant를 넣는다. `send`는 0.5초 늦춰서 부른다. `HelperActivity`가 화면 맨 앞에 올라온 뒤에 보내야 백그라운드 Activity 시작으로 잡히지 않기 때문이다.

```java
// apps/attacker/src/io/seika/piatk/HelperActivity.java 발췌
final Intent fill = new Intent()
        .setPackage(getPackageName())
        .setDataAndType(Uri.parse(target), "text/plain")   // content://io.seika.pilab.secret/secret.txt
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
// send once this activity is in front, so the start is not a background launch
new Handler().postDelayed(new Runnable() {
    @Override public void run() {
        try {
            pi.send(HelperActivity.this, 0, fill);
            Log.i(TAG, "Helper sent fill-in " + fill);
        } catch (Exception e) {
            Log.w(TAG, "Helper send failed: " + e);
        }
        finish();
    }
}, 500);
```

공격자 UID 10180에서 돈 `LeakActivity`가 피해자의 비밀 파일 내용 `pilab-secret-7311`을 읽었다. provider 쪽 로그에도 `callingUid=10180 callingPackage=io.seika.piatk`로 찍혀, 읽은 주체는 공격자 자신이다. `dumpsys activity permissions`에는 UID 10180이 `content://io.seika.pilab.secret/secret.txt`에 대한 UriPermission을 들고 있고, 그 출처가 `sourcePkg=io.seika.pilab`로 남아 있다. 아래쪽 UID 10195 항목은 이 AVD에 원래 설치돼 있던 AndroGoat의 다운로드 grant로, 이 실험과는 관계없다.

![mutable-implicit 모드 실행 뒤 logcat: Emit flags=0x2000000 targetSdk=33, Helper sent fill-in flg=0x1 pkg=io.seika.piatk, LeakActivity myUid=10180 flags=0x10000001 referrer=android-app://io.seika.pilab, SecretProvider openFile callingUid=10180, LeakActivity read -> pilab-secret-7311, dumpsys에 UID 10180 holds UriPermission content://io.seika.pilab.secret/secret.txt sourcePkg=io.seika.pilab](/assets/img/android-mastery/p1c19/04-device-hijack.png)

에뮬레이터 화면에도 공격자 앱의 보라색 `LeakActivity`가 떠 있었다. referrer가 `android-app://io.seika.pilab`로 찍힌 것이 이 시작이 피해자 이름으로 이뤄졌다는 흔적이다.

![에뮬레이터 화면, PiAtk LeakActivity 보라색 배경에 myUid=10180 data=content://io.seika.pilab.secret/secret.txt flags=0x10000001 referrer=android-app://io.seika.pilab, 아래에 LeakActivity read -> pilab-secret-7311](/assets/img/android-mastery/p1c19/05-emu-leakactivity.png)

왜 이렇게 되는지는 [`Intent.fillIn`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#10955)에 다 있다. 원래 Intent에서 비어 있는 필드만 채운다. 액션은 비었을 때만, data와 type은 둘 다 비었을 때만([10963행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#10963)), 패키지도 비었을 때만([10983행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#10983)) 들어간다. 컴포넌트는 `FILL_IN_COMPONENT`가 없으면 채워지지 않는다([11009행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#11009)). 반면 플래그는 조건 없이 OR된다([11013행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#11013)). 액션만 있던 base에 공격자의 패키지와 data, `FLAG_GRANT_READ_URI_PERMISSION`(0x1)이 그대로 얹혔고, `LeakActivity`가 받은 플래그 `0x10000001`은 `FLAG_ACTIVITY_NEW_TASK`에 읽기 grant가 붙은 값이다.

이렇게 합쳐진 Intent를 시스템은 PendingIntent를 만든 앱의 UID로 시작한다. [`PendingIntentRecord.sendInner`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/PendingIntentRecord.java#501)가 `startActivityInPackage(uid, …)`를 부를 때 넘기는 `uid`가 생성자의 것이다. URI grant 검사는 "보내는 쪽이 이 URI를 읽을 수 있는가"를 묻는데, 보내는 쪽이 provider 주인인 피해자이니 통과하고, grant는 공격자 UID 앞으로 기록된다.

예상 밖이었던 값이 하나 있다. 설치 직후 첫 실행에서 `HelperActivity`가 찍은 `getCreatorPackage()`는 `null`, `getCreatorUid()`는 -1이었다. 같은 기기에서 바로 다음에 돌린 실험에서는 `io.seika.pilab`/10179가 나왔다. 그래서 하이재크 앞뒤로 `adb shell dumpsys package queries`를 떠 두었다. 설치만 끝난 상태의 덤프에는 `io.seika.piatk`라는 문자열이 아예 없었고, "queryable via interaction" 항목에도 두 앱을 서로 잇는 줄은 없었다(pilab은 시스템 패키지 묶음 아래에만 한 번 나왔다). 하이재크 직후에는 같은 항목에 `io.seika.pilab:` 아래 `io.seika.piatk`, `io.seika.piatk:` 아래 `io.seika.pilab`이 올라와 있었다. 공격자 앱은 targetSdk 33에 `<queries>`가 없으니, 첫 상호작용 전에는 피해자가 보이지 않아 생성자 정보가 걸러졌다가 이 상호작용으로 보이게 된 것으로 보인다. `<queries>`를 넣고 빼는 대조는 하지 않았으니 원인을 확정하지는 못했다. Android 16에서는 재설치와 `pm clear` 뒤 매번 `null`이었고 이유는 따로 보지 않았다. 어쨌든 공격 자체에는 생성자 정보가 필요 없었다.

## fill-in이 멈추는 자리

같은 공격자 코드를 성격이 다른 PendingIntent들에 던져 봤다. 컴포넌트를 지정한 immutable, 컴포넌트를 지정한 mutable, 그리고 암시적 mutable인데 공격자가 grant를 허용하지 않는 `NoGrantProvider`의 URI를 넣은 경우다. 실행은 `pm clear io.seika.piatk`로 공격자 설정을 비우고, 매번 `am start --activity-clear-task`로 시작했다. 처음에는 둘 다 빼먹어서 이전 실험의 Activity가 맨 앞으로 불려 나오기만 하고 새로 시작되지 않거나, 앞서 저장한 URI가 남아 엉뚱한 결과가 나왔다. `pm clear` 직후의 공격자 앱은 콜드 스타트라 3초 안에 끝나지 않아서, 첫 대기를 3초로 두었을 때는 immutable 결과가 다음 실험 로그 사이에 끼어들었다. 첫 대기만 6초로 늘렸다.

```bash
adb -s $S shell pm clear io.seika.piatk
adb -s $S logcat -c
adb -s $S shell am start --activity-clear-task -n io.seika.pilab/.EmitActivity --es mode immutable-explicit
sleep 6
adb -s $S shell am start --activity-clear-task -n io.seika.pilab/.EmitActivity --es mode mutable-explicit
sleep 3
adb -s $S shell am start --activity-clear-task -n io.seika.piatk/.AttackActivity --es mode set-uri --es uri content://io.seika.pilab.nogrant/secret.txt
sleep 1
adb -s $S shell am start --activity-clear-task -n io.seika.pilab/.EmitActivity --es mode mutable-implicit
sleep 3
adb -s $S logcat -d -v tag | grep -E "PILAB|PIATK|does not allow granting|PendingIntent" | cut -c1-300
```

![logcat: immutable-explicit flags=0x4000000에서 DoneActivity reached data=null flags=0x10000000, mutable-explicit flags=0x2000000에서 DoneActivity reached data=content://io.seika.pilab.secret/secret.txt flags=0x10000001, nogrant URI로 바꾼 mutable-implicit에서 W/ActivityManager SecurityException "NoGrantProvider does not allow granting of Uri permissions" at PendingIntentRecord.sendInner(PendingIntentRecord.java:501), 그 뒤에도 PIATK Helper sent fill-in 로그](/assets/img/android-mastery/p1c19/06-device-pi-defenses.png)

immutable은 fill-in을 통째로 무시했다. `DoneActivity`는 `data=null`, 플래그 `0x10000000`만 받았다. [`PendingIntentRecord` 365행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/PendingIntentRecord.java#365)이 `FLAG_IMMUTABLE`을 보고, `fillIn`은 `if (!immutable)` 안에서만 부른다. immutable 쪽 else 분기는 생성 시점의 resolvedType만 가져간다.

![PendingIntentRecord.java android-13.0.0_r84 359~388행, 365행 final boolean immutable = (key.flags & PendingIntent.FLAG_IMMUTABLE) != 0 강조, 366행 if (!immutable) 안에서만 finalIntent.fillIn(intent, key.flags) 호출](/assets/img/android-mastery/p1c19/01-src-pendingintentrecord-fillin.png)

내가 틀리게 예상했던 건 mutable explicit 쪽이다. 막히긴 했으니 결과만 보면 안전하지만, 로그를 보면 `DoneActivity`가 `data=content://io.seika.pilab.secret/secret.txt`와 `flags=0x10000001`을 받았다. 공격자의 data와 grant 플래그는 그대로 들어갔다. Intent가 피해자 앱 밖으로 나가지 못한 건 컴포넌트가 `DoneActivity`로 고정돼 있었기 때문이다. 컴포넌트가 지정된 Intent는 fillIn이 컴포넌트를 바꾸지 못하니 목적지가 정해진다. 그래도 `DoneActivity`가 받은 data를 믿고 무언가를 한다면 그건 또 다른 주입 경로가 된다.

grant를 허용하지 않는 provider로 겨눈 경우는 시스템이 막았다. `W/ActivityManager`에 `Provider io.seika.pilab/io.seika.pilab.NoGrantProvider does not allow granting of Uri permissions`가 `PendingIntentRecord.sendInner(PendingIntentRecord.java:501)` 스택과 함께 찍혔고, `LeakActivity`는 시작되지 않았다. 이 예외는 [`UriGrantsManagerService` 1224행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/uri/UriGrantsManagerService.java#1224)의 `if (!grantAllowed)` 분기 안, 1235행에서 던진다. provider가 `grantUriPermissions`도, 맞는 `<grant-uri-permission>` 패턴도 없으면 보내는 쪽이 provider 주인이라도 grant를 거절한다.

![UriGrantsManagerService.java android-13.0.0_r84 1218~1247행, 1224행 if (!grantAllowed) 강조, 1235~1238행 throw new SecurityException "does not allow granting of Uri permissions", 1242행 주석 Third... does the caller itself have permission to access this uri?](/assets/img/android-mastery/p1c19/02-src-ugm-nogrant.png)

공격자 쪽에서는 이 실패가 보이지 않는다. `pi.send()`는 예외를 던지지 않았고 `HelperActivity`는 실패한 뒤에도 `Helper sent fill-in`을 찍었으니, 실패는 위 캡처의 `W/ActivityManager` 줄에서만 보인다.

## Android 14 이후에도 targetSdk가 정한다

[Android 14 동작 변경 문서](https://developer.android.com/about/versions/14/behavior-changes-14#safer-intents)는 targetSdk 34 이상 앱이 mutable 암시적 PendingIntent를 만들면 시스템이 예외를 던진다고 적고 있다. 그 차단이 기기 버전으로 걸리는지 앱의 targetSdk로 걸리는지 보려고 Android 16 에뮬레이터에 같은 targetSdk 33 피해자를 올렸다. 이 이미지는 처음 부팅한 상태라 체인이 느려서, 처음에 `sleep 3`으로 잡았을 때는 로그가 아직 안 나와 있었다. 대기를 15초로 늘리고 logcat 버퍼를 `logcat -G 4M`으로 키운 뒤(캡처 밖에서 한 번 실행) 다시 돌렸다. grep 필터도 처음에는 `PendingIntent`라는 단어를 통째로 걸었더니 Google 서비스 쪽 `ctxmgr`, `AnomalyConfigLogger` 줄이 섞여 들어와서, 경고 태그 `W/PendingIntent`와 BAL 줄만 남기도록 좁혔다.

```bash
adb -s $S shell getprop ro.build.version.sdk
adb -s $S install -r out/pilab.apk
adb -s $S install -r out/piatk.apk
adb -s $S logcat -c
adb -s $S shell am start --activity-clear-task -n io.seika.pilab/.EmitActivity --es mode mutable-implicit
sleep 15
adb -s $S logcat -d -v tag | grep -E "PILAB|PIATK|^W/PendingIntent|BAL hardening" | grep -vE '^W/PendingIntent:[[:space:]]+at ' | cut -c1-300
```

![API 36 기기, getprop ro.build.version.sdk 36, targetSdk 33 피해자 mutable-implicit 실행 뒤 W/PendingIntent "New mutable implicit PendingIntent: pkg=io.seika.pilab ... This will be blocked once the app targets U+", E/ActivityTaskManager "With Android 14 BAL hardening this activity start will be blocked if the PI sender upgrades target_sdk to 34+", LeakActivity myUid=10217, LeakActivity read -> pilab-secret-7311](/assets/img/android-mastery/p1c19/10-aux36-target33.png)

Android 16에서도 targetSdk 33 앱은 그대로 뚫렸다. 생성 시점에 `W/PendingIntent`로 "This will be blocked once the app targets U+" 경고가 찍히고, 시작 시점에 `E/ActivityTaskManager`가 백그라운드 Activity 시작(BAL) 강화 관련으로 "With Android 14 BAL hardening this activity start will be blocked if the PI sender upgrades target_sdk to 34+"를 남겼지만, 시작은 진행됐고 공격자 UID 10217이 `pilab-secret-7311`을 읽었다. 경고는 [`PendingIntent` 466행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/app/PendingIntent.java#466)의 조건 안에서, `BLOCK_MUTABLE_IMPLICIT_PENDING_INTENT`가 켜지지 않은 앱에만 [473행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/app/PendingIntent.java#473)의 `Log.w`로 찍는다.

같은 피해자를 targetSdk 34로 다시 빌드해 올렸다(`out/pilab-t34.apk`, 설치 뒤 `dumpsys package io.seika.pilab`에 `targetSdk=34`). 이번에는 `mutable-implicit` 생성 자체가 `IllegalArgumentException`으로 실패했다. 이어서 `FLAG_ALLOW_UNSAFE_IMPLICIT_INTENT`(0x01000000)를 더한 `mutable-unsafe`(플래그 `0x3000000`)로 만들자 PendingIntent가 생성됐고, 하이재크가 똑같이 재현됐다. 처음 돌렸을 때는 앞 실험의 `LeakActivity` 태스크가 앞으로 불려 나오기만 하고 `onCreate` 로그가 안 찍혀서, 공격자 앱에 `pm clear`와 `am force-stop`을 넣었다.

![API 36, pm clear 결과 Success 다음 logcat -c, mutable-implicit 실행, sleep 15, am force-stop io.seika.piatk, mutable-unsafe 실행 뒤 logcat: Emit targetSdk=34 mutable-implicit에서 W/PILAB Emit getActivity failed: IllegalArgumentException "Targeting U+ (version 34 and above) disallows creating or retrieving a PendingIntent with FLAG_MUTABLE, an implicit Intent", 이어서 mutable-unsafe flags=0x3000000 생성 성공, LeakActivity myUid=10217 read -> pilab-secret-7311](/assets/img/android-mastery/p1c19/11-aux36-target34.png)

이 예외는 system_server의 [`ActivityManagerService` 5509행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/am/ActivityManagerService.java#5509)의 검사에 걸리고, 같은 블록의 5530행에서 던진다. 앱별 compat 변경 `BLOCK_MUTABLE_IMPLICIT_PENDING_INTENT`(236704164)가 켜진 앱, 곧 targetSdk 34 이상인 앱에만 해당한다. "암시적"의 정의는 [`isNewMutableDisallowedImplicitPendingIntent`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/app/PendingIntent.java#478) 안에서 컴포넌트와 패키지가 둘 다 null인 경우이고([488행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/app/PendingIntent.java#488)), `FLAG_NO_CREATE`나 `FLAG_ALLOW_UNSAFE_IMPLICIT_INTENT`가 있으면 대상에서 빠진다. base Intent에 `setPackage`만 해도 이 검사는 통과한다. 소스대로라면 그때는 앞에서 본 패키지 fill-in 규칙(이미 있으면 안 바뀐다) 때문에 공격자가 목적지를 자기 앱으로 돌리지 못하겠지만, 이 조합은 따로 돌려 보지 않았다.

BAL 로그는 보내는 쪽이 targetSdk 34 이상이면 막힌다고 했는데, 이 부분은 공격자 앱을 targetSdk 34 이상으로 빌드해야 확인할 수 있고 이번에는 그 빌드를 돌리지 않았다. 이 실험에서는 보내는 쪽(piatk, targetSdk 33)이 `postDelayed`로 화면 맨 앞에 올라온 뒤 보냈기 때문에 `BAL_ALLOW_VISIBLE_WINDOW`로 허용됐다. 그런데 [백그라운드 Activity 시작 제한 문서](https://developer.android.com/guide/components/activities/background-starts#senders-must)를 보면 targetSdk 34 이상인 sender는 `send` 때 `ActivityOptions.setPendingIntentBackgroundActivityStartMode`로 자기 BAL 권한을 넘기겠다고 직접 opt-in한다. 그 opt-in을 정하는 쪽이 공격자이니, 이 규칙을 피해자 쪽 방어로 치기는 어려워 보인다.

## 대신 읽어 주는 공유 대상

이제 반대 방향이다. 피해자의 `ImportActivity`는 `ACTION_SEND`로 들어온 `EXTRA_STREAM` URI를 제 권한으로 열어서 내용을 결과로 돌려준다. 공유받은 파일을 미리 보기로 보여 주는 흔한 기능을 줄여 놓은 것이다.

```java
// apps/victim/src/io/seika/pilab/ImportActivity.java 발췌
@Override protected void onCreate(Bundle b) {
    super.onCreate(b);
    Uri u = incoming(getIntent());   // EXTRA_STREAM, 없으면 getData()
    String tag = getClass().getSimpleName();
    Log.i(EmitActivity.TAG, tag + " uri=" + u + " caller=" + getCallingPackage());
    if (!allowed(u)) { setResult(RESULT_CANCELED); finish(); return; }
    try {
        String text = readAll(getContentResolver().openInputStream(u));
        Log.i(EmitActivity.TAG, tag + " read " + text.length() + " chars, returning them to " + getCallingPackage());
        setResult(RESULT_OK, new Intent().putExtra("preview", text));
    } catch (Exception e) {
        Log.w(EmitActivity.TAG, tag + " read failed: " + e);
        setResult(RESULT_CANCELED);
    }
    finish();
}

/** The vulnerable version trusts everything. */
boolean allowed(Uri u) { return u != null; }
```

공격자가 직접 열면 둘 다 실패한다. `content://io.seika.pilab.secret/secret.txt`는 `not exported from UID 10179`로 거부됐고, `file:///data/data/io.seika.pilab/files/secret.txt`는 `EACCES`가 아니라 `ENOENT`로 실패했다. 이 시스템 이미지에서 공격자 프로세스에게는 다른 앱의 `/data/data` 항목이 아예 보이지 않는다는 뜻으로 읽었지만 더 파고들지는 않았다.

같은 content URI를 `ImportActivity`에 건네자 결과가 달라졌다. provider 로그의 호출자가 `callingUid=10179 callingPackage=io.seika.pilab`, 피해자 자신이다. 피해자는 17자를 읽어 `io.seika.piatk`에 돌려줬고, 공격자는 `preview=pilab-secret-7311`을 받았다.

![logcat: mode=direct에서 SecurityException "not exported from UID 10179"와 FileNotFoundException ENOENT, import-content에서 SecretProvider openFile callingUid=10179 callingPackage=io.seika.pilab, result code=-1 preview=pilab-secret-7311, import-file-strict에서 FileUriExposedException, import-file-lax에서 StrictMode VmPolicy LAX 후 file:// URI도 preview=pilab-secret-7311](/assets/img/android-mastery/p1c19/07-device-confused-deputy.png)

![에뮬레이터 화면 PiAtk: mode=import-content, start ImportActivity EXTRA_STREAM=content://io.seika.pilab.secret/secret.txt -> sent, result code=-1 preview=pilab-secret-7311](/assets/img/android-mastery/p1c19/08-emu-import-result.png)

`file://` 경로도 시험했다. 공격자 앱(targetSdk 33)이 `file://` URI를 Intent에 넣자 보내는 쪽에서 `FileUriExposedException`이 났다. 이 검사는 targetSdk 24 이상 앱의 기본 StrictMode VmPolicy가 보내는 쪽 프로세스 안에서 거는 것이라 보내는 앱이 스스로 끌 수 있다. 공격자가 `StrictMode.setVmPolicy(VmPolicy.LAX)`로 풀자 그냥 보내졌고, 피해자는 제 파일을 `file://`로 열어 돌려줬다(위 logcat 캡처의 `import-file-strict`, `import-file-lax` 줄).

## 공유 대상을 고치다 정상 공유까지 막은 일

`SafeImportActivity`는 처음에 이렇게 판단하도록 썼다. 스킴은 `content`만 받는다. authority가 가리키는 provider가 내 앱 것이면 거부한다. 마지막으로 호출자 UID가 그 URI를 읽을 수 있는지 `Context.checkUriPermission(uri, -1, callerUid, FLAG_GRANT_READ_URI_PERMISSION)`로 확인한다. 호출자가 못 읽는 URI를 내가 대신 읽어 주면 안 된다는 생각이다.

두 버전의 APK를 번갈아 설치하며 같은 세 요청을 보냈다. 첫 버전 `out/v1/pilab.apk`는 아래 `check` 메서드에서 provider 소유 UID를 허용하는 줄(`SafeImportActivity.java` 34행)이 없던 상태로 처음 빌드한 `out/pilab.apk`(빌드 옵션은 앞과 같다)를, 다시 빌드하기 전에 `out/v1/`로 복사해 둔 것이다. 이 버전에서 내 provider URI와 `file://` 공격은 막혔다. 그런데 공격자 앱이 자기 provider(`io.seika.piatk.files`)의 URI를 grant까지 붙여 정상적으로 공유한 경우도 `caller uid 10180 cannot read it`으로 막혔다.

![adb install -r out/v1/pilab.apk 뒤 첫 SafeImportActivity: safe-content는 reason=own provider io.seika.pilab.SecretProvider로 차단, safe-file은 reason=scheme file로 차단, safe-own의 content://io.seika.piatk.files/shared.txt +grant도 reason=caller uid 10180 cannot read it으로 차단되어 result code=0 preview=null](/assets/img/android-mastery/p1c19/09-device-safe-import-v1.png)

원인은 `checkUriPermission`이 결국 도착하는 [`UriGrantsManagerService.checkUriPermissionLocked`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/uri/UriGrantsManagerService.java#1275)에 있었다. 이 함수는 uid가 0이면 허용하고, 그 밖에는 grant 테이블에서 정확히 일치하는 항목과 prefix 항목만 찾는다. provider를 소유한 UID인지는 보지 않는다. 호출자는 자기 URI의 주인이라 grant 테이블에 자기 항목이 있을 리 없으니 DENIED가 나온다. 그래서 provider 소유 UID가 호출자 UID와 같으면 허용하는 줄을 넣고 다시 빌드했다.

```java
// apps/victim/src/io/seika/pilab/SafeImportActivity.java (고친 뒤 check 메서드)
private String check(Uri u) {
    if (u == null) return "no uri";
    if (!"content".equals(u.getScheme())) return "scheme " + u.getScheme();
    PackageManager pm = getPackageManager();
    ProviderInfo pi = pm.resolveContentProvider(u.getAuthority(), 0);
    if (pi == null) return "unknown authority " + u.getAuthority();
    if (getPackageName().equals(pi.packageName)) return "own provider " + pi.name;
    String caller = getCallingPackage();
    if (caller == null) return "caller unknown (not started for result)";
    int callerUid;
    try {
        callerUid = pm.getPackageUid(caller, 0);
    } catch (PackageManager.NameNotFoundException e) {
        return "caller not visible " + caller;
    }
    // checkUriPermission only consults the URI grant table, so the provider's own UID is not in it
    if (pi.applicationInfo.uid == callerUid) return null;   // 파일의 34행, v1에는 없던 줄
    if (checkUriPermission(u, -1, callerUid, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            != PackageManager.PERMISSION_GRANTED) return "caller uid " + callerUid + " cannot read it";
    return null;
}
```

고친 `out/pilab.apk`를 설치하고 같은 요청을 다시 보내면 자기 provider와 `file` 스킴은 여전히 막히고, 호출자 자신의 URI는 `SafeImport allowed`로 통과해 `preview=piatk-shared-note`가 돌아온다.

![adb install -r out/pilab.apk 뒤 고친 SafeImportActivity: safe-content는 own provider로 차단 result code=0, safe-file은 scheme file로 차단, safe-own은 SafeImport allowed uri=content://io.seika.piatk.files/shared.txt, read 17 chars, result code=-1 preview=piatk-shared-note](/assets/img/android-mastery/p1c19/09-device-safe-import.png)

이 수정도 빈틈이 있다. 호출자가 소유하지도 않고 grant도 받지 않았지만 export된 provider나 권한으로 정당하게 읽을 수 있는 제3자 URI는 `checkUriPermission`이 여전히 거부할 것이다. 그 경우는 이번에 돌려 보지 않았다. [`getCallingPackage()`](https://developer.android.com/reference/android/app/Activity#getCallingPackage())는 `startActivityForResult`로 시작됐을 때만 값이 있어서, 결과를 받지 않는 공유 흐름에서는 `getCallingPackage()`가 null이라 이 검사 전체가 "caller unknown"으로 끝난다.

## 방어를 고르고 확인하는 법

PendingIntent는 `FLAG_IMMUTABLE`에 컴포넌트를 지정한 base Intent로 만든다. 측정에서 fill-in을 완전히 무시한 건 immutable뿐이었다. 인라인 답장처럼 정말 mutable이 필요하면 최소한 컴포넌트를 지정한다. 그러면 Intent는 내 앱 밖으로 못 나가지만, mutable explicit 실험에서 본 것처럼 data와 grant 플래그는 여전히 들어오니 받는 쪽 컴포넌트가 그 값을 검증해야 한다. targetSdk를 34 이상으로 올리면 암시적 mutable 생성은 시스템이 막아 주지만, `FLAG_ALLOW_UNSAFE_IMPLICIT_INTENT` 한 비트로 그대로 되살아난다는 걸 위에서 봤다. 코드 리뷰에서는 이 플래그(0x01000000)가 보이면 의심하는 편이 낫다.

provider 쪽에서는 grant가 꼭 필요한 provider에만 허용한다. [`<provider>` 문서](https://developer.android.com/guide/topics/manifest/provider-element#gprmsn)는 `grantUriPermissions="true"`를 provider의 URI 전체에 grant를 여는 설정으로, 속성을 false로 두고 [`<grant-uri-permission>`](https://developer.android.com/guide/topics/manifest/grant-uri-permission-element)에 적은 경로만 여는 것을 좁히는 방법으로 설명한다. 그러니 속성은 false로 두고 `<grant-uri-permission android:pathPrefix=…>`로 grant를 내줄 경로만 적는다. Android 13 소스에서는 [`UriGrantsManagerService` 1212~1223행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/uri/UriGrantsManagerService.java#1212)이 패턴이 하나라도 있으면 `grantAllowed`를 패턴 일치 여부로 다시 정해서 속성이 true여도 경로가 좁혀지는 것으로 읽히지만, 이 조합은 돌려 보지 않았고 문서와도 다르니 기대지 않는 편이 낫다. `NoGrantProvider` 실험에서 grant가 꺼진 provider는 피해자 이름을 빌려도 grant가 나가지 않았다. 공유받은 URI를 대신 여는 코드는 스킴, 내 provider 여부, 호출자가 읽을 수 있는지를 따진다.

확인은 실제로 공격해 보는 게 제일 빠르다. 위 공격자 앱처럼 fill-in으로 data와 `FLAG_GRANT_READ_URI_PERMISSION`을 넣어 보낸 뒤 dumpsys와 system_server 로그를 본다.

```bash
# 공격자 UID 앞으로 피해자 URI grant가 생겼는지
adb -s $S shell dumpsys activity permissions | grep -A2 "holds:"
# send()는 조용하니 실패 이유는 system_server 로그에서 본다
adb -s $S logcat -d -v tag | grep -E "does not allow granting|^W/PendingIntent|BAL hardening"
```

*다음 글: [Deep Link·App Link·WebView 실습](/posts/android-lab-p1c20-deeplink-applink-webview/)*
