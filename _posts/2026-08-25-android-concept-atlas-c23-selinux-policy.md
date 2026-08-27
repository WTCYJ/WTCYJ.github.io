---
layout: post
title: "Android Security Concept Atlas C23 - SELinux 정책 언어, 라벨을 보던 데서 규칙을 읽는 데로"
date: 2026-08-25 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, SELinux, SEAndroid, TypeEnforcement, domain, neverallow, MLS, MCS, seapp_contexts, AVC, Treble, CIL, sepolicy, MAC, DAC, ConceptAtlas, 학습기록]
excerpt: "1~4주차에서 앱 격리가 UID와 SELinux 두 겹이라고 명령 출력으로 확인했고, 15~16주차에서는 ps -Z로 프로세스 라벨을 봤습니다. 그런데 그때 저는 '경계를 재려다 세 번 틀렸다'고 적었습니다. 라벨은 봤지만 그 라벨을 지배하는 정책을 읽지 못했기 때문입니다. 이 글은 그 정책 언어를 다룹니다. allow 규칙의 문법, domain과 type이 같은 것이라는 사실, neverallow가 런타임이 아니라 컴파일 시점 단언이라는 것, 그리고 같은 untrusted_app 도메인을 쓰는 두 앱을 실제로 갈라놓는 것이 타입이 아니라 네 번째 필드(MLS 카테고리)라는 것. Concept Atlas의 여덟 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C23 — SELinux domain·type·allow·neverallow
> **계층**: Tier 4 (플랫폼 격리) · **난이도**: 고급 · **선수 개념**: C05(예외 수준; SELinux는 EL1 커널 LSM), C09(UID·appid·샌드박스)
> **성격**: 보완 편. 라벨 관측은 1~4·15~16주차에서 했으므로 요약·진단으로 넘기고, 공백인 정책 언어에 깊이를 둡니다.
> **완료 기준**: 정책 한 줄을 읽고 그 접근이 허용될지 거부될지 예측할 수 있다.

1~4주차에서 저는 앱 격리가 "UID와 SELinux 두 겹"이라고 명령 출력으로 확인했고, 15~16주차에서는 `ps -A -Z`로 프로세스 라벨을 봤습니다. 그런데 그때 저는 "`adb shell`로 경계를 재려다 세 번째로 틀렸다"고 적었습니다. **라벨은 봤지만, 그 라벨을 지배하는 규칙을 읽지 못했기 때문입니다.** `u:r:untrusted_app:s0:c...`라는 문자열이 무엇을 허용하고 무엇을 막는지, 그 문자열의 네 필드가 각각 무슨 일을 하는지 몰랐습니다.

이 모듈은 그 규칙을 읽는 법입니다. C05에서 "SELinux는 EL1 커널 LSM이 강제한다"고 세웠고 1~4주차의 "이중 샌드박스"에서 그 두 번째 겹을 관측했으니, 이제 그 두 번째 겹의 **정책 언어**로 내려갑니다. 이건 제 Top 5 우선 개념 중 하나였습니다.

## 배경 개념 - 타입 강제라는 접근 통제

- **보안 컨텍스트**: 모든 주체(프로세스)와 객체(파일·소켓·프로퍼티…)에 붙는 라벨. `user:role:type:level` 네 필드입니다. `ps -Z`로 본 게 이것입니다.
- **타입 강제(Type Enforcement, TE)**: SELinux의 규칙 엔진. 거의 전부 **세 번째 필드(type)**를 기준으로 판정합니다.
- **도메인 = 타입**: `domain`과 `type`은 다른 종류가 아닙니다. **하나의 타입 이름공간**입니다. 타입이 "실행 중인 프로세스(주체)에 붙으면" 그걸 **도메인**이라 부르는 것뿐입니다. 파일에 붙으면 그냥 타입입니다.
- **MAC vs DAC**: SELinux는 강제 접근 제어(MAC)로, C05·C09의 UID/모드(DAC) **위에 더해집니다**. **둘 다 통과해야** 접근이 됩니다. SELinux는 오직 **더 조일 뿐**, DAC가 막은 것을 열지 못합니다.
- **AVC**: 커널이 최근 판정을 캐시하는 Access Vector Cache. 거부는 `avc: denied` 로그로 남습니다.

라벨의 생김새 자체는 15~16주차에서 봤으므로 여기서는 되풀이하지 않고, 그 라벨을 지배하는 **규칙**으로 바로 들어갑니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

DAC(UID 샌드박스) 위에 얹히는 **MAC 층**입니다. 1~4주차에서 "두 겹"이라 부른 것의 두 번째 겹이고, C05에서 "EL1 커널 LSM이 강제"라 세운 바로 그 층입니다. 라벨은 봤지만 규칙은 못 읽던 그 규칙이 여기 있습니다. Treble(C31)의 파티션 분할과도 얽힙니다 — 정책이 플랫폼과 벤더로 나뉘어 각자의 파티션에서 오기 때문입니다(C32의 파티션 신뢰).

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

판정은 **EL1 커널의 LSM 훅**에서 일어납니다. syscall이 접근을 시도하면 훅이 `avc_has_perm()`을 부르고, AVC가 (주체 SID, 객체 SID, 클래스) → 허용 벡터를 캐시합니다. 미스면 로드된 정책에서 계산해 채웁니다.

정책 자체는 **부팅 극초기에** init이 로드합니다. Treble(8.0+) 이후에는 플랫폼(`/system/etc/selinux/plat_sepolicy.cil`)과 벤더(`/vendor/etc/selinux/vendor_sepolicy.cil`) CIL 조각을 **따로 컴파일해 부팅 때 링크**해 하나의 바이너리 정책으로 커널에 싣습니다. 그리고 커널만이 아니라 **유저스페이스 오브젝트 매니저**도 자체 검사를 합니다 — `servicemanager`(binder 서비스의 `find`/`add`), `property_service`(`setprop`)가 같은 형식의 AVC 거부를 냅니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **기본은 거부(default-deny)입니다.** 일치하는 `allow`가 없으면 거부됩니다. `deny` 규칙이라는 건 없습니다 — 정책은 순수한 **허용 목록**이고, 규칙이 없다는 것 자체가 거부입니다.
- **neverallow는 런타임 규칙이 아닙니다.** 컴파일/CTS 시점 단언입니다(질문 5에서 상세). 런타임 차단은 오직 allow 부재에서 옵니다.
- **`permissive` 도메인은 MAC를 사실상 끕니다.** 전역이 Enforcing이어도, 정책에 `permissive <도메인>;`이 있으면 그 도메인의 거부는 차단 대신 로그만 됩니다. 특히 **벤더 도메인**에서 실수로 남아 있곤 합니다.
- **`dontaudit`는 거부를 조용히 숨깁니다.** 로그가 없다고 허용된 게 아닙니다 — 접근은 여전히 거부되고 AVC 줄만 억제됩니다.
- **앱-대-앱 격리는 타입(TE)이 하지 않습니다.** 뒤(질문 4·5)에서 볼 MLS 카테고리가 합니다. 이걸 섞으면 "왜 같은 untrusted_app인데 서로 못 읽지?"를 틀리게 설명하게 됩니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 하나의 접근 시도 = { 주체 도메인, 대상 객체의 타입, 객체 클래스, 시도한 권한 }.
- **출력**: 허용 또는 거부(+ 거부 시 `avc: denied` 로그).

규칙의 원자는 이렇습니다.

```
allow  untrusted_app  app_data_file : file  { open read write };
       └── 주체 도메인 └── 대상 타입    └클래스 └── 권한 ──┘
```

읽으면: "**`untrusted_app` 도메인의 프로세스**가, **`app_data_file` 타입**의 **`file` 클래스** 객체를 열고·읽고·쓰는 것을 허용한다." 대상 타입이나 클래스가 바뀌면(예: `system_data_file`, 또는 `dir` 클래스) 그건 **다른 규칙**이고, 자기 allow가 없으면 거부됩니다. `sesearch -A -s untrusted_app -t app_data_file -c file`로 실제 확장된 권한 집합을 기기에서 볼 수 있습니다(실제 AOSP는 `rw_file_perms` 매크로를 써서 `getattr`/`lock`/`append`/`ioctl` 등으로 확장됩니다).

**주체=source / 객체=target 순서가 load-bearing입니다.** 뒤집으면 완전히 다른(대개 존재하지 않는) 권한을 뜻합니다. 15~16주차에서 제가 헷갈렸던 지점이 정확히 이 방향이었습니다.

컨텍스트의 네 필드로 돌아오면: Android는 **user `u`, role `r`(주체)/`object_r`(객체)를 상수로** 씁니다. 분리는 전부 **type과 level**이 합니다. level은 단일 민감도 `s0`뿐이고, 실제 분리는 **카테고리**(`c0..c1023`)가 담당합니다 — 이게 질문 5의 앱 샌드박스입니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**정책이 곧 공격 표면입니다.** 침해된 EL0 서비스는 자기 도메인 밖으로 나가는 **allow 엣지의 유한 집합**에만 갇힙니다. 그래서 잘 짜인 정책은 미디어/블루투스 코드 실행(제 CVE 시리즈)을 그 도메인(`mediacodec`, `bluetooth`)이 이미 만질 수 있는 타입들로 **가둡니다** — 시스템 전체가 아니라. 이것이 C37의 "완화가 무기화를 막는다"와 나란한, "MAC가 침해를 가둔다"는 이야기입니다.

정책이 이 가둠을 **넓히거나 없애는** 지점들:

- **과도한 allow / permissive 도메인**: `permissive <도메인>;`은 그 도메인의 거부를 로그만 남기고 통과시켜, 침해 시 MAC로부터 사실상 무방비가 됩니다. 그런데 전역 `getenforce`는 여전히 `Enforcing`을 보여줍니다. **AOSP는 플랫폼/`coredomain`의 permissive만 user 빌드에서 컴파일 제거하고 CTS로 막습니다 — 벤더 도메인은 여전히 permissive로 출하되어 왔고**, 그래서 `sepolicy-analyze <policy> permissive`로 사냥할 가치가 있습니다.

- **neverallow는 회귀 방지 가드레일입니다.** "이 엣지는 절대 존재하면 안 된다"를 인코딩하고, OEM이 그걸 위반하는 allow를 넣으면 **빌드가 실패**하며 CTS `SELinuxNeverallowRulesTest`가 출하 정책에서 다시 검사합니다. 대표적 예: `neverallow domain ...:process { execmem execheap execstack };`(W^X 강제 — C37의 완화와 직결)와 raw `ioctl`을 허용목록(`allowxperm`) 없이 쓰지 못하게 하는 것. 속성(`appdomain`, `coredomain`)에 대해 쓰여 한 줄로 수백 도메인을 규율합니다.

  > **여기서 흔한 오해 하나를 못 박습니다.** "`untrusted_app`이 **다른 앱의** `app_data_file`을 읽지 못하게 하는 neverallow가 있다"고 생각하기 쉽지만, **그런 neverallow는 존재할 수 없습니다.** 두 앱의 데이터는 **같은 타입** `app_data_file`이고, TE는 오히려 `untrusted_app → app_data_file` 읽기를 **허용**합니다. neverallow는 타입에 대해서만 말할 수 있어 "다른 앱의 같은 타입 파일"을 표현하지 못합니다. 앱-대-앱 격리는 neverallow가 아니라 **런타임 MLS 카테고리**가 합니다(아래).

- **AVC 거부는 정찰입니다.** `avc: denied { read } for ... scontext=u:r:untrusted_app:s0:c... tcontext=u:object_r:vendor_foo_data_file:s0 tclass=file` 한 줄이 주체 도메인·정확한 대상 타입·클래스·시도한 권한을 알려줍니다 — 즉 타입 그래프와 대상이 무엇을 건드리려 했는지를 노출합니다.

**앱-대-앱 샌드박스(SELinux 절반)** — 여기가 이 글에서 가장 중요하고 가장 많이 틀리는 지점입니다. 서드파티 앱은 **전부 같은 `untrusted_app` 도메인**을 씁니다. 그래서 TE 타입만으로는 앱 A와 앱 B를 구분할 수 없습니다(같은 scontext 타입). Android는 **각 앱에 서로 다른 MLS 카테고리 집합**을 붙여 `mlsconstrain`으로 교차 접근을 막습니다.

```
u:r:untrusted_app:s0:c145,c256,c512,c768
                      └─appId─┘ └─userId 0─┘
```

즉 **네 번째 필드(카테고리)**가 격리를 하지, 타입이 하는 게 아닙니다. (카테고리 숫자의 정확한 인코딩은 릴리스마다 바뀌므로 고정 공식으로 외우지 마세요 — appId는 낮은 offset, userId는 `c512`/`c768`대에 들어가고, 최신 `levelFrom=all`은 카테고리 **네 개**를 답니다.) 예외는 **`mlstrustedsubject`** 속성입니다 — `system_server`·`init`·`zygote` 같은 특권 도메인은 카테고리 검사를 **건너뛰어** 모든 앱의 파일을 정당하게 만집니다. 그래서 "왜 system_server는 다 읽는데 앱끼리는 못 읽나"의 답은 "같은 MLS 필드, 다른 속성"입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 4.3 | SELinux permissive(로그만)로 도입 |
| Android 4.4 | 핵심 도메인 몇 개(`installd`·`netd`·`vold`·`zygote`)만 enforcing |
| **Android 5.0** | **전역 enforcing**. 이후 모든 프로덕션 기기는 `getenforce`=Enforcing |
| Android 8.0 (Treble) | 정책을 **플랫폼/벤더로 분할**, CIL로 컴파일해 부팅 때 링크. `public`/`private` 타입 분리 |
| Android 10 / 11 | `product`(10) · `system_ext`(11) 정책 파티션 추가 |

`untrusted_app_NN`(예: `_29`/`_30`/`_32`)는 **targetSdk별 레거시 도메인**인데, **직관과 반대로 더 느슨**합니다 — 평범한 `untrusted_app`(최신 targetSdk)이 가장 엄격하고, `minTargetSdkVersion=` 행이 낮은 targetSdk를 느슨한 도메인으로 보냅니다. 즉 **targetSdk를 올리면 앱이 더 조이는 도메인으로 옮겨갑니다**(재설치 시 관측 가능한 실제 동작 변화). 버전 태그는 `BOARD_SEPOLICY_VERS`로, 벤더가 빌드한 **플랫폼 정책 버전**입니다(26.0=8.0 … 30.0=11 … 34.0=14) — 실행 중 프레임워크 버전이 아니라는 점이 자주 헷갈립니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**기기에서 직접 관측**
- `getenforce`(전역 모드), `id -Z`(내 셸 컨텍스트), `ps -A -Z`(모든 프로세스의 도메인), `ls -Z`(파일 타입), `dmesg | grep avc` / `logcat -b events`(거부). AVC 줄의 `permissive=` 필드가 `1`이면 허용되고 로그만 된 것, `0`이면 실제 차단입니다.

**정책 분석** (핵심: 도구는 **바이너리 정책**에 돌립니다 — 기기의 `.te` 소스가 아니라)
- `sesearch --allow -s untrusted_app <policy>`(그 도메인의 허용 엣지), `sepolicy-analyze <policy> {permissive|neverallow|attribute}`, `seinfo`. 대상은 `/sys/fs/selinux/policy`(로드된 커널 정책)나 Treble의 `precompiled_sepolicy`. `.te`/CIL 소스는 **AOSP 트리에만** 있습니다.

**소스**
- AOSP `system/sepolicy`(`public/`·`private/`·`vendor/`의 `*.te`; `te_macros`; `seapp_contexts`; `mls`/`mls_macros`)
- `source.android.com/docs/security/features/selinux`(concepts·implement·validate), CTS `SELinuxNeverallowRulesTest`
- 정책 언어 레퍼런스: The SELinux Notebook (Richard Haines)

한 가지 더 — **`seapp_contexts`**가 앱을 도메인/타입에 연결하는 다리입니다(C09의 UID/appid 세계와 TE 타입 세계를 잇는). `user=`·`seinfo=`(APK 서명 → `mac_permissions.xml`)·`isPrivApp=`·`minTargetSdkVersion=` 같은 **선택자**를 **가장 구체적으로 일치**하는 행이(파일 순서가 아니라) `domain=`·`type=`·`levelFrom=`을 공급합니다. 그래서 어떤 앱이 `untrusted_app`이고 어떤 앱이 `platform_app`인지는 **매니페스트가 아니라 서명(seinfo)에서** 옵니다.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **1~4주차(이중 샌드박스)**: 그 "두 겹"의 MAC 절반이 **TE + MLS 카테고리**라는 것을 이제 규칙으로 설명할 수 있습니다.
- **15~16주차(`ps -Z` 라벨)**: 그 라벨은 **타입**이고, 그것을 지배하는 규칙은 대개 그 타입이 멤버인 **속성**(`appdomain` 등)에 대해 쓰여 있습니다. "경계를 재려다 세 번 틀렸다"의 해소가 이것입니다 — 라벨이 아니라 정책을 읽어야 했습니다.
- **C05(EL1 LSM)**: 판정은 EL1에서, DAC와 나란히. 둘 다 통과해야 합니다.
- **C09(UID·appid)**: `seapp_contexts`가 UID/서명 세계를 SELinux 타입 세계로 잇습니다.
- **C31/C32(Treble·파티션 신뢰)**: 정책의 플랫폼/벤더 분할이 곧 파티션 신뢰의 정책적 표현입니다.
- **C37(완화)**: `neverallow ... execmem`은 W^X 강제를 정책 층에서 못 박은 것입니다.
- 다음은 **C26(샌드박스 vs SELinux 역할 구분)**(진단 대체 예정)이나 부팅 체인으로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

두 개를 손으로 그려 보시길 권합니다.

```
[ 접근 하나가 판정되는 길 ]

syscall (예: open("/data/data/other.app/...", ...))
   │
   ▼
DAC 검사(UID/모드) ── 막히면 EACCES (SELinux 안 감)
   │ 통과
   ▼
LSM 훅(EL1) → avc_has_perm()
   │            ├─ AVC 히트: 캐시된 결정
   │            └─ 미스: 로드된 정책에서 계산 → 캐시
   ▼
allow 엣지 있음? ──아니오→ 거부(+ avc: denied 로그)
   │ 예
   ▼
MLS 카테고리 검사(mlsconstrain) ──카테고리 다르면(다른 앱)→ 거부
   │ mlstrustedsubject 거나 카테고리 일치
   ▼
   허용
```

```
[ 앱이 자기 라벨을 얻는 길 ]

zygote fork
   │
   ▼
seapp_contexts 최선-매칭 (seinfo=서명, isPrivApp, minTargetSdkVersion, ...)
   │
   ▼
domain=untrusted_app · type=app_data_file · levelFrom=all
   │
   ▼
카테고리 생성(appId + userId)
   │
   ▼
u:r:untrusted_app:s0:c145,c256,c512,c768   ← ps -Z 로 보이는 그 문자열
```

## 오개념 판별 문제 5개

각 문장이 왜 틀렸는지 한 줄로 반박해 보세요.

1. "`neverallow` 규칙이 런타임에 그 접근을 막는다."
2. "두 앱이 같은 `untrusted_app` 도메인이면 서로의 파일을 못 읽는 것은 TE(타입 강제)가 막는 것이다."
3. "`getenforce`가 `Enforcing`이면 모든 프로세스가 MAC로 갇혀 있다."
4. "루트를 얻으면 `setenforce 0`으로 SELinux를 끌 수 있다."
5. "`sesearch`를 기기의 `.te` 소스에 돌린다 / `dmesg`에 avc 거부가 없으면 그 접근은 허용된 것이다."

<details><summary>판정 기준(펼치기)</summary>

1. `neverallow`는 컴파일(`checkpolicy`/`secilc`)과 CTS 시점 단언입니다. 일치하는 allow가 있으면 **빌드가 실패**합니다. 런타임 차단은 오직 allow 부재(default-deny)에서 옵니다 — 커널은 neverallow 개념 자체가 없습니다.
2. TE는 오히려 `untrusted_app → app_data_file`을 **허용**합니다. 두 앱 파일은 같은 타입이라 TE로는 구분 불가입니다. 막는 것은 **per-app MLS 카테고리**(`mlsconstrain`)입니다. 격리는 네 번째 필드가 합니다.
3. 정책에 `permissive <도메인>;`이 남아 있을 수 있습니다(특히 벤더). 전역 enforcing과 도메인별 permissive는 공존합니다. `sepolicy-analyze <policy> permissive`로 확인하세요.
4. user 빌드에선 불가입니다. 셸 도메인에 `security:setenforce` 권한이 없고, `androidboot.selinux=permissive` cmdline 우회는 userdebug/eng에서만 유효합니다. 게이트는 Verified Boot가 아니라 **빌드 변종**입니다.
5. 도구는 **바이너리 정책**(`/sys/fs/selinux/policy`, `precompiled_sepolicy`)에 돌립니다 — `.te` 소스는 AOSP 트리에만 있습니다. 그리고 `dontaudit`·permissive가 거부를 숨기거나 바꾸므로, avc 부재는 허용의 증거가 아닙니다.
</details>

## 서술형 문제 3개

1. 15~16주차에서 `ps -Z`로 본 `u:r:untrusted_app:s0:c145,c256,c512,c768`의 네 필드를 각각 설명하고, **어느 필드가 두 앱을 구분하며** 그 강제가 TE가 아니라 무엇(무슨 제약)에서 오는지 서술하세요.
2. `neverallow`가 런타임이 아니라 컴파일/CTS 시점 단언이라는 사실이, OEM/벤더가 스스로에게 위험한 `allow`를 추가하지 못하게 하는 데 왜 결정적인지 서술하세요.
3. 미디어/블루투스 EL0 침해(제 CVE 시리즈)가 SELinux로 "그 도메인이 접근 가능한 타입 집합"에 어떻게 갇히는지, 그리고 `permissive` 도메인이 그 가둠을 어떻게 무력화하는지 서술하세요.

## 소스 탐색 과제

기기(또는 에뮬레이터)에서 다음을 수행하고 정리하세요. **SELinux는 아키텍처와 무관하므로 x86 에뮬(`sec-api33`)에서도 대부분 됩니다** — PAC/MTE와 달리 실기기가 꼭 필요하지 않습니다.

- `ps -A -Z | grep untrusted_app`로 서로 다른 두 앱이 **같은 도메인인데 카테고리 꼬리가 다름**을 확인하세요 — 그 꼬리가 앱-대-앱 샌드박스입니다.
- `sepolicy-analyze <policy> permissive`로 permissive 도메인 목록을, `sesearch -A -s untrusted_app -t app_data_file -c file`로 실제 확장된 권한 집합을 뽑으세요(대상은 바이너리 정책).
- `dmesg | grep avc` 거부 한 줄을 골라 `scontext`/`tcontext`/`tclass`/`{ perm }`로 **어떤 `allow`가 빠졌는지**(또는 어떤 `mlsconstrain`인지)를 역산해, "정책 한 줄을 읽고 허용/거부를 예측한다"는 완료 기준을 채우세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 앞의 세 모듈(C05·C37·C33)과 달리 이 주제는 **`sec-api33` 에뮬로 대부분 실측 가능**합니다(SELinux는 x86에도 있음). 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **라벨 실측**: `getenforce`·`id -Z`·`ps -A -Z`·`ls -Z` 출력을 실제 화면으로. 15~16주차에서 라벨만 봤던 것을 이제 네 필드로 분해해 설명.
2. **앱-대-앱 격리를 실물로**: 앱 두 개를 설치해 카테고리 꼬리가 다름을 캡처하고, 한 앱에서 다른 앱의 데이터 접근을 시도해 실패를 보이기.
3. **정책 한 줄 읽기(완료 기준)**: `sesearch`로 `untrusted_app`의 allow 엣지 하나를 뽑아, 주체·대상 타입·클래스·권한으로 소리 내어 읽기.
4. **거부 귀속**: 위 2의 접근 시도가 남긴 `avc: denied`(또는 억제됐다면 `dontaudit` 때문임을 확인)를 캡처하고, 그것이 allow 부재인지 `mlsconstrain`인지 귀속.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 재현 불가·미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

15~16주차에서 저는 라벨을 보고도 경계를 세 번 틀리게 쟀습니다. 라벨은 정책의 **결과**일 뿐, 규칙 자체가 아니었기 때문입니다. 이제 그 규칙을 읽습니다 — `allow 주체 대상:클래스 권한;`이 원자이고, 기본은 거부이며, `neverallow`는 런타임이 아니라 빌드/CTS 시점에 OEM의 손을 묶는 가드레일이고, 무엇보다 **같은 `untrusted_app`을 쓰는 두 앱을 실제로 갈라놓는 것은 타입이 아니라 네 번째 필드(MLS 카테고리)**입니다.

이걸 알면 제 CVE 시리즈가 새로 읽힙니다. 미디어/블루투스 EL0 침해는 SELinux로 그 도메인의 allow 엣지에 갇히고, 커널(EL1) 탈출만이 그 가둠을 벗어납니다(C05). 정책이 곧 공격 표면이라, `permissive` 벤더 도메인 하나가 그 가둠을 조용히 없앱니다. 다음은 이 격리를 UID 샌드박스와 나란히 놓는 **C26**, 또는 이 모든 것이 부팅 때 어떻게 실리는지의 부팅 체인으로 이어집니다. 위의 「블로그 초안 작성 과제」를 마치면 이 모듈이 실측 글로 확정됩니다.
