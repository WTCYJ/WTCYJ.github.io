---
layout: post
title: "[Android 앱 보안 S01] 재현 가능한 실습 환경 구축"
date: 2026-09-02 09:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, AVD, 에뮬레이터, adb, Frida, jadx, apktool, 실습환경, 학습기록]
excerpt: "Android 앱 보안을 처음부터 체계적으로 다시 밟아 보려고 합니다. 그 첫 글은 화려한 취약점이 아니라, 언제 다시 켜도 똑같은 상태로 돌아오는 실습 환경을 만드는 일입니다. AVD를 새로 만들고 부팅해서 API·ABI·빌드 타입·SELinux·adb root를 실제로 확인하고, 스냅샷과 초기화 절차, 네트워크 구성, 도구 버전까지 실행 결과로 남깁니다."
---

> 이 글은 시리즈의 첫 편입니다. 앞으로 S02, S03… 순서로 APK 수집·정적 분석·저장소·컴포넌트·WebView·네트워크·인증 같은 주제를 하나씩 다룹니다. 그 전에, 모든 실습이 딛고 설 바닥부터 만듭니다.

취약점을 파기 전에 늘 발목을 잡는 건 환경이었습니다. 어제 되던 게 오늘 안 되고, 에뮬레이터가 갑자기 다른 상태가 되어 있고, 도구 버전이 바뀌어 있고. 그래서 이번 시리즈는 첫 글을 아예 환경 구축에만 씁니다. 목표는 하나입니다. 언제 다시 켜도 똑같은 상태로 돌아오는, 기록으로 남는 실습 환경.

이번 편은 취약점 실습이 아니라 바닥 다지기라, 뒤에 나올 대상 앱이나 근본 원인·수정 같은 항목은 자연히 비어 있습니다. 그 칸들은 S02부터 채워집니다.

---

## 실습 목표

- Android Studio SDK로 실습 전용 AVD를 새로 만들고 부팅한다.
- API 버전, ABI, 빌드 타입, SELinux 상태, adb 연결과 root 승격을 실제 명령으로 확인한다.
- 스냅샷 저장과 초기화(리셋) 절차를 만들어, 매번 같은 상태에서 시작할 수 있게 한다.
- 실습 네트워크(호스트 루프백, 프록시)를 확인한다.
- 사용하는 도구의 버전을 전부 기록한다.

---

## 윤리적 범위와 허가 조건

이 시리즈 전체에 걸리는 원칙을 첫 글에 못 박아 둡니다.

- 실습은 내가 소유했거나 명시적으로 허용된 교육용 앱에서만 합니다. 실제 서비스, 남의 계정, 남의 기기, 운영 서버는 대상이 아닙니다.
- 실물 기기는 쓰지 않습니다. Android Studio AVD(에뮬레이터)와 로컬 서버만 씁니다.
- 명령은 실제로 실행하고 결과를 그대로 싣습니다. 안 돌려 본 걸 돌렸다고 쓰지 않고, 재현하지 못한 건 이유와 환경 한계를 밝힙니다.
- 관측과 보안 경계 무력화를 구분해서 씁니다. 우회 코드가 필요하면 내가 소유한 실습 앱 내부 검증에만 씁니다.
- 공격 성공에서 끝내지 않고 원인·수정·재검증까지 갑니다(취약점을 다루는 편부터).

S01은 이 원칙 안에서도 가장 안전한 축입니다. 대상은 내가 방금 만든 빈 에뮬레이터 하나뿐이고, 밖으로 나가는 트래픽도 없습니다.

---

## 환경 및 도구 버전

호스트는 Windows 11이고, SDK는 `%LOCALAPPDATA%\Android\Sdk`에 있습니다. 이번에 만든 AVD와 도구 버전은 아래와 같습니다. 전부 실행해서 뽑은 값입니다.

| 항목 | 값 |
|---|---|
| AVD 이름 | `aas-api33` (Pixel 6 프로필) |
| 시스템 이미지 | `system-images;android-33;google_apis;x86_64` (Android 13 Tiramisu) |
| adb | 1.0.41 / 37.0.0 |
| emulator | 36.5.11.0 |
| build-tools | 36.0.0 (aapt2 2.20) |
| apksigner | build-tools 36.0.0 |
| jadx | `C:\Users\yejun\android-sec-tools\bin\jadx.bat` |
| apktool | `C:\Users\yejun\android-sec-tools\bin\apktool.bat` |
| Frida | 17.17.0 (frida-python 17.17.0) |
| Java | 26.0.1 |
| Python | 3.11.0 |

`google_apis` 이미지를 고른 게 중요합니다. `google_apis_playstore`는 프로덕션 빌드라 `adb root`가 막히는데, `google_apis`(그리고 뒤에서 확인할 `userdebug` 빌드)는 root 승격이 됩니다. 저장소를 직접 열어 봐야 하는 실습에서는 이 차이가 갈림길입니다.

동적 분석용 프록시(Burp 또는 mitmproxy)와 Objection은 아직 깔지 않았습니다. 각각 필요한 편(S09·S10·S14)에서 설치하고 그때 버전을 기록하겠습니다. 지금 없는 걸 있다고 적어 두지는 않습니다.

---

## 위협 모델 — 이 랩의 신뢰 경계

취약점 편이라면 여기서 대상 앱의 공격 표면을 그리겠지만, S01의 대상은 실습 환경 그 자체입니다. 그래서 위협 모델 대신 이 랩이 무엇을 신뢰하고 무엇을 열어 두는지를 적어 둡니다.

- 에뮬레이터는 신뢰 경계 밖의 "테스트 대상"입니다. 그래서 일부러 `adb root`가 되는 `userdebug` 빌드를 씁니다. 실기기 사용자를 흉내 내는 게 아니라, 앱 내부를 열어 관찰하는 분석자 시점이기 때문입니다.
- 네트워크는 호스트 로컬로 가둡니다. 에뮬레이터에서 `10.0.2.2`가 호스트의 `127.0.0.1`로 매핑되므로, 뒤 편들의 테스트 서버는 전부 이 경로 안에서만 돕니다.
- SELinux는 켠 채로 둡니다(Enforcing). 실기기와 같은 강제 접근 제어 위에서 관찰하기 위해서입니다.

---

## 재현 절차

### 1. AVD 생성

`avdmanager`로 실습 전용 AVD를 새로 만듭니다. 이름을 시리즈에 묶어 두면 나중에 헷갈리지 않습니다.

```bash
avdmanager create avd -n aas-api33 -k "system-images;android-33;google_apis;x86_64" -d pixel_6 --force
```

만들어진 정의를 확인합니다.

```console
$ avdmanager list avd
    Name: aas-api33
  Device: pixel_6 (Google)
    Path: C:\Users\yejun\.android\avd\aas-api33.avd
  Target: Google APIs (Google Inc.)
          Based on: Android 13.0 ("Tiramisu") Tag/ABI: google_apis/x86_64
  Sdcard: 512 MB
```

### 2. 콜드 부팅

스냅샷을 불러오지 않고(`-no-snapshot-load`) 맨 상태에서 올립니다. 처음 한 번은 깨끗한 기준점을 잡아야 하기 때문입니다.

```bash
emulator -avd aas-api33 -no-snapshot-load -gpu swiftshader_indirect -no-boot-anim -netdelay none -netspeed full
```

부팅이 끝났는지는 화면이 아니라 속성으로 확인합니다.

```console
$ adb wait-for-device
$ adb shell getprop sys.boot_completed
1
$ adb devices
List of devices attached
emulator-5554	device
```

### 3. 디바이스 속성 검증

이 실습이 어떤 기기 위에서 돌아가는지 못 박아 둡니다. API, ABI, 빌드 타입, 지문, 보안 패치까지 한 번에 뽑았습니다.

```console
$ adb shell getprop ro.build.version.sdk       # API
33
$ adb shell getprop ro.build.version.release   # Android 버전
13
$ adb shell getprop ro.product.cpu.abi
x86_64
$ adb shell getprop ro.build.type
userdebug
$ adb shell getprop ro.product.model
sdk_gphone64_x86_64
$ adb shell getprop ro.build.fingerprint
google/sdk_gphone64_x86_64/emu64x:13/TE1A.240213.009/12342917:userdebug/dev-keys
$ adb shell getprop ro.build.version.security_patch
2024-03-01
```

빌드 타입이 `userdebug`인 게 핵심입니다. 이래야 다음 단계의 root 승격이 됩니다.

### 4. SELinux와 adb root

SELinux는 실기기와 똑같이 Enforcing 상태를 유지하고, 그 위에서 `adb root`로 uid 0을 얻습니다.

```console
$ adb shell getenforce
Enforcing

$ adb root
restarting adbd as root
$ adb shell id
uid=0(root) gid=0(root) groups=0(root),1004(input),1007(log),... context=u:r:su:s0
```

Enforcing인데도 root가 되는 건 모순이 아닙니다. SELinux 정책(강제 접근 제어)은 그대로 살아 있고, 다만 이 `userdebug` 이미지가 디버그 목적의 root 승격을 허용할 뿐입니다. 실기기 사용자 환경이 아니라 분석용 환경이라는 뜻입니다.

### 5. 실습 네트워크 확인

에뮬레이터의 NAT 주소와 호스트 루프백 매핑을 확인합니다. 뒤 편들의 테스트 서버가 전부 이 위에서 돕니다.

```console
$ adb shell ip -4 addr show | grep 'inet '
    inet 127.0.0.1/8 scope host lo
    inet 10.0.2.15/8 brd 10.255.255.255 scope global eth0
    inet 10.0.2.16/24 brd 10.0.2.255 scope global wlan0
```

`10.0.2.15`가 에뮬레이터, `10.0.2.2`가 호스트(127.0.0.1)입니다. 프록시도 이 주소로 걸고 푸는 걸 미리 확인해 둡니다. 지금은 리스너가 없으니 설정만 넣었다 빼 봅니다.

```console
$ adb shell settings put global http_proxy 10.0.2.2:8080
$ adb shell settings get global http_proxy
10.0.2.2:8080
$ adb shell settings delete global http_proxy
Deleted 1 rows
$ adb shell settings get global http_proxy
null
```

### 6. 스냅샷 저장

여기까지가 깨끗한 기준 상태입니다. 스냅샷으로 박아 둡니다.

```console
$ adb emu avd snapshot save clean-boot
OK
$ adb emu avd snapshot list
List of snapshots present on all disks:
--        clean-boot             195M ...   00:02:37
```

---

## 스크린샷

부팅이 끝난 홈 화면입니다. Pixel 런처와 Android 13 기본 앱이 떠 있습니다.

![aas-api33 부팅 완료 홈 화면 — Pixel 런처, Gmail/Photos/YouTube, 하단 독의 전화·메시지·Chrome, Google 검색 바](/assets/img/android-app-security/S01/01-home.png)

설정의 기기 정보 화면입니다. 화면 제목이 "About emulated device"라고 대놓고 에뮬레이터임을 밝히고, 기기 이름과 모델이 `sdk_gphone64_x86_64`로 나옵니다. 앞의 `getprop` 값과 화면이 서로 맞는지 눈으로 한 번 더 맞춰 봤습니다.

![설정 > 기기 정보 화면 — 제목 "About emulated device", Device name/Model 모두 sdk_gphone64_x86_64, SIM status T-Mobile, IMEI 표시](/assets/img/android-app-security/S01/02-about.png)

원시 출력(getprop 덤프, 도구 버전, 네트워크, 스냅샷 목록)은 `assets/evidence/android-app-security/S01/`에 텍스트로 따로 남겼습니다.

---

## 관측 결과

- 실습 대상은 API 33 / Android 13 / x86_64 / `userdebug` 빌드의 `aas-api33` 하나로 고정됐습니다.
- SELinux는 Enforcing인 채로 `adb root`(uid 0)가 됩니다. 저장소·프로세스를 직접 열어 볼 수 있는 분석 환경이 갖춰졌다는 뜻입니다.
- 호스트 루프백은 `10.0.2.2`, 프록시 설정/해제가 정상 동작합니다. 네트워크 편의 준비가 됐습니다.
- 깨끗한 상태가 `clean-boot` 스냅샷으로 박혀 있어, 언제든 같은 지점으로 돌아올 수 있습니다.

---

## 재검증 — 초기화하면 같은 상태로 돌아오는가

환경이 "재현 가능"하다는 말은 망가뜨려도 원상 복구된다는 뜻입니다. 두 가지 초기화 경로를 준비해 둡니다.

- 가벼운 복구: 저장해 둔 스냅샷으로 되돌립니다.

```bash
adb emu avd snapshot load clean-boot
```

- 완전 초기화: 사용자 데이터를 통째로 지우고 공장 상태로 콜드 부팅합니다.

```bash
emulator -avd aas-api33 -wipe-data -no-snapshot-load
```

`-wipe-data`로 다시 올린 뒤 `getprop`으로 API·ABI·빌드 타입이 그대로인지 확인하면, 매 실습을 같은 기준선에서 시작할 수 있습니다.

---

## 참고 자료

- Android Developers — Create and manage virtual devices (`avdmanager`, `emulator`)
- Android Developers — `adb` 명령 레퍼런스
- Android Emulator Networking (호스트 루프백 `10.0.2.2`)

