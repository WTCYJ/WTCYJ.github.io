---
layout: post
title: "AMS·ActivityTaskManagerService"
date: 2026-11-22 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, AMS, ActivityTaskManager, system_server, TaskHijacking]
excerpt: "AMS는 Android 10에서 프로세스 관리(AMS)와 액티비티·태스크 관리(ActivityTaskManagerService)로 쪼개졌다. 흔한 착각 — startActivity의 권한은 호출한 앱이 아니라 system_server가 Binder.getCallingUid로 다시 확인한다. taskAffinity로 남의 태스크에 끼어드는 StrandHogg가 노린 게 정확히 이 경계의 빈틈이었다."
---

앱이 `startActivity()`를 부르면 화면이 바뀐다. 이 한 줄 뒤에서 실제로 무슨 일이 벌어지는지는 대부분 블랙박스로 남는다 — 어느 프로세스가 결정하고, 누가 권한을 검사하고, 태스크(task)라는 그릇에 액티비티가 어떻게 쌓이는지. 이 결정을 내리는 주체가 system_server 안의 **ActivityManagerService(AMS)** 와, Android 10에서 여기서 갈라져 나온 **ActivityTaskManagerService(ATMS)** 다. 그리고 이 경계가 어떻게 검사되느냐가 곧 "남의 앱 화면으로 위장할 수 있느냐"를 가른다.

이 글은 AMS/ATMS가 system_server에서 무슨 일을 하고, 앱→프레임워크→Binder→system_server 흐름에서 신뢰 경계가 어디에 그어지는지를 AOSP 소스 구조와 함께 정리한 기록이다. 공격 실습이 아니라 구조·검사 지점의 이해가 목적이다.

> **한 줄 결론**: `startActivity`의 최종 권한·신원 검사는 호출 앱이 아니라 system_server(ATMS의 `ActivityStarter`)가 `Binder.getCallingUid()`로 다시 하며, 태스크는 UID가 아니라 `taskAffinity`로 묶이기 때문에 이 두 사실의 틈이 StrandHogg류 태스크 하이재킹의 뿌리다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 세 가지다. (1) AMS와 ATMS가 각각 무엇을 맡고 왜 Android 10에서 쪼개졌는지, (2) 앱의 `startActivity` 호출이 Binder를 건너 system_server에서 검사되는 경로, (3) 태스크·액티비티가 쌓이는 구조(`Task`/`ActivityRecord`)와 거기서 생기는 태스크 하이재킹의 원리다.

선수 개념이 셋 깔린다. Binder IPC — 앱과 system_server는 같은 프로세스가 아니라 커널 Binder 드라이버를 건너 대화하고, 그 경계에서 호출자 UID/PID가 커널이 보증하는 값으로 넘어온다는 점(Atlas의 Binder 편, 이 파트 14장에서 proxy/stub을 다룬다). system_server — AMS/ATMS/PMS/WMS 같은 핵심 시스템 서비스가 한 프로세스 안 여러 스레드로 사는 특권 프로세스라는 점. 그리고 프로세스 생명주기 — 앱 프로세스는 zygote fork로 태어나고 AMS가 그 생사를 관리한다는 점이다.

전체 구조에서 AMS/ATMS는 **앱 실행의 관제탑**이다. 아래로 PackageManagerService(다음 장)에서 "이 컴포넌트가 존재하고 export됐는가"를 받아, WindowManagerService(13장)로 "실제 창을 어디에 그릴지"를 넘긴다. 이 장은 그 중간, "누가 무엇을 띄울 수 있는가"의 결정 지점이다.

## 핵심 개념 — AMS와 ATMS의 분업

Android 10(API 29)에서 액티비티·태스크·창 관련 로직이 AMS에서 떨어져 나와 **ActivityTaskManagerService**로 옮겨졌고, 패키지도 `com.android.server.am`에서 창 관리와 같은 `com.android.server.wm`으로 갔다. `Source-confirmed` 목적은 프로세스 관리(broadcast/service/provider/OOM)와 창·액티비티 관리의 관심사 분리다.

| 서비스 | 패키지 | 주요 책임 | 대표 소스 |
|--|--|--|--|
| `ActivityManagerService` (AMS) | `com.android.server.am` | 프로세스 생명주기, 브로드캐스트, 서비스, ContentProvider, oom_adj/LMK, ANR | `ActivityManagerService.java` |
| `ActivityTaskManagerService` (ATMS) | `com.android.server.wm` | 액티비티 시작, 태스크·백스택, recents, 실행 모드/affinity | `ActivityTaskManagerService.java`, `ActivityStarter.java` |

두 서비스 모두 **system_server 프로세스 안**에 살고, 앱은 이들을 직접 호출하지 못한다. 앱이 보는 것은 AIDL로 정의된 원격 인터페이스 `IActivityManager`/`IActivityTaskManager`뿐이고, 실제 호출은 Binder proxy가 마샬링해 커널을 건너 stub 쪽 system_server 스레드에서 풀린다. `Source-confirmed` 그래서 `startActivity`의 "진짜" 구현은 앱 프로세스가 아니라 특권 프로세스에서 돈다.

액티비티가 쌓이는 그릇의 계층은 대략 `RootWindowContainer` → `DisplayContent` → `Task` → `ActivityRecord`다(단, 이 글 기준인 Android 10에는 `DisplayContent`와 `Task` 사이에 `ActivityStack` 계층이 하나 더 있었고, 대략 Android 12에서 `Task`로 병합됐다 — 위 사슬은 병합 이후의 모던 구조에 가깝다). `ActivityRecord` 하나가 화면의 액티비티 한 인스턴스에 대응하고, 이들이 `Task`라는 백스택에 LIFO로 쌓인다. `Source-confirmed` 핵심은 **태스크의 묶음 단위가 UID가 아니라 `taskAffinity`(기본값=패키지명)** 라는 점이다. 같은 affinity면 서로 다른 성격의 액티비티도 한 태스크에 들어갈 수 있고, 이게 뒤에서 문제의 뿌리가 된다.

> **[그림 1]** 자작 앱을 AVD에서 실행한 뒤 `adb shell dumpsys activity activities`로 `RootWindowContainer → Task → ActivityRecord` 계층과 각 ActivityRecord의 `taskAffinity`가 찍힌 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

경계는 명확하다. **앱 프로세스(비특권, 각자 UID) ↔ system_server(특권)** 사이를 Binder가 가른다. 앱이 보내는 `Intent`·플래그·타깃 컴포넌트는 전부 **신뢰할 수 없는 입력**이고, system_server는 이걸 그대로 믿으면 안 된다.

여기서 가장 자주 오해되는 지점 — "권한 검사는 호출한 앱이 이미 한다"는 착각이다. 앱 쪽 `Context.startActivity`나 `Instrumentation`이 하는 일은 인자 포장에 가깝고, 결정권 있는 검사는 system_server에서 다시 이뤄진다. ATMS의 `ActivityStarter`/`ActivityStartController`가 `Binder.getCallingUid()`·`getCallingPid()`로 호출자 신원을 **커널이 보증한 값**으로 다시 읽어, 대상 액티비티의 `exported`·권한·같은 UID 여부·백그라운드 시작 여부를 판정한다. `Source-confirmed` 앱이 보낸 필드가 아니라 Binder가 실어준 UID가 기준이라는 게 이 경계의 핵심이다.

위협 모델의 대상은 셋이다. (1) **컴포넌트 무단 실행** — export되지 않은 남의 액티비티를 띄우려는 시도(권한/UID 검사로 차단). (2) **백그라운드 액티비티 실행(BAL)** — 포그라운드가 아닌 앱이 갑자기 화면을 가로채는 것으로, Android 10부터 조건을 크게 제한했다. `Reported` (3) **태스크 하이재킹** — 검사를 우회하는 게 아니라 `taskAffinity`·실행 모드·`allowTaskReparenting`이라는 정상 기능을 조합해, 악성 앱의 액티비티를 정상 앱의 태스크에 끼워 넣어 UI를 위장하는 것.

## 관측 — dumpsys로 결정의 흔적 읽기

system_server의 결정은 `dumpsys`로 밖에서 관측된다. 안전 범위는 로컬 AVD + 자작 앱뿐이다.

태스크·백스택 구조는 `dumpsys activity activities`로, 프로세스 상태와 kill 우선순위는 `dumpsys activity oom`으로 읽는다. 자작 앱을 포그라운드→백그라운드로 옮기며 oom_adj가 어떻게 변하는지 대조하면, AMS가 프로세스 중요도를 어떻게 매기는지가 그대로 보인다.

```bash
# 태스크/액티비티 계층 + affinity
adb shell dumpsys activity activities | sed -n '/Task{/,/taskAffinity/p'
# 프로세스 중요도(oom_adj)와 상태
adb shell dumpsys activity oom | grep -i "포함할 내 패키지명"
# 백그라운드 시작 시도의 로그(자작 앱이 백그라운드에서 startActivity 시도 시)
adb logcat -s ActivityTaskManager:* | grep -i "background"
```

`예시 출력`(네 실제 실행으로 교체):

```
# (아래 <...>는 형식이 아니라 자리표시 — 실제 pid/UID/상태 문자열은 dumpsys 출력마다 다르다)
# 자작 앱이 포그라운드일 때  → adj=0 (foreground/TOP)
Proc #<N>: <state>  <pid>:com.wtcy.demo/u0a<XXX>   adj=0
# 홈으로 내린 직후  → 먼저 previous(PREVIOUS_APP_ADJ=700)
Proc #<N>: <state>  <pid>:com.wtcy.demo/u0a<XXX>   adj=700
# 한참 방치돼 늙으면  → cached(CACHED_APP_MIN_ADJ=900~999)
Proc #<N>: <state>  <pid>:com.wtcy.demo/u0a<XXX>   adj=900
# 백그라운드에서 startActivity를 시도하면
W ActivityTaskManager: Background activity start ... blocked
```

`adj=0`(포그라운드, TOP)에서 화면을 내리면 먼저 previous(adj=700)로 떨어지고, 한참 방치돼 캐시로 늙으면 cached(adj=900~999)가 된다 — '홈으로 내린 직후'와 'cached'는 같은 시점이 아니다. 이 숫자가 LMK가 메모리 압박 시 누구를 먼저 죽일지의 순번이 된다. `Source-confirmed` 그리고 백그라운드에서의 무단 액티비티 시작은 정책상 차단 로그를 남긴다(정확한 로그 문자열·차단 조건은 버전별로 다르니 원문 재확인 필요).

> **[그림 2]** 자작 앱을 포그라운드→백그라운드로 옮기며 `dumpsys activity oom`의 `adj` 값이 `0(foreground)` → `700(previous)` → `900+(cached)`로 늙어가는 시점들을 나란히 잡은 대조 캡처 — *실측 스크린샷 자리*

## Root Cause — 왜 태스크 하이재킹이 가능했나

검사가 허술해서가 아니다. **권한 검사는 UID 기준인데 태스크 묶음은 affinity 기준**이라, 두 축이 서로 다른 것을 본다는 구조적 불일치가 원인이다.

`startActivity`의 UID/권한 검사는 "이 호출자가 이 컴포넌트를 띄울 자격이 있나"만 본다. 통과한 뒤 그 액티비티가 **어느 태스크에 들어가는가**는 `taskAffinity`·실행 모드(`singleTask` 등)·`allowTaskReparenting`이 결정한다. 악성 앱이 정상 앱과 같은 `taskAffinity`를 선언하면, 자기 액티비티를 정상 앱의 태스크 위에 얹어 사용자가 정상 앱을 열었을 때 위장 화면을 먼저 보이게 만들 수 있다. `Reported` 이게 Promon이 공개한 **StrandHogg**(2019)의 원리다 — 취약점 하나를 터뜨린 게 아니라 정상 기능의 조합을 악용했다.

후속판 **StrandHogg 2.0(CVE-2020-0096)** 은 매니페스트에 affinity를 미리 박아두지 않고 코드로 태스크 재구성을 유도해 탐지를 어렵게 만든 변형이다. `Reported` 2020년 5월 보안 게시판에서 패치됐고, Google은 이 CVE를 Framework의 권한 상승(Elevation of Privilege)·심각도 Critical로 공식 분류했다. `Source-confirmed` (정확한 수정 범위는 해당 게시판 원문 재확인 필요.) 여기서 붙잡을 오개념 하나 — **메커니즘**은 권한 우회(privilege bypass)라기보다 **UI 신원 위장(스푸핑)** 에 가깝지만, **임팩트**는 권한 상승에까지 이른다: 위장한 권한 다이얼로그로 사용자가 미승인 권한을 내주게 만들 수 있어 Google이 EoP/Critical로 매겼다. 크래시도 RCE도 아닌, "사용자가 보는 화면의 소속을 속여 권한까지 탈취할 수 있는" 스푸핑·권한상승 클래스다.

## 버전 차이와 한계

- **Android 10(API 29)**: AMS에서 ATMS 분리(`com.android.server.wm`), 그리고 백그라운드 액티비티 실행(BAL) 제한 도입. `Source-confirmed` 이후 버전에서 BAL 조건은 계속 조여졌다(세부 조건은 버전별로 다르니 원문 확인 필요).
- **태스크 affinity 하이재킹 대응**: StrandHogg 2.0 패치 이후에도 플랫폼은 affinity 기반 재부모화·백그라운드 시작을 지속적으로 강화했다. 특정 API 레벨에서의 정확한 동작 변화는 원문(보안 게시판·플랫폼 릴리스 노트) 재확인이 필요하다. `Inferred`
- **관측의 한계**: `dumpsys`가 보여주는 것은 결정의 *결과*(태스크 구성·oom_adj)이지 검사 코드 자체가 아니다. 검사 경로는 `ActivityStarter`/`ActivityStartController` 소스를 직접 읽어야 한다. 에뮬레이터에서도 이 로직은 아키텍처 무관으로 그대로 관측된다.
- 오프셋·정확한 클래스 분업은 릴리스마다 리팩터링되므로, 소스를 인용할 땐 **AOSP 태그/브랜치를 함께 표기**해야 한다.

## 정리

- AMS(프로세스·브로드캐스트·서비스·oom_adj)와 ATMS(액티비티·태스크·시작 검사)는 Android 10에서 갈라졌고 둘 다 system_server에 산다.
- `startActivity`의 결정적 검사는 앱이 아니라 system_server가 `Binder.getCallingUid()`로 다시 하며, 태스크는 UID가 아니라 `taskAffinity`로 묶인다 — 이 축의 불일치가 태스크 하이재킹의 뿌리다.
- StrandHogg류는 취약점 폭발이 아니라 정상 기능(affinity·실행 모드·reparenting) 조합에 의한 **UI 스푸핑**이며, 관측은 `dumpsys activity activities`/`oom`으로 로컬 AVD에서 재현·확인한다.

**점검 질문** — (1) `startActivity`를 부를 때 실제 권한 검사는 어느 프로세스에서, 무엇을 기준으로 이뤄지는가? (2) 태스크가 UID가 아니라 `taskAffinity`로 묶인다는 사실이 왜 보안 문제가 되는가? (3) Android 10에서 ATMS가 AMS에서 분리되며 패키지가 어디로 옮겨졌고, 그 이유는?

**참고** — AOSP `frameworks/base` (`services/core/java/com/android/server/wm/ActivityTaskManagerService.java`, `ActivityStarter.java`, `am/ActivityManagerService.java`) at cs.android.com · Android Developers, Tasks and the back stack · Android Security Bulletin (CVE-2020-0096, 2020-05) · Promon, "StrandHogg" 공개 분석.

*다음 글: [PackageManagerService·설치/서명 검증](/posts/android-expert-p2c11/).*
