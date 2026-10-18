---
layout: post
title: "HAL·VINTF·VTS"
date: 2026-11-28 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, HAL, VINTF, VTS, Treble]
excerpt: "HAL은 커널 드라이버가 아니라 유저스페이스 서비스다. VINTF '호환성 실패'는 하드웨어 고장이 아니라 매니페스트와 매트릭스의 버전 불일치이고, lshal의 declared와 served는 서로 다른 뜻이다."
---

Android에서 프레임워크와 벤더(칩셋 제조사) 코드는 서로 다른 팀·다른 업데이트 주기·다른 신뢰 도메인에서 만들어진다. 이 둘을 갈라놓고, 그럼에도 같은 기기에서 맞물려 돌게 만드는 계약이 **HAL**(Hardware Abstraction Layer)이다. 그리고 "이 프레임워크 이미지와 이 벤더 이미지가 정말 호환되는가"를 부팅 전에 판정하는 장치가 **VINTF**(Vendor Interface), 벤더 구현이 그 계약을 지키는지 검사하는 도구가 **VTS**(Vendor Test Suite)다. 세 개는 Project Treble 이후 프레임워크/벤더 분리를 떠받치는 한 세트다.

이 글은 HAL이 프로세스·SELinux 도메인 경계를 넘어 어떻게 앉는지, VINTF가 매니페스트와 호환성 매트릭스를 어떻게 대조하는지, VTS가 무엇을 보장하는지를 AOSP 문서와 Cuttlefish 관측으로 정리한 기록이다. 공격 실습이 아니라 **구조와 신뢰 경계**를 읽는 데 초점을 둔다.

> **한 줄 결론**: HAL은 벤더 도메인에서 도는 유저스페이스 Binder 서비스이고, VINTF는 "기기 매니페스트(제공) ⟷ 프레임워크 호환성 매트릭스(요구)"를 양방향 대조해 부팅 전에 호환성을 판정한다. 여기서 갈리는 것은 하드웨어가 아니라 **버전 계약**이다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 세 가지다. (1) HAL의 종류(binderized vs passthrough)와 프레임워크↔벤더 통신 경로, (2) VINTF 객체가 대조하는 매니페스트/호환성 매트릭스의 구조와 위치, (3) VTS가 검증하는 대상. 익스플로잇이나 벤더 이미지 개조는 다루지 않는다.

선수 지식이 두 개 깔린다. 바로 앞 15장에서 다룬 **Stable AIDL**을 알아야 한다 — 요즘 신규 HAL은 HIDL이 아니라 안정 AIDL로 정의되기 때문이다. 그리고 14장의 **Binder proxy/stub·thread pool**을 알아야 한다 — HAL 호출은 결국 Binder 트랜잭션이고, 프레임워크 프로세스에서 벤더 프로세스로 넘어가는 IPC이기 때문이다. SELinux 도메인 개념(뒤의 19장, Atlas의 SELinux 항목)도 배경으로 얕게 깔린다.

전체 구조에서 HAL·VINTF·VTS는 **App→Framework→Binder→system_server→HAL→Kernel** 흐름의 아래쪽 두 칸을 잇는 이음매다. system_server(와 다른 프레임워크 서비스)가 Binder로 HAL을 부르고, HAL이 커널 드라이버를 두드린다. HAL은 그 사이의 유저스페이스 계층이지 커널이 아니다.

## 핵심 개념 — HAL의 종류와 통신 경로

가장 흔한 오개념부터 짚자. **HAL은 커널 드라이버가 아니다.** HAL은 커널 드라이버 위에 앉는 유저스페이스 라이브러리 또는 서비스이고, `ioctl` 같은 저수준 접근을 감싸 프레임워크에 안정된 인터페이스로 노출한다. `Source-confirmed`

HAL은 크게 세 갈래다.

| 유형 | 로딩 방식 | 프로세스 | 인터페이스 정의 | 상태 |
|--|--|--|--|--|
| Binderized (AIDL) | 별도 서비스, Binder로 통신 | 벤더 프로세스(분리) | 안정 AIDL | 신규 표준 |
| Binderized (HIDL) | 별도 서비스, hwbinder로 통신 | 벤더 프로세스(분리) | HIDL(`.hal`) | 동결·유지보수 |
| Passthrough (HIDL) | 클라이언트 프로세스에 `.so`로 dlopen | 호출자와 동일 | HIDL | 레거시 |

핵심은 **binderized HAL은 별도 프로세스에서 돈다**는 점이다. 프레임워크가 HAL을 Binder로 부르면 트랜잭션이 프로세스 경계를 넘어 벤더 프로세스로 간다. 그래서 HAL이 크래시해도 `system_server`가 같이 죽지 않는다(격리). 반대로 passthrough HAL은 호출자 프로세스 안으로 `dlopen`되므로 이 격리가 없다 — 그래서 레거시로 밀려났다. `Source-confirmed`

통신 채널도 유형마다 다르다. HIDL binderized는 `hwbinder`(`/dev/hwbinder`)를 쓰고 이름은 `hwservicemanager`가 관리한다. 반면 **프레임워크가 소비하는 AIDL HAL은 프레임워크와 동일한 메인 `servicemanager`(`/dev/binder`)에 등록**되어야 `system_server` 등 프레임워크 프로세스에서 조회·도달할 수 있다. `Source-confirmed`

여기서 `/dev/vndbinder`·`vndservicemanager`는 헷갈리기 쉬운 별개의 채널이다. 이 둘은 **프레임워크에 노출하지 않는 벤더↔벤더 내부 AIDL 통신 전용**이며, SELinux `neverallow` 규칙이 프레임워크(`system_server`)의 `vndbinder` 접근을 차단한다. 따라서 프레임워크가 소비하는 HAL을 `vndbinder`에만 등록하면 `servicemanager`가 그 이름을 볼 수 없어 애초에 도달이 불가능하다 — 프레임워크용 AIDL HAL이 메인 `servicemanager`에 올라가야 하는 이유다. `Inferred`

> **[그림 1]** Cuttlefish에서 `adb shell lshal`을 실행해 HAL 인터페이스 목록과 각 항목의 transport(hwbinder/passthrough)·server PID·`(declared, served)` 상태를 보여주는 터미널 — *실측 스크린샷 자리*

여기서 두 번째 함정 — `lshal` 출력의 **`declared`와 `served`는 다른 뜻**이다. `declared`는 VINTF 매니페스트에 "이 기기가 제공한다"고 적혀 있다는 뜻이고, `served`는 실제로 그 서비스가 지금 등록되어 살아 있다는 뜻이다. 선언만 되고 아직 안 뜬(lazy) HAL, 혹은 떴는데 매니페스트에 없는 HAL을 이 두 라벨로 구분한다. "lshal에 안 보이니 그 HAL이 없다"는 성급한 결론은 여기서 틀린다. `Source-confirmed`

## 신뢰 경계와 위협 모델

HAL은 **프레임워크(system) 도메인과 벤더 도메인이 만나는 Binder 신뢰 경계**다. 두 쪽 다 특권이 있지만 SELinux 도메인이 다르고, 서로를 무조건 신뢰하지 않는 것이 Treble의 전제다.

위협 모델에서 중요한 사실은, HAL이 **공격자 영향을 받는 데이터를 파싱**한다는 점이다. 미디어 코덱, 라디오(RIL), NFC, GNSS, 카메라, 센서 — 앱이 프레임워크를 거쳐 흘려보낸 데이터, 혹은 네트워크·라디오에서 들어온 데이터가 벤더 HAL의 파서에 도달한다. HAL 파서에 메모리 손상 버그가 있으면 벤더 도메인에서의 권한 상승으로 이어질 수 있다 — 실제로 벤더 미디어·카메라 HAL 계열은 월간 보안 게시판의 단골이다. `Reported`

방어는 두 층이다. 첫째, binderized HAL은 별도 프로세스이므로 침해가 나도 그 벤더 도메인 안에 갇힌다(프레임워크 프로세스로 즉시 번지지 않는다). 둘째, 각 HAL 프로세스는 자기 몫의 SELinux 벤더 도메인에서 돌아 접근할 수 있는 자원이 최소화된다. `Inferred` 이 격리가 "HAL 하나의 버그 = 기기 완전 장악"을 막는 완충이다.

주의할 것은 **여기서 다루는 것은 어디까지나 관측**이라는 점이다. Cuttlefish/에뮬레이터의 벤더 파티션을 읽어 구조를 이해하는 것이지, 실기기 벤더 이미지를 개조하거나 HAL을 무기화하는 것이 아니다.

## 관측 — VINTF 호환성과 lshal

Cuttlefish(또는 벤더 파티션이 있는 이미지)에서 안전하게 관측할 수 있는 것은 두 가지다: 실제로 뜬 HAL 목록(`lshal`)과, VINTF가 대조하는 XML들이다.

VINTF가 대조하는 파일은 크게 네 개다. `Source-confirmed`

| 파일 | 대략 위치 | 뜻 |
|--|--|--|
| 기기(벤더) 매니페스트 | `/vendor/etc/vintf/manifest.xml` | 이 기기가 **제공하는** HAL |
| 프레임워크 매니페스트 | `/system/etc/vintf/manifest.xml` | 프레임워크가 제공하는 서비스 |
| 프레임워크 호환성 매트릭스 | `/system/etc/vintf/compatibility_matrix.*.xml` | 프레임워크가 벤더에 **요구하는** HAL 버전 |
| 기기 호환성 매트릭스 | `/vendor/etc/vintf/compatibility_matrix.xml` | 기기가 프레임워크에 요구하는 것 |

호환성 판정은 **양방향**이다: 기기 매니페스트(제공) ⟷ 프레임워크 호환성 매트릭스(요구), 그리고 프레임워크 매니페스트 ⟷ 기기 호환성 매트릭스. 둘 다 통과해야 한다. 이 검사는 부팅 시점(그리고 OTA 전)에 `libvintf`/`checkvintf`가 수행하며, 실패하면 그 조합은 부팅/업데이트가 거부된다. `Source-confirmed`

```bash
adb root
# 실제로 살아 있는 HAL과 그 상태
adb shell lshal
# 기기가 제공한다고 선언한 HAL (AIDL은 format="aidl", HIDL은 format="hidl")
adb shell cat /vendor/etc/vintf/manifest.xml
# 프레임워크가 요구하는 HAL 버전 (FCM level별로 파일이 여러 개)
adb shell ls /system/etc/vintf/
adb shell getprop ro.build.type
```

> **[그림 2]** `/vendor/etc/vintf/manifest.xml`의 한 HAL 항목(name/version/interface/instance)과, 같은 HAL을 요구하는 `/system/etc/vintf/compatibility_matrix.*.xml` 항목을 나란히 캡처해 버전 범위 매칭을 보여주는 화면 — *실측 스크린샷 자리*

`예시 출력`(네 실제 실행으로 교체) — 매니페스트 쪽:

```xml
<!-- /vendor/etc/vintf/manifest.xml  (기기가 "제공") -->
<!-- version 은 VINTF 매니페스트 스키마 메타버전(실기기는 보통 "1.0" 계열)이지,
     릴리스 버전이 아니다. OS 릴리스에 대응하는 값은 target-level(FCM level)이다. -->
<manifest version="1.0" type="device" target-level="9">
  <hal format="aidl">
    <name>android.hardware.gnss</name>
    <version>2</version>
    <interface>
      <name>IGnss</name>
      <instance>default</instance>
    </interface>
  </hal>
</manifest>
```

매트릭스 쪽:

```xml
<!-- /system/etc/vintf/compatibility_matrix.9.xml  (프레임워크가 "요구") -->
<compatibility-matrix version="1.0" type="framework" level="9">
  <hal format="aidl" optional="false">
    <name>android.hardware.gnss</name>
    <version>2-3</version>
    <interface>
      <name>IGnss</name>
      <instance>default</instance>
    </interface>
  </hal>
</compatibility-matrix>
```

여기서 판정: 기기가 GNSS AIDL v2를 제공하고, 프레임워크가 v2~v3을 요구하니 v2가 범위 안 → **호환**. 만약 프레임워크가 v3만 요구하는데 기기가 v2만 제공하면 이 항목에서 불일치가 나고, `optional="false"`인 HAL이라면 검사가 실패한다. `Source-confirmed` 즉 "VINTF 실패"는 대부분 하드웨어 고장이 아니라 **버전 범위 계약의 어긋남**이다.

아래 블록은 실제 `lshal` 원본 출력이 아니라 **`declared`/`served` 상태를 나타내려는 개념 도식**이다(실제 `lshal`은 Interface·Transport·Server PID 등을 컬럼으로 두고, 선언만 되고 등록 안 된 항목은 'declared but not registered' 같은 별도 섹션으로 표시한다). 실측 값은 기기에서 직접 확인해 교체한다.

```
# (개념 도식 — 실제 컬럼 포맷 아님)
android.hardware.gnss.IGnss/default                     [declared+served] pid=4123
android.hardware.graphics.composer3.IComposer/default   [declared+served] pid=3980
android.hardware.health@2.1::IHealth/default            [served, hwbinder] pid=3510
```

여기서 VTS가 등장한다. VTS는 CTS·STS와 함께 3대 적합성 스위트 중 벤더 인터페이스 담당으로, **벤더 HAL 구현이 인터페이스 명세대로 동작하는지**를 검사한다. 특히 `VtsTrebleVintfTest` 계열은 위의 VINTF 대조를 테스트로 강제해, "매니페스트에 선언된 HAL이 실제로 뜨는지", "선언한 버전이 매트릭스와 호환되는지"까지 확인한다. `Source-confirmed` VTS를 직접 돌리는 것은 이 글의 범위 밖(무거운 테스트 하니스)이라, 여기서는 그 검사가 무엇을 보장하는지만 정리한다.

## Root Cause — 왜 이렇게 되는가

이 구조의 뿌리는 **Project Treble**(Android 8.0)의 프레임워크/벤더 분리다. 그 전에는 프레임워크와 벤더 코드가 뒤섞여, OS를 올리려면 벤더가 매번 통합을 다시 해야 했다. Treble은 둘 사이에 안정된 인터페이스(HIDL, 지금은 AIDL)를 두어 프레임워크만 따로 업데이트할 수 있게 했다. `Source-confirmed`

그런데 분리했으니 "이 프레임워크와 이 벤더가 정말 맞물리는가"를 누군가 판정해야 한다. 그게 VINTF다. 인터페이스에 버전을 붙이고(매니페스트=제공, 매트릭스=요구), 부팅 전에 기계적으로 대조한다. 그래서 프레임워크 이미지만 새로 올려도 벤더 HAL과의 호환이 깨지지 않았음을 보장할 수 있다. `Inferred`

그리고 계약이 문서로만 있으면 벤더가 실제로 지켰는지 알 수 없다 — 그래서 VTS가 실행 검증을 맡는다. 정리하면 **HAL=계약, VINTF=버전 대조, VTS=구현 검증**이라는 삼각형이고, 셋이 있어야 프레임워크/벤더 독립 업데이트가 성립한다.

## 버전 차이와 한계

- **HIDL → 안정 AIDL.** 신규 HAL은 HIDL이 아니라 안정 AIDL로 정의하는 것이 현재 방향이다(Android 11+). 기존 HIDL 인터페이스는 대체로 동결되어 유지보수만 되고, `hwservicemanager` 같은 HIDL 인프라도 축소·폐기 방향이다 — 정확한 폐기 버전은 원문 재확인 필요. `Reported`
- **VNDK.** 최신 버전에서는 VNDK가 폐기 방향으로 가고 있어, `ro.vndk.version` 같은 프로퍼티의 의미가 버전마다 다르다. 특정 값을 단정하지 말고 버전 확인 필요. `Inferred`
- **에뮬레이터의 한계.** goldfish 에뮬레이터는 벤더 HAL이 제한적이라, 진짜 벤더 파티션·VINTF 구조를 보려면 **Cuttlefish**가 더 낫다(뒤의 18장 주제). 실기기의 실제 SoC HAL은 관측 대상이 아니다 — 개조·flashing 없이 구조만 읽는다.
- **파일 위치/스키마는 버전 의존.** 매니페스트 `version`, 매트릭스 `level`(FCM level), `target-level` 값은 릴리스마다 갱신되므로, 위 예시의 구체 숫자는 그대로 믿지 말고 기기에서 직접 확인한다.

## 정리

- HAL은 커널 드라이버가 아니라 벤더 도메인에서 도는 유저스페이스 Binder 서비스이고, binderized HAL은 별도 프로세스라 크래시가 프레임워크로 번지지 않는다.
- VINTF는 "기기 매니페스트(제공) ⟷ 프레임워크 호환성 매트릭스(요구)"를 양방향으로 대조하며, 실패는 하드웨어가 아니라 버전 계약의 불일치다.
- `lshal`의 `declared`(선언)와 `served`(실제 등록)는 다른 뜻이고, VTS(특히 VtsTrebleVintfTest)가 이 계약을 실행으로 검증한다.

**점검 질문** — (1) binderized HAL과 passthrough HAL의 격리 차이는 무엇이고, 보안상 왜 중요한가? (2) 부팅 시 VINTF 호환성 검사는 어떤 두 파일 쌍을 대조하는가? (3) `lshal`에서 어떤 HAL이 `declared`인데 `served`가 아니면 무슨 상황인가?

**참고** — [VINTF Object](https://source.android.com/docs/core/architecture/vintf) · [HAL types](https://source.android.com/docs/core/architecture/hal) · [AIDL for HALs](https://source.android.com/docs/core/architecture/aidl/aidl-hals) · [Compatibility matrices](https://source.android.com/docs/core/architecture/vintf/comp-matrices) · [VTS](https://source.android.com/docs/compatibility/vts)

*다음 글: [AOSP repo·Android.bp·Soong](/posts/android-expert-p2c17/).*
