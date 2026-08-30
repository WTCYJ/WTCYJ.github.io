---
layout: post
title: "Android Security Concept Atlas C32 | 가상 실습 보고서 — system·vendor·product·odm의 신뢰 관계"
date: 2026-09-05 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Partitions, Treble, coredomain, VendorInterface, TrustBoundary, SELinux, AVB, ConceptAtlas, 학습기록]
excerpt: "한 기기 안의 파티션들은 서로 다른 주체가 만들고 서명합니다 - system은 Google/OEM, vendor는 SoC 벤더, odm은 기기 통합자. 그래서 '한 기기니 다 같은 신뢰'가 아니라, 파티션마다 신뢰 수준과 방향이 다릅니다. 프레임워크는 벤더 입력을 OS 무결성에 대해 맹신하면 안 되고, 벤더는 프레임워크 내부에 닿지 못하며, 둘 사이의 유일한 인가된 통로가 벤더 인터페이스입니다. 이 신뢰 지도가 SELinux 도메인·링커 네임스페이스·체인 vbmeta로 어떻게 강제되는지 정리합니다. Concept Atlas의 열여덟 번째 모듈입니다."
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

![C32 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C32 — system/vendor/product/odm 신뢰 관계
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 중급 · **선수 개념**: C31(Treble), C23(SELinux plat/vendor), C28(chained vbmeta), C33(링커 네임스페이스)
> **성격**: 보완/종합 편. 앞 네 모듈의 신뢰 경계를 하나의 지도로 묶습니다.

C31이 프레임워크와 벤더를 **갈랐다**면, C32는 그 갈라진 조각들이 서로 **무엇을 신뢰하고 무엇을 신뢰하면 안 되는가**입니다. 새 메커니즘을 도입하기보다, C23·C28·C31·C33에서 이미 본 강제 층들을 **하나의 신뢰 지도**로 종합합니다.

한 문장으로: **한 기기의 파티션들은 서로 다른 주체가 서명하므로 신뢰 수준과 방향이 다르고, 프레임워크↔벤더 사이의 유일한 인가된 통로가 벤더 인터페이스다.**

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

파티션들의 **신뢰 지도**입니다. Domain 2(부팅·업데이트)의 마지막 조각으로, C31의 분리를 신뢰 관계로 읽습니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가 (누가 무엇을 소유하는가)

| 파티션 | 저자·서명 | 담는 것 |
|--------|----------|---------|
| **system** | AOSP/Google·OEM | 프레임워크(플랫폼) |
| **system_ext** (11) | 파트너 | 프레임워크 확장(system의 오염 방지) |
| **product** (9) | OEM/캐리어 | 제품·캐리어 특화 |
| **vendor** | SoC 벤더 | HAL 구현·드라이버 |
| **odm** | ODM/기기 통합자 | 기기별 오버레이(vendor 위) |

**한 기기니 다 같은 신뢰가 아닙니다** — 파티션마다 다른 서명자, 다른 SELinux 도메인, 다른 vbmeta 키(C28)입니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

**신뢰는 방향성 비대칭입니다.**

- **프레임워크(system)는 벤더 입력을 OS 무결성에 대해 맹신하면 안 됩니다.** 벤더가 넘긴 데이터·포인터·길이는 검증 대상입니다(C39 TEE의 "노멀 월드 입력을 적대적으로"와 같은 결).
- **벤더는 프레임워크 내부에 닿지 못합니다.** 링커 네임스페이스(C33)가 벤더 `.so`를 사설 프레임워크 라이브러리에서 격리하고, SELinux(C23)가 `coredomain`(플랫폼 도메인)과 벤더 도메인 사이의 **직접 IPC를 neverallow로 금지**합니다 — 오직 **안정 인터페이스**(hwbinder/vndbinder, HAL)로만.
- **유일한 인가된 통로는 벤더 인터페이스**(VINTF, C31)입니다.
- **신뢰하면 안 되는 것들**: "파티션이 한 기기니 서로 완전히 신뢰"(다른 서명자·도메인), "vendor는 안전"(커널에 도달하는 드라이버/HAL은 큰 공격 표면 — C36).

## 질문 4 — 입력과 출력은 무엇인가

**객체가 사는 파티션이 그것의 저자·신뢰 수준의 신호입니다.** SELinux 타입(라벨)·AVB 디스크립터·서명자가 파티션에 대응합니다. 그래서 "이 바이너리가 어느 파티션에 있나"가 곧 "누가 만들고 누가 보증하나"입니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **침해된 벤더 HAL**은 자기 SELinux 도메인과 링커 네임스페이스에 갇혀 프레임워크로 번지지 않습니다 — Treble이 만든 안정 경계를 따라 봉쇄가 **강제 가능**해졌습니다.
- **그러나 벤더 드라이버/HAL은 커널에 도달하는 큰 공격 표면**입니다(C36에서 상세). 벤더 코드의 결함이 EL0→EL1 상승의 진입점이 될 수 있습니다.
- **confused deputy**: 벤더가 프레임워크의 신뢰를 악용하려는 것을, 안정 인터페이스와 caller 검사(C22)가 제한합니다.
- **과특권 product/system_ext**: 프레임워크 확장이 과도한 권한을 가지면 신뢰 표면이 넓어집니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

`/product`(9), `/system_ext`(11), 그리고 chained vbmeta·plat/vendor 정책·VNDK는 모두 Treble(8.0)에서 시작했습니다(C31·C23·C28). dynamic partitions(10, C30)가 이 파티션들을 논리 파티션으로 유연화했습니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ls -Z /system /vendor /product /odm /system_ext`(파티션별 SELinux 타입), `cat /proc/mounts`(파티션 마운트).
- `sepolicy-analyze <policy> attribute coredomain`(플랫폼 도메인 집합), 벤더 도메인과의 neverallow(C23).
- `avbtool info_image`로 vbmeta_system / vbmeta_vendor의 **별도 키·롤백 슬롯**(C28), `lshal`로 벤더 HAL(C31).
- **소스**: `source.android.com/docs/core/architecture/partitions`, C23·C28·C31·C33 문서.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C31(Treble)**: 이 파티션 분리의 본체.
- **C23(SELinux)**: `coredomain` vs 벤더 도메인, neverallow가 직접 IPC를 막는 정책 강제.
- **C28(Verified Boot)**: chained vbmeta가 파티션별 키로 독립 서명 — 파티션 신뢰의 암호학적 앵커.
- **C33(링커 네임스페이스)**: 벤더 라이브러리 격리의 네이티브 강제.
- **C36(벤더 드라이버·HAL 공격 표면, 예정)**: vendor가 왜 큰 공격 표면인지.
- 다음은 **C36(벤더 드라이버·HAL 공격 표면)** 또는 커널 티어로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 파티션 신뢰 지도 — 누가 서명하고, 무엇으로 격리되나 ]

  system / system_ext / product         vendor / odm
  (Google·OEM·파트너 서명)              (SoC·ODM 서명)
  coredomain(SELinux)                   vendor 도메인
  시스템 링커 네임스페이스               벤더 네임스페이스(VNDK)
  vbmeta_system(플랫폼 키)              vbmeta_vendor(벤더 키)
        │                                    │
        └──── 안정 인터페이스로만 대화 ───────┘
              (hwbinder/vndbinder · HAL · VINTF)
              neverallow: coredomain ↔ vendor 직접 IPC 금지
        │                                    │
   프레임워크는 벤더 입력을 검증(맹신 X)   벤더는 프레임워크 내부에 못 닿음
```

## 오개념 판별 문제 5개

1. "한 기기의 모든 파티션은 같은 주체가 서명하므로 서로 완전히 신뢰한다."
2. "프레임워크는 자기 기기의 벤더 HAL이 준 데이터를 검증 없이 믿어도 된다."
3. "벤더 코드는 프레임워크의 사설 라이브러리를 자유롭게 dlopen할 수 있다."
4. "vendor 파티션은 벤더가 만든 것이니 프레임워크만큼 안전하다."
5. "system과 vendor의 무결성은 하나의 vbmeta·하나의 키로 검증된다."

<details><summary>판정 기준(펼치기)</summary>

1. system=Google/OEM, vendor=SoC, odm=ODM 등 **다른 주체가 서명**하고 다른 SELinux 도메인·다른 vbmeta 키를 가집니다.
2. 프레임워크는 벤더 입력을 OS 무결성에 대해 **검증**해야 합니다. 안정 인터페이스를 넘어온 것도 신뢰 경계를 넘은 데이터입니다.
3. 링커 네임스페이스(C33)가 벤더를 격리해 사설 프레임워크 라이브러리를 **물리적으로 못 닿게** 합니다. 허용된 VNDK/LL-NDK만.
4. vendor 드라이버/HAL은 커널에 도달하는 **큰 공격 표면**입니다(C36). 갇히긴 하지만 안전과는 다릅니다.
5. chained vbmeta로 **파티션별 별도 키·별도 롤백 슬롯**(C28)입니다 — vbmeta_system과 vbmeta_vendor는 서로 다른 서명자.
</details>

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, Android 13/API 33, x86_64)에서 이 모듈이 전제하는 **파티션 분리**가 이 기기에서 실제로 켜져 있음을 확인했고, 그 분리를 신뢰 경계로 강제하는 세 층의 근거는 AOSP 소스로 확정했다.

**1) Treble이 활성 → system/vendor 파티션 분리가 이 기기의 실제 상태다.** 검증 블록에 기록한 대로, 아래 속성 조회가 Treble/APEX 활성을 반환했다.

```console
$ adb shell getprop ro.treble.enabled
$ adb shell getprop ro.apex.updatable
```

Treble이 켜져 있다는 것은 질문 1·2의 전제 — 프레임워크(system)와 벤더가 별도 파티션·별도 서명자·별도 SELinux 도메인으로 갈린다는 분리 — 가 이 기기에서 개념이 아니라 실물 상태로 존재한다는 뜻이다. `ro.apex.updatable` 활성은 시스템 구성요소가 APEX 모듈 단위로 독립 서명·업데이트된다는, 같은 "파티션이 곧 저자·신뢰의 신호"(질문 4) 원리의 연장이다.

**2) `/data`는 별도 암호화 상태를 가진다.** `mount`와 FBE 속성 조회가 `/data`의 file-based encryption(`file`, `encrypted`)을 보여줬다 — 상단 검증 화면과 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 보존한 값이다. 한 기기 안에서도 저장 영역마다 보호 상태가 균일하지 않다는, 질문 3의 "신뢰는 균일하지 않고 방향이 있다"를 저장소 측에서 확인해 주는 관측이다.

**3) 신뢰 지도를 강제하는 세 층은 AOSP 소스로 확정했다.** 이 AVD가 AVB·정책 덤프를 노출하지 않아 이 세션의 실측 캡처는 (1)·(2)까지지만, 질문 3·6·7이 든 강제 메커니즘 자체는 소스에 명시돼 있다: `coredomain`↔벤더 도메인의 직접 IPC를 막는 SELinux neverallow(C23), 벤더 라이브러리를 사설 프레임워크 라이브러리에서 격리하는 링커 네임스페이스·VNDK(C33), 파티션마다 다른 키로 독립 서명하는 chained vbmeta(C28). Treble 활성(1)은 이 세 층이 실제로 놓일 분리 구조가 이 기기에 존재함을 뒷받침한다.

## 가상환경 검증 한계

정직하게, 이 문서의 실측 캡처는 (1)·(2)까지다. 파티션 신뢰의 암호학적·정책적 앵커는 이 x86_64 Google APIs AVD 세션에서 새로 캡처하지 못했다.

- **AVB 상태와 A/B 슬롯 속성을 이 AVD가 노출하지 않았다.** 그래서 `avbtool info_image`로 vbmeta_system과 vbmeta_vendor가 서로 다른 키로 체인됨을 이 세션에서 실물 덤프로 대조하지는 못했다 — 근거는 C28·AOSP Verified Boot 문서로 확정한 상태다.
- **하드웨어 롤백 퓨즈와 부트 ROM은 검증 범위 밖이다.** 실제 롤백 인덱스 소비와 부트 ROM의 1차 서명 검증은 에뮬레이터가 아니라 실기기·SoC의 영역이라 이 세션에서 관측하지 않았다.
- **파티션별 `ls -Z` 타입 대조와 coredomain↔vendor neverallow 덤프도 이 세션에서 새로 뜨지 않았다.** x86_64 에뮬레이터 정책이 실기기 벤더 정책과 동일하다는 보장이 없어, 정책 강제의 근거는 AOSP sepolicy 소스 쪽으로 확정해 두었다.

관련 근거: [AOSP Partitions overview](https://source.android.com/docs/core/architecture/partitions) · [Android Verified Boot](https://source.android.com/docs/security/features/verifiedboot) · [SELinux for Android](https://source.android.com/docs/security/features/selinux) · [VNDK / linker namespaces](https://source.android.com/docs/core/architecture/vndk)

## 마치며

한 기기 안이라도 파티션들은 서로 다른 주체가 만들고 서명하므로, 신뢰는 균일하지 않고 **방향이 있습니다** — 프레임워크는 벤더 입력을 검증하고, 벤더는 프레임워크 내부에 닿지 못하며, 둘 사이의 유일한 통로가 벤더 인터페이스입니다. 그리고 그 신뢰 지도는 세 층으로 동시에 강제됩니다: SELinux 도메인(C23), 링커 네임스페이스(C33), 체인 vbmeta(C28). 봉쇄된 벤더 HAL이라도 커널에 도달하는 코드라 큰 공격 표면으로 남는데, 그건 다음 커널 티어에서 다룹니다. 이로써 **부팅·업데이트 체인(Domain 2)이 C27·C28·C29·C30·C31·C32로 닫혀** 갑니다(C29 롤백 심화만 남음).
