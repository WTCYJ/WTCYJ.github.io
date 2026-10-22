---
layout: post
title: "Flutter·React Native·Cordova — 로직이 DEX 밖에 있는 앱"
date: 2026-11-07 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Flutter, ReactNative, Hermes, Cordova, reFlutter, dartio]
excerpt: "직접 빌드한 Flutter·React Native·Cordova APK를 열어 보니 Flutter의 상수는 jadx 결과에 없고 libapp.so에 그대로 있었고, RN 번들은 이름만 index.android.bundle인 Hermes v98 바이트코드라 hbctool은 실패하고 hermes-dec은 읽었다. dart:io는 Android 전역 프록시가 들어가는 JVM 시스템 프로퍼티 대신 환경 변수만 보고 루트 인증서도 /system/etc/security/cacerts만 읽는다는 것을 소스와 호스트 프로브로 확인했고, reFlutter는 그중 인증서 검증 쪽만 바꾼다."
---

[22장](/posts/android-lab-p1c22-sanitizer-jni-analysis/)까지는 앱 로직이 DEX에 있고 가끔 JNI로 `.so`에 내려가는 경우만 다뤘다. 크로스플랫폼 프레임워크로 만든 앱은 출발점부터 다르다. jadx가 DEX를 깔끔하게 풀어 줘도 거기에는 엔진을 띄우는 글루 코드뿐이고, 화면과 네트워크 로직은 Dart 스냅샷이나 JS 번들, 웹 페이지로 APK의 다른 자리에 있어서, 어떤 프레임워크인지부터 알아봐야 쓸 도구가 정해진다.

이번에는 세 프레임워크로 앱을 하나씩 직접 만들었다. 셋 다 버튼을 누르면 `http://10.0.2.2:8788/ping` 으로 요청을 보낸다. Flutter와 RN 앱은 여기에 일부러 심은 가짜 API 키를 `X-Demo-Key` 헤더로 싣고, Cordova 앱은 키 없이 ping만 보내는 대신 8788과 8789의 브리지 시험 페이지를 iframe으로 띄우는 IFRAMES 버튼을 하나 더 가진다. 빌드 환경은 Flutter 3.47.7(Dart 3.13.5), React Native 0.87.1(Hermes, 새 아키텍처 켜짐), cordova-android 15.1.0이고 셋 다 targetSdk 36이다. 분석은 모두 호스트에서 APK와 소스를 놓고 했다. 에뮬레이터에 올려서 실제 요청이 어디로 가는지 보는 실험은 이번에 돌리지 못했고, 그 부분은 해당 대목에서 소스 근거로만 말한다. 선수 지식은 [jadx 정적 분석(4장)](/posts/android-lab-p1c04-jadx-static-analysis/), [프록시와 NSC(11장)](/posts/android-lab-p1c11-burp-mitmproxy-intercept/), [WebView 브리지(20장)](/posts/android-lab-p1c20-deeplink-applink-webview/)다.

## 세 APK를 unzip -l 로만 봐도 갈린다

압축 목록에서 로직이 어디 있는지 이미 드러난다. Flutter APK는 DEX가 520 KB짜리 하나뿐이고 `lib/x86_64/` 에 `libapp.so`(3,539,848바이트)와 `libflutter.so`(13,051,424바이트)가 있다. React Native APK는 DEX가 두 개, 엔진인 `libhermesvm.so`, 그리고 `assets/index.android.bundle`(1,000,900바이트)을 담고 있다. Cordova APK는 DEX가 여섯 개로 쪼개져 있지만 앱 고유의 내용은 `assets/www/` 아래 `index.html`, `cordova.js`, `js/index.js` 와 `res/xml/config.xml` 에 있다.

![unzip -l 출력. xplat-flutter.apk는 classes.dex 520168바이트와 lib/x86_64/libapp.so 3539848, libflutter.so 13051424. xplat-rn.apk는 classes.dex, classes2.dex, libhermestooling.so, libhermesvm.so, assets/index.android.bundle 1000900. xplat-cordova.apk는 classes.dex~classes6.dex, assets/www/cordova.js, index.html, js/index.js, res/xml/config.xml](/assets/img/android-mastery/p1c23/01-apk-layout.png)

같은 확인을 직접 해 보려면 이 정도면 된다(캡처에 보이는 명령 그대로다).

```bash
unzip -l xplat-flutter.apk | grep -E 'classes[0-9]*\.dex|lib/x86_64/'
unzip -l xplat-rn.apk | grep -E 'classes[0-9]*\.dex|index\.android\.bundle|x86_64/libhermes'
unzip -l xplat-cordova.apk | grep -E 'classes[0-9]*\.dex|assets/www/(index\.html|cordova\.js|js/)|res/xml/config'
```

실무에서 처음 받은 APK도 이 목록으로 판별한다. `libflutter.so` 와 `libapp.so` 가 보이면 Flutter, `index.android.bundle` 과 `libhermes*.so` 가 보이면 Hermes를 쓰는 React Native, `assets/www/cordova.js` 가 보이면 Cordova 계열(Ionic 포함)이다.

## jadx에는 Flutter 엔진 글루뿐, 키는 libapp.so에

Flutter 앱의 Dart 코드는 릴리스 빌드에서 AOT 컴파일되어 `libapp.so` 안의 스냅샷이 된다. 내가 넣은 코드는 이렇다(`lib/main.dart` 의 일부).

```dart
const String demoApiKey = 'XPLAT-FLUTTER-KEY-5c1d9e';
const String pingUrl = 'http://10.0.2.2:8788/ping?from=flutter';
const String pingTlsUrl = 'https://10.0.2.2:8443/ping?from=flutter-tls';
...
      final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
      final req = await client.getUrl(Uri.parse(url));
      req.headers.set('X-Demo-Key', demoApiKey);
      final res = await req.close();
```

jadx로 풀면 `io/flutter` 아래에는 `embedding`, `plugin`, `plugins`, `view` 디렉터리만 나온다. 앱 패키지의 `MainActivity` 는 `public final class MainActivity extends k6 {}` 한 줄인데, `k6` 은 R8이 `FlutterActivity` 를 줄여 붙인 이름이다. 디컴파일된 소스 전체에서 `XPLAT-FLUTTER-KEY` 를 grep하면 아무것도 나오지 않는다. 반면 `libapp.so` 를 `grep -a` 로 훑으면 두 ping URL과 `XPLAT-FLUTTER-KEY-5c1d9e` 가 평문으로 튀어나온다.

![jadx -d jadx-flutter 결과의 io/flutter에는 embedding, plugin, plugins, view만 있고 MainActivity는 'extends k6 {}'. grep XPLAT-FLUTTER-KEY는 'no match in decompiled DEX'. llvm-readelf --dyn-syms libapp.so는 _kDartSnapshotText, _kDartSnapshotData, _kDartSnapshotBuildId. grep -a는 libapp.so에서 http://10.0.2.2:8788/ping?from=flutter, https://10.0.2.2:8443/ping?from=flutter-tls, XPLAT-FLUTTER-KEY-5c1d9e를 출력](/assets/img/android-mastery/p1c23/02-flutter-dex-vs-libapp.png)

`llvm-readelf --dyn-syms` 로 본 `libapp.so` 의 동적 심볼은 `_kDartSnapshotText`, `_kDartSnapshotData`, `_kDartSnapshotBuildId` 셋이었다. 인터넷에 도는 Flutter 리버싱 글 다수가 `_kDartVmSnapshotData`, `_kDartIsolateSnapshotInstructions` 같은 이름을 보여 주는데, 이번 3.47.7 빌드에는 그 이름들이 없었다. 심볼 이름으로 Flutter를 판별하는 스크립트를 쓴다면 둘 다 봐야 한다.

문자열 상수가 평문으로 남는다는 건 비밀 탐색에는 `strings` 수준으로 충분하다는 뜻이다. 함수 구조를 복원하려면 Dart 스냅샷 전용 도구(Blutter, reFlutter의 dump 모드)가 필요한데, Blutter는 Dart 버전마다 VM을 따로 빌드해야 해서 이번에는 돌리지 않았다.

## 이름만 .bundle인 Hermes 바이트코드 v98

RN 쪽 `assets/index.android.bundle` 은 확장자와 달리 JS 텍스트가 아니다. 첫 16바이트가 `c61f bc03 c103 191f` 로 시작하는데, 이게 Hermes 바이트코드(HBC) 매직이다. Hermes를 켠 릴리스 빌드는 번들을 미리 바이트코드로 컴파일해 같은 파일 이름으로 넣는다. `.hbc` 확장자가 따로 붙지 않으니 파일 이름만 보고 평문 JS라고 짐작하면 틀린다.

[hermes-dec](https://github.com/P1sec/hermes-dec) 0.1.8의 `hbc-file-parser` 는 버전 98, 함수 4,205개, 문자열 5,982개로 읽었다. 문자열 테이블은 평문이라 `grep -a -c XPLAT-RN-KEY` 만으로 1이 나온다. 많이 알려진 [hbctool](https://github.com/bongtrop/hbctool)은 `AssertionError: The HBC version (98) is not supported.` 로 멈췄다. README가 지원 버전으로 59·62·74·76만 적고 있어서 지금 RN이 내놓는 번들에는 맞지 않는다. 같은 파일을 `hbc-decompiler` 에 넣으면 의사 JS가 나오고, 그 18만 번째 줄 근처에 키와 URL이 레지스터 대입으로 나란히 보인다. hermes-dec도 매끈하게 돈 건 아니다. 시작하자마자 버전 98은 정식 지원 대상이 아니라는 경고를 내고 `pass4: LoadFromEnvironment references unknown register` 경고를 줄줄이 찍었는데(캡처에서는 stderr를 버렸다), 그래도 `bundle.js` 는 키와 URL이 온전한 채로 나왔다.

![xxd -l 16 index.android.bundle의 첫 바이트 c61f bc03 c103 191f. hbc-file-parser 결과 Version 98, FunctionCount 4205, StringCount 5982. grep -a -c XPLAT-RN-KEY는 1. hbctool disasm은 AssertionError: The HBC version (98) is not supported. hbc-decompiler 출력 bundle.js 180863행 r8 = 'XPLAT-RN-KEY-a83f02', 180865행 r8 = 'http://10.0.2.2:8788/ping?from=rn'](/assets/img/android-mastery/p1c23/03-rn-hermes-bundle.png)

원본 코드에서 키는 `const DEMO_API_KEY = 'XPLAT-RN-KEY-a83f02';` 였고 `fetch(url, { headers: { 'X-Demo-Key': DEMO_API_KEY } })` 로 쓴다. 디컴파일 결과는 변수 이름을 잃었지만 상수와 사용 위치는 그대로 남았다.

자바 쪽과의 연결도 예전 설명과 달라졌다. RN 0.87 템플릿은 `gradle.properties` 에 `newArchEnabled=true` 가 기본이라 JS가 네이티브 모듈을 JSI와 TurboModules로 부른다. JSON 메시지를 큐로 넘기던 옛 브리지는 이 경로에 없다. 네이티브 모듈의 Java/Kotlin 구현은 여전히 DEX에 있으니 jadx로 보고, JS 쪽 호출부는 번들에서 찾는다.

## Flutter 요청이 프록시에 안 잡히는 이유

"Flutter 앱은 Burp에 안 잡힌다"는 말 뒤에는 서로 다른 문제가 겹쳐 있다. 요청이 아예 프록시로 가지 않고, 가더라도 프록시 인증서를 믿지 않으며, NSC의 평문 차단에도 걸리지 않는다. 모두 `dart:io` 가 Android 프레임워크의 자바 네트워크 스택을 거치지 않고 자체 소켓과 BoringSSL을 쓰기 때문에 생긴다.

### 전역 프록시는 JVM 시스템 프로퍼티로 전달된다

Android에서 `settings put global http_proxy` 로 건 전역 프록시는 앱 프로세스에 자바 시스템 프로퍼티로 들어간다. 앱이 뜰 때 [`ActivityThread.java` 6690행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/app/ActivityThread.java#6690)이 `Proxy.setHttpProxyConfiguration(cm.getDefaultProxy())` 를 부르고, 그 안에서 [`Proxy.java` 218~231행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/net/Proxy.java#218)이 값을 박는다.

```java
// frameworks/base core/java/android/net/Proxy.java (android-13.0.0_r1), 218-231행 발췌
    public static void setHttpProxyConfiguration(String host, String port, String exclList,
            Uri pacFileUrl) {
        if (exclList != null) exclList = exclList.replace(",", "|");
        if (false) Log.d(TAG, "setHttpProxySystemProperty :"+host+":"+port+" - "+exclList);
        if (host != null) {
            System.setProperty("http.proxyHost", host);
            System.setProperty("https.proxyHost", host);
        } else {
            System.clearProperty("http.proxyHost");
            System.clearProperty("https.proxyHost");
        }
        if (port != null) {
            System.setProperty("http.proxyPort", port);
            System.setProperty("https.proxyPort", port);
```

OkHttp와 `HttpURLConnection` 은 이 프로퍼티를 읽는 자바 `ProxySelector` 를 따르고, WebView는 같은 프로퍼티를 자기 쪽에서 따로 읽으니 셋 다 결국 이 값을 쓴다. `dart:io` 는 같은 프로세스 안에 있어도 이 자바 프로퍼티를 읽지 않는다. Dart 3.13.5의 `HttpClient` 는 기본 프록시 결정 함수가 [`HttpClient.findProxyFromEnvironment`](https://github.com/dart-lang/sdk/blob/3.13.5/sdk/lib/_http/http_impl.dart#L2795)이고, [`_findProxyFromEnvironment`](https://github.com/dart-lang/sdk/blob/3.13.5/sdk/lib/_http/http_impl.dart#L3251)는 `Platform.environment` 에서 `http_proxy`, `https_proxy`, `no_proxy` 만 찾는다. Android 앱 프로세스에는 이 환경 변수가 없으니 결과는 `DIRECT` 가 된다.

에뮬레이터에서 전역 프록시를 걸고 Flutter와 RN 앱을 비교하는 실험은 이번에 하지 못했다. 대신 같은 Flutter SDK에 들어 있는 Dart 3.13.5와 JDK 21로 호스트(Windows)에서 두 선택 방식을 나란히 돌려 봤다. Dart 쪽 프로브는 이게 전부다.

```dart
import 'dart:io';

// dart:io HttpClient with the default findProxy (= findProxyFromEnvironment)
Future<void> main(List<String> args) async {
  final url = Uri.parse(args.isNotEmpty ? args[0] : 'http://127.0.0.1:8788/ping?from=dart-host');
  final c = HttpClient()..connectionTimeout = const Duration(seconds: 5);
  print('findProxy -> ${HttpClient.findProxyFromEnvironment(url)}');
  try {
    final rs = await (await c.getUrl(url)).close();
    print('HTTP ${rs.statusCode}: ${await rs.transform(SystemEncoding().decoder).join()}');
  } catch (e) {
    print('error: $e');
  }
  c.close(force: true);
}
```

자바 쪽 `Probe.java` 는 `ProxySelector.getDefault().select(uri)` 결과를 찍은 뒤 `HttpURLConnection` 으로 같은 URL을 부른다. 8788에는 받은 요청을 기록하는 작은 HTTP 서버를, 8790에는 mitmproxy 11.0.2 일반 프록시를 띄웠다. 환경 변수 없이 돌린 Dart는 `findProxy -> DIRECT` 로 서버에 직접 갔다. `-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=8790` 을 준 자바는 `[HTTP @ 127.0.0.1/<unresolved>:8790]` 를 골라 프록시를 거쳤다. Dart도 `http_proxy=127.0.0.1:8790` 환경 변수를 주자 그제야 `PROXY 127.0.0.1:8790` 으로 바뀌었다. 서버 로그에는 세 요청이 다 찍혔고 프록시 로그에는 `java-props` 와 `dart-env` 두 건만 남았다.

![호스트 Dart 3.13.5 windows_x64. dart run probe.dart from=dart-noenv는 findProxy -> DIRECT와 HTTP 200 pong (Dart/3.13 (dart:io)). java -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=8790 -Dhttp.nonProxyHosts= Probe.java는 ProxySelector -> [HTTP @ 127.0.0.1/<unresolved>:8790]와 pong (java-probe). http_proxy=127.0.0.1:8790 dart run probe.dart는 findProxy -> PROXY 127.0.0.1:8790. hostserver 로그에는 dart-noenv, java-props, dart-env 세 GET, mitm-proxy 로그에는 java-props와 dart-env 두 GET](/assets/img/android-mastery/p1c23/08-host-dart-env-proxy-vs-java-props.png)

자바 명령에 `-Dhttp.nonProxyHosts=` 를 비워서 넣은 데는 이유가 있다. JDK 기본값이 `localhost`, `127.*`, `[::1]` 을 예외로 두기 때문에 그대로 두면 127.0.0.1 요청은 프록시를 건너뛰고, 비교 자체가 성립하지 않는다.

이 캡처는 Windows 호스트에서 두 런타임이 프록시를 고르는 방식이 다르다는 것만 보여 준다. Android 기기에서 Flutter 앱이 전역 프록시를 무시한다는 것을 직접 측정한 결과는 아니고, 그 결론은 위 두 소스 파일을 이어 붙여 얻은 것이다. 실제 앱에서 프록시로 보내려면 기기 쪽에서 VPN 방식(TunProxy 같은 도구)이나 iptables로 트래픽 자체를 돌리거나, 앱 코드에서 `HttpClient.findProxy` 를 바꾸는 방법을 쓴다. Frida로 엔진의 소켓 연결 경로를 후킹해 목적지를 바꾸는 방법도 있다.

### 신뢰하는 루트는 /system/etc/security/cacerts 하나

프록시로 보냈다 해도 TLS에서 다시 막힌다. Dart의 Android용 인증서 로딩은 [`security_context_linux.cc` 43~53행](https://dart.googlesource.com/sdk/+/refs/tags/3.13.5/runtime/bin/security_context_linux.cc#43)에 있다. `DART_HOST_OS_ANDROID` 일 때 루트 인증서를 바이너리에 넣지 않고 `/system/etc/security/cacerts` 디렉터리 하나를 `LoadRootCertCache` 로 읽는다.

![Dart SDK 3.13.5 runtime/bin/security_context_linux.cc 소스 32~65행. 43행 #if defined(DART_HOST_OS_ANDROID), 51행 const char* android_cacerts = "/system/etc/security/cacerts";, 52행 LoadRootCertCache(android_cacerts);, 54행 #else 아래로 Linux용 kCertFiles 목록](/assets/img/android-mastery/p1c23/06-dart-android-cacerts-source.png)

사용자가 설정 앱으로 설치한 Burp CA는 `/data/misc/user/0/cacerts-added` 쪽에 들어가니 Dart는 보지 않는다. 앱이 NSC의 `<trust-anchors>` 로 사용자 CA를 믿겠다고 선언해도 그건 자바 쪽 `TrustManager` 설정이라 Dart에는 닿지 않는다. 같은 파일의 현재 main 브랜치도 이 경로 하나만 읽고 `apex` 라는 문자열은 없다. Android 14부터 루트 인증서는 업데이트 가능한 Conscrypt APEX의 `/apex/com.android.conscrypt/cacerts` 에서도 제공되는데, Dart가 그 디렉터리를 보지 않는다는 것은 소스로만 확인했고 API 34 이상 기기에서 재 보지는 않았다.

### NSC의 평문 차단도 Dart에는 걸리지 않는다

세 앱의 매니페스트를 `aapt` 로 덤프해 보면 셋 다 targetSdk 36이고 `networkSecurityConfig` 속성은 하나도 없다. Flutter 매니페스트에는 `usesCleartextTraffic` 이 아예 없고, RN은 릴리스 빌드라 `0x0`(false), Cordova는 `config.xml` 에서 켜 둔 대로 `0xffffffff`(true)다.

![aapt dump badging 결과 세 APK 모두 targetSdkVersion:'36'. 세 매니페스트의 grep -c networkSecurityConfig는 모두 0. Flutter의 grep -c usesCleartextTraffic는 0, RN은 usesCleartextTraffic(0x010104ec)=(type 0x12)0x0, Cordova는 0xffffffff](/assets/img/android-mastery/p1c23/04-host-network-config.png)

AOSP의 NSC 기본값은 [`NetworkSecurityConfig.java` 181~197행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/security/net/config/NetworkSecurityConfig.java#181)에서 정해진다. targetSdk가 P(28) 미만일 때만 평문을 허용하고, 사용자 인증서 저장소는 M(23) 이하에서만 신뢰 목록에 넣는다. 그러니 Flutter와 RN 앱 모두 NSC 기준으로는 평문 HTTP가 금지된 상태다. RN의 `fetch` 는 밑에서 OkHttp를 쓰고 OkHttp는 이 정책을 묻기 때문에 평문 요청이 막힐 것이다. Dart 3.13.5의 `http_impl.dart` 에는 이 정책을 확인하는 코드가 없다. [Dart 2.13.0](https://github.com/dart-lang/sdk/blob/2.13.0/sdk/lib/_http/http_impl.dart#L2644)까지는 `isInsecureConnectionAllowed` 로 확인하고 `Insecure HTTP is not allowed by platform` 예외를 던졌는데, 2.14.0에서 `network_policy.dart` 와 함께 빠졌다. 같은 매니페스트 조건에서 Flutter 앱의 http 요청은 통과하고 RN 앱은 실패할 거라고 보지만, 에뮬레이터에서 두 버튼을 눌러 결과를 확인하는 것까지는 하지 못했다.

## reFlutter가 실제로 바꾸는 것

[reFlutter](https://github.com/Impact-I/reFlutter) 0.9.8은 APK의 스냅샷 해시로 Flutter 엔진 버전을 알아내고, BoringSSL 인증서 체인 검증을 무조건 성공시키도록 패치한 `libflutter.so` 로 바꿔 끼운다. 이번 APK에는 `reflutter xplat-flutter.apk -n` 을 돌린 뒤, 결과물 `release.RE.apk` 를 정렬하고 원본과 같은 디버그 키로 다시 서명했다.

![zipalign -p -f 4 reflutter/release.RE.apk와 apksigner sign으로 다시 서명한 resigned.apk의 sha256과 xplat-flutter-reflutter.apk의 sha256이 6cc2c1d6...a58d로 같음. 두 APK의 Signer #1 certificate SHA-256이 766e4a4ce2ecb9bf...feb1로 같음. lib/x86_64/libflutter.so는 13051424에서 13048376바이트로 변함. 항목별 해시 비교에서 arm64-v8a, armeabi-v7a, x86_64의 libflutter.so만 DIFF이고 libapp.so는 모두 same](/assets/img/android-mastery/p1c23/05-reflutter-diff.png)

항목별 해시를 비교하니 세 ABI의 `libflutter.so` 만 달라졌고 `libapp.so` 는 전부 그대로였다. 앱 로직은 손대지 않고 엔진의 TLS 검증만 바꾼다는 뜻이다. 서명 인증서가 같으니 원본 위에 `adb install -r` 로 덮어 설치할 수 있다. 캡처의 `--ks-pass pass:android` 는 Android SDK 디버그 키스토어의 공개 기본 비밀번호다.

예전 설명처럼 reFlutter만 돌리면 Burp에 트래픽이 뜨는 시절은 지났다. reFlutter README의 "Proxy routing by era" 항목에 따르면 Flutter 3.24.x 엔진까지는 엔진 안에 하드코딩된 프록시 IP를 넣어 줬지만 3.27부터는 그게 없고 기기 쪽에서 프록시 경로를 따로 잡아야 한다. 프록시 경로와 인증서 신뢰 중 reFlutter가 고치는 건 신뢰 쪽뿐이다. 패치된 x86_64 3.47.7 엔진이 에뮬레이터에서 mitmproxy 인증서를 받아들이고 헤더가 복호화되는지는 이번에 측정하지 못했다.

## Cordova 브리지를 여는 건 allow-navigation

Cordova 앱은 `assets/www` 의 웹앱을 시스템 WebView에 띄운 것이고, [20장](/posts/android-lab-p1c20-deeplink-applink-webview/)에서 본 WebView 공격면이 그대로 적용된다. 차이는 JS와 네이티브 플러그인을 잇는 Cordova 브리지에 있다. cordova-android 15.1.0은 [`SystemWebViewEngine.java` 247행](https://github.com/apache/cordova-android/blob/rel/15.1.0/framework/src/org/apache/cordova/engine/SystemWebViewEngine.java#L247)에서 `_cordovaNative` 를 `addJavascriptInterface` 로 노출한다. 이 객체는 iframe을 포함한 모든 프레임에서 보인다. 대신 호출할 때마다 브리지 비밀값을 요구하고, 그 값은 `gap_init` 프롬프트를 통해서만 받는다.

![GitHub apache/cordova-android rel/15.1.0 CordovaBridge.java. promptOnJsPrompt(String origin, ...) 안 169~182행이 강조됨: defaultValue가 "gap_init:"으로 시작하면 if (pluginManager.shouldAllowBridgeAccess(origin))일 때 setBridgeMode 후 generateBridgeSecret()을 반환하고, 아니면 LOG.e(LOG_TAG, "gap_init called from restricted origin: " + origin) 후 빈 문자열 반환](/assets/img/android-mastery/p1c23/07-cordova-bridge-gap-init-source.png)

[`CordovaBridge.java` 169~182행](https://github.com/apache/cordova-android/blob/rel/15.1.0/framework/src/org/apache/cordova/CordovaBridge.java#L169)은 프롬프트를 띄운 프레임의 origin으로 `shouldAllowBridgeAccess` 를 묻는다. 플러그인 기본 구현인 [`CordovaPlugin.java` 275~277행](https://github.com/apache/cordova-android/blob/rel/15.1.0/framework/src/org/apache/cordova/CordovaPlugin.java#L275)은 `return shouldAllowNavigation(url);` 이고, [`AllowListPlugin.java` 117~121행](https://github.com/apache/cordova-android/blob/rel/15.1.0/framework/src/org/apache/cordova/AllowListPlugin.java#L117)의 `shouldAllowNavigation` 은 `<allow-navigation>` 목록만 본다. `<access>` 목록은 같은 파일 [124~128행](https://github.com/apache/cordova-android/blob/rel/15.1.0/framework/src/org/apache/cordova/AllowListPlugin.java#L124)의 `shouldAllowRequest` 에서 리소스 요청을 허용하는 데만 쓰인다. 어떤 플러그인도 답하지 않으면 [`PluginManager.java` 479행](https://github.com/apache/cordova-android/blob/rel/15.1.0/framework/src/org/apache/cordova/PluginManager.java#L479)이 시작 URL 접두사와 비교한다.

데모 앱의 `config.xml` 에는 일부러 둘을 나눠 넣었다. `config.xml` 을 덤프하면 `http://10.0.2.2:8788/*` 은 14행 `<allow-navigation>` 에, `http://10.0.2.2:8789/*` 은 15행 `<access>` 에 들어가 있다.

![aapt dump xmltree xplat-cordova.apk res/xml/config.xml 을 grep -A1 으로 allow-navigation과 access 요소만 거른 결과. E: :allow-navigation (line=14) 아래 A: href="http://10.0.2.2:8788/*", E: :access (line=15) 아래 A: origin="http://10.0.2.2:8789/*"](/assets/img/android-mastery/p1c23/09-cordova-config-allownav-access.png)
 소스대로라면 8788에서 온 iframe은 브리지 비밀값을 받아 `deviceready` 까지 가고, 8789 iframe은 페이지는 뜨되 `gap_init called from restricted origin` 로그와 함께 브리지가 거절된다. 두 iframe을 띄워 logcat으로 확인하는 실험은 이번에 돌리지 못했다.

분석하는 쪽에서 이 구분이 중요한 이유는 `<allow-navigation href="*">` 나 넓은 와일드카드가 들어간 앱이 흔해서다. 그런 앱에서는 WebView에 들어온 외부 페이지나 광고 iframe이 Cordova 플러그인(파일, 연락처, 카메라 등)을 부를 수 있다. 진단할 때는 `res/xml/config.xml` 의 `<allow-navigation>` 항목부터 본다.

## 개발과 점검에서 할 일

키를 심은 Flutter와 RN 앱에서는 상수가 APK 안에 평문으로 남았다. Flutter는 `libapp.so` 에, RN은 Hermes 문자열 테이블에 있다. Cordova는 키를 심지 않았지만 `assets/www/js/index.js` 가 미니파이도 안 된 875바이트 원본 그대로 들어가 있으니, 거기 넣은 상수도 그대로 읽힐 것이다. 난독화 옵션(`--obfuscate`, JS 미니파이)은 식별자 이름만 바꾸고 문자열 리터럴은 그대로 두니, API 키 같은 비밀은 서버로 옮기는 것 말고는 답이 없다. 회귀 점검은 빌드 산출물을 대상으로 위 캡처에서 쓴 `grep -a` 를 CI에 걸어 두는 정도로 충분하다. RN은 바이트코드여도 문자열 테이블이 평문이라 `grep -a -c` 가 그대로 통한다.

Flutter 앱의 인증서 고정은 자바 쪽 NSC `<pin-set>` 으로는 걸리지 않는다. `dart:io` 의 `SecurityContext` 에 허용할 인증서만 넣고 `withTrustedRoots: false` 로 만들거나, `badCertificateCallback` 을 열어 두지 않았는지 코드에서 확인해야 한다. 거꾸로 점검할 때는 reFlutter 같은 엔진 교체가 이 고정까지 함께 무력화하니, 트래픽 경로만 VPN 방식으로 따로 잡으면 된다.

Cordova 앱은 `<allow-navigation>` 을 앱이 실제로 이동해야 하는 오리진으로 좁히고, 외부 리소스는 `<access>` 로만 허용한다. 점검은 `aapt dump xmltree app.apk res/xml/config.xml | grep -A1 -E 'E: :(allow-navigation|access) '` 한 줄로 시작할 수 있다. 평문 허용(`usesCleartextTraffic=0xffffffff`)이 같이 켜져 있으면 네트워크 공격자가 페이지를 바꿔치기해 브리지까지 닿는 경로가 생기니 함께 본다.
