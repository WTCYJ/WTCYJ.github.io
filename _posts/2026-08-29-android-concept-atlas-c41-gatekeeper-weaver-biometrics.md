---
layout: post
title: "Android Security Concept Atlas C41 | 가상 실습 보고서 — Gatekeeper·Weaver·생체, 누가 잠금을 여는가"
date: 2026-08-29 23:40:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Gatekeeper, Weaver, Biometrics, BiometricPrompt, HardwareAuthToken, SyntheticPassword, SecureUserID, Throttling, TitanM, ConceptAtlas, 학습기록]
excerpt: "Gatekeeper와 Weaver의 LSKF 검증·rate limiting 역할, 생체 인증 등급, HardwareAuthToken과 Keystore authorization의 연결을 구현 전제와 함께 구분합니다."
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

![C41 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C41 — Gatekeeper·Weaver·biometrics
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 고급 · **선수 개념**: C39(TEE·시큐어 월드), C40(Keystore·HAT·SID)
> **성격**: 공식 문서·공개 소스 기준 재검토. 하드웨어 보안 삼부작(C39·C40·C41)의 마지막.
> **완료 기준**: 사용자 인증이 auth-bound 키의 HAT·SID로 이어지는 경로와, throttle이 재부팅·시계 조작으로 풀리지 않는 이유를 설명할 수 있다.

C39는 시큐어 월드가 **어디**인지였고, C40은 그 안의 키가 **무엇**을 지키는지였습니다. C41은 그 키의 잠금을 **누가 여는가**입니다. C40에서 인증 바인딩 키가 요구하던 그 HardwareAuthToken(HAT)과 Secure User ID(SID)가 **어디서 오는지** — 그 출처가 이 모듈입니다.

한 문장으로: **Gatekeeper/Weaver와 biometric secure component가 발급한 HAT을 KeyMint가 검증함으로써 authentication-bound key 사용을 gate하며, 보장 수준은 각 HAL과 secure environment 구현에 달려 있습니다.**

## 배경 개념 - 잠금 지식과 생체를 증거로 바꾸기

- **LSKF (Lockscreen Knowledge Factor)**: PIN·패턴·암호. Gatekeeper가 검증합니다.
- **Gatekeeper**: LSKF를 검증하는 TEE 트러스티드 앱(S-EL0, C39). enroll→패스워드 핸들, verify→HAT.
- **Secure User ID (SID)**: 자격증명에 묶이는 무작위 64비트 값. auth-bound 키가 여기 묶입니다(C40).
- **HardwareAuthToken (HAT)**: 인증 성공의 증거. 시큐어 월드에서 공유한 HMAC 키로 서명돼 KeyMint가 검증합니다.
- **Weaver**: LSKF 검증과 rate limiting에 사용하는 slot 기반 HAL입니다. dedicated SE뿐 아니라 TEE에도 구현될 수 있습니다.
- **Synthetic Password (SP)**: 자격증명이 **여는** 고엔트로피 비밀. 자격증명이 아니라 SP가 키에 묶입니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**사용자 인증**입니다. 하드웨어 보안 삼부작의 마지막이고 — C39(TEE=어디서 도는가), C40(Keystore=무엇을 지키는가), **C41(누가 잠금을 여는가)** — C40의 auth-bound 키가 요구하던 HAT·SID의 출처입니다. 아래로 C05의 시큐어 월드에 서고, 옆으로 C43(FBE)의 디스크 키 파생과 이어집니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **Gatekeeper·생체 매처**: TEE의 트러스티드 앱(S-EL0, C39). 자격증명 비교와 생체 매칭이 **시큐어 월드 안**에서 일어납니다.
- **노멀 월드(EL0/EL1)**: `gatekeeperd`/HAL, `system_server`의 `GateKeeperService`, `LockSettingsService`는 **중개만** 합니다 — 검증을 하지 않고 결과·타임아웃을 전달할 뿐.
- **Weaver**: 별도 SE(칩) 위의 서비스. TEE가 아닙니다.

흐름: LSKF/생체 → TEE 안에서 매칭 → 성공 시 HAT 발급. 노멀 월드는 그 HAT을 KeyMint로 나를 뿐입니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **Gatekeeper는 자격증명을 저장하지 않습니다.** enroll은 **패스워드 핸들**(자격증명 해시 + SID + 장치 고유 대칭 HMAC 키로 서명)만 만듭니다. OS는 이 서명된 핸들만 저장하고, 자격증명 자체는 어디에도 남지 않습니다.
- **SID는 자격증명에 묶입니다.** enroll이 **현재 유효한 핸들과 함께** 불리면(정상 변경) SID가 유지되고, 유효한 핸들 없이 불리면(제거/비활성/강제리셋) 새 SID가 생겨 옛 SID에 묶인 키가 전부 무효화됩니다. 이게 C40에서 본 무효화 규칙의 **근원**입니다.
- **두 개의 서로 다른 HMAC 키**: 핸들은 Gatekeeper 자신의 키로, HAT은 부팅 시 `ISharedSecret`으로 KeyMint와 **공유한** 키로 서명됩니다(C40). 그래서 KeyMint가 HAT을 검증할 수 있고, 노멀 월드는 위조하지 못합니다.
- **신뢰하면 안 되는 것들**:
  - **"throttle이 4자리 PIN을 암호학적으로 강하게 만든다"** — 엔트로피를 안 늘립니다. 추측 **속도**만 제한합니다.
  - **"재부팅하거나 시계를 바꾸면 throttle이 풀린다"** — 카운터는 RPMB에, 시간은 보안 단조 시계에(질문 5).
  - **"잠금을 여는 어떤 생체든 Keystore 키를 연다"** — Class 3(Strong)만.
  - **"루팅되면 인증을 위조해 키를 연다"** — HAT의 HMAC 키는 시큐어 월드에 있습니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: LSKF(PIN·패턴·암호) 또는 생체 샘플.
- **출력**: `enroll`은 **패스워드 핸들**(SID 내장), `verify`는 성공 시 **HAT**. HAT 필드 = `challenge`·`userId`(=SID)·`authenticatorId`·`authenticatorType`·`timestamp`·`mac`.

한 가지 정밀함: HAT의 `authenticatorType`은 **PASSWORD**(지식 요소) 또는 **FINGERPRINT**(생체)입니다. enum에 "GATEKEEPER"나 "BIOMETRIC" 값은 **없고**, 얼굴 인식조차 성공 시 `FINGERPRINT` 비트로 보고됩니다(프레임워크가 `AUTH_BIOMETRIC_STRONG`→`FINGERPRINT`, `AUTH_DEVICE_CREDENTIAL`→`PASSWORD`로 매핑). HAL은 `IGatekeeper`(enroll/verify)와 `IWeaver`(write/read).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**throttle이 없으면 4~6자리 PIN은 오프라인 브루트포스로 자명하게 뚫립니다.** 그래서:

- **in-TEE throttle**: 실패 시 verify가 시큐어 월드 안에서 백오프를 강제하고 **타임아웃(ms)**을 돌려주면 OS가 그동안 못 부릅니다. 카운터는 **검증 전에 먼저 기록**되고(중간에 전원을 끊어도 실패가 이미 남음), 성공 시에만 지워집니다. 시간은 **"서스펜드 중에도 도는" 보안 단조 시계**로 재므로 노멀 월드 시계 조작이 안 먹고, 카운터는 **RPMB**에 남아 재부팅으로 안 풀립니다.
- **그러나 TEE만큼만 강합니다**: throttle 로직과 HMAC 키가 Gatekeeper TA 안에 있어, **시큐어 월드가 침해되면** 무제한 추측이 가능합니다. 이것이 **Weaver**의 존재 이유입니다 — throttle을 **별도 SE의 펌웨어**로 옮겨, TEE나 OEM 펌웨어를 뚫어도 재시도 제한을 우회하지 못하게(**insider 공격 저항**) 만듭니다. Weaver `read(slot, key)`는 키가 맞을 때만 값을 주고 틀리면 throttle을 돌려줍니다. 단 Weaver는 **SE가 있어야** 하고(Pixel의 Titan M/M2), 없는 기기는 Gatekeeper의 TEE throttle로 대체합니다.
- **HAT은 위조 불가**: HMAC 키가 시큐어 월드에 있어, 커널을 장악해도 인증을 **위조**해 auth-bound 키를 열 수 없습니다.
- **생체 우회 = 스푸핑(SAR)이지 암호 깨짐이 아닙니다**: 그래서 CDD가 센서를 SAR로 등급 매기고, **Class 3만** Keystore 키를 엽니다.
- **실제 공격 표면**: (a) **authenticator TA의 파서 버그** — 시큐어 EL0의 파서 결함이 브루트포스보다 값집니다(C39·C37). (b) **저엔트로피 PIN** — throttle이 지키는 딱 그만큼만 안전합니다. (c) **클래스 다운그레이드** — Weak를 요청하는 호출.

**핵심 구분**: 인증은 키의 **사용**과 기기 잠금해제를 게이팅할 뿐, 키 **추출**(C40)과는 별개이고, **인증 바인딩 안 된 키를 안전하게 만들지도 않습니다**(그런 키는 HAT 없이 그냥 쓰입니다). 이건 제 CVE 시리즈의 결과 겹칩니다 — authenticator TA의 파서 버그는 8편 블루투스·9편 Parcel과 같은 결의 메모리 안전 문제가, 이번엔 시큐어 월드 안에서 벌어지는 것입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 6.0 | **Gatekeeper** 도입(enroll/verify + SID 모델) |
| Android 7.0 | **Synthetic Password**(자격증명↔키 디커플링) |
| Android 8.1 / Pixel 2·3 | **Weaver** + Titan M(SE 기반 throttle) |
| Android 9 (API 28) | **BiometricPrompt**(FingerprintManager 대체), Strong/Weak/Convenience 명명 |
| Android 10 (API 29) | `BiometricManager.canAuthenticate()`(무인자) |
| **Android 11 (API 30)** | **Class 3/2/1** 숫자 라벨, `Authenticators`(BIOMETRIC_STRONG/WEAK)·`DEVICE_CREDENTIAL`·`setAllowedAuthenticators` |
| Android 13/14 | Gatekeeper HAL HIDL→AIDL |

생체 임계값은 CDD 7.3.10: 모든 등급이 **FAR ≤ 1/50,000**을 공유하고, Strong/Weak를 가르는 건 **SAR/IAR**(Class 3 ≤ 7%, Class 2 ≤ 20%) + 아키텍처 요건입니다. FAR가 아니라 **스푸핑 저항(SAR)**이 축입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**앱/온디바이스**
- `BiometricManager.canAuthenticate(BIOMETRIC_STRONG)` vs `(BIOMETRIC_WEAK)`의 결과 차이(같은 기기가 다르게 답함), 반환 코드 `SUCCESS`/`ERROR_NONE_ENROLLED`/`ERROR_NO_HARDWARE`/`ERROR_HW_UNAVAILABLE`/`ERROR_SECURITY_UPDATE_REQUIRED`.
- `KeyguardManager.isDeviceSecure()`(보안 잠금 존재 여부), `dumpsys biometric`(센서 강도 Strong/Weak/Convenience·lockout), `dumpsys lock_settings`(자격증명 타입·SP/Weaver 사용).
- 생체 HAL의 `SensorStrength`, **Weaver HAL 인스턴스 존재 자체가 SE 기반 throttle의 신호**.

**주의: 에뮬레이터는 전부 소프트웨어입니다** — 소프트 Keymaster/Gatekeeper, Weaver/SE 없음, goldfish 생체 스텁, StrongBox 없음. 지문은 `adb -e emu finger touch <id>`로 주입. TEE/SE/클래스 보증은 여기서 검증되지 않습니다.

**소스**
- AOSP `hardware/interfaces/{gatekeeper,weaver,biometrics/fingerprint,biometrics/face,security/keymint,security/sharedsecret}/aidl`, `system/gatekeeper`, `frameworks/base` `SyntheticPasswordManager`·`LockSettingsService`
- `source.android.com/docs/security/features/{authentication,authentication/gatekeeper,biometric}`, CDD 7.3.10

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C39(TEE)**: Gatekeeper와 생체 매처가 사는 곳이 그 시큐어 월드의 TA(S-EL0)입니다. 매칭이 거기서 일어나 템플릿이 노멀 월드로 안 나옵니다.
- **C40(Keystore)**: auth-bound 키가 요구하던 **HAT·SID의 출처**가 여기입니다. C40에서 "정상 PIN 변경은 키를 안 죽인다"고 정정했던 그 규칙의 근원이 아래 synthetic password입니다.
- **C43(FBE)**: synthetic password가 **CE(자격증명 암호화) 저장소 키**를 파생합니다. 자격증명은 SP를 열 뿐, SP가 디스크 키와 키스토어 키 양쪽에 묶입니다.
- **C05·C28**: 시큐어 월드와, 그 TEE 이미지를 검증하는 부팅의 뿌리.
- **CVE 시리즈**: authenticator TA의 파서 버그가 같은 결의 메모리 안전 문제입니다.
- 다음은 **C42(attestation·신뢰의 뿌리)** 또는 **C43(FBE·Direct Boot)**로 이어집니다.

## 호출 흐름

두 개를 손으로 그려 보시길 권합니다.

```
[ Gatekeeper: 자격증명이 증거(HAT)가 되는 길 ]

enroll(자격증명) ──▶ Gatekeeper TA(TEE)
                       패스워드 핸들 = 해시 + SID + HMAC(GateKeeper 키)
                       ◀── 핸들만 OS 에 저장(자격증명은 안 남음)

verify(자격증명, 핸들) ──▶ Gatekeeper TA(TEE)
   │ 실패 → throttle 카운터 먼저 기록(RPMB) → 타임아웃(ms) 반환
   │ 성공 → HAT = { userId=SID, authenticatorType=PASSWORD, timestamp, mac }
   │        mac = HMAC(ISharedSecret 공유키)
   ▼
   KeyMint(C40): mac 검증 → HAT.userId == 키의 USER_SECURE_ID? → 사용 허용
```

```
[ 생체 CryptoObject: Strong 만 키를 연다 ]

BiometricPrompt.authenticate(CryptoObject, BIOMETRIC_STRONG)
   │  (WEAK/DEVICE_CREDENTIAL 를 CryptoObject 와 섞으면 거부)
   ▼
생체 매처 TA(TEE) — 템플릿·매칭은 안에서, 결과 boolean 만 밖으로
   │ Strong 매치 성공
   ▼
HAT { userId=생체 SID(≠ Gatekeeper SID), authenticatorType=FINGERPRINT, ... }
   │
   ▼
KeyMint 검증 → auth-per-use 면 begin() 챌린지 일치까지 → 연산
   ── 새 지문 등록 → 생체 SID 회전 → 그 키 영구 무효화(기본값) ──
   ── PIN 변경 → Gatekeeper SID 유지 → 그 키 생존 ──
```

## 실측으로 확인한 것

이 모듈의 핵심 주장은 "Gatekeeper·Weaver·생체 매처의 검증과 HAT 서명이 모두 하드웨어 시큐어 컴포넌트 안에서 일어난다"는 것입니다. 그 전제의 참·거짓을 이 AVD(`codex-atlas-api33`, x86_64, API 33)에서 KeyMint 자신이 보고하는 값으로 확인했습니다.

**1) 이 환경엔 시큐어 컴포넌트가 없다 — KeyMint가 스스로 `SOFTWARE(0)`이라고 답한다.** AndroidKeyStore EC 키를 만들고 attestation challenge와 함께 `KeyInfo`·인증서 체인을 조회한 결과, 키 보안 수준이 정확히 소프트웨어였습니다.

```console
# AndroidKeyStore EC 키 생성 → attestation challenge → KeyInfo·인증서 체인 조회
KeyInfo.securityLevel       = SECURITY_LEVEL_SOFTWARE (0)
attestation cert chain 길이 = 3
```

이 한 값이 질문 2·질문 3·질문 7의 전제를 프로세스 수준에서 확증합니다. Gatekeeper TA의 throttle HMAC 키도, KeyMint가 HAT을 검증하는 `ISharedSecret` 공유 키도 **TEE/SE 안**에 있어야 하는데(질문 2·3), 이 AVD의 KeyMint는 자기 자신이 SOFTWARE 수준이라고 보고합니다. 곧 질문 7의 "에뮬레이터는 전부 소프트웨어 — Weaver/SE 없음, TEE·클래스 보증은 여기서 검증되지 않는다"가 서술이 아니라 측정된 상수로 확인됩니다.

**2) attestation 체인은 성립하지만 하드웨어 루트가 아니다 — 길이 3, 리프는 SOFTWARE.** attestation 요청 자체는 성공해 길이 3의 인증서 체인이 돌아왔지만, 리프 키의 보안 수준이 `SOFTWARE(0)`이므로 이 체인의 뿌리는 하드웨어 root of trust가 아니라 소프트웨어입니다. HAT을 서명하는 secure environment(질문 3의 "두 개의 서로 다른 HMAC 키")가 이 환경엔 물리적으로 부재함을, attestation 산출물 자체가 드러냅니다. 원시 값은 상단 검증 화면(`evidence-keystore.png`)과 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 보존했습니다.

**3) HAT의 `authenticatorType`이 PASSWORD·FINGERPRINT 두 값뿐인 건 인터페이스 정의로 확정된다(질문 4).** 이 부분은 AVD가 아니라 공개 소스로 확인했습니다 — AOSP `hardware/interfaces/gatekeeper`·`security/keymint`의 `HardwareAuthToken`/`HardwareAuthenticatorType` 정의에 열거값이 두 개뿐이고, 얼굴 인식조차 성공 시 `FINGERPRINT` 비트로 보고되는 매핑은 프레임워크의 `AUTH_BIOMETRIC_STRONG`→`FINGERPRINT` 변환 코드에서 나옵니다. 이 열거 구조는 하드웨어 서명 유무와 무관하게 인터페이스 정의가 확정하며, 값이 두 개뿐이라는 사실은 소스에서 그대로 확인됩니다.

## 소스로 확정한 것

이 AVD로 직접 캡처한 값은 위 (1)~(3)입니다. 나머지 하드웨어 축은 실행 지점이 시큐어 월드·전용 SE·ARM64 런타임이라, x86_64 AVD가 아니라 **AOSP·ARM 공식 문서와 공개 소스로 확정**하고, 에뮬레이터에서 실제로 도는 **소프트웨어 폴백은 위 실측이 이미 붙잡았습니다.**

**1) Gatekeeper·Weaver throttle과 HAT 서명·검증, in-TEE 생체 매칭의 동작은 AOSP 소스로 확정된다.** verify 실패 시 카운터를 RPMB에 먼저 적고, 서스펜드 중에도 도는 보안 단조 시계로 백오프를 재며, HAT을 `ISharedSecret` 공유 키로 서명하는 경로는 `system/gatekeeper`와 인증 문서에 못 박혀 있습니다(질문 5). 이 AVD에서는 그 자리에 소프트웨어 폴백이 서고, **위 실측 (1)의 `SECURITY_LEVEL_SOFTWARE(0)`이 바로 그 폴백의 산물**입니다 — 하드웨어 동작은 소스로, 소프트웨어 대체물은 측정으로 각각 확정됩니다.
근거: [Gatekeeper](https://source.android.com/docs/security/features/authentication/gatekeeper) · [system/gatekeeper](https://cs.android.com/android/platform/superproject/+/main:system/gatekeeper/)

**2) Weaver/SE(Titan M류)·StrongBox의 SE 기반 throttle insider 저항은 공개 AIDL과 인증 문서로 확정된다.** Weaver `write/read(slot, key)`가 키 불일치 시 throttle을 돌려주고 재시도 제한을 **별도 SE 펌웨어**로 옮긴다는 계약은 `hardware/interfaces/weaver` AIDL과 인증 문서의 설계입니다(질문 5). 전용 SE를 얹은 기기는 이 경로로 TEE·OEM 펌웨어를 뚫어도 재시도 제한이 우회되지 않고, 전용 SE가 없는 이 에뮬레이터는 Gatekeeper의 TEE-throttle 경로로 대체되며 그 경로가 여기선 다시 (1)의 소프트웨어 폴백으로 내려앉습니다.
근거: [Authentication](https://source.android.com/docs/security/features/authentication) · [hardware/interfaces/weaver](https://cs.android.com/android/platform/superproject/+/main:hardware/interfaces/weaver/)

**3) 생체 클래스(3/2/1)와 SAR/IAR 임계값은 CDD 7.3.10으로, ARM64 완화의 런타임은 ARM/AOSP 문서로 확정되고 — 정적 마커는 실측이 있다.** 클래스 임계값은 모든 등급이 FAR ≤ 1/50,000을 공유하고 Class 3 SAR ≤ 7%·Class 2 ≤ 20%로 CDD 7.3.10이 고정합니다(질문 6). ARM64의 PAC 서명·인증, BTI 랜딩 패드, MTE 태깅, EL 전이는 ARM 아키텍처 문서가 규정하고 AOSP 빌드가 켭니다. 런타임 실행은 x86 호스트 밖이지만, **정적 마커는 실제 arm64 바이너리에서 뽑았습니다** — 진짜 arm64 `.so`를 빌드해 `readelf`로 `.note.gnu.property`를 확인하면 `aarch64 feature: BTI, PAC`가 그대로 박혀 있고, 대조군(`-mbranch-protection=none`)은 매치 0으로 대조가 성립합니다.

```console
# 실제 arm64 .so 빌드 → readelf 로 .note.gnu.property 확인
  Machine:                           AArch64
Displaying notes found in: .note.gnu.property
  GNU                  0x00000010	NT_GNU_PROPERTY_TYPE_0 (property note)
    Properties:    aarch64 feature: BTI, PAC
# 대조군 -mbranch-protection=none: BTI/PAC note 매치 수 = 0 (대조 성립)
```

즉 **마커는 실측, 런타임 동작은 소스 확정**입니다.
근거: [CDD 7.3.10](https://source.android.com/docs/compatibility/cdd) · [Biometric](https://source.android.com/docs/security/features/biometric) · [ARM MTE](https://source.android.com/docs/security/test/memory-safety/arm-mte) · [Arm 아키텍처 학습](https://developer.arm.com/architectures/learn-the-architecture) · [LLVM `-mbranch-protection`](https://clang.llvm.org/docs/ClangCommandLineReference.html)

## 마치며

이 계층의 핵심은 인증 UI 자체가 아니라 secure component가 발급한 HAT과 KeyMint authorization의 연결입니다. Gatekeeper와 Weaver는 LSKF 검증·rate limiting 역할을 나눌 수 있고 Weaver는 SE 또는 TEE에 구현될 수 있습니다. 생체 class와 HAT 검증도 각 구현의 security requirement와 threat model 안에서 평가해야 합니다.

그리고 두 가지를 분명히 해야 합니다: 인증은 키의 **사용**을 게이팅할 뿐 **추출**이 아니고(C40), 정상 PIN 변경이 키를 죽이지 않는 이유는 **synthetic password**가 자격증명과 키를 떼어놨기 때문입니다. 다음은 이 모든 것이 원격까지 증명되는 자리인 **C42(key attestation·신뢰의 뿌리)**, 또는 synthetic password가 디스크 키를 파생하는 **C43(FBE·Direct Boot)**로 이어집니다. 이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.
