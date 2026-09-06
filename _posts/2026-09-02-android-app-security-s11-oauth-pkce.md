---
layout: post
title: "[Android 앱 보안 S11] 인증과 세션 — OAuth PKCE"
date: 2026-09-02 19:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, OAuth, PKCE, 인증, 세션, 토큰, 학습기록]
excerpt: "모바일 OAuth의 표준인 Authorization Code + PKCE를 처음부터 끝까지 돌려 봤습니다. InsecureShop엔 OAuth가 없어서, 모의 인증 서버와 클라이언트 앱을 직접 만들어 verifier/challenge 생성, 인가 코드 발급, 토큰 교환까지 화면에 찍었습니다. 그리고 도난당한 코드를 틀린 verifier로 교환하려 하면 PKCE가 그것을 막는다는 것, 등록되지 않은 redirect_uri는 거부된다는 것을 함께 확인했습니다."
---

> 지금까지는 InsecureShop의 결함을 팠습니다. 이번 편은 반대로, 제대로 된 인증이 무엇을 어떻게 지키는지를 직접 만들어 확인합니다. 모바일 OAuth의 표준인 Authorization Code + PKCE입니다.

모바일 앱에서 OAuth를 안전하게 하는 핵심은 PKCE입니다. 앱은 브라우저를 통해 인가 코드를 받는데, 그 코드가 중간에 새면(다른 앱이 같은 redirect를 가로채는 등) 공격자가 토큰을 받아 갈 수 있습니다. PKCE는 "코드를 요청한 그 클라이언트만 코드를 토큰으로 바꿀 수 있게" 묶어 이걸 막습니다. 이번 대상 InsecureShop엔 OAuth가 없어서, 모의 인증 서버와 클라이언트 앱을 직접 만들어 흐름 전체와 그 방어를 눈으로 확인했습니다.

---

## 실습 목표

- Authorization Code + PKCE 흐름(verifier/challenge → code → token)을 실제로 수행한다.
- state로 CSRF를, redirect_uri 정확 일치로 코드 탈취를 막는 걸 확인한다.
- access token과 id token의 차이를 확인한다.
- 도난 코드를 틀린 verifier로 교환하려 할 때 PKCE가 막는지 확인한다.

---

## 윤리적 범위와 허가 조건

인증 서버와 클라이언트 모두 내가 직접 작성한 로컬 모의물입니다(서버 `http://10.0.2.2:8011`, 앱 `com.aas.oauth`). 실제 IdP나 계정은 쓰지 않았고, 모든 조작은 `aas-api33` 에뮬레이터 안입니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01)
- 모의 인증 서버: `python`(`/authorize`, `/token`, PKCE S256 검증)
- 클라이언트: 직접 손빌드한 앱(`SecureRandom`·`MessageDigest`·`HttpURLConnection`), S05 툴체인

---

## 위협 모델 — 코드가 새도 안전한가

- 인가 코드가 중간에 탈취되면 토큰까지 넘어가는가? → PKCE가 막아야 한다.
- state 없이 응답을 위조할 수 있는가? → state로 막아야 한다.
- 아무 redirect_uri나 받아 코드를 다른 곳으로 보낼 수 있는가? → 정확 일치로 막아야 한다.

---

## 재현 절차

### 1. PKCE 준비 (클라이언트)

클라이언트가 매 요청마다 무작위 `code_verifier`를 만들고, 그 SHA-256을 `code_challenge`로 씁니다.

```java
byte[] vb = new byte[32]; new SecureRandom().nextBytes(vb);
String verifier  = base64url(vb);
String challenge = base64url(sha256(verifier));   // S256
String state     = base64url(random16);           // CSRF 방지용
```

### 2. 인가 요청 (/authorize)

`code_challenge`와 `state`, 그리고 등록된 `redirect_uri`를 담아 인가를 요청하면, 서버가 코드를 발급하며 그 코드에 `challenge`를 묶어 저장합니다. 응답의 `state`가 보낸 값과 같은지도 확인합니다.

```
[/authorize]
 code = mXpJslPqW9hXpV0BqbxVZg
 state 검증: sent==returned ? OK
```

### 3. 토큰 교환 (/token)

이제 원래의 `code_verifier`를 함께 보내 코드를 토큰으로 바꿉니다. 서버는 `S256(verifier) == 저장된 challenge`를 확인하고 통과하면 토큰을 줍니다.

```
[/token  올바른 verifier]
 access_token = at_RUP4qOyxXq3h55aH
 id_token     = eyJhbGciOiAibm9uZSIsICJ0…
 id_token claims = {"sub":"user-42","name":"Test User","iss":"aas-mock","aud":"aas-client","iat":...}
```

토큰이 둘입니다. `access_token`은 API를 부를 때 쓰는 열쇠고, `id_token`은 "누가 로그인했는가"를 담은 신원 증명(JWT)입니다. 둘을 섞어 쓰면 안 됩니다 — API 인가에 id_token을 쓰거나, 신원 확인에 access_token을 쓰면 사고가 납니다.

### 4. PKCE가 막는 것 — 도난 코드 재사용

핵심 방어를 직접 시험했습니다. 새 코드를 발급받은 뒤, 원래 verifier가 아니라 틀린 verifier로 교환을 시도했습니다(코드만 훔친 공격자를 흉내낸 것입니다).

```
[/token  틀린 verifier = 도난 code 재사용 시도]
 error  = invalid_grant
 reason = PKCE verifier mismatch
 => PKCE 가 도난 code 의 교환을 막았다.
```

코드를 손에 넣어도, 그 코드를 요청한 클라이언트가 쥔 verifier가 없으면 토큰으로 못 바꿉니다. 이게 PKCE가 하는 일입니다.

### 5. redirect_uri 정확 일치

등록되지 않은 redirect_uri로 인가를 요청하면 서버가 거부합니다.

```
[/authorize  악성 redirect_uri]
 error = invalid_redirect_uri  (등록값과 정확 일치만 허용)
```

`evil://cb` 같은 값은 등록값(`aasoauth://cb`)과 다르므로 코드 발급 자체가 안 됩니다. 부분 일치나 접두/접미 매칭이 아니라 정확 일치여야 코드가 엉뚱한 곳으로 새지 않습니다.

---

## 스크린샷

클라이언트 앱이 흐름 전체를 수행하고 결과를 찍은 화면입니다. PKCE 준비, 코드 발급과 state 검증, 토큰 교환(두 토큰과 클레임), 그리고 틀린 verifier·악성 redirect_uri가 거부되는 것까지 한 화면에 있습니다.

![OAuthPKCE 앱 실행 화면 — PKCE verifier/challenge(S256), /authorize code와 state OK, /token access_token·id_token·claims, 틀린 verifier는 invalid_grant(PKCE mismatch)로 거부, 악성 redirect_uri는 invalid_redirect_uri로 거부](/assets/img/android-app-security/S11/01-pkce.png)

모의 서버·클라이언트 소스와 결과 원문은 `assets/evidence/android-app-security/S11/`에 남겼습니다.

---

## 관측 결과

- Authorization Code + PKCE 흐름이 끝까지 성립했다(verifier/challenge → code → token).
- state가 왕복 일치로 검증됐고, redirect_uri는 정확 일치만 통과했다.
- access_token과 id_token이 구분돼 발급됐고, id_token 클레임을 디코드해 확인했다.
- 틀린 verifier(도난 코드 재사용)는 `invalid_grant`(PKCE mismatch)로 거부됐다.

---

## 근본 원인과 보안 영향

- PKCE 없이 Authorization Code만 쓰면, 코드를 가로챈 공격자가 그대로 토큰을 받습니다. 모바일은 redirect가 커스텀 스킴·앱 링크로 오가 가로채기가 특히 쉬워, PKCE가 사실상 필수입니다.
- state가 없으면 인가 응답을 위조·재생해 세션을 고정하거나 CSRF를 걸 수 있습니다.
- redirect_uri를 느슨하게 매칭하면 코드가 공격자 통제 위치로 새 나갑니다.
- access token과 id token을 혼용하면 인가·인증 경계가 무너집니다.

## 수정 방법 / 권고

- 모바일 OAuth는 Authorization Code + PKCE(S256)로만 한다. Implicit 그랜트는 쓰지 않는다.
- `state`(그리고 OIDC라면 `nonce`)를 매 요청 무작위로 만들고 응답에서 검증한다.
- redirect_uri는 서버에서 정확 일치로만 허용한다.
- access token은 API 인가에, id token은 신원 확인에만 쓴다. 토큰은 안전한 저장소(Keystore 기반, S05)에 둔다.
- 로그아웃 시 서버에서 토큰을 폐기(revocation)하고, 클라이언트의 access/refresh/id 토큰을 모두 지운다. 클라이언트에서 지우기만 하고 서버가 살려 두면 탈취된 토큰이 계속 유효하다.

---

## 재검증

같은 흐름에서 올바른 verifier는 토큰을 받아 냈고, 틀린 verifier는 `invalid_grant`로 거부됐습니다. 두 결과가 같은 화면에 있어, "코드를 요청한 클라이언트만 코드를 쓸 수 있다"는 PKCE의 성질이 성립·비성립 양쪽으로 확인됩니다. 악성 redirect_uri 거부도 함께 찍혔습니다.

---

## 참고 자료

- RFC 7636 — Proof Key for Code Exchange (PKCE)
- OAuth 2.0 for Native Apps (RFC 8252)
- OpenID Connect — id_token과 access_token의 구분
