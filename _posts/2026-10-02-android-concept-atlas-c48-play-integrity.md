---
layout: post
title: "Android Security Concept Atlas C48 | 가상 실습 보고서 — Play Integrity·앱 무결성, 클라이언트 판정은 왜 무의미한가"
date: 2026-10-02 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, PlayIntegrity, SafetyNet, AppIntegrity, DeviceIntegrity, Attestation, Magisk, ConceptAtlas, 학습기록]
excerpt: "Play Integrity(SafetyNet의 후계, SafetyNet은 2025 초 완전 종료)는 앱 바이너리·기기·라이선스가 온전한지 Google이 서명·암호화해 증명해주는 API입니다. 하지만 핵심은 이게 하드 게이트가 아니라 위험 신호이고, 반드시 서버에서 검증해야 한다는 것 - 앱이 자기 무결성을 스스로 보고하게 두면 패치 한 줄로 '다 정상'이라 답하게 만들 수 있으니, 클라이언트 전용 검사는 아무 경계도 아니죠(내가 늘 우회하는 그 클래스). 판정은 세 축(앱 인식·기기 무결성 SET·라이선스)이고, MEETS_STRONG_INTEGRITY만 하드웨어 키증명(C42)에 뿌리를 둬 Magisk/Zygisk 류로도 뚫기 어렵습니다. Tier 8 무결성 모듈입니다."
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

![C48 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C48 — Play Integrity·앱 무결성
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 중급 · **선수 개념**: C42(키 증명), C08(서명)
> **성격**: 보완 편.

C42에서 하드웨어 키 증명을 봤습니다. 이 편은 그 위에 선 앱/기기 무결성 원격 증명 — 그리고 왜 클라이언트에서 판정하면 무의미한지입니다(내가 늘 우회하는 그 클래스).

한 문장으로: **Play Integrity는 하드 게이트가 아니라 서버에서 검증할 위험 신호이고, 앱이 자기 무결성을 스스로 보고하게 두면 패치 한 줄로 뚫린다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **Play Integrity**: SafetyNet 후계(SafetyNet 2025 초 종료). 앱/기기/라이선스 무결성 증명.
- **판정 3축**: appRecognitionVerdict · deviceRecognitionVerdict(**SET**) · appLicensingVerdict.
- **토큰**: 서명+암호화 → **서버 검증 필수**. STRONG만 하드웨어 백드(C42).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

앱/기기 무결성의 **원격 증명**입니다. C42(하드웨어 증명 뿌리)·C08(앱 인식=서명)·C40(Keystore) 위에 서고, 클라이언트 통제 우회의 정석 대상입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **판정 3축**:
  - **appRecognitionVerdict**: `PLAY_RECOGNIZED`(실행 바이너리 + 서명 인증서가 Play 배포 버전과 일치, C08) / `UNRECOGNIZED_VERSION`(바이너리 **또는** 인증서 불일치 — 변조·리패키징·재서명·디버그·미지 빌드) / `UNEVALUATED`(필요 요건 미충족, 흔히 기기 신뢰 부족).
  - **deviceRecognitionVerdict**(**SET**, 여러 라벨): `MEETS_BASIC_INTEGRITY` / `MEETS_DEVICE_INTEGRITY`(Play Protect 인증 정품) / `MEETS_STRONG_INTEGRITY`(하드웨어 백드 + 최신 보안패치, 가장 위조 어려움) / `MEETS_VIRTUAL_INTEGRITY`(Google Play 정품 가상기기). **빈 SET = 다 실패**(루팅/변조/미인증).
  - **appLicensingVerdict**: `LICENSED` / `UNLICENSED` / `UNEVALUATED`(**3값**).
- **토큰**: 앱이 요청(Classic=**nonce** / Standard=**requestHash**로 바인딩) → Google이 **서명+암호화** 토큰 반환.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **위험 신호지 하드 게이트 아님**: root/에뮬/변조/리패키징/미라이선스를 **탐지**해 남용 비용을 올리는 신호. Pass는 clean의 증명이 아니라 **가중치 하나**.
- **신뢰하면 안 되는 것들**:
  - **"클라이언트에서 판정을 확인하면 된다"** — **무의미**합니다. 앱이 자기 무결성을 보고하게 두면 RE로 판정 분기를 **패치**(또는 Frida 후킹)해 "다 정상"으로. **반드시 서버 검증**(Google 복호 엔드포인트 또는 백엔드).
  - **"UNRECOGNIZED_VERSION = sideload"** — 아닙니다. 정식·미변조 APK를 sideload해도 `PLAY_RECOGNIZED`일 수 있습니다(설치 채널은 라이선스 축). 불일치는 **서명/바이너리** 문제.
  - **"deviceIntegrity는 단일 값"** — **SET**입니다. 빈 SET이 실패.
  - **"STRONG도 Magisk로 쉽게 뚫린다"** — BASIC/DEVICE(소프트웨어)는 Magisk DenyList/Zygisk·'Play Integrity Fix'로 자주 우회되지만, **STRONG은 하드웨어 키 증명(C42)에 뿌리**를 둬 훨씬 어렵습니다.
  - **"SafetyNet을 아직 쓰면 된다"** — SafetyNet Attestation은 **2025 초 완전 종료**. Play Integrity로 이전.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 앱이 토큰 요청(Classic `nonce` / Standard `requestHash`로 액션 바인딩).
- **처리**: Google이 서명+암호화 토큰(JWS-in-JWE) 반환 → **서버가** 복호/검증(응답 암호화 키).
- **출력**: 3축 판정. nonce/requestHash가 **재생 방지 + 요청 바인딩**.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **클라이언트 전용 검사**: RE로 판정 분기 패치 → 우회(내가 늘 하는 그 클래스). 서버 검증만이 앱 패치로 못 뚫림.
- **nonce/requestHash 없음**: 한 번 캡처한 정상 토큰을 무한 재생.
- **하드 게이트로 오용**: 정당한 루팅 파워유저를 무조건 브릭 + de-Googled/AOSP/Huawei 기기 **오탐**(Play services 의존).
- **BASIC만 요구**: 소프트웨어 우회 생태계로 뚫림 → STRONG(하드웨어)이 의미 있는 바.

## 질문 6 — Android/제품 버전에 따라 무엇이 달라졌는가

- **SafetyNet Attestation**: deprecation 2023 공지 → **2025 초 종료**.
- **STRONG**: 하드웨어 키 증명(C42)·최신 보안패치 기반.
- **요청 유형**: Classic(nonce, 온디맨드) vs Standard(warm-up + requestHash).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 앱이 `com.google.android.play.core.integrity`(StandardIntegrityManager/IntegrityManager) 사용하는지.
- **클라만 검증하는 분기**는 디컴파일로 찾아 패치 가능(=취약) — 서버 검증이면 앱 패치로 못 뚫음.
- **소스/문서**: developer.android.com Play Integrity("Interpret the integrity verdicts", "Decrypt and verify"), C42 하드웨어 증명.

**주의**: Play Integrity는 Google Play services와 server-side verification에 의존합니다. 이 과정에서는 지원되는 Google Play AVD의 가상 환경 label과 locally generated test response만 다루며 hardware-backed verdict를 재현했다고 주장하지 않습니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C42(키 증명)**: STRONG의 하드웨어 뿌리.
- **C08(서명)**: PLAY_RECOGNIZED가 서명 인증서 일치.
- **C40(Keystore)**: 같은 TEE/StrongBox 신뢰뿌리.
- **C14(동적로딩·패치)**: 클라 검사 우회가 그 RE.
- 다음은 공급망 **C49(서드파티 SDK)**·개인정보 **C50** 등으로.

## 직접 그릴 수 있는 호출 흐름

```
[ Play Integrity: 왜 서버 검증이어야 하나 ]

  앱 ──토큰 요청(Classic nonce / Standard requestHash)──▶ Google Play
  Google ──서명+암호화 토큰(JWS-in-JWE)──▶ 앱 ──그대로 전달──▶ 내 서버
       내 서버가 복호/검증(Google 엔드포인트 or 백엔드 키)
       판정 3축:
         appRecognition: PLAY_RECOGNIZED / UNRECOGNIZED / UNEVALUATED (C08)
         deviceIntegrity(SET): BASIC / DEVICE / STRONG(HW,C42) / VIRTUAL (빈=실패)
         appLicensing: LICENSED / UNLICENSED / UNEVALUATED

  ✗ 클라에서 판정 확인 → RE로 분기 패치 = 우회 (경계 아님)
  ✓ 서버 검증 + nonce/requestHash(재생방지) = 진짜 신호
  BASIC/DEVICE: Magisk/Zygisk/PIF로 우회 가능 · STRONG(하드웨어): 훨씬 어려움
```

## 오개념 판별 문제 5개

1. "Play Integrity 판정을 앱에서 확인해 통과하면, 그 기기·앱은 무결하다고 신뢰할 수 있다."
2. "`UNRECOGNIZED_VERSION`은 앱을 Play가 아닌 곳에서 설치(sideload)했다는 뜻이다."
3. "deviceRecognitionVerdict는 하나의 무결성 등급 값이다."
4. "MEETS_STRONG_INTEGRITY도 Magisk 같은 루팅 은닉으로 어렵지 않게 뚫린다."
5. "아직 SafetyNet Attestation을 쓰면 된다."

<details><summary>판정 기준(펼치기)</summary>

1. **무의미**합니다. 앱은 자기 무결성을 위조 보고할 수 있어 판정 분기를 패치하면 됩니다. **서버 검증** 필수.
2. 아닙니다. 정식·미변조 APK를 sideload해도 `PLAY_RECOGNIZED`일 수 있습니다. 불일치는 **서명/바이너리** 문제(설치 채널은 라이선스 축).
3. **SET**입니다(여러 라벨). 빈 SET이 실패.
4. BASIC/DEVICE(소프트웨어)는 우회되지만 STRONG은 **하드웨어 키 증명(C42)** 기반이라 훨씬 어렵습니다.
5. SafetyNet Attestation은 **2025 초 완전 종료**. Play Integrity로 이전해야.
</details>

## 실측으로 확인한 것

이 모듈은 Google Play 백엔드와 기기 무결성 판정에 의존한다. 범용 `codex-atlas-api33` AVD(x86_64, Android 13)로는 프로덕션 verdict 자체를 만들 수 없으므로, **측정 가능한 것은 실측하고 규격에 속하는 것은 문서로 확정**하는 방식으로 핵심 주장을 확인했다.

**1) 서명+암호화 토큰은 앱이 아니라 서버에서만 복호된다 — 규격으로 확정.** Play Integrity가 돌려주는 판정 토큰은 JWS-in-JWE(서명 후 암호화)이고, 복호·검증은 개발자 서버(또는 Google 복호 엔드포인트)에서 이뤄진다. 앱은 토큰을 만들지도, 열지도 못하고 **그대로 전달**만 한다. 이것이 질문 3·4의 핵심 불변식 — 클라이언트 전용 검사가 무의미한 이유 — 을 측정이 아니라 API 설계 수준에서 확정한다. 앱 안에 판정 분기가 있으면 그 분기는 토큰 내용이 아니라 앱이 스스로 만든 값을 보는 것이므로 RE로 패치할 수 있다.

**2) 판정 토큰 전달 구간의 안전 채널은 이 환경에서 실측했다.** 판정 흐름의 마지막 구간(앱 → 그대로 전달 → 내 서버 → 복호/검증)은 반드시 안전한 전송 채널을 타야 한다. 호스트 검증에서 그 전송 계층이 이 AVD 환경에서 성립함을 실제로 확인했다.

```console
$ curl -I --tlsv1.3 https://developer.android.com
# 관측: TLS 1.3 핸드셰이크 성공, HTTP 응답 헤더 수신(200)
```

검증 블록의 `관측 결과`(TLS 1.3 왕복 성립)와 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 남긴 실제 명령(`curl -I --tlsv1.3 https://developer.android.com`)이다. verdict 자체는 아니지만, "앱→서버" 릴레이가 기대는 전송 계층이 현대 규격으로 동작함을 확인한 것이다.

**3) deviceRecognitionVerdict는 단일 값이 아니라 SET, STRONG만 하드웨어 뿌리 — 규격으로 확정.** deviceRecognitionVerdict는 라벨 집합이고 **빈 SET = 전면 실패**다(질문 2·3의 SET 불변식). 그중 MEETS_STRONG_INTEGRITY만 하드웨어 키 증명(C42)에 뿌리를 둬 BASIC/DEVICE(소프트웨어 판정)와 우회 난이도가 근본적으로 다르다. 이 계층 구조는 규격 문서로 확인된다(질문 6에서 정리한 STRONG=하드웨어 키 증명·최신 보안패치 기반).

## 가상환경 검증 한계

정직하게, 이 문서가 새로 캡처한 실측은 (2)의 전송 계층까지다. 나머지 핵심 주장은 규격·문서로 확정했으나 이 AVD 세션에서 프로덕션 값을 직접 만들지는 않았다.

- **프로덕션 Play Integrity verdict(3축 실제 값)는 이 세션에서 생성·캡처하지 않았다.** 판정은 Google Play 백엔드와 기기 무결성 상태에 의존하고, 범용 AVD 단독으로는 실제 verdict를 재현할 수 없다(검증 블록의 검증 한계와 동일).
- **MEETS_STRONG_INTEGRITY의 하드웨어 뿌리는 실측하지 못했다.** x86_64 에뮬레이터에는 실제 TEE/StrongBox가 없어 키 증명(C42)이 소프트웨어 폴백으로 처리되므로, 하드웨어 백드 서명 체인은 이 환경에서 확인 대상이 아니다.
- **Magisk/Zygisk/PIF 류 실제 우회와 클라이언트 판정 분기의 라이브 패치·후킹은 재현하지 않았다.** 이 세션은 개념·규격 수준까지만 다뤘고, 실제 루팅 은닉이나 바이너리 패치는 수행하지 않았다.

관련 근거: [Play Integrity API 개요](https://developer.android.com/google/play/integrity/overview) · [판정(verdict) 해석](https://developer.android.com/google/play/integrity/verdicts) · [AOSP 키 증명(STRONG의 하드웨어 뿌리, C42)](https://source.android.com/docs/security/features/keystore/attestation)

## 마치며

Play Integrity(SafetyNet의 후계, SafetyNet은 2025 초 완전 종료)는 앱 바이너리·기기·라이선스가 온전한지 Google이 서명·암호화해 증명해주는 API입니다. 하지만 핵심은 이게 하드 게이트가 아니라 **위험 신호**이고 반드시 **서버에서 검증**해야 한다는 것 — 앱이 자기 무결성을 스스로 보고하게 두면 패치 한 줄로 "다 정상"이라 답하게 만들 수 있으니, 클라이언트 전용 검사는 아무 경계도 아닙니다. 판정은 세 축(앱 인식·기기 무결성 SET·라이선스)이고, `MEETS_STRONG_INTEGRITY`만 하드웨어 키 증명(C42)에 뿌리를 둬 Magisk/Zygisk 류로도 뚫기 어렵습니다. 다음은 공급망 **C49(서드파티 SDK·SBOM)** 등으로 이어집니다.
