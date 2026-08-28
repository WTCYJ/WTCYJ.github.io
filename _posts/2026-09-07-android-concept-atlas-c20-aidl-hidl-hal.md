---
layout: post
title: "Android Security Concept Atlas C20 | 가상 실습 보고서 — AIDL·HIDL·HAL, 프레임워크와 하드웨어의 계약"
date: 2026-09-07 21:00:00 +0900
category: 블로그/기술문서
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

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "레거시 conventional HAL도 별도 프로세스에서 격리되어 돈다."
2. "passthrough HAL은 binderized HAL과 같은 수준의 격리를 준다."
3. "Android의 HAL은 앱 IPC와 다른 hwbinder를 쓴다."
4. "벤더 HAL 코드는 system의 libbinder(CPP)를 링크한다."
5. "HIDL은 Android 13에서 폐기됐다."

<details><summary>판정 기준(펼치기)</summary>

1. 레거시 HAL은 `hw_get_module()`이 프레임워크 프로세스에 **dlopen**합니다 — 같은 주소 공간·권한, 격리 없음. Treble binderized만 별도 프로세스입니다.
2. passthrough는 레거시 C++ HAL을 클라이언트 프로세스에 dlopen하는 **마이그레이션 브리지**로 격리가 **전혀** 없습니다.
3. HIDL만 `/dev/hwbinder`입니다. **stable AIDL HAL은 앱과 같은 `/dev/binder`**(system libbinder)를 씁니다. `/dev/vndbinder`는 벤더↔벤더용입니다.
4. 벤더 코드는 **`libbinder_ndk`(NDK)나 `libbinder_rs`(Rust)**를 링크합니다. CPP `libbinder`는 system/system_ext만.
5. 공식 폐기 **공지는 Android 10**입니다. 13은 "신규 HIDL 중단"의 별개 마일스톤이고, 신규 칩셋 하드 금지는 **A15 VSR**입니다.
</details>

## 서술형 문제 3개

1. 레거시 in-process HAL과 Treble binderized HAL의 격리 차이가 왜 보안적 이득인지(메모리 손상이 프레임워크 권한으로 번지느냐)를 서술하세요.
2. "HAL은 hwbinder를 쓴다"가 왜 HIDL에만 맞고 stable AIDL엔 틀린지, 세 binder 도메인(binder/hwbinder/vndbinder)의 용도를 구분해 서술하세요.
3. `@VintfStability` + frozen 스냅샷 + VINTF가 함께 어떻게 "업데이트된 프레임워크와 옛 벤더 HAL의 호환성"을 강제하는지 서술하세요.

## 소스·정적 검증 경로

- Cuttlefish에서 `lshal`과 `service list`를 사용해 제공되는 HAL/service instance를 확인하고, AOSP의 VINTF manifest와 `.hal`/`.aidl` 정의를 대조하세요. 특정 OEM HAL은 이 환경의 범위 밖입니다.
- `service list`로 AIDL 서비스를, `hardware/interfaces`(AOSP)에서 특정 HAL의 `.hal`/`.aidl` 정의를 대조하세요.
- 이 기기가 hwbinder를 여전히 쓰는 HIDL HAL을 가졌는지(레거시 잔존) 근거와 함께 판정하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **HAL 목록·transport**: `lshal` 출력으로 HIDL/AIDL 혼재와 transport를 캡처.
2. **인터페이스 정의**: `hardware/interfaces`의 `.hal`/`.aidl` 하나를 골라 버전·메서드를 서술.
3. **격리 서술**: binderized HAL이 별도 SELinux 도메인에 있음을 `ls -Z`/lshal로, passthrough와 대비.
4. **전송 도메인**: 이 기기의 /dev/binder·hwbinder·vndbinder 사용을 C17 실측과 연결.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

HAL은 프레임워크와 하드웨어 사이의 경계이고, HIDL·AIDL은 그것을 표현하는 두 언어입니다. Treble이 그 경계를 프로세스 밖으로 빼내(binderized) 벤더 코드의 침해를 자기 도메인에 가뒀고 — 레거시 in-process HAL이라면 프레임워크 권한으로 번졌을 것을 — Google은 HIDL(hwbinder)에서 stable AIDL(/dev/binder, Rust/NDK 백엔드)로 통합하며 메모리 안전 HAL로 가고 있습니다. 이 인터페이스는 빌드 경계가 아니라 신뢰·안정성 경계이고, `@VintfStability`+frozen+VINTF가 프레임워크/벤더 호환성을 강제합니다. 다음은 이 HAL이 왜 여전히 큰 공격 표면인지(커널 도달)를 다루는 **C36(벤더 드라이버·HAL 공격 표면)**, 또는 **C19(servicemanager)**로 이어집니다.
