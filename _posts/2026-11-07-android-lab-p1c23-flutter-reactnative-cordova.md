---
layout: post
title: "Flutter·React Native·Cordova 구조 비교 — 크로스플랫폼 앱을 어디서 여는가"
date: 2026-11-07 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Flutter, ReactNative, Cordova]
excerpt: "크로스플랫폼 앱은 로직 위치가 프레임워크마다 다르다. Flutter는 Dart를 libapp.so로 AOT 컴파일해 jadx엔 엔진 글루만 보이고 시스템 프록시/NSC를 안 써서 Burp에 안 잡힌다(reFlutter 필요). React Native는 assets의 JS 번들(Hermes면 .hbc 바이트코드), Cordova는 assets/www의 웹앱이라 WebView 보안(20장)이 그대로 지배한다 — jadx만 믿으면 코드를 못 본다."
---

크로스플랫폼 앱은 분석 접근이 완전히 다르다. jadx가 DEX를 잘 열어도, Flutter/RN/Cordova는 정작 로직이 DEX 밖에 있어서 "코드가 안 보이는" 착시가 생긴다. 프레임워크를 먼저 식별하고 각각의 코드 위치·인터셉션·RE 도구로 갈아타야 한다. 이 글은 세 프레임워크의 구조 차이를 자작 앱으로 관측하고, 특히 Flutter가 왜 Burp에 안 잡히는지를 정리한 기록이다.

> **한 줄 결론**: Flutter는 Dart를 `libapp.so`로 AOT 컴파일하고 시스템 프록시/NSC를 안 써서 Burp에 트래픽이 안 잡힌다(reFlutter로 패치). RN 로직은 assets의 JS 번들(Hermes면 `.hbc`), Cordova는 `assets/www`의 웹앱이라 WebView 보안이 그대로 지배한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Flutter/RN/Cordova의 코드 위치·인터셉션·RE 차이를 다룬다. 선수 개념은 [jadx(4장)](/posts/android-lab-p1c04-jadx-static-analysis/)의 DEX 정적분석, [인터셉션(11장)](/posts/android-lab-p1c11-burp-mitmproxy-intercept/)의 프록시/NSC, [WebView(20장)](/posts/android-lab-p1c20-deeplink-applink-webview/)의 브리지 표면이다.

## 핵심 개념 — 프레임워크별 코드 위치

- **Flutter**: Dart를 **AOT로 `lib/<abi>/libapp.so`(Dart 스냅샷)**에 컴파일 → 표준 DEX가 아니라 jadx엔 엔진 글루만 보인다. RE는 Dart 스냅샷 도구(reFlutter·Blutter). 네트워킹이 Dart 런타임 자체라 **시스템 프록시/NSC를 안 탄다** → Burp에 트래픽이 안 잡히고, reFlutter로 엔진을 패치해야 인터셉션이 된다(가장 흔한 함정). `Source-confirmed`
- **React Native**: 로직이 `assets/index.android.bundle` — Hermes 엔진이면 **`.hbc`(Hermes 바이트코드)**(hermes-dec/hbctool로 디컴파일), 아니면 평문/미니파이 JS. 네이티브 모듈은 Java/native로 브리지된다. `Source-confirmed`
- **Cordova/Ionic**: `assets/www`의 웹앱(HTML/JS) + WebView 호스트 → **WebView 보안(20장)·JS 브리지가 그대로 지배**한다. 설정은 `config.xml`. `Source-confirmed`

**신뢰 경계와 위협 모델.** 프레임워크마다 코드·네트워크·브리지 위치가 달라 표면도 다르다 — Cordova는 WebView 표면, Flutter는 프록시 우회가 선결, RN은 번들에 남은 로직/키가 표면이다. 대상은 자작 앱만.

> **[그림 1]** 자작 Flutter 앱을 unzip해 `lib/arm64-v8a/libapp.so`가 있고 jadx엔 엔진 글루만 보이는 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 Flutter/RN/Cordova 앱 각 하나로 코드 위치·인터셉션·브리지 차이를 관측한다. 상용 앱 RE는 허가 대상만.

## 실습 절차와 관측

### 가설
Flutter 앱은 Burp에 트래픽이 안 잡히고 reFlutter로 잡히며, RN 번들엔 로직/키가 남고, Cordova는 20장 WebView 공격이 그대로 성립한다. `Inferred`

### 절차
1. 각 앱을 unzip해 코드 위치를 확인한다(libapp.so / bundle / www).
2. Flutter를 Burp로 시도(실패)한 뒤 reFlutter로 패치해 인터셉션한다.
3. RN 번들을 (Hermes면 hbctool로) 디컴파일해 로직/키를 본다.
4. Cordova WebView에 20장 공격을 적용한다.
5. 프레임워크별 표면을 표로 정리한다.

```bash
unzip app.apk -d out
# Flutter:  out/lib/arm64-v8a/libapp.so   → Blutter/reFlutter
# RN:       out/assets/index.android.bundle → (Hermes?) hbctool
# Cordova:  out/assets/www/*.html,*.js
```

> **[그림 2]** Flutter 앱이 Burp엔 트래픽 0이다가 reFlutter 패치 후 요청이 잡히는 대비 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[Flutter] Burp: (no traffic) → reFlutter patched: GET https://api... 200
[RN] assets/index.android.bundle: Hermes .hbc → hbctool 디컴파일
[Cordova] assets/www/index.html + JS bridge → 20장 표면
```

## Root Cause — 왜 이렇게 되는가

Flutter가 프록시를 안 쓰는 것은 Dart 런타임이 자체 네트워킹을 하기 때문이다 — 그래서 시스템 NSC/프록시 밖에 있고, 엔진 자체를 패치(reFlutter)해야 트래픽이 노출된다. Cordova가 WebView 표면인 것은 본질이 WebView에 얹힌 웹앱이기 때문이고, RN 로직이 번들에 남는 것은 JS가 인터프리터/바이트코드로 배포되기 때문이다. 요컨대 "코드가 어디 있나"가 곧 "어떤 도구를 쓰나"를 결정한다.

## 방어와 회귀 검증

- (개발자) Flutter도 pinning·비밀 서버화, RN 번들에 비밀 하드코딩 금지, Cordova WebView는 20장 방어를 그대로. 프레임워크별로 "번들/스냅샷에 하드코딩 비밀 없음"을 회귀로.
- (연구자) 자작 앱만. 상용 앱 RE는 허가 대상만.

**흔한 실패와 처리.** Flutter 트래픽 없음 → 정상, reFlutter 필요. RN 번들이 `.hbc` → hermes-dec/hbctool. Blutter 실패 → Dart/Flutter 버전 불일치(버전별 스냅샷 포맷 상이).

## 버전 차이와 한계

- Flutter/Dart 스냅샷 포맷·Hermes on/off·Cordova 버전에 따라 산출물이 달라진다 → 버전을 기록한다.
- 자작 앱 기준. arm64 우선(내 관측은 실기기).

## 정리

- Flutter=libapp.so(AOT Dart)·프록시 우회 필요, RN=assets 번들(Hermes .hbc), Cordova=assets/www(WebView).
- Flutter는 Burp에 안 잡힌다 — reFlutter로 엔진 패치.
- Cordova는 WebView 보안이 그대로 지배한다.

**점검 질문** — (1) Flutter가 Burp로 안 잡히는 이유와 우회 방법은? (2) RN 로직은 어디에 있고 Hermes면 무엇이 되나? (3) Cordova가 의존하는 보안 표면은?

**참고** — [Flutter](https://docs.flutter.dev) · [React Native](https://reactnative.dev) · [reFlutter](https://github.com/Impact-I/reFlutter) · [C47 WebView(HexTree)](/posts/hextree-android-track/)

*다음 글: [MobSF 자동 분석 결과 수동 검증](/posts/android-lab-p1c24-mobsf-verification/).*
