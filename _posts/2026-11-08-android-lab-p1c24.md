---
layout: post
title: "MobSF 결과 손으로 검증하기 — 정답을 아는 앱으로 오탐과 미탐 가르기"
date: 2026-11-08 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, MobSF, 정적분석, 오탐, 미탐, Frida, MASTG]
excerpt: "취약점을 심어 둔 자작 앱을 MobSF v4.5.3으로 스캔하고 경보를 하나씩 기기에서 확인했다. 시크릿 두 개 중 하나는 아무도 부르지 않는 클래스에 있었고 ECB 경보는 실제 호출 세 곳 중 한 곳만 잡았으며, 같은 warning을 받은 액티비티 중 하나가 인증 우회였다. 매니페스트에 없는 런타임 리시버로 로그인 상태를 바꾸는 경로는 리포트에 아예 없었다."
---

[23장](/posts/android-lab-p1c23-flutter-reactnative-cordova/)에서는 로직이 DEX 밖에 있는 앱을 열었다. 이번에는 도구 쪽을 본다. MobSF 같은 자동 스캐너는 APK 하나를 넣으면 몇십 초 만에 점수와 경보 목록을 내놓는데, 그 목록에서 어느 경보가 왜 틀리고 무엇이 빠지는지는 직접 가려 보기 전에는 알기 어렵다.

공개 취약앱으로 해 보면 정답지가 없어서 "이건 오탐 같다"에서 멈추게 된다. 그래서 정답을 아는 앱을 직접 만들었다. `io.seika.scanlab` 은 MobSF가 잡는 부류마다 진짜 결함, 무해한 패턴, 스캐너가 못 볼 만한 변형을 하나씩 심은 Java 앱이고, `io.seika.scanprobe` 는 다른 서명 키로 서명한 권한 없는 공격자 앱이다. 둘 다 `mkapk` 로 빌드했고 minSdk 26, targetSdk 33이다. 심어 둔 것은 이렇다.

| 심은 것 | 위치 | 실제 상태 |
|--|--|--|
| `LEGACY_API_KEY`, http `OLD_ENDPOINT`, `md5()` | `Legacy.java` | 어디서도 참조하지 않는 클래스 |
| HMAC 키 `SIGNING_KEY`, `http://10.0.2.2:8088` 동기화 | `ApiClient.java` | 로그인할 때마다 평문 HTTP로 서명해 전송 |
| `Cipher.getInstance("AES/ECB/...")` 리터럴 | `CredentialStore.java` | 로그인 시 PIN 저장 |
| 같은 ECB, 변환 문자열을 `static final` 필드에 | `TokenCache.java` | 동기화 본문에 사용 |
| 같은 ECB, 리플렉션과 `'E','C','B'` 문자 배열 | `ExportHelper.java` | VaultActivity가 호출 |
| 권한 없는 exported, 로그인 확인 없음 | `VaultActivity` | 인증 우회 |
| 권한 없는 exported, 정적 문구만 | `AboutActivity` | 열려 있지만 무해 |
| 사용자 정의 `signature` 권한 | `SyncActivity` | 제3자 앱 도달 불가 |
| 사용자 정의 `normal` 권한, 키와 prefs 덤프 | `DebugActivity` | 아무 앱이나 권한 요청 가능 |
| `WRITE_SECURE_SETTINGS` 가드 | `AdminActivity` | 제3자 앱 불가, adb shell 가능 |
| exported=false, JS 브리지를 리플렉션으로 등록 | `HelpActivity` | 앱 내부에서만 |
| 런타임 `registerReceiver(..., RECEIVER_EXPORTED)` | `App.java` | 매니페스트에 없음, scanlab 프로세스가 살아 있는 동안 아무 앱이나 로그인 상태 조작 |

MobSF는 v4.5.3(커밋 `d3869ad`)을 WSL에서 소스로 띄우고 REST API로 업로드와 스캔을 했다. Docker 이미지로도 같은 버전을 받을 수 있지만 이번에 돌린 것은 소스 실행본이다. 기기 쪽은 `codex-atlas-api33` 에뮬레이터(Android 13, `TE1A.240213.009`, userdebug)이고, 이번 부팅에서 scanlab은 uid 10179, scanprobe는 uid 10180을 받았다. 역컴파일은 jadx 1.5.5와 apktool, 런타임 확인은 Frida 17.17.0이다. 앞 장들의 [jadx 정적 분석](/posts/android-lab-p1c04-jadx-static-analysis/), [smali](/posts/android-lab-p1c05-apktool-smali/), [매니페스트 공격면](/posts/android-lab-p1c06-manifest-attack-surface-mapping/), [Frida 훅](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)을 그대로 쓴다.

## MobSF가 준 숫자: 점수 44, 매니페스트 경보 8줄, 코드 경보 5줄

스캔은 41초 정도 걸렸고 리포트의 `security_score` 는 44였다. 매니페스트 분석은 high 1, warning 6에 SyncActivity 줄이 info로 하나 더 붙었다.

![MobSF v4.5.3 MANIFEST ANALYSIS 표. HIGH 1, WARNING 6. minSdk=26 warning, usesCleartextTraffic=true high, allowBackup warning, VaultActivity와 AboutActivity is not Protected warning, SyncActivity는 SYNC signature 권한으로 info, DebugActivity는 DEBUG normal 권한 warning, AdminActivity는 WRITE_SECURE_SETTINGS 권한이 분석한 앱에 정의되지 않았다는 warning](/assets/img/android-mastery/p1c24/01-mobsf-manifest-analysis.png)

여기서 벌써 눈에 걸리는 게 있다. VaultActivity와 AboutActivity가 똑같은 문구, 똑같은 warning을 받았다. 하나는 비밀 메모를 보여 주는 화면이고 하나는 정적 문구 화면인데, 매니페스트만 보는 규칙이 둘을 구별할 방법은 없다. AdminActivity 줄은 "권한이 이 앱에 정의되지 않았으니 보호 수준을 확인하라"고 말한다. MobSF는 앱 안에 정의된 권한만 보호 수준을 읽고, 플랫폼 권한은 [`exported_protected_permission_not_defined`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/android/manifest_analysis.py#L445) 로 분류만 하고 넘긴다. 그 권한이 서드파티 앱은 받을 수 없는 `WRITE_SECURE_SETTINGS` 라는 사실은 리포트에 반영되지 않는다.

코드 분석은 ECB 하나가 high, IP 노출과 하드코딩, MD5가 warning, 로깅이 info였다.

![MobSF CODE ANALYSIS 표. HIGH 1 WARNING 3 INFO 1. ECB 모드 경보 high는 CredentialStore.java 하나만, IP Address disclosure는 ApiClient.java와 HelpActivity.java, 로깅 info, 하드코딩 민감정보 warning은 ApiClient.java와 Legacy.java, MD5 warning은 Legacy.java](/assets/img/android-mastery/p1c24/02-mobsf-code-analysis.png)

시크릿 칸에는 문자열 두 개가 나왔다.

![MobSF POSSIBLE HARDCODED SECRETS. Showing all 2 secrets, 6589af8494117d6fe9913f1e3bfaf479와 Uvp3QKi1BI/UN27PvXGWKS6oXd2AHWRV](/assets/img/android-mastery/p1c24/03-mobsf-secrets.png)

URL 목록에는 죽은 코드의 `http://legacy.example.invalid/api/v0/login` 과 실제로 쓰는 `http://10.0.2.2:8088/api/v1/notes/sync` 가 아무 구분 없이 나란히 있었다.

## 시크릿 두 개 중 하나는 아무도 부르지 않는다

먼저 MobSF가 시크릿을 어떻게 고르는지 봐야 판정 기준이 선다. "정규식 기반"이라고 흔히 말하지만 v4.5.3의 시크릿 칸은 그보다 넓다. [`strings_and_entropies`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/common/shared_func.py#L476-L512) 가 역컴파일한 소스에서 문자열 리터럴을 모으고, [`get_secrets`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/common/secret_detection.py#L199) 가 알려진 키 형식 패턴과 [Shannon 엔트로피](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/common/entropy.py#L53)로 걸러 낸다. 코드 분석 쪽의 하드코딩 경보는 또 다른 규칙인 [`android_hardcoded`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/android/rules/android_rules.yaml#L772-L779) 로, 소문자로 바꾼 소스에서 `key = "…"` 같은 이름 대입을 찾는 정규식이다. 어느 쪽도 그 값이 쓰이는지는 보지 않는다.

그래서 사용처를 직접 따라갔다.

![jadx로 scanlab.apk를 jsrc에 풀고 jsrc/sources/io/seika/scanlab 경로로 grep한 터미널. 6589af84는 Legacy.java:7 LEGACY_API_KEY 선언에만 있고 LEGACY_API_KEY, OLD_ENDPOINT, Legacy. 를 Legacy.java 밖에서 찾는 grep은 아무것도 출력하지 않는다. SIGNING_KEY는 ApiClient.java:19 mac.init HmacSHA256과 HelpActivity.java:15에서 쓰이고 DebugActivity.java:7에는 값이 인라인돼 있다. ApiClient.java:29 http://10.0.2.2:8088/api/v1/notes/sync openConnection, :33 X-Signature 헤더. SecretKeySpec 리터럴은 CredentialStore.java:11 scanlab-device-k, ExportHelper.java:18 export-key-2026!, TokenCache.java:13 token-cache-key!](/assets/img/android-mastery/p1c24/04-secrets-xref.png)

`6589af84…` 는 `Legacy.java:7` 의 선언에만 있고, `Legacy` 클래스나 그 상수를 바깥에서 참조하는 줄은 하나도 없다. 다만 이름 grep만으로는 부족하다. 두 상수는 `public static final String` 컴파일 타임 상수라 javac가 쓰는 곳에 값을 인라인한다. 같은 캡처에서 `DebugActivity.java:7` 에 `SIGNING_KEY` 이름 대신 값이 박혀 있는 게 그 예다. 그래서 결정적인 건 값 grep이 선언 한 줄만 찾았다는 것과 `Legacy.md5` 를 부르는 줄이 없다는 것이다. legacy URL도 MobSF URL 목록에서 출처가 `Legacy.java` 하나뿐이다. 이 키와 같은 클래스의 MD5 경보, legacy URL은 코드에 존재하는 것은 맞지만 실행 경로에 없다. 보고서에 올린다면 "제거 권고" 정도가 맞다.

`Uvp3QKi1…` 는 반대다. `ApiClient.java:19` 에서 `HmacSHA256` 키로 들어가고, 그 서명이 `:33` 의 `X-Signature` 헤더가 되어 `:29` 의 평문 http URL로 나간다. 정적으로는 여기까지가 추론이니 실제로 돌려 봤다. 호스트에 `127.0.0.1:8088` 을 여는 작은 서버(`sync_server.py`)를 띄우고 에뮬레이터에서 PIN 2468로 로그인하게 했다. 에뮬레이터에서 `10.0.2.2` 는 호스트의 루프백이다. 서버는 받은 본문으로 HMAC-SHA256을 다시 계산하는데, 키로는 MobSF 시크릿 칸에 찍힌 문자열을 그대로 썼다.

```python
KEY = b"Uvp3QKi1BI/UN27PvXGWKS6oXd2AHWRV"  # value from MobSF "Possible hardcoded secrets"
# ...
        want = base64.b64encode(hmac.new(KEY, body, hashlib.sha256).digest()).decode()
        print(f"  HMAC-SHA256(MobSF secret, body) matches: {hmac.compare_digest(sig, want)}", flush=True)
```

로그인 조작은 `uiautomator dump` 로 PIN 칸과 버튼 좌표를 얻어 탭하는 스크립트다.

```bash
#!/usr/bin/env bash
# Log in to scanlab through its UI (PIN 2468). usage: bash scripts/login.sh SERIAL
set -e
S=$1
# --activity-clear-task: a VaultActivity left on top of the task hid the PIN field once
adb -s $S shell am start -W --activity-clear-task -n io.seika.scanlab/.MainActivity >/dev/null
sleep 2
adb -s $S shell uiautomator dump /sdcard/ui.xml >/dev/null
adb -s $S pull /sdcard/ui.xml raw/ui.xml >/dev/null
PIN_XY=$(python scripts/bounds.py raw/ui.xml android.widget.EditText 0)
BTN_XY=$(python scripts/bounds.py raw/ui.xml android.widget.Button 0)
adb -s $S shell input tap $PIN_XY
adb -s $S shell input text 2468
adb -s $S shell input tap $BTN_XY
echo "login.sh: PIN entered, login tapped"
```

`bounds.py` 는 덤프 XML에서 지정한 클래스의 n번째 노드 `bounds` 중심 좌표를 출력하는 아홉 줄짜리 스크립트다. 주석의 `--activity-clear-task` 는 한 번 데어서 넣은 것이다. 앞 실험에서 열어 둔 VaultActivity가 태스크 위에 남아 있으면 덤프에 EditText가 없어 탭할 곳을 못 찾는다.

![터미널. timeout 40 python scripts/sync_server.py --once 백그라운드 실행 후 listening on 127.0.0.1:8088, bash scripts/login.sh $S 는 adb pull 진행 줄과 login.sh: PIN entered, login tapped 출력. 서버가 POST /api/v1/notes/sync from 127.0.0.1, body user alice reason login cache 6odosOm5HniT0dc8M9TTOw==, X-Signature n0eM7rWsBJvIxorbPvcPSIphaZjYhZaQXwn/kpEk5Bw=, HMAC-SHA256(MobSF secret, body) matches: True 출력. logcat에 login ok, VaultActivity shown referrer=android-app://io.seika.scanlab, sync POST -> HTTP 200](/assets/img/android-mastery/p1c24/10-cleartext-sync.png)

`matches: True` 가 나왔다. MobSF가 뽑은 문자열은 실제로 쓰이는 서명 키이고, 그 키로 서명한 요청이 평문 HTTP로 나간다. 같은 트래픽을 가로챈 사람은 본문을 읽을 수 있고, 키를 APK에서 꺼냈으니 임의 본문에 유효한 서명을 붙일 수도 있다. 매니페스트의 cleartext high 경보도 이 요청으로 참이 확정됐다. 참고로 cleartext 기본값은 [`NetworkSecurityConfig.java#187`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/security/net/config/NetworkSecurityConfig.java#187) 에서 targetSdk가 28 미만이고 인스턴트 앱이 아닐 때만 허용인데, scanlab은 `usesCleartextTraffic="true"` 를 직접 켰으니 기본값과는 상관없다.

시크릿 칸이 놓친 것도 같은 캡처 맨 아래에 있다. `SecretKeySpec("scanlab-device-k"...)`, `"token-cache-key!"`, `"export-key-2026!"` 는 세 곳 모두 실제 AES 키로 쓰이는데 시크릿 칸에도 하드코딩 경보에도 없다. 사람이 읽을 수 있는 16바이트 문자열이라 엔트로피 기준을 넘지 못하고, `key = "…"` 꼴 대입도 아니어서 정규식에도 안 걸린 것으로 보인다. 시크릿 칸이 비어 있어도 하드코딩 키는 있을 수 있으니 `SecretKeySpec(`, `Mac.init`, `IvParameterSpec(` 같은 암호 API 인자를 따로 검색한다.

## ECB 경보는 실제 호출 세 곳 중 한 곳만 잡았다

ECB 경보 규칙 [`android_aes_ecb`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/android/rules/android_rules.yaml#L565-L573) 는 jadx가 만든 Java 소스 위를 도는 정규식 하나다. 같은 패턴을 같은 소스에 직접 돌려 봤다.

![터미널. GitHub v4.5.3 android_rules.yaml에서 꺼낸 android_aes_ecb 패턴 Cipher\.getInstance\(\s*"\s*AES\/ECB. 같은 정규식 grep은 CredentialStore.java:12 하나만 맞는다. TokenCache.java:12는 Cipher.getInstance(TRANSFORMATION), ExportHelper.java:17은 cls.getMethod("getInstance", String.class).invoke(null, str2). apktool smali의 TokenCache.smali:7에는 static final TRANSFORMATION 필드 값 AES/ECB/PKCS5Padding, :29 const-string v0 "AES/ECB/PKCS5Padding", :31 invoke-static Cipher;->getInstance](/assets/img/android-mastery/p1c24/05-ecb-rule-vs-code.png)

패턴은 `getInstance(` 바로 뒤에 `"AES/ECB` 리터럴이 와야 맞는다. `CredentialStore` 만 그 모양이다. `TokenCache` 는 smali를 보면 재미있다. `TRANSFORMATION` 은 컴파일 타임 상수라 javac가 호출 지점에 `const-string v0, "AES/ECB/PKCS5Padding"` 으로 값을 인라인했는데, jadx는 같은 값의 `static final` 필드가 있는 걸 보고 역컴파일 결과에 필드 이름을 되살렸다. 바이트코드에는 리터럴이 있고 MobSF가 읽는 Java에는 없다. `ExportHelper` 는 변환 문자열을 실행 중에 문자 배열로 조립하고 `Class.forName` 과 `getMethod("getInstance", ...)` 로 부르니 어떤 정적 패턴에도 리터럴이 남지 않는다. ECB 경보는 없고, `ExportHelper.java` 는 `api_crypto`, `api_java_reflection` 같은 info 등급 API 목록에만 이름이 올랐다.

정말 세 곳이 다 실행되는지는 Frida로 `Cipher.getInstance(String)` 을 걸어 확인했다. 훅은 호출 스택에서 처음 나오는 `io.seika.*` 프레임을 같이 찍는다.

```javascript
// Log every Cipher.getInstance(String) with the first io.seika.* frame that asked for it.
Java.perform(function () {
  var Cipher = Java.use('javax.crypto.Cipher');
  var Thread = Java.use('java.lang.Thread');
  Cipher.getInstance.overload('java.lang.String').implementation = function (t) {
    var st = Thread.currentThread().getStackTrace();
    var caller = '?';
    for (var i = 0; i < st.length; i++) {
      var c = st[i].getClassName();
      if (c.indexOf('io.seika.') === 0) { caller = c + '.' + st[i].getMethodName(); break; }
    }
    console.log('[Cipher.getInstance] ' + t + '  <- ' + caller);
    return this.getInstance(t);
  };
  console.log('hooked Cipher.getInstance(String)');
});
```

첫 시도는 실패했다. frida-server를 띄우는 준비 스크립트가 `adb shell` 안에서 `pgrep -f frida-server` 로 실행 여부를 확인했는데, `pgrep -f` 가 그 명령을 실행하는 `sh -c` 의 명령줄 자체에 매칭되어 "이미 떠 있다"고 판단하고 서버를 띄우지 않았다. Frida는 서버 없이 루트 없는 기기로 판단해 Gadget이 필요하다는 오류를 냈다. `pidof frida-server` 로 바꾸고 서버를 루트로 띄운 뒤 다시 돌렸다.

![터미널. am force-stop 후 timeout 60 frida -D $S -f io.seika.scanlab -l frida/ecb_hook.js -q -t 25 백그라운드 실행, Spawned io.seika.scanlab. Resuming main thread!, hooked Cipher.getInstance(String). bash scripts/login.sh $S 후 Cipher.getInstance 로그 AES/ECB/PKCS5Padding이 CredentialStore.save, TokenCache.wrap, ExportHelper.export 세 호출자에서 각각 한 줄씩 찍힘](/assets/img/android-mastery/p1c24/11-frida-ecb.png)

로그인 한 번에 `AES/ECB/PKCS5Padding` 이 세 번 요청됐고 호출자는 `CredentialStore.save`, `TokenCache.wrap`, `ExportHelper.export` 다. high 경보 한 줄은 맞았지만 같은 결함의 나머지 둘은 리포트에 없다. 리플렉션 쪽은 결국 런타임 훅이 아니면 확정하기 어렵다.

덤으로 하나 더 겪었다. 같은 APK를 jadx 1.5.5로 처음 풀었을 때는 `ExportHelper.java` 메서드 위에 jadx 자신의 `ConcurrentModificationException` 경고 주석 블록이 붙어 코드가 열 줄 밀렸고, 인라인 키가 `:28` 에 있었다. 그 뒤로 여섯 번 더 풀었을 때는 블록이 없었고 키는 매번 `:18` 이었다. 위 시크릿 캡처와 ECB 캡처(`getInstance` 호출이 `:17`)가 이 출력이고, MobSF 리포트의 리플렉션 경보 `:16` 도 블록이 없는 출력 기준으로 `Class.forName` 줄이다. 역컴파일러가 붙인 줄 번호는 위치를 찾는 힌트로만 쓰고 보고서의 식별자로 삼지 않는 게 안전하다.

## 같은 warning, 다른 도달성: adb shell과 공격자 앱은 다르게 본다

exported 경보를 검증할 때 가장 흔한 실수는 `adb shell am start` 가 성공했으니 외부 앱도 열 수 있다고 적는 것이다. 액티비티 시작 경로는 [`ActivityTaskSupervisor.java#1065`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#1065) 에서 호출자의 uid로 `checkComponentPermission` 을 부르고, 그 판단 순서는 [`ActivityManager.java#4214`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/app/ActivityManager.java#4214) 에 있다.

![android.googlesource.com android-13.0.0_r1 ActivityManager.java 4208~4243줄, 4214줄 checkComponentPermission(String permission, int uid, int owningUid, boolean exported) 강조. 4218 ROOT_UID 또는 SYSTEM_UID면 PERMISSION_GRANTED, 4222 isolated면 DENIED, 4227 같은 앱이면 GRANTED, 4231 !exported면 DENIED, 4240 permission == null이면 GRANTED](/assets/img/android-mastery/p1c24/14-aosp-checkcomponentpermission.png)

root와 system은 첫 줄에서 모든 검사를 건너뛴다. 그다음 isolated 프로세스는 거부, 소유 앱 자신은 허용(그래서 앱 안에서는 non-exported HelpActivity를 연다), 그다음 exported가 아니면 거부, 권한이 없으면 허용, 권한이 있으면 호출자 uid가 그 권한을 가졌는지 본다. 그러니 같은 컴포넌트라도 부르는 쪽 uid에 따라 결과가 갈린다. adb shell(uid 2000)은 [`packages/Shell/AndroidManifest.xml`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/packages/Shell/AndroidManifest.xml#143) 에서 `WRITE_SECURE_SETTINGS` 를 받는다. 이 권한은 [코어 매니페스트](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/res/AndroidManifest.xml#3753)에서 보호 수준이 signature, privileged, development, role, installer 조합이라 일반 앱은 못 받는다. 반대로 shell은 scanlab이 정의한 `normal` 권한을 요청한 적이 없으니 갖고 있지 않다. 모든 검사를 건너뛰게 해 주는 [`START_ANY_ACTIVITY`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/res/AndroidManifest.xml#3084) 는 signature 권한이고 Shell 매니페스트에 없다.

이걸 실제로 비교했다. 루트가 아닌 adbd에서 shell로 여섯 액티비티를 열어 보고, 같은 여섯 개를 scanprobe 안에서 `startActivity` 로 열게 했다. scanprobe가 하는 일은 이게 전부다.

```java
try {
    startActivity(new Intent().setComponent(new ComponentName(PKG, PKG + "." + act)));
    res = "startActivity " + act + " -> OK";
} catch (SecurityException e) {
    res = "startActivity " + act + " -> SecurityException: " + e.getMessage();
}
// ...
Log.i(TAG, "uid=" + Process.myUid() + " " + res);
```

scanprobe 매니페스트는 `io.seika.scanlab.permission.DEBUG` 를 `uses-permission` 으로 요청하고, targetSdk 33이라 패키지 가시성 때문에 `<queries>` 에 scanlab을 넣었다.

![터미널. adb shell id -u 2000. shell에서 am start -W 루프 결과 VaultActivity Status: ok, AboutActivity Status: ok, SyncActivity requires io.seika.scanlab.permission.SYNC, DebugActivity requires io.seika.scanlab.permission.DEBUG, AdminActivity Status: ok, HelpActivity not exported from uid 10179. dumpsys package io.seika.scanprobe에서 userId=10180, io.seika.scanlab.permission.DEBUG: granted=true. Probe를 --activity-clear-task로 여섯 번 띄운 뒤 logcat SCANPROBE에서 uid=10180 VaultActivity OK, AboutActivity OK, SyncActivity SecurityException requires SYNC, DebugActivity OK, AdminActivity SecurityException requires android.permission.WRITE_SECURE_SETTINGS, HelpActivity SecurityException not exported from uid 10179](/assets/img/android-mastery/p1c24/07-reach-shell-vs-app.png)

캡처에 보이는 명령을 그대로 옮기면 이렇다(`S` 는 에뮬레이터 시리얼).

```bash
adb -s $S shell id -u
for a in VaultActivity AboutActivity SyncActivity DebugActivity AdminActivity HelpActivity; do
  r=$(adb -s $S shell am start -W -n io.seika.scanlab/.$a 2>&1 | grep -oE 'Status: ok|not exported from uid [0-9]+|requires [A-Za-z0-9_.]+' | head -1)
  printf 'shell(2000)  %-14s %s\n' $a "$r"
done
adb -s $S shell dumpsys package io.seika.scanprobe | grep -E "userId=|scanlab.permission.DEBUG"
adb -s $S logcat -c
for a in VaultActivity AboutActivity SyncActivity DebugActivity AdminActivity HelpActivity; do
  adb -s $S shell am start -W -n io.seika.scanprobe/.Probe --activity-clear-task --es act $a >/dev/null; sleep 1
done
adb -s $S logcat -d -s SCANPROBE:I | grep -oE 'uid=.*' | sed -E 's/Permission Denial: starting Intent \{[^}]*\} from .*\)//'
```

두 열이 양방향으로 어긋난다. DebugActivity는 shell에게 막혔지만 공격자 앱에는 열렸다. `normal` 권한은 설치할 때 요청만 하면 자동으로 받기 때문이다(`granted=true`). shell로만 검증했다면 "권한으로 보호됨, 도달 불가"라고 오판했을 것이고, 이 화면은 서명 키와 prefs를 통째로 보여 준다. AdminActivity는 반대로 shell에서 열렸지만 공격자 앱은 `requires android.permission.WRITE_SECURE_SETTINGS` 로 막혔다. shell 결과만 믿었다면 없는 취약점을 보고했을 것이다. 덧붙이면 AdminActivity는 열리는 순간 세션 prefs를 지운다. 검증용 `am start` 도 대상 앱의 상태를 바꿀 수 있다.

루트에서는 더 넓게 열린다. 같은 에뮬레이터를 `adb root` 로 바꾸고 shell에게 막혔던 두 개를 다시 열어 봤다.

![터미널. adb -s $S shell id -u 결과 0. root 상태에서 am start -W io.seika.scanlab/.HelpActivity와 .SyncActivity가 모두 Status: ok](/assets/img/android-mastery/p1c24/12-root-bypass.png)

exported가 아닌 HelpActivity도, signature 권한의 SyncActivity도 `Status: ok` 다. `checkComponentPermission` 의 첫 분기 그대로다. SyncActivity는 열리면서 동기화까지 시도했고, 그때는 호스트 서버를 띄워 두지 않아서 logcat에 `ConnectException: Failed to connect to /10.0.2.2:8088` 이 남았다. 그래서 루트로 연 결과는 도달성 판정에 쓰지 않았다.

그럼 공격자 앱이 연 VaultActivity에는 뭐가 보일까. 부팅 직후 로그인하지 않은 상태에서 scanprobe로 열었다.

![에뮬레이터 화면. scanlab 앱 바 아래 VaultActivity, logged_in=false, secret note: door code 7391, spare key under the plant, export blob: D/VQxMM3mPUNS8dkhhUQ9J9nKuEKAPWpXJj73ShI8taOsQbSqK4MgS8JO6TJ5A8b](/assets/img/android-mastery/p1c24/08-vault-opened-by-probe.png)

`logged_in=false` 인데 비밀 메모가 그대로 나온다. logcat에는 `VaultActivity shown, logged_in=false, caller uid=n/a (referrer=null)` 이 찍혔다. 정상 로그인으로 들어왔을 때는 앞의 동기화 캡처처럼 `referrer=android-app://io.seika.scanlab` 였다. API 33에는 [`Activity#getLaunchedFromUid()`](https://developer.android.com/reference/android/app/Activity#getLaunchedFromUid%28%29) 가 없어서(API 34에 추가) 리퍼러로 대신 찍었는데, 리퍼러는 호출자가 꾸밀 수 있는 값이라 방어 근거로 쓰면 안 된다. AboutActivity와 같은 warning 한 줄을 받은 이 화면이 앱에서 가장 심각한 결함이었다.

## 매니페스트에 없는 리시버는 리포트에도 없다

`App.onCreate` 는 리시버를 코드로 등록한다.

```java
BroadcastReceiver devLogin = new BroadcastReceiver() {
    @Override public void onReceive(Context c, Intent i) {
        c.getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                .putBoolean("logged_in", true).putString("user", "dev").apply();
        Log.i(TAG, "DEV_LOGIN accepted from broadcast, logged_in=true");
    }
};
IntentFilter f = new IntentFilter("io.seika.scanlab.action.DEV_LOGIN");
if (Build.VERSION.SDK_INT >= 33) registerReceiver(devLogin, f, 2 /* RECEIVER_EXPORTED */);
else registerReceiver(devLogin, f);
```

`2` 는 [`Context.RECEIVER_EXPORTED`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/content/Context.java#589) 값이다(`RECEIVER_NOT_EXPORTED` 는 [`4`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/content/Context.java#603)). API 33에서는 이 플래그가 선택이고, targetSdk 34부터 컨텍스트 등록 리시버에 둘 중 하나를 반드시 지정해야 한다([Android 14 동작 변경](https://developer.android.com/about/versions/14/behavior-changes-14)). 매니페스트 기반 분석기에게 이 리시버는 존재하지 않는다. 매니페스트를 직접 세어 봐도 receiver 태그는 없다.

```bash
aapt2 dump xmltree --file AndroidManifest.xml out/scanlab.apk | grep -c "E: receiver"
```

```text
0
```

![터미널. MobSF receivers 빈 목록, exported_receivers: 0. am force-stop 후 MainActivity 시작 Status: ok. dumpsys activity broadcasts에 app=5177:io.seika.scanlab/u0a179 uid=10179의 BroadcastFilter와 Action: "io.seika.scanlab.action.DEV_LOGIN". Probe로 --es bcast io.seika.scanlab.action.DEV_LOGIN 실행 Status: ok, 이어서 --es act VaultActivity Status: ok. logcat에 runtime receiver registered, SCANPROBE uid=10180 sendBroadcast DEV_LOGIN -> sent, DEV_LOGIN accepted from broadcast logged_in=true, startActivity VaultActivity -> OK, VaultActivity shown logged_in=true referrer=null](/assets/img/android-mastery/p1c24/09-runtime-receiver.png)

MobSF 리포트도 `receivers: []`, 내보낸 리시버 0이다. 그런데 앱을 한 번 띄우면 `dumpsys activity broadcasts` 에 uid 10179가 등록한 `DEV_LOGIN` 필터가 보이고, scanlab 프로세스가 살아 있는 동안에는 권한 없는 scanprobe가 보낸 브로드캐스트 하나로 `logged_in=true` 가 된다. 캡처에서 MainActivity를 먼저 띄운 것도 그래서다. 이어서 연 VaultActivity도 `logged_in=true` 를 표시했다. 로그인 상태 위조인데 정적 리포트에는 흔적이 없다. 런타임 리시버는 `dumpsys activity broadcasts` 를 앱 실행 후에 떠 보거나 역컴파일 결과에서 `registerReceiver(` 를 검색해야 찾는다. 리시버 자체는 [16장](/posts/android-lab-p1c16-broadcastreceiver-ordered-broadcast/)에서 다뤘다.

## 리플렉션으로 붙인 JS 브리지

WebView 경고 규칙 [`android_webview`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/android/rules/android_rules.yaml#L148) 는 `RegexAnd` 다. 한 파일에 `setJavaScriptEnabled(true)` 와 `addJavascriptInterface(` 가 둘 다 리터럴로 있어야 경보가 뜬다.

![터미널. android_rules.yaml v4.5.3의 android_webview 규칙 type RegexAnd, pattern setJavaScriptEnabled\(true\)와 addJavascriptInterface\(. HelpActivity.java:23 setJavaScriptEnabled(true), :25 WebView.class.getMethod("addJavascriptInterface", Object.class, String.class).invoke(webView, new Bridge(), "seika"). 리포트 code_analysis 키는 android_aes_ecb, android_hardcoded, android_ip_disclosure, android_logging, android_md5뿐이고 android_api api_webview에 HelpActivity.java](/assets/img/android-mastery/p1c24/06-webview-rule-miss.png)

소스에서는 `"add" + "Javascript" + "Interface"` 로 메서드 이름을 쪼갰다. 캡처에서 jadx 출력에는 `getMethod("addJavascriptInterface", ...)` 로 합쳐져 보이지만, 이 문자열 뒤에는 `(` 대신 `"` 가 와서 패턴이 맞지 않는다. 그래서 code_analysis에 `android_webview` 가 없다. 대신 info 등급 API 목록은 HelpActivity를 두 번 잡았다. 메시지가 "WebView JavaScript Interface"인 [`api_webview`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/android/rules/android_apis.yaml#L204) 는 패턴이 `(` 없는 `addJavascriptInterface` 라 리플렉션 문자열에도 맞았고, [`api_javascript_interface_methods`](https://github.com/MobSF/Mobile-Security-Framework-MobSF/blob/v4.5.3/mobsf/StaticAnalyzer/views/android/rules/android_apis.yaml#L462) 는 `@JavascriptInterface` 어노테이션을 잡았다. JS 인터페이스가 있다는 표시 자체는 info 등급으로 남아 있다.

브리지는 실제로 살아 있다. 루트 shell로 HelpActivity를 열자 페이지 스크립트가 `seika.token()` 을 불러 서명 키를 화면에 썼다.

![에뮬레이터 화면. scanlab 앱 바 아래 WebView에 help 제목과 bridge seika.token() = Uvp3QKi1BI/UN27PvXGWKS6oXd2AHW까지 보이고 나머지는 화면 오른쪽 끝에서 잘림](/assets/img/android-mastery/p1c24/13-help-bridge.png)

화면 폭 때문에 값 끝이 잘렸지만 앞부분은 MobSF의 두 번째 시크릿과 같다. 다만 HelpActivity는 exported가 아니고, 페이지는 앱이 `loadDataWithBaseURL` 로 직접 넣는 문자열이다. 제3자 앱은 이 화면을 열 수 없고(앞의 `not exported from uid 10179`) 외부 콘텐츠도 로드하지 않으니 지금 구조에서 영향은 낮다. 이 액티비티가 외부 URL을 받기 시작하는 순간 키 유출 경로가 되는 코드라서 경보가 빠진 것 자체는 기록해 둘 만하다. WebView 브리지의 공격면은 [20장](/posts/android-lab-p1c20-deeplink-applink-webview/)에 있다.

## 판정표

위의 확인을 경보 단위로 모으면 이렇다.

| MobSF 경보 | MobSF 심각도 | 판정 | 근거 |
|--|--|--|--|
| 시크릿 6589af84…, Legacy.java 하드코딩, MD5, legacy URL | warning | 오탐(참조 없는 클래스), 제거 권고 | grep xref |
| 시크릿 Uvp3QKi1…, ApiClient.java 하드코딩 | warning | 참, 살아 있는 HMAC 키 | 서명 재계산 일치 |
| cleartext 허용 | high | 참, 동기화가 http | 호스트 서버 수신 |
| ECB, CredentialStore.java | high | 참 | Frida |
| VaultActivity not Protected | warning | 참, 인증 우회(가장 심각) | probe가 열고 메모 노출 |
| AboutActivity not Protected | warning | 참이지만 영향 없음(정적 문구) | probe OK |
| SyncActivity signature | info | 참(info 그대로), 제3자 도달 불가 | probe 거부 |
| DebugActivity normal | warning | 참, 아무 앱이나 키와 prefs 열람 | probe OK, shell은 거부 |
| AdminActivity 권한 미정의 | warning | 오탐, 제3자 도달 불가(shell만 가능) | probe 거부 |
| (없음) TokenCache, ExportHelper ECB | 없음 | 미탐 | smali, Frida |
| (없음) SecretKeySpec 인라인 키 | 없음 | 미탐 | grep |
| (없음) 런타임 DEV_LOGIN 리시버 | 없음 | 미탐, 앱 실행 중 로그인 상태 위조 | dumpsys, probe |
| (경고 없음) 리플렉션 JS 브리지 | info API 목록만 | 경고 누락(info로만 표시), 현재 영향 낮음 | 규칙 대조, 화면 |

점수 44는 이 표의 판정과 상관없이 계산된다. [OWASP MASTG](https://mas.owasp.org/MASTG/0x04b-Mobile-App-Security-Testing/)의 정적 분석 절도 자동 도구가 오탐을 많이 내니 결과를 사람이 다시 보라고 하고, 동적 분석을 별도 절차로 둔다. 오탐으로 억제하는 줄에는 억제 사유(참조 없음, 제3자 도달 불가 등)와 근거 캡처를 함께 남겨 다음 스캔에서도 같은 판단을 할 수 있게 한다. 숫자는 모두 MobSF v4.5.3 `d3869ad` 기준이라 규칙 파일이 바뀐 버전에서는 다시 확인해야 하니 리포트에 버전을 적어 둔다. 위협 모델로 영향을 매기는 방법은 Atlas [C55](/posts/android-concept-atlas-c55-threat-model-impact-assessment/)를 따랐다.

## 고칠 곳과 고쳤는지 확인하는 방법

여기서는 수정판을 빌드해 돌려 보지 않았다. 방향과 확인 방법만 적는다.

VaultActivity는 `exported="false"` 로 닫는 게 먼저이고, 외부에서 열려야 하는 화면이라면 `onCreate` 에서 로그인 상태를 확인해 아니면 `finish()` 한다. 확인은 위의 scanprobe 루프를 다시 돌려 `VaultActivity -> SecurityException: not exported` 가 나오는지 보면 된다. DebugActivity는 릴리스 빌드에서 빼거나 권한을 `signature` 로 올린다. 이때 검증은 반드시 shell이 아니라 다른 키로 서명한 앱으로 한다. shell은 이 권한을 처음부터 갖고 있지 않아 고치기 전에도 막혀 있었다.

런타임 리시버는 `RECEIVER_NOT_EXPORTED` 로 등록하거나, 개발용 경로라면 릴리스에서 등록 자체를 없앤다. 확인은 scanprobe의 `bcast` 를 다시 보내 logcat에 `DEV_LOGIN accepted` 가 안 찍히는지, `dumpsys activity broadcasts` 에서 필터가 사라졌는지 본다.

APK에 박힌 HMAC 키는 꺼내 쓸 수 있다는 걸 전제로 설계를 바꿔야 한다. 서버가 요청 서명을 검증해야 한다면 기기마다 Android Keystore에서 만든 키와 서버 측 등록을 쓰는 쪽이 맞다([14장](/posts/android-lab-p1c14-keystore-biometricprompt/)). 동기화 URL은 https로 바꾸고 `usesCleartextTraffic` 를 지우거나 [Network Security Config](/posts/android-lab-p1c12-network-security-config/)로 cleartext를 막는다. 확인은 `sync_server.py` 를 띄운 채 로그인해서 평문 요청이 더 이상 들어오지 않는지 보는 것이다.

ECB 세 곳은 `AES/GCM/NoPadding` 과 호출마다 새 IV로 바꾸고, 인라인 키는 Keystore 키로 대체한다. 확인은 MobSF 재스캔으로는 부족하다. 처음부터 두 곳은 MobSF가 못 봤으니, 위의 Frida 훅을 다시 걸고 로그인했을 때 `AES/ECB` 줄이 하나도 안 나오는지 본다. 리플렉션 브리지는 브리지가 정말 필요한지부터 따지고, 남긴다면 신뢰하는 출처의 페이지에만 붙인다.
