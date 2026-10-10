---
layout: post
title: "API level/SPL/실제 코드 불일치"
date: 2026-12-30 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, SPL, APILevel, 패치갭, 보안불리틴]
excerpt: "기기가 보고하는 Security Patch Level은 빌드 때 박아넣은 문자열이지 패치가 실제로 들어갔다는 증명이 아니다. API level과 SPL은 서로 독립된 축이라 프레임워크 SPL이 최신이어도 vendor·커널은 몇 달 뒤처질 수 있고, 코드가 진짜 바뀌었는지는 SPL이 아니라 바이너리 diff로만 확인된다."
---

취약점 연구를 시작하면 제일 먼저 하는 질문이 "이 기기, 이 이슈 패치됐나?"다. 그리고 대부분 `getprop ro.build.version.security_patch` 한 줄을 보고 판단해 버린다. 이게 이 파트에서 가장 값비싼 착각이다. SPL은 빌드 담당자가 손으로 넣은 날짜 문자열일 뿐, "이 날짜까지의 모든 커밋이 이 코드에 들어가 있다"를 검증한 결과가 아니다. 세 개의 서로 다른 값 — API level, Security Patch Level, 그리고 실제 코드 — 이 각자 다른 속도로 움직이고, 연구자는 이 셋이 어긋나는 지점에서 표적을 찾는다.

이 글은 그 세 축이 각각 무엇을 뜻하고, 왜 서로 일치하지 않는지, 그리고 "패치됐다"는 주장을 코드로 되짚는 방법을 정리한 기록이다. 실습이 아니라 신뢰 경계 분석에 가깝다.

> **한 줄 결론**: SPL은 빌드 시점에 박아넣은 주장(claim)이지 코드가 패치됐다는 증명이 아니다. API level과 SPL은 독립축이고, 코드가 실제로 바뀌었는지는 baseline↔patched diff로만 확정된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 것은 세 축의 정의와 그 사이의 간극이다 — (1) API level(`ro.build.version.sdk`), (2) Security Patch Level(`ro.build.version.security_patch`), (3) 실제 코드/바이너리의 상태. 다루지 않는 것은 특정 벤더를 지목한 patch-gap 폭로나 우회 무기화다. 대상은 공개된 AOSP·이미 공개·패치된 CVE·에뮬레이터로 한정한다.

선수 지식은 셋이다. 이 파트 1장에서 만든 AOSP 소스 트리와 `repo`/브랜치 개념, 이 파트 3장의 Android Security Bulletin과 patch provenance(불리틴이 CVE를 어떤 커밋에 매핑하는가), 그리고 `adb shell getprop`으로 빌드 프로퍼티를 읽는 기본기다. 이 셋을 알고 나면 "SPL이 코드의 대리값이 아니다"라는 이 글의 핵심이 바로 선다.

전체 구조에서 이 장은 **표적 선정의 전제**다. 5장 이후의 공격 표면 열거와 6~10장의 퍼징은 전부 "무엇이 패치됐고 무엇이 안 됐나"를 안다는 가정 위에 선다. 그 가정을 만드는 곳이 여기다.

## 핵심 개념 — 세 축은 서로 다른 시계로 움직인다

세 값은 이름이 비슷해 자꾸 하나로 뭉뚱그려지지만, 갱신 트리거가 완전히 다르다.

| 축 | 프로퍼티 / API | 갱신 트리거 | 뜻하는 것 |
|--|--|--|--|
| API level | `ro.build.version.sdk` / `Build.VERSION.SDK_INT` | OS 메이저 업그레이드 | 프레임워크 API 표면(SDK 버전) |
| 릴리스 | `ro.build.version.release` | OS 메이저 업그레이드 | 사용자 표기 버전(예: 14) |
| SPL | `ro.build.version.security_patch` / `Build.VERSION.SECURITY_PATCH` | (이상적으로) 월간 보안 업데이트 | "이 날짜의 패치를 적용했다"는 주장 |

`Build.VERSION.SECURITY_PATCH`는 `YYYY-MM-DD` 문자열로 노출되는 사용자 가시 값이고, `SDK_INT`는 정수다. `Source-confirmed` 둘은 정의상 독립이다 — API 34 기기가 반년 전 SPL을 달고 있을 수 있고, 반대로 같은 SPL이 여러 API level에 걸쳐 존재할 수도 있다.

여기에 SPL 안쪽의 잘 안 알려진 하위 구분이 있다 — 독립된 넷째 축이 아니라 SPL 끝자리다. **불리틴 자체가 매월 두 개의 SPL을 정의한다.** `YYYY-MM-01`과 `YYYY-MM-05`. `-05` 레벨은 `-01`의 이슈를 전부 포함하고 그 위에 추가분(주로 커널·폐쇄소스 벤더 컴포넌트)을 더한다. `Source-confirmed` 즉 같은 달이라도 `2024-09-01`을 보고하는 기기와 `2024-09-05`를 보고하는 기기는 **다른 코드 상태**다. SPL을 "월"로만 읽고 끝자리를 무시하면 여기서 틀린다.

> **[그림 1]** 에뮬레이터에서 `ro.build.version.sdk`·`ro.build.version.release`·`ro.build.version.security_patch`를 한 화면에 출력해, API level·릴리스·SPL이 서로 다른 값·다른 축임을 보여주는 adb 터미널 캡처 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

SPL은 **벤더의 빌드 프로세스가 생산하고, 그 아래 모두가 소비하는 주장**이다. 소비자는 사용자(설정 화면의 "보안 업데이트" 날짜), MDM/기업 정책, 그리고 원격 증명(Play Integrity류)이다. 신뢰 경계는 "SPL 문자열을 만든 빌드 시스템"과 "그 문자열을 사실로 받아들이는 다운스트림" 사이에 그어진다.

문제는 이 문자열이 코드 내용에 **암호학적으로도 의미론적으로도 묶여 있지 않다**는 것이다. 빌드가 `2024-09-05`라고 선언하는 것과, 그달 `-05` 커밋 집합이 실제로 이 소스에 머지됐는지는 별개다. 그래서 두 방향의 오차가 모두 가능하다.

- **과대 주장(patch gap)**: SPL은 최신인데 특정 수정 커밋이 백포트에서 누락. 겉보기엔 패치됐지만 취약 코드 경로가 살아 있다. `Reported`(patch-gap은 SRLabs 등 2차 연구로 문서화된 현상)
- **파티션 불일치**: 프레임워크 SPL은 최신인데 `vendor`/`boot` 파티션 SPL은 뒤처짐. Treble(Android 8+) 이후 파티션별 SPL이 분리되면서 흔해졌다. 프레임워크만 보고 "패치됨"이라 단정하면 커널·HAL 취약점을 통째로 놓친다. `Reported`(정확한 vendor 프로퍼티 키 이름은 기기·버전별 확인 필요)

연구자의 위협 모델은 단순하다. **SPL은 힌트지 진실이 아니다.** 표적이 진짜 열려 있는지는 코드로 확인한다.

## 분석 — "패치됐다"를 코드로 되짚기

이미 공개·패치된 CVE 하나를 골라, "이 SPL이면 이 수정이 들어 있어야 한다"는 주장을 검증하는 흐름은 이렇다. (무기화가 아니라, 코드 존재 여부 확인이다.)

1. 대상 기기의 축을 읽는다 — API level, 릴리스, SPL(끝자리 `-01`/`-05`까지).
2. 이 파트 3장 방식으로 해당 월 불리틴에서 CVE와 그 **AOSP 수정 커밋 링크**를 뽑는다. 불리틴은 CVE를 커밋에 매핑해 준다.
3. 그 수정이 대상 코드/바이너리에 실제로 존재하는지 확인한다. 소스가 있으면 원본 해시가 아니라 커밋의 **Change-Id**나 메시지의 `cherry picked from commit ...` 트레일러(체리픽이 보존한다)로, 또는 해당 함수·헝크의 코드 상태로 대조한다. 이미지뿐이면 baseline↔patched diff로(이 파트 14장).
4. `-05`를 주장하는데 그 수정이 코드에 없으면(Change-Id·헝크 기준) → 주장이 코드를 앞선 것이다. 단, **AOSP 원본 해시가 안 잡히는 것만으로는** 부재의 증거가 아니다 — 벤더·백포트 트리는 체리픽이 해시를 새로 만들기 때문이라, 원본 해시 기준으론 결론을 보류한다.

```bash
# 대상 축 읽기
adb shell getprop ro.build.version.sdk              # API level
adb shell getprop ro.build.version.release          # 릴리스
adb shell getprop ro.build.version.security_patch   # SPL (끝자리 확인)

# (A) 불리틴이 링크한 그 AOSP 브랜치·태그를 직접 체크아웃한 경우에만: 원본 해시로 확인
git -C frameworks/base log --oneline <branch-or-tag> | grep <commit-prefix>
# (B) 벤더·백포트 트리(현실의 대부분): 체리픽이 해시를 새로 만들어 원본 해시 grep은 false negative.
#     Change-Id 또는 'cherry picked from commit' 트레일러로 대조한다
git -C frameworks/base log --grep='Change-Id: I<change-id>'
```

불리틴이 링크한 바로 그 AOSP 브랜치·태그를 체크아웃했다면, 원본 해시가 `git log`에 나오면 존재·안 나오면 그 브랜치엔 미백포트다. 그러나 벤더·기기 트리(현실의 대부분)에서는 체리픽이 새 해시를 만들어 원본 해시 grep이 false negative가 나므로, Change-Id·헝크로 대조하고 원본 해시 부재는 결론 보류로만 읽는다. 여기서 얻는 결론은 "취약하다"가 아니라 "SPL 주장과 코드 상태가 일치/불일치한다"까지다. 실제 트리거 가능성은 별개 검증이다 — 크래시를 취약점으로, 코드 부재를 익스플로잇으로 부풀리지 않는다.

> **[그림 2]** 특정 월 Android Security Bulletin 페이지에서 `YYYY-MM-01`·`YYYY-MM-05` 두 패치 레벨 정의와 CVE→AOSP 커밋 링크가 보이는 브라우저 캡처, 옆에 대상 기기의 `getprop ...security_patch` 출력 — *실측 스크린샷 자리*

`예시 출력`(실제 실행으로 교체):

```
$ adb shell getprop ro.build.version.sdk
34
$ adb shell getprop ro.build.version.release
14
$ adb shell getprop ro.build.version.security_patch
2024-09-05
$ git -C frameworks/base log --oneline --grep='Change-Id: Iabc...def'
a1b2c3d Fix OOB read in <parser> (CVE-2024-XXXXX)
```

이 대조(Change-Id·헝크 기준)에서 결과가 비면 "SPL은 09-05인데 09-05 수정이 코드에 없다"가 되고, 그게 patch provenance 조사의 출발점이다. 반대로 원본 해시만 안 잡힌 경우라면 부재가 아니라 대조 방법을 바꿔야 한다는 신호다.

## Root Cause — 왜 어긋나는가

근본 원인은 **SPL이 코드에서 유도되지 않고 손으로 설정되는 빌드 변수**라는 데 있다. SPL 문자열은 빌드 설정의 `PLATFORM_SECURITY_PATCH`(`build/make/core/version_defaults.mk`에서 정의)에서 나온다. `Source-confirmed` 이 값을 정할 때 빌드 시스템은 "선언한 날짜의 모든 커밋이 실제로 머지됐는가"를 검사하지 않는다. 검증 없는 선언이므로, 백포트가 수동·벤더별인 현실과 만나면 주장과 코드가 갈라진다.

API level이 코드 내용을 보장하지 못하는 것도 같은 결의 문제다. API level은 프레임워크 API 표면의 버전일 뿐, 그 밑의 네이티브·커널 코드가 얼마나 바뀌었는지와 직접 연결되지 않는다. 실제로 API 라벨이 크게 점프해도 그 아래 커널 소스가 동일한 경우를 관측한 적 있다. `Inferred`(24주 스터디 관측: 라벨 점프에도 커널 코드 동일) 라벨은 코드의 신뢰할 만한 대리값이 아니다.

정리하면, 세 축의 불일치는 버그가 아니라 **선언(빌드 변수)과 사실(머지된 커밋 집합)을 묶는 강제 장치가 없기 때문**에 생기는 구조적 결과다.

## 버전 차이와 한계

- **Treble 경계(Android 8.0)**: 이전엔 SPL이 사실상 단일값, 이후엔 파티션별(system/vendor/boot)로 분리 가능. 8.0+ 기기를 조사할 땐 프레임워크 SPL 하나로 결론 내지 말 것.
- **`-01` vs `-05`**: 끝자리를 무시하면 같은 달이라도 코드 상태를 잘못 읽는다. 커널·폐쇄소스 컴포넌트 이슈는 대개 `-05`에 몰린다. `Source-confirmed`
- **불리틴의 사후 수정**: 불리틴은 개정 표기 없이 내용이 바뀌기도 한다. `Inferred`(스터디 관측) 그래서 "불리틴이 이렇게 말했다"보다 불리틴이 링크한 **커밋 자체**를 근거로 삼는 편이 안전하다.
- **에뮬레이터 한계**: AVD의 SPL/API는 시스템 이미지가 정하며, 실기기의 벤더별 patch-gap을 재현하지 못한다. 파티션 SPL 불일치 같은 현상은 실제 기기 이미지로만 관측된다(공개·허가 대상 한정).
- SPL은 신뢰뿌리가 아니다. 최종 판정은 언제나 코드/바이너리 diff(이 파트 14장)로 넘긴다.

## 정리

- SPL은 빌드 때 손으로 넣은 주장이다. "패치됨"의 증명이 아니라 조사 시작점으로만 쓴다.
- API level·릴리스·SPL은 서로 다른 시계로 움직이는 독립축이고, 특히 SPL은 `-01`/`-05` 끝자리까지 읽어야 한다.
- 코드가 실제로 바뀌었는지는 불리틴이 링크한 커밋의 존재 여부, 즉 baseline↔patched diff로만 확정된다.

**점검 질문** — (1) 같은 달 SPL인데 `-01`과 `-05`가 코드 상태에서 무엇이 다른가? (2) 프레임워크 SPL만으로 "패치됨"을 단정하면 어떤 표면을 놓치는가? (3) SPL이 코드 내용을 보장하지 못하는 근본 원인은 무엇인가?

**참고** — [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [Build.VERSION (SDK_INT / SECURITY_PATCH)](https://developer.android.com/reference/android/os/Build.VERSION) · [AOSP build numbers](https://source.android.com/docs/setup/reference/build-numbers)

*다음 글: [System Service 공격 표면](/posts/android-vulnresearch-p4c05/).*
