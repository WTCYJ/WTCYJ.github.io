---
layout: post
title: "Service·Messenger·AIDL 실습 — 호출자 UID를 읽는 자리"
date: 2026-11-01 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Service, AIDL, Messenger, Binder, getCallingUid, RaceCondition]
excerpt: "Android 13 에뮬레이터에서 다른 키로 서명한 앱이 Messenger 서비스의 관리 기능을 실행했다. handleMessage에서 읽은 getCallingUid()가 서비스 자신의 UID였기 때문이고, msg.sendingUid로 바꾸자 막혔으며, 검사와 기록이 떨어진 쿠폰 메서드는 동시 호출을 매번 전부 통과시켰다."
---

[브로드캐스트](/posts/android-lab-p1c16-broadcastreceiver-ordered-broadcast/)는 보낸 쪽이 누구인지 리시버가 알기 어려운 채널이었다. 서비스는 사정이 다르다. 바인드한 앱과 서비스 사이에는 Binder 연결이 생기고, 트랜잭션마다 커널이 보낸 프로세스의 UID를 찍어 넘긴다. 서비스는 그 값을 `Binder.getCallingUid()`로 읽어 "이 호출자에게 관리 기능을 열어 줘도 되나"를 판단하면 된다. 그런데 그 값은 언제, 어느 스레드에서 읽느냐에 따라 전혀 다른 숫자가 된다. Messenger를 쓰는 서비스에서 이걸 잘못 읽으면 서명 검사가 공격자 앱에게 "같은 서명"이라고 답한다.

개념 쪽 배경은 Atlas의 [Binder 드라이버(C17)](/posts/android-concept-atlas-c17-binder-driver/), [컴포넌트와 Binder(C21)](/posts/android-concept-atlas-c21-components-binder/), [인증과 인가(C02)](/posts/android-concept-atlas-c02-authn-authz/)에 있고, 호출자 UID가 커널에서 찍히는 과정과 `clearCallingIdentity()`는 [Binder 호출자 신원과 confused deputy(C22)](/posts/android-concept-atlas-c22-binder-caller-identity-confused-deputy/)에서 다뤘다. 이번에는 그 값을 실제 서비스 코드의 여러 자리에서 찍어 봤다.

실험 기기는 Android 13 에뮬레이터(API 33, x86_64, userdebug, 빌드 TE1A.240213.009, 보안 패치 2024-03-01, SELinux Enforcing) 한 대다. 소스 링크는 frameworks/base·frameworks/native `android-13.0.0_r84` 태그와 커널 `android13-5.15` 브랜치로 건다. 캡처에 나오는 `$S`는 에뮬레이터 시리얼이다.

## 실험에 쓴 서비스 앱과 클라이언트 앱

서비스 쪽 `io.seika.svclab`(targetSdk 33, 디버그 키)은 서비스 세 개를 내놓는다. `AdminAidlService`와 `AdminMessengerService`는 `exported="true"`에 권한이 없고, `GuardedAidlService`는 같은 AIDL 구현을 쓰되 앱이 정의한 signature 권한 `io.seika.svclab.permission.ADMIN`을 요구한다. 앱 자신은 `INTERNET` 권한을 갖는다. 이 권한은 뒤에서 권한 확인 도우미 두 개를 비교하는 데만 쓴다.

```xml
<!-- svclab AndroidManifest.xml 5~18행 -->
    <permission android:name="io.seika.svclab.permission.ADMIN"
        android:protectionLevel="signature" />

    <uses-permission android:name="android.permission.INTERNET" />

    <application android:label="SvcLab" android:allowBackup="false">
        <service android:name="io.seika.svclab.AdminAidlService"
            android:exported="true" />
        <service android:name="io.seika.svclab.GuardedAidlService"
            android:exported="true"
            android:permission="io.seika.svclab.permission.ADMIN" />
        <service android:name="io.seika.svclab.AdminMessengerService"
            android:exported="true" />
    </application>
```

클라이언트는 같은 코드로 세 벌을 만들었다. `io.seika.svcclient`는 다른 키(공격자 키)로 서명했고 `INTERNET`이 없으며, ADMIN 권한을 요청은 하지만 서명이 달라 받지 못한다. 매니페스트에 `<queries><package android:name="io.seika.svclab"/></queries>`가 있다. `io.seika.svcfriend`는 서비스와 같은 디버그 키로 서명한 정상 클라이언트이고, `io.seika.svcblind`는 svcclient에서 `<queries>`만 뺀 것이다. 클라이언트는 `am start -S -n <패키지>/io.seika.svcclient.Main --es mode <모드>`로 띄우면 모드에 맞는 호출을 하고 결과를 `SVCCLI` 태그로, 서비스는 판단 결과를 `SVCLAB` 태그로 남긴다. 이번 실행에서 받은 UID는 svclab 10179, svcclient 10180, svcfriend 10181, svcblind 10182다.

## AIDL stub은 인터페이스 토큰만 본다

AIDL 인터페이스는 메서드 아홉 개로, 이름만 봐도 구현 방식을 알 수 있게 지었다. `adminNoCheck`는 검사가 없고, `adminTrustPayload`는 인자로 받은 UID를 믿고, `adminChecked`는 바인더 스레드에서 호출자 서명을 비교한다. `adminAfterClear`와 `adminOnExecutor`는 각각 `clearCallingIdentity()` 뒤, 작업 스레드에서 호출자를 읽는다. `redeem`과 `redeemAtomic`은 쿠폰 사용 흉내이고 `ping`은 oneway다.

build-tools의 `aidl`로 Java stub을 만들어 `onTransact`를 grep했다. 캡처는 Windows용 build-tools의 `aidl.exe`를 돌린 것이라 경로 구분자가 `\`다. Linux나 macOS에서는 다음처럼 `/`로 쓴다.

```bash
aidl --lang=java -I apps/svclab/aidl -o gen-demo apps/svclab/aidl/io/seika/svclab/IAdminService.aidl
```

![cat apps/svclab/aidl/io/seika/svclab/IAdminService.aidl 출력에 whoami, adminNoCheck, adminTrustPayload(int claimedUid), adminChecked, adminAfterClear, adminOnExecutor, redeem, redeemAtomic, oneway void ping(String tag) 아홉 메서드. aidl --lang=java -I 'apps\svclab\aidl' -o gen-demo 로 생성한 IAdminService.java를 grep한 결과 87행 data.enforceInterface(descriptor), 95행 case TRANSACTION_whoami 다음 97행 this.whoami()처럼 case마다 바로 this.메서드 호출이 이어지고, 331행 mRemote.transact(Stub.TRANSACTION_ping, _data, null, android.os.IBinder.FLAG_ONEWAY)](/assets/img/android-mastery/p1c17/01-host-aidl-stub.png)

87행 `enforceInterface(descriptor)`는 Parcel 앞머리의 인터페이스 이름이 `io.seika.svclab.IAdminService`와 같은지만 확인한다. 누가 보냈는지는 묻지 않는다. 그다음은 `switch`가 트랜잭션 코드에 맞는 메서드를 곧장 부른다(95~161행). 서비스가 막지 않으면 바인드한 앱은 아홉 개 중 아무 메서드나 원하는 순서로 호출한다. 인가는 메서드마다 따로 넣어야 한다. 331행은 클라이언트 쪽 proxy인데, `oneway`로 선언한 `ping`만 `FLAG_ONEWAY`로 보낸다.

## Messenger의 handleMessage는 트랜잭션이 끝난 뒤에 돈다

Messenger 서비스는 `Handler` 하나를 감싼 `Messenger`의 binder를 `onBind`에서 돌려준다. 클라이언트가 `Messenger.send()`를 부르면 서비스 프로세스의 바인더 스레드에서 다음 코드가 돈다.

![android-13.0.0_r84 Handler.java 910~925행. getIMessenger()가 synchronized(mQueue) 안에서 mMessenger = new MessengerImpl()을 만들어 돌려주고, MessengerImpl extends IMessenger.Stub의 send(Message msg)는 msg.sendingUid = Binder.getCallingUid(); 다음 Handler.this.sendMessage(msg);](/assets/img/android-mastery/p1c17/02-src-a13-messengerimpl.png)

[Handler.java 920~925행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/Handler.java#920)의 `MessengerImpl.send`는 바인더 스레드에서 호출자 UID를 `msg.sendingUid`에 적어 두고 메시지를 큐에 넣는다. 트랜잭션은 거기서 끝난다. `handleMessage`는 나중에 Handler의 Looper 스레드(이 랩에서는 메인 스레드)가 큐에서 꺼내 부르는데, 그 시점의 그 스레드는 어떤 트랜잭션도 처리하고 있지 않다. 그래서 `handleMessage` 안의 `Binder.getCallingUid()`는 호출자 대신 서비스 자신의 UID를 돌려준다.

취약한 처리와 고친 처리는 호출자를 어디서 가져오느냐만 다르다.

```java
// AdminMessengerService.java 68~77행
            case ADMIN_VULN: {
                // (취약) handleMessage는 트랜잭션 밖이라 getCallingUid()가 자기 UID다
                int caller = Binder.getCallingUid();
                return decide("ADMIN_VULN", "Binder.getCallingUid()", caller, msg.sendingUid);
            }
            case ADMIN_SAFE: {
                // (방어) Messenger가 메시지를 받는 순간 기록해 둔 호출자
                int caller = msg.sendingUid;
                return decide("ADMIN_SAFE", "msg.sendingUid", caller, msg.sendingUid);
            }

// AdminMessengerService.java 94~100행
    private String decide(String what, String source, int caller, int sender) {
        int sig = getPackageManager().checkSignatures(caller, Process.myUid());
        String r = sig == PackageManager.SIGNATURE_MATCH ? "EXECUTED" : "DENIED";
        Log.w(TAG, what + " caller from " + source + "=" + caller + " (sender " + sender + ")"
                + " checkSignatures=" + sig + " -> " + r);
        return r;
    }
```

클라이언트는 WHOAMI 메시지에 Bundle로 `uid=1000`을 넣고, `msg.sendingUid`도 일부러 1000으로 채워 보낸다. `sendingUid`는 [Message.java 648행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/Message.java#648)(writeToParcel)에서 Parcel에 그대로 쓰이고 662행(readFromParcel)에서 그대로 읽히는 필드라 보내는 쪽이 값을 정할 수 있다. 공격자 키의 svcclient로 돌렸다. 캡처에서는 `am start`와 `logcat -d` 사이에 3초를 기다렸는데, 막 부팅한 에뮬레이터에서는 첫 실행이 10초 남짓 걸려(다시 돌렸을 때 `Displayed ... +11s30ms`) 3~4초 뒤의 덤프에 SVCLAB 줄이 하나도 없었다. 줄이 비어 있으면 더 기다렸다가 `logcat -d`를 다시 치면 된다.

![adb install로 svclab, svcclient, svcfriend 설치 Success 세 번, pm list packages -U io.seika 결과 svcclient uid:10180, svcfriend uid:10181, svclab uid:10179. am start -S -n io.seika.svcclient/.Main --es mode msgr 후 logcat -d -v tag -s SVCLAB:I SVCCLI:I. AdminMessengerService onBind thread=main getCallingUid=10179, sent WHOAMI (payload uid=1000, msg.sendingUid=1000 set by client), 서비스 쪽 WHOAMI thread=main payloadUid=1000 msg.sendingUid=10180, WHOAMI getCallingUid()=10179 getCallingPid()=4143 myUid=10179 myPid=4143, getCallingUidOrThrow() -> IllegalStateException: Thread is not in a binder transcation, checkCallingPermission(INTERNET)=-1 checkCallingOrSelfPermission(INTERNET)=0, ADMIN_VULN caller from Binder.getCallingUid()=10179 (sender 10180) checkSignatures=0 -> EXECUTED, ADMIN_SAFE caller from msg.sendingUid=10180 (sender 10180) checkSignatures=-3 -> DENIED, 클라이언트 reply what=2 -> EXECUTED, reply what=3 -> DENIED](/assets/img/android-mastery/p1c17/05-device-messenger.png)

`handleMessage` 안에서 읽은 `getCallingUid()`는 10179, `getCallingPid()`는 4143으로 `myUid`·`myPid`와 똑같다. 서비스 앱 자기 자신이다. 이 값으로 `checkSignatures(caller, myUid())`를 하면 자기와 자기를 비교하니 0(`SIGNATURE_MATCH`)이 나오고, 다른 키로 서명한 앱의 ADMIN_VULN 요청이 EXECUTED가 됐다. 같은 키의 정상 클라이언트로 시험했다면 이 결과는 정상 동작과 구별되지 않았을 것이다.

같은 검사를 `msg.sendingUid`로 바꾼 ADMIN_SAFE는 10180을 받아 `checkSignatures=-3`(`SIGNATURE_NO_MATCH`, [PackageManager.java 1222행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/PackageManager.java#1222))으로 DENIED가 됐다. 클라이언트가 1000으로 위조해 보낸 `sendingUid`는 서비스에 도착했을 때 10180으로 바뀌어 있었다. `MessengerImpl.send`가 922행에서 덮어썼기 때문이다. 반면 Bundle에 실은 `payloadUid=1000`은 그대로 왔다.

`sendingUid`를 믿어도 되는 건 그 Message가 Messenger를 거쳐 들어왔을 때뿐이다. 앱 안에서 직접 만든 Message나 다른 경로로 언마샬한 Message에는 기본값 -1이나 누군가 넣은 값이 들어 있다([Message.java 85~90행 주석](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/Message.java#85)). 필드 자체는 API 21에서 공개됐다.

같은 화면의 나머지 두 줄도 이 "트랜잭션 밖" 상태가 만든 결과다. `getCallingUidOrThrow()`는 `IllegalStateException`을 던졌고(메시지 철자 `transcation`은 Android 13 소스 그대로다), `checkCallingPermission(INTERNET)`은 -1, `checkCallingOrSelfPermission(INTERNET)`은 0이었다. svcclient에는 `INTERNET`이 없는데 OrSelf가 허용을 돌려준 것이다.

![android-13.0.0_r84 Binder.java 320~361행. getCallingPid 주석의 Warning: oneway transactions do not receive PID. 와 If the current thread is not currently executing an incoming transaction, then its own PID is returned, getCallingUid 주석의 then its own UID is returned, @hide isDirectlyHandlingTransaction(), getCallingUidOrThrow()가 !isDirectlyHandlingTransaction()이면 IllegalStateException("Thread is not in a binder transcation")을 던지는 코드](/assets/img/android-mastery/p1c17/03-src-a13-binder-calling.png)

[Binder.java 332~340행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/Binder.java#332) 주석대로, 트랜잭션을 처리 중이 아닌 스레드에서는 자기 UID가 나온다. 시스템 서비스라면 그 값이 1000(system)이겠지만 일반 앱에서는 앱 자신의 10xxx UID다. API 29에 들어온 `getCallingUidOrThrow()`([358~361행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/Binder.java#358))는 이 상황에서 조용히 자기 UID를 주는 대신 예외를 던진다. Messenger 핸들러에서 실수로 호출자를 읽는 코드를 잡아내는 데 쓸 만하다.

권한 도우미 두 개의 차이는 [ContextImpl.java 2197~2217행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ContextImpl.java#2197)에 그대로 있다. `checkCallingPermission`은 `getCallingPid()`가 자기 PID와 같으면 무조건 `PERMISSION_DENIED`를 돌려주고, `checkCallingOrSelfPermission`은 지금 보이는 PID·UID를 그대로 검사한다. 트랜잭션 밖에서는 그게 서비스 자신이니 서비스가 가진 권한이 호출자 권한처럼 보인다.

## AIDL 메서드는 바인더 스레드에서만 호출자를 본다

같은 svcclient로 AIDL 서비스를 호출했다.

![am start -S -n io.seika.svcclient/.Main --es mode aidl 후 logcat. AdminAidlService onBind thread=main getCallingUid=10179, whoami thread=binder:4143_1 getCallingUid=10180 getCallingPid=4728 myUid=10179 myPid=4143, checkCallingPermission(INTERNET)=-1 checkCallingOrSelfPermission(INTERNET)=-1, adminNoCheck caller=10180 -> EXECUTED (no check), adminTrustPayload claimedUid=1000 realCaller=10180 -> EXECUTED, adminChecked caller=10180 checkSignatures=-3 -> DENIED와 클라이언트 SecurityException: adminChecked: uid 10180 is not signed like svclab (checkSignatures=-3), adminAfterClear before=10180 afterClear getCallingUid=10179 getCallingUidOrThrow=10179 이어서 checkSignatures=0 -> EXECUTED, adminOnExecutor binderThread getCallingUid=10180, worker thread=pool-2-thread-1 getCallingUid=10179 checkSignatures=0 -> EXECUTED, ping(oneway) tag=oneway thread=binder:4143_2 getCallingUid=10180 getCallingPid=0](/assets/img/android-mastery/p1c17/06-device-aidl.png)

`whoami`는 `binder:4143_1` 스레드에서 돌았고 `getCallingUid=10180`, `getCallingPid=4728`로 클라이언트를 정확히 보여 준다. 여기서는 권한 도우미 둘 다 클라이언트를 검사해 -1/-1이 나왔다. 바인더 스레드에서 트랜잭션을 처리하는 동안에는 [IPCThreadState.cpp 1267~1269행](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r84/libs/binder/IPCThreadState.cpp#1267)이 커널이 넘긴 `sender_pid`·`sender_euid`를 스레드 상태에 넣어 두기 때문이다.

`adminNoCheck`는 검사가 없으니 공격자 앱이 그냥 실행했다. `adminTrustPayload`는 인자로 받은 1000을 믿었다. 로그의 `realCaller=10180`이 보여 주듯 진짜 호출자는 서비스가 언제든 알 수 있었는데도 그렇다. 바인더 스레드에서 서명을 비교한 `adminChecked`만 -3으로 막았고, 서비스가 던진 `SecurityException`은 Parcel을 타고 클라이언트까지 그대로 넘어갔다.

```java
// AdminBinder.java 67~80행
    // (방어) 트랜잭션의 호출자 UID로 서명을 비교한다
    @Override
    public String adminChecked() {
        int caller = Binder.getCallingUid();
        int sig = ctx.getPackageManager().checkSignatures(caller, Process.myUid());
        boolean ok = sig == PackageManager.SIGNATURE_MATCH;
        Log.i(TAG, svc + " adminChecked caller=" + caller + " checkSignatures=" + sig
                + " -> " + (ok ? "EXECUTED" : "DENIED"));
        if (!ok) {
            throw new SecurityException("adminChecked: uid " + caller
                    + " is not signed like svclab (checkSignatures=" + sig + ")");
        }
        return "EXECUTED";
    }
```

AIDL에서도 Messenger와 같은 실수가 나온다. `clearCallingIdentity()` 뒤에 호출자를 읽거나, 작업을 다른 스레드로 넘긴 다음 거기서 읽으면 된다.

```java
// AdminBinder.java 84~95행 (adminAfterClear 앞부분)
    public String adminAfterClear() {
        int before = Binder.getCallingUid(); // 로그 비교용
        long token = Binder.clearCallingIdentity();
        try {
            int caller = Binder.getCallingUid();
            int orThrow = Binder.getCallingUidOrThrow();
            int sig = ctx.getPackageManager().checkSignatures(caller, Process.myUid());
            ...

// AdminBinder.java 103~108행 (adminOnExecutor 앞부분)
    public String adminOnExecutor() {
        final int onBinder = Binder.getCallingUid();
        try {
            return worker.submit(() -> {
                int caller = Binder.getCallingUid();
                int sig = ctx.getPackageManager().checkSignatures(caller, Process.myUid());
```

`adminAfterClear`는 clear 전에는 10180이던 값이 clear 뒤에 10179가 됐고 EXECUTED로 끝났다. [IPCThreadState.cpp 488~493행](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r84/libs/binder/IPCThreadState.cpp#488)의 `clearCaller()`가 호출자 자리에 자기 PID·UID를 써 넣기 때문이다. `getCallingUidOrThrow()`도 여기서는 예외 없이 10179를 돌려줬다. Android 13의 이 함수는 "지금 바인더 트랜잭션을 처리 중인 스레드인가"만 보기 때문에, 트랜잭션 도중에 identity를 지운 경우는 잡지 못한다. 현재 [main 브랜치의 Binder.java](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/os/Binder.java)는 조건을 `!isDirectlyHandlingTransaction() && !hasExplicitIdentity()`로 바꿨는데, `hasExplicitIdentity()`는 clear 뒤에 참이 되므로 main에서도 clear 뒤에는 예외 없이 자기 UID가 나온다. main 쪽은 소스로만 확인했고 다른 API 레벨 기기에서 돌려 보지는 않았다.

호출자는 바인더 스레드에서 읽어 변수로 넘겨야 한다. `adminOnExecutor`는 바인더 스레드에서는 10180이었지만 `pool-2-thread-1` 작업 스레드에서는 10179였고, 그 스레드는 Messenger의 메인 스레드처럼 트랜잭션 밖이다.

마지막 줄의 `ping`은 `getCallingUid=10180`은 맞게 나왔지만 `getCallingPid=0`이었다.

![cs.android.com kernel/superproject common-android13-5.15 common/drivers/android/binder.c 3437~3441행. if (!reply && !(tr->flags & TF_ONE_WAY)) t->from = thread; else t->from = NULL; t->sender_euid = task_euid(proc->tsk);](/assets/img/android-mastery/p1c17/04-src-kernel-binder-oneway.png)

커널 [binder.c](https://android.googlesource.com/kernel/common/+/1ceae02e2db96f9dd761eb80d98b9f4b66234663/drivers/android/binder.c#3437)(`android13-5.15` 브랜치의 `1ceae02e` 커밋 기준 행 번호)는 UID를 보낸 태스크의 euid로 찍지만(3441행), oneway 트랜잭션에는 보낸 스레드(`t->from`)를 기록하지 않는다(3437~3440행). 받는 쪽에 넘길 때 `from`이 없으면 `sender_pid`가 0이 된다([5146~5155행](https://android.googlesource.com/kernel/common/+/1ceae02e2db96f9dd761eb80d98b9f4b66234663/drivers/android/binder.c#5146)). Binder.java 327행 주석의 "oneway transactions do not receive PID"가 이 이야기다. [IMessenger.aidl](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/IMessenger.aidl#23)은 `oneway interface`로 선언돼 있어서 Messenger 트랜잭션도 PID를 받지 못한다. `Message`에 `sendingUid`는 있어도 보낸 PID 필드가 없는 것도 그래서다. oneway 호출을 받는 메서드에서 PID로 권한을 따지면 0을 놓고 판단하게 된다.

## onBind에서 거르려는 시도

바인드할 때 한 번 확인하고 binder를 줄지 말지 정하면 되지 않을까 싶어 `onBind`에서도 `getCallingUid()`를 찍었다. 앞의 두 캡처에서 이미 `onBind thread=main getCallingUid=10179`가 보였다. `onBind`는 [ActivityThread.java 4503~4516행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#4503)의 `handleBindService`가 메인 스레드에서 부르니, 여기서도 자기 UID만 보인다. 두 앱이 연달아 같은 서비스에 바인드하면 어떻게 되는지도 봤다.

![svcclient와 svcfriend를 차례로 am start -S ... --es mode aidl 한 뒤 logcat grep onBind 또는 whoami thread. AdminAidlService onBind thread=main getCallingUid=10179 한 줄, whoami thread=binder:4143_1 getCallingUid=10180 getCallingPid=5041, whoami thread=binder:4143_1 getCallingUid=10181 getCallingPid=5107. dumpsys activity services io.seika.svclab/.AdminAidlService 에서 IntentBindRecord{de4ec5d CREATE} 하나, requested=true received=true hasBound=true doRebind=false, Client AppBindRecord 두 개(5107:io.seika.svcfriend/u0a181, 5041:io.seika.svcclient/u0a180)](/assets/img/android-mastery/p1c17/08-device-onbind.png)

`onBind`는 한 번만 불렸다. 두 번째 앱 svcfriend가 바인드할 때 시스템은 이미 받아 둔 binder를 그대로 넘겼고, 서비스 코드는 그 바인드를 볼 기회조차 없었다. `dumpsys`에도 `IntentBindRecord` 하나 아래 클라이언트 두 개가 매달려 있다. [ActiveServices.java 3009~3032행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActiveServices.java#3009)은 binder를 이미 받은 경우 앱을 부르지 않고 연결만 이어 주고, [ServiceRecord.java 913~916행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ServiceRecord.java#913)은 같은 Intent(`Intent.FilterComparison` 기준)마다 레코드를 하나만 둔다. `onBind`는 Intent 단위로 한 번 도는 콜백이라 호출자별 인가를 걸 자리가 못 된다. 한편 그 뒤의 `whoami`는 두 앱 모두 자기 UID로 정확히 찍혔다.

## 바인더 스레드 풀과 check-then-act

[AIDL 문서](https://developer.android.com/develop/background-work/services/aidl)는 원격 호출이 플랫폼이 관리하는 스레드 풀에서 동시에 들어온다고 하고, [bound services 문서](https://developer.android.com/develop/background-work/services/bound-services)는 Messenger가 요청을 한 스레드에 줄 세운다고 설명한다. 쿠폰 사용 메서드로 이 차이를 재 봤다. `redeem`은 사용 여부를 확인하고 50 ms(DB 쓰기를 흉내 낸 지연) 뒤에 기록한다. `redeemAtomic`은 `Set.add()` 한 번으로 확인과 기록을 같이 한다.

```java
// AdminBinder.java 120~145행
    // (취약) 검사와 기록 사이에 50ms 창이 있는 check-then-act
    @Override
    public boolean redeem(String code) {
        if (used.contains(code)) {
            Log.i(TAG, svc + " redeem " + code + " thread=" + thread() + " -> already used");
            return false;
        }
        SystemClock.sleep(50); // DB 쓰기 같은 지연을 흉내 낸다
        used.add(code);
        Log.i(TAG, svc + " redeem " + code + " thread=" + thread()
                + " caller=" + Binder.getCallingUid() + " -> OK");
        return true;
    }

    // (방어) Set.add()가 검사와 기록을 한 번에 한다
    @Override
    public boolean redeemAtomic(String code) {
        if (!usedAtomic.add(code)) {
            Log.i(TAG, svc + " redeemAtomic " + code + " thread=" + thread() + " -> already used");
            return false;
        }
        SystemClock.sleep(50);
        Log.i(TAG, svc + " redeemAtomic " + code + " thread=" + thread()
                + " caller=" + Binder.getCallingUid() + " -> OK");
        return true;
    }
```

`used`는 `ConcurrentHashMap.newKeySet()`이라 컬렉션 자체는 스레드 안전하다. 그래도 `contains`와 `add` 사이가 비어 있으면 소용없다. 클라이언트는 스레드 네 개를 `CountDownLatch`로 묶어 동시에 출발시킨다. 한 클라이언트 스레드에서 보낸 호출은 순서대로 도착하기 때문에, 경쟁을 만들려면 클라이언트 쪽 스레드가 여럿이어야 한다.

![am start -S ... --es mode race 후 mode msgrace, logcat grep. AdminAidlService redeem GIFT-71904가 binder:4143_1, _4, _2, _3 네 스레드에서 모두 caller=10180 -> OK, redeem(GIFT-71904): 4 concurrent calls, true=4. redeemAtomic GIFT-71904A는 세 번 already used, binder:4143_3에서 한 번 OK, true=1. Messenger는 sent 4 x REDEEM(GIFT-76396M) from 4 threads 후 REDEEM GIFT-76396M thread=main caller=10180 -> OK 한 번, thread=main -> already used 세 번. ps -T -p $(pidof io.seika.svclab) 결과 u0_a179 PID 4143의 binder:4143_1부터 binder:4143_6까지 binder_wait_for_work 상태](/assets/img/android-mastery/p1c17/09-device-race.png)

같은 쿠폰이 서로 다른 바인더 스레드 네 개에서 네 번 다 OK가 났다. 처음에는 50 ms 창이면 두세 개쯤 새어 나갈 거라고 예상했는데, 네 개가 전부 통과했다. 우연인지 보려고 같은 실험을 스크립트로 반복했다. 동시 호출 4개로 캡처한 실행을 포함해 6번, 8개로 5번 돌렸고, `redeem`은 11번 모두 보낸 호출이 하나도 빠짐없이 통과했다(8개일 때는 서로 다른 바인더 스레드 8개를 썼다). `redeemAtomic`은 11번 모두 정확히 하나만 통과했다. 며칠 뒤 새로 부팅한 에뮬레이터에서 동시 호출 4개로 네 번 더 돌렸을 때도 `true=4`와 `true=1`이 그대로 나왔다. 이 숫자는 랩에 넣은 50 ms 지연과 에뮬레이터 스케줄링에 기대고 있어서 실제 앱에서 같은 비율이 나온다는 뜻은 아니다.

Messenger 쪽은 클라이언트 스레드 네 개가 동시에 보냈는데도 캡처한 실행에서 모든 REDEEM이 `thread=main`에서 하나씩 처리돼 OK는 한 번뿐이었다. OK가 한 번뿐인 것은 앞의 반복 실행 전부에서 같았다(반복 로그에는 스레드 이름을 남기지 않았지만, 핸들러가 `Handler(Looper.getMainLooper())`라 코드상 메인 스레드다). 메인 Looper에 묶었으니 경쟁은 없지만, 대신 핸들러에서 무거운 작업을 하면 앱의 UI 스레드가 막힌다. `ps -T`의 `binder:4143_1`…`_6`은 같은 시점 서비스 프로세스에 떠 있던 바인더 스레드들이다. 기본 최대치는 [ProcessState.cpp 48행](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r84/libs/binder/ProcessState.cpp#48)의 `DEFAULT_MAX_BINDER_THREADS 15`다.

## 매니페스트의 signature 권한은 서비스 코드보다 먼저 막는다

메서드마다 검사를 빠짐없이 넣는 것보다 확실한 방법은 처음부터 바인드를 못 하게 하는 것이다. 같은 서명의 앱끼리만 쓰는 서비스라면 `android:permission`에 signature 권한을 걸면 된다.

![dumpsys package io.seika.svcclient 에서 io.seika.svclab.permission.ADMIN: granted=false, svcfriend는 granted=true. svcclient mode guarded 실행 시 W/ActivityManager( 510): Permission Denial: Accessing service io.seika.svclab/.GuardedAidlService from pid=7297, uid=10180 requires io.seika.svclab.permission.ADMIN, 클라이언트 bindService GuardedAidlService -> SecurityException: Not allowed to bind to service Intent { cmp=io.seika.svclab/.GuardedAidlService }. svcfriend는 bindService -> true, GuardedAidlService onBind thread=main getCallingUid=10179, whoami thread=binder:4143_6 getCallingUid=10181, adminChecked caller=10181 checkSignatures=0 -> EXECUTED](/assets/img/android-mastery/p1c17/10-device-guarded.png)

svcclient는 ADMIN 권한을 요청했지만 서명이 달라 `granted=false`였다. 바인드는 system_server(pid 510)의 `Permission Denial`로 끝났고 클라이언트는 `bindService`에서 `SecurityException`을 받았다. 이 시도에 해당하는 SVCLAB 로그는 한 줄도 없다. svclab의 코드는 아예 돌지 않았다. [ActiveServices.java 3538~3552행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActiveServices.java#3538)이 서비스 레코드를 찾을 때 `checkComponentPermission`으로 거르고, 클라이언트 쪽 [ContextImpl.java 2039~2042행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ContextImpl.java#2039)이 음수 결과를 `Not allowed to bind to service` 예외로 바꾼다. 같은 키의 svcfriend는 바인드했고 `adminChecked`도 통과했다.

검사가 맞게 들어갔는지 확인하려면 정상 클라이언트로도 돌려 봐야 한다. svcfriend로 권한 없는 서비스의 모든 관리 경로를 다시 호출했다.

![svcfriend로 mode aidl과 mode msgr 실행 후 logcat grep admin 또는 ADMIN_. adminNoCheck caller=10181 EXECUTED, adminTrustPayload claimedUid=1000 realCaller=10181 EXECUTED, adminChecked caller=10181 checkSignatures=0 -> EXECUTED, adminAfterClear before=10181 afterClear getCallingUid=10179 checkSignatures=0 EXECUTED, adminOnExecutor binderThread getCallingUid=10181 worker pool-5-thread-1 getCallingUid=10179 EXECUTED, ADMIN_VULN caller from Binder.getCallingUid()=10179 (sender 10181) EXECUTED, ADMIN_SAFE caller from msg.sendingUid=10181 (sender 10181) checkSignatures=0 -> EXECUTED](/assets/img/android-mastery/p1c17/11-device-friend.png)

관리 경로 일곱 개가 모두 EXECUTED로 끝났다(adminAfterClear는 로그가 두 줄로 나뉘어 있다). 고친 검사(`adminChecked`, ADMIN_SAFE)는 10181을 보고 통과시켰다. clear 뒤·작업 스레드·handleMessage에서 읽은 검사(`adminAfterClear`, `adminOnExecutor`, ADMIN_VULN)는 서비스 자신의 10179를 보고 통과시켰고, `adminNoCheck`는 검사가 없었고 `adminTrustPayload`는 인자 1000을 믿었다.

## "아무 앱이나 바인드한다"의 조건

exported 서비스라고 아무 앱이나 바인드하는 건 아니다. 방금 본 `android:permission` 말고도 패키지 가시성이 걸린다. targetSdk 30 이상 앱은 `<queries>` 같은 선언 없이는 다른 앱의 컴포넌트를 찾지 못한다([Atlas C11](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)). svcblind로 확인했다.

![adb install out/svcblind.apk Success, am start -S -n io.seika.svcblind/io.seika.svcclient.Main --es mode aidl 후 logcat. io.seika.svcblind uid=10182 mode=aidl, W/ActivityManager: Unable to start service Intent { cmp=io.seika.svclab/.AdminAidlService } U=0: not found, bindService AdminAidlService -> false](/assets/img/android-mastery/p1c17/12-device-blind.png)

명시적 컴포넌트를 줬는데도 `not found`로 끝나고 `bindService`는 false를 돌려줬다. 예외가 아니라 false라서 앱에서는 그냥 "연결이 안 된다"로만 보인다. [ComputerEngine.java 640~679행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/ComputerEngine.java#640)이 호출자가 볼 수 없는 패키지의 컴포넌트를 결과에서 빼고, [ActiveServices.java 3377~3383행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ActiveServices.java#3377)이 그 로그를 찍는다. 공격자는 매니페스트에 `<queries>` 한 줄을 넣으면 그만이니 이건 방어로 칠 수 없다. svcclient가 그랬다.

서비스 Intent는 Android 5.0(API 21)부터 명시적이어야 한다. targetSdk 21 이상에서 컴포넌트도 패키지도 없는 Intent로 `bindService`를 부르면 [ContextImpl.java 1848~1859행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ContextImpl.java#1848)이 `IllegalArgumentException("Service Intent must be explicit")`을 던진다. Android 14의 암시적 Intent 제한은 exported되지 않은 컴포넌트로 가는 암시적 Intent와 mutable PendingIntent 이야기라([동작 변경 문서](https://developer.android.com/about/versions/14/behavior-changes-14)) 이미 명시적인 서비스 바인드와는 관계가 없다.

## 고친 서비스를 점검하는 방법

코드 리뷰는 매니페스트에서 시작한다. exported 서비스마다 `android:permission`이 있는지, 같은 개발사 앱끼리만 쓰는 서비스라면 그 권한이 `protectionLevel="signature"`인지 본다. 권한이 없다면 그 서비스의 모든 메서드가 기기의 다른 앱에 열려 있다고 보고 구현을 읽는다.

AIDL 구현에서는 `onTransact`가 부르는 메서드마다 맨 앞에서 `Binder.getCallingUid()`를 읽어 검사하는지 확인한다. 인자나 Bundle에 담긴 UID·패키지명으로 판단하는 코드, `clearCallingIdentity()` 뒤에 호출자를 읽는 코드, `Executor`·`Handler`·코루틴으로 넘긴 뒤에 읽는 코드가 grep 대상이다. 남의 요청을 처리하면서 `checkCallingOrSelfPermission`을 쓰는 곳도 함께 찾는다. Messenger 구현이라면 `handleMessage` 안의 `Binder.getCallingUid()`·`getCallingPid()`를 모두 `msg.sendingUid`로 바꾼다. 디버그 빌드에서 이 자리를 `getCallingUidOrThrow()`로 바꿔 두면 잘못 읽는 코드가 예외로 드러난다. 다만 이 함수는 `clearCallingIdentity()` 뒤에 읽는 경우를 잡지 못한다(adminAfterClear 결과 참고).

상태를 바꾸는 메서드는 바인더 스레드에서 동시에 불린다는 전제로 짠다. 확인과 기록이 한 번에 일어나야 한다(`Set.add`, `putIfAbsent`, DB의 유니크 제약이나 트랜잭션).

마지막으로 기기에서 확인한다. 다른 키로 서명한 클라이언트와 같은 키의 클라이언트를 둘 다 만들어 같은 호출을 보내고, 전자는 거부되고 후자는 자기 UID로 판정되는지 로그로 본다. 판정 로그에 누구로 판단했는지(이번 랩에서는 `caller=`)를 남겨 두면 정상 클라이언트의 UID가 찍히는지도 함께 확인할 수 있다. 상태를 바꾸는 메서드는 여러 클라이언트 스레드에서 동시에 불러 본다.

*다음 글: [ContentProvider와 FileProvider 실습](/posts/android-lab-p1c18-contentprovider-fileprovider/)*
