---
layout: post
title: "Android Security Concept Atlas C03 | 가상 실습 보고서 — 최소권한·완전중재·심층방어, Atlas가 실증해온 설계 원칙"
date: 2026-09-27 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, LeastPrivilege, CompleteMediation, DefenseInDepth, FailSafeDefaults, ReferenceMonitor, SaltzerSchroeder, ConceptAtlas, 학습기록]
excerpt: "이 Atlas의 거의 모든 모듈은 사실 몇 개의 오래된 설계 원칙(Saltzer & Schroeder 1975)의 사례입니다. 앱마다 UID를 주고 capability를 0으로 만드는 건 최소권한, SELinux가 매 접근을 검사하는 건 완전중재, 규칙이 없으면 거부하는 건 fail-safe defaults, UID+SELinux+seccomp를 겹치는 건 심층방어(이건 현대 원칙이지 S&S 8개엔 없음)죠. Reference monitor는 '항상 호출됨+변조불가+검증가능' 세 속성으로 정의되고요. 중요한 뉘앙스 - 완전중재는 stale 인가/권한 캐싱 버그를 막지 고전 TOCTOU 레이스는 원자성이 따로 필요하고, Binder는 프레임워크로 가는 주 매개 채널이지 유일한 문은 아닙니다. Atlas 전체를 하나의 원칙 지도로 묶는 Tier 0 토대 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `id`, `cat /proc/self/attr/current`, `/proc/self/status`, `uname -a` |
| 관측 결과 | 앱 UID 10174, `untrusted_app` 도메인, `CapEff=0`, `Seccomp=2`, Linux 5.15 커널을 확인했다. |
| 검증 한계 | AVD가 x86_64이므로 ARM64 EL·PAC·BTI·MTE는 런타임 관측 대신 공개 소스 경로로 판정한다. |

![C03 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C03 — 최소권한·완전중재·심층방어(설계 원칙)
> **계층**: Tier 0 (보안·시스템 기초) · **난이도**: 기초 · **선수 개념**: C01, C02
> **성격**: 원칙 편 — Atlas 전체를 하나의 원칙 지도로.

지금까지 각 티어에서 본 메커니즘들은 사실 **몇 개의 오래된 설계 원칙**의 사례입니다. 이 편은 그 원칙에 이름을 붙여 Atlas 전체를 하나로 묶습니다.

한 문장으로: **Android 보안은 최소권한·완전중재·fail-safe defaults 같은 Saltzer & Schroeder(1975) 원칙과 현대의 심층방어를 각 계층에서 실현한 것이다.** 🟡 기초·원칙 편이라 원칙 지도에 집중합니다.

## 배경 개념 — S&S 8원칙 + 현대

- **최소권한**: 필요한 최소 권한만(권한의 **크기**).
- **완전중재**: 모든 접근을 매번 검사(캐시된 결정 재사용·우회 금지).
- **fail-safe defaults**: 기본 거부(무규칙·오류 시 거부) — 최소권한과 **다른 축**.
- **심층방어**: 독립 층 겹치기 — **S&S 8개엔 없는 현대 원칙**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**Atlas 전체가 실현해온 원칙에 이름 붙이기**입니다. 거의 모든 모듈이 어느 원칙의 사례이고, 이 편이 그 지도입니다.

## 질문 2 — 어떤 원칙들이며 무엇을 뜻하는가

- **S&S 8원칙(1975)**: 최소권한 · 완전중재 · fail-safe defaults · economy of mechanism(보안 핵심을 작고 단순하게=검증가능) · separation of privilege(둘 이상의 독립 조건) · least common mechanism(공유 메커니즘 최소화) · psychological acceptability(쓸 만해야) · open design(설계 비밀 아닌 키에만 의존).
- **현대**: **심층방어**(독립 층 다중화 — S&S 8개엔 **없음**).
- **Reference monitor(Anderson 1972)**: 접근 매개자의 **세 속성** — (1) 항상 호출됨(=완전중재), (2) **변조 불가**, (3) 검증 가능할 만큼 작음(=economy). 세 속성 중 **변조 불가는 S&S 어느 원칙에도 안 매핑** — 그래서 "두 원칙의 합성"이 아님.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **원칙은 겹쳐서** 작동합니다(어느 하나가 만능 아님).
- **신뢰하면 안 되는 것들**:
  - **"최소권한 = fail-safe defaults"** — 다른 축입니다. 최소권한=권한의 **크기**, fail-safe defaults=**기본/오류 시** 방향(거부).
  - **"심층방어는 Saltzer-Schroeder 원칙"** — 아닙니다. 현대 원칙입니다(S&S 8개 = 위 목록).
  - **"reference monitor는 완전중재+economy 두 원칙의 합성"** — **세 속성**입니다. **변조 불가**는 별개 요구(어느 S&S 원칙에도 안 매핑).
  - **"완전중재가 TOCTOU를 막는다"** — 완전중재는 **stale 인가/권한 캐싱** 버그를 막습니다. 고전 **TOCTOU 레이스는 원자적 check-and-use**가 따로 필요(별개).
  - **"Binder가 유일한 문이라 완전중재가 자동"** — Binder는 프레임워크로 가는 **주** 매개 채널이지 유일한 문이 아닙니다(소켓·공유메모리·파일·직접 시스템콜도 — 각각 DAC/SELinux/seccomp가 매개).

## 질문 4 — Android는 각 원칙을 어떻게 구현하나 (입출력)

- **최소권한**: 앱마다 UID(C09) + capability 0(C24) + 요청한 권한만(C10) + system_server가 root 아닌 전용 서비스(C19) + isolatedProcess는 극단(C25).
- **완전중재**: SELinux가 **매 접근**을 정책과 대조(C23; AVC는 **결정 캐시**지 우회 아님) + system_server의 레퍼런스 모니터가 **매 호출** 호출자 UID 검사(C19/C21/C22) + Binder가 주 매개 채널(C17).
- **fail-safe defaults**: SELinux deny-by-default + neverallow(C23) + 컴포넌트 기본 non-exported(C21) + 권한 미요청=미보유(C10).
- **심층방어**: 앱 샌드박스 = DAC+MAC+seccomp+caps 비움(C09/C23/C24) + 검증 부팅 체인(C27/C28/C30~C32) + 완화(C37) — 한 층 실패가 전면 실패가 아님.

## 질문 5 — 원칙 위반이 어떤 취약점이 되나

- **최소권한 위반**: 과특권 컴포넌트(root로 도는 데몬, shared-UID) → 침해 시 폭발 반경 큼.
- **완전중재 위반**: stale 인가 재사용·우회 경로(권한 캐싱 버그).
- **fail-safe 위반**: default-allow(잊은 규칙이 허용으로).
- **심층방어 부재**: 단일 층 실패가 전면 장악.
- **economy 위반**: 거대 TCB는 감사 불가 → 숨은 버그. (Android도 SELinux **엔진/TCB**는 작지만 **정책 자체는 방대**하다는 한계.)
- **Atlas는 이 위반들의 지도**이자, 각 원칙이 어느 계층에서 실현되는지의 안내서.

## 질문 6 — Android 버전/역사에 따라 무엇이 달라졌나

- 원칙 자체는 시대 무관(S&S 1975). Android는 시간이 갈수록 **원칙을 강화**: pre-Treble의 모놀리식 벤더 특권·shared-UID(최소권한·least common mechanism 위반)를 **Treble/GKI(C31/C35)·isolatedProcess(C25)·shared-UID 폐기(C09)**로 개선.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- **원전**: Saltzer & Schroeder, "The Protection of Information in Computer Systems"(1975) — 8원칙; Anderson(1972) — reference monitor; Orange Book.
- **Android**: AOSP 소스 + 공개 sepolicy(=**open design**의 실증). 각 원칙을 어느 모듈이 실현하는지 이 Atlas로 추적.

**주의**: 개념 검증은 도구 무관 → **어떤 설계든 "이 원칙 중 무엇을 지키고 무엇을 어겼나"로 점검** 가능.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **최소권한**: C09·C24·C10·C19·C25.
- **완전중재**: C23·C17·C19·C21·C22.
- **fail-safe defaults**: C23·C21·C10.
- **심층방어**: C09+C23+C24 + C27/C28 + C37.
- **reference monitor**: C23(SELinux) + system_server 권한 검사.
- 이 원칙 지도가 Atlas의 뼈대이고, 다음 티어들은 그 원칙의 추가 사례입니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 설계 원칙 → Android 실현 지도 ]

  최소권한 ────────▶ 앱 UID(C09)·caps 0(C24)·요청권한(C10)·non-root SS(C19)
  완전중재 ────────▶ SELinux 매 접근(C23,AVC=캐시)·SS 매 호출 UID검사(C19/21/22)
                     (stale 인가는 막지만 고전 TOCTOU 레이스는 원자성 별도)
  fail-safe defaults ▶ SELinux deny-by-default·non-exported(C21)·미요청=거부(C10)
  심층방어(현대) ──▶ DAC+MAC+seccomp+caps + 검증부팅(C27/28) + 완화(C37)
                     (S&S 8원칙에는 없음)

  Reference monitor(Anderson): ①항상호출 ②변조불가 ③검증가능(작음)
     ≈ SELinux LSM(엔진 작음, 정책은 방대) + system_server 권한검사
     ⚠ 변조불가는 어느 S&S 원칙에도 안 매핑 → "두 원칙 합성"이 아님

  Binder = 프레임워크로 가는 주 매개 채널(유일한 문 X: 소켓/파일/syscall도)
```

## 오개념 판별 문제 5개

1. "최소권한과 fail-safe defaults는 사실상 같은 원칙이다."
2. "심층방어는 Saltzer & Schroeder의 고전 보안 원칙 중 하나다."
3. "reference monitor는 완전중재와 economy of mechanism 두 원칙을 합친 것이다."
4. "완전중재를 지키면 TOCTOU 경쟁 조건이 방어된다."
5. "Android에서는 Binder가 유일한 IPC 문이라 완전중재가 자동으로 보장된다."

<details><summary>판정 기준(펼치기)</summary>

1. **다른 축**입니다. 최소권한=권한의 크기, fail-safe defaults=기본/오류 시 거부 방향.
2. 아닙니다. 심층방어는 **현대** 원칙입니다(S&S 8 = 최소권한·완전중재·fail-safe defaults·economy·separation of privilege·least common mechanism·psychological acceptability·open design).
3. **세 속성**(항상호출+변조불가+검증가능)입니다. **변조 불가**는 어느 S&S 원칙에도 안 매핑됩니다.
4. 완전중재는 **stale 인가/권한 캐싱**을 막습니다. 고전 TOCTOU는 **원자적 check-and-use**가 별도로 필요합니다.
5. Binder는 **주** 채널이지 유일한 문이 아닙니다(소켓·공유메모리·파일·직접 시스템콜, 각각 DAC/SELinux/seccomp가 매개).
</details>

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, Android 13/API 33, x86_64)에서 이 모듈의 원칙 주장을 앱 프로세스 자기 관측으로 확인했다. 검증 블록에 기록한 명령이 그 근거다.

```console
$ id
uid=10174 ...                    # 앱마다 다른 격리 UID
$ cat /proc/self/attr/current
untrusted_app ...                # SELinux 도메인
$ cat /proc/self/status          # 발췌
CapEff=0                         # 상속 capability 전부 비움
Seccomp=2                        # seccomp-bpf 필터 강제(SECCOMP_MODE_FILTER)
$ uname -a
Linux ... 5.15 ...
```

**1) 최소권한이 프로세스 수준에서 실재한다.** 앱 UID는 `10174`, `CapEff=0`이다. 이 프로세스는 자기 앱 전용 UID 하나만 갖고 상속 capability는 전부 비어 있다 — 질문 4의 "앱마다 UID(C09) + capability 0(C24)"가 권한의 **크기** 축에서 그대로 관측된다. 권한이 0에서 시작한다는 이 값이, 최소권한과 fail-safe defaults가 다른 축이라는 질문 3의 구분(크기 vs 기본/오류 시 방향)을 뒷받침한다.

**2) 심층방어의 독립 층들이 한 프로세스에 동시에 얹혀 있다.** 같은 프로세스에서 DAC(UID `10174`) · MAC(`untrusted_app` SELinux 도메인) · seccomp(`Seccomp=2`) · capability 비움(`CapEff=0`)이 함께 관측된다 — 질문 4의 "앱 샌드박스 = DAC+MAC+seccomp+caps 비움"이 네 값으로 동시에 확인된다. 한 층이 뚫려도 나머지 세 층이 남는다는 것이 심층방어의 요점이고, 이는 질문 5의 "단일 층 실패가 전면 장악"의 정반대 상태다.

**3) SELinux가 이 프로세스를 정책 대상으로 잡고 있다.** `/proc/self/attr/current`가 빈 값이 아니라 `untrusted_app` 도메인을 돌려준다는 것은, 이 앱 프로세스가 커널 LSM의 매개 대상으로 등록돼 있다는 뜻이다 — reference monitor "항상 호출됨(=완전중재)" 속성의 전제(질문 2)가 도메인 배정 수준에서 확인된다. 다만 "매 접근을 정책과 대조"하는 런타임 매개 자체와 "변조 불가" 속성은 아래 한계로 넘긴다.

## 가상환경 검증 한계

정직하게, 이 문서가 새로 캡처한 실측은 위 (1)~(3)까지다. 나머지는 근거를 소스·문서로 확정했을 뿐 이 AVD 세션에서 새로 관측하지는 않았다.

- **완전중재의 런타임 매개와 reference monitor "변조 불가"는 값으로 관측하지 않았다.** 도메인 배정까지는 확인했으나, SELinux가 매 접근을 실제로 정책과 대조하는 경로와 정책·TCB의 변조 불가 속성(질문 2·3)은 AOSP sepolicy와 커널 LSM 소스로만 판정한다.
- **ARM64 하드웨어 격리 계층은 x86_64 AVD라 미측정이다.** 검증 블록에 적었듯 ARM64 EL·PAC·BTI·MTE는 이 아키텍처에서 런타임 관측 대상이 아니며, 하드웨어 TEE/StrongBox도 에뮬레이터에서는 소프트웨어 폴백이라 실제 격리 경계를 재현하지 않는다.
- **원칙 위반의 라이브 재현은 하지 않았다.** shared-UID 악용이나 과특권 데몬 같은 위반 사례(질문 5)는 개념·역사(질문 6)로만 서술했고, 이 세션에서 실제로 익스플로잇하거나 커널 완화를 우회한 관측은 없다.

관련 근거: [Android 앱 샌드박스](https://source.android.com/docs/security/app-sandbox) · [Android SELinux](https://source.android.com/docs/security/features/selinux) · [capabilities(7)](https://man7.org/linux/man-pages/man7/capabilities.7.html) · [seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html)

## 마치며

이 Atlas의 거의 모든 모듈은 사실 몇 개의 오래된 설계 원칙(Saltzer & Schroeder 1975)의 사례입니다: 앱마다 UID를 주고 capability를 0으로 만드는 건 **최소권한**, SELinux가 매 접근을 검사하는 건 **완전중재**, 규칙이 없으면 거부하는 건 **fail-safe defaults**, UID+SELinux+seccomp를 겹치는 건 **심층방어**(이건 현대 원칙이지 S&S 8개엔 없음)입니다. Reference monitor는 "항상 호출됨+변조 불가+검증 가능" **세** 속성으로 정의되고요. 뉘앙스는 — 완전중재는 stale 인가/권한 캐싱 버그를 막지 고전 TOCTOU 레이스는 원자성이 따로 필요하고, Binder는 프레임워크로 가는 **주** 매개 채널이지 유일한 문은 아니라는 것입니다. 이로써 Tier 0(보안·시스템 기초)을 닫습니다 — 이 원칙 지도가 Atlas 전체의 뼈대입니다. 다음은 남은 티어(Tier 5·8·9)로 이어집니다.
