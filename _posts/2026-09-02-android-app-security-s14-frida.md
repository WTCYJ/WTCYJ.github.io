---
layout: post
title: "[Android 앱 보안 S14] 동적 분석과 Frida"
date: 2026-09-02 22:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Frida, 동적분석, 후킹, 인증우회, InsecureShop, 학습기록]
excerpt: "정적으로 읽은 것을 이번엔 살아 있는 프로세스에서 확인했습니다. Frida로 InsecureShop에 붙어, 로그인 검증 메서드가 받는 아이디·비밀번호와 그 반환값을 그대로 관측했습니다. 그리고 같은 훅으로 반환을 true로 바꾸자, 틀린 비밀번호로도 로그인이 통과했습니다. 관측과 보안 경계 무력화는 다른 일이라, 그 경계를 분명히 그어 둡니다."
---

> 지금까지 코드를 읽고 화면을 두드렸다면, 이번엔 실행 중인 앱 안으로 들어갑니다. Frida로 메서드가 실제로 무엇을 주고받는지 보고, 그 판정을 바꿔 봅니다 — 내 소유 앱에서만.

정적 분석은 "이렇게 동작할 것"을 읽는 것이고, 동적 분석은 "실제로 이렇게 동작한다"를 보는 것입니다. Frida는 실행 중인 앱의 메서드에 끼어들어 인자·반환값을 관측하고, 필요하면 바꾸기도 합니다. InsecureShop의 로그인 검증에 붙어, 먼저 관측만 하고 그다음 판정을 뒤집어 봤습니다. 두 가지는 성격이 다른 일이라, 글에서 그 선을 분명히 긋습니다.

---

## 실습 목표

- frida-server를 올리고 내 소유 앱 프로세스에 붙는다.
- 로그인 검증 메서드의 인자와 반환값을 관측한다.
- 같은 훅으로 반환을 바꿔, 클라이언트 측 인증이 무력화되는지 확인한다(내 소유 앱).
- 관측과 보안 경계 무력화의 차이를 정리한다.

---

## 윤리적 범위와 허가 조건

Frida 후킹, 특히 판정을 바꾸는 우회 코드는 오직 내가 소유한 교육용 InsecureShop의 디버그 빌드에 대해서만, `aas-api33` 에뮬레이터 안에서만 했습니다. 관측(로그 남기기)과 보안 경계 무력화(반환 바꾸기)는 성격이 다르며, 후자는 학습을 위한 자기 앱 검증에 한정합니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 대상 앱: `com.insecureshop` (S02)
- frida-server 17.17.0(디바이스 `/data/local/tmp/frida-server`), 호스트 `frida` 17.17.0
- 정적 근거: S04에서 확인한 `Util.verifyUserNamePassword`

---

## 위협 모델 — 실행 중에 무엇을 보고 바꿀 수 있나

- 로그인 검증이 받는 값과 돌려주는 값을 관측할 수 있는가?
- 그 반환을 바꿔 클라이언트 측 판정을 뒤집을 수 있는가?
- 이건 관측인가, 무력화인가?

---

## 재현 절차

### 1. frida-server 기동

디바이스에 아키텍처에 맞는 frida-server를 올리고 실행합니다.

```console
$ adb push frida-server-17.17.0-android-x86_64 /data/local/tmp/frida-server
$ adb shell chmod 755 /data/local/tmp/frida-server
$ adb shell "nohup /data/local/tmp/frida-server >/dev/null 2>&1 &"
$ frida-ps -U | grep InsecureShop
8462  InsecureShop
```

### 2. 관측 — 검증 메서드가 받는 값

S04에서 로그인 검증이 `Util.verifyUserNamePassword(username, password)`임을 봤습니다. 여기에 훅을 걸어 인자와 반환값을 로그로 남깁니다(값을 바꾸지 않는 관측).

```javascript
Java.perform(function () {
    var Util = Java.use('com.insecureshop.util.Util');
    Util.verifyUserNamePassword.implementation = function (u, p) {
        var real = this.verifyUserNamePassword(u, p);       // 원래 판정
        send('[OBSERVE] verifyUserNamePassword("' + u + '", "' + p + '") -> ' + real);
        return real;                                        // 그대로 돌려줌 (관측만)
    };
});
```

이 상태로 아이디 `shopuser`, 틀린 비밀번호 `WRONGPASS999`를 넣고 로그인하면, 훅이 실제 값을 그대로 보여 줍니다.

```console
[OBSERVE] verifyUserNamePassword(username="shopuser", password="WRONGPASS999") -> false
```

앱이 받은 값이 무엇인지, 검증이 어떻게 판정했는지(틀렸으니 false)가 그대로 드러납니다. 여기까지는 아무것도 바꾸지 않은 관측입니다.

### 3. 무력화 — 반환을 바꾸기

이제 같은 훅에서 반환을 `true`로 바꿉니다. 판정을 뒤집는 것이라, 성격이 관측과 다릅니다.

```javascript
Util.verifyUserNamePassword.implementation = function (u, p) {
    var real = this.verifyUserNamePassword(u, p);
    send('[OBSERVE] ... -> ' + real);
    send('[BYPASS]  forcing return = true');
    return true;    // 무조건 통과
};
```

같은 틀린 비밀번호로 다시 로그인했습니다.

```console
[OBSERVE] verifyUserNamePassword(username="shopuser", password="WRONGPASS999") -> false
[BYPASS]  forcing return = true  (client-side auth neutralized on owned app)
```

검증은 여전히 false를 냈지만(틀린 비밀번호가 맞습니다), 훅이 true로 바꿔 앱은 통과로 처리했습니다. 화면은 로그인 화면을 지나 상품 목록으로 넘어갔습니다.

---

## 스크린샷

틀린 비밀번호(`WRONGPASS999`)를 넣었는데도, Frida가 검증 반환을 뒤집어 로그인이 통과한 결과 화면입니다. 인증 판정이 클라이언트에만 있으면 이렇게 실행 중에 뒤집힙니다.

![Frida로 verifyUserNamePassword 반환을 true로 강제한 뒤, 틀린 비밀번호로 로그인이 통과해 열린 InsecureShop 상품 목록 화면](/assets/img/android-app-security/S14/01-frida-bypass.png)

Frida 훅 스크립트와 관측·우회 로그는 `assets/evidence/android-app-security/S14/`에 남겼습니다.

---

## JNI 관측에 대해

Frida는 네이티브 계층도 관측합니다. `System.loadLibrary`/`JNI_OnLoad`에 붙어 어떤 `.so`가 언제 로드되는지, `RegisterNatives`로 어떤 자바 메서드가 네이티브에 연결되는지 볼 수 있습니다. 다만 InsecureShop은 네이티브 라이브러리가 없어(S02) 이 앱에선 관측할 JNI 로딩이 없었습니다. 네이티브가 있는 앱을 다루는 S16에서 그 계층을 따로 봅니다.

---

## 관측 결과

- Frida로 `com.insecureshop` 프로세스에 붙어 `verifyUserNamePassword`의 인자·반환을 관측했다(`shopuser`/`WRONGPASS999` -> false).
- 같은 훅에서 반환을 `true`로 바꾸자 틀린 비밀번호로도 로그인이 통과했다(상품 목록 진입).
- InsecureShop엔 네이티브 라이브러리가 없어 JNI 로딩 관측 대상은 없었다.

---

## 근본 원인과 보안 영향

- 인증 판정이 클라이언트(앱 안 `verifyUserNamePassword`)에만 있으면, 실행 중에 그 판정을 뒤집을 수 있습니다. 하드코딩된 자격증명(S04)에 더해, 판정 자체가 로컬이라는 게 이중의 문제입니다.
- Frida 같은 도구는 관측에도, 무력화에도 쓰입니다. 방어 관점에서 중요한 건 "후킹을 막는 것"이 아니라(그건 경쟁일 뿐입니다) 애초에 신뢰를 클라이언트에 두지 않는 것입니다.

## 수정 방법

- 인증 판정을 서버로 옮긴다. 앱은 자격증명을 서버에 보내 검증받고, 결과 토큰(S11)만 다룬다. 클라이언트가 판정하지 않으면 클라이언트에서 뒤집을 것도 없다.
- 하드코딩된 자격증명·비교 로직을 앱에서 제거한다(S04).
- 무결성·탐지(S15·S17)는 보조 수단일 뿐, 근본 방어는 서버 신뢰다.

---

## 재검증

같은 틀린 비밀번호로, 관측만 했을 때는 로그인 화면에 머물렀고(검증 false), 반환을 true로 바꾼 뒤엔 상품 목록으로 넘어갔습니다. 훅의 개입 여부에 따라 결과가 갈리는 것으로, 판정이 클라이언트에 있었다는 게 확인됩니다. 관측 로그의 `-> false`와 화면의 로그인 성공이 그 대비를 그대로 보여 줍니다.

---

## 참고 자료

- Frida — Java 계층 후킹, `Java.use`/`implementation`
- Frida — 네이티브 후킹과 JNI 관측
- OWASP MASVS — Resilience(동적 분석 저항)와 서버 측 신뢰
