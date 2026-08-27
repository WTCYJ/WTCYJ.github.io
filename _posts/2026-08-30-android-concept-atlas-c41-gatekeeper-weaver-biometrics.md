---
layout: post
title: "Android Security Concept Atlas C41 - Gatekeeper·Weaver·생체, 누가 잠금을 여는가"
date: 2026-08-30 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Gatekeeper, Weaver, Biometrics, BiometricPrompt, HardwareAuthToken, SyntheticPassword, SecureUserID, Throttling, TitanM, ConceptAtlas, 학습기록]
excerpt: "C39는 시큐어 월드가 어디인지, C40은 그 안의 키가 무엇을 지키는지였습니다. C41은 그 키의 잠금을 누가 여는가입니다. Gatekeeper가 TEE 안에서 PIN을 검증하고, 재부팅으로도 시계 조작으로도 풀리지 않는 throttle로 저엔트로피 PIN을 지키며, Weaver가 그 throttle을 별도 보안 요소로 옮겨 OEM조차 우회 못 하게 만듭니다. 생체는 클래스(Strong만 Keystore를 엽니다)로 갈리고, 성공하면 위조 불가능한 HardwareAuthToken이 KeyMint로 건너갑니다. 그리고 왜 정상 PIN 변경이 auth-bound 키를 죽이지 않는지 — synthetic password가 그 답입니다. 하드웨어 보안 삼부작의 마지막, Concept Atlas의 열두 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C41 — Gatekeeper·Weaver·biometrics
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 고급 · **선수 개념**: C39(TEE·시큐어 월드), C40(Keystore·HAT·SID)
> **성격**: 미학습 → 풀 작성. 하드웨어 보안 삼부작(C39·C40·C41)의 마지막.
> **완료 기준**: 사용자 인증이 auth-bound 키의 HAT·SID로 이어지는 경로와, throttle이 재부팅·시계 조작으로 풀리지 않는 이유를 설명할 수 있다.

C39는 시큐어 월드가 **어디**인지였고, C40은 그 안의 키가 **무엇**을 지키는지였습니다. C41은 그 키의 잠금을 **누가 여는가**입니다. C40에서 인증 바인딩 키가 요구하던 그 HardwareAuthToken(HAT)과 Secure User ID(SID)가 **어디서 오는지** — 그 출처가 이 모듈입니다.

한 문장으로: **사용자 확인(PIN·생체)은 TEE 안에서 이뤄지고, 그 성공의 증거인 HAT은 시큐어 월드 키로 서명돼 커널이 위조할 수 없으며, throttle은 재부팅으로도 시계 조작으로도 풀리지 않는다.** 🔴 미학습 영역이라 처음부터 세웁니다.

## 배경 개념 - 잠금 지식과 생체를 증거로 바꾸기

- **LSKF (Lockscreen Knowledge Factor)**: PIN·패턴·암호. Gatekeeper가 검증합니다.
- **Gatekeeper**: LSKF를 검증하는 TEE 트러스티드 앱(S-EL0, C39). enroll→패스워드 핸들, verify→HAT.
- **Secure User ID (SID)**: 자격증명에 묶이는 무작위 64비트 값. auth-bound 키가 여기 묶입니다(C40).
- **HardwareAuthToken (HAT)**: 인증 성공의 증거. 시큐어 월드에서 공유한 HMAC 키로 서명돼 KeyMint가 검증합니다.
- **Weaver**: throttle을 **별도 보안 요소(SE)**로 옮긴 서비스(Titan M/M2).
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

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

각 문장이 왜 틀렸는지 한 줄로 반박해 보세요.

1. "Gatekeeper의 throttle이 4자리 PIN을 긴 암호만큼 암호학적으로 강하게 만든다."
2. "재부팅하거나 시스템 시계를 앞으로 돌리면 throttle이 풀려 계속 추측할 수 있다."
3. "기기 잠금을 여는 어떤 지문/얼굴이든 Keystore의 auth-bound 키를 열 수 있다."
4. "루팅/커널 침해로 인증 성공(HAT)을 위조해 auth-bound 키를 열 수 있다."
5. "Weaver는 모든 Android 기기의 기본 보안이다 / 정상 PIN 변경은 auth-bound 키를 무효화한다."

<details><summary>판정 기준(펼치기)</summary>

1. throttle은 엔트로피를 안 늘리고 추측 **속도**만 제한합니다. PIN은 여전히 저엔트로피이고, TEE가 뚫리면(또는 SE 기반 throttle이 없으면) 속도 제한도 우회됩니다 — 그래서 Weaver가 throttle을 SE로 옮깁니다.
2. 카운터는 RPMB(재생 방지)에 남아 재부팅으로 안 풀리고, 타임아웃은 **서스펜드 중에도 도는 보안 단조 시계**로 재므로 노멀 월드 시계 조작이 안 먹습니다.
3. **Class 3(Strong)만** Keystore 키를 열고 CryptoObject를 지원합니다. Class 2(Weak)·Class 1(Convenience)은 UI 잠금해제는 되지만 키는 못 엽니다.
4. HAT의 HMAC 키는 시큐어 월드에서만 공유됩니다(`ISharedSecret`). 커널은 연산을 요청할 순 있어도 인증을 위조하지 못합니다.
5. Weaver는 SE가 있어야 합니다(Titan급) — 없는 기기는 Gatekeeper TEE throttle로 대체. 그리고 정상 PIN 변경은 현재 핸들과 함께 enroll해 **SID를 유지**하므로 키가 살아남습니다(제거/리셋에서만 회전).
</details>

## 서술형 문제 3개

1. Gatekeeper throttle이 재부팅·시계 조작으로 풀리지 않는 이유(RPMB·보안 단조 시계)와, 그럼에도 TEE 침해엔 무너지는 이유, 그래서 Weaver가 throttle을 **어디로** 옮겼는지 서술하세요.
2. Synthetic Password가 왜 정상 PIN 변경 시 데이터 재암호화 없이 SID를 유지하는지(= C40의 "변경은 키를 안 죽인다"의 근원)를 **디커플링**으로 설명하세요.
3. 생체 클래스가 modality(지문/얼굴)가 아니라 **SAR/IAR**로 정해지는 이유와, 왜 Class 3만 Keystore를 여는지(그리고 클래스 다운그레이드 요청이 왜 키를 못 건드리는지) 서술하세요.

## 소스 탐색 과제

실기기에서 다음을 수행하고 근거와 함께 정리하세요.

- `BiometricManager.canAuthenticate(BIOMETRIC_STRONG)`와 `(BIOMETRIC_WEAK)`를 각각 호출해 **같은 기기가 다르게 답하는지** 확인하고, `dumpsys biometric`으로 센서의 광고 강도(Strong/Weak/Convenience)를 대조.
- `dumpsys lock_settings`(또는 HAL 인스턴스 목록)로 이 기기가 **Weaver(SE)**를 쓰는지 확인하고, 그것이 왜 SE 기반 throttle의 신호인지 적으세요.
- 왜 `sec-api33` 에뮬에서는 이 신호들이 소프트웨어/부재로 나오는지(진짜 TEE/SE/생체 하드웨어 없음) 근거와 함께 적으세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 환경 특성: 에뮬은 전부 소프트웨어(소프트 Gatekeeper/KeyMint, Weaver/SE·StrongBox 없음, goldfish 생체) — TEE/SE/클래스 보증은 실기기 필요. 지문은 `adb -e emu finger touch <id>`. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **클래스 대조**: `canAuthenticate(STRONG)` vs `(WEAK)` 결과와 `dumpsys biometric` 센서 강도를 실제 출력으로.
2. **사용 게이팅 실측**: `setUserAuthenticationRequired(true)` 키를 만들어 잠금 해제 전 사용 시 `UserNotAuthenticatedException`, 해제 후 성공을 캡처.
3. **SID 회전 대조**: 새 지문을 등록한 뒤 생체-바인딩 키가 `KeyPermanentlyInvalidatedException`이 나는 것과, PIN을 변경한 뒤 자격증명-바인딩 키가 **살아남는** 것을 대조.
4. **Weaver 유무**: 실기기(가능하면 Pixel)와 에뮬에서 Weaver HAL/SE 사용 여부를 대조.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 재현 불가·미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

하드웨어 보안 삼부작이 여기서 닫힙니다. C39가 시큐어 월드(어디서), C40이 키 블롭(무엇을 지키나)이었다면, C41은 그 잠금을 여는 **인증**입니다. Gatekeeper가 TEE 안에서 PIN을 검증하고, 재부팅·시계로도 못 푸는 throttle이 저엔트로피 PIN을 지키며, Weaver가 그 throttle을 별도 SE로 옮겨 OEM조차 우회 못 하게 합니다. 생체는 스푸핑 저항(SAR)으로 클래스가 갈리고 **Class 3만** 키를 열며, 성공의 증거인 HAT은 시큐어 월드 키로 서명돼 커널이 위조하지 못합니다.

그리고 두 가지를 분명히 해야 합니다: 인증은 키의 **사용**을 게이팅할 뿐 **추출**이 아니고(C40), 정상 PIN 변경이 키를 죽이지 않는 이유는 **synthetic password**가 자격증명과 키를 떼어놨기 때문입니다. 다음은 이 모든 것이 원격까지 증명되는 자리인 **C42(key attestation·신뢰의 뿌리)**, 또는 synthetic password가 디스크 키를 파생하는 **C43(FBE·Direct Boot)**로 이어집니다. 위의 「블로그 초안 작성 과제」를 마치면 이 모듈이 실측 글로 확정됩니다.
