---
layout: post
title: "Android Security Concept Atlas C46 | 가상 실습 보고서 — TLS·Network Security Config·pinning, 왜 유저 CA로 프록시가 안 되나"
date: 2026-09-30 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, TLS, NetworkSecurityConfig, CertificatePinning, MITM, Frida, Conscrypt, ConceptAtlas, 학습기록]
excerpt: "펜테스트에서 Burp CA를 유저 인증서로 설치했는데 앱 트래픽이 안 잡힌 적 있다면, 그건 버그가 아니라 Android 7(API 24)의 설계입니다 - targetSdk 24+ 앱은 유저가 추가한 CA를 기본으로 안 믿고 시스템 저장소만 신뢰하죠. 그래서 인터셉션엔 네 가지 길밖에 없습니다: 옛 타깃 앱, NSC를 고쳐 유저 CA 신뢰(debuggable 한정), 루팅해 시스템 스토어에 CA 넣기, 또는 Frida로 TLS 검증 후킹. 인증서 피닝은 SPKI 해시로 신뢰를 특정 키에 좁혀 rogue CA·프록시를 막지만, 클라이언트 측이라 루팅 기기에선 Frida/objection으로 우회됩니다 - 벽을 높일 뿐 절대는 아니죠. 그리고 최고 수확은 all-trusting TrustManager, 즉 아무 인증서나 받는 자폭 코드고요. 내 인터셉션 작업과 직결되는 Tier 8 모듈입니다."
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

![C46 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C46 — TLS·Network Security Config·pinning
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 중급 · **선수 개념**: C09(앱), C45(토큰 전송)
> **성격**: 보완 편.

C45에서 bearer 토큰이 TLS 위에서 흘러야 한다 했습니다. 이 편은 그 **전송 보안** — 그리고 왜 펜테스트에서 유저 CA로 프록시가 안 되는지입니다.

한 문장으로: **targetSdk 24+ 앱은 유저 CA를 안 믿어 프록시가 실패하고, 피닝은 신뢰를 특정 키로 좁히지만 클라이언트 측이라 루팅 기기에선 우회된다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **TLS**: 시스템 신뢰 저장소로 서버 인증서 검증(체인 + 호스트명 **SAN**).
- **NSC**(A7/API24, `res/xml`): cleartext·trust-anchors·pin-set을 도메인별 선언.
- **pinning**: SPKI SHA-256 해시로 신뢰를 특정 키에 좁힘. 클라 측 → 우회 가능.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

앱 **전송 보안**(C45 토큰 전송)이자, 내 **인터셉션 작업의 핵심** — 왜 유저 CA로 프록시가 안 되는지의 답입니다. C47(WebView TLS)·C09(앱)와 얽힙니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **TLS 검증**: 앱이 서버 인증서를 **시스템 신뢰 저장소**(`/system/etc/security/cacerts`의 `<hash>.0`)로 체인 검증 + **호스트명(SAN)** 확인. 제공자는 **Conscrypt**. `HttpsURLConnection`/`OkHttp`는 **NSC를 준수**하지만 **Cronet은 NSC를 안 읽음**(검증 경로가 다름).
- **cleartext**: targetSdk **API 28+**부터 평문 HTTP **기본 차단**(`usesCleartextTraffic`/NSC로만 허용).
- **NSC**(A7/API24): `res/xml`, `<base-config>`/`<domain-config>`/`<debug-overrides>`로 cleartext·trust-anchors·pin-set 선언.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **TLS 유효 = 신뢰 CA로 체인 + 호스트명 일치**. 둘 다 필수.
- **신뢰하면 안 되는 것들**:
  - **"유저 CA를 설치하면 앱 프록시가 된다"** — **API 24(A7)부터 targetSdk 24+ 앱은 유저 추가 CA를 기본으로 불신**(시스템만). 그래서 인터셉션은 4가지: ① 옛 타깃(<24) 앱, ② NSC에 `<certificates src="user"/>` 추가(단 `debug-overrides`는 `debuggable`만·리패키징 필요), ③ 루팅해 시스템 스토어에 CA, ④ Frida로 TLS 검증 후킹.
  - **"pin-set은 백업 핀·expiration이 필수"** — 둘 다 **선택적**입니다. 백업 핀은 **강력 권장**(키 순환 시 브릭 방지)이지 필수 아니고, `expiration`도 선택(있으면 만료 후 fail-open, 없으면 무기한 시행). 단일 핀도 파싱·시행됩니다.
  - **"업데이트 CA 세트가 A10부터"** — A10(API29)의 Conscrypt APEX는 **TLS 코드** 업데이트입니다. 독립 업데이트 **루트 CA 세트**는 **A14(API34)**부터.
  - **"호스트명은 CN으로 확인"** — 현대 검증은 **SAN 기반**입니다(CN 폴백 폐기; SAN 있으면 CN 안 봄).
  - **"pinning이면 절대 못 뚫는다"** — **클라이언트 측**이라 루팅/제어 기기에선 우회(Frida OkHttp/TrustManager 후킹, objection `android sslpinning disable`, APK 리패키징). 벽을 높일 뿐.
  - **"all-trusting TrustManager는 무해"** — `checkServerTrusted` 빈 구현/`HostnameVerifier` 무조건 true = **아무 인증서 수락 = 고전 MITM 버그**(감사에서 최우선 grep).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 서버 인증서 체인. **검증**: 신뢰 CA 체인 + 호스트명 SAN (+ 피닝이면 SPKI SHA-256 대조).
- **NSC 준수**: `HttpsURLConnection`/`OkHttp`는 준수, `Cronet`은 별도 경로(NSC 미반영).
- **출력**: 성공 시 암호화 채널, 실패 시 핸드셰이크 거부.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **all-trusting TrustManager/HostnameVerifier**: any cert 수락 → 임의 네트워크 공격자가 MITM. **감사 최고 수확**.
- **cleartext 허용**: 평문 HTTP로 토큰·데이터 유출.
- **피닝 부재**: rogue/오발급 CA로 MITM 가능.
- **피닝 있어도**: 루팅 기기선 우회(내 Frida unpin 작업) — 그래서 서버 측 통제의 대체가 아님.
- **인터셉션 실패(유저 CA 미신뢰)**: 방어 성공의 신호이자, 펜테스터가 4 우회로 가는 이유.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **A7/API24**: NSC 도입 + targetSdk 24+ **유저 CA 미신뢰**(인터셉션 분기점).
- **A9/API28**: cleartext HTTP **기본 차단**.
- **A10/API29**: Conscrypt가 **APEX Mainline**(TLS 코드 업데이트).
- **A14/API34**: 독립 업데이트 **루트 CA 세트**(+ 시스템 스토어 CA 설치가 apex로 복잡해짐).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `apktool`로 `res/xml`의 NSC·manifest의 `android:networkSecurityConfig`·`targetSdkVersion` 확인(cleartext/trust-anchors/pin-set 자세).
- 인터셉션: 유저 CA로 프록시(24+ 실패) → 루팅 시스템 스토어 CA 또는 **Frida SSL-unpin**(`objection android sslpinning disable`) → Burp로 복호 트래픽 확인.
- all-trusting: 디컴파일에서 빈 `checkServerTrusted`·무조건 `HostnameVerifier` grep.

**주의**: 인터셉션은 직접 만든 교육용 앱과 Android Emulator에서만 수행합니다. Network Security Configuration의 debug override와 앱 전용 test CA를 사용하며 system trust store 변조는 과정에서 제외합니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C45(토큰 전송)**: bearer 토큰이 이 TLS 위에서 보호됨.
- **C47(WebView)**: WebView도 TLS·NSC를 따름(그리고 별도 공격면).
- **C08(서명)**: NSC 수정 인터셉션은 리패키징=재서명 필요.
- **C09(앱)**: 앱 UID가 자기 NSC/트래픽.
- 다음은 무결성 증명 **C48(Play Integrity)** 등으로.

## 직접 그릴 수 있는 호출 흐름

```
[ TLS 검증과 인터셉션 분기 ]

  앱(OkHttp/HttpsURLConnection, NSC 준수 · Cronet은 NSC 무시)
    │ 서버 인증서 → 시스템 신뢰 저장소로 체인 + 호스트명(SAN) 검증
    │ (+ pinning이면 SPKI SHA-256 대조)
    ▼
  targetSdk 24+ : 유저 추가 CA 불신 (시스템만)  ← Burp 유저 CA 프록시 실패!
    인터셉션 4길:
      ① 옛 타깃(<24)  ② NSC user 신뢰(debuggable+리패키징)
      ③ 루팅 시스템 스토어 CA  ④ Frida TLS 후킹

  pinning(SPKI): rogue CA/프록시도 거부 (백업핀·expiration은 선택)
      └ 클라 측 → 루팅 기기서 Frida/objection로 우회 (벽↑, 절대 X)

  ⚠ all-trusting TrustManager/HostnameVerifier = any cert 수락 = MITM 버그
```

## 오개념 판별 문제 5개

1. "Burp CA를 유저 인증서로 설치하면 요즘 앱도 프록시로 트래픽을 볼 수 있다."
2. "NSC 인증서 피닝은 백업 핀과 만료일(expiration)을 반드시 넣어야 유효하다."
3. "업데이트 가능한 루트 CA 세트는 Android 10(Conscrypt APEX)부터 제공됐다."
4. "인증서 피닝을 하면 루팅 기기에서도 트래픽을 가로챌 수 없다."
5. "커스텀 TrustManager로 모든 인증서를 받아도 TLS라서 안전하다."

<details><summary>판정 기준(펼치기)</summary>

1. targetSdk **24+ 앱은 유저 CA를 불신**합니다. 4가지 우회(옛 타깃/NSC/루팅 시스템 스토어/Frida)가 필요.
2. 둘 다 **선택적**입니다. 백업 핀은 강력 권장(브릭 방지), expiration은 있으면 만료 후 fail-open.
3. A10은 **TLS 코드**(Conscrypt) 업데이트입니다. 업데이트 **CA 세트**는 **A14**부터.
4. 피닝은 **클라이언트 측**이라 루팅 기기선 Frida/objection로 우회됩니다.
5. all-trusting TrustManager는 **any cert 수락 = MITM 버그**입니다(감사 최우선).
</details>

## 실측으로 확인한 것

이 모듈의 실측 앵커는 상단 검증 블록의 **TLS 1.3 핸드셰이크 성공**이다. `codex-atlas-api33` AVD(Android 13/API 33) 세션에서 다음을 실행해 HTTP 200을 받았다.

```console
$ curl --tlsv1.3 <검증 엔드포인트>
# → HTTP 200 (TLS 1.3 핸드셰이크 성공)
```

**1) 정상 TLS = 신뢰 CA 체인 + 호스트명(SAN) 통과.** `--tlsv1.3` 강제 핸드셰이크가 200으로 끝났다는 것은, 서버 인증서가 시스템 신뢰 저장소로 체인 검증되고 호스트명(SAN)이 일치했음을 뜻한다. 질문 3·4의 불변식 — "TLS 유효 = 신뢰 CA로 체인 + 호스트명 일치, 둘 다 필수" — 이 호스트 검증 경로에서 확증된다. 원시 결과는 검증 블록이 가리키는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존돼 있다.

**2) targetSdk 24+의 유저 CA 기본 불신은 프레임워크 문서로 확정된다.** 이 AVD는 값을 새로 캡처하지 않았지만, NSC의 `<base-config>` 기본 trust-anchors가 API 24부터 `system`만 포함하고 `user`를 제외한다는 것은 플랫폼 문서에 명시된 동작이다. 그래서 Burp 유저 CA 프록시가 24+ 앱에서 실패하는 것은 버그가 아니라 설계이며(질문 3), 인터셉션이 4경로(옛 타깃 / NSC user 신뢰 / 루팅 시스템 스토어 / Frida 후킹)로 갈라지는 분기점이 된다.

**3) all-trusting TrustManager는 정적 grep으로 판별되는 결정적 버그다.** 빈 `checkServerTrusted` 구현과 무조건 `true`를 반환하는 `HostnameVerifier`는 any cert 수락 = MITM이며(질문 5), 실행 없이 디컴파일 소스에서 패턴으로 잡아내는 항목이다. 이 판별 자체는 소스 근거로 성립하고, TLS 기본값(24+/28+)이 지키는 것과 정반대의 실패 모드다.

## 가상환경 검증 한계

정직하게, 이 세션에서 새로 캡처한 것은 위 (1)의 TLS 1.3 결과와 상단 권한·개인정보 화면까지다. 인터셉션·피닝 우회 계열은 근거는 확정했으나 이 x86_64 AVD 세션에서 실행·재현하지 않았다.

- **실제 앱의 NSC·targetSdk 정적 추출은 이 세션에서 수행하지 않았다.** apktool로 `res/xml` NSC와 `targetSdkVersion`을 떠 cleartext/trust-anchors/pin-set 자세를 확인하는 작업은 대상 앱이 없어 이번엔 하지 않았고, 유저 CA 불신은 프레임워크 문서 근거로만 서술했다.
- **유저 CA 프록시 실패 → 우회 → Burp 복호의 라이브 체인은 재현하지 않았다.** 루팅 시스템 스토어 CA 삽입, Frida/objection SSL-unpin, 리패키징 후 재서명은 모두 루팅·실기기·소유 앱을 요구하며, 이 범용 AVD 세션에서는 캡처하지 못했다.
- **하드웨어·아키텍처 의존 속성은 미측정이다.** ARM64 EL/PAC/BTI/MTE는 x86_64라 관측할 수 없고, 하드웨어 TEE·StrongBox 기반 키 증명은 에뮬레이터라 소프트웨어 폴백으로 동작하므로 실기기 검증 대상이다.

관련 근거: [Network Security Configuration](https://developer.android.com/privacy-and-security/security-config) · [X509TrustManager](https://developer.android.com/reference/javax/net/ssl/X509TrustManager) · [Conscrypt 모듈](https://source.android.com/docs/core/ota/modular-system/conscrypt)

## 마치며

펜테스트에서 Burp CA를 유저 인증서로 설치했는데 앱 트래픽이 안 잡힌다면, 그건 버그가 아니라 Android 7(API 24)의 설계입니다 — targetSdk 24+ 앱은 유저가 추가한 CA를 기본으로 안 믿고 시스템 저장소만 신뢰하죠. 그래서 인터셉션엔 네 길밖에 없습니다: 옛 타깃 앱, NSC를 고쳐 유저 CA 신뢰(debuggable 한정), 루팅해 시스템 스토어에 CA 넣기, Frida로 TLS 검증 후킹. 인증서 피닝은 SPKI 해시로 신뢰를 특정 키에 좁혀 rogue CA·프록시를 막지만(백업 핀·expiration은 선택), 클라이언트 측이라 루팅 기기에선 우회됩니다 — 벽을 높일 뿐 절대는 아니죠. 그리고 최고 수확은 all-trusting TrustManager, 아무 인증서나 받는 자폭 코드입니다. 다음은 앱·기기 무결성을 원격 증명하는 **C48(Play Integrity·앱 무결성)** 등으로 이어집니다.
