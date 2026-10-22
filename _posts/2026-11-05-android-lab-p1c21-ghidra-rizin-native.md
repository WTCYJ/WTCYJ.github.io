---
layout: post
title: "Ghidra·Rizin native 분석 — 스트립된 JNI 표를 파일에서 읽기"
date: 2026-11-05 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Ghidra, Rizin, JNI, RegisterNatives, ESIL, NativeRE]
excerpt: "심볼을 지운 libnativere.so에서 JNI_OnLoad의 RegisterNatives 호출을 따라가 상수 등록 표를 Rizin과 Ghidra 헤드리스 스크립트로 읽었다. 같은 소스라도 ABI마다 함수 오프셋이 달랐고, 스택에서 조립한 Vault 표의 이름과 check_guess의 비교 문자열은 Rizin ESIL 에뮬레이션으로 꺼냈다."
---

[10장](/posts/android-lab-p1c10-jni-native-observation/)에서는 앱을 띄워 놓고 libart의 RegisterNatives 순간을 Frida로 잡아 스트립된 함수의 주소를 알아냈다. 그 방법은 프로세스가 돌아야 하고, 등록이 끝난 뒤 attach하면 아무것도 못 본다. 그런데 RegisterNatives에 넘기는 표는 대부분 라이브러리 파일 안에 상수로 박혀 있다. 그렇다면 기기 없이 `.so`만 열어서도 같은 매핑을 읽을 수 있어야 한다. 이번에는 그걸 Rizin과 Ghidra로 해 봤고, 정적 분석이 막히는 경우(스택에서 조립하는 표)도 일부러 하나 넣어 두었다.

도구는 Rizin 0.9.1(rz-ghidra 플러그인 없음), Ghidra 12.1.4(헤드리스, JDK 21.0.10), NDK r27d의 clang 18.0.4다. 대상은 직접 만든 `io.seika.nativere` 앱이고, APK 안에 `arm64-v8a`, `armeabi-v7a`, `x86_64` 세 ABI의 `libnativere.so`가 들어 있다. 선수 개념은 10장과 [ELF·linker(C33)](/posts/android-concept-atlas-c33-elf-linker-plt-got/)이다.

## 등록 방식을 섞어 둔 실험 라이브러리

Java 쪽에서 네이티브 메서드를 선언한 클래스는 `Native`와 `Vault`다. `Native`의 메서드 셋은 `JNI_OnLoad`가 상수 표로 등록하고, `nativeHello`만 전통적인 `Java_` 이름으로 export한다. `Vault.nativeOpen`은 표를 런타임에 스택에서 조립해서 등록한다.

```java
// src/io/seika/nativere/Native.java
package io.seika.nativere;

public class Native {
    static { System.loadLibrary("nativere"); }

    public native boolean nativeCheck(String guess);   // RegisterNatives, static table
    public static native int nativeScore(int a, int b); // RegisterNatives, static table
    public static native String nativeBuild();          // RegisterNatives, static table
    public static native String nativeHello();          // exported Java_ symbol
}
```

```java
// src/io/seika/nativere/Vault.java
package io.seika.nativere;

public class Vault {
    public static native boolean nativeOpen(int pin);   // RegisterNatives, table built at run time
}
```

C 쪽 전체다. 비밀 문자열은 XOR 0x37로, `Vault`의 이름·시그니처·클래스 문자열은 XOR 0x41로 가려 두어서 `strings`로는 안 나온다.

```c
// libnativere.so — release-style: -fvisibility=hidden, stripped with llvm-strip.
// Native's three methods come from a constant JNINativeMethod table (.data.rel.ro).
// Vault's table is built on the stack from strings decoded at run time.
// nativeHello is a classic exported Java_ symbol.
#include <jni.h>
#include <string.h>

static const unsigned char kSecret[] = {      // "SEIKA-RE-1105" ^ 0x37
    0x64, 0x72, 0x7e, 0x7c, 0x76, 0x1a, 0x65, 0x72, 0x1a, 0x06, 0x06, 0x07, 0x02,
};
static volatile unsigned char kKey = 0x37;

static jboolean check_guess(JNIEnv *env, jobject thiz, jstring guess) {
    char secret[sizeof(kSecret) + 1];
    for (size_t i = 0; i < sizeof(kSecret); i++) secret[i] = (char)(kSecret[i] ^ kKey);
    secret[sizeof(kSecret)] = 0;
    const char *s = (*env)->GetStringUTFChars(env, guess, NULL);
    if (!s) return JNI_FALSE;
    int ok = strcmp(s, secret) == 0;
    (*env)->ReleaseStringUTFChars(env, guess, s);
    memset(secret, 0, sizeof(secret));
    return ok ? JNI_TRUE : JNI_FALSE;
}

static jint score(JNIEnv *env, jclass c, jint a, jint b) { return a * 1000 + b * 7 + 0x21; }

static jstring build_tag(JNIEnv *env, jclass c) { return (*env)->NewStringUTF(env, "nativere-1105"); }

static const JNINativeMethod kNativeMethods[] = {
    {"nativeCheck", "(Ljava/lang/String;)Z", (void *)check_guess},
    {"nativeScore", "(II)I", (void *)score},
    {"nativeBuild", "()Ljava/lang/String;", (void *)build_tag},
};

__attribute__((visibility("default")))
JNIEXPORT jstring JNICALL Java_io_seika_nativere_Native_nativeHello(JNIEnv *env, jclass c) {
    return (*env)->NewStringUTF(env, "hello from an exported symbol");
}

static jboolean vault_open(JNIEnv *env, jclass c, jint pin) { return (pin ^ 0x5a5a) == 0x4f3d; }

// "nativeOpen" / "(I)Z" / "io/seika/nativere/Vault", each byte ^ 0x41, decoded into .bss
static const unsigned char kVName[] = {0x2f,0x20,0x35,0x28,0x37,0x24,0x0e,0x31,0x24,0x2f};
static const unsigned char kVSig[]  = {0x69,0x08,0x68,0x1b};
static const unsigned char kVCls[]  = {0x28,0x2e,0x6e,0x32,0x24,0x28,0x2a,0x20,0x6e,0x2f,0x20,0x35,
                                       0x28,0x37,0x24,0x33,0x24,0x6e,0x17,0x20,0x34,0x2d,0x35};
static char gName[16], gSig[8], gCls[32];
static volatile unsigned char kMask = 0x41;

static void decode(char *dst, const unsigned char *src, size_t n) {
    for (size_t i = 0; i < n; i++) dst[i] = (char)(src[i] ^ kMask);
    dst[n] = 0;
}

__attribute__((noinline)) static jint register_vault(JNIEnv *env) {
    decode(gName, kVName, sizeof(kVName));
    decode(gSig, kVSig, sizeof(kVSig));
    decode(gCls, kVCls, sizeof(kVCls));
    JNINativeMethod m[1];
    m[0].name = gName;
    m[0].signature = gSig;
    m[0].fnPtr = (void *)vault_open;
    jclass c = (*env)->FindClass(env, gCls);
    if (!c) return -1;
    return (*env)->RegisterNatives(env, c, m, 1);
}

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env;
    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6) != JNI_OK) return JNI_ERR;
    jclass c = (*env)->FindClass(env, "io/seika/nativere/Native");
    if (!c) return JNI_ERR;
    if ((*env)->RegisterNatives(env, c, kNativeMethods, 3) != JNI_OK) return JNI_ERR;
    if (register_vault(env) != JNI_OK) return JNI_ERR;
    return JNI_VERSION_1_6;
}
```

릴리스 빌드처럼 `-fvisibility=hidden`으로 컴파일하고 `llvm-strip --strip-unneeded`로 심볼을 지웠다. 지우기 전 사본은 따로 두고 나중에 정답지로 썼다. 두 파일은 코드가 같고 심볼 표만 다르다. ABI마다 타깃만 바꿔 같은 명령을 돌린다.

```bash
"$NDK_BIN/clang.exe" --target=aarch64-linux-android26 -fPIC -shared -O2 -fvisibility=hidden \
    app/native-src/nativere.c -o out/unstripped/arm64-v8a/libnativere.so
"$NDK_BIN/llvm-strip.exe" --strip-unneeded \
    -o out/lib/arm64-v8a/libnativere.so out/unstripped/arm64-v8a/libnativere.so
```

`armeabi-v7a`는 `--target=armv7a-linux-androideabi26`, `x86_64`는 `--target=x86_64-linux-android26`이다. 세 라이브러리를 APK의 `lib/<abi>/`에 넣고 서명했다.

## 스트립된 .so에서 Rizin이 먼저 보여 주는 것

APK에서 라이브러리를 꺼내는 데서 시작한다. Git Bash의 `unzip`은 `'lib/*'`만 주면 "filename not matched"를 내서 `'lib/*/*.so'`로 줬다.

![unzip -q nativere.apk로 lib 아래 arm64-v8a, armeabi-v7a, x86_64 세 libnativere.so를 꺼내고, rizin iI가 arch arm, bits 64, machine ARM aarch64, stripped true를, iE가 Java_io_seika_nativere_Native_nativeHello(0x1900, 20바이트)와 JNI_OnLoad(0x1914, 148바이트) 두 줄만 보여 주며, aaa 후 afl에는 fcn.000019a8, fcn.00001b30, sym.imp.strcmp 등은 있지만 0x1c68, 0x1c80, 0x1c94 함수는 없는 화면](/assets/img/android-mastery/p1c21/01-rizin-stripped-exports-afl.png)

`stripped true`이고 export는 두 개뿐이다. `Java_io_seika_nativere_Native_nativeHello`는 이름만으로 어느 Java 메서드인지 드러나지만, 나머지 네 메서드는 이름이 어디에도 없다. `aaa`로 자동 분석을 돌린 뒤 `afl`을 보면 `fcn.000019a8`(392바이트)과 `fcn.00001b30`(312바이트)이 잡혔고, 정답지 기준으로 각각 `register_vault`와 `check_guess`다. `score`(0x1c68), `build_tag`(0x1c80), `vault_open`(0x1c94)은 함수 목록에 아예 없다. 이 셋은 코드 어디에서도 직접 호출되지 않고 데이터(등록 표)나 스택에 쓰는 주소로만 참조되니, 호출 흐름을 따라가는 분석으로는 발견되지 않았다.

어떤 ABI를 여느냐도 처음부터 정해 둬야 한다. 같은 소스라도 ABI마다 함수 위치가 다르고(아래 Ghidra 결과에서 확인한다), 함수 표 칸 크기도 64비트는 8바이트, 32비트 ARM은 4바이트다. 동적 분석과 맞춰 볼 거라면 대상 기기가 실제로 로드하는 ABI 파일을 열어야 하고, 이번에는 arm64-v8a부터 봤다.

## JNI_OnLoad 안의 0x30과 0x6b8

스트립된 라이브러리에서도 `JNI_OnLoad`는 남는다. ART가 `System.loadLibrary` 처리 중에 이 이름을 dlsym으로 찾아 부르기 때문이다([java_vm_ext.cc L1093](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/java_vm_ext.cc#1093)의 `library->FindSymbol("JNI_OnLoad", nullptr)`). 그래서 분석도 여기서 출발한다.

![rizin pdf @ sym.JNI_OnLoad 결과. 0x1920에서 x0이 가리키는 표를 x8로 읽고 mov w2, 6 / movk w2, 1, lsl 16 뒤 0x1938에서 x8+0x30 칸을 읽어 blr x8, 0x195c에서 문자열 io/seika/nativere/Native를 x1에 넣고 0x1964에서 다시 x8+0x30 칸을 읽어 blr x8, 0x197c adr x2, data.00002d18과 0x1980 mov w3, 3, 0x1988에서 x8+data.000006b8 칸을 읽는 줄 옆에 0x6b8:4=53 ; "5" 주석, 0x198c blr x8, 0x1998 bl fcn.000019a8](/assets/img/android-mastery/p1c21/02-rizin-jni-onload-slot215.png)

간접 호출 세 번이 보인다. 셋 모두 `ldr x8, [x0]`으로 함수 표 포인터를 꺼내고 `ldr x8, [x8, 오프셋]`으로 칸을 고른 다음 `blr x8`로 부른다. 어떤 함수인지는 오프셋을 칸 번호로 바꿔 보면 안다. AOSP [jni.h](https://android.googlesource.com/platform/libnativehelper/+/refs/tags/android-13.0.0_r84/include_jni/jni.h#149)의 `struct JNINativeInterface`와 `struct JNIInvokeInterface`를 스크립트로 세어 본 결과다.

```text
JNINativeInterface: 233 slots
  FindClass              index   6  64-bit 0x30  32-bit 0x18  (jni.h L159)
  GetStringUTFChars      index 169  64-bit 0x548  32-bit 0x2a4  (jni.h L377)
  ReleaseStringUTFChars  index 170  64-bit 0x550  32-bit 0x2a8  (jni.h L378)
  NewStringUTF           index 167  64-bit 0x538  32-bit 0x29c  (jni.h L374)
  RegisterNatives        index 215  64-bit 0x6b8  32-bit 0x35c  (jni.h L454)
JNIInvokeInterface: 8 slots
  GetEnv                 index   6  64-bit 0x30  32-bit 0x18  (jni.h L1044)
```

![AOSP libnativehelper include_jni/jni.h(android-13.0.0_r84) 440~466행 화면. 454행 jint (*RegisterNatives)(JNIEnv*, jclass, const JNINativeMethod*, jint);가 강조돼 있고 위로 SetCharArrayRegion부터 SetDoubleArrayRegion, 아래로 UnregisterNatives, MonitorEnter, MonitorExit, GetJavaVM, GetStringRegion이 이어진다](/assets/img/android-mastery/p1c21/09-aosp-jni-h-registernatives-l454.png)

[L454](https://android.googlesource.com/platform/libnativehelper/+/refs/tags/android-13.0.0_r84/include_jni/jni.h#454)의 `RegisterNatives`가 215번 칸이고, 64비트에서 215×8 = 0x6b8이다. 0x1988의 `ldr x8, [x8, 0x6b8]`이 RegisterNatives이고, 그 직전에 `x2`에 들어간 0x2d18이 표 주소, `w3`의 3이 항목 수다.

여기서 0x30이 두 번 나오는 게 함정이다. 첫 번째 0x30은 `JNI_OnLoad`의 첫 인자 `x0`(JavaVM*)에서 꺼낸 표의 6번 칸이라 `GetEnv`다. 세 번째 인자 `w2`가 0x10006(`JNI_VERSION_1_6`)인 것도 맞아떨어진다. 두 번째 0x30은 GetEnv가 돌려준 env(`[fp, 0x18]`에 저장된 값)에서 꺼낸 표의 6번 칸이라 `FindClass`다. "arm64에서 JNIEnv*는 x0"이라는 말은 네이티브 메서드 본체와 `(*env)->Fn(env, …)` 호출에는 맞지만, `JNI_OnLoad`에 들어온 순간의 x0은 JavaVM*라서, 포인터가 어디서 왔는지 따라가기 전에는 오프셋만으로 어느 표인지 가릴 수 없었다.

Rizin이 붙인 주석도 그대로 믿으면 안 된다. `ldr x8, [x8, data.000006b8]` 옆의 `[0x6b8:4]=53 ; "5"`는 0x6b8을 이 라이브러리의 가상 주소로 보고 그 자리 바이트를 읽어 준 것이다. 여기서 0x6b8은 구조체 안의 오프셋이니 이 주석은 의미가 없다.

## 표를 따라가면 이름과 주소가 나온다

JNINativeMethod는 [jni.h L128~132](https://android.googlesource.com/platform/libnativehelper/+/refs/tags/android-13.0.0_r84/include_jni/jni.h#128)에 정의된 대로 `const char* name`, `const char* signature`, `void* fnPtr` 포인터 세 개다. 64비트에서는 항목 하나가 0x18바이트, armv7에서는 12바이트다. Rizin의 `pf`로 이 모양을 세 번 반복해 0x2d18에 대 보았다.

![rizin pf '3 ssp8 name signature fnPtr' @ 0x2d18를 arm64 libnativere.so에 돌린 결과. 0x2d18 name nativeCheck, 0x2d20 signature (Ljava/lang/String;)Z, 0x2d28 fnPtr 0x1b30, 0x2d30 nativeScore, (II)I, fnPtr 0x1c68, 0x2d48 nativeBuild, ()Ljava/lang/String;, fnPtr 0x1c80까지 아홉 줄](/assets/img/android-mastery/p1c21/03-rizin-pf-table-0x2d18.png)

출력 아홉 줄이 등록 표 전부다. 항목이 0x2d18, 0x2d30, 0x2d48로 0x18씩 떨어져 있고 `nativeCheck (Ljava/lang/String;)Z → 0x1b30`, `nativeScore (II)I → 0x1c68`, `nativeBuild ()Ljava/lang/String; → 0x1c80`이다. PIE 라이브러리라 이 포인터들은 로드할 때 `R_AARCH64_RELATIVE` 재배치로 채워지는데, Rizin이 재배치를 적용해 보여 주기 때문에 포인터가 바로 로드 베이스 기준 가상 주소(vaddr, 곧 모듈 오프셋)로 읽혔다. 파일 안 위치(paddr)는 이와 달라서, 실행 세그먼트가 파일 오프셋 0x8a0을 vaddr 0x18a0에 올리는 이 라이브러리에서 0x1b30의 파일 오프셋은 0xb30이다. 정답지(`llvm-nm`)의 `check_guess 1b30`, `score 1c68`, `build_tag 1c80`과 같다.

`(Ljava/lang/String;)Z` 같은 시그니처는 매핑을 확정하는 데 생각보다 쓸모가 크다. 이름이 겹치는 오버로드를 가르고, 네이티브 함수가 몇 번째 인자를 jstring으로 받는지 알려 주니 Ghidra에서 타입을 입힐 근거가 된다.

## 같은 작업을 Ghidra 헤드리스 스크립트로

손으로 한 번 해 봤으니 스크립트로 바꿨다. `RecoverJniNatives.java`는 Java로 쓴 GhidraScript다. 피연산자로 `215 × 포인터 크기`를 쓰는 명령을 찾고, 그 뒤의 간접 호출을 잡아, 함수 전체에 Ghidra의 상수 전파(`SymbolicPropogator`)를 돌려 호출 시점의 methods·count 레지스터 값을 읽는다. 값이 상수면 그 자리에 `JNINativeMethod[n]` 구조체를 만들고 각 fnPtr를 `JNI_<클래스>_<이름>` 함수로 만든다. 그 부분을 옮긴다(원본 61~96행 발췌).

```java
    private void report(Function f, Instruction call, String[] regs, DataType jnmType) throws Exception {
        SymbolicPropogator sp = new SymbolicPropogator(currentProgram);
        sp.flowConstants(f.getEntryPoint(), f.getBody(), new ConstantPropagationContextEvaluator(monitor, true), false, monitor);
        Address at = call.getAddress();
        Value methods = sp.getRegisterValue(at, currentProgram.getRegister(regs[0]));
        Value count = sp.getRegisterValue(at, currentProgram.getRegister(regs[1]));
        String fname = f.getName();
        println(String.format("call @ %s in %s: %s", at, fname, call));
        if (methods == null || count == null) {
            println("  methods/count not constant here");
            return;
        }
        if (methods.getRelativeRegister() != null) {
            println(String.format("  methods = %s%+d (built at run time on the stack), count = %d -> table not in the file",
                    methods.getRelativeRegister().getName(), methods.getValue(), count.getValue()));
            return;
        }
        Address tab = toAddr(methods.getValue());
        int n = (int) count.getValue();
        String cls = guessClass(f, call);
        println(String.format("  methods = %s, count = %d, class = %s", tab, n, cls));
        clearListing(tab, tab.add((long) n * 3 * ptr - 1));
        createData(tab, new ArrayDataType(jnmType, n, 3 * ptr));
        createLabel(tab, "JNINativeMethods_" + cls.replace('/', '_'), true, SourceType.USER_DEFINED);
        for (int i = 0; i < n; i++) {
            Address e = tab.add((long) i * 3 * ptr);
            String name = cstr(readPtr(e));
            String sig = cstr(readPtr(e.add(ptr)));
            Address fn = readPtr(e.add(2L * ptr));
            String label = "JNI_" + cls.substring(cls.lastIndexOf('/') + 1) + "_" + name;
            Function tf = getFunctionAt(fn);
            if (tf == null) tf = createFunction(fn, label);
            else tf.setName(label, SourceType.USER_DEFINED);
            setPlateComment(fn, cls.replace('/', '.') + "." + name + " " + sig);
            println(String.format("  [%d] %-12s %-24s -> %s  %s", i, name, sig, fn, label));
        }
```

인자 레지스터는 아키텍처마다 다르게 준다. AArch64는 `x2/x3`, 32비트 ARM은 `r2/r3`, x86-64는 `RDX/RCX`다. 세 ABI 라이브러리에 같은 스크립트를 돌렸다.

![analyzeHeadless.bat를 arm64-v8a, armeabi-v7a, x86_64에 돌린 RecoverJniNatives.java 출력. AARCH64는 slot 215 -> offset 0x6b8, call @ 0010198c blr x8, methods = 00102d18 count 3 class io/seika/nativere/Native, nativeCheck -> 00101b30, nativeScore -> 00101c68, nativeBuild -> 00101c80. ARM 32-bit는 offset 0x35c, blx r12, 00012914, 0001174c, 0001186c, 00011880. x86 64-bit는 CALL qword ptr R8 + 0x6b8, 00102e20, 00101c60, 00101d70, 00101d90. 세 ABI 모두 두 번째 호출에서 methods = sp-56, sp-44, RSP-40 (built at run time on the stack) -> table not in the file. 아래 llvm-nm 정답지 build_tag 1c80, check_guess 1b30, score 1c68, vault_open 1c94](/assets/img/android-mastery/p1c21/04-ghidra-headless-three-abis.png)

세 ABI의 결과를 표로 옮겼다. 주소는 Ghidra가 찍은 그대로다.

| ABI | RegisterNatives 호출 | 표 주소(Ghidra) | nativeCheck | nativeScore | nativeBuild |
|---|---|---|---|---|---|
| arm64-v8a | `blr x8` (0x6b8) | 00102d18 | 0x1b30 | 0x1c68 | 0x1c80 |
| armeabi-v7a | `blx r12` (0x35c) | 00012914 | 0x174c | 0x186c | 0x1880 |
| x86_64 | `CALL [R8 + 0x6b8]` | 00102e20 | 0x1c60 | 0x1d70 | 0x1d90 |

Ghidra는 64비트 PIE `.so`를 이미지 베이스 0x100000에, armv7은 0x10000에 올린다. Rizin은 0에 올리니 같은 함수가 Rizin에서는 0x1b30, Ghidra에서는 00101b30으로 찍힌다. Frida 같은 동적 도구에 넘길 값은 "모듈 베이스 + 0x1b30"이다. 표를 보면 소스가 같아도 nativeCheck가 arm64 0x1b30, armv7 0x174c, x86_64 0x1c60으로 다 다르다. arm64 라이브러리에서 뽑은 오프셋을 x86_64 에뮬레이터 프로세스에 걸면 다른 함수 중간을 가리키게 된다(표의 오프셋 차이로 본 것이고 기기에서 걸어 보지는 않았다).

x86_64 쪽은 지우기 전 사본의 심볼과도 대 보았다.

```text
## x86_64 unstripped nm (ground truth)
0000000000001910 T JNI_OnLoad
00000000000018f0 T Java_io_seika_nativere_Native_nativeHello
0000000000001d90 t build_tag
0000000000001c60 t check_guess
0000000000001d70 t score
0000000000001db0 t vault_open
## x86_64 stripped: lea of vault fnPtr in fcn.00001990
│           0x00001c1a      lea   rax, qword data.00001db0             ; 0x1db0
│       │   0x00001c42      call  qword [r8+data.000006b8]             ; 0x6b8
```

스크립트가 낸 0x1c60, 0x1d70, 0x1d90이 심볼과 일치한다. 다만 이건 파일과 파일을 맞춘 것이다. 이 라이브러리를 에뮬레이터에 올려 Frida로 같은 오프셋에 후크를 걸고 RegisterNatives가 넘기는 주소와 비교하는 단계는 이번에 돌리지 못했다. 런타임 쪽 방법과 그때 본 출력은 [10장의 215번 칸 후킹](/posts/android-lab-p1c10-jni-native-observation/)에 있고, 거기서는 RegisterNatives가 넘긴 주소에 후크를 걸어 JNI 인자와 반환값을 읽었다.

## 디컴파일러에 JNI 타입을 입히면

Rizin 문서나 옛 글에서 디컴파일 명령으로 `pdc`와 `pdg`를 소개하는 경우가 많은데, 지금 Rizin에서는 둘 다 기본으로 없다. 0.9.1에서 그대로 쳐 보면 이렇게 나온다.

```text
$ rizin -e scr.color=0 -qc 'pdc' -c 'pdg' apk/lib/arm64-v8a/libnativere.so 2>&1 | grep 'does not exist'
ERROR: Command 'pdc' does not exist.
ERROR: Command 'pdg' does not exist.
```

`pdc`는 radare2의 의사 C 출력이고, Rizin은 포크 직후 [PR #105](https://github.com/rizinorg/rizin/pull/105)에서 이걸 지웠다. `pdg`는 [rz-ghidra](https://github.com/rizinorg/rz-ghidra) 플러그인을 설치해야 생기는 명령이다. 플러그인 없이 디컴파일이 필요하면 Ghidra 쪽으로 넘어가는 게 빠르다.

Ghidra 디컴파일러로 `JNI_OnLoad`를 그냥 뽑으면 앞에서 본 오프셋이 그대로 C 문법으로 바뀔 뿐이다. 그래서 NDK의 `jni.h`를 전처리해 Ghidra가 읽을 수 있게 다듬고(`__attribute__`, `_Nonnull` 제거) `ApplyJniTypes.java`로 파싱했다. 이 스크립트가 `JNI_OnLoad`의 프로토타입을 `jint JNI_OnLoad(JavaVM *vm, void *reserved)`로 바꾸고, GetEnv가 채우는 지역 변수를 `JNIEnv *env`로 잡고, 등록 표에서 찾은 `JNI_*` 함수들에 JNI 시그니처대로 타입을 입힌다. 정적인지 인스턴스인지는 시그니처만으로 알 수 없어서 두 번째 인자는 `jobject thiz_or_clazz`로 뒀다.

![analyzeHeadless.bat -readOnly로 DecompileJni.java와 ApplyJniTypes.java를 돌린 뒤, 타입 없는 decomp/plain/JNI_OnLoad.c에 param_1 + 0x30 칸 호출(param_1,&local_8,0x10006), local_8 + 0x30 칸 호출(local_8,"io/seika/nativere/Native"), local_8 + 0x6b8 칸 호출(local_8,lVar3,JNINativeMethods_io_seika_nativere_Native,3)이 보이고, 타입을 입힌 결과 grep에는 (*vm)->GetEnv(vm,&env,0x10006), (*env)->FindClass, (*env)->RegisterNatives, JNI_Native_nativeCheck의 GetStringUTFChars와 ReleaseStringUTFChars, JNI_Native_nativeBuild의 NewStringUTF(env,"nativere-1105")가 보이는 화면](/assets/img/android-mastery/p1c21/05-ghidra-decompile-before-after-jni-types.png)

타입을 입히기 전에는 `(*param_1 + 0x30)`과 `(*local_8 + 0x30)`이 똑같이 생겨서 어느 쪽이 GetEnv인지 머릿속으로 계산해야 한다. 그나마 세 번째 인자 자리에 `JNINativeMethods_io_seika_nativere_Native`가 보이는 건 앞의 스크립트가 붙인 라벨 덕분이다. 타입을 입힌 뒤에는 `(*(*vm)->GetEnv)`, `(*(*env)->FindClass)`, `(*(*env)->RegisterNatives)`로 바로 읽히고, `nativeCheck` 본체에서는 `GetStringUTFChars`로 받은 문자열을 `strcmp`에 넘기는 흐름이, `nativeBuild`에서는 `"nativere-1105"`가 드러난다.

Ghidra 12.1.4는 JDK 21 이상을 요구하고(`application.properties`의 `application.java.min=21`), Jython은 확장으로 분리돼 기본으로는 설치돼 있지 않다(File → Install Extensions에서 켜야 한다, GP-6754, [ChangeHistory](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.1.4_build/Ghidra/Configurations/Public_Release/src/global/docs/ChangeHistory.md)). 여기서 쓴 스크립트는 전부 Java라 상관이 없었다.

## 스택에서 조립한 표는 상수 전파로 안 풀린다

Ghidra 출력에서 세 ABI 모두 두 번째 RegisterNatives 호출은 스택 상대값(arm64 `sp-56`, armv7 `sp-44`, x86_64 `RSP-40`)과 `(built at run time on the stack)`으로 끝났다. `register_vault`는 표를 스택에 만들고, 그 안의 이름·시그니처 포인터는 런타임에 `.bss`로 풀어 낸 문자열을 가리킨다. 상수 전파는 "스택 포인터에서 56 아래"까지만 알려 주고, 거기 무엇이 쓰일지는 모른다. 파일에 등록 표가 없으니 표를 읽는 방식은 여기서 끝난다.

Rizin으로 돌아가면 길이 남아 있다. `pd 9 @ 0x1ad8`에서 `stp x8, x11, [var_38h]`가 이름과 시그니처 포인터를 스택에 쓰고, `adrp x9, 0x1000; add x9, x9, 0xc94; str x9, [var_38h + 0x10]`이 fnPtr 0x1c94를 그 옆에 쓴다. 함수 주소는 코드에 상수로 남아 있다. 문자열은 Rizin의 ESIL 에뮬레이터로 `register_vault` 시작(0x19a8)부터 FindClass 호출 직전(0x1ad8)까지 돌린 다음 `.bss`의 0x3f20, 0x3f30, 0x3f38을 읽었더니 `nativeOpen`, `(I)Z`, `io/seika/nativere/Vault`가 나왔다.

![rizin pd 9 @ 0x1ad8에서 stp x8, x11, [var_38h], ldr x8, [x9, 0x30], adrp x9, 0x1000 / add x9, x9, 0xc94 / str x9, [var_38h + 0x10], blr x8이 보이고, io.cache=true로 s 0x19a8, aei, aeim, aeip, aesu 0x1ad8 후 ps @ 0x3f20, 0x3f30, 0x3f38이 nativeOpen, (I)Z, io/seika/nativere/Vault를 출력한 화면](/assets/img/android-mastery/p1c21/06-rizin-esil-vault-strings.png)

같은 수법으로 `check_guess`(0x1b30)를 `GetStringUTFChars` 직전(0x1c14)까지 에뮬레이션하고 스택을 읽자 XOR을 푼 비교 문자열 `SEIKA-RE-1105`가 나왔다. Ghidra 디컴파일 결과에서도 이 함수는 `DAT_00103f18 ^ 상수`를 13번 스택에 쓰는 모양이라 손으로 풀 수는 있지만, ESIL에 맡기면 그 계산을 건너뛴다.

`vault_open`은 더 허무하다. `af @ 0x1c94`로 함수를 만들어 보면 `mov w8, 0x1567; cmp w2, w8; cset w0, eq; ret` 네 줄이다. 소스의 `(pin ^ 0x5a5a) == 0x4f3d`를 컴파일러가 `pin == 0x5a5a ^ 0x4f3d`, 곧 `pin == 0x1567`(5479)로 접어 버렸다. 세 번째 인자 `w2`가 jint `pin`이다.

![rizin io.cache=true로 s 0x1b30, aei, aeim, aeip, aesu 0x1c14 후 ps @ sp가 SEIKA-RE-1105를 출력하고, af @ 0x1c94와 pdf @ 0x1c94가 fcn.00001c94(int64_t arg1, int64_t arg3)의 mov w8, 0x1567 / cmp w2, w8 / cset w0, eq / ret 네 줄을 보여 주는 화면](/assets/img/android-mastery/p1c21/07-rizin-esil-secret-vault-open.png)

여기까지는 파일에서 얻은 입력값이다. `SEIKA-RE-1105`와 5479를 실제 앱에 넣어 `true`가 나오는지는 이번에 기기에서 확인하지 못했다. 난독화 쪽도 이 실험이 다룬 건 "표를 스택에 만들고 문자열을 XOR로 푸는" 정도다. OLLVM 같은 제어 흐름 평탄화나 패커를 붙였을 때 ESIL 에뮬레이션이 어디까지 버티는지는 시험하지 않았다.

## 직접 export한 Java_ 함수는 언제 연결되나

`nativeHello`는 표에 없다. ART는 이런 메서드를 처음 호출될 때 [jni_entrypoints.cc](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/entrypoints/jni/jni_entrypoints.cc#50)의 `artFindNativeMethodRunnable`에서 `FindCodeForNativeMethod`로 넘기고, 로드된 라이브러리들에서 `Java_io_seika_nativere_Native_nativeHello`라는 이름을 dlsym으로 찾는다. 라이브러리 로더의 지연 바인딩과는 관계가 없다. bionic 링커는 [linker.cpp L2903](https://android.googlesource.com/platform/bionic/+/refs/tags/android-13.0.0_r84/linker/linker.cpp#2903)에서 `DT_PLTGOT`를 "RTLD_LAZY is not supported"라며 무시한다. 정적 분석 입장에서는 이 방식이 가장 쉽다. `iE` 한 번에 이름과 주소(0x1900)가 같이 나온다. 이 경로가 실제로 첫 호출 때 dlsym을 거치는 모습은 10장에서 Frida로 본 적이 있고, 이번 라이브러리로는 다시 돌리지 않았다.

## 라이브러리를 만드는 쪽에서 확인할 것

등록 표를 상수로 두면, 심볼을 지워도 `JNI_OnLoad` → slot 215 → 표 주소 → 항목 순회라는 기계적인 경로로 매핑이 나온다. 위의 Ghidra 스크립트는 아키텍처별 인자 레지스터만 알려 주자 세 ABI 모두에서 같은 이름·시그니처 매핑을 뽑아냈다(주소는 ABI마다 달랐다). 표를 런타임에 만들면 상수 전파는 멈추지만, 디코드 루프가 라이브러리 안에 있는 한 에뮬레이션이 그걸 대신 돌려 준다. 이번 `check_guess`도 XOR을 풀어 둔 비교 문자열이 ESIL 한 번에 나왔으니, 통과 여부를 가르는 비밀은 서버나 하드웨어 키 저장소 쪽에 두고 네이티브 난독화는 분석 시간을 늘리는 정도로 보는 편이 맞다고 생각한다.

확인하는 방법도 이 실험 그대로다. 릴리스 빌드의 각 ABI `.so`에 `RecoverJniNatives.java`를 헤드리스로 돌려 등록 표가 그대로 출력되는지 보고, 출력된 이름 집합이 Java 쪽 `native` 선언과 같은지 대조하면 "정적으로 얼마나 드러나는가"를 빌드마다 회귀 검사로 돌릴 수 있다. `table not in the file`이 나오면 다음 단계로 Rizin ESIL을 디코드 루프에 돌려 문자열이 나오는지 본다. `strings`나 `iE`에서 의도하지 않은 이름이 보이는지도 같이 본다. 이번 빌드에서는 `-fvisibility=hidden` 덕분에 export가 `JNI_OnLoad`와 일부러 연 `Java_` 하나뿐이었다.

## -mbranch-protection과 16 KB 정렬이 바꾼 것

arm64 빌드 옵션도 정적 분석 화면을 바꾼다. NDK r27d 기본 설정으로 만든 arm64 라이브러리는 `llvm-readelf`로 보면 LOAD 세그먼트 정렬이 0x1000이고, 우리 코드에는 `paciasp`/`autiasp`가 없었다. 디스어셈블에 보인 `bti c`는 NDK가 붙이는 crt 오브젝트 쪽뿐이었고 GNU property 노트도 없었다. `-mbranch-protection=standard`와 `-Wl,-z,max-page-size=16384`를 주고 다시 빌드하자 정렬이 0x4000으로 바뀌고, PAC/BTI 명령이 6개에서 17개로 늘었으며, 노트에 `aarch64 feature: BTI, PAC`가 찍혔다.

```text
== default NDK 27 arm64 build: LOAD align
  LOAD           0x0008a0 0x00000000000018a0 0x00000000000018a0 0x000470 0x000470 R E 0x1000
== paciasp/bti count in default build
6
== -mbranch-protection=standard -z max-page-size=16384
  LOAD           0x000940 0x0000000000004940 0x0000000000004940 0x0004b0 0x0004b0 R E 0x4000
17
    Properties:    aarch64 feature: BTI, PAC
```

`paciasp`와 `bti c`는 힌트 공간 명령이라 디스어셈블과 디컴파일 흐름에는 영향이 없었다. [16 KB 페이지 문서](https://developer.android.com/guide/practices/page-sizes)에 따르면 r28부터는 16 KB 정렬이 기본이니, 최신 앱의 arm64 `.so`에서는 0x4000 정렬을 보는 게 정상이다. PAC가 실제로 포인터를 서명하고 검사하는 런타임 동작은 x86_64 에뮬레이터에서는 관측할 수 없어서 보지 못했다.

*다음 글: [ASan·IntSan으로 JNI 버그 읽기](/posts/android-lab-p1c22-sanitizer-jni-analysis/)*
