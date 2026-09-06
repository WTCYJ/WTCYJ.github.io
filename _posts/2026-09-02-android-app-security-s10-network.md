---
layout: post
title: "[Android 앱 보안 S10] 네트워크 보안"
date: 2026-09-02 18:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 네트워크, cleartext, NetworkSecurityConfig, TLS, pinning, InsecureShop, 학습기록]
excerpt: "앱이 무엇을 어떻게 전송하는지 봤습니다. InsecureShop은 usesCleartextTraffic=true에 Network Security Config도 없어서, HTTP를 그냥 평문으로 보냅니다. 앱이 로드한 요청을 로컬 인터셉트 서버로 받아, 헤더와 앱 식별 정보까지 그대로 읽히는 걸 확인했습니다. S09의 SSL 무시와 겹치면 HTTPS마저 방어가 되지 못한다는 것도 정리했습니다."
---

> S09에서 WebView가 인증서 오류를 무시하는 걸 봤습니다. 이번엔 그 아래 네트워크 계층 — 앱이 아예 평문으로 보내는지, 무엇으로 그걸 막을 수 있는지를 봅니다.

네트워크 보안의 첫 질문은 단순합니다. 이 앱의 트래픽을, 같은 네트워크에 있는 누군가가 읽을 수 있는가. HTTPS라면 못 읽어야 하고, 평문 HTTP라면 그대로 읽힙니다. InsecureShop은 후자를 허용합니다 — `usesCleartextTraffic=true`이고 Network Security Config도 없습니다. 앱의 요청을 로컬 인터셉트 서버로 받아, 무엇이 평문으로 오가는지 눈으로 확인했습니다.

---

## 실습 목표

- 앱이 평문 HTTP를 보내는지, 그 요청이 그대로 읽히는지 확인한다.
- Network Security Config의 유무와 기본 정책을 확인한다.
- TLS 인증서 검증·hostname 검증·SPKI pinning의 유무를 확인한다.
- 사용자 CA와 시스템 CA 신뢰의 차이를 정리한다.

---

## 윤리적 범위와 허가 조건

피해 앱은 내가 소유한 InsecureShop, 트래픽을 받은 곳은 내 호스트의 로컬 인터셉트 서버(`http://10.0.2.2:8010`)입니다. 실제 외부 도메인·서비스는 쓰지 않았고, 모든 조작은 `aas-api33` 에뮬레이터 안입니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 피해 앱: `com.insecureshop` (S02)
- 로컬 인터셉트 서버: `python`(요청 로깅 + 응답 반환), 호스트 `10.0.2.2:8010`
- 정적 근거: S03 매니페스트, 디컴파일 결과

---

## 위협 모델 — 트래픽을 읽을 수 있나

- 앱이 평문 HTTP를 쓰는가? 그 요청이 그대로 읽히는가?
- Network Security Config가 평문을 막거나 CA·pin을 제한하는가?
- 인증서 검증·pinning이 있는가? 없으면 HTTPS도 가로챌 수 있는가?

---

## 재현 절차

### 1. 정적 — 평문 허용, NSC 없음

S03에서 본 매니페스트에 이미 답이 있습니다.

```xml
<application android:usesCleartextTraffic="true" ...>
```

그리고 `res/xml`에 `network_security_config` 파일이 없고, 매니페스트에 `android:networkSecurityConfig` 참조도 없습니다. 즉 평문을 명시적으로 허용한 채, 그것을 조일 설정을 두지 않았습니다. 앱 소스에는 OkHttp/Retrofit 같은 HTTP 클라이언트도, 인증서 pinning도 없습니다. 네트워크는 주로 WebView와 이미지 로더가 담당합니다.

### 2. 동적 — 평문 요청 가로채기

호스트에 요청을 로깅하는 인터셉트 서버를 띄우고, 앱이 그 주소를 평문으로 로드하게 했습니다(S08의 딥링크 통로 재사용). 서버가 받은 요청은 이랬습니다.

```console
GET /s10.html HTTP/1.1
Host: 10.0.2.2:8010
User-Agent: Mozilla/5.0 (Linux; Android 4.1.1; ...) Mobile Safari/537.36
Accept: text/html,application/xhtml+xml,...
X-Requested-With: com.insecureshop        ← 어느 앱의 트래픽인지까지 노출
```

메서드·경로·헤더가 전부 평문으로 읽힙니다. `X-Requested-With`에는 앱의 package name까지 실려, 이게 InsecureShop의 요청이라는 것도 드러납니다. 요청만 읽히는 게 아니라, 응답도 이 서버가 마음대로 돌려줄 수 있습니다 — 화면에 뜬 페이지가 곧 "인터셉트 서버가 돌려준 내용"입니다. 읽기(도청)와 쓰기(변조)가 둘 다 열린 셈입니다.

---

## 스크린샷

앱이 평문 HTTP로 요청한 결과, 인터셉트 서버가 돌려준 페이지가 그대로 렌더된 화면입니다. 내용은 내가 서버에 심은 것이고, 그게 앱 화면에 떴다는 건 응답 변조가 성립한다는 뜻입니다.

![WebView에 렌더된 인터셉트 서버의 응답 — 갈색 배경에 "PLAINTEXT HTTP", "usesCleartextTraffic=true → 이 요청은 TLS 없이 평문으로 오갔고, 경로 위 누구나 읽고 응답까지 바꿀 수 있다. (이 페이지 자체가 인터셉트 서버가 돌려준 내용)"](/assets/img/android-app-security/S10/01-cleartext.png)

캡처한 평문 요청 원문은 `assets/evidence/android-app-security/S10/`에 남겼습니다.

---

## TLS·pinning·CA 정리

평문이 문제의 절반이라면, 나머지 절반은 HTTPS를 써도 방어가 안 된다는 것입니다.

- 인증서 pinning이 없습니다(SPKI pin도, OkHttp `CertificatePinner`도 없음). 그래서 신뢰 저장소에 있는 아무 CA가 서명한 인증서면 통과합니다.
- 게다가 S09에서 본 대로 WebView는 `onReceivedSslError`로 모든 인증서 오류를 무시합니다. 이러면 pinning은커녕 기본 검증조차 없는 것과 같습니다.
- 사용자 CA와 시스템 CA: targetSdk 24 이상 앱은 기본적으로 사용자가 설치한 CA를 신뢰하지 않습니다(시스템 CA만). InsecureShop은 targetSdk 29라 플랫폼 네트워크 스택에선 이 기본이 적용되지만, WebView의 SSL 무시가 그 방어선을 넘어서 버립니다.

정리하면, 평문은 그냥 읽히고 HTTPS는 검증이 무력화돼 있어, 네트워크 계층 전체가 중간자에게 열려 있습니다.

---

## 관측 결과

- `usesCleartextTraffic=true` + Network Security Config 없음. 평문 HTTP가 허용되고, 인터셉트 서버가 요청·응답을 그대로 읽고 돌려줬다.
- 요청 헤더에 `X-Requested-With: com.insecureshop`까지 평문 노출.
- 인증서 pinning 없음. 그리고 WebView는 SSL 오류를 무시(S09)해 HTTPS 검증도 무력.

---

## 근본 원인과 보안 영향

- 평문 HTTP는 도청과 변조를 동시에 엽니다. 로그인·토큰 같은 값을 이렇게 보내면 그대로 새고, 응답을 바꿔 악성 콘텐츠를 주입할 수도 있습니다.
- Network Security Config가 없으면 정책을 코드 밖에서 강제할 수단이 없습니다. NSC로 평문 금지·CA 제한·pinning을 선언하는 게 표준입니다.
- pinning이 없고 SSL 검증까지 무력화되면, HTTPS로 바꿔도 중간자를 막지 못합니다.

## 수정 방법

- `usesCleartextTraffic="false"`로 두고, `res/xml/network_security_config.xml`에서 평문을 금지한다.

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors><certificates src="system"/></trust-anchors>   <!-- 사용자 CA 불신 -->
    </base-config>
    <!-- 필요한 도메인에 pin-set 추가 -->
</network-security-config>
```

- 민감 트래픽을 다루는 도메인엔 SPKI pinning을 건다(NSC `<pin-set>` 또는 OkHttp `CertificatePinner`).
- WebView의 `onReceivedSslError`를 오버라이드해 `proceed()` 하지 않는다(S09).

수정 후에는 같은 인터셉트 서버로 평문 요청을 받으려 해도 연결 자체가 성립하지 않아야 합니다.

---

## 재검증

앱이 로드한 URL(`Prefs.data = http://10.0.2.2:8010/s10.html`)과 인터셉트 서버가 받은 평문 요청, 그리고 그 서버가 돌려준 내용이 그대로 뜬 화면 — 세 지점이 "이 트래픽이 평문으로 오가며 읽고 바꿀 수 있다"를 함께 가리킵니다.

---

## 참고 자료

- Android Developers — Network Security Configuration(`cleartextTrafficPermitted`, `trust-anchors`, `pin-set`)
- Android Developers — 사용자 CA 신뢰 기본값 변경(API 24)
- OWASP MASVS — Network(MSTG-NETWORK) 요구사항
