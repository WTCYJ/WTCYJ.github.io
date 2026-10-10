---
layout: post
title: "Stable AIDL·Java/NDK/Rust backend"
date: 2026-11-27 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, AIDL, Binder, Treble, Rust]
excerpt: "Stable AIDL의 '안정'은 한 번 frozen된 버전의 바이트 레이아웃이 hash 계약으로 고정된다는 뜻이다. 흔한 함정 둘 — 새 메서드는 인터페이스 '끝'에만 붙일 수 있고, ndk_platform 백엔드는 이미 ndk로 통합됐다."
---

Binder 트랜잭션은 결국 Parcel에 담긴 바이트 뭉치다(14장). 그런데 그 바이트를 "양쪽이 똑같이 해석한다"를 누가 보장하나? system 이미지와 vendor 이미지가 따로 업데이트되는 Treble 세계에서, 이 해석 계약이 어긋나면 한쪽은 그 자리를 `int`로, 다른 쪽은 `long`으로 읽는다 — 조용한 타입 혼동이다. Stable AIDL은 이 계약을 인터페이스마다 hash로 고정하고, 어긋남을 빌드 시점에 잡아낸다.

이 글은 `aidl_interface` Soong 모듈이 어떻게 인터페이스 버전을 얼리고(freeze) java/cpp/ndk/rust 네 백엔드로 **같은 계약**을 각 언어로 찍어내는지, 그리고 그게 왜 신뢰 경계 문제인지를 AOSP 소스와 함께 정리한 기록이다.

> **한 줄 결론**: Stable AIDL의 "안정"은 인터페이스가 한 번 frozen되면 그 버전의 바이트 레이아웃(hash)이 계약으로 고정된다는 뜻이다. 백엔드(java/cpp/ndk/rust)는 그 계약을 각 언어로 구현할 뿐, 계약 자체를 바꾸지 못한다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 넷이다. (1) `aidl_interface`가 왜 있고 무엇을 생성하는가, (2) 네 백엔드(java/cpp/ndk/rust)의 산출물과 사용처 차이, (3) "frozen 버전"과 `.hash`가 무엇을 고정하는가, (4) 그 고정이 왜 보안(신뢰 경계) 문제인가. 공격 실습이 아니라 구조와 소스 이해가 목적이다.

선수 지식으로 세 가지가 밑에 깔린다. Binder의 proxy/stub·트랜잭션 코드 구조(14장)를 알아야 AIDL 컴파일러가 무엇을 찍어내는지 이해된다. Soong 빌드(`Android.bp`)의 모듈 개념을 알면 `aidl_interface` 선언이 눈에 들어온다. 그리고 Treble이 system/vendor 파티션을 독립 업데이트로 쪼갰다는 사실 — 이게 "안정된 계약"이 왜 필요한지의 이유 전부다.

전체 구조에서 이 장은 **계약 층**이다. 14장의 raw Binder proxy/stub는 이 AIDL 컴파일러의 **산출물**이고, 16장(HAL·VINTF·VTS)의 하드웨어 인터페이스는 이 Stable AIDL 계약 **위에** 선다. 즉 아래는 Binder, 위는 HAL, 그 사이에서 "무엇을 주고받기로 했는지"를 못박는 게 이 층이다.

## 핵심 개념 — aidl_interface와 4개 백엔드

Stable AIDL은 `.aidl` 파일을 Soong의 `aidl_interface` 모듈로 감싸는 데서 시작한다. 이 모듈 하나가 **켜둔 백엔드마다** 별도 라이브러리를 생성한다. `Source-confirmed`

| 백엔드 | 생성물(요지) | 주 사용처 |
|--|--|--|
| `java` | `IFoo`, `IFoo.Stub`(서버), `IFoo.Stub.Proxy`(클라) | 프레임워크/앱(Java·Kotlin) |
| `cpp` | `IFoo`, `BnFoo`(서버), `BpFoo`(클라) — `libbinder` 의존 | system 내부 C++ |
| `ndk` | `aidl::<pkg>::IFoo`, `BnFoo`/`BpFoo` — `libbinder_ndk` C API | **vendor·앱**(안정 ABI) |
| `rust` | `IFoo`/`BnFoo`/`BpFoo` 크레이트 — `libbinder_rs` | 메모리 안전이 필요한 서버 |

여기서 흔한 오개념 하나 — "백엔드를 여러 개 켜면 인터페이스가 여러 개 생긴다"가 아니다. **계약은 하나**고, 백엔드는 그 하나의 계약을 언어별로 구현할 뿐이다. cpp와 ndk를 가르는 핵심은 ABI다. cpp 백엔드는 `libbinder`(불안정 C++ ABI)에 묶여 system 내부에서만 쓰고, ndk 백엔드는 `libbinder_ndk`의 안정 C API(`AIBinder`/`AParcel`/`AStatus`)를 써서 vendor와 앱이 경계를 넘어 쓸 수 있다. `Source-confirmed`

선언은 대략 이렇게 생겼다.

```
// Android.bp
aidl_interface {
    name: "com.example.foo",
    srcs: ["com/example/foo/*.aidl"],
    stability: "vintf",          // system/vendor 경계를 넘는 계약
    backend: {
        cpp:  { enabled: false },
        ndk:  { enabled: true },
        rust: { enabled: true },
    },
    versions: ["1", "2"],        // 얼린(frozen) 버전 목록
}
```

```
// com/example/foo/IFoo.aidl
package com.example.foo;

@VintfStability
interface IFoo {
    int getValue();
    void setValue(int v);   // 버전 2에서 "끝"에 추가된 메서드
}
```

`versions`에 올라간 각 버전은 소스 트리에 스냅샷과 해시로 박제된다. `aidl_api/<이름>/<버전>/`에 그 버전의 `.aidl` 사본과 `.hash` 한 개가 들어가고, `current/`에는 아직 안 얼린 진행 중 버전이 있다. `.hash`는 그 버전 인터페이스의 구조를 요약한 지문이며, 이게 바뀌면 빌드가 "계약을 몰래 고쳤다"고 실패시킨다. `Source-confirmed`

> **[그림 1]** `find aidl_api/com.example.foo` 출력 — 얼린 버전 디렉터리(`1/`, `2/`)와 각 버전의 `.hash`, 그리고 `current/`가 나란히 보이는 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

여기서 신뢰 경계는 **Parcel 그 자체**다. 서버는 클라이언트가 보낸 바이트를 "약속된 순서·타입대로" 읽는다고 믿고 역직렬화한다. 이 믿음이 깨지는 순간이 고전적 Binder 취약점의 무대다 — 손으로 짠 `readFromParcel`이 길이를 잘못 믿거나, 양쪽 레이아웃이 어긋난 채로 읽는 경우.

Stable AIDL은 이 표면을 두 방향으로 좁힌다. 첫째, **구조화(structured) parcelable**만 허용한다. 필드를 `.aidl`에 선언하면 (역)직렬화 코드를 컴파일러가 생성하므로, 손으로 짠 마샬링에서 나오던 오프셋·길이 실수가 줄어든다. `Source-confirmed` 둘째, **hash가 레이아웃을 못박는다**. 한 번 얼린 버전의 바이트 배치는 지문으로 고정되니, 어느 쪽이 몰래 필드를 끼워 넣어 스큐를 만드는 일을 CI에서 차단한다.

위협 모델의 핵심은 "버전 스큐"다. 클라이언트는 v2로, 서버는 아직 v1로 빌드된 상황 — Treble에서는 정상적으로 벌어진다. 이때 v2가 v1에 없는 메서드를 부르면 Binder는 `STATUS_UNKNOWN_TRANSACTION`을 돌려준다. `Source-confirmed` 조용한 오동작이 아니라 **명시적 거부**라는 점이 안정성의 요체다. 다만 이건 "새 메서드는 끝에만 붙는다"는 규칙 위에서만 성립한다. 중간에 끼워 넣으면 뒤 메서드들의 트랜잭션 코드가 한 칸씩 밀려, v1 서버가 `getValue`인 줄 알고 엉뚱한 코드를 실행한다. 그래서 append-only가 규칙이 아니라 안전의 전제다. `Inferred`

Rust 백엔드는 이 경계에서 한 겹을 더 준다. Parcel 파싱은 메모리 손상이 자주 나던 자리인데, 서버(`BnFoo`) 구현을 Rust로 두면 그 역직렬화 경로가 메모리 안전 코드로 생성된다. 무기가 아니라 **표면 축소**의 관점이다. `Reported`

## 분석 — freeze·버전 협상·생성 코드

안전 범위는 전부 공개 AOSP 소스와 Cuttlefish/에뮬레이터(userdebug), 그리고 자작 `aidl_interface`다. 제3자·프로덕션 인터페이스는 건드리지 않는다.

**freeze는 무엇을 하나.** 진행 중인 `current/`를 다음 번호의 frozen 버전으로 승격하면서 그 시점의 `.aidl` 스냅샷과 `.hash`를 굳힌다. 문서화된 빌드 타깃은 인터페이스 이름 뒤에 접미사를 붙이는 형태다 — `m <이름>-freeze-api`로 얼리고, `m <이름>-update-api`로 `current/`를 갱신한다. `Source-confirmed` (정확한 타깃 접미사는 트리 버전에 따라 재확인 권장.)

얼린 뒤 규칙은 append-only다. 기존 메서드의 시그니처 변경·순서 변경·삭제는 금지, 새 메서드는 인터페이스 끝에만, parcelable에는 기본값 있는 필드를 끝에만, enum에는 새 상수만 추가할 수 있다. 이 규칙을 어기면 `.hash` 불일치로 빌드가 깨진다. `Source-confirmed`

**생성 코드 관측.** ndk 백엔드를 빌드하면 중간 산출물에 버전 상수와 협상 함수가 박힌다.

```bash
# 빌드 후 생성된 ndk 스텁 헤더를 본다 (경로는 트리에 따라 다름)
find out/soong/.intermediates -path '*com.example.foo*ndk*' -name 'IFoo.h'
```

`예시 출력`(네 실제 빌드로 교체):

```cpp
// aidl::com::example::foo::IFoo (생성물, 발췌)
class IFoo : public ::ndk::ICInterface {
public:
  static const int32_t version = 2;                 // 이 백엔드가 구현한 버전
  virtual ::ndk::ScopedAStatus getInterfaceVersion(int32_t* _aidl_return);
  ...
  enum : int32_t {
    TRANSACTION_getValue = FIRST_CALL_TRANSACTION + 0,
    TRANSACTION_setValue = FIRST_CALL_TRANSACTION + 1,  // 끝에 추가 → 코드도 끝
  };
};
```

**버전 협상 관측.** 두 버전을 나란히 빌드해 v2 클라이언트가 v1 서버의 `setValue`를 부르면, 없는 트랜잭션이라 명시적 상태 코드가 돌아온다.

`예시 출력`(교체):

```cpp
::ndk::ScopedAStatus s = proxy->setValue(7);
// s.getStatus() == STATUS_UNKNOWN_TRANSACTION
// 안전한 패턴: 먼저 getInterfaceVersion()으로 원격 버전을 확인하고 분기
int32_t remoteVer = 0;
proxy->getInterfaceVersion(&remoteVer);   // v1 서버면 1
```

즉 스큐는 크래시나 침묵이 아니라 "이 원격은 그 메서드를 모른다"는 **읽을 수 있는 신호**로 표면화된다. 방어적 클라이언트는 새 메서드를 부르기 전에 `getInterfaceVersion()`으로 협상한다.

> **[그림 2]** v2 클라이언트가 v1 서버의 신규 메서드를 호출해 `STATUS_UNKNOWN_TRANSACTION`이 로그(logcat/콘솔)에 찍히고, 이어서 `getInterfaceVersion()`이 `1`을 반환하는 대조 캡처 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

뿌리는 Treble다. Android 8부터 system 파티션과 vendor 파티션은 서로 다른 주체가 서로 다른 주기로 업데이트한다. 그 둘이 Binder로 대화하려면 **바이너리 계약**에 합의해야 하는데, 옛날의 비구조화·무버전 AIDL은 계약을 코드 안에만 두어 한쪽만 바뀌면 조용히 어긋났다. `Source-confirmed`

Stable AIDL은 그 계약을 세 가지로 명시화한다. (1) 레이아웃을 `.aidl` 스냅샷으로 **기록**하고, (2) `.hash`로 **기계 검증** 가능하게 만들고(변경 시 빌드 실패), (3) 마샬링 코드를 네 언어로 **생성**해 양쪽이 같은 바이트 배치에 도달하도록 강제한다. 결과적으로 "무엇을 주고받기로 했는가"가 사람 기억이 아니라 트리에 박제된 지문이 된다. 이게 append-only 규칙과 버전 협상이 존재하는 이유다.

`@VintfStability`(또는 `stability: "vintf"`)는 이 못박음을 경계에 강제하는 스위치다. 이 표식이 붙은 인터페이스는 얼리지 않으면 vendor 경계를 넘는 빌드가 거부된다 — 계약 없는 크로스보더 통신을 원천 차단하려는 설계다. `Source-confirmed`

## 버전 차이와 한계

- **ndk_platform 백엔드는 없어졌다.** 과거 vendor용 `ndk_platform`과 앱용 `ndk`가 갈라져 있었으나, 지금은 `ndk` 하나로 통합됐다. 오래된 예제의 `ndk_platform`을 그대로 켜면 안 된다(통합 릴리스 시점은 트리 버전 확인 필요). `Reported`
- **Rust 백엔드**는 비교적 나중에 추가됐다 — 도입 API 레벨은 원문 재확인 필요. 안 켜져 있으면 `backend.rust.enabled`를 명시해야 한다. `Inferred`
- **한계 1**: `.hash`는 **구조**를 고정하지 구현의 **의미**를 고정하지 않는다. 같은 시그니처로 서버가 뜻을 바꿔 반환하면 hash는 그대로다 — 계약은 형(型) 계약이지 행동 계약이 아니다.
- **한계 2**: 기존 비구조화 Java parcelable을 stable 인터페이스에 끌어들이려면 `@JavaOnlyStableParcelable` 같은 브리지가 필요하고, 이 경우 java 외 백엔드에서의 안정성 보장이 제한된다 — 정확한 제약은 원문 재확인 필요. `Inferred`
- **한계 3**: 파일 디스크립터·바인더 객체 전달은 여전히 수명·권한 관리가 별도 주의 대상이다. Stable AIDL이 마샬링은 생성해도, 그 FD로 무엇을 열어줬는지의 권한 경계는 인터페이스 계약 밖이다.

## 정리

- Stable AIDL의 "안정"은 frozen 버전의 바이트 레이아웃을 `.hash`로 못박는 것이다. 백엔드는 그 계약의 언어별 구현일 뿐, 하나의 계약을 공유한다.
- 신뢰 경계는 Parcel이고, 구조화 parcelable + hash + append-only가 스큐와 손짠 마샬링 실수를 좁힌다. 스큐는 침묵이 아니라 `STATUS_UNKNOWN_TRANSACTION`으로 표면화된다.
- 네 백엔드의 갈림은 ABI다 — cpp는 system 내부, ndk는 안정 ABI로 경계를 넘고, rust는 파싱 경로의 메모리 안전을 더한다.
- `.hash`는 형 계약이지 행동 계약이 아니다. 의미 변화·FD 권한은 여전히 밖이다.

**점검 질문** — (1) cpp 백엔드와 ndk 백엔드를 나누는 결정적 차이는 무엇이고, vendor는 왜 ndk를 써야 하나? (2) 얼린 인터페이스에 새 메서드를 "중간에" 끼우면 무슨 일이 벌어지나? (3) v2 클라이언트가 v1 서버의 신규 메서드를 호출하면 어떤 신호가 오고, 그 전에 무엇을 확인해야 하나?

**참고** — [Stable AIDL](https://source.android.com/docs/core/architecture/aidl/stable-aidl) · [AIDL backends](https://source.android.com/docs/core/architecture/aidl/aidl-backends) · [AIDL(개념)](https://developer.android.com/develop/background-work/services/aidl) · AOSP `system/tools/aidl`

*다음 글: [HAL·VINTF·VTS](/posts/android-expert-p2c16/).*
