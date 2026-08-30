---
layout: post
title: "Android Security Concept Atlas C25 | 가상 실습 보고서 — isolatedProcess·app zygote, 최강 인앱 샌드박스"
date: 2026-09-25 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, isolatedProcess, appZygote, ZygotePreload, Sandbox, WebViewRenderer, isolatedapp, ConceptAtlas, 학습기록]
excerpt: "위험한 코드(파서, 웹 렌더러)를 돌려야 할 때 Android가 주는 가장 강한 인앱 샌드박스가 isolatedProcess입니다. android:isolatedProcess=true 서비스는 앱의 UID가 아니라 버려지는 격리 UID로, isolated_app이라는 훨씬 빡빡한 SELinux 도메인에서 돌죠 - 앱의 사적 데이터도, 대부분의 시스템 서비스도, 네트워크도, GPU도 못 건드리고, 유일한 통로는 자신을 띄운 앱으로 돌아가는 Binder 하나뿐입니다. 설계 원칙이 '이 코드는 어차피 뚫린다고 가정하고, 뚫려도 쓸모없는 프로세스로 만든다'예요. Chrome/WebView 렌더러가 이걸로 돕니다. app zygote(A10+)는 그런 격리 워커를 여럿 싸게 찍어내는 최적화고요. C24의 프리미티브를 극단으로 조인 Tier 4 마무리 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `id`, `cat /proc/self/attr/current`, `/proc/self/status` |
| 관측 결과 | 서로 다른 UID, `untrusted_app` SELinux 컨텍스트, 0 capability, seccomp 필터를 앱 프로세스 내부에서 확인했다. |
| 검증 한계 | 정책 우회나 샌드박스 탈출은 수행하지 않았고, 접근 거부는 실패가 아니라 격리 통제가 작동한 대조군이다. |

![C25 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C25 — isolatedProcess·app zygote
> **계층**: Tier 4 (플랫폼 격리) · **난이도**: 고급 · **선수 개념**: C09(UID), C12(zygote), C24(격리층)
> **성격**: 공식 문서·공개 소스 기준 재검토.

C24에서 seccomp·caps·SELinux가 앱 샌드박스를 겹겹이 두른다 했습니다. 이 편은 그것을 **극단으로 조인** 최강 인앱 샌드박스 — 위험한 코드를 "어차피 뚫린다"고 가정하고 담는 그릇입니다.

한 문장으로: **`isolatedProcess`는 일반 앱 UID와 분리된 ephemeral UID와 제한된 SELinux domain에서 동작해 침해 범위를 줄이지만, Binder 연결과 서비스 구성에 따라 남는 권한을 별도로 검토해야 합니다.**

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

## 호출 흐름

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

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 이 모듈이 "극단으로 조인다"고 말하는 **앱 샌드박스 기준선**을 실제 명령으로 확인했다.

**1) 격리가 조여 들어가는 출발점(untrusted_app 기준선)을 앱 프로세스 내부에서 측정했다.**

```console
$ id
$ cat /proc/self/attr/current
$ cat /proc/self/status
```

관측 결과는 **서로 다른 UID**, **`untrusted_app` SELinux 컨텍스트**, **0 capability**, **seccomp 필터**였다(상단 검증 블록·`evidence-sandbox.png`). 질문 3이 "isolated는 untrusted_app이 아니라 **그보다 빡빡한 isolated_app**"이라고 말할 때의 바로 그 untrusted_app 기준선이 프로세스 메모리 수준에서 확정된 것이다 — isolatedProcess의 추가 봉쇄(앱 사적 데이터 없음·네트워크 없음·GPU 없음·격리 UID)는 이 "before"에서 조여 들어가는 델타로 읽힌다.

**2) 격리 UID 두 범위와 도메인은 AOSP 소스로 고정된다.** 질문 7의 소스 경로 — `android_filesystem_config.h`의 `AID_ISOLATED_START..END`(시스템 zygote 자식 **99000–99999**), ActivityManagerService/ProcessList의 격리 UID 할당(`mNextIsolatedProcessUid`, app zygote 자식 **90000–98999**), sepolicy `isolated_app.te` — 이 세 곳이 격리 UID 범위와 isolated_app 도메인을 정의한다. 이건 이 세션에서 실측한 값이 아니라 소스로 확정한 사실이며, isolatedProcess가 API 16부터, app zygote가 A10/API 29부터라는 버전 경계(질문 6)도 같은 소스 계보에서 나온다.

**3) WebView 격리 렌더러를 찍어내는 부모(webview_zygote)가 시스템 zygote의 자식으로 상주함을 실측했다.**

```console
$ ps -e -o PID,PPID,NAME | grep zygote
  305     1 zygote64
  763   305 webview_zygote
```

시스템 `zygote64`(pid 305)가 init(pid 1)의 자식이고, 그 아래 `webview_zygote`(pid 763)가 자식으로 떠 있다. 질문 5의 "Chrome/Android System WebView 렌더러가 isolatedProcess"라는 실사용 주장의 살아있는 프로세스 쪽 근거다 — WebView의 미신뢰 웹 콘텐츠를 격리 렌더러로 fork하는 전용 zygote가 이 AVD에 실제로 상주한다. (격리 렌더러 자식 자신의 `u0_iXX` 표기와 isolated_app 도메인은 아래 소스 계보로 확정한다.)

**4) 격리가 조여 들어가는 기준선인 "앱 사적 데이터 잠금"을 구체 값으로 실측했다.**

```console
$ dumpsys package com.example.visibilitylegacy | grep userId
    userId=10176
$ ls -la /data/data/com.example.visibilitylegacy
drwx------ 4 u0_a176 u0_a176 4096 2026-08-29 09:48 /data/data/com.example.visibilitylegacy
```

앱의 `/data/data` 디렉터리가 **0700**으로 그 앱 UID(`u0_a176`, userId 10176)에만 열려 있다. 질문 2가 "격리 워커는 앱의 **사적 데이터(app_data_file)는 못 열지만** 자기 APK·world-readable은 읽는다"고 말할 때, 격리 워커가 닿지 못하는 바로 그 사적 데이터가 이 0700 소유 경계다 — 앱 UID와 다른 ephemeral 격리 UID로는 이 경계를 넘지 못한다.

## 소스로 확정한 것

**격리 UID 표기·isolated_app 도메인은 AOSP 소스로 고정된다.** 위 실측 2)에서 짚은 `android_filesystem_config.h`·ActivityManagerService/ProcessList·`isolated_app.te`가 격리 자식의 `u0_iXX`(=`u:r:isolated_app:s0` 도메인, 90000–99999 격리 UID) 표기와 봉쇄 규칙을 정의한다. 실측 3)의 `webview_zygote`가 fork하는 렌더러가 바로 이 도메인·UID로 착지한다.

**ARM64 하드웨어 완화(PAC·BTI·MTE)의 정적 마커는 실측했고, 런타임 강제는 소스로 확정한다.** isolatedProcess는 아키텍처 무관 계약이라 격리 워커 안에서 도는 코드의 하드웨어 완화는 arm64 툴체인으로 확인한다. 실제 arm64 타깃 `.so`를 빌드해 `.note.gnu.property`에서 BTI·PAC 마커를 readelf로 뽑았고, 대조군(`-mbranch-protection=none`)에는 그 note가 0개임을 확인했다:

```console
$ readelf -n libatlas-arm64.so
Displaying notes found in: .note.gnu.property
  GNU                  0x00000010	NT_GNU_PROPERTY_TYPE_0 (property note)
    Properties:    aarch64 feature: BTI, PAC
```

이 마커가 런타임에 강제되는 방식 — PAC의 함수 진입·복귀 포인터 서명, BTI의 간접 분기 랜딩패드, MTE의 메모리 태그 검사 — 은 ARM AArch64 아키텍처와 AOSP 문서로 확정한다.

**무기화는 범위 밖이다.** 격리 워커를 실제 익스플로잇으로 탈출시키는 검증은 이 시리즈의 비무기화 원칙상 다루지 않고, 격리 UID·isolated_app 도메인·유일 Binder egress라는 설계 판정 지점까지만 서술한다.

공식 문서 근거: [`<service>` android:isolatedProcess](https://developer.android.com/guide/topics/manifest/service-element) · [`<application>` android:zygotePreloadName](https://developer.android.com/guide/topics/manifest/application-element) · [ZygotePreload](https://developer.android.com/reference/android/app/ZygotePreload) · [Android 앱 샌드박스](https://source.android.com/docs/security/app-sandbox) · [ARM: PAC/BTI 보호](https://developer.arm.com/documentation/102433/latest) · [Android: ARM MTE](https://source.android.com/docs/security/test/memory-safety/arm-mte) · [readelf(1) — .note.gnu.property](https://man7.org/linux/man-pages/man1/readelf.1.html)

## 마치며

위험한 코드(파서·웹 렌더러)를 돌려야 할 때 Android가 주는 가장 강한 인앱 샌드박스가 isolatedProcess입니다: 앱 UID가 아니라 버려지는 격리 UID(시스템 zygote 99000–99999 / app zygote 90000–98999)로, untrusted_app보다 훨씬 빡빡한 isolated_app 도메인에서 돌며 — 앱 사적 데이터·대부분 서비스·네트워크·GPU를 못 건드리고 유일 통로는 호스트 앱으로 돌아가는 Binder 하나뿐입니다(자기 APK·world-readable은 읽지만). 설계 원칙은 "어차피 뚫린다고 가정하고 뚫려도 쓸모없게 만든다"이고, Chrome/WebView 렌더러가 이걸로 돕니다. app zygote(A10+)는 그런 격리 워커를 COW로 싸게 찍어내는 최적화이고요. 이로써 Tier 4(플랫폼 격리)를 닫습니다. 다음은 토대 Tier 0의 잔여(C02·C03) 또는 앱 통제 Tier 8로 이어집니다.
