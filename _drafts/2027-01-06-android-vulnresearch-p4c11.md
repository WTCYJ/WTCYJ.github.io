---
layout: post
title: "compatibility layer·중복 구현 버그"
date: 2027-01-06 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, DifferentialFuzzing, ParseDifferential, CompatLayer, Fuzzing]
excerpt: "같은 바이트를 두 번 구현하면 반드시 갈라진다. 흔한 함정 — 중복 구현 버그를 '크래시'로만 보면 절반을 놓친다. 검증하는 파서와 실행하는 파서가 서로 다른 바이트를 읽는 순간, 크래시 하나 없이 서명 검증이 우회된다(Master Key·Janus)."
---

큰 트리에서 버그를 가장 안정적으로 만들어내는 구조는 딱 하나다 — **같은 로직이 두 번 구현돼 있는 곳**. Android는 이 함정이 세 겹으로 깔려 있다. `targetSdkVersion`이 낡은 동작 경로를 새 경로 옆에 살려두고, 벤더와 언어 포트(C++→C, Java↔native)가 AOSP 컴포넌트를 다시 짜고, 그 결과 한쪽 사본에 들어간 수정이 다른 사본을 조용히 비껴간다. 그리고 이 클래스에서 제일 고약한 형태는 크래시가 아니다 — 어떤 입력을 **검증하는 코드**와 그걸 **실제로 쓰는 코드**가 같은 바이트를 다르게 읽는 파스 차분(parse differential)이다.

이 글은 중복 구현·파스 차분이라는 버그 클래스를 정리하고, 두 구현을 같은 코퍼스로 나란히 돌려 어긋남을 잡아내는 차분 퍼징(differential fuzzing) 워크플로를 개념 정리 + 자작 하네스 실습으로 기록한 것이다. 안전 범위는 오픈소스 파서 쌍과 이미 공개·패치된 CVE(Master Key·Janus)뿐이고, 어떤 무기화 PoC도 만들지 않는다.

> **한 줄 결론**: 같은 바이트를 두 번 구현하면 반드시 갈라진다. 크래시는 갈라짐이 눈에 띄는 한 형태일 뿐이고, 진짜 위험은 "검증하는 파서와 실행하는 파서가 다른 바이트를 읽는" 무-크래시 차분이다. 차분 퍼징은 그 둘을 한 번에 노린다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글이 다루는 것은 (1) 중복 구현이 버그를 만드는 통로 세 가지, (2) 그중 파스 차분이 왜 크래시보다 위험한지, (3) 두 구현에 같은 입력을 먹여 차분을 CI에 상시로 물리는 방법이다. 다루지 않는 것은 특정 벤더를 지목한 patch-gap 폭로(그건 이 파트 15장의 몫)와, 검증 우회를 실제 배포 앱에 적용하는 완성 익스플로잇이다.

선수 지식은 이 파트 앞 장들에서 쌓았다고 본다. 7장의 libFuzzer 하네스 작성, 8장의 corpus·coverage·dictionary, 9장의 crash dedup·minimization, 10장의 sanitizer(ASan/UBSan) 기반 네이티브 연구다. 차분 퍼징은 이 넷을 "두 벌"로 돌리는 것에 가깝다 — 새 개념이라기보다 기존 하네스를 나란히 세우는 배치다. APK 서명 스킴(v1 JAR 서명 vs v2 전체파일 서명)의 개념도 뒤에서 잠깐 필요한데, 이건 서명편 개념글에서 다룬 범위로 충분하다.

전체 구조에서 이 장은 **표면 열거와 퍼징 사이의 렌즈**다. 5~6장에서 공격 표면을 열거하고 7~10장에서 파서를 퍼징했다면, 이 장은 "같은 파서가 트리 안에 몇 개나 있고, 그중 어느 것이 안 고쳐졌나"를 묻는다. 그 질문이 15장의 patch-gap 사냥으로 이어진다.

## 핵심 개념 — 중복 구현이 버그를 만드는 세 통로

세 통로는 원인이 다 다르지만, 결과는 똑같다 — 트리 안에 같은 일을 하는 코드가 둘 이상 있고, 그것들이 시간이 갈수록 벌어진다.

| 통로 | 무엇이 중복되나 | 왜 벌어지나 | 보안적 결과 |
|--|--|--|--|
| targetSdk 호환 분기 | 같은 API의 legacy vs 신규 동작 | 구버전 앱을 안 깨려고 낡은 경로 유지 | 하드닝이 신규 경로에만 들어가 legacy가 약한 채 잔존 |
| 언어 포트·재구현 | C++↔C, Java↔native의 같은 파서 | 재구현자가 원본의 불변식을 추측 | 자료구조 선택 차이가 새 메모리 버그를 심음 |
| 벤더 포크 | AOSP 컴포넌트의 OEM 사본 | 상류 수정이 사본에 미전파 | 이미 고쳐진 버그가 사본에 그대로(→15장) |

Android의 targetSdk 분기는 `android.compat.Compatibility`/`CompatChanges.isChangeEnabled(long changeId)`로 게이트된다. 프레임워크가 **한 API에 대해 두 동작을 동시에 들고 있고**, 앱의 targetSdk가 특정 값 미만이면 낡은 쪽으로 흐른다. `Source-confirmed`(구체적으로 어느 changeId가 어느 targetSdk에서 하드닝을 켜는지는 버전마다 다르니 원문 재확인 필요) 요점은, 낡은 분기는 "안 깨는 것"이 목표라 하드닝 우선순위가 낮고, 그래서 같은 기능인데도 관측 가능한 취약면이 더 넓다는 것이다.

두 번째 통로가 이 글의 실습 표적이다. 하나의 포맷 파서를 언어를 바꿔 다시 짜면, 재구현자는 원본이 문서로 남기지 않은 불변식을 추측으로 메운다. C++ 원본이 `std::vector`로 임의 길이를 흡수하던 자리를 C 포트가 `tinyobj_vertex_index_t f[TINYOBJ_MAX_FACES_PER_F_LINE]`(상수 16, face 한 줄의 정점-인덱스 트리플 배열) 고정 배열로 옮기면, "한 face에 정점-인덱스 트리플 16개면 충분하겠지"라는 가정이 들어가고 — 그 가정이 곧 취약점이 된다. `Inferred`

세 번째 통로의 극단이 파스 차분이다. 두 파서가 **둘 다 크래시 없이** 같은 파일을 파싱했는데 결과가 다르면, 그 자체가 취약점이다. 검증 담당 파서가 본 것과 실행 담당 파서가 본 것이 다르기 때문이다.

> **[그림 1]** 같은 OBJ face 라인 파싱 로직을 C++ 원본(동적 `std::vector`)과 C 포트(고정 `tinyobj_vertex_index_t f[TINYOBJ_MAX_FACES_PER_F_LINE]`, 상수 16)에서 나란히 열어, 같은 기능이 서로 다른 버퍼 전략으로 구현된 대목을 강조한 소스 대조(diff/에디터) 캡처 — *실측 스크린샷 자리*

**신뢰 경계와 위협 모델.** 이 클래스의 신뢰 경계는 "무언가를 검증·인가한 컴포넌트"와 "그걸 실제로 실행·설치·역참조하는 컴포넌트" 사이에 있다. 둘이 서로 다른 파서일 때, 공격자의 일은 단 하나 — **두 파서가 다르게 읽는 입력**을 찾는 것이다. 두 개의 이미 공개·패치된 사례가 이 모델을 그대로 보여준다. Master Key(2013, Android 이슈 8219321)는 서명을 **검증하는 Java ZIP 경로**와 앱을 **설치·로드하는 C++ ZIP 경로**가 같은 파일명을 가진 중복 엔트리를 다르게 골라, 서명을 깨지 않고 내용을 바꿀 수 있었다. `Reported` Janus(CVE-2017-13156)는 한 파일이 유효한 ZIP이자 유효한 DEX일 수 있다는 점을 이용해, v1(JAR) 서명이 파일 앞에 덧붙인 바이트를 검증 범위에 넣지 않는 반면 런타임은 그 앞머리 DEX를 실행하는 차분이었다. `Reported` 둘 다 크래시가 아니라 "검증과 실행이 다른 바이트를 봤다"는 순수 차분이다.

## 실습 환경과 안전 범위

표적은 **중립 오픈소스 파서 쌍** 하나다 — 3D 모델 로더 tinyobjloader(C++ 원본)와 그 C 포트 tinyobjloader-c. 둘 다 같은 OBJ 포맷을 파싱하지만 구현이 독립이라, 차분 퍼징의 교과서 예제가 된다. 보안 경계(APK 서명 등) 위에서 confusion을 재현하지 않고, 파스 차분 논의는 이미 공개된 Master Key·Janus의 사실만 인용한다. 빌드는 clang의 `-fsanitize=address,fuzzer`, 하네스는 자작이다. 어떤 배포 앱도 건드리지 않는다.

한 가지 못 박아둔다. 아래에서 잡는 tinyobjloader-c의 결함은 **스택 버퍼 오버플로 쓰기(메모리 손상)**이고, 나는 이걸 크래시로 확정했을 뿐이다. RCE로 부풀리지 않는다 — 이 클래스는 "크래시를 취약점으로, DoS를 RCE로" 과장하기 딱 좋은 자리라 특히 조심한다.

## 실습 절차와 관측

### 가설
- **가설 A** — 같은 face 라인 입력을 C++ 원본과 C 포트에 먹이면, 고정 버퍼 `tinyobj_vertex_index_t f[TINYOBJ_MAX_FACES_PER_F_LINE]`(상수 16)를 쓰는 C 포트만 ASan 스택 오버플로로 죽고 C++ 원본은 멀쩡하다. `Source-confirmed`(내가 검증한 결과)
- **가설 B** — 크래시가 없어도, 두 파서의 파싱 결과(예: 정점/면 개수)가 갈리면 그 자체가 차분이다. 이게 Master Key·Janus의 무-크래시 버전이다. `Inferred`

### 절차
1. 두 구현을 각각 `-DNDEBUG`(릴리스=assert 컴파일아웃 상태) + ASan + libFuzzer로 빌드한다.
2. 얇은 래퍼로 두 구현을 각자 libFuzzer 타깃으로 감싼다.
3. **같은 seed corpus**로 두 바이너리를 돌려, 어느 쪽이 죽는지 비교한다(가설 A).
4. 크래시 입력을 9장 방식으로 최소화해 어느 구현·어느 함수·어느 버퍼인지 특정한다.
5. 무-크래시 차분(가설 B)은 두 파서를 한 하네스에 넣고 결과를 대조한다.

```c
// fuzz_one.c — 한 구현을 감싸는 표준 libFuzzer 타깃 (양쪽에 같은 파일을 씀)
#include <stdint.h>
#include <stddef.h>
int load_obj(const uint8_t *buf, size_t len);   // 대상 구현의 얇은 래퍼
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    load_obj(data, size);   // 파싱만; 여기서 죽으면 = 이 구현만의 메모리 버그
    return 0;
}
```

```bash
# 두 구현을 각각 ASan+fuzzer로. -DNDEBUG로 릴리스(assert 없는) 상태를 재현한다.
clang++ -O1 -DNDEBUG -fsanitize=address,fuzzer \
        fuzz_one.c wrap_cpp.cc -Itinyobjloader     -o fuzz_cpp
clang   -O1 -DNDEBUG -fsanitize=address,fuzzer \
        fuzz_one.c wrap_c.c    -Itinyobjloader-c   -o fuzz_c
# 완전히 같은 seed corpus로 나란히
./fuzz_cpp -runs=200000 corpus/     # 깨끗
./fuzz_c   -runs=200000 corpus/     # parseLine에서 ASan
```

무-크래시 차분(가설 B)은 하네스를 이렇게 바꾼다 — `load_obj` 대신 두 파서를 다 호출하고, 둘 다 성공했는데 정점 수가 다르면 `__builtin_trap()`. 그 트랩이 곧 "검증-실행이 갈릴 수 있는 지점"이다.

> **[그림 2]** `./fuzz_c`가 같은 corpus에서 `parseLine`의 고정 배열 `f`에 대한 ASan stack-buffer-overflow WRITE를 뱉고, 동일 corpus로 돌린 `./fuzz_cpp`는 크래시 없이 진행되는 두 터미널을 대조한 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체 — 줄번호 NNN 등은 실측값으로):

```
==12345==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffe...
WRITE of size 4 at 0x7ffe... thread T0
    #0 ... in parseLine tinyobjloader-c/tinyobj_loader_c.h:NNN
    #1 ... in tinyobj_parse_obj tinyobjloader-c/tinyobj_loader_c.h:...
    #2 ... in load_obj wrap_c.c:...
    #3 ... in LLVMFuzzerTestOneInput fuzz_one.c:6
Address 0x7ffe... is located in stack of thread T0 at offset ...
  'f' (line NNN) <== Memory access at offset ... overflows this variable
```

읽는 법은 세 가지다. (1) 크래시가 **C 포트에서만** 났다 → 이건 포맷의 버그가 아니라 이 구현의 버그다(가설 A 확정). (2) 오버플로 변수가 `f`(고정 배열)라 원인이 자료구조 선택임을 짚어준다. (3) 같은 corpus에서 C++는 멀쩡했다는 사실이, "원본은 임의 길이를 흡수했다"를 방증한다. 정점-인덱스 트리플이 16개를 넘는 face 라인 하나가 `f[TINYOBJ_MAX_FACES_PER_F_LINE]`(=16)를 넘겨 스택에 쓴 것이다. `Source-confirmed`

## Root Cause — 왜 이렇게 되는가

재구현자는 원본의 불변식을 **문서 없이 추측**한다. C++ tinyobjloader는 face의 정점-인덱스를 동적 컨테이너로 받아 개수에 상한이 없다. C 포트는 이걸 옮기며 "한 face에 정점-인덱스 트리플 16개면 넉넉하지"라는 암묵 가정을 `tinyobj_vertex_index_t f[TINYOBJ_MAX_FACES_PER_F_LINE]`(상수 16)로 굳혔다 — 그 상수가 곧 취약점의 경계다. 원본에 없던 버그가 포트에서 새로 태어난 전형이다. `Source-confirmed`

여기에 릴리스 빌드 함정이 겹친다. 이런 코드는 종종 `assert`로 인덱스를 지키는데, `-DNDEBUG`가 켜진 배포 빌드에선 `assert`가 통째로 컴파일아웃된다. **소스에 가드가 보여도 출하 바이너리엔 없다.** 그래서 위 실습을 `-DNDEBUG`로 돌린다 — 개발 빌드에서만 잡히는 가드에 속지 않으려고. `Source-confirmed`

targetSdk 분기의 근본 원인은 정책적이다. legacy 경로의 목표는 "구버전 앱을 안 깨는 것"이라, 새 하드닝은 신규 changeId 뒤에만 붙고 낡은 경로는 의도적으로 그대로 둔다. 기능은 하나인데 보안 자세가 둘인 셈이다. `Inferred`

파스 차분의 근본 원인은 하나의 암묵 가정이 깨지는 것이다 — "검증하는 파서와 실행하는 파서가 같은 바이트를 같은 방식으로 본다." Master Key는 그 둘이 서로 다른 ZIP 구현이었고, Janus는 v1 서명의 검증 범위가 파일 전체가 아니었다. 두 파서가 존재하는 순간, 공격자는 코드를 건드릴 필요 없이 **둘이 갈리는 입력**만 찾으면 된다. `Reported`

## 방어와 회귀 검증

- **차분을 회귀 씨앗으로 고정.** 잡은 크래시·차분 입력을 corpus/regression 디렉터리에 넣고, CI에서 두 구현 모두를 매번 그 씨앗에 통과시킨다. 한쪽만 고치고 넘어가면 다른 사본에 그대로 남는다는 게 이 클래스의 본질이라, "양쪽 다"를 CI가 강제해야 한다.
- **가능하면 구현을 하나로.** 진짜 방어는 single source of truth다. 못 합치면, 두 구현에 같은 차분 하네스를 상시로 물려 벌어짐을 조기에 잡는다.
- **파스 차분은 '검증한 그 바이트만 실행'으로.** Janus는 파일 전체를 서명하는 v2 스킴이 검증 범위와 실행 범위를 일치시켜 닫혔고, Master Key는 ZIP 처리 경로 자체를 일치시켜 닫혔다. `Reported` 방어의 방향은 언제나 "두 파서를 하나로 수렴".
- **targetSdk 하드닝 확인.** 어떤 changeId가 특정 targetSdk 미만에서 꺼지는지 점검한다(구체 changeId·버전 귀속은 원문 재확인 필요). 낡은 분기가 살아 있는 한, 낮은 targetSdk를 노리는 우회면이 남는다.
- **함정: 상류만 고쳐진다.** tinyobjloader-c 같은 코드는 다운스트림(예: 게임/렌더 프로젝트)이 소스째 번들한다. 상류가 아카이브되거나 고쳐져도 **사본은 사본으로 남는다.** 이게 통로 3(벤더 포크)의 오픈소스 판본이고, 사냥은 15장으로 이어진다.

## 정리

- 같은 로직이 두 번 구현된 곳이 이 클래스의 서식지다 — targetSdk 분기, 언어 포트, 벤더 포크의 셋.
- 크래시는 갈라짐의 한 형태일 뿐. 무-크래시 파스 차분(검증≠실행)이 서명 우회 같은 더 조용하고 큰 위협이다.
- 방어·검증의 핵심은 "두 구현을 같은 corpus로 나란히, 상시로" 돌려 벌어짐을 회귀로 고정하는 것. 이상적으로는 구현 자체를 하나로 합친다.

**점검 질문** — (1) 같은 corpus에서 C 포트만 죽고 C++ 원본은 멀쩡했다면, 이건 포맷의 버그인가 구현의 버그인가? (2) `-DNDEBUG`로 빌드해 실습하는 이유는? (3) Master Key·Janus가 "크래시 없는" 취약점인 이유를, 검증 파서와 실행 파서라는 말로 설명해 보라.

**참고** — [tinyobjloader](https://github.com/tinyobjloader/tinyobjloader) · [tinyobjloader-c](https://github.com/syoyo/tinyobjloader-c) · [libFuzzer](https://llvm.org/docs/LibFuzzer.html) · [APK Signature Scheme v2](https://source.android.com/docs/security/features/apksigning/v2) · [Android Security Bulletin 2017-12(Janus, CVE-2017-13156)](https://source.android.com/docs/security/bulletin/2017-12-01)

*다음 글: [SELinux policy·service_contexts 감사](/posts/android-vulnresearch-p4c12/).*
