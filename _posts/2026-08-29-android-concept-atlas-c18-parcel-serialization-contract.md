---
layout: post
title: "Android Security Concept Atlas C18 | 가상 실습 보고서 — Parcel 직렬화 계약이 어긋날 때"
date: 2026-08-29 23:13:00 +0900
category: 안드로이드
author: SeiKa
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-10-14
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C18, Binder, Parcel, Serialization, AIDL, Bundle, TypeConfusion, CVE-2017-13288, CVE-2021-0394]
excerpt: "writeInt·writeString이 남기는 바이트에는 타입 표시가 없어서 같은 20바이트를 순서와 타입을 바꿔 읽으면 예외 없이 null과 밀린 값이 나왔습니다. 비대칭 Parcelable은 Android 8.0 Bundle에서 다음 키를 지웠지만 Android 13에서는 길이 접두사 때문에 그 항목을 넘지 못했고, 순서가 바뀐 AIDL 인자는 --min_sdk_version=33으로 생성한 Stub만 거부했습니다."
---

> 가상 환경 전용: 이 글의 실습은 Android Emulator(Android 13/API 33, 비교용 Android 8.0/API 26)와 직접 만든 실습 앱 안에서만 했습니다. 실물 기기, 루팅, 부트로더 잠금 해제, 플래싱, 다른 사람의 앱이나 시스템은 쓰지 않았고, 플랫폼 서비스에 조작한 Parcel이나 Bundle을 보내지도 않았습니다.

> Concept Atlas 모듈: C18 · Tier 3 IPC·프레임워크 · 선수 개념: [C17 Binder 드라이버](/posts/android-concept-atlas-c17-binder-driver/)

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-10-14 |
| 대상 | `codex-atlas-api33` AVD(Android 13/API 33, 보안 패치 2024-03-01, x86_64 userdebug), 비교용 `sec-26-r08` AVD(Android 8.0/API 26, 보안 패치 2017-11-05), 직접 만든 앱 io.seika.parcellab과 io.seika.parcelsvc |
| 실행 명령·코드 | Atlas Evidence 앱은 `--es section parcel`, ParcelLab은 `am start -S -W`에 `--es exp`로 wire, token, mismatch, bundle, par, typed, ipc를 주고 `logcat -d -s C18:I -v raw`로 결과를 모았습니다. |
| 관측 결과 | int와 String 20바이트는 같은 순서로 읽으면 복원되고 다른 순서로 읽으면 예외 없이 null과 밀린 값이 나왔습니다. Bundle 안의 비대칭 Parcelable은 API 26에서 다음 키를 지웠고 API 33에서는 길이 접두사 때문에 그 항목 안에 갇혔습니다. 순서가 바뀐 AIDL 인자를 legacy Stub은 그대로 실행했고 strict Stub은 남는 바이트로 거부했습니다. |
| 검증 한계 | 메모리 손상은 관측하지 않았습니다. 특권 프로세스를 거치는 공격용 Bundle은 만들지 않았습니다. API 33의 PeriodicAdvertisingReport 대칭과 libbinder 헤더 불일치 거부는 소스로만 확인했고 C++/NDK Parcel 소비자, Binder 객체나 fd가 든 Parcel, API 34 이상 이미지는 재지 않았습니다. |

![Atlas Evidence 앱의 ATLAS / PARCEL 화면, API 33 Android Emulator, 2026-08-28 16:50:55 표시. Parcel symmetric read/write and mismatch control 아래 dataSize=20, roundTrip.int=0x11223344, roundTrip.string=atlas, mismatch.unexpected-value=null, result=PASS, 하단에 VERIFIED IN RUNNING APP PROCESS](/assets/img/android-concept-atlas/verified-api33/evidence-parcel.png)

위 화면은 저장소의 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 2026-08-28에 찍은 것입니다. 2026-10-14에 같은 AVD를 깨끗하게 다시 부팅하고 `adb -s emulator-5600 shell am start -S -W -n com.example.atlasreport/.MainActivity --es section parcel`로 다시 돌렸을 때도 dataSize=20, 0x11223344, atlas, mismatch null이 똑같이 나왔습니다. 본문의 나머지 출력과 그림은 모두 2026-10-14에 얻었습니다. 앱 출력은 직접 만든 ParcelLab·ParcelSvc 앱에서 나왔습니다. aidl 생성 결과와 CVE 수정 커밋 diff는 같은 터미널에서 함께 찍었습니다. wire, token, mismatch, bundle, par, typed는 API 33과 API 26에서 두 번씩(API 26의 typed는 해당 메서드가 없다는 줄만 찍습니다), ipc는 API 33에서만 세 번 돌렸고 출력은 매번 한 글자도 다르지 않았습니다.
<!-- atlas-verification:end -->

[C17](/posts/android-concept-atlas-c17-binder-driver/)에서 본 Binder 드라이버는 트랜잭션 버퍼를 한 번 복사하고 호출자 UID를 붙여 줍니다. 버퍼 안에서 드라이버가 번역하는 것은 오프셋 배열이 가리키는 Binder 객체와 fd 항목(`flat_binder_object`)입니다. 나머지 바이트에 무엇을 어떤 순서로 넣고 꺼낼지는 `android.os.Parcel`을 쓰는 양쪽 코드가 정합니다. 보내는 쪽이 `writeInt`, `writeString`을 차례로 부르면 바이트가 쌓이고 받는 쪽은 같은 순서로 `readInt`, `readString`을 불러 값을 되찾습니다. 아래 실험은 Binder 객체 없이 값만 담은 Parcel을 다룹니다. `marshall()`은 Binder 객체가 든 Parcel을 바이트로 꺼내 주지 않아서 객체 항목의 형식은 여기서 재지 않았습니다.

[Parcel 레퍼런스](https://developer.android.com/reference/android/os/Parcel)는 Parcel을 범용 직렬화 수단으로 쓰지 말고 영구 저장소에도 넣지 말라고 적어 두었습니다. 구현이 바뀌면 예전 바이트를 읽지 못하게 될 수 있어서입니다. 실제로 인터페이스 토큰만 해도 Android 8.0과 13의 바이트 구성이 다릅니다.

저는 쓰는 쪽과 읽는 쪽의 순서나 타입이 어긋나면 받는 쪽에서 예외가 날 줄 알았습니다. Android 13과 8.0 에뮬레이터에서 돌려 보니 예외가 난 경우는 드물었고 대부분은 그럴듯한 값이나 null이 나와 조용히 다음 코드로 넘어갔습니다. Android 13에는 받는 쪽 검사가 몇 가지 더 있었습니다. 그중 AIDL 인자 검사는 Stub을 생성할 때 준 옵션에 따라 들어가기도 하고 빠지기도 했습니다.

## 실험 앱 ParcelLab

실험에는 직접 만든 앱 두 개를 썼습니다. `io.seika.parcellab`(uid 10179)는 자기 프로세스 안에서 Parcel을 쓰고 읽는 실험을 돌리고 IPC 클라이언트 역할도 합니다. `io.seika.parcelsvc`(uid 10180)는 같은 `.aidl`에서 생성한 Stub 서비스 두 개를 노출합니다. 둘 다 Gradle 없이 javac, d8, aapt, apksigner로 묶었고 minSdk 26, targetSdk 33입니다. 서비스는 실습용이라 권한 없이 exported로 열어 두었습니다. 클라이언트 매니페스트에는 targetSdk 33의 패키지 가시성 때문에 `<queries>`로 서비스 패키지를 적었습니다.

앱은 결과를 `C18` 태그로 logcat에 남기고 같은 줄을 화면에도 찍습니다. 실험마다 `exp` 값만 바꿔 같은 명령을 씁니다.

```bash
adb -s emulator-5600 logcat -c
adb -s emulator-5600 shell am start -S -W -n io.seika.parcellab/.MainActivity --es exp mismatch > /dev/null
sleep 2
adb -s emulator-5600 logcat -d -s C18:I -v raw
```

`exp` 자리에는 wire, token, mismatch, bundle, par, typed, ipc가 들어갑니다. emulator-5600은 Android 13 이미지(보안 패치 2024-03-01)입니다. Android 8.0 비교는 같은 APK를 emulator-5620의 `sec-26-r08` 이미지(보안 패치 2017-11-05)에 설치해 돌렸습니다. API 26 이미지에서는 3초쯤 기다렸습니다. ipc는 서비스에 bind한 뒤 백그라운드 스레드에서 결과를 찍으므로 5초쯤 기다린 뒤 logcat을 읽었습니다. IPC 실험을 빼면 모두 앱 자기 프로세스 안에서 Parcel 하나를 다루는 실험입니다.

## writeInt·writeString이 쓴 바이트

`wire` 실험은 값을 하나 쓸 때마다 `dataSize()`를 찍고 끝에 `marshall()`로 꺼낸 바이트를 16바이트씩, 4바이트마다 띄어 덤프합니다. `wire()`에서 로그 출력 줄을 걷어 내면 이렇습니다.

```java
Parcel p = Parcel.obtain();
p.writeInt(0x11223344);
p.writeString("atlas");
p.writeLong(0x0102030405060708L);
if (Build.VERSION.SDK_INT >= 29) p.writeBoolean(true); else p.writeInt(1);
p.writeString(null);
p.writeByteArray(new byte[]{1, 2, 3});
dump(p.marshall());
p.recycle();
```

`writeBoolean`이 API 29에 생긴 메서드라서 API 26에서는 같은 자리에 `writeInt(1)`을 씁니다.

![API 33 에뮬레이터 터미널에서 exp wire 실행. writeInt(0x11223344), writeString("atlas"), writeLong(0x0102030405060708), writeBoolean(true), writeString(null), writeByteArray({1,2,3}) 뒤 dataSize가 4, 20, 28, 32, 36, 44로 늘고 헥스 덤프는 44 33 22 11 / 05 00 00 00 61 00 74 00으로 시작. 이어서 exp token 결과로 writeInterfaceToken("io.seika.echo.IEcho")가 API 33에서 dataSize=56(04 00 00 c2, ff ff ff ff, 54 53 59 53, strictModePolicy=0xc2000004 workSource=-1 header=0x53595354('SYST')), API 26에서 dataSize=48(04 00 40 01 뒤 바로 디스크립터, strictModePolicy=0x01400004)](/assets/img/android-concept-atlas/atlas-c18/01-wire-token-hexdump.png)

`0x11223344`는 `44 33 22 11`로, long은 `08 07 06 05 04 03 02 01`로 들어가 있습니다. 둘 다 리틀엔디언입니다. 문자열은 글자 수를 int로 먼저 쓰고(`05 00 00 00`) 글자를 UTF-16LE로 쓴 다음 NUL 한 글자(`00 00`)를 붙여 4바이트 경계까지 채웁니다. "atlas"는 4 + (5+1)×2 = 16바이트라서 앞의 int와 합쳐 20바이트가 됩니다. boolean은 int 한 칸(`01 00 00 00`), null 문자열은 길이 -1(`ff ff ff ff`) 한 칸입니다. byte[]는 길이 int 뒤에 바이트를 넣고 `01 02 03 00`처럼 패딩합니다. Android 8.0 이미지에서도 이 덤프는 바이트 단위로 같았습니다.

덤프 어디에도 "여기부터 String"이라는 표시는 없습니다. 같은 4바이트가 int로도, 문자열 길이로도, long의 아래 절반으로도 읽힐 수 있습니다. 어느 쪽으로 읽힐지는 받는 쪽이 부르는 메서드 순서로만 정해집니다. 타입 코드(VAL_*)와 클래스 이름은 `writeValue`나 Bundle처럼 쓰는 쪽이 따로 적을 때만 들어갑니다. 뒤의 Bundle 덤프가 그런 경우입니다.

### 인터페이스 토큰 헤더

AIDL이 생성한 Proxy는 인자보다 먼저 `writeInterfaceToken(DESCRIPTOR)`를 씁니다. 같은 그림 아래쪽이 이 토큰만 쓴 `token` 실험입니다. Android 13에서는 StrictMode 정책 int(0xc2000004), WorkSource uid int(-1은 설정되지 않았다는 뜻), 헤더 `'SYST'`(메모리에는 `54 53 59 53`), 디스크립터 문자열 순서로 56바이트가 쌓였습니다. Android 8.0은 정책 int(0x01400004) 바로 뒤에 디스크립터가 와서 48바이트입니다.

네이티브 [`Parcel::writeInterfaceToken`](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp#688)이 이 순서로 씁니다. 태그별 `Parcel.cpp` 원문을 내려받아 비교해 보니 WorkSource 칸은 android-10.0.0_r1에서, 헤더 칸은 android-11.0.0_r1에서 처음 나타납니다. 정책 값의 최상위 비트가 다른 것은 `STRICT_MODE_PENALTY_GATHER` 정의가 바뀌어서입니다. android-8.0.0_r1에서는 `(0x40 << 16)`, android-13.0.0_r1에서는 [`(1 << 31)`](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp#76)이라 관측값과 맞습니다.

헤더 값은 빌드 종류에 따라 갈립니다. [674~680행](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp#674)을 보면 VNDK로 빌드한 libbinder는 `'VNDR'`, recovery는 `'RECO'`, 나머지는 `'SYST'`를 씁니다. 받는 쪽 [`Parcel::enforceInterface`](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp#739)는 헤더가 다르면 "Mixing copies of libbinder?" 로그를 남기고 거부합니다. 이 거부 경로는 소스로만 확인했습니다. 디스크립터 문자열이 다를 때 거부되는 모습은 뒤의 IPC 실험에서 실제로 나옵니다.

## 같은 20바이트를 다른 순서로 읽으면

`mismatch` 실험은 `writeInt(0x11223344)`와 `writeString("atlas")`로 만든 20바이트를 `base()`로 매번 새로 만들어 서로 다른 방식으로 읽고, 읽은 직후의 `dataPosition()`을 `@` 뒤에 붙여 찍습니다. 아래는 `mismatch()`에서 String부터 읽는 경우, 끝을 넘겨 읽는 경우, NUL 없는 문자열을 읽는 경우만 뽑았습니다.

```java
p = base();
s = p.readString(); a = p.dataPosition(); i = p.readInt(); int b2 = p.dataPosition();
String s2 = p.readString();

p = base();
p.setDataPosition(p.dataSize());
i = p.readInt(); a = p.dataPosition(); s = p.readString(); b2 = p.dataPosition(); l = p.readLong();

p = Parcel.obtain();               // length 2, but no NUL terminator after 2 chars
p.writeInt(2); p.writeInt(0x00420041); p.writeInt(0x00440043);
p.setDataPosition(0);
s = p.readString();
```

![ParcelLab 앱 화면(API 33, patch 2024-03-01). writeInt(0x11223344)+writeString("atlas")로 만든 dataSize=20 버퍼와 헥스 44 33 22 11 05 00 00 00 61 00 74 00 6c 00 61 00 73 00 00 00. int,String은 0x11223344 @4와 "atlas" @20, String,int,String은 null @4, 5 @8, null @12, int,int는 0x11223344와 5 @8, long은 0x0000000511223344 @8, boolean은 true @4, 끝 너머 읽기는 int=0 @20, String=null @20, long=0 @20, avail=0, NUL 없는 len=2 "AB"는 null @12, 마지막 줄은 no exception thrown](/assets/img/android-concept-atlas/atlas-c18/02-mismatch-screen-api33.png)

`[1]`은 계약대로 읽은 결과입니다. `[2]`에서 String부터 읽으면 0x11223344를 글자 수로 받아들입니다. 남은 바이트보다 훨씬 큰 값이라 null이 나옵니다. 그런데 위치는 이미 4로 옮겨 가 있습니다. 이어지는 `readInt`는 진짜 문자열의 글자 수 5를 받고 다음 `readString`은 'a'와 't' 두 글자(0x00740061)를 다시 글자 수로 읽어 null을 내며 위치 12에 멈춥니다.

나머지도 비슷합니다. `[3]`의 두 번째 int는 문자열 길이 5입니다. `[4]`에서는 int와 문자열 길이가 long 하나로 합쳐져 0x0000000511223344가 됐고 `[5]`에서는 0x11223344가 boolean true로 읽혔습니다. 끝을 넘겨 읽은 `[6]`은 int 0, String null, long 0을 주고 위치는 20에서 움직이지 않았습니다. 화면 마지막 줄처럼 어느 경우에도 예외는 나지 않았습니다. Android 8.0에서도 `[7]`을 뺀 결과는 같았습니다. `[7]`은 아래 네이티브 코드와 함께 봅니다.

Java [`readString()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#3065)은 `readString16()`을 거쳐 JNI로 내려갑니다. 실제로 문자열을 꺼내는 곳은 아래 네이티브 함수입니다.

```cpp
// frameworks/native libs/binder/Parcel.cpp, android-13.0.0_r1, 1885~1901행
const char16_t* Parcel::readString16Inplace(size_t* outLen) const
{
    int32_t size = readInt32();
    // watch for potential int overflow from size+1
    if (size >= 0 && size < INT32_MAX) {
        *outLen = size;
        const char16_t* str = (const char16_t*)readInplace((size+1)*sizeof(char16_t));
        if (str != nullptr) {
            if (str[size] == u'\0') {
                return str;
            }
            android_errorWriteLog(0x534e4554, "172655291");
        }
    }
    *outLen = 0;
    return nullptr;
}
```

길이를 `readInt32()`로 먼저 읽으니 위치는 그 자리에서 4 전진합니다. 이어지는 [`readInplace`](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp#1533)는 요청한 크기가 남은 데이터를 넘으면 위치를 건드리지 않고 nullptr를 돌려줍니다. `[2]`의 "null @4"가 이렇게 나옵니다. 고정 크기 값을 읽는 [`readAligned`](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp#1584)도 데이터가 모자라면 `NOT_ENOUGH_DATA`를 내고 결과를 0으로 채웁니다. `[6]`의 0이 그 결과입니다.

`[7]`은 길이를 2로 적고 세 번째 UTF-16 칸에 NUL 대신 'C'를 둔 문자열입니다. 두 이미지에서 이것만 골라 보면 Android 8.0은 "AB"로 받아들였고 Android 13은 null로 거부했습니다. Android 13 쪽 events 로그에는 SafetyNet 이벤트가 남았습니다.

![터미널에서 exp mismatch를 두 이미지에 실행하고 7번 케이스 줄만 grep. API 26(emulator-5620, patch 2017-11-05)은 len=2 "AB" w/o NUL -> "AB" @12, API 33(emulator-5600, patch 2024-03-01)은 len=2 "AB" w/o NUL -> null @12, 둘 다 no exception thrown. 이어서 events 버퍼를 grep 172655291로 거른 결과 snet_event_log 172655291,-1](/assets/img/android-concept-atlas/atlas-c18/07-nul-terminator-api26-vs-33.png)

```bash
adb -s emulator-5600 logcat -b events -d | grep 172655291
```

위 `readString16Inplace`의 `str[size] == u'\0'` 검사와 `android_errorWriteLog(0x534e4554, "172655291")`가 이 결과를 만듭니다. 이 검사는 2021년 3월 [보안 게시판](https://source.android.com/docs/security/bulletin/2021-03-01)에 실린 CVE-2021-0394(A-172655291, 정보 노출 High, 영향 버전 8.1·9·10·11)의 수정입니다. frameworks/native 커밋 [58f5cfa](https://android.googlesource.com/platform/frameworks/native/+/58f5cfa56d5282e69a7580dc4bb97603c409f003)가 NUL 검사를 넣었고 [61d0f84](https://android.googlesource.com/platform/frameworks/native/+/61d0f84881cfc1bbac513ccd156c56603a48cc90)가 SafetyNet 로그를 더했습니다. 두 번째 커밋이 적은 테스트 방법도 events 로그에서 snet을 grep하는 것이었습니다. 태그 원문으로 보면 android-11.0.0_r1 Parcel.cpp에는 172655291이 없고 android-12.0.0_r1에는 있습니다. 2017-11 패치의 Android 8.0 이미지는 수정 전입니다.

이런 경계 검사 덕분에 이번 실험에서 Parcel 버퍼 밖을 읽는 일은 없었고 메모리 손상도 보지 못했습니다. 길이 필드를 믿고 직접 복사하는 네이티브 소비자라면 결과가 다를 수 있습니다. 다만 C++ AIDL이나 HIDL 쪽 소비자는 이번에 재지 않았습니다.

## writeLong으로 쓰고 readInt로 읽은 PeriodicAdvertisingReport

받는 쪽이 일부러 틀리게 읽을 일은 드뭅니다. 실제 버그는 한 클래스의 `writeToParcel`과 `createFromParcel`이 서로 다른 모양을 가질 때 생깁니다. 2018년 4월 [Android 보안 게시판](https://source.android.com/docs/security/bulletin/2018-04-01)에는 프레임워크 Parcelable의 쓰기·읽기 비대칭 수정이 여러 건 함께 실렸고 모두 권한 상승(EoP) High로 분류됐습니다.

| CVE | 클래스 | 어긋난 곳 | 수정 커밋 |
|---|---|---|---|
| CVE-2017-13286 | OutputConfiguration | 읽는 쪽이 mIsShared를 읽지 않음 | [47ebfaa](https://android.googlesource.com/platform/frameworks/base/+/47ebfaa2196aaf4fbeeec34f1a1c5be415cf041b) |
| CVE-2017-13287 | VerifyCredentialResponse | payload가 null이면 쓰는 쪽이 길이 칸을 쓰지 않음 | [09ba8fd](https://android.googlesource.com/platform/frameworks/base/+/09ba8fdffd9c8d74fdc6bfb51bcebc27fc43884a) |
| CVE-2017-13288 | PeriodicAdvertisingReport | txPower를 long으로 쓰고 int로 읽음 | [b796cd3](https://android.googlesource.com/platform/frameworks/base/+/b796cd32a45bcc0763c50cc1a0cc8236153dcea3) |
| CVE-2017-13289 | ParcelableRttResults | LCR 길이를 int로 쓰고 데이터 대신 id 바이트를 씀 | [5a3d270](https://android.googlesource.com/platform/frameworks/base/+/5a3d2708cd2289a4882927c0e2cb0d3c21a99c02) |

CVE-2017-13287 커밋 메시지는 이 비대칭이 "could lead to type confusion if packed with other objects in a Parcel"이라고 적습니다.

이 가운데 CVE-2017-13288을 패치 전 이미지에서 돌려 봤습니다. Android 8.0 이미지의 보안 패치는 2017-11-05라 2018년 4월 수정이 들어 있지 않습니다. [android-8.0.0_r1 원문](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/bluetooth/le/PeriodicAdvertisingReport.java#72)을 보면 `writeToParcel`은 74행에서 `dest.writeLong(txPower)`를, `readFromParcel`은 87행에서 `txPower = in.readInt()`를 합니다. 클래스가 `@hide`라 SDK의 android.jar로 컴파일하면 클래스를 찾지 못했습니다. 그래서 생성자와 `CREATOR`를 리플렉션으로 꺼내는 쪽으로 바꿨습니다(출력 줄은 생략).

```java
final int MARK = 0x4D41524B;   // 'MARK'
Class<?> c = Class.forName("android.bluetooth.le.PeriodicAdvertisingReport");
Parcelable r = (Parcelable) c.getConstructor(int.class, int.class, int.class, int.class,
        android.bluetooth.le.ScanRecord.class).newInstance(1, -20, -60, 0, null);
Parcelable.Creator<Parcelable> creator = (Parcelable.Creator<Parcelable>) c.getField("CREATOR").get(null);
Parcel p = Parcel.obtain();
r.writeToParcel(p, 0);
int written = p.dataPosition();
p.writeInt(MARK);
p.setDataPosition(0);
Object back = creator.createFromParcel(p);
int consumed = p.dataPosition();
int next = p.readInt();
```

![터미널에서 CVE-2017-13288 수정 diff를 grep한 결과 PeriodicAdvertisingReport.java의 -dest.writeLong(txPower)와 +dest.writeInt(txPower). 이어서 API 26(patch 2017-11-05)에서 exp par 실행: PeriodicAdvertisingReport(1, txPower=-20, rssi=-60, 0, null) 헥스 01 00 00 00 ec ff ff ff ff ff ff ff c4 ff ff ff 00 00 00 00 00 00 00 00 4b 52 41 4d, written=24 consumed=20 next int=0x00000000 (expect 0x4d41524b) ASYMMETRIC, read back txPower=-20 rssi=-1 dataStatus=-60. API 33에서는 FAILED java.lang.NoSuchMethodException과 Accessing hidden method ... (max-target-o, reflection, denied)](/assets/img/android-concept-atlas/atlas-c18/06-cve-2017-13288-asymmetry-api26.png)

Android 8.0에서는 24바이트를 쓰고 20바이트만 읽었습니다. txPower -20을 long으로 쓰면 아래 4바이트 `ec ff ff ff` 뒤에 위 4바이트 `ff ff ff ff`가 낍니다. 읽는 쪽은 이 위 절반을 rssi로 받아 -1을 만들고 진짜 rssi -60은 dataStatus로 받습니다. `createFromParcel`이 멈춘 위치 20에서 다음 int를 읽으니 MARK(0x4d41524b) 대신 아직 읽히지 않은 data 유무 플래그 0이 나왔습니다. MARK는 그보다 4바이트 뒤인 24에 그대로 남아 있습니다.

Android 13 쪽은 런타임으로 재지 못했습니다. 같은 리플렉션이 hidden API 정책(max-target-o)에 막혀 `NoSuchMethodException`이 났고 logcat에는 "reflection, denied"가 남았습니다. 그래서 대칭 여부는 소스로만 확인했습니다. Android 13에서 이 클래스는 Bluetooth 모듈로 옮겨졌습니다. [android-13.0.0_r1 원문](https://android.googlesource.com/platform/packages/modules/Bluetooth/+/refs/tags/android-13.0.0_r1/framework/java/android/bluetooth/le/PeriodicAdvertisingReport.java#72)을 보면 74행 쓰기와 87행 읽기가 모두 int입니다. hidden API 정책은 앱이 이 클래스를 직접 부르는 길을 막습니다. 시스템 프로세스가 Parcel을 풀 때 생기는 비대칭까지 막는다는 근거는 찾지 못했습니다.

WorkSource의 CVE-2023-20963도 쓸 때와 읽을 때 길이가 다른 같은 모양의 버그입니다. 그쪽은 [CVE 재현 9편](/posts/android-cve-09-parcel-mismatch/)에서 패치 전후 이미지로 따로 쟀습니다. 이번에는 그 패치 전 이미지를 쓸 수 없어 다시 돌리지 않았습니다.

## Bundle에 넣은 비대칭 Parcelable

CVE-2017-13287 커밋 메시지가 말한 '다른 객체와 함께 담긴' 경우를 Bundle로 보려고 일부러 계약을 깬 Parcelable을 만들었습니다.

```java
// Asym.java (package와 import 생략)
public class Asym implements Parcelable {
    int a, b;

    public Asym(int a, int b) { this.a = a; this.b = b; }

    @Override public void writeToParcel(Parcel dest, int flags) {
        dest.writeInt(a);
        dest.writeInt(b);
    }

    @Override public int describeContents() { return 0; }

    public static final Creator<Asym> CREATOR = new Creator<Asym>() {
        @Override public Asym createFromParcel(Parcel in) {
            return new Asym(in.readInt(), 0);   // b is never read
        }
        @Override public Asym[] newArray(int n) { return new Asym[n]; }
    };

    @Override public String toString() {
        return String.format("Asym{a=0x%x,b=0x%x}", a, b);
    }
}
```

`bundle` 실험은 n=7, bad=Asym(0x41414141, 0x42424242), next="hello"를 담은 Bundle을 `writeBundle`로 쓰고 `readBundle`로 다시 읽은 다음 `getInt("n")`, `getString("next")`, `keySet()`, `getParcelable("bad")`를 차례로 부릅니다. 처음에는 넣은 순서대로 쓰일 줄 알았습니다. 그런데 Bundle 안의 ArrayMap은 키 해시 순으로 씁니다. "bad"의 해시가 97285라 실제 순서는 n, bad, next였고 덕분에 `next`가 비대칭 항목 바로 뒤에 놓였습니다. `keySet()`을 바로 문자열로 찍으면 `MapCollections$KeySet@…` 같은 객체 이름만 나와서 ArrayList로 감싸 찍었습니다.

![같은 APK의 exp bundle 결과. API 26(emulator-5620)은 written keys n, bad, next, bad 키 뒤 04 00 00 00 바로 다음에 클래스명 길이 17 00 00 00, getInt(n)=7 getString(next)=null, keys=null, n, bad, re-write bytes=112 identical=false, ArrayMap 경고 New hash 0 is before end of array hash 97285 at index 2 key null. API 33(emulator-5600)은 04 00 00 00 뒤에 길이 3c 00 00 00이 먼저 오고, getString(next)="hello", keys=n, bad, next, re-write without touching bad bytes=144 identical=true, Parcel 로그 Unparcelling of Asym{a=0x41414141,b=0x0} of type VAL_PARCELABLE consumed 56 bytes, but 60 expected](/assets/img/android-concept-atlas/atlas-c18/03-bundle-lengthprefix-26-vs-33.png)

### Android 8.0에서는 다음 키가 사라졌다

Android 8.0의 덤프에서 VAL_PARCELABLE 타입 코드(`04 00 00 00`) 바로 뒤에는 클래스 이름의 글자 수(`17 00 00 00`, 23)가 옵니다. 항목 길이를 따로 적는 칸이 없습니다. [android-8.0.0_r1의 `writeValue`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/os/Parcel.java#1631)는 타입 코드를 쓰고 곧바로 `writeParcelable`을 부르기 때문입니다. Asym이 4바이트만 읽고 멈추면 다음 키 이름을 읽어야 할 자리에 0x42424242가 남고 거기서부터 해석이 밀립니다.

결과는 그림 위쪽 그대로입니다. `getString("next")`는 null이었고 키 목록에서 `next`가 사라지고 null 키가 생겼습니다(`keys=[null, n, bad]`). 예외는 없었고 로그에 남은 것은 Bundle을 풀 때마다 찍힌 ArrayMap의 "New hash 0 ... key null" 경고뿐이었습니다. 첫 경고의 스택은 `getInt("n")`에서 출발해 [`BaseBundle.unparcel()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/os/BaseBundle.java#257)이 [`readArrayMapInternal`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/os/Parcel.java#3031)로 Bundle 전체를 한 번에 푸는 경로를 가리킵니다. 0x42424242를 키 길이로 읽어 null 키가 되고 "next"의 글자 수 4를 타입 코드 VAL_PARCELABLE로 읽어 클래스 이름 읽기에 실패하는 식으로 밀렸을 것으로 보입니다. 다만 이 세부 경로는 소스를 따라간 추론이고 null 키에 붙은 값은 출력해 보지 않았습니다.

Android 8.0에서 140바이트였던 Bundle을 읽고 그대로 다시 쓰자 112바이트가 나왔고 바이트도 원본과 달랐습니다. 한 프로세스가 Bundle을 풀어 검사한 뒤 다시 직렬화해 다른 프로세스로 넘기는 경로라면 검사한 내용과 받는 쪽이 읽는 내용이 달라질 수 있습니다. 이번에 확인한 것은 무해한 형태의 내용 변화까지입니다. 특권 프로세스를 거치게 만드는 공격용 Bundle은 만들지 않았습니다.

### Android 13에서는 다음 키가 온전했다

같은 APK가 Android 13에서는 다른 결과를 냈습니다. VAL_PARCELABLE 뒤에 길이 `3c 00 00 00`(60)이 먼저 붙고 그다음이 클래스 이름 글자 수 23입니다. Bundle 전체도 144바이트로, Android 8.0보다 많은 4바이트가 이 길이 칸 하나입니다. [`writeValue`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#2302)가 길이 자리에 -1을 써 두고 객체를 쓴 다음 되돌아가 실제 길이를 채웁니다.

읽을 때도 이 길이를 씁니다. [`BaseBundle`은 Bundle을 풀 때 `lazy`를 true로 넘기고](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/BaseBundle.java#441), [`readLazyValue`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#4351)는 길이만큼 건너뛰고 항목을 지연 값으로 남겨 둡니다. 그래서 `getString("next")`는 Asym을 건드리지 않은 채 "hello"를 온전히 읽었습니다. `bad`를 실제로 꺼내는 순간에는 아래 검사가 돌아갑니다.

```java
// frameworks/base core/java/android/os/Parcel.java, android-13.0.0_r1, 4305~4323행
private <T> T readValue(@Nullable ClassLoader loader, @Nullable Class<T> clazz,
        @Nullable Class<?>... itemTypes) {
    int type = readInt();
    final T object;
    if (isLengthPrefixed(type)) {
        int length = readInt();
        int start = dataPosition();
        object = readValue(type, loader, clazz, itemTypes);
        int actual = dataPosition() - start;
        if (actual != length) {
            Slog.wtfStack(TAG,
                    "Unparcelling of " + object + " of type " + Parcel.valueTypeToString(type)
                            + "  consumed " + actual + " bytes, but " + length + " expected.");
        }
    } else {
        object = readValue(type, loader, clazz, itemTypes);
    }
    return object;
}
```

Asym이 소비한 것은 클래스 이름 52바이트와 int 하나 4바이트를 더한 56바이트입니다. 길이 칸은 60바이트를 말하므로 그림 맨 아래의 "consumed 56 bytes, but 60 expected." 로그가 찍힙니다. `Slog.wtfStack`이라 앱이 죽지는 않았고 그 뒤 출력도 계속 나왔습니다. 다음 항목은 Asym이 몇 바이트를 읽었든 길이 칸이 가리키는 위치에서 시작하므로 `next`는 영향을 받지 않았습니다.

재직렬화 결과도 달랐습니다. `bad`를 건드리지 않은 Bundle은 지연 항목의 원래 바이트를 그대로 복사해 144바이트로, 원본과 똑같이 써졌습니다(`identical=true`). `bad`를 한 번 꺼낸 뒤 다시 쓰면 길이는 같지만 b가 0으로 바뀐 만큼 내용이 달라집니다.

태그 원문을 비교하면 `isLengthPrefixed`는 android-12.1.0_r1의 Parcel.java에는 없고 [android-13.0.0_r1](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#4670)에 처음 나옵니다. 대상 타입은 VAL_MAP, VAL_PARCELABLE, VAL_LIST, VAL_SPARSEARRAY, VAL_PARCELABLEARRAY, VAL_OBJECTARRAY, VAL_SERIALIZABLE입니다. 주석에는 Bundle 같은 클라이언트가 역직렬화 중에 내용을 건너뛸 수 있게 하려는 것이라고 적혀 있습니다. 그러니 한 항목의 불일치가 Bundle의 뒤 항목까지 밀어내는 것은 Android 12L까지이고 Android 13부터는 해당 항목 안으로 좁혀집니다. AIDL 인자처럼 평평하게 쓰인 Parcel이나 Parcelable 자신의 필드 안에서는 지금도 밀림이 일어납니다. main 브랜치(2026-10-14 기준)도 같은 `wtfStack`을 씁니다. API 34 이상 이미지에서 직접 재 보지는 않았습니다.

## 인자 순서를 바꾼 AIDL 호출

AIDL 인자가 그 평평한 경우입니다. AIDL 자체의 구조는 [C20](/posts/android-concept-atlas-c20-aidl-hidl-hal/)에서 다루고 여기서는 인자 배치가 어긋났을 때 생성된 Stub이 어떻게 반응하는지만 봤습니다. 인터페이스는 메서드 하나짜리입니다.

```java
// aidl/io/seika/echo/IEcho.aidl
package io.seika.echo;

interface IEcho {
    String describe(int id, String name, long ts);
}
```

같은 파일로 Stub을 두 번 생성했습니다. 한 번은 기본 옵션으로, 한 번은 `--min_sdk_version=33`을 줘서 만들었습니다. Windows의 SDK build-tools 36.0.0 `aidl.exe`는 `-I .`나 슬래시 경로를 주면 "directory ./ is not found in any of the import paths"로 실패해서 백슬래시 경로로 넘겼습니다.

```bash
aidl.exe --lang=java --omit_invocation -I 'aidl\' -o 'gen\legacy' 'aidl\io\seika\echo\IEcho.aidl'
aidl.exe --lang=java --omit_invocation --min_sdk_version=33 -I 'aidl\' -o 'gen\strict' 'aidl\io\seika\echo\IEcho.aidl'
diff gen/legacy/io/seika/echo/IEcho.java gen/strict/io/seika/echo/IEcho.java
```

diff에 나온 차이는 strict 쪽 Stub이 인자를 다 읽은 뒤 `data.enforceNoDataAvail()`을 부르는 줄과, Proxy가 `Parcel.obtain(asBinder())`로 Parcel을 얻는 줄이 전부입니다. strict Stub의 `onTransact`는 이렇게 생성됐습니다.

```java
// gen/strict/io/seika/echo/IEcho.java, Stub.onTransact 일부
java.lang.String descriptor = DESCRIPTOR;
if (code >= android.os.IBinder.FIRST_CALL_TRANSACTION && code <= android.os.IBinder.LAST_CALL_TRANSACTION) {
  data.enforceInterface(descriptor);
}
// (중략)
case TRANSACTION_describe:
{
  int _arg0;
  _arg0 = data.readInt();
  java.lang.String _arg1;
  _arg1 = data.readString();
  long _arg2;
  _arg2 = data.readLong();
  data.enforceNoDataAvail();
  java.lang.String _result = this.describe(_arg0, _arg1, _arg2);
  reply.writeNoException();
  reply.writeString(_result);
  break;
}
```

[`enforceNoDataAvail()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#927)은 API 33에 추가된 메서드로, 남은 바이트가 있으면 "Parcel data not fully consumed" 예외를 던집니다. android-12.1.0_r1 Parcel.java에는 이 메서드가 없습니다.

서비스 앱에는 legacy Stub을 그대로, strict Stub은 패키지 이름만 바꿔 넣었고 DESCRIPTOR 문자열은 둘 다 `io.seika.echo.IEcho`로 두었습니다. 각 서비스는 `onTransact`에서 받은 `dataSize`를 로그로 남기고 `describe()`는 읽은 값과 `Binder.getCallingUid()`를 문자열로 돌려줍니다. 클라이언트는 정상 호출 한 번을 생성된 Proxy로 보내고 나머지는 같은 transaction code에 인자를 손으로 써서 보냅니다.

```java
// MainActivity.java call() 일부
d.writeInterfaceToken(token);
w.write(d);
int size = d.dataSize();
b.transact(IBinder.FIRST_CALL_TRANSACTION, d, r, 0);
r.readException();

// runIpc() 일부, legacy와 strict 서비스에 차례로 보낸다
call(svc, b, "v2 match", DESC, d -> { d.writeInt(7); d.writeString("atlas"); d.writeLong(ts); });
call(svc, b, "v1 no ts", DESC, d -> { d.writeInt(7); d.writeString("atlas"); });
call(svc, b, "v3 +int", DESC, d -> { d.writeInt(7); d.writeString("atlas"); d.writeLong(ts); d.writeInt(0x99); });
call(svc, b, "swap str,int", DESC, d -> { d.writeString("atlas"); d.writeInt(7); d.writeLong(ts); });
call(svc, b, "wrong token", DESC + "V0", d -> { d.writeInt(7); d.writeString("atlas"); d.writeLong(ts); });
```

![터미널에서 cat aidl/io/seika/echo/IEcho.aidl로 String describe(int id, String name, long ts) 확인, aidl.exe를 기본 옵션과 --min_sdk_version=33으로 각각 실행, diff 결과 strict에만 data.enforceNoDataAvail()과 Parcel.obtain(asBinder()). exp ipc 결과 generated Proxy와 legacy v2 match는 id=7 name="atlas" ts=0x1122334455667788 callingUid=10179, legacy v1 no ts는 sent=76B ts=0x0, legacy v3 +int는 sent=88B로 정상, legacy swap str,int는 id=5 name=null ts=0x730061006c, strict v1 no ts는 ts=0x0, strict v3 +int는 BadParcelableException unread size 4, strict swap은 unread size 12, wrong token은 두 서비스 모두 SecurityException: Binder invocation to an incorrect interface, 마지막 줄은 Parcel 경고 enforceInterface() expected 'io.seika.echo.IEcho' but read 'io.seika.echo.IEchoV0'](/assets/img/android-concept-atlas/atlas-c18/05-aidl-stub-ipc-skew.png)

| 보낸 인자 | 크기 | legacy Stub | strict Stub |
|---|---|---|---|
| int, String, long | 84B | id=7 name="atlas" ts=0x1122334455667788 | 같음 |
| int, String (long 빠짐) | 76B | ts=0x0으로 describe() 실행 | ts=0x0으로 describe() 실행 |
| int, String, long, int | 88B | 남은 4바이트를 무시하고 실행 | BadParcelableException, unread size: 4 |
| String, int, long | 84B | id=5 name=null ts=0x730061006c로 실행 | BadParcelableException, unread size: 12 |
| 디스크립터 io.seika.echo.IEchoV0 | 88B | SecurityException | SecurityException |

크기는 토큰 56바이트에 int 4, "atlas" 16, long 8을 더한 값으로, 서비스 로그에 찍힌 `dataSize`와 같았습니다. 디스크립터가 두 글자 긴 IEchoV0 호출은 토큰이 60바이트라 88B입니다. 이 크기는 클라이언트 출력에 없어서 서비스 쪽 `onTransact` 로그에서 읽었습니다.

long이 빠진 호출은 두 Stub 모두 ts=0x0으로 `describe()`까지 실행했습니다. 끝을 넘긴 `readLong`이 0을 돌려주는 것은 앞의 `[6]`과 같은 동작입니다. `enforceNoDataAvail()`은 남은 바이트가 있는지만 확인하므로 읽을 것이 모자랐던 이 호출을 막지 못했습니다. int가 하나 더 붙은 호출을 legacy Stub은 꼬리 4바이트를 버린 채 정상 처리했고 strict Stub은 `describe()`에 들어가기 전에 거부했습니다.

순서를 바꾼 호출에서 legacy Stub은 문자열 길이 5를 id로, 'a'와 't'를 길이로 읽어 생긴 null을 name으로, 'l', 'a', 's'의 UTF-16 바이트를 ts(0x730061006c)로 받은 채 `describe()`를 실제로 실행했습니다. 서비스 로그에도 "legacy read id=5 name=null ts=0x730061006c"가 남았습니다. strict Stub은 남은 12바이트(int 4, long 8) 때문에 거부했고 서비스 로그에는 `onTransact` 줄 다음에 `strict read` 줄이 찍히지 않았습니다.

디스크립터를 `IEchoV0`으로 바꾼 호출은 두 Stub 모두에서 `enforceInterface`에 막혔습니다. 서비스 쪽 logcat에는 libbinder의 "enforceInterface() expected ... but read ..." 경고가 남았습니다. 예외를 던진 곳은 서비스 프로세스의 JNI [`android_os_Parcel_enforceInterface`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/jni/android_os_Parcel.cpp#721)입니다. 이 SecurityException이 reply에 실려 돌아왔고 클라이언트의 `readException()`이 "Binder invocation to an incorrect interface" 메시지 그대로 다시 던졌습니다.

성공한 호출마다 찍힌 `callingUid=10179`는 클라이언트 앱의 uid입니다. Parcel에 무엇을 쓰든 이 값은 커널 드라이버가 붙여 준 것이라 바뀌지 않았습니다. 권한 판정을 Parcel 안의 값이 아니라 이 값으로 해야 하는 이유입니다. 그 판정을 언제 어떻게 하는지는 [C22](/posts/android-concept-atlas-c22-binder-caller-identity-confused-deputy/)에서 다룹니다.

## 기대 타입을 넘기는 readParcelable

Parcelable을 읽을 때 받는 쪽은 Parcel에 적힌 클래스 이름으로 그 클래스의 `CREATOR`를 찾습니다. 이름은 보내는 쪽이 적습니다. `typed` 실험은 이 자리에 받는 쪽이 기대하지 않은 클래스 이름을 넣었을 때 무엇이 실행되는지 봤습니다. `Evil`은 static 초기화와 `createFromParcel`에서 카운터만 올리는 클래스입니다. 카운터는 별도 클래스 `Counters`에 둬서 카운터를 읽는 것만으로 `Evil`이 초기화되지 않게 했습니다.

```java
// Evil.java (package와 import 생략)
public class Evil implements Parcelable {
    static { Counters.evilClinit++; }
    @Override public void writeToParcel(Parcel dest, int flags) { dest.writeInt(0); }
    @Override public int describeContents() { return 0; }
    public static final Creator<Evil> CREATOR = new Creator<Evil>() {
        @Override public Evil createFromParcel(Parcel in) { Counters.evilCreate++; in.readInt(); return new Evil(); }
        @Override public Evil[] newArray(int n) { return new Evil[n]; }
    };
}
```

```java
// MainActivity.java typed() 일부
Parcel p = Parcel.obtain();
p.writeString(Evil.class.getName());   // class literal does not run Evil's static init
p.writeInt(0x1337);

p.setDataPosition(0);
try {
    Benign x = p.readParcelable(getClassLoader(), Benign.class);
    out("typed returned %s", x);
} catch (Throwable t) {
    out("typed  -> %s: %s", t.getClass().getName(), t.getMessage());
}

p.setDataPosition(0);
try {
    Benign x = p.readParcelable(getClassLoader());
    out("legacy returned %s", x);
} catch (Throwable t) {
    out("legacy -> %s: %s", t.getClass().getName(), t.getMessage());
}
```

![API 33 터미널에서 exp typed 실행. parcel에 Parcelable name=io.seika.parcellab.Evil + int, start clinit=0 create=0, 타입 지정 readParcelable은 android.os.BadTypeParcelableException: Parcelable creator io.seika.parcellab.Evil is not a subclass of required class io.seika.parcellab.Benign provided in the parameter, after typed clinit=0 create=0 pos=52, 예전 readParcelable은 java.lang.ClassCastException: io.seika.parcellab.Evil cannot be cast to io.seika.parcellab.Benign, after legacy clinit=1 create=1 pos=56, Bundle.getParcelable(k, Benign.class)는 null, create 1 -> 1](/assets/img/android-concept-atlas/atlas-c18/04-typed-readparcelable.png)

API 33에 추가된 타입 지정 메서드 `readParcelable(ClassLoader, Class)`는 클래스 이름 문자열(52바이트)만 읽고 `BadTypeParcelableException`을 던졌습니다. 카운터는 0과 0으로, `Evil`의 static 초기화도 `createFromParcel`도 돌지 않았습니다. 같은 바이트를 예전 메서드 `readParcelable(ClassLoader)`로 읽자 `Evil`을 초기화하고 `createFromParcel`까지 실행해 위치 56까지 읽은 뒤, 호출한 쪽에서 `Benign`에 대입하는 순간 ClassCastException이 났습니다. 받는 쪽 클래스로더에서 찾을 수 있는 Parcelable이라면 보내는 쪽은 이름만 적어서 그 클래스의 static 초기화와 `createFromParcel`을 돌릴 수 있습니다.

이 순서는 [`readParcelableCreatorInternal`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#4831)에 있습니다.

```java
// frameworks/base core/java/android/os/Parcel.java, android-13.0.0_r1, 4866~4878행
Class<?> parcelableClass = Class.forName(name, false /* initialize */,
        parcelableClassLoader);
if (!Parcelable.class.isAssignableFrom(parcelableClass)) {
    throw new BadParcelableException("Parcelable protocol requires subclassing "
            + "from Parcelable on class " + name);
}
if (clazz != null) {
    if (!clazz.isAssignableFrom(parcelableClass)) {
        throw new BadTypeParcelableException("Parcelable creator " + name + " is not "
                + "a subclass of required class " + clazz.getName()
                + " provided in the parameter");
    }
}
```

`Class.forName`에 initialize=false를 넘겨 클래스를 초기화하지 않은 채 타입부터 확인합니다. `CREATOR` 필드 값을 읽어 클래스가 초기화되는 [4893행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java#4893)은 그 뒤에 옵니다. 캐시된 creator를 쓰는 경로(4847~4855행)에도 같은 검사가 있습니다.

Bundle 수준의 `getParcelable(String, Class)`도 같은 검사를 거칩니다. 이쪽은 [`BaseBundle.get`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/BaseBundle.java#690)이 `BadTypeParcelableException`을 잡아 경고만 남기고 null을 돌려줍니다. 실험에서도 "Key k expected io.seika.parcellab.Benign but value was of a different type" 경고와 함께 null이 나왔고 create 카운터는 1에서 움직이지 않았습니다. 이 줄은 `Evil`이 이미 초기화된 뒤에 돌린 것이라 static 초기화 여부는 따로 보지 않았습니다. 두 타입 지정 메서드는 모두 API 33에 추가됐고 예전 메서드는 같은 버전에서 deprecated 됐습니다([Parcel](https://developer.android.com/reference/android/os/Parcel), [Bundle](https://developer.android.com/reference/android/os/Bundle) 레퍼런스).

## Parcel 코드를 짤 때 확인할 것

Parcelable을 직접 구현했다면 쓰기·읽기 왕복 테스트부터 둡니다. 앞의 `par()`처럼 `writeToParcel` 직후의 `dataPosition()`을 기록하고 뒤에 표식 int를 붙입니다. 그다음 처음으로 돌아가 `createFromParcel`이 소비한 위치와 그 뒤에 읽히는 표식을 비교합니다. 읽은 값만 비교하면 끝을 넘긴 읽기가 0을 돌려주는 경우(`[6]`)를 놓칠 수 있으니 위치와 표식을 함께 봐야 합니다. null 필드나 빈 배열처럼 쓰는 코드가 분기하는 입력도 따로 넣어야 합니다. CVE-2017-13287이 payload가 null일 때만 칸 하나를 빠뜨린 버그였습니다.

IPC 인자는 손으로 Parcel을 다루기보다 AIDL이 생성한 코드에 맡기고 Stub을 `--min_sdk_version` 33 이상으로 생성해 `enforceNoDataAvail()`을 넣습니다. 이렇게 생성한 Stub과 Proxy는 API 33에 추가된 `enforceNoDataAvail()`과 `Parcel.obtain(IBinder)`를 부르므로 minSdk가 33 이상인 모듈에만 맞습니다. minSdk 26인 이 실험 앱들처럼 그보다 낮은 모듈이라면 오래된 기기에서 이 메서드를 찾지 못해 실패할 것으로 보입니다. strict 서비스는 API 33 이미지에서만 돌려 봤습니다. 빌드 시스템이 이 값을 aidl에 어떻게 넘기는지는 확인하지 않았습니다. 생성된 `onTransact`를 열어 인자를 읽은 직후에 이 호출이 있는지 봅니다. `enforceNoDataAvail()`도 모자란 바이트는 잡지 못하므로 빠진 인자가 0이나 null로 들어오는 경우는 서비스 코드가 값 자체를 검증해야 합니다.

받는 쪽에서는 API 33부터 있는 `readParcelable(ClassLoader, Class)`와 `Bundle.getParcelable(String, Class)`처럼 기대 타입을 넘기는 메서드를 씁니다.

Android 13에서는 어긋난 Bundle 항목을 꺼낼 때 "Unparcelling of … consumed N bytes, but M expected" 로그가 남았습니다. 비대칭 Parcelable을 찾을 때는 logcat부터 걸러 봅니다.

```bash
adb -s emulator-5600 logcat -d | grep -m1 'Unparcelling of'
```

## 참고한 공식 소스

- [Parcel 레퍼런스](https://developer.android.com/reference/android/os/Parcel), [Bundle 레퍼런스](https://developer.android.com/reference/android/os/Bundle), [AIDL 가이드](https://developer.android.com/develop/background-work/services/aidl), [Binder 개요](https://source.android.com/docs/core/architecture/ipc/binder-overview)
- [Parcel.java android-13.0.0_r1](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/Parcel.java), [Parcel.cpp android-13.0.0_r1](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r1/libs/binder/Parcel.cpp), [Parcel.java android-8.0.0_r1](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-8.0.0_r1/core/java/android/os/Parcel.java)
- [2018-04-01 보안 게시판](https://source.android.com/docs/security/bulletin/2018-04-01), [2021-03-01 보안 게시판](https://source.android.com/docs/security/bulletin/2021-03-01)

다음 모듈은 handle 0의 주인을 다루는 [C19 servicemanager와 system_server](/posts/android-concept-atlas-c19-servicemanager-systemserver/)입니다.
