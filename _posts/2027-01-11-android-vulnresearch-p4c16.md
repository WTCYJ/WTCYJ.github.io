---
layout: post
title: "semantic patch·정적 규칙"
date: 2027-01-11 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Coccinelle, Semgrep, CodeQL, 정적분석]
excerpt: "패치 diff는 취약 패턴의 명세다. 그 명세를 grep이 아니라 제어·데이터 흐름 규칙으로 옮기면 이름과 공백이 바뀐 형제 변종까지 잡힌다 — 대신 매치 하나를 취약점으로 착각하는 순간 오탐 수십 개에 파묻힌다."
---

퍼징은 크래시 하나를 준다. 그런데 그 크래시를 만든 코드 형태 — 예를 들어 고정 크기 스택 버퍼에 길이 검사 없이 `memcpy` 하는 모양 — 는 보통 트리 안에 여러 벌 복제되어 있다. 하나를 고쳐도 형제들은 그대로 남는다. 이때 필요한 건 실행이 아니라 **패턴 검색**이다. 그리고 이미 패치된 공개 CVE의 diff는, 그 취약 패턴이 어떻게 생겼는지를 이미 글로 적어 놓은 명세다.

이 글은 패치 diff에서 취약 패턴을 뽑아 Coccinelle(semantic patch)·Semgrep·CodeQL 같은 정적 규칙으로 옮기고, 그 규칙을 공개 AOSP 소스 트리에 읽기 전용으로 돌려 형제 변종 후보를 찾는 워크플로를 정리·실습한 기록이다. 무기화가 아니라, "같은 실수가 또 어디 있나"를 소스만 보고 세는 작업이다.

> **한 줄 결론**: 패치 diff는 취약 패턴의 명세이고, 규칙은 "패치 전 형태에는 매칭하되 패치 후 가드에는 매칭하지 않게" 쓴다 — 이름·공백·매크로가 달라도 잡으려면 grep이 아니라 제어·데이터 흐름을 보는 도구여야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 범위는 세 가지다. (1) grep → Semgrep → Coccinelle → CodeQL로 이어지는 정적 도구의 표현력 스펙트럼, (2) 패치 커밋 하나를 규칙으로 번역하는 방법, (3) 그 규칙을 AOSP 미디어 파서 같은 공격 표면에 돌려 나온 매치를 후보로 삼아 삼각검증하는 절차. 무기화된 익스플로잇이나 미공개 취약점은 다루지 않는다. 씨앗은 **이미 패치된 공개 CVE**로만 잡는다.

선수 지식이 셋 깔린다. 첫째, 패치 계보를 읽을 줄 알아야 한다 — 3장(Security Bulletin·patch provenance)과 15장(patch-gap·backport 누락)에서 "무엇이 언제 고쳐졌나"를 다뤘고, 이 글은 그 "무엇"의 **모양**을 규칙으로 옮긴다. 둘째, C의 AST와 제어 흐름 개념 — 규칙은 텍스트가 아니라 이 구조 위에서 돈다. 셋째, `git diff` 읽기. diff의 `-` 줄이 취약 형태, `+` 줄이 가드다.

전체 구조에서 이 장은 15장(patch-gap)과 17장(sibling variant hunting) 사이에 있다. 15장이 "이 패치가 여기에 안 들어왔다"를 찾았다면, 이 장은 그 판단을 **자동화 가능한 규칙**으로 굳히고, 17장은 그 규칙이 뱉은 후보들을 실제 변종으로 좁힌다.

## 핵심 개념 — 표현력 스펙트럼

정적 검색 도구는 "무엇을 같은 것으로 보느냐"가 다르다. 이 축 하나가 도구 선택의 전부다.

| 도구 | 매칭 단위 | 변수명·공백 변화에 | 데이터 흐름 | 대표 실행 |
|--|--|--|--|--|
| grep/ripgrep | 텍스트(정규식) | **깨진다** | 못 봄 | `rg 'memcpy\('` |
| Semgrep | AST/구조 패턴 | 견딤 | 얕게(로컬) | `semgrep --config r.yaml` |
| Coccinelle | 제어 흐름(SmPL) | 견딤 | 경로 기반 | `spatch --sp-file r.cocci` |
| CodeQL | 데이터·타인트 흐름 | 견딤 | **깊게(전역)** | `codeql database analyze` |

핵심은 위에서 아래로 갈수록 **오탐은 줄고 비용은 는다**는 점이다. grep은 `memcpy(hdr, p, n)`을 찾다가 매크로로 감싼 `MEMCPY(hdr, p, n)`이나 줄바꿈이 낀 변종을 놓친다. `Inferred` Semgrep 이상은 파서를 통과한 뒤 구조로 비교하므로 그런 표면 차이에 견딘다. `Source-confirmed` 반대로 "이 길이가 공격자에게서 왔나"까지 물으려면 전역 데이터 흐름이 필요하고, 그건 CodeQL 급에서만 답한다. `Reported`(GitHub Security Lab의 variant analysis 개념)

흔한 오개념 하나 — "정적 규칙은 그냥 똑똑한 grep"이라는 생각. 아니다. grep은 문자열을, Semgrep 이상은 **문법 트리**를 본다. 변수명을 바꾸면 grep 규칙은 리팩터 한 번에 무력화되지만 구조 규칙은 살아남는다. 이 차이가 형제 변종 사냥에서 결정적이다.

> **[그림 1]** 동일한 취약 패턴을 grep과 Semgrep으로 각각 돌려, grep은 변수명이 바뀐 변종을 놓치고 Semgrep은 같은 구조로 잡아내는 것을 나란히 보여주는 터미널 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **공개 AOSP 소스에 대한 읽기 전용 정적 스캔**으로만 진행한다. 소스는 `cs.android.com` 또는 로컬 `repo sync` 트리, 도구는 오픈소스(Semgrep·Coccinelle·CodeQL CLI)뿐이다. 실행·후킹·기기 접근은 없다. 씨앗 패턴은 이미 패치가 공개된 CVE, 또는 내가 직접 겪어 그 **모양**을 아는 파서 버그 클래스에서만 가져온다.

씨앗 예로는 내가 직접 겪은 파서 오버플로 클래스를 쓴다 — tinyobjloader의 `parseLine`이 고정 크기 배열 `f[16]`에 인덱스 검사 없이 쓰다 OOB write를 냈던 형태(원저장소가 아카이브되어 이슈 접수는 불가능한 상태라 다운스트림 프로젝트 쪽 제보를 예정하고 있고, 여기서 쓰는 건 그 **패턴 모양**뿐이다). 이 "고정 배열 + 루프 인덱스 + 가드 없음"이라는 **모양**은 언어와 프로젝트를 넘어 반복되므로, 규칙으로 옮겨 AOSP 미디어 파서 표면에 던져 보기 좋은 후보다. `Inferred`

## 실습 절차와 관측

### 가설
- **가설 A** — 패치 diff의 `+` 가드(길이 검사)를 `pattern-not-inside`로 빼면, 규칙은 "아직 가드가 없는" 매치만 남긴다. `Inferred`
- **가설 B** — 같은 규칙이라도 대상 디렉터리를 공격 표면(미디어 파서)으로 좁히면 오탐 대비 실효 매치 비율이 오른다. `Inferred`

### 절차
1. 씨앗 CVE의 fix diff를 읽어 취약 형태(`-`)와 가드(`+`)를 분리한다.
2. Semgrep 규칙에 `pattern`(취약 형태)과 `pattern-not-inside`(가드)를 넣는다.
3. `semgrep --config`로 좁힌 경로에 돌려 file:line과 개수를 기록한다.
4. 각 매치를 열어 길이 인자가 상수인지·상위에서 이미 bound 되는지 수동 확인한다.
5. 살아남은 후보만 17장의 변종 검증으로 넘긴다.

Semgrep 규칙(YAML) — 고정 크기 버퍼로의 `memcpy`에 크기 가드가 안 보이는 형태:

```yaml
rules:
  - id: memcpy-into-fixed-array-no-guard
    languages: [c, cpp]
    severity: WARNING
    message: 고정 크기 버퍼로의 memcpy에 크기 가드가 보이지 않음(후보, 취약 아님)
    patterns:
      - pattern: memcpy($DST, $SRC, $N)
      - pattern-not-inside: |
          if (... <= sizeof($DST)) { ... }
      - pattern-not: memcpy($DST, $SRC, sizeof($DST))
```

같은 클래스를 Coccinelle로 쓰면 제어 흐름 위에서 매칭한다. SmPL 문법 세부는 원문 재확인이 필요하지만, 골자는 "고정 배열을 목적지로 하는 memcpy 줄을 report 모드로 표시"다:

```cocci
// spatch --sp-file rule.cocci --dir frameworks/av/media/ (예시 경로, 재확인)
// 확인 필요: 배열 크기 자리에 `...`는 유효한 SmPL이 아님 → 상수 메타변수(constant)로 크기를 잡는다.
//           아래는 그 형태의 의사코드에 가까운 초안이며 실제 spatch 파싱은 재검증 전제.
@overflow@
type T; identifier dst; expression src, n; constant SIZE;
@@
  T dst[SIZE];
  ...
* memcpy(dst, src, n)
```

CodeQL은 여기서 한 걸음 더 나가, `$N`이 IPC/파일 경계에서 흘러온 값인지를 타인트로 묻는다 — `codeql database create --language=cpp` 로 DB를 만든 뒤 질의를 돌리는 방식이라 비용이 크므로, 후보가 좁혀진 뒤에만 쓴다. `Source-confirmed`

> **[그림 2]** `semgrep --config rule.yaml` 를 AOSP 미디어 파서 경로에 돌려 file:line·룰 메시지·finding 개수 요약이 출력된 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
frameworks/av/media/.../SomeExtractor.cpp
  memcpy-into-fixed-array-no-guard
   411┆ uint8_t hdr[16];
   412┆ memcpy(hdr, ptr, len);

Ran 1 rule on 1873 files: 7 findings
```

7개 매치 중 대부분은 `len`이 상위에서 이미 `min(len, sizeof(hdr))`로 잘렸거나 상수인 오탐일 것이다. 이 표가 규칙 자체의 결론이 아니라 **후보 목록**임을 잊으면 안 된다 — 매치 = 취약점이 아니다.

## Root Cause — 왜 이렇게 되는가

규칙이 오탐을 뱉는 이유는 근본적이다. 패치는 하나의 **구체적 경로**를 막지만, 그 경로에서 뽑아낸 패턴은 원래 버그를 성립시킨 **불변식**보다 항상 넓다. 진짜 버그의 조건은 "길이가 공격자 제어이고, 목적지 버퍼보다 크고, 그 경로가 IPC 경계에서 도달 가능"인데, 구조 규칙은 이 중 마지막 두 조건을 못 본다. 그래서 형태만 같고 안전한 코드까지 딸려 온다. `Inferred`

반대로 grep이 형제 변종을 **놓치는** 이유도 같은 뿌리다. grep은 소스를 문자열로 보므로 매크로 확장·변수명 변경·줄바꿈이 그대로 다른 문자열이 된다. Semgrep 이상은 파서를 거쳐 AST/CFG로 정규화한 뒤 비교하니 그 표면 차이가 사라진다. `Source-confirmed` 즉 표현력 스펙트럼은 "무엇을 같다고 볼지"를 파서·CFG·데이터흐름 어느 층에서 결정하느냐의 문제고, 오탐·미탐은 그 층 선택의 자연스러운 대가다.

## 방어와 회귀 검증

- **발견 규칙 = 회귀 가드.** 취약 형태를 찾으려고 쓴 규칙은, 그대로 CI 프리서브밋에 넣으면 동일 패턴의 재도입을 막는 린트가 된다. Linux 커널이 `scripts/coccinelle/*.cocci`와 `make coccicheck`로 semantic patch를 상시 린트로 돌리는 것이 정확히 이 구조다. `Source-confirmed` 내 wabt 퍼징 때도 결국 회귀 테스트가 PoC 그 자체였던 것과 같은 논리다.
- **정밀도 노브.** `pattern-not-inside` 가드 추가, 메타변수 타입 제약, 스캔 경로를 공격 표면으로 한정 — 이 셋이 오탐을 가장 크게 줄인다. 규칙을 넓게 시작해 노브로 조이는 편이, 좁게 시작해 미탐을 늘리는 것보다 안전하다.
- **한계와 과장 금지.** 정적 매치는 도달성·공격자 제어 여부를 증명하지 못한다. 후보를 실제 취약점으로 확정하려면 데이터 흐름(CodeQL) + 수동 도달성 분석 + (실행이 필요하면) 안전한 하네스 퍼징이 뒤따라야 한다. 매치 개수를 취약점 개수로 보고하는 순간 신뢰를 잃는다.

## 정리

- 패치 diff는 취약 패턴의 명세다 — `-` 줄이 형태, `+` 줄이 가드이고, 규칙은 "형태에 매칭·가드에 비매칭"으로 쓴다.
- 도구는 grep→Semgrep→Coccinelle→CodeQL 순으로 표현력이 넓어지고, 아래로 갈수록 오탐은 줄고 비용은 는다.
- 매치는 취약점이 아니라 후보다. 도달성과 공격자 제어는 별도로 확인해야 한다.
- 발견에 쓴 규칙은 그대로 CI 회귀 가드가 되어, 같은 실수의 재도입을 자동으로 막는다.

**점검 질문** — (1) 같은 취약 패턴을 grep이 놓치고 Semgrep이 잡는 이유를 파서 관점에서 설명하라. (2) 패치 커밋 하나를 규칙으로 옮길 때 `+` 가드 줄은 규칙의 어느 자리에 들어가는가? (3) 정적 매치를 취약점으로 확정하기 전에 반드시 답해야 할 두 조건은?

**참고** — [Coccinelle](https://coccinelle.gitlabpages.inria.fr/website/) · [Linux 커널 coccinelle 문서](https://www.kernel.org/doc/html/latest/dev-tools/coccinelle.html) · [Semgrep 규칙 문법](https://semgrep.dev/docs/writing-rules/rule-syntax) · [CodeQL 문서](https://codeql.github.com/docs/) · [AOSP Code Search](https://cs.android.com)

*다음 글: [sibling variant hunting](/posts/android-vulnresearch-p4c17/).*
