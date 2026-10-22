---
layout: post
title: "Network Security Config 분석 — 정적으로 만든 호스트 표를 기기에서 맞춰 보기"
date: 2026-10-27 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, NetworkSecurityConfig, CertificatePinning, Cleartext, Cronet, OkHttp]
excerpt: "APK에서 꺼낸 NSC를 상속까지 풀어 호스트별 표로 만들고, Android 13 에뮬레이터에서 HttpURLConnection, OkHttp, Cronet으로 맞춰 봤다. 핀셋이 만료되면 핀 검사만 꺼지고 앵커 검사는 남았으며, 앱이 직접 만든 TrustManager와 raw 소켓은 NSC를 거치지 않았다."
---

[지난 글](/posts/android-lab-p1c11-burp-mitmproxy-intercept/)에서는 프록시 CA를 유저 저장소와 시스템 저장소에 차례로 넣으면서 어느 앱이 어디서 끊기는지 기기에서 확인했다. 끊긴 자리마다 이유는 앱에 들어 있는 Network Security Config(NSC) 한 장에 적혀 있었다. 이번에는 순서를 뒤집는다. APK에서 NSC를 꺼내 호스트마다 평문 허용, 신뢰 앵커, 핀이 실제로 어떻게 정해지는지 표로 만들고, 그 표가 기기에서 맞는지 같은 앱으로 검증한다.

돌려 보기 전에는 debug-overrides가 핀까지 끄고, NSC가 없으면 시스템 CA만 믿는다고 알고 있었다. 둘 다 조건이 붙어야 맞는 말이었다. 지난 글에서 Cronet도 NSC의 앵커를 따른다는 것까지는 봤는데, 이번에는 평문 차단과 핀 실패에서도 다른 스택과 같은 답을 내는지 함께 확인했다.

기기는 Android 13(API 33, `TE1A.240213.009`, 2024-03-01 보안 패치) x86_64 google_apis userdebug 에뮬레이터이고 SELinux는 Enforcing이다. 호스트 도구는 apktool 3.0.2, aapt2 2.20, Python 3.11, OpenSSL 3.5.5를 썼다. 플랫폼 소스는 frameworks/base의 `android-13.0.0_r84` 태그에서 봤다. `android-13.0.0_r1`, `r83`, `r84` 태그를 비교해 보니 NSC 클래스가 같았다. 실험 앱에 넣은 Cronet은 `org.chromium.net:cronet-embedded:143.7445.0`(Chromium 143.0.7445.0)이고, Chromium 쪽 소스는 앱에 넣은 것과 같은 143.0.7445.0 태그에서 확인했다. TLS 신뢰 체인과 NSC 개념은 [C46](/posts/android-concept-atlas-c46-tls-nsc-pinning/)에, APK를 푸는 방법은 [apktool 글](/posts/android-lab-p1c05-apktool-smali/)에 있다.

## 파일 이름은 매니페스트 속성이 정한다

NSC는 매니페스트 `<application>`의 `android:networkSecurityConfig`가 가리키는 XML 리소스다(API 24에서 [추가](https://developer.android.com/reference/android/R.attr#networkSecurityConfig)). 흔히 `res/xml/network_security_config.xml`이라고 부르지만 이름은 앱이 정하기 나름이라, 분석은 경로를 짐작하지 말고 속성에서 출발해야 한다. 교육용 취약 앱 AndroGoat부터 풀어 봤다.

![p1c12 폴더 터미널. apktool d -f -s -p fw androgoat.apk -o androgoat 가 Using Apktool 3.0.2 와 Loading resource table from file: fw\1.apk 를 찍고, grep 결과 android:debuggable="true" 와 android:networkSecurityConfig="@xml/network_security_config", apktool.yml 의 targetSdkVersion: 33. cat 한 network_security_config.xml 에는 base-config cleartextTrafficPermitted="true" 아래 certificates src="system" 과 src="user", domain-config 에 includeSubdomains="true" 인 cve.org 와 pin-set expiration="2050-01-01", SHA-256 핀 p4si93w2..., DxH4tt40..., ++MBgDH5... 세 개](/assets/img/android-mastery/p1c12/01-androgoat-nsc.png)

`-p fw`는 apktool이 프레임워크 리소스(`1.apk`)를 현재 폴더의 `fw`에 두게 하는 옵션이다. 화면에 로컬 경로가 찍히지 않게 하려고 붙였다. `-s`는 dex를 smali로 풀지 않아서 빠르다.

AndroGoat의 NSC는 짧지만 읽을 거리가 많다. `base-config`가 평문 HTTP를 허용하고 유저 CA까지 믿는다. `cve.org`와 그 하위 도메인에는 핀이 세 개 걸려 있고 2050년까지 유효하다. 그 `domain-config`에는 `trust-anchors`가 없는데, 이 경우 앵커는 `base-config`에서 물려받는다. 그러니 `cve.org`도 유저 CA로 끝나는 체인을 앵커 단계에서는 받아들이고, 프록시 CA를 유저 저장소에 넣은 사람은 핀 단계에서야 막힌다.

릴리스 빌드에서는 파일 이름이 더 흐려진다. 같은 NSC(`@xml/nsc`)를 넣어 디버그와 릴리스로 빌드한 자작 앱 두 벌을 비교했다.

![p1c12 폴더 터미널. unzip -l nsc-lab-debug.apk 에서 4360 res/xml/nsc.xml, unzip -l nsc-lab-release.apk 의 grep -c 'res/xml/' 결과 0. aapt2 dump xmltree 로 본 릴리스 매니페스트의 networkSecurityConfig(0x01010527)=@0x7f0c0000, aapt2 dump resources 에서 resource 0x7f0c0000 xml/nsc 가 (file) res/jz.xml type=XML, aapt2 dump xmltree --file res/jz.xml 에 base-config, cleartextTrafficPermitted=false, src="system". apktool d 로 풀면 nsc-lab-release/res/xml 아래 nsc.xml](/assets/img/android-mastery/p1c12/02-release-resname.png)

릴리스 APK에는 `res/xml/`가 하나도 없다. AGP가 릴리스 빌드에서 리소스 경로를 줄여 NSC를 `res/jz.xml`로 넣었기 때문이다. zip을 `grep`해서 NSC를 찾는 스크립트는 여기서 "NSC 없음"이라고 잘못 판정한다. 매니페스트의 리소스 ID(`0x7f0c0000`)를 리소스 테이블에서 찾아가면 `xml/nsc`가 나오고 그 파일이 `res/jz.xml`이다. apktool은 이 과정을 대신 해서 원래 이름 `res/xml/nsc.xml`로 복원한다. 기기 쪽에서도 같은 이름을 쓴다. 릴리스 빌드를 띄우면 logcat에 `Using Network Security Config from resource nsc debugBuild: false`가 찍히고, NSC가 없는 앱은 `No Network Security Config specified, using platform default`를 남긴다. APK를 풀기 전에 어떤 설정이 적용됐는지 빨리 보고 싶을 때 이 `NetworkSecurityConfig` 태그 한 줄이 쓸 만하다.

## 상속과 기본값을 풀어 호스트별 표로 만들기

NSC를 눈으로 읽을 때 놓치기 쉬운 것은 "적혀 있지 않은 값"이다. 플랫폼은 호스트 이름으로 설정 하나를 고르고([ApplicationConfig.java 70~113행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/ApplicationConfig.java#70): 정확히 일치하는 `domain`이 먼저, 없으면 `includeSubdomains`로 가장 길게 일치하는 것, 그것도 없으면 `base-config`), 그 설정에 없는 값은 부모에게서 가져온다. 중첩된 `domain-config`의 부모는 바깥 `domain-config`, 최상위 `domain-config`의 부모는 `base-config`, `base-config`의 부모는 플랫폼 기본값이다. 핀셋도 물려받는다. 부모에 핀이 있고 자식에 `<pin-set>`이 없으면 자식도 그 핀으로 검사된다.

플랫폼 기본값은 기기 버전이 아니라 앱의 targetSdkVersion이 정한다. [NetworkSecurityConfig.java 187행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/NetworkSecurityConfig.java#187)은 `targetSdkVersion < P`(28 미만)일 때만 평문을 허용하고, [192행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/NetworkSecurityConfig.java#192)은 `targetSdkVersion <= M`(23 이하)일 때만 유저 저장소를 앵커에 더한다. NSC가 아예 없는 앱은 매니페스트의 `android:usesCleartextTraffic`이 평문 여부를 정하고([ManifestConfigSource.java 58~80행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/ManifestConfigSource.java#58)), NSC가 있으면 그 매니페스트 플래그는 무시된다.

이 규칙대로 상속을 따라가 호스트별 실효값을 찍는 스크립트 [`nsc_triage.py`](/assets/code/android-mastery/p1c12/nsc_triage.py)를 표준 라이브러리만으로 150줄쯤 짜서 호스트에서 돌렸다. apktool로 푼 폴더에서 매니페스트와 NSC를 읽고, `debuggable`일 때만 `debug-overrides` 앵커를 덧붙이고, 핀셋 만료일을 오늘 날짜와 비교한다. NSC만 보면 놓치는 것도 있어서 dex의 클래스·메서드·문자열 테이블도 훑는다. `X509TrustManager`나 `HostnameVerifier`를 직접 구현한 클래스(okhttp3·okhttp2·Volley·Cronet 같은 묶인 네트워크 스택 내부는 제외), OkHttp `CertificatePinner` 형식의 `sha256/...` 문자열, `onReceivedSslError`를 가진 WebView 클라이언트 클래스, 묶여 들어간 네트워크 스택과 네이티브 TLS 라이브러리를 찾아 함께 출력한다. 교육용 앱 네 개에 먼저 돌렸다.

![p1c12 폴더 터미널. allsafe, insecureshop, pivaa 를 apktool 로 푼 뒤 python nsc_triage.py androgoat.apk allsafe.apk insecureshop.apk pivaa.apk, today = 2026-10-15. androgoat 은 targetSdk=33, base-config true / system, user, cve.org/* 는 true* / system, user / 3 pins, until 2050-01-01, stacks: okhttp3, pins in code 3. allsafe 는 targetSdk=35, (platform default) false / system, infosecadventures.io/* true / system, pins in code 1. insecureshop 은 targetSdk=29, networkSecurityConfig=- usesCleartextTraffic=true, (platform default) true / system, WebView onReceivedSslError overridden: com.insecureshop.util.CustomWebViewClient. pivaa 는 targetSdk=26, networkSecurityConfig=-, (platform default) true / system, own trust code: com.htbridge.pivaa.handlers.API$1, API$2](/assets/img/android-mastery/p1c12/03-triage-edu.png)

`*`는 cleartext 칸에서 상속받은 값을 표시한다. 앵커 칸에는 표시가 없어서, AndroGoat의 `cve.org/*` 줄은 cleartext `true*`뿐 아니라 앵커 `system, user`도 `base-config`에서 내려온 값이다. Allsafe는 targetSdk 35에 `base-config`가 없어서 첫 줄이 플랫폼 기본값(`false`, `system`)이 된다. InsecureShop은 NSC가 없고 targetSdk 29지만 `usesCleartextTraffic=true` 때문에 평문이 열려 있다. PIVAA는 targetSdk 26이라 기본값만으로도 평문이 열린다.

표 아래 줄들이 NSC가 말해 주지 않는 부분이다. smali로 따로 확인해 보니 AndroGoat은 NSC에 없는 `owasp.org`에 OkHttp `CertificatePinner`로 핀 세 개를 코드에서 걸고 있었다. Allsafe의 코드 핀은 일부러 넣은 가짜 값 `sha256/AAAA...A=`다. InsecureShop의 `CustomWebViewClient.onReceivedSslError`는 `SslErrorHandler.proceed()`를 불러 WebView의 인증서 오류를 그냥 넘긴다. PIVAA의 `API$2`는 `checkServerTrusted`가 빈 TrustManager이고 `API$1`은 `verify()`가 무조건 true인 HostnameVerifier인데, 이 둘을 `HttpsURLConnection.setDefaultSSLSocketFactory`로 전역에 설치한다. 이런 코드가 있으면 NSC 표가 아무리 깔끔해도 해당 경로의 TLS 검증은 NSC가 정하지 않는다. 이 앱들은 실제 인터넷 호스트와 통신하므로 실행은 하지 않았고, 여기까지는 정적 분석 결과다.

스크립트에도 사각이 있다. 앱이 자기 CA만 담은 KeyStore로 `TrustManagerFactory.init(ks)`를 부르는 패턴은 잡지 못한다. OkHttp 자신도 `TrustManagerFactory.init`을 부르기 때문에 호출 여부만으로는 가릴 수 없었다.

## 실험용 NSC와 정적 예측

기기에서 맞춰 보려면 결과를 아는 서버가 필요하다. 호스트에 직접 만든 루트 CA를 세 개 두고, 각각으로 서명한 리프를 서로 다른 포트에서 내미는 작은 서버(`labserver.py`)를 띄웠다. `lab_ca` 체인은 18121, 가로채기 프록시 역할을 하는 `proxy_ca` 체인은 18122, 디버그 전용 `debug_ca` 체인은 18123이고 평문 HTTP는 18120이다. 리프의 SAN에는 `localhost`, `*.seika.test`, `10.0.2.2`, `127.0.0.1`을 넣었다. 에뮬레이터에서 같은 서버를 `10.0.2.2`(에뮬레이터 NAT)로도, `adb reverse`를 건 `127.0.0.1`과 `localhost`로도 부를 수 있어서 호스트 이름만 바꿔 다른 `domain-config`를 고르게 했다. 이 디버그 빌드에서 apktool로 복원한 NSC가 아래다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain>10.0.2.2</domain>
        <trust-anchors>
            <certificates src="@raw/lab_ca" />
        </trust-anchors>
        <pin-set expiration="2030-01-01">
            <pin digest="SHA-256">ddZbbmEpNqnjTaCgAFCvhvnaG2AyX5I1Gf2cI2WUges=</pin>
            <pin digest="SHA-256">thGiBSz9zrllFsC+ZLYWFiJ7CROCrXoRChHYfZqYpEU=</pin>
        </pin-set>
    </domain-config>
    <domain-config>
        <domain>127.0.0.1</domain>
        <trust-anchors>
            <certificates src="@raw/lab_ca" />
        </trust-anchors>
        <pin-set>
            <pin digest="SHA-256">HvjQsjcQ8+dqELUZ+5ZzyPd/zSmDHVy4ZE8VE8W/IYA=</pin>
        </pin-set>
    </domain-config>
    <domain-config>
        <domain>localhost</domain>
        <trust-anchors>
            <certificates src="@raw/lab_ca" />
        </trust-anchors>
        <pin-set expiration="2025-01-01">
            <pin digest="SHA-256">HvjQsjcQ8+dqELUZ+5ZzyPd/zSmDHVy4ZE8VE8W/IYA=</pin>
        </pin-set>
    </domain-config>
    <domain-config>
        <domain includeSubdomains="true">seika.test</domain>
        <trust-anchors>
            <certificates src="@raw/lab_ca" />
        </trust-anchors>
        <domain-config>
            <domain>pinned.seika.test</domain>
            <pin-set>
                <pin digest="SHA-256">HvjQsjcQ8+dqELUZ+5ZzyPd/zSmDHVy4ZE8VE8W/IYA=</pin>
            </pin-set>
        </domain-config>
        <domain-config>
            <domain>user.seika.test</domain>
            <trust-anchors>
                <certificates src="system" />
                <certificates src="user" />
            </trust-anchors>
            <pin-set>
                <pin digest="SHA-256">HvjQsjcQ8+dqELUZ+5ZzyPd/zSmDHVy4ZE8VE8W/IYA=</pin>
            </pin-set>
        </domain-config>
        <domain-config>
            <domain>override.seika.test</domain>
            <trust-anchors>
                <certificates overridePins="true" src="user" />
            </trust-anchors>
            <pin-set>
                <pin digest="SHA-256">HvjQsjcQ8+dqELUZ+5ZzyPd/zSmDHVy4ZE8VE8W/IYA=</pin>
            </pin-set>
        </domain-config>
    </domain-config>
    <debug-overrides cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="@raw/debug_ca" />
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```

`10.0.2.2`의 핀 두 개는 `lab_ca`의 공개키 해시와 백업용 리프 공개키 해시다. 나머지 호스트에 박은 `HvjQsjcQ...`는 어느 서버도 쓰지 않는 키(`retired.key`)의 해시라서 일부러 틀린 핀이다. `127.0.0.1`과 `localhost`는 앵커도 핀도 같고 차이는 `localhost` 핀셋이 2025-01-01에 만료됐다는 것 하나다. `debug-overrides`에는 `cleartextTrafficPermitted="true"`도 적어 두었다. 이 값이 어떻게 되는지도 보려고 넣은 것이다.

같은 NSC로 네 가지 APK를 빌드했다. 디버그 빌드(`io.seika.nsc`, debuggable), 릴리스 빌드(`io.seika.nsc.rel`, 리소스 경로가 `res/jz.xml`로 줄어든 그 APK), NSC를 뺀 targetSdk 33 빌드(`io.seika.nsc.plain`), NSC를 뺀 targetSdk 23 빌드(`io.seika.nsc.legacy`)다. 두 NSC 빌드를 먼저 스크립트로 읽어 기기에서 무엇이 나올지 예측해 두었다.

![p1c12 폴더 터미널. python nsc_triage.py nsc-lab-debug.apk nsc-lab-release.apk, today = 2026-10-15. nsc-lab-debug(targetSdk=33 debuggable=true networkSecurityConfig=@xml/nsc) 표에서 base-config false / system, @raw/debug_ca+, 10.0.2.2 true / @raw/lab_ca, @raw/debug_ca+ / 2 pins, until 2030-01-01, 127.0.0.1 false* / 1 pin, no expiration, localhost false* / 1 pin, expired 2025-01-01 -> NOT checked, user.seika.test false* / system, user, @raw/debug_ca+, override.seika.test false* / user+, @raw/debug_ca+, debug-overrides: applied, its cleartextTrafficPermitted is never used, stacks: cronet, okhttp3, libcronet.143.0.7445.0.so. nsc-lab-release 는 같은 줄에서 @raw/debug_ca+ 만 빠지고 debug-overrides: ignored (not debuggable)](/assets/img/android-mastery/p1c12/04-triage-lab.png)

디버그 빌드에서는 자기 `trust-anchors`가 있는 설정마다 `@raw/debug_ca+`가 붙는다(`+`는 `overridePins`). `debug-overrides` 줄은 "적용되지만 거기 적힌 cleartext 값은 쓰이지 않는다"고 말한다. 이 두 줄은 플랫폼 소스를 읽고 스크립트에 넣은 판단이라 기기에서 확인할 대상이었다.

## 네트워크 없이 TrustManager에 물어보기

예측을 확인하는 앱은 `ProbeActivity` 하나짜리다. 먼저 플랫폼 기본 TrustManager를 만들어 세 체인을 호스트 이름과 함께 넘기고 결과를 찍는다. 앱에서 `TrustManagerFactory.init(null)`로 얻는 기본 TrustManager는 NSC의 `RootTrustManager`이고, 호스트 이름이 있어야 `domain-config`를 고를 수 있다. 그래서 세 인자 버전 `checkServerTrusted(chain, authType, host)`를 부르는 `X509TrustManagerExtensions`를 썼다. 네트워크 연결은 하나도 없이 신뢰 판단만 보는 실험이다. `ProbeActivity.java`의 125~161행을 그대로 옮긴다.

```java
    // The platform default TrustManager is NSC's RootTrustManager; the host picks the domain-config.
    private void trustMatrix() throws Exception {
        X509TrustManager platform = defaultTrustManager(null);
        X509TrustManagerExtensions ext = new X509TrustManagerExtensions(platform);
        X509Certificate[][] chains = new X509Certificate[CHAINS.length][];
        for (int i = 0; i < CHAINS.length; i++) chains[i] = chain(CHAINS[i]);

        out("-- trust (platform TrustManager, chain x host, no network)");
        out(String.format("%-20s %-10s %-10s %s", "host", "lab", "debug", "proxy"));
        for (String host : TRUST_HOSTS) {
            String[] r = new String[CHAINS.length];
            for (int i = 0; i < CHAINS.length; i++) {
                try {
                    ext.checkServerTrusted(chains[i], "RSA", host);
                    r[i] = "ok";
                } catch (Exception e) {
                    r[i] = verdict(e);
                    Log.i(TAG, "  detail " + host + " " + CHAINS[i] + ": " + e);
                }
            }
            out(String.format("%-20s %-10s %-10s %s", host, r[0], r[1], r[2]));
        }
        try {
            platform.checkServerTrusted(chains[0], "RSA");   // hostname-unaware call
            out("2-arg checkServerTrusted(lab): ok");
        } catch (Exception e) {
            out("2-arg checkServerTrusted(lab): " + verdict(e));
            Log.i(TAG, "  detail 2-arg: " + e);
        }
        X509TrustManager own = ownTrustManager();
        try {
            new X509TrustManagerExtensions(own).checkServerTrusted(chains[0], "RSA", "pinned.seika.test");
            out("own TrustManager(lab CA) pinned.seika.test lab: ok");
        } catch (Exception e) {
            out("own TrustManager(lab CA) pinned.seika.test lab: " + verdict(e));
        }
    }
```

`verdict()`는 예외 메시지를 줄여 표에 넣는다. `Pin verification failed`면 `PIN-FAIL`, `Trust anchor for certification path not found`면 `NO-ANCHOR`, `Domain specific configurations require that hostname aware ...`면 `NEEDS-HOSTNAME`이다. 마지막의 `ownTrustManager()`는 앱이 "자기 CA를 코드로 추가할 때" 흔히 쓰는 방식 그대로, `lab_ca` 하나만 든 KeyStore로 `TrustManagerFactory.init(ks)`를 부른다.

유저 저장소 앵커를 시험하려면 프록시 CA가 실제로 유저 저장소에 있어야 한다. 설정 앱을 거치지 않고 root 셸로 `/data/misc/user/0/cacerts-added`에 넣었다. 파일 이름은 OpenSSL의 `subject_hash_old` 값에 `.0`을 붙인 것이다.

![p1c12 폴더 터미널. openssl x509 -in certs/proxy-ca.pem -noout -subject -subject_hash_old 가 subject=O=SeiKa Lab, CN=SeiKa Proxy Root CA 와 6042c89d, adb -s $S push certs/6042c89d.0 /data/local/tmp/ 가 857 bytes, adb shell 에서 /data/misc/user/0/cacerts-added 를 만들고 복사, chown -R system:system, chmod 755 와 644, restorecon 후 ls -laZ 가 SELinux: Loaded file_contexts 와 -rw-r--r-- 1 system system u:object_r:misc_user_data_file:s0 857 2026-10-15 11:54 6042c89d.0](/assets/img/android-mastery/p1c12/05-user-ca.png)

위 캡처의 `$S`는 에뮬레이터 시리얼을 담은 셸 변수다. 네 앱 모두 `AndroidCAStore`의 `user:` 별칭으로 이 인증서를 보았다(`user CA user:6042c89d.0 CN=SeiKa Proxy Root CA,O=SeiKa Lab`). 그다음 디버그 빌드와 릴리스 빌드를 차례로 띄워 신뢰 표를 받았다.

![p1c12 폴더 터미널. io.seika.nsc 를 am force-stop, logcat -c, am start -W 로 띄우고 Status: ok, DONE 을 기다린 뒤 NSCLAB 로그를 출력. io.seika.nsc lab/debug targetSdk=33 debuggable=true, user CA user:6042c89d.0 CN=SeiKa Proxy Root CA,O=SeiKa Lab, cleartext 줄 10.0.2.2=true 127.0.0.1=false localhost=false api.seika.test=false. 디버그 표 host/lab/debug/proxy: api.seika.test ok ok NO-ANCHOR, pinned.seika.test PIN-FAIL ok NO-ANCHOR, user.seika.test NO-ANCHOR ok PIN-FAIL, override.seika.test NO-ANCHOR ok ok, other.example NO-ANCHOR ok NO-ANCHOR, 10.0.2.2 ok ok NO-ANCHOR, 127.0.0.1 PIN-FAIL ok NO-ANCHOR, localhost ok ok NO-ANCHOR, 2-arg checkServerTrusted(lab): NEEDS-HOSTNAME, own TrustManager(lab CA) pinned.seika.test lab: ok. 이어서 io.seika.nsc.rel 의 표는 debug 열이 모두 NO-ANCHOR 이고 나머지 칸은 같음, 2-arg NEEDS-HOSTNAME, own TrustManager ok](/assets/img/android-mastery/p1c12/06-trust-debug-release.png)

모든 칸이 스크립트 예측과 같았다.

`127.0.0.1`과 `localhost`는 앵커도 같고 틀린 핀도 같은데 `lab` 열이 `PIN-FAIL`과 `ok`로 갈렸다. 차이는 만료일 하나다. `proxy` 열은 두 호스트 모두 `NO-ANCHOR`다. 핀셋이 만료돼도 프록시 CA가 들어오지는 못했다. 루프백은 버전에 따라 기본값도 바뀐다. [공식 문서](https://developer.android.com/privacy-and-security/security-config)에 따르면 API 37부터는 `localhost`와 루프백 주소에 대한 설정이 없을 때 평문을 허용하고 핀이 없는 암묵적 설정이 들어가는데(CT 기본 적용도 이때부터다), API 37 이미지가 없어 측정하지 못했다. 이 실험처럼 `localhost`와 `127.0.0.1`을 명시한 설정은 그대로 이긴다.

`user.seika.test`와 `override.seika.test`는 둘 다 유저 저장소를 앵커로 두고 틀린 핀을 걸었다. 그런데 프록시 체인은 앞에서 `PIN-FAIL`, 뒤에서 `ok`였다. `src="user"`만으로는 유저 CA로 끝나는 체인이 앵커 검사를 통과하고, 그 뒤에 핀 검사가 남는다. 핀까지 건너뛰게 하는 것은 `overridePins="true"`다.

`debug` 열은 디버그 빌드에서 모든 호스트가 `ok`였고 릴리스 빌드에서는 모두 `NO-ANCHOR`였다. `pinned.seika.test`와 `127.0.0.1`처럼 틀린 핀이 걸린 호스트도 디버그 체인은 통과했다. 반면 같은 디버그 빌드에서도 `lab` 체인은 그 두 호스트에서 여전히 `PIN-FAIL`이었다.

두 인자 `checkServerTrusted`는 `NEEDS-HOSTNAME`으로 실패했다. [RootTrustManager.java 110~119행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/RootTrustManager.java#110)은 `domain-config`가 하나라도 있으면 호스트 없는 호출을 예외로 끊는다. 기본 TrustManager를 감싸서 직접 검증하던 앱 코드가 NSC에 `domain-config`를 추가하는 순간 깨지는 경로다. NSC가 없는 plain, legacy 빌드에서는 같은 호출이 `NO-ANCHOR`로 끝났다. 앵커 검사까지 진행했다는 뜻이다.

마지막 줄의 `own TrustManager(lab CA) pinned.seika.test lab: ok`가 NSC 밖으로 나가는 경로다. 기본 TrustManager는 같은 호스트, 같은 체인을 `PIN-FAIL`로 거절했다. 앱이 KeyStore를 넘겨 `TrustManagerFactory.init(ks)`를 부르면 [RootTrustManagerFactorySpi.java 52~56행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/RootTrustManagerFactorySpi.java#52)이 그 KeyStore만으로 `KeyStoreConfigSource`를 만든다. 그 설정에는 핀셋이 없으니 NSC에 적힌 핀은 이 TrustManager와 무관하다.

## 만료된 핀셋은 핀 검사만 끈다

핀 검사는 [NetworkSecurityTrustManager.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/NetworkSecurityTrustManager.java#118)의 `checkPins`가 한다.

![android.googlesource.com 의 NetworkSecurityTrustManager.java(android-13.0.0_r84) 112~151행. 113행 trustedChain = mDelegate.checkServerTrusted(certs, authType, host), 114행 checkPins(trustedChain). 강조된 118행 private void checkPins 에서 pinSet.pins.isEmpty() 또는 System.currentTimeMillis() > pinSet.expirationTime 또는 !isPinningEnforced(chain) 이면 return, 체인을 끝에서부터 돌며 cert.getPublicKey().getEncoded() 를 해시해 pinSet.pins.contains 로 대조, 맞는 게 없으면 148행 throw new CertificateException("Pin verification failed"), 151행 isPinningEnforced 선언](/assets/img/android-mastery/p1c12/07-src-checkpins.png)

113행에서 앵커 검사가 먼저 끝나고 `checkPins`는 그 결과로 나온 신뢰 체인을 받는다. 핀셋이 비어 있거나, 현재 시각이 만료 시각을 지났거나, 체인의 앵커가 `overridePins`면 그냥 돌아간다. 그러니 만료돼도 앵커 검사는 남는다. 앞 표의 `localhost` 줄이 그 경우다. 앵커가 `lab_ca`뿐이라 프록시 체인은 핀 단계까지 가지도 못했다. 반대로 AndroGoat처럼 유저 저장소를 앵커로 물려받은 설정에서 핀셋이 만료되면, 소스대로라면 유저 CA로 끝나는 프록시 체인이 아무 저항 없이 통과한다. 이 조합은 이번 실험에서 돌려 보지 않았다.

128~144행은 체인의 각 인증서에서 SubjectPublicKeyInfo를 해시해 핀 목록과 대조한다. 루트를 핀하든 리프를 핀하든 체인 안에 있으면 맞는다. 실험 NSC의 `10.0.2.2`가 CA 핀과 리프 핀을 함께 둔 이유다. 백업 핀과 `expiration`은 둘 다 선택 사항이다([XmlConfigSource.java 123~152행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#123), 만료를 안 쓰면 `Long.MAX_VALUE`). HPKP가 백업 핀을 [필수로 요구했던 것](https://www.rfc-editor.org/rfc/rfc7469#section-4.3)과 다르다. 핀이 없는 빈 `<pin-set>`도 파서는 받아 주고, 이때는 위의 `isEmpty()` 조건으로 핀 검사가 사라진다.

만료일은 [XmlConfigSource.java 129행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#129)의 `SimpleDateFormat("yyyy-MM-dd")`로 읽는다. 시간대를 따로 주지 않으니 기기 시간대 기준 그날 0시부터 핀이 꺼지고, 판단에는 기기 시계가 쓰인다. 기기 시계를 바꿀 수 있는 사람은 만료일이 적힌 핀셋을 그 날짜 이후로 시계를 돌려 끌 수 있다.

## debug-overrides가 실제로 하는 일

[XmlConfigSource.java 328~338행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#328)은 `mDebugBuild`일 때만 `<debug-overrides>`를 파싱하고 아니면 태그를 건너뛴다. `mDebugBuild`는 [51행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#51)에서 설치된 APK의 `FLAG_DEBUGGABLE`로 정해진다. 앱을 어떻게 띄웠는지는 상관없고 매니페스트의 `android:debuggable`만 본다.

파싱된 내용이 어디로 가는지가 중요하다. [292~304행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#292)의 `addDebugAnchorsIfNeeded`는 디버그 설정의 인증서 참조만, 그것도 자기 `trust-anchors`를 가진 설정에만 덧붙인다(없는 설정은 부모에게서 물려받는다). 핀셋은 건드리지 않는다. 대신 [228행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#228)이 디버그 설정 안의 인증서는 `overridePins` 기본값을 true로 만든다. 결과적으로 디버그 빌드에서 핀이 면제되는 것은 디버그 CA로 끝나는 체인뿐이다. 그래서 디버그 빌드에서도 `lab` 체인은 `127.0.0.1`과 `pinned.seika.test`에서 계속 `PIN-FAIL`이었다. "디버그 빌드는 핀을 무시한다"고 알고 있었다면, 디버그 빌드에 프록시를 붙였는데 핀 걸린 호스트만 안 잡히는 상황에서 헤매게 된다.

`<debug-overrides>`의 `cleartextTrafficPermitted` 속성은 [242행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/XmlConfigSource.java#242)에서 디버그 설정 빌더에 읽혀 들어가지만, 그 빌더에서 실제 설정으로 옮겨지는 것은 인증서 참조뿐이라 이 값은 어디에도 적용되지 않는다. 디버그 빌드의 cleartext 줄에서 `127.0.0.1`과 `localhost`는 그대로 false였다. 디버그 빌드에서 평문을 열려면 해당 `domain-config`에 직접 써야 한다.

## 세 스택에 실제 요청을 보내 보니

신뢰 표는 TrustManager만 따로 불러 본 결과다. 실제 앱은 HTTP 라이브러리를 거치니 그쪽도 같은 답을 내는지 봐야 한다. 같은 디버그 빌드로 플랫폼 `HttpURLConnection`(표의 `huc`), OkHttp 4.12.0, 앱에 묶은 Cronet 143, 그리고 `java.net.Socket`에 HTTP 요청을 손으로 써 보내는 raw 소켓으로 같은 서버를 불렀다.

![p1c12 폴더 터미널. io.seika.nsc 를 다시 띄워 NSCLAB 로그의 cronet: 부터 DONE 까지 출력. cronet: Cronet/143.0.7445.0@1f9b1382. http 10.0.2.2:18120 은 huc, okhttp, cronet, socket 모두 200, http 127.0.0.1:18120 은 huc CLEARTEXT-BLOCKED, okhttp CLEARTEXT-BLOCKED, cronet ERR_CLEARTEXT_NOT_PERMITTED, socket 200. https 10.0.2.2:18121 세 스택 200, 127.0.0.1:18121 은 huc PIN-FAIL, okhttp PIN-FAIL, cronet ERR_CERT_AUTHORITY_INVALID, localhost:18121 세 스택 200, 10.0.2.2:18122 와 localhost:18122 는 huc, okhttp NO-ANCHOR 와 cronet ERR_CERT_AUTHORITY_INVALID, 10.0.2.2:18123 과 127.0.0.1:18123 은 세 스택 200, 127.0.0.1:18121 okhttp+ownTM 200. OkHttp dns *.seika.test -> 10.0.2.2 블록은 pinned.seika.test:18121 PIN-FAIL, api.seika.test:18122 NO-ANCHOR, user.seika.test:18122 PIN-FAIL, override.seika.test:18122 200, pinned.seika.test:18123 200, DONE. 이어서 logcat 의 cn_X509Util: Failed to validate the certificate chain, error: Pin verification failed 한 줄과 java.security.cert.CertPathValidatorException: Trust anchor for certification path not found. 두 줄](/assets/img/android-mastery/p1c12/08-network-debug.png)

세 라이브러리는 모든 줄에서 같은 판단을 내렸고 신뢰 표와도 일치했다. 평문은 `10.0.2.2`에서만 열렸다. 핀이 틀린 `127.0.0.1:18121`은 막히고 핀셋이 만료된 `localhost:18121`은 통과했다. 프록시 체인은 만료와 상관없이 앵커에서 막혔고 디버그 체인은 핀 걸린 호스트까지 통과했다. `*.seika.test`는 OkHttp에 사용자 정의 `Dns`를 붙여 `10.0.2.2`로 보냈는데, 실제 연결에서도 `user.`는 `PIN-FAIL`, `override.`는 `200`이었다.

Cronet은 판단은 같지만 실패 이유를 뭉갠다. 핀 실패든 앵커 실패든 앱이 받는 예외는 `ERR_CERT_AUTHORITY_INVALID`(`InternalErrorCode=-202`) 하나이고, 이유는 logcat의 `cn_X509Util` 줄에만 남는다. 위 캡처 맨 아래 세 줄 가운데 첫 줄이 `127.0.0.1:18121`의 `Pin verification failed`이고, 나머지 두 줄은 프록시 체인의 `Trust anchor for certification path not found.`다. 터미널 출력은 logcat에서 옮긴 것이고, 같은 실행에서 앱 화면에는 아래처럼 남는다.

![에뮬레이터의 NSC probe 앱 화면. 맨 위 io.seika.nsc lab/debug targetSdk=33 debuggable=true 와 user CA user:6042c89d.0, cleartext 줄 10.0.2.2=true 127.0.0.1=false localhost=false api.seika.test=false, trust 표(pinned.seika.test 와 127.0.0.1 의 lab 칸 PIN-FAIL, debug 열 전부 ok), 2-arg checkServerTrusted(lab): NEEDS-HOSTNAME, cronet: Cronet/143.0.7445.0@1f9b1382, http 127.0.0.1:18120 의 huc, okhttp CLEARTEXT-BLOCKED 와 cronet ERR_CLEARTEXT_NOT_PERMITTED, socket 200, https 127.0.0.1:18121 의 cronet ERR_CERT_AUTHORITY_INVALID, okhttp+ownTM 200, OkHttp dns 블록의 user.seika.test:18122 PIN-FAIL 과 override.seika.test:18122 200, 마지막 줄 DONE](/assets/img/android-mastery/p1c12/12-probe-screen.png)

Cronet도 평문과 핀에서 NSC를 그대로 따랐다. 평문은 `ERR_CLEARTEXT_NOT_PERMITTED`로 막혔고, 틀린 핀은 `ERR_CERT_AUTHORITY_INVALID`로 거절됐다. 소스에서도 같은 경로가 보인다. Chromium 143.0.7445.0의 [X509Util.java 600~635행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/X509Util.java#600)은 `X509TrustManagerExtensions`로 감싼 플랫폼 기본 TrustManager([202행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/X509Util.java#202), [266~285행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/X509Util.java#266))에 호스트 이름을 넘겨 `checkServerTrusted`를 부르고, 실패하면 `cn_X509Util` 줄을 남기고 `NO_TRUSTED_ROOT`로 끝낸다.

평문 요청 전에는 [AndroidNetworkLibrary.java 402~406행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/AndroidNetworkLibrary.java#402)이 플랫폼 `NetworkSecurityPolicy`를 감싼 `NetworkSecurityPolicyProxy`를 거쳐 `isCleartextTrafficPermitted(host)`를 묻는다. 호스트 인자 버전이 `IllegalArgumentException`을 던지면 호스트 없는 버전으로 다시 묻는다. 그 답이 false면 [url_request_http_job.cc 416~426행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/url_request/url_request_http_job.cc#416)이 `ERR_CLEARTEXT_NOT_PERMITTED`를 돌려준다. 브라우저용 Chrome Root Store 검증기를 Android Cronet이 쓰지 않는 이유는 빌드 설정에 있다.

![chromium net/features.gni(143.0.7445.0) 47~57행. Chrome Root Store 와 플랫폼 검증기 중 하나로 인증서를 검증할 수 있는 플랫폼에 대한 주석, WebView 가 Android cert verifier 를 쓴다는 주석, 53행 chrome_root_store_optional = is_android && !is_cronet_build, 57행 chrome_root_store_only 가 is_win, is_mac, is_linux, is_chromeos 의 논리합](/assets/img/android-mastery/p1c12/09-src-cronet-verifier.png)

Cronet 빌드에서는 `chrome_root_store_optional`이 거짓이 되고 Android에서는 플랫폼 검증기로 내려간다. 확인한 것은 앱에 Cronet을 직접 묶은 경우(`App-Packaged-Cronet-Provider`)뿐이다. Play 서비스가 제공하는 Cronet과 WebView는 이번에 돌려 보지 않았다.

raw 소켓은 NSC가 평문을 막은 `127.0.0.1:18120`에서도 `200`을 받았다. 평문 차단은 HTTP 라이브러리 안에서 일어난다. 플랫폼 `HttpURLConnection`은 [HttpHandler.java 118~124행](https://android.googlesource.com/platform/external/okhttp/+/refs/tags/android-13.0.0_r84/android/src/main/java/com/squareup/okhttp/HttpHandler.java#118)에서, OkHttp 4.12.0은 [RealConnection.kt 187~190행](https://github.com/square/okhttp/blob/parent-4.12.0/okhttp/src/main/kotlin/okhttp3/internal/connection/RealConnection.kt#L187-L190)에서 Platform을 거쳐 `NetworkSecurityPolicy`에 묻는다. raw 소켓처럼 이 정책을 조회하지 않는 코드는 NSC의 평문 설정과 상관없이 요청을 보낸다. TLS 쪽에서도 비슷한 일이 `okhttp+ownTM` 줄에서 보인다. 앞에서 본 KeyStore 기반 TrustManager를 OkHttp에 넣자, 기본 설정에서 `PIN-FAIL`이던 `127.0.0.1:18121`이 `200`이 됐다.

요청이 서버에 닿았는지도 서버 쪽 로그로 확인했다. 이 실행 직전에 서버를 다시 띄워서 로그에는 위 요청들만 있다.

![p1c12 폴더 터미널. cat labserver.log 에 listening on 127.0.0.1:18120,18121,18122,18123 다음으로 :18120 http 10.0.2.2:18120 의 /huc, /okhttp, /cronet, 10.0.2.2 /socket, 127.0.0.1 /socket, :18121 의 10.0.2.2:18121 /huc, /okhttp, /cronet 뒤 handshake failed: SSLV3_ALERT_CERTIFICATE_UNKNOWN 세 줄, localhost:18121 /huc, /okhttp, /cronet, :18122 handshake failed 일곱 줄, :18123 의 10.0.2.2:18123 과 127.0.0.1:18123 /huc, /okhttp, /cronet, 127.0.0.1:18121 /okhttp-ownTM, handshake failed 세 줄, override.seika.test:18122 /okhttp-dns, pinned.seika.test:18123 /okhttp-dns. 모든 요청의 앱은 io.seika.nsc](/assets/img/android-mastery/p1c12/10-server-log.png)

`127.0.0.1:18120`에 도착한 요청은 `/socket` 하나뿐이다. 세 라이브러리는 연결을 열지도 않았다. 거절된 TLS 연결은 모두 `SSLV3_ALERT_CERTIFICATE_UNKNOWN`을 남겼다. 클라이언트가 서버 인증서를 받아 본 뒤 certificate_unknown 경고를 보내고 끊었다는 뜻이다. `127.0.0.1:18121`에서 세 스택이 거절한 횟수만큼 세 줄이 같은 초에 찍혀 있으니 Cronet도 경고를 보낸다.

`:18122`에서는 기기가 거절한 줄이 여덟인데 서버 쪽 실패는 아홉 번이었다. 에뮬레이터를 새로 부팅해 반복해 봐도 이런 한 줄 차이는 `10.0.2.2`에서 HttpURLConnection과 Cronet이 함께 거절된 포트에서만 가끔 생겼고, 앱이 찍은 결과 로그는 매번 바이트 단위로 같았다. Cronet 줄 근처에서 생기는 것으로 보아 Cronet이 연결을 하나 더 연 것으로 보이지만, 패킷을 캡처하지 않아 확인하지는 못했다.

## NSC가 없으면 targetSdk가 정한다

NSC를 뺀 두 빌드는 코드가 같고 targetSdk만 33과 23으로 다르다. 기기에는 앞에서 넣은 프록시 CA가 유저 저장소에 그대로 있다.

![p1c12 폴더 터미널. io.seika.nsc.plain 을 띄운 결과. io.seika.nsc.plain plain/debug targetSdk=33 debuggable=true, user CA user:6042c89d.0, cleartext 10.0.2.2=false 127.0.0.1=false localhost=false api.seika.test=false, other.example NO-ANCHOR NO-ANCHOR NO-ANCHOR, 2-arg checkServerTrusted(lab): NO-ANCHOR, http 10.0.2.2:18120 과 127.0.0.1:18120 모두 huc, okhttp CLEARTEXT-BLOCKED, cronet ERR_CLEARTEXT_NOT_PERMITTED, socket 200, https 10.0.2.2:18122 와 localhost:18122 는 huc, okhttp NO-ANCHOR, cronet ERR_CERT_AUTHORITY_INVALID, api.seika.test, user.seika.test, override.seika.test:18122 okhttp NO-ANCHOR](/assets/img/android-mastery/p1c12/11a-defaults-plain.png)

![p1c12 폴더 터미널. io.seika.nsc.legacy 를 띄운 결과. io.seika.nsc.legacy legacy/debug targetSdk=23 debuggable=true, user CA user:6042c89d.0, cleartext 10.0.2.2=true 127.0.0.1=true localhost=true api.seika.test=true, other.example NO-ANCHOR NO-ANCHOR ok, 2-arg checkServerTrusted(lab): NO-ANCHOR, http 18120 은 두 호스트 네 방식 모두 200, https 10.0.2.2:18122 와 localhost:18122 는 huc, okhttp, cronet 모두 200, api.seika.test, user.seika.test, override.seika.test:18122 okhttp 200](/assets/img/android-mastery/p1c12/11b-defaults-legacy.png)

targetSdk 33 빌드는 세 HTTP 스택의 평문 요청이 전부 막히고(raw 소켓은 여전히 200) 프록시 체인도 전부 거절됐다. targetSdk 23 빌드는 같은 기기, 같은 저장소에서 평문이 전부 열리고 유저 저장소의 프록시 CA로 끝나는 체인을 세 스택 모두 받아들였다. 앞에서 링크한 `NetworkSecurityConfig.java` 187행과 192행이 정한 기본값대로다. "NSC가 없으면 시스템 CA만 믿는다"는 targetSdk 24 이상에서만 맞다. targetSdk 23 이하 앱은 NSC가 없어도 유저 CA를 믿는다. 반대로 targetSdk 33 앱의 표에서 `lab` 열이 모두 `NO-ANCHOR`인 것은 NSC가 없으니 `@raw/lab_ca` 같은 앱 내장 앵커도 없기 때문이다. [지난 글](/posts/android-lab-p1c11-burp-mitmproxy-intercept/)에서 NSC 없는 targetSdk 23 앱이 유저 CA만으로 복호된 것도 같은 기본값에서 나왔다.

## CI에서 릴리스 APK 대조하기

정적 표와 기기 결과가 맞았으니 점검은 대부분 빌드 산출물에서 끝낼 수 있다. CI에서는 릴리스 APK를 apktool로 풀어(NSC는 매니페스트 속성으로 찾는다) 상속을 푼 호스트별 표를 만들고, 릴리스에서 평문이 열린 호스트가 의도한 목록과 같은지 대조하고, `src="user"`가 앵커에 들어간 설정은 따로 표시해 둔다. 그런 설정은 핀셋을 물려받더라도 만료일이 지나면 유저 CA로 끝나는 프록시 체인을 막을 게 없다. 핀셋에는 백업 핀을 두고, `expiration`을 쓴다면 키 교체 일정보다 넉넉히 뒤로 잡는 편이 안전하다. `overridePins`와 `debug-overrides`에는 디버그 CA만 들어가야 하며, `debug-overrides`의 cleartext 속성은 효과가 없으니 거기 적어 둔 값에 기대지 않는다.

NSC 밖도 같이 본다. 직접 구현한 `X509TrustManager`나 `HostnameVerifier`, KeyStore로 만든 TrustManager를 HTTP 클라이언트에 넣는 코드, OkHttp `CertificatePinner`의 코드 핀, WebView의 `onReceivedSslError` 재정의, raw 소켓, 네이티브 TLS 라이브러리나 Flutter의 dart:io가 있으면 해당 경로는 NSC 표와 따로 판정해야 한다. 디버그 전용 CA는 `debug-overrides`에만 넣고, 디버그 빌드에서 TLS를 풀어야 할 때도 기본 TrustManager를 바꾸지 말고 그 방식을 쓰는 편이 릴리스로 새어 나갈 위험이 적다.

배포 전에는 릴리스 빌드를 기기에 깔아 logcat의 `NetworkSecurityConfig` 태그가 의도한 리소스를 `debugBuild: false`로 읽었는지 확인한다. 핀 걸린 호스트에 유저 CA 프록시를 붙여 보면 회귀 확인이 된다. 연결이 끊기면 정상이다. 앱이 Cronet을 쓴다면 그 실패가 앱 쪽에서는 `ERR_CERT_AUTHORITY_INVALID`로만 보이니 `cn_X509Util` 줄로 이유를 확인한다.

참고 자료: [Network security configuration](https://developer.android.com/privacy-and-security/security-config) · [NetworkSecurityConfig 패키지 소스(android-13.0.0_r84)](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/security/net/config/) · [Cronet X509Util.java(143.0.7445.0)](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/X509Util.java) · [RFC 7469 HPKP](https://www.rfc-editor.org/rfc/rfc7469) · [TLS·NSC·pinning(C46)](/posts/android-concept-atlas-c46-tls-nsc-pinning/)

*다음 글: [저장소·log·clipboard·backup 점검](/posts/android-lab-p1c13-storage-log-clipboard-backup/)*
