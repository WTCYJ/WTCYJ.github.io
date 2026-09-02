---
layout: post
title: "Android Security Concept Atlas C42 | 가상 실습 보고서 — Key Attestation과 신뢰의 뿌리, 앱을 믿지 않고 키를 증명하기"
date: 2026-08-29 23:41:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, KeyAttestation, RootOfTrust, KeyDescription, RKP, RemoteKeyProvisioning, IDAttestation, X509, ConceptAtlas, 학습기록]
excerpt: "C40에서 attestation을 요점만 봤다면, 이 글은 그 심화입니다. 원격 서버가 앱도 OS도 믿지 않고, 이 키가 정말 보안 하드웨어 안에 있는지·기기가 잠긴 채 검증 부팅됐는지를 인증서 체인 하나로 확인하는 방법. KeyDescription ASN.1 확장을 어디서 어떻게 읽는지, 왜 리프에 있다고 가정하면 안 되는지, 폐기가 왜 X.509 CRL이 아니라 JSON 상태 목록인지, 그리고 공장 배치 키를 대체하는 RKP의 내부. 마침 2026년 2월부터 P-384 루트로 전환 중이라, 검증기는 두 루트를 다 핀해야 합니다. Concept Atlas의 열세 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | AndroidKeyStore EC 키 생성, attestation challenge, `KeyInfo`, certificate chain 조회 |
| 관측 결과 | EC 키 생성과 attestation 요청이 성공했고 인증서 체인 길이는 3이었다. 이 AVD의 키 보안 수준은 정확히 `SOFTWARE(0)`였다. |
| 검증 한계 | TEE·StrongBox·Weaver는 물리 보안 하드웨어가 없는 AVD에서 증명할 수 없다. SOFTWARE 결과를 하드웨어 보안으로 해석하지 않는다. |

![C42 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C42 — key attestation·root of trust
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 연구 · **선수 개념**: C40(Keystore·attestation 기초), C28(Verified Boot·RootOfTrust)
> **성격**: 공식 문서·공개 소스 기준 재검토. C40의 attestation을 깊이 파고, C28의 RootOfTrust가 도착하는 자리를 확정합니다.

C40에서 저는 attestation을 요점만 봤습니다 — 인증서 체인, `securityLevel`, C28의 `RootOfTrust`가 실린다는 것까지. 이 글은 그 **심화**입니다. **원격 서버가 앱도 OS도 믿지 않고**, 이 키가 정말 TEE/StrongBox 안에 있는지·기기가 잠긴 채 검증 부팅됐는지를 인증서 체인 하나로 확인하는 방법입니다.

한 문장으로: **키의 속성과 부팅 상태를 하드웨어가 서명해 증명하고, 검증은 앱이 아니라 서버가, 핀된 Google 루트에 대해, 오프디바이스로 한다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 자기 보고가 아니라 서명된 증명

- **Key Attestation**: 생성된 키에 대해 X.509 인증서 체인을 발급하고, 그 리프의 커스텀 확장(**OID 1.3.6.1.4.1.11129.2.1.17**)에 키 속성·부팅 상태를 담아 하드웨어가 서명하는 것.
- **KeyDescription**: 그 확장 안의 ASN.1 구조. `attestationVersion`·`securityLevel`·`attestationChallenge`·두 개의 AuthorizationList(software/hardware).
- **RootOfTrust**: hardware 목록 안에 중첩된 C28의 부팅 상태(`verifiedBootState`·`deviceLocked`·`verifiedBootKey`·`verifiedBootHash`).
- **RKP (Remote Key Provisioning)**: 공장 배치 키를 기기별 단수명 인증서로 대체하는 프로비저닝.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**원격 신뢰의 확장**입니다. C40이 "키가 시큐어 하드웨어에 있다"를 로컬에서 다뤘다면, C42는 그것을 **원격 서버에 암호학적으로 증명**합니다. C28의 부팅 상태가 여기로 실려 오고, C48(Play Integrity)와는 **다른 질문**에 답합니다 — attestation은 키의 속성과 부팅 상태를 증명하지, 런타임 앱 무결성을 증명하지 않습니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **발급**: `attestKey`를 시큐어 월드(KeyMint TA, C39)가 자기 서명 키로 수행. keystore2가 인증서 체인을 앱에 전달(`KeyStore.getCertificateChain(alias)`).
- **검증**: **반드시 오프디바이스**, 개발자가 신뢰하는 서버에서. 침해된 기기가 자기 검증을 조작할 수 있으니 온디바이스 검증은 무의미합니다.
- **RKP 경로**: 노멀 월드의 `rkpd` 데몬(Android 14부터 업데이트 가능한 APEX `com.android.rkpd`)이 기기에서 키를 만들어 Google 백엔드로 CSR을 보내고 단수명 인증서를 받아 캐시합니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

검증의 규칙이 곧 이 모듈의 핵심입니다.

- **체인은 핀된 Google 하드웨어 루트에 도달해야 합니다.** 기기가 준 루트나 시스템 신뢰 저장소를 그냥 믿으면, 위조된 체인이 자기 루트로 앵커할 수 있습니다.
- **태그는 `hardwareEnforced`에 있어야 신뢰합니다.** 같은 태그가 `softwareEnforced`에 있으면 (믿을 수 없는) OS의 주장일 뿐입니다. `origin`·`RootOfTrust`·`purpose` 같은 보안 결정은 반드시 hardware 목록에서.
- **확장은 "첫 등장"만 신뢰하고, 리프에 있다고 가정하지 마세요.** Google 문서가 명시적으로 경고합니다: 공격자가 체인을 연장해 가짜 KeyDescription을 덧붙일 수 있으므로 **처음 나타난 것만** 믿어야 하고, RKP에서는 리프가 프로비저닝 정보 확장(OID `.26`)을 담고 KeyDescription은 **바로 다음 인증서**에 있을 수 있습니다.
- **챌린지를 바이트 단위로 대조**(재생 방지)하고, **폐기는 JSON 상태 목록**으로 확인합니다.
- **신뢰하면 안 되는 것들**: "체인이 유효하면 기기가 안전하다"(→ `deviceLocked=true`·`verifiedBootState=Verified`를 **따로** 확인해야; 언락 기기도 유효한 체인으로 `deviceLocked=false`를 정직하게 보고합니다), "온디바이스 검증", "attestation = 런타임 앱 무결성".

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: `setAttestationChallenge(서버 nonce)` + 키 생성.
- **출력**: X.509 **리프**(증명 대상 키의 공개키) + OID `.17` 확장의 **KeyDescription**(DER ASN.1 SEQUENCE, 8필드):

```
KeyDescription ::= SEQUENCE {
  attestationVersion      INTEGER,           -- 스키마/HAL 세대 (마케팅 버전 아님)
  attestationSecurityLevel SecurityLevel,    -- 이 증명이 어디서 서명됐나
  keyMintVersion          INTEGER,
  keyMintSecurityLevel    SecurityLevel,      -- 키가 어디 사나
  attestationChallenge    OCTET_STRING,       -- 서버 nonce 그대로
  uniqueId                OCTET_STRING,        -- 선택적·회전형(안정 식별자 아님)
  softwareEnforced        AuthorizationList,  -- OS 주장
  hardwareEnforced        AuthorizationList   -- 시큐어 하드웨어가 보장
}
```

`SecurityLevel`은 `Software(0)`·`TrustedEnvironment(1)`·`StrongBox(2)`. hardware 목록 안에 `origin`(GENERATED(0)만이 "하드웨어에서 태어나 밖에 안 나옴"을 증명)과 `rootOfTrust`(C28)가 있습니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**공장 배치 키의 문제**가 RKP의 존재 이유입니다. 예전에는 한 모델의 모든 기기에 **공유 배치 서명 키**를 구워 넣었습니다. 그래서 (1) 어느 한 기기에서 그 키가 유출되면 **배치 전체**의 attestation을 위조할 수 있었고(대규모 blast radius), (2) 공유 인증서가 모델 지문이 됐으며(프라이버시), (3) 키가 영구적이라 폐기가 곧 모델 전체 폐기였습니다.

**RKP**가 이 셋을 1:1로 해결합니다: 기기에서 키를 만들고 Google 백엔드가 **단수명 인증서**를 발급해 (1) per-device 폐기, (2) 짧은 수명, (3) per-device라 공유 지문 아님. 내부는 **CBOR/COSE**입니다 — `IRemotelyProvisionedComponent`가 공개키를 `COSE_Mac0`(MacedPublicKeys)으로 싸고, 기기별 Device Key(DICE 앵커)로 **출처 증명**을 서명합니다(이 Device Key는 앱이 보는 attestation 키가 **아닙니다** — 백엔드에 "진짜 하드웨어"임을 증명하는 용도). 백엔드가 돌려주는 것만 X.509 체인입니다.

**검증 실수**가 곧 우회입니다: 리프만 읽기, 온디바이스 검증, 챌린지 미대조(재생), 상태 목록 미확인(폐기된 배치 키 통과), `Software` 수용, `deviceLocked`/`verifiedBootState` 무시. 이건 제 CVE 시리즈의 "검증을 한 겹 빼먹으면 뚫린다"와 같은 결입니다 — 여기서는 PKI 검증 로직이 그 대상입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **attestationVersion 표**(스키마/HAL 세대): 1/2/3/4 = Keymaster 2.0/3.0/4.0/4.1, 100/200/300 = KeyMint 1.0/2.0/3.0(Android 12/13/14), 이후 +100씩. **API 레벨이 아닙니다** — 기기가 API를 건너뛰어도 이 값은 고정될 수 있습니다.
- **`verifiedBootHash`는 attestationVersion 3(Keymaster 4.0)부터** RootOfTrust에 추가됐습니다. v1/v2는 3필드(hash 없음)이니 파서는 버전 분기를 해야 합니다.
- **RKP**: AOSP Android 12 도입, `rkpd` APEX Android 14.
- **P-384 루트 전환(진행 중)**: 새 ECDSA P-384 루트(`CN=Key Attestation CA1`)가 **2026-02-01부터** 체인을 서명하기 시작했고, 2026-03-31까지 신뢰 저장소에 추가, 2026-04-10부터 RKP 기기는 새 루트 전용으로 이동합니다. **검증기는 두 루트(레거시 RSA + 새 P-384)를 다 핀해야** 합니다 — 공장 키 기기는 루트를 못 바꿔 RSA에 계속 걸립니다. 루트는 `android.googleapis.com/attestation/root`(JSON 배열)에 게시됩니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**직접 파싱**
- `KeyGenParameterSpec.setAttestationChallenge(nonce)`로 키 생성 → `KeyStore.getInstance("AndroidKeyStore").getCertificateChain(alias)` → `openssl x509 -text`/`asn1parse`로 OID `1.3.6.1.4.1.11129.2.1.17` 확장을 열어 `securityLevel`·`origin`·`RootOfTrust`를 읽기.
- 리프의 `serialNumber`는 상수 `1`, subject `CN=Android Keystore Key`(식별자 아님) — 판단은 확장 내용으로.
- 폐기: `android.googleapis.com/attestation/status`의 JSON(소문자 hex serial 키, 없으면 유효). X.509 CRL/OCSP가 **아닙니다**.

**주의: 에뮬레이터는 `Software` 레벨**입니다(하드웨어 루트 없음) — 확장은 파싱되지만 하드웨어 보증은 검증되지 않습니다.

**소스·레퍼런스**
- `source.android.com/docs/security/features/keystore/attestation`(스키마), `developer.android.com/privacy-and-security/security-key-attestation`(검증 절차·루트 전환)
- **`github.com/android/keyattestation`**(공식 검증 라이브러리 — 첫 등장 추출·루트 핀·폐기·버전 분기를 처리)
- AOSP `hardware/interfaces/security/{keymint,rkp}`(Tag/SecurityLevel/KeyOrigin/ErrorCode AIDL, `IRemotelyProvisionedComponent`)

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C40(Keystore)**: attestation의 기초가 거기였고, 여기는 그 심화(KeyDescription·RKP·검증 규칙)입니다. `origin=GENERATED`가 C40의 "키가 밖으로 안 나온다"를 원격에 증명합니다.
- **C28(Verified Boot)**: `RootOfTrust`(verifiedBootState/deviceLocked/verifiedBootKey/verifiedBootHash)가 여기 hardware 목록에 실려, 부트로더가 측정한 부팅 상태를 원격 서버가 확인합니다. 그때 예고한 다리가 여기 도착합니다.
- **C39(TEE)**: attestation을 서명하는 주체가 그 시큐어 월드입니다.
- **C48(Play Integrity)**: attestation은 키·부팅 상태를, Play Integrity는 런타임 앱 무결성을 — **다른 질문**입니다. 함께 써야지 서로 대체하면 안 됩니다.
- **ID attestation**: 기기 식별자(IMEI/serial 등)를 증명하는 **별도 opt-in**입니다(`ATTESTATION_ID_*` 태그, 불일치 시 `CANNOT_ATTEST_IDS(-66)`로 실패, `destroyAttestationIds()`는 영구). 기본 attestation엔 식별자가 없고, 프라이버시 대안으로 `getEnrollmentSpecificId()`(ESID)가 있습니다.
- 다음은 **C48(Play Integrity·앱 무결성)** 또는 앱 통제(C44~C50)로 이어집니다.

## 호출 흐름

```
[ 검증기가 attestation 을 소비하는 길 — 전부 오프디바이스 ]

앱: setAttestationChallenge(서버 nonce) → 키 생성 → getCertificateChain
   │ (체인을 서버로 전송)
   ▼
서버(신뢰):
  1) 체인 서명 검증 → 핀된 Google 루트(레거시 RSA + 새 P-384 둘 다)에 도달?
  2) OID .17 확장의 "첫 등장" 파싱 (리프 가정 X; RKP 면 .26 다음 인증서)
  3) attestationChallenge == 내가 낸 nonce? (바이트 일치, 재생 방지)
  4) attestationSecurityLevel ∈ {TrustedEnvironment, StrongBox}? (Software 거부)
  5) hardwareEnforced 안: origin==GENERATED? RootOfTrust.deviceLocked==true?
                          verifiedBootState==Verified?
  6) 상태 목록(JSON) 에서 체인 serial 들 폐기 여부
   ▼
  전부 통과 → "이 키는 잠긴·검증부팅된 기기의 시큐어 하드웨어에 있다"
```

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33` AVD, Android 13/API 33, x86_64)에서 이 모듈의 검증 규칙 중 온디바이스로 관측 가능한 부분을 실제로 확인했다. 상단 검증 블록의 관측 결과와 `evidence-keystore.png` 화면이 근거다.

**1) getCertificateChain은 리프 한 장이 아니라 다중 인증서 체인을 돌려준다 — 리프 가정 금지의 실물 근거.** 검증 블록에서 EC 키 생성과 attestation 요청이 성공했고, 반환된 인증서 체인 길이는 3이었다.

```console
# AndroidKeyStore EC 키 생성 + setAttestationChallenge(server nonce)
# KeyStore.getInstance("AndroidKeyStore").getCertificateChain(alias)
→ 체인 길이 = 3   (리프 한 장이 아니라 세 장)
```

리프 한 장이 아니라 세 장이 온다는 사실 자체가 질문 3·오개념 2("리프를 읽으면 된다")를 프로세스 수준에서 반증한다. KeyDescription 확장(OID `.17`)의 "첫 등장"을 찾으려면 체인 전체를 순회해야 하며, 리프에만 있다고 가정할 근거가 이 환경에서도 성립하지 않는다.

**2) 이 AVD의 보안 수준은 정확히 `SOFTWARE(0)`였다 — Software 거부 규칙이 실제로 걸리는 지점.** `KeyInfo`가 보고한 키 보안 수준은 `SOFTWARE(0)`로, `TrustedEnvironment(1)`·`StrongBox(2)`가 아니었다.

```console
# KeyInfo.getSecurityLevel()
→ SOFTWARE(0)
```

질문 4의 `SecurityLevel` 값(`Software(0)`·`TrustedEnvironment(1)`·`StrongBox(2)`) 중 가장 낮은 값이다. 질문 7이 예고한 "에뮬레이터는 Software 레벨"이 실측으로 확인됐고, 검증 서버라면 이 값을 거부해야 한다(질문 3, 그리고 호출 흐름 4단계의 "Software 거부"). 즉 이 AVD는 attestation의 *형식*은 정직하게 만들어내고, 그 위에서 하드웨어 보증이 어디서 어떻게 채워지는지는 다음 절에서 소스로 확정한다.

## 소스로 확정한 것

이 모듈의 하드웨어 전용 속성은 AOSP 소스와 Google 공식 문서로 확정했고, 이 AVD에서는 그 하드웨어가 없을 때의 소프트웨어 경로를 실측해 둘을 나란히 대조했다. 하드웨어 경로는 소스가, 소프트웨어 폴백 경로는 실측이 각각 근거다.

**1) TEE·StrongBox의 하드웨어 attestation은 시큐어 월드(KeyMint TA)가 서명한다 — AOSP 소스로 확정.** `attestKey`가 시큐어 하드웨어 안에서 배치 키로 인증서를 발급하고, `origin=GENERATED`·`hardwareEnforced` 목록의 보증은 그 하드웨어가 봉인한다. 이 AVD는 물리 시큐어 하드웨어 대신 소프트웨어 KeyMint가 동작하는 환경이라, 위 "실측으로 확인한 것 2)"에서 보안 수준이 정확히 `SOFTWARE(0)`로 실측됐다. 즉 하드웨어가 있으면 `TrustedEnvironment(1)`·`StrongBox(2)`가 서명하고, 없으면 소프트웨어 폴백이 `SOFTWARE(0)`를 정직하게 보고한다 — 스키마와 서명 주체는 소스로, 폴백 동작은 실측으로 확정했다.
근거: [Key Attestation 스키마(source.android.com)](https://source.android.com/docs/security/features/keystore/attestation) · [KeyInfo.getSecurityLevel(developer.android.com)](https://developer.android.com/reference/android/security/keystore/KeyInfo)

**2) RootOfTrust의 부팅 상태는 부트로더가 측정해 하드웨어 목록에 실린다 — AOSP Verified Boot로 확정.** `verifiedBootState`·`deviceLocked`·`verifiedBootKey`·`verifiedBootHash`는 C28의 Verified Boot가 부팅 시 측정한 값을 KeyMint가 `hardwareEnforced` 안 `rootOfTrust`에 봉인하는 구조다. "잠긴·검증부팅된 기기"라는 원격 판정은 이 측정값을 서버가 읽어 확정하며, 그 데이터 경로는 AOSP Verified Boot·keystore attestation 문서로 확정했다.
근거: [Verified Boot(source.android.com)](https://source.android.com/docs/security/features/verifiedboot) · [Key Attestation 스키마(source.android.com)](https://source.android.com/docs/security/features/keystore/attestation)

**3) 핀된 Google 루트 체인 검증과 폐기 상태 목록 대조는 설계상 오프디바이스 서버 절차다 — 공식 문서로 확정.** 레거시 RSA + 새 P-384 두 루트 핀과 `android.googleapis.com/attestation/status` JSON 조회는 검증기가 서버에서 수행하도록 설계돼 있다 — 침해된 기기의 자기 검증을 배제하려는 것이 그 이유다(질문 2·질문 3). 이 시리즈의 온디바이스·비무기화 실습은 앱 프로세스에서 관측 가능한 형식(체인 길이·보안 수준)까지를 실측 범위로 삼고, 서버 측 PKI 검증 로직은 공식 문서로 확정한다.
근거: [Security key attestation(developer.android.com)](https://developer.android.com/privacy-and-security/security-key-attestation) · [android/keyattestation 검증 라이브러리](https://github.com/android/keyattestation)

## 마치며

Key attestation은 "내가 안전한 하드웨어에 키를 넣었다"는 **앱의 말**을, 하드웨어가 서명한 **증명**으로 바꿉니다. 그리고 그 증명은 앱도 OS도 믿지 않는 서버가, 핀된 Google 루트에 대해, 오프디바이스로 검증합니다. C28의 부팅 상태가 이 확장으로 들어와 "잠긴·검증부팅된 기기"까지 원격에 확인되고, RKP가 공장 배치 키의 blast radius를 per-device 단수명으로 줄였습니다.

그러나 범위는 분명합니다: attestation은 **키와 부팅 상태**를 증명하지 **런타임 앱 무결성**은 아닙니다(그건 C48 Play Integrity). 그리고 검증기는 지금(2026년) **두 루트를 다 핀**해야 합니다 — 이건 오늘 당장의 운영 사실입니다. 다음은 그 런타임 무결성을 다루는 **C48(Play Integrity)**, 또는 앱 통제 티어(C44~C50)로 이어집니다.
