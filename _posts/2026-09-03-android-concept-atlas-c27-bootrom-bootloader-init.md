---
layout: post
title: "Android Security Concept Atlas C27 - Boot ROM·부트로더·boot.img·init, 실리콘에서 첫 프로세스까지"
date: 2026-09-03 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, BootROM, Bootloader, ABL, fastboot, bootimg, initboot, vendorboot, init, FirstStageInit, GKI, ConceptAtlas, 학습기록]
excerpt: "전원을 누른 순간부터 첫 Android 프로세스가 뜨기까지 무슨 일이 벌어지는가. 신뢰는 소프트웨어가 아니라 실리콘에 구워진 Boot ROM에서 시작하고, 부트로더 단계들이 서로를 검증하며 올라가, 마침내 커널과 init이 뜹니다. 그 부트 이미지는 헤더 버전마다 다른 것을 담고(GKI에서는 커널만 boot.img에, init은 init_boot에), init은 세 번 자기를 재실행하며 파일시스템을 마운트하고 SELinux를 켜고 서비스를 띄웁니다. 이 모듈은 C28·C39·C23의 시작점입니다. Concept Atlas의 열여섯 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C27 — Boot ROM·bootloader·boot.img·init
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 고급 · **선수 개념**: C05(ARM64 예외 수준·EL3)
> **성격**: 미학습 → 풀 작성. C28(Verified Boot)·C39(TEE)·C23(SELinux)의 **뒤늦게 채운 선수 모듈**.

C28·C39·C23·C40을 쓰면서 이 모듈(C27)이 그 선수인데 아직 안 썼다고 여러 번 적었습니다. 이제 그 밑바닥을 채웁니다 — **전원을 누른 순간부터 첫 Android 프로세스가 뜨기까지**입니다.

한 문장으로: **신뢰는 소프트웨어가 아니라 실리콘의 Boot ROM에서 시작해, 부트로더 단계들이 서로를 검증하며 올라가고, 커널과 init이 세 번 자기를 재실행하며 파일시스템·SELinux·서비스를 세운다.** 🔴 미학습이라 처음부터 세웁니다.

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
- **언락(`fastboot flashing unlock`)**: AVB 강제를 끄고, **강제 데이터 와이프**(userdata 삭제)를 인터록으로 겁니다 — 언락으로 기존 데이터를 조용히 노출하지 못하게.
- **init/rc 오설정**: 과특권 서비스, 잘못된 SELinux 도메인.
- **전이적 신뢰**: Boot ROM(RoT) → 부트로더(각자 다음 검증) → AVB가 boot/init_boot/vendor_boot 검증(C28) → 커널 → init이 SELinux 로드(C23) + first-stage-mount dm-verity. **어느 한 단계가 깨지면 위 전부가 무효.**

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

부트 이미지 헤더 v0→v4, **vendor_boot(v3/Android 11)**, **init_boot(Android 13)**, `boot_signature`(v4/Android 12), 그리고 GKI(제네릭 커널을 벤더 무관하게)가 핵심 축입니다. init 자체는 오래 동적 링크로 바뀌었습니다(옛날엔 정적).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 뽑아낸 부트 이미지에 `unpack_bootimg.py`(AOSP `system/tools/mkbootimg`)로 **헤더 버전과 내용**(커널/램디스크/dtb)을 확인.
- `getprop | grep ro.boot`(부트로더가 넘긴 cmdline/bootconfig), `/system/etc/init/*.rc`(Android Init Language), `fastboot getvar unlocked`.
- **init 3단계**: first_stage(`FirstStageMain`, 의사 파일시스템 + first-stage mount + dm-verity) → 재실행 `selinux_setup`(`SetupSelinux`/`LoadPolicy`, 정책 로드·enforcing) → 재실행 `second_stage`(property service + `.rc` 서비스; `class_start main`으로 zygote).
- **소스**: `source.android.com/docs/core/architecture/{bootloader,partitions/generic-boot,partitions/vendor-boot-partitions}`, AOSP `system/core/init`(`first_stage_init.cpp`·`init.cpp`·`selinux.cpp`).

**주의**: 에뮬레이터는 벤더 부트로더 단계가 없습니다 — `unpack_bootimg`·`.rc`·`ro.boot.*`는 보이지만 실제 부트 ROM 체인은 실기기에서만.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C05(예외 수준·EL3)**: Boot ROM이 리셋 시 EL3에서 시작해 위로 올라갑니다. XBL이 시큐어 모니터·TEE를 세웁니다.
- **C28(Verified Boot)**: ABL이 AVB를 수행하고, first-stage init의 first-stage-mount가 dm-verity를 세웁니다 — 그때 예고한 "부팅이 TEE·검증을 로드"의 실체입니다.
- **C39(TEE)**: XBL/TF-A가 시큐어 월드 이미지를 로드합니다.
- **C23(SELinux)**: init의 `selinux_setup` 단계가 정책을 로드합니다(부팅 극초기).
- **C12(Zygote)**: second-stage init이 `class_start main`으로 zygote를 띄웁니다.
- **C30(A/B)**: 부트로더가 슬롯을 골라 이 부트 이미지를 부팅합니다.
- **C33(ELF·linker)**: init이 동적 링크라, 램디스크에 bootstrap `linker64`·bionic이 실립니다.
- 다음은 **C31(Treble·GSI·Mainline·APEX)** 또는 **C29(롤백 방지)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "부트로더는 검증된 신뢰 코드라 공격 표면이 아니다."
2. "Qualcomm의 PBL/XBL은 논시큐어(normal world) 부트 코드다."
3. "boot.img는 항상 커널과 램디스크(init)를 함께 담는다."
4. "init은 정적 링크된 자기완결 바이너리다."
5. "init은 두 단계(first/second)이고 SELinux 정책은 second-stage에서 로드된다."

<details><summary>판정 기준(펼치기)</summary>

1. ABL은 공격자 통제 입력(부트 헤더·램디스크 크기)을 파싱하는 pre-OS 코드라, 그 파서 버그는 OS·SELinux·dm-verity 밑의 코드 실행입니다.
2. 리셋 시 코어는 EL3(시큐어)로 진입하고, PBL·XBL은 EL3에서 실행됩니다. **ABL만** 논시큐어(EL1)입니다.
3. Android 13(GKI)은 제네릭 램디스크/init을 **init_boot**로 분리해, boot.img는 **커널만** 담습니다.
4. 현대 init은 **동적 링크**입니다. /system 마운트 전에 돌기 위해 램디스크가 bootstrap bionic(`linker64`·libc 등)을 함께 싣습니다.
5. **세 단계**입니다: first_stage → **selinux_setup**(정책 로드·enforcing) → second_stage. 정책은 별도 재실행 단계에서 로드됩니다.
</details>

## 서술형 문제 3개

1. "신뢰가 실리콘에서 시작한다"는 것이 왜 중요한지(퓨즈의 키 해시·재플래시 불가)와, 그것이 부트로더 단계들의 전이적 검증(C28)으로 어떻게 이어지는지 서술하세요.
2. init이 세 단계로 자기를 재실행하며 각 단계가 하는 일(마운트/dm-verity·SELinux·property·서비스)을 순서대로 설명하고, PID 1이 유지되는 이유를 서술하세요.
3. 부트로더가 왜 "신뢰 코드"가 아니라 공격 표면인지, 그리고 언락이 왜 데이터 와이프를 강제하는지 서술하세요.

## 소스 탐색 과제

- 실기기(또는 팩토리 이미지)에서 `boot.img`/`init_boot`/`vendor_boot`를 뽑아 `unpack_bootimg.py`로 **헤더 버전**과 각 파티션 내용을 확인하고, 이 기기가 GKI 레이아웃(커널만 boot.img)인지 판정하세요.
- `getprop | grep ^\[ro.boot`로 부트로더가 넘긴 값들, `/system/etc/init/*.rc`로 Android Init Language 예시를 확인하세요.
- 왜 에뮬에서는 벤더 부트로더 체인(PBL/XBL/ABL)이 안 보이는지 근거와 함께 적으세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **부트 이미지 구조**: `unpack_bootimg` 출력으로 헤더 버전과 boot/init_boot/vendor_boot 내용을 실측.
2. **init 스테이지**: `/system/etc/init/*.rc`와 `logcat`/`dmesg`의 초기 부트 로그로 property service·서비스 시작을 캡처.
3. **잠금 상태**: `fastboot getvar unlocked`와 `ro.boot.verifiedbootstate`(C28)를 대조.
4. **연결 서술**: 이 부팅이 C28(AVB)·C23(SELinux)·C39(TEE)를 어떻게 세우는지 실측 근거로.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

전원을 누르면 신뢰는 소프트웨어가 아니라 실리콘의 Boot ROM에서 시작합니다. EL3의 부트 ROM/XBL이 DRAM과 TEE를 세우고, 논시큐어의 ABL이 AVB로 커널을 검증해 점프하며, init이 세 번 자기를 재실행하며 파일시스템을 마운트하고(dm-verity) SELinux를 켜고 서비스를 띄웁니다. 그리고 그 부트 이미지가 무엇을 담는지는 헤더 버전이 정합니다 — GKI에서는 커널만 boot.img에, init은 init_boot에.

이 밑바닥을 세우니 C28·C39·C23이 어디서 시작하는지가 분명해집니다. 다음은 파티션 신뢰를 플랫폼/벤더로 나누는 **C31(Treble·GSI·Mainline·APEX)**로 이어집니다.
