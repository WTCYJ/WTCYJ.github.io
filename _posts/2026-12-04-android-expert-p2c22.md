---
layout: post
title: "CTS·VTS·STS"
date: 2026-12-04 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, CTS, VTS, STS, 보안패치]
excerpt: "CTS는 GMS 라이선스의 관문이지 보안 검증이 아니다. 기기가 주장하는 보안 패치 수준(SPL) 문자열은 그 자체로 아무것도 증명하지 않으며, 수정이 실제로 들어갔는지는 STS만이 대조한다."
---

Android 기기가 "호환된다", "패치됐다"고 말할 때 그 말을 누가 검증하는가. 벤더가 자기 입으로 하는 주장과, 자동화된 테스트가 실측으로 확인한 사실은 전혀 다른 층위다. Android 생태계는 이 간극을 세 개의 테스트 스위트로 메운다 — CTS(호환성), VTS(벤더 경계), STS(보안 패치). 세 스위트를 뭉뚱그려 "인증 테스트"로 알면 정작 보안 검증이 어디서 일어나는지를 놓친다.

이 글은 CTS·VTS·STS가 각각 무엇을 검증하고, 세 스위트가 왜 같은 하네스(Trade Federation) 위에 서면서도 신뢰 경계가 서로 다른지를 AOSP 공개 문서 기준으로 정리한 기록이다. 특히 보안 관점에서 제일 자주 오해되는 지점 — "보안 패치 수준 문자열 = 안전"이라는 등식 — 이 왜 틀렸는지를 STS의 구조로 설명한다.

> **한 줄 결론**: CTS=호환성(CDD·GMS 관문), VTS=Treble 벤더 인터페이스, STS=보안 패치 실적용. 셋 다 tradefed 위에 서지만 검증 대상이 다르고, 특히 SPL 문자열은 STS 없이는 신뢰할 수 없다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 세 스위트의 목적·실행 구조·신뢰 경계다. 각 스위트를 처음부터 끝까지 돌리는 운영 가이드가 아니라, "어느 스위트가 무엇을 보증하고 무엇은 보증하지 않는가"를 가르는 개념 정리다. 무기화된 우회나 인증 회피는 다루지 않는다.

선수 지식이 몇 개 깔린다. Binder/AIDL로 정의되는 서비스 경계(14·15장)와 HAL·VINTF가 만드는 벤더/프레임워크 분리(16장)를 알아야 VTS가 왜 필요한지가 보인다. AOSP 빌드(Soong, 17장)와 Cuttlefish(18장)를 알면 이 스위트들을 안전 범위에서 직접 돌려볼 수 있다. 그리고 보안 패치 수준(SPL)과 월간 Android Security Bulletin의 관계를 알아야 STS의 위치가 잡힌다.

전체 구조에서 이 장은 **출하 게이트**에 해당한다. 앱→프레임워크→Binder→HAL→커널까지 쌓아 올린 구현이 실제로 "호환·안전"하다고 말하려면 마지막에 이 스위트들을 통과해야 한다. tradefed는 이 검증들을 얹는 공통 바닥이다.

## 핵심 개념 — 세 스위트, 하나의 하네스

세 스위트는 모두 **Trade Federation**(tradefed) 위에서 돈다. tradefed는 AOSP의 Java 기반 테스트 하네스로, 기기 준비·모듈 실행·결과 집계·재시도를 담당한다. CTS/VTS/STS(+비공개 GTS)는 tradefed에 얹힌 "xTS" 계열이며, 각각 콘솔 진입 후 `run <suite>` 형태로 실행한다. `Source-confirmed`

| 스위트 | 검증 대상 | 기준 문서/근거 | 실행(예) | 공개 여부 |
|--|--|--|--|--|
| CTS | 호환성(API 동작·동작 요건) | CDD(Compatibility Definition Document) | `cts-tradefed` → `run cts` | AOSP 공개 |
| VTS | 벤더 인터페이스(HAL·커널·VINTF) | Treble/VINTF 호환성 매트릭스 | `vts-tradefed` → `run vts` | AOSP 공개 |
| STS | 보안 패치의 실적용 | Android Security Bulletin(CVE) | `sts-tradefed` → `run sts` | 공개 문서·파트너 배포 |
| GTS | GMS 동작 | 비공개 | (비공개) | Google 전용 |

- **CTS**는 CDD가 규정한 "MUST" 요건을 자동으로 두드린다. CDD는 RFC 2119식 MUST/SHOULD 언어로 쓰이고, CTS는 그중 객관적으로 테스트 가능한 항목을 검증한다. CTS 통과는 GMS(Play 등) 라이선스의 전제다 — 즉 CTS는 일차적으로 **호환성 게이트**이지 보안 게이트가 아니다. `Source-confirmed` 사람·하드웨어 개입이 필요한 항목은 별도 APK인 **CTS Verifier**가 담당한다. `Source-confirmed`
- **VTS**는 Treble이 그은 벤더/프레임워크 경계를 검증한다. 프레임워크 호환성 매트릭스와 벤더 매니페스트(VINTF)가 맞물리는지, HAL·커널이 요구 인터페이스를 만족하는지를 본다. 이게 통과해야 프레임워크만 교체하는 OTA가 성립한다(16장). `Source-confirmed`
- **STS**는 월간 보안 게시판의 CVE 수정이 **실제로 들어갔는지**를 두드린다. 기기가 주장하는 SPL이 사실인지 대조하는 유일한 자동 검증이다. `Source-confirmed`

여기서 흔한 착각 하나 — "CTS를 통과했으니 안전하다"는 말은 성립하지 않는다. CTS는 호환성을, STS가 보안 패치를 본다. 두 스위트는 검증 대상이 겹치지 않는다. `Inferred`

> **[그림 1]** `cts-tradefed` 대화형 콘솔에서 `list plans`와 `list modules`로 CTS 계획·모듈 목록을 확인한 터미널 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 스위트들의 위협 모델은 외부 공격자가 아니라 **주장과 사실의 불일치**다. 벤더는 "API 34 호환", "보안 패치 2026-11-05 적용"이라고 선언할 수 있고, 이 선언은 문자열일 뿐이다. 신뢰 경계는 "누가 그 문자열을 강제하느냐"에서 갈린다.

- CTS의 경계: GMS 라이선스. CTS를 통과하지 못하면 Play 서비스를 실을 수 없다 — 이게 벤더에게 호환성을 강제하는 경제적 압력이다. `Source-confirmed`
- VTS의 경계: framework-only OTA. VINTF가 맞지 않으면 프레임워크 단독 업데이트가 깨지므로, Treble 경계 준수는 업데이트 가능성 자체와 묶인다. `Source-confirmed`
- STS의 경계: 보안 패치 수준의 신뢰성. **SPL 문자열(`ro.build.version.security_patch`)은 벤더가 채워 넣는 값이라 그 자체로는 수정 적용을 증명하지 않는다.** STS는 각 CVE에 대응하는 회귀 테스트를 실행해 실제 수정 여부를 실측한다. 문자열과 실측이 어긋나면 그게 바로 결함이다. `Source-confirmed`

즉 세 스위트가 하는 일의 본질은 같다 — **자기 신고를 자동 검증으로 대체**한다. 다른 것은 무엇을 신고 대상으로 보느냐뿐이다.

## 관측

전부 안전 범위(에뮬레이터·Cuttlefish·공개 AOSP 소스)에서 확인 가능하다. SPL 문자열은 어떤 기기에서든 `getprop`으로 읽히고, tradefed 스위트는 로컬 대상(에뮬/Cuttlefish)에 붙여 돌릴 수 있다. 다만 하드웨어에 의존하는 일부 모듈(카메라·센서·TEE 등)은 에뮬에서 스킵되거나 실패할 수 있으니, 관측의 목적은 "구조 이해"에 둔다.

SPL 문자열 읽기와 STS의 실측을 나란히 두면 위협 모델이 눈으로 잡힌다.

```bash
# 기기가 "주장하는" 보안 패치 수준 — 그냥 문자열이다
adb shell getprop ro.build.version.security_patch

# STS는 이 주장을 CVE별 회귀 테스트로 대조한다 (스위트 배포본 필요)
sts-tradefed
sts-tf > run sts --module <CVE 대응 모듈>
```

`예시 출력` — STS 배포본이 없으면 아래처럼 **출력 형식만** 보인다(`N`·`<CVE 대응 모듈>`은 자리표시자). 실증하려면 실제 `run sts` 실행 요약으로 교체하되, CTS(`run cts`) 출력으로 대신하지 마라 — 권한 등 CTS 통과는 보안 패치 적용과 무관하다:

```
$ adb shell getprop ro.build.version.security_patch
2026-11-05

$ sts-tradefed
sts-tf > run sts --module <CVE 대응 모듈>
...
=============== Summary ===============
Passed: N, Failed: 0, Modules Done: 1/1
```

문자열은 `2026-11-05`라고 말하지만, 그 날짜 게시판 수정 가운데 STS가 커버하는(회귀 테스트가 존재하는) CVE에 한해 실적용이 STS 통과로 확인된다. 이 대조가 이 글의 실용적 핵심이다.

> **[그림 2]** `getprop ro.build.version.security_patch` 출력과 **실제 STS 실행**(`sts-tradefed` → `run sts`) 요약을 나란히 둔 대조 캡처 — *실측 스크린샷 자리(CTS 출력으로 대체 금지)*

## Root Cause — 왜 이렇게 되는가

세 스위트가 나뉜 근본 이유는 **책임 주체가 다르기** 때문이다. Android는 계층마다 다른 조직이 코드를 넣는다 — 프레임워크는 Google, 벤더 HAL·커널은 SoC/OEM, 보안 수정은 Google과 벤더가 나눠 진다. 하나의 스위트로 이 셋을 다 검증하려 하면 책임 경계가 뭉개진다.

- CTS는 **앱 개발자를 위한** 보증이다. "이 기기는 CDD를 지킨다"가 성립해야 개발자가 한 번 짠 앱이 여러 기기에서 동작한다. 검증 대상은 프레임워크가 노출하는 동작이다. `Source-confirmed`
- VTS는 **Treble을 위한** 보증이다. Google이 프레임워크를 갱신해도 벤더 파티션을 건드리지 않으려면, 그 경계(VINTF)가 계약대로 지켜져야 한다. 검증 대상은 벤더/프레임워크 인터페이스다. `Source-confirmed`
- STS는 **사용자를 위한** 보증이다. 게시판에 수정이 공개되면 공격자도 그 diff를 본다. 따라서 "SPL 날짜를 올렸다"가 아니라 "그 날짜의 수정이 실제로 들어갔다"를 강제해야 하고, 이는 CVE별 회귀 테스트로만 가능하다. `Source-confirmed`

같은 tradefed 위에 올린 것은 실행·집계·재시도라는 공통 기계가 필요해서지, 검증 대상이 같아서가 아니다. 하네스는 공유하되 신뢰 경계는 분리 — 이게 xTS 설계의 골자다. `Inferred`

## 버전 차이와 한계

- CTS·CDD는 **API 레벨마다** 판본이 다르다. `android-cts-<version>` 배포본은 대상 릴리스와 맞춰야 하며, 상위 API의 CTS로 하위 기기를 검증하면 안 된다. 문서화할 땐 버전을 표기한다. `Source-confirmed`
- STS는 **월간** 게시판을 따라 갱신된다. 스위트에는 동적/엔지니어링 계열 변형이 있어 목적에 따라 고른다(정확한 계열명·구성은 배포본 문서 재확인 필요). `Reported`
- VTS는 Treble 도입(Android 8.0) 이후의 개념이라, 그 이전 기기엔 VINTF 경계 자체가 없다. VTS 배포본의 명칭 규칙도 릴리스에 따라 달라졌다(정확한 바이너리명은 대상 버전 문서 확인 필요). `Reported`
- 한계: 이 스위트들은 **테스트된 항목만** 보증한다. CTS 통과가 "CDD의 모든 MUST 충족"을 뜻하지 않고(객관 테스트 가능한 것만), STS 통과가 "미공개 취약점 없음"을 뜻하지 않는다(게시판에 든 CVE만 회귀 검증). 통과는 하한선이지 안전 증명이 아니다. `Inferred`
- 에뮬레이터 한계: 실제 TEE/StrongBox·특정 하드웨어에 묶인 모듈은 Cuttlefish/AVD에서 완전히 재현되지 않는다 — 구조 학습용으로만 쓰고, 인증 판정은 실기기·공식 절차로 넘긴다.

## 정리

- CTS=호환성(CDD·GMS 관문), VTS=Treble 벤더 경계, STS=보안 패치 실적용. 검증 대상이 서로 겹치지 않는다.
- 셋 다 Trade Federation 위에 서지만, 하네스만 공유할 뿐 신뢰 경계는 분리된다.
- **SPL 문자열은 자기 신고일 뿐, 수정 적용을 증명하는 건 STS의 실측이다** — 이 등식을 혼동하지 말 것.
- 통과는 하한선이지 안전 증명이 아니다. 테스트된 항목만 보증한다.

**점검 질문** — (1) "CTS를 통과했으니 보안 패치가 됐다"가 왜 틀린 추론인가? (2) framework-only OTA가 성립하려면 어느 스위트가 무엇을 보증해야 하는가? (3) `ro.build.version.security_patch` 문자열만으로 기기의 패치 상태를 신뢰할 수 없는 이유는?

**참고** — [CTS](https://source.android.com/docs/compatibility/cts) · [CDD](https://source.android.com/docs/compatibility/cdd) · [VTS](https://source.android.com/docs/core/tests/vts) · [보안 테스트(STS)](https://source.android.com/docs/security/test) · [Trade Federation](https://source.android.com/docs/core/tests/tradefed)

*다음 글: [APEX·Mainline·모듈 업데이트](/posts/android-expert-p2c23/).*
