---
layout: post
title: "Android Security Concept Atlas C25 - isolatedProcess·app zygote, 최강 인앱 샌드박스"
date: 2026-09-25 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, isolatedProcess, appZygote, ZygotePreload, Sandbox, WebViewRenderer, isolatedapp, ConceptAtlas, 학습기록]
excerpt: "위험한 코드(파서, 웹 렌더러)를 돌려야 할 때 Android가 주는 가장 강한 인앱 샌드박스가 isolatedProcess입니다. android:isolatedProcess=true 서비스는 앱의 UID가 아니라 버려지는 격리 UID로, isolated_app이라는 훨씬 빡빡한 SELinux 도메인에서 돌죠 - 앱의 사적 데이터도, 대부분의 시스템 서비스도, 네트워크도, GPU도 못 건드리고, 유일한 통로는 자신을 띄운 앱으로 돌아가는 Binder 하나뿐입니다. 설계 원칙이 '이 코드는 어차피 뚫린다고 가정하고, 뚫려도 쓸모없는 프로세스로 만든다'예요. Chrome/WebView 렌더러가 이걸로 돕니다. app zygote(A10+)는 그런 격리 워커를 여럿 싸게 찍어내는 최적화고요. C24의 프리미티브를 극단으로 조인 Tier 4 마무리 모듈입니다."
---

> **Concept Atlas 모듈**: C25 — isolatedProcess·app zygote
> **계층**: Tier 4 (플랫폼 격리) · **난이도**: 고급 · **선수 개념**: C09(UID), C12(zygote), C24(격리층)
> **성격**: 미학습 편.

C24에서 seccomp·caps·SELinux가 앱 샌드박스를 겹겹이 두른다 했습니다. 이 편은 그것을 **극단으로 조인** 최강 인앱 샌드박스 — 위험한 코드를 "어차피 뚫린다"고 가정하고 담는 그릇입니다.

한 문장으로: **isolatedProcess는 버려지는 격리 UID·isolated_app 도메인에서 돌며 앱으로 돌아가는 Binder 하나 말고는 아무것도 못 건드리는, 뚫려도 쓸모없는 워커다.** 🔴이지만 핵심에 집중합니다.

## 배경 개념

- **isolatedProcess**: `android:isolatedProcess="true"` 서비스 → **격리 UID**·isolated_app 도메인, 권한 거의 0.
- **유일 통로**: 자신을 띄운 앱으로 돌아가는 **Binder(AIDL/Messenger)** 하나.
- **app zygote**(A10/API29): 격리 워커를 여럿 싸게 찍어내는 per-app zygote.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**최강 인앱 샌드박스 티어**입니다. C24의 프리미티브(seccomp·caps·SELinux)를 극단으로 조여, 위험/미신뢰 코드(파서·렌더러)를 담습니다. C09(격리 UID)·C12(app zygote)·C23(isolated_app)·C34(GPU 차단)와 직결.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **isolatedProcess**(API 16~): `<service android:isolatedProcess="true">`가 **자기 프로세스**에서, 앱의 10000+ UID가 아닌 **버려지는 격리 UID**로 실행. 격리 UID는 **두 범위**:
  - 시스템 zygote에서 fork된 격리 자식: **99000–99999**(`AID_ISOLATED_START..END`).
  - **app zygote**에서 fork된 격리 자식: **90000–98999**.
- **봉쇄**: isolated_app SELinux 도메인(untrusted_app보다 훨씬 빡빡), 권한 거의 0, 대부분의 servicemanager 서비스 도달 불가, 네트워크·GPU(C34) 불가. **단** 파일시스템이 "전무"는 아님 — 앱의 **사적 데이터(app_data_file)는 못 열지만** 자기 APK·world-readable 시스템 파일은 읽습니다.
- **통로**: 앱이 `bindService`로 바인드한 **Binder(AIDL/Messenger)** 하나가 유일 채널.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **설계 원칙**: "이 코드는 어차피 뚫린다고 가정하고, 뚫려도 **쓸모없는** 프로세스로 만든다." 익스플로잇 성공 시 공격자는 앱 데이터·서비스 없는 버려지는 UID에 착지.
- **신뢰하면 안 되는 것들**:
  - **"isolatedProcess는 `android:process=":x"` 같은 프로세스 분리일 뿐"** — 아닙니다. `:x`는 **같은 앱 UID·데이터 공유**, isolatedProcess는 **별도 격리 UID·데이터 없음**.
  - **"isolated는 untrusted_app 도메인"** — **isolated_app**(훨씬 빡빡: 앱 파일 접근 없음·GPU 없음·임의 서비스 없음·네트워크 없음).
  - **"권한만 적을 뿐 IPC는 넓게 가능"** — 대부분 시스템/Binder 서비스에 **아예 못 닿습니다**. 유일 채널은 호스트 앱으로의 Binder.
  - **"파일시스템 접근이 전혀 없다"** — 앱의 **사적 데이터**는 못 열지만 자기 APK·world-readable은 읽습니다(코드 실행에 필요).
  - **"isolated의 추가 봉쇄는 더 빡빡한 seccomp"** — 주된 구별 봉쇄는 **isolated_app 도메인 + 격리 UID + 무권한/무네트워크**입니다(seccomp/caps-drop은 이미 모든 앱의 기본).
  - **"app zygote 공유가 샌드박스를 약화"** — 아닙니다. 공유 부모(app zygote) 자체가 비특권·격리입니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 앱이 `bindService`로 격리 서비스 바인드. (app zygote면 `android:useAppZygote="true"` on `<service>` + `android:zygotePreloadName` on `<application>`(=`ZygotePreload` 구현) → per-app 자식 zygote가 `doPreload()`로 앱 코드 1회 preload.)
- **동작**: 격리 워커가 위험 계산 수행. app zygote면 여러 격리 자식이 preload 코드를 **COW 공유**(빠른 시작·메모리 절감).
- **출력**: 결과를 Binder로 호스트 앱에 반환.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **봉쇄의 목적**: 파서·렌더러 코드실행(RCE) 버그를 **저가치 발판**으로 전환. 뚫려도 앱 데이터·서비스·네트워크·GPU가 없어 후속 상승이 막힘.
- **실제 사용**: **Chrome/Android System WebView 렌더러**가 isolatedProcess(미신뢰 웹 콘텐츠) — 브라우저 다중프로세스 샌드박스의 Android판. (단 렌더러/유틸리티 서비스가 isolated이지 **GPU 프로세스는 isolated 아님**.) 미디어 추출/트랜스코딩 샌드박스도.
- **감사 표면**: 격리 워커의 유일 egress가 그 **하나의 AIDL**이라, 공격 표면은 넓은 시스템 서비스가 아니라 그 인터페이스로 좁혀집니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **isolatedProcess**: API 16/A4.1(2012)부터.
- **app zygote**(`useAppZygote`/`zygotePreloadName`/`ZygotePreload`): **A10/API29**(2019).
- 격리 UID 범위: 시스템 zygote 99000–99999 / app zygote 90000–98999.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ps -A`(격리 프로세스는 **`u0_iXX`**, i=isolated; 일반 앱은 `u0_aXX`), `ps -Z`(SELinux 컨텍스트 `u:r:isolated_app:s0`), `dumpsys activity processes`(격리 + app zygote).
- **소스**: AOSP `android_filesystem_config.h`(격리 UID), `frameworks/base` ActivityManagerService/ProcessList(격리 UID 할당·`mNextIsolatedProcessUid`), sepolicy `isolated_app.te`, `android.app.ZygotePreload`.

**주의**: 아키텍처 무관 → **에뮬레이터로 WebView 페이지 띄우고 `ps -AZ | grep u0_i`로 격리 렌더러 실측 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C24(격리층)**: 같은 seccomp·caps·SELinux 프리미티브를 극단으로 조인 것.
- **C09(UID)**: 격리 UID(90000–99999)가 그 UID 체계의 특수 구간.
- **C12(zygote)**: app zygote가 그 fork 트리의 per-app 자식.
- **C23(SELinux)**: isolated_app 도메인이 핵심 봉쇄.
- **C34(드라이버)**: 격리는 GPU 미접근.
- 다음은 다른 티어(토대 Tier 0 잔여·앱통제 Tier 8 등)로.

## 직접 그릴 수 있는 호출 흐름

```
[ isolatedProcess: 뚫려도 쓸모없는 워커 ]

  앱(UID 10xxx) ──bindService──▶ isolated 서비스
       │  자기 프로세스, 격리 UID:
       │    시스템 zygote 자식 → 99000–99999
       │    app zygote 자식   → 90000–98999
       ▼
  isolated_app 도메인 (untrusted_app보다 빡빡):
     ✗ 앱 사적 데이터  ✗ 대부분 서비스  ✗ 네트워크  ✗ GPU(C34)
     ✓ 자기 APK·world-readable만
     유일 통로 = 호스트 앱으로 돌아가는 Binder(AIDL) 하나

  app zygote(A10+): useAppZygote + zygotePreloadName(ZygotePreload)
     → 앱 코드 1회 preload → 격리 자식들 COW fork (싸게 다수)

  실사용: Chrome/WebView 렌더러 = isolatedProcess (GPU 프로세스는 제외)
```

## 오개념 판별 문제 5개

1. "isolatedProcess는 `android:process=":x"`처럼 앱을 다른 프로세스로 쪼개는 것과 같다."
2. "격리 프로세스는 일반 앱과 같은 untrusted_app SELinux 도메인에서 돈다."
3. "격리 프로세스는 권한만 적을 뿐, 여전히 시스템 서비스에 두루 접근할 수 있다."
4. "app zygote로 코드를 공유하면 격리 프로세스의 샌드박스가 약해진다."
5. "isolatedProcess 프로세스는 파일시스템에 전혀 접근할 수 없다."

<details><summary>판정 기준(펼치기)</summary>

1. `:x`는 **같은 앱 UID·데이터 공유**, isolatedProcess는 **별도 격리 UID·데이터 없음**입니다.
2. **isolated_app** 도메인입니다(훨씬 빡빡: 앱 파일·GPU·임의 서비스·네트워크 없음).
3. 대부분 시스템/Binder 서비스에 **아예 못 닿습니다**. 유일 통로는 호스트 앱 Binder.
4. 공유 부모(app zygote)가 **비특권·격리**라 약해지지 않습니다.
5. 앱 **사적 데이터**는 못 열지만 자기 APK·world-readable은 읽습니다.
</details>

## 서술형 문제 3개

1. isolatedProcess의 봉쇄(격리 UID·isolated_app·무권한·유일 Binder 통로)가 왜 "뚫려도 쓸모없는 워커"를 만드는지 서술하세요.
2. isolatedProcess와 `android:process=":x"` 분리의 차이(UID·데이터 공유)를 서술하세요.
3. app zygote가 무엇을 최적화하고 왜 샌드박스를 약화하지 않는지, WebView 렌더러 사용을 예로 서술하세요.

## 소스 탐색 과제

- 에뮬레이터에서 WebView 페이지를 띄우고 `ps -AZ | grep u0_i`로 격리 렌더러와 그 SELinux 컨텍스트(`isolated_app`)를 확인하세요.
- 그 격리 UID가 99000–99999(시스템 zygote) 또는 90000–98999(app zygote) 중 어디인지 판정하세요.
- 일반 앱(`u0_aXX`)과 격리(`u0_iXX`)의 접근 가능 서비스 차이를 서술하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **격리 실측**: `ps -AZ`로 WebView 렌더러의 `u0_iXX`·`isolated_app`을.
2. **UID 판정**: 격리 UID 범위로 시스템 zygote vs app zygote를.
3. **봉쇄 서술**: 격리가 못 닿는 것(데이터/서비스/네트워크/GPU)과 유일 Binder 통로를.
4. **연결**: 이것이 C24 프리미티브를 어떻게 극단화한 것인지.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

위험한 코드(파서·웹 렌더러)를 돌려야 할 때 Android가 주는 가장 강한 인앱 샌드박스가 isolatedProcess입니다: 앱 UID가 아니라 버려지는 격리 UID(시스템 zygote 99000–99999 / app zygote 90000–98999)로, untrusted_app보다 훨씬 빡빡한 isolated_app 도메인에서 돌며 — 앱 사적 데이터·대부분 서비스·네트워크·GPU를 못 건드리고 유일 통로는 호스트 앱으로 돌아가는 Binder 하나뿐입니다(자기 APK·world-readable은 읽지만). 설계 원칙은 "어차피 뚫린다고 가정하고 뚫려도 쓸모없게 만든다"이고, Chrome/WebView 렌더러가 이걸로 돕니다. app zygote(A10+)는 그런 격리 워커를 COW로 싸게 찍어내는 최적화이고요. 이로써 Tier 4(플랫폼 격리)를 닫습니다. 다음은 토대 Tier 0의 잔여(C02·C03) 또는 앱 통제 Tier 8로 이어집니다.
