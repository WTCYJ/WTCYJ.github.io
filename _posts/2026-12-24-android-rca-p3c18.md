---
layout: post
title: "regression으로 되살아난 취약점"
date: 2026-12-24 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, regression, 회귀버그, git-bisect, 패치검증]
excerpt: "'패치가 있다 = 안전하다'가 아니다. 나중 커밋이 조용히 가드를 되돌리면 같은 취약점이 되살아난다 — `Fixes:` 태그나 불리틴 문구가 있어도 그 수정이 지금 트리에 남아 있다는 보장은 없다."
---

취약점은 한 번 고치면 끝이라고 생각하기 쉽다. 그런데 실무에서 반복적으로 되돌아오는 부류가 있다 — 한때 완전히 막혔던 결함이 나중 변경으로 **되살아난** 것. revert 한 번, 리팩터 중 가드 한 줄 누락, 지원 브랜치 하나에 백포트 빠짐. 그러면 예전 PoC가 최신 빌드에서 그대로 다시 통한다. 더 나쁜 건 "이미 고쳤다"고 믿어 아무도 그 코드를 다시 보지 않는다는 점이다. 이 글은 이 **회귀(regression)** 를 증상/트리거/폴트사이트/근본원인으로 분해하고, `git bisect`와 pickaxe로 "언제·어느 커밋에서 수정이 사라졌는지"를 특정하는 방법을 자작 회귀 랩으로 정리한 기록이다.

안전 범위는 앞 장들과 같다. 자작 결함 프로그램·자작 git 저장소·에뮬레이터(AVD)·Cuttlefish·이미 공개되고 패치된 사례의 히스토리 열람만 다루고, 재도입 커밋이라는 프리미티브의 위치를 특정하는 데서 멈춘다. 무기화·실서비스 공격은 하지 않는다.

> **한 줄 결론**: 회귀 RCA의 핵심 산출물은 크래시 주소가 아니라 **수정을 되돌린 그 "재도입 커밋(reintroducing commit)"** 이다. "옛 PoC가 다시 통함"만으로는 부족하고, 수정이 있었다가 사라진 증거를 커밋으로 짚어야 회귀라고 부를 수 있다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 scope는 세 가지다. (1) 회귀를 불완전 패치·variant와 명확히 구분하는 틀, (2) `git bisect`로 재도입 커밋을 자동 이분 탐색하고 pickaxe(`git log -S`)로 가드의 생몰을 직접 확인하는 절차, (3) 회귀의 영향을 정직하게 산정하는 경계 — 회귀는 원래 결함의 등급을 그대로 복원할 뿐, 크래시를 원래 이상으로 부풀리지 않는다.

선수 지식이 밑에 깔린다. 이 파트 1장의 증상/트리거/폴트사이트/근본원인 4요소, 16장의 patch diff·Patch Invariant(무엇을 지켜야 패치가 성립하는가), 17장의 불완전 패치·variant analysis를 그대로 쓴다. 실습은 1부에서 세운 계측 환경(clang·ASan)을 재사용한다. git 쪽으로는 `bisect`의 good/bad 이분 탐색과 `-S`/`-L` 히스토리 검색을 안다는 전제다.

전체 구조에서 이 장은 3부 RCA의 "패치 검증" 묶음(16장 patch diff, 17장 variant, 18장 regression)의 마지막 조각이다. 셋은 겉보기에 비슷하지만 요구하는 산출물이 다르다 — 불완전 패치는 "남은 트리거", variant는 "패치 안 된 형제 경로", regression은 "수정을 되돌린 커밋". 여기서 그 셋을 가르는 법을 정리한다.

## 핵심 개념 — 세 가지를 혼동하지 말 것

먼저 회귀를 이웃 개념과 구분한다. 이 표 하나가 이 글의 절반이다.

| 클래스 | 무엇이 문제인가 | RCA 산출물 |
|--|--|--|
| 불완전 패치 | 패치가 결함의 일부만 막아 다른 조건으로 여전히 트리거 | 패치가 놓친 나머지 입력·경로 |
| variant | 같은 버그 패턴의 **형제 코드 경로가 애초에 패치 안 됨**(다른 함수/파일) | 패치되지 않은 쌍둥이 위치 |
| **regression(회귀)** | **한때 완전히 막힌 결함이 나중 변경으로 재도입됨** | 수정을 되돌린 **재도입 커밋** |

핵심 차이는 시간축이다. 불완전 패치·variant는 "애초에 다 안 막았다"이고, 회귀는 "다 막았었는데 다시 뚫렸다"이다. 그래서 회귀는 유일하게 히스토리에서 **수정이 존재했던 구간**을 증거로 요구한다. `Inferred`

회귀가 생기는 메커니즘도 몇 가지로 수렴한다.

| 유형 | 어떻게 되살아나나 | 전형 |
|--|--|--|
| revert | 수정 커밋이 명시적으로 되돌려짐(성능·다른 회귀 이유) | `Fixes:` 커밋이 나중에 `Revert` 됨 |
| refactor drop | 코드 이동·재작성 중 가드가 조용히 누락 | 함수 분리하며 bounds check를 안 옮김 |
| merge 해소 오류 | 충돌 해소에서 수정 아닌 쪽을 채택 | 3-way merge에서 옛 코드 선택 |
| 백포트 누락 | 한 브랜치엔 들어갔지만 다른 지원 브랜치/LTS엔 빠짐 | Android 버전·커널 LTS 간 불일치 |
| cherry-pick 부분누락 | 수정이 여러 커밋인데 일부만 집음 | 후속 hardening 커밋 하나 누락 |
| flag/config 회귀 | 완화가 기본값·플래그로 꺼짐 | 빌드 옵션 바뀌며 가드 비활성 |

Android에서 가장 흔한 회귀 원천은 **백포트 누락과 브랜치 간 불일치**다. 하나의 수정이 여러 지원 버전·커널 브랜치로 나뉘어 반영되기 때문에, 한 곳엔 들어가고 다른 곳엔 빠지거나 revert되는 일이 구조적으로 생긴다. 보안 불리틴이 CVE마다 "영향받는 버전"과 패치 링크를 따로 표기하는 것도 이 분산 반영 모델 때문이다. `Source-confirmed` 그리고 실무 함정 하나 — 불리틴 문구나 `Fixes:` 태그의 존재가 지금 내가 보는 그 브랜치 트리에 수정이 남아 있음을 보장하지 않는다. 반드시 대상 브랜치의 실제 커밋으로 확인해야 한다. `Reported`

> **[그림 1]** 자작 회귀 랩의 `git log --oneline`에서 도입(A)·수정(B)·재도입(C) 세 커밋을, 옆에 `git log -S '<가드 문자열>'`가 가드를 추가한 B와 제거한 C만 집어낸 출력을 나란히 놓은 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 자작 git 저장소와 자작 결함 C 프로그램으로만 진행한다. 세 커밋짜리 히스토리를 손으로 만들어 회귀를 재현하고, `git bisect run`으로 재도입 커밋을 자동으로 찾은 뒤 pickaxe로 교차 확인한다. 빌드·검증은 1부에서 세운 clang+ASan을 그대로 쓴다(호스트/WSL clang이면 그대로 재현). 제3자 저장소·실서비스·실데이터는 건드리지 않고, 공개 CVE는 히스토리 열람 용도로만 참고한다.

## 실습 절차와 관측

### 가설

- **가설 A** — 도입(A)→수정(B)→리팩터(C) 히스토리에서, `good`을 수정이 검증된 B로 `bad`를 HEAD로 두면 `git bisect run`이 가드를 떨어뜨린 C를 first bad commit으로 정확히 지목한다. `Inferred`
- **가설 B** — `git log -S '<가드 문자열>'`는 그 문자열이 등장한 커밋(B)과 사라진 커밋(C)을 함께 집어내, bisect 결과를 히스토리로 교차 확인해 준다. `Inferred`

### 절차

1. 아래 `parse.c`(가드가 유실된 HEAD 상태)와 3-커밋 히스토리를 만든다.
2. good/bad를 잡고 `git bisect run`으로 재도입 커밋을 찾는다.
3. `git log -S`로 가드 문자열의 생몰을 대조 확인한다.

```c
/* parse.c — 자작 회귀 랩 (원리 이해용, HEAD=C 상태) */
#include <string.h>
static char buf[16];
static int copy_in(const char *src, unsigned long len) {
    /* B에서 추가됐던 가드:  if (len > sizeof(buf)) return -1;
       C의 refactor에서 이 한 줄이 조용히 누락됨 → 옛 OOB write 부활 */
    memcpy(buf, src, len);      /* len > 16 이면 전역(global) 경계 밖 write (ASan: global-buffer-overflow) */
    return 0;
}
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    return copy_in(argv[1], strlen(argv[1]));  /* 폴트사이트는 예전과 동일 */
}
```

```bash
# 판정 스크립트: ASan이 OOB를 발화하면 bad, 아니면(가드 생존으로 정상 거부된 경우 포함) good
# ※ exit code로 가르면 안 된다 — 가드가 살아있으면 copy_in이 -1을 반환해 프로세스가 exit 255가 되므로,
#   100바이트 오버사이즈 입력에선 가드-생존 경로가 절대 exit 0에 닿지 못해 '정상 거부'와 'ASan 크래시'를 exit code로 구분할 수 없다.
cat > regress_test.sh <<'EOF'
#!/bin/sh
clang -fsanitize=address -g -O0 parse.c -o /tmp/parse 2>/dev/null || exit 125  # 빌드실패=skip
out=$(/tmp/parse "$(printf 'A%.0s' $(seq 1 100))" 2>&1)   # 100바이트 > buf[16]
echo "$out" | grep -q 'AddressSanitizer' && exit 1 || exit 0   # ASan 발화=bad, 아니면 good
EOF
chmod +x regress_test.sh

# 이분 탐색: good 앵커는 '수정이 검증된' B여야 한다(취약한 A를 good으로 두면 good 전제가 깨져 결과를 신뢰할 수 없다)
git bisect start
git bisect bad  HEAD                 # 최신에서 결함 부활
git bisect good <B의_커밋해시>        # 수정이 살아있던 지점
git bisect run ./regress_test.sh     # → first bad commit = 재도입 커밋(C)
git bisect reset

# 교차 확인: 가드 문자열이 언제 생기고 사라졌나 (pickaxe)
git log -S 'len > sizeof(buf)' --oneline
git log -L :copy_in:parse.c          # copy_in 본문의 변경 이력만 추적
```

> **[그림 2]** `git bisect run ./regress_test.sh`가 재도입 커밋(C)을 "is the first bad commit"으로 지목한 최종 출력과, 그 커밋 메시지·diff가 함께 보이는 터미널 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
$ git bisect run ./regress_test.sh
running ./regress_test.sh
Bisecting: 0 revisions left to test after this (roughly 0 steps)
<hash_C> is the first bad commit
    refactor: split copy_in / validate            <- 이 커밋에서 가드가 누락됨
 parse.c | 4 +---
bisect found first bad commit

$ git log -S 'len > sizeof(buf)' --oneline
<hash_C> refactor: split copy_in / validate       <- 여기서 가드 문자열 사라짐
<hash_B> fix: reject oversized input              <- 여기서 가드 문자열 등장
```

읽는 순서가 곧 회귀 RCA다. bisect가 준 `<hash_C>`가 **재도입 커밋** = root cause 후보이고, pickaxe가 준 두 줄(B에서 등장, C에서 소멸)이 "수정이 존재했던 구간"이라는 결정적 증거다. 이 두 조각이 다 있어야 회귀라고 단정한다. `Source-confirmed` `git bisect run`은 스크립트 exit code로 판정한다는 점을 기억하라 — 0이면 good, 1~127(단 125 제외)이면 bad, **125면 skip**(테스트 불가), 128 이상이면 bisect 자체가 중단된다(abort). 빌드가 깨지는 중간 커밋을 skip 처리하지 않으면 이분 탐색이 엉뚱한 커밋을 지목한다. `Source-confirmed`

## Root Cause — 왜 이렇게 되는가

회귀에서 폴트사이트(크래시 라인)는 예전 CVE와 **똑같다**. 그래서 폴트사이트를 root cause로 적으면 "옛날에 이미 고친 그 줄"이라는 동어반복이 된다. 진짜 root cause는 시간축 위에 있다 — **가드를 되돌린 그 변경**. 그 변경이 revert인지, 리팩터 중 누락인지, merge 해소 실수인지, 백포트 빠짐인지가 root cause의 실제 내용이고, 재발 방지책도 거기서 갈린다(revert면 "왜 되돌렸나"를, 백포트 누락이면 "브랜치 매트릭스"를 손대야 한다).

여기서 회귀를 오판하는 세 가지 함정이 있다. 첫째, **good 앵커를 잘못 잡는 것**. 히스토리가 취약(A)→수정(B)→재도입(C)이면 good→bad 전이가 하나가 아니다. 실제로 취약한 A를 good이라 거짓 표시하면 bisect의 good 전제(precondition — "이 지점엔 결함이 없다")가 깨져 결과를 신뢰할 수 없다. 특히 A~B 구간에 취약 중간 커밋이 여럿인 더 긴 히스토리에선 테스트 중점이 그 구간에 떨어질 때 A~B 사이 커밋을 first-bad로 잘못 지목한다. 반대로 이 글의 최소 3-커밋 예제에선 중간 커밋이 B 하나뿐이라 good=A로 둬도 결과가 우연히 C로 수렴하기도 하지만, 전제가 깨진 판정은 신뢰 근거가 못 된다. good은 반드시 "수정이 실제로 살아있었다"를 확인한 B로 잡아야 한다. `Source-confirmed` 둘째, **"옛 PoC가 최신 빌드에서 통함 = 회귀"라고 단정하는 것**. 그건 회귀일 수도, 애초에 그 브랜치에 백포트가 안 됐을 수도(=미적용), 형제 경로가 남은 variant일 수도 있다. 재도입 커밋을 못 찾으면 회귀가 아니라 다른 클래스다. `Inferred` 셋째, **`Fixes:` 태그를 수정 존재의 증거로 읽는 것**. 태그는 "이 커밋이 무엇을 고쳤다"는 주장일 뿐, 그 수정이 지금 트리에 남아 있다는 보장이 아니다. 나중에 revert됐을 수 있다. `Reported`

**영향은 정직하게, 원래 등급 그대로.** 회귀는 원래 결함의 프리미티브를 **복원**할 뿐이다 — 원래가 OOB write였으면 회귀도 OOB write, 원래가 DoS였으면 회귀도 DoS다. 더도 덜도 아니다. 다만 회귀에는 기술 등급과 별개로 운영상 위험이 얹힌다: (a) "이미 고쳤다"고 믿어 재심사·재테스트를 건너뛰고, (b) 과거에 은퇴시킨 탐지 시그니처가 더 이상 잡지 못한다. 이건 "심각도를 올린다"가 아니라 "노출 기간과 발견 지연을 키운다"로 적어야 정확하다. 크래시를 RCE로, DoS를 상향 등급으로 부풀리는 것과는 다른 축이다. `Inferred`

## 방어와 회귀 검증

- **회귀 테스트는 트리거를 CI에 박제한다.** 회귀의 특효약은 원래 취약점의 최소 PoC(6장)를 sanitizer 빌드로 만들어 CI에 상시 남기는 것이다. 누군가 revert·리팩터로 가드를 떨어뜨리면 그 순간 옛 크래시가 다시 떠 파이프라인이 빨개진다. "패치했다"가 아니라 "패치가 지금도 유효하다"를 매 빌드 검증하는 것 — 이게 16장 Patch Invariant를 시간축으로 연장한 것이다.
- **가드에 앵커 코멘트를 남긴다.** 리팩터 중 가드가 조용히 사라지는 걸 막으려면, 가드 옆에 "이 검사를 제거하면 <원래 CVE/버그ID>가 되살아난다"는 근거를 붙여 둔다. 리뷰어가 그 한 줄을 지울 때 최소한 멈칫하게 만든다.
- **백포트 매트릭스를 명시적으로 관리한다.** Android처럼 다수 브랜치·버전에 수정을 반영하는 구조에선, "어느 CVE가 어느 브랜치에 반영됐나"를 표로 추적해야 한다. 불리틴 문구가 아니라 각 대상 브랜치의 실제 커밋으로 확인한다. 불리틴은 개정 표기 없이 조용히 갱신되기도 하므로, 커밋 해시가 유일한 신뢰 근거다. `Reported`
- **bisect 친화적 히스토리를 유지한다.** 각 커밋이 빌드 가능해야(중간 커밋이 깨지면 `skip`으로 우회는 되지만 탐색이 흐려진다) 회귀 추적이 빠르다. 무기화된 재현이 아니라 "가드가 언제 사라졌나"를 찾는 데까지가 이 글의 경계다.

## 정리

- 회귀는 "애초에 다 안 막았다"(불완전 패치·variant)와 달리 "다 막았었는데 되살아났다"이다. 유일하게 히스토리에서 수정이 존재했던 구간을 증거로 요구한다.
- 회귀 RCA의 산출물은 크래시 주소가 아니라 재도입 커밋이다. `git bisect run`으로 찾고 `git log -S` pickaxe로 교차 확인한다. good 앵커는 수정이 검증된 커밋이어야 한다.
- 회귀는 원래 결함의 등급을 그대로 복원한다. 부풀리지 않되, "고쳤다고 믿어 재심사를 건너뛴다"는 노출 기간·발견 지연 위험은 별도로 적는다.
- 특효약은 원래 트리거를 sanitizer 빌드로 CI에 박제하는 회귀 테스트다 — 패치했음이 아니라 패치가 지금도 유효함을 매 빌드 검증한다.

**점검 질문** — (1) "옛 PoC가 최신 빌드에서 통한다"는 것만으로 regression이라 단정할 수 없는 이유와, 회귀로 확정하려면 추가로 무엇을 찾아야 하는가? (2) 취약(A)→수정(B)→재도입(C) 히스토리에서 `git bisect`의 good 앵커를 A로 두는 게 왜 위험한가 — good 전제 관점에서 설명하고, 이 최소 3-커밋 예제에선 왜 결과가 우연히 맞을 수 있는지, 어떤 히스토리 형태에서 실제로 엉뚱한 커밋을 지목하는지도 함께 답하라? (3) 회귀와 원래 취약점의 severity 관계는 무엇이며, 그럼에도 회귀에서 별도로 적어야 할 위험은?

**참고** — [git-bisect(1)](https://git-scm.com/docs/git-bisect) · [git-log -S/-L(pickaxe)](https://git-scm.com/docs/git-log) · [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [Linux "Fixes:" 태그(submitting-patches)](https://www.kernel.org/doc/html/latest/process/submitting-patches.html)

*다음 글: [증거 등급·Confidence](/posts/android-rca-p3c19/).*
