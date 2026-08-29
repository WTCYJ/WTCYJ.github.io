---
layout: post
title: "Android Security Concept Atlas C40 | 가상 실습 보고서 — Keystore·KeyMint·StrongBox와 키의 보안 수준"
date: 2026-08-27 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Keystore, KeyMint, Keymaster, StrongBox, TEE, KeyAttestation, RKP, HardwareAuthToken, Gatekeeper, keystore2, TitanM, ConceptAtlas, 학습기록]
excerpt: "Android Keystore API, keystore2와 KeyMint의 역할을 구분하고 Software·TrustedEnvironment·StrongBox security level에 따라 key material과 authorization을 어디서 보호하는지 정리합니다."
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

![C40 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C40 — Keystore·KeyMint·StrongBox
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 고급 · **선수 개념**: C05(예외 수준; EL3 너머 시큐어 월드의 키 추출 비대칭), C39(TEE·Trusty — 형제 모듈)
> **성격**: 공식 문서·공개 소스 기준 재검토. Domain 8(하드웨어 보안)의 첫 삽.
> **완료 기준**: 키 생성 요청이 시큐어 월드(TEE/StrongBox)에 도달하는 경로를 추적할 수 있다.

Hardware-backed Keystore는 raw key material을 Android user/kernel space 밖의 secure component에 두도록 설계됩니다. 그러나 Software/Keystore security level의 key에는 같은 추출 저항을 적용할 수 없으므로 실제 level과 authorization을 먼저 확인해야 합니다.

한 문장으로: **Android Keystore key의 보호 위치와 non-exportability는 security level, key type과 authorization에 따라 달라지므로 `KeyInfo`와 attestation으로 실제 보장을 확인해야 합니다.**

## 배경 개념 - 키를 손에 쥐지 않는 저장소

- **AndroidKeyStore**: 앱이 쓰는 JCA(Java 암호화) 프로바이더 이름. 키를 앱에 주지 않고 **핸들(별칭)**만 줍니다.
- **KeyMint (구 Keymaster)**: 시큐어 월드 안에서 실제 키를 만들고 쓰는 HAL. Android 12에 Keymaster에서 KeyMint로 개명·재설계되며 HIDL→AIDL로 바뀌었습니다.
- **keystore2**: 노멀 월드(EL0)의 Rust 데몬. 앱과 KeyMint 사이를 중개하고 **암호화된 블롭만** 저장합니다.
- **키 블롭**: 시큐어 월드의 루트 키로 감싼(디바이스에 묶인) 암호문. 오프디바이스에선 무용지물입니다.
- **Security level**: `SOFTWARE`/`KEYSTORE`, `TRUSTED_ENVIRONMENT`, `STRONGBOX`는 key와 authorization을 어느 경계가 enforce하는지 나타냅니다. 단순 숫자 서열로만 보지 말고 algorithm 지원, performance와 threat model을 함께 확인합니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**하드웨어 백업 키 관리**입니다. C05의 EL3→시큐어 월드 비대칭이 여기서 "키 블롭 모델"로 구체화되고, C28의 attestation `RootOfTrust`가 여기서 키 인증서에 실려 나갑니다. 위로는 앱의 인증·세션·결제 키(C44/C45), 옆으로는 앱 무결성(C48)과 이어지지만, 그것들과 **다른 질문**에 답합니다(질문 5).

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

앱은 시큐어 월드를 **직접 부르지 않습니다.** 스택을 한 층씩 넘습니다.

```
앱 (EL0)  ── JCA "AndroidKeyStore" (KeyStore/KeyGenParameterSpec)
   │ Binder
   ▼
keystore2 데몬 (EL0, Rust, uid=AID_KEYSTORE)   ← 암호화 블롭만 저장, 키는 없음
   │ KeyMint AIDL HAL
   ▼
KeyMint secure implementation(구현별 TEE 배치) ─ 또는 ─▶ StrongBox secure element
   (트러스티드 OS 커널은 S-EL1: Trusty/QSEE/Kinibi)
```

마지막 홉이 C05의 **EL3→시큐어 월드 경계**를 넘습니다. keystore2는 노멀 월드의 **브로커**일 뿐 — 블롭을 저장하고 요청을 전달하지, 키를 쥐거나 연산하지 않습니다. 그래서 keystore2가 뚫려도 키는 안 새어 나갑니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **Key blob model**: hardware-backed KeyMint key는 secure implementation에서 생성하거나 안전하게 import되고 opaque key blob으로 참조됩니다. AndroidKeyStore의 non-exportable private/secret key는 일반적으로 `getEncoded()`가 `null`이지만 public key와 Software level key까지 같은 문장으로 일반화하지 않습니다.
- **Authorization enforcement 분리**: attestation의 authorization list는 security level별 enforcement 위치를 보여줍니다. `hardwareEnforced`라고 해서 구현 취약점까지 배제되는 것은 아니며, 해당 secure component가 침해되지 않았다는 전제가 붙습니다.
- **신뢰하면 안 되는 것들**:
  - **"하드웨어 백업 = 루팅돼도 안전"** — 아닙니다. 추출은 못 해도 **사용 오라클**은 됩니다(질문 5).
  - **`importKey`** — 원본 키가 노멀 월드 RAM에 한 번은 뜹니다(`generateKey`나 `importWrappedKey`가 그것을 피함).
  - **레벨 미고정** — 하드웨어를 못 쓰면 조용히 `SOFTWARE`로 폴백할 수 있습니다.
  - **`softwareEnforced` 목록의 태그** — OS의 주장일 뿐, 커널 침해에 안 견딤.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: `KeyGenParameterSpec`으로 태그를 **요청**(용도·알고리즘·다이제스트·인증 요구·유효기간·attestation 챌린지 등) + 연산 요청(블롭 + 데이터 + 필요 시 HAT).
- **출력**: 암호화 키 블롭 + 핸들, 그리고 연산 결과(서명 등). **키는 절대 출력이 아닙니다.**

키를 넣는 세 방법의 강도 순:

| 방법 | 원본 키가 노멀 월드에? | 비고 |
|------|----------------------|------|
| `generateKey` | **없음**(안에서 태어남) | 최선 |
| `importWrappedKey` (Secure Key Import, API 28/Android 9) | **없음** | 기기 래핑 공개키로 미리 감싼 키(전송키 RSA-OAEP + 페이로드 AES-GCM)를 안에서만 복호 |
| `importKey` | **한 번 뜸** | 보증 약화 |

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

여기가 C05 비대칭의 정밀한 결론입니다.

- **OS/kernel compromise의 범위**: hardware-backed raw key 추출 저항은 유지될 수 있지만, 공격자는 app identity·UI·authorization 흐름을 장악해 key operation을 오용할 수 있습니다. secure component 자체의 결함이나 side channel까지 배제하는 절대 보장은 아닙니다.
- **기밀성 ≠ 사용 통제 (핵심 구분)**: "추출 불가"는 "아무나 못 씀"이 아닙니다. 인증 바인딩이 **안 된** 하드웨어 키는, 침해된 기기에서 적절한 앱 UID/keystore 접근을 가진 자가 **자유로이 사용**합니다. 사용을 막는 건 오직 인증 바인딩입니다.
- **인증 바인딩이 커널에 견디는 이유**: `setUserAuthenticationRequired` 키는 사용 전 사용자 인증을 요구하고, 그 증거인 **HardwareAuthToken(HAT)**은 Gatekeeper(PIN/암호 TA)·생체 TA와 KeyMint TA 사이에서 부팅 시 `ISharedSecret`으로 합의한 **HMAC 키로 서명**됩니다. KeyMint TA가 연산 전 그 MAC을 검증하므로 **검사가 시큐어 월드를 안 떠나고**, 커널은 불투명한 토큰을 전달만 할 뿐 **위조하지 못합니다**. 인증-매-사용 모드는 `begin()`이 준 연산별 챌린지가 HAT에 있어야 해 재생도 막습니다.
- **StrongBox는 별도 security level입니다**: TEE KeyMint와 다른 isolation·tamper-resistance 요구사항을 가지지만, 구체적인 구현을 보지 않고 "메인 SoC 전체 침해에도 무조건 안전"이라고 주장하지 않습니다.
- **잔존 공격 표면**: keystore2 브로커를 통한 **use-oracle/confused-deputy**(승인된 앱 UID 사칭), **보안 레벨 다운그레이드**(레벨을 고정 안 하면 `SOFTWARE`로), SE/TEE의 **사이드채널**. 그리고 **attestation은 키의 속성과 부팅 상태를 증명하지 런타임 앱 무결성은 증명하지 않습니다**(그건 Play Integrity, C48).

여기서 제 Toss 분석과 대조됩니다. 거기서 그 앱은 **스스로** 다단계 패커(Blowfish+SEED)로 키를 굴렸습니다 — 앱 프로세스(EL0) 안에서요. 그 방식은 이 모든 하드웨어 보증이 **전혀 없습니다**: 프로세스 메모리를 덤프하면 키가 나옵니다. Keystore가 대체하려는 게 정확히 그것입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 4.3 | 하드웨어 백업 키 저장 등장(legacy `keymaster0` HAL, **인증목록 없음**) |
| Android 6.0 | **Keymaster 1.0**: 태그/인증목록 모델 + 하드웨어 사용 강제 도입 |
| Android 8.0 (Treble) | Keymaster 3.0 — **첫 HIDL** HAL(0/1/2는 C-struct 레거시) |
| Android 9 | Keymaster 4.0 + **StrongBox**(별도 보안 요소), **Secure Key Import**(API 28) |
| Android 11 | `setUserAuthenticationParameters`(옛 duration API deprecated, API 30) |
| **Android 12** | **KeyMint**(AIDL로 개명·재설계), Rust **keystore2**, `getSecurityLevel()`(API 31), **RKP** AOSP 도입 |
| Android 13/14/15 | KeyMint 2.0/3.0/4.0 |
| Android 14 | RKP 데몬(`rkpd`)이 업데이트 가능한 APEX로 |

주의: "하드웨어 백업"의 시작은 Keymaster 1.0이 **아니라** 4.3입니다 — 1.0의 기여는 **태그/인증목록 모델**입니다. StrongBox 하드웨어는 Google의 **Titan M**(Pixel 3)·**Titan M2**(RISC-V, Pixel 6+) 또는 타 OEM의 별도 SE입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**앱/온디바이스**
- `KeyInfo.getSecurityLevel()`(API 31) → `SECURITY_LEVEL_{SOFTWARE|TRUSTED_ENVIRONMENT|STRONGBOX}`. 옛 `isInsideSecureHardware()`는 TEE와 StrongBox를 못 가려 deprecated.
- `PackageManager.hasSystemFeature(FEATURE_STRONGBOX_KEYSTORE)`, `setIsStrongBoxBacked(true)`(없으면 `StrongBoxUnavailableException`).
- `KeyStore.getCertificateChain(alias)`로 attestation 체인을 뽑아 `openssl asn1parse`/`x509 -text`로 **OID 1.3.6.1.4.1.11129.2.1.17**(KeyDescription)을 파싱 → `attestationSecurityLevel`·`origin`(GENERATED/IMPORTED)·`RootOfTrust`(C28의 `verifiedBootState` 등). **검증은 오프디바이스로**, 체인의 **첫 확장만** 신뢰, 챌린지 nonce 확인, 그리고 폐기는 `android.googleapis.com/attestation/status`의 **JSON 상태 목록**(X.509 CRL 아님)으로.

**주의: 에뮬레이터는 `SOFTWARE`로 나옵니다**(진짜 TEE/StrongBox 없음).

**소스**
- AOSP `hardware/interfaces/security/keymint/aidl`(`SecurityLevel.aidl`: SOFTWARE=0/TRUSTED_ENVIRONMENT=1/STRONGBOX=2/KEYSTORE=100; `Tag.aidl`·`KeyPurpose.aidl`·`HardwareAuthToken.aidl`·`IKeyMintDevice.aidl`), `.../sharedsecret`·`.../secureclock` AIDL, `system/security/keystore2`
- `source.android.com/docs/security/features/keystore`(+`/attestation`), `developer.android.com` key-attestation, 공식 검증기 `github.com/android/keyattestation`

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C05(EL3→시큐어 월드 비대칭)**: 그 비대칭의 실체가 **키 블롭 모델**입니다. 커널을 따도 못 빼내는 이유가 여기 있습니다.
- **C28(Verified Boot)**: 그때 예고한 attestation `RootOfTrust`(verifiedBootState/deviceLocked/verifiedBootKey/verifiedBootHash)가 **여기 key attestation의 하드웨어-강제 목록으로 도착**합니다. 그래서 원격 서버가 "하드웨어 백업 + GREEN 잠금"을 한 번에 확인합니다.
- **C39(TEE·Trusty — 형제 모듈)**: KeyMint TA가 사는 곳이 그 TEE(S-EL0), 트러스티드 OS는 S-EL1입니다.
- **C41(Gatekeeper·생체)**: 인증 바인딩의 SID와 HAT의 출처. 잠금 자격증명을 **제거/비활성/강제리셋**하면 SID가 갈려 인증 바인딩 키가 영구 무효화(`KeyPermanentlyInvalidatedException`)됩니다 — 단, **정상적인 PIN 변경**(옛 자격증명 제시)은 SID를 유지해 키가 **살아남습니다**.
- **C42(attestation 심화)·C48(Play Integrity 대비)**: 여기서는 요점만, 상세는 그쪽에서.
- 다음은 **C41(Gatekeeper·Weaver·생체)** 또는 **C42(key attestation·신뢰의 뿌리)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

두 개를 손으로 그려 보시길 권합니다.

```
[ 키 생성과 사용 — 키는 절대 위로 안 온다 ]

앱: KeyGenParameterSpec(용도·알고리즘·인증요구·챌린지) 요청
   │
   ▼
keystore2 (블롭 저장·전달만)  ──▶  KeyMint TA(S-EL0)/StrongBox
   │                                 ├ 키를 안에서 생성
   │  ◀── 암호화 키 블롭 + 핸들 ─────┘   (원본은 밖으로 안 나옴)
   ▼
[사용] 앱이 핸들로 sign 요청 → keystore2 → KeyMint TA
        블롭을 안에서 풀어 서명 → 결과만 위로 (키는 절대)
```

```
[ 인증 바인딩 키 + attestation 다리 ]

사용자 인증(잠금해제/지문)
   │
   ▼
Gatekeeper/생체 TA ── HAT 발급(HMAC, 부팅시 공유한 비밀)
   │                      keystore2 는 전달만(위조 불가)
   ▼
KeyMint TA: HAT 의 MAC 검증 → (인증-매-사용이면 begin() 챌린지 일치?) → 연산 허용

   그리고 attestKey 는 인증서 체인에:
      키 속성(securityLevel·origin·용도) + RootOfTrust(C28: verifiedBootState·deviceLocked)
      → Google 루트로 체인 → 원격 서버가 "하드웨어 백업 + 잠긴 GREEN" 확인
      (단, 앱이 무결한지는 증명 안 함 — 그건 Play Integrity)
```

## 오개념 판별 문제 5개

각 문장이 왜 틀렸는지 한 줄로 반박해 보세요.

1. "키 블롭을 기기에서 복사해 가면 그 키를 훔친 것이다."
2. "하드웨어 백업 키는 기기가 루팅돼도 안전하다(아무도 못 쓴다)."
3. "StrongBox는 더 강하게 만든 TEE라, TEE 익스플로잇으로 StrongBox 키에 닿을 수 있다."
4. "유효한 key attestation 인증서는 그 앱이 진짜이고 변조되지 않았음을 증명한다."
5. "`AndroidKeyStore`에 요청하면 하드웨어 키를 받는다 / 인증 목록의 태그는 전부 하드웨어가 보장한다."

<details><summary>판정 기준(펼치기)</summary>

1. 블롭은 시큐어 월드 루트 키로 감싼 **디바이스 바인딩 암호문**입니다. 다른 기기·오프디바이스에선 풀 수 없어 무용지물이고, 평문 키는 시큐어 월드 안에만 존재합니다.
2. 추출은 못 하지만, **인증 바인딩이 안 된** 키는 접근 권한을 가진 자가 오라클로 **사용**할 수 있습니다. 기밀성(추출 불가)과 사용 통제는 별개입니다.
3. StrongBox는 별도 CPU/RAM/저장을 가진 **물리적으로 분리된 칩**(다른 보안 도메인)입니다. TEE(S-EL1)나 EL3 침해로 닿지 않습니다.
4. attestation은 **키의 속성**(하드웨어 백업·origin·용도)과 **부팅 상태**(C28의 RootOfTrust)를 증명하지, 요청 시점의 **런타임 앱/OS 무결성**은 아닙니다. 그건 Play Integrity의 몫입니다.
5. 레벨을 고정하지 않으면 하드웨어가 없을 때 조용히 `SOFTWARE`로 폴백합니다(에뮬은 `SOFTWARE`). 그리고 태그는 `hardwareEnforced` 목록에 있어야 시큐어 월드가 보장하고, `softwareEnforced`에 있으면 OS의 주장일 뿐입니다.
</details>

## 서술형 문제 3개

1. C05의 "커널을 완전히 장악해도 Keystore 키는 추출하지 못한다"를 **키 블롭 모델**로 구체적으로 설명하고, 그럼에도 루팅된 기기에서 공격자가 **얻는 것(오라클)**과 **못 얻는 것(원본)**을 구분하세요.
2. "기밀성(추출 불가)"과 "사용 통제"가 왜 다른 것인지, 그리고 인증 바인딩 키의 `HardwareAuthToken`을 왜 커널이 위조하지 못하는지(부팅 시 공유한 HMAC) 서술하세요.
3. C28의 `verifiedBootState`가 이 모듈의 key attestation으로 어떻게 이어져 원격 서버가 "하드웨어 백업 + GREEN 잠금"을 검증하는지, 그리고 attestation이 증명하지 **않는** 것(앱 무결성)은 무엇인지 서술하세요.

## 소스·정적 검증 경로

- `sec-api33` 에뮬에서 `KeyGenParameterSpec`으로 키 하나를 `setAttestationChallenge`와 함께 생성하고, `KeyStore.getCertificateChain(alias)`로 체인을 뽑아 `openssl asn1parse`(또는 `x509 -text`)로 OID `1.3.6.1.4.1.11129.2.1.17` KeyDescription을 파싱하세요. **`securityLevel`이 `SOFTWARE`, `origin`이 `GENERATED`로 나옴**을 확인하고, 왜 에뮬에서 `SOFTWARE`인지(진짜 TEE/StrongBox 없음) 근거와 함께 적으세요.
- Android Keystore 공식 문서와 공개 attestation 예제를 이용해 `TRUSTED_ENVIRONMENT`/`STRONGBOX` 형식을 비교하세요. 이것은 로컬 에뮬레이터의 하드웨어 보증을 증명하는 실험이 아님을 표시합니다.

## 추가 심화 재현 절차

이 모듈을 **가상 환경 실측 글**로 승격하세요. `sec-api33`에서 보고된 security level을 먼저 관측하고, `SOFTWARE`라면 그 범위 안에서 API·비추출성·인증 요구와 attestation 파싱만 검증합니다. TEE/StrongBox 하드웨어 보증은 공식 문서와 공개 인증서 예제로만 설명하고 로컬 관측으로 주장하지 않습니다.

1. **블롭 모델 실측**: 키를 생성하고 `PrivateKey.getEncoded()`가 `null`임을, 그리고 attestation 체인의 `securityLevel=SOFTWARE`·`origin=GENERATED`를 실제 출력으로.
2. **형식 대조**: 공식 문서와 공개 attestation 예제에서 `TRUSTED_ENVIRONMENT`/`STRONGBOX` 및 `RootOfTrust` 필드를 비교하고, 로컬 `SOFTWARE` 결과와 증거 등급을 분리.
3. **사용 통제 실측**: `setUserAuthenticationRequired(true)` 키를 만들어 잠금 해제 없이 사용 시 `UserNotAuthenticatedException`이 나는 것을 캡처.
4. **오라클 대 절도 구분**: 위 실측으로 "블롭은 있어도 원본은 없다 / 인증 바인딩이 사용을 막는다"를 글로 귀속.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 재현 불가·미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

C05의 한 문장 — "커널을 따도 Keystore 키는 못 빼낸다" — 이 이 모듈 전체였습니다. 키는 시큐어 월드에서 태어나 절대 나오지 않고, 앱은 디바이스에 묶인 블롭만 쥡니다. 그 위에 세 신뢰 레벨(SOFTWARE < TEE < StrongBox, StrongBox는 별도 칩이라 TEE 침해도 견딤), 커널이 위조 못 하는 HardwareAuthToken, 그리고 C28의 부팅 상태를 원격까지 서명해 보내는 attestation이 얹힙니다.

그러나 범위는 정확해야 합니다: **하드웨어 백업은 "추출 불가"이지 "사용 불가"가 아닙니다.** 루팅된 기기에서 인증 바인딩 안 된 키는 오라클로 쓰이고, attestation은 키의 속성을 증명하지 앱의 무결성을 증명하지 않습니다. 제 Toss 분석의 앱-자작 키 관리는 이 보증이 전혀 없었고, Keystore는 정확히 그 공백을 메우려는 설계였습니다.

이로써 Atlas Top 5(C05·C37·C28·C23·C40)가 모두 나왔습니다. 다음은 인증의 출처인 **C41(Gatekeeper·Weaver·생체)**, 또는 attestation을 더 깊이 보는 **C42**로 이어집니다. 이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.
