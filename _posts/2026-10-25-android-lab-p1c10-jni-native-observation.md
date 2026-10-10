---
layout: post
title: "JNI·native 함수 동적 관찰 — 스트립된 심볼도 RegisterNatives로 매핑하기"
date: 2026-10-25 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, JNI, Frida, NativeHook, RegisterNatives]
excerpt: "네이티브 로직은 DEX 밖이라 정적 jadx로 안 보인다. Frida의 Interceptor.attach로 .so 함수의 onEnter/onLeave를 잡고, 특히 RegisterNatives를 후킹하면 심볼이 스트립된 앱에서도 'Java native 메서드 이름 ↔ C 함수 주소' 매핑이 드러난다. 단 RegisterNatives는 libart.so에서 평문 export가 아니라 C++ 맹글 심볼이라 enumerateSymbols나 JNIEnv 테이블 슬롯으로 찾아야 한다."
---

DEX 정적 분석(4장)이 못 보는 네이티브 표면을 동적으로 관찰한다. Frida의 네이티브 API로 `.so` 함수를 후킹하고, 특히 `RegisterNatives`를 후킹하면 심볼이 스트립됐어도 Java native 메서드와 C 함수 주소의 매핑이 드러난다. 이 글은 네이티브 함수·JNI 경계를 Frida로 후킹해 스트립된 심볼까지 매핑하는 방법을 정리한 기록이다. 이는 정적 native RE([21장 Ghidra](/posts/android-lab-p1c21-ghidra-rizin-native/))의 동적 짝이다.

> **한 줄 결론**: `Interceptor.attach`로 `.so` 함수의 onEnter/onLeave를 잡고, `RegisterNatives` 후킹으로 스트립된 심볼의 이름↔주소를 복원한다. 단 `RegisterNatives`는 libart.so에 평문 export가 아니라 C++ 맹글 심볼이라 `enumerateSymbols`나 JNIEnv 테이블 슬롯으로 접근한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Frida 네이티브 API로 JNI 경계를 관찰한다. 선수 개념은 [Frida(8장)](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)의 네이티브 API 짝, [ELF·linker(C33)](/posts/android-concept-atlas-c33-elf-linker-plt-got/)의 `.so`·심볼, [HexTree Android](/posts/hextree-android-track/)의 JNI 경계다.

## 핵심 개념 — 네이티브 후킹과 RegisterNatives

- **네이티브 후킹**: `Module.getExportByName('libfoo.so','func')`/`Module.findExportByName`, `Interceptor.attach(addr, {onEnter(args){...}, onLeave(retval){...}})`, `Interceptor.replace`, `NativeFunction`/`NativeCallback`, `Memory.readByteArray`/`hexdump`. `Source-confirmed`
- **JNI_OnLoad**: `System.loadLibrary` → `JNI_OnLoad` 호출(후킹으로 lib 초기화 관찰). `Source-confirmed`
- **RegisterNatives**: lib이 Java native 메서드를 C 함수 포인터로 매핑하는 지점 — 후킹하면 **스트립된 심볼에서도 이름↔주소**가 드러난다. 단 `libart.so`에 **평문 export가 아니라 C++ 맹글 심볼**(`art::JNI<...>::RegisterNatives`)이라 `Module.enumerateSymbols('libart.so')` 필터 또는 **JNIEnv 함수테이블 슬롯(215)**으로 접근. `JNINativeMethod` = `{const char* name; const char* signature; void* fnPtr}`, stride 3×pointerSize(arm64 24B). `Source-confirmed`
- **JNI 인자**: `onEnter`의 `args[0]=JNIEnv*`(= 함수테이블 포인터에의 포인터), `args[1]=jobject`(인스턴스)/`jclass`(static), 이후 Java 인자. `Source-confirmed`

**신뢰 경계와 위협 모델.** 네이티브 인라인 후크는 실제 컴파일된 주소를 노린다(C16). 자작/허가 대상만, 무기화 금지.

> **[그림 1]** `RegisterNatives` 후킹으로 스트립된 lib의 `nativeCheck`↔주소 매핑을 로깅한 콘솔 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 JNI 앱(스트립 lib에 `nativeCheck()` 하나)으로 RegisterNatives 매핑을 추출하고 onEnter 인자를 관찰한다.

## 실습 절차와 관측

### 가설
스트립 lib이라 `findExportByName`은 null이지만, RegisterNatives 후킹으로 `nativeCheck`↔주소가 드러난다. `Inferred`

### 절차
1. `android_dlopen_ext` 후킹으로 lib 로드를 관찰.
2. RegisterNatives 접근(enumerateSymbols/JNIEnv 슬롯) → 이름↔주소 매핑 로깅.
3. 그 주소에 `Interceptor.attach` → onEnter 인자(JNIEnv*/jobject/Java 인자)·onLeave 반환.
4. `Memory.hexdump`로 버퍼 관찰.
5. Java 후킹(8장)과 상관지어 경계 넘나듦을 추적.

```javascript
// dlopen 관찰
Interceptor.attach(Module.getExportByName(null, 'android_dlopen_ext'), {
  onEnter(a) { console.log('dlopen', a[0].readCString()); }
});
// 스트립 함수에 직접 attach (RegisterNatives로 얻은 주소)
Interceptor.attach(base.add(0x1240), {
  onEnter(args) { console.log('nativeCheck arg=', args[2].toInt32()); },
  onLeave(ret) { console.log('  ret=', ret); }
});
```

> **[그림 2]** 그 주소에 attach해 onEnter 인자(JNIEnv*/jobject/arg)와 onLeave 반환을 관찰 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[RegisterNatives] com.example/Native.nativeCheck -> 0x7abc... (stripped)
[attach 0x7abc] onEnter JNIEnv=0x.. jobject=0x.. arg=42 | onLeave ret=0x1
```

## Root Cause — 왜 이렇게 되는가

RegisterNatives가 매핑을 드러내는 것은 JNI 설계상 동적 등록이 여기 집중되기 때문이다 — 스트립 심볼을 우회하는 정석이다. 네이티브가 정적 DEX 분석 밖인 것은 JNI가 별개 표면이기 때문이고, `Java_<pkg>_<Class>_<method>` 심볼 방식이면 ART 런타임이 첫 호출 시 dlsym으로 결정하지 ELF lazy binding이 아니다.

## 방어와 회귀 검증

- (개발자) 네이티브에 비밀을 숨겨도 RegisterNatives·onEnter로 드러난다 — 난독화는 지연일 뿐, 인가는 서버. 자작 lib에서 "RegisterNatives 매핑이 예상 함수 집합과 일치"를 회귀로.
- (연구자) 네이티브 메모리 버그는 8부의 최소재현 원칙으로(무기화 금지).

**흔한 실패와 처리.** `getExportByName` throws → 맹글/스트립, `enumerateSymbols`/슬롯으로. onEnter 인자 깨짐 → arg 인덱스 오해(0=JNIEnv*). 주소가 매번 다름 → ASLR, 모듈 base 상대 오프셋으로.

## 버전 차이와 한계

- JNIEnv 슬롯 인덱스는 JNI 스펙 고정이나, libart 내부 심볼명은 버전별 상이 → `enumerateSymbols`가 안전.
- root/userdebug + arch 일치. arm64에서 실제 PAC 서명 함수 관측(C37), x86_64는 변환.

## 정리

- 네이티브 후킹은 `Interceptor.attach` onEnter/onLeave.
- 스트립 심볼은 RegisterNatives로 이름↔주소 복원.
- `getExportByName('libart.so','RegisterNatives')`는 맹글이라 실패 → enumerateSymbols/슬롯.

**점검 질문** — (1) `getExportByName('libart.so','RegisterNatives')`가 실패하는 이유와 대안은? (2) `onEnter`의 `args[0]`은 무엇인가? (3) 스트립 lib에서 Java native↔C 매핑을 얻는 방법은?

**참고** — [Frida JS API](https://frida.re/docs/javascript-api) · [JNI Tips](https://developer.android.com/training/articles/perf-jni) · [C33 ELF·linker](/posts/android-concept-atlas-c33-elf-linker-plt-got/)

*다음 글: [Burp/mitmproxy 로컬 인터셉션](/posts/android-lab-p1c11-burp-mitmproxy-intercept/).*
