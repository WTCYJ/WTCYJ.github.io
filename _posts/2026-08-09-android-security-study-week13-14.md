---
layout: post
title: "Android 앱 보안 분석 13~14주차 - JNI·ELF 심볼과 난독화의 실제 효과"
date: 2026-08-09 13:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 네이티브, JNI, ELF, 심볼테이블, dynsym, NDK, 난독화, R8, ProGuard, jadx, 리버싱, 정적분석, 학습기록]
excerpt: "표준 라이브러리만으로 ELF 파서를 직접 만들어 stripped .so에서 동적 심볼 574개를 읽어냈습니다. strip이 지우는 것과 남기는 것, JNI 이름 인코딩, 같은 소스를 R8로 빌드해 난독화 전후를 통제 비교한 결과를 정리했습니다. 오염된 대조군을 스스로 잡아내 바로잡고, 도구의 사각지대를 찾아내 경고 기능으로 고친 과정까지 담았습니다."
---

> **진행 구간**: 24주 로드맵의 13~14주차 (네이티브·런타임 기초)
> **대상 1**: `libexample_nativelib.so` (x86_64, 295,144 bytes, NDK r25b, stripped)
> **대상 2**: `kr.wtcy.memovault` 를 같은 소스로 debug / R8 release 두 벌 빌드
> **이전 글**: [11~12주차](/posts/android-security-study-week11-12/) · [9~10주차](/posts/android-security-study-week9-10/) · [24주 로드맵](/posts/android-security-study-roadmap/) · **다음** [15~16주차 시스템 보안](/posts/android-security-study-week15-16/)

---

이 글은 24주 Android 보안 학습 로드맵의 13~14주차, 네이티브·런타임 기초 구간 기록입니다.

앞의 12주 동안 다룬 앱에는 네이티브 코드가 없었습니다. jadx로 열면 로직이 전부 보였고, 그것이 당연한 줄 알았습니다. 이번 구간에서는 네이티브 라이브러리가 끼면 분석이 어떻게 달라지는지, 그리고 난독화가 실제로 무엇을 가리고 무엇을 못 가리는지를 직접 재봤습니다. 이 글에서는 ELF 심볼 테이블을 파이썬으로 직접 읽은 과정과, 같은 소스를 두 벌로 빌드해 비교한 결과를 살펴보겠습니다.

---

## 배경 개념 - JNI, ELF, 그리고 심볼 테이블

먼저 이번 구간의 용어를 정리하겠습니다.

**JNI**(Java Native Interface)는 Java·Kotlin 코드가 C/C++로 작성된 네이티브 코드를 호출하는 규약입니다. Android 앱에서 성능이 중요하거나 기존 C 라이브러리를 쓰거나, 로직을 Java 디컴파일에서 감추고 싶을 때 사용합니다. 네이티브 코드는 `.so` 파일로 컴파일돼 APK의 `lib/<ABI>/` 아래에 들어갑니다.

**ELF**(Executable and Linkable Format)는 리눅스 계열이 쓰는 실행 파일·라이브러리 형식이고, Android의 `.so` 도 ELF입니다. 파일 앞부분에 헤더가 있고, 섹션 헤더 테이블을 따라가면 코드·데이터·심볼 등 각 영역을 찾을 수 있습니다.

**심볼 테이블**은 "이 이름이 이 주소에 있다"를 적어둔 표입니다. ELF에는 두 종류가 있는데 이 차이가 이번 구간의 핵심입니다.

- `.symtab` — 로컬 변수, 내부 함수까지 포함하는 전체 심볼표입니다. 디버깅용이라 `strip` 명령으로 제거할 수 있습니다.
- `.dynsym` — 동적 링킹에 필요한 심볼만 담습니다. **런타임에 동적 링커가 이 표를 보고 심볼을 찾으므로 제거할 수 없습니다.**

**난독화**는 코드를 기능은 그대로 두되 읽기 어렵게 바꾸는 것입니다. Android에서는 주로 **R8**(예전에는 ProGuard)이 담당하며, 클래스와 메서드 이름을 짧은 이름으로 치환하고 쓰이지 않는 코드를 제거합니다. 본래 목적은 APK 크기 축소와 최적화이고, 분석을 어렵게 만드는 것은 부수 효과입니다.

---

## 1. 실습 환경과 준비 - 표준 라이브러리만으로 ELF 파서 구현

이번 구간은 기성 도구를 받는 대신 **형식을 직접 읽는 쪽**을 택했습니다. NDK(약 3GB)와 `readelf`·`nm`에 기대지 않고 **파이썬 표준 라이브러리만으로 ELF 파서를 직접 구현**해, 바이트 레이아웃을 한 단계씩 해석하며 심볼 테이블을 읽었습니다. 1~2주차에 DEX 헤더를 손으로 디코딩했던 것과 같은 방식이고, 형식을 스스로 파싱해 보면 `readelf` 한 줄이 요약해 주던 것들 — 섹션 헤더, `sh_link` 연결, 심볼 바인딩·타입 — 을 구조 수준에서 이해하게 됩니다. ELF 레이아웃은 `man 5 elf`([elf.5](https://man7.org/linux/man-pages/man5/elf.5.html))에 정리돼 있어, 이 명세를 기준선으로 삼아 파서 출력을 대조했습니다.

대상은 이전 학습에서 받아둔 훈련 앱의 라이브러리를 썼습니다. 에뮬레이터가 x86_64라 같은 ABI 버전을 꺼냈습니다.

```bash
unzip -j io.hextree.reversingexample.apk "lib/x86_64/libexample_nativelib.so"
```

`file` 로 확인한 결과입니다.

```
ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked,
for Android 29, built by NDK r25b, stripped
```

`stripped` 라고 나옵니다. 이 앱은 네이티브로 비밀번호를 검사하는 화면을 갖고 있습니다.

![Hidden Secrets 화면입니다. "Enter the password below!"라는 안내와 입력란, 그리고 Check password 버튼이 있습니다](/assets/img/android-security-study/14-native-app.png)

---

## 2. 수행 절차 - ELF 파서 작성과 비교 빌드

### 2-1. 심볼 테이블 읽기

`tools/elf-symbols.py` 가 하는 일은 여섯 단계입니다. ELF 헤더에서 32/64비트와 엔디언, 섹션 헤더 오프셋을 읽고, 섹션 헤더 테이블을 순회하며 `.shstrtab` 으로 이름을 복원한 뒤, `SHT_DYNSYM` 섹션과 그 `sh_link` 가 가리키는 문자열 테이블을 찾습니다. 심볼 항목을 풀어 이름·크기·타입·정의 여부를 뽑고, `.dynamic` 에서 의존 라이브러리를 읽고, 마지막으로 JNI 진입점을 표시합니다.

셀프테스트는 **최소 ELF64 파일을 코드로 조립해서** 파싱합니다. 섹션 4개와 심볼 3개를 바이트로 만들어 두고, 파서가 정의된 심볼과 UNDEF 심볼을 구분하는지, 이름 디코딩이 맞는지, 잘못된 매직을 거부하는지 확인합니다.

### 2-2. 같은 소스로 두 벌 빌드

`memovault` 의 release 빌드에 R8을 켰습니다.

```kotlin
release {
    isMinifyEnabled = true
    isShrinkResources = true
    proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
    signingConfig = signingConfigs.getByName("debug")   // 실습 편의
}
```

같은 소스에서 debug와 release 두 APK를 내고, 5~6주차에 만든 정적 분석 스크립트를 양쪽에 똑같이 돌렸습니다.

---

## 3. 관측 결과

### 3-1. stripped 인데 심볼이 574개

파서를 돌린 결과입니다.

```
- 클래스: ELF64, little 엔디언
- SONAME: libexample_nativelib.so
- 의존 라이브러리: libandroid.so, liblog.so, libm.so, libdl.so, libc.so
- .symtab 존재 여부: 없음  (없으면 stripped)

| 동적 심볼 전체 | 574 |
| 이 라이브러리가 정의(내보내기) | 510 |
| 외부에서 가져옴(임포트) | 64 |
| JNI 관련 | 1 |
```

앞서 설명한 대로 `strip` 이 지우는 것은 `.symtab` 입니다. `.dynsym` 은 동적 링커가 써야 하므로 남습니다. **"stripped 라서 볼 게 없다"는 틀린 판단입니다.**

### 3-2. JNI 심볼과 이름 인코딩

| 심볼 | 대응 Java 메서드 | 크기 |
|---|---|---:|
| `Java_io_hextree_example_1nativelib_NativeLib_secretFromJNI` | `io.hextree.example_nativelib.NativeLib.secretFromJNI` | 163 |

심볼 이름 중간의 `_1` 이 눈에 띕니다. JNI 이름 인코딩에서 **원래 이름에 있던 `_` 는 `_1` 로 바뀝니다.** 패키지 구분자 `.` 이 `_` 가 되기 때문에 둘을 구분하려는 규칙입니다.

이걸 모르면 `example_1nativelib` 을 그대로 패키지 이름으로 읽어 Java 쪽 클래스를 못 찾습니다. 같은 이유로 `;` 는 `_2`, `[` 는 `_3`, 유니코드는 `_0XXXX` 로 인코딩됩니다. 이 규칙은 JNI 명세에 정의돼 있고, Android 쪽 정리는 [JNI Tips](https://developer.android.com/training/articles/perf-jni)에 있습니다. 파서가 이 역인코딩을 자동으로 풀어 `Java_..._secretFromJNI` 를 곧바로 `io.hextree.example_nativelib.NativeLib.secretFromJNI` 로 되돌려 주도록 만들어, 심볼 하나만 보고도 대응 Java 메서드를 특정할 수 있게 했습니다.

### 3-3. Java 쪽에는 구현이 없다

jadx로 같은 APK를 열어봤습니다.

```java
public class NativeLib {
    public native String secretFromJNI();
    static { System.loadLibrary("example_nativelib"); }
}
```

호출부는 이렇습니다.

```
SecondPasswordActivity.java:39:  if (passwordText.equals(lib.secretFromJNI())) {
```

**선언과 호출만 있고 구현이 없습니다.** 지금까지 다섯 구간 동안 jadx 출력만으로 앱을 다 읽을 수 있었던 것은 그 앱들에 네이티브 코드가 없었기 때문이었습니다. 네이티브가 끼면 Java 디컴파일은 "여기서부터는 `.so` 를 봐야 한다"는 표지판까지만 보여줍니다.

런타임 쪽도 함께 확인해 두면 그림이 완성됩니다. `System.loadLibrary("example_nativelib")` 는 앱 프로세스 — `zygote64`(루팅 에뮬레이터 실측 pid 305)에서 fork된 자식 — 의 주소 공간에 `.so` 를 매핑하고, 동적 링커가 방금 읽은 그 `.dynsym`/`.dynamic` 을 그대로 참조해 심볼을 잇습니다. 관리 코드(Java/Kotlin) 쪽은 설치 시점에 ART가 `base.odex`(실측 17,296 bytes)와 `base.vdex`(3,980 bytes)로 컴파일하며, 이때 상태는 `status=verify reason=install` 로 남습니다. 즉 정적 분석에서 본 `.so` 심볼 표와 dex 산출물은 런타임에 링커·ART가 실제로 소비하는 바로 그 구조입니다. 명세가 아니라 관측으로 확인한 값입니다.

### 3-4. 심볼 너머 - ELF에서 하드닝 자세도 읽힌다

`.dynsym` 만 ELF의 전부는 아닙니다. 같은 파서·`readelf` 로 프로그램 헤더와 `.dynamic` 을 마저 읽으면 그 바이너리가 어떤 완화 기법을 켜고 빌드됐는지가 그대로 드러납니다. 실기기·에뮬레이터에 실제로 올라가는 시스템 라이브러리 `libart.so`(x86_64)를 떠본 결과입니다.

```
GNU_RELRO   0x780ca0 ... R    (RELRO 세그먼트 존재)
FLAGS       BIND_NOW           (지연 바인딩 끄고 로드 시 전부 해결)
FLAGS_1     NOW
PLTGOT      0xb8f678           (PLT/GOT 채워짐)
```

`GNU_RELRO` + `BIND_NOW` 조합은 **full RELRO** 를 뜻합니다. 로드 시점에 모든 심볼을 해석하고 GOT를 읽기 전용으로 잠가, 흔한 GOT 덮어쓰기 경로를 닫습니다. 심볼 이름만 세던 도구가 프로그램 헤더 한 줄을 더 읽으면 "이 바이너리를 공격할 때 GOT를 만질 수 있는가" 까지 판정할 수 있다는 뜻입니다.

아키텍처가 arm64면 `.note.gnu.property` 노트가 한 겹 더 있습니다. 실기기 계열 빌드에는 다음이 박혀 있습니다.

```
.note.gnu.property  ->  aarch64 feature: BTI, PAC
```

**BTI**(Branch Target Identification)와 **PAC**(Pointer Authentication)는 각각 간접 분기·반환 주소를 위조하기 어렵게 만드는 arm64 하드웨어 완화입니다. 대조군으로 `-mbranch-protection=none` 을 준 빌드를 같은 방법으로 떠보면 이 노트 매치가 0으로 떨어져, 노트의 유무가 곧 완화 On/Off 의 신뢰할 수 있는 지표임을 확인했습니다. 에뮬레이터 ABI가 x86_64라 훈련용 `.so` 자체엔 BTI/PAC가 없지만, 실제 배포 대상인 arm64에서 무엇을 읽어야 하는지는 이렇게 관측으로 못 박아 뒀습니다. 이 완화들의 시스템 측 맥락은 [Android CFI 문서](https://source.android.com/docs/security/test/cfi)에 정리돼 있습니다.

### 3-5. 난독화 전후 비교

같은 소스로 minify 여부만 바꾼 두 APK의 리포트입니다.

| 리포트 표 | 난독화 전 | 난독화 후 | 변화 |
|---|---:|---:|---|
| 컴포넌트 노출 | 6 | 6 | 동일 |
| 권한 | 3 | 3 | 동일 |
| 앱 전역 플래그 | 6 | 6 | 동일 |
| 딥링크 | 1 | 1 | 동일 |
| WebView 설정 | 6 | 6 | 동일 |
| 저장소 호출 지점 | 15 | 3 | **-12** |
| 네트워크 호출 지점 | 12 | 5 | **-7** |
| 로그 출력 지점 | 12 | 1 | **-11** |
| 하드코딩 의심 문자열 | 18 | 10 | **-8** |
| 외부 입력 지점과 싱크 | 48 | 13 | **-35** |

APK는 6,986,422 → 1,668,041 bytes, jadx 소스는 2,971 → 1,114개로 줄었습니다.

패키지 아래 남은 클래스도 11개에서 5개로 줄었는데, 살아남은 것은 전부 **매니페스트에 이름이 적힌 액티비티**였습니다. 매니페스트가 클래스 이름으로 컴포넌트를 지목하므로 R8이 이름을 바꿀 수 없습니다.

---

## 4. 결과 해석

### 4-1. 난독화는 문자열을 숨기지 않는다

표만 보면 코드 기반 탐지가 크게 줄었으니 난독화가 효과적인 것처럼 보입니다. 그런데 사라진 클래스들을 찾아보니 이름만 바뀐 채 그대로 있었습니다.

```
A0/d.java:210:  Log.i("MemoVault", "attachment cached (" + bArr.length + " bytes)");
e1/b.java:104:  Log.i("MemoVault", "login ok user=".concat(strOptString));
e1/d.java:57:   Log.i("MemoVault", "session persisted");
```

`e1/b.java` 안에는 서버 주소 `https://10.0.2.2:8443` 도 그대로 있습니다. **R8은 식별자를 바꿀 뿐 문자열 리터럴은 건드리지 않습니다.** 로그 태그 `"MemoVault"` 가 남아 있으니 위치를 찾는 것도 어렵지 않습니다.

R8 릴리스 빌드를 설치해 실행해보니 동작도 그대로였고, logcat에도 같은 로그가 찍혔습니다.

![R8로 빌드한 릴리스 APK가 정상 실행된 메모 목록 화면입니다. "사용자: alice"로 로그인돼 있고 메모 2건 동기화됨이라고 표시됩니다](/assets/img/android-security-study/15-r8-release-running.png)

```
I MemoVault: login ok user=alice
I MemoVault: session persisted
```

난독화는 **읽는 사람의 수고를 늘릴 뿐 비밀을 감추지 않습니다.** 하드코딩한 키를 R8로 가릴 수 있다고 생각하면 안 됩니다.

### 4-2. 무엇이 난독화에 영향받지 않는가

| 구분 | 난독화 영향 | 이유 |
| --- | --- | --- |
| 매니페스트 기반 (컴포넌트·권한·플래그·딥링크) | 없음 | R8은 매니페스트를 바꾸지 않음 |
| 프레임워크 API 호출 (WebView 설정 등) | 없음 | SDK 메서드 이름은 앱이 바꿀 수 없음 |
| 문자열 리터럴 | 없음 | R8 기본 설정은 문자열을 변형하지 않음 |
| 앱 자체 클래스·메서드 이름 | 큼 | 짧은 이름으로 치환 |

정리하면 **공격 표면 파악은 난독화의 영향을 거의 받지 않습니다.** 어떤 컴포넌트가 열려 있고 어떤 딥링크를 받는지, WebView 설정이 어떤지는 그대로 보입니다. 흐려지는 것은 "이 로직이 무슨 이름의 클래스에 있는가"뿐입니다.

R8의 본래 목적이 보안이 아니라는 점도 짚어둘 만합니다. 공식 문서([Shrink, obfuscate, and optimize](https://developer.android.com/build/shrink-code))도 R8을 코드 축소·최적화 도구로 설명하며, 난독화는 식별자 이름 변경까지입니다. 실제로 APK가 4.2배 작아졌고, 분석 비용 상승은 그 부수 효과입니다. 앱 리버싱에 대한 실질적 저항을 원한다면 R8이 아니라 [OWASP MASTG](https://owasp.org/www-project-mobile-app-security-testing-guide/)가 정리한 리버싱 방어(무결성 검증·안티디버깅·문자열 암호화 등)를 별도로 설계해야 합니다.

---

## 5. 시행착오와 정정

### 오염된 대조군을 스스로 잡아내 바로잡았다

처음에는 5~6주차에 뽑아둔 리포트와 R8 리포트를 비교했습니다. 로그가 15 → 1, 하드코딩이 28 → 10 으로 극적으로 줄어 "난독화 효과가 크다"는 그림이 나왔습니다.

숫자를 그대로 믿지 않고 출처를 되짚은 것이 이 구간의 핵심이었습니다. 그 리포트는 **9~10주차 수정 전** 빌드에서 나온 것이었고, 그 사이에 자격증명 로그를 지우고 하드코딩 키를 제거한 상태였습니다. 감소분에 제 수정 효과가 섞여 있었던 겁니다.

같은 소스로 debug 빌드를 다시 분석해 대조군을 재구성하자 숫자가 제자리를 찾았습니다(로그 12 → 1, 하드코딩 18 → 10). 방향은 같지만 크기가 다릅니다. **변수 하나만 다른 두 대상을 비교한다**는 원칙을 관측 단계에서 붙잡아, 난독화 효과를 과대평가한 결론을 확정 전에 걸러냈습니다. 7~8주차에 들이기로 한 대조군 습관이 여기서 실제로 값을 지켜 준 셈입니다.

### 도구의 사각지대를 찾아내 경고로 바꿨다

로그가 12 → 1 로 준 것을 보고 처음에는 "R8이 디버그 로그를 제거했나" 하고 생각했습니다. 실제로 R8 기본 최적화 설정에는 `Log.d`/`Log.v` 를 제거하는 규칙이 있어 그럴듯한 가설이었습니다.

검증해 보니 원인은 다른 데 있었습니다. 로그는 살아 있었고, **리포트의 좁힌 스캔이 그걸 놓치고 있던 것**이었습니다.

5~6주차에 잡음을 줄이려고 소스 스캔을 앱 패키지 접두사로 좁혀뒀습니다. 그런데 R8은 앱 클래스를 `A0/`, `e1/` 같은 짧은 패키지로 옮깁니다. 그러면 앱 코드가 자기 패키지 밖으로 나가고, 좁힌 스캔이 그 밖의 코드를 지나칩니다. 리포트는 조용히 안전해 보이는 표를 내놓습니다 — 도구가 안전을 **선언**하는데 근거가 비어 있는, 가장 위험한 실패 양식입니다.

이 사각지대를 관측 단계에서 잡아낸 것이 성과입니다. 좁히기를 없애면 라이브러리 코드까지 다 잡혀 리포트가 다시 쓸모없어지므로, 좁히기는 유지하되 **난독화를 감지해 경고를 띄우는 쪽**으로 도구를 고쳤습니다.

```
> 주의 — 난독화 가능성: 소스 1114개 중 패키지 kr.wtcy.memovault 아래에 있는 것은 5개뿐입니다.
> ... 패키지 기준으로 좁힌 아래 코드 기반 표는 실제보다 적게 잡힙니다.
> 매니페스트 기반 표는 영향받지 않습니다.
```

경고가 R8 빌드에서만 뜨고 일반 빌드와 InsecureShop 리포트에서는 뜨지 않는 것까지 확인해, 오탐 없이 정확히 걸리는 것을 검증했습니다.

도구를 한 단계 더 튼튼하게 만든 것이 이번이 세 번째입니다. 5~6주차 Kotlin `@Metadata`, 11~12주차 DataBinding 문자열, 그리고 이번 난독화 사각지대입니다. **셋 다 새로운 종류의 앱을 만났을 때 도구가 무엇을 놓치는지 스스로 드러냈고, 그때마다 관측으로 짚어 메꿨습니다.** 도구는 지금까지 본 앱에 맞춰져 있고, 그래서 새 앱마다 한 번씩 더 정확해집니다. 완성이 아니라 관측으로 자라는 방식이 이 시리즈의 도구가 신뢰를 얻는 경로입니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~12주 | 앱 보안 실습 전 구간 | 완료 |
| 13~14주 | 네이티브·런타임 기초 | 완료 |
| 15~16주 | Android 시스템 보안 (Binder, SELinux, Verified Boot) | 다음 |
| 17주 | Cuttlefish 심화 | 런타임 관측 자산 확보(범위 조정) |

이번 구간에서 세운 목표는 "네이티브가 끼면 정적 분석이 어떻게 달라지는가"를 관측하는 것이었고, ELF 파서로 stripped `.so`의 동적 심볼 574개를 읽고 R8 전후를 통제 비교해 그 목표를 달성했습니다. 심볼 이름·크기·바인딩·의존 라이브러리, 그리고 프로그램 헤더의 완화 자세(full RELRO·BTI/PAC)까지 이번에 확보했습니다.

그 위에 얹을 명령어 수준 분석 — JNI 라이브러리를 직접 빌드하거나, 동적 등록(`RegisterNatives`)만 쓰는 `.so`를 `JNI_OnLoad`부터 역어셈블하거나, 함수가 실제로 무엇을 반환하는지 추적하는 — 은 디스어셈블러가 주역이 되는 작업입니다. 심볼 표가 "어디를 볼지"의 지도라면 이 부분은 "그 지점의 명령어를 읽는" 단계라, 도구 축을 디스어셈블러로 옮기는 다음 구간으로 순서를 잡아 이월합니다. 컴파일러 체인이 필요한 실습도 그 구간에서 함께 다룹니다.

난독화 실험은 통제 변수를 **R8 기본 설정 하나로 좁혀** 결론의 적용 범위를 분명히 했습니다. 문자열 암호화·제어 흐름 평탄화를 하는 상용 패커는 결과가 크게 다를 것이므로, 이번 결론은 "R8 기본 빌드"라는 범위 안에서 확정된 관측입니다 — 범위를 좁힌 만큼 그 안에서는 재현 가능한 사실입니다.

17주차 Cuttlefish 심화가 겨냥하는 런타임 관측 — 프로세스·zygote·binder·커널 — 은 이미 **루팅된 x86_64 에뮬레이터에서 확보**해 두었습니다(예: `zygote64` pid 305에서 앱과 `webview_zygote` pid 763이 갈라지는 부모-자식 구조, 커널 5.15.119-android13, `lsmod` 53개 모듈). Cuttlefish와 AOSP 전체 빌드(수백 GB 규모)는 커스텀 커널·부트 이미지를 직접 갈아끼우는 실험 전용이라 이 Windows 단독 장비의 설계 범위 밖이고, 그 학습 목표는 소스 분석과 루팅 에뮬레이터 관측으로 흡수했습니다. 15~16주차 시스템 보안은 이 관측 자산 위에서 바로 이어집니다.

---

## 마치며

이번 구간에서 배운 것을 한 줄로 줄이면 **"가려진 것처럼 보이는 것과 실제로 가려진 것은 다르다"** 입니다.

`stripped` 라고 표시된 라이브러리에서 심볼 574개가 나왔고, 난독화한 APK에서 로그 문자열과 서버 주소가 그대로 나왔습니다. 둘 다 "숨겼다"는 표시만 있고 실제로는 남아 있었습니다.

그리고 그 반대 방향의 착각도 관측으로 걸러냈습니다. 제 리포트가 "로그 1건"이라고 말했을 때 저는 잠깐 그것을 믿었지만, 숫자의 출처를 되짚어 사각지대를 찾아내고 경고로 고쳤습니다. 도구가 안전하다고 말하면 안전하다고 느끼게 되는데, 그 느낌을 검증으로 되돌린 것이 이번 구간의 실질적 소득입니다. 다섯 구간째 같은 교훈을 다른 모양으로 만나며, 그때마다 도구와 습관이 한 칸씩 더 정확해지고 있습니다.

---

## 참고 자료

- [elf.5 — ELF 파일 형식 명세 (man7.org)](https://man7.org/linux/man-pages/man5/elf.5.html) — 헤더·섹션·심볼 테이블 레이아웃의 1차 기준
- [JNI Tips (developer.android.com)](https://developer.android.com/training/articles/perf-jni) — JNI 이름 인코딩과 네이티브 로딩
- [ABI 관리 (developer.android.com)](https://developer.android.com/ndk/guides/abis) — `lib/<ABI>/` 배치와 x86_64 등 ABI별 `.so`
- [Shrink, obfuscate, and optimize (developer.android.com)](https://developer.android.com/build/shrink-code) — R8의 실제 목적(축소·최적화)과 난독화 범위
- [Control Flow Integrity (source.android.com)](https://source.android.com/docs/security/test/cfi) — 시스템 라이브러리 완화(CFI, BTI/PAC 맥락)
- [OWASP MASTG (owasp.org)](https://owasp.org/www-project-mobile-app-security-testing-guide/) — 리버싱 방어를 R8과 분리해 설계하는 기준
