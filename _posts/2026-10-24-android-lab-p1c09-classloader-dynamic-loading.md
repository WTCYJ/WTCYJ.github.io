---
layout: post
title: "ClassLoader·동적 로딩 관찰 — 패커가 로드하는 dex를 런타임에 덤프하기"
date: 2026-10-24 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ClassLoader, DynamicLoading, Packer, Frida]
excerpt: "패커가 있으면 정적 APK엔 로더 stub만 남고 진짜 코드는 런타임에 복호돼 InMemoryDexClassLoader로 올라간다. 그래서 DexClassLoader/InMemoryDexClassLoader 생성자와 DexFile.openInMemoryDexFile을 후킹해 ByteBuffer의 dex를 그 자리에서 덤프하고, Java.enumerateClassLoaders로 base 로더에 없던 클래스를 쥔 로더를 찾는다 — Toss 패커 분석의 핵심 동작이다."
---

정적 jadx(4장)가 로더 stub만 보여줄 때, 이 장이 진짜 코드로 넘어가는 다리다. 패커는 진짜 dex를 런타임에 복호해 InMemoryDexClassLoader로 올리므로, 그 로드 시점을 후킹해 dex 바이트를 그 자리에서 덤프하면 정적으로 안 보이던 클래스가 나온다. 이 글은 로더 생성자를 후킹해 로드되는 dex를 포착·덤프하고 리플렉션 흐름을 관찰하는 방법을, 내가 분석한 Toss 패커(Blowfish+SEED 복호 후 InMemory 로드)를 배경으로 정리한 기록이다.

> **한 줄 결론**: 언팩은 초기 init에서 일어나므로 **spawn**으로 로더 생성자를 후킹해 `ByteBuffer`의 dex를 덤프하고(dex 매직 `dex\n035` 확인), `Java.enumerateClassLoaders`로 동적 클래스를 쥔 로더를 찾는다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Frida로 런타임 로드 dex를 포착·덤프하고 리플렉션을 관찰한다. 선수 개념은 [Frida(8장)](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)의 spawn·Java 후킹, [ClassLoader·동적로딩(C14)](/posts/android-concept-atlas-c14-classloader-reflection/)의 로더 계층·패커다.

## 핵심 개념 — 로더 후킹과 dex 덤프

- **로더 후킹**: `dalvik.system.InMemoryDexClassLoader`(API 26; 배열 오버로드 API 29)·`DexClassLoader`·`BaseDexClassLoader` 생성자, `DexFile.openInMemoryDexFile`을 후킹해 로드 시점의 dex 바이트를 캡처. `Source-confirmed`
- **덤프**: `InMemoryDexClassLoader`에 넘어온 `ByteBuffer`를 읽어 파일로(**dex 매직 `dex\n035`**로 검증), 또는 `/proc/<pid>/maps`의 익명 실행 영역을 스캔. direct buffer는 `.array()`가 던질 수 있어 position을 보존하며 읽는다. `Source-confirmed`
- **로더 열거**: `Java.enumerateClassLoaders({onMatch,onComplete})`로 base에 없던 동적 클래스를 쥔 로더를 발견 → 그 로더의 `ClassFactory`로 전환해 해당 클래스를 후킹. `Source-confirmed`
- **리플렉션·hidden-API**: `java.lang.reflect.Method.invoke`·`Class.forName` 후킹으로 리플렉션 흐름. A9+ hidden-API 강제는 ART 조회층(리플렉션+JNI)에서 — `setHiddenApiExemptions(['L'])`로 완화. `Source-confirmed`

**신뢰 경계와 위협 모델.** 패커/DCL은 악성·보호 양쪽에 쓰인다. **자작 앱 또는 허가된 분석 대상**만. 덤프한 dex에 PII가 없도록 유의한다.

> **[그림 1]** InMemoryDexClassLoader 생성자 후킹으로 로드되는 dex를 캡처하고 매직을 확인한 콘솔 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 "미니 패커" 앱(자작 dex를 XOR로 감싸 InMemory 로드)으로 덤프 파이프라인을 검증한 뒤, 필요 시 내 Toss 분석을 재현(비공개).

## 실습 절차와 관측

### 가설
정적 jadx엔 로더 stub만, 런타임 후킹 덤프엔 진짜 클래스가 담긴 dex가 나온다. `Inferred`

### 절차
1. spawn으로 로더 생성자를 후킹한다.
2. ByteBuffer를 덤프 → dex 매직 확인 → baksmali/jadx로 분석.
3. `enumerateClassLoaders`로 동적 로더를 확인.
4. `Method.invoke` 후킹으로 리플렉션 흐름.
5. 덤프 dex를 정적 APK와 대조("정적 stub ≠ 실제").

```javascript
Java.perform(function () {
  var IMD = Java.use('dalvik.system.InMemoryDexClassLoader');
  IMD.$init.overload('java.nio.ByteBuffer', 'java.lang.ClassLoader')
    .implementation = function (buf, parent) {
      dumpBuffer(buf);            // dex 매직 확인 후 파일로 (position 보존)
      return this.$init(buf, parent);
    };
});
```

> **[그림 2]** `enumerateClassLoaders`가 base에 없던 동적 클래스를 쥔 로더를 찾은 출력 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[IMD.$init] ByteBuffer captured, magic=dex\n035, size=... -> dumped real.dex
[enumerateClassLoaders] found dynamic loader holding com.real.Logic
```

## Root Cause — 왜 이렇게 되는가

정적이 stub만 보는 것은 코드가 런타임에만 존재하기 때문이다(C14) — "정적으로 보이는 것 ≠ 실제 실행"의 원인이 JIT/AOT가 아니라 DCL임을 실증한다(C16). 그래서 정적 결론이 비어 보여도 "깨끗하다"가 아니라 "런타임에 있다"로 읽어야 한다.

## 방어와 회귀 검증

- (개발자) DCL 사용은 Play 정책·A14 읽기전용 dex 규칙을 준수하고, 무결성은 서버(C48). 자작 패커 앱에서 "덤프한 dex == 원본 dex(의미상)"를 baksmali 비교로 회귀.
- (연구자) 덤프물은 최소보관·비공개.

**흔한 실패와 처리.** dex 매직 불일치 → 아직 복호 전 버퍼, 복호 후 지점을 후킹. 클래스 후킹 실패 → base 로더에 없으니 동적 로더의 ClassFactory로.

## 버전 차이와 한계

- InMemoryDexClassLoader 단일 ByteBuffer=API26, 배열=API29. A14 "Safer Dynamic Code Loading"(읽기전용 dex, C14).
- 아키텍처 무관. 상용 패커의 안티후킹은 별도 우회(허가 대상만).

## 정리

- 언팩은 spawn으로 로더 생성자 후킹.
- ByteBuffer 덤프 + 매직 확인으로 실제 dex 복원.
- 동적 로더는 `enumerateClassLoaders`로.

**점검 질문** — (1) 언팩 후킹에 spawn이 필요한 이유는? (2) `enumerateClassLoaders`가 필요한 상황은? (3) 덤프 dex의 매직으로 무엇을 확인하나?

**참고** — [InMemoryDexClassLoader](https://developer.android.com/reference/dalvik/system/InMemoryDexClassLoader) · [Frida docs](https://frida.re/docs) · [C14](/posts/android-concept-atlas-c14-classloader-reflection/) · [C16](/posts/android-concept-atlas-c16-jit-aot-analysis/)

*다음 글: [JNI·native 함수 동적 관찰](/posts/android-lab-p1c10-jni-native-observation/).*
