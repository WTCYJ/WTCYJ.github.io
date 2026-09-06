---
layout: post
title: "[Android 앱 보안 S09] WebView 보안"
date: 2026-09-02 17:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, WebView, SSL, onReceivedSslError, MITM, JavaScript, InsecureShop, 학습기록]
excerpt: "S08에서 딥링크로 임의 URL을 앱 WebView에 넣었습니다. 그 WebView가 어떻게 설정돼 있느냐가 피해 크기를 정합니다. InsecureShop의 WebView는 자바스크립트를 켜 두고, 파일 URL의 교차오리진 접근까지 허용하며, 결정적으로 모든 SSL 인증서 오류를 무시하고 그냥 진행합니다. 자체 서명 인증서로 HTTPS를 띄워, 경고 하나 없이 로드되는 걸 확인했습니다."
---

> S08의 딥링크가 넣어 준 URL을, 이번엔 그 URL이 도착하는 WebView 쪽에서 봅니다. 같은 임의 URL 로드라도 WebView 설정에 따라 피해가 달라집니다.

WebView는 앱 안에 심은 브라우저입니다. 그래서 브라우저가 지키는 안전장치(인증서 검증, 오리진 격리)를 앱이 꺼 버리면, 그 안에서 도는 페이지는 무엇이든 할 수 있게 됩니다. InsecureShop의 WebView가 그런 상태입니다. 자바스크립트가 켜져 있고, 파일 URL의 교차오리진 접근이 열려 있고, 무엇보다 인증서 오류를 전부 무시합니다. 그중 가장 눈에 띄는 SSL 무시를 자체 서명 인증서로 직접 확인했습니다.

---

## 실습 목표

- WebView의 자바스크립트·파일 접근·JS 인터페이스 설정을 확인한다.
- SSL 오류 처리(`onReceivedSslError`)가 안전한지 확인한다.
- 자체 서명 인증서 HTTPS가 경고 없이 로드되는지 실측한다.

---

## 윤리적 범위와 허가 조건

피해 앱은 내가 소유한 InsecureShop, 로드한 페이지는 내 호스트의 로컬 HTTPS 테스트 서버(`https://10.0.2.2:8443`, 자체 서명 인증서)입니다. 실제 외부 도메인은 쓰지 않았고 모든 조작은 `aas-api33` 에뮬레이터 안입니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 피해 앱: `com.insecureshop` (S02)
- 로컬 HTTPS 서버: `python`(`ssl` 모듈) + `openssl` 자체 서명 인증서, 호스트 `10.0.2.2:8443`
- 정적 근거: S03 디컴파일 결과

---

## 위협 모델 — WebView가 얼마나 열려 있나

- 자바스크립트가 켜져 있는가? 임의 페이지의 JS가 도는가?
- 파일 URL이 교차오리진 접근을 하는가(`allowUniversalAccessFromFileURLs`)?
- 네이티브 브리지(`@JavascriptInterface`)가 있는가?
- 인증서 오류를 어떻게 처리하는가?

---

## 재현 절차

### 1. WebView 설정 (정적)

세 WebView 액티비티(WebViewActivity·WebView2Activity·PrivateActivity) 모두 같은 위험 설정을 씁니다.

```java
settings.setJavaScriptEnabled(true);                    // JS 실행
settings.setAllowUniversalAccessFromFileURLs(true);     // file:// 의 교차오리진 접근 허용
webview.setWebViewClient(new CustomWebViewClient());    // ← 문제의 클라이언트
```

`@JavascriptInterface`로 노출한 네이티브 브리지는 없었습니다(즉 JS에서 앱 자바 메서드를 직접 부르는 경로는 없음). 대신 문제는 `CustomWebViewClient`에 있습니다.

### 2. 모든 SSL 오류를 무시하는 클라이언트 (정적)

디컴파일한 `CustomWebViewClient`는 이게 전부입니다.

```java
public class CustomWebViewClient extends WebViewClient {
    @Override
    public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
        if (handler != null) handler.proceed();   // 어떤 인증서 오류든 그냥 진행
    }
}
```

인증서가 자체 서명이든, 만료됐든, 호스트가 안 맞든 — `handler.proceed()`로 전부 통과시킵니다. 이건 HTTPS의 신뢰 근거를 통째로 없애는 것과 같습니다. 중간자(MITM)가 가짜 인증서를 내밀어도 WebView는 그대로 로드합니다.

### 3. 자체 서명 HTTPS 로드 (동적)

호스트에 자체 서명 인증서로 HTTPS 서버를 띄우고, S08의 딥링크로 그 페이지를 로드했습니다.

```console
$ openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 2 -nodes   # 자체 서명
$ python https_server.py        # 호스트 10.0.2.2:8443, ssl.wrap_socket
$ adb shell am start -a android.intent.action.VIEW \
        -d "insecureshop://com.insecureshop/web?url=https://10.0.2.2:8443/attacker.html"
```

일반 앱이었다면 여기서 "신뢰할 수 없는 인증서" 경고 페이지가 떠야 합니다. InsecureShop은 경고 없이 페이지를 그대로 렌더했습니다.

---

## 스크린샷

자체 서명(신뢰 안 됨) 인증서의 HTTPS 페이지가 경고 하나 없이 WebView에 로드된 화면입니다. 페이지 안 자바스크립트가 실제 로드된 주소(`https://10.0.2.2:8443/...`)를 찍어, 라이브로 렌더됐음을 보여 줍니다.

![WebViewActivity에 로드된 자체 서명 HTTPS 페이지 — 보라 배경에 "SSL-ERROR IGNORED", "자체 서명(신뢰 안 됨) 인증서의 HTTPS인데도 onReceivedSslError → handler.proceed() 때문에 경고 없이 로드됐다", "href = https://10.0.2.2:8443/attacker.html"](/assets/img/android-app-security/S09/01-ssl-ignored.png)

WebView 설정·SSL 처리 코드와 재현 명령은 `assets/evidence/android-app-security/S09/`에 남겼습니다.

---

## 관측 결과

- 세 WebView 모두 자바스크립트가 켜져 있고, 임의 페이지의 JS가 실행된다(S08의 로드 주소 출력도 그 JS였다).
- `setAllowUniversalAccessFromFileURLs(true)`로 파일 URL의 교차오리진 접근이 열려 있다.
- `@JavascriptInterface` 네이티브 브리지는 없다.
- `CustomWebViewClient`가 모든 SSL 오류를 `handler.proceed()`로 무시한다. 자체 서명 HTTPS가 경고 없이 로드됐다.

---

## 근본 원인과 보안 영향

- `onReceivedSslError`에서 `handler.proceed()`를 부르는 순간 HTTPS는 의미가 없어집니다. 중간자가 가짜 인증서로 트래픽을 가로채도 앱은 정상으로 여깁니다. 여기에 S08의 임의 URL 로드가 겹치면, 공격자는 자기 페이지를 그대로 앱 안에 띄웁니다.
- 자바스크립트가 켜진 WebView에 임의 페이지를 로드하면 그 JS가 앱의 WebView 컨텍스트에서 돕니다. 네이티브 브리지가 있었다면 앱 기능까지 닿았겠지만, 이 앱엔 없어 화면·오리진 범위에서 멈춥니다.
- `allowUniversalAccessFromFileURLs(true)`는 `file://` 페이지가 다른 오리진·파일을 읽게 열어 둔 설정입니다. 최신 안드로이드가 외부저장 `file://`을 막아 이번엔 파일 절도까지 가진 않았지만, 켜 둘 이유가 없는 위험 설정입니다.

## 수정 방법

- `onReceivedSslError`를 오버라이드해 `proceed()` 하지 않는다. 기본 동작(오류 시 취소)을 두거나, 정말 필요한 특정 핀만 검증한다.
- 필요 없으면 `setJavaScriptEnabled(false)`, `setAllowUniversalAccessFromFileURLs(false)`(그리고 `setAllowFileAccess(false)`)로 표면을 줄인다.
- WebView에 로드할 URL은 화이트리스트로 검증한다(S08). 신뢰할 수 없는 콘텐츠는 애초에 로드하지 않는다.

수정 전후는 이 메서드의 존재 여부입니다.

```java
// 전: 모든 인증서 오류 통과
public void onReceivedSslError(WebView v, SslErrorHandler h, SslError e){ h.proceed(); }
// 후: 오버라이드하지 않음(기본 = 오류 시 로드 취소). 필요하면 정식 핀 검증만.
```

---

## 재검증

자체 서명 인증서라 신뢰 저장소에 없는데도, WebView는 경고 없이 페이지를 렌더했고 페이지 JS가 로드 주소를 찍었습니다. 앱의 `Prefs.data`에도 `https://10.0.2.2:8443/attacker.html`이 기록됐습니다. "인증서 검증이 무력화됐다"가 화면과 저장값으로 함께 확인됩니다.

---

## 참고 자료

- Android Developers — `WebView`, `WebSettings`(JavaScript·파일 접근)
- Android Developers — `WebViewClient.onReceivedSslError`와 인증서 검증
- OWASP MASVS — Platform(WebView) 요구사항
