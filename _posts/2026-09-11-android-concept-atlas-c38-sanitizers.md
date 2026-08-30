---
layout: post
title: "Android Security Concept Atlas C38 | 가상 실습 보고서 — ASan·HWASan·KASAN·UBSan, 버그를 프로덕션 전에 잡는 탐지기들"
date: 2026-09-11 21:00:00 +0900
category: 안드로이드
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

## 호출 흐름

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

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 이 모듈의 주장 가운데 유저스페이스 계측으로 확인 가능한 부분을 실제 빌드·실행으로 검증했다. 상단 검증 블록의 `실행 명령·코드`(`uname -a`, `/proc/cpuinfo`, NDK JNI 빌드, UBSan 패치 전·후 실행)와 `관측 결과`(Android 13 기반 Linux 5.15 x86_64 커널 확인, NDK 27로 JNI 공유 라이브러리와 UBSan 대조군 빌드·실행)가 근거다.

**1) 새니타이저 계측은 배포 이미지가 아니라 컴파일러가 계측한 target에만 붙는다(질문 2·7·8/C33).** UBSan 대조군은 일반 release 이미지에서 나온 게 아니라, NDK 27 툴체인으로 `-fsanitize` 계측 빌드를 새로 만들어 실행한 것이다. 이 빌드 과정 자체가 질문 7의 주의사항 — "sanitizer는 계측해 빌드한 target에서만 동작하며 일반 release image에 자동으로 존재한다고 가정하지 말라" — 를 그대로 보여준다. 유저 폰의 release 바이너리에는 이 런타임이 없다(질문 3).

**2) UBSan은 정의되지 않은 동작을 겨냥하는 탐지기다(질문 4·5).** NDK 27로 JNI 공유 라이브러리를 빌드하고, 같은 코드에 UBSan을 계측한 대조군을 패치 전·후로 나눠 빌드·실행했다. 결함을 그대로 둔 빌드와 고친 빌드를 나눠 돌리는 이 대조 구성이, UBSan이 정의되지 않은 동작(정수 오버플로·시프트·정렬)을 런타임에 드러내는 탐지기임을 확인하는 절차다 — 질문 5의 "IntSan이 정수 오버플로를 조용한 wrap 대신 통제된 abort로 바꾼다"가 이 대조군이 겨냥한 불변식이고, 프로덕션 미디어의 최소 IntSan(A7.0+)이 상시로 남기는 것도 바로 이 abort 동작이다.

**3) AVD 커널 세대와 적재 모듈을 실측했다 — KASAN 모드 타임라인과 맞물린다(질문 6).** `uname -a`로 커널 세대를, `lsmod`로 적재 모듈 전체를 실측했다.

```console
$ uname -a
Linux ... 5.15.119-android13-8-00034-gd34029c8258b-ab10871489 #1 SMP PREEMPT Wed Sep 27 18:42:24 UTC 2023 x86_64
$ lsmod
Module                  Size  Used by
zram                   24576  2
zsmalloc               24576  1 zram
virtio_snd             28672  0
virtio_net             53248  0
virtio_input           20480  0
virtio_balloon         28672  0
# (총 53개 — zram/zsmalloc + virtio 계열, 벤더 .ko 없음)
```

질문 6의 KASAN 타임라인(generic 4.0 · SW_TAGS 5.4 · HW_TAGS 5.11)에 비추면 5.15.119 커널은 세 KASAN 모드를 모두 담을 수 있는 세대다. 적재 모듈은 zram/zsmalloc과 virtio 계열 53개로 전부 확인했고, C36이 말한 벤더 `.ko`는 이 범용 AVD 이미지에 실려 있지 않다 — 그래서 `CONFIG_KASAN` 커널 리포트는 커널 소스로 확정한다(아래 "소스로 확정한 것").

## 소스로 확정한 것

유저스페이스 UBSan 대조군과 커널 세대·적재 모듈은 위에서 실측했고, 아키텍처·하드웨어에 매인 나머지 런타임 동작은 공식 소스로 확정한다.

- **ASan/HWASan의 리드존·격리·태그-불일치 리포트는 clang 소스로 확정한다.** `-fsanitize=address`/`hwaddress` 런타임이 인접 오버플로를 리드존으로, UAF를 격리로, 태그 불일치를 상위바이트 태그 비교로 abort시키는 동작은 [Clang AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html)와 [HardwareAssistedAddressSanitizerDesign](https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html)에 규정돼 있다. 이 세션에서 실측한 건 "계측한 target에만 붙는다"(질문 7)는 성질을 [Clang UndefinedBehaviorSanitizer](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) 계열 UBSan 대조군으로 직접 확인한 부분이다.

- **HWASan의 TBI 상위바이트 태깅과 MTE의 하드웨어 4비트 태그는 arm64 런타임이라 ARM·AOSP 소스로 확정한다 — 단 arm64 정적 마커는 실측했다.** arm64 바이너리의 기능 마커는 이 호스트에서 실제로 빌드해 뽑을 수 있다. 실제 arm64 `.so`를 빌드해 `readelf`로 ELF 헤더 Machine과 `.note.gnu.property`를 확인했고, `-mbranch-protection=none` 대조 빌드는 그 note가 0개였다(정적 마커 = 실측).

```console
$ readelf -h libarm64.so | grep Machine
  Machine:                           AArch64
$ readelf -n libarm64.so
Displaying notes found in: .note.gnu.property
  GNU                  0x00000010  NT_GNU_PROPERTY_TYPE_0 (property note)
    Properties:    aarch64 feature: BTI, PAC
# 대조군(-mbranch-protection=none): .note.gnu.property 기능 note 매치 0
```

  정적 마커는 이렇게 실측되지만, HWASan의 TBI(상위바이트 8비트 태그, ~1/16 섀도)와 MTE의 하드웨어 태그 검사(Armv8.5-A FEAT_MTE2)는 실행 시점 동작이라 [source.android.com HWASan](https://source.android.com/docs/security/test/hwasan)·[Android 메모리 안전(MTE)](https://source.android.com/docs/security/test/memory-safety)로 확정한다. `aosp_<device>_hwasan`(Android 10+) 디바이스 이미지의 계측 경로도 같은 문서 계열이 규정한다.

- **KASAN 커널 리포트와 syzkaller 커널 퍼징은 커널 소스로 확정한다.** 위 실측대로 이 AVD 커널은 5.15.119-android13 세대이고 적재 모듈은 virtio/zram 계열 53개뿐이라 C36의 벤더 `.ko`가 없다. 그래서 `CONFIG_KASAN`·`CONFIG_KASAN_SW_TAGS`·`CONFIG_KASAN_HW_TAGS`가 커널 OOB/UAF를 abort로 바꾸는 동작과 syzkaller 퍼징 경로는 [Kernel KASAN 문서](https://www.kernel.org/doc/html/latest/dev-tools/kasan.html)로 확정한다. 동작하는 커널 익스플로잇 재현은 이 시리즈의 **비무기화 범위** 밖이라 판정 지점까지만 다룬다.

## 마치며

ASan·HWASan·KASAN·UBSan은 C37의 "탐지기" 절반의 실체입니다 — 1/8 섀도 + 리드존/격리(ASan), TBI 상위바이트 태그(HWASan), 커널판(KASAN), 정의되지 않은 동작(UBSan). 넷 다 **버그를 테스트·퍼징에서 잡는 런타임 탐지기지 배포 바이너리를 지키는 장벽이 아닙니다**: 유저 폰에는 MTE·GWP-ASan·Scudo·최소 IntSan(미디어, A7.0+)만 실립니다. 그리고 이 도구들이 겨냥하는 정수 오버플로→OOB·UAF가 바로 내 CVE 시리즈와 퍼징 작업이 다뤄온 클래스입니다 — Atlas가 여기서 내 실측과 만납니다. 이로써 Tier 6(Native·커널)를 닫고, 다음 파도는 다른 티어로 넘어갑니다.
