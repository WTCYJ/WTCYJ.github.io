---
layout: post
title: "Android Security Concept Atlas C17 | 가상 실습 보고서 — Binder 드라이버, node와 handle과 하나의 ioctl"
date: 2026-08-29 23:12:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Binder, binderdriver, node, handle, transaction, SingleCopy, ThreadPool, BadBinder, binderfs, ConceptAtlas, 학습기록]
excerpt: "15~16주차에서 저는 'Binder 경계는 두 겹'이라고 관측했지만, 그 경계 안쪽의 드라이버는 읽지 않았습니다. 이 글은 그 내부입니다. 모든 Binder 통신은 /dev/binder 문자 장치의 ioctl 하나로 다중화되고, 커널 드라이버가 서로 못 믿는 프로세스들 사이의 유일한 브로커가 됩니다. 서버가 소유한 node와 클라이언트가 쥔 handle은 완전히 다른 것이고, 데이터는 딱 한 번만 복사되며, 커널이 발신자의 UID를 위조 불가능하게 도장 찍습니다 - 그게 권한 검사의 근거죠. 그리고 이 드라이버는 앱이 ioctl 하나로 닿는 Android 최대 커널 공격 표면입니다. Concept Atlas의 열아홉 번째 모듈입니다."
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

![C17 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-binder.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






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

## 호출 흐름

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

## 실측으로 확인한 것

가상 실습 환경(codex-atlas-api33, x86_64, Android 13/API 33)에서 이 모듈의 핵심 주장을 실제 명령으로 확인했다. 상단 검증 화면(`evidence-binder.png`)과 호스트 `adb shell` 교차 확인이 근거다.

**1) Binder는 하나의 통로가 아니라 세 도메인으로 갈라져 있다(질문 6).** `ls`가 세 개의 별도 문자 장치를 그대로 보여준다.

```console
$ ls -l /dev/{binder,hwbinder,vndbinder}
```

세 노드가 모두 존재한다는 관측(검증 블록의 "binderfs의 세 Binder 노드")이 질문 6의 세 도메인 주장을 파일시스템 수준에서 확증한다. 같은 `binder.c` 코드의 별도 장치 인스턴스이고, binderfs가 정적 노드 대신 이 노드들을 프로비저닝하며, Treble의 system↔vendor 분리(C31)가 여기서 장치 단위로 강제된다 — 오개념 판별 5번("서로 다른 드라이버다")이 반증되는 지점이다.

**2) handle 0의 컨텍스트 매니저가 서비스를 이름으로 중개한다(질문 3).** `service list`가 등록된 서비스 목록을 돌려준다.

```console
$ service list
```

255개 서비스 등록(검증 블록의 관측 결과)은, 나머지 프로세스가 handle 0(servicemanager, C19)에 트랜잭션해 이름으로 node를 얻는 구조의 실물이다. 서비스 하나하나가 서버 소유 node이고 클라이언트는 이름으로 그 참조를 요청한다는, node와 handle을 가르는 질문 3·질문 4의 골격이 서비스 디렉터리 수준에서 드러난다.

**3) sender_euid 도장과 node↔ref 번역은 드라이버 소스에서 근거를 확정했다.** 위조 불가 신원(`sender_euid = task_euid`)과 node↔handle 재작성은 유저스페이스에서 관측되는 값이 아니라 커널 `drivers/android/binder.c`의 `binder_transaction()` 안에서 드라이버가 수행하는 동작이다. 발신자 euid가 유저스페이스 입력이 아니라 드라이버가 발신자 task에서 직접 읽어 트랜잭션에 박는 값이라는 점이 질문 3의 "커널이 도장 찍는다(위조 불가)"와 C22 권한 검사의 근거를 이룬다 — 오개념 판별 3번("악성 앱이 UID를 위조")은 이 소스 사실 앞에서 성립하지 않는다.

**4) 드라이버 안에서 트랜잭션이 실제로 돌고 있음을 root로 binderfs와 통계까지 캡처했다(질문 2·4·5).** binderfs를 나열하면 세 도메인 장치 외에 `binder-control`·`binder_logs`·`features`가 함께 잡히고, 드라이버의 `binder_logs/stats`가 라이브 명령 카운터를 그대로 돌려준다.

```console
$ ls /dev/binderfs
binder  binder-control  binder_logs  features  hwbinder  vndbinder
$ cat /dev/binderfs/binder_logs/stats
BC_TRANSACTION: 113300
BC_REPLY: 88602
BC_FREE_BUFFER: 211526
BC_INCREFS: 14673
BC_ACQUIRE: 14674
BC_RELEASE: 7642
BC_DECREFS: 7633
BC_INCREFS_DONE: 11027
BC_ACQUIRE_DONE: 11032
BC_REGISTER_LOOPER: 429
BC_ENTER_LOOPER: 209
```

11만 건이 넘는 `BC_TRANSACTION`과 그에 짝지어진 `BC_REPLY`·`BC_FREE_BUFFER` 카운터는, 질문 4의 단일 복사 트랜잭션 경로가 소스로 확정한 동작인 동시에 이 세션에서 실제로 돌고 있는 상태로 계측됨을 보여준다. `BC_FREE_BUFFER`(211,526)가 `BC_TRANSACTION`+`BC_REPLY`(약 201,902)와 같은 자릿수로 맞물려, 질문 5의 버퍼 회계(트랜잭션마다 버퍼를 잡고 풀어야 한다)가 드라이버 카운터 수준에서 균형을 이룬다. `BC_INCREFS`/`BC_ACQUIRE`와 `BC_DECREFS`/`BC_RELEASE`, 그리고 각 `*_DONE` 쌍은 질문 3의 node↔ref 번역이 관리하는 참조 카운팅이 살아 움직인 흔적이다. 통계 노드가 root로 열려, 앞서 소스로 근거화한 드라이버 동작이 계측값으로도 확증됐다.

## 소스로 확정한 것

x86_64 AVD로는 실행되지 않는 실물 하드웨어·ARM64 런타임 속성은 공식 문서와 소스로 확정하고, 검증 가능한 정적 근거는 실측으로 뒷받침했다.

- **ARM64 하드웨어 완화(PAC·BTI·MTE, EL0→EL1 전이)의 런타임 강제는 ARM·AOSP 공식 문서로 확정한다.** 이 호스트는 arm64 이미지를 실행하지 않으므로 런타임 강제는 문서로 확정하되, **정적 마커는 실측했다**: arm64 타깃으로 `.so`를 빌드해 `readelf -n`으로 `.note.gnu.property`의 `aarch64 feature: BTI, PAC`를 그대로 뽑았고, `-mbranch-protection=none` 대조군에서는 이 note가 0건으로 사라지는 것까지 확인했다(Atlas의 arm64 정적 마커 실측). 마커는 실측, 런타임 강제는 소스 확정이다. — [Arm MTE (AOSP)](https://source.android.com/docs/security/test/memory-safety/arm-mte) · [clang `-mbranch-protection`(BTI·PAC)](https://clang.llvm.org/docs/ClangCommandLineReference.html)
- **Bad Binder(CVE-2019-2215)의 EL0→EL1 커널 LPE 귀속은 공개 분석과 `drivers/android/binder.c`의 use-after-free 구조로 확정한다(C05).** 이 시리즈는 비무기화 원칙에 따라, 동작 익스플로잇 실행이 아니라 드라이버 구조와 판정 지점까지를 범위로 삼는다. — [drivers/android/binder.c (커널 소스)](https://cs.android.com/android/kernel/superproject/+/common-android-mainline:common/drivers/android/binder.c)
- **hwbinder/vndbinder가 나르는 벤더 HIDL·AIDL 인터페이스 계약은 Treble 아키텍처로 확정한다(C31).** 세 도메인 장치 노드의 존재 자체는 실측이다(항목 1·4). — [frameworks/native/libs/binder (AOSP)](https://cs.android.com/android/platform/superproject/+/master:frameworks/native/libs/binder/) · [Android AIDL 가이드](https://developer.android.com/guide/components/aidl) · [HIDL·벤더 인터페이스(Treble)](https://source.android.com/docs/core/architecture/hidl)

## 마치며

15~16주차에 관측만 했던 "Binder 경계"의 안쪽이 이것이었습니다: `/dev/binder`의 ioctl 하나로 다중화되는 통로, 서로 못 믿는 프로세스 사이의 유일한 커널 브로커, 서버 소유의 node와 클라이언트별 handle, 한 번만 하는 복사, 그리고 무엇보다 **커널이 위조 불가능하게 찍는 발신자 UID** — 이게 모든 권한 검사(C22)의 근거입니다. 동시에 이 드라이버는 앱이 `ioctl` 하나로 닿는 최대 커널 공격 표면이라, Bad Binder 같은 EL0→EL1 LPE가 나옵니다. 다음은 handle 0의 주인 **C19(servicemanager)**, 또는 이 위에 얹히는 **C20(AIDL·HIDL·HAL)**로 이어집니다.
