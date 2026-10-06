# debugger.py 사용 메뉴얼

The Debugging Book의 [How Debuggers Work](https://www.debuggingbook.org/html/Debugger.html) 장을 따라 만든 명령줄 파이썬 디버거다. 책의 기본 명령, Exercise 1(`assign`), Exercise 2(이름 중단점, `next`, `where`, `up`/`down`, `until`, `finish`, `watch`)를 모두 구현했고, 여기에 조건부 중단점, `display`, `jump`, `catch`, `info`, 스크립트 실행 모드, 명령 파일(`-x`)을 추가했다.

외부 패키지 없이 표준 라이브러리만 쓴다. Python 3.11과 3.13에서 `test_debugger.py` 로 테스트했다.

## 1. 실행 방법

### 1.1 스크립트 전체를 디버깅

```
python debugger.py [-x 명령파일] 스크립트.py [스크립트 인자...]
```

스크립트의 모듈 코드가 시작되는 순간 처음 멈춘다. `sys.argv` 는 `[스크립트.py, 스크립트 인자...]` 로 바뀌므로, 스크립트는 직접 실행했을 때와 똑같이 동작한다.

`-x 명령파일` 을 지정하면 프롬프트에서 입력을 받는 대신 파일에 적힌 명령을 한 줄씩 읽어 실행한다. 읽은 명령은 프롬프트 뒤에 그대로 출력되므로 직접 입력했을 때와 화면이 같다. 빈 줄과 `#` 으로 시작하는 줄은 건너뛴다. 파일의 명령을 다 쓰면 표준 입력에서 이어서 받고, 표준 입력도 닫혀 있으면 `quit` 으로 처리한다.

### 1.2 코드 안에서 일부만 디버깅

```python
from debugger import Debugger

with Debugger():
    remove_html_markup('<b>"x"</b>')
```

`with` 블록 안에서 호출된 함수만 추적하고, 블록이 끝나면 추적도 꺼진다. `with` 문이 있는 함수 자신의 줄은 추적하지 않으며, 블록 안에서 처음 호출되는 함수의 `call` 이벤트에서 처음 멈춘다.

## 2. 프롬프트와 명령 입력

멈출 때마다 현재 상태를 보여 주고 `(debugger)` 프롬프트를 띄운다.

| 멈춘 이벤트 | 출력 예 |
|---|---|
| 스크립트 시작 | `Running C:\work\demo.py` |
| 함수 호출(`call`) | `Calling remove_html_markup(s = '<b>foo</b>')` |
| 새 줄 실행 직전(`line`) | `17> out = out + c` (실제로는 소스 들여쓰기가 그대로 나온다) |
| 함수 반환(`return`) | `remove_html_markup() returns 'foo'` |
| 예외 발생(`exception`) | `Exception in risky(): ZeroDivisionError: division by zero` |

`line` 이벤트에서 멈췄는데 직전에 멈췄던 곳과 다른 함수라면 `[demo.py:17 remove_html_markup]` 처럼 위치를 먼저 보여 준다. 중단점이나 감시 때문에 멈춘 경우에는 그 이유(`Breakpoint demo.py:17`, `Watch quote: False -> True`)가 맨 위에 나온다.

직전에 멈췄던 곳과 같은 함수라면, 그 사이에 값이 바뀐 지역 변수를 소스 줄 위에 `# c = 'b', out = 'a'` 형태로 보여 준다. `display` 로 등록한 식은 그 아래에 나온다.

명령은 앞부분만 입력해도 된다. `s` 는 `step`, `p out` 은 `print out` 이다. 입력한 글자로 시작하는 명령이 여러 개면(`d` 는 `delete`, `display`, `down`) 후보 목록만 보여 주고 아무것도 실행하지 않는다. 빈 줄을 입력하면 직전 명령을 반복한다.

## 3. 명령어

표기법: `대문자` 는 직접 채워 넣는 값이고, `[ ]` 안은 생략할 수 있다.

### 3.1 실행 제어

| 명령 | 동작 |
|---|---|
| `step` | 다음 이벤트(호출, 줄, 반환)까지만 실행하고 멈춘다. 다음 줄이 함수 호출이면 그 함수 안으로 들어간다. |
| `next` | 현재 함수의 다음 줄까지 실행한다. 그 사이에 호출되는 함수 안으로는 들어가지 않는다. 현재 함수가 반환하면 반환 지점에서 멈춘다. |
| `until [LINE]` | 현재 함수에서 `LINE` 보다 큰 줄에 도달할 때까지 실행한다. `LINE` 을 생략하면 현재 줄 번호를 쓴다. 루프 본문의 마지막 줄에서 쓰면 루프가 끝난 다음 줄에서 멈춘다. 그 전에 함수가 반환하면 반환 지점에서 멈춘다. |
| `finish` | 현재 함수가 반환할 때까지 실행하고 반환 이벤트에서 멈춘다. |
| `continue` | 중단점, 감시 조건, `catch` 중 하나에 걸릴 때까지 실행한다. |
| `jump LINE` | 다음에 실행할 줄을 `LINE` 으로 바꾼다. 건너뛴 줄은 실행되지 않고, 이미 지난 줄로 돌아가 다시 실행할 수도 있다. 현재 함수의 `line` 이벤트에서만 쓸 수 있고, 루프 밖에서 루프 안으로 들어가는 것처럼 CPython이 허용하지 않는 이동은 오류 메시지만 보여 준다. 해당 줄의 첫 바이트코드로 이동하기 때문에, `for` 줄로 이동하면 반복자를 새로 만들어 루프가 처음부터 다시 시작된다. |
| `quit` | 중단점과 감시 조건을 모두 지우고 추적을 끈 뒤 프로그램을 끝까지 실행한다. |

`next`, `until`, `finish` 는 `up`/`down` 으로 고른 프레임을 기준으로 한다. 예를 들어 `up` 다음에 `finish` 를 쓰면 호출한 함수가 반환할 때까지 실행한다. 실행 도중 중단점이나 감시 조건에 걸리면 그곳에서 먼저 멈춘다.

### 3.2 중단점

| 명령 | 동작 |
|---|---|
| `break` | 중단점 목록을 보여 준다. |
| `break LINE [if COND]` | 현재 파일의 `LINE` 번째 줄에 중단점을 건다. |
| `break FILE:LINE [if COND]` | 다른 파일의 줄에 건다. `FILE` 은 파일 이름이나 경로의 뒷부분만 써도 된다(`util.py:12`). |
| `break FUNCTION [if COND]` | 이름이 `FUNCTION` 인 함수가 호출되는 순간(`call` 이벤트) 멈춘다. 메서드는 `Class.method` 로도 쓸 수 있다. 아직 정의되지 않은 함수에도 걸 수 있다. |
| `delete SPEC` | `break` 에 쓴 것과 같은 `LINE`, `FILE:LINE`, `FUNCTION` 으로 중단점을 지운다. 감시 식을 넣으면 그 감시를 지운다. |
| `delete` | 중단점과 감시 조건을 모두 지운다. |

`if COND` 를 붙이면 조건부 중단점이 된다. 그 줄(또는 함수 호출)에 도달했을 때 그 프레임의 변수로 `COND` 를 평가해 참일 때만 멈춘다. 평가하다 예외가 나면 멈추고 오류를 보여 준다. 같은 위치에 `break` 를 다시 쓰면 조건만 새로 바뀐다.

### 3.3 감시와 표시

| 명령 | 동작 |
|---|---|
| `watch EXPR` | 이벤트마다 `EXPR` 을 현재 프레임에서 평가해 값이 바뀌면 멈추고 `Watch quote: False -> True` 를 보여 준다. 인자 없이 쓰면 감시 목록을 보여 준다. |
| `display EXPR` | 멈출 때마다 `EXPR = 값` 을 자동으로 보여 준다. 인자 없이 쓰면 등록된 식을 지금 모두 보여 준다. |
| `undisplay [EXPR]` | 자동 표시를 하나 지운다. 인자가 없으면 전부 지운다. |

감시 식은 항상 지금 실행 중인 프레임에서 평가한다. 식을 평가할 수 없을 때(변수가 아직 없거나 다른 함수 안에 있을 때)는 값이 바뀐 것으로 보지 않는다. 아직 정의되지 않은 변수를 감시하면 값이 `<undefined>` 로 시작하고, 처음 값이 생기는 순간 `Watch quote: <undefined> -> False` 를 보여 주며 멈춘다.

값은 `repr()` 문자열로 비교한다. 그래서 리스트에 `append` 하는 것처럼 같은 객체의 내용이 바뀌어도 알아챈다. 반대로 `repr` 이 `<Foo object at 0x...>` 처럼 주소만 보여 주는 객체는 속성이 바뀌어도 알아채지 못하므로, 이럴 때는 `watch obj.attr` 처럼 속성을 직접 감시한다.

### 3.4 상태 보기와 바꾸기

| 명령 | 동작 |
|---|---|
| `print [EXPR]` | `EXPR` 을 선택한 프레임에서 평가해 보여 준다. 인자가 없으면 지역 변수를 모두 보여 준다. |
| `list [FUNCTION]` | 선택한 프레임의 함수 소스를 보여 준다. 현재 줄은 `>`, 중단점은 `#` 으로 표시한다. 모듈 수준에서는 파일 전체를 보여 준다. `FUNCTION` 을 주면 그 함수의 소스를 보여 준다. |
| `assign VAR=EXPR` | `EXPR` 을 평가해 지역 변수 `VAR` 에 넣는다. 프로그램은 바뀐 값으로 계속 실행된다. |
| `where` | 호출 스택을 안쪽부터 바깥쪽 순서로 보여 준다. 선택한 프레임에 `>` 를 붙인다. |
| `up` | 한 단계 바깥쪽(호출한 쪽) 프레임을 선택한다. `print`, `list`, `assign` 이 이 프레임을 대상으로 한다. |
| `down` | 한 단계 안쪽 프레임을 선택한다. |
| `catch [on\|off]` | 예외가 발생하는 순간 멈출지 정한다. 인자 없이 쓰면 켜져 있을 때는 끄고 꺼져 있을 때는 켠다. 처음에는 꺼져 있다. |
| `info` | 중단점, 감시 식, 자동 표시 식, `catch` 상태를 한꺼번에 보여 준다. |
| `help [COMMAND]` | 명령 목록이나 한 명령의 설명을 보여 준다. |

`up` 으로 고른 프레임의 변수를 `assign` 으로 바꾸는 것은 Python 3.13 이상에서만 실제 프로그램에 반영된다. 3.12 이하에서는 현재 실행 중인 프레임의 변수만 바꿀 수 있고, 다른 프레임에서 시도하면 실행하지 않고 메시지를 보여 준다(5절 참고).

## 4. 멈추는 조건

디버거는 이벤트가 올 때마다 아래 순서로 멈출지 정한다.

1. 감시 식을 모두 평가해 바뀐 것이 있으면 멈춘다.
2. `line` 이벤트면 줄 중단점, `call` 이벤트면 함수 중단점을 확인한다. 조건이 있으면 평가한다.
3. 위 두 경우가 아니고 `exception` 이벤트면 `catch` 가 켜져 있을 때만 멈춘다. `step` 중이어도 `catch` 가 꺼져 있으면 예외 이벤트에서는 멈추지 않는다.
4. 마지막으로 직전 명령(`step`, `next`, `until`, `finish`, `continue`)이 정한 위치인지 본다.

## 5. 제약

- 한 스레드만 추적한다. `sys.settrace` 는 그것을 호출한 스레드에만 적용되기 때문이다. 다른 스레드는 멈추지 않는다.
- C로 구현된 함수(`len`, `sorted` 등) 안으로는 들어갈 수 없다. 이런 함수 안에서는 파이썬 이벤트가 생기지 않기 때문이다.
- `print`, `watch`, `display`, 중단점 조건은 실제로 `eval` 된다. 식에 함수 호출이 있으면 그 함수가 실제로 실행되고, 함수가 상태를 바꾸면 그 변화도 프로그램에 남는다.
- 추적 중에는 프로그램이 수십에서 수백 배 느려진다. 반복이 많은 프로그램은 필요한 함수만 `with Debugger():` 로 감싸서 디버깅한다.
- Python 3.12 이하의 `frame.f_locals` 는 읽을 때마다 새로 채워지는 사본이다. 디버거는 이벤트마다 한 번만 읽어 두고 그 사본을 고친다. CPython은 추적 함수가 끝날 때 현재 프레임의 사본만 실제 변수에 되돌려 쓰므로, 3.12 이하에서는 `up` 으로 고른 프레임에 `assign` 해도 반영되지 않는다.

## 6. 예제 세션: `remove_html_markup` 의 버그 찾기

`demo.py` 는 책의 버그 있는 `remove_html_markup()` 이다. 태그 밖의 `"foo"` 를 넣으면 따옴표가 사라져 `foo` 가 나온다. 따옴표 안인지를 나타내는 `quote` 의 값이 언제 바뀌는지 감시해 원인을 찾는다. 아래는 명령을 `sessions/find_bug.txt` 에 넣고 `python debugger.py -x sessions/find_bug.txt demo.py` 로 실행한 실제 출력이다.

```
Running C:\Users\yejun\python-debugger\demo.py
(debugger) break remove_html_markup if s == '"foo"'
Breakpoints: remove_html_markup if s == '"foo"'
(debugger) continue
Breakpoint remove_html_markup
Calling remove_html_markup(s = '"foo"')
(debugger) watch quote
Watching quote = <undefined>
(debugger) continue
Watch quote: <undefined> -> False
                                         # tag = False, quote = False
   7>     out = ""
(debugger) continue
Watch quote: False -> True
                                         # quote = True, out = '', c = '"'
   9>     for c in s:
(debugger) print c, tag
c, tag = ('"', False)
(debugger) print c == '"' or c == "'" and tag
c == '"' or c == "'" and tag = True
(debugger) print (c == '"' or c == "'") and tag
(c == '"' or c == "'") and tag = False
(debugger) where
> #0 demo.py:9 remove_html_markup   for c in s:
  #1 demo.py:25 clean_all           results.append(remove_html_markup(page))
  #2 demo.py:31 <module>            print(clean_all(pages))
(debugger) quit
['foo', 'foo', 'bar']
```

조건부 중단점 덕분에 두 번째 호출에서만 멈췄고, `watch quote` 로 태그 밖(`tag = False`)인데도 `quote` 가 `True` 로 바뀌는 순간을 찾았다. 14번 줄 조건을 그대로 평가하면 `True` 이고, 의도대로 괄호를 넣어 묶으면 `False` 다. `and` 가 `or` 보다 먼저 묶이는 연산자 우선순위 때문에 `c == '"'` 하나만으로 조건이 참이 된 것이다.
