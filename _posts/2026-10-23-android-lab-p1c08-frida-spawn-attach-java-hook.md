---
layout: post
title: "Frida spawn/attach와 Java hook — 언제 붙고 어떻게 후킹되나"
date: 2026-10-23 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Frida, DynamicAnalysis, JavaHook]
excerpt: "동적 분석의 두 축은 언제 붙느냐(spawn vs attach)와 어떻게 후킹되느냐(ART deopt)다. spawn(-f)은 앱 코드가 돌기 전에 게이트하니 초기 init·JNI_OnLoad·패커 언팩을 잡고, attach는 이미 지난 코드를 못 본다. Java 후킹은 ArtMethod 엔트리포인트 스왑만으론 인라인된 호출부를 놓쳐, Frida는 deopt로 인터프리터로 되돌려 잡는다(C16)."
---

정적 분석(4·5장)이 막히는 지점 — 패커·리플렉션·런타임 로직 — 을 Frida는 살아 있는 프로세스 안에서 관측한다. 동적 분석의 핵심 두 질문은 "언제 붙느냐"와 "어떻게 후킹되느냐"다. spawn은 앱 코드 전에 게이트하고, Java 후킹은 ART의 인라인 때문에 엔트리포인트 스왑만으론 부족해 deopt에 기댄다. 이 글은 Frida를 정확한 API로 붙이고 Java 메서드를 후킹하는 법과, 그 두 메커니즘의 정확한 동작을 정리한 기록이다.

> **한 줄 결론**: 초기 코드(패커 언팩·안티-Frida)를 잡으려면 `spawn(-f)`이어야 한다. Java 후킹은 인라인 때문에 엔트리포인트 스왑만으론 부족하고, Frida가 **deopt**로 인터프리터에서 후킹 지점을 통과시킨다(C16).

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Frida spawn/attach와 Java 메서드 후킹을 다룬다. 선수 개념은 [연구 환경(1장)](/posts/android-lab-p1c01-research-environment/)의 root/userdebug 이미지, [jadx(4장)](/posts/android-lab-p1c04-jadx-static-analysis/)의 타깃 특정, [JIT/AOT 분석차(C16)](/posts/android-concept-atlas-c16-jit-aot-analysis/)의 "deopt가 모드 독립성의 보증"이다.

## 핵심 개념 — spawn/attach와 ART 후킹

- **frida-server**: 기기 arch + 호스트 `frida` 버전 **양쪽 일치**, `/data/local/tmp/`에 push·`chmod 755`·root 실행(userdebug/에뮬). 비-root는 **frida-gadget**(APK 리패키징) 별도 경로. `Source-confirmed`
- **spawn vs attach**: `frida -U -f com.pkg -l s.js`는 프로세스를 **정지 상태로 생성**해 스크립트/후킹을 설치한 뒤 재개 → 앱 코드 전에. `--no-pause`는 그 재개를 자동화할 뿐(게이팅은 `-f`의 성질). `frida -U -n <name>` / `-p <pid>`는 이미 도는 프로세스에 붙어 **초기 코드는 못 본다**. `frida-ps -Uai`로 식별자·pid. `Source-confirmed`
- **Java 후킹**: `Java.perform(fn)`(VM 부착 스레드) 안에서 `Java.use('com.example.Foo')`로 래퍼 → `Foo.method.implementation = function(a, b){ return this.method(a, b); }`(**인자는 개별 위치 파라미터**, `this.method(...)`가 원본 호출). 오버로드는 `Foo.bar.overload('int','java.lang.String')`(**Java 정규 타입명**, JVM 디스크립터 아님). `Java.choose(cls,{onMatch,onComplete})`로 힙의 살아있는 인스턴스, `Java.cast(handle, Klass)`. `Source-confirmed`
- **deopt(C16)**: 후킹은 `ArtMethod` 엔트리포인트를 조작하지만, AOT/JIT가 콜리를 **인라인**하면 그 호출부는 엔트리포인트를 안 읽는다 → frida-java-bridge가 **deopt**(JDWP와 같은 기제)로 인터프리터에서 후킹 지점을 통과시킨다. `Source-confirmed`

**신뢰 경계와 위협 모델.** Frida 런타임은 **타깃 주소공간 안**에 주입되므로 실제 객체·메모리에 닿지만, 안티-Frida(maps 스캔·스레드명)가 탐지할 수 있다. 자작/교육용 앱에서만.

> **[그림 1]** `frida-ps -Uai`로 앱 식별자를 확인하고 `frida -U -f ... --no-pause`로 spawn하는 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱의 로컬 로직 게이트(예: `checkLicense()Z`)를 후킹해 반환을 관측/변경(교육용). 상용 앱 안티-Frida 우회는 하지 않는다.

## 실습 절차와 관측

### 가설
spawn으로 `Application.onCreate` 전에 후킹하면 초기 로그가 잡히고, attach로는 그 부분이 비어 있다. `Inferred`

### 절차
1. frida-server를 실행하고 버전을 대조한다.
2. `Java.use`로 타깃 클래스를 래핑, `.implementation`으로 인자·반환을 로깅.
3. spawn과 attach를 각각 시도해 초기 코드 관측 차이를 기록.
4. 인라인 가능성이 높은 작은 메서드에서 후킹이 걸리는지(deopt) 확인.
5. `Java.choose`로 키를 쥔 인스턴스를 열거(자작 복호기).

```javascript
// hook.js — spawn으로 로드
Java.perform(function () {
  var Gate = Java.use('com.example.Gate');
  Gate.checkLicense.implementation = function () {
    console.log('[hook] checkLicense() -> forcing true');
    return true;                      // 원본 대신 강제 (자작 앱)
  };
});
```
```bash
adb shell "su -c /data/local/tmp/fs &"
frida -U -f com.example.app -l hook.js --no-pause
```

> **[그림 2]** 같은 앱에 spawn(초기 로그 잡힘)과 attach(초기 로그 놓침)를 대조한 콘솔 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[Java.perform] checkLicense() called -> returning true (hooked)
[spawn] Application.onCreate observed  |  [attach] (missed)
```

## Root Cause — 왜 이렇게 되는가

attach가 초기 코드를 못 보는 것은 구조적이다 — 그 코드는 이미 실행됐다. deopt가 필요한 것은 ART가 콜리를 인라인해 엔트리포인트를 우회하기 때문이다(C16). Android 앱은 Zygote fork(C12)로 생성되고, Frida는 그 fork를 계측해 자식에서 앱 클래스·정적 초기화자 전에 후킹을 설치하므로 spawn이 초기 anti-Frida·패커 언팩을 잡을 수 있다.

## 방어와 회귀 검증

- (개발자) 클라이언트 로직을 신뢰하지 말 것(서버 인가·C48 서버검증). 후킹 스크립트가 원본 반환을 보존(`return this.method`)하는지 확인해 로직 변형을 방지.
- (연구자) 안티-Frida 우회는 자작/허가 대상만.

**흔한 실패와 처리.** `unable to connect to remote frida-server` → arch/버전/실행 여부. `use()` throws → `Java.perform` 밖에서 호출. hook 무발동 → 인라인이면 deopt 확인, 또는 spawn 필요.

## 버전 차이와 한계

- frida-server와 호스트 `frida`는 **같은 버전**이어야 한다. SELinux가 `/data/local/tmp` 실행을 막으면 userdebug/에뮬로.
- root/userdebug 필요. production 기기는 gadget 경로(리패키징).

## 정리

- 초기 코드는 spawn(-f), 이후 코드는 attach.
- Java 후킹은 인자가 위치 파라미터, 오버로드는 Java 정규 타입명.
- 인라인 때문에 엔트리포인트 스왑만으론 부족 → deopt가 보증.

**점검 질문** — (1) 패커 언팩을 잡으려면 spawn과 attach 중 무엇이며 왜? (2) `.overload`의 인자는 `'I'`인가 `'int'`인가? (3) 엔트리포인트 스왑만으로 후킹이 안 걸리는 경우와 해결은?

**참고** — [Frida JS API](https://frida.re/docs/javascript-api) · [Frida Android](https://frida.re/docs/android) · [C12 Zygote](/posts/android-concept-atlas-c12-zygote/) · [C16 JIT/AOT](/posts/android-concept-atlas-c16-jit-aot-analysis/)

*다음 글: [ClassLoader·동적 로딩 관찰](/posts/android-lab-p1c09-classloader-dynamic-loading/).*
