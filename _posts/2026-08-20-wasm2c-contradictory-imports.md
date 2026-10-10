---
layout: post
title: "valid 하지만 linkable 하지 않은 모듈 — 내가 낸 wasm2c abort 가 78일 만에 error 가 되기까지"
date: 2026-08-20 09:00:00 +0900
category: BugBounty
author: SeiKa
tags: [wabt, WebAssembly, wasm2c, 퍼징, libFuzzer, ASAN, 계측, 하네스, 오픈소스제보, 업스트림, 코드리뷰, 실측]
excerpt: "wasm2c 하네스를 직접 짜서 돌리다 나온 크래시를 제보했더니, 메인테이너의 첫 답은 그건 valid 하지만 linkable 하지 않은 모듈이라는 반문이었습니다. 저도 동의했습니다. 제가 고쳐 달라고 한 건 지원이 아니라 실패하는 방식이었고, 78일 뒤 다른 기여자의 패치로 abort 가 error 로 바뀌었습니다. 고쳐진 빌드를 직접 세워서 무엇이 달라졌고 무엇이 남았는지 재봤습니다 — 같은 매크로가 아직 한 자리 남아 있고, 그 자리는 여전히 abort 합니다."
---

> **관련 글**: [WebAssembly를 직접 뜯어보며 배운 것들](/posts/webassembly/) · [퍼징 완전 정복 — AFL++, Jackalope, libFuzzer](/posts/fuzzing-guide/)
> **대상**: [WebAssembly/wabt](https://github.com/WebAssembly/wabt) · 제보 [#2751](https://github.com/WebAssembly/wabt/issues/2751) · 수정 [68a7ed2](https://github.com/WebAssembly/wabt/commit/68a7ed2769b883f6bfd83e4ea6ced6837a33dae7)

6월 1일에 wabt 에 이슈를 하나 냈습니다. `wasm2c` 가 유효한 WebAssembly 모듈 하나에
`abort()` 로 죽는다는 내용이었습니다. 메인테이너의 첫 답은 수정 약속이 아니라 반문이었습니다.

> Well, yes it's a *valid* module, but it's not a *linkable* module (…) What output do you
> think wasm2c should produce in this situation?
> — keithw, 2026-06-01

**맞는 말이었고, 저도 동의했습니다.** 그래서 논점을 옮겼습니다. 8월 18일에 그 이슈는
수정과 함께 닫혔습니다. 이 글은 그 78일 동안 무슨 일이 있었는지, 그리고 **고쳐진 빌드를
직접 세워서 재본 결과** 무엇이 실제로 달라지고 무엇이 남았는지에 대한 기록입니다.

---

## 1. 왜 하필 wasm2c 였나

wabt 는 이미 OSS-Fuzz 에 등록된 프로젝트입니다. 빌드 인프라가 갖춰져 있다는 뜻이고,
동시에 **쉬운 버그는 이미 다 잡혔다는 뜻**이기도 합니다. 그래서 새 하네스를 쓰는 대신
기존 하네스 6종이 **닿지 않는 코드**를 먼저 찾았습니다.

| wabt 도구 | 핵심 소스 | 기존 하네스 커버 |
|---|---|---|
| wat2wasm | wast-parser.cc (모듈 문법, 기본 기능만) | 부분 |
| **wasm2c** | **c-writer.cc** | **없음** |
| **wast2json** | **wast-parser.cc (스크립트 문법), binary-writer-spec.cc** | **없음** |
| wat-desugar | wat-writer.cc | 없음 |

`c-writer.cc` 는 6천 줄이 넘는 코드 생성기인데 퍼저가 한 번도 들어가 본 적이 없었습니다.
빈칸이 거기 있었습니다.

---

## 2. 하네스를 "도구와 똑같이" 만들지 않으면 전부 가짜양성이다

첫 하네스는 돌리자마자 크래시를 뱉었습니다. `c-writer.cc:669` 의 `MangleType` 에서
`WABT_UNREACHABLE` 이었습니다. 신났다가, 실제 도구로 재현이 안 됐습니다.

원인은 하네스 쪽에 있었습니다. `src/tools/wasm2c.cc` 는 코드 생성에 들어가기 **전에**
기능 게이트를 통과시킵니다.

```cpp
// src/tools/wasm2c.cc — 지원하지 않는 기능이 켜져 있으면 아예 시작을 안 한다
if (any_non_supported_feature) {
  fprintf(stderr, "wasm2c currently only supports a limited set of features.\n");
  exit(1);
}
```

즉 `function-references` 같은 미지원 기능이 켜진 입력은 **도구로는 codegen 에 도달할 수
없습니다.** 전 기능을 무차별로 켠 제 하네스만 거기 도달했던 겁니다. 크래시는 진짜였지만
**공격 표면에는 없는 크래시**, 하네스가 만들어 낸 아티팩트였습니다.

하네스에 같은 게이트를 그대로 복제하고 나서야 나온 크래시가 의미를 갖게 됐습니다.
**"크래시가 났다"와 "버그가 있다"는 다른 문장입니다.** 그 사이를 잇는 건 도달성이고,
도달성은 코드로 확인해야 합니다.

---

## 3. 계측이 빠진 줄도 모르고 돌리던 시간

두 번째 함정은 더 조용했습니다. 빌드를 이렇게 잡았습니다.

```bash
export CXXFLAGS="$CFLAGS"    # ← 여기
```

WSL 바깥 셸이 `$CFLAGS` 를 **먼저** 빈 값으로 확장해서, WSL 안에는 `CXXFLAGS=""` 가
들어갔습니다. C 파일만 계측되고 libwabt 본체(C++)는 전부 맨몸으로 컴파일됐습니다.
퍼저는 아무 불평도 하지 않았습니다. 다만 배너의 숫자가 이상했습니다.

```
# 계측이 빠진 빌드 (당시 기록)
$ nm libwabt.a | grep -c sancov
0
INFO: Loaded 1 modules (455 inline 8-bit counters)     # ← 사실상 하네스만 계측됨
```

컴파일러 래퍼로 플래그를 강제 주입해서 다시 빌드했습니다. 셸 변수 확장에 의존하지
않는 방법입니다.

```bash
# /tmp/cxxwrap
exec clang++ -fsanitize=address,undefined,fuzzer-no-link -fno-omit-frame-pointer -g -O1 "$@"
```

```
# 계측된 빌드 — 이 값은 캠페인 로그에 그대로 남아 있다
INFO: Loaded 1 modules (50400 inline 8-bit counters)
```

카운터가 두 자릿수 배로 뜁니다. **퍼징을 시작하기 전에 계측이 실제로 들어갔는지 재는 절차**가
없으면, 피드백도 세니타이저도 없이 몇 시간을 헛돌 수 있습니다. `nm | grep -c sancov` 한 줄,
또는 배너의 카운터 수 한 줄이면 됩니다.

제대로 계측된 상태로 wasm2c 캠페인을 돌렸고, 거기서 이 글의 크래시가 나왔습니다.
글을 쓰면서 당시 로그를 다시 열어 보니 캠페인 조건은 이랬습니다.

```
wasm2c_fuzzer -max_total_time=3600 -rss_limit_mb=4096 -max_len=16384 \
              -artifact_prefix=./ corpus_min          # 워커 8개
```

`-max_total_time=3600` 을 걸었지만 16코어에 ASAN 워커 8개를 얹어서, 끝까지 간 잡은
`Done ... in 10656 second(s)` 를 찍었습니다. 벽시계로는 10:25에 시작해 13:28에 끝났으니
1시간이 아니라 약 3시간짜리 캠페인이었습니다. 크래시 아티팩트는 10:40, 시작하고 15분쯤
지난 시점에 떨어졌습니다. **플래그로 건 시간과 실제로 돈 시간은 다를 수 있습니다.**

---

## 4. 나온 크래시 — 같은 이름, 다른 kind

최소화하면 세 줄입니다.

```wat
(module
  (import "e" "x" (func))
  (import "e" "x" (global i32)))
```

코어 WebAssembly 는 import 이름 중복을 금지하지 않습니다. 그래서 이건 유효한 모듈이고,
검증도 통과합니다. 30바이트짜리입니다.

```console
$ wat2wasm dup.wat -o dup.wasm     # 기본 기능, --enable-* 필요 없음
$ xxd dup.wasm
00000000: 0061 736d 0100 0000 0104 0160 0000 020e  .asm.......`....
00000010: 0201 6501 7800 0001 6501 7803 7f00       ..e.x...e.x...

$ wasm2c dup.wasm -o dup.c
Aborted (core dumped)                              # rc=134
```

원인은 `CWriter::ComputeUniqueImports` 였습니다. import 를 `(module, field)` 키로 map 에
넣다가 충돌하면, **같은 종류면 경고, 다른 종류면 abort** 였습니다.

```cpp
// src/c-writer.cc (수정 전)
if (!iterator_and_insertion_bool.second) {
  if (iterator_and_insertion_bool.first->second->kind() != import->kind()) {
    UNIMPLEMENTED("contradictory import declaration");        // ← 유효 입력에 abort
  } else {
    fprintf(stderr, "warning: duplicate import declaration ...");   // 같은 종류는 경고
  }
}
```

### 이 abort 는 아무 말도 남기지 않는다

이건 이번에 다시 재보다가 확인한 건데, 매크로 정의가 이렇습니다.

```cpp
// src/c-writer.cc:40
#define UNIMPLEMENTED(x) printf("unimplemented: %s\n", (x)), abort()
```

`stderr` 가 아니라 **`stdout` 으로 `printf`** 한 뒤 `abort()` 합니다. stdout 은 터미널이
아닐 때 블록 버퍼링이라, `abort()` 가 버퍼를 그대로 버립니다. 파이프나 CI 로그처럼
**터미널이 아닌 곳에서는 진단 메시지가 통째로 사라집니다.**

```console
$ wasm2c dup.wasm -o dup.c 2>&1 | cat
                                                    # ← 아무것도 안 나옴
rc=134

$ stdbuf -o0 wasm2c dup.wasm -o dup.c 2>&1 | cat
unimplemented: contradictory import declaration      # ← 버퍼링을 끄면 그제야 나옴
```

스크립트에서 돌리는 쪽 입장에서는 **이유 없는 SIGABRT** 하나만 남습니다.

---

## 5. 메인테이너의 답 — "valid 하지만 linkable 하지 않다"

이슈를 올리고 25분 만에 답이 달렸습니다.

> Well, yes it's a *valid* module, but it's not a *linkable* module under the conventions of
> how imports/exports are represented in wast/the reference interpreter or in wasm2c.
>
> I guess more to the point: What output do you think wasm2c should produce in this situation?
> — keithw, [#2751](https://github.com/WebAssembly/wabt/issues/2751)

핵심을 정확히 짚은 반문입니다. wasm2c 는 import 를 `(module, field)` 이름으로 호스트가
제공할 C 심볼에 대응시킵니다. 그런데 이 모듈은 **같은 키에 함수와 전역 두 개**를 요구합니다.
호스트가 하나의 이름으로 서로 다른 두 가지를 줄 방법이 없습니다. JS API 로 인스턴스화해도
`module.name` 하나에 값은 하나입니다.

**즉 "이 모듈을 지원하라"는 요구는 애초에 성립하지 않습니다.** 제 이슈가 그걸 요구한 건
아니었지만, 제목이 "abort on a **valid** module" 이었으니 그렇게 읽힐 여지는 충분했습니다.

---

## 6. 논점을 옮긴 곳 — 지원 여부가 아니라 실패하는 방식

그래서 답장에서 먼저 동의부터 했습니다. 받아들일 수 없다는 판단에 반대하지 않았습니다.

> Agreed — it's valid but not linkable (…) so I don't think wasm2c should try to *accept* it.
>
> My concern is only the failure mode, not the lack of support. Today this path hits
> `UNIMPLEMENTED(...)` → `abort()`, so any tool/service that runs wasm2c on untrusted input
> gets a SIGABRT instead of an error it can handle.
>
> So I'd expect wasm2c to **reject the module with a normal compile error** rather than abort
> (…) The existing same-kind duplicate branch already degrades to a warning; only the
> contradictory-kind branch aborts.

붙인 근거는 **같은 함수 안에 이미 정답이 있다**는 것이었습니다. 이름이 겹치는 같은 종류
import 는 이미 경고로 처리하고 넘어갑니다. 거절 자체가 문제였다면 그쪽도 abort 였어야 합니다.
한 분기만 abort 한다는 건 **정책이 아니라 미완성**이라는 신호입니다.

기대하는 출력 형태까지 초안으로 적어 뒀습니다.

```
error: contradictory import declaration: "e"."x" is imported as both a
function and a global; ...
```

이슈 하나에서 **요구를 줄이면 통과 가능성이 올라갑니다.** "새 기능을 구현해 달라"는
로드맵 논쟁이 되지만, "abort 대신 `Result::Error` 를 반환해 달라"는 20줄짜리 diff 입니다.

---

## 7. 68a7ed2 이 실제로 바꾼 것

8월 8일에 [ANAMASGARD(Gauarv Chaudhary)](https://github.com/ANAMASGARD) 님이
[PR #2813](https://github.com/WebAssembly/wabt/pull/2813) 을 올렸습니다. **패치를 쓴 건
제가 아닙니다.** sbc100 은 곧바로 승인("Seems reasonable to me")했지만, shravanrn 이 두 차례
변경을 요구했고 그 뒤 8월 18일에 머지됐습니다. 이슈는 1초 뒤 자동으로 닫혔습니다.

머지된 diff 는 두 파일, +33/−4 입니다. 한 줄로 요약하면 **abort 를 error 로 바꾸고, 그 error 를
호출자 네 곳까지 흘려보낸 것**입니다.

```diff
-void CWriter::ComputeUniqueImports() {
+Result CWriter::ComputeUniqueImports() {
@@
-        UNIMPLEMENTED("contradictory import declaration");
+        fprintf(stderr,
+                "error: contradictory import declaration: \"%s\".\"%s\" is "
+                "imported as both a %s and a %s\n",
+                import->module_name.c_str(), import->field_name.c_str(),
+                GetKindName(iterator_and_insertion_bool.first->second->kind()),
+                GetKindName(import->kind()));
+        return Result::Error;
@@ void CWriter::BeginInstance() {
-  ComputeUniqueImports();
+  if (Failed(ComputeUniqueImports())) {
+    result_ = Result::Error;
+    return;
+  }
```

여기에 `WriteModuleInstance()`, `WriteCHeader()`, `WriteModule()` 세 곳에
`if (Failed(result_)) return;` 가 추가됐습니다. 한 자리만 고치면 abort 는 사라지지만
**거절당한 모듈로 코드 생성이 계속 굴러가기 때문에**, 반환값을 끝까지 전달하는 부분이
실제 작업량이었습니다.

### "20줄짜리 diff" 가 리뷰를 두 번 돈 이유

제가 이슈에 적은 건 `UNIMPLEMENTED` 를 `Result::Error` 로 바꾸라는 한 줄짜리 요구였습니다.
그런데 그렇게 하려면 **어디서 검사할 것인가**를 정해야 하고, 거기서 리뷰가 두 번 돌았습니다.

첫 버전은 `WriteModule()` 시작 지점에서 미리 한 번 검사하고 `BeginInstance()` 의 호출을
빼는 모양이었습니다. 리뷰어가 곧바로 상태 순서를 짚었습니다.

> Doesn't `unique_imports_` have to be populated before this code is run? With this PR's
> removal of `ComputeUniqueImports()` from this function, it looks like this would no longer
> be the case — shravanrn

이 함수는 검사만 하는 게 아니라 **`unique_imports_` 를 채우는 함수**입니다. 검사를 앞으로
빼면서 원래 자리를 비우면 뒤쪽 코드 생성이 빈 목록을 보게 됩니다. 두 곳 모두에서 부르고
진입할 때 상태를 비우는 방식으로 고쳤더니, 이번엔 그 방식이 지적됐습니다.

> This seems a bit clunky. I think the right approach would be to not add multiple calls to
> `ComputeUniqueImports` and for `if (Failed(ComputeUniqueImports()))` to set the `_result`
> variable and return. You may need to add some checks to `_result` in the call stack (…)
> — shravanrn

최종 형태가 지금 main 에 있는 코드입니다. 커밋 제목만 봐도 경로가 그대로 보입니다.

```
660ac76  wasm2c: reject contradictory imports instead of aborting
fdcbc5b  wasm2c: restore ComputeUniqueImports in BeginInstance
b9daac6  wasm2c: use single ComputeUniqueImports call with result_ propagation
1a0967d  wasm2c: drop unnecessary ComputeUniqueImports clears
```

**abort 를 에러로 바꾸는 작업의 어려운 부분은 에러를 만드는 게 아니라, 에러가 난 뒤에도
계속 돌던 코드를 멈추는 것**입니다. `abort()` 는 그 뒷정리를 전부 건너뛰는 대가로 편했던
셈이고, 그걸 없애면 호출 스택이 그 몫을 나눠 져야 합니다.

그리고 회귀 테스트가 하나 추가됐는데, 내용이 제 PoC 그대로입니다.

```
;;; RUN: %(wat2wasm)s %(in_file)s -o %(temp_file)s.wasm
;;; RUN: %(wasm2c)s %(temp_file)s.wasm -o %(temp_file)s.c
;;; ERROR: 1
(module
  (import "e" "x" (func))
  (import "e" "x" (global i32)))
(;; STDERR ;;;
error: contradictory import declaration: "e"."x" is imported as both a func and a global
;;; STDERR ;;)
```

### 직접 세워서 재본 before / after

머지 커밋으로 체크아웃해 같은 옵션으로 다시 빌드하고, 같은 입력을 넣어 봤습니다.

```console
# 수정 전 (03a00a1)
$ wasm2c dup.wasm -o dup.c 2>&1 | cat
rc=134                      # 메시지 없음, SIGABRT

# 수정 후 (68a7ed2)
$ wasm2c dup.wasm -o dup.c 2>&1 | cat
error: contradictory import declaration: "e"."x" is imported as both a func and a global
rc=1                        # 파이프를 통과해도 메시지가 남는다
```

바뀐 건 종료 코드만이 아닙니다. **진단이 `stdout` 에서 `stderr` 로 옮겨 갔습니다.**
`stderr` 는 버퍼링되지 않으니 파이프·CI 로그에서도 사라지지 않습니다. 제가 이슈에 쓰지도
않았던 부분인데, `printf` 를 `fprintf(stderr, ...)` 로 바꾸면서 같이 해결됐습니다.

같은 이름·**같은** 종류 중복은 예전 그대로 경고 후 정상 생성입니다. 회귀가 없다는 확인입니다.

```console
$ wasm2c same.wasm -o same.c    # (import "e" "x" (func)) 를 두 번
warning: duplicate import declaration "e" "x"
rc=0                            # same.c 29,351 바이트 정상 생성
```

자잘하게 남은 건, 거절할 때도 출력 파일이 먼저 만들어진다는 점입니다. 0바이트 `.c` 와
`extern "C" {` 에서 잘린 459바이트 `.h` 가 남습니다. 빌드 스크립트가 "파일이 생겼으니 성공"
으로 읽으면 헷갈릴 수 있는 정도이고 종료 코드를 보면 되는 문제라, 따로 제보하지는 않았습니다.

---

## 8. 남은 것

**① 수정은 main 에만 있습니다.** 릴리스 태그에는 아직 안 들어갔습니다.

```console
$ git tag --contains 68a7ed2
                                # (없음)
$ git tag --sort=-creatordate | head -1
1.0.41                          # 2026-05-06
```

`1.0.41` 을 쓰고 있다면 여전히 abort 합니다. 제가 처음 테스트한 `03a00a1` 과 수정 커밋
사이는 60 커밋입니다.

**② CVE 는 없습니다.** 저는 [#2750](https://github.com/WebAssembly/wabt/issues/2750)(같은
캠페인에서 나온 WAT 파서 어서션)에 GitHub Security Advisory 발행을 요청했지만 답이 없었습니다.
받아들여지지도, 거절되지도 않았습니다. 다만 wabt 의 입장은 2023년 `SECURITY.md` 논의에
이미 공개돼 있습니다.

> we have a lot of open CVE's from clusterfuzz and other places and our approach today is to
> pretty much ignore them. This is because wabt is mostly used on trusted inputs.
> — sbc100, 2023

wabt 의 `SECURITY.md` 는 지금도 **비공개 제보가 아니라 공개 이슈**로 보내라고 안내합니다.
"신뢰할 수 있는 입력에만 쓰인다"는 전제에서는 저 판단이 이상하지 않습니다. 대신 그 전제가
깨지는 곳(웹 변환기, CI, 사용자 업로드를 받는 파이프라인)에서는 **툴체인을 쓰는 쪽이 프로세스
경계로 막아야 한다**는 뜻이기도 합니다.

CVE 가 붙은 선례를 봐도 방향은 비슷합니다. wabt 의 같은 계열 어서션 실패인 CVE-2025-6273
(`LogOpcode`, ~1.0.37)은 CVSS 3.1 기준 **3.3 LOW** 로 매겨졌고, NVD 에서 **DISPUTED** 로
표시돼 있습니다. 유지보수 쪽 코멘트는 "실제 wasm 프로그램에는 영향이 없을 수 있다"는
취지입니다. 이 클래스에 높은 점수를 기대하고 들어가면 어긋납니다.

덧붙이면 제 이슈도 완전히 정확하진 않았습니다. 저는 이걸 CWE-617(Reachable Assertion)로
적었는데, 이 자리는 `assert()` 가 아니라 조건 없이 `abort()` 하는 매크로입니다. 분류를
느슨하게 붙인 셈이고, 다행히 그 라벨이 아니라 **재현 절차와 실패 방식**이 논의를 끌고
갔습니다.

**③ #2750 은 아직 열려 있습니다.** 흥미롭게도 같은 기여자가 이쪽도 고쳐서
[PR #2809](https://github.com/WebAssembly/wabt/pull/2809) 를 올렸는데, 1년 넘게 진행 중인
GC 타입 시스템 대규모 패치셋([#2607](https://github.com/WebAssembly/wabt/pull/2607) 등)과
겹친다는 이유로 머지되지 않고 닫혔습니다.

> There is a GC patchset which reworks the whole codebase. (…) — zherczeg
>
> Yeah, I guess it makes sense to wait on the larger patchset. — sbc100

**같은 사람이 비슷한 시기에 비슷한 크기의 패치를 두 개 냈는데 하나는 머지되고 하나는
닫혔습니다.** 차이는 패치 품질이 아니라 **그 코드가 재작성 예정 구역인가**였습니다. 제보가
코드로 바뀌는 데는 코드 외적인 변수가 섞이고, 그건 제보자가 통제할 수 있는 게 아닙니다.

**④ 같은 매크로가 아직 한 자리 남아 있습니다.** 수정된 main 에서 `UNIMPLEMENTED(` 를
다시 세어 보면 정의 한 줄과 호출 한 곳이 남습니다.

```console
$ grep -n "UNIMPLEMENTED(" src/c-writer.cc
40:#define UNIMPLEMENTED(x) printf("unimplemented: %s\n", (x)), abort()
4373:        UNIMPLEMENTED("...");
```

4373번은 `AtomicWait` / `AtomicNotify` / `CallRef` / `ReturnCallRef` / `Quaternary` 를 받는
`switch` 분기입니다. `CallRef` 계열은 기능 게이트가 먼저 막아서 도달할 수 없지만,
**atomics 는 wasm2c 가 지원 목록에 넣어 둔 기능**입니다. 게이트를 통과합니다.

```console
$ cat wait.wat
(module
  (memory 1 1 shared)
  (func (export "w") (result i32)
    (memory.atomic.wait32 (i32.const 0) (i32.const 0) (i64.const -1))))

$ wat2wasm --enable-threads wait.wat -o wait.wasm    # 48바이트 유효 모듈
$ wasm2c --enable-threads wait.wasm -o wait.c
unimplemented: ...
rc=134
```

`memory.atomic.wait32` / `wait64` / `memory.atomic.notify` 세 개가 이렇게 죽습니다. 같은
shared 메모리에서 `i32.atomic.load`, `i32.atomic.rmw.add`, `atomic.fence` 는 정상 생성됩니다.

기능이 없는 것 자체는 **알려진 계획**입니다. atomics 지원은
[#2233](https://github.com/WebAssembly/wabt/pull/2233) 에서 (1) 로드·스토어·RMW 와 (2) 펜스를
먼저 넣고 (3) wait/notify 는 나중으로 미룬다고 적어 두었습니다. 그러니 이건 "구현해 달라"가
아닙니다. 남은 건 **미구현을 알리는 방식**이고, 그건 방금 #2751 에서 고친 것과 정확히 같은
문제입니다 — 게다가 메시지가 말줄임표 세 개라, 버퍼링을 꺼도 아무 정보가 없습니다.

---

## 정리

제보 하나가 코드로 바뀌는 데 78일이 걸렸고, 그 사이에 제가 한 일은 **첫 답장에서 요구를
줄인 것**뿐입니다.

- 메인테이너가 "그건 지원 대상이 아니다"라고 하면, 그 판단에 반대할 필요가 없을 때가 많습니다.
  받아들여야 하는 건 모듈이 아니라 **입력이 잘못됐을 때 죽지 않는 것**입니다.
- "크래시가 났다"와 "버그가 있다" 사이는 도달성이 잇습니다. 도구가 코드 생성 전에 거르는
  기능이면, 하네스가 만든 크래시는 공격 표면에 없습니다.
- 계측이 들어갔는지 재는 절차 없이 퍼저를 돌리면, 아무 말 없이 몇 시간을 헛돌 수 있습니다.
- 그리고 수정이 머지됐다고 그 클래스가 사라진 건 아닙니다. 같은 파일에 같은 매크로가
  한 자리 남아 있고, 거기는 아직 `rc=134` 입니다.

패치를 써서 머지시킨 건 ANAMASGARD 님이고, 리뷰와 머지는 sbc100·shravanrn 이 했습니다.
제 몫은 재현 가능한 이슈 하나와, 그 이슈를 고칠 수 있는 크기로 줄인 답장 하나였습니다.
