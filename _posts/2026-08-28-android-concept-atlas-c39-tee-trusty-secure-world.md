---
layout: post
title: "Android Security Concept Atlas C39 | 가상 실습 보고서 — TEE·Trusty·시큐어 월드, 같은 코어 위의 두 세계"
date: 2026-08-28 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, TrustZone, TEE, Trusty, SecureWorld, SMC, TZASC, GlobalPlatform, KeyMint, Gatekeeper, WidevineL1, pKVM, AVF, ConceptAtlas, 학습기록]
excerpt: "TrustZone의 보안 상태, EL3 monitor, TEE OS와 trusted application의 역할을 구분하고 공유 메모리·SMC·memory controller가 만드는 경계를 공개 Arm·Trusty 자료로 검토합니다."
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

![C39 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C39 — TEE·Trusty·시큐어 월드(TrustZone)
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 연구 · **선수 개념**: C05(예외 수준; 시큐어/논시큐어 축·EL3 모니터·SMC), C27(부트로더·init)
> **성격**: 공식 문서·공개 소스 기준 재검토. C40(Keystore)의 선수이자 형제 모듈 — KeyMint TA가 사는 곳입니다.
> **완료 기준**: SMC 한 번이 노멀 월드에서 시큐어 월드로 넘어가는 경로와, 그 격리를 강제하는 하드웨어를 설명할 수 있다.

시큐어/논시큐어 상태는 EL0–EL3 특권 수준과 구분해 이해해야 합니다. 이 글은 EL3 monitor, TEE OS와 trusted application의 역할을 나누고, hardware-backed KeyMint가 어떤 신뢰 경계 안에서 동작하는지 살펴봅니다.

한 문장으로: **하나의 물리적 코어가 두 세계를 시분할하고, 그 격리는 모니터 소프트웨어가 아니라 하드웨어(버스의 NS 비트·메모리 컨트롤러)가 강제한다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 두 세계와 그 문

- **시큐어 월드 / 논시큐어 월드**: TrustZone이 만드는 두 실행 상태. EL과 직교하는 별개의 축(`SCR_EL3.NS`).
- **TEE (Trusted Execution Environment)**: Rich OS와 분리된 실행 환경으로, 정해진 위협 모델 안에서 trusted code와 data의 기밀성·무결성을 보호하도록 설계됩니다. 실제 보장은 TEE와 SoC 구현 및 취약점 상태에 달려 있습니다.
- **S-EL0 / S-EL1**: 트러스티드 앱(트러스트릿)이 S-EL0, TEE OS가 S-EL1. (S-EL2는 `FEAT_SEL2`/Armv8.4에서만.)
- **EL3 시큐어 모니터**: 보통 Trusted Firmware-A의 BL31. `SCR_EL3`를 소유하고 월드 전환을 수행하는 **문**. TEE OS(S-EL1)나 TA(S-EL0)가 **아닙니다**.
- **Trusty**: Google의 오픈소스 TEE OS(AOSP `external/trusty`). 벤더는 QSEE/QTEE·Kinibi·TEEGRIS·OP-TEE로 대체할 수 있습니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**시큐어 월드**입니다. C05의 시큐어/논시큐어 축의 안쪽이고, 하드웨어 격리된 신뢰 실행 환경입니다. 여기에 **KeyMint(C40)·Gatekeeper(C41)·생체 매처·Widevine L1 DRM**이 삽니다. 그리고 이 TEE의 이미지 자체는 부팅 체인이 검증합니다 — 단, 뒤에서 보듯 그것은 AVB(C28)가 아니라 EL3 앞단 펌웨어(TF-A)의 몫입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

두 세계는 EL과 직교합니다.

```
  논시큐어(Normal World)          │  시큐어(Secure World)
  ──────────────────────────────┼──────────────────────────────
  EL0  앱                        │  S-EL0  트러스티드 앱(TA)
  EL1  Linux 커널                │  S-EL1  TEE OS (Trusty/QSEE/Kinibi/OP-TEE)
  EL2  하이퍼바이저(pKVM)         │  S-EL2  (FEAT_SEL2/v8.4 에서만)
  ────────────  EL3  시큐어 모니터(TF-A BL31)  ────────────
                SMC 로 진입, SCR_EL3.NS 뒤집어 월드 전환
```

**월드 전환**: 논시큐어 `SMC` 명령이 EL3로 트랩 → 모니터가 나가는 세계의 상태를 저장하고 들어오는 세계의 상태를 복원 → `SCR_EL3.NS`를 뒤집고 `ERET`로 다른 세계로. **하나의 물리적 코어**가 두 세계를 시분할합니다 — 별도의 "시큐어 CPU"는 없습니다(별도 칩은 StrongBox 얘기, C40).

한 가지 정밀함: **EL3는 시큐어 모니터를 돌리지 TEE가 아니지만, 아키텍처상 "축 밖"에 있는 것도 아닙니다.** pre-RME(현재 모든 Android SoC)에서 EL3는 **항상 시큐어 상태**로 실행되고, `SCR_EL3.NS`는 EL3 **아래** 층(EL0–EL2)의 보안 상태를 정합니다. (Armv9.2의 `FEAT_RME`/CCA에서만 EL3가 별도의 Root 상태로 옮겨갑니다.) 그리고 `SMC`는 EL3로 들어가는 유일한 **동기적 명령**이지 유일한 진입은 아닙니다 — `SCR_EL3` 라우팅으로 FIQ/IRQ/SError도 EL3에 들어갑니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **격리는 하드웨어가 강제합니다(모니터 소프트웨어가 아니라).** 모든 AMBA 버스 트랜잭션은 **NS 비트**(`AxPROT[1]`)를 싣고, 코어가 자기 보안 상태에서 이 비트를 구동합니다. **TZASC/TZC**(예: Arm TZC-400)가 DRAM을 시큐어/논시큐어 영역으로 분할해 각 트랜잭션의 NS 비트를 검사하고, **TZPC**가 주변장치를 게이팅합니다. 모니터는 상태 전환만 할 뿐, 매 접근 검사는 안 합니다. (이 TZASC 검사는 CPU MMU/stage-2와 **별개**라, CPU뿐 아니라 GPU·DMA 마스터까지 전부 걸립니다.)
- **핵심 비대칭**: **시큐어 월드는 논시큐어 메모리를 볼 수 있지만, 논시큐어 월드는 시큐어 메모리를 볼 수 없습니다.** 그래서 커널이 TEE 비밀을 못 읽지만, TEE는 클라이언트가 넘긴 노멀 월드 버퍼를 읽습니다 — 설계입니다.
- **신뢰하면 안 되는 것들**:
  - **"TEE는 별도 CPU/칩에서 돈다"** — TrustZone은 CPU 확장, 같은 코어 시분할. 별도 칩은 StrongBox.
  - **"EL3 = 시큐어 월드"** — EL3는 모니터(문). TEE OS는 S-EL1, TA는 S-EL0.
  - **"TA 코드가 특별히 하드닝돼서 안전"** — **위치** 때문에 안전합니다. 같은 코드가 노멀 월드에 있으면 이 보호가 전혀 없습니다.
  - **"검증한 공유 버퍼는 믿어도 된다"** — 공유 버퍼는 노멀 월드에 매핑된 채 쓰기 가능이라, 검사 후 내용이 바뀔 수 있습니다(**TOCTOU**). TA는 시큐어 메모리로 **복사한 뒤** 검증·사용해야 합니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 노멀 월드 클라이언트의 요청. **제어는 SMC**(EL3 경유 월드 전환), **데이터는 공유 메모리**(노멀 월드에 매핑된 명령 버퍼). Trusty는 명명 포트에 `tipc`로 연결합니다.
- **출력**: 연산 결과만. 비밀(키·생체 템플릿·PIN)은 절대 나오지 않고, 대신 서명된 **HardwareAuthToken**이나 서명 같은 결과가 나옵니다.

표준 API는 **GlobalPlatform**이 정의합니다 — TA용 **TEE Internal Core API**, 클라이언트용 **TEE Client API** — 그리고 OP-TEE·여러 벤더 TEE가 이를 구현합니다. **Trusty는 자체 네이티브 API와 `tipc`**를 쓰지 GlobalPlatform TEE는 아닙니다(둘을 섞지 않도록).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**TEE는 고가치·고특권 공격 표면입니다.** 층으로 봅니다.

- **첫 발판 = TA(S-EL0)의 메모리 안전 버그.** 파서·메시지 핸들러가 노멀 월드가 통제하는 바이트를 처음 만나는 자리라 여기가 주 진입점입니다.
- **S-EL0 → S-EL1 상승**: TA↔OS syscall 인터페이스를 통해 TEE OS로. 그 **S-EL1 TEE OS는 시큐어 자원에 대해 노멀 월드 EL1 커널보다 상위**입니다 — 시큐어 메모리는 커널에게 안 보이지만, TEE OS는 노멀 DRAM을 직접 읽습니다.
- **S-EL1 → EL3 상승**: S-EL1이 SMC로 부르는 EL3 모니터(TF-A의 SMC 디스패처/SPD)에 버그가 있으면 **양쪽 세계 위의 전-플랫폼 장악**.

실제 TrustZone 익스 대다수의 근본 원인이 **TA/TEE OS가 노멀 월드 포인터나 길이를 믿는 것**, 또는 TOCTOU(검사 후 노멀 월드가 공유 버퍼를 바꿈)입니다. 이건 제 CVE 시리즈의 결과 겹칩니다 — 8편 블루투스가 "네트워크에서 온 길이 필드를 산술에 그대로" 쓴 것, 9편 Parcel의 write/read 불일치가, 여기서는 **시큐어 월드 경계**에서 벌어지는 것입니다. 신뢰 경계만 바뀌었을 뿐 형태는 같습니다.

**파급(blast radius)**: 특정 TEE가 침해되면 그 TEE가 제공하던 KeyMint·Gatekeeper·DRM service의 보장이 약해질 수 있습니다. StrongBox는 TEE와 다른 security level 및 격리 요구사항을 가지므로 같은 TEE 결함의 직접 영향에서 분리될 수 있지만, **전체 SoC 침해에도 반드시 안전하다고 단정할 수는 없습니다.** 평가는 실제 구현과 공격 경로를 기준으로 해야 합니다.

## 질문 6 — Android/ARM 버전에 따라 무엇이 달라졌는가

- **FEAT_SEL2 (Armv8.4)**: 시큐어 하이퍼바이저 S-EL2 — 없으면 시큐어 월드는 S-EL1/S-EL0뿐.
- **FEAT_RME / Arm CCA (Armv9.2)**: NS 1비트를 **2비트 보안 공간**(Secure/Non-secure/Realm/Root)으로 일반화, EL3는 Root 상태로. 신규·비주류 — 클래식 TrustZone은 1비트 모델입니다.
- **pKVM / AVF (Android 13)**: 대안 격리 도메인(질문 8).
- **KeyMint (Android 12)**: TA가 구현하는 HAL 개명(C40).
- **Trusty-in-a-VM**: Trusty를 시큐어 월드가 아니라 pVM 게스트로 돌리는 신규 배치 — "Trusty ⇒ TrustZone"이 더는 안전한 추론이 아님.

그리고 기기마다 TEE 벤더가 다릅니다: Pixel은 Trusty, 다수 Exynos는 Kinibi/TEEGRIS, Qualcomm은 QSEE/QTEE, 그 외 OP-TEE. "Android의 TEE"라고 뭉뚱그리지 말고 **그 기기의 실제 TEE를 특정**해야 합니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

노멀 월드에선 시큐어 메모리를 못 봅니다. 하지만 **어떤 TEE인지**는 식별할 수 있습니다.

- `KeyStore` attestation의 `securityLevel`이 `TRUSTED_ENVIRONMENT`면 TEE 백업(C40 절차).
- 빌드 props: `ro.hardware.keystore`·`ro.hardware.gatekeeper`.
- Linux 드라이버/노드: `/dev/trusty-ipc-dev0`(Trusty) vs `/dev/tee0`(OP-TEE), `dmesg | grep -iE "trusty|optee"`.

**주의: 에뮬레이터에는 진짜 시큐어 월드가 없습니다**(attestation은 `SOFTWARE`).

**소스**
- `source.android.com/docs/security/features/trusty`, AOSP `external/trusty`(LK 유래 커널, `lib/tipc`), Android 커널 `drivers/trusty`
- Trusted Firmware-A(EL3 BL31, SMC 디스패처/SPD, Trusted Board Boot)
- Arm ARM(`SCR_EL3`·보안 상태·SMC), AMBA AXI 명세(`AxPROT[1]`), Arm CoreLink **TZC-400** TRM, GlobalPlatform TEE 명세
- pKVM/AVF: `source.android.com/docs/core/virtualization`

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C05(시큐어/논시큐어 축·EL3·SMC)**: 그 축의 **안쪽**이 이 모듈입니다. C05가 문(EL3)을 세웠다면 여기는 문 너머의 방(S-EL1/S-EL0)입니다.
- **C40(Keystore)**: "커널을 따도 못 빼내는 키"의 그 키가 사는 곳이 여기 KeyMint TA(S-EL0)입니다. StrongBox가 왜 TEE와 다른지도 여기서 분명해집니다.
- **C28(Verified Boot)**: TEE 이미지도 부팅에 검증되지만, 정확히는 **AVB가 아니라 TF-A의 BL2가 Trusted Board Boot로 BL31(EL3 모니터)·BL32(TEE OS)를 ROTPK에 대해 검증**합니다. AVB는 노멀 월드 vbmeta를, 이쪽은 펌웨어 단계가 — **같은 신뢰의 뿌리에 걸린 다른 검증자**입니다.
- **C41(Gatekeeper·생체)**: PIN 검증·지문 매칭을 하는 TA가 여기 살고, 비밀이 아니라 서명된 토큰만 경계를 넘습니다.
- **C37(하드닝)**: TA도 메모리 안전·하드닝의 대상입니다 — 시큐어 월드라고 버그가 없는 게 아닙니다.
- 다음은 **C41(Gatekeeper·Weaver·생체)** 또는 **C42(attestation·신뢰의 뿌리)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

두 개를 손으로 그려 보시길 권합니다.

```
[ 월드 전환 — 같은 코어, SMC 한 번 ]

논시큐어 EL1 (커널)  ──SMC──▶  EL3 (TF-A 모니터)
                                 │  나가는 세계 상태 저장
                                 │  SCR_EL3.NS = 0
                                 │  들어오는 세계 상태 복원 → ERET
                                 ▼
                          시큐어 S-EL1 (TEE OS)
                                 ... 일 처리 ...
                          ──SMC(복귀)──▶ EL3 → SCR_EL3.NS = 1 → 논시큐어로
```

```
[ 노멀 클라이언트가 TA 를 부르는 길 ]

앱/HAL (EL0)
   │ /dev/trusty-ipc-dev0 (tipc, 명명 포트)
   ▼
Linux trusty 드라이버 (EL1)  ── 제어는 SMC, 데이터는 공유 메모리
   │ SMC → EL3(TF-A) → 월드 전환
   ▼
Trusty OS (S-EL1)  ──▶  대상 TA (S-EL0, 예: KeyMint)
   │  TA 는 공유 버퍼를 "복사 후 검증"(TOCTOU 방지)
   ◀── 결과만 반환 (비밀은 안 나옴)

  ── 격리 강제: 버스의 NS 비트 · TZASC(DRAM) · TZPC(주변장치) ──
  ── 시큐어→논시큐어 읽기 O, 논시큐어→시큐어 읽기 X (비대칭) ──
```

## 오개념 판별 문제 5개

각 문장이 왜 틀렸는지 한 줄로 반박해 보세요.

1. "TEE는 별도의 시큐어 CPU/칩에서 돌아간다."
2. "시큐어 월드는 EL3다(또는 EL3가 시큐어 월드다)."
3. "격리는 EL3 모니터 소프트웨어가 강제한다."
4. "두 세계는 대칭으로 서로의 메모리를 못 본다 / 한 번 검증한 공유 버퍼는 믿어도 된다."
5. "StrongBox 키는 TEE 안에 있어, TEE를 뚫으면 StrongBox 키도 얻는다."

<details><summary>판정 기준(펼치기)</summary>

1. TrustZone은 CPU 확장으로 **하나의 물리적 코어**가 두 세계를 시분할합니다(SMC→EL3). 별도 칩은 TrustZone이 아니라 StrongBox/별도 보안 요소입니다.
2. EL3는 **시큐어 모니터**(월드 전환의 문)입니다. TEE OS는 S-EL1, TA는 S-EL0. (EL3는 시큐어 상태로 실행되지만 TEE 스택은 아니고, `SCR_EL3.NS`는 EL3 아래 층의 상태를 정합니다.)
3. 하드웨어가 강제합니다 — 버스의 NS 비트, TZASC(DRAM), TZPC(주변장치). 모니터는 상태 전환만 합니다.
4. **비대칭**입니다: 시큐어는 논시큐어 메모리를 읽지만 역은 불가. 그리고 공유 버퍼는 노멀 월드에 매핑된 채라 검사 후 바뀔 수 있어(TOCTOU), TA는 **복사한 뒤** 검증해야 합니다.
5. StrongBox는 TrustZone TA가 아니라 AP와 격리된 **별도 보안 프로세서**입니다. TEE(S-EL1)·EL3 침해로 닿지 않습니다.
</details>

## 실측으로 확인한 것

이 모듈은 하드웨어 전용 개념이라 x86_64 AVD가 직접 캡처할 수 있는 표면은 좁다. 그래도 이 세션의 검증 블록이 실제로 확증한 지점이 있고, 나머지 경계는 공개 소스로 추적했다.

**1) 이 AVD에는 진짜 시큐어 월드가 없고, 키는 소프트웨어에 있다.** `codex-atlas-api33`(Android 13, x86_64)에서 AndroidKeyStore EC 키를 만들고 attestation challenge를 걸어 `KeyInfo`와 인증서 체인을 조회한 결과, 키의 보안 수준이 정확히 `SOFTWARE(0)`였다.

```console
# AndroidKeyStore EC 키 생성 → attestation challenge → KeyInfo 조회
KeyInfo.getSecurityLevel() → SOFTWARE (0)
attestation certificate chain length = 3
```

이 결과가 질문 7의 불변식을 그대로 확증한다 — "에뮬레이터에는 진짜 시큐어 월드가 없고, attestation은 `SOFTWARE`로 떨어진다." securityLevel이 `TRUSTED_ENVIRONMENT`였다면 그 키가 TEE(S-EL0의 KeyMint TA) 뒤에 있다는 뜻이지만, 이 AVD는 그 값을 만들지 못했다. 상단 스크린샷(`evidence-keystore.png`)이 보여주는 SOFTWARE는 "TEE가 있는데 접근이 막힌 것"이 아니라 "TrustZone이 애초에 없어 소프트웨어로 폴백한 것"이다.

**2) attestation 체인은 생성됐지만 하드웨어 신뢰의 뿌리에 걸려 있지 않다.** 인증서 체인 길이 3은 challenge→`KeyInfo`→체인 조회 흐름 자체는 끝까지 동작했음을 뜻한다. 그러나 그 체인이 증언하는 보안 수준이 SOFTWARE인 이상, 이 체인은 하드웨어 ROT가 아니라 에뮬레이터 소프트웨어 키에 뿌리를 둔다 — 질문 6·C42가 말하는 "신뢰의 뿌리"가 여기서는 물리 하드웨어가 아님을 확인한다.

**3) 하드웨어가 강제하는 격리는 소스로만 추적했다.** 월드 전환(SMC→EL3, `SCR_EL3.NS` 토글)·TZASC의 DRAM 분할·`tipc` 명명 포트 같은 경계는 x86_64에서 실행되지 않으므로, 질문 2·3의 호출 경계는 AOSP `external/trusty`와 Trusted Firmware-A의 공개 소스, Arm 아키텍처 문서로만 확인했고 이 AVD에서 측정하지는 않았다.

## 가상환경 검증 한계

정직하게, 이 문서가 새로 캡처한 실측은 (1)·(2)의 KeyStore 결과까지다. 하드웨어 전용 속성은 근거는 확정했으나 이 x86_64 AVD 세션에서 관측하지 못했다.

- **ARM64 시큐어 월드와 EL3의 하드웨어 강제는 측정하지 못했다.** x86_64 AVD에는 TrustZone이 없어 SMC 월드 전환, `SCR_EL3.NS` 토글, TZASC/TZPC의 버스 NS 비트 검사, 시큐어→논시큐어 비대칭 읽기를 이 세션에서 관측할 수 없었다. 이 경계들은 공개 소스·문서로만 확인했다.
- **하드웨어 TEE·StrongBox·Weaver는 소프트웨어 폴백으로 떨어졌다.** 물리 보안 하드웨어가 없는 AVD라 securityLevel이 `SOFTWARE`가 됐고, `TRUSTED_ENVIRONMENT`/StrongBox 경로와 `/dev/trusty-ipc-dev0`·`/dev/tee0`·`ro.hardware.keystore` 같은 실제 TEE 벤더 식별 신호는 이 AVD에서 나오지 않았다.
- **라이브 익스 경로는 재현하지 않았다.** TA(S-EL0) 파서의 메모리 안전 버그, 공유 버퍼 TOCTOU, S-EL0→S-EL1→EL3 상승 같은 시큐어 월드 공격 흐름은 실제 TEE와 대상 기기에서만 성립하므로 이 세션에서 재현하지 않았다.

관련 근거: [Android Trusty TEE](https://source.android.com/docs/security/features/trusty) · [KeyInfo (securityLevel)](https://developer.android.com/reference/android/security/keystore/KeyInfo) · [Android Virtualization Framework](https://source.android.com/docs/core/virtualization)

## 마치며

C05가 "시큐어/논시큐어는 EL과 직교한다"였다면, C39는 그 시큐어 월드의 안쪽입니다 — 하나의 코어가 SMC 한 번으로 두 세계를 오가고, 격리를 강제하는 것은 모니터가 아니라 버스의 NS 비트·TZASC·TZPC라는 하드웨어이며, 신뢰는 비대칭입니다(시큐어는 노멀을 보지만 역은 불가). 그 안에 KeyMint(C40)·Gatekeeper(C41)·Widevine L1이 살고, 그들의 안전은 **코드가 특별해서가 아니라 위치 때문**입니다.

공유 memory와 command parser는 TEE가 Rich OS의 입력을 받는 핵심 신뢰 경계입니다. pointer·length 검증이나 copy-before-use가 빠지면 memory safety와 TOCTOU 문제가 생길 수 있습니다. StrongBox는 별도 security level로 평가하되 실제 구현과 공격 경로를 확인하지 않고 생존 여부를 단정하지 않습니다. 다음은 **C41(Gatekeeper·Weaver·생체)**와 **C42(key attestation)**로 이어집니다.
