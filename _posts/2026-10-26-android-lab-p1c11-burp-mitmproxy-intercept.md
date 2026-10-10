---
layout: post
title: "Burp/mitmproxy 로컬 인터셉션 — 왜 유저 CA로 프록시가 안 되나"
date: 2026-10-26 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Burp, mitmproxy, TLSIntercept, Frida]
excerpt: "인터셉션의 첫 벽은 프록시 IP(에뮬은 10.0.2.2, 물리기기는 호스트 LAN IP)이고, 두 번째 벽은 API 24다 — targetSdk 24+ 앱은 유저 CA를 안 믿어 Burp CA를 유저 인증서로 깔아도 안 잡힌다. 그래서 옛 타깃·NSC user 앵커(리패키징)·루팅 시스템 스토어 CA·Frida unpin 넷 중 하나로 간다."
---

앱↔서버 경계를 관찰하려면 TLS를 복호해야 한다. 그런데 여기엔 두 벽이 있다. 첫째는 프록시 IP(에뮬레이터냐 물리기기냐로 다르다), 둘째는 Android 7(API 24)의 유저 CA 미신뢰다. Burp CA를 유저 인증서로 깔았는데 트래픽이 안 잡힌 적이 있다면 그건 버그가 아니라 설계다. 이 글은 자작/교육용 앱의 트래픽을 프록시로 복호하는 셋업과, 유저 CA가 실패할 때의 네 가지 우회를 정리한 기록이다.

> **한 줄 결론**: targetSdk 24+ 앱은 유저 CA를 안 믿는다. 인터셉션엔 네 길뿐이다 — 옛 타깃 앱, NSC user 앵커(리패키징), 루팅 시스템 스토어 CA, Frida unpin. 그리고 Cronet은 NSC를 아예 안 읽는다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 로컬 프록시(Burp/mitmproxy)로 TLS를 복호하는 셋업과 우회를 다룬다. 선수 개념은 [연구 환경(1장)](/posts/android-lab-p1c01-research-environment/)의 google_apis writable-system, [TLS·NSC·pinning(C46)](/posts/android-concept-atlas-c46-tls-nsc-pinning/)의 API 24 유저 CA 미신뢰, [재서명(7장)](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)의 NSC 수정 시 리패키징이다.

## 핵심 개념 — 프록시와 네 우회

- **프록시 IP**: 에뮬은 `10.0.2.2:8080`(호스트 루프백 별칭). **물리기기는 호스트 LAN IP** + Burp 리스너를 **전 인터페이스/LAN IP에 바인딩**(기본 127.0.0.1은 루프백만). `Source-confirmed`
- **API 24 현실**: targetSdk 24+ 앱은 유저 CA 미신뢰 → Burp CA를 유저 인증서로 깔아도 실패(C46). `Source-confirmed`
- **네 우회**: (a) 타깃<24, (b) NSC에 `<certificates src="user"/>`(base-config에 넣으면 **debuggable 아니어도** 리패키징으로 신뢰; `<debug-overrides>`는 **debuggable 전용**이며 핀도 무시), (c) 루팅/writable-system에 시스템 스토어 CA, (d) Frida SSL-unpin. `Source-confirmed`
- **시스템 스토어 CA**(에뮬): `emulator -writable-system` + `adb root && adb remount`, `<subject_hash_old>.0`(=`openssl x509 -subject_hash_old`)을 `/system/etc/security/cacerts/`에 `chmod 644` 후 재부팅. **A30+는 /system이 루팅이라도 RO** → Magisk 모듈. `Source-confirmed`
- **mitmproxy**: `mitmproxy`(TUI)/`mitmdump`(headless), CA는 `~/.mitmproxy`, 기기가 프록시 상태로 `http://mitm.it` 접속해 설치, `mitmdump -s addon.py`로 자동화. `Source-confirmed`

**신뢰 경계와 위협 모델.** 프록시는 앱과 서버 사이에 끼어 TLS를 복호한다 — **소유/허가 대상만**. 유저 CA 미신뢰는 방어 성공의 신호이자 네 우회의 이유다.

> **[그림 1]** 유저 CA로 자작 앱을 프록시했을 때 핸드셰이크가 실패하는 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱(HTTPS 호출)에서 유저 CA 실패 → 시스템 스토어 CA/Frida unpin 성공을 단계별로 관측한다. 실서비스 인터셉션은 하지 않는다.

## 실습 절차와 관측

### 가설
유저 CA로는 핸드셰이크 실패, 시스템 스토어 CA(writable-system)로는 복호 성공. `Inferred`

### 절차
1. 프록시를 설정하고 Burp/mitmproxy CA를 준비한다.
2. 유저 CA로 자작 앱 실패를 관측한다.
3. 시스템 스토어 CA(에뮬 writable-system)로 성공시킨다.
4. 핀 있는 자작 앱은 Frida unpin(objection `android sslpinning disable`).
5. Burp로 복호 트래픽을 확인한다.

```bash
emulator -avd sec-api34 -writable-system -http-proxy http://127.0.0.1:8080
adb root && adb remount
openssl x509 -inform PEM -subject_hash_old -noout -in burp.pem     # 예: 9a5ba575
adb push burp.pem /system/etc/security/cacerts/9a5ba575.0
adb shell chmod 644 /system/etc/security/cacerts/9a5ba575.0 && adb reboot
```

> **[그림 2]** 시스템 스토어 CA 설치 후 Burp에 복호된 HTTPS 요청이 나타난 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[user CA]   javax.net.ssl.SSLHandshakeException: Trust anchor for certification path not found
[system CA] GET https://api.local/... 200  (복호됨)
```

## Root Cause — 왜 이렇게 되는가

유저 CA 실패는 API 24의 의도된 방어다(C46). 시스템 스토어/Frida는 신뢰 경계 자체를 낮추는 것이라 소유 기기에서만 한다. 그리고 NSC가 정상으로 보여도 안 막히거나 안 잡힐 수 있는데, 그 앱이 **Cronet**을 쓰면 NSC를 무시하기 때문이다.

## 방어와 회귀 검증

- (개발자) pinning은 벽을 높이나 루팅선 우회되니 서버 통제를 병행(C48). 앱이 cleartext로 폴백하지 않는지(C46)를 프록시 다운그레이드로 회귀.
- (연구자) Cronet 여부를 먼저 확인한다.

**흔한 실패와 처리.** A30+ /system RO → Magisk cert 모듈. mitm.it 접속 불가 → 프록시 미적용. 핀 우회 실패 → Cronet/네이티브 TLS면 다른 훅 지점.

## 버전 차이와 한계

- API 24 유저 CA, API 28 cleartext off, A30+ /system 하드닝, A14 업데이트 CA 세트(C46).
- 소유 앱/에뮬. 실서비스 인터셉션 금지.

## 정리

- 프록시 IP: 에뮬 10.0.2.2 / 물리 LAN IP(전 인터페이스 바인딩).
- targetSdk 24+ 유저 CA 미신뢰 → 네 우회.
- NSC가 강해 보여도 Cronet이면 무의미.

**점검 질문** — (1) 물리기기에서 Burp 리스너를 어디에 바인딩하나? (2) 유저 CA가 targetSdk 24+에서 실패하는 이유는? (3) NSC가 잠겨 보여도 안 막힐 수 있는 이유는(Cronet)?

**참고** — [Burp 문서](https://portswigger.net/burp/documentation) · [mitmproxy](https://docs.mitmproxy.org) · [NSC](https://developer.android.com/privacy-and-security/security-config) · [C46 TLS·NSC·pinning](/posts/android-concept-atlas-c46-tls-nsc-pinning/)

*다음 글: [Network Security Config 분석](/posts/android-lab-p1c12-network-security-config/).*
