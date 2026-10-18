---
layout: post
title: "정수 오버플로·절단 RCA — UBSan과 ASan이 가리킨 서로 다른 줄"
date: 2026-12-17 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, IntegerOverflow, UBSan, ASan, Scudo, IntSan, RootCause]
excerpt: "64비트 길이를 16비트에 담는 함수 하나를 Android 13 x86_64 에뮬레이터에서 돌리자 UBSan은 절단이 일어난 8행을, ASan은 11행 memcpy를 짚었다. 새니타이저 없는 빌드는 이웃 청크를 free할 때에야 Scudo 헤더 검사에 걸렸고, 캐스트 패치는 경고만 지웠으며 memcpy 앞 검사는 크래시를 호출자 쪽으로 옮겼다."
---

ASan 보고서 맨 위에 `memcpy`가 찍히면 손이 먼저 그 줄로 간다. 복사 길이를 검사하는 `if` 하나를 넣고 크래시가 사라지면 닫는다. 정수 오버플로 계열 버그에서는 이 순서가 거의 언제나 틀린다. memcpy는 넘겨받은 길이만큼 복사했을 뿐이고, 버퍼 크기와 복사 길이를 어긋나게 만든 건 몇 줄 위에서 값을 잃어버린 산술이다. 3부 1장의 말로 하면 memcpy는 폴트 사이트, 산술은 근본 원인이다.

앞 글의 Parcel 불일치는 읽는 위치가 어긋나는 결함이었다. 이번에는 크기가 어긋난다. 확인할 불변식도 3부 2장 방식으로 하나만 세워 둔다. 할당에 쓴 크기는 접근에 쓰는 크기보다 작으면 안 된다. 자작 함수 하나를 여러 빌드로 돌려 보니, 이 불변식이 깨지는 줄과 도구가 손가락으로 가리키는 줄은 빌드마다 달랐다.

## 길이를 16비트에 담는 copy_chunk

대상은 일부러 짧게 만든 함수다. 길이를 `size_t`로 받아 `uint16_t`에 담고, 그 값으로 할당한 다음 원래 길이로 복사한다. `len`은 파싱한 헤더의 길이 필드처럼 신뢰 경계 밖에서 들어온다고 가정했다.

```c
// vuln.c: 자작 결함, 개념 이해용 최소 예시
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// src, len 은 신뢰 경계 밖(파싱된 헤더 길이)에서 온다고 가정한다.
uint8_t *copy_chunk(const uint8_t *src, size_t len) {
    uint16_t n = len;          // (근본원인) 64→16bit 절단: len=0x10001 -> n=1
    uint8_t *buf = malloc(n);  // 절단된 크기로 할당 -> 1바이트
    if (!buf) return NULL;
    memcpy(buf, src, len);     // (폴트사이트) 원래 len 으로 복사 -> 힙 OOB write
    return buf;
}
```

```c
// harness.c: 트리거 입력 주입
#include <stdint.h>
#include <stddef.h>
uint8_t *copy_chunk(const uint8_t *src, size_t len);
int main(void) {
    static uint8_t src[0x10001];              // 65537 바이트
    return copy_chunk(src, sizeof src) ? 0 : 1; // len=0x10001 (트리거)
}
```

8행이 좁히는 대입, 9행이 할당, 11행이 복사다. `len`이 0x10001이면 `n`은 1이 되고, 1바이트 버퍼에 65,537바이트가 쓰인다.

## NDK 27로 빌드해 x86_64 에뮬레이터에 올리기

실행은 Android 13(API 33) `google_apis` x86_64 에뮬레이터 이미지에서 했다. userdebug 빌드에 보안 패치 수준은 2024-03-01, 커널은 5.15다. 이 이미지는 `ro.product.cpu.abilist`가 `x86_64` 하나뿐이라 32비트 사용자 공간이 없다. 그래서 32비트 실험만 Android 9 x86 AVD를 따로 잠깐 띄웠다. 컴파일러는 NDK 27.3에 들어 있는 clang 18.0.4이고 호스트는 Windows다.

새니타이저로 ASan을 고른 데는 사정이 있다. [NDK ASan 가이드](https://developer.android.com/ndk/guides/asan) 맨 위에는 2023년부터 ASan을 지원하지 않으니 HWASan을 쓰라는 공지가 붙어 있고, HWASan 권장 대상은 Android 14 이상 ARM64 기기다. 손에 있는 AVD가 전부 x86 계열이라 ASan밖에 쓸 수 없었다. ARM64에서 HWASan이 같은 버그를 어떻게 보고하는지는 재지 못했다. 그 가이드가 설명하는 것도 앱에 `wrap.sh`를 넣는 절차라서, 여기서는 실행 파일을 `/data/local/tmp`에 올리고 NDK 런타임을 같은 폴더에 둔 뒤 `LD_LIBRARY_PATH`로 지정했다. 빌드는 전부 `-O0`이고, 최적화 빌드에서 진단 위치가 어떻게 바뀌는지는 보지 않았다.

```bash
# Git Bash 기준. 기기 경로가 Windows 경로로 바뀌지 않게 한다.
export MSYS_NO_PATHCONV=1
NDK="$ANDROID_HOME/ndk/27.3.13750724"
NDK_BIN="$NDK/toolchains/llvm/prebuilt/windows-x86_64/bin"
RT="$NDK/toolchains/llvm/prebuilt/windows-x86_64/lib/clang/18/lib/linux"
export PATH="$NDK_BIN:$PATH"   # 뒤에서 쓰는 llvm-symbolizer도 여기 있다
CC="$NDK_BIN/clang.exe --target=x86_64-linux-android33 -g -O0 -fno-omit-frame-pointer -ffile-prefix-map=$(cygpath -w "$PWD")=."

mkdir -p out/rt
cp "$RT/libclang_rt.asan-x86_64-android.so" out/rt/
$CC vuln.c harness.c -o out/vuln_plain
$CC -fsanitize=address,implicit-conversion,signed-integer-overflow vuln.c harness.c -o out/vuln_san

adb -s emulator-5602 shell mkdir -p /data/local/tmp/p3c11
adb -s emulator-5602 push "$(cygpath -m out/vuln_san)" /data/local/tmp/p3c11/
adb -s emulator-5602 push "$(cygpath -m out/rt/libclang_rt.asan-x86_64-android.so)" /data/local/tmp/p3c11/
adb -s emulator-5602 shell chmod 755 /data/local/tmp/p3c11/vuln_san
adb -s emulator-5602 shell "cd /data/local/tmp/p3c11 && LD_LIBRARY_PATH=. ./vuln_san"
```

`-ffile-prefix-map`은 디버그 정보의 소스 경로를 `./vuln.c`처럼 상대 경로로 바꾸려고 넣었다. 같은 스크립트를 다시 돌리면 바이트 단위로 같은 바이너리가 나왔다. Windows 호스트에서 push한 파일에는 실행 비트가 붙지 않아서 `chmod 755`를 따로 준다.

처음 한 번은 Git Bash가 넘긴 호스트 경로를 Windows용 adb가 찾지 못해 `push`가 `cannot stat`으로 실패했는데, 그걸 놓치고 그대로 실행했다. 폴더에 NDK 런타임이 없으니 userdebug 이미지에 들어 있는 `/system/lib64/libclang_rt.asan-x86_64-android.so`가 대신 로드됐다. BuildId가 NDK 런타임과 다른 이 런타임으로는 10번 중 4번이 `AddressSanitizer: SEGV on unknown address`와 `nested bug in the same thread, aborting`으로 죽었다. 이 버그와 아무 상관 없는 죽음이다. 이미지 런타임은 같은 오버플로를 `0 bytes to the right of 1-byte region`이라고 적고 NDK 27 런타임은 `0 bytes after 1-byte region`이라고 적으니, 문구와 스택 #0 줄의 경로·BuildId를 보면 어느 런타임이 올라왔는지 바로 갈린다. 위 명령에서 호스트 경로를 `cygpath -m`으로 바꿔 넘기는 것도 이 일을 겪고 나서다.

## UBSan은 8행, ASan은 11행과 9행

`vuln_san` 한 번 실행에 두 도구의 보고가 모두 나온다.

![vuln_san 실행 결과. UBSan이 vuln.c:8:18에서 size_t 값 65537이 uint16_t로 바뀌며 1이 됐다고 보고하고, 같은 실행에서 ASan이 heap-buffer-overflow, WRITE of size 65537, 0 bytes after 1-byte region을 보고한다. 기기 스택은 모듈+오프셋뿐이고, 호스트 llvm-symbolizer로 푼 결과는 ASan 런타임의 __asan_memcpy, copy_chunk at vuln.c:11:5, copy_chunk at vuln.c:9:20, main at harness.c:7:12](/assets/img/android-mastery/p3c11/01-ubsan-asan-two-sites.png)

먼저 UBSan이 `vuln.c:8:18`에서 64비트 값 65537이 16비트 값 1로 바뀌었다고 알린다. 18열은 대입 오른쪽의 `len` 자리다. UBSan은 기본이 recover 모드라서 경고만 남기고 실행을 계속한다. 11행 memcpy에 들어서는 순간 ASan이 `heap-buffer-overflow`를 잡고, 1바이트 영역 바로 뒤에 65,537바이트를 쓰려 했다고 보고한 뒤 abort한다. 종료 코드는 134였고, 같은 바이너리를 세 번 더 돌려도 줄 번호와 오프셋은 바뀌지 않았다.

기기에서 찍힌 ASan 스택에는 함수 이름이 없다. `vuln_san+0x40ea`처럼 모듈과 오프셋만 있을 뿐이다. 기기에 심볼라이저가 없어서다. UBSan 쪽 `파일:줄:열`이 기기에서 바로 읽히는 건 컴파일러가 검사 지점마다 위치 정보를 바이너리에 박아 두기 때문이다. 오프셋은 호스트의 `llvm-symbolizer`에 그대로 넘기면 된다. 새니타이저가 찍는 프레임 주소는 이미 호출 명령 쪽으로 보정된 값이라 손댈 필요가 없다.

```bash
llvm-symbolizer --pretty-print --basenames --obj=out/rt/libclang_rt.asan-x86_64-android.so 0xdbf83 0xdd72f
llvm-symbolizer --pretty-print --basenames --obj=out/vuln_san 0x40ea 0x40b6 0x415f
```

풀어 보면 WRITE 스택 #0은 ASan 계측이 memcpy 호출을 바꿔 부르는 런타임 함수 `__asan_memcpy`(`asan_interceptors_memintrinsics.cpp:63`)이고, #1이 `copy_chunk at vuln.c:11:5`, 할당 스택은 `copy_chunk at vuln.c:9:20`, 둘을 부른 곳은 `main at harness.c:7:12`다. NDK의 `ndk-stack`은 logcat 툼스톤은 잘 풀었지만 이 ASan 보고에는 아무것도 출력하지 않아서, ASan 오프셋은 `llvm-symbolizer`에 직접 넣었다.

버그 하나가 세 줄에 걸쳐 있고 도구마다 다른 줄을 준다. 3부 1장의 증상·트리거·폴트 사이트·근본 원인으로 나눠 보면 이렇다.

| 구분 | 이 버그에서 | 어디서 보이나 |
|--|--|--|
| 증상 | ASan `heap-buffer-overflow`, WRITE of size 65537, exit 134. 새니타이저가 없으면 exit 0이거나 엉뚱한 free에서 abort | ASan 보고, 아래 Scudo 실험 |
| 트리거 | `len`이 0x10000 이상. 그때부터 `n`은 `len`의 하위 16비트라 `len`보다 작다(0x10000이면 0, 0x10001이면 1) | 회귀 시드 결과 |
| 폴트 사이트 | `vuln.c:11` memcpy | ASan WRITE 스택 #1 |
| 근본 원인 | `vuln.c:8` `uint16_t n = len`. 불변식 "할당 크기 ≥ 접근 크기"가 깨지는 줄 | UBSan `vuln.c:8:18` |

9행 malloc은 둘 사이에 있다. 잘못된 크기가 메모리 배치로 굳는 곳이고, ASan은 그 위치를 할당 스택으로 따로 준다.

### 도구를 하나씩만 켰을 때

같은 두 소스를 플래그만 바꿔 다시 빌드해 돌렸다.

| 빌드 플래그 | 보이는 진단 | 종료 코드 |
|--|--|--|
| 없음 | 없음 | 0 |
| `-fsanitize=undefined` | 없음 | 0 |
| `-fsanitize=implicit-conversion` | `vuln.c:8:18` 절단 경고, 실행은 계속 | 0 |
| `-fsanitize=address` | WRITE of size 65537, memcpy 줄 오프셋 | 134 |
| address, implicit-conversion, signed-integer-overflow | 8:18 경고 뒤 ASan 보고 | 134 |
| address, implicit-conversion에 `-fno-sanitize-recover=implicit-conversion` 추가 | 8:18 경고와 SUMMARY 줄 직후 Aborted, ASan 보고 없음 | 134 |

`-fsanitize=undefined`가 아무것도 잡지 못한 게 먼저 눈에 걸렸다. 그 이유는 뒤에서 kinds.c로 따로 확인했다. `implicit-conversion`만 켠 빌드는 근본 원인 줄을 정확히 짚고도 0으로 끝났다. memcpy가 힙을 65,537바이트 덮었는데 그 사실을 아는 쪽이 없는 상태다. `UBSAN_OPTIONS=print_stacktrace=1`을 주면 UBSan도 스택을 찍지만, 기기에서는 역시 `vuln_ubsan+0x18b3` 같은 오프셋만 나온다.

마지막 줄의 fail-fast 빌드는 근본 원인 줄에서 바로 멈추고 memcpy까지 가지 않으니 ASan 보고도 아예 없다. 퍼저나 CI에서 원인 줄 하나만 받고 싶을 때 쓸 만한 조합이다.

## 새니타이저 없는 빌드는 이웃을 free할 때에야 죽는다

새니타이저 없이 돌리면 언젠가 힙 메타데이터를 밟고 엉뚱한 곳에서 abort가 날 거라고 예상했다. glibc에서 흔히 보는 `malloc(): corrupted top size` 같은 메시지를 기대했다. 실제로는 아무 일도 없었다. `vuln_plain`을 10번 돌려 10번 모두 종료 코드 0, 따로 50번을 더 돌려도 전부 0이었다. 1바이트 청크 뒤로 65,537바이트를 써도 프로세스는 아무렇지 않게 끝난다.

크래시를 보려면 덮인 이웃을 누군가 건드려야 한다. 같은 크기 클래스의 이웃을 먼저 64개 잡아 두고, 결함을 실행한 뒤 이웃을 해제하는 harness를 따로 만들었다.

```c
// harness_free.c: 같은 결함 뒤에 평범한 힙 작업이 이어지는 경우
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
uint8_t *copy_chunk(const uint8_t *src, size_t len);
int main(void) {
    static uint8_t src[0x10001];
    void *peers[64];
    for (int i = 0; i < 64; i++) peers[i] = malloc(1);   // 같은 크기 클래스 이웃
    uint8_t *buf = copy_chunk(src, sizeof src);          // 결함 실행
    fprintf(stderr, "copy_chunk returned\n");
    for (int i = 0; i < 64; i++) free(peers[i]);         // 이웃 해제
    free(buf);
    fprintf(stderr, "clean exit\n");
    return 0;
}
```

처음에는 메시지를 stdout에 찍었다가 통째로 잃었다. adb 셸 너머로 파이프에 연결된 stdout은 블록 단위로 버퍼링되고, abort하는 프로세스는 그 버퍼를 비우지 못한다. 그래서 stderr로 바꿨다.

![새니타이저 없는 빌드. 원래 harness.c로 만든 vuln_plain은 10번 모두 종료 코드 0, 이웃을 free하는 vuln_plain_free는 20번 중 19번 134이고 한 번은 0. 한 번 더 돌린 실행은 copy_chunk returned 뒤 exit=134. ndkstack(ndk-stack.cmd를 부르는 셸 함수)으로 푼 크래시는 Abort message Scudo ERROR: corrupted chunk header이고 백트레이스는 scudo reportHeaderCorruption과 Allocator deallocate를 거쳐 main의 ./harness_free.c:12:34를 가리키며 copy_chunk는 없다](/assets/img/android-mastery/p3c11/02-plain-scudo-drift.png)

이번에는 20번 중 19번이 134로 죽었다. 50번을 더 돌렸을 때는 48번 abort, 2번 정상 종료였다. 같은 입력이 실행마다 죽기도 하고 안 죽기도 한다. `logcat -b crash`로 받은 툼스톤을 `ndk-stack -sym out`에 넣으면 abort 메시지가 `Scudo ERROR: corrupted chunk header`로 나오고, 백트레이스는 `scudo::reportHeaderCorruption`과 `Allocator::deallocate`를 거쳐 `main`의 `harness_free.c:12:34`, 이웃을 해제하는 `free(peers[i])`에서 멈춘다. 캡처에 보이는 `ndkstack`은 NDK의 `ndk-stack.cmd`를 Git Bash에서 부르려고 만든 셸 함수다. 백트레이스 어디에도 `copy_chunk`는 없다. 툼스톤만 보고 RCA를 시작하면 엉뚱하게 free 루프부터 의심하게 된다.

Android 11부터 네이티브 코드의 기본 할당기는 [Scudo](https://source.android.com/docs/security/test/scudo)다(저메모리 기기는 여전히 jemalloc을 쓴다). 청크마다 헤더에 16비트 체크섬이 있다. 에뮬레이터 libc에 맞춰 Android 13 브랜치 소스를 보면 [`loadHeader`](https://android.googlesource.com/platform/external/scudo/+/refs/heads/android13-qpr3-release/standalone/chunk.h#121)가 헤더를 읽을 때 체크섬을 다시 계산해 맞지 않으면 `reportHeaderCorruption`을 부른다. 그 함수가 [`corrupted chunk header at address %p`](https://android.googlesource.com/platform/external/scudo/+/refs/heads/android13-qpr3-release/standalone/report.cpp#65)를 찍고 프로세스를 끝낸다. 이번 크래시에서 헤더를 읽은 쪽은 해제 경로였다. 이웃을 free하지 않는 `harness.c`가 60번 모두 멀쩡히 끝난 것도 같은 이유로 설명된다. 덮인 헤더를 아무도 다시 읽지 않았다.

죽고 안 죽고가 갈리는 이유로는 블록 배치가 의심된다. [`primary64.h`](https://android.googlesource.com/platform/external/scudo/+/refs/heads/android13-qpr3-release/standalone/primary64.h#34) 주석에 따르면 Scudo는 주소 패턴을 예측하기 어렵게 하려고 블록을 섞는다. 실행마다 1바이트 버퍼 뒤에 무엇이 놓이는지가 달라지니 결과도 흔들린다고 보는 게 자연스럽다. 다만 실행마다 블록 배치를 덤프해 확인하지는 않았다.

비교하려고 같은 소스를 WSL Ubuntu 24.04(glibc 2.39, gcc 13.3.0)에서도 빌드했다. `harness.c`는 세 번 모두 exit 0, free가 있는 harness는 세 번 모두 같은 `free(): invalid next size (fast)`로 abort했다. 기대했던 `malloc(): corrupted top size`는 어느 쪽에서도 나오지 않았다.

### 덮인 이웃 청크 세어 보기

크래시와 별개로, 넘친 바이트가 살아 있는 다른 할당의 내용을 바꾸는지 보고 싶었다. `src`를 `'A'`로 채우고 이웃 64개의 첫 바이트를 0으로 둔 다음, `copy_chunk` 뒤에 `'A'`로 바뀐 이웃을 셌다. 헤더 검사를 피하려고 free는 하지 않았다.

```c
// harness_peek.c: OOB write 가 이웃 청크 내용을 공격자 바이트로 덮는지 확인
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint8_t *copy_chunk(const uint8_t *src, size_t len);
int main(void) {
    static uint8_t src[0x10001];
    memset(src, 'A', sizeof src);                        // 공격자가 고른 내용
    uint8_t *peers[64];
    for (int i = 0; i < 64; i++) { peers[i] = malloc(1); peers[i][0] = 0; }
    uint8_t *buf = copy_chunk(src, sizeof src);
    int hit = 0;
    for (int i = 0; i < 64; i++) hit += (peers[i][0] == 'A');
    printf("buf=%p  peers overwritten with 'A': %d/64\n", (void *)buf, hit);
    return 0;                                            // free 하지 않는다(헤더 검사 회피)
}
```

```
buf=0x7f5958a87a90  peers overwritten with 'A': 7/64
buf=0x77f5f056ac30  peers overwritten with 'A': 0/64
buf=0x7a5d1f264c90  peers overwritten with 'A': 0/64
buf=0x7c32fc72ea50  peers overwritten with 'A': 5/64
buf=0x7e55760436f0  peers overwritten with 'A': 11/64
buf=0x7d8552768730  peers overwritten with 'A': 11/64
buf=0x7f7f4de8a7b0  peers overwritten with 'A': 9/64
buf=0x7c699c866a10  peers overwritten with 'A': 10/64
```

50번 돌렸을 때 47번은 이웃 1개에서 13개까지가 `'A'`로 바뀌었고, 3번은 하나도 바뀌지 않았다. 길이와 내용이 모두 입력에서 오는 힙 OOB write로 살아 있는 이웃 할당을 덮는다는 것까지는 관측으로 확인됐다. 어느 이웃이 덮이는지는 매번 다르다.

3부 7장의 기준으로 영향을 매기면, 이 PoC가 보여 준 것은 프로세스를 죽이는 DoS와 힙 OOB write 프리미티브의 존재다. 제어 흐름 탈취는 시도하지 않았다. 거기까지 가려면 무엇을 이웃에 앉힐지 고르는 힙 배치와 [완화 기법](/posts/android-concept-atlas-c37-exploit-mitigations/) 우회가 따로 필요하고, Scudo가 블록을 섞는다는 사실 자체가 그 배치를 어렵게 만든다. 이 결과를 RCE라고 부를 근거는 없다.

## 플래그마다 보이는 정수 결함이 다르다

`-fsanitize=undefined`가 절단을 못 본 이유를 확인하려고 정수 결함 네 유형을 한 번씩 밟는 `kinds.c`를 만들었다. 값은 모두 `volatile` 변수에서 읽어 컴파일러가 미리 계산하지 못하게 했다.

```c
// kinds.c 7~15행 발췌(main 안)
    volatile uint32_t count = 0x10001, elem = 0x10000;  // 부호 없는 곱셈 wrap
    volatile int32_t  a = INT32_MAX;                    // 부호 있는 오버플로
    volatile size_t   len = 0x10001;                    // 64->16bit 절단
    volatile int32_t  neg = -1;                         // 부호 혼동

    uint32_t total = count * elem;
    int32_t  b     = a + 1;
    uint16_t n     = len;
    size_t   s     = neg;
```

![kinds.c 12~15행(부호 없는 곱셈, 부호 있는 +1, 64에서 16비트로의 절단, -1을 size_t로)을 네 빌드로 실행한 화면. 새니타이저 없는 kinds_plain은 total=0x10000 b=-2147483648 n=0x1 s=0xffffffffffffffff를 출력하고, -fsanitize=undefined는 13:24 signed integer overflow만, implicit-conversion을 더하면 14:22와 15:22 implicit conversion, unsigned-integer-overflow까지 더하면 12:28의 65537×65536 unsigned integer overflow까지 보고한다](/assets/img/android-mastery/p3c11/03-ubsan-flag-matrix.png)

| 유형 | kinds.c | 새니타이저 없이 나온 값 | 처음 잡힌 플래그 |
|--|--|--|--|
| 부호 없는 곱셈 wrap | 12행 `count * elem` | 0x10000 | `unsigned-integer-overflow` |
| 부호 있는 오버플로 | 13행 `a + 1` | -2147483648 | `undefined`에 포함된 `signed-integer-overflow` |
| 64→16비트 절단 | 14행 `n = len` | 0x1 | `implicit-conversion` |
| 음수를 `size_t`로 | 15행 `s = neg` | 0xffffffffffffffff | `implicit-conversion` |

새니타이저 없이는 네 값이 모두 소리 없이 바뀐다. `-fsanitize=undefined`가 잡은 건 13행 하나다. [clang 18 UBSan 문서](https://releases.llvm.org/18.1.0/tools/clang/docs/UndefinedBehaviorSanitizer.html)를 보면 `undefined` 그룹은 `float-divide-by-zero`, `unsigned-integer-overflow`, `implicit-conversion`, `local-bounds`, `nullability-*`를 뺀 나머지다. 이 가운데 `unsigned-integer-overflow`와 `implicit-conversion`이 빠진 건 이 검사들이 잡는 일이 C 표준상 정의된 동작이기 때문이다. 부호 있는 정수의 오버플로는 정의되지 않은 동작(UB)이지만, 부호 없는 산술은 2^n으로 나눈 나머지로 감기도록 정해져 있고 좁히는 변환도 값이 바뀔 뿐 규칙대로 일어난다. 문서도 이런 검사가 잡는 문제는 UB는 아니지만 의도하지 않은 경우가 많다고만 적는다.

절단과 부호 혼동은 `implicit-conversion`을 따로 켜야 나온다. clang 18에서 이 그룹은 `implicit-unsigned-integer-truncation`, `implicit-signed-integer-truncation`, `implicit-integer-sign-change`로 이루어진다. 12행의 부호 없는 곱셈은 `unsigned-integer-overflow`를 명시해야만 나왔다. 이 검사는 감기는 부호 없는 산술을 전부 보고하니, 해시처럼 일부러 감기게 짠 코드까지 걸린다. 크기 계산의 wrap만 보고 싶다면 켜는 범위를 좁혀야 한다.

### Android IntSan의 검사 집합으로는 이 절단이 지나간다

Android 플랫폼은 모듈 단위로 정수 새니타이저를 켠다. [IntSan 문서](https://source.android.com/docs/security/test/intsan)에 따르면 Android 7.0에서 미디어 프레임워크를 단단하게 하려고 부호 있는·없는 정수 오버플로 새니타이저를 넣었고, Android 9에서 범위를 넓혔다. 모듈은 `Android.bp`의 `sanitize: { integer_overflow: true }`로 켠다.

soong의 [`cc/sanitize.go` 1477~1479행](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go#1477)을 보면 이 속성이 덧붙이는 검사는 `unsigned-integer-overflow`와 `signed-integer-overflow`뿐이다. 같은 파일 [961~964행](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go#961)은 정수 계열 새니타이저 플래그가 있으면 `-fno-sanitize=implicit-integer-sign-change`를 덧붙이는데, 주석에는 이 검사를 켜면 Android 코어가 아직 부팅하지 못한다고 적혀 있다(b/119329758).

같은 검사 집합으로 `vuln.c`와 `kinds.c`를 빌드해 돌렸다. 기기용 빌드에 붙는 [`-fsanitize-trap=all`](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go#86)도 넣었다.

```bash
CCN="$NDK_BIN/clang.exe --target=x86_64-linux-android33 -g -O0 -ffile-prefix-map=$(cygpath -w "$PWD")=."
I="-fsanitize=unsigned-integer-overflow,signed-integer-overflow -fsanitize-trap=all"
$CCN $I vuln.c harness.c -o out/vuln_intsan
$CCN $I kinds.c -o out/kinds_intsan
```

```
vuln_intsan exit=0
kinds_intsan exit=132
Illegal instruction
10-14 11:07:14.778  7518  7518 F DEBUG   : signal 4 (SIGILL), code 2 (ILL_ILLOPN), fault addr 0x0000632c803f778b
10-14 11:07:14.779  7518  7518 F DEBUG   :       #00 pc 000000000000178b  /data/local/tmp/p3c11/kinds_intsan (main+75)
```

`kinds_intsan`은 12행 곱셈(`llvm-symbolizer`로 `kinds.c:12:28`, 그 주소의 명령은 `ud1l`)에서 SIGILL로 끝났고, `vuln_intsan`은 힙을 덮은 채 0으로 종료했다. copy_chunk의 64→16비트 절단은 IntSan이 보는 대상이 아니다. 실제 플랫폼 빌드는 ASan 같은 다른 새니타이저나 `diag` 설정이 없으면 정수 검사의 trap을 끄고 minimal runtime을 붙인다([954~958행](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go#954)). 붙는 플래그는 [80~81행](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go#80)에, 그 조건은 [1756행](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go#1756) `enableMinimalRuntime`에 있다. 그러면 죽는 방식이 SIGILL에서 abort로 바뀔 것이다. 그 빌드는 만들어 보지 않았고, 검사 대상 집합은 어느 쪽이든 같다.

## 캐스트와 memcpy 앞 검사는 버그를 남겼다

명시 캐스트로 경고만 지운 것, memcpy 앞에 검사를 건 것, 좁히기 전에 길이를 거부한 것을 같은 시드에 돌렸다.

```c
// fix_cast.c 7행: 경고만 끄는 "패치"(명시적 캐스트)
    uint16_t n = (uint16_t)len;  // 캐스트로 바꿨을 뿐, 절단은 그대로

// fix_symptom.c 6~12행: 폴트사이트에 경계 검사를 붙인 증상 패치
uint8_t *copy_chunk(const uint8_t *src, size_t len) {
    uint16_t n = len;               // 절단은 그대로 남아 있다
    uint8_t *buf = malloc(n);
    if (!buf) return NULL;
    if (len <= n) memcpy(buf, src, len);  // memcpy 만 막는다
    return buf;                     // 호출자는 len 바이트짜리라고 믿는다
}

// fix_root.c 6~13행: 크기가 아직 size_t 일 때 검증하는 근본원인 패치
uint8_t *copy_chunk(const uint8_t *src, size_t len) {
    if (len == 0 || len > UINT16_MAX) return NULL;  // 좁히기 전에 거부
    uint16_t n = (uint16_t)len;     // 이제 값이 보존되는 좁힘
    uint8_t *buf = malloc(n);
    if (!buf) return NULL;
    memcpy(buf, src, n);
    return buf;
}
```

harness도 바꿨다. 앞의 `harness.c`는 반환값이 NULL인지만 보니, 함수가 돌려준 버퍼를 실제 호출자처럼 쓰는 쪽이 필요했다. `harness_len.c`는 길이를 인자로 받아 `copy_chunk`를 부르고, 돌려받은 버퍼를 `len` 바이트만큼 읽는다.

```c
// harness_len.c: 헤더 길이를 인자로 받아 넣고, 호출자처럼 결과를 len 바이트로 소비한다
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
uint8_t *copy_chunk(const uint8_t *src, size_t len);
int main(int argc, char **argv) {
    static uint8_t src[0x10001];
    size_t len = strtoull(argv[1], NULL, 0);
    uint8_t *buf = copy_chunk(src, len);
    if (!buf) { printf("len=%#zx rejected\n", len); return 0; }
    unsigned sum = 0;
    for (size_t i = 0; i < len; i++) sum += buf[i];   // 호출자: len 바이트를 읽는다
    printf("len=%#zx ok sum=%u\n", len, sum);
    free(buf);
    return 0;
}
```

네 변형 모두 `-fsanitize=address,implicit-conversion`으로 빌드해 `reg_<변형>`으로 올리고, 시드 다섯 개를 넣어 진단 토큰만 뽑았다.

```bash
for v in vuln fix_cast fix_symptom fix_root; do for s in 0x100 0xFFFF 0x10000 0x10001 0x100000000; do \
  printf '%-12s %-12s ' $v $s; adb -s emulator-5602 shell "cd /data/local/tmp/p3c11 && LD_LIBRARY_PATH=. ./reg_$v $s 2>&1" \
  | grep -oE "runtime error: implicit conversion|ERROR: AddressSanitizer: [a-z-]+|(READ|WRITE) of size [0-9]+|ok sum=[0-9]+|rejected" \
  | sed -E 's/runtime error: implicit conversion/UBSan:implicit-conversion/; s/ERROR: AddressSanitizer: /ASan:/' | paste -sd' '; done; done
```

![패치 세 변형의 핵심 줄을 grep한 뒤 vuln, fix_cast, fix_symptom, fix_root를 시드 0x100, 0xFFFF, 0x10000, 0x10001, 0x100000000으로 돌린 20행 결과. fix_cast는 UBSan 경고 없이 heap-buffer-overflow WRITE가 남고, fix_symptom은 정상 입력은 ok지만 큰 시드에서 UBSan 경고와 heap-buffer-overflow READ of size 1, fix_root는 큰 시드 셋을 모두 rejected. 마지막 줄 llvm-symbolizer 결과는 main at harness_len.c:12:45](/assets/img/android-mastery/p3c11/04-patch-regression.png)

캐스트 패치 행에서는 UBSan 토큰이 전부 사라졌다. OOB는 원본과 똑같이 남아 ASan만 잡는다. `implicit-conversion`은 이름 그대로 암묵 변환만 검사하고, `(uint16_t)` 캐스트를 쓰는 순간 그 대입은 명시 변환이 된다. 문서에서 명시 캐스트를 따로 언급한 대목은 찾지 못했고, 동작은 이 실행으로 확인했다.

증상 패치는 처음 예상이 틀렸다. `n`이 이미 틀렸으니 이 검사가 정상 입력까지 막을 거라고 봤는데, 0x100과 0xFFFF는 멀쩡히 통과했다. 절단이 일어나는 입력에서만 memcpy를 건너뛴다. 문제는 그다음이다. 함수는 내용이 채워지지 않은 1바이트 버퍼를 성공처럼 돌려주고, 호출자는 그걸 `len` 바이트짜리라고 믿고 읽는다. 0x10001 시드의 원문은 이렇다.

```
fix_symptom.c:7:18: runtime error: implicit conversion from type 'size_t' (aka 'unsigned long') of value 65537 (64-bit, unsigned) to type 'uint16_t' (aka 'unsigned short') changed the value to 1 (16-bit, unsigned)
==6446==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x502000000031 at pc 0x5d6746cae596 bp 0x7ffeb3371aa0 sp 0x7ffeb3371a98
READ of size 1 at 0x502000000031 thread T0
    #0 0x5d6746cae595  (/data/local/tmp/p3c11/reg_fix_symptom+0x4595)
    #1 0x72a3c9bd2cc9  (/apex/com.android.runtime/lib64/bionic/libc.so+0x50cc9) (BuildId: f090904cc3ac285a6f190f8003c3eb0e)
0x502000000031 is located 0 bytes after 1-byte region [0x502000000030,0x502000000031)
allocated by thread T0 here:
```

`+0x4595`는 `main at harness_len.c:12:45`, 호출자의 읽기 루프다. 할당 스택은 `copy_chunk` `fix_symptom.c:8:20`에서 `main` `harness_len.c:9:20`으로 이어진다. 폴트 사이트는 함수 안의 WRITE에서 호출자의 READ로 옮겨 갔고, 1바이트 버퍼를 len 바이트로 다루는 불일치는 그대로다. UBSan도 `fix_symptom.c:7:18`의 절단을 그대로 보고한다. harness가 반환 버퍼를 읽지 않았다면 이 READ는 보이지 않았을 것이고, 증상 패치는 깨끗해 보였을 것이다.

근본 원인 패치는 큰 시드 셋을 모두 `rejected`로 돌려보냈고 정상 입력은 통과했다. 새니타이저 진단은 하나도 없었다.

0x10000과 0x100000000 시드는 결과를 읽을 때 조심해야 했다. 0x10000을 넣으면 `n`은 0이 되어 `malloc(0)`이 불린다. 그런데 ASan은 이것도 `1-byte region`이라고 보고한다. ASan 할당기가 크기 0 요청을 1로 바꿔 잡기 때문이다([`asan_allocator.cpp` 544~551행](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.0/compiler-rt/lib/asan/asan_allocator.cpp#L544-L551)). 영역 크기만 보고 `n`을 거꾸로 추정하면 틀리고, UBSan 줄의 `changed the value to 0`을 봐야 한다.

0x100000000 시드에서 원본과 캐스트 패치는 `global-buffer-overflow READ of size 4294967296`을 먼저 보고했다. ASan 계측이 memcpy 대신 부르는 `__asan_memcpy`는 원본 범위를 대상 범위보다 먼저 검사하고([`asan_interceptors_memintrinsics.cpp` 28~35행](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.0/compiler-rt/lib/asan/asan_interceptors_memintrinsics.cpp#L28-L35)), 이 harness의 `src`는 65,537바이트짜리 전역 배열이라 원본 쪽이 먼저 넘친다. harness 구조 때문에 생긴 행이라 버그 해석에는 쓰지 않았다.

회귀 시드는 이 다섯 값을 그대로 쓴다. 0x100은 평범한 정상 입력, 0xFFFF는 통과해야 하는 최댓값, 0x10000은 `n`이 0이 되는 경계, 0x10001은 원래 트리거, 0x100000000은 하위 32비트가 모두 0인 값이다. 패치 판정은 함수 안의 memcpy와 함께, 호출자가 믿는 버퍼 길이에 대해서도 "할당 크기 ≥ 접근 크기"가 성립하는지로 한다. 패치 diff에서 이런 불변식을 세우는 방법은 3부 16장에서 따로 다룬다.

## 32비트에서만 감기는 크기 곱셈

정수 버그가 실제로 버그인지 여부가 대상 ABI에 따라 갈리는 경우가 있다. 레코드 개수와 레코드 크기를 곱해 할당하는 흔한 모양으로 확인했다.

```c
// mul.c: 같은 소스가 ABI 에 따라 감기거나 안 감기는 크기 곱셈
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_TOTAL (16u << 20)  // 16 MiB 상한

uint8_t *alloc_records(uint32_t count, uint32_t elem) {
    size_t total;
#ifndef FIX
    total = (size_t)count * elem;              // LP64: 64비트 곱, ILP32: 32비트 곱
#else
    if (__builtin_mul_overflow(count, elem, &total)) return NULL;  // 넘치면 거부
#endif
    if (total > MAX_TOTAL) return NULL;         // 상한 검사는 감긴 값을 본다
    uint8_t *p = malloc(total);
    if (!p) return NULL;
    for (uint32_t i = 0; i < count; i++)
        memset(p + (size_t)i * elem, 'A', elem); // 레코드마다 elem 바이트
    return p;
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IONBF, 0);
    uint32_t count = strtoul(argv[1], NULL, 0), elem = strtoul(argv[2], NULL, 0);
    printf("sizeof(size_t)=%zu count=%#x elem=%#x\n", sizeof(size_t), count, elem);
    uint8_t *p = alloc_records(count, elem);
    printf("%s\n", p ? "allocated" : "rejected");
    free(p);
    return 0;
}
```

곱하기 전에 `size_t`로 넓히는 습관은 64비트에서는 효과가 있다. `size_t`가 64비트면 `uint32_t` 두 개의 곱이 넘칠 수 없다. 32비트 ABI에서는 `size_t`가 32비트라 이 캐스트가 아무 일도 하지 않는다. Android 9 x86 AVD에서 i686 빌드를, 주 AVD에서 x86_64 빌드를 돌렸고 두 ABI 모두 `-fsanitize=address,unsigned-integer-overflow`로 빌드했다.

![mul.c 11, 13, 15행을 보인 뒤 같은 입력 0x10001과 0x10000을 넣은 결과. x86_64 빌드는 sizeof(size_t)=8에서 rejected, Android 9 x86 AVD의 i686 빌드는 sizeof(size_t)=4에서 mul.c:11:27 unsigned integer overflow 후 heap-buffer-overflow WRITE of size 65536이 65536-byte region 바로 뒤에서 나고 llvm-symbolizer는 alloc_records at mul.c:19:9, 곱셈 넘침 검사를 넣은 mul_i686_fix는 rejected](/assets/img/android-mastery/p3c11/05-abi-mul-wrap.png)

입력은 0x10001 × 0x10000이다. x86_64에서는 곱이 0x100010000으로 온전하게 나오고 16 MiB 상한에 걸려 거부된다. i686에서는 곱이 0x10000, 64 KiB로 감긴다. 상한 검사를 가볍게 통과하고 64 KiB가 할당된 뒤, 두 번째 레코드를 쓰는 19행 memset이 영역 바로 뒤를 쓴다. 할당 스택은 `mul.c:16:18`의 malloc, 호출은 `main`의 `mul.c:27:18`이다. 정상 입력인 0x10 × 0x100은 두 ABI, 두 빌드 모두에서 `allocated`였다.

i686에서도 15행 상한 검사는 돌았다. 다만 그때 `total`은 이미 0x10000으로 감겨 있었다. `__builtin_mul_overflow`([clang 문서](https://clang.llvm.org/docs/LanguageExtensions.html#checked-arithmetic-builtins))로 곱셈 자체에서 넘침을 판정하면 i686에서도 x86_64에서도 같은 입력이 거부된다. x86_64 빌드만 돌렸다면 이 입력은 rejected로 끝났고 버그는 재현되지 않은 채 닫혔을 것이다. 그래서 정수 버그 RCA 기록에는 대상 ABI를 같이 적는다.

## Stagefright의 정수 검사도 32비트에서 다시 감겼다

2015년 libstagefright 버그 묶음에도 같은 모양이 여럿 있다. 아래는 NVD 설명과 AOSP 수정 커밋을 읽어 확인한 것이고, 직접 재현하지는 않았다.

| CVE | 위치 | 결함 | 수정 커밋 |
|--|--|--|--|
| [CVE-2015-1538](https://nvd.nist.gov/vuln/detail/CVE-2015-1538) | `SampleTable::setSampleToChunkParams` | 검사 없는 곱셈 | [2434839](https://android.googlesource.com/platform/frameworks/av/+/2434839bbd168469f80dd9a22f1328bc81046398%5E%21/) |
| [CVE-2015-3824](https://nvd.nist.gov/vuln/detail/CVE-2015-3824) | `MPEG4Extractor::parseChunk`, tx3g 아톰 | `size + chunk_size` 덧셈 넘침 | [463a6f8](https://android.googlesource.com/platform/frameworks/av/+/463a6f807e187828442949d1924e143cf07778c6%5E%21/) |
| [CVE-2015-3864](https://nvd.nist.gov/vuln/detail/CVE-2015-3864) | 같은 함수 | 3824 수정 검사식의 언더플로 | [6fe85f7](https://android.googlesource.com/platform/frameworks/av/+/6fe85f7e15203e48df2cc3e8e1c4bc6ad49dc968%5E%21/) |

1538의 수정은 `new SampleToChunkEntry[mNumSampleToChunkOffsets]` 앞에서 `SIZE_MAX / sizeof(SampleToChunkEntry) <= mNumSampleToChunkOffsets`이면 `ERROR_OUT_OF_RANGE`를 돌려준다. 할당 전에 곱셈 넘침을 거부하는 방식이고, 위 `mul.c`의 FIX와 같은 자리를 막는다. 3824의 수정도 같은 생각으로 `uint8_t[size + chunk_size]` 할당 앞에 `SIZE_MAX - chunk_size <= size` 검사를 넣었다. 같은 커밋에서 그 할당의 `new (std::nothrow)`도 그냥 `new`로 바뀌었다. 커밋 메시지는 두 값의 합이 2^32를 넘으면 작은 버퍼가 잡히고 힙 손상으로 이어진다고 설명한다.

![Google Git의 platform/frameworks/av 커밋 6fe85f7e15203e48df2cc3e8e1c4bc6ad49dc968 화면. 작성자 Nick Kralevich, 2015-08-07. 메시지는 MPEG4Extractor.cpp: handle chunk_size > SIZE_MAX, chunk_size가 uint64_t라 SIZE_MAX보다 클 수 있어 뺄셈이 언더플로한다는 설명과 Bug: 23034759. diff는 if (SIZE_MAX - chunk_size <= size)를 chunk_size > SIZE_MAX 조건을 앞에 붙인 검사로 바꾼다](/assets/img/android-mastery/p3c11/06-stagefright-3864-fix.png)

NVD는 3864를 3824의 불완전한 수정 때문에 생긴 취약점이라고 적는다. 커밋 메시지가 원인을 직접 말한다. `chunk_size`는 `uint64_t`라서 `SIZE_MAX`보다 클 수 있고, 그러면 `SIZE_MAX - chunk_size`가 언더플로한다. 32비트 빌드에서 `SIZE_MAX`는 2^32-1이니 그런 값이 실제로 들어올 수 있다. 뺄셈은 64비트로 계산돼 아주 큰 값으로 감기고, `<= size` 비교는 거짓이 되어 검사를 통과한다. 수정은 `chunk_size > SIZE_MAX`를 먼저 확인하는 조건을 더했다. 오버플로를 막으려고 쓴 산술이 `size_t` 폭에 따라 다시 감긴 사례이고, 위의 i686 실험과 같은 축에 있다.

## 고칠 자리와 확인하는 법

고칠 자리는 위 표에서 근본 원인으로 적은 8행이다. 신뢰 경계 밖에서 온 길이는 `size_t`처럼 넓은 타입으로 받아, 좁히기 전에 범위를 검증한다. `fix_root.c`가 그 모양이다. 곱셈과 덧셈이 끼면 `__builtin_mul_overflow`, `__builtin_add_overflow`로 넘침을 산술 지점에서 판정한다. 32비트 빌드가 남아 있는 코드라면 이게 상한 검사보다 먼저다. CVE-2015-3864처럼 검사식 자체가 감기기도 하니, 검사식에 들어가는 피연산자의 폭도 같이 확인한다.

경고를 끄는 캐스트는 리뷰에서 따로 본다. 크기 계산 경로에 `(uint16_t)`, `(uint32_t)` 같은 좁히는 캐스트가 새로 생겼다면, 그게 값 보존이 확인된 뒤의 캐스트인지 경고를 지우려고 붙인 캐스트인지 물어야 한다. 같은 모듈에서 좁히는 대입, `* elem`, `+ HDR` 같은 형제 패턴을 훑는 작업은 3부 17장의 variant analysis로 이어진다.

다시 돌릴 때는 이 순서로 확인한다.

1. 새니타이저 보고에 찍힌 런타임 경로와 BuildId가 NDK 런타임인지부터 본다. 시스템 이미지에 들어 있는 다른 런타임이 올라오면 버그와 무관한 SEGV가 섞인다.
2. 원본을 `-fsanitize=address,implicit-conversion -fno-sanitize-recover=implicit-conversion`으로 빌드해 트리거를 넣고, 근본 원인 줄(`vuln.c:8:18`)에서 멈추는지 본다. 고칠 줄을 먼저 못 박아 두는 단계다.
3. 패치한 쪽은 `-fsanitize=address,implicit-conversion`으로 빌드해, 반환 버퍼를 실제 호출자처럼 소비하는 harness로 위의 회귀 시드 다섯 개를 돌린다. 정상 입력은 통과하고 큰 입력은 거부되며 새니타이저 진단은 없어야 한다.
4. 곱셈이 있는 경로는 32비트 타깃(`--target=i686-linux-android28`)으로도 빌드해 0x10001 × 0x10000처럼 곱이 32비트를 넘는 입력을 넣는다.

IntSan이 켜진 모듈이라도 크기 계산에는 위의 검사를 직접 넣는다. `integer_overflow: true`가 켜는 검사에는 copy_chunk 같은 절단이 들어 있지 않고, 부호 없는 wrap 검사도 플랫폼은 모듈 단위로 골라 켠다. IntSan 문서의 `Android.bp` 예시에는 검사에서 뺄 함수를 적는 blocklist 항목도 함께 들어 있다.

참고: [clang 18 UndefinedBehaviorSanitizer](https://releases.llvm.org/18.1.0/tools/clang/docs/UndefinedBehaviorSanitizer.html) · [clang AddressSanitizer](https://clang.llvm.org/docs/AddressSanitizer.html) · [NDK ASan 가이드](https://developer.android.com/ndk/guides/asan) · [Scudo](https://source.android.com/docs/security/test/scudo) · [IntSan](https://source.android.com/docs/security/test/intsan) · [soong cc/sanitize.go](https://android.googlesource.com/platform/build/soong/+/d046c2afef086a35d24222b09f4d2c4914e8a2a5/cc/sanitize.go) · [clang checked arithmetic builtins](https://clang.llvm.org/docs/LanguageExtensions.html#checked-arithmetic-builtins)
