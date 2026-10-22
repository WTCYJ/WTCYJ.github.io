---
layout: post
title: "APK triage — META-INF에 있는데 false로 찍힌 v1 서명"
date: 2026-10-18 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, apksigner, aapt2, bundletool, APK서명, AXML, AAB]
excerpt: "서명 조합을 달리한 자작 앱을 Android 13 에뮬레이터에 깔아 보니 META-INF에 v1 서명이 있는데도 apksigner verify는 v1을 false로 찍었다. v1만 서명한 같은 앱은 targetSdk 33에서는 설치를 거부당했고 29로 낮추자 들어갔다."
---

[지난 글](/posts/android-lab-p1c02-adb-evidence-collection/)에서는 기기에 깔린 앱의 UID와 권한, 로그와 저장소를 받아 적었다. 이번에는 손에 APK 파일 하나만 있다. 코드를 열기 전에 누가 서명했고 어떤 서명 스킴이 들어 있는지, 매니페스트가 어떤 컴포넌트를 밖으로 열어 두었는지, split으로 쪼개져 있거나 네이티브 라이브러리를 품고 있는지를 먼저 적는다.

도구는 build-tools에 든 `apksigner`, `aapt2`와 따로 배포되는 `bundletool`이다. 서명 스킴과 exported 컴포넌트를 미리 정해 둔 앱을 넣었는데 첫 명령부터 출력을 곧이곧대로 옮겨 적을 수 없었다. `Verified using v1 scheme (JAR signing): false`라고 찍힌 APK를 풀어 보니 META-INF에는 v1 서명 파일이 있었다.

## 정답을 알고 만든 실험 앱

실험 앱 `io.seika.triage`는 Gradle 8.9와 AGP 8.5.2로 빌드한 작은 Java 앱이다. minSdk 26, targetSdk 33, versionCode 3, versionName `1.3-lab`이다. targetSdk만 29로 바꾼 빌드를 하나 더 뽑았다. x86_64와 arm64-v8a용 JNI 라이브러리 `libtriage.so`(소스 `jni/triage.c`)는 `"lib built for "` 뒤에 ABI 이름을 붙인 문자열을 돌려주는 함수 하나뿐이고, NDK 27 clang으로 빌드해 `proj/app/src/main/jniLibs/` 아래 ABI 폴더에 넣었다. 여기에 mdpi·xxhdpi 아이콘과 한국어 `values-ko` 문자열을 넣어 bundletool이 ABI, 화면 밀도, 언어별 split을 만들게 했다. 매니페스트에는 triage에서 걸러내야 할 것들을 일부러 섞었다.

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <permission android:name="io.seika.triage.permission.SYNC" android:protectionLevel="signature"/>
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <application android:label="@string/app_name" android:icon="@drawable/ic_dot" android:allowBackup="true">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <activity android:name=".LinkActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.VIEW"/>
                <category android:name="android.intent.category.DEFAULT"/>
                <category android:name="android.intent.category.BROWSABLE"/>
                <data android:scheme="seika" android:host="triage"/>
            </intent-filter>
        </activity>
        <receiver android:name=".TokenReceiver" android:exported="true">
            <intent-filter><action android:name="io.seika.triage.RESET_TOKEN"/></intent-filter>
        </receiver>
        <service android:name=".SyncService" android:exported="true"
            android:permission="io.seika.triage.permission.SYNC"/>
        <provider android:name=".NotesProvider" android:authorities="io.seika.triage.notes"
            android:exported="false"/>
    </application>
</manifest>
```

`MainActivity`는 런처라서 열려 있어야 하고 `LinkActivity`는 `seika://triage` 딥링크를 받는다. `TokenReceiver`는 아무 권한 없이 export된 리시버다. `SyncService`도 export됐지만 signature 보호 수준의 커스텀 권한 `SYNC`가 막는다. `NotesProvider`는 닫혀 있다. 그러니 권한 없이 밖에서 닿는 컴포넌트는 MainActivity, LinkActivity, TokenReceiver다. triage 도구가 이 목록을 그대로 돌려주는지가 확인 거리다.

릴리스 빌드는 서명 없이 나오게 두고 `make_variants.sh`에서 zipalign한 뒤 apksigner로 서명 조합을 바꿔 가며 서명했다. `$NDK_BIN`은 NDK 27의 `toolchains/llvm/prebuilt/windows-x86_64/bin`이고 targetSdk는 `app/build.gradle.kts`가 `-Ptsdk` 속성으로 정한다(기본 33). 두 번째 키 `CN=Attacker Lab, O=SeiKa Lab`(RSA 2048)은 키 교체와 키 불일치 실험에 쓴다. 여기서 쓴 Attacker Lab 키는 아래 목록과 같은 keytool 옵션으로 미리 만들어 둔 것이고, 목록의 keytool 줄은 그 키를 다시 만드는 방법이다. keytool은 실행할 때마다 새 키를 만드니 따라 하면 Attacker Lab 인증서의 다이제스트가 글의 `863afb43…0d9a`와 다르게 나온다. debug 키의 다이제스트(`766e4a4c…feb1`)도 각자의 `debug.keystore`에 따라 달라진다.

```bash
mkdir -p proj/app/src/main/jniLibs/x86_64 proj/app/src/main/jniLibs/arm64-v8a
"$NDK_BIN/clang" --target=x86_64-linux-android26 -shared -fPIC -O2 -o proj/app/src/main/jniLibs/x86_64/libtriage.so jni/triage.c
"$NDK_BIN/clang" --target=aarch64-linux-android26 -shared -fPIC -O2 -o proj/app/src/main/jniLibs/arm64-v8a/libtriage.so jni/triage.c
mkdir -p build
(cd proj && gradle --no-daemon assembleRelease bundleRelease)
cp proj/app/build/outputs/apk/release/app-release-unsigned.apk build/unsigned-t33.apk
cp proj/app/build/outputs/bundle/release/app-release.aab build/triage-unsigned.aab
(cd proj && gradle --no-daemon -Ptsdk=29 assembleRelease)
cp proj/app/build/outputs/apk/release/app-release-unsigned.apk build/unsigned-t29.apk
B=build; O=out; mkdir -p "$O"
keytool -genkeypair -keystore attacker.jks -alias attacker -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Attacker Lab, O=SeiKa Lab" -storepass attacker -keypass attacker
DBG=(--ks "$HOME/.android/debug.keystore" --ks-key-alias androiddebugkey --ks-pass pass:android --key-pass pass:android)
ATK=(--ks attacker.jks --ks-key-alias attacker --ks-pass pass:attacker --key-pass pass:attacker)
zipalign -f -p 4 "$B/unsigned-t33.apk" "$B/aligned-t33.apk"
zipalign -f -p 4 "$B/unsigned-t29.apk" "$B/aligned-t29.apk"
# default apksigner policy: writes v1+v2+v3 and the v4 sidecar triage.apk.idsig
apksigner sign "${DBG[@]}" --out "$O/triage.apk" "$B/aligned-t33.apk"
# v1 (JAR) only, same app at targetSdk 33 and 29
V1=(--v1-signing-enabled true --v2-signing-enabled false --v3-signing-enabled false --v4-signing-enabled false)
apksigner sign "${DBG[@]}" "${V1[@]}" --out "$O/triage-v1only-t33.apk" "$B/aligned-t33.apk"
apksigner sign "${DBG[@]}" "${V1[@]}" --out "$O/triage-v1only-t29.apk" "$B/aligned-t29.apk"
# no v1: only the APK Signing Block (v2+v3) carries the signature
apksigner sign "${DBG[@]}" --v1-signing-enabled false --v4-signing-enabled false --out "$O/triage-nov1.apk" "$B/aligned-t33.apk"
# key rotation debug -> attacker; rotated key used from API 33 (v3.1), original key below
apksigner rotate --out "$O/lineage" --old-signer "${DBG[@]}" --new-signer "${ATK[@]}"
apksigner sign "${DBG[@]}" --next-signer "${ATK[@]}" --lineage "$O/lineage" --out "$O/triage-rotated.apk" "$B/aligned-t33.apk"
rm -f "$O/triage-v1only-"*.idsig "$O/triage-nov1.apk.idsig" "$O/triage-rotated.apk.idsig"
cp "$B/triage-unsigned.aab" "$O/triage.aab"
```

키 교체본 서명은 v4를 끄지 않아서 `triage-rotated.apk.idsig`도 생긴다. `rm` 줄은 기본 서명본의 `triage.apk.idsig`만 남기고 사이드카를 지운다. `.aab`는 AGP `bundleRelease`가 만든 서명 없는 번들을 복사만 했다. 이 번들로 APK 세트 두 개를 만들었다. `ANDROID_SDK_HOME=.`은 작업 폴더 `.android/`에 둔 SDK debug 키스토어 사본을 bundletool이 쓰게 하려고 잡았다. 잡지 않으면 사용자 홈의 키스토어를 쓴다.

```bash
export ANDROID_SDK_HOME=.
bundletool build-apks --bundle=out/triage.aab --output=out/triage.apks
bundletool build-apks --bundle=out/triage.aab --output=out/universal.apks --mode=universal
```

| 파일 | 서명 | 보려는 것 |
|---|---|---|
| `triage.apk`, `triage.apk.idsig` | apksigner 기본값, debug 키 | 기본 정책이 실제로 넣는 스킴 |
| `triage-nov1.apk` | v1과 v4를 끔 | 서명 블록만 있는 APK |
| `triage-v1only-t33.apk` | v1만, targetSdk 33 | targetSdk에 걸린 설치 관문 |
| `triage-v1only-t29.apk` | v1만, targetSdk 29 | 같은 관문의 반대편 |
| `triage-rotated.apk` | debug 키에서 attacker 키로 교체 | v3.1과 SDK 범위별 서명 키 |
| `triage.aab` | 없음 | 번들의 구조 |
| `triage.apks`, `universal.apks` | bundletool, debug 키 | APK 세트 |
| `triage-attacker.apks` | bundletool, attacker 키 | install-apks의 키 불일치 |

호스트는 Windows의 Git Bash다. build-tools 36.0.0의 apksigner 0.9·aapt2 2.20-13193326, 따로 받은 bundletool 1.18.3, platform-tools의 adb 37.0.0, Android Studio에 든 JBR 21의 jarsigner·keytool을 썼다. 기기는 Android 13(API 33) google_apis x86_64 userdebug 에뮬레이터(빌드 `TE1A.240213.009`, 보안 패치 2024-03-01)다. 버전 차이를 볼 때만 Android 8.0(API 26, 보안 패치 2017-11-05) 에뮬레이터를 잠깐 띄웠다. 터미널 캡처의 `~/p1c03`이 작업 폴더다.

## v1이 false로 찍힌 APK 안의 v1 서명

옵션 없이 서명한 `triage.apk`를 `apksigner verify --verbose --print-certs`에 넣으면 이렇게 나온다. 인증서 SHA-256 뒤에 이어지는 SHA-1·MD5 다이제스트, 키 알고리즘과 키 크기, 공개 키 다이제스트 줄은 뺐다.

```text
$ apksigner verify --verbose --print-certs out/triage.apk
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v3.1 scheme (APK Signature Scheme v3.1): false
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
Signer #1 certificate DN: C=US, O=Android, CN=Android Debug
Signer #1 certificate SHA-256 digest: 766e4a4ce2ecb9bfce171ec829100591aa9f0bbd3fa1a497ad909ee5b9d2feb1
```

그대로 읽으면 이 APK에는 v1 서명도 v4 서명도 없다. 그런데 apksigner 소스를 보면 [ApkSignerTool.java 146~149행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/ApkSignerTool.java#146)에서 `v1SigningEnabled`부터 `v4SigningEnabled`까지 전부 `true`로 시작하고 v4가 켜져 있으면 출력 파일 이름 뒤에 `.idsig`를 붙인 사이드카를 따로 쓴다([419~423행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/ApkSignerTool.java#419)). 실제로 `out/`에는 `triage.apk.idsig`가 생겼고 APK 안에는 `META-INF/ANDROIDD.SF`, `ANDROIDD.RSA`, `MANIFEST.MF`가 들어 있었다.

![unzip -l out/triage.apk 가 META-INF/ANDROIDD.SF 1009바이트·ANDROIDD.RSA 1167바이트·MANIFEST.MF 882바이트를 보여 주고, apksigner verify 에 --min-sdk-version 23 을 주면 v1 scheme true, --v4-signature-file out/triage.apk.idsig 를 주면 v4 scheme true 가 찍히는 터미널](/assets/img/android-mastery/p1c03/01-apksigner-verify.png)

같은 파일에 `--min-sdk-version 23`을 주자 v1이 `true`로 바뀌었다. apksigner는 따로 지정하지 않으면 매니페스트의 minSdk(여기서는 26)를 검증 기준으로 삼는다.

v4 줄도 비슷하다. verify는 사이드카를 스스로 찾지 않는다. `--v4-signature-file` 옵션을 읽는 곳이 [546~547행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/ApkSignerTool.java#546)이고 파일이 주어졌을 때만 검증기에 넘긴다([597~602행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/ApkSignerTool.java#597)). `.idsig`를 넘기자 v4가 `true`로 바뀌었다. triage할 때는 서명자 인증서의 SHA-256을 먼저 적고 관심 있는 가장 오래된 기기의 API를 `--min-sdk-version`으로 넣어 한 번 더 돌린다. 옆에 `.idsig`가 있으면 그것도 넘긴다.

v1이 false였던 이유는 `ApkVerifier.java`에 있다. 아래 화면은 apksig 커밋 184702d의 그 파일이다. [340~344행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkVerifier.java#340)은 기준이 Android N(API 24) 이상이고 v2 이상 서명이 하나라도 있으면 JAR 서명 검증을 아예 건너뛴다.

![334~348행 소스 화면. 강조된 340행에서 시작해 343행까지 이어지는 주석이 Android N 이전 플랫폼은 v2 서명을 무시하고 항상 JAR 서명을 검증하며 N 이후는 v2 이상 서명이 없을 때만 JAR 서명을 검증한다고 설명하고, 344행 if 문은 minSdkVersion < AndroidSdkVersion.N 이거나 foundApkSigSchemeIds.isEmpty() 일 때만 V1SchemeVerifier.verify 를 부른다](/assets/img/android-mastery/p1c03/08-src-apkverifier-v1-skip.png)

verify가 찍은 v1 `false`는 "v1 서명으로 검증하지 않았다"는 보고다. API 24 이상 기기는 v2 서명이 있는 APK의 v1을 보지 않고 API 28 이상은 v3만 있어도 그렇다. 이 APK에는 v2와 v3가 다 있으니 minSdk 26 앱에서 v1을 보는 기기는 없고 META-INF의 v1 서명은 쓰이지 않은 채 남아 있다. `--min-sdk-version 23`을 줘서 v1까지 검증한 실행에는 경고 두 줄이 더 붙었다.

```text
WARNING: META-INF/com/android/build/gradle/app-metadata.properties not protected by signature. Unauthorized modifications to this JAR entry will not be detected. Delete or move the entry outside of META-INF/.
WARNING: META-INF/version-control-info.textproto not protected by signature. Unauthorized modifications to this JAR entry will not be detected. Delete or move the entry outside of META-INF/.
```

둘 다 AGP가 META-INF 아래에 넣은 빌드 정보 파일이다. `unzip -p out/triage.apk META-INF/MANIFEST.MF`로 열어 보면 두 파일의 다이제스트도 적혀 있다. 그래도 기기의 v1 검증은 `META-INF/` 아래 항목을 아예 건너뛴다([ApkSignatureVerifier.java 409행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/util/apk/ApkSignatureVerifier.java#409)). 그래서 apksigner는 서명 파일이 아닌 `META-INF/` 항목마다 이 경고를 낸다([V1SchemeVerifier.java 401~407행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/internal/apk/v1/V1SchemeVerifier.java#401)). [v2 서명](https://source.android.com/docs/security/features/apksigning/v2)은 ZIP 항목과 central directory까지 통째로 보호하는 whole-file 방식이니 이 경고는 JAR 서명만 보는 기기에서 의미가 있다.

인증서 DN은 신원을 판단하는 데 쓰지 않는다. 호스트에 있던 Allsafe 원본과 AndroGoat, 그리고 이 실험 앱은 셋 다 DN이 `C=US, O=Android, CN=Android Debug`였지만 SHA-256은 각각 `b1c87b48…b8ae`, `0fbee68b…d1ad`, `766e4a4c…feb1`로 모두 달랐다. debug 키스토어는 개발 환경마다 따로 만들어지니 같은 이름의 서로 다른 키가 흔하다.

## 서명이 들어 있는 자리

v1은 JAR 서명이라 `META-INF/`의 `.SF`, `.RSA`, `MANIFEST.MF`에 들어 있다. v2와 v3, v3.1은 ZIP 항목 바깥의 [APK Signing Block](https://source.android.com/docs/security/features/apksigning/v2)에 들어간다. central directory 바로 앞에 끼워 넣는 블록이다. 안은 ID와 값의 쌍이고 검증기는 모르는 ID를 건너뛴다. v4는 [`<apk 이름>.apk.idsig`라는 별도 파일](https://source.android.com/docs/security/features/apksigning/v4)이고 v2나 v3 서명이 함께 있어야 한다.

블록 안에 무엇이 있는지 보려고 표준 라이브러리만으로 짧은 파서를 썼다. 끝의 EOCD에서 central directory 오프셋을 읽고 그 바로 앞 16바이트가 `APK Sig Block 42`인지 본 다음 ID-값 쌍을 훑는다.

```python
"""List the ID-value pairs of an APK's APK Signing Block (the block that sits right before the ZIP Central Directory).

usage: python sigblock.py APK [APK ...]
Block layout (source.android.com/docs/security/features/apksigning/v2):
  uint64 size | (uint64 len, uint32 id, value)* | uint64 size | "APK Sig Block 42"
"""
import struct, sys

NAMES = {  # apksig V2SchemeConstants / V3SchemeConstants / SourceStampConstants / ApkSigningBlockUtils
    0x7109871A: "APK Signature Scheme v2",
    0xF05368C0: "APK Signature Scheme v3",
    0x1B93AD61: "APK Signature Scheme v3.1",
    0x42726577: "verity padding",
    0x6DFF800D: "source stamp v2",
    0x2B09189E: "source stamp v1",
}


def blocks(data):
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise ValueError("no ZIP EOCD")
    cd_off = struct.unpack_from("<I", data, eocd + 16)[0]
    if data[cd_off - 16:cd_off] != b"APK Sig Block 42":
        return cd_off, None, []
    size = struct.unpack_from("<Q", data, cd_off - 24)[0]
    start = cd_off - size - 8
    assert struct.unpack_from("<Q", data, start)[0] == size, "size fields disagree"
    pairs, p = [], start + 8
    while p < cd_off - 24:
        ln, bid = struct.unpack_from("<QI", data, p)
        pairs.append((bid, ln - 4))
        p += 8 + ln
    return cd_off, start, pairs


for path in sys.argv[1:]:
    data = open(path, "rb").read()
    cd_off, start, pairs = blocks(data)
    print(f"{path}: central directory @ {cd_off}")
    if start is None:
        print("  no APK Signing Block (magic 'APK Sig Block 42' absent before the central directory)")
        continue
    print(f"  APK Signing Block @ {start}, {cd_off - start} bytes")
    for bid, n in pairs:
        print(f"  id 0x{bid:08x}  {n:6d} bytes  {NAMES.get(bid, 'unknown')}")
```

ID 값은 apksig의 [V2SchemeConstants.java 23행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/internal/apk/v2/V2SchemeConstants.java#23), [V3SchemeConstants.java 25~26행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/internal/apk/v3/V3SchemeConstants.java#25), [ApkSigningBlockUtils.java 100행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/internal/apk/ApkSigningBlockUtils.java#100), 소스 스탬프 ID는 [SourceStampConstants.java 23~24행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/internal/apk/stamp/SourceStampConstants.java#23)에서 가져왔다. 변형마다 돌려 보면 apksigner가 `true`라고 하는 스킴이 블록 안의 ID와 맞아떨어진다.

![sigblock.py 가 v1 전용 APK triage-v1only-t29.apk 에는 APK Signing Block 이 없다고 하고, triage.apk 에서는 45056 오프셋 4096바이트 블록에 0x7109871a v2·0xf05368c0 v3·0x42726577 verity padding 을 나열하며, unzip -p 로 본 ANDROIDD.SF 머리에 X-Android-APK-Signed: 2, 3 이 있고 ls 로 본 triage.apk.idsig 크기가 5507 인 터미널](/assets/img/android-mastery/p1c03/02a-signing-block.png)

v1만 서명한 APK에는 블록 자체가 없다. 기본값으로 서명한 `triage.apk`는 45056 오프셋에 4096바이트짜리 블록이 있다. v2와 v3 항목이 각각 1402바이트이고 나머지는 verity padding(1224바이트)이 채운다. v1을 끈 `triage-nov1.apk`에서는 같은 구성(4096바이트, v2·v3 각 1402바이트와 padding)의 블록이 40960 오프셋에 있었다. META-INF에는 AGP가 넣은 빌드 정보 파일 두 개만 있고 `.SF`, `.RSA`, `MANIFEST.MF`는 없었다.

`ANDROIDD.SF` 머리에는 `X-Android-APK-Signed: 2, 3` 줄이 있다. v2 문서는 v1과 v2를 함께 서명한 APK의 `.SF`에 이 속성을 반드시 넣으라고 한다. 누군가 서명 블록을 떼어 내고 v1만 남겨 옛 방식으로 검증받게 만드는 공격을 막는 장치다. v1을 검증하는 쪽은 여기 적힌 스킴 가운데 자기가 지원하는 것의 서명이 APK에 없으면 거부해야 한다. v1만 서명한 빌드의 `.SF`에는 이 줄이 없었다.

| 스킴 | 위치 | 지원 시작 | 이번 파일에서 본 것 |
|---|---|---|---|
| v1 (JAR) | `META-INF/*.SF`, `*.RSA`, `MANIFEST.MF` | 처음부터 | `ANDROIDD.SF` 1009바이트, `ANDROIDD.RSA` 1167바이트 |
| v2 | 서명 블록, ID `0x7109871a` | Android 7.0 (API 24) | 1402바이트 |
| v3 | 서명 블록, ID `0xf05368c0` | Android 9 (API 28) | 1402바이트, 키 교체본은 1414바이트 |
| v3.1 | 서명 블록, ID `0x1b93ad61` | Android 13 (API 33) | 키 교체본에만 있음, 3260바이트 |
| v4 | 별도 파일 `.idsig` | Android 11 (API 30) | 5507바이트 |

지원 시작 버전은 source.android.com의 [v2](https://source.android.com/docs/security/features/apksigning/v2), [v3](https://source.android.com/docs/security/features/apksigning/v3), [v3.1](https://source.android.com/docs/security/features/apksigning/v3-1), [v4](https://source.android.com/docs/security/features/apksigning/v4) 문서를 따랐다.

## 키를 바꾼 APK는 SDK 범위마다 서명 키가 다르다

`apksigner rotate`로 debug 키에서 attacker 키로 넘어가는 lineage를 만들고 `--lineage`로 서명하자 블록이 8192바이트로 커지면서 v3.1 항목이 새로 생겼다. verify는 여전히 `Number of signers: 1`이라고 찍는다. apksig는 v3.1로 검증한 APK라면 v3.1 블록의 서명자 인증서 하나만 서명자 목록에 넣는다([ApkVerifier.java 611~613행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkVerifier.java#611)). 개수는 1로 찍혀도 이 APK에 든 서명 인증서는 두 개다. `--print-certs`는 v3.1 블록이 있으면 v3.1 블록의 서명자와 v3 블록의 서명자를 따로 찍는다([ApkSignerTool.java 653~669행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/ApkSignerTool.java#653)). `minSdkVersion=33` 줄에는 Attacker Lab 키(`863afb43…0d9a`)가, `minSdkVersion=24, maxSdkVersion=32` 줄에는 원래의 debug 키(`766e4a4c…feb1`)가 나온다. [apksigner 문서](https://developer.android.com/tools/apksigner)에도 교체된 키는 기본값으로 Android 13 이상에서 v3.1 블록에 쓰인다고 적혀 있다.

![sigblock.py 로 본 키 교체본 triage-rotated.apk 의 APK Signing Block 이 45056 오프셋 8192바이트이고 0x7109871a v2 1402바이트, 0x1b93ad61 v3.1 3260바이트, 0xf05368c0 v3 1414바이트, verity padding 2036바이트가 들어 있으며, apksigner verify --print-certs 가 minSdkVersion=33 서명자 CN=Attacker Lab 863afb43...0d9a 와 minSdkVersion=24, maxSdkVersion=32 서명자 Android Debug 766e4a4c...feb1 을 따로 보여 주는 터미널](/assets/img/android-mastery/p1c03/02b-rotated-signers.png)

lineage 파일에는 새 키가 lineage의 각 키에 허용한 권한이 적혀 있다.

```text
$ apksigner lineage --print-certs --in out/lineage
Signer #1 in lineage certificate DN: C=US, O=Android, CN=Android Debug
Signer #1 in lineage certificate SHA-256 digest: 766e4a4ce2ecb9bfce171ec829100591aa9f0bbd3fa1a497ad909ee5b9d2feb1
Signer #1 in lineage certificate SHA-1 digest: 0679ec7bdf576e4552e0ccd8354faeb2e89c2735
Signer #1 in lineage certificate MD5 digest: 92815a7f2913c239a33045c80b9efd1f
Has installed data capability: true
Has shared UID capability    : true
Has permission capability    : true
Has rollback capability      : false
Has auth capability          : true
Signer #2 in lineage certificate DN: CN=Attacker Lab, O=SeiKa Lab
Signer #2 in lineage certificate SHA-256 digest: 863afb436354b0cbfc1df223533008db1f037a4e64e06eaa43281ae1a3960d9a
Signer #2 in lineage certificate SHA-1 digest: aa29c9d4da185363a51c50f295ec527e782df1bb
Signer #2 in lineage certificate MD5 digest: b46c49a7f09f5f3730de8810079fa4df
Has installed data capability: true
Has shared UID capability    : true
Has permission capability    : true
Has rollback capability      : false
Has auth capability          : true
```

Android 13 에뮬레이터에 debug 키 빌드를 깔고 그 위에 교체본을 덮은 다음, 다시 옛 키 빌드로 되돌려 봤다.

```text
$ adb -s emulator-5600 install out/triage.apk
Performing Incremental Install
Performing Streamed Install
Success
$ adb -s emulator-5600 install -r out/triage-rotated.apk
Performing Streamed Install
Success
$ adb -s emulator-5600 shell dumpsys package io.seika.triage | grep -E 'signatures=|past signatures'
    signatures=PackageSignatures{3f10148 version:3, signatures:[7cd71cb8], past signatures:[687d1130 flags: 17, 7cd71cb8 flags: 17]}
$ adb -s emulator-5600 install -r out/triage.apk
Performing Incremental Install
Performing Streamed Install
adb.exe: failed to install out/triage.apk: Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package io.seika.triage signatures do not match newer version; ignoring!]
```

`Performing Incremental Install`은 APK 옆의 `.idsig`를 보고 adb가 증분 설치부터 시도했다는 표시다. 같은 APK를 `.idsig` 없는 폴더에 복사해 깔면 이 줄 없이 `Performing Streamed Install`만 나왔다. `--incremental`을 직접 주면 Windows용 adb 37.0.0이 `Failed to stat input file 'out/triage.apk': Bad file descriptor.`를 찍고 기기에 아무것도 보내지 않아서 v4는 호스트에서 `apksigner verify --v4-signature-file`로 검증한 데까지만 봤다.

dumpsys의 `687d1130`과 `7cd71cb8`은 [지난 글](/posts/android-lab-p1c02-adb-evidence-collection/)에서 본 것처럼 서명 바이트의 `hashCode()`라서 각각 debug 키와 attacker 키를 가리키는 꼬리표로만 쓴다. `version:3`은 기기가 검증에 쓴 스킴 번호다([SigningDetails.java 58~62행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/content/pm/SigningDetails.java#58), JAR=1, V2=2, V3=3). 현재 서명자 `7cd71cb8`(attacker 키)은 v3.1 블록에만 있고 v3 블록에는 API 24~32용 debug 키가 들어 있으니 이 숫자만 보면 헷갈린다. Android 13의 [ApkSignatureSchemeV3Verifier.java 141~142행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/util/apk/ApkSignatureSchemeV3Verifier.java#141)은 v3.1 블록을 먼저 찾아 검증하고 그 결과는 [ApkSignatureVerifier.java 313~314행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/util/apk/ApkSignatureVerifier.java#313)에서 `SIGNING_BLOCK_V3`로 기록된다. SigningDetails에는 v3.1 값이 따로 없어 v3.1 블록으로 검증해도 3으로 남는다.

`flags: 17`은 [PackageSignatures.java 334~336행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/PackageSignatures.java#334)이 `Integer.toHexString`으로 찍은 16진수라 십진수로 23이고 [SigningDetails의 권한 비트](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/content/pm/SigningDetails.java#100)로 풀면 INSTALLED_DATA=1, SHARED_USER_ID=2, PERMISSION=4, AUTH=16의 합이다. ROLLBACK=8만 빠졌으니 lineage 출력의 `Has rollback capability: false`와 같은 내용이다.

옛 키로 되돌리는 설치가 막힌 이유도 여기서 나온다. [PackageManagerServiceUtils.java의 verifySignatures](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/PackageManagerServiceUtils.java#510)는 롤백이 아닌 일반 업데이트 설치에서 새로 들어온 APK의 lineage가 기존 서명자를 포함하고 그 키에 INSTALLED_DATA를 허용했거나, 기존 설치본의 lineage가 새로 들어온 키에 ROLLBACK을 허용했을 때 업데이트를 받는다([519~524행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/PackageManagerServiceUtils.java#519)). RollbackManager가 시작한 롤백은 예외라서 ROLLBACK 권한이 없어도 lineage에 있는 옛 키를 받아 준다([548~553행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/PackageManagerServiceUtils.java#548)). adb로 넣은 이번 `install -r`은 일반 설치다. 되돌리려고 넣은 `triage.apk`는 debug 키 하나로만 서명돼 attacker 키를 모른다. 설치본의 lineage에는 debug 키가 있지만 rollback을 허용받지 못했으니 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`이다.

Android 8.0(API 26) 에뮬레이터에서는 결과가 달랐다. 교체본을 덮어도 dumpsys는 `PackageSignatures{bfa6fb2 [687d1130]}`, 처음부터 교체본만 깔아도 `[687d1130]`이었다. v3와 v3.1을 모르는 8.0은 v2 블록의 서명자인 옛 debug 키로 앱을 알아본다. 같은 기기에서 옛 키 빌드로 되돌리는 `install -r`도 Success였다.

## grep이 0을 돌려준 매니페스트

APK 안의 `AndroidManifest.xml`은 텍스트가 아니다. 처음 두 줄을 16진수로 찍고 문자열을 grep해 봤다.

![unzip -p 로 꺼낸 AndroidManifest.xml 의 xxd 머리가 0300 0800 e410 0000 0100 1c00 9008 0000 과 3700 0000 ... f800 0000 이고, grep -c exported 는 0, NUL 을 지운 뒤 grep 하면 TokenReceiver 1번과 exported 1번만 나오고 true 는 없으며, aapt2 dump xmlstrings 는 55 unique UTF-16 strings, 2192 bytes, --file 없는 aapt2 dump xmltree 는 missing required flag --file 을 찍는 터미널](/assets/img/android-mastery/p1c03/03a-axml-grep.png)

머리 8바이트는 청크 헤더다. `0300`은 타입 `RES_XML_TYPE`(0x0003), `0800`은 헤더 크기 8, `e410 0000`은 전체 크기 0x10e4로 4324바이트다. `unzip -l`이 보여 주는 이 파일의 크기도 4324바이트였다. 바로 뒤에 `RES_STRING_POOL_TYPE`(0x0001) 청크가 이어진다. 헤더 크기 0x1c, 청크 크기 0x890(2192바이트), 문자열 개수 0x37(55개)이고 flags가 0이다. 두 타입 값은 [ResourceTypes.h 239~241행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/libs/androidfw/include/androidfw/ResourceTypes.h#239)에 있고 flags의 `UTF8_FLAG`(1<<8, [480행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/libs/androidfw/include/androidfw/ResourceTypes.h#480))가 꺼져 있으면 문자열이 UTF-16이라는 뜻이다. aapt2는 매니페스트를 링크할 때 일부러 UTF-16으로 굽는다([Link.cpp 1908~1909행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/tools/aapt2/cmd/Link.cpp#1908)의 `true /*utf16*/`). `aapt2 dump xmlstrings`가 찍은 "55 unique UTF-16 non-sorted strings … using 2192 bytes"가 헤더에서 읽은 값과 같다.

UTF-16에서는 ASCII 글자마다 0x00이 끼니 `grep -c exported`는 0을 돌려준다. NUL을 지우고 다시 세면 `exported`가 한 번, `TokenReceiver`가 한 번 나오고 `true`는 한 번도 나오지 않는다. 컴포넌트 다섯 개가 모두 `android:exported`를 달고 있어도 속성 이름은 문자열 풀에 한 번만 저장되고 각 속성은 그 문자열 인덱스만 가리킨다. 리소스 ID `0x01010010`은 문자열 풀 바로 뒤의 리소스 맵 청크(`RES_XML_RESOURCE_MAP_TYPE` = 0x0180, [ResourceTypes.h 253행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/libs/androidfw/include/androidfw/ResourceTypes.h#253))에 같은 인덱스 자리로 한 번 적힌다. 이 파일에서는 76바이트짜리 맵의 5번 자리가 `0x01010010`이고 문자열 풀 5번이 `exported`였다. `true`와 `false`는 문자열 풀에 들어가지 않고 타입이 붙은 값(`TYPE_INT_BOOLEAN` = 0x12, [ResourceTypes.h 331행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/libs/androidfw/include/androidfw/ResourceTypes.h#331))으로 저장된다. NUL을 지워도 grep만으로는 어떤 컴포넌트가 열렸는지 알 수 없다.

`aapt2 dump xmltree`로 디코드해서 읽는다. `--file`을 빼면 `missing required flag --file`과 사용법을 찍고 종료 코드 1로 끝나니 출력이 비어 보이는 경우와 헷갈릴 일은 없다. [Dump.h 257행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/tools/aapt2/cmd/Dump.h#257)이 `--file`을 필수 플래그로 등록한다. 흔히 쓰는 `grep -E 'exported|permission'`만 걸면 `E: activity` 같은 원소 줄이 빠져서 어느 줄이 어느 컴포넌트 것인지 알 수 없으니 원소 줄과 `android:name`을 같이 남기는 필터를 썼다.

```bash
aapt2 dump xmltree out/triage.apk --file AndroidManifest.xml \
  | sed 's#http://schemas.android.com/apk/res/android:#android:#; s/ (Raw: .*//' \
  | grep -E "E: (activity|service|receiver|provider)|android:name.*seika.triage.[A-Z][a-z]|exported|android:permission"
```

`sed`는 속성 이름 앞의 네임스페이스 URI를 `android:`로 줄이고 줄 끝의 `(Raw: …)`를 지운다. `seika.triage.[A-Z][a-z]` 조건은 인텐트 액션 같은 다른 `android:name` 줄을 떨어내려고 이 앱 패키지 바로 아래 클래스 이름만 남긴다.

![aapt2 dump xmltree out/triage.apk --file AndroidManifest.xml 을 sed 와 grep 으로 거른 출력에서 MainActivity·LinkActivity·TokenReceiver 는 exported=true, SyncService 는 permission io.seika.triage.permission.SYNC 와 exported=true, NotesProvider 는 exported=false 인 터미널](/assets/img/android-mastery/p1c03/03b-xmltree-filter.png)

출력은 매니페스트를 보고 꼽은 목록과 같았고 SyncService만 `exported=true` 위에 `android:permission` 줄이 하나 더 붙어 있다.

## badging에는 컴포넌트가 없다

실험 앱에 `aapt2 dump badging`을 돌린 출력이다.

```text
$ aapt2 dump badging out/triage.apk
package: name='io.seika.triage' versionCode='3' versionName='1.3-lab' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'
minSdkVersion:'26'
targetSdkVersion:'33'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.CAMERA'
application-label:'Triage Lab'
application-label-ko:'트리아지 랩'
application-icon-160:'res/lI.png'
application-icon-480:'res/lC.png'
application: label='Triage Lab' icon='res/lI.png'
launchable-activity: name='io.seika.triage.MainActivity'  label='' icon=''
feature-group: label=''
  uses-feature: name='android.hardware.camera'
  uses-implied-feature: name='android.hardware.camera' reason='requested android.permission.CAMERA permission'
  uses-feature: name='android.hardware.faketouch'
  uses-implied-feature: name='android.hardware.faketouch' reason='default feature for all apps'
main
other-activities
other-receivers
other-services
supports-screens: 'small' 'normal' 'large' 'xlarge'
supports-any-density: 'true'
locales: '--_--' 'ko'
densities: '160' '480'
native-code: 'arm64-v8a' 'x86_64'
$ aapt dump badging out/triage.apk | grep -E 'sdkVersion|targetSdk'
sdkVersion:'26'
targetSdkVersion:'33'
$ aapt2 dump permissions out/triage.apk
package: io.seika.triage
permission: io.seika.triage.permission.SYNC
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.CAMERA'
```

minSdk 줄의 이름이 도구마다 다르다. aapt2는 `minSdkVersion:'26'`이라고 찍고([DumpManifest.cpp 838행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/tools/aapt2/dump/DumpManifest.cpp#838)), 예전 aapt는 같은 값을 `sdkVersion:'26'`이라고 찍는다. 오래된 자료의 grep 패턴을 그대로 가져오면 aapt2 출력에서 minSdk를 놓친다. aapt는 build-tools 36.0.0에도 아직 `aapt.exe`로 들어 있지만 [aapt2 문서](https://developer.android.com/tools/aapt2)는 이미 deprecated라고 적었다.

badging에서 triage에 쓸 줄은 권한, 런처, `native-code`, `locales`, `densities` 정도다. 컴포넌트별 exported 여부는 badging에 나오지 않는다. 릴리스 빌드라 리소스 경로가 `res/lI.png`처럼 줄어 있어서 파일 이름으로 짐작할 거리도 없다. `aapt2 dump permissions`는 앱이 쓰는 권한과 함께 스스로 선언한 권한(`io.seika.triage.permission.SYNC`)까지 보여 주니 export된 컴포넌트를 지키는 권한이 앱 자신의 것인지 확인할 때 쓴다.

## AAB 안의 protobuf 매니페스트

`.aab`는 Play에 올리는 발행 포맷이라 APK와 생김새가 다르다.

![unzip -Z1 out/triage.aab 이 BundleConfig.pb, base/dex/classes.dex, base/lib/arm64-v8a·x86_64/libtriage.so, base/manifest/AndroidManifest.xml, base/native.pb, base/resources.pb 를 보이고, 매니페스트 xxd 가 0a80 200a 390a 0761 6e64 726f 6964 122a 로 시작하며, aapt2 dump xmltree out/triage.aab --file base/manifest/AndroidManifest.xml 는 could not identify format of APK 를 찍은 터미널](/assets/img/android-mastery/p1c03/04a-aab-layout.png)

루트에 `AndroidManifest.xml`도 `resources.arsc`도 없다. 매니페스트는 `base/manifest/` 아래에 있고 형식은 protobuf다. 첫 바이트 `0a`는 1번 필드(길이 구분 타입)의 태그이고 이어지는 `80 20`은 varint로 적은 길이 4096이다. aapt2 [Resources.proto](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/tools/aapt2/Resources.proto#582)에서 이 필드는 `XmlNode.element`다. 그다음 `0a 39`는 `XmlElement.namespace_declaration`(57바이트)다. 그 안에 `0a 07` 뒤로 `android`(prefix), `12 2a` 뒤로 42바이트짜리 `http://schemas.android.com/apk/res/android`(uri)가 UTF-8 그대로 보인다. APK의 AXML과 달리 문자열에 NUL이 끼지 않는다.

APK를 기대하는 도구는 이 파일을 열지 못한다. aapt2는 `could not identify format of APK.`를 찍었고 apksigner는 스택 트레이스와 함께 죽었다.

```text
$ apksigner verify out/triage.aab
Exception in thread "main" com.android.apksig.apk.ApkFormatException: Missing AndroidManifest.xml
	at com.android.apksig.ApkSigner.getAndroidManifestFromApk(ApkSigner.java:975)
	at com.android.apksig.ApkVerifier.getAndroidManifestFromApk(ApkVerifier.java:1245)
	at com.android.apksig.ApkVerifier.verifyAndGetMinSdkVersion(ApkVerifier.java:656)
	at com.android.apksig.ApkVerifier.verify(ApkVerifier.java:196)
	at com.android.apksig.ApkVerifier.verify(ApkVerifier.java:164)
	at com.android.apksigner.ApkSignerTool.verify(ApkSignerTool.java:610)
	at com.android.apksigner.ApkSignerTool.main(ApkSignerTool.java:97)
```

번들의 매니페스트는 bundletool이 읽는다. `bundletool dump manifest`는 protobuf를 XML로 풀어 주고 `--xpath`를 받는다. exported가 `true`이면서 `android:permission`이 없는 컴포넌트를 이렇게 물었다.

```bash
bundletool dump manifest --bundle=out/triage.aab --xpath="/manifest/application/*[@android:exported='true'][not(@android:permission)]/@android:name"
```

![bundletool dump manifest --xpath 가 io.seika.triage 의 MainActivity·LinkActivity·TokenReceiver 를 돌려주고, bundletool build-apks 가 debug keystore 로 서명한다는 INFO 와 toc.pb + splits 12개, --mode=universal 이 toc.pb universal.apk 를 만든 터미널](/assets/img/android-mastery/p1c03/04b-bundletool-xpath.png)

MainActivity, LinkActivity, TokenReceiver만 돌아왔다. SyncService는 권한이 붙어 있어서 빠졌다. 이 질의는 `android:exported='true'`라고 적힌 원소만 본다. 속성 없이 intent-filter만 둔 컴포넌트는 targetSdk에 따라 취급이 달라서 이 질의로는 잡히지 않고 그런 경우까지 포함한 지도 그리기는 [6장](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)에서 한다.

`build-apks`는 서명 정보를 주지 않으면 debug 키로 서명한다([bundletool 문서](https://developer.android.com/tools/bundletool)). 캡처의 INFO 줄에 `.\.android\debug.keystore`가 찍힌 것도 그 때문이다. 결과물 `triage.apks`는 `toc.pb`와 split 열두 개가 든 ZIP이다. master가 둘(`base-master`, `base-master_2`), ABI split이 둘, 밀도 split이 일곱, 언어 split(`ko`)이 하나다. `--mode=universal`로 만들어도 확장자는 `.apks`이고 안에 `toc.pb`와 `universal.apk`가 들어 있을 뿐이다. 이 파일을 `adb install`에 그대로 넣을 수는 없고 넣으려면 안의 `universal.apk`를 꺼내야 한다.

### base-master와 base-master_2

master가 둘인 이유는 기기 스펙을 바꿔 가며 `extract-apks`를 돌려 보고 알았다. API 28 스펙에서는 `base-master.apk`가, API 33 스펙에서는 `base-master_2.apk`가 뽑혔고 둘은 `classes.dex`를 압축했느냐 아니냐가 달랐다.

```text
$ cat specs/sdk28.json
{"supportedAbis":["x86_64","arm64-v8a"],"supportedLocales":["en-US"],"screenDensity":420,"sdkVersion":28}
$ cat specs/sdk33.json
{"supportedAbis":["x86_64","arm64-v8a"],"supportedLocales":["en-US"],"screenDensity":420,"sdkVersion":33}
$ mkdir -p specs/x28 specs/x33
$ bundletool extract-apks --apks=out/triage.apks --device-spec=specs/sdk28.json --output-dir=specs/x28
The APKs have been extracted in the directory: specs\x28
$ bundletool extract-apks --apks=out/triage.apks --device-spec=specs/sdk33.json --output-dir=specs/x33
The APKs have been extracted in the directory: specs\x33
$ ls specs/x28 specs/x33
specs/x28:
base-master.apk
base-x86_64.apk
base-xxhdpi.apk

specs/x33:
base-master_2.apk
base-x86_64.apk
base-xxhdpi.apk
$ unzip -v specs/x28/base-master.apk | grep classes.dex
    4348  Defl:N     2131  51% 1981-01-01 01:01 a4fe4729  classes.dex
$ unzip -v specs/x33/base-master_2.apk | grep classes.dex
    4348  Stored     4348   0% 1981-01-01 01:01 a4fe4729  classes.dex
```

CRC가 같으니 같은 DEX를 하나는 압축하고 하나는 그대로 담은 것이다.

### 번들 서명은 jarsigner로

[명령줄 빌드 문서](https://developer.android.com/build/building-cmdline)에 따르면 앱 번들은 apksigner로 서명할 수 없고 jarsigner를 써야 한다. AGP가 만든 서명 없는 번들을 `triage-signed.aab`로 복사해 jarsigner로 제자리 서명하고 keytool로 서명자를 읽었다.

```text
$ cp out/triage.aab out/triage-signed.aab
$ jarsigner -J-Duser.language=en -keystore .android/debug.keystore -storepass android -digestalg SHA-256 -sigalg SHA256withRSA out/triage-signed.aab androiddebugkey
jar signed.

Warning: 
The signer's certificate is self-signed.
$ unzip -Z1 out/triage-signed.aab | grep META-INF
META-INF/MANIFEST.MF
META-INF/ANDROIDD.SF
META-INF/ANDROIDD.RSA
base/root/META-INF/com/android/build/gradle/app-metadata.properties
base/root/META-INF/version-control-info.textproto
$ keytool -J-Duser.language=en -printcert -jarfile out/triage-signed.aab | grep -E 'Owner|SHA256'
Owner: C=US, O=Android, CN=Android Debug
	 SHA256: 76:6E:4A:4C:E2:EC:B9:BF:CE:17:1E:C8:29:10:05:91:AA:9F:0B:BD:3F:A1:A4:97:AD:90:9E:E5:B9:D2:FE:B1
Signature algorithm name: SHA256withRSA
```

keytool이 콜론을 넣어 찍은 SHA256은 apksigner가 APK에서 읽은 `766e4a4c…feb1`과 같은 값이다. 번들을 triage할 때는 이 경로로 업로드 키를 확인한다.

## Android 13 에뮬레이터에서 본 설치 관문

v1 전용 빌드와 번들은 같은 에뮬레이터에 이 순서로 넣었다. `S`는 에뮬레이터 시리얼이고 `TMP`와 `TEMP`는 bundletool이 APK 세트를 풀어 놓을 임시 폴더를 사용자 프로필 밖의 `C:\tmp`로 빼려고 잡았다.

```bash
export S=emulator-5600
export TMP='C:\tmp' TEMP='C:\tmp'
mkdir -p /c/tmp
export ANDROID_SDK_HOME=.
adb -s $S uninstall io.seika.triage
adb -s $S shell getprop ro.build.version.sdk
apksigner verify out/triage-v1only-t33.apk 2>&1 | head -2
adb -s $S install out/triage-v1only-t33.apk
adb -s $S install out/triage-v1only-t29.apk
adb -s $S shell dumpsys package io.seika.triage | grep -E 'targetSdk|signatures='
adb -s $S uninstall io.seika.triage
adb -s $S install out/triage.aab
adb -s $S install out/universal.apks
cp out/triage.aab out/renamed-aab.apk
adb -s $S install out/renamed-aab.apk
bundletool install-apks --apks=out/triage.apks --device-id=$S
adb -s $S shell pm path io.seika.triage
bundletool get-device-spec --device-id=$S --output=device-spec.json --overwrite
adb -s $S shell am start -W -n io.seika.triage/.MainActivity
```

### v1만 서명한 APK는 targetSdk에 따라 갈린다

v1만 서명한 targetSdk 33 빌드는 호스트의 apksigner에서부터 `DOES NOT VERIFY`였고 기기에서도 `INSTALL_PARSE_FAILED_NO_CERTIFICATES: Scanning Failed.: No signature found in package of version 2 or newer for package io.seika.triage`로 거부됐다. targetSdk만 29로 바꾼 같은 앱은 Success였다. dumpsys에는 `targetSdk=29`와 함께 `signatures=PackageSignatures{cbdf265 version:1, signatures:[687d1130], past signatures:[]}`가 남았다. JAR 서명(version 1)만으로 설치된 것이다.

![API 33 에뮬레이터에서 getprop ro.build.version.sdk 가 33, apksigner verify out/triage-v1only-t33.apk 가 DOES NOT VERIFY 와 Target SDK version 33 requires a minimum of signature scheme v2, adb install out/triage-v1only-t33.apk 가 INSTALL_PARSE_FAILED_NO_CERTIFICATES: Scanning Failed.: No signature found in package of version 2 or newer for package io.seika.triage, adb install out/triage-v1only-t29.apk 는 Success 인 터미널](/assets/img/android-mastery/p1c03/05a-v1-only-gate.png)

android13-release 브랜치의 `core/java/android/util/apk/ApkSignatureVerifier.java`에 있는 `getMinimumSignatureSchemeVersionForTargetSdk`는 targetSdk가 R(API 30) 이상이면 `SIGNING_BLOCK_V2`를, 아니면 `JAR`를 돌려준다.

![508~523행 소스 화면. 강조된 514행 getMinimumSignatureSchemeVersionForTargetSdk(int targetSdk) 가 targetSdk >= Build.VERSION_CODES.R 이면 SignatureSchemeVersion.SIGNING_BLOCK_V2, 아니면 SignatureSchemeVersion.JAR 를 반환한다](/assets/img/android-mastery/p1c03/07-src-min-scheme-targetsdk.png)

[ApkSignatureVerifier.java 514~519행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/core/java/android/util/apk/ApkSignatureVerifier.java#514)의 이 값은 설치할 때 패키지 검사에서 쓰인다. 기기가 찍은 문구는 [ScanPackageUtils.java 691~702행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/ScanPackageUtils.java#691)과 글자 하나까지 같다.

```java
    public static void assertMinSignatureSchemeIsValid(AndroidPackage pkg,
            @ParsingPackageUtils.ParseFlags int parseFlags) throws PackageManagerException {
        int minSignatureSchemeVersion =
                ApkSignatureVerifier.getMinimumSignatureSchemeVersionForTargetSdk(
                        pkg.getTargetSdkVersion());
        if (pkg.getSigningDetails().getSignatureSchemeVersion()
                < minSignatureSchemeVersion) {
            throw new PackageManagerException(INSTALL_PARSE_FAILED_NO_CERTIFICATES,
                    "No signature found in package of version " + minSignatureSchemeVersion
                            + " or newer for package " + pkg.getPackageName());
        }
    }
```

문구 속 `version 2`는 `SIGNING_BLOCK_V2`의 값 2다. 이 검사는 [InstallPackageHelper.java 4206행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/InstallPackageHelper.java#4206)에서 불리고 스캔 단계의 예외를 받아 앞에 `Scanning Failed.`를 붙이는 곳은 [같은 파일 974행](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/pm/InstallPackageHelper.java#974)이다. apksigner도 같은 규칙을 호스트에서 미리 적용한다([ApkVerifier.java 571~602행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkVerifier.java#571), [1253~1257행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkVerifier.java#1253)). 기기에 넣기도 전에 호스트에서 `DOES NOT VERIFY`가 나온 이유가 이것이다.

Android 8.0 에뮬레이터에서는 같은 v1 전용 targetSdk 33 빌드가 Success로 깔렸고 dumpsys에도 `targetSdk=33`이 찍혔다. [Android 11 동작 변경 문서](https://developer.android.com/about/versions/11/behavior-changes-11)가 말하는 대로, Android 11 이상 기기가 targetSdk 30 이상 앱에 v2 이상을 요구하는 규칙이라 그 전 버전에는 이 관문이 없다.

### .aab와 .apks는 adb 클라이언트에서 막힌다

`adb install out/triage.aab`와 `adb install out/universal.apks`는 `Performing Streamed Install`을 찍은 직후 `adb.exe: filename doesn't end .apk or .apex`로 끝났다. 기기까지 가지 않은 거절이다.

![adb install out/triage.aab 와 adb install out/universal.apks 가 둘 다 Performing Streamed Install 뒤 adb.exe: filename doesn't end .apk or .apex 로 끝나는 터미널](/assets/img/android-mastery/p1c03/05b-adb-reject.png)

adb 클라이언트의 [adb_install.cpp 161~169행](https://android.googlesource.com/platform/packages/modules/adb/+/1cf2f017d312f73b3dc53bda85ef2610e35a80e9/client/adb_install.cpp#161)이 안내 문구부터 찍고 확장자를 본다.

```cpp
static int install_app_streamed(int argc, const char** argv, bool use_fastdeploy) {
    printf("Performing Streamed Install\n");

    // The last argument must be the APK file
    const char* file = argv[argc - 1];
    if (!android::base::EndsWithIgnoreCase(file, ".apk") &&
        !android::base::EndsWithIgnoreCase(file, ".apex")) {
        error_exit("filename doesn't end .apk or .apex: %s", file);
    }
```

번들은 bundletool이 기기 스펙에 맞는 split을 골라 설치해야 한다. 확장자만 `.apk`로 바꾼 번들은 adb를 통과했지만 PackageManager가 `INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION: Failed to parse /data/app/vmdl405683414.tmp/base.apk: AndroidManifest.xml`로 거부했다. 루트에 매니페스트가 없는 ZIP이라 파서가 첫 단계에서 멈췄다.

### install-apks가 기기 스펙으로 고른 split

`bundletool install-apks`는 조용히 끝나지 않는다. `The APKs have been extracted in the directory: C:\tmp\7065071209111015968`처럼 고른 split을 풀어 둔 임시 폴더를 찍는다. 기본값이면 사용자 프로필 아래에 있는 Java 임시 폴더 경로가 찍히니 화면을 공유할 때 주의한다. 설치 뒤 `pm path`에는 `base.apk`, `split_config.x86_64.apk`, `split_config.xxhdpi.apk`가 나왔다.

![bundletool install-apks --apks=out/triage.apks --device-id=$S 가 The APKs have been extracted in the directory: C:\tmp\7065071209111015968 을 찍고, pm path io.seika.triage 가 같은 /data/app 폴더의 base.apk·split_config.x86_64.apk·split_config.xxhdpi.apk 세 줄을 나열한 터미널](/assets/img/android-mastery/p1c03/05c-install-apks-split.png)

`bundletool get-device-spec`으로 본 이 에뮬레이터는 `"sdkVersion": 33`, `"screenDensity": 420`, `"supportedLocales": ["en-US"]`이니 420dpi에 맞는 xxhdpi split이 붙고 한국어 split은 빠졌다.

세 파일을 뽑아 해시를 대 보니 `base.apk`는 `base-master_2.apk`, `split_config.x86_64.apk`는 `base-x86_64.apk`, `split_config.xxhdpi.apk`는 `base-xxhdpi.apk`와 바이트 단위로 같았다. 기기는 받은 파일의 이름만 `split_config.<설정>.apk`로 바꿔 둔다. dumpsys에는 `splits=[base, config.x86_64, config.xxhdpi]`로 남는다. x86_64 split에는 `lib/x86_64/libtriage.so`(5032바이트, 압축 없이 Stored)가 들어 있다. 앱을 띄우니 그 라이브러리가 돌려준 문자열이 화면에 떴다.

![Android 13 에뮬레이터 화면 위쪽을 자른 캡처. 상태바 아래 Triage Lab 앱 바와 그 밑 TextView 에 native says: lib built for x86_64 가 보인다](/assets/img/android-mastery/p1c03/09-app-abi-split.png)

### 다른 키로 서명한 APK 세트

같은 번들에 attacker 키스토어를 넘겨 APK 세트를 하나 더 만들었다.

```bash
bundletool build-apks --bundle=out/triage.aab --output=out/triage-attacker.apks --ks=attacker.jks --ks-key-alias=attacker --ks-pass=pass:attacker --key-pass=pass:attacker
```

이 세트를 debug 키 설치본 위에 넣으면 이렇게 끝난다.

```text
$ bundletool install-apks --apks=out/triage-attacker.apks --device-id=emulator-5600
The APKs have been extracted in the directory: C:\tmp\13470958846496961050
09:31:02 E/SplitApkInstallerBase: Failed to commit install session 2138243111 with command package install-commit 2138243111. Error: INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package io.seika.triage signatures do not match newer version; ignoring!
[BT:1.18.3] Error: Installation of the app failed.
com.android.tools.build.bundletool.model.exceptions.CommandExecutionException: Installation of the app failed.
```

그 뒤로 Java 스택 트레이스가 길게 이어지고 종료 코드는 1이다. 눈에 띄는 줄은 `[BT:1.18.3] Error: Installation of the app failed.`이지만 진짜 원인은 그 바로 위, ddmlib의 `SplitApkInstallerBase`가 전한 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`이다.

## 기기에서 꺼낸 APK로 한 바퀴

남이 만든 앱을 triage할 때는 기기에서 APK를 꺼내는 데서 시작한다. 에뮬레이터에 미리 깔아 둔 교육용 앱 Allsafe로 같은 순서를 밟았다. 꺼낸 파일은 빈 `pulled/` 폴더에 모았다.

![pm path infosecadventures.allsafe 가 base.apk 하나를 돌려주고, adb pull 이 10083052 bytes in 0.788s, apksigner 가 v1·v2·v3 true 와 Android Debug 766e4a4c...feb1, aapt2 badging 이 versionCode 5, versionName 1.5, minSdkVersion 23, targetSdkVersion 35, uses-permission 7줄(RECORD_AUDIO, QUERY_ALL_PACKAGES 포함), launchable MainActivity, native-code arm64-v8a armeabi-v7a x86 x86_64 를 보이는 터미널](/assets/img/android-mastery/p1c03/06a-device-pull-allsafe.png)

`pm path`는 `base.apk` 하나를 돌려줬고 pull로 10,083,052바이트를 받았다. 서명은 v1, v2, v3가 모두 `true`이고 minSdk가 23이라 v1도 검증됐다. 서명자 다이제스트를 보고 바로 멈췄다. `766e4a4c…feb1`은 이 실험 앱과 같은 debug 키다. 호스트에 있던 Allsafe 원본은 `b1c87b48…b8ae`에 v3가 `false`였으니 다른 빌드다. 해시를 대 보니 이 이미지의 Allsafe는 예전 실습에서 패치하고 이 debug 키로 다시 서명한 사본(sha256 `852a0792…2ed2`)이었다. 패키지 이름도 버전 문자열(`1.5`)도 같아서 badging만 봤다면 원본으로 적었을 파일이다.

badging에는 minSdk 23, targetSdk 35, 권한 일곱 줄(`RECORD_AUDIO`, `QUERY_ALL_PACKAGES` 포함), 런처 `MainActivity`, ABI 네 개짜리 `native-code`가 나왔다. 컴포넌트는 앞의 xmltree 필터로 보려 했다. 패키지 부분만 `infosecadventures.allsafe`로 바꿔 돌렸더니 `challenges` 하위 패키지와 androidx·Firebase 컴포넌트는 `android:name` 줄이 빠져 원소 줄과 `exported` 줄만 남았다. 거꾸로 `<application>`의 이름(`ArbitraryCodeExecution`) 줄은 섞여 나왔다. 이름 조건이 패키지 바로 아래 클래스만 통과시킨 탓이다. xmltree는 `<application>` 바로 아래 원소의 속성을 공백 12칸 들여 찍으니 이름 조건을 들여쓰기로 바꿨다.

```bash
aapt2 dump xmltree pulled/allsafe.apk --file AndroidManifest.xml \
  | sed 's#http://schemas.android.com/apk/res/android:#android:#; s/ (Raw: .*//' \
  | grep -E "E: (activity|activity-alias|service|receiver|provider) |^ {12}A: android:(name|exported|permission)\("
```

권한 없이 열린 컴포넌트는 ProxyActivity와 MainActivity, `challenges` 패키지의 DeepLinkTask, NoteReceiver, RecorderService, DataProvider였다. `exported=true` 일곱 줄 가운데 나머지 하나는 `android.permission.DUMP`가 붙은 androidx의 ProfileInstallReceiver다. 같은 깊이에 있는 `uses-library`와 `meta-data`의 이름 세 줄도 섞여 나왔다.

같은 방법으로 꺼낸 AndroGoat는 minSdk 19, targetSdk 33, 런처 `SplashActivity`였고 `native-code` 줄이 없었다. 같은 필터로 보니 권한 없이 열린 것은 SplashActivity, AccessControl1ViewActivity, ShowDataReceiver, DownloadInvoiceService와 provider `ContentProviderActivity`였다. 이 provider와 이름이 같은 activity가 따로 있지만 그쪽은 exported 속성이 없다. 서명자 `0fbee68b…d1ad`와 파일 해시는 호스트 원본과 같았다.

### config split을 badging하면 요청하지 않은 권한이 찍힌다

실험 앱의 `split_config.x86_64.apk`를 꺼내 badging하면 `split='config.x86_64'`, 빈 `versionName`과 함께 앱이 요청한 적 없는 `WRITE_EXTERNAL_STORAGE`, `READ_PHONE_STATE`, `READ_EXTERNAL_STORAGE`가 나온다. 전체 출력에는 이유가 붙어 있다. 앞의 둘은 `reason='targetSdkVersion < 4'`, 마지막은 `reason='requested WRITE_EXTERNAL_STORAGE'`다.

![adb pull 로 io.seika.triage 의 split_config.x86_64.apk 를 pulled/split-x86_64.apk 로 꺼내 aapt2 dump badging 하면 package 줄에 versionCode 3, versionName='', split='config.x86_64' 가 찍히고 WRITE_EXTERNAL_STORAGE·READ_PHONE_STATE·READ_EXTERNAL_STORAGE uses-permission 세 줄이 나오는 터미널](/assets/img/android-mastery/p1c03/06b-split-badging.png)

config split의 매니페스트에는 `<uses-sdk>`가 없다. 그래서 aapt2는 targetSdk를 4보다 작다고 보고 [DumpManifest.cpp 2588~2597행](https://android.googlesource.com/platform/frameworks/base/+/1cdfff555f4a21f71ccc978290e2e212e2f8b168/tools/aapt2/dump/DumpManifest.cpp#2588)의 Android 1.6 이전 호환 규칙대로 두 권한을 암묵 권한으로 붙인다. 이어서 쓰기 권한이 있으면 읽기 권한도 붙인다.

config split은 minSdk도 선언하지 않는다. 그래서인지 bundletool은 열어 본 config split(x86_64, xxhdpi, ko)마다 `META-INF/BNDLTOOL.SF`로 JAR 서명을 넣어 두었고 apksigner도 여기서는 v1을 `true`로 검증했다. minSdk를 선언한 `base-master`와 `base-master_2`에는 `BNDLTOOL.SF`가 없고 v1도 `false`였다. 앱의 권한과 서명 스킴은 split이 아니라 `base.apk`에서 읽는다. 실험 앱의 `pm path`에서도 `base.apk`가 맨 앞에 나왔다. Allsafe처럼 `pm path`가 한 줄이면 `head -1`로 충분하지만 split 앱이면 `grep base.apk`로 줄을 골라 꺼낸다.

## 배포 전에 서명과 노출을 확인하는 법

서명은 apksigner 기본값으로 충분하다. 배포 후보 APK에는 triage 때와 같은 옵션으로 `apksigner verify --verbose --print-certs`를 돌린다. `DOES NOT VERIFY`일 때 종료 코드가 1이었으니 CI에서는 종료 코드만 봐도 걸러진다. 같은 출력에서 인증서 SHA-256을 뽑아 릴리스마다 기록해 둔 값과 비교한다.

키를 교체했다면 다이제스트를 SDK 범위별로 둘 다 기록하고 `apksigner lineage --print-certs`로 각 키의 권한을 확인한다. 옛 키가 유출돼서 교체하는 경우라면 범위를 따져야 한다. 앞의 8.0 결과처럼 API 33부터 새 키를 쓰게 교체하면 그보다 낮은 기기에서는 여전히 옛 키가 앱의 신원이다.

노출은 허용 목록과 비교한다. 번들이라면 앞의 `bundletool dump manifest --xpath` 질의를, APK라면 앞의 `aapt2 dump xmltree` 필터를 빌드마다 돌려 출력이 허용한 컴포넌트 이름과 같은지 본다. xpath 질의는 권한 없는 것만 고르니 SyncService처럼 signature 권한을 붙이거나 `exported="false"`로 닫은 컴포넌트는 결과에서 빠진다. 막을 컴포넌트를 그렇게 고친 빌드에서 같은 질의를 다시 돌려 이름이 사라지는지 확인한다.

번들 업로드 서명은 jarsigner로 하고 `keytool -printcert -jarfile`로 서명자를 확인한다. Play는 올린 번들로 APK를 만들어 [Play 앱 서명](https://developer.android.com/studio/publish/app-signing)에 따라 Google이 관리하는 앱 서명 키로 서명해 배포한다. 그래서 사용자 기기에 깔린 APK의 서명자는 업로드 키와 다를 수 있다. 이번 환경에는 Play 배포 경로가 없어 그 서명은 관측하지 못했다. APK를 수정해 다시 서명하는 순서와 함정은 [7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)에서 다룬다.

참고 자료: [apksigner](https://developer.android.com/tools/apksigner) · [aapt2](https://developer.android.com/tools/aapt2) · [bundletool](https://developer.android.com/tools/bundletool) · [APK 서명 스킴 v2](https://source.android.com/docs/security/features/apksigning/v2) · [v3.1](https://source.android.com/docs/security/features/apksigning/v3-1) · [v4](https://source.android.com/docs/security/features/apksigning/v4) · [APK·AAB·Split(C06)](/posts/android-concept-atlas-c06-apk-aab-split/) · [APK 서명(C08)](/posts/android-concept-atlas-c08-apk-signing/) · [컴포넌트와 Binder(C21)](/posts/android-concept-atlas-c21-components-binder/)

*다음 글: [jadx 정적 분석](/posts/android-lab-p1c04-jadx-static-analysis/)*
