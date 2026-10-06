"""python test_debugger.py — 명령을 미리 넣어 두고 출력과 반환값을 확인한다."""

import io
import os
import subprocess
import sys

from debugger import Debugger
from demo import clean_all, remove_html_markup


def risky(x):
    try:
        return 1 / x
    except ZeroDivisionError:
        return None


def run(commands, func, *args):
    out = io.StringIO()
    with Debugger(file=out, commands=commands + ['quit']):
        result = func(*args)
    return out.getvalue(), result


def check(name, cond, out=''):
    print(('ok  ' if cond else 'FAIL') + ' ' + name)
    if not cond:
        print(out)
        raise SystemExit(1)


# 책 본문: break / list / print / delete
out, _ = run(['break 17', 'list', 'continue', 'print out', 'delete 17'], remove_html_markup, 'ab')
check('break + list markers', '  17# ' in out and '   4> def remove_html_markup' in out, out)
check('stops at line breakpoint', 'Breakpoint demo.py:17' in out and "out = ''" in out, out)

# Exercise 1: assign 은 실제 실행에 반영된다
out, result = run(['break 19', 'continue', 'assign out = "zzz"'], remove_html_markup, 'abc')
check('assign changes the program', result == 'zzz', out)

# Exercise 2: next 는 호출한 함수 안으로 들어가지 않는다
out, _ = run(['next'] * 4 + ['print results'], clean_all, ['<b>x</b>'])
check('next steps over calls', "results = ['x']" in out and 'Calling remove_html_markup' not in out, out)

# 이름 중단점, where, up, down
out, _ = run(['break remove_html_markup', 'continue', 'where', 'up', 'print page', 'down'], clean_all, ['a'])
check('function breakpoint', 'Breakpoint remove_html_markup' in out, out)
check('where', '#1 demo.py:25 clean_all' in out and '#2' in out, out)
check('up selects caller', "page = 'a'" in out and '#0 demo.py:4 remove_html_markup' in out, out)

# until: 루프가 끝난 다음 줄에서 멈춘다
out, _ = run(['break 17', 'continue', 'delete 17', 'until', 'print out'], remove_html_markup, 'abc')
check('until leaves the loop', '  19>     return out' in out and "out = 'abc'" in out, out)

# finish: 현재 함수가 반환할 때 멈춘다
out, _ = run(['finish'], remove_html_markup, 'abc')
check('finish', "remove_html_markup() returns 'abc'" in out, out)

# watch: 값이 바뀔 때마다 멈추고, delete 로 지운다
out, _ = run(['watch quote', 'continue', 'continue'], remove_html_markup, '"x"')
check('watch', 'Watch quote: <undefined> -> False' in out and 'Watch quote: False -> True' in out, out)
out, _ = run(['watch quote', 'delete quote', 'continue'], remove_html_markup, '"x"')
check('delete watch', 'Deleted watch quote' in out and 'Watch quote:' not in out, out)

# 추가 기능: 조건부 중단점, display, jump, catch, 모호한 명령
out, _ = run(["break 17 if c == 'b'", 'continue', 'print c'], remove_html_markup, 'abc')
check('conditional breakpoint', "c = 'b'" in out and "c = 'a'" not in out, out)
out, _ = run(['display out', 'break 17', 'continue', 'continue'], remove_html_markup, 'ab')
check('display', out.count("out = ''") >= 2 and "out = 'a'" in out, out)
out, result = run(['break 17', 'continue', 'jump 19'], remove_html_markup, 'abc')
check('jump skips lines', result == '', out)
out, result = run(['catch on', 'continue'], risky, 0)
check('catch', 'Exception in risky(): ZeroDivisionError: division by zero' in out and result is None, out)
out, _ = run(['d'], remove_html_markup, 'a')
check('ambiguous command', "Ambiguous command 'd'" in out and 'display' in out, out)

# up 한 프레임에 assign: 3.13 부터만 반영된다
out, result = run(['break remove_html_markup', 'continue', 'up', 'assign results = ["hacked"]'],
                  clean_all, ['a', 'b'])
if sys.version_info >= (3, 13):
    check('assign in caller frame (3.13+)', result == ['hacked', 'b'], out)
else:
    check('assign in caller frame refused (<3.13)', 'only the current frame' in out and result == ['a', 'b'], out)

# 명령줄 모드: -x 명령 파일을 다 쓰고 입력이 닫히면 끝까지 실행한다
here = os.path.dirname(os.path.abspath(__file__))
cmdfile = os.path.join(here, 'test_commands.tmp')
with open(cmdfile, 'w', encoding='utf-8') as f:
    f.write('# comment\nbreak remove_html_markup\n\ncontinue\nprint s\n')
try:
    proc = subprocess.run([sys.executable, os.path.join(here, 'debugger.py'), '-x', cmdfile,
                           os.path.join(here, 'demo.py')],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'})
finally:
    os.remove(cmdfile)
check('script mode with -x', "(debugger) print s\ns = '<b>foo</b>'" in proc.stdout and
      "['foo', 'foo', 'bar']" in proc.stdout, proc.stdout + proc.stderr)

print('all passed on Python', sys.version.split()[0])
