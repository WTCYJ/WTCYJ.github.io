---
layout: post
title: "patch-gap·backport 누락 — SPL이 약속한 패치와 이미지에 실제로 있는 코드"
date: 2027-01-10 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, PatchGap, SPL, 백포트, SecurityBulletin]
excerpt: "SPL(ro.build.version.security_patch)은 빌드 때 박아 넣는 자기신고 문자열이라, 2021-05-05를 표시하는 기기가 그 날짜의 패치를 전부 갖고 있다는 증명은 아니다 — SRLabs는 SPL이 같아도 일부 패치가 빠진 'hidden patch gap'을 실측했다."
---

n-day 취약점이 위험한 이유는 대개 제로데이가 아니다. **이미 고쳐졌는데 내 기기엔 아직 안 들어온** 패치가 위험하다. 공개된 수정 커밋과 월간 불리틴은 방어자에게만 지도가 아니라 공격자에게도 지도다. 그 지도(공개 수정)와 실제 기기 사이에 벌어진 시간·코드 격차가 **patch gap**이고, 어떤 릴리스 브랜치에는 고쳐 놓고 다른 지원 브랜치에는 안 옮긴 것이 **backport 누락**이다.

이 글은 SPL(보안 패치 수준) 문자열이 실제로 무엇을 보장하고 무엇을 보장하지 않는지, 그리고 공개 소스(AOSP)와 이미 패치된 공개 CVE만으로 patch gap과 backport 누락을 어떻게 확인하는지 분석·정리한 기록이다. 무기화가 아니라, "이 기기가 정말 그 패치를 갖고 있는가"를 검증하는 연구 워크플로가 목표다.

> **한 줄 결론**: SPL은 빌드 때 박아 넣는 자기신고 문자열이지, 어떤 패치가 실제로 들어있는지의 증명이 아니다. patch gap 연구는 "SPL이 약속한 패치 집합"과 "이미지에 실제로 있는 코드"의 차이를 좁혀 가며 확인하는 일이다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 (1) SPL 문자열의 의미와 두 단계 구조, (2) upstream 수정 → 불리틴 → OEM → OTA로 이어지는 격차의 발생 지점, (3) git 계보와 baseline/patched 비교로 backport 누락을 잡아내는 방법을 다룬다. 익스플로잇을 만들지 않고, 이미 공개·패치된 사안만 대상으로 한다.

선수 지식이 세 개 깔린다. 2장(git log/blame/tag·패치 계보)에서 다룬 `git tag/branch --contains`가 여기서 backport 추적의 주력 도구가 되고, 3장(Security Bulletin·patch provenance)에서 정리한 불리틴↔커밋 연결이 "이 SPL이 무엇을 약속하는지"의 출발점이다. 그리고 14장(이미지 baseline/patched 비교)의 바이너리 대조 기법이, 소스가 없는 벤더 이미지에서 패치 존재 여부를 확인하는 유일한 길이 된다. 전체 4부 흐름에서 이 장은 "패치가 어디까지 퍼졌는가(확산의 실측)"를 담당한다 — 앞이 개별 수정의 계보였다면, 여기는 그 수정이 실제 기기 모집단에 도달했는지의 문제다.

## 핵심 개념 — 세 개의 시계와 하나의 문자열

patch gap을 이해하려면 서로 다른 속도로 도는 시계 세 개를 분리해야 한다.

| 시계 | 무엇을 재나 | 연구자가 보는 곳 |
|--|--|--|
| upstream 수정 시계 | AOSP/Linux stable에 fix 커밋이 머지된 시각 | git log, gerrit, kernel stable 트리 |
| 불리틴/SPL 시계 | 그 수정이 어느 월간 SPL에 귀속됐나 | Android Security Bulletin |
| 기기 OTA 시계 | OEM이 통합해 사용자에게 내려간 시각 | 기기 `ro.build.version.security_patch` |

**patch gap = 이 세 시계의 격차**다. 상단(upstream→불리틴)은 며칠~몇 주지만, 하단(불리틴→OTA)은 OEM·모델에 따라 몇 달로 벌어진다. `Inferred` 내 wabt 퍼징에서 보고→머지가 78일이었는데, 그건 오픈소스 한 프로젝트의 *상단*만이다 — 안드로이드 기기는 그 위에 OEM 통합과 OTA 배포가 더 얹힌다. `Reported`

SPL 문자열은 이 확산을 한 줄로 요약한 값이다. Android 보안 불리틴은 매월 **두 단계**를 발행한다: `YYYY-MM-01`과 `YYYY-MM-05`. -01 수준은 프레임워크/플랫폼 이슈를, -05 수준은 -01의 모든 이슈에 더해 커널·벤더·closed-source 컴포넌트 이슈까지 포함한다. `Source-confirmed` 즉 SPL이 `2021-05-05`라면 "2021-05-05 불리틴이 나열한 모든 이슈가 반영됨"을 **주장**한다.

**backport 누락**은 이 확산이 한 브랜치를 빠뜨렸을 때다. 수정이 main과 최신 릴리스 브랜치엔 들어갔지만, 아직 지원되는 이전 릴리스 브랜치엔 cherry-pick되지 않으면, 그 브랜치를 쓰는 기기는 SPL을 올려도 정작 코드는 취약한 채로 남는다. SRLabs는 2018년 "Mind the Gap" 연구에서, SPL이 같은 기기들 사이에서도 일부 패치가 빠진 **hidden patch gap**을 바이너리 수준으로 실측해 보였다(측정 도구 SnoopSnitch). `Reported`

> **[그림 1]** 에뮬레이터에서 `adb shell getprop ro.build.version.security_patch`로 기기가 주장하는 SPL 문자열을 확인한 터미널 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

여기서의 신뢰 경계는 **SPL이 약속하는 것**과 **이미지에 실제로 있는 코드** 사이에 있다. SPL은 기기가 자기 자신에 대해 내놓는 진술이지, 검증된 증거가 아니다.

위협 모델은 n-day 공격자다. 공격자는 공개된 수정 커밋에서 취약 코드 경로와 패치 diff를 그대로 읽을 수 있고(공개 소스이므로), 특정 기기 모델과 SPL을 알면 "이 모델의 이 SPL 빌드가 아직 이 backport를 안 받았다"를 노릴 수 있다. patch gap이 열려 있는 창이 곧 n-day 공격 창이다. `Inferred`

연구자 관점의 위협 모델은 다르다. 공격이 아니라 **오탐**이 적이다 — SPL만 보고 "패치됨"으로 결론 내렸다가, 실제로는 벤더 포크에서 backport가 빠져 있던 경우. 그래서 SPL은 조사의 *출발 가설*이지 결론이 아니다. 조사 범위는 전부 로컬 에뮬레이터 이미지·공개 AOSP 소스·이미 패치된 공개 CVE로 한정하고, 실기기 익스플로잇·실서비스 공격은 하지 않는다.

## 분석 — patch gap을 어떻게 확인하나

절차는 "SPL이 약속한 것"에서 시작해 "실제로 있는 것"으로 좁혀 간다.

1. 기기가 주장하는 SPL을 읽는다.
2. 그 SPL의 불리틴에서 대상 CVE(들)와 각 CVE의 수정 커밋을 확인한다(3장).
3. 소스가 있으면 git 계보로, 없으면 바이너리 대조로 그 커밋이 이미지에 실제로 들어있는지 확인한다.

```bash
# 1) 기기가 주장하는 보안 패치 수준
adb shell getprop ro.build.version.security_patch     # 예: 2021-05-05

# 2~3) AOSP 체크아웃에서 특정 수정 커밋의 계보 확인 (2장의 도구)
git log --oneline -- <취약했던 파일 경로>
git tag    --contains <fix-commit>     # 이 수정이 들어간 릴리스 태그들
git branch -r --contains <fix-commit>  # 이 수정이 있는 브랜치들
```

`git tag --contains`가 backport 누락 탐지의 핵심이다. 어떤 릴리스 태그가 수정 커밋을 "포함(contains)"하지 않는다면, 그 태그로 만든 이미지에는 그 수정이 없다 — SPL이 뭐라 주장하든. `Source-confirmed`(git의 `--contains`는 해당 커밋이 조상으로 도달 가능한 ref만 나열한다)

`예시 출력`(네 실제 실행으로 교체):

```
$ adb shell getprop ro.build.version.security_patch
2021-05-05

$ git tag --contains a1b2c3d
android-13.0.0_r1
android-13.0.0_r2
# android-12 계열 태그가 여기 없다 → 12로의 backport 누락 의심
# (단, 이전 브랜치는 별도 cherry-pick 커밋을 쓸 수 있으니 그 브랜치의
#  해당 파일 blame으로 재확인 — tag만으로 단정 금지)
```

소스가 없는 벤더 closed 컴포넌트라면 이 git 경로가 막힌다. 그때는 14장의 baseline/patched 바이너리 대조로 넘어간다 — 패치 전/후 함수의 시그니처(추가된 경계검사, 바뀐 분기)를 대상 이미지에서 찾아 존재 여부를 판정한다. SRLabs의 SnoopSnitch가 대규모로 한 게 정확히 이 바이너리 수준 판정이다. `Reported`

> **[그림 2]** AOSP 체크아웃에서 `git tag --contains <fix-commit>`로 특정 수정 커밋이 어느 릴리스 태그에 포함됐는지 확인해, 이전 브랜치에 backport가 빠졌는지 대조한 화면 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

SPL이 "주장"에 그치는 근본 이유는 그 값이 **빌드 시 설정 변수에서 나오는 문자열**이라는 데 있다. SPL은 빌드 구성의 보안 패치 날짜 변수 `PLATFORM_SECURITY_PATCH`(build/make/core/version_defaults.mk)에서 채워지며, CDD는 이 값이 실제 패치 수준을 정확히 반영하도록 *요구*하지만 이는 정책적 요구지 암호학적 증명이 아니다. `Inferred` 빌드하는 쪽이 날짜를 올리면서 커밋을 하나 빠뜨려도, 문자열 자체는 아무 불평 없이 올라간다.

backport 누락이 구조적으로 발생하는 이유는 **분기의 다수성과 수동성**이다. 하나의 수정을 main·최신 릴리스·이전 지원 릴리스·각 OEM 포크·각 커널 LTS까지 옮기는 일은 대부분 수동 cherry-pick이고, 포크마다 코드 경로가 미묘하게 달라 같은 diff가 그대로 안 붙는다. 하나만 빠뜨려도 그 분기에 조용한 gap이 생긴다. `Inferred`

불리틴이 upstream 커밋을 참조하더라도, OEM은 자기 포크에서 불완전하게 cherry-pick하거나 다른 경로에만 적용할 수 있다. 게다가 불리틴 자체가 **개정 표기 없이 사후 수정**되기도 한다 — 커밋 링크나 CVE 귀속이 조용히 바뀌면, 어제 잡아둔 provenance가 오늘 어긋난다. `Reported` 그래서 provenance는 "불리틴이 이렇게 말했다"가 아니라 "커밋이 실제로 이 코드를 이렇게 바꿨다"에 앵커해야 한다.

## 방어와 회귀 검증

- **SPL을 결론이 아니라 가설로.** "SPL이 X면 CVE-Y는 안전"은 backport가 실제로 있는지 확인하기 전까진 미검증 주장이다. 대상 CVE마다 커밋 존재를 git 또는 바이너리로 확인해 표를 채운다.
- **backport는 회귀를 검증한다.** 이전 브랜치로 옮긴 수정이 불완전하거나, 나중 변경이 그 수정을 되돌리기도 한다. 내 CVE 재현 스터디에서 CVE-2024-26926은 앞선 수정(20938 계열)의 **회귀**로 정리됐다 — 한 번 고친 자리도 이후 커밋이 되살릴 수 있다는 실물 사례다. `Reported` 그래서 "패치 존재 확인"만으로 부족하고, 취약 경로가 실제로 닫혔는지 회귀 관점 재확인이 필요하다(회귀 검증 자체는 18장 주제).
- **커널은 LTS 준수로 gap을 줄인다.** Android common kernel 브랜치는 Linux LTS/stable에서 수정을 병합하는 구조라, 기기 커널이 upstream LTS를 꾸준히 따라오면 커널 patch gap이 좁아진다. `Source-confirmed` 반대로 LTS에서 이탈해 고정된 포크는 backport 누락이 누적된다.
- **판정의 함정.** `git tag --contains`에 태그가 안 보인다고 곧장 "취약"으로 단정하지 말 것 — 이전 브랜치는 동일 내용을 별도 cherry-pick 커밋(다른 해시)으로 담았을 수 있다. 태그 부재는 *신호*고, 확정은 그 브랜치의 해당 파일 blame/diff로 한다.

## 정리

- SPL(`ro.build.version.security_patch`)은 자기신고 문자열이다. 같은 SPL이라도 특정 backport가 빠진 hidden patch gap이 존재할 수 있다.
- 불리틴은 두 단계(-01/-05) SPL로 발행되며, -05가 커널·벤더까지 포함한다. SPL이 약속한 집합과 이미지 실제 코드의 차이를 좁히는 것이 조사다.
- 소스가 있으면 `git tag/branch --contains`로, 없으면 baseline/patched 바이너리 대조(14장)로 패치 존재를 판정한다 — 단, 태그 부재는 단정이 아니라 재확인 신호다.
- 확인은 "패치가 있다"에서 멈추지 말고 "취약 경로가 실제로 닫혔다"(회귀)까지 간다.

**점검 질문** — (1) SPL이 `2021-05-05`인 두 기기가 같은 CVE에 대해 다른 상태일 수 있는 이유는? (2) `git tag --contains <fix>`에 이전 릴리스 태그가 없을 때, 곧바로 "취약"이라 단정하면 안 되는 이유는? (3) 불리틴이 커밋 대신 "SPL 날짜"만 앵커로 쓰면 provenance가 왜 취약해지나?

**참고** — [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [보안 패치 수준/업데이트](https://source.android.com/docs/security/overview/updates-resources) · [Android common kernels](https://source.android.com/docs/core/architecture/kernel/android-common) · SRLabs "Mind the Gap"(Hack in the Box Amsterdam 2018) 및 SnoopSnitch

*다음 글: [semantic patch·정적 규칙](/posts/android-vulnresearch-p4c16/).*
