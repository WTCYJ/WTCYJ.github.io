---
layout: post
title: "Keystore와 BiometricPrompt 검증 — CryptoObject vs boolean 인증"
date: 2026-10-29 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Keystore, BiometricPrompt, CryptoObject]
excerpt: "생체 인증 검증의 핵심은 'boolean 성공'이 아니라 CryptoObject 바인딩이다. onAuthenticationSucceeded가 그냥 true를 주는 앱은 Frida로 그 콜백을 덮어 우회되지만, CryptoObject로 묶인 Keystore 키(setUserAuthenticationRequired)는 실제 인증 없이는 키를 못 꺼내 우회가 안 된다."
---

로컬 인증 우회를 판정하려면 그 인증이 "boolean 성공"인지 "암호적 결속"인지를 봐야 한다. `onAuthenticationSucceeded`가 그냥 true를 돌려주는 앱은 Frida로 그 콜백을 덮으면 우회되지만, CryptoObject로 Keystore 키를 묶은 앱은 실제 인증 없이는 키가 안 나와 우회가 안 된다. 이 글은 Keystore 키의 비추출성과 생체 인증이 암호적으로 강제되는지를 검증하는 방법을 정리한 기록이다.

> **한 줄 결론**: boolean 인증은 클라이언트 결과라 Frida로 우회되지만, CryptoObject+`setUserAuthenticationRequired` 키는 인증을 키 잠금해제에 결속해 우회 불가다. Keystore 키는 `getEncoded()`가 null이라 원본이 안 나온다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Keystore 비추출성과 CryptoObject 결속을 검증한다. 선수 개념은 [Keystore·KeyMint·StrongBox(C40)](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/)·[Gatekeeper·biometrics(C41)](/posts/android-concept-atlas-c41-gatekeeper-weaver-biometrics/), [Frida(8장)](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)의 콜백 후킹이다.

## 핵심 개념 — 비추출 키와 CryptoObject

- **Keystore 비추출**: `KeyGenParameterSpec`로 `AndroidKeyStore`에 생성한 키는 **비추출** — `KeyStore.getKey`는 불투명 핸들, `getEncoded()`는 **null**. TEE 백드, `setIsStrongBoxBacked(true)`(API 28+, 불가 시 `StrongBoxUnavailableException`). `setUserAuthenticationRequired(true)`로 키 **사용**을 잠금해제/생체에 게이트. 증명은 `setAttestationChallenge`(C42). `Source-confirmed`
- **BiometricPrompt**(androidx.biometric, 구 FingerprintManager 대체): 인증기 `BIOMETRIC_STRONG`(Class 3)/`BIOMETRIC_WEAK`(Class 2)/`DEVICE_CREDENTIAL`. `Source-confirmed`
- **CryptoObject 바인딩**: `BiometricPrompt.authenticate(promptInfo, CryptoObject(cipher))`로 Keystore 키(사용-인증-필요) 사용을 **성공한 STRONG 인증에 암호적으로 결속** → 인증 결과가 boolean이 아니라 키 잠금해제로 강제. `Source-confirmed`
- **함정**: `onAuthenticationSucceeded`가 boolean만 주고 CryptoObject/게이트 키가 없으면 → **Frida로 그 콜백을 강제 호출/덮어 우회**. `Source-confirmed`

**신뢰 경계와 위협 모델.** 루팅/제어 기기에서 boolean 인증은 클라이언트 측이라 우회된다. CryptoObject+게이트 키는 실제 인증 없이는 키가 안 나와 우회 불가(단 키가 보호하는 동작이 서버 검증과 결합돼야 완전).

> **[그림 1]** boolean 인증 앱에서 `onAuthenticationSucceeded`를 Frida로 강제 호출해 우회되는 콘솔 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱 두 버전(boolean 인증 / CryptoObject+게이트 키)을 Frida로 각각 우회 시도해 차이를 관측한다. 소유/교육용 앱만.

## 실습 절차와 관측

### 가설
boolean 버전은 `onAuthenticationSucceeded` 후킹으로 우회되고, CryptoObject 버전은 후킹해도 키(cipher)가 안 나와 복호에 실패한다. `Inferred`

### 절차
1. 자작 앱 정적 분석으로 CryptoObject 사용 여부를 확인한다(4장).
2. boolean 버전: Frida로 콜백을 강제 → 우회 성립.
3. CryptoObject 버전: 콜백을 후킹해도 `cipher.doFinal` 실패를 확인.
4. `getEncoded()`가 null임을 후킹으로 확인.
5. 판정: "boolean = 우회 가능 / CryptoObject = 불가".

```javascript
// boolean 인증 우회 시도 (자작 취약 앱)
Java.perform(function () {
  var cb = Java.use('androidx.biometric.BiometricPrompt$AuthenticationCallback');
  cb.onAuthenticationSucceeded.implementation = function (result) {
    console.log('[forced] onAuthenticationSucceeded');   // boolean이면 우회 성립
    return this.onAuthenticationSucceeded(result);
  };
});
```

> **[그림 2]** CryptoObject 버전에서 콜백을 덮어도 `cipher.doFinal`이 실패(키 미해제)하는 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[boolean]      hooked onAuthenticationSucceeded -> unlocked (bypassed)
[CryptoObject] callback forced, but cipher.doFinal -> IllegalBlockSizeException (키 미해제)
```

## Root Cause — 왜 이렇게 되는가

boolean 인증이 우회되는 것은 클라이언트 결과를 신뢰하기 때문이다(C02 인증≠인가의 로컬판). CryptoObject는 인증을 **키 잠금해제**에 결속해 결과를 위조 불가로 만든다(C40/C41). 즉 인증의 강도는 boolean이 아니라 그 인증이 무엇을 여느냐에 달려 있다.

## 방어와 회귀 검증

- (개발자) 생체는 CryptoObject+사용-인증-필요 키로, Class 3, 그리고 그 키가 보호하는 동작을 서버 인가와 결합한다. "onAuthenticationSucceeded 후킹으로 보호 자원에 접근 불가"를 회귀로.
- (연구자) 우회 판정은 소유/교육용 앱만.

**흔한 실패와 처리.** `StrongBoxUnavailableException` → 폴백(TEE)·기기 미지원. CryptoObject null 요구 → DEVICE_CREDENTIAL/Class 2 조합 제약(API별). 재등록 후 키 무효 → `setInvalidatedByBiometricEnrollment` 기본.

## 버전 차이와 한계

- StrongBox API 28, DEVICE_CREDENTIAL+CryptoObject 제약은 API별 상이 → 버전 표기.
- 에뮬엔 실제 TEE/StrongBox 없음 → 비추출/게이트 로직은 관측되나 하드웨어 증명은 실기기(C40/C42).

## 정리

- boolean 인증은 클라이언트 측이라 우회 가능.
- CryptoObject가 인증을 키 잠금해제에 결속해 우회를 막는다.
- Keystore 키는 `getEncoded()`가 null.

**점검 질문** — (1) boolean 인증이 우회되는 이유는? (2) CryptoObject가 그 우회를 막는 원리는? (3) `getEncoded()`가 null인 의미는?

**참고** — [Keystore](https://developer.android.com/privacy-and-security/keystore) · [Biometric auth](https://developer.android.com/identity/sign-in/biometric-auth) · [C40 Keystore](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/) · [C41 biometrics](/posts/android-concept-atlas-c41-gatekeeper-weaver-biometrics/)

*다음 글: [Activity와 Intent injection 실습](/posts/android-lab-p1c15-activity-intent-injection/).*
