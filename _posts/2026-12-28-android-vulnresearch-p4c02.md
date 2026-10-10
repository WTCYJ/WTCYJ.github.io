---
layout: post
title: "git log/blame/tag·패치 계보"
date: 2026-12-28 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, AOSP, git, 패치분석, 취약점연구]
excerpt: "git blame이 가리키는 커밋은 취약점을 넣은 커밋이 아니라 그 줄을 마지막으로 건드린 커밋이다. 도입 시점은 blame이 아니라 픽액스(-S/-G)로, 릴리스 포함 여부는 --contains로 확인한다."
---

Android 보안 불리틴은 CVE 옆에 AOSP 커밋 링크 하나를 붙여준다. 초심자는 그 커밋을 열어 diff만 보고 끝낸다. 하지만 연구 관점에서 그 커밋은 출발점이 아니라 **한 점**일 뿐이다. 언제 이 버그가 들어왔고(도입 커밋), 어떤 릴리스가 이 수정을 담고 있으며(태그·브랜치), 재발을 막는 회귀 테스트가 무엇인지는 전부 git 히스토리를 되짚어야 나온다. 이걸 못 하면 "패치됐다"는 사실만 손에 쥔 채, 그 버그의 계보와 아직 안 고쳐진 형제 변종(4부 뒤 장의 sibling variant hunting)을 통째로 놓친다.

이 글은 AOSP 미러 같은 공개 소스에서 `git log`·`git blame`·`git tag`/`git branch --contains`로 **이미 패치된 공개 CVE의 패치 계보**를 되짚는 워크플로를 실습·정리한 기록이다. 무기화는 없다. 대상은 공개 소스와 이미 공개된 수정 커밋뿐이다.

> **한 줄 결론**: `git blame`이 가리키는 커밋은 "이 줄을 마지막으로 건드린" 커밋이지 "취약점을 넣은" 커밋이 아니다. 도입 시점은 blame이 아니라 `-S`/`-G` 픽액스로, 릴리스 포함 여부는 `--contains`로 따로 확인해야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 하나의 수정 커밋 해시에서 출발해 (1) 버그가 들어온 도입 커밋, (2) 그 수정이 담긴 릴리스 태그·브랜치, (3) 함께 추가된 회귀 테스트까지 git 명령만으로 복원하는 절차를 다룬다. 다루지 않는 것도 분명히 해두자. 불리틴 항목 자체를 해석하는 법(CVE→커밋 매핑, patch provenance)은 다음 장, 브랜치별 백포트 누락(patch-gap)의 정량 분석은 뒤의 15장에서 따로 판다. 여기서는 순수하게 **git 도구를 다루는 손기술**만 세운다.

선수 지식은 셋이다. git의 `log`/`show`/`diff`를 읽을 줄 알아야 하고, AOSP가 하나의 저장소가 아니라 `repo`로 묶인 수백 개 git 저장소(각 프로젝트가 독립 히스토리)라는 점을 알아야 하며, 앞 장에서 소스 트리를 받고 대상 프로젝트를 골라 둔 상태여야 한다. 4부(취약점 연구)의 흐름에서 이 장은 두 번째다. 앞 장이 "어느 트리를 볼 것인가"였다면, 이 장은 "그 트리의 시간축을 어떻게 읽는가"다.

## 핵심 개념 — git 히스토리를 심문하는 명령들

패치 계보 추적은 결국 아래 명령 몇 개의 조합이다. 각 명령이 대답하는 질문이 다르다는 게 핵심이다.

| 질문 | 명령 | 대답 |
|--|--|--|
| 이 파일을 누가 언제 바꿨나 | `git log --oneline -- <path>` | 파일을 건드린 커밋 목록 |
| 이 줄은 어느 커밋에서 왔나 | `git blame -w -C -M <file>` | 각 줄을 **마지막으로** 바꾼 커밋 |
| 이 코드가 처음 들어온 건 언제 | `git log -S'<코드 조각>' -- <path>` | 문자열 등장/삭제가 일어난 커밋(픽액스) |
| (정규식으로) 도입/제거 커밋 | `git log -G'<regex>' -- <path>` | diff가 정규식에 걸리는 커밋 |
| 이 함수의 변천사 | `git log -L :<func>:<file>` | 특정 함수/줄 범위의 변경 이력 |
| 이 수정이 담긴 릴리스는 | `git tag --contains <commit>` | 그 커밋을 조상으로 갖는 태그 |
| 이 수정이 담긴 브랜치는 | `git branch -r --contains <commit>` | 그 커밋을 담은 원격 브랜치 |
| 커밋 직후 첫 태그는 | `git describe --contains <commit>` | 계보상 가장 가까운 이후 태그 |

여기서 도구별 성격을 구분해야 한다. `git blame`은 **줄 → 최종 수정 커밋** 매핑이고, `git log -S`(픽액스)는 **문자열 등장/소멸 커밋**을 찾는다. blame은 "누가 이 줄을 지금 모습으로 만들었나"에 답하지 "누가 이 버그를 처음 심었나"에는 답하지 않는다. `-S`는 지정한 문자열의 **출현 횟수가 바뀐** 커밋만 골라내므로 도입 시점 추적에 정확하다. `Source-confirmed`

AOSP 플랫폼 커밋은 트레일러 관습이 고정돼 있다. `Bug:`(Buganizer 숫자 id, 보안 건은 대개 비공개), `Test:`(검증 방법), `Change-Id:`(Gerrit I-해시), 그리고 백포트면 `(cherry picked from commit ...)`. 여기서 흔한 오해 하나 — 커널 상류의 `Fixes:` 트레일러(도입 커밋을 명시)는 AOSP 플랫폼 코드엔 거의 없다. 그래서 "이 수정이 고친 원래 커밋"을 트레일러로 바로 못 읽고, 픽액스로 직접 캐야 한다. `Source-confirmed`

> **[그림 1]** AOSP 미러에서 `git show <fix-commit>`으로 한 수정 커밋의 `Bug:`/`Test:`/`Change-Id:` 트레일러와 diff를 함께 띄운 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **공개 소스와 이미 공개된 수정 커밋**만 다룬다. 대상은 로컬에 받아 둔 AOSP 미러(또는 `platform/frameworks/av` 같은 개별 프로젝트의 공개 미러)와, 내가 실제로 다뤄 본 공개 오픈소스 이슈다. 무기화된 PoC·비공개 취약점·실서비스 공격은 없다. `git blame`/`git log`는 읽기 전용 조회라 부작용이 없다는 점도 안전 측면의 실질 이점이다.

한 가지 환경 함정 — `--contains` 계열은 **완전한 히스토리**를 전제한다. `repo sync -c`(현재 브랜치만)나 shallow clone으로 받은 트리에서는 태그·조상 커밋이 잘려 있어 `git tag --contains`가 빈 결과나 틀린 결과를 준다. 계보를 볼 거면 얕게 받지 말아야 한다. `Inferred`

## 실습 절차와 관측

### 가설
- **가설 A** — 불리틴이 준 수정 커밋에서 `git blame`으로 취약 줄을 짚으면, blame이 가리키는 커밋과 `-S` 픽액스가 찾는 도입 커밋이 **서로 다르다**(중간에 리포맷·이동이 blame을 훔쳤다면). `Inferred`
- **가설 B** — 그 수정 커밋을 `git tag --contains`에 넣으면 담긴 릴리스 태그 목록이 나오고, `git branch -r --contains`로 어느 릴리스 브랜치에 반영됐는지 대조할 수 있다. `Inferred`

### 절차
1. 대상 프로젝트로 이동해 파일 이력을 훑는다.
2. 취약 줄을 `blame`으로 짚되 이동·공백을 무시하는 옵션을 붙인다.
3. 같은 코드 조각을 픽액스로 넣어 **도입 커밋**을 찾는다.
4. 수정 커밋을 `--contains`에 넣어 담긴 태그/브랜치를 뽑는다.
5. 수정 커밋의 diff에서 함께 추가된 **테스트 파일**을 확인한다.

```bash
# 0) 대상 프로젝트 (예: 미디어 파서 표면)
cd platform/frameworks/av

# 1) 파일 이력
git log --oneline -- media/libstagefright/FooExtractor.cpp

# 2) 줄 → 커밋 (공백 -w, 복사/이동 추적 -C -M 으로 blame 도둑질 완화)
git blame -w -C -M -- media/libstagefright/FooExtractor.cpp

# 3) 도입 커밋 (픽액스: 이 코드가 '처음 들어온' 커밋)
git log -S'uint8_t buf[n]' --oneline -- media/libstagefright/FooExtractor.cpp

# 4) 수정 커밋이 담긴 릴리스 태그 / 브랜치
git tag    --contains <fix-commit> | sort -V | head
git branch -r --contains <fix-commit>

# 5) 수정과 함께 들어온 회귀 테스트
git show <fix-commit> --stat | grep -i test
```

> **[그림 2]** `git log -S`(픽액스)로 취약 코드의 도입 커밋을, `git tag --contains`로 그 수정이 담긴 릴리스 태그 목록을 한 화면에서 대조한 터미널 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)`(해시·경로·태그는 실제 실행으로 교체):

```
$ git blame -w -C -M -- media/libstagefright/FooExtractor.cpp
e5f6a7b8 (Dev B 2019-03-11 ...) 143)   size_t n = readU32(box);
a1b2c3d4 (Dev A 2021-08-02 ...) 144)   uint8_t buf[n];        // 2021 리포맷 커밋에 blame이 붙음, n 검증 없음

$ git log -S'uint8_t buf[n]' --oneline -- media/libstagefright/FooExtractor.cpp
9c8d7e6f Fix unbounded stack VLA (stack exhaustion) in Foo box parsing   # <- 수정(제거)
e5f6a7b8 Add Foo box handling               # <- 도입(등장)

$ git tag --contains 9c8d7e6f | sort -V | head
android-14.0.0_r15
android-14.0.0_r16
```

두 가지가 드러난다. 첫째, 취약 줄 144(`uint8_t buf[n]`)의 `blame`은 2021년 리포맷·이동 커밋(`a1b2c3d4`)을 가리키지만, 그 취약 패턴이 **실제로 도입된 커밋은 `e5f6a7b8`(2019)**다 — blame은 줄을 마지막으로 건드린 청소 커밋에 도둑맞았고, 픽액스가 진짜 도입 시점을 집어낸다. 둘째, 수정 `9c8d7e6f`가 담긴 릴리스는 `git tag --contains`가 열거해 준다. 이 두 축(도입 시점 · 릴리스 포함)이 계보의 뼈대다.

## Root Cause — 왜 blame으로는 부족한가

`git blame`은 정의상 각 줄을 **가장 최근에 바꾼** 커밋을 귀속시킨다. 그래서 대량 리포맷(clang-format 일괄 적용), 파일 이름 변경, 코드 블록 이동이 한 번이라도 끼면 원래 취약 줄의 blame이 그 "청소" 커밋으로 옮겨간다. `-w`(공백 무시)·`-C -M`(복사·이동 추적)·`.git-blame-ignore-revs`로 완화할 수 있지만 완전하진 않다. 그래서 도입 시점은 blame이 아니라, 문자열 출현 횟수 변화를 추적하는 픽액스 `-S`(또는 정규식 `-G`, 함수 단위 `-L`)로 봐야 한다. `Source-confirmed`

릴리스 계보가 선형이 아닌 것도 핵심이다. AOSP는 단일 저장소가 아니라 `repo`로 묶인 다수 저장소이고, 한 CVE의 수정이 main에 들어간 뒤 지원 브랜치들로 **cherry-pick(백포트)**된다. 그래서 "이 버그가 특정 릴리스에 있느냐"는 main 히스토리만 봐선 답이 안 나오고, 각 릴리스 브랜치에서 `--contains`로 따로 확인해야 한다. 하나의 CVE가 여러 커밋(주 수정 + 후속 보완)을 갖는 경우도 흔해, 커밋 하나만 보고 계보를 단정하면 틀린다. `Inferred`

## 방어와 회귀 검증

패치 계보 추적의 실용적 종착점은 **회귀 테스트**다. 잘 다뤄진 수정 커밋은 diff에 취약 입력을 재현하는 테스트를 함께 넣는다. 내 오픈소스 퍼징 경험이 이걸 그대로 보여준다. wabt(WebAssembly Binary Toolkit)에 내가 올린 이슈 #2751은 보고 뒤 **78일 만에 커밋 `68a7ed2`로 머지**됐고, 패치는 제3자(ANAMASGARD)가 작성했으며, 그 커밋에 붙은 **회귀 테스트가 내가 제출한 PoC 그대로**였다. `Source-confirmed` 즉 수정 커밋의 diff에서 테스트 파일만 뽑아도 "이 버그를 트리거하는 최소 입력"과 "재발 방지 장치"를 동시에 확보한다. libsoup의 range 정수 오버플로(assert DoS)는 GNOME GitLab에 **제보한 단계까지** 진행했다. `Source-confirmed` (다만 이 건은 수정 커밋 머지·회귀 테스트 반영 여부까지는 확인하지 못했다 — 확인 필요.)

연구자 관점의 회귀 검증 절차는 단순하다. `git show <fix> -- <test-path>`로 추가된 테스트를 읽고, 그 입력을 도입 커밋 기준(수정 직전)으로 되돌린 트리에서 돌려 크래시를 재현한 뒤, 수정 커밋에서 테스트가 통과하는지 확인한다. 이렇게 하면 "패치됐다더라"가 아니라 **내 손에서 도입→수정 전이가 재현**된다. 단, 재현은 언제나 안전 범위 안에서(공개 CVE·자작 하네스·에뮬레이터) 최소 개념 수준으로만 한다.

## 정리

- 불리틴의 수정 커밋은 계보의 한 점이다. 도입 커밋은 `-S`/`-G` 픽액스로, 릴리스 포함은 `--contains`로 따로 캔다.
- `git blame`은 "마지막으로 건드린" 커밋을 준다. 리포맷·이동이 blame을 훔치므로 `-w -C -M`로 완화하되 도입 판정엔 픽액스를 쓴다.
- AOSP는 다중 저장소 + 백포트 모델이라 릴리스 계보가 비선형이다. main만 보고 릴리스 존재 여부를 단정하지 말 것.
- 수정 커밋의 회귀 테스트가 버그 클래스와 최소 트리거를 동시에 알려주는 가장 값진 부산물이다.

**점검 질문** — (1) 어떤 줄의 "도입 커밋"을 찾을 때 `git blame` 대신 무엇을 쓰고 왜인가? (2) 얕은 클론에서 `git tag --contains`가 틀린 답을 주는 이유는? (3) AOSP 플랫폼 커밋에 `Fixes:` 트레일러가 없을 때 원래 도입 커밋을 어떻게 찾는가?

**참고** — [git-log(픽액스 -S/-G, -L)](https://git-scm.com/docs/git-log) · [git-blame(-w/-C/-M)](https://git-scm.com/docs/git-blame) · [AOSP Submit patches(트레일러 관습)](https://source.android.com/docs/setup/contribute/submit-patches) · [Android Security Bulletins](https://source.android.com/docs/security/bulletin)

*다음 글: [Security Bulletin·patch provenance](/posts/android-vulnresearch-p4c03/).*
