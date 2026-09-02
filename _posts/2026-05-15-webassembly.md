---
layout: post
title: "WebAssembly를 직접 뜯어보며 배운 것들 — WAT 작성부터 바이너리 파싱까지"
date: 2026-05-15
category: 개발
author: WTCY
tags: [WebAssembly, Wasm, WAT, JavaScript, 바이너리분석, LEB128]
---

---

## 들어가며

"Wasm은 빠르다"는 말은 많이 들었지만, `.wat` 파일을 직접 써보고 바이너리로 컴파일해서 JS와 연동하기 전까지는 피부로 와닿지 않았다.

더 솔직히 말하면 처음에는 기대가 컸다. 막상 `fibonacci(35)` 벤치마크를 돌려보니 JS랑 속도가 비슷하거나 JS가 더 빠른 경우도 있었다. 그 이유를 파고들면서 Wasm이 실제로 어디서 빠른지, 왜 그런지가 보이기 시작했다.

---

## WebAssembly가 뭔가

WebAssembly(Wasm)는 브라우저에서 실행되는 **이진 명령어 형식(binary instruction format)** 이다. C, C++, Rust, AssemblyScript 등을 `.wasm`으로 컴파일하면 브라우저의 Wasm VM이 이를 실행한다.

핵심 특성 세 가지다.

- **타입 안전성** — 모든 값에 `i32 / i64 / f32 / f64` 타입이 지정됨
- **샌드박스** — Linear memory 외부에 직접 접근 불가. DOM은 JS를 통해서만 조작
- **이식성** — 동일 `.wasm`이 Chrome, Firefox, Safari, Node.js에서 동작

---

## WAT: Wasm의 텍스트 표현

`.wasm`은 바이너리지만, 공식 텍스트 포맷인 **WAT(WebAssembly Text Format)** 로 표현할 수 있다. S-expression 문법이다.

```wat
(module
  (func (export "add") (param $a i32) (param $b i32) (result i32)
    (i32.add (local.get $a) (local.get $b))
  )
)
```

이 5줄이 컴파일되면 29 bytes `.wasm`이 된다. header 8바이트 + 섹션들로 구성된다.

이번 프로젝트에서 만든 모듈(`src/math.wat`)에는 총 8개 함수가 있다.

### 함수 목록

| 함수 | 시그니처 | 시연하는 패턴 |
|---|---|---|
| `add` | (i32, i32) → i32 | 기본 스택 연산 |
| `fibonacci` | (i32) → i32 | 재귀 (`if/then/return/call`) |
| `factorial` | (i32) → i32 | 반복 (`block/loop/br_if`) |
| `sumArray` | (i32, i32) → i32 | 메모리 읽기 (`i32.load`) |
| `dotProduct` | (i32, i32, i32) → f64 | f64 메모리 (`f64.load`) |
| `strlen` | (i32) → i32 | 1바이트 접근 (`i32.load8_u`) |
| `clamp` | (i32, i32, i32) → i32 | 분기 없는 선택 (`select`) |
| `sumArrayBounded` | (i32, i32, i32) → i32 | 명시적 trap (`unreachable`) |

---

### 재귀 패턴 — fibonacci

```wat
(func $fib (export "fibonacci") (param $n i32) (result i32)
  (if (i32.lt_s (local.get $n) (i32.const 2))
    (then (return (local.get $n)))
  )
  (i32.add
    (call $fib (i32.sub (local.get $n) (i32.const 1)))
    (call $fib (i32.sub (local.get $n) (i32.const 2)))
  )
)
```

---

### 반복 패턴 — factorial

WAT에는 `for`나 `while`이 없다. `block + loop + br_if`로 구현한다.

```wat
(func (export "factorial") (param $n i32) (result i32)
  (local $result i32) (local $i i32)
  (local.set $result (i32.const 1))
  (local.set $i      (i32.const 1))
  (block $break
    (loop $loop
      (br_if $break (i32.gt_s (local.get $i) (local.get $n)))
      (local.set $result (i32.mul (local.get $result) (local.get $i)))
      (local.set $i      (i32.add (local.get $i) (i32.const 1)))
      (br $loop)
    )
  )
  (local.get $result)
)
```

- `block $break` — 탈출 대상 레이블
- `loop $loop` — 반복 대상 레이블
- `br_if $break (조건)` — 조건이 참이면 `$break`로 점프 (루프 탈출)
- `br $loop` — 무조건 `$loop`로 점프 (반복)

---

### `select` 명령어 — clamp

JS의 삼항 연산자와 비슷하지만 **분기가 없다**. 스택에서 세 값을 pop해 조건에 따라 하나를 push한다.

```wat
(func (export "clamp") (param $value i32) (param $lo i32) (param $hi i32) (result i32)
  (local $r i32)
  (local.set $r
    (select (local.get $value) (local.get $lo)
            (i32.ge_s (local.get $value) (local.get $lo))))
  (select (local.get $r) (local.get $hi)
          (i32.le_s (local.get $r) (local.get $hi)))
)
```

---

### `unreachable` — sumArrayBounded

Wasm이 의도적으로 trap을 발생시키는 명령어다. JS에서 `WebAssembly.RuntimeError`로 잡힌다.

```wat
(func (export "sumArrayBounded")
  (param $offset i32) (param $length i32) (param $memLimit i32) (result i32)
  (local $required i32)
  (local.set $required
    (i32.add (local.get $offset) (i32.mul (local.get $length) (i32.const 4))))
  (if (i32.gt_u (local.get $required) (local.get $memLimit))
    (then (unreachable))   ;; 경계 초과 시 즉시 trap
  )
)
```

```javascript
try {
  sumArrayBounded(0, 100, 64);  // 400 bytes > 64 bytes limit
} catch (e) {
  console.log(e instanceof WebAssembly.RuntimeError);  // true
  console.log(e.message);  // "unreachable"
}
```

---

## JS API — Wasm과 연동하는 세 가지 핵심

### 1. 로드: instantiateStreaming

```javascript
const importObject = {
  env: {
    log_i32: (v) => console.log('[wasm]', v),
    log_f64: (v) => console.log('[wasm]', v),
  },
};

const { instance } = await WebAssembly.instantiateStreaming(
  fetch('./src/math.wasm'),
  importObject
);
```

`instantiateStreaming`이 권장되는 이유는 네트워크에서 받으면서 동시에 컴파일하기 때문이다. `fetch → arrayBuffer → instantiate` 순서보다 빠르다.

### 2. importObject — JS가 Wasm에 제공하는 함수

WAT의 `(import "env" "log_i32" ...)`는 JS에서 반드시 대응하는 함수를 넘겨야 한다는 선언이다. 모듈명·필드명이 하나라도 다르면 `WebAssembly.LinkError`가 발생한다. 이 방향이 **JS → Wasm** 방향이다. Wasm이 JS를 "역으로 호출"하는 것이다.

### 3. exports — Wasm이 JS에 노출하는 것들

```javascript
const { add, fibonacci, factorial, sumArray, dotProduct,
        strlen, clamp, sumArrayBounded, memory } = instance.exports;
```

`memory`도 export된다. 이게 핵심이다.

---

## Linear Memory — 가장 중요한 개념

Wasm의 메모리 모델을 이해하면 절반은 이해한 것이다.

**Linear memory**는 Wasm 모듈이 가진 연속 바이트 배열이다. `1 page = 65,536 bytes (64 KB)`.

JS와 Wasm이 **동일한** `memory.buffer`(ArrayBuffer)를 공유한다. JS에서 쓰면 Wasm이 즉시 읽을 수 있고, Wasm이 계산한 결과를 JS가 즉시 읽을 수 있다. 복사가 없다.

```javascript
const { memory, sumArray } = instance.exports;
new Int32Array(memory.buffer, 0, 4).set([1, 2, 3, 4]);
console.log(sumArray(0, 4));  // → 10
```

### sumArray([1, 2, 3, 4]) 호출 추적

```
Step 1. JS: new Int32Array(memory.buffer, 0, 4).set([1, 2, 3, 4])

  memory[0x0000–0x000F]:
  ┌────────┬────────────────────────────────────┐
  │ Offset │  +0    +1    +2    +3   +4 ...      │
  ├────────┼────────────────────────────────────┤
  │ 0x0000 │  01    00    00    00   02    00    │  ← 1, 2
  │ 0x0008 │  03    00    00    00   04    00    │  ← 3, 4
  └────────┴────────────────────────────────────┘
  i32는 4바이트 little-endian: 값 1 = [01 00 00 00]

Step 2. sumArray(0, 4) 호출: $offset=0, $length=4, $end=16

Step 3. Wasm 루프 실행
  iter 1: i32.load(0x0000) = 1,  $sum=1
  iter 2: i32.load(0x0004) = 2,  $sum=3
  iter 3: i32.load(0x0008) = 3,  $sum=6
  iter 4: i32.load(0x000C) = 4,  $sum=10

Step 4. $i(16) >= $end(16) → 루프 탈출
Step 5. return 10
```

### strlen("Hello") 호출 추적

`i32.load8_u`는 `i32.load`(4바이트)와 달리 **1바이트**만 읽는다.

```
Step 1. JS: new TextEncoder().encode("Hello\0") → [48 65 6C 6C 6F 00]
  memory[0x0000–0x0005]:
  48  65  6C  6C  6F  00
  'H' 'e' 'l' 'l' 'o' '\0'

Step 2. strlen(0) 호출
  iter 1~5: 0x48~0x6F ≠ 0 → continue
  iter 6:   0x00 == 0 → break

Step 3. return 5
```

---

## WASM 바이너리 구조 — 바이트 단위로 뜯기

빌드 스크립트에 LEB128 파서를 직접 구현해서 섹션 구조를 분석했다.

### 헤더

```
Offset  Hex                 필드
0x0000  00 61 73 6D         magic: "\0asm"
0x0004  01 00 00 00         version: 1 (MVP)
```

### 섹션 맵 (778 bytes 기준)

```
Offset   ID  이름        크기   설명
0x0008    1  Type       34 B    함수 시그니처 정의 (7개 타입)
0x002C    2  Import     29 B    env.log_i32, env.log_f64
0x004B    3  Function    9 B    내부 함수 → Type 인덱스 매핑
0x0056    5  Memory      3 B    min=1 page
0x005B    7  Export     99 B    함수 8개 + memory
0x00C0   10  Code      361 B    실제 바이트코드 (전체 46%)
0x022C    0  Custom    219 B    name section (DevTools 함수명용)
```

Section 4(Table), 6(Global)이 없다 — 함수 포인터 테이블과 전역 변수를 쓰지 않았기 때문이다.

### LEB128 — 섹션 크기를 인코딩하는 방법

WASM 바이너리 전체에서 정수는 **LEB128** 가변 길이 인코딩을 사용한다.

- 각 바이트의 하위 7비트가 데이터
- 최상위 비트(MSB) = 1이면 다음 바이트 있음, 0이면 마지막

```
0x22  = 0010 0010  → MSB=0, 값 = 34  (Type 섹션 34 bytes)
0x81 0x01          → (0x01 << 7) | 0x01 = 129
```

섹션 크기, 타입 인덱스, `local.get` 인수, `i32.const` 상수, `call` 대상 인덱스 — 전부 LEB128이다.

### Type 섹션 decode

| 인덱스 | Hex | 시그니처 | 사용 함수 |
|---|---|---|---|
| [0] | `60 01 7f 00` | (i32) → void | env.log_i32 |
| [1] | `60 01 7c 00` | (f64) → void | env.log_f64 |
| [2] | `60 02 7f 7f 01 7f` | (i32, i32) → i32 | add, sumArray |
| [3] | `60 01 7f 01 7f` | (i32) → i32 | fibonacci, factorial, strlen |
| [4] | `60 03 7f 7f 7f 01 7c` | (i32, i32, i32) → f64 | dotProduct |
| [5] | `60 03 7f 7f 7f 01 7f` | (i32, i32, i32) → i32 | clamp, sumArrayBounded |

valtype 인코딩: `0x7F` = i32, `0x7C` = f64, `0x60` = function type marker.

### `add` 함수 바이트코드 decode

```
Offset   Hex     니모닉        스택 상태
0x00C5   00      (local 0개)
+1       20 00   local.get 0   [13]         $a push
+3       20 01   local.get 1   [13, 29]     $b push
+5       6A      i32.add       [42]         pop 2, push 합계
+6       0B      end                        반환값 42
```

Wasm은 레지스터 머신이 아닌 **스택 머신**이다. `end` 시점의 스택 top이 반환값이 된다.

---

## 원본 WAT vs 역변환 WAT

`wasm2wat`으로 바이너리를 다시 텍스트로 변환하면 원본과 다른 형태가 나온다.

| 원본 WAT (S-expression) | 역변환 WAT (flat) | 이유 |
|---|---|---|
| `(local.set $result (i32.const 1))` | `i32.const 1` → `local.set 1` | 중첩 S-exp → 스택 push 순서 평탄화 |
| `$break`, `$loop` (이름 있는 레이블) | `1 (;@1;)`, `0 (;@2;)` | 레이블 이름은 name section에 저장됨 |

WAT의 S-expression 표기는 인간을 위한 편의 문법이다. 실제 실행 모델은 항상 스택 머신이며, 역변환 결과가 그 스택 순서를 그대로 드러낸다.

---

## DevTools로 Wasm 분석하기

Chrome DevTools가 Wasm을 꽤 잘 지원한다. Sources 패널에서 `wasm://` 가상 경로로 `.wasm` 파일이 보이고, WAT로 디스어셈블된 코드가 표시된다. 브레이크포인트를 찍으면 Wasm 함수 안에서 멈춰서 로컬 변수를 확인할 수 있다. name section이 있어야 함수명이 제대로 보인다.

```bash
wasm-objdump -h src/math.wasm     # 섹션 헤더
wasm-objdump -d src/math.wasm     # 전체 디스어셈블
wasm-objdump -j Export src/math.wasm  # export만
wasm2wat src/math.wasm            # 전체 역변환
```

---

## 벤치마크: Wasm이 항상 빠를까?

`fibonacci(35)`를 5회씩 측정했다 (Chrome V8, M1 MacBook 기준).

| 구현 | 평균 |
|---|---|
| JavaScript | 40–80 ms |
| WebAssembly | 30–100 ms |

**비슷하거나 JS가 빠른 경우도 있었다.** V8의 TurboFan JIT가 재귀 fibonacci처럼 예측 가능한 수치 패턴을 이미 매우 잘 최적화하기 때문이다. Wasm은 AOT 컴파일이지만, JIT는 런타임 프로파일링 기반으로 더 공격적인 인라이닝을 할 수 있다.

Wasm의 실제 이점이 드러나는 케이스는 따로 있다.

| 케이스 | 이유 |
|---|---|
| 대용량 float 배열 연산 (오디오/이미지 처리) | SIMD, 예측 가능한 메모리 패턴 |
| 기존 C/C++/Rust 코드 포팅 | 재작성 없이 브라우저 이식 |
| 암호화·압축 등 CPU 집약적 연산 | 일관된 실행 시간 |
| 게임 엔진 물리 계산 | tight loop + GC 없음 |

단순 재귀 fibonacci로는 Wasm의 이점을 보여주기 어렵다.

### JS↔Wasm 경계 비용

함수 호출마다 Wasm ↔ JS 경계를 넘는 비용이 있다. 1,000,000회 빈 호출로 측정하면 회당 수십 ns 수준이다. DOM 조작처럼 호출이 매우 빈번하면 누적 비용이 문제가 된다.

---

## Wasm의 한계 — 솔직하게

- **DOM 접근 불가** — `document.querySelector` 같은 것은 없다. JS를 거쳐야 한다
- **JS interop 비용** — 잦은 왕복 호출은 오히려 느리다
- **문자열이 없다** — 메모리에 UTF-8로 쓰고 offset+length를 파라미터로 넘긴다
- **GC 없음(1.0)** — C/Rust 스타일 메모리 관리 그대로
- **디버깅** — DWARF 소스맵이 개선 중이지만 JS보다 불편하다
- **Cold start** — 초기 인스턴스화 비용 있음 (HTTP 캐시로 완화 가능)

---

## 언제 쓰고 언제 안 쓰나

**써야 할 때:**
- Figma, AutoCAD 류의 복잡한 렌더링·계산 엔진
- FFmpeg, OpenCV 등 기존 네이티브 라이브러리의 브라우저 포팅
- 게임 엔진 (Unity WebGL)
- 암호화·해시·압축 연산

**안 써도 될 때:**
- 일반 웹 UI 로직
- DOM이 많이 개입하는 코드
- JIT가 이미 잘 처리하는 단순 반복 수치 연산

---

## 마치며

WAT를 직접 작성하고, 바이너리를 LEB128까지 파싱하고, `sumArray` 루프를 iteration별로 추적해보고 나서야 "WebAssembly가 어떻게 돌아가는지"가 머릿속에 자리잡혔다.

Emscripten이나 wasm-pack 같은 도구를 쓰면 훨씬 빠르게 결과물을 낼 수 있다. 하지만 *왜* 동작하는지를 알려면 이 낮은 층위를 한 번쯤 직접 뜯어봐야 한다고 생각한다. 특히 Linear memory 개념과 스택 머신 실행 모델은 추상화 뒤에 있으면 잘 보이지 않는다.

---

## 참고 자료

- [MDN WebAssembly Guides](https://developer.mozilla.org/en-US/docs/WebAssembly/Guides)
- [WebAssembly Binary Toolkit (WABT)](https://github.com/WebAssembly/wabt)
- [Chrome DevTools: Debug Wasm](https://developer.chrome.com/docs/devtools/wasm)
- [WebAssembly Specification](https://webassembly.github.io/spec/core/)
- [Lin Clark — A cartoon intro to WebAssembly](https://hacks.mozilla.org/2017/02/a-cartoon-intro-to-webassembly/)
