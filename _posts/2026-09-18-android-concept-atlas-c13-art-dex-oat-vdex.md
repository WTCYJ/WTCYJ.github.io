---
layout: post
title: "Android Security Concept Atlas C13 | 가상 실습 보고서 — ART: DEX→OAT→VDEX, 리버서가 무엇을 분석해야 하나"
date: 2026-09-18 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ART, dex2oat, OAT, VDEX, ARTImage, AOT, JIT, ConceptAtlas, 학습기록]
excerpt: "앱을 리버싱할 때 무엇을 분석해야 하느냐 - OAT의 네이티브 코드? 아닙니다, DEX입니다. ART는 DEX 바이트코드를 실행하고, dex2oat가 그 DEX를 OAT(ELF에 싸인 네이티브 코드)와 VDEX(DEX + 검증 메타데이터, 재검증 생략용)로 컴파일하죠. 핵심은 DEX가 진실의 원천이라 VDEX 안에 그대로 보존되고, OAT는 그것의 파생 캐시일 뿐 새 로직이 없으며, ISA·부트이미지·DEX 체크섬에 묶여 기기 간 이식이 안 된다는 것. 그리고 Android 7부터는 설치 시 완전 AOT가 아니라 인터프리트+JIT로 프로필을 모으다 백그라운드에서 핫 메서드만 speed-profile로 컴파일하는 하이브리드입니다. 내 DEX 리버싱 작업의 배경을 이루는 Tier 2 런타임 모듈입니다."
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

![C13 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-runtime.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C13 — ART: DEX→OAT→VDEX
> **계층**: Tier 2 (Android Runtime) · **난이도**: 중급 · **선수 개념**: C07(DEX), C06(APK)
> **성격**: 보완 편.

C07에서 DEX를, C06에서 APK 안 `classes.dex`를 봤습니다. 그 DEX가 실제로 **어떻게 실행되고 컴파일되는지**, 그리고 리버서가 왜 여전히 **DEX를 분석하는지**가 이 편입니다.

한 문장으로: **ART는 DEX를 실행하고, dex2oat가 DEX를 OAT(네이티브)+VDEX(dex+검증)로 컴파일하지만, DEX가 진실의 원천이라 VDEX에 보존되고 OAT는 파생 캐시일 뿐이다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **ART**(A5.0~, Dalvik 대체): DEX 바이트코드 실행(인터프리트/JIT/AOT).
- **dex2oat**: DEX → **OAT**(ELF에 싸인 네이티브) + **VDEX**(dex+검증 메타).
- **ART 이미지(.art)**: 사전초기화 힙 스냅샷. **부트 이미지**(boot.art/boot.oat)를 zygote가 맵(C12).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

DEX(C07)를 실행하는 **런타임**입니다. C06의 APK 안 DEX가 여기서 컴파일되고, C12 zygote가 부트 이미지를 맵하며, C16(JIT/AOT 분석차)의 토대이자 내 DEX 리버싱 작업의 배경입니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **ART**가 앱 프로세스(EL0)에서 DEX를 인터프리트/JIT/AOT 실행.
- **dex2oat**(설치 시 + 백그라운드 dexopt)가 DEX를 소비해:
  - **OAT** = DEX 메서드를 컴파일한 **네이티브 코드**, **ELF 공유객체**에 포장(고전 `.odex`/`.oat`).
  - **VDEX**(A8.0~) = 앱의 **DEX + 검증 메타데이터**(재검증 생략용). **네이티브 코드 없음.**
  - **ART 이미지(.art)** = 사전초기화 객체 힙 스냅샷(부트 이미지는 프레임워크용, zygote가 맵).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **DEX = 진실의 원천**: VDEX 안에 DEX가 보존되므로, 디스크에 별도 `classes.dex`가 없어도 vdex/odex에서 복원됩니다(vdexExtractor/oatdump). OAT는 그 **AOT 컴파일**일 뿐 새 로직이 없습니다.
- **신뢰하면 안 되는 것들**:
  - **"OAT로 컴파일되면 DEX는 삭제/대체된다"** — DEX는 VDEX에 보존, 항상 복원 가능.
  - **"VDEX가 네이티브 코드를 담는다"** — VDEX는 **dex+검증**만. 네이티브는 OAT에만.
  - **"speed-profile은 앱 전체를 컴파일"** — **프로필의 핫 메서드만**. 나머지는 인터프리트/JIT.
  - **"모든 앱은 설치 시 완전 AOT"** — A7.0부터 **하이브리드**(인터프리트+JIT로 프로필 수집→백그라운드 speed-profile). 대부분 앱은 부분 컴파일이고 사용에 따라 자람.
  - **"OAT/VDEX는 기기 간 이식 가능"** — **ISA·부트이미지 체크섬·DEX 체크섬에 묶여** 비이식(부트이미지/OTA/ISA 바뀌면 무효화→재컴파일). "기기 정체성"이 아니라 이 체크섬들에 묶인 것.
  - **"부트 이미지는 /data/dalvik-cache에 있다"** — A10+는 **ART APEX**(`/apex/com.android.art/javalib/<isa>`)+`/system/framework/<isa>`. `/data/dalvik-cache/<isa>`는 온디바이스 재생성분만.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: DEX(+수집된 프로필).
- **동작(A7+ 하이브리드)**: 앱이 **인터프리트+JIT**로 돌며 핫 메서드 프로필을 `/data/misc/profiles`(cur/ref)에 기록 → 유휴/충전 시 **백그라운드 dexopt**가 `speed-profile`로 핫 메서드를 AOT. (A12+는 **ART 메인라인 모듈 `artd`(ART Service)**가 오케스트레이션, installd 경로는 A14에 은퇴.)
- **출력**: `oat/<isa>/base.odex`+`base.vdex`(런타임에 로드). Play Cloud Profiles로 설치 시 프로필 시드 가능.

## 질문 5 — 실패하면 어떤 취약점으로/분석에 어떤 함의가

- **분석 함의**: 앱 **로직 분석은 DEX 레벨로 완전**합니다(OAT는 그 컴파일). 네이티브 `.so`(JNI, C15)는 **별개** 표면.
- **DEX 복원**: 별도 `classes.dex` 없이 배포돼도 vdex에서 DEX 복원 → baksmali 등으로 분석.
- **비이식성**: 한 기기의 OAT를 다른 기기로 옮길 수 없음(체크섬 무효화) → 분석은 원본 DEX 대상.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **ART 기본**: A5.0. **하이브리드 JIT+AOT/프로필 유도**: A7.0. **VDEX**: A8.0.
- **dexopt 주체**: A12+ **artd(ART Service)** 메인라인 모듈, installd 경로 A14 은퇴.
- **부트 이미지**: A10+ ART APEX로 이동. 모던 시스템앱 기본 필터는 `speed`가 아니라 **`speed-profile`**(사전 프로필 동봉); `speed`는 부트 이미지·system_server·프로필 없는 컴포넌트.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `oatdump --oat-file=base.odex`(OAT/VDEX/.art 내부·임베디드 DEX·네이티브), `dexdump`/`baksmali`(복원 DEX), `vdexExtractor`(vdex→dex).
- `ls /data/app/<pkg>/oat/<isa>/`, `dumpsys package <pkg>`(현재 컴파일 필터/상태), `cmd package compile -m speed -f <pkg>`(강제 컴파일), `cmd package dump-profiles`, 부트 이미지 `/apex/com.android.art`.
- **소스**: AOSP `art/dex2oat`·`oatdump`·`compiler_filter.h`, source.android.com "Configure ART"·"ART optimizing profiles".

**주의**: `.odex`의 native code는 target ISA에 종속됩니다. x86_64 AVD와 ARM64 Cuttlefish/QEMU의 OAT를 구분하고, DEX 수준 결과와 ISA별 결과를 섞지 않습니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C07(DEX)·C06(APK)**: 그 `classes.dex`가 여기서 컴파일.
- **C12(zygote)**: 부트 이미지(boot.art/boot.oat)를 zygote가 맵해 앱이 COW 상속.
- **C16(JIT/AOT 분석차)**: 이 컴파일 모드가 정적/동적 분석 결과 차이를 만듦 — 바로 다음.
- **C15(JNI)**: 네이티브 `.so`는 이 DEX 파이프라인과 별개 표면.
- 다음은 이 실행 위에서 클래스를 로드하는 **C14(class loading·reflection)** 또는 **C16**로.

## 직접 그릴 수 있는 호출 흐름

```
[ ART: DEX가 실행되고 컴파일되는 길 ]

  classes.dex (C07) ──dex2oat──▶ base.odex (OAT = 네이티브, ELF 포장)
                                 base.vdex (DEX + 검증 메타, 재검증 생략)
                                          └ DEX 보존 → vdexExtractor로 복원

  A7+ 하이브리드:
    앱 실행 → 인터프리트 + JIT → 핫 메서드 프로필(/data/misc/profiles)
        → (유휴/충전) 백그라운드 dexopt: speed-profile로 핫만 AOT
        → (A12+ artd/ART Service가 오케스트레이션)

  부트 이미지(boot.art/boot.oat, A10+ /apex/com.android.art) ─맵─▶ zygote(C12)

  리버싱 대상 = DEX (OAT는 그 파생 컴파일 · ISA/체크섬에 묶여 비이식)
```

## 오개념 판별 문제 5개

1. "앱이 OAT로 컴파일되면 DEX 바이트코드는 사라져서, 네이티브 OAT를 디스어셈블해 분석해야 한다."
2. "VDEX 파일에는 OAT처럼 컴파일된 네이티브 코드가 들어 있다."
3. "`speed-profile`은 프로필을 붙인 `speed`라, 앱 전체를 AOT 컴파일한다."
4. "모든 앱은 설치 시점에 완전히 AOT 컴파일된다."
5. "한 기기에서 만든 `.odex`/`.vdex`를 다른 기기로 복사해 쓸 수 있다."

<details><summary>판정 기준(펼치기)</summary>

1. **DEX가 진실의 원천**이고 VDEX에 보존됩니다. vdex/odex에서 DEX를 복원해 분석하며, OAT는 파생 캐시.
2. VDEX는 **DEX+검증 메타데이터**만. 네이티브 코드는 OAT/`.odex`에만.
3. `speed-profile`은 **프로필의 핫 메서드만** AOT합니다(나머지 인터프리트/JIT).
4. A7.0부터 **하이브리드**(인터프리트+JIT 프로파일링→백그라운드 speed-profile 점진).
5. **ISA·부트이미지·DEX 체크섬에 묶여** 비이식입니다(무효화→재컴파일).
</details>

## 실측으로 확인한 것

가상 실습 환경(codex-atlas-api33, x86_64, ART 13/API 33)에서 이 모듈이 전제하는 런타임 상태를 검증 블록의 명령으로 확인했다.

**1) 이 기기의 ART는 JIT를 켠 A7+ 하이브리드 런타임이다.** 블록에 기록한 세 명령을 그대로 실행해 `zygote64`와 JIT 활성 상태를 관측했다.

```console
$ getprop ro.zygote
$ getprop dalvik.vm.usejit
$ ps
```

`ro.zygote`가 `zygote64`라는 것은 64비트 ART 프로세스가 부트 이미지를 맵한다는 뜻이고(질문 8의 C12 연결), `dalvik.vm.usejit` 활성은 앱이 인터프리트+JIT로 돌며 프로필을 모으는 파이프라인의 진입 경로가 켜져 있다는 뜻이다. 질문 4의 하이브리드 동작이 프로퍼티 수준에서 확인되고, "모든 앱은 설치 시 완전 AOT"라는 오개념 4가 이 한 기기에서 곧바로 반증된다.

**2) DEX를 실행하는 앱 프로세스는 격리돼 있다.** 같은 캡처에서 비특권 앱의 전체 프로세스 열람이 막히는 것을 함께 관측했다(`ps` 접근 거부). ART가 DEX를 인터프리트/JIT 실행하는 무대가 EL0의 격리된 앱 프로세스라는 질문 2의 전제가, 예상된 격리 결과로 뒷받침된다. 원시 출력은 검증 블록의 API 33 기준 로그에, 화면은 상단 검증 스크린샷(`evidence-runtime.png`)에 보존돼 있다.

DEX가 진실의 원천이고 OAT/VDEX가 그 파생 산출물이라는 이 모듈의 중심 불변식은 AOSP `art/dex2oat`·`oatdump`와, VDEX가 원본 DEX를 그대로 담아 재검증을 생략한다는 소스 사실로 확정했다. 다만 이 AVD 세션에서 산출물 파일 자체를 캡처하지는 않았다(아래 한계).

## 가상환경 검증 한계

정직하게, 이 문서의 신규 캡처는 (1)·(2)의 런타임 프로퍼티까지다. DEX→OAT→VDEX 파이프라인의 산출물 수준 증거는 소스·문서로 근거를 확정했으나 이 세션에서 새로 캡처하지는 않았다.

- **`oat/<isa>/base.odex`·`base.vdex` 산출물과 `dumpsys package` 컴파일 필터는 이 세션에서 캡처하지 않았다.** OAT/VDEX 생성은 빌드·프로필 상태에 따라 달라져(검증 블록 각주와 동일), 한 번의 x86_64 AVD 캡처를 모든 Android 버전으로 일반화하지 않는다.
- **vdex→dex 복원(vdexExtractor/oatdump)과 baksmali 대조도 이 세션에서 실행하지 않았다.** DEX 보존은 VDEX 포맷의 문서화된 속성이지만, 실제 복원 출력을 이 문서의 관측 결과로 주장하지는 않는다.
- **ARM64 전용 OAT는 이 x86_64 AVD로 측정할 수 없다.** `.odex`의 네이티브 코드는 타깃 ISA에 종속되므로, ARM64 Cuttlefish/QEMU의 OAT와 여기서 본 x86_64 런타임을 섞지 않는다.

관련 근거: [ART 개요 (source.android.com)](https://source.android.com/docs/core/runtime) · [Configuring ART](https://source.android.com/docs/core/runtime/configure) · [AOSP art/dex2oat](https://cs.android.com/android/platform/superproject/+/main:art/dex2oat/)

## 마치며

ART는 DEX를 실행하고, dex2oat가 그 DEX를 OAT(ELF에 싸인 네이티브)와 VDEX(dex+검증)로 컴파일합니다. 핵심은 **DEX가 진실의 원천**이라 VDEX에 보존되고, OAT는 새 로직 없는 파생 캐시이며, ISA·부트이미지·DEX 체크섬에 묶여 기기 간 이식이 안 된다는 것 — 그래서 리버서는 **DEX를 분석**합니다. 그리고 A7부터는 설치 시 완전 AOT가 아니라 인터프리트+JIT로 프로필을 모으다 핫 메서드만 백그라운드에서 `speed-profile`로 컴파일하는 하이브리드이고(A12+는 `artd`가 오케스트레이션), 부트 이미지는 A10+ ART APEX로 옮겨갔습니다. 다음은 이 컴파일 모드가 만드는 분석 차이(**C16**) 또는 클래스를 실제로 로드하는 **C14**로 이어집니다.
