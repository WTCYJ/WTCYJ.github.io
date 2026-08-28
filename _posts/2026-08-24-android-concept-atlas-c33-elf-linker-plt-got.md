---
layout: post
title: "Android Security Concept Atlas C33 | 가상 실습 보고서 — ELF·동적 링커·PLT/GOT, 정적 파일이 살아있는 프로세스가 되기까지"
date: 2026-08-24 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ELF, DynamicLinker, linker64, bionic, PLT, GOT, RELRO, BIND_NOW, Relocation, Relr, LinkerNamespace, JNI, GNUProperty, BTI, PAC, ConceptAtlas, 학습기록]
excerpt: "13~14주차에서 ELF 파서를 직접 짜고 심볼 테이블을 손으로 디코딩했습니다. 그건 정적 파일이었습니다. 이 글은 그 파일이 linker64에 의해 로드·연결·초기화되어 살아있는 프로세스가 되는 동적 과정을 다룹니다. 그리고 Android가 데스크톱 리눅스와 다르게 내린 두 선택 — lazy 바인딩을 아예 안 하고 full RELRO+BIND_NOW를 기본으로 하는 것, 그리고 링커 네임스페이스로 앱과 시스템 라이브러리를 가르는 것 — 이 이 층의 공격 표면을 어떻게 바꾸는지 봅니다. C37의 완화(BTI/PAC 노트, RELRO)가 실리는 자리가 바로 여기입니다. Concept Atlas의 일곱 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `uname -a`, `/proc/cpuinfo`, NDK JNI 빌드, UBSan 패치 전·후 실행 |
| 관측 결과 | Android 13 기반 Linux 5.15 x86_64 커널을 확인하고, NDK 27로 JNI 공유 라이브러리와 UBSan 대조군을 빌드·실행했다. |
| 검증 한계 | 범용 AVD에 없는 벤더 드라이버와 KASAN 커널은 실행하지 않았으며, 해당 항목은 공개 소스·설정 분석 결과로 구분한다. |

![C33 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C33 — ELF·linker·PLT/GOT
> **계층**: Tier 6 (네이티브·커널) · **난이도**: 고급 · **선수 개념**: C05(예외 수준·메모리 보호), C15(JNI·네이티브 라이브러리 로딩)
> **성격**: 보완 편. ELF 기초는 13~14주차에서 실측했으므로 요약·진단으로 넘기고, 동적 링커·PLT/GOT·RELRO에 깊이를 둡니다.
> **완료 기준**: GOT 항목 하나를 로드 전·후로 관찰해 Android에서 이미 해석·읽기전용임을 설명할 수 있다.

13~14주차에서 저는 ELF 파서를 직접 짜서 심볼 테이블을 읽고, stripped인데도 심볼이 574개 남아 있는 것을 세고, JNI 이름 인코딩을 손으로 디코딩했습니다. 그건 전부 **디스크 위의 정적 파일**을 연 것이었습니다. 이 모듈은 그 다음을 다룹니다. 그 파일이 `linker64`에 의해 로드되고, 재배치되고, 연결되고, 초기화되어 **EL0에서 살아 도는 프로세스**가 되는 동적 과정입니다.

이 층은 두 이웃 사이에 있습니다. 아래로는 C05(네이티브 코드가 도는 EL0, 그리고 페이지를 로드 후 읽기전용으로 만드는 MMU 기능), 위로는 C37(그 완화들이 실려 있는 자리 — BTI/PAC 노트는 바로 ELF의 `.note.gnu.property`에 있습니다). 그래서 이 글은 C37의 RELRO와 BTI/PAC를 "어디에 어떻게 실려서 강제되는가"의 관점에서 다시 만납니다.

## 배경 개념 - 정적 이미지와 그것을 살리는 링커

- **ELF과 세그먼트**: 실행 파일·공유 라이브러리의 형식. 링커가 실제로 보는 것은 섹션(`.text` 등)이 아니라 **프로그램 헤더의 세그먼트**입니다. `PT_LOAD`(메모리에 매핑할 조각), `PT_DYNAMIC`(동적 연결 정보표), `PT_INTERP`(누가 이걸 연결할지 = `/system/bin/linker64`), `PT_GNU_RELRO`(연결 후 읽기전용으로 만들 구간).
- **동적 링커 `linker64`**: 모든 arm64 프로세스의 `PT_INTERP`인 static PIE. 커널이 이걸 먼저 매핑하고 제어를 넘깁니다. glibc의 `ld-linux-aarch64.so.1`에 해당하지만, Android에는 **아키텍처별 링커도, `ldconfig`도, `ld.so.cache`도 없습니다** — 링커는 하나뿐입니다.
- **재배치(relocation)**: PIE/PIC는 어느 주소에 실릴지 모른 채 빌드되므로, 로드 후 실제 주소로 값을 채워 넣어야 합니다. 그 "어디에 무엇을 채워라"의 목록이 재배치 항목입니다.
- **GOT/PLT**: 외부(다른 모듈) 함수·데이터를 부를 때 거치는 **간접 테이블**. GOT는 포인터 배열, PLT는 그 GOT를 읽어 점프하는 코드 스텁.
- **RELRO**: 재배치가 끝난 뒤 그 테이블 구간을 `mprotect`로 읽기전용으로 얼리는 하드닝. C05에서 말한 "연결 후 페이지를 읽기전용으로" 기능의 구체적 사용처입니다.

이 정도를 깔고 여덟 질문으로 조립합니다. ELF 헤더·심볼 테이블은 NDK로 빌드한 증거 앱의 실제 공유 라이브러리를 `llvm-readelf`로 다시 확인하고, 원시 결과를 호스트 검증 로그에 연결합니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

EL0 네이티브 코드의 **파일 형식(ELF)이자, 그것을 프로세스로 만드는 로더(링커)**입니다. 앱이 `System.loadLibrary`로 `.so`를 올릴 때, 그 파일을 지도로 삼아 메모리에 펼치고 심볼을 잇는 주체가 `linker64`입니다. 13~14주차가 이 지도를 **손으로 판** 것이라면, 이 모듈은 그 지도가 **실제로 실행되는** 과정입니다. 그리고 C37의 완화들(RELRO, BTI/PAC 노트)이 이 층의 메타데이터로 표현되고 링커에 의해 강제됩니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

`linker64`는 EL0에서, **연결 대상과 같은 프로세스 안**에서 돕니다(별도 특권 없음). 로드 순서는 이렇습니다.

1. 커널이 `PT_INTERP`(`linker64`)를 매핑하고 제어를 넘김.
2. 링커가 모든 `PT_LOAD` 세그먼트를 담을 **연속 span 하나**를 예약(상대 오프셋 보존)하고, 각 세그먼트를 `p_flags` 권한으로 `mmap`, `.bss` 꼬리를 0으로 채움.
3. `PT_DYNAMIC`을 읽어 재배치·심볼·초기화 표의 위치를 파악.
4. **재배치 적용** → **초기화 실행**(`DT_PREINIT_ARRAY`(실행파일만) → `DT_INIT` → `DT_INIT_ARRAY`, 의존성 먼저).

한 가지 자주 헷갈리는 지점: `dlopen`/`dlsym`/`dlclose`는 libc가 아니라 **링커 안에** 구현돼 있습니다. 앱이 링크하는 공개 `dl*` 심볼은 얇은 스텁 라이브러리 **`libdl.so`**가 export하며, 그 스텁이 링커 내부(`__loader_dlopen` 등)로 포워딩합니다. (링커 자신의 soname인 `ld-android.so`는 `__loader_*`/`__cfi_*` 같은 내부 심볼을 export하지, 공개 `dl*`을 export하지 않습니다 — 둘을 바꿔 말하지 않도록.)

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **`DT_NEEDED`는 파일명이 아니라 soname입니다.** 링커는 후보의 `DT_SONAME`과 대조해 찾고 네임스페이스 안에서 soname으로 refcount합니다. 그래서 `.so` 파일 이름을 바꿔도 `DT_NEEDED` 해석은 바뀌지 않습니다.
- **심볼은 평평한 전역이 아닙니다.** bionic은 로컬 그룹+전역 그룹에서 찾고, `dlopen`은 기본 `RTLD_LOCAL`입니다. 그리고 **링커 네임스페이스**(Android 7/API 24~)가 앱과 시스템 라이브러리를 벽으로 가릅니다.
- **앱은 아무 `/system` 라이브러리나 못 엽니다.** 앱 네임스페이스에는 `public.libraries.txt`에 있는 공개 NDK 라이브러리(libc, libm, libdl, liblog, libandroid, libEGL, libGLESv2, libvulkan …)만 노출됩니다. 사설 라이브러리를 `dlopen`하면 `not found`가 아니라 **`is not accessible for the namespace`**로 실패합니다 — 이 메시지가 파일 부재가 아니라 네임스페이스 거부의 신호입니다.
- **`LD_LIBRARY_PATH`·`LD_PRELOAD`는 앱 프로세스에서 무시됩니다.** 이유가 중요합니다: `AT_SECURE` 때문이 **아닙니다**(zygote에서 fork된 앱은 setuid/setcap exec이 아니므로 `AT_SECURE`가 아닙니다). 진짜 이유는, 링커의 프리로드/환경 처리는 **프로세스 이미지 시작 때 한 번** 일어나는데 그건 부팅 시 `app_process`/zygote가 `LD_PRELOAD` 없는 환경에서 뜬 시점이고, 특수화된 자식은 링커 init을 다시 돌리지 않기 때문입니다. 그래서 앱이 나중에 자기 환경에 `LD_PRELOAD`를 넣어도 참조되지 않습니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: ELF 이미지 = `PT_LOAD` 세그먼트, `PT_DYNAMIC`(재배치·심볼·`DT_NEEDED` 표), 그리고 재배치 항목들. aarch64는 **RELA 전용**(명시적 addend를 담은 `.rela.dyn`/`.rela.plt`)이며 `REL` 형식이 없습니다.
- **출력**: 매핑되고, 재배치되고, 초기화되고, GOT가 채워진 뒤 RELRO 구간이 읽기전용으로 얼려진 라이브러리.

핵심 재배치 타입(aarch64):

| 타입 | 무엇 | 비고 |
|------|------|------|
| `R_AARCH64_RELATIVE` | 심볼 없음, `로드베이스 + addend` | PIE의 **대다수**. ASLR 슬라이드용. packed 압축(APS2/RELR)의 대상 |
| `R_AARCH64_GLOB_DAT` | 데이터/심볼 주소를 GOT 슬롯에(`S+A`) | `.rela.dyn` |
| `R_AARCH64_JUMP_SLOT` | 함수 주소를 GOT 슬롯에(`S+A`) | `.rela.plt`. 고전 lazy 바인딩의 대상 |
| `R_AARCH64_IRELATIVE` | 심볼 없음, addend가 **IFUNC 리졸버 주소** | 로드시 리졸버를 **호출**해 결과를 슬롯에 |

`GLOB_DAT`과 `JUMP_SLOT`은 계산(`S+A`)이 **같습니다**. 다른 건 의도(데이터 vs 함수 슬롯)와 섹션뿐이고, 뒤에서 보듯 Android에서는 그 차이마저 사실상 겉모양뿐입니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**고전적 원시는 GOT 덮어쓰기입니다.** GOT는 여러 코드 경로가 거쳐 가는, 예측 가능한 하나의 쓰기 가능 함수 포인터라, 그 슬롯에 값을 써넣으면 다음 호출 때 제어가 넘어갑니다. 복귀 주소를 훼손하거나 호출 지점을 찾을 필요도 없습니다.

**그런데 Android는 이 원시를 기본값으로 없앱니다.** 두 가지가 겹칩니다.

1. **bionic은 lazy 바인딩을 아예 구현하지 않습니다.** 고전 리눅스에서는 첫 호출 때 PLT0을 거쳐 리졸버(`_dl_runtime_resolve`)가 심볼을 찾아 `GOT[n]`에 써넣고 이후엔 GOT에서 바로 읽습니다. bionic은 `-z now`가 없어도 **모든 `JUMP_SLOT`을 로드 시점에 해석**합니다. 컴파일러가 PLT0과 스텁, `GOT[1]/GOT[2]` 자리는 파일에 넣지만 링커가 리졸버를 설치하지 않아 **PLT0은 죽은 코드**입니다. 그래서 x86/glibc의 `ret2dlresolve`에 해당하는 표적이 Android에는 없습니다.
2. **full RELRO + BIND_NOW가 툴체인 기본값입니다.** Soong/NDK가 `-Wl,-z,relro -Wl,-z,now`로 링크하므로, 로드가 끝나면 GOT 전체와 `.data.rel.ro`가 `PT_GNU_RELRO` 세그먼트로 묶여 읽기전용으로 `mprotect`됩니다(`phdr_table_protect_gnu_relro()`). 즉 앱 코드가 첫 명령을 실행할 때 **GOT는 이미 해석되어 있고 읽기전용**입니다.

그래서 공격자는 **다른 데로 피벗합니다**. RELRO가 덮는 건 `.got`과 `.data.rel.ro`뿐이므로, 여전히 쓰기 가능한 것들: `.data`/`.bss`의 함수 포인터, 쓰기 가능 메모리(힙)의 C++ vtable 포인터, 콜백 테이블, 그리고 **`__cxa_atexit`/atexit 핸들러 체인**. 특히 bionic은 glibc의 `PTR_MANGLE` 같은 포인터 인코딩을 atexit 핸들러에 **하지 않으므로**, Android에서 이 체인은 인코딩되지 않은 진짜 표적입니다(공격자에게 유리한 Android-vs-glibc 차이).

부수적 표면 둘: **IFUNC 리졸버**는 로드 시점에 링커 문맥에서 실행됩니다(단, 순서상 RELRO 이전에 슬롯에 쓰이고 그 뒤 얼려지므로 앱 코드 시점엔 이미 RO). **`dlopen` 경로 주입**은 링커 네임스페이스가 제한합니다. `LD_PRELOAD`는 앞서 봤듯 앱에는 무효이고, 루팅/adb/디버그 가능 빌드(`wrap.<pkg>` 속성)에서만 됩니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 6.0 (API 23) | `.gnu.hash`·심볼 버저닝 지원, **APS2 packed 재배치**(`DT_ANDROID_RELA`) 지원 |
| Android 7 (API 24) | **링커 네임스페이스** 도입. `targetSdk ≥ 24` 앱은 사설 플랫폼 라이브러리 하드 차단(이전엔 경고만) |
| Android 11 (API 30) | **RELR** relative-reloc 압축을 OS 로더가 지원(빌드시 `min_sdk`로 게이트) |
| Android 11~12 | BTI 강제가 성숙(단 ARMv8.5 하드웨어 + 로더 지원 필요) |

빌드 기본값인 **full RELRO + BIND_NOW**는 이미 오래된 툴체인 기본이라 특정 버전에 묶이지 않습니다. 다만 항상 그런지는 바이너리마다 `readelf -d`로 확인해야 합니다. 그리고 **RELR과 RELRO는 이름만 비슷할 뿐 별개입니다** — RELR은 relative 재배치를 압축하는 인코딩이고, RELRO는 재배치 후 세그먼트를 읽기전용으로 만드는 것입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**실제 `.so`에서 관측** (APK의 `lib/arm64-v8a/`나 `/system/lib64/`에서)
- `readelf -dW lib.so` → `FLAGS BIND_NOW` / `FLAGS_1 NOW`, `NEEDED`(soname), `SONAME`
- `readelf -rW lib.so` → `JUMP_SLOT` vs `GLOB_DAT` vs `RELATIVE` vs `IRELATIVE`(packed면 최신 `llvm-readelf` 필요)
- `readelf -n lib.so` → `GNU_PROPERTY_AARCH64_FEATURE_1_AND`의 BTI/PAC 비트(C37의 완화가 광고되는 자리)
- `readelf -lW lib.so` → `GNU_RELRO` 세그먼트 존재; `checksec --file=lib.so` → `Full RELRO`
- `objdump -d -j .plt lib.so` → PLT 스텁의 `adrp x16 / ldr x17 / add x16 / br x17`

**AOSP·아키텍처 문서**
- bionic: `bionic/linker/linker_relocate.cpp`(재배치 루프·IRELATIVE), `linker_phdr.cpp`(`phdr_table_protect_gnu_relro`), `linker_namespaces.cpp`; `dlfcn.cpp`
- 네임스페이스 생성: `system/core/libnativeloader`(ART APEX). 설정 파일은 `/system/etc/ld.config.txt`와 버전별 `/system/etc/ld.config.<VNDK버전>.txt`(예: `ld.config.30.txt`), 공개 라이브러리 목록은 `/system/etc/public.libraries.txt`
- JNI 해석: ART `art/runtime/jni/java_vm_ext.cc`(`LoadNativeLibrary`, `FindNativeMethod`)
- ABI: **ELF for the Arm 64-bit Architecture (IHI 0056)** — 재배치 타입표, GNU property 노트

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **13~14주차(ELF·JNI)**: 그때 손으로 판 정적 파일의 **동적 측면**이 이 글입니다. JNI 이름 인코딩도 여기서 링커·ART 해석 경로로 이어집니다 — `System.loadLibrary`가 네임스페이스 안에서 `dlopen`하고, ART가 `JNI_OnLoad`를 `dlsym`(있으면 `RegisterNatives`), 없으면 `Java_<클래스>_<메서드>` 맹글 이름으로 지연 조회합니다(그때 본 `_1`/`_2`/`_3`/`_0XXXX` 규칙). aarch64에서 `JNICALL`은 비어 있습니다.
- **C05(예외 수준·메모리 보호)**: RELRO의 읽기전용화는 C05의 "로드 후 페이지를 읽기전용으로" MMU 기능의 사례입니다. 네이티브 코드가 EL0이라는 것도 여기서 재확인됩니다.
- **C37(완화)**: RELRO는 GOT에 대한 **익스플로잇 장벽**이고, BTI/PAC는 `.note.gnu.property`에 광고됩니다. 단, 그 노트의 "AND"는 **정적 링크 시 입력 오브젝트들 사이에서** 결합됩니다(하나라도 BTI 없이 빌드된 오브젝트가 있으면 그 출력 이미지의 비트가 클리어). 런타임에는 로더가 **오브젝트별로** 자기 노트를 읽어 BTI를 적용하지, 로드된 모든 `.so`에 걸쳐 AND하지 않습니다. 노트가 있다고 강제되는 것도 아닙니다 — ARMv8.5 하드웨어와 로더 지원이 있어야 합니다.
- **C15(JNI 로딩)** 위에 서고, 다음은 **C23(SELinux 정책 언어)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

두 개를 손으로 그려 보시길 권합니다.

```
[ System.loadLibrary 부터 네이티브 메서드까지 ]

System.loadLibrary("foo")
   │  ART가 lib<foo>.so 로 매핑
   ▼
링커: 호출자 ClassLoader 의 네임스페이스에서 dlopen
   │   ├─ 공개 라이브러리(public.libraries.txt)만 도달 가능
   │   └─ 사설이면 "not accessible for the namespace"
   ▼
PT_LOAD 매핑 → 재배치(RELATIVE/GLOB_DAT/JUMP_SLOT/IRELATIVE)
   │            ※ bionic 은 lazy 없음 — JUMP_SLOT 전부 지금 해석
   ▼
RELRO: GOT + .data.rel.ro 를 읽기전용으로 mprotect
   ▼
DT_INIT_ARRAY 실행 → dlsym("JNI_OnLoad")
   ├─ 있으면 호출 → RegisterNatives(이름·시그니처로 바인딩)
   └─ 없으면 첫 호출 때 Java_<클래스>_<메서드> 맹글 이름으로 dlsym
```

```
[ 외부 함수 호출이 PLT/GOT 를 지나는 길 ]

  call foo@plt
       │
       ▼
  .plt 스텁:  adrp x16, page(&GOT[n])
             ldr  x17, [x16, #:lo12:&GOT[n]]   ← GOT[n] 읽기(이미 해석·RO)
             add  x16, x16, #:lo12:&GOT[n]
             br   x17                          ← 대상으로 점프
       │
       ▼
   foo 의 실제 주소
   ── glibc 라면 첫 호출 시 여기서 lazy 리졸버. Android 는 없음(GOT 이미 RO) ──
```

## 오개념 판별 문제 5개

각 문장이 왜 틀렸는지 한 줄로 반박해 보세요.

1. "Android도 첫 호출 때 lazy 바인딩을 하므로 `_dl_runtime_resolve`를 후킹할 수 있다."
2. "aarch64도 x86처럼 `.rel.plt`에 REL 재배치를 쓴다."
3. "`LD_LIBRARY_PATH`나 `LD_PRELOAD`로 앱에 라이브러리를 주입할 수 있다."
4. "full RELRO면 프로세스의 모든 함수 포인터가 읽기전용이라 포인터 하이재킹은 끝이다."
5. "`.note.gnu.property`에 BTI 비트가 있으면 그 라이브러리는 BTI가 강제되어 실행된다."

<details><summary>판정 기준(펼치기)</summary>

1. bionic은 lazy 바인딩을 아예 안 합니다. 모든 `JUMP_SLOT`이 로드 시점에 해석되고 PLT0/리졸버 경로는 파일에만 있고 실행되지 않습니다. 후킹할 lazy 창이 없습니다.
2. aarch64는 RELA 전용(`.rela.dyn`/`.rela.plt`, 명시적 addend)이고 함수 슬롯 타입은 `R_AARCH64_JUMP_SLOT`입니다. `.rel.plt`/REL을 기대하면 `readelf -r`를 오독합니다.
3. 앱(zygote 자식) 프로세스는 둘 다 무시합니다. 링커의 환경 처리는 부팅 시 zygote가 뜰 때 한 번 일어났고 자식은 다시 돌지 않습니다(`AT_SECURE` 때문이 아님). 루팅/adb/디버그 빌드에서만 가능합니다.
4. RELRO가 덮는 건 `.got`과 `.data.rel.ro`뿐입니다. `.data`/`.bss`의 함수 포인터, 힙 vtable, 콜백, atexit 체인은 여전히 쓰기 가능합니다. bionic은 atexit 포인터를 인코딩하지도 않습니다.
5. 노트는 광고일 뿐입니다. "AND"는 정적 링크 시 입력 오브젝트들 사이에서 결합되고, 런타임 강제는 오브젝트별 + ARMv8.5 하드웨어 + 로더 지원이 있어야 합니다. 노트만으로 켜지지 않습니다.
</details>

## 서술형 문제 3개

1. Android가 lazy 바인딩을 쓰지 않고 full RELRO + BIND_NOW를 기본으로 하는 것이 "GOT 덮어쓰기" 익스플로잇에 어떤 결과를 주는지, 그리고 공격자가 어디로 피벗하는지(구체적 표적 3개 이상) 서술하세요.
2. 링커 네임스페이스가 앱과 시스템 라이브러리의 경계를 어떻게 강제하는지, 그리고 `is not accessible for the namespace`가 왜 `not found`와 다른 신호인지 서술하세요.
3. 13~14주차에서 본 JNI 이름 인코딩(`Java_<클래스>_<메서드>`, `_1`/`_2`/`_3`/`_0XXXX`)과 `RegisterNatives`라는 두 바인딩 경로를 구분하고, 명시적 등록이 왜 스트립·리네임된 네이티브 리버싱을 어렵게 하는지 서술하세요.

## 소스·정적 검증 경로

실제 arm64 `.so` 하나(APK의 `lib/arm64-v8a/`에서 추출)로 다음을 수행하고 정리하세요.

- `readelf -dW`로 `BIND_NOW`/`FLAGS_1 NOW`를 확인하고, `readelf -rW`로 `JUMP_SLOT`·`RELATIVE`·`GLOB_DAT`·`IRELATIVE`를 세어 보세요(RELATIVE가 적게 보이면 RELR/APS2로 packed된 것 — 이유를 적으세요).
- `readelf -n`으로 BTI/PAC 노트를, `objdump -d -j .plt`로 `adrp/ldr/add/br` 스텁을 확인하세요.
- 디버거로 GOT 항목 하나를 프로세스 시작 직후에 관찰해, Android full RELRO에서는 **이미 해석되어 있고 읽기전용**이라 lazy 데모가 재현되지 않음을 13~14주차의 정적 파서 결과와 대조하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 환경 한계를 먼저 명시합니다: AVD `sec-api33`은 x86_64라 그 안의 `.so`는 AArch64 PLT/GOT 스텁이 아닙니다. AArch64 비교는 NDK로 빌드한 샘플 ELF, ARM64 Cuttlefish/QEMU 이미지 또는 공개 AOSP 바이너리를 사용합니다. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **정적 관측**: 소스 탐색 과제의 `readelf`/`objdump`/`checksec` 출력을 실제 화면으로. Full RELRO·BIND_NOW·BTI/PAC 노트를 각각 짚기.
2. **네임스페이스 거부 실측**: 앱에서 사설 `/system` 라이브러리를 `dlopen` 시도해 `is not accessible for the namespace` 로그를 실제로 캡처.
3. **JNI 해석 경로 대조**: `JNI_OnLoad`+`RegisterNatives`가 있는 `.so`와, 그것 없이 맹글 이름으로 해석되는 `.so` 두 개를 만들어 심볼 조회 방식의 차이를 관측.
4. **GOT 읽기전용 확인**: full RELRO 라이브러리의 GOT 슬롯에 로드 후 쓰기를 시도해 폴트가 나는 것으로 "읽기전용으로 얼려졌음"을 증명.

각 단계는 명령 출력 또는 실제 스크린샷으로만 증적화하고, 재현 불가·미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

ELF은 정적 이미지이고, 링커는 그것을 EL0에서 살아 도는 프로세스로 만듭니다. Android가 데스크톱 리눅스와 다르게 내린 두 선택 — **lazy 바인딩을 아예 안 하고 full RELRO+BIND_NOW를 기본으로** 한 것, 그리고 **링커 네임스페이스로 앱과 시스템 라이브러리를 가른** 것 — 이 이 층의 공격 표면을 바꿉니다. 고전적 GOT 덮어쓰기와 `ret2dlresolve`는 기본값에서 사라지고, 공격은 `.data`/힙의 쓰기 가능 포인터와 인코딩 안 된 atexit 체인으로 옮겨 갑니다.

13~14주차가 정적 파일을 손으로 팠다면, 이 글은 그 파일이 로드·연결되는 동적 과정과 그 보안 결과입니다. C37의 완화(RELRO의 GOT 보호, `.note.gnu.property`의 BTI/PAC)가 실려서 강제되는 자리가 바로 여기였습니다. 다음은 격리 정책 언어인 **C23(SELinux)**으로 이어집니다. 이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.
