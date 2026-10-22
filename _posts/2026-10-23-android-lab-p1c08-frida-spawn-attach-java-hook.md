---
layout: post
title: "Frida spawn·attach와 Java 훅 — 붙는 시점과 훅이 새는 길"
date: 2026-10-23 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Frida, DynamicAnalysis, JavaHook, ART, Zygote, Deoptimization]
excerpt: "Android 13 에뮬레이터에서 spawn은 앱의 첫 static 초기화부터 반환값을 바꿨고 attach는 시작 코드를 놓쳤다. 다만 spawn으로 건 static 훅은 클래스 초기화 뒤 GC 전까지 빠졌고, AOT 코드에 인라인된 호출은 호출자를 직접 deopt해야 잡혔다."
---

[지난 글](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)에서는 APK 안의 문자열을 고치고 다른 키로 다시 서명했다. 파일을 바꾸는 길이라 서명이 달라지고 서명을 확인하는 앱이라면 거기서 걸린다. Frida는 파일을 건드리지 않는다. 실행 중인 프로세스에 에이전트를 올려 Java 메서드 구현을 바꿔 끼운다. 이번에 붙들고 있던 질문은 에이전트가 앱 코드보다 먼저 들어가느냐, 그리고 바꿔 끼운 메서드를 앱 코드가 정말 거쳐 가느냐였다. 앞의 질문은 spawn과 attach의 차이로 갈렸고, 뒤의 질문은 ART가 그 메서드를 어떤 경로로 부르느냐에 달려 있었다.

기기는 `codex-atlas-api33` 에뮬레이터다(Android 13, API 33, google_apis x86_64 userdebug, 보안 패치 2024-03-01, SELinux Enforcing, ART 모듈 versionCode 331711080). 호스트에는 Frida 17.17.0과 frida-tools 14.8.1을, 기기에는 같은 버전의 frida-server x86_64 빌드를 썼다. 결과가 ART 버전에 따라 갈린 대목에서만 Android 16 에뮬레이터 `sec-36-std`(API 36, ART 모듈 360527520)를 잠깐 띄웠다. Frida 쪽 동작은 [frida-core 17.17.0](https://github.com/frida/frida-core/tree/17.17.0), frida-tools 14.8.1이 싣고 다니는 [frida-java-bridge v7.0.12](https://github.com/frida/frida-java-bridge/tree/v7.0.12), [frida-tools 14.8.1](https://github.com/frida/frida-tools/tree/14.8.1) 태그의 소스로 확인했다. AOSP 링크는 `android-13.0.0_r84` 태그로 걸었는데, 측정한 이미지(TE1A.240213.009)가 그보다 나중 빌드라 스택 트레이스의 줄 번호가 링크한 소스와 몇 줄씩 어긋나는 곳이 있다. ART는 mainline 모듈(331711080)로 업데이트된 것이라 링크한 r84 ART 소스와 빌드가 정확히 같지는 않은데, 인용한 분기는 측정 결과와 맞았다.

## 시작 단계마다 라이선스를 묻는 실습 앱

대상은 직접 만든 `io.seika.fridalab`(라벨 "Frida Lab", minSdk 26, targetSdk 33)이고 debuggable 플래그 없이 빌드했다. 바꿔 끼울 메서드는 늘 false를 내는 로컬 라이선스 게이트다.

```java
package io.seika.fridalab;

/** Local license gate (lab target). Always false unless something changes it at runtime. */
public final class Gate {
    private static final String LICENSE = "TRIAL-0000";

    public static boolean checkLicense() {
        return LICENSE.hashCode() == 0x5eed1ab;
    }
}
```

`Stage.log(where)`는 이 게이트의 결과와 함께 `/proc/self/maps`에서 "frida"가 든 줄 수(`frida_maps`)와 `/proc/self/task/*/comm`에서 Frida 에이전트 스레드로 보이는 이름 수(`frida_thr`)를 logcat 태그 `fridalab`으로 남긴다. 값은 앱들이 흔히 넣는 단순한 안티 Frida 검사를 흉내 낸 `Probe` 클래스가 센다. 처음 빌드에서는 패키지 이름 자체에 frida가 들어 있다는 걸 잊어서, Frida 없이 띄워도 `frida_maps=5 frida_thr=1`이 찍혔다. 자기 APK·oat 경로와 15자로 잘린 자기 메인 스레드 이름(`.seika.fridalab`)을 빼도록 고친 뒤로는 Frida 없이 띄우면 둘 다 0이다.

`Stage.log`를 부르는 곳은 앱 프로세스가 올라오는 순서를 따라 깔았다. `App`의 static 초기화 블록(`App.<clinit>`), `App.attachBaseContext`, `ContentProvider`인 `EarlyProvider`의 `onCreate`, `App.onCreate`, `MainActivity.onCreate` 순이다. 그 밖에 adb로 부를 수 있는 리시버 `Cmd`(`am broadcast -n io.seika.fridalab/.Cmd --es op check`처럼 쓴다), 인라인 실험용 `Hot`, 오버로드 실험용 `Codec`, 런타임 난수 키를 쥔 `Vault`가 들어 있다. 빌드한 APK는 `adb install -r out/fridalab.apk`로 깔았고 설치 직후 dexopt 상태는 `verify`였다.

## frida-server는 adb root로 띄운다

frida-server 바이너리는 기기 ABI에 맞춰 고른다. 이 에뮬레이터의 `ro.product.cpu.abilist`는 `x86_64` 하나다. 띄우는 명령으로 자주 보이는 `adb shell "su -c /data/local/tmp/frida-server &"`는 여기서 `su`에 막힌다. AOSP userdebug 이미지의 `su`는 사용법이 [`su [WHO [COMMAND...]]`](https://android.googlesource.com/platform/system/extras/+/refs/tags/android-13.0.0_r84/su/su.cpp#90)이고 첫 인자를 무조건 사용자로 읽는다([108행](https://android.googlesource.com/platform/system/extras/+/refs/tags/android-13.0.0_r84/su/su.cpp#108)). `-c`는 사용자 이름도 숫자도 아니어서 [38행](https://android.googlesource.com/platform/system/extras/+/refs/tags/android-13.0.0_r84/su/su.cpp#38)의 `invalid uid/gid` 오류로 끝난다. `su -c`는 Magisk 같은 루팅 도구가 깔아 주는 `su`의 문법이고 [Frida 문서](https://frida.re/docs/android/)도 adbd를 root로 돌릴 수 없는 production 빌드에서 쓰는 방법으로 소개한다. userdebug 이미지라면 `su 0 id`처럼 사용자를 먼저 주거나 `adb root`로 adbd를 root로 다시 띄우면 된다.

![adb -s $S shell su -c id 가 su: invalid uid/gid '-c' 로 실패하고 su 0 id 는 uid=0(root) ... context=u:r:su:s0 를 출력. adb root 가 restarting adbd as root, frida-server --version 이 17.17.0, stdin 을 /dev/null 로 돌린 frida-server -D 로 띄운 프로세스가 ps -A -Z 에서 레이블 u:r:su:s0 의 root 10658 frida-server, 호스트 frida --version 17.17.0, frida-ps -ai 결과는 Name 'Frida Lab' Identifier 'io.seika.fridalab'](/assets/img/android-mastery/p1c08/02-server-setup.png)

기본 AVD에는 frida-server가 이미 `/data/local/tmp`에 올라가 있어서 위 캡처에서는 `adb root`부터 쳤다. 바이너리가 없는 기기라면 그 사이에 push와 `chmod 755`가 들어간다. Android 16 에뮬레이터(`emulator-5622`)에는 호스트에 미리 풀어 둔 17.17.0 사본을 이렇게 올렸다. [Frida 릴리스](https://github.com/frida/frida/releases)에서 받는 `frida-server-17.17.0-android-x86_64.xz`는 xz로 묶여 있으니 처음 받았다면 호스트에서 `unxz`로 먼저 풀어야 한다(이번 작업에서는 이미 풀린 사본을 썼다). 에뮬레이터가 여러 대 붙어 있어서 adb는 `-s`, Frida는 `-D`에 adb 시리얼을 줬다. 기기가 하나뿐이면 Frida 쪽은 `-U`로 충분하다.

```bash
S=emulator-5602
# 릴리스 .xz 를 처음 받았다면 먼저 푼다
unxz frida-server-17.17.0-android-x86_64.xz
adb -s $S root
adb -s $S wait-for-device
# 기기에 바이너리가 없을 때만 (이번에는 emulator-5622 에서 실행)
adb -s $S push frida-server-17.17.0-android-x86_64 /data/local/tmp/frida-server
adb -s $S shell chmod 755 /data/local/tmp/frida-server
adb -s $S shell /data/local/tmp/frida-server --version
adb -s $S shell "/data/local/tmp/frida-server -D </dev/null"
adb -s $S shell ps -A -Z -o LABEL,USER,PID,NAME | grep frida-server
frida-ps -D $S -ai | grep -E "Identifier|fridalab"
```

`-D`는 frida-server 17.17.0의 `--help`에 있는 `--daemonize`다. 처음에는 `adb shell /data/local/tmp/frida-server -D`로 쳤는데 데몬이 `ps`에 뜬 뒤에도 adb가 돌아오지 않아 20초 타임아웃에 걸렸다. stdout과 stderr만 `/dev/null`로 돌려도 똑같이 20초를 채웠고 stdin을 `/dev/null`로 돌리자 0.6초 만에 돌아왔다. 열린 stdin이 왜 adb 세션을 붙잡는지까지는 파지 않았다.

frida-server는 `u:r:su:s0` 레이블로 돌았다. `/data/local/tmp`에서 실행하는 걸 SELinux가 막는 일은 이 userdebug 이미지에서 생기지 않았다. user 빌드에서 막히는 건 root가 없다는 점이고 그때는 앱에 frida-gadget을 넣고 [지난 글](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)처럼 다시 서명하는 길로 간다(이번에 돌려 보지는 않았다).

호스트 `frida`와 frida-server는 둘 다 17.17.0으로 맞췄다. 꼭 같아야 하는지 보려고 일부러 어긋나게도 붙여 봤다. `venv16`은 Frida 16.7.19를 깐 파이썬 가상환경이다.

```text
$ venv16/Scripts/frida --version
16.7.19
$ venv16/Scripts/frida-ps -D $S -a 2>&1 | grep -E "Identifier|fridalab|Failed"
Failed to enumerate applications: unable to communicate with remote frida-server; please ensure that major versions match and that the remote Frida has the feature you are trying to use
$ venv16/Scripts/frida -D $S -N io.seika.fridalab -q -e "Process.arch"
Failed to attach: unable to communicate with remote frida-server; please ensure that major versions match and that the remote Frida has the feature you are trying to use
$ frida -D $S -N io.seika.fridalab -q -e "Process.arch"
"x64"
```

메이저 버전이 다르면 앱 목록부터 실패했다. 반대로 서버만 17.9.1로 내리고 17.17.0 클라이언트로 붙였을 때는 `frida-ps`, attach, 아래에서 쓸 Java 훅까지 모두 됐다. 이때 대상 프로세스에는 뒤에 나오는 attach 실험에서 eternalize한 17.17.0 에이전트가 남아 있었다. 위 오류 문구는 frida-core가 원격에 없는 D-Bus 메서드를 불렀을 때 내는 것이다([session.vala 1292~1296행](https://github.com/frida/frida-core/blob/17.17.0/lib/base/session.vala#L1292-L1296)). 조건은 같은 메이저 버전, 그리고 쓰려는 기능이 서버 쪽에 있는 것이다. 마이너 버전이 달라도 되는 조합은 확인했지만 모든 기능을 대 보지는 않았고, 실습에서는 버전을 정확히 맞춰 두는 편이 마음 편하다.

## spawn은 zygote 자식을 setArgV0 안에 세워 둔다

spawn 예제로 흔히 보이는 `frida -U -f <패키지> -l hook.js --no-pause`도 지금 도구에서는 돌지 않는다. [frida-tools 커밋 a557bfe](https://github.com/frida/frida-tools/commit/a557bfea93e1ac109687b1814bed49177ee184fe)(2022-09)가 기본 동작을 뒤집어서, 12.0.0부터 `-f`는 스크립트를 올린 뒤 알아서 메인 스레드를 재개한다. 멈춘 채로 두고 싶으면 `--pause`를 준다([repl.py 119~124행](https://github.com/frida/frida-tools/blob/14.8.1/frida_tools/repl.py#L119-L124), 스크립트를 로드한 다음 재개하는 곳은 [236~249행](https://github.com/frida/frida-tools/blob/14.8.1/frida_tools/repl.py#L236-L249)). `--no-pause`를 붙이면 인자 해석 단계에서 바로 죽는다.

![frida --version 17.17.0, frida-tools 14.8.1. frida -U -f io.seika.fridalab -l hooks/gate.js --no-pause 가 usage 줄과 frida: error: unrecognized arguments: --no-pause 로 끝남. frida --help 에서 -f TARGET spawn FILE, -n NAME attach to NAME, -N IDENTIFIER attach to IDENTIFIER, -p PID attach to PID, -W PATTERN await spawn, --pause leave main thread paused after spawning program, --eternalize, --kill-on-exit 줄](/assets/img/android-mastery/p1c08/01-cli-no-pause.png)

Android에서는 앱 프로세스를 zygote가 fork해서 만들기 때문에([Atlas C12](/posts/android-concept-atlas-c12-zygote/)), spawn도 리눅스처럼 멈춘 프로세스를 새로 만드는 방식으로 돌지 않는다. frida-core의 Android 런처는 대상 패키지를 멈췄다가 다시 시작시키고 20초 안에 zygote 자식이 연락해 오기를 기다린다([linux-host-session.vala 1479~1530행](https://github.com/frida/frida-core/blob/17.17.0/src/linux/linux-host-session.vala#L1479-L1530)). 연락하는 쪽은 frida-server가 zygote에 미리 심어 둔 zymbiote라는 작은 페이로드다. zygote의 `selinux_android_setcontext`와 `android.os.Process.setArgV0()`의 JNI 구현을 가로채 둔다(같은 파일 [1845행](https://github.com/frida/frida-core/blob/17.17.0/src/linux/linux-host-session.vala#L1845), [1863행](https://github.com/frida/frida-core/blob/17.17.0/src/linux/linux-host-session.vala#L1863)).

![GitHub 파일 화면 frida-core / src / linux / helpers / zymbiote.c 64~108행. 68~71행에서 setcontext 때 받은 이름을 zymbiote.process_name 에 복사하고, 77~108행 강조 구간의 frida_zymbiote_replacement_setargv0 가 zymbiote.original_set_argv0 를 부른 뒤 process_name 이 있으면 그것을 name_utf8 로 쓰고 frida_wait_for_permission_to_resume(name_utf8, &revert_now) 를 부르며, revert_now 이면 frida_stop_and_return_from_setargv0 로 꼬리 호출](/assets/img/android-mastery/p1c08/s1-zymbiote-setargv0-gate.png)

fork된 자식이 처음으로 `setArgV0`를 부르면 대체 함수가 원래 함수를 부른 다음 frida-server의 abstract 유닉스 소켓에 pid·ppid와 프로세스 이름을 보내고 1바이트 응답이 올 때까지 `recv`에서 기다린다([zymbiote.c 114~187행](https://github.com/frida/frida-core/blob/17.17.0/src/linux/helpers/zymbiote.c#L114-L187)). spawn 대상이면 서버가 응답을 미루는데, 그동안 에이전트를 올리고 스크립트를 로드한다. resume하면 응답이 가고 자식은 `frida_stop_and_return_from_setargv0`에서 SIGSTOP으로 스스로 한 번 멈춘 뒤 서버가 뒷정리를 마치면 계속 간다. 프로세스 이름으로는 `setcontext` 때 잡아 둔 값을 먼저 쓴다(zymbiote.c 87~88행). argv[0]이 엉뚱하게 찍혀도 Frida가 대상을 놓치지 않은 건 이 덕분이었다.

게이트에 선 순간 프로세스 안에 무엇이 있는지 보려고 `hooks/spawn.js`를 썼다. 스크립트 최상위는 게이트에서 돌고 `Java.perform` 콜백은 브리지가 앱 클래스 로더를 쓸 수 있게 될 때까지 미뤄진다.

```javascript
// spawn.js: what exists at the spawn gate, and where Java.perform() finally runs
const PKG = 'io.seika.fridalab';
const appMaps = () => File.readAllText('/proc/self/maps').split('\n').filter(l => l.includes(PKG)).length;
// /proc/self/cmdline is NUL-separated and File.readAllText() refuses NUL bytes, so read raw bytes
const cmdline = String.fromCharCode(...new Uint8Array(File.readAllBytes('/proc/self/cmdline'))).split('\0')[0];

console.log(`[gate] pid=${Process.id} cmdline=${cmdline} maps-lines-with-${PKG}=${appMaps()}`);

try {
  Java.use(PKG + '.Gate');
} catch (e) {
  console.log('[gate] Java.use outside perform: ' + e.message);
}

Java.performNow(() => {
  const AT = Java.use('android.app.ActivityThread');
  console.log('[gate] ActivityThread.currentApplication() = ' + AT.currentApplication());
  try {
    Java.use(PKG + '.Gate');
  } catch (e) {
    console.log('[gate] Java.use in performNow: ' + e.message.split('\n')[0].slice(0, 90));
  }
  // Java stack of the thread that came out of zygote, while Frida holds it
  const Thread = Java.use('java.lang.Thread');
  const threads = Thread.getAllStackTraces().keySet().toArray();
  for (let i = 0; i < threads.length; i++) {
    const t = Java.cast(threads[i], Thread);
    const frames = t.getStackTrace().map(String);
    if (!frames.some(f => f.includes('Zygote'))) continue;
    console.log(`[gate] thread "${t.getName()}":`);
    frames.slice(0, 7).forEach(f => console.log('[gate]   at ' + f));
  }
});

Java.perform(() => {
  const Thread = Java.use('java.lang.Thread');
  const AT = Java.use('android.app.ActivityThread');
  const me = Thread.currentThread();
  console.log(`[perform] thread=${me.getName()} maps-lines-with-${PKG}=${appMaps()} currentApplication()=${AT.currentApplication()}`);
  me.getStackTrace().map(String).filter(l => l.includes('ActivityThread.')).slice(0, 3)
    .forEach(f => console.log('[perform]   at ' + f));

  const Gate = Java.use(PKG + '.Gate');
  let calls = 0;
  Gate.checkLicense.implementation = function () {
    const real = this.checkLicense();          // inside the replacement this calls the original
    if (calls++ === 0) console.log(`[hook] first checkLicense() real=${real} -> true`);
    return true;
  };
  console.log('[perform] Gate.checkLicense hooked');
});
```

처음에는 cmdline을 `File.readAllText`로 읽었다가 `can't decode byte 0x00` 오류가 났다. 스크립트 최상위에서 예외가 터졌는데도 앱은 그대로 재개돼 평소처럼 떴다. 명령의 `-q`는 REPL 없이 돌리는 옵션이고 `-t 4`는 4초 뒤에 끝낸다.

![frida -D $S -f io.seika.fridalab -l hooks/spawn.js -q -t 4 실행 결과. gate 줄은 pid=11489 cmdline=com.google.android.apps.maps:server_recovery_process_scheduled maps-lines-with-io.seika.fridalab=0, perform 밖과 performNow 안의 Java.use 가 모두 ClassNotFoundException, currentApplication() = null, main 스레드 스택 setArgV0Native ← Process.setArgV0 ← Zygote.setAppProcessName(Zygote.java:890) ← ZygoteConnection.processCommand(ZygoteConnection.java:299) ← ZygoteServer.runSelectLoop ← ZygoteInit.main. Resuming main thread 다음 perform 줄은 thread=main, 앱 경로 maps 4줄, ActivityThread.getPackageInfo(Native Method) ← getPackageInfoNoCheck:2566 ← handleBindApplication:6608, 훅 첫 호출 real=false -> true. logcat 은 App.\<clinit\> 줄만 license=true 이고 나머지 네 줄은 license=false, 모두 frida_maps=9 frida_thr=4](/assets/img/android-mastery/p1c08/03-spawn-gate.png)

게이트에서 메인 스레드는 zygote 코드 안에 있었다. 스택 맨 위가 `Process.setArgV0Native`이고 그 아래로 `Zygote.setAppProcessName`, `ZygoteConnection.processCommand`, `ZygoteServer.runSelectLoop`, `ZygoteInit.main`이 이어진다. `ActivityThread` 프레임은 하나도 없으니 `ActivityThread.main`도 아직 돌지 않았다. maps에는 앱 경로가 한 줄도 없고 `currentApplication()`은 null이었다. `Java.use(Gate)`는 perform 밖에서든 `performNow` 안에서든 ClassNotFoundException이었다. 브리지 소스에는 perform 밖에서 부르면 "Current thread is not attached to the Java VM"을 던지는 코드가 있는데([vm.js 94행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/vm.js#L94)) 여기서는 그 문구가 아니었다.

예상하지 못한 값은 cmdline이었다. 우리 앱을 spawn했는데 argv[0]이 `com.google.android.apps.maps:server_recovery_process_scheduled`였다. 같은 실행을 세 번 했을 때 모두 같은 값이었다. 스택의 `processCommand` 299행이 단서다. Android 13의 이 경로는 zygote가 한 번에 받은 요청 여러 개를 연달아 fork하는 `forkSimpleApps`이고 자식에서 부르는 [`Zygote.setAppProcessName(parsedArgs, TAG)`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/com/android/internal/os/ZygoteConnection.java#299)는 그 묶음에서 먼저 해석한 요청의 인자를 쓴다. 그 줄에는 `// ??? Necessary?`라는 주석이 붙어 있다. 다른 앱 이름이 잠깐 붙은 건 이 때문으로 보인다. 이름은 나중에 `handleBindApplication`이 [`Process.setArgV0(data.processName)`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#6534)으로 바로잡는다. Frida는 `setcontext` 때 잡아 둔 이름으로 프로세스를 가려내므로 엉뚱한 argv[0]에도 우리 앱을 정확히 붙잡았다. 같은 스크립트를 API 36에서 돌리면 게이트의 cmdline이 `io.seika.fridalab`였고 `setAppProcessName`은 `Zygote.childMain` 안에서 제 이름으로 불렸다. 측정한 API 33 이미지는 USAP 풀이 꺼져 있었고(usap 관련 프로퍼티가 비어 있음), API 36 이미지의 USAP 설정은 확인하지 않았다. 풀이 켜진 기기에서는 zygote가 미리 fork해 둔 프로세스를 쓰니 게이트가 걸리는 경로가 다를 수 있는데, 그 경우는 재 보지 않았다.

`Java.perform` 콜백은 resume 뒤 메인 스레드에서 돌았다. 그 순간의 스택은 `handleBindApplication` → `getPackageInfoNoCheck` → `getPackageInfo`이고 맨 위 `getPackageInfo`가 `Native Method`로 찍힌 건 Frida가 바꿔 끼운 대체 메서드라서다. frida-java-bridge는 앱 객체가 아직 없으면 `ActivityThread.handleBindApplication`과 인자가 가장 많은 `getPackageInfo` 오버로드를 후킹해 두고 그 안에서 앱의 `LoadedApk`로 클래스 팩토리를 만든 뒤 쌓아 둔 perform 콜백을 실행한다([index.js 400~455행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/index.js#L400-L455)). AOSP 순서로 보면 [`getPackageInfoNoCheck`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#6602) 뒤에야 `App.<clinit>`과 `attachBaseContext`를 부르는 [`makeApplicationInner`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#6766), provider를 만드는 [`installContentProviders`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#6790), [`callApplicationOnCreate`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#6805)가 온다. perform 콜백이 도는 때는 앱 코드가 한 줄도 실행되기 전이다.

logcat의 첫 줄 `App.<clinit>`은 `license=true`였다. 앱에서 가장 먼저 도는 코드부터 반환값이 바뀌었다. 같은 줄에서 `frida_maps=9 frida_thr=4`도 찍혀, 가장 이른 검사에도 에이전트가 보였다.

이 스크립트가 쓰는 `Java` 전역은 Frida 17부터 GumJS 런타임에 들어 있지 않다. `frida` REPL과 `frida-trace`가 frida-java-bridge를 같이 실어 보내서 `-l`로 올린 스크립트에서는 예전처럼 쓸 수 있다([Frida 문서](https://frida.re/docs/bridges/)). 호스트의 파이썬 프로세스 하나에 Python API로 만든 스크립트를 넣었더니 `typeof Java`가 `undefined`였고 같은 프로세스에 `frida -p <pid> -q -e "typeof Java"`로 붙으면 `"object"`였다. Python API로 자동화할 때는 문서대로 frida-compile로 브리지를 묶어 넣어야 한다.

## spawn으로 건 static 훅이 첫 호출 뒤에 빠졌다

앞 캡처에서 이상한 건 logcat의 아래 네 줄이다. 훅은 `App.<clinit>`에서 한 번 불렸고, 같은 메서드를 다시 부른 `attachBaseContext`부터는 원래 값 false가 나왔다. 호출마다 줄을 찍게 바꾼 `hooks/spawn-every.js`로 돌려도 `[hook]` 줄은 한 번뿐이었다. 그래서 같은 spawn에서 후킹 직전에 클래스를 먼저 초기화해 봤다. `spawn-every.js`에 `-P`로 준 JSON은 스크립트 끝의 `rpc.exports.init(stage, params)`가 받아 `run(params)`으로 넘긴다. `-P '{"init":true}'`를 주면 perform 콜백 안에서 후킹 전에 아래 부분이 돈다.

```javascript
    if (params.init) {
      const Class = Java.use('java.lang.Class');
      Class.forName(PKG + '.Gate', true, Java.classFactory.loader);
      console.log('[perform] Gate class initialized before hooking');
    }

// 파일 끝: -P 로 넘긴 값이 여기로 들어온다
rpc.exports = {
  init(stage, params) {
    run(params || {});
  }
};
```

```text
$ adb -s $S logcat -c
$ frida -D $S -f io.seika.fridalab -l hooks/spawn-every.js -q -t 4 -P '{"init":true}'
Spawned `io.seika.fridalab`. Resuming main thread!
[perform] Gate class initialized before hooking
[perform] Gate.checkLicense hooked
[hook] checkLicense() call #1 real=false -> true
[hook] checkLicense() call #2 real=false -> true
[hook] checkLicense() call #3 real=false -> true
[hook] checkLicense() call #4 real=false -> true
[hook] checkLicense() call #5 real=false -> true
$ adb -s $S logcat -d -v raw -s fridalab:I
--------- beginning of main
App.<clinit>           license=true  frida_maps=9 frida_thr=3
App.attachBaseContext  license=true  frida_maps=9 frida_thr=3
EarlyProvider.onCreate license=true  frida_maps=9 frida_thr=3
App.onCreate           license=true  frida_maps=9 frida_thr=3
MainActivity.onCreate  license=true  frida_maps=9 frida_thr=3
```

클래스를 먼저 초기화하면 다섯 곳 모두 걸렸다. 클래스 초기화가 훅을 지운 셈인데, 무엇이 어떻게 지우는지 보려면 Frida가 훅을 어떻게 거는지부터 알아야 했다.

frida-java-bridge는 메서드 진입점에 JS 함수를 그대로 꽂지 않는다. [`replace()`](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/android.js#L3707-L3763)는 원래 `ArtMethod`를 복제해 JS 구현을 JNI 코드로 갖는 native 대체 메서드를 만들고 원본에는 `kAccCompileDontBother`를 켜고 몇 가지 빠른 경로 플래그를 끈다. 원본의 진입점이 nterp(ART 13의 기본 인터프리터)라면 그것만 `art_quick_to_interpreter_bridge`로 바꾸고 컴파일된 코드가 있으면 그 코드의 프롤로그를 덮어쓴다. 그다음 ART의 진입 스텁(generic JNI trampoline, quick-to-interpreter bridge, resolution trampoline)과 인터프리터의 `DoCall`을 가로채서 원본으로 가던 호출을 대체 메서드로 돌린다([android.js 2077~2136행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/android.js#L2077-L2136)). 호출이 이 가로챈 길 중 하나를 지나야 훅이 걸린다.

`hooks/static-diag.js`로 `Gate.checkLicense`의 `ArtMethod`에서 quick 진입점(x86_64에서 오프셋 24의 [`entry_point_from_quick_compiled_code_`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/runtime/art_method.h#856))이 무엇을 가리키는지 시간에 따라 찍었다. 브리지가 클래스 초기화 뒤 훅을 다시 맞추려고 찾는 libart 심볼이 있는지, GC가 몇 번 돌았는지도 같이 봤다. 아래는 그 스크립트의 perform 부분이다.

```javascript
Java.perform(() => {
  const m = Java.use(PKG + '.Gate').checkLicense;
  const quick = () => sym(m.handle.add(24).readPointer()); // ArtMethod quick entry point, offset 24 on x86_64
  console.log(`[perform] ${ts()} before hooking; Gate.checkLicense quick entry = ${quick()}`);
  let calls = 0;
  m.implementation = function () {
    const real = this.checkLicense();
    console.log(`[hook] ${ts()} call #${++calls} real=${real} -> true`);
    return true;
  };
  console.log(`[perform] ${ts()} hooked; Gate.checkLicense quick entry = ${quick()}`);
  setTimeout(() => Java.perform(() => {
    console.log(`[later] ${ts()} quick entry = ${quick()}, hook calls so far = ${calls}, GCs so far = ${gcs}`);
  }), 3000);
  setTimeout(() => Java.perform(() => {
    Java.use('java.lang.Runtime').getRuntime().gc();
    console.log(`[gc] ${ts()} Runtime.gc() returned, GCs so far = ${gcs}; quick entry = ${quick()}`);
  }), 7000);
});
```

frida를 백그라운드로 띄우고 6초 간격으로 `check` 브로드캐스트를 두 번 보냈다. frida 출력과 브로드캐스트 결과가 시간 순으로 섞여 찍혔고 `t+`는 스크립트가 로드된 때부터 잰 시간이다.

![frida -D $S -f io.seika.fridalab -l hooks/static-diag.js -q -t 16 & 로 백그라운드 실행 후 sleep 6 간격으로 check 브로드캐스트 두 번. art 줄은 MarkVisiblyInitialized: symbol not found, AdjustThreadVisibilityCounter: symbol not found, Heap::CollectGarbageInternal: found. t+0.3s 후킹 전과 t+1.0s 후킹 후 quick entry 모두 art_quick_to_interpreter_bridge, t+1.0s 훅 call #1, 첫 브로드캐스트 data="license=false". t+4.0s quick entry = ExecuteNterpImpl, hook calls 1, GCs 0. t+8.0s Runtime.gc() 뒤 GCs 1, quick entry = art_quick_to_interpreter_bridge, t+10.4s 훅 call #2, 두 번째 브로드캐스트 data="license=true". logcat 은 App.\<clinit\> 줄만 license=true, 끝에 cmd license=false 와 cmd license=true](/assets/img/android-mastery/p1c08/03c-static-resync.png)

진입점은 후킹 전에도 후킹 직후에도 `art_quick_to_interpreter_bridge`였다. 첫 호출(`App.<clinit>`)은 이 스텁을 지나 훅에 걸렸다. 그 호출로 `Gate`가 초기화된 뒤 t+4.0초에 다시 보니 진입점이 `ExecuteNterpImpl`로 바뀌어 있었고, 그 사이 앱 코드가 부른 `checkLicense`(첫 브로드캐스트)는 훅을 거치지 않고 false를 냈다. nterp로 곧장 들어가는 호출은 Frida가 가로챈 스텁을 하나도 지나지 않는다. 브리지의 `replace()`가 nterp 진입점을 굳이 interpreter bridge로 바꿔 두는 이유가 이것이다([android.js 3745~3751행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/android.js#L3745-L3751)). `Runtime.gc()`를 한 번 부르자 진입점이 다시 `art_quick_to_interpreter_bridge`가 됐다. 다음 브로드캐스트에서 훅이 두 번째로 불려 true가 나왔다. 시작부터 t+4.0초까지 GC는 한 번도 없었다.

진입점이 바뀌는 쪽은 ART 13 소스와 맞는다. [`Instrumentation::InitializeMethodsCode`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/runtime/instrumentation.cc#389)는 아직 초기화되지 않은 클래스의 static 메서드에 일단 resolution stub이나 interpreter bridge를 넣어 둔다. 주석은 resolution stub을 두고 클래스 초기화 뒤 `ClassLinker::FixupStaticTrampolines`가 제 진입점으로 바꾼다고 적었고, interpreter bridge 쪽에는 그런 주석이 없다. interpreter bridge도 초기화 뒤 바뀐다는 건 측정에서 본 진입점 변화(bridge → `ExecuteNterpImpl`)가 그렇게 보여 준 것이다. 이 메서드는 AOT 코드가 없고 그 시점에 nterp도 쓸 수 없다고 판정돼 interpreter bridge를 받은 것으로 보이는데, `CanUseNterp`가 왜 거짓이었는지는 확인하지 않았다. 바꾸는 순간이 정확히 `FixupStaticTrampolines` 호출인지도 Interceptor로 잡아 보지는 않았고, 진입점 값의 전후와 소스 주석까지만 맞춰 봤다.

브리지도 이 상황을 알고 대비해 둔 코드가 있다.

![GitHub frida-java-bridge v7.0.12 lib/android.js 2138~2182행 강조. instrumentArtGarbageCollection 은 findSymbolByName 으로 Heap::CollectGarbageInternal 을 찾아 Interceptor.attach 의 onLeave 에서 artController.replacedMethods.synchronize(quickCodeOffset, artNterpEntryPoint, artQuickToInterpreterBridge) 를 부른다. instrumentArtFixupStaticTrampolines 는 VisiblyInitializedCallback 의 MarkVisiblyInitialized 와 AdjustThreadVisibilityCounter 심볼에 바이트 패턴 'e90340f8 : ff0ff0ff', '7f0f00f9 : 1ffcffff' 를 짝지어 두고, 심볼이 null 이면 continue, Memory.scanSync 매치가 없으면 return](/assets/img/android-mastery/p1c08/s4-bridge-resync-hooks.png)

`instrumentArtFixupStaticTrampolines()`는 클래스가 "보이게 초기화"되는 ART 함수 안의 특정 명령에 걸어서 훅을 다시 맞추려는 장치다. 그런데 이 함수가 찾는 두 심볼, `ClassLinker::VisiblyInitializedCallback::MarkVisiblyInitialized`와 `::AdjustThreadVisibilityCounter`가 이 libart에는 아예 없었다. 두 번 다 `continue`로 넘어가니 아무것도 걸리지 않는다. libart에서 이름에 `VisiblyInitialized`나 `FixupStaticTrampolines`가 든 심볼은 `ClassLinker::FixupStaticTrampolines`, `ClassLinker::VisiblyInitializedCallbackDone`, `ClassLinker::MakeInitializedClassesVisiblyInitialized`뿐이었다. 바이트 패턴은 ARM64 명령 인코딩이라 심볼이 있었더라도 x86_64에서 맞았을지는 의문이다. 남은 장치는 `instrumentArtGarbageCollection()`이다. GC가 끝날 때마다 [`synchronize_replacement_methods`](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/android.js#L1868-L1891)가 후킹된 메서드를 훑어 진입점이 nterp면 interpreter bridge로 되돌린다. GC 한 번 뒤 진입점이 interpreter bridge로 돌아오고 훅이 다시 불린 것은 이 코드가 한 일로 보인다(synchronize 호출 자체를 잡아 보지는 않았다). 이 실습 앱의 시작 구간에는 GC가 없어서 훅이 빠진 채로 시작 단계를 다 지나갔다. GC가 자주 도는 실제 앱이라면 빠지는 구간이 첫 GC까지로 짧아질 텐데 그건 재 보지 않았다.

클래스를 먼저 초기화한 경우도 같은 방법으로 봤다. 후킹 직전 진입점이 이미 `ExecuteNterpImpl`이었고 `replace()`가 그걸 `art_quick_to_interpreter_bridge`로 바꿨다. 그 뒤에는 ART가 진입점을 다시 고칠 일이 없어서 GC 없이도 여섯 번째 호출까지 훅이 유지됐다. spawn 단계에서 static 메서드를 바꿀 때 훅이 한 번만 걸린다면 후킹 전에 `Class.forName(이름, true, Java.classFactory.loader)`로 클래스를 초기화해 두는 게 이 환경에서 통한 처리다. 다만 그 클래스의 static 초기화가 앱이 의도한 때보다 일찍, `handleBindApplication` 안에서 돈다는 건 감안해야 한다.

API 36(ART 360527520)에서도 두 심볼은 없었다. 그런데 거기서는 `Gate.checkLicense` 진입점이 처음부터 끝까지 `art_quick_to_interpreter_bridge`였고 GC 없이 시작 단계 다섯 곳 모두에서 훅이 불렸다. 같은 브리지가 왜 API 36에서는 진입점을 interpreter bridge에 묶어 두는지는 찾지 못했다. ARM64 기기에서 `instrumentArtFixupStaticTrampolines()`가 실제로 걸리는지는 이 랩이 x86_64 에뮬레이터뿐이라 확인하지 못했다.

## attach는 시작 코드를 이미 지나 있다

attach는 돌고 있는 프로세스에 붙는다. 앱을 평소처럼 띄운 뒤 같은 게이트를 바꾸는 `hooks/gate.js`를 붙였다. 구현 안에서 `this.checkLicense()`를 부르면 원래 메서드가 돌기 때문에, 원래 값을 찍어 두면 훅이 무엇을 바꿨는지 로그에 남는다.

```javascript
// gate.js (attach): make Gate.checkLicense() return true from now on
Java.perform(() => {
  const Thread = Java.use('java.lang.Thread');
  console.log(`[gate] Java.perform ran on thread "${Thread.currentThread().getName()}"`);

  const Gate = Java.use('io.seika.fridalab.Gate');
  Gate.checkLicense.implementation = function () {
    const real = this.checkLicense();          // inside the replacement this calls the original
    console.log(`[hook] checkLicense() real=${real} -> true`);
    return true;
  };
  console.log('[gate] Gate.checkLicense hooked');
});
```

![am force-stop 후 am start -W 로 앱을 띄우고 Status: ok. frida -D $S -n io.seika.fridalab -l hooks/gate.js -q 는 Failed to spawn: unable to find process with name 'io.seika.fridalab'. frida-ps -a 는 PID 11664 Name 'Frida Lab' Identifier io.seika.fridalab. frida -N io.seika.fridalab -l hooks/gate.js -q -t 1 --eternalize 로 붙자 Java.perform ran on thread "Thread-2" 와 Gate.checkLicense hooked. logcat 다섯 줄은 모두 license=false frida_maps=0 frida_thr=0. 그 뒤 check 브로드캐스트는 data="license=true", probe 브로드캐스트는 maps 에 /memfd:frida-agent-64.so (deleted), threads 에 gdbus, gmain, pool-frida](/assets/img/android-mastery/p1c08/04-attach-late.png)

`-n io.seika.fridalab`는 실패했다. `-n`은 프로세스 이름으로 찾는데, `frida-ps -a`의 Name 열이 보여 주듯 앱의 이름은 라벨 "Frida Lab"이다. 패키지 식별자로 붙으려면 `-N`을 쓴다([application.py 345~362행](https://github.com/frida/frida-tools/blob/14.8.1/frida_tools/application.py#L345-L362)). `-n`이 실패했는데 문구가 `Failed to spawn`인 건 frida-tools 14.8.1이 그렇게 찍어서다. pid를 안다면 `-p`도 된다.

`-N`으로 붙자 perform 콜백은 Frida 쪽 스레드 `Thread-2`에서 곧바로 돌았다. 기다릴 앱 초기화가 이미 끝났으니 미룰 이유가 없다. 시작 단계 다섯 줄은 붙기 전에 이미 찍혀서 전부 `license=false frida_maps=0 frida_thr=0`이다. 붙은 뒤에 보낸 `check`만 true였다. `--eternalize`는 CLI가 끝나도 스크립트를 프로세스에 남기는 옵션이라, 브로드캐스트 때 `[hook]` 줄은 호스트에 찍히지 않았지만 훅은 살아 있었다. spawn 때와 달리 static 훅이 빠지지 않은 건 붙을 때 `Gate`가 이미 초기화돼 있었기 때문으로 보인다.

붙은 뒤에는 앱 안에서도 흔적이 보였다. `probe` 응답의 maps에 `/memfd:frida-agent-64.so (deleted)`가 있고 스레드 이름은 `gdbus`, `gmain`, `pool-frida`였다.

## 오버로드는 Class.getName() 문자열로 고른다

`Codec.encode`는 이름이 같은 메서드 넷을 가진다.

```java
public final class Codec {
    static String encode(int v) { return "i:" + Integer.toHexString(v); }

    static String encode(String s) { return "s:" + s.length(); }

    static String encode(byte[] b) { return "b:" + b.length; }

    static String encode(String s, int rounds) { return "si:" + s.length() * rounds; }

    static String demo() {
        return encode(7) + " " + encode("seika") + " " + encode(new byte[] {1, 2, 3}) + " " + encode("x", 2);
    }
}
```

`hooks/overload.js`는 오버로드를 고르지 않고 구현을 바꿔 보고 JVM 디스크립터식 `'I'`로 골라 보고 마지막으로 `byte[]`판과 `(String, int)`판에 훅을 건 뒤 `demo()`를 부른다. 대체 구현 안에서 원본은 오버로드 객체의 `call`로 부른다.

```javascript
// overload.js: Codec.encode has four overloads; pick them by Class.getName() strings
Java.perform(() => {
  const Codec = Java.use('io.seika.fridalab.Codec');

  try {
    Codec.encode.implementation = function (x) { return 'never'; };
  } catch (e) {
    console.log('[1] ' + e.message);
  }

  try {
    Codec.encode.overload('I');
  } catch (e) {
    console.log('[2] ' + e.message.split('\n')[0]);
  }

  const encBytes = Codec.encode.overload('[B');
  encBytes.implementation = function (b) {
    console.log(`[hook] encode(byte[]) len=${b.length}`);
    return encBytes.call(this, b);
  };
  const encStrInt = Codec.encode.overload('java.lang.String', 'int');
  encStrInt.implementation = function (s, rounds) {
    console.log(`[hook] encode(String, int) s="${s}" rounds=${rounds}`);
    return encStrInt.call(this, s, rounds);
  };

  console.log('[3] Codec.demo() = ' + Codec.demo());
});
```

![frida -D $S -N io.seika.fridalab -l hooks/overload.js -q -t 1 결과. 첫 줄 encode(): has more than one overload 오류와 함께 .overload('int'), .overload('java.lang.String'), byte 배열 오버로드, .overload('java.lang.String', 'int') 목록. 둘째 줄 encode(): specified argument types do not match any of. 훅 줄 encode(byte 배열) len=3 과 encode(String, int) s="x" rounds=2, 마지막 줄 Codec.demo() = i:7 s:5 b:3 si:2](/assets/img/android-mastery/p1c08/06-overload.png)

오버로드가 여럿이면 고르지 않은 `implementation` 대입은 거절되고 오류 메시지가 쓸 수 있는 문자열을 그대로 알려 준다. 브리지는 인자 타입들의 `className`을 `:`로 이어 붙여 비교한다([class-factory.js 1490~1509행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/class-factory.js#L1490-L1509)). 이 이름은 `Class.getName()` 꼴이라 기본형은 `int`, 클래스는 `java.lang.String`처럼 점 표기지만 배열은 `[B`, `[Ljava.lang.String;`처럼 디스크립터와 비슷한 모양이 된다([types.js 17~30행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/types.js#L17-L30)). 배열 인자는 `'[B'`처럼 써야 했다. `'I'`는 어느 오버로드와도 맞지 않았다.

## 힙에 살아 있는 객체는 Java.choose로 찾는다

`Vault`는 런타임에 `SecureRandom`으로 만든 AES 키로 비밀을 봉인해 들고 있어서 APK 어디에도 키가 없다. 앱은 시작할 때 `boot`, 액티비티에서 `session`이라는 `Vault`를 하나씩 만든다. `Java.choose`는 힙을 훑어 그 클래스의 살아 있는 인스턴스를 넘겨준다.

```javascript
// vault.js: find live Vault objects on the Java heap and call their own open()
Java.perform(() => {
  Java.choose('io.seika.fridalab.Vault', {
    onMatch(v) {
      const key = Array.from(v.key.value, b => ('0' + (b & 0xff).toString(16)).slice(-2)).join('');
      console.log(`[choose] label=${v.label.value} key=${key} open()=${v.open()}`);
    },
    onComplete() {
      console.log('[choose] heap scan done');
    }
  });
});
```

```text
$ adb -s $S shell am broadcast -n io.seika.fridalab/.Cmd --es op vaults | tail -1
Broadcast completed: result=0, data="vaults boot=true session=true"
$ frida -D $S -N io.seika.fridalab -l hooks/vault.js -q -t 2
[choose] label=boot key=784d490bf8ef7824d68f411314d17c31 open()=boot-681dfdbf
[choose] label=session key=0e2af9bfaffa0b400c3de54ec973e596 open()=token-806c674aff8a66b9
[choose] heap scan done
```

필드는 private인 `key`까지 `.value`로 읽혔고 객체 자신의 `open()`을 불러 봉인을 풀었다.

## Android 13에서는 AOT 인라인 호출이 훅을 비켜 갔다

앞의 훅은 전부 설치 직후, 앱이 `verify` 상태(AOT 코드 없음)일 때 걸었다. ART가 메서드를 최적화 컴파일하면 작은 메서드는 호출자 안에 복사되고 복사본은 `ArtMethod`를 읽지 않는다. 개념은 [Atlas C16](/posts/android-concept-atlas-c16-jit-aot-analysis/)에서 다뤘다. 여기서는 그 일이 실제로 훅을 비켜 가는지, 비켜 갔을 때 Frida가 무엇을 해 주는지를 쟀다.

ART 13 인라이너는 try 블록이 있는 콜리를 거절하고([inliner.cc 1399행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/compiler/optimizing/inliner.cc#1399)), 크기가 `inline_max_code_units`를 넘는 콜리도 거절한다([1431행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/compiler/optimizing/inliner.cc#1431), 기본값 32는 [compiler_options.h 69행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/compiler/driver/compiler_options.h#69)). `Hot`의 세 콜리는 이 조건에 맞춰 만들었다. dexdump로 보면 `isPremium`은 9 code unit, `isPremiumGuarded`는 14 code unit에 try 범위가 있고 `isPremiumLong`은 35 code unit이다. 셋 다 원래 false를 낸다.

```java
public final class Hot {
    private static int sLevel = 1; // never > 5

    static boolean isPremium() {
        return sLevel > 5;
    }

    static boolean isPremiumGuarded() {
        try {
            return 100 / sLevel > 500; // div-int can throw, so d8 keeps the try range
        } catch (ArithmeticException e) {
            return false;
        }
    }

    static boolean isPremiumLong() {
        int a = sLevel;
        int b = a * 31 + 7;
        int c = b ^ (a << 3);
        int d = c * 17 - b;
        int e = d ^ (d >>> 5);
        int f = e * 13 + c;
        int g = f ^ (f >>> 7);
        int h = g * 29 - e;
        return sLevel > 5 && h != 0;
    }

    static int spin(int n) {
        int c = 0;
        for (int i = 0; i < n; i++) if (isPremium()) c++;
        return c;
    }

    static int spinGuarded(int n) {
        int c = 0;
        for (int i = 0; i < n; i++) if (isPremiumGuarded()) c++;
        return c;
    }

    static int spinLong(int n) {
        int c = 0;
        for (int i = 0; i < n; i++) if (isPremiumLong()) c++;
        return c;
    }
}
```

`hooks/inline.js`는 세 콜리에 똑같이 "부르면 횟수를 세고 true를 내는" 훅을 건다. 훅 전과 후에 `spin*(1000)`을 한 번씩 부르고 `isPremium()`을 직접 한 번 부른 다음, 호출자 `spin`을 deopt하고 다시 부른다. 아래는 그 파일의 `run` 함수다.

```javascript
function run(deopt) {
  Java.perform(() => {
    const Hot = Java.use('io.seika.fridalab.Hot');
    const hits = {};
    const pad = (v, w) => String(v).padStart(w);
    const row = tag => {
      CALLEES.forEach(c => { hits[c] = 0; });
      const r = [Hot.spin(N), Hot.spinGuarded(N), Hot.spinLong(N)];
      console.log(`${tag.padEnd(24)} spin=${pad(r[0], 4)} spinGuarded=${pad(r[1], 4)} spinLong=${pad(r[2], 4)}` +
        `   hook hits ${CALLEES.map(c => hits[c]).join('/')}`);
    };

    row('before hook');
    CALLEES.forEach(c => {
      Hot[c].implementation = function () { hits[c]++; return true; };
    });
    row('hooked');
    hits.isPremium = 0;
    console.log(`${'direct isPremium()'.padEnd(24)} = ${Hot.isPremium()}   hook hits ${hits.isPremium}`);

    try {
      if (deopt === 'everything') {
        Java.deoptimizeEverything();
        row('deoptimizeEverything()');
      } else {
        Java.deoptimizeMethod(Hot.spin.handle);   // deoptimize the caller, not the hooked callee
        row('deoptimizeMethod(spin)');
      }
    } catch (e) {
      console.log(`deopt (${deopt}) failed: ${e.message}`);
    }
  });
}
```

앱을 [공식 절차](https://source.android.com/docs/core/runtime/jit-compiler)대로 `speed`로 강제 AOT 컴파일하고 다시 띄운 뒤 붙였다.

![adb shell pm list packages --apex-only --show-versioncode 에서 com.google.android.art versionCode:331711080, cmd package compile -m speed -f io.seika.fridalab 가 Success, dumpsys 상태 x86_64 status=speed reason=cmdline, force-stop 후 am start Status: ok. frida -N io.seika.fridalab -l hooks/inline.js -q -t 1 결과 before hook spin=0 spinGuarded=0 spinLong=0 hook hits 0/0/0, hooked spin=0 spinGuarded=1000 spinLong=1000 hook hits 0/1000/1000, direct isPremium() = true hook hits 1, deoptimizeMethod(spin) spin=1000 spinGuarded=1000 spinLong=1000 hook hits 1000/1000/1000](/assets/img/android-mastery/p1c08/05-inline-deopt.png)

훅을 건 뒤에도 `spin`은 0이었고 `isPremium` 훅은 한 번도 불리지 않았다. 같은 `isPremium()`을 직접 부르면 훅이 걸려 true가 나왔으니 훅 자체는 제대로 설치돼 있다. try가 있는 `isPremiumGuarded`와 35 code unit짜리 `isPremiumLong`은 1000번 모두 훅을 거쳤다. 기계어로 확인하려고 기기에 들어 있는 oatdump로 `spin*`의 AOT 코드를 덤프했다.

![adb shell 에서 pm path 로 구한 경로로 oatdump --oat-file=$D/oat/x86_64/base.odex --dex-file=$D/base.apk --class-filter=io.seika.fridalab.Hot --method-filter=spin 을 돌려 grep 한 결과. Hot.spin(int) dex_method_idx=44 에는 cmp eax, 5 와 pReadBarrierMarkReg00, pTestSuspend 호출만 있고, Hot.spinGuarded(int) idx=45 와 Hot.spinLong(int) idx=46 에는 각각 rdi + 24 를 거치는 call 과 native_pc=0x5330, 0x53c0 의 dex_pc=0x5 StackMap 이 있다](/assets/img/android-mastery/p1c08/08-oatdump-spin.png)

dex로는 `spin`의 0x5 위치에 `invoke-static isPremium()`이 있는데, 기계어에는 그 호출이 없다. 전체 덤프를 보면 루프에 들어가기 전에 `sLevel`을 한 번 읽어 `cmp eax, 5`로 비교해 두고 루프 안에서는 그 결과로 카운터만 `cmov`로 올린다. 루프 안에 `isPremium` 호출은 없다. `spinGuarded`와 `spinLong`에는 dex_pc 0x5에 해당하는 `call [rdi + 24]`가 남아 있다. 콜리의 `ArtMethod`에서 오프셋 24, 앞에서 진입점을 읽은 바로 그 필드로 뛰는 호출이라 Frida가 손댄 진입점을 지나간다.

대조로 같은 앱을 `verify`로 되돌리고 같은 스크립트를 돌리면 `hooked` 줄부터 세 경로 모두 1000이었다.

```text
$ adb -s $S shell cmd package compile -m verify -f io.seika.fridalab
Success
$ adb -s $S shell dumpsys package io.seika.fridalab | grep "status="
      x86_64: [status=verify] [reason=cmdline]
$ adb -s $S shell am force-stop io.seika.fridalab
$ adb -s $S shell am start -W -n io.seika.fridalab/.MainActivity | grep Status
Status: ok
$ frida -D $S -N io.seika.fridalab -l hooks/inline.js -q -t 1
before hook              spin=   0 spinGuarded=   0 spinLong=   0   hook hits 0/0/0
hooked                   spin=1000 spinGuarded=1000 spinLong=1000   hook hits 1000/1000/1000
direct isPremium()       = true   hook hits 1
deoptimizeMethod(spin)   spin=1000 spinGuarded=1000 spinLong=1000   hook hits 1000/1000/1000
```

인라인이 시작 단계의 게이트 훅을 통째로 없앤 경우도 있었다. 앱을 `speed`로 컴파일한 상태에서 spawn으로 `Gate.checkLicense`를 후킹하자 `[perform] Gate.checkLicense hooked`만 찍히고 훅은 한 번도 불리지 않았으며 다섯 곳 모두 false였다. `Stage.log`의 AOT 코드를 덤프해 보니 `Gate.checkLicense()` 호출 자리에 `cmp ecx, 99537323`이 있었다. 99537323은 0x5EED1AB, 게이트가 비교하는 상수다. 실제 앱에서도 검사 코드가 설치 뒤 백그라운드 dexopt로 컴파일돼 있다면 같은 일이 날 수 있다.

Frida는 이걸 알아서 메워 주지 않는다. 브리지에서 deopt는 공개 API에서만 요청된다. `Java.deoptimizeEverything()`과 `Java.deoptimizeMethod()`는 `requestDeoptimization`을 거치고, `Java.deoptimizeBootImage()`는 `art::Runtime::DeoptimizeBootImage`를 직접 부른다([index.js 512~525행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/index.js#L512-L525), [android.js 3978~4056행](https://github.com/frida/frida-java-bridge/blob/v7.0.12/lib/android.js#L3978-L4056)). 후킹 경로는 이 중 아무것도 부르지 않는다. [Frida 문서](https://frida.re/docs/javascript-api/#java)는 `deoptimizeEverything()`을 최적화가 메서드 훅을 비켜 가는 경우에 필요하다고 설명하고, `deoptimizeMethod()`는 문서에는 없고 소스에만 있다. API 30 이상에서는 JDWP를 거치지 않고 `art::Instrumentation::Deoptimize`/`DeoptimizeEverything`을 직접 부르며, JDWP 경로는 API 30 미만에서만 쓴다.

ART 13의 [`Instrumentation::Deoptimize(method)`](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/runtime/instrumentation.cc#1143)는 그 메서드의 진입점을 interpreter bridge로 바꾼다. 그래서 deopt할 대상은 훅을 건 `isPremium`이 아니라 인라인 복사본을 품은 호출자 `spin`이다. 인터프리터로 도는 `spin`은 `isPremium`을 `ArtMethod`를 통해 부르고 그 호출은 훅에 걸린다. 같은 함수는 이미 deopt된 메서드를 또 넣으면 `CHECK`로 프로세스를 죽이게 돼 있어서 같은 메서드에 두 번 부르지 않도록 해야 한다. `deoptimizeMethod(spin)`은 이 debuggable이 아닌 앱에서도 예외 없이 돌았고 프로세스도 살아 있었다. 호출자를 모를 때 쓰는 `deoptimizeEverything()`으로 바꿔 돌려도 마지막 줄은 같았다. `inline.js`는 `-P`의 `deopt` 값을 파일 끝 `rpc.exports.init`에서 받아 `run`에 넘긴다.

```text
$ adb -s $S shell am force-stop io.seika.fridalab
$ adb -s $S shell am start -W -n io.seika.fridalab/.MainActivity | grep Status
Status: ok
$ frida -D $S -N io.seika.fridalab -l hooks/inline.js -q -t 1 -P '{"deopt":"everything"}'
before hook              spin=   0 spinGuarded=   0 spinLong=   0   hook hits 0/0/0
hooked                   spin=   0 spinGuarded=1000 spinLong=1000   hook hits 0/1000/1000
direct isPremium()       = true   hook hits 1
deoptimizeEverything()   spin=1000 spinGuarded=1000 spinLong=1000   hook hits 1000/1000/1000
```

## Android 16에서는 같은 실험이 다르게 나왔다

ART 14부터는 try/catch가 있는 콜리도 인라인한다. [android-14.0.0_r1의 inliner.cc](https://android.googlesource.com/platform/art/+/refs/tags/android-14.0.0_r1/compiler/optimizing/inliner.cc#1444)는 `kInlineTryCatches`가 켜져 있으면([76행](https://android.googlesource.com/platform/art/+/refs/tags/android-14.0.0_r1/compiler/optimizing/inliner.cc#76)) 호출 지점이 try 안이 아닐 때 try/catch 콜리를 받아들인다. 이 소스대로라면 API 36 에뮬레이터에서는 `spin`과 `spinGuarded`가 둘 다 0이 나올 거라고 보고 돌렸다.

![API 36 에뮬레이터에서 getprop ro.build.version.sdk 36, com.google.android.art versionCode:360527520, cmd package compile -m speed -f 가 Success, am start Status: ok. frida -N io.seika.fridalab -l hooks/inline.js -q -t 1 결과 before hook 0/0/0, hooked spin=1000 spinGuarded=1000 spinLong=1000 hook hits 1000/1000/1000, direct isPremium() = true hook hits 1, deoptimizeMethod(spin) 1000/1000/1000](/assets/img/android-mastery/p1c08/10-api36-inline.png)

훅을 걸자마자 셋 다 1000이었다. API 36의 AOT 코드도 소스대로 인라인돼 있었다. oatdump에서 `spin`은 호출 없이 `cmp eax, 5`만 있고 `spinGuarded`에는 `InlineInfo[0] (depth=0, dex_pc=0x5, method_index=42)`와 `cmp eax, 500`, `Catch` 표시가 붙은 StackMap이 있었다. method 42가 `isPremiumGuarded`이니 try/catch 콜리까지 인라인됐다. `call [rdi + 24]`가 남은 건 `spinLong`뿐이다. 그런데도 훅은 세 경로 모두 걸렸다.

차이는 Frida 브리지가 올라간 뒤 그 AOT 코드가 아예 실행되지 않는 데 있었다. 브리지가 붙은 API 36 프로세스에서 `Hot` 메서드의 진입점은 전부 `art_quick_to_interpreter_bridge`였다(API 33에서는 같은 진단에서 `base.odex` 안의 각 메서드 코드였다). simpleperf로 실행 위치를 비교했다. Frida 없이 `spinLong(300000000)`을 돌리면 샘플의 82.32%가 `base.odex`였고(다른 두 번은 78.93%, 86.60%), 같은 프로세스에 `Java.perform(() => {})` 하나만 eternalize한 뒤 `spinLong(30000000)`을 돌리면 73.57%가 `[JIT app cache]`, 12.86%가 `libart.so`였다. API 33은 같은 절차의 전후 모두 `base.odex`가 99%대였다. 앞에서 본 static 훅이 API 36에서 처음부터 끝까지 interpreter bridge에 머문 것도 같은 현상으로 보인다. 브리지의 어떤 초기화가 ART 36에서 진입점을 interpreter bridge에 묶어 두는지는 찾지 못했고, 반복을 늘려 JIT가 다시 컴파일할 때 인라인하는지나 다른 빌드에서는 어떤지도 재지 않았다.

## 앱을 지키는 쪽에서 본 것

이 실습에서 Frida가 바꾼 건 기기 안의 boolean 하나였고, spawn으로 붙으면 앱의 첫 static 초기화부터 그 값이 바뀌었다. 유료 기능을 여는 판정을 서버가 내리는 앱이라면 이 훅으로 바뀌는 건 화면뿐이다(서버 검증 흐름은 [Atlas C48](/posts/android-concept-atlas-c48-play-integrity/)). 확인은 `gate.js` 같은 훅을 자기 릴리스 빌드에 걸어 둔 채 유료 기능 API를 불러 서버가 거절하는지 보면 된다.

`Probe` 같은 검사는 이번 실험에서 실제로 에이전트를 봤다. spawn했을 때는 `App.<clinit>`에서 이미 `frida_maps=9`였고, attach 뒤에는 `frida-agent-64.so` memfd와 `gdbus`, `gmain`, `pool-frida` 스레드가 보였다. 다만 `Probe`에 박아 둔 이름 중 `gum-js-loop`은 attach 뒤 목록에 없었고 이름에 frida가 든 `pool-frida`가 대신 걸렸다. 스레드 이름 몇 개에 기대는 검사는 Frida 버전이 바뀌면 빗나갈 수 있다. 그리고 이 검사도 같은 프로세스 안의 Java 코드라서 `Gate`를 바꾼 것과 같은 방식으로 반환값을 바꿀 수 있다. 그 우회를 직접 돌려 보지는 않았다.

*다음 글: [ClassLoader와 동적 로딩](/posts/android-lab-p1c09-classloader-dynamic-loading/)*
