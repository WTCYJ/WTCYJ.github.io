---
layout: post
title: "Binder/AIDL service fuzzing"
date: 2027-01-01 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Binder, AIDL, Fuzzing, Parcel, libFuzzer]
excerpt: "Binder 서비스에 바이트를 무작정 던지면 인터페이스 디스크립터 검사에서 전부 튕겨 커버리지가 0에 수렴한다. 구조를 존중하는 fuzzService/randomParcel로 onTransact에 닿아야 하고, 거기서 나온 CHECK-abort는 RCE가 아니라 system_server 재시작 수준 DoS다."
---

Android에서 앱과 시스템 서비스는 거의 전부 **Binder**로 대화한다. 낮은 권한의 앱이 `system_server`나 네이티브 서비스(대개 더 높은 권한, 즉 더 낮은 UID)에 트랜잭션을 보내고, 서비스는 받은 **Parcel**을 언마샬링한다. 이 언마샬링 코드가 공격자 통제 값을 검증 없이 쓰면, 신뢰 경계를 가로지르는 메모리 손상이 된다 — Android 보안 불리틴에 반복적으로 등장하는 계열이다. 그래서 시스템 서비스 퍼징의 표적은 "메서드 로직"이 아니라 **onTransact에 도달하는 Parcel**이다.

이 글은 그 표면을 안전하게 두드리는 fuzzing 하네스를 세운 기록이다. 자작 AIDL 서비스와 AOSP의 오픈소스 퍼징 프레임워크(`fuzzService`/`randomParcel`)만 쓰고, 실서비스 공격이나 무기화는 하지 않는다. 앞서 wabt(wasm2c)·libsoup·tinyobjloader에서 쓴 규율 — 하네스 + 새니타이저 + 코퍼스 — 을 Binder 표면에 그대로 옮긴다.

> **한 줄 결론**: Binder 퍼징은 인터페이스 디스크립터·타입을 존중하는 **구조 인지 하네스**(fuzzService/randomParcel)로 onTransact까지 도달해야 의미가 있고, 거기서 나온 크래시는 곧바로 취약점이 아니라 "untrusted_app에서 도달 가능한 메모리 손상인가"로 트리아지해야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 범위는 세 가지다. (1) Binder 시스템 서비스의 공격 표면이 왜 Parcel 언마샬링에 몰리는가, (2) in-process libFuzzer 하네스로 서비스 구현을 링크해 랜덤 Parcel을 주입하는 법, (3) 퍼저가 뱉은 크래시를 취약점으로 볼지 결정하는 트리아지. 익스플로잇 작성은 다루지 않는다.

선수 지식으로는, Binder IPC와 Parcel 직렬화가 무엇인지(Atlas의 Binder/IPC 편에서 다룬 트랜잭션 코드·인터페이스 디스크립터·마샬링 개념), 그리고 커버리지 유도 퍼징과 `FuzzedDataProvider`의 기본기가 깔려 있어야 한다. SELinux `service_contexts`로 어떤 도메인이 어떤 서비스를 호출할 수 있는지 읽는 법은 이 4부 뒤쪽 12장에서 더 판다.

전체 구조에서 이 장의 위치는, 4부 5장(System Service 공격 표면)이 "무엇이 표면인가"를 지도로 그렸다면, 이 6장은 그 표면을 실제로 **퍼징 도구로 두드리는** 첫 실습이다. 이어지는 7장부터는 같은 libFuzzer 기법을 미디어·파일 **파서**로 좁혀 간다.

## 핵심 개념 — Parcel·onTransact, 그리고 두 가지 퍼징 모드

Binder 트랜잭션은 구조를 갖는다. 클라이언트는 `transact(code, data, reply, flags)`를 호출하고, 서비스는 `onTransact(code, data, reply, flags)`에서 받는다. `data`는 **Parcel** — 앞머리에 인터페이스 디스크립터가 오고, 이어서 AIDL 시그니처가 규정한 타입들이 순서대로 마샬링돼 있다. `Source-confirmed`

여기서 퍼징의 첫 함정이 나온다. `onTransact`은 본체를 실행하기 전에 인터페이스 디스크립터부터 확인한다(Java의 `enforceInterface`, C++의 `CHECK_INTERFACE`). **무작위 바이트는 이 검사에서 전부 튕겨** 즉시 반환되므로, 파서 깊숙한 곳엔 닿지도 못하고 커버리지가 바닥에 눕는다. `Source-confirmed` 그래서 Binder 퍼징은 반드시 구조를 존중해야 한다 — 올바른 디스크립터를 채우고, 타입 순서에 맞는 Parcel을 생성해 실제 메서드 디스패치까지 도달시켜야 한다.

AOSP는 이걸 위한 오픈소스 도구를 제공한다. `randomParcel` 계열 라이브러리는 binder 오브젝트·파일 디스크립터까지 포함한 랜덤 Parcel을 생성하고, `fuzzService` 헬퍼는 그 Parcel을 대상 서비스의 `IBinder::transact`에 반복 주입한다. 빌드는 Soong의 `cc_fuzz` 모듈로 하며, ASan/HWASan 아래에서 in-process로 돌아간다. `Source-confirmed`(정확한 헤더 경로·시그니처는 원문 재확인 필요)

퍼징 모드는 크게 둘이고, 트레이드오프가 분명하다.

| 모드 | 위치 | 입력 생성 | 커버리지/ASan | 한계 |
|--|--|--|--|--|
| **in-process 하네스**(`fuzzService`) | host 또는 device, 서비스 구현을 **직접 링크** | `randomParcel` | 있음 | 서비스를 빌드에서 격리·링크해야 함 |
| **on-device 트랜잭션**(`service call`/자작 앱) | 라이브 서비스에 원격 호출 | 손으로 만든 Parcel | **없음** | 재현·최소화 어렵고 production엔 ASan 없음 |

실질적 결론은 표 그대로다. 진짜 연구는 in-process 하네스에서 나오고, on-device 호출은 **도달성 열거**(어떤 서비스가 내 도메인에서 호출되나)용이지 커버리지 퍼징을 대체하지 못한다. `Inferred`

> **[그림 1]** `adb shell service list`로 기기에 등록된 Binder 서비스 목록(공격 표면)을 나열한 터미널 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 AIDL 서비스 + 로컬 빌드**로만 진행한다. 실기기의 실서비스에 malformed Parcel을 쏘거나, 남의 앱·프로덕션을 대상으로 삼지 않는다. 표적은 내가 정의한 `.aidl`로 생성한 최소 서비스이고, 여기에 의도적으로 검증 없는 네이티브 언마샬링 한 줄을 심어 하네스가 그걸 잡는지 확인한다. AOSP 트리 자체의 `libbinder` 서비스 퍼저(오픈소스)도 같은 방식으로 빌드·관찰할 수 있다. 크래시가 나오면 개념 수준까지만 분석하고, 완성형 익스플로잇으로 발전시키지 않는다.

## 실습 절차와 관측

### 가설
- **가설 A** — 무작위 바이트를 raw `transact`에 던지면 디스크립터 검사에서 튕겨 커버리지가 거의 늘지 않는다. `fuzzService`로 바꾸면 cov/ft가 유의미하게 오른다. `Inferred`
- **가설 B** — 손으로 심은 "길이 필드를 검증 없이 할당에 사용" 버그는 ASan 빌드에서 `heap-buffer-overflow`로 잡힌다. `Inferred`

### 절차
1. `.aidl`로 최소 서비스를 정의하고 스텁을 생성한다(네이티브 `Bn` 측에 검증 없는 언마샬링 한 줄을 심어 둔다).
2. `fuzzService`를 호출하는 하네스를 작성한다.
3. `cc_fuzz`로 ASan 빌드해 host 퍼저 바이너리를 만든다.
4. 작은 시드 코퍼스로 실행하고 cov/exec와 크래시 여부를 기록한다.
5. 대조군으로, 같은 서비스에 raw 랜덤 `transact`만 던지는 하네스를 돌려 커버리지 차이를 본다.

```cpp
// my_service_fuzzer.cpp — 개념용 최소 하네스
#include <fuzzer/FuzzedDataProvider.h>
#include <fuzzbinder/libbinder_driver.h>   // 경로/시그니처는 원문 재확인 필요
#include "MyService.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
    FuzzedDataProvider provider(data, size);
    auto service = sp<MyService>::make();
    // fuzzService가 올바른 디스크립터를 채우고 랜덤 Parcel을 onTransact에 주입
    fuzzService(service, std::move(provider));
    return 0;
}
```

```
// Android.bp
cc_fuzz {
    name: "my_service_fuzzer",
    srcs: ["my_service_fuzzer.cpp"],
    static_libs: ["libbinder_random_parcel", "libmyservice"],
    shared_libs: ["libbinder", "libutils"],
    // fuzz_config: { componentid: ... },  // 실제 등록 시
}
```

```bash
# ASan host 퍼저 빌드 (정확한 변형 지정은 트리 버전에 따라 확인 필요)
m my_service_fuzzer
# 시드 코퍼스와 함께 실행
$ANDROID_HOST_OUT/fuzz/.../my_service_fuzzer corpus/ -max_len=4096
```

> **[그림 2]** 자작 AIDL 서비스 하네스를 libFuzzer+ASan으로 돌려 cov/exec 증가와 `heap-buffer-overflow` 리포트가 뜬 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
INFO: Running with entropic power schedule (0xFF, 100).
INFO: Seed: 2894571032
#2      INITED cov: 412 ft: 431 corp: 1/1b exec/s: 0
#1024   NEW    cov: 903 ft: 1210 corp: 37/2114b exec/s: 51200
==12345==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...
    #0 MyService::readPayload ... (심어 둔 검증 없는 언마샬링 라인, 실제 실행으로 교체)
SUMMARY: AddressSanitizer: heap-buffer-overflow
```

대조군(raw 랜덤 `transact`)은 같은 시간 동안 `cov`가 거의 초기값에 머문다 — 디스크립터에서 튕겼다는 증거다. 두 로그의 `cov` 격차 하나가 "구조를 존중하라"의 실측 근거다. `Inferred`

## Root Cause — 왜 이렇게 되는가

Parcel 언마샬링이 메모리 안전 버그의 온상인 이유는 세 겹이다.

첫째, **공격자 통제 길이/개수 필드**다. `readInt32`로 원소 개수나 바이트 길이를 읽어, 검증 전에 그 값으로 할당하거나 반복하면 정수 오버플로·OOB가 난다. 이건 libsoup의 Range 정수 오버플로, tinyobjloader의 길이 주도 OOB write와 **정확히 같은 클래스**다 — 표면만 Binder일 뿐. `Inferred`

둘째, **네이티브 대 생성 스텁의 비대칭**이다. AIDL이 생성한 Java 스텁은 경계 검사가 비교적 붙어 있지만, 손으로 짠 `onTransact`이나 C++ 네이티브 서비스는 그 검사를 건너뛰기 쉽다. `Reported` 그래서 하네스는 Java보다 **네이티브 서비스**에 겨눌수록 수확이 크다.

셋째, **타입 혼동**이다. `readStrongBinder`·`readParcelable`은 상대가 보낸 타입을 신뢰해 역직렬화하는데, 프로세스 경계 너머의 값이 예상과 다른 타입으로 유도되면 혼동이 생긴다. `randomParcel`이 binder 오브젝트·fd까지 섞는 이유가 이 표면을 때리기 위해서다. `Inferred`

## 방어와 회귀 검증

퍼저 크래시는 **취약점이 아니라 후보**다. 세 관문을 통과해야 보안 이슈로 센다.

- **도달성** — untrusted_app 도메인이 그 서비스를 `binder_call`할 수 있나? SELinux `service_contexts`와 sepolicy가 막고 있으면, 그 크래시는 특권 호출자만 닿을 수 있어 보안 경계 문제가 아니다. `service list`로 표면을 열거하되, 정책으로 다시 걸러야 한다. `Inferred`
- **손상 유형** — ASan `heap-buffer-overflow`/`use-after-free`는 메모리 손상이지만, 단순 `CHECK`/`LOG(FATAL)` abort는 다르다. `system_server`의 CHECK-abort는 프로세스 재시작 수준 **DoS**이지 RCE가 아니다. DoS를 RCE로, 크래시를 무조건 취약점으로 부풀리면 안 된다 — IrfanView의 무한루프를 DoS로만 기록했던 것과 같은 규율이다. `Inferred`
- **회귀 시드화** — 확정된 크래시 Parcel은 코퍼스에 회귀 시드로 넣는다. 패치가 나온 뒤 같은 하네스를 CI로 재실행해 재발을 막는다. wabt에서 내 PoC가 그대로 업스트림 회귀 테스트가 됐던 것처럼, **크래시 입력 자체가 회귀 테스트**다. `Inferred`

이미 패치된 공개 CVE로 하네스를 검증하는 것도 좋은 습관이다 — 패치 이전 코드에서 하네스가 그 크래시를 재현하면, 하네스가 실제로 그 표면에 닿는다는 증거가 된다. 무기화가 아니라 **하네스 신뢰도 측정**이다.

## 정리

- Binder 퍼징의 표적은 메서드 로직이 아니라 `onTransact`에 도달하는 Parcel이며, 무작위 바이트는 디스크립터 검사에서 튕겨 커버리지가 0에 수렴한다.
- 구조 인지 하네스(`fuzzService`/`randomParcel` + `cc_fuzz` + ASan)로 in-process 링크해야 파서까지 닿는다. on-device `service call`은 도달성 열거용이다.
- 크래시는 후보일 뿐 — untrusted_app 도달성·메모리 손상 유형으로 트리아지하고, CHECK-abort는 DoS로 정직하게 기록한다.
- 확정된 크래시 Parcel은 회귀 시드로 코퍼스에 넣어 패치 후 CI로 재검증한다.

**점검 질문** — (1) 왜 raw 랜덤 바이트를 `transact`에 던지면 커버리지가 늘지 않는가? (2) 퍼저가 `system_server`에서 CHECK-abort를 냈다. 이걸 왜 RCE라 부르면 안 되는가? (3) 크래시가 실제 보안 이슈인지 판정할 때 SELinux를 왜 봐야 하는가?

**참고** — AOSP `frameworks/native/libs/binder`(fuzzService/randomParcel, 경로·시그니처는 트리에서 재확인) · Android Open Source Project 「Fuzzing with libFuzzer」(source.android.com) · LLVM `FuzzedDataProvider`(compiler-rt) · Android 보안 불리틴(source.android.com/security/bulletin)

*다음 글: [Parser용 libFuzzer harness](/posts/android-vulnresearch-p4c07/).*
