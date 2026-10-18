---
layout: post
title: "adb·logcat·dumpsys 증적 수집 — 링 버퍼가 덮어쓰기 전에"
date: 2026-10-17 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, adb, logcat, dumpsys, run-as, AppOps, 증적수집]
excerpt: "Android 13 에뮬레이터에서 자작 앱이 흘린 가짜 토큰을 logcat·run-as·dumpsys로 거둬 봤다. 256 KiB main 버퍼는 20000줄 flood 한 번에 토큰 줄을 잃었고, READ_LOGS를 받은 앱도 사용자 동의 없이는 events 버퍼만 읽었다."
---

[지난 글](/posts/android-lab-p1c01-research-environment/)에서 `adb root`가 되는 userdebug 이미지를 골랐다. 그 위에서 앱을 뜯기 전에, 앱이 어떤 UID와 권한으로 깔렸고 실행하면서 로그와 저장소에 무엇을 남겼는지부터 받아 적는다. 이 기록이 있어야 나중에 정적·동적 분석에서 나온 결론을 되짚을 수 있다.

쓰는 명령은 대부분 `adb`, `logcat`, `dumpsys`, `pm`, `am` 안에 있다. 손에 익은 명령들인데 하나씩 다시 돌려 보니 출력이 내가 알던 것과 어긋나는 곳이 여럿 있었다. 릴리스로 빌드한 앱도 토큰을 로그에 그대로 찍었다.

## 가짜 토큰을 흘리는 실험 앱

대상은 직접 만든 `io.seika.evidence`다. Gradle 없이 javac, d8, aapt, apksigner로 묶은 작은 Java 앱(minSdk 26, targetSdk 33, debug 키)이고, 실행하면 JWT 모양의 가짜 토큰을 로그에 찍은 뒤 같은 값을 `shared_prefs/auth.xml`과 `files/session.json`에 평문으로 쓴다. 서명 자리에 `FAKE_SIG_ONLY_FOR_LAB`을 박아 둔 실험용 값이라 아래 출력에서도 가리지 않았다. `MainActivity.login()`의 앞부분이 그 동작이다.

```java
    void login() {
        Log.d("SeikaAuth", "login ok user=demo access_token=" + TOKEN);
        SharedPreferences sp = getSharedPreferences("auth", Context.MODE_PRIVATE);
        sp.edit().putString("access_token", TOKEN).putString("user", "demo").commit();
        try (FileOutputStream f = openFileOutput("session.json", Context.MODE_PRIVATE)) {
            f.write(("{\"user\":\"demo\",\"token\":\"" + TOKEN + "\"}\n").getBytes("UTF-8"));
        } catch (Exception e) { Log.e("SeikaAuth", "write failed", e); }
```

매니페스트에는 `pm grant` 결과를 비교하려고 보호 수준이 다른 권한을 일부러 섞었다. INTERNET은 normal, 위치 권한 둘은 runtime(dangerous), READ_LOGS는 signature·privileged·development 플래그가 붙은 권한, INSTALL_PACKAGES는 signature·privileged 권한이다. 컴포넌트는 런처 액티비티 말고도 exported 리시버, intent-filter 없는 exported 서비스, exported provider를 붙였다.

```xml
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    <uses-permission android:name="android.permission.READ_LOGS"/>
    <uses-permission android:name="android.permission.INSTALL_PACKAGES"/>
    <application android:label="Evidence Lab" android:debuggable="true" android:allowBackup="true">
        ...
        <receiver android:name=".PingReceiver" android:exported="true">
            <intent-filter><action android:name="io.seika.evidence.PING"/></intent-filter>
        </receiver>
        <service android:name=".SyncService" android:exported="true"/>
        <provider android:name=".NotesProvider" android:authorities="io.seika.evidence.notes"
            android:exported="true"/>
    </application>
```

이 소스로 debuggable 빌드(`evidence-debug.apk`), `android:debuggable`을 뺀 빌드(`evidence-release.apk`), debuggable 빌드에 `android:testOnly="true"`를 더한 빌드(`evidence-testonly.apk`)를 만들어 번갈아 깔았다. 셋 다 한 키로 서명했다.

주 에뮬레이터는 Android 13(API 33) google_apis x86_64 userdebug 이미지다. 빌드는 `TE1A.240213.009`, 보안 패치는 2024-03-01, SELinux는 Enforcing. user 빌드와 견줄 때는 같은 빌드 번호의 google_apis_playstore 이미지를, 옛 동작과 견줄 때는 Android 8.0(API 26) 이미지를 잠깐 띄웠다. 호스트 adb는 1.0.41(platform-tools 37.0.0)이고, 에뮬레이터 시계가 UTC라서 아래 로그 시각도 전부 UTC다.

## 설치 옵션 `-t`와 `-g`가 실제로 한 일

직접 빌드한 디버그 앱이니 `adb install -t`로 깔아야 한다고 생각하고 있었다. 돌려 보니 `-t` 없이 거부된 건 testOnly 빌드뿐이었고 debuggable 빌드는 옵션 없이 깔렸다.

```text
$ adb install out/evidence-testonly.apk
Performing Streamed Install
adb.exe: failed to install out/evidence-testonly.apk: Failure [INSTALL_FAILED_TEST_ONLY: installPackageLI]

$ adb install -t out/evidence-testonly.apk
Performing Streamed Install
Success
$ adb uninstall io.seika.evidence
Success
$ adb install out/evidence-debug.apk
Performing Streamed Install
Success
```

[`PackageManagerShellCommand.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/PackageManagerShellCommand.java#3067)를 보면 `-t`는 `INSTALL_ALLOW_TEST` 플래그 하나를 켤 뿐이다. 바로 아래에서 `-g`는 `INSTALL_GRANT_RUNTIME_PERMISSIONS`가 되는데, 이름과 달리 런타임 권한만 주지 않았다. `-g`로 깔자 READ_LOGS까지 `granted=true`가 됐다.

```text
$ adb install -g out/evidence-debug.apk
Performing Streamed Install
Success
$ adb shell dumpsys package io.seika.evidence | grep granted=
      android.permission.INSTALL_PACKAGES: granted=false
      android.permission.INTERNET: granted=true
      android.permission.READ_LOGS: granted=true
        android.permission.ACCESS_FINE_LOCATION: granted=true
        android.permission.ACCESS_COARSE_LOCATION: granted=true
```

설치 때 권한을 나눠 주는 [`PermissionManagerServiceImpl`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/permission/PermissionManagerServiceImpl.java#3600)의 조건이 runtime이거나 development인 권한을 함께 통과시키기 때문이다.

```java
                shouldGrantPermission = bp != null && (bp.isRuntime() || bp.isDevelopment())
                        && (!instantApp || bp.isInstant())
                        && (supportsRuntimePermissions || !bp.isRuntimeOnly())
                        && (permissions == null || permissions.contains(permission));
```

`adb install -r`로 덮어 깔면 UID와 데이터, 권한이 그대로 남지만, 지웠다가 다시 깔면 UID가 바뀐다. 그래서 증적에 UID를 적을 때는 어느 설치본의 UID인지까지 같이 남겨 두어야 나중에 로그의 UID와 맞춰 볼 수 있다. 이번에도 다시 깔 때마다 10180, 10181, 10182, 10184로 바뀌었다. 10183은 실험 앱을 처음 깔기 전인 부팅 직후 로그에 이미 찍혀 있었으니, 다른 앱이 쓰던 번호라 건너뛴 것으로 보인다.

## dumpsys package로 읽는 설치 상태

`dumpsys`는 서비스 매니저에서 이름으로 시스템 서비스를 찾아 그 서비스의 `dump()`를 부르는 얇은 클라이언트다([dumpsys.cpp](https://android.googlesource.com/platform/frameworks/native/+/refs/heads/android13-release/cmds/dumpsys/dumpsys.cpp#456)). `dumpsys package`의 출력은 PackageManagerService가 자기 상태를 글로 풀어 쓴 것이다. 이 이미지에서 `dumpsys -l`로 본 서비스는 247개였다. 방금 깐 디버그 빌드의 출력에서 증적으로 쓸 줄만 걸렀다.

![adb install out/evidence-debug.apk 가 Success, pm list packages -3 -U 가 io.seika.evidence uid:10181 을 돌려주고, dumpsys package 발췌에 userId=10181, targetSdk=33, signatures 값 687d1130, pkgFlags DEBUGGABLE HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP, requested 권한 5개, install 권한 INSTALL_PACKAGES false·INTERNET true·READ_LOGS false, User 0 줄의 stopped=true notLaunched=true, firstInstallTime 2026-10-14 11:00:18, runtime 위치 권한 둘 다 granted=false 가 보이는 터미널](/assets/img/android-mastery/p1c02/01-dumpsys-package.png)

`userId=10181`이 이 앱의 리눅스 UID다. `pkgFlags`의 `DEBUGGABLE`은 뒤에서 볼 run-as와, targetSdk 31 이상 앱의 `adb backup`이 되느냐를 함께 가른다. `ALLOW_BACKUP`은 클라우드 백업 쪽 값이고, adb backup에서는 targetSdk 30 이하일 때만 쓰인다. 권한은 두 덩어리로 찍힌다. `install permissions`는 패키지 단위이고, `runtime permissions`는 `User 0:` 줄 아래에 사용자 단위로 들여 써진다. grep으로 런타임 권한 줄을 뽑는다면 줄 모양이 두 가지라는 걸 감안해야 한다. 위 캡처(11:00:18 설치)에서는 `granted=false`로 끝났는데, 10:48에 갓 깔았을 때는 아무 권한도 주기 전인데도 두 줄 끝에 `USER_SENSITIVE_WHEN_GRANTED`와 `USER_SENSITIVE_WHEN_DENIED`를 담은 `flags=[ ... ]`가 붙어 있었다. 한 번도 주지 않은 COARSE 권한에도 같은 플래그가 붙었으니 권한을 준 결과는 아니다.

`User 0:` 줄의 `stopped=true notLaunched=true`는 설치만 되고 한 번도 실행되지 않았다는 표시다. 처음 실행하면 둘 다 `false`가 되고, `am force-stop` 뒤에는 `stopped=true`만 돌아온다. 이 앱이 실제로 실행된 적이 있느냐를 따질 때 쓸 수 있다.

### 목록에 없는 exported 서비스

intent-filter 없는 exported 서비스 `SyncService`는 `dumpsys package` 출력 어디에도 없었다. 컴포넌트는 intent-filter로 등록된 resolver 표와 provider 목록을 거쳐서만 나온다.

```text
Receiver Resolver Table:
  Non-Data Actions:
      io.seika.evidence.PING:
        18f023c io.seika.evidence/.PingReceiver filter 2fa6bc5
          Action: "io.seika.evidence.PING"
...
ContentProvider Authorities:
  [io.seika.evidence.notes]:
    Provider{d1f804 io.seika.evidence/.NotesProvider}
```

```text
$ adb shell dumpsys package io.seika.evidence | grep -c SyncService
0
$ adb shell cmd package query-services --components -n io.seika.evidence/.SyncService
io.seika.evidence/.SyncService
$ aapt2 dump xmltree --file AndroidManifest.xml out/evidence-release.apk | grep -E 'E: (activity|receiver|service|provider)|exported'
          E: activity (line=10)
            A: http://schemas.android.com/apk/res/android:exported(0x01010010)=true
          E: receiver (line=16)
            A: http://schemas.android.com/apk/res/android:exported(0x01010010)=true
          E: service (line=19)
            A: http://schemas.android.com/apk/res/android:exported(0x01010010)=true
          E: provider (line=20)
            A: http://schemas.android.com/apk/res/android:exported(0x01010010)=true
```

이름을 알면 `cmd package query-services`로 찾을 수 있지만, 이름을 모르는 컴포넌트를 빠짐없이 exported 여부까지 보려면 매니페스트를 디코드해야 한다. 그 방법은 [다음 글](/posts/android-lab-p1c03-apk-triage/)에서 다룬다.

### signatures 값은 Java hashCode다

`signatures:[687d1130]`은 인증서 지문과 상관없는 값이다. [PackageSignatures.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/PackageSignatures.java#313)의 문자열 변환은 각 `Signature`의 `hashCode()`를 16진수로 찍고, 그 `hashCode()`는 [Signature.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/content/pm/Signature.java#269)에서 서명 바이트에 대한 `Arrays.hashCode`다.

```java
    @Override
    public int hashCode() {
        if (mHaveHashCode) {
            return mHashCode;
        }
        // Note, similar to equals some classes rely on the hash code not including
        // the flags for Set membership checks.
        mHashCode = Arrays.hashCode(mSignature);
        mHaveHashCode = true;
        return mHashCode;
    }
```

32비트 비암호 해시라 서명자를 증명하는 값으로 쓸 수 없다. 앞의 `PackageSignatures{56136f7`는 객체마다 붙는 identity hash라 서명 내용과는 상관이 없다. 설치할 때마다(`-r`로 덮어 깔 때도) 이 객체가 새로 만들어지니, 재부팅 없이 한 부팅 안에서도 `78f72b3`, `56136f7`, `5857f32`로 바뀌었다. 서명은 APK를 뽑아 apksigner로 본다.

```text
$ adb pull $(adb shell pm path io.seika.evidence | cut -d: -f2) raw/base.apk
/data/app/~~AvcroojZefwV_tQdt-aXew==/io.seika.evidence-KFLOHzj74rfB8Fex7PcqNg==/base.apk: 1 file pulled, 0 skipped. 6.0 MB/s (12631 bytes in 0.002s)
$ sha256sum raw/base.apk out/evidence-release.apk
51f481db4fa1edd4b475f5caf203c876e24e65dbe372ca887d88184c95c89885 *raw/base.apk
51f481db4fa1edd4b475f5caf203c876e24e65dbe372ca887d88184c95c89885 *out/evidence-release.apk
$ apksigner verify --print-certs raw/base.apk
Signer #1 certificate DN: C=US, O=Android, CN=Android Debug
Signer #1 certificate SHA-256 digest: 766e4a4ce2ecb9bfce171ec829100591aa9f0bbd3fa1a497ad909ee5b9d2feb1
Signer #1 certificate SHA-1 digest: 0679ec7bdf576e4552e0ccd8354faeb2e89c2735
Signer #1 certificate MD5 digest: 92815a7f2913c239a33045c80b9efd1f
$ adb shell dumpsys package io.seika.evidence | grep signatures=
    signatures=PackageSignatures{5857f32 version:3, signatures:[687d1130], past signatures:[]}
```

`pm path`에 나오는 `~~…==` 디렉터리 이름은 설치할 때마다 바뀌니 같은 파일인지는 경로보다 해시로 묶어야 하는데, 기기에서 뽑은 `base.apk`의 SHA-256은 빌드 산출물(`evidence-release.apk`)과 같았다.

### pm dump, 그리고 pm과 am의 정체

`pm dump <pkg>`의 출력은 1909줄로 `dumpsys package <pkg>`보다 훨씬 길었다. 섹션 머리를 따라가면 `DUMP OF SERVICE package:` 뒤로 activity, meminfo, procstats, usagestats, batterystats가 차례로 붙는다. 앞에서 안 보이던 `SyncService`가 `pm dump`에는 세 번 나왔는데 전부 procstats 쪽(`* Svc io.seika.evidence.SyncService:`)이었다. usagestats 섹션에는 실행 이력이 절대 시각으로 남는다.

```text
    time="2026-10-14 11:00:58" type=ACTIVITY_RESUMED package=io.seika.evidence class=io.seika.evidence.MainActivity ...
    ...
    time="2026-10-14 11:01:20" type=ACTIVITY_STOPPED package=io.seika.evidence class=io.seika.evidence.MainActivity ...
    ...
      package=io.seika.evidence totalTimeUsed="00:57" lastTimeUsed="2026-10-14 11:01:59" ...
```

마지막 `totalTimeUsed="00:57"` 줄은 일 단위 통계(`In-memory daily stats`)다. 지우고 다시 깔기 전 설치본의 11:00:35 실행은 이벤트 목록(`Last 24 hour events`)에 없었고, 일 단위 합계도 `appLaunchCount=5`에 그쳤다. 그런데 같은 출력의 주·월·연 단위 통계는 `totalTimeUsed="10:18"`, `appLaunchCount=21`로, 10:48 이후 앞 설치본들의 실행까지 합쳐 들고 있었다. 재설치로 사라진 건 이벤트 단위의 상세 기록이고 누적 사용량은 남았다. 어느 코드가 무엇을 지우는지는 따라가 보지 않았다.

`pm`과 `am`은 바이너리조차 아니었다.

```text
$ adb shell cat /system/bin/pm
#!/system/bin/sh
cmd package "$@"
$ adb shell cat /system/bin/am
#!/system/bin/sh

if [ "$1" != "instrument" ] ; then
    cmd activity "$@"
else
    ...
    exec app_process $base/bin com.android.commands.am.Am "$@"
fi
```

API 33에서는 `pm`을 치든 `cmd package`를 치든 같은 셸 명령 구현에 도착한다. 다음 절에서 볼 `pm grant` 예외의 스택트레이스에 `PackageManagerShellCommand.runGrantRevokePermission`이 찍히는 것도 그래서다.

## pm grant가 바꾸는 권한, appops가 남기는 접근 기록

설치 때 `-g`가 READ_LOGS까지 준 것을 봤으니, `pm grant`도 같은 기준을 쓰는지 보호 수준별로 하나씩 넣어 봤다.

![cmd appops get 이 COARSE_LOCATION·FINE_LOCATION ignore, pm grant ACCESS_FINE_LOCATION 과 READ_LOGS 는 출력 없이 성공, INTERNET 과 INSTALL_PACKAGES 는 java.lang.SecurityException is not a changeable permission type, dumpsys granted= 줄에 READ_LOGS true·FINE true·COARSE false 와 USER_SENSITIVE 플래그, 앱 실행 뒤 cmd appops get 이 foreground 와 FINE_LOCATION allow; time=+455ms ago 를 찍은 터미널](/assets/img/android-mastery/p1c02/05-pm-grant-appops.png)

위치 권한과 READ_LOGS는 출력 없이 바뀌었고, INTERNET과 INSTALL_PACKAGES는 `is not a changeable permission type`으로 거절됐다. 캡처 맨 위와 맨 아래의 `cmd appops get`은 권한을 주기 전 위치 op의 UID 모드를 `ignore`로, 권한을 주고 앱을 실행한 뒤에는 `foreground`로 보여 줬다. FINE만 줬는데 COARSE의 UID 모드도 `foreground`로 바뀌었다(`granted=` 줄로는 COARSE 권한 자체가 `granted=false`). `foreground`는 백그라운드 위치 권한 없이 포그라운드에서만 허용한다는 뜻이다.

바뀐 권한과 거절된 권한을 기기에서 `pm list permissions -f`로 본 보호 수준과 나란히 놓으면 갈리는 기준이 보인다.

```text
+ permission:android.permission.READ_LOGS
  protectionLevel:signature|privileged|development
+ permission:android.permission.INSTALL_PACKAGES
  protectionLevel:signature|privileged
+ permission:android.permission.INTERNET
  protectionLevel:normal|instant
+ permission:android.permission.WRITE_SECURE_SETTINGS
  protectionLevel:signature|privileged|development|installer|role
+ permission:android.permission.DUMP
  protectionLevel:signature|privileged|development
+ permission:android.permission.PACKAGE_USAGE_STATS
  protectionLevel:signature|privileged|development|appop|retailDemo
```

development 플래그가 붙은 권한은 signature 권한이라도 `pm grant`로 바뀐다. 판정 코드는 [PermissionManagerServiceImpl.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/permission/PermissionManagerServiceImpl.java#1384)에 있고, 기기의 스택트레이스가 가리킨 1392행은 아래 발췌의 마지막 `throw`다.

```java
            isRuntimePermission = bp.isRuntime();
            permissionHasGids = bp.hasGids();
            if (isRuntimePermission || bp.isDevelopment()) {
                // Good.
            } else if (bp.isRole()) {
                if (!mayGrantRolePermission) {
                    throw new SecurityException("Permission " + permName + " is managed by role");
                }
            } else {
                throw new SecurityException("Permission " + permName + " requested by "
                        + pkg.getPackageName() + " is not a changeable permission type");
            }
```

공식 문서도 실측과 맞지 않았다. developer.android.com의 [adb 문서](https://developer.android.com/tools/adb)는 `grant`를 설명하면서 "the permission can be any permission declared in the app manifest"라고 쓰는데, INTERNET과 INSTALL_PACKAGES는 매니페스트에 선언했어도 거절됐다. 매니페스트에 없는 CAMERA는 `has not requested permission`으로 거절됐다. 실패하면 adb 종료 코드가 255, 성공하면 0이고 아무것도 출력하지 않는다.

출력이 없다고 반영됐다고 단정할 수는 없으니, grant 뒤에는 위 캡처처럼 `dumpsys package`의 `granted=` 줄을 다시 읽는다. 앞의 판정 함수는 system-fixed 권한이나 면제받지 못한 hard-restricted 권한을 만나면 예외 없이 로그만 남기고 돌아간다. `--restrict-permissions`로 설치해야 나올 것으로 보이는 경로라 이번에는 만들지 않았다.

권한을 바꾸면 실행 중인 프로세스가 죽기도 한다. READ_LOGS처럼 gid가 딸린 권한을 주면 앱이 내려가고, 뒤에서 볼 events 버퍼에 `am_kill ... permission grant or revoke changed gids`가 남는다.

`pm list permissions -d -g`는 이 이미지에서 `android.permission.*` dangerous 권한 40개를 전부 `android.permission-group.UNDEFINED` 아래에 찍었다. 플랫폼 [AndroidManifest.xml](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/res/AndroidManifest.xml#1214)이 권한 그룹을 UNDEFINED로 선언하기 때문이라, 그룹 출력으로 위치 권한 묶음을 찾으려 하면 헛수고가 된다.

### 상대 시간과 절대 시각

캡처 마지막 줄, 접근 기록의 `time=+455ms ago`는 명령을 친 순간 기준의 상대 시간이라 나중에 다시 읽으면 의미가 없다. 그보다 앞선 회차에서는 `date -u`와 `dumpsys appops --package`를 함께 남겨 두었다.

```text
$ adb emu geo fix 127.1270 37.4505
OK
$ adb shell am force-stop io.seika.evidence
$ adb shell am start -W -n io.seika.evidence/.MainActivity
Status: ok
LaunchState: COLD
$ adb logcat -d -s SeikaLoc
--------- beginning of main
10-14 10:51:04.150  6049  6049 I SeikaLoc: lastKnown(gps)=null
$ adb shell date -u
Wed Oct 14 10:51:06 UTC 2026
$ adb shell cmd appops get io.seika.evidence
Uid mode: COARSE_LOCATION: foreground
FINE_LOCATION: foreground
FINE_LOCATION: allow; time=+2s622ms ago
$ adb shell dumpsys appops --package io.seika.evidence
Current AppOps Service state:
...
  Uid u0a180:
    state=top
    ...
      COARSE_LOCATION: mode=foreground
      FINE_LOCATION: mode=foreground
    Package io.seika.evidence:
      FINE_LOCATION (allow):
        null=[
          Access: [top-s] 2026-10-14 10:51:04.144 (-10s534ms)
        ]
```

증적으로는 `dumpsys appops` 쪽 절대 시각을 남긴다. 위치 값은 null이었지만(에뮬레이터에 마지막 위치가 아직 없었다) 접근 시도 자체는 기록됐고, 그 시각 10:51:04.144와 logcat의 SeikaLoc 줄 10:51:04.150이 6 ms 차이로 맞물렸다.

## logcat에 남은 토큰

앱을 실행하고 그 PID의 로그만 받았다. 명령 전체를 작은따옴표로 감싸면 `pidof`가 기기에서 logcat과 한 셸 안에서 돌고, 그 결과가 곧바로 `--pid`로 들어간다. POSIX 치환이 없는 PowerShell이나 cmd에서도 이 한 줄은 그대로 된다.

![adb shell 'logcat -d --pid=$(pidof io.seika.evidence) -s SeikaAuth SeikaLoc' 가 PID 7851 의 D SeikaAuth access_token 줄을 찍고, adb install -r out/evidence-release.apk 뒤 pkgFlags 에 DEBUGGABLE 이 없는데도 재실행한 PID 7918 이 같은 access_token 줄을 남긴 터미널](/assets/img/android-mastery/p1c02/02-logcat-token.png)

위쪽이 debuggable 빌드(PID 7851)가 남긴 줄이다. 그다음 `android:debuggable`을 뺀 빌드로 덮어 깔고, `pkgFlags`에서 `DEBUGGABLE`이 빠진 걸 확인한 뒤 다시 실행했다. PID 7918이 똑같은 토큰 줄을 남겼다. `Log.d`는 앱의 debuggable 여부를 보지 않으니, 호출을 코드에서 지우지 않는 한 릴리스 빌드에서도 찍힌다.

`--pid` 출력에는 앱이 찍은 줄 말고 프레임워크 줄도 섞여 나왔다. `nativeloader: ... permitted_path=/data:/mnt/expand:/data/user/0/io.seika.evidence` 같은 줄에는 데이터 경로가, `ziparchive: Unable to open '/data/app/.../base.dm'` 같은 줄에는 설치 경로가 남는다. user 빌드 에뮬레이터에서도 `adb logcat -d -s SeikaAuth`로 같은 토큰 줄이 나왔다.

### 필터의 대소문자

우선순위 문자는 대소문자를 가리지 않고, 태그는 가린다.

```text
$ adb logcat -d -b main,system ActivityManager:I "*:S" | wc -l
435
$ adb logcat -d -b main,system ActivityManager:i "*:s" | wc -l
435
$ adb logcat -d -b main,system "*:E" | wc -l
402
$ adb logcat -d -b main,system "*:e" | wc -l
402
$ adb logcat -d "*:X"
logcat: Invalid filter expression '*:X'.
exit=1
$ adb logcat -d -b main,system activitymanager:I "*:S" | wc -l
0
```

[logprint.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/liblog/logprint.cpp#106)에서 우선순위 문자는 `tolower` 후에 비교하고, 태그는 이 파일 [180행](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/liblog/logprint.cpp#180)의 `strcmp`로 비교한다. 태그 이름을 소문자로 잘못 치면 에러 없이 0줄이 나온다.

## 256 KiB 링 버퍼

로그는 logd가 메모리에 들고 있는 링 버퍼라서 새 줄이 들어오면 오래된 줄부터 밀려난다. 얼마나 빨리 밀려나는지 쟀다. 부팅 직후 버퍼 크기는 이랬다.

```text
main: ring buffer is 256 KiB (242 KiB consumed, 1 MiB readable), max entry is 5120 B, max payload is 4068 B
system: ring buffer is 256 KiB (250 KiB consumed, 1 MiB readable), max entry is 5120 B, max payload is 4068 B
crash: ring buffer is 256 KiB (0 B consumed, 0 B readable), max entry is 5120 B, max payload is 4068 B
kernel: ring buffer is 256 KiB (126 KiB consumed, 354 KiB readable), max entry is 5120 B, max payload is 4068 B
```

Android 13 logd의 기본 버퍼 구현은 serialized이고([logd/main.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/main.cpp#238)), 로그를 청크 단위로 zstd 압축해 담는다([CompressionEngine.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/CompressionEngine.cpp#82)). `logcat -g`의 readable은 버퍼에 든 로그를 풀었을 때 크기다([LogStatistics.h](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogStatistics.h#557)). consumed는 청크들이 메모리에서 차지하는 크기의 합인데([LogStatistics.h](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogStatistics.h#548), [SerializedLogBuffer.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/SerializedLogBuffer.cpp#313)), [SerializedLogChunk.h](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/SerializedLogChunk.h#77)의 `PruneSize()`가 다 찬 청크는 압축된 크기로, 아직 쓰고 있는 청크는 압축 전이라 할당된 크기 그대로 센다. 256 KiB 안에 1 MiB 분량의 텍스트가 들어 있던 셈이다.

### ro.logd.size를 읽지 않는 logd

이때 `getprop ro.logd.size`는 `1M`이었다. 그런데 버퍼는 256 KiB였다. 처음엔 속성 이름을 잘못 본 줄 알았다. 소스를 열어 보니 Android 13 logd는 크기 속성을 읽는 코드를 통째로 주석으로 막아 두었다([LogSize.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogSize.cpp#50)).

```cpp
size_t GetBufferSizeFromProperties(log_id_t /*log_id*/) {
/*
 * http://b/196856709
 *
 * We've been seeing timeouts from logcat in bugreports for years, but the
 * rate has gone way up lately. ...
    std::array<std::string, 4> properties = {
            "persist.logd.size." + buffer_name,
            "ro.logd.size." + buffer_name,
            "persist.logd.size",
            "ro.logd.size",
    };
    ...
*/

    if (android::base::GetBoolProperty("ro.config.low_ram", false)) {
        return kLogBufferMinSize;
    }

    return kDefaultLogBufferSize;
}
```

이 저장소의 [README.property](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/README.property#27)는 여전히 `ro.logd.size`가 기본 크기를 정하고 기본 버퍼 종류가 chatty라고 적고 있어서 코드와 맞지 않는다. main 브랜치에서는 debuggable 빌드이면서 `ro.hardware.type`이 automotive나 desktop일 때만 속성을 다시 읽는다([LogSize.cpp, main](https://android.googlesource.com/platform/system/logging/+/refs/heads/main/logd/LogSize.cpp#66)). 휴대폰 이미지라면 기본 256 KiB를 그대로 쓴다고 보는 게 안전하다.

### flood 한 번에 사라진 토큰 줄

앱에 flood 모드를 넣어 두었다. 난수 UUID 두 개짜리 줄을 N개 쏟는다. 처음엔 `xxxx…` 패딩으로 채웠는데 zstd가 너무 잘 눌러서 버퍼가 좀처럼 넘치지 않았고, 그래서 난수로 바꿨다.

```java
    void flood(int n) {
        // random hex so logd's compression cannot squeeze the flood away
        for (int i = 0; i < n; i++) Log.i("SeikaFlood", "line " + i + " " + java.util.UUID.randomUUID() + java.util.UUID.randomUUID());
        Log.i("SeikaFlood", "flood done n=" + n);
        tv.setText("flooded " + n + " lines");
    }
```

![logcat -g -b main 이 256 KiB(121 KiB consumed, 310 KiB readable), SeikaAuth access_token 줄 6개, main 첫 줄 10:56:02.795 와 system 첫 줄 10:56:02.835, 20000줄 flood 뒤 access_token 0개, main 첫 줄이 SeikaFlood line 16188 로 바뀌고 system 첫 줄은 그대로이며 마지막 -g 가 242 KiB consumed, 474 KiB readable 인 터미널](/assets/img/android-mastery/p1c02/03-logcat-ring.png)

토큰 줄 6개가 flood 한 번에 0개가 됐다. main의 가장 오래된 줄은 `SeikaFlood: line 16188`로 바뀌었고, system 버퍼의 첫 줄(10:56:02.835)은 flood 전후가 같았으니 링은 버퍼마다 따로 돈다.

flood 전에 main이 절반쯤(121 KiB consumed)만 차 있었던 건 10:56:02에 버퍼를 한 번 비웠기 때문이다. 명령 기록에는 빠져 있지만 main(10:56:02.795)과 system(10:56:02.835)의 첫 줄이 둘 다 릴리스 빌드를 덮어 깐 순간에 몰려 있다. `adb logcat -c`를 친 흔적으로 보인다. 그 뒤 6분 가까이 쌓인 로그가 121 KiB였고, flood가 나머지를 채워 242 KiB가 됐다.

같은 실험을 처음 했을 때(10:49)는 아직 비우기 전이라 main이 꽉 찬 상태(248 KiB consumed, 1 MiB readable)였다. 그 직전 10:49:35에 읽은 main의 가장 오래된 줄은 10:45:58이었다. 부팅(10:44)에서 5분 남짓 지났고 그사이 앱을 한 번 깔아 한 번 실행했을 뿐인데, 부팅 직후 2분 가까운 main 로그가 이미 밀려나 있었다. `am start -W`가 잰 flood 시간은 3395 ms였고, 끝나고 보니 main에는 16357번째 줄부터만 남아 있었다. 토큰 줄과 미리 `log -t SeikaMark`로 박아 둔 표지 줄이 같이 사라졌다. readable은 457 KiB로 줄었는데, 잘 눌리던 시스템 로그 자리를 덜 눌리는 난수 줄이 차지했기 때문이다.

덮인 줄은 `-b all`로도 돌아오지 않는다. 수집 스크립트로 11:03:31에 `-b all`을 받았을 때 버퍼별 가장 오래된 줄은 아래와 같았고, main은 위 캡처의 flood 직후와 똑같이 16188번째 줄에서 시작했다.

| 버퍼 | 가장 오래된 줄 (UTC) |
|---|---|
| events | 10:44:05.611 snet_event_log, 부팅 직후 |
| radio | 10:44:11.929 RILD, RIL Daemon Started |
| system | 10:56:02.835 PackageManager, 10:56:02에 비운 뒤 첫 줄 |
| kernel | 10:56:02.845 logd, 10:56:02에 비운 뒤 첫 줄 |
| main | 11:02:01.638 SeikaFlood line 16188 |

system과 kernel 행은 링이 밀어낸 경계를 보여 주지 않는다. 둘 다 10:56:02에 비운 시점에서 시작하고, kernel 버퍼는 부팅 때 풀어서 354 KiB가 있었는데 이때는 70줄뿐이었다. `-b` 없이 친 `logcat -c`는 기본 버퍼(main, system, crash, kernel)만 비우니, events와 radio에는 부팅 직후 줄이 그대로 남아 있었다.

### 덮이기 전에 늘려 두기

재현 전에 버퍼를 키우면 된다. `logcat -G`는 root 없이 shell 권한으로 동작했고, 속성으로 저장되지 않아 재부팅하면 원래대로 돌아간다. [LogSize.h](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogSize.h#23)에 기본 256 KiB, 최소 64 KiB, 최대 256 MiB가 정해져 있다.

```text
$ adb shell id -un
shell
$ adb logcat -b main -G 2M
exit=0
$ adb logcat -g -b main
main: ring buffer is 2 MiB (233 KiB consumed, 571 KiB readable), max entry is 5120 B, max payload is 4068 B
$ adb shell getprop persist.logd.size

$ adb logcat -b main -G 256K
```

16 MiB로 키운 뒤 같은 20000줄 flood를 돌리자 이번에는 토큰 줄이 살아남았다.

```text
$ adb logcat -b main -G 16M
$ adb shell am start -S -W -n io.seika.evidence/.MainActivity | grep Status
Status: ok
$ adb logcat -d -s SeikaAuth | grep -c access_token
1
$ adb shell am start -S -W -n io.seika.evidence/.MainActivity --es mode flood --ei n 20000 | grep Status
Status: ok
$ adb logcat -d -s SeikaAuth | grep -c access_token
1
$ adb logcat -g -b main
main: ring buffer is 16 MiB (4 MiB consumed, 2 MiB readable), max entry is 5120 B, max payload is 4068 B
$ adb logcat -b main -G 256K
```

16 MiB일 때 consumed(4 MiB)가 readable(2 MiB)보다 크게 찍힌 것도 앞의 `PruneSize()` 계산으로 설명된다. 청크 하나는 버퍼 크기의 4분의 1([SerializedLogBuffer.h](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/SerializedLogBuffer.h#40)의 `kChunkSizeDivisor = 4`)이라 16 MiB 버퍼에서는 4 MiB다. 아직 쓰고 있는 이 청크가 할당된 4 MiB 그대로 consumed에 들어가는데, 버퍼에 든 로그는 다 풀어도 2 MiB였다.

userdebug 이미지에는 kernel 버퍼가 따로 있고, `-b` 없이 logcat을 실행하면 main, system, crash, kernel을 읽는다. `-b default`는 main, system, crash만이다([logcat.cpp 817행](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logcat/logcat.cpp#817), [725행](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logcat/logcat.cpp#725)). API 26 이미지에서는 기본 출력에 kernel 버퍼가 없었고 `-g`도 `main: ring buffer is 256Kb (243Kb consumed), max entry is 5120b, max payload is 4068b`처럼 readable 항목 없이 찍혔다.

### events 버퍼에 남는 실행 이력

main이 flood로 두 번 갈리고 한 번 비워진 뒤에도 events 버퍼는 앱의 첫 실행을 들고 있었다. 버퍼마다 들어오는 양이 달라서 수명이 다르고, 앞에서 본 대로 `-b` 없는 `logcat -c`도 events는 건드리지 않는다.

```text
$ adb logcat -d -b events | grep io.seika.evidence | grep -E "am_proc_start|am_kill|am_uid_stopped|wm_on_resume_called|am_proc_died" | head -8
10-14 10:48:56.668   515   550 I am_proc_start: [0,5704,10180,io.seika.evidence,next-top-activity,{io.seika.evidence/io.seika.evidence.MainActivity}]
10-14 10:48:57.169  5704  5704 I wm_on_resume_called: [69814231,io.seika.evidence.MainActivity,RESUME_ACTIVITY]
10-14 10:49:27.511   515   549 I am_kill : [0,5704,io.seika.evidence,0,stop io.seika.evidence due to installPackageLI]
10-14 10:49:36.298   515   550 I am_proc_start: [0,5888,10180,io.seika.evidence,next-top-activity,{io.seika.evidence/io.seika.evidence.MainActivity}]
10-14 10:49:39.355  5888  5888 I wm_on_resume_called: [55611155,io.seika.evidence.MainActivity,RESUME_ACTIVITY]
10-14 10:50:17.423   515   570 I am_kill : [0,5888,io.seika.evidence,0,permission grant or revoke changed gids]
...
```

`am_proc_start`에는 PID, UID, 패키지, 시작 이유가, `am_kill`에는 죽은 이유가 남는다. 10:50:17의 `permission grant or revoke changed gids`는 앞에서 `pm grant ... READ_LOGS`를 했을 때 보조 그룹이 바뀌면서 실행 중이던 앱이 죽은 기록이다. main이 이미 갈린 뒤에 사고를 재구성한다면 events부터 본다. 토큰 같은 앱 메시지는 main에 남지만, 언제 어떤 UID로 떴고 왜 죽었는지는 events에 남기 때문이다.

## READ_LOGS 앱이 읽은 남의 로그

logcat을 "토큰이 새는 공유 채널"이라고 부르기 전에 누가 실제로 남의 로그를 읽는지 확인했다. 앱 안에서 logcat을 exec해 받은 줄 수와 UID 목록을 세는 모드를 넣었다.

```java
            String[] cmd = buffer == null
                    ? new String[]{"logcat", "-d", "-v", "threadtime", "-v", "uid"}
                    : new String[]{"logcat", "-d", "-b", buffer, "-v", "threadtime", "-v", "uid"};
            Process p = Runtime.getRuntime().exec(cmd);
```

API 33에서 READ_LOGS 없이 돌리면 자기 UID 줄만 받는다. `pids=4`는 같은 UID로 앞서 떴던 프로세스들까지 센 값이다.

```text
10-14 10:52:35.251  6277  6315 I SeikaReader: readlogs: lines=3219 uids=[10180] pids=4 myPid=6277 took=407ms
```

`pm grant`로 READ_LOGS를 준 뒤 같은 모드를 돌리자 앱의 logcat 프로세스가 멈추고 시스템 대화상자가 떴다. 그때 최상위 액티비티는 `com.android.internal.app.LogAccessDialogActivity`였다.

![Android 13 에뮬레이터에서 Evidence Lab 앱(뒤 화면에 reading logs...) 위에 뜬 시스템 대화상자. 제목 Allow Evidence Lab to access all device logs?, 거부해도 자기 로그는 읽을 수 있다는 본문, Allow one-time access 와 Don’t allow 버튼이 보인다](/assets/img/android-mastery/p1c02/06-logaccess-dialog.png)

"Don’t allow"를 누른 다음 몇 번 더 실행하면서 결과를 모았다.

```text
10-14 10:53:19.070  6346  6369 I SeikaReader: readlogs: lines=3247 uids=[10180] pids=5 myPid=6346 took=30496ms
10-14 10:53:30.576  6474  6496 I SeikaReader: readlogs: lines=3274 uids=[10180] pids=6 myPid=6474 took=214ms
10-14 10:53:58.319  6544  6565 I SeikaReader: readlogs: lines=2794 uids=[10180] pids=7 myPid=6544 took=162ms
10-14 10:54:33.848  6616  6639 I SeikaReader: readlogs: lines=16566 uids=[1000, 1002, 10085, 10108, 10111, 10112, 10114, 10117, 10119, 10120, 10122, 10135, 10137, 10138, 10152, 10157, 10161, 10169, 1017, 10173, 10180, 1041, 1073, logd, media, radio, root, shell, wifi] pids=58 myPid=6616 took=9651ms
```

첫 줄이 거부한 결과다. 30.5초는 내가 버튼을 누를 때까지 logcat이 기다린 시간이고, 받은 건 자기 UID 줄뿐이다. 약 12초 뒤와 39초 뒤에 다시 실행했을 때는 대화상자가 뜨지 않고 곧바로 거부된 결과가 나왔다. 60초가 지나고 실행하자 대화상자가 다시 떴고, 이번에 "Allow one-time access"를 누르자 29개 UID, 58개 PID의 줄 16566개가 들어왔다.

결정이 60초 동안 캐시되는 건 [LogcatManagerService.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-qpr3-release/services/core/java/com/android/server/logcat/LogcatManagerService.java#78)의 `STATUS_EXPIRATION_TIMEOUT_MILLIS = 60 * 1000` 때문이다. 이 파일을 보면 대화상자는 요청한 앱이 포그라운드(`PROCESS_STATE_TOP`)일 때만 뜨고, 아니면 묻지 않고 거부한다. 대화상자를 내버려 두면 debuggable 빌드에서 70초 뒤 자동으로 거부된다는 것도 이 파일 [68행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-qpr3-release/services/core/java/com/android/server/logcat/LogcatManagerService.java#68)에 있다. 이 두 경로는 소스로만 확인했고 돌려 보지는 않았다.

```java
    private boolean shouldShowConfirmationDialog(LogAccessClient client) {
        // If the process is foreground, show a dialog for user consent
        final int procState = mActivityManagerInternal.getUidProcessState(client.mUid);
        return procState == ActivityManager.PROCESS_STATE_TOP;
    }
```

동의를 물을지 말지는 logd가 먼저 가른다. [LogReader.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogReader.cpp#253)의 조건이다.

```cpp
    bool only_read_event_logs = (logMask ^ (1 << LOG_ID_EVENTS)) == 0;

    // The logd access will be granted when any of the following three
    // conditions is satisfied:
    // 1. the client (native processes) is exempted from user consent check.
    // 2. the client doesn't have log credentials and so can only access its own log data anyway
    // 3. the client (for EventLog API) only wants to access the event log.
    if (clientIsExemptedFromUserConsent(cli) || !clientHasLogCredentials(cli) ||
        only_read_event_logs) {
        reader_list_->AddAndRunThread(std::move(entry));
```

면제 대상은 UID가 10000 미만인 클라이언트이고([LogPermissions.cpp](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogPermissions.cpp#186)), 로그 자격은 log 보조 그룹(AID_LOG, 1007)으로 판단한다([LogPermissions.cpp 137행](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release/logd/LogPermissions.cpp#137)). `adb shell`의 `id`에는 `uid=2000(shell)`과 `1007(log)`가 같이 찍히니 adb는 동의 없이 전부 읽는다.

세 번째 조건이 눈에 걸렸다. events 버퍼만 달라고 하면 READ_LOGS 앱도 대화상자 없이 다른 앱 기록을 읽을 수 있을까. 돌려 봤다.

```text
$ adb shell dumpsys package io.seika.evidence | grep 'READ_LOGS: granted'
      android.permission.READ_LOGS: granted=true
$ adb shell am start -S -W -n io.seika.evidence/.MainActivity --es mode readevents | grep Status
Status: ok
$ adb shell dumpsys activity activities | grep topResumedActivity
    topResumedActivity=ActivityRecord{340e8b5 u0 io.seika.evidence/.MainActivity} t293}
$ adb logcat -d -s SeikaReader | tail -1
10-14 11:07:10.690 10585 10606 I SeikaReader: read events: lines=4205 uids=[1000, 1002, 10070, 10085, 10111, 10112, 10113, 10115, 10117, 10119, 10120, 10122, 10124, 10127, 10142, 10152, 10157, 1017, 10180, 10181, 10182, 10184, 1067, 1068, 1073, lmkd, logd, radio, root, u0_i0, u0_i1, u0_i2, u0_i3, u0_i4, u0_i5] pids=70 myPid=10585 took=418ms
$ adb shell pm revoke io.seika.evidence android.permission.READ_LOGS
$ adb shell am start -S -W -n io.seika.evidence/.MainActivity --es mode readevents | grep Status
Status: ok
$ adb logcat -d -s SeikaReader | tail -1
10-14 11:07:15.592 10638 10659 I SeikaReader: read events: lines=7 uids=[10184] pids=2 myPid=10638 took=14ms
```

대화상자 없이 35개 UID의 events 4205줄이 들어왔고, 최상위 액티비티는 앱 자신 그대로였다. 앞에서 본 `am_proc_start`, `am_kill`처럼 다른 앱이 언제 떴고 왜 죽었는지가 이 버퍼에 있다. Google 도움말 [Manage your device logs](https://support.google.com/android/answer/12986432)도 거부한 앱이 event log 같은 일부 로그에는 여전히 접근할 수 있다고 적고 있다.

API 26 이미지에서 이 앱을 `-g`로 깔고 돌렸을 때는 대화상자 없이 전체 로그를 받았다(4147줄, 46개 UID). READ_LOGS를 회수하자 자기 줄 18개만 남았다.

```text
10-14 11:09:59.183  3668  3686 I SeikaReader: readlogs: lines=4147 uids=[1000, 10010, 10013, ... 1058, 39999, logd, mdnsr, media, radio, root, u0_a0, u0_a2, u0_a4, u0_a5, u0_a6, u0_a8, wifi] pids=102 myPid=3668 took=961ms
```

이번에 남의 로그를 받아 간 쪽은 adb 셸(과 거기서 뽑은 bugreport), 사용자가 허락한 READ_LOGS 앱이었고, events 버퍼는 허락 없이도 READ_LOGS 앱에 열렸다. READ_LOGS가 없는 일반 앱은 API 26과 33 둘 다 자기 UID 줄만 받았다.

## /data/data와 run-as

앱 사설 저장소는 그 앱 UID의 것이다. adbd를 `adb unroot`로 shell에 내린 상태에서 시작했다.

```text
$ adb shell id
uid=2000(shell) gid=2000(shell) groups=2000(shell),1004(input),1007(log),1011(adb),... context=u:r:shell:s0
$ adb shell ls /data/data/io.seika.evidence
ls: /data/data/io.seika.evidence: Permission denied
exit=1
$ adb shell run-as io.seika.evidence id
uid=10180(u0_a180) gid=10180(u0_a180) groups=10180(u0_a180),1004(input),1007(log),1011(adb),...,50180(all_a180) context=u:r:runas_app:s0:c180,c256,c512,c768
$ adb shell run-as io.seika.evidence ls -l shared_prefs files
files:
total 8
-rw-rw---- 1 u0_a180 u0_a180 97 2026-10-14 10:51 session.json

shared_prefs:
total 8
-rw-rw---- 1 u0_a180 u0_a180 220 2026-10-14 10:48 auth.xml
```

run-as는 앱 UID로 바뀌면서 SELinux 도메인도 `runas_app`으로, MLS 카테고리도 앱 데이터와 같은 `c180,c256,c512,c768`로 맞춘다. 그래서 사설 디렉터리가 열린다. 파일을 호스트로 가져올 때 `adb pull`은 shell 권한으로 경로를 열다가 실패하므로 `adb exec-out`으로 run-as의 표준출력을 받는다. exec-out은 바이트를 가공하지 않아 바이너리 파일도 깨지지 않는다.

```text
$ adb pull /data/data/io.seika.evidence/shared_prefs/auth.xml
adb: error: failed to stat remote object '/data/data/io.seika.evidence/shared_prefs/auth.xml': Permission denied
exit=1
$ adb exec-out run-as io.seika.evidence cat files/session.json > session.json
{"user":"demo","token":"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzZWlrYS1kZW1vIn0.FAKE_SIG_ONLY_FOR_LAB"}
```

마지막 줄은 그렇게 받아 온 `session.json`의 내용이다.

run-as가 거절하는 메시지는 `package not debuggable` 말고도 있었다.

```text
$ adb shell run-as com.android.settings id
run-as: package not an application: com.android.settings
exit=1
$ adb shell run-as io.seika.nothere id
run-as: unknown package: io.seika.nothere
exit=1
$ adb shell run-as com.android.camera2 id
run-as: package not debuggable: com.android.camera2
exit=1
```

이 앱을 비-debuggable 빌드로 덮어 깔자 `run-as: package not debuggable: io.seika.evidence`가 나왔다. 검사 순서는 [run-as.cpp](https://android.googlesource.com/platform/system/core/+/refs/heads/android13-release/run-as/run-as.cpp#173) 그대로다. 호출자가 shell이나 root인지 보고, `/data/system/packages.list`에서 패키지를 찾고, UID가 앱 범위인지, debuggable인지를 차례로 따진다.

```c
  if (info.uid == 0) {
    error(1, 0, "unknown package: %s", pkgname);
  }
  ...
  // Reject system packages.
  if (userAppId < AID_APP) {
    error(1, 0, "package not an application: %s", pkgname);
  }

  // Reject any non-debuggable package.
  if (!info.debuggable) {
    error(1, 0, "package not debuggable: %s", pkgname);
  }
```

run-as가 읽는 그 파일을 root로 열어 봤다(이때는 비-debuggable 빌드가 깔려 있었다).

```text
$ adb root
(restarting adbd as root)
$ adb shell id -Z
u:r:su:s0
$ adb shell ls -lZd /data/data/io.seika.evidence
drwx------ 6 u0_a182 u0_a182 u:object_r:app_data_file:s0:c182,c256,c512,c768  4096 2026-10-14 11:00 /data/data/io.seika.evidence
$ adb shell grep io.seika.evidence /data/system/packages.list
io.seika.evidence 10182 0 /data/user/0/io.seika.evidence default:targetSdkVersion=33 3003,1007 0 1 1 @null
$ adb pull /data/data/io.seika.evidence/shared_prefs/auth.xml raw/auth-root.xml
/data/data/io.seika.evidence/shared_prefs/auth.xml: 1 file pulled, 0 skipped. 0.1 MB/s (220 bytes in 0.002s)
```

[packagelistparser.cpp](https://android.googlesource.com/platform/system/core/+/refs/heads/android13-release/libpackagelistparser/packagelistparser.cpp#72)의 필드 순서(이름, UID, debuggable, 데이터 경로, seinfo, gids, profileable, 버전)대로 읽으면 세 번째 `0`이 debuggable 여부이고, `3003,1007`은 inet과 log 보조 그룹이다. READ_LOGS를 받은 뒤라 1007이 붙어 있다. 이 세션에서 본 `/data/data`와 `/data/user/0`은 둘 다 `drwxrwx--x system system`이었다. 그래서 shell이 목록은 못 봐도 경로를 지나갈 수는 있다. 실제로 막는 건 패키지 디렉터리의 `drwx------`와 MLS 카테고리다. root는 둘 다 넘어서 비-debuggable 앱의 평문 토큰도 그대로 가져왔다.

user 빌드(google_apis_playstore 이미지)에도 실험 앱의 debuggable 빌드를 깔았다.

![user 빌드 에뮬레이터에서 getprop ro.build.type 이 user, adb root 가 adbd cannot run as root in production builds, shell 의 id 가 shell 과 u:r:shell:s0, ls /data/data/io.seika.evidence 가 Permission denied, run-as 로는 u0_a174 와 u:r:runas_app:s0:c174,c256,c512,c768 이 되어 shared_prefs/auth.xml 의 access_token 을 읽고, run-as com.android.chrome ls 는 package not debuggable 인 터미널](/assets/img/android-mastery/p1c02/04-user-build-runas.png)

`adb root`는 거부됐다([restart_service.cpp](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/android13-release/daemon/restart_service.cpp#36)가 `__android_log_is_debuggable()`로 막는다). 그런데 이때 종료 코드가 0이었다. 스크립트에서 `adb root` 성공 여부를 종료 코드로 판단하면 user 빌드에서 root인 줄 알고 다음 단계로 넘어간다. `adb shell id -u`로 다시 확인하는 게 맞다. `su`도 없었다(`/system/bin/sh: su: inaccessible or not found`). 그래도 debuggable 앱이면 run-as로 사설 저장소를 읽을 수 있었다.

## am과 content로 컴포넌트를 두드릴 때

exported 컴포넌트를 셸에서 건드리는 일도 증적 수집에 들어간다. 여기서는 명령의 결과 문자열을 믿으면 안 됐다.

```text
$ adb shell am force-stop io.seika.evidence
$ adb shell dumpsys package io.seika.evidence | grep -o 'stopped=[a-z]*'
stopped=true
$ adb shell am broadcast -a io.seika.evidence.PING --es msg implicit
Broadcasting: Intent { act=io.seika.evidence.PING flg=0x400000 (has extras) }
Broadcast completed: result=0
$ adb shell am broadcast -a io.seika.evidence.PING -p io.seika.evidence --es msg explicit-pkg
Broadcasting: Intent { act=io.seika.evidence.PING flg=0x400000 pkg=io.seika.evidence (has extras) }
Broadcast completed: result=0
$ adb shell am broadcast -a io.seika.evidence.PING -p io.seika.evidence --include-stopped-packages --es msg incl-stopped
Broadcasting: Intent { act=io.seika.evidence.PING flg=0x400020 pkg=io.seika.evidence (has extras) }
Broadcast completed: result=0
$ adb shell am broadcast -a io.seika.evidence.PING --es msg implicit-after-start
Broadcasting: Intent { act=io.seika.evidence.PING flg=0x400000 (has extras) }
Broadcast completed: result=0
$ adb shell am broadcast -a io.seika.evidence.PING -p io.seika.evidence --es msg explicit-after-start
Broadcasting: Intent { act=io.seika.evidence.PING flg=0x400000 pkg=io.seika.evidence (has extras) }
Broadcast completed: result=0
$ adb logcat -d -s SeikaPing
--------- beginning of main
10-14 10:54:57.677  6734  6734 I SeikaPing: onReceive action=io.seika.evidence.PING msg=incl-stopped
10-14 10:54:59.885  6734  6734 I SeikaPing: onReceive action=io.seika.evidence.PING msg=explicit-after-start
$ adb logcat -d | grep -E 'Background execution not allowed' | tail -3
10-14 10:54:59.461   515   549 W BroadcastQueue: Background execution not allowed: receiving Intent { act=android.intent.action.DROPBOX_ENTRY_ADDED flg=0x10 (has extras) } to com.google.android.gms/.stats.service.DropBoxEntryAddedReceiver
10-14 10:54:59.462   515   549 W BroadcastQueue: Background execution not allowed: receiving Intent { act=android.intent.action.DROPBOX_ENTRY_ADDED flg=0x10 (has extras) } to com.google.android.gms/.chimera.GmsIntentOperationService$PersistentTrustedReceiver
10-14 10:54:59.808   515   549 W BroadcastQueue: Background execution not allowed: receiving Intent { act=io.seika.evidence.PING flg=0x400010 (has extras) } to io.seika.evidence/.PingReceiver
```

다섯 번 모두 `result=0`이었지만 수신 측 로그에 찍힌 건 두 번뿐이다. 수신 여부는 리시버 쪽 로그로만 알 수 있었다. `--include-stopped-packages`를 붙인 브로드캐스트가 PID 6734를 띄웠고, 뒤의 두 번은 그 프로세스가 살아 있는 동안 보낸 것이다.

| 상황 | 전달 |
|---|---|
| force-stop 상태, 암시적 | 안 됨 |
| force-stop 상태, `-p` | 안 됨 (stopped 패키지 제외) |
| force-stop 상태, `-p --include-stopped-packages` | 됨 |
| 프로세스가 뜬 뒤, 암시적 | 안 됨 (Background execution not allowed) |
| 프로세스가 뜬 뒤, `-p` | 됨 |

`result=`는 브로드캐스트의 결과 코드를 찍을 뿐이고([ActivityManagerShellCommand.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/am/ActivityManagerShellCommand.java#772)), 전달 여부와는 상관이 없다. `flg=0x400000`은 `FLAG_RECEIVER_FROM_SHELL`, `--include-stopped-packages`가 더한 0x20은 `FLAG_INCLUDE_STOPPED_PACKAGES`다([Intent.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/content/Intent.java#6609)). 매니페스트 리시버로 가는 암시적 브로드캐스트를 막는 건 Android 8의 [백그라운드 실행 제한](https://developer.android.com/about/versions/oreo/background#broadcasts)이고, 경고는 [BroadcastQueue.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/am/BroadcastQueue.java#1703)가 찍는다.

서비스와 provider는 이렇게 나왔다.

```text
$ adb shell am force-stop io.seika.evidence
$ adb shell am start-service -n io.seika.evidence/.SyncService --es target bg
Starting service: Intent { cmp=io.seika.evidence/.SyncService (has extras) }
Error: app is in background uid null
exit=255
$ adb shell content query --uri content://io.seika.evidence.notes/notes
Row: 0 _id=1, title=memo, body=wifi password: demo-not-real
Row: 1 _id=2, title=todo, body=rotate api key
$ adb shell am start-service -n io.seika.evidence/.SyncService --es target after-provider
Starting service: Intent { cmp=io.seika.evidence/.SyncService (has extras) }
exit=0
$ adb shell am start -W -n io.seika.evidence/.MainActivity
Status: ok
$ adb shell am start-service -n io.seika.evidence/.SyncService --es target fg
Starting service: Intent { cmp=io.seika.evidence/.SyncService (has extras) }
exit=0
$ adb logcat -d -s SeikaSync SeikaNotes
--------- beginning of main
10-14 10:55:11.951  6803  6818 I SeikaNotes: query uri=content://io.seika.evidence.notes/notes callingPkg=com.android.shell
10-14 10:55:12.850  6803  6803 I SeikaSync: onStartCommand target=after-provider
10-14 10:55:13.442  6803  6803 I SeikaSync: onStartCommand target=fg
```

멈춘 앱에 `am start-service`를 보내면 [ActiveServices.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/am/ActiveServices.java#816)의 백그라운드 서비스 제한에 걸린다. 그런데 `content query`로 provider를 한 번 부르자 프로세스가 떴고, 바로 다음 start-service는 통과했다. 앱이 아직 idle로 분류되기 전이라 그런 것으로 보인다([공식 문서](https://developer.android.com/about/versions/oreo/background#services)가 말하는 몇 분의 유예). provider는 호출자를 `com.android.shell`로 기록했다. 셸에서 컴포넌트를 두드리면 앱의 프로세스 상태가 바뀌고, 그 변화가 다음 명령의 결과를 바꾼다.

## adb backup과 bugreport

`adb backup`은 최신 앱에서 사실상 막혀 있다고 알려져 있다. debuggable 빌드와 비-debuggable 빌드로 각각 받아 봤다. 기기 확인 화면에서는 비밀번호 없이 "Back up my data"를 눌렀고, 비밀번호를 넣는 암호화 백업은 이번에 하지 않았다.

```text
$ adb backup -f raw/backup-debuggable.ab io.seika.evidence
WARNING: adb backup is deprecated and may be removed in a future release
Now unlock your device and confirm the backup operation...
$ python abls.py backup-debuggable.ab
header: ['ANDROID BACKUP', '5', '1', 'none']
  1519 apps/io.seika.evidence/_manifest
    97 apps/io.seika.evidence/f/session.json
   220 apps/io.seika.evidence/sp/auth.xml
entries: 3
$ adb backup -f raw/backup-release.ab io.seika.evidence
WARNING: adb backup is deprecated and may be removed in a future release
Now unlock your device and confirm the backup operation...
$ python abls.py backup-release.ab
header: ['ANDROID BACKUP', '5', '1', 'none']
entries: 0
```

`abls.py`는 암호화되지 않은 `.ab` 파일의 tar 항목을 나열하려고 만든 작은 스크립트다. 비-debuggable 쪽은 47바이트짜리 빈 백업이었고, logcat에는 `BackupManagerService: Package io.seika.evidence is not eligible for backup, removing.`이 남았다. 매니페스트의 `android:allowBackup="true"`는 그대로였다. targetSdk 31 이상이면 일반 앱은 debuggable일 때만 adb backup 대상이 된다([BackupEligibilityRules.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/backup/java/com/android/server/backup/utils/BackupEligibilityRules.java#70), Android 12 [동작 변경](https://developer.android.com/about/versions/12/behavior-changes-12)의 ADB backup restriction). targetSdk 30 이하라면 이 제한이 꺼져 있어 `allowBackup` 값만 본다([BackupEligibilityRules.java 176행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/backup/java/com/android/server/backup/utils/BackupEligibilityRules.java#176)).

```java
    @ChangeId
    @EnabledSince(targetSdkVersion = Build.VERSION_CODES.S)
    static final long RESTRICT_ADB_BACKUP = 171032338L;
    ...
                } else {
                    // All other apps can use adb backup only when running in debuggable mode.
                    return isDebuggable;
                }
```

`adb bugreport`는 50초 걸려 5.7 MB zip을 만들었다. 안에 항목 299개, 본문 텍스트 35.7 MB, `------ ... ------` 섹션 938개가 있었다. logcat은 `SYSTEM LOG (logcat -v threadtime -v printable -v uid -d *:v)`, `EVENT LOG`, `RADIO LOG`, `KERNEL LOG`로, dumpsys는 `DUMPSYS CRITICAL`, `APP ACTIVITIES` 같은 섹션으로 들어 있다. 앱의 토큰 줄은 이미 flood로 밀려난 뒤라 bugreport에도 없었다. 본문의 `access_token` 한 번은 GMS 기능 이름 `get_relay_access_token`이었다.

## 휘발성 높은 것부터 받는 수집 스크립트

위에서 본 것들을 순서로 묶었다. 가장 빨리 사라지는 logcat을 먼저 받고, 명령마다 호스트와 기기의 UTC 시각과 정확한 명령줄을 남기고, 끝에 해시를 뜬다. 휘발성 순서라는 원칙 자체는 [RFC 3227 2.1절](https://www.rfc-editor.org/rfc/rfc3227#section-2.1)에서 왔다.

```bash
#!/usr/bin/env bash
# Collect app evidence from one device, most volatile first, with a timestamped command log and hashes.
#   ANDROID_SERIAL=emulator-5600 ./collect.sh io.seika.evidence evidence-run
set -u
pkg=$1; out=$2; mkdir -p "$out"; log=$out/collection.log
run() {  # run FILE CMD...: record host/device UTC time and the exact command, save output
  local f=$1; shift
  printf '%s\thost=%s\tdevice=%s\t%s\n' "$f" "$(date -u +%FT%TZ)" \
    "$(adb shell date -u +%FT%TZ | tr -d '\r')" "$*" >> "$log"
  "$@" > "$out/$f" 2>&1
}
run logcat-all.txt     adb logcat -d -b all -v threadtime -v uid -v year
run appops.txt         adb shell dumpsys appops --package "$pkg"
run usagestats.txt     adb shell dumpsys usagestats "$pkg"
run dumpsys-package.txt adb shell dumpsys package "$pkg"
run pm-path.txt        adb shell pm path "$pkg"
run build.txt          adb shell getprop ro.build.fingerprint
apk=$(tr -d '\r' < "$out/pm-path.txt" | sed -n 's/^package://p' | head -1)
run base.apk.pull.txt  adb pull "$apk" "$out/base.apk"
(cd "$out" && sha256sum -- * > SHA256SUMS)
```

실행 결과의 기록 파일이다.

```text
$ ANDROID_SERIAL=emulator-5600 ./collect.sh io.seika.evidence evidence-run
$ cat evidence-run/collection.log
logcat-all.txt	host=2026-10-14T11:03:32Z	device=2026-10-14T11:03:31Z	adb logcat -d -b all -v threadtime -v uid -v year
appops.txt	host=2026-10-14T11:03:33Z	device=2026-10-14T11:03:32Z	adb shell dumpsys appops --package io.seika.evidence
usagestats.txt	host=2026-10-14T11:03:33Z	device=2026-10-14T11:03:32Z	adb shell dumpsys usagestats io.seika.evidence
dumpsys-package.txt	host=2026-10-14T11:03:33Z	device=2026-10-14T11:03:32Z	adb shell dumpsys package io.seika.evidence
pm-path.txt	host=2026-10-14T11:03:33Z	device=2026-10-14T11:03:32Z	adb shell pm path io.seika.evidence
build.txt	host=2026-10-14T11:03:33Z	device=2026-10-14T11:03:32Z	adb shell getprop ro.build.fingerprint
base.apk.pull.txt	host=2026-10-14T11:03:34Z	device=2026-10-14T11:03:33Z	adb pull /data/app/~~AvcroojZefwV_tQdt-aXew==/io.seika.evidence-KFLOHzj74rfB8Fex7PcqNg==/base.apk evidence-run/base.apk
$ cat evidence-run/SHA256SUMS
02866974d39de6c4dd0728f57adb0e05de26aa4f7d0d383b79eca93fd33e60de *appops.txt
51f481db4fa1edd4b475f5caf203c876e24e65dbe372ca887d88184c95c89885 *base.apk
...
f8395b0127d82c5f6ffb7500a942a979767c7f8404e896ae75812b44a7275897 *logcat-all.txt
```

기기 시계가 호스트보다 1초쯤 늦다는 사실이 기록에 그대로 남는다. 나중에 호스트 쪽 로그(프록시, 서버)와 시각을 맞출 때 이 차이를 보정한다. `-v year`로 연도를, `-v uid`로 줄마다 UID를 찍게 해 두면 앞에서 본 재설치 UID 변화도 로그 안에서 구분된다. 권한을 바꾸거나 컴포넌트를 두드리는 명령은 이 수집이 끝난 뒤에 한다. 앞에서 봤듯 둘 다 프로세스를 죽이거나 띄운다.

## 고친 빌드를 다시 확인하는 순서

로그부터. 토큰이나 개인정보를 인자로 받는 로그 호출은 코드에서 지운다. 확인은 릴리스 APK를 깔고 같은 동작을 시킨 뒤 해당 태그의 로그를 읽는 것이다. Android 13의 동의 대화상자가 READ_LOGS를 받은 앱의 접근은 줄여 주지만, adb와 bugreport와 events 버퍼는 그 바깥에 있었다.

저장소는 debuggable 플래그가 빠지면 run-as와 adb backup 경로가 닫혔다. root로는 비-debuggable 앱의 `auth.xml`도 그대로 나왔으니 평문 저장은 여전히 문제다. 토큰을 Keystore 키로 감싸는 방법은 [Keystore 글](/posts/android-lab-p1c14-keystore-biometricprompt/)과 [보안 저장소·백업(C44)](/posts/android-concept-atlas-c44-secure-storage-backup/)에서 이어 간다. 클라우드 백업이나 기기 간 이전 경로는 이번에 재지 않았다.

exported provider는 셸에서 `content query` 한 줄로 메모를 내줬다. 권한 없이 export된 provider를 어떻게 막는지는 [ContentProvider 글](/posts/android-lab-p1c18-contentprovider-fileprovider/)에서 다룬다.

비-debuggable 빌드로 덮어 깐 직후 돌린 확인이 그대로 회귀 검사 순서가 된다. 이 출력은 앞에서 말한 10:56:02의 버퍼 비우기 바로 뒤라 SeikaAuth 줄이 이 설치본 것 하나만 나왔다. 비우지 않았다면 직전 debuggable 빌드가 찍은 토큰 줄이 섞였을 테니, 따라 할 때는 설치 전에 `adb logcat -c`부터 친다.

```text
$ adb install -r out/evidence-release.apk
Performing Streamed Install
Success
$ adb shell dumpsys package io.seika.evidence | grep pkgFlags
    pkgFlags=[ HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP ]
$ adb shell run-as io.seika.evidence ls
run-as: package not debuggable: io.seika.evidence
exit=1
$ adb shell am start -W -n io.seika.evidence/.MainActivity
Status: ok
$ adb logcat -d -s SeikaAuth
--------- beginning of main
10-14 10:56:03.815  7103  7103 D SeikaAuth: login ok user=demo access_token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzZWlrYS1kZW1vIn0.FAKE_SIG_ONLY_FOR_LAB
```

`DEBUGGABLE`이 빠졌고 run-as는 거절됐으니 앞의 두 검사는 통과다. 마지막 logcat 검사에서 비-debuggable 프로세스(PID 7103)가 토큰을 찍었으니 이 앱은 여기서 떨어진다. 로그 호출을 지운 빌드라면 이 자리에 아무 줄도 나오지 않아야 한다.

참고 자료: [adb](https://developer.android.com/tools/adb) · [logcat](https://developer.android.com/tools/logcat) · [platform/system/logging (android13-release)](https://android.googlesource.com/platform/system/logging/+/refs/heads/android13-release) · [Manage your device logs](https://support.google.com/android/answer/12986432) · [UID 샌드박스(C09)](/posts/android-concept-atlas-c09-uid-sandbox/) · [permission·AppOps(C10)](/posts/android-concept-atlas-c10-permissions-appops/) · [system_server와 dumpsys(C19)](/posts/android-concept-atlas-c19-servicemanager-systemserver/)

*다음 글: [apksigner·aapt2·bundletool로 하는 APK triage](/posts/android-lab-p1c03-apk-triage/)*
