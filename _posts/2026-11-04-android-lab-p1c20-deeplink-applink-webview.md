---
layout: post
title: "Deep Link·App Link·WebView 실습 — 스킴 하이재크와 JS 브리지"
date: 2026-11-04 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, DeepLink, AppLink, WebView]
excerpt: "커스텀 스킴 딥링크(myapp://)는 아무 앱이나 같은 스킴을 등록해 가로챌 수 있고(소유권 없음), 검증된 App Link(autoVerify+assetlinks.json)만 도메인 소유가 보장된다. WebView는 setJavaScriptEnabled+addJavascriptInterface로 JS에 Java 메서드를 노출하니 미신뢰 콘텐츠를 로드하면 위험하고, file 접근 플래그와 intent:// 스킴도 표면이다."
---

딥링크와 WebView는 앱의 외부 진입·웹 경계 표면이다. 커스텀 스킴 딥링크는 소유권 검증이 없어 아무 앱이나 가로챌 수 있고, 검증된 App Link만 도메인 소유가 보장된다. WebView는 JS 브리지·파일 접근·intent:// 스킴이 표면이 된다. 이 글은 딥링크 하이재크·App Link 검증·WebView 브리지/파일접근을 교육용 앱에서 재현·수정하는 기록이다. 내가 분석한 Toss ExternalWebActivity(exported WebView)가 이 표면의 실사례다.

> **한 줄 결론**: 커스텀 스킴은 아무 앱이나 가로채고, 검증된 App Link(autoVerify+assetlinks.json)만 도메인 소유가 보장된다. 딥링크 도달성은 검증이 아니라 **exported 상태**가 결정한다. WebView는 `addJavascriptInterface`로 JS에 Java를 노출하니 미신뢰 콘텐츠 로드가 위험하다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 딥링크 하이재크·App Link 검증·WebView 표면을 다룬다. 선수 개념은 [URI(C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/), [WebView·딥링크(HexTree)](/posts/hextree-android-track/), 내 Toss ExternalWebActivity 분석(exported WebView 취약)이다.

## 핵심 개념 — 딥링크와 WebView

- **커스텀 스킴 딥링크**(`myapp://`): 소유권 없음 → **아무 앱이나 같은 스킴 등록해 가로챈다**. `Source-confirmed`
- **App Link**(http(s) + `autoVerify` + `assetlinks.json` Digital Asset Links): 도메인 검증 → 검증된 앱만 수신. 상태는 `adb shell pm get-app-links <pkg>`(강제 지정 시 `pm set-app-links ... STATE_APPROVED`/`STATE_SUCCESS`). `Source-confirmed`
- **도달성**: 타 앱이 딥링크 Activity에 Intent를 보낼 수 있는지는 **exported 상태**에 달렸다(검증이 아님). `Source-confirmed`
- **WebView**(C47): `setJavaScriptEnabled(true)`(기본 false) + `addJavascriptInterface(obj,'name')`로 `@JavascriptInterface` 메서드를 JS에 노출(`@JavascriptInterface`는 API 17 게이트, 4.2 미만 addJavascriptInterface RCE 이력). `setAllowFileAccess`/`setAllowFileAccessFromFileURLs`/`setAllowUniversalAccessFromFileURLs`(file:// origin, 모던 기본 false). `intent://` 스킴을 파싱해 startActivity하는 WebView. `shouldOverrideUrlLoading`. `Source-confirmed`

**신뢰 경계와 위협 모델.** 커스텀 스킴은 신뢰 없음(App Link 검증 필요). WebView가 미신뢰 콘텐츠를 로드하면 JS가 브리지 메서드·file·intent://에 도달한다.

> **[그림 1]** 자작 악성 앱이 커스텀 스킴 콜백(`myapp://cb?token=...`)을 가로챈 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱: 커스텀 스킴 콜백 + exported WebView(브리지·file·intent://) + 방어(App Link·명시 검증·브리지 제거·file false). 상용 앱/실도메인 공격 금지.

## 실습 절차와 관측

### 가설
커스텀 스킴은 자작 악성 앱이 가로채고, 미검증 URL WebView는 임의 페이지 로드·브리지 호출, 방어 버전은 App Link 검증·allowlist·브리지 제거로 차단. `Inferred`

### 절차
1. 커스텀 스킴 콜백을 자작 앱으로 가로챈다.
2. `pm get-app-links`로 App Link 검증 상태를 확인한다.
3. exported WebView에 URL/`intent://`를 주입한다.
4. 브리지 메서드 JS 호출·file 접근을 관측한다.
5. 방어 버전에서 전부 차단을 확인한다.

```bash
adb shell am start -a android.intent.action.VIEW -d "myapp://cb?token=X" com.example.app
adb shell pm get-app-links com.example.app     # verified 상태
```

> **[그림 2]** exported WebView에서 `addJavascriptInterface` 메서드를 JS가 호출한 로그 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ pm get-app-links com.example.app
  Domain verification state:
    example.com: verified
# 커스텀 스킴 myapp://는 자작 악성 앱이 가로챔 (취약)
```

## Root Cause — 왜 이렇게 되는가

커스텀 스킴이 위험한 것은 소유권 검증이 없기 때문이다(App Link가 해결). WebView 위험은 미신뢰 콘텐츠에 Java/파일/컴포넌트를 노출한 것이다. 그리고 딥링크 도달성이 검증이 아니라 exported에 달린 것은, 검증(autoVerify)이 OS의 http(s) 자동 열기만 통제하기 때문이다.

## 방어와 회귀 검증

- (개발자) App Link(autoVerify+assetlinks), URL allowlist, 브리지 최소·`@JavascriptInterface` 신중, file 접근 false, `intent://` 검증. "커스텀 스킴 콜백에 민감정보 없음", "WebView가 allowlist 외 URL 미로드", "브리지 미노출"을 회귀로.
- (연구자) 자작만.

**흔한 실패와 처리.** App Link 검증 실패 → assetlinks.json 미배포/서명 해시 불일치. 브리지 호출 안 됨 → `@JavascriptInterface` 누락(API 17+).

## 버전 차이와 한계

- `@JavascriptInterface` API 17, file 접근 플래그 기본값 버전별, App Link 검증 흐름 진화. targetSdk/기기 기록.
- 에뮬/자작. 상용 앱/실도메인 공격 금지.

## 정리

- 커스텀 스킴은 소유권 없음, App Link만 검증됨.
- 딥링크 도달성은 검증이 아니라 exported가 결정.
- WebView는 브리지·file·intent://가 표면.

**점검 질문** — (1) 커스텀 스킴과 App Link의 신뢰 차이는? (2) 딥링크 도달성을 결정하는 것은 검증인가 exported인가? (3) WebView에서 JS가 Java에 닿는 조건은?

**참고** — [App Links](https://developer.android.com/training/app-links) · [WebView](https://developer.android.com/reference/android/webkit/WebView) · [C11 가시성·URI](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) · [C47 WebView(HexTree)](/posts/hextree-android-track/)

*다음 글: [Ghidra/Rizin native 분석](/posts/android-lab-p1c21-ghidra-rizin-native/).*
