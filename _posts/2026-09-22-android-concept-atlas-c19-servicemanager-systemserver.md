---
layout: post
title: "Android Security Concept Atlas C19 | 가상 실습 보고서 — servicemanager·system_server, 서비스의 신뢰 앵커와 특권 호스트"
date: 2026-09-22 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, servicemanager, system_server, Binder, handle0, ContextManager, AMS, ConceptAtlas, 학습기록]
excerpt: "Binder는 핸들을 쥐어야 통신하는데, 아무 핸들도 없는 프로세스는 어떻게 첫 서비스를 찾을까요? handle 0 - servicemanager입니다. init이 zygote보다 먼저 띄우는 이 작은 데몬이 BINDER_SET_CONTEXT_MGR로 컨텍스트 매니저가 되어, 이름→binder 레지스트리 역할을 하죠(addService/getService). 그리고 그 위에서 조회되는 서비스 대부분 - AMS·PMS·WMS - 은 zygote가 fork한 하나의 특권 프로세스 system_server(UID 1000)에 삽니다. 그래서 system_server 코드실행 버그는 프레임워크 전체 장악급이지만, root는 아니고 SELinux 도메인에 갇혀 있죠. 누가 어떤 서비스를 등록/조회할 수 있는지는 service_contexts가 SELinux로 가릅니다. Tier 3 IPC의 신뢰 앵커 모듈입니다."
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

![C19 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-binder.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C19 — servicemanager·system_server
> **계층**: Tier 3 (IPC·프레임워크) · **난이도**: 고급 · **선수 개념**: C17(Binder), C12(zygote)
> **성격**: 보완 편.

C17에서 Binder가 **핸들**로 통신한다 했습니다. 그럼 아무 핸들도 없는 프로세스는 첫 서비스를 어떻게 찾을까요? 그 부트스트랩이 이 편의 절반(servicemanager)이고, 나머지 절반은 그 서비스 대부분이 사는 곳(system_server)입니다.

한 문장으로: **servicemanager는 handle 0의 이름→binder 레지스트리(신뢰 앵커)이고, 그 위 서비스 대부분은 zygote가 fork한 특권 프로세스 system_server(UID 1000)에 산다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **servicemanager**: Binder **컨텍스트 매니저**(handle 0). 이름→IBinder 레지스트리.
- **system_server**: zygote가 fork한 특권 호스트(UID 1000). AMS·PMS·WMS를 **한 프로세스**에.
- **service_contexts**: 누가 어떤 서비스를 add/find할지 **SELinux**로 게이트.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

Binder 네임스페이스의 **부트스트랩**(servicemanager) + 프레임워크의 **특권 호스트**(system_server)입니다. C17(핸들/트랜잭션)의 "이름으로 서비스 찾기" 뿌리이고, C21의 4대 컴포넌트가 결국 이 system_server의 AMS를 통해 연결됩니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **servicemanager**: `BINDER_SET_CONTEXT_MGR` ioctl로 `/dev/binder`의 **유일 컨텍스트 매니저**가 됨(드라이버가 핸들 0을 전용 `context_mgr_node`로 라우팅). 이름→IBinder 레지스트리: `addService(name, binder)` 발행 / `getService`·`checkService(name)` 조회. init이 **zygote·system_server보다 먼저** 띄우는 작은 네이티브 데몬.
- **system_server**: zygote가 `forkSystemServer`로 fork(**exec 없음**), **UID 1000**(AID_SYSTEM)·SELinux `system_server` 도메인. AMS·PMS·WMS·PowerManagerService… 대부분 프레임워크 서비스를 **한 프로세스**에 호스트, 각자 servicemanager에 등록.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **handle 0 = 신뢰 앵커**: 컨텍스트당 **한 번만** 설정되는 유일 컨텍스트 매니저라, 아무 핸들 없는 프로세스도 handle 0에 트랜잭션해 이름으로 서비스 핸들을 얻습니다.
- **이중 게이트**: 서비스 도달성은 (1) SELinux `service_contexts`(이 도메인이 find/add 가능?) + (2) 서비스 자체의 호출자 UID/PID 검사(C10/C22) 둘 다.
- **신뢰하면 안 되는 것들**:
  - **"system_server 침해 = root"** — **UID 1000**이고 SELinux `system_server` 도메인에 갇힙니다(커널/디바이스 접근 제한). 프레임워크 장악급이지 root/커널이 아님.
  - **"handle 0은 전역 하나"** — **컨텍스트별**입니다. `/dev/binder`·`/dev/vndbinder`·`/dev/hwbinder`가 **각자** 컨텍스트 매니저와 handle 0을 가짐(벤더/HAL 추적 시 혼동 금지).
  - **"getService = checkService"** — `checkService`는 **논블록**(없으면 즉시 null), `getService`는 역사적으로 블록/재시도.
  - **"아무나 서비스를 등록·조회한다"** — `service_contexts`가 이름→라벨을 고정하고 SELinux가 게이트합니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: `addService(name, binder)`(서비스 발행), `getService`/`checkService(name)`(클라이언트 조회).
- **출력**: 이름에 해당하는 binder 핸들. AMS 등 system_server의 서비스가 부팅 시 servicemanager에 등록되면, 앱은 `getService`로 핸들을 얻어 직접 트랜잭션(C17).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **system_server 침해 = 프레임워크 전체 장악**: system UID + 방대한 Binder-노출 서비스 표면 때문에 고가치 표적. 단 SELinux `system_server` 도메인이 상한(root/커널 아님) — 이 정확한 천장을 넘겨 말하면 오류.
- **servicemanager 신뢰 앵커 훼손**: 악성 프로세스가 컨텍스트 매니저가 되거나 서비스 이름을 사칭하면 조회를 MITM할 수 있으므로 — `BINDER_SET_CONTEXT_MGR`는 한 번만·SELinux 게이트, `service_contexts`가 이름→라벨 고정.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **servicemanager 구현**: A11에 **stable-AIDL(C++) 서비스**로 재작성(외부 계약=handle 0·add/get/check·service_contexts는 불변). 이전은 **raw C**가 `/dev/binder`를 직접 ioctl(libbinder/NDK 미링크).
- **hwservicemanager**(HIDL, `/dev/hwbinder`): HIDL→AIDL 이행으로 **폐기 진행**(신형은 아예 안 띄우기도).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `service list`(등록 서비스+인터페이스 = **프레임워크 Binder 공격면 지도**), `dumpsys -l`, `dumpsys <svc>`, `service check <name>`.
- `ls -l /dev/binder /dev/vndbinder /dev/hwbinder`, `/system/etc/selinux/*service_contexts`(이름→라벨), `ps -A | grep system_server`.
- **소스**: AOSP `frameworks/native/cmds/servicemanager/`, `frameworks/native/libs/binder/IServiceManager.cpp`, `frameworks/base/services/java/com/android/server/SystemServer.java`, 커널 `drivers/android/binder.c`(BINDER_SET_CONTEXT_MGR).

**주의**: servicemanager/system_server는 아키텍처 무관 → **에뮬레이터로 `service list`·`dumpsys -l`·`ps system_server` 실측 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C17(Binder)**: handle 0이 그 핸들/트랜잭션 모델의 부트스트랩.
- **C12(zygote)**: system_server가 `forkSystemServer`로 태어남.
- **C09(UID)**: system_server = UID 1000.
- **C23(SELinux)**: `service_contexts`가 add/find를 게이트.
- **C10/C22**: 서비스 자체가 호출자 UID를 검사.
- 다음은 이 AMS를 통해 앱 컴포넌트가 연결되는 **C21(4대 컴포넌트↔Binder)**로.

## 직접 그릴 수 있는 호출 흐름

```
[ servicemanager(handle 0)와 system_server ]

  init ──(zygote 전에)──▶ servicemanager
       BINDER_SET_CONTEXT_MGR → /dev/binder의 handle 0
       이름→IBinder 레지스트리 (add/get/check), service_contexts로 SELinux 게이트

  zygote ──forkSystemServer──▶ system_server (UID 1000, system_server 도메인)
       AMS · PMS · WMS · PowerMS … 를 한 프로세스에 호스트
       각 서비스 ──addService(name, binder)──▶ servicemanager 등록

  앱 ──getService("activity")──▶ servicemanager ──(핸들)──▶ 앱
      앱 ──Binder 트랜잭션──▶ AMS  (이후 직접 채널, C17)

  ⚠ 컨텍스트별 handle 0: /dev/binder · /dev/vndbinder · /dev/hwbinder 각각
```

## 오개념 판별 문제 5개

1. "system_server가 뚫리면 곧 root(커널)까지 장악한 것이다."
2. "handle 0은 시스템 전체에 하나뿐인 전역 컨텍스트 매니저다."
3. "`getService`와 `checkService`는 동작이 같다."
4. "아무 앱이나 원하는 서비스를 servicemanager에 등록하거나 조회할 수 있다."
5. "servicemanager는 프레임워크(자바) 서비스 중 하나라, system_server 안에서 돈다."

<details><summary>판정 기준(펼치기)</summary>

1. **UID 1000**이고 SELinux `system_server` 도메인에 갇힙니다 — 프레임워크 장악급이지 root/커널이 아닙니다.
2. **컨텍스트별**입니다. `/dev/binder`·`/dev/vndbinder`·`/dev/hwbinder`가 각자 handle 0을 가집니다.
3. `checkService`는 논블록(즉시 null), `getService`는 블록/재시도.
4. `service_contexts`가 이름→라벨을 고정하고 **SELinux가 add/find를 게이트**합니다.
5. servicemanager는 init이 zygote·system_server보다 **먼저** 띄우는 별도 네이티브 데몬입니다(그래야 서비스들이 등록할 대상이 존재).
</details>

## 실측으로 확인한 것

가상 실습 환경(codex-atlas-api33, Android 13/API 33, x86_64)에서 이 모듈의 핵심 불변식 두 개를 실제 명령으로 확인했다. 위 검증 화면(evidence-binder.png)이 그 근거다.

**1) handle 0은 전역 하나가 아니라 컨텍스트별이다.** Binder 디바이스 노드를 나열하면 셋이 각각 실재한다.

```console
$ ls -l /dev/{binder,hwbinder,vndbinder}
```

binderfs의 세 노드(`/dev/binder`·`/dev/hwbinder`·`/dev/vndbinder`)가 모두 존재한다는 것은, 각 컨텍스트가 자기 컨텍스트 매니저와 handle 0을 따로 가진다는 뜻이다 — 질문 3의 "컨텍스트별 handle 0" 불변식, 그리고 오개념 판별 2번("전역 하나뿐")의 반증이 디바이스 계층에서 그대로 확인된다.

**2) servicemanager는 이름→binder 레지스트리이고, 그 등록 목록이 곧 프레임워크 Binder 공격면이다.** `service list`는 handle 0에 트랜잭션해 등록된 서비스 이름과 인터페이스를 통째로 떠온다.

```console
$ service list
```

이 AVD에서 255개 서비스 등록을 확인했다(검증 블록 관측 결과). AMS·PMS·WMS를 포함한 이 목록의 항목 하나하나가 `addService`로 발행되어 `getService`로 조회 가능한 핸들이며(질문 4), 질문 7이 말한 "프레임워크 Binder 공격면 지도"의 실체가 바로 이 출력이다.

## 가상환경 검증 한계

정직하게, 이 세션이 새로 캡처한 실측은 위 두 명령(`ls -l /dev/{binder,hwbinder,vndbinder}`, `service list`)까지다. 나머지는 AOSP 소스로 근거는 확정했으나 이 AVD에서 새 출력으로 붙이지는 않았다.

- **system_server의 UID 1000·zygote 자식 관계는 이 세션에서 `ps`로 새로 캡처하지 않았다.** `forkSystemServer`(exec 없음)와 AID_SYSTEM은 SystemServer.java·zygote 소스에서 확정한 사실이며, 프로세스 목록 실측은 이 문서의 검증 범위 밖이었다.
- **`service_contexts`의 이름→라벨 매핑과 SELinux add/find 게이트는 정책 파일을 직접 떠서 대조하지 않았다.** 벤더 전용 HAL 트랜잭션이나 취약한 서비스 호출은 범용 AVD에 존재하지 않아(검증 블록 검증 한계) 공개 인터페이스·소스 분석으로 제한된다.
- **ARM64 전용 하드 격리(EL/PAC/BTI/MTE)와 하드웨어 TEE는 x86_64 에뮬레이터라 측정 대상이 아니다.** system_server가 갇히는 SELinux 도메인 상한은 정책·소스로 확인되지만, 커널/디바이스 접근을 실제로 시도해 막히는 것을 재현하지는 않았다.

관련 근거: [AOSP servicemanager](https://cs.android.com/android/platform/superproject/+/master:frameworks/native/cmds/servicemanager/) · [IServiceManager.cpp](https://cs.android.com/android/platform/superproject/+/master:frameworks/native/libs/binder/IServiceManager.cpp) · [SystemServer.java](https://cs.android.com/android/platform/superproject/+/master:frameworks/base/services/java/com/android/server/SystemServer.java) · [android.os.IBinder](https://developer.android.com/reference/android/os/IBinder)

## 마치며

Binder는 핸들을 쥐어야 통신하지만, 아무 핸들 없는 프로세스도 **handle 0**(servicemanager)에 트랜잭션해 이름으로 첫 서비스를 찾습니다 — init이 zygote보다 먼저 띄우는 이 데몬이 이름→binder 레지스트리이자 신뢰 앵커이고, `service_contexts`가 누가 등록/조회할지를 SELinux로 가릅니다. 그리고 그 위에서 조회되는 서비스 대부분(AMS·PMS·WMS)은 zygote가 fork한 하나의 특권 프로세스 **system_server**(UID 1000)에 삽니다 — 그래서 여기 코드실행 버그는 프레임워크 전체 장악급이지만 root/커널은 아니고 SELinux 도메인에 갇혀 있습니다. 다음은 이 AMS를 통해 앱의 4대 컴포넌트가 연결되고 exported 표면이 드러나는 **C21**로 이어집니다.
