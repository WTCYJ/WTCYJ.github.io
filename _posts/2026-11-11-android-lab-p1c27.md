---
layout: post
title: "방어 회귀 테스트 설계: 패치된 결함이 변종으로 되살아나지 않게 고정"
date: 2026-11-11 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 회귀테스트, VariantAnalysis, Robolectric, 퍼징]
excerpt: "회귀 테스트의 유일한 존재 증명은 '취약본에서 빨간불'이다. 패치본에서만 돌려 초록불을 보고 안심하면 그 테스트는 아무것도 지키지 못한다. Robolectric의 그림자 프레임워크엔 취약 코드가 아예 없어 양쪽 다 통과하는 미탐 함정도 있다."
---

패치는 결함을 한 번 막는다. 그런데 다음 리팩터링에서 같은 결함이, 혹은 형제 코드 경로의 변종이 조용히 되살아나면 그걸 잡아줄 게 없다. 그래서 익스플로잇을 재현하는 것보다 어려운 일이 **재현을 고정하는 것**이다 — 취약 상태에서는 반드시 실패하고 패치 상태에서는 통과하는 테스트를 남겨, 회귀가 일어나는 순간 빌드를 빨갛게 만드는 일.

이 글은 이미 패치된 공개 CVE를 앵커로 삼아, 취약본에서 실패하고 패치본에서 통과하는 최소 회귀 테스트 하네스를 설계하고 작성한 기록이다. instrumented/Robolectric 단위 테스트와 퍼저 시드 코퍼스를 결합해, 단 하나의 CVE 입력이 아니라 그 결함의 변종 표면까지 방어하도록 만든다.

> **한 줄 결론**: 회귀 테스트의 존재 증명은 "패치본에서 초록불"이 아니라 "취약본에서 빨간불"이다. RED-first로 확인되지 않은 테스트는 아무 일도 안 하는 테스트와 구별되지 않는다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 패치된 결함을 회귀 테스트로 고정하는 세 가지 방법 — instrumented 테스트, Robolectric 단위 테스트, 퍼저 시드 코퍼스 — 을 같은 앵커 CVE에 대해 각각 적용하고, 변종까지 덮도록 parameterize하는 법을 다룬다.

선수 지식이 세 갈래 깔린다. 25장(커스텀 정적 규칙)과 26장(MASVS↔MASTG 커버리지 매트릭스)에서 나온 결함 목록이 이 테스트들의 대상이 된다. 개념적으로는 Atlas C43(patch diff·variant analysis)이 "하나의 근본원인이 형제 경로에서 되살아난다"는 이 글의 뼈대를, Atlas C44(재현성·대조군)가 "취약본/패치본 대조 없이는 아무것도 증명 못 한다"는 전제를, Atlas C25(Parcel 불일치)가 앵커로 쓰는 결함 클래스의 내부 구조를 설명한다. 실습 앵커는 SeiKa의 기존 CVE 재현 10편 중 Parcel 불일치 재현본(CVE-2023-20963)을 재사용한다.

전체 구조에서 이 장은 감사 파이프라인의 **마지막에서 두 번째 칸**이다. 24~26장이 "지금 취약한가"를 판정했다면, 27장은 "다시 취약해지지 않는가"를 시간축으로 고정하고, 28장이 이 산출물을 종합 리포트로 묶는다.

## 핵심 개념 — 회귀 테스트는 대조군이 없으면 존재하지 않는다

회귀 테스트의 값어치는 통과가 아니라 **실패할 수 있음**에서 나온다. 같은 테스트를 취약본과 패치본 두 대조군에 돌려, 취약본=FAIL·패치본=PASS가 나와야 비로소 그 테스트가 "이 결함"을 겨냥한다는 게 증명된다. 패치본에서만 초록불을 본 테스트는, 결함과 무관하게 항상 통과하는 빈 테스트일 수도 있다. 이 대조 없이 커밋한 회귀 테스트는 심리적 안심만 주고 방어는 0이다. `Inferred`

| 방법 | 실행 위치 | 속도 | 충실도 | 주된 미탐 위험 |
|--|--|--|--|--|
| Robolectric 단위 | JVM(그림자 프레임워크) | 빠름 | 낮음 | shadow에 취약 코드가 없어 양쪽 다 PASS |
| instrumented(androidTest) | 에뮬레이터/실기기(실제 프레임워크) | 느림 | 높음 | API 레벨에 취약 경로가 없으면 미재현 |
| 퍼저 시드 코퍼스 | 하네스(파서 직접) | 중간 | 결함 클래스 넓음 | 시드가 결함을 자극 못 하면 통과 |

Robolectric은 JVM 위에서 안드로이드 프레임워크를 **shadow(그림자) 클래스**로 흉내 낸다. `Source-confirmed` 빠르고 기기가 필요 없지만, shadow는 프레임워크의 단순화된 재구현이라 프레임워크 내부 결함(예: Parcel 직렬화 불일치)이 아예 모델링돼 있지 않을 수 있다. 그러면 취약본에서도 테스트가 통과해버리는 미탐이 생긴다. 반대로 instrumented 테스트는 에뮬레이터의 **실제** 프레임워크를 태워 충실하지만 느리고, 취약 경로가 특정 API 레벨에만 있으면 이미지 선택(1장)이 결과를 가른다. `Source-confirmed`

> **[그림 1]** 같은 회귀 테스트를 취약본 APK/이미지와 패치본에서 각각 실행해 '취약본=FAIL, 패치본=PASS'가 나온 test runner 출력 대조 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 앱과 이미 패치된 공개 CVE**로만 진행한다. 앵커는 CVE-2023-20963(WorkSource Parcel 불일치, Framework 권한상승) 재현본의 취약본/패치본 대조다. `Reported`(공식 불리틴 문구는 "a logic error in the code"이고, WorkSource의 Parcel/Bundle 직렬화 바이트 불일치라는 근본원인 특정은 연구자 분석 계열의 서술 — 패치 커밋으로 재확인 필요) 무기화된 완성 익스플로잇은 만들지 않는다 — 회귀 테스트가 필요로 하는 건 "결함을 자극하는 최소 입력"과 "안전한 결과를 단언하는 어서션"뿐이고, 실데이터 탈취·지속성·전파 코드는 테스트에 들어갈 이유가 없다. 취약본은 패치 직전 커밋을, 패치본은 패치 커밋을 각각 체크아웃해 두 개의 AVD/빌드로 나눠 둔다.

## 실습 절차와 관측

### 가설
- **가설 A** — 대조 어서션 `assertEquals(원본.keySet, 재직렬화본.keySet)`은 취약본에서 실패(예상치 못한 키 혼입)하고 패치본에서 통과한다. `Inferred`
- **가설 B** — 같은 결함을 Robolectric으로 옮기면, shadow 프레임워크가 재직렬화 경로를 모델링하지 않아 취약본에서도 통과(=미탐)한다. RED-first 확인 없이는 이 미탐을 알아챌 수 없다. `Inferred`

### 절차
1. 앵커 CVE의 취약 커밋/패치 커밋을 각각 체크아웃해 두 대조군을 만든다(월별 불리틴이 아니라 **커밋 해시**로 고정).
2. instrumented 회귀 테스트를 작성하고 **먼저 취약본에서 실패하는지** 확인한다(RED-first).
3. 같은 로직을 Robolectric으로 옮겨, 취약본에서 통과하면 그 테스트는 미탐임을 기록한다.
4. 결함을 자극한 최소 입력(PoC 바이트)을 회귀 코퍼스에 영구 시드로 넣는다.
5. 변종 표면(경계를 넘는 모든 Parcelable)을 parameterize해 형제 경로까지 덮는다.

```kotlin
// (b) instrumented 회귀 테스트 — 재직렬화가 키를 밀반입하지 않는지 단언
@Test fun reparcel_doesNotSmuggleKeys() {
    val original = Bundle().apply { putParcelable("ws", craftBoundaryInput()) } // 결함 자극 최소 입력
    val bytes    = marshall(original)     // Parcel.marshall
    val restored = unmarshall(bytes)      // 경계(system_server 등)의 재직렬화 흉내
    // 취약본: write/read 바이트 수 불일치로 예상 밖 키가 섞여 들어옴 → FAIL
    assertEquals(original.keySet(), restored.keySet())
}

// (c) 변종 방어 — 하나의 CVE가 아니라 경계 Parcelable 전체를 parameterize
@ParameterizedTest
@MethodSource("boundaryParcelables")      // 신뢰 경계를 넘는 모든 Parcelable
fun noWriteReadSizeMismatch(clazz: Class<out Parcelable>) {
    val obj = defaultInstance(clazz)
    assertEquals(sizeWritten(obj), sizeRead(obj))   // write == read 바이트 수
}
```

```bash
# (d) 퍼저 시드 코퍼스를 영구 회귀 스위트로 고정
cp crash-*.bin regress/corpus/         # 크래시 입력을 리포지토리에 시드로 커밋
# CI: 퍼저를 새로 돌리지 않고 코퍼스만 파서에 먹여도 회귀는 잡힌다
for f in regress/corpus/*.bin; do
  ./parse_harness "$f" || { echo "REGRESSION: $f"; exit 1; }
done
```

> **[그림 2]** PoC Parcel 바이트를 시드 코퍼스에 넣고 파서 하네스에 재입력했을 때, 취약본에서 결함이 재현되고 패치본에서 방어되는(코퍼스 전량 통과) CI 로그 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)`(네 실제 실행으로 교체):

```
# 취약 커밋 (RED-first 확인)
> reparcel_doesNotSmuggleKeys  FAILED
    expected: [ws] but was: [ws, smuggled_uid]

# 패치 커밋
> reparcel_doesNotSmuggleKeys  PASSED
> noWriteReadSizeMismatch[WorkSource]  PASSED

# Robolectric 판(같은 로직) — 취약 커밋인데도
> reparcel_doesNotSmuggleKeys  PASSED   # ← 미탐: shadow에 재직렬화 경로 없음
```

세 줄이 이 실습의 요점이다. instrumented는 취약본에서 빨간불이 떠 유효한 회귀 테스트임이 증명됐고, Robolectric 판은 취약본에서도 초록불이라 **RED-first를 통과하지 못한 가짜 회귀 테스트**다. 이걸 대조 없이 커밋했다면 그린 CI를 보며 방어가 됐다고 착각했을 것이다.

## Root Cause — 왜 이렇게 되는가

회귀 테스트가 "존재만 하고 방어는 0"이 되는 근본 원인은 **대조군의 부재**다. 테스트는 특정 입력에 대한 프로그램 동작을 고정할 뿐, 그 동작이 "결함 때문"인지 "원래 그런지"는 스스로 말하지 못한다. 그 인과를 만드는 유일한 장치가 취약본/패치본 대조(C44)이고, 그래서 RED-first가 선택이 아니라 정의다. 취약본에서 실패하지 않은 테스트는 결함을 겨냥한 적이 없다.

Robolectric 미탐의 뿌리는 다른 결이다. shadow는 프레임워크의 **행위 계약**을 흉내 낸 재구현이지 실제 코드가 아니다. `Source-confirmed` Parcel 직렬화 불일치처럼 결함이 실제 구현의 바이트 레벨 세부에 있으면, 그 세부를 갖지 않은 shadow는 취약도 패치도 아닌 제3의 동작을 하고, 결과적으로 양쪽 다 통과한다. 프레임워크 내부 결함은 원칙적으로 instrumented(실제 프레임워크)로 앵커해야 하는 이유다.

변종이 되살아나는 원인은 **근본원인과 sink 표면의 불일치**다. Parcel 불일치는 특정 클래스 하나의 버그가 아니라 "writeToParcel이 쓴 바이트 수와 read가 읽는 바이트 수가 어긋나는" 클래스 전체의 성질이다. `Reported` 한 클래스만 패치하고 그 클래스만 테스트하면, 같은 성질을 가진 형제 Parcelable에서 결함이 재등장한다. 그래서 회귀 시드는 하나의 입력이 아니라 경계를 넘는 Parcelable 집합에 대한 parameterized 어서션이어야 한다(variant analysis, C43).

## 버전 차이와 한계

- **불리틴은 개정 표기 없이 바뀐다.** 앵커를 "2023년 3월 불리틴"처럼 월로 고정하면, 나중에 패치 커밋 목록이 조용히 갱신됐을 때 대조군이 어긋난다. 반드시 **패치 커밋 해시**로 고정한다. `Reported`(저자 관측 — 공개 불리틴 페이지엔 개정 이력이 표기되지 않아 "개정 표기 없음"은 링크로 1차 증명되지 않음)
- **Robolectric shadow는 SDK 레벨을 따라가며 지연된다.** 최신 프레임워크 픽스가 아직 shadow에 반영 안 됐으면 취약/패치 구분 자체가 불가능하다 — 이 경우 instrumented로 내려야 한다. `Source-confirmed`
- **instrumented 테스트는 API 레벨에 종속된다.** 취약 경로가 특정 릴리스에만 존재하면 AVD 이미지 선택(1장의 `google_apis` userdebug·ABI)이 재현 성패를 가른다. 이미지도 테스트 픽스처의 일부다.
- **퍼저 코퍼스는 시드가 결함을 자극할 때만 회귀를 잡는다.** 크래시 입력을 최소화(minimize)해 시드로 남기되, 원래 크래시를 여전히 재현하는지 커밋 전에 재확인한다.
- CTS(Compatibility Test Suite)와 STS(Security Test Suite)는 별개 스위트지만, 둘 다 결국 CVE별 테스트 메서드를 취약 기기에서 실패·패치 기기에서 통과하도록 앵커한 것과 같은 구조다. `Source-confirmed`(STS 모듈 구성은 원문 재확인 필요)

## 정리

- 회귀 테스트의 존재 증명은 "취약본에서 빨간불(RED-first)"이다. 패치본 초록불만 본 테스트는 방어 0이다.
- 프레임워크 내부 결함은 instrumented로 앵커한다 — Robolectric shadow는 취약 코드를 안 담아 양쪽 다 통과하는 미탐을 낸다.
- 시드 코퍼스와 parameterized 어서션으로 하나의 CVE가 아니라 결함 클래스의 변종 표면까지 덮는다(C43).
- 앵커는 월별 불리틴이 아니라 패치 커밋 해시로 고정한다(불리틴은 개정 표기 없이 바뀐다).

**점검 질문** — (1) 패치본에서만 통과를 확인한 회귀 테스트가 왜 방어 0인가? (2) Parcel 불일치 결함을 Robolectric으로 앵커하면 왜 미탐이 나는가? (3) 하나의 CVE 입력을 시드로 넣는 것만으로 변종을 못 잡는 이유와, parameterize가 그걸 어떻게 해결하는가?

**참고** — [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [CTS(Compatibility Test Suite)](https://source.android.com/docs/compatibility/cts) · [STS(Security Test Suite)](https://source.android.com/docs/security/test-suite) · [Robolectric 공식 문서](https://robolectric.org/) · OWASP MASTG(회귀·재현 절차)

*다음 글: [최종 종합 보안 감사 리포트: 증적·CVSS 심각도·책임공개 타임라인 통합](/posts/android-lab-p1c28/).*
