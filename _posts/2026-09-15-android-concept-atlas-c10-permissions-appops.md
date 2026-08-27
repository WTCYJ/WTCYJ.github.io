---
layout: post
title: "Android Security Concept Atlas C10 - permission·signature 권한·AppOps, UID에 무엇을 허가할까"
date: 2026-09-15 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Permission, RuntimePermission, SignaturePermission, AppOps, protectionLevel, SpecialAccess, ConceptAtlas, 학습기록]
excerpt: "C09에서 앱은 UID를 얻어 격리됩니다. 이 편은 그 UID에 '무엇을 허가할까'입니다 - 보호수준 normal(설치시 자동)·dangerous(런타임 A6+)·signature(선언 앱과 같은 서명 키일 때만, C08)·internal(A11+) 네 가지가 부여 방식을 정하고, AppOps가 그 아래에서 op별로 더 잘게 추적·시행하죠(IGNORED는 예외 없이 조용히 빈 데이터를 줍니다). 그리고 시행의 핵심 함정: checkPermission(perm,pid,uid)은 명시된 uid를 검사하지 Binder 호출자를 읽지 않습니다 - 호출자를 푸는 건 *Calling* 변형뿐이라, 자기와 호출자를 헷갈리면 그게 바로 권한 우회 취약점(C17)입니다. Tier 1 앱·패키징 모듈입니다."
---

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

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "`checkPermission(perm, pid, uid)`는 Binder 호출자의 UID를 검사한다."
2. "normal 권한도 런타임에 프롬프트되고 설정에서 개별 취소된다."
3. "signature 권한은 시스템 파티션에 설치된 앱이면 받는다."
4. "SYSTEM_ALERT_WINDOW(다른 앱 위에 그리기)는 dangerous 런타임 권한 그룹이다."
5. "일회성 권한('이번만 허용')은 Android 10(Q)에서 도입됐다."

<details><summary>판정 기준(펼치기)</summary>

1. **명시된 uid**를 검사합니다. 호출자를 Binder로 푸는 건 `checkCallingPermission` 등 `*Calling*` 변형뿐 — 혼동이 우회 취약점(C17).
2. normal은 **설치 시 자동·개별 취소 불가**입니다. 런타임 프롬프트/취소는 dangerous.
3. **같은 서명 키**(선언자 인증서 일치)여야 합니다. 파티션+허용목록은 별개 플래그 `|privileged`.
4. **special access**(설정 관리, AppOp 백킹)입니다. 런타임 그룹이 아닙니다.
5. **A11/R**입니다. Q는 지속형 "사용 중일 때만"을 추가했습니다.
</details>

## 서술형 문제 3개

1. 네 보호수준(normal/dangerous/signature/internal)이 각각 어떻게 부여되는지 서술하고, signature가 왜 C08 서명과 직결되는지 설명하세요.
2. AppOps의 네(다섯) 모드를 설명하고, 특히 `MODE_IGNORED`(조용한 빈 데이터)와 `MODE_ERRORED`(예외)의 차이가 리버싱에서 왜 중요한지 서술하세요.
3. `checkPermission`(명시 uid) vs `checkCallingPermission`(Binder 호출자)의 차이가 어떻게 권한 우회 취약점이 되는지, C09·C17과 엮어 서술하세요.

## 소스 탐색 과제

- 임의 앱에 대해 `dumpsys package <pkg>`로 요청/부여 권한과 install/runtime 구분을 확인하세요.
- `cmd appops get <pkg>`로 op 모드를 보고, `pm revoke`로 하나 취소한 뒤 대응 op가 어떻게 바뀌는지 관찰하세요.
- `pm list permissions -g -d`로 dangerous 그룹을 나열하고, SYSTEM_ALERT_WINDOW가 그 목록에 없음(special access)을 확인하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **권한 실측**: `dumpsys package`로 한 앱의 protectionLevel별 권한을.
2. **AppOps 실측**: `cmd appops get`으로 모드를, `pm revoke` 전후 대조를.
3. **시행 서술**: `*Calling*` vs 명시-uid 차이를, 권한 우회 패턴으로 서술(C17).
4. **연결**: signature 권한을 공유하는 두 앱의 서명자 해시(C08)를 대조.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

권한은 C09의 UID에 "무엇을 허가할까"입니다: 보호수준 normal(설치시 자동)·dangerous(런타임 A6+)·signature(선언 앱과 같은 서명 키, C08)·internal(A11+)이 부여 방식을 정하고, AppOps가 그 아래에서 op별로 더 잘게 시행합니다(IGNORED는 예외 없이 조용히 빈 데이터). 그리고 시행의 핵심 함정은 — `checkPermission(perm,pid,uid)`은 **명시된 uid**를 검사하지 Binder 호출자를 읽지 않고, 호출자를 푸는 건 `*Calling*` 변형뿐이라, 자기와 호출자를 헷갈리면 그게 곧 권한 우회 취약점(C17)입니다. 다음은 이 권한과 가시성을 컴포넌트/URI로 넘기는 **C11(package visibility·URI permission)**로 이어집니다.
