---
layout: post
title: "Android Security Concept Atlas C12 | 가상 실습 보고서 — Zygote, 앱 프로세스가 태어나고 권한을 버리는 곳"
date: 2026-09-19 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Zygote, forkAndSpecialize, SpecializeCommon, seccomp, ASLR, USAP, ConceptAtlas, 학습기록]
excerpt: "모든 Android 앱 프로세스는 zygote를 fork해서 태어납니다 - 그것도 exec 없이. zygote는 부팅 때 ART 런타임과 프레임워크 클래스를 미리 로드해 둔 따뜻한 템플릿이라, 자식은 그 페이지들을 COW로 물려받아 빨리 뜨고 RAM을 아끼죠. 그런데 보안의 핵심은 specialization입니다: fork 직후 자식은 아직 root인 zygote 정체성이고, 거기서 UID를 앱 UID로 낮추고 SELinux 컨텍스트와 seccomp를 겁니다. 흔한 오해와 달리 seccomp는 UID를 낮추기 *전에* (아직 uid 0일 때) 설치되고 no_new_privs는 일부러 안 걸며, 특권의 마지막 순간은 fork가 아니라 그 UID 드롭 지점이에요. 그리고 모두가 한 zygote에서 갈라지니 ASLR 레이아웃을 공유하는 약점도 여기서 나옵니다. C04 fork 모델의 Android판, Tier 2 런타임 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `getprop ro.zygote`, `getprop dalvik.vm.usejit`, `ps` |
| 관측 결과 | `zygote64`와 JIT 활성 상태를 확인했다. 비특권 앱의 전체 프로세스 열람 제한도 함께 관측했다. |
| 검증 한계 | OAT/VDEX 생성 정책은 빌드와 프로파일 상태에 따라 달라지므로 이 한 번의 캡처를 모든 Android 버전에 일반화하지 않는다. |

![C12 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-runtime.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C12 — Zygote·앱 프로세스 생성
> **계층**: Tier 2 (Android Runtime) · **난이도**: 중급 · **선수 개념**: C04(fork/COW), C09(UID)
> **성격**: 보완 편.

C04에서 fork(COW)/exec의 차이를, C09에서 UID를 봤습니다. Android는 그 둘을 **한 곳**에서 씁니다 — zygote를 fork-without-exec로 갈라, 자식이 UID를 낮추며 샌드박스가 됩니다.

한 문장으로: **모든 앱 프로세스는 미리 로드된 zygote를 exec 없이 fork해 태어나고, 그 직후 specialization에서 UID·SELinux·seccomp를 적용하며 특권을 버린다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **zygote**: 부팅 때 ART+프레임워크를 preload한 **따뜻한 템플릿**. `init`→`app_process`→`ZygoteInit`.
- **fork-without-exec**: 자식이 preload 페이지를 **COW 상속**(빠른 시작+RAM 공유).
- **specialization**: fork 후 자식이 UID 드롭·SELinux·seccomp 적용(C09·C23·C04).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**C04 fork 모델의 Android판**이자 앱 프로세스 생성의 유일 경로입니다. C09(UID)·C23(SELinux)·C04(seccomp)가 전부 여기 한 곳(specialization)에서 적용되고, C13의 부트 이미지를 zygote가 맵합니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **생성**: `init`이 부팅 초기에 `/system/bin/app_process` 실행 → `ZygoteInit.main()`. **preload**: ART 런타임 + 프레임워크 클래스(preloaded-classes) + 리소스 + 네이티브 라이브러리.
- **spawn**: `system_server`(AMS→`ZygoteProcess`)가 **UNIX 소켓**(`/dev/socket/zygote`)으로 인자(uid/gids/seinfo/nice-name)를 보내면, zygote가 `forkAndSpecialize`로 fork(**exec 없음**). system_server는 `forkSystemServer`로.
- **두 zygote**: 64/32비트 기기는 `zygote64`(주, `/dev/socket/zygote`)+32비트 `zygote`(`/dev/socket/zygote_secondary`), 각 ABI로 preload.
- zygote는 **root**로 돌아 자식이 임의 UID로 드롭할 수 있게.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **specialization = 보안 전이**: fork 직후 자식은 아직 zygote 정체성(root+caps). `SpecializeCommon`이 특권을 버립니다. **핵심은 순서**(아래).
- **신뢰하면 안 되는 것들**:
  - **"zygote는 fork+exec로 앱을 띄운다"** — **exec 없음**. exec하면 preload 페이지가 다 버려집니다.
  - **"seccomp는 UID를 낮춘 뒤 설치된다"** — 반대입니다. seccomp는 **UID 드롭 *전에*, 아직 uid 0·`CAP_SYS_ADMIN` 보유 상태**에서 설치되고, `PR_SET_NO_NEW_PRIVS`는 **일부러 안 겁니다**(SELinux 도메인 전이가 깨지므로, b/71859146).
  - **"fork가 특권의 경계"** — 아닙니다. 자식은 `SpecializeCommon` 전반부 동안 root이고, **특권의 마지막 순간은 그 안의 `setresuid`+`SetCapabilities`+`selinux_android_setcontext` 시퀀스**입니다.
  - **"공유 ASLR은 전세계에서 동일"** — **같은 기기·같은 부팅·같은 ABI zygote 내에서만** 동일합니다. 기기·부팅마다 zygote가 독립 랜덤화되고, 전세계로 불변인 건 **상대 오프셋**뿐.
  - **"USAP = app-zygote"** — 별개입니다. USAP는 미특화 프로세스 **풀**, app-zygote는 isolated 서비스용 **앱별 zygote**.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 소켓으로 온 spawn 인자(uid, gids, seinfo, nice-name, mount-mode…).
- **동작(SpecializeCommon 개략 순서)**: DropCapabilitiesBoundingSet(초기) → 마운트/에뮬레이트 저장소(초기, **uid 0**) → 보조 gids·setresgid → **seccomp 설치(uid 0)** → **setresuid(앱 UID)** → SetCapabilities → `selinux_android_setcontext` → 프로세스 이름.
- **출력**: 탈특권 앱 샌드박스가 관리 코드로 재진입(앱=`ActivityThread.main`, system_server=`SystemServer.main`).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **zygote 침해 = 모든 앱**: zygote의 특권 + 모든 앱이 공유하는 레이아웃 때문에, 여기 버그는 전 앱에 파급됩니다.
- **드롭 전 실행/드롭 실패**: root인 전반부에서 도는 버그나 UID 드롭 누락은 치명적(specialization 순서가 보안의 핵심인 이유).
- **공유 ASLR 약점**: 모두 한 zygote에서 갈라져 **같은 부팅·ABI 내 형제 앱이 같은 베이스 주소**를 씀 → 한 앱(또는 zygote)의 주소 누출이 다른 앱 레이아웃을 근사(익스플로잇 신뢰성에 유리). fork는 재랜덤화하지 않음.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **seccomp 필터(specialization)**: A8.0(Oreo) 추가. 이전엔 uid/gid/SELinux/caps만.
- **USAP**(구 'blastula') 풀: A10(Q).
- **app-zygote**(isolated 서비스용): A10+. `<service android:isolatedProcess="true" android:useAppZygote="true">` + `<application android:zygotePreloadName="…ZygotePreload">`.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ps -A -o PID,PPID,NAME`(앱들이 `zygote`/`zygote64`를 부모로), `/proc/<pid>/smaps`(zygote와 COW-공유된 클린 영역), `/system/etc/preloaded-classes`.
- **소스**: `frameworks/base/core/java/com/android/internal/os/{ZygoteInit,Zygote,ZygoteConnection}.java`, `android/os/ZygoteProcess.java`, **`frameworks/base/core/jni/com_android_internal_os_Zygote.cpp`(SpecializeCommon)**, `init.zygote64_32.rc`.

**주의**: zygote/COW는 아키텍처 무관 → **에뮬레이터로 `ps`·`smaps` 실측 가능**(단 실제 UID 드롭·seccomp는 앱 컨텍스트/디버그 필요).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C04(fork/COW)**: zygote가 그 fork-without-exec + COW의 실체.
- **C09(UID)**: specialization의 `setresuid`가 `uid=userId×100000+appId`를 적용.
- **C23(SELinux)**: `selinux_android_setcontext`가 seinfo 기반 도메인을 설정.
- **C05(EL0)**: 탈특권 자식은 EL0 앱.
- **C13(ART)**: 부트 이미지(boot.art)를 zygote가 맵해 앱이 상속.
- 다음은 이 실행 위에서 클래스를 로드하는 **C14** 또는 JIT/AOT 분석차 **C16**로.

## 호출 흐름

```
[ zygote: 태어나고 권한을 버리는 순서 ]

  init → app_process → ZygoteInit.main
       preload(ART + 프레임워크 클래스 + 리소스 + 네이티브)
       listen /dev/socket/zygote

  system_server(AMS→ZygoteProcess) ──소켓 인자(uid,gids,seinfo)──▶ zygote
       fork()  (exec 없음! preload 페이지 COW 상속)
          │  자식은 아직 root(zygote 정체성)
          ▼  SpecializeCommon:
       DropCapBoundingSet → 마운트/저장소(uid 0) → gids/setresgid
          → seccomp 설치(uid 0, no_new_privs 안 씀)   ← UID 드롭 전!
          → setresuid(앱 UID) → SetCapabilities
          → selinux_android_setcontext → 이름   ← 특권의 마지막 순간
          ▼
       ActivityThread.main  (탈특권 앱, EL0)

  ⚠ 모든 앱이 한 zygote에서 → 같은 부팅·ABI 내 ASLR 레이아웃 공유
```

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 이 모듈의 핵심 사실을 실제 명령으로 확인했다. 아키텍처 무관 속성(zygote 존재·프로세스 격리)은 AVD로 실측했고, 앱 디버그 컨텍스트가 필요한 specialization 내부는 AOSP 소스로 확정했다.

**1) 주 zygote는 64비트다.** `ro.zygote`가 `zygote64`를 반환해, 질문 2의 "64비트 기기는 `zygote64`가 주(`/dev/socket/zygote`)"를 이 AVD에서 확인했다.

```console
$ adb shell getprop ro.zygote
zygote64
```

**2) 비특권 앱은 전체 프로세스 트리를 열람하지 못한다.** 앱 컨텍스트의 `ps`가 전체 프로세스 목록을 돌려주지 않았다 — 이 열람 제한 자체가 질문 3의 신뢰 경계(앱은 자기 샌드박스 밖을 못 본다)가 프로세스 수준에서 관측된 결과다. 그래서 "앱→zygote 부모 관계"와 형제 앱의 `smaps` COW 대조는 이 비특권 세션에서 새로 캡처하지 못했고(→ 한계), 부모 관계·COW 상속은 소스·문서 근거로 서술한다.

**3) 런타임 preload의 전제인 JIT가 활성이다.** `dalvik.vm.usejit`가 활성으로, zygote가 부팅 때 맵해 두는 ART 런타임(C13, boot 이미지)이 JIT를 켠 상태로 자식에 COW 상속됨을 확인했다.

```console
$ adb shell getprop dalvik.vm.usejit
true
```

**4) specialization의 드롭 순서는 소스로 확정했다.** 이 세션에서 동적으로 트레이스하지는 못했지만(→ 한계), 질문 3~4의 핵심 주장 — seccomp가 `setresuid`보다 앞(아직 uid 0)에서 설치되고 `PR_SET_NO_NEW_PRIVS`는 일부러 걸지 않는다 — 은 `com_android_internal_os_Zygote.cpp`의 `SpecializeCommon`에서 그 호출 순서가 그대로 확인된다.

## 가상환경 검증 한계

정직하게, 이 문서가 이 AVD 세션에서 새로 캡처한 실측은 (1)~(3)까지이고, specialization 내부 동작은 소스로만 확정했다.

- **SpecializeCommon의 드롭 시퀀스를 런타임으로 트레이스하지 못했다.** seccomp 설치→`setresuid`→`SetCapabilities`→`selinux_android_setcontext` 순서는 AOSP 소스에서만 확인했다. 실제 앱 spawn 중에 이 호출들을 실측하려면 앱 컨텍스트 디버그 권한이 필요해 이 비특권 세션에서는 관측하지 못했다.
- **COW 공유·부모 관계의 프로세스 실측은 확보하지 못했다.** 비특권 앱의 `ps`가 전체 목록을 반환하지 않아 앱→zygote 부모 트리와 두 앱의 `/proc/<pid>/smaps` 공유 클린 영역 대조를 새로 캡처하지 못했다. 근거는 확정했으나 화면은 남기지 못했다.
- **ARM64 전용 완화는 x86_64 AVD라 측정 대상이 아니다.** 공유 ASLR 약점(질문 5)과 얽히는 PAC·BTI·MTE 같은 ARM64 EL 계층 방어는 이 x86_64 이미지에 존재하지 않아, C05/C37과의 연결은 개념 서술로만 다뤘다.

관련 근거: [SpecializeCommon (com_android_internal_os_Zygote.cpp)](https://cs.android.com/android/platform/superproject/+/master:frameworks/base/core/jni/com_android_internal_os_Zygote.cpp) · [ZygoteInit.java](https://cs.android.com/android/platform/superproject/+/master:frameworks/base/core/java/com/android/internal/os/ZygoteInit.java) · [seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html) · [Android App Sandbox](https://source.android.com/docs/security/app-sandbox)

## 마치며

모든 Android 앱 프로세스는 부팅 때 ART와 프레임워크를 미리 로드한 zygote를 **exec 없이 fork**해 태어납니다 — 그래서 빨리 뜨고 프레임워크 메모리를 COW로 공유하죠. 보안의 핵심은 그 직후 `SpecializeCommon`입니다: 자식은 아직 root이고, 거기서 (아직 uid 0일 때) seccomp를 걸고 마운트를 세운 뒤 `setresuid`로 앱 UID로 낮추며 `selinux_android_setcontext`로 도메인을 설정합니다 — 흔한 오해와 달리 seccomp는 UID 드롭 *전*이고 `no_new_privs`는 일부러 안 걸며, 특권의 마지막 순간은 fork가 아니라 그 UID 드롭 지점입니다. 그리고 모두가 한 zygote에서 갈라지므로 같은 부팅·ABI 안에서 ASLR 레이아웃을 공유하는 약점도 여기서 나옵니다. 다음은 이 실행 위에서 클래스를 로드하는 **C14** 또는 JIT/AOT 분석차 **C16**로 이어집니다.
