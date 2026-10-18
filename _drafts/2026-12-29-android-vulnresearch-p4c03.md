---
layout: post
title: "Security Bulletin·patch provenance"
date: 2026-12-29 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, SecurityBulletin, CVE, PatchProvenance, SPL]
excerpt: "안드로이드 보안 불리틴에서 진짜 근거는 표가 아니라 링크된 커밋의 diff 하나다. 태그 diff를 CVE 수정으로 읽거나 NVD 설명을 그대로 믿으면 엉뚱한 코드를 패치라 부르게 되고, 게다가 불리틴은 개정 표기 없이 조용히 바뀐다."
---

취약점 연구는 대개 "이미 고쳐진 것"에서 출발한다. 이미 패치된 공개 CVE를 골라 그 수정 커밋을 읽고, 형제 변종(sibling variant)이나 백포트 누락(patch-gap)을 찾는 흐름이다. 그런데 이 흐름 전체가 딱 하나에 매달려 있다 — **그 CVE의 진짜 수정 커밋이 무엇인가**. 이걸 잘못 짚으면 이후 분석이 통째로 엉뚱한 코드 위에 세워진다. patch provenance, 즉 수정의 출처를 정확히 확립하는 일이 연구의 첫 단추다.

문제는 이 첫 단추가 조용히 틀린다는 데 있다. 안드로이드 보안 불리틴은 CVE를 커밋 링크와 함께 게시하지만, 연구자는 종종 링크된 커밋 대신 릴리스 태그의 diff를 통째로 보거나, 불리틴 대신 NVD 설명을 근거로 삼거나, 표를 눈으로 세다 오집계한다. 이 글은 불리틴에서 실제 수정 커밋까지 내려가 provenance를 확립하는 방법과, 그 과정에서 반복해서 걸려 넘어지는 함정들을 정리한 기록이다.

> **한 줄 결론**: 어떤 CVE의 진짜 근거는 불리틴이 링크한 **그 커밋의 diff 하나**뿐이다. 태그 diff·NVD 설명·불리틴 표를 근거로 삼으면 provenance가 어긋나고, 불리틴 자체도 개정 표기 없이 바뀌므로 시점은 커밋 해시로 고정해야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 안드로이드 보안 불리틴의 구조(CVE 표·References 열·Type·Severity·Updated AOSP versions), 보안 패치 레벨(SPL)의 의미와 `01`/`05` 두 갈래, 그리고 하나의 CVE 식별자에서 버그 ID(A-번호)를 거쳐 AOSP 커밋 diff까지 내려가는 provenance 확립 절차를 다룬다. 그 위에서 오귀속을 부르는 세 가지 함정을 콕 집는다.

선수 지식은 앞 장에 깔려 있다. 1장에서 AOSP 소스 트리를 내려받아 대상 컴포넌트를 골랐고, 2장에서 `git log`·`git blame`·태그로 커밋 계보를 읽는 법을 익혔다. 이 장은 그 계보 읽기를 "공식 발표(불리틴)"에 정박(anchor)시키는 단계다. 개념적으로는 보안 업데이트·SPL이 무엇을 보장하는지에 대한 배경이 있으면 편하다.

전체 구조에서 이 장은 취약점 연구 파트의 **공통 입구**다. 뒤에 오는 API 레벨/SPL과 실제 코드의 불일치(4장), patch-gap·백포트 누락(15장), sibling variant 사냥(17장), 보안 패치 회귀 검증(18장)이 전부 "정확한 provenance"를 전제로 한다. 여기서 커밋을 잘못 짚으면 그 네 장이 다 무너진다.

## 핵심 개념 — 불리틴에서 커밋까지

안드로이드 보안 불리틴은 매월 게시되고, 각 CVE가 한 행을 차지하는 표로 구성된다. 표의 각 열이 provenance의 재료다.

| 요소 | 어디서 읽나 | 무엇을 뜻하나 |
|--|--|--|
| CVE ID | 표 첫 열 | 식별자일 뿐, 코드가 아니다 |
| References | 표의 References/링크 열 | 버그 ID(`A-XXXXXXXXX`) + AOSP 커밋 링크 — **여기가 근거** |
| Type | RCE/EoP/ID/DoS | 영향 유형(과장 금지의 기준선) |
| Severity | Critical/High/… | 심각도(벡터 아닌 카테고리) |
| Updated AOSP versions | 12/13/14 … | 어느 브랜치에 수정이 들어갔나 |

불리틴 상단에는 그 달의 **보안 패치 레벨(SPL)** 문자열이 명시된다. SPL은 `YYYY-MM-DD` 형식이고 한 달에 두 갈래가 나온다 — `YYYY-MM-01`은 프레임워크/AOSP 계열 수정의 부분집합을, `YYYY-MM-05`는 거기에 커널·벤더 등 기기별 수정까지 포함한 전체를 가리킨다. 기기의 SPL은 `ro.build.version.security_patch` 프로퍼티에 박혀 있고, 이 값은 "이 날짜까지의 수정을 포함한다"는 선언이다. `Source-confirmed`

```bash
# 기기/AVD가 어느 SPL까지 포함한다고 주장하는가
adb shell getprop ro.build.version.security_patch
```

```
2024-05-05
```

이 문자열 하나가 4장의 주제(선언한 SPL과 실제 코드의 불일치)로 이어진다. 지금은 "불리틴의 SPL 열과 기기의 SPL 프로퍼티가 같은 축 위에 있다"는 것만 잡고 간다.

> **[그림 1]** source.android.com 보안 불리틴에서 한 달치 CVE 표를 펼친 화면 — CVE / References(A-번호·커밋 링크) / Type / Severity / Updated AOSP versions 다섯 열이 보이도록 캡처 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

여기서의 "위협"은 외부 공격자가 아니라 **나 자신의 오귀속(misattribution)**이다. provenance 체인에는 신뢰 등급이 있고, 그 경계를 넘으면 조용히 틀린다.

- **1차(ground truth)**: 불리틴이 링크한 AOSP 커밋의 diff. 실제로 바뀐 코드는 오직 git 안에만 있다. `Source-confirmed`
- **1차(발표)**: 불리틴 표 자체. 권위 있지만 배포용 요약이고, 개정된다.
- **2차(파생)**: NVD, 벤더 어드바이저리, 블로그. CVE 식별자를 각자 다시 요약하며 원본에서 드리프트한다.

연구자가 2차를 1차처럼 쓰는 순간 경계를 넘는다. NVD 설명을 근거로 "이 함수가 취약하다"고 단언하거나, 남의 블로그가 지목한 파일을 그대로 믿는 식이다. 규칙은 단순하다 — **주장의 근거는 항상 커밋 diff까지 내려가서 확인한다.** 표나 요약은 커밋을 찾아가는 인덱스일 뿐 근거가 아니다. `Inferred`

## 분석 — provenance 확립 절차와 세 함정

### 절차

1. 대상 CVE를 해당 월 불리틴 표에서 찾는다.
2. References 열에서 버그 ID(`A-XXXXXXXXX`)와 AOSP 커밋 링크를 확보한다.
3. 커밋 링크(`android.googlesource.com/...`)를 열어 **diff를 직접 읽는다**. 이 diff가 provenance의 바닥이다.
4. Updated AOSP versions 열로 어느 브랜치에 들어갔는지 기록한다.
5. 그 CVE가 처음 등장한 불리틴의 달 → SPL 월을 확정한다.

References 열을 사람이 아니라 스크립트로 훑으면 오집계를 피할 수 있다. 불리틴 페이지에서 커밋 링크만 뽑아내는 것으로 시작한다.

```bash
# 불리틴 페이지에서 AOSP 커밋 링크만 추출(눈으로 세지 말 것)
curl -s https://source.android.com/docs/security/bulletin/2024-05-01 \
  | grep -oE 'https://android\.googlesource\.com[^"]+' \
  | sort -u
```

```
예시 출력(교체):
https://android.googlesource.com/platform/frameworks/base/+/<commit-hash>
https://android.googlesource.com/platform/frameworks/av/+/<commit-hash>
https://android.googlesource.com/platform/packages/modules/Bluetooth/+/<commit-hash>
```

> **[그림 2]** 불리틴이 링크한 android.googlesource.com 커밋 페이지에서 실제 수정 diff를 펼친 화면 — 바뀐 파일과 라인, 커밋 해시가 보이도록 캡처 — *실측 스크린샷 자리*

### 함정 1 — 태그 diff를 CVE 수정으로 읽는다

릴리스 태그(예: `android-14.0.0_rXX`)의 diff에는 그 릴리스에 담긴 수백 개의 커밋이 섞여 있다. 특정 CVE의 수정은 그중 한두 커밋일 뿐이다. 태그 전체 diff를 "그 CVE 패치"라고 부르면 무관한 변경까지 근본 원인으로 오독하게 된다. 근거는 태그가 아니라 불리틴이 링크한 **개별 커밋**이다. `Inferred`

### 함정 2 — NVD 설명이 실제 수정 코드와 다르다

NVD 항목은 파생 요약이라, 종종 불리틴이 가리키는 것과 다른 컴포넌트나 다른 근본 원인을 지목한다. 실제로 NVD의 서술과 불리틴이 링크한 수정이 서로 다른 취약점을 가리키는 사례가 있다(예: CVE-2020-12856 — NVD와 불리틴의 대상이 어긋난다는 관측). `Reported` 개별 CVE의 정확한 귀속은 항상 불리틴 링크 커밋으로 재확인해야 한다(원문 재확인 필요).

### 함정 3 — 불리틴이 개정 표기 없이 바뀐다

불리틴 하단에는 개정(Revisions) 표가 있지만, CVE 표나 링크의 변경이 그 개정 노트에 항상 반영되지는 않는다. 어제 본 표와 오늘 본 표가 다를 수 있다는 뜻이다. `Reported` 그래서 provenance를 기록할 때는 "불리틴에 그렇게 적혀 있었다"가 아니라 **커밋 해시**로 시점을 고정하고, 필요하면 캡처를 남긴다. 커밋 해시는 개정되지 않는다. `Inferred`

## Root Cause — 왜 provenance가 어긋나는가

근본 원인은 하나다. **불리틴은 소스 오브 트루스가 아니라 배포 문서**라는 것. 실제 변경은 git 커밋에만 존재하고, 불리틴·NVD·벤더 어드바이저리는 그 커밋을 각자의 목적으로 요약한 파생물이다. 파생물은 원본에서 드리프트하기 마련이고, 여러 파생물이 병렬로 갱신되면서 서로, 그리고 원본과 어긋난다. `Inferred`

CVE 식별자 자체도 코드가 아니라 라벨이다. 하나의 CVE가 여러 커밋으로 고쳐질 수도, 한 커밋이 여러 CVE를 건드릴 수도 있다. 태그는 릴리스 스냅샷이라 수많은 수정이 한 diff에 뭉친다. 이 구조에서 "식별자 → 요약 → 추정"으로 가면 반드시 어디선가 미끄러진다. 유일하게 안정적인 경로는 "식별자 → 불리틴 링크 → 커밋 diff"로 **끝까지 내려가는** 것이다. 그리고 집계는 손이 아니라 스크립트로 한다 — 표를 눈으로 옮기는 순간 오집계가 들어온다. `Inferred`

## 버전 차이와 한계

- Updated AOSP versions 열은 그 수정이 **어느 브랜치**(12/13/14 …)에 백포트됐는지를 보여준다. 어떤 브랜치엔 있고 다른 브랜치엔 없으면 그게 patch-gap의 씨앗이다(15장에서 다룬다). 브랜치별 diff가 미묘하게 다를 수 있어, 백포트 변형까지 각 브랜치의 커밋으로 따로 확인해야 한다. `Inferred`
- **커널·벤더 수정은 AOSP git에 없을 수 있다.** `05` 패치 레벨에 포함되는 커널/벤더 수정은 링크가 upstream Linux나 파트너 저장소로 가거나, 아예 공개되지 않는다. 이 경우 provenance는 AOSP 밖(예: kernel/common, upstream 커밋)에서 이어 붙여야 한다. `Source-confirmed`
- 과거 수정이 새 CVE로 **되살아나는 회귀**도 있다. 이전에 고친 결함이 이후 변경으로 재도입되어 별도 CVE로 다시 발표되는 식이다(예: CVE-2024-26926이 앞선 수정의 회귀라는 관측 — 원문 재확인 필요). `Reported` 회귀를 실제로 검증하는 절차는 18장에서 다룬다. 이 장의 범위는 "어떤 커밋이 진짜 수정인가"까지다.
- 안전 범위: 여기서 다루는 대상은 전부 **이미 공개·패치된 CVE와 공개 AOSP 소스**뿐이다. 커밋 diff를 읽고 provenance를 정리하는 것은 방어·연구 목적의 정적 분석이며, 무기화된 익스플로잇 제작과는 무관하다.

## 정리

- 어떤 CVE의 근거는 불리틴 표가 아니라 **불리틴이 링크한 커밋의 diff**다. 표·NVD·태그 diff는 인덱스일 뿐 근거가 아니다.
- SPL은 `YYYY-MM-01`(부분집합)과 `YYYY-MM-05`(커널·벤더 포함 전체) 두 갈래이며, 기기의 `ro.build.version.security_patch`와 같은 축에 있다.
- 불리틴은 개정 표기 없이 바뀔 수 있으니 시점은 **커밋 해시**로 고정하고, 집계는 눈이 아니라 스크립트로 한다.

**점검 질문** — (1) 같은 CVE에서 불리틴 링크 커밋과 릴리스 태그 diff 중 어느 쪽이 근거이고 왜인가? (2) `YYYY-MM-01`과 `YYYY-MM-05` SPL의 차이는 무엇인가? (3) 불리틴 표만 보고 CVE 개수를 집계하면 안 되는 이유는?

**참고** — [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [AOSP 소스(android.googlesource.com)](https://android.googlesource.com) · [보안 업데이트·SPL 개요](https://source.android.com/docs/security/overview/updates-resources) · [NVD](https://nvd.nist.gov)(2차, 발산 지점)

*다음 글: [API level/SPL/실제 코드 불일치](/posts/android-vulnresearch-p4c04/).*
