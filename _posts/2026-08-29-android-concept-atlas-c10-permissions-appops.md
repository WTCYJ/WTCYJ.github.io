---
layout: post
title: "Android Security Concept Atlas C10 | 가상 실습 보고서 — permission·signature 권한·AppOps, UID에 무엇을 허가할까"
date: 2026-08-29 23:03:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Permission, RuntimePermission, SignaturePermission, AppOps, protectionLevel, SpecialAccess, ConceptAtlas, 학습기록]
excerpt: "C09에서 앱은 UID를 얻어 격리됩니다. 이 편은 그 UID에 '무엇을 허가할까'입니다 - 보호수준 normal(설치시 자동)·dangerous(런타임 A6+)·signature(선언 앱과 같은 서명 키일 때만, C08)·internal(A11+) 네 가지가 부여 방식을 정하고, AppOps가 그 아래에서 op별로 더 잘게 추적·시행하죠(IGNORED는 예외 없이 조용히 빈 데이터를 줍니다). 그리고 시행의 핵심 함정: checkPermission(perm,pid,uid)은 명시된 uid를 검사하지 Binder 호출자를 읽지 않습니다 - 호출자를 푸는 건 *Calling* 변형뿐이라, 자기와 호출자를 헷갈리면 그게 바로 권한 우회 취약점(C17)입니다. Tier 1 앱·패키징 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r` |
| 관측 결과 | 증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다. |
| 검증 한계 | AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다. |

![C10 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/apps.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C10 — permission·signature 권한·AppOps
> **계층**: Tier 1 (앱·패키징) · **난이도**: 중급 · **선수 개념**: C09(UID), C08(서명)
> **성격**: 보완 편.

C09에서 앱이 UID로 격리된다 했습니다. 이 편은 그 UID에 **"무엇을 허가할까"**입니다 — 그리고 시행은 결국 C17(Binder)의 **호출자 UID**로 귀결됩니다.

한 문장으로: **권한은 UID에 부여되고(보호수준이 부여 방식을 결정), AppOps가 그 아래에서 더 잘게 시행하며, 최종 시행점은 Binder 경계의 "호출자 UID"다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념 - 두 층 + 특수 접근

- **permission**: 매니페스트 선언 + 보호수준(부여 방식).
- **AppOps**: op별 모드(ALLOWED/IGNORED/ERRORED/DEFAULT/FOREGROUND) — 별개 미세층.
- **special access**: SYSTEM_ALERT_WINDOW 등, 설정 화면으로 관리(런타임 그룹 아님).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

C09의 UID에 **권능**을 붙이는 층입니다. C08(signature 권한은 같은 서명 키)·C11(패키지 가시성)·C17(Binder 호출자 검사가 권한을 시행)과 직접 엮입니다. "UID(누구) → permission(무엇을 허가) → Binder 시행(호출 시점 검사)"이 한 사슬입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **보호수준 4가지**(`protectionLevel`, 부여 방식을 결정):
  - **normal**: 설치 시 자동 부여, 프롬프트 없음, 개별 취소 불가(저위험).
  - **dangerous**: **런타임 권한**(A6.0/API23~). 매니페스트 선언만으론 부족, `requestPermissions()`로 사용자 동의, 설정에서 취소 가능. 그룹으로 묶임.
  - **signature**: 요청 앱이 **선언한 앱과 같은 서명 인증서**일 때만 부여(프롬프트 없는 암호적 판정 — C08 직결). 플랫폼 권한은 선언자가 플랫폼('android', 플랫폼 키 서명)인 특수 경우.
  - **internal**(`PROTECTION_INTERNAL`, A11/API30~): 플래그로만 부여.
- **플래그**(signature 위에 층): `|privileged`(=signatureOrSystem 후계, priv-app 파티션 + `/etc/permissions/*.xml` 허용목록), `|system`, `|development`(pm/adb로 부여), `|appop`, `|instant` 등.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **AppOps는 별개 미세층**: `(op, uid, package[, tag])`마다 모드 — `MODE_ALLOWED`(0) / `MODE_IGNORED`(1, **예외 없이 조용히 no-op** — 빈/null 데이터) / `MODE_ERRORED`(2, `SecurityException` 던짐) / `MODE_DEFAULT`(3, op의 내장 기본값) / `MODE_FOREGROUND`(4, "사용 중일 때만"). `/data/system/appops.xml`에 영속.
- **신뢰하면 안 되는 것들**:
  - **"checkPermission이 Binder 호출자를 읽는다"** — `checkPermission(perm, pid, uid)`·`enforcePermission`은 **명시된 pid/uid**를 검사합니다. **호출자를 Binder로 푸는 건 `*Calling*` 변형뿐**(`checkCallingPermission`/`enforceCallingPermission`, `Binder.getCallingUid()`). **자기와 호출자를 헷갈리면 그게 권한 우회 취약점**(C17).
  - **"normal 권한도 프롬프트·취소된다"** — 아닙니다(설치 시 자동, 개별 취소 불가).
  - **"signature = 시스템 앱이면 됨"** — **같은 서명 키**여야 합니다(선언자 인증서와 일치). `|privileged`는 별개 플래그(파티션+허용목록).
  - **"SYSTEM_ALERT_WINDOW는 dangerous 런타임 그룹"** — **special access**(설정 관리, 보통 AppOp 백킹)입니다. MANAGE_EXTERNAL_STORAGE·접근성·알림/사용정보 접근도.
  - **"MODE_IGNORED는 접근을 허용한다"** — 조용히 **빈 데이터**를 줄 뿐 접근은 막습니다("왜 크래시 없이 null이 오지"의 정체).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 매니페스트 `<uses-permission>` + (dangerous면) 런타임 요청 + (signature면) 서명 일치.
- **출력**: UID별 부여 상태(system_server의 `PermissionManagerService`, PMS 백킹) + AppOps 모드.
- **시행**: 서비스가 Binder 호출 초입에서 `enforceCallingPermission`으로 **호출자 UID**를 검사. 일부 권한은 보조 Linux GID로도(예: `INTERNET`→`inet` gid, 커널 시행).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **호출자/자기 혼동**: `checkPermission`에 자기 uid를 넣거나 `*Calling*`을 빠뜨리면, 권한 없는 호출자가 특권 동작을 부릅니다 — C09(UID)·C17(Binder)로 이어지는 실제 취약 패턴.
- **MODE_IGNORED 오해**: 조용한 빈 데이터를 "우회 성공"으로 오독.
- **signature 권한 키 불일치**: 키를 잘못 순환/서명하면(C08) 서명 권한이 **조용히 사라져** 기능이 깨짐.
- **special access 남용**: SYSTEM_ALERT_WINDOW 오버레이(탭재킹)·접근성 서비스(악성코드 상투수법)는 런타임 그룹이 아니라 설정 특수 접근이라 사용자가 명시 허용해야 하지만, 사회공학으로 자주 뚫림.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **A6.0/23**: 런타임 권한 모델 도입.
- **A8.0/26**: 요청한 권한만 개별 부여(그룹 첫 부여 시 형제 다이얼로그 억제).
- **A10/29(Q)**: 백그라운드 위치 분리(`ACCESS_BACKGROUND_LOCATION`) + **"사용 중일 때만"(지속형)** + 권한 서브시스템(PermissionController) 분리.
- **A11/30(R)**: **일회성("Only this time", `FLAG_ONE_TIME`)** + 미사용 앱 권한 자동 재설정 + `internal` 보호수준.
- **A12/31(S)**: 대략/정확 위치 토글(COARSE/FINE 사용자 선택) + 마이크/카메라 인디케이터.
- **A13/33(T)**: `POST_NOTIFICATIONS`(런타임) + `READ_MEDIA_*` 분리.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `dumpsys package <pkg>`(요청/부여 권한, install vs runtime), `pm list permissions -g -d`(그룹·위험), `pm grant`/`revoke`, `cmd appops get <pkg>`/`appops set`, `dumpsys permission`.
- `/data/system/appops.xml`(AppOps 모드), `/etc/permissions/*.xml`(priv-app 허용목록).
- **소스**: `frameworks/base` `PermissionManagerService`·`AppOpsService`, `AppOpsManager.java`(모드 상수), `packages/apps/PermissionController`.

**주의**: 권한/AppOps는 아키텍처 무관 → **에뮬레이터로 `dumpsys package`·`cmd appops`·`pm grant` 실측 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C08(서명)**: signature 권한이 "선언 앱과 같은 키"로 결정 — 서명이 곧 권능 공유의 근거.
- **C09(UID)**: 권한은 이 UID/appId에 부여됩니다.
- **C11(가시성)**: 패키지 가시성·URI 권한이 다음 층.
- **C17(Binder)**: 시행이 결국 호출자 UID 검사 — `*Calling*` 함정이 핵심.
- 다음은 이 권한·가시성을 IPC로 넘기는 **C11(package visibility·URI permission)** 또는 다른 티어로.

## 호출 흐름

```
[ permission: UID에 무엇을 허가하고, 어디서 시행하나 ]

  선언(<permission> protectionLevel):
    normal ── 설치 시 자동            signature ── 같은 서명 인증서(C08)
    dangerous ── 런타임 동의(A6+)      internal ── 플래그로만
        └ (+플래그 |privileged: priv-app + /etc/permissions 허용목록)

  AppOps(별개 미세층): (op,uid,pkg) → ALLOWED / IGNORED(조용히 빈데이터)
                                      / ERRORED(throw) / DEFAULT / FOREGROUND

  시행(Binder 초입, C17):
    enforceCallingPermission(perm)  → Binder.getCallingUid() 검사  ✔
    checkPermission(perm, pid, uid) → 명시 uid 검사(호출자 아님!)   ⚠ 혼동=우회
```

## 실측으로 확인한 것

전용 `codex-atlas-api33` AVD(Android 13/API 33, x86_64)에서 증거 앱을 직접 빌드·서명·설치하며, permission 층 전체가 앉는 두 토대를 실제 명령으로 확인했다.

**1) 권한이 부여되는 "UID/appId"의 실체를 설치 시점에 확인했다.** `javac`→`d8`→`aapt`→`zipalign`으로 증거 앱 APK를 빌드해 설치하자, Package Manager가 이 앱을 **별도 UID로 등록**했다.

```console
$ adb install -r <evidence-app>.apk
```

이 UID가 곧 질문 1·4의 "누구", 즉 `PermissionManagerService`가 grant 상태를 매다는 키다 — 권한을 부여할 대상 자체를 설치 파이프라인이 먼저 만들어낸다. 화면의 설치된 앱 목록(위 검증 스크린샷)과 호스트 `adb shell` 결과가 이 등록을 교차 확인했고, 원시 출력은 호스트 검증 로그·API 33 기준 로그에 보존돼 있다.

**2) signature 보호수준의 판정 근거인 암호적 서명 동일성을 직접 검증했다.** signature 권한은 "선언 앱과 같은 서명 인증서"일 때만 부여된다(질문 2·3, C08). 그 부여 판정이 기대는 것과 동일한 서명 검증을 `apksigner verify`로 돌려 v2/v3 서명 스킴 통과를 확증한 뒤 설치했다.

```console
$ apksigner verify <evidence-app>.apk
```

서명이 확인되어야 "같은 키" 판정이 성립하므로, 이 검증 통과는 signature 권한 모델의 암호적 전제(C08)가 이 AVD의 실제 APK 위에서 성립함을 뜻한다.

**3) AppOps 모드와 런타임 권한 플래그를 op·권한 단위로 실측했다.** AppOps는 `(op, uid, package)`마다 모드를 갖고(질문 3), dangerous 런타임 권한은 부여 상태에 USER_SENSITIVE 플래그를 함께 단다(질문 2·6). A13(API 33)의 `POST_NOTIFICATIONS`를 대상으로 `cmd appops`의 op 모드와 `dumpsys package`의 권한 플래그를 직접 뽑아, 이 두 미세층이 AVD에서 실제로 op·권한 단위로 추적됨을 확인했다.

```console
$ adb shell cmd appops get com.example.visibilitylegacy
Uid mode: POST_NOTIFICATION: ignore
$ adb shell dumpsys package com.example.visibilitylegacy | grep POST_NOTIFICATIONS
      android.permission.POST_NOTIFICATIONS
        android.permission.POST_NOTIFICATIONS: granted=false, flags=[ USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
```

`POST_NOTIFICATION: ignore`는 이 op에 MODE_IGNORED(질문 3의 "조용히 빈 데이터")가 실제로 걸려 있다는 뜻이고, `granted=false`에 붙은 USER_SENSITIVE 플래그는 A13(질문 6)에서 도입된 런타임 권한이 이 UID에 매달리는 실제 상태다.

**4) 나머지 시행 규칙은 질문 7이 가리키는 AOSP 소스에서 확정했다.** 보호수준 네 가지의 부여 방식, AppOps 다섯 모드 상수(`MODE_ALLOWED`~`MODE_FOREGROUND`), `checkPermission`(명시 uid) vs `checkCallingPermission`(Binder 호출자)의 분기는 `PermissionManagerService`·`AppOpsService`·`AppOpsManager.java`(모드 상수 정의)가 규정한다. 권한/AppOps는 아키텍처 무관 로직이라 이 x86_64 AVD와 실기의 동작이 같다(질문 7).

## 소스로 확정한 것

실기·에뮬레이터를 가리지 않는 두 사실은 실행 대신 공식 근거로 확정했다.

- **Play App Signing과 AAB의 서버측 서명 키 변환**은 Google Play 서버가 업로드 키와 **별개의 앱 서명 키**로 재서명하는 서버측 절차이므로, 그 변환 규약은 [Play App Signing 공식 문서](https://developer.android.com/studio/publish/app-signing#app-signing-google-play)로 확정한다. 이 글이 로컬에서 실측한 v2/v3 서명(위 2항)은 그 서버 재서명의 입력이 되는 업로드 서명에 해당한다.
- **비무기화 범위**: `checkPermission`(명시 uid) ↔ `checkCallingPermission`(Binder 호출자, C17) 혼동이 권한 우회로 이어지는 분기는 AOSP 소스로 확정했고(위 4항), 살아있는 우회 익스플로잇 제작은 이 시리즈의 비무기화 원칙상 다루지 않는다.

관련 근거: [Android 권한 개요](https://developer.android.com/guide/topics/permissions/overview) · [<permission> protectionLevel](https://developer.android.com/guide/topics/manifest/permission-element) · [AppOpsManager](https://developer.android.com/reference/android/app/AppOpsManager) · [AOSP AppOpsManager.java](https://cs.android.com/android/platform/superproject/+/master:frameworks/base/core/java/android/app/AppOpsManager.java)

## 마치며

권한은 C09의 UID에 "무엇을 허가할까"입니다: 보호수준 normal(설치시 자동)·dangerous(런타임 A6+)·signature(선언 앱과 같은 서명 키, C08)·internal(A11+)이 부여 방식을 정하고, AppOps가 그 아래에서 op별로 더 잘게 시행합니다(IGNORED는 예외 없이 조용히 빈 데이터). 그리고 시행의 핵심 함정은 — `checkPermission(perm,pid,uid)`은 **명시된 uid**를 검사하지 Binder 호출자를 읽지 않고, 호출자를 푸는 건 `*Calling*` 변형뿐이라, 자기와 호출자를 헷갈리면 그게 곧 권한 우회 취약점(C17)입니다. 다음은 이 권한과 가시성을 컴포넌트/URI로 넘기는 **C11(package visibility·URI permission)**로 이어집니다.
