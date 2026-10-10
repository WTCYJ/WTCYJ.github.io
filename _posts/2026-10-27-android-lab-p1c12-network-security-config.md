---
layout: post
title: "Network Security Config 분석 — 앱의 전송 자세를 한눈에 읽기"
date: 2026-10-27 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, NetworkSecurityConfig, Pinning, Cleartext]
excerpt: "NSC 하나로 앱의 전송 자세를 한눈에 읽는다 — cleartext 허용 여부, 신뢰 앵커(system/user), 핀셋(SPKI SHA-256). 함정은 핀셋의 백업 핀·만료일이 둘 다 선택이고 만료되면 fail-open으로 조용히 꺼진다는 것, 그리고 Cronet은 NSC를 아예 안 읽는다는 것이다."
---

11장의 인터셉션은 "어디를 뚫어야 하는지"를 먼저 알아야 효율적이다. 그 지도가 Network Security Config다. NSC 하나만 정적으로 읽어도 앱의 cleartext 허용 여부, 신뢰 앵커, 핀셋을 파악할 수 있다. 이 글은 앱의 NSC를 추출해 전송 보안 자세와 그 허점(만료된 핀·유저 앵커·Cronet)을 판정하는 방법을 정리한 기록이다.

> **한 줄 결론**: NSC의 `cleartextTrafficPermitted`·`trust-anchors`·`pin-set`을 읽는다. 핀셋의 백업 핀·`expiration`은 둘 다 선택이고 만료되면 fail-open으로 핀이 꺼진다. 그리고 Cronet은 NSC를 안 읽으니 판정 전에 앱의 네트워크 스택을 확인해야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 앱의 NSC를 정적으로 판독한다. 선수 개념은 [APK triage(3장)](/posts/android-lab-p1c03-apk-triage/)·[apktool(5장)](/posts/android-lab-p1c05-apktool-smali/)의 NSC 추출, [TLS·NSC·pinning(C46)](/posts/android-concept-atlas-c46-tls-nsc-pinning/)이다. NSC 분석은 [인터셉션(11장)](/posts/android-lab-p1c11-burp-mitmproxy-intercept/)의 지도가 된다.

## 핵심 개념 — NSC 필드

`res/xml`의 파일(매니페스트 `android:networkSecurityConfig` 참조)에서 다음을 읽는다:

| 필드 | 의미 |
|--|--|
| `<base-config>`/`<domain-config includeSubdomains>`의 `cleartextTrafficPermitted` | 평문 HTTP 허용(API 28+ 기본 false) |
| `<trust-anchors><certificates src="system\|user"/>` | 신뢰 CA 세트(유저 앵커면 유저 CA 인터셉션 가능) |
| `<pin-set expiration="YYYY-MM-DD"?>` + `<pin digest="SHA-256">base64</pin>` | **SPKI** 해시 핀 |
| `<debug-overrides>` | `android:debuggable`에서만 적용, 핀도 무시 |

핵심 함정: **핀셋의 백업 핀·`expiration`은 둘 다 선택**이고, **만료되면 fail-open**(핀이 조용히 비활성)이다. `Source-confirmed`

**신뢰 경계와 위협 모델.** NSC는 앱의 전송 신뢰 정책이다. cleartext 허용·유저 앵커·만료된 핀·`debug-overrides`가 인터셉션 표면이 된다. Cronet 사용 시 NSC는 무의미하다.

> **[그림 1]** apktool로 추출한 `network_security_config.xml`에서 cleartext/trust-anchors/pin-set이 보이는 부분 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱의 NSC를 여러 형태(cleartext true/false, system/user, 핀셋 유/무/만료)로 만들어 판정 스크립트로 대조한다.

## 실습 절차와 관측

### 가설
cleartext=true·유저 앵커·만료 핀셋 세 형태가 각각 "약함"으로 플래그되고, system-only·유효 핀셋은 "강함". `Inferred`

### 절차
1. `apktool d`로 NSC를 추출한다.
2. cleartext/trust-anchors/pin-set을 파싱한다.
3. 핀셋 만료일 vs 오늘을 비교한다(fail-open 여부).
4. 앱이 Cronet/OkHttp/HttpURLConnection 중 무엇인지 확인한다(NSC 유효성).
5. 11장 인터셉션 계획에 반영한다.

```bash
apktool d app.apk -o work
cat work/res/xml/network_security_config.xml
# expiration 파싱: 오늘 이후면 시행, 이전이면 fail-open
```

> **[그림 2]** 만료된 pin-set(`expiration` 지남)이 fail-open으로 핀이 비활성인 예 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
cleartextTrafficPermitted=false
trust-anchors: system
pin-set expiration=2025-01-01 (EXPIRED → fail-open, 핀 비활성)
```

## Root Cause — 왜 이렇게 되는가

핀셋 fail-open은 **가용성 보호**(만료 설정이 앱을 브릭하지 않도록)라 보안적으론 함정이다. 백업 핀이 선택인 것은 HPKP의 필수와 대조된다(C46). 그리고 NSC가 강해도 무의미할 수 있는 것은 Cronet이 NSC를 우회하기 때문이다.

## 방어와 회귀 검증

- (개발자) cleartext 차단·system 앵커·유효한 핀셋(백업 포함)·debug-overrides는 디버그만. CI에서 "cleartext 불가 + 유저 앵커 없음 + 핀셋 미만료"를 NSC 파싱으로 회귀.
- (연구자) Cronet 여부를 확인한 뒤 판정한다.

**흔한 실패와 처리.** NSC 없음 → 기본 정책(system-only, cleartext는 targetSdk 따름). 핀이 안 먹는 듯 → 만료 or Cronet.

## 버전 차이와 한계

- API 24 NSC 도입·유저 CA 미신뢰, API 28 cleartext off(C46).
- 정적 판독. 실제 핀 시행은 런타임(11장)으로 확인.

## 정리

- `cleartextTrafficPermitted`·`trust-anchors`·`pin-set`이 세 판정 축.
- 백업 핀·만료는 선택, 만료 핀은 fail-open.
- Cronet이면 NSC 판정이 무의미.

**점검 질문** — (1) 핀셋 `expiration`이 지나면? (2) `<certificates src="user"/>`가 base-config에 있으면 인터셉션에 무슨 의미? (3) NSC가 강해 보여도 무의미할 수 있는 앱은?

**참고** — [NSC](https://developer.android.com/privacy-and-security/security-config) · [C46 TLS·NSC·pinning](/posts/android-concept-atlas-c46-tls-nsc-pinning/)

*다음 글: [저장소·log·clipboard·backup 점검](/posts/android-lab-p1c13-storage-log-clipboard-backup/).*
