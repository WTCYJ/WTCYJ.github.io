---
layout: post
title: "OWASP MASTG Hacking Playground - 취약한 안드로이드 앱 정공법 실습"
date: 2026-09-01 20:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, OWASP, MASTG, MASVS, Frida, adb, jadx, 정적분석, 동적분석, 취약점실습, 학습기록]
excerpt: "안드로이드 실습 자료를 찾다가 깃허브에서 OWASP MASTG Hacking Playground를 발견해, 안드로이드 취약 앱을 Windows 에뮬레이터에 올려 처음부터 끝까지 실제로 뜯어봤습니다. 평문 저장·자작 암호·로그 유출·SQL 인젝션·WebView 브릿지·거꾸로 된 SSL 핀·/sdcard에서 코드 로딩까지, 각 테스트 케이스를 기기에서 직접 발화시키고 run-as·logcat·sqlite·Frida로 값을 뽑아 확인한 기록입니다. 되는 것만이 아니라, 배포 APK가 소스보다 오래돼 아예 안 열리던 것, 요즘 안드로이드가 API를 없애 크래시나던 것까지 그대로 적었습니다."
---

> 대상: [OWASP/MASTG-Hacking-Playground](https://github.com/OWASP/MASTG-Hacking-Playground) — OWASP MAS 프로젝트의 교육용 의도적 취약 앱 (MASTG Android Java App, "Attack me if u can")
> 환경: Windows 11 + Android x86 에뮬레이터(API 26), 배포된 `app-x86-debug.apk`, adb / jadx / Frida 17

안드로이드 보안을 더 실습해 보고 싶어서 괜찮은 연습용 자료를 찾아다니다가, 깃허브에서 OWASP
MAS 프로젝트의 MASTG Hacking Playground를 발견했습니다. 마침 안드로이드 앱이라 Windows
에뮬레이터에 그냥 올라가니, 이걸로 제대로 해보기로 했습니다.

앱 이름은 "Attack me if u can"이고, OWASP Mobile Application Security Testing Guide(MASTG)의
테스트 케이스를 하나씩 액티비티로 심어 놨습니다. 저장소·암호·로그·주입·WebView·네트워크까지
카테고리별로 스물네 개가 있는데, 메뉴에서 항목을 누르면 그 취약점이 발화합니다.

![MASTG Hacking Playground 메인 화면 — "Attack me if u can" 제목 아래로 OMTG-DATAST-001-BADENRYPTION 부터 카테고리별 테스트 케이스 버튼이 나열돼 있다](/assets/img/mastg-playground/mastg-home.png)

이번엔 정적 분석에서 멈추지 않고, 각 케이스를 에뮬레이터에서 실제로 눌러 발화시키고
`adb`·`run-as`·`logcat`·`sqlite3`·`Frida`로 값을 뽑아 확인했습니다. 잘 된 것만 적진
않았습니다. 배포된 APK가 소스보다 오래돼서 특정 화면이 아예 안 열리던 것, 요즘 안드로이드가
옛 API를 없애서 앱이 크래시나던 것도 그대로 남겼습니다. 사실 그 "안 되던 것"들이 이 앱에서
제일 많이 배운 지점이었습니다.

정리는 안드로이드판을 풀 때처럼 성격별로 묶었습니다.

---

## 0. 먼저 정한 환경

앱은 `app-arm-debug.apk`와 `app-x86-debug.apk` 두 종을 제공합니다. 제 에뮬레이터가
x86이라 x86 빌드를 골랐는데, 여기서 첫 벽을 만났습니다. 최신 API 33 에뮬레이터에 설치하니
이렇게 거부됩니다.

```console
$ adb install app-x86-debug.apk
Failure [INSTALL_FAILED_NO_MATCHING_ABIS: Failed to extract native libraries, res=-113]
```

앱이 SQLCipher 네이티브 라이브러리를 32비트로만 담고 있는데, 요즘 에뮬레이터는 x86_64
전용이라 32비트 x86 `.so`가 안 맞습니다. 게다가 앱의 `targetSdk`가 26이라, 굳이 최신
API에서 돌릴 이유도 없었습니다. 그래서 앱의 시대에 맞춰 API 26(Android 8.0) x86 에뮬레이터를
띄웠습니다. 여기는 ABI 목록에 32비트 x86이 있어 설치가 통과합니다.

```console
$ adb shell getprop ro.product.cpu.abilist
x86_64,x86
$ adb install -g -r app-x86-debug.apk
Success
```

시작하기 전에 하나 확인해 둔 게 있는데, 이게 뒤에서 계속 중요해집니다. 소스와 배포된 APK가
같지 않습니다. 저장소의 소스는 계속 고쳐지는데 릴리스로 올라온 APK는 예전에 빌드된 것이라,
소스에는 고쳐진 취약점이 배포본에는 옛날 그대로 남아 있는 경우가 있습니다. 그래서 이 글에서
"실제로 이렇게 동작한다"는 부분은 전부 **배포된 APK를 jadx로 디컴파일한 코드**와 **기기에서
관측한 것**을 기준으로 적었습니다. 소스는 참고만 하고요.

테스트 케이스 액티비티들은 전부 `exported=false`라 셸에서 직접 못 켭니다.

```console
$ adb shell am start -n .../OMTG_DATAST_001_SharedPreferences
SecurityException: Permission Denial: ... not exported from uid 10085
```

그래서 실제 사용자처럼 메뉴 버튼을 눌러 발화시켰습니다. 이게 오히려 실전에 가깝습니다.
그리고 이 앱은 디버그 빌드(`debuggable=true`)라, 루팅 없이도 `run-as`로 앱의 프라이빗
저장소에 들어갈 수 있습니다. 이건 뒤에 나올 저장소 계열 문제 대부분의 열쇠가 됩니다.

---

## 1. 로컬 저장소

가장 큰 덩어리입니다. 요지는 하나입니다. 앱이 값을 어디에 두든(내부 저장소, 외부 저장소,
SharedPreferences, SQLite) 결국 파일로 남고, 그 파일은 `run-as`·백업·루트로 읽힙니다.
암호화가 없으면 그대로 노출됩니다.

### 1-1. Internal Storage

`OMTG_DATAST_001_InternalStorage`는 화면을 열기만 해도 신용카드 번호를 앱 내부 파일에
평문으로 씁니다. `MODE_PRIVATE`라 파일 권한은 `0600`이지만, 내용 자체가 평문이라
`run-as`로 그대로 읽힙니다.

```console
$ adb shell run-as sg.vp.owasp_mobile.omtg_android ls -l files/test_file
-rw-rw---- 1 u0_a85 u0_a85 41 files/test_file
$ adb shell run-as sg.vp.owasp_mobile.omtg_android cat files/test_file
Credit Card Number is 1234 4321 5678 8765
```

### 1-2. External Storage

`OMTG_DATAST_001_ExternalStorage`는 한 술 더 떠서 평문 비밀번호를 공유 외부 저장소
`/sdcard`에 씁니다(설치 시 `-g`로 저장소 권한을 준 상태). 외부 저장소는 앱 샌드박스가
아니라, `READ_EXTERNAL_STORAGE`만 있으면 어떤 앱이든 읽습니다.

```console
$ adb shell cat /sdcard/password.txt
L33tS3cr3t
```

내부 저장소는 그래도 `run-as`/루트가 필요했는데, 외부 저장소는 그 벽조차 없습니다.

### 1-3. SQLite

`OMTG_DATAST_001_SQLite`는 자격증명을 표준(비암호) SQLite에 그대로 적재합니다. DB 파일을
뽑아 첫 16바이트만 봐도 암호화가 안 됐다는 게 그대로 드러납니다.

```console
$ adb exec-out run-as sg.vp.owasp_mobile.omtg_android cat databases/privateNotSoSecure > priv.db
$ xxd priv.db | head -1
00000000: 5351 4c69 7465 2066 6f72 6d61 7420 3300   SQLite format 3.
$ sqlite3 priv.db "SELECT * FROM Accounts;"
admin|AdminPass
```

`SQLite format 3`이라는 매직이 평문으로 보이면 그 DB는 암호화가 안 된 겁니다.

### 1-4. SharedPreferences

여기서 이 앱에서 제일 재밌었던 순간이 나옵니다. `OMTG_DATAST_001_SharedPreferences`를
누르면 앱이 그냥 죽습니다. logcat을 보니 이유가 이렇습니다.

```console
$ adb logcat
E AndroidRuntime: java.lang.RuntimeException: Unable to start activity
    ...OMTG_DATAST_001_SharedPreferences: java.lang.SecurityException:
    MODE_WORLD_READABLE no longer supported
  Caused by: java.lang.SecurityException: MODE_WORLD_READABLE no longer supported
    at ...OMTG_DATAST_001_SharedPreferences.onCreate(OMTG_DATAST_001_SharedPreferences.java:19)
```

배포 APK를 디컴파일해 보면 원인이 분명합니다.

```java
// jadx 디컴파일 — 배포된 코드
SharedPreferences sharedPref = getSharedPreferences("key", 1);   // 1 = MODE_WORLD_READABLE
editor.putString("username", "administrator");
editor.putString("password", "supersecret");
```

원래 이 케이스의 취약점이 바로 이 `MODE_WORLD_READABLE`입니다. 관리자 계정/비밀번호를
"세상 모두가 읽을 수 있는" prefs 파일에 저장하는 것. 그런데 안드로이드가 이 위험한 모드를
API 24(Android 7.0)에서 아예 제거해 버려서, 그걸 쓰는 앱은 실행하는 순간
`SecurityException`으로 죽습니다. 그러니까 이 배포 APK는 그 위험한 코드를 그대로 담은 옛
빌드이고, 요즘 안드로이드에서는 취약점이 터지기도 전에 플랫폼이 앱을 멈춰 세웁니다.

그럼 이 취약점이 원래 노렸던 Android 6에서는 어떻게 되는지 실제로 보고 싶어서, API 23
에뮬레이터를 따로 띄우고 같은 앱을 설치했습니다. 여기서는 `MODE_WORLD_READABLE`이 아직
살아 있어서 화면이 크래시 없이 열리고, `key.xml`이 월드 리더블로 만들어집니다.

```console
# API 23 (Android 6.0) — 크래시 없이 SharedPreferences 화면이 열림
$ adb -s emulator-5558 shell run-as sg.vp.owasp_mobile.omtg_android \
      ls -l /data/data/sg.vp.owasp_mobile.omtg_android/shared_prefs/key.xml
-rw-rw-r-- u0_a61 u0_a61 170 key.xml            # 끝의 r 이 '다른 앱도 읽기' 비트

# run-as 없이, 셸(uid 2000 = 앱과 다른 신원)로 그냥 읽힌다
$ adb -s emulator-5558 shell cat \
      /data/data/sg.vp.owasp_mobile.omtg_android/shared_prefs/key.xml
<map>
    <string name="username">administrator</string>
    <string name="password">supersecret</string>
</map>
```

`-rw-rw-r--`의 마지막 `r`이 핵심입니다. 파일이 월드 리더블이라, 앱과 다른 신원(`run-as`
없이 셸 uid)으로도 `administrator`/`supersecret`이 그대로 읽힙니다. 실기기였다면 아무 앱이나
이 파일을 읽어 자격증명을 가져갔을 겁니다. 정확히 이게 이 케이스가 노린 취약점이고요.

그래서 한 취약점을 두 안드로이드에서 나란히 본 셈이 됐습니다. Android 6에서는 world-readable
익스가 그대로 통하고(위), 같은 APK가 API 26에서는 그 위험한 API가 제거돼 실행조차 못 하고
크래시납니다(앞의 logcat). 취약점 코드가 있다는 것과 지금 이 기기에서 진짜 터지는 것은
다르다는 얘기를, 이 앱이 두 버전에 걸쳐 직접 보여준 셈입니다.

### 1-5. Encrypted SQLite

`OMTG_DATAST_001_SQLite-Encrypted`는 SQLCipher로 DB를 암호화합니다. 다만 복호화 키가 앱에
하드코딩돼 있어서 암호화가 무력화됩니다. 참고로 이 화면 자체는 제 x86 에뮬에서 안 열립니다 —
앱이 SQLCipher 네이티브 라이브러리를 armeabi(32비트 ARM)로만 담고 x86 빌드를 빼먹어서
(`lib/x86/`엔 `libnative.so` 하나뿐입니다), `loadLibs()`가 `UnsatisfiedLinkError`로 죽거든요.
그런데 정작 열쇠는 아키텍처와 무관하게 그대로 나옵니다.

```console
$ unzip -p app-x86-debug.apk 'lib/x86/libnative.so' | strings | grep -i s3cr3t
S3cr3tString!!!
```

이 문자열이 어디로 들어가는지는 디컴파일로 확정됩니다. 두 번째 인자가 SQLCipher의
패스프레이즈인데, 그게 방금 라이브러리에서 뽑은 그 값(`stringFromJNI()`)입니다.

```java
// jadx 디컴파일 — OMTG_DATAST_001_SQLite_Encrypted
public native String stringFromJNI();          // libnative.so 의 "S3cr3tString!!!" 반환
...
SQLiteDatabase.loadLibs(this);
SQLiteDatabase secureDB = SQLiteDatabase.openOrCreateDatabase(
        database, stringFromJNI(), null);       // 2번째 인자 = 복호 키
secureDB.execSQL("INSERT INTO Accounts VALUES('admin','AdminPassEnc');");
```

그럼 그 열쇠가 정말 이 암호화를 여는지 직접 확인해 봤습니다. 앱 화면은 x86에서 못 돌지만,
앱이 하는 동작(키·스키마·INSERT)은 위 디컴파일에 전부 있으니, 뽑은 키로 진짜 SQLCipher에
앱과 똑같이 재현했습니다(앱의 SQLCipher 3.1.0 포맷을 맞추려 `cipher_compatibility=3`).

```console
# 앱에서 뽑은 하드코딩 키로, 앱과 같은 스키마·데이터의 암호화 DB 생성
$ sqlcipher encrypted
sqlite> PRAGMA key = 'S3cr3tString!!!';  PRAGMA cipher_compatibility = 3;
sqlite> CREATE TABLE Accounts(Username,Password);
sqlite> INSERT INTO Accounts VALUES('admin','AdminPassEnc');

# 1) 파일 앞 16바이트 — 'SQLite format 3' 매직이 없다 = 진짜로 암호화됨
$ xxd encrypted | head -1
00000000: 5a89 bfde 55c8 2ece 71e1 7fbb 0bb6 e4e7  Z...U...q.......

# 2) 키 없이 열기 → 못 연다
$ sqlcipher encrypted "SELECT * FROM Accounts;"
Error: file is not a database (26)

# 3) 앱에서 뽑은 바로 그 키로 열기 → 평문이 그대로
$ sqlcipher encrypted     # PRAGMA key='S3cr3tString!!!'; cipher_compatibility=3;
admin|AdminPassEnc
```

암호화 자체는 멀쩡합니다 — 파일은 랜덤 바이트고, 키 없이는 `file is not a database`로 안
열립니다. 문제는 그 열쇠가 앱 안에 상수로 같이 들어 있다는 것뿐입니다. 그래서 리버서는
`strings` 한 번으로 키를 뽑아 암호화를 통째로 무력화합니다. 자물쇠는 튼튼한데 열쇠를 그
자물쇠에 테이프로 붙여 배포한 셈이죠.

---

## 2. 잘못 쓴 암호

### 2-1. Bad Encryption

`OMTG-DATAST-001-BADENRYPTION`은 표준 암호 대신 직접 만든 변환을 씁니다. 디컴파일해 보면
바이트마다 `XOR 0x10` 후 비트 반전(`~x & 0xff`)이 전부고, 검증 대상 암호문
`vJqfip28ioydips=`가 코드에 상수로 박혀 있습니다. 가역 변환에 하드코딩이라, 역산 한 줄이면
평문이 나옵니다.

```console
$ python -c "import base64; d=base64.b64decode('vJqfip28ioydips='); \
             print(bytes(((~s&0xff)^0x10) for s in d).decode())"
SuperSecret
```

이렇게 복원한 `SuperSecret`를 앱에 넣으니 정답으로 인정합니다.

![BadEncryption 화면 — 입력칸에 SuperSecret 를 넣고 VERIFY PASSWORD 를 누르자 "Congratulations, this is the correct password" 토스트가 뜬 화면](/assets/img/mastg-playground/badenc-toast.png)

### 2-2. KeyStore

`OMTG-DATAST-001-KEYSTORE`는 AndroidKeyStore로 RSA 키쌍을 만듭니다. 이건 사실 잘한
부분입니다 — 개인키가 추출 불가라서요. 문제는 그 옆에서 민감정보를 통째로 logcat에 흘린다는
겁니다. Encrypt를 누르니 하드코딩된 테스트 값과 공개키, 암호문이 로그로 쏟아집니다.

```console
$ adb logcat -s OMTG_DATAST_001_KeyStore:V
V OMTG_DATAST_001_KeyStore: test log: 12345678
E OMTG_DATAST_001_KeyStore: android.security.keystore.AndroidKeyStoreRSAPublicKey@7f4f66b6
E OMTG_DATAST_001_KeyStore: MyzKB2anCgMmPVWWnAvQDNpTVZXT9hiD9fOBVQsS8ZGA6OkNRQxy8ka/GAWx9ql...
```

키 자체는 안전한 곳(Keystore)에 있는데, 정작 다뤄야 할 값들을 로그로 내보내면 그 방어가
소용없습니다. 안드로이드에서 `adb logcat`은 셸 권한으로 전체 로그를 읽으니, 앱 로그 제한도
우회됩니다.

### 2-3. Memory

`OMTG_DATAST_011_Memory`는 AES로 복호한 문자열을 메모리에 그대로 두는데, 키와 암호문이
전부 소스에 하드코딩돼 있습니다. 키스토어 대신 코드에 키를 둔 거라, 정적으로 그대로
복호됩니다. `AesCbcWithIntegrity` 포맷(`iv:mac:cipher`, AES-128-CBC)대로 풀어 봤습니다.

```console
$ python decode_memory.py       # 하드코딩 키/IV/암호문으로 AES-128-CBC 복호
복호 평문 => U got the decrypted message. Well done.
```

### 2-4. KeyChain

`OMTG-DATAST-001-KEYCHAIN`은 개인키가 든 PKCS#12 파일을 앱 assets에 통째로 담아 배포합니다.
APK는 그냥 zip이라, 풀기만 하면 키 컨테이너가 나옵니다.

```console
$ unzip -o app-x86-debug.apk assets/server.p12
$ ls -l server.p12
-rw-r--r-- 1 yejun 1533 server.p12     # PKCS#12 개인키+인증서 컨테이너
```

개인키를 앱 패키지에 넣어 배포하면, 그 앱을 받은 누구나 키 자료를 손에 쥐게 됩니다. p12
비밀번호는 앱이 아니라 사용자가 설치 시 입력하는 구조라 소스엔 없었지만, "개인키가 APK 안에
그대로 있다"는 것 자체가 문제입니다.

---

## 3. 로그로 새는 비밀

`OMTG_DATAST_002_LOGGING`은 로그인 처리에서 아이디와 비밀번호를 문자열로 조립해 로그에
찍습니다. 화면의 비밀번호 칸은 마스킹되지만, 로그에는 평문 그대로입니다.

```console
$ adb logcat -c ; # 로그 비우고 admin / P@ssw0rd123 입력 후 Login
$ adb logcat -s OMTG_DATAST_002_Logging:E System.out:I
E OMTG_DATAST_002_Logging: User successfully logged in. User: admin Password: P@ssw0rd123
I System.out: WTF, Logging Class should be used instead.
```

디버그용으로 남긴 로그 한 줄이, 통합 로그를 읽을 수 있는 누구에게나 자격증명을 흘립니다.

---

## 4. 주입

### 4-1. SQL Injection

`OMTG_CODING_003_SQL_INJECTION`은 사용자 입력을 쿼리 문자열에 그대로 이어 붙입니다. 그래서
아이디 칸에 `admin'--`만 넣으면 뒤의 비밀번호 검사가 통째로 주석 처리되어 로그인됩니다.

![SQL Injection 화면 — 아이디 칸에 admin'-- 를 넣고 비밀번호는 anything 을 넣은 뒤 LOGIN 을 누르자 "User logged in" 토스트가 뜬 화면](/assets/img/mastg-playground/sqli-bypass.png)

값은 애초에 앱 DB에 평문으로 들어 있어서, 우회할 것도 없이 그냥 뽑을 수도 있습니다.

```console
$ adb exec-out run-as sg.vp.owasp_mobile.omtg_android cat databases/authentication > auth.db
$ sqlite3 auth.db "SELECT * FROM Accounts;"
admin|AdminPass
```

### 4-2. Best Practice

`OMTG_CODING_003_BEST_PRACTICE`는 같은 로그인 화면인데, 이번엔 파라미터 바인딩
(`... WHERE Username=? and Password=?`)을 씁니다. 그래서 방금 통했던 `admin'--`이 여기선
문자열 그대로 취급되어 로그인이 거부됩니다.

![Best Practice 화면 — 같은 admin'-- 페이로드를 넣었지만 이번엔 "Username and/or password wrong" 토스트가 뜬 화면](/assets/img/mastg-playground/bestpractice-negctrl.png)

앞의 SQL Injection과 코드가 거의 같은데 결과가 정반대인 게 이 앱의 좋은 점입니다. 무엇이
공격 표면을 만들고, 무엇이 그걸 닫는지가 한 화면 차이로 드러납니다. 다만 이 "모범사례"
화면조차 자격증명은 여전히 평문 DB(`admin`/`AdminPass`)에 저장합니다 — 주입은 막았어도 저장은
못 막은 거죠.

### 4-3. Content Provider

`OMTG-CODING-003-SQL_INJECTION_CONTENT_PROVIDER`는 사용자 입력을 ContentProvider의 selection
절에 직접 이어 붙입니다. 학생을 몇 명 추가한 뒤 검색 칸에 `' OR '1'='1`을 넣으니, 검색어와
무관하게 모든 행이 쏟아집니다.

![Content Provider 화면 — 검색 칸에 ' OR '1'='1 을 넣고 RETRIVE STUDENT 를 누르자 추가했던 학생 행들이 토스트로 덤프되는 화면](/assets/img/mastg-playground/cp-inject.png)

거기에 입력값 원문을 로그로도 흘립니다.

```console
$ adb logcat -s searchPattern:E
E searchPattern: ' OR '1'='1
```

### 4-4. Code Injection

`OMTG_CODING_004_CODE_INJECTION`은 외부 저장소의 jar를 무결성 검증 없이 `DexClassLoader`로
불러 리플렉션으로 실행합니다. 공유 저장소는 아무나 쓸 수 있으니, 곧 임의 코드 실행입니다.
`returnString()`이 마커를 반환하는 페이로드 클래스를 만들어 심었습니다.

```console
$ python -c "..."   # javac -> d8 -> jar 로 com.example.CodeInjection 패키징
$ adb push libcodeinjection.jar /sdcard/libcodeinjection.jar
$ adb shell pm grant sg.vp.owasp_mobile.omtg_android android.permission.WRITE_EXTERNAL_STORAGE
# Code Injection 화면 진입 후:
$ adb logcat -s Test:E
E Test: PWNED: attacker code from /sdcard executed inside the host app process
```

그 코드가 앱의 신원(uid 10085)으로 돕니다. 신뢰할 수 없는 위치에서 코드를 읽어 실행하는
순간, 그 위치에 쓸 수 있는 누구든 앱이 됩니다.

---

## 5. WebView

### 5-1. WebView Local

`OMTG_ENV_005_WEBVIEW_LOCAL`은 로컬 HTML을 로드하면서 JS 브릿지(`@JavascriptInterface`)를
붙입니다. 그 브릿지가 `getSomeString()`으로 "string"을, 다른 브릿지가 하드코딩된
`Secret String`을 내주는데, 두 값 다 DEX에 평문으로 있습니다.

```console
$ unzip -p app-x86-debug.apk classes.dex | grep -a "Secret String"
Secret String
```

흥미로운 건 이 케이스의 로컬 HTML(`local.htm`)이 `getClass().forName('java.lang.Runtime')`
리플렉션으로 `/sdcard/mstg.txt`를 만드는 RCE를 시도한다는 점입니다. 옛 안드로이드였다면
통했겠지만, API 17부터 `@JavascriptInterface`가 붙은 메서드만 JS에서 호출되고 `getClass()`는
막히기 때문에, 요즘 기기에서는 그 RCE가 발화하지 않습니다. 실제로 화면을 열고 확인했습니다.

```console
$ adb shell ls -l /sdcard/mstg.txt
ls: /sdcard/mstg.txt: No such file or directory      # RCE 미발화 = 플랫폼이 차단
```

파일이 없다는 게, 그 고전 WebView RCE가 이 API 26에서 막혔다는 증거입니다. 브릿지가 하드코딩
비밀을 흘리는 건 여전하고요.

### 5-2. WebView Remote

`OMTG_ENV_005_WEBVIEW_REMOTE`는 비밀을 내주는 그 브릿지를 **원격** 콘텐츠에 붙입니다. 로드
대상이 `rawgit.com`인데, 이 서비스는 2019년에 종료됐습니다. 화면을 여니 이렇게 뜹니다.

![WebView Remote 화면 — 앱이 로드한 rawgit.com 페이지에 "RawGit is no longer operational. It was fun while it lasted!" 라는 종료 안내만 표시된 화면](/assets/img/mastg-playground/webview-remote.png)

앱이 자기 UI/로직을 자기가 통제하지 않는 남의 도메인에서 가져오고, 거기에 비밀 브릿지까지
바인딩합니다. 그 도메인을 공격자가 다시 가져가거나(만료된 도메인) 중간에서 가로채면, 그
페이지의 JS가 `Android.returnString()`으로 `Secret String`을 그대로 훔쳐 갑니다. 지금은 종료
안내 페이지만 떠서 조용하지만, 신뢰 경계가 네트워크에 걸려 있다는 사실 자체가 문제입니다.

---

## 6. 네트워크

### 6-1. SSL Pinning

`OMTG_NETW_004_SSL_PINNING`이 이 앱에서 제일 어이없으면서 배울 게 많았습니다. 이름은 SSL
피닝인데, 디컴파일해 보면 커스텀 TrustManager가 표준 검증을 통과한 뒤 인증서 발급자(issuer)
이름에 `,O=PortSwigger,`가 들어 있는지만 봅니다. PortSwigger는 Burp Suite를 만드는 회사죠.
즉 이 "핀"은 **Burp의 기본 CA로 서명된 인증서면 무조건 통과**시킵니다 — 공격자의 프록시만
믿는 핀입니다.

그래서 이 앱이 진짜 `www.example.com`에 접속할 때 무슨 일이 벌어지는지 Frida로 봤습니다.

```console
$ frida -U -p <pid> -l hook_sslpin.js
[SSLPIN] hook installed
[SSLPIN] checkServerTrusted() called for real cert
[SSLPIN] PIN REJECTED real cert -> Error: java.security.cert.CertificateException
```

정상적인 example.com 인증서(발급자가 PortSwigger가 아님)를 앱이 **거부**합니다. 이 앱은
자기 서버의 진짜 인증서는 못 믿고, 오직 Burp의 CA로 MITM할 때만 연결이 됩니다. 방어라고 넣은
코드가 정확히 반대로 동작하는, 교과서적인 안티패턴입니다.

### 6-2. 3rd Party

`OMTG_DATAST_004_3RD_PARTY`는 서드파티 크래시 리포팅 SDK(ACRA)를 씁니다. 앱을 크래시시키면
스택 트레이스와 기기 정보가 조용히(SILENT 모드) 외부 서버로 전송되는데, 그 전송에 쓰는 HTTP
기본 인증 자격증명이 소스에 하드코딩돼 있습니다.

```java
// jadx 디컴파일 — MyApplication
@ReportsCrashes(
  formUri = "https://sushi2k.cloudant.com/acra/_design/acra-storage/_update/report",
  formUriBasicAuthLogin = "MmHZOqxAdT0mWSmXddYBdLPDo",
  formUriBasicAuthPassword = "MmHZOqxAdT0mWSmXddYBdLPDo",
  mode = ReportingInteractionMode.SILENT, ... )
```

크래시 리포트에 무엇이 담기는지, 어디로 가는지, 그 채널의 자격증명이 무엇인지가 전부 앱
안에 있습니다. 리포트를 받는 엔드포인트 자격증명이 노출된다는 것 자체도 문제고요. 실제 전송
본문을 가로채려면 프록시에 시스템 CA를 심는 MITM 랩이 필요해서, 여기서는 하드코딩 자격증명과
전송 대상까지 정적으로 확인하는 데서 멈췄습니다.

### 6-3. Secure Channel

`OMTG_NETW_001_SECURE_CHANNEL`은 두 개의 WebView 중 하나를 평문 `http://example.com`으로
로드합니다(`usesCleartextTraffic` 제한도 없음). 정말 평문으로 나가는지 보려고, 에뮬레이터
프록시를 호스트의 리스너로 돌리고 화면을 열었습니다.

```console
$ adb shell settings put global http_proxy 10.0.2.2:8888   # 호스트 리스너로 프록시
# Secure Channel 화면 진입 → 리스너에 그대로 잡힌 요청:
=== 평문으로 흐른 HTTP 요청 ===
GET http://example.com/ HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0 (Linux; Android 8.0.0; ...) ... Chrome/58 Mobile Safari/537.36
```

요청 라인·Host·헤더가 전부 평문으로 흐릅니다. 중간에 있는 누구든 읽고 바꿀 수 있습니다.
참고로 같은 앱을 API 28+에서 열면 이 요청이 `ERR_CLEARTEXT_NOT_PERMITTED`로 막히니, API 26이
이 관측에 맞는 환경이기도 합니다.

### 6-4. SSL Pinning (Certificate)

`OMTG_NETW_004_SSL_PINNING_WHOLE_CERT`는 `res/raw`에 박아 둔 단일 인증서를 유일한 신뢰
앵커로 씁니다. APK에서 그 인증서를 뽑아 보면 문제가 여럿입니다.

```console
$ unzip -p app-x86-debug.apk res/raw/certificate.pem | openssl x509 -noout -subject -dates
subject= ... CN=www.example.org          # 접속 대상은 example.com — CN 불일치
notBefore=Nov  3 00:00:00 2015 GMT
notAfter =Nov 28 12:00:00 2018 GMT        # 이미 만료(에뮬 시계는 2026)
```

핀 자료가 APK에서 그대로 추출되고, 게다가 만료됐고, CN도 대상과 다릅니다. 화면을 여니 앱은
이 만료·불일치 앵커 때문에 진짜 example.com 인증서를 거부합니다.

```console
$ adb logcat
I System.out: KeyStore: ca                          # 핀 인증서를 앵커로 로드
W System.err: javax.net.ssl.SSLHandshakeException: CertPathValidatorException:
              Trust anchor for certification path not found.
```

이 핀은 앱 코드 레벨이라 Frida 한 방으로 걷힙니다. `checkTrustedRecursive`를 무력화하니
핸드셰이크 예외가 사라지고 연결이 통과합니다.

```console
$ frida -U -p <pid> -l unpin.js
[UNPIN] checkTrustedRecursive -> bypassed         # 이후 SSLHandshakeException 없음
```

### 6-5. Clipboard

`OMTG_DATAST_006_CLIPBOARD`는 민감 입력 칸의 복사 차단 콜백(`setCustomSelectionActionMode
Callback`)이 통째로 주석 처리돼 있습니다. 그래서 민감값을 입력하고 길게 눌러 보면, 막혀야 할
복사 메뉴가 그대로 뜹니다.

![Clipboard 화면 — SECRET-CC-4111111111111111 을 입력하고 롱프레스하자 CUT / COPY / SHARE 선택 메뉴가 그대로 뜬 화면](/assets/img/mastg-playground/clipboard-copy.png)

COPY를 누른 뒤, 다른 앱이 전역 클립보드를 읽는 상황을 Frida로 재현했습니다.

```console
$ frida -U -p <pid> -l readclip.js
[CLIP] global clipboard readable => SECRET-CC-4111111111111111
```

민감값을 복사할 수 있게 두면, 그 값은 시스템 전역 클립보드로 올라가 아무 앱이나 읽어 갑니다.

### 6-6. Keyboard Cache

`OMTG_DATAST_005_KEYBOARD_CACHE`의 핵심은 입력 칸의 `inputType`입니다. 키보드가 토큰을
학습·캐시하지 않게 하려면 `textNoSuggestions`가 있어야 하는데, APK의 레이아웃을 뜯어 보면
정작 이 케이스의 필드는 방어가 돼 있고 다른 칸들이 뚫려 있습니다.

```console
$ aapt dump xmltree app-x86-debug.apk res/layout/content_omtg__datast_005__keyboard__cache.xml
  E: EditText ... android:inputType=0x80001     # NO_SUGGESTIONS 있음 → 방어됨(정상)

$ aapt dump xmltree app-x86-debug.apk res/layout/content_omtg__datast_002__logging.xml
  E: EditText (username) ...                     # inputType 속성 자체가 없음 → 학습·캐시됨(취약)
```

즉 방어의 유무가 한 속성 차이로 갈립니다. `textNoSuggestions`가 없는 로그인 아이디 칸이나
방금 본 클립보드 칸에 넣은 토큰은 IME 개인사전에 남습니다(구체적 캐시 파일 열람은 루트 +
사용하는 키보드에 따라 갈립니다).

---

## 마치며

스물네 개를 훑고 나니 한 문장이 남았습니다. 기기 안에 평문으로 둔 건 뭐든 비밀이 아니고
(내부·외부 저장소·prefs·SQLite·로그·바이너리 문자열 전부 뽑혔습니다), 클라이언트가 내리는
판정과 클라이언트에 둔 열쇠는 결국 뒤집힙니다(자작 암호·하드코딩 키·거꾸로 된 SSL 핀).
검증 없는 입력과 신뢰할 수 없는 코드·콘텐츠(SQL·ContentProvider·/sdcard의 dex·원격 WebView)는
그대로 공격 표면이 되고요. 방어는 결국 같은 얘기입니다 — 비밀은 Keystore나 서버로, 판정은
서버로, 입력은 파라미터 바인딩으로, 코드와 콘텐츠는 신뢰할 수 있는 출처에서만.

이번엔 정적 분석에서 멈추지 않고 각 케이스를 기기에서 직접 눌러 값을 뽑아 본 게 제일
좋았습니다. 저장소부터 네트워크·클립보드까지 실제로 터뜨려 봤고, world-readable 같은 오래된
취약점은 그 시절 안드로이드(API 23)까지 띄워 확인했습니다.

깃허브에서 우연히 발견한 연습용 앱 하나로 MASTG 카테고리를 처음부터 끝까지 훑어볼 수 있어서
좋았습니다. 다음엔 시스템 CA를 심어야 하는 MITM 케이스를 프록시 랩까지 세워서 마저 가 보고
싶습니다. 긴 글 읽어 주셔서 감사합니다.
