---
layout: post
title: "보안 패치 회귀 검증"
date: 2027-01-13 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 패치검증, 회귀테스트, 퍼징, OSSFuzz]
excerpt: "패치 빌드에서 PoC가 안 터졌다고 곧 '수정됨'이 아니다. 결정론적으로 재현되는 최소 입력과, 기능이 안 깨졌다는 반대편 증거까지 있어야 검증이 끝난다. 그리고 그 입력은 CI에 영구히 박아 재도입을 막는다."
---

보안 패치는 한 번 머지됐다고 끝이 아니다. 백포트가 원본과 어긋나고, 다른 브랜치로 체리픽하다 한 갈래를 빠뜨리고, 리팩터링 한 번에 조용히 되살아난다. 그래서 취약점 연구의 마지막 절반은 "패치가 실제로 그 버그를 막는가"와 "패치가 다른 걸 깨지 않는가"를 각각 증거로 확인하는 일이다. 이걸 건너뛰면 "고쳤다고 믿는데 안 고쳐진" 상태로 남는다.

이 글은 이미 패치된 공개 CVE와 자작 하네스로, 보안 패치의 회귀 검증 절차 — 취약/패치 빌드 대조, 최소 입력의 영구 고정, 그리고 어느 빌드 구성에서 검증해야 하는지 — 를 실습한 기록이다. 무기화가 아니라 "수정됐음을 증명하는" 방향의 작업이다.

> **한 줄 결론**: 회귀 검증은 **양성**(패치 빌드에서 같은 최소 입력이 더는 안 터짐)과 **음성**(기존 기능·코퍼스가 안 깨짐) 두 방향을 모두 채워야 하고, 그 크래시 입력을 CI 테스트로 박아 넣어야 재도입을 자동으로 잡는다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 것은 세 가지다. (1) 취약 빌드 vs 패치 빌드에서 동일 입력을 돌려 수정 여부를 대조하는 법, (2) 크래시 입력을 최소화·결정론화해 영구 회귀 테스트로 고정하는 법, (3) `git bisect run`으로 어느 커밋이 실제로 고쳤는지 기계적으로 짚는 법. 안 다루는 것: 미공개 취약점 무기화, 실서비스·실기기 대상 재현, 완성형 익스플로잇.

선수로 몇 가지가 깔린다. 커밋 계보와 `git blame`(2부 2장), 시큐리티 불리틴이 어느 AOSP 커밋을 가리키는지(3부 3장 성격의 patch provenance), 크래시 중복 제거와 최소화(같은 파트 9장), 새니타이저 기반 네이티브 재현(같은 파트 10장), 코퍼스·커버리지 관리(같은 파트 8장). 불완전 수정이 왜 생기는지는 sibling variant hunting(같은 파트 17장)과 맞물린다. 여기 나오는 명령은 전부 그 위에서 돈다.

전체 구조에서 이 장은 **연구 루프의 닫는 고리**다. 표면을 찾고(5장 성격) 하네스로 터뜨리고(7장) 크래시를 정리(9장)한 뒤, 그것이 정말 고쳐졌는지, 고친 게 다른 걸 깨지 않았는지를 여기서 증거로 닫는다.

## 핵심 개념 — 회귀 검증의 세 축

"회귀 검증 = 패치 후 안 터지는지 보는 것"으로 좁게 잡으면 절반을 놓친다. 실제로는 서로 다른 세 질문이다.

| 축 | 질문 | 증거 | 빠뜨렸을 때 증상 |
|--|--|--|--|
| **양성**(fix 검증) | 패치가 그 버그를 실제로 막나 | 취약 빌드=크래시, 패치 빌드=통과 (같은 최소 입력) | 불완전 수정이 살아있음 |
| **음성**(회귀 검증) | 패치가 다른 걸 깨지 않나 | 기능 테스트·코퍼스 재실행이 green | 새 크래시·기능 파손 |
| **고정**(regression pin) | 재도입을 자동으로 잡나 | 크래시 입력이 CI 테스트로 상주 | 조용한 재발 |

OSS-Fuzz가 이 모델의 교과서다. 크래시가 나면 재현용 testcase를 저장하고, 이후 매 빌드에서 그 입력을 다시 돌려 "여전히 안 터짐"을 확인한다 — 즉 크래시 하나하나가 영구 회귀 테스트가 된다. Android 쪽에도 같은 사상이 있다. AOSP의 `cts/hostsidetests/securitybulletin` 아래에는 공개 CVE별 PoC 테스트가 들어 있어, 기기가 해당 패치를 실제로 갖췄는지(=그 입력에 안 터지는지)를 CTS로 검사한다. `Source-confirmed`

여기서 흔한 착각 — "패치 빌드에서 안 터졌다"는 양성 검증의 **필요조건일 뿐**이다. 최소화·결정론화되지 않은 PoC는 힙 배치·ASLR·타이밍 때문에 우연히 안 터졌을 수 있다. 그래서 최소 입력의 결정론적 재현(9장)이 검증의 전제다. `Inferred`

> **[그림 1]** 취약(패치 직전) 빌드에서 자작 하네스로 이미 패치된 공개 CVE의 최소 입력을 돌려 AddressSanitizer가 크래시를 리포트한 터미널 — before 기준선 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

대상은 **이미 패치된 공개 CVE**와 **자작 하네스**, 오픈소스 트리뿐이다. 필자는 wabt(WebAssembly Binary Toolkit)·libsoup처럼 소스가 공개되고 패치 계보가 투명한 프로젝트를 검증 대상으로 쓴다. 실서비스·제3자 앱·실기기 flashing은 없다. Android 측 대조는 로컬 에뮬레이터(AVD) 또는 baseline/patched 이미지 두 벌로만 한다. PoC는 원리 이해용 최소 개념 수준이며, 목표는 "터뜨리기"가 아니라 "고쳐졌음을 증명하기"다.

## 실습 절차와 관측

### 가설
- **가설 A** — 같은 최소 입력이 취약 빌드에선 새니타이저 크래시를, 패치 빌드에선 정상 종료(exit 0)를 낸다. `Inferred`
- **가설 B** — `git bisect run`에 "크래시=실패 / 통과=성공" 스크립트를 물리면, 실제로 고친 커밋을 사람 개입 없이 짚어낸다. `Inferred`

### 절차
1. 하네스를 새니타이저+libFuzzer로 빌드한다.
2. 패치 직전 커밋에서 최소 입력을 단일 재실행해 크래시(before)를 기록한다.
3. 패치 커밋에서 같은 입력을 재실행해 통과(after)를 기록한다.
4. 그 입력을 `regress/` 코퍼스에 넣고 전체를 재실행해 음성 검증을 건다.
5. `git bisect run`으로 실제 fix 커밋을 기계적으로 확정한다.

```bash
# (before) 패치 직전 커밋 — 체크아웃 후 하네스를 재빌드해 같은 최소 입력을 단일 재실행
git checkout <vuln_commit^>
clang -g -O1 -fsanitize=address,fuzzer harness.c -o fuzz_target   # 새니타이저 + libFuzzer main
./fuzz_target crash_min        # 크래시면 nonzero, ASan 리포트

# (after) 패치 커밋
git checkout <fix_commit>
clang -g -O1 -fsanitize=address,fuzzer harness.c -o fuzz_target
./fuzz_target crash_min        # 통과면 exit 0

# 음성 검증 — 축적된 크래시 입력 전체 재실행
for f in regress/crash-*; do ./fuzz_target "$f" || echo "STILL CRASHES: $f"; done
```

fix 커밋을 눈대중으로 고르지 말고 `git bisect run`으로 확정한다. 커스텀 용어로 "고침/터짐"을 그대로 쓸 수 있다.

```bash
# repro.sh: exit 0 = crashes(old, 터짐), 비영 = fixed(new, 안 터짐), 125 = skip(빌드 실패)
cat > repro.sh <<'EOF'
#!/bin/sh
clang -g -O1 -fsanitize=address,fuzzer harness.c -o /tmp/ft || exit 125
/tmp/ft crash_min && exit 1
exit 0
EOF
chmod +x repro.sh

git bisect start --term-old=crashes --term-new=fixed
git bisect fixed   <known_patched_tag>
git bisect crashes <known_vuln_tag>
git bisect run ./repro.sh      # 첫 fixed 커밋 = 실제 수정 지점
```

Android 이미지 대조는 baseline/patched 두 벌에 같은 PoC를 밀어 exit 코드와 tombstone 유무를 본다.

```bash
adb push poc /data/local/tmp/poc && adb shell chmod 755 /data/local/tmp/poc
adb shell /data/local/tmp/poc; echo "exit=$?"
adb logcat -d -b crash | tail   # 취약 빌드면 DEBUG/tombstone, 패치 빌드면 조용함
```

> **[그림 2]** 동일 최소 입력을 패치 빌드에서 재실행해 exit 0으로 통과하고, 그 입력을 `regress/`에 넣어 코퍼스 전체가 크래시 없이 재실행되는 터미널 — after + 영구 회귀 고정 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — 아래는 실제 실행으로 갈아끼운다:

```
# 취약 빌드
$ ./fuzz_target crash_min
Running: crash_min
==12345==ERROR: AddressSanitizer: heap-buffer-overflow ...
    #0 parse_section harness.c:88

# 패치 빌드 — 같은 입력
$ ./fuzz_target crash_min
Running: crash_min
Executed crash_min in 2 ms
$ echo $?
0

# 회귀 코퍼스 재실행
$ for f in regress/crash-*; do ./fuzz_target "$f" || echo FAIL $f; done
$    # (FAIL 출력 없음 = 음성 검증 통과)
```

세 줄이 다 맞아야 검증이 닫힌다: before에 ASan 리포트가 있고, after가 exit 0이며, 코퍼스 재실행이 조용하다. 하나라도 비면 아직 "고쳐졌다"고 말할 수 없다.

## Root Cause — 왜 이렇게 되는가

불완전 수정과 조용한 재발은 네 갈래에서 온다.

- **백포트 드리프트.** 메인라인 수정이 세 군데를 건드렸는데 LTS·벤더 브랜치엔 한두 군데만 적용되면, 안 고쳐진 sibling 경로가 남는다(17장). 텍스트 diff는 깨끗이 적용돼도 갈라진 트리에선 의미가 어긋날 수 있다(semantic patch 성격).
- **비결정론.** 힙 레이아웃·ASLR·경쟁 조건 때문에 같은 입력이 어떤 실행에선 안 터진다. 최소화·결정론화(9장)를 안 거친 PoC로 "패치 빌드 통과"를 선언하면 우연을 증거로 착각한다.
- **빌드 구성 의존.** `assert` 하나로 막는 가드는 `NDEBUG`가 정의된 릴리스 빌드에서 제거되기도 한다. 필자가 본 tinyobjloader의 `parseLine` 스택 OOB write는 `NDEBUG` 환경에서 ASan으로만 드러났다. `Reported` 디버그/새니타이저 빌드에서만 검증하고 릴리스 구성을 안 보면, 반대 구성에서 결론이 뒤집힌다.
- **표면 재도입.** 리팩터링·기능 추가가 같은 파서 경로를 다시 열어도, 회귀 테스트가 CI에 없으면 아무도 모른다. 그래서 "고정" 축이 별개로 필요하다.

핵심은 이렇다. 패치는 코드의 한 상태에 대한 주장이고, 트리는 계속 움직인다. 그 주장을 **움직이는 트리 위에서 계속 참으로 유지**하는 유일한 방법이 코퍼스에 박힌 회귀 입력이다.

## 버전 차이와 한계

- **OSS-Fuzz vs 로컬.** OSS-Fuzz는 재현 파일 저장·재실행을 자동화한다. 로컬에선 그 규율(크래시 입력을 반드시 `regress/`에 커밋)을 사람이 지켜야 한다. 규율이 없으면 "고정" 축이 통째로 빈다.
- **새니타이저 빌드 vs 릴리스.** ASan/UBSan/HWASan이 잡는 걸 릴리스는 조용히 넘긴다. 위협 모델에 맞는 구성에서 검증하고, 무엇보다 **크래시=취약점이 아님**을 기억해야 한다. 필자가 GNOME에 제보한 libsoup Range 정수 오버플로는 `assert` DoS였고, IrfanView `Dpx.dll` 케이스는 무한 루프 DoS(CWE-835)였다 — 둘 다 DoS이지 RCE가 아니다. `Reported` 회귀 검증 보고서에서 DoS를 메모리 손상으로 부풀리면 그 자체가 오류다.
- **완결 시점의 차이.** 필자가 wabt에 제보한 크래시(#2751 계열)는 약 두 달여 만에 수정 머지됐고, 그 수정 커밋에 붙은 회귀 테스트는 제보 당시의 최소화된 PoC 입력 그대로였다. 반대로 함께 제보한 다른 크래시는 여전히 Open이다. `Reported` 즉 "제보 = 수정 = 회귀 등록"이 한 박자에 끝나지 않는다. 정확한 커밋 해시·일수는 원문 재확인이 필요하다.
- **Android STS/CTS의 범위.** `cts/hostsidetests/securitybulletin`은 공개 CVE의 패치 **존재**를 검사하지만, 새 회귀의 **부재**까지 보장하진 않는다. 벤더 포크는 SPL 표기와 실제 코드가 어긋나기도 해(patch-gap, 15장), 이미지 대조는 SPL을 믿지 말고 코드/동작으로 확인한다.

## 정리

- 회귀 검증은 양성(패치 빌드에서 최소 입력이 안 터짐)·음성(기능·코퍼스가 안 깨짐)·고정(입력을 CI에 상주)의 세 축을 전부 채워야 닫힌다.
- "패치 빌드에서 안 터짐"은 필요조건일 뿐 — 결정론적 최소 입력이 없으면 우연을 증거로 착각한다.
- `git bisect run`으로 실제 fix 커밋을 기계적으로 확정하고, 어느 빌드 구성에서 검증했는지(디버그/릴리스, 새니타이저 유무)를 항상 기록한다.
- DoS는 DoS로, OOB write는 OOB write로 — 검증 보고에서 심각도를 부풀리지 않는다.

**점검 질문** — (1) 패치 빌드에서 PoC가 안 터졌다. 이것만으로 "수정됨"이라 못 하는 이유 두 가지는? (2) `git bisect run` 스크립트의 exit 코드 0/1/125는 각각 무엇을 뜻하나? (3) `assert` 기반 가드가 릴리스 빌드에서 검증되지 않는 이유는?

**참고** — [OSS-Fuzz](https://google.github.io/oss-fuzz/) · [libFuzzer](https://llvm.org/docs/LibFuzzer.html) · [git bisect run](https://git-scm.com/docs/git-bisect) · [AOSP CTS](https://source.android.com/docs/compatibility/cts) · [Android Security Bulletins](https://source.android.com/docs/security/bulletin)

*다음 글: [새 완화기법 평가](/posts/android-vulnresearch-p4c19/).*
