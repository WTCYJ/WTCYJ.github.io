---
layout: post
title: "JNI·native 함수 동적 관찰 — 스트립된 함수를 RegisterNatives로 찾기"
date: 2026-10-25 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, JNI, Frida, RegisterNatives, libart, CheckJNI, NativeHook]
excerpt: "심볼을 지운 자작 .so를 spawn으로 띄우고 libart의 RegisterNatives에 후크를 걸어 nativeCheck가 libjnimap.so+0x19f0이라는 걸 찾았고, 그 주소에서 strcmp에 들어가는 비밀값과 반환값까지 읽었다. RegisterNatives는 libart에서 export되지 않았고, debuggable 앱에서는 등록 스레드의 215번 칸이 CheckJNI 판을 가리켰다."
---

[지난 글](/posts/android-lab-p1c09-classloader-dynamic-loading/)에서는 패커가 ART에 넘기는 dex를 입구에서 받아 냈다. 그렇게 꺼낸 dex는 다시 jadx로 읽힌다. 앱이 `.so`에 넣어 둔 로직은 사정이 다르다. DEX에는 `native` 선언 한 줄만 남고, 라이브러리를 스트립하면 함수 이름까지 사라진다. 그래도 Java 메서드와 C 함수가 이어지는 순간은 있고, 라이브러리가 직접 등록하는 방식이면 그 순간은 ART의 `RegisterNatives`를 지난다. 이번에는 [8장](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)의 Frida로 그 지점을 잡아 이름과 주소의 짝을 받아 적고, 그 주소에 직접 붙어 인자와 반환값을 읽는다. JNI 경계와 `.so` 로딩의 개념은 [Atlas C15](/posts/android-concept-atlas-c15-jni-native-library-loading/)에, PLT와 GOT는 [C33](/posts/android-concept-atlas-c33-elf-linker-plt-got/)에 있다.

기기는 `codex-atlas-api33` 에뮬레이터(Android 13, API 33, google_apis x86_64 userdebug, 빌드 TE1A.240213.009, 보안 패치 2024-03-01)이고 ART 모듈은 versionCode 331711080이다. `adb root`가 되고 SELinux는 Enforcing이다. 이 이미지는 `ro.product.cpu.abilist`가 `x86_64` 하나이고 `ro.dalvik.vm.native.bridge`는 `0`이다. ARM 코드를 옮겨 주는 변환 계층 없이 앱의 x86_64 라이브러리가 그대로 돈다. arm64의 PAC/BTI가 켜진 함수에 거는 후크는 이 x86_64 이미지에서 볼 수 없어서 [C37](/posts/android-concept-atlas-c37-exploit-mitigations/)의 설명으로 대신한다. libart에서 심볼 표가 빠진 경우를 볼 때만 `sec-36-std`(Android 16, API 36, ART 모듈 360527520)를 따로 띄웠다. 호스트 쪽은 Frida 17.17.0과 frida-tools 14.8.1, NDK 27의 clang 18.0.4와 llvm 도구, jadx 1.5.5, 에뮬레이터 36.5.11이다. ART 소스 링크는 기기의 ART 모듈과 같은 태그 `aml_art_331711080`에, 프레임워크와 bionic 링크는 `android-13.0.0_r84`에 걸었다.

## 심볼을 지운 libjnimap.so와 실험 앱

실험 앱 `io.seika.jnimap`의 Java 쪽은 네이티브 메서드를 선언한 `Native` 클래스와 액티비티 하나다.

```java
// src/io/seika/jnimap/Native.java
package io.seika.jnimap;

public class Native {
    static {
        System.loadLibrary("jnimap");
    }

    // registered from JNI_OnLoad with RegisterNatives (no exported symbol)
    public native boolean nativeCheck(String guess);

    public static native int nativeMix(int x);

    // registered too; calling it makes the library call RegisterNatives again
    public static native int nativeRebind();

    // classic Java_<pkg>_<Class>_<method> export, resolved by ART on first call
    public static native String nativeHello();
}
```

`nativeCheck`, `nativeMix`, `nativeRebind`는 라이브러리의 `JNI_OnLoad`가 `RegisterNatives`로 등록한다. `nativeHello` 하나만 `Java_패키지_클래스_메서드` 이름 규칙을 따르는 export로 남겼다. 한 라이브러리 안에서 두 연결 방식을 나란히 보려고 섞었다.

```c
// jni/jnimap.c
// libjnimap.so: built with -fvisibility=hidden and stripped (-s), so the functions
// registered below have no symbol at all. Only JNI_OnLoad and the classic
// Java_ export are visible in .dynsym.
#include <jni.h>
#include <string.h>
#include <android/log.h>

#define TAG "JniMap"

// "SEIKA-JNI-1025" XOR 0x5a, decoded only at call time
static const unsigned char kEnc[] = {
    0x09, 0x1f, 0x13, 0x11, 0x1b, 0x77, 0x10, 0x14, 0x13, 0x77, 0x6b, 0x6a, 0x68, 0x6f,
};
static volatile unsigned char kKey = 0x5a;  // volatile: keep the decode at run time

static jboolean verify_guess(JNIEnv *env, jobject thiz, jstring guess) {
    char secret[sizeof(kEnc) + 1];
    for (size_t i = 0; i < sizeof(kEnc); i++) secret[i] = (char)(kEnc[i] ^ kKey);
    secret[sizeof(kEnc)] = '\0';

    const char *s = (*env)->GetStringUTFChars(env, guess, NULL);
    if (s == NULL) return JNI_FALSE;
    int ok = strcmp(s, secret) == 0;
    (*env)->ReleaseStringUTFChars(env, guess, s);
    memset(secret, 0, sizeof(secret));
    return ok ? JNI_TRUE : JNI_FALSE;
}

static jint mix_int(JNIEnv *env, jclass clazz, jint x) {
    return (x * 31) ^ 0x1025;
}

static jint rebind(JNIEnv *env, jclass clazz);

static const JNINativeMethod kMethods[] = {
    {"nativeCheck", "(Ljava/lang/String;)Z", (void *)verify_guess},
    {"nativeMix", "(I)I", (void *)mix_int},
    {"nativeRebind", "()I", (void *)rebind},
};
#define N_METHODS ((jint)(sizeof(kMethods) / sizeof(kMethods[0])))

// registers the same table again at a moment the app chooses (lets an attached
// tool see a RegisterNatives call without spawning the app)
static jint rebind(JNIEnv *env, jclass clazz) {
    jint r = (*env)->RegisterNatives(env, clazz, kMethods, N_METHODS);
    __android_log_print(ANDROID_LOG_INFO, TAG, "nativeRebind: RegisterNatives(%d) = %d", N_METHODS, r);
    return r;
}

JNIEXPORT jstring JNICALL Java_io_seika_jnimap_Native_nativeHello(JNIEnv *env, jclass clazz) {
    return (*env)->NewStringUTF(env, "hi from Java_ export");
}

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env;
    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6) != JNI_OK) return JNI_ERR;
    jclass c = (*env)->FindClass(env, "io/seika/jnimap/Native");
    if (c == NULL) return JNI_ERR;
    if ((*env)->RegisterNatives(env, c, kMethods, N_METHODS) != JNI_OK) return JNI_ERR;
    __android_log_print(ANDROID_LOG_INFO, TAG, "JNI_OnLoad: RegisterNatives(%d) ok", N_METHODS);
    return JNI_VERSION_1_6;
}
```

`verify_guess`는 XOR로 감춰 둔 문자열을 호출될 때만 스택에 풀어 입력과 `strcmp`로 비교하고, 끝나면 지운다. 바이너리에서 평문 비밀값을 치워 둔 흔한 모양을 작게 흉내 냈다. `rebind`는 같은 표로 `RegisterNatives`를 다시 부른다. 이미 떠 있는 앱에 붙은 도구에게 등록 호출을 보여 주려고 넣었다.

APK는 javac, d8, aapt, apksigner를 차례로 부르는 작은 빌드 스크립트로 묶었고, `jni/` 아래 C 파일은 NDK clang으로 이렇게 컴파일된다.

```
clang --target=x86_64-linux-android26 -fPIC -shared -O1 -g -s -fvisibility=hidden \
    jni/jnimap.c -llog -o lib/x86_64/libjnimap.so
```

`-g`로 디버그 정보를 만들어도 `-s`가 링크 단계에서 심볼 표와 함께 걷어 낸다. 등록하는 함수들은 `static`이라 처음부터 `.dynsym`에 들어가지 않고, `-s`는 `.symtab`에 남은 로컬 심볼을 지운다(`-s`를 뺀 빌드에서는 `llvm-nm`에 `t verify_guess`처럼 보인다). `-fvisibility=hidden`은 `static`이 아니면서 `JNIEXPORT`도 없는 보조 함수를 `.dynsym`에서 뺀다. 오프셋을 맞춰 보려고 `-s`만 뺀 같은 빌드(`libjnimap.unstripped.so`)도 남겼는데, 두 파일의 `.text`는 바이트 단위로 같았다. 비교용으로 매니페스트에 `android:debuggable="true"`만 더한 `io.seika.jnimapdbg`를 같은 코드로 하나 더 만들었다. 둘 다 minSdk 26, targetSdk 33이고 `lib/x86_64`만 들어 있다.

액티비티는 `singleTop`이라 `am start`를 다시 보내면 같은 인스턴스의 `onNewIntent`에서 `run()`이 돈다. 인텐트 엑스트라로 입력을 바꿀 수 있게 했다.

```java
// src/io/seika/jnimap/MainActivity.java 30~38행
    private void run(Intent i) {
        String guess = i.getStringExtra("guess");
        if (guess == null) guess = "hello";
        int n = i.getIntExtra("n", 42);

        boolean ok = new Native().nativeCheck(guess);
        int mix = Native.nativeMix(n);
        String hello = i.getBooleanExtra("hello", false) ? Native.nativeHello() : "(not called)";
        String rebind = i.getBooleanExtra("rebind", false) ? String.valueOf(Native.nativeRebind()) : "(not called)";
```

결과는 화면과 logcat `JniMap` 태그에 찍히고, `nativeCheck`가 true면 `UNLOCKED`, false면 `locked`가 뜬다. 기기 준비는 아래와 같고, 이후 명령의 `$S`는 에뮬레이터 시리얼이다.

```bash
export S=emulator-5600
adb -s $S root
adb -s $S install out/jnimap.apk
adb -s $S install out/jnimapdbg.apk
adb -s $S push frida-server-17.17.0-android-x86_64 /data/local/tmp/frida-server
adb -s $S shell chmod 755 /data/local/tmp/frida-server
adb -s $S shell "pidof frida-server >/dev/null || (/data/local/tmp/frida-server >/dev/null 2>&1 &)"
```

## 파일만 봐서는 nativeCheck가 어느 함수인지 모른다

먼저 정적으로 무엇이 남는지 봤다. `llvm-*`는 NDK에 들어 있는 도구다.

```bash
jadx -q -d jx out/jnimap.apk && grep -n 'native' jx/sources/io/seika/jnimap/Native.java
unzip -o -q out/jnimap.apk lib/x86_64/libjnimap.so -d apk && llvm-readelf -S -W apk/lib/x86_64/libjnimap.so | grep -c -E 'symtab|debug_info'
llvm-nm -D --defined-only apk/lib/x86_64/libjnimap.so
llvm-objdump -d --no-show-raw-insn --start-address=0x1960 --stop-address=0x1b00 apk/lib/x86_64/libjnimap.so | grep -E '<JNI_OnLoad>:|callq|^ +(19f0|1a90|1aa0):|JNI_OnLoad\+0xb0'
llvm-strings apk/lib/x86_64/libjnimap.so | grep -E '^native|^\('
llvm-readelf -r -W apk/lib/x86_64/libjnimap.so | grep -E '^0000000000002b(50|58|60)'
llvm-nm out/libjnimap.unstripped.so | grep -E 'verify_guess|mix_int|rebind'
```

![jadx로 푼 Native.java에는 native 선언 네 줄뿐이고, libjnimap.so는 symtab·debug_info 섹션 수 0, llvm-nm -D 결과는 JNI_OnLoad 1960과 Java_io_seika_jnimap_Native_nativeHello 1940 두 개다. objdump에는 19b4의 callq *0x6b8(%r8), 이름 없는 19f0·1a90·1aa0 코드, 분기 대상 표기 JNI_OnLoad+0xb0, callq *0x548·*0x550과 strcmp@plt가 보이고, llvm-strings는 nativeCheck·nativeMix·nativeRebind와 시그니처를, .rela.dyn은 2b50·2b58·2b60 → 6ec·6f8·19f0을, 스트립 전 빌드는 19f0 verify_guess·1a90 mix_int·1aa0 rebind를 보여 준다](/assets/img/android-mastery/p1c10/01-static-stripped-lib.png)

jadx로 푼 `Native.java`에는 `native` 선언 네 줄뿐이다. 라이브러리에는 `.symtab`도 `.debug_info`도 없고, `llvm-nm -D`가 보여 주는 동적 심볼은 `JNI_OnLoad`(0x1960)와 `Java_io_seika_jnimap_Native_nativeHello`(0x1940)뿐이다. `nativeCheck`가 실제로 어느 함수인지 이름으로 찾을 방법이 없다.

디스어셈블에는 단서가 있다. `JNI_OnLoad`의 0x19b4 `callq *0x6b8(%r8)`은 JNIEnv 함수 표에서 0x6b8 ÷ 8 = 215번 칸을 부르는데, 그 칸이 `RegisterNatives`다. 앞의 `callq *0x30(%rax)` 두 번은 JavaVM 표 6번 칸의 `GetEnv`와 JNIEnv 표 6번 칸의 `FindClass`다. 0x19f0, 0x1a90, 0x1aa0에서 시작하는 코드에는 이름표가 없다. objdump는 0x1a25의 분기 대상 0x1a10을 `<JNI_OnLoad+0xb0>`으로 적는데, 이름 없는 코드를 바로 앞 심볼에 오프셋을 붙여 부른 것이라 스트립된 함수가 `JNI_OnLoad`의 일부처럼 읽힌다. 0x1a3a의 `*0x548`(169번 `GetStringUTFChars`)과 0x1a67의 `*0x550`(170번 `ReleaseStringUTFChars`) 사이에 `strcmp@plt` 호출이 끼어 있다. 문자열 쪽에는 메서드 이름과 시그니처가 평문으로 남았다.

이 라이브러리는 등록 표를 상수 배열로 들고 있어서 정적으로도 짝을 맞출 수 있다. 위치 독립 코드라 배열의 포인터 칸은 로드할 때 `.rela.dyn`의 `R_X86_64_RELATIVE` 재배치로 채워진다. 0x2b50, 0x2b58, 0x2b60 칸이 0x6ec(`"nativeCheck"`), 0x6f8(`"(Ljava/lang/String;)Z"`), 0x19f0을 차례로 가리키고, 8바이트 간격의 이 칸들이 `JNINativeMethod`의 `name`, `signature`, `fnPtr`이다. 스트립하지 않은 빌드에서 0x19f0은 `verify_guess`, 0x1a90은 `mix_int`, 0x1aa0은 `rebind`였다. [21장](/posts/android-lab-p1c21-ghidra-rizin-native/)에서 Ghidra로 따라가는 길이 이것이다. 이름 문자열을 실행 중에 복호화하거나 표를 런타임에 조립하는 라이브러리라면 재배치에서 짝이 나오지 않고, 등록되는 순간을 지켜보는 쪽이 남는다. 그렇게 만든 상용 난독화 라이브러리는 이번에 다루지 않았다.

`JNINativeMethod`는 포인터 세 개짜리 구조체라 LP64에서는 x86_64든 arm64든 24바이트다. NDK 27의 `jni.h`로 아래 단언을 두 타깃에 컴파일해 보니 모두 통과했다.

```c
// slotassert.c
#include <jni.h>
#include <stddef.h>
_Static_assert(offsetof(struct JNINativeInterface, RegisterNatives) / sizeof(void *) == 215, "RegisterNatives slot");
_Static_assert(offsetof(struct JNINativeInterface, UnregisterNatives) / sizeof(void *) == 216, "UnregisterNatives slot");
_Static_assert(offsetof(struct JNINativeInterface, GetVersion) / sizeof(void *) == 4, "GetVersion slot");
_Static_assert(sizeof(struct JNINativeInterface) / sizeof(void *) == 233, "table entries");
_Static_assert(sizeof(JNINativeMethod) == 24, "JNINativeMethod size on LP64");
_Static_assert(offsetof(JNINativeMethod, fnPtr) == 16, "fnPtr offset");
```

```
clang --target=x86_64-linux-android26 -fsyntax-only slotassert.c
clang --target=aarch64-linux-android26 -fsyntax-only slotassert.c
```

215번은 [JNI 명세의 RegisterNatives 항목](https://docs.oracle.com/en/java/javase/21/docs/specs/jni/functions.html#registernatives)이 정해 둔 번호이고, Android의 [jni.h](https://android.googlesource.com/platform/libnativehelper/+/refs/tags/android-13.0.0_r84/include_jni/jni.h#454)도 같은 자리에 `RegisterNatives`를 둔다.

## libart의 RegisterNatives는 export되지 않는다

등록을 실제로 처리하는 함수는 libart.so에 있다. libart가 `RegisterNatives`를 C++ 맹글 이름으로 export하니 그 이름으로 찾으면 된다는 설명을 종종 보는데, 파일을 열어 보면 그렇지 않다. `art33-sdk/libart.so`는 SDK 시스템 이미지에서 꺼낸 사본으로 기기의 `/apex/com.android.art/lib64/libart.so`와 sha256(`7c0d898b…3efdae`)이 같고, `art9/libart.so`는 API 28 x86 시스템 이미지에서 꺼낸 것이다.

```bash
llvm-readelf -S -W art33-sdk/libart.so | grep -E ' \.(dynsym|symtab|gnu_debugdata) '
llvm-nm -D -C art33-sdk/libart.so | grep -c RegisterNatives
llvm-nm -C art33-sdk/libart.so | grep RegisterNatives
llvm-nm -C art9/libart.so | grep RegisterNatives
```

![API 33 libart.so의 llvm-readelf 결과에 .dynsym과 .symtab이 있고, llvm-nm -D -C 로 RegisterNatives를 센 값은 0이다. llvm-nm -C 에는 로컬 t 심볼로 615ab0 CheckJNI::RegisterNatives(.llvm.6973224403690363785 접미사), 69ca80 art::JNI false 판, 7074f0 art::JNI true 판이 나오고, Android 9 libart에는 CheckJNI 판과 템플릿 없는 art::JNI::RegisterNatives만 있다](/assets/img/android-mastery/p1c10/02-libart-registernatives-symbols.png)

`.dynsym`에서 이름에 RegisterNatives가 들어간 심볼은 0개다. `.symtab`에는 소문자 `t`, 곧 로컬 함수로 `art::(anonymous namespace)::CheckJNI::RegisterNatives`(0x615ab0), `art::JNI<false>::RegisterNatives`(0x69ca80), `art::JNI<true>::RegisterNatives`(0x7074f0)가 있다. 동적 링커가 보는 export 표에 아예 없으니 맹글된 이름을 그대로 넣어도 export 조회는 실패한다. 구현도 하나가 아니다. ART의 `JNI` 클래스는 [jni_internal.cc L657-658](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/jni_internal.cc#657)에서 `template <bool kEnableIndexIds>`로 선언돼 두 벌이 생기고, CheckJNI가 그 앞을 감싸는 판을 하나 더 둔다. Android 9 이미지(API 28 x86)의 libart에는 템플릿 없는 `art::JNI::RegisterNatives`와 CheckJNI 판만 있다. 소스로 보면 [android-10.0.0_r1 L643](https://android.googlesource.com/platform/art/+/refs/tags/android-10.0.0_r1/runtime/jni/jni_internal.cc#643)까지 평범한 `class JNI`였고 [android-11.0.0_r1 L481-482](https://android.googlesource.com/platform/art/+/refs/tags/android-11.0.0_r1/runtime/jni/jni_internal.cc#481)에서 템플릿이 됐다. CheckJNI 판 이름 끝의 `.llvm.6973224403690363785`는 컴파일러가 로컬 함수에 붙인 접미사라 빌드가 바뀌면 같이 바뀐다. `.symtab` 자체도 이 에뮬레이터 이미지가 남겨 둔 것이어서 다른 이미지에 있다는 보장이 없다. 뒤에서 API 36 이미지로 따로 확인했다.

스크립트를 쓰기 전에 Frida 버전도 짚어 둔다. Frida 17에서는 `Module.findExportByName()`, `Module.getExportByName()` 같은 정적 Module 메서드가 빠졌다([17.0.0 릴리스 노트](https://frida.re/news/2025/05/17/frida-17-0-0-released/)의 Static Module APIs 절). 전역 export는 `Module.getGlobalExportByName(name)`으로 찾고, 특정 모듈은 `Process.getModuleByName('libart.so')`로 모듈 객체를 받은 뒤 그 객체의 `findExportByName`, `enumerateExports`, `enumerateSymbols`를 부른다. 호스트의 Frida 17.17.0에서 `typeof`로 확인해 보니 `Module.getExportByName`, `Module.findExportByName`, `Module.enumerateSymbols`, `Memory.readByteArray`, `Memory.hexdump`는 모두 `undefined`였고 `hexdump`는 전역 함수로 있었다. 아래 스크립트는 전부 이 API로 썼다.

## 215번 칸을 읽어 등록 순간을 잡는다

후크를 걸 주소는 libart의 심볼 표에서 찾을 수도 있고, 심볼 없이 JNIEnv 함수 표에서 읽을 수도 있다. C에서 `JNIEnv*`는 함수 표 포인터를 가리키는 포인터라서 `(*env)->RegisterNatives(...)`는 `*env`가 가리키는 표의 215번 칸을 부른다. ART가 채운 표에서도 [jni_internal.cc L3240](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/jni_internal.cc#3240)의 `JNIImpl::RegisterNatives`가 맨 앞 `reserved0`을 0번으로 세어 215번 자리다. 등록을 하려는 스레드의 이 칸을 읽으면 그 스레드가 실제로 부를 함수가 나온다.

`regnatives.js`는 두 방법을 함께 쓴다. 이름에 `RegisterNatives`가 들어간 libart 함수 심볼을 모두 걸고, 스크립트가 로드될 때 Frida 스레드의 215번 칸과, `libjnimap.so`가 막 로드된 직후 그 로드를 한 스레드의 215번 칸도 읽어 건다. 뒤의 스레드가 곧바로 `JNI_OnLoad`를 부를 스레드다. 같은 주소는 한 번만 건다. 등록 호출이 들어오면 세 번째 인자의 표를 24바이트씩 걸어가며 이름, 시그니처, 함수 주소를 읽고, 주소를 `모듈+오프셋`으로 바꿔 찍는다. CheckJNI 판이 안쪽 구현을 다시 부르는 경우는 깊이로 구분해 한 줄만 남긴다.

```javascript
// frida/regnatives.js
// Hook ART's RegisterNatives to map Java native methods to C function addresses,
// even when the library that registers them is stripped. Frida 17 API.
// Two ways to find RegisterNatives: libart's symbol table (enumerateSymbols), and,
// without any symbol, slot 215 of the JNIEnv function table of the calling thread.
// usage: frida -D $S -f io.seika.jnimap -l frida/regnatives.js -q -t 6
const WATCH = 'libjnimap.so';            // print method tables only for this library
const P = Process.pointerSize;
const art = Process.getModuleByName('libart.so');
const hooked = new Map();                // address -> label
const depth = {};                        // threadId -> nesting level inside RegisterNatives

// mangled -> readable, only for the three forms that exist in libart (Android 11+)
const pretty = n => n.includes('CheckJNI') ? 'art::CheckJNI::RegisterNatives'
  : n.includes('JNIILb0E') ? 'art::JNI<false>::RegisterNatives'
  : n.includes('JNIILb1E') ? 'art::JNI<true>::RegisterNatives' : n;
const describe = a => {
  const m = Process.findModuleByAddress(a);
  const s = DebugSymbol.fromAddress(a).name;
  return (m ? `${m.name}+0x${a.sub(m.base).toString(16)}` : `${a}`) + (s ? ` (${pretty(s)})` : '');
};
const slot215 = env => env.readPointer().add(215 * P).readPointer();   // env = JNIEnv*

console.log(`[libart] ${art.path} base=${art.base}`);
console.log(`[export] findExportByName('RegisterNatives') -> ${art.findExportByName('RegisterNatives')}`);
console.log(`[export] exports containing 'RegisterNatives': ${art.enumerateExports().filter(e => e.name.includes('RegisterNatives')).length}`);
const cands = art.enumerateSymbols().filter(s => s.type === 'function' && s.name.includes('RegisterNatives'));
console.log(`[symbol] enumerateSymbols(): ${cands.length} function symbols contain 'RegisterNatives'`);
for (const s of cands) {
  console.log(`[symbol] ${s.isGlobal ? 'global' : 'local'} libart+0x${s.address.sub(art.base).toString(16)} ${s.name}`);
  hook(s.address, pretty(s.name));
}

// symbol-free route, at script load: this (Frida) thread's table
try {
  Java.performNow(() => {
    const fn = slot215(Java.vm.getEnv().handle);
    console.log(`[slot 215] at script load, Frida thread: ${fn} ${describe(fn)}`);
    hook(fn, `slot 215 target ${describe(fn)}`);
  });
} catch (e) {
  console.log(`[slot 215] at script load: ${e.message}`);
}
// ... and when the watched library is loaded, the loading thread's table (the one JNI_OnLoad will use)
Interceptor.attach(Process.getModuleByName('libdl.so').getExportByName('android_dlopen_ext'), {
  onEnter(a) { this.path = a[0].isNull() ? null : a[0].readCString(); },
  onLeave() {
    if (this.path === null || !this.path.endsWith('/' + WATCH)) return;
    const env = Java.vm.tryGetEnv();
    if (env === null) return;
    const fn = slot215(env.handle);
    console.log(`[slot 215] ${WATCH} just loaded, loading thread: ${fn} ${describe(fn)}`);
    hook(fn, `slot 215 target ${describe(fn)}`);
  }
});

function hook(addr, label) {
  if (hooked.has(addr.toString())) return;
  hooked.set(addr.toString(), label);
  Interceptor.attach(addr, {
    onEnter(args) {
      const t = this.threadId;
      this.d = depth[t] = (depth[t] || 0) + 1;
      const n = args[3].toInt32();
      const list = [];
      for (let i = 0; i < n; i++) {
        const e = args[2].add(i * 3 * P);       // JNINativeMethod {name, signature, fnPtr}
        list.push({ name: e.readPointer().readCString(), sig: e.add(P).readPointer().readCString(), fn: e.add(2 * P).readPointer() });
      }
      const mod = n > 0 ? Process.findModuleByAddress(list[0].fn) : null;
      this.show = mod !== null && mod.name === WATCH;
      if (!this.show) {
        if (this.d === 1) console.log(`[RegisterNatives] ${label} n=${n} fnPtr in ${mod ? mod.name : '?'} (not shown)`);
        return;
      }
      if (this.d > 1) {
        console.log(`  -> ${label} (called from inside the outer RegisterNatives, depth ${this.d})`);
        return;
      }
      const slot = slot215(args[0]);
      let cls = `${args[1]}`;
      try { cls = Java.vm.tryGetEnv().getClassName(args[1]); } catch (e) { cls += ` (${e.message})`; }
      console.log(`[RegisterNatives] ${label} class=${cls} n=${n}`);
      console.log(`  caller JNIEnv->functions[215] = ${slot} ${hooked.get(slot.toString()) || describe(slot)}`);
      for (const m of list) {
        const mm = Process.findModuleByAddress(m.fn);
        console.log(`  ${m.name} ${m.sig} -> ${m.fn} = ${mm.name}+0x${m.fn.sub(mm.base).toString(16)}  DebugSymbol: ${DebugSymbol.fromAddress(m.fn)}`);
      }
    },
    onLeave(ret) {
      depth[this.threadId]--;
      if (this.show && this.d === 1) console.log(`[RegisterNatives] ${label} returned ${ret.toInt32()}`);
    }
  });
}
console.log(`[hook] RegisterNatives hooks: ${hooked.size}`);
```

`JNI_OnLoad`는 라이브러리가 로드될 때 한 번 돌고 끝나므로 Frida가 앱을 직접 띄우는 spawn(`-f`)으로 실행했다. `-q`는 REPL 없이 스크립트 출력만 내고 `-t 6`은 6초 뒤에 끝낸다.

```bash
adb -s $S shell am force-stop io.seika.jnimap
frida -D $S -f io.seika.jnimap -l frida/regnatives.js -q -t 6
```

![spawn으로 regnatives.js를 올린 터미널. findExportByName('RegisterNatives') -> null, export 0개, enumerateSymbols 3개(local libart+0x615ab0 CheckJNI, +0x69ca80 JNIILb0E, +0x7074f0 JNIILb1E), slot 215는 Frida 스레드와 로딩 스레드 모두 libart.so+0x69ca80 art::JNI false 판이다. libframework-connectivity-jni.so의 n=12 등록이 먼저 지나가고, class=io.seika.jnimap.Native n=3 등록에서 nativeCheck → libjnimap.so+0x19f0, nativeMix → +0x1a90, nativeRebind → +0x1aa0, DebugSymbol은 libjnimap.so!0x19f0 식으로 찍히고 returned 0](/assets/img/android-mastery/p1c10/03-registernatives-spawn.png)

`findExportByName('RegisterNatives')`는 null이고 export 목록에도 없다. `enumerateSymbols()`는 `.symtab`의 로컬 심볼 세 개를 돌려줬다. 215번 칸은 두 시점 모두 libart+0x69ca80, `art::JNI<false>::RegisterNatives`를 가리켰다. 심볼로 이미 건 주소라서 후크 수는 3에서 늘지 않았다. 앱을 재개하자 프레임워크 쪽 `libframework-connectivity-jni.so`가 메서드 12개를 등록하는 호출이 먼저 지나갔고, 이어서 `io.seika.jnimap.Native`에 대한 `n=3` 등록이 잡혔다.

`nativeCheck`는 `libjnimap.so+0x19f0`, `nativeMix`는 `+0x1a90`, `nativeRebind`는 `+0x1aa0`이다. 스트립하지 않은 빌드의 `verify_guess`, `mix_int`, `rebind` 주소와 그대로 맞는다. `DebugSymbol`은 이 주소들을 `libjnimap.so!0x19f0`처럼 모듈과 오프셋으로만 적었고, objdump처럼 앞 심볼에 갖다 붙이지 않았다. `nativeHello`는 출력 어디에도 없다. 등록 표에 들어 있지 않은 메서드라서 그렇고, 이 메서드가 언제 연결되는지는 뒤에서 따로 본다.

## 찾은 오프셋에 붙어 JNI 인자 읽기

오프셋을 알았으니 앱이 떠 있는 상태에서 붙는다. `natives.js`는 `libjnimap.so` 베이스에 0x19f0과 0x1a90을 더한 주소에 `Interceptor.attach`를 건다. JNI 네이티브 함수의 모양은 명세대로 `(JNIEnv *env, jobject objectOrClass, ...)`이다. `args[0]`은 JNIEnv*, `args[1]`은 인스턴스 메서드면 `this`, static 메서드면 그 클래스, 그 뒤로 Java 인자가 온다. `jstring`은 문자 배열을 가리키는 포인터가 아닌 참조라서 `Java.vm.tryGetEnv()`로 얻은 env의 `stringFromJni`로 풀었다. `*env`가 가리키는 표에는 libart의 객체 심볼과 대조해 이름을 붙였다. `strcmp@plt` 후크는 다음 절에서 따로 다룬다.

```javascript
// frida/natives.js
// Attach to the two stripped functions by the offsets that regnatives.js printed,
// and look at JNI arguments, return values and the strcmp inside nativeCheck. Frida 17 API.
// usage (app already running): frida -D $S -N io.seika.jnimap -l frida/natives.js -q -t 8
const OFF_CHECK = 0x19f0;   // nativeCheck (Ljava/lang/String;)Z
const OFF_MIX = 0x1a90;     // nativeMix (I)I
const lib = Process.getModuleByName('libjnimap.so');
const art = Process.getModuleByName('libart.so');

const tables = new Map(art.enumerateSymbols()
  .filter(s => s.type === 'object' && s.name.includes('NativeInterface'))
  .map(s => [s.address.toString(), s.name.includes('ILb0E') ? 'JniNativeInterfaceFunctions<false>::gJniNativeInterface'
    : s.name.includes('ILb1E') ? 'JniNativeInterfaceFunctions<true>::gJniNativeInterface'
    : s.name.includes('gCheckNativeInterface') ? 'gCheckNativeInterface' : s.name]));
const envDesc = env => { const t = env.readPointer(); return `JNIEnv*=${env} (*env=${t} ${tables.get(t.toString()) || '?'})`; };

console.log(`[lib] ${lib.name} base=${lib.base}  nativeCheck=${lib.base.add(OFF_CHECK)}  nativeMix=${lib.base.add(OFF_MIX)}`);

Interceptor.attach(lib.base.add(OFF_CHECK), {
  onEnter(args) {
    const env = Java.vm.tryGetEnv();
    console.log(`[nativeCheck] onEnter ${envDesc(args[0])}`);
    console.log(`  args[1] jobject this=${args[1]} (${env.getObjectClassName(args[1])})  args[2] jstring=${args[2]} -> "${env.stringFromJni(args[2])}"`);
  },
  onLeave(ret) {
    console.log(`[nativeCheck] onLeave ret=${ret} -> jboolean ${ret.toInt32() & 0xff}`);
  }
});

Interceptor.attach(lib.base.add(OFF_MIX), {
  onEnter(args) {
    const env = Java.vm.tryGetEnv();
    console.log(`[nativeMix] onEnter args[1] jclass=${args[1]} (${env.getClassName(args[1])})  args[2] jint=${args[2].toInt32()}`);
  },
  onLeave(ret) { console.log(`[nativeMix] onLeave ret=${ret.toInt32()}`); }
});

// strcmp as seen from libjnimap only. Attaching to its PLT stub (llvm-objdump: callq 0x1b30 <strcmp@plt>)
// is not enough: Frida follows the stub's jmp and patches libc strcmp itself, so every strcmp in the
// process hits this hook. Keep only calls whose return address is inside libjnimap.so.
const OFF_STRCMP_PLT = 0x1b30;
const fromLib = p => p.compare(lib.base) >= 0 && p.compare(lib.base.add(lib.size)) < 0;
Interceptor.attach(lib.base.add(OFF_STRCMP_PLT), {
  onEnter(args) {
    if (!fromLib(this.returnAddress)) return;
    console.log(`[strcmp@plt] from ${lib.name}+0x${this.returnAddress.sub(lib.base).toString(16)}  a="${args[0].readCString()}"  b="${args[1].readCString()}"`);
    console.log(hexdump(args[1], { length: 16, header: false, ansi: false }));
  }
});
```

Java 쪽에서 같은 호출을 나란히 보려고 8장 방식의 후크도 함께 올렸다.

```javascript
// frida/java-side.js
// Java-side view of the same calls (chapter 8 style), to line up with natives.js output.
// usage: frida -D $S -N io.seika.jnimap -l frida/natives.js -l frida/java-side.js -q -t 8
Java.perform(() => {
  const Native = Java.use('io.seika.jnimap.Native');
  Native.nativeCheck.implementation = function (guess) {
    console.log(`[java] Native.nativeCheck("${guess}") called`);
    const r = this.nativeCheck(guess);
    console.log(`[java] Native.nativeCheck returned ${r}`);
    return r;
  };
  console.log('[java] hooked io.seika.jnimap.Native.nativeCheck');
});
```

`-N`은 패키지 이름으로 실행 중인 앱에 붙는다. 앱을 먼저 띄워 두고, 6초 뒤에 `guess=letmein`, `n=7`을 담은 인텐트가 같은 액티비티로 가게 했다.

```bash
adb -s $S shell am start -W -n io.seika.jnimap/.MainActivity
(sleep 6; adb -s $S shell am start -n io.seika.jnimap/.MainActivity --es guess letmein --ei n 7 >/dev/null) & \
frida -D $S -N io.seika.jnimap -l frida/natives.js -l frida/java-side.js -q -t 12
```

![natives.js와 java-side.js를 attach한 터미널. libjnimap.so base=0x730b8bf63000, Java 후크의 Native.nativeCheck("letmein") called 뒤에 nativeCheck onEnter JNIEnv 포인터 0x730cd116f8d0, 그 표 0x730c0a58d358은 JniNativeInterfaceFunctions false 판 gJniNativeInterface, 두 번째 인자 jobject this는 io.seika.jnimap.Native, 세 번째 인자 jstring은 "letmein", strcmp@plt는 libjnimap.so+0x1a55에서 a="letmein" b="SEIKA-JNI-1025"로 불리고 hexdump 53 45 49 4b 41 2d 4a 4e 49 2d 31 30 32 35, onLeave jboolean 0, Java 쪽 returned false, nativeMix는 jclass io.seika.jnimap.Native와 jint=7을 받아 ret=4348](/assets/img/android-mastery/p1c10/04-native-args-attach.png)

Java 후크의 `called` 줄과 `returned false` 줄 사이에 네이티브 쪽 줄이 끼어 경계를 넘나드는 순서가 그대로 보인다. `args[0]`의 JNIEnv*가 가리키는 표는 0x730c0a58d358로, libart 베이스 0x730c09a00000에서 +0xb8d358에 있는 `JniNativeInterfaceFunctions<false>::gJniNativeInterface`다. 등록 때 215번 칸이 `JNI<false>` 구현을 가리킨 것과 같은 표다.

`nativeCheck`의 `args[1]`은 `io.seika.jnimap.Native` 인스턴스, `args[2]`는 jstring이고 풀면 `"letmein"`이다. 이 둘의 값은 0x7ffc2b3cef48과 0x7ffc2b3cef4c로 스택 주소에 4바이트 간격이었고, static 메서드 `nativeMix`의 jclass는 0x730eb8b77648로 다른 영역에 있었다. ART가 네이티브 호출 직전에 참조를 스택 칸에 늘어놓고 그 칸의 주소를 넘기는 것으로 보이는데, 소스까지 따라가 확인하지는 않았다. 어느 쪽이든 args에 든 값은 참조라서 `args[2].toInt32()`처럼 정수로 읽으면 참조 값의 하위 32비트가 나올 뿐이다.

`strcmp@plt` 줄의 반환 주소 `libjnimap.so+0x1a55`는 정적 분석에서 본 0x1a50 `callq 0x1b30 <strcmp@plt>` 바로 다음 명령이다. 비교 상대 `b`는 `SEIKA-JNI-1025`였다. 파일에는 XOR된 바이트만 있었지만 비교하는 순간에는 스택에 평문으로 풀려 있고, hexdump에도 `53 45 49 4b …`로 찍혔다. 반환값은 0, Java로는 `false`가 돌아갔다. `nativeMix`는 `args[1]`이 클래스이고 `args[2]`가 jint 7, 반환은 4348로 (7×31) XOR 0x1025와 맞다.

처음에는 인텐트를 `sleep 3` 뒤에 보냈는데 `[lib]`와 `[java] hooked` 두 줄만 나오고 호출은 하나도 잡히지 않았다. `am start`가 남기는 `Warning: Activity not started, intent has been delivered…` 줄이 `[lib]` 줄보다 먼저 찍혀 있었다. 호스트에서 시간을 재 보니 frida를 띄운 뒤 `[lib]`까지 2.8초, `[java] hooked`까지 3.0초가 걸렸다(`natives.js`가 libart 심볼을 훑는 시간도 여기 들어 있다). 인텐트가 후크보다 먼저 도착한 것이다. 6초로 늘리고 위 출력을 얻었다.

## strcmp@plt에 건 후크는 libc의 strcmp를 고친다

`natives.js`의 `strcmp@plt` 후크에는 반환 주소가 `libjnimap.so` 안인 호출만 찍는 필터가 붙어 있다. PLT 칸에 걸면 이 라이브러리가 부르는 `strcmp`만 걸릴 거라고 생각하고 필터 없이 돌렸더니 `a="all_codenames"  b="release"`처럼 이 라이브러리와 상관없는 비교가 줄줄이 찍혔다. 후크가 실제로 어디를 고치는지 바이트로 확인했다.

```javascript
// frida/pltcheck.js
// Where does Interceptor.attach(libjnimap.so+0x1b30 = strcmp@plt) actually patch?
const lib = Process.getModuleByName('libjnimap.so');
const plt = lib.base.add(0x1b30);
const libcStrcmp = Process.getModuleByName('libc.so').getExportByName('strcmp');
const got = plt.add(6).add(plt.add(2).readS32());   // jmpq *disp32(%rip)
const show = (tag, p) => console.log(`${tag} ${p}  ${hexdump(p, { length: 8, header: false, ansi: false }).split('  ')[1]}`);
console.log(`[plt] strcmp@plt=${plt}  GOT slot=${got} -> ${got.readPointer()}  libc strcmp=${libcStrcmp}`);
show('[before] plt        ', plt); show('[before] libc strcmp', libcStrcmp);
const l = Interceptor.attach(plt, { onEnter() {} });
show('[after]  plt        ', plt); show('[after]  libc strcmp', libcStrcmp);
l.detach();
```

```bash
frida -D $S -N io.seika.jnimap -l frida/pltcheck.js -q -t 1
```

![pltcheck.js 출력. strcmp@plt=0x730b8bf64b30의 GOT 칸 0x730b8bf65d60이 libc strcmp 0x730eb52c21e0을 가리킨다. 후크 전후 PLT 바이트는 ff 25 2a 12 00 00 68 04로 같고, libc strcmp 첫 바이트는 89 f1 89 f8 48 83 e1 3f에서 e9 23 06 1b 0c 0f 1f 00으로 바뀌었다](/assets/img/android-mastery/p1c10/04b-plt-hook-patches-libc.png)

PLT의 `ff 25 2a 12 00 00`은 `jmp *0x122a(%rip)`이고, 그 GOT 칸(0x730b8bf65d60)에는 이미 libc `strcmp` 주소가 들어 있다. bionic 링커는 lazy binding을 하지 않아서 로드할 때 GOT를 다 채운다([linker.cpp L2903-2904](https://android.googlesource.com/platform/bionic/+/refs/tags/android-13.0.0_r84/linker/linker.cpp#2903)는 `RTLD_LAZY`를 지원하지 않는다며 `DT_PLTGOT`을 무시한다). 후크를 건 뒤에도 PLT 바이트는 그대로였고 바뀐 건 libc `strcmp`의 첫 바이트였다. `89 f1 89 f8 …`이 `e9`로 시작하는 `jmp rel32`로 덮였다. Frida가 PLT의 간접 점프를 따라가 최종 목적지 함수에 인라인 후크를 박은 것이다.

그러니 이 후크는 프로세스 안의 모든 `strcmp`에서 불린다. 인텐트 하나를 처리하는 동안 호출자 모듈별로 세어 보니 libart.so에서 179번, libjnimap.so에서 1번이었다. 필터가 없으면 이 180줄 가운데 비밀값이 든 한 줄을 골라내야 한다.

## 반환값을 바꾸자 locked가 UNLOCKED로 바뀌었다

틀린 입력부터 넣었다. `--es guess letmein`으로 띄우면 화면에 `nativeCheck("letmein") = false`와 `locked`가 뜬다.

![후크 전 에뮬레이터 화면. JniMap 앱에 JniMap (io.seika.jnimap), nativeCheck("letmein") = false, nativeMix(42) = 5427, nativeHello() = (not called), nativeRebind() = (not called), 그 아래 locked가 떠 있다](/assets/img/android-mastery/p1c10/07a-locked-screen.png)

그 상태에서 `nativeCheck`의 반환을 1로 바꾸는 스크립트를 붙이고 같은 인텐트를 다시 보냈다.

```javascript
// frida/flip.js
// Force nativeCheck's jboolean result to 1 at the native return.
// usage: frida -D $S -N io.seika.jnimap -l frida/flip.js -q -t 8   (then send a wrong guess)
const lib = Process.getModuleByName('libjnimap.so');
Interceptor.attach(lib.base.add(0x19f0), {
  onLeave(ret) {
    console.log(`[flip] nativeCheck returned ${ret.toInt32() & 0xff}, replacing with 1`);
    ret.replace(ptr(1));
  }
});
console.log(`[flip] attached to ${lib.name}+0x19f0`);
```

```bash
adb -s $S shell am start -W -n io.seika.jnimap/.MainActivity --es guess letmein
(sleep 5; adb -s $S shell am start -n io.seika.jnimap/.MainActivity --es guess letmein >/dev/null) & \
frida -D $S -N io.seika.jnimap -l frida/flip.js -q -t 9
```

```
[flip] attached to libjnimap.so+0x19f0
[flip] nativeCheck returned 0, replacing with 1
Warning: Activity not started, intent has been delivered to currently running top-most instance.
```

logcat의 `JniMap` 태그에는 후크 전후가 이렇게 남았다.

```
10-15 11:35:23.297  5011  5011 I JniMap  : JniMap (io.seika.jnimap)  nativeCheck("letmein") = false nativeMix(42) = 5427 nativeHello() = (not called) nativeRebind() = (not called)  locked
10-15 11:35:28.555  5011  5011 I JniMap  : JniMap (io.seika.jnimap)  nativeCheck("letmein") = true nativeMix(42) = 5427 nativeHello() = (not called) nativeRebind() = (not called)  UNLOCKED
```

![후크 뒤 에뮬레이터 화면. JniMap 앱에 JniMap (io.seika.jnimap), nativeCheck("letmein") = true, nativeMix(42) = 5427, nativeHello() = (not called), nativeRebind() = (not called), 그 아래 UNLOCKED가 떠 있다](/assets/img/android-mastery/p1c10/07-flip-unlocked-screen.png)

입력은 여전히 `letmein`이고 네이티브 함수는 비교에 실패해 0을 돌려줬다. 바뀐 건 x86_64에서 반환값이 실려 나가는 `rax` 하나이고, 앱은 그 값을 보고 `UNLOCKED`를 띄웠다.

## JNI_OnLoad와 Java_ export는 dlsym으로 찾는다

등록 표에 없는 `nativeHello`는 언제 연결될까. 라이브러리 로드부터 따라가려고 `android_dlopen_ext`, `dlsym`, `JNI_OnLoad`를 거는 스크립트를 썼다. Frida 17에서 옛 정적 호출이 기기에서 어떻게 끝나는지도 같은 화면에서 먼저 확인했다.

```javascript
// frida/loadtrace.js
// When does ART touch libjnimap? dlopen, the JNI_OnLoad lookup and call, and the dlsym lookups
// it makes later for Java_* exports. Frida 17 API.
// usage: frida -D $S -f io.seika.jnimap -l frida/loadtrace.js -q -t 14
const libdl = Process.getModuleByName('libdl.so');
const where = p => {
  const m = Process.findModuleByAddress(p);
  const n = DebugSymbol.fromAddress(p).name;
  return (m ? `${m.name}+0x${p.sub(m.base).toString(16)}` : `${p}`) + (n ? ` (${n})` : '');
};
let handle = null;

Interceptor.attach(libdl.getExportByName('android_dlopen_ext'), {
  onEnter(a) { this.path = a[0].isNull() ? null : a[0].readCString(); this.ra = this.returnAddress; },
  onLeave(h) {
    if (this.path === null || !this.path.includes('libjnimap.so')) return;
    this.caller = where(this.ra);
    handle = ptr(h.toString());   // copy: Frida reuses the retval object after onLeave returns
    const lib = Process.findModuleByName('libjnimap.so') || Process.enumerateModules().find(m => m.name === 'libjnimap.so');
    console.log(`[android_dlopen_ext] ${this.path}`);
    console.log(`  caller ${this.caller}  handle=${h}  libjnimap.so base=${lib.base}`);
    Interceptor.attach(lib.getExportByName('JNI_OnLoad'), {
      onEnter(a) { console.log(`[JNI_OnLoad] enter JavaVM*=${a[0]} caller ${where(this.returnAddress)}`); },
      onLeave(r) { console.log(`[JNI_OnLoad] returned 0x${r.toUInt32().toString(16)}`); }
    });
    setTimeout(hookJava, 0);      // MainActivity is initialized by now (we are inside its onCreate)
  }
});

Interceptor.attach(libdl.getExportByName('dlsym'), {
  onEnter(a) {
    if (handle === null || !a[0].equals(handle)) return;
    this.name = a[1].readCString();
    this.caller = where(this.returnAddress);
  },
  onLeave(r) { if (this.name !== undefined) console.log(`[dlsym] ${this.name} -> ${r}  caller ${this.caller}`); }
});

// Java-side marker for each `am start`. Installed only after libjnimap is loaded: a hook placed
// right at spawn, before MainActivity was initialized, never fired on this image.
function hookJava() {
  Java.perform(() => {
    const A = Java.use('io.seika.jnimap.MainActivity');
    A.onNewIntent.implementation = function (i) {
      console.log(`[java] onNewIntent hello=${i.getBooleanExtra('hello', false)}`);
      return this.onNewIntent(i);
    };
  });
}
console.log('[loadtrace] hooks installed');
```

```bash
frida -D $S -N io.seika.jnimap -q -e "Module.getExportByName(null, 'android_dlopen_ext')"
frida -D $S -N io.seika.jnimap -q -e "Module.getGlobalExportByName('android_dlopen_ext')"
adb -s $S shell am force-stop io.seika.jnimap
(sleep 8; adb -s $S shell am start -n io.seika.jnimap/.MainActivity --ez hello true >/dev/null; \
 sleep 2; adb -s $S shell am start -n io.seika.jnimap/.MainActivity --ez hello true >/dev/null) & \
frida -D $S -f io.seika.jnimap -l frida/loadtrace.js -q -t 14
```

![로드 추적 터미널. Module.getExportByName(null, 'android_dlopen_ext')는 TypeError: not a function, at eval (input:1)로 끝나고 getGlobalExportByName은 "0x730ea36b2bd0"을 돌려준다. spawn 뒤 android_dlopen_ext가 libjnimap.so를 libnativeloader.so+0x204bc (NativeLoaderNamespace::Load+0xbc)에서 열고, dlsym JNI_OnLoad -> 0x730ba5a75960 (호출자 SharedLibrary::FindSymbolWithoutNativeBridge+0x3e), JNI_OnLoad는 JavaVMExt::LoadNativeLibrary+0xe89에서 불려 0x10006을 돌려준다. 첫 onNewIntent hello=true 뒤에만 dlsym Java_io_seika_jnimap_Native_nativeHello -> 0x730ba5a75940이 찍히고 두 번째 onNewIntent 뒤에는 dlsym 줄이 없다](/assets/img/android-mastery/p1c10/05-loadtrace.png)

옛 호출 `Module.getExportByName(null, ...)`은 `TypeError: not a function`으로 끝났고 `Module.getGlobalExportByName`은 주소를 돌려줬다. Frida 16 시절 예제를 그대로 가져오면 이 줄에서 멈춘다.

spawn 쪽 출력은 로드 순서를 그대로 보여 준다. `libjnimap.so`를 연 `android_dlopen_ext`의 호출자는 `libnativeloader.so`의 `android::NativeLoaderNamespace::Load`였다. 이 함수는 [native_loader_namespace.cpp L162-168](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/libnativeloader/native_loader_namespace.cpp#162)에서 앱의 링커 네임스페이스를 지정해 `RTLD_NOW`로 연다. 이어서 같은 핸들로 `dlsym(handle, "JNI_OnLoad")`가 불렸고 결과의 끝자리 960이 정적 분석의 0x1960과 맞는다. 호출자는 `art::SharedLibrary::FindSymbolWithoutNativeBridge`로, [java_vm_ext.cc L164-177](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/java_vm_ext.cc#164)에서 `dlsym(handle_, symbol_name.c_str())`을 부르는 그 함수다. `JNI_OnLoad`는 `art::JavaVMExt::LoadNativeLibrary`에서 불렸고([java_vm_ext.cc L1093-1108](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/java_vm_ext.cc#1093)) `JNI_VERSION_1_6`인 0x10006을 돌려줬다. 출력의 맹글된 이름은 `llvm-cxxfilt`로 풀어 확인했다.

`nativeHello`는 첫 `hello=true` 인텐트에서 처음 불릴 때 `dlsym(handle, "Java_io_seika_jnimap_Native_nativeHello")`로 찾아졌고(끝자리 940), 두 번째 인텐트에서는 dlsym 줄이 없었다. `nativeCheck`나 `nativeMix`로는 dlsym이 한 번도 불리지 않았다. ART는 네이티브 메서드의 진입점을 처음에 dlsym 조회 스텁으로 걸어 둔다([class_linker.cc L3454-3459](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/class_linker.cc#3454)). 처음 불리면 `artFindNativeMethodRunnable`이 `FindCodeForNativeMethod`로 주소를 찾고([jni_entrypoints.cc L114](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/entrypoints/jni/jni_entrypoints.cc#114)), 짧은 이름과 시그니처가 붙은 긴 이름을 차례로 `FindSymbol`에 넣어 본다([java_vm_ext.cc L327-332](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/java_vm_ext.cc#327)). 찾은 주소는 `class_linker->RegisterNative`로 메서드에 기록되고(L124), 다음 호출부터는 스텁을 거치지 않는다. 처음 쓸 때 찾는다는 점에서 lazy binding처럼 보이지만 ELF의 lazy binding과는 관계가 없다. bionic은 앞에서 본 대로 lazy binding 자체를 지원하지 않는다.

그래서 `Java_` export 방식의 메서드는 `RegisterNatives`를 한 번도 지나지 않고, `RegisterNatives` 후크로는 보이지 않는다. 그런 메서드의 이름과 주소는 `dlsym` 후크나 동적 심볼 표에서 얻는다. 두 길은 ART 안의 `ClassLinker::RegisterNative`에서 만난다([jni_internal.cc L2688](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/jni_internal.cc#2688)과 jni_entrypoints.cc L124). API 33 libart에서는 이 함수가 `_ZN3art11ClassLinker14RegisterNativeEPNS_6ThreadEPNS_9ArtMethodEPKv`로 `.dynsym`에까지 올라 있어 한곳에서 둘 다 볼 자리로 보이지만, 이번에는 걸어 보지 않았다. API 36 libart의 `.dynsym`에는 없다.

이 출력이 처음부터 나온 건 아니다. 첫 판의 `loadtrace.js`는 dlopen과 `JNI_OnLoad` 줄만 찍고 `[dlsym]`도 `[java]`도 내지 않았다. logcat에는 `nativeHello() = hi from Java_ export`가 남았는데도 그랬다. 먼저 onLeave에서 받은 `retval` 객체를 `handle = h`로 그대로 저장한 게 문제였다. 콜백이 끝난 뒤 그 객체를 다시 읽으면 0x0이 나왔고, 그래서 dlsym 필터가 어떤 핸들과도 맞지 않았다. Frida가 retval 객체를 콜백 뒤에 다시 쓰는 것으로 보여 `ptr(h.toString())`으로 값을 복사해 두게 고쳤다. spawn 직후에 건 `MainActivity.onNewIntent` Java 후크도 "hooked"까지 찍고는 한 번도 불리지 않았다. 4초 뒤에 건 후크는 불렸기 때문에, `libjnimap.so`의 dlopen이 끝나는 시점(액티비티의 onCreate 안)에 `setTimeout`으로 후크를 걸게 바꿨다. 이른 후크가 왜 사라지는지는 더 파고들지 않았다.

## debuggable 앱에서는 215번 칸이 CheckJNI다

같은 코드를 debuggable로만 바꾼 `io.seika.jnimapdbg`에 같은 스크립트를 돌렸다. 시스템 속성으로 CheckJNI가 켜져 있는지도 함께 봤다. 마지막 줄은 앞의 실험에서 띄운 `io.seika.jnimap`이 떠 있는 상태에서 그 프로세스의 로그를 센다.

```bash
adb -s $S shell getprop | grep -i checkjni
adb -s $S shell am force-stop io.seika.jnimapdbg
frida -D $S -f io.seika.jnimapdbg -l frida/regnatives.js -q -t 6 | grep -v -E '^\[(symbol|export|libart)\]'
adb -s $S logcat -d --pid=$(adb -s $S shell pidof io.seika.jnimapdbg) | grep -i 'check:jni'
adb -s $S logcat -d --pid=$(adb -s $S shell pidof io.seika.jnimap) | grep -c -i 'check:jni'
```

![debuggable 쌍둥이 앱 터미널. getprop에서 checkjni 속성은 아무것도 나오지 않는다. io.seika.jnimapdbg를 spawn하자 slot 215가 Frida 스레드와 로딩 스레드 모두 libart.so+0x615ab0 art::CheckJNI::RegisterNatives이고, class=io.seika.jnimap.Native n=3 등록이 같은 +0x19f0·+0x1a90·+0x1aa0으로 매핑된 뒤 안쪽에서 art::JNI true 판 RegisterNatives가 depth 2로 불리고 returned 0. logcat에는 I seika.jnimapdbg: Late-enabling -Xcheck:jni 한 줄, io.seika.jnimap 쪽 개수는 0](/assets/img/android-mastery/p1c10/06-checkjni-debuggable.png)

`getprop`에서 checkjni가 들어간 속성은 하나도 나오지 않았다. 그런데도 debuggable 앱에서는 215번 칸이 libart+0x615ab0, `art::CheckJNI::RegisterNatives`를 가리켰다. 이 함수는 검사를 마친 뒤 `art::JNI<true>::RegisterNatives`를 안쪽에서 다시 불렀다(깊이 2). 매핑 결과는 일반 앱과 같다. logcat에는 이 프로세스에서만 `Late-enabling -Xcheck:jni`가 한 줄 찍혔고, 떠 있던 `io.seika.jnimap`의 로그에서는 0줄이었다.

소스를 따라가면 순서가 맞아떨어진다. system_server는 debuggable 앱을 띄울 때 [ProcessList.java L1739-1744](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ProcessList.java#1739)에서 `DEBUG_ENABLE_CHECKJNI` 플래그를 얹는다. 포크된 앱 프로세스는 [ZygoteHooks.cc L165-171](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/native/dalvik_system_ZygoteHooks.cc#165)에서 이 플래그를 보고 `Late-enabling -Xcheck:jni`를 남긴 뒤 현재 스레드의 JNIEnv를 CheckJNI로 돌린다. CheckJNI가 켜진 JNIEnv는 [jni_env_ext.cc L318-324](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/jni_env_ext.cc#318)에서 `GetCheckJniNativeInterface()`의 표를 받는다. 그 표의 `RegisterNatives`는 [check_jni.cc L1828-1840](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/check_jni.cc#1828)에서 인자를 검사하고 `baseEnv(env)->RegisterNatives`를 부른다. `baseEnv`가 돌려주는 검사 없는 표는 `GetJniNativeInterface()`에서 오는데, 이 함수가 두 구현 중 하나를 고른다.

![jni_internal.cc 3261~3268행의 GetJniNativeInterface. 3265행이 강조돼 있고 Runtime::Current()->GetJniIdType() == JniIdType::kPointer이면 JniNativeInterfaceFunctions false 판의 gJniNativeInterface를, 아니면 true 판을 돌려준다](/assets/img/android-mastery/p1c10/s2-art-getjninativeinterface.png)

JniIdType이 `kPointer`일 때만 `JNI<false>` 표다([jni_internal.cc L3261-3268](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/jni/jni_internal.cc#3261)). 포크 직후 [runtime.cc L1220-1226](https://android.googlesource.com/platform/art/+/refs/tags/aml_art_331711080/runtime/runtime.cc#1220)이 debuggable 프로세스에는 `kIndices`를, 나머지에는 `kPointer`를 정한다. 그래서 일반 앱은 `JNI<false>`로 곧장 가고, debuggable 앱은 CheckJNI를 거쳐 `JNI<true>`로 간다. 이름에 `JNIILb0E`가 든 구현 하나만 골라 거는 스크립트는 debuggable 앱의 등록을 놓치고, CheckJNI 판만 거는 스크립트는 릴리스 앱을 놓친다. 등록하는 스레드의 215번 칸을 읽거나 세 구현을 다 걸어야 앱 종류와 상관없이 잡힌다.

Android의 [JNI 팁 문서](https://developer.android.com/training/articles/perf-jni#extended-checking)는 에뮬레이터에서는 CheckJNI가 기본으로 켜져 있다고 하고, 늦게 켜질 때의 로그를 `D Late-enabling CheckJNI`로 소개한다. 이 에뮬레이터(36.5.11, API 33 이미지)에서는 일반 앱에 CheckJNI가 켜지지 않았다.

시스템 전체 스위치는 [AndroidRuntime.cpp L750-755](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/jni/AndroidRuntime.cpp#750)가 읽는 `dalvik.vm.checkjni`이고, 이 값이 켜져 있으면 zygote가 뜰 때 `CheckJNI is ON`을 남긴다. 이미지의 `init.ranchu.rc`는 이 값을 `ro.boot.dalvik.vm.checkjni`에서 복사해 오는데, 이번 부팅에서는 둘 다 비어 있었고 `CheckJNI is ON` 로그도 없었다. 에뮬레이터에는 이 값을 켜는 `-dalvik-vm-checkjni` 옵션이 있으니 문서의 문장은 그 옵션을 주고 띄운 경우에 맞는 것으로 보인다.

문서의 `D Late-enabling CheckJNI` 예시는 앱마다 켜는 경로 쪽이다. debuggable 플래그 말고도 앱을 띄울 때마다 읽히는 `debug.checkjni`([ProcessList.java L1764-1766](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ProcessList.java#1764))가 같은 플래그를 얹는데, 이 값도 이번 부팅에서 비어 있었다. 두 경로 모두 결국 ZygoteHooks를 지나므로 실제 로그는 INFO 수준의 `Late-enabling -Xcheck:jni`다(태그 `seika.jnimapdbg`는 프로세스 이름의 뒤쪽 15자다).

## 다시 띄우면 움직이는 주소와 그대로인 주소

스크립트에 절대 주소를 박아 두면 안 되는 이유를 확인하려고 같은 앱을 두 번 spawn했다.

```bash
adb -s $S shell am force-stop io.seika.jnimap
frida -D $S -f io.seika.jnimap -l frida/regnatives.js -q -t 5 | grep -E '^\[libart\]|nativeCheck'
adb -s $S shell am force-stop io.seika.jnimap
frida -D $S -f io.seika.jnimap -l frida/regnatives.js -q -t 5 | grep -E '^\[libart\]|nativeCheck'
```

![두 번 spawn한 터미널. 두 번 모두 libart base=0x730c09a00000으로 같고, nativeCheck는 처음 0x730b8b31d9f0, 다음 0x730b8a2709f0으로 절대 주소가 다르지만 둘 다 libjnimap.so+0x19f0이다](/assets/img/android-mastery/p1c10/08-aslr-offsets.png)

`nativeCheck`의 절대 주소는 0x730b8b31d9f0에서 0x730b8a2709f0으로 바뀌었지만 `libjnimap.so+0x19f0`은 그대로다. 이번 세션 동안 `libjnimap.so`는 실행할 때마다 0x730b8bf63000, 0x730ba5a74000, 0x730b8b31c000처럼 다른 베이스에 올라왔다. 반면 libart의 베이스는 두 번 다 0x730c09a00000이었고, 앞의 debuggable 앱에서 본 215번 칸 주소 0x730c0a015ab0에서 0x615ab0을 빼도 같은 값이 나온다. 두 앱의 `/proc/<pid>/maps`에서도 libart는 730c09a00000에 있었다. libart는 zygote가 이미 올려 둔 것을 포크로 물려받고, 앱 라이브러리는 포크 뒤에 각자 로드하기 때문이다. 그래서 스크립트에는 절대 주소 대신 모듈 이름과 오프셋을 적었다.

## attach로는 이미 끝난 등록을 못 본다

`JNI_OnLoad`를 spawn으로 잡은 이유를 반대쪽에서 확인했다. 떠 있는 앱에 `regnatives.js`를 attach하고, 7초 뒤에 `--ez rebind true`로 앱이 `nativeRebind()`를 부르게 했다.

```bash
adb -s $S shell am start -W -n io.seika.jnimap/.MainActivity
(sleep 7; adb -s $S shell am start -n io.seika.jnimap/.MainActivity --ez rebind true >/dev/null) & \
frida -D $S -N io.seika.jnimap -l frida/regnatives.js -q -t 12
```

![attach 모드의 regnatives.js 출력. export null, enumerateSymbols 3개, slot 215는 Frida 스레드 기준 libart.so+0x69ca80 art::JNI false 판이고, libjnimap.so just loaded 줄은 없다. rebind 인텐트 뒤에 RegisterNatives class=io.seika.jnimap.Native n=3이 한 번 찍혀 nativeCheck +0x19f0, nativeMix +0x1a90, nativeRebind +0x1aa0, returned 0](/assets/img/android-mastery/p1c10/09c-rebind-attach-main.png)

`libjnimap.so just loaded` 줄은 나오지 않았다. 붙기 전에 이미 로드된 라이브러리라서다. 이 프로세스가 시작할 때 `JNI_OnLoad`에서 한 등록도 보이지 않는다. 등록 줄은 앱이 `nativeRebind()`로 `RegisterNatives`를 다시 불렀을 때 한 번 찍혔고, logcat에도 `nativeRebind: RegisterNatives(3) = 0`이 남았다. 실제 앱은 보통 이런 재등록을 하지 않으니 등록 표를 보려면 ([8장](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)에서처럼) spawn으로 띄워야 한다. attach는 오프셋을 이미 알고 있을 때 쓴다.

## Android 16 이미지의 libart에는 .symtab이 없다

`enumerateSymbols()`가 세 구현을 찾은 건 API 33 에뮬레이터 이미지의 libart에 `.symtab`이 남아 있어서였다. API 36 이미지를 보조 에뮬레이터로 띄워 같은 APK를 설치하고 frida-server를 올린 뒤, 기기의 libart를 꺼내 봤다. 호스트에서 쓴 `llvm-*` 도구는 NDK의 것이다.

```bash
export S=emulator-5620
adb -s $S shell getprop ro.build.version.sdk
adb -s $S shell pm list packages --apex-only --show-versioncode | grep -i '\.art'
mkdir -p art36 && adb -s $S pull /apex/com.android.art/lib64/libart.so art36/
llvm-readelf -S -W art36/libart.so | grep -E ' \.(dynsym|symtab|gnu_debugdata) '
llvm-nm -C art36/libart.so
llvm-objcopy --dump-section .gnu_debugdata=art36/mdi.xz art36/libart.so && xz -dc art36/mdi.xz > art36/mdi.elf
llvm-nm -C art36/mdi.elf | grep RegisterNatives
```

![API 36 보조 에뮬레이터 터미널. sdk 36, com.google.android.art versionCode 360527520, libart.so 12782304바이트를 pull했고 grep으로 고른 심볼 섹션 중 .dynsym과 .gnu_debugdata만 있고 .symtab은 없다. llvm-nm은 art36/libart.so: no symbols, .gnu_debugdata를 덤프해 xz로 푼 mdi.elf에는 T 타입으로 667e40 CheckJNI::RegisterNatives(.__uniq.99033978352804627313491551960229047428.llvm.6262425906947437964), 6e9ec0 art::JNI false 판, 7538e0 art::JNI true 판이 있다](/assets/img/android-mastery/p1c10/09a-api36-libart.png)

이 libart에는 `.symtab`이 없고 심볼이 든 섹션은 `.dynsym`과 `.gnu_debugdata`뿐이며 `llvm-nm`은 "no symbols"라고 답한다. `.gnu_debugdata`는 xz로 압축한 작은 ELF를 넣어 두는 섹션(MiniDebugInfo)인데, 풀어 보면 세 구현이 그대로 있다. 다만 CheckJNI 판 접미사가 `.__uniq.99033978352804627313491551960229047428.llvm.6262425906947437964`로 API 33의 것과 다르고, 세 심볼 모두 대문자 `T`로 적혀 있다. 이 상태에서 Frida가 무엇을 찾는지 같은 `regnatives.js`로 봤다.

```bash
adb -s $S shell am force-stop io.seika.jnimap
frida -D $S -f io.seika.jnimap -l frida/regnatives.js -q -t 8
```

![API 36에서 regnatives.js를 spawn한 터미널. libart base=0x7cf2a4c00000, findExportByName null, export 0개, enumerateSymbols 3개가 global로 libart+0x667e40 CheckJNI(.__uniq 접미사), +0x6e9ec0 JNIILb0E, +0x7538e0 JNIILb1E, slot 215는 두 시점 모두 libart.so+0x6e9ec0 art::JNI false 판. libframework-connectivity-tiramisu-jni.so의 n=2 등록 뒤 class=io.seika.jnimap.Native n=3에서 nativeCheck → libjnimap.so+0x19f0, nativeMix → +0x1a90, nativeRebind → +0x1aa0, returned 0](/assets/img/android-mastery/p1c10/09b-api36-registernatives.png)

Frida 17.17.0은 MiniDebugInfo도 읽었다. `enumerateSymbols()`가 세 심볼을 `global`로 돌려줬고, `DebugSymbol`도 215번 칸의 목적지 libart+0x6e9ec0에 `art::JNI<false>::RegisterNatives`라는 이름을 붙였다. 매핑은 API 33과 똑같이 `nativeCheck → libjnimap.so+0x19f0`이다. 이번 두 이미지에서는 심볼 쪽 길도 통했지만, 심볼 이름에 기대는 스크립트는 CheckJNI 접미사처럼 빌드마다 바뀌는 부분에서 깨지기 쉽다. MiniDebugInfo까지 걷어 낸 libart라면 심볼 쪽 길은 막히고 215번 칸을 읽는 길만 남을 것이다.

| 이미지 | 앱 | 등록 스레드의 215번 칸 | 안쪽에서 다시 부르는 구현 |
|---|---|---|---|
| API 33 | io.seika.jnimap | `JNI<false>` libart+0x69ca80 | 없음 |
| API 33 | io.seika.jnimapdbg | `CheckJNI` libart+0x615ab0 | `JNI<true>` |
| API 36 | io.seika.jnimap | `JNI<false>` libart+0x6e9ec0 | 없음 |

API 36 이미지는 `ro.product.cpu.abilist`가 `x86_64,arm64-v8a`이고 `ro.dalvik.vm.native.bridge`가 `libndk_translation.so`다. 앱 프로세스에도 `/system/lib64/libndk_translation.so`가 매핑돼 있었다. 하지만 앱의 `primaryCpuAbi`는 x86_64였고 x86_64 라이브러리는 변환 없이 돌았다. 그 위에 건 x86_64 후크가 그대로 동작했다. ARM 라이브러리를 이 변환기로 돌리는 경우는 해 보지 않았다.

## 판정을 기기 밖으로 빼야 하는 이유

`static`과 숨김 visibility, 스트립은 이름만 지운다. 이름을 지워도 등록 순간과 재배치에서 주소가 나왔고, XOR로 감춘 비밀값은 `strcmp` 인자로 풀렸고, 판정은 반환값 하나로 뒤집혔다. 그러니 잠금 해제나 구매 확인처럼 결과가 중요한 판단은 서버가 내리고, 앱은 서버가 검증할 수 있는 근거를 보내도록 짜야 한다. 비밀값을 기기에 두어야 한다면 앱 메모리에 평문으로 풀리지 않는 Keystore 키로 바꾸는 쪽이 낫다([14장](/posts/android-lab-p1c14-keystore-biometricprompt/)).

점검도 같은 도구로 한다. 릴리스 빌드에 `regnatives.js`를 spawn으로 돌리면 등록되는 메서드와 오프셋 목록이 나온다. 목록에 디버그용 메서드가 남아 있거나 예상 밖의 등록이 보이면 빌드 설정부터 본다. `flip.js`처럼 네이티브 판정의 반환값을 바꿔 놓고도 서버가 요청을 거절하는지 보면 판정이 정말 서버에 있는지 드러난다. 이번 실험 앱에는 서버가 없어서 이 확인은 돌려 보지 못했다.

변조를 알아채는 쪽의 단서도 남았다. Frida의 인라인 후크는 libc `strcmp`의 머리를 `e9`로 시작하는 jmp로 덮었다. 민감한 함수와 그 함수가 부르는 libc 함수의 앞부분을 디스크의 바이트와 견주는 무결성 검사라면 이런 변경을 볼 수 있을 것이다(이번 표본에는 그런 검사가 없었다). Frida 세션을 끝낸 뒤에도 앱의 `/proc/<pid>/maps`에서 libart의 실행 영역이 libart+0x3fc000, +0x615000, +0x69c000, +0x707000에서 한 페이지씩 잘게 쪼개져 있었다. 뒤의 셋은 후크한 세 RegisterNatives가 든 페이지이고, 앞의 하나는 `art::ArtMethod::Invoke`와 `PrettyMethod`가 있는 페이지다. 모두 Frida가 패치하면서 남긴 흔적으로 보이고, 앞의 페이지는 Java 브리지 쪽에서 건드린 것으로 짐작한다.

*다음 글: [Burp/mitmproxy 로컬 인터셉션](/posts/android-lab-p1c11-burp-mitmproxy-intercept/)*
