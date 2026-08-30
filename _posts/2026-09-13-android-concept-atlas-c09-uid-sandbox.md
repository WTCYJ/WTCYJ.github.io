---
layout: post
title: "Android Security Concept Atlas C09 | 가상 실습 보고서 — UID·sharedUserId·앱 샌드박스, 격리의 1차 경계"
date: 2026-09-13 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, UID, appId, sharedUserId, Sandbox, DAC, isolatedProcess, PackageManager, ConceptAtlas, 학습기록]
excerpt: "Android 앱 샌드박스의 심장은 권한 대화상자도 SELinux 라벨도 아니라, 리눅스 커널의 UID 기반 DAC입니다 - 설치 때 PackageManager가 앱마다 고유 UID(appId, 10000~19999)를 주고, /data/data/<pkg>를 그 UID 소유로 만들면, 커널이 open/stat마다 소유 UID를 확인해 다른 앱이 못 읽게 막죠. 멀티유저는 uid=userId×100000+appId로 같은 앱을 프로필별로 가릅니다. sharedUserId는 같은 키로 서명한 앱들을 한 UID로 묶던 레거시(A10 폐기)라 샌드박스를 넓히고, isolatedProcess는 99000~99999의 버려지는 UID로 가장 좁힙니다. DAC·SELinux MAC·seccomp는 별개의 세 층 - 이걸 뭉뚱그리지 않는 게 이 편의 핵심입니다. C04 위에 정체성을 얹는 Atlas의 밑변 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r` |
| 관측 결과 | 증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다. |
| 검증 한계 | AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다. |

![C09 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/apps.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C09 — UID·sharedUserId·앱 샌드박스
> **계층**: Tier 1 (앱·패키징) · **난이도**: 중급 · **선수 개념**: C04(프로세스), C05(EL)
> **성격**: 보완 편.

C04에서 Android 앱이 평범한 Linux 프로세스라 했습니다. 이 편은 그 프로세스에 **정체성(UID)**을 부여해 샌드박스를 만드는 층입니다 — C10(권한)·C11(가시성)·C17(Binder 호출자 UID)·C43(per-user 저장)이 전부 여기서 갈립니다.

한 문장으로: **앱 샌드박스의 1차 경계는 권한 대화상자도 SELinux 라벨도 아니라, 리눅스 커널의 UID 기반 DAC다** — 앱마다 고유 UID를 주고 커널이 파일 소유 UID를 검사한다. 🟡 보완이라 핵심에 집중합니다.

## 배경 개념 - 세 층의 격리

- **DAC(이 편)**: 커널 UID/GID 소유권. 임의적(owner가 mode 설정)·베이스라인.
- **MAC(C23)**: SELinux. 강제적·우회 불가(root도 정책에 묶임).
- **seccomp**: 시스템 콜 표면 필터(C04).
- 접근은 **DAC ∧ MAC ∧ seccomp** 전부 통과해야 하며, 하나만 거부해도 막힙니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**Android 격리의 심장**입니다. C04의 프로세스에 UID라는 정체성을 얹어, 앱↔앱 경계를 만듭니다. 그 위에 C10(권한은 UID에 부여)·C11(패키지 가시성)·C17(Binder 호출자 검사는 커널 uid로)·C23(SELinux는 별개 강제층)·C43(per-user CE 저장 `/data/user/N`)이 서 있습니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **설치 시**: `PackageManager`가 앱마다 **고유 appId**를 `AID_APP_START=10000`부터 할당(설치 앱 범위는 **10000~19999**, `AID_APP_END`). `/data/system/packages.xml`·`packages.list`에 영속.
- **실행 시**: 앱은 그 UID로 EL0에서 실행. `ps -A`에 **`u0_aXX`**(user 0, XX=appId−10000)로 표시.
- **멀티유저/워크프로필**: 실제 커널 uid = **`userId × 100000 + appId`**(`PER_USER_RANGE=100000`). appId 10123은 user 0에선 10123, user 10에선 1010123.
- **시스템 AID**(`android_filesystem_config.h`): root=0, system=1000, radio=1001, shell=2000 — 전부 10000 미만이라 앱에 안 쓰임.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **앱↔앱 1차 경계 = UID DAC**: `/data/data/<pkg>`(= `/data/user/0/<pkg>`)가 앱 UID 소유(보통 0700)라, 커널이 **모든 `open()`/`stat()`에서 소유 UID를 검사**해 다른 UID의 사적 파일 접근을 물리적으로 막습니다. 임의적(owner가 설정)이고 베이스라인.
- **DAC ≠ SELinux**: DAC 위에 **강제적** SELinux MAC(C23, root도 정책에 묶임) + seccomp가 얹힙니다. 셋은 **별개 층**입니다.
- **신뢰하면 안 되는 것들**:
  - **"`/data/data`가 `/data/user/0`의 심링크"** — 방향이 반대입니다. **`/data/data`가 실제 디렉터리**, `/data/user/0`이 그걸 가리키는 심링크(`ls -la /data/user` → `0 -> /data/data`).
  - **"공유 UID는 `u0_sXX`로 보인다"** — 그런 버킷은 없습니다. sharedUserId 앱들도 한 appId(10000+)를 공유해 **동일한 `u0_aXX`**로 표시됩니다. 실재하는 별도 버킷은 `u0_iXX`(isolated)·`all_aXXX`(공유 GID)이고, 플랫폼 공유 ID는 심볼릭 이름(예: `system`)으로.
  - **"uid≥10000이면 앱"** — 설치 앱은 **10000~19999만**입니다. isolated는 99000~99999, 공유 GID는 50000~59999, 캐시는 20000~29999.
  - **"샌드박스 = SELinux"** 또는 **"appId = uid"** — 1차 경계는 UID DAC(SELinux는 별개 강제층), uid는 `userId×100000+appId`의 **합성값**(appId는 그 성분).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 서명(C08)·매니페스트 → PMS가 appId 할당(sharedUserId면 공유 appId).
- **출력**: 프로세스 UID + 데이터 디렉터리 소유권. Binder 호출자 검사(C17)는 커널 uid를 받아 `UserHandle.getUserId(uid)`/`getAppId(uid)`로 사용자·appId를 복원.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **sharedUserId**: 같은 키로 서명한 앱 여럿을 **한 UID로 병합** → 한 앱의 침해가 그룹 전체의 사적 데이터·프로세스에 도달합니다. 게다가 나중에 UID를 안전히 쪼갤 수 없어(데이터 고아화) **비가역 병합**이자 마이그레이션 함정.
- **부적절한 권한**: world-readable로 만든 사적 파일, 느슨한 mode → UID 경계를 앱 스스로 뚫음.
- **isolatedProcess**: 반대로 가장 좁힌 샌드박스(버려지는 UID, 권한 거의 0) — 렌더러 등 신뢰 못 할 코드 격리.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **sharedUserId 폐기**: **API 29 / Android 10**부터 deprecated(신규 앱 채택 제한).
- **`android:sharedUserMaxSdkVersion`**: **API 33 / Android 13** 추가 — 새 기기 신규 설치는 독립 UID를 받되 기존 설치는 공유 UID 유지(마이그레이션 경로).
- **isolated 범위**: `AID_ISOLATED_START=99000`~99999.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `ps -A`(`u0_aXX`=앱, `u0_iXX`=isolated, `system`/`shell`=심볼릭), `dumpsys package <pkg>`(`userId=<appId>`·`dataDir`·`sharedUser=`), `stat`/`ls -n /data/data/<pkg>`(숫자 uid 소유권).
- `/data/system/packages.xml`·`packages.list`(uid↔패키지 레지스트리·sharedUserId 그룹).
- **소스**: `system/core/libcutils/include/private/android_filesystem_config.h`(AID 상수), `frameworks/base/.../os/UserHandle.java`(`getUid/getUserId/getAppId`, `PER_USER_RANGE`).

**주의**: UID 샌드박스는 아키텍처 무관이라 **에뮬레이터로 `ps`·`dumpsys package`·`packages.xml` 실측 가능**(단 `/data/data`는 루팅/디버그 앱 컨텍스트라야 내부 확인).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C04(프로세스)**: 이 UID가 바로 그 프로세스에 얹히는 정체성.
- **C05(EL)**: DAC 검사는 EL1 커널에서, 앱은 EL0.
- **C10(권한)·C11(가시성)**: 권한은 UID/appId에 부여됩니다.
- **C17(Binder)**: 호출자 검사가 커널 uid로 이뤄집니다.
- **C23(SELinux)**: MAC은 이 DAC 위의 **별개 강제층** — 뭉뚱그리지 말 것.
- **C43(FBE)**: per-user CE 저장 `/data/user/N/<pkg>`이 이 UID 소유.
- 다음은 이 UID에 무엇을 허가하는지인 **C10(permission·AppOps)** 또는 다른 티어로.

## 호출 흐름

```
[ UID 샌드박스: 설치 → 실행 → 격리 ]

  설치: PMS가 appId 할당(10000~19999) ─▶ packages.xml 영속
  실행: 앱 프로세스가 uid = userId×100000 + appId 로 (EL0)
         ps: u0_aXX(앱) / u0_iXX(isolated 99000~) / system(1000)

  격리(3층, 전부 통과해야):
    ① DAC  : 커널이 /data/data/<pkg>(앱UID 0700) open/stat마다 소유UID 검사
    ② MAC  : SELinux(C23) 강제 라벨 — root도 묶임 (별개 층)
    ③ seccomp: 시스템 콜 표면 필터(C04)

  sharedUserId(레거시,같은키): 앱 여럿 → 한 UID(샌드박스 병합, A10 폐기)
```

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, Android 13/API 33, Google APIs x86_64)에서 이 모듈의 핵심 불변식을 실제로 확인했다. UID 샌드박스는 아키텍처 무관이라 이 x86_64 AVD에서도 설치·등록 경로가 그대로 관측된다.

**1) 설치 = 서명 검증 → PMS의 UID 등록.** 증거 앱 APK를 직접 빌드해 v2/v3 서명을 검증한 뒤 설치했고, Package Manager가 그 앱을 **별도 UID로 등록**했다.

```console
$ apksigner verify --print-certs app.apk
$ adb install -r app.apk
```

이 한 줄이 질문 2(설치 시 PMS가 고유 appId 할당)와 질문 4의 입력→출력(서명·매니페스트 → 프로세스 UID + 데이터 디렉터리 소유권)을 동시에 확증한다. 서명 검증이 설치보다 **앞서** 성공한다는 사실이 곧 질문 3의 오개념 5("다른 키로도 묶인다")를 반증한다 — appId를 키잉하는 신뢰 근거는 서명(C08)이다.

**2) 앱마다 별도 UID = 앱↔앱 1차 경계.** 상단 검증 화면([apps.png](/assets/img/android-concept-atlas/verified-api33/apps.png))의 값은 실행 중인 앱 프로세스에서 수집해 호스트 `adb shell` 결과와 교차 확인했고, 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 보존했다. "앱을 별도 UID로 등록"은 질문 1·질문 3의 핵심 불변식 그 자체다 — 앱마다 고유 UID가 있어야 커널이 `/data/data/<pkg>`의 소유 UID를 `open()`/`stat()`마다 검사해 다른 UID의 사적 파일을 막을 수 있다. 관측된 UID 경계가 이 DAC 검사가 설 토대다.

## 가상환경 검증 한계

정직하게, 이 세션의 실측은 위 (1)·(2)까지다. 이 모듈의 나머지 사실은 근거(소스·문서)로 확정했으나 이 AVD에서 새로 캡처하지는 않았다.

- **`/data/data/<pkg>`의 숫자 uid 소유권과 0700 mode를 직접 캡처하지 않았다.** 내부 소유권 확인(`ls -n /data/data/<pkg>`)은 루팅·디버그 앱 컨텍스트라야 가능해, 이 세션은 커널의 파일 소유 UID 검사를 "별도 UID 등록"에서 추론했을 뿐 per-file mode를 열람하지 않았다.
- **멀티유저 합성 uid를 실측하지 않았다.** 이 AVD는 user 0만 있어, `uid = userId×100000 + appId`로 같은 appId가 user 10에서 `1010123`이 되는 것은 소스(`UserHandle.PER_USER_RANGE`)로 확인했을 뿐 두 번째 프로필에서 관측하지 않았다.
- **sharedUserId 그룹을 packages.xml에서 열거하지 않았다.** API 29(Android 10)부터 deprecated인 레거시라 이 증거 앱에는 없고, 병합의 샌드박스 확대·비가역성은 문서·소스 근거로만 서술했다. AAB의 Play 서버 변환과 Play App Signing도 검증 블록대로 로컬 Google APIs AVD로는 재현하지 않았다.

관련 근거: [Android App Sandbox](https://source.android.com/docs/security/app-sandbox) · [android_filesystem_config.h (AID 상수)](https://cs.android.com/android/platform/superproject/+/master:system/core/libcutils/include/private/android_filesystem_config.h) · [UserHandle.java (PER_USER_RANGE·getAppId)](https://cs.android.com/android/platform/superproject/+/master:frameworks/base/core/java/android/os/UserHandle.java) · [&lt;manifest&gt; android:sharedUserId](https://developer.android.com/guide/topics/manifest/manifest-element)

## 마치며

Android 앱 샌드박스의 심장은 권한 대화상자도 SELinux 라벨도 아니라 **리눅스 커널의 UID 기반 DAC**입니다: PackageManager가 앱마다 고유 UID(appId, 10000~19999)를 주고, `/data/data/<pkg>`를 그 UID 소유로 만들면, 커널이 파일 접근마다 소유 UID를 검사합니다. 멀티유저는 `uid=userId×100000+appId`로 프로필을 가르고, sharedUserId는 같은 키로 서명한 앱들을 한 UID로 병합해 샌드박스를 넓히며(A10 폐기), isolatedProcess는 버려지는 UID(99000~)로 가장 좁힙니다. 그리고 DAC·SELinux MAC(C23)·seccomp는 **뭉뚱그리면 안 되는 별개의 세 층**입니다. 이 UID 위에 다음 편 **C10(권한·AppOps)**이 "이 UID에 무엇을 허가할까"를 얹습니다.
