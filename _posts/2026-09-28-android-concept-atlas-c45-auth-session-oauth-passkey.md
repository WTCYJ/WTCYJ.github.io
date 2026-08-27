---
layout: post
title: "Android Security Concept Atlas C45 - 인증·세션·OAuth/OIDC·passkey, 토큰과 리다이렉트가 새는 곳"
date: 2026-09-28 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, OAuth, OIDC, PKCE, Passkey, WebAuthn, Session, Token, CredentialManager, ConceptAtlas, 학습기록]
excerpt: "내 reporch OAuth 버그의 교훈이 이 편의 핵심입니다: 계정을 사용자가 바꿀 수 있는 username/email에 묶으면 계정 탈취가 되고, 불변의 sub+iss에 묶어야 하죠. OAuth 2.0은 '무엇을 해도 되는가'(access token)이고 OIDC의 ID token이 '누구인가'인데, access token을 신원 증명으로 쓰는 게 대표적 혼동입니다. 네이티브 앱은 client_secret을 못 숨기니 authorization code + PKCE가 필수고, 커스텀 스킴 리다이렉트는 아무 앱이나 등록해 가로채니 verified App Link + 시스템 브라우저(WebView 금지)로 막습니다. passkey는 rpId(도메인)에 묶여 피싱 저항이 있고, 토큰은 Keystore에 넣지 평문 prefs에 안 넣죠. Tier 8 앱 인증 모듈입니다."
---

> **Concept Atlas 모듈**: C45 — 인증·세션·OAuth/OIDC·passkey
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 중급 · **선수 개념**: C02(인증/인가), C40(Keystore)
> **성격**: 보완 편.

C02에서 인증과 인가를 구분했습니다. 이 편은 그 인증의 **앱 레벨 구현** — 세션 토큰·OAuth·passkey이고, 내 **reporch OAuth 버그**가 정확히 여기 삽니다.

한 문장으로: **OAuth는 '무엇을 해도 되는가'(access token), OIDC ID token이 '누구인가'이며, 계정은 사용자가 바꿀 수 없는 불변 식별자(sub+iss)에 묶어야 한다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **세션 토큰**: bearer(소유=권한). access(단명, 요청마다) / refresh(장수, 토큰 엔드포인트만).
- **OAuth 2.0**=인가(access token) / **OIDC**=인증(ID token). 네이티브=**code + PKCE**.
- **passkey**=WebAuthn 공개키(rpId 바인딩, 피싱 저항). Android **Credential Manager**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

C02(인증 vs 인가)의 **앱 레벨 구현**입니다. 토큰은 Keystore(C40/C44)에 저장하고, OAuth 리다이렉트는 딥링크(C11/C21/C47)로 오며 TLS(C46) 위에서 흐릅니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **세션**: 로그인 후 토큰을 이후 요청에 제시. **access**(분~1시간, `Authorization: Bearer …`) / **refresh**(일~월, **리소스 서버엔 안 보냄**, 토큰 엔드포인트에서 새 access로 교환). opaque bearer(서버 조회) vs JWT(자체 포함·오프라인 검증 but 폐기 어려워 단명 필수).
- **OAuth/OIDC**: OAuth 2.0=**access token**(위임 접근). OIDC=**ID token**(서명 JWT, sub/aud/iss/exp). 네이티브(public client, secret 못 숨김)=**authorization code + PKCE**.
- **passkey**: WebAuthn 공개키 쌍. 앱 프로세스(EL0), 개인키는 보안 하드웨어/E2E 동기화.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **bearer = 소유가 곧 권한**: 홀더 바인딩이 없어 토큰 도난 = 남은 수명 동안 완전 사칭. TLS 전송(C46) + 고가치는 DPoP(RFC 9449)/mTLS로 sender-constraint.
- **신뢰하면 안 되는 것들**:
  - **"access token이 신원 증명"** — access는 "무엇을 해도"입니다. 신원은 **OIDC ID token**(sub). access token을 신원으로 쓰거나 ID token을 API에 보내는 게 대표 혼동.
  - **"계정을 email/username에 바인딩"** — **불변 `sub`+`iss`**에 묶어야 합니다. 사용자가 바꿀 수 있는 값에 묶으면 계정 탈취(**내 reporch OAuth-complete username 버그**가 정확히 이것).
  - **"네이티브에 client_secret을 박으면 confidential"** — APK에서 추출됩니다. 코드 교환은 **PKCE**가 지킵니다(`code_challenge = base64url(SHA-256(code_verifier))`, 생 해시가 아님).
  - **"커스텀 스킴 리다이렉트는 안전"** — 아무 앱이나 같은 스킴을 등록해 code를 가로챕니다. **verified App Link**(https, autoVerify+assetlinks.json) + PKCE + **시스템 브라우저/Custom Tabs**(WebView 금지 — 호스트 앱이 자격증명·쿠키를 읽음).
  - **"passkey는 정확한 origin에 묶인다"** — **rpId(도메인)**에 묶입니다(caller origin의 등록가능 도메인 접미사; rpId `example.com`은 `login.example.com`에서 유효).
  - **"토큰을 평문 SharedPreferences에 저장"** — Keystore 래핑(C40, StrongBox/TEE·user-auth 게이트)에. 평문 prefs/파일/logcat 금지.

## 질문 4 — 입력과 출력은 무엇인가

- **세션**: 인증 → 토큰. access(요청마다)/refresh(교환용).
- **OAuth code+PKCE**: 앱이 `code_verifier` 생성 → `code_challenge`(=base64url(SHA256)) 전송 → 리다이렉트로 code 수신 → 토큰 엔드포인트에 code+`code_verifier` 제시(가로챈 code는 verifier 없이 무용). `state`(CSRF)·`nonce`(ID token 바인딩, **보냈을 때만 검증**).
- **passkey**: RP 챌린지 → 인증기가 사용자 제스처(생체/잠금, C41) 후 서명 → RP는 공개키로 검증.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **토큰 도난 = 사칭**(재인증·MFA 없이 헤더만 재생). refresh token 유출 = 고임팩트.
- **OAuth**: 커스텀 스킴 가로채기 + PKCE 없음 → code 탈취. `state` 없음 = CSRF 로그인 하이재크. **계정을 mutable username에 바인딩 = ATO**(reporch). WebView 사용 = 앱이 자격증명 판독.
- **로그아웃이 서버 세션을 안 죽임** → 캡처된 토큰이 계속 유효.
- **평문 토큰 저장** → 루팅/백업/포렌식 이미지에서 유출.

## 질문 6 — Android/표준 버전에 따라 무엇이 달라졌는가

- **implicit/ROPC 폐기**: 권위 근거는 **RFC 9700(OAuth Security BCP, BCP 240, 2025.1)**·**RFC 8252(BCP 212)**. (OAuth 2.1은 아직 **IETF 초안**.)
- **Credential Manager passkey**: A14/API34 플랫폼(Jetpack `androidx.credentials`·Play services 백포트).
- **EncryptedSharedPreferences**(androidx.security-crypto): 현재 **deprecated** → Keystore 직접.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- OAuth 흐름이 **code+PKCE**인가(implicit 아님), 리다이렉트가 **verified App Link**인가(raw 커스텀 스킴 아님), **시스템 브라우저** vs WebView.
- 토큰이 Keystore인가 평문인가(`/data/data/<pkg>/shared_prefs`, logcat), `state`/`nonce` 사용.
- passkey면 `assetlinks.json`의 **`delegate_permission/common.get_login_creds`** relation(App Link의 `handle_all_urls`와 다름).
- **도구**: 프록시(Burp)로 인가 요청·토큰 교환 관찰, Frida로 토큰 저장.

**주의**: 앱 인증은 아키텍처 무관 → **에뮬레이터+프록시로 OAuth 흐름·토큰 저장 실측 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C02(인증/인가)**: OAuth=인가, OIDC=인증 — 그 구분의 앱 사례.
- **C40/C44(Keystore)**: 토큰 저장.
- **C11/C21/C47(딥링크)**: 리다이렉트 가로채기.
- **C46(TLS)**: bearer 전송 보호.
- **C41(생체)**: passkey 사용자 검증.
- 다음은 그 전송을 지키는 **C46(TLS·NSC·pinning)** 등으로.

## 직접 그릴 수 있는 호출 흐름

```
[ OAuth code+PKCE (네이티브) + passkey ]

  앱 ─code_verifier 생성→ code_challenge=base64url(SHA256(verifier)) ─┐
     시스템 브라우저/Custom Tabs (WebView 금지) ──authorize──▶ IdP    │
  IdP ──redirect(verified App Link, +code, +state)──▶ 앱             │
  앱 ──token endpoint(code + code_verifier)──▶ IdP ──access/refresh/ID token
     (가로챈 code는 verifier 없이 무용 · state로 CSRF 방어)
     계정 바인딩 = 불변 sub+iss (mutable username ✗ = reporch ATO)
     토큰 저장 = Keystore(C40) (평문 prefs ✗)

  passkey: RP ─challenge→ 인증기(생체 UV, C41) ─서명(rpId 바인딩)→ RP(공개키 검증)
           rpId = 도메인(registrable suffix) → 피싱 저항
```

## 오개념 판별 문제 5개

1. "OAuth 2.0 access token이 있으면 그 사용자가 누구인지 증명된 것이다."
2. "OAuth 로그인 후 계정을 IdP가 준 이메일/username으로 매칭하면 된다."
3. "네이티브 앱은 client_secret을 APK에 넣어 confidential client로 만들 수 있다."
4. "커스텀 스킴(myapp://cb) 리다이렉트는 그 앱만 받으니 안전하다."
5. "passkey는 정확한 URL origin에 묶여 서명한다."

<details><summary>판정 기준(펼치기)</summary>

1. access token은 "**무엇을 해도** 되는가"입니다. 신원은 **OIDC ID token**(sub). access를 신원으로 쓰는 게 대표 혼동.
2. **불변 `sub`+`iss`**에 묶어야 합니다. mutable username에 묶으면 계정 탈취(reporch 버그).
3. APK에서 secret이 추출됩니다. 코드 교환은 **PKCE**가 지킵니다.
4. 아무 앱이나 같은 스킴을 등록해 가로챕니다. **verified App Link + PKCE + 시스템 브라우저**.
5. **rpId(도메인)**에 묶입니다(등록가능 도메인 접미사).
</details>

## 서술형 문제 3개

1. OAuth(access token)와 OIDC(ID token)의 역할 차이를 서술하고, 왜 access token을 신원 증명으로 쓰면 안 되는지 설명하세요.
2. 네이티브 앱에서 authorization code + PKCE가 왜 필수이며(client_secret 추출), 커스텀 스킴 가로채기를 어떻게 무력화하는지 서술하세요.
3. 내 reporch 케이스처럼 계정을 mutable username에 바인딩하면 왜 ATO가 되는지, 불변 sub+iss 바인딩과 대비해 서술하세요.

## 소스 탐색 과제

- 한 앱의 OAuth 흐름을 프록시로 떠서 code+PKCE인지·implicit인지, 리다이렉트가 verified App Link인지 커스텀 스킴인지 확인하세요(소유/허가 대상).
- 토큰이 Keystore 래핑인지 평문 prefs/logcat인지 점검하세요.
- passkey를 쓰는 앱이면 `assetlinks.json`의 `get_login_creds` relation을 확인하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 캡처·응답만** 붙입니다.

1. **흐름 실측**: OAuth 요청/토큰 교환을 프록시로(민감값 마스킹).
2. **저장 실측**: 토큰이 Keystore인지 평문인지.
3. **바인딩 서술**: 내 reporch 케이스를 "mutable username 바인딩 → ATO" 틀로(공개 정책 범위).
4. **연결**: 리다이렉트 가로채기를 C11/C47과 엮어.

각 단계는 응답·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

내 reporch OAuth 버그의 교훈이 이 편의 핵심입니다: 계정을 사용자가 바꿀 수 있는 username/email에 묶으면 계정 탈취가 되고, 불변의 `sub`+`iss`에 묶어야 합니다. OAuth 2.0은 "무엇을 해도 되는가"(access token)이고 OIDC의 ID token이 "누구인가"인데, access token을 신원 증명으로 쓰는 게 대표적 혼동이죠. 네이티브 앱은 client_secret을 못 숨기니 authorization code + PKCE가 필수고, 커스텀 스킴 리다이렉트는 아무 앱이나 등록해 가로채니 verified App Link + 시스템 브라우저(WebView 금지)로 막습니다. passkey는 rpId(도메인)에 묶여 피싱 저항이 있고, 토큰은 Keystore에 넣지 평문 prefs에 안 넣습니다. 다음은 그 토큰을 전송에서 지키는 **C46(TLS·Network Security Config·pinning)**으로 이어집니다.
