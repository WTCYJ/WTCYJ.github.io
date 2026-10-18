---
layout: post
title: "bionic·linker·ELF·JNI"
date: 2026-12-02 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, bionic, linker, ELF, JNI]
excerpt: "System.loadLibrary('foo')는 그냥 dlopen이 아니다 — 앱의 classloader 네임스페이스를 거친다. 그래서 Android 7부터 앱은 아무 시스템 .so나 열지 못한다."
---

Android 앱이 네이티브 코드를 부르는 순간, 우리는 ART의 관리 세계에서 C/C++의 원시 세계로 넘어간다. 그 경계를 지키는 세 겹의 장치가 bionic(Android의 libc), 동적 링커(`linker64`), 그리고 JNI다. 개발자에게는 그냥 `System.loadLibrary("native-lib")` 한 줄이지만, 그 아래에서는 ELF 파싱·의존성 해결·재배치·네임스페이스 격리·심볼 바인딩이 순서대로 일어난다. 이 흐름을 모르면 "왜 내 .so가 안 열리지", "왜 시스템 라이브러리를 dlopen 못 하지", "왜 심볼을 못 찾지"에서 몇 시간을 태운다.

이 글은 실행 파일이 커널에서 링커로, 링커에서 JNI로 넘어가는 경로를 AOSP `bionic/`의 실제 동작과 함께 정리하고, 자작 앱·에뮬레이터로 그 흔적을 관측한 기록이다. 공격 실습이 아니라 구조 이해가 목적이다.

> **한 줄 결론**: 앱의 네이티브 로딩은 `dlopen`이 아니라 **classloader 네임스페이스를 거친 `android_dlopen_ext`**이며, 이 네임스페이스가 "앱이 어떤 .so를 열 수 있느냐"라는 신뢰 경계를 강제한다 — Android 7(API 24)부터.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 네 가지다. (1) 커널이 ELF 실행 파일을 로드하고 `PT_INTERP`가 가리키는 링커로 제어를 넘기는 방식, (2) `linker64`가 하는 일 — `DT_NEEDED` 의존성 해결, 재배치, 생성자 호출, (3) 링커 **네임스페이스**가 앱과 시스템 라이브러리를 격리하는 방식, (4) JNI가 관리 코드와 네이티브 코드를 잇는 두 가지 바인딩 방식.

선수 개념은 앞 장들에 깔려 있다. ClassLoader와 동적 코드 로딩(9장)을 알아야 `loadLibrary`가 왜 "어느 classloader의 네임스페이스"에서 열리는지가 보이고, ART의 실행 모델(8장)을 알아야 관리/네이티브 경계가 왜 문제인지 감이 온다. 프로세스·가상메모리(Part1의 개념편)를 알면 링커가 결국 무엇을 `mmap`하는지 이해된다. 이 장은 App→Framework→Binder→system_server→HAL→Kernel 흐름에서 **앱 프로세스가 실제로 코드를 메모리에 올리는 최하단 메커니즘**에 해당한다.

## 핵심 개념 — ELF에서 실행까지, 그리고 네임스페이스

**커널의 몫은 작다.** `execve`가 ELF 헤더를 확인하고, `PT_LOAD` 세그먼트를 매핑하고, `PT_INTERP`에 적힌 인터프리터(= 동적 링커)를 함께 매핑한 뒤, auxiliary vector를 세팅하고 링커의 진입점으로 점프한다. 나머지 전부 — 심볼 해결, 의존성 그래프, 재배치, 생성자 순서 — 는 **유저스페이스 링커의 정책**이다. `Source-confirmed`

Android에서 그 링커는 `/system/bin/linker64`(64비트)·`/system/bin/linker`(32비트)이고, `bionic/linker/`에 있다. 앱은 Zygote에서 fork되므로 `app_process64`의 `PT_INTERP`가 이미 `linker64`를 가리키고, libc·링커는 fork 시점에 이미 매핑돼 있다. `Source-confirmed`

링커가 하나의 ELF 오브젝트에 대해 하는 일을 순서로 보면:

| 단계 | 하는 일 | 관련 ELF 구조 |
|--|--|--|
| 1. 파싱 | 프로그램 헤더·동적 섹션 읽기 | `PT_LOAD`, `PT_DYNAMIC` |
| 2. 의존성 | `DT_NEEDED`를 재귀적으로 로드 | `DT_NEEDED`, `DT_SONAME` |
| 3. 재배치 | 심볼 주소 채우기 | `DT_RELA`/`DT_JMPREL`, `DT_SYMTAB` |
| 4. RELRO | GOT 등을 읽기 전용으로 `mprotect` | `PT_GNU_RELRO`, `DF_BIND_NOW` |
| 5. 초기화 | 생성자 실행 | `DT_INIT_ARRAY` |

여기서 흔한 오개념 하나 — "`.so`에도 `PT_INTERP`가 있다"는 착각. `PT_INTERP`는 **실행 파일**에만 있고 공유 라이브러리에는 없다. 라이브러리의 정체는 `DT_SONAME`으로, 의존성은 `DT_NEEDED`로 표현된다. `Source-confirmed`

**네임스페이스가 핵심이다.** Android 7.0(API 24)부터 링커는 라이브러리를 격리된 **네임스페이스**로 나눈다. 앱은 `classloader-namespace`에 속하고, 이 네임스페이스에서 열 수 있는 시스템 라이브러리는 `/system/etc/public.libraries.txt`에 나열된 NDK 공개 라이브러리(libc, liblog, libEGL, libjnigraphics 등)뿐이다. `libandroid_runtime.so`나 `libbinder.so` 같은 비공개 시스템 라이브러리를 `dlopen`하려 하면 `library "..." is not accessible for the namespace "classloader-namespace"`로 거부된다. `Source-confirmed` 네임스페이스 구성은 `ld.config` 파일에서 오며, 파일 경로는 릴리스에 따라 `/system/etc/ld.config.<ver>.txt`에서 `/linkerconfig/ld.config.txt`로 바뀌었다. `Reported`

> **[그림 1]** 자작 `libnative-lib.so`에 `readelf -d`를 돌려 `DT_NEEDED`(liblog/libc)·`DT_SONAME`·`FLAGS(BIND_NOW)`를 확인하고, `app_process64`에 `readelf -l`을 돌려 `INTERP=/system/bin/linker64`와 `GNU_RELRO` 세그먼트를 나란히 대조한 터미널 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 층에는 세 개의 경계가 겹쳐 있다.

- **경계 1 — 앱 ↔ 시스템 라이브러리.** 네임스페이스 격리가 강제하는 경계다. 앱이 시스템 내부 라이브러리의 비공개 심볼을 직접 끌어다 쓰는 것을 막는다. 이건 보안이면서 동시에 호환성 방어다(내부 심볼에 의존하던 앱이 OS 업데이트로 깨지는 것을 예방).
- **경계 2 — 관리 코드(ART) ↔ 네이티브 코드(C/C++).** JNI가 그 문이다. ART 쪽은 상대적으로 메모리 안전하지만, 문을 넘는 순간 경계 검사가 사라진다. **앱의 메모리 손상 취약점 대부분이 이 문 뒤의 네이티브 코드에 있다.** JNI 자체가 취약점은 아니지만, 공격 표면이 넓어지는 지점이다.
- **경계 3 — 링커가 강제하는 익스플로잇 완화.** 링커는 로드 시점에 재배치 후 `PT_GNU_RELRO` 영역을 읽기 전용으로 만들어 GOT 덮어쓰기를 어렵게 하고, 쓰기+실행 세그먼트나 텍스트 재배치를 거부한다. 이건 앱 프로세스 안에서 메모리 손상 → 코드 실행으로 가는 길을 좁힌다.

위협 모델을 오해하지 말 것: 여기서 "공격자"는 이미 앱 프로세스 안에서 실행되는 네이티브 코드다. 링커 완화는 그 코드가 임의 실행으로 승격하는 난이도를 올리는 것이지, 앱에 코드가 들어오는 것 자체를 막는 게 아니다. **크래시나 완화 우회를 곧바로 RCE로 부풀리면 안 된다.**

## 관측

전부 로컬 에뮬레이터(`google_apis` userdebug)와 자작 앱·자작 `.so`로만 확인한다. 제3자 앱·실기기·실서비스는 대상이 아니다.

관측 절차는 네 가지다.

```bash
# 1) .so의 동적 정보: 무엇에 의존하고, 어떤 완화 플래그가 켜졌나
readelf -d libnative-lib.so
# 2) 실행 파일의 인터프리터: 링커 경로 확인 (app_process64는 기기의 /system/bin 파일이라 먼저 pull)
adb pull /system/bin/app_process64 .
readelf -l app_process64 | grep -A1 INTERP
# 3) JNI 심볼: RegisterNatives용 JNI_OnLoad와 이름규칙 Java_ 심볼
nm -D --defined-only libnative-lib.so | grep -E 'JNI_OnLoad|Java_'
# 4) 네임스페이스 공개 목록 + 실제로 매핑된 링커
adb shell cat /system/etc/public.libraries.txt
adb shell "cat /proc/\$(pidof com.example.app)/maps" | grep linker64
```

`예시 출력(교체)`:

```
$ readelf -d libnative-lib.so
 0x0000000000000001 (NEEDED)   Shared library: [liblog.so]
 0x0000000000000001 (NEEDED)   Shared library: [libc.so]
 0x000000000000000e (SONAME)   Library soname: [libnative-lib.so]
 0x000000000000001e (FLAGS)    BIND_NOW
 0x000000006ffffffb (FLAGS_1)  Flags: NOW

$ nm -D --defined-only libnative-lib.so | grep -E 'JNI_OnLoad|Java_'
0000000000000c40 T JNI_OnLoad
0000000000000d10 T Java_com_example_app_MainActivity_stringFromJNI
```

읽는 법: `NEEDED`에 `liblog.so`·`libc.so`만 있으니 이 라이브러리는 공개 목록 안에서만 논다 — 네임스페이스 위반이 없다. `BIND_NOW`/`FLAGS_1: NOW`가 켜져 있으니 지연 바인딩 없이 로드 시점에 전부 재배치되고 RELRO가 완전 적용된다(Full RELRO). `nm -D`에 `JNI_OnLoad`와 `Java_com_example_app_...` 심볼이 둘 다 보이면, 이 라이브러리는 두 바인딩 방식을 다 쓸 수 있다는 뜻이다.

**JNI 바인딩의 두 경로.** ART가 네이티브 메서드를 찾는 방법은 두 가지다. (1) **이름 규칙** — `Java_` + 패키지·클래스명(점을 `_`로) + `_` + 메서드명. 이름 안의 언더스코어는 `_1`로, 오버로드는 시그니처를 덧붙여 구분한다. 이 심볼은 **최초 호출 시점에 지연 조회**된다. (2) **명시 등록** — `JNI_OnLoad`에서 `RegisterNatives`로 함수 포인터를 직접 등록. 둘 다 없으면 `UnsatisfiedLinkError`. `Source-confirmed` 그리고 `JNIEnv*`는 **스레드마다** 다르고 `JavaVM*`는 **프로세스 하나**다 — 네이티브에서 새 스레드를 만들면 `AttachCurrentThread`로 `JNIEnv`를 얻어야 한다. 이걸 빼먹고 다른 스레드의 `JNIEnv`를 재사용하는 게 JNI 크래시의 단골 원인이다. `Source-confirmed`

> **[그림 2]** 자작 앱을 에뮬레이터에서 실행한 뒤 `/proc/<pid>/maps`에서 `/system/bin/linker64`가 매핑된 줄과, 비공개 시스템 `.so`를 `dlopen` 시도했을 때 logcat에 뜨는 `is not accessible for the namespace "classloader-namespace"` 메시지를 함께 캡처 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

**왜 링커가 유저스페이스에 있나.** 커널은 인터프리터를 매핑하는 것까지만 안다. 심볼 해결·재배치·생성자 순서·네임스페이스 정책은 릴리스마다 진화하는 "정책"이고, 정책을 커널에 박으면 업데이트가 불가능하다. 그래서 이 모든 것이 교체 가능한 유저스페이스 링커로 빠져 있다. bionic이 Android 릴리스마다 재배치 압축(packed relocations)·16KB 페이지 정렬 같은 변화를 실을 수 있는 이유가 이것이다. `Inferred`

**왜 네임스페이스가 생겼나.** Android 7 이전에는 앱이 시스템 라이브러리의 비공개 심볼을 자유롭게 `dlopen`했다. 두 가지가 터졌다 — (a) OS가 그 내부 심볼을 바꾸면 앱이 깨지는 호환성 문제, (b) 앱이 프레임워크 내부에 직접 손을 대는 넓은 ABI/공격 표면. 해법은 링커 수준의 격리였다. "앱이 볼 수 있는 라이브러리"를 `public.libraries.txt`로 화이트리스트화하고, 나머지는 다른 네임스페이스에 숨긴다. 그래서 `System.loadLibrary`가 단순 `dlopen`이 아니라 **classloader의 네임스페이스를 인자로 넘기는** `android_dlopen_ext` 경로를 타는 것이다. `Source-confirmed`

**왜 JNI가 위험 지점인가.** 관리 코드에서 네이티브로 넘어가는 순간 배열 경계·타입·null 검사가 사라진다. `GetStringUTFChars`로 얻은 포인터를 놓아주지 않아 생기는 참조 누수, `Release` 없이 로컬 참조를 쌓아 터지는 로컬 레퍼런스 오버플로, 잘못된 `jobject`로 인한 메모리 손상 — 전부 문 이쪽(관리 코드)에서는 있을 수 없던 실수가 문 저쪽에서 되살아난 것이다. 그래서 개발/에뮬레이터 빌드에서는 **CheckJNI**(`-Xcheck:jni`)가 기본으로 켜져 이런 오용을 즉시 잡는다. `Source-confirmed`

## 버전 차이와 한계

- **네임스페이스 격리는 Android 7.0(API 24)부터.** 이전 targetSdk 앱에는 완화된 규칙이 적용된다(하위호환). `Source-confirmed`
- **텍스트 재배치 금지** — targetSdk 23 이상 앱은 `DT_TEXTREL`이 있으면 로드가 거부된다. `Reported`
- **쓰기+실행(W^X) 세그먼트 거부** — 최근 릴리스의 링커는 로드 세그먼트가 동시에 쓰기·실행이면 거부한다(정확한 API 경계는 원문 재확인 필요). `Reported`
- **16KB 페이지 크기** — Android 15(API 35) 이후 16KB 페이지 기기에서, ELF 세그먼트가 4KB 정렬만 돼 있으면 로드에 실패할 수 있다. 네이티브 라이브러리를 16KB 정렬로 다시 빌드해야 한다. `Reported`
- **에뮬레이터 한계** — x86_64 AVD에서는 x86_64용 `linker64`가 매핑되고, arm64 전용 하드웨어 완화(PAC/BTI/MTE)는 관측되지 않는다(1장의 이미지 선택 참고). 반면 네임스페이스 격리·RELRO·JNI 바인딩은 아키텍처와 무관하게 그대로 관측된다. `Inferred`

한계를 분명히: 이 글의 관측은 완화가 "켜져 있음"을 확인하는 수준이다. 완화 우회 가능성은 대상 코드·버전마다 다르므로, "RELRO가 있으니 안전"·"크래시 났으니 취약"처럼 단정하지 않는다.

## 정리

- 앱의 네이티브 로딩은 `dlopen`이 아니라 classloader 네임스페이스를 거치는 `android_dlopen_ext`이고, 이 네임스페이스가 "어떤 .so를 열 수 있느냐"를 강제한다(Android 7+).
- 커널은 인터프리터 매핑까지만, 나머지(의존성·재배치·RELRO·생성자)는 유저스페이스 `linker64`의 정책이다. `PT_INTERP`는 실행 파일에만, `DT_SONAME`/`DT_NEEDED`는 라이브러리에.
- JNI는 관리/네이티브 경계의 문이고, 바인딩은 이름 규칙(`Java_...`, 지연 조회) 또는 `RegisterNatives`(즉시 등록) 두 가지. `JNIEnv`는 스레드별, `JavaVM`은 프로세스별.

**점검 질문** — (1) `System.loadLibrary("x")`가 비공개 시스템 `.so`를 열지 못하는 이유는 무엇이고, 그 경계는 어디서 강제되는가? (2) 공유 라이브러리에 `PT_INTERP`가 없는 이유는? (3) `Java_` 이름 규칙과 `RegisterNatives`는 각각 언제 심볼이 해석되는가?

**참고** — [bionic (AOSP)](https://android.googlesource.com/platform/bionic/) · [JNI Tips](https://developer.android.com/training/articles/perf-jni) · [Native libraries namespaces / 7.0 변경](https://developer.android.com/about/versions/nougat/android-7.0-changes) · [Support 16 KB page sizes](https://developer.android.com/guide/practices/page-sizes)

*다음 글: [Perfetto·simpleperf·관측](/posts/android-expert-p2c21/).*
