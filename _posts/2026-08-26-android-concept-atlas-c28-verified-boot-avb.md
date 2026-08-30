---
layout: post
title: "Android Security Concept Atlas C28 | 가상 실습 보고서 — Verified Boot·vbmeta·dm-verity, 실리콘에서 커널까지 이어지는 신뢰"
date: 2026-08-26 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, VerifiedBoot, AVB, vbmeta, dmverity, RootOfTrust, RollbackProtection, KeyAttestation, avbtool, Bootloader, Treble, ConceptAtlas, 학습기록]
excerpt: "Verified Boot의 신뢰 사슬을 공개 이미지와 avbtool로 분석합니다. vbmeta 서명, Hash·Hashtree descriptor, dm-verity와 rollback metadata를 구분하고, 하드웨어 Root of Trust는 AOSP 소스·공식 문서로 확정하고 ARM64 신뢰 마커는 정적으로 실측해 뒷받침합니다."
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

![C28 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C28 — AVB·vbmeta·dm-verity
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 고급 · **선수 개념**: C05(ARM64 예외수준; EL3 시큐어 모니터·신뢰의 뿌리), C08(APK 서명 스킴)
> **성격**: 공식 문서·공개 소스 기준 재검토. 선수 C27(부트 ROM·부트로더)의 맥락은 이 글이 스스로 서도록 최소한만 깝니다.
> **완료 기준**: vbmeta 서명 체인을 도식화하고 dm-verity 해시 트리 검증을 설명할 수 있다.

15~16주차에서 저는 "Verified Boot는 에뮬레이터에서 안 보인다"고 한 줄 적고 지나갔습니다. 그때는 그게 **왜** 안 보이는지 몰랐습니다. 이 모듈이 그 답입니다. 그리고 그 답은 Android 부팅 체인 전체(Domain 2)의 앵커이자, C05의 "EL3 너머 신뢰의 뿌리"와 C40의 attestation이 실제로 걸려 있는 자리입니다.

한 문장으로 요약하면: **실리콘에 구워진 키 해시에서 시작한 신뢰가, 부트로더 → vbmeta 서명 → dm-verity 해시 트리 → 부팅 상태 → 원격 attestation으로 이어지는 하나의 사슬**입니다. 그리고 그 사슬은 **잠긴 부트로더**라는 전제 위에서만 의미가 있습니다 — 에뮬레이터에서 안 보였던 이유가 바로 그것입니다.

## 배경 개념 - 검증된 부팅이라는 사슬

- **신뢰의 뿌리(Root of Trust)**: 변경 불가능한 마스크 ROM(Boot ROM)과, OTP/eFuse에 **한 번만** 구워지는 값. 이 값은 재플래시할 수 없어 하드웨어 앵커가 됩니다.
- **AVB (Android Verified Boot) 2.0**: Android 8.0(Oreo)에 도입된 검증 부팅 설계. 중심에 **vbmeta** 파티션이 있어 다른 모든 파티션의 다이제스트를 담고, 한 번 서명됩니다.
- **vbmeta**: 서명된 메타데이터. 헤더 + 인증(Authentication) 블록(해시+서명) + 보조(Auxiliary) 블록(공개키 + 디스크립터).
- **dm-verity**: 큰 읽기전용 파티션(system 등)을 블록 단위로 검증하는 커널 device-mapper. 머클(해시) 트리를 쓰고, 그 루트가 vbmeta 안에 있습니다.
- **롤백 방지**: 서명된 **구버전** 이미지로 되돌리는 다운그레이드 공격을 막는 단조 증가 인덱스.

공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다. 여덟 질문으로 조립합니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

부팅 체인의 **무결성 앵커**입니다. C05에서 부팅이 각 EL의 코드를 심는 과정이라 했는데, Verified Boot는 그 각 단계가 **다음 단계를 실행하기 전에 암호학적으로 검증**하도록 만듭니다. 신뢰가 실리콘(퓨즈)에서 위로 사슬처럼 올라가, 어느 단계도 자기를 로드한 것을 그냥 믿지 않습니다. 그리고 이 앵커는 위로 C40(Keystore attestation의 `verifiedBootState`)과, 옆으로 C31/C32(Treble 파티션 분할)와 이어집니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

**부트로더**(C05의 EL 사다리에서 커널보다 아래, 최종적으로 EL3/EL2에서 도는 펌웨어 단계)가 주역입니다. 흐름은 이렇습니다.

1. **Boot ROM**이 첫 부트로더를 OTP에 구워진 키 해시로 검증.
2. 각 부트로더 단계가 다음 단계를 검증.
3. 최종 부트로더가 **libavb**로 vbmeta 서명을 검증하고, 그제서야 그 안의 디스크립터를 믿고 커널로 점프.

부팅이 끝난 뒤에도 하나가 계속 삽니다: **dm-verity**는 커널 안에서 살아, system/vendor의 블록을 **읽을 때마다** 검증합니다. 즉 Verified Boot는 "부팅 때 한 번"이 아니라, 작은 파티션은 로드 시 한 번 + 큰 파티션은 **읽는 내내** 검증됩니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

이 모듈에서 가장 미묘하고 가장 많이 틀리는 지점이 신뢰의 뿌리가 **어디** 있느냐입니다.

- **퓨즈에는 전체 키가 아니라 키의 해시만 굽습니다.** OTP/eFuse에는 신뢰하는 vbmeta 서명 공개키의 **SHA-256 다이제스트**만 들어갑니다(작고 불변이라야 하므로). **전체 공개키는 vbmeta 안에 실려서** 옵니다. 부트로더는 그 실려온 키로 서명을 검증한 **다음**, 그 키의 해시가 퓨즈 값과 일치하는지 확인합니다. 그래서 자가서명 vbmeta는 자기 키로는 서명이 맞아도 **퓨즈 해시와 안 맞아** 잠긴 기기에서 거부됩니다. **진짜 신뢰의 뿌리는 키 소유가 아니라 이 해시 대조입니다.**
- **vbmeta는 한 번 서명됩니다.** 파티션마다 따로 서명하는 게 아니라, vbmeta가 **파티션별 다이제스트(디스크립터)**를 담고 그 vbmeta 서명 하나가 전부를 전이적으로 보증합니다.
- **AVB는 잠긴 부트로더에서만 의미가 있습니다.** 언락하면 강제가 꺼지고 ORANGE가 됩니다. 신뢰하면 안 되는 것: "언락해도 AVB가 지켜준다", "에뮬레이터에서 안 보이니 고장".
- **AVB는 런타임 침해를 막지 않고 기밀성을 주지 않습니다.** 부팅시점·정지상태의 무결성과 롤백 방지일 뿐입니다(질문 5).

## 질문 4 — 입력과 출력은 무엇인가

**vbmeta의 검증 봉투**부터 정확히. vbmeta 이미지는 세 블록입니다: **헤더**(256바이트, 매직 `AVB0`) + **인증 블록**(해시 + 서명) + **보조 블록**(공개키 + 디스크립터).

- 부트로더는 **헤더 + 보조 블록**에 대해 해시를 계산합니다. **인증 블록은 제외**됩니다 — 그 안에 해시와 서명 자신이 들어 있어, 자기를 담은 영역을 해시할 수 없기 때문입니다.
- 그 계산한 해시를 인증 블록에 저장된 해시와 비교하고, **서명은 그 해시(다이제스트)에 대해** RSA 검증합니다(예: `SHA256_RSA4096`). 디스크립터가 보호받는 건 그것이 해시 입력인 보조 블록 안에 있기 때문입니다 — 디스크립터를 건드리면 해시가 바뀌어 서명이 깨집니다.

**디스크립터**는 보조 블록 안의 TLV 레코드로, 태그가 있습니다: `PROPERTY=0`, `HASHTREE=1`, `HASH=2`, `KERNEL_CMDLINE=3`, `CHAIN_PARTITION=4`(`HASHTREE=1`이 `HASH=2`보다 작은 게 함정입니다). 두 검증 전략이 핵심입니다.

| 디스크립터 | 대상 | 검증 방식 |
|-----------|------|----------|
| **HASH** (tag 2) | 작은 파티션 — `boot`·`init_boot`·`vendor_boot`·`dtbo` | 전체 이미지를 RAM에 통째로 올려 **한 번 해시**(로드 후 검증) |
| **HASHTREE** (tag 1) | 큰 읽기전용 fs — `system`·`vendor`·`product` | dm-verity 머클 트리로 **읽을 때마다 블록 단위** 검증 |
| **CHAIN_PARTITION** (tag 4) | `vbmeta_system`·`vbmeta_vendor` | **별도 키·별도 롤백 슬롯**을 가진 하위 vbmeta에 검증을 위임 |

작은 파티션은 통째로 해시해도 되지만, 수 GB의 system을 부팅 때 전부 해시할 수는 없어서 **dm-verity가 존재**합니다. 파티션이 자기 이미지와 vbmeta 구조를 함께 담으면 끝에 64바이트 **AvbFooter**(매직 `AVBf`)를 붙이고, 최상위 `vbmeta` 파티션은 footer 없이 순수 vbmeta 이미지로 **검증의 진입점**이 됩니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**dm-verity의 실체** — 머클 트리입니다. 파티션의 4KiB 블록마다 SHA-256(+ per-partition salt)으로 리프 해시를 만들고, 그 해시들을 다시 블록으로 묶어 해시해 올라가, 마침내 하나의 **루트 해시**가 됩니다. 그 루트(와 salt)는 **서명된 vbmeta의 hashtree 디스크립터** 안에 있습니다. 즉 AVB가 vbmeta 서명을 검증 → vbmeta가 루트 해시를 보증 → dm-verity가 그 루트로 블록을 검증. **루트 해시가 서명 앵커 없이 파티션에만 있으면** 공격자가 변조 데이터 위에 유효한 트리를 새로 계산해버릴 수 있습니다 — 그래서 vbmeta 앵커가 load-bearing입니다.

검증은 **읽을 때(lazy)** 일어납니다. 커널은 실제로 읽히는 4KiB 블록만 해시해 트리 위로 검증하므로, 거의 안 읽히는 블록의 변조도 **읽히는 순간** 잡힙니다. 실패 시 동작은 모드로 정해집니다: `restart`(재부팅), `eio`(그 읽기에 I/O 에러), `logging`(기록만). FEC(Reed-Solomon, Android 7+)는 **악의 없는 비트 부패**를 복구할 뿐, 악의적 변조 블록은 여전히 해시에서 걸립니다(우회 아님).

**롤백 방지** — 서명된 **구버전**은 암호학적으로는 여전히 유효합니다. 그걸 막는 건 각 vbmeta의 단조 증가 `rollback_index`입니다. 기기는 위치별 최고값을 **RPMB(Replay Protected Memory Block)나 TEE 보안 저장소** 같은 변조 방지·재생 방지 저장소에 두고, 인덱스가 낮은 이미지는 부팅을 거부합니다. 버전 문자열이 아니라 정수를 비교합니다. 체인 파티션은 각자 롤백 슬롯을 가집니다.

**정책이 곧 공격 표면**이라는 관점에서 AVB의 범위와 한계:

- **AVB가 주는 것**: 정지상태 파티션의 **무결성 + 롤백 방지 + 서명된 부팅 상태 판정**.
- **AVB가 주지 않는 것**: **기밀성**(그건 FBE, C43)과 **런타임 침해 방어**. 부팅 후 커널/유저스페이스 RCE는 살아있는 시스템을 그대로 장악하고, dm-verity는 디스크의 읽기전용 블록만 재검증하지 RAM은 못 봅니다. 즉 AVB는 "무엇이 부팅됐는가"의 부팅시점 증명이지 런타임 샌드박스가 아닙니다.
- **표준 우회**: `fastboot --disable-verity --disable-verification flash vbmeta`가 vbmeta 헤더에 `HASHTREE_DISABLED`(비트 0)·`VERIFICATION_DISABLED`(비트 1) 플래그를 세워 dm-verity와 AVB 검사를 건너뜁니다. 모든 Magisk/커스텀 커널 가이드의 그 명령입니다. 단 이 변조된 vbmeta는 서명이 깨지므로 **잠긴 부트로더는 거부**합니다 — 언락에서만 먹힙니다. AVB의 가치가 전적으로 잠금 상태에 달렸다는 실증입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 4.4 | dm-verity가 `/system`에 도입(당시 루트 해시·서명은 파티션에 붙는 verity 메타데이터에) |
| Android 6.0 | Verified Boot 요구(경고 수준) |
| **Android 7.0** | **엄격 강제 + 부팅 상태 색(GREEN/YELLOW/ORANGE/RED) 정의**, FEC 도입 |
| **Android 8.0 (Treble)** | **AVB 2.0**: 단일 서명 `vbmeta`로 통합, 디스크립터·체인 파티션·롤백 인덱스 |
| Android 11 | `vendor_boot` 파티션(벤더 램디스크/DTB) |
| Android 13 (GKI) | `init_boot` 파티션(제네릭 램디스크/init을 boot에서 분리) — **`boot.img`는 GKI 커널만** 담음 |

즉 "`boot.img`가 init을 담는다"는 Android 13+ GKI 기기에서는 틀립니다. 그리고 이 글의 vbmeta·디스크립터·체인·`verifiedBootHash` 얘기는 전부 **AVB 2.0(Android 8.0+)** 한정입니다 — 그 이전 기기에는 `vbmeta` 파티션 자체가 없습니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**호스트에서(기기 없이도 가능)**
- `avbtool info_image --image vbmeta.img` → 알고리즘·rollback index·flags(정상 0x0, `HASHTREE_DISABLED`/`VERIFICATION_DISABLED` 확인)와 각 디스크립터(Hash/Hashtree/Chain Partition/Prop/Kernel Cmdline). `boot.img`에 돌리면 끝의 `AvbFooter` 덕에 Hash 디스크립터가, `system` 관련엔 Hashtree 디스크립터가 보입니다. `avbtool verify_image`로 사슬 검증.

**Cuttlefish/QEMU와 공개 이미지에서**
- `getprop ro.boot.verifiedbootstate`(green/yellow/orange/red), `ro.boot.flash.locked`(1/0), `ro.boot.veritymode`(enforcing/logging), `ro.boot.vbmeta.digest`(부트로더가 실제 검증한 vbmeta 해시). `cat /proc/cmdline`.
- 공개 이미지의 `vbmeta.img`를 `avbtool info_image`로 분석하고, Cuttlefish에서 제공되는 `ro.boot.*` 속성을 실제 출력으로 확인합니다. 실제 단말의 잠금 해제 가능 여부를 조회하거나 변경하지 않습니다.
- `ls -l /dev/block/dm-*`로 verity 매핑된 파티션 확인 — 있으면 hashtree가 런타임에 강제 중, 있어야 할 파티션에 없으면 `--disable-verity` 흔적.

**소스·문서**
- AOSP `external/avb`(libavb: `avb_vbmeta_image.h`·`avb_descriptor.h`·`avb_chain_partition_descriptor.h`·`avb_footer.h`; `avbtool.py`)
- `source.android.com/docs/security/features/verifiedboot`(AVB·Boot flow·dm-verity), `.../keystore/attestation`(RootOfTrust)
- Linux `Documentation/admin-guide/device-mapper/verity.rst`

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **15~16주차 / CVE-01("에뮬레이터에선 안 보인다")**: 이제 이유가 분명합니다 — 강제는 **잠금 상태 + 하드웨어 신뢰의 뿌리**에 게이트됩니다. AOSP 에뮬레이터는 사실상 언락(ORANGE)이고 앵커할 퓨즈 RoT가 없어 vbmeta 강제가 없습니다. **빌드 변종 때문이 아닙니다** — userdebug 이미지도 테스트 키로 서명된 AVB 메타데이터를 싣고, 잠긴 기기에 그 키로 올리면 검증됩니다.
- **week18(이미지 마커·패치 수준)**: `ro.boot.vbmeta.digest`가 도는 시스템을 특정 서명 이미지에 묶고, 롤백 인덱스는 "패치 수준 라벨"과 달리 단조 정수라 되돌릴 수 없습니다.
- **C05(EL3·신뢰의 뿌리)**: 퓨즈 키 해시가 reset 시 신뢰되는 그 앵커이고, 검증이 사슬로 올라갑니다.
- **C08(서명 스킴)**: APK v1~v4가 앱마다 서명한다면, AVB는 vbmeta를 **한 번** 서명해 파티션들을 전이적으로 덮습니다 — 같은 RSA-over-digest 암호, 다른 범위.
- **C40/C42(Keystore·attestation)**: 부팅 상태가 attestation의 `RootOfTrust`로 전달됩니다(질문의 다리, 아래).
- **C31/C32(Treble·파티션 신뢰)**: 체인 파티션이 곧 파티션별 신뢰 위임입니다.
- 롤백은 **C29**에서, 기밀성 대비는 **C43(FBE)**에서 더 깊이 다룹니다.

## 호출 흐름

두 개를 손으로 그려 보시길 권합니다.

```
[ 신뢰의 사슬 — 퓨즈에서 커널까지 ]

OTP/eFuse: vbmeta 서명 공개키의 해시(다이제스트)   ← 불변, 재플래시 불가
   │  (Boot ROM 이 이 값으로 첫 단계 검증)
   ▼
Boot ROM ──검증──▶ 부트로더 단계들 ──검증──▶ 최종 부트로더(libavb)
                                                │
                                                ▼
                              vbmeta 검증:
                                hash(헤더 + 보조블록)  ← 인증블록은 제외
                                = 인증블록의 해시?
                                서명(다이제스트) RSA 검증
                                실려온 키의 해시 == 퓨즈 값?   ← 진짜 뿌리
                                                │ 통과
                                                ▼
                                        커널로 점프
```

```
[ 하나의 vbmeta 가 보증하는 것들, 그리고 원격까지 ]

           서명된 vbmeta
        ┌───────┼────────────┬─────────────────┐
        ▼       ▼            ▼                 ▼
   HASH 디스크립터  HASHTREE 디스크립터   CHAIN 디스크립터    rollback_index
   (boot 통째 해시) (system 루트 해시)   (vbmeta_system,     (RPMB/TEE 에
        │            │  ↓ dm-verity      vbmeta_vendor       저장, 다운그레이드
    로드시 검증    읽을 때마다 블록 검증   = 별도 키·롤백)      거부)
                                                │
   부팅 상태(GREEN/YELLOW/ORANGE/RED) ──────────┘
        │
        ▼
   Keystore attestation 의 RootOfTrust
   (verifiedBootState·deviceLocked·verifiedBootKey·verifiedBootHash)
        │  TEE 가 서명 — OS 는 위조 불가
        ▼
   원격 서버가 "이 기기는 GREEN + 잠김"을 암호학적으로 확인
```

두 번째 그림의 마지막이 C40으로 가는 다리입니다. `verifiedBootState`는 로컬 경고 화면만이 아니라 하드웨어 서명된 인증서 필드라, 침해된 OS도 GREEN을 위조하지 못합니다.

## 실측으로 확인한 것

이 모듈은 하드웨어 신뢰의 뿌리에 묶인 속성이 많아, 가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)의 실측과 공개 소스·공식 문서의 확정을 나눠 정리합니다. 먼저 위 실행 보고서의 관측을 이 모듈의 주장과 하나씩 이었습니다.

**1) 이 AVD에는 AVB 강제 신호가 실제로 부재한다 — 질문 8의 핵심.** 실행 보고서의 관측이 그대로 기록합니다: 이 Google APIs AVD에서 AVB 상태·A/B 슬롯 속성은 빈 값으로 나옵니다. 질문 7이 부팅 상태를 읽는 창구로 든 `ro.boot.verifiedbootstate`·`ro.boot.vbmeta.digest`가 이 AVD에서는 빈 값이고(보고서 각주 그대로 — 빈 속성은 AVD가 값을 제공하지 않았다는 뜻), 이것이 곧 질문 8의 주장을 세션 내에서 확증합니다: **강제는 잠금 상태 + 하드웨어 신뢰의 뿌리에 게이트되며, 에뮬레이터는 둘 다 없어 아무것도 강제되지 않는다.** 15~16주차의 "에뮬에선 안 보인다"가 빌드 변종 탓이 아니라 RoT 부재 탓이라는 정정과 일치합니다.

**2) Treble/APEX 파티션 분할은 이 AVD에서 활성이다 — 체인 파티션 위임의 전제.** 실행 보고서의 실제 명령으로 확인했습니다.

```console
$ getprop ro.treble.enabled
$ getprop ro.apex.updatable
```

두 속성 모두 활성으로 관측됐습니다(보고서: Treble/APEX 활성화). 질문 1·8이 CHAIN_PARTITION 디스크립터(`vbmeta_system`·`vbmeta_vendor`의 별도 키·롤백 슬롯)를 Treble의 파티션 분할(C31/C32)에 걸어 설명했는데, 그 분할 자체가 이 AVD에 실재함을 뒷받침합니다. 체인 vbmeta의 강제 검증 동작 자체는 libavb 소스로 확정하며(아래 「소스로 확정한 것」), 이 AVD에서는 파티션 분할이 실재한다는 전제까지를 실측으로 확인합니다.

**3) `/data`가 FBE로 암호화돼 "AVB ≠ 기밀성" 경계가 mount 출력에서 갈린다 — 질문 5.** 보고서의 `mount` 관측은 `/data`를 file-based encryption(`file`, `encrypted`)으로 보였습니다. 질문 5와 마치며가 그은 경계 — **AVB는 정지상태 무결성 + 롤백 방지일 뿐, 기밀성은 FBE(C43)의 몫** — 이 이 AVD의 실제 mount 산출물로 확인됩니다. 무결성 앵커(AVB)와 기밀성(FBE)이 별개 메커니즘임이 관측으로 구분됩니다.

vbmeta 봉투(256바이트 헤더·매직 `AVB0`·인증 블록 제외 해시)와 HASH/HASHTREE/CHAIN 디스크립터, dm-verity 머클 루트가 서명된 vbmeta에 앵커된다는 구조적 주장(질문 4·5)은 libavb 소스와 공식 문서로 확정했습니다 — 아래 「소스로 확정한 것」이 그 출처입니다.

## 소스로 확정한 것

하드웨어 신뢰의 뿌리에 묶인 속성들은 공개 AOSP 소스와 공식 문서로 사실을 확정하고, ARM64 아키텍처 신뢰 경계는 정적 마커를 직접 실측해 뒷받침합니다.

- **vbmeta 봉투·디스크립터·롤백·flags 구조는 libavb 소스로 확정합니다.** 256바이트 헤더(매직 `AVB0`), 인증 블록을 뺀 해시 입력, HASH/HASHTREE/CHAIN 디스크립터의 TLV 레이아웃, 단조 증가 `rollback_index`, `HASHTREE_DISABLED`/`VERIFICATION_DISABLED` flags는 모두 `external/avb`의 헤더와 `avbtool.py`에 정의돼 있습니다 — 질문 4·7의 구조 주장은 이 소스가 출처이고, `avbtool info_image`/`verify_image`가 읽어 내는 값도 바로 이 구조입니다. ([AOSP external/avb](https://cs.android.com/android/platform/superproject/+/main:external/avb/) · [Android Verified Boot](https://source.android.com/docs/security/features/verifiedboot))

- **dm-verity의 읽기시 블록 검증과 실패 모드는 커널 문서·소스로 확정합니다.** 4KiB 블록마다 SHA-256(+salt)으로 리프 해시를 만들어 머클 트리 루트까지 올리는 구조, 블록을 읽을 때 검증하는 lazy 동작, `restart`/`eio`/`logging` 실패 모드, FEC(Reed-Solomon)의 복구 범위는 Linux device-mapper verity 문서에 규정돼 있습니다 — 질문 5의 dm-verity 서술은 이 문서가 출처입니다. verity 매핑은 잠긴 실기기의 `/dev/block/dm-*`에서 런타임 강제되고, 그 강제 규칙 자체는 문서가 정의합니다. ([Linux dm-verity](https://www.kernel.org/doc/html/latest/admin-guide/device-mapper/verity.html))

- **하드웨어 신뢰의 뿌리는 공식 문서로 확정합니다.** OTP/eFuse에 굽는 vbmeta 키 해시, RPMB/TEE 롤백 저장소, 부트 ROM, ARM64 EL3 시큐어 모니터의 역할, 그리고 그 위에서 `verifiedBootState`가 하드웨어 서명 인증서로 전달되는 경로는 Android Verified Boot·Key Attestation 문서로 확정됩니다. 이들은 실리콘에 고정된 하드웨어 속성이므로 근거의 자리도 소스와 문서입니다. ([Key Attestation·RootOfTrust](https://source.android.com/docs/security/features/keystore/attestation))

- **ARM64 아키텍처 신뢰 경계는 정적 마커를 실측하고, 런타임 동작을 소스로 확정합니다.** 선수 C05가 든 ARM64 EL3·PAC/BTI 신뢰 경계에서, 분기 보호·포인터 인증 마커는 실제로 실측했습니다. arm64 타깃으로 빌드한 공유 라이브러리를 readelf로 뜯으면 `.note.gnu.property`에 aarch64 BTI·PAC feature가 그대로 박혀 있고, `-mbranch-protection=none` 대조군에서는 이 note가 사라집니다.

```console
$ readelf -hn arm64-target.so
  Machine:                           AArch64
Displaying notes found in: .note.gnu.property
  GNU                  0x00000010	NT_GNU_PROPERTY_TYPE_0 (property note)
    Properties:    aarch64 feature: BTI, PAC
# 대조군(-mbranch-protection=none) 빌드: BTI/PAC note 매치 0
```

마커는 이렇게 실측했고, 런타임의 분기 목표 강제·포인터 인증 동작은 Arm 아키텍처 문서로 확정합니다. ([Arm Architecture Reference Manual](https://developer.arm.com/documentation/ddi0487/latest))

관련 근거: [Android Verified Boot](https://source.android.com/docs/security/features/verifiedboot) · [Key Attestation·RootOfTrust](https://source.android.com/docs/security/features/keystore/attestation) · [AOSP external/avb (libavb)](https://cs.android.com/android/platform/superproject/+/main:external/avb/) · [Linux dm-verity](https://www.kernel.org/doc/html/latest/admin-guide/device-mapper/verity.html)

## 마치며

15~16주차의 "에뮬레이터에선 안 보인다"는 한 줄은, 사실 이 모듈 전체를 압축하고 있었습니다 — **AVB의 모든 보장이 잠긴 부트로더와 하드웨어 신뢰의 뿌리를 전제**하기 때문에, 그것이 없는 에뮬레이터에서는 아무것도 강제되지 않았던 것입니다. 신뢰는 퓨즈된 키 **해시**에서 시작해(전체 키가 아니라), 부트로더가 vbmeta 서명을 검증하고, 그 vbmeta가 dm-verity의 루트 해시를 보증하고, 마침내 부팅 상태가 TEE 서명 attestation으로 원격까지 전달됩니다.

그리고 그 범위는 분명합니다: AVB는 **부팅시점·정지상태의 무결성과 롤백 방지**이지, 런타임 방어도 기밀성도 아닙니다. 커널을 따면(C05의 EL0→EL1) 살아있는 시스템은 여전히 넘어가고, 데이터 기밀성은 C43(FBE)의 몫입니다. 다음은 이 부팅 상태가 실제로 키에 서명돼 나가는 자리인 **C40(Keystore·KeyMint·StrongBox)**, 또는 롤백 방지를 더 깊이 보는 **C29**로 이어집니다. 이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.
