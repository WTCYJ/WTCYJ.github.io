---
layout: post
title: "PermissionManagerService·AppOpsService"
date: 2026-11-24 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, PermissionManagerService, AppOpsService, 런타임권한, system_server]
excerpt: "런타임 권한은 '부여됨' 상태만으로 통과되지 않는다. PermissionManagerService의 grant 플래그와 AppOpsService의 op 모드가 함께 AND로 평가되고, 앱이 위치를 못 받는데 크래시도 안 나면 십중팔구 appop이 MODE_IGNORED로 조용히 삼킨 것이다."
---

Android에서 "이 앱은 위치 권한이 있다"는 문장은 생각보다 애매하다. 사용자가 다이얼로그에서 허용을 눌렀고 `dumpsys`에도 `granted=true`가 찍히는데, 정작 앱은 위치를 못 받는다. 예외도 안 난다. 그냥 `null`이 온다. 이 조용한 실패의 뒤에는 두 개의 서비스가 있다 — 권한 부여 상태를 들고 있는 **PermissionManagerService**와, 실제 접근 순간을 게이팅하는 **AppOpsService**. 둘은 같은 결정을 두 겹으로 나눠 갖는다.

이 글은 system_server 안에서 권한이 어떻게 저장되고, 어느 지점에서 실제로 강제되며, 왜 "권한 부여"와 "접근 허용"이 별개인지를 AOSP 소스 경로와 함께 정리한 기록이다. 공격이 아니라 구조를 읽는다. 실습은 에뮬레이터와 자작 앱으로만 한다.

> **한 줄 결론**: 민감 자원 접근 여부는 앱 프로세스가 아니라 system_server에서, PermissionManagerService의 grant 상태와 AppOpsService의 op 모드를 **AND로** 묶어 판정한다. 권한을 부여한 채 appop만 IGNORED로 두면 앱은 예외 없이 빈 데이터를 받는다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 세 가지다. (1) 권한의 보호 수준(normal/dangerous/signature/special)과 런타임 권한이 어디에 저장되는가, (2) AppOpsService의 op 모드가 권한 위에 얹혀 무엇을 더 게이팅하는가, (3) `checkSelfPermission`부터 실제 접근까지의 호출 경로가 어느 Binder 서비스를 지나는가.

선수 개념은 앞선 장들에 깔려 있다. 권한과 op는 모두 **UID/패키지 단위**로 키가 잡히므로 앱 샌드박스와 UID 배정(11장 PackageManagerService에서 서명·UID 확정)을 전제한다. 그리고 앱에서 시스템 서비스로 넘어가는 모든 검사는 Binder를 탄다(14장 Binder proxy/stub). 이 두 가지가 없으면 "판정이 왜 앱 바깥에서 내려지는가"가 설명되지 않는다.

전체 흐름에서 이 장의 위치는 App → Framework(`PermissionManager`/`AppOpsManager`) → Binder → **system_server(PermissionManagerService·AppOpsService)** → 민감 서비스(LocationManagerService 등) → HAL/Kernel의 중간 관문이다. 권한은 그 관문의 정책 데이터이고, 실제 문은 자원 서비스가 연다.

## 핵심 개념 — 두 겹의 결정: grant와 op

권한 하나에는 **보호 수준(protectionLevel)** 이 붙는다. 이 값이 "언제, 어떻게 부여되는가"를 결정한다. `frameworks/base/core/java/android/content/pm/PermissionInfo.java`에 상수가 정의돼 있다. `Source-confirmed`

| 보호 수준 | 부여 시점 | 예 |
|--|--|--|
| normal | 설치 시 자동 | `INTERNET`, `VIBRATE` |
| dangerous | 런타임 다이얼로그(사용자 승인) | `ACCESS_FINE_LOCATION`, `RECORD_AUDIO`, `CAMERA` |
| signature | 정의한 앱과 **같은 서명 키**일 때만 자동 | 벤더/시스템 앱 간 사설 권한 |
| special (appop) | 설치·런타임 아님, **전용 설정 화면**에서 | `SYSTEM_ALERT_WINDOW`, `WRITE_SETTINGS`, `MANAGE_EXTERNAL_STORAGE` |

> `special`은 위 셋과 달리 `PermissionInfo`의 protectionLevel 상수가 아니다 — 개발자 문서상의 분류명이고, 실체는 `signature|appop` 플래그 조합이다(`PROTECTION_SPECIAL` 같은 상수는 없다). `Source-confirmed`

여기서 첫 번째 흔한 착각 — dangerous 권한이 "부여됨"이면 접근이 보장된다는 생각. 아니다. dangerous 권한의 상당수는 뒤에 대응하는 **appop**을 달고 있고, 실제 접근은 그 op 모드까지 통과해야 한다. AppOpsService의 op 모드는 다섯 가지다. `Reported`(상수값은 브랜치별 `AppOpsManager` 재확인)

| 모드 | 의미 | 앱이 겪는 것 |
|--|--|--|
| `MODE_ALLOWED` | 허용 | 정상 접근 |
| `MODE_IGNORED` | **조용히 거부** | 예외 없음, 빈/더미 데이터 |
| `MODE_ERRORED` | 거부 | `SecurityException` |
| `MODE_DEFAULT` | 권한 검사로 위임 | grant 상태를 따름 |
| `MODE_FOREGROUND` | 포그라운드일 때만 허용 | while-in-use 위치·마이크 |

`MODE_IGNORED`가 두 번째 함정이다. 권한을 revoke하지 않고 op만 ignore로 내리면 앱은 `SecurityException`을 못 받는다. try/catch로는 절대 안 잡힌다. 그래서 "권한 있는데 위치가 null"이라는 증상이 나온다. 이게 버그가 아니라 설계다 — 사용자가 권한을 껐다고 앱을 죽이면 안 되니, 프라이버시 계층은 조용히 삼키는 쪽을 택했다. `Inferred`

grant 상태는 어디 사는가. 런타임 권한 부여는 사용자별로 `/data/system/users/<id>/runtime-permissions.xml`에, appop 모드는 `/data/system/appops.xml`에 영속화된다. `Reported`(경로는 버전에 따라 이동 가능 — 원문 재확인) 재부팅해도 유지되는 이유가 여기 있다.

> **[그림 1]** 자작 앱에 대한 `adb shell dumpsys package com.example.myapp`의 runtime permissions 구간 — `granted=true`와 `flags=[...]`가 함께 찍힌 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 서브시스템의 신뢰 경계는 명확하다. **앱 프로세스는 신뢰되지 않는다.** 앱이 자기 안에서 `checkSelfPermission()`이 뭘 리턴하든, 그건 앱 스스로에게 알려주는 **참고용 조회**일 뿐이다. 실제 강제는 민감 자원을 쥔 서비스 쪽에서 일어난다. 앱이 자기 프로세스의 검사 결과를 조작해도 얻는 게 없는 이유 — 위치를 실제로 꺼내는 `LocationManagerService`가 호출 시점에 **다시** 권한과 op를 확인하기 때문이다. `Source-confirmed`

호출 경로를 따라가면 경계가 보인다. 앱의 `AppOpsManager`(`frameworks/base/core/java/android/app/AppOpsManager.java`)는 `IAppOpsService` AIDL로 Binder를 건너 system_server의 `AppOpsService`(`frameworks/base/services/core/java/com/android/server/appop/AppOpsService.java`)에 도달한다. `Source-confirmed`(경로 확인) 권한 쪽도 마찬가지로 `PermissionManager` → `IPermissionManager` → `PermissionManagerService`(`frameworks/base/services/core/java/com/android/server/pm/permission/`)를 탄다.

세 번째 착각을 여기서 정리한다 — 이름이 헷갈린다. **PermissionManagerService ≠ PackageManagerService.** 둘 다 흔히 "PMS"로 줄여 부르지만, 전자는 권한 부여 상태를, 후자는 패키지 설치·서명·UID를 관장한다. Android 10 무렵 권한 로직이 PackageManagerService에서 분리돼 나왔다. `Reported`

op 검사에는 세 종류의 진입점이 있고, 이 구분이 프라이버시 표시(인디케이터)와 연결된다. `checkOp`은 모드만 확인하고 기록하지 않는다. `noteOp`은 확인 + **1회 접근을 기록**한다(감사·마이크/카메라 점 표시 유발). `startOp`/`finishOp`은 마이크 녹음처럼 **지속되는** 접근의 활성 구간을 추적한다. `Reported`

## 관측

가설은 단순하다 — 자작 앱에서 위치 권한을 grant한 상태로 두고 appop만 `ignore`로 내리면, 앱은 크래시 없이 위치를 못 받는다. 에뮬레이터(userdebug)에서 `pm`과 `appops`로 두 계층을 따로 만져 본다.

```bash
# 1) 권한은 부여
adb shell pm grant com.example.myapp android.permission.ACCESS_FINE_LOCATION
# 2) 권한 상태 확인 (grant=true 기대)
adb shell dumpsys package com.example.myapp | sed -n '/runtime permissions/,/^$/p'
# 3) appop 모드 확인
adb shell cmd appops get com.example.myapp
# 4) op만 조용히 거부로 내림 (권한은 그대로)
#    COARSE도 함께 내려야 완전한 null — FINE만 막으면 LocationManagerService가
#    남은 COARSE(allow)로 대략 위치를 낮춰 넘겨서 null이 아니라 저정밀 좌표가 온다
adb shell cmd appops set com.example.myapp COARSE_LOCATION ignore
adb shell cmd appops set com.example.myapp FINE_LOCATION ignore
# 5) 다시 확인 — 권한 granted=true 인데 두 op는 ignore
adb shell cmd appops get com.example.myapp
```

> **[그림 2]** 4번 실행 후 `adb shell cmd appops get`에서 `COARSE_LOCATION: ignore`·`FINE_LOCATION: ignore`가 찍혔는데도 `dumpsys package`의 권한은 `granted=true`로 남은 대조 캡처 — *실측 스크린샷 자리*

`예시 출력`(네 실제 실행으로 교체):

```
# 3) 초기: 부여됨 + 허용
$ adb shell cmd appops get com.example.myapp
COARSE_LOCATION: allow
FINE_LOCATION: allow

# 5) 두 op를 ignore로 내린 뒤
$ adb shell cmd appops get com.example.myapp
COARSE_LOCATION: ignore
FINE_LOCATION: ignore
```

권한 계층(`dumpsys package`)은 여전히 `granted=true`인데 op 계층(`cmd appops`)은 `ignore`다. 앱을 다시 실행하면 위치 콜백에 `null`이 오고 로그엔 아무 예외도 없다 — 단, 이 완전한 `null`은 COARSE·FINE **두 op를 모두** ignore로 내렸을 때다. COARSE를 allow로 남기면 앱은 null이 아니라 대략 위치(저정밀 좌표)를 받는다(fine-only로 요청한 앱이라면 그때도 null). 두 계층이 별개라는 것, 그리고 **더 조이는 쪽이 이긴다**는 것이 이 관측의 요점이다.

## Root Cause — 왜 이렇게 되는가

왜 하나로 안 하고 두 겹으로 나눴나. 권한(grant)은 "사용자가 이 앱에 이 능력을 준다"는 **비교적 정적인 정책**이다. 반면 op는 "지금 이 순간 이 앱이 실제로 자원을 만지는 것을 허용하느냐"는 **동적·시점적 게이트**다. while-in-use(포그라운드에서만), 1회 허용, 데이터 접근 감사, 사용자 토글(마이크·카메라 전체 차단) 같은 기능은 grant 하나로는 표현이 안 된다. 그래서 AppOps라는 두 번째 축이 얹혔다. `Inferred`

실제 접근 판정은 자원 서비스에서 **AND**로 합쳐진다. 위치를 예로 들면, `LocationManagerService`가 위치를 넘기기 전에 (a) 권한이 grant됐는지, (b) 대응 appop이 허용(또는 포그라운드 조건 충족)인지를 함께 본다. 둘 중 하나라도 막히면 접근이 끊긴다. `Source-confirmed`(위치가 appop을 검사한다는 사실) 그리고 이 판정이 앱 밖(system_server/서비스)에서 일어나기 때문에, 앞서 말한 대로 앱이 자기 검사 결과를 위조해도 소용이 없다.

op가 예외 대신 빈 값을 주는 것(`MODE_IGNORED`)도 근본은 같다. 프라이버시 제어는 "능력을 뺏는" 게 아니라 "결과를 무해하게 만드는" 방향으로 설계됐다. 권한을 껐다고 앱이 죽으면 사용자 경험이 망가지고, 앱이 죽는지 여부로 "권한이 꺼졌는지"를 역탐지할 수도 있다. 조용히 삼키면 그 사이드 채널이 준다. `Inferred`

## 버전 차이와 한계

권한 모델은 릴리스마다 꾸준히 조여졌다. 아래는 방향성이고, 구체 API·상수·정확한 클래스 위치는 대상 브랜치에서 재확인해야 한다.

- **API 23(6)**: 런타임 권한(dangerous) 다이얼로그 도입 — 이전엔 설치 시 일괄 부여였다. `Reported`
- **API 29(10)**: while-in-use(포그라운드 위치), `ACCESS_BACKGROUND_LOCATION` 분리. 권한 정책·UI의 상당 부분이 Mainline **PermissionController** 모듈(`com.android.permission`)로 이동 시작 — 이 때문에 정책 코드가 프레임워크 소스에만 있지 않다(23장 APEX/Mainline과 연결). `Reported`
- **API 30(11)**: 1회 허용, 미사용 앱 권한 자동 재설정, scoped storage. `Reported`
- **API 31(12)**: 대략 위치(approximate), 마이크·카메라 전역 토글과 사용 인디케이터, 접근 감사(attribution tag). `Reported`
- **API 33(13)**: `POST_NOTIFICATIONS` 런타임 권한, 미디어 세분화(`READ_MEDIA_IMAGES` 등). `Reported`
- **API 34(14)**: 사진·동영상 부분 접근(`READ_MEDIA_VISUAL_USER_SELECTED`). `Reported`

한계도 분명하다. 에뮬레이터로는 op 게이팅·grant 저장·`dumpsys`/`appops` 관측이 전부 재현되지만, TEE/StrongBox에 뿌리를 둔 하드웨어 신뢰나 특정 벤더 앱의 signature 권한 관계는 그 서명 키가 없으면 관측되지 않는다. `signature` 권한은 런타임에 묻지 않고 **설치 시 서명 일치로 정적 결정**되므로, `appops`로 흔들리지 않는다는 점도 기억할 것.

## 정리

- 민감 자원 접근은 권한(grant)과 appop(op 모드)의 **AND**로, 앱이 아닌 system_server/자원 서비스에서 판정된다.
- `MODE_IGNORED`는 예외가 아니라 **조용한 거부**다 — "권한 있는데 데이터가 비었다"의 단골 원인.
- PermissionManagerService(권한 상태)와 PackageManagerService(설치·서명)는 이름만 비슷한 별개 서비스다.
- 관측은 `dumpsys package`(권한 계층)와 `cmd appops`(op 계층)를 **따로** 봐야 진실이 보인다.

**점검 질문** — (1) 권한이 `granted=true`인데 앱이 위치를 못 받고 예외도 없다. 어느 계층의 어떤 모드를 의심하고, 어떤 명령으로 확인하나? (2) `checkSelfPermission()` 결과를 앱이 위조해도 무의미한 이유를 신뢰 경계로 설명하라. (3) `noteOp`과 `checkOp`의 차이는 무엇이며, 그 차이가 프라이버시 인디케이터와 어떻게 연결되나?

**참고** — [권한 개요(developer.android.com)](https://developer.android.com/guide/topics/permissions/overview) · [AOSP 권한 문서](https://source.android.com/docs/core/permissions) · [AppOpsService 소스(cs.android.com)](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/base/services/core/java/com/android/server/appop/AppOpsService.java) · [PermissionManager 레퍼런스](https://developer.android.com/reference/android/permission/PermissionManager)

*다음 글: [WindowManagerService·UI 보안](/posts/android-expert-p2c13/).*
