---
layout: post
title: "Fuzzing-101 - AFL++로 Xpdf, libexif, tcpdump의 옛 CVE를 직접 터뜨려 보기"
date: 2026-09-03 02:00:00 +0900
category: 블로그/기술
author: WTCY
tags: [Fuzzing, AFL++, ASAN, CVE, Xpdf, libexif, tcpdump, libpcap, 취약점분석, 학습기록]
excerpt: "퍼징 환경을 직접 만들고, 타겟을 읽고, 전략을 세워 돌리고, 나온 크래시의 원인을 끝까지 따라가 본 기록입니다. Fuzzing-101의 앞 세 문제를 골라 WSL에 AFL++를 소스로 올리고 Xpdf 3.02·libexif 0.6.14·tcpdump 4.9.1을 세웠습니다. Xpdf에서는 CVE-2019-13288의 재귀 고리와 그 옆에 있던 NULL 역참조를, libexif에서는 정수 오버플로로 무너진 경계 검사와 exif_entry_fix의 힙 오버플로를 확인했습니다. tcpdump는 크래시가 한참 안 나왔는데, 판정이 pcap 헤더의 snaplen에 걸려 있다는 걸 알아내 시드와 전략을 고치자 CVE-2017-13011·CVE-2017-13000·CVE-2017-13032를 포함해 네 자리가 나왔습니다. 노리던 CVE-2017-13028은 조건을 세워 직접 재현했고, 두 자리는 고쳐서 확인까지 했습니다."
---

> 대상: [antonio-morales/Fuzzing101](https://github.com/antonio-morales/Fuzzing101) Exercise 1~3
> — Xpdf 3.02 / libexif 0.6.14 / tcpdump 4.9.1
> 환경: Windows 11 + WSL2 Ubuntu 24.04, AFL++ 5.03c(소스 빌드), clang 18, 16스레드

퍼징을 글로만 읽으면 "무작위 입력을 왕창 넣어서 크래시를 본다"로 요약되고 맙니다. 실제로 해 보면
그 한 줄에 안 들어가는 게 훨씬 많습니다. 타겟을 어떻게 세우고, 시드를 뭘로 주고, 크래시를 무엇으로
판정하고, 나온 파일 더미에서 버그가 몇 개인지 어떻게 가릴지가 전부 선택입니다. 이번 미션은
Fuzzing-101에서 세 문제를 골라 그 선택들을 직접 해 보는 것이었습니다.

사실 이 글은 몇 달 전에 한 번 썼던 것입니다. 그때는 `aflplusplus/aflplusplus` 도커 이미지 안에서
작업했는데, 컨테이너를 지우고 나니 결과를 다시 꺼내 볼 방법이 없었습니다. 화면도 한 장 없이 제가
옮겨 적은 숫자만 남아 있었습니다. 나중에 제 글을 다시 읽다가 "이거 지금 확인이 되나" 싶었고, 답이
"안 된다"였습니다. 그래서 환경부터 새로 만들어 처음부터 다시 했습니다. 이번에는 산출물을 전부
디스크에 남겼고, 화면은 실제로 돌아가는 콘솔을 찍었습니다.

다시 하면서 예전 글에 없던 게 여럿 나왔습니다. Xpdf에서는 목표 CVE 말고 다른 버그가 하나 더
나왔고, libexif는 하네스를 어떻게 짜느냐가 찾을 수 있는 버그를 갈랐습니다. tcpdump는 다섯 시간을
돌려도 크래시가 없었는데, 그 이유를 파고들어 시드와 전략을 고치고 나서야 나왔습니다. 그것도 제가
노리던 것과는 다른 자리 넷이었습니다.

---

## 0. 환경

도커 데스크톱이 죽어 있었습니다. 소켓은 있는데 데몬이 안 붙는 그 상태였고, 되살리는 데 시간을
쓰느니 WSL에서 하는 게 빠르겠다 싶었습니다. Ubuntu 24.04에 AFL++를 소스로 올렸습니다.

```console
$ git clone --depth 1 -b stable https://github.com/AFLplusplus/AFLplusplus.git
$ LLVM_CONFIG=llvm-config-18 NO_NYX=1 make -j16 source-only PREFIX=$HOME/afl
$ make install PREFIX=$HOME/afl
```

빌드 요약에 LTO 모드와 gcc 플러그인 모드가 빠졌다고 나오는데 둘 다 이번엔 필요 없습니다. LTO
모드는 LLVM 11~14를 요구하고 여기 깔린 건 18입니다. 필요한 건 `afl-clang-fast` 하나이고 그건
정상적으로 만들어졌습니다.

![AFL++ 5.03c와 clang 18 버전 출력, 소스 빌드 요약에서 LLVM mode는 성공하고 LTO·gcc_mode는 선택 사항이라 빠졌다는 메시지, 그리고 afl-showmap이 pdftotext에서 엣지 1259개를 잡아낸 화면](/assets/img/fuzzing101/env-afl.png)

계측이 실제로 들어갔는지는 `afl-showmap`으로 확인합니다. 엣지가 잡히면 컴파일러 래퍼가 제대로
붙은 겁니다. 여기서 0이 나오면 그 뒤로 아무리 오래 돌려도 커버리지 없는 랜덤 테스트에 불과합니다.
퍼징을 시작하기 전에 반드시 보고 넘어가야 하는 숫자입니다.

이 환경에서 걸린 게 둘 있었습니다. 하나는 sudo 비밀번호입니다. 이 WSL 계정은 무암호 sudo가
아니라서 `apt install`을 못 씁니다. tcpdump 쪽에서 flex와 bison이, 트리아지에서 gdb가 필요했는데
전부 이렇게 우회했습니다.

```console
$ apt-get download flex bison m4 gdb          # 루트 없이 .deb 만 받는다
$ for d in *.deb; do dpkg -x "$d" ~/f101/localtools/root; done
$ export PATH=~/f101/localtools/root/usr/bin:$PATH
$ export BISON_PKGDATADIR=~/f101/localtools/root/usr/share/bison
```

`apt-get download`는 권한이 필요 없습니다. 받은 `.deb`를 `dpkg -x`로 홈에 풀고 PATH만 앞에 얹으면
됩니다. bison은 자기 데이터 디렉터리를 절대경로로 찾으니 `BISON_PKGDATADIR`을 같이 지정해야
동작합니다.

다른 하나는 커널의 코어 덤프 설정입니다. WSL은 `core_pattern`이 파이프(`|/wsl-capture-crash`)로
잡혀 있어서, AFL이 크래시를 놓칠 수 있다며 시작을 거부합니다. 고치려면 root가 필요하니
`AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1`로 넘겼습니다. 크래시마다 커널이 헬퍼를 하나씩 띄우는
셈이라 조금 느려지지만 판정 자체는 정상입니다.

---

## 1. 문제 고르기와 사전 리서치

Fuzzing-101은 열 문제인데, 뒤로 갈수록 클로즈드소스·윈도우·자바스크립트 엔진으로 넘어갑니다.
앞 세 문제가 기본기를 한 번씩 다르게 요구해서 그걸 골랐습니다. 1번은 계측 빌드와 트리아지, 2번은
라이브러리를 어떻게 부를지, 3번은 AddressSanitizer가 주제입니다. 세 개를 하면 파일 파서,
라이브러리, 네트워크 파서를 한 번씩 만지게 됩니다.

돌리기 전에 세 CVE를 먼저 읽었습니다. 여기서 하나 걸렸습니다.

![Fuzzing-101 Readme의 앞 세 문제 목록(Xpdf/CVE-2019-13288, libexif/CVE-2009-3895·CVE-2012-2836, TCPdump/CVE-2017-13028), 그런데 실습이 지정한 tcpdump 4.9.2의 print-bootp.c 325행에 ND_TCHECK(bp->bp_flags)가 이미 들어 있고, 4.9.1에는 그 검사가 0개라는 것을 보여 주는 화면](/assets/img/fuzzing101/research.png)

원본 실습 문서는 Exercise 3에서 tcpdump 4.9.2를 받아 CVE-2017-13028을 찾으라고 합니다. 그런데
4.9.2에는 이 CVE의 수정이 이미 325행에 들어가 있습니다. 문서가 공식 수정이라며 링크한 커밋
`85078ee`는 2017년 12월 것이고, 4.9.2 릴리스는 그해 9월입니다. 즉 4.9.2를 퍼징해서 나오는 건 이
CVE가 아니라 그 뒤에 고쳐진 다른 경계 버그입니다. 그래서 저는 CVE-2017-13028이 실제로 살아 있는
4.9.1로 내렸습니다. 미션의 목표가 그 CVE를 재현하는 것이니 버전을 맞추는 게 먼저였습니다.

---

## 2. Xpdf 3.02

첫 문제의 목표는 CVE-2019-13288입니다. 2007년에 나온 Xpdf 3.02의 `pdftotext`가 대상이고, 악성 PDF
하나로 스택을 다 태워 버리는 버그입니다.

### 2-1. 빌드 두 벌

세 문제를 다 ASAN으로 빌드했던 게 예전 글의 실수였습니다. 이 버그는 재귀가 스택을 소진하면서 나는
SIGSEGV라, 계측 없이도 커널이 알아서 잡아 줍니다. ASAN을 얹으면 실행 속도만 몇 배 느려집니다.
그래서 이번에는 퍼징용은 ASAN 없이, 트리아지용은 ASAN 있게 두 벌을 따로 만들었습니다.

```console
$ CC=afl-clang-fast CXX=afl-clang-fast++ ./configure --prefix=$R/install/xpdf
$ make -j16 && make install                         # 퍼징용 — 빠르게

$ AFL_USE_ASAN=1 로 같은 소스를 install/xpdf-asan 에 한 벌 더    # 트리아지용 — 자세하게
```

18년 된 C++인데 clang 18에서 경고 998개를 뱉으면서도 에러 없이 빌드됩니다. `register` 키워드
같은 게 걸릴 줄 알았는데 3.02는 그 문법을 안 씁니다.

### 2-2. 시드와 퍼징

시드는 최소 PDF 두 개로 시작했습니다. 파서를 열려면 유효한 PDF 구조가 있어야 하고, 그 이상은
퍼저가 알아서 부술 몫입니다. 인스턴스는 `-M main` 하나에 `-S sec1~3`을 붙여 넷을 돌렸습니다.

```console
$ afl-fuzz -i seeds/pdf -o out/xpdf -M main -- install/xpdf/bin/pdftotext @@ /dev/null
```

첫 크래시는 6분 만에 나왔습니다. 파일 이름에 `op:trim`이 찍혀 있는데, 변이 단계가 아니라 큐에 든
입력을 줄이다가 터졌다는 뜻입니다.

![AFL++ 상태 화면. sec1 인스턴스가 54분 22초 동안 146만 회 실행, saved crashes 2가 빨간색으로, saved hangs 9, 커버리지 7.93%, 안정도 100%를 보이고 있다](/assets/img/fuzzing101/ex1-afl.png)

행(hang)이 크래시보다 훨씬 많이 쌓입니다. 무한 재귀는 스택이 다 차기 전에 타임아웃에 먼저 걸리는
경우가 많아서 그렇습니다. 같은 뿌리에서 나온 것들이니 행 쪽도 한 번은 봐야 합니다.

### 2-3. 크래시 분류

크래시 파일 개수는 버그 개수가 아닙니다. 퍼징을 멈추고 나온 입력을 전부 ASAN 빌드에 다시 먹인 뒤,
ASAN 리포트의 유형과 상위 프레임을 시그니처로 삼아 묶었습니다.

```console
$ kind=$(grep -m1 -oE "AddressSanitizer: [A-Za-z-]+" $out)
$ top=$(grep -E "^    #[0-9]+ " $out | head -4 | grep -oE ' in [A-Za-z_:~][A-Za-z0-9_:~]*')
$ echo "$kind | $top" >> sigs.txt          # 이걸로 sort | uniq -c
```

![xpdf 크래시를 ASAN 유형과 터진 함수로 묶은 결과. SEGV가 EmbedStream::getPos에서 4회, SEGV가 EmbedStream::getChar에서 2회, stack-overflow가 Lexer::getObj에서 1회. 시그니처는 셋이지만 앞의 둘은 크래시 지점만 다르고 원인이 같아 서로 다른 버그는 둘이라는 설명이 붙어 있다](/assets/img/fuzzing101/ex1-buckets.png)

시그니처는 셋으로 갈렸는데 그중 둘은 크래시 지점만 다를 뿐 원인이 같았습니다. 결국 서로 다른
버그는 두 개입니다.

여기서 실수를 하나 했습니다. 처음엔 크래시 파일이 여덟 개로 잡혔는데 그중 둘이 0바이트라 재현이
안 됐습니다. AFL++ 5.x는 크래시 입력 옆에 같은 이름의 `.txt` 파일을 하나 더 만듭니다
(`afl-fuzz-bitmap.c:774`). 제 `find` 패턴이 그 사이드카까지 같이 긁어온 것이었습니다.
`! -name '*.txt'`를 붙이니 정리됐습니다.

한 가지 더. 중간에 퍼징을 잠깐 멈췄다가 `-i -`로 이어 돌렸는데, 그러면 AFL이 기존 `crashes/`를
`crashes.2026-09-03-00:51:40/` 같은 이름으로 옮겨 둡니다. 지우는 게 아니라 보관하는 것이라, 나중에
집계할 때 이 디렉터리들까지 봐야 합니다. 처음엔 몰라서 크래시가 사라졌다고 잠깐 착각했습니다.

### 2-4. 재귀 (CVE-2019-13288)

ASAN이 `stack-overflow`를 보고한 크래시가 목표한 그것이었습니다. 스택 트레이스가 328프레임인데,
읽어 보면 같은 네 개가 계속 돌고 있습니다.

![ASAN stack-overflow 리포트. Parser::getObj → XRef::fetch → Object::dictLookup → Parser::makeStream → Parser::getObj 순서로 프레임이 반복되고, 함수별 등장 횟수가 각각 82·81·80·80회로 집계된 화면](/assets/img/fuzzing101/ex1-recursion.png)

고리의 모양은 이렇습니다. `Parser::getObj`가 딕셔너리를 읽다가 `stream` 키워드를 만나면
`Parser::makeStream`을 부릅니다. 스트림의 길이를 알아야 하니 `/Length`를 찾습니다.

```c
/* Parser.cc:156 */
dict->dictLookup("Length", &obj);
```

그런데 `/Length` 값이 숫자가 아니라 간접 참조(`12 0 R`)면 `dictLookup`은 `XRef::fetch`를 통해 그
객체를 가져옵니다. `XRef::fetch`는 새 파서를 만들어 `getObj`를 부릅니다. 그 객체가 또 스트림이고
그 `/Length`가 다시 앞의 객체를 가리키면 고리가 닫힙니다.

```c
/* XRef.cc:823 */
parser->getObj(obj, encrypted ? fileKey : NULL, encAlgorithm, keyLength, num, gen);
```

깊이를 세는 곳이 어디에도 없습니다. 방문한 객체 번호를 기억하지도 않습니다. 그래서 PDF 안에
서로를 가리키는 두 객체만 있으면 스택이 다 찰 때까지 내려갑니다. Xpdf 4.x가 `getObj`와 `fetch`에
재귀 깊이 인자를 추가한 게 이 문제의 수정입니다. 퍼저가 이걸 6분 만에 찾은 이유도 간단합니다.
객체 번호 하나를 다른 숫자로 바꾸는 변이는 havoc이 제일 잘하는 일이고, 그 결과가 곧바로 새 코드
경로로 이어지니 커버리지 피드백이 그쪽으로 계속 밀어 줍니다.

### 2-5. NULL을 감싼 EmbedStream

같은 퍼징에서 성격이 전혀 다른 크래시가 나왔습니다. NULL 역참조인데 인라인 이미지 처리 경로에
있습니다.

![ASAN SEGV on unknown address 0x000000000000 리포트. EmbedStream::getPos → Stream::makeFilter → Stream::addFilters → Gfx::buildImageStream 순으로 프레임이 이어지고, 아래에 Gfx.cc의 EmbedStream 생성 코드와 Stream.h의 getPos 정의가 함께 표시된 화면](/assets/img/fuzzing101/ex1-null.png)

`Gfx::buildImageStream`이 PDF 콘텐츠 스트림 안의 인라인 이미지(`BI`)를 만나면 이렇게 합니다.

```c
/* Gfx.cc:3924 */
str = new EmbedStream(parser->getStream(), &dict, gFalse, 0);
str = str->addFilters(&dict);
```

`parser->getStream()`은 렉서가 현재 읽고 있는 스트림을 돌려주는데, 다 읽었으면 NULL입니다.

```c
/* Lexer.h:53 */
Stream *getStream()
  { return curStr.isNone() ? (Stream *)NULL : curStr.getStream(); }
```

그 NULL을 검사 없이 `EmbedStream`으로 감쌉니다. `EmbedStream`의 메서드들은 전부 안쪽 스트림에
그대로 넘기는 구조라 어느 하나만 불려도 터집니다.

```c
/* Stream.h:364 */
virtual int getPos() { return str->getPos(); }
```

크래시 지점이 두 군데로 갈린 이유가 이겁니다. 필터 이름이 알 수 없는 것이면 `makeFilter`가
`error(getPos(), ...)`를 부르면서 `getPos`에서 터지고, 필터를 통과하면 `opBeginImage`가 `EI`
태그를 찾으려고 `getChar`를 부르면서 거기서 터집니다. 호출자 쪽에 `if (str)` 검사가 있긴 한데
`str` 자체는 멀쩡한 객체이고 NULL은 그 안에 들어 있으니 소용이 없습니다.

이 버그에 CVE 번호가 붙어 있는지는 확인하지 못했습니다. Xpdf 3.02는 알려진 파서 버그가 워낙 많고,
벤더가 3.x 시절 수정 이력을 커밋 단위로 공개하지 않아서 어느 항목에 해당하는지 대조할 방법이
마땅치 않았습니다. 재현 조건과 원인은 위에 적은 그대로입니다.

---

## 3. libexif 0.6.14

두 번째 문제의 목표는 CVE-2009-3895와 CVE-2012-2836입니다. 둘 다 EXIF 파서의 경계 검사 문제입니다.

### 3-1. 하네스

원본 실습은 libexif 배포판의 `exif` 명령줄 도구를 대상으로 씁니다. 그런데 그 도구는 popt에
의존하고, 이 환경엔 `popt.h`가 없습니다. 설치하려면 또 sudo입니다. 그래서 `exif`가 하는 일을
그대로 옮긴 하네스를 직접 만들었습니다.

```c
int main(int argc, char **argv)
{
	ExifData *d = exif_data_new_from_file(argv[1]);
	if (!d)                       /* EXIF 없는 파일 — 크래시가 아니라 정상 종료 */
		return 0;

	exif_data_fix(d);                               /* 규격 위반 태그 교정 */
	exif_data_foreach_content(d, on_content, NULL);  /* 엔트리 값 문자열화 */
	exif_data_unref(d);
	return 0;
}
```

세 줄이 각각 다른 코드 영역을 엽니다. `exif_data_new_from_file`은 파싱, `exif_data_fix`는 교정,
`foreach_content`는 출력 경로입니다. 뒤에 나오지만 두 번째 줄을 넣은 게 결정적이었습니다. 그걸
빼면 CVE-2009-3895 쪽 코드에는 아예 도달하지 못합니다. 하네스를 짤 때 무엇을 부를 것인가가 곧
무엇을 찾을 수 있는가입니다.

시드는 EXIF가 들어 있는 JPEG 두 장이면 충분했습니다. 이번엔 힙을 넘어가는 읽기가 목표라 ASAN을
켜고 빌드했습니다.

![AFL++ 상태 화면. exif_harness를 대상으로 55분 11초 동안 40만 8천 회 실행, 사이클 19회 완료, saved crashes 2, 커버리지 4.81%/29.47%를 보이고 있다](/assets/img/fuzzing101/ex2-afl.png)

### 3-2. IFD0 오프셋 (CVE-2012-2836)

첫 크래시가 79초 만에 나왔습니다. 파일 이름이 어떻게 나왔는지까지 말해 줍니다.

```
id:000000,sig:11,src:000000,time:78947,execs:10691,op:arith32,pos:34,val:-9
```

`arith32`는 32비트 정수를 조금씩 더하고 빼 보는 단계입니다. `pos:34`, `val:-9`. 시드의 34번
바이트에서 32비트 값을 읽어 9를 뺐다는 뜻입니다. 그 자리에 뭐가 있었는지 보면,

```console
$ xxd -s 32 -l 16 seeds/jpeg/canon40d.jpg
00000020: 2a00 0800 0000 0b00 0f01 0200 0600 0000  *...............
```

`2a00`이 TIFF 매직이고 그 뒤 4바이트가 IFD0 오프셋입니다. 값은 8입니다. 8에서 9를 빼면 −1, 즉
`0xFFFFFFFF`입니다. 퍼저가 우연히 뒤집은 게 아니라 결정적 단계가 정확히 그 필드를 골라 음수로
넘긴 겁니다.

![ASAN SEGV 리포트. exif_get_sshort → exif_get_short → exif_data_load_data → exif_loader_get_data → exif_data_new_from_file 프레임과, 크래시 입력의 헥스덤프에서 TIFF 매직 2a00 뒤 IFD0 오프셋이 ffffffff로 바뀐 것이 표시된 화면](/assets/img/fuzzing101/ex2-asan.png)

문제의 코드는 이렇습니다.

```c
/* exif-data.c:815 — 0.6.14 */
if (offset + 6 + 2 > ds) {
	return;
}
n = exif_get_short (d + 6 + offset, data->priv->order);
```

검사가 있긴 있습니다. 그런데 `offset`이 부호 없는 32비트입니다. `0xFFFFFFFF + 8`은 자리를 넘겨
`7`이 되고 `7 > ds`는 거짓입니다. 검사를 통과합니다. 그 다음 줄에서 `d + 6 + 0xFFFFFFFF`를 읽습니다.
경계 검사가 없어서가 아니라 경계 검사 자체가 오버플로로 무너진 경우입니다.

CVE 번호를 눈대중으로 붙이지 않으려고 상류 저장소 이력을 직접 뒤졌습니다.

```console
$ git log --oneline -S 'offset > ds || offset + 6 + 2 > ds' -- libexif/exif-data.c
8ce72b7 Fix a buffer overflow on corrupt EXIF data. ... fixes part of CVE-2012-2836
```

![0.6.14의 경계 검사 코드와, 상류 커밋 8ce72b7(2012-07-12)이 그 자리에 offset > ds 조건을 앞에 붙인 diff가 함께 표시된 화면](/assets/img/fuzzing101/ex2-guard.png)

2012년 7월 커밋이 같은 줄에 `offset > ds ||`를 앞에 붙였습니다. 덧셈을 하기 전에 걸러 내는
방식입니다. 2020년에는 `CHECKOVERFLOW` 매크로로 한 번 더 일반화됐는데, 뺄셈으로 바꿔 아예 넘칠
일이 없게 만든 형태입니다.

```c
#define CHECKOVERFLOW(offset,datasize,structsize) \
	((offset) >= (datasize) || (structsize) > (datasize) || (offset) > (datasize) - (structsize))
```

### 3-3. exif_entry_fix (CVE-2009-3895)

16분쯤 뒤에 성격이 다른 크래시가 나왔습니다. 이번엔 SEGV가 아니라 힙 오버플로입니다.

![ASAN heap-buffer-overflow 리포트. READ of size 4, exif_get_slong → exif_get_long → exif_entry_fix → fix_func → exif_content_fix → exif_data_fix → main 경로와, exif-entry.c의 components 만큼 도는 변환 루프 코드가 함께 표시된 화면](/assets/img/fuzzing101/ex2-entryfix.png)

경로가 `exif_data_fix → exif_content_fix → exif_entry_fix`입니다. 하네스에서 제가 넣은 그 줄로
들어간 겁니다. 문제 지점은 태그 포맷 교정 루프입니다.

```c
/* exif-entry.c:188 — LONG 으로 들어온 태그를 SHORT 로 고치는 중 */
for (i = 0; i < e->components; i++)
	exif_set_short (e->data + i * exif_format_get_size (EXIF_FORMAT_SHORT), o,
		(ExifShort) exif_get_long (e->data + i * exif_format_get_size (EXIF_FORMAT_LONG), o));
```

`e->components`는 파일이 정하는 값이고 `e->data`는 파싱할 때 잡아 둔 버퍼입니다. 루프는
`components × 4`바이트를 읽는데 그게 버퍼 크기 안인지 확인하지 않습니다. `components`를 크게 써
넣은 EXIF 하나면 버퍼 밖을 읽습니다. CVE-2009-3895가 이겁니다.

기록해 둘 만한 건 이 크래시가 하네스 설계에 달려 있었다는 점입니다. `exif_data_fix`를 부르지 않는
하네스로 아무리 오래 돌려도 이 코드에는 도달하지 못합니다. 라이브러리를 퍼징할 때는 하네스가
어디까지 부르느냐가 곧 찾을 수 있는 버그의 범위입니다.

---

## 4. tcpdump 4.9.1

세 번째 문제는 CVE-2017-13028, BOOTP 파서의 경계 읽기 버그입니다. 셋 중 제일 오래 걸렸고 제일
많이 배웠습니다.

### 4-1. 빌드와 ASAN 링크

libpcap은 flex와 bison이 필요합니다. GitHub 태그 스냅샷에는 생성물(`scanner.c`, `grammar.c`)이
없어서 configure가 바로 막힙니다. 0장에서 만든 로컬 flex/bison으로 넘겼습니다. tcpdump.org는 이
환경에서 연결이 리셋돼서 소스는 GitHub 태그로 받았습니다.

여기서 시간을 제일 많이 쓴 건 tcpdump의 configure였습니다.

```
checking for local pcap library... ../libpcap-1.8.1/libpcap.a
checking for pcap_loop... no
configure: error: This is a bug, please follow the guidelines in CONTRIBUTING ...
```

libpcap은 `AFL_USE_ASAN=1 make`로 빌드해 뒀는데, tcpdump의 configure는 그 `.a`를 ASAN 없이
링크해서 시험합니다. `config.log`를 열어 보면 이유가 바로 나옵니다.

```
libpcap-1.8.1/pcap.c:158: undefined reference to `__asan_report_load8'
libpcap-1.8.1/pcap.c:197: undefined reference to `__asan_memcpy'
```

계측된 라이브러리를 계측 없이 링크하니 ASAN 런타임 심볼이 없다는 겁니다. `pcap_loop`가 없는 게
아니라 링크가 실패한 것이고, configure는 그걸 함수가 없다고 읽습니다. configure 단계에도 같은
`AFL_USE_ASAN=1`을 걸어 링크 조건을 맞추니 통과했습니다.

예전 글에는 configure에는 ASAN을 걸면 안 된다고 적어 뒀는데, 그건 `CFLAGS="-fsanitize=address"`를
직접 넣었을 때 얘기입니다. `AFL_USE_ASAN`은 AFL++가 포크 서버와의 충돌까지 처리해 주는 경로라
configure와 make 양쪽에 똑같이 걸어 주는 게 맞습니다.

### 4-2. 빠진 한 줄

퍼징을 돌리기 전에 4.9.1과 4.9.2의 `print-bootp.c`를 그냥 비교해 봤습니다. 차이가 딱 한 줄입니다.

![4.9.1과 4.9.2의 print-bootp.c diff. 추가된 줄은 ND_TCHECK(bp->bp_flags); 하나뿐이고, 아래에 ND_TCHECK가 걸린 필드 목록으로 307행 bp_secs, 331행 bp_ciaddr, 336행 bp_yiaddr가 표시된 화면](/assets/img/fuzzing101/ex3-diff.png)

BOOTP 헤더에서 `bp_secs`는 오프셋 8~9, `bp_flags`는 10~11, `bp_ciaddr`는 12~15입니다. `bp_secs`에도
`ND_TCHECK`가 있고 `bp_ciaddr`에도 있는데 사이에 낀 `bp_flags`만 없습니다. 캡처된 데이터가 오프셋
10이나 11에서 끝나면 그 2바이트 읽기가 밖으로 나갑니다.

조건이 하나 더 있습니다. 바로 위에 `if (!ndo->ndo_vflag) return;`가 있어서 `-v` 이상이어야 여기까지
옵니다. 그리고 그보다 위에는 이런 검사가 있습니다.

```c
if (bp->bp_htype == 1 && bp->bp_hlen == 6 && bp->bp_op == BOOTPREQUEST) {
	ND_TCHECK2(bp->bp_chaddr[0], 6);      /* chaddr 는 오프셋 28 */
	...
}
```

BOOTP 요청 패킷이면 오프셋 28의 MAC 주소를 먼저 검사합니다. 10바이트짜리로 잘린 패킷은 여기서
걸려 `[|bootp]`를 찍고 돌아갑니다. 그러니까 요청이 아니라 응답(op=2)이어야 이 검사를 건너뛰고
`bp_flags`까지 갑니다. 여기까지가 돌리기 전에 알아낸 트리거 조건입니다.

### 4-3. 안 나오는 크래시

BOOTP를 확실히 타는 DHCP 캡처만 골라 시드로 넣고 돌렸습니다.

```console
$ afl-fuzz -i seeds/pcap -o out/tcpdump -M main -- install/tcpdump/sbin/tcpdump -e -vv -nr @@
```

3시간 39분, 181만 회. 크래시 0. 시드를 손봐 2시간 더. 여전히 0. Xpdf가 6분, libexif가 79초였던 걸
생각하면 이상했습니다.

### 4-4. snaplen이 정하는 판정

퍼저를 더 돌리는 대신 애초에 도달 가능한 경로인지 손으로 확인해 보기로 했습니다. pcap 레코드의
캡처 길이를 한 바이트씩 줄여 가며 tcpdump를 돌렸습니다. 그랬더니 이런 게 나왔습니다.

```
BOOTP/DHCP, Reply, length 310, hops 1, xid 0x68c4847, Flags [Broadcast] (0xbebe)
```

`0xbebe`. ASAN이 갓 할당한 힙을 채워 두는 값입니다. tcpdump가 패킷 밖의 바이트를 읽어서 그대로
찍고 있습니다. 취약점은 정확히 재현되고 있었습니다. 그런데 ASAN은 아무 말이 없습니다.

이유는 libpcap이 패킷을 담는 버퍼를 어떻게 잡느냐에 있었습니다.

```c
/* sf-pcap.c */
394:  p->bufsize = p->snapshot;        /* snapshot = pcap 글로벌 헤더의 snaplen */
401:  p->buffer = malloc(p->bufsize);
596:  hdr->caplen = p->bufsize;        /* caplen 이 버퍼보다 크면 깎아 버린다 */
```

버퍼 크기는 pcap 글로벌 헤더의 snaplen이 정합니다. 제 시드들은 전부 snaplen이 262144였습니다.
캡처 길이를 52바이트로 줄여도 버퍼는 여전히 256KB이고, 그 두 바이트 밖을 읽는 건 같은 할당 안입니다.
ASAN이 잡을 이유가 없습니다.

그래서 캡처 길이는 그대로 두고 snaplen만 바꿔 봤습니다.

![세 가지 실험 결과. ① caplen만 자르고 snaplen을 크게 두면 ASAN은 조용하고 Flags 값에 0xbebe가 그대로 찍힌다. ② snaplen을 캡처 길이에 붙이면 같은 읽기가 heap-buffer-overflow로 잡히고, 읽힌 메모리를 할당한 곳이 sf-pcap.c:401로 나온다. ③ 버퍼 크기를 정하는 libpcap 소스 세 줄](/assets/img/fuzzing101/ex3-snaplen.png)

snaplen을 52나 53으로 두는 순간 `print-bootp.c:325`에서 heap-buffer-overflow가 뜹니다. 리포트의
allocated by 항목이 `pcap_check_header ./sf-pcap.c:401`을 가리킵니다. 그 malloc이 곧 버퍼입니다.
게다가 `sf-pcap.c:596`이 캡처 길이를 버퍼 크기로 깎아 주기 때문에, 레코드는 건드릴 필요도 없이
글로벌 헤더의 snaplen 하나만 52나 53이면 터집니다.

그러니까 이 크래시의 조건은 4바이트 필드 하나가 정확히 두 값 중 하나가 되는 것입니다. 그리고
여기가 핵심인데, 거기까지 가는 중간 보상이 없습니다. 제 시드는 그 값이 262144(`0x00040000`)라
52로 가려면 바이트 두 개를 한 번에 맞춰야 합니다. 하나만 바꾸면 여전히 거대한 수라 동작이 똑같고,
커버리지가 그대로니 퍼저 입장에서는 아무 신호가 없습니다. 커버리지 피드백이 길을 안내해 주지
못하는 구간입니다. 시드에 그 필드의 다양성이 0이었다는 게 진짜 원인이었습니다.

### 4-5. 시드와 전략 재설계

확인해 보니 tcpdump 저장소의 `tests/` 폴더에는 snaplen이 한 자리 수인 pcap이 이미 여럿 들어
있습니다. 파일 이름이 전부 `*-heapoverflow-*.pcap`입니다. 예전에 누군가 퍼징으로 찾은 버그들의
회귀 테스트가 그대로 남아 있는 겁니다.

```console
$ 시드 중 snaplen 이 17~88 인 것
  snaplen 17   stp-heapoverflow-3.pcap
  snaplen 34   ipcomp-heapoverflow.pcap
  snaplen 42   isoclns-heapoverflow-2.pcap
  snaplen 46   tcp_header_heapoverflow.pcap
  snaplen 48   heapoverflow-ip_print_demux.pcap
  ... 총 24개
```

원본 실습이 시드로 `tests/` 폴더를 통째로 지정하는 이유가 여기 있었습니다. 저는 BOOTP를 타는
것만 고르는 게 효율적이라고 생각해서 네 개로 줄였는데, 그게 정확히 퍼저의 손발을 묶은 선택이었습니다.

전략을 세 가지로 고쳤습니다. 첫째, 시드를 `tests/` 232개 전부로 바꿨습니다. 둘째, AFL의 결정적
단계(`-D`)를 도는 인스턴스를 넷 섞었습니다. arith 단계는 값에 1~35를 더하고 빼는데, snaplen이 34나
46인 파일이라면 그 한 번으로 52에 닿습니다. AFL++는 결정적 단계가 기본으로 꺼져 있어 켜 줘야
합니다. 셋째, 인자에서 `-XX`(패킷 헥스덤프)를 뺐습니다. 이 버그는 `-v` 이상이면 도달하는데
헥스덤프는 출력 비용만 크게 올립니다. 실측으로 초당 150회에서 2500회로 올라갔습니다.

```console
$ afl-fuzz -m none -i tests/ -o out/tcpdump -M main -- install/sbin/tcpdump -e -vv -nr @@
$ afl-fuzz -m none -i tests/ -o out/tcpdump -S detD1 -D -- ...   # 결정적 단계 켠 인스턴스
```

시드를 232개로 바꾸자마자 커버리지가 6.8%에서 15%로 올라갔습니다. 그리고 얼마 지나지 않아 크래시가
들어오기 시작했습니다. 절반 이상이 `-D`를 켠 인스턴스에서 나왔습니다.

![AFL++ 상태 화면. detD3 인스턴스가 39분 14초 동안 40만 3천 회 실행, saved crashes 4, total crashes 0(4 saved), corpus count 3125를 보이고 있다](/assets/img/fuzzing101/ex3-afl.png)

### 4-6. 크래시 분류

Xpdf에서 하던 대로 전부 ASAN에 다시 먹여 시그니처로 묶었습니다. 네 종류로 갈렸는데, 넷 다 제가
노리던 BOOTP가 아니었습니다.

![크래시 입력을 다시 먹여 묶은 결과. global-buffer-overflow가 bittok2str_internal(util-print.c:540)에서 3회, heap-buffer-overflow가 ospf6_print_lshdr(print-ospf6.c:395)에서 3회, ieee802_15_4_if_print(print-802_15_4.c:161)에서 1회, print_attr_string(print-radius.c:543)에서 1회. 아래에 tcpdump 4.9.2 CHANGES의 CVE 항목들이 표시된 화면](/assets/img/fuzzing101/ex3-buckets.png)

번호는 추측하지 않고 tcpdump가 4.9.2 `CHANGES`에 직접 적어 둔 것을 봤습니다. 넷 중 셋은 파서
이름이 그대로 적혀 있어 바로 맞춰집니다.

### 4-7. bittok2str_internal (CVE-2017-13011)

가장 많이 나온 것부터 봅니다. ASAN이 `global-buffer-overflow`를 보고합니다.

![ASAN global-buffer-overflow 리포트. bittok2str_internal(util-print.c:540) → bittok2str → lldp_private_8023_print(print-lldp.c:872) → lldp_print → ethertype_print → ether_print 프레임과, 넘친 대상이 util-print.c:524에 정의된 256바이트 전역 bittok2str_internal.buf이며 그 내용이 10BASE-T hdx로 시작하는 이더넷 속도 목록이라는 설명이 표시된 화면](/assets/img/fuzzing101/ex3-crash.png)

읽고 나니 이야기가 분명합니다. LLDP 패킷의 IEEE 802.3 TLV를 찍는 `lldp_private_8023_print`가
자동협상 지원 속도 비트맵을 문자열로 바꾸려고 `bittok2str`를 부릅니다. 그 안의 전역 버퍼가
256바이트인데, 비트를 많이 켜 두면 `10BASE-T hdx, 10BASE-T fdx, 100BASE-T4, ...`가 줄줄이 붙어
넘칩니다. 넘친 자리는 ASAN이 `bittok2str_internal.buf` 바로 뒤 4바이트라고 정확히 짚어 줍니다.

넘치는 방식이 흥미롭습니다.

![4.9.1의 bittok2str_internal 코드에서 static char buf[256]과 buflen += snprintf(buf+buflen, sizeof(buf)-buflen, ...) 부분, tcpdump 4.9.2 CHANGES의 Fix buffer overflow vulnerabilities 항목에 CVE-2017-11543(SLIP)과 CVE-2017-13011(bittok2str_internal)이 적혀 있는 부분, 그리고 4.9.2가 snprintf 누적을 strlcpy와 space_left 추적으로 바꾼 diff가 함께 표시된 화면](/assets/img/fuzzing101/ex3-bittok.png)

```c
/* util-print.c:524 — 4.9.1 */
static char buf[256];
int buflen = 0;
...
buflen += snprintf(buf + buflen, sizeof(buf) - buflen, "%s%s", sepstr, lp->s);
```

`snprintf`는 실제로 쓴 길이가 아니라 쓰려고 했던 길이를 돌려줍니다. 잘려도 원래 길이를 반환합니다.
그래서 `buflen`이 256을 넘어서면 그 다음 호출에서 `sizeof(buf) - buflen`이 `size_t`로 언더플로해
어마어마한 수가 되고, `buf + buflen`은 이미 버퍼 밖을 가리킵니다. 경계를 재는 계산이 스스로
무너지는 구조입니다. libexif에서 본 것과 결이 같습니다.

`CHANGES`의 Fix buffer overflow vulnerabilities 목록에 `CVE-2017-13011 (bittok2str_internal)`이
그대로 적혀 있습니다. 4.9.2는 버퍼를 1025바이트로 키우고, `snprintf` 누적을 `strlcpy`와
`space_left` 추적으로 바꿔 남은 공간이 없으면 그 자리에서 돌아가게 고쳤습니다.

### 4-8. IEEE 802.15.4 (CVE-2017-13000)

한 건은 `ieee802_15_4_if_print`의 `print-802_15_4.c:161`에서 났습니다. 그 자리를 보면 이렇습니다.

```c
/* print-802_15_4.c — 4.9.1 */
case 0x02:
	if (!(fc & (1 << 6))) {
		panid = EXTRACT_LE_16BITS(p);   /* caplen 을 안 본다 */
		p += 2;
	}
	ND_PRINT((ndo,"%04x:%04x ", panid, EXTRACT_LE_16BITS(p)));
	p += 2;
```

주소 지정 모드에 따라 PAN ID와 주소를 읽는데, 남은 캡처 길이를 확인하지 않고 그냥 2바이트씩
전진합니다. 4.9.2는 이 파서를 통째로 다시 쓰면서 읽기마다 `if (caplen < 2) { ... return; }`을
넣고 `caplen`을 같이 깎도록 고쳤습니다. `CHANGES`에는 `CVE-2017-13000 (IEEE 802.15.4)`으로 적혀
있습니다.

### 4-9. OSPFv3

가장 많이 나온 자리는 `ospf6_print_lshdr`의 `print-ospf6.c:395`였습니다.

```c
/* print-ospf6.c:390 — 4.9.1 */
if ((const u_char *)(lshp + 1) > dataend)
	goto trunc;
ND_TCHECK(lshp->ls_type);
ND_TCHECK(lshp->ls_seq);

ND_PRINT((ndo, "\n\t  Advertising Router %s, seq 0x%08x, age %us, length %u",
       ipaddr_string(ndo, &lshp->ls_router),
       EXTRACT_32BITS(&lshp->ls_seq),
       EXTRACT_16BITS(&lshp->ls_age),
       EXTRACT_16BITS(&lshp->ls_length) - (u_int)sizeof(struct lsa6_hdr)));
```

`struct lsa6_hdr`의 필드 순서는 `ls_age, ls_type, ls_stateid, ls_router, ls_seq, ls_chksum,
ls_length`입니다. `ND_TCHECK(ls_seq)`는 `ls_seq`까지만 보장하는데, 바로 다음 줄에서 그 뒤에 있는
`ls_length`를 읽습니다. 앞의 `(lshp + 1) > dataend` 검사는 OSPF 헤더의 길이 필드에서 계산한
`dataend`를 쓰기 때문에, 실제로 캡처된 끝(`snapend`)보다 뒤일 수 있습니다.

`CHANGES`에는 `CVE-2017-13036 (OSPFv3)`이 있습니다. 그런데 4.9.2가 `print-ospf6.c`에 추가한
`ND_TCHECK`는 `hello_options`, `db_options`, `llsa_nprefix` 세 자리뿐이고, 제 크래시 지점은 그
셋에 들어 있지 않습니다. 이 자리는 한참 뒤에 tcpdump가 모든 읽기를 경계 검사가 내장된 `GET_*`
접근자로 갈아치우면서 정리됐습니다. 그러니 OSPFv3 파서에서 힙 경계를 넘어 읽는다까지는 확실하고,
그게 CVE-2017-13036과 같은 항목인지는 확인하지 못했습니다. 이건 그대로 적어 둡니다.

### 4-10. RADIUS (CVE-2017-13032)

마지막 한 건은 `print_attr_string`의 `print-radius.c:543`입니다. 함수 맨 앞에 `ND_TCHECK2`로 원래
길이만큼 검사를 하긴 하는데, 그 뒤 `case` 분기들이 `data++; length--;`로 커서를 옮깁니다.

![ASAN heap-buffer-overflow 리포트. print_attr_string(print-radius.c:543) → radius_attrs_print → radius_print → ip_print_demux 프레임, 4.9.1의 for (i=0; *data && i < length; i++, data++) 루프, 4.9.2가 EGRESS_VLAN_NAME 분기에 if (length < 1) goto trunc를 추가한 diff, 그리고 CHANGES의 CVE-2017-13032 (RADIUS) 항목이 함께 표시된 화면](/assets/img/fuzzing101/ex3-radius.png)

`length`는 부호 없는 정수입니다. `length`가 0인 상태로 `length--`를 하면 `0xFFFFFFFF`가 되고,
함수 끝의 루프가 그 값을 믿고 돕니다.

```c
/* print-radius.c:543 — 4.9.1 */
for (i = 0; *data && i < length; i++, data++)
    ND_PRINT((ndo, "%c", (*data < 32 || *data > 126) ? '.' : *data));
```

4.9.2는 각 분기에서 커서를 옮기기 전에 `if (length < 1) goto trunc;`를 넣었습니다. libexif와
`bittok2str_internal`에서 본 것과 또 같은 모양입니다. 길이를 부호 없는 정수로 들고 다니다가 한 번
빼는 순간 검사가 무의미해집니다. `CHANGES`에는 `CVE-2017-13032 (RADIUS)`로 적혀 있습니다.

노린 CVE는 하나도 안 나왔지만, 이게 퍼징의 성격이라고 생각합니다. 저는 BOOTP 파서의 빠진 한 줄을
보고 들어갔고, 퍼저는 232개 시드를 훑다가 LLDP·OSPFv3·802.15.4·RADIUS에서 다른 걸 물어 왔습니다.
사람이 코드를 읽어 가설을 세우는 일과 퍼저가 아무 편견 없이 훑는 일은 서로 다른 걸 찾습니다.

### 4-11. 패치와 검증

원본 실습의 마지막 단계는 직접 고치기입니다. 두 군데를 고쳤습니다. BOOTP 쪽은 4.9.2가 넣은
`ND_TCHECK(bp->bp_flags);` 한 줄을 그대로 넣었고, `bittok2str_internal`은 4.9.2의 함수를 통째로
가져왔습니다.

![패치된 print-bootp.c의 325행과, 같은 PoC를 두 바이너리에 먹인 결과. 원본은 print-bootp.c:325에서 heap-buffer-overflow를 보고하고, 한 줄 넣은 빌드는 ASAN 보고 없이 [|bootp]로 잘렸다고 표시하며 정상 종료한다](/assets/img/fuzzing101/ex3-fix.png)

`ND_TCHECK`는 읽으려는 위치가 `ndo_snapend`를 넘는지 보고 넘으면 `trunc` 라벨로 점프하는
매크로입니다. 원본은 `print-bootp.c:325`에서 힙 밖을 읽고, 한 줄 넣은 빌드는 그 자리에서 멈춰
`[|bootp]`를 찍습니다. 두 바이트짜리 경계 검사 하나가 전부였습니다.

두 PoC를 두 바이너리에 나란히 먹여 봤습니다.

![원본 4.9.1과 두 자리를 고친 빌드에 같은 입력 두 개를 먹인 결과. 퍼저가 찾은 CVE-2017-13011 입력은 원본에서 global-buffer-overflow, 고친 빌드에서는 autonegotiation supported enabled 0x03을 정상 출력한다. 분석으로 찾은 CVE-2017-13028 입력은 원본에서 heap-buffer-overflow, 고친 빌드에서는 [|bootp]로 정상 종료한다](/assets/img/fuzzing101/ex3-fix2.png)

고친 빌드는 LLDP 자동협상 정보를 잘린 데 없이 제대로 찍고, 잘린 BOOTP 패킷은 `[|bootp]`로
표시하고 멈춥니다. 둘 다 원인 그대로 막혔습니다.

여기서 사고를 한 번 냈습니다. 패치본을 같은 소스 트리에서 빌드했는데 configure가 실패했고, `make`가
예전 Makefile을 그대로 써서 `make install`이 퍼징 중이던 원본 바이너리를 패치본으로 덮어썼습니다.
다행히 곧 알아차려서 원본을 다시 빌드해 넣고 퍼징도 처음부터 다시 시작했습니다. 고친 버전과 안
고친 버전을 같이 두려면 소스 트리부터 따로 떼어 놓는 게 맞습니다. tcpdump의 configure가
`../libpcap-<버전>`을 상대경로로 찾으니, 복사한 트리 옆에 libpcap 심볼릭 링크도 같이 걸어 줘야
합니다.

---

## 마치며

세 문제에서 확인한 취약점을 다시 적어 두면 이렇습니다. Xpdf 3.02에서 CVE-2019-13288과 CVE 번호를
특정하지 못한 NULL 역참조 하나, libexif 0.6.14에서 CVE-2012-2836과 CVE-2009-3895, tcpdump 4.9.1에서
CVE-2017-13011과 CVE-2017-13000과 CVE-2017-13032, OSPFv3 파서의 경계 읽기 하나, 그리고
CVE-2017-13028입니다.
CVE-2017-13028만 4.9.1과 4.9.2의 차이를 읽고 조건을 세워 직접 만들었고 나머지는 전부 퍼저가
찾았습니다. tcpdump는 두 자리를 고쳐서 같은 입력이 더는 안 터지는 것까지 확인했습니다.

ASAN은 공짜가 아니고 모든 버그에 필요하지도 않았습니다. Xpdf의 스택 소진은 계측 없이도 SIGSEGV로
잡힙니다. 반대로 tcpdump의 2바이트 경계 읽기는 ASAN 없이는 아무 일도 일어나지 않습니다. 퍼징은
빠른 빌드로, 원인 추적은 ASAN 빌드로 나누는 편이 낫습니다. 같은 소스를 두 벌 만드는 비용은 디스크
몇백 메가입니다.

계측은 링크 경계를 넘어 일관돼야 합니다. 라이브러리를 ASAN으로 만들었으면 그걸 검사하는 configure도
같은 조건이어야 합니다. 아니면 함수가 없다는 엉뚱한 메시지를 받고 한참 헤맵니다.

크래시 파일 개수는 아무것도 말해 주지 않습니다. ASAN 리포트의 유형과 상위 프레임으로 묶어야 비로소
버그가 몇 개인지 보입니다. Xpdf는 크래시 지점이 둘로 갈렸지만 원인은 하나였습니다.

하네스가 부르는 만큼만 찾을 수 있습니다. libexif의 `exif_entry_fix` 버그는 하네스에
`exif_data_fix` 한 줄이 있었기 때문에 나왔습니다. 그 줄이 없으면 몇 시간을 돌려도 그 코드에는
닿지 않습니다.

그리고 시드가 오라클을 결정합니다. 이번에 제일 크게 배운 대목입니다. tcpdump에서 크래시가 늦은 건
시간이 부족해서가 아니라, 취약점 판정에 필요한 필드가 시드에 단 한 종류만 있었기 때문입니다.
커버리지 피드백은 한 걸음씩 좋아지는 방향만 안내합니다. 두 바이트를 동시에 맞춰야 하는 구간에서는
도움을 주지 못하고, 그런 구간은 시드가 미리 넘어가 있어야 합니다. 원본 실습이 `tests/` 폴더를
통째로 시드로 쓰라고 한 데에는 이유가 있었습니다. 저는 그걸 불필요한 시드가 많다고 읽고 줄였다가
다섯 시간을 버렸습니다.

퍼징이 돌려 놓고 기다리는 일이라고 생각했는데, 실제로 해 보니 기다리는 시간보다 읽고 고르는 시간이
훨씬 길었습니다. 무엇을 계측할지, 무엇으로 판정할지, 어디서 시작할지를 정하는 게 대부분이고 퍼저는
그 안에서만 움직입니다. 크래시가 안 나올 때 더 돌리자가 아니라 왜 안 나오지를 물어본 게 이번에 제일
잘한 일이었습니다. 그리고 그렇게 조건을 고쳐 준 다음에는, 제가 안 보고 있던 LLDP·OSPFv3·802.15.4
쪽은 물론 RADIUS 쪽에서까지 퍼저가 다른 것들을 물어 왔습니다. 사람이 읽어서 세우는 가설과 퍼저가 편견 없이 훑는 일이
각각 다른 걸 찾는다는 걸 이번에 나란히 봤습니다. 긴 글 읽어 주셔서 감사합니다.
