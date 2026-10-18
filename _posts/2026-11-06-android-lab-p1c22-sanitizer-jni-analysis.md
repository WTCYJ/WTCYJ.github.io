---
layout: post
title: "ASan·IntSan으로 JNI 버그 읽기 — 섀도 바이트에서 tombstone까지"
date: 2026-11-06 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ASan, HWASan, UBSan, IntSan, JNI, ndk-stack, wrapsh]
excerpt: "일부러 버그를 심은 C 코드를 Android 13 x86_64 에뮬레이터에서 ASan·UBSan·IntSan 빌드로 돌리고, wrap.sh로 앱 안의 JNI 라이브러리에도 ASan을 걸었다. 리포트의 섀도 바이트와 스택 순서를 읽고 ndk-stack으로 tombstone을 심볼화했다. 리드존을 건너뛰어 옆 블록에 착지한 쓰기는 ASan도 보고하지 않았고, 부호 없는 곱셈의 감김은 -fsanitize=undefined로는 잡히지 않고 unsigned-integer-overflow를 명시해야 잡혔다."
---

[21장](/posts/android-lab-p1c21-ghidra-rizin-native/)에서는 스트립된 `.so`를 Rizin과 Ghidra로 열어 함수가 어디 있는지를 파일만 보고 찾았다. 위치를 알아도 그 함수가 메모리를 실제로 어떻게 망가뜨리는지는 정적 분석만으로 확정하기 어렵다. 이번에는 반대쪽 도구를 썼다. 컴파일러가 모든 메모리 접근 앞에 검사 코드를 심게 하고, 버그가 난 순간 런타임이 리포트를 찍게 했다. 개념 쪽 배경(탐지기와 완화 장벽의 차이)은 [새니타이저(C38)](/posts/android-concept-atlas-c38-sanitizers/)에, JNI 경계 관찰은 [10장](/posts/android-lab-p1c10-jni-native-observation/)에 있다.

실험 환경은 Android 13(API 33) google_apis x86_64 userdebug 에뮬레이터와 NDK 27.3.13750724의 clang 18.0.4다. 대상은 직접 만든 C 파일 하나와 그 파일을 JNI로 감싼 `io.seika.sanjni` 앱이다.

시작 전에 확인할 것이 있다. NDK 공식 ASan 안내 페이지는 2023년 현재 ASan은 지원되지 않는다고 적고(계속 쓸 수는 있지만 버그가 있을 수 있다고 덧붙인다), ARM64 Android 14 이상 기기(또는 특수 이미지를 올린 Android 10 Pixel)에서는 HWASan을 쓰라고 권한다.

![developer.android.com NDK Address Sanitizer 가이드 한국어판 상단. '지원 중단됨: 2023년 현재 ASan은 지원되지 않습니다. 대신 HWASan을 사용하는 것이 좋습니다'와 Android 14(API 34) 이상 ARM64 기기, Android 10 Pixel 특수 시스템 이미지 안내가 보인다](/assets/img/android-mastery/p1c22/05-doc-ndk-asan-deprecated.png)

그래도 여기서 ASan을 쓴 이유는 랩 에뮬레이터가 x86_64라서다. HWASan은 AArch64의 상위 바이트 무시(TBI) 기능에 기대어 ARM64에서 쓰도록 만든 도구라 이 x86_64 환경에서는 제대로 돌지 않았다. ASan 리포트의 형식, 섀도 바이트의 뜻, tombstone 심볼화 절차는 HWASan과 거의 그대로 이어진다.

## 버그를 모아 둔 bugs.c와 빌드 변형

버그는 `src/bugs.c` 한 파일에 모았다. 명령줄 실행 파일 `sanlab`과 JNI 라이브러리 `libsanjni.so`가 같은 파일을 컴파일한다. 아래는 그 파일의 14~43행과 84~105행을 그대로 옮긴 발췌다(본문에서 말하는 `bugs.c:20`, `:42`, `:87`, `:101`이 이 줄들이다).

```c
// src/bugs.c 14~43행
// volatile index so the compiler cannot prove the overflow at build time
static volatile int g_idx;

__attribute__((noinline)) int parse_records(int n) {
    int *rec = malloc(10 * sizeof(int));          // 40 bytes
    g_idx = n;
    for (int i = 0; i <= g_idx; i++) rec[i] = i;  // i == 10 writes rec[10]
    int sum = rec[0];
    free(rec);
    return sum;
}

__attribute__((noinline)) int read_tail(void) {
    char *p = malloc(13);                         // 13 bytes: last granule partially addressable
    memset(p, 'A', 13);
    g_idx = 13;
    char c = p[g_idx];                            // 1 byte past the end
    free(p);
    return c;
}

__attribute__((noinline)) static void release_session(char *s) { free(s); }

__attribute__((noinline)) int use_after_free(void) {
    char *s = malloc(32);
    strcpy(s, "session-token");
    release_session(s);
    g_idx = 5;
    return s[g_idx];                              // read after free
}
```

```c
// src/bugs.c 84~105행
// media-style size computation: count * elem_size in 32 bits
__attribute__((noinline)) int alloc_entries(uint32_t count) {
    uint32_t elem_size = 16;
    uint32_t total = count * elem_size;           // wraps for count >= 0x10000000
    printf("alloc_entries: count=%u total=%u\n", count, total);
    fflush(stdout);
    uint8_t *buf = malloc(total);
    uint32_t todo = count < 4 ? count : 4;        // write the first few entries only
    for (uint32_t i = 0; i < todo; i++) memset(buf + i * elem_size, 0x41, elem_size);
    __asm__ volatile("" : : "r"(buf) : "memory");  // keep buf and its stores alive at -O1
    printf("alloc_entries: wrote %u entries into %u bytes\n", todo, total);
    fflush(stdout);
    free(buf);
    return 0;
}

__attribute__((noinline)) int add_signed(int a) {
    int r = a + 1;                                // signed overflow for INT32_MAX
    printf("add_signed: %d + 1 = %d\n", a, r);
    fflush(stdout);
    return r;
}
```

이 밖에 `use_after_poison()`(64바이트 풀의 뒤쪽 절반을 `ASAN_POISON_MEMORY_REGION`으로 막고 오프셋 40을 읽음)과 `far_overflow()`(16바이트 블록 두 개를 잡고 `a[b-a]`에 써서 리드존을 건너뛰고 곧장 `b`에 착지)가 있다. `run_bug(name)`이 이름으로 버그 함수를 고르고, `sanlab heap-oob`처럼 부른다. `alloc_entries()`는 미디어 코드에서 흔한 "개수 × 원소 크기" 크기 계산을 흉내 내 직접 쓴 함수다. 실제 미디어 프레임워크의 버그가 아니다.

`alloc_entries()`의 93행 빈 `asm` 줄에는 사연이 있다. 이 줄이 없던 첫 버전으로 돌렸을 때 ASan 빌드가 `int-overflow`에서 아무것도 보고하지 않았다. 디스어셈블해 보니 `-O1`에서 컴파일러가 결과를 아무도 읽지 않는 `malloc`·`memset`·`free`를 통째로 지워 버렸다. 퍼징 하네스에서도 결과를 쓰지 않는 버퍼는 같은 식으로 사라진다. 이 첫 버전에서는 넘치는 쓰기 자체가 바이너리에 없었다.

빌드는 Git Bash에서 NDK clang을 직접 불렀다. 공통 플래그는 다음과 같다(`-fdebug-compilation-dir`과 `-ffile-prefix-map`은 DWARF에 호스트 절대 경로가 남지 않게 하려고 넣었다).

```bash
mkdir -p out/x86_64 out/arm64-v8a out/sym/x86_64
CFLAGS="-O1 -g -fno-omit-frame-pointer -fdebug-compilation-dir=. -ffile-prefix-map=$(cygpath -m $NDK)=ndk"
X86="--target=x86_64-linux-android26"
S="src/sanlab.c src/bugs.c"
$NDK_BIN/clang.exe $X86 $CFLAGS $S -o out/x86_64/sanlab-plain
$NDK_BIN/clang.exe $X86 $CFLAGS -fsanitize=address $S -o out/x86_64/sanlab-asan
$NDK_BIN/clang.exe $X86 $CFLAGS -fsanitize=undefined $S -o out/x86_64/sanlab-ubsan
$NDK_BIN/clang.exe $X86 $CFLAGS -fsanitize=signed-integer-overflow,unsigned-integer-overflow $S -o out/x86_64/sanlab-intsan-diag
$NDK_BIN/clang.exe $X86 $CFLAGS -fsanitize=signed-integer-overflow,unsigned-integer-overflow \
    -fsanitize-minimal-runtime -fno-sanitize-recover=all $S -o out/x86_64/sanlab-intsan
$NDK_BIN/clang.exe $X86 $CFLAGS -fsanitize=signed-integer-overflow,unsigned-integer-overflow -fsanitize-minimal-runtime \
    -fno-sanitize-trap=integer,undefined -fno-sanitize-recover=integer,undefined -fsanitize-trap=all -ftrap-function=abort \
    $S -o out/x86_64/sanlab-intsan-soong
$NDK_BIN/clang.exe --target=aarch64-linux-android34 $CFLAGS -fsanitize=hwaddress $S -o out/arm64-v8a/sanlab-hwasan
$NDK_BIN/clang.exe --target=x86_64-linux-android33 $CFLAGS -fsanitize=hwaddress $S -o out/x86_64/sanlab-hwasan-x86
cp out/x86_64/sanlab-* out/sym/x86_64/
```

`intsan-soong`의 긴 플래그 열은 Android 13 플랫폼 빌드 시스템이 IntSan 모듈에 붙이는 순서를 그대로 흉내 낸 것이다.

## 메모리 접근마다 붙는 8분의 1 섀도 검사

ASan 빌드를 디스어셈블하면 `rec[i] = i` 한 줄에 검사 코드가 붙은 것이 바로 보인다.

![NDK clang 18.0.4 버전 줄, ASan과 plain 빌드 명령, wc -c 결과 15736(plain)과 76624(asan) 바이트, readelf NEEDED에 libclang_rt.asan-x86_64-android.so, parse_records 디스어셈블에서 shrq $0x3 / movzbl 0x7fff8000(%rdx) / testb 뒤에 movl %ecx,(%rax,%rcx,4) 저장이 오고 느린 경로가 callq __asan_report_store4로 끝나는 모습](/assets/img/android-mastery/p1c22/01-host-asan-build.png)

`shrq $0x3`로 주소를 8로 나누고 `0x7fff8000`을 더한 자리의 바이트 하나를 읽는다. 이 바이트가 섀도다. 애플리케이션 메모리 8바이트마다 섀도 1바이트가 대응하고, 값이 0이면 8바이트 전부 접근할 수 있다는 뜻이라 저장(`4fe2`)으로 바로 간다. 0이 아니면 느린 경로로 가서 `(주소 & 7) + 3`(4바이트 쓰기의 마지막 바이트 위치)을 섀도 값과 비교하고, 섀도 값 이상이면(마지막 바이트 오프셋이 유효 바이트 수 k 안에 들지 않으면) `__asan_report_store4`를 부른다. 섀도 값 1~7이 "앞에서부터 n바이트만 유효"라는 뜻이어서 이 비교가 성립한다.

검사는 바이너리에 박히지만 리포트 출력, 섀도 관리, `malloc` 교체는 별도 런타임 `libclang_rt.asan-x86_64-android.so`가 맡는다. readelf의 NEEDED 줄이 그 의존성이다. 이 런타임을 프로세스에 먼저 올려야 하는데, 명령줄 실행 파일은 `LD_LIBRARY_PATH`로 해결되고 앱은 뒤에 나올 `wrap.sh`가 필요하다. 크기는 plain 15736바이트, ASan 76624바이트였다. 작은 프로그램이라 대표성은 없다. NDK 문서가 말하는 비용은 CPU 약 2배, 코드 크기 50%~2배, 메모리 2배 안팎이며, 이 랩에서 직접 재지는 않았다.

## 40바이트 버퍼 뒤 4바이트, plain은 조용했고 ASan은 134로 죽었다

기기에 올리는 절차는 이렇다. 런타임 `.so`는 NDK의 `toolchains/llvm/prebuilt/windows-x86_64/lib/clang/18/lib/linux`에 있다.

```bash
S=emulator-5602
adb -s $S shell mkdir -p /data/local/tmp/p1c22
adb -s $S push out/x86_64/sanlab-* /data/local/tmp/p1c22/
cd $NDK/toolchains/llvm/prebuilt/windows-x86_64/lib/clang/18/lib/linux
for r in asan ubsan_standalone ubsan_minimal hwasan; do adb -s $S push libclang_rt.$r-x86_64-android.so /data/local/tmp/p1c22/; done
cd - > /dev/null
adb -s $S shell "chmod 755 /data/local/tmp/p1c22/sanlab-*; ls /data/local/tmp/p1c22"
adb -s $S shell "cd /data/local/tmp/p1c22 && export LD_LIBRARY_PATH=. && ./sanlab-plain heap-oob; echo exit=\$?"
adb -s $S shell "cd /data/local/tmp/p1c22 && export LD_LIBRARY_PATH=. && ./sanlab-asan heap-oob 2>&1" > raw/11-heap-oob.txt; echo exit=$?
```

`parse_records(10)`은 40바이트를 잡고 `rec[10]`까지 써서 끝에서 4바이트를 넘친다. plain 빌드는 `sanlab: returned 0`, `exit=0`으로 끝났다. Android 13의 기본 할당자 Scudo도 이 정도 넘침은 알아채지 못했다. ASan 빌드는 같은 입력에서 exit 134(SIGABRT)로 끝났다.

![기기에서 sanlab-plain heap-oob는 returned 0, exit=0. sanlab-asan은 exit=134, heap-buffer-overflow on address 0x5040000000f8, WRITE of size 4, 프레임 #0 sanlab-asan+0x5011, #1 +0x4eb9, #2 libc.so, 0 bytes after 40-byte region, allocated by thread T0의 asan 런타임과 +0x4fb1 프레임, 섀도 행 fa fa 00 00 00 00 00 00 fa fa 00 00 00 00 00 다음 괄호 친 fa, 섀도 범례 fa/fd/f7](/assets/img/android-mastery/p1c22/11-device-heap-oob.png)

위에서부터 읽는다. 첫 줄은 버그 종류와 주소다. 다음 줄 `WRITE of size 4 at 0x5040000000f8 thread T0`가 문제의 접근이다(읽기인지 쓰기인지, 몇 바이트인지). 그 아래 스택이 접근 시점의 호출 경로다. `0 bytes after 40-byte region [0x5040000000d0,0x5040000000f8)`는 접근 주소가 어떤 할당 블록 기준으로 어디에 있는지 알려 준다. 블록 끝 바로 다음 바이트다. `allocated by thread T0 here:` 아래는 그 블록을 할당한 스택이다.

기대와 달랐던 점은 기기 위의 스택에 함수 이름이 하나도 없다는 것이다. `(sanlab-asan+0x5011)`처럼 모듈과 오프셋만 찍힌다. 기기에 `llvm-symbolizer`가 없어서다. 그래서 호스트에서 심볼이 남은 바이너리에 오프셋을 넣어 풀었다(뒤의 UAF와 정수 오버플로 절에서 쓰는 0x50ee, 0x5493도 같이 넣었다).

```bash
$NDK_BIN/llvm-symbolizer.exe --obj=out/x86_64/sanlab-asan 0x5011 0x4fb1 0x4eb9 0x50ee 0x5493
```

![llvm-symbolizer.exe --obj=out/x86_64/sanlab-asan 0x5011 0x4fb1 0x4eb9 0x50ee 0x5493 출력. parse_records ./src/bugs.c:20:45, parse_records ./src/bugs.c:18:16, main ./src/sanlab.c:11:13, use_after_free ./src/bugs.c:40:5, alloc_entries ./src/bugs.c:92:41](/assets/img/android-mastery/p1c22/18-host-symbolize.png)

0x5011은 `parse_records ./src/bugs.c:20:45`, 할당 스택의 0x4fb1은 `parse_records ./src/bugs.c:18:16`(malloc 줄), 0x4eb9는 `main ./src/sanlab.c:11:13`이었다. `run_bug` 프레임은 어디에도 없다. `run_bug`이 버그 함수를 `jmp`로 꼬리 호출해서 자기 프레임을 남기지 않기 때문이다.

맨 아래 `=>` 행이 섀도 덤프다. `fa fa 00 00 00 00 00 00 fa fa 00 00 00 00 00[fa]`에서 대괄호가 접근 주소의 섀도다. `00` 다섯 개가 40바이트 블록이고, 바로 오른쪽 `fa`가 접근 위치다. 범례는 `fa`를 "Heap left redzone"이라고 부르는데 여기서는 블록 오른쪽에 있다. 이름이 헷갈리지만 런타임 소스를 보면 이유가 나온다.

![NDK 툴체인 포크 compiler-rt asan_allocator.cpp 611~631행. 618행과 619행이 블록 앞(alloc_beg)과 꼬리(tail_beg) 양쪽에 PoisonShadow(..., kAsanHeapLeftRedzoneMagic)를 쓰고, 631행이 끝이 8바이트에 맞지 않으면 마지막 섀도 바이트에 size & (ASAN_SHADOW_GRANULARITY - 1)을 넣는다](/assets/img/android-mastery/p1c22/03-src-asan-redzone-fa.png)

NDK clang이 빌드된 [llvm-project 포크의 asan_allocator.cpp 616~619행](https://android.googlesource.com/toolchain/llvm-project/+/d8003a456d14a3deb8054cdaa529ffbf02d9b262/compiler-rt/lib/asan/asan_allocator.cpp#616)은 블록 앞쪽과 꼬리를 똑같이 `kAsanHeapLeftRedzoneMagic`으로 칠한다. 오른쪽 리드존 전용 값은 따로 없다. 같은 포크의 [asan_internal.h 140~147행](https://android.googlesource.com/toolchain/llvm-project/+/d8003a456d14a3deb8054cdaa529ffbf02d9b262/compiler-rt/lib/asan/asan_internal.h#140)에 `0xfa`(힙 리드존), `0xfd`(해제된 힙), `0xf7`(사용자가 독으로 칠한 영역)이 정의돼 있다. 리포트를 읽을 때 손에 쥘 값은 이 셋과 1~7의 부분 유효 값이다.

## UAF 리포트는 접근, 해제, 할당 순으로 나온다

처음에는 UAF 리포트가 "해제한 스택"부터 보여 줄 거라고 생각했다. `grep -n`으로 줄 번호를 같이 찍어 보니 순서가 달랐다.

![sanlab-asan uaf 출력을 grep -n으로 거른 결과. 3행 heap-use-after-free on address 0x503000000015, 4행 READ of size 1, 5~7행 접근 스택(sanlab-asan+0x512c, +0x4eb9, libc), 9행 located 5 bytes inside of 32-byte region, 10행 freed by thread T0 here(asan 런타임 +0xdd61b, +0x50ee, +0x4eb9), 16행 previously allocated by thread T0 here(+0xdd72f, +0x50cf, +0x4eb9), 22행 SUMMARY, 29행 섀도 행 fa fa 다음 괄호 친 fd와 fd fd fd](/assets/img/android-mastery/p1c22/12-device-uaf.png)

3행 에러 종류, 4행 `READ of size 1`, 5~7행 접근 스택이 먼저 온다. 9행이 `5 bytes inside of 32-byte region`으로 블록 안의 위치를 말하고, 10행 `freed by thread T0 here:`, 16행 `previously allocated by thread T0 here:`가 뒤따른다. 해제 스택이 할당 스택보다 앞에 오는 것은 맞지만 맨 앞은 언제나 잘못된 접근 자체다. 섀도 행 `fa fa[fd]fd fd fd`에서 32바이트 블록 네 그래뉼이 모두 `fd`이고, 대괄호가 오프셋 5가 든 첫 그래뉼에 있다.

해제 스택에도 빠진 이름이 있다. 소스상으로는 `use_after_free → release_session → free`인데, 해제 스택 `#1`인 0x50ee를 심볼화하면 `use_after_free ./src/bugs.c:40:5`가 나온다. `release_session(s)`을 부르는 줄이다. `release_session`은 `noinline`이라 인라인되지는 않았다. 대신 하는 일이 `free(s)` 하나라서 `-O1`에서 `free`로 꼬리 점프한다. 디스어셈블하면 바로 보인다.

![llvm-objdump -d로 본 release_session 0x5130: pushq %rbp, movq %rsp,%rbp, popq %rbp, jmp 0x57c0 free@plt. use_after_free 안 0x50ea의 callq 0x5130 release_session과 다음 명령 0x50ef movl $0x5 (g_idx)](/assets/img/android-mastery/p1c22/18b-host-release-session-disasm.png)

`release_session`은 `push %rbp; mov %rsp,%rbp; pop %rbp; jmp free@plt` 네 명령이 전부다. 프레임을 세웠다가 `free`로 점프하기 전에 걷으므로 `free`가 보는 복귀 주소는 `use_after_free`가 0x50ea에서 `release_session`을 부를 때 쌓은 0x50ef다. 리포트의 0x50ee는 여기서 1을 뺀 값이다.

## f7, 05, 그리고 아무 보고도 없던 먼 쓰기

같은 ASan 바이너리로 섀도 값이 다른 경우를 더 돌렸다.

![use-after-poison on address 0x506000000048, READ of size 1, 섀도 행 fa fa fa fa 00 00 00 00 f7 다음 괄호 친 f7, f7 f7과 범례 Poisoned by user f7. heap-oob-partial은 heap-buffer-overflow, READ of size 1, 0 bytes after 13-byte region, 섀도 행 fa fa 00 fa fa fa 00 다음 괄호 친 05, fa. far-oob는 a=0x502000000030 b=0x502000000050 distance=32, b의 첫 바이트가 X, returned 0, exit=0](/assets/img/android-mastery/p1c22/13-device-poison-far.png)

`use_after_poison()`은 64바이트 블록의 32~63바이트를 `ASAN_POISON_MEMORY_REGION`으로 막고 오프셋 40을 읽는다. 섀도 행은 `fa fa fa fa 00 00 00 00 f7[f7]f7 f7`이다. 앞의 `00` 넷이 열린 32바이트, `f7` 넷이 막힌 32바이트이고, 대괄호는 오프셋 40이 든 여섯 번째 그래뉼에 있다. 자체 메모리 풀을 쓰는 네이티브 코드라면 풀에 돌려받은 조각을 이렇게 칠해 두어야 ASan이 풀 내부의 UAF를 본다. 칠하지 않으면 풀 안의 해제는 ASan 입장에서 그냥 살아 있는 메모리다.

`read_tail()`은 13바이트를 잡고 `p[13]`을 읽는다. 섀도는 `00[05]`다. 첫 그래뉼 8바이트는 전부 유효하고, 두 번째 그래뉼은 앞 5바이트만 유효하다는 뜻이다(13 = 8 + 5). 앞의 소스 캡처 631행 `size & (ASAN_SHADOW_GRANULARITY - 1)`이 이 `05`를 만든다. 접근한 바이트는 그래뉼 안 오프셋 5라서 걸렸다. 8바이트 정렬 경계에 걸리지 않는 1바이트 넘침도 잡힌다는 것을 보여 준다.

`far_overflow()`는 ASan을 피해 갔다. 16바이트 블록 `a`와 `b`의 거리가 32였고, `a[32]`에 쓴 `X`가 그대로 `b[0]`에 들어갔다. 리포트 없이 `exit=0`. ASan은 접근 주소의 섀도만 본다. 리드존을 뛰어넘어 살아 있는 다른 블록에 착지한 쓰기는 그 주소의 섀도가 `00`이니 정상 접근이다. 길이 필드를 믿고 오프셋을 더하는 파서처럼 인덱스가 입력에서 오는 버그라면, 그 오프셋이 리드존을 넘어 다른 블록에 닿는 순간 ASan 리포트는 나오지 않는다.

## 정수 오버플로는 누가 잡는가

`alloc_entries(0x10000001)`에서 `count * 16`은 32비트에서 16으로 감긴다. 16바이트를 할당하고 16바이트 원소 넷을 쓰니 48바이트가 넘친다. 같은 입력을 빌드 변형마다 돌렸다.

![같은 int-overflow 입력. sanlab-plain은 count=268435457 total=16, wrote 4 entries into 16 bytes, exit=0. sanlab-ubsan은 같은 출력에 보고 없음, signed-overflow에서 src/bugs.c:101:15 runtime error: signed integer overflow: 2147483647 + 1. sanlab-intsan-diag는 src/bugs.c:87:28 runtime error: unsigned integer overflow: 268435457 * 16 뒤에 total=16 줄이 이어짐. sanlab-intsan은 ubsan: mul-overflow by 0x00006010de26d0df, exit=134 Aborted. sanlab-intsan-soong은 메시지 없이 exit=134 Aborted](/assets/img/android-mastery/p1c22/14-device-intsan.png)

plain은 48바이트를 넘쳐 쓰고도 `exit=0`이었다. Scudo는 `free` 때도 아무 말이 없었다.

`-fsanitize=undefined`(UBSan 기본 묶음)는 이 감김을 보고하지 않았다. C에서 부호 없는 정수의 감김은 정의된 동작이라 [UBSan 문서](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)상 `unsigned-integer-overflow`는 `undefined` 묶음에 들어 있지 않다. 부호 있는 오버플로(`add_signed(INT32_MAX)`)는 `src/bugs.c:101:15: runtime error: signed integer overflow`로 보고했다. 그리고 멈추지 않았다. UBSan 검사는 기본이 "보고 후 계속"이다. 보고 뒤에도 실행이 이어지는 모습은 `intsan-diag` 줄에서 보인다. `unsigned-integer-overflow`를 명시한 `intsan-diag`는 `src/bugs.c:87:28`에서 `268435457 * 16`을 보고한 뒤 다음 줄 `alloc_entries: count=268435457 total=16`을 계속 찍었다.

멈추게 하려면 recover를 끄거나 트랩으로 바꿔야 했다. 최소 런타임에 `-fno-sanitize-recover=all`을 준 `intsan`은 `ubsan: mul-overflow by 0x00006010de26d0df` 한 줄을 남기고 exit 134로 죽었다. 곱셈 다음 줄은 실행되지 않았으니 넘치는 쓰기도 없었다. 트랩 모드를 덧붙인 `intsan-soong`은 메시지 하나 없이 exit 134였다. 두 실행의 tombstone도 달랐다. `intsan`은 `Abort message: 'ubsan: mul-overflow by 0x000060a745e330df'`와 `#01 libclang_rt.ubsan_minimal-x86_64-android.so (__ubsan_handle_mul_overflow_minimal_abort+104)`, `#02 sanlab-intsan (alloc_entries+174)`가 찍혔다. `intsan-soong`은 Abort message 줄이 아예 없고 `#00 abort+191` 바로 위가 `#01 sanlab-intsan-soong (alloc_entries+179)`였다.

![crash 버퍼를 저장한 raw/14-intsan-crash.txt에서 Cmdline, Abort message, #00~#03 줄만 거른 결과. sanlab-intsan은 Abort message: 'ubsan: mul-overflow by 0x000060a745e330df', #00 abort+191, #01 libclang_rt.ubsan_minimal (__ubsan_handle_mul_overflow_minimal_abort+104), #02 sanlab-intsan (alloc_entries+174), #03 run_bug+334. sanlab-intsan-soong은 Abort message 줄 없이 #00 abort+191, #01 alloc_entries+179, #02 run_bug+334, #03 main+58](/assets/img/android-mastery/p1c22/17-host-intsan-tombstone.png)

왜 `intsan-soong` 같은 변형을 만들었는지는 플랫폼 빌드 시스템 소스에 있다.

![Android 13 soong cc/sanitize.go 725~737행. enableMinimalRuntime이면 CFlags에 minimalRuntimeFlags를 붙이고, Fuzzer면 -fno-sanitize-trap=all, 호스트면 -fno-sanitize-recover=all, 그 밖(기기 빌드)이면 -fsanitize-trap=all과 -ftrap-function=abort를 붙인다](/assets/img/android-mastery/p1c22/04-src-soong-intsan-trap.png)

[Android 13 soong `cc/sanitize.go` 725~737행](https://android.googlesource.com/platform/build/soong/+/refs/tags/android-13.0.0_r83/cc/sanitize.go#725)은 최소 런타임을 쓰는 모듈에 먼저 [76~77행의 `minimalRuntimeFlags`](https://android.googlesource.com/platform/build/soong/+/refs/tags/android-13.0.0_r83/cc/sanitize.go#76)(`-fsanitize-minimal-runtime -fno-sanitize-trap=integer,undefined -fno-sanitize-recover=integer,undefined`)를 붙이고, 기기 빌드면 그 뒤에 `-fsanitize-trap=all -ftrap-function=abort`를 붙인다. 이 순서를 NDK clang 18에 그대로 주면 뒤의 트랩 플래그가 이겨서 `abort()` 직접 호출이 나왔고, 기기에서 본 결과가 메시지 없는 abort였다. [IntSan 문서](https://source.android.com/docs/security/test/intsan)는 프로덕션 abort 예로 `ubsan: sub-overflow` 메시지를 든다. 실제 플랫폼 모듈 빌드에서 메시지가 남는지는 확인하지 못했다. 직접 확인한 것은 같은 플래그 순서를 쓴 우리 바이너리뿐이다. 메시지가 없더라도 tombstone 백트레이스의 `alloc_entries+179`가 위치를 알려 준다.

ASan은 이 버그를 어떻게 보는지도 돌렸다.

![sanlab-asan int-overflow는 count=268435457 total=16 뒤에 heap-buffer-overflow on address 0x502000000040, WRITE of size 64, #0 libclang_rt.asan 런타임 +0xdc164, #1 sanlab-asan+0x5493, 0 bytes after 16-byte region, SUMMARY가 asan 런타임 오프셋을 가리킴. 이어 int-ok는 count=3 total=48, wrote 3 entries into 48 bytes, returned 0](/assets/img/android-mastery/p1c22/14b-device-int-asan.png)

ASan이 본 것은 곱셈이 아니라 그 결과로 생긴 넘침이다. `WRITE of size 64`, `0 bytes after 16-byte region`. 컴파일러가 memset 네 번을 64바이트 한 번으로 합친 것으로 보이고, `#0`은 ASan 런타임의 memset 가로채기라 SUMMARY도 런타임 오프셋을 가리킨다. 호스트에서 `#1` 0x5493을 풀면 `alloc_entries ./src/bugs.c:92:41`이 나온다. 87행의 곱셈까지 거슬러 올라가는 일은 리포트를 읽는 사람 몫이다. 곱셈이 감겨도 그 버퍼를 넘치게 쓰는 코드가 없으면 ASan 리포트는 나오지 않는다. 정상 입력 `int-ok`(`count=3 total=48`)는 같은 ASan 빌드에서 보고 없이 `returned 0`으로 끝났다.

## ndk-stack으로 tombstone을 소스 줄까지 풀기

ASan이 abort하면 debuggerd가 tombstone을 남기고 crash 버퍼에 요약을 쓴다. 이걸 호스트의 `ndk-stack`에 먹였다.

```bash
adb -s $S logcat -c
adb -s $S shell "cd /data/local/tmp/p1c22 && export LD_LIBRARY_PATH=. && ./sanlab-asan uaf > /dev/null 2>&1; echo exit=\$?"
adb -s $S logcat -d -b crash > raw/15-crash.txt
$NDK/ndk-stack.cmd -sym out/sym/x86_64 -i raw/15-crash.txt > raw/15-ndkstack.txt
```

![exit=134 뒤 crash 버퍼에 Fatal signal 6 (SIGABRT) in tid 4265 (sanlab-asan)와 DEBUG Abort message: '=====' 줄. ndk-stack.cmd -sym out/sym/x86_64 출력에 Crash dump, Build fingerprint, Abort message 안의 프레임 #0 0x512c use_after_free ./src/bugs.c:42:12, #1 0x4eb9 main ./src/sanlab.c:11:13, 해제 스택 #1 0x50ee use_after_free ./src/bugs.c:40:5, debuggerd 프레임 #06 sanlab-asan (use_after_free+108) ./src/bugs.c:42:12](/assets/img/android-mastery/p1c22/15-device-crash-ndkstack.png)

stderr를 `/dev/null`로 버렸는데도 리포트 전체가 crash 버퍼의 `Abort message:` 안에 들어 있었다. ASan 런타임이 Android에서 abort 메시지로 리포트를 넘겨서다. `ndk-stack`은 그 안의 새니타이저 프레임까지 `use_after_free ./src/bugs.c:42:12`, 해제 스택 `./src/bugs.c:40:5`로 풀었다. `-sym`에 준 바이너리가 기기에 올린 것과 같은 파일이라 BuildId가 맞았다. 아래쪽 `#06 ... (use_after_free+108)`은 debuggerd 자신의 백트레이스로, `.symtab`을 읽어 기기에서도 함수 이름은 붙는다.

잘 안 되는 경우도 있다. NDK 27의 `ndkstack.py`는 tombstone 배너 뒤의 줄만 파싱하므로, 터미널에 찍힌 ASan stderr를 그대로 붙여 넣으면 풀지 못한다. `-sym`에는 스트립하지 않은 사본을 둔 디렉터리를 준다. ndk-build 프로젝트라면 `obj/local` 아래 ABI 디렉터리가 그 자리인데, 이 랩은 clang을 직접 불렀으니 빌드 직후 복사해 둔 `out/sym/x86_64`다.

## wrap.sh로 앱 안의 JNI 라이브러리에 ASan 걸기

명령줄 바이너리는 `LD_LIBRARY_PATH`로 런타임을 찾게 하면 그만이다. 앱 프로세스는 zygote에서 fork되므로 ASan 런타임을 가장 먼저 올릴 틈이 없다. 그래서 debuggable 앱에 한해 프로세스 시작 명령 앞에 끼울 셸 스크립트를 허용한다.

![Android 13 ProcessList.java 1828~1839행. if (debuggableFlag) 안에서 wrapperFileName = app.info.nativeLibraryDir + "/wrap.sh"이고, 그 파일이 존재하면 invokeWith = "/system/bin/logwrapper " + wrapperFileName](/assets/img/android-mastery/p1c22/06-src-a13-wrapsh-logwrapper.png)

[ProcessList.java 1828~1839행(android-13.0.0_r83)](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r83/services/core/java/com/android/server/am/ProcessList.java#1828)을 보면 조건은 debuggable 플래그와 `nativeLibraryDir/wrap.sh` 파일 존재다. 그래서 매니페스트에 `android:debuggable="true"`와 `android:extractNativeLibs="true"`(라이브러리가 디스크에 풀려 있어야 파일이 존재한다)를 넣었다. 명령 앞에는 `/system/bin/logwrapper`가 붙어서, 앱 프로세스의 stdout/stderr가 logwrapper를 거쳐 logcat으로 간다.

APK에는 ASan과 정수 오버플로 검사(`signed-integer-overflow`, `unsigned-integer-overflow`)를 함께 켜고 빌드한 `libsanjni.so`, ASan 런타임, 그리고 NDK가 제공하는 `wrap.sh/asan.sh`를 `lib/x86_64/wrap.sh`로 넣었다. 앞의 빌드 블록과 같은 셸에서 이어 돌렸다. `mkapk`는 javac, d8, aapt로 네이티브 라이브러리 없는 기본 APK를 만드는 작은 스크립트이고, 라이브러리와 wrap.sh는 그 뒤에 `aapt add`로 넣었다.

```bash
RT=$NDK/toolchains/llvm/prebuilt/windows-x86_64/lib/clang/18/lib/linux
BT=$ANDROID_HOME/build-tools/36.0.0
B=out/apk-asan
mkdir -p $B/lib/x86_64
$NDK_BIN/clang.exe $X86 $CFLAGS -fPIC -shared -fsanitize=address -fsanitize=signed-integer-overflow,unsigned-integer-overflow \
    app/sanjni/native/sanjni.c src/bugs.c -llog -o $B/lib/x86_64/libsanjni.so
cp $B/lib/x86_64/libsanjni.so out/sym/x86_64/libsanjni.so
mkapk app/sanjni $B/unaligned.apk
cp $RT/libclang_rt.asan-x86_64-android.so $B/lib/x86_64/
cp $NDK/wrap.sh/asan.sh $B/lib/x86_64/wrap.sh
(cd $B && $BT/aapt add unaligned.apk lib/x86_64/libsanjni.so lib/x86_64/libclang_rt.asan-x86_64-android.so lib/x86_64/wrap.sh)
zipalign -f -p 4 $B/unaligned.apk $B/aligned.apk
apksigner sign --ks ~/.android/debug.keystore --ks-key-alias androiddebugkey --ks-pass pass:android \
    --key-pass pass:android --out out/sanjni-asan.apk $B/aligned.apk
```

비교용 `out/sanjni-plain.apk`는 `out/apk-plain`에서 같은 순서로 만들되, clang 줄에서 `-fsanitize` 플래그 둘을 빼고 런타임과 wrap.sh 복사를 건너뛰어 `aapt add`에 `lib/x86_64/libsanjni.so`만 넘겼다. `out/sym/x86_64`에는 ASan 빌드의 사본만 둔다. 뒤에서 JNI 크래시를 `ndk-stack`에 넣을 때 쓰는 것이 이 파일이다.

wrap.sh로 들어간 `asan.sh`의 끝부분은 다음과 같다(NDK 원문 발췌).

```sh
export ASAN_OPTIONS=log_to_syslog=false,allow_user_segv_handler=1
ASAN_LIB=$(ls "$HERE"/libclang_rt.asan-*-android.so)
if [ -f "$HERE/libc++_shared.so" ]; then
    # Workaround for https://github.com/android-ndk/ndk/issues/988.
    export LD_PRELOAD="$ASAN_LIB $HERE/libc++_shared.so"
else
    export LD_PRELOAD="$ASAN_LIB"
fi

exec $cmd
```

`MainActivity`는 인텐트 extra `bug`를 읽어 `LD_PRELOAD`·`ASAN_OPTIONS` 환경 변수와 함께 `SANJNI` 태그로 로그를 남기고, 1.5초 뒤 `runBug(bug)`를 부른다.

```bash
unzip -l out/sanjni-asan.apk | grep lib/
adb -s $S install -r $(cygpath -m out/sanjni-asan.apk)
adb -s $S logcat -c
adb -s $S shell am start -W -n io.seika.sanjni/.MainActivity --es bug heap-oob
sleep 6
adb -s $S logcat -d > raw/20-jni-logcat.txt
grep -E ' (SANJNI|wrap.sh) ' raw/20-jni-logcat.txt
```

![unzip -l에 lib/x86_64/libsanjni.so 94152, libclang_rt.asan-x86_64-android.so 2324352, wrap.sh 1070. install Success, am start Status: ok. logcat에 SANJNI onCreate bug=heap-oob LD_PRELOAD=/data/app/~~.../lib/x86_64/libclang_rt.asan-x86_64-android.so ASAN_OPTIONS=log_to_syslog=false..., calling runBug(heap-oob), native runBug(heap-oob), 이어 pid 6622 태그 wrap.sh로 ==6623==ERROR: AddressSanitizer: heap-buffer-overflow, WRITE of size 4 thread T0 (io.seika.sanjni), #0 libsanjni.so+0x53ca, #1 libsanjni.so+0x5242, #2와 #3 libart.so, 0 bytes after 40-byte region이 색깔 있는 글자로 찍힘](/assets/img/android-mastery/p1c22/20-device-jni-asan.png)

`LD_PRELOAD`가 앱 lib 디렉터리의 ASan 런타임을 가리키는 것으로 wrap.sh가 실행됐음을 알 수 있다. 리포트를 찍은 쪽은 앱(pid 6623)이 아닌 pid 6622였고, 태그는 `wrap.sh`였다. 6622가 logwrapper다. 줄마다 ANSI 색 코드가 섞여 있어 터미널에서는 빨강·파랑·초록으로 보였다. 스택은 `#0 libsanjni.so+0x53ca`, `#1 libsanjni.so+0x5242` 다음이 곧장 libart다. 여기서도 `run_bug`은 꼬리 호출로 빠졌다. logcat에 `runBug returned`는 없고, 대신 `F libc : Fatal signal 6 (SIGABRT) ... (io.seika.sanjni)`가 남았다.

프로세스 관계는 `ps`로 따로 확인했다(인텐트 없이 다시 띄운 실행).

![sanjni-asan.apk 설치 후 extra 없이 am start, ps -A -o PID,PPID,NAME 결과 5968 5949 logwrapper와 5969 5968 io.seika.sanjni, SANJNI onCreate bug=null LD_PRELOAD=.../lib/x86_64/libclang_rt.asan-x86_64-android.so 로그](/assets/img/android-mastery/p1c22/23-device-jni-screen.png)

`io.seika.sanjni`(5969)의 부모가 `logwrapper`(5968)다. 같은 pid 5969가 남긴 SANJNI onCreate 로그의 `LD_PRELOAD`도 앱 lib 디렉터리의 ASan 런타임을 가리킨다. 앱 화면에도 같은 경로가 찍혔다.

![에뮬레이터 화면 상단을 자른 캡처. 앱 바 SanJNI, 본문 SanJNI, bug=null, LD_PRELOAD=/data/app/~~HcCv1Ky1WfKg7fI7qQYsOA==/io.seika.sanjni-s5BcGcPebGGR3n8FC8BNZA==/lib/x86_64/libclang_rt.asan-x86_64-android.so](/assets/img/android-mastery/p1c22/23-device-jni-screen-emu.png)

같은 크래시를 crash 버퍼에서 꺼내 `ndk-stack`에 넣으면 JNI 경계가 소스 줄로 보인다.

![crash 버퍼 DEBUG Cmdline: io.seika.sanjni와 Abort message 줄. ndk-stack.cmd -sym out/sym/x86_64 결과 #0 0x53ca libsanjni.so parse_records ./src/bugs.c:20:45, #1 0x5242 Java_io_seika_sanjni_MainActivity_runBug ./app/sanjni/native/sanjni.c:9:13, 할당 스택 #1 0x5315 parse_records ./src/bugs.c:18:16](/assets/img/android-mastery/p1c22/21-device-jni-ndkstack.png)

접근은 `parse_records ./src/bugs.c:20:45`, 그걸 부른 곳은 `Java_io_seika_sanjni_MainActivity_runBug ./app/sanjni/native/sanjni.c:9:13`(`run_bug(name)` 줄), 할당은 `bugs.c:18:16`이다. debuggerd 백트레이스 쪽은 `#05 __asan_report_store4`, `#06 libsanjni.so (parse_records+202)`, `#07 (Java_io_seika_sanjni_MainActivity_runBug+114)`, `#08 libart.so (art_quick_generic_jni_trampoline+219)`로 이어져 Java 쪽 `Handler.dispatchMessage`와 `ActivityThread.main`까지 올라간다.

비교용으로 새니타이저도 wrap.sh도 없는 APK를 같은 인텐트로 띄웠다.

![sanjni-plain.apk 설치 후 같은 인텐트. logcat에 onCreate bug=heap-oob LD_PRELOAD=null ASAN_OPTIONS=null, calling runBug, native runBug, runBug returned 0, AddressSanitizer나 DEBUG 줄 없음, pidof io.seika.sanjni가 5811을 출력](/assets/img/android-mastery/p1c22/22-device-jni-plain.png)

`runBug returned 0`, 크래시 없음, `pidof`가 5811을 돌려줘 프로세스도 살아 있었다. 40바이트 버퍼 뒤 4바이트를 덮어쓴 앱이 아무 일 없다는 듯 계속 돈다.

## HWASan은 이 랩에서 정적으로만 봤다

arm64 HWASan 빌드는 만들 수 있다. 기기에서 돌리지 못했을 뿐이다.

![aarch64-linux-android34 HWASan 빌드. readelf에 Machine AArch64, NEEDED libclang_rt.hwasan-aarch64-android.so. parse_records 디스어셈블에 movk x1, #0x9300, lsl #48, bl __hwasan_check_x1_18_short_v2 뒤 str w19, __hwasan_check_x1_2_short_v2 뒤 ldr, __hwasan_check_x2_18_short_v2 뒤 str w8. x86_64 HWASan 빌드는 NEEDED libclang_rt.hwasan-x86_64-android.so](/assets/img/android-mastery/p1c22/02-host-hwasan-build.png)

`movk x1, #0x9300, lsl #48`은 전역 변수 `g_idx` 주소의 상위 비트에 태그를 박는다. 포인터 최상위 바이트가 태그이고, 메모리 16바이트마다 하나씩 붙은 태그와 비교한다. 접근마다 섀도를 인라인으로 읽던 ASan과 달리 `__hwasan_check_x1_18_short_v2` 같은 작은 함수를 호출해 검사한다. 이름 끝의 18과 2는 쓰기 4바이트와 읽기 4바이트를 나타내는 접근 정보로 보인다(str 앞에 18, ldr 앞에 2가 붙어 있다). [HWASan 설계 문서](https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html)에 따르면 섀도는 16분의 1이고, 태그가 8비트라 한 번 실행에서 버그를 놓칠 확률은 약 0.39%다. ASan처럼 결정적이지 않고 확률적이다. 대신 리드존이 없어 앞에서 ASan이 놓친 `far_overflow` 같은 먼 쓰기도 태그가 다르면 잡힐 수 있다. 이 부분은 문서상의 설명이고 직접 돌려 보지는 못했다.

NDK 27은 x86_64용 HWASan 런타임도 넣어 두었기에 에뮬레이터에서 돌려 봤다.

![sanlab-hwasan-x86 heap-oob 실행 결과 exit=139, Segmentation fault, hw.txt는 빈 출력. /proc/cpuinfo에서 lam이나 la57 플래그를 grep해도 아무것도 없고 uname -r은 5.15.119-android13-8-00034-gd34029c8258b-ab10871489](/assets/img/android-mastery/p1c22/16-device-hwasan-x86.png)

exit 139(SIGSEGV), 출력은 한 글자도 없었다. CPU 플래그에 LAM도 없다. tombstone을 보면 `main` 근처에도 가지 못했다.

![crash 버퍼를 저장한 raw/16-hwasan-tombstone.txt에서 거른 줄. Fatal signal 11 (SIGSEGV), code 128 (SI_KERNEL), fault addr 0x0, Cmdline: ./sanlab-hwasan-x86 heap-oob, #00 libc.so scudo::HybridMutex::tryLock()+7, #01 scudo::Allocator allocate, #02 scudo_malloc+25, #03 malloc+23, #04 __register_atfork+30, #05 libclang_rt.hwasan-x86_64-android.so (__hwasan_init+1954)](/assets/img/android-mastery/p1c22/19-host-hwasan-tombstone.png)

`#05 libclang_rt.hwasan-x86_64-android.so (__hwasan_init+1954)`가 `#04 libc.so (__register_atfork+30)`를 불렀고, 거기서 bionic의 Scudo `malloc`이 `#00 scudo::HybridMutex::tryLock()+7`에서 `SIGSEGV, code 128 (SI_KERNEL)`로 죽었다. 이 바이너리가 링크한 런타임은 앨리어싱을 쓰지 않는 x86_64용으로, 포인터 상위 비트에 태그를 넣는다. 그래서 상위 비트를 무시하는 CPU 기능(인텔 LAM)을 전제하는데, 앞의 grep처럼 이 CPU에는 `lam` 플래그가 없다. 태그가 붙은 비정규 주소를 커널이 거부한 것으로 보이지만 확인하지는 않았다. NDK 27에는 [설계 문서](https://clang.llvm.org/docs/HardwareAssistedAddressSanitizerDesign.html)가 x86_64의 제한된 구현으로 소개하는 페이지 앨리어싱 런타임 `libclang_rt.hwasan_aliases-x86_64-android.so`도 들어 있다. 이쪽은 `-mllvm -hwasan-experimental-use-page-aliases`로 계측을 따로 해야 하고, 이번에는 시도하지 않았다.

실기기에서는 사정이 바뀌었다. [NDK HWASan 가이드](https://developer.android.com/ndk/guides/hwasan)에 따르면 Android 14부터는 arm64 기기라면 debuggable 앱의 wrap.sh에 `LD_HWASAN=1`을 주는 것만으로 HWASan을 쓸 수 있다. 그 전 버전은 HWASan으로 빌드한 시스템 이미지가 필요하다. [AOSP HWASan 문서](https://source.android.com/docs/security/test/hwasan)는 플랫폼 쪽 지원을 Android 10 이상 AArch64로, 사용자 공간 지원을 Android 11부터로 적는다. 이 랩에는 arm64 이미지도 기기도 없어 HWASan 런타임 리포트는 측정하지 못했다.

## 사용자 기기에 실제로 남는 것과 수정 확인

ASan과 HWASan은 출시 빌드에 들어가지 않는다. 런타임을 프리로드해야 하고 비용이 크다. 사용자 기기에서 상시 켜져 있는 것은 따로 있다. 기본 할당자 [Scudo](https://source.android.com/docs/security/test/scudo)의 헤더 검사, 할당 일부를 샘플링해 감시하는 [GWP-ASan](https://developer.android.com/ndk/guides/gwp-asan), 그리고 미디어 같은 선택된 플랫폼 구성 요소에 들어간 [IntSan](https://source.android.com/docs/security/test/intsan), [BoundSan](https://source.android.com/docs/security/test/bounds-sanitizer), [CFI](https://source.android.com/docs/security/test/cfi)다. [MTE](https://source.android.com/docs/security/test/memory-safety/arm-mte)는 MTE 하드웨어가 있는 기기에서만, 그것도 앱이나 개발자 옵션이 켜야 동작한다. 이번 plain 실행 두 번에서 Scudo는 모두 조용했다. 이 랩에서는 MTE도 측정하지 못했다(x86_64 에뮬레이터에 해당 하드웨어가 없다).

그래서 새니타이저는 개발과 테스트 단계에서 버그를 찾는 데 쓴다. 네이티브 라이브러리를 포함한 앱은 ASan(arm64 Android 14 이상 기기가 있으면 HWASan) 빌드로 계측 테스트와 퍼징을 돌린다. 크기 계산은 `unsigned-integer-overflow`를 명시해 따로 검사한다. `-fsanitize=undefined`만으로는 이번 `count * 16` 같은 감김이 빠진다. 고칠 때는 곱셈 전에 상한을 확인하거나 `__builtin_mul_overflow`로 감김을 검사해 실패를 돌려준다. 증상인 memset 쪽만 막으면 다른 소비 지점이 또 넘친다. 자체 메모리 풀이 있다면 돌려받은 조각을 `ASAN_POISON_MEMORY_REGION`으로 칠해 둔다.

`far_overflow`처럼 리드존을 건너뛰는 쓰기는 고치기 전에도 ASan이 조용했으니, 그런 경로는 경계 검사가 코드에 들어갔는지를 소스로 확인해야 한다. 나머지는 크래시를 낸 입력을 회귀 코퍼스에 넣고 같은 ASan·IntSan 빌드로 다시 돌려 리포트가 사라지는지, 정상 입력(`int-ok`처럼)이 여전히 보고 없이 끝나는지를 본다. 이번에는 버그를 고친 버전을 만들지 않았고, 확인한 것은 정상 입력이 ASan 빌드에서 깨끗하게 끝난다는 데까지다.
