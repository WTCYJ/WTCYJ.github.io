---
layout: post
title: "Cuttlefish·GSI·userdebug build"
date: 2026-11-30 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Cuttlefish, GSI, Treble, AOSP]
excerpt: "Cuttlefish는 흔히 '또 하나의 에뮬레이터'로 오해되지만 crosvm/KVM 위에서 도는 완전한 가상 기기다. 그리고 userdebug는 adb root를 열어줘도 SELinux는 여전히 enforcing이다 — root가 곧 정책 해제는 아니다."
---

앞 장들에서 system_server·PMS·Binder·HAL을 소스로 읽었다면, 이제 그걸 **직접 빌드해서 돌려볼 기기**가 필요하다. 그런데 여기서 조용히 갈리는 선택이 셋이다 — 어떤 가상 기기(Cuttlefish vs AVD)를, 어떤 이미지(순정 GSI vs 벤더 포함)로, 어떤 빌드 변형(user/userdebug/eng)으로 올리느냐. 이 셋을 뭉뚱그리면 "왜 adb root가 안 되지", "왜 이 GSI가 저 폰에서 부팅이 안 되지", "왜 SELinux가 여전히 막지" 같은 질문에서 몇 시간을 흘린다.

이 글은 AOSP를 소스에서 빌드해 Cuttlefish로 올리고, GSI가 아무 Treble 기기에서나 도는 이유와 빌드 변형이 관측 능력을 어떻게 가르는지를 AOSP 문서·소스와 함께 정리한 기록이다. 공격 실습이 아니라 "프레임워크 전체 스택을 내 손으로 세우고 계측하는 바닥"을 만드는 것이 목적이다.

> **한 줄 결론**: Cuttlefish와 GSI가 성립하는 근거는 하나 — **Treble의 system/vendor 분리**다. 순정 system 이미지가 임의 벤더 위에서 돌고(GSI), 하드웨어 없이 소프트웨어 벤더 구현으로 완전한 기기가 서는(Cuttlefish) 것이 모두 여기서 나온다. 그리고 userdebug는 root를 열되 신뢰 경계(ro.secure=1·SELinux enforcing)는 유지한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 셋이다. (1) Cuttlefish가 무엇이고 AVD/에뮬레이터와 어떻게 다른가(crosvm/KVM 위의 가상 기기, `launch_cvd`/`stop_cvd`), (2) GSI가 무엇이고 왜 임의 Treble 기기에서 도는가(Treble·VINTF·동적 파티션·DSU), (3) 빌드 변형 user/userdebug/eng가 각각 무엇을 열고 무엇을 막는가(`ro.build.type`·`ro.debuggable`·`ro.secure`). 공격 기법이 아니라 구조와 빌드 경로를 읽는다.

선수 지식으로 셋이 밑에 깔린다. Treble의 system/vendor 분할과 벤더 인터페이스(HAL이 안정 ABI로 분리된다는 것), SELinux 도메인·enforcing 모드(root라도 정책이 별개로 막는다는 것), 그리고 파티션 개념(system·vendor·boot이 따로 존재한다는 것)이다. Atlas C12(SELinux)와 앞 16장(HAL·VINTF·VTS)의 개념을 알고 있으면 충분하다.

전체 흐름에서 이 장의 위치는 App→Framework→Binder→system_server→HAL→Kernel 스택 **전부를 한 번에 세우는 발판**이다. 앞 장들이 각 계층을 따로 읽었다면, 여기서 그 계층들이 같이 부팅되는 하나의 이미지를 만든다. 다음 장의 init rc·property·SELinux 정책은 바로 이 부팅 과정 안에서 벌어지는 일이다.

## 핵심 개념 — 세 축: Cuttlefish, GSI, 빌드 변형

**Cuttlefish**는 AOSP가 제공하는 설정 가능한 **가상 기기(virtual device)**다. Android SDK의 에뮬레이터(qemu 기반 AVD)와 목적이 겹치지만 구현이 다르다 — Cuttlefish는 x86 호스트의 KVM 위에서 `crosvm`으로 게스트를 돌리며, 실기기에 가까운 충실도(guest HAL, WebRTC 디스플레이, 멀티 인스턴스, CI 친화)를 노린다. `Source-confirmed` 로컬뿐 아니라 GCE 같은 클라우드에서도 같은 방식으로 뜬다. 빌드 타깃은 `aosp_cf_x86_64_phone-userdebug` 형태이고, `launch_cvd`로 켜고 `stop_cvd`로 끈다. `Source-confirmed`

**GSI(Generic System Image)**는 순정 AOSP 코드로 빌드한 **system 파티션 이미지**다. Treble 준수 기기라면 벤더 파티션은 그대로 두고 이 순정 system만 얹어 부팅할 수 있다 — OEM의 프레임워크 커스터마이즈를 걷어낸 "레퍼런스 프레임워크"로 벤더 구현을 검증(CTS-on-GSI/VTS)하는 데 쓴다. `Source-confirmed` GSI는 `system.img` 하나로 배포되고, 실기기엔 `fastboot flash system`으로, 지우지 않고 시험 부팅하려면 DSU(Dynamic System Updates)로 얹는다.

**빌드 변형**은 `lunch <product>-<variant>`의 뒷부분이다. 셋이 있고, 관측 능력을 가른다.

| 변형 | 용도 | adb root | 대표 속성(개념) |
|--|--|--|--|
| `user` | 출하(production) | **불가**(adb 기본 off) | `ro.debuggable=0`, `ro.secure=1` |
| `userdebug` | 개발+디버깅 | **가능** | `ro.debuggable=1`, `ro.secure=1` |
| `eng` | 엔지니어링 | 가능(adbd 기본 root) | `ro.debuggable=1`, `ro.secure=0` |

`user`/`userdebug`/`eng`의 역할 구분(출하용·디버깅 가능·엔지니어링)은 빌드 문서에 명시돼 있다. `Source-confirmed` 다만 위 속성 열의 정확한 매핑은 AOSP 버전별로 다를 수 있어 빌드 문서 재확인을 권한다. `Inferred` 실무에서 load-bearing한 사실은 **root 가용성**이다 — 계측(후킹·리마운트·debugfs)이 필요하면 최소 userdebug여야 한다.

여기서 가장 흔한 착각 하나 — "userdebug면 root니까 뭐든 된다"는 오해다. userdebug에선 `adb root`가 열리고(이건 `ro.debuggable`/빌드 타입이 지배) **SELinux도 여전히 enforcing**이라, root라도 도메인 정책이 막는 접근은 그대로 막힌다 — 두 사실이 동시에 성립한다. 다만 SELinux enforcing 기본값은 `ro.secure`가 아니라 **빌드 타입 게이트**에서 나온다 — 커널 cmdline에 `androidboot.selinux=permissive`가 없고 빌드가 `user`가 아니면 enforcing이다. `ro.secure`가 지배하는 건 adbd가 부팅 시 기본 root로 뜨는지다. `eng`도 기본은 enforcing이며 permissive는 cmdline opt-in일 뿐이다. root ≠ 정책 해제. `Inferred`(SELinux 게이트 로직은 `system/core/init/selinux.cpp` 재확인 필요)

> **[그림 1]** `lunch` 메뉴에서 `aosp_cf_x86_64_phone-userdebug` 타깃을 고른 화면과, 빌드 후 `out/target/product/vsoc_x86_64/`에 `system.img`·`vendor.img`·`boot.img`가 생성된 디렉터리 목록을 나란히 캡처한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **공개 AOSP 소스와 로컬 Cuttlefish**로만 진행한다. 제3자 앱·실서비스·타인 소유 실기기 flashing은 없다. 실기기 GSI/DSU는 brick·데이터 손실 위험이 있어 기본 과정에서 제외하고, 필요하면 내 소유·언락 가능한 개발용 기기에서만 다룬다. Cuttlefish는 KVM 가상화가 켜진 리눅스 호스트를 전제로 한다(클라우드 VM 안에서 다시 돌릴 땐 중첩 가상화가 필요하다). `Source-confirmed`

## 실습 절차와 관측

### 가설
- **가설 A** — Cuttlefish를 `userdebug`로 빌드해 올리면 `adb root`가 성공하고, `getprop ro.build.type`은 `userdebug`, `getprop ro.secure`는 여전히 `1`, `getenforce`는 `Enforcing`이다. `Inferred`
- **가설 B** — 같은 트리를 `user`로 빌드하면 `adb root`가 거부되고(또는 adb 자체가 기본 비활성), `ro.debuggable=0`이 된다. `Inferred`

### 절차
1. AOSP 트리에서 `envsetup.sh`를 로드하고 `lunch`로 Cuttlefish userdebug 타깃을 고른다.
2. `m`으로 전체 이미지를 빌드한다(system/vendor/boot 등이 함께 나온다).
3. `launch_cvd`로 가상 기기를 부팅하고 `adb`로 붙는다.
4. `adb root` 성공 여부와 `getprop`/`getenforce`로 변형·신뢰 경계를 기록한다.
5. `stop_cvd`로 정리하고, 필요하면 `user` 변형으로 다시 빌드해 A/B를 대조한다.

```bash
# AOSP 트리에서 (repo sync 완료 가정)
source build/envsetup.sh
lunch aosp_cf_x86_64_phone-userdebug   # <product>-<variant>
m                                       # 전체 빌드

# Cuttlefish 부팅 / 종료
launch_cvd --daemon
adb wait-for-device
# ...관측...
stop_cvd
```

```bash
# 변형과 신뢰 경계 관측
adb root
getprop ro.build.type     # userdebug
getprop ro.debuggable     # 1
getprop ro.secure         # 1  (userdebug도 1 — root여도 정책은 산다)
getenforce                # Enforcing
```

> **[그림 2]** Cuttlefish에서 `adb root` 성공 직후 `getprop ro.build.type`(userdebug)·`ro.secure`(1)·`getenforce`(Enforcing)를 한 화면에서 실행한 대조 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체 — 타깃·버전에 따라 다르다):

```
# userdebug Cuttlefish
$ adb root
restarting adbd as root
$ getprop ro.build.type
userdebug
$ getprop ro.secure
1
$ getenforce
Enforcing
```

여기서 두 가지를 읽는다. (1) `adb root`가 성공했으니 계측(리마운트·debugfs·프레임워크 프로세스 관찰)의 전제가 열렸다. (2) 그럼에도 `ro.secure=1`·`Enforcing`이라 신뢰 경계는 살아 있다 — root로 프로세스 목록·로그는 봐도, SELinux가 막는 도메인 접근은 정책을 손대기 전엔 그대로 거부된다. `Reported`(수치·형식은 버전별 재확인 필요)

## Root Cause — 왜 이렇게 되는가

Cuttlefish가 하드웨어 없이 **완전한 기기**로 서고, GSI가 임의의 벤더 위에서 부팅되는 이유는 같은 뿌리다 — **Treble이 system과 vendor를 안정 인터페이스로 갈라놨기** 때문이다. Treble은 프레임워크(system)와 벤더 HAL(vendor)을 별도 파티션으로 나누고, 그 사이를 VINTF로 버전 관리되는 HIDL/AIDL HAL 경계로 고정한다. `Source-confirmed` 그래서 순정 system(GSI)은 자기가 어떤 벤더 위에 있는지 몰라도 그 안정 경계로만 대화하면 부팅되고, Cuttlefish는 그 벤더 쪽을 **소프트웨어 참조 구현(가상 HAL)**으로 통째로 채워 하드웨어를 대체한다. Treble이 없던 시절엔 system과 vendor가 얽혀 있어 이 둘 다 불가능했다.

빌드 변형이 관측 능력을 가르는 이유는 신뢰 경계를 어디에 두느냐의 문제다. `adbd`는 부팅 시 `ro.debuggable`/빌드 타입을 확인해 root 전환을 허용하거나 거부한다 — 그래서 user 빌드에선 "adbd cannot run as root in production builds"로 막힌다. `Source-confirmed` 반면 `ro.secure`는 adbd가 부팅 시 기본 root로 뜨는지를 지배하는 별개 스위치다 — adb 키 인증은 `ro.adb.secure`, SELinux enforcing은 빌드 타입 게이트(cmdline `androidboot.selinux`+빌드 타입)로 각각 다른 속성이다. userdebug는 root(`ro.debuggable=1`)를 열되 `ro.secure=1`을 유지해 adbd 기본을 비root로 둔다. root와 정책 해제가 분리돼 있는 것이 핵심이고, 그래서 "userdebug root"로도 SELinux가 계속 막는 것이다. `Inferred`(정확한 속성 지배 범위는 빌드 문서·`system/core` 재확인 필요)

정리하면, Treble의 분리가 GSI/Cuttlefish라는 이동성을 만들고, 빌드 변형이라는 별도 축이 그 위에서 "무엇을 관측할 수 있느냐"를 결정한다. 두 축은 독립이다.

## 버전 차이와 한계

- **Treble은 Android 8.0(2017)에서 도입**됐고, GSI 기반 검증은 그 이후 세대의 전제다 — 8.0 이전 기기엔 GSI를 얹는 개념 자체가 성립하지 않는다. `Source-confirmed`
- **동적 파티션(dynamic partitions)과 DSU는 Android 10에서 도입**됐다. DSU는 기존 system을 지우지 않고 GSI를 임시 슬롯으로 부팅해 시험할 수 있게 한다 — 실기기 flashing의 위험을 크게 줄이는 경로다. `Source-confirmed` 그 이전엔 `fastboot flash system`으로 파티션을 덮어야 했다.
- **GSI의 한계** — GSI는 벤더 HAL을 포함하지 않으므로(그건 기기의 vendor 파티션 몫), OEM 고유 하드웨어 기능 일부는 GSI 부팅에서 동작하지 않을 수 있다. 또 GSI는 잠긴 부트로더에선 얹을 수 없고, 배포되는 GSI도 user/userdebug 계열이라 목적에 맞는 변형을 골라야 한다. `Reported`(구체 제약은 대상 기기·GSI 릴리스별 원문 재확인 필요)
- **Cuttlefish의 한계** — 소프트웨어 참조 벤더 구현이라 실제 하드웨어 신뢰뿌리(TEE/StrongBox·RPMB)는 없다. 소프트웨어 KeyMint/TEE 구현을 띄울 수 있어도 하드웨어 기반 키 증명(attestation)의 실제 보증은 얻지 못한다 — 하드웨어 신뢰 관련 관측은 실기기로 넘긴다. `Inferred`(구성별 동작은 원문 재확인 필요) 반대로 SELinux·FBE·프레임워크 로직은 Cuttlefish로도 그대로 관측된다.

## 정리

- Cuttlefish는 crosvm/KVM 위의 **완전한 가상 기기**다 — AVD와 목적은 겹쳐도 소프트웨어 벤더 구현으로 실기기에 가까운 스택을 통째로 세운다.
- GSI가 임의 Treble 기기에서 도는 근거는 **Treble의 system/vendor 안정 인터페이스**이고, Cuttlefish도 같은 분리 위에 선다 — 두 기술의 뿌리는 하나다.
- 빌드 변형은 별개 축이다. 계측엔 최소 userdebug가 필요하지만, userdebug는 root를 열되 `ro.secure=1`·SELinux enforcing으로 **신뢰 경계를 유지**한다 — root가 곧 정책 해제는 아니다.

**점검 질문** — (1) GSI가 여러 다른 기기에서 부팅될 수 있게 하는 Treble의 구조적 근거는 무엇인가? (2) userdebug에서 `adb root`가 성공해도 SELinux가 여전히 막는 이유는(`ro.secure` vs `ro.debuggable`)? (3) Cuttlefish로는 관측되지만 실기기로 넘겨야 하는 것은 무엇이고 왜인가?

**참고** — [Cuttlefish 가상 기기](https://source.android.com/docs/setup/create/cuttlefish) · [Generic System Image(GSI)](https://source.android.com/docs/core/tests/vts/gsi) · [빌드 변형(user/userdebug/eng)](https://source.android.com/docs/setup/build/building) · [VINTF·벤더 인터페이스](https://source.android.com/docs/core/architecture/vintf) · [Dynamic System Updates(DSU)](https://source.android.com/docs/core/ota/dsu)

*다음 글: [init rc·property service·SELinux policy](/posts/android-expert-p2c19/).*
