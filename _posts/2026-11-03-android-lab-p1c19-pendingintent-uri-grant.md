---
layout: post
title: "PendingIntent·URI grant 실습 — 하이재크와 confused deputy"
date: 2026-11-03 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, PendingIntent, URIPermission, ConfusedDeputy]
excerpt: "PendingIntent는 생성자의 정체성으로 실행되는 토큰이라, mutable로 넘기면 보유자가 빈 필드를 채워 생성자 권한으로 발사한다(API 31부터 IMMUTABLE/MUTABLE 명시 필수). URI 권한은 content:// 하나에만 임시 위임인데, 악성 발신자가 URI를 피해자 자신의 사적 provider로 겨누면 피해자가 제 파일을 대신 읽어 넘기는 confused deputy가 된다."
---

PendingIntent와 URI grant는 권한 위임의 표면이다. PendingIntent는 생성자 정체성으로 실행되는 토큰이라 mutable로 넘기면 하이재크되고, URI 권한은 발신자가 준 URI를 무비판 신뢰하면 confused deputy가 된다. 이 글은 mutable PendingIntent 하이재크와 URI grant confused-deputy를 교육용 앱에서 재현·수정하는 기록이다.

> **한 줄 결론**: mutable PendingIntent를 타 앱에 넘기면 빈 필드를 채워 생성자 권한으로 발사된다(API 31부터 IMMUTABLE/MUTABLE 명시 필수). 미신뢰 URI를 무검증 읽으면, 그 URI가 피해자 자신의 provider를 가리켜 피해자가 제 파일을 대신 읽는 confused deputy가 된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 PendingIntent 하이재크와 URI grant confused-deputy를 다룬다. 선수 개념은 [Intent(15장)](/posts/android-lab-p1c15-activity-intent-injection/)·[URI(C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)·[컴포넌트(C21)](/posts/android-concept-atlas-c21-components-binder/)다.

## 핵심 개념 — PendingIntent와 URI

- **PendingIntent**: 생성자의 정체성/권한으로 실행되는 토큰. **API 31+는 `FLAG_IMMUTABLE`(0x04000000)/`FLAG_MUTABLE`(0x02000000) 명시 필수**. mutable을 타 앱에 넘기면 빈 필드를 채워 생성자 권한으로 발사(하이재크). A14는 암시적 base Intent의 mutable PendingIntent를 차단. `Source-confirmed`
- **URI 권한**: `FLAG_GRANT_READ_URI_PERMISSION`(0x1)/`WRITE`(0x2)/`PERSISTABLE`(0x40)/`PREFIX`(0x80). provider가 opt-in(`android:grantUriPermissions`/`<grant-uri-permission>`)해야. `Source-confirmed`
- **confused-deputy(URI 읽기)**: 앱이 미신뢰 Intent가 준 content:// URI를 무비판적으로 읽는데, 그 URI가 **피해자 자신의 사적 provider**를 가리키면 피해자가 제 파일을 공격자에게 넘긴다(C11). `Source-confirmed`

**신뢰 경계와 위협 모델.** PendingIntent는 생성자 권한을 위임한다 — mutable+암시적이면 하이재크. URI는 발신자가 준 것을 무비판 신뢰하면 안 된다.

> **[그림 1]** 악성 보유자 앱이 mutable PendingIntent의 빈 필드를 채워 생성자 권한으로 발사한 로그 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱: mutable+암시적 PendingIntent 발급 앱 + 미신뢰 URI 읽는 앱 + 방어 버전. 소유/교육용 앱만.

## 실습 절차와 관측

### 가설
mutable 버전은 필드 주입으로 생성자 권한 동작, URI 읽기 앱은 피해자 provider URI로 자기 파일 유출, 방어 버전은 IMMUTABLE·authority 검증으로 차단. `Inferred`

### 절차
1. mutable PendingIntent 발급 앱 + 악성 보유자 앱으로 하이재크한다.
2. URI 읽기 앱에 피해자 provider URI를 전달 → 자기 파일 유출.
3. 방어 버전(IMMUTABLE·명시 base·authority 검증)에서 차단을 확인한다.
4. A14 기기에서 mutable+암시적 차단을 확인한다.

```java
// 방어: 명시적 base + IMMUTABLE
PendingIntent pi = PendingIntent.getActivity(
    ctx, 0, explicitIntent, PendingIntent.FLAG_IMMUTABLE);
// URI 읽기 전 발신자 URI의 authority를 검증 (자기 provider면 거부)
```

> **[그림 2]** URI 읽기 앱이 피해자 provider URI로 자기 파일을 읽어 넘긴 confused-deputy 로그 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[hijack] holder filled blank Intent -> fired with creator uid/perm (취약)
[confused-deputy] victim read content://victim.provider/secret for attacker (취약)
```

## Root Cause — 왜 이렇게 되는가

하이재크는 mutable이 생성자 권한을 위임하기 때문, confused-deputy는 피해자가 공격자 제어 URI를 자기 권한으로 읽기 때문이다 — 둘 다 "입력 신뢰" 결함이다. API 31의 IMMUTABLE/MUTABLE 명시 강제는 개발자가 이 선택을 의식하게 만든 완화다.

## 방어와 회귀 검증

- (개발자) PendingIntent는 IMMUTABLE·명시 base, URI는 authority/소유 검증, provider opt-in 최소. "PendingIntent 필드 주입 불가", "미신뢰 URI 무검증 읽기 없음"을 회귀로.
- (연구자) 자작만.

**흔한 실패와 처리.** A14 mutable 오류 → 명시 base로. URI 읽기 실패 → provider opt-in/authority(방어).

## 버전 차이와 한계

- API 31 IMMUTABLE/MUTABLE 필수, A14 mutable+암시적 차단.
- 에뮬/자작 다중 앱. 상용 공격 금지.

## 정리

- mutable PendingIntent는 생성자 권한으로 하이재크된다.
- 미신뢰 URI를 무검증 읽으면 confused-deputy.
- IMMUTABLE·authority 검증이 방어.

**점검 질문** — (1) mutable PendingIntent가 위험한 이유는? (2) URI confused-deputy의 성립 조건은? (3) FLAG_IMMUTABLE/MUTABLE는 언제부터 필수인가?

**참고** — [PendingIntent](https://developer.android.com/reference/android/app/PendingIntent) · [C11 가시성·URI](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) · [C21 컴포넌트](/posts/android-concept-atlas-c21-components-binder/)

*다음 글: [Deep Link·App Link·WebView 실습](/posts/android-lab-p1c20-deeplink-applink-webview/).*
