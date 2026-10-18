---
layout: post
title: "ClassLoader와 동적 로딩 — 패커가 ART에 넘기는 dex를 입구에서 꺼내기"
date: 2026-10-24 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ClassLoader, InMemoryDexClassLoader, DexClassLoader, DynamicCodeLoading, Packer, Frida, ART]
excerpt: "직접 만든 2단 패커의 dex 두 개를 spawn으로 DexFile 네이티브 입구에서 받아 냈더니 메모리로 올린 것도 로드 직후 지워진 파일도 빌드 원본과 SHA-256이 같았다. 생성자에서 buf.get()으로 읽는 덤프는 position을 밀어 로드를 조용히 깨뜨렸고, Android 14의 읽기 전용 규칙은 파일 로드에만 걸렸다."
---

[지난 글](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)에서 Frida를 spawn과 attach로 붙여 Java 메서드를 바꿔 끼웠다. 이번에는 그 도구를 패커에 댄다. 패커가 걸린 APK를 jadx로 열면 복호화하고 로더를 만드는 스텁만 보인다. 진짜 dex는 실행 중에 풀려 `InMemoryDexClassLoader`나 `DexClassLoader`를 거쳐 ART로 들어간다. 그 들어가는 문이 생각보다 좁아서 거기에 후킹을 걸어 두면 어느 로더를 쓰든 바이트가 지나가는 순간 복사할 수 있다. 로더 계층과 리플렉션의 기본은 [Atlas C14](/posts/android-concept-atlas-c14-classloader-reflection/)에 있다.

상용 패커를 뜯는 대신 2단짜리 패커 `io.seika.dcl`을 직접 만들었다. 1단 페이로드 `io.seika.payload.Core`는 XOR로 감싸 `assets/s1.bin`에 넣었다. 스텁이 이걸 풀어 direct `ByteBuffer`에 담은 뒤 `InMemoryDexClassLoader`에 넘긴다. 1단은 실행되면서 `assets/s2.bin`을 풀어 `files/s2/stage2.dex`로 쓰고 `DexClassLoader`로 2단 `io.seika.payload2.Beacon`을 올린 다음 파일을 지운다. 메모리에서만 사는 dex와 디스크에 잠깐 있다 사라지는 dex를 한 앱에서 같이 보려고 단을 나눴다. 페이로드에 든 주소는 전부 `example.invalid`다. [4장](/posts/android-lab-p1c04-jadx-static-analysis/)의 한 겹짜리 패커를 두 단으로 늘린 것이다.

기기는 `codex-atlas-api33` 에뮬레이터(Android 13, API 33, google_apis x86_64 userdebug, 보안 패치 2024-03-01, ART 모듈 versionCode 331711080)를 썼다. 호스트 쪽은 Frida 17.17.0(frida-tools 14.8.1)과 jadx 1.5.5다. Android 14의 읽기 전용 규칙을 볼 때만 `sec-36-std`(Android 16, API 36, ART 모듈 versionCode 360527520)를 따로 띄웠다. 앱은 debuggable 플래그 없이 빌드했다. Java 디버깅이 가능한 프로세스에서는 ART가 동적으로 올린 dex의 백그라운드 검증을 건너뛰게 짜여 있어서 아래에서 볼 익명 vdex가 생기지 않는다.

## 스텁이 흘린 건 클래스 이름 두 줄뿐이다

1단을 푸는 일은 `StubApp.attachBaseContext` 안에서 끝난다. 액티비티가 만들어지기 전에 1단을 메모리로 올리고, 넘긴 버퍼는 곧바로 0으로 덮는다.

```java
// app/src/io/seika/dcl/StubApp.java 19~36행
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try {
            byte[] blob = read(base.getAssets().open("s1.bin"));
            for (int i = 0; i < blob.length; i++) blob[i] ^= K1[i % K1.length];
            ByteBuffer buf = ByteBuffer.allocateDirect(blob.length);
            buf.put(blob);
            buf.rewind();
            Arrays.fill(blob, (byte) 0);
            payload = new InMemoryDexClassLoader(buf, StubApp.class.getClassLoader());
            // ART copied the bytes into its own mapping; wipe ours like real packers do.
            for (int i = 0; i < buf.capacity(); i++) buf.put(i, (byte) 0);
            Log.i(TAG, "stage1 loaded from a " + buf.capacity() + "-byte direct buffer");
        } catch (Exception e) {
            Log.e(TAG, "stage1 failed", e);
        }
    }
```

페이로드는 `javac --release 8`로 컴파일하고 `d8 --min-api 26`으로 dex를 만든 다음, 빌드 스크립트 안의 짧은 파이썬으로 키를 돌려 XOR해 assets에 넣었다.

```python
# build.sh 안의 XOR 단계
for src, dst, key in (("out/stage1.dex", "app/assets/s1.bin", b"s1-key-p1c09"),
                      ("out/stage2.dex", "app/assets/s2.bin", b"s2-key-p1c09")):
    d = open(src, "rb").read()
    open(dst, "wb").write(bytes(b ^ key[i % len(key)] for i, b in enumerate(d)))
    print(dst, len(d), "bytes, head", d[:8])
```

APK는 Gradle 없이 javac, d8, aapt, zipalign, apksigner를 이어 붙여 minSdk 26, targetSdk 33으로 묶었다. 같은 코드를 targetSdk 34로 한 벌 더 만들어 Android 14 규칙 실험에 썼다. 완성된 `out/dcl.apk`를 jadx에 넣으면 이렇게 보인다.

![호스트 터미널에서 unzip -l out/dcl.apk 로 본 APK 목록(AndroidManifest.xml 1736, assets/s1.bin 4888, assets/s2.bin 1200, classes.dex 5664 바이트), jadx 결과가 MainActivity.java 와 StubApp.java 뿐인 것, grep 이 찾은 MainActivity.java:45 loadClass("io.seika.payload.Core") 와 StubApp.java:30 new InMemoryDexClassLoader(byteBufferAllocateDirect, StubApp.class.getClassLoader()) 가 걸리고, xxd 로 본 s1.bin 첫 16바이트 1754 5561 554a 1570 에 dex 매직이 없고 jadx 가 No classes to decompile 경고를 내는 화면](/assets/img/android-mastery/p1c09/01-static-stub.png)

APK 안의 코드는 5664바이트짜리 `classes.dex` 하나이고 jadx가 푼 소스도 `MainActivity.java`와 `StubApp.java`뿐이다. 정적으로 건질 수 있는 건 grep에 걸린 두 줄 정도다. `MainActivity`가 `loadClass("io.seika.payload.Core")`를 부르고 `StubApp`이 direct 버퍼로 `InMemoryDexClassLoader`를 만든다. 클래스 이름은 새어 나왔지만 몸통은 어디에도 없다. `s1.bin`은 `1754 5561`로 시작해 dex 매직이 보이지 않고, jadx에 넣으면 `No classes to decompile`로 끝난다.

## 로더가 무엇이든 DexFile의 네이티브 메서드로 모인다

처음 떠올린 방법은 `InMemoryDexClassLoader(ByteBuffer, ClassLoader)` 생성자 하나를 후킹하는 것이었는데 생성자 목록을 다시 보니 그걸로는 모자랐다. [레퍼런스](https://developer.android.com/reference/dalvik/system/InMemoryDexClassLoader)에 실린 공개 생성자는 API 26의 `(ByteBuffer, ClassLoader)`, API 27의 `(ByteBuffer[], ClassLoader)`, API 29의 `(ByteBuffer[], String librarySearchPath, ClassLoader)`다. Android 13 소스에서 단일 버퍼 생성자는 버퍼를 배열로 감싸 배열 생성자를 부른다([62~64행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/InMemoryDexClassLoader.java#62)). 배열 생성자는 `librarySearchPath`를 null로 채워 세 인자 생성자를 부르고([50~53행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/InMemoryDexClassLoader.java#50)) 그게 `BaseDexClassLoader`로 넘어간다([38~41행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/InMemoryDexClassLoader.java#38)). 단일 버퍼에서 배열로 넘기는 위임은 8.0 소스에도 있고 10에서 한 단계가 더 붙었다. 앱이 배열 생성자를 직접 부르면 단일 버퍼 오버로드에 건 후킹은 아무것도 보지 못한다.

그 아래는 전부 `DexFile`로 모인다. `BaseDexClassLoader`의 ByteBuffer 생성자가 `DexPathList.initByteBufferDexPath`를 부르고 거기서 만든 `DexFile`이 [`openInMemoryDexFiles`](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#380)를 거쳐 네이티브 메서드 `openInMemoryDexFilesNative`로 들어간다. 파일 경로를 받는 `DexClassLoader`와 `PathClassLoader`는 `DexFile.openDexFile`에서 [`openDexFileNative`](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#442)로 들어간다.

Android 8과 9는 모양이 달랐다. 이름이 단수형인 Java 래퍼 `openInMemoryDexFile(ByteBuffer)`가 따로 있었고([8.0.0_r1 362행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-8.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#362), [9.0.0_r1 363행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-9.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#363)), 그 아래 네이티브 입구도 direct 버퍼는 `createCookieWithDirectBuffer`, 힙 버퍼는 `createCookieWithArray`로 갈렸다([8.0.0_r1 370~371행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-8.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#370), [9.0.0_r1 371~372행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-9.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#371)). 버퍼 배열을 받는 지금 모양은 10부터다. 그래서 아래 `dcl-dump.js`는 Android 10 이상에서만 맞고, API 26~28 경로는 기기 없이 소스로만 확인했다.

![android-13.0.0_r1 libcore DexFile.java 383~409행. 389행 isDirect() 이면 null, 아니면 array() 를 arrays 에 넣는 줄이 강조돼 있고, 390~391행 starts 는 position(), ends 는 limit() 로 채우며, 393행 openInMemoryDexFilesNative 호출과 396~397행 그 네이티브 선언(ByteBuffer 배열, byte 2차원 배열, int 배열 둘, ClassLoader, Element 배열)이 보이는 소스 화면](/assets/img/android-mastery/p1c09/12-src-openinmemorydexfiles.png)

네이티브로 넘기기 직전에 libcore가 하는 일이 덤프 스크립트의 규칙이 된다. direct 버퍼면 `array()`를 부르지 않고 null을 넘기며(389행) 읽을 범위는 버퍼의 `position()`부터 `limit()`까지다(390~391행). 그래서 덤프하는 쪽도 direct 버퍼는 네이티브 주소에서 그 범위만 읽는다. 힙 버퍼는 libcore가 꺼내 준 배열을 쓰고 버퍼 객체는 건드리지 않는다.

이 Java 래퍼들은 부트 이미지에 들어 있어 미리 컴파일됐을 수 있다. 그러면 [지난 글](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)에서 본 인라인 문제로 Java 단 후킹이 빗나갈 수도 있다고 봤다. 그래서 덤프는 네이티브 메서드 두 곳에 걸었다(`dcl-dump.js`, 사용법 머리 주석은 뺐다).

```javascript
const OUT = '/data/data/io.seika.dcl/files/dumps';
let seq = 0;

// "dex\n038\0" -> printable form; a real dex starts with dex\n + 3 digits + \0
function magic(u8) {
  return Array.from(u8.slice(0, 8), b => b === 10 ? '\\n' : b === 0 ? '\\0' : String.fromCharCode(b)).join('');
}

function save(tag, u8) {
  Java.use('java.io.File').$new(OUT).mkdirs();
  const path = `${OUT}/${tag}-${++seq}-${u8.length}.dex`;
  File.writeAllBytes(path, u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.length));
  return path;
}

Java.perform(() => {
  const DexFile = Java.use('dalvik.system.DexFile');
  const env = () => Java.vm.getEnv();

  DexFile.openInMemoryDexFilesNative.implementation = function (bufs, arrays, starts, ends, loader, elements) {
    for (let i = 0; i < bufs.length; i++) {
      const s = starts[i], e = ends[i];
      let u8;
      if (arrays[i] === null) {                       // direct buffer: read native memory, buffer untouched
        const base = env().getDirectBufferAddress(bufs[i].$h);
        u8 = new Uint8Array(base.add(s).readByteArray(e - s));
      } else {                                        // heap buffer: DexFile already pulled out .array()
        const a = arrays[i];
        u8 = new Uint8Array(e - s);
        for (let j = s; j < e; j++) u8[j - s] = a[j] & 0xff;
      }
      console.log(`[openInMemoryDexFilesNative] buf ${i}: ${arrays[i] === null ? 'direct' : 'heap'} ` +
                  `[${s},${e}) magic=${magic(u8)} -> ${save('mem', u8)}`);
    }
    return this.openInMemoryDexFilesNative(bufs, arrays, starts, ends, loader, elements);
  };

  DexFile.openDexFileNative.implementation = function (src, out, flags, loader, elements) {
    if (/^\/data\/(user|data)\//.test(src)) {         // app-private files only, not base.apk
      const u8 = new Uint8Array(File.readAllBytes(src));
      console.log(`[openDexFileNative] ${src} ${u8.length} bytes magic=${magic(u8)} -> ${save('file', u8)}`);
    }
    return this.openDexFileNative(src, out, flags, loader, elements);
  };
  console.log('[dcl-dump] hooks installed');
});
```

힙 버퍼 분기는 바이트를 하나씩 옮기니 수 MB짜리 dex에서는 느릴 것이다. 이 앱은 direct 버퍼만 쓰니 그 분기를 탈 일이 없었다. Java 쪽에는 덤프 없이 로그만 남기는 후킹을 `dcl-trace.js`로 따로 걸었다. `InMemoryDexClassLoader`의 생성자 오버로드 전부, `DexFile.openInMemoryDexFiles`, `DexClassLoader` 생성자, `ClassLoader.loadClass(String)`, `Method.invoke`가 대상이고 네이티브 쪽과 비교하려고 넣었다.

```javascript
Java.perform(() => {
  const IMDCL = Java.use('dalvik.system.InMemoryDexClassLoader');
  IMDCL.$init.overloads.forEach(ov => {
    ov.implementation = function () {
      console.log(`[InMemoryDexClassLoader.<init>(${ov.argumentTypes.map(t => t.className).join(', ')})]`);
      return ov.apply(this, arguments);
    };
  });

  // Java-level private wrapper above the native call. If this line never shows while the
  // native hook in dcl-dump.js does, the wrapper was inlined into boot-image code.
  const DexFile = Java.use('dalvik.system.DexFile');
  DexFile.openInMemoryDexFiles.implementation = function (bufs, loader, elements) {
    console.log(`[DexFile.openInMemoryDexFiles] ${bufs.length} buffer(s), isDirect=${bufs[0].isDirect()}`);
    return this.openInMemoryDexFiles(bufs, loader, elements);
  };

  const DCL = Java.use('dalvik.system.DexClassLoader');
  DCL.$init.implementation = function (dexPath, odexDir, libPath, parent) {
    console.log(`[DexClassLoader.<init>] ${dexPath} parent=${parent.$className}`);
    return this.$init(dexPath, odexDir, libPath, parent);
  };

  const ClassLoader = Java.use('java.lang.ClassLoader');
  ClassLoader.loadClass.overload('java.lang.String').implementation = function (name) {
    const c = this.loadClass(name);
    if (name.startsWith('io.seika.payload')) console.log(`[loadClass] ${name} via ${this.$className}`);
    return c;
  };

  const Method = Java.use('java.lang.reflect.Method');
  Method.invoke.implementation = function (obj, args) {
    const cls = this.getDeclaringClass().getName();
    if (cls.startsWith('io.seika.payload') && this.getName() !== 'beat') {
      console.log(`[Method.invoke] ${cls}.${this.getName()}`);
    }
    return this.invoke(obj, args);
  };
});
```

## spawn으로 붙여 두 dex를 다 받아 내다

1단은 `Application.attachBaseContext`에서 올라가니 앱이 뜬 뒤에 attach하면 늦다. spawn으로 프로세스를 멈춘 채 만들고 후킹을 건 다음 재개한다. frida-server는 지난 글처럼 `/data/local/tmp`에 올려 둔 17.17.0이다.

```bash
export S=emulator-5602
adb -s $S root
adb -s $S wait-for-device
adb -s $S install out/dcl.apk
adb -s $S shell "/data/local/tmp/frida-server >/dev/null 2>&1 &"
adb -s $S shell am force-stop io.seika.dcl
adb -s $S shell rm -rf /data/data/io.seika.dcl/files/dumps
frida -D $S -f io.seika.dcl -l frida/dcl-trace.js -l frida/dcl-dump.js -q -t 10
```

![frida -D $S -f io.seika.dcl -l frida/dcl-trace.js -l frida/dcl-dump.js -q -t 10 실행 결과. dcl-dump hooks installed 뒤로 InMemoryDexClassLoader 생성자 세 오버로드(ByteBuffer, ByteBuffer 배열, ByteBuffer 배열과 String), DexFile.openInMemoryDexFiles 1 buffer(s) isDirect=true, openInMemoryDexFilesNative buf 0 direct 0부터 4888 magic=dex\n038\0 이 files/dumps/mem-1-4888.dex 로 저장, loadClass io.seika.payload.Core via InMemoryDexClassLoader, Method.invoke Core.run, DexClassLoader 생성자 files/s2/stage2.dex, openDexFileNative stage2.dex 1200 bytes 가 file-2-1200.dex 로 저장, loadClass Beacon via DexClassLoader, Method.invoke Beacon.ping 이 차례로 찍힌 터미널](/assets/img/android-mastery/p1c09/03-spawn-dump.png)

예상과 다르게 나온 건 Java 쪽이다. 생성자 오버로드 셋이 공개 단일 버퍼, 배열, 배열과 `librarySearchPath` 순서로 모두 찍혀 위임 사슬이 드러났고 Java 래퍼 `DexFile.openInMemoryDexFiles`의 후킹도 걸렸다. 이 이미지에서는 부트 이미지 코드가 후킹을 비켜 가지 않아서 대비해 둔 `Java.deoptimizeBootImage()` 스크립트를 꺼낼 일도 없었다. 1단 덤프는 네이티브 입구에서 direct 버퍼의 `[0,4888)` 범위로 나왔고, 앞 8바이트는 `dex\n038\0`이다. 트레이스는 그 뒤로 `MainActivity`가 `InMemoryDexClassLoader`에서 `Core`를 찾아 `run`을 리플렉션으로 부르고, 1단이 `stage2.dex`로 `DexClassLoader`를 만들고, `openDexFileNative`가 1200바이트 파일을 연 다음 `Beacon.ping`이 불리는 순서로 이어졌다.

같은 프로세스의 logcat에서 앱 줄만 추리면 이렇다(시각, pid, tid 열은 지웠다).

```text
W io.seika.dcl: Openjdkjvmti plugin was loaded on a non-debuggable Runtime. Plugin was loaded too late to change runtime state to DEBUGGABLE. Only kArtTiVersion (0x70010200) environments are available. Some functionality might not work properly.
I dcl     : stage1 loaded from a 4888-byte direct buffer
I dcl     : Core.run, defined by dalvik.system.InMemoryDexClassLoader
I dcl     : stage2 written: /data/user/0/io.seika.dcl/files/s2/stage2.dex (1200 bytes, writable=true)
I dcl     : stage2 says: pong from DexClassLoader via beacon://stage2.example.invalid/ping
I dcl     : stage2 file deleted: true
```

2단 파일은 로드 직후에 지워졌지만 `openDexFileNative`가 받은 경로로 후킹이 먼저 읽어 두었다. 첫 줄은 Frida의 Java 브리지가 non-debuggable 런타임에 JVMTI 플러그인을 올리면서 남긴 경고라, 앱 logcat만 봐도 Frida가 붙었던 걸 알 수 있다. 꺼낸 파일은 호스트로 가져와 빌드 산출물과 비교했다.

```bash
adb -s $S shell ls -l /data/data/io.seika.dcl/files/dumps
adb -s $S pull /data/data/io.seika.dcl/files/dumps dumps
sha256sum dumps/*.dex out/stage1.dex out/stage2.dex
jadx -q -d jdump dumps/*.dex && find jdump/sources -name '*.java'
grep -rn 'ENDPOINT = \|CHANNEL = ' jdump/sources
```

![adb shell ls -l 로 본 files/dumps 의 file-2-1200.dex(1200 바이트)와 mem-1-4888.dex(4888 바이트), adb pull 뒤 sha256sum 에서 mem-1-4888.dex 와 out/stage1.dex 가 a15c99b46de4fa48 로 시작하는 같은 값, file-2-1200.dex 와 out/stage2.dex 가 f035082ad665af61 로 시작하는 같은 값이고, jadx 가 io/seika/payload/Core.java 와 io/seika/payload2/Beacon.java 를 풀어 grep 에 ENDPOINT = https://api.example.invalid/v3/unlock 과 CHANNEL = beacon://stage2.example.invalid/ping 이 걸린 터미널](/assets/img/android-mastery/p1c09/04-dump-verify.png)

`mem-1-4888.dex`는 `out/stage1.dex`와, `file-2-1200.dex`는 `out/stage2.dex`와 SHA-256이 같다. jadx-gui로 1단을 열면 정적으로는 보이지 않던 `Core`가 나온다.

![jadx-gui 1.5.5(한국어 UI)로 mem-1-4888 덤프를 연 화면. Core 탭에 package io.seika.payload, public final class Core, ENDPOINT 상수, K2 = "s2-key-p1c09".getBytes(), "SEIKA-" + Integer.toHexString(ENDPOINT.hashCode() ^ 24266) 를 돌려주는 token(), run(Context, boolean) 과 s2.bin 을 읽기 시작하는 stage2() 가 보인다](/assets/img/android-mastery/p1c09/04b-jadx-gui-core.png)

1단 안에는 2단을 푸는 키 `K2 = "s2-key-p1c09"`가 들어 있다. 이 패커처럼 바깥 한 겹을 벗기면 다음 겹의 키가 드러나는 구조라면 그다음부터는 런타임 없이 정적으로 이어 갈 수 있다. 실제 분석에서는 비교할 원본이 없으니 매직이 `dex\n`과 숫자 세 자리로 시작하는지, 헤더 0x20의 `file_size`가 덤프 길이와 같은지, jadx가 클래스를 풀어 내는지로 덤프를 확인하게 된다.

상용 패커 중에는 로드한 뒤에 메서드 몸통을 채워 넣거나 Frida를 감지하는 것도 있다. 그런 패커라면 로드 시점에 뜬 덤프의 메서드가 비어 있을 수 있는데, 직접 만든 패커로는 이 경우를 재현하지 못했다.

### dex 매직은 `dex\n035`로 고정돼 있지 않다

덤프가 dex인지 앞 8바이트를 `dex\n035`와 비교해 가리는 예제를 종종 보는데 위 덤프부터 038이었다. 같은 `Beacon.class`를 `--min-api`만 바꿔 d8로 다시 변환했다.

```bash
javac -Xlint:-options --release 8 -d minapi/cls payload2/src/io/seika/payload2/Beacon.java
for m in 21 24 26 28 35; do mkdir -p minapi/$m && d8 --min-api $m --output minapi/$m minapi/cls/io/seika/payload2/Beacon.class && echo "min-api $m: $(xxd -l 8 minapi/$m/classes.dex)"; done
xxd -l 8 out/stage1.dex
```

![같은 Beacon.class 를 d8 --min-api 21, 24, 26, 28, 35 로 변환한 classes.dex 의 첫 8바이트가 각각 dex.035, dex.037, dex.038, dex.039, dex.039 로 찍히고, xxd -l 8 out/stage1.dex 는 6465 780a 3033 3800(dex\n038\0)인 터미널](/assets/img/android-mastery/p1c09/02-dex-magic-minapi.png)

min-api 21은 035, 24는 037, 26은 038, 28과 35는 039를 썼다. 페이로드는 min-api 26으로 만들었으니 038이다. 측정에 쓴 Android 13의 목록은 [android-13.0.0_r1 standard_dex_file.cc 26~39행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/libdexfile/dex/standard_dex_file.cc#26)에 있다. `dex\n` 뒤에 035, 037, 038(O), 039(P), 040(10)이 오고 `\0`으로 끝난다. 036은 옛 Dalvik 버그 때문에 건너뛰었다는 주석이 붙어 있다. API 36(Android 16) 이미지와 같은 세대인 [android-16.0.0_r1 태그](https://android.googlesource.com/platform/art/+/refs/tags/android-16.0.0_r1/libdexfile/dex/standard_dex_file.cc#39)에는 Android 15용 041이 더 붙어 있다. 035로 고정해 비교하는 덤프 코드는 min-api 24 이상으로 빌드된 페이로드를 dex가 아니라고 판정한다.

## 생성자에서 buf.get()으로 읽으면 로드가 조용히 깨진다

생성자 후킹으로 덤프하려 할 때 먼저 떠오르는 모양은 `$init(ByteBuffer, ClassLoader)`에서 버퍼를 읽어 저장한 뒤 원래 생성자를 부르는 것이다. `imdcl-naive.js`는 그중 읽는 부분만 옮겨 길이와 앞 8바이트를 찍고, `imdcl-dup.js`는 읽는 방법만 `duplicate()`로 바꿔 파일로 저장까지 한다. 둘을 나란히 돌렸다.

```javascript
// imdcl-naive.js
Java.perform(() => {
  const IMDCL = Java.use('dalvik.system.InMemoryDexClassLoader');
  IMDCL.$init.overload('java.nio.ByteBuffer', 'java.lang.ClassLoader').implementation = function (buf, parent) {
    const b = Java.cast(buf, Java.use('java.nio.Buffer'));  // ByteBuffer only redeclares position(int)/limit(int); the getters live on Buffer
    const arr = Java.array('byte', new Array(buf.remaining()).fill(0));
    buf.get.overload('[B').call(buf, arr);
    let m = '';
    for (let i = 0; i < 8; i++) { const x = arr[i] & 0xff; m += x === 10 ? '\\n' : x === 0 ? '\\0' : String.fromCharCode(x); }
    console.log(`[naive] copied ${arr.length} bytes magic=${m}; position=${b.position()} limit=${b.limit()}`);
    return this.$init(buf, parent);
  };
});
```

```javascript
// imdcl-dup.js
const OUT = '/data/data/io.seika.dcl/files/dumps';
Java.perform(() => {
  const IMDCL = Java.use('dalvik.system.InMemoryDexClassLoader');
  IMDCL.$init.overload('java.nio.ByteBuffer', 'java.lang.ClassLoader').implementation = function (buf, parent) {
    const b = Java.cast(buf, Java.use('java.nio.Buffer'));  // ByteBuffer only redeclares position(int)/limit(int); the getters live on Buffer
    const d = buf.duplicate();
    const arr = Java.array('byte', new Array(d.remaining()).fill(0));
    d.get.overload('[B').call(d, arr);
    const u8 = new Uint8Array(arr.length);
    for (let i = 0; i < arr.length; i++) u8[i] = arr[i] & 0xff;
    Java.use('java.io.File').$new(OUT).mkdirs();
    const path = `${OUT}/ctor-${u8.length}.dex`;
    File.writeAllBytes(path, u8.buffer);
    console.log(`[dup] copied ${u8.length} bytes; position=${b.position()} limit=${b.limit()} -> ${path}`);
    return this.$init(buf, parent);
  };
});
```

`Java.cast` 줄은 첫 실행 뒤에 넣었다. [4장](/posts/android-lab-p1c04-jadx-static-analysis/) 스크립트는 처음부터 `Buffer` 쪽 `position()`을 불렀는데 이번 두 스크립트에서는 그걸 빠뜨려 첫 실행이 멈췄다. position을 찍으려고 부른 `buf.position()`에서 둘 다 같은 오류가 났다.

```text
Error: position(): argument types do not match any of:
	.overload('int')
	.overload('int')
```

Frida가 만든 `java.nio.ByteBuffer` 래퍼에는 ByteBuffer가 다시 선언한 `position(int)`(Buffer를 돌려주는 선언과 [`@CovariantReturnType`으로 합성된 ByteBuffer 반환 사본](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/nio/ByteBuffer.java#811))만 있다. 인자 없는 getter인 `position()`과 `limit()`은 부모 `java.nio.Buffer`에 선언돼 있어서 `java.nio.Buffer`로 캐스팅해 읽게 고쳤다. 고치기 전 실패에서도 볼 것이 있었다. 후킹 함수가 원래 생성자를 부르기 전에 예외로 끝나자 Frida가 오류를 찍은 뒤 생성자는 아무 일도 하지 않은 채 정상 반환했다. 스텁은 평소처럼 성공 로그를 남겼고 첫 `loadClass`에서 앱이 NullPointerException으로 넘어졌다(logcat은 150자에서 잘랐다).

```text
I/dcl     : stage1 loaded from a 4888-byte direct buffer
I/dcl     : result: payload failed: java.lang.NullPointerException: Attempt to invoke virtual method 'java.lang.Class dalvik.system.DexPathList.findCl
```

`DexPathList`에 대고 부른 메서드가 null에서 터진 것으로 보아 로더의 `pathList`가 채워지지 않은 채 남은 것이다. 후킹 스크립트가 원본 호출 전에 던지면 앱은 예외 없이 반쯤 만들어진 로더를 받는다. 고친 스크립트로 다시 돌린 결과가 아래다.

```bash
adb -s $S shell am force-stop io.seika.dcl; adb -s $S logcat -c
frida -D $S -f io.seika.dcl -l frida/imdcl-naive.js -q -t 6
adb -s $S logcat -d -v tag -s System dcl | grep -E 'Unable to load dex|Bad range|stage1 loaded|result:' | cut -c1-150
adb -s $S shell am force-stop io.seika.dcl; adb -s $S logcat -c
frida -D $S -f io.seika.dcl -l frida/imdcl-dup.js -q -t 6
adb -s $S logcat -d -v tag -s System dcl | grep -E 'Unable to load dex|Bad range|stage1 loaded|result:' | cut -c1-150
```

![imdcl-naive.js 로 spawn 하자 naive copied 4888 bytes magic=dex\n038\0; position=4888 limit=4888 이 찍히고, logcat 에 E/System Unable to load dex files, java.io.IOException: Bad range, I/dcl stage1 loaded from a 4888-byte direct buffer, result: payload failed: java.lang.ClassNotFoundException 과 비어 있는 DexPathList 가 나온다. imdcl-dup.js 로는 dup copied 4888 bytes; position=0 limit=4888 -> files/dumps/ctor-4888.dex 뒤 result: token=SEIKA-eb72f0fd stage2=pong from DexClassLoader ... hidden-api=NoSuchMethodException 이 찍힌 터미널](/assets/img/android-mastery/p1c09/08-ctor-hook-pitfall.png)

naive 쪽은 4888바이트를 읽었고 앞 8바이트 매직도 맞다. 그런데 읽기가 끝난 버퍼의 position은 4888, limit도 4888이다. 그 직후 `System` 태그로 `Unable to load dex files`와 `java.io.IOException: Bad range`가 찍혔다. 스텁은 여전히 `stage1 loaded`라고 적었고 `MainActivity`는 dex 경로가 빈 `DexPathList[[],...]`에서 `io.seika.payload.Core`를 찾지 못했다. 앱 화면에도 같은 오류가 떴다.

![naive 후킹 상태로 뜬 앱 화면. 제목 dcl lab 아래에 payload failed: java.lang.ClassNotFoundException: Didn't find class io.seika.payload.Core on path: DexPathList 빈 목록, nativeLibraryDirectories=/system/lib64, /system_ext/lib64 문구가 보인다](/assets/img/android-mastery/p1c09/08b-naive-app-screen.png)

`duplicate()`로 읽은 쪽은 원래 버퍼의 position이 0으로 남아 앱이 끝까지 돌았다. 저장한 `ctor-4888.dex`의 SHA-256도 `out/stage1.dex`와 같았다.

경로는 소스로 따라갈 수 있다. `buf.get(byte[])`은 읽은 만큼 position을 limit까지 옮긴다. `openInMemoryDexFiles`가 범위를 `[position, limit)`로 잡으니 ART가 받은 범위는 `[4888, 4888)`이다. [`AllocateDexMemoryMap`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/native/dalvik_system_DexFile.cc#202)은 `end <= start`면 `Bad range`를 던진다(203~206행). 그 예외는 앱까지 올라오지 않는다. [`DexPathList.initByteBufferDexPath`](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/DexPathList.java#249)가 `IOException`을 잡아 `Unable to load dex files`로 로그만 남기고(267행) `dexElements`를 빈 배열로 채운다(269행). 같은 naive 후킹을 캡처 없이 한 번 더 돌려 logcat 전체를 남겼더니 스택에 이 사슬이 찍혀 있었다.

```text
E System  : Unable to load dex files
E System  : java.io.IOException: Bad range
E System  : 	at dalvik.system.DexFile.openInMemoryDexFilesNative(Native Method)
E System  : 	at dalvik.system.DexFile.openInMemoryDexFiles(DexFile.java:393)
E System  : 	at dalvik.system.DexFile.<init>(DexFile.java:121)
E System  : 	at dalvik.system.DexPathList.initByteBufferDexPath(DexPathList.java:264)
E System  : 	at dalvik.system.BaseDexClassLoader.<init>(BaseDexClassLoader.java:226)
E System  : 	at dalvik.system.InMemoryDexClassLoader.<init>(InMemoryDexClassLoader.java:40)
E System  : 	at dalvik.system.InMemoryDexClassLoader.<init>(InMemoryDexClassLoader.java:52)
E System  : 	at dalvik.system.InMemoryDexClassLoader.<init>(InMemoryDexClassLoader.java:63)
E System  : 	at dalvik.system.InMemoryDexClassLoader.<init>(Native Method)
E System  : 	at io.seika.dcl.StubApp.attachBaseContext(StubApp.java:29)
```

줄 번호가 android-13.0.0_r1 소스와 맞고 위임 사슬 63, 52, 40행이 기기 스택으로도 확인된다. `(Native Method)`로 찍힌 생성자가 Frida가 바꿔 끼운 자리다. naive 실행에서 읽은 4888바이트도 매직이 맞았으니, 꺼낸 바이트만 검사해서는 앱이 로드에 실패했다는 걸 알 수 없고 logcat의 `Bad range` 줄을 같이 봐야 한다.

## 늦게 붙었을 때는 로더를 찾아가야 한다

이미 떠 있는 앱에 attach하면 어떻게 되는지도 봤다. 앱을 평소처럼 띄우고 덤프 스크립트와 로더 탐색 스크립트를 차례로 붙였다.

```bash
adb -s $S shell am force-stop io.seika.dcl
adb -s $S shell am start -W -n io.seika.dcl/.MainActivity | grep -E 'Status|TotalTime'
frida -D $S -N io.seika.dcl -l frida/dcl-dump.js -q -t 3
frida -D $S -N io.seika.dcl -l frida/loaders.js -q -t 8
```

`loaders.js`는 먼저 기본 팩토리로 `Core`를 찾아보고 결과를 찍은 뒤 [`Java.enumerateClassLoaders`](https://frida.re/docs/javascript-api/#java)로 로더를 하나씩 돌며 `Core`를 가진 로더를 고른다. 후킹은 그 로더에 묶인 `ClassFactory`로 건다.

```javascript
Java.perform(() => {
  const target = 'io.seika.payload.Core';
  try {
    Java.use(target);
    console.log('[default factory] found ' + target);
  } catch (e) {
    console.log('[default factory] ' + String(e).split('\n')[0].slice(0, 120));
  }

  let holder = null;
  Java.enumerateClassLoaders({
    onMatch(loader) {
      let has = false;
      try { loader.loadClass(target); has = true; } catch (e) { }
      console.log(`[loader]${has ? ' HAS Core ' : ' '}${loader.toString().slice(0, 130)}`);
      if (has && holder === null) holder = loader;
    },
    onComplete() { }
  });
  if (holder === null) return;

  const Core = Java.ClassFactory.get(holder).use(target);
  Core.token.implementation = function () {
    const t = this.token();
    console.log(`[Core.token] -> ${t}`);
    return t;
  };
  console.log('[hooked] Core.token through ' + holder.$className);
});
```

![am force-stop 뒤 am start -W 로 앱을 띄워 Status: ok, TotalTime: 534 를 확인하고, frida -N 으로 늦게 붙인 dcl-dump.js 는 hooks installed 만 찍는다. loaders.js 는 기본 팩토리에서 io.seika.payload.Core 를 못 찾는 ClassNotFoundException, 열거된 로더(directory 점 경로의 PathClassLoader, BootClassLoader, /data/app/~~.../io.seika.dcl-.../ba 에서 잘린 경로의 앱 PathClassLoader, HAS Core 표시가 붙은 InMemoryDexClassLoader InMemoryDexFile cookie, stage2.dex 의 DexClassLoader), hooked Core.token through InMemoryDexClassLoader, Core.token -> SEIKA-eb72f0fd 세 줄을 찍은 터미널](/assets/img/android-mastery/p1c09/05-attach-late-loaders.png)

늦게 붙은 `dcl-dump.js`는 `hooks installed`만 찍고 끝났다. 로드는 이미 지나갔으니 잡을 것이 없다. 기본 팩토리는 앱의 `PathClassLoader`로 찾기 때문에 `Core`에서 ClassNotFoundException이 났다. 열거된 로더 중 `Core`를 가진 것은 `InMemoryDexFile[cookie=...]`를 경로로 둔 `InMemoryDexClassLoader` 하나였다. 2단의 `DexClassLoader`도 목록에 있었는데 그 로더가 가리키는 `stage2.dex`는 이미 디스크에서 지워진 뒤였다. `ClassFactory.get(holder)`로 후킹한 `Core.token`은 `MainActivity`가 3초마다 부르는 `beat`를 타고 8초 동안 세 번 `SEIKA-eb72f0fd`를 돌려줬다.

## ART가 따로 복사해 둔 사본

attach로는 로드 순간을 놓쳤지만 dex는 아직 메모리에 있다. ART가 버퍼를 `[anon:dalvik-DEX data]` 익명 매핑에 복사해 두고 열기가 끝나면 읽기 전용으로 돌린다는 건 [4장](/posts/android-lab-p1c04-jadx-static-analysis/)에서 소스로 따라갔다. 4장의 스텁은 `ByteBuffer.wrap`으로 배열을 넘겨 배열에서 복사하는 갈래를 탔고, 이번 스텁은 direct 버퍼를 넘기니 그 주소에서 바로 `memcpy`하는 갈래([274~283행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/native/dalvik_system_DexFile.cc#274))를 탄다. 스텁이 자기 버퍼를 0으로 덮은 뒤에도 사본이 남는지, attach 실험을 한 프로세스를 그대로 두고 maps에서 찾았다.

```bash
adb -s $S shell 'grep "dalvik-DEX data" /proc/$(pidof io.seika.dcl)/maps'
frida -D $S -N io.seika.dcl -l frida/memscan.js -q -t 1
sha256sum out/stage1.dex
```

`memscan.js`는 `/proc/self/maps`에서 그 이름의 줄을 골라, 매핑 시작점의 dex 헤더에서 `file_size`(0x20)를 읽고 그만큼만 저장한다.

```javascript
const OUT = '/data/data/io.seika.dcl/files/dumps';
Java.perform(() => {
  Java.use('java.io.File').$new(OUT).mkdirs();
  File.readAllText('/proc/self/maps').split('\n')
    .filter(l => l.includes('dalvik-DEX data'))
    .forEach(l => {
      const [range, perms] = l.split(/\s+/);
      const base = ptr('0x' + range.split('-')[0]);
      const head = new Uint8Array(base.readByteArray(8));
      const size = base.add(0x20).readU32();          // dex header file_size
      const data = base.readByteArray(size);
      const path = `${OUT}/maps-${range.split('-')[0]}-${size}.dex`;
      File.writeAllBytes(path, data);
      const m = Array.from(head, b => b === 10 ? '\\n' : b === 0 ? '\\0' : String.fromCharCode(b)).join('');
      console.log(`${range} ${perms} magic=${m} file_size=${size} sha256=${Checksum.compute('sha256', data).slice(0, 16)}... -> ${path}`);
    });
});
```

![adb shell 로 /proc/PID/maps 를 grep 해 752c7daa0000-752c7daa2000 r--p 권한의 anon:dalvik-DEX data 매핑 하나를 찾고, frida -N 으로 memscan.js 를 붙여 같은 범위에서 magic=dex\n038\0 file_size=4888 sha256=a15c99b46de4fa48... 을 읽어 files/dumps/maps-752c7daa0000-4888.dex 로 저장했으며, 호스트의 sha256sum out/stage1.dex 가 a15c99b46de4fa48 로 시작해 일치하는 터미널](/assets/img/android-mastery/p1c09/06-memory-copy.png)

매핑은 두 페이지(0x2000)짜리 하나이고, 바이트코드를 담은 데이터 영역이라 권한은 실행 없이 `r--p`다. maps에서 실행 가능한 익명 영역만 훑는 방식으로는 이 사본을 놓친다. 헤더의 `file_size`는 4888이고 SHA-256 앞 16자리가 `out/stage1.dex`와 같다. 스텁이 자기 버퍼를 지운 다음이니 이건 ART의 사본이다. [4장](/posts/android-lab-p1c04-jadx-static-analysis/)의 `memdex.sh`로 같은 프로세스의 `/proc/PID/mem`을 Frida 없이 떠도 8192바이트를 4888바이트로 잘라 같은 해시가 나왔다.

```bash
bash scripts/memdex.sh $S io.seika.dcl memdump
sha256sum memdump/*.dex out/stage1.dex
adb -s $S shell 'rm /data/local/tmp/memdex-*.bin'
```

```text
/data/local/tmp/memdex-6169-752c7daa0000.bin: 1 file pulled, 0 skipped. 4.4 MB/s (8192 bytes in 0.002s)
memdump/memdex-6169-752c7daa0000.dex b'dex\n038\x00' 4888 bytes
a15c99b46de4fa484c51728a9d1ebe56374059d9093f2fba3f76b7a6763abf4c *memdump/memdex-6169-752c7daa0000.dex
a15c99b46de4fa484c51728a9d1ebe56374059d9093f2fba3f76b7a6763abf4c *out/stage1.dex
```

2단 파일은 사정이 다르다. 숨은 API 실험에서 `hiddenapi.js`로 마지막에 spawn한 프로세스(Frida가 붙은 채 뜬 지 16초쯤)의 maps를 떠 보니 지워진 파일이 아직 매핑돼 있었다.

```text
752c7d864000-752c7d865000 r--p 00000000 fe:22 148675                     /data/data/io.seika.dcl/files/s2/stage2.dex (deleted)
752c7d8a6000-752c7d8a7000 rw-p 00000000 fe:22 149134                     /data/data/io.seika.dcl/files/s2/oat/x86_64/stage2.vdex
752c7d8a8000-752c7d8a9000 rw-p 00000000 fe:22 149122                     /data/data/io.seika.dcl/oat/x86_64/Anonymous-DexFile@1733560294.vdex
752c7d8fd000-752c7d8ff000 r--p 00000000 00:00 0                          [anon:dalvik-DEX data]
```

`/proc/PID/map_files`로 그 지워진 파일을 읽어 오려 했는데 25초쯤 뒤 같은 프로세스에서 다시 보니 `stage2.dex (deleted)`와 `stage2.vdex` 줄이 이미 사라져 있었다. 1단은 `Core.stage2`의 지역 변수로만 `DexClassLoader`를 들고 있으니 그 로더가 GC되면서 dex가 닫힌 것으로 보인다. 원인까지 확인하지는 못했다. 스텁이 필드로 붙잡고 있는 1단의 `DEX data` 매핑과 익명 vdex는 그때도 남아 있었다.

## 디스크와 PackageManager에 남는 것

메모리에서만 올렸다고 디스크에 아무것도 안 남는 건 아니다. spawn 덤프 뒤로 생성자 후킹 실험과 attach 실험에서 앱을 여러 번 더 띄웠고, 메모리 사본까지 확인한 다음 데이터 디렉터리부터 열었다.

```bash
adb -s $S shell ls -lR /data/user/0/io.seika.dcl/files/s2 /data/user/0/io.seika.dcl/oat
adb -s $S shell 'xxd -l 64 /data/user/0/io.seika.dcl/oat/x86_64/Anonymous-DexFile@*.vdex'
python -c "import struct; print(struct.unpack('<I', open('out/stage1.dex','rb').read()[8:12])[0])"
```

![adb shell ls -lR 결과 files/s2 에는 stage2.dex 가 없고 oat/stage2.dex.cur.prof(0 바이트)와 oat/x86_64/stage2.vdex(92 바이트)만 있으며, 앱 데이터 디렉터리의 oat/x86_64 에 Anonymous-DexFile@1733560294.vdex(96 바이트)가 있고 시각은 모두 02:09 다. xxd -l 64 로 본 그 vdex 는 vdex027 로 시작하고 0x3c 에 e607 5467 이 있으며, python 으로 읽은 out/stage1.dex 헤더 checksum 은 1733560294 인 터미널](/assets/img/android-mastery/p1c09/07a-disk-files-vdex.png)

`files/s2`에 `stage2.dex`는 없지만 `oat/stage2.dex.cur.prof`(0바이트)와 `oat/x86_64/stage2.vdex`(92바이트)가 남았다. 메모리로만 올린 1단도 `oat/x86_64/Anonymous-DexFile@1733560294.vdex`(96바이트)를 남겼다. 시각은 모두 02:09, spawn 덤프를 돌린 첫 실행 때다. 그 뒤 실행에서는 다시 쓰이지 않았다.

익명 vdex는 백그라운드 검증의 결과물이다. `BaseDexClassLoader`가 로더를 만든 뒤 `maybeRunBackgroundVerification`을 부르고 ART의 [`RunBackgroundVerification`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/oat_file_manager.cc#729)이 검증 결과를 vdex로 쓴다. Java 디버깅이 가능한 프로세스(734행), targetSdk 29 미만인 앱(755행), dex 위치가 앱 데이터 디렉터리 밖인 경우(772행)에는 건너뛴다. 파일 이름은 아래 함수가 정한다.

![android-13.0.0_r1 art oat_file_assistant.cc 467~500행. 473행 OatFileAssistant::AnonymousDexVdexLocation 이 강조돼 있고, 477~482행이 각 dex 헤더의 checksum_ 을 adler32_combine 으로 합치며, 489행 StringPrintf 로 data_dir 아래에 kAnonymousDexPrefix 와 checksum 을 붙인 .jar 위치를 만들고, 498행 GetVdexFilename 으로 vdex 이름을 얻는 소스 화면](/assets/img/android-mastery/p1c09/15-src-anonymous-vdex.png)

dex 헤더의 checksum들을 `adler32_combine`으로 합친 값에 [`Anonymous-DexFile@` 접두사](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/oat_file_assistant.cc#55)를 붙여 데이터 디렉터리 아래 가상의 `.jar` 위치를 만들고 거기서 vdex 이름을 뽑는다. dex가 하나면 그 dex의 헤더 checksum이 그대로 이름이 된다. 호스트에서 `stage1.dex`의 8~12바이트를 읽으면 1733560294이고 vdex의 0x3c에 리틀 엔디언으로 박힌 `e607 5467`도 같은 값(0x675407e6)이다. 덤프를 손에 넣었다면 이 이름과 맞춰 볼 수 있다.

내용물에 dex는 없다. [`VdexFile::WriteToDisk`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/vdex_file.cc#267)는 `has_dex_section=false`로 헤더를 만들고 dex 섹션의 오프셋과 크기를 0으로 둔다. 두 vdex를 호스트로 가져와 섹션 헤더를 풀었다. [vdex 027 헤더](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/vdex_file.h#123)는 매직과 버전 다음 0x8에 섹션 수를 두고(123~131행), 0xc부터 섹션마다 종류, 오프셋, 크기를 u32 세 개로 적는다(92~95행). [섹션 종류](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/vdex_file.h#80) 0은 dex마다 checksum 하나, 1은 dex 자체, 2는 검증 의존성, 3은 타입 조회 테이블이다.

```bash
mkdir -p vdex
adb -s $S pull /data/user/0/io.seika.dcl/oat/x86_64/Anonymous-DexFile@1733560294.vdex vdex/
adb -s $S pull /data/user/0/io.seika.dcl/files/s2/oat/x86_64/stage2.vdex vdex/
python scripts/vdexsec.py vdex/Anonymous-DexFile@1733560294.vdex vdex/stage2.vdex out/stage2.dex
```

```python
# scripts/vdexsec.py
import struct, sys
for path in sys.argv[1:]:
    if path.endswith('.dex'):                  # a dex for comparison: header checksum at 0x8
        d = open(path, 'rb').read()
        print(path.split('/')[-1], 'header checksum', struct.unpack_from('<I', d, 8)[0])
        continue
    d = open(path, 'rb').read()                # vdex 027: magic, version, section count at 0x8
    print(path.split('/')[-1], len(d), 'bytes magic', d[:4], 'version', d[4:8])
    secs = [struct.unpack_from('<3I', d, 0xc + 12 * i) for i in range(struct.unpack_from('<I', d, 8)[0])]
    for kind, off, size in secs:               # (kind, offset, size) triples from 0xc
        print(f'  section kind {kind} offset {off:#x} size {size}')
    off, size = secs[0][1:]                    # kind 0 = dex checksums, one u32 per dex
    print('  checksum section values:', list(struct.unpack_from(f'<{size // 4}I', d, off)))
```

```text
Anonymous-DexFile@1733560294.vdex 96 bytes magic b'vdex' version b'027\x00'
  section kind 0 offset 0x3c size 4
  section kind 1 offset 0x0 size 0
  section kind 2 offset 0x40 size 20
  section kind 3 offset 0x54 size 12
  checksum section values: [1733560294]
stage2.vdex 92 bytes magic b'vdex' version b'027\x00'
  section kind 0 offset 0x3c size 4
  section kind 1 offset 0x0 size 0
  section kind 2 offset 0x40 size 16
  section kind 3 offset 0x50 size 12
  checksum section values: [3037707347]
stage2.dex header checksum 3037707347
```

kind 1(dex 섹션)은 둘 다 크기가 0이다. 남은 건 checksum, 검증 의존성(20바이트, 16바이트), 타입 조회 테이블(12바이트)뿐이라 코드를 되살릴 수는 없다. 대신 이 앱이 어떤 dex를 올렸는지, 메모리로만 올린 것까지 가리키는 지문으로는 쓸 만하다. 경로의 `x86_64`는 명령어 집합별 디렉터리라 ARM 기기에서는 이름이 다를 것이다(x86_64 에뮬레이터에서만 봤다).

PackageManager가 아는 것도 둘이 다르다. 같은 시점의 dexopt 기록에 그 차이가 그대로 찍혀 있다.

```bash
adb -s $S shell dumpsys package dexopt | grep -A5 'io.seika.dcl\]'
```

![dumpsys package dexopt 의 io.seika.dcl 항목에 base.apk 경로와 x86_64 status=verify, known secondary dex files 로 /data/user/0/io.seika.dcl/files/s2/stage2.dex 와 class loader context PCL[];PCL[base.apk] 가 있고 메모리로 올린 1단은 없는 터미널](/assets/img/android-mastery/p1c09/07b-dumpsys-secondary-dex.png)

`dumpsys package dexopt`는 지워진 `stage2.dex`를 `known secondary dex files`로 들고 있고 `class loader context: PCL[];PCL[.../base.apk]`까지 적었다. 1단은 목록에 없다. 파일 경로를 받는 `BaseDexClassLoader` 생성자는 끝에서 `reportClassLoaderChain()`을 부르고([168행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/BaseDexClassLoader.java#168)) ByteBuffer 생성자에는 그 호출이 없다([221~229행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/BaseDexClassLoader.java#221)).

보고를 받는 쪽은 [`LoadedApk`가 앱 프로세스에 설치한](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/app/LoadedApk.java#1013) `DexLoadReporter`다. 이 클래스는 PackageManager에 알리고([97행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/app/DexLoadReporter.java#97)) `dalvik.vm.dexopt.secondary`가 켜져 있으면 dex 옆 `oat/` 아래에 `<이름>.cur.prof`를 만든다([114~157행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/app/DexLoadReporter.java#114)). 이 이미지는 그 속성이 `true`였고 0바이트 `.cur.prof`가 그 결과다. dumpsys 출력은 [`PackageDexOptimizer` 762~773행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/services/core/java/com/android/server/pm/PackageDexOptimizer.java#762)이 찍는다. `DexManager`는 같은 보고를 `DynamicCodeLogger`에도 넘기는데([267~271행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/services/core/java/com/android/server/pm/dex/DexManager.java#267)) 그 기록까지 꺼내 보지는 않았다.

`DexClassLoader`의 두 번째 인자 `optimizedDirectory`는 API 26부터 효과가 없다([DexClassLoader.java 47행](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/DexClassLoader.java#47), 생성자는 55행에서 null을 넘긴다). 1단도 null을 넘겼고 vdex는 dex 옆 `oat/x86_64/`에 생겼다.

## 리플렉션 경계와 숨은 API

spawn 트레이스에는 `Method.invoke`가 두 번 찍혔다. `MainActivity`가 `Core.run`을, 1단이 `Beacon.ping`을 부른 자리다. 스텁은 컴파일할 때 자기 dex에 없는 클래스를 직접 참조할 수 없으니 로더 경계는 리플렉션으로 넘는다. `Method.invoke`를 후킹하고 선언 클래스로 거르면 단계 사이의 호출 흐름이 보인다. `dcl-trace.js`는 3초마다 불리는 `beat`만 걸렀다.

1단은 리플렉션으로 숨은 API인 `VMRuntime.setHiddenApiExemptions`도 찾아본다. 언패킹 코드가 숨은 API에 손을 대는 경우를 흉내 낸 것이다. 그냥 실행, 아무것도 바꾸지 않는 Frida 스크립트(`noop.js`), 예외를 거는 스크립트(`hiddenapi.js`)를 차례로 돌렸다. `hiddenapi.js`는 이렇다.

```javascript
// hiddenapi.js
Java.perform(() => {
  const VMRuntime = Java.use('dalvik.system.VMRuntime');
  VMRuntime.getRuntime().setHiddenApiExemptions(Java.array('java.lang.String', ['L']));
  console.log('[hiddenapi] VMRuntime.getRuntime().setHiddenApiExemptions(["L"]) done');
});
```

```bash
adb -s $S shell am force-stop io.seika.dcl; adb -s $S logcat -c
adb -s $S shell am start -W -n io.seika.dcl/.MainActivity | grep Status
adb -s $S logcat -d -v tag | grep -E 'Accessing hidden|hidden api lookup'
adb -s $S shell am force-stop io.seika.dcl; adb -s $S logcat -c
frida -D $S -f io.seika.dcl -l frida/noop.js -q -t 4
adb -s $S logcat -d -v tag | grep -E 'Accessing hidden|hidden api lookup'
adb -s $S shell am force-stop io.seika.dcl; adb -s $S logcat -c
frida -D $S -f io.seika.dcl -l frida/hiddenapi.js -q -t 4
adb -s $S logcat -d -v tag | grep -E 'Accessing hidden|hidden api lookup'
```

![그냥 실행한 앱과 noop.js 로 spawn 한 앱 모두 logcat 에 Accessing hidden method Ldalvik/system/VMRuntime;->setHiddenApiExemptions(...)V (blocked,core-platform-api, reflection, denied) 와 hidden api lookup failed: java.lang.NoSuchMethodException 이 찍히고, hiddenapi.js 로 setHiddenApiExemptions 에 L 을 건 실행에서는 hidden api lookup ok: public native void dalvik.system.VMRuntime.setHiddenApiExemptions(java.lang.String 배열) 한 줄만 남은 터미널](/assets/img/android-mastery/p1c09/09-hiddenapi.png)

그냥 실행하면 ART가 `blocked,core-platform-api` 목록의 멤버를 `reflection`으로 접근하려 했다며 `denied`를 찍는다. 앱 쪽에서는 그런 메서드가 없다는 듯 `NoSuchMethodException`이 난다. Frida를 붙이기만 한 `noop.js` 실행도 똑같았다. 예외를 건 실행에서는 조회가 성공했고 logcat에도 ART 쪽 줄이 하나도 남지 않았다.

[`hidden_api.cc`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/hidden_api.cc#71)를 보면 접근 방법은 리플렉션, JNI, 링킹으로 나뉘고(71~86행) 예외 접두사에 걸린 멤버는 공개 API처럼 취급하며 경고도 남기지 않는다(582~589행). 거부된 접근은 항상 로그를 남긴다(614~621행). `setHiddenApiExemptions`는 [`@hide`이면서 `@SystemApi(client = MODULE_LIBRARIES)`](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/libart/src/main/java/dalvik/system/VMRuntime.java#506)라 앱이 쓰는 SDK에 들어 있지 않고, 로그에 찍힌 대로 `blocked` 목록에 올라 있다. 그래서 앱이 리플렉션으로 찾으면 첫 실행처럼 거부된다. Frida는 같은 프로세스 안에서 브리지로 이 메서드를 불렀고 통했다. 반대로 보면 `Accessing hidden` 줄이 없다고 숨은 API 접근이 없었던 것도 아니다. 예외에 걸린 접근은 위에서 본 대로 조용히 지나가고, 거부되지 않은 접근도 디버깅 가능한 앱이 아니면 로그를 남기지 않는다(619행).

## Android 14 읽기 전용 규칙이 보는 곳

Android 14 동작 변경 문서의 [안전한 동적 코드 로딩](https://developer.android.com/about/versions/14/behavior-changes-14#safer-dynamic-code-loading) 항목은 targetSdk 34 이상 앱이 동적으로 로드하는 파일을 읽기 전용으로 두라고 하면서 쓰기 전에 읽기 전용으로 표시하라고 권한다. 앱이 쓴 파일을 로드 전에 누가 바꿔치기하는 경로를 막으려는 규칙이다. 1단의 `stage2`는 그 권고를 따르는 분기를 인텐트 extra로 켤 수 있게 짰다.

```java
// payload1/src/io/seika/payload/Core.java 31~57행
    static String stage2(Context ctx, boolean readOnly) {
        File f = new File(ctx.getFilesDir(), "s2/stage2.dex");
        f.getParentFile().mkdirs();
        f.delete();
        try {
            byte[] dex = read(ctx.getAssets().open("s2.bin"));
            for (int i = 0; i < dex.length; i++) dex[i] ^= K2[i % K2.length];
            FileOutputStream os = new FileOutputStream(f);
            try {
                if (readOnly) f.setReadOnly(); // Android 14 guidance: mark read-only before writing
                os.write(dex);
            } finally {
                os.close();
            }
            Log.i(TAG, "stage2 written: " + f + " (" + dex.length + " bytes, writable=" + f.canWrite() + ")");
            DexClassLoader dcl = new DexClassLoader(f.getPath(), null, null, ctx.getClassLoader());
            Class<?> b = dcl.loadClass("io.seika.payload2.Beacon");
            String r = (String) b.getMethod("ping").invoke(null);
            Log.i(TAG, "stage2 says: " + r);
            return r;
        } catch (Throwable t) {
            Log.e(TAG, "stage2 failed: " + t);
            return "failed: " + t.getClass().getSimpleName();
        } finally {
            Log.i(TAG, "stage2 file deleted: " + f.delete());
        }
    }
```

검사 위치는 android-14.0.0_r1의 [`openDexFileNative` 380~389행](https://android.googlesource.com/platform/art/+/refs/tags/android-14.0.0_r1/runtime/native/dalvik_system_DexFile.cc#380)이다. 파일에 쓰기 권한이 있으면 먼저 `Attempt to load writable dex file:`을 ERROR로 남긴다. 강제 조건까지 맞으면 `Writable dex file '%s' is not allowed.`로 `SecurityException`을 던진다. 강제 조건은 기기 API가 33보다 크거나 33이면서 U 프리뷰 빌드이고([317~345행](https://android.googlesource.com/platform/art/+/refs/tags/android-14.0.0_r1/runtime/native/dalvik_system_DexFile.cc#317)) 호환성 변경 218865702가 켜져 있을 때다. 이 변경은 [`@EnabledAfter(targetSdkVersion = TIRAMISU)`](https://android.googlesource.com/platform/libcore/+/refs/tags/android-14.0.0_r1/dalvik/src/main/java/dalvik/system/DexFile.java#75)라 targetSdk 34 이상에서 켜진다. root, system, shell UID는 검사 자체에서 빠진다([353~364행](https://android.googlesource.com/platform/art/+/refs/tags/android-14.0.0_r1/runtime/native/dalvik_system_DexFile.cc#353)). 같은 파일의 `openInMemoryDexFilesNative`에는 이런 검사가 없다. 측정에 쓴 API 36 이미지와 같은 세대인 [android-16.0.0_r1 태그](https://android.googlesource.com/platform/art/+/refs/tags/android-16.0.0_r1/runtime/native/dalvik_system_DexFile.cc#380)에서도 이 코드는 380~389행에 그대로 있다. API 36 에뮬레이터에서 targetSdk 34 빌드와 33 빌드를 바꿔 가며 돌렸다(`S`는 이 보조 에뮬레이터 시리얼로 바꿨다).

```bash
adb -s $S uninstall io.seika.dcl
adb -s $S shell getprop ro.build.version.sdk
adb -s $S install out/dcl-t34.apk
adb -s $S logcat -c; adb -s $S shell am start -W -n io.seika.dcl/.MainActivity | grep Status
adb -s $S logcat -d -v tag | grep -E 'stage1 loaded|stage2 (written|says|failed)|writable dex'
adb -s $S shell am force-stop io.seika.dcl; adb -s $S logcat -c
adb -s $S shell am start -W -n io.seika.dcl/.MainActivity --ez ro true | grep Status
adb -s $S logcat -d -v tag | grep -E 'stage1 loaded|stage2 (written|says|failed)|writable dex'
adb -s $S uninstall io.seika.dcl; adb -s $S install out/dcl.apk
adb -s $S logcat -c; adb -s $S shell am start -W -n io.seika.dcl/.MainActivity | grep Status
adb -s $S logcat -d -v tag | grep -E 'stage1 loaded|stage2 (written|says|failed)|writable dex'
```

![API 36 에뮬레이터에서 getprop ro.build.version.sdk 가 36. targetSdk 34 빌드 기본 실행은 stage1 loaded from a 4888-byte direct buffer, stage2 written writable=true, E Attempt to load writable dex file, stage2 failed: java.lang.SecurityException: Writable dex file ... is not allowed. --ez ro true 실행은 writable=false 와 stage2 says: pong. targetSdk 33 인 dcl.apk 로 바꿔 깐 실행은 writable=true 에 같은 ERROR 줄이 찍히지만 stage2 says: pong 이 나온 터미널](/assets/img/android-mastery/p1c09/10-api36-readonly.png)

targetSdk 34 빌드는 파일이 쓰기 가능하면 ERROR 줄 다음에 `SecurityException`으로 2단이 막혔고, 쓰기 전에 읽기 전용으로 표시하면 `writable=false`로 로드됐다. targetSdk 33 빌드는 같은 기기에서 ERROR 줄만 남기고 그대로 올라갔다. 1단의 메모리 로드는 세 실행 어디서도 영향을 받지 않았다. API 33 이미지에서 spawn 덤프를 돌린 첫 실행의 logcat은 `writable dex`로 grep해도 한 줄도 나오지 않았다. android-13.0.0_r1의 `dalvik_system_DexFile.cc`에는 이 검사가 아예 없고, 그 이미지의 ART 모듈(331711080)도 2단 파일을 쓰기 가능한 채로 올리는 이 앱에 경고를 남기지 않았다.

## 동적 로딩을 쓰는 앱에서 확인할 것

동적 로딩을 직접 써야 하는 앱이라면 targetSdk를 올리기 전에 지금 빌드를 API 34 이상 기기에서 돌려 본다. targetSdk 33이어도 `Attempt to load writable dex file`이 ERROR로 찍히니 이 줄만 찾으면 된다. 자기 앱이 로드하는 파일은 QA 때 `dumpsys package dexopt`의 secondary dex 목록으로 확인할 수 있다. 메모리 로드는 거기 잡히지 않고, 디버그 빌드로 QA를 하면 익명 vdex도 생기지 않는다(이 부분은 소스로만 확인했다).

파일은 앱 전용 디렉터리에 두고 쓰기 전에 `setReadOnly()`를 부르되, 처음부터 바꿔치기된 바이트는 이 표시로 걸러지지 않으니 로드 전에 서명이나 해시를 따로 확인한다. Google Play는 [기기 및 네트워크 악용 정책](https://support.google.com/googleplay/android-developer/answer/9888379)에서 Play 밖에서 dex, JAR, .so 같은 실행 코드를 내려받는 것을 금지한다.

*다음 글: [JNI·native 함수 동적 관찰](/posts/android-lab-p1c10-jni-native-observation/)*
