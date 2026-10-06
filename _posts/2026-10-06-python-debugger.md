---
layout: post
title: "Python 디버거를 직접 만들며 배운 것"
date: 2026-10-06 10:00:00 +0900
category: 개발
author: WTCY
tags: [Python, 디버거, sys.settrace, frame, f_locals, 바이트코드, The Debugging Book]
excerpt: "The Debugging Book 세 장을 읽고 sys.settrace 위에 명령줄 디버거를 만들었다. Exercise 2의 명령들과 조건부 중단점, jump, catch 를 구현하면서 프레임, f_locals, 바이트코드 줄 번호가 실제로 어떻게 움직이는지 Python 3.11과 3.13에서 확인한 기록."
---

[The Debugging Book](https://www.debuggingbook.org/)은 디버깅 도구를 파이썬으로 직접 만들어 보면서 원리를 익히게 하는 책이다. 이번에 읽은 것은 [Introduction to Debugging](https://www.debuggingbook.org/html/Intro_Debugging.html), [Tracing Executions](https://www.debuggingbook.org/html/Tracer.html), [How Debuggers Work](https://www.debuggingbook.org/html/Debugger.html) 세 장이다. 마지막 장의 Exercise 2가 요구하는 명령까지 구현하고, 쓰고 싶었던 기능을 몇 가지 더 추가해 `debugger.py` 파일 하나로 만들었다.

결과물은 이렇다.

- 디버거: [debugger.py](/assets/files/python-debugger/debugger.py) (표준 라이브러리만 사용)
- 메뉴얼: [debugger.py 사용 메뉴얼](/posts/python-debugger-manual/), 원본 [MANUAL.md](/assets/files/python-debugger/MANUAL.md)
- 예제와 테스트: [demo.py](/assets/files/python-debugger/demo.py), [test_debugger.py](/assets/files/python-debugger/test_debugger.py)

글에 실은 화면은 전부 Windows 콘솔에서 실제로 돌린 것을 캡처했다. 디버거 세션은 명령을 파일에 적어 두고 `-x` 옵션으로 넣었다. 읽은 명령을 프롬프트 뒤에 그대로 출력하게 해 두었기 때문에 직접 입력했을 때와 화면이 같다.

---

## 1. 실패에서 원인으로 거슬러 올라가기

첫 장은 도구 이야기보다 디버깅을 어떤 순서로 해야 하는지부터 다룬다. 책 전체에서 계속 쓰는 예제는 HTML 태그를 지우는 `remove_html_markup()` 이다.

```python
def remove_html_markup(s):
    tag = False
    quote = False
    out = ""

    for c in s:
        if c == '<' and not quote:
            tag = True
        elif c == '>' and not quote:
            tag = False
        elif c == '"' or c == "'" and tag:
            quote = not quote
        elif not tag:
            out = out + c

    return out
```

`<b>foo</b>` 는 `foo` 로 잘 바뀌는데 `"foo"` 를 넣으면 따옴표까지 사라진 `foo` 가 나온다. 책은 이런 실패가 생기는 과정을 이렇게 설명한다. 코드의 결함(defect)이 실행 중에 변수를 잘못된 값으로 만들고(책은 이를 infection이라고 부른다), 그 값이 다른 값에까지 영향을 주다가 결국 눈에 보이는 실패(failure)로 나타난다. 그래서 디버깅은 실패에서 출발해 잘못된 값이 어디서 처음 생겼는지 거꾸로 찾아가는 일이 된다. 책은 이때 가설을 세우고 실험으로 확인하는 과학적 방법을 따르라고 강조한다.

가장 기억에 남은 건 "The Devil's Guide to Debugging" 절이다. 아무 데나 `print` 를 넣고, 증상이 사라질 때까지 코드를 이것저것 바꿔 보고, 눈앞의 증상만 막고 넘어가라고 비꼬는 내용인데, 읽다 보니 전부 내가 해 본 것들이었다. 프로그램 상태를 들여다볼 방법이 없으면 결국 감으로 코드를 고치게 된다. 디버거가 필요한 이유다.

## 2. 실행 중인 파이썬 프로그램 들여다보기

두 번째 장은 [sys.settrace()](https://docs.python.org/3/library/sys.html#sys.settrace) 에서 시작한다. 추적 함수를 등록하면 인터프리터가 이벤트가 생길 때마다 `traceit(frame, event, arg)` 를 부른다.

```python
def tracer(frame, event, arg):
    if frame.f_code.co_filename == __file__:
        print(f"{event:9} {frame.f_code.co_name:7} line {frame.f_lineno:2}  arg={arg!r}")
    return tracer

sys.settrace(tracer)
main()
sys.settrace(None)
```

`main()` 안에서 `square()` 를 두 번 부르는 작은 프로그램에 적용해 보면 이벤트가 어떤 순서로 오는지 바로 알 수 있다.

![events.py 실행 결과. call main line 8, line 9, line 10, line 11, call square line 4, line 5, line 6, return square arg=0, 다시 line 10, line 11 순으로 이벤트가 찍히고 마지막에 return main arg=1 이 나온다](/assets/img/python-debugger/01-settrace-events.png)

함수에 들어갈 때 `call`, 줄을 실행하기 직전마다 `line`, 빠져나갈 때 `return` 이 온다. `return` 의 `arg` 는 반환값이다. 예외가 생기면 `exception` 이벤트가 오고 `arg` 로 `(타입, 값, 트레이스백)` 튜플이 들어온다. `frame` 은 지금 실행 중인 함수의 상태를 담고 있는 객체다. 디버거 기능은 거의 다 이 프레임의 속성 몇 개만으로 만들 수 있었다.

| 속성 | 뜻 | 디버거에서 쓴 곳 |
|---|---|---|
| `f_lineno` | 지금 줄 번호 | 상태 출력, 줄 중단점, `until`, `jump` |
| `f_locals` | 지역 변수 | `print`, `assign`, `watch` |
| `f_globals` | 전역 변수 | 식 평가 |
| `f_back` | 이 함수를 부른 프레임 | `where`, `up`/`down`, `next` |
| `f_code.co_name`, `co_qualname` | 함수 이름 | 함수 이름 중단점 |
| `f_code.co_filename` | 소스 파일 | 소스 출력, 디버거 자신 걸러 내기 |

캡처를 보면 for 문이 있는 10번 줄이 반복할 때마다 다시 찍힌다. 루프 본문이 끝나고 for 줄의 `FOR_ITER` 로 되돌아갈 때마다 `line` 이벤트가 새로 생기기 때문이다. 이 동작은 뒤에서 `until` 과 `jump` 를 설명할 때 다시 나온다.

추적 함수가 무엇을 반환하는지도 중요하다. `sys.settrace()` 로 등록한 함수는 새 프레임이 생길 때 `call` 이벤트로만 불리는 전역 추적 함수이고, 여기서 함수를 돌려주면 그게 그 프레임의 지역 추적 함수(`frame.f_trace`)가 되어 `line` 과 `return` 을 받는다. `None` 을 돌려주면 그 프레임은 더 이상 추적하지 않는다. 그래서 책의 `Tracer` 는 늘 자기 자신을 돌려준다.

같은 이유로 `with Debugger():` 블록이 들어 있는 함수의 줄은 추적되지 않는다. `settrace` 는 이미 실행 중인 프레임에는 지역 추적 함수를 달아 주지 않기 때문이다. 블록 안에서 새로 부르는 함수부터 잡힌다. 책 코드에도 `inspect.currentframe().f_back.f_trace = self._traceit` 를 넣으면 현재 블록까지 추적된다는 주석이 남아 있다.

`with` 문이 정확히 어떻게 동작하는지도 이번에 제대로 알게 됐다. `with X():` 는 들어갈 때 `X.__enter__()`, 나올 때 예외가 났든 안 났든 `X.__exit__(타입, 값, 트레이스백)` 을 부른다. `Tracer` 는 `__enter__` 에서 기존 추적 함수를 `sys.gettrace()` 로 저장한 뒤 자기 함수를 걸고, `__exit__` 에서 원래 것으로 되돌린다. `__exit__` 가 참인 값을 돌려주면 블록 안에서 난 예외가 사라져 버리므로 `None` 을 돌려줘 디버깅 대상의 예외가 그대로 밖으로 나가게 한다.

## 3. 디버거의 기본 구조

세 번째 장을 읽으면서 추적 함수를 디버거로 만드는 방법이 생각보다 간단해서 놀랐다. 추적 함수 안에서 `input()` 을 부르기만 하면 된다. 사용자가 명령을 입력할 때까지 추적 함수가 반환하지 않으므로 그동안 프로그램도 멈춰 있다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 760 270" role="img" aria-label="디버거 구조. 인터프리터가 이벤트를 보내면 _traceit 가 디버거 자신의 프레임을 걸러 내고, stop_here 가 감시, 중단점, catch, mode 순으로 멈출지 정한다. 멈추면 interaction_loop 가 상태를 출력하고 명령을 받아 NAME_command 를 부른다. 실행 명령은 mode 를 정한 뒤 반환하고, 멈출 이유가 없으면 바로 반환해 실행이 이어진다">
  <style>
    .pd-box { fill: var(--surface); stroke: var(--rule-dark); stroke-width: 1.4; }
    .pd-hot { fill: var(--surface); stroke: var(--blue); stroke-width: 2; }
    .pd-t { fill: var(--ink); font-family: var(--mono); font-size: 13px; text-anchor: middle; }
    .pd-s { fill: var(--ink-soft); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .pd-a { stroke: var(--ink-soft); stroke-width: 1.6; fill: none; }
    .pd-r { stroke: var(--forest); stroke-width: 1.6; fill: none; stroke-dasharray: 5 4; }
    .pd-l { fill: var(--ink-faint); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .pd-head { fill: var(--ink-soft); }
    .pd-headr { fill: var(--forest); }
  </style>
  <defs>
    <marker id="pd-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="pd-head" d="M0,0 L10,5 L0,10 z"/></marker>
    <marker id="pd-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="pd-headr" d="M0,0 L10,5 L0,10 z"/></marker>
  </defs>
  <rect class="pd-box" x="16" y="92" width="160" height="80" rx="6"/>
  <text class="pd-t" x="96" y="118">인터프리터</text>
  <text class="pd-s" x="96" y="140">call · line</text>
  <text class="pd-s" x="96" y="158">return · exception</text>
  <rect class="pd-box" x="206" y="92" width="150" height="80" rx="6"/>
  <text class="pd-t" x="281" y="118">_traceit()</text>
  <text class="pd-s" x="281" y="140">frame, event, arg</text>
  <text class="pd-s" x="281" y="158">디버거 자신은 건너뜀</text>
  <rect class="pd-box" x="386" y="92" width="160" height="80" rx="6"/>
  <text class="pd-t" x="466" y="118">stop_here()</text>
  <text class="pd-s" x="466" y="140">감시 → 중단점</text>
  <text class="pd-s" x="466" y="158">→ catch → mode</text>
  <rect class="pd-hot" x="576" y="92" width="168" height="80" rx="6"/>
  <text class="pd-t" x="660" y="118">interaction_loop()</text>
  <text class="pd-s" x="660" y="140">상태 출력 → input()</text>
  <text class="pd-s" x="660" y="158">→ NAME_command()</text>
  <line class="pd-a" x1="176" y1="132" x2="203" y2="132" marker-end="url(#pd-ar)"/>
  <line class="pd-a" x1="356" y1="132" x2="383" y2="132" marker-end="url(#pd-ar)"/>
  <line class="pd-a" x1="546" y1="132" x2="573" y2="132" marker-end="url(#pd-ar)"/>
  <text class="pd-l" x="560" y="122">멈춤</text>
  <path class="pd-r" d="M660,92 L660,50 L96,50 L96,89" marker-end="url(#pd-arr)"/>
  <text class="pd-l" x="378" y="40">step · next · until · finish · continue 가 mode 를 정하고 반환</text>
  <path class="pd-r" d="M466,172 L466,214 L96,214 L96,175" marker-end="url(#pd-arr)"/>
  <text class="pd-l" x="281" y="236">멈출 이유가 없으면 그대로 반환하고 다음 이벤트까지 실행</text>
</svg>
</figure>

명령을 처리하는 방식도 깔끔했다. 디버거 클래스는 이름이 `_command` 로 끝나는 메서드를 전부 명령으로 취급한다. `dir(self.__class__)` 로 메서드 이름을 모으고, 사용자가 입력한 글자로 시작하는 명령이 하나뿐이면 `getattr(self, cmd + '_command')` 로 그 메서드를 찾아 호출한다. `help` 는 메서드의 독스트링을 출력하기만 한다. 그래서 명령을 하나 추가하려면 메서드 하나만 정의하면 된다.

```python
def command_method(self, command):
    if command.startswith('#'):
        return None
    cmds = self.commands_list()
    if command in cmds:  # 정확히 같은 이름이 있으면 접두사 검사보다 먼저
        return getattr(self, command + '_command')
    possible = [cmd for cmd in cmds if cmd.startswith(command)]
    if len(possible) != 1:
        self.help_command(command)
        return None
    return getattr(self, possible[0] + '_command')
```

이 방식 때문에 실수도 한 번 했다. 입력을 읽는 메서드 이름을 처음에 `read_command()` 로 지었더니 `help` 목록에 `read -- None` 이라는 명령이 생겼다. 메서드 이름만 보고 명령을 등록하기 때문이다. 메서드 이름을 `next_input()` 으로 바꿔 해결했다.

정확히 일치하는 이름을 먼저 보는 줄은 책 코드에 없던 것이다. 지금은 명령 이름끼리 접두사가 겹치는 경우가 없어 차이가 없지만, 나중에 `up` 과 `update` 같은 명령이 함께 생기면 `up` 을 입력해도 둘 중 어느 것인지 정할 수 없어 실행되지 않는다. 그래서 미리 막아 두었다.

## 4. Exercise 2: GDB 명령 따라 만들기

Exercise 2는 GDB의 명령을 따라 이름 중단점(`break FUNCTION`), `next`, `where`, `up`/`down`, `until`, `finish`, `watch` 를 만들라고 한다. 구현해 보니 이 명령들은 호출 스택을 보여 주는 명령과 실행을 어디까지 진행할지 정하는 명령으로 나뉘었다.

### 4.1 호출 스택 보여 주기: `f_back`

`where` 는 현재 프레임에서 `f_back` 을 따라 올라가며 프레임을 모으면 끝난다. 다만 그대로 올라가면 디버거 자신의 `__enter__` 나 스크립트를 `exec` 하는 `main()` 같은 프레임이 섞인다. 그래서 프레임의 `co_filename` 이 `debugger.py` 인 것은 건너뛰고, `with` 문이 있던 프레임(`__enter__` 에서 `sys._getframe(1)` 로 기억해 둔다)에서 멈춘다.

`up` 과 `down` 은 이 목록의 인덱스를 옮길 뿐이다. `print`, `list`, `assign` 이 이 인덱스로 고른 프레임을 대상으로 하니 호출한 쪽의 변수를 볼 수 있다. 문제 설명에는 "down returns to the caller" 라고 적혀 있는데, `up` 이 호출한 쪽으로 가는 명령이니 `down` 은 다시 안쪽(호출된 쪽)으로 돌아오는 게 맞다. GDB도 그렇게 동작해서 GDB와 같게 만들었다.

### 4.2 실행 제어: 기준 프레임으로 판단하기

`next`, `until`, `finish` 는 모두 어떤 프레임을 기준으로 어디까지 실행할지 정하는 명령이다. 명령을 받을 때 그 순간의 프레임을 `self.target` 에 기억해 두고, 이벤트가 올 때마다 아래 함수로 판단했다.

```python
def reached_target(self):
    if self.mode in ('step', 'continue'):
        return self.mode == 'step'
    frame, target = self.frame, self.target
    if frame is target:
        if self.mode == 'finish':
            return self.event == 'return'
        if self.mode == 'until':
            return (self.event == 'return' or
                    (self.event == 'line' and frame.f_lineno > self.until_line))
        return True  # next: 같은 프레임의 다음 이벤트
    # 기준 프레임보다 깊이 들어가 있으면 계속, 기준 프레임이 이미 반환했으면 멈춘다
    return not self.on_stack(target)
```

`next` 의 핵심은 마지막 줄이다. 지금 이벤트가 온 프레임의 `f_back` 사슬 안에 기준 프레임이 있으면 기준 프레임이 부른 함수 안에 들어와 있다는 뜻이므로 계속 실행한다. 사슬 어디에도 없으면 기준 프레임이 이미 반환한 것이므로, 호출한 쪽으로 돌아온 지점에서 멈춘다. 줄 번호나 호출 깊이를 세지 않고 같은 프레임 객체인지(`is`)만 보기 때문에 재귀 호출에서도 제대로 동작한다.

`until` 은 2절에서 본 for 줄의 `line` 이벤트와 관련이 있다. 루프 본문 마지막 줄에서 `until` 을 입력하면, 그 뒤에 실행되는 루프 안의 줄들은 번호가 모두 더 작아서 그냥 지나가고 루프가 끝난 다음 줄에서 멈춘다. `finish` 는 기준 프레임의 `return` 이벤트를 기다리면 된다. 예외로 함수를 빠져나갈 때도 `return` 이벤트는 오기 때문에(반환값 자리에 `None`) 따로 처리할 게 없었다.

`up` 을 한 다음 `finish` 를 입력하면 고른 프레임, 즉 호출한 쪽 함수가 끝날 때까지 실행된다. 기준을 현재 프레임이 아니라 `up`/`down` 으로 고른 프레임으로 잡았기 때문에 이렇게 쓸 수 있다.

![Exercise 2 명령 시연. break remove_html_markup 후 continue 로 함수 호출에서 멈추고, next 두 번, where 로 remove_html_markup, clean_all, module 세 프레임을 확인한 뒤 up 으로 clean_all 프레임의 pages, results, page 를 print 하고 list 로 소스를 본다. down 으로 돌아와 finish 하자 remove_html_markup() returns 'foo' 가 출력된다](/assets/img/python-debugger/03-exercise2-tour.png)

### 4.3 이름 중단점과 감시

`break remove_html_markup` 처럼 함수 이름을 받으면 `call` 이벤트에서 `f_code.co_name` 과 비교한다. Python 3.11에 생긴 `co_qualname` 도 함께 비교해서 `break Parser.feed` 처럼 클래스 메서드도 잡히게 했다. 줄 중단점은 `(파일, 줄)` 쌍으로 저장하고 `break util.py:12` 처럼 다른 파일도 지정할 수 있게 했다. 책 코드는 줄 번호만 저장해서, 디버깅하는 함수가 표준 라이브러리 함수를 부르면 그 파일의 같은 번호 줄에서도 멈춘다.

`watch` 는 책의 `EventTracer` 처럼 이벤트마다 식을 평가해 지난번 값과 비교한다. 값을 어떻게 비교할지 고민했다. 지난 값을 그대로 저장해 두었다가 `==` 로 비교하면, 리스트에 `append` 하는 경우 지난 값과 지금 값이 같은 객체라서 언제나 같다고 나온다. `copy.deepcopy` 는 복사할 수 없는 객체도 있고 무겁다. 결국 `repr()` 문자열을 저장해 비교했다. 제자리 변경도 잡히고, 화면에 보여 줄 값도 어차피 `repr` 이다. 대신 `<Foo object at 0x...>` 처럼 주소만 찍는 객체의 속성 변화는 놓치는데, 그때는 `watch obj.attr` 로 속성을 직접 보면 된다.

문제 설명에 있던 "변수가 항상 있는 것은 아니다" 라는 주의 사항도 실제로 겪었다. `quote` 를 감시하다가 다른 함수에 들어가면 `quote` 가 없으니 평가가 실패한다. 이걸 값의 변화로 치면 함수에 들어갈 때마다 멈춘다. 그래서 평가가 실패한 이벤트는 건너뛰고, 아직 정의되지 않은 변수를 감시하기 시작한 경우에만 `<undefined> -> False` 처럼 처음 값이 생기는 순간을 변화로 보고 멈추게 했다.

## 5. 이벤트 하나가 처리되는 전체 흐름

지금까지는 기능을 하나씩 설명했다. 이 기능들은 모두 같은 함수 안에서 정해진 순서로 검사된다. 인터프리터가 이벤트 하나를 보냈을 때 디버거가 프로그램을 계속 실행할지, 멈추고 명령을 받을지 정하는 과정을 처음부터 끝까지 따라가 보면 이렇다. 3절의 그림을 판단 순서까지 펼쳐 그린 것이다.

<figure style="margin: 0 0 1.6rem">
<svg viewBox="0 0 760 482" role="img" aria-label="이벤트 하나의 처리 흐름. _traceit 가 호출되면 디버거 자신의 프레임인지 보고, 맞으면 바로 반환한다. 아니면 traceit 가 상태를 저장하고, 감시와 중단점 검사에 걸리면 멈춘다. 걸리지 않았는데 exception 이벤트면 catch 가 켜져 있을 때만 멈춘다. 그 외에는 reached_target 이 step, continue, next, until, finish 에 따라 멈출지 정한다. 멈추면 interaction_loop 가 명령을 받고, 실행 명령이 mode 를 정하면 반환해 실행이 이어진다">
  <style>
    .pf-box { fill: var(--surface); stroke: var(--rule-dark); stroke-width: 1.4; }
    .pf-go { fill: var(--surface); stroke: var(--forest); stroke-width: 2; }
    .pf-stop { fill: var(--surface); stroke: var(--blue); stroke-width: 2; }
    .pf-t { fill: var(--ink); font-family: var(--mono); font-size: 13px; text-anchor: middle; }
    .pf-s { fill: var(--ink-soft); font-family: var(--sans); font-size: 12px; text-anchor: middle; }
    .pf-a { stroke: var(--ink-soft); stroke-width: 1.5; fill: none; }
    .pf-ag { stroke: var(--forest); stroke-width: 1.5; fill: none; }
    .pf-ab { stroke: var(--blue); stroke-width: 1.5; fill: none; }
    .pf-r { stroke: var(--forest); stroke-width: 1.5; fill: none; stroke-dasharray: 5 4; }
    .pf-l { fill: var(--ink-faint); font-family: var(--sans); font-size: 11.5px; text-anchor: middle; }
    .pf-h { fill: var(--ink-soft); }
    .pf-hg { fill: var(--forest); }
    .pf-hb { fill: var(--blue); }
  </style>
  <defs>
    <marker id="pf-m" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="pf-h" d="M0,0 L10,5 L0,10 z"/></marker>
    <marker id="pf-mg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="pf-hg" d="M0,0 L10,5 L0,10 z"/></marker>
    <marker id="pf-mb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="pf-hb" d="M0,0 L10,5 L0,10 z"/></marker>
  </defs>

  <rect class="pf-box" x="196" y="16" width="320" height="52" rx="6"/>
  <text class="pf-t" x="356" y="37">① _traceit(frame, event, arg)</text>
  <text class="pf-s" x="356" y="59">인터프리터가 이벤트마다 호출</text>
  <rect class="pf-box" x="196" y="88" width="320" height="52" rx="6"/>
  <text class="pf-t" x="356" y="109">② 디버거 자신의 프레임인가</text>
  <text class="pf-s" x="356" y="131">co_filename 이 debugger.py 인지 비교</text>
  <rect class="pf-box" x="196" y="160" width="320" height="52" rx="6"/>
  <text class="pf-t" x="356" y="181">③ traceit(): 상태 저장</text>
  <text class="pf-s" x="356" y="203">frame, event, arg 저장, f_locals 는 한 번만 읽기</text>
  <rect class="pf-box" x="196" y="232" width="320" height="52" rx="6"/>
  <text class="pf-t" x="356" y="253">④ 감시와 중단점</text>
  <text class="pf-s" x="356" y="275">watch 값 변화, 줄·함수 중단점과 조건</text>
  <rect class="pf-box" x="196" y="304" width="320" height="52" rx="6"/>
  <text class="pf-t" x="356" y="325">⑤ exception 이벤트인가</text>
  <text class="pf-s" x="356" y="347">맞으면 catch 설정만 보고 결정</text>
  <rect class="pf-box" x="196" y="376" width="320" height="52" rx="6"/>
  <text class="pf-t" x="356" y="397">⑥ reached_target()</text>
  <text class="pf-s" x="356" y="419">step 멈춤, continue 계속, 그 외 기준 프레임 비교</text>

  <line class="pf-a" x1="356" y1="68" x2="356" y2="85" marker-end="url(#pf-m)"/>
  <line class="pf-a" x1="356" y1="140" x2="356" y2="157" marker-end="url(#pf-m)"/>
  <line class="pf-a" x1="356" y1="212" x2="356" y2="229" marker-end="url(#pf-m)"/>
  <line class="pf-a" x1="356" y1="284" x2="356" y2="301" marker-end="url(#pf-m)"/>
  <line class="pf-a" x1="356" y1="356" x2="356" y2="373" marker-end="url(#pf-m)"/>
  <text class="pf-l" x="382" y="154">아니오</text>
  <text class="pf-l" x="384" y="298">안 걸림</text>
  <text class="pf-l" x="382" y="370">아니오</text>

  <rect class="pf-go" x="16" y="88" width="140" height="340" rx="6"/>
  <text class="pf-t" x="86" y="230">계속 실행</text>
  <text class="pf-s" x="86" y="252">self._traceit 반환</text>
  <text class="pf-s" x="86" y="270">다음 이벤트까지</text>
  <text class="pf-s" x="86" y="288">프로그램이 진행</text>
  <line class="pf-ag" x1="196" y1="114" x2="159" y2="114" marker-end="url(#pf-mg)"/>
  <text class="pf-l" x="177" y="107">예</text>
  <line class="pf-ag" x1="196" y1="330" x2="159" y2="330" marker-end="url(#pf-mg)"/>
  <text class="pf-l" x="177" y="323">off</text>
  <line class="pf-ag" x1="196" y1="402" x2="159" y2="402" marker-end="url(#pf-mg)"/>
  <text class="pf-l" x="177" y="395">아님</text>

  <rect class="pf-stop" x="556" y="232" width="188" height="196" rx="6"/>
  <text class="pf-t" x="650" y="262">interaction_loop()</text>
  <text class="pf-s" x="650" y="288">스택 수집, 상태 출력</text>
  <text class="pf-s" x="650" y="308">명령 입력 → NAME_command</text>
  <text class="pf-s" x="650" y="334">조회 명령이면 다시 입력</text>
  <text class="pf-s" x="650" y="360">실행 명령이면 mode, target</text>
  <text class="pf-s" x="650" y="380">설정 후 루프 종료</text>
  <line class="pf-ab" x1="516" y1="258" x2="553" y2="258" marker-end="url(#pf-mb)"/>
  <text class="pf-l" x="535" y="251">걸림</text>
  <line class="pf-ab" x1="516" y1="330" x2="553" y2="330" marker-end="url(#pf-mb)"/>
  <text class="pf-l" x="535" y="323">on</text>
  <line class="pf-ab" x1="516" y1="402" x2="553" y2="402" marker-end="url(#pf-mb)"/>
  <text class="pf-l" x="535" y="395">도달</text>

  <path class="pf-r" d="M650,428 L650,450 L86,450 L86,431" marker-end="url(#pf-mg)"/>
  <text class="pf-l" x="368" y="470">실행 명령이 정한 mode 를 가지고 반환하면 프로그램이 다시 진행된다</text>
</svg>
</figure>

단계별로 보면 다음과 같다.

1. 인터프리터가 `call`, `line`, `return`, `exception` 이벤트마다 `_traceit(frame, event, arg)` 를 호출한다.
2. 프레임의 `co_filename` 이 `debugger.py` 면 디버거 자신의 코드이므로 아무것도 하지 않고 바로 반환한다.
3. `traceit()` 이 `frame`, `event`, `arg` 를 저장하고 `frame.f_locals` 를 한 번만 읽어 `self.local_vars` 에 둔다(이유는 7.1절).
4. `stop_here()` 가 먼저 감시 식을 모두 평가하고, `line` 이벤트면 줄 중단점, `call` 이벤트면 함수 중단점과 그 조건을 확인한다. 하나라도 걸리면 그 이유를 모아 두고 멈춘다. 감시와 중단점은 지금 어떤 실행 명령 중이든 가장 먼저 본다. `next` 로 함수 호출을 건너뛰는 중이라도 그 함수 안에서 감시하는 값이 바뀌면 멈춘다.
5. 걸린 것이 없는데 `exception` 이벤트라면 `catch` 가 켜져 있을 때만 멈추고, 꺼져 있으면 아래 단계를 보지 않고 계속 실행한다.
6. 나머지 경우는 `reached_target()` 이 직전 실행 명령(`self.mode`)으로 정한다. `step` 이면 항상 멈추고, `continue` 면 항상 계속한다. `next`, `until`, `finish` 는 명령을 받을 때 기억해 둔 기준 프레임과 지금 프레임을 비교한다(4.2절).
7. 멈추기로 했으면 `interaction_loop()` 가 호출 스택을 모으고, 멈춘 이유와 현재 줄, `display` 식을 출력한 뒤 명령을 기다린다. `print`, `where`, `up`, `break`, `watch` 같은 조회·설정 명령은 실행한 뒤 다시 입력을 받는다.
8. `step`, `next`, `until`, `finish`, `continue`, `quit` 같은 실행 명령은 `mode` 와 기준 프레임을 정하고 `interact` 를 `False` 로 바꿔 입력 루프를 끝낸다. 그러면 추적 함수가 반환하고 프로그램이 다음 이벤트까지 진행한다. 다음 이벤트가 오면 1번부터 다시 시작하는데, 이때 방금 정한 `mode` 가 6번의 판단에 쓰인다.

코드로는 아래 두 함수가 이 흐름의 중심이다. 2번은 7.4절에서 다룬 `_traceit` 에, 6번은 4.2절의 `reached_target()` 에 있다.

```python
def traceit(self, frame, event, arg):
    self.frame, self.event, self.arg = frame, event, arg
    self.local_vars = frame.f_locals          # 3번: 한 번만 읽는다
    if self.stop_here():
        self.interaction_loop()               # 7, 8번: 명령을 받고 mode 를 정한다

def stop_here(self):
    self.reasons = self.watch_changes() + self.breakpoint_hits()   # 4번
    if self.reasons:
        return True
    if self.event == 'exception':             # 5번
        return self.catch
    return self.reached_target()              # 6번
```

이 순서는 일부러 정한 것이다. 감시를 `catch` 보다 먼저 보는 이유는 6절에서 설명한다. 실행 명령은 "다음에 어디서 멈출지" 를 정하기만 하고 실제 판단은 다음 이벤트들이 들어올 때마다 6번에서 이루어진다는 점도 이 흐름에서 드러난다. 예를 들어 `next` 는 명령을 친 순간 무언가를 실행하는 것이 아니라, 앞으로 오는 이벤트마다 기준 프레임과 비교할 수 있게 `target` 을 남겨 두는 명령이다.

## 6. 메뉴얼을 먼저 쓰고 기능 더하기

과제는 추가할 명령을 구현하기 전에 메뉴얼에 먼저 적으라고 한다. 그래서 저장소의 첫 커밋은 코드 없이 `MANUAL.md` 만 들어 있다. 이름, 문법, 동작을 먼저 정해 두니 구현하다 애매한 부분이 생길 때마다 메뉴얼을 보고 결정할 수 있었다. 반대로 구현하면서 메뉴얼에 빠진 내용을 찾기도 했다. 초안에는 "예외 이벤트에서는 `catch` 가 켜져 있을 때만 멈춘다" 고만 적었는데, 변수를 바꾼 줄에서 바로 예외가 나면 그 변화가 처음 보이는 이벤트가 `exception` 이다. 여기서 감시를 확인하지 않으면 변화를 놓친다. 그래서 감시와 중단점에 걸리지 않았을 때만 이 규칙을 적용한다고 문장을 고쳤다. 감시 값을 `repr` 로 비교한다는 것, `for` 줄로 `jump` 하면 루프가 처음부터 다시 돈다는 것도 구현해 보고 나서야 메뉴얼에 적을 수 있었다.

추가한 기능은 디버깅하면서 있었으면 했던 것들이다.

- 조건부 중단점 `break 17 if c == 'o'`: 루프 안 중단점은 조건이 없으면 쓸 수가 없다.
- `display EXPR`: 멈출 때마다 보고 싶은 식을 매번 `print` 하지 않아도 되게 한다.
- `jump LINE`: 다음에 실행할 줄을 바꾼다. 아래 7.3절에서 따로 다룬다.
- `catch on`, `catch off`: 예외가 발생하는 순간 멈춘다. `try`/`except` 로 처리되는 예외에서도 멈춘다.
- `info`: 중단점, 감시, 자동 표시, `catch` 상태를 한 번에 본다.
- 스크립트 모드 `python debugger.py script.py`: `with` 로 감싸지 않아도 파일 하나를 통째로 디버깅한다.
- 명령 파일 `-x CMDFILE`: GDB의 `-x` 처럼 명령을 파일에서 읽는다. 이 글의 캡처와 테스트는 모두 이 기능으로 만들었다.

스크립트 모드는 파이썬이 스크립트를 실행하는 방식을 그대로 따라 만들었다. 파일을 읽어 `compile(소스, 절대경로, 'exec')` 로 코드 객체를 만들고, `__name__` 을 `'__main__'` 으로 둔 새 이름공간에서 `exec` 한다. `compile` 에 넘긴 파일 이름이 코드 객체의 `co_filename` 이 되고, `linecache` 가 그 이름으로 소스 줄을 찾아온다. 여기에 엉뚱한 이름을 넣으면 디버거가 소스를 한 줄도 못 보여 준다. `sys.argv` 와 `sys.path[0]` 도 스크립트 기준으로 바꿔서 스크립트 입장에서는 직접 실행된 것과 구별이 안 되게 했다.

![추가 기능 시연. break 17 if c == 'o' 로 조건부 중단점을 걸고 continue 하자 out = 'f' 일 때 17번 줄에서 멈춘다. display out 을 등록하고 jump 9 로 for 줄로 이동한 뒤 delete 17, until 17 을 하자 19번 줄 return out 에서 out = 'ffoo' 로 멈춘다. assign out = out.upper() 후 finish 하자 'FFOO' 가 반환되고, catch on 과 info 로 상태를 확인한다](/assets/img/python-debugger/04-extras.png)

## 7. 구현하면서 알게 된 파이썬 실행 방식

디버거를 만드는 시간의 상당 부분은 코드를 쓰는 데가 아니라, 파이썬이 예상과 다르게 동작하는 이유를 확인하는 데 들었다. Python 3.11과 3.13을 둘 다 깔아 두고 같은 코드를 돌려 봤다.

### 7.1 `f_locals` 는 3.12까지 사본이었다

Exercise 1의 `assign` 은 추적 함수 안에서 `frame.f_locals[var] = value` 로 지역 변수를 바꾼다. 책은 "`f_locals` 는 접근할 때마다 다시 채워지니 한 번 읽은 별칭에 대입하라" 고 주의를 준다. 정말 그런지 실험했다. 추적 함수에서 `x` 를 99로 바꾼 뒤, 한 번은 그대로 두고 한 번은 `frame.f_locals` 를 한 번 더 읽기만 했다.

![flocals.py 실험 결과. Python 3.11.0 에서는 f_locals 타입이 dict 이고 once 는 99, reread 는 1 이다. Python 3.13.13 에서는 타입이 FrameLocalsProxy 이고 once 와 reread 모두 99 다](/assets/img/python-debugger/05-flocals-311-vs-313.png)

3.11에서 함수의 `f_locals` 는 진짜 변수가 아니라 변수 값을 복사해 둔 딕셔너리다. 속성을 읽을 때마다 실제 변수 값으로 이 딕셔너리를 다시 채우고, 추적 함수가 반환할 때 CPython이 현재 프레임의 딕셔너리를 실제 변수로 되돌려 쓴다. 그래서 대입한 뒤 한 번 더 읽으면 바꾼 값이 원래 값으로 덮이고(`reread: 1`), 결과적으로 대입이 사라진다. 3.13에서는 [PEP 667](https://peps.python.org/pep-0667/)로 `f_locals` 가 실제 변수에 바로 쓰는 `FrameLocalsProxy` 가 되어 이 문제가 없어졌다.

디버거에서는 이벤트마다 `frame.f_locals` 를 딱 한 번 읽어 `self.local_vars` 에 두고, 현재 프레임에 대한 읽기와 쓰기는 전부 이 별칭으로 한다. 되돌려 쓰기가 현재 프레임에만 일어난다는 점도 중요하다. 3.12 이하에서 `up` 으로 고른 바깥 프레임에 `assign` 하면 화면에는 바뀐 것처럼 보여도 프로그램에는 반영되지 않는다. 그래서 그 경우는 거부하고 메시지를 띄우게 했다. 테스트도 버전에 따라 기대값을 나눴는데, 3.13에서는 바깥 프레임의 리스트를 바꾸는 것까지 실제로 반영되는 것을 확인했다.

### 7.2 `eval` 속 컴프리헨션이 지역 변수를 못 본다

`print` 는 사용자가 친 식을 `eval(식, 전역, 지역)` 으로 평가한다. 그런데 3.11에서 `print [x for x in s if x != c]` 를 치면 `NameError: name 'c' is not defined` 가 난다.

```
(3, 11) NameError name 'c' is not defined
(3, 13) ['a', 'c']
```

3.11까지 리스트 컴프리헨션은 내부적으로 별도 함수로 컴파일된다. `eval` 에 지역 딕셔너리를 따로 넘기면 그 함수 안에서는 이 딕셔너리가 보이지 않고 전역만 보인다. 맨 앞의 `s` 는 바깥에서 평가되어 넘어가니 괜찮지만 조건식의 `c` 는 찾지 못한다. 3.12의 [PEP 709](https://peps.python.org/pep-0709/)가 컴프리헨션을 감싼 쪽 코드에 인라인하면서 이 차이가 사라졌고, 3.13에서는 실제로 잘 된다. 디버거에서는 평가용으로만 `{**f_globals, **지역 변수}` 를 합친 딕셔너리를 전역으로 넘겨 두 버전에서 같은 결과가 나오게 했다.

### 7.3 `jump` 는 줄이 아니라 바이트코드로 간다

`frame.f_lineno` 는 읽기 전용처럼 보이지만, [추적 함수 안의 `line` 이벤트에서는 대입할 수 있다](https://docs.python.org/3/reference/datamodel.html#frame.f_lineno). 대입하면 다음에 실행할 줄이 바뀐다. `jump` 명령은 이 한 줄로 구현했다. 루프 안으로 뛰어드는 것처럼 CPython이 허용하지 않는 점프는 `ValueError` 가 나므로 메시지만 보여 준다.

위 캡처에서 'o' 를 한 번 건너뛰려고 17번 줄에서 `jump 9` 로 for 줄로 갔다. 결과는 `'fo'` 가 아니라 `'ffoo'` 였다. 루프가 처음부터 다시 돈 것이다. 바이트코드를 보면 이유가 보인다.

```
>>> for ins in dis.get_instructions(remove_html_markup): ...
9 14 LOAD_FAST s
9 16 GET_ITER
9 18 FOR_ITER to 118
9 20 STORE_FAST c
```

9번 줄에는 `s` 로 새 반복자를 만드는 `GET_ITER` 와, 반복자에서 다음 값을 꺼내는 `FOR_ITER` 가 함께 들어 있다. 반복할 때 되돌아오는 곳은 `FOR_ITER`(오프셋 18)지만, `jump 9` 는 그 줄의 첫 명령인 `LOAD_FAST s`(오프셋 14)로 간다. 그래서 반복자를 새로 만들고 문자열을 처음부터 다시 읽었다. 소스 코드 한 줄은 바이트코드 여러 개로 이루어져 있고, 디버거가 말하는 "줄" 은 실제로는 바이트코드 위치를 줄 번호로 묶어 부르는 것이라는 걸 이 실험으로 알게 됐다.

### 7.4 디버거는 자기 자신을 추적하면 안 된다

추적 함수는 전역이라, 디버거가 명령을 처리하면서 부르는 파이썬 함수도 전부 이벤트를 만든다. `Tracer._traceit` 에서 프레임의 `co_filename` 이 디버거 파일과 같으면 아무것도 하지 않고 넘기는 이유다. 비교할 파일 이름은 `(lambda: None).__code__.co_filename` 으로 얻었다. 디버거 파일 안에서 만든 코드 객체의 `co_filename` 이므로, 이벤트로 들어오는 프레임의 `f_code.co_filename` 과 같은 방식으로 만들어진 값끼리 비교하게 된다. 직접 실행할 때와 `import` 할 때 모두 `__file__` 과 같은 절대 경로가 나오는 것도 확인했다.

`quit` 은 반대로 추적을 완전히 끈다. 책의 `quit` 은 중단점만 지우고 계속 실행하게 하는데, 그러면 프로그램이 끝날 때까지 이벤트마다 추적 함수가 불려서 계속 느리다. 책의 측정에서도 추적 중 실행은 수백 배 느렸다. 그래서 `sys.settrace(None)` 까지 불러 주었다.

## 8. 만든 디버거로 버그 찾기

이제 1절의 버그를 직접 잡아 볼 차례다. `"foo"` 에서 따옴표가 사라지니, 따옴표 안인지를 나타내는 `quote` 가 언제 뒤집히는지 보면 된다. `clean_all()` 이 페이지 세 개를 차례로 처리하므로 조건부 중단점으로 두 번째 호출에서만 멈추고 `watch quote` 를 걸었다.

![버그 추적 세션. break remove_html_markup if s == '"foo"' 로 두 번째 호출에서 멈추고 watch quote 를 건다. continue 두 번 만에 Watch quote: False -> True 가 뜨는데 이때 c 는 큰따옴표, tag 는 False 다. 14번 줄 조건 c == '"' or c == "'" and tag 는 True, 괄호로 묶은 (c == '"' or c == "'") and tag 는 False 로 나온다](/assets/img/python-debugger/06-find-bug.png)

태그 밖(`tag = False`)인데 `"` 를 만나자 `quote` 가 `True` 가 됐다. 14번 줄 조건을 그 자리에서 그대로 평가하면 `True`, 괄호를 넣어 의도대로 묶으면 `False` 다. 파이썬에서 `and` 는 `or` 보다 먼저 묶이므로 원래 조건은 `c == '"' or (c == "'" and tag)` 로 읽힌다. 큰따옴표는 태그 안팎을 가리지 않고 `quote` 를 뒤집었고, 그다음 분기인 `elif not tag:` 로 가지 못해 `out` 에 들어가지 않은 것이다. 조건을 `(c == '"' or c == "'") and tag` 로 고치면 된다.

따옴표 처리 코드를 짐작으로 고치지 않고, 잘못된 출력에서 시작해 값이 틀어진 변수(`quote`)를 찾고, 그 값이 처음 잘못 바뀐 줄(14번)까지 거슬러 올라갔다. 1절에서 책이 설명한 디버깅 과정을 직접 만든 도구로 해 본 것이다.

## 9. 테스트

명령이 늘수록 하나를 고치면 다른 게 깨지기 쉬워서 `test_debugger.py` 를 두었다. `Debugger(commands=[...], file=StringIO())` 로 명령을 미리 넣고, 출력에 기대한 문자열이 있는지와 함수의 반환값이 바뀌었는지를 본다. `assign` 은 출력이 아니라 반환값으로 확인했다. 디버거 안에서 바뀐 것처럼 보이는 것과 프로그램이 실제로 바뀐 것은 7.1절에서 봤듯이 다른 문제이기 때문이다. 스크립트 모드와 `-x` 는 하위 프로세스로 띄워 확인했고, 표준 입력을 닫아 두어서 명령 파일이 끝나면 `quit` 으로 처리되는 경우도 함께 확인한다.

![test_debugger.py 를 Python 3.11.0 과 3.13.13 에서 각각 실행한 화면. 3.11 에서는 assign in caller frame refused (<3.13), 3.13 에서는 assign in caller frame (3.13+) 항목이 ok 로 나오고 두 버전 모두 all passed 로 끝난다](/assets/img/python-debugger/07-tests.png)

## 10. 한계

`sys.settrace` 는 부른 스레드에만 걸린다. 다른 스레드는 디버거가 멈춰 있는 동안에도 계속 실행된다. `len` 이나 `sorted` 처럼 C로 구현된 함수 안은 파이썬 이벤트가 생기지 않아 들어갈 수 없다. `print`, `watch`, `display`, 중단점 조건은 모두 실제로 `eval` 되므로 함수 호출이 들어간 식은 부작용까지 일으킨다. 감시 식은 늘 지금 실행 중인 프레임에서 평가하기 때문에, GDB처럼 특정 프레임에 묶인 감시는 아직 없다.

속도도 문제다. 추적 함수가 모든 줄에서 불리고 감시 식을 매번 평가하니 무거운 루프에서는 체감될 만큼 느리다. Python 3.12에 들어온 [sys.monitoring](https://docs.python.org/3/library/sys.monitoring.html)(PEP 669)은 필요한 이벤트만, 필요한 코드 객체에만 켤 수 있다고 한다. 중단점이 걸린 줄에만 이벤트를 켜는 식으로 바꾸면 `continue` 가 거의 원래 속도로 돌 것 같아서 다음에 시도해 볼 생각이다.

---

## 참고 자료

- Andreas Zeller et al., [The Debugging Book](https://www.debuggingbook.org/): [Introduction to Debugging](https://www.debuggingbook.org/html/Intro_Debugging.html), [Tracing Executions](https://www.debuggingbook.org/html/Tracer.html), [How Debuggers Work](https://www.debuggingbook.org/html/Debugger.html), 노트북 원본은 [GitHub uds-se/debuggingbook](https://github.com/uds-se/debuggingbook/tree/master/notebooks)
- Python 문서 [sys.settrace](https://docs.python.org/3/library/sys.html#sys.settrace), [프레임 객체](https://docs.python.org/3/reference/datamodel.html#frame-objects), [dis](https://docs.python.org/3/library/dis.html), [sys.monitoring](https://docs.python.org/3/library/sys.monitoring.html)
- [PEP 667 – Consistent views of namespaces](https://peps.python.org/pep-0667/), [PEP 709 – Inlined comprehensions](https://peps.python.org/pep-0709/)
- [GDB 문서](https://sourceware.org/gdb/current/onlinedocs/gdb.html/): 명령 이름과 동작(`next`, `until`, `finish`, `watch`, `display`, `-x`)을 맞출 때 참고
