---
layout: post
title: "Android Security Concept Atlas C29 | 가상 실습 보고서 — 롤백 방지·롤백 인덱스, 서명된 옛 이미지를 막는 층"
date: 2026-09-29 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, RollbackProtection, AntiRollback, RollbackIndex, AVB, RPMB, KeyMint, ConceptAtlas, 학습기록]
excerpt: "검증 부팅(C28)은 이미지가 진짜인지 확인하지만, 벤더가 예전에 정당하게 서명한 '오래된' 이미지도 여전히 진짜입니다 - 그래서 서명만 보면 몇 달 전의, 이미 패치된 취약점을 담은 빌드도 그냥 부팅되죠. 롤백 방지는 그 다운그레이드를 막는 별개 층입니다: 이미지의 롤백 인덱스가 RPMB 같은 변조증거 저장소의 최소값보다 작으면 부팅을 거부하고, 성공 부팅 후 그 최소값을 앞으로만 올리죠. 핵심 뉘앙스 - 이미지의 인덱스는 그 빌드의 고정값이라 연속 빌드가 같은 값일 수 있고, 단조로 오르는 건 저장된 최소값이며, 월단위 다운그레이드 방지는 사실 AVB가 아니라 KeyMint의 os_patchlevel 바인딩이 담당합니다. 내 부팅/펌웨어 작업과 맞닿는 Tier 5 모듈입니다."
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

![C29 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C29 — 롤백 방지·롤백 인덱스
> **계층**: Tier 5 (부팅·업데이트 체인) · **난이도**: 고급 · **선수 개념**: C28(AVB/vbmeta)
> **성격**: 공식 문서·공개 소스 기준 재검토 — 초점 좁은 모듈.

C28에서 AVB가 이미지의 진위를 증명한다 했습니다. 그런데 **벤더가 예전에 서명한 오래된 이미지도 여전히 진짜**입니다 — 그 다운그레이드를 막는 별개 층이 이 편입니다.

한 문장으로: **서명은 이미지가 진짜임을 증명하지만, 롤백 인덱스는 그것이 "서명됐지만 낡은" 빌드가 아님을 증명한다.** 🔴이지만 초점을 좁힙니다.

## 배경 개념

- **위협**: 서명된 **옛 이미지**로 다운그레이드 → 이미 패치된 n-day 재노출.
- **롤백 인덱스**: vbmeta의 정수(`rollback_index_location`별, 최대 32슬롯).
- **저장**: 변조증거 보안 저장소(**RPMB**/TEE)에 "최소 허용값".

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**검증 부팅(C28) 위의 별개 층**입니다. 서명·dm-verity가 진위를, 롤백 인덱스가 최신성을 증명 — 둘 다 통과해야 부팅. C42(원격 탐지)·C40(롤백저항 키)·C30(A/B)와 얽힙니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **롤백 인덱스**: AVB 2.0의 vbmeta가 담는 정수(`rollback_index` uint64), `rollback_index_location`(uint32, 서명 시 지정, 관례상 최상위 vbmeta=0·체인 파티션=1,2…, 최대 32슬롯)별로 독립.
- **비교**: 부트로더/검증부팅이 부팅 시 **이미지 인덱스 vs 저장된 최소값**을 대조.
- **저장**: **RPMB**(Replay Protected Memory Block — 256비트 키·HMAC-SHA256·단조 쓰기 카운터, eMMC 4.4+/UFS, 키는 REE에 노출 안 됨) 또는 TEE/Trusty 보안 저장소.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **서명 위의 별개 층**: 진위(서명)와 최신성(인덱스)은 다른 검사이고 **둘 다** 통과해야.
- **신뢰하면 안 되는 것들**:
  - **"서명을 통과하면 안전"** — 오래된 서명 이미지도 진짜입니다. 다운그레이드는 서명이 못 보는 별개 위협.
  - **"이미지의 롤백 인덱스가 단조 증가한다"** — 아닙니다. 이미지의 인덱스는 **그 빌드의 고정값**이라 연속 빌드가 **같은 값**일 수 있습니다. 단조 비감소인 건 **저장된 최소값**.
  - **"월단위 다운그레이드 방지가 AVB 롤백 인덱스"** — AVB 인덱스는 **드물게만**(반드시 롤백 불가여야 할 수정 시) 올립니다. 월단위 패치레벨 다운그레이드 방지는 **KeyMint `os_patchlevel`/`boot_patchlevel` 바인딩**이 별도로 담당(C40/C42).
  - **"ROLLBACK_RESISTANCE는 다운그레이드 시 키가 자폭"** — 아닙니다. **삭제 영속성** 보장입니다(`deleteKey` 후 백업/저장소 롤백으로도 복원 불가). 보안 저장소 뒷받침이 없으면 `ROLLBACK_RESISTANCE_UNAVAILABLE` 반환(KM4.0에서 개명).
  - **"저장값이 일반 플래시에 있어도 된다"** — 재플래시로 되돌릴 수 있으면 무력. **RPMB/TEE**라야.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 이미지 vbmeta의 `rollback_index`(위치별) + 저장된 최소값.
- **로직**: `image_index < stored_min` 이면 **부팅 거부**(다운그레이드 차단). 성공 부팅/업데이트 후 저장값을 이미지값으로 **전진**(forward-only 래칫, **동등은 통과**).
- **A/B(C30)**: 슬롯이 **성공 표시된 뒤** 인덱스를 커밋(플래시 시점 아님) → 확인 전엔 이전 슬롯 폴백 유지.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **위협**: 플래시 접근(또는 물리) 공격자가 오래된 서명 펌웨어/부트/vbmeta로 n-day를 재노출 → 롤백 방지가 부팅 거부.
- **한계/뉘앙스**:
  - 저장이 **replay-protected**(RPMB)여야 — 아니면 공격자가 저장값을 되돌려 무력화.
  - **다운그레이드만** 방지(현재 이미지의 0day는 못 막음).
  - **벤더가 인덱스를 실제로 올려야** — 안 올린 수정은 같은-인덱스 옛 이미지가 여전히 수용.
- **원격 탐지**: 로컬에서 새어도 **key attestation**(C42)의 patchlevel/부팅상태가 다운그레이드를 relying party에 노출.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **AVB 2.0**: vbmeta에 rollback_index + location(최대 32).
- **RPMB**: eMMC 4.4+/UFS.
- **KeyMint 패치레벨 바인딩**: 월단위 다운그레이드 방지의 실질 담당. `ROLLBACK_RESISTANCE`(옵션)는 KM4.0에서 boolean `ROLLBACK_RESISTANT`를 대체.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `avbtool info_image --image vbmeta.img`(헤더의 `Rollback Index`/`Rollback Index Location`; 체인 파티션 descriptor는 자기 location 출력).
- `getprop | grep -E 'ro.boot.vbmeta|verifiedbootstate|ro.boot.flash.locked'`, `fastboot getvar`(일부는 anti-rollback/슬롯 노출).
- key attestation 확장 필드(osPatchLevel·bootPatchLevel·verified boot state)로 원격 탐지.
- **소스**: AOSP `external/avb/README.md`(AVB 2.0), Trusty secure storage, KeyMint HAL Tag 정의, `source.android.com/docs/security/features/verifiedboot`.

**주의**: 일반 x86_64 AVD에서는 hardware-backed rollback index storage를 검증할 수 없습니다. `avbtool info_image`로 metadata를 분석하고 Cuttlefish의 가상 동작을 관찰하되, RPMB 보증은 `가상 환경의 검증 한계`로 남깁니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C28(AVB/vbmeta)**: 롤백 인덱스가 그 vbmeta 위에.
- **C42(attestation)**: patchlevel 보고로 다운그레이드 원격 탐지 — 예방(인덱스)과 탐지(증명)의 상보.
- **C40(Keystore)**: os_patchlevel 바인딩·ROLLBACK_RESISTANCE·RPMB.
- **C30(A/B)**: 슬롯 성공 후 커밋으로 폴백 보존.
- **C27(부트로더)**: 비교·거부를 부트로더가 수행.
- 다음은 다른 티어(앱통제 등)로.

## 직접 그릴 수 있는 호출 흐름

```
[ 롤백 방지: 서명 위의 최신성 검사 ]

  이미지(vbmeta): 서명 OK(C28)  +  rollback_index (그 빌드 고정값)
        │
  부트로더: image_index  vs  저장된 최소값(RPMB/TEE)
        ├ image_index <  stored_min → 부팅 거부 (다운그레이드 차단)
        ├ image_index >= stored_min → 부팅 (동등 통과)
        └ 성공 부팅 후: stored_min ← image_index (forward-only 래칫)
                        (A/B는 슬롯 성공 표시 후 커밋)

  월단위 다운그레이드 방지 = KeyMint os_patchlevel 바인딩(별도, C40)
  원격 탐지 = attestation의 patchlevel/부팅상태 (C42)
  ⚠ 저장이 RPMB/TEE 아니면 재플래시로 무력화
```

## 오개념 판별 문제 5개

1. "검증 부팅에서 서명 검증만 통과하면, 오래된 펌웨어로 다운그레이드해도 안전하다."
2. "이미지에 박힌 롤백 인덱스는 빌드마다 하나씩 증가하는 단조 카운터다."
3. "매달 나오는 보안 패치의 다운그레이드는 AVB 롤백 인덱스가 막는다."
4. "`ROLLBACK_RESISTANCE` 키는 OS를 다운그레이드하면 자동으로 파괴된다."
5. "롤백 최소값을 일반 플래시 파티션에 저장해도 안전하다."

<details><summary>판정 기준(펼치기)</summary>

1. 오래된 서명 이미지도 진짜입니다 — 다운그레이드는 별개 위협이고 **롤백 인덱스**가 막습니다.
2. 이미지의 인덱스는 **그 빌드 고정값**(연속 빌드가 같은 값 가능)입니다. 단조인 건 **저장된 최소값**.
3. AVB 인덱스는 드물게만 올립니다. 월단위는 **KeyMint `os_patchlevel` 바인딩**이 별도로.
4. **삭제 영속성** 보장입니다(삭제 시 복원 불가). 다운그레이드 자폭이 아닙니다.
5. 재플래시로 되돌릴 수 있으면 무력. **RPMB/TEE**(replay-protected)라야.
</details>

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 이 모듈이 검증할 수 있는 지점과 없는 지점을 실제로 갈라 확인했다. 롤백 방지의 저장·비교는 RPMB/TEE·부트로더에 있어 에뮬레이터가 직접 만질 수 없으므로, 측정으로 확정한 것과 소스·문서로 확정한 것을 나눠 적는다.

**1) 이 AVD는 업데이트 인프라(Treble/APEX)는 노출하되 롤백 방지의 실측 지점은 노출하지 않는다 — 질문 7의 주의가 실측으로 확인된다.** 검증 블록의 명령으로 Treble/APEX 활성화와 `/data`의 file-based encryption(`file`, `encrypted`)까지는 확인했으나, 같은 AVD가 AVB 상태·A/B 슬롯 속성은 내주지 않았다.

```console
$ getprop ro.treble.enabled
$ getprop ro.apex.updatable
$ mount
```

관측 결과는 검증 블록 표(| 관측 결과 |)와 상단 [부팅 증거 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)에 보존했다. 즉 "일반 x86_64 AVD에서는 hardware-backed rollback index storage를 검증할 수 없다"(질문 7 주의)가 추측이 아니라 이 세션의 실제 관측이다 — AVB의 `rollback_index`와 저장된 최소값을 읽을 인터페이스 자체가 이 이미지에 없다.

**2) 저장이 replay-protected여야 한다는 불변식은 소스로 확정된다(질문 3·5).** 저장소가 RPMB(Replay Protected Memory Block — 256비트 키·HMAC-SHA256·단조 쓰기 카운터, 키가 REE에 노출되지 않음) 또는 TEE 보안 저장소여야, 재플래시로 최소값을 되돌려 무력화하는 공격이 막힌다. 이 구조는 AOSP `external/avb`와 eMMC/UFS 규격에 명시돼 있고, 에뮬레이터가 그 저장소를 갖지 않는다는 점이 (1)의 관측과 정확히 맞물린다.

**3) 월단위 다운그레이드 방지는 AVB 롤백 인덱스가 아니라 KeyMint `os_patchlevel` 바인딩이 담당한다(질문 3·6·8).** AVB `rollback_index`는 반드시 롤백 불가여야 할 수정에서만 드물게 오르고, 매달의 패치레벨 다운그레이드 차단은 KeyMint의 `os_patchlevel`/`boot_patchlevel` 바인딩이, 원격 노출은 key attestation의 patchlevel/부팅상태 보고(C42)가 나눠 맡는다. 이 역할 분담은 KeyMint HAL Tag 정의와 attestation 확장 필드 문서로 확인된다.

## 가상환경 검증 한계

정직하게, 이 문서에서 새로 캡처한 실측은 (1)의 속성 관측까지다. (2)·(3)은 근거를 소스·문서로 확정했으나 이 AVD 세션에서 하드웨어 동작으로 재현하지는 않았다.

- **AVB `rollback_index`와 저장된 최소값을 이 세션에서 읽지 못했다.** 이 Google APIs x86_64 AVD는 AVB 상태·A/B 슬롯 속성을 노출하지 않아, `avbtool info_image`가 대상으로 삼을 실기 vbmeta도, 부트로더의 비교·전진(forward-only 래칫)도 관측 범위 밖이었다.
- **RPMB/TEE 롤백 저장의 replay-protection은 소프트웨어 폴백으로만 존재한다.** 에뮬레이터에는 실제 RPMB 파티션과 하드웨어 보안 저장소가 없어, 단조 쓰기 카운터의 물리적 보증은 측정하지 못했다. 하드웨어 롤백 퓨즈와 부트 ROM도 검증 범위 밖이다.
- **다운그레이드 부팅 거부를 라이브로 재현하지 않았다.** 오래된 서명 이미지로 실제 플래시·다운그레이드해 부팅 거부를 유발하는 절차는 실물 기기·언락이 필요해 이 가상 실습에서 다루지 않았다.

관련 근거: [AVB 2.0 README (AOSP external/avb)](https://cs.android.com/android/platform/superproject/+/master:external/avb/README.md) · [Verified Boot](https://source.android.com/docs/security/features/verifiedboot) · [Android Keystore/KeyMint](https://source.android.com/docs/security/features/keystore) · [Key Attestation](https://developer.android.com/privacy-and-security/security-key-attestation)

## 마치며

검증 부팅(C28)은 이미지가 진짜인지 확인하지만, 벤더가 예전에 정당하게 서명한 오래된 이미지도 여전히 진짜입니다 — 그래서 서명만 보면 이미 패치된 취약점을 담은 빌드도 그냥 부팅되죠. 롤백 방지는 그 다운그레이드를 막는 별개 층입니다: 이미지의 롤백 인덱스가 RPMB 같은 변조증거 저장소의 최소값보다 작으면 부팅을 거부하고, 성공 부팅 후 그 최소값을 앞으로만 올립니다. 핵심은 — 이미지의 인덱스는 그 빌드의 고정값이라 연속 빌드가 같은 값일 수 있고, 단조로 오르는 건 저장된 최소값이며, 월단위 다운그레이드 방지는 AVB가 아니라 KeyMint의 `os_patchlevel` 바인딩이 담당하고, `ROLLBACK_RESISTANCE`는 삭제 영속성 보장이라는 것입니다. 이로써 Tier 5(부팅·업데이트 체인)를 닫습니다. 다음은 남은 앱 통제(Tier 8)·연구(Tier 9)로 이어집니다.
