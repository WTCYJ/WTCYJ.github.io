---
layout: post
title: "Android Security Concept Atlas C32 | 가상 실습 보고서 — system·vendor·product·odm의 신뢰 관계"
date: 2026-09-05 21:00:00 +0900
category: Android
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

## 서술형 문제 3개

1. 파티션마다 다른 서명자·SELinux 도메인·vbmeta 키를 가진다는 것이 "신뢰 방향의 비대칭"으로 어떻게 이어지는지 서술하세요.
2. `coredomain`과 벤더 도메인 사이의 직접 IPC를 막는 neverallow(C23)와 링커 네임스페이스(C33)가 함께 어떻게 벤더 인터페이스를 **유일한 통로**로 만드는지 서술하세요.
3. 봉쇄된 벤더 HAL이 그럼에도 왜 위험한 공격 표면인지(커널 도달)를 서술하세요.

## 소스·정적 검증 경로

- Cuttlefish에서 `ls -Z`로 `/system`·`/vendor`·`/product`·`/odm`의 SELinux type을 비교하고, host-side `sepolicy-analyze`로 `coredomain`과 vendor domain의 경계 및 neverallow를 확인하세요.
- `avbtool info_image`로 vbmeta_system과 vbmeta_vendor가 **서로 다른 키**로 체인됨을 확인하세요(C28 절차).
- 이 세 층(SELinux·링커·AVB)이 같은 프레임워크/벤더 선을 어떻게 강제하는지 근거와 함께 정리하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. C23·C28·C31·C33의 실측을 **하나의 신뢰 지도**로 엮는 종합 편입니다. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **파티션별 라벨**: `ls -Z`로 파티션마다 다른 SELinux 타입을 실측.
2. **정책 경계**: `sepolicy-analyze`로 coredomain↔vendor neverallow를 캡처.
3. **서명 분리**: `avbtool info_image`로 vbmeta_system/vendor의 별도 키를 대조.
4. **종합 서술**: 세 층이 같은 프레임워크/벤더 선을 강제함을 하나의 그림(실측 출력 기반)으로.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

한 기기 안이라도 파티션들은 서로 다른 주체가 만들고 서명하므로, 신뢰는 균일하지 않고 **방향이 있습니다** — 프레임워크는 벤더 입력을 검증하고, 벤더는 프레임워크 내부에 닿지 못하며, 둘 사이의 유일한 통로가 벤더 인터페이스입니다. 그리고 그 신뢰 지도는 세 층으로 동시에 강제됩니다: SELinux 도메인(C23), 링커 네임스페이스(C33), 체인 vbmeta(C28). 봉쇄된 벤더 HAL이라도 커널에 도달하는 코드라 큰 공격 표면으로 남는데, 그건 다음 커널 티어에서 다룹니다. 이로써 **부팅·업데이트 체인(Domain 2)이 C27·C28·C29·C30·C31·C32로 닫혀** 갑니다(C29 롤백 심화만 남음).
