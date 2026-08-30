---
layout: post
title: "Android Security Concept Atlas C31 | 가상 실습 보고서 — Treble·GSI·Mainline·APEX, 프레임워크와 벤더를 가르다"
date: 2026-09-04 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ProjectTreble, VINTF, VNDK, HIDL, AIDL, GSI, Mainline, APEX, apexd, ConceptAtlas, 학습기록]
excerpt: "왜 어떤 Android 보안 패치는 OEM 업데이트를 기다리지 않고 Play를 통해 바로 오는가. Project Treble이 프레임워크(/system)와 벤더 구현(/vendor)을 안정된 인터페이스로 갈라 프레임워크만 따로 업데이트할 수 있게 했고, Mainline은 미디어·ART·conscrypt 같은 핵심 부품을 APEX 모듈로 만들어 Google이 플릿 전체를 직접 패치하게 했습니다. 그리고 그 벤더 인터페이스는 빌드 경계가 아니라 신뢰 경계입니다 - 벤더 HAL은 자기 SELinux 도메인과 링커 네임스페이스에 갇힙니다. 제가 CVE 시리즈에서 본 패치 갭을 줄인 구조입니다. Concept Atlas의 열일곱 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `getprop ro.treble.enabled`, `getprop ro.apex.updatable`, `mount`, FBE 속성 |
| 관측 결과 | Treble/APEX 활성화와 `/data`의 file-based encryption(`file`, `encrypted`)을 확인했다. |
| 검증 한계 | 이 Google APIs AVD는 AVB 상태·A/B 슬롯 속성을 노출하지 않았다. 실제 하드웨어 롤백 퓨즈와 부트 ROM은 검증 범위 밖이다. |

![C31 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C31 — Treble·GSI·Mainline·APEX
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 중급 · **선수 개념**: C30(dynamic partitions), C23(SELinux 분할), C33(링커 네임스페이스)
> **성격**: 공식 문서·공개 소스 기준 재검토. 여러 앞 모듈이 참조하던 "플랫폼/벤더 분리"의 본체.

C23에서 SELinux가 plat/vendor로 나뉜다고, C33에서 링커 네임스페이스가 벤더 라이브러리를 가둔다고, C28에서 vbmeta가 체인 파티션으로 위임된다고 했습니다. 이 모듈이 그 모든 분리의 **본체** — Project Treble입니다.

한 문장으로: **프레임워크(/system)와 벤더 구현(/vendor)을 안정된 인터페이스로 갈라 프레임워크만 따로 업데이트하게 하고, Mainline은 핵심 부품을 APEX 모듈로 만들어 Google이 플릿 전체를 직접 패치하게 한다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 프레임워크와 벤더의 계약

- **Project Treble(Android 8.0)**: OS 프레임워크와 벤더/SoC 구현을 안정된 **벤더 인터페이스**로 분리.
- **VINTF**: 벤더 매니페스트(제공)와 프레임워크 호환성 행렬(요구)을 대조해 호환성 강제.
- **HAL**: 프레임워크에 dlopen되던 공유 라이브러리 → 별도 프로세스의 버전된 인터페이스(HIDL → AIDL).
- **GSI(Generic System Image)**: 순수 AOSP `/system` 이미지. Treble 기기의 `/vendor` 위에서 부팅 → 컴플라이언스 검증용.
- **Mainline / APEX**: 핵심 OS 부품을 Google Play로 업데이트하는 모듈 / 그 컨테이너 형식.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**업데이트 속도를 위한 재설계**입니다. 프레임워크가 벤더 내부에 의존하지 않게 해서, OEM이 SoC 벤더의 재포팅 없이 프레임워크만 업데이트할 수 있게 했습니다. 그리고 이 분리가 C23(SELinux plat/vendor), C33(링커 네임스페이스), C30(dynamic partitions), C28(chained vbmeta)로 층마다 표현됩니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **프레임워크(/system, /product(9), /system_ext(11))** vs **벤더(/vendor, /odm)**가 VINTF 경계로 갈립니다. `/vendor`=SoC 벤더 HAL·드라이버, `/odm`=ODM 기기별 오버레이.
- **HAL은 별도 프로세스**입니다. HIDL(8.0, `/dev/hwbinder`, `hwservicemanager`) → 안정 AIDL(11, 일반 binder + 벤더간은 `/dev/vndbinder`, 일반 `servicemanager`). HIDL은 13에서 폐기.
- **Mainline**: Google Play 시스템 업데이트가 모듈을 배포. **APEX**는 `apexd`가 부팅 시 `/apex`에 **읽기전용**으로 마운트.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **벤더 인터페이스는 빌드 경계가 아니라 신뢰 경계입니다.** VINTF(매니페스트=제공 vs 호환성 행렬=요구)가 빌드·부팅 시 호환성을 강제합니다. 침해되거나 버그 있는 벤더 HAL은 자기 **SELinux 도메인**(C23)과 제한된 **링커 네임스페이스**(C33)에 갇혀, 프레임워크로 번지지 못합니다.
- **VNDK**: 벤더가 링크할 수 있는 안정 시스템 네이티브 라이브러리 집합. 링커 네임스페이스로 강제되어, 벤더 바이너리가 사설 프레임워크 라이브러리를 물리적으로 dlopen하지 못합니다. (Treble과 함께 8.0에 개념 도입, 9에서 강제, **15에서 폐기** → LL-NDK/안정 AIDL로.)
- **신뢰하면 안 되는 것들**: "Treble = 8.0 실행 모든 기기"(**런치** 기기만 의무, 업그레이드 기기는 면제), "HAL은 여전히 공유 라이브러리"(별도 프로세스), "HIDL이 현역"(AIDL로 이전, 13 폐기), "GSI = 데일리 ROM"(컴플라이언스 도구), "VTS는 GSI가 필요하다"(아니오 — VTS는 **기기 자체 빌드**로 벤더 인터페이스를 검사; GSI가 필요한 건 **CTS-on-GSI**).

## 질문 4 — 입력과 출력은 무엇인가

- **Treble(개념적)**: 입력 = 프레임워크 이미지 + 벤더 이미지. 출력 = VINTF 호환성 통과 시 부팅(불일치면 실패).
- **Mainline**: 입력 = Play가 배포한 모듈(**APK 또는 APEX**). 출력 = APK는 일반 패키지로, **APEX는 `/apex`에 읽기전용 마운트**(스테이징 후 재부팅에 활성화).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**Mainline/APEX의 보안적 요점**: 미디어 코덱·conscrypt·ART 같은 보안 핵심 부품을 **OEM OTA 없이 플릿 전체에** 패치합니다 — 제가 CVE 시리즈에서 본 그 **패치 갭**을 줄인 구조입니다. APEX는 서명(AVB 페이로드 서명 + APK v3 서명)되고, 페이로드가 dm-verity로 검증되며, **읽기전용** 마운트에 **롤백 방지**가 걸립니다. 그래서 로그(rogue) APEX나 다운그레이드는 서명+롤백이 막습니다.

**벤더 인터페이스의 봉쇄**: 벤더 HAL 버그는 그 HAL의 도메인/네임스페이스에 갇혀 프레임워크로 번지지 않습니다. 안정된 경계를 따라 봉쇄가 **강제 가능**해진 것이 Treble의 보안적 기여입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 8.0 | **Treble**, HIDL HAL, VNDK 개념 |
| Android 9 | `/product` 파티션, VNDK 강제, **GSI 컴플라이언스**(CTS-on-GSI) |
| Android 10 | **Mainline·APEX·DSU·dynamic partitions**(C30) |
| Android 11 | `/system_ext` 파티션, **안정 AIDL HAL** |
| Android 12 | **ART가 업데이트 모듈**(`com.android.art`) |
| Android 13 | HIDL **폐기**(신규 HAL은 AIDL) |
| Android 15 | VNDK **폐기** |

ART 관련 APEX는 10에서 `com.android.runtime`, 12부터 `com.android.art`. 그 외 미디어·conscrypt·tzdata·statsd·**rkpd(C42)** 등이 모듈입니다. Permission Controller 등은 APK로, runtime/tzdata/statsd 등은 APEX로 — **APEX는 앱 실행 전에 필요하거나 네이티브 내용(라이브러리·바이너리)을 담는** 부품용입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ls /apex`(마운트된 모듈), `pm list packages --apex-only`, `cmd apexservice`.
- `lshal`(HAL 인스턴스와 transport — **hwbinder**(HIDL binderized)·**passthrough**(in-process HIDL)·**binder**(AIDL)).
- `cat /vendor/etc/vintf/manifest.xml`(벤더 제공), `getprop ro.build.flavor`(GSI 여부), `getprop ro.apex.*`.
- **소스**: `source.android.com/docs/core/architecture/{vintf,hidl,aidl,vndk}`, `.../tests/vts`, `.../ota/modular-system`.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C23(SELinux)**: Treble이 정책을 plat/vendor로 나눈 것 — 같은 분리의 정책 층 표현.
- **C33(링커 네임스페이스)**: VNDK를 강제하는 네이티브 층 — 벤더 `.so`가 사설 프레임워크 라이브러리에 못 닿게.
- **C30(dynamic partitions)**: 이 여러 파티션을 실용적으로 리사이즈 가능하게 만든 것.
- **C28(Verified Boot)**: chained vbmeta(vbmeta_system/vbmeta_vendor)가 파티션별 키로 독립 서명 — Treble의 서명 층.
- **C42(rkpd)**: RKP 데몬이 업데이트 가능한 APEX입니다.
- **CVE 시리즈**: Mainline이 그 패치 갭을 줄였습니다.
- 다음은 이 파티션들의 **신뢰 관계**를 정리하는 **C32**로 이어집니다.

## 호출 흐름

```
[ Treble 의 프레임워크/벤더 분리와 그 층별 강제 ]

  /system (프레임워크, Google/OEM)        /vendor + /odm (SoC/ODM)
        │                                      │
        └──────── VINTF 경계 ──────────────────┘
           매니페스트(제공) vs 호환성 행렬(요구) → 빌드·부팅 시 검사
        │                                      │
   강제되는 층:
     · SELinux: plat 정책      ┃  vendor 정책        (C23)
     · 링커: 시스템 네임스페이스 ┃ 벤더 네임스페이스(VNDK) (C33)
     · AVB: vbmeta_system      ┃ vbmeta_vendor(별도 키)  (C28)
     · HAL: AIDL over binder   ┃ /dev/vndbinder (벤더간)

[ Mainline: OEM OTA 를 건너뛰는 패치 ]

Google Play 시스템 업데이트 → 모듈(APK 또는 APEX)
   │ APEX 면: 스테이징 → 재부팅 시 apexd 가 /apex 에 읽기전용 마운트
   │          (AVB+APK 서명 · dm-verity · 롤백 방지)
   ▼
미디어·ART·conscrypt·rkpd 등이 OEM 없이 플릿 전체 패치 → 패치 갭 축소
```

## 실측으로 확인한 것

가상 실습 환경(codex-atlas-api33 AVD · Android 13/API 33 · Google APIs x86_64)에서 이 모듈의 핵심 경계 두 가지를, 검증 블록에 기록한 속성 조회로 실제 확인했다.

**1) 이 부팅 이미지에서 Treble 벤더 인터페이스가 실제로 켜져 있다.** 프레임워크/벤더 분리는 이 글의 개념이 아니라 이 이미지의 속성으로 관측된다.

```console
$ getprop ro.treble.enabled
$ getprop ro.apex.updatable
```

두 속성 모두 활성(참) 값을 돌려줬고, 이것이 검증 블록의 "Treble/APEX 활성화 … 확인했다"는 관측 결과의 근거다. `ro.treble.enabled`가 참이라는 것은 이 AVD의 `/system`과 `/vendor`가 질문 1~3에서 말한 VINTF 경계로 분리된 채 부팅했다는 뜻 — 질문 3의 "벤더 인터페이스는 빌드 경계가 아니라 신뢰 경계"라는 불변식이 부팅한 이미지 수준에서 성립함을 확인한다.

**2) APEX가 갱신 가능한 형태로 활성화되어 있다.** `ro.apex.updatable`가 참이므로, 이 이미지의 `/apex` 모듈들은 질문 2·5의 Mainline 경로(스테이징 후 재부팅에 활성화, 읽기전용 마운트)로 갱신될 수 있는 형식이다. 원시 출력은 상단 스크린샷(`evidence-boot.png`)과 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 보존했다.

**3) `/data`가 file-based encryption으로 마운트되어 있다.** 같은 세션의 `mount` 조회에서 `/data`가 `file`·`encrypted` 옵션으로 올라온 것을 확인했다 — Treble이 가른 파티션들이 실제로 각자의 속성대로 마운트되어 부팅한다는 것을 보여주는 부수 관측이다.

## 가상환경 검증 한계

정직하게, 이 세션의 실측은 위 세 가지(속성·마운트 관측)까지다. 나머지는 근거는 공개 소스로 확정했으나 이 x86_64 Google APIs AVD가 새로 캡처하지는 못했다.

- **AVB 상태와 A/B 슬롯 속성은 이 AVD가 노출하지 않았다.** 검증 블록에 적었듯 이 Google APIs 이미지는 vbmeta·슬롯 속성을 제공하지 않아, APEX 페이로드의 dm-verity 검증과 vbmeta 체인(C28)은 이 세션에서 관측되지 않았다.
- **APEX 롤백 방지와 하드웨어 롤백 퓨즈는 재현하지 않았다.** 서명 실패·다운그레이드가 실제로 거부되는 경로는 부트 ROM·퓨즈 영역이라 에뮬레이터 검증 범위 밖이다.
- **`lshal`·`/apex` 목록·VINTF 매니페스트의 라이브 덤프는 이 세션에 포함하지 않았다.** HIDL/AIDL transport 혼재와 벤더 매니페스트(제공)/호환성 행렬(요구) 구조는 개념과 공개 소스로만 다뤘고, 이 AVD에서 새로 캡처하지는 않았다.

관련 근거: [VINTF (Treble 호환성)](https://source.android.com/docs/core/architecture/vintf) · [Modular System / Mainline](https://source.android.com/docs/core/ota/modular-system) · [VNDK](https://source.android.com/docs/core/architecture/vndk)

## 마치며

Project Treble은 프레임워크와 벤더를 안정된 인터페이스로 갈라 "OEM이 SoC 재포팅 없이 프레임워크만 업데이트"를 가능하게 했고, 그 분리는 SELinux(C23)·링커 네임스페이스(C33)·AVB(C28)·파티션(C30)으로 층마다 강제됩니다. Mainline은 한 걸음 더 나아가, 미디어·ART·conscrypt 같은 핵심 부품을 APEX 모듈로 만들어 **Google이 플릿 전체를 OEM OTA 없이 직접 패치**하게 했습니다 — 제가 CVE 시리즈에서 마주한 패치 갭을 구조적으로 줄인 것입니다. 다음은 이 파티션들이 서로 **무엇을 신뢰하고 무엇을 신뢰하면 안 되는가**를 정리하는 **C32**로 이어집니다.
