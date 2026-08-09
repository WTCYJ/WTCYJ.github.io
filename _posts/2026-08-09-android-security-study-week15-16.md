---
layout: post
title: "Android 앱 보안 분석 15~16주차 - Binder 경계와 SELinux, 그리고 패치 수준"
date: 2026-08-09
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 시스템보안, Binder, servicemanager, SELinux, MAC, AVC, VerifiedBoot, 보안패치수준, SecurityBulletin, adb, 에뮬레이터, 학습기록]
excerpt: "앱이 아니라 앱을 담고 있는 플랫폼을 봤습니다. 같은 호출을 shell과 앱 UID에서 각각 시도해 Binder 경계가 두 겹으로 동작하는 것을 확인했고, API 33과 16을 나란히 놓고 패치 수준과 SELinux 정책을 비교했습니다. adb shell로 경계를 재려다 세 번째로 같은 함정을 밟은 이야기도 함께 적었습니다."
---

> **진행 구간**: 24주 로드맵의 15~16주차 (Android 시스템 보안)
> **대상**: AVD `sec-api33`(Android 13) / `sec-api36`(Android 16) 두 대 비교
> **원칙**: 관측만 하고 시스템을 변경하지 않음
> **이전 글**: [13~14주차 네이티브·런타임](/posts/android-security-study-week13-14/) · [11~12주차](/posts/android-security-study-week11-12/) · [24주 로드맵](/posts/android-security-study-roadmap/)

---

이 글은 24주 Android 보안 학습 로드맵의 15~16주차, 시스템 보안 구간 기록입니다.

지금까지 열네 주 동안은 앱 하나를 놓고 그 앱이 스스로 연 문을 봤습니다. 이번 구간은 **그 앱을 담고 있는 플랫폼**을 봅니다. 1~2주차에 앱 샌드박스가 DAC와 SELinux 두 겹이라는 것까지 확인했는데, 그 위에 무엇이 더 있는지가 이번 주제입니다. 이 글에서는 Binder 경계를 두 권한 수준에서 재본 실험과, Android 13과 16을 나란히 놓고 비교한 결과를 살펴보겠습니다.

---

## 배경 개념 - Binder, servicemanager, 그리고 강제 계층

먼저 이번 구간의 용어를 정리하겠습니다.

**Binder**는 Android의 프로세스 간 통신(IPC) 메커니즘입니다. 앱이 화면을 띄우거나 위치를 얻거나 알림을 보내는 일은 전부 자기 프로세스 안에서 처리되지 않고, `system_server` 같은 다른 프로세스의 **시스템 서비스**에 요청해서 이루어집니다. 그 요청이 오가는 통로가 Binder이고, 커널 드라이버(`/dev/binder`)가 중개합니다.

**servicemanager**는 시스템 서비스의 전화번호부에 해당합니다. 서비스들이 자기 이름을 여기 등록해두고, 앱은 이름으로 조회해 핸들을 얻은 뒤 호출합니다. **조회 단계가 따로 있다는 점이 이번 구간에서 중요합니다.**

**SELinux**는 파일 소유권 기반 접근 제어(DAC) 위에 얹히는 강제 접근 제어(MAC)입니다. 프로세스에는 도메인(`u:r:untrusted_app:s0` 같은 것), 객체에는 타입 레이블이 붙고, 정책이 허용한 조합만 통과합니다. 거부되면 `avc: denied` 로그가 남습니다.

**Verified Boot**는 부팅 각 단계의 무결성을 검증하고 구버전으로의 롤백을 막는 부트 체인 보호입니다.

**보안 패치 수준**은 이 빌드에 어느 시점까지의 보안 수정이 들어갔는지를 나타내는 날짜입니다. Android Security Bulletin이 매달 이 날짜 단위로 수정 사항을 공개하므로, CVE 대응 여부를 판단하는 기준선이 됩니다.

---

## 1. 실습 환경과 준비 - 두 API 레벨 나란히 놓기

1~2주차에 만들어두고 한 번도 띄우지 않았던 `sec-api36` 을 이번에 처음 부팅했습니다. 두 버전을 비교하려는 목적입니다.

| | `sec-api33` | `sec-api36` |
| --- | --- | --- |
| Android | 13 | 16 |
| 보안 패치 수준 | 2024-03-01 | 2025-07-05 |

`sec-api36` 은 부팅 후 아무것도 설치하기 전에 `clean` 스냅샷을 떴습니다. 로드맵 환경 체크리스트에 있던 항목인데 이제야 채웠습니다.

관측은 `tools/observe-system.sh` 로 자동화했습니다. 이 스크립트는 **읽기만 합니다.** 시스템 속성, SELinux 상태, Binder 서비스 목록, 그리고 경계가 실제로 동작하는지 확인하는 비파괴적 호출까지가 전부입니다.

---

## 2. 수행 절차 - 두 권한 수준에서 같은 호출

두 기기에서 같은 스크립트를 돌려 빌드 지문과 패치 수준, Verified Boot 속성, SELinux 상태와 컨텍스트, 서비스 목록을 수집했습니다.

이번 구간의 핵심 실험은 마지막 항목입니다. **같은 명령을 `adb shell`(uid 2000)과 일반 앱 UID에서 각각 시도**했습니다.

9~10주차에 `am start` 로 배운 대로 `adb shell` 은 특권 계정이라 경계 측정에 쓰면 안 됩니다. 그래서 `run-as` 로 앱 UID까지 내려가 같은 호출을 반복했습니다.

---

## 3. 관측 결과

### 3-1. 보안 패치 수준은 하나가 아니다

`adb shell getprop ro.build.version.security_patch` 로 읽은 값이 설정 화면에도 그대로 나타납니다.

![Android 16 기기의 버전 상세 화면입니다. Android version 16, Android security update July 5 2025, Google Play system update May 1 2025, Baseband version 1.0.0.0, 커널 버전 6.6.66, 빌드 번호가 표시돼 있습니다](/assets/img/android-security-study/16-android16-patch.png)

![Android 13 기기의 같은 화면입니다. Android version 13, Android security update March 1 2024, Google Play system update May 1 2023, 커널 버전 5.15.119, 빌드 번호가 표시돼 있습니다](/assets/img/android-security-study/17-android13-patch.png)

**패치 수준이 두 개로 나뉘어 있습니다.** 플랫폼 패치와 Google Play 시스템 업데이트(Mainline 모듈)가 따로 갱신됩니다.

| | API 33 | API 36 |
| --- | --- | --- |
| Android security update | 2024-03-01 | 2025-07-05 |
| Google Play system update | 2023-05-01 | 2025-05-01 |
| 커널 | 5.15.119 | 6.6.66 |

두 축이 독립적으로 움직인다는 것이 API 33 쪽에서 분명히 드러납니다. **플랫폼 패치는 2024년 3월인데 Play 시스템 업데이트는 2023년 5월로, 10개월이나 뒤처져 있습니다.** CVE를 추적할 때 "이 기기가 패치됐는가"는 어느 축에 속한 수정인지까지 봐야 답할 수 있습니다. 18주차에 CVE를 고를 때 쓰게 될 기준입니다.

### 3-2. SELinux

| 항목 | API 33 | API 36 |
| --- | --- | --- |
| 강제 모드 | `Enforcing` | `Enforcing` |
| 정책 버전 | 33 | 33 |
| 객체 클래스 수 | 103 | **107** |
| `init` | `u:r:init:s0` | `u:r:init:s0` |
| `zygote` | `u:r:zygote:s0` | `u:r:zygote:s0` |
| `system_server` | `u:r:system_server:s0` | `u:r:system_server:s0` |
| 앱 프로세스 | `u:r:untrusted_app:s0:c137,…` | `u:r:untrusted_app:s0:c153,…` |

**정책 언어 버전은 33으로 같은데 객체 클래스 수는 늘었습니다.** 정책 파일 형식이 같아도 정책이 다루는 대상은 계속 추가된다는 뜻입니다. 버전 숫자만 보고 "같은 정책"이라고 판단하면 안 됩니다.

프로세스 도메인이 역할별로 갈려 있는 것도 확인됩니다. `init`, `zygote`, `system_server`, `untrusted_app` 이 각각 다른 도메인이고, 앱에만 MLS 카테고리가 붙습니다.

### 3-3. Binder 경계는 두 겹이다

등록된 system service 수가 **256 → 318** 로 늘었습니다.

핵심 실험 결과입니다. 같은 명령을 두 권한 수준에서 실행했습니다.

| 호출 | `adb shell` (uid 2000) | 앱 UID (`run-as`) |
| --- | --- | --- |
| `cmd stats print-stats` | 정상 출력 | **`Can't find service: stats`** |
| `cmd package install-create` | 세션 생성 성공 | **`SecurityException: … requires INTERACT_ACROSS_USERS_FULL`** |

두 실패의 성격이 다릅니다.

**첫째는 서비스를 찾지 못합니다.** 호출이 거부된 것이 아니라 **핸들 자체를 못 얻습니다.** 이때 남은 SELinux 로그입니다.

```
avc: denied { find } for pid=14740 uid=10176 name=stats
     scontext=u:r:runas_app:s0:c176,c256,c512,c768
     tcontext=u:object_r:stats_service:s0
     tclass=service_manager permissive=0
```

객체 클래스가 `service_manager`, 권한이 `find` 입니다. **서비스 조회 단계에서 SELinux가 막습니다.**

**둘째는 서비스를 찾았고 호출도 전달됐는데, 서비스 구현이 거부합니다.** Binder가 호출자의 UID를 함께 전달하고, 서비스가 그 UID의 권한을 확인해 예외를 던집니다.

정리하면 이런 구조입니다.

```
앱 → [1] servicemanager 조회 ── SELinux service_manager:find 검사
        ↓ 통과
     [2] Binder 트랜잭션 ────── 커널이 호출자 UID/PID 를 전달
        ↓
     [3] 서비스 구현 ────────── Android 권한 검사 (SecurityException)
```

`adb shell` 도 모든 서비스를 볼 수 있는 것은 아니었습니다. API 36에서 `netd`, `suspend_control` 조회가 거부됐습니다.

```
avc: denied { find } for pid=3118 uid=2000 name=netd
     scontext=u:r:shell:s0 tcontext=u:object_r:netd_service:s0
     tclass=service_manager permissive=0
```

### 3-4. Verified Boot 는 에뮬레이터에서 안 보인다

| 속성 | API 33 | API 36 |
| --- | --- | --- |
| `ro.boot.verifiedbootstate` | (빈 값) | (빈 값) |
| `ro.boot.veritymode` | `enforcing` | `enforcing` |
| `ro.boot.flash.locked` | (빈 값) | (빈 값) |
| `ro.boot.vbmeta.digest` | `cc2acf6c…24e5` | `7466b5c2…2bd5` |

**부트 상태와 잠금 여부를 에뮬레이터가 보고하지 않습니다.** `vbmeta` 다이제스트와 `veritymode` 는 있지만, 실기기에서 `green`/`yellow`/`orange` 로 나오는 `verifiedbootstate` 는 비어 있습니다.

이 항목은 에뮬레이터에서 제대로 실습할 수 없습니다. 속성이 어디에 있고 무엇을 뜻하는지까지만 확인하고, 실제 검증은 실기기나 Cuttlefish로 미뤘습니다.

---

## 4. 결과 해석

### 4-1. 경계는 한 겹이 아니다

구간별로 확인한 것을 쌓아보면 이렇습니다.

| 층 | 무엇을 막나 | 확인한 구간 |
| --- | --- | --- |
| DAC (파일 소유권) | 다른 앱의 `/data/data` 읽기 | 1~2주차 |
| SELinux MAC (도메인·MLS) | 같은 도메인 앱끼리도 격리 | 1~2주차 |
| SELinux `service_manager:find` | 시스템 서비스 조회 자체 | **이번 구간** |
| Binder + 서비스 권한 검사 | 조회에 성공한 서비스의 개별 호출 | **이번 구간** |
| 앱 컴포넌트 `exported` | 외부 앱의 액티비티 호출 | 7~10주차 |

7~10주차에 확인한 "샌드박스는 멀쩡한데 데이터는 나간다"가 왜 성립하는지도 여기서 정리됩니다. 위 층들은 전부 **앱 밖에서 앱 안으로 들어오는 것**을 막습니다. 앱이 스스로 문을 열고 데이터를 내보내는 것은 이 층들의 관심사가 아닙니다. 플랫폼이 아무리 촘촘해도 앱 자신의 설계 결함은 플랫폼이 대신 막아주지 않습니다.

### 4-2. 플랫폼이 커지면 표면도 커진다

system service 가 256에서 318로 늘었습니다. 각각이 Binder 인터페이스를 노출하고, 그 뒤에 권한 검사 코드가 있습니다. 검사 하나가 빠지면 그것이 권한 상승 취약점이 됩니다. Android Security Bulletin에 framework/system component 항목이 꾸준히 올라오는 이유입니다.

SELinux 객체 클래스가 103에서 107로 는 것도 같은 방향입니다. 새 기능이 생기면 그것을 통제할 클래스가 추가됩니다. **보안 기능이 늘어난 것과 공격 표면이 늘어난 것이 같은 변화의 양면입니다.**

---

## 5. 시행착오와 정정

### `adb shell` 로 경계를 재려다 세 번째로 틀렸다

처음 스크립트는 "권한이 필요한 호출"의 예로 `cmd package install-create` 를 shell 에서 실행하도록 짰습니다. 거부될 것으로 기대했는데 **성공했습니다.**

```
Success: created install session [295587018]
```

`adb shell` 은 `INSTALL_PACKAGES` 를 갖고 있습니다. 9~10주차에 `am start` 가 shell 에서 통과한 것과 정확히 같은 이유이고, 그때 "adb shell 이 성공했다고 제3자 앱도 가능한 건 아니다"라고 적어두기까지 했습니다. **그래놓고 또 같은 자리에서 틀렸습니다.**

`run-as` 로 앱 UID까지 내려가 대조하도록 고쳤고, 그러자 두 종류의 거부가 깔끔하게 갈렸습니다. 기록해두는 것과 다음번에 실제로 적용하는 것은 다른 일이라는 걸 배웠습니다.

덧붙여, 이 실수로 설치 세션이 하나 생겼습니다. 관측만 하기로 해놓고 상태를 바꾼 것이라 `pm install-abandon` 으로 정리했습니다. **비파괴 원칙을 지키려면 "무엇을 만들었는지"도 추적해야 합니다.**

### `ps -A -Z -o LABEL` 은 열이 두 번 나온다

프로세스 컨텍스트를 뽑는데 `init` 컨텍스트가 `u:r:vendor_init:s0` 로 나왔습니다. 실제로는 `u:r:init:s0` 입니다.

원인은 `-Z` 와 `-o LABEL` 을 같이 준 것이었습니다. LABEL 열이 두 번 출력돼 열 번호가 밀렸고, `$4` 로 PID를 찾던 awk가 엉뚱한 값을 집었습니다.

```
LABEL                LABEL                USER   PID NAME
u:r:init:s0          u:r:init:s0          root     1 init
```

출력 형식을 확인하지 않고 열 번호를 가정한 것이 문제였습니다. 값이 그럴듯해서(`vendor_init` 도 실재하는 도메인입니다) 하마터면 그대로 적을 뻔했습니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~14주 | 앱 보안·네이티브 전 구간 | 완료 |
| 15~16주 | Android 시스템 보안 | 완료 |
| 17주 | Cuttlefish 실습 | **환경 준비 필요 (Linux + KVM)** |
| 18주 | CVE 선정·사전 조사 | 대기 |

한계를 적어둡니다. Verified Boot는 에뮬레이터가 부트 상태를 보고하지 않아 속성 확인까지만 했습니다. SELinux 정책 바이너리를 열어 도메인 간 허용 규칙을 나열하는 작업은 하지 않았고, 실행 중 상태와 거부 로그만 봤습니다. `/sys/kernel/debug/binder/` 가 shell 에서도 거부돼 실제 트랜잭션을 관찰하지 못했습니다. 서비스 318개의 개별 인터페이스도 감사하지 않았습니다.

17주차부터는 Linux + KVM 호스트가 필요합니다. 현재 Windows 단독이라 환경을 준비해야 하고, 준비가 늦어지면 18주차 CVE 사전 조사를 먼저 진행하는 것도 방법입니다.

---

## 마치며

이번 구간에서 가장 남는 것은 **거부의 종류가 다르다**는 발견이었습니다.

"권한이 없어서 안 된다"는 한 문장으로 뭉뚱그리기 쉬운데, 실제로는 서비스를 찾지 못하는 것과 찾았지만 호출이 거부되는 것이 완전히 다른 층에서 일어납니다. 앞의 것은 SELinux 정책이고 뒤의 것은 서비스 구현 코드입니다. 취약점을 찾는 입장에서는 이 구분이 중요합니다. 후자는 개발자가 검사를 빠뜨릴 수 있지만 전자는 정책을 고쳐야 하는 일이니까요.

그리고 또 한 번, 측정 도구가 특권을 갖고 있으면 경계가 보이지 않는다는 것을 확인했습니다. 세 번째입니다. 다음 구간부터는 "이 명령을 실행하는 주체가 누구인가"를 먼저 적고 시작하려 합니다.
