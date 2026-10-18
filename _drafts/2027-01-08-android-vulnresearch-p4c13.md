---
layout: post
title: "HAL·vendor boundary"
date: 2027-01-08 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, HAL, Treble, 퍼징, VINTF]
excerpt: "앱이 HAL을 직접 못 부른다고 안전한 게 아니다. system service가 앱 데이터를 그대로 벤더 파서로 흘려보낸다. 그리고 신뢰 경계를 실제로 갖는 건 binderized HAL뿐이고, passthrough HAL은 호출자 프로세스 안이라 경계가 없다."
---

Android 보안 공지(Security Bulletin)를 몇 달치만 세어 보면 한쪽으로 쏠린 것이 보인다. 커널과 프레임워크도 있지만, **벤더 컴포넌트**(Qualcomm·MediaTek 등 SoC 벤더의 HAL·드라이버)가 상당수를 차지한다. `Reported` 이유는 단순하다. HAL은 하드웨어에서, 혹은 앱에서 넘어온 데이터를 C/C++로 파싱하는 코드이고, 대부분 폐쇄 소스라 외부 검증이 적게 들어간다. 취약점 연구자에게 이 벤더 경계는 밀도 높은 표면이다.

폐쇄 소스 벤더 HAL을 직접 뜯는 건 이 시리즈의 안전 범위를 벗어난다. 하지만 경계 자체의 구조, AOSP 기본(reference) HAL 구현, 그리고 AOSP가 제공하는 인터페이스 퍼징 프레임워크는 전부 공개돼 있다. 이 글은 Treble이 만든 system↔vendor 경계가 왜 공격 표면이 되는지, 그리고 그 경계를 안전하게(Cuttlefish·기본 HAL·자작 하네스로) 관측·퍼징하는 워크플로를 정리한 기록이다.

> **한 줄 결론**: 신뢰 경계를 실제로 갖는 건 별도 프로세스+SELinux 도메인을 가진 **binderized HAL뿐**이고 passthrough/same-process HAL엔 경계가 없다. 앱이 HAL을 직접 못 불러도 system service가 앱 데이터를 그대로 벤더 파서로 전달하므로, 벤더 경계는 퍼징 1순위 표면이다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 것은 세 가지다. (1) Treble이 나눈 system·vendor 파티션과 HAL 유형(binderized/passthrough/same-process), (2) VINTF가 그 경계에서 무엇을 강제하는지, (3) 앱→system service→HAL로 이어지는 데이터 흐름을 어디서 어떻게 퍼징하느냐. 벤더 자체 소스가 아니라 **경계와 기본 구현**만 대상으로 한다.

선수 지식이 몇 가지 깔린다. Binder/AIDL 서비스 퍼징의 기본기(6장에서 다룬 `fuzzService` 계열 하네스), SELinux `service_contexts`로 누가 어느 서비스에 닿는지 읽는 법(12장), 그리고 system service 공격 표면의 개념(5장)이다. Atlas 쪽에선 Binder IPC와 SELinux 강제 접근 제어 편을 먼저 훑어 두면 좋다. 하이퍼링크 대신 장 번호로만 적는다.

전체 구조에서 이 장은 4부(심화 취약점 연구)의 "표면 넓히기" 지점이다. 프레임워크 서비스(5·6장)에서 한 겹 더 내려가, 벤더 프로세스에서 도는 코드까지 시야를 넓힌다. 다음 장부터는 이 표면을 baseline/patched 이미지 비교와 patch-gap 분석으로 이어 간다.

## 핵심 개념 — Treble이 만든 벤더 경계

Project Treble은 Android 8.0에서 system과 vendor를 **별도 파티션**으로 분리했다. 목적은 OS 업데이트와 벤더(SoC) 구현의 수명 주기를 떼어내는 것이지만, 부수 효과로 둘 사이에 안정된 인터페이스(HAL)와 그 인터페이스를 넘나드는 **신뢰 경계**가 생겼다. `Source-confirmed`

HAL이 어떻게 실행되느냐에 따라 경계의 성격이 완전히 달라진다. 이게 연구자가 제일 먼저 확인해야 할 축이다.

| HAL 유형 | 실행 위치 | 프로세스 경계 | SELinux 도메인 | 비고 |
|--|--|--|--|--|
| **Binderized** | 별도 벤더 프로세스 | **있음** | `hal_*` 벤더 도메인 | Treble 기본. hwbinder(HIDL)/binder(AIDL) |
| **Passthrough** | **호출자 프로세스 안** | 없음 | 호출자와 동일 | HIDL 전용 레거시 `.so` 래핑 |
| **Same-process(SP-HAL)** | 앱/서비스 프로세스 안 | 없음(설계상) | 호출자와 동일 | gralloc mapper, Vulkan/GLES 등 |

`Source-confirmed`(source.android.com HAL types). 여기서 흔한 오개념 하나 — "HAL은 무조건 격리된 벤더 프로세스에서 돈다"는 틀렸다. **passthrough와 same-process HAL은 호출자 프로세스 주소 공간 안에 로드**되므로, 그 안의 메모리 손상은 별도 벤더 도메인이 아니라 **호출자의 권한으로** 곧장 이어진다. 반대로 binderized HAL의 크래시는 원칙적으로 그 벤더 프로세스에 갇힌다.

경계를 계약으로 못박는 것이 **VINTF**(Vendor Interface)다. 벤더는 `/vendor/etc/vintf/manifest.xml`에 자신이 제공하는 HAL과 버전을 선언하고, 프레임워크는 compatibility matrix에 요구 버전을 선언한다. 둘이 안 맞으면 빌드 타임과 OTA 시점의 호환성 검사에서 비호환 업데이트가 거부된다. `Source-confirmed`(빌드·OTA 시 호환성 검사) 연구자에겐 이 매니페스트가 **"이 이미지에 어떤 HAL 표면이 있는가"의 1차 목록**이다.

> **[그림 1]** Cuttlefish/AVD에서 `adb shell cat /vendor/etc/vintf/manifest.xml` 앞부분과 `adb shell ls -ld /system /vendor`로 파티션·HAL 선언을 함께 담은 캡처 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

위협 모델을 앱 관점으로 세우면 경계가 선명해진다. 일반 앱은 SELinux상 대부분의 HAL 서비스(`hal_*`/`hwservice`)에 **직접** 바인딩할 수 없다. `Source-confirmed` 그래서 "앱이 못 부르니 안전"이라고 결론 내리기 쉽다. 이게 두 번째 함정이다.

실제 경로는 한 다리 건넌다. 앱이 닿을 수 있는 system service(예: media/camera/sensor 프레임워크)가 앱이 준 데이터(이미지 버퍼, 카메라 메타데이터, 센서 설정 등)를 **그대로 또는 얇게 감싸서** 벤더 HAL로 전달한다. `Inferred` 즉 신뢰 경계를 넘는 데이터의 출처는 결국 앱이고, 파싱은 벤더 C/C++ 코드가 한다. 퍼징 관점에서 이건 전형적인 **불신 입력 → 네이티브 파서** 구도다. 내가 예전에 다룬 tinyobjloader의 `parseLine` OOB write나 미디어 파서류와 성격이 똑같다.

경계의 성격을 유형별로 요약하면 이렇다.

- **Binderized HAL** — 넘어가는 것은 Parcel(직렬화 메시지). 표면은 언마샬링·역직렬화 경로. 크래시는 벤더 프로세스에 갇히지만, 서비스가 죽으면 그를 의존하는 프레임워크가 재시작·기능불능이 될 수 있다(가용성).
- **Passthrough/SP-HAL** — 경계가 없으므로 벤더 파서의 메모리 손상이 곧 호출자(때로는 앱) 프로세스의 손상이다. 심각도가 다르다. `Inferred`

## 관측 — HAL 표면 나열과 퍼징 하네스

**표면 나열.** 기기에 등록된 HAL은 `lshal`로 본다. HIDL 인터페이스를 서버 프로세스와 함께 나열하고, 최근 버전은 AIDL HAL도 표시한다(표시 범위는 버전 확인 필요). `Reported`

```bash
adb shell lshal            # 등록된 HAL 인터페이스와 서버
adb shell lshal --types=b  # binderized만
adb shell service list | grep -i vendor   # AIDL 벤더 서비스(참고)
```

`예시 출력(교체)` — Cuttlefish에서 실제 실행 결과로 바꿀 것:

```
Interface                                                Server ...
android.hardware.audio@7.0::IDevicesFactory/default      1234 ...
android.hardware.camera.provider@2.7::ICameraProvider/...  1288 ...
android.hardware.sensors@2.1::ISensors/default           1301 ...
```

이 목록에서 **불신 입력을 파싱하는 인터페이스**(camera metadata, audio effect config, sensor 등)를 우선 후보로 고른다. `Inferred`

> **[그림 2]** `adb shell lshal`로 등록된 HAL 인터페이스·서버 PID를 나열한 캡처(binderized 표시 포함) — *실측 스크린샷 자리*

**하네스.** AOSP는 binder 서비스에 임의 Parcel을 먹이는 퍼징 헬퍼를 제공한다. `frameworks/native/libs/binder` 아래 `libbinder_random_parcel`/`fuzzService` 계열이며, HAL 서비스 객체를 만들어 랜덤 트랜잭션을 던진다(정확한 헤더·경로·심볼명은 AOSP 트리에서 재확인 권장). `Reported` 대상은 **AOSP 기본 HAL 구현**으로 한정한다 — 폐쇄 벤더 바이너리가 아니다.

```cpp
// 개념 골격 — 실제 심볼/헤더는 AOSP 트리에서 확인
#include <fuzzbinder/libbinder_driver.h>
#include <fuzzer/FuzzedDataProvider.h>
#include "MyDefaultHal.h"          // AOSP 기본(reference) HAL 구현

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
    static auto hal = ndk::SharedRefBase::make<MyDefaultHal>();
    // fuzzService는 libbinder sp<IBinder>를 받는다 — NDK AIBinder*는
    // AIBinder_toPlatformBinder로 플랫폼 바인더 변환 필요
    fuzzService(AIBinder_toPlatformBinder(hal->asBinder().get()),
                FuzzedDataProvider(data, size));
    return 0;
}
```

빌드는 AOSP 트리 안에서 `cc_fuzz` 모듈로 걸고 HWASan/ASan을 켠 채 `m` 으로 만든다. 실행하면 libFuzzer가 커버리지 기반으로 트랜잭션을 변형한다. 여기서 이전 퍼징 경험 두 가지가 그대로 적용된다.

- **크래시 트리아지 = 심각도 판정.** libsoup Range 하네스에서 나온 건 assert 실패(가용성/DoS)였고 tinyobj는 OOB write(메모리 손상)였다. HAL 퍼징에서도 **DoS를 RCE로 부풀리지 않는다** — assert/`CHECK` 실패인지, 실제 힙/스택 손상인지 sanitizer 리포트로 갈라 적는다.
- **NDEBUG 함정.** tinyobj OOB가 `NDEBUG` 빌드에서만 ASan에 잡혔던 것처럼, HAL도 `CHECK`가 켜진 빌드는 손상 전에 abort로 가려질 수 있다. 하네스 빌드 구성(assert on/off)을 기록해 둔다.
- **기능 게이트 트리아지.** wabt에서 미구현 경로 크래시를 걸러냈듯, 기본 HAL의 스텁/미구현 반환이 만든 얕은 크래시를 실제 파싱 버그와 분리한다.

## Root Cause — 왜 벤더 경계가 취약점 밀집 지대인가

세 가지가 겹친다. 첫째, **입력의 출처가 불신**이다. system service가 앱 데이터를 벤더 파서로 넘기는 구조라, 경계 너머 파서는 사실상 공격자 제어 입력을 다룬다. `Inferred` 둘째, **구현 주체가 다르다.** HAL 계약(AIDL/HIDL)은 AOSP가 정의하지만 구현은 SoC 벤더이고, 폐쇄 소스라 AOSP만큼의 퍼징·리뷰가 균일하게 들어가지 않는다. `Reported` 셋째, **유형이 경계를 지운다.** passthrough/same-process HAL은 격리 프로세스라는 통념과 달리 호출자 안에서 돌아, 같은 버그라도 심각도가 올라간다. `Source-confirmed`(유형 정의 기준)

정리하면, 벤더 경계의 위험은 "벤더가 특별히 못 짜서"가 아니라 **불신 입력 + 얇은 외부 검증 + 유형에 따른 경계 소실**의 구조적 산물이다. 그래서 표면이 넓고, 그래서 퍼징이 효과적이다.

## 버전 차이와 한계

HAL 지형은 버전마다 크게 바뀌었다. 여기서 세대를 헷갈리면 없는 표면을 뒤지거나 있는 표면을 놓친다.

- **HIDL → AIDL 전환.** 초기 Treble의 HAL 인터페이스 언어는 HIDL이었고, 이후 **Stable AIDL for HALs**로 이동했다. 새 HAL은 AIDL로 작성되고 HIDL은 레거시/고정 상태다. `Reported` 등록·조회 경로도 다르다 — HIDL은 `hwservicemanager`/`lshal` 중심, AIDL 벤더 서비스는 일반 `servicemanager` 인스턴스로 온다. 어느 세대냐에 따라 하네스와 조회 도구가 갈린다.
- **VNDK.** 벤더 코드가 링크 가능한 system 라이브러리 집합(ABI 안정용)이었으나, 최신 Android에서 **폐지 방향**으로 정리됐다(폐지/유지 여부는 대상 버전에서 확인 필요). `Reported` VNDK를 전제로 한 오래된 자료를 그대로 따르면 어긋난다.
- **passthrough의 축소.** Treble 기본은 binderized이며 passthrough는 레거시 호환 목적이다. 최신 이미지에서 특정 HAL이 어느 유형인지는 이미지별로 다르니 `lshal --types`로 실측한다. `Source-confirmed`(유형 구분)

한계도 분명하다. 에뮬레이터/Cuttlefish의 HAL은 대부분 **소프트웨어 기본 구현**이라, 실제 SoC 벤더 바이너리의 버그는 여기서 재현되지 않는다. 이 랩으로는 **경계 구조와 기본 구현·계약 표면**까지가 안전·재현 범위이고, 실벤더 코드 분석은 별개의(그리고 이 시리즈 범위 밖의) 작업이다. 회귀 검증도 이 선을 지킨다 — 기본 HAL에서 재현한 크래시는 sanitizer 리포트+최소화된 시드를 코퍼스에 넣어 패치 후 재실행으로 확인한다.

## 정리

- 신뢰 경계를 실제로 갖는 건 **binderized HAL뿐**(별도 프로세스+`hal_*` 도메인). passthrough/same-process는 호출자 안에서 돌아 경계가 없고 심각도가 다르다.
- 앱이 HAL을 직접 못 불러도, system service가 앱 데이터를 벤더 파서로 전달한다. 불신 입력 → 네이티브 파서가 퍼징 표면의 본질이다.
- 안전 범위는 **경계 구조 + AOSP 기본 HAL + `fuzzService` 계열 하네스 + Cuttlefish**. 폐쇄 벤더 바이너리·무기화는 범위 밖. 크래시는 DoS/메모리손상을 sanitizer로 갈라 심각도를 정직하게 적는다.

**점검 질문** — (1) 같은 파서 버그가 binderized HAL과 passthrough HAL에서 심각도가 다른 이유는? (2) 일반 앱이 HAL에 직접 못 바인딩하는데도 HAL이 공격 표면인 까닭은? (3) 대상 이미지의 HAL 표면 목록을 어디서(파일/명령) 얻는가?

**참고** — [HAL types](https://source.android.com/docs/core/architecture/hal-types) · [AIDL HALs](https://source.android.com/docs/core/architecture/aidl/aidl-hals) · [VINTF](https://source.android.com/docs/core/architecture/vintf) · [AOSP Fuzzing](https://source.android.com/docs/security/test/fuzzing)

*다음 글: [이미지 baseline/patched 비교](/posts/android-vulnresearch-p4c14/).*
