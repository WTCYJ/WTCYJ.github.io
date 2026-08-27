---
layout: post
title: "Android Security Concept Atlas C17 - Binder 드라이버, node와 handle과 하나의 ioctl"
date: 2026-09-06 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Binder, binderdriver, node, handle, transaction, SingleCopy, ThreadPool, BadBinder, binderfs, ConceptAtlas, 학습기록]
excerpt: "15~16주차에서 저는 'Binder 경계는 두 겹'이라고 관측했지만, 그 경계 안쪽의 드라이버는 읽지 않았습니다. 이 글은 그 내부입니다. 모든 Binder 통신은 /dev/binder 문자 장치의 ioctl 하나로 다중화되고, 커널 드라이버가 서로 못 믿는 프로세스들 사이의 유일한 브로커가 됩니다. 서버가 소유한 node와 클라이언트가 쥔 handle은 완전히 다른 것이고, 데이터는 딱 한 번만 복사되며, 커널이 발신자의 UID를 위조 불가능하게 도장 찍습니다 - 그게 권한 검사의 근거죠. 그리고 이 드라이버는 앱이 ioctl 하나로 닿는 Android 최대 커널 공격 표면입니다. Concept Atlas의 열아홉 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C17 — Binder driver·handle·node·transaction
> **계층**: Tier 3 (IPC·프레임워크) · **난이도**: 고급 · **선수 개념**: C04(프로세스·시스템콜), C12(Zygote)
> **성격**: 보완 편. 라벨/경계는 15~16주차에서 관측했으므로, 여기서는 **드라이버 내부**로 내려갑니다.

15~16주차에서 저는 `ps -A -Z`로 도메인을 보고 "Binder 경계는 두 겹"이라 적었습니다. 그런데 그 경계 **안쪽의 드라이버**는 읽지 않았습니다. 이 모듈이 그 내부입니다.

한 문장으로: **모든 Binder 통신은 `/dev/binder`의 ioctl 하나로 다중화되고, 커널 드라이버가 서로 못 믿는 프로세스들 사이의 유일한 브로커로서 데이터를 한 번만 복사하고 발신자 UID를 위조 불가능하게 도장 찍는다.** 🟡 보완이라 드라이버·객체 모델에 집중합니다.

## 배경 개념 - 하나의 통로, 두 종류의 참조

- **`/dev/binder`**: 문자 장치. 데이터 경로 전체가 `ioctl(fd, BINDER_WRITE_READ, &bwr)` 하나.
- **`binder_node`**: 서비스(서버) 프로세스가 **소유**하는 커널 안의 진짜 객체.
- **`binder_ref` / handle**: 클라이언트가 쥔 참조. 유저스페이스엔 **작은 정수(handle)**로만 노출, **프로세스별**.
- **transaction**: 호출 하나. BC_* 명령(클→드라이버)과 BR_* 반환(드라이버→클).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**Android IPC의 커널 브로커**입니다. 앱↔프레임워크, 프레임워크↔벤더(HAL, C20/C31)의 거의 모든 통신이 이 드라이버를 지납니다. 15~16주차의 "경계 두 겹"이 실은 여러 **binder 도메인**(질문 6)이었습니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **커널 드라이버(`drivers/android/binder.c`, EL1)**가 브로커/라우터입니다. `/dev/binder`를 여는 프로세스마다 `binder_proc`를 갖고, **드라이버가** 프로세스 사이에서 데이터를 복사하고 참조를 해석하고 대상 스레드를 깨웁니다. **유저스페이스는 드라이버하고만** 대화하지, 상대 프로세스 주소 공간을 직접 만지지 않습니다.
- 데이터 경로는 `open()` 한 번, `mmap()` 한 번, 이후 `ioctl(BINDER_WRITE_READ)` 루프. `read()`/`write()`로 payload를 주고받지 않습니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **커널이 발신자 신원을 도장 찍습니다(위조 불가).** 드라이버가 발신자 task의 **effective uid**(`sender_euid = task_euid`)와 pid(tgid)를 트랜잭션에 박아, 수신자가 `getCallingUid()`/`getCallingPid()`로 읽습니다. 발신자가 피어와 직접 대화하지 않으므로 **위조할 수 없습니다** — 이게 권한 검사(C22)의 근거입니다.
- **node와 handle은 다릅니다.** node=서버 소유의 진짜 참조, handle=클라이언트의 **프로세스별 작은 정수 디스크립터**. 같은 node가 클라이언트 A에겐 handle 4, B에겐 handle 9입니다 — 숫자는 그 프로세스 밖에선 무의미합니다. 드라이버가 node↔ref 매핑을 쥐고 handle을 번역합니다.
- **handle 0은 컨텍스트 매니저(servicemanager, C19)** 예약입니다. `BINDER_SET_CONTEXT_MGR`로 한 프로세스가 차지하고(도메인당 하나, SELinux 게이트), 나머지는 handle 0에 트랜잭션해 이름으로 서비스를 얻습니다.
- **신뢰하면 안 되는 것들**: "handle은 포인터/전역 ID"(프로세스별 디스크립터), "유저스페이스가 UID를 위조"(커널이 찍음), "발신자가 상대와 직접 통신"(드라이버 경유만).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: BC_* 명령(`BC_TRANSACTION` + 대상 handle + 메서드 코드 + Parcel).
- **출력**: BR_* 반환(`BR_TRANSACTION`을 대상에, `BR_REPLY`를 발신자에).

**단일 복사**가 정의적 성질입니다: 대상 프로세스가 `mmap`한 버퍼(유저스페이스엔 **읽기전용**, 드라이버가 채움)로, 드라이버가 발신자에서 `copy_from_user`를 **한 번만** 해 넣습니다 — 파이프/소켓의 2회 복사와 대비. Parcel 안에 박힌 객체·fd는 `flat_binder_object`로 드라이버가 경계에서 **번역**합니다(발신자 소유 객체→node; 수신자가 소유주면 로컬 포인터, 아니면 handle; fd는 대상에 dup).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**드라이버는 앱(EL0)이 `ioctl` 하나로 닿는 Android 최대 커널 공격 표면 중 하나입니다.**

- **Bad Binder(CVE-2019-2215)**: binder 드라이버의 **use-after-free**로, 비특권 앱(심지어 Chrome 렌더러 샌드박스)에서 **EL0→EL1 커널 LPE**를 얻었고 실제로 악용됐습니다(Project Zero/TAG가 익스플로잇 벤더 사용 확인). C05의 "EL0→EL1이 곧 커널 LPE"의 실물입니다.
- **refcount/death 버그**: node/ref의 over/under-decrement·UAF가 반복되는 binder 커널 CVE의 원천입니다.
- **스레드풀 소진**: 깊은 재진입 호출이 풀을 고갈시키면 liveness/DoS.
- **버퍼 회계**: `BC_FREE_BUFFER`를 빼먹으면 고정 크기 버퍼가 새어 트랜잭션이 실패합니다.

이건 제 CVE 시리즈(8편 BT·9편 Parcel)와 같은 결의 메모리 안전 문제가 **커널의 IPC 코어**에서 벌어지는 것입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **세 binder 도메인(Treble, Android 8.0)**: `/dev/binder`(프레임워크/앱 AIDL), `/dev/hwbinder`(HIDL HAL), `/dev/vndbinder`(벤더↔벤더 AIDL). **같은 드라이버 코드, 별도 장치·별도 컨텍스트 매니저·별도 SELinux 도메인**으로 system↔vendor 분리(C31)를 강제.
- **binderfs**(`CONFIG_ANDROID_BINDERFS`, Linux 5.0 메인라인/GKI): 정적 노드 대신 파일시스템으로 동적 프로비저닝.
- **scatter-gather**(Android 8): 큰 데이터 전송 최적화.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ls -l /dev/binder*`(세 도메인 장치), `ls -l /proc/<pid>/fd`/`lsof`(이 프로세스가 어느 도메인에 참여하는지 — /dev/binder vs hwbinder vs vndbinder fd).
- `/sys/kernel/debug/binder`(트랜잭션/통계, 접근 가능 시), `dumpsys`.
- **소스**: 커널 `drivers/android/binder.c`(`binder_transaction`·`binder_alloc`), AOSP `frameworks/native/libs/binder`(`ProcessState`/`IPCThreadState`, `BpBinder`(클라이언트 프록시)/`BBinder`(로컬 객체), `DEFAULT_MAX_BINDER_THREADS=15`).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **15~16주차(경계 두 겹)**: 실은 세 binder 도메인(framework/hw/vnd)의 분리였습니다.
- **C22(confused deputy)**: 커널이 찍는 euid/pid가 CVE-2022-20425 같은 "호출자 신원" 검사의 위조 불가 근거입니다.
- **C18(Parcel)**: `flat_binder_object`의 **형식**은 C18, 드라이버의 node/ref **재작성**은 C17입니다.
- **C19(servicemanager)**: handle 0의 정책이 C19입니다.
- **C05(EL)**: Bad Binder가 EL0→EL1의 실물.
- **C20/C31(HAL·Treble)**: hwbinder/vndbinder가 HIDL/벤더 AIDL을 나릅니다.
- 다음은 **C19(servicemanager)** 또는 **C20(AIDL·HIDL·HAL)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 하나의 트랜잭션 — node 와 handle, 단일 복사 ]

클라이언트 프로세스                     서버(서비스) 프로세스
  BpBinder(handle=4) ─BC_TRANSACTION→   binder_node(소유)
      │ ioctl(BINDER_WRITE_READ)             ▲
      ▼                                      │ 드라이버가 handle→node 해석
  커널 드라이버(binder.c)                     │
      │ 발신자 euid/pid 도장(위조 불가)        │
      │ copy_from_user 1회 → 서버의 mmap RO 버퍼(단일 복사)
      │ flat_binder_object: node↔handle·fd dup 번역
      ▼                                      ▼
  BR_REPLY ◀──────────────────  서버 binder 스레드: onTransact → BC_REPLY
  (동기면 발신 스레드 블록; oneway 면 즉시 반환·per-node 큐)
```

## 오개념 판별 문제 5개

1. "Binder 메시지를 보내는 것은 소켓에 write하는 것과 같다."
2. "handle은 서비스 객체의 포인터이거나 프로세스 간 공유되는 전역 ID다."
3. "발신자가 트랜잭션에 자기 UID를 넣으므로 악성 앱은 UID를 위조할 수 있다."
4. "Binder는 데이터를 커널을 거쳐 두 번 복사한다(파이프처럼)."
5. "`/dev/binder`·`/dev/hwbinder`·`/dev/vndbinder`는 서로 다른 드라이버다."

<details><summary>판정 기준(펼치기)</summary>

1. 아닙니다. 모든 것(송신·수신·응답·refcount·death 등록)이 **하나의 `ioctl(BINDER_WRITE_READ)`** 안 BC_*/BR_* 옵코드로 다중화됩니다.
2. handle은 포인터도 전역 ID도 아닙니다. **발신 프로세스의 `binder_ref` 테이블을 인덱싱하는 작은 정수**이고, 같은 node가 프로세스마다 다른 handle입니다.
3. 커널 드라이버가 발신자 task의 **effective uid/pid를 직접 박습니다**(`sender_euid=task_euid`). 유저스페이스가 넣는 값이 아니라 위조할 수 없습니다.
4. **단일 복사**입니다: 드라이버가 발신자에서 대상의 mmap 버퍼로 `copy_from_user`를 한 번만 합니다. 파이프/소켓의 2회 복사와 대비되는 성능 성질입니다.
5. **같은 드라이버 코드(binder.c)**의 별도 장치 인스턴스입니다. Treble이 컨텍스트를 셋으로 나눠 각자 컨텍스트 매니저·SELinux 도메인을 갖게 한 것입니다.
</details>

## 서술형 문제 3개

1. `binder_node`(서버 소유)와 `handle`(클라이언트 측 프로세스별 정수)의 차이를, 드라이버가 어떻게 handle을 node로(그리고 다른 프로세스의 다른 handle로) 번역하는지로 설명하세요.
2. 커널이 발신자 euid/pid를 도장 찍는 것이 왜 권한 검사(C22)의 위조 불가 근거인지, 그리고 그것이 왜 유저스페이스에서 스푸핑되지 않는지 서술하세요.
3. Bad Binder(CVE-2019-2215)가 왜 EL0→EL1 커널 LPE인지(C05)와, binder 드라이버가 왜 큰 커널 공격 표면인지 서술하세요.

## 소스 탐색 과제

- 실기기/에뮬에서 `ls -l /dev/binder*`로 세 도메인 장치를, `ls -l /proc/<pid>/fd`(예: `system_server`·앱·HAL 프로세스)로 각 프로세스가 어느 binder 도메인에 참여하는지 확인하세요.
- 가능하면 `/sys/kernel/debug/binder/transactions`나 `dumpsys` 일부로 활성 트랜잭션/노드를 관측하세요.
- 커널 소스 `binder_transaction()`에서 `sender_euid`가 어디서 오는지 한 곳 인용하세요(위조 불가의 근거).

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **도메인 실측**: `ls -l /dev/binder*`와 대표 프로세스의 fd로 세 도메인 참여를 캡처.
2. **node/handle 서술**: 소스(`binder.c`)에서 node/ref 번역과 `sender_euid` 도장을 인용해 서술.
3. **공격면 서술**: Bad Binder를 EL0→EL1(C05)로 귀속하고, refcount/death가 왜 반복 CVE인지.
4. **경계 재해석**: 15~16주차의 "경계 두 겹" 관측을 세 binder 도메인으로 재서술.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

15~16주차에 관측만 했던 "Binder 경계"의 안쪽이 이것이었습니다: `/dev/binder`의 ioctl 하나로 다중화되는 통로, 서로 못 믿는 프로세스 사이의 유일한 커널 브로커, 서버 소유의 node와 클라이언트별 handle, 한 번만 하는 복사, 그리고 무엇보다 **커널이 위조 불가능하게 찍는 발신자 UID** — 이게 모든 권한 검사(C22)의 근거입니다. 동시에 이 드라이버는 앱이 `ioctl` 하나로 닿는 최대 커널 공격 표면이라, Bad Binder 같은 EL0→EL1 LPE가 나옵니다. 다음은 handle 0의 주인 **C19(servicemanager)**, 또는 이 위에 얹히는 **C20(AIDL·HIDL·HAL)**로 이어집니다.
