---
layout: post
title: "Android 앱 보안 분석 1~4주차 - 구조 실측과 분석 대상 앱 제작"
date: 2026-08-08 21:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 학습기록, APK, DEX, AndroidManifest, Sandbox, SELinux, UID, 앱수명주기, Kotlin, adb, 에뮬레이터, AVD, aapt2, apkanalyzer, 취약점분석, exported, ScopedStorage, SharedPreferences, 정적분석, 동적분석]
excerpt: "24주 로드맵의 첫 4주를 진행한 기록입니다. Android 앱 격리가 DAC와 SELinux 두 겹이라는 것을 명령 출력으로 확인하고, DEX 헤더를 손으로 디코딩해 ZIP 엔트리 크기와 교차 검증했습니다. 이어서 5주차부터 분석 대상이 될 테스트 앱을 직접 작성하면서, 통과하던 단위 테스트가 덮고 있던 배선 버그를 잡아내고 외부 저장소 노출 범위를 권한 비트까지 파고들어 정확히 규정했습니다."
---

> **진행 구간**: 24주 로드맵의 1~4주차
> **환경**: Windows 11 호스트 · AVD `sec-api33`(Android 13, API 33, 보안 패치 2024-03-01) · Gradle 8.9 + AGP 8.7.2 + Kotlin 2.0.21 + JBR 21
> **산출물**: 스터디 작업 디렉터리, 관측 자동화 스크립트 6종, 로컬 테스트 API, 테스트 앱 `kr.wtcy.memovault`
> **관련 글**: [24주 학습 로드맵](/posts/android-security-study-roadmap/) · [5~6주차](/posts/android-security-study-week5-6/) · [7~8주차](/posts/android-security-study-week7-8/)

---

이 글은 24주 Android 보안 학습 로드맵의 1~4주차 기록입니다. 커리큘럼상 1~2주차는 Android 앱의 구조를 정리하는 구간이고, 3~4주차는 앞으로 분석 대상이 될 테스트 앱을 직접 작성하는 구간입니다. 이 글에서는 Android 앱의 격리 구조와 실행 구조를 문서 설명이 아니라 실제 기기 출력으로 확인하는 과정, 그리고 5주차부터 분석할 취약 앱을 만들어 종단 동작까지 확인하는 과정을 순서대로 살펴보겠습니다.

---

## 배경 개념 - APK·DEX·샌드박스·수명주기

본격적인 관측에 들어가기 전에, 이번 구간에서 반복해서 등장하는 네 가지 개념을 먼저 짚어두겠습니다. Android 보안을 처음 보시는 분이라도 이후 절의 명령 출력을 그대로 따라올 수 있도록 최소한만 정리했습니다.

**APK**는 Android 앱의 배포 단위입니다. 실체는 ZIP 아카이브이며, 그 안에 실행 코드(`classes.dex`), 앱의 선언 정보(`AndroidManifest.xml`), 리소스와 서명이 함께 들어 있습니다. ZIP이기 때문에 압축 해제 도구만으로도 내부 엔트리 목록을 볼 수 있고, 우리가 분석을 시작할 때 가장 먼저 여는 대상이기도 합니다.

**DEX**(Dalvik Executable)는 Android 런타임이 실행하는 바이트코드 포맷입니다. Java의 `.class` 파일이 클래스마다 하나씩 생기는 것과 달리, DEX는 여러 클래스를 하나의 파일로 묶고 문자열·타입·메서드 참조를 공용 풀에 모아둡니다. 파일 맨 앞 112바이트가 헤더이고, 여기에 매직 넘버·파일 크기·각 풀의 개수와 오프셋이 들어 있습니다. 이 필드 배치는 AOSP의 [DEX 포맷 명세](https://source.android.com/docs/core/runtime/dex-format)에 바이트 단위로 정의돼 있어서, 뒤에서 헤더를 손으로 디코딩할 때 그대로 대조하는 기준이 됩니다. 이 메서드 참조 풀의 인덱스가 16비트라서 하나의 DEX가 담을 수 있는 메서드 참조는 65,536개가 상한이고, 이를 넘기면 `classes2.dex`, `classes3.dex`처럼 파일을 쪼개는 [멀티덱스](https://developer.android.com/build/multidex) 구성이 됩니다. 설치 시점에는 이 DEX가 다시 [ART](https://source.android.com/docs/core/runtime)의 검증·최적화 산출물(`.odex`/`.vdex`)로 한 번 더 가공되는데, 그 실물은 3-2에서 확인합니다.

**앱 샌드박스**는 앱끼리 서로의 데이터를 건드리지 못하게 막는 격리 장치입니다. Android는 설치 시점에 앱마다 고유한 리눅스 UID를 부여하고, 앱의 데이터 디렉터리를 그 UID 소유로 만듭니다. 즉 1차 방어선은 리눅스의 일반적인 파일 권한, 곧 **DAC**(임의 접근 제어)입니다. 그 위에 [**SELinux**](https://source.android.com/docs/security/features/selinux)가 **MAC**(강제 접근 제어)를 한 겹 더 얹습니다. SELinux는 프로세스에 도메인 레이블을, 파일에 타입 레이블을 붙이고 정책이 허용한 조합만 통과시킵니다. 여기에 **MLS 카테고리**라는 값이 추가로 붙는데, 앱마다 서로 다른 카테고리를 부여하면 같은 도메인에 속한 프로세스끼리도 서로를 건드릴 수 없게 됩니다. 두 겹 모두 같은 리눅스 커널이 강제하며([앱 샌드박스](https://source.android.com/docs/security/app-sandbox) 문서가 이 구조를 그림으로 정리해 둡니다), 이번 구간에서 두 겹을 각각 눈으로 확인합니다.

[**앱 수명주기**](https://developer.android.com/guide/components/activities/activity-lifecycle)는 액티비티가 생성되고 화면에 올라오고 가려지고 파괴되는 상태 전이 규칙입니다. 보안 분석에서 이 개념이 중요한 이유는, 프로세스가 완전히 죽은 뒤 새로 뜨는 **콜드 스타트**와 이미 살아 있는 프로세스를 다시 앞으로 불러오는 **웜 스타트**가 전혀 다른 코드 경로를 타기 때문입니다. 초기화 로직에 심어둔 결함은 콜드 스타트에서만 드러나는 경우가 많습니다. 여기서 새로 뜨는 프로세스는 매번 새로 컴파일되는 것이 아니라 [zygote](https://developer.android.com/guide/components/activities/process-lifecycle)에서 갈라져 나오는데, 그 실체도 3-3에서 확인합니다.

---

## 1. 실습 환경과 준비 - 기록 원칙과 JDK 버전 충돌

### 진행 방식과 기록 원칙

로드맵을 세워두고 첫 4주를 진행했습니다. 커리큘럼상 1~2주차는 "Android 구조를 노트로 정리", 3~4주차는 "로그인·메모·파일 업로드가 있는 테스트 앱 작성"입니다.

진행하면서 규칙을 하나 정했습니다. **읽어서 아는 것은 노트에 적지 않는다**는 규칙입니다. 문서에 있는 설명은 문서를 다시 보면 되고, 남길 가치가 있는 것은 제 기기에서 나온 출력과 그것을 잘못 읽을 뻔한 지점입니다. 그래서 아래 내용은 개념 정리라기보다 관측 기록에 가깝습니다.

### 도구 상태 점검과 JDK 버전 충돌

이전 작업들 덕분에 Android Studio·SDK·adb·에뮬레이터·jadx·apktool·frida가 이미 설치돼 있었습니다. Day 1~2를 건너뛸 수 있어 보였는데, 실제로 확인해보니 손봐야 할 것이 나왔습니다. 아래는 시스템 JDK와 Android Studio 번들 JDK의 버전을 각각 확인한 출력입니다.

```
$ java -version
java version "26.0.1"

$ "/c/Program Files/Android/Android Studio/jbr/bin/java" -version
openjdk version "21.0.10"
```

시스템 기본 JDK가 26입니다. AGP(Android Gradle Plugin)가 지원하지 않는 버전이라 Gradle을 그대로 돌리면 깨집니다. Android Studio 번들 JBR 21을 `JAVA_HOME`으로 강제해야 했습니다. "설치돼 있다"와 "쓸 수 있다"는 다릅니다.

시스템 이미지가 `android-33` 하나뿐이면 버전 간 차이를 비교할 축이 없습니다. 그래서 `android-36;google_apis;x86_64`를 추가로 받아 `sec-api33`/`sec-api36` 두 대를 baseline/비교 축으로 세우고, 실습 전 복구용 `clean` 스냅샷을 떴습니다. 한 대에서 관측한 절차를 다른 대에서 그대로 돌리면 API 레벨 차이가 출력에 그대로 드러나는 비교 하네스가 됩니다. 이 구조가 5주차 이후 "버전에 따라 무엇이 달라지는가"를 실측으로 답하는 뼈대가 됩니다.

이번 구간의 관측은 adb·apkanalyzer·jadx·apktool처럼 호스트에서 바로 도는 도구만으로 전부 덮이므로, Docker가 필요한 MobSF는 범위를 명확히 그어 다음 구간으로 넘겼습니다. 도구를 이번 목표에 맞게 고르는 것도 계획의 일부이고, 이렇게 못박아 두면 나중에 없는 도구를 전제로 한 절차에서 막힐 일이 없습니다.

---

## 2. 수행 절차 - 무계측 관측 자동화와 테스트 앱 제작

### 무계측 관측 절차

수명주기는 앱에 계측 코드를 넣지 않고 시스템 로그(`ActivityTaskManager`)와 `dumpsys`, `ps`로 관측했습니다. 분석 대상에 손을 대지 않고 바깥에서만 보는 방식이라, 나중에 소스가 없는 앱에도 같은 절차를 그대로 쓸 수 있습니다. 스크립트로 자동화해서 콜드 스타트 → 백그라운드 → 복귀 → 회전 → 종료 → 재시작을 순서대로 밟게 했습니다.

### 분석 대상 테스트 앱 제작

3~4주차 과제는 테스트 앱 작성입니다. 5주차부터 이 앱을 분석할 것이므로, **찾아낼 거리가 있는 앱**으로 만들었습니다.

`kr.wtcy.memovault` — 로그인, 메모 목록/작성/상세, 공지 WebView, 첨부 파일 업로드로 구성했습니다. 서버는 파이썬 표준 라이브러리만 쓴 단일 파일 테스트 더블입니다.

의존성은 최소로 했습니다. JSON은 내장 `org.json`, 네트워크는 `HttpURLConnection`, 스레딩은 `Executors`를 썼습니다. 코루틴도 Retrofit도 쓰지 않았는데 취향 문제가 아니라 **jadx로 열었을 때 생성 코드가 적어야 제가 쓴 로직이 보이기 때문**입니다. 디컴파일 결과에서 라이브러리가 만들어낸 코드와 개발자가 쓴 코드를 구분하는 일은 정적 분석에서 늘 부담이 되는 작업인데, 학습용 대상에서는 그 부담을 처음부터 줄여두는 편이 낫다고 판단했습니다.

현실적인 실수 패턴 10개를 심었습니다. exported 컴포넌트, 평문 토큰 저장, 로그 유출, cleartext HTTP, `allowBackup`, WebView JS 브릿지, 하드코딩 키, 클라이언트 측 인가, 그리고 업로드를 붙이며 생긴 두 개입니다.

---

## 3. 관측 결과 - 이중 샌드박스·DEX 구조·수명주기·테스트 앱 동작

### 3-1. UID와 SELinux로 이루어진 이중 샌드박스

"앱마다 UID가 달라서 서로 보지 못한다"는 문장은 알고 있었지만, 실제로 막히는 것을 확인한 적은 없었습니다. 앞서 정리한 대로 이 격리는 DAC와 MAC 두 층으로 이루어져 있으므로, 두 층을 따로따로 확인해보겠습니다. 먼저 설치된 앱의 UID를 조회합니다.

```
$ adb shell pm list packages -U | grep io.hextree.poc
package:io.hextree.poc uid:10174
```

일반 앱은 10000번대 UID를 받습니다. 파일시스템에서는 `u0_a174`(user 0, app 174)로 보입니다. 이 UID로 실제 접근이 막히는지 확인한 출력은 다음과 같습니다.

```
$ adb shell ls -ld /data/data/io.hextree.poc
ls: /data/data/io.hextree.poc: Permission denied

$ adb shell ls -la /data/data/com.android.settings
ls: /data/data/com.android.settings: Permission denied
```

`adb shell`은 uid 2000(`shell`)이고 앱이 아니므로 어느 앱 데이터도 읽지 못합니다. 다만 debug 빌드라 `run-as`로는 해당 앱의 권한을 빌려 들어갈 수 있었습니다.

```
$ adb shell run-as io.hextree.poc ls -laR /data/data/io.hextree.poc
drwx------   4 u0_a174 u0_a174        4096 .
drwxrwx--x 208 system  system        12288 ..
drwxrws--x   2 u0_a174 u0_a174_cache  4096 cache
```

앱 홈이 `0700`이고, 부모인 `/data/data`는 `drwxrwx--x`입니다. 여기서 실행 비트(`x`)만 있고 읽기 비트(`r`)는 없다는 점이 중요합니다. **탐색은 되지만 목록은 되지 않습니다.** 경로를 정확히 알면 접근을 시도할 수는 있어도 무엇이 설치돼 있는지는 열거하지 못합니다. 이 구분을 몰랐는데 권한 비트를 직접 보고 알았습니다. 참고로 "무엇이 설치돼 있는지 열거하지 못한다"는 이 성질은 Android 11 이후 [패키지 가시성](https://developer.android.com/training/package-visibility) 필터링과 짝을 이룹니다. `QUERY_ALL_PACKAGES` 없이 다른 앱을 조회하면 `system apps queryable: false`로 막히는데, 파일시스템의 목록 차단과 패키지 질의의 목록 차단이 같은 원리로 겹쳐 있는 셈입니다.

이 `0700` 구조는 이 앱·이 기기에만 있는 값이 아닙니다. 별도로 세팅한 API 33 루트 에뮬레이터에서 전혀 다른 표본 앱(`com.example.visibilitylegacy`)으로 다시 떠보면 `userId=10176`이 붙고 `/data/data/com.example.visibilitylegacy`는 `drwx------ u0_a176 u0_a176`, 부모 `/data/data`는 `drwxrwx--x`로 동일했습니다. 기기·앱을 바꿔도 홈 `0700`·부모 `--x`라는 배치가 그대로 재현된다는 것을, 두 개의 독립된 관측으로 확인한 셈입니다.

여기까지가 첫 번째 겹인 DAC입니다. 두 번째 겹도 확인해보겠습니다.

```
$ adb shell getenforce
Enforcing

$ adb shell ps -A -Z | grep io.hextree.poc
u:r:untrusted_app:s0:c174,c256,c512,c768  u0_a174  7606  io.hextree.poc
```

SELinux가 `Enforcing` 모드로 동작 중이고, 앱 프로세스의 도메인은 `untrusted_app`입니다. 그리고 카테고리에 **`c174`**가 붙어 있습니다. 앞서 본 앱 ID 174와 같은 값입니다. 즉 UID로 한 번, SELinux MLS 카테고리로 또 한 번 격리합니다. 설치된 모든 일반 앱이 똑같이 `untrusted_app` 도메인을 쓰기 때문에 도메인만으로는 앱끼리 구분되지 않는데, 카테고리가 서로 달라서 결국 접근하지 못하게 됩니다.

### 3-2. DEX 헤더 수동 디코딩과 멀티덱스 구성

앞에서 정리한 DEX 헤더 구조를 실제 파일로 확인했습니다. `classes.dex` 앞 64바이트를 그대로 떠서 해석한 결과입니다.

```
00000000: 6465 780a 3033 3900 03b9 14e4 c5ac c8fb  dex.039.........
00000020: 3085 9a00 7000 0000 7856 3412 0000 0000  0...p...xV4.....
00000030: 0000 0000 6084 9a00 ea16 0100 7000 0000  ....`.......p...
```

각 오프셋을 필드에 대응시키면 다음과 같습니다. DEX 헤더는 리틀 엔디언이므로 바이트 순서를 뒤집어 읽어야 합니다.

| 오프셋 | 필드 | 해석 |
| --- | --- | --- |
| 0x00 | `magic` | `dex\n039\0` |
| 0x20 | `file_size` | 0x009A8530 = **10,126,640** |
| 0x24 | `header_size` | 112 |
| 0x28 | `endian_tag` | 0x12345678 |
| 0x38 | `string_ids_size` | 0x000116EA = 71,402 |

`endian_tag`가 0x12345678로 읽힌다는 것 자체가 바이트 순서를 제대로 해석했다는 신호입니다. 여기에 더해, ZIP 엔트리 목록의 `classes.dex` 크기도 정확히 10,126,640이었습니다. 손으로 읽은 값과 맞아떨어져서 디코딩이 맞다는 확인이 됐습니다. 이런 자체 검증 지점을 하나씩 잡아두는 습관을 들이려 합니다.

멀티덱스가 왜 존재하는지도 숫자로 확인했습니다. 아래는 DEX 파일별 메서드 참조 개수입니다.

```
classes.dex   61381
classes2.dex    237
classes3.dex    174
classes4.dex    140
```

주 DEX 메서드 참조가 61,381개로 한도 65,536의 94%입니다. 나머지 3개에 흩어진 것은 551개뿐인데도 파일이 나뉜 이유가 이것입니다. 앱 코드가 커서가 아니라 androidx가 인덱스 공간을 먹어서입니다.

이 DEX는 설치되면 그대로 실행되는 것이 아니라 ART가 한 번 더 가공합니다. 배경에서 예고한 `.odex`/`.vdex`가 그 결과물인데, 별도 API 33 루트 에뮬레이터에서 설치 직후 앱의 `oat/` 디렉터리를 떠보면 실체가 드러납니다.

```
$ ls -l .../oat/x86_64/
-rw-r--r-- 1 system all_a176 17296 base.odex
-rw-r--r-- 1 system all_a176  3980 base.vdex

# dumpsys package <pkg> 의 Dexopt state 절
      x86_64: [status=verify] [reason=install]
```

`base.vdex`는 검증(verify) 결과를 담고 `base.odex`는 최적화된 코드를 담습니다. 여기서 `status=verify`라는 값이 중요합니다. 설치 시점에는 전체 AOT 컴파일까지 가지 않고 **검증만 마친 상태**로 두었다가, 이후 유휴 시간의 백그라운드 dexopt에서 실제 사용 패턴에 맞춰 더 컴파일한다는 뜻입니다. 즉 "DEX 헤더 → 멀티덱스 분할 → 설치 시 verify → 백그라운드 AOT"라는 한 흐름의 앞 두 단계를 손으로, 뒤 단계를 `dumpsys`로 이어 붙여 확인했습니다.

### 3-3. 콜드 스타트 판별

HOME으로 보낸 뒤 프로세스를 종료하고 다시 띄운 재시작 결과입니다.

```
LaunchState: COLD    TotalTime: 707
PID 7276 → 7606
```

**PID가 바뀌었는지가 콜드 스타트의 증거입니다.** 상태 문자열만 믿으면 안 됩니다.

바뀐 PID는 "새 프로세스가 어디서 태어났는가"까지 말해줍니다. 앱 프로세스는 매번 새로 컴파일되는 게 아니라 이미 클래스와 힙이 예열된 zygote를 `fork`해서 만들어지고, 그래서 콜드 스타트가 707ms로 끝납니다. 별도 API 33 루트 에뮬레이터에서 프로세스 트리를 떠보면 이 부모-자식 관계가 그대로 보입니다.

```
$ ps -A -o PID,PPID,NAME | grep zygote
  305     1 zygote64
  763   305 webview_zygote
```

`zygote64`(pid 305)의 부모는 `init`(pid 1)이고, 앱과 WebView 프로세스는 다시 이 zygote 계열에서 갈라져 나옵니다. 특히 WebView는 별도의 `webview_zygote`를 거치는데, 3-4의 공지 WebView처럼 웹 콘텐츠를 렌더링하는 코드를 앱 본체와 다른 프로세스로 떼어 격리하기 위해서입니다. 콜드 스타트의 새 PID를 이 트리 위에 얹으면 "새로 fork된 자식"이라는 그림이 완성됩니다.

### 3-4. 테스트 앱 종단 동작

빌드하고 설치해서 실제로 도는지 확인했습니다. 아래는 테스트 서버 쪽에 남은 요청 로그입니다.

```
POST /login  -> 200
GET  /memos  -> 200
POST /upload -> 201
```

![MemoVault 로그인 화면. 에뮬레이터 sec-api33에서 실행 중이며 아이디·비밀번호 입력란과 로그인 버튼, 하단에 접속 서버 주소 http://10.0.2.2:8099가 표시돼 있습니다](/assets/img/android-security-study/01-login.png)

로그인 후 메모 목록입니다. 여기서 한 가지가 바로 눈에 띕니다.

![메모 목록 화면. 상단에 "사용자: alice"로 로그인돼 있는데 목록에는 alice의 메모(장보기, 스터디 메모)뿐 아니라 bob의 메모(회의 요약, 비밀 메모)까지 함께 나열돼 있습니다](/assets/img/android-security-study/02-memo-list.png)

`alice`로 로그인했는데 `bob`의 메모까지 보입니다. 서버가 토큰 주인을 확인하지 않고 전체 목록을 내려주기 때문입니다. 일부러 남겨둔 인가 결함이고, 앱의 클라이언트 측 인가 문제와 짝을 이룹니다.

로그도 확인했습니다. 다음은 로그인 시점에 실제로 관측된 logcat 출력입니다.

```
D MemoVault: submit credentials u=alice p=alice123 key=mv_live_7c1f9a3e...
```

첫 줄에서 비밀번호와 API 키가 그대로 logcat에 찍힙니다. 심어둔 대로입니다.

3~4주차 과제에 있던 파일 업로드도 붙였습니다. 메모 상세에서 첨부를 올리면 서버 저장 이름과 로컬 사본 경로가 함께 표시됩니다.

![메모 상세 화면에서 첨부 파일 업로드 버튼을 누른 결과. "업로드 완료: 0001-memo-1786235238359.txt (29 bytes)"와 로컬 사본 경로가 표시돼 있습니다](/assets/img/android-security-study/03-attach-upload.png)

### 3-5. exported 컴포넌트를 통한 내부 파일 유출

가장 흥미로웠던 확인입니다. exported 컴포넌트란 다른 앱이 인텐트로 직접 호출할 수 있도록 공개된 컴포넌트를 말합니다. 매니페스트에서 [`android:exported="true"`](https://developer.android.com/guide/topics/manifest/activity-element#exported)로 선언되며, 이 경우 해당 액티비티는 시스템의 어떤 앱이든 `am start`나 코드 한 줄로 띄울 수 있습니다.

이번 앱의 메모 상세 화면이 바로 `exported="true"`이고, 첨부할 파일 경로를 인텐트 extra로 그대로 받습니다. 외부에서 인텐트 하나를 던져보겠습니다.

```bash
adb shell am start -n kr.wtcy.memovault/.MemoDetailActivity \
  --es memo_id 1 \
  --es attach_path /data/data/kr.wtcy.memovault/shared_prefs/session.xml
```

서버에 `session.xml`이 올라왔습니다. 앱 화면이 그 결과를 그대로 보여줍니다.

![메모 상세 화면 하단에 "업로드 완료: 0002-session.xml (213 bytes)"와 로컬 사본 경로가 표시돼 있습니다. 외부 인텐트로 지정한 앱 내부 세션 파일이 서버로 전송된 결과입니다](/assets/img/android-security-study/04-exfil-session.png)

올라간 파일 내용은 다음과 같습니다.

```xml
<string name="auth_token">mvt_alice_0001</string>
<string name="username">alice</string>
```

`am start`로 던진 이 인텐트는 겉으로는 명령 한 줄이지만, 밑에서는 커널의 **binder** 드라이버를 지나는 IPC 트랜잭션입니다. 인텐트를 `ActivityManager`에 넘기는 것도, 그쪽이 대상 앱의 프로세스를 깨워 액티비티를 띄우는 것도 전부 binder 위에서 일어납니다. 별도 API 33 루트 에뮬레이터에서 `binder` 통계를 떠보면 이 경로가 시스템 전체에서 얼마나 뜨거운지 보입니다.

```
$ cat /sys/kernel/debug/binder/stats   # (일부)
BC_TRANSACTION: 113300
BC_REPLY: 88602
BC_FREE_BUFFER: 211526
```

부팅 후 짧은 시간에도 트랜잭션이 11만 건을 넘습니다. exported 컴포넌트가 위험한 근본 이유가 여기 있습니다. 앱 간 경계를 넘나드는 이 binder 통로는 시스템이 정상 동작하려면 늘 열려 있어야 하고, `exported="true"`는 그 통로의 수신구를 "아무 앱이나"에게 여는 선언입니다. 격리(3-1)와 그 격리를 넘는 통로(여기)를 같은 기기에서 한 번씩 관측하니, 왜 exported 하나가 유출로 직결되는지가 명령 출력만으로 이어졌습니다.

---

## 4. 결과 해석 - 두 겹의 격리와 앱이 스스로 여는 입구

### 한 단어 뒤에 있던 두 메커니즘

"앱 샌드박스"라는 한 단어가 실제로는 서로 다른 두 메커니즘(DAC + MAC)이라는 것을 출력으로 확인한 것이 이번 구간에서 가장 남는 부분이었습니다.

### 격리를 뚫지 않고 넘는 경로

공격자 입장에서 `/data/data/kr.wtcy.memovault/`는 직접 읽지 못합니다. 3-1에서 확인한 그대로입니다. 그런데 **피해 앱에게 대신 읽어달라고 시킬 수는 있습니다.** 샌드박스는 뚫리지 않았고, 앱이 자기 권한을 남에게 빌려준 것입니다. 격리가 프로세스 단위로 걸려 있는 이상, 경계를 넘는 입구를 앱이 스스로 열어두면 격리 자체는 아무 일도 하지 않습니다.

exported 컴포넌트가 왜 위험한지를 문장이 아니라 파일 하나로 확인했습니다.

---

## 5. 시행착오와 정정

아래 다섯 가지는 이번 구간에서 **최종 기록에 들어가기 전에 잡아낸** 측정·해석 오류입니다. 다섯 건 모두 노트에 굳기 전에 걸러졌고, 걸러낸 과정 자체가 이 구간의 산출물입니다. 관측 로그는 맞은 결론만큼이나 "틀릴 뻔한 지점을 어디서, 어떤 대조로 잡았는가"로 신뢰를 얻기 때문에, 지우지 않고 그대로 남깁니다. 하나씩 보면 전부 "출력은 정직했고, 한 번 더 확인해서 제자리로 돌려놓은" 이야기입니다.

### 5-1. sourced 환경 파일로 인한 스크립트 조기 종료

관측 스크립트가 첫 실행에서 중간에 끊겼습니다. 증적 파일이 일부만 생기고 완료 표시가 찍히지 않았는데 에러 메시지도 없었습니다.

원인은 공통 환경 파일이었습니다. 문제가 된 부분은 다음과 같습니다.

```bash
# tools/env.sh
set -euo pipefail     # ← 이것
export ANDROID_HOME=...
```

관측 스크립트는 일부러 `set -e`를 빼고 `set -uo pipefail`만 걸어뒀습니다. **실패가 정상 결과**이기 때문입니다. `Permission denied`가 곧 샌드박스가 작동한다는 증거이니까요. 그런데 다음 줄에서 `source tools/env.sh`를 하는 순간 `set -e`가 다시 켜집니다. sourced 파일의 `set`은 별도 프로세스가 아니라 호출한 셸에 그대로 적용되기 때문입니다.

그래서 첫 `Permission denied`에서 스크립트 전체가 죽었습니다.

고칠 때 호출부에 `set +e`를 붙이는 대신 원인 쪽을 건드렸습니다. `env.sh`는 변수만 내보내는 파일이므로 `set` 선언을 지웠고, 실행 스크립트들은 이미 각자 자기 옵션을 첫 줄에서 선언하고 있어 영향이 없었습니다. 덕분에 jadx/apktool이 경고만으로도 non-zero로 끝나서 `set -u`만 걸어둔 정적 분석 스크립트에서 같은 버그가 터질 예정이었던 것도 함께 막혔습니다.

수정 후 재실행하면 16개 항목이 전부 수집되고 두 개만 `exit=1`로 남습니다. 그 두 개의 실패가 이번 구간의 핵심 증거입니다.

### 5-2. DEX 파일 개수 오판

여기서 첫 번째 오판이 나왔습니다. `unzip -l | grep dex` 출력 앞부분만 보고 "DEX 2개"라고 적었는데, `apkanalyzer`는 4개를 보고했습니다. 확인해보니 4개가 맞았고 ZIP 엔트리 순서상 `classes4.dex`가 `classes3.dex`보다 먼저 나열돼 있었습니다. **도구 하나의 출력을 결론으로 삼으면 안 된다**는 것을 첫날부터 확인한 셈입니다.

### 5-3. `am kill`이 포그라운드 프로세스를 죽이지 않는 문제

수명주기 관측 스크립트에서 문제는 "종료" 단계였습니다. 처음 스크립트는 `am kill`만 부르고 다음 단계를 "콜드 스타트 재현"이라고 적게 돼 있었는데, 출력이 다음과 같았습니다.

```
=== 5. 프로세스 강제 종료 (am kill) 후 상태 ===
u:r:untrusted_app:... u0_a174 7276 ... io.hextree.poc      ← 살아있음

=== 6. 강제 종료 후 재시작 ===
Warning: Activity not started, intent has been delivered to
         currently running top-most instance.
LaunchState: UNKNOWN (0)   TotalTime: 0
```

`am kill`은 **백그라운드 프로세스만** 죽입니다. 포그라운드에 있으면 아무 일도 하지 않습니다. 그대로 뒀으면 노트에는 "콜드 스타트"라고 적히고 실제로는 웜 스타트인 기록이 남았을 것입니다.

HOME으로 보낸 뒤 `am kill`을 부르도록 고치니 프로세스가 사라졌고, 재시작 결과가 3-3의 출력으로 바뀌었습니다. `am kill`(저메모리 킬 시뮬레이션)과 `am force-stop`(태스크까지 제거)의 차이도 이 과정에서 갈렸습니다.

### 5-4. 통과하는 단위 테스트가 가린 필드명 불일치

앱을 붙여보니 로그인이 401로 떨어졌습니다. 서버는 로그인 응답에 `is_admin`을 내려주는데 앱은 다음과 같이 읽고 있었습니다.

```kotlin
o.optBoolean("isAdmin", false)     // 서버는 is_admin 으로 보낸다
```

그리고 단위 테스트는 다음과 같이 쓰여 있었습니다.

```kotlin
ApiClient.parseLogin("""{"token":"tok","user":"alice","isAdmin":true}""")
```

**테스트가 코드와 같은 오타를 쓰고 있어서 초록불이 떴습니다.** 서버가 실제로 무엇을 보내는지 확인하지 않고 자기 자신을 검증한 셈입니다. 결과적으로 서버 경로로는 관리자 플래그가 영원히 false여서, 심어둔 클라이언트 측 인가 취약점이 반쪽짜리가 되어 있었습니다.

테스트를 서버가 실제로 보내는 페이로드 기준으로 다시 썼습니다. 통과 여부보다 **무엇을 기준으로 통과했는지**를 봐야 한다는 것을 실물로 확인했습니다.

### 5-5. 외부 저장소 노출 범위의 재평가

업로드한 첨부의 로컬 사본을 `getExternalFilesDir()` 아래 남기도록 만들어 놓고, "외부 저장소이니 다른 앱이 읽겠지"라고 생각했습니다. 여기서 말하는 외부 저장소는 물리적으로 분리된 SD 카드가 아니라 `/storage/emulated/0` 아래의 공유 볼륨을 가리키며, `Android/data/<패키지명>/`은 그중에서도 앱 전용으로 할당된 영역입니다. 확인해보니 읽히기는 했습니다.

```
$ adb shell cat /storage/emulated/0/Android/data/kr.wtcy.memovault/files/attachments/memo-*.txt
우유, 계란, 커피 원두
```

그런데 디렉터리 권한이 다음과 같았습니다.

```
drwxrws--- 2 u0_a175 ext_data_rw 4096 .
```

그룹이 `ext_data_rw`이고, 그룹 외 권한(other)은 아예 비어 있습니다. `adb shell`이 읽을 수 있었던 것은 shell이 마침 그 그룹에 속해 있어서였습니다. 실제 소속 그룹을 확인한 출력입니다.

```
$ adb shell id
... 1015(sdcard_rw),1028(sdcard_r),1078(ext_data_rw) ...
```

일반 앱은 이 그룹에 속하지 않습니다. [Scoped storage](https://developer.android.com/training/data-storage#scoped-storage) 도입 이후 `Android/data/<pkg>/`는 다른 앱에서 접근이 막힙니다. 그러니 정확한 영향은 "다른 앱이 훔쳐본다"가 아니라 **"앱 샌드박스 바깥 볼륨에 평문으로 남아서 adb·백업·파일관리 권한을 가진 주체에게 노출된다"**입니다. 대조군으로 앱 전용 `shared_prefs`는 같은 shell로도 `Permission denied`였습니다.

한 단계 낮춰 적는 것이 맞았습니다. 관측 결과가 있어도 **왜 그렇게 나왔는지**를 확인하지 않으면 결론이 틀어집니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~2주 | Android 구조 정리 | 완료 |
| 3~4주 | 테스트 앱 작성 | 완료 (빌드·설치·종단 동작 확인) |
| 5~6주 | 정적 분석 | 다음 |

로드맵에 적어둔 "다음 단계 판단 기준" 중 지금 충족한 것은 재현성 항목입니다. 스냅샷·빌드 지문·요청 로그로 실험을 언제든 되돌릴 수 있게 만들어 두었습니다. 나머지 기준은 5주차 이후 항목이라 지금 손댈 대상이 아니고, 그 항목들을 밟을 발판(두 대 비교 하네스, 무계측 관측 스크립트)은 이번 구간에 이미 갖췄습니다.

심어둔 약점 10개는 모두 소스·매니페스트에서 위치를 확인해 두었고, 그중 4개는 이번 구간에 동적으로 종단까지 눌러 재현했습니다(로그 유출, 서버·클라이언트 인가 결함, exported 유출, 평문 세션 저장). 나머지 6개는 5~6주차 정적 분석에서 전부 표로 정리한 뒤 하나씩 동적으로 밟을 차례입니다. `sec-api36`에서 같은 절차를 돌려 API 레벨 차이를 비교하는 축도 이미 세워 두었습니다.

관측의 토대가 되는 기기 자체도 버전까지 못박아 두었습니다. 이 계열 에뮬레이터의 커널은 `5.15.119-android13`이고 로드된 모듈은 53개(대부분 `virtio_*` 가상화 드라이버)로, 앞에서 확인한 DAC·MAC·binder를 강제하는 바로 그 커널을 특정해 기록했습니다. 5주차 이후 네이티브 라이브러리 분석으로 넘어가면 여기에 프로세스 **내부**의 완화 계층이 한 겹 더 붙습니다. 같은 계열의 `libart.so`를 정적으로 뜯어보면 `BIND_NOW` 기반 full RELRO가 걸려 있고(`FLAGS: BIND_NOW`, `FLAGS_1: NOW`), arm64 빌드에는 `.note.gnu.property`에 `aarch64 feature: BTI, PAC` 표시가 들어 있습니다. 이번 구간의 프로세스 **간** 격리와, 다음 네이티브 구간의 프로세스 **내** 익스플로잇 완화를 이렇게 잇대어 볼 계획입니다.

---

## 참고 자료 (1차 출처)

이번 구간에서 관측한 값들을 대조한 원 문서입니다. 위에서 인용한 링크를 주제별로 모았습니다.

- **APK · DEX · ART**
  - [DEX 포맷 명세](https://source.android.com/docs/core/runtime/dex-format) — 헤더 112바이트 필드 배치의 원본 (3-2 대조 기준)
  - [ART와 Dalvik](https://source.android.com/docs/core/runtime) — 설치 시 `.odex`/`.vdex` 생성과 dexopt
  - [멀티덱스 구성](https://developer.android.com/build/multidex) — 65,536 메서드 한도와 분할
- **앱 샌드박스 · SELinux · 가시성**
  - [애플리케이션 샌드박스](https://source.android.com/docs/security/app-sandbox) — UID 기반 격리(DAC)
  - [SELinux](https://source.android.com/docs/security/features/selinux) — 도메인·타입·MLS 카테고리(MAC)
  - [권한 개요](https://developer.android.com/guide/topics/permissions/overview) · [패키지 가시성](https://developer.android.com/training/package-visibility) — 3-1의 열거 차단과 짝
- **수명주기 · 프로세스**
  - [액티비티 수명주기](https://developer.android.com/guide/components/activities/activity-lifecycle) · [프로세스와 앱 수명주기](https://developer.android.com/guide/components/activities/process-lifecycle) — 콜드/웜 스타트와 zygote fork
- **IPC · exported 컴포넌트**
  - [`<activity android:exported>`](https://developer.android.com/guide/topics/manifest/activity-element#exported) · [앱 보안 권장사항](https://developer.android.com/privacy-and-security/security-tips) — 3-5의 유출 경로
- **저장소 · 데이터**
  - [데이터·파일 저장소(Scoped storage)](https://developer.android.com/training/data-storage#scoped-storage) · [Android 11 저장소 변경](https://developer.android.com/about/versions/11/privacy/storage) — 5-5의 노출 범위 판정
- **모바일 앱 보안 점검 기준**
  - [OWASP MASVS](https://mas.owasp.org/MASVS/) · [OWASP MASTG](https://mas.owasp.org/MASTG/) — exported·저장소·로깅 결함의 표준 테스트 항목

---

## 마치며

이번 구간에서 반복해서 나온 패턴이 하나 있습니다. **출력은 맞는데 해석이 처음엔 어긋났다가, 한 번 더 확인해서 매번 제자리로 잡아낸 경우**입니다.

DEX 개수를 앞부분만 보고 셌고, `am kill`이 동작했다고 가정했고, 외부 저장소를 과대평가했고, 테스트가 통과했으니 코드가 맞다고 봤습니다. 네 번 다 첫 판단은 빗나갔지만, 네 번 다 출력을 한 번 더 파고들어 제자리로 돌려놨습니다. 도구를 바꿔 다시 세고, PID·권한 비트·그룹 소속·서버가 실제로 보낸 페이로드를 각각 대조한 결과입니다. 도구는 정직했고, 그 정직한 출력을 끝까지 읽어낸 것이 이번 구간의 실제 성과입니다.

로드맵에 "도구 결과는 결론이 아니다"라고 적어둔 것이 추상적인 원칙인 줄 알았는데, 4주 동안 네 번을 실물로 붙잡으면서 몸에 붙는 절차가 됐습니다. 이제는 관측할 때마다 "이 출력이 다르게 해석될 여지가 있나"를 한 번씩 붙이는 것이 기본기가 됐습니다.

여기까지 읽어주셔서 감사합니다. 다음 글에서는 5~6주차 정적 분석 과정을 다루겠습니다.
