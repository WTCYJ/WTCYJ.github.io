---
layout: post
title: "APK 재서명과 zipalign — 서명 뒤 정렬은 서명 블록을 버린다"
date: 2026-10-22 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, zipalign, apksigner, APKSignatureScheme, Repackaging, SignaturePermission]
excerpt: "문자열 하나 바꾼 APK를 다른 키로 서명하자 Android 13 에뮬레이터는 원본 위 업데이트를 INSTALL_FAILED_UPDATE_INCOMPATIBLE로 막았고 uninstall 뒤 새로 깐 앱에는 signature 권한을 주지 않았다. 서명한 뒤에 zipalign을 돌리자 APK Signing Block이 통째로 빠졌고 build-tools 35와 36의 apksigner는 서명하면서 .so를 16KiB 경계에 스스로 맞췄다."
---

[지난 글](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)에서는 매니페스트를 읽기만 했다. [5장](/posts/android-lab-p1c05-apktool-smali/)에서 smali 한 줄을 고쳐 기기에 깔았을 때는 원본을 서명한 키를 그대로 갖고 있었으니 기기 입장에서는 같은 개발자가 낸 업데이트였다. 남이 만든 앱을 고치면 그 키가 없다. 다른 키로 다시 서명해야 하고 그 앞이든 뒤든 어딘가에 zipalign이 들어간다.

순서는 [zipalign 문서](https://developer.android.com/tools/zipalign)의 경고 상자에 적혀 있다. apksigner로 서명한다면 zipalign은 서명 전에, jarsigner를 쓴다면 서명 후에 돌리라고 한다.

![developer.android.com zipalign 문서의 Caution 상자. If you use apksigner, zipalign must be used before the APK file has been signed 와 If you use jarsigner (not recommended), zipalign must be used after the APK file has been signed 두 항목, 그 아래 zipalign alters the size of the "extra" field in the zip Local File Header sections 문장, Usage 절의 -P 16 설명과 예시 명령 zipalign -P 16 -f -v 4 infile.apk outfile.apk](/assets/img/android-mastery/p1c07/15-web-zipalign-caution.png)

이유로는 보통 다이제스트를 든다. v2 이상의 서명은 정렬이 끝난 바이트 배치를 서명하니 서명 뒤에 정렬하면 바이트가 밀려 다이제스트가 어긋난다는 설명이다. 직접 돌려 보니 그보다 더 크게 깨졌다. 서명한 APK에 zipalign을 돌리자 서명 블록이 통째로 사라졌다. 그리고 지금 쓰는 apksigner는 서명하면서 스스로 정렬까지 해서 서명 전에 zipalign이 넣어 둔 패딩을 자기 형식으로 다시 썼다.

도구는 apktool 3.0.2와 Android SDK build-tools 36.0.0의 zipalign, apksigner다. 비교용으로 build-tools 34.0.0과 35.0.0도 썼다. 세 버전 모두 `apksigner version`이 0.9를 찍어서 버전은 build-tools 번호로 부른다. 기기는 Android 13(API 33, 2024-03-01 보안 패치) x86_64 google_apis userdebug 에뮬레이터이고 SELinux는 Enforcing이다. 플랫폼 동작은 frameworks/base 태그 `android-13.0.0_r84`에서, apksigner와 zipalign의 동작은 [apksig](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb) 커밋 `184702d`와 [platform/build](https://android.googlesource.com/platform/build/+/045a3d6a3e359633a14853a5a5e1e4f2a11cbdae) 커밋 `045a3d6`의 소스에서 확인했다. 두 저장소에서 build-tools 36.0.0에 대응하는 공개 태그를 찾지 못해 main 브랜치의 커밋을 봤고, 아래에서 관측한 16KiB 재정렬과 `-P` 처리는 이 소스와 그대로 맞았다. 측정한 에뮬레이터 빌드(TE1A.240213.009)에는 대응하는 AOSP 태그가 없어서 마지막으로 공개된 Android 13 태그인 r84를 대신 봤고 기기가 낸 메시지 문구는 이 태그의 소스와 그대로 일치했다.

## signature 권한으로 묶은 자작 앱 한 쌍

실험 대상은 직접 만든 앱 두 개다. `io.seika.vault`는 signature 보호 수준의 권한을 정의하고 그 권한으로 막은 provider에서 토큰 문자열을 내준다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="io.seika.vault" android:versionCode="1" android:versionName="1.0">
    <permission android:name="io.seika.vault.permission.READ"
        android:protectionLevel="signature"/>
    <application android:label="Vault">
        <provider android:name=".SecretProvider"
            android:authorities="io.seika.vault.secret"
            android:exported="true"
            android:readPermission="io.seika.vault.permission.READ"/>
    </application>
</manifest>
```

`io.seika.resign`(minSdk 28, targetSdk 33)은 이 권한을 `<uses-permission>`으로 요청하고 `<queries>`에 vault 패키지를 적어 두었다. 켜지면 `ResignLab` 태그의 logcat과 화면에 같은 항목을 찍는다. 문자열 리소스 `build_label`, 자기 서명 인증서의 SHA-256(앞 16자와 뒤 8자), 그 값을 코드에 박아 둔 릴리스 인증서 해시와 견준 자체 검사 결과, vault 권한을 받았는지, provider를 조회한 결과, JNI 라이브러리 `libresign.so`를 불러왔는지가 차례로 나온다. provider가 조회를 거부하면 화면에는 예외 문구의 앞부분만 나오고 logcat에는 전체 문구를 담은 `vault exception` 줄이 하나 더 찍힌다. 매니페스트에 `android:extractNativeLibs="false"`를 두고 x86_64용 `.so`는 압축하지 않은 채(STORED) 넣었다. 이러면 설치기가 라이브러리를 따로 풀어 두지 않고 APK 안에서 바로 매핑하려 하므로 `.so`가 파일의 어디에 놓였는지가 설치 성패에 걸린다.

빌드는 Gradle 없이 javac, d8, aapt로 묶고 `.so`를 STORED로 덧붙여 `build-unsigned.apk`를 만든 뒤 `zipalign -P 16 -f 4`와 apksigner로 마쳤다. 키도 둘을 새로 만들었다. 개발자 키 역할인 `release.jks`(`CN=SeiKa Lab Release, O=SeiKa Lab`)로 두 앱의 원본을 서명했고 리패키징하는 쪽은 debug 키처럼 만든 `debug.keystore`(`CN=Android Debug, O=Android, C=US`, 비밀번호 `android`)를 쓴다. SDK가 자동으로 만드는 debug 키와는 다른 키다. 원본 둘을 깔고 띄우면 이렇게 나온다.

![에뮬레이터의 ResignLab 화면. label build: original release, signer sha256 bd44d3879fe5cc3d...abf51c80, self-check OK, signed with release key, vault permission GRANTED, vault query token=vault-7f3a, native libresign.so loaded](/assets/img/android-mastery/p1c07/16-device-original-screen.png)

릴리스 키로 서명된 원본은 자체 검사를 통과하고 vault와 서명자가 같으니 권한을 받아 `token=vault-7f3a`를 읽는다.

## 문자열 하나 바꿔 다른 키로 서명하기

작업 폴더(`resign-lab`)에서 원본을 apktool로 풀고 `build_label` 문자열만 바꿔 다시 묶은 다음, 정렬하고 debug 키로 서명했다. `-p fw`는 apktool이 쓰는 프레임워크 파일을 작업 폴더의 `fw/`에 두게 하는 옵션이다.

```bash
apktool d -q -f -p fw original.apk -o work
grep -n build_label work/res/values/strings.xml
sed -i 's/build: original release/build: repackaged/' work/res/values/strings.xml
grep -n build_label work/res/values/strings.xml
apktool b -p fw work -o unsigned.apk
apksigner verify unsigned.apk
zipalign -c -P 16 -v 4 unsigned.apk | tail -4
zipalign -P 16 -f 4 unsigned.apk aligned.apk
apksigner sign --ks debug.keystore --ks-pass pass:android --out repacked.apk aligned.apk
ls repacked.apk*
apksigner verify -v repacked.apk | head -4
```

![resign-lab 폴더의 터미널. apktool d -q -f -p fw original.apk -o work, grep 으로 본 strings.xml 4행 build_label 이 build: original release 에서 sed 뒤 build: repackaged 로 바뀜, apktool b -p fw work -o unsigned.apk 의 Using Apktool 3.0.2 와 Built apk into: unsigned.apk, apksigner verify unsigned.apk 의 DOES NOT VERIFY 와 ERROR: Missing META-INF/MANIFEST.MF, zipalign -c -P 16 -v 4 의 961 classes.dex (OK - compressed), 3828 resources.arsc (OK), 4521 lib/x86_64/libresign.so (BAD - 4521), Verification FAILED, 이어서 zipalign -P 16 -f 4 와 apksigner sign --out repacked.apk 뒤 ls 에 repacked.apk 와 repacked.apk.idsig, apksigner verify -v 가 Verifies 와 v1 false, v2 false, v3 true](/assets/img/android-mastery/p1c07/01-repack-pipeline.png)

`apktool b`가 만든 `unsigned.apk`는 이름 그대로 서명이 없어서 `Missing META-INF/MANIFEST.MF`로 검증에 떨어진다. 정렬도 돼 있지 않다. `apktool.yml`의 `doNotCompress` 목록에 `arsc`와 `so`가 있어서 두 파일은 압축 없이 들어갔지만, `libresign.so`의 데이터가 4521바이트 지점에서 시작해 `BAD - 4521`이다. 5장에서 본 대로 apktool은 결과물을 ZIP으로 묶기만 하고 정렬 단계를 거치지 않는다.

zipalign 인자는 잘못 읽기 쉽다. 맨 뒤 숫자 `4`는 위치 인자 `<align>`이고 압축하지 않은 모든 항목의 데이터를 4바이트 경계에 맞추라는 뜻이다. `-P 16`은 그와 별개로 압축하지 않은 `.so`만 16KiB 페이지 경계에 맞춘다. 옵션은 [ZipAlignMain.cpp 86~108행](https://android.googlesource.com/platform/build/+/045a3d6a3e359633a14853a5a5e1e4f2a11cbdae/tools/zipalign/ZipAlignMain.cpp#86)에서 페이지 크기로 바뀐다. 이름이 `.so`로 끝나는 항목에만 그 크기를 쓰는 건 [ZipAlign.cpp 39~51행](https://android.googlesource.com/platform/build/+/045a3d6a3e359633a14853a5a5e1e4f2a11cbdae/tools/zipalign/ZipAlign.cpp#39)의 `getAlignment()`다. 5장에서 쓴 `-p`는 같은 일을 4KiB로 하는 옛 플래그로, 흔히 보는 `zipalign -p 4`도 `-p` 스위치 뒤에 `<align>` 4가 따로 붙은 꼴이다. zipalign 문서는 `-p`를 deprecated로 표시하고 `-P 16`을 권한다. 검사할 때는 같은 옵션에 `-c`를 붙인다.

서명하고 나니 `repacked.apk.idsig`가 하나 더 생겼다. Android 11에서 들어온 v4 서명은 APK 밖의 별도 파일에 담기고 adb가 증분 설치(incremental install)에 쓴다([APK Signature Scheme v4](https://source.android.com/docs/security/features/apksigning/v4)).

## 서명이 다 들어 있는데 v3만 true

검증 결과에서 v2가 `true`로 나올 줄 알았다. 5장의 앱에서는 v2와 v3가 `true`였다. 그런데 `repacked.apk`는 v1과 v2가 `false`, v3만 `true`였다. 서명자를 대조하면서 범위를 바꿔 다시 검증했다.

```bash
apksigner verify --print-certs original.apk | grep -E "DN|certificate SHA-256"
apksigner verify --print-certs repacked.apk | grep -E "DN|certificate SHA-256"
apksigner verify -v repacked.apk | grep -E "v1 |v2 |v3 "
apksigner verify -v --min-sdk-version 21 repacked.apk | grep -E "v1 |v2 |v3 "
unzip -l repacked.apk | grep META-INF
```

![apksigner verify --print-certs 로 본 original.apk 의 Signer #1 certificate DN: CN=SeiKa Lab Release, O=SeiKa Lab 과 SHA-256 digest bd44d3879fe5cc3dff872e3e7d2c970e48211a6690ca77c05f897e88abf51c80, repacked.apk 의 CN=Android Debug, O=Android, C=US 와 7515cf75558219fb7402d88f9b5be302218da39997ad234eb823a8fc84895c53. apksigner verify -v repacked.apk 는 v1 false, v2 false, v3 true 이고 --min-sdk-version 21 을 주면 v1, v2, v3 모두 true, unzip -l repacked.apk 에 META-INF/ANDROIDD.SF, META-INF/ANDROIDD.RSA, META-INF/MANIFEST.MF](/assets/img/android-mastery/p1c07/02-signer-identity.png)

서명자는 의도대로 바뀌었다. 원본은 `CN=SeiKa Lab Release`에 `bd44d387…abf51c80`, 다시 서명한 쪽은 `CN=Android Debug`에 `7515cf75…84895c53`이다. `META-INF/`에 `ANDROIDD.SF`와 `ANDROIDD.RSA`가 있으니 v1 서명은 들어 있고 `--min-sdk-version 21`을 주자 세 스킴이 모두 `true`로 바뀌었다.

apksigner는 범위를 따로 주지 않으면 APK의 minSdk(여기서는 28)부터 검증한다. [ApkVerifier.java](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkVerifier.java#217)는 범위 상한이 Android 7.0(N) 이상일 때만 서명 블록(v2·v3)을 보고(217행), 그 안에서도 범위에 Android 9(P) 이상이 들어 있어야 v3를 확인한다(246~249행). v2는 minSdk가 P보다 낮거나 v3 이상을 하나도 못 찾았을 때만(279~283행), v1은 minSdk가 N보다 낮거나 v2 이상이 없을 때만(340~344행) 검증 대상에 오른다. 그 범위의 플랫폼이 실제로 검증할 스킴만 골라 보는 셈이다. Android 13은 v4, v3 순으로 보고 없을 때만 v2, v1로 내려간다([ApkSignatureVerifier.java 117~181행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSignatureVerifier.java#117)). 5장 앱은 minSdk가 26이라 v2까지 범위에 들어왔다. 서명이 다 들어갔는지 보려면 `--min-sdk-version`과 `--max-sdk-version`으로 범위를 넓힌다.

`apksigner sign`은 반대로 기본값에서 스킴을 다 넣는다. [ApkSignerTool.java 146~149행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/ApkSignerTool.java#146)에서 v1부터 v4까지 기본값이 모두 `true`다. 도움말([help_sign.txt 22~25행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/apksigner/java/com/android/apksigner/help_sign.txt#22))은 v1이 min/max SDK에 따라 켜진다고 적지만, minSdk 28인 이 앱에도 v1 파일이 들어갔다. v2와 v3는 아래에서 볼 APK Signing Block에, v4는 `.idsig`에 들어 있다.

## 기기는 업데이트를 막고 signature 권한을 거둔다

원본을 깐 에뮬레이터에 `repacked.apk`를 업데이트로 올려 보고 막히면 지운 뒤 새로 깔았다. `$S`는 에뮬레이터 시리얼을 담은 셸 변수이고 셸은 Windows의 Git Bash, adb는 platform-tools 37.0.0이다. `export`부터 첫 `logcat -c`까지 네 줄은 환경 준비와 이전 상태 정리라 아래 캡처에는 보이지 않는다.

```bash
export S=emulator-5600
adb -s $S uninstall io.seika.resign
adb -s $S uninstall io.seika.vault
adb -s $S logcat -c
adb -s $S install vault.apk
adb -s $S install original.apk
adb -s $S shell am start -W -n io.seika.resign/.MainActivity | grep Status
adb -s $S logcat -d -v raw -s ResignLab:I
adb -s $S install -r repacked.apk
adb -s $S uninstall io.seika.resign
adb -s $S install repacked.apk
adb -s $S logcat -c
adb -s $S shell am start -W -n io.seika.resign/.MainActivity | grep Status
adb -s $S logcat -d -v raw -s ResignLab:I
```

![adb -s $S install vault.apk 와 install original.apk 가 Performing Streamed Install 과 Success. 원본의 logcat 은 label: build: original release, signer sha256: bd44d3879fe5cc3d...abf51c80, self-check: OK, signed with release key, vault permission: GRANTED, vault query: token=vault-7f3a, native: libresign.so loaded. install -r repacked.apk 는 Performing Incremental Install, Performing Streamed Install 뒤 Failure INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package io.seika.resign signatures do not match newer version; ignoring!. uninstall io.seika.resign 후 install repacked.apk 는 Success, 다시 본 logcat 은 label: build: repackaged, signer sha256: 7515cf75558219fb...84895c53, self-check: MISMATCH, not the release key, vault permission: DENIED, vault exception: Permission Denial: reading io.seika.vault.SecretProvider ... requires io.seika.vault.permission.READ, vault query: SecurityException, native: libresign.so loaded](/assets/img/android-mastery/p1c07/08-device-identity.png)

`install -r`은 `INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package io.seika.resign signatures do not match newer version; ignoring!`로 끝났다. 설치된 패키지의 서명 정보와 새 APK를 맞춰 보는 [PackageManagerServiceUtils.java의 `verifySignatures()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/PackageManagerServiceUtils.java#516)가 내는 문장이다(561~564행). 그 위의 분기들은 서명자가 같거나 v3 서명의 키 순환 계보로 이어진 경우, 그리고 시스템 앱 검증이나 롤백 같은 특수한 경우만 통과시킨다. 아무 관계 없는 새 키는 어디에도 걸리지 않는다. `uninstall` 뒤에는 설치된다. 다만 uninstall은 앱 데이터까지 지우므로 원래 앱이 쌓아 둔 데이터를 그대로 두고 리패키징한 앱을 붙여 보는 실험은 이 방법으로는 안 된다.

다시 띄운 앱은 `build: repackaged`와 debug 키의 해시를 찍고 자체 검사는 `MISMATCH`, vault 권한은 `DENIED`다. provider 조회도 `Permission Denial: reading io.seika.vault.SecretProvider ... requires io.seika.vault.permission.READ`로 막혔다. 매니페스트는 그대로이니 `<uses-permission>`도 그대로인데 권한이 사라졌다. signature 권한을 줄지는 [PermissionManagerServiceImpl.java 3396~3421행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/permission/PermissionManagerServiceImpl.java#3396)의 `shouldGrantPermissionBySignature()`가 정한다. 권한을 정의한 패키지(또는 플랫폼)와 공통 서명자가 있어야 하고 그 서명자가 키 순환 계보의 옛 키라면 권한 공유 자격(`PERMISSION` capability)이 남아 있어야 한다.

위 캡처에서 `repacked.apk`를 깔 때만 `Performing Incremental Install` 뒤에 `Performing Streamed Install`이 찍혔다. v4 문서는 adb가 기본으로 `.idsig`를 써서 증분 설치를 시도하고 그 파일이 없거나 유효하지 않으면 일반 설치로 넘어간다고 적는데, 여기서는 `.idsig`가 있는데도 일반 설치로 넘어갔다. `--incremental`을 직접 주자 Windows용 adb가 `Failed to stat input file 'repacked.apk': Bad file descriptor.`를 내고 끝났다. 기기는 `ro.incremental.enable=yes`이니 증분 시도는 호스트 쪽에서 실패한 것으로 보이고 원인은 더 파지 않았다. 여기서 한 설치는 모두 일반(streamed) 설치로 들어갔다.

## 서명한 다음에 zipalign을 돌리면

이번에는 순서를 뒤집었다. 정렬하지 않은 `unsigned.apk`에 바로 apksigner를 쓰고 그 결과에 zipalign을 돌렸다. 처음 예상은 v2와 v3의 다이제스트 불일치였다.

```bash
apksigner sign --ks debug.keystore --ks-pass pass:android --out signed.apk unsigned.apk
zipalign -c -P 16 -v 4 signed.apk | grep -E "arsc|\.so|Verification"
zipalign -P 16 -f 4 signed.apk signed-then-aligned.apk
wc -c signed.apk signed-then-aligned.apk
grep -c -a "APK Sig Block 42" signed.apk signed-then-aligned.apk
unzip -p signed-then-aligned.apk META-INF/ANDROIDD.SF | grep X-Android
apksigner verify signed-then-aligned.apk
```

![apksigner sign --out signed.apk unsigned.apk 뒤 zipalign -c 가 3836 resources.arsc (OK), 16384 lib/x86_64/libresign.so (OK), Verification successful. zipalign -P 16 -f 4 signed.apk signed-then-aligned.apk 뒤 wc -c 가 29144 signed.apk, 23743 signed-then-aligned.apk, grep -c -a "APK Sig Block 42" 가 signed.apk:1, signed-then-aligned.apk:0, unzip -p 로 본 ANDROIDD.SF 의 X-Android-APK-Signed: 2, 3, apksigner verify 가 DOES NOT VERIFY 와 JAR signature META-INF/ANDROIDD.SF indicates the APK is signed using APK Signature Scheme v2 but no such signature was found. Signature stripped? 그리고 같은 문장의 v3 판](/assets/img/android-mastery/p1c07/03-sign-then-zipalign.png)

뜻밖에도 `signed.apk`는 zipalign을 거치기 전부터 정렬 검사를 통과했다. resources.arsc는 3836, `.so`는 16384에 놓였다. apksigner가 서명하면서 맞춰 놓은 자리다. zipalign을 거친 파일은 29144바이트에서 23743바이트로 줄었고 APK Signing Block 끝에 붙는 매직 문자열 `APK Sig Block 42`가 없어졌다. 블록이 없으니 v2와 v3는 비교할 다이제스트조차 남지 않았다. `.SF`에는 여전히 `X-Android-APK-Signed: 2, 3`이 남아 있어서 apksigner는 v1 쪽에서 `Signature stripped?`를 냈다.

서명 블록이 어디 있었는지 보려고 짧은 스크립트를 썼다. EOCD에서 central directory 오프셋을 읽고 그 바로 앞 16바이트가 매직 문자열이면 블록 크기를 읽어 안의 ID-값 쌍을 늘어놓는다.

```python
"""Where is the APK Signing Block? usage: python sigblock.py <apk>...
Prints file size, central directory offset, and the signing block's offset, size and ID-value pairs
(0x7109871a = v2, 0xf05368c0 = v3, 0x42726577 = padding). Stdlib only."""
import struct, sys

IDS = {0x7109871a: "v2", 0xf05368c0: "v3", 0x1b93ad61: "v3.1", 0x42726577: "padding"}
for fn in sys.argv[1:]:
    d = open(fn, "rb").read()
    eocd = d.rfind(b"PK\x05\x06")
    cd_off = struct.unpack("<I", d[eocd + 16:eocd + 20])[0]
    out = f"{fn}: size={len(d)} central-dir@{cd_off}"
    if d[cd_off - 16:cd_off] != b"APK Sig Block 42":
        print(out + " no signing block")
        continue
    size = struct.unpack("<Q", d[cd_off - 24:cd_off - 16])[0]
    start = cd_off - size - 8
    pairs, p = [], start + 8
    while p < cd_off - 24:
        ln, i = struct.unpack("<QI", d[p:p + 12])
        pairs.append(f"{IDS.get(i, hex(i))}:{ln - 4}")
        p += 8 + ln
    print(out + f" signing-block@{start} len={size + 8} [{' '.join(pairs)}]")
```

`sigblock.py`로 저장해 네 APK에 돌렸다.

```bash
python sigblock.py signed.apk signed-then-aligned.apk repacked.apk original.apk
```

```text
signed.apk: size=29144 central-dir@28672 signing-block@24576 len=4096 [v2:1449 v3:1449 padding:1130]
signed-then-aligned.apk: size=23743 central-dir@23271 no signing block
repacked.apk: size=29144 central-dir@28672 signing-block@24576 len=4096 [v2:1449 v3:1449 padding:1130]
original.apk: size=29142 central-dir@28672 signing-block@24576 len=4096 [v2:1436 v3:1436 padding:1156]
```

`signed.apk`에는 24576바이트(4096의 6배) 지점에 4096바이트짜리 블록이 있고 그 안에 v2 서명 1449바이트, v3 서명 1449바이트, 패딩 항목 1130바이트가 들어 있다. 블록 앞의 23271~24575 구간 1305바이트는 전부 0이었다. zipalign을 거친 쪽은 central directory가 23271로 당겨졌고 서명 블록이 없다. 줄어든 5401바이트는 블록 4096바이트와 그 앞 1305바이트를 더한 값이다.

zipalign은 입력 파일을 고치지 않고 새 파일에 항목을 하나씩 옮겨 담는다. [ZipAlign.cpp의 `copyAndAlign()`](https://android.googlesource.com/platform/build/+/045a3d6a3e359633a14853a5a5e1e4f2a11cbdae/tools/zipalign/ZipAlign.cpp#56)(56~102행)은 `getNumEntries()`만큼 돌며 항목마다 `pZout->add()`를 부르고 압축하지 않은 항목에만 정렬 값을 넘긴다. APK Signing Block은 ZIP 항목이 아니고 마지막 항목과 central directory 사이에 끼워 둔 바이트라서 옮겨 담을 목록에 처음부터 없다. 반면 v1 파일들은 평범한 항목이라 그대로 따라온다. 그래서 남은 `.SF`가 v2와 v3로도 서명됐다고 주장하는데 정작 그 서명은 없는 APK가 된다. `.SF`에 `X-Android-APK-Signed`를 두는 이유는 [v2 문서의 rollback 보호 절](https://source.android.com/docs/security/features/apksigning/v2#rollback-protections)에 나온다. 공격자가 v2 서명을 떼어 내고 v1만으로 검증받으려는 시도를 막으려고 v1 검증기는 `.SF`가 가리키는 더 강한 서명이 없으면 거부해야 한다. 5장에서 apktool `--copy-original`로 원래 `META-INF`를 붙여 다시 묶었을 때 본 메시지도 같은 경로였다.

## 패딩 한 바이트도 v2와 v3가 지킨다

zipalign이 서명 블록까지 옮겨 담는 도구였다고 쳐도 문제는 그대로다. 경고 상자 아래 문장대로 zipalign은 로컬 파일 헤더의 extra 필드 크기를 바꿔 데이터 위치를 맞춘다. 데이터가 아닌 그 패딩 바이트를 v1과 v2·v3가 어떻게 다루는지 보려고 서명된 `repacked.apk`에서 extra 필드 한 바이트만 바꿨다. 쓴 스크립트는 이것이다.

```python
"""Show or poke the local-header "extra" field of one APK entry (the bytes zipalign/apksigner use as padding).
usage: python lhextra.py <apk> <entry>             print offset, extra bytes, data offset
       python lhextra.py <apk> <entry> --poke      overwrite the LAST extra byte with 0x01 (in place, same size)
Entry contents and central directory are untouched; only padding inside the local file header changes."""
import struct, sys, zipfile

apk, name = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(apk) as z:
    off = z.getinfo(name).header_offset
with open(apk, "r+b") as f:
    f.seek(off)
    h = f.read(30)
    assert h[:4] == b"PK\x03\x04", "not a local file header"
    nlen, xlen = struct.unpack("<HH", h[26:30])
    xoff = off + 30 + nlen
    f.seek(xoff)
    extra = f.read(xlen)
    shown = extra[:8].hex(" ") + (" ..." if xlen > 8 else "")
    print(f"{name}: header@{off} extra@{xoff} len={xlen} [{shown}] data@{xoff + xlen}")
    if "--poke" in sys.argv:
        assert xlen > 0, "no extra field to poke"
        f.seek(xoff + xlen - 1)
        f.write(b"\x01")
        print(f"poked byte @{xoff + xlen - 1}: {extra[-1]:#04x} -> 0x01")
```

```bash
cp repacked.apk poked.apk
python lhextra.py poked.apk resources.arsc --poke
cmp -l repacked.apk poked.apk
unzip -tq poked.apk
apksigner verify -v --min-sdk-version 21 --max-sdk-version 23 poked.apk | head -2
apksigner verify --min-sdk-version 24 --max-sdk-version 27 poked.apk
apksigner verify poked.apk
```

![cp repacked.apk poked.apk 뒤 python lhextra.py poked.apk resources.arsc --poke 가 resources.arsc: header@3784 extra@3828 len=8 과 35 d9 04 00 04 00 00 00, data@3836, poked byte @3835: 0x00 -> 0x01 을 찍고, cmp -l 은 3836 0 1 한 줄, unzip -tq 는 No errors detected in compressed data of poked.apk, --min-sdk-version 21 --max-sdk-version 23 검증은 Verifies 와 v1 true, 24~27 범위는 DOES NOT VERIFY 와 APK Signature Scheme v2 signer #1: APK integrity check failed. CHUNKED_SHA256 digest mismatch, 기본 범위는 APK Signature Scheme v3 signer #1 의 같은 digest mismatch](/assets/img/android-mastery/p1c07/04-padding-byte-v1-vs-v2v3.png)

`resources.arsc`의 extra 필드는 8바이트 `35 d9 04 00 04 00 00 00`이다. apksigner가 정렬용으로 넣는 필드로, 리틀 엔디언 헤더 ID `0xd935`, 데이터 길이 4, 정렬 단위 4, 그리고 0 두 바이트로 되어 있다([ApkSigner.java 882~898행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkSigner.java#882)). 그 마지막 0을 1로 바꿨다. 파일 오프셋은 3835이고 `cmp`는 1부터 세서 3836으로 찍는다. 항목 내용은 그대로라 `unzip -t`는 오류를 내지 않는다. v1만 보는 범위(21~23)에서는 `Verifies`였고 v2를 보는 범위(24~27)에서는 `CHUNKED_SHA256 digest mismatch`, 기본 범위의 v3도 같은 불일치로 떨어졌다.

![source.android.com APK 서명 체계 v2 한국어 문서의 무결성 보호 콘텐츠 절. APK 를 1. ZIP 항목 콘텐츠(오프셋 0부터 APK 서명 블록 시작 지점까지), 2. APK 서명 블록, 3. ZIP 중앙 디렉터리, 4. 중앙 디렉터리의 ZIP 끝으로 나눈 색 막대 그림과, v2 가 섹션 1, 3, 4 및 섹션 2 안의 v2 블록 signed data 의 무결성을 보호한다는 문장](/assets/img/android-mastery/p1c07/09-web-v2-integrity-sections.png)

[v2 문서](https://source.android.com/docs/security/features/apksigning/v2#integrity-protected-contents)는 서명된 APK를 ZIP 항목 내용, APK 서명 블록, central directory, EOCD 네 구역으로 나누고 그중 1, 3, 4번 구역을 1MB 단위 청크 다이제스트로 보호한다. 1번 구역은 오프셋 0부터 서명 블록 직전까지의 모든 바이트라서 로컬 파일 헤더와 그 안의 패딩도 들어간다. v1은 `MANIFEST.MF`에 항목별 다이제스트를 적어 두고 `.SF`와 `.RSA`로 그 목록을 서명하는 방식이라 헤더 바이트는 보지 않는다. [APK 서명 개요](https://source.android.com/docs/security/features/apksigning)도 v1이 ZIP 메타데이터를 보호하지 않는다고 적는다.

## jarsigner 시절에 정렬을 나중에 한 이유

v1만 쓰던 시절에는 순서가 반대였다. Android Studio에 딸린 JBR(OpenJDK 21.0.10)의 jarsigner로 v1만 서명하고 그다음에 zipalign을 돌려 봤다.

```bash
cp unsigned.apk jar.apk
jarsigner -keystore debug.keystore -storepass android -digestalg SHA-256 -sigalg SHA256withRSA jar.apk androiddebugkey | head -1
zipalign -c -P 16 -v 4 jar.apk | grep -E "arsc|\.so"
zipalign -P 16 -f 4 jar.apk jar-aligned.apk
zipalign -c -P 16 -v 4 jar-aligned.apk | grep -E "arsc|\.so"
jarsigner -verify jar-aligned.apk | grep verified
apksigner verify -v jar-aligned.apk
cp -r work work29
sed -i 's/targetSdkVersion: 33/targetSdkVersion: 29/' work29/apktool.yml
apktool b -q -p fw work29 -o unsigned29.apk
cp unsigned29.apk jar29.apk
jarsigner -keystore debug.keystore -storepass android -digestalg SHA-256 -sigalg SHA256withRSA jar29.apk androiddebugkey | head -1
zipalign -P 16 -f 4 jar29.apk jar29-aligned.apk
apksigner verify -v jar29-aligned.apk | head -2
```

![cp unsigned.apk jar.apk 뒤 jarsigner -digestalg SHA-256 -sigalg SHA256withRSA 가 jar signed., zipalign -c 가 5887 resources.arsc (BAD - 3), 6580 lib/x86_64/libresign.so (BAD - 6580), zipalign -P 16 -f 4 뒤 5888 resources.arsc (OK), 16384 lib/x86_64/libresign.so (OK), jarsigner -verify 가 jar verified., apksigner verify -v jar-aligned.apk 가 DOES NOT VERIFY 와 ERROR: Target SDK version 33 requires a minimum of signature scheme v2; the APK is not signed with this or a later signature scheme, apktool.yml 의 targetSdkVersion 을 29 로 바꿔 만든 jar29-aligned.apk 는 Verifies 와 v1 true](/assets/img/android-mastery/p1c07/05-jarsigner-v1-align-after.png)

jarsigner는 정렬을 신경 쓰지 않아서 서명 직후 resources.arsc가 `BAD - 3`, `.so`가 `BAD - 6580`이다. 그 뒤에 zipalign을 돌리면 둘 다 맞춰지고 `jar verified.`도 그대로다. v1이 지키는 건 항목 내용과 `META-INF` 파일이라 extra 필드 길이가 바뀌어도 서명은 멀쩡하고 그래서 문서도 jarsigner에는 반대 순서를 시킨다.

다만 이 APK는 apksigner 검증에서 `Target SDK version 33 requires a minimum of signature scheme v2`로 떨어졌다. `apktool.yml`의 targetSdk만 29로 바꿔 다시 묶은 사본은 같은 절차로 `Verifies`, v1 `true`가 나왔다.

## 깨뜨린 APK를 기기에 올리면

호스트에서 깨뜨린 APK들을 debug 키로 서명한 `repacked.apk` 위에 `install -r`로 올렸다. targetSdk 29 사본에도 서명 뒤 zipalign을 적용해 같이 넣었다.

```bash
apksigner sign --ks debug.keystore --ks-pass pass:android --out signed29.apk unsigned29.apk
zipalign -P 16 -f 4 signed29.apk signed29-then-aligned.apk
adb -s $S install -r signed-then-aligned.apk
adb -s $S install -r signed29-then-aligned.apk
adb -s $S install -r poked.apk
adb -s $S install -r jar-aligned.apk
adb -s $S install -r jar29-aligned.apk
```

![adb install -r 결과. signed-then-aligned.apk 와 signed29-then-aligned.apk 는 둘 다 Failure INSTALL_PARSE_FAILED_NO_CERTIFICATES: Failed to collect certificates from /data/app/vmdl...tmp/base.apk: META-INF/ANDROIDD.SF indicates ... is signed using APK Signature Scheme v2, but no such signature was found. Signature stripped?, poked.apk 는 Failed to collect certificates ... using APK Signature Scheme v3: SHA-256 digest of contents did not verify, jar-aligned.apk 는 INSTALL_PARSE_FAILED_NO_CERTIFICATES: Scanning Failed.: No signature found in package of version 2 or newer for package io.seika.resign, jar29-aligned.apk 는 Success](/assets/img/android-mastery/p1c07/11-device-install-rejections.png)

targetSdk 33인 `signed-then-aligned.apk`는 `No APK Signature Scheme v2 signature in package`로 막힐 거라고 봤다. [ApkSignatureVerifier.java 514~519행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSignatureVerifier.java#514)의 `getMinimumSignatureSchemeVersionForTargetSdk()`가 targetSdk 30 이상에는 v2를 최소 스킴으로 정한다. 그러면 같은 파일 138~181행의 대체 경로는 v2를 못 찾은 시점에 [165~167행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSignatureVerifier.java#165)에서 그 문구로 멈추고 v1까지 내려가지 않는다. 실제로는 targetSdk 29 사본과 똑같이 v1 검증기의 `Signature stripped?`가 나왔다.

설치 세션이 처음 인증서를 모으는 가벼운 파싱 단계에서는 아직 앱의 targetSdk를 모른다. [ApkLiteParseUtils.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/parsing/ApkLiteParseUtils.java#370)는 370~373행에서 `DEFAULT_TARGET_SDK_VERSION`(77행, 값 0)을 넘긴다. 받는 쪽 [FrameworkParsingPackageUtils.java 226~243행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/parsing/FrameworkParsingPackageUtils.java#226)이 그 값으로 최소 스킴을 정하니 JAR까지 허용된다. v3도 v2도 없으니 v1 검증기 [StrictJarVerifier.java 422~445행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/jar/StrictJarVerifier.java#422)에 이르고 `.SF`의 `X-Android-APK-Signed` 목록에서 처음 만난 2에서 멈춰 v2 메시지 하나만 던진다. 호스트의 apksigner가 v2와 v3를 각각 한 줄씩 낸 것과 다른 부분이다.

`poked.apk`는 `using APK Signature Scheme v3: SHA-256 digest of contents did not verify`로 막혔다. 기기는 v3 서명을 찾았으니 아래로 내려가지 않았고 [ApkSigningBlockUtils.java 176~181행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSigningBlockUtils.java#176)에서 계산한 다이제스트가 서명된 값과 달랐다.

v1만 서명한 두 APK는 결과가 갈렸다. targetSdk 33인 `jar-aligned.apk`는 `Scanning Failed.: No signature found in package of version 2 or newer for package io.seika.resign`, targetSdk 29인 `jar29-aligned.apk`는 `Success`다. 가벼운 파싱은 v1 서명만으로 통과했고 패키지를 스캔하는 [ScanPackageUtils.java 690~700행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/ScanPackageUtils.java#690)이 실제 targetSdk로 최소 스킴을 다시 계산해 막았다. `Scanning Failed.`라는 접두어는 [InstallPackageHelper.java 978행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/InstallPackageHelper.java#978)이 붙인다. 5장에서 apksigner로 v1만 넣은 `v1only.apk`가 막힌 문구도 이것이었다. 같은 Android 13 기기에서 targetSdk만 다른 두 APK가 다르게 처리됐으니 v2 요구는 기기 버전보다 앱의 targetSdk를 따른다. [Android 11 동작 변경 문서](https://developer.android.com/about/versions/11/behavior-changes-11)도 이 요구의 대상을 Android 11(API 30) 이상을 타깃으로 하는 앱으로 적는다.

## 지금 apksigner는 서명하면서 정렬한다

`signed.apk`가 왜 이미 정렬돼 있었는지 확인하려고 정렬하지 않은 같은 `unsigned.apk`를 build-tools 버전별 apksigner로 서명했다. Windows라 SDK 안의 실행 파일 이름이 `apksigner.bat`이다.

```bash
zipalign -c -P 16 -v 4 unsigned.apk | grep -E "arsc|\.so"
$ANDROID_HOME/build-tools/34.0.0/apksigner.bat sign --ks debug.keystore --ks-pass pass:android --out bt34.apk unsigned.apk
zipalign -c -P 16 -v 4 bt34.apk | grep -E "arsc|\.so"
$ANDROID_HOME/build-tools/35.0.0/apksigner.bat sign --ks debug.keystore --ks-pass pass:android --out bt35.apk unsigned.apk
zipalign -c -P 16 -v 4 bt35.apk | grep -E "arsc|\.so"
python lhextra.py aligned.apk lib/x86_64/libresign.so
python lhextra.py repacked.apk lib/x86_64/libresign.so
apksigner sign --alignment-preserved --ks debug.keystore --ks-pass pass:android --out preserved.apk unsigned.apk
zipalign -c -P 16 -v 4 preserved.apk | grep -E "arsc|\.so"
```

![정렬하지 않은 unsigned.apk 는 3828 resources.arsc (OK), 4521 lib/x86_64/libresign.so (BAD - 4521). build-tools/34.0.0 의 apksigner.bat 로 만든 bt34.apk 도 .so 가 BAD - 4521, build-tools/35.0.0 으로 만든 bt35.apk 는 3836 resources.arsc (OK), 16384 lib/x86_64/libresign.so (OK). lhextra.py 로 본 aligned.apk 의 .so extra 는 header@4468 extra@4521 len=11863 에 00 00 00 00 ..., data@16384, repacked.apk 는 header@4476 extra@4529 len=11855 에 35 d9 4b 2e 00 40 00 00 ..., data@16384. apksigner sign --alignment-preserved 로 만든 preserved.apk 는 .so 가 BAD - 4521](/assets/img/android-mastery/p1c07/06-apksigner-realigns.png)

build-tools 34.0.0의 apksigner는 `.so`를 `BAD - 4521`로 그대로 두었고 35.0.0은 16384로 옮겼다. resources.arsc도 3828에서 3836으로 움직였는데 여전히 4의 배수다. 2023년 11월의 apksig 커밋 [f1682ab](https://android.googlesource.com/platform/tools/apksig/+/f1682abcc0752e3231fc65f727f94b4f821e2d05) "Set defaults to align native libraries to 16k"가 이 동작을 넣었다. 기존 정렬을 보존하던 기본값을 바꿔서 네이티브 라이브러리는 16KiB 경계에, 압축하지 않은 나머지 파일은 4바이트에 맞춘다. 페이지 크기는 [Constants.java 46행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/Constants.java#46)의 `LIBRARY_PAGE_ALIGNMENT_BYTES = 16384`이고 [ApkSigner.java 752~799행](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkSigner.java#752)은 `mAlignmentPreserved`가 꺼져 있으면 압축하지 않은 항목마다 extra 필드를 새로 만들어 데이터를 옮긴다. [build-tools 릴리스 노트](https://developer.android.com/tools/releases/build-tools)에는 35와 36에 해당하는 항목이 없어서 어느 릴리스부터인지는 34.0.0과 35.0.0을 비교한 결과와 커밋 날짜로만 말할 수 있다.

![android.googlesource.com 의 platform/tools/apksig 커밋 f1682abcc0752e3231fc65f727f94b4f821e2d05 페이지. author Michael Groover, Fri Nov 03 2023, 메시지 제목 Set defaults to align native libraries to 16k 와 본문 to not preserve existing alignment for files within an APK, but instead native library files will be aligned on a 16k boundary and all other uncompressed files will use 4 bytes, 아래에 바뀐 파일 ApkSignerTool.java, help_sign.txt, ApkSigner.java, Constants.java](/assets/img/android-mastery/p1c07/07-web-apksig-16k-commit.png)

zipalign이 만든 패딩도 그대로 두지 않는다. zipalign만 거친 `aligned.apk`에서 `.so`의 extra 필드는 11863바이트가 모두 0인데, 그것을 서명한 `repacked.apk`에서는 11855바이트이고 `35 d9 4b 2e 00 40`으로 시작한다. 헤더 ID `0xd935`, 데이터 길이 `0x2e4b`(11851), 정렬 단위 `0x4000`(16384)인 apksigner 자신의 정렬 필드다. `--alignment-preserved`를 주면 옛 동작대로 `.so`가 `BAD - 4521`로 남는다. 서명 전 zipalign이 남긴 패딩이 결과물에 살아남는 건 이 옵션을 주거나 build-tools 34 이하로 서명할 때다.

## 정렬이 어긋나면 기기는 어디서 막나

정렬을 빼먹으면 무엇이 깨지는지 보려고 `--alignment-preserved`로 서명해 어긋난 배치를 일부러 남긴 APK를 깔았다. `build-unsigned.apk`는 처음 빌드의 정렬·서명 전 파일이라 resources.arsc와 `.so`가 둘 다 어긋나 있다. apktool 결과물인 `unsigned.apk`는 `.so`만 어긋나 있다.

```bash
apksigner sign --alignment-preserved --ks debug.keystore --ks-pass pass:android --out noalign-arsc.apk build-unsigned.apk
zipalign -c -P 16 -v 4 noalign-arsc.apk | grep -E "resources|\.so"
adb -s $S install -r noalign-arsc.apk
apksigner sign --alignment-preserved --ks debug.keystore --ks-pass pass:android --out noalign-so.apk unsigned.apk
zipalign -c -P 16 -v 4 noalign-so.apk | grep -E "resources|\.so"
adb -s $S logcat -c
adb -s $S install -r noalign-so.apk
adb -s $S logcat -d | grep -m1 "page-aligned"
```

![apksigner sign --alignment-preserved 로 만든 noalign-arsc.apk 는 889 resources.arsc (BAD - 1), 4548 lib/x86_64/libresign.so (BAD - 4548) 이고 install -r 이 Failure INSTALL_FAILED_INVALID_APK: Failed to extract native libraries, res=-2. noalign-so.apk 는 3828 resources.arsc (OK), 4521 lib/x86_64/libresign.so (BAD - 4521) 이고 같은 res=-2 실패, logcat 에 E NativeLibraryHelper: Library 'libresign.so' is not page-aligned - will not be able to open it directly from apk.](/assets/img/android-mastery/p1c07/12-device-alignment.png)

`noalign-arsc.apk`라고 이름을 붙였지만 첫 설치를 막은 건 `.so`였다. `.so`만 어긋난 `noalign-so.apk`도 같은 `Failed to extract native libraries, res=-2`였고 logcat에 `NativeLibraryHelper: Library 'libresign.so' is not page-aligned - will not be able to open it directly from apk.`가 남았다. `extractNativeLibs="false"`인 앱의 라이브러리는 [NativeLibraryHelper.cpp 195~207행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/jni/com_android_internal_content_NativeLibraryHelper.cpp#195)에서 STORED인지, 데이터 오프셋이 `PAGE_SIZE`의 배수인지 검사받고 아니면 `INSTALL_FAILED_INVALID_APK`(-2)가 돌아온다. 그 값을 [PackageInstallerSession.java 3441~3447행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/PackageInstallerSession.java#3441)이 `Failed to extract native libraries, res=`로 감싼다. 이 에뮬레이터 이미지의 `PAGE_SIZE`는 4096이다. 4KiB에만 맞춘 `.so`가 16KiB 페이지 기기에서 어떻게 되는지는 그런 기기가 없어 확인하지 못했다([16KB 페이지 크기 지원](https://developer.android.com/guide/practices/page-sizes)).

resources.arsc 규칙만 따로 보려면 `.so`는 맞고 arsc만 어긋난 APK가 필요했다. zipalign의 `<align>`을 1로 주면 일반 항목은 제자리에 두고 `-P 16`에 따라 `.so`만 페이지에 맞춘다.

```bash
zipalign -P 16 -f 1 build-unsigned.apk arsc-unaligned.apk
apksigner sign --alignment-preserved --ks debug.keystore --ks-pass pass:android --out noalign-arsc-only.apk arsc-unaligned.apk
zipalign -c -P 16 -v 4 noalign-arsc-only.apk | grep -E "resources|\.so"
adb -s $S install -r noalign-arsc-only.apk
```

![zipalign -P 16 -f 1 build-unsigned.apk arsc-unaligned.apk 와 apksigner sign --alignment-preserved 로 만든 noalign-arsc-only.apk 가 889 resources.arsc (BAD - 1), 16384 lib/x86_64/libresign.so (OK) 이고, install -r 이 Failure -124: Failed parse during installPackageLI: Targeting R+ (version 30 and above) requires the resources.arsc of installed APKs to be stored uncompressed and aligned on a 4-byte boundary](/assets/img/android-mastery/p1c07/17-device-arsc-only.png)

이번에는 실패 코드가 상수 이름 없이 숫자로만 찍혔다(`-124: Failed parse during installPackageLI: Targeting R+ (version 30 and above) requires the resources.arsc of installed APKs to be stored uncompressed and aligned on a 4-byte boundary`). -124는 `INSTALL_PARSE_FAILED_RESOURCES_ARSC_COMPRESSED`다([PackageManager.java 2178행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/PackageManager.java#2178)). 메시지는 [ParsingPackageUtils.java 546~555행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java#546)에서 나오고 이 검사는 [ParseInput.java 71~72행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/parsing/result/ParseInput.java#71)의 `@EnabledAfter(targetSdkVersion = Q)`로 targetSdk 30 이상 앱에만 켜진다. 두 캡처를 합치면 이 이미지에서는 네이티브 라이브러리 정렬이 세션을 커밋할 때 먼저 걸리고 resources.arsc 규칙은 그 뒤 `installPackageLI`의 파싱에서 걸린다. Android 11 동작 변경 문서는 메모리에 바로 매핑할 수 없는 리소스 테이블이 RAM으로 복사돼 메모리를 더 쓰게 된다는 것을 이 규칙의 이유로 든다.

## 앱 안의 서명 검사는 APK 안의 상수 하나

`ResignLab`의 자체 검사는 리패키징 탐지에서 흔히 쓰는 형태다. 자기 서명 인증서의 해시를 구해 코드에 넣어 둔 릴리스 해시와 비교한다.

```java
// MainActivity.java 38~41행. RELEASE_CERT_SHA256(20행)은 빌드 스크립트가 릴리스 인증서의 SHA-256으로 채운다
        String signer = signerSha256();
        line("signer sha256", signer.substring(0, 16) + "..." + signer.substring(56));
        line("self-check", signer.equals(RELEASE_CERT_SHA256)
                ? "OK, signed with release key" : "MISMATCH, not the release key");
```

`signerSha256()`(56~68행)은 `GET_SIGNING_CERTIFICATES`로 받은 `getApkContentsSigners()`의 첫 인증서를 SHA-256으로 해시한다. 비교할 해시가 APK 안에 있으니 리패키징하는 쪽도 그 값을 고칠 수 있다. 앞에서 문자열을 바꿔 둔 `work/` 트리의 smali에서 릴리스 해시를 debug 키 해시로 바꾸고 다시 묶었다. root는 쓰지 않았다.

```bash
grep -c bd44d3879fe5cc3dff872e3e7d2c970e48211a6690ca77c05f897e88abf51c80 work/smali/io/seika/resign/MainActivity.smali
sed -i 's/bd44d3879fe5cc3dff872e3e7d2c970e48211a6690ca77c05f897e88abf51c80/7515cf75558219fb7402d88f9b5be302218da39997ad234eb823a8fc84895c53/' work/smali/io/seika/resign/MainActivity.smali
apktool b -q -p fw work -o unsigned-selfcheck.apk
zipalign -P 16 -f 4 unsigned-selfcheck.apk aligned-selfcheck.apk
apksigner sign --ks debug.keystore --ks-pass pass:android --out selfcheck-patched.apk aligned-selfcheck.apk
adb -s $S install -r selfcheck-patched.apk
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.resign/.MainActivity | grep Status
adb -s $S logcat -d -v raw -s ResignLab:I
```

![grep -c 로 MainActivity.smali 에서 릴리스 해시 bd44d3879fe5...abf51c80 가 2 번 나오고, sed 로 debug 키 해시 7515cf75558219fb...84895c53 로 바꾼 뒤 apktool b -q -p fw work, zipalign -P 16 -f 4, apksigner sign 으로 selfcheck-patched.apk 를 만들어 install -r 이 Success. logcat 은 label: build: repackaged, signer sha256: 7515cf75558219fb...84895c53, self-check: OK, signed with release key, vault permission: DENIED, vault exception: Permission Denial ... requires io.seika.vault.permission.READ, vault query: SecurityException, native: libresign.so loaded](/assets/img/android-mastery/p1c07/13-device-selfcheck-patched.png)

해시는 smali에 두 번 나온다. `static final` 필드의 초깃값(7행)과, javac가 컴파일 타임 상수를 인라인해 넣은 `onCreate`의 `const-string`(513행)이다. 둘 다 바꾸고 같은 debug 키로 서명하자 `install -r`이 성공했고 서명자는 여전히 `7515cf75…84895c53`인데 자체 검사는 `OK, signed with release key`를 찍었다.

vault 권한은 플랫폼이 서명자를 직접 비교해 정하므로 `DENIED` 그대로였다. 원본이 깔려 있을 때 `dumpsys package`로 보면 두 앱 모두 `signatures:[41b7cfa1]`이었고 `io.seika.resign`에는 `io.seika.vault.permission.READ: granted=true`가 찍혔다. 같은 상태에서 뜬 전체 `dumpsys package` 출력에서 서명과 그 권한 줄만 추리면 이렇다.

```bash
adb -s $S shell dumpsys package io.seika.resign | grep -E "signatures|io.seika.vault.permission.READ"
```

```text
    signatures=PackageSignatures{609c9f9 version:3, signatures:[8f0ad5a3], past signatures:[]}
      io.seika.vault.permission.READ
      io.seika.vault.permission.READ: granted=false
```

서버 쪽에서는 Play Integrity의 `appRecognitionVerdict`가 앱과 인증서가 Play 배포본과 맞으면 `PLAY_RECOGNIZED`, 인증서나 패키지 이름이 Play 기록과 다르면 `UNRECOGNIZED_VERSION`을 준다([판정 문서](https://developer.android.com/google/play/integrity/verdicts), [Play Integrity(C48)](/posts/android-concept-atlas-c48-play-integrity/)). 판정 토큰은 앱 서버가 Google 서버에 보내 복호화하거나(기본) 자체 키로 직접 복호화해 검증하니 앱 안의 상수처럼 고쳐 넘기기 어렵지만, Play 배포본도 Play Integrity가 붙은 이미지도 없어 여기서는 측정하지 못했다. Google Cloud API 키의 패키지 이름·SHA-1 제한은 그 값을 요청의 `X-Android-Package`, `X-Android-Cert` 헤더로 받는데, 리패키징한 앱이 원본 값을 그대로 실어 보내면 막을 방법이 없어 보인다. 여기서 시험하지는 않았다. [API 키 문서](https://cloud.google.com/docs/authentication/api-keys)도 API 제한과 사용량 감시를 같이 걸라고 권한다.

재서명이 TLS certificate pinning을 깬다는 말도 종종 보는데 Network Security Config의 pin-set은 APK 안 `res/xml`에 있는 리소스라 서명과는 상관이 없다. 리패키징하는 쪽은 `strings.xml`을 바꾼 것처럼 그 파일도 고칠 수 있다([TLS·NSC 피닝(C46)](/posts/android-concept-atlas-c46-tls-nsc-pinning/)). 리패키징한 앱으로 실제로 무엇을 노리고 막는지는 5부 2장에서 다시 다룬다.

## 막혔을 때 메시지로 원인 찾기

| 메시지 | 원인 | 처리 |
|---|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 설치된 앱과 서명자가 다르다 | 원래 키로 서명한다. 키가 없으면 앱 데이터를 포기하고 uninstall 뒤 설치 |
| `Signature stripped?` | 서명한 APK를 zipalign 같은 도구가 다시 썼다 | 서명 전 APK에서 정렬과 서명을 다시 한다 |
| `digest of contents did not verify` | 서명 뒤 바이트가 바뀌었다(패딩 포함) | 서명 전 APK에서 다시 만든다 |
| `verify -v`의 v1, v2 `false` | 그 SDK 범위에서 확인하지 않았다 | `--min-sdk-version 21`로 범위를 넓혀 본다 |
| `version 2 or newer` | targetSdk 30 이상인데 v1 서명뿐이다 | apksigner로 v2 이상을 넣는다 |
| `res=-2` (native libraries) | `extractNativeLibs`가 false인데 `.so`가 압축돼 있거나 페이지 경계에 없다 | `.so`를 STORED로 두고 `zipalign -P 16`, 또는 정렬하는 apksigner |
| `-124` (resources.arsc) | resources.arsc가 압축돼 있거나 4바이트 경계에 없다 (targetSdk 30 이상) | 압축하지 않고(doNotCompress) `<align>` 4로 정렬한다 |

참고 자료: [zipalign](https://developer.android.com/tools/zipalign) · [apksigner](https://developer.android.com/tools/apksigner) · [APK 서명 개요](https://source.android.com/docs/security/features/apksigning) · [APK Signature Scheme v2](https://source.android.com/docs/security/features/apksigning/v2) · [APK Signature Scheme v4](https://source.android.com/docs/security/features/apksigning/v4) · [Android 11 동작 변경](https://developer.android.com/about/versions/11/behavior-changes-11) · [APK 서명 v1~v4(C08)](/posts/android-concept-atlas-c08-apk-signing/) · [DEX·multidex·resources.arsc(C07)](/posts/android-concept-atlas-c07-dex-multidex-resources-arsc/)

*다음 글: [Frida spawn/attach와 Java hook](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)*
