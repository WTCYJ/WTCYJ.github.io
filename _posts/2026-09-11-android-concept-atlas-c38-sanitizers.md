---
layout: post
title: "Android Security Concept Atlas C38 | 가상 실습 보고서 — ASan·HWASan·KASAN·UBSan, 버그를 프로덕션 전에 잡는 탐지기들"
date: 2026-09-11 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ASan, HWASan, KASAN, UBSan, AddressSanitizer, MemorySafety, Fuzzing, IntSan, ConceptAtlas, 학습기록]
excerpt: "내가 퍼징으로 OOB를 잡을 때 크래시를 진단 가능한 리포트로 바꿔준 게 ASan이고, 미디어 코덱의 정수 언더플로→OOB 버그가 바로 이들이 겨냥하는 클래스입니다. ASan은 1/8 섀도 메모리 + 리드존(인접 오버플로) + 격리(UAF)로, HWASan은 arm64 TBI 상위바이트 태그로 같은 버그를 더 싼 메모리로, KASAN은 그걸 커널로 가져가 벤더 드라이버 버그를(C36) 잡습니다. 그런데 이건 전부 완화(장벽)가 아니라 탐지기입니다 - 테스트·퍼징에서 버그를 찾을 뿐, 유저 폰에 실리는 건 MTE·GWP-ASan·최소 IntSan뿐이죠. C37의 '탐지기 vs 장벽'을 도구 층위에서 마무리하는, Atlas의 스물네 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `uname -a`, `/proc/cpuinfo`, NDK JNI 빌드, UBSan 패치 전·후 실행 |
| 관측 결과 | Android 13 기반 Linux 5.15 x86_64 커널을 확인하고, NDK 27로 JNI 공유 라이브러리와 UBSan 대조군을 빌드·실행했다. |
| 검증 한계 | 범용 AVD에 없는 벤더 드라이버와 KASAN 커널은 실행하지 않았으며, 해당 항목은 공개 소스·설정 분석 결과로 구분한다. |

![C38 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C38 — ASan·HWASan·KASAN·UBSan
> **계층**: Tier 6 (Native·커널) · **난이도**: 고급 · **선수 개념**: C37(완화·MTE), C33(네이티브)
> **성격**: 보완 편.

C37에서 "메모리 안전은 **탐지기**(HWASan/KASAN/MTE)와 **장벽**(PAC/CFI 등)의 두 축"이라 했습니다. 이 모듈은 그 **탐지기 도구들**입니다 — 그리고 내가 퍼징(libFuzzer/AFL)과 VR에서 실제로 OOB를 잡을 때 쓴 바로 그 런타임입니다.

한 문장으로: **ASan·HWASan·KASAN·UBSan은 버그를 프로덕션 전에 테스트·퍼징에서 잡는 런타임 탐지기지, 배포 바이너리를 지키는 완화가 아니다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념 - 네 개의 새니타이저

- **ASan(AddressSanitizer)**: 유저스페이스. **1/8 섀도** + 리드존 + 격리.
- **HWASan**: arm64 **TBI 상위바이트 태그**. 섀도 ~1/16, 훨씬 싼 메모리. MTE의 소프트웨어 사촌.
- **KASAN**: ASan을 **커널**로. 벤더 드라이버 버그(C36)를 잡는 도구.
- **UBSan**: 정의되지 않은 동작(정수 오버플로·시프트·정렬…). 미디어의 **최소 IntSan**만 프로덕션 상시.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

C37의 "탐지기 vs 장벽" 이분법에서 **탐지기 쪽의 실제 도구들**입니다. 장벽(PAC/CFI/PAN)은 배포 바이너리에서 익스플로잇을 막고, 탐지기는 **버그가 트리거될 때 abort+진단**하여 출시 전에 잡습니다. 내 CVE 시리즈의 미디어 정수 언더플로→OOB(4·7편)와 BT 오버플로가 정확히 이들이 겨냥하는 클래스입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **ASan/HWASan**: 유저스페이스. **컴파일러 계측**(모든 로드/스토어에 검사 삽입) + **런타임**. 테스트/퍼징 빌드에서만.
- **KASAN**: **커널(EL1)**. `CONFIG_KASAN`.
- **UBSan**: 컴파일러 계측. 전체 UBSan은 개발용, **미디어의 최소 IntSan 서브셋만** 프로덕션에 상시.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **탐지기지 장벽이 아니다**: 유저 폰에는 ASan/HWASan/KASAN/full-UBSan이 **없습니다**. 프로덕션에 실리는 건 **MTE**(하드웨어 후계자)·**GWP-ASan**(샘플링)·**Scudo**·**최소 IntSan/BoundSan**뿐입니다(C37).
- **신뢰하면 안 되는 것들**:
  - **"ASan/HWASan은 프로덕션 완화"** — 아닙니다. ASan은 ~2–3배 CPU + 큰 RAM, 계측이라 배포 안 됩니다.
  - **"HWASan = MTE"** — HWASan은 **소프트웨어** 태깅(TBI, 8비트 태그, 16B 그래뉼, ~1/16 섀도). MTE는 **하드웨어**(4비트 태그, **Armv8.5-A FEAT_MTE2**). HWASan이 MTE를 예고할 뿐입니다.
  - **"ASan은 모든 OOB를 잡는다"** — 리드존(인접 오버플로)·격리(UAF)는 결정적이지만, **리드존을 건너뛰어 다른 유효 할당으로 점프하는 먼 오버플로는 놓칠 수 있습니다**. HWASan의 랜덤 태그는 그런 먼 오버플로·오래된 UAF를 **확률적(~255/256)**으로 잡습니다.
  - **"미디어 IntSan은 Android 8부터"** — **Android 7.0(Nougat, Stagefright 직후) 도입**, **9.0(Pie) 확장**입니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 소스 → 계측 컴파일(`-fsanitize=...`).
- **동작**: 런타임이 접근마다 **섀도**(ASan 1/8: `(Addr>>3)+offset`, 바이트값 `0`=8개 다 유효/`1..7`/음수=포이즌 종류)를 검사. HWASan은 포인터 태그 vs 섀도 태그.
- **출력**: 버그면 abort + 진단 리포트. **퍼징 하네스(libFuzzer)가 ASan 런타임 위에서** 메모리 오류를 크래시·축소 가능한 발견으로 바꿉니다 — 내 워크플로 그대로.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- 이들은 **취약점을 만드는 게 아니라 잡는** 도구입니다. 놓치면 = 버그가 출시로 새어나감.
- **탐지 대상**: heap/stack/global OOB, UAF, use-after-return/scope, double-free (ASan/HWASan/KASAN); 정수 오버플로·시프트·정렬·경계 (UBSan).
- **내 CVE와의 연결**: 미디어 코덱 정수 언더플로→OOB, BT 버퍼 오버플로가 바로 ASan(퍼징 하네스)·HWASan 디바이스 빌드가 런타임에 드러내려는 것이고, 프로덕션 **IntSan**이 정수 오버플로를 **조용한 wrap 대신 통제된 abort**로 바꿔 그 클래스를 무디게 합니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **HWASan 디바이스 이미지**: `aosp_<device>_hwasan` lunch, **Android 10(Q)**부터.
- **KASAN 모드**(커널 타임라인): generic(4.0)·SW_TAGS(5.4)·HW_TAGS(5.11, = 커널 MTE, FEAT_MTE2).
- **미디어 IntSan**: **7.0 도입 · 9.0 확장**(BoundSan/CFI 합류).
- **MTE**(C37): **Armv8.5-A FEAT_MTE2** — Pixel 8/Tensor G3가 마침 Armv9 코어일 뿐, MTE 자체는 Armv9 전용이 아닙니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 빌드: `Android.bp`의 `sanitize: {address:true}` / `{hwaddress:true}`, `-fsanitize=address|hwaddress|undefined`, 전체 시스템 ASan은 **`SANITIZE_TARGET=address`** 빌드 플래그(별도 `_asan` lunch 제품이 아님), HWASan은 `aosp_<device>_hwasan`.
- 커널: `CONFIG_KASAN`·`CONFIG_KASAN_SW_TAGS`·`CONFIG_KASAN_HW_TAGS` + **syzkaller** 퍼징.
- **소스**: `clang.llvm.org/docs/{AddressSanitizer,HardwareAssistedAddressSanitizerDesign}.html`, `source.android.com/docs/security/test/{hwasan,memory-safety}`.

**주의**: sanitizer는 계측해 빌드한 target에서만 동작합니다. 일반 release image에 자동으로 존재한다고 가정하지 말고, host-side harness 또는 sanitizer-enabled Cuttlefish/QEMU build를 사용합니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C37(완화·MTE)**: 탐지기(HWASan/KASAN)와 하드웨어 후계자(MTE)의 사다리 — 이 모듈이 그 탐지기 절반의 실체.
- **C36(벤더 드라이버)**: KASAN이 벤더 `.ko`의 OOB/UAF를 syzkaller로 잡는 도구.
- **C33(네이티브)**: 계측이 네이티브 코드에 붙습니다.
- **내 실측**: 퍼징(afl·libFuzzer)의 ASan 런타임, VR에서 ASan으로 확인한 OOB, CVE 4·7편의 정수결함 = IntSan 타겟.
- 다음은 다른 티어(토대 Tier 0–2 또는 앱통제 Tier 8)로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 새니타이저: 탐지기(테스트/퍼징) vs 프로덕션에 실리는 것 ]

  소스 ── -fsanitize=address ──▶ 계측 컴파일 + ASan 런타임
                                      │  접근마다 섀도(1/8) 검사
                                      │  리드존=인접 OOB / 격리=UAF
             libFuzzer ──────────────┘  → 크래시+진단 (내 퍼징)

  ASan(유저,1/8,리드존/격리) │ HWASan(TBI 태그,1/16) │ KASAN(커널,C36)
        └── 전부 "탐지기": 테스트/퍼징 전용, 폰에 안 실림 ──┘

  프로덕션에 실제 실리는 것:  MTE(HW 4bit, Armv8.5) · GWP-ASan(샘플)
                              · Scudo · 최소 IntSan(미디어, A7.0+)
```

## 오개념 판별 문제 5개

1. "ASan은 배포 바이너리를 익스플로잇에서 지키는 프로덕션 완화다."
2. "HWASan과 MTE는 같은 것이다."
3. "ASan은 모든 out-of-bounds 접근을 반드시 잡는다."
4. "미디어의 프로덕션 정수 오버플로 새니타이즈는 Android 8부터 실렸다."
5. "KASAN HW_TAGS는 Armv9 전용 기능이다."

<details><summary>판정 기준(펼치기)</summary>

1. **탐지기**입니다. ~2–3배 CPU + 큰 RAM의 계측이라 배포 안 됩니다. 프로덕션 완화는 MTE·GWP-ASan·Scudo·최소 IntSan뿐.
2. HWASan은 **소프트웨어** TBI 태깅(8비트, 16B, ~1/16 섀도), MTE는 **하드웨어**(4비트, Armv8.5-A FEAT_MTE2). HWASan이 MTE를 예고할 뿐.
3. 리드존(인접)·격리(UAF)는 결정적이지만 **먼 오버플로는 놓칠 수 있습니다**. HWASan의 랜덤 태그가 그걸 확률적(~255/256)으로 보완.
4. **Android 7.0(Stagefright 직후) 도입**, 9.0 확장입니다.
5. **Armv8.5-A FEAT_MTE2**입니다. 실기 실리콘이 Armv9 코어일 뿐 MTE는 Armv9 전용이 아닙니다.
</details>

## 서술형 문제 3개

1. ASan의 리드존(인접 OOB)과 격리(UAF)가 각각 어떤 버그 클래스를 결정적으로 잡는지, 그리고 왜 먼 오버플로는 놓칠 수 있는지 서술하세요.
2. HWASan이 TBI 상위바이트 태그로 어떻게 ASan보다 싼 메모리로 전체 디바이스 계측을 가능케 하고, 왜 탐지가 확률적인지 서술하세요.
3. "탐지기 vs 프로덕션 완화" 구분에서, 유저 폰에 실제로 실리는 것(MTE/GWP-ASan/Scudo/IntSan)과 실리지 않는 것(ASan/HWASan/KASAN)을 C37과 일관되게 서술하세요.

## 소스·정적 검증 경로

- 네 퍼징 하네스(libFuzzer/AFL) 하나를 `-fsanitize=address`로 빌드해 ASan 리포트의 리드존/격리 메시지를 캡처하세요.
- 그 OOB/UAF가 리드존형인지 UAF형인지 리포트로 판정하고, HWASan(`-fsanitize=hwaddress`)에서 같은 버그의 태그-불일치 리포트와 대조하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 리포트·화면만** 붙입니다.

1. **ASan 실측**: 내 CVE 4·7편 재현 하네스를 ASan으로 돌려 리포트를 캡처.
2. **버그 클래스 판정**: 리드존/격리/태그-불일치로 OOB vs UAF를 근거와 함께.
3. **탐지 vs 완화 서술**: 같은 버그가 프로덕션 IntSan(A7.0+)이면 abort로, MTE면 태그체크로 어떻게 달라지는지.
4. **연결**: C36 벤더 드라이버 버그를 KASAN+syzkaller로 잡는 그림.

각 단계는 실제 새니타이저 리포트·스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

ASan·HWASan·KASAN·UBSan은 C37의 "탐지기" 절반의 실체입니다 — 1/8 섀도 + 리드존/격리(ASan), TBI 상위바이트 태그(HWASan), 커널판(KASAN), 정의되지 않은 동작(UBSan). 넷 다 **버그를 테스트·퍼징에서 잡는 런타임 탐지기지 배포 바이너리를 지키는 장벽이 아닙니다**: 유저 폰에는 MTE·GWP-ASan·Scudo·최소 IntSan(미디어, A7.0+)만 실립니다. 그리고 이 도구들이 겨냥하는 정수 오버플로→OOB·UAF가 바로 내 CVE 시리즈와 퍼징 작업이 다뤄온 클래스입니다 — Atlas가 여기서 내 실측과 만납니다. 이로써 Tier 6(Native·커널)를 닫고, 다음 파도는 다른 티어로 넘어갑니다.
