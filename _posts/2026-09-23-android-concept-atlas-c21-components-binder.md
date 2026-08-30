---
layout: post
title: "Android Security Concept Atlas C21 | 가상 실습 보고서 — 4대 컴포넌트↔Binder 연결, exported가 만드는 공격면"
date: 2026-09-23 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Components, Intent, exported, PendingIntent, IntentRedirection, AMS, ConceptAtlas, 학습기록]
excerpt: "앱 펜테스트에서 제일 먼저 세는 게 exported 컴포넌트입니다. 왜냐면 Activity·Service·BroadcastReceiver·ContentProvider를 시작/바인드/조회하는 건 전부 Binder 트랜잭션이고, 그 문을 여닫는 게 exported 플래그거든요. startActivity는 앱→system_server(A10+ ATMS) Binder 호출이고, AMS/ATMS가 exported와 android:permission을 호출자 UID로 검사하는 레퍼런스 모니터입니다. 핵심 함정: exported=false는 같은 UID만 - 권한을 아무리 가져도 타 앱은 못 갑니다. 반대로 exported면서 권한 가드가 없으면 그게 고전 공격면이죠. 그 위에 intent redirection(confused deputy)과 mutable PendingIntent 하이재크가 얹힙니다. 내 앱 펜테스트 작업의 뼈대인 Tier 3 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `ls -l /dev/{binder,hwbinder,vndbinder}`, `service list` |
| 관측 결과 | binderfs의 세 Binder 노드와 255개 서비스 등록을 확인했다. |
| 검증 한계 | 벤더 전용 HAL 트랜잭션이나 취약한 서비스 호출은 범용 AVD에 없으므로 공개 인터페이스·소스 분석으로 제한한다. |

![C21 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-binder.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C21 — 4대 컴포넌트↔Binder 연결
> **계층**: Tier 3 (IPC·프레임워크) · **난이도**: 중급 · **선수 개념**: C17(Binder), C19(AMS)
> **성격**: 보완 편.

C17에서 Binder를, C19에서 AMS/system_server를 봤습니다. 앱의 4대 컴포넌트가 **어떻게 그 위에서 연결되고**, 어디가 **공격면**이 되는지가 이 편 — 내 앱 펜테스트의 뼈대입니다.

한 문장으로: **4대 컴포넌트 호출은 전부 system_server가 브로커하는 Binder 트랜잭션이고, exported+android:permission이 그 문을 여닫는다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **4대 컴포넌트**: Activity·Service·BroadcastReceiver·ContentProvider. 전부 **Binder**로 교차 프로세스 호출.
- **AMS/ATMS**(system_server, C19): 레퍼런스 모니터 — exported+권한을 **호출자 UID**로 검사.
- **exported**: 타 앱 도달 가능 여부의 **절대 게이트**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

앱 컴포넌트가 Binder/AMS(C19)로 **연결되는 배선**이자, exported 컴포넌트라는 **외부 공격면**입니다. C17(Binder)·C10(권한)·C11(URI)·C22(호출자 UID)·C47(딥링크)이 전부 여기서 교차합니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **Activity**: `startActivity(intent)` = 앱→system_server Binder 호출. **A10/API29부터 액티비티 경로는 ActivityTaskManagerService(ATMS)**(AMS에서 분리). ATMS가 대상 해석(explicit/implicit)·exported·권한 검사 후, 대상 앱의 **`IApplicationThread`**(Binder)로 `ActivityThread`가 인스턴스화하게 함. 호출 앱이 대상 프로세스를 직접 건드리지 않음.
- **Service**: `startService`/`bindService`도 AMS 경유. `bindService`는 **직접 IBinder 반환**(`onServiceConnected`) → 이후 앱↔앱 직접 Binder(AMS 우회). `startService`는 IPC 채널 없음(ComponentName만).
- **BroadcastReceiver**: `sendBroadcast`→AMS가 매칭 리시버에 디스패치. ordered broadcast는 우선순위·결과 변조 가능.
- **ContentProvider**: 첫 접근은 AMS 경유로 프로바이더 프로세스 기동 → 이후 **직접 `IContentProvider`**로 query/insert/openFile. `readPermission`/`writePermission` + URI 권한(C11).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **AMS/ATMS가 레퍼런스 모니터**: exported+`android:permission`을 **호출자 UID**(`Binder.getCallingUid`, 커널이 각인해 위조 불가, C22)로 검사. 그래서 검사는 앱이 아니라 system_server에 있어야 함.
- **신뢰하면 안 되는 것들**:
  - **"`exported=false`라도 권한 있으면 타 앱이 접근"** — 아닙니다. `exported=false`는 **같은 UID만**(자기 앱, 또는 sharedUserId+같은 키). 권한을 아무리 가져도 타 앱은 못 갑니다 — exported는 **절대 게이트**.
  - **"exported면 무조건 접근"** — exported는 **필요조건이지 충분조건 아님**. `android:permission` 가드가 있으면 호출자가 그 권한을 가져야 합니다.
  - **"A14가 처음으로 타 앱 암시적 Intent의 비exported 도달을 막았다"** — 타 앱 암시적 Intent는 **원래** 비exported에 못 갑니다(exported가 항상 게이트). A14/API34가 새로 막은 건 **같은 앱(같은 UID) 내부**의 암시적→비exported 경로.
  - **"딥링크 도달성은 App Link 검증에 달렸다"** — 타 앱이 딥링크 Activity에 Intent를 보낼 수 있는지는 **exported 상태**에 달렸습니다. 검증(autoVerify)은 OS가 http(s) 링크를 자동으로 이 앱에 열지만 통제.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: Intent(explicit=ComponentName 지정 / implicit=action·category·data를 intent-filter로 매칭). 프로바이더는 query args + URI.
- **검사**: AMS/ATMS가 exported+permission을 호출자 UID로(reference monitor).
- **출력**: 대상 컴포넌트 인스턴스화, 또는 직접 Binder 채널(bind/provider).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **exported+무가드 = 고전 공격면**(펜테스터가 먼저 세는 것): (1) exported Activity → 악성 앱이 실행·조작 extra 주입; (2) exported Service → 바인드/시작; (3) exported Receiver → 조작 브로드캐스트·ordered 결과 변조; (4) exported ContentProvider 무권한 → 직접 읽기/쓰기(SQLi·경로 트래버설)+URI 권한 이슈(C11).
- **intent redirection(confused deputy)**: 권한 있는 exported 컴포넌트가 공격자가 준 Intent(예: `getParcelableExtra`)를 무비판적으로 내부 비exported 컴포넌트로 전달 → 공격자가 **피해자 UID로** 내부에 도달(C22).
- **PendingIntent 하이재크**: PendingIntent는 **생성자 정체성**으로 실행되는 토큰. mutable로 만들어 넘기면 보유자가 빈 필드를 채워 생성자 권한을 악용(A12/API31부터 `FLAG_IMMUTABLE`/`FLAG_MUTABLE` 명시 필수).
- **implicit intent 누출**: 민감 데이터의 암시적 Intent/브로드캐스트를 악성 앱이 매칭 필터로 수신. 딥링크 남용(C47).

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **A12/API31**: intent-filter 가진 컴포넌트에 `android:exported` **명시 필수**(누락 시 빌드 실패). PendingIntent **가변성 플래그 필수**.
- **API17(A4.2)**: ContentProvider 기본 exported가 true→**false**로.
- **A14/API34**: targetSdk 34+ 앱은 **같은 앱 내부**의 암시적 Intent가 비exported 컴포넌트에 도달 못 함.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 매니페스트의 `android:exported`·`android:permission`(aapt dump/apktool), `dumpsys package <pkg>`(선언 컴포넌트).
- `adb shell am start`/`am broadcast`/`content query`로 exported 컴포넌트 찔러보기, drozer식 열거, `pm get-app-links <pkg>`(App Link 검증 상태).
- **소스**: AOSP `frameworks/base/services/.../am`(ATMS/AMS), `ActivityThread`·`IApplicationThread`.

**주의**: 컴포넌트/Intent는 아키텍처 무관 → **에뮬레이터로 `am start`·`content query`·매니페스트 열거 실측 가능**(단 타 앱 대상 실전 테스트는 권한·소유 앱 한정).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C17(Binder)·C19(AMS)**: 4대 컴포넌트가 그 트랜잭션·레퍼런스 모니터 위에.
- **C10(권한)**: `android:permission`이 호출자 UID로 검사.
- **C11(URI)**: ContentProvider가 URI 권한을 추가로.
- **C22(호출자 UID)**: intent redirection·PendingIntent가 그 정체성을 악용.
- **C47(딥링크)**: exported Activity의 URI 취급.
- 다음은 플랫폼 격리 **Tier 4**(C24 seccomp/namespaces 등)로.

## 직접 그릴 수 있는 호출 흐름

```
[ 4대 컴포넌트 ↔ Binder/AMS, 그리고 exported 게이트 ]

  앱A ──startActivity(intent)──▶ system_server: ATMS(A10+, 액티비티 경로)
        ATMS: 대상 해석 + exported? + android:permission?(호출자 UID, C22)
        ──IApplicationThread──▶ 앱B: ActivityThread가 Activity 생성

  bindService  ──AMS──▶ onServiceConnected(IBinder) ──직접 앱↔앱 Binder──▶
  sendBroadcast ──AMS──▶ 매칭 리시버(ordered=결과 변조)
  ContentProvider 첫 접근 ──AMS──▶ 이후 직접 IContentProvider + URI권한(C11)

  게이트:
    exported=false → 같은 UID만 (권한 있어도 타 앱 ✗)
    exported=true + permission → 호출자 권한 필요
    exported=true + 무가드 → 공격면 (redirection/PendingIntent 하이재크)
```

## 오개념 판별 문제 5개

1. "`android:exported="false"`인 컴포넌트도, 적절한 (서명) 권한을 가진 다른 앱은 호출할 수 있다."
2. "컴포넌트가 exported이기만 하면 다른 앱이 무조건 접근할 수 있다."
3. "Android 14가 처음으로 다른 앱의 암시적 Intent가 비exported 컴포넌트에 닿는 것을 막았다."
4. "딥링크 Activity에 다른 앱이 Intent를 보낼 수 있는지는 App Link 검증(autoVerify) 상태로 결정된다."
5. "startActivity는 대상 앱을 직접 호출한다."

<details><summary>판정 기준(펼치기)</summary>

1. `exported=false`는 **같은 UID만**(자기 앱·sharedUserId+같은 키). 권한을 가져도 타 앱은 못 갑니다 — exported는 절대 게이트.
2. exported는 **필요조건**입니다. `android:permission` 가드가 있으면 호출자가 그 권한을 가져야 합니다.
3. 타 앱 암시적 Intent는 **원래** 비exported에 못 갑니다. A14는 **같은 앱 내부** 경로를 막았습니다.
4. **exported 상태**에 달렸습니다. 검증은 OS의 http(s) 자동 열기만 통제합니다.
5. 앱→system_server(ATMS/AMS) Binder → 대상 앱의 `IApplicationThread`로 이어지는 **왕복**입니다.
</details>

## 실측으로 확인한 것

전용 `codex-atlas-api33` AVD(Android 13/API 33, x86_64)에서, 4대 컴포넌트 호출이 올라타는 전송·브로커 계층을 실제 명령으로 확인했다.

**1) 컴포넌트 호출이 타는 Binder 전송 계층이 커널 노드로 실재한다.** 상단 검증 화면(`evidence-binder.png`)의 값은 다음 명령으로 얻었다.

```console
$ ls -l /dev/{binder,hwbinder,vndbinder}
```

binderfs의 세 노드(`binder`=앱↔프레임워크, `hwbinder`=HAL, `vndbinder`=벤더 도메인)가 모두 존재함을 확인했다. `startActivity`·`bindService`·`sendBroadcast`·ContentProvider 접근이 전부 Binder 트랜잭션이라는 질문 2의 주장이, 그 트랜잭션이 실제로 지나가는 커널 디바이스 수준에서 확인된다.

**2) 레퍼런스 모니터가 named Binder 서비스로 system_server에 등록돼 있다.**

```console
$ service list
```

255개 서비스 등록을 확인했다 — 컴포넌트 브로커인 `activity`(AMS)·`activity_task`(ATMS)가 이 목록에 등록된 Binder 서비스로 존재한다. 컴포넌트 시작·바인드·브로드캐스트 요청이 앱이 아니라 이 system_server 서비스로 라우팅된다는 것, 즉 "검사는 앱이 아니라 system_server에 있어야 한다"는 질문 3의 불변식이 서비스 등록 수준에서 확인된다.

**3) exported 게이트와 권한 검사의 위치는 AOSP 소스로 확정한다.** 호출자 UID(`Binder.getCallingUid`, 커널이 각인해 위조 불가, C22)로 exported·`android:permission`을 검사하는 코드는 ATMS/AMS와 매니페스트 파서에 있다. 이 지점 자체는 AVD에서 새로 실행해 캡처하지 않았고(아래 한계 참조), 위 (1)·(2)가 확인해 주는 것은 그 검사가 앉아 있는 전송·브로커 토대까지다.

## 가상환경 검증 한계

정직하게, 이 문서에서 새로 캡처한 실측은 (1)·(2)까지다. 나머지는 근거는 소스로 확정했으나 이 x86_64 AVD 세션에서 명령 출력으로 재현하지 않았다.

- **타 앱 exported 컴포넌트로의 크로스-앱 도달 테스트는 이 세션에서 재현하지 않았다.** 범용 AVD에는 대상이 될 취약 앱이 없고(검증 블록의 한계 줄과 동일), `am start`·`content query`로 타 앱 컴포넌트를 찌르는 실전 테스트는 소유·테스트 앱 한정 원칙에 따라 수행하지 않았다.
- **intent redirection·mutable PendingIntent 하이재크는 개념·소스로만 다뤘다.** 피해자 앱과 공격 앱 한 쌍으로 confused deputy 경로를 라이브 익스플로잇하는 재현은 이 문서 범위 밖이다.
- **hwbinder/vndbinder 위의 실제 벤더 HAL 트랜잭션은 미측정이다.** 노드 존재는 확인했으나, 벤더 전용 HAL·하드웨어 서비스는 범용 x86_64 AVD에 실체가 없어 그 위의 트랜잭션을 관측할 수 없다.

관련 근거: [앱 컴포넌트 기초](https://developer.android.com/guide/components/fundamentals) · [android:exported (activity 매니페스트)](https://developer.android.com/guide/topics/manifest/activity-element) · [PendingIntent 가변성(A12)](https://developer.android.com/about/versions/12/behavior-changes-12#pending-intent-mutability) · [PendingIntent 레퍼런스](https://developer.android.com/reference/android/app/PendingIntent)

## 마치며

앱 펜테스트에서 먼저 세는 건 exported 컴포넌트입니다 — Activity·Service·Receiver·Provider를 시작/바인드/조회하는 건 전부 Binder 트랜잭션이고, 그 문을 여닫는 게 exported이기 때문입니다. `startActivity`는 앱→system_server(A10+ **ATMS**) Binder 호출이고, AMS/ATMS가 exported와 `android:permission`을 **호출자 UID**로 검사하는 레퍼런스 모니터입니다. 핵심은 — `exported=false`는 **같은 UID만**이라 권한을 가져도 타 앱은 못 가고, 반대로 exported이면서 권한 가드가 없으면 그게 고전 공격면이며, 그 위에 intent redirection(confused deputy)과 mutable PendingIntent 하이재크가 얹힙니다. 이로써 Tier 3(IPC·프레임워크)를 닫습니다. 다음은 플랫폼 격리 **Tier 4**(C24 seccomp·namespaces·cgroups·capabilities)로 이어집니다.
