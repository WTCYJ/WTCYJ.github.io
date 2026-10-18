---
layout: post
title: "OkHttp/Retrofit·모바일 API 설계"
date: 2026-11-18 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, OkHttp, Retrofit, TLS, CertificatePinning]
excerpt: "OkHttp의 application interceptor와 network interceptor는 이름만 비슷할 뿐 호출 시점이 다르다 — 재시도·리다이렉트마다 도는 건 network 쪽이고, 인증서 핀닝은 leaf 인증서가 아니라 공개키(SPKI) 해시를 고정한다. 이 둘을 헷갈리면 로그도, 보안도 새는 곳을 못 잡는다."
---

앱이 서버와 말을 섞는 거의 모든 순간은 OkHttp를 지난다. Retrofit도, Coil도, Firebase 상당 부분도 바닥에 OkHttp를 깔고 돈다. 그래서 이 스택을 "라이브러리 하나"로 뭉뚱그리면 두 종류의 사고가 난다 — 로깅 인터셉터가 리다이렉트를 못 잡거나, 인증서 핀닝을 걸어 뒀는데도 MITM이 뚫리거나(혹은 반대로 멀쩡한 프록시가 막혀 며칠을 태우거나). 두 사고 모두 **인터셉터 체인의 순서**와 **핀닝이 무엇을 고정하는가**를 몰라서 생긴다.

이 글은 OkHttp 인터셉터 체인의 실제 배치, Retrofit이 인터페이스를 HTTP로 바꾸는 경로, 그리고 그 위에서 TLS·핀닝·Network Security Config가 만드는 신뢰 경계를 AOSP·Square 1차 문서와 최소 자작 앱 관측으로 정리한 기록이다.

> **한 줄 결론**: application interceptor는 호출당 한 번(재시도·캐시 히트를 못 봄), network interceptor는 실제 온-더-와이어마다(리다이렉트·재시도 전부) 돈다. 그리고 인증서 핀닝은 인증서가 아니라 **SPKI(공개키) 해시**를 고정하므로, leaf를 핀하면 키 회전 때 앱이 죽는다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 앱→네트워크 경계다. (1) OkHttp의 인터셉터 체인·디스패처·커넥션 풀, (2) Retrofit이 애노테이션 인터페이스를 동적 프록시로 HTTP 호출로 바꾸고 Converter/CallAdapter로 타입을 잇는 경로, (3) 이 스택 위의 TLS 신뢰 경계 — 시스템/사용자 CA, 인증서 핀닝, Network Security Config를 다룬다. 프레임워크·Binder 내부가 아니라 **앱의 바깥쪽 가장자리**다.

선수 지식은 두 가지다. 앞 1장(Kotlin·coroutine)과 2장(Flow·StateFlow)에서 다룬 `suspend`/구조적 동시성 — Retrofit의 suspend 지원과 취소 전파가 그 위에 선다. 그리고 TLS 인증서 체인(leaf→intermediate→root)과 공개키 개념 — 핀닝이 "무엇을" 고정하는지가 여기서 갈린다. 전체 구조에서 이 장은 App 계층의 출력 단자에 해당한다. 이후 6장(Gradle·공급망)은 이 라이브러리들이 어떤 경로로 앱에 들어오는지를, Atlas의 네트워크·TLS 항목은 프로토콜 자체를 다룬다.

## 핵심 개념 — 인터셉터 체인은 순서가 전부다

OkHttp가 요청 하나를 실행할 때, 내부적으로 인터셉터를 정확히 이 순서로 리스트에 쌓아 체인을 만든다(`RealCall.getResponseWithInterceptorChain()`). `Source-confirmed`

| # | 인터셉터 | 등록 API / 성격 |
|--|--|--|
| 1 | **application interceptors** | `addInterceptor()` — 개발자 등록 |
| 2 | `RetryAndFollowUpInterceptor` | 재시도·리다이렉트 루프 |
| 3 | `BridgeInterceptor` | `Content-Length`·`Host`·`Accept-Encoding: gzip` 등 자동 헤더 |
| 4 | `CacheInterceptor` | HTTP 캐시 단락(short-circuit) |
| 5 | `ConnectInterceptor` | 소켓·TLS 핸드셰이크 |
| 6 | **network interceptors** | `addNetworkInterceptor()` — 개발자 등록 |
| 7 | `CallServerInterceptor` | 실제 바이트 송수신 |

이 배치가 모든 차이를 만든다. application interceptor는 **1번(가장 바깥)** 이라 재시도 루프(2번)와 캐시(4번) *위에* 앉는다. 그래서 (a) 호출당 정확히 한 번 돌고, (b) 리다이렉트/재시도를 별개 호출로 보지 않으며, (c) 캐시가 네트워크 없이 응답을 돌려주면 그 응답까지 본다. 반면 network interceptor는 **6번**, 즉 재시도 루프 *안쪽·*캐시 *아래*라, 리다이렉트/재시도마다 다시 돌고 실제로 전송되는 헤더(BridgeInterceptor가 채운 `Host`·`gzip`)를 보며 `chain.connection()`으로 커넥션에 접근한다. 대신 캐시 히트로 네트워크가 생략되면 **아예 호출되지 않는다**. `Source-confirmed`

> 흔한 함정: "로깅 인터셉터를 `addInterceptor`로 걸었는데 리다이렉트 후 최종 URL만 찍힌다"는 버그의 정체가 이것이다. 리다이렉트 사슬 전부를 보려면 로거를 `addNetworkInterceptor`로 올려야 한다. 반대로 인증 토큰을 붙이는 인터셉터는 재시도마다 중복 붙지 않도록 `addInterceptor` 쪽이 맞다.

디스패처와 풀도 기본값을 알아야 한다. `Dispatcher`의 동시 요청 상한은 `maxRequests=64`, 호스트당 `maxRequestsPerHost=5`, `ConnectionPool`은 유휴 커넥션 5개를 5분 keep-alive로 유지한다. HTTP/2에서는 한 커넥션이 다중 스트림을 멀티플렉싱하므로 호스트당 5 제한의 체감이 달라진다. `Source-confirmed`

Retrofit은 이 위에 얇게 얹힌다. `Retrofit.create(Api::class.java)`는 인터페이스의 **동적 프록시**(`Proxy.newProxyInstance`)를 만들고, 각 메서드의 `@GET`/`@POST`/`@Query`/`@Body` 애노테이션을 파싱해 `okhttp3.Call`로 바꾼다. 반환 타입은 `CallAdapter`가(예: `suspend`, RxJava), 바디는 `Converter`가(Gson/Moshi/kotlinx.serialization) 잇는다. Converter를 등록하지 않으면 `ResponseBody`/`RequestBody` 외에는 변환하지 못한다. `Source-confirmed` `suspend` 함수 네이티브 지원은 Retrofit 2.6.0에서 추가됐고, 취소는 coroutine 취소→`Call.cancel()`로 전파된다. `Reported`

> **[그림 1]** application interceptor와 network interceptor를 각각 건 자작 앱에서, 한 번 리다이렉트되는 자기 서버(10.0.2.2)를 호출했을 때 Logcat에 APP 로그 1회·NET 로그 2회가 찍히는 대조 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 스택의 신뢰 경계는 명확하다: **앱 프로세스는 신뢰, 그 바깥의 네트워크 경로는 불신.** 위협 모델의 주인공은 경로상의 능동적 중간자(rogue Wi-Fi, 악성 CA, 사내 프록시)다. TLS가 기밀·무결·서버 인증을 주지만, TLS의 신뢰뿌리는 "기기가 신뢰하는 CA 집합"이다. 여기서 두 개의 오개념이 사고를 만든다.

첫째, **사용자 CA 기본 불신.** targetSdk 24(Android 7.0) 이상 앱은 기본적으로 *사용자가 설치한* CA를 신뢰하지 않는다. 시스템 CA만 신뢰한다. `Source-confirmed` Burp/mitmproxy CA를 사용자 스토어에 넣고 프록시가 안 붙을 때, 많은 개발자가 "핀닝 때문"이라 단정하지만 실제로는 이 기본값이 원인인 경우가 흔하다. 핀닝을 아직 안 걸었어도 막힌다.

둘째, **핀닝이 무엇을 고정하는가.** OkHttp `CertificatePinner`(그리고 Network Security Config의 `<pin-set>`)는 인증서 전체가 아니라 인증서의 **SPKI(Subject Public Key Info) SHA-256** 을 고정한다. `Source-confirmed` 그래서 같은 키쌍으로 인증서만 갱신하면 핀은 유효하고, 반대로 leaf를 핀했는데 키를 회전하면 앱이 전부 죽는다. 실무 권고는 leaf가 아니라 **intermediate CA 키**를 핀하거나 백업 핀을 함께 두는 것이다.

핀닝을 과대평가하지도 말자. 핀닝은 *다른 체인으로 위장한 중간자*를 막을 뿐, 신뢰뿌리를 통제하는 상대(루팅 기기의 Frida 후킹, 앱 리패키징)나 서버 자체의 배신은 막지 못한다. DoS를 RCE로 부풀리지 않듯, 핀닝을 "만능 방어"로 부풀리면 안 된다.

## 관측 — 핀 불일치는 조용하지 않다

자작 앱을 에뮬레이터(google_apis userdebug)에 올리고, 로컬 개발 서버(`10.0.2.2:8443`, 에뮬레이터의 호스트 루프백 별칭)를 향해 **일부러 틀린 핀**을 걸어 관측한다. 제3자·실서비스는 건드리지 않는다.

### 가설
- **가설 A** — `addInterceptor`(APP)는 리다이렉트 1회 호출에서 1번, `addNetworkInterceptor`(NET)는 2번 찍힌다. `Inferred`
- **가설 B** — SPKI가 틀린 핀을 걸면 TLS는 성공해도 OkHttp가 `SSLPeerUnverifiedException: Certificate pinning failure!`로 끊고, 로그에 peer 체인 해시와 pinned 해시를 나란히 남긴다. `Inferred`

### 절차
1. application/network 인터셉터를 모두 로깅으로 걸고, 한 번 302 리다이렉트하는 자기 엔드포인트를 호출한다.
2. `CertificatePinner`에 실제와 다른 `sha256/...` 핀을 넣고 같은 호스트를 호출한다.
3. Logcat에서 인터셉터 호출 횟수와 예외 메시지를 기록한다.

```kotlin
val client = OkHttpClient.Builder()
    .addInterceptor { c ->                       // application: 호출당 1회
        Log.d("OK", "APP -> ${c.request().url}")
        c.proceed(c.request()).also { Log.d("OK", "APP <- ${it.code}") }
    }
    .addNetworkInterceptor { c ->                 // network: 전송마다
        Log.d("OK", "NET -> ${c.request().url} via ${c.connection()}")
        c.proceed(c.request())
    }
    .certificatePinner(
        CertificatePinner.Builder()
            .add("10.0.2.2", "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=") // 일부러 틀린 핀
            .build()
    )
    .build()
```

`예시 출력(교체)` — 리다이렉트 관측(핀닝 제거 상태):

```
APP -> https://10.0.2.2:8443/a
NET -> https://10.0.2.2:8443/a via Connection{h2}
NET -> https://10.0.2.2:8443/b via Connection{h2}
APP <- 200
```

`예시 출력(교체)` — 틀린 핀으로 인한 종료:

```
javax.net.ssl.SSLPeerUnverifiedException: Certificate pinning failure!
  Peer certificate chain:
    sha256/kR6q... (실측 해시로 교체): CN=10.0.2.2
  Pinned certificates for 10.0.2.2:
    sha256/AAAAAAAA...=
```

APP는 1회, NET는 2회 — 가설 A 예상대로. 그리고 핀 불일치는 조용히 통과하지 않고 peer/pinned 해시를 나란히 던진다 — 가설 B 예상대로. (위 두 블록은 아직 `예시 출력(교체)`이므로 여기까지는 **예상 — 실측 후 확정**이다. [그림 1]/[그림 2]의 실측 Logcat — APP×1·NET×2, `Certificate pinning failure!` — 을 붙인 뒤에야 '확인'으로 확정한다.) 이 메시지에 찍힌 peer 해시가 사실은 올바른 핀 값이므로, 실제 핀을 뽑을 때도 이 출력을 그대로 쓴다.

> **[그림 2]** 틀린 핀으로 호출했을 때 Logcat에 뜬 `Certificate pinning failure!` 스택 — peer 인증서 체인의 `sha256/...`와 pinned `sha256/...`가 나란히 보이는 화면 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 배치되는가

인터셉터 순서가 "설정"이 아니라 **의미**인 이유는, 재시도·캐시·연결이 서로 다른 관심사이기 때문이다. 재시도/리다이렉트는 "논리적 호출 하나"를 여러 물리 요청으로 펼친다. 그래서 그 루프(`RetryAndFollowUpInterceptor`)를 기준으로 위(application)는 "논리적 호출"의 세계, 아래(network)는 "물리적 전송"의 세계로 갈린다. 로깅·인증·재시도 정책은 어느 세계에 속하느냐로 등록 위치가 정해지는 것이지 취향 문제가 아니다. `Source-confirmed`

핀닝이 인증서가 아니라 공개키를 고정하는 것도 우연이 아니다. CA는 같은 키에 대해 인증서를 반복 재발급한다(만료 갱신). 인증서 지문을 핀하면 갱신마다 앱을 재배포해야 하지만, SPKI를 핀하면 키가 유지되는 한 갱신을 견딘다. 즉 "가장 오래 안정적으로 유지되는 식별자"를 고른 설계다. 대가는 명확하다 — 키를 교체하면 그 순간 모든 구버전 앱이 끊긴다. 그래서 백업 핀이 필수다. `Source-confirmed`

## 방어와 회귀 검증

- **핀닝은 Network Security Config로 선언하는 편을 우선 고려한다.** `res/xml/network_security_config.xml`의 `<domain-config>`+`<pin-set expiration="...">`은 OkHttp뿐 아니라 플랫폼 HTTP 스택 전체에 적용되고, `expiration`이 지나면 핀이 만료돼 잠금-아웃을 방지한다. `Source-confirmed` OkHttp `CertificatePinner`는 코드 경로에만 걸리므로, 둘 중 하나만 선택하거나 역할을 나눈다.
- **cleartext는 명시적으로 끈다.** targetSdk 28+ 앱은 평문 HTTP가 기본 차단이지만, `cleartextTrafficPermitted="false"`를 config에 박아 회귀를 막는다. `debug-overrides`(디버그 CA 신뢰)는 `android:debuggable=true`에서만 먹으므로 릴리스로 새지 않는다. `Source-confirmed`
- **회귀 검증**: 백업 핀 없이 leaf만 핀했는지, 프록시 실패의 원인이 핀닝인지 사용자-CA 기본값인지를 구분하는 체크를 CI/코드리뷰에 둔다. 핀 값은 배포 전 서버의 실측 SPKI로 재계산해 하드코딩 오타를 잡는다.

## 정리

- application interceptor = 논리적 호출당 1회(재시도·캐시 히트 못 봄), network interceptor = 물리적 전송마다(리다이렉트·재시도 전부, 커넥션 접근). 로거·인증기의 등록 위치가 여기서 갈린다.
- 인증서 핀닝은 leaf 인증서가 아니라 SPKI(공개키) SHA-256을 고정한다 — 백업 핀 없이 leaf를 핀하면 키 회전 때 앱이 죽는다.
- targetSdk 24+는 사용자 CA를 기본 불신한다 — 프록시가 안 붙는다고 무조건 "핀닝 탓"이 아니다.
- Retrofit은 얇은 프록시일 뿐, 실제 신뢰·재시도·연결은 전부 OkHttp 체인에서 일어난다.

**점검 질문** — (1) 리다이렉트 사슬 전부를 로깅하려면 인터셉터를 어느 API로 등록해야 하며 왜인가? (2) leaf 인증서 지문 대신 SPKI를 핀하는 이유와 그 대가는? (3) Burp 프록시가 안 붙을 때, 핀닝과 사용자-CA 기본 불신을 어떻게 구분하는가?

**참고** — [OkHttp Interceptors](https://square.github.io/okhttp/features/interceptors/) · [OkHttp HTTPS/CertificatePinner](https://square.github.io/okhttp/features/https/) · [Retrofit](https://square.github.io/retrofit/) · [Android Network Security Config](https://developer.android.com/privacy-and-security/security-config)

*다음 글: [Gradle·multi-module·공급망](/posts/android-expert-p2c07/).*
