---
layout: post
title: "Burp/mitmproxy 로컬 인터셉션 — 유저 CA가 막히는 곳, 핀이 막는 곳"
date: 2026-10-26 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, mitmproxy, Burp, NetworkSecurityConfig, CertificatePinning, Cronet, Frida]
excerpt: "Android 13 에뮬레이터에서 유저 저장소의 mitmproxy CA는 targetSdk 23 앱만 믿었고 targetSdk 33 앱은 Trust anchor 오류로 끊겼다. 시스템 저장소로 옮기자 핀셋을 건 앱은 Pin verification failed, 임베디드 Cronet은 1년짜리 리프를 ERR_CERT_VALIDITY_TOO_LONG으로 거절했다."
---

[지난 글](/posts/android-lab-p1c10-jni-native-observation/)까지는 Frida로 앱 프로세스 안을 들여다봤다. 이번에는 앱이 서버와 주고받는 HTTPS를 프로세스 밖, 호스트의 프록시에서 읽는다. 그러려면 앱의 트래픽이 프록시로 와야 하고 프록시가 그 자리에서 만들어 내미는 인증서를 앱이 믿어야 한다. 앞의 것은 주소를 맞추면 되지만 뒤의 것은 앱이 어느 CA 저장소를 믿느냐에 걸려 있다. 프록시 CA를 설정 앱에서 사용자 인증서로 깔았는데 앱 트래픽이 하나도 안 잡혔다면 뒤쪽에서 막힌 것이다.

직접 만든 앱 몇 벌로 같은 HTTPS 요청을 보내면서 CA를 유저 저장소에서 시스템 저장소로 옮기고 단계마다 어느 앱이 어디서 끊기는지 봤다. 유저 CA가 안 먹히는 이유는 플랫폼 소스 한 줄로 설명된다. 시스템 저장소로 옮긴 뒤에도 핀셋(pin-set)을 건 앱은 여전히 실패했고, 임베디드 Cronet을 쓰는 앱은 전혀 다른 이유로 실패했다.

기기는 `-read-only`로 띄워 끄면 변경이 모두 사라지는 Android 13(API 33, 빌드 TE1A.240213.009, 2024-03-01 보안 패치) x86_64 google_apis userdebug 에뮬레이터로, `adb root`가 되고 SELinux는 Enforcing이다. Android 14 이후의 동작은 Android 16(API 36, BE2A.250530.026.F3) 에뮬레이터에서 확인했다. 프록시는 mitmproxy 11.0.2다. 제목에 Burp를 넣었지만 이 환경에는 Burp Suite가 없어서, 화면과 출력은 전부 mitmproxy의 것이고 Burp가 다르게 동작하는 대목은 PortSwigger 문서로 대신한다. 그 밖에 OpenSSL 3.5.5, apktool 3.0.2, build-tools 36.0.0, Frida 17.17.0과 frida-tools 14.8.1을 썼다. 플랫폼 소스는 frameworks/base의 android13-release(`d27f996`)와 android14-release(`6e47c70`)에서, Cronet 쪽은 앱에 넣은 것과 같은 Chromium 143.0.7445.0 태그에서 봤다. TLS 신뢰 체인과 NSC의 개념은 [C46](/posts/android-concept-atlas-c46-tls-nsc-pinning/)에 있다.

## 자작 앱 여섯 벌과 프록시가 직접 답하는 api.lab.test

실험 앱은 액티비티 하나짜리다. 플랫폼의 `HttpURLConnection`으로 `https://api.lab.test/hello`에 GET을 한 번 보내고 결과를 화면과 logcat의 `Intercept` 태그에 찍는다. 어느 빌드가 보낸 요청인지 프록시에서 가릴 수 있게 `X-Lab-Variant` 헤더에 빌드 이름을 싣는다. 결과 줄에는 targetSdk와 debuggable 여부, 앱이 본 프록시(`ProxySelector`가 돌려준 값), 응답 코드나 예외가 차례로 나온다. 요청을 보내는 부분은 `MainActivity.java`의 이 메서드다.

```java
static String fetch(String url, String variant) {
    HttpURLConnection c = null;
    try {
        c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(8000);
        c.setRequestProperty("X-Lab-Variant", variant);
        int code = c.getResponseCode();
        BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
        return code + " " + r.readLine();
    } catch (Exception e) {
        return e.getClass().getSimpleName() + ": " + e.getMessage();
    } finally {
        if (c != null) c.disconnect();
    }
}
```

같은 코드를 targetSdk, debuggable, NSC만 바꿔 여러 벌로 빌드했다. Cronet을 쓰는 두 벌은 `openConnection` 줄만 `engine.openConnection(new URL(url))`로 바꾸고 `org.chromium.net:cronet-embedded:143.7445.0`을 APK에 넣었다. Play 서비스가 제공하는 Cronet 대신 APK에 든 것을 쓰도록 `CronetProvider.PROVIDER_NAME_APP_PACKAGED` 공급자를 골라 엔진을 만든다.

| 빌드 | targetSdk | debuggable | Network Security Config | HTTP 스택 |
|---|---|---|---|---|
| t23 | 23 | 아니오 | 없음 | HttpURLConnection |
| t33 | 33 | 아니오 | 없음 | HttpURLConnection |
| dbg | 33 | 예 | api.lab.test 핀셋, debug-overrides의 user 앵커 | HttpURLConnection |
| rel | 33 | 아니오 | dbg와 같은 파일 | HttpURLConnection |
| cr | 33 | 아니오 | 없음 | Cronet 143 |
| crnsc | 33 | 아니오 | base-config에 system과 user 앵커 | Cronet 143 |

패키지 이름은 `io.seika.intercept.<빌드>`다. dbg와 rel에 넣은 NSC는 아래와 같다. 핀 두 개는 실험용으로 만든 서버 키(origin)와 백업 키의 SPKI SHA-256이다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config>
        <domain includeSubdomains="false">api.lab.test</domain>
        <pin-set>
            <pin digest="SHA-256">gUgCOxOv2KkQ1bq+Tja8Ky9kItI6o7Xh0o38mjlDa9g=</pin>
            <pin digest="SHA-256">b7EJcPjmkmgJTzspsO8zbUV+la2ucbU0Q1+3eMS8FME=</pin>
        </pin-set>
    </domain-config>
    <debug-overrides>
        <trust-anchors>
            <certificates src="user" />
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```

서버는 따로 두지 않았다. `api.lab.test`로 가는 요청에 mitmproxy가 직접 응답하게 하는 애드온을 붙이고 `--set connection_strategy=lazy`로 띄우면 mitmproxy는 위쪽 서버로 연결을 시도하지 않는다. 실서비스도, DNS도, 인터넷도 끼지 않는다. 대신 프록시를 거치지 않은 요청은 기기에서 `api.lab.test`라는 이름부터 풀지 못하는데, 이 성질이 아래 프록시 주소 실험에서 쓸모가 있었다.

```python
# Mock origin for api.lab.test: mitmproxy answers it itself, so no real server, DNS or internet is involved.
# Run with --set connection_strategy=lazy so mitmproxy never tries to connect upstream.
import logging

from mitmproxy import http


def request(flow: http.HTTPFlow) -> None:
    if flow.request.pretty_host == "api.lab.test":
        body = f"hello from lab origin ({flow.request.scheme} {flow.request.path})\n"
        flow.response = http.Response.make(200, body.encode(), {"content-type": "text/plain"})
        who = flow.request.headers.get("X-Lab-Variant", "-")
        logging.info(f"lab origin answered {flow.request.method} {flow.request.pretty_url} for {who}")
```

기기 쪽은 빌드 이름을 받아 앱을 띄우고 결과 한 줄을 기다리는 `probe.sh`로 돌렸다. `$S`는 에뮬레이터 시리얼이다. `am start -S`가 앱을 먼저 죽이고 띄우므로 매번 새 프로세스가 CA 저장소를 처음부터 읽는다.

```sh
#!/bin/sh
# probe.sh VARIANT [URL] : cold-start io.seika.intercept.VARIANT once and print its result line (logcat tag Intercept)
pkg=io.seika.intercept.$1
adb -s "$S" logcat -c
adb -s "$S" shell am start -S -W -n $pkg/io.seika.intercept.MainActivity ${2:+--es url $2} >/dev/null
for i in $(seq 30); do
  line=$(adb -s "$S" logcat -d -v tag -s Intercept:I | grep '^I/Intercept')
  [ -n "$line" ] && break
  sleep 0.5
done
echo "${line:-$1: no result within 15 s}"
```

## mitmproxy CA와 안드로이드가 찾는 파일 이름

mitmproxy는 처음 뜰 때 설정 폴더에 CA를 만들고 그 뒤로는 클라이언트가 접속하는 호스트마다 그 CA로 서명한 리프 인증서를 즉석에서 만들어 내민다([mitmproxy 인증서 문서](https://docs.mitmproxy.org/stable/concepts/certificates/)). 설정 폴더 기본값은 `~/.mitmproxy`인데 여기서는 `--set confdir=mitm/conf`로 작업 폴더 안에 두었다. 앱이 그 리프를 받아들이느냐는 앱이 믿는 CA 목록에 달려 있다. 기기에 올리기 전에 호스트의 openssl로 먼저 확인했다.

![p1c11 폴더의 호스트 터미널. mitmdump --version 이 Mitmproxy: 11.0.2, ls -C mitm/conf 에 mitmproxy-ca-cert.cer, mitmproxy-ca-cert.pem, mitmproxy-ca.pem, mitmproxy-ca-cert.p12, mitmproxy-ca.p12, mitmproxy-dhparam.pem, openssl x509 -subject -subject_hash_old 가 subject=CN=mitmproxy, O=mitmproxy 와 c8750f0d, 그 이름으로 c8750f0d.0 을 만들고 python android_hash.py c8750f0d.0 도 c8750f0d. mitmdump -p 18119 는 HTTP(S) proxy listening at *:18119, --listen-host 127.0.0.1 -p 18110 --set confdir=mitm/conf --set connection_strategy=lazy -s mitm/lab_origin.py 는 127.0.0.1:18110. openssl s_client -proxy 로 받은 체인은 0 s:CN=api.lab.test, i:CN=mitmproxy, O=mitmproxy 이고 Verify return code: 20 (unable to get local issuer certificate), -CAfile 을 주면 Verify return code: 0 (ok), 프록시 로그는 Client TLS handshake failed. The client does not trust the proxy's certificate for api.lab.test (tlsv1 alert unknown ca)](/assets/img/android-mastery/p1c11/01-proxy-ca-host.png)

프록시를 거쳐 받은 체인은 리프 `CN=api.lab.test`와 발급자 `CN=mitmproxy, O=mitmproxy`다. CA를 주지 않으면 openssl은 `Verify return code: 20 (unable to get local issuer certificate)`로 끝나고 프록시 로그에는 `The client does not trust the proxy's certificate for api.lab.test (tlsv1 alert unknown ca)`가 남는다. `-CAfile`로 mitmproxy CA를 주면 `0 (ok)`다. 뒤에서 볼 기기 쪽 실패도 프록시 로그에는 이 문장으로 남는다. 괄호 안의 TLS 경고 이름만 다르다.

안드로이드의 CA 디렉터리는 인증서를 `<해시>.0`이라는 파일 이름으로 찾는다. 해시는 주체(subject)를 DER로 인코딩한 값의 MD5 앞 4바이트를 리틀엔디언으로 읽은 것으로, [DirectoryCertificateSource.java 211~222행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/DirectoryCertificateSource.java#211)의 `hashName()`에는 Conscrypt의 `X509_NAME_hash_old()`와 맞춰 둔 코드라는 주석이 붙어 있고, openssl의 `-subject_hash_old`도 같은 이름의 함수로 계산한다. 이 계산을 파이썬으로 옮긴 `android_hash.py`도 openssl과 같은 `c8750f0d`를 냈다.

```python
# Same hash as Android's DirectoryCertificateSource.hashName(): MD5 of the DER subject, first 4 bytes little-endian.
import hashlib, sys
from cryptography import x509

cert = x509.load_pem_x509_certificate(open(sys.argv[1], "rb").read())
d = hashlib.md5(cert.subject.public_bytes()).digest()
print("%08x" % int.from_bytes(d[:4], "little"))
```

mitmproxy CA의 주체는 늘 `CN=mitmproxy, O=mitmproxy`라서 설치할 때마다 키는 달라도 파일 이름은 `c8750f0d.0`으로 같다. Burp는 CA를 DER로 내보내므로([PortSwigger 안드로이드 기기 설정 문서](https://portswigger.net/burp/documentation/desktop/mobile/config-android-device)) Burp가 없어 확인하지는 못했지만 같은 계산에 `-inform DER`을 붙여야 할 것이다.

리스너 주소는 두 도구의 기본값이 반대다. 이 절 첫 캡처의 `mitmdump -p 18119` 줄에서 보듯 주소를 주지 않으면 `*:18119`, 곧 모든 인터페이스에서 듣는다([옵션 문서](https://docs.mitmproxy.org/stable/concepts/options/)의 `listen_host`). Burp의 기본 리스너는 루프백의 8080 하나뿐이고([Burp Proxy 설정 문서](https://portswigger.net/burp/documentation/desktop/settings/tools/proxy)), 같은 Wi-Fi의 실기기를 붙이려면 PortSwigger 안내대로 Bind to address를 All interfaces로 바꾸고 기기 프록시에 호스트의 LAN IP를 준다. Burp Proxy 설정 문서가 경고하듯 모든 인터페이스에 묶인 리스너에는 같은 망의 다른 컴퓨터도 붙을 수 있으니, mitmproxy를 공유망에서 기본값으로 띄우는 것도 같은 상태다. 에뮬레이터는 루프백 리스너로 충분해서 `--listen-host 127.0.0.1`로 묶었다(실기기는 이번에 붙이지 않았다).

`export PYTHONUNBUFFERED=1`은 mitmproxy 출력을 파일로 돌릴 때 넣었다. 이게 없으면 로그 파일이 프로세스가 끝날 때까지 비어 있어서 프록시가 아무것도 못 받은 것처럼 보인다.

기기 실험에서는 흐름을 웹 화면으로 보려고 mitmweb을 썼다. 프록시는 `127.0.0.1:18110`, 웹 UI는 `127.0.0.1:18111`이다.

```bash
export PYTHONUNBUFFERED=1
mitmweb --listen-host 127.0.0.1 -p 18110 --web-host 127.0.0.1 --web-port 18111 --no-web-open-browser \
  --set confdir=mitm/conf --set connection_strategy=lazy -s mitm/lab_origin.py \
  --set 'allow_hosts=api\.lab\.test' > mitm.log 2>&1
```

`allow_hosts`는 정규식을 받아서 점을 이스케이프했고, 처음에는 이 옵션을 넣지 않았다. 기기 프록시를 호스트로 돌리자마자 에뮬레이터의 구글 앱들이 `www.googleapis.com`, `youtubei.googleapis.com`, `android.googleapis.com` 같은 호스트로 연결을 쏟아냈고, 2분 남짓 사이에 로그가 `does not trust the proxy's certificate` 줄로 가득 찼다. CA를 시스템 저장소에 넣은 뒤였다면 핀을 걸지 않은 앱의 트래픽은 복호까지 됐을 것이다. `allow_hosts`를 주면 mitmproxy는 맞는 호스트만 가로채고 나머지는 열어 보지 않고 넘긴다.

기기 준비는 앱 설치와 파일 세 개 올리기다. `c8750f0d.0`은 위 캡처에서 만든 CA 파일이고 `usercert.sh`, `syscert.sh`의 내용은 아래에서 차례로 나온다.

```bash
export S=emulator-5600
adb -s $S root
for a in t23 t33 dbg rel cr crnsc; do adb -s $S install $a.apk; done
adb -s $S push c8750f0d.0 usercert.sh syscert.sh /data/local/tmp/
```

## 127.0.0.1을 프록시로 주면 DNS 오류가 난다

앱이 쓰는 프록시는 시스템 설정 `http_proxy`([Settings.Global.HTTP_PROXY](https://developer.android.com/reference/android/provider/Settings.Global#HTTP_PROXY))다. 앱 프로세스가 뜰 때 [ActivityThread.java 6690행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/app/ActivityThread.java#6690)이 연결 관리자의 기본 프록시를 [Proxy.java 203행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/net/Proxy.java#203)의 `setHttpProxyConfiguration(ProxyInfo)`에 넘기고, 이 메서드가 부르는 218~231행의 오버로드가 `http.proxyHost`, `https.proxyHost` 시스템 속성을 채운다. 실험 앱이 찍는 `proxy=[HTTP @ ...]`는 이 속성을 읽은 `ProxySelector`의 결과다. 첫 실행에서는 `settings put` 뒤 1분쯤 앱이 `proxy=[DIRECT]`를 찍었다. 새로 부팅해 다시 돌렸을 때는 바로 반영돼 원인은 확인하지 못했다.

이번 에뮬레이터는 프록시 옵션 없이 띄웠으니 `-http-proxy` 쪽 동작은 문서 설명만 옮긴다. [에뮬레이터 프록시 문서](https://developer.android.com/studio/run/emulator-networking-proxy)는 이 옵션을 네트워크 계층에서 동작하는 프록시로 설명하고, HTTPS를 복호하지 않은 채 TCP로 터널링한다고 적으며, 앱 트래픽 검사에는 Android 시스템 프록시를 권한다.

어느 주소가 호스트의 프록시에 닿는지는 평문 HTTP 주소로 먼저 봤다.

```bash
adb -s $S shell settings put global http_proxy 127.0.0.1:18110
./probe.sh t23 http://api.lab.test/plain
adb -s $S reverse tcp:18110 tcp:18110
./probe.sh t23 http://api.lab.test/plain
adb -s $S reverse --remove tcp:18110
adb -s $S shell settings put global http_proxy 10.0.2.2:18110
./probe.sh t23 http://api.lab.test/plain
./probe.sh t33 http://api.lab.test/plain
grep -o 'lab origin answered.*' mitm.log
```

![기기 프록시 주소 실험 터미널. settings put global http_proxy 127.0.0.1:18110 뒤 t23 은 프록시를 HTTP @ 127.0.0.1:18110 으로 읽고도 UnknownHostException: Unable to resolve host "api.lab.test": No address associated with hostname, adb reverse tcp:18110 tcp:18110 뒤 같은 127.0.0.1 설정으로 200 hello from lab origin (http /plain), http_proxy 10.0.2.2:18110 으로 바꾸자 t23 200, t33 은 IOException: Cleartext HTTP traffic to api.lab.test not permitted, mitm.log 에는 lab origin answered GET http://api.lab.test/plain for t23 두 줄](/assets/img/android-mastery/p1c11/02-proxy-address.png)

`127.0.0.1:18110`을 주자 앱은 프록시를 제대로 읽었는데(`proxy=[HTTP @ 127.0.0.1:18110]`) 결과는 DNS 오류인 `UnknownHostException: Unable to resolve host "api.lab.test"`였다. 에뮬레이터 안의 127.0.0.1은 기기 자신이고 그 포트에는 아무것도 없다. Android에 들어 있는 OkHttp는 경로를 고를 때 `ProxySelector`가 준 프록시를 차례로 시도하고 맨 끝에 `Proxy.NO_PROXY`, 곧 직접 연결을 한 번 더 붙여 둔다([RouteSelector.java 117~124행](https://android.googlesource.com/platform/external/okhttp/+/fba9ea2fbda5e85b0ffd671b2a819ebf26a7917b/okhttp/src/main/java/com/squareup/okhttp/internal/http/RouteSelector.java#117)). 프록시 연결이 실패하자 직접 연결로 넘어갔고, 직접 연결은 `api.lab.test`를 풀지 못해 DNS 오류로 끝난 것으로 보인다. 이 폴백을 기기에서 추적하지는 않았고 오류 문구와 소스로 미루어 본 것이다. 실제 서비스였다면 이름이 풀려 요청이 프록시를 건너뛰고 곧장 나갔을 테니, 주소가 틀렸을 때 보이는 증상은 프록시에 아무것도 안 잡히는 것뿐일 것이다.

`adb reverse tcp:18110 tcp:18110`으로 기기의 18110을 adb 연결 너머 호스트의 18110에 이어 주자 같은 127.0.0.1 설정으로 200이 나왔다. 루프백에만 묶인 리스너를 쓸 때 쓸 만한 방법이다. 에뮬레이터에서는 `10.0.2.2`가 호스트 루프백의 별칭이라([에뮬레이터 네트워크 주소 문서](https://developer.android.com/studio/run/emulator-networking-address)) `10.0.2.2:18110`도 바로 통했다. 이후 실험은 모두 이 주소로 했다.

같은 평문 요청을 t33으로 보내자 `IOException: Cleartext HTTP traffic to api.lab.test not permitted`로 끝났고 프록시 로그에는 t23의 두 줄만 남았다. 요청이 앱을 떠나기도 전에 막혔다. 문구는 Android OkHttp의 [HttpHandler.java 120~124행](https://android.googlesource.com/platform/external/okhttp/+/fba9ea2fbda5e85b0ffd671b2a819ebf26a7917b/android/src/main/java/com/squareup/okhttp/HttpHandler.java#120)에서 나온다. NSC가 없을 때 평문 허용 여부는 [NetworkSecurityConfig.java 187행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/NetworkSecurityConfig.java#187)의 `info.targetSdkVersion < Build.VERSION_CODES.P`로 정해진다. 경계가 targetSdk 28이라 같은 Android 13에서도 t23은 평문을 보냈다.

## 유저 CA를 넣자 targetSdk 33 앱이 끊겼다

이제 CA를 유저 저장소에 넣는다. 보통은 설정 앱의 인증서 설치 화면을 거친다. Android 11부터는 앱이 `KeyChain.createInstallIntent()`로 CA 설치를 띄울 수 없고 설정 앱에서만 깔 수 있다([KeyChain 문서](https://developer.android.com/reference/android/security/KeyChain#createInstallIntent%28%29)). 설치 직전에는 아래 경고가 나온다. 이 화면은 루트 adb로 설정 앱의 `InstallCaCertificateWarning` 액티비티를 직접 띄워 찍었고 설치는 진행하지 않았다.

![에뮬레이터 설정 앱의 CA 설치 경고 화면. 빨간 경고 아이콘, 제목 Your data won't be private, CA certificates are used by websites, apps, and VPNs for encryption. Only install CA certificates from organizations you trust. 와 If you install a CA certificate, the certificate owner could access your data, such as passwords or credit card details 로 시작하는 두 문단, 아래쪽 INSTALL ANYWAY 와 DON'T INSTALL 버튼](/assets/img/android-mastery/p1c11/13b-ca-install-warning.png)

설치가 끝나면 남는 건 파일 하나다. 유저 저장소는 [UserCertificateSource.java 33~34행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/UserCertificateSource.java#33)에서 보듯 `/data/misc/user/<사용자 ID>/cacerts-added` 디렉터리다. 설정 앱의 설치 요청을 받은 KeyChain 서비스가 쓰는 conscrypt의 [TrustedCertificateStore.java 199~213행](https://android.googlesource.com/platform/external/conscrypt/+/3832167e0316aa5ba7ffb921a10c6ba4df0f2b2f/platform/src/main/java/org/conscrypt/TrustedCertificateStore.java#199) `writeCertificate()`는 디렉터리를 만들고 인증서를 DER로 써 넣은 뒤 디렉터리와 파일을 모두가 읽을 수 있게 열어 둔다. 매번 화면을 누르는 대신 루트 셸에서 같은 상태를 만드는 `usercert.sh`를 썼다. 파일은 PEM 그대로 넣었는데 플랫폼은 문제없이 읽었다(아래 t23의 200).

```sh
#!/system/bin/sh
# usercert.sh CERT : copy CERT into user 0's added-CA directory, where Settings > Install a certificate puts it (needs root)
set -e
D=/data/misc/user/0/cacerts-added
mkdir -p $D
cp "$1" $D/
chown -R system:system $D
chmod 755 $D
chmod 644 $D/*
restorecon -R $D
```

이렇게 넣은 파일도 설정의 Trusted credentials 화면 User 탭에 `mitmproxy`로 올라온다. 시스템이 보기에 설정 앱으로 깐 것과 같은 유저 CA다.

![에뮬레이터 설정의 Trusted credentials 화면. System 과 User 탭 중 User 가 선택돼 있고 목록에 mitmproxy / mitmproxy 항목 하나](/assets/img/android-mastery/p1c11/13-settings-user-ca.png)

이 상태에서 여섯 벌을 차례로 띄웠다.

```bash
adb -s $S shell sh /data/local/tmp/usercert.sh /data/local/tmp/c8750f0d.0
adb -s $S shell ls -lZ /data/misc/user/0/cacerts-added
./probe.sh t23
./probe.sh t33
./probe.sh dbg
./probe.sh rel
./probe.sh cr
./probe.sh crnsc
grep -o 'Client TLS handshake failed.*' mitm.log | sort | uniq -c
grep -o 'lab origin answered GET https.*' mitm.log
```

![유저 CA 실험 터미널. usercert.sh 실행에 SELinux: Loaded file_contexts, ls -lZ 에 -rw-r--r-- 1 system system u:object_r:misc_user_data_file:s0 1172 c8750f0d.0. probe 결과 t23 target=23 은 200 hello from lab origin (https /hello), t33 target=33 은 SSLHandshakeException: java.security.cert.CertPathValidatorException: Trust anchor for certification path not found., dbg target=33 debuggable=true 는 200, rel 은 t33 과 같은 Trust anchor 실패, cr 은 cronet/Cronet/143.0.7445.0@1f9b1382 로 NetworkExceptionImpl: Exception in CronetUrlRequest: net::ERR_CERT_AUTHORITY_INVALID, ErrorCode=11, InternalErrorCode=-202, crnsc 는 200. mitm.log 의 Client TLS handshake failed. The client does not trust the proxy's certificate for api.lab.test 가 4 회, lab origin answered 는 t23, dbg, crnsc 세 줄](/assets/img/android-mastery/p1c11/04-user-ca.png)

t23은 200을 받았고 t33은 `SSLHandshakeException: java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.`로 끊겼다. 같은 기기, 같은 CA, 같은 코드에서 targetSdk만 다르다. 핀셋과 debug-overrides가 있는 두 벌은 갈렸다. debuggable인 dbg는 통했고 NSC 파일이 똑같은 rel은 t33과 같은 오류를 냈다. Cronet 쪽은 NSC가 없는 cr이 `net::ERR_CERT_AUTHORITY_INVALID`(내부 코드 -202), NSC에서 유저 CA를 켠 crnsc가 200이다. 프록시 로그의 `Client TLS handshake failed` 네 줄은 시각을 맞춰 보면 t33, rel, 그리고 cr이 거의 동시에 연 연결 두 개다. 이 숫자는 거절된 연결의 수다. 새로 부팅한 에뮬레이터에서 같은 순서를 다시 돌렸을 때는 빌드별 결과는 똑같았지만 cr이 연결을 하나만 열어 세 줄이었다. 줄의 앞부분은 openssl 때와 같고, 괄호 안의 TLS 경고가 `tlsv1 alert unknown ca` 대신 `ssl/tls alert certificate unknown`이다.

t33의 화면에는 바깥 예외 이름 뒤에 원인 예외가 붙어 나온다.

![에뮬레이터의 Intercept t33 앱 화면. t33 target=33 debuggable=false, GET https://api.lab.test/hello, proxy HTTP @ 10.0.2.2:18110, 그 아래 SSLHandshakeException: java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.](/assets/img/android-mastery/p1c11/03-t33-user-ca-screen.png)

## targetSdk 24부터 유저 저장소는 기본 설정에서 빠진다

NSC가 없는 앱에는 플랫폼의 기본 설정이 적용된다. 그 설정을 만드는 코드가 아래다.

![frameworks/base android13-release 의 NetworkSecurityConfig.java 163~199행. javadoc 에 API level 27 이하면 cleartext 허용, API level 23 이하면 user certificate store 도 신뢰, Privileged applications do not trust the user certificate store on Android P and higher. getDefaultBuilder 에서 SystemCertificateSource 를 false 로 추가하고 187행 cleartextTrafficPermitted = info.targetSdkVersion < Build.VERSION_CODES.P, 강조된 192행 if (info.targetSdkVersion <= Build.VERSION_CODES.M && !info.isPrivilegedApp()) 안에서만 UserCertificateSource 를 추가](/assets/img/android-mastery/p1c11/05-src-nsc-default-user-ca.png)

[NetworkSecurityConfig.java의 `getDefaultBuilder()`](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/NetworkSecurityConfig.java#181)는 시스템 저장소를 늘 넣고(184~186행), 유저 저장소는 192행의 조건 `info.targetSdkVersion <= Build.VERSION_CODES.M && !info.isPrivilegedApp()`이 참일 때만 넣는다. 190~191행 주석대로 Android 7.0(N, API 24) 이상을 타깃으로 하는 앱은 유저 저장소를 쓰려면 스스로 선택해야 한다. 기준이 기기의 OS 버전이 아니라 앱의 targetSdk라서 Android 13의 t23이 유저 CA를 믿었다. 시스템의 privileged 앱은 Android 9부터 targetSdk와 상관없이 유저 저장소를 믿지 않는다(175행). 186행과 195행에 넘기는 `false`는 그 저장소에서 온 앵커가 핀을 무시하지 않는다는 표시인데, 이 값은 핀 실험에서 다시 나온다.

dbg와 rel은 NSC 파일이 같으니 차이는 `<debug-overrides>`를 읽느냐에서 나온다. [XmlConfigSource.java](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/XmlConfigSource.java#51)는 51행에서 앱의 `FLAG_DEBUGGABLE`을 `mDebugBuild`에 담고 328~338행에서 debuggable이 아니면 `<debug-overrides>` 태그를 통째로 건너뛴다. rel에는 그 안의 user 앵커가 아예 없는 셈이다. dbg에서는 앵커가 들어오고, 228행에서 debug-overrides 안의 `<certificates>`는 `overridePins` 기본값이 참이 된다. 체인이 이 앵커로 끝나면 핀셋을 검사하지 않으므로 dbg는 핀셋이 있어도 mitmproxy 인증서로 200을 받았다. [NSC 문서](https://developer.android.com/privacy-and-security/security-config)도 debug-overrides의 앵커로 끝나는 체인에는 핀을 적용하지 않고 `android:debuggable`이 false면 이 섹션 전체를 무시한다고 적고 있다.

cr과 crnsc도 NSC 파일 하나로 결과가 갈렸는데, Cronet이 이 설정을 어디서 읽는지는 아래 Cronet 절에서 소스로 따라간다.

## 릴리스 앱에 user 앵커를 넣으려면 다시 묶어야 한다

rel 같은 릴리스 빌드가 유저 CA를 믿게 하려면 `<base-config>`의 trust-anchors에 `<certificates src="user"/>`가 있어야 한다. base-config는 debuggable과 상관없이 읽히므로(XmlConfigSource 318~324행) 이 파일 하나면 되지만, 남이 만든 앱이면 APK를 풀어 다시 묶어야 한다. NSC가 없는 t33에 해 봤고, 넣은 파일에는 system과 user 앵커만 있다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config>
        <trust-anchors>
            <certificates src="system" />
            <certificates src="user" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

`-p fw`는 apktool이 쓰는 프레임워크 파일을 작업 폴더의 `fw/`에 두는 옵션이고([5장](/posts/android-lab-p1c05-apktool-smali/)), `attacker.jks`는 원래 서명과 다른 키다.

```bash
apktool d -p fw -f t33.apk -o t33-src
mkdir -p t33-src/res/xml && cp nsc-user.xml t33-src/res/xml/network_security_config.xml
sed -i 's|<application |<application android:networkSecurityConfig="@xml/network_security_config" |' t33-src/AndroidManifest.xml
grep -o '<application[^>]*>' t33-src/AndroidManifest.xml
apktool b -p fw t33-src -o t33-nsc-unsigned.apk
zipalign -p -f 4 t33-nsc-unsigned.apk t33-nsc-aligned.apk
apksigner sign --ks attacker.jks --ks-key-alias attacker --ks-pass pass:attacker --out t33-nsc.apk t33-nsc-aligned.apk
aapt2 dump xmltree --file AndroidManifest.xml t33-nsc.apk | grep -E 'package=|networkSecurityConfig'
for a in t33.apk t33-nsc.apk; do echo "$a $(apksigner verify --print-certs $a | grep -o 'SHA-256 digest: .*')"; done
```

![t33 리패키징 호스트 터미널. cat nsc-user.xml 에 base-config 의 trust-anchors 로 certificates src="system" 과 src="user", apktool d -p fw -f t33.apk -o t33-src 의 Using Apktool 3.0.2 와 Loading resource table from file: fw\1.apk, network_security_config.xml 복사와 sed 로 바뀐 application 태그의 android:networkSecurityConfig="@xml/network_security_config" android:allowBackup="false", apktool b 의 Built apk into: t33-nsc-unsigned.apk, zipalign 과 apksigner sign --ks attacker.jks, aapt2 dump xmltree 의 package="io.seika.intercept.t33" 와 networkSecurityConfig(0x01010527)=@0x7f010000, 서명자 SHA-256 digest 가 t33.apk 766e4a4ce2ecb9bf... 와 t33-nsc.apk 863afb436354b0cb... 로 다름](/assets/img/android-mastery/p1c11/06-repack-nsc-host.png)

매니페스트의 `networkSecurityConfig`가 `@xml/network_security_config`를 가리키고 서명자 해시는 `766e4a4c…`에서 `863afb43…`으로 바뀌었다. `.so`가 없는 APK라 zipalign은 [7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)에서 쓴 `-P 16` 대신 옛 `-p`로 돌렸다. 유저 CA가 깔린 기기에 올렸다.

```bash
adb -s $S install -r t33-nsc.apk
adb -s $S uninstall io.seika.intercept.t33
adb -s $S install t33-nsc.apk
./probe.sh t33
grep -o 'lab origin answered GET https.*' mitm.log | tail -n 1
```

![리패키징한 t33 설치 터미널. adb install -r t33-nsc.apk 가 Performing Incremental Install, Performing Streamed Install 뒤 adb.exe: failed to install t33-nsc.apk: Failure INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package io.seika.intercept.t33 signatures do not match newer version; ignoring!, uninstall io.seika.intercept.t33 은 Success, install t33-nsc.apk 도 Success, probe t33 은 target=33 debuggable=false 로 200 hello from lab origin (https /hello), mitm.log 마지막 줄 lab origin answered GET https://api.lab.test/hello for t33](/assets/img/android-mastery/p1c11/07-repack-device.png)

원본 위에 덮어 깔기는 서명자가 달라 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`로 거부됐다. 지우고 새로 깔면 들어가지만 앱 데이터도 함께 사라진다. 로그인한 상태 그대로 트래픽을 보고 싶을 때는 이 비용이 크다. 다시 깐 t33은 유저 CA만 있는 상태에서 200을 받았다. 같은 방법으로 pin-set을 지워 다시 묶는 것도 가능하다. 서명 검사나 무결성 검사가 없는 앱이라면 막을 장치가 없다. 확인한 뒤에는 원래 t33을 다시 깔아 두었다.

## 시스템 저장소에 넣으면 앱은 믿지만 핀은 그대로다

루트가 있으면 앱을 건드리지 않고 시스템 저장소에 CA를 넣을 수 있다. Android 13의 시스템 저장소는 [SystemCertificateSource.java 35행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/SystemCertificateSource.java#35)의 `$ANDROID_ROOT/etc/security/cacerts`(이 기기에서는 `/system/etc/security/cacerts`)다. 흔히는 `-writable-system`으로 띄운 에뮬레이터에서 `adb remount`로 /system을 쓰기 가능하게 만든 뒤 파일을 복사한다. 이번 인스턴스는 `-read-only`라 [1장](/posts/android-lab-p1c01-research-environment/)에서 본 대로 `adb remount`가 실패한다. 그래서 디렉터리 위에 tmpfs를 올리고 원래 파일과 새 CA를 함께 복사하는 `syscert.sh`를 썼다. /system 파티션은 건드리지 않고 재부팅하면 사라진다.

```sh
#!/system/bin/sh
# syscert.sh CERT [DIR] : add CERT to a system CA directory until the next reboot (needs root).
# DIR defaults to /system/etc/security/cacerts (Android 13 and lower). A tmpfs copy is mounted over DIR,
# keeping the directory's SELinux label so apps can still read it.
set -e
D=${2:-/system/etc/security/cacerts}
T=/data/local/tmp/cacerts-copy
L=$(ls -dZ $D | cut -d' ' -f1)
mkdir -p $T
cp $D/* $T/
mount -t tmpfs tmpfs $D
cp $T/* $D/
cp "$1" $D/
rm -r $T
chown root:root $D $D/*
chmod 755 $D
chmod 644 $D/*
chcon $L $D $D/*
```

마지막 `chcon`은 마운트 전에 읽어 둔 원래 디렉터리의 SELinux 라벨을 새 tmpfs와 파일에 다시 붙인다. 이 라벨 `system_security_cacerts_file`은 모든 도메인이 읽을 수 있게 정책에 열려 있다([sepolicy public/domain.te 167행](https://android.googlesource.com/platform/system/sepolicy/+/6f6029407a5e7059e2ae2ac2e6cfd0c9b4e00509/public/domain.te#167)). 유저 CA 파일을 지우고 시스템 저장소에만 넣은 뒤 같은 요청을 보냈다.

```bash
adb -s $S shell rm /data/misc/user/0/cacerts-added/c8750f0d.0
adb -s $S shell sh /data/local/tmp/syscert.sh /data/local/tmp/c8750f0d.0
adb -s $S shell "mount | grep cacerts; ls -lZ /system/etc/security/cacerts/c8750f0d.0"
./probe.sh t33
./probe.sh cr
./probe.sh rel
./probe.sh dbg
grep -o 'lab origin answered GET https.*' mitm.log | tail -n 2
```

![시스템 저장소 실험 터미널. 유저 CA 파일 rm, syscert.sh 실행, mount 에 tmpfs on /system/etc/security/cacerts type tmpfs (rw,seclabel,relatime), ls -lZ 에 -rw-r--r-- 1 root root u:object_r:system_security_cacerts_file:s0 1172 c8750f0d.0. t33 은 200 hello from lab origin (https /hello), cr 은 NetworkExceptionImpl: Exception in CronetUrlRequest: net::ERR_CERT_VALIDITY_TOO_LONG, ErrorCode=11, InternalErrorCode=-213, rel 과 dbg(debuggable=true) 는 둘 다 SSLHandshakeException: Pin verification failed, mitm.log 마지막 두 줄은 모두 lab origin answered ... for t33](/assets/img/android-mastery/p1c11/08-system-ca.png)

t33은 재부팅 없이 200을 받았다. 시스템 저장소 객체는 `NoPreloadHolder`로 감싸여 있어(SystemCertificateSource 28~30행) 프로세스가 처음 쓸 때 만들어진다. 새로 뜬 앱은 바뀐 디렉터리를 읽는다. adb 셸과 zygote64는 마운트 네임스페이스가 다른데도(`mnt:[4026532373]`과 `mnt:[4026532893]`) adb 셸에서 올린 tmpfs가 앱에 보였다. Android 16에서 떠 본 mountinfo를 보면 이 경로의 마운트가 adb 쪽에서는 `shared:39`, zygote와 앱 쪽에서는 `master:39`로 묶여 있어 한쪽에서 올린 마운트가 다른 쪽으로 전파됐다. Android 13에서는 mountinfo를 떠 보지 않았지만 같은 전파가 일어난 것으로 보인다. mitm.log 마지막 두 줄이 모두 t33인 건 앞의 리패키징 실험과 이번 요청이 한 줄씩 남겨서다.

rel과 dbg는 `SSLHandshakeException: Pin verification failed`로 끊겼다. CA는 이제 믿지만 핀이 맞지 않는다. NSC의 신뢰 판단은 [NetworkSecurityTrustManager.java 111~116행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/NetworkSecurityTrustManager.java#111)에서 보듯 체인을 먼저 검증하고(`mDelegate.checkServerTrusted`) 그 결과 체인에 `checkPins()`를 적용하는 순서다. CA를 시스템 저장소로 옮기면 앞 단계만 통과한다. 이 단계를 새로 부팅한 지 2분쯤 된 에뮬레이터에서 다시 돌렸을 때 rel이 한 번은 프록시 연결을 연 채 8.4초 동안 TLS를 시작하지 못하고 `UnknownHostException`으로 끝났다. 곧바로 세 번 더 돌리니 모두 `Pin verification failed`였다. 부팅 직후에는 주소가 맞아도 프록시가 안 잡히는 것처럼 보일 수 있다.

dbg가 이번에는 실패한 것도 같은 파일에서 설명된다. [isPinningEnforced()](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/NetworkSecurityTrustManager.java#151)(151~162행)는 체인 끝 앵커를 찾아 그 앵커의 `overridesPins`가 거짓이면 핀을 검사한다. 앵커가 이제 기본 설정의 시스템 소스에서 오고, 위 소스 캡처의 186행처럼 그 소스는 핀을 무시하지 않는다. 같은 CA가 두 소스에 다 있었다면 핀을 무시하는 쪽 앵커가 먼저 잡히도록 정렬돼 있어서(NetworkSecurityConfig 57~69행) dbg가 통했겠지만, 여기서는 유저 CA를 지웠으니 시스템 소스 하나뿐이고 그래서 dbg도 핀 검사를 받았다.

cr은 이번에는 `net::ERR_CERT_VALIDITY_TOO_LONG`(-213)으로 실패했다. 이름대로 리프의 유효 기간을 문제 삼은 오류다.

## mitmweb에 남은 복호된 요청

시스템 저장소 단계에서 통과한 t33의 요청을 mitmweb에서 열었다.

![mitmweb Flow 화면. 왼쪽 목록에 http://api.lab.test/plain 200 36b 두 건, https://api.lab.test/hello 200 37b 세 건, http://connectivitycheck.gstatic.com/generate_204 204 세 건, 다시 https://api.lab.test/hello 두 건이 있고 마지막 건이 선택됨. 오른쪽 Request 탭에 GET https://api.lab.test/hello HTTP/1.1, X-Lab-Variant: t33, User-Agent: Dalvik/2.1.0 (Linux; U; Android 13; sdk_gphone64_x86_64 Build/TE1A.240213.009), Host: api.lab.test, Connection: Keep-Alive, Accept-Encoding: gzip, No content, 아래 상태줄 127.0.0.1:18110 과 mitmproxy 11.0.2](/assets/img/android-mastery/p1c11/09-mitmweb-decrypted-t33.png)

오른쪽에 요청 줄과 헤더가 평문으로 보인다. 왼쪽 목록은 지금까지 프록시를 지난 흐름이다. 평문 `/plain` 두 건, 유저 CA 단계에서 통과한 t23, dbg, crnsc의 `/hello` 세 건, 리패키징한 t33과 시스템 CA 단계의 t33 두 건이다. 사이에 낀 `connectivitycheck.gstatic.com/generate_204` 세 건은 에뮬레이터가 인터넷 연결을 확인하려고 보내는 평문 요청인데, `allow_hosts`와 상관없이 흐름으로 남았다. 핸드셰이크에서 끊긴 요청은 흐름 목록에 나오지 않고 로그에만 남는다.

## 핀이 맞춰 보는 것은 공개키 해시

rel의 핀은 실험용 origin 키와 백업 키의 SPKI SHA-256이다. 두 번째 mitmdump를 18112에 띄우고 `--certs api.lab.test=origin/origin-chain.pem`으로 origin 키가 든 리프를 내밀게 했다. 이 리프도 실험용으로 같은 mitmproxy CA가 서명했다. 두 프록시가 내미는 리프의 공개키 해시를 견주고 rel을 양쪽으로 보냈다.

```bash
export PYTHONUNBUFFERED=1
mitmdump --listen-host 127.0.0.1 -p 18112 --set confdir=mitm/conf --set connection_strategy=lazy --set allow_hosts=api.lab.test --certs api.lab.test=origin/origin-chain.pem -s mitm/lab_origin.py > mitm-origin.log 2>&1 & sleep 5
cat origin/pins.txt
for p in 18110 18112; do echo "$p $(openssl s_client -proxy 127.0.0.1:$p -connect api.lab.test:443 -servername api.lab.test </dev/null 2>/dev/null | openssl x509 -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64)"; done
adb -s $S shell settings put global http_proxy 10.0.2.2:18112
./probe.sh rel
adb -s $S shell settings put global http_proxy 10.0.2.2:18110
./probe.sh rel
kill $!
```

![핀 대조 실험 터미널. mitmdump -p 18112 --certs api.lab.test=origin/origin-chain.pem 실행, cat origin/pins.txt 에 origin gUgCOxOv2KkQ1bq+Tja8Ky9kItI6o7Xh0o38mjlDa9g= 와 backup b7EJcPjmkmgJTzspsO8zbUV+la2ucbU0Q1+3eMS8FME=, 리프 공개키 해시는 18110 pq8uSY4VTWIDpwc5YR8A4kvSDoaxuGnRX3dNQeUatDw= 와 18112 gUgCOxOv2KkQ1bq+Tja8Ky9kItI6o7Xh0o38mjlDa9g=, http_proxy 10.0.2.2:18112 로 rel 은 200 hello from lab origin, 10.0.2.2:18110 으로 돌리면 SSLHandshakeException: Pin verification failed](/assets/img/android-mastery/p1c11/11-pin-control.png)

18110이 내민 리프의 해시 `pq8uSY4V…`는 mitmproxy CA 자신의 공개키 해시와 같다. mitmproxy는 호스트마다 리프를 새로 만들지만 키는 CA의 것을 다시 쓴다([certs.py 307행](https://github.com/mitmproxy/mitmproxy/blob/v11.0.2/mitmproxy/certs.py#L307)의 `builder.public_key(cacert.public_key())`). 18112의 리프는 origin 핀 `gUgCOx…`와 같고 rel은 18112를 거치면 200, 18110으로 돌아오면 다시 `Pin verification failed`였다. [checkPins()](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/NetworkSecurityTrustManager.java#118)는 검증된 체인의 인증서마다 SPKI 해시를 구해 핀 목록과 대조하므로(128~145행), 이번처럼 핀이 서버 키일 때는 기기가 어떤 CA를 믿든 그 키의 개인키 없이 만든 리프는 맞출 수 없다. 121행은 핀셋의 expiration이 지나면 검사를 통째로 건너뛴다.

## Frida로 checkPins 하나만 건너뛰기

루팅한 기기에서는 핀 검사 자체를 끌 수 있다. NSC의 핀 판정은 `android.security.net.config.NetworkSecurityTrustManager.checkPins` 한 메서드에서 끝나니, 이 메서드를 아무 일도 하지 않는 함수로 바꿔 rel에 spawn으로 붙였다. CA는 계속 시스템 저장소에 둔다. 체인 검증은 남기고 핀 비교만 뺀다. frida-server 17.17.0(x86_64)은 미리 `/data/local/tmp`에 올려 두었다. Frida 사용법은 [8장](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)에 있다. 훅 스크립트 `unpin.js`는 체인 길이와 앵커 이름만 찍고 돌아간다.

```javascript
// Skip the Network Security Config pin check (android.security.net.config.NetworkSecurityTrustManager.checkPins).
// The chain must still be trusted by a CA source; only the <pin-set> comparison is removed.
Java.perform(() => {
  const X509 = Java.use('java.security.cert.X509Certificate');
  const NSTM = Java.use('android.security.net.config.NetworkSecurityTrustManager');
  NSTM.checkPins.implementation = function (chain) {
    const n = chain.size();
    const anchor = Java.cast(chain.get(n - 1), X509).getSubjectX500Principal().getName();
    console.log(`[unpin] checkPins skipped: ${n} certs, anchor ${anchor}`);
  };
  console.log('[unpin] hooked NetworkSecurityTrustManager.checkPins');
});
```

```bash
adb -s $S shell "/data/local/tmp/frida-server </dev/null >/dev/null 2>&1 &"; sleep 2
cat unpin.js
adb -s $S logcat -c
frida -D $S -f io.seika.intercept.rel -l unpin.js -q -t 8
adb -s $S logcat -d -v tag -s Intercept:I | grep '^I/Intercept'
grep -o 'lab origin answered GET https.*' mitm.log | tail -n 1
```

![Frida unpin 터미널. frida-server 실행, cat unpin.js 로 NetworkSecurityTrustManager.checkPins 를 Java.use 로 잡아 체인 길이와 앵커만 출력하는 12줄 스크립트, frida -D $S -f io.seika.intercept.rel -l unpin.js -q -t 8 출력 Spawned io.seika.intercept.rel. Resuming main thread!, unpin 접두어가 붙은 hooked NetworkSecurityTrustManager.checkPins 와 checkPins skipped: 2 certs, anchor O=mitmproxy,CN=mitmproxy, logcat 의 rel target=33 debuggable=false, 프록시 HTTP @ 10.0.2.2:18110, https://api.lab.test/hello 결과 200 hello from lab origin (https /hello), mitm.log 마지막 줄 for rel](/assets/img/android-mastery/p1c11/10-frida-unpin.png)

spawn한 rel은 `[unpin] checkPins skipped: 2 certs, anchor O=mitmproxy,CN=mitmproxy`를 찍고 200을 받았다. 체인은 리프와 mitmproxy CA 두 장이다. Frida 17은 GumJS 런타임에서 Java 브리지를 뺐지만 frida-tools 14.8.1의 `frida` 명령은 브리지를 함께 싣고 있어서 `-l`로 넘긴 스크립트의 `Java.perform`이 돌았다. `-q -t 8`은 8초 뒤 frida만 빠져나오고 앱은 살려 둔다. objection 같은 범용 unpinning 도구는 쓰지 않았고, 앱이 핀을 NSC가 아닌 곳에서 검사한다면 이 훅으로는 풀리지 않는다.

## Cronet도 NSC를 따른다, 다만 리프 수명을 하나 더 본다

Cronet은 NSC를 읽지 않는다는 말을 종종 보는데 이번 결과는 반대였다. 유저 CA만 있을 때 NSC가 없는 cr은 t33처럼 `ERR_CERT_AUTHORITY_INVALID`로 끊겼고, NSC에서 유저 CA를 켠 crnsc는 200을 받았다. 두 빌드의 차이는 NSC 파일 하나다. mitmweb에 남은 crnsc의 흐름을 보면 Cronet은 시스템 프록시로 나갔고 mitmproxy와 HTTP/2로 붙었다.

![mitmweb 에서 crnsc 흐름의 Request 탭. GET https://api.lab.test/hello HTTP/2.0, x-lab-variant: crnsc, user-agent: io.seika.intercept.crnsc/1 (Linux; U; Android 13; en_US; sdk_gphone64_x86_64; Build/TE1A.240213.009; Cronet/143.0.7445.0), accept-encoding: gzip, deflate, priority: u=1, i, 왼쪽 목록에서 세 번째 https://api.lab.test/hello 가 선택됨](/assets/img/android-mastery/p1c11/09c-mitmweb-cronet-h2.png)

Chromium 소스가 이 동작을 설명한다. [net/features.gni 53행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/features.gni#53)의 `chrome_root_store_optional = is_android && !is_cronet_build` 때문에 Android용 Cronet에는 Chrome Root Store가 들어가지 않고 인증서 검증은 플랫폼에 맡긴다. [X509Util.java](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/X509Util.java#202)는 기본 신뢰 관리자를 `createTrustManager(null)`로 만들고(202행), 그 안에서 `TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())`로 팩토리를 얻는다(266~285행). 앱 프로세스에서 이 팩토리를 내주는 쪽이 NSC다. 앱이 뜰 때 [ActivityThread.java 6711행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/app/ActivityThread.java#6711)이 `NetworkSecurityConfigProvider.install()`을 부르고, [NetworkSecurityConfigProvider.java 31~47행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/NetworkSecurityConfigProvider.java#31)은 `TrustManagerFactory.PKIX`를 NSC의 `RootTrustManagerFactorySpi`로 등록한 보안 제공자를 1순위에 끼운다. X509Util은 받은 신뢰 관리자를 [X509TrustManagerExtensions](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/net/http/X509TrustManagerExtensions.java#53)로 감싸 호스트 이름이 붙은 `checkServerTrusted`를 부르고 이 호출은 [RootTrustManager.java 127~134행](https://android.googlesource.com/platform/frameworks/base/+/d27f9960456403533af0a0d5d9f14cf71c9c8cf6/core/java/android/security/net/config/RootTrustManager.java#127)에서 그 호스트의 도메인 설정으로 넘어간다. 앞에서 본 핀 검사까지 같은 길로 간다. 평문 허용 여부도 [AndroidNetworkLibrary.java 381~386행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/AndroidNetworkLibrary.java#381)에서 `NetworkSecurityPolicy`에 묻는다. cr 프로세스의 logcat에도 다른 앱처럼 `NetworkSecurityConfig: No Network Security Config specified, using platform default`가 찍혀 있었다.

CA를 시스템 저장소로 옮긴 뒤 cr이 낸 `ERR_CERT_VALIDITY_TOO_LONG`은 유저 CA 때의 AUTHORITY_INVALID와 코드부터 다르다(-213). Chromium [cert_verify_proc.cc 557~560행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/cert/cert_verify_proc.cc#557)은 체인이 알려진 루트(known root)로 끝나면 리프의 유효 기간이 너무 긴지 한 번 더 검사한다. 상한은 [HasTooLongValidity() 791~860행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/cert/cert_verify_proc.cc#791)이 정하고 2026년 3월 15일 이후 발급된 인증서는 200일이다(850~854행). Android에서 알려진 루트란 [X509Util.java 383~413행](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/android/java/src/org/chromium/net/X509Util.java#383)의 `isKnownRoot()`가 시스템 키스토어에서 `system:` 별칭으로 찾아내는 루트다. 유저 저장소의 CA는 여기 들지 않아 crnsc는 이 검사를 받지 않았고, 시스템 저장소에 넣은 mitmproxy CA는 해당된다. mitmproxy 11.0.2의 [certs.py](https://github.com/mitmproxy/mitmproxy/blob/v11.0.2/mitmproxy/certs.py#L310)는 리프의 시작 시각을 발급 시점보다 이틀 앞으로, 만료를 발급 시점에서 `CERT_EXPIRY`(34행, 365일) 뒤로 잡는다(310~311행). 실제로 받은 리프도 `notBefore=Oct 13 15:46:34 2026 GMT`, `notAfter=Oct 15 15:46:34 2027 GMT`였다. 시각 옆에 GMT가 붙어 있지만 숫자는 리프를 발급한 순간의 호스트 한국 시각에서 이틀을 뺀 값이라, 같은 순간의 UTC로 적었어야 할 값보다 9시간 크다. 309행이 시간대 없는 `datetime.now()`를 넘기고 cryptography가 그 값을 UTC로 받아들여서 생긴 일로 보인다. 시작 시각을 이틀 당겨 둔 덕에 검증에는 영향이 없었다.

리프 수명만 줄이면 되는지 보려고 mitmproxy의 `CERT_EXPIRY`를 90일로 바꾸는 애드온을 붙인 두 번째 프록시를 18112에 띄웠다. 애드온 `short_leaf.py`는 주석과 import를 빼면 `mitmproxy.certs.CERT_EXPIRY = datetime.timedelta(days=90)` 한 줄이다.

```bash
cat mitm/short_leaf.py
export PYTHONUNBUFFERED=1
mitmdump --listen-host 127.0.0.1 -p 18112 --set confdir=mitm/conf --set connection_strategy=lazy --set allow_hosts=api.lab.test -s mitm/short_leaf.py -s mitm/lab_origin.py > mitm-short.log 2>&1 & sleep 5
for p in 18110 18112; do echo "$p $(openssl s_client -proxy 127.0.0.1:$p -connect api.lab.test:443 -servername api.lab.test </dev/null 2>/dev/null | openssl x509 -noout -startdate -enddate | tr -d '\r' | tr '\n' ' ')"; done
adb -s $S shell settings put global http_proxy 10.0.2.2:18112
./probe.sh cr
adb -s $S shell settings put global http_proxy 10.0.2.2:18110
./probe.sh cr
kill $!
grep -o 'lab origin answered GET https.*' mitm-short.log
```

![Cronet 리프 수명 실험 터미널. cat mitm/short_leaf.py 에 mitmproxy.certs.CERT_EXPIRY = datetime.timedelta(days=90), mitmdump -p 18112 -s mitm/short_leaf.py -s mitm/lab_origin.py 실행, 리프 기간은 18110 notBefore=Oct 13 15:46:34 2026 GMT notAfter=Oct 15 15:46:34 2027 GMT, 18112 notBefore=Oct 13 15:57:42 2026 GMT notAfter=Jan 13 15:57:42 2027 GMT. http_proxy 10.0.2.2:18112 에서 cr 은 200 hello from lab origin (https /hello), 10.0.2.2:18110 으로 돌리자 net::ERR_CERT_VALIDITY_TOO_LONG, InternalErrorCode=-213, mitm-short.log 에 lab origin answered GET https://api.lab.test/hello for cr](/assets/img/android-mastery/p1c11/08b-cronet-short-leaf.png)

90일 리프를 내민 18112로는 cr이 200을 받았고, 18110으로 돌아오자 다시 `ERR_CERT_VALIDITY_TOO_LONG`이었다. Cronet은 플랫폼 신뢰 저장소와 NSC를 그대로 쓰고 그 위에 Chromium의 공개 CA 정책을 하나 더 얹는다. Cronet 앱을 시스템 CA로 볼 때는 리프의 notBefore~notAfter가 200일 안쪽이어야 하고([HasTooLongValidity()](https://chromium.googlesource.com/chromium/src/+/refs/tags/143.0.7445.0/net/cert/cert_verify_proc.cc#821)는 두 시각의 차이를 잰다), mitmproxy는 시작 시각을 이틀 당기므로 `CERT_EXPIRY`는 198일 이하로 둔다. 같은 함수에서 이 상한은 2027년 3월 15일 이후 발급분부터 100일로 내려가니(844~848행) 그때부터는 98일 이하라야 한다. 프록시 로그에서는 이 거절도 앞의 신뢰 실패와 똑같이 `does not trust the proxy's certificate` 줄로 보였고, 이번에는 cr이 연결을 두 개 열어 두 줄이었다.

NSC를 정말로 비켜 가는 쪽은 신뢰 판단을 스스로 하는 코드다. 앱이 자기 `X509TrustManager`나 KeyStore를 넘기는 경우, 네이티브 `.so`에 BoringSSL이나 OpenSSL을 넣어 쓰는 경우, Dart 쪽 TLS를 쓰는 Flutter 앱 같은 경우가 그렇다. 이런 앱을 직접 만들어 보지는 않았지만, Cronet도 빌더의 `addPublicKeyPins`로 준 핀은 네이티브 쪽에서 검사하므로 위의 `checkPins` 훅으로는 풀리지 않을 것이다.

## Android 14부터 앱은 /system 사본을 읽지 않는다

여기까지는 Android 13이다. Android 14부터 루트 CA는 Conscrypt APEX 모듈에 들어가 모듈 업데이트로 바뀔 수 있게 됐다([Conscrypt 문서](https://source.android.com/docs/core/ota/modular-system/conscrypt)). 플랫폼이 읽는 디렉터리도 그에 맞춰 바뀌었다.

![frameworks/base android14-release(6e47c70) 의 SystemCertificateSource.java 28~51행, 강조된 41행 getDirectory(). system.certs.enabled 속성이 "true" 면 ANDROID_ROOT 의 /etc/security/cacerts 를 쓰고, 아니면 /apex/com.android.conscrypt/cacerts 가 존재하고 비어 있지 않을 때 그 디렉터리를 반환, 둘 다 아니면 /etc/security/cacerts 로 돌아감](/assets/img/android-mastery/p1c11/12-src-a14-system-ca-apex.png)

android14-release의 [`getDirectory()`](https://android.googlesource.com/platform/frameworks/base/+/6e47c7075b91983ae501114425ea25e6df7690c8/core/java/android/security/net/config/SystemCertificateSource.java#41)(41~52행)는 `system.certs.enabled` 속성이 `true`가 아니면 `/apex/com.android.conscrypt/cacerts`가 있고 비어 있지 않을 때 그쪽을 쓴다. /system 쪽 디렉터리는 대체 경로로 밀려났다. Android 14와 15 이미지는 띄우지 못했고, Android 16 에뮬레이터에서 t33 하나로 같은 순서를 밟았다. 이 기기에는 t33만 설치하고 `c8750f0d.0`과 `syscert.sh`를 올린 뒤 프록시를 `10.0.2.2:18110`으로 맞춰 두었다.

```bash
adb -s $S shell getprop ro.build.version.release
adb -s $S shell "ls /system/etc/security/cacerts | wc -l; ls /apex/com.android.conscrypt/cacerts | wc -l"
adb -s $S shell sh /data/local/tmp/syscert.sh /data/local/tmp/c8750f0d.0
./probe.sh t33
adb -s $S shell sh /data/local/tmp/syscert.sh /data/local/tmp/c8750f0d.0 /apex/com.android.conscrypt/cacerts
./probe.sh t33
adb -s $S shell 'nsenter --mount=/proc/$(pidof zygote64)/ns/mnt -- sh /data/local/tmp/syscert.sh /data/local/tmp/c8750f0d.0 /apex/com.android.conscrypt/cacerts'
./probe.sh t33
```

![Android 16 에뮬레이터 터미널. getprop ro.build.version.release 가 16, /system/etc/security/cacerts 와 /apex/com.android.conscrypt/cacerts 의 파일 수가 둘 다 149. /system 쪽에 syscert.sh 를 돌린 뒤 t33 은 프록시 10.0.2.2/unresolved:18110 표기와 함께 SSLHandshakeException: java.security.cert.CertPathValidatorException: Trust anchor for certification path not found., APEX 경로에 adb 셸에서 syscert.sh 를 돌려도 같은 실패, nsenter --mount=/proc/$(pidof zygote64)/ns/mnt 로 zygote64 네임스페이스에서 APEX 경로에 넣자 t33 이 200 hello from lab origin (https /hello)](/assets/img/android-mastery/p1c11/14-api36-apex.png)

Android 16에서는 두 디렉터리에 똑같이 149개 파일이 있었다. Android 13에서 통한 대로 /system 쪽에 tmpfs로 CA를 넣으면 t33은 여전히 `Trust anchor for certification path not found`였다. APEX 쪽에 adb 셸에서 같은 방법으로 넣어도 실패했고 zygote64의 마운트 네임스페이스에 들어가 넣었을 때 비로소 200이 나왔다. 앱이 찍는 프록시가 `10.0.2.2/<unresolved>:18110`으로 바뀐 것은 새 버전의 `InetSocketAddress.toString()` 표기 차이다. 직후에 adb 셸, zygote64, t33 프로세스의 `/proc/<pid>/mountinfo`에서 conscrypt와 cacerts 줄만 골라 보니 이유가 보였다.

```text
== adb shell ns
193 49 254:30 / /apex/com.android.conscrypt ro,nodev,noatime - ext4 /dev/block/dm-30 ro,dirsync,seclabel
10890 35 0:304 / /system/etc/security/cacerts rw,relatime shared:39 - tmpfs tmpfs rw,seclabel
10956 193 0:305 / /apex/com.android.conscrypt/cacerts rw,relatime - tmpfs tmpfs rw,seclabel
== zygote64 ns
324 265 254:30 / /apex/com.android.conscrypt ro,nodev,noatime - ext4 /dev/block/dm-30 ro,dirsync,seclabel
10892 238 0:304 / /system/etc/security/cacerts rw,relatime master:39 - tmpfs tmpfs rw,seclabel
11126 324 0:311 / /apex/com.android.conscrypt/cacerts rw,relatime - tmpfs tmpfs rw,seclabel
== app ns (t33)
10475 10416 254:30 / /apex/com.android.conscrypt ro,nodev,noatime - ext4 /dev/block/dm-30 ro,dirsync,seclabel
10476 10475 0:311 / /apex/com.android.conscrypt/cacerts rw,relatime - tmpfs tmpfs rw,seclabel
10542 10387 0:304 / /system/etc/security/cacerts rw,relatime master:39 - tmpfs tmpfs rw,seclabel
```

/system 쪽 tmpfs(장치 번호 `0:304`)는 adb 쪽에서 `shared:39`, zygote와 앱 쪽에서 `master:39`라 앱까지 전파됐지만, 앱이 이제 그 디렉터리를 읽지 않는다. APEX 쪽 마운트에는 전파 표시가 없다. 앱은 zygote에서 fork되므로 zygote 네임스페이스의 마운트만 물려받는다. adb 셸에서 올린 tmpfs(`0:305`)는 adb 네임스페이스에만 남았고, 앱에 보인 것은 zygote에서 올린 tmpfs(`0:311`)였다.

[mitmproxy의 안드로이드 시스템 CA 안내](https://docs.mitmproxy.org/stable/howto/install-system-trusted-ca-android/)에 있는 Magisk 모듈 방식은 부팅 때 인증서를 `/system/etc/security/cacerts/`에 복사한다고 적혀 있다. Magisk는 써 보지 않았지만, 위 결과대로라면 Android 14 이상에서는 그 위치만으로 앱에 닿지 않을 것으로 보인다.

## 앱을 만드는 쪽에서 막고 확인하는 법

개발 중에 프록시를 쓰려고 user 앵커를 넣는다면 `<debug-overrides>` 안에만 둔다. rel처럼 debuggable이 꺼진 빌드에서는 그 블록이 통째로 무시되니 개발용 편의가 릴리스로 새지 않는다. 반대로 릴리스 빌드에 debuggable이 실수로 켜져 있으면 그 앵커가 살아나므로, 배포 APK의 badging 출력에 `application-debuggable`이 없는지, 설치 뒤 `dumpsys package`의 `pkgFlags`에 `DEBUGGABLE`이 없는지 본다. 이번 빌드에서는 둘 다 dbg에만 있었다. `<base-config>`에 `<certificates src="user"/>`가 있으면 그 앱은 기기에 깔린 유저 CA를 무엇이든 믿는다.

핀셋은 시스템 저장소에 CA를 넣는 방법까지 막았다(rel의 `Pin verification failed`). 하지만 루트와 Frida가 있는 기기에서는 rel의 `checkPins` 한 메서드로 꺼졌고, 리패키징하면 핀셋 자체를 지울 수 있다. 그러니 요청을 믿을지는 서버가 따로 판단해야 한다. Play Integrity의 앱 인식 판정 같은 서버 쪽 검증([C48](/posts/android-concept-atlas-c48-play-integrity/))은 이번에 측정하지 않았다. 서버 키를 바꿀 때를 대비해 rel처럼 백업 핀을 함께 둔다([NSC 문서](https://developer.android.com/privacy-and-security/security-config)).

평문은 targetSdk 28 이상이면 기본으로 꺼진다. t33에서 본 것처럼 `http://` 주소로 한 번 요청해 `Cleartext HTTP traffic to ... not permitted`가 나오는지 보면 확인된다. Cronet을 쓰는 앱이라면 시스템 CA 단계에서 리프 수명 때문에 먼저 떨어질 수 있으니 90일짜리 리프로 다시 확인한다.

## 앱과 프록시 로그의 문구로 실패 단계 가르기

| 증상 | 원인 | 처리 |
|---|---|---|
| `127.0.0.1` 프록시인데 `UnknownHostException` | 기기 자신의 루프백이라 프록시에 못 붙고 직접 연결로 넘어갔다 | 에뮬레이터는 `10.0.2.2`, 아니면 `adb reverse` |
| 설정 직후에도 `proxy=[DIRECT]` | 반영이 늦은 적이 있다(원인 미확인) | `settings get global http_proxy`로 값을 확인하고 앱을 다시 띄운다 |
| `Cleartext HTTP traffic ... not permitted` | targetSdk 28 이상의 기본 설정 | HTTPS 주소로 보낸다 |
| `Trust anchor for certification path not found`, Cronet은 `ERR_CERT_AUTHORITY_INVALID` | 앱의 NSC가 그 CA 저장소를 믿지 않는다 | 시스템 저장소에 넣거나 NSC를 고쳐 다시 묶는다 |
| `Pin verification failed` | CA는 믿지만 핀셋과 키가 다르다 | `checkPins` 훅, 또는 리패키징으로 핀셋 삭제 |
| `ERR_CERT_VALIDITY_TOO_LONG` (Cronet) | 시스템 저장소 루트에 notBefore~notAfter가 200일 넘는 리프 | mitmproxy `CERT_EXPIRY`를 198일 이하로(2027-03-15 이후 발급분은 98일 이하) 줄인다 |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 리패키징으로 서명자가 바뀌었다 | 앱 데이터를 포기하고 지운 뒤 설치 |
| 프록시 로그의 `does not trust the proxy's certificate` | 위 실패들이 모두 이 줄로 보인다 | 앱 쪽 오류 문구로 가른다 |
| 파일로 돌린 mitmproxy 로그가 비어 있다 | 파이썬 출력 버퍼 | `PYTHONUNBUFFERED=1` |
| Android 14 이상에서 /system에 넣은 CA가 안 먹힌다 | 플랫폼이 APEX 디렉터리를 읽는다 | zygote 네임스페이스에서 APEX 경로에 넣는다 |

참고 자료: [Network security configuration](https://developer.android.com/privacy-and-security/security-config) · [에뮬레이터 프록시](https://developer.android.com/studio/run/emulator-networking-proxy) · [에뮬레이터 네트워크 주소](https://developer.android.com/studio/run/emulator-networking-address) · [mitmproxy 인증서](https://docs.mitmproxy.org/stable/concepts/certificates/) · [mitmproxy 안드로이드 시스템 CA](https://docs.mitmproxy.org/stable/howto/install-system-trusted-ca-android/) · [Burp 안드로이드 기기 설정](https://portswigger.net/burp/documentation/desktop/mobile/config-android-device) · [Conscrypt 모듈](https://source.android.com/docs/core/ota/modular-system/conscrypt) · [TLS·NSC·pinning(C46)](/posts/android-concept-atlas-c46-tls-nsc-pinning/)

*다음 글: [Network Security Config 분석](/posts/android-lab-p1c12-network-security-config/)*
