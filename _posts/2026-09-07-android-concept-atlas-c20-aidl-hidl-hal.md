---
layout: post
title: "Android Security Concept Atlas C20 | 가상 실습 보고서 — AIDL·HIDL·HAL, 프레임워크와 하드웨어의 계약"
date: 2026-09-07 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, HAL, HIDL, AIDL, StableAIDL, VintfStability, hwbinder, vndbinder, Treble, ConceptAtlas, 학습기록]
excerpt: "프레임워크가 카메라·NFC·지문 같은 기기별 하드웨어와 어떻게 대화하는가. HAL은 그 경계이고, HIDL과 AIDL은 그것을 표현하는 두 언어입니다. 예전에는 벤더 C 코드가 프레임워크 프로세스에 dlopen돼 같은 주소 공간·같은 권한으로 돌았지만, Treble이 그것을 별도 프로세스의 버전된 인터페이스로 빼내 격리했습니다. 그리고 'HAL은 hwbinder를 쓴다'는 HIDL에만 맞고, 요즘의 stable AIDL HAL은 앱과 같은 /dev/binder를 씁니다. 이 인터페이스는 빌드 경계가 아니라 신뢰·안정성 경계입니다. Concept Atlas의 스무 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `ls -l /dev/{binder,hwbinder,vndbinder}`, `service list` |
| 관측 결과 | binderfs의 세 Binder 노드와 255개 서비스 등록을 확인했다. |
| 검증 한계 | 벤더 전용 HAL 트랜잭션이나 취약한 서비스 호출은 범용 AVD에 없으므로 공개 인터페이스·소스 분석으로 제한한다. |

![C20 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-binder.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C20 — AIDL·HIDL·HAL
> **계층**: Tier 3 (IPC·프레임워크) · **난이도**: 고급 · **선수 개념**: C17(Binder 드라이버), C31(Treble)
> **성격**: 공식 문서·공개 소스 기준 재검토.

C17에서 Binder 드라이버를, C31에서 Treble이 HAL을 프로세스 밖으로 뺐다는 것을 봤습니다. 이 모듈은 그 **HAL 인터페이스** 자체 — HIDL과 AIDL입니다.

한 문장으로: **HAL은 프레임워크와 기기별 하드웨어/벤더 코드 사이의 경계이고, HIDL·AIDL은 그것을 표현하는 두 언어이며, Treble이 그 경계를 별도 프로세스로 빼내 격리했다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 경계와 두 언어

- **HAL(Hardware Abstraction Layer)**: 프레임워크가 하드웨어와 대화하는 **경계**. 기술이 아니라 개념 — HIDL/AIDL보다 먼저 있었습니다.
- **레거시 HAL**: `hw_module_t` C 구조체를 프레임워크 프로세스에 dlopen(in-process, 격리 없음).
- **HIDL**(Android 8): `.hal` 파일, `android.hardware.<name>@<major>.<minor>`, `/dev/hwbinder` + `hwservicemanager`.
- **Stable AIDL**(Android 11): `.aidl` + `@VintfStability`, `/dev/binder`, 백엔드 Java/NDK/CPP/Rust.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**프레임워크↔벤더/하드웨어 경계**입니다. C31의 Treble이 이 HAL을 별도 프로세스로 빼냈고, 그 통신이 C17의 Binder(정확히는 도메인별 binder) 위에서 돕니다. 이 인터페이스가 곧 C32의 파티션 신뢰 경계의 실체입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **레거시 HAL(pre-Treble)**: 벤더가 `hw_module_t`/`hw_device_t`(`hardware/hardware.h`)를 `.so`로 주면, `hw_get_module()`이 그것을 **프레임워크 프로세스에 직접 dlopen**합니다 — 같은 주소 공간·권한·SELinux 도메인. **격리 없음**.
- **Treble HAL(Android 8+)**: 버전된 IDL 인터페이스를 **별도 벤더 프로세스**가 제공하고 binder로 접근. HAL 크래시/침해가 자기 프로세스/SELinux 도메인에 갇힙니다 — 이게 보안적 이득.
- **두 모드**: **binderized**(별도 프로세스, 기본/Treble 필수) vs **passthrough**(HIDL 생성 `Bs*` 래퍼가 레거시 C++ HAL을 **클라이언트 프로세스 안에** dlopen — 같은 프로세스, **격리 없음**, 마이그레이션 브리지). passthrough는 HIDL 전용이고, **AIDL HAL은 항상 binderized**입니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **인터페이스는 빌드 경계가 아니라 신뢰+안정성 경계입니다.** 벤더 HAL은 별도 프로세스 + SELinux 도메인(C23) + 링커 네임스페이스(C33)에 격리됩니다. `@VintfStability` + **frozen 스냅샷**(`aidl_api/<ver>/`, `.hash`) + VINTF(C31)가 프레임워크/벤더 호환성을 강제합니다.
- **신뢰하면 안 되는 것들**:
  - **"레거시 HAL도 격리된다"** — in-process dlopen이라 프레임워크 권한으로 돕니다.
  - **"passthrough도 binderized 수준으로 격리된다"** — 격리가 **전혀** 없습니다(같은 프로세스).
  - **"HAL은 hwbinder를 쓴다"** — HIDL만입니다. **stable AIDL HAL은 `/dev/binder`**(system libbinder)를 씁니다.
  - **"벤더 HAL은 system libbinder를 링크한다"** — 벤더 코드는 **`libbinder_ndk`(NDK)나 `libbinder_rs`(Rust)**를 링크합니다. CPP `libbinder`는 system/system_ext만.

## 질문 4 — 입력과 출력은 무엇인가

| | HIDL | Stable AIDL |
|--|------|-------------|
| 정의 | `.hal`, `@major.minor`(minor는 append만) | `.aidl`, `@VintfStability` |
| 생성 | `hidl-gen` → C++ | Java/NDK(C++)/CPP/Rust 백엔드 |
| 버전 | 패키지 major.minor | **frozen 스냅샷**(append-only, `.hash` 불일치 시 빌드 실패) |
| 전송 | `/dev/hwbinder` + `hwservicemanager` | `/dev/binder` + `servicemanager` |
| 상태 | 레거시(폐기) | 현행 |

**전송 요약(C17/C31 종합)**: `/dev/binder`(앱·프레임워크·프레임워크向 AIDL HAL) + `servicemanager`; `/dev/hwbinder`(HIDL HAL, 프레임워크↔벤더) + `hwservicemanager`; **`/dev/vndbinder`(벤더↔벤더 AIDL)** + `vndservicemanager`. 셋 다 **같은 binder 드라이버**의 별도 장치.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**HAL 구현은 프레임워크 요청을 파싱하고 하드웨어를 모는 벤더 코드라 실제 공격 표면입니다** — binder로 닿습니다. 생성된 stub이 공격자 영향 Parcel을 역직렬화하고(C18), HAL은 종종 커널 드라이버까지 몹니다(C36). 그러나 **binderized면** 그 침해가 HAL의 프로세스/SELinux 도메인에 **갇힙니다**(C31/C32) — 레거시 in-process HAL이라면 프레임워크 권한으로 번졌을 것을. 그리고 **Rust/NDK 백엔드**는 메모리 안전 HAL을 가능하게 해 이 공격면을 좁힙니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **HAL 개념**: pre-Treble부터(레거시 C).
- **HIDL**: Android 8.0(Treble).
- **Stable AIDL for HALs**: Android 11.
- **HIDL 폐기 타임라인(정밀하게)**: 공식 폐기 **공지는 Android 10**("HIDL is deprecated, has been replaced by AIDL"), HAL용 stable AIDL은 **11**에 등장, 신규 HIDL 사실상 중단은 **~12/13**, 신규 칩셋의 HIDL 금지(하드 컷오프)는 **Android 15 VSR**(2024 칩셋). 그래서 "HIDL이 13에서 폐기"는 거친 요약입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `lshal`(HAL 인스턴스와 transport(hwbinder/passthrough/binder)·interface@version), `service list`(AIDL 서비스), `dumpsys -l`.
- **소스**: `source.android.com/docs/core/architecture/{hidl,aidl/aidl-hals,hal/hal-types}`, AOSP `system/tools/{hidl,aidl}`, `hardware/interfaces`(실제 HAL 정의).

**주의**: 에뮬레이터는 소프트웨어/디폴트 HAL 구현을 제공합니다(실제 벤더 HAL 아님).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C17(Binder 드라이버)**: HIDL/AIDL이 그 위에서 돕니다(hwbinder/binder).
- **C31(Treble)**: HAL을 프로세스 밖으로 뺀 본체이자, VINTF가 호환성을 강제.
- **C18(Parcel)**: 생성된 stub이 Parcel을 역직렬화 — 공격자 입력의 진입점.
- **C33(링커 네임스페이스)**: 벤더 HAL 라이브러리 격리.
- **C36(벤더 드라이버·HAL 공격 표면, 예정)**: HAL이 왜 큰 공격 표면인지 상세.
- 다음은 **C36(벤더 드라이버·HAL 공격 표면)** 또는 **C19(servicemanager)**로 이어집니다.

## 호출 흐름

```
[ 레거시 vs Treble HAL — 격리의 차이 ]

레거시:  프레임워크 프로세스 ─dlopen→ 벤더 HAL(.so)  (같은 주소공간·권한, 격리 X)

Treble(binderized):
  프레임워크 ──binder──▶ 벤더 HAL 프로세스(별도 SELinux 도메인, 링커 네임스페이스)
     │  HIDL: /dev/hwbinder + hwservicemanager
     │  stable AIDL: /dev/binder + servicemanager (백엔드 NDK/Rust)
     └─ 침해는 HAL 도메인에 갇힘(레거시라면 프레임워크로 번짐)

passthrough(HIDL 마이그레이션): 프레임워크 ─Bs*래퍼→ 레거시 HAL (같은 프로세스, 격리 X)
```

## 실측으로 확인한 것

전용 `codex-atlas-api33` AVD(Android 13/API 33, Google APIs x86_64)에서 이 모듈의 전송·등록 주장을 실제 명령으로 확인했다. 벤더 전용 HAL 트랜잭션은 범용 AVD에 없으므로, 격리 구조는 공식 소스·문서 근거까지 짚는다.

**1) 세 binder 도메인은 같은 드라이버의 별개 장치 노드로 실재한다.** 검증 블록의 명령이 세 노드를 모두 반환했다.

```console
$ ls -l /dev/{binder,hwbinder,vndbinder}
```

`/dev/binder`·`/dev/hwbinder`·`/dev/vndbinder`가 binderfs에 세 노드로 함께 존재한다는 것이 관측 결과("binderfs의 세 Binder 노드")로 확인된다. 이것이 질문 4·질문 3의 물리적 전제다 — "HAL은 hwbinder를 쓴다"는 HIDL(hwbinder)에만 맞고, stable AIDL HAL의 전송(`/dev/binder`)과 벤더↔벤더(`/dev/vndbinder`)는 별개 도메인으로 같은 드라이버 위에 나뉘어 있다.

**2) AIDL/Binder 서비스는 `/dev/binder` + servicemanager에 등록되어 열거된다.**

```console
$ service list
```

255개 서비스 등록이 관측됐다. 이들은 `/dev/binder` 도메인의 servicemanager가 관장하는 AIDL/Binder 서비스이며(질문 4의 전송 행), 프레임워크向 AIDL이 앱과 같은 `/dev/binder`를 쓴다는 주장을 서비스 열거 수준에서 확증한다. 상단 스크린샷(`evidence-binder.png`)과 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 원시 출력을 보존했다.

**3) 레거시 in-process HAL과 binderized HAL의 격리 차이는 소스로 확정된다.** 이 AVD엔 실제 벤더 HAL이 없어 트랜잭션을 재현하진 못하지만, 레거시 경로가 `hw_get_module()`로 벤더 `.so`를 **호출 프로세스에 dlopen**한다는 것(같은 주소 공간·권한, 격리 없음)과 Treble binderized HAL이 별도 프로세스·SELinux 도메인에서 도는 이득은 AOSP `hardware/libhardware`(`hardware/hardware.h`)와 AIDL/HIDL HAL 공식 문서로 확정된다 — 질문 2·3의 신뢰 경계 서술의 근거다.

## 가상환경 검증 한계

정직하게, 이 문서의 새 캡처는 세 binder 노드 존재와 서비스 열거까지다. 하드웨어·벤더 의존 항목은 근거는 확정했으나 이 x86_64 AVD 세션에서 새로 측정하지 않았다.

- **실제 벤더 HAL의 transport(`lshal`)와 HIDL/AIDL 혼재는 측정하지 않았다.** 범용 AVD는 소프트웨어/디폴트 HAL만 제공하므로, 특정 OEM 기기의 hwbinder 잔존이나 HAL별 transport는 이 환경 밖이다(검증 블록의 "벤더 전용 HAL 트랜잭션 없음"과 일치).
- **binderized HAL의 별도 SELinux 도메인·링커 네임스페이스 격리는 `ls -Z`로 직접 확인하지 않았다.** 실제 벤더 HAL 프로세스가 없어 passthrough 대비 격리를 프로세스 수준에서 관측하지 못했고, 소스·문서 근거까지만 짚었다.
- **하드웨어 backed HAL(TEE/StrongBox keymaster 등)은 에뮬레이터라 소프트웨어 폴백이며, ARM64 PAC/BTI/MTE 같은 하드웨어 완화는 x86_64 AVD라 관측되지 않는다.** 메모리 안전 Rust/NDK 백엔드 HAL의 실 벤더 구현도 이 이미지엔 없다.

관련 근거: [AIDL HALs](https://source.android.com/docs/core/architecture/aidl/aidl-hals) · [HIDL](https://source.android.com/docs/core/architecture/hidl) · [HAL types](https://source.android.com/docs/core/architecture/hal/hal-types) · [VINTF](https://source.android.com/docs/core/architecture/vintf)

## 마치며

HAL은 프레임워크와 하드웨어 사이의 경계이고, HIDL·AIDL은 그것을 표현하는 두 언어입니다. Treble이 그 경계를 프로세스 밖으로 빼내(binderized) 벤더 코드의 침해를 자기 도메인에 가뒀고 — 레거시 in-process HAL이라면 프레임워크 권한으로 번졌을 것을 — Google은 HIDL(hwbinder)에서 stable AIDL(/dev/binder, Rust/NDK 백엔드)로 통합하며 메모리 안전 HAL로 가고 있습니다. 이 인터페이스는 빌드 경계가 아니라 신뢰·안정성 경계이고, `@VintfStability`+frozen+VINTF가 프레임워크/벤더 호환성을 강제합니다. 다음은 이 HAL이 왜 여전히 큰 공격 표면인지(커널 도달)를 다루는 **C36(벤더 드라이버·HAL 공격 표면)**, 또는 **C19(servicemanager)**로 이어집니다.
