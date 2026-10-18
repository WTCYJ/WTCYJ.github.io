---
layout: post
title: "crash dedup·minimization"
date: 2027-01-04 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 퍼징, 크래시분석, libFuzzer, AFLpp]
excerpt: "AFL의 'unique crashes' 숫자는 버그 개수가 아니다. 커버리지 비트맵으로 버킷팅하므로 한 버그가 수천 개로 뻥튀기되고(overcount), 반대로 top frame만 보는 dedup은 서로 다른 버그를 free()·memcpy() 프레임에서 뭉갠다(undercount)."
---

퍼저를 하루 돌리면 크래시가 수백에서 수천 개 쌓인다. 초보가 여기서 하는 착각 하나 — 그 숫자를 버그 개수로 믿는 것. 아니다. 대부분은 같은 버그가 다른 경로로 도달해 중복 저장된 것이고, 상당수는 크래시조차 아닌 feature-gate abort나 hang이다. 진짜 일은 퍼징이 아니라 그 뒤에 온다: 중복을 접고(dedup), 입력을 깎고(minimize), 남은 소수의 서명(signature)을 사람이 읽을 수 있게 만드는 것.

이 글은 7장(Parser용 libFuzzer harness)과 8장(corpus·dictionary·coverage)에서 세운 하네스·코퍼스로 얻은 크래시 더미를 dedup·minimization 파이프라인으로 정리하는 절차를 실습한 기록이다. 대상은 전부 자작 하네스와 이미 패치된 공개 CVE·오픈소스 파서다.

> **한 줄 결론**: AFL의 'unique crashes'는 버그 수가 아니다. 커버리지 비트맵 버킷팅은 한 버그를 수천 개로 부풀리고(overcount), top frame만 보는 dedup은 서로 다른 버그를 `free()`/`memcpy()` 프레임에서 뭉갠다(undercount). dedup은 스택을 정규화해 crash type + top-N 프레임으로, minimization은 '같은 서명'을 보존하며 해야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

scope는 셋이다. (1) 크래시 dedup의 세 방식 — 커버리지 버킷 / top-N 스택 / stack hash — 과 각 방식의 오차 방향, (2) 두 종류의 minimization — 코퍼스 최소화(`afl-cmin`, libFuzzer `-merge`)와 테스트케이스 최소화(`afl-tmin`, `-minimize_crash`), (3) hang·abort를 크래시와 분리하는 트리아지.

선수 지식. 7장에서 libFuzzer 하네스를, 8장에서 코퍼스·딕셔너리·커버리지를 이미 세웠다고 가정한다. sanitizer 리포트를 읽을 줄 알아야 한다 — ASan의 top frame이 무엇인지 모르면 dedup 키를 만들 수 없다. sanitizer 자체는 다음 장인 10장(sanitizer 기반 native 연구)에서 더 깊게 다룬다. 완화 배경은 Atlas C37을 참고하면 된다.

전체 구조에서 이 장은 "퍼저가 돈 다음"이다. 4부 파이프라인은 c07 harness → c08 corpus/coverage → **c09 dedup/minimization** → c10 sanitizer 분석으로 이어진다. 여기서 수천 개를 수 개로 줄여야 그 다음 사람 손이 감당할 크기가 된다.

## 핵심 개념 — dedup은 오차가 양방향이다

세 dedup 방식을 나란히 놓으면 이렇다.

| 방식 | 키 | 대표 도구 | 실패 방향 |
|--|--|--|--|
| 커버리지 버킷 | 크래시 시점 edge 비트맵 | AFL/AFL++ `unique crashes` | **overcount** — 도달 경로가 다르면 같은 버그도 별개 |
| top-N 스택 프레임 | crash type + 상위 N개 함수명(정규화) | ClusterFuzz/OSS-Fuzz | 균형 — N·정규화 방식에 민감 |
| stack hash | 백트레이스(상위 프레임) 해시 | honggfuzz | 프레임 하나만 달라도 별개 → over/undercount 혼재 |

핵심은 이거다: **완벽한 dedup은 없고 오차 방향만 고른다.** AFL의 `unique crashes`는 커버리지로 버킷팅하므로 한 버그가 수천 'unique'로 부풀려진다. `Reported` 반대로 top frame 하나만 키로 쓰면 `free()`·`memcpy()`·`operator new` 안에서 죽는 서로 다른 버그가 한 버킷으로 뭉개진다. `Inferred` 그래서 실무 dedup은 인터셉터·래퍼 프레임(`__asan_*`, `__interceptor_*`, libc `memcpy` 등)을 건너뛴 뒤 **호출자** 쪽 top-N을 잡는다. `Reported`

sanitizer는 이 dedup을 도와주는 힌트를 낸다. `ASAN_OPTIONS=dedup_token_length=3`을 주면 리포트에 `DEDUP_TOKEN:` 줄이 top-3 프레임으로 찍힌다 — sanitizer가 내는 top-N dedup 힌트다. `Reported` OSS-Fuzz/ClusterFuzz는 이 ASan 줄을 직접 소비하지 않고, 자체 스택 파싱으로 상위 N개 프레임(자체 ignore 정규식 적용)의 crash state를 따로 산출해 dedup한다 — 개념은 비슷한 top-N 토큰이되 계산 주체가 다르다. `Inferred`

> **[그림 1]** `afl-fuzz` status 화면의 `uniq crashes` 수치와, 같은 크래시들을 top-N 스택 프레임으로 dedup한 뒤 남은 실제 버그 수를 나란히 대조한 캡처 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 로컬이다. 대상은 (1) 7장에서 만든 자작 libFuzzer 하네스가 AOSP 네이티브 파서(이미 공개·패치된 CVE가 있는 미디어/이미지 파서)를 감싼 것, (2) 내 과거 하네스 — wabt(`wasm2c`), tinyobjloader-c, libsoup. 무기화된 익스플로잇은 만들지 않는다. dedup·minimization은 그 자체로 방어·트리아지 도구다. 크래시 입력은 원리 이해용 최소 샘플만 보관하고, 실서비스·제3자 앱 대상은 없다.

## 실습 절차와 관측

### 가설
- **가설 A** — `afl-fuzz`의 `uniq crashes`와, 같은 크래시들을 top-N 스택으로 dedup한 실제 버그 수는 자릿수가 다르다(전자 ≫ 후자). `Inferred`
- **가설 B** — `afl-tmin`/`-minimize_crash`는 '크래시'는 보존하지만 '같은 크래시'는 보장하지 않는다 — 최소화 후 `DEDUP_TOKEN`이 바뀌면 다른 버그로 흘러간 것이다. `Inferred`

### 절차
1. 코퍼스 최소화로 입력 수부터 줄인다.
2. 크래시 더미를 sanitizer 리포트로 재실행해 crash type + `DEDUP_TOKEN`을 뽑는다.
3. 토큰별로 버킷팅하고, 각 버킷 대표 하나만 남긴다.
4. 대표 크래시를 테스트케이스 최소화한다.
5. 최소화 결과가 **같은 토큰**을 유지하는지 확인한다(아니면 폐기).

```bash
# (1) 코퍼스 최소화 — 같은 edge를 덮는 최소 집합만 남긴다
afl-cmin -i corpus_raw -o corpus_min -- ./parser_target @@
#   libFuzzer라면:
./parser_fuzzer -merge=1 corpus_min corpus_raw

# (2) 크래시별 서명 뽑기 (interceptor 프레임 건너뛴 top-3)
#   파일별 루프 — libFuzzer는 첫 크래시에서 abort하므로 한 번에 넘기면 첫 파일 토큰만 찍힌다
for c in crash-*; do ASAN_OPTIONS=dedup_token_length=3 ./parser_fuzzer "$c" 2>&1 | grep -E 'ERROR|DEDUP_TOKEN'; done

# (4) 대표 크래시 최소화 — tmin은 크래시를 감지하면 crash mode로 보존한다
afl-tmin -i crash-orig -o crash-min -- ./parser_target @@
#   libFuzzer라면:
./parser_fuzzer -minimize_crash=1 -runs=100000 -exact_artifact_path=crash-min crash-orig
```

> **[그림 2]** `afl-tmin`(또는 libFuzzer `-minimize_crash`)으로 크래시 입력을 최소화하기 전/후 파일 크기와, 최소화 뒤에도 동일한 `DEDUP_TOKEN`(같은 top-3 프레임)이 나오는지 확인한 대조 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
# afl status
  uniq crashes : 3179
# top-3 스택 dedup 후
  distinct DEDUP_TOKEN : 4

# 최소화 전후
  crash-orig : 41027 bytes
  crash-min  :   118 bytes
  DEDUP_TOKEN(before) : ParseChunk--ReadU32--memcpy
  DEDUP_TOKEN(after)  : ParseChunk--ReadU32--memcpy   # 동일 → 유효
```

위 예시대로라면 3179개 'unique'가 실제로는 4개 버그였다는 뜻이다 — 이 블록을 실측치로 교체할 때 뒤따르는 4:3179 서술도 함께 갱신해야 한다. 이런 자릿수 격차가 dedup을 하지 않으면 안 되는 이유의 전부다. 그리고 최소화 후 토큰이 그대로면 유효, 바뀌었으면(예: `memcpy`→`abort`) 다른 버그로 샌 것이니 버린다.

feature-gate abort는 여기서 걸러진다. wabt를 퍼징하면 `UNIMPLEMENTED`(atomic wait/notify 등) abort가 결과를 뒤덮는데, 이건 메모리 안전 버그가 아니라 의도된 미구현 게이트다 — `DEDUP_TOKEN`이 abort 경로로 한 버킷에 모이므로 통째로 무시 목록에 넣는다. 그 잡음을 걷어낸 뒤 남은 게 실제 신호였다(내 wabt 케이스에선 #2751이 78일 만에 수정 머지, #2750은 여전히 open, 둘 다 CVE 없음). `Reported`

## Root Cause — 왜 이렇게 되는가

overcount의 뿌리는 AFL이 '크래시의 종류'가 아니라 '크래시에 도달한 경로'를 본다는 데 있다. `unique crashes`는 크래시 순간의 edge 커버리지 튜플이 새로우면 새 크래시로 센다 — 같은 널 역참조라도 앞선 분기가 다르면 다른 버킷이다. `Reported` 파서는 입력 앞부분에서 분기가 폭발적으로 갈리므로, 한 버그가 수천 경로로 도달해 수천 'unique'가 된다.

undercount는 정반대 이유다. 메모리 버그는 대개 `free()`·`memcpy()`·`malloc` 같은 공용 지점에서 터진다. top frame만 키로 쓰면 이 공용 프레임이 키가 되어 서로 다른 버그가 한 버킷으로 접힌다. 그래서 dedup은 sanitizer 인터셉터와 libc 래퍼 프레임을 스킵하고 그 위 **호출자** top-N을 잡아야 한다. `Inferred`

minimization이 다른 버그로 새는 것도 구조적이다. `afl-tmin`과 `-minimize_crash`의 종료 조건은 '크래시가 난다'이지 '같은 크래시가 난다'가 아니다. `Source-confirmed` 입력을 깎다 보면 우연히 더 얕은 다른 버그를 먼저 때릴 수 있고, 그러면 최소화기는 만족하고 멈춘다 — 결과물은 원래 버그와 무관해진다. 그래서 종료 조건을 서명(`DEDUP_TOKEN`/top frame)으로 좁혀야 한다.

## 방어와 회귀 검증

- **dedup 파이프라인 자체를 회귀 검증한다.** 이미 서로 다른 버그로 아는 두 크래시(예: tinyobjloader-c의 `f[16]` OOB write vs libsoup Range 정수 오버플로 assert)를 넣어 두 버킷으로 갈라지는지, 같은 버그의 두 경로가 한 버킷으로 합쳐지는지 고정 테스트로 박아 둔다. dedup 로직을 바꿔도 이게 안 깨지면 신뢰한다.
- **hang은 크래시가 아니다 — 분리 처리한다.** 무한 루프 DoS(예: IrfanView `Dpx.dll`의 CWE-835 사례)는 sanitizer 크래시가 아니라 timeout으로 잡힌다. AFL은 hang을 crashes와 별도 디렉터리로 나누고, libFuzzer는 `-timeout`으로 처리한다. hang을 크래시 버킷에 섞으면 dedup 키(스택)가 없어 통계가 오염된다. `Source-confirmed`
- **최소화 유효성은 토큰 동일성으로 게이트한다.** 최소화 전후 `DEDUP_TOKEN`이 다르면 그 결과는 버린다. 코퍼스 최소화(`-merge`/`cmin`)와 테스트케이스 최소화(`tmin`/`minimize_crash`)는 목적이 다르다 — 전자는 '커버리지 유지', 후자는 '크래시 재현'이다. 둘을 섞어 부르면 안 된다.
- 도구 버전 주의: `afl-tmin`의 crash mode 자동 진입, libFuzzer `-minimize_crash` 플래그 조합은 버전에 따라 옵션이 달라질 수 있어 문서 재확인이 필요하다. `원문 재확인 필요`

## 정리

- 'unique crashes' 숫자는 버그 수가 아니다. 커버리지 버킷은 overcount, top-frame-only는 undercount — dedup은 스택을 정규화해 crash type + top-N으로 한다.
- minimization은 두 종류다: 코퍼스(`-merge`/`cmin`, 커버리지 유지)와 테스트케이스(`tmin`/`minimize_crash`, 크래시 재현). 후자는 '같은 서명'을 게이트로 걸어야 다른 버그로 새지 않는다.
- hang·feature-gate abort는 크래시와 분리해 걷어낸다. 남은 소수의 서명만 사람이 읽는다.

**점검 질문** — (1) `afl-fuzz`의 `uniq crashes`가 위 예시의 4:3179처럼 부풀려지는 이유는 무엇이고, 반대로 top frame만으로 dedup하면 왜 undercount 되는가? (2) `afl-tmin`으로 최소화한 크래시가 '유효'하다고 말하려면 무엇이 같아야 하는가? (3) 무한 루프 DoS를 크래시 버킷에 넣으면 안 되는 이유는?

**참고** — LLVM libFuzzer(`-merge`/`-minimize_crash`) https://llvm.org/docs/LibFuzzer.html · AFL++(`afl-cmin`/`afl-tmin`) https://github.com/AFLplusplus/AFLplusplus · honggfuzz https://github.com/google/honggfuzz · sanitizer common flags(`dedup_token_length`) https://github.com/google/sanitizers/wiki/SanitizerCommonFlags · OSS-Fuzz/ClusterFuzz dedup https://google.github.io/oss-fuzz

*다음 글: [sanitizer 기반 native 연구](/posts/android-vulnresearch-p4c10/).*
