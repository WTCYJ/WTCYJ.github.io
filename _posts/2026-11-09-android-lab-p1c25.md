---
layout: post
title: "Semgrep·CodeQL·Androguard 커스텀 규칙 작성: 데이터플로우 taint로 프로젝트 고유 결함 잡기"
date: 2026-11-09 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Semgrep, CodeQL, Androguard, taint, SAST]
excerpt: "같은 결함을 세 도구로 잡는 것 같지만 셋은 서로 다른 것을 본다 — Semgrep 오픈소스판 taint는 대개 함수 안(intraprocedural)에 머물러 메서드를 건너뛰는 흐름을 놓치고, CodeQL은 대개 컴파일되는 소스를 요구하며(최신 `build-mode: none`은 예외), Androguard는 소스 없이 DEX만 보되 taint 엔진이 아니라 XREF 도달성만 준다."
---

기성 스캐너는 "일반적으로 위험한 패턴"을 안다. 하지만 우리 앱 고유의 결함 — 이 액티비티의 이 intent extra가 저 provider의 `rawQuery`로 흘러 들어가는 흐름 — 은 규칙을 직접 써야 잡힌다. 앞 장(24장)에서 MobSF가 놓친 것이 바로 이런 프로젝트 고유의 데이터플로우였다. 그래서 이번엔 `source → sink`를 내 손으로 정의한다. 이 글은 같은 결함 하나(untrusted Intent → SQL sink)를 Semgrep·CodeQL·Androguard 세 도구로 각각 규칙화하고, 표현력·정밀도·재현율을 자작 취약앱에서 교차 검증한 실습 기록이다.

핵심은 "세 도구가 같은 답을 준다"가 아니라 **세 도구가 애초에 서로 다른 것을 본다**는 점이다. 입력(소스 vs 바이트코드), taint 범위(함수 내 vs 전역), 엔진 유무가 다르므로 결과의 성격도 다르다.

> **한 줄 결론**: 세 도구는 상호 대체재가 아니라 상호 보완재다 — Semgrep은 빠른 문법 패턴, CodeQL은 전역 데이터플로우, Androguard는 소스 없는 DEX 도달성. 하나의 결과만 믿으면 그 도구의 사각지대가 곧 나의 사각지대가 된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 하나의 데이터플로우 결함을 세 규칙 언어로 표현하고, 심어둔 결함을 정확히 잡는지(양성)·안전 변형에는 오발화하지 않는지(음성)를 자기검증하는 과정을 다룬다. Semgrep은 `mode: taint`의 `pattern-sources`/`pattern-sinks`로, CodeQL은 데이터플로우 쿼리로, Androguard는 XREF 기반 파이썬 스크립트로 접근한다.

선수 지식이 셋 깔린다. 앞 24장의 수동 검증 결과(스캐너가 놓친 흐름)가 이 장의 출발점이고, 실습 5장의 apktool/smali 감각은 Androguard가 다루는 DEX 계층을 읽는 데 필요하며, 실습 20장의 Ghidra/Rizin 경험은 "바이트코드에서 호출 그래프를 따라간다"는 발상과 이어진다. 개념 축으로는 Atlas C13(DEX 포맷)이 Androguard의 입력이 무엇인지를, Atlas C15(ClassLoader·리플렉션)가 왜 정적 도구가 동적 로딩·리플렉션 앞에서 흐름을 놓치는지를, Atlas C43(patch diff·variant analysis)이 왜 규칙을 "변종까지 잡게" 일반화해야 하는지를 설명한다.

전체 구조에서 이 장은 24장(자동 결과의 수동 검증)과 26장(MASVS 커버리지 매트릭스) 사이에 놓인다. 24장에서 "무엇을 놓쳤나"를 확인했다면, 이 장은 "놓친 것을 잡는 규칙을 어떻게 쓰나"이고, 26장은 그 규칙 산출물을 요구사항의 증적으로 엮는다.

## 핵심 개념 — 세 엔진은 서로 다른 것을 본다

같은 취약 코드를 놓고 세 도구를 붙이면 결과가 갈리는데, 원인은 규칙을 못 써서가 아니라 입력과 엔진이 달라서다.

| 도구 | 입력 | 분석 대상 | taint 범위 | 규칙 언어 |
|--|--|--|--|--|
| Semgrep(OSS) | **소스** 트리(Java/Kotlin) | AST | 대개 함수 내(intraprocedural) | YAML 패턴 + `mode: taint` |
| CodeQL | 컴파일된 **소스**로 만든 DB | 데이터플로우 그래프 | 전역(interprocedural) | QL(선언형 쿼리) |
| Androguard | **APK/DEX**(소스 불필요) | Dalvik 바이트코드·XREF | taint 엔진 없음(도달성 근사) | Python API |

세 가지 오개념을 여기서 짚는다.

- **"Semgrep taint면 어디까지든 따라간다"** — 오픈소스판의 taint는 대체로 함수 내부에 머문다. 여러 메서드·파일을 건너뛰는 전역 흐름은 Pro/엔진 계열 기능에 가깝다(정확한 경계는 원문 재확인 필요). 그래서 `getStringExtra`와 `rawQuery`가 다른 메서드에 흩어져 있으면 규칙이 맞아도 흐름을 못 잇는다. `Reported`
- **"CodeQL은 소스만 있으면 된다"** — 기본값(`autobuild`·`manual`)에서는 소스를 **빌드하며** DB를 만들고, 빌드가 안 되면 DB도 쿼리도 없다. 다만 최신 CodeQL은 Java/Kotlin에 `build-mode: none`(빌드리스 추출, 2024년 GA)을 제공해 컴파일 없이도 DB를 만들 수 있다 — 대신 의존성 타입 해석이 불완전해 데이터플로우 정확도가 떨어진다. 그래서 규칙을 게시할 땐 어떤 build-mode로 DB를 만들었는지 함께 표기한다. `Source-confirmed`
- **"Androguard로 taint 하면 된다"** — Androguard는 taint 엔진이 아니다. `getStringExtra` 호출부와 `rawQuery` 호출부 사이의 XREF(호출 관계) 도달성으로 흐름을 **근사**할 뿐, 실제 값이 흘렀는지는 보장하지 않는다. `Inferred`

즉 소스가 있으면 Semgrep/CodeQL, APK만 있으면 Androguard가 자리를 잡고, 정밀한 전역 흐름이 필요하면 CodeQL, 빠른 문법 매치가 필요하면 Semgrep이다.

> **[그림 1]** 같은 취약 메서드에 대해 Semgrep `mode: taint` 규칙과 그 매치 결과(source→sink 경로)를 한 화면에 띄운 터미널/에디터 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 취약앱 소스 트리**와 세 도구의 **오픈소스판 로컬 설치**로만 진행한다. 제3자 앱·프로덕션 앱은 스캔하지 않는다. 규칙이 겨냥할 결함과 그 안전 변형을 내가 직접 심어두고(양성/음성 대조 케이스), 각 도구가 양성을 잡고 음성에 오발화하지 않는지를 자기검증한다. 무기화된 익스플로잇은 없고, PoC는 흐름을 드러내는 최소 개념 수준에 머문다.

겨냥할 결함은 하나로 고정한다 — 신뢰 불가한 Intent extra가 SQL 문자열에 그대로 이어지는 SQL 인젝션.

```java
// [양성] 취약: intent extra가 rawQuery로 직접 흐름
String q = getIntent().getStringExtra("q");
Cursor c = db.rawQuery("SELECT * FROM users WHERE name = '" + q + "'", null);

// [음성] 안전: 파라미터 바인딩 (같은 소스, 다른 sink 형태)
Cursor c = db.rawQuery("SELECT * FROM users WHERE name = ?", new String[]{ q });
```

## 실습 절차와 관측

### 가설

- **가설 A** — 세 도구 모두 양성(취약)을 잡되, Semgrep은 source와 sink가 **다른 메서드**로 분리되면(전역 흐름) 놓친다. `Inferred`
- **가설 B** — CodeQL은 barrier/sanitizer(파라미터 바인딩)를 흐름 차단으로 모델링하면 음성에 오발화하지 않지만, Androguard의 XREF 도달성은 sink "형태"를 구분하지 못해 음성에서도 발화(오탐)하기 쉽다. `Inferred`

### 절차

1. 자작 앱 소스에 위 양성/음성 메서드를 각각 심고, 추가로 양성 흐름을 **두 메서드로 쪼갠** 변형(전역 흐름)을 하나 더 둔다.
2. Semgrep 규칙(`mode: taint`)을 소스 트리에 적용한다.
3. CodeQL DB를 빌드로 생성한 뒤 데이터플로우 쿼리를 돌린다.
4. 앱을 빌드해 APK를 만들고 Androguard 스크립트로 XREF 도달성을 확인한다.
5. 각 도구의 양성 검출 여부·음성 오발화 여부·전역 흐름 검출 여부를 표로 기록한다.

Semgrep 규칙(개념 수준):

```yaml
rules:
  - id: intent-extra-to-rawquery
    languages: [java]
    severity: ERROR
    mode: taint
    message: "신뢰 불가 Intent extra가 rawQuery로 흐름 (SQLi)"
    pattern-sources:
      - pattern: (Intent $I).getStringExtra(...)
    pattern-sinks:
      - pattern: $DB.rawQuery($SQL, ...)
    pattern-sanitizers:
      # 파라미터 바인딩은 sink 형태로 근사 차단 (정확도는 케이스별 재확인 필요)
      - pattern: $DB.rawQuery("...", new String[]{ ... })
```

한 가지 주의: 위 sink 패턴 `$DB.rawQuery($SQL, ...)`의 `...`는 두 번째 인자(`selectionArgs`)까지 포함하므로, 안전한 `rawQuery("...=?", new String[]{ q })`에서도 taint가 두 번째 인자를 타고 sink에 닿아 오탐이 날 수 있다. 그래서 위처럼 sanitizer로 되막는데, 정석은 애초에 sink를 SQL 문자열 인자 하나로 좁혀(예: 첫 인자만 sink로 지정) 음성이 sink에 닿지 않게 하는 것이다 — sanitizer 되막기는 근사에 가깝다.

CodeQL 쿼리(개념 골격 — 정확한 데이터플로우 API 세대는 원문 재확인 필요):

```ql
import java
import semmle.code.java.dataflow.TaintTracking
// source: Intent.getStringExtra(...) 반환값
// sink:   SQLiteDatabase.rawQuery(...) 의 SQL 인자
// barrier: 파라미터 바인딩 경로
// isSource / isSink / isBarrier 로 정의하고 flowPath 로 경로를 출력
```

Androguard 스크립트(개념 수준):

```python
from androguard.misc import AnalyzeAPK
a, d, dx = AnalyzeAPK("app-debug.apk")
# rawQuery 호출부를 찾고, 그 호출자(caller)에서 getStringExtra 로의
# XREF 도달성을 확인 — 실제 값 흐름이 아니라 '호출 관계 도달성' 근사
for m in dx.find_methods(methodname="rawQuery"):
    for _, caller, _ in m.get_xref_from():
        print(caller.name)   # 예시 로직: 도달성만 판정
```

> **[그림 2]** 같은 결함에 대해 Semgrep·CodeQL·Androguard 각각의 탐지 결과와, 음성(파라미터 바인딩) 대조 케이스에서의 미발화/오발화를 나란히 비교한 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — 아래는 형식 예시이며, 실제 실행 결과로 교체한다.

```
# Semgrep (같은 메서드 내 흐름)
intent-extra-to-rawquery  app/.../UserActivity.java:42  ERROR   ← 양성 검출
# Semgrep (두 메서드로 분리된 전역 흐름)
(검출 없음)                                                       ← 놓침(가설 A)
# 음성(파라미터 바인딩)
(검출 없음)                                                       ← 오발화 없음

# CodeQL
경로: getStringExtra → (helper) → rawQuery                        ← 전역 흐름 검출
음성: barrier(바인딩)로 경로 차단 → 결과 없음

# Androguard
rawQuery caller: queryUser  (getStringExtra 도달 가능)            ← 도달성 발화
음성에서도 caller 도달성 발화 가능 → 형태 구분 못 함(오탐 소지)
```

정밀도·재현율을 한 표로 정리하면 아래와 같다. 이 표가 이 글의 실용적 결론이다.

| 도구 | 함수 내 양성 | 전역 흐름 양성 | 음성 오발화 | 강점 | 대가 |
|--|--|--|--|--|--|
| Semgrep(OSS) | 잡음 | **놓치기 쉬움** | 적음 | 빠름·규칙 쉬움 | 전역 재현율↓ |
| CodeQL | 잡음 | 잡음 | barrier로 억제 | 전역 정밀도↑ | 빌드·DB·느림 |
| Androguard | (도달성) 발화 | (도달성) 발화 | **발화 소지(오탐)** | 소스 불필요 | taint 아님·정밀도↓ |

## Root Cause — 왜 세 결과가 갈리는가

결과가 갈리는 근본 원인은 규칙 품질이 아니라 **엔진 모델의 차이**다.

Semgrep 오픈소스판이 전역 흐름을 놓치는 건, taint 전파가 대체로 함수 경계 안에서 끝나기 때문이다. source와 sink가 한 메서드에 있으면 매치되지만 helper를 거치면 전파가 끊긴다. 이건 규칙을 더 잘 써서 메우는 문제가 아니라 엔진 범위의 한계다(전역 taint는 상위 계열 기능, 경계는 원문 재확인 필요). `Reported`

CodeQL이 전역 흐름을 잡는 건, 소스를 컴파일해 만든 데이터플로우 그래프 위에서 interprocedural 추적을 하기 때문이다. 대신 그 대가로 빌드 가능한 소스와 DB 생성·쿼리 실행 비용이 든다. `Source-confirmed` barrier(sanitizer)를 명시하면 음성 오발화를 억제할 수 있는 것도 그래프 모델 덕이다.

Androguard가 음성에서도 발화하기 쉬운 건, 그것이 taint가 아니라 **XREF 도달성**이기 때문이다. `getStringExtra`를 부른 메서드가 `rawQuery`도 부른다는 사실은 "값이 흘렀다"가 아니라 "호출 관계가 이어진다"만 말한다. 파라미터 바인딩(음성)이든 문자열 연결(양성)이든 호출 그래프상 도달성은 같을 수 있어, sink 형태를 구분하지 못한다. `Inferred` 그래서 Androguard는 "소스가 없을 때의 1차 선별"로 강하고, 판정은 다시 수동 검증(24장)으로 넘겨야 한다.

## 버전 차이와 한계

- **Semgrep**: 오픈소스판과 상위 계열의 taint 범위가 다르다. 문서에 적을 땐 어떤 판·버전에서 어디까지 전파됐는지 표기한다(interprocedural 지원 경계는 버전별로 다르니 원문 재확인 필요). `Reported`
- **CodeQL**: 데이터플로우 API가 세대에 걸쳐 바뀌었다(구 `TaintTracking::Configuration` 계열 vs 신 모듈형). 쿼리를 게시할 땐 CodeQL 버전과 쿼리팩 버전을 함께 표기한다 — 그렇지 않으면 남이 재현할 때 컴파일이 안 된다. Kotlin 소스 지원 범위도 버전별로 다르니 원문 재확인 필요. `Reported`
- **Androguard**: 리플렉션·동적 로딩(Atlas C15) 앞에서 XREF가 끊긴다. `Class.forName`·`DexClassLoader`로 우회된 호출은 정적으로 이어지지 않아, 정적 도달성만으로는 미탐이 남는다. 이 사각지대는 동적분석(11장 mitmproxy·후속 후킹)으로 메운다. `Inferred`
- 공통 한계: 세 도구 모두 규칙이 겨냥한 것만 잡는다. 심어둔 양성/음성 대조 케이스로 규칙 자체를 검증하지 않으면, "안 나왔다"가 "결함이 없다"인지 "규칙이 못 잡았다"인지 구분되지 않는다.

## 정리

- 세 도구는 대체재가 아니라 보완재다 — Semgrep(빠른 문법 패턴)·CodeQL(전역 데이터플로우)·Androguard(소스 없는 DEX 도달성).
- Semgrep OSS taint는 함수 경계에서 끊기기 쉽고, CodeQL은 빌드·DB를 요구하며, Androguard는 taint가 아니라 XREF 도달성이다 — 각 결과의 성격을 알고 읽어야 한다.
- 규칙은 심어둔 양성/음성 대조 케이스로 자기검증한다. "안 나옴"을 "안전"으로 읽지 않는 유일한 방법이다.
- 정적 3종의 미탐(리플렉션·동적 로딩)은 동적분석으로 메운다.

**점검 질문** — (1) source와 sink가 다른 메서드에 있을 때 Semgrep 오픈소스판이 흐름을 놓치는 이유는? (2) CodeQL 데이터플로우 쿼리를 돌리려면 소스 외에 무엇이 더 필요한가? (3) Androguard의 XREF 도달성이 왜 taint가 아니며, 그 결과 음성 케이스에서 어떤 오류가 나기 쉬운가?

**참고** — Semgrep 공식 규칙 문서(taint mode) · GitHub CodeQL `java-security` 쿼리팩 문서 · Androguard 공식 문서

*다음 글: [MASVS 요구사항을 MASTG 검증 절차로: 커버리지 매트릭스로 감사 재현하기](/posts/android-lab-p1c26/).*
