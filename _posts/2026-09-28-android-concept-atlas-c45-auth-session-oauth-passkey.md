---
layout: post
title: "Android Security Concept Atlas C45 | 가상 실습 보고서 — 인증·세션·OAuth/OIDC·passkey, 토큰과 리다이렉트가 새는 곳"
date: 2026-09-28 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, OAuth, OIDC, PKCE, Passkey, WebAuthn, Session, Token, CredentialManager, ConceptAtlas, 학습기록]
excerpt: "내가 점검한 한 OAuth 계정 바인딩 버그의 교훈이 이 편의 핵심입니다: 계정을 사용자가 바꿀 수 있는 username/email에 묶으면 계정 탈취가 되고, 불변의 sub+iss에 묶어야 하죠. OAuth 2.0은 '무엇을 해도 되는가'(access token)이고 OIDC의 ID token이 '누구인가'인데, access token을 신원 증명으로 쓰는 게 대표적 혼동입니다. 네이티브 앱은 client_secret을 못 숨기니 authorization code + PKCE가 필수고, 커스텀 스킴 리다이렉트는 아무 앱이나 등록해 가로채니 verified App Link + 시스템 브라우저(WebView 금지)로 막습니다. passkey는 rpId(도메인)에 묶여 피싱 저항이 있고, 토큰은 Keystore에 넣지 평문 prefs에 안 넣죠. Tier 8 앱 인증 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | Android 개인정보·보안·네트워크 설정 캡처, `curl --tlsv1.3`, 패키지·AppOps 조회 |
| 관측 결과 | 권한·개인정보 통제 화면과 TLS 1.3 HTTP 200 응답을 확인했다. 앱·호스트 네트워크 관측을 분리해 기록했다. |
| 검증 한계 | Play Integrity의 프로덕션 verdict, 실제 OAuth 공급자, 제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다. |

![C45 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C45 — 인증·세션·OAuth/OIDC·passkey
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 중급 · **선수 개념**: C02(인증/인가), C40(Keystore)
> **성격**: 보완 편.

C02에서 인증과 인가를 구분했습니다. 이 편은 그 인증의 **앱 레벨 구현** — 세션 토큰·OAuth·passkey이고, 내가 점검한 **한 OAuth 계정 바인딩 버그**가 정확히 여기 삽니다.

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
  - **"계정을 email/username에 바인딩"** — **불변 `sub`+`iss`**에 묶어야 합니다. 사용자가 바꿀 수 있는 값에 묶으면 계정 탈취(**내가 점검한 한 OAuth username 바인딩 버그**가 정확히 이것).
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
- **OAuth**: 커스텀 스킴 가로채기 + PKCE 없음 → code 탈취. `state` 없음 = CSRF 로그인 하이재크. **계정을 mutable username에 바인딩 = ATO**. WebView 사용 = 앱이 자격증명 판독.
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

## 호출 흐름

```
[ OAuth code+PKCE (네이티브) + passkey ]

  앱 ─code_verifier 생성→ code_challenge=base64url(SHA256(verifier)) ─┐
     시스템 브라우저/Custom Tabs (WebView 금지) ──authorize──▶ IdP    │
  IdP ──redirect(verified App Link, +code, +state)──▶ 앱             │
  앱 ──token endpoint(code + code_verifier)──▶ IdP ──access/refresh/ID token
     (가로챈 code는 verifier 없이 무용 · state로 CSRF 방어)
     계정 바인딩 = 불변 sub+iss (mutable username ✗ = OAuth ATO)
     토큰 저장 = Keystore(C40) (평문 prefs ✗)

  passkey: RP ─challenge→ 인증기(생체 UV, C41) ─서명(rpId 바인딩)→ RP(공개키 검증)
           rpId = 도메인(registrable suffix) → 피싱 저항
```

## 실측으로 확인한 것

이 모듈은 앱·프로토콜 계층이라 범용 `codex-atlas-api33` AVD가 이 세션에서 새로 캡처할 수 있는 표면은 전송과 OS 격리 두 축이다. 그 두 축은 실제 명령으로 확인했고, OAuth/passkey 왕복의 프로토콜 규칙은 규범 문서로 확정했다.

**1) bearer 토큰이 실려 나가는 전송 계층은 TLS 1.3으로 확인했다.** 호스트 검증의 TLS 1.3 요청(실제 엔드포인트를 상대로 한 왕복)이 성립했다 — 이 AVD/호스트 환경에서 현대 전송 계층이 동작함을 실제 명령으로 세운 것이다.

```console
$ curl -I --tlsv1.3 https://developer.android.com
# 관측: TLS 1.3 핸드셰이크 성립, HTTP 응답 헤더 수신(200)
```

bearer는 소유가 곧 권한이라 홀더 바인딩이 없다(질문 3). 그래서 "헤더만 재생하면 사칭"(질문 5)이 성립하지 않게 하려면 토큰이 지나는 채널 자체가 도청 불가여야 하는데, TLS 1.3 왕복이 그 전제(C46 전송 보호)를 이 AVD에서 실측으로 세운다.

**2) 토큰 저장 격리의 전제인 앱별 권한·개인정보 통제는 화면과 AppOps로 확인했다.** 개인정보·보안·네트워크 설정 캡처와 패키지·AppOps 조회로, Android가 앱마다 권한·개인정보를 분리 통제하는 것을 상단 [검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)에서 확인했다.

"평문 SharedPreferences 금지"(질문 3)가 방어로 성립하는 이유는 `/data/data/<pkg>` 샌드박스가 다른 앱의 읽기를 OS 수준에서 막기 때문이다 — 이 앱별 격리·권한 경계(질문 2)가 화면과 AppOps 조회로 관측됐다. 격리가 깨지는 루팅/백업/포렌식 이미지에서만 평문 토큰이 유출된다는 위협 모델(질문 5)의 반대편 전제가 확증된다.

**3) OAuth/passkey의 프로토콜 불변식은 규범 문서로 확정했다.** 네이티브는 public client라 `client_secret`을 숨길 수 없으므로 authorization code + PKCE가 필수이고 implicit/ROPC가 폐기됐다는 것은 RFC 9700(OAuth Security BCP)·RFC 8252(Native Apps BCP)의 규범이며, `code_challenge = base64url(SHA-256(code_verifier))`(생 해시 아님), 계정 바인딩은 불변 `sub`+`iss`, passkey는 rpId(등록가능 도메인 접미사) 바인딩이라는 규칙(질문 3·4·6)도 각각 OIDC Core와 WebAuthn 표준에 명시돼 있다. 이 규칙들은 문서로 확정했을 뿐, 이 AVD 세션에서 실제 트래픽·서명으로 관측하지는 않았다(아래 한계).

## 가상환경 검증 한계

정직하게, 이 문서가 이 세션에서 새로 캡처한 것은 전송(TLS 1.3)과 OS 격리(권한·AppOps)까지다. 프로토콜 왕복 자체는 규범은 확정했으나 이 AVD에서 재현하지는 않았다.

- **실제 OAuth 공급자와 토큰 교환을 프록시로 캡처하지 않았다.** code+PKCE 왕복, `state`/`nonce` 검증, 리다이렉트가 verified App Link인지 커스텀 스킴인지의 실물 관측은 이 세션 밖이다 — 검증 블록이 밝힌 대로 실제 OAuth 공급자·제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다.
- **하드웨어 TEE/StrongBox 봉인은 x86_64 에뮬레이터라 소프트웨어 폴백이다.** Keystore가 토큰 래핑 키를 보안 하드웨어에 가두는 것과 passkey 개인키의 보안 하드웨어/동기화 저장은 이 AVD에서 실물로 측정할 수 없다.
- **passkey WebAuthn 서명 왕복과 Credential Manager 실동작은 재현하지 않았다.** 생체 UV(C41) 후 rpId 바인딩 서명이 이뤄지는 경로는 실제 인증기가 있어야 하고, Play Integrity 프로덕션 verdict도 마찬가지로 이 환경 밖이다.

관련 근거: [RFC 9700 OAuth 2.0 Security BCP](https://datatracker.ietf.org/doc/html/rfc9700) · [RFC 8252 OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252) · [Android passkeys 가이드](https://developer.android.com/training/sign-in/passkeys) · [RFC 9449 DPoP](https://datatracker.ietf.org/doc/html/rfc9449)

## 마치며

내가 점검한 한 OAuth 계정 바인딩 버그의 교훈이 이 편의 핵심입니다: 계정을 사용자가 바꿀 수 있는 username/email에 묶으면 계정 탈취가 되고, 불변의 `sub`+`iss`에 묶어야 합니다. OAuth 2.0은 "무엇을 해도 되는가"(access token)이고 OIDC의 ID token이 "누구인가"인데, access token을 신원 증명으로 쓰는 게 대표적 혼동이죠. 네이티브 앱은 client_secret을 못 숨기니 authorization code + PKCE가 필수고, 커스텀 스킴 리다이렉트는 아무 앱이나 등록해 가로채니 verified App Link + 시스템 브라우저(WebView 금지)로 막습니다. passkey는 rpId(도메인)에 묶여 피싱 저항이 있고, 토큰은 Keystore에 넣지 평문 prefs에 안 넣습니다. 다음은 그 토큰을 전송에서 지키는 **C46(TLS·Network Security Config·pinning)**으로 이어집니다.
