---
layout: post
title: "Kotlin 코루틴과 structured concurrency — 취소를 삼키는 catch"
date: 2026-11-13 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Kotlin, Coroutine, StructuredConcurrency, CancellationException, GlobalScope, detekt, CachedAppsFreezer]
excerpt: "suspend 함수를 디컴파일해 label로 도는 상태 기계를 확인하고, Android 13 에뮬레이터에서 로그아웃 뒤에도 GlobalScope 작업이 옛 토큰으로 폴링하는 것을 봤다. catch (e: Exception)이 취소를 삼킨 루프는 isActive=false인 채 CPU를 110% 안팎으로 쓰다가 600초 뒤 프리저에 얼었고, 앱을 다시 열자 이어서 돌았다."
---

Android 앱의 백그라운드 작업은 이제 거의 코루틴으로 짠다. 로그아웃 버튼이 `finish()`를 부르면 화면과 ViewModel은 사라진다. 그 화면이 띄운 코루틴도 같이 끝나는지는 어느 스코프에서 띄웠는지, catch 블록을 어떻게 썼는지에 달려 있다. 코루틴의 취소는 예외로 구현돼 있어서 습관처럼 쓰는 `catch (e: Exception)` 한 줄이 취소를 삼킬 수 있다.

실험 앱은 Kotlin 1.9.24(K1 컴파일러), kotlinx-coroutines 1.8.1, androidx lifecycle 2.8.3으로 만든 `io.seika.coroutine`이다. AGP 8.5.2로 debug APK를 빌드해 Android 13(API 33) x86_64 userdebug 에뮬레이터에 올렸고, 캐시된 앱 프리저를 견줄 때만 Android 16(API 36) 이미지를 잠깐 띄웠다. `fun main()`이 있는 실험 코드는 호스트 JVM에서 돌리지 않았다. 빌드한 APK는 앱으로 설치하고, 같은 파일을 `/data/local/tmp`에도 올려 클래스 이름만 바꿔 가며 `app_process`로 에뮬레이터의 ART 위에서 실행했다. gradle과 javap 명령은 프로젝트 루트에서 친다.

```bash
gradle --no-daemon assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb push app/build/outputs/apk/debug/app-debug.apk /data/local/tmp/p2c01.apk
```

## suspend 함수를 풀면 나오는 switch(label)

코루틴이 무엇으로 컴파일되는지부터 봤다. 중단 지점이 두 군데 있는 함수를 `Suspend.kt`에 두었다. 파일 전체이고, 11행과 12행이 중단 지점이다.

```kotlin
package io.seika.coroutine

import kotlinx.coroutines.delay

suspend fun loadSalt(): Int {
    delay(5)
    return 42
}

suspend fun fetchToken(user: String): String {
    val salt = loadSalt()      // 중단 지점 1
    delay(10)                  // 중단 지점 2
    return "$user:$salt"
}
```

빌드된 클래스를 `javap`로 보면 소스에 없던 인자가 붙어 있다.

```text
$ javap -cp app/build/tmp/kotlin-classes/debug -p io.seika.coroutine.SuspendKt 'io.seika.coroutine.SuspendKt$fetchToken$1' 'SwallowKt$main$1$job$1'
Compiled from "Suspend.kt"
public final class io.seika.coroutine.SuspendKt {
  public static final java.lang.Object loadSalt(kotlin.coroutines.Continuation<? super java.lang.Integer>);
  public static final java.lang.Object fetchToken(java.lang.String, kotlin.coroutines.Continuation<? super java.lang.String>);
}
Compiled from "Suspend.kt"
final class io.seika.coroutine.SuspendKt$fetchToken$1 extends kotlin.coroutines.jvm.internal.ContinuationImpl {
  java.lang.Object L$0;
  int I$0;
  java.lang.Object result;
  int label;
  io.seika.coroutine.SuspendKt$fetchToken$1(kotlin.coroutines.Continuation<? super io.seika.coroutine.SuspendKt$fetchToken$1>);
  public final java.lang.Object invokeSuspend(java.lang.Object);
}
Compiled from "Swallow.kt"
final class SwallowKt$main$1$job$1 extends kotlin.coroutines.jvm.internal.SuspendLambda implements kotlin.jvm.functions.Function2<kotlinx.coroutines.CoroutineScope, kotlin.coroutines.Continuation<? super kotlin.Unit>, java.lang.Object> {
  int I$0;
  int I$1;
  int label;
  SwallowKt$main$1$job$1(kotlin.coroutines.Continuation<? super SwallowKt$main$1$job$1>);
  public final java.lang.Object invokeSuspend(java.lang.Object);
  public final kotlin.coroutines.Continuation<kotlin.Unit> create(java.lang.Object, kotlin.coroutines.Continuation<?>);
  public final java.lang.Object invoke(kotlinx.coroutines.CoroutineScope, kotlin.coroutines.Continuation<? super kotlin.Unit>);
  public java.lang.Object invoke(java.lang.Object, java.lang.Object);
}
```

`fetchToken(String)`은 `fetchToken(String, Continuation)`이 됐고 반환형은 `String`에서 `Object`로 바뀌었다. 함수가 중간에 멈추면 결과 대신 `COROUTINE_SUSPENDED`라는 표식 객체를 돌려주고, 나중에 결과가 준비되면 덧붙은 `Continuation`을 거쳐 이어서 실행되기 때문에 반환형이 넓어진다. Kotlin 코루틴 설계 문서 KEEP에 [이 continuation-passing 변환](https://github.com/Kotlin/KEEP/blob/54993607f09e92444ccf64d985c37885c8ee6e22/proposals/coroutines.md#L870-L892)과 [suspend 함수가 중단 지점마다 상태를 하나씩 갖는 상태 기계로 컴파일된다는 설명](https://github.com/Kotlin/KEEP/blob/54993607f09e92444ccf64d985c37885c8ee6e22/proposals/coroutines.md#L903-L907)이 있다.

함수 본문은 보통 Android Studio의 Show Kotlin Bytecode 창에서 Decompile을 눌러 본다. 여기서는 IDE를 띄우지 않고 컴파일된 `SuspendKt` 클래스 파일들을 `ff/in`에 모아 둔 뒤, 그 기능이 쓰는 IntelliJ Java Bytecode Decompiler, 곧 Android Studio에 번들된 Fernflower(`plugins/java-decompiler/lib/java-decompiler.jar`)를 `ConsoleDecompiler`로 명령줄에서 돌려 `ff/out`에 풀었다. 캡처의 `$AS`는 Android Studio 설치 폴더다.

![Android Studio 번들 Fernflower(java-decompiler.jar ConsoleDecompiler)로 디컴파일한 fetchToken: 시그니처 fetchToken(String user, Continuation var1)이 Object를 반환하고, 익명 ContinuationImpl에 L$0·I$0·result·label 필드, invokeSuspend가 label에 Integer.MIN_VALUE를 OR한 뒤 fetchToken(null, this)를 다시 부르며, IntrinsicsKt.getCOROUTINE_SUSPENDED() 비교와 switch($continuation.label)의 case 0·1·2, default의 IllegalStateException, label = 2 다음 DelayKt.delay(10L) 호출이 보이는 터미널](/assets/img/android-mastery/p2c01/01-fernflower-state-machine.png)

위에서부터 읽으면 이렇다. 입구에서 넘어온 `var1`이 이미 이 함수의 Continuation이고 `label`에 `Integer.MIN_VALUE` 비트가 켜져 있으면 그 비트를 끄고 재개 경로로 간다. 그렇지 않으면 처음 호출이므로 새 `ContinuationImpl`을 만든다. 지역 변수 `user`는 객체 칸 `L$0`에, `salt`는 int 칸 `I$0`에 저장된다. 중단 지점 두 곳이 `label` 0, 1, 2의 상태를 만들고, case 0은 `label = 1`로 바꾼 뒤 `loadSalt($continuation)`을 부른다. 그 반환값이 `var5`, 곧 `COROUTINE_SUSPENDED`이면 그대로 `return var5` 한다. 중단은 결국 함수가 반환하는 일이고, 스레드는 이 return으로 풀려나 다른 일을 하러 간다. 재개될 때 지역 변수는 Continuation 필드에서 다시 읽힌다.

이 상태 기계를 "생성된 Continuation 클래스의 `invokeSuspend` 안에 있는 큰 switch"로 설명하는 글이 많은데, 이름 있는 suspend 함수에서는 그렇지 않았다. 화면 속 익명 `ContinuationImpl`의 `invokeSuspend`는 결과를 `result`에 넣고 `label`에 부호 비트를 켠 뒤 `fetchToken(null, this)`를 다시 부르는 게 전부다. `javap -c`로 본 바이트코드도 같다.

```text
  public final java.lang.Object invokeSuspend(java.lang.Object);
    Code:
       0: aload_0
       1: aload_1
       2: putfield      #41                 // Field result:Ljava/lang/Object;
       5: aload_0
       6: aload_0
       7: getfield      #44                 // Field label:I
      10: ldc           #45                 // int -2147483648
      12: ior
      13: putfield      #44                 // Field label:I
      16: aconst_null
      17: aload_0
      18: checkcast     #47                 // class kotlin/coroutines/Continuation
      21: invokestatic  #52                 // Method io/seika/coroutine/SuspendKt.fetchToken:(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;
      24: areturn
```

`tableswitch { // 0 to 2 }`는 `fetchToken` 메서드 본문에 있다. `invokeSuspend` 안에 switch가 들어가는 쪽은 `launch { }`에 넘기는 suspend 람다다. 뒤에서 돌릴 `Swallow.kt`의 람다 클래스 `SwallowKt$main$1$job$1`은 `SuspendLambda`를 상속하고, 그 `invokeSuspend`에 `tableswitch { // 0 to 1 }`이 들어 있었다. `label`의 부호 비트는 "지금 재개 중인 Continuation"이라는 표시로, `invokeSuspend`가 켜고 함수 입구가 끈다.

jadx 1.5.5로 같은 APK를 열면 `fetchToken`과 `loadSalt` 모두 "Code decompiled incorrectly, please refer to instructions dump."로 디컴파일에 실패하고 주석 안에 `switch(r2) { case 0: goto L40; ... }` 같은 레지스터 수준 덤프만 남는다. 대신 Continuation 클래스에 붙은 디버그 메타데이터는 그대로 보여 준다.

```text
@DebugMetadata(c = "io.seika.coroutine.SuspendKt", f = "Suspend.kt", i = {0, 1, 1}, l = {11, 12}, m = "fetchToken", n = {"user", "user", "salt"}, s = {"L$0", "L$0", "I$0"})
```

`l = {11, 12}`가 위 파일의 두 중단 지점 행이고, `n`과 `s`는 지역 변수 `user`가 `L$0`에, `salt`가 `I$0`에 저장된다는 대응표다. 코루틴이 많은 앱을 리버싱할 때 변수 이름을 되살려 주는 단서인데, debug 빌드에서 본 것이다. R8로 줄인 release 빌드에 이 어노테이션이 남는지, K2 컴파일러가 같은 모양을 만드는지는 이번에 확인하지 않았다.

## 디스패처를 바꿔도 pid와 uid는 그대로

디스패처를 바꾸면 스레드 말고 무엇이 달라지는지 보려고, 앱의 `onCreate`에서 디스패처마다 자기 위치를 찍게 했다.

```kotlin
    private fun where(label: String) {
        val ctx = File("/proc/self/attr/current").readText().trim('\u0000', '\n')
        Log.i(TAG, "%-18s pid=%d uid=%d thread=%s selinux=%s".format(label, Process.myPid(), Process.myUid(), Thread.currentThread().name, ctx))
    }
    ...
        where("Dispatchers.Main")
        lifecycleScope.launch(Dispatchers.IO) { where("Dispatchers.IO") }
        lifecycleScope.launch(Dispatchers.Default) { where("Dispatchers.Default") }
```

![앱을 띄운 뒤 logcat에서 Dispatchers.Main·IO·Default가 모두 pid=6403 uid=10179 selinux=u:r:untrusted_app:s0:c179,c256,c512,c768로 같고 IO는 DefaultDispatcher-worker-1, Default는 worker-2에서 돌며, lifecycleScope와 viewModelScope 컨텍스트가 SupervisorJobImpl{Active}와 Dispatchers.Main.immediate, ps -T에는 같은 u0_a179와 같은 라벨의 DefaultDispatch 스레드 5개와 DefaultExecutor가 보이는 터미널](/assets/img/android-mastery/p2c01/02a-dispatcher-same-process.png)

Main, IO, Default 어디서 찍어도 pid 6403, uid 10179, SELinux 컨텍스트 `u:r:untrusted_app:s0:c179,c256,c512,c768`이 같다. IO로 보낸 작업은 `DefaultDispatcher-worker-1`에서, Default로 보낸 작업은 `worker-2`에서 돌았으니 두 디스패처는 이름까지 같은 워커 풀을 나눠 쓴다. `ps -T`의 `DefaultDispatch`는 커널 comm이 15자에서 잘린 모습이고, 이 스레드들도 USER와 LABEL이 메인 스레드와 같다. 그러니 민감한 처리를 `Dispatchers.IO`로 옮겨도 권한도 SELinux 도메인도 그대로다([UID 샌드박스](/posts/android-concept-atlas-c09-uid-sandbox/)).

`lifecycleScope`와 `viewModelScope`의 컨텍스트는 둘 다 `[SupervisorJobImpl{Active}, Dispatchers.Main.immediate]`로 찍혔다. lifecycle 2.8.3 릴리스 커밋의 소스에서도 [`viewModelScope`는 `Dispatchers.Main.immediate`에 `SupervisorJob()`을 더해 만들고](https://android.googlesource.com/platform/frameworks/support/+/92cc6e5d71efd12345ce7ba558cbc2a29926e9ac/lifecycle/lifecycle-viewmodel/src/commonMain/kotlin/androidx/lifecycle/viewmodel/internal/CloseableCoroutineScope.kt#51), Main 디스패처가 없는 플랫폼에서는 `EmptyCoroutineContext`로 대신한다. [`lifecycleScope`도 `SupervisorJob() + Dispatchers.Main.immediate`](https://android.googlesource.com/platform/frameworks/support/+/92cc6e5d71efd12345ce7ba558cbc2a29926e9ac/lifecycle/lifecycle-common/src/commonMain/kotlin/androidx.lifecycle/Lifecycle.kt#320)다. 앱에 들어간 바이트코드도 jadx로 열어 같은 구성인 것을 확인했다.

`app_process`로 돌린 `Threads` 실험은 `Dispatchers.Default`에서 부모 하나가 자식 코루틴 100,000개를 띄우고, 각 자식이 자기 스레드 이름을 기록한 뒤 `delay(30_000)`으로 잠들게 한다. 3초 뒤 거쳐 간 스레드 수, `/proc/self/task` 항목 수, `System.gc()` 두 번 뒤의 힙 사용량을 잰다. 이어서 `Thread.sleep(300)` 하는 블로킹 작업 200개를 Default와 IO에 각각 던진다.

```kotlin
        val parent = launch(Dispatchers.Default) {
            repeat(100_000) { launch { names.add(Thread.currentThread().name.substringBefore(" @")); delay(30_000) } }
        }
```

![app_process로 io.seika.coroutine.demo.Threads를 돌린 터미널: CPU 4개, 프로세스 스레드 14개, 힙 사용 449 KB에서 시작해 delay 중인 자식 코루틴 100,000개가 거쳐 간 스레드 3개, 프로세스 스레드 19개, 힙 사용 29,235 KB이고, Thread.sleep(300) 작업 200개는 Dispatchers.Default에서 스레드 4개로 15,076 ms, Dispatchers.IO에서 스레드 64개로 1,212 ms](/assets/img/android-mastery/p2c01/02b-threads-100k-coroutines.png)

100,000개 실험에서 delay로 잠든 코루틴들이 거쳐 간 스레드는 3개였다(한 번 더 돌렸을 때는 4개). 프로세스 스레드는 14개에서 19개로 다섯 늘었는데, 앱의 `ps -T`에 비춰 보면 Default 워커들과 delay 타이머용 `DefaultExecutor`로 보인다. 이 실험에서 프로세스의 스레드 목록을 따로 찍지는 않았다. 대신 힙이 449 KB에서 29,235 KB로 28,786 KB(약 28.1 MiB) 불었다. 코루틴 하나에 295바이트쯤이다. 잠든 코루틴은 힙 위의 Continuation 객체로 남고 스레드는 차지하지 않는다. 그러니 입력이 들어올 때마다 스코프에 `launch`를 쌓는 코드가 먼저 바닥낼 자원은 스레드 쪽보다 힙 쪽이다. OOM이나 ANR까지 밀어 보지는 않았다.

블로킹 작업은 사정이 다르다. `Thread.sleep(300)` 200개가 Default에서는 4스레드로 15,076 ms(200/4 × 300 ms), IO에서는 64스레드로 1,212 ms 걸렸다. 1.8.1 소스의 [Default 코어 풀 크기는 `AVAILABLE_PROCESSORS.coerceAtLeast(2)`](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/jvm/src/scheduling/Tasks.kt#L28-L33)이고, [IO 병렬도는 `64.coerceAtLeast(AVAILABLE_PROCESSORS)`](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/jvm/src/scheduling/Dispatcher.kt#L54-L62)다. 에뮬레이터 CPU가 4개라 숫자가 그대로 맞는다. 유휴 워커는 [60초 뒤 사라지기](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/jvm/src/scheduling/Tasks.kt#L43-L46) 때문에 앱 안의 워커 수는 측정할 때마다 3개, 5개로 달랐다.

## 로그아웃 버튼을 누른 뒤 남은 작업

앱 화면에는 현재 토큰을 보여 주는 "로그인됨" 문구와 "로그아웃" 버튼만 있다. `onCreate`는 `Session.token`에 난수 토큰을 넣고 1초 폴링을 `GlobalScope.launch(Dispatchers.IO)`, `lifecycleScope.launch`, `PollViewModel`의 `viewModelScope`에 하나씩 띄운다. `lifecycleScope`에는 catch가 취소를 삼키는 루프도 하나 붙였다. 생명주기 스코프 작업은 `finally`에서 "루프 종료"를 찍는다. 그중 GlobalScope 작업과 catch 루프가 아래 코드다.

```kotlin
        val captured = Session.token
        // 생명주기에 안 묶인 작업
        GlobalScope.launch(Dispatchers.IO) {
            var n = 0
            while (true) {
                Log.i(TAG, "[GlobalScope] poll #${++n} 보낸 토큰=$captured 현재 세션=${Session.token}")
                delay(1000)
            }
        }
        ...
        // 생명주기에 묶였지만 catch(Exception)이 취소를 삼키는 작업
        lifecycleScope.launch(Dispatchers.Default) {
            var n = 0L
            var last = 0L
            while (true) {
                try { n++; delay(1000) } catch (e: Exception) { /* 오류는 로그만 남기고 계속 */ }
                val now = SystemClock.elapsedRealtime()
                if (now - last >= 1000) { Log.i(TAG, "[lifecycleScope+catch] 반복 누계 $n, isActive=$isActive"); last = now }
            }
        }
```

로그아웃 버튼은 `Session.token = null` 뒤 `finish()`를 부른다. Android 12부터는 런처에서 띄운 루트 액티비티에서 BACK을 눌러도 액티비티가 destroy되지 않아서, BACK 대신 이 버튼으로 로그아웃을 흉내 냈다. 좌표 (540, 510)은 `uiautomator dump`로 얻은 버튼 영역 `[48,447][1032,573]`의 가운데다.

![로그아웃 버튼(input tap 540 510) 뒤 logcat: 11:28:16.408 로그아웃 다음 lifecycleScope와 viewModelScope 루프 종료, ViewModel.onCleared(), Activity.onDestroy() isFinishing=true가 차례로 찍히고, GlobalScope는 poll #5~#8에서 보낸 토큰=tok-9352 현재 세션=null로 계속 돌며, catch(Exception) 루프는 isActive=false인데 반복 누계가 4, 29815, 69218, 108392로 뛰고, top에서 io.seika.coroutine이 112 %CPU인 터미널](/assets/img/android-mastery/p2c01/03-logout-globalscope.png)

생명주기 스코프는 약속대로 끊겼다. 16.408초에 로그아웃을 누르고 0.3초 뒤 `lifecycleScope`와 `viewModelScope`의 루프가 `finally`를 탔고, 곧바로 `ViewModel.onCleared()`가 불렸다. 순서가 하나 눈에 띄었다. 두 스코프의 취소와 `onCleared()`가 `Activity.onDestroy()` 본문의 로그(내 코드에서 `super.onDestroy()`보다 앞에 있다)보다 먼저 찍혔다. lifecycle 2.8.3에서 API 29 이상이면 androidx가 [`ON_DESTROY`를 `onActivityPreDestroyed` 콜백에서 보내고](https://android.googlesource.com/platform/frameworks/support/+/92cc6e5d71efd12345ce7ba558cbc2a29926e9ac/lifecycle/lifecycle-runtime/src/androidMain/kotlin/androidx/lifecycle/ReportFragment.android.kt#145), activity 1.9.0의 `ComponentActivity`는 [그 이벤트에서 구성 변경 중이 아니면 `viewModelStore.clear()`를 부른다](https://android.googlesource.com/platform/frameworks/support/+/fdf742dd71a144f62554c9d810891993dcfb9fa8/activity/activity/src/main/java/androidx/activity/ComponentActivity.kt#266). `viewModelScope`는 키를 붙인 closeable로 ViewModel에 등록되는데, [`clear()`는 이런 closeable을 먼저 닫고 마지막에 `onCleared`를 부른다](https://android.googlesource.com/platform/frameworks/support/+/92cc6e5d71efd12345ce7ba558cbc2a29926e9ac/lifecycle/lifecycle-viewmodel/src/commonMain/kotlin/androidx/lifecycle/ViewModel.kt#158). 그래서 액티비티의 `onDestroy()`가 실행될 무렵에는 두 스코프의 자식이 이미 취소된 상태다.

GlobalScope 작업은 어느 부모에도 묶이지 않았으니 취소를 받을 길이 없다. poll #5부터 #8까지 "보낸 토큰=tok-9352 현재 세션=null"이 1초마다 찍혔다. 세션 객체는 비웠어도 작업을 띄울 때 클로저에 잡힌 `captured`는 그대로다. 이 로그 자리에 네트워크 요청이 있었다면 로그아웃한 사용자의 토큰이 계속 서버로 나갔을 것이다. 서버가 로그아웃 때 토큰을 무효화하지 않으면 그 요청은 통한다([인증·세션(C45)](/posts/android-concept-atlas-c45-auth-session-oauth-passkey/)).

kotlinx는 `GlobalScope`에 [`@DelicateCoroutinesApi`](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/common/src/CoroutineScope.kt#L212-L213)를 붙여 두었고, opt-in 없이 쓴 `GlobalWarn.kt`를 빌드하면 컴파일러가 경고를 낸다. 실험 앱의 `MainActivity`는 `@OptIn(DelicateCoroutinesApi::class)`를 달아 이 경고를 꺼 둔 상태였다.

```text
w: ./app/src/main/java/io/seika/coroutine/demo/GlobalWarn.kt:9:5 This is a delicate API and its use requires care. Make sure you fully read and understand documentation of the declaration that is marked as a delicate API.
```

catch 루프는 더 나빴다. `lifecycleScope`에 묶여 있어 취소 신호는 받았고 `isActive=false`가 찍혔는데 멈추지 않았다. 1초에 한 번 돌던 루프의 누계가 4에서 29815, 69218, 108392로 초당 4만 번 가까이 뛰었다. `delay(1000)`이 기다리지 않고 곧장 예외를 던지기 때문이다. 화면이 없는 프로세스가 `top`에서 112 %CPU를 쓴다. 앞서 한 번 더 돌렸을 때는 로그아웃 3분여 뒤에 116 %CPU, TIME+ 3:52였다. 로그아웃 뒤 `dumpsys activity activities`에는 이 패키지의 액티비티가 하나도 없었다. 액티비티는 사라졌는데 프로세스는 캐시 상태로 살아서 루프를 돌리고 있었다. 권한이 넘어가지는 않지만, 세션이 끝난 뒤에도 옛 토큰이 쓰이고 배터리가 샌다.

## 프리저가 얼린 프로세스를 다시 깨우면

"로그아웃 뒤에도 계속 돈다"가 언제까지인지 재 봤다. Android 11부터 들어온 [cached apps freezer](https://source.android.com/docs/core/perf/cached-apps-freezer)는 캐시 상태 프로세스를 cgroup freezer로 얼린다. API 33 이미지의 설정은 이랬다.

```text
$ adb -s emulator-5602 shell dumpsys activity settings | grep -iE "freez"
  use_freezer=true
  freeze_statsd_sample_rate=0.1
  freeze_debounce_timeout=600000
```

앱을 띄우고 로그아웃을 누른 뒤 60초마다 `top`의 CPU, `/sys/fs/cgroup/uid_<uid>/pid_<pid>/cgroup.freeze`, `dumpsys activity processes`의 `curProcState`와 `isFrozen`, 마지막 GlobalScope 로그와 catch 루프 누계를 받아 적었다. 13분치 중 앞뒤 몇 줄이다.

```text
pid=6881 uid=10179 logout at 11:33:26
t+1m 11:34:26 cpu=108% TIME+=1:08.20 cgroup.freeze=0 curProcState=18 isFrozen=false | last GlobalScope: 11:34:26.657 #76 | last swallow: 11:34:27.041 1028212
t+2m 11:35:27 cpu=112% TIME+=2:14.07 cgroup.freeze=0 curProcState=18 isFrozen=false | last GlobalScope: 11:35:27.978 #137 | last swallow: 11:35:28.140 2450868
...
t+9m 11:42:35 cpu=116% TIME+=9:52.88 cgroup.freeze=0 curProcState=18 isFrozen=false | last GlobalScope: 11:42:35.190 #561 | last swallow: 11:42:35.276 13938347
t+10m 11:43:36 cpu=0.0% TIME+=10:48.27 cgroup.freeze=1 curProcState=18 isFrozen=true | last GlobalScope: 11:43:26.302 #612 | last swallow: 11:43:26.280 15611705
t+11m 11:44:37 cpu=0.0% TIME+=10:48.27 cgroup.freeze=1 curProcState=18 isFrozen=true | last GlobalScope: 11:43:26.302 #612 | last swallow: 11:43:26.280 15611705
...
t+13m 11:46:39 cpu=0.0% TIME+=10:48.27 cgroup.freeze=1 curProcState=18 isFrozen=true | last GlobalScope: 11:43:26.302 #612 | last swallow: 11:43:26.280 15611705
```

로그아웃이 11:33:26, 마지막 로그가 11:43:26이다. 그 600초 동안 GlobalScope의 폴링 번호는 #612까지 올라갔고(앱 시작부터 센 번호라 로그아웃 뒤로 치면 600번 가까이다), catch 루프 누계는 1,561만, 프로세스 전체의 TIME+는 10분 48초가 됐다. 11:43:26 뒤로는 로그가 끊겼고, 다음 표본에서 `cgroup.freeze=1`과 CPU 0이 찍혔다. 600초는 위 설정의 `freeze_debounce_timeout=600000`이고, Android 13 소스의 [`DEFAULT_FREEZER_DEBOUNCE_TIMEOUT = 600_000L`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-release/services/core/java/com/android/server/am/CachedAppOptimizer.java#134) 기본값 그대로다.

얼린 뒤 앱을 다시 열었다. `LaunchState: WARM`, pid는 6881 그대로였다.

```text
reopen at 11:47:04
11:47:09.682 [lifecycleScope+catch] 반복 누계 15650536, isActive=false
11:47:09.916 [lifecycleScope] poll #4
11:47:09.916 [GlobalScope] poll #617 보낸 토큰=tok-6198 현재 세션=tok-2854
11:47:09.993 [GlobalScope] poll #4 보낸 토큰=tok-2854 현재 세션=tok-2854
11:47:09.993 [lifecycleScope+catch] 반복 누계 3, isActive=true
11:47:10.681 [lifecycleScope+catch] 반복 누계 15678312, isActive=false
11:47:10.929 [GlobalScope] poll #618 보낸 토큰=tok-6198 현재 세션=tok-2854
```

옛 GlobalScope 작업이 #612 다음 번호로 이어서 돌며(발췌에는 #617, #618) 지난 세션의 `tok-6198`을 들고 있고, 새 세션의 작업(`tok-2854`, poll #4)이 그 옆에서 따로 돈다. 취소를 삼킨 옛 루프도 `isActive=false`인 채 1,565만에서 다시 폭주했다. 얼어 있던 3분 반쯤 동안에도 옛 작업의 Continuation과 거기 붙잡힌 토큰은 힙에 그대로 있었고, 깨어나자 멈춘 자리에서 이어서 돌았다.

API 36 이미지(`sec-36-std`, 빌드 BE2A.250530.026.F3)에서 같은 APK로 5초 간격으로 재 보니 로그아웃 약 12초 뒤에 얼었다. TIME+는 0:09.36에서 멈췄다. source.android.com 문서는 Android 14 이상에서 캐시 상태에 들어가고 10초 뒤 얼린다고 적고 있다. 여기서도 다시 열자(WARM, pid 2520 그대로) 옛 작업이 `tok-1604`를 들고 새 세션 `tok-9831` 옆에서 돌았고 옛 catch 루프 누계는 46543에서 54073으로 다시 뛰었다. API 36에서는 같은 `cgroup.freeze` 경로를 읽을 수 없어서(오류 출력은 버렸다) `isFrozen=true`와 멈춘 TIME+로 판정했다. 프로세스가 force-stop이나 LMK로 죽으면 코루틴도 같이 사라진다. 실기기 제조사 설정에서 언제 얼리는지와 LMK가 캐시 프로세스를 죽이는 경우는 재현하지 않았다. cgroup 프리저 자체는 [seccomp·cgroups(C24)](/posts/android-concept-atlas-c24-seccomp-namespaces-cgroups-capabilities/)에서 다뤘다.

## catch (e: Exception)에 걸리는 CancellationException

catch 루프가 멈추지 않은 까닭을 `Swallow.kt` 하나로 줄여 다시 만들었다. `Swallow.kt`는 패키지 선언 없는 파일이라 클래스 이름이 `SwallowKt`가 된다. 파일 전체다.

```kotlin
import kotlinx.coroutines.*

fun main() = runBlocking {
    val job = launch(Dispatchers.Default) {
        repeat(1000) { i ->
            try {
                println("작업 $i")
                delay(100)               // 취소 확인 지점
            } catch (e: Exception) {     // 함정: CancellationException까지 삼킴
                println("삼킴: ${e::class.simpleName} — 계속 진행")
                // rethrow 없음 → 취소가 매 반복 무시된다
            }
        }
    }
    delay(350)
    println("cancel() 호출")
    job.cancel()                          // 취소 요청
    job.join()
    println("종료")
}
```

`job.cancel()`은 스레드를 건드리지 않는다. Job을 취소 상태로 바꿔 두면, 코루틴이 중단돼 있던 자리에서는 곧바로, 실행 중이었다면 다음 중단 지점에서 `CancellationException`이 던져진다. 그 예외가 어떤 클래스인지 `Hierarchy` 실험에서 상위 클래스를 따라 올라가 봤다.

```text
kotlinx.coroutines.JobCancellationException → java.util.concurrent.CancellationException → java.lang.IllegalStateException → java.lang.RuntimeException → java.lang.Exception → java.lang.Throwable → java.lang.Object
e is Exception = true, message = StandaloneCoroutine was cancelled
```

JVM에서 [`CancellationException`은 `java.util.concurrent.CancellationException`의 typealias](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/jvm/src/Exceptions.kt#L11)이고, `IllegalStateException`과 `RuntimeException`을 거쳐 `Exception`의 자식이다. `catch (e: Exception)`에 걸릴 수밖에 없다.

`SwallowKt`를 `app_process`로 돌려 출력을 파일로 받고 앞뒤만 봤다.

![adb shell CLASSPATH=/data/local/tmp/p2c01.apk app_process /system/bin SwallowKt 출력을 swallow.log로 받아 head와 tail로 본 터미널: 작업 0~3, cancel() 호출, 이어서 삼킴: JobCancellationException 줄과 작업 4, 5, 6이 번갈아 나오고 생략 뒤 작업 999와 종료, grep 집계는 작업 줄 1000과 삼킴 줄 997](/assets/img/android-mastery/p2c01/04a-swallow-cancel.png)

`작업 0`부터 `cancel() 호출`, `삼킴: JobCancellationException`, `작업 4`까지는 짐작한 대로다. 처음에는 그 뒤로도 100 ms 간격으로 "작업 N"이 이어질 거라고 생각했는데, 파일 끝은 `작업 999`, `삼킴`, `종료`였다. "작업" 줄 1000개, "삼킴" 줄 997개. cancel 순간 `작업 3`의 delay가 던진 1번에 작업 4부터 999까지의 996번을 더한 수다. cancel 뒤 996회는 기다림 없이 몰아서 돌았다. 이 파일에는 시간을 재는 코드가 없어서, 출력 대신 횟수만 세는 같은 모양의 루프로 cancel부터 `join()`까지를 두 번 재 보니 21 ms, 51 ms였다.

kotlinx 문서의 표현을 빌리면 suspend 함수들은 "check for cancellation of coroutine and throw CancellationException when cancelled."([cancellation-and-timeouts](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/cancellation-and-timeouts.md#L55-L61)) 재개될 때만 확인하는 게 아니다. [`delay`는 `suspendCancellableCoroutine`으로 구현돼 있어서](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/common/src/Delay.kt#L121-L123) 이미 취소된 Job에서 부르면 중단하지 않고 그 자리에서 던진다. catch가 그 예외를 삼키면 다음 반복에서 또 즉시 던지고, 1000번을 채우면 루프가 끝나 `join()`이 돌아온다. 공식 문서에도 [이 루프와 구조가 똑같은 예제](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/cancellation-and-timeouts.md#L106-L140)가 이 함정을 보여 주려고 실려 있다.

`repeat(1000)`은 끝이라도 있다. 실제 폴링 코드는 대개 `while (true)`다. `Spin`은 그 모양을 그대로 옮긴 실험이다.

```kotlin
        val valve = AtomicBoolean(false)          // 실험을 끝내려고 넣은 밸브. cancel()로는 못 멈춘다
        val job = launch(Dispatchers.Default) {
            while (!valve.get()) {
                try { polls.incrementAndGet(); delay(100) } catch (e: Exception) { }
            }
        }
```

![app_process로 io.seika.coroutine.demo.Spin을 돌린 터미널: cancel 전 1초 폴링 10회와 프로세스 CPU 20 ms, cancel 후 1초 폴링 76,908회와 프로세스 CPU 2000 ms(isActive=false, isCancelled=true, isCompleted=false), 밸브를 열고 나서야 join 반환, isCompleted=true](/assets/img/android-mastery/p2c01/04b-spin-while-loop.png)

cancel 전 1초 동안 10번 폴링하고 CPU 20 ms를 쓰던 루프가 cancel 뒤 1초에 76,908번 돌며 CPU 2000 ms를 썼다. 다섯 번 돌린 값은 cancel 뒤 1초에 14,393회에서 76,908회, CPU 1580~2000 ms로 흔들렸지만 코어 1.6~2개분을 태우는 것은 매번 같았다. 상태는 `isActive=false, isCancelled=true, isCompleted=false`다. 취소는 됐는데 끝나지 않은 Job이고, `join()`은 밸브를 열기 전까지 돌아오지 않았다. structured concurrency에서 부모는 자식이 끝날 때까지 완료되지 않으므로, 이런 자식 하나가 `coroutineScope`나 `runBlocking` 전체를 붙잡는다.

## 취소를 지키는 catch 모양

같은 루프(100 ms 간격 1000회, 350 ms에 cancel)를 catch 모양만 바꿔 `Fixes`에서 돌렸다. 아래는 취소를 지키는 쪽의 코드다(`Lab.kt` 46~62행 발췌).

```kotlin
        trial("if (e is CancellationException) throw e") { work ->
            repeat(1000) {
                try { work.incrementAndGet(); delay(100) }
                catch (e: Exception) { if (e is CancellationException) throw e }
            }
        }
        trial("catch (e: IOException)") { work ->
            repeat(1000) {
                try { work.incrementAndGet(); delay(100) } catch (e: IOException) { }
            }
        }
        trial("catch + ensureActive()") { work ->
            repeat(1000) {
                try { work.incrementAndGet(); delay(100) }
                catch (e: Exception) { coroutineContext.ensureActive() }
            }
        }
```

`SwallowFixed.kt`는 `Swallow.kt`에서 catch 블록만 `coroutineContext.ensureActive()`를 먼저 부르게 바꾼 파일이다. 계산만 하는 루프는 `CpuBound`로 따로 쟀다. 100 ms 동안 `System.nanoTime()`을 바쁘게 도는 덩어리 20개를 350 ms 시점에 cancel한다.

![Fixes 실행 결과 catch (e: Exception)·catch (e: Throwable)·runCatching은 cancel 후 996회, CancellationException 재throw·catch (e: IOException)·catch + ensureActive()는 0회, SwallowFixedKt는 작업 0~3과 cancel() 호출 직후 종료, CpuBound는 검사 없음 20/20 덩어리와 cancel→join 1650 ms, ensureActive()·yield()·while (isActive)는 4/20 덩어리와 49~51 ms인 터미널](/assets/img/android-mastery/p2c01/05-catch-variants.png)

`catch (e: Throwable)`과 `runCatching { delay() }`도 `catch (e: Exception)`처럼 cancel 뒤 996회를 돌았다. `runCatching`은 안에서 `Throwable`을 잡아 `Result`로 감싸므로 suspend 호출을 감싸면 똑같이 취소를 삼킨다. 공식 문서도 그 예제 바로 아래에서 이를 경고한다. 반대로 `CancellationException`을 다시 던지거나, 잡을 예외를 `IOException`처럼 좁히거나, catch 안에서 [`ensureActive()`](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/common/src/Job.kt#L593)를 부르면 cancel 뒤 0회, `join()`은 0 ms에 돌아왔다. `ensureActive()`는 Job이 활성 상태가 아니면 그 취소 예외를 다시 던진다. `SwallowFixedKt`는 `cancel() 호출` 바로 다음 줄이 `종료`였다.

중단 지점이 없는 계산은 catch와 무관하게 취소되지 않는다. 검사가 없으면 cancel을 받고도 남은 1.65초를 다 써서 20덩어리를 끝냈다. 덩어리마다 `ensureActive()`, `yield()`, `isActive` 중 하나를 확인하면 350 ms에 진행 중이던 네 번째 덩어리를 마치고 50 ms 안팎에서 멈췄다. 확인 간격이 그대로 취소 지연이 된다. 문서의 [계산 코드를 취소 가능하게 만드는 절](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/cancellation-and-timeouts.md#L142-L180)과 같은 결과다.

## async 실패가 형제로 번지는 길과 supervisorScope가 막는 길

취소와 실패는 Job 계층을 한 길로 오간다. `Propagation`에서 그 길을 따로 확인했다. A는 `coroutineScope` 안에서 100 ms 뒤 `IOException`을 던지는 `async`를 띄우고 본문은 1초 기다린 뒤 `await()`한다. B는 이 일을 `supervisorScope`에서 한다. C는 `CoroutineExceptionHandler`를 단 스코프에서 자식이 `CancellationException`을 던질 때와 `IOException`을 던질 때를 견준다.

```text
[   0 ms] A. coroutineScope + async(100 ms 뒤 IOException), 본문은 1초 대기 후 await
[ 294 ms] A: 본문 delay 가 JobCancellationException 로 끊김
[ 294 ms] A: coroutineScope 밖으로 IOException, await 줄은 실행되지 않음
[   0 ms] B. supervisorScope + 같은 async
[1023 ms] B: 1초 대기 끝, 본문은 멀쩡함
[1023 ms] B: await() 에서 비로소 IOException
[  18 ms] C1: 자식이 CancellationException → handler 미호출, 부모 isActive=true, 형제 isActive=true
[  23 ms] C: handler 호출 ← IOException
[  28 ms] C2: 자식이 IOException → 부모 isActive=false, 형제 isCancelled=true
```

A에서 `async`가 실패하자 `await()`를 부르기도 전에 형제인 본문의 `delay(1000)`이 `JobCancellationException`으로 끊겼고, `coroutineScope`는 원래 예외인 `IOException`을 밖으로 던졌다. `await()` 줄은 실행되지 않았다. 294 ms는 첫 실행 값이고, 다시 돌리면 175~183 ms였다. 100 ms보다 늦은 것은 `app_process` 첫 실행의 클래스 로딩과 인터프리터 비용으로 보인다. 소스 주석에도 [`async`가 실패하면 부모를 취소한다](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/common/src/Builders.common.kt#L61-L63)고 적혀 있다. B에서는 본문이 1초를 다 채웠고 예외는 `await()`에서야 나왔다. supervisor 아래 자식의 실패는 부모와 형제로 번지지 않는다.

C1과 C2가 앞의 함정과 이어진다. 자식이 `CancellationException`을 던지면 handler는 불리지 않고 부모와 형제가 모두 살아 있다. `IOException`이면 handler가 불리고 부모가 취소되며 형제도 취소된다. kotlinx는 `CancellationException`을 오류가 아닌 정상 종료 신호로 다룬다([exception-handling](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/docs/topics/exception-handling.md#L127-L131), [CoroutineExceptionHandler.kt](https://github.com/Kotlin/kotlinx.coroutines/blob/1.8.1/kotlinx-coroutines-core/common/src/CoroutineExceptionHandler.kt#L83-L85)). 취소 신호 자체는 Job 트리를 따라 자식 Job까지 전해진다. 각 코루틴의 코드를 실제로 멈추는 것은 중단 지점에서 던져지는 이 예외라서, 넓은 catch가 이 예외를 삼키면 Job은 취소 상태인데 코드는 계속 돈다. 앞의 `Spin`이 `isActive=false, isCancelled=true, isCompleted=false`에 머문 것이 그 경우다.

## 취소를 예외로 나르는 이유

스레드라면 밖에서 강제로 멈출 수 있지 않을까 싶어 Android에서 `Thread.stop()`을 불러 봤다.

```text
$ adb -s emulator-5602 shell CLASSPATH=/data/local/tmp/p2c01.apk app_process /system/bin io.seika.coroutine.demo.ThreadStop
Thread.stop() → java.lang.UnsupportedOperationException: null
```

ART의 libcore는 [`stop()`을 "Android-changed: Throws UnsupportedOperationException." 주석과 함께 무조건 예외를 던지게 바꿔 놓았다](https://android.googlesource.com/platform/libcore/+/refs/heads/android13-release/ojluni/src/main/java/java/lang/Thread.java#1061). Android에서는 실행 중인 스레드를 밖에서 멈추는 API가 막혀 있어서, 스레드는 인터럽트 플래그를, 코루틴은 Job 상태를 코드가 스스로 확인해야 한다. kotlinx.coroutines는 그 확인을 자기 suspend 함수마다 넣어 두고 결과를 예외로 전달한다. 덕분에 `finally` 블록이 취소 때도 실행되지만(앞에서 lifecycleScope 루프가 찍은 "루프 종료 (취소됨)"이 그것이다), 넓은 catch가 그 예외를 가로챌 수도 있다.

## detekt의 취소 규칙은 runCatching만 본다

정적 분석으로 이 패턴을 막을 수 있는지 detekt-cli 1.23.8(GitHub 릴리스 jar)로 확인했다. 기본 설정 위에 코루틴 규칙 `GlobalCoroutineUsage`와 `SuspendFunSwallowedCancellation`을 켜고, type resolution을 위해 kotlin-stdlib 1.9.24와 kotlinx-coroutines-core-jvm 1.8.1 jar를 `--classpath`로 넘겼다(캡처의 `$CP`). 대상 `Cases.kt`에는 catch 모양별 함수를 한 줄씩 두었다. 모든 행의 `delay(100)`에 걸리는 `MagicNumber`와 패키지 경로 규칙 `InvalidPackageDeclaration`은 catch 모양과 무관해서 캡처의 `grep -vE`로 걸러 냈다.

![detekt-cli 1.23.8에 GlobalCoroutineUsage와 SuspendFunSwallowedCancellation을 켠 detekt.yml로 Cases.kt를 검사하고 MagicNumber·MaxLineLength·InvalidPackage를 grep -vE로 걸러 낸 터미널: 10행(e를 로그에 쓰는 catch)은 TooGenericExceptionCaught만, 14행 빈 catch는 SwallowedException·TooGenericExceptionCaught·EmptyCatchBlock, 18행 runCatching은 SuspendFunSwallowedCancellation, 올바른 수정인 22행과 30행에도 TooGenericExceptionCaught, 26행 IOException catch는 catch 관련 규칙이 하나도 걸리지 않음](/assets/img/android-mastery/p2c01/06-detekt-rules.png)

| 행 | catch 모양 | catch 관련으로 걸린 규칙 |
|--|--|--|
| 10 | `e`를 로그에 쓰는 `catch (e: Exception)` | TooGenericExceptionCaught |
| 14 | 빈 `catch (e: Exception) { }` | SwallowedException, TooGenericExceptionCaught, EmptyCatchBlock |
| 18 | `runCatching { delay(100) }` | SuspendFunSwallowedCancellation |
| 22 | `CancellationException` 재throw | TooGenericExceptionCaught, EmptyElseBlock |
| 26 | `catch (e: IOException)` | 없음 |
| 30 | catch 안에서 `ensureActive()` | TooGenericExceptionCaught |

`SwallowedException`이면 잡힐 줄 알았는데, 10행처럼 catch 안에서 `e`를 로그에 찍기만 해도 이 규칙은 삼키지 않은 것으로 보고 넘어갔다. 걸린 것은 빈 catch인 14행뿐이다. 이름이 딱 맞아 보이는 `SuspendFunSwallowedCancellation`은 [`runCatching` 안의 suspend 호출만 보는 규칙](https://detekt.dev/docs/1.23.8/rules/coroutines/)이라 try/catch는 아예 보지 않는다. 게다가 기본 비활성이고 type resolution이 있어야 돈다. `--config` 없이 기본 설정만으로 돌리면 18행 결과 하나만 빠지고 나머지는 같았다. `GlobalCoroutineUsage`도 기본 비활성이라, 켰을 때만 `GlobalWarn.kt:9:5`에 "This use of GlobalScope should be replaced by `CoroutineScope` or `coroutineScope`."가 떴다.

10행 패턴에 기본으로 걸리는 규칙은 [`TooGenericExceptionCaught`](https://detekt.dev/docs/1.23.8/rules/exceptions/) 하나인데, 이 규칙은 취소를 제대로 다시 던지는 22행과 30행에도 뜬다. 규칙을 켜고 앱 소스(`Swallow.kt`, `SwallowFixed.kt`)를 따로 검사했을 때도 두 파일의 catch에는 똑같이 `TooGenericExceptionCaught`만 걸렸다.

## 세션 작업은 로그아웃에 묶고 catch는 좁힌다

로그인 세션에 딸린 작업은 GlobalScope에 띄우지 않는다. 화면과 함께 끝나야 하면 `lifecycleScope`, ViewModel과 함께 끝나야 하면 `viewModelScope`를 쓰고, 화면보다 오래 살아야 하는 세션 작업이라면 로그아웃 처리에서 직접 `cancel()`하는 별도 스코프를 두는 편이 낫다. 토큰은 작업을 띄울 때 지역 변수로 붙잡지 말고 쓸 때마다 세션에서 읽어야 남은 작업이 있더라도 null을 보게 된다. [Android 코루틴 모범 사례](https://developer.android.com/kotlin/coroutines/coroutines-best-practices)도 GlobalScope를 피하고 `CancellationException`을 소비하지 말라고 권한다.

catch는 잡을 예외를 좁히는 게 먼저이고, 넓게 잡아야 하면 첫 줄에서 `CancellationException`을 다시 던지거나 `ensureActive()`를 부른다. 중단 지점이 없는 긴 계산에는 덩어리마다 `ensureActive()`나 `yield()`를 넣는다. 권한을 갈라야 하는 처리는 [별도 프로세스와 isolatedProcess](/posts/android-concept-atlas-c25-isolatedprocess-appzygote/)로 옮긴다.

CI에 detekt를 건다면 `SuspendFunSwallowedCancellation`과 `GlobalCoroutineUsage`를 켜고 type resolution을 맞춰야 한다. try/catch 쪽 취소 누락은 detekt 규칙으로 가려낼 수 없으니 실행해서 확인하는 검사를 하나 둔다. 기준은 "cancel() 호출" 다음에 새 "작업 N" 줄이 하나도 없는 것이다. 맨 앞의 빌드와 push를 마친 뒤 실행한다.

```bash
adb shell CLASSPATH=/data/local/tmp/p2c01.apk app_process /system/bin SwallowFixedKt
```

출력은 이렇다.

```text
작업 0
작업 1
작업 2
작업 3
cancel() 호출
종료
```

앱에서는 로그아웃을 누른 뒤 `logcat -s p2c01:I`에 GlobalScope 줄이 더 나오지 않는지, `top`의 %CPU가 0 근처로 내려가는지를 본다. 앱을 다시 열었을 때 옛 토큰을 든 로그가 나오는지도 함께 봐야 프리저가 가린 작업까지 잡힌다. 이 앱 검사는 고친 빌드로는 돌리지 않았고, 위에 적은 것은 고치기 전 빌드에서 쓴 명령과 판정 기준이다.

참고 자료: [Kotlin 코루틴 KEEP](https://github.com/Kotlin/KEEP/blob/54993607f09e92444ccf64d985c37885c8ee6e22/proposals/coroutines.md) · [Cancellation and timeouts](https://kotlinlang.org/docs/cancellation-and-timeouts.html) · [Coroutine exceptions handling](https://kotlinlang.org/docs/exception-handling.html) · [kotlinx.coroutines 1.8.1](https://github.com/Kotlin/kotlinx.coroutines/tree/1.8.1) · [Android 코루틴 모범 사례](https://developer.android.com/kotlin/coroutines/coroutines-best-practices) · [Cached apps freezer](https://source.android.com/docs/core/perf/cached-apps-freezer) · [detekt 1.23.8 coroutines 규칙](https://detekt.dev/docs/1.23.8/rules/coroutines/) · [프로세스·가상메모리·시스템 콜(C04)](/posts/android-concept-atlas-c04-process-vm-syscall/) · ART 실행 방식
