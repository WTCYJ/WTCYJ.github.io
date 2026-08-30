---
layout: post
title: "Android Security Concept Atlas C30 | 가상 실습 보고서 — A/B 무중단 업데이트·dynamic partitions·Virtual A/B"
date: 2026-09-02 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ABUpdate, SeamlessUpdate, DynamicPartitions, superimg, VirtualAB, VABC, updateengine, bootcontrol, OTA, ConceptAtlas, 학습기록]
excerpt: "OTA 하나가 어떻게 실행 중인 폰을 건드리지 않고 배경에서 설치되고, 새 빌드가 부팅에 실패하면 어떻게 저절로 예전으로 돌아가는가. A/B는 부팅 핵심 파티션을 두 슬롯으로 두고 비활성 슬롯에 업데이트를 쓴 뒤 재부팅으로 전환하며, 실패하면 부트로더가 롤백합니다. dynamic partitions는 고정 GPT를 super 하나 속 논리 파티션으로 바꿔 OTA가 재분할하게 하고, Virtual A/B는 두 벌 저장 비용을 스냅샷으로 없앱니다. 그리고 이 '슬롯 롤백'은 C28의 AVB 롤백 인덱스와 완전히 다른 층입니다 - 자주 헷갈리는 지점이죠. Concept Atlas의 열다섯 번째 모듈입니다."
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

![C30 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C30 — A/B OTA·dynamic partitions·super.img
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 중급 · **선수 개념**: C27(부트로더), C28(Verified Boot·롤백 인덱스)
> **성격**: 공식 문서·공개 소스 기준 재검토. Domain 2(부팅·업데이트 체인)를 채웁니다.

OTA 하나가 어떻게 실행 중인 폰을 건드리지 않고 배경에서 설치되고, 새 빌드가 부팅에 실패하면 어떻게 저절로 예전으로 돌아가는가 — 이게 이 모듈입니다. C28이 "부팅된 게 진짜인가"였다면, C30은 그 이미지가 **어떻게 갱신되고, 실패해도 어떻게 살아 돌아오는가**입니다.

한 문장으로: **부팅 핵심 파티션을 두 슬롯으로 두고 비활성 슬롯에 업데이트를 쓴 뒤 재부팅으로 전환하며, 새 슬롯이 스스로를 검증하지 못하면 부트로더가 예전 슬롯으로 롤백한다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 두 슬롯과 하나의 super

- **A/B(무중단) 업데이트**: 부팅 핵심 파티션(boot·system·vendor·vbmeta 등)을 두 슬롯(`_a`/`_b`)으로 둠. userdata는 **공유**(중복 아님).
- **update_engine**: 실행 중 시스템의 데몬. OTA를 **비활성 슬롯**에 씀.
- **boot_control HAL(`IBootControl`)**: 슬롯 상태(활성/부팅가능/성공/재시도)를 부트로더와 주고받음.
- **dynamic partitions**: 고정 GPT 파티션을 `super` 하나 속 **논리 파티션**으로 바꿔 OTA가 재분할 가능.
- **Virtual A/B**: 두 벌 저장 대신 **스냅샷(COW)**으로 A/B 의미를 구현.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

부팅 체인의 **업데이트 측면**입니다. C28이 각 슬롯을 **독립적으로 AVB 검증**하고, C27의 부트로더가 슬롯을 골라 부팅합니다. 그리고 dynamic partitions는 C31/C32의 파티션 신뢰 구조를 **유연하게** 만든 것이고, Virtual A/B의 COW는 C43의 userdata 위에 얹힙니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **`update_engine`**(실행 중 시스템)이 서명된 OTA 페이로드를 **비활성 슬롯**에 배경으로 씁니다.
- **부트로더 + `boot_control` HAL**이 슬롯을 활성/부팅가능으로 표시하고 다음 부팅에 전환합니다.
- **첫 부팅 후 검증**: 네이티브 **`update_verifier`**가 `care_map`에 나열된 블록을 읽어 커널 dm-verity 검증을 **강제**하고(자기가 해시 트리를 걷는 게 아니라, 읽어서 dm-verity가 검증하게 함), 통과하면 `markBootSuccessful`을 호출합니다.
- **dynamic partitions 마운트**: first-stage init(`fs_mgr_dm_linear`)이 `super`의 liblp 메타데이터를 읽어 논리 파티션마다 **dm-linear** 가상 블록 장치를 만듭니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **두 롤백은 완전히 다른 층입니다.** (1) **슬롯 성공 롤백**: 새 슬롯이 재시도 예산 안에 스스로 성공 표시를 못 하면(부트 루프·verifier 실패) 부트로더가 그 슬롯을 부팅불가로 표시하고 **이전 성공 슬롯**으로 돌아감 — 나쁜 부팅 복구. (2) **AVB 롤백 인덱스**(C28): vbmeta 롤백 인덱스가 저장값보다 낮은 이미지는 아예 부팅 거부 — 다운그레이드 차단. **이 둘을 합치는 게 A/B 최대 오해입니다.**
- **각 슬롯은 독립적으로 AVB 검증**됩니다. userdata는 슬롯 공유입니다(중복 아님).
- **OTA 페이로드는 서명 검증**을 거칩니다(payload 키 + per-operation 블록 해시).
- **신뢰하면 안 되는 것들**: "슬롯 롤백 = AVB 안티롤백"(다른 층), "모든 파티션이 중복"(boot-critical만), "A/B도 recovery/cache를 쓴다"(제거됨 — recovery 램디스크는 boot/GKI에선 init_boot로), "Virtual A/B는 Android 11부터 필수"(13부터).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 서명된 OTA 페이로드(`payload.bin`). **delta**(원본 슬롯 대비 블록 차분, 작음) 또는 **full**, 스트리밍 가능.
- **출력**: 비활성 슬롯(또는 VAB 스냅샷)에 쓰인 새 빌드. 실행 슬롯은 `ro.boot.slot_suffix`(`_a`/`_b`)로 노출되고, fstab의 파티션 이름에 치환됩니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **페이로드 검증**: `update_engine`이 페이로드 서명과 블록 해시를 적용 전·중에 확인해, 변조/손상 페이로드는 거부합니다. 이게 OTA의 주 공격 표면(페이로드 검증·liblp 파싱·스트리밍 OTA)입니다.
- **부팅 실패 복구**: 새 슬롯이 재시도 소진 시 `setSlotAsUnbootable` → 이전 슬롯 롤백. 사용자 개입 없이 자동.
- **다운그레이드 차단**: AVB 롤백 인덱스가 구버전을 막습니다. 단 **롤백 인덱스는 매 OTA가 아니라 보안 마일스톤에만 증가**하므로, 그 사이 버전으로의 다운그레이드는 인덱스로는 안 막힙니다(거친 단위).
- **VAB 롤백 창**: Virtual A/B는 **병합(merge) 전에만** 롤백 가능합니다. 병합이 시작되면 이전 상태가 사라집니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 7.0 | **A/B 무중단 업데이트** 도입(선택). recovery/cache OTA 흐름 제거 |
| Android 10 | **dynamic partitions**(super + 논리 파티션, liblp) |
| Android 11 | **Virtual A/B**(단일 super + COW 스냅샷) 도입 |
| Android 12 | **VABC**(Virtual A/B Compression, `snapuserd`/`dm-user`로 COW 압축) |
| **Android 13** | Virtual A/B **필수**(신규 기기). init_boot 분리(C27) |

**Virtual A/B의 실체**: 두 벌 대신 한 벌 + 스냅샷입니다. `update_engine`이 새 데이터를 **COW 스냅샷**(COW는 `/data`에, 상태는 `/metadata`에)으로 쓰고, 새 빌드가 성공 부팅해 표시되면 **병합**이 스냅샷을 베이스로 복사합니다. 순수 Android 11 VAB는 **커널 dm-snapshot**으로 병합하고, **VABC(12+)만** 유저스페이스 `snapuserd`/`dm-user`를 씁니다. 단 이건 **읽기전용 dynamic partitions에만** — 작은 boot-critical 파티션(boot·init_boot·vendor_boot·vbmeta)은 여전히 진짜 A/B `_a`/`_b`라, VAB 기기는 하이브리드입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**온디바이스(플래시 없이)**
- `fastboot getvar current-slot` / `getvar slot-count`(또는 온디바이스 `bootctl get-current-slot` / `get-number-slots`), `getprop ro.boot.slot_suffix`(실행 슬롯).
- `lpdump`(super의 liblp 논리 파티션 레이아웃), `ls /dev/block/mapper`(dm-linear로 매핑된 논리 파티션).

**소스**
- `source.android.com/docs/core/ota/{ab,ab/ab_implement,dynamic_partitions,virtual_ab}`
- AOSP `system/update_engine`(+ `update_verifier`), `hardware/interfaces/boot`(`IBootControl`), `system/core/fs_mgr`/`liblp`, `libsnapshot`/`snapuserd`

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C28(Verified Boot)**: 각 슬롯이 독립 AVB 검증되고, **슬롯 롤백(부트로더) ≠ 롤백 인덱스(AVB)** 두 층이 여기서 갈립니다. `update_verifier`가 첫 부팅에 dm-verity를 강제하는 것도 C28의 hashtree입니다.
- **C27(부트로더·init)**: 부트로더가 슬롯을 골라 부팅하고, first-stage init이 dm-linear로 논리 파티션을 마운트합니다.
- **C31/C32(Treble·파티션 신뢰)**: dynamic partitions가 고정 파티션의 경직성을 풀어, OTA가 파티션 크기를 재조정하게 합니다.
- **C43(FBE)**: Virtual A/B의 COW 데이터가 userdata(`/data`)에 얹힙니다.
- 다음은 **C31(Treble·GSI·Mainline·APEX)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ A/B 무중단 업데이트의 한 주기 ]

실행 슬롯 _a
   │  update_engine: 서명된 페이로드를 비활성 슬롯 _b 에 배경 기록(검증하며)
   ▼
재부팅 → 부트로더: _b 를 활성·재시도 카운터로 부팅
   │
   ▼
새 시스템(_b) 부팅 → update_verifier: care_map 블록 읽어 dm-verity 강제
   │  통과 → markBootSuccessful (_b 성공)         → 정착
   │  실패/부트루프 → 재시도 소진 → setSlotAsUnbootable(_b)
   ▼                                              → 부트로더가 _a 로 롤백
  (별개 층) AVB 롤백 인덱스: 구버전 이미지면 슬롯 무관하게 부팅 거부
```

```
[ 진짜 A/B vs Virtual A/B ]

진짜 A/B   : super 안에 system_a + system_b (2벌) — 즉시 슬롯 전환·병합 없음
Virtual A/B: super 안에 한 벌 + COW 스냅샷(/data)
             성공 부팅 후 병합(merge): 11=커널 dm-snapshot, 12+ VABC=snapuserd/dm-user
             롤백은 병합 전에만 가능
```

## 오개념 판별 문제 5개

1. "A/B 슬롯 롤백과 AVB 롤백 인덱스 안티다운그레이드는 같은 보호다."
2. "A/B 업데이트도 recovery로 재부팅해 /cache에 스테이징한다."
3. "슬롯 A/B는 userdata를 포함한 모든 파티션을 두 벌 복제한다."
4. "Virtual A/B는 Android 11부터 모든 기기의 기본/필수 OTA 방식이다."
5. "새 슬롯은 부팅하자마자 markBootSuccessful로 성공 표시된다."

<details><summary>판정 기준(펼치기)</summary>

1. 다른 층입니다. 슬롯 롤백(부트로더)은 나쁜 부팅을 복구하고, AVB 롤백 인덱스는 저장값보다 낮은 버전을 아예 거부합니다(다운그레이드 차단).
2. A/B는 recovery/cache 흐름을 제거했습니다. 실행 중 비활성 슬롯에 in-place로 씁니다.
3. boot-critical 파티션(boot·system·vendor·vbmeta 등)만 슬롯화됩니다. userdata는 **공유**입니다.
4. Virtual A/B는 11 도입이지만 **13부터 필수**입니다. 11/12는 선택(진짜 A/B나 non-A/B도 가능).
5. 즉시가 아닙니다. 네이티브 `update_verifier`가 첫 부팅에 care_map 블록으로 dm-verity를 강제해 통과한 **후에만** 성공 표시됩니다.
</details>

## 실측으로 확인한 것

이 모듈은 슬롯·부트로더·하드웨어 롤백 퓨즈를 다루므로 핵심 대상은 x86_64 AVD의 범위를 넘어선다. 그래도 이 세션의 검증 블록으로 실제 확인한 토대부터 정리한다.

**1) A/B와 dynamic partitions가 얹히는 플랫폼 토대(Treble·APEX)는 이 AVD에서 활성으로 확인된다.** dynamic partitions와 모듈식 OTA는 Treble 기반 파티션 분리 위에서 성립하는데, `codex-atlas-api33`에서 두 속성이 모두 켜져 있었다.

```console
$ getprop ro.treble.enabled
true
$ getprop ro.apex.updatable
true
```

이 값은 질문 1의 배치 — "dynamic partitions는 C31/C32의 파티션 신뢰 구조를 유연하게 만든 것" — 가 성립하기 위한 전제(Treble 분리)가 실제로 켜져 있음을 뜻한다. 검증 블록의 관측 결과("Treble/APEX 활성화")가 가리키는 그대로다.

**2) A/B가 두 벌로 복제하지 않는 공유 userdata(`/data`)는 FBE로 암호화되어 실재한다.** 검증 블록의 `mount` 수집에서 `/data`가 file-based encryption 상태로 확인됐다.

```console
$ mount        # /data → file-based encryption: file, encrypted
```

질문 3의 "userdata는 슬롯 공유(중복 아님)"와 질문 8의 "Virtual A/B의 COW 데이터가 userdata(`/data`)에 얹힌다"가 가리키는 바로 그 파티션이, 이 AVD에서 `file`·`encrypted`로 확인된다. VAB 스냅샷이 앉을 자리는 슬롯화된 두 벌이 아니라 이 한 벌의 `/data`라는 불변식이, 실제 마운트 상태로 뒷받침된다.

**3) 이 AVD는 A/B 기기가 아니며, 그 사실 자체가 질문 7의 관측과 일치한다.** 검증 블록 기록대로 이 Google APIs AVD는 AVB 상태와 A/B 슬롯 속성을 노출하지 않았다 — `getprop ro.boot.slot_suffix`가 공백이었다. 질문 7에 적은 "에뮬/일부 기기는 A/B·dynamic partitions가 없을 수 있다"가 그대로 관측된 셈이고, 따라서 슬롯 전환·부트로더 롤백·롤백 인덱스의 동작 서술은 이 세션의 캡처가 아니라 AOSP 소스와 공식 문서를 근거로 삼았다.

## 가상환경 검증 한계

정직하게, 이 x86_64 Google APIs AVD 세션에서 새로 캡처한 것은 위의 플랫폼 토대(Treble·APEX)와 공유 `/data`의 FBE 상태까지다. 슬롯과 롤백의 실제 동작은 이 환경에서 재현하지 못했다.

- **A/B 슬롯 전환과 부트로더 롤백은 이 AVD에서 관측하지 못했다.** 검증 블록 기록대로 AVB 상태와 A/B 슬롯 속성이 노출되지 않았고(`ro.boot.slot_suffix` 공백), 이 에뮬레이터는 A/B 기기가 아니다. `setSlotAsUnbootable`·재시도 카운터·`markBootSuccessful`의 실제 흐름은 소스·문서 근거로만 서술했다.
- **하드웨어 롤백 퓨즈와 부트 ROM은 x86_64 에뮬레이터의 검증 범위 밖이다.** AVB 롤백 인덱스가 다운그레이드를 최종 강제하는 지점은 실물 부트 체인에 있어, 이 세션에서는 실측하지 않았다.
- **dynamic partitions와 Virtual A/B의 실체(`lpdump`·`/dev/block/mapper`·COW 스냅샷·`snapuserd` 병합)는 이 AVD에 존재하지 않아 캡처하지 못했다.** update_engine의 비활성 슬롯 기록과 update_verifier의 첫 부팅 dm-verity 강제도 이 환경의 재현 대상이 아니었다.

관련 근거: [A/B(무중단) 업데이트](https://source.android.com/docs/core/ota/ab) · [Dynamic partitions](https://source.android.com/docs/core/ota/dynamic_partitions) · [Virtual A/B](https://source.android.com/docs/core/ota/virtual_ab) · [AOSP update_engine](https://cs.android.com/android/platform/superproject/+/main:system/update_engine/)

## 마치며

A/B는 OTA를 "재부팅하며 설치"에서 "배경 설치 + 빠른 전환 + 자동 롤백"으로 바꿨고, dynamic partitions는 고정 파티션의 경직성을 super 속 논리 파티션으로 풀었으며, Virtual A/B는 두 벌 저장 비용을 스냅샷으로 없앴습니다. 이 모든 것 위에서 **각 슬롯은 독립적으로 AVB 검증**되고, 두 개의 롤백 — 부트로더의 슬롯 롤백과 AVB의 롤백 인덱스 — 이 서로 다른 실패를 막습니다. 이 둘을 헷갈리지 않는 것이 이 모듈의 핵심입니다. 다음은 파티션 신뢰를 플랫폼/벤더로 나누는 **C31(Treble·GSI·Mainline·APEX)**로 이어집니다.
