---
layout: post
title: "CodeQL 원리와 실습: 쿼리 하나로 U-Boot NFS 취약점 다시 찾기"
date: 2026-10-06 12:00:00 +0900
category: 블로그/기술
author: WTCY
tags: [CodeQL, 정적 분석, QL, Datalog, taint tracking, U-Boot, variant analysis, CVE-2019-14192]
excerpt: "CodeQL이 코드를 어떻게 데이터베이스로 바꾸고 쿼리를 어떻게 평가하는지 TRAP 파일과 관계 대수 덤프로 직접 확인했다. 그다음 네트워크 길이 값이 memcpy 크기로 흘러가는 경로를 찾는 쿼리를 만들어 U-Boot 2019.07, 패치된 2019.10, 2026년 최신 소스에 차례로 돌려 봤다."
---

[CodeQL](https://codeql.github.com/)은 GitHub이 만든 정적 분석 엔진이다. 소스 코드를 데이터베이스로 만들어 두고, 그 위에 QL이라는 언어로 "이런 모양의 코드가 어디 있나"를 묻는다. 이름은 많이 들었지만 직접 쿼리를 짜 본 적은 없었다. 이번에는 원리부터 하나씩 확인하고, 실제 취약점을 쿼리로 다시 찾아보는 데까지 가 보기로 했다.

실습 대상은 U-Boot 부트로더의 NFS 클라이언트다. 2019년에 GitHub Security Lab이 이 코드에서 [원격 코드 실행 취약점 묶음](https://securitylab.github.com/research/uboot-rce-nfs-vulnerability/)을 찾았다. 첫 번째 취약점은 코드를 직접 읽다가 비슷한 두 곳에서 발견했고, 나머지는 그 패턴을 CodeQL 쿼리로 옮겨 찾았다고 밝혔다. 같은 방식을 따라 하되 쿼리는 직접 짜고, 패치 전후 버전과 최신 소스에 모두 돌려서 결과가 어떻게 바뀌는지 보기로 했다.

실습 환경은 WSL2 Ubuntu 24.04, gcc 13.3, CodeQL CLI 2.25.6 번들(cpp-queries 1.6.4, cpp-all 10.2.0)이다. 쿼리와 스크립트는 글 끝에 파일로 올려 두었다.

## 1. CodeQL이 하는 일

CodeQL은 분석을 두 단계로 나눈다. 먼저 소스를 관계형 데이터베이스로 뽑아 두고, 그다음 그 데이터베이스에 쿼리를 던진다. 데이터베이스를 한 번 만들어 두면 쿼리는 몇 번이든 다시 돌릴 수 있다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 760 290" role="img" aria-label="CodeQL 동작 흐름. 위쪽 줄은 데이터베이스 생성이다. 빌드 명령을 실행하면 CodeQL이 컴파일러 호출을 가로채고, 추출기가 AST와 타입, 이름 결합 정보를 TRAP 파일로 쓰고, 이것을 가져와 테이블과 dbscheme, src.zip 으로 된 데이터베이스를 만든다. 아래쪽 줄은 쿼리 실행이다. QL 쿼리를 Datalog 와 관계 대수로 컴파일하고, 데이터베이스 위에서 바닥부터 고정점까지 평가해 BQRS 결과를 만들고, 이를 SARIF 나 CSV 로 해석한다">
  <style>
    .cq-box { fill: var(--surface); stroke: var(--rule-dark); stroke-width: 1.4; }
    .cq-hot { fill: var(--surface); stroke: var(--blue); stroke-width: 2; }
    .cq-t { fill: var(--ink); font-family: var(--mono); font-size: 13px; text-anchor: middle; }
    .cq-s { fill: var(--ink-soft); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .cq-a { stroke: var(--ink-soft); stroke-width: 1.6; fill: none; }
    .cq-l { fill: var(--ink-faint); font-family: var(--sans); font-size: 12px; }
    .cq-head { fill: var(--ink-soft); }
  </style>
  <defs>
    <marker id="cq-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="cq-head" d="M0,0 L10,5 L0,10 z"/></marker>
  </defs>
  <text class="cq-l" x="16" y="26">데이터베이스 만들기 (codeql database create)</text>
  <rect class="cq-box" x="16" y="40" width="128" height="74" rx="6"/>
  <text class="cq-t" x="80" y="68">빌드 명령</text>
  <text class="cq-s" x="80" y="90">make, gcc ...</text>
  <rect class="cq-box" x="164" y="40" width="128" height="74" rx="6"/>
  <text class="cq-t" x="228" y="68">호출 추적</text>
  <text class="cq-s" x="228" y="90">컴파일러 실행마다</text>
  <rect class="cq-box" x="312" y="40" width="128" height="74" rx="6"/>
  <text class="cq-t" x="376" y="68">추출기</text>
  <text class="cq-s" x="376" y="90">AST, 타입, 이름 결합</text>
  <rect class="cq-box" x="460" y="40" width="128" height="74" rx="6"/>
  <text class="cq-t" x="524" y="68">TRAP</text>
  <text class="cq-s" x="524" y="90">튜플을 적은 텍스트</text>
  <rect class="cq-hot" x="608" y="40" width="136" height="74" rx="6"/>
  <text class="cq-t" x="676" y="66">데이터베이스</text>
  <text class="cq-s" x="676" y="86">테이블 + dbscheme</text>
  <text class="cq-s" x="676" y="104">src.zip</text>
  <line class="cq-a" x1="144" y1="77" x2="161" y2="77" marker-end="url(#cq-ar)"/>
  <line class="cq-a" x1="292" y1="77" x2="309" y2="77" marker-end="url(#cq-ar)"/>
  <line class="cq-a" x1="440" y1="77" x2="457" y2="77" marker-end="url(#cq-ar)"/>
  <line class="cq-a" x1="588" y1="77" x2="605" y2="77" marker-end="url(#cq-ar)"/>
  <text class="cq-l" x="16" y="176">쿼리 실행 (codeql query run, database analyze)</text>
  <rect class="cq-box" x="16" y="190" width="128" height="74" rx="6"/>
  <text class="cq-t" x="80" y="218">QL 쿼리</text>
  <text class="cq-s" x="80" y="240">.ql, .qll</text>
  <rect class="cq-box" x="164" y="190" width="128" height="74" rx="6"/>
  <text class="cq-t" x="228" y="218">컴파일</text>
  <text class="cq-s" x="228" y="240">Datalog → 관계 대수</text>
  <rect class="cq-hot" x="312" y="190" width="128" height="74" rx="6"/>
  <text class="cq-t" x="376" y="218">평가</text>
  <text class="cq-s" x="376" y="240">바닥부터, 고정점까지</text>
  <rect class="cq-box" x="460" y="190" width="128" height="74" rx="6"/>
  <text class="cq-t" x="524" y="218">BQRS</text>
  <text class="cq-s" x="524" y="240">결과 튜플</text>
  <rect class="cq-box" x="608" y="190" width="136" height="74" rx="6"/>
  <text class="cq-t" x="676" y="218">SARIF, CSV</text>
  <text class="cq-s" x="676" y="240">메타데이터로 해석</text>
  <line class="cq-a" x1="144" y1="227" x2="161" y2="227" marker-end="url(#cq-ar)"/>
  <line class="cq-a" x1="292" y1="227" x2="309" y2="227" marker-end="url(#cq-ar)"/>
  <line class="cq-a" x1="440" y1="227" x2="457" y2="227" marker-end="url(#cq-ar)"/>
  <line class="cq-a" x1="588" y1="227" x2="605" y2="227" marker-end="url(#cq-ar)"/>
  <path class="cq-a" d="M676,114 L676,150 L376,150 L376,187" marker-end="url(#cq-ar)"/>
</svg>
</figure>

[공식 문서](https://codeql.github.com/docs/codeql-overview/about-codeql/)에 따르면 C/C++이나 Java처럼 컴파일하는 언어는 빌드를 지켜보다가 컴파일러가 실행될 때마다 그 입력을 추출하고, Python이나 JavaScript처럼 인터프리트하는 언어는 소스를 바로 읽는다. 아래에서는 C 쪽만 다룬다.

### 1.1 데이터베이스는 빌드에서 나온다

C로 된 작은 예제부터 데이터베이스를 만들어 봤다. 길이 필드가 붙은 패킷을 받아 처리하는 프로그램이고, 일부러 취약하게 짰다. 코드는 3장에서 자세히 본다. `--command` 로 빌드 명령을 넘기면 CodeQL이 그 명령을 실행하면서 안에서 호출되는 gcc를 가로챈다.

![codeql database create 실행 화면. build.sh 의 내용은 gcc -O2 -Wall -o pktd pktd.c 한 줄이다. 출력은 Initializing database, Running build command, Finalizing database, Running TRAP import, Importing TRAP files, Merging relations 순으로 진행되고 relations 266.41 KiB, string pool 2.22 MiB 로 데이터베이스를 쓴 뒤 Successfully created database 로 끝난다. 생성된 디렉터리에는 codeql-database.yml, db-cpp, src.zip 등이 있고 db-cpp 안에는 semmlecode.cpp.dbscheme 가 있다](/assets/img/codeql-study/01-create.png)

출력 순서를 보면 구조가 그대로 드러난다. 빌드 명령을 돌리고, TRAP 파일을 모아서 가져오고(import), 관계를 합친 뒤(merge) 소스를 `src.zip` 으로 묶는다. 이 순서 때문에 생기는 중요한 결과가 하나 있다. 빌드에서 컴파일되지 않은 파일은 데이터베이스에도 없다. 뒤에서 U-Boot를 분석할 때 CodeQL은 "C/C++ 파일 8378개 중 1209개를 스캔했다"고 알려 주는데, 나머지는 sandbox 설정으로 빌드할 때 컴파일되지 않은 파일이다. 다른 보드 설정으로 빌드하면 데이터베이스가 달라진다.

### 1.2 TRAP 파일과 dbscheme

`database create` 는 중간 산출물을 지워 버리기 때문에, 이번에는 단계를 쪼개서 돌렸다. `codeql database init` 으로 빈 데이터베이스를 만들고 `codeql database trace-command` 로 gcc를 한 번 실행한 뒤, 마무리(`finalize`)를 하기 전에 `trap/` 디렉터리를 열어 봤다. TRAP은 zstd로 압축한 tar 안에 소스 파일과 헤더마다 하나씩 들어 있었다.

![handle_echo 함수의 소스 네 줄과, 그 함수에 해당하는 TRAP 튜플. functions(#153, "handle_echo", 1), params 두 줄, 각 위치를 적은 locations_default 줄들, localvariables(#1ff, #11d, "len"), exprs(#201, 97, #loc_201), funbind(#201, #202) 가 보인다. #loc_201 은 14번 줄 20열부터 24열, 즉 ntohl 이 적힌 자리다](/assets/img/codeql-study/02-trap.png)

TRAP은 튜플을 한 줄에 하나씩 적은 텍스트다. `functions(#153, "handle_echo", 1)` 은 "153번 개체는 이름이 handle_echo인 함수"라는 뜻이다. 14번 줄의 `ntohl(...)` 호출은 `exprs(#201, 97, #loc_201)` 로 기록되고, `funbind(#201, #202)` 가 이 호출식을 함수 개체 `#202` 에 묶는다. 같은 TRAP 앞쪽에서 `#202` 는 `fun_decl_ntohl` 로 정의되어 있다. 소스의 함수 호출 하나가 "식 테이블의 한 행"과 "호출식과 함수를 잇는 테이블의 한 행"으로 쪼개지는 셈이다.

각 테이블의 모양은 `semmlecode.cpp.dbscheme` 에 정의돼 있다.

![semmlecode.cpp.dbscheme 에서 functions, funbind, exprs 세 관계의 정의를 grep 한 화면. functions 는 unique int id, string name, int kind 세 열이고, funbind 는 int expr 과 int fun 두 열, exprs 는 unique int id, int kind, int location 세 열이다](/assets/img/codeql-study/03-dbscheme.png)

데이터베이스를 SQL 테이블처럼 생각하면 된다. 다만 사람이 이 테이블을 직접 조인하지는 않는다. `cpp-all` 라이브러리가 이 테이블들 위에 `Function`, `FunctionCall`, `Expr` 같은 클래스를 만들어 두었고, 쿼리는 그 클래스로 쓴다.

### 1.3 QL은 객체 지향 문법을 입힌 Datalog다

QL을 처음 보면 SQL처럼 `from`, `where`, `select` 가 있어서 비슷해 보인다. 실제로는 논리 프로그래밍 언어인 Datalog에 가깝고, Semmle 연구진이 [ECOOP 2016 논문](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2016.2)에서 설계를 설명했다. 핵심은 클래스가 곧 술어(predicate)라는 점이다. 아래는 이번 실습에서 만든 클래스다.

```ql
/** 네트워크 바이트 순서를 뒤집는 식. 빌드 옵션에 따라 함수일 수도 매크로일 수도 있다. */
class NetworkByteSwap extends Expr {
  NetworkByteSwap() {
    this.(FunctionCall).getTarget().getName().regexpMatch("ntoh(s|l|ll)")
    or
    exists(MacroInvocation mi |
      mi.getMacroName().regexpMatch("ntoh(s|l|ll)") and this = mi.getExpr()
    )
  }
}
```

생성자처럼 생긴 `NetworkByteSwap()` 은 객체를 만드는 코드가 아니다. 이 클래스에 속하는 값의 조건을 적은 특성 술어(characteristic predicate)이고, 클래스 자체는 "조건을 만족하는 `Expr` 들의 집합"이다. `or` 과 `exists` 로 조건을 엮고, 조건을 만족하는 모든 값이 결과가 된다. 반복문을 돌며 하나씩 검사하는 코드가 아니라 집합을 정의하는 식이라고 보면 된다.

### 1.4 쿼리는 관계 대수로 컴파일된다

이 집합이 실제로 어떻게 계산되는지 보려고 가장 단순한 쿼리를 컴파일해 봤다. `codeql query compile --dump-ra` 는 컴파일된 관계 대수(RA)를 출력한다.

![01-memcpy-calls.ql 의 from, where, select 세 줄과 그 RA 덤프 일부. where call.getTarget().getName() = "memcpy" 가 RA 에서 r1 = CONSTANT(unique string)["memcpy"] 로 상수 관계를 만든 뒤 JOIN WITH #functionsMerge_10#join_rhs 로 함수 테이블과 조인하고, 다시 FunctionCall.getTarget 관계와 조인한 다음 생성자 호출을 AND NOT 으로 빼는 단계로 바뀌어 있다](/assets/img/codeql-study/09-ra.png)

`getName() = "memcpy"` 라는 조건이 "memcpy 한 행짜리 상수 관계를 만들고, 그것을 함수 이름 테이블과 조인하라"로 바뀌었다. 모든 함수 호출을 돌면서 이름을 비교하는 게 아니라, 이름이 memcpy인 함수를 먼저 찾고 그 함수를 호출하는 식을 조인으로 붙인다. 조건 순서는 최적화기가 정한다.

[평가 방식 문서](https://codeql.github.com/docs/ql-language-reference/evaluation-of-ql-programs/)를 보면 술어는 의존 관계에 따라 층으로 나뉘고, 아래층부터 차례로 계산된다. 재귀 술어는 새 튜플이 더 이상 나오지 않을 때까지, 즉 최소 고정점에 닿을 때까지 반복한다. 같은 RA 덤프 안에 `EVALUATE RECURSIVE LAYER` 블록이 있었는데, 거기에는 `BASE CASE` 와 `SEMINAIVE VARIANT` 가 따로 적혀 있었다. 매 반복마다 전체를 다시 조인하지 않고 직전 반복에서 새로 생긴 튜플(`#prev_delta`)만 조인하는 준순진(semi-naive) 평가다. 결과는 항상 유한한 집합이어야 해서, 변수 하나가 무한히 많은 값을 가질 수 있으면 컴파일 단계에서 오류가 난다.

### 1.5 데이터 흐름과 오염 추적

보안 쿼리에서 제일 많이 쓰는 기능은 데이터 흐름이다. "이 값이 저기까지 흘러가는가"를 묻는다. CodeQL은 함수 안에서만 보는 지역 흐름과, 함수 호출을 넘나드는 전역 흐름을 구분한다. 오염 추적(taint tracking)은 여기에 "값이 그대로 전달되지는 않아도 영향을 준다"는 단계를 더한 것이다. `len - 4` 는 `len` 과 다른 값이지만 `len` 에 오염돼 있다고 본다.

[C/C++ 데이터 흐름 문서](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-cpp/)에 나온 대로, 전역 흐름은 설정 모듈을 하나 만들어 쓴다. 출발점(`isSource`), 도착점(`isSink`), 흐름을 끊는 지점(`isBarrier`)을 술어로 적어 `TaintTracking::Global<...>` 에 넘기면, 라이브러리가 출발점에서 도착점까지 가는 경로를 계산한다. 경로 계산도 결국 재귀 술어라서 위에서 본 고정점 반복으로 돌아간다.

실제로 얼마나 반복하는지 궁금해서, 뒤에서 만들 U-Boot 쿼리를 캐시를 비운 상태로 `--evaluator-log` 를 켜고 돌린 뒤 `codeql generate log-summary` 로 요약했다.

![평가 로그에서 데이터 흐름 재귀 술어만 뽑은 표. Stage1 의 fwdFlow 는 튜플 257,614 개를 920 번 반복해 2198ms, revFlow 는 109,540 개를 364 번 반복해 791ms 걸렸다. Stage2 fwdFlow1 은 916 개로 줄고, Stage3 부터 Stage6 까지는 100 개 남짓에서 26 에서 34 번 반복한다](/assets/img/codeql-study/10-eval.png)

흐름 계산이 여러 단계(Stage)로 나뉘어 있다는 게 눈에 띈다. Stage1은 호출 문맥이나 구조체 필드 같은 세부를 무시하고 "출발점에서 앞으로 닿을 수 있는 노드"와 "도착점에서 거꾸로 닿을 수 있는 노드"를 거칠게 구한다. U-Boot 전체에서 앞쪽으로 25만 개가 넘는 튜플이 나왔고, 920번 반복해서야 고정점에 닿았다. 뒤 단계들은 앞 단계에서 살아남은 노드만 가지고 필드 접근 경로와 호출 문맥을 점점 정밀하게 따진다. 그래서 Stage2에서 916개, Stage3부터는 100개 남짓으로 줄어든다. 넓게 거른 다음 좁은 범위만 정밀하게 보는 구조라서 큰 코드베이스에서도 경로 계산이 감당할 만한 시간 안에 끝난다.

## 2. 실습 준비: 쿼리 팩

쿼리는 `qlpack.yml` 이 있는 디렉터리, 즉 쿼리 팩 안에 둔다. 의존성으로 C/C++ 표준 라이브러리 하나만 적었다.

```yaml
name: wtcy/codeql-study
version: 0.0.1
dependencies:
  codeql/cpp-all: "*"
```

번들 배포판에는 표준 라이브러리와 표준 쿼리가 이미 들어 있어서 `codeql pack install` 이 따로 내려받는 것은 없었다. 쿼리를 돌리는 방법은 두 가지를 썼다. 결과를 표로 바로 보고 싶을 때는 `codeql query run` 으로 BQRS를 만들어 `codeql bqrs decode` 로 풀었다. 위치 정보까지 필요할 때는 `codeql database analyze` 로 SARIF를 뽑고, 짧은 파이썬 스크립트로 "도착점 위치 ← 출발점 위치"를 한 줄씩 찍었다. 이후 화면의 결과는 모두 이 스크립트 출력이다.

처음에 `codeql resolve qlpacks` 가 2분이 넘도록 끝나지 않았다. CodeQL 배포판을 홈 디렉터리 바로 아래(`~/codeql`)에 풀어 뒀더니, 팩을 찾느라 홈 디렉터리 전체를 뒤지고 있었다. CLI도 홈 디렉터리 설치는 성능 문제가 생길 수 있다고 경고한다. `~/tools/codeql` 로 옮기자 바로 끝났다.

## 3. 실습 1: 작은 예제로 쿼리 키우기

### 3.1 예제 프로그램

처음부터 U-Boot에 쿼리를 돌리면 결과가 맞는지 판단하기 어렵다. 그래서 정답을 아는 작은 프로그램을 먼저 만들었다. 패킷 첫 바이트로 처리기를 고르고, 처리기마다 길이 필드를 읽어 `memcpy` 한다.

```c
static char buf[256];

/* 길이 필드를 그대로 믿는다: 원격 길이 -> memcpy 크기 */
void handle_echo(const unsigned char *pkt, size_t n)
{
    uint32_t len = ntohl(*(const uint32_t *)pkt);
    memcpy(buf, pkt + 4, len);
    write(1, buf, len);
}

/* 길이를 검사한 뒤 복사한다: 걸리면 안 되는 경우 */
void handle_name(const unsigned char *pkt, size_t n)
{
    uint16_t len = ntohs(*(const uint16_t *)pkt);
    if (len > sizeof(buf))
        return;
    memcpy(buf, pkt + 2, len);
}

/* 함수를 하나 건너서 흐른다: 함수 경계를 넘는 추적이 필요하다 */
static void copy_payload(const unsigned char *src, unsigned size)
{
    memcpy(buf, src, size);
}

void handle_data(const unsigned char *pkt, size_t n)
{
    unsigned size = ntohs(*(const uint16_t *)(pkt + 2)) - 4;
    copy_payload(pkt + 4, size);
}
```

`handle_echo` 와 `handle_data` 는 취약하고 `handle_name` 은 안전하다. `handle_data` 는 길이가 4보다 작으면 뺄셈에서 언더플로가 나고, 값이 다른 함수로 넘어간 뒤에야 `memcpy` 에 닿는다.

### 3.2 ntohl은 함수인가

첫 쿼리는 `memcpy` 호출을 전부 찾는 문법 수준의 쿼리였다. 세 곳이 그대로 나왔다. 두 번째로 출발점이 될 `ntohl` 을 찾으려는데, 처음 오염 추적 결과를 보니 출발점이 `call to __bswap_32` 로 찍혀 있었다. 소스에는 그런 함수를 쓴 적이 없다. 그래서 함수 호출과 매크로 전개를 따로 세는 쿼리를 만들고, 같은 소스를 `-O0` 로 빌드한 데이터베이스를 하나 더 만들어 비교했다.

![02-ntoh.ql 쿼리와 두 데이터베이스에서의 결과. gcc -O0 로 빌드한 DB 에서는 call to ntohs 두 개와 call to ntohl 하나가 모두 함수 호출로 나오고, gcc -O2 로 빌드한 DB 에서는 ntohs(x) 두 개와 ntohl(x) 하나가 모두 매크로 전개로 나온다](/assets/img/codeql-study/04-ntoh.png)

같은 소스인데 최적화 옵션에 따라 `ntohl` 이 함수 호출이 되기도 하고 매크로가 되기도 한다. glibc의 `netinet/in.h` 는 `__OPTIMIZE__` 가 정의돼 있으면 `ntohl(x)` 를 `__bswap_32(x)` 로 바꾸는 매크로를 쓴다. `-O2` 로 컴파일하면 컴파일러가 이 매크로를 정의하므로 `ntohl` 이라는 함수 호출은 사라지고 `__bswap_32` 호출만 남는다. CodeQL은 컴파일러가 실제로 본 코드를 추출하기 때문에 이 차이가 데이터베이스에 그대로 남는다. 앞에서 본 `NetworkByteSwap` 클래스가 함수 호출과 매크로 전개를 둘 다 받는 이유가 이것이다. U-Boot도 `ntohs` 를 자체 매크로로 정의해서 이 처리가 꼭 필요했다.

### 3.3 첫 오염 추적 쿼리

출발점은 `NetworkByteSwap` 식, 도착점은 `memcpy` 의 세 번째 인자로 정했다.

```ql
/**
 * @name 네트워크 값이 memcpy 크기로 흐른다
 * @kind path-problem
 * @id wtcy/ntoh-to-memcpy
 * @problem.severity warning
 */
import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import NetworkByteSwap

module NtohConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { n.asExpr() instanceof NetworkByteSwap }

  predicate isSink(DataFlow::Node n) {
    exists(FunctionCall c | c.getTarget().getName() = "memcpy" and n.asExpr() = c.getArgument(2))
  }
}

module NtohFlow = TaintTracking::Global<NtohConfig>;
import NtohFlow::PathGraph

from NtohFlow::PathNode src, NtohFlow::PathNode sink
where NtohFlow::flowPath(src, sink)
select sink.getNode(), src, sink, "$@ 에서 온 값이 검사 없이 memcpy 크기가 된다", src.getNode(),
  "네트워크 값"
```

`@kind path-problem` 을 적으면 결과에 출발점부터 도착점까지의 경로가 함께 담긴다. VS Code 확장에서 결과를 클릭하면 이 경로를 한 단계씩 따라갈 수 있고, SARIF에는 `codeFlows` 로 들어간다.

결과는 세 건이었다. `copy_payload` 안의 `memcpy` 를 `handle_data` 의 `ntohs` 와 이어 준 것을 보면 함수 경계를 넘는 추적은 제대로 됐다. 문제는 `handle_name` 도 나왔다는 것이다. 이 쿼리는 길이 검사가 있는지 전혀 보지 않으니 당연한 결과다.

### 3.4 검사를 흐름의 차단점으로 만들기

`isBarrier` 에 "상한 검사를 통과한 값"을 적어야 했다. 처음 쓴 버전(04번 쿼리)은 단순했다. 변수 `v` 가 비교문의 한쪽에 직접 놓여 있고, 그 비교가 "v가 더 작다"는 쪽으로 판정된 블록 안에서 `v` 를 읽으면 차단한다. 비교문이 어느 블록을 지키는지는 `semmle.code.cpp.controlflow.Guards` 의 `GuardCondition.controls` 로 알 수 있다. 예제에서는 이 정도로 충분해서 `handle_name` 이 빠졌다.

그런데 이 버전을 U-Boot의 패치된 코드에 돌려 보니 부족한 점이 둘 드러났다. 자세한 경위는 5장에서 다루고, 결론만 먼저 적으면 최종 버전(05번 쿼리)의 차단 조건은 이렇게 됐다.

```ql
/**
 * e 와 같은 모양의 식이, e 를 지키는 비교문의 '작은 쪽'에 들어 있다.
 * `a > b` 가 거짓인 쪽이면 a 가, `a < b` 가 참인 쪽이면 a 가 상한을 받은 것으로 본다.
 * 음수가 될 수 있는 값은 상한 검사를 그냥 통과하므로 인정하지 않는다. 타입이 아니라 범위 분석으로 본다.
 */
predicate boundedAbove(Expr e) {
  lowerBound(e) >= 0 and
  exists(GuardCondition g, RelationalOperation cmp, boolean branch, Expr side, Expr sub |
    g = cmp and
    g.controls(e.getBasicBlock(), branch) and
    (if branch = true then side = cmp.getLesserOperand() else side = cmp.getGreaterOperand()) and
    sub = side.getAChild*() and
    hashCons(sub) = hashCons(e)
  )
}
```

하나는 변수가 비교식에 그대로 놓이지 않고 `offset + rlen > len` 처럼 식 안에 들어간 경우다. 그래서 비교문의 작은 쪽 하위 식(`getAChild*`) 가운데 지금 보는 식과 모양이 같은 것(`hashCons`)이 있으면 인정하도록 바꿨다. 다른 하나는 부호다. 음수는 상한 검사를 그대로 통과한 뒤 `memcpy` 에서 거대한 크기로 바뀐다. 그래서 범위 분석 라이브러리(`SimpleRangeAnalysis`)의 `lowerBound` 로 값이 음수가 될 수 없는 경우에만 검사를 인정했다.

![pktd 데이터베이스에 03번 쿼리와 05번 쿼리를 돌린 결과와 ASan 재현. 03번은 handle_echo, handle_name, copy_payload 세 건, 05번은 handle_echo 와 copy_payload 두 건이다. poc.sh 는 E 처리기에 길이 0x1000 을 보내면 AddressSanitizer stack-buffer-overflow in memcpy, N 처리기에 같은 길이를 보내면 정상 종료, D 처리기에 길이 2 를 보내 2-4 언더플로를 일으키면 다시 stack-buffer-overflow 가 난다](/assets/img/codeql-study/05-pktd.png)

결과가 맞는지는 실행으로 확인했다. ASan을 붙여 빌드하고 처리기마다 길이 필드만 큰 패킷을 보냈다. 쿼리가 남긴 두 곳은 실제로 `memcpy` 에서 터졌고, 쿼리가 뺀 `handle_name` 은 정상 종료했다. ASan이 stack-buffer-overflow로 보고한 것은 복사 원본인 `main` 의 2048바이트 스택 배열을 넘어 읽은 쪽이 먼저 걸렸기 때문이다. 처음 `-O1 -fsanitize=address` 로 빌드했을 때는 ASan 보고 대신 `*** buffer overflow detected ***` 가 먼저 떴다. Ubuntu의 gcc가 최적화 빌드에서 기본으로 켜는 `_FORTIFY_SOURCE` 가 `memcpy` 를 크기 검사 버전으로 바꿔 놓았기 때문이다. `-U_FORTIFY_SOURCE` 로 끄고 다시 빌드했다.

## 4. 실습 2: U-Boot 2019.07

### 4.1 데이터베이스 만들기

U-Boot는 x86 리눅스에서 실행 파일로 돌릴 수 있는 sandbox 보드 설정이 있어서 교차 컴파일러 없이 빌드할 수 있다. 취약점이 고쳐지기 직전 릴리스인 v2019.07을 받아 빌드 명령을 그대로 CodeQL에 넘겼다.

```bash
make sandbox_defconfig
codeql database create ~/codeql-study/db-uboot --language=c-cpp --threads=0 \
    --command="make -j10 NO_SDL=1 HOSTCFLAGS=-fcommon"
```

`NO_SDL=1` 은 SDL 개발 패키지 없이 빌드하려고 넣었다. `-fcommon` 은 gcc 10부터 기본값이 바뀌어서 필요했다. 2019년 코드에는 헤더에서 전역 변수를 정의하는 곳이 있어서, 최신 gcc로는 링크 단계에서 `multiple definition` 오류가 난다. 2019.07은 호스트 도구 쪽에서만 문제가 생겨 `HOSTCFLAGS` 로 충분했지만, 2019.10은 본체 쪽 헤더(`include/cbfs.h`)에서도 같은 오류가 나서 `KCFLAGS=-fcommon` 까지 넘겨야 했다. 빌드와 추출은 합쳐서 43초쯤 걸렸고 데이터베이스는 116MB가 됐다.

### 4.2 결과와 CVE 대조

05번 쿼리를 돌린 결과다.

![U-Boot 2019.07 데이터베이스에 05번 쿼리를 돌린 결과 18건. 왼쪽은 memcpy 크기 인자가 있는 위치와 함수, 오른쪽은 출발점인 ntoh 식의 위치와 함수다. netconsole.c 의 nc_input_packet 두 건, efi_net.c 의 efi_net_set_dhcp_ack, net.c 의 __net_defragment, nfs.c 의 store_block, rpc_req 두 건, nfs_readlink_req, nfs_read_req, rpc_lookup_reply, nfs_mount_reply, nfs_umountall_reply, nfs_lookup_reply 두 건, nfs_readlink_reply 세 건, ping.c 의 ping_receive 가 있다](/assets/img/codeql-study/06-uboot1907.png)

각 결과를 [NVD](https://nvd.nist.gov/vuln/detail/CVE-2019-14192)의 CVE 설명과 하나씩 맞춰 봤다. 함수 이름과 "if 블록 / else 블록" 같은 설명까지 NVD 문구를 기준으로 삼았다. 처음에 GitHub Security Lab 글을 웹 요약 도구로 읽었을 때는 CVE 번호와 함수가 엉뚱하게 짝지어져 나와서, NVD 원문으로 다시 확인했다.

| 도착점 (memcpy) | 출발점 | 대응 |
|---|---|---|
| `netconsole.c:161`, `:164` nc_input_packet | `net.c:1306` UDP 길이 | CVE-2019-14192 |
| `nfs.c:644` nfs_readlink_reply (if 블록) | `nfs.c:635` 경로 길이 | CVE-2019-14193 |
| `nfs.c:106` store_block | `nfs.c:688` nfs_read_reply 읽은 길이 | CVE-2019-14194 (NFSv2), CVE-2019-14198 (NFSv3) |
| `nfs.c:649` nfs_readlink_reply (else 블록) | `nfs.c:635` 경로 길이 | CVE-2019-14195 |
| `nfs.c:574` nfs_lookup_reply | `nfs.c:571` 파일 핸들 길이 | CVE-2019-14196 |
| `efi_net.c:536` efi_net_set_dhcp_ack | `net.c:1315` UDP 길이 | CVE-2019-14199 경로 |
| `nfs.c:435` rpc_lookup_reply | `net.c:1315` UDP 길이 | CVE-2019-14200 |
| `nfs.c:517` nfs_lookup_reply | `net.c:1315` UDP 길이 | CVE-2019-14201 |
| `nfs.c:616` nfs_readlink_reply | `net.c:1315` UDP 길이 | CVE-2019-14202 |
| `nfs.c:467` nfs_mount_reply | `net.c:1315` UDP 길이 | CVE-2019-14203 |
| `nfs.c:493` nfs_umountall_reply | `net.c:1315` UDP 길이 | CVE-2019-14204 |
| `nfs.c:202`, `:207`, `:304`, `:376` | `nfs.c:571` 파일 핸들 길이 | CVE-2019-14196과 같은 값이 다음 요청에 다시 쓰임 |
| `net.c:1009` __net_defragment | `net.c:913` IP 전체 길이 | CVE-2022-30552 (2022년 발견) |
| `ping.c:108` ping_receive | `net.c:913` IP 전체 길이 | 위 재조립 길이의 하류 |

2019년 CVE 13개 가운데 CVE-2019-14197을 뺀 12개가 이 결과 안에 있었다. 14197은 `nfs_read_reply` 의 범위 밖 읽기인데, `memcpy` 크기가 아니라 패킷 안의 오프셋을 잘못 쓰는 문제라서 이 쿼리의 도착점 정의로는 잡히지 않는다. 쿼리는 내가 정의한 모양의 버그만 찾는다.

UDP 길이에서 시작하는 결과가 많은 이유는 흐름을 그려 보면 보인다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 760 250" role="img" aria-label="U-Boot UDP 길이의 흐름. net_process_received_packet 이 len 을 ntohs(udp_len) 빼기 8 로 계산해 udp_packet_handler 함수 포인터로 넘긴다. udp_len 이 8 보다 작으면 언더플로가 난다. NFS 처리기 nfs_handler 는 이 len 을 다섯 개의 응답 처리 함수로 넘기고, 각 함수는 memcpy(&rpc_pkt.u.data[0], pkt, len) 으로 스택 버퍼에 복사한다. 2019.10 패치는 net_process_received_packet 에 udp_len 이 8 이상이고 ip_len 이하인지 보는 검사를, nfs_handler 에 len 이 sizeof(struct rpc_t) 이하인지 보는 검사를 넣었다">
  <style>
    .ub-box { fill: var(--surface); stroke: var(--rule-dark); stroke-width: 1.4; }
    .ub-hot { fill: var(--surface); stroke: var(--red); stroke-width: 2; }
    .ub-t { fill: var(--ink); font-family: var(--mono); font-size: 13px; text-anchor: middle; }
    .ub-s { fill: var(--ink-soft); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .ub-m { fill: var(--ink-soft); font-family: var(--mono); font-size: 11.5px; text-anchor: middle; }
    .ub-a { stroke: var(--ink-soft); stroke-width: 1.6; fill: none; }
    .ub-fix { stroke: var(--forest); stroke-width: 2; fill: none; stroke-dasharray: 5 4; }
    .ub-fl { fill: var(--forest); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .ub-head { fill: var(--ink-soft); }
  </style>
  <defs>
    <marker id="ub-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="ub-head" d="M0,0 L10,5 L0,10 z"/></marker>
  </defs>
  <rect class="ub-box" x="16" y="60" width="226" height="86" rx="6"/>
  <text class="ub-t" x="129" y="86">net_process_received_packet</text>
  <text class="ub-m" x="129" y="110">len = ntohs(udp_len) - 8</text>
  <text class="ub-s" x="129" y="132">udp_len 이 8 보다 작으면 언더플로</text>
  <rect class="ub-box" x="282" y="60" width="176" height="86" rx="6"/>
  <text class="ub-t" x="370" y="86">nfs_handler</text>
  <text class="ub-m" x="370" y="110">(*udp_packet_handler)</text>
  <text class="ub-s" x="370" y="132">상태에 따라 응답 함수 호출</text>
  <rect class="ub-hot" x="498" y="40" width="246" height="126" rx="6"/>
  <text class="ub-t" x="621" y="64">응답 처리 함수 다섯 개</text>
  <text class="ub-s" x="621" y="86">rpc_lookup_reply, nfs_mount_reply</text>
  <text class="ub-s" x="621" y="104">nfs_umountall_reply, nfs_lookup_reply</text>
  <text class="ub-s" x="621" y="122">nfs_readlink_reply</text>
  <text class="ub-m" x="621" y="148">memcpy(&amp;rpc_pkt..., pkt, len)</text>
  <line class="ub-a" x1="242" y1="103" x2="279" y2="103" marker-end="url(#ub-ar)"/>
  <line class="ub-a" x1="458" y1="103" x2="495" y2="103" marker-end="url(#ub-ar)"/>
  <line class="ub-fix" x1="129" y1="146" x2="129" y2="190"/>
  <text class="ub-fl" x="129" y="208">fe7288069d: 8 ≤ udp_len ≤ ip_len</text>
  <line class="ub-fix" x1="370" y1="146" x2="370" y2="190"/>
  <text class="ub-fl" x="390" y="232">741a8a08eb: len ≤ sizeof(struct rpc_t)</text>
</svg>
</figure>

UDP 헤더의 길이 필드에서 8을 빼서 함수 포인터로 넘기는데, 길이 필드가 8보다 작으면 큰 양수가 된다(CVE-2019-14199). NFS 처리기는 이 값을 응답 처리 함수 다섯 개에 넘기고, 각 함수가 그 길이만큼 스택 버퍼로 복사한다(CVE-2019-14200부터 14204). 하나의 출발점이 여러 CVE로 갈라지는 구조라서 쿼리 결과도 같은 출발점이 여러 번 찍혔다.

### 4.3 표준 쿼리는 이걸 잡았을까

직접 짠 쿼리와 비교하려고 CodeQL이 기본으로 제공하는 C/C++ 보안 쿼리 묶음(`cpp-security-extended`)도 같은 데이터베이스에 돌렸다.

![cpp-security-extended 묶음을 U-Boot 2019.07 에 돌린 결과 요약. CodeQL scanned 1209 out of 8378 C/C++ files. 전체 216건이고 상위 규칙은 suspicious-pointer-scaling-void 45, unbounded-write 38, integer-multiplication-cast-to-long 23, invalid-pointer-deref 22 등이다. net/ 과 drivers/net/ 에서 나온 결과는 tftp.c 의 곱셈 오버플로 두 건, dns.c 의 비교 한 건, sandbox 드라이버의 포인터 스케일링 다섯 건, tftp.c 의 strcpy 한 건뿐이고 nfs.c 는 없다](/assets/img/codeql-study/08-std.png)

규칙 95개에서 216건이 나왔지만 `nfs.c` 는 한 건도 없었다. 표준 쿼리의 원격 입력 모델은 `recv` 나 `read` 같은 함수로 데이터를 받는 코드를 전제로 한다. U-Boot는 네트워크 드라이버가 받은 프레임을 `net_process_received_packet(uchar *in_packet, int len)` 에 포인터로 넘기는 구조라서, 표준 모델 입장에서는 이 버퍼가 외부 입력인지 알 방법이 없다. 이 코드베이스에서 어디가 공격자 입력인지 아는 것은 분석하는 사람이고, 그 지식을 쿼리에 적어 넣어야 결과가 나온다. 이번에는 "네트워크 바이트 순서를 뒤집는 식"을 출발점으로 삼는 것으로 그 지식을 표현했다.

## 5. 실습 3: 패치된 2019.10에 다시 돌리기

쿼리가 버그를 찾는다면, 버그가 고쳐진 버전에서는 결과가 사라져야 한다. v2019.10과 v2019.07 사이의 `net/` 커밋을 보면 CVE 수정이 다섯 개 들어가 있다. 2019.10으로 데이터베이스를 하나 더 만들어 같은 쿼리를 돌렸다.

### 5.1 차단 조건이 부족했다

3.4절에서 말한 04번 쿼리를 먼저 돌렸을 때는 결과가 꽤 많이 남았다. 사라진 것은 응답 처리 함수 다섯 개의 `memcpy` 뿐이었다. 수정 커밋을 하나씩 열어 보니 이유가 보였다. 다섯 개를 고친 커밋은 `nfs_handler` 에 `if (len > sizeof(struct rpc_t)) return;` 을 넣었는데, 변수 `len` 이 비교식에 그대로 놓여 있어서 04번 쿼리도 알아봤다. 나머지 수정은 모양이 달랐다.

```c
/* cf3a4f1e86: CVE-2019-14195 수정 */
if (((uchar *)&(rpc_pkt.u.reply.data[0]) - (uchar *)(&rpc_pkt) + rlen) > len)
        return -NFS_RPC_DROP;

/* fe7288069d: UDP 길이 수정 */
if (ntohs(ip->udp_len) < UDP_HDR_SIZE || ntohs(ip->udp_len) > ntohs(ip->ip_len))
        return;
```

앞의 것은 `rlen` 이 덧셈식 안에 들어 있고, 뒤의 것은 변수 없이 `ntohs(ip->udp_len)` 이라는 식을 직접 비교한다. 04번 쿼리는 둘 다 검사로 보지 못했다. 그래서 비교식 안쪽을 뒤져 같은 모양의 식(`hashCons`)을 찾도록 고쳤다.

### 5.2 넓혔더니 진짜 버그를 놓칠 뻔했다

고치고 나서 다시 보니 이번에는 너무 많이 지울 것 같았다. 남은 결과 중 `nfs_lookup_reply` 의 `filefh3_length` 를 확인하러 U-Boot 이력을 뒤지다가 [bdbf7a05e2](https://github.com/u-boot/u-boot/commit/bdbf7a05e26f3c5fd437c99e2755ffde186ddc80) 커밋을 찾았다. 2022년에 들어간 이 커밋의 메시지에는 CVE-2019-14196의 2019년 수정이 무력했다고 적혀 있다. `filefh3_length` 가 `static int` 라서, 서버가 보낸 값이 음수면 `offset + filefh3_length > len` 검사를 그대로 통과한다. 이 문제는 [CVE-2022-30767](https://nvd.nist.gov/vuln/detail/CVE-2022-30767)로 다시 등록됐고 변수를 `unsigned int` 로 바꿔서 고쳤다.

비교식 안쪽까지 인정하도록 넓힌 상태라면 이 검사도 통과로 처리돼서 결과가 사라졌을 것이다. 상한 검사는 값이 음수가 될 수 없을 때만 의미가 있다. 처음에는 "부호 없는 타입이면 인정"으로 조건을 붙였다. 그랬더니 이번에는 UDP 길이 검사가 인정되지 않았다. 디버그용 쿼리로 확인해 보니 U-Boot의 `ntohs` 는 `__builtin_constant_p(x) ? ___swab16(x) : __fswab16(x)` 형태의 조건식으로 전개되고, 정수 승격 때문에 이 식의 타입이 `int` 로 잡혀 있었다. 16비트 값을 뒤집은 결과라 음수일 수 없는데 타입만 보면 부호가 있다. 그래서 타입 대신 범위 분석의 `lowerBound(e) >= 0` 을 쓰는 지금의 05번 쿼리가 됐다.

### 5.3 남은 결과는 모두 나중에 고쳐진 버그였다

![U-Boot 2019.10 데이터베이스에 05번 쿼리를 돌린 결과 10건. net.c 의 __net_defragment 한 건, nfs.c 의 store_block 한 건, rpc_req 두 건, nfs_readlink_req, nfs_read_req, nfs_lookup_reply 각 한 건, nfs_readlink_reply 두 건, ping.c 의 ping_receive 한 건이다. netconsole, efi_net, 응답 처리 함수 다섯 개의 결과는 사라졌다](/assets/img/codeql-study/07-uboot1910.png)

netconsole, EFI, 응답 처리 함수 다섯 개처럼 2019.10에서 실제로 고쳐진 곳은 결과에서 사라졌다. 남은 10건을 다시 U-Boot 이력과 NVD에 대조했다.

| 도착점 | 출발점 | 고쳐진 시점 |
|---|---|---|
| `net.c:1018` __net_defragment, `ping.c:108` | `net.c:922` IP 전체 길이 | [CVE-2022-30552](https://nvd.nist.gov/vuln/detail/CVE-2022-30552), b85d130ea0 (2022-05) |
| `nfs.c:578` nfs_lookup_reply 외 4건 | `nfs.c:573` 파일 핸들 길이 | [CVE-2022-30767](https://nvd.nist.gov/vuln/detail/CVE-2022-30767), bdbf7a05e2 (2022-05) |
| `nfs.c:106` store_block | `nfs.c:695` nfs_read_reply 읽은 길이 | [CVE-2026-74220](https://nvd.nist.gov/vuln/detail/CVE-2026-74220), 0bbf098596 (2026-08) |
| `nfs.c:651`, `:656` nfs_readlink_reply | `nfs.c:639` 경로 길이 | [CVE-2026-74221](https://nvd.nist.gov/vuln/detail/CVE-2026-74221), 1c0aff3a5f (2026-08) |

`__net_defragment` 결과는 2019.07에서도 나왔던 것이다. IP 헤더의 전체 길이에서 헤더 크기 20을 빼는데, 전체 길이가 20보다 작으면 `int len` 이 음수가 되고 그대로 `memcpy` 에 들어간다. 이 버그는 NCC Group이 2022년에 보고했고, 수정 커밋 [b85d130ea0](https://github.com/u-boot/u-boot/commit/b85d130ea0cac152c21ec38ac9417b31d41b5552)의 메시지에 같은 설명이 "BUG 2"로 적혀 있다. 2019년 코드에 대해 짠 쿼리가 3년 뒤에 보고될 버그 자리를 이미 가리키고 있었던 셈이다.

나머지 둘은 더 최근이다. `nfs_read_reply` 와 `nfs_readlink_reply` 는 2019년 수정 이후에도 길이를 `int rlen` 에 담고 있었다. 2026년 8월 메일링 리스트에 올라온 [패치](https://ratatoskr.run/u-boot/2026/08/17435127/t) 설명에 따르면, 64비트 대상에서는 포인터 뺄셈 결과가 64비트 `ptrdiff_t` 라서 최상위 비트가 켜진 길이가 음수로 계산되고 검사를 통과한다. 이후 `store_block` 이 이 값을 `unsigned int` 로 받아 2GB 가까이 복사한다. 32비트 보드라면 같은 식이 부호 없는 비교로 계산돼 검사에 걸린다. 내가 분석한 데이터베이스가 x86-64 sandbox 빌드였기 때문에 64비트 쪽 동작이 반영됐다는 점도 1.1절에서 말한 "빌드한 그대로 보인다"와 같은 이야기다. 둘 다 v2026.10-rc5에서 `u32 rlen` 으로 고쳐졌다.

처음 이 결과를 봤을 때는 아직 안 알려진 버그일 수도 있다고 생각했다. 그래서 글에 쓰기 전에 최신 소스와 메일링 리스트부터 확인했다. 이미 보고되고 고쳐진 뒤였다. 쿼리 결과가 "의심스럽다"는 것과 "알려지지 않았다"는 것은 별개라서, 이 확인을 건너뛰면 남이 찾은 버그를 새 발견처럼 쓰게 된다.

## 6. 실습 4: 2026년 최신 소스

마지막으로 2026-10-05 기준 `main`(8d7bc8add1)으로 데이터베이스를 만들었다. 최신 U-Boot는 빌드에 `swig` 와 `efitools` 가 필요해서 패키지를 더 설치했다. 그런데 05번 쿼리가 끝나지 않았다. Java 힙 부족으로 연달아 실패했고, `--ram` 을 늘려도 힙 상한은 2GB 남짓에서 크게 늘지 않았다. `--ram` 으로 준 메모리는 힙과 디스크 캐시용 메모리로 나뉘기 때문이다.

처음에는 범위 분석을 의심했다. 소스가 2019년보다 훨씬 커졌고, `SimpleRangeAnalysis` 는 비싸기로 알려져 있다. 그런데 데이터베이스의 `log/` 에 남은 평가 로그를 보니 실패는 매번 같은 곳에서 났다.

![최신 main 분석 실패 원인을 추적한 화면. 05번 쿼리의 평가 로그에서 마지막으로 평가를 시작한 술어는 edges#query 다. 그 아래는 net.c 982번 줄에서 출발한 오염이 닿는 전역 변수 대입을 찾은 디버그 쿼리 결과로, malloc_extend_top 안의 sbrk_base, max_sbrked_mem, max_total_mem 과 sbrk 안의 mem_malloc_brk 가 나온다](/assets/img/codeql-study/11-main-hub.png)

마지막으로 시작한 술어가 `edges#query`, 즉 경로 결과의 간선을 만드는 출력 단계였다. 흐름 계산은 이미 끝났고, 찾은 경로를 그래프로 펼치다가 메모리가 모자란 것이다. 그래서 경로 없이 출발점과 도착점 쌍만 내도록 `@kind problem` 으로 바꿔 돌렸다. 6분쯤 걸려 끝나긴 했는데 결과가 65건이었고, 그중 대부분이 `net.c:982` 의 `__net_defragment` 한 곳에서 출발해 lz4 압축 해제, mbedtls 인증서 파서, 디바이스 트리 라이브러리의 `memcpy` 에까지 닿아 있었다. 네트워크 조각 재조립 코드와 아무 관계가 없는 곳들이다.

어디서 번지는지 보려고, 차단 조건 없이 `net.c:982` 하나만 출발점으로 두고 "오염된 값이 전역 변수에 대입되는 곳"을 찾는 디버그 쿼리를 짰다. 위 화면 아래쪽이 그 결과다. U-Boot의 자체 할당기(`common/dlmalloc.c`) 안에 있는 `mem_malloc_brk`, `max_total_mem` 같은 전역 상태가 오염돼 있었다. 패킷에서 나온 길이로 `malloc(len)` 을 부르는 곳이 있으면, 할당기 본문이 그 크기로 내부 전역 변수를 갱신한다. 그 뒤로는 어떤 `malloc` 이 돌려준 포인터든 이 전역 변수에서 계산되니 전부 오염된 것으로 처리된다. glibc를 쓰는 보통 프로그램이라면 `malloc` 본문이 데이터베이스에 없고 라이브러리 모델로만 처리되니 생기지 않을 문제다. 할당기까지 직접 컴파일하는 펌웨어라서 생겼다.

할당기 본문 안의 노드를 차단점에 추가한 것이 06번 쿼리다.

```ql
  predicate isBarrier(DataFlow::Node n) {
    boundedAbove(n.asExpr())
    or
    // malloc(len) 의 len 이 할당기 내부 전역 상태(mem_malloc_brk 등)를 오염시키면
    // 그 뒤 모든 할당 결과가 오염된 것으로 번진다. 할당기 본문은 따라 들어가지 않는다.
    n.getFunction().getFile().getBaseName() = "dlmalloc.c"
  }
```

2019.07과 2019.10에서는 05번과 같은 도착점을 그대로 냈다. 최신 main에서는 10건으로 줄었다.

![최신 main 에 06번 쿼리를 돌린 결과 10건. efi_image_loader.c 의 efi_prepare_aligned_image 가 tftp.c 495번 줄의 tftp_handler 에서, net.c 1104번 줄의 __net_defragment 와 ping.c 112번 줄의 ping_receive 가 net.c 982번 줄에서, nfs-common.c 의 rpc_req_common 두 건, nfs_readlink_req, nfs_read_req, nfs_lookup_reply 가 603번 줄의 nfs_lookup_reply 에서, nfs_lookup_req 와 nfs_mount_reply 가 551번 줄의 nfs_mount_reply 에서 출발한다](/assets/img/codeql-study/12-main.png)

이번에는 비교할 수정 이력이 없으니 코드를 직접 읽어 하나씩 판정했다. 읽어 본 범위에서 위험한 것은 없었다. 오탐이 남은 이유는 각각 달랐다.

`nfs-common.c` 의 일곱 건은 파일 핸들 길이(`filefh3_length`, `dirfh3_length`)에서 출발한다. 지금은 둘 다 `unsigned int` 이고, `if (filefh3_length > NFS3_FHSIZE) filefh3_length = NFS3_FHSIZE;` 로 값을 64로 깎은 뒤 복사한다. 비교문이 `memcpy` 를 막아서는 대신 값을 대입으로 바꾸는 형태라서, 비교문이 지키는 블록만 보는 내 차단 조건이 알아보지 못했다.

`__net_defragment` 와 `ping_receive` 는 2022년 수정 이후의 코드다. 함수 첫머리에 `if (ntohs(ip->ip_len) <= IP_HDR_SIZE) return NULL;` 이 생겼고, 그 다음 줄들에서 `len = ntohs(ip->ip_len) - IP_HDR_SIZE` 를 계산한 뒤 `start + len > IP_MAXUDP` 로 상한도 본다. 그런데 범위 분석은 앞의 검사가 뒤에서 새로 계산한 `len` 에도 적용된다는 것을 연결하지 못해서 `len` 의 하한을 음수로 본다. 그래서 상한 검사가 인정되지 않았다.

`efi_prepare_aligned_image` 는 TFTP 블록 번호가 다운로드한 파일 크기를 거쳐 흘러온 것이다. 그런데 이 함수는 `calloc(ALIGN(*efi_size, 8), 1)` 로 같은 크기 이상의 버퍼를 새로 잡은 뒤 복사한다. 목적지 크기가 같은 값에서 나오니 넘칠 수 없다. 이런 경우는 도착점에서 목적지 버퍼 크기와 비교해야 걸러지는데, 이번 쿼리는 그렇게까지 만들지 않았다.

할당기 차단점을 05번(경로 결과를 내는 형태)에 넣어 다시 돌려 보니, 이번에는 힙 부족 없이 끝나고 같은 10건을 냈다. 처음의 메모리 부족도 범위 분석 때문이 아니라 오염이 할당기를 타고 프로그램 전체로 번져 경로 그래프가 커진 탓이었다. 처음 추측대로 범위 분석을 빼는 쪽으로 쿼리를 고쳤다면 원인은 그대로 둔 채 결과만 바뀌었을 것이다.

## 7. 정리

원리를 직접 확인하고 나니 CodeQL의 강점과 한계가 같은 곳에서 나온다는 게 보였다. CodeQL은 컴파일러가 본 코드를 테이블로 옮겨 두고 그 위에서 Datalog를 돌린다. 그래서 매크로 전개, 정수 승격, 포인터 크기까지 정확하게 반영된다. 64비트 빌드에서만 생기는 부호 문제가 결과에 나온 것도 이 덕분이다. 반대로 빌드하지 않은 파일과 다른 설정에서만 컴파일되는 코드는 아예 보지 못한다. U-Boot의 C/C++ 파일 가운데 85%가 이번 분석 대상에 없었다.

쿼리 쪽에서 배운 것은 출발점과 도착점, 차단점을 정의하는 일이 곧 분석이라는 점이다. 표준 쿼리 묶음은 U-Boot의 NFS 버그를 하나도 찾지 못했다. 엔진이 약해서가 아니라 이 코드에서 무엇이 공격자 입력인지 몰랐기 때문이다. 차단점을 넓히면 오탐이 줄지만, 이번처럼 무력한 패치를 정상 검사로 착각해 진짜 버그를 지울 수도 있다. 이번에는 패치 전후 버전과 이후 수정 이력이 있어서 그런 실수를 바로잡을 수 있었다. 이력이 없는 코드라면 차단 조건을 넓힐 때마다 그 조건이 무엇을 지우는지 직접 확인해야 한다.

최신 소스에서는 다른 종류의 문제를 만났다. 2019년 코드에서 잘 돌던 쿼리가 할당기를 타고 번진 오염 때문에 엉뚱한 결과를 내고 메모리까지 모자랐다. 결과가 이상하게 많거나 평가가 끝나지 않을 때, 엔진 설정을 만지기 전에 오염이 어디로 새는지부터 찾는 편이 빨랐다. 평가 로그와 작은 디버그 쿼리가 그 일을 해 줬다.

CodeQL CLI는 오픈 소스 코드 분석과 학술 연구, 시연 용도로는 무료로 쓸 수 있지만, 그 밖의 코드를 분석하려면 GitHub Advanced Security 라이선스가 필요하다. [라이선스 조건](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md)을 먼저 읽어 보는 것이 좋다.

## 실습 파일

- [qlpack.yml](/assets/files/codeql-study/qlpack.yml), [NetworkByteSwap.qll](/assets/files/codeql-study/NetworkByteSwap.qll)
- 쿼리: [01-memcpy-calls.ql](/assets/files/codeql-study/01-memcpy-calls.ql), [02-ntoh.ql](/assets/files/codeql-study/02-ntoh.ql), [03-ntoh-to-memcpy.ql](/assets/files/codeql-study/03-ntoh-to-memcpy.ql), [04-ntoh-to-memcpy-guarded.ql](/assets/files/codeql-study/04-ntoh-to-memcpy-guarded.ql), [05-ntoh-to-memcpy-bounded.ql](/assets/files/codeql-study/05-ntoh-to-memcpy-bounded.ql), [06-ntoh-to-memcpy-alloc-barrier.ql](/assets/files/codeql-study/06-ntoh-to-memcpy-alloc-barrier.ql), [dbg-tainted-globals.ql](/assets/files/codeql-study/dbg-tainted-globals.ql)
- 예제: [pktd.c](/assets/files/codeql-study/pktd.c), [poc.sh](/assets/files/codeql-study/poc.sh)
- 스크립트: [analyze.sh](/assets/files/codeql-study/analyze.sh), [sarif_summary.py](/assets/files/codeql-study/sarif_summary.py), [eval_summary.py](/assets/files/codeql-study/eval_summary.py), [std_summary.py](/assets/files/codeql-study/std_summary.py)

## 참고 자료

- [CodeQL 공식 사이트](https://codeql.github.com/)
- [About CodeQL](https://codeql.github.com/docs/codeql-overview/about-codeql/), [Evaluation of QL programs](https://codeql.github.com/docs/ql-language-reference/evaluation-of-ql-programs/), [Analyzing data flow in C and C++](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-cpp/)
- Pavel Avgustinov 외, [QL: Object-oriented Queries on Relational Data](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2016.2), ECOOP 2016
- GitHub Security Lab, [U-Boot NFS RCE Vulnerabilities (CVE-2019-14192)](https://securitylab.github.com/research/uboot-rce-nfs-vulnerability/)
- NVD: [CVE-2019-14192](https://nvd.nist.gov/vuln/detail/CVE-2019-14192), [CVE-2022-30552](https://nvd.nist.gov/vuln/detail/CVE-2022-30552), [CVE-2022-30767](https://nvd.nist.gov/vuln/detail/CVE-2022-30767), [CVE-2026-74220](https://nvd.nist.gov/vuln/detail/CVE-2026-74220), [CVE-2026-74221](https://nvd.nist.gov/vuln/detail/CVE-2026-74221)
- U-Boot 커밋: [fe7288069d](https://github.com/u-boot/u-boot/commit/fe7288069d2e6659117049f7d27e261b550bb725), [741a8a08eb](https://github.com/u-boot/u-boot/commit/741a8a08ebe5bc3ccfe3cde6c2b44ee53891af21), [b85d130ea0](https://github.com/u-boot/u-boot/commit/b85d130ea0cac152c21ec38ac9417b31d41b5552), [bdbf7a05e2](https://github.com/u-boot/u-boot/commit/bdbf7a05e26f3c5fd437c99e2755ffde186ddc80), [0bbf098596](https://github.com/u-boot/u-boot/commit/0bbf09859658b8cc9ac13be41af23b516b8ef69a), [1c0aff3a5f](https://github.com/u-boot/u-boot/commit/1c0aff3a5fbfeee7a8948f624e0b8554e6e0d8fd)
- Shahriyar Jalayeri, [net: nfs: bound server-supplied lengths in READ and READLINK replies (v3)](https://ratatoskr.run/u-boot/2026/08/17435127/t), U-Boot 메일링 리스트
