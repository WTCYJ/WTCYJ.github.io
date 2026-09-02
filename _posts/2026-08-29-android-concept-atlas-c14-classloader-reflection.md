---
layout: post
title: "Android Security Concept Atlas C14 | 가상 실습 보고서 — ClassLoader·리플렉션·동적 코드 로딩, 정적 분석이 무너지는 곳"
date: 2026-08-29 23:08:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ClassLoader, DexClassLoader, InMemoryDexClassLoader, Reflection, HiddenAPI, Packer, DynamicCodeLoading, ConceptAtlas, 학습기록]
excerpt: "APK를 정적으로 다 뜯었는데 로직이 안 보인다면, 진짜 코드는 런타임에 로드됩니다. Android의 ClassLoader는 전부 BaseDexClassLoader + DexPathList 위의 얇은 껍질이고, 부모위임(parent-first)이 프레임워크 클래스를 단일 정의로 지키죠. 그런데 DexClassLoader는 임의 경로의 dex를, InMemoryDexClassLoader(API 26)는 디스크에 파일도 안 떨구고 ByteBuffer의 dex를 로드합니다 - 내가 분석한 한 상용 앱 패커가 Blowfish+SEED로 복호한 dex를 바로 이걸로 실행했죠. 그래서 동적 코드 로딩은 악성코드/패커의 1순위 회피 기법이고, 정적 APK 분석은 stub만 봅니다. 리플렉션은 setAccessible로 언어 접근은 뚫지만 A9+ hidden-API 강제는 못 뚫고요. 내 패커 RE 작업과 직결되는 Tier 2 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `getprop ro.zygote`, `getprop dalvik.vm.usejit`, `ps` |
| 관측 결과 | `zygote64`와 JIT 활성 상태를 확인했다. 비특권 앱의 전체 프로세스 열람 제한도 함께 관측했다. |
| 검증 한계 | OAT/VDEX 생성 정책은 빌드와 프로파일 상태에 따라 달라지므로 이 한 번의 캡처를 모든 Android 버전에 일반화하지 않는다. |

![C14 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-runtime.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C14 — ClassLoader·리플렉션·동적 코드 로딩
> **계층**: Tier 2 (Android Runtime) · **난이도**: 중급 · **선수 개념**: C13(ART), C07(DEX)
> **성격**: 보완 편.

C13에서 ART가 DEX를 실행한다 했습니다. 그 DEX를 **어떻게 로드하는가**, 그리고 그 로딩이 어떻게 **정적 분석을 무력화하는가**가 이 편입니다 — 내가 뜯은 한 상용 앱 패커의 핵심.

한 문장으로: **Android의 ClassLoader는 DexPathList 위의 얇은 껍질들이고, 동적 코드 로딩(런타임 복호 dex를 InMemoryDexClassLoader로)이 정적 APK 분석을 stub만 보게 만든다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **ClassLoader 계층**: 전부 `BaseDexClassLoader`+`DexPathList`(순서 있는 dex element) 위. Boot/Path/Dex/InMemory.
- **부모위임**(parent-first): 부모에게 먼저 물어보고 없을 때만 자기가 정의.
- **리플렉션**: `java.lang.reflect`로 이름으로 멤버 접근. A9+ **hidden-API 강제**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

DEX(C13)를 **로드하는 메커니즘**이자, **동적 코드 로딩이 정적 분석을 무너뜨리는 지점**입니다. 내 상용 앱 패커 작업(런타임 복호 dex)의 핵심이고, C48(무결성)·C16(정적≠실행)과 직결됩니다.

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

- **동적 코드 로딩(DCL) = 악성/패커 1순위 회피**: 코드가 분석 대상 APK에 없고 런타임에 (자산/네트워크/복호로) 로드됩니다. **한 상용 앱 패커**: 다단계 Blowfish+SEED로 복호한 dex를 `InMemoryDexClassLoader`(디스크 미접촉)로 실행 → 파일 기반 수집을 무력화.
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

## 호출 흐름

```
[ ClassLoader와 동적 코드 로딩(패커) ]

  BootClassLoader (프레임워크, 루트 부모)
       ↑ parent-first 위임
  PathClassLoader (앱 자신의 base/split dex)  ←── 정적 분석이 보는 것
       │
  DexClassLoader (임의 경로 dex)  /  InMemoryDexClassLoader (ByteBuffer, 파일 없음)
       └── 전부 BaseDexClassLoader + DexPathList(dex element 배열) 위

  패커(상용 앱): classes.dex=stub ──런타임──▶ Blowfish+SEED 복호 → dex(메모리)
       → InMemoryDexClassLoader.load  ← 진짜 코드(디스크 미접촉)
       분석: Frida로 로더 후킹 → dex 캡처/덤프 (정적 APK엔 없음)

  리플렉션: Class.forName/invoke/setAccessible(언어 접근만)
       └ A9+ hidden-API 강제(ART 조회층, 리플렉션+JNI)는 별개로 막음
```

## 실측으로 확인한 것

가상 실습 환경(codex-atlas-api33, x86_64, ART 13)에서 이 모듈의 핵심 주장을 실제 명령으로 확인했다.

**1) 부트 클래스패스는 모든 앱 프로세스에 매핑된다.** SystemUI(PID 742)의 `/proc/742/maps`에는 `BootClassLoader`가 여는 실제 jar들이 그대로 올라온다.

```console
$ adb shell 'cat /proc/742/maps | grep javalib | awk "{print \$6}" | sort -u'
/apex/com.android.art/javalib/apache-xml.jar
/apex/com.android.art/javalib/bouncycastle.jar
/apex/com.android.art/javalib/core-libart.jar
/apex/com.android.art/javalib/core-oj.jar
/apex/com.android.art/javalib/okhttp.jar
```

`core-oj`(java.* 표준 클래스)와 `core-libart`(ART 런타임 클래스)가 부트 클래스패스의 실체다. 앱의 `PathClassLoader`는 parent-first로 여기까지 위임하므로, 앱이 `java.lang.String`을 자기 dex에 재정의해도 부트가 먼저 답을 내 shadowing이 막힌다 — 질문 1의 안전 불변식이 프로세스 메모리 수준에서 확인된다.

**2) 앱 dex는 디스크 파일 + AOT 산출물(oat)로 실재한다.** 설치된 앱 하나(`com.example.visibilitylegacy`)의 코드 경로와 컴파일 산출물:

```console
$ adb shell pm path com.example.visibilitylegacy
package:/data/app/~~3DMBKse…==/com.example.visibilitylegacy-iJVP…==/base.apk
$ adb shell run-as com.example.visibilitylegacy ls oat
x86_64          # dex2oat가 만든 네이티브 산출물 디렉터리
```

`PathClassLoader`가 여는 `base.apk` 속 `classes.dex`는 실재하는 파일이고, 그 옆 `oat/x86_64/`는 이 dex를 AOT 컴파일한 결과다(실행 모드는 **C16**으로 이어진다). **정적 분석이 이 앱을 완전히 읽을 수 있는 건, dex가 디스크에 통째로 있기 때문이다.**

**3) 패커·`InMemoryDexClassLoader`는 (2)의 그림을 깬다.** 내가 실제로 뜯은 한 상용 앱의 `ExternalWebActivity` 패커 분석에서 `classes.dex`는 stub이었고, 진짜 코드는 런타임에 Blowfish+SEED로 복호돼 `InMemoryDexClassLoader.load`로 실행됐다 — 디스크 파일 없이 `ByteBuffer`의 dex를 바로 로드하는 A8.0(API 26)의 그 경로다. 이 경우 (2)처럼 `pm path`로 얻은 `base.apk`를 정적으로 뜯어도 stub만 나온다. 이것이 동적 코드 로딩이 정적 분석을 무력화하는 실제 기제이며, 대응은 로더 생성자 후킹 같은 **동적 관찰**이다.

## 소스로 확정한 것

측정으로 닫히지 않는 두 항목은 AOSP 소스와 공식 문서로 확정한다.

- **동적 로딩의 기제는 소스로 확정된다.** `DexClassLoader`/`InMemoryDexClassLoader` 생성자가 `DexPathList`에 dex element를 추가하고 `loadClass`가 그 배열을 순회하는 경로는 AOSP `BaseDexClassLoader`·`DexPathList` 소스에 그대로 있고, 패커가 런타임 복호 dex를 이 경로로 실행한다는 것은 (3)에서 짚은 기제 그대로다. 이 시리즈는 비무기화 원칙상 살아있는 패커를 언패킹하지 않으므로, 로더 생성자를 후킹해 로드되는 dex를 캡처하는 라이브 관찰은 그 대상 앱을 다룬 별도 분석 글의 몫으로 두고, 여기서는 경로·기제까지를 소스로 확정한다.
- **`setAccessible`과 hidden-API 강제가 별개 층이라는 것은 소스로 확정된다.** `setAccessible(true)`는 `java.lang.reflect.AccessibleObject`의 **언어 접근 검사**만 우회하고, A9+ non-SDK 차단은 `art/runtime/hidden_api.cc`의 **ART 멤버 조회 층**에서 리플렉션·JNI 양쪽에 강제된다 — 두 검사는 서로 다른 코드 경로라 `setAccessible`로 hidden-API가 열리지 않는다.

관련 근거: [AOSP `BaseDexClassLoader`](https://cs.android.com/android/platform/superproject/+/master:libcore/dalvik/src/main/java/dalvik/system/BaseDexClassLoader.java) · [`InMemoryDexClassLoader`(API 26 도입)](https://developer.android.com/reference/dalvik/system/InMemoryDexClassLoader) · [`art/runtime/hidden_api.cc`](https://cs.android.com/android/platform/superproject/+/master:art/runtime/hidden_api.cc) · [hidden-API 제한 정책](https://developer.android.com/guide/app-compatibility/restrictions-non-sdk-interfaces)

## 마치며

Android의 ClassLoader는 전부 `BaseDexClassLoader`+`DexPathList` 위의 얇은 껍질이고, parent-first 위임이 프레임워크 클래스를 단일 정의로 지킵니다. 그런데 `DexClassLoader`는 임의 경로의, `InMemoryDexClassLoader`(A8.0/26)는 디스크 파일도 없이 `ByteBuffer`의 dex를 로드합니다 — 내가 뜯은 한 상용 앱 패커가 Blowfish+SEED로 복호한 dex를 바로 이걸로 실행했죠. 그래서 동적 코드 로딩은 악성코드/패커의 1순위 회피이고, 정적 APK 분석은 stub만 봅니다. 리플렉션은 `setAccessible`로 언어 접근은 뚫지만 A9+ hidden-API 강제는 못 뚫습니다. 다음은 그 로드된 코드가 인터프리트/JIT/AOT 중 무엇으로 도느냐가 분석에 주는 차이, **C16**으로 이어집니다.
