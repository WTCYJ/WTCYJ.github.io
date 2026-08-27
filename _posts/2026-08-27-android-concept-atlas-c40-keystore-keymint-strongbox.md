---
layout: post
title: "Android Security Concept Atlas C40 - Keystore·KeyMint·StrongBox, 커널을 따도 못 빼내는 키"
date: 2026-08-27 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Keystore, KeyMint, Keymaster, StrongBox, TEE, KeyAttestation, RKP, HardwareAuthToken, Gatekeeper, keystore2, TitanM, ConceptAtlas, 학습기록]
excerpt: "C05에서 저는 '커널을 완전히 장악해도 Keystore 개인키는 추출하지 못한다'고 적었습니다. 이 글은 그 비대칭의 실체입니다. 키는 시큐어 월드 안에서 태어나 절대 나오지 않고, 앱은 디바이스에 묶인 암호화 블롭(핸들)만 쥡니다. 그리고 그 위에 세 층의 신뢰(SOFTWARE < TEE < StrongBox), 인증 바인딩 키를 위조 불가능하게 만드는 HardwareAuthToken, 그리고 C28의 부팅 상태를 원격 서버까지 서명해 보내는 key attestation이 얹힙니다. 그런데 '하드웨어 백업'이 '루팅돼도 안전'을 뜻하지는 않습니다 — 추출과 사용은 다른 문제니까요. Concept Atlas의 열 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C40 — Keystore·KeyMint·StrongBox
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 고급 · **선수 개념**: C05(예외 수준; EL3 너머 시큐어 월드의 키 추출 비대칭), C39(TEE·Trusty — 형제 모듈)
> **성격**: 미학습 → 풀 작성. Domain 8(하드웨어 보안)의 첫 삽.
> **완료 기준**: 키 생성 요청이 시큐어 월드(TEE/StrongBox)에 도달하는 경로를 추적할 수 있다.

C05에서 저는 결정적 비대칭 하나를 세웠습니다: 앱 샌드박스와 SELinux는 둘 다 EL1에서 강제되어 커널 탈출 하나로 함께 무너지지만, **Keystore 개인키는 EL3 너머 시큐어 월드에 있어 커널을 완전히 장악해도 추출하지 못한다.** 이 모듈은 그 비대칭의 실체입니다. 그리고 C28의 `verifiedBootState`가 실제로 키에 서명돼 원격 서버까지 나가는 자리이기도 합니다.

한 문장으로: **키는 시큐어 월드 안에서 태어나 절대 나오지 않고, 앱은 디바이스에 묶인 암호화 블롭(핸들)만 쥔다.** 이게 전부의 뿌리입니다. 🔴 미학습 영역이라 처음부터 세웁니다.

## 배경 개념 - 키를 손에 쥐지 않는 저장소

- **AndroidKeyStore**: 앱이 쓰는 JCA(Java 암호화) 프로바이더 이름. 키를 앱에 주지 않고 **핸들(별칭)**만 줍니다.
- **KeyMint (구 Keymaster)**: 시큐어 월드 안에서 실제 키를 만들고 쓰는 HAL. Android 12에 Keymaster에서 KeyMint로 개명·재설계되며 HIDL→AIDL로 바뀌었습니다.
- **keystore2**: 노멀 월드(EL0)의 Rust 데몬. 앱과 KeyMint 사이를 중개하고 **암호화된 블롭만** 저장합니다.
- **키 블롭**: 시큐어 월드의 루트 키로 감싼(디바이스에 묶인) 암호문. 오프디바이스에선 무용지물입니다.
- **보안 레벨 3단**: `SOFTWARE`(OS 안, 하드웨어 없음) < `TRUSTED_ENVIRONMENT`(온-SoC TEE) < `STRONGBOX`(AP와 격리된 전용 보안 프로세서 — Pixel의 Titan M2처럼 별도 칩이거나 Qualcomm SPU처럼 온-SoC 보안 유닛).

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
KeyMint 트러스티드 앱 (시큐어 EL0)  ── 또는 ──▶  StrongBox 보안 요소(별도 칩)
   (트러스티드 OS 커널은 S-EL1: Trusty/QSEE/Kinibi)
```

마지막 홉이 C05의 **EL3→시큐어 월드 경계**를 넘습니다. keystore2는 노멀 월드의 **브로커**일 뿐 — 블롭을 저장하고 요청을 전달하지, 키를 쥐거나 연산하지 않습니다. 그래서 keystore2가 뚫려도 키는 안 새어 나갑니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **키 블롭 모델**: 키는 시큐어 월드 안에서 **생성**되고, Android에는 시큐어 월드 루트 키로 감싼 **암호화 블롭 + 핸들**로만 돌아옵니다. 원본 개인키는 노멀 월드 메모리에 **한 번도** 들어오지 않습니다. 사용할 때도 블롭을 다시 내려보내면 시큐어 월드가 안에서 풀어 서명·복호하고, **결과만** 올라옵니다 — 키는 절대. 그래서 `getEncoded()`는 `null`입니다.
- **세 신뢰 레벨과 태그 분리**: 모든 키의 인증 목록은 **하드웨어-강제** 태그(TEE/SE가 보장, 커널 침해로 못 뚫음)와 **소프트웨어-강제** 태그(OS가 추적만)로 나뉩니다. 어떤 태그가 믿을 만한지는 그것이 **어느 목록에 있느냐**로 정해집니다.
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

- **커널/루트(EL1) 침해가 할 수 있는 것 vs 없는 것**: 접근 권한이 있는 동안 그 키를 **서명/복호 오라클로 쓸 수 있지만**, **원본 키를 추출하지는 못합니다.** 원본은 `TRUSTED_ENVIRONMENT`/`STRONGBOX`를 절대 안 떠나기 때문입니다. 즉 완전한 EL1 장악 = 일시적 **사용**, 영구적 **절도**가 아님.
- **기밀성 ≠ 사용 통제 (핵심 구분)**: "추출 불가"는 "아무나 못 씀"이 아닙니다. 인증 바인딩이 **안 된** 하드웨어 키는, 침해된 기기에서 적절한 앱 UID/keystore 접근을 가진 자가 **자유로이 사용**합니다. 사용을 막는 건 오직 인증 바인딩입니다.
- **인증 바인딩이 커널에 견디는 이유**: `setUserAuthenticationRequired` 키는 사용 전 사용자 인증을 요구하고, 그 증거인 **HardwareAuthToken(HAT)**은 Gatekeeper(PIN/암호 TA)·생체 TA와 KeyMint TA 사이에서 부팅 시 `ISharedSecret`으로 합의한 **HMAC 키로 서명**됩니다. KeyMint TA가 연산 전 그 MAC을 검증하므로 **검사가 시큐어 월드를 안 떠나고**, 커널은 불투명한 토큰을 전달만 할 뿐 **위조하지 못합니다**. 인증-매-사용 모드는 `begin()`이 준 연산별 챌린지가 HAT에 있어야 해 재생도 막습니다.
- **StrongBox는 TEE 침해도 견딥니다**: 별도 칩(별도 CPU/RAM/저장)이라, TEE(S-EL1)나 EL3 모니터, 심지어 메인 SoC 전체가 뚫려도 StrongBox 키는 안 나옵니다.
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

## 소스 탐색 과제

- `sec-api33` 에뮬에서 `KeyGenParameterSpec`으로 키 하나를 `setAttestationChallenge`와 함께 생성하고, `KeyStore.getCertificateChain(alias)`로 체인을 뽑아 `openssl asn1parse`(또는 `x509 -text`)로 OID `1.3.6.1.4.1.11129.2.1.17` KeyDescription을 파싱하세요. **`securityLevel`이 `SOFTWARE`, `origin`이 `GENERATED`로 나옴**을 확인하고, 왜 에뮬에서 `SOFTWARE`인지(진짜 TEE/StrongBox 없음) 근거와 함께 적으세요.
- 실기기(가능하면 Pixel)에서 같은 절차로 `TRUSTED_ENVIRONMENT`/`STRONGBOX`와 `RootOfTrust`의 `verifiedBootState`를 대조하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 환경 특성: `sec-api33` 에뮬은 **`SOFTWARE` 레벨만** 보고합니다(진짜 TEE/StrongBox 없음) → 하드웨어 보증은 실기기 필요(StrongBox=Pixel 3+ Titan). 다만 API·블롭 모델·attestation 파싱은 에뮬에서도 실측 가능합니다. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **블롭 모델 실측**: 키를 생성하고 `PrivateKey.getEncoded()`가 `null`임을, 그리고 attestation 체인의 `securityLevel=SOFTWARE`·`origin=GENERATED`를 실제 출력으로.
2. **레벨 대조**(가능하면): 실기기에서 같은 키로 `TRUSTED_ENVIRONMENT`/`STRONGBOX`와 `RootOfTrust`를 대조.
3. **사용 통제 실측**: `setUserAuthenticationRequired(true)` 키를 만들어 잠금 해제 없이 사용 시 `UserNotAuthenticatedException`이 나는 것을 캡처.
4. **오라클 대 절도 구분**: 위 실측으로 "블롭은 있어도 원본은 없다 / 인증 바인딩이 사용을 막는다"를 글로 귀속.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 재현 불가·미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

C05의 한 문장 — "커널을 따도 Keystore 키는 못 빼낸다" — 이 이 모듈 전체였습니다. 키는 시큐어 월드에서 태어나 절대 나오지 않고, 앱은 디바이스에 묶인 블롭만 쥡니다. 그 위에 세 신뢰 레벨(SOFTWARE < TEE < StrongBox, StrongBox는 별도 칩이라 TEE 침해도 견딤), 커널이 위조 못 하는 HardwareAuthToken, 그리고 C28의 부팅 상태를 원격까지 서명해 보내는 attestation이 얹힙니다.

그러나 범위는 정확해야 합니다: **하드웨어 백업은 "추출 불가"이지 "사용 불가"가 아닙니다.** 루팅된 기기에서 인증 바인딩 안 된 키는 오라클로 쓰이고, attestation은 키의 속성을 증명하지 앱의 무결성을 증명하지 않습니다. 제 Toss 분석의 앱-자작 키 관리는 이 보증이 전혀 없었고, Keystore는 정확히 그 공백을 메우려는 설계였습니다.

이로써 Atlas Top 5(C05·C37·C28·C23·C40)가 모두 나왔습니다. 다음은 인증의 출처인 **C41(Gatekeeper·Weaver·생체)**, 또는 attestation을 더 깊이 보는 **C42**로 이어집니다. 위의 「블로그 초안 작성 과제」를 마치면 이 모듈이 실측 글로 확정됩니다.
