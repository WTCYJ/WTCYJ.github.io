---
layout: post
title: "Android Security Concept Atlas Tier 5 | 학습 로드맵 — 부팅·업데이트 체인"
date: 2026-08-29 23:30:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: learning-roadmap
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, Tier5, VerifiedBoot, AVB, 학습기록]
excerpt: "전원 첫 바이트부터의 신뢰 사슬입니다. Boot ROM이 부트로더를, 부트로더가 커널을(AVB), 각 단계가 다음을 검증하며, 롤백 방지가 '서명됐지만 낡은' 이미지를 막고, A/B·Treble·파티션 신뢰가 업데이트와 벤더 분리를 실현합니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier 5의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: `getprop ro.treble.enabled`, `getprop ro.apex.updatable`, `mount`, FBE 속성. Treble/APEX 활성화와 `/data`의 file-based encryption(`file`, `encrypted`)을 확인했다. 이 Google APIs AVD는 AVB 상태·A/B 슬롯 속성을 노출하지 않았다. 실제 하드웨어 롤백 퓨즈와 부트 ROM은 검증 범위 밖이다.

![Tier 5 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/evidence-boot.png)

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->






> **Concept Atlas · Tier 5 — 부팅·업데이트 체인 (Domain 2)**
> 6개 모듈 · 이 계층은 **전원부터의 신뢰 사슬**입니다.
> [← 마스터 인덱스](/posts/android-concept-atlas-index/) · [← Tier 4](/posts/android-concept-atlas-tier4-platform-isolation/) · 다음 → [Tier 6 Native·커널](/posts/android-concept-atlas-tier6-native-kernel/)

앱이 돌기도 전, 전원 첫 바이트부터 시작하는 신뢰 사슬입니다. Boot ROM→부트로더→커널→init(C27), 각 단계가 다음을 서명으로 검증(C28)하고, 낡은 이미지를 막고(C29), 무중단 업데이트(C30)와 벤더/프레임워크 분리(C31·C32)를 실현합니다.

## 모듈

| # | 개념 | 판정 | 상태 | 핵심 한 줄 |
|--|--|--|--|--|
| C27 | [Boot ROM·bootloader·boot.img·init](/posts/android-concept-atlas-c27-bootrom-bootloader-init/) | 🔴 | ✅ | PBL/XBL@EL3·vendor_boot·3단계 init — 신뢰 사슬의 시작점 |
| C28 | [AVB·vbmeta·dm-verity](/posts/android-concept-atlas-c28-verified-boot-avb/) | 🔴 | ✅ | 서명으로 진위 증명, dm-verity가 블록 단위로 무결성 강제 |
| C29 | [rollback protection·롤백 인덱스](/posts/android-concept-atlas-c29-rollback-protection/) | 🔴 | ✅ | '서명됐지만 낡은' 이미지 차단; RPMB에 저장된 최소 인덱스 |
| C30 | [A/B OTA·dynamic partitions·super.img](/posts/android-concept-atlas-c30-ab-ota-dynamic-partitions/) | 🔴 | ✅ | 무중단 업데이트; VirtualAB 의무(A13), 슬롯 성공 후 커밋 |
| C31 | [Treble·GSI·Mainline·APEX](/posts/android-concept-atlas-c31-treble-gsi-mainline-apex/) | 🔴 | ✅ | 벤더/프레임워크 분리 + 모듈식 업데이트(APEX) |
| C32 | [system/vendor/product/odm 신뢰관계](/posts/android-concept-atlas-c32-partition-trust/) | 🟡 | ✅ | 파티션별 신뢰·SELinux 라벨 분리 |

## 이 계층의 서사

C27이 전원 첫 바이트(EL3의 PBL)에서 신뢰 사슬을 시작하고, C28(AVB)이 각 단계의 서명 검증으로 그 사슬을 잇습니다 — 서명은 **진위**를 증명하고, C29의 롤백 인덱스는 그것이 **낡지 않았음**을 증명합니다(둘 다 통과해야). C30(A/B)은 업데이트를 무중단으로, C31·C32(Treble/파티션)는 벤더와 프레임워크를 분리해 각자 갱신·신뢰되게 합니다. 이 계층의 검증이 곧 하드웨어 신뢰 뿌리(Tier 7)와 만납니다.

---

**다음** → [Tier 6 — Native·커널](/posts/android-concept-atlas-tier6-native-kernel/) · [← Tier 4](/posts/android-concept-atlas-tier4-platform-isolation/) · [← 마스터 인덱스](/posts/android-concept-atlas-index/)
