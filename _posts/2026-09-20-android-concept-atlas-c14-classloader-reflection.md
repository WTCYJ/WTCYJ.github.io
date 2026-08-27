---
layout: post
title: "Android Security Concept Atlas C14 - ClassLoader·리플렉션·동적 코드 로딩, 정적 분석이 무너지는 곳"
date: 2026-09-20 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ClassLoader, DexClassLoader, InMemoryDexClassLoader, Reflection, HiddenAPI, Packer, DynamicCodeLoading, ConceptAtlas, 학습기록]
excerpt: "APK를 정적으로 다 뜯었는데 로직이 안 보인다면, 진짜 코드는 런타임에 로드됩니다. Android의 ClassLoader는 전부 BaseDexClassLoader + DexPathList 위의 얇은 껍질이고, 부모위임(parent-first)이 프레임워크 클래스를 단일 정의로 지키죠. 그런데 DexClassLoader는 임의 경로의 dex를, InMemoryDexClassLoader(API 26)는 디스크에 파일도 안 떨구고 ByteBuffer의 dex를 로드합니다 - 내가 분석한 Toss 패커가 Blowfish+SEED로 복호한 dex를 바로 이걸로 실행했죠. 그래서 동적 코드 로딩은 악성코드/패커의 1순위 회피 기법이고, 정적 APK 분석은 stub만 봅니다. 리플렉션은 setAccessible로 언어 접근은 뚫지만 A9+ hidden-API 강제는 못 뚫고요. 내 패커 RE 작업과 직결되는 Tier 2 모듈입니다."
---

> **Concept Atlas 모듈**: C14 — ClassLoader·리플렉션·동적 코드 로딩
> **계층**: Tier 2 (Android Runtime) · **난이도**: 중급 · **선수 개념**: C13(ART), C07(DEX)
> **성격**: 보완 편.

C13에서 ART가 DEX를 실행한다 했습니다. 그 DEX를 **어떻게 로드하는가**, 그리고 그 로딩이 어떻게 **정적 분석을 무력화하는가**가 이 편입니다 — 내가 뜯은 Toss 패커의 핵심.

한 문장으로: **Android의 ClassLoader는 DexPathList 위의 얇은 껍질들이고, 동적 코드 로딩(런타임 복호 dex를 InMemoryDexClassLoader로)이 정적 APK 분석을 stub만 보게 만든다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **ClassLoader 계층**: 전부 `BaseDexClassLoader`+`DexPathList`(순서 있는 dex element) 위. Boot/Path/Dex/InMemory.
- **부모위임**(parent-first): 부모에게 먼저 물어보고 없을 때만 자기가 정의.
- **리플렉션**: `java.lang.reflect`로 이름으로 멤버 접근. A9+ **hidden-API 강제**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

DEX(C13)를 **로드하는 메커니즘**이자, **동적 코드 로딩이 정적 분석을 무너뜨리는 지점**입니다. 내 Toss 패커 작업(런타임 복호 dex)의 핵심이고, C48(무결성)·C16(정적≠실행)과 직결됩니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **공통 코어**: 모든 앱 로더는 `BaseDexClassLoader`를 상속, 상태는 `DexPathList`(dex element 배열)이고 클래스 조회는 이 배열을 순회. 로더들의 차이는 **엔진이 아니라 목록을 채우는 방식**.
- **네 로더**:
  - `BootClassLoader`: bootclasspath(프레임워크 `java.*`/`android.*`) 로드, **루트 부모**.
  - `PathClassLoader`: 앱 **자신의 설치된** 코드(base/split dex).
  - `DexClassLoader`: **호출자가 준 임의 경로**의 dex/jar/apk — 동적 로딩 진입점.
  - `InMemoryDexClassLoader`(**API 26/A8.0**): `ByteBuffer`의 dex를 **디스크 파일 없이** 로드.
- **부모위임**: `loadClass`가 부모에게 먼저 위임, 부모가 못 찾을 때만 자기 정의(**parent-first**).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **부모위임이 안전 불변식**: 프레임워크 클래스는 항상 `BootClassLoader`가 정의(위임으로 도달)하므로, 앱 로더가 `java.lang.String`을 갈아끼울 수 없습니다. 클래스 정체성 = **이름 + 정의 로더**(다른 로더로 같은 바이트 로드하면 별개 Class, ClassCastException).
- **신뢰하면 안 되는 것들**:
  - **"PathClassLoader는 외부 경로를 못 읽는 보안 제한 로더"** — `DexClassLoader`와 거의 동일한 `BaseDexClassLoader` 서브클래스입니다. 차이는 **의도지 하드 제한이 아님** — PathClassLoader라고 코드가 설치 APK에서만 왔다는 증거는 아닙니다.
  - **"부모위임은 self-first"** — **parent-first**입니다(그래서 동적 로드 dex가 상위가 이미 정의한 클래스를 재정의 못 함).
  - **"InMemoryDexClassLoader는 A8.1/27"** — **A8.0/API26**입니다(ByteBuffer[] 배열 오버로드만 A29).
  - **"setAccessible이면 hidden-API도 뚫린다"** — `setAccessible(true)`는 **언어 접근 검사**만 우회합니다. A9+ **hidden-API 런타임 강제는 별개**(ART 멤버 조회 층에서 리플렉션·JNI 둘 다).
  - **"읽기전용 dex 강제는 A10 하드룰"** — 하드룰("읽기전용 아니면 throw")은 **A14/API34 "Safer Dynamic Code Loading"**(targetSdk 34+, 앱이 `File.setReadOnly()`)입니다. A29는 경고 위주로 릴리스마다 강화.
  - **"정적 APK 분석이면 로직 완전"** — 패커면 `classes.dex`는 **stub**이고 진짜 코드는 런타임 로드.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: dex(설치 APK / 임의 경로 / `ByteBuffer`).
- **동작**: 로더가 `DexPathList`에 element로 추가 → `loadClass`가 parent-first로 조회.
- **리플렉션**: `Class.forName`·`getDeclaredMethod`·`setAccessible`·`Method.invoke`로 이름으로 멤버 접근. hidden-API 강제(A9+)가 non-SDK 접근을 거부/경고(카테고리: SDK/greylist/max-target/blocklist).

## 질문 5 — 실패하면 어떤 취약점으로/분석에 어떤 함의가

- **동적 코드 로딩(DCL) = 악성/패커 1순위 회피**: 코드가 분석 대상 APK에 없고 런타임에 (자산/네트워크/복호로) 로드됩니다. **Toss 패커**: 다단계 Blowfish+SEED로 복호한 dex를 `InMemoryDexClassLoader`(디스크 미접촉)로 실행 → 파일 기반 수집을 무력화.
- **정적 분석 불완전**: 정적으론 얇은 로더 stub만 보임 → **동적으로** 관찰해야(로더 후킹·메모리 덤프).
- **리플렉션/JNI 탈출**: `Class.forName/invoke`의 흐름은 단순 정적 도구에 안 보이고, `.so`(JNI, C15) 로직은 DEX 밖.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **InMemoryDexClassLoader**: A8.0/API26(단일 ByteBuffer), 배열 오버로드 A29.
- **hidden-API 제한**: A9/API28 도입(당시 이름 greylist/greylist-max-o/-p/blacklist), A10에 unsupported/max-target-*/blocklist로 명명 진화. 이중 리플렉션(meta-reflection) 우회는 패치됨.
- **Safer Dynamic Code Loading**(읽기전용 dex 강제): A14/API34(targetSdk 34+).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- **동적 분석**: Frida로 `DexClassLoader`/`InMemoryDexClassLoader` 생성자·`DexFile.openInMemoryDexFile` 후킹 → 로드되는 dex 바이트 캡처, 복호 후 메모리에서 dex 덤프, `/proc/<pid>/maps`의 익명 실행 dex 영역.
- **정적**: `veridex`(non-SDK 사용 스캔), `baksmali`(복원 dex).
- **소스**: AOSP `libcore/dalvik/src/main/java/dalvik/system/`(`BaseDexClassLoader`·`DexPathList`·`InMemoryDexClassLoader`), `art/runtime/hidden_api.cc`.

**주의**: 아키텍처 무관 → **에뮬레이터로 Frida 후킹·dex 덤프 실측 가능**(단 패커의 루팅탐지/안티후킹은 별도 우회 필요).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C13(ART)**: 로드된 dex가 여기서 실행(인터프리트/JIT/AOT).
- **C15(JNI)**: 네이티브 `.so`는 이 DEX 파이프라인과 **별개** 표면.
- **C16(JIT/AOT 분석차)**: "정적으로 보이는 것 ≠ 실제 실행"의 다음 편.
- **C48(무결성)**: DCL/패커가 무결성·Play Integrity와 충돌.
- 다음은 이 실행 형태(인터프리트/JIT/AOT)가 분석에 주는 차이 **C16**로.

## 직접 그릴 수 있는 호출 흐름

```
[ ClassLoader와 동적 코드 로딩(패커) ]

  BootClassLoader (프레임워크, 루트 부모)
       ↑ parent-first 위임
  PathClassLoader (앱 자신의 base/split dex)  ←── 정적 분석이 보는 것
       │
  DexClassLoader (임의 경로 dex)  /  InMemoryDexClassLoader (ByteBuffer, 파일 없음)
       └── 전부 BaseDexClassLoader + DexPathList(dex element 배열) 위

  패커(Toss): classes.dex=stub ──런타임──▶ Blowfish+SEED 복호 → dex(메모리)
       → InMemoryDexClassLoader.load  ← 진짜 코드(디스크 미접촉)
       분석: Frida로 로더 후킹 → dex 캡처/덤프 (정적 APK엔 없음)

  리플렉션: Class.forName/invoke/setAccessible(언어 접근만)
       └ A9+ hidden-API 강제(ART 조회층, 리플렉션+JNI)는 별개로 막음
```

## 오개념 판별 문제 5개

1. "부모위임 모델에서 로더는 자기가 먼저 클래스를 찾고, 없으면 부모에게 넘긴다."
2. "`PathClassLoader`는 외부 경로를 못 읽게 하드 제한된 보안 로더다."
3. "`InMemoryDexClassLoader`는 Android 8.1(API 27)에서 도입됐다."
4. "리플렉션에서 `setAccessible(true)`를 쓰면 숨김 프레임워크 API(hidden API)도 호출된다."
5. "APK를 정적으로 다 분석하면 앱의 실행 로직을 완전히 안다."

<details><summary>판정 기준(펼치기)</summary>

1. **parent-first**입니다 — 부모에게 먼저 위임하고 없을 때만 자기 정의(프레임워크 클래스 shadowing 방지).
2. `DexClassLoader`와 거의 같은 서브클래스입니다. 차이는 **의도지 하드 제한이 아님**.
3. **A8.0/API26**입니다(ByteBuffer[] 오버로드만 A29).
4. `setAccessible`은 **언어 접근**만 우회합니다. A9+ **hidden-API 강제는 별개**로 막습니다.
5. 패커/DCL이면 `classes.dex`는 **stub**이고 진짜 코드는 런타임 로드 — 동적 관찰이 필요합니다.
</details>

## 서술형 문제 3개

1. 네 ClassLoader(Boot/Path/Dex/InMemory)가 `BaseDexClassLoader`+`DexPathList` 위에서 무엇이 같고 무엇이 다른지, parent-first 위임이 왜 안전 불변식인지 서술하세요.
2. 동적 코드 로딩(패커)이 왜 정적 APK 분석을 무력화하는지, Toss의 복호-후-InMemory 로드를 예로 서술하고, 어떤 동적 관찰이 필요한지 설명하세요.
3. `setAccessible`(언어 접근)과 A9+ hidden-API 강제(런타임)가 왜 별개 층인지, 리플렉션/JNI 모두에 적용됨과 함께 서술하세요.

## 소스 탐색 과제

- Frida로 `DexClassLoader`/`InMemoryDexClassLoader` 생성자를 후킹해, 어떤 앱이 런타임에 dex를 로드하는지 캡처하세요(양성 앱 대상).
- `/proc/<pid>/maps`에서 익명 실행 dex 영역을 찾고, 거기서 dex를 덤프해 `baksmali`로 확인하세요.
- `veridex`로 한 앱의 non-SDK(hidden API) 사용을 스캔하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **로더 실측**: Frida 후킹으로 로드되는 dex를 캡처(내 Toss 작업 재활용).
2. **정적 vs 동적**: 정적 APK의 stub vs 덤프한 실제 dex를 대조.
3. **hidden-API 서술**: `setAccessible` vs hidden-API 강제 차이를 veridex 출력으로.
4. **연결**: 이 로드된 dex가 C13의 어느 실행 모드로 도는지(C16).

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

Android의 ClassLoader는 전부 `BaseDexClassLoader`+`DexPathList` 위의 얇은 껍질이고, parent-first 위임이 프레임워크 클래스를 단일 정의로 지킵니다. 그런데 `DexClassLoader`는 임의 경로의, `InMemoryDexClassLoader`(A8.0/26)는 디스크 파일도 없이 `ByteBuffer`의 dex를 로드합니다 — 내가 뜯은 Toss 패커가 Blowfish+SEED로 복호한 dex를 바로 이걸로 실행했죠. 그래서 동적 코드 로딩은 악성코드/패커의 1순위 회피이고, 정적 APK 분석은 stub만 봅니다. 리플렉션은 `setAccessible`로 언어 접근은 뚫지만 A9+ hidden-API 강제는 못 뚫습니다. 다음은 그 로드된 코드가 인터프리트/JIT/AOT 중 무엇으로 도느냐가 분석에 주는 차이, **C16**으로 이어집니다.
