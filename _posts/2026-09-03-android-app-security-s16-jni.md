---
layout: post
title: "[Android 앱 보안 S16] JNI와 네이티브 라이브러리 분석"
date: 2026-09-03 09:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, JNI, 네이티브, readelf, RELRO, NX, PIE, RegisterNatives, 학습기록]
excerpt: "코드를 네이티브(.so)로 내리면 분석이 어려워진다고들 하지만, 어디까지 그런지 직접 확인했습니다. NDK로 JNI 라이브러리를 하나 만들어, 이름 규칙으로 연결한 메서드와 JNI_OnLoad의 RegisterNatives로 연결한 메서드를 심볼 테이블에서 비교했습니다. 그리고 readelf로 PIE·RELRO·NX·카나리 같은 보호 수준을 읽고, 네이티브에 넣은 비밀 문자열이 그대로 strings로 나오는 것도 봤습니다."
---

> S14에서 Frida가 네이티브 로딩(JNI_OnLoad)도 관측한다고 했습니다. 이번엔 그 네이티브 계층을 직접 만들어, .so를 어떻게 읽는지 봅니다. InsecureShop은 네이티브가 없어(S02) 내가 만든 안전한 JNI 샘플로 진행합니다.

앱 로직이나 비밀을 네이티브(.so)로 내리는 이유는 분석을 조금 더 어렵게 만들기 위해서입니다. 그런데 "어렵게"가 "불가능"은 아닙니다. JNI 메서드가 어떻게 연결됐느냐에 따라 심볼로 바로 보이기도 하고 숨기도 하며, 네이티브 안 문자열은 그냥 `strings`로 나옵니다. NDK로 작은 JNI 라이브러리를 만들어 이 경계를 직접 확인했습니다.

---

## 실습 목표

- NDK로 JNI 네이티브 라이브러리를 빌드하고 앱에서 로드한다.
- 이름 규칙 연결과 `RegisterNatives` 연결이 심볼 테이블에서 어떻게 다른지 본다.
- `readelf`로 PIE·RELRO·NX·카나리 보호 수준을 읽는다.
- 네이티브에 넣은 비밀이 정말 숨는지 확인한다.

---

## 윤리적 범위와 허가 조건

이번 대상은 내가 직접 작성한 JNI 샘플(`com.aas.jni`, `libaasnative.so`)입니다. 모든 빌드·실행은 `aas-api33` 에뮬레이터와 내 호스트에서만 했습니다.

---

## 환경 및 도구 버전

- NDK r27(27.3.13750724)의 `clang`으로 x86_64 `.so` 빌드, `llvm-readelf`로 분석
- 대상 기기: `aas-api33` (S01)
- 앱 빌드: S05 툴체인(+ `.so`를 `lib/x86_64/`에 포함)

---

## 위협 모델 — 네이티브는 무엇을 숨기나

- JNI 메서드가 심볼로 노출되는가, 숨는가?
- 네이티브 안 비밀(문자열·로직)이 정말 안 보이는가?
- 이 `.so`는 어떤 익스플로잇 완화(PIE/RELRO/NX/카나리)를 갖췄나?

---

## 재현 절차

### 1. JNI 라이브러리 (두 가지 연결 방식)

샘플 `.so`에 두 종류의 네이티브 메서드를 넣었습니다. 하나는 이름 규칙(`Java_<pkg>_<class>_<method>`)으로 연결하고, 하나는 `JNI_OnLoad`에서 `RegisterNatives`로 동적 연결합니다.

```c
// 이름 규칙으로 연결 — 이름이 곧 심볼
JNIEXPORT jstring JNICALL
Java_com_aas_jni_MainActivity_getNativeSecret(JNIEnv* env, jobject o) {
    return (*env)->NewStringUTF(env, "N4T1V3_S3CR3T_x9");
}
// RegisterNatives 로 연결 — static 함수, 이름 규칙 안 씀
static jstring native_flag(JNIEnv* env, jobject o) {
    return (*env)->NewStringUTF(env, "flag{registered_via_JNI_OnLoad}");
}
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* r) {
    ... RegisterNatives(env, clazz, {{"nativeFlag","()Ljava/lang/String;", native_flag}}, 1);
    return JNI_VERSION_1_6;
}
```

앱은 `System.loadLibrary("aasnative")`로 로드하고 두 네이티브 메서드를 부릅니다. 실행하면 둘 다 값을 돌려줍니다(스크린샷). `JNI_OnLoad`가 도는 것도 logcat으로 확인됩니다.

```console
$ adb logcat -s aasjni
I aasjni  : JNI_OnLoad: RegisterNatives(nativeFlag)
```

### 2. 심볼 테이블 — 무엇이 보이나

`readelf`로 내보낸 심볼을 봤습니다.

```console
$ llvm-readelf --dyn-syms libaasnative.so
  ... FUNC GLOBAL ... Java_com_aas_jni_MainActivity_getNativeSecret
  ... FUNC GLOBAL ... JNI_OnLoad
```

이름 규칙 메서드(`getNativeSecret`)와 `JNI_OnLoad`는 심볼로 그대로 보입니다. 그런데 `RegisterNatives`로 연결한 `nativeFlag`(내부 `native_flag`)는 심볼 테이블에 없습니다. static 함수라 내보내지 않았고, 자바 메서드와의 연결은 `JNI_OnLoad` 코드 안에서만 이뤄지기 때문입니다. 그래서 이런 메서드는 심볼만 봐서는 못 찾고, `JNI_OnLoad`를 디스어셈블(Ghidra·objdump)해서 `RegisterNatives` 호출과 함수 포인터를 따라가야 정체가 드러납니다. 네이티브 분석에서 "숨은 메서드"를 찾는 게 이 지점입니다.

### 3. 익스플로잇 완화 수준

`.so`가 어떤 보호를 갖췄는지 읽었습니다.

```console
$ llvm-readelf -h  libaasnative.so   | grep Type
  Type: DYN (Shared object)                 -> PIE (ASLR 가능)
$ llvm-readelf -l  libaasnative.so
  GNU_RELRO ...                             -> RELRO 있음
  GNU_STACK ... RW                          -> NX (스택 실행 불가)
$ llvm-readelf -d  libaasnative.so   | grep -i now
  FLAGS  BIND_NOW / FLAGS_1 NOW             -> Full RELRO
$ llvm-readelf --syms libaasnative.so | grep stack_chk
  (없음)                                     -> 스택 카나리 없음
```

PIE, Full RELRO(BIND_NOW), NX는 갖췄지만 스택 카나리는 없습니다(빌드에 `-fstack-protector`를 안 넣은 결과). 네이티브를 다룰 땐 이런 완화 수준을 먼저 읽는 게 순서입니다.

### 4. 네이티브는 문자열을 숨기지 않는다

정작 "네이티브에 넣으면 숨겠지" 싶은 비밀 문자열은, 그냥 `.so` 안에 평문으로 있습니다.

```console
$ strings libaasnative.so | grep -E 'N4T1V3|flag\{'
N4T1V3_S3CR3T_x9
flag{registered_via_JNI_OnLoad}
```

이름 규칙 메서드의 반환값도, RegisterNatives 메서드의 반환값도 그대로 나옵니다. 네이티브로 내리는 건 로직 리버싱을 조금 늦출 뿐, 평문 비밀을 숨기지는 못합니다.

---

## 스크린샷

JNI 샘플 앱의 실행 화면입니다. 이름 규칙으로 연결한 `getNativeSecret()`과 `RegisterNatives`로 연결한 `nativeFlag()`가 각각 네이티브의 값을 돌려줬습니다.

![JniDemo 앱 실행 화면 — System.loadLibrary("aasnative")로 JNI_OnLoad 실행, getNativeSecret()[이름규칙 연결] = N4T1V3_S3CR3T_x9, nativeFlag()[RegisterNatives] = flag{registered_via_JNI_OnLoad}](/assets/img/android-app-security/S16/01-jni.png)

네이티브 소스와 readelf 분석 결과는 `assets/evidence/android-app-security/S16/`에 남겼습니다.

---

## 관측 결과

- 이름 규칙 메서드(`getNativeSecret`)와 `JNI_OnLoad`는 심볼로 노출된다.
- `RegisterNatives`로 연결한 `nativeFlag`는 심볼에 없어, `JNI_OnLoad`를 디스어셈블해야 찾을 수 있다.
- `.so`는 PIE·Full RELRO(BIND_NOW)·NX를 갖췄으나 스택 카나리는 없다.
- 네이티브 안 비밀 문자열은 `strings`로 그대로 추출된다.

---

## 근본 원인과 보안 영향

- 네이티브로 코드를 내리면 자바 디컴파일보다 분석이 번거로워지지만, 심볼·문자열·완화 수준은 정적 도구로 바로 읽힙니다. 특히 이름 규칙으로 연결한 메서드는 심볼로 그대로 드러납니다.
- `RegisterNatives`는 메서드를 심볼에서 숨겨 분석을 늦추지만, `JNI_OnLoad` 리버싱으로 복구됩니다. 은닉이지 보호가 아닙니다.
- 카나리 같은 완화가 빠지면, 네이티브에 메모리 버그가 있을 때 악용이 쉬워집니다. 네이티브를 쓴다면 완화 옵션을 켜는 게 기본입니다.

## 수정 방법 / 권고

- 비밀은 네이티브에도 평문으로 두지 않는다. 서버에서 받거나 Keystore(S05)로 보호한다.
- 네이티브 빌드에 `-fstack-protector-strong`, Full RELRO, PIE, NX를 켠다(대개 NDK 기본이지만 카나리는 명시 필요).
- 민감 로직을 네이티브로 내리는 것은 난독화의 일종일 뿐, 서버 신뢰를 대체하지 못한다(S14·S15와 같은 결론).

---

## 재검증

같은 `.so`에서, 이름 규칙 메서드는 심볼로 보였고 RegisterNatives 메서드는 심볼에 없었습니다. 보호 수준(PIE/RELRO/NX 있음, 카나리 없음)과 평문 비밀 추출도 readelf·strings로 확인했습니다. 앱 실행에서 두 메서드가 각각 값을 돌려준 것과, JNI_OnLoad가 logcat에 남긴 것으로 연결 방식 두 가지가 다 동작함을 교차 확인했습니다.

---

## 참고 자료

- Android NDK — JNI, `RegisterNatives`, `JNI_OnLoad`
- `llvm-readelf` / `readelf` — ELF 심볼·세그먼트·완화 확인
- Ghidra — 네이티브 디스어셈블과 `JNI_OnLoad` 분석
