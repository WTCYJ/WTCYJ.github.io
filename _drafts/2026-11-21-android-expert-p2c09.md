---
layout: post
title: "ClassLoader·dynamic code loading"
date: 2026-11-21 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ClassLoader, DexClassLoader, 동적코드로딩, ART]
excerpt: "동적 코드 로딩의 신뢰 경계는 '어떤 ClassLoader를 쓰느냐'가 아니라 '로드할 파일을 누가 쓸 수 있느냐'다. DexClassLoader의 optimizedDirectory 인자는 API 26부터 무시되는데, 여기에 월드라이터블 경로를 넘기던 옛 코드가 바로 그 취약점이었다."
---

앱이 자기 APK 안의 클래스만 실행한다면 보안 관점은 단순하다 — 코드의 무결성은 설치 시 서명 검증으로 끝난다. 문제는 앱이 **설치 이후에** 코드를 더 불러올 때 생긴다. 플러그인 프레임워크, 핫픽스, 광고 SDK, 그리고 정적 분석을 피하려는 악성코드가 전부 이 동적 코드 로딩(DCL, dynamic code loading)을 쓴다. 그런데 "어떤 ClassLoader를 쓰면 안전한가"라는 질문 자체가 틀린 질문이다.

이 글은 Android의 ClassLoader 계층(`BootClassLoader`→`PathClassLoader`→`DexClassLoader`/`InMemoryDexClassLoader`)이 AOSP `libcore` 소스에서 어떻게 구현되는지, 그리고 동적 로딩의 신뢰 경계가 어디에 그어지는지를 자작 앱과 1차 소스로 정리한 기록이다.

> **한 줄 결론**: 동적으로 로드한 코드의 무결성은 ClassLoader의 *종류*가 아니라 그 코드 파일이 놓인 *위치의 쓰기 권한*이 결정한다 — 앱 전용 내부 저장소의 읽기 전용 파일만 신뢰 경계 안이다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 세 가지다. (1) ART가 클래스를 찾는 위임(delegation) 모델과 `DexPathList` 자료구조, (2) `DexClassLoader`·`InMemoryDexClassLoader`·`DelegateLastClassLoader`의 차이와 각각이 언제 도입됐는지, (3) DCL이 왜 고전적 RCE 벡터가 되는지와 안전한 로딩 패턴이다. 무기화된 익스플로잇이 아니라 구조·소스 이해가 목적이므로, 실행 코드는 전부 **우리 자신이 만든 양성 dex**만 다룬다.

선수 지식이 셋 깔린다. dex 바이트코드가 ART에서 해석·컴파일되는 경로(이 파트 8장 ART interpreter/JIT/AOT/dex2oat)를 알면 "동적 로드한 dex는 AOT 최적화 밖이라 느리다"가 왜 그런지 보인다. 앱 서명 검증(이 파트 11장 PackageManagerService)은 설치 시점의 무결성 경계이고, DCL은 그 경계를 설치 *이후로* 확장하는 행위다. 그리고 네이티브 라이브러리 로딩(이 파트 20장 bionic·linker)도 결국 같은 ClassLoader의 검색 경로를 탄다. 전체 구조에서 ClassLoader는 App 계층에 있지만, 그 무결성 판단은 파일시스템 권한(Kernel)과 서명 검증(system_server)에 뿌리를 둔다.

## 핵심 개념 — 위임 모델과 DexPathList

Android의 ClassLoader는 자바 표준의 **부모 우선 위임(parent-first delegation)** 을 그대로 따른다. `java.lang.ClassLoader.loadClass`는 ① `findLoadedClass`로 이미 로드됐는지 보고 ② 없으면 부모에게 위임하고 ③ 부모도 못 찾으면 자기 `findClass`를 호출한다. `Source-confirmed` 앱 클래스로더의 부모는 결국 `BootClassLoader`이고, 이건 부팅 이미지(`boot.art`/`boot.oat`)에서 컴파일된 프레임워크 클래스를 공급하는 싱글턴이다. `Source-confirmed`

앱 코드를 실제로 여는 로더는 두 갈래인데 **둘 다 `BaseDexClassLoader`를 상속한다**. `PathClassLoader`는 설치된 APK(`base.apk`)를 로드하는 시스템 기본 로더이고, `DexClassLoader`는 임의 경로의 dex/jar를 로드하도록 열어둔 로더다. `Source-confirmed` 핵심은 실제 탐색이 `BaseDexClassLoader`가 들고 있는 `DexPathList pathList` 한 곳에 모인다는 점이다 — `pathList.dexElements[]` 배열을 순회하며 각 `Element`에서 클래스를 찾는다. `Source-confirmed` 핫픽스·멀티덱스 프레임워크가 "런타임에 클래스를 주입"한다고 할 때 실제로 하는 일은 이 `dexElements` 배열을 리플렉션으로 갈아끼우는 것뿐이다.

| 로더 | 소스 | 도입 | 용도 |
|--|--|--|--|
| `BootClassLoader` | 부팅 이미지(boot.oat) | - | 프레임워크 클래스, 위임 사슬의 뿌리 |
| `PathClassLoader` | 설치된 `base.apk` | - | 앱 자기 코드(시스템이 생성) |
| `DexClassLoader` | 임의 경로 dex/jar | - | 명시적 동적 로딩 |
| `InMemoryDexClassLoader` | `ByteBuffer`(파일 없음) | API 26 | 메모리에서 직접 로드 |
| `DelegateLastClassLoader` | 임의 경로 dex/jar (파일 기반, PathClassLoader 상속) | API 27 | **자기 우선** 탐색(위임 순서 반전) |

흔한 오해 둘. 첫째, "`DexClassLoader`는 위험하고 `PathClassLoader`는 안전하다"는 틀렸다 — 둘의 클래스 탐색 로직은 `BaseDexClassLoader`로 **동일**하고, 위험은 로더 종류가 아니라 로드하는 파일의 출처에서 온다. 둘째, `DelegateLastClassLoader`는 부모를 건너뛰는 게 아니라 순서를 바꾼다 — 부팅 클래스패스 → 자기 자신 → 부모 순으로 봐서, 라이브러리 버전 충돌 시 자기 버전을 이기게 한다. `Source-confirmed`

```
BootClassLoader          (프레임워크, boot 이미지 · 위임 사슬의 뿌리)
      ▲ parent
PathClassLoader          (설치된 base.apk = 서명 검증된 코드)
      ▲ parent
DexClassLoader / InMemoryDexClassLoader   (동적 로드 코드 ← 무결성 미검증)
```

> **[그림 1]** AOSP `libcore/dalvik/src/main/java/dalvik/system/BaseDexClassLoader.java`와 `DexPathList.java`에서 `findClass`가 `dexElements` 배열을 순회하는 부분을 열어 강조한 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

DCL의 신뢰 경계는 한 문장으로 요약된다: **로드하는 코드의 무결성 ≤ 그 코드 파일이 놓인 디렉터리에 쓸 수 있는 주체의 무결성.** 서명 검증은 `base.apk`에만 적용되고, 런타임에 `DexClassLoader`로 여는 dex 파일에는 아무런 서명 검증도 없다. `Source-confirmed` 따라서 그 파일을 다른 주체가 덮어쓸 수 있으면, 그 주체가 우리 앱의 프로세스 안에서 코드를 실행하는 것과 같다.

고전적 취약 패턴은 셋이다.

- **월드라이터블/외부 저장소 로딩.** 외부 저장소나 월드라이터블 경로의 dex를 로드하면, 같은 기기의 다른 앱이 그 파일을 먼저 덮어써 임의 코드를 주입할 수 있다. 이건 confused-deputy의 교과서 사례다. `Reported`
- **`optimizedDirectory`에 안전하지 않은 경로.** `DexClassLoader(dexPath, optimizedDirectory, libPath, parent)`의 옛 시그니처는 최적화된 odex를 둘 위치를 인자로 받았는데, 여기에 공용 경로를 넘기면 그 odex가 오염될 수 있었다. 그래서 **이 인자는 API 26부터 deprecated이고 무시된다** — 옛 코드가 여기에 월드라이터블 경로를 넘기던 것이 바로 취약점이었다. `Source-confirmed`
- **평문 서버에서 받은 코드.** HTTPS 없이(또는 핀 없이) 내려받은 dex를 로드하면 네트워크 중간자가 곧 코드 실행자다. `Reported`

방어 측 관점에서 악성코드가 DCL을 쓰는 이유도 같은 구조의 뒷면이다. 2차 페이로드를 런타임에 복호화해 `InMemoryDexClassLoader`로 메모리에서만 로드하면, APK를 정적 분석해도 실제 악성 로직이 dex에 없다. `Reported` 이건 이미 널리 공개된 분석 사실이고, 여기서는 탐지·방어 맥락으로만 다룬다 — 무기화 절차는 다루지 않는다.

## 관측 — 자작 앱으로 위임 사슬 확인

### 절차

에뮬레이터(AVD)에 올린 자작 앱에서 (1) 자기 ClassLoader 사슬을 로그로 찍고, (2) 빌드 타임에 만들어 둔 **우리 자신의 양성 dex**를 `InMemoryDexClassLoader`로 메모리 로드해 원리만 확인한다. 실행 코드는 우리가 작성한 `com.example.Plugin` 한 클래스뿐이다.

```kotlin
// (1) 위임 사슬 출력 — 부모를 따라 뿌리까지
var cl: ClassLoader? = javaClass.classLoader
while (cl != null) { Log.d("CL", cl.toString()); cl = cl.parent }

// (2) 메모리에서 우리 양성 dex 로드(원리 이해용, PoC 최소 수준)
val dex = ByteBuffer.wrap(assets.open("plugin.dex").readBytes()) // 우리가 빌드한 dex
val loader = InMemoryDexClassLoader(dex, javaClass.classLoader)  // parent = 앱 로더
val plugin = loader.loadClass("com.example.Plugin").getConstructor().newInstance()
Log.d("CL", "loaded by = ${plugin.javaClass.classLoader}")
```

> **[그림 2]** 위 자작 앱을 에뮬레이터에서 실행하고 `adb logcat -s CL`로 `PathClassLoader → BootClassLoader` 사슬과 `InMemoryDexClassLoader`로 로드된 클래스의 로더가 각각 찍힌 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
CL: dalvik.system.PathClassLoader[DexPathList[[zip file "/data/app/~~xxxx/base.apk"],
      nativeLibraryDirectories=[/data/app/~~xxxx/lib/arm64, /system/lib64, ...]]]
CL: java.lang.BootClassLoader@a1b2c3d
CL: loaded by = dalvik.system.InMemoryDexClassLoader[DexPathList[[dex file "<Unknown>"], ...]]
```

세 줄이 이 절의 결론을 그대로 보여준다. 앱 코드는 `PathClassLoader`가, 프레임워크는 그 부모 `BootClassLoader`가 담당하고, 동적 로드한 클래스는 **별도의 `InMemoryDexClassLoader`가 정의 로더(defining loader)** 가 된다. 정의 로더가 다르다는 사실이 다음 절의 `ClassCastException` 함정으로 이어진다.

## Root Cause — 왜 이렇게 되는가

**클래스의 정체성은 (완전 이름, 정의 ClassLoader) 쌍이다.** 같은 `com.example.Plugin`이라도 앱 로더가 정의한 것과 동적 로더가 정의한 것은 ART에게 **서로 다른 타입**이다. `Source-confirmed` 그래서 동적 로드한 인스턴스를 앱 쪽 `Plugin` 타입으로 캐스팅하면 `ClassCastException`이 난다 — 플러그인 프레임워크가 겪는 "같은 이름인데 캐스팅이 안 된다" 버그의 뿌리가 이것이다. 해법은 타입을 **공통 부모 로더**(보통 앱 로더나 부팅 로더)가 정의한 인터페이스로 좁히는 것이다. 부모 우선 위임이 존재하는 이유가 바로 이 공통 타입 공유다.

무결성 문제의 뿌리도 구조적이다. 서명 검증은 `PackageManagerService`가 설치 *시점에* `base.apk`에만 수행한다. `DexPathList`가 런타임에 새 `Element`를 추가할 때는 그 dex의 출처를 검증할 프레임워크 훅이 없다 — 그저 파일을 열어 파싱할 뿐이다. `Source-confirmed` 즉 DCL은 "서명된 APK"라는 신뢰 뿌리 바깥으로 코드 경로를 확장하는 행위이고, 그 순간 무결성 책임은 전적으로 **파일시스템 권한**으로 떠넘겨진다. 앱 전용 내부 저장소(`getCodeCacheDir()` 등)에 두고 로드 후 읽기 전용으로 잠그라는 권고는 여기서 나온다 — 다른 UID가 못 쓰게 만드는 것이 유일한 대체 신뢰 뿌리이기 때문이다. `Reported`

## 버전 차이와 한계

- **`InMemoryDexClassLoader`는 API 26(Android 8.0), `DelegateLastClassLoader`는 API 27부터**다. 그 이하를 타겟하면 파일 없는 로딩을 쓸 수 없다. `Source-confirmed`
- **`DexClassLoader`의 `optimizedDirectory` 인자는 API 26부터 무시**된다. 옛 코드가 여기에 넘기던 경로가 취약점이었으니, 마이그레이션 시 이 인자를 `null`로 정리한다. `Source-confirmed`
- 최근 버전은 **쓰기 가능한 파일에서의 코드 실행을 제한**하는 방향으로 강화됐다(W^X 계열). 정확한 시작 API와 적용 범위는 원문 재확인 필요. `Inferred`
- 동적 로드한 dex는 앱 설치 시의 `dex2oat` AOT 최적화 대상이 아니라 대체로 인터프리터/JIT로 돈다 — 성능 페널티가 있고, 이 자체가 DCL 남용을 관측·프로파일링으로 탐지하는 단서가 된다. `Reported`
- 에뮬레이터로는 파일시스템 권한·SELinux 경계는 그대로 관측되지만, 실기기 특유의 Play Protect 스캐닝 같은 상위 방어는 재현되지 않는다.

## 정리

- ClassLoader 위험도는 로더 *종류*가 아니라 로드하는 파일의 *쓰기 권한*이 정한다 — `PathClassLoader`든 `DexClassLoader`든 탐색 로직은 `BaseDexClassLoader`로 동일하다.
- 클래스 정체성은 (이름, 정의 로더) 쌍이다. 동적 로드 클래스를 앱 타입으로 캐스팅하면 깨지고, 공통 부모 로더가 정의한 인터페이스로만 다뤄야 한다.
- 안전한 DCL은 앱 전용 내부 저장소의 읽기 전용 파일에서만 로드하는 것. 외부 저장소·월드라이터블·평문 다운로드는 곧 임의 코드 실행 경로다.
- `optimizedDirectory`(API 26+ 무시)에 공용 경로를 넘기던 옛 코드는 즉시 정리한다.

**점검 질문** — (1) 같은 FQCN 클래스를 두 로더가 정의하면 왜 `ClassCastException`이 나고, 어떻게 피하는가? (2) 서명 검증은 `base.apk`에만 걸리는데, 동적 로드 dex의 무결성은 무엇이 대신 보장하는가? (3) `DelegateLastClassLoader`의 탐색 순서는 표준 위임과 어떻게 다른가?

**참고** — AOSP `libcore` `dalvik.system.{BaseDexClassLoader, DexClassLoader, PathClassLoader, InMemoryDexClassLoader, DelegateLastClassLoader, DexPathList}` · Android 개발자 문서 `DexClassLoader`/`InMemoryDexClassLoader` (developer.android.com/reference/dalvik/system/) · Android "Safely load dynamic code" 보안 가이드

*다음 글: [AMS·ActivityTaskManagerService](/posts/android-expert-p2c10/).*
