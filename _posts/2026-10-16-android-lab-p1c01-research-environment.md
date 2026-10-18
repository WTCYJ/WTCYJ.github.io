---
layout: post
title: "Android 연구용 에뮬레이터 — 빌드 타입과 ABI가 가르는 것"
date: 2026-10-16 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, SDK, NDK, AVD, Emulator, userdebug, ndk_translation, 실습환경]
excerpt: "Android 13 x86_64 에뮬레이터에서 google_apis 이미지는 adb root가 됐고 같은 빌드 번호의 Play 이미지는 ro.debuggable=0이라 거부됐다. 이 x86_64 호스트의 에뮬레이터는 API 33 arm64 AVD를 시작 단계에서 거부했고, ARM 번역이 들어 있는 API 36 이미지에서도 번역된 프로세스가 본 PAC·BTI·MTE 비트는 전부 0이었다."
---

이 시리즈의 실습은 대부분 Android 에뮬레이터 위에서 돈다. 어떤 시스템 이미지로 AVD를 만드느냐에 따라 `adb root`가 되는지, `/system`에 파일을 쓸 수 있는지, 네이티브 코드가 어떤 CPU 기능을 보는지가 달라진다. 주 에뮬레이터는 Android 13(API 33) google_apis x86_64 이미지로 만든 AVD `codex-atlas-api33`이다. 빌드는 `TE1A.240213.009`, 보안 패치는 2024-03-01, 커널은 5.15.119다. 호스트는 x86_64 Windows 11이고 에뮬레이터 36.5.11이 WHPX 가속으로 돈다.

처음에는 계측용 x86_64 AVD 옆에 arm64-v8a AVD를 하나 더 두고 PAC·BTI·MTE를 들여다볼 생각이었다. 그런데 이 호스트에서는 arm64 AVD가 시작조차 되지 않았다. ARM 쪽은 결국 ARM 번역이 들어 있는 API 36 이미지와 호스트의 qemu-user로 볼 수 있는 데까지만 봤다.

PAC·BTI·MTE가 왜 ARM 쪽 기능인지는 [ARM64 예외 수준(C05)](/posts/android-concept-atlas-c05-arm64-exception-levels/)과 [익스플로잇 완화(C37)](/posts/android-concept-atlas-c37-exploit-mitigations/)에, 에뮬레이터가 결국 무엇을 흉내 내는지는 [프로세스·가상메모리·시스템 콜(C04)](/posts/android-concept-atlas-c04-process-vm-syscall/)에 따로 적어 두었다.

## SDK 패키지 문자열과 도구가 오는 곳

`sdkmanager`와 `avdmanager`는 `cmdline-tools/latest/bin` 아래에 있다(Windows에서는 `.bat`). 예전 `tools/` 패키지(SDK Tools)는 [업데이트가 끊겼고](https://developer.android.com/tools/releases/sdk-tools) 지금 패키지 이름은 `cmdline-tools;latest`다. 다만 2026년 현재 [sdkmanager 문서](https://developer.android.com/tools/sdkmanager)는 첫머리에서 이 도구를 deprecated로 표시하고 Android CLI의 `android sdk`를 쓰라고 한다. avdmanager 문서도 같은 식으로 `android emulator`를 가리킨다. Android CLI는 이번에 설치해 보지 않았다. 이 PC에 깔린 cmdline-tools는 20.0이고 목록에 뜬 `cmdline-tools;latest`는 23.0이다.

패키지는 `"build-tools;36.0.0"`처럼 세미콜론으로 이은 경로를 따옴표로 감싸 `sdkmanager`에 넘긴다. 정확한 문자열은 `sdkmanager --list`가 알려 준다. 아래는 이 랩에 깔린 패키지 목록과, 받을 수 있는 API 33 이미지를 default, google_apis, google_apis_playstore 태그로 거른 결과다.

![sdkmanager --list_installed 출력에 build-tools 34.0.0·35.0.0·36.0.0, cmake;3.22.1, emulator 36.5.11, ndk;25.1.8937393, ndk;27.3.13750724, platform-tools 37.0.0, platforms android-34·35·36, system-images android-28 google_apis x86 12, android-33 google_apis arm64-v8a 17과 x86_64 17, android-33 google_apis_playstore x86_64 9, android-36 google_apis x86_64 7이 나오고 sdkmanager --list 에서 거른 API 33 이미지 default·google_apis·google_apis_playstore 각각의 arm64-v8a·x86_64 행이 보이는 터미널](/assets/img/android-mastery/p1c01/01-sdk-packages.png)

어느 도구가 어느 패키지에서 오는지는 SDK 폴더를 직접 열어 보면 바로 나온다. PATH에 무엇을 넣어야 하는지가 여기서 정해진다. APK를 들여다보는 `aapt2`와 `apksigner`는 `build-tools`에, `adb`는 `platform-tools`에, 에뮬레이터는 따로 받는 `emulator` 패키지에 들어 있다.

| 패키지 | 이 PC에서 확인한 내용물 |
|--|--|
| `platform-tools` 37.0.0 | adb, fastboot |
| `build-tools;36.0.0` | aapt, aapt2, apksigner, d8, dexdump, zipalign |
| `emulator` 36.5.11 | emulator, emulator-check |
| `ndk;27.3.13750724` | clang 18.0.4, ndk-build, ndk-stack, android.toolchain.cmake, ASan·HWASan·UBSan 런타임 |
| `cmake;3.22.1` | cmake, ninja |

![platform-tools 의 adb.exe·fastboot.exe, build-tools/36.0.0 의 aapt.exe·aapt2.exe·apksigner.bat·d8.bat·dexdump.exe·zipalign.exe, build-tools 전체에서 dx 개수 0, emulator 폴더의 emulator-check.exe·emulator.exe, NDK 27.3 의 ndk-build.cmd·ndk-stack.cmd·android.toolchain.cmake, cmake/3.22.1/bin 의 cmake.exe·ninja.exe, NDK 25.1 clang 14.0.6 과 27.3 clang 18.0.4, libclang_rt asan·hwasan·ubsan_standalone 런타임의 aarch64·x86_64 판이 보이는 터미널](/assets/img/android-mastery/p1c01/02-tool-origins.png)

NDK에 든 것은 CMake에 넘길 툴체인 파일(`build/cmake/android.toolchain.cmake` 등)까지이고 `cmake.exe`와 `ninja.exe`는 별도 패키지 `cmake;3.22.1`에 들어 있다([NDK와 CMake 설치](https://developer.android.com/studio/projects/install-ndk)). `dx`는 build-tools 34, 35, 36 어디에도 없다. [d8로 넘어가면서](https://android-developers.googleblog.com/2020/02/the-path-to-dx-deprecation.html) 빠졌다.

NDK 판마다 번들 clang도 다르다. 이 PC의 25.1은 clang 14.0.6(r450784d), 27.3은 18.0.4(r522817d)다([r27 변경 기록](https://github.com/android/ndk/wiki/Changelog-r27)). 깔려 있지 않은 r26은 [변경 기록](https://github.com/android/ndk/wiki/Changelog-r26)을 보면 첫 판이 clang-r487747c였고 r26b에서 r487747d, r26c에서 r487747e로 올라갔다. 27.3에는 ASan, HWASan, UBSan 런타임이 aarch64용과 x86_64용으로 함께 들어 있다. 이 시리즈에서 네이티브 코드는 27.3으로 빌드한다.

## 부팅하기 전에 build.prop에서 읽히는 빌드 타입

API 33 x86_64만 해도 이미지 태그는 `default`, `google_apis`, `google_apis_playstore`로 나뉜다. 태그마다 빌드 타입이 다르고 그 값은 AVD를 띄우기 전에 SDK 폴더의 `build.prop`에서 읽을 수 있다. 아래 `$SI`는 SDK의 `system-images` 폴더(`$ANDROID_HOME/system-images`)다. `default` 이미지는 내려받지 않았다. 694 MB짜리 zip에서 HTTP Range 요청으로 `x86_64/build.prop` 하나만 꺼내 읽었는데, 그때 쓴 `tools/remote_zip_cat.py`는 zip 끝의 중앙 디렉터리를 Range 요청으로 읽은 뒤 이름이 맞는 항목 하나만 받아 푸는 37줄짜리 스크립트다.

```python
"""Print one member of a remote zip using HTTP Range requests (no full download).
usage: python remote_zip_cat.py URL MEMBER_SUFFIX
"""
import struct, sys, urllib.request, zlib

def rng(url, a, b):
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
    return urllib.request.urlopen(req, timeout=60).read()

def main(url, suffix):
    size = int(urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60).headers["Content-Length"])
    tail = rng(url, max(0, size - 65536), size - 1)
    i = tail.rfind(b"PK\x05\x06")
    cd_size, cd_off = struct.unpack_from("<II", tail, i + 12)
    if cd_off == 0xFFFFFFFF:  # zip64
        j = tail.rfind(b"PK\x06\x06")
        cd_size, cd_off = struct.unpack_from("<QQ", tail, j + 40)
    cd = rng(url, cd_off, cd_off + cd_size - 1)
    p = 0
    while p < len(cd):
        meth, = struct.unpack_from("<H", cd, p + 10)
        csize, usize, nlen, xlen, clen = struct.unpack_from("<IIHHH", cd, p + 20)
        off, = struct.unpack_from("<I", cd, p + 42)
        name = cd[p + 46:p + 46 + nlen].decode()
        if name.endswith(suffix):
            lh = rng(url, off, off + 29)
            ln, lx = struct.unpack_from("<HH", lh, 26)
            data = rng(url, off + 30 + ln + lx, off + 30 + ln + lx + csize - 1)
            out = zlib.decompress(data, -15) if meth == 8 else data
            sys.stdout.write(f"# {name} ({usize} bytes) from {url}\n")
            sys.stdout.write(out.decode("utf-8", "replace"))
            return
        p += 46 + nlen + xlen + clen
    sys.exit(f"{suffix} not found")

if __name__ == "__main__":
    main(*sys.argv[1:3])
```

![부팅 전 build.prop 비교. android-33 google_apis x86_64 는 ro.build.type=userdebug, ro.debuggable=1, google_apis_playstore x86_64 는 ro.build.type=user, ro.adb.secure=1, ro.debuggable=0, 원격 x86_64-33_r02.zip 에서 build.prop 만 읽은 default 는 userdebug 와 ro.debuggable=1, ro.dalvik.vm.native.bridge 는 android-33 이 0, android-36 이 libndk_translation.so 인 터미널](/assets/img/android-mastery/p1c01/03-image-buildprop.png)

google_apis는 `userdebug`에 `ro.debuggable=1`, Play 이미지는 `user`에 `ro.debuggable=0`과 `ro.adb.secure=1`이다. default도 `userdebug`, `ro.debuggable=1`로 나온다. [AVD 관리 문서](https://developer.android.com/studio/run/managing-avds)는 Play Store가 든 이미지는 release 키로 서명돼 root 권한을 얻을 수 없다고 하면서 대안으로 AOSP 이미지를 드는데, google_apis 이미지도 userdebug라 root가 됐다(다음 절의 adb root 대조).

부팅 전 `build.prop`을 믿을 수 있는 범위는 빌드 타입과 `ro.debuggable`까지였다. SDK에 받아 둔 Play 이미지 폴더의 `build.prop`에는 `ro.build.tags=dev-keys`라고 적혀 있는데, 부팅한 기기의 `ro.build.tags`와 `ro.system.build.fingerprint`는 `release-keys`로 나왔다. 기기 안의 `/product/etc/build.prop`과 `/system_ext/etc/build.prop`도 release-keys였다. 서명 태그는 부팅한 뒤 `getprop`으로 다시 읽는다.

## adb root를 가르는 값은 ro.debuggable

같은 빌드 번호(`TE1A.240213.009`)의 userdebug 이미지와 user 이미지를 나란히 띄우고 같은 `adb root`를 쳤다.

`$S`는 주 에뮬레이터 `emulator-5600`(google_apis)이고 `$A`는 보조 포트 `emulator-5620`이다. 이 절에서는 보조 포트에 `mastery-play33`(google_apis_playstore)을 띄웠다. 두 인스턴스 모두 `-read-only -no-snapshot`으로 띄웠다. 주 에뮬레이터는 띄우는 스크립트가 이미 root로 올려 두기 때문에 `adb -s $S unroot`로 되돌리고 `adb -s $S wait-for-device`로 다시 붙은 다음 찍었다. `adb -s $S root` 뒤에도 adbd가 다시 뜰 때까지 `sleep 4; adb -s $S wait-for-device`로 기다렸는데, 이 대기와 unroot는 캡처에 보이지 않는다.

![같은 adb root 대조. userdebug 기기는 fingerprint 끝이 userdebug/dev-keys, ro.debuggable 1, id -u 2000 이고 adb root 가 restarting adbd as root 를 찍은 뒤 id 가 uid=0(root) context=u:r:su:s0, getenforce Enforcing. user 기기는 user/release-keys, ro.debuggable 0 이고 adb root 가 adbd cannot run as root in production builds 로 거부되어 uid=2000(shell) context=u:r:shell:s0, Enforcing 인 터미널](/assets/img/android-mastery/p1c01/08-adb-root-contrast.png)

userdebug 쪽은 `restarting adbd as root`를 찍고 `uid=0(root)`, SELinux 컨텍스트 `u:r:su:s0`가 됐다. user 쪽은 `adbd cannot run as root in production builds`로 거부되고 `uid=2000(shell)`, `u:r:shell:s0`에 머물렀다. root 셸이 된 쪽도 `getenforce`는 `Enforcing` 그대로였다. userdebug와 SELinux의 관계는 Cuttlefish와 GSI를 다루는 2부 글과 [SELinux 정책(C23)](/posts/android-concept-atlas-c23-selinux-policy/)에서 다시 다룬다.

거부 문구는 adbd의 [`restart_service.cpp`](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-13.0.0_r1/daemon/restart_service.cpp#36)에 그대로 있다. `adb root`를 받은 adbd는 이미 uid 0이면 `adbd is already running as root`를 돌려주고, `__android_log_is_debuggable()`이 거짓이면 거부 문구를 쓰고 끝낸다. 통과하면 `service.adb.root`를 1로 바꾸고 `restarting adbd as root`를 쓴다. 다시 뜬 adbd는 [`main.cpp`의 `should_drop_privileges()`](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-13.0.0_r1/daemon/main.cpp#66)에서 `ro.secure`가 1이면 권한을 내려놓되, debuggable 빌드에서 `service.adb.root`가 1일 때만 root를 유지한다.

![googlesource 의 android-13.0.0_r1 adb daemon/restart_service.cpp 25~55행. 31행 restart_root_service 가 강조되어 있고 getuid() == 0 이면 adbd is already running as root, 36~37행 !__android_log_is_debuggable() 이면 adbd cannot run as root in production builds, 42행 service.adb.root 를 1로 설정한 뒤 restarting adbd as root 를 쓰는 코드와 그 아래 restart_unroot_service 가 보이는 화면](/assets/img/android-mastery/p1c01/05-adbd-restart-root-source.png)

`__android_log_is_debuggable()`은 liblog의 [`properties.cpp`](https://android.googlesource.com/platform/system/logging/+/refs/tags/android-13.0.0_r1/liblog/properties.cpp#264)에 있고, `ro.debuggable`이 문자열 `"1"`인지만 본다. adbd는 빌드 타입 문자열을 직접 보지 않는다.

```cpp
// system/logging liblog/properties.cpp (android-13.0.0_r1), 264~271행
int __android_log_is_debuggable() {
  static int is_debuggable = [] {
    char value[PROP_VALUE_MAX] = {};
    return __system_property_get("ro.debuggable", value) > 0 && !strcmp(value, "1");
  }();

  return is_debuggable;
}
```

`ro.debuggable`을 정하는 건 빌드 변형이다. 빌드 시스템의 [`core/main.mk`](https://android.googlesource.com/platform/build/+/refs/tags/android-13.0.0_r1/core/main.mk#363)는 user와 userdebug 모두에 `ro.secure=1`을 넣고, user에는 `ro.adb.secure=1`을 더하면서 디버깅을 끈다. 디버깅이 켜진 변형만 `ro.debuggable=1`을 받는다.

```make
# build/make core/main.mk (android-13.0.0_r1), 363~403행 발췌
user_variant := $(filter user userdebug,$(TARGET_BUILD_VARIANT))
enable_target_debugging := true
...
  ADDITIONAL_SYSTEM_PROPERTIES += ro.secure=1
...
  ifeq ($(user_variant),user)
    ADDITIONAL_SYSTEM_PROPERTIES += ro.adb.secure=1
  endif
...
    # Disable debugging in plain user builds.
    enable_target_debugging :=
...
ifeq (true,$(strip $(enable_target_debugging)))
  # Target is more debuggable and adbd is on by default
  ADDITIONAL_SYSTEM_PROPERTIES += ro.debuggable=1
...
else # !enable_target_debugging
  # Target is less debuggable and adbd is off by default
  ADDITIONAL_SYSTEM_PROPERTIES += ro.debuggable=0
endif # !enable_target_debugging
```

아래는 두 기기에서 `getprop`으로 읽은 값이다. `ro.build.type`, `ro.debuggable`, `ro.secure`, 그리고 user 쪽 `ro.adb.secure=1`이 위 매핑과 맞는다. userdebug 쪽 `ro.adb.secure=0`은 main.mk가 넣는 값이 아니다. 앞에서 본 이미지 폴더의 `build.prop`에도 이 줄은 없었고, 어디서 들어오는지는 따로 찾지 않았다. 마지막 줄 `ro.build.tags`는 이 코드와 상관없이 함께 읽어 둔 서명 태그다.

| 속성 | google_apis (userdebug) | google_apis_playstore (user) |
|--|--|--|
| ro.build.type | userdebug | user |
| ro.debuggable | 1 | 0 |
| ro.secure | 1 | 1 |
| ro.adb.secure | 0 | 1 |
| ro.build.tags | dev-keys | release-keys |

user 빌드에서는 `/system`을 여는 쪽 명령도 막혀 있었다. `adb disable-verity`는 `verity cannot be disabled/enabled - USER build`를 찍었고, `adb remount`는 셸이 `remount` 명령을 찾지 못해 `/system/bin/sh: remount: inaccessible or not found`(종료 코드 127)로 끝났다. remount 쪽 소스 [`fs_mgr_remount.cpp`](https://android.googlesource.com/platform/system/core/+/refs/tags/android-13.0.0_r1/fs_mgr/fs_mgr_remount.cpp#156)에도 `ro.debuggable`이 1이 아니면 `only functions on userdebug or eng builds`를 남기고 멈추는 검사가 있지만, 이 이미지에서는 그 코드까지 가지도 못했다.

출하 기기의 adb가 root를 내주지 않는 것도 이 `ro.debuggable` 검사 때문이다. 기기를 볼 때는 `getprop ro.debuggable`부터 확인하고 `adb root`와 `adb disable-verity`가 위의 거부 문구로 끝나는지 본다.

헷갈리는 출력이 하나 있었다. userdebug 이미지에서 `adb root`가 아무것도 찍지 않고 끝났는데 root는 돼 있는 경우다. 전날 같은 순서로 돌렸을 때는 여섯 번 중 다섯 번이 그랬다. 그때 여섯 번 모두 `adb root` 직전 `id -u`는 2000이었고, 문구 없이 끝난 한 번을 캡처로 확인했을 때 직후 `id`는 `uid=0(root)`였다. 적어도 그 한 번은 전환이 일어났고 문구만 빠졌다. 이번에는 재부팅 직후에 한 번 보였다(뒤의 remount 캡처). 그 직후 다시 `adb root`를 치면 `adbd is already running as root`가 나왔다. 이 한 번은 직전 uid를 찍어 두지 않아서, 문구만 빠진 것인지 재부팅 뒤 이미 root였던 것인지 가리지 못했다. 그래서 스크립트에서는 `adb root`의 출력 대신 `adb shell id -u`로 root 여부를 확인한다.

Play 이미지는 user 빌드의 동작을 보는 대조군으로 쓴다. 이 이미지가 Play Integrity 판정을 통과하는지는 재지 않았다(Play Console 쪽 프로젝트가 있어야 한다). [판정 문서](https://developer.android.com/google/play/integrity/verdicts)는 `MEETS_DEVICE_INTEGRITY`를 인증받은 진짜 Android 기기에 주고 무결성 검사를 통과하지 못하는 에뮬레이터를 판정이 비는 경우의 예로 든다. `default` 이미지의 `adb root`도 부팅해서 확인하지는 않았다. `build.prop`의 `ro.debuggable=1`과 위 adbd 코드로 보면 될 것으로 예상할 뿐이다.

| 이미지 태그 | 빌드 타입 | adb root | 이 랩에서의 쓰임 |
|--|--|--|--|
| `google_apis` | userdebug | 됨 | 주 계측 환경 |
| `google_apis_playstore` | user | 거부 | user 빌드 동작 대조 |
| `default` | userdebug | 부팅해 보지 않음 | 쓰지 않음 |

## x86_64 호스트가 거부한 arm64 AVD

AVD는 `avdmanager`로 만든다. 계측용 `p1c01-x86`과 arm64 쪽 `p1c01-arm64`를 API 33 google_apis 이미지의 x86_64판과 arm64-v8a판으로 하나씩 만들었다. 랩의 다른 AVD와 섞이지 않게 작업 폴더 안의 `avd/`를 `ANDROID_AVD_HOME`으로 잡았다. 입력을 닫아 둔 채(`</dev/null`) 실행하고 진행률 줄(`Loading …`)과 빈 줄은 걸러 냈다.

```text
$ export ANDROID_AVD_HOME=$(cygpath -w "$PWD/avd")
$ avdmanager create avd -n p1c01-x86 -k "system-images;android-33;google_apis;x86_64" -d pixel_6 </dev/null 2>&1 | tr '\r' '\n' | grep -v -E 'Loading|^ *$'
Auto-selecting single ABI x86_64
$ avdmanager create avd -n p1c01-arm64 -k "system-images;android-33;google_apis;arm64-v8a" -d pixel_6 </dev/null 2>&1 | tr '\r' '\n' | grep -v -E 'Loading|^ *$'
Auto-selecting single ABI arm64-v8a
$ emulator -list-avds
p1c01-arm64
p1c01-x86
```

`p1c01-arm64`의 `config.ini`에는 `abi.type=arm64-v8a`, `hw.cpu.arch=arm64`가 들어갔다. 만드는 데까지는 아무 문제가 없었다. 이렇게 만든 `p1c01-arm64`를 띄우자 `timeout 60`이 끊기도 전에 에뮬레이터가 종료 코드 1로 끝났다. 캡처의 `$AP`는 보조 포트 5620이다.

![timeout 60 emulator -avd p1c01-arm64 -port $AP -no-window -no-audio -no-snapshot 출력을 PANIC·FATAL·ERROR 로 거른 결과가 FATAL 머리의 Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator on x86_64 host. System image must match the host architecture. 한 줄인 터미널](/assets/img/android-mastery/p1c01/18-arm64-avd-fatal.png)

이 PC의 에뮬레이터는 36.5인데 그 브랜치의 소스는 공개돼 있지 않아서, 공개된 것 중 가장 새 릴리스 브랜치인 `emu-36-1-release`의 런처 [`main-emulator.cpp`](https://android.googlesource.com/platform/external/qemu/+/refs/heads/emu-36-1-release/android/emulator/main-emulator.cpp#1094)를 봤다. x86_64 호스트용으로 빌드된 런처는 AVD의 CPU가 arm64이고 API 레벨이 28 이상이면 그 자리에서 끝낸다.

```cpp
// platform/external/qemu emu-36-1-release, android/emulator/main-emulator.cpp 1093~1099행
#ifdef __x86_64__
            if (sarch == "arm64" && apiLevel >= 28) {
                APANIC("Avd's CPU Architecture '%s' is not supported by the "
                       "QEMU2 emulator on x86_64 host.\n",
                       avdarch);
            }
#endif
```

이 PC의 36.5.11 바이너리는 같은 문장을 `FATAL` 머리로 찍는다. 소스의 이 줄에는 없는 `System image must match the host architecture.`도 덧붙는데, `emulator.exe`에서 문자열을 뽑아 보면 이 꼬리까지 한 문자열로 들어 있다. 조건이 API 28 이상이라 그보다 오래된 arm64 이미지는 여기서 걸리지 않을 텐데, 그런 이미지는 띄워 보지 않았다.

## arm64 코드를 받지 않는 API 33 x86_64 이미지

그다음 주 에뮬레이터(API 33 x86_64)에 arm64 코드를 올려 봤다. 비교에 쓴 `hwprobe`는 직접 만든 작은 C 프로그램이다. `getauxval(AT_HWCAP)`과 `AT_HWCAP2`로 커널이 알려 주는 CPU 기능을 읽고 arm64로 빌드했을 때는 PACA·PACG·BTI·MTE 비트를 따로 풀어 찍는다. MTE는 [NDK의 MTE 안내](https://developer.android.com/ndk/guides/arm-mte)에 나오는 `PR_GET_TAGGED_ADDR_CTRL` prctl과, 동기 모드를 켜는 `PR_SET_TAGGED_ADDR_CTRL`을 불러 본다. PAC는 `paciza x9`를 직접 실행한다. `paciza`는 HINT 공간 밖의 PAC 명령이라 PAC가 없는 CPU에서는 정의되지 않은 명령이 되고 SIGILL이 난다. 그 SIGILL을 잡아 따로 보고하게 했다.

```c
// probe.c 53~83행 (같은 파일을 x86_64와 arm64로 각각 빌드한다)
#if defined(__aarch64__)
    unsigned long h = getauxval(AT_HWCAP), h2 = getauxval(AT_HWCAP2);
    out("hwcap bits   : PACA=%d PACG=%d BTI=%d MTE=%d\n",
        !!(h & HWCAP_PACA), !!(h & HWCAP_PACG), !!(h2 & HWCAP2_BTI), !!(h2 & HWCAP2_MTE));
#endif
    errno = 0;
    int g = prctl(PR_GET_TAGGED_ADDR_CTRL, 0, 0, 0, 0);
    out("prctl(GET_TAGGED_ADDR_CTRL) = %d (%s)\n", g, g < 0 ? strerror(errno) : "ok");
    errno = 0;
    int s = prctl(PR_SET_TAGGED_ADDR_CTRL,
                  PR_TAGGED_ADDR_ENABLE | PR_MTE_TCF_SYNC | (0xfffeUL << PR_MTE_TAG_SHIFT), 0, 0, 0);
    out("prctl(SET_TAGGED_ADDR_CTRL, MTE sync) = %d (%s)\n", s, s < 0 ? strerror(errno) : "ok");
#if defined(__aarch64__)
    /* PACIZA x9 is outside the HINT space: on a CPU without pointer authentication it is UNDEFINED. */
    struct sigaction sa, old; memset(&sa, 0, sizeof sa); sa.sa_handler = on_sigill;
    sigaction(SIGILL, &sa, &old);
    unsigned long before = (unsigned long)&probe;
    volatile unsigned long after = 0;
    if (sigsetjmp(jb, 1) == 0) {
        register unsigned long x9 __asm__("x9") = before;
        __asm__ volatile(".inst 0xdac123e9" : "+r"(x9));  /* paciza x9 */
        after = x9;
        /* a PAC only fills the unused top bits; the low 48 address bits stay as they were */
        out("paciza x9    : %#lx -> %#lx (%s)\n", before, after,
            after == before ? "unchanged" : after == 0 ? "zeroed, not a signature" :
            ((after ^ before) & 0xffffffffffffUL) == 0 ? "pointer signed" : "changed");
    } else {
        out("paciza x9    : SIGILL (instruction not implemented)\n");
    }
    sigaction(SIGILL, &old, NULL);
#endif
```

`src/hwprobe.c`는 `probe()`를 불러 결과를 표준 출력에 찍는 `main()` 하나가 든 세 줄짜리 파일이고, `src/jni.c`는 같은 결과를 logcat에 쓰고 Java 문자열로 돌려주는 JNI 함수 하나다.

빌드는 NDK 27.3 clang으로 했다. 아래는 Git Bash에서 작업 폴더를 기준으로 돌린 순서다. Java 쪽 APK는 랩의 작은 빌드 스크립트(`mkapk`)로 만들었는데, 그 스크립트가 하는 javac, d8, aapt 단계를 블록 머리에 풀어 적었다(스크립트는 이 APK를 한 번 정렬·서명까지 하지만 아래에서 어차피 다시 하므로 뺐다). `javac`는 Android Studio에 든 JBR 21, `d8`·`aapt`·`zipalign`·`apksigner`는 build-tools 36.0.0에 든 것을 PATH에 넣고 썼다.

```bash
NDK_BIN="$ANDROID_HOME/ndk/27.3.13750724/toolchains/llvm/prebuilt/windows-x86_64/bin"
CC="$NDK_BIN/clang.exe"
AJAR="$ANDROID_HOME/platforms/android-34/android.jar"
mkdir -p out/lib/arm64-v8a classes dex
"$CC" --target=x86_64-linux-android26  -O1 -o out/hwprobe-x86_64 src/hwprobe.c src/probe.c
"$CC" --target=aarch64-linux-android26 -O1 -mbranch-protection=standard -o out/hwprobe-arm64 src/hwprobe.c src/probe.c
"$CC" --target=aarch64-linux-android29 -O1 -mbranch-protection=standard -static -o out/hwprobe-arm64-static src/hwprobe.c src/probe.c
"$CC" --target=aarch64-linux-android26 -O1 -o out/hwprobe-arm64-nobp src/hwprobe.c src/probe.c   # 대조군: PAC/BTI 없음
# JNI 라이브러리 (arm64-v8a 전용)
"$CC" --target=aarch64-linux-android26 -O1 -fPIC -shared -mbranch-protection=standard \
  -o out/lib/arm64-v8a/libprobe.so src/jni.c src/probe.c -llog
# Java 부분만 든 abiprobe-base.apk (MainActivity.java 하나)
javac --release 8 -classpath "$(cygpath -w "$AJAR")" -d classes src/abiprobe/src/io/seika/abiprobe/MainActivity.java
d8 --min-api 26 --lib "$(cygpath -w "$AJAR")" --output dex classes/io/seika/abiprobe/*.class
aapt package -f -M src/abiprobe/AndroidManifest.xml -I "$(cygpath -w "$AJAR")" -F out/abiprobe-base.apk \
  --min-sdk-version 26 --target-sdk-version 33
(cd dex && aapt add ../out/abiprobe-base.apk classes.dex)
# 라이브러리를 넣고 정렬·서명
cp out/abiprobe-base.apk out/unsigned.apk
(cd out && aapt add unsigned.apk lib/arm64-v8a/libprobe.so)
zipalign -f -p 4 out/unsigned.apk out/aligned.apk
apksigner sign --ks "$(cygpath -w ~/.android/debug.keystore)" --ks-key-alias androiddebugkey \
  --ks-pass pass:android --key-pass pass:android --out out/abiprobe-arm64.apk out/aligned.apk
```

`-mbranch-protection=standard`를 준 `hwprobe-arm64`에는 BTI·PAC 속성 노트와 명령이 들어간다. `hwprobe-arm64-nobp`는 그 옵션을 뺀 대조군이다. 같은 `probe.c`를 JNI 라이브러리 `libprobe.so`로도 빌드해 arm64-v8a 라이브러리만 담은 APK `io.seika.abiprobe`(minSdk 26, targetSdk 33)에 넣었다. 이 앱은 Java 쪽 `os.arch`, `Build.SUPPORTED_ABIS`, `nativeLibraryDir`와 JNI 프로브 결과를 화면과 logcat에 함께 찍는다.

![API 33 x86_64 기기의 abilist x86_64, native.bridge 0, grep -c mte /proc/cpuinfo 0, hwprobe-x86_64 의 AT_HWCAP 0x78bfbff 와 tagged-addr prctl 두 번의 -1 (Invalid argument), hwprobe-arm64 실행이 not executable: 64-bit ELF file, abiprobe-arm64.apk 설치가 INSTALL_FAILED_NO_MATCHING_ABIS res=-113 으로 실패하는 터미널](/assets/img/android-mastery/p1c01/09-arm64-avd-api33-abi.png)

이 이미지의 `ro.product.cpu.abilist`는 `x86_64` 하나이고 `ro.dalvik.vm.native.bridge`는 `0`이다. MTE 안내 문서가 확인법으로 드는 `grep mte /proc/cpuinfo`는 0줄이다. x86_64 프로브의 `AT_HWCAP` `0x78bfbff`는 x86 CPUID 기능 비트다. tagged address prctl은 두 번 다 `Invalid argument`였다. arm64 실행 파일은 셸이 `not executable: 64-bit ELF file`로 거부했고 arm64 라이브러리만 든 APK는 `INSTALL_FAILED_NO_MATCHING_ABIS`(res=-113)로 설치조차 되지 않았다. 이 이미지에서 arm64 전용 네이티브 코드는 돌지 않는다.

ARM 번역이 실려 있는지는 이미지마다 달랐다. Google은 [Android 11 시스템 이미지부터](https://android-developers.googleblog.com/2020/03/run-arm-apps-on-android-emulator.html) ARM 명령을 x86으로 번역해 실행할 수 있다고 발표하면서, 이 기능은 Google APIs와 Play Store 이미지에만 들어간다고 했다. 이 PC의 이미지를 열어 보면 API 33 google_apis x86_64(rev 17)와 API 33 Play 이미지(rev 9)는 vendor `ro.vendor.product.cpu.abilist`가 `x86_64` 하나뿐이고 native bridge가 `0`이다. API 36 google_apis x86_64(rev 7)는 `x86_64,arm64-v8a`에 `libndk_translation.so`가 걸려 있다. 오래된 API 28 google_apis x86(rev 12)은 `x86,armeabi-v7a,armeabi`로 32비트 ARM을 내건다. ARM 네이티브 코드를 돌려야 한다면 이미지를 고를 때 abilist와 native bridge 두 속성부터 본다.

## API 36 번역 환경에서 arm64 프로세스가 본 CPU

ARM 번역이 실린 AVD `sec-36-std`(Android 16, API 36 google_apis x86_64, 빌드 `BE2A.250530.026.F3`, 보안 패치 2025-07-05, 커널 6.6.66)를 보조 포트에 띄우고 같은 바이너리와 APK를 올렸다.

![API 36 sec-36-std 에서 release 16, abilist x86_64,arm64-v8a, native.bridge libndk_translation.so, binfmt_misc 의 arm64_dyn·arm64_exe·arm_dyn·arm_exe 와 ndk_translation_program_runner_binfmt_misc_arm64 가 보이고 번역 실행한 hwprobe-arm64 가 compiled for aarch64, uname -m x86_64, AT_PLATFORM (null), AT_HWCAP 0x19b, AT_HWCAP2 0, PACA=0 PACG=0 BTI=0 MTE=0, prctl 두 번 Invalid argument, paciza x9 0x7f869e881e08 -> 0 (zeroed, not a signature), cpuinfo Features fp asimd aes pmull crc32 atomics 를 찍은 뒤 abiprobe-arm64.apk 설치 Success 와 primaryCpuAbi=arm64-v8a 가 나오는 터미널](/assets/img/android-mastery/p1c01/10-api36-translation.png)

`/proc/sys/fs/binfmt_misc/`에는 `arm64_dyn`과 `arm64_exe`가 등록돼 있다. 둘 다 해석기가 `/system/bin/ndk_translation_program_runner_binfmt_misc_arm64`다. 매직 값은 ELF 헤더에서 `e_type`(`0300`은 ET_DYN, `0200`은 ET_EXEC)과 `e_machine` 첫 바이트 `b7`(AArch64)까지 맞춰 본다. 셸에서 arm64 실행 파일을 그냥 실행해도 커널이 이 x86_64 러너에게 넘기고 러너가 `libndk_translation.so`로 번역해 돌리는 구조로 보인다. 32비트 ARM용 `arm_dyn`, `arm_exe`도 따로 등록돼 있었다. 다만 이 둘이 가리키는 `ndk_translation_program_runner_binfmt_misc`는 `/system/bin`에 없었고 abilist에도 armeabi가 없어서, 32비트 ARM 실행은 시도하지 않았다.

번역된 `hwprobe-arm64`가 본 CPU는 이랬다. `uname -m`은 `x86_64` 그대로다. uname은 커널에 묻는 시스템 콜인데, 번역기가 그 값을 바꾸지 않고 그대로 넘기는 듯하다. `AT_PLATFORM`은 없고 `AT_HWCAP`은 `0x19b`, `AT_HWCAP2`는 0이다. 0x19b를 arm64 HWCAP 비트로 풀면 FP, ASIMD, AES, PMULL, CRC32, ATOMICS다. 같은 프로세스가 읽은 `/proc/cpuinfo`의 `Features` 줄(`fp asimd aes pmull crc32 atomics`)과 같은 집합이다. API 33에서 x86_64 프로브가 읽은 cpuinfo는 x86 `flags` 줄이었으니, 번역기가 auxv와 cpuinfo를 게스트용으로 꾸며 내놓는 것으로 보인다. 그렇게 꾸민 CPU에는 PACA·PACG(HWCAP 30, 31번 비트)도, BTI·MTE(HWCAP2 17, 18번 비트)도 없다. tagged address prctl은 둘 다 `Invalid argument`로, x86_64 프로브가 받은 값과 같았다.

뜻밖이었던 건 `paciza x9`다. PAC가 없는 CPU라면 SIGILL이 나야 하고 PAC가 있으면 위쪽 비트에 서명이 붙은 포인터가 돌아와야 한다. 번역기 아래에서는 레지스터가 0이 됐다. 같은 실행 파일을 세 번 더 돌리자 주소는 ASLR로 매번 바뀌었지만(`0x7d5f3f841e08`, `0x75f6963c1e08`, `0x7eb662b41e08`) 결과는 모두 0이었고, 앱의 JNI 안에서 불러도 같았다. 번역기 소스를 보지 않아서 왜 0이 되는지는 확인하지 못했다.

BTI·PAC 노트가 붙은 `hwprobe-arm64`와 노트가 없는 `hwprobe-arm64-nobp`는 출력이 똑같았다(대조군도 `paciza x9 : 0x770dfc901d60 -> 0`). HWCAP2의 BTI 비트가 0인 것과 맞아떨어진다. 정적 링크한 `hwprobe-arm64-static`은 번역기 아래에서 `Segmentation fault`(SIGSEGV, `SI_KERNEL`, 종료 코드 139)로 죽었다. tombstone의 ABI는 `'x86_64'`, 명령줄은 러너에 바이너리 경로를 넘긴 형태였다.

APK는 `Success`로 깔렸고 `primaryCpuAbi=arm64-v8a`였다. 앱을 실행한 화면이 아래다.

![API 36 에뮬레이터의 ABI Probe 앱 화면. Java/ART 쪽 os.arch aarch64, SUPPORTED_ABIS x86_64,arm64-v8a, nativeLibDir 끝이 lib/arm64 이고 libprobe.so 쪽 compiled for aarch64, uname -m x86_64, AT_PLATFORM (null), AT_HWCAP 0x19b, AT_HWCAP2 0, PACA=0 PACG=0 BTI=0 MTE=0, prctl 두 번 Invalid argument, paciza x9 0x786a62deeda4 -> 0 (zeroed, not a signature), cpuinfo Features fp asimd aes pmull crc32 atomics](/assets/img/android-mastery/p1c01/11-abiprobe-api36-screen.png)

JNI 쪽 값은 셸에서 돌린 프로브와 같다. Java 쪽 `os.arch`는 `aarch64`로 나왔다. ART는 x86_64로 돌 테니 `x86_64`가 찍힐 거라고 봤는데 아니었다. 앱 프로세스의 실행 파일은 `/system/bin/app_process64`였고, maps에는 `lib/arm64/libprobe.so`와 함께 `/system/lib64/libndk_translation.so`, `libndk_translation_proxy_libc.so`가 올라와 있었다. `os.arch`는 libnativebridge가 번역기를 초기화하면서 번역기가 알려 준 값으로 덮어쓴다([`native_bridge.cc`의 `SetupEnvironment()`](https://android.googlesource.com/platform/art/+/refs/tags/android-16.0.0_r1/libnativebridge/native_bridge.cc#458)).

```cpp
// platform/art libnativebridge/native_bridge.cc (android-16.0.0_r1), 458~466행
  if (env_values->os_arch != nullptr) {
    jclass sclass_id = env->FindClass("java/lang/System");
    if (sclass_id != nullptr) {
      jmethodID set_prop_id = env->GetStaticMethodID(sclass_id, "setUnchangeableSystemProperty",
          "(Ljava/lang/String;Ljava/lang/String;)V");
      if (set_prop_id != nullptr) {
        // Init os.arch to the value reqired by the apps running with native bridge.
        env->CallStaticVoidMethod(sclass_id, set_prop_id, env->NewStringUTF("os.arch"),
            env->NewStringUTF(env_values->os_arch));
```

같은 프로세스 안에서 `uname -m`은 `x86_64`를 그대로 돌려줬다. 그래서 기기 아키텍처를 판단하는 코드가 `os.arch`를 보면 `aarch64`를, `uname`을 보면 `x86_64`를 얻는다. 밖에서 본 `/proc/<pid>/exe`는 `/system/bin/app_process64`였는데, 이 경로는 arm64 기기에서도 같아서 경로만으로는 x86_64가 드러나지 않는다. 그 파일의 ELF 헤더(`e_machine`)를 읽으면 차이가 날 것으로 보이지만 거기까지는 보지 않았다. 번역된 코드 안에서 `/proc/self/exe`를 읽으면 무엇이 나오는지도 재지 않았다.

## 바이너리에 든 PAC·BTI와 그것을 실행할 CPU

arm64 런타임에서 PAC·BTI·MTE가 실제로 걸리는 모습은 이 호스트에서 보지 못했고, 랩에는 arm64 실기기도 없다. 확인할 수 있었던 것은 바이너리 쪽, 그리고 호스트 WSL의 qemu-user로 CPU 모델만 바꿔 같은 프로브를 돌린 결과다. qemu-user는 리눅스 사용자 모드 에뮬레이션이라 Android에서 잰 값이 아니다. 캡처의 `llvm-readelf`와 `llvm-objdump`는 `$NDK_BIN`을 PATH 앞에 넣고 실행한 NDK 27.3 판이다.

![llvm-readelf --notes 가 hwprobe-arm64 에서 aarch64 feature: BTI, PAC 를 보이고 대조군 nobp 는 0, llvm-objdump 가 probe 함수의 paciasp·bti j·paciza x9·autiasp 를 보이며, WSL qemu-aarch64-static -cpu cortex-a53 에서는 AT_HWCAP 0x8fb, PACA=0 PACG=0 BTI=0 MTE=0, MTE sync prctl -1 (Invalid argument), paciza SIGILL, -cpu max 에서는 AT_HWCAP 0xeffffffb, PACA=1 PACG=1 BTI=1 MTE=1, MTE sync prctl 0 (ok), paciza 0x219c98 -> 0x55000000219c98 (pointer signed) 인 터미널](/assets/img/android-mastery/p1c01/07-probe-static-qemu.png)

`llvm-readelf --notes`는 `hwprobe-arm64`에 `aarch64 feature: BTI, PAC` 속성이 있다고 보여 주고 대조군에는 그 줄이 없다. 역어셈블하면 함수 앞뒤의 `paciasp`와 `autiasp`, 간접 점프의 착지점을 표시하는 `bti j`, 프로브가 일부러 넣은 `paciza x9`가 보인다. 정적 빌드를 `-cpu cortex-a53`으로 돌리면 PAC·BTI·MTE 비트가 0이다. MTE 동기 모드를 켜는 prctl은 `Invalid argument`, `paciza`는 SIGILL이다. `-cpu max`에서는 네 비트가 모두 1이 되고 MTE prctl도 성공한다. `paciza`는 `0x219c98`을 `0x55000000219c98`로 바꿨다. 아래쪽 48비트 주소는 그대로 두고 위쪽 비트에만 서명이 붙었다. 키가 프로세스마다 달라서 서명 값은 실행할 때마다 바뀐다(다른 실행에서는 `0x5d000000219c98`).

[Arm의 아키텍처 발표](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/arm-a-profile-architecture-2018-developments-armv85a)를 기준으로 PAC는 Armv8.3-A, BTI와 MTE는 Armv8.5-A 확장이다. Android의 [MTE 안내](https://developer.android.com/ndk/guides/arm-mte)는 MTE를 Armv9 세대 기능으로 소개하면서 지원 기기로 Pixel 8 이후 실기기를 든다. 커널 쪽 MTE 태그 검사는 QEMU 시스템 에뮬레이션에 Android Common Kernel을 올린 [Android Kernel Security 02](/posts/android-kernel-security-arm64-ack-mte/)에서 본 적이 있다.

`-cpu cortex-a53`에서도 프로브는 `paciza`에 닿을 때까지 멀쩡히 돌았다. 함수 입구의 `paciasp`와 본문의 `bti j`는 HINT 공간 명령이라 그 기능이 없는 CPU에서는 아무 일 없이 지나가고, 라이브러리는 보호 없이 그대로 실행된다. 앱의 네이티브 라이브러리가 이 옵션으로 빌드됐는지는 실기기 없이 `llvm-readelf --notes`로 확인한다. `BTI, PAC` 줄이 없으면 링크된 오브젝트 가운데 하나 이상이 그 옵션 없이 빌드된 것이다. 이 노트는 링크한 모든 입력의 AND라서, 대조군처럼 전부 옵션 없이 빌드한 경우와 손으로 쓴 어셈블리 파일이나 미리 빌드된 정적 라이브러리 하나만 빠진 경우가 똑같이 보인다. 함수 단위로 PAC가 들어갔는지는 위처럼 `llvm-objdump -d`로 `paciasp`·`autiasp`와 `bti`를 찾아 본다. 노트가 있는 라이브러리에서 보호가 실제로 걸리는지는 PAC와 BTI를 갖춘 arm64 기기에서만 확인된다.

## /system 쓰기는 -writable-system으로

실기기에서 흔히 쓰는 순서는 `adb disable-verity`, 재부팅, `adb remount`다. 에뮬레이터 [명령줄 문서](https://developer.android.com/studio/run/emulator-commandline)와 `emulator -help-writable-system`은 다른 방법을 적어 둔다. AVD를 `-writable-system`으로 띄운 뒤 `adb remount`를 하라는 것이다. 이때 만들어지는 시스템 이미지 사본은 에뮬레이터를 끄면 지워진다고 한다.

먼저 랩의 주 에뮬레이터에서 `adb disable-verity`와 `adb remount`를 그 사이 재부팅 없이 차례로 쳐 봤다(remount가 재부팅을 요구하면 그때 하려고 했다). 이 인스턴스는 `-read-only -no-snapshot`으로 띄웠고 root 상태다.

![-read-only 로 띄운 API 33 userdebug 기기에서 / 와 /vendor 가 ext4 ro, adb disable-verity 가 avb_user_verity.c Error writing to partition 'vbmeta' 와 Error setting verity 를 찍고 adb remount 가 같은 vbmeta 오류 뒤 Skipping /system for remount, liblp WritePrimaryMetadata write 840 bytes failed: Operation not permitted 와 add partition scratch 를 네 번, Can not mount overlayfs for partitions, /vendor·/product·/system_dlkm·/system_ext 의 Permission denied, remount failed 를 찍은 뒤 touch /system/p1c01-marker 가 Read-only file system rc=1 인 터미널](/assets/img/android-mastery/p1c01/12-remount-readonly.png)

`disable-verity`는 vbmeta 파티션에 쓰지 못해 `Error setting verity`를 찍었는데 종료 코드는 0이었다. 스크립트에서 종료 코드만 보면 성공으로 넘어간다. `adb remount`는 같은 vbmeta 오류 뒤 `/system`을 건너뛰었다. 이어서 overlayfs에 쓸 `scratch` 파티션을 super 메타데이터에 추가하려다 `Operation not permitted`로 네 번 실패했다. 결과는 `remount failed`(종료 코드 10)였다. 재부팅하라는 말은 없었고 `/system`에 `touch`하면 `Read-only file system`이다. 실패가 `-read-only`로 띄운 디스크 때문인지는 이것만으로 알 수 없었다. `-read-only`만 빼고 `-writable-system` 없이 띄운 대조는 해 보지 않았다.

그래서 앞에서 만들어 둔 `p1c01-x86`(같은 API 33 google_apis x86_64 이미지)을 `-writable-system`으로 띄웠다. 실제로 돌린 순서는 아래와 같다. 첫 `adb remount`와 두 번째 사이에 재부팅이 한 번 들어간다.

```bash
export ANDROID_AVD_HOME=$(cygpath -w "$PWD/avd")
emulator -avd p1c01-x86 -port 5620 -no-window -no-audio -no-boot-anim -memory 2048 \
  -gpu swiftshader_indirect -writable-system -no-snapshot &
A=emulator-5620
until [ "$(adb -s $A shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; do sleep 3; done
adb -s $A root; sleep 3; adb -s $A wait-for-device
adb -s $A remount          # 첫 번째: verity를 끄고 재부팅을 요구한다
adb -s $A reboot; sleep 15
adb -s $A wait-for-device shell 'while [ "$(getprop sys.boot_completed)" != 1 ]; do sleep 2; done; echo boot_completed=1'
adb -s $A root; sleep 4; adb -s $A wait-for-device
adb -s $A remount          # 두 번째: remount succeeded
adb -s $A shell 'touch /system/p1c01-marker && ls -l /system/p1c01-marker'
```

이 AVD는 첫 부팅부터 `ro.boot.verifiedbootstate`가 `orange`였다. 문서만 보면 여기서 `adb remount` 한 번이면 끝날 것 같았는데, 첫 remount는 verity를 끄고 overlayfs를 준비한 다음 재부팅을 요구했다. 이 상태에서는 아직 `/system`에 쓸 수 없다.

![-writable-system 으로 띄운 p1c01-x86 에서 ro.build.type userdebug, id -u 0, 첫 adb remount 가 Disabling verity for /system, Using overlayfs for /system·/vendor·/product·/system_dlkm·/system_ext, Now reboot your device for settings to take effect 를 찍고 touch /system/p1c01-marker 는 Read-only file system, mount 에서 / 는 ext4 ro 인 터미널](/assets/img/android-mastery/p1c01/13-remount-writable-system.png)

재부팅하고 다시 remount하자 `remount succeeded`가 나왔고 `/system/p1c01-marker`가 만들어졌다.

![adb reboot 뒤 boot_completed=1, adb root 는 빈 출력, adb remount 가 remount succeeded, touch 한 /system/p1c01-marker 가 -rw-rw-rw- root root 0 2026-10-15 01:43 으로 보이고 mount 에서 / 와 /vendor 는 ext4 ro 이며 그 위에 overlay on /vendor 와 overlay on /system 이 rw, upperdir=/mnt/scratch/overlay/vendor/upper 와 /mnt/scratch/overlay/system/upper 로 붙은 터미널](/assets/img/android-mastery/p1c01/16-remount-after-reboot.png)

`/`는 재부팅 뒤에도 `ro`다. `/system`과 `/vendor` 위에 overlay가 rw로 얹혔다. 쓰기는 `/mnt/scratch/overlay/` 아래의 upper 디렉터리로 간다. `/mnt/scratch`는 2.5G짜리 f2fs(240M 사용)였고 overlay는 `/product`, `/system_dlkm`, `/system_ext`에도 같은 식으로 붙었다. 이 AVD를 `-writable-system` 없이 다시 띄운 실행에서는 마커도 overlay 마운트도 없었고 `verifiedbootstate`도 빈 값이었다. 도움말은 이 사본이 에뮬레이터 종료 때 지워진다고 하지만, 같은 플래그로 다시 띄웠을 때 쓰기 층이 남는지는 확인하지 않았다. 부팅 상태 색과 verity의 관계는 [Verified Boot·AVB(C28)](/posts/android-concept-atlas-c28-verified-boot-avb/)에 있다.

## 실험 사이의 기준선은 스냅샷 대신 새 부팅으로

에뮬레이터 콘솔의 [`avd snapshot` 명령](https://developer.android.com/studio/run/emulator-console)으로 상태를 저장하고 되돌릴 수 있고 `adb emu`로 콘솔 명령을 넘길 수 있다. 그런데 랩의 공용 인스턴스에서는 저장부터 거부됐다.

![-read-only 공용 인스턴스에서 adb emu avd snapshot save clean 이 KO: Snapshot save is disabled because -read-only was specified 로 거부되고 /data/local/tmp/p1c01-dirty 를 만든 뒤 labemu fresh $PORT 가 emulator-5600 ready: 0 Enforcing 을 찍고 다시 본 p1c01-dirty 는 No such file or directory 인 터미널](/assets/img/android-mastery/p1c01/14-readonly-baseline.png)

`emulator -help-read-only`는 이 옵션을 같은 AVD로 여러 인스턴스를 동시에 띄우게 해 주는 대신 스냅샷은 저장할 수 없는 모드라고 설명한다. load도 같은 이유로 `KO: Snapshot load is disabled because "-read-only" was specified`였다. 종료 때의 자동 저장만 끄는 `-no-snapshot-save`와는 다르다. 쓰기 가능한 AVD를 그 옵션으로 띄웠을 때 콘솔의 수동 save는 `OK`였다. 공용 인스턴스에서 스냅샷을 쓸 수 없으니 이 랩은 실험을 시작할 때마다 인스턴스를 새로 부팅해 기준선을 잡는다. 캡처의 `labemu fresh`가 그 일을 하는 랩 스크립트다(`$PORT`는 5600). 해당 포트의 에뮬레이터를 끄고 아래 명령으로 다시 띄운 뒤, 부팅이 끝나면 `adb root`를 한 다음 uid와 SELinux 모드를 찍는다(`ready: 0 Enforcing`).

```bash
emulator -avd codex-atlas-api33 -read-only -no-window -no-audio -no-boot-anim -no-snapshot \
  -port 5600 -memory 2048 -gpu swiftshader_indirect
```

다시 부팅하기 전에 만든 `p1c01-dirty`는 부팅 뒤에 없었다. 앞 실험에서 올린 `hwprobe-*`도 사라졌다. `/data/local/tmp`에는 AVD 디스크에 원래 들어 있던 파일(frida-server 등)만 남았다.

쓰기 가능한 `p1c01-x86`에서는 스냅샷이 됐다. 스냅샷을 저장하고 파일을 만든 뒤 되돌리자 파일이 사라졌다.

![쓰기 가능한 p1c01-x86 에서 adb emu avd snapshot save clean 이 OK, p1c01-dirty 생성, snapshot load clean 이 OK, sleep 30 뒤 adb devices 에 emulator-5620 device, emu avd status 가 virtual device is running, 로드 뒤 ls /data/local/tmp/ 가 빈 출력인 터미널](/assets/img/android-mastery/p1c01/17-snapshot-load-restore.png)

다만 이 호스트에서 스냅샷 로드는 믿을 만하지 않았다. 로드를 네 번 해서 두 번은 위처럼 복원됐다(save→load 세 번에 한 번, 이미 저장된 스냅샷을 load만 한 실험에서 한 번). 나머지 두 번은 로드 직후 adb가 `offline`에 머물렀다(첫 번째는 5분 넘게 지켜봤고, 두 번째는 세션 제한 4분이 지나고 `avd stop`·`avd start`까지 해 본 뒤 껐다). 그동안 콘솔의 `avd status`는 `virtual device is running`이었다. 첫 번째 실패 때 콘솔로 찍은 화면의 시계는 스냅샷 시각에 멈춰 있었다. `adb reconnect`, 한 번 더 load, `avd stop`과 `avd start`로도 풀리지 않았다. 로드 직후 adb를 너무 일찍 건드려서라고 의심하고 5초 뒤 바로 `wait-for-device`를 걸어 봤는데, 그때는 8초 만에 정상으로 붙었다. 원인은 찾지 못했다.

## 실험 전에 받아 두는 환경 값

인스턴스를 띄울 때마다 아래 값부터 받아 둔다. 결과를 다시 볼 때 어느 이미지, 어떤 SELinux·암호화 상태에서 나온 것인지 이 출력으로 가린다.

```bash
S=emulator-5600
adb -s $S shell 'getprop ro.build.fingerprint; getprop ro.build.version.sdk; getprop ro.build.version.security_patch; getprop ro.crypto.type; getprop ro.crypto.state; getenforce; uname -r; getprop ro.product.cpu.abilist; getprop ro.dalvik.vm.native.bridge'
```

랩 AVD 세 개에서 받은 값이다.

| 값 | codex-atlas-api33 | mastery-play33 | sec-36-std |
|--|--|--|--|
| 이미지 | API 33 google_apis | API 33 google_apis_playstore | API 36 google_apis |
| fingerprint 끝 | userdebug/dev-keys | user/release-keys | userdebug/dev-keys |
| 보안 패치 | 2024-03-01 | 2024-03-01 | 2025-07-05 |
| crypto type, state | file, encrypted | file, encrypted | file, encrypted |
| getenforce | Enforcing | Enforcing | Enforcing |
| 커널 | 5.15.119 | 5.15.119 | 6.6.66 |
| abilist | x86_64 | x86_64 | x86_64,arm64-v8a |
| native bridge | 0 | 0 | libndk_translation.so |

세 이미지 모두 파일 기반 암호화(`file`, `encrypted`)와 SELinux Enforcing 상태로 돈다. 이 둘은 CPU 아키텍처와 상관없어서 x86_64 에뮬레이터에서도 관찰할 수 있다([FBE·Direct Boot(C43)](/posts/android-concept-atlas-c43-fbe-direct-boot/)). 반대로 에뮬레이터에는 TEE와 StrongBox가 없으니 [Keystore(C40)](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/)와 [롤백 방지(C29)](/posts/android-concept-atlas-c29-rollback-protection/)의 하드웨어 쪽은 이 랩에서 볼 수 없다. 이번에 Keystore 보안 수준을 따로 재지는 않았다. 커널이나 부팅 체인까지 바꿔 봐야 하는 실험은 Cuttlefish로 넘긴다.

참고 자료: [sdkmanager](https://developer.android.com/tools/sdkmanager) · [에뮬레이터 명령줄 옵션](https://developer.android.com/studio/run/emulator-commandline) · [에뮬레이터 콘솔](https://developer.android.com/studio/run/emulator-console) · [AVD 관리](https://developer.android.com/studio/run/managing-avds) · [Arm MTE (NDK)](https://developer.android.com/ndk/guides/arm-mte) · [에뮬레이터의 ARM 앱 번역](https://android-developers.googleblog.com/2020/03/run-arm-apps-on-android-emulator.html) · [adb daemon (android-13.0.0_r1)](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-13.0.0_r1/daemon/)

*다음 글: [adb·logcat·dumpsys 증적 수집](/posts/android-lab-p1c02-adb-evidence-collection/)*
