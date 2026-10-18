---
layout: post
title: "init rc·property service·SELinux policy"
date: 2026-12-01 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, init, SELinux, PropertyService, sepolicy]
excerpt: "속성 읽기는 공유 메모리에서 누구나 한다. 하지만 쓰기는 init이 SELinux property_contexts로 검사한다 — setprop이 조용히 실패하면 root가 없어서가 아니라 그 도메인에 쓰기 권한이 없어서다."
---

Android가 부팅될 때 커널이 사용자 공간에서 마지막으로 하는 일은 첫 프로세스, PID 1 `init`을 띄우는 것이다. 이 init이 파티션을 마운트하고, SELinux 정책을 로드하고, 수백 개의 서비스와 시스템 속성을 조립한다. 앱이 `getprop`으로 읽는 값, `setprop`이 조용히 실패하는 이유, root인데도 못 하는 동작 — 이 셋의 뿌리가 전부 여기 **init · property service · SELinux** 삼각형에 있다.

이 글은 그 삼각형을 AOSP 소스(`system/core/init`, `bionic`, `system/sepolicy`)와 에뮬레이터 관측으로 정리한 기록이다. 우리가 흔히 "root면 뭐든 된다"고 착각하는 자리에, 실제로는 타입으로 못 박힌 경계가 세 겹 깔려 있다.

> **한 줄 결론**: init은 부팅을 조립하는 동시에 시스템 속성의 **단일 정책 지점**이고, SELinux는 그 위에서 root조차 도메인으로 가두는 MAC이다 — uid(DAC)만 보면 딱 절반만 본 것이다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 범위는 네 가지다. (1) Android Init Language(`.rc`)의 문법과 부팅 스테이지, (2) property service가 **읽기(공유 메모리)와 쓰기(init 소켓)를 왜 비대칭으로** 처리하는가, (3) SELinux가 프로세스·파일·속성·앱을 각각 어떤 파일로 라벨링하는가, (4) 이 셋이 어떻게 하나의 신뢰 경계를 이루는가.

선수 개념은 리눅스의 DAC(uid/gid/권한 비트)와 프로세스 모델이다(1부 및 Atlas C04). SELinux는 "root도 가두는 강제적 접근제어(MAC)"라는 한 문장만 잡고 들어오면 충분하다. Binder까지 갈 필요는 없지만, `system_server`·`zygote`가 결국 init이 띄운 자식이라는 점(10장 AMS)만 기억하면 그림이 맞물린다.

전체 구조에서 init의 위치는 명확하다. App → Framework → Binder → system_server → HAL → Kernel 흐름에서 init은 **그 모두의 부모**다. init의 `.rc`가 직접 띄우는 것은 `zygote`·`surfaceflinger`·`servicemanager`이며, `system_server`는 그 `zygote`가 `--start-system-server` 인자로 fork한다(init `.rc`에 `service system_server` 항목은 없다). 즉 이 장은 "system_server가 대체 어디서 나오는가"에 대한 소스 수준의 답이다 — 앞서 말한 "system_server·zygote가 결국 init이 띄운 자식"이 바로 이 zygote 경유 경로다.

## 핵심 개념 — init·property·sepolicy 삼각형

**(1) Android Init Language.** init은 `.rc` 파일을 파싱한다. 구성 요소는 네 종류다. `Source-confirmed`

| 요소 | 문법 | 하는 일 |
|--|--|--|
| Action | `on <trigger>` + 명령들 | 트리거가 발생하면 명령 블록 실행 |
| Service | `service <name> <path> <args>` | 데몬 정의(재시작·권한·도메인 옵션 포함) |
| Command | `mount`, `mkdir`, `setprop`, `start`, `write` … | Action 안에서 실행 |
| Option | `class`, `user`, `group`, `seclabel`, `oneshot` … | Service 동작 제어 |

트리거에는 부팅 단계(`early-init`, `init`, `late-init`, `boot`)와 **속성 트리거**(`on property:sys.boot_completed=1`)가 있다. init은 `/system/etc/init`, `/vendor/etc/init` 등에서 `.rc`를 import해 조립한다. `Source-confirmed`

**(2) 부팅 스테이지.** init은 두 단계로 나뉜다. **1단계 init**(램디스크)은 필수 파티션 마운트와 **SELinux 정책 로드·setenforce**를 하고 2단계로 re-exec한다. **2단계 init**은 property service를 띄우고, `.rc`를 파싱해 Action을 실행하고 Service를 기동한다. `Source-confirmed` 핵심은 순서다 — 정책이 enforcing으로 올라간 **뒤에** 대부분의 서비스가 뜬다.

**(3) property service.** 여기가 이 글의 급소다. 읽기와 쓰기가 대칭이 아니다. `Source-confirmed`

- **읽기**: bionic의 `__system_property_get`이 읽기 전용 공유 매핑(`/dev/__properties__`)을 직접 읽는다. **권한 검사 없음** — 누구나 읽는다.
- **쓰기**: `__system_property_set`은 값을 `/dev/socket/property_service` 소켓으로 init에 보낸다. init이 호출자의 SELinux 컨텍스트를 `property_contexts`가 지정한 그 속성의 **타입**에 대해 `set` 권한으로 검사한 뒤에만 기록한다.
- 접두사별 규칙: `ro.`는 한 번만 설정(재설정 거부), `persist.`는 `/data/property`에 영속화, `ctl.`은 서비스 제어(`ctl.start`/`ctl.stop`).

**(4) SELinux 라벨링 네 파일.** SELinux는 대상마다 라벨 소스를 나눈다. `Source-confirmed`

- `file_contexts` → 파일/디렉터리 라벨
- `property_contexts` → 시스템 속성 라벨
- `seapp_contexts` → 앱 프로세스·앱 데이터 라벨
- `*.te`(도메인) → 프로세스 도메인과 `allow`/`neverallow` 규칙

라벨은 대상에 따라 role이 갈린다 — 객체(파일·속성·소켓)는 `u:object_r:<type>:s0`, 프로세스/도메인은 role이 `r`이라 `u:r:<domain>:s0` 형태다(아래 관측의 `u:r:init:s0`이 그 예). `neverallow`는 **빌드 시점**에 정책 컴파일러가 검증한다(회귀 방지). `Source-confirmed`

> **[그림 1]** AOSP `system/core/init/README.md` 또는 `rootdir/init.rc`에서 `on <trigger>` Action 블록과 `service` 정의(seclabel 옵션 포함) 구조를 펼친 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 삼각형의 위협 모델은 외부 침입자가 아니라 **"이미 손상된 특권 프로세스가 얼마나 더 나아갈 수 있나"**다. 경계는 두 겹이다.

- **DAC(uid/gid)** — 전통적 Unix 권한. 그런데 uid 0(root)이면 사실상 전능하다. 이 한 겹만으로는 프로세스 하나가 뚫리면 끝난다.
- **MAC(SELinux)** — uid와 무관하게 "이 도메인이 이 타입에 이 동작을 하도록 정책에 적혀 있는가"를 강제한다. root여도 도메인이 허용 안 하면 막힌다. 이게 절반의 나머지다.

속성 쓰기 경계가 대표적이다. `setprop`은 결국 init에 요청을 보내고, init은 `property_contexts`로 "이 도메인이 이 타입 속성을 `set`할 수 있는가"를 판정한다. 그래서 앱 도메인에서 특권 속성을 바꾸려는 시도는 두 겹에서 막힌다 — 타입에 대한 `set` 권한이 없고(MAC), 애초에 `ro.` 계열은 재설정 불가다. `ctl.start <svc>`처럼 **임의 서비스 기동을 요청하는 제어 속성**은 별도 타입(`ctl_*`)으로 강하게 라벨링돼 아무 도메인이나 못 건드린다. `Source-confirmed`

init 자신은 `u:r:init:s0`라는 매우 특권적인 도메인이지만, 그 특권조차 `neverallow`가 상한을 긋는다. 즉 이 시스템은 "가장 강한 프로세스도 정책이 적힌 만큼만 강하다"를 불변식으로 삼는다. `Inferred`

## 관측 — 에뮬레이터에서 삼각형 확인

전부 **Cuttlefish 또는 AVD userdebug 이미지와 공개 AOSP 소스**로만 확인한다. 제3자·실서비스·실기기 flashing은 없다. SELinux·property는 에뮬레이터로도 그대로 관측된다(1부 연구환경 장에서 정리한 대로 아키텍처 무관 부분).

### 절차

1. enforcing 상태와 빌드 타입을 확인한다.
2. init·주요 서비스의 SELinux **도메인**을 본다.
3. property service 소켓과 property_contexts 매핑을 본다.
4. `ro.`/`persist.` 속성의 성질을 대조한다.

```bash
adb shell getenforce                         # Enforcing
adb shell getprop ro.build.type              # userdebug
adb shell ps -Z | grep -E 'init|zygote'      # 프로세스 도메인
adb shell ls -Z /dev/socket/property_service # 소켓 라벨
adb shell 'cat /system/etc/selinux/plat_property_contexts | head'  # 속성→타입 매핑
adb shell getprop | grep -E 'persist\.'      # 영속 속성 목록
```

> **[그림 2]** Cuttlefish/AVD userdebug에서 `getenforce`·`ps -Z`·`ls -Z /dev/socket/property_service`·`plat_property_contexts` 매핑을 한 화면에 대조한 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — 네 실제 실행으로 바꿔라. 아래는 형태 예시다.

```
$ getenforce
Enforcing
$ getprop ro.build.type
userdebug
$ ps -Z | grep init
u:r:init:s0    root  1  0  ... init
$ ls -Z /dev/socket/property_service
u:object_r:property_socket:s0 property_service
```

세 가지가 한눈에 잡힌다 — init은 자기 도메인(`init`)에서 돌고, property service 소켓은 자기 타입(`property_socket`)으로 라벨링되며, `plat_property_contexts`는 속성 접두사를 타입으로 사상한다. 이 매핑이 곧 "누가 무엇을 쓸 수 있나"의 정책 표다.

## Root Cause — 왜 이렇게 되는가

**읽기와 쓰기가 비대칭인 이유.** 시스템 속성은 전역 설정 버스다. 값을 노출하는 것 자체는 위험이 낮고 빈번하므로, 읽기는 공유 메모리로 열어 검사 없이 빠르게 한다. 반대로 쓰기는 시스템 상태를 바꾸므로 신뢰를 좁혀야 한다. 그래서 **쓰기를 init 한 곳으로 깔때기**처럼 모으고, 거기에 SELinux 검사를 단 한 번 건다. 검사 지점이 하나면 정책도 하나로 관리된다.

**SELinux가 root를 가두는 이유.** 전통적 Unix는 uid 0이면 전능이라, 특권 프로세스 하나가 손상되면 방어선이 무너진다. MAC은 접근 권한을 "무엇을 하도록 설계됐나(타입·도메인)"에 고정해 uid와 분리한다. 그리고 이 불변식이 시간이 지나며 슬금슬금 깨지는 걸 막으려고, `neverallow`를 **빌드 시점에 컴파일러가 검증**한다. 정책 변경이 금지 규칙을 어기면 빌드가 실패한다 — 회귀가 코드로 막히는 것이다. `Source-confirmed`

**부팅 스테이지를 나눈 이유.** 정책을 로드하기 전에는 시스템이 사실상 무방비다. 그래서 1단계에서 최소한(마운트·정책 로드·setenforce)만 하고, enforcing으로 올라간 뒤 2단계에서 나머지를 조립한다. "정책 없이 도는 창"을 최소화하는 설계다. `Inferred`

## 버전 차이와 한계

- **SELinux 전역 enforcing**은 Android 5.0(Lollipop)부터다. `Source-confirmed`
- **Treble(Android 8.0)**이 정책을 platform/vendor로 분리했다 — `plat_sepolicy`/`vendor_sepolicy`, `plat_property_contexts`/`vendor_property_contexts`로 나뉘고 버전 호환이 붙는다. `Source-confirmed` 컨텍스트 파일이 `/system/etc/selinux`·`/vendor/etc/selinux`로 이동한 정확한 도입 버전은 원문 재확인 필요.
- 실기기의 OEM `.te`·property 라벨은 이미지마다 다르다. Cuttlefish에서 본 도메인 집합이 특정 기기와 같다고 단정하지 말 것 — "이미지 확인 필요".
- 에뮬레이터 한계: SELinux·property는 관측되지만, 벤더 HAL 도메인이나 실제 하드웨어 신뢰뿌리(16장 HAL/VINTF, 24장 TEE)까지 그대로 재현하지는 않는다. 1단계 init의 세부는 microdroid·GKI 구성에 따라 달라진다(원문 재확인 필요).
- 과장 금지: 여기서 본 것은 **정책 구조의 관측**이지 우회가 아니다. `setprop` 거부는 취약점이 아니라 설계된 경계다.

## 정리

- init은 부팅 조립기이자 **시스템 속성의 단일 쓰기 지점**이다. 속성 쓰기는 전부 init을 거쳐 SELinux 검사를 받는다.
- SELinux는 파일·프로세스·속성·앱을 각각 다른 파일(`file_contexts`/`.te`/`property_contexts`/`seapp_contexts`)로 라벨링하고, `neverallow`를 빌드 시점에 검증한다.
- "root면 된다"는 절반의 진실이다 — uid 0이어도 도메인이 허용해야 한다. 관측할 때 DAC와 MAC을 반드시 함께 봐라.
- 에뮬레이터로 삼각형의 구조는 확인되지만, 하드웨어 신뢰뿌리와 OEM 정책은 실기기/원문으로 넘긴다.

**점검 질문** — (1) `getprop`은 검사가 없는데 `setprop`은 왜 init을 거쳐야 하는가? (2) 프로세스·파일·속성·앱의 SELinux 라벨은 각각 어느 파일에서 오는가? (3) root 프로세스가 어떤 동작에서 막힐 수 있는 이유는 무엇인가?

**참고** — [Android Init Language(README)](https://android.googlesource.com/platform/system/core/+/master/init/README.md) · [시스템 속성 추가](https://source.android.com/docs/core/architecture/configuration/add-system-properties) · [Security-Enhanced Linux in Android](https://source.android.com/docs/security/features/selinux) · [SELinux 구현](https://source.android.com/docs/security/features/selinux/implement)

*다음 글: [bionic·linker·ELF·JNI](/posts/android-expert-p2c20/).*
