#!/usr/bin/env python3
"""The Debugging Book 의 'How Debuggers Work' 장을 따라 만든 명령줄 파이썬 디버거.

코드 일부만 디버깅:

    from debugger import Debugger
    with Debugger():
        some_function()

스크립트 전체를 디버깅:

    python debugger.py [-x 명령파일] script.py [인자...]

명령과 동작은 MANUAL.md 에 정리했다.
"""

import argparse
import inspect
import linecache
import os
import sys
from types import CodeType, FrameType, TracebackType
from typing import Any, Callable, Dict, List, Optional, TextIO, Type, Union

# 이 파일 안의 프레임(디버거 자신)은 추적하지 않는다
_OUR_FILE = (lambda: None).__code__.co_filename
_UNDEF = '<undefined>'  # watch 식을 평가할 수 없을 때의 값

BreakpointKey = Union[str, tuple]  # 함수 이름 또는 (정규화한 파일 경로, 줄 번호)


class Tracer:
    """with 블록 동안 sys.settrace 를 켜고 끈다. 책 'Tracing Executions' 장의 Tracer."""

    def __init__(self, *, file: TextIO = sys.stdout) -> None:
        self.file = file
        self.original_trace_function: Optional[Callable] = None
        self.entry_frame: Optional[FrameType] = None

    def traceit(self, frame: FrameType, event: str, arg: Any) -> None:
        """이벤트마다 불린다. 하위 클래스에서 바꾼다."""
        self.log(event, frame.f_lineno, frame.f_code.co_name, frame.f_locals)

    def _traceit(self, frame: FrameType, event: str, arg: Any) -> Optional[Callable]:
        if frame.f_code.co_filename != _OUR_FILE:
            self.traceit(frame, event, arg)
        return self._traceit  # 이 함수를 돌려줘야 그 프레임의 line 이벤트도 계속 받는다

    def log(self, *objects: Any, sep: str = ' ', end: str = '\n') -> None:
        print(*objects, sep=sep, end=end, file=self.file, flush=True)

    def __enter__(self) -> Any:
        self.original_trace_function = sys.gettrace()
        self.entry_frame = sys._getframe(1)  # with 문이 있는 프레임. where 는 여기까지만 보여 준다
        sys.settrace(self._traceit)
        return self

    def __exit__(self, exc_tp: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 exc_traceback: Optional[TracebackType]) -> None:
        sys.settrace(self.original_trace_function)
        self.entry_frame = None
        # None 을 돌려주므로 블록 안에서 난 예외는 그대로 밖으로 나간다


class Debugger(Tracer):
    """대화형 디버거. NAME_command() 메서드를 하나 추가하면 NAME 명령이 생긴다."""

    def __init__(self, *, file: TextIO = sys.stdout,
                 commands: Optional[List[str]] = None) -> None:
        super().__init__(file=file)
        self.commands = list(commands or [])  # -x 로 받은 명령. 다 쓰면 input() 으로 넘어간다
        self.last_command = ''

        # 실행 제어: step | next | until | finish | continue
        self.mode = 'step'
        self.target: Optional[FrameType] = None  # next/until/finish 의 기준 프레임
        self.until_line = 0

        self.breakpoints: Dict[BreakpointKey, Optional[str]] = {}  # 위치 -> 조건
        self.watches: Dict[str, str] = {}  # 식 -> 마지막 값의 repr
        self.displays: List[str] = []
        self.catch = False

        self.frame: FrameType
        self.event = ''
        self.arg: Any = None
        self.local_vars: Any = {}
        self.stack: List[FrameType] = []
        self.cur = 0  # up/down 으로 고른 프레임의 stack 인덱스
        self.reasons: List[str] = []
        self.last_frame: Optional[FrameType] = None
        self.last_vars: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 추적 함수와 정지 판단

    def traceit(self, frame: FrameType, event: str, arg: Any) -> None:
        self.frame, self.event, self.arg = frame, event, arg
        # 3.12 이하에서 f_locals 는 읽을 때마다 실제 변수로 다시 채워지는 사본이다.
        # 한 번만 읽어 두어야 assign 으로 고친 값이 덮이지 않는다.
        self.local_vars = frame.f_locals
        if self.stop_here():
            self.interaction_loop()

    def stop_here(self) -> bool:
        self.reasons = self.watch_changes() + self.breakpoint_hits()
        if self.reasons:
            return True
        if self.event == 'exception':
            return self.catch
        return self.reached_target()

    def reached_target(self) -> bool:
        """직전 실행 제어 명령이 정한 곳에 왔는가"""
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

    def on_stack(self, target: Optional[FrameType]) -> bool:
        f = self.frame.f_back
        while f is not None:
            if f is target:
                return True
            f = f.f_back
        return False

    def breakpoint_hits(self) -> List[str]:
        code = self.frame.f_code
        if self.event == 'line':
            key = self.line_breakpoint(code.co_filename, self.frame.f_lineno)
        elif self.event == 'call':
            key = self.function_breakpoint(code)
        else:
            return []
        if key is None:
            return []

        message = f"Breakpoint {self.format_breakpoint(key)}"
        cond = self.breakpoints[key]
        if cond:
            try:
                if not self.evaluate(cond, self.frame):
                    return []
            except Exception as err:
                return [f"{message}: {err.__class__.__name__}: {err}"]
        return [message]

    def line_breakpoint(self, filename: str, lineno: int) -> Optional[BreakpointKey]:
        filename = os.path.normcase(filename)
        for key in self.breakpoints:
            if (isinstance(key, tuple) and key[1] == lineno and
                    (filename == key[0] or filename.endswith(os.sep + key[0]))):
                return key
        return None

    def function_breakpoint(self, code: CodeType) -> Optional[BreakpointKey]:
        qualname = getattr(code, 'co_qualname', code.co_name)  # co_qualname 은 3.11 부터
        for name in (code.co_name, qualname):
            if name in self.breakpoints:
                return name
        return None

    def watch_changes(self) -> List[str]:
        changes = []
        for expr, old in self.watches.items():
            new = self.watch_value(expr)
            # 평가할 수 없는 곳(다른 함수 안 등)은 변화로 치지 않는다
            if new != _UNDEF and new != old:
                self.watches[expr] = new
                changes.append(f"Watch {expr}: {old} -> {new}")
        return changes

    def watch_value(self, expr: str) -> str:
        # repr 로 비교하면 리스트에 append 하는 것처럼 제자리에서 바뀌는 것도 잡힌다
        try:
            return repr(self.evaluate(expr, self.frame))
        except Exception:
            return _UNDEF

    # ------------------------------------------------------------------
    # 사용자와의 상호작용

    def interaction_loop(self) -> None:
        self.stack = self.collect_stack()
        self.cur = 0
        self.print_debugger_status()

        self.interact = True
        while self.interact:
            self.execute(self.next_input())

        self.last_frame = self.frame
        self.last_vars = self.snapshot(self.local_vars)
        self.stack = []  # 프레임을 붙잡고 있지 않도록 비운다

    def next_input(self) -> str:
        if self.commands:
            command = self.commands.pop(0)
            self.log(f"(debugger) {command}")
        else:
            try:
                command = input("(debugger) ")
            except EOFError:  # 입력이 끝났으면 프로그램을 마저 실행한다
                self.log("quit")
                command = 'quit'
        if command.strip():
            self.last_command = command
        return command if command.strip() else self.last_command

    def collect_stack(self) -> List[FrameType]:
        """현재 프레임부터 with 문이 있는 프레임까지. 디버거 자신의 프레임은 뺀다."""
        stack = []
        f: Optional[FrameType] = self.frame
        while f is not None:
            if f.f_code.co_filename != _OUR_FILE:
                stack.append(f)
            if f is self.entry_frame:
                break
            f = f.f_back
        return stack

    @property
    def selected(self) -> FrameType:
        return self.stack[self.cur] if self.stack else self.frame

    def vars(self, frame: FrameType) -> Any:
        return self.local_vars if frame is self.frame else frame.f_locals

    def evaluate(self, expr: str, frame: Optional[FrameType] = None) -> Any:
        frame = frame or self.selected
        # 지역 변수를 globals 쪽에 합쳐서 넘긴다. 3.11 은 컴프리헨션이 별도 함수라
        # eval(expr, globals, locals) 로는 [x for x in s if x != c] 의 c 를 못 찾는다.
        return eval(expr, {**frame.f_globals, **self.vars(frame)})

    @staticmethod
    def snapshot(variables: Any) -> Dict[str, str]:
        try:
            return {name: repr(value) for name, value in variables.items()}
        except Exception:
            return {}

    @staticmethod
    def source_line(frame: FrameType) -> str:
        return linecache.getline(frame.f_code.co_filename, frame.f_lineno).rstrip()

    def location(self, frame: FrameType) -> str:
        return f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno} {frame.f_code.co_name}"

    def print_debugger_status(self) -> None:
        for reason in self.reasons:
            self.log(reason)

        frame, event, name = self.frame, self.event, self.frame.f_code.co_name
        if event == 'call' and name == '<module>':
            self.log(f"Running {frame.f_code.co_filename}")
        elif event == 'call':
            # call 이벤트 시점의 지역 변수는 곧 인자다
            args = ", ".join(f"{var} = {value}"
                             for var, value in self.snapshot(self.local_vars).items())
            self.log(f"Calling {name}({args})")
        elif event == 'line':
            if frame is not self.last_frame:
                self.log(f"[{self.location(frame)}]")
            else:
                now = self.snapshot(self.local_vars)
                changed = ", ".join(f"{var} = {value}" for var, value in now.items()
                                    if self.last_vars.get(var) != value)
                if changed:
                    self.log(' ' * 40, '#', changed)
            self.log(f"{frame.f_lineno:4}> {self.source_line(frame)}")
        elif event == 'return':
            self.log(f"{name}() returns {self.arg!r}")
        elif event == 'exception':
            exc_type, exc_value, _ = self.arg
            self.log(f"Exception in {name}(): {exc_type.__name__}: {exc_value}")

        for expr in self.displays:
            self.print_expression(expr)

    def print_expression(self, expr: str) -> None:
        try:
            self.log(f"{expr} = {self.evaluate(expr)!r}")
        except Exception as err:
            self.log(f"{expr}: {err.__class__.__name__}: {err}")

    # ------------------------------------------------------------------
    # 명령 분배 (책의 execute / command_method / help 그대로)

    def commands_list(self) -> List[str]:
        return sorted(method[:-len('_command')] for method in dir(self.__class__)
                      if method.endswith('_command'))

    def command_method(self, command: str) -> Optional[Callable[[str], None]]:
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

    def execute(self, command: str) -> None:
        cmd, _, arg = command.strip().partition(' ')
        method = self.command_method(cmd)
        if method:
            method(arg.strip())

    def help_command(self, command: str = "") -> None:
        """명령 목록을 보여 준다. 'help COMMAND' 는 그 명령의 설명만 보여 준다."""
        cmds = self.commands_list()
        if command:
            possible = [cmd for cmd in cmds if cmd.startswith(command)]
            if not possible:
                self.log(f"Unknown command {command!r}. Possible commands are:")
                possible = cmds
            elif len(possible) > 1 and command not in cmds:
                self.log(f"Ambiguous command {command!r}. Possible expansions are:")
            elif command in cmds:
                possible = [command]
            cmds = possible
        for cmd in cmds:
            doc = getattr(self, cmd + '_command').__doc__
            self.log(f"{cmd:10} -- {doc}")

    # ------------------------------------------------------------------
    # 실행 제어

    def resume(self, mode: str, target: Optional[FrameType] = None) -> None:
        self.mode = mode
        self.target = target
        self.interact = False

    def step_command(self, arg: str = "") -> None:
        """다음 이벤트(호출, 줄, 반환)까지 진행한다. 호출이면 함수 안으로 들어간다."""
        self.resume('step')

    def next_command(self, arg: str = "") -> None:
        """현재 함수의 다음 줄까지 진행한다. 호출하는 함수는 통째로 실행한다."""
        self.resume('next', self.selected)

    def until_command(self, arg: str = "") -> None:
        """'until [LINE]': 현재 함수에서 LINE(생략 시 현재 줄)보다 큰 줄에 닿을 때까지 진행한다."""
        try:
            self.until_line = int(arg) if arg else self.selected.f_lineno
        except ValueError:
            self.log(f"Not a line number: {arg!r}")
            return
        self.resume('until', self.selected)

    def finish_command(self, arg: str = "") -> None:
        """현재 함수가 반환할 때까지 진행한다."""
        self.resume('finish', self.selected)

    def continue_command(self, arg: str = "") -> None:
        """중단점, 감시, catch 에 걸릴 때까지 진행한다."""
        self.resume('continue')

    def jump_command(self, arg: str = "") -> None:
        """'jump LINE': 다음에 실행할 줄을 LINE 으로 바꾼다. 현재 프레임의 line 이벤트에서만 된다."""
        if self.cur != 0 or self.event != 'line':
            self.log("jump: only possible at a line event of the current frame")
            return
        try:
            # CPython 은 추적 함수 안의 line 이벤트에서만 f_lineno 대입을 허용한다
            self.frame.f_lineno = int(arg)
        except ValueError as err:
            self.log(f"jump: {err}")
            return
        self.log(f"{self.frame.f_lineno:4}> {self.source_line(self.frame)}")

    def quit_command(self, arg: str = "") -> None:
        """중단점과 감시를 모두 지우고 추적을 끈 채 끝까지 실행한다."""
        self.breakpoints.clear()
        self.watches.clear()
        self.displays.clear()
        self.catch = False
        sys.settrace(None)
        self.resume('continue')

    # ------------------------------------------------------------------
    # 중단점

    def parse_location(self, spec: str) -> Optional[BreakpointKey]:
        file, sep, line = spec.rpartition(':')
        if line.isdigit():
            file = file if sep else self.selected.f_code.co_filename
            return (os.path.normcase(os.path.normpath(file)), int(line))
        if spec and all(part.isidentifier() for part in spec.split('.')):
            return spec
        self.log(f"Not a line, FILE:LINE or function name: {spec!r}")
        return None

    @staticmethod
    def format_breakpoint(key: BreakpointKey) -> str:
        if isinstance(key, tuple):
            return f"{os.path.basename(key[0])}:{key[1]}"
        return key

    def list_breakpoints(self) -> None:
        items = [self.format_breakpoint(key) + (f" if {cond}" if cond else "")
                 for key, cond in self.breakpoints.items()]
        self.log("Breakpoints:", ", ".join(items) or "(none)")

    def break_command(self, arg: str = "") -> None:
        """'break LINE|FILE:LINE|FUNCTION [if COND]': 중단점을 건다. 인자가 없으면 목록을 보여 준다."""
        if arg:
            spec, _, cond = arg.partition(' if ')
            key = self.parse_location(spec.strip())
            if key is None:
                return
            self.breakpoints[key] = cond.strip() or None
        self.list_breakpoints()

    def delete_command(self, arg: str = "") -> None:
        """'delete [SPEC|EXPR]': 중단점이나 감시를 지운다. 인자가 없으면 모두 지운다."""
        if not arg:
            self.breakpoints.clear()
            self.watches.clear()
        elif arg in self.watches:
            del self.watches[arg]
            self.log(f"Deleted watch {arg}")
            return
        else:
            key = self.parse_location(arg)
            if key is None:
                return
            if key not in self.breakpoints:
                self.log(f"No such breakpoint: {arg}")
                return
            del self.breakpoints[key]
        self.list_breakpoints()

    # ------------------------------------------------------------------
    # 감시와 자동 표시

    def watch_command(self, arg: str = "") -> None:
        """'watch EXPR': EXPR 의 값이 바뀌면 멈춘다. 인자가 없으면 감시 목록을 보여 준다."""
        if arg:
            self.watches[arg] = self.watch_value(arg)
        for expr, value in self.watches.items():
            self.log(f"Watching {expr} = {value}")

    def display_command(self, arg: str = "") -> None:
        """'display EXPR': 멈출 때마다 EXPR 을 보여 준다. 인자가 없으면 지금 모두 보여 준다."""
        if arg and arg not in self.displays:
            self.displays.append(arg)
        for expr in ([arg] if arg else self.displays):
            self.print_expression(expr)

    def undisplay_command(self, arg: str = "") -> None:
        """'undisplay [EXPR]': 자동 표시를 지운다. 인자가 없으면 모두 지운다."""
        if not arg:
            self.displays.clear()
        elif arg in self.displays:
            self.displays.remove(arg)
        else:
            self.log(f"Not displayed: {arg}")

    # ------------------------------------------------------------------
    # 상태 보기와 바꾸기

    def print_command(self, arg: str = "") -> None:
        """'print [EXPR]': 식을 평가해 보여 준다. 인자가 없으면 지역 변수를 모두 보여 준다."""
        if arg:
            self.print_expression(arg)
            return
        for var, value in self.snapshot(self.vars(self.selected)).items():
            self.log(f"{var} = {value}")

    def list_command(self, arg: str = "") -> None:
        """'list [FUNCTION]': 현재 함수(또는 FUNCTION)의 소스를 보여 준다. > 현재 줄, # 중단점."""
        frame = self.selected
        try:
            if arg:
                lines, start = inspect.getsourcelines(self.evaluate(arg))
                current, filename = -1, inspect.getsourcefile(self.evaluate(arg)) or ''
            elif frame.f_code.co_name == '<module>':
                lines, start = linecache.getlines(frame.f_code.co_filename), 1
                current, filename = frame.f_lineno, frame.f_code.co_filename
            else:
                lines, start = inspect.getsourcelines(frame.f_code)
                current, filename = frame.f_lineno, frame.f_code.co_filename
        except Exception as err:
            self.log(f"{err.__class__.__name__}: {err}")
            return

        for lineno, line in enumerate(lines, start):
            if lineno == current:
                mark = '>'
            elif self.line_breakpoint(filename, lineno) is not None:
                mark = '#'
            else:
                mark = ' '
            self.log(f"{lineno:4}{mark} {line}", end='')

    def assign_command(self, arg: str = "") -> None:
        """'assign VAR=EXPR': 지역 변수 VAR 에 EXPR 의 값을 넣는다."""
        var, sep, expr = arg.partition('=')
        var = var.strip()
        if not sep or not var.isidentifier():
            self.help_command('assign')
            return
        frame = self.selected
        if frame is not self.frame and sys.version_info < (3, 13):
            # 3.12 이하는 추적 중인 프레임의 f_locals 사본만 실제 변수로 되돌려 쓴다
            self.log("assign: only the current frame can be changed before Python 3.13")
            return
        try:
            self.vars(frame)[var] = self.evaluate(expr.strip(), frame)
        except Exception as err:
            self.log(f"{err.__class__.__name__}: {err}")

    def where_command(self, arg: str = "") -> None:
        """호출 스택을 안쪽부터 보여 준다. > 는 선택한 프레임이다."""
        for i, frame in enumerate(self.stack):
            mark = '>' if i == self.cur else ' '
            self.log(f"{mark} #{i} {self.location(frame):30} {self.source_line(frame).strip()}")

    def up_command(self, arg: str = "") -> None:
        """한 단계 바깥쪽(호출한 쪽) 프레임을 고른다."""
        self.move_frame(+1)

    def down_command(self, arg: str = "") -> None:
        """한 단계 안쪽(호출된 쪽) 프레임을 고른다."""
        self.move_frame(-1)

    def move_frame(self, delta: int) -> None:
        cur = self.cur + delta
        if not 0 <= cur < len(self.stack):
            self.log("Already at the", "outermost" if delta > 0 else "innermost", "frame")
            return
        self.cur = cur
        frame = self.selected
        self.log(f"#{cur} {self.location(frame)}")
        self.log(f"{frame.f_lineno:4}> {self.source_line(frame)}")

    def catch_command(self, arg: str = "") -> None:
        """'catch [on|off]': 예외가 발생하는 순간 멈출지 정한다. 인자가 없으면 켜고 끄기를 바꾼다."""
        if arg in ('on', 'off'):
            self.catch = arg == 'on'
        elif arg:
            self.log(f"catch: expected 'on' or 'off', got {arg!r}")
            return
        else:
            self.catch = not self.catch
        self.log("Catch exceptions:", "on" if self.catch else "off")

    def info_command(self, arg: str = "") -> None:
        """중단점, 감시, 자동 표시, catch 상태를 한꺼번에 보여 준다."""
        self.list_breakpoints()
        self.log("Watches:", ", ".join(f"{e} = {v}" for e, v in self.watches.items()) or "(none)")
        self.log("Displays:", ", ".join(self.displays) or "(none)")
        self.log("Catch exceptions:", "on" if self.catch else "off")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Python 스크립트를 한 줄씩 디버깅한다.")
    parser.add_argument('-x', metavar='CMDFILE',
                        help="명령을 한 줄씩 읽어 실행할 파일 (빈 줄과 # 줄은 건너뜀)")
    parser.add_argument('script', help="디버깅할 파이썬 스크립트")
    parser.add_argument('args', nargs=argparse.REMAINDER, help="스크립트에 넘길 인자")
    options = parser.parse_args(argv)

    commands = []
    if options.x:
        with open(options.x, encoding='utf-8') as cmdfile:
            commands = [line.strip() for line in cmdfile
                        if line.strip() and not line.lstrip().startswith('#')]

    path = os.path.abspath(options.script)
    with open(path, 'rb') as source:
        code = compile(source.read(), path, 'exec')

    # 스크립트가 직접 실행된 것처럼 보이게 한다
    sys.argv = [options.script] + options.args
    sys.path[0] = os.path.dirname(path)
    namespace = {'__name__': '__main__', '__file__': path, '__builtins__': __builtins__}

    with Debugger(commands=commands):
        exec(code, namespace)


if __name__ == '__main__':
    main()
