---
layout: post
title: "Binder proxy/stub·thread pool"
date: 2026-11-26 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Binder, IPC, AIDL, ThreadPool]
excerpt: "Binder 프록시는 원격 객체가 아니라 32비트 핸들 하나를 든 껍데기다. 흔한 착각 — getCallingUid()는 clearCallingIdentity() 이후엔 내 프로세스 UID를 돌려주므로, 권한 검사를 그 뒤에 두면 confused deputy가 된다."
---

Android에서 `getSystemService(...)`로 받은 매니저 객체는 시스템 서비스가 아니다. 다른 프로세스에 있는 진짜 서비스를 가리키는 **프록시**일 뿐이고, 그 프록시가 감춘 것이 Binder다. 앱이 메서드 하나를 부르면 인자는 Parcel로 직렬화돼 커널 binder 드라이버를 건너 system_server의 **binder 스레드**에서 되살아나고, 거기서 실제 로직과 권한 검사가 돈다. 이 왕복 구조를 모르면 "권한 검사를 어디에 둬야 하나", "왜 이 서비스가 느려지면 폰 전체가 먹통이 되나" 같은 질문에 답할 수 없다.

이 글은 AIDL이 만들어내는 proxy/stub 코드와 libbinder의 BpBinder/BBinder, 그리고 이들을 실제로 돌리는 binder 스레드 풀을 AOSP 소스와 함께 정리하고, 에뮬레이터에서 스레드/버퍼 상태를 관측한 기록이다. 공격 실습이 아니라 신뢰 경계가 어디에 그어지는지를 소스 수준에서 짚는 것이 목적이다.

> **한 줄 결론**: Binder의 신뢰 경계는 커널이 채워주는 호출자 UID/PID 단 하나이며 이 값은 위조 불가다 — 그래서 권한 검사는 반드시 `clearCallingIdentity()` 이전, `onTransact` 진입 직후에 해야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 셋이다. (1) AIDL이 생성하는 `Stub`/`Proxy`와 `transact`/`onTransact` 디스패치, (2) 그 밑 libbinder의 `BpBinder`(프록시)·`BBinder`(스텁)와 `IPCThreadState`가 Parcel을 나르는 경로, (3) `ProcessState`/`IPCThreadState`가 관리하는 binder 스레드 풀의 크기·고갈. 공격 방법이 아니라 구조와 소스를 읽는다.

선수 지식으로 세 가지가 밑에 깔린다. 프로세스와 UID 격리(각 앱이 별도 UID로 샌드박싱된다는 것), Parcel 직렬화(인자가 바이트로 평탄화된다는 것), 그리고 SELinux가 도메인 간 `binder { call transfer }`를 통제한다는 것이다. Atlas C08(Binder 개론)과 C12(SELinux)의 개념을 알고 있으면 충분하다.

전체 흐름에서 이 장의 위치는 App→Framework→**Binder**→system_server의 정중앙이다. 앞 장들이 프레임워크 서비스(AMS·PMS·WindowManager)를 다뤘다면, 그 서비스들이 앱과 대화하는 유일한 통로가 여기서 설명하는 Binder다. 다음 장의 Stable AIDL은 이 프록시/스텁을 버전 안정적으로 만드는 이야기다.

## 핵심 개념 — 프록시/스텁과 스레드 풀

AIDL `interface IFoo` 하나를 컴파일하면 세 조각이 나온다. 인터페이스 `IFoo`, 수신자 측 추상 클래스 `IFoo.Stub`(= `android.os.Binder`를 상속), 호출자 측 `IFoo.Stub.Proxy`(= `IBinder mRemote`를 든 껍데기). 핵심은 `asInterface()`다 — 같은 프로세스면 `queryLocalInterface`가 로컬 구현을 그대로 돌려주고(직접 호출, IPC 없음), 다른 프로세스면 `BinderProxy`를 `Proxy`로 감싼다. `Source-confirmed`

```java
// AIDL이 생성하는 코드의 골격 (개념용)
public static IFoo asInterface(IBinder obj) {
  if (obj == null) return null;
  IInterface iin = obj.queryLocalInterface(DESCRIPTOR);
  if (iin instanceof IFoo) return (IFoo) iin;   // 같은 프로세스 → 직접 호출
  return new IFoo.Stub.Proxy(obj);              // 다른 프로세스 → 프록시
}
// Proxy 측: 인자를 Parcel에 쓰고 커널로 넘긴다
mRemote.transact(Stub.TRANSACTION_doThing, _data, _reply, 0);
// Stub 측: binder 스레드에서 되살아나 디스패치
public boolean onTransact(int code, Parcel data, Parcel reply, int flags) { ... }
```

이 Java 계층은 libbinder(C++) 위에 앉는다. 계층별 대응은 아래와 같고, 프록시가 실제로 든 것은 원격 객체가 아니라 **프로세스별 핸들 테이블의 32비트 핸들**이라는 점이 요점이다. `Source-confirmed`

| 계층 | 프록시(호출자 측) | 스텁(수신자 측) | 전송 |
|--|--|--|--|
| AIDL/Java | `IFoo.Stub.Proxy`(`mRemote:BinderProxy`) | `IFoo.Stub` (extends `Binder`) | `transact()` → `onTransact()` |
| libbinder(C++) | `BpBinder`(handle) / `BpInterface` | `BBinder` / `BnInterface` | `IPCThreadState::transact` |
| 커널 binder | handle → ref | `binder_node` | `binder_transaction()` |

스레드 풀은 별도다. 프록시 호출은 스레드를 만들지 않는다 — **수신 측**이 미리 스레드를 띄워 두고 들어오는 트랜잭션을 처리한다. `ProcessState::startThreadPool()`이 풀을 열고, 각 스레드는 `IPCThreadState::joinThreadPool()` 루프에서 `BR_TRANSACTION`을 읽어 `BBinder::transact`→`onTransact`로 흘려보낸다. 커널은 처리 여력이 모자라면 `BR_SPAWN_LOOPER`를 보내 스레드를 하나 더 요청하고, 프로세스는 상한까지만 늘린다. 이 상한이 `DEFAULT_MAX_BINDER_THREADS = 15`다(메인 스레드는 별도, system_server 등은 더 크게 설정 가능). `Source-confirmed` 스레드 이름은 `Binder:<pid>_<n>`으로 붙는다. `Reported`

> **[그림 1]** AIDL 인터페이스 하나를 빌드해 생성된 `IFoo.java`에서 `Stub`·`Proxy`·`asInterface`·`onTransact`가 나온 부분을 편집기로 펼친 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

Binder에서 신뢰 경계는 **프로세스 경계**이고, 그 경계를 통과할 때 커널이 트랜잭션에 발신자의 UID/PID를 직접 박아 넣는다. 그래서 `onTransact` 안에서 `Binder.getCallingUid()`/`getCallingPid()`가 돌려주는 값은 호출자가 위조할 수 없다 — 이것이 Android 권한 모델 전체의 앵커다. `Source-confirmed` 서비스가 "이 호출자가 이 권한을 갖고 있나"를 판단하는 근거는 오직 이 값이다.

위협 모델은 두 축이다. 첫째, **confused deputy**. `clearCallingIdentity()`는 호출자 신원을 지우고 현재 프로세스(예: system_server, 즉 system UID) 신원으로 바꾼다 — 특권 리소스에 접근하려고 흔히 쓴다. 문제는 이 뒤에서 `getCallingUid()`를 부르면 원래 호출자가 아니라 system을 보게 된다는 것. 권한 검사를 `clearCallingIdentity()` **뒤**에 두면 검사는 항상 통과하고, 서비스는 자기 특권을 호출자에게 빌려주는 대리인이 된다. `Inferred`

둘째, **스레드 풀 고갈**. 풀은 상한이 있으므로(기본 15), 느리거나 블로킹되는 트랜잭션으로 모든 binder 스레드를 점유하면 그 서비스로 오는 새 호출이 큐에 쌓이고 호출자들이 줄줄이 블로킹된다. system_server가 이렇게 막히면 watchdog이 돌거나 시스템 전체가 ANR로 흐른다. 이건 RCE도 권한 상승도 아닌 **가용성(DoS) 문제**다 — 크래시나 무한 대기를 취약점으로 부풀리지 않도록 등급을 정확히 봐야 한다. `Inferred`

## 관측

에뮬레이터(userdebug, `adb root`)에서 binder 상태는 debugfs로 직접 볼 수 있다. 각 프로세스의 최대 스레드 수, 준비된 스레드, 비동기(oneway) 여유 공간이 그대로 노출된다. 아래는 안전 범위(로컬 AVD·자작 앱)에서만 돌린다.

```bash
adb root
# 프로세스별 binder 상태: max threads, ready threads, free async space
adb shell 'cat /sys/kernel/debug/binder/proc/$(pidof system_server)'
# binder 스레드가 실제로 여러 개 떠 있는지
adb shell 'ps -T -p $(pidof system_server)' | grep -i binder
# 전역 통계(트랜잭션/노드/ref 카운트)
adb shell cat /sys/kernel/debug/binder/stats
# 최신 커널/Android는 이 debug 노드가 binderfs로 옮겨져 위 경로가 비거나 없을 수 있다.
# 그때는 binderfs 경로로: /dev/binderfs/binder_logs/proc/<pid>, /dev/binderfs/binder_logs/stats
```

`예시 출력`(네 실제 실행으로 교체 — 커널 버전에 따라 형식이 다르다):

```
# ps -T 발췌
  PID   TID CMD
 1523  1587 Binder:1523_1
 1523  1590 Binder:1523_2
 1523  1602 Binder:1523_4

# /sys/kernel/debug/binder/proc/<pid> 발췌
proc 1523
context binder
  max threads 31
  ready threads 6
  free async space 520192
```

여기서 두 가지를 읽는다. (1) 스레드 이름이 `Binder:<pid>_<n>`으로 여럿 떠 있으면 풀이 실제로 돌고 있는 것. (2) `free async space`가 전체 버퍼의 절반쯤에서 시작한다 — oneway 트랜잭션이 여기서 깎이고, 0에 닿으면 그 뒤 oneway 호출은 실패한다. `Reported`(형식·수치는 커널 버전별로 원문 재확인 필요)

> **[그림 2]** `/sys/kernel/debug/binder/proc/<pid>`에서 `max threads`·`ready threads`·`free async space`가 보이는 줄과, `ps -T`의 `Binder:pid_n` 스레드 목록을 나란히 캡처한 화면 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

호출자 UID를 위조할 수 없는 이유는 프레임워크가 아니라 **커널**이 채우기 때문이다. 앱은 자기 Parcel에 UID를 쓸 기회가 없다 — `binder_transaction()`이 트랜잭션을 배달할 때 발신 태스크의 `cred`에서 euid를, 발신 태스크에서 pid(`task_tgid_nr_ns`)를 읽어 트랜잭션에 박는다. 프레임워크의 `getCallingUid()`는 그 커널이 넣은 값을 읽을 뿐이다. 그래서 신뢰의 뿌리가 사용자 공간이 아닌 커널에 있고, `clearCallingIdentity()`는 이 "커널이 준 진실"을 **일부러 덮어쓰는** 연산이라 위험한 것이다. `Source-confirmed`

스레드 풀이 상한을 갖는 이유는 자원 보호다. 무제한이면 악의적이든 실수든 폭주하는 호출이 수신 프로세스의 스레드/메모리를 무한히 잡아먹는다. 그래서 프로세스마다 상한을 두고 커널이 `BR_SPAWN_LOOPER`로 필요할 때만 늘린다. 트랜잭션 버퍼도 같은 논리로 유한하다 — 프로세스당 mmap 크기는 `1MB - (페이지 2장)`, 4KB 페이지에서 약 1MB−8KB이고, 이걸 넘기면 Java 계층에서 `TransactionTooLargeException`이 난다. `Source-confirmed` 그리고 oneway(비동기) 트랜잭션은 합쳐서 버퍼의 절반(`free_async_space`, 초기값=버퍼/2)까지만 쓸 수 있게 상한이 걸려 있고 — 동기 호출은 버퍼 전체를 쓸 수 있다 — oneway를 남발하면 동기 호출과 무관하게 이 async 상한부터 고갈된다. `Reported`

정리하면, "핸들 하나 든 프록시 + 커널이 박은 신원 + 유한한 스레드/버퍼"라는 세 설계가 맞물려, 편의를 위한 `clearCallingIdentity`나 무심한 oneway 남발이 곧바로 보안·가용성 결함으로 번진다.

## 방어와 회귀 검증

- **권한 검사는 신원을 지우기 전에.** `onTransact`(또는 서비스 메서드) 진입 직후 `getCallingUid()`/`enforceCallingPermission()`으로 검사하고, 그 다음에야 `clearCallingIdentity()`로 특권 작업을 한다. `restoreCallingIdentity(token)`은 `try/finally`로 반드시 복원한다 — 예외 경로에서 신원이 새면 이후 호출이 잘못된 UID로 돈다.
- **입력은 신뢰 경계 데이터로 취급.** Parcel로 넘어온 값은 전부 외부 입력이다. 인덱스·크기·핸들을 검증하지 않고 쓰면 서비스 측에서 크래시나 논리 오류가 난다. 큰 페이로드는 잘라 보내거나(`TransactionTooLargeException` 회피) 공유 메모리/파일 디스크립터로 우회한다.
- **oneway와 풀 고갈.** 응답이 필요 없는 알림성 호출만 oneway로, 무거운 작업은 서비스가 즉시 반환하고 자체 워커로 넘겨 binder 스레드를 오래 잡지 않는다. 그래야 한 클라이언트가 풀을 통째로 점유하지 못한다.
- **회귀 검증.** SELinux `neverallow`가 도메인 간 `binder call`을 원천 차단하는지 CTS/정책 테스트로 확인하고, 서비스는 CTS의 권한 우회 테스트로 "검사 위치"가 리팩터링 중 뒤로 밀리지 않았는지 지킨다. `Inferred`

버전 차이도 하나 — 최대 스레드 수·버퍼 크기 같은 상수는 프로세스 종류(앱 vs system_server)와 AOSP 버전에 따라 다르게 설정될 수 있으니, 문서화할 땐 관측한 값을 함께 적는다.

## 정리

- 프록시(`BpBinder`/`Proxy`)는 원격 객체가 아니라 커널 핸들 하나를 든 껍데기이고, 실제 로직·권한 검사는 수신 프로세스의 binder 스레드에서 `onTransact`로 돈다.
- 신뢰 경계는 커널이 박아 넣는 호출자 UID/PID뿐이다 — 위조 불가이므로 권한 검사는 반드시 `clearCallingIdentity()` 이전에.
- 스레드 풀(기본 상한 15)과 트랜잭션 버퍼(≈1MB−8KB, oneway는 버퍼 절반까지만)는 유한하다 — 고갈은 권한 상승이 아니라 가용성(DoS) 문제로 정확히 등급을 매긴다.

**점검 질문** — (1) `asInterface()`가 같은 프로세스와 다른 프로세스에서 각각 무엇을 돌려주는가? (2) 권한 검사를 `clearCallingIdentity()` 뒤에 두면 왜 confused deputy가 되는가? (3) oneway 남발이 동기 호출과 무관하게 서비스를 막을 수 있는 이유는?

**참고** — [AIDL 개요](https://developer.android.com/develop/background-work/services/aidl) · [frameworks/native/libs/binder (ProcessState.cpp / IPCThreadState.cpp / BpBinder.cpp)](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/native/libs/binder/) · [android.os.Binder](https://developer.android.com/reference/android/os/Binder) · Linux `drivers/android/binder.c`

*다음 글: [Stable AIDL·Java/NDK/Rust backend](/posts/android-expert-p2c15/).*
