---
layout: post
title: "AOSP repo·Android.bp·Soong"
date: 2026-11-29 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, AOSP, Soong, 빌드시스템, 공급망]
excerpt: "AOSP는 하나의 git이 아니라 manifest가 묶은 수백 개 git이고, 빌드는 Make가 아니라 Soong이 조립한다. 흔한 함정 — Android.bp를 Make처럼 조건문으로 짜려다 막히고, manifest revision을 브랜치로 두면 어제 빌드와 오늘 빌드가 달라진다."
---

system_server도, HAL도, Binder도 결국 누군가 소스에서 빌드한 바이너리다. 그 "소스에서 빌드"가 실제로 어떻게 일어나는지를 모르면, 앞 장들에서 읽은 프레임워크 코드가 어느 트리의 어느 revision에서 왔고 어떤 variant로 굳어졌는지를 말할 수 없다. 그리고 그 두 가지 — 소스의 출처와 이미지의 보안 경계 — 는 정확히 `repo` manifest와 `lunch` variant가 정한다.

이 글은 AOSP를 어떻게 받아(`repo`) 어떻게 조립하는지(`Soong`/`Android.bp`)를 1차 문서와 함께 정리한 기록이다. 공개 AOSP 소스만 대상으로 하며, 실기기 flashing이나 배포는 다루지 않는다.

> **한 줄 결론**: AOSP 빌드의 신뢰 뿌리는 manifest가 고정한 git revision과 `lunch`가 고른 variant다 — 소스의 출처와 최종 이미지의 보안 경계가 여기서 결정된다. Android.bp는 선언형이라 Make식 제어 흐름을 기대하면 막힌다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 세 조각이다. (1) `repo`와 manifest가 수백 개 git 저장소를 하나의 트리로 묶는 방식, (2) `Android.bp`(Blueprint 문법)로 모듈을 선언하는 방식, (3) `Soong`이 그 선언을 Ninja로 바꿔 실제 빌드가 도는 파이프라인. 공격 실습이 아니라 구조·소스 이해가 목적이다.

선수 지식은 두 가지다. 먼저 git의 기본(clone·revision·remote) — `repo`는 git 위에 얹힌 얇은 파이썬 래퍼라 git을 모르면 manifest가 안 읽힌다. 그리고 앞 장들에서 본 것들이 소스로는 어디 사는지 — 15장(Stable AIDL)의 `aidl_interface`, 16장(HAL·VINTF)의 HAL 모듈이 전부 `Android.bp` 모듈로 존재한다. Atlas C04(프로세스·가상메모리)에서 본 "에뮬레이터가 무엇을 흉내 내나"는 결국 이 트리를 빌드한 이미지다.

전체 구조에서 이 장은 **소스에서 이미지까지의 바닥 파이프라인**이다. 8장(ART·dex2oat)이 만든 실행 형식도, 다음 18장(Cuttlefish/GSI/userdebug build)이 부팅할 이미지도 전부 여기서 나온 산출물이다.

## 핵심 개념 — 소스는 repo가, 빌드는 Soong이 조립한다

AOSP는 단일 저장소가 아니다. `platform/frameworks/base`, `platform/system/core`, `platform/build/soong` 같은 수백 개의 독립 git 저장소를, manifest 하나가 "어떤 저장소를 어느 경로에 어느 revision으로" 놓을지 기술한다. `repo init -u <manifest-url> -b <branch>` 로 manifest 저장소를 `.repo/manifests`에 받고, `repo sync`가 그 목록대로 모든 프로젝트를 병렬로 clone/pull 한다. `Source-confirmed`

manifest(`default.xml`)의 골격은 이렇다. `<remote>`가 서버를, `<default>`가 기본 revision/remote를, `<project>`가 개별 저장소를 잡는다.

```xml
<manifest>
  <remote name="aosp" fetch="https://android.googlesource.com/" />
  <default revision="refs/tags/android-14.0.0_r1" remote="aosp" sync-j="4" />
  <project path="frameworks/base" name="platform/frameworks/base" />
  <project path="system/core"     name="platform/system/core" />
</manifest>
```

`revision`을 태그(`android-14.0.0_r1`)나 커밋 SHA로 고정하면 재현 가능한 트리가 되지만, `main` 같은 브랜치로 두면 `repo sync`할 때마다 그 아래 코드가 조용히 바뀐다. `.repo/local_manifests/*.xml`로 프로젝트를 덧붙이거나 덮어쓸 수도 있는데, 이게 공급망 관점에선 곧 "내 트리에 임의 저장소를 끼워 넣는 지점"이다. `Source-confirmed`

빌드 쪽. Android 7.0(Nougat)부터 플랫폼 빌드는 Make에서 **Soong**으로 옮겨졌고, 모듈은 `Android.bp` 파일에 선언한다. `Android.bp`는 Google의 Blueprint 파서 문법을 쓰며, **선언형**이다 — 문자열/불리언/리스트/맵과 모듈 정의만 있고 `if`·반복·산술·임의 include가 없다. `Source-confirmed`

```
cc_library_shared {
    name: "libexample",
    srcs: ["example.cpp"],
    shared_libs: ["liblog", "libbinder"],
    arch: {
        arm64: { cflags: ["-DARM64"] },
        x86_64: { cflags: ["-DX86"] },
    },
}
```

아키텍처·타깃별 차이는 `if`가 아니라 `arch: { ... }`, `target: { android: {}, host: {} }`, 그리고 빌드 플래그 기반 분기는 `soong_config_variables`로 표현한다. 여기서 가장 흔한 착각이 나온다 — **Make 습관대로 조건문을 쓰려다 파서에서 막힌다.** 제어 흐름이 필요하면 그건 Soong 로직(Go 코드)이나 `genrule`로 내려가는 신호지, `.bp`에 쓸 게 아니다. `Source-confirmed`

주요 모듈 타입은 산출물로 외운다.

| 모듈 타입 | 산출물 | 대략의 예 |
|--|--|--|
| `cc_binary` / `cc_library_{shared,static}` | 네이티브 실행/라이브러리 | `servicemanager`, `libbinder` |
| `java_library` / `android_library` | 자바 라이브러리 | framework 조각 |
| `android_app` | APK | 시스템 앱 |
| `aidl_interface` | 안정 AIDL 인터페이스(15장) | 서비스/HAL 계약 |
| `genrule` / `filegroup` | 생성물 / 파일 묶음 | 코드젠·리소스 |
| `prebuilt_etc` | `/system/etc` 배치 | 정책·설정 파일 |

보조 도구도 알아둔다. `bpfmt`가 `.bp`를 정렬(포맷)하고, `androidmk`가 옛 `Android.mk`를 `.bp`로 근사 변환한다(완전 자동은 아니고 손질 필요). `Source-confirmed`

> **[그림 1]** 실제 AOSP 저장소에서 하나의 `Android.bp`를 열어 모듈 타입·`srcs`·`shared_libs`·`arch{}` 블록이 보이는 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 장의 위협 모델은 런타임 공격자가 아니라 **소스와 빌드의 출처(provenance)**다. 경계는 세 겹으로 선다.

- **소스 출처 경계** — 무엇을 빌드하느냐는 manifest의 `<remote fetch>`와 각 `<project revision>`이 정한다. remote가 신뢰할 수 없거나 revision이 고정되지 않으면, 같은 명령이 서로 다른 코드를 만든다. `repo` 자체는 실행 시 repo 런처의 GPG 서명을 검증하지만, 그건 도구의 진위일 뿐 manifest가 가리키는 코드의 진위는 아니다. `Inferred`
- **로컬 manifest 경계** — `.repo/local_manifests/`는 트리에 프로젝트를 추가/치환하는 합법적 훅이자, 검토 없이 들어오면 공급망 삽입 지점이다. `Source-confirmed`
- **이미지 보안 경계** — `lunch <product>-<variant>`의 variant가 최종 이미지의 신뢰 수준을 굳힌다. `user`는 `ro.debuggable=0`·adbd root 불가·SELinux enforcing으로 출하 기기와 같고, `userdebug`/`eng`는 이를 의도적으로 낮춰 관측을 연다(1장에서 정리한 이미지 선택이 정확히 이 축이다). `Source-confirmed`

즉 "무엇을 빌드했나(소스)"와 "무엇을 관측할 수 있나(variant)"가 전부 빌드 진입 단계에서 결정된다. 런타임 완화(PAC/MTE, SELinux)를 아무리 논해도, 그 이미지가 어느 revision·어느 variant인지 모르면 근거가 없다.

## 분석 — repo에서 Ninja까지의 파이프라인

전체 흐름은 한 장의 그림으로 압축된다. 핵심은 **`.bp`도 `.mk`도 직접 빌드하지 않는다는 것** — 둘 다 Ninja 파일로 번역되고, 실제 컴파일은 Ninja가 돈다.

```
manifest (git revision 고정)
      │  repo sync
      ▼
AOSP 소스 트리
   ├── Android.bp ──► Soong ──┐
   └── Android.mk ──► Kati  ──┤
                              ▼
                       Ninja 파일(out/)
                              │  ninja
                              ▼
                       out/ 이미지·바이너리
```

진입점은 `build/envsetup.sh` → `lunch` → `m`이다. `source build/envsetup.sh`가 `lunch`·`m` 같은 함수를 셸에 심고, `lunch`가 product-variant를 고르면 그 조합의 제품 설정이 로드된다. `m`은 내부적으로 `soong_ui.bash`를 불러, 제품 설정(Kati)과 `Android.bp`(Soong)를 각각 Ninja로 만든 뒤 Ninja를 실행한다. `Source-confirmed`

파싱만 검증하고 싶으면 `m nothing`이 유용하다 — 제품 설정과 Soong 분석까지만 돌고 실제 타깃은 만들지 않아, `.bp` 문법 오류나 모듈 충돌을 빠르게 잡는다. 소스 출처를 스냅샷으로 굳히려면 `repo manifest -r`가 현재 각 프로젝트의 실제 SHA로 revision을 잠근 manifest를 출력한다. 이 두 명령이 이 장의 실무 결론이다. `Source-confirmed`

```bash
# 소스 받기 (revision은 태그로 고정)
repo init -u https://android.googlesource.com/platform/manifest -b android-14.0.0_r1
repo sync -c -j"$(nproc)"          # -c: 현재 브랜치만

# 빌드 진입
source build/envsetup.sh
lunch aosp_cf_x86_64_phone-userdebug
m nothing                          # 설정+Soong 파싱만, 컴파일 없음

# 재현용 스냅샷 manifest (모든 프로젝트를 현재 SHA로 고정)
repo manifest -r -o pinned.xml
```

`예시 출력`(실제 실행으로 교체):

```
============================================
PLATFORM_VERSION_CODENAME=REL
PLATFORM_VERSION=14
TARGET_PRODUCT=aosp_cf_x86_64_phone
TARGET_BUILD_VARIANT=userdebug
TARGET_ARCH=x86_64
============================================

$ m nothing
[  0% 1/1] finishing build rules ...
No build target specified, so nothing to build.
```

> **[그림 2]** `lunch`로 product-variant를 고른 뒤 표시되는 설정 배너(TARGET_PRODUCT/TARGET_BUILD_VARIANT)와 `m nothing`이 Soong 분석까지만 돌고 끝나는 화면 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

두 설계 결정이 나머지를 전부 설명한다.

**첫째, 왜 `repo`인가.** AOSP는 규모와 소유가 서로 다른 수백 개 컴포넌트의 합이라 단일 git으로 관리되지 않는다. manifest로 "저장소 목록 + revision"을 분리하니, 소스 구성 자체가 하나의 버전 관리 대상이 된다 — 그래서 재현성·출처가 manifest 한 파일에 집약되고, 반대로 그 파일이 곧 공급망의 급소가 된다. `Inferred`

**둘째, 왜 선언형 `Android.bp`인가.** Make 기반 빌드는 규칙 안에 임의 셸·조건이 섞여 병렬성·정확성·증분 빌드가 무너졌다. Soong은 빌드 그래프를 **데이터(선언)**로 고정하고 로직은 Go 코드로 분리해, 전체 그래프를 미리 계산한 뒤 Ninja에 넘긴다. `.bp`에 `if`가 없는 건 부족이 아니라 의도다 — 제어 흐름을 데이터에서 걷어내야 그래프가 결정적이어서 증분·병렬·캐시가 성립한다. Make식 조건문을 기대하면 막히는 이유가 여기다. `Source-confirmed`

그래서 `.bp`도 `.mk`도 최종 실행자가 아니다. Soong과 Kati는 각각 번역기이고, 실제 작업은 단일한 Ninja 그래프가 수행한다. 빌드가 이상할 때 "누가 이 규칙을 만들었나"를 `.bp`가 아니라 생성된 Ninja/`out`에서 확인해야 하는 이유다. `Inferred`

## 버전 차이와 한계

- **7.0 경계** — Soong/`Android.bp`는 Android 7.0부터다. 그 이전(또는 아직 이행 안 된 일부)은 `Android.mk`라 Kati 경로로 처리된다. 두 체계가 한 트리에 공존한다는 점을 잊으면 "왜 이 모듈은 `.bp`가 없지"에서 헤맨다. `Source-confirmed`
- **Bazel(Roboleaf) 이행** — 한때 Soong→Bazel 이행이 추진됐으나 방향/우선순위가 바뀐 이력이 있다. 현재 공식 상태는 배포 버전마다 다르니 원문 재확인 필요. `Reported`
- **SBOM/출처** — 최근 AOSP는 빌드 산출물에 대한 SPDX 형식 SBOM 생성을 지원한다(모듈 provenance 추적용). 구체적 생성 경로·플래그는 버전 확인 필요. `Reported`
- **에뮬레이터 한계** — 빌드 결과가 무엇을 관측하게 하느냐는 variant에 종속된다. TEE/StrongBox 같은 하드웨어 신뢰뿌리는 빌드로 만들어지지 않으므로, Atlas의 하드웨어 부분은 실기기로 넘어간다. `Inferred`

## 정리

- AOSP는 manifest가 묶은 수백 개 git이다. `revision`을 고정해야 재현되고, `.repo/local_manifests`는 편의이자 공급망 삽입 지점이다.
- `Android.bp`는 선언형(Blueprint) — `if`가 없고, 분기는 `arch{}`/`target{}`/`soong_config_variables`로 표현한다. Make 습관이 여기서 막힌다.
- `.bp`도 `.mk`도 Ninja로 번역될 뿐, 실제 빌드는 Ninja가 돈다. 진입은 `envsetup.sh`→`lunch`→`m`이고, `lunch`의 variant가 이미지의 보안 경계를 굳힌다.
- 소스 출처는 `repo manifest -r`로 SHA 고정, 파싱 검증은 `m nothing`으로 빠르게.

**점검 질문** — (1) 같은 `repo sync`가 서로 다른 코드를 만들 수 있는 조건은? (2) `Android.bp`에서 아키텍처별로 다른 `cflags`를 주려면 무엇을 쓰나(그리고 왜 `if`가 아닌가)? (3) `lunch aosp_cf_x86_64_phone-userdebug`의 어느 부분이 최종 이미지의 adb root 가능 여부를 결정하나?

**참고** — [Building Android](https://source.android.com/docs/setup/build/building) · [Repo command reference](https://source.android.com/docs/setup/reference/repo) · [Downloading the source](https://source.android.com/docs/setup/download/downloading) · Soong/`Android.bp` — `build/soong/README.md`(AOSP) · [Blueprint](https://github.com/google/blueprint)

*다음 글: [Cuttlefish·GSI·userdebug build](/posts/android-expert-p2c18/).*
