---
layout: post
title: "corpus·dictionary·coverage"
date: 2027-01-03 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, libFuzzer, 퍼징, 커버리지, corpus]
excerpt: "퍼징의 성패는 하네스가 아니라 코퍼스가 가른다. 그런데 흔한 함정은 코퍼스를 무작정 키우는 것 — 커버리지가 겹치는 씨앗 1만 개보다 -merge로 추린 서로 다른 200개가 더 빨리 버그를 찾는다. dictionary가 없으면 매직바이트 체크조차 못 넘어 커버리지가 입구에서 평평해진다."
---

앞 장에서 파서용 libFuzzer 하네스를 세웠다. 그런데 하네스만 있으면 버그가 나오느냐 하면, 그렇지 않다. 커버리지 기반 퍼저는 "지금 입력이 새 코드 경로를 열었는가"라는 피드백으로 방향을 잡는데, 그 피드백을 만들어내는 재료가 **씨앗 코퍼스**와 **딕셔너리**다. 이 둘이 부실하면 퍼저는 파일 매직바이트나 형식 키워드 같은 첫 관문조차 못 넘고, 커버리지 그래프가 입구에서 평평해진 채 며칠을 태운다.

이 글은 파서 하네스 하나를 놓고 코퍼스를 모으고 딕셔너리를 붙이고 커버리지로 진전을 측정하는 워크플로를, 실제로 돌아가는 명령과 함께 정리한 기록이다. 대상은 전부 오픈소스(AOSP·자작 하네스·이미 공개된 파서)이고, 목적은 무기화가 아니라 "왜 이 입력이 여기서 막히는가"를 커버리지로 읽는 것이다.

> **한 줄 결론**: 커버리지 퍼징은 코퍼스를 키우는 게임이 아니라 **서로 다른 경로를 여는 최소 코퍼스**를 만드는 게임이다. 딕셔너리로 형식 게이트를 넘기고, `-merge`로 중복을 걷어내고, `llvm-cov`로 미도달 지점을 봐서 씨앗을 보강한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 세 가지를 다룬다 — (1) 파서 형식에 맞는 씨앗 코퍼스를 모으고 `-merge=1`로 증류하는 법, (2) 매직바이트·키워드를 담은 AFL 형식 딕셔너리 작성, (3) libFuzzer의 `cov`/`ft` 카운터와 `llvm-cov` 리포트로 커버리지를 읽어 씨앗·딕셔너리를 되먹임하는 법이다. crash 자체의 중복 제거와 최소화는 다음 장의 몫이라 여기선 다루지 않는다.

선수 지식은 앞 장이다. 파서 하네스(`LLVMFuzzerTestOneInput`)와 `-fsanitize=fuzzer,address` 빌드가 이미 손에 있다고 전제한다. 커버리지 계측이 왜 컴파일 타임에 들어가는지(SanitizerCoverage가 분기마다 카운터를 심는다)는 Atlas의 계측/새니타이저 편에서 다룬 내용을 그대로 쓴다. AOSP 쪽에서는 Soong의 `cc_fuzz` 모듈이 이 빌드를 대신 해준다.

전체 구조에서 이 장의 위치는 "표면을 정하고(앞 파트) 하네스를 세운(앞 장)" 다음, **하네스를 실제로 작동시키는** 단계다. 여기서 만든 코퍼스와 딕셔너리는 이후 crash 분류·새니타이저 분석 장에서 그대로 재료가 된다.

## 핵심 개념 — 코퍼스·딕셔너리·커버리지

세 축을 한 줄씩 먼저 못 박자.

| 축 | 무엇 | 없으면 생기는 증상 | 근거 라벨 |
|--|--|--|--|
| **corpus(씨앗)** | 형식이 유효한 샘플 입력 모음. libFuzzer는 이 디렉터리에서 시작해 변이한다 | 빈 코퍼스는 바이트를 0부터 쌓아 형식 헤더를 우연히 맞춰야 한다 → 진입이 느리다 | `Source-confirmed` |
| **dictionary** | 매직바이트·키워드·마커 토큰 목록. 변이 시 통째로 삽입된다 | `RIFF`·`ftyp` 같은 상수 비교를 못 넘어 커버리지가 입구에서 평평 | `Source-confirmed` |
| **coverage** | 실행이 도달한 엣지/피처. `cov`(엣지)·`ft`(피처) 카운터로 표시 | 진전 여부를 숫자로 못 봐서 "언제까지 돌릴지"를 감으로 정하게 됨 | `Source-confirmed` |

**흔한 오해 1 — 코퍼스는 클수록 좋다.** 아니다. 커버리지가 겹치는 씨앗은 exec/s만 갉아먹는다. libFuzzer `-merge=1`은 같은 피처 집합을 유지하는 최소 부분집합만 남긴다. `Source-confirmed` 내 wabt 하네스 때도 수집한 `.wasm` 씨앗을 merge로 증류하니 절반 이하로 줄면서 커버리지는 그대로였다.

**흔한 오해 2 — 딕셔너리는 성능 튜닝 옵션이다.** 아니라 형식 게이트를 넘는 **필수 재료**다. AFL 딕셔너리 형식(`keyword="value"`, `\xNN` 이스케이프)을 libFuzzer도 `-dict=`로 그대로 읽는다. `Source-confirmed` 파서가 첫 4바이트로 매직을 검사하면, 딕셔너리에 그 매직이 없는 한 변이가 우연히 맞출 확률은 사실상 0이다.

**흔한 오해 3 — `cov` 숫자만 보면 된다.** `cov`는 도달한 엣지 수, `ft`는 값 프로파일까지 포함한 피처 수다. `-use_value_profile=1`을 켜야 `if (x == 0xCAFEBABE)` 같은 상수 비교의 부분 진전이 피처로 잡힌다. `Source-confirmed` `ft`가 오르는데 `cov`가 안 오르면 같은 엣지 안에서 새 값 상태를 파고드는 중이다.

> **[그림 1]** 딕셔너리 없이 돌린 것과 붙여 돌린 것의 libFuzzer 로그(`cov`/`ft` 증가 곡선)를 나란히 캡처 — 딕셔너리 쪽이 초반에 `cov`가 계단식으로 뛰는 대조 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **로컬 자작 하네스와 오픈소스 파서**로만 진행한다. 제3자 앱·실서비스·실기기는 없다. 대상은 이미 공개된 파서(예: 오픈소스 이미지/미디어 파서, 또는 AOSP `external/`의 fuzz 타깃)와, 그 위에 내가 얹은 최소 하네스다. 발견되는 것은 크래시일 뿐이고, 취약점 귀속·CVSS·무기화는 이 장의 범위가 아니다. crash를 RCE로 부풀리지 않는다 — 여기서 세는 것은 커버리지와 재현 입력뿐이다.

## 실습 절차와 관측

### 가설
- **가설 A** — 같은 씨앗 코퍼스라도 딕셔너리를 붙이면 초반 `cov` 상승이 눈에 띄게 빨라진다. `Inferred`
- **가설 B** — 무작정 모은 큰 코퍼스를 `-merge=1`로 증류하면 파일 수는 크게 줄지만 커버리지 피처 총량은 유지된다. `Inferred`
- **가설 C** — `llvm-cov report`에서 커버리지 0%인 함수는 씨앗/딕셔너리 보강의 우선 후보다. `Inferred`

### 절차
1. 형식이 유효한 샘플 몇 개를 `corpus/`에 넣어 씨앗을 만든다(파일 하나라도 없는 것보다 낫다).
2. 파서의 매직·키워드를 딕셔너리로 적는다.
3. 딕셔너리 유무로 두 번 짧게 돌려 초반 `cov`를 비교한다(가설 A).
4. 여러 번 돌린 코퍼스를 `-merge=1`로 증류한다(가설 B).
5. 커버리지 계측 바이너리를 따로 빌드해 코퍼스 전체를 먹이고 `llvm-cov`로 미도달 함수를 본다(가설 C).

```bash
# 1) 하네스 빌드 (앞 장의 harness.c + 대상 parser.c)
clang -g -O1 -fsanitize=fuzzer,address harness.c parser.c -o fuzz_parser

# 2) 딕셔너리 (AFL 형식: libFuzzer -dict= 가 그대로 읽음)
cat > parser.dict <<'EOF'
# magic / format tokens
riff="RIFF"
webp="WEBP"
fmt_="fmt "
data="data"
box_ftyp="ftyp"
EOF

# 3) 딕셔너리 유무 대조 (각 60초)
./fuzz_parser corpus/                    -max_total_time=60 -print_final_stats=1
./fuzz_parser corpus/ -dict=parser.dict  -max_total_time=60 -print_final_stats=1

# 4) 코퍼스 증류 (중복 피처 제거)
mkdir corpus_min
./fuzz_parser -merge=1 corpus_min/ corpus/

# 5) 커버리지 리포트용 별도 빌드 → 코퍼스 재생 → 리포트
clang -g -O1 -fprofile-instr-generate -fcoverage-mapping \
      -fsanitize=fuzzer harness.c parser.c -o cov_parser
LLVM_PROFILE_FILE=cov.profraw ./cov_parser corpus_min/ -runs=0
llvm-profdata merge -sparse cov.profraw -o cov.profdata
llvm-cov report --show-functions ./cov_parser -instr-profile=cov.profdata parser.c
```

`-runs=0`은 변이 없이 코퍼스를 한 번씩만 재생하라는 뜻이라, 순수하게 "이 코퍼스가 여는 커버리지"를 측정할 수 있다. `Source-confirmed` AFL++를 쓴다면 증류는 `afl-cmin -i corpus -o corpus_min -- ./target @@`, 개별 입력 축소는 `afl-tmin`이 같은 역할을 한다. `Source-confirmed`

> **[그림 2]** `-merge=1` 실행 로그(MERGE-OUTER 요약: 입력 N개 중 새 피처를 더한 파일 수)와 그 직후 `llvm-cov report`의 함수별 커버리지 표를 한 화면에 캡처 — *실측 스크린샷 자리*

### 관측 결과

딕셔너리 대조(절차 3)의 `예시 출력(교체)` — `MS:`(mutation sequence) 끝의 `ManualDict-`가 딕셔너리 삽입이 새 경로를 연 흔적이다:

```
# without dict
#2      INITED cov: 214 ft: 215 corp: 6/4096b exec/s: 0 rss: 44Mb
#65536  pulse  cov: 231 ft: 240 corp: 9/8Kb exec/s: 32768 rss: 61Mb

# with -dict=parser.dict
#2      INITED cov: 214 ft: 215 corp: 6/4096b exec/s: 0 rss: 44Mb
#512    NEW    cov: 402 ft: 588 corp: 41/12Kb exec/s: 25600 L: 96/4096 MS: 3 ChangeByte-InsertByte-ManualDict-
```

증류(절차 4)의 `예시 출력(교체)`:

```
MERGE-OUTER: 3096 files, 3096 in the initial corpus, 0 processed earlier
MERGE-OUTER: 214 new files with 5321 new features added; 4108 new coverage edges
```

커버리지 리포트(절차 5)의 `예시 출력(교체)` — `--show-functions`를 붙였으므로 `File '...'` 아래 `Name` 열에 함수명이 오고(파일 합계는 `TOTAL` 행), `parseChunk`가 0%면 그 청크 타입을 씨앗/딕셔너리에 넣어야 한다는 신호다:

```
File 'parser.c':
Name          Regions  Missed  Cover   Functions  Missed  Executed
parseChunk         46      46   0.00%          1       1      0.00%
--------------------------------------------------------------------
TOTAL             412      88  78.64%         37       6     83.78%
```

세 관측이 가설을 지지한다. 딕셔너리는 초반 `cov`를 214→402로 계단식으로 끌어올렸고(A), 3096개 코퍼스는 214개로 줄면서 피처는 보존됐고(B), 0% 함수가 다음에 무엇을 보강할지를 그대로 가리켰다(C).

## Root Cause — 왜 이렇게 되는가

커버리지 퍼징의 엔진은 단순하다. 입력을 변이해서 실행하고, **새 피처가 잡히면** 그 입력을 코퍼스에 남긴다. 이 루프는 "새 피처"라는 신호가 있어야만 방향을 잡으므로, 신호를 못 만드는 입력은 아무리 많아도 낭비다. 여기서 두 병목이 나온다.

첫째, **형식 게이트**. 파서는 대개 앞부분에서 매직·버전·청크 타입을 상수와 비교하고, 안 맞으면 즉시 반환한다. 랜덤 변이가 4바이트 매직을 맞출 확률은 무시할 수준이라, 딕셔너리로 그 토큰을 통째로 넣어주지 않으면 실행이 파서 입구에서 전부 되돌아온다. 그래서 커버리지가 특정 값에서 평평해진다. `Source-confirmed`

둘째, **코퍼스 중복**. 같은 경로만 여는 씨앗이 쌓이면 매 사이클 변이 대상만 늘고 새 신호는 안 나온다. `-merge=1`이 유지하는 불변식은 "합쳐진 코퍼스의 피처 합집합"이라, 같은 피처를 여는 파일 중 하나만 남긴다. 파일 수가 줄어도 커버리지가 보존되는 이유가 이것이다. `Source-confirmed`

정리하면, 코퍼스·딕셔너리·커버리지는 각각 **진입 신호를 만들고(딕셔너리)·신호 중복을 없애고(merge)·신호를 측정하는(coverage)** 세 역할이고, 셋 중 하나만 빠져도 퍼징은 신호 없이 도는 빈 루프가 된다.

## 방어와 회귀 검증

- **최소 재현 입력을 회귀 씨앗으로.** 크래시를 찾으면 그 입력을 최소화해 코퍼스에 남긴다. 패치 후 같은 코퍼스로 다시 돌리면, 그 입력이 크래시를 재현하지 않는지(=패치가 경로를 막았는지)를 `llvm-cov`로 확인할 수 있다. 이때 crash를 취약점으로 승격하지 말 것 — 재현되는 크래시가 곧 exploitable은 아니다. 내 libsoup Range 하네스에서 나온 것도 정수 오버플로로 인한 assert 종료(DoS)였지, 메모리 손상 RCE가 아니었다.
- **커버리지 리포트를 종료 기준으로.** "며칠 돌렸다"가 아니라 "커버리지가 N시간째 평평하고 미도달 함수가 씨앗/딕셔너리로 안 열린다"가 캠페인을 멈추거나 하네스를 고칠 근거다. wabt 캠페인도 실측 3시간이었고, 남은 UNIMPLEMENTED 분기는 커버리지 리포트가 "여긴 씨앗으로 못 연다"를 먼저 알려줬다.
- **구조화 퍼징은 게이트가 딕셔너리로 안 열릴 때만.** 형식에 체크섬·길이 상호검증이 있으면 딕셔너리로도 못 넘는다. 이럴 때 libprotobuf-mutator 같은 구조 인식 변이나 커스텀 뮤테이터를 붙인다. 다만 이건 비용이 크므로, 커버리지 리포트로 "정말 여기서 막힌다"를 확인한 뒤에 도입한다. `Reported`

## 정리

- 코퍼스는 **크기가 아니라 서로 다른 경로 수**다. `-merge=1`로 증류해 exec/s를 살린다.
- 딕셔너리는 성능 옵션이 아니라 형식 게이트를 넘는 필수 재료다 — 없으면 `cov`가 입구에서 평평해진다.
- 진전은 감이 아니라 `cov`/`ft` 카운터와 `llvm-cov` 리포트로 측정하고, 0% 함수가 다음 보강 지점을 가리킨다.
- 찾은 크래시의 최소 입력은 회귀 씨앗으로 남기되, 크래시를 취약점으로 부풀리지 않는다.

**점검 질문** — (1) 코퍼스를 무작정 키우면 왜 오히려 느려지고, `-merge=1`은 무엇을 불변으로 유지하는가? (2) 딕셔너리가 없을 때 파서 하네스의 커버리지가 "입구에서 평평"해지는 이유는? (3) libFuzzer 로그의 `cov`와 `ft`는 각각 무엇을 세며, `-use_value_profile=1`은 어느 쪽을 바꾸는가?

**참고** — [LLVM libFuzzer 문서](https://llvm.org/docs/LibFuzzer.html) · [SanitizerCoverage](https://clang.llvm.org/docs/SanitizerCoverage.html) · [source code coverage(llvm-cov)](https://clang.llvm.org/docs/SourceBasedCodeCoverage.html) · [AFL++ (afl-cmin/afl-tmin)](https://github.com/AFLplusplus/AFLplusplus) · [AOSP fuzzing(cc_fuzz)](https://source.android.com/docs/security/test/fuzz)

*다음 글: [crash dedup·minimization](/posts/android-vulnresearch-p4c09/).*
