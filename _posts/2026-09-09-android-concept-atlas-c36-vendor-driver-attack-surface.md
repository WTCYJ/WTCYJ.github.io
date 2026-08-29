---
layout: post
title: "Android Security Concept Atlas C36 | 가상 실습 보고서 — 벤더 드라이버·HAL 공격 표면, EL0에서 EL1로 가는 다리"
date: 2026-09-09 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, VendorDriver, GPU, MaliKbase, KGSL, Adreno, KernelLPE, PatchGap, MindTheGap, baseband, ConceptAtlas, 학습기록]
excerpt: "제 CVE 시리즈의 미디어·블루투스 버그는 EL0에서 멈췄습니다. 그것을 커널 장악으로 올리는 두 번째 단계가 벤더 드라이버 LPE입니다. Android 커널 익스플로잇의 대다수는 코어 커널이 아니라 SoC/OEM의 out-of-tree 드라이버 - 특히 GPU - 에서 나옵니다. 렌더링 때문에 평범한 앱조차 GPU 노드를 열 수 있어서, 샌드박스와 거대한 복잡한 커널 드라이버 사이에 아무 권한 게이트가 없기 때문입니다. 그리고 그 수정은 SoC 벤더→OEM을 거쳐 느리게 오는 '패치 갭'에 걸립니다. Treble/GKI가 플랫폼은 분리했지만 벤더 드라이버 전달은 고치지 못한 그 지점입니다. Concept Atlas의 스물두 번째 모듈입니다."
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

![C36 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C36 — vendor driver·HAL 공격 표면
> **계층**: Tier 6 (Native·커널) · **난이도**: 연구 · **선수 개념**: C34(ioctl), C20(HAL), C32(벤더 파티션), C05(EL0→EL1)
> **성격**: 공식 문서·공개 소스 기준 재검토. 내 CVE 시리즈의 "EL0 버그 → 커널 장악"의 그 EL1 단계.

제 CVE 시리즈의 미디어(4·7편)·블루투스(8편) 버그는 EL0에서 멈췄습니다 — 샌드박스된 유저스페이스 프로세스 안이지 커널이 아니었습니다(C37). 그것을 **커널 장악으로 올리는 두 번째 단계**가 이 모듈입니다.

한 문장으로: **Android 커널 익스플로잇의 대다수는 코어 커널이 아니라 SoC/OEM의 out-of-tree 벤더 드라이버 — 특히 GPU — 에서 나오고, 렌더링 때문에 평범한 앱이 GPU 노드를 열 수 있어 샌드박스와 커널 사이에 권한 게이트가 없다.** 공식 문서와 공개 소스를 기준으로 핵심 경계를 정리합니다.

## 배경 개념 - 벤더 코드가 곧 공격 표면

- **벤더 드라이버**: SoC/OEM의 **out-of-tree 커널 드라이버**(GPU·디스플레이·카메라 ISP·모뎀·센서·전력). EL1에서 돌고 ioctl(C34)로 닿음.
- **벤더 HAL**: 유저스페이스 데몬. 프레임워크 요청을 Binder/HIDL/AIDL(C20)로 파싱한 뒤 드라이버를 몲.
- **패치 갭**: 벤더 수정이 SoC벤더→OEM→캐리어로 Google Mainline보다 느리게 오는 간극.
- **GPU 드라이버**: Arm Mali `kbase`(`/dev/mali0`), Qualcomm Adreno **KGSL**(`/dev/kgsl-3d0`).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**Android 최대 실전 LPE 공격 표면**입니다. C32의 벤더 파티션 코드가 커널/HAL로 실행되고, C34의 ioctl·C20의 HAL이 그 진입 경로입니다. 그리고 이것이 제 CVE 시리즈의 **EL0→EL1(C05) 상승 자리**입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

표면은 **두 층**이고 둘 다 앱이 닿습니다.

1. **유저스페이스 벤더 HAL(C20)**: 프레임워크/앱 요청(Parcel, C18)을 파싱하는 binder 서비스. 자기 SELinux 도메인에 갇히지만 종종 특권적이고 하드웨어를 몲.
2. **커널 벤더 드라이버(C34, EL1)**: HAL이 ioctl로 모는(또는 일부 노드는 앱이 직접 여는) 커널 코드.

가치 있는 체인은 **앱/HAL → ioctl → 커널 드라이버 LPE**입니다. HAL 버그만으로는 그 도메인 권한이지만, 커널 드라이버 LPE가 EL1(커널)을 줍니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **벤더 코드는 코어 커널이 아닙니다.** mainline보다 훨씬 덜 검토되고, 기기별로 무수하며, per-SoC로 배포됩니다. 그래서 Android 커널 LPE의 **대다수가 벤더 드라이버 버그**이지 코어 커널 버그가 아닙니다.
- **GPU는 의도적 예외입니다.** 렌더링/EGL/Vulkan 때문에 `untrusted_app` 도메인이 GPU 노드(`gpu_device`)를 열도록 허용됩니다 — 대부분의 드라이버 노드는 앱이 못 여는데, GPU만은 **샌드박스와 거대한 복잡한 커널 드라이버 사이에 아무 권한 게이트가 없습니다.**
- **신뢰하면 안 되는 것들**:
  - **"mainline 하드닝이 벤더 버그를 막는다"** — 버그는 벤더 out-of-tree에 삽니다.
  - **"HAL RCE = 커널 RCE"** — HAL은 자기 도메인, 커널은 별개의 상승 단계입니다.
  - **"`isolated_app`(브라우저 렌더러)도 GPU를 연다"** — **아닙니다.** `untrusted_app`(과 Chrome의 별도 GPU 프로세스)만. `isolated_app`은 최대로 잠겨 있어, Chrome은 GPU 작업을 별도 GPU 프로세스로 브로커합니다.
  - **"모뎀/baseband가 주 앱-LPE 표면"** — baseband는 **별도 프로세서의 원격(OTA/RIL) 표면**이지 앱 도달 EL1 경로가 아닙니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 앱/프레임워크의 요청 → 벤더 HAL이 파싱 → 커널 드라이버를 ioctl로.
- **출력**: 하드웨어 동작(렌더링 등), 그리고 실패 시 **커널 메모리 손상**.
- **주 노드**: `/dev/mali0`(Arm Mali kbase), `/dev/kgsl-3d0`(Qualcomm Adreno KGSL).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**벤더 드라이버 LPE가 EL0→EL1(C05)입니다.** GPU 드라이버의 반복 버그 클래스:

- **CPU↔GPU 공유 메모리 / JIT 할당 관리**(페이지 매핑·권한 혼동),
- **객체 수명 use-after-free**.

**실제 in-the-wild** 체인(브라우저/렌더러 → GPU 커널 → root):

- **CVE-2023-4211**(Arm Mali UAF, 표적 악용, Google TAG),
- **CVE-2023-26083**(Mali, 삼성 기기 대상 상용 스파이웨어 체인),
- **CVE-2022-22706**(Mali 접근 단위, CISA KEV),
- **CVE-2022-38181**(Mali kbase UAF, GitHub Security Lab의 Man Yue Mo 보고(GHSL-2022-054), 악용 확인·CISA KEV),
- **CVE-2023-33106 / CVE-2023-33107**(Qualcomm **KGSL**의 2023-10 in-the-wild — 각각 `IOCTL_KGSL_GPU_AUX_COMMAND` OOB write, KGSL 정수 오버플로).

**패치 갭**이 벤더 특유의 킬러입니다: 수정이 SoC벤더→OEM→캐리어로, Google의 Mainline/Play 시스템 업데이트보다 느린 별도 트랙을 탑니다. Project Zero의 **"Mind the Gap"**(2022-11)이 Arm Mali 수정(**CVE-2022-33917 / CVE-2022-36449**)이 Arm에서 몇 달 먼저 고쳐지고도 기기엔 늦게 온 **노출 창**을 문서화했습니다(단 이 둘은 Project Zero가 직접 찾은 것으로, in-the-wild 악용이 확인된 건 아닙니다). **Treble/GKI(C31)는 플랫폼 패치만 분리하지, 벤더 드라이버 전달은 고치지 않습니다.**

제 CVE 시리즈의 호선이 여기서 완성됩니다: **미디어/BT의 EL0 발판(진입) → GPU/벤더 드라이버 LPE(피벗) → EL1(커널 장악)**.

## 질문 6 — Android 버전/기법에 따라 무엇이 달라졌는가

완화 방향은 수렴합니다:

- **도달성 축소**: SELinux ioctl 명령 필터링(`allowxperm`/`neverallowxperm`, C23/C34), zygote/앱 **seccomp-bpf** syscall 필터.
- **GKI + 안정 KMI(C35)**: 커널/벤더-모듈 경계를 안정화·축소(단 GPU 등 벤더 모듈은 여전히 벤더 배포·벤더 패치).
- **EL1 밖으로**: 드라이버 로직의 **하드웨어 격리(pKVM/protected-KVM, Microdroid식)** — "드라이버를 유저스페이스 HAL로 옮긴다"가 아니라(HAL은 원래 유저스페이스이고 여전히 ioctl로 커널을 몲), EL1 자체를 벗어나게 하는 것.
- **하드웨어 메모리 안전**: **MTE(C37)**가 GPU의 UAF/OOB 클래스를 EL1에서 잡고, CFI/PAC/BTI, 그리고 신규 드라이버/HAL의 **Rust**.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ls -Z /dev`로 GPU 노드가 `gpu_device`로 라벨되고 `untrusted_app`이 접근 가능함을(sepolicy) 확인. `lsof`로 어느 프로세스가 GPU fd를 쥐는지.
- **Android Security Bulletin**의 "Arm components"·"Qualcomm components / Qualcomm closed-source components" 절 — 벤더 드라이버 CVE와 in-the-wild 악용 플래그의 1차 기록.
- **Project Zero "Mind the Gap"**(2022-11), TAG의 스파이웨어 체인 보고.
- **소스**: 벤더 GPU KMD(kbase/KGSL, 대개 out-of-tree), `source.android.com` 벤더 보안 문서.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C34(ioctl)**: 벤더 드라이버로 닿는 채널.
- **C20(HAL)**: 유저스페이스 첫 번째 층(프레임워크 요청 파서).
- **C32(벤더 파티션)**: 벤더가 왜 큰 공격 표면인지의 신뢰 지도.
- **C05(EL)**: EL0→EL1 상승.
- **C31(GKI·패치갭)**: Treble/GKI가 무엇을 고치고(플랫폼) 무엇을 못 고치는지(벤더 드라이버 전달).
- **C37(완화)**: MTE·CFI·Rust가 이 표면을 좁힙니다.
- **CVE 시리즈**: EL0 버그의 EL1 상승 자리.
- 다음은 **C35(GKI·KMI)** 또는 **C38(새니타이저)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 앱에서 커널까지 — 두 층, 그리고 EL0→EL1 ]

앱(EL0, untrusted_app)
   │ (a) 프레임워크 요청 → 벤더 HAL(유저스페이스, C20)  ── HAL 버그면 그 도메인 권한
   │ (b) 또는 GPU 노드 직접 open (렌더링 때문에 허용)
   ▼
ioctl(/dev/mali0 또는 /dev/kgsl-3d0)  (C34)
   ▼
GPU 커널 드라이버(EL1): 공유메모리/JIT 페이지·권한 혼동 / 객체 UAF
   ▼
   EL0→EL1 커널 LPE (C05)  ← CVE 시리즈 EL0 발판의 피벗

[ 패치 갭 ]
Arm/Qualcomm 수정 ──(몇 달)──▶ SoC 벤더 ──▶ OEM ──▶ 기기
  (Google Mainline/Play 는 플랫폼만 빠르게; 벤더 드라이버는 이 느린 트랙)
```

## 오개념 판별 문제 5개

1. "Linux mainline 커널을 하드닝하면 Android 커널 LPE의 대다수가 막힌다."
2. "벤더 HAL에서 코드 실행을 얻으면 곧 커널(EL1)을 장악한 것이다."
3. "브라우저의 격리된 렌더러(`isolated_app`)가 GPU 드라이버를 직접 공격한다."
4. "모뎀/baseband가 앱이 도달하는 주 커널 LPE 표면이다."
5. "벤더 드라이버 LPE를 없애려면 드라이버를 유저스페이스 HAL로 옮기면 된다."

<details><summary>판정 기준(펼치기)</summary>

1. 버그는 코어 커널이 아니라 **벤더 out-of-tree 드라이버**(특히 GPU)에 삽니다. mainline 하드닝은 그곳을 거의 안 건드립니다.
2. HAL 침해는 그 HAL의 SELinux 도메인 권한입니다. EL1은 그 뒤 **커널 드라이버 LPE**라는 별개 단계입니다.
3. `isolated_app`은 최대로 잠겨 GPU 노드를 **못 엽니다**. GPU를 여는 건 `untrusted_app`(과 별도 GPU 프로세스)입니다 — Chrome은 렌더러의 GPU 작업을 GPU 프로세스로 브로커합니다.
4. baseband는 **별도 프로세서의 원격(OTA/RIL) 표면**입니다. 앱 도달 EL1 경로의 아웃라이어는 **GPU**입니다.
5. HAL은 원래 유저스페이스이고 여전히 ioctl로 커널 드라이버를 몹니다 — 커널 드라이버를 HAL로 바꿀 순 없습니다. EL1을 벗어나는 진짜 방향은 **하드웨어 격리(pKVM)**입니다.
</details>

## 서술형 문제 3개

1. 왜 Android 커널 LPE의 대다수가 코어 커널이 아니라 벤더 드라이버에서 나오는지(검토·수·패치 트랙)를 서술하세요.
2. GPU 드라이버가 왜 유독 앱 도달 가능한 EL0→EL1 표적인지(렌더링·`untrusted_app` 접근·복잡도)와, 두 층(HAL/드라이버)의 차이를 서술하세요.
3. "패치 갭"이 왜 벤더 특유인지, Treble/GKI가 무엇을 고치고 무엇을 못 고치는지, 그리고 그것이 제 CVE 시리즈의 EL0→EL1 서사와 어떻게 맞물리는지 서술하세요.

## 소스·정적 검증 경로

- Cuttlefish/QEMU가 제공하는 가상 device node와 SELinux label을 `ls -Z /dev`로 확인하고, 공개 AOSP/vendor kernel source의 device node 및 sepolicy 선언과 비교하세요. `/dev/mali0`·`/dev/kgsl-3d0`가 존재한다고 가정하지 않습니다.
- 최근 몇 달치 **Android Security Bulletin**에서 "Arm/Qualcomm components" 절을 열어 벤더 드라이버 CVE 비율과 in-the-wild 악용 플래그를 세어 보세요(스크립트로 집계 — 제 24주 교훈: 집계는 스크립트가).
- Project Zero "Mind the Gap"에서 패치 갭의 구체 사례(CVE-2022-33917/36449)를 확인하세요.

## 추가 심화 재현 절차

이 모듈을 **실측/조사 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 출력·화면만** 붙입니다.

1. **노드 접근 실측**: `ls -Z /dev` GPU 노드와 sepolicy로 `untrusted_app` 접근을 캡처.
2. **불리틴 집계**: 최근 ASB의 Arm/Qualcomm 절 CVE를 스크립트로 집계해 "벤더 드라이버가 대다수"를 근거로.
3. **패치 갭 서술**: "Mind the Gap"과 이 기기의 벤더 SPL을 대조.
4. **시리즈 연결**: 내 미디어/BT EL0 버그(4·7·8편)를 이 GPU/벤더 드라이버 EL1 단계와 하나의 체인으로 서술.

각 단계는 명령 출력·실제 스크린샷/집계로만 증적화하고, 미확인·추정 항목은 "못 한 것/추정"으로 분리하세요.

## 마치며

제 CVE 시리즈의 미디어·블루투스 버그는 EL0에서 멈췄습니다. 그것을 커널 장악으로 올리는 두 번째 단계가 벤더 드라이버 LPE이고, Android 커널 익스플로잇의 대다수는 코어 커널이 아니라 SoC/OEM의 out-of-tree 드라이버 — 특히 GPU — 에서 나옵니다. 렌더링 때문에 평범한 앱이 GPU 노드를 열 수 있어 샌드박스와 커널 사이에 권한 게이트가 없고(그래서 Mali kbase·Qualcomm KGSL의 in-the-wild 0-day가 이어지고), 그 수정은 SoC 벤더를 거쳐 느리게 오는 패치 갭에 걸립니다. Treble/GKI가 플랫폼은 분리했지만 벤더 드라이버 전달은 고치지 못한 그 지점입니다. 완화의 진짜 방향은 도달성 축소(ioctl 필터·seccomp)와 EL1 밖 하드웨어 격리(pKVM), 그리고 MTE·Rust입니다. 다음은 그 커널 표면을 줄이는 **C35(GKI·KMI)**, 또는 버그를 잡는 **C38(새니타이저)**로 이어집니다.
