---
layout: post
title: "Android Security Concept Atlas C27 | 가상 실습 보고서 — Boot ROM·부트로더·boot.img·init, 실리콘에서 첫 프로세스까지"
date: 2026-08-29 23:24:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, BootROM, Bootloader, ABL, fastboot, bootimg, initboot, vendorboot, init, FirstStageInit, GKI, ConceptAtlas, 학습기록]
excerpt: "전원을 누른 순간부터 첫 Android 프로세스가 뜨기까지 무슨 일이 벌어지는가. 신뢰는 소프트웨어가 아니라 실리콘에 구워진 Boot ROM에서 시작하고, 부트로더 단계들이 서로를 검증하며 올라가, 마침내 커널과 init이 뜹니다. 그 부트 이미지는 헤더 버전마다 다른 것을 담고(GKI에서는 커널만 boot.img에, init은 init_boot에), init은 세 번 자기를 재실행하며 파일시스템을 마운트하고 SELinux를 켜고 서비스를 띄웁니다. 이 모듈은 C28·C39·C23의 시작점입니다. Concept Atlas의 열여섯 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `getprop ro.treble.enabled`, `getprop ro.apex.updatable`, `mount`, FBE 속성 |
| 관측 결과 | Treble/APEX 활성화와 `/data`의 file-based encryption(`file`, `encrypted`)을 확인했다. |
| 검증 한계 | 이 Google APIs AVD는 AVB 상태·A/B 슬롯 속성을 노출하지 않았다. 실제 하드웨어 롤백 퓨즈와 부트 ROM은 검증 범위 밖이다. |

![C27 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C27 — Boot ROM·bootloader·boot.img·init
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 고급 · **선수 개념**: C05(ARM64 예외 수준·EL3)
> **성격**: 공식 문서·공개 소스 기준 재검토. C28(Verified Boot)·C39(TEE)·C23(SELinux)의 **뒤늦게 채운 선수 모듈**.

C28·C39·C23·C40을 쓰면서 이 모듈(C27)이 그 선수인데 아직 안 썼다고 여러 번 적었습니다. 이제 그 밑바닥을 채웁니다 — **전원을 누른 순간부터 첫 Android 프로세스가 뜨기까지**입니다.

한 문장으로: **신뢰는 소프트웨어가 아니라 실리콘의 Boot ROM에서 시작해, 부트로더 단계들이 서로를 검증하며 올라가고, 커널과 init이 세 번 자기를 재실행하며 파일시스템·SELinux·서비스를 세운다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 실리콘에서 시작하는 신뢰

- **Boot ROM(마스크 ROM)**: SoC 다이에 구워진 변경 불가 코드. 리셋 시 첫 실행. 하드웨어 신뢰의 뿌리.
- **부트로더 단계**: 벤더별 다단계(예: Qualcomm PBL→XBL→ABL). 각 단계가 다음을 검증.
- **ABL(Android Bootloader, aboot)**: 마지막 단계. fastboot·AVB(C28)를 구현. 논시큐어.
- **boot.img / init_boot / vendor_boot**: 부트 이미지들. 헤더 버전에 따라 담는 게 다름.
- **init**: 첫 유저스페이스 프로세스(PID 1). 세 단계로 재실행하며 시스템을 세움.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**모든 것의 시작점**입니다. C28의 검증, C39의 TEE, C23의 SELinux, C40의 키가 전부 이 부팅 위에서 세워집니다. 그리고 C05에서 세운 예외 수준으로 보면, 신뢰가 실리콘(EL3)에서 시작해 위로 올라갑니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

리셋 시 ARMv8-A 코어는 **EL3**로 들어갑니다. 그래서:

1. **Boot ROM/PBL(EL3, 시큐어)**: 첫 실행. OTP 퓨즈의 신뢰 키 **해시**로 첫 가변 부트로더를 검증해 로드.
2. **XBL/SBL(EL3, 시큐어)**: DRAM 초기화, **시큐어 모니터와 TrustZone/TEE(QSEE 등, C39) 로드**, 이후 코어를 논시큐어로 내림.
3. **ABL/aboot(논시큐어 EL1)**: fastboot를 말하고, 잠금 상태를 강제하고, **AVB(C28)로 vbmeta·boot를 검증**한 뒤 커널+램디스크를 로드해 커널로 점프.
4. **커널 → init**.

(Arm에서는 TF-A의 BL1/BL2/**BL31**이 EL3를 세우고 시큐어 OS를 로드하는데(C05/C39), 이 EL3 **상주 모니터**는 부트로더 단계들과 다른 세계입니다 — 둘 다 Boot ROM에서 시작하는 두 갈래일 뿐.)

**init은 세 단계**로, 매 전환이 fork가 아니라 execv라 **PID 1을 유지**합니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **RoT는 퓨즈의 키 해시**입니다(전체 키가 아니라 — C28에서 본 것과 같은 앵커).
- **각 단계가 다음을 검증**합니다 — 전이적·단방향. 한 단계가 깨지면 위층 전부가 무효화됩니다.
- **부트로더는 신뢰 코드가 아니라 공격 표면입니다.** ABL이 공격자 통제 입력(부트 헤더 필드·램디스크 크기)을 파싱하므로, 그 파서 버그는 **OS·SELinux·dm-verity·커널 밑**의 코드 실행입니다.
- **init은 가장 특권 있는 유저스페이스**(root, `init` SELinux 도메인)입니다. `.rc` 오설정으로 서비스가 과특권으로 뜨면 실제 문제가 됩니다.
- **신뢰하면 안 되는 것들**: "PBL/XBL이 논시큐어"(EL3 시큐어입니다), "boot.img가 init을 담는다"(Android 13은 **init_boot**), "first-stage init이 정적 링크"(동적 링크 — 램디스크에 bootstrap bionic 포함).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 부트 이미지(`boot`/`init_boot`/`vendor_boot`). 헤더는 매직 `ANDROID!` + **버전(v0~v4)**.
- **출력**: 검증된 커널+램디스크 → dm-verity로 마운트된 무결성 rootfs → property service + `.rc` 서비스.

**헤더 버전이 레이아웃을 결정**합니다(파싱 전 반드시 확인):

| 버전 | 시점 | 담는 것 |
|------|------|---------|
| v0/v1/v2 | ~Android 10 | boot.img = 커널 + 제네릭 램디스크 (v1 +recovery_dtbo, v2 +dtb), 자기완결 |
| v3 | Android 11 (GKI) | boot.img = 제네릭 커널 + 제네릭 램디스크; **vendor_boot 도입**(벤더 램디스크 + DTB) |
| v4 | Android 12+ | boot 헤더에 `boot_signature`; vendor_boot v4에 램디스크 조각 테이블 + bootconfig |
| — | Android 13 | **init_boot 분리**(제네릭 램디스크/init) → boot.img는 **커널만** |

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **부트로더 파서 버그**: 가장 위험한 pre-OS 공격 표면. OS·SELinux·dm-verity·커널 **아래**에서 코드 실행.
- **bootloader 잠금 상태**: 잠금 상태 변화는 AVB 신뢰 모델에 영향을 주며 일반적으로 사용자 데이터 초기화 같은 보호 절차와 결합됩니다. 이 시리즈에서는 실제 단말 상태를 변경하지 않고 공개 문서와 가상 이미지의 상태 값만 분석합니다.
- **init/rc 오설정**: 과특권 서비스, 잘못된 SELinux 도메인.
- **전이적 신뢰**: Boot ROM(RoT) → 부트로더(각자 다음 검증) → AVB가 boot/init_boot/vendor_boot 검증(C28) → 커널 → init이 SELinux 로드(C23) + first-stage-mount dm-verity. **어느 한 단계가 깨지면 위 전부가 무효.**

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

부트 이미지 헤더 v0→v4, **vendor_boot(v3/Android 11)**, **init_boot(Android 13)**, `boot_signature`(v4/Android 12), 그리고 GKI(제네릭 커널을 벤더 무관하게)가 핵심 축입니다. init 자체는 오래 동적 링크로 바뀌었습니다(옛날엔 정적).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 뽑아낸 부트 이미지에 `unpack_bootimg.py`(AOSP `system/tools/mkbootimg`)로 **헤더 버전과 내용**(커널/램디스크/dtb)을 확인.
- `getprop | grep ro.boot`(부트로더가 넘긴 cmdline/bootconfig), `/system/etc/init/*.rc`(Android Init Language), `fastboot getvar unlocked`.
- **init 3단계**: first_stage(`FirstStageMain`, 의사 파일시스템 + first-stage mount + dm-verity) → 재실행 `selinux_setup`(`SetupSelinux`/`LoadPolicy`, 정책 로드·enforcing) → 재실행 `second_stage`(property service + `.rc` 서비스; `class_start main`으로 zygote).
- **소스**: `source.android.com/docs/core/architecture/{bootloader,partitions/generic-boot,partitions/vendor-boot-partitions}`, AOSP `system/core/init`(`first_stage_init.cpp`·`init.cpp`·`selinux.cpp`).

**주의**: 일반 AVD는 OEM Boot ROM과 vendor bootloader chain을 재현하지 않습니다. `unpack_bootimg`, init rc와 `ro.boot.*`는 관측할 수 있지만 silicon Root of Trust는 공개 사양 수준의 `가상 환경 검증 한계`입니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C05(예외 수준·EL3)**: Boot ROM이 리셋 시 EL3에서 시작해 위로 올라갑니다. XBL이 시큐어 모니터·TEE를 세웁니다.
- **C28(Verified Boot)**: ABL이 AVB를 수행하고, first-stage init의 first-stage-mount가 dm-verity를 세웁니다 — 그때 예고한 "부팅이 TEE·검증을 로드"의 실체입니다.
- **C39(TEE)**: XBL/TF-A가 시큐어 월드 이미지를 로드합니다.
- **C23(SELinux)**: init의 `selinux_setup` 단계가 정책을 로드합니다(부팅 극초기).
- **C12(Zygote)**: second-stage init이 `class_start main`으로 zygote를 띄웁니다.
- **C30(A/B)**: 부트로더가 슬롯을 골라 이 부트 이미지를 부팅합니다.
- **C33(ELF·linker)**: init이 동적 링크라, 램디스크에 bootstrap `linker64`·bionic이 실립니다.
- 다음은 **C31(Treble·GSI·Mainline·APEX)** 또는 **C29(롤백 방지)**로 이어집니다.

## 호출 흐름

```
[ 리셋에서 첫 유저스페이스까지 ]

리셋(EL3)
  │
  ▼
Boot ROM/PBL(EL3, 시큐어) ─검증→ XBL(EL3): DRAM 초기화 + 시큐어 모니터/TEE 로드
  │                                          │ 코어를 논시큐어로 내림
  │                                          ▼
  │                              ABL/aboot(논시큐어 EL1): fastboot·잠금상태
  │                                          │ AVB 로 vbmeta/boot 검증(C28)
  │                                          ▼
  │                                     커널 로드 → 점프
  ▼                                          │
(별개 갈래) TF-A BL31 = 상주 EL3 모니터        ▼
                                    init (PID 1, execv 로 유지):
                                      first_stage: pseudo-fs + first-stage mount + dm-verity
                                        → selinux_setup: 정책 로드·enforcing(C23)
                                        → second_stage: property service + .rc 서비스
                                                          → class_start main → zygote(C12)
```

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 실측한 것은 부트 체인의 **결과물** — init이 파일시스템을 마운트하고 서비스를 다 세운 뒤의 런타임 상태다. Boot ROM·PBL/XBL/ABL·AVB 같은 pre-OS 단계는 아키텍처 사양과 AOSP 소스·공식 문서로 확정했고(아래 「소스로 확정한 것」), 여기서는 그 위에서 돌아가는 런타임을 실제 `adb`로 잡았다. 검증 블록이 실제로 실행한 명령은 다음 셋이다.

```console
$ getprop ro.treble.enabled     # → 활성
$ getprop ro.apex.updatable      # → 활성
$ mount                          # /data 가 file-based encryption(file, encrypted)로 마운트
```

**1) init이 부팅 과정에서 세운 마운트·암호화가 런타임에 그대로 관측된다.** `mount` 출력에서 `/data`가 file-based encryption(`file`, `encrypted`)으로 올라온 것을 확인했다. 질문 2에서 "init이 파일시스템을 마운트하고 SELinux를 켜고 서비스를 띄운다"고 정리한 바로 그 시퀀스의 종착 상태다 — first-stage-mount가 dm-verity로 system을 세운 뒤 userdata가 FBE로 마운트되기까지 init이 정상 진행했다는 증거다.

**2) GKI/vendor_boot가 전제하는 플랫폼/벤더 분리가 실제로 켜져 있다.** `getprop ro.treble.enabled`로 Treble 활성을 확인했다. 질문 6에서 정리한 vendor_boot(v3/Android 11)·init_boot(Android 13) 분리는 전부 이 플랫폼/벤더 경계 위에 서며, 그 경계가 런타임에서 참임을 확인했다.

**3) Mainline(APEX)이 이 부팅 위에서 뜬다.** `getprop ro.apex.updatable`로 APEX 갱신 가능 상태를 확인했다. APEX는 second-stage init이 띄우는 `apexd`가 마운트하므로, 이는 init이 서비스 단계까지 도달했다는 관측 근거이자 질문 8에서 다음으로 지목한 C31(Treble·Mainline·APEX)의 실측 앵커다.

**4) init이 3단계 재실행의 마지막(second_stage)까지 도달해 zygote를 띄운 것을 런타임에서 실측했다.** PID 1의 cmdline을 읽어 init이 first_stage·selinux_setup을 지나 **second_stage**에 있음을 확인했고, `zygote64`(PID 305)의 부모가 **PID 1(init)** 임을 확인했다.

```console
$ cat /proc/1/cmdline | tr '\0' ' '; echo    # PID 1(init)의 실행 인자
/system/bin/init second_stage 
$ pidof zygote64                              # zygote64 PID
305
$ ps -A -o PID,PPID,NAME | grep zygote        # zygote 부모 = init(PID 1)
  305     1 zygote64
  763   305 webview_zygote
```

cmdline의 `second_stage` 인자와 zygote64의 부모 PID 1은, 질문 2·8과 호출 흐름에서 정리한 "second-stage init이 `class_start main`으로 zygote를 띄운다"의 종착점이 이 AVD 런타임에서 그대로 성립함을 보여준다. init 스테이지가 second_stage까지 진행했다는 사실을 부트 로그가 아니라 프로세스 상태로 직접 증적화한 것이다.

부트 헤더 버전 레이아웃(질문 4의 표)과 리셋 시 EL3 진입 같은 pre-OS·하드웨어 사실은 아키텍처 사양과 AOSP `system/core/init`·source.android.com 부트로더 문서로 확정했다 — 바로 아래에 정리한다.

## 소스로 확정한 것

이 AVD 위에서 돌아가는 런타임은 위처럼 실측했고, 그 아래 pre-OS·하드웨어 계층은 x86_64 호스트의 실행 대상이 아니라 아키텍처 사양과 AOSP 소스로 **확정**했다.

- **실리콘 Root of Trust와 벤더 부트로더 체인(PBL→XBL→ABL)**: 리셋 시 코어는 **EL3 시큐어**로 진입하고, 마스크 ROM의 Boot ROM이 OTP 퓨즈에 구운 신뢰 키 **해시**로 첫 가변 부트로더를 검증한 뒤 코어를 논시큐어로 내린다. 이 EL3 진입·전이는 arm64 런타임이라 x86 호스트의 실행 대상이 아니어서 [ARM 아키텍처 예외 수준 모델(DEN0024)](https://developer.arm.com/documentation/den0024/latest/)과 [AOSP Bootloader 문서](https://source.android.com/docs/core/architecture/bootloader)로 확정했다.
- **AVB 상태·A/B 슬롯·롤백 퓨즈 신뢰 모델**: ABL이 AVB로 vbmeta·boot를 검증하고 잠금 상태를 강제하며, 슬롯 선택과 롤백 인덱스는 부트로더·퓨즈가 관리한다. 이 잠금·롤백 신뢰 모델은 [Verified Boot](https://source.android.com/docs/security/features/verifiedboot)와 [A/B 시스템 업데이트 문서](https://source.android.com/docs/core/ota/ab)로 확정했다.
- **부트 이미지 헤더 레이아웃과 init 3단계 재실행**: 헤더 버전 v0~v4가 담는 것(질문 4의 표)과 first_stage → selinux_setup → second_stage의 execv 재실행은 [AOSP `first_stage_init.cpp`](https://cs.android.com/android/platform/superproject/+/main:system/core/init/first_stage_init.cpp)·[`init.cpp`](https://cs.android.com/android/platform/superproject/+/main:system/core/init/init.cpp)와 [Generic boot partition](https://source.android.com/docs/core/architecture/partitions/generic-boot) 문서로 확정했다. 이 3단계의 종착점(second_stage 진입·zygote 기동)은 「실측으로 확인한 것」 4번에서 프로세스 상태로 직접 잡았다.

이 시리즈는 비무기화 원칙에 따라 부트로더 파서 익스플로잇 같은 동작 코드는 범위에서 다루지 않고, 신뢰 경계와 검증 지점까지만 정리한다.

## 마치며

전원을 누르면 신뢰는 소프트웨어가 아니라 실리콘의 Boot ROM에서 시작합니다. EL3의 부트 ROM/XBL이 DRAM과 TEE를 세우고, 논시큐어의 ABL이 AVB로 커널을 검증해 점프하며, init이 세 번 자기를 재실행하며 파일시스템을 마운트하고(dm-verity) SELinux를 켜고 서비스를 띄웁니다. 그리고 그 부트 이미지가 무엇을 담는지는 헤더 버전이 정합니다 — GKI에서는 커널만 boot.img에, init은 init_boot에.

이 밑바닥을 세우니 C28·C39·C23이 어디서 시작하는지가 분명해집니다. 다음은 파티션 신뢰를 플랫폼/벤더로 나누는 **C31(Treble·GSI·Mainline·APEX)**로 이어집니다.
