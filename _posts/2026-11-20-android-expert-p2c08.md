---
layout: post
title: "ART interpreter/JIT/AOT/dex2oat"
date: 2026-11-20 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ART, dex2oat, JIT, AOT]
excerpt: "흔한 오해가 하나 있다 — ART가 설치할 때 앱을 전부 컴파일한다는 것. Android 7.0부터는 아니다. 설치 시점엔 컴파일하지 않고, JIT가 프로파일을 모으는 동안 인터프리트하다가 유휴·충전 시 dex2oat가 hot 메서드만 AOT한다. 그리고 .oat 네이티브 코드는 실행 시 검증을 다시 하지 않으므로, oat/vdex 무결성이 곧 실행 신뢰의 경계다."
---

앱을 뜯어보면 결국 마주치는 질문이 있다 — 이 dex 바이트코드는 기기 위에서 정확히 무엇으로, 언제 변환되어 돌아가는가. 답을 인터프리터/JIT/AOT 중 하나로 뭉뚱그리면 관측이 어긋난다. 같은 APK라도 방금 설치한 직후, 하룻밤 재운 뒤, OTA 직후가 서로 다른 실행 형태를 갖기 때문이다. 이 차이를 모르면 "왜 어제는 후킹이 먹혔는데 오늘은 네이티브 코드로 뛰느냐" 같은 혼란에 빠진다.

이 글은 Android Runtime(ART)의 실행 파이프라인 — 인터프리터, JIT, dex2oat AOT — 이 어떻게 맞물리고, 그 산출물(.oat/.vdex/.art)이 어디에 어떤 신뢰 경계로 놓이는지를 AOSP·공식 문서 기준으로 정리하고 에뮬레이터에서 관측한 기록이다.

> **한 줄 결론**: Android 7.0부터 ART는 설치 시 전체 AOT를 하지 않는다. 인터프리트+JIT로 실행하며 프로파일을 모으고, 유휴·충전 시 dex2oat가 프로파일 기반으로 hot 메서드만 AOT한다. 그 산출물인 .oat 네이티브 코드는 런타임 검증을 건너뛰므로, oat/vdex의 무결성이 곧 실행 신뢰의 경계다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 범위는 ART의 세 실행 모드(인터프리터·JIT·AOT), 이들을 잇는 프로파일 유도 컴파일(PGC), 컴파일러 드라이버 dex2oat와 그 산출 파일들, 그리고 컴파일을 트리거하는 프레임워크 경로(PackageManagerService → installd[Android 13 이하]/artd[Android 14+ ART Service] → dex2oat)다. 커널·HAL은 다루지 않고, 앱이 실제로 실행되는 **런타임 계층**과 그 위쪽(system_server)의 dexopt 스케줄링에 집중한다.

선수 지식은 세 가지다. 첫째, dex 바이트코드가 무엇이고 클래스가 로더를 통해 올라온다는 것(다음 9장 ClassLoader가 이어받는다). 둘째, 앱이 각자 독립 프로세스로 뜨고 그 프로세스 주소 공간에서 코드가 실행된다는 프로세스 모델. 셋째, 네이티브(ELF) 코드와 JNI의 존재 — .oat가 결국 ELF라는 사실이 여기서 걸린다(20장 bionic·linker·ELF·JNI). 이 셋이 없으면 "AOT 코드가 왜 앱 권한으로 직접 뛰는가"가 와닿지 않는다.

전체 구조에서 ART는 App 계층 바로 아래, Kernel 위에 있다. 앱의 Java/Kotlin 코드는 dex로 컴파일되고, 그 dex를 기기에서 실행하는 주체가 ART다. 설치와 유휴 시 컴파일을 부르는 쪽은 system_server의 PackageManagerService이며, 실제 컴파일은 네이티브 데몬(Android 13 이하는 installd, Android 14+는 ART Service의 artd)이 dex2oat를 fork해 수행한다. `Source-confirmed`

## 핵심 개념 — 세 실행 모드와 산출 파일

ART는 한 가지 방식으로만 코드를 돌리지 않는다. 같은 메서드가 생애주기 동안 세 형태를 오간다.

- **인터프리터** — dex 바이트코드를 그대로 해석 실행한다. 현행 ART의 기본 인터프리터는 어셈블리로 작성된 고속 인터프리터 **nterp**로, 예전 mterp를 대체했다(기본화 정확 버전은 Android 11~12대, 원문 재확인 필요). `Reported`
- **JIT(Just-In-Time)** — 자주 실행되는 메서드가 임계치를 넘으면 런타임에 네이티브로 컴파일해 캐시하고, 동시에 어떤 메서드/클래스가 hot인지 **프로파일**로 기록한다. `Source-confirmed`
- **AOT(Ahead-Of-Time)** — dex2oat가 미리 네이티브 코드로 컴파일해 파일로 남긴다. 실행 시 컴파일 비용이 없다. `Source-confirmed`

이 셋을 잇는 축이 프로파일 유도 컴파일이다. JIT가 모은 프로파일을 근거로, dex2oat는 앱 전체가 아니라 hot 메서드만 골라 AOT한다. 그래서 설치는 빠르고, 저장 공간은 아끼며, 정상 상태 성능은 챙긴다.

dex2oat의 산출물은 앱별 oat 디렉터리에 세 파일로 떨어진다. `Source-confirmed`

| 파일 | 내용 | 성격 |
|--|--|--|
| `base.odex` | 컴파일된 네이티브 코드 컨테이너. 내부에 **.oat 섹션**(ELF)이 들어 있다 | 실행 코드 |
| `base.vdex` | 검증(verify)을 마친 dex 원본 + 검증 메타데이터 | 검증 결과 캐시 |
| `base.art` | 미리 초기화한 힙 객체/내부 클래스 표현 이미지 | 시작 가속 |

흔한 착각 — ".oat만 있으면 실행된다"가 아니다. .oat는 자기가 어느 dex(체크섬)로부터, 어떤 부트 이미지 위에서, 어떤 클래스 로더 컨텍스트로 컴파일됐는지를 헤더에 박아 둔다. 런타임이 이 값들을 대조해 하나라도 어긋나면 .oat를 버린다. `Source-confirmed` vdex는 그때 "다시 검증하지 않고 인터프리트로 폴백"할 근거가 되므로, .oat 없이도 앱은 돈다 — 느릴 뿐이다.

부트 클래스패스(프레임워크)는 별도로 `boot.art`/`boot.oat` 부트 이미지로 미리 컴파일된다. 정확한 위치는 버전·설정에 따라 `/apex/com.android.art/` 또는 `/data/dalvik-cache/<isa>/`로 갈린다(원문 재확인 필요). `Inferred`

> **[그림 1]** AVD에서 `ls -l /data/app/.../oat/x86_64/`로 `base.odex`·`base.vdex`·`base.art` 세 파일과 각 크기를 확인한 터미널 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

ART 실행 모드 자체는 권한 경계가 아니다. 세 모드 모두 **앱 프로세스 안에서, 앱의 UID·권한으로** 실행된다. 그러나 보안상 결정적인 사실이 하나 있다 — AOT로 만든 .oat 네이티브 코드는 실행 시점에 바이트코드 검증을 다시 하지 않는다. 검증은 컴파일 시점에 한 번 수행돼 vdex에 결과가 기록되고, 이후엔 그 결과를 신뢰한다. `Source-confirmed`

여기서 위협 모델이 선다. 만약 공격자가 앱의 oat 디렉터리에 조작된 .oat를 심을 수 있다면, **검증을 우회한 네이티브 코드**가 그 앱 권한으로 직접 뛴다. 이를 막는 방어는 두 겹이다.

1. **쓰기 차단** — oat 디렉터리와 dalvik-cache는 system 소유이고, SELinux 도메인(`dex2oat`, `installd`, `dalvikcache_data_file` 라벨)으로 앱의 직접 쓰기가 막힌다. 앱은 자기 oat를 만들 수 없다. `Source-confirmed`
2. **사용 시 검증** — 앞서의 dex 체크섬·부트 이미지 체크섬·클래스 로더 컨텍스트(CLC) 대조. 스테일하거나 다른 classpath에서 만든 .oat는 자동으로 거부된다. `Source-confirmed`

반대 방향의 공격면도 있다. dex2oat는 앱이 제출한 **신뢰할 수 없는 dex**를 파싱·컴파일한다. 그래서 dex2oat는 제한된 SELinux 도메인에서 fork되어 격리된다. dex/oat 파서의 메모리 안전 이슈는 이 클래스의 전형적 표적이다(구체 CVE 귀속은 원문 재확인 필요, 여기서는 이미 공개된 방어 구조만 다룬다). `Inferred`

정리하면, ART의 보안 경계는 "누가 oat를 쓸 수 있는가"와 "런타임이 oat를 신뢰하기 전에 무엇을 대조하는가"에 있다. 실행 모드가 아니라 파일 무결성이 경계다.

## 관측 — AVD에서 dexopt 상태 확인

전부 **로컬 AVD(google_apis userdebug)와 자작 앱**으로만 확인한다. 제3자·실서비스 앱은 대상이 아니다. 아래는 실행 상태를 바꾸지 않고 읽기만 하는 명령과, 컴파일을 수동 트리거하는 명령이다.

```bash
# 1) reason별 기본 컴파일러 필터 (system property)
adb shell getprop | grep pm.dexopt
#   [pm.dexopt.install]: [speed-profile]
#   [pm.dexopt.bg-dexopt]: [speed-profile]
#   [pm.dexopt.first-boot]: [verify]  ...

# 2) 특정 앱의 현재 dexopt 상태 (filter / reason)
adb shell dumpsys package dexopt | grep -A2 com.example.myapp

# 3) 수동으로 speed 컴파일 강제 (자작 앱)
adb shell cmd package compile -m speed -f com.example.myapp

# 4) 프로파일 위치 확인 (userdebug)
adb shell ls /data/misc/profiles/cur/0/com.example.myapp/
adb shell ls /data/misc/profiles/ref/com.example.myapp/
```

`예시 출력(교체)` — 실제 실행으로 교체:

```
$ adb shell dumpsys package dexopt | grep -A2 com.example.myapp
  [com.example.myapp]
    path: /data/app/~~abc.../com.example.myapp-xyz.../base.apk
      x86_64: [status=speed-profile] [reason=bg-dexopt] [primary-abi]

$ adb shell cmd package compile -m speed -f com.example.myapp
Success
```

`status`가 컴파일러 필터(무엇으로 컴파일됐나), `reason`이 트리거(왜 컴파일됐나)다. 위 `getprop`에서 보듯 `install` 필터 자체는 `speed-profile`이지만, 갓 설치한 자작 앱은 baseline/cloud 프로파일이 없어 AOT할 hot 메서드가 하나도 없으므로 실질적으로 `verify`와 동등하게 시작한다. 그래서 방금 설치한 앱은 `reason=install`·`status=verify` 근처로 시작했다가, 앱을 쓰고 하룻밤 두면 `bg-dexopt`가 돌며 프로파일이 쌓여 `speed-profile`로 바뀐다. 이 전이를 눈으로 보는 것이 이 관측의 핵심이다. `Source-confirmed`

컴파일러 필터의 의미는 아래와 같다. `Source-confirmed`

| 필터 | 무엇을 하나 |
|--|--|
| `verify` | dex 검증만. AOT 컴파일 없음(설치 직후 기본) |
| `speed` | 대부분의 메서드를 AOT |
| `speed-profile` | 프로파일에 오른 hot 메서드만 AOT |
| `everything` | 모든 메서드 AOT(디버그·측정용) |

> **[그림 2]** 같은 자작 앱에 대해 `dumpsys package dexopt`를 (a) 설치 직후와 (b) `cmd package compile -m speed-profile` 실행 후 두 번 찍어 `status`가 `verify`→`speed-profile`로 바뀐 것을 대조한 캡처 — *실측 스크린샷 자리*

## Root Cause — 왜 이런 하이브리드가 됐나

이 구조는 세 요구의 충돌을 조정한 결과다. **설치 속도**, **저장 공간·배터리**, **정상 상태 실행 성능** — 이 셋을 한 방식으로 동시에 만족할 수 없다.

- Android 5.0~6.0은 설치 시점에 dex2oat로 앱 전체를 AOT했다. 정상 상태 성능은 좋지만 설치가 느리고 저장 공간을 많이 먹었으며, OTA마다 모든 앱을 재컴파일했다. `Reported`
- 순수 JIT는 설치가 빠르지만 실행마다 워밍업 비용을 다시 치르고 배터리를 쓴다.

Android 7.0(Nougat)의 하이브리드는 이 둘을 시간축으로 분리한다. **설치 순간엔 컴파일하지 않는다**(빠른 설치). 앱을 쓰는 동안 JIT가 hot 메서드를 컴파일하며 프로파일을 쌓는다. 기기가 **유휴·충전 상태**일 때 백그라운드 dexopt가 그 프로파일을 dex2oat에 먹여, 자주 쓰이는 코드만 골라 AOT한다. `Source-confirmed` 즉 "전부 미리 컴파일"에서 "실제로 쓰는 것만, 나중에, 눈에 안 띌 때 컴파일"로 바뀐 것이다. 앞서 본 "설치 직후 앱과 하룻밤 재운 앱의 실행 형태가 다르다"는 관측이 바로 이 설계의 직접 결과다.

## 버전 차이와 한계

- **Dalvik(≤ Android 4.4)** → 레지스터 기반 VM + 트레이스 JIT. Android 5.0에서 ART가 Dalvik을 대체했다(4.4는 실험적 옵트인). `Source-confirmed`
- **전체 AOT(5.0~6.0)** → 설치 시 완전 컴파일.
- **하이브리드(7.0+)** → 인터프리트 + JIT + 프로파일 유도 AOT. dex2oat가 프로파일을 소비.
- **프로파일 부트스트랩(9.0+/11+)** → JIT 수집을 기다리지 않고 speed-profile을 시작시키는 두 경로. Play가 배포하는 **Cloud Profile**(설치 시 집계 프로파일)과, APK/AAB에 동봉해 `androidx.profileinstaller`가 설치하는 **Baseline Profile**(`assets/dexopt/baseline.prof`). `Reported`
- **ART Mainline(APEX)** → dex2oat와 런타임, 부트 이미지가 업데이트 가능한 ART APEX(`com.android.art`)로 배포되어 Play로 갱신된다(정확 도입 버전은 23장 APEX 참조, 원문 재확인). `Reported`

한계도 분명하다. AVD에서 `dumpsys package dexopt`·`cmd package compile`·프로파일 파일까지는 관측되지만, 이는 실행 형태의 관측일 뿐 컴파일 결과의 정합성 자체를 증명하진 않는다. 정합성은 런타임의 체크섬·CLC 대조에 맡겨진다. 또한 `oatdump` 같은 심층 도구는 userdebug 이미지에서만 안정적으로 붙는다(이미지 종류 확인 필요). `Inferred`

## 정리

- ART는 인터프리터(nterp)·JIT·AOT를 시간축으로 오가며, Android 7.0부터 설치 시점엔 컴파일하지 않고 프로파일을 모아 유휴 시 hot 메서드만 AOT한다.
- dex2oat 산출물은 base.odex(내부 .oat ELF)·base.vdex(검증 캐시)·base.art(시작 이미지) 셋이며, 앱별 oat 디렉터리에 system 소유로 저장된다.
- .oat는 런타임 재검증을 건너뛰므로 oat/vdex 무결성이 실행 신뢰의 경계다 — 쓰기는 SELinux로 막고, 사용 전엔 dex 체크섬·부트 이미지·CLC를 대조한다.
- 상태는 `dumpsys package dexopt`(status=필터, reason=트리거)로 읽고, `cmd package compile`로 수동 트리거해 전이를 관측할 수 있다.

**점검 질문** — (1) 방금 설치한 앱과 하룻밤 지난 앱의 `status`가 왜 다를 수 있는가? (2) ART가 이미 존재하는 .oat를 실행하기 전에 대조하는 값 세 가지는 무엇인가? (3) speed와 speed-profile 필터의 차이는, 그리고 speed-profile이 무엇에 의존하는가?

**참고** — [ART 및 Dalvik](https://source.android.com/docs/core/runtime) · [ART 컴파일 구성/dexopt](https://source.android.com/docs/core/runtime/configure) · [JIT 컴파일러](https://source.android.com/docs/core/runtime/jit-compiler) · [Baseline Profiles](https://developer.android.com/topic/performance/baselineprofiles/overview) · [installd/dex2oat 소스(AOSP frameworks/native/cmds/installd)](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/native/cmds/installd/)

*다음 글: [ClassLoader·dynamic code loading](/posts/android-expert-p2c09/).*
