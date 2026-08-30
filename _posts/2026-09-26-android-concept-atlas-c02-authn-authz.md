---
layout: post
title: "Android Security Concept Atlas C02 | 가상 실습 보고서 — 인증 vs 인가, 혼동이 곧 접근 통제 버그"
date: 2026-09-26 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, Authentication, Authorization, IDOR, BOLA, BFLA, BrokenAccessControl, ConceptAtlas, 학습기록]
excerpt: "버그바운티에서 제일 많이 나오는 게 이 둘을 헷갈린 버그입니다. 인증(AuthN)은 '너 누구야?'를 확인하고, 인가(AuthZ)는 '그래서 이걸 해도 돼?'를 결정하죠 - 완전히 별개 질문인데, '로그인했으니 다 허용'이라 착각하거나 정체성만 확인하고 특정 객체/행위 권한은 안 보면 그게 바로 IDOR(객체수준)·BFLA(함수수준), 곧 Broken Access Control(OWASP 1위)입니다. 내 HSPACE PII 케이스가 정확히 그거였어요 - 세션은 인증했는데 그 레코드가 이 사용자 것인지는 인가 안 함. Android도 똑같습니다: 커널이 각인한 호출자 UID로 '누구'는 위조 불가로 알지만, 그걸로 권한을 검사하는 건 별개고, checkCallingOrSelfPermission의 OrSelf 폴백이면 자기 정체성으로 조용히 통과하죠. Atlas 전체가 이 구분의 실현인, Tier 0 토대 모듈입니다."
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

![C02 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C02 — 인증 vs 인가
> **계층**: Tier 0 (보안·시스템 기초) · **난이도**: 기초 · **선수 개념**: C01
> **성격**: 원칙 편 — Atlas 전체가 실현하는 구분에 이름 붙이기.

버그바운티에서 가장 흔한 결함이 이 둘을 헷갈린 것입니다. 내 HSPACE PII 케이스가 정확히 그랬죠 — 세션은 **인증**했는데 그 레코드가 이 사용자 것인지는 **인가**하지 않았습니다.

한 문장으로: **인증(누구인가)과 인가(무엇을 해도 되는가)는 별개 질문이고, 이 둘을 혼동하면 곧 IDOR·BFLA, 즉 Broken Access Control이다.** 🟡 기초·원칙 편이라 구분에 집중합니다.

## 배경 개념

- **인증(AuthN)**: "너 누구야?" — 정체성 **확인**.
- **인가(AuthZ)**: "그래서 이 행위/객체를 해도 돼?" — 접근 **결정**.
- **혼동 = #1 버그**: "인증됐으니 인가됨" / "정체성만 확인" → Broken Access Control(OWASP A01).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**모든 접근 통제의 두 축**이고, Atlas 전체가 이 구분의 실현입니다. C08(앱 정체성)·C22(호출자 UID)는 AuthN, C10(권한)·C23(SELinux)·C21(exported)·C11(URI)은 AuthZ.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **AuthN(정체성 확립)** on Android:
  - 앱 정체성 = **서명 인증서**(C08).
  - IPC 호출자 = **커널이 각인한 호출자 UID/PID**(`Binder.getCallingUid`, C22) — **위조 불가**.
  - 사용자 = **Gatekeeper**(지식요소 PIN/패턴/비번만 검증, HAT 발행, C41) + **별도 생체 HAL**(지문/얼굴, BiometricPrompt, 자체 HAT) + KeyMint 인증연동 키(C40).
- **AuthZ(접근 결정)** on Android: 권한(C10)·SELinux MAC(C23)·exported+`android:permission`(C21)·URI 권한(C11).
- **순서**: 인가는 **항상 도는 관문**이고, 인증은 결정이 **정체성 기반일 때만** 선행합니다(공개 리소스는 인증 없는 인가 "allow").

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **AuthN은 시작이지 끝이 아님**: 정체성을 알아도 "무엇을 해도 되는지"는 전혀 안 알려줍니다 — 그건 특정 객체/행위에 대한 **별도 명시 결정**.
- **신뢰하면 안 되는 것들**:
  - **"인증됐으니 인가됨"** — 각 민감 행위마다 **재검사**해야 합니다(한 번 로그인 후 무검사 세션 = 전형적 파손).
  - **"접근 통제 버그는 전부 IDOR"** — **객체수준**(이 사용자가 이 객체를 가졌나 안 봄) = IDOR/BOLA, **함수수준**(인증된 일반 사용자가 관리 기능에 도달) = **BFLA**. 둘 다 **Broken Access Control(A01)** 산하(CWE-639/862/863).
  - **"공개 리소스면 접근 통제가 불필요"** — 익명 허용도 **인가 결정**입니다(의도적 allow).
  - **"호출자 UID만 확인하면 된다"** — 그건 AuthN입니다. 그 UID에 **권한을 적용하는 AuthZ**가 별도로 있어야.
  - **"`checkPermission`이 위험한 API"** — 아닙니다. `checkPermission(perm, pid, uid)`은 **넘긴 uid**를 검사하는 중립 API. 함정은 **`checkCallingOrSelfPermission`/`enforceCallingOrSelfPermission`의 `OrSelf` 폴백** — IPC 진행 중이 아니면 **서비스 자기 정체성**을 검사해 조용히 통과. 호출자를 게이트하려면 `checkCallingPermission`을.

## 질문 4 — 입력과 출력은 무엇인가

- **AuthN**: 자격증명(비번/생체/서명/커널 UID) → **확립된 정체성**.
- **AuthZ**: (정체성 또는 익명) + 특정 행위/객체 → **허용/거부**. Android는 커널이 각인한 호출자 UID(위조 불가)를 AuthZ가 소비.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **IDOR/BOLA**(객체수준): 서버/앱이 사용자를 인증하지만 요청한 객체 id가 **이 사용자 것인지** 안 봄 — 내 **HSPACE PII 케이스**(세션 인증, 레코드 인가 누락).
- **BFLA**(함수수준): 인증된 일반 사용자가 관리 행위에 도달.
- **OAuth "인증됐으니 신뢰"**: 내 **reporch OAuth-complete 케이스**(콜백이 계정은 인증했으나 username 바인딩/인가가 조작 가능).
- **Android IPC**: exported 컴포넌트/서비스가 호출자 UID를 알지만 권한 미검사, 또는 `checkCallingOrSelfPermission`으로 자기 정체성 통과 → 아무 앱이나 특권 행위.

## 질문 6 — Android 버전/맥락에 따라 무엇이 달라지나

- 개념 자체는 버전 무관. 단 구현 디테일: **Gatekeeper**=지식요소, **생체 HAL**=생체(각각 HAT 발행); **`*OrSelf*` 권한 API**는 IPC 진행 중에만 호출자를 검사(밖에선 자기).
- OWASP: Web **A01:2021 Broken Access Control(#1)**, API **API1:2023 BOLA(#1)**·**API5:2023 BFLA**.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- **진단 질문 쌍**(모든 민감 행위마다): ① "정체성이 확인됐나?(AuthN)" **그리고 따로** ② "이 정체성이 이 **특정 객체/행위**에 인가됐나?(AuthZ)".
- **Android**: 매니페스트/`dumpsys package`의 컴포넌트 `android:permission` 가드 유무, 비특권 앱으로 exported 컴포넌트 호출; 코드에서 `checkCallingPermission` vs `*OrSelf*` 확인.
- **웹/API**: 객체 id를 다른 사용자 것으로 바꿔보기(IDOR), 역할을 낮춰 관리 기능 호출(BFLA).

**주의**: 개념 검증은 도구 무관 → **어떤 대상에서도 "정체성 확인 AND 객체 인가" 질문 쌍으로 점검** 가능.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **AuthN 층**: C08(서명=앱 정체성), C22(호출자 UID), C40/C41(사용자 인증).
- **AuthZ 층**: C10(권한), C23(SELinux), C21(exported+permission), C11(URI 권한).
- **구분의 실현**: Atlas의 접근 통제 편들이 전부 이 두 축의 사례.
- 다음은 이 구분을 떠받치는 **설계 원칙** C03(최소권한·완전중재·심층방어)으로.

## 직접 그릴 수 있는 호출 흐름

```
[ 인증 vs 인가: 두 별개 질문 ]

  AuthN "너 누구야?"           AuthZ "이 행위/객체를 해도 돼?"
   ├ 앱: 서명 인증서(C08)        ├ 권한(C10)
   ├ IPC: 커널 각인 호출자 UID    ├ SELinux MAC(C23)
   │      (위조 불가, C22)        ├ exported+android:permission(C21)
   └ 사용자: Gatekeeper(지식)     └ URI 권한(C11)
            + 생체 HAL(생체)

  올바름:  AuthN(정체성) ──▶ AuthZ(이 특정 객체/행위마다 재검사) ──▶ 허용
  파손:    AuthN "됨" ──▶ (AuthZ 생략/자기정체성 통과) ──▶ IDOR/BFLA
           checkCallingPermission(호출자) ✔  vs  *OrSelf*(자기로 폴백) ✗
```

## 오개념 판별 문제 5개

1. "사용자가 로그인(인증)했으면, 그 세션의 요청은 인가된 것으로 봐도 된다."
2. "접근 통제 취약점은 결국 다 IDOR다."
3. "인증이 필요 없는 공개 리소스는 접근 통제도 필요 없다."
4. "Binder 서비스가 호출자 UID를 확인했다면 권한 검사를 한 것이다."
5. "`checkPermission`은 자기 정체성으로 항상 통과하는 위험한 API다."

<details><summary>판정 기준(펼치기)</summary>

1. 각 민감 행위마다 **인가를 재검사**해야 합니다. "인증=인가"가 Broken Access Control의 뿌리.
2. **객체수준**은 IDOR/BOLA, **함수수준**은 BFLA입니다 — 둘 다 Broken Access Control(A01) 산하지만 다른 granularity.
3. 익명 허용도 **인가 결정**입니다(의도적 allow). 공개라도 통제는 존재.
4. 그건 **AuthN**입니다. 그 UID에 권한을 적용하는 **AuthZ가 별도**로 있어야.
5. 아닙니다. `checkPermission(perm,pid,uid)`은 넘긴 uid를 검사하는 중립 API. 함정은 **`*OrSelf*` 변형**(IPC 밖에서 자기 정체성 폴백).
</details>

## 실측으로 확인한 것

이 모듈의 두 축이 **한 앱 프로세스 안에 서로 다른 레이어로 동시에 존재한다**는 것을, 가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 검증 블록에 기록한 네 명령으로 확인했다. 위 [검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)의 값이 그대로다.

```console
$ adb shell id                          # → 앱 UID 10174   (AuthN: 커널이 각인한 정체성)
$ adb shell cat /proc/self/attr/current # → untrusted_app  (AuthZ: SELinux MAC 도메인)
$ adb shell cat /proc/self/status       # → CapEff=0, Seccomp=2  (AuthZ: 능력·시스템콜 제한)
$ adb shell uname -a                    # → Linux 5.15     (커널)
```

**1) "누구"(AuthN)는 앱이 고르는 값이 아니라 커널이 박은 UID다.** `id`가 보고한 앱 UID 10174는 프로세스 생성 시 커널이 각인한 정체성이지 앱이 선언한 값이 아니다. 질문 2의 불변식 "IPC 호출자 = 커널이 각인한 호출자 UID(위조 불가)"가 프로세스 수준에서 그대로 관측되며, Binder AuthZ(`Binder.getCallingUid`, C22)가 소비하는 게 바로 이 값이다.

**2) "무엇을 해도 되나"(AuthZ)는 그 정체성과 별개의 레이어다.** 같은 프로세스에서 `/proc/self/attr/current`는 `untrusted_app` SELinux 도메인을 보고했다. 정체성(UID 10174)과 접근 결정(SELinux MAC 도메인, C23)이 한 프로세스 안에 나란히, 서로 다른 축으로 존재한다 — 질문 3의 "AuthN은 시작이지 끝이 아니다"가 눈으로 확인된다. UID를 알아도 무엇이 허용되는지는 도메인 정책이 별도로 결정한다.

**3) 인증된 앱이라도 특권은 기본 차단이다.** `/proc/self/status`의 `CapEff=0`(유효 capability 없음)과 `Seccomp=2`(seccomp 필터 활성)는, "로그인/실행됐으니 뭐든 된다"가 아니라 인가 관문이 항상 돈다는 질문 2의 "인가는 항상 도는 관문"을 뒷받침한다. 정체성 확인과 무관하게 능력과 시스템콜 표면이 좁혀져 있다.

## 가상환경 검증 한계

정직하게, 이 문서의 실측 캡처는 위 세 값(UID · SELinux 도메인 · CapEff/Seccomp)까지다. 나머지는 근거는 소스로 확정했으나 이 AVD 세션에서 새로 캡처하지는 않았다.

- **`checkCallingOrSelfPermission`의 `OrSelf` 폴백은 라이브로 재현하지 않았다.** 두 앱 사이에 실제 IPC를 걸어 "IPC 밖이면 서비스 자기 정체성으로 통과"를 관측한 것이 아니라, 동작은 AOSP 소스 정의로만 확정했다. 질문 3·5의 핵심 함정이지만 이 세션의 관측 결과는 아니다.
- **exported 컴포넌트를 비특권 앱으로 호출한 응답은 이 세션에서 찍지 않았다.** 소유 앱 두 개(호출자·피호출자)를 띄워 권한 가드 유무를 실제 응답으로 증적화하는 절차는 실행하지 않았다.
- **ARM64 EL·PAC·BTI·MTE는 x86_64 AVD라 런타임으로 관측하지 못했다.** 검증 블록의 한계 줄과 동일하게, 이 하드웨어 완화들은 공개 소스 경로로만 판정한다.

관련 근거: [OWASP A01:2021 Broken Access Control](https://owasp.org/Top10/A01_2021-Broken_Access_Control/) · [OWASP API Security Project (BOLA/BFLA)](https://owasp.org/www-project-api-security/) · [Android Context.checkCallingOrSelfPermission](https://developer.android.com/reference/android/content/Context) · [Android Binder.getCallingUid](https://developer.android.com/reference/android/os/Binder)

## 마치며

버그바운티에서 가장 흔한 결함이 인증과 인가를 헷갈린 것입니다: 인증(AuthN)은 "너 누구야?"를 확인하고 인가(AuthZ)는 "그래서 이걸 해도 돼?"를 결정하는데 — "로그인했으니 다 허용"이라 착각하거나 정체성만 확인하고 특정 객체/행위 권한을 안 보면 그게 IDOR(객체수준)·BFLA(함수수준), 곧 Broken Access Control(OWASP 1위)입니다. 내 HSPACE PII 케이스가 정확히 그거였고요. Android도 똑같아서, 커널이 각인한 호출자 UID로 "누구"는 위조 불가로 알지만 그걸로 권한을 검사하는 건 별개이며, `checkCallingOrSelfPermission`의 `OrSelf` 폴백이면 자기 정체성으로 조용히 통과합니다. 다음은 이 구분을 떠받치는 설계 원칙 **C03(최소권한·완전중재·심층방어)**으로 이어집니다.
