---
layout: post
title: "Android Security Concept Atlas C16 | 가상 실습 보고서 — JIT/AOT와 분석 결과 차이, 정적으로 보이는 것 ≠ 실제 실행"
date: 2026-09-21 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ART, JIT, AOT, Interpreter, ArtMethod, Deoptimization, Frida, ConceptAtlas, 학습기록]
excerpt: "같은 메서드가 인터프리트로도, JIT 네이티브로도, AOT 네이티브로도 돕니다 - 실행 형태는 고정된 속성이 아니라 런타임 상태죠. 중요한 건 세 모드가 같은 DEX의 컴파일이라 의미가 동일하다는 것: 두 실행의 행동 차이가 'JIT됐기 때문'인 경우는 없습니다. 그래서 로직은 DEX 정적 분석으로 완전하고, '정적으로 보이는 것 ≠ 실제 실행'의 진짜 원인은 JIT/AOT가 아니라 동적 코드 로딩(C14)·리플렉션·JNI(C15)입니다. 계측의 함정도 여기 있어요: ArtMethod 엔트리포인트를 갈아끼우는 것만으론 부족합니다 - 인라인된 호출은 엔트리포인트를 안 읽으니까요. 그래서 견고한 후킹은 deopt로 인터프리터로 되돌립니다. 내 패커 RE 방법론의 뼈대이자 Tier 2를 닫는 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `getprop ro.zygote`, `getprop dalvik.vm.usejit`, `ps` |
| 관측 결과 | `zygote64`와 JIT 활성 상태를 확인했다. 비특권 앱의 전체 프로세스 열람 제한도 함께 관측했다. |
| 검증 한계 | OAT/VDEX 생성 정책은 빌드와 프로파일 상태에 따라 달라지므로 이 한 번의 캡처를 모든 Android 버전에 일반화하지 않는다. |

![C16 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-runtime.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C16 — JIT/AOT와 분석 결과 차이
> **계층**: Tier 2 (Android Runtime) · **난이도**: 중급 · **선수 개념**: C13(ART), C14(DCL)
> **성격**: 보완 편.

C13에서 DEX가 인터프리트/JIT/AOT로 컴파일된다 했습니다. 그 **실행 형태의 변화가 분석·계측에 무슨 차이를 주는가**, 그리고 흔한 오해와 달리 그게 왜 로직 분석을 안 바꾸는가가 이 편입니다.

한 문장으로: **세 실행 모드는 같은 DEX의 컴파일이라 의미가 동일하고, "정적≠실행"의 진짜 원인은 JIT/AOT가 아니라 DCL·리플렉션·JNI다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **세 모드**: 인터프리트 / JIT(런타임 네이티브, 인프로세스 캐시) / AOT(OAT 네이티브, C13).
- **런타임 상태**: 한 메서드가 시간에 따라 모드를 바꿈(인터프리트→핫하면 JIT→백그라운드 AOT).
- **의미 동일**: JIT/AOT는 같은 DEX의 충실한 하강 — 행동을 안 바꿈.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

C13의 컴파일 모드가 **분석·계측에 주는 차이**입니다. C14(DCL)·C15(JNI)와 함께 "정적으로 보이는 것 ≠ 실제 실행"을 이루고, 내 패커 리버싱 방법론의 뼈대입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **세 모드**(앱 프로세스, EL0 내):
  - 인터프리트: ART 인터프리터가 DEX 바이트코드를 순회(컴파일 전·콜드·deopt 후). **A12+ 기본은 nterp**(런타임 생성 어셈블리 인터프리터, C++ 스위치 아님).
  - JIT: 핫해지면 인프로세스 **JIT 코드 캐시**의 네이티브로(프로필에도 기록).
  - AOT: dex2oat가 OAT/.odex에 미리 컴파일(부트이미지 또는 speed/speed-profile).
- **전환**: 호출은 `ArtMethod`의 엔트리포인트(`entry_point_from_quick_compiled_code_`)를 통해 디스패치되고, ART가 이 포인터를 인터프리터 브리지↔컴파일 코드로 바꿈.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **세 모드는 의미 동일**: 같은 DEX의 컴파일/실행이라 **행동이 같습니다**(성능·기계 형태만 다름). 두 실행의 행동 차이가 "JIT/AOT됐기 때문"인 경우는 없습니다 → 로직은 DEX 레벨로 추론 가능.
- **신뢰하면 안 되는 것들**:
  - **"JIT/AOT 컴파일이 코드 동작을 바꾼다"** — 아닙니다(의미 보존 하강).
  - **"OAT 네이티브를 분석해야 로직을 안다"** — DEX가 원천, OAT는 파생(C13). 로직은 **모든 shipped DEX**(멀티덱스·split 포함) 정적 분석으로 완전.
  - **"'정적≠실행'은 JIT/AOT 탓"** — 아닙니다. 진짜 원인은 **DCL/패커**(C14, shipped dex가 stub)·**리플렉션**·**JNI**(C15, .so는 DEX 밖).
  - **"ArtMethod 엔트리포인트만 갈아끼우면 모드 무관 후킹"** — **부족**합니다. AOT/JIT가 콜리를 **인라인**하면 그 호출부는 엔트리포인트를 안 읽습니다. **견고한 후킹은 deopt(역최적화)를 강제**해 인터프리터로 되돌립니다 — 그게 진짜 모드 독립성의 보증. (참고: `kAccCompileDontBother`는 미래 재컴파일만 막지 deopt가 아님.)

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: DEX. **실행 형태**는 런타임 상태(인터프리트→JIT→백그라운드 AOT, C13의 프로필 유도 파이프라인 — JIT가 프로필을 먹여 AOT로).
- **계측**: `ArtMethod` 조작(엔트리포인트 리다이렉트) + **deopt**(전체/선택적 단일 메서드)로 인터프리터에서 훅이 확실히 걸리게. JDWP 디버깅·Frida가 이에 의존.

## 질문 5 — 실패하면 어떤 취약점으로/분석에 어떤 함의가

- **로직 분석은 DEX로 완전**: OAT를 역공학할 필요 없음(같은 의미, 읽기만 어려움) — 인라인 훅을 놓을 때만 네이티브 형태를 봄.
- **진짜 괴리는 DCL/패커·리플렉션·JNI**: packed 앱은 shipped DEX가 실행 코드를 과소표현 → 런타임 로드 dex를 덤프해야(OAT vs DEX 비교로는 같은 stub만 재도출).
- **네이티브 인라인 훅은 모드별로 깨짐**: AOT 코드에 놓은 인라인 패치는 그 메서드가 인터프리트로 돌면 무효 → **ART 레벨 훅+deopt**가 모드 질문을 우회.
- **JIT 코드 캐시는 인프로세스·비영속**: 라이브 프로세스 메모리 스캔이 정적 산출물에 없는 JIT 네이티브를 드러냄.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **하이브리드 JIT+AOT**(프로필 유도): A7.0/API24. 이전(A5.0)은 설치 시 완전 AOT·JIT 없음, Dalvik(pre-5.0)은 트레이스 JIT·OAT 없음.
- **nterp**(새 기본 인터프리터): A12.
- **베이스라인 프로필**(Play/Cloud) 선컴파일: A9+/Jetpack(7+).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `dumpsys package <pkg>`(현재 컴파일 필터=얼마나 AOT인지), `oatdump`(OAT 네이티브).
- Frida `Java.use`/`Java.perform`(ArtMethod 레벨 훅, 필요시 deopt), `/proc/<pid>/maps`(JIT/익명 실행 영역), 복호 후 메모리 dex 덤프(C14).
- **소스**: AOSP `art/runtime/art_method.h`(엔트리포인트), `art/runtime/instrumentation.cc`(Deoptimize), `art/runtime/interpreter/`(nterp).

**주의**: JIT/AOT native code는 target ISA에 종속됩니다. x86_64 AVD와 ARM64 Cuttlefish/QEMU의 compiled code를 구분하고 ART·DEX 수준의 결론과 섞지 않습니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C13(ART)**: 이 세 모드가 그 컴파일 필터/프로필 파이프라인의 런타임 얼굴.
- **C14(DCL)**: "정적≠실행"의 진짜 원인 — packed dex는 런타임 로드.
- **C15(JNI)**: 네이티브 `.so` 로직은 DEX·이 세 모드 밖.
- **C37(완화)**: JIT 코드 캐시의 W^X(실행-쓰기 배타)와 얽힘.
- 다음은 다른 티어(IPC·프레임워크 Tier 3 등)로 넘어갑니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 세 실행 모드와 계측 ]

  DEX (진실의 원천, 로직 분석 대상)
    │  실행 형태는 런타임 상태(시간에 따라 변함):
    ├─ 인터프리트 (nterp, A12+)  ← 콜드/deopt 후
    ├─ JIT 네이티브 (인프로세스 캐시)  ← 핫
    └─ AOT 네이티브 (OAT/.odex)   ← 백그라운드 dexopt
         └ 세 모드 의미 동일 (행동 안 바뀜)

  계측: ArtMethod 엔트리포인트 리다이렉트  ──(인라인 호출은 우회!)──▶ 부족
        → deopt(인터프리터로 되돌림)  ← 진짜 모드 독립성의 보증

  "정적 ≠ 실행"의 원인 = JIT/AOT ✗
                        DCL/패커(C14) · 리플렉션 · JNI(C15) ✓
```

## 오개념 판별 문제 5개

1. "어떤 앱이 실행마다 다르게 동작한다면, JIT/AOT로 컴파일됐기 때문일 수 있다."
2. "앱 로직을 정확히 알려면 OAT의 네이티브 코드를 디스어셈블해야 한다."
3. "'정적으로 보이는 것과 실제 실행이 다르다'는 것은 JIT/AOT 컴파일 때문이다."
4. "ArtMethod 엔트리포인트만 다른 함수로 바꾸면, 실행 모드와 무관하게 그 메서드 호출이 다 후킹된다."
5. "ART의 인터프리터는 하나의 C++ 스위치 루프다."

<details><summary>판정 기준(펼치기)</summary>

1. 세 모드는 **의미 동일**입니다. 행동 차이가 JIT/AOT 탓인 경우는 없습니다(원인은 DCL/리플렉션/JNI/서버설정).
2. **DEX가 원천**이고 OAT는 파생입니다. 로직은 DEX(모든 shipped dex) 정적 분석으로 완전.
3. JIT/AOT는 의미 보존입니다. 진짜 원인은 **DCL/패커·리플렉션·JNI**.
4. **부족**합니다 — 인라인된 호출부는 엔트리포인트를 안 읽습니다. **deopt**가 실제 보증.
5. **A12+ 기본은 nterp**(런타임 생성 어셈블리)입니다.
</details>

## 서술형 문제 3개

1. 세 실행 모드가 왜 의미 동일이며, 그로부터 "로직은 DEX 레벨로 추론 가능"이 어떻게 따라오는지 서술하세요.
2. "정적으로 보이는 것 ≠ 실제 실행"의 진짜 원인이 JIT/AOT가 아니라 DCL/리플렉션/JNI임을, packed 앱을 예로 서술하세요.
3. ArtMethod 엔트리포인트 스왑이 왜 인라인 때문에 불충분하고, deopt가 왜 모드 독립성의 실제 보증인지 서술하세요.

## 소스·정적 검증 경로

- 한 앱의 `dumpsys package <pkg>` 컴파일 필터를 확인하고, `cmd package compile -m speed -f`로 바꾼 뒤 차이를 관찰하세요.
- Frida로 한 메서드를 후킹할 때 deopt가 트리거되는지(인터프리터로 되돌아가는지) 확인하고, 인라인 가능성이 높은 작은 메서드에서 훅이 견고한지 비교하세요.
- `/proc/<pid>/maps`에서 JIT 코드 캐시(익명 실행 영역)를 찾으세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **모드 실측**: `dumpsys` 필터와 `/proc/maps` JIT 영역을.
2. **후킹 서술**: Frida 훅에서 deopt가 걸리는 걸(로그) 캡처.
3. **괴리 서술**: 내 패커 작업에서 shipped dex(stub) vs 덤프 dex(실제)를 대조해 "정적≠실행"의 원인이 DCL임을.
4. **연결**: JNI(.so)가 왜 이 세 모드 밖 표면인지(C15).

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

같은 메서드가 인터프리트로도, JIT/AOT 네이티브로도 돌지만 — 세 모드는 같은 DEX의 컴파일이라 **의미가 동일**합니다. 그래서 로직은 DEX 정적 분석으로 완전하고, "정적으로 보이는 것 ≠ 실제 실행"의 진짜 원인은 JIT/AOT가 아니라 **동적 코드 로딩(C14)·리플렉션·JNI(C15)**입니다. 계측의 함정도 여기 있습니다 — ArtMethod 엔트리포인트를 갈아끼우는 것만으론 인라인된 호출을 놓치니, 견고한 후킹은 **deopt로 인터프리터로 되돌립니다**(그리고 A12+ 인터프리터는 nterp). 이로써 Tier 2(Android Runtime)를 닫습니다. 다음은 IPC·프레임워크(Tier 3)나 다른 티어로 이어집니다.
