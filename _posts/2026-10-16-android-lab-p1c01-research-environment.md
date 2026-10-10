---
layout: post
title: "Android 보안 연구 환경 구축 — 계측 가능한 에뮬레이터 고르기"
date: 2026-10-16 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, SDK, NDK, AVD, Emulator, 실습환경]
excerpt: "보안 연구용 Android 환경에서 가장 결정적인 선택은 에뮬레이터 이미지다. google_apis(userdebug)는 adb root와 /system 리마운트가 되지만 google_apis_playstore(production)는 막힌다. 그리고 PAC/BTI/MTE 같은 ARM 하드웨어 완화는 arm64-v8a에서만 보인다."
---

Android 앱을 뜯어보려면 도구보다 먼저 **환경**을 정해야 한다. 그런데 이 환경에서 제일 자주, 그리고 조용히 틀리는 결정이 하나 있다 — 어떤 에뮬레이터 이미지를 쓰느냐. 잘못 고르면 `adb root`가 거부되고 후킹·리마운트가 막혀, 원인을 몇 시간씩 헤매게 된다. 이 글은 그 선택을 정확한 SDK 패키지 경로와 함께 정리한 기록이다. 이후 시리즈의 모든 실습(정적·동적·네이티브·커널)이 여기서 만든 환경 위에서 돌아간다.

> **한 줄 결론**: 계측(후킹·리마운트)이 필요하면 `google_apis` userdebug 이미지를, 하드웨어 완화(PAC/MTE) 관측이 필요하면 `arm64-v8a`를 골라야 한다. 이 두 축이 "무엇을 관측할 수 있느냐"를 결정한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 SDK/NDK/AVD를 어떤 패키지 경로로 설치하고, 어떤 시스템 이미지를 골라야 계측이 가능한 랩이 되는지를 다룬다. 세 가지 선수 개념이 밑에 깔린다. [ARM64 예외 수준(C05)](/posts/android-concept-atlas-c05-arm64-exception-levels/)은 PAC/BTI/MTE가 왜 arm64에만 존재하는지를, [프로세스·가상메모리(C04)](/posts/android-concept-atlas-c04-process-vm-syscall/)는 에뮬레이터가 결국 무엇을 흉내 내는지를 설명한다. 이미 [HexTree Android Track](/posts/hextree-android-track/)에서 실전 랩을 돌려봤다면, 그 랩들이 정확히 이 환경 위에 선다.

전체 구조에서 이 환경은 **모든 것의 바닥**이다. 앱 분석 → 프레임워크 관찰 → 네이티브 디버깅 → 커널 실습(7부의 Cuttlefish/QEMU)까지, 이후 등장하는 도구와 이미지가 전부 여기서 갈라져 나온다.

## 핵심 개념 — 무엇이 어디에 있나

Android SDK의 커맨드라인 도구는 `cmdline-tools/latest/bin` 아래 `sdkmanager`·`avdmanager`로 산다(Windows는 `.bat`). 예전 `tools/` 패키지는 폐기됐고 현행 패키지명은 `cmdline-tools;latest`다. `Source-confirmed` 패키지는 세미콜론으로 구분하고 버전을 고정하며, `sdkmanager --list`가 정확한 설치 문자열을 알려준다.

| 패키지 문자열 | 담긴 것 | 비고 |
|--|--|--|
| `platform-tools` | `adb`, `fastboot` | 기기 통신 |
| `build-tools;34.0.0` | `aapt2`, `apksigner`, `zipalign`, `d8`(구 `dx`), `dexdump`, (legacy) `aapt` | APK triage 도구 |
| `platforms;android-34` | 컴파일 대상 플랫폼 | API 레벨과 매칭 |
| `ndk;26.1.10909125` | LLVM/Clang, `ndk-build`/CMake, `ndk-stack`, ASan/HWASan/UBSan 런타임 | 네이티브 RE·크래시 분석 |
| `system-images;android-34;google_apis;x86_64` | AVD용 시스템 이미지 | 빌드 타입·ABI가 핵심 |
| `emulator` | 에뮬레이터 실행 파일 | **별도 패키지** |

여기서 흔한 착각 하나 — APK triage 도구(`aapt2`·`apksigner`)는 `build-tools`에서, `adb`는 `platform-tools`에서, 에뮬레이터는 또 별도 `emulator` 패키지에서 온다. 이 세 패키지를 뭉뚱그리면 "명령을 못 찾는다"의 절반이 여기서 나온다. `Source-confirmed`

**신뢰 경계와 위협 모델.** 연구 환경의 위협 모델은 외부 공격자가 아니라 **나 자신의 관측 능력**이다. 후킹·리마운트를 하려면 `adb root`가 필요한데, 이 능력의 유무가 이미지의 빌드 타입(userdebug vs user)에 종속된다. 잘못된 이미지를 고르면 관측 경계가 조용히 낮아지지 않고 오히려 막힌다.

> **[그림 1]** `sdkmanager --list`로 설치 가능한 패키지 문자열(build-tools/system-images 버전)을 확인한 터미널 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **로컬 에뮬레이터와 자작 앱**으로만 진행한다. 제3자 앱·실서비스·실기기 flashing은 없다. 계측용(`google_apis` x86_64, 속도)과 하드웨어 완화 관측용(`arm64-v8a`) 두 AVD를 나란히 둔다.

## 실습 절차와 관측

### 가설
- **가설 A** — `google_apis`에선 `adb root`가 성공하고, `google_apis_playstore`에선 `adbd cannot run as root in production builds`로 거부된다. `Inferred`
- **가설 B** — x86_64 이미지에는 PAC/MTE 관련 표시가 없고, arm64-v8a에는 나타난다(MTE는 에뮬/호스트 지원 필요). `Inferred`

### 절차
1. `sdkmanager --list`로 정확한 패키지 문자열을 확인한다.
2. 아래처럼 두 AVD(`google_apis` x86_64, `arm64-v8a`)를 생성한다.
3. 각각에서 `adb root`를 시도해 성공/거부를 기록한다.
4. `getprop ro.build.type`·`getprop ro.product.cpu.abi`로 빌드 타입·ABI를 기록한다.
5. Quick Boot 스냅샷(`adb emu avd snapshot save clean`)으로 재현 기준선을 잡는다.

```bash
# 설치
sdkmanager "platform-tools" "build-tools;34.0.0" "platforms;android-34" \
           "system-images;android-34;google_apis;x86_64" "emulator"
# AVD 생성 (-k 값은 이미 설치된 system-image 문자열이어야 한다)
avdmanager create avd -n sec-api34 -k "system-images;android-34;google_apis;x86_64"
# 실행 + 계측 확인
emulator -avd sec-api34
adb root                 # userdebug(google_apis)에서만 성공
adb shell whoami         # root
adb disable-verity && adb reboot && adb remount   # /system 쓰기
```

> **[그림 2]** 같은 `adb root`를 `google_apis`(성공)와 `google_apis_playstore`(거부) 두 이미지에서 실행한 대조 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
# google_apis x86_64
$ adb root
restarting adbd as root
$ getprop ro.build.type
userdebug

# google_apis_playstore
$ adb root
adbd cannot run as root in production builds
```

이미지별 계측 능력을 표로 정리하면 아래와 같다. 이 표 하나가 이 글의 실용적 결론이다.

| 이미지 태그 | 빌드 타입 | `adb root` | GMS/Play | 용도 |
|--|--|--|--|--|
| `google_apis` | userdebug | **가능** | Google APIs(Play Store 없음) | **계측·후킹**(권장) |
| `google_apis_playstore` | user(production) | **불가** | Play Store·Integrity 통과 | production 동작 관측 |
| `default`/AOSP (no-tag) | userdebug | 가능 | GMS 없음 | GMS 배제 실험 |

## Root Cause — 왜 이렇게 되는가

Play Store 이미지가 `adb root`를 막는 것은 버그가 아니라 **production 빌드의 의도된 보안**이다. user 빌드는 출하 기기와 동일한 신뢰 경계를 갖고, `adbd`는 `ro.debuggable`/빌드 타입을 확인해 root 전환을 거부한다. `Source-confirmed` 즉 "무엇을 관측할 수 있느냐"가 빌드 타입에 종속되고, 연구자는 신뢰 경계를 낮춘 userdebug를 골라야 관측이 가능하다.

x86_64에서 PAC/BTI/MTE를 볼 수 없는 것도 같은 결의 문제다. 이 기능들은 ARMv8.3/8.5의 하드웨어 확장(C05)이라 x86 명령 집합엔 애초에 없다. x86_64 이미지는 ~API 28부터 ARM→x86 바이너리 변환을 실어 arm64 전용 네이티브도 (변환되어) 실행하지만, 변환은 명령을 흉내 낼 뿐 하드웨어 완화를 만들어내진 못한다. `Source-confirmed` 내 x86 AVD(`sec-api33`)로 확인하면 PAC/MTE 표시가 없지만, SELinux·FBE는 아키텍처 무관이라 그대로 관측된다.

> **[그림 3]** arm64-v8a와 x86_64에서 각각 `cat /proc/cpuinfo` 등으로 하드웨어 기능 표시 차이를 대조한 캡처 — *실측 스크린샷 자리*

## 방어와 회귀 검증(연구자 관점)

- 계측용(userdebug)과 production 검증용(Play image)을 **분리**해 둔다. 하나의 AVD로 둘 다 하려다 조용히 막힌다.
- 스냅샷으로 매 실험을 깨끗한 기준선에서 시작해 오염을 막는다. "이미지 X에서 adb root가 성공/실패한다"를 스냅샷 복원 후에도 재확인하면 환경 드리프트를 잡을 수 있다.
- 실기기 flashing은 brick·데이터 손실 위험이 있어 기본 과정에서 제외한다.

**흔한 실패와 처리.** `sdkmanager: command not found` → `tools/bin`이 아니라 `cmdline-tools/latest/bin`을 PATH에. `adb root` 무응답 → Play image를 골랐거나 실기기(user) 대상. arm64 이미지가 지나치게 느림 → x86 호스트에선 arm64가 에뮬레이션이라 느리니, 완화 관측이 목적이 아니면 x86_64를 쓴다.

## 버전 차이와 한계

- `build-tools`·`platforms`·`system-images`는 각각 독립 버전이라 API 레벨과 맞춰야 한다.
- NDK **r26 vs r27**은 번들 Clang/LLVM 버전과 기본 동작이 달라진다 — 문서화할 땐 버전을 표기한다.
- **PAC/BTI/MTE는 arm64-v8a에서만**(MTE는 추가로 에뮬/호스트 지원 필요). 에뮬레이터엔 실제 TEE/StrongBox·RPMB가 없어 [Keystore(C40)](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/)·[롤백 방지(C29)](/posts/android-concept-atlas-c29-rollback-protection/)의 하드웨어 부분은 관측되지 않는다. 반대로 SELinux·FBE는 에뮬로도 관측된다.

## 정리

- 계측 랩은 `google_apis` userdebug 이미지 — `adb root`·`/system` 리마운트가 관측의 전제다.
- PAC/BTI/MTE는 arm64-v8a에서만; x86_64는 빠르지만 그 기능이 없다.
- 스냅샷으로 재현 기준선을 잡고, 하드웨어 신뢰뿌리는 실기기로 넘긴다.

**점검 질문** — (1) 후킹 랩에 맞는 이미지는 무엇이고 왜인가? (2) `aapt2`와 `adb`는 각각 어느 SDK 패키지에서 오는가? (3) x86_64에서 PAC를 관측할 수 없는 이유는?

**참고** — [SDK 도구](https://developer.android.com/tools/sdkmanager) · [platform/build-tools 릴리스](https://developer.android.com/tools/releases/build-tools) · [NDK](https://developer.android.com/ndk) · [Concept Atlas C05](/posts/android-concept-atlas-c05-arm64-exception-levels/) · [C37 완화](/posts/android-concept-atlas-c37-exploit-mitigations/)

*다음 글: [adb·logcat·dumpsys로 증적 수집하기](/posts/android-lab-p1c02-adb-evidence-collection/).*
