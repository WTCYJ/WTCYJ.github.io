---
layout: post
title: "KeyMint·TEE·Gatekeeper·Weaver"
date: 2026-12-06 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, KeyMint, Keystore2, TEE, StrongBox, Gatekeeper]
excerpt: "하드웨어 키 저장이라 해도 앱이 손에 쥐는 건 평문 키가 아니라 불투명 키 블롭이다. 그리고 흔한 착각 — StrongBox와 TEE는 같은 물건이 아니다."
---

안드로이드에서 지문·PIN으로 잠금을 풀고, 앱은 "하드웨어 키"로 서명한다. 그런데 이 "하드웨어"가 정확히 어디이고, 무엇을 지키며, 무엇은 못 지키는지는 대충 넘어가기 쉽다. KeyMint·Gatekeeper·Weaver는 전부 Rich Execution Environment(REE, 즉 안드로이드+리눅스 커널) 바깥의 신뢰 실행 환경(TEE)이나 별도 보안칩에서 도는 컴포넌트다. REE는 크고, 뚫린다고 가정된다. 그래서 비밀은 REE 밖으로 밀려난다.

이 글은 KeyMint(키 연산)·Gatekeeper(자격증명 검증)·Weaver(스로틀링 슬롯) 세 축이 AOSP HAL과 `keystore2`를 통해 어떻게 맞물리는지, 그리고 앱과 system_server가 실제로 손에 쥐는 게 무엇인지를 1차 소스 기준으로 정리한 기록이다. 실습은 에뮬레이터와 자작 앱으로 관측 가능한 부분까지만 확인한다.

> **한 줄 결론**: 하드웨어 키 저장의 핵심은 "앱이 평문 키가 아니라 불투명 키 블롭만 쥔다"는 것이다. KeyMint는 연산을, Gatekeeper/Weaver는 스로틀링을 secure world 안에서 담당하고, REE는 오직 스로틀링된 오라클과 HMAC로 봉인된 토큰만 본다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 것은 넷의 역할 분담과 그 사이의 신뢰 경계다. KeyMint HAL이 키 연산을 어떻게 캡슐화하는지, `keystore2`가 왜 중간 브로커로 필요한지, 사용자 인증에 묶인(auth-bound) 키가 어떻게 `HardwareAuthToken`으로 게이팅되는지, Gatekeeper와 Weaver의 스로틀링이 어디서 갈라지는지, 그리고 이 중 무엇이 에뮬레이터에서 관측되고 무엇은 안 되는지까지다.

선수 개념 셋이 밑에 깔린다. 이 컴포넌트는 전부 AIDL HAL이라 14장(Binder proxy/stub)·15장(Stable AIDL)·16장(HAL·VINTF·VTS)에서 다룬 인터페이스 구조를 그대로 쓴다. ARM TrustZone의 secure/non-secure world 분리는 Atlas C05, 하드웨어 신뢰뿌리·롤백 방지는 Atlas C29, Keystore·StrongBox의 큰 그림은 Atlas C40에 있다. 이걸 모르면 "왜 굳이 REE 밖으로 보내나"가 안 잡힌다.

전체 구조에서 이 장은 2부(플랫폼 내부)의 바닥이다. 앱 → 프레임워크 → Binder → system_server → HAL을 내려온 흐름이 여기, 가장 낮은 신뢰뿌리인 secure world에서 끝난다.

## 핵심 개념 — 네 컴포넌트의 역할 분담

넷은 겹치지 않는다. 하나는 연산, 하나는 자격증명 검증, 하나는 스로틀링된 저장, 하나는 이들을 REE에서 중개한다.

| 컴포넌트 | 어디서 도나 | 무엇을 하나 | REE/앱이 보는 것 |
|--|--|--|--|
| **KeyMint** | TEE 또는 StrongBox(SE) | 키 생성·서명·암복호·attestation | 불투명 키 블롭 + 연산 결과 |
| **Gatekeeper** | TEE | PIN/패턴/비번 HMAC 검증 + 스로틀링 | 성공 시 `HardwareAuthToken` |
| **Weaver** | 별도 보안칩(SE) | `key→value` 슬롯 저장 + 읽기 스로틀링 | value 또는 스로틀 타임아웃 |
| **keystore2** | REE(system 프로세스) | KeyMint 접근 중개·앱별 권한·키 DB | 앱↔KeyMint 브로커 |

KeyMint는 Android 12에서 이전 Keymaster(HIDL)를 대체한 AIDL HAL이고, `keystore2`는 같은 시점에 Rust로 재작성돼 옛 `keystore` 데몬을 대체했다. `Source-confirmed` 앱이 `AndroidKeyStore` 프로바이더로 키를 만들면, 개인키 바이트는 앱 프로세스로 절대 넘어오지 않는다. 앱은 `keystore2`를 통해 KeyMint에게 "이 키로 서명해"라고 요청할 뿐이고, 연산은 secure world 안에서 일어난다. `Source-confirmed`

키가 실제로 어디 사는지는 `KeyInfo.getSecurityLevel()`(API 31+)이 알려준다 — 생성한 키에서는 주로 `SOFTWARE`·`TRUSTED_ENVIRONMENT`·`STRONGBOX` 셋 중 하나이며, 그 밖에 `UNKNOWN`/`UNKNOWN_SECURE` 값도 정의돼 있다. 여기서 흔한 착각 하나. **StrongBox와 TEE는 같은 물건이 아니다.** TEE는 메인 CPU의 secure world(TrustZone)이고, StrongBox는 그와 물리적으로 분리된 tamper-resistant 보안칩(예: 픽셀의 Titan M 계열)이다. `TRUSTED_ENVIRONMENT`와 `STRONGBOX`가 다른 값인 이유가 이것이다. `Source-confirmed` StrongBox는 `FEATURE_STRONGBOX_KEYSTORE`가 있는 기기에만 존재하며, 없는 기기에서 StrongBox 키를 요청하면 실패한다.

Key attestation은 이 하드웨어 소속을 외부에 증명하는 장치다. KeyMint가 키의 속성(하드웨어 보관 여부·인증 요구·롤백 저항 등)을 담은 인증서 체인을 발급하고, 그 체인은 벤더/구글의 attestation 루트로 이어진다. 서버는 이 체인을 검증해 "이 키는 진짜 하드웨어에 있다"를 확인한다. `Source-confirmed`

> **[그림 1]** 자작 앱에서 `KeyGenParameterSpec`로 만든 키의 `KeyInfo.getSecurityLevel()` 값을 logcat으로 출력 — 에뮬레이터에서 SOFTWARE/TRUSTED_ENVIRONMENT 중 무엇으로 잡히는지 실측 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 아키텍처의 위협 모델은 명확하다. **REE(안드로이드+리눅스 커널)는 언젠가 뚫린다고 가정한다.** 커널 LPE 하나로 root가 잡히면 REE의 모든 메모리가 노출된다. 그러니 키 바이트와 자격증명 검증을 REE 밖, 훨씬 작고 따로 서명·검증되는 secure world로 밀어낸다. TCB(Trusted Computing Base)를 줄이는 게 목적이다. `Inferred`

인증에 묶인 키가 이 경계를 잘 보여준다. 앱이 `setUserAuthenticationRequired(true)`로 키를 만들면, 그 키의 연산은 사용자 인증 없이는 KeyMint가 거부한다. 인증 성공의 증거는 Gatekeeper(또는 생체 HAL)가 발급한 `HardwareAuthToken`이고, 이 토큰에는 secure user id·인증 타입·타임스탬프와 **HMAC**이 들어 있다. `Source-confirmed`

핵심은 이 HMAC 키가 어디 있느냐다. KeyMint와, `HardwareAuthToken`을 발급하는 컴포넌트들(Gatekeeper·생체 HAL)은 부팅마다 각자의 논스를 모아 공유 HMAC 키를 합의한다(`ISharedSecret.computeSharedSecret`). 그래야 생체 HAL이 서명한 토큰도 KeyMint가 같은 키로 검증할 수 있다. 이 키는 secure world 참여자들만 알고 REE는 모른다. 그래서 REE는 `HardwareAuthToken`을 **위조할 수 없다** — 토큰을 만들어 보내도 HMAC이 안 맞아 KeyMint가 걷어찬다. `Source-confirmed` REE는 토큰을 나르는 배달부일 뿐, 발행자가 아니다.

Gatekeeper의 두 번째 무기는 스로틀링이다. `verify()`가 틀린 비번을 받으면 실패를 secure storage에 기록하고 백오프를 강제한다. 그래서 잠금화면 무차별 대입은 REE에서 아무리 빨리 때려도 secure world가 정한 속도 이상 못 나간다. `Source-confirmed`

Weaver는 여기서 한 단계 더 나간다. TEE마저 신뢰하지 않는 위협을 상정한다. Weaver는 별도 보안칩의 슬롯에 `(key, value)`를 저장하고, 틀린 key로 `read`하면 칩 자체가 지수 백오프를 건다. 안드로이드의 synthetic password는 이 value를 자격증명(PIN에서 유도한 key)으로만 풀 수 있게 묶어, FBE(파일 기반 암호화) 키 유도를 하드웨어 스로틀링에 종속시킨다. `Reported` 즉 SE가 있는 기기에서는 TEE가 털려도 자격증명에 묶인 비밀은 SE의 스로틀링을 못 넘는다.

## 관측

무엇이 실제로 이 기기에서 도는지는 `lshal`로 등록된 HAL 인스턴스를 보면 된다. userdebug 에뮬레이터에서 실행한다.

```bash
adb shell lshal | grep -iE "keymint|gatekeeper|weaver|sharedsecret"
adb shell pm list features | grep -iE "keystore|strongbox"
```

`예시 출력`(네 실제 실행으로 교체):

```
# lshal (형식·PID는 환경마다 다름 — 교체)
android.hardware.security.keymint.IKeyMintDevice/default
android.hardware.gatekeeper.IGatekeeper/default
android.hardware.security.sharedsecret.ISharedSecret/default

# pm list features
feature:android.hardware.hardware_keystore
# (에뮬레이터에는 feature:android.hardware.strongbox_keystore 가 없다)
```

에뮬레이터에서 관측되는 것과 아닌 것이 갈린다. KeyMint HAL 인스턴스와 keystore2 서비스는 잡히지만, 그건 software 또는 에뮬된 구현이라 **하드웨어 tamper-resistance는 흉내일 뿐 실물이 아니다.** StrongBox 피처는 아예 없어 SE 경로는 관측 불가다. `getSecurityLevel()`이 에뮬레이터에서 무엇을 반환하는지는 AVD의 Trusty 지원 여부에 달려 SOFTWARE 또는 TRUSTED_ENVIRONMENT로 갈린다 — 원문/실측 재확인 필요. 이건 앞선 환경 편(Atlas C40)에서 "에뮬엔 실 TEE/StrongBox·RPMB가 없다"고 짚은 그 한계와 정확히 같은 지점이다.

> **[그림 2]** `adb shell lshal | grep -iE "keymint|gatekeeper|weaver"`로 등록된 보안 HAL 인스턴스와 backing 프로세스를 확인 + `pm list features`에서 StrongBox 부재를 대조한 터미널 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

세 가지가 겹쳐 이 구조를 강제한다.

첫째, **TCB 최소화.** 리눅스 커널은 수백만 줄에 드라이버까지 얹혀 공격 표면이 거대하다. 비밀을 이 안에 두면 커널 버그 하나가 곧 키 유출이다. 그래서 키와 자격증명 검증만 떼어 작고 따로 검증되는 secure world에 넣는다. secure world가 작을수록 감사·형식검증이 현실적이 된다. `Inferred`

둘째, **하드웨어로 강제하는 스로틀링.** 무차별 대입 방어를 소프트웨어에 맡기면 그 소프트웨어를 우회하는 순간 무력화된다. Gatekeeper/Weaver는 백오프 상태를 secure storage/SE에 두고 하드웨어가 세므로, REE root를 잡아도 시도 속도를 못 올린다. 6자리 PIN이 버티는 이유는 엔트로피가 아니라 이 스로틀링이다. `Inferred`

셋째, **불투명 핸들.** 앱에게 평문 키를 절대 주지 않고 암호화된 블롭과 "연산해줘" 인터페이스만 준다. 키는 secure world를 떠나지 않고, REE는 결과만 받는다. `HardwareAuthToken`의 HMAC 봉인도 같은 논리다 — REE에게 오라클은 주되 발행 권한은 안 준다. `Source-confirmed`

정리하면, 신뢰뿌리를 OS가 아니라 하드웨어에 두고, REE에는 스로틀링된 오라클과 봉인된 토큰만 노출하는 것 — 이게 KeyMint·Gatekeeper·Weaver가 한 몸으로 겨냥하는 설계다.

## 버전 차이와 한계

- **Keymaster → KeyMint.** Android 12(API 31)부터 HIDL Keymaster가 AIDL KeyMint로 바뀌었고, secure clock(`ISecureClock`)·shared secret(`ISharedSecret`)이 별도 AIDL 인터페이스로 분리됐다. 문서화할 땐 어느 세대인지 표기한다. `Source-confirmed`
- **keystore → keystore2.** 같은 시점에 데몬이 Rust `keystore2`로 재작성됐다. 옛 `keystore` 코드 경로를 참조하면 최신 기기와 안 맞는다. `Source-confirmed`
- **StrongBox는 선택.** `FEATURE_STRONGBOX_KEYSTORE`가 없는 기기에선 TEE 레벨까지만 가능하다. StrongBox를 무조건 가정하고 키를 만들면 실패한다. `Source-confirmed`
- **API 변화.** `KeyInfo.isInsideSecureHardware()`는 deprecated이고, 세밀한 구분은 `getSecurityLevel()`을 쓴다. `Reported`
- **에뮬레이터 한계.** 실 TEE/SE가 없어 하드웨어 attestation의 신뢰뿌리·Weaver 스로틀링·StrongBox 격리는 관측되지 않는다. secure world 로직의 흐름 이해까지가 에뮬로 가능한 상한이다. `Inferred`

## 정리

- KeyMint는 연산, Gatekeeper는 자격증명 검증+스로틀링, Weaver는 SE 슬롯 스로틀링, keystore2는 REE 브로커 — 역할이 겹치지 않는다.
- 앱은 평문 키가 아니라 불투명 블롭만 쥐고, auth-bound 키는 REE가 위조 못 하는 HMAC 봉인 `HardwareAuthToken`으로 게이팅된다.
- StrongBox(별도 SE)와 TEE(TrustZone)는 다른 신뢰 레벨이며, `getSecurityLevel()`이 이를 구분한다.
- PIN이 버티는 힘은 엔트로피가 아니라 하드웨어 스로틀링이다.

**점검 질문** — (1) `HardwareAuthToken`을 REE가 위조할 수 없는 이유는 무엇인가? (2) `TRUSTED_ENVIRONMENT`와 `STRONGBOX`는 각각 어떤 하드웨어를 가리키며 왜 구분하나? (3) Gatekeeper와 Weaver의 스로틀링은 어떤 위협 가정에서 갈리는가?

**참고** — Android Keystore([developer.android.com/privacy-and-security/keystore](https://developer.android.com/privacy-and-security/keystore)) · Hardware-backed Keystore/KeyMint([source.android.com/docs/security/features/keystore](https://source.android.com/docs/security/features/keystore)) · Gatekeeper([source.android.com/docs/security/features/authentication/gatekeeper](https://source.android.com/docs/security/features/authentication/gatekeeper)) · AOSP HAL 소스 `hardware/interfaces/security/keymint/aidl`·`hardware/interfaces/gatekeeper/aidl`·`hardware/interfaces/weaver/aidl`([cs.android.com](https://cs.android.com)) · Keystore 2.0 `system/security/keystore2`
