---
layout: post
title: "Android Security Concept Atlas C42 - Key Attestation과 신뢰의 뿌리, 앱을 믿지 않고 키를 증명하기"
date: 2026-08-31 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, KeyAttestation, RootOfTrust, KeyDescription, RKP, RemoteKeyProvisioning, IDAttestation, X509, ConceptAtlas, 학습기록]
excerpt: "C40에서 attestation을 요점만 봤다면, 이 글은 그 심화입니다. 원격 서버가 앱도 OS도 믿지 않고, 이 키가 정말 보안 하드웨어 안에 있는지·기기가 잠긴 채 검증 부팅됐는지를 인증서 체인 하나로 확인하는 방법. KeyDescription ASN.1 확장을 어디서 어떻게 읽는지, 왜 리프에 있다고 가정하면 안 되는지, 폐기가 왜 X.509 CRL이 아니라 JSON 상태 목록인지, 그리고 공장 배치 키를 대체하는 RKP의 내부. 마침 2026년 2월부터 P-384 루트로 전환 중이라, 검증기는 두 루트를 다 핀해야 합니다. Concept Atlas의 열세 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C42 — key attestation·root of trust
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 연구 · **선수 개념**: C40(Keystore·attestation 기초), C28(Verified Boot·RootOfTrust)
> **성격**: 미학습 → 풀 작성. C40의 attestation을 깊이 파고, C28의 RootOfTrust가 도착하는 자리를 확정합니다.

C40에서 저는 attestation을 요점만 봤습니다 — 인증서 체인, `securityLevel`, C28의 `RootOfTrust`가 실린다는 것까지. 이 글은 그 **심화**입니다. **원격 서버가 앱도 OS도 믿지 않고**, 이 키가 정말 TEE/StrongBox 안에 있는지·기기가 잠긴 채 검증 부팅됐는지를 인증서 체인 하나로 확인하는 방법입니다.

한 문장으로: **키의 속성과 부팅 상태를 하드웨어가 서명해 증명하고, 검증은 앱이 아니라 서버가, 핀된 Google 루트에 대해, 오프디바이스로 한다.** 🔴 미학습이라 처음부터 세웁니다.

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

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "인증서 체인이 암호학적으로 Google 루트까지 유효하면 기기는 안전하고 잠겨 있다."
2. "attestation 확장은 리프 인증서에 있으니 리프를 읽으면 된다."
3. "폐기는 표준 X.509 CRL/OCSP로 확인하니 일반 PKI 라이브러리면 된다."
4. "key attestation은 그 앱이 변조되지 않고 무결하게 실행 중임을 증명한다."
5. "Google attestation 루트를 한 번 핀하면 끝이다."

<details><summary>판정 기준(펼치기)</summary>

1. 체인 유효는 "키가 하드웨어 백업이고 보고가 진짜"만 증명합니다. `deviceLocked=true`·`verifiedBootState=Verified`·보안 레벨·챌린지·폐기를 **따로** 확인해야 합니다. 언락 기기도 유효한 체인으로 `deviceLocked=false`를 정직하게 보고합니다.
2. 리프에 있다고 가정하면 안 됩니다. **첫 등장**만 신뢰하고(공격자가 체인을 연장해 가짜를 덧붙일 수 있음), RKP면 리프는 OID `.26`, KeyDescription은 다음 인증서일 수 있습니다.
3. Android는 `android.googleapis.com/attestation/status`의 **JSON 상태 목록**(hex serial 키, 없으면 유효)을 씁니다. CRL/OCSP가 아니라, 표준 라이브러리는 자동으로 안 가져옵니다.
4. attestation은 **키의 속성**과 **부팅 상태(키 생성 시점)**를 증명하지 런타임 앱/OS 무결성이 아닙니다. 그건 Play Integrity(C48)입니다.
5. 2026-02-01부터 새 **P-384 루트**가 서명을 시작해, 레거시 RSA와 **둘 다 핀**해야 합니다. 하나만 핀하면 전환 후 정상 기기를 거부합니다.
</details>

## 서술형 문제 3개

1. 공장 배치 키의 세 가지 문제(영구·배치 전체 blast radius·공유 지문)와, RKP가 각각을 어떤 설계 요소로 해결하는지 1:1로 대응해 서술하세요.
2. `hardwareEnforced`와 `softwareEnforced` 목록의 차이가 왜 이 스키마의 핵심 보안 불변식인지, 잘못된 목록에서 태그를 검증하면 무엇이 뚫리는지 서술하세요.
3. C28의 `RootOfTrust`가 이 attestation 확장으로 들어와 원격 서버가 "잠긴·검증부팅된 기기"를 확인하는 경로를 설명하고, 그럼에도 이것이 **증명하지 않는 것**(런타임 앱 무결성)은 무엇인지 서술하세요.

## 소스 탐색 과제

- `sec-api33` 에뮬에서 `setAttestationChallenge`로 키를 만들고 `getCertificateChain`으로 체인을 뽑아, `openssl asn1parse`로 OID `1.3.6.1.4.1.11129.2.1.17` 확장을 열어 `attestationVersion`·`attestationSecurityLevel`·`RootOfTrust`를 읽으세요. **`securityLevel`이 `Software`로 나옴**과, 리프의 `serialNumber=1`·`CN=Android Keystore Key` 상수를 확인하고, 왜 에뮬에서 하드웨어 보증이 검증되지 않는지 적으세요.
- 실기기(가능하면 Pixel)에서 같은 절차로 `TrustedEnvironment`/`StrongBox`와 `RootOfTrust`의 `deviceLocked`/`verifiedBootState`를 대조하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 환경: 에뮬은 `Software` 레벨(하드웨어 루트 없음)이라 파싱은 되지만 하드웨어 보증은 검증 불가 — 실기기 필요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **확장 파싱**: 에뮬에서 체인을 뽑아 OID `.17` 확장을 `openssl`로 열고 `securityLevel=Software`·`origin=GENERATED`·`RootOfTrust` 필드를 실제 출력으로.
2. **레벨 대조**(가능하면): 실기기에서 `TrustedEnvironment`/`StrongBox`와 `deviceLocked=true`/`verifiedBootState=Verified`를 대조.
3. **검증 규칙 실증**: 챌린지 불일치·`softwareEnforced`의 태그·리프 가정이 왜 우회인지를 파싱한 실물로 서술.
4. **루트 전환**: `android.googleapis.com/attestation/root`의 JSON에서 레거시 RSA + 새 P-384 루트가 둘 다 있음을 확인(정적 조회).

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

Key attestation은 "내가 안전한 하드웨어에 키를 넣었다"는 **앱의 말**을, 하드웨어가 서명한 **증명**으로 바꿉니다. 그리고 그 증명은 앱도 OS도 믿지 않는 서버가, 핀된 Google 루트에 대해, 오프디바이스로 검증합니다. C28의 부팅 상태가 이 확장으로 들어와 "잠긴·검증부팅된 기기"까지 원격에 확인되고, RKP가 공장 배치 키의 blast radius를 per-device 단수명으로 줄였습니다.

그러나 범위는 분명합니다: attestation은 **키와 부팅 상태**를 증명하지 **런타임 앱 무결성**은 아닙니다(그건 C48 Play Integrity). 그리고 검증기는 지금(2026년) **두 루트를 다 핀**해야 합니다 — 이건 오늘 당장의 운영 사실입니다. 다음은 그 런타임 무결성을 다루는 **C48(Play Integrity)**, 또는 앱 통제 티어(C44~C50)로 이어집니다.
