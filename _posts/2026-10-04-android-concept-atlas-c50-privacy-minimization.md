---
layout: post
title: "Android Security Concept Atlas C50 | 가상 실습 보고서 — 개인정보 최소화·권한 모델 변화, 권한은 침해의 폭발 반경이다"
date: 2026-10-04 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, DataMinimization, Permissions, PrivacyDashboard, PhotoPicker, ScopedStorage, PrivateSpace, ConceptAtlas, 학습기록]
excerpt: "보안 블로그가 왜 '개인정보 최소화'를 다루냐면 - 앱이 쥔 권한 하나하나가 침해 시 공격자(그리고 그 앱의 모든 SDK)가 상속하는 능력, 즉 폭발 반경이기 때문입니다. 권한은 고전적 의미의 공격 진입점이 아니라 뚫린 뒤의 반경이고, 최소화는 그 반경과 새어나갈 데이터를 동시에 줄이죠. Android 권한 모델은 A6 런타임 권한부터 A15 Private Space까지 꾸준히 그쪽으로 진화해 왔습니다 - 넓고 영구적인 사전 허가에서 좁고 취소 가능하고 시간 제한적이고 투명한 접근으로. 다만 '최소화 = 최소권한'은 사촌 관계지 등호가 아니고(하나는 능력, 하나는 데이터), 이 기본 축소도 targetSdk 게이트라 옛 타깃 앱은 비켜갑니다. Tier 8을 닫는 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | Android 개인정보·보안·네트워크 설정 캡처, `curl --tlsv1.3`, 패키지·AppOps 조회 |
| 관측 결과 | 권한·개인정보 통제 화면과 TLS 1.3 HTTP 200 응답을 확인했다. 앱·호스트 네트워크 관측을 분리해 기록했다. |
| 검증 한계 | Play Integrity의 프로덕션 verdict, 실제 OAuth 공급자, 제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다. |

![C50 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C50 — 개인정보 최소화·권한 모델 변화
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 기초 · **선수 개념**: C10(권한), C02(최소권한)
> **성격**: 보완 편.

C10에서 권한을, C49에서 SDK가 앱 권한을 상속함을 봤습니다. 이 편은 왜 보안이 **개인정보 최소화**를 신경 쓰는지 — 권한이 곧 침해의 **폭발 반경**이기 때문입니다.

한 문장으로: **앱이 쥔 권한은 침해 시 공격자와 모든 SDK가 상속하는 능력(폭발 반경)이고, 최소화는 그 반경과 새어나갈 데이터를 함께 줄인다.** 🟡 기초·보완이라 원칙+타임라인에 집중합니다.

## 배경 개념

- **데이터 최소화**: 필요한 **최소 데이터·최단 시간·최조 입도**(정밀 대신 대략 위치, 전체 저장소 대신 고른 사진 1장).
- **권한 = 폭발 반경**: 침해 후 공격자·SDK(C49)가 상속하는 능력.
- **모델 진화**: 넓고 영구적 → 좁고 취소 가능·시간 제한·투명.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**데이터에 적용한 최소권한**입니다. C10(권한)·C11(가시성)·C49(SDK 상속)·C02/C03(최소권한)과 엮이고, 권한 모델의 역사가 이 원칙을 기본값으로 인코딩한 과정입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **최소화 원칙**: 기능에 꼭 필요한 데이터만, 최단 보유, 되는 한 가장 거친 입도로.
- **권한 모델 진화(정확한 버전)**: A6 런타임 권한 → A15 Private Space까지(§6). 요지는 사전·영구 허가에서 **범위 한정·취소 가능·시간 제한·투명** 접근으로.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **핵심 프레이밍**: 최소화는 **① 새어나갈 데이터**(적게 수집·짧게 보유·거칠게)와 **② 상속되는 능력**(권한 적을수록 침해 시 남용 여지 작음)을 동시에 줄입니다.
- **신뢰하면 안 되는 것들**:
  - **"최소화 = 최소권한"** — **사촌**이지 등호가 아닙니다. 최소권한(Saltzer & Schroeder 1975)은 **능력**을, 데이터 최소화(GDPR 5(1)(c) "필요한 만큼으로 제한")는 **데이터**를 좁힙니다. 같은 반사, 다른 대상.
  - **"권한은 공격 진입점(attack surface)"** — 고전적 의미(Manadhata & Wing 2011: 도달 가능한 진입/출구·채널)의 진입점이 **아닙니다**. 쥔 권한은 뚫린 뒤의 **폭발 반경**(상속 능력)입니다.
  - **"앱이 SDK에 부분 권한을 못 준다"** — 절대는 아닙니다. 기본(인프로세스 정적 링크 SDK, C49)은 전부 상속하지만, **Privacy Sandbox의 SDK Runtime(A13+)**은 특정 SDK를 별도 프로세스·축소 접근으로 돌려 부분화가 가능.
  - **"최소화는 프라이버시/컴플라이언스 얘기"** — 보안입니다(유출 데이터 + 상속 능력 둘 다 축소).
  - **"기본 노출이 무조건 작아졌다"** — 많은 통제가 **targetSdk 게이트**라, 옛 타깃 앱은 scoped storage·런타임 POST_NOTIFICATIONS·패키지 가시성을 비켜갑니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 앱이 요청하는 권한/데이터. **출력**: 사용자에게 노출·수집되는 것, 침해 시 상속되는 능력.
- **능력 제거형 통제**: Photo Picker는 **무권한**으로 고른 사진만 반환(앱이 저장소 읽기 능력 자체를 못 가짐), 부분 미디어 접근은 선택분만 — "요청-신뢰"보다 **능력 제거**가 낫습니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **과권한 앱 = 큰 유출 표면 + SDK 상속**(C49): 침해 반경 = 앱이 닿을 수 있는 모든 것의 합집합, 그리고 그 권한을 **모든 SDK가** 씀.
- **미사용 권한은 휴면이 아님**: 모든 라이브러리에 넘겨준 능력.
- **정찰 표면**: 패키지 가시성 미제한(옛 타깃) = 설치앱 목록으로 지문·타깃팅.
- **능력 제거의 우위**: Photo Picker/부분접근처럼 능력을 앱 손에서 빼면, 침해돼도 그 능력이 없음.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가 (정확한 타임라인)

- **A6/API23**: 런타임 권한(설치시 일괄 → 런타임 개별·취소).
- **A10/API29**: 백그라운드 위치 분리 + "사용 중일 때만" + scoped storage 도입.
- **A11/API30**: 일회성 권한 + 미사용 앱 자동 재설정 + 패키지 가시성(`<queries>`) + scoped storage 강제.
- **A12/API31**: 대략/정밀 위치 토글 + 마이크·카메라 인디케이터 + 센서 토글 + 프라이버시 대시보드 + 클립보드 토스트.
- **A13/API33**: Photo Picker(무권한) + granular `READ_MEDIA_*` + 런타임 `POST_NOTIFICATIONS` + `AD_ID`(targetSdk 33+, 옵트아웃=올제로).
- **A14/API34**: 부분 미디어(`READ_MEDIA_VISUAL_USER_SELECTED`) + Credential Manager(A14 GA·Jetpack 백포트).
- **A15/API35**: Private Space(민감 앱 격리 잠금 공간).
- (자동 재설정은 Play services로 A23~29 백포트, 단 앱이 30+ 타깃이어야.)

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 설정 > 프라이버시 대시보드(접근 타임라인), `dumpsys package <pkg>`(권한 상태), `cmd appops get <pkg>`(접근 이력).
- 앱이 **Photo Picker(무권한)** vs `READ_MEDIA_*` 요청인지, `AD_ID` 선언, `<queries>`.
- **소스**: developer.android.com "권한 최소화"·release별 behavior-changes(개인정보 절), Photo Picker/미디어 권한 가이드.

**주의**: 아키텍처 무관 → **에뮬레이터로 대시보드·appops·Photo Picker 유무 실측 가능**(단 버전별 기능은 해당 API 레벨 필요).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C10(권한)·C11(가시성)**: 최소화가 그 권한·정찰 표면을 줄임.
- **C49(SDK)**: 상속되는 능력이 곧 최소화의 최대 근거.
- **C02/C03(최소권한)**: 데이터판 사촌.
- **C43(scoped storage)**: 저장 접근 최소화.
- 이로써 Tier 8을 닫고, 다음은 이 모든 것을 실제 제보로 잇는 **C56(책임 있는 공개)**로.

## 호출 흐름

```
[ 최소화 = 유출 데이터 + 상속 능력 함께 줄이기 ]

  앱 권한 세트 ── 침해 시 → 공격자 + 모든 SDK(C49)가 상속 = 폭발 반경
       (고전 공격면=진입점 ≠ 이것; 이건 뚫린 뒤의 반경)

  능력 제거형(최선):  Photo Picker(무권한, 고른 사진만)
                      부분 미디어(선택분만)  ← 앱이 능력 자체를 못 가짐
  범위·시간 한정:     while-in-use, 일회성, 대략 위치, 자동 재설정
  투명:               대시보드, 인디케이터, 클립보드 토스트
  정찰 축소:          패키지 가시성(C11)

  진화: A6 런타임 → A10 위치분리 → A11 일회성/가시성/scoped
        → A12 대시보드/토글 → A13 Photo Picker/granular
        → A14 부분미디어 → A15 Private Space
  ⚠ 다수 통제가 targetSdk 게이트 → 옛 타깃 앱은 회피
```

## 실측으로 확인한 것

전용 `codex-atlas-api33` AVD(Android 13/API 33, x86_64)에서 이 모듈의 검증 가능한 주장을 실제 명령으로 확인했다.

**1) 투명·통제 계층은 이 API 레벨에 실재한다.** Android 개인정보·보안·네트워크 설정을 캡처한 결과, 검증 블록의 관측 결과대로 권한·개인정보 통제 화면이 확인됐다(상단 `privacy.png`). 질문 6에서 A12 프라이버시 대시보드·A13 통제로 정리한 "투명" 계층이 API 33 이미지에 그대로 존재함을 화면으로 확증한다.

**2) 권한 상태·접근 이력은 조회로 열거된다 = 과권한 식별의 실제 메커니즘.** 관측 결과에 기록된 "패키지·AppOps 조회"는 질문 7의 두 점검 경로에 대응한다. 같은 세션에서 실제로 두 명령을 돌려 값을 받았다.

```console
$ adb shell dumpsys package <pkg>    # 요청·허가된 권한 상태
      android.permission.POST_NOTIFICATIONS
        android.permission.POST_NOTIFICATIONS: granted=false, flags=[ USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]

$ adb shell cmd appops get <pkg>     # 접근 모드
Uid mode: POST_NOTIFICATION: ignore
```

A13에서 런타임으로 승격된 `POST_NOTIFICATIONS`가 `granted=false`·`USER_SENSITIVE` 플래그로, AppOps 모드가 `ignore`로 실제 열거됐다 — 질문 6의 "A13 런타임 `POST_NOTIFICATIONS`" 통제가 이 이미지에 값으로 실재함을 확증한다. `dumpsys package`가 앱의 요청·허가 권한을, `cmd appops`가 접근 모드·이력을 되돌려준다는 점이 이 출력으로 확인된다. 요청 권한과 기능상 필요 권한을 대조해 과권한을 식별할 수 있다는 질문 5·7의 주장은, 값을 열람할 이 경로가 실제로 동작하기 때문에 성립한다.

**3) 앱·호스트 네트워크 관측을 분리해 기록했다.** `curl --tlsv1.3`로 호스트 측 TLS 1.3 HTTP 200을 받아, 앱 프로세스 관측과 호스트 네트워크 관측을 검증 블록의 관측 결과대로 분리해 남겼다. 무엇이 앱에서 새고 무엇이 호스트에서 관측되는지 경계를 나눠 기록하는 것이 최소화 서술의 전제다(질문 3의 신뢰 경계).

**4) 폭발 반경의 경계인 UID 샌드박스는 실측된다.** "권한 = 폭발 반경"이 성립하는 이유는 침해가 앱의 UID 샌드박스 경계 안에서 상속되기 때문이다. 그 경계를 같은 세션에서 실제로 열거했다.

```console
$ adb shell dumpsys package com.example.visibilitylegacy | grep userId
    userId=10176
$ adb shell ls -la /data/data/com.example.visibilitylegacy
drwx------ 4 u0_a176 u0_a176 4096 2026-08-29 09:48 /data/data/com.example.visibilitylegacy
```

앱마다 고유 UID(`10176`/`u0_a176`)와 `0700` 사설 디렉터리가 부여돼, 폭발 반경이 곧 이 UID가 닿는 능력의 합집합임을 값으로 확인했다. 이 경계가 실재하기에 "권한을 모든 SDK가 상속한다"는 질문 5의 서술이 성립한다.

**5) 패키지 가시성 필터링이 이 이미지에서 활성이다 = 정찰 표면 축소 실측.** A11 패키지 가시성(질문 6)이 API 33 이미지에서 실제로 켜져 있는지 같은 세션에서 조회했다.

```console
$ adb shell dumpsys package com.example.visibilitylegacy
Queries:
  system apps queryable: false
...
    forceQueryable=false
```

`system apps queryable: false`·`forceQueryable=false`로, 비특권 앱이 `QUERY_ALL_PACKAGES` 없이 설치앱 목록을 훑는 정찰 표면이 기본 차단됨을 값으로 확인했다. 질문 5의 "패키지 가시성이 정찰 표면"이라는 서술의 반대 방향 — 제한이 실재한다는 것 — 을 실측으로 뒷받침한다.

## 소스로 확정한 것

실측으로 다룬 (1)~(5) 외의 근거는 소스·공식 문서로 확정했다.

- **부분 미디어(`READ_MEDIA_VISUAL_USER_SELECTED`, A14)와 Private Space(A15)는 API 34/35에 도입된 버전 게이트 기능이다.** 이 API 33 이미지에 존재하지 않는 것이 도입 API 레벨상 정상이며, 각 도입 시점은 [Android 14 동작 변경](https://developer.android.com/about/versions/14/behavior-changes-14)과 [Android 15 동작 변경](https://developer.android.com/about/versions/15/behavior-changes-all)으로 확정된다. Photo Picker가 무권한 컴포넌트로 고른 사진만 반환한다는 점은 [Photo picker 가이드](https://developer.android.com/training/data-storage/shared/photopicker)에 명시돼 있다.
- **Privacy Sandbox의 SDK Runtime(A13+)은 특정 SDK를 별도 프로세스에서 축소된 접근으로 실행한다.** 인프로세스 정적 링크 SDK(C49)가 앱 권한을 전부 상속하는 기본형과 달리 부분화가 가능하다는 설계는 [SDK Runtime 문서](https://developer.android.com/design-for-safety/privacy-sandbox/sdk-runtime)로 확정된다.
- **다수 최소화 통제가 `targetSdk` 게이트라는 사실은 릴리스별 동작 변경 문서로 확정된다.** scoped storage·런타임 알림·패키지 가시성이 타깃 SDK에 따라 적용됨은 [권한 필요성 평가](https://developer.android.com/training/permissions/evaluating)와 각 릴리스 behavior-changes(개인정보 절)에 기술돼 있다. 게이트의 존재 자체가 문서로 확정되므로, 별도 레거시 앱 없이도 이 버전 축이 성립한다.

**비무기화 범위**: "폭발 반경"의 끝단 — 제3자 SDK 백엔드로의 실제 데이터 유출·남용 — 은 이 시리즈의 비무기화 원칙에 따라 판정 지점까지만 다룬다. 권한이 침해 시 UID 경계 안에서 상속된다는 사실(위 실측 4)까지 확인하고, 그 능력을 실제로 행사하는 익스는 범위에 두지 않는다.

## 마치며

보안 블로그가 개인정보 최소화를 다루는 이유는 — 앱이 쥔 권한 하나하나가 침해 시 공격자(그리고 그 앱의 모든 SDK)가 상속하는 능력, 즉 폭발 반경이기 때문입니다. 권한은 고전적 의미의 공격 진입점이 아니라 뚫린 뒤의 반경이고, 최소화는 그 반경과 새어나갈 데이터를 동시에 줄입니다. Android 권한 모델은 A6 런타임 권한부터 A15 Private Space까지 꾸준히 그쪽으로 진화해 왔습니다 — 넓고 영구적인 사전 허가에서 좁고 취소 가능하고 시간 제한적이고 투명한 접근으로. 다만 "최소화 = 최소권한"은 사촌 관계지 등호가 아니고(하나는 능력, 하나는 데이터), 이 기본 축소도 targetSdk 게이트라 옛 타깃 앱은 비켜갑니다. 이로써 Tier 8(앱 보안 통제)을 닫습니다. 다음은 이 모든 발견을 실제로 제보하는 **C56(책임 있는 공개)** — Atlas의 마지막 모듈로 이어집니다.
