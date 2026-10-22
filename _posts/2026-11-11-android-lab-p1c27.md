---
layout: post
title: "방어 회귀 테스트 — WorkSource의 4바이트를 취약 이미지에서 먼저 빨갛게"
date: 2026-11-11 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 회귀테스트, CVE-2023-20963, WorkSource, Parcel, Robolectric, CTS]
excerpt: "CVE-2023-20963의 빈 WorkChain 리스트 시드는 Android 9 이미지에서 'read 16 of 20 bytes'로 실패했고, 2024-03 패치가 든 API 33 이미지에서는 같은 스위트 13개가 모두 통과했다. Robolectric은 진짜 프레임워크 바이트코드를 돌려 sdk 28·33에서 실패하고 34에서 통과했지만, sdk=33은 패치 수준을 뜻하지 않았고 ShadowParcel은 원시 바이트 시드를 받지 못했다."
---

지난 글에서는 발견 하나하나를 MASVS 요구사항과 MASTG 절차에 묶었다. 고친 결함은 거기서 끝나지 않는다. 다음 리팩터링에서 같은 실수가 돌아와도 빌드가 빨갛게 변해야 고친 의미가 남는다. 이번에는 이미 패치된 공개 CVE 하나를 붙잡고, 취약한 코드에서는 반드시 실패하고 고친 코드에서는 통과하는 회귀 테스트를 만들어 기기와 JVM 양쪽에서 돌렸다. 앵커는 [CVE-2023-20963](https://source.android.com/docs/security/bulletin/2023-03-01)이다. 2023년 3월 불리틴의 Framework 표에 A-220302519, 권한 상승(EoP), High, 영향 버전 11·12·12L·13으로 올라 있고, 같은 불리틴은 이 CVE가 제한적·표적 공격에 쓰였을 수 있다고 적어 두었다. Parcel의 쓰기·읽기 계약은 [Atlas C18](/posts/android-concept-atlas-c18-parcel-serialization-contract/)에, 패치 diff에서 변종을 찾는 법은 [C53](/posts/android-concept-atlas-c53-patch-diff-variant-analysis/)에, 취약본과 패치본을 대조군으로 세우는 이유는 [C54](/posts/android-concept-atlas-c54-reproducibility-control-design/)에 있다.

취약한 쪽 대조군은 `vitor-x86`(Android 9, API 28, x86, 빌드 PSR1.180720.122, 보안 패치 2019-08-05)이고, 고친 쪽은 `codex-atlas-api33`(Android 13, API 33, x86_64, TE1A.240213.009, 보안 패치 2024-03-01)이다. 시드가 버전에 묶이는지 보려고 `sec-26-r08`(Android 8.0.0, API 26, 보안 패치 2017-11-05)도 잠깐 띄웠다. 모두 google_apis userdebug 에뮬레이터다. JVM 쪽은 Robolectric 4.13과 그것이 내려받은 android-all-instrumented 28·33·34 jar이고, 빌드는 AGP 8.5.2와 Gradle 8.9, JUnit 4.13.2, androidx.test runner 1.6.2다. 패치 직전과 직후 커밋으로 AOSP를 두 번 빌드해 대조하는 방법도 있지만 디스크가 모자라서 하지 않았다. 대신 패치 전 코드를 실은 이미지와 패치 후 코드를 실은 이미지를 대조군으로 세웠다.

## 빈 WorkChain 리스트가 남기는 4바이트

`WorkSource`는 어떤 작업을 어느 앱(uid)의 몫으로 칠지 실어 나르는 Parcelable이다. 앱이 넘긴 값이 `system_server`에서 다시 풀리므로 쓰는 쪽과 읽는 쪽의 바이트 수가 어긋나면 그 뒤에 오는 항목들이 엉뚱한 자리에서 읽힌다. Android 13 태그의 [`writeToParcel`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/WorkSource.java#1172)과 [Parcel 생성자](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/WorkSource.java#125)를 나란히 보면 어긋나는 자리가 바로 보인다(왼쪽 숫자는 android-13.0.0_r1 파일의 실제 줄 번호).

```java
// core/java/android/os/WorkSource.java @ android-13.0.0_r1
1172    public void writeToParcel(Parcel dest, int flags) {
1173        dest.writeInt(mNum);
1174        dest.writeIntArray(mUids);
1175        dest.writeStringArray(mNames);
1176
1177        if (mChains == null) {
1178            dest.writeInt(-1);
1179        } else {
1180            dest.writeInt(mChains.size());
1181            dest.writeParcelableList(mChains, flags);
1182        }
1183    }

 125    WorkSource(Parcel in) {
 126        mNum = in.readInt();
 127        mUids = in.createIntArray();
 128        mNames = in.createStringArray();
 129
 130        int numChains = in.readInt();
 131        if (numChains > 0) {
 132            mChains = new ArrayList<>(numChains);
 133            in.readParcelableList(mChains, WorkChain.class.getClassLoader(), android.os.WorkSource.WorkChain.class);
 134        } else {
 135            mChains = null;
 136        }
 137    }
```

쓰는 쪽은 리스트가 비어 있지 않기만 하면(null이 아니면) 크기 int를 쓰고 `writeParcelableList`를 부른다. `writeParcelableList`는 자기 원소 개수를 int로 한 번 더 쓴다. 빈 리스트라면 `0`, `0`이 나란히 8바이트 들어간다. 읽는 쪽은 크기가 양수일 때만 리스트를 읽으니 첫 `0`만 소비하고 둘째 `0`은 남긴다. 그 4바이트가 다음 필드의 첫머리로 읽히면서 뒤의 내용이 한 칸씩 밀린다.

![gitiles 커밋 266b3bddcf14d448c0972db64b42950f76c759e3 화면. 제목 Reconcile WorkSource parcel and unparcel code, 본문에 빈 리스트일 때 크기 원소가 읽히지 않고 남아 이후 항목을 오염시킨다는 설명, Bug: 220302519, Test: atest android.security.cts.WorkSourceTest#testWorkChainParceling, diff는 core/java/android/os/WorkSource.java 의 - if (numChains > 0) 를 + if (numChains >= 0) 로 바꾼 한 줄](/assets/img/android-mastery/p1c27/01-patch-266b3bd.png)

원인은 패치 커밋 [266b3bd](https://android.googlesource.com/platform/frameworks/base/+/266b3bddcf14d448c0972db64b42950f76c759e3)가 직접 밝혀 두었다. 메시지는 빈 리스트일 때 크기 원소 하나가 읽히지 않고 남아 같은 Parcelable에서 이후에 읽는 항목을 망가뜨린다고 설명하고, diff는 `numChains > 0`을 `>= 0`으로 바꾼 한 줄이다. 메시지의 `Test:` 줄에는 회귀 테스트 이름까지 적혀 있다. [android-14.0.0_r1의 같은 생성자](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-14.0.0_r1/core/java/android/os/WorkSource.java#130)는 이 조건을 `>= 0`으로 갖고 있고, [android-9.0.0_r1](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-9.0.0_r1/core/java/android/os/WorkSource.java#110)은 `> 0`이다. Android 9는 불리틴의 영향 버전 목록에 없지만 지원이 끝나 목록에서 빠진 것으로 보이고, 코드는 같은 결함을 갖고 있다. 그래서 9 이미지를 취약한 쪽 대조군으로 쓸 수 있었다.

## 시드 파일 세 개를 기기와 JVM이 함께 읽게 만들었다

테스트는 `io.seika.regress`라는 작은 Java/JUnit4 프로젝트에 넣었다. 결함을 건드리는 최소 입력을 바이트 파일로 만들어 `corpus/`에 두고, 기기 테스트와 Robolectric 테스트가 같은 파일을 읽는다. 시드는 `writeToParcel`이 까는 순서 그대로 little-endian int32를 늘어놓고 맨 끝에 표지 `MARK`(0x4D41524B)를 붙인 것이다. 생성 스크립트 `mkseeds.py`는 인자로 받은 폴더에 파일을 쓴다.

```python
# corpus/*.bin 생성: WorkSource.writeToParcel 형식(little-endian int32) + 끝에 MARK
import struct, sys, pathlib
MARK = 0x4D41524B
seeds = {
    "00-null-chains.bin":      [0, -1, -1, -1],            # mChains == null  -> writeInt(-1)
    "01-empty-chains.bin":     [0, -1, -1, 0, 0],          # CVE-2023-20963: size 0 + list length 0
    "02-uid-empty-chains.bin": [1, 1, 1000, -1, 0, 0],     # mNum=1, mUids=[1000], 같은 빈 체인
}
out = pathlib.Path(sys.argv[1]); out.mkdir(exist_ok=True)
for name, ints in seeds.items():
    (out / name).write_bytes(struct.pack("<%di" % (len(ints) + 1), *ints, MARK))
    print(name, len(ints) * 4 + 4, "bytes")
```

`00`은 체인이 null인 정상 입력이고, `01`이 CVE의 상태(크기 0, 리스트 길이 0)다. `02`는 uid 하나(1000)를 실은 채 같은 빈 체인을 붙여 앞부분 길이가 달라도 같은 4바이트가 남는지 본다. 만들어진 파일을 xxd로 보면 이렇다.

```
== corpus/00-null-chains.bin
00000000: 0000 0000 ffff ffff ffff ffff ffff ffff  ................
00000010: 4b52 414d                                KRAM
== corpus/01-empty-chains.bin
00000000: 0000 0000 ffff ffff ffff ffff 0000 0000  ................
00000010: 0000 0000 4b52 414d                      ....KRAM
== corpus/02-uid-empty-chains.bin
00000000: 0100 0000 0100 0000 e803 0000 ffff ffff  ................
00000010: 0000 0000 0000 0000 4b52 414d            ........KRAM
```

판정은 한 함수가 한다. 시드를 Parcel에 채운 뒤 `WorkSource.CREATOR.createFromParcel`로 읽고, 읽기가 끝난 자리가 MARK 바로 앞인지, 다음 int가 정말 MARK인지 본다. 아래는 `app/src/main/java/io/seika/regress/ParcelReplay.java`에서 시드를 넣는 두 경로와 판정부를 발췌한 것이고, 줄 번호는 파일의 실제 번호다.

```java
26    public static String replayWorkSource(int[] seed) {
27        Parcel p = Parcel.obtain();
28        try {
29            for (int v : seed) p.writeInt(v);
30            return check(p);
31        } finally {
32            p.recycle();
33        }
34    }
35
36    /** 같은 시드를 Parcel.unmarshall 로 원시 바이트째 넣는 판. */
37    public static String replayWorkSourceUnmarshall(byte[] seed) {
38        Parcel p = Parcel.obtain();
39        try {
40            p.unmarshall(seed, 0, seed.length);
41            p.setDataPosition(seed.length);
42            return check(p);
43        } finally {
44            p.recycle();
45        }
46    }
47
48    private static String check(Parcel p) {
49        int total = p.dataPosition();
50        p.setDataPosition(0);
51        WorkSource.CREATOR.createFromParcel(p);
52        int after = p.dataPosition();
53        int next = p.readInt();
54        if (after == total - 4 && next == MARK) return null;
55        return String.format("WorkSource read %d of %d bytes, next int 0x%08x (want 0x%08x)",
56                after, total - 4, next, MARK);
57    }
```

`viaWriteInt`는 시드를 `writeInt`로 하나씩 채우고, `viaUnmarshall`은 `Parcel.unmarshall`로 원시 바이트를 통째로 넣는다. 퍼저가 남긴 크래시 입력처럼 형식을 모르는 바이트를 다시 먹일 때는 뒤쪽이 필요하다. `androidTest`의 `CorpusReplayTest`는 APK assets에서 `.bin`을 모두 읽어 파라미터로 돌리니, 시드 파일을 하나 넣으면 테스트가 두 개 늘어난다.

```java
// app/src/androidTest/java/io/seika/regress/CorpusReplayTest.java (44~52행)
    @Test
    public void viaWriteInt() {
        assertNull(name, ParcelReplay.replayWorkSource(ParcelReplay.ints(seed)));
    }

    @Test
    public void viaUnmarshall() {
        assertNull(name, ParcelReplay.replayWorkSourceUnmarshall(seed));
    }
```

같은 파일을 기기 테스트 assets로 싣는 건 `app/build.gradle.kts`의 한 줄이다. Robolectric 쪽 `CorpusReplayRoboTest`는 `../corpus`를 파일 경로로 읽는다. 아래 `systemProperty`는 Robolectric 테스트 이름에 `[34]` 같은 SDK 표지를 붙여 결과를 SDK별로 구분해 준다.

```kotlin
// app/build.gradle.kts (발췌)
    // 같은 시드 파일을 기기 테스트(assets)와 JVM 테스트(파일 경로) 양쪽이 읽는다
    sourceSets["androidTest"].assets.srcDirs("../corpus")
// ...
tasks.withType<Test>().configureEach {
    systemProperty("robolectric.alwaysIncludeVariantMarkersInTestName", "true")
}
```

시드와 별개로 업스트림 회귀 테스트의 단언도 옮겨 왔다. 커밋 메시지가 가리킨 CTS [`WorkSourceTest#testWorkChainParceling`](https://android.googlesource.com/platform/cts/+/refs/tags/android-14.0.0_r1/tests/tests/security/src/android/security/cts/WorkSourceTest.java#39)은 `createWorkChain()`으로 체인 리스트를 만든 뒤 `clear()`로 비우고, 왕복 직렬화 끝에 `assertEquals(p.dataSize(), p.dataPosition())`로 모든 바이트를 읽었는지 확인한다. 클래스는 `StsExtraBusinessLogicTestCase`를 상속하고 메서드에는 `@AsbSecurityTest(cveBugId = 220302519)`가 붙어 있다. `createWorkChain`과 `getWorkChains`는 `@SystemApi`라 일반 앱에서는 이름으로 부를 수 없어서 리플렉션으로 불렀다.

```java
// app/src/main/java/io/seika/regress/ParcelReplay.java (60~67행)
    public static WorkSource emptyChainWorkSource() throws ReflectiveOperationException {
        WorkSource ws = new WorkSource();
        Method create = WorkSource.class.getMethod("createWorkChain");   // @SystemApi
        Method chains = WorkSource.class.getMethod("getWorkChains");     // @SystemApi
        create.invoke(ws);
        ((java.util.List<?>) chains.invoke(ws)).clear();
        return ws;
    }
```

```java
// app/src/androidTest/java/io/seika/regress/WorkSourceRegressionTest.java (17~34행)
    @Test
    public void emptyChainList_readsEveryByte() {
        WorkSource ws;
        try {
            ws = ParcelReplay.emptyChainWorkSource();
        } catch (ReflectiveOperationException e) {
            assumeNoException("createWorkChain/getWorkChains not reachable from app", e);
            return;
        }
        Parcel p = Parcel.obtain();
        ws.writeToParcel(p, 0);
        int size = p.dataSize();
        p.setDataPosition(0);
        WorkSource.CREATOR.createFromParcel(p);
        int pos = p.dataPosition();
        p.recycle();
        assertEquals("bytes consumed by createFromParcel", size, pos);
    }
```

리플렉션이 막히면 이 테스트는 실패하지 않고 건너뛴다(`assumeNoException`). 이 선택이 Android 9에서 어떤 결과를 냈는지는 아래에 적었다. 마지막 스위트 `DefaultInstanceSweepTest`는 `WorkSource()`, `WorkSource(copy)`, `Bundle{k=1}`, `Intent(VIEW)`, `Rect`, `Point`를 기본 상태로 만들어 쓴 바이트 수와 읽은 바이트 수를 견준다. 기기용 스위트는 시드 테스트 6개, CTS식 테스트 1개, 스윕 6개로 모두 13개다. APK는 `regress/`에서 `gradle --no-daemon --offline assembleDebug assembleDebugAndroidTest`로 빌드했다.

## Android 9 이미지에서 먼저 실패하는지 본다

회귀 테스트는 패치된 기기에서 초록불을 보는 것만으로는 아무것도 증명하지 못한다. 결함과 상관없이 늘 통과하는 테스트도 똑같이 초록이기 때문이다. 그래서 취약한 이미지부터 돌렸다. 아래 명령의 `S`에는 에뮬레이터 시리얼(이번에는 `emulator-5620`)을 넣어 두었다.

```bash
export S=emulator-5620
adb -s $S shell getprop ro.build.version.release
adb -s $S shell getprop ro.build.version.security_patch
adb -s $S shell settings put global hidden_api_policy_p_apps 1
adb -s $S install -r -t app/build/outputs/apk/debug/app-debug.apk
adb -s $S install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb -s $S shell am instrument -w io.seika.regress.test/androidx.test.runner.AndroidJUnitRunner \
  | grep -E "^[0-9]+\) |AssertionError|^OK|^FAILURES|^Tests run"
```

처음에는 `hidden_api_policy_p_apps`를 건드리지 않고(설정값 `null`) `-r`로 상태 코드까지 받으며 돌렸다. 시드 테스트 네 개(01·02 시드의 두 경로)는 실패했고 요약 줄은 `Tests run: 13,  Failures: 4`였다. CTS식 테스트가 빠져 있었다. `emptyChainList_readsEveryByte`는 `INSTRUMENTATION_STATUS_CODE: -4`, 곧 가정 위반으로 건너뛴 상태였고, logcat에는 리플렉션이 막힌 흔적이 남아 있었다.

```
W o.seika.regres: Accessing hidden method Landroid/os/WorkSource;->getWorkChains()Ljava/util/ArrayList; (dark greylist, reflection)
E TestRunner: org.junit.AssumptionViolatedException: createWorkChain/getWorkChains not reachable from app: got: <java.lang.NoSuchMethodException: getWorkChains []>, expected: null
E TestRunner: Caused by: java.lang.NoSuchMethodException: getWorkChains []
```

`am instrument -w`의 요약에는 건너뛴 테스트가 따로 표시되지 않는다. 13개가 돌았고 4개가 실패했다는 숫자만 보면 회귀 테스트가 실행됐다고 믿기 쉽다. 시드 테스트가 리플렉션 없이 같은 결함을 잡아 준 덕에 이번에는 빨간불이 켜졌지만, CTS식 테스트 하나만 걸어 두었다면 이 기기에서 결과는 실패 0이었을 것이다. 정책을 `1`로 열고 다시 돌린 것이 아래 화면이다.

![터미널 탭 p1c27-api28b. getprop 결과 9 와 2019-08-05, settings put global hidden_api_policy_p_apps 1, APK 두 개 install Success, am instrument 출력에 01-empty-chains.bin 'WorkSource read 16 of 20 bytes, next int 0x00000000 (want 0x4d41524b)', 02-uid-empty-chains.bin 'read 20 of 24 bytes', emptyChainList_readsEveryByte 'bytes consumed by createFromParcel expected:<20> but was:<16>', 실패 목록 1)~5) 와 FAILURES!!! Tests run: 13, Failures: 5](/assets/img/android-mastery/p1c27/04-instr-api28-red.png)

실패한 다섯 개는 `viaWriteInt`와 `viaUnmarshall`의 01·02 시드, 그리고 `emptyChainList_readsEveryByte`다. 01 시드는 MARK 앞까지 20바이트 중 16바이트만 읽혔고, 다음 int는 MARK가 아니라 `0x00000000`이었다. 남은 4바이트가 정확히 `writeParcelableList`가 쓴 길이 `0`이다. uid를 하나 더 실은 02 시드도 24바이트 중 20바이트에서 멈췄다. CTS식 테스트는 `createFromParcel`이 쓴 20바이트 중 16바이트만 소비했다고 보고했다. 정상 시드 00과 스윕 여섯 개는 통과했다. 실패 메시지가 한 번씩 더 찍힌 것은 `am instrument` 스트림이 실행 중에 실패의 첫 줄을 먼저 내보내고 끝에 번호 붙은 요약을 다시 내기 때문이다.

## 2024-03 패치 이미지에서는 같은 스위트가 모두 통과했다

같은 APK 두 개를 `codex-atlas-api33`(`emulator-5600`)에 깔고 똑같이 돌렸다. 리플렉션용 정책은 `hidden_api_policy`를 1로 두었다.

![터미널 탭 p1c27-api33. getprop 결과 13 과 2024-03-01, settings put global hidden_api_policy 1, APK 두 개 install Success, am instrument 결과 OK (13 tests)](/assets/img/android-mastery/p1c27/05-instr-api33-green.png)

`OK (13 tests)`다. 이번에도 `-r`로 테스트마다 상태 코드를 받아 13개 모두 `INSTRUMENTATION_STATUS_CODE: 0`인 것을 확인했다. `emptyChainList_readsEveryByte`도 건너뛰지 않고 실제로 돌아서 통과했다는 뜻이다. 초록불이 정말 고친 코드 덕인지 보려고 기기의 `/system/framework/framework.jar`(37,337,276바이트, dex 4개)를 꺼내 jadx로 `android.os.WorkSource`만 디컴파일했다. 생성자 분기는 `if (numChains >= 0) {`였다. 패치 커밋과 같은 조건이다.

Android 9 기기에서도 같은 확인을 하려 했지만 되지 않았다. 그 이미지의 `framework.jar`는 183바이트짜리 껍데기로 `META-INF/MANIFEST.MF`만 들어 있었고, 코드는 `boot-framework.vdex`(헤더 `vdex019`) 안에 CompactDex(`cdex001`)로 들어 있었다. jadx는 CompactDex를 읽지 못하고 변환기도 갖추지 못해서, Android 9 쪽 기기 코드는 소스 태그와 위의 실패 결과로 갈음한다.

## Robolectric은 진짜 프레임워크 바이트코드를 돌린다

기기 없이 JVM에서 돌리는 Robolectric을 두고는 처음에 반대 결과를 예상했다. 섀도가 프레임워크를 흉내 내는 재구현이라면 WorkSource의 바이트 수준 결함은 거기 없을 테고, 그러면 취약한 SDK에서도 테스트가 통과해 결함을 놓칠 것이라고 봤다. 같은 단언을 `@Config(sdk = {28, 33, 34})`로 묶어 `gradle --no-daemon testDebugUnitTest`를 돌렸다.

![터미널 탭 p1c27-robo. gradle testDebugUnitTest 결과에서 CorpusReplayRoboTest viaWriteInt 00-null-chains 는 28·33·34 모두 PASSED, 01-empty-chains 와 02-uid-empty-chains 는 28·33 FAILED 34 PASSED, DefaultInstanceSweepRoboTest WorkSource() 와 WorkSource(copy) 는 세 SDK 모두 PASSED, WorkSourceRegressionRoboTest emptyChainList_readsEveryByte 는 28·33 FAILED 34 PASSED. 테스트 결과 XML 메시지 집계는 'read 16 of 20 bytes' 2건, 'read 20 of 24 bytes' 2건, 'expected:<20> but was:<16>' 2건, ShadowParcel$UnreliableBehaviorError 9건](/assets/img/android-mastery/p1c27/02-robolectric-android-all.png)

예상은 틀렸다. 01·02 시드와 CTS식 테스트가 sdk 28과 33에서 실패하고 34에서 통과했다. 실패 메시지도 기기와 바이트 단위까지 같았다(16 of 20, 20 of 24, 20 대 16). Robolectric은 [설명서](https://robolectric.org/architecture/)대로 android-all jar에 든 실제 프레임워크 코드를 계측해서 돌리고, 섀도는 `Parcel` 같은 일부 클래스에만 씌운다. `WorkSource` 생성자는 그 jar에 든 코드가 그대로 실행됐다. Maven 캐시의 jar 세 개에서 `WorkSource` 클래스를 꺼내 javap로 생성자 분기를 봤다.

![터미널 탭 p1c27-javap2. export M2=~/.m2/repository/org/robolectric/android-all-instrumented 후 ls 결과 13-robolectric-9030017-i6, 14-robolectric-10818077-i6, 9-robolectric-4913185-2-i6. 각 jar의 WorkSource Parcel 생성자 javap 결과 9-robolectric-4913185-2 는 30: ifle 62, 13-robolectric-9030017 은 30: ifle 64, 14-robolectric-10818077 은 46: iflt 80, 각각 뒤에 Parcel.readParcelableList 호출](/assets/img/android-mastery/p1c27/03-javap-android-all.png)

`ifle`는 스택 위의 값이 0 이하이면 else로 뛴다. 리스트를 읽는 본문은 `numChains > 0`일 때만 실행된다는 뜻이고, 9와 13 jar가 이렇다. 14 jar의 `iflt`는 0보다 작을 때만 건너뛰니 `>= 0`이다. 섀도가 결함을 지운다는 걱정은 이 클래스에는 맞지 않았다. Robolectric이 오히려 취약한 빌드를 공짜로 주는 셈이라, 기기 없이 실패부터 확인하는 데 쓸 수 있다.

## sdk=33은 패치 수준을 말하지 않는다

문제는 다른 데서 나왔다. 같은 "33"인데 Robolectric은 빨간불, 2024-03 패치 이미지는 초록불이다. Robolectric 4.13은 SDK 번호마다 android-all 빌드 하나를 고정해 둔다. [`DefaultSdkProvider`](https://github.com/robolectric/robolectric/blob/robolectric-4.13/robolectric/src/main/java/org/robolectric/plugins/DefaultSdkProvider.java#L71-L77)의 표에서 33은 `13` / `9030017`이고, 위 javap에서 본 대로 그 빌드는 패치 전 코드다. sdk 번호는 API 레벨일 뿐이고, 그 레벨의 어느 보안 패치인지는 말해 주지 않는다.

그래서 Robolectric의 sdk=33 결과로 "Android 13 기기는 아직 취약하다"고 쓰면 틀린다. 반대로 CI에서 패치 후 초록불을 기대하며 sdk=33 테스트를 걸어 두면 영원히 빨갛게 남고, 결국 누군가 `@Ignore`를 붙이게 된다. 프레임워크 결함의 패치 여부를 판정하는 데는 보안 패치 수준을 `getprop`으로 찍은 실제 이미지를 쓰고, Robolectric은 jar 빌드 번호를 함께 기록한 취약 대조군으로 쓰는 편이 맞다.

## ShadowParcel은 원시 바이트 시드를 받지 못한다

위 캡처의 마지막 줄 `ShadowParcel$UnreliableBehaviorError` 9건은 `viaUnmarshall`이 시드 3개와 SDK 3개의 모든 조합에서 낸 것이다. 정상 시드 00도, 고친 sdk 34도 빠짐없이 실패했다. `Parcel`에는 섀도가 씌워져 있고, [`ShadowParcel`](https://github.com/robolectric/robolectric/blob/robolectric-4.13/shadows/framework/src/main/java/org/robolectric/shadows/ShadowParcel.java#L44-L52)은 값을 타입별로 들고 있는 순수 Java 재구현이라 자기가 만들지 않은 바이트는 `unmarshall`하지 못하고, 그때 [같은 파일의 859행](https://github.com/robolectric/robolectric/blob/robolectric-4.13/shadows/framework/src/main/java/org/robolectric/shadows/ShadowParcel.java#L859)에서 `UnreliableBehaviorError("ShadowParcel unable to unmarshall its custom format")`를 던진다. 결함과 상관없는 거짓 빨간불이다. 아무 입력에나 실패하니 취약한 대조군에서 빨간불을 확인하는 단계는 그대로 통과한다. 패치된 SDK에서도 빨갛다는 사실까지 대조해야 드러난다.

기기에서는 사정이 달랐다. Android 9에서 `viaUnmarshall`은 01·02 시드에서 `viaWriteInt`와 똑같은 "read 16 of 20 bytes" 메시지로 실패했고 00 시드에서는 통과했다. 진짜 `Parcel`은 원시 바이트를 그대로 받기 때문이다. JVM에서는 `writeInt` 경로로만 시드를 다시 먹이고, 퍼저가 뱉은 형식 모를 바이트는 기기 테스트로 돌리는 것으로 나눴다.

## 기본 인스턴스 스윕은 이 결함을 지나친다

변종까지 막겠다고 경계를 넘는 Parcelable을 기본 생성자로 만들어 쓴 바이트와 읽은 바이트를 견주는 스윕을 짰다. 결함 클래스(쓰기·읽기 바이트 수 불일치)를 그대로 단언으로 옮긴 것이니 잡을 거라 봤다. 결과는 Robolectric 28·33에서도, Android 9 기기에서도 `WorkSource()`와 `WorkSource(copy)`가 모두 통과였다. Bundle·Intent·Rect·Point도 통과했다.

이유는 기본 상태에 있다. 새로 만든 `WorkSource`는 `mChains`가 null이라 `-1` 하나를 쓰고, 읽는 쪽은 `-1`을 받아 null로 되돌린다. 쓴 만큼 읽으니 대칭이다. 결함은 리스트가 비어 있지만 null은 아닌 상태에서만 나온다. 그 상태로 가려면 `createWorkChain()`을 부르고 비우는 식으로 객체를 일부러 몰아넣어야 한다. 스윕의 단언은 맞았지만 기본 생성자로는 그 상태에 닿지 않았다. 빈 체인 상태는 `01`·`02` 시드와 `emptyChainWorkSource()`만 만들어 냈다.

## 시드는 자기를 만든 버전의 직렬화 형식에 묶인다

Android 8.0 이미지에서는 01·02 시드만 실패할 거라고 예상했다. 8.0의 `WorkSource`에는 체인 필드가 아예 없으니([8.0.0_r1 생성자](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/os/WorkSource.java#80)는 `mNum`, `mUids`, `mNames`만 읽고 [`writeToParcel`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/os/WorkSource.java#673)도 그 셋만 쓴다) 체인 뒤의 바이트가 남는 건 당연하고, 체인이 null인 00은 괜찮으리라 봤다.

![터미널 탭 p1c27-api26. getprop 결과 8.0.0 과 2017-11-05, APK 두 개 install Success, am instrument 출력에 00-null-chains.bin 'WorkSource read 12 of 16 bytes, next int 0xffffffff', 01-empty-chains.bin 'read 12 of 20 bytes, next int 0x00000000', 02-uid-empty-chains.bin 'read 16 of 24 bytes', 실패 목록 1)~6) 은 세 시드의 viaWriteInt 와 viaUnmarshall, FAILURES!!! Tests run: 13, Failures: 6](/assets/img/android-mastery/p1c27/08-instr-api26.png)

00도 실패했다. 16바이트 중 12바이트만 읽혔고 다음 int는 `0xffffffff`였다. 8.0에는 체인 null 표지 `-1`을 읽는 코드가 없으니 그 4바이트가 남는다. 01은 20바이트 중 12, 02는 24바이트 중 16에서 멈췄다. 이 실패는 CVE와 무관한 형식 불일치다. `emptyChainList_readsEveryByte`는 `NoSuchMethodException: createWorkChain []`으로 건너뛰었다(상태 코드 `-4`). 메서드가 8.0에는 아예 없다.

코퍼스를 회귀 스위트로 쓸 때는 시드마다 어느 버전의 형식으로 잘랐는지 함께 적어 두고, 그 형식을 쓰지 않는 버전에서는 돌리지 않거나 결과를 따로 읽어야 한다. 그러지 않으면 오래된 기기 행렬에서 나온 빨간불이 결함인지 형식 차이인지 구분할 수 없다.

## 테스트에는 커밋 해시와 패치 수준을 적어 두었다

![2023-03-01 Android 보안 불리틴의 Versions 표. 1.0 March 6, 2023 Bulletin Published, 1.1 March 8, 2023 Bulletin revised to include AOSP links, 2.0 May 8, 2023 Revised CVE table](/assets/img/android-mastery/p1c27/06-bulletin-versions.png)

불리틴은 고쳐진다. 2023-03-01 불리틴의 Versions 표를 보면 3월 6일 1.0 게시 뒤 3월 8일에 AOSP 링크가 추가됐고(1.1) 5월 8일에 CVE 표가 다시 고쳐졌다(2.0). 개정은 기록되지만, "3월 불리틴"이라고만 적어 둔 테스트는 어느 판의 어느 링크를 기준으로 했는지 나중에 알 수 없다. 게다가 불리틴의 달은 기기에 실린 코드를 말해 주지 않는다. 이번에 쓴 API 33 이미지만 해도 2024-03 패치라서 2023-03 수정이 들어 있었고, Robolectric의 33 jar는 그 전 빌드였다.

그래서 테스트 주석과 기록에는 `266b3bddcf14d448c0972db64b42950f76c759e3`과 버그 번호 220302519를 적고, 대조군 이미지마다 빌드 지문과 `ro.build.version.security_patch`를, Robolectric은 android-all 빌드 번호를 함께 남겼다. 업스트림 CTS 테스트가 `@AsbSecurityTest(cveBugId = 220302519)`로 버그 번호에 매여 있는 것도 같은 방식이다. 파트너용 STS의 실행과 [AutoRepro](https://source.android.com/docs/security/test/autorepro)는 이 환경에서 돌려 보지 못했다. 이 CVE의 테스트가 상속하는 `StsExtraBusinessLogicTestCase` 같은 STS 클래스는 [STS 클래스 레퍼런스](https://source.android.com/reference/sts/classes)에서 볼 수 있다.

## CI에 걸 때 확인하는 것들

새 테스트는 취약한 대조군에서 먼저 실패하는지, 그 실패가 결함 때문인지까지 본다. 01 시드라면 "16 of 20"에 다음 int `0x00000000`이어야 하고, 같은 시드가 고친 대조군에서는 통과해야 한다. 건너뛴 테스트는 실패로 다룬다. `am instrument -w` 요약에는 가정 위반이 보이지 않으니 `-r`로 상태 코드를 받아 `-4`가 있으면 CI를 멈추게 하는 편이 안전하다. 이번에 Android 9에서 CTS식 테스트가 조용히 빠졌던 것처럼, 숨은 API 정책이나 버전 차이로 회귀 테스트가 실행조차 안 되는 일이 생긴다.
