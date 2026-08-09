---
layout: post
title: "Android 보안 스터디 1~4주차 — 구조를 실측으로 확인하고, 분석할 앱을 직접 만들었다"
date: 2026-08-08
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 학습기록, APK, DEX, AndroidManifest, Sandbox, SELinux, UID, 앱수명주기, Kotlin, adb, 에뮬레이터, AVD, aapt2, apkanalyzer, 취약점분석, exported, ScopedStorage, SharedPreferences, 정적분석, 동적분석]
excerpt: "24주 로드맵의 첫 4주를 진행한 기록입니다. Android 앱 격리가 DAC와 SELinux 두 겹이라는 걸 명령 출력으로 확인하고, DEX 헤더를 손으로 디코딩해 교차 검증했습니다. 이어서 5주차부터 분석 대상이 될 테스트 앱을 직접 작성하면서, 통과하는 단위 테스트가 배선 버그를 덮고 있던 일과 외부 저장소 노출 범위를 처음에 과대평가했던 일을 함께 적었습니다."
---

> **진행 구간**: 24주 로드맵의 1~4주차
> **환경**: Windows 11 호스트 · AVD `sec-api33`(Android 13, API 33, 보안 패치 2024-03-01) · Gradle 8.9 + AGP 8.7.2 + Kotlin 2.0.21 + JBR 21
> **산출물**: 스터디 작업 디렉터리, 관측 자동화 스크립트 6종, 로컬 테스트 API, 테스트 앱 `kr.wtcy.memovault`
> **관련 글**: [24주 학습 로드맵](/posts/android-security-study-roadmap/) · [5~6주차](/posts/android-security-study-week5-6/) · [7~8주차](/posts/android-security-study-week7-8/)

---

## 0. 왜 이렇게 진행했나

로드맵을 세워두고 첫 4주를 돌렸습니다. 커리큘럼상 1~2주차는 "Android 구조를 노트로 정리", 3~4주차는 "로그인·메모·파일 업로드가 있는 테스트 앱 작성"입니다.

진행하면서 규칙을 하나 정했습니다. **읽어서 아는 것은 노트에 안 적는다.** 문서에 있는 설명은 문서를 다시 보면 되고, 남길 가치가 있는 건 내 기기에서 나온 출력과 그걸 잘못 읽을 뻔한 지점입니다. 그래서 아래 내용은 개념 정리가 아니라 관측 기록에 가깝습니다.

---

## 1. 환경은 예상보다 앞서 있었고, 그게 함정이었다

이전 작업들 때문에 Android Studio·SDK·adb·에뮬레이터·jadx·apktool·frida가 이미 깔려 있었습니다. Day 1~2를 건너뛸 수 있어 보였는데, 실제로 확인해보니 손봐야 할 게 나왔습니다.

```
$ java -version
java version "26.0.1"

$ "/c/Program Files/Android/Android Studio/jbr/bin/java" -version
openjdk version "21.0.10"
```

시스템 기본 JDK가 26입니다. AGP가 지원하지 않는 버전이라 Gradle을 그대로 돌리면 깨집니다. Android Studio 번들 JBR 21을 `JAVA_HOME`으로 강제해야 했습니다. "설치돼 있다"와 "쓸 수 있다"는 다릅니다.

시스템 이미지도 `android-33`뿐이라 API 레벨 비교가 불가능했습니다. `android-36;google_apis;x86_64`를 추가로 받아 `sec-api33`/`sec-api36` 두 대를 만들고, 실습 전 복구용 `clean` 스냅샷을 떴습니다.

Docker 데몬이 죽어 있어 MobSF는 이번 구간에서 제외했습니다. 없는 도구를 쓰는 계획을 세워두면 나중에 막히므로 범위에서 빼고 기록해뒀습니다.

---

## 2. 앱 샌드박스는 두 겹이었다

"앱마다 UID가 달라서 서로 못 본다"는 문장은 알고 있었지만, 실제로 막히는 걸 확인한 적은 없었습니다. 이번에 명령으로 확인했습니다.

```
$ adb shell pm list packages -U | grep io.hextree.poc
package:io.hextree.poc uid:10174
```

일반 앱은 10000번대 UID를 받습니다. 파일시스템에서는 `u0_a174`(user 0, app 174)로 보입니다.

```
$ adb shell ls -ld /data/data/io.hextree.poc
ls: /data/data/io.hextree.poc: Permission denied

$ adb shell ls -la /data/data/com.android.settings
ls: /data/data/com.android.settings: Permission denied
```

`adb shell`은 uid 2000(`shell`)이고 앱이 아니므로 어느 앱 데이터도 못 읽습니다. debug 빌드라 `run-as`로는 들어갈 수 있었습니다.

```
$ adb shell run-as io.hextree.poc ls -laR /data/data/io.hextree.poc
drwx------   4 u0_a174 u0_a174        4096 .
drwxrwx--x 208 system  system        12288 ..
drwxrws--x   2 u0_a174 u0_a174_cache  4096 cache
```

앱 홈이 `0700`이고, 부모인 `/data/data`는 `drwxrwx--x`입니다. **탐색은 되지만 목록은 안 됩니다.** 경로를 정확히 알면 접근을 시도할 수는 있어도 무엇이 설치돼 있는지는 열거하지 못합니다. 이 구분을 몰랐는데 권한 비트를 직접 보고 알았습니다.

여기까지가 첫 번째 겹입니다. 두 번째가 있었습니다.

```
$ adb shell getenforce
Enforcing

$ adb shell ps -A -Z | grep io.hextree.poc
u:r:untrusted_app:s0:c174,c256,c512,c768  u0_a174  7606  io.hextree.poc
```

SELinux 도메인이 `untrusted_app`이고 카테고리에 **`c174`**가 붙어 있습니다. 앱 ID 174와 같은 값입니다. UID로 한 번, SELinux MLS 카테고리로 또 한 번 격리합니다. 같은 `untrusted_app` 도메인끼리도 카테고리가 달라서 서로 접근하지 못합니다.

"앱 샌드박스"라는 한 단어가 실제로는 서로 다른 두 메커니즘(DAC + MAC)이라는 걸 출력으로 본 게 이번 구간에서 제일 남는 부분이었습니다.

---

## 3. DEX 헤더를 손으로 읽고 교차 검증했다

`classes.dex` 앞 64바이트를 그대로 떠서 해석했습니다.

```
00000000: 6465 780a 3033 3900 03b9 14e4 c5ac c8fb  dex.039.........
00000020: 3085 9a00 7000 0000 7856 3412 0000 0000  0...p...xV4.....
00000030: 0000 0000 6084 9a00 ea16 0100 7000 0000  ....`.......p...
```

| 오프셋 | 필드 | 해석 |
| --- | --- | --- |
| 0x00 | `magic` | `dex\n039\0` |
| 0x20 | `file_size` | 0x009A8530 = **10,126,640** |
| 0x24 | `header_size` | 112 |
| 0x28 | `endian_tag` | 0x12345678 |
| 0x38 | `string_ids_size` | 0x000116EA = 71,402 |

ZIP 엔트리 목록의 `classes.dex` 크기도 정확히 10,126,640이었습니다. 손으로 읽은 값과 맞아떨어져서 디코딩이 맞다는 확인이 됐습니다. 이런 자체 검증 지점을 하나씩 잡아두는 습관을 들이려 합니다.

멀티덱스가 왜 있는지도 숫자로 봤습니다.

```
classes.dex   61381
classes2.dex    237
classes3.dex    174
classes4.dex    140
```

주 DEX 메서드 참조가 61,381개로 한도 65,536의 94%입니다. 나머지 3개에 흩어진 건 551개뿐인데도 파일이 나뉜 이유가 이겁니다. 앱 코드가 커서가 아니라 androidx가 인덱스 공간을 먹어서입니다.

그리고 여기서 첫 번째 오판이 나왔습니다. `unzip -l | grep dex` 출력 앞부분만 보고 "DEX 2개"라고 적었는데, `apkanalyzer`는 4개를 보고했습니다. 확인해보니 4개가 맞았고 ZIP 엔트리 순서상 `classes4.dex`가 `classes3.dex`보다 먼저 나열돼 있었습니다. **도구 하나의 출력을 결론으로 삼으면 안 된다**는 걸 첫날부터 확인한 셈입니다.

---

## 4. 콜드 스타트인 줄 알았던 게 아니었다

수명주기는 앱에 계측을 넣지 않고 시스템 로그(`ActivityTaskManager`)와 `dumpsys`, `ps`로 관측했습니다. 스크립트로 자동화해서 콜드 스타트 → 백그라운드 → 복귀 → 회전 → 종료 → 재시작을 순서대로 밟게 했습니다.

문제는 "종료" 단계였습니다. 처음 스크립트는 `am kill`만 부르고 다음 단계를 "콜드 스타트 재현"이라고 적게 돼 있었는데, 출력이 이랬습니다.

```
=== 5. 프로세스 강제 종료 (am kill) 후 상태 ===
u:r:untrusted_app:... u0_a174 7276 ... io.hextree.poc      ← 살아있음

=== 6. 강제 종료 후 재시작 ===
Warning: Activity not started, intent has been delivered to
         currently running top-most instance.
LaunchState: UNKNOWN (0)   TotalTime: 0
```

`am kill`은 **백그라운드 프로세스만** 죽입니다. 포그라운드에 있으면 아무 일도 하지 않습니다. 그대로 뒀으면 노트에는 "콜드 스타트"라고 적히고 실제로는 웜 스타트인 기록이 남았을 겁니다.

HOME으로 보낸 뒤 `am kill`을 부르도록 고치니 프로세스가 사라졌고, 재시작이 이렇게 나왔습니다.

```
LaunchState: COLD    TotalTime: 707
PID 7276 → 7606
```

**PID가 바뀌었는지가 콜드 스타트의 증거입니다.** 상태 문자열만 믿으면 안 됩니다. `am kill`(저메모리 킬 시뮬레이션)과 `am force-stop`(태스크까지 제거)의 차이도 이 과정에서 갈렸습니다.

---

## 5. 조용히 죽는 스크립트

관측 스크립트가 첫 실행에서 중간에 끊겼습니다. 증적 파일이 일부만 생기고 완료 표시가 안 찍혔는데 에러 메시지도 없었습니다.

원인은 공통 환경 파일이었습니다.

```bash
# tools/env.sh
set -euo pipefail     # ← 이것
export ANDROID_HOME=...
```

관측 스크립트는 일부러 `set -e`를 빼고 `set -uo pipefail`만 걸어뒀습니다. **실패가 정상 결과**이기 때문입니다 — `Permission denied`가 곧 샌드박스가 작동한다는 증거니까요. 그런데 다음 줄에서 `source tools/env.sh`를 하는 순간 `set -e`가 다시 켜집니다. sourced 파일의 `set`은 호출한 셸에 그대로 적용됩니다.

그래서 첫 `Permission denied`에서 스크립트 전체가 죽었습니다.

고칠 때 호출부에 `set +e`를 붙이는 대신 원인 쪽을 건드렸습니다. `env.sh`는 변수만 내보내는 파일이므로 `set` 선언을 지웠고, 실행 스크립트들은 이미 각자 자기 옵션을 첫 줄에서 선언하고 있어 영향이 없었습니다. 덕분에 jadx/apktool이 경고만으로도 non-zero로 끝나서 `set -u`만 걸어둔 정적 분석 스크립트에서 같은 버그가 터질 예정이었던 것도 함께 막혔습니다.

수정 후 재실행하면 16개 항목이 전부 수집되고 두 개만 `exit=1`로 남습니다. 그 두 개의 실패가 이번 구간의 핵심 증거입니다.

---

## 6. 분석당할 앱 만들기

3~4주차 과제는 테스트 앱 작성입니다. 5주차부터 이걸 분석할 거라서, **찾아낼 거리가 있는 앱**으로 만들었습니다.

`kr.wtcy.memovault` — 로그인, 메모 목록/작성/상세, 공지 WebView, 첨부 파일 업로드. 서버는 파이썬 표준 라이브러리만 쓴 단일 파일 테스트 더블입니다.

의존성은 최소로 했습니다. JSON은 내장 `org.json`, 네트워크는 `HttpURLConnection`, 스레딩은 `Executors`. 코루틴도 Retrofit도 안 썼는데 취향 문제가 아니라 **jadx로 열었을 때 생성 코드가 적어야 내가 쓴 로직이 보이기 때문**입니다.

현실적인 실수 패턴 10개를 심었습니다. exported 컴포넌트, 평문 토큰 저장, 로그 유출, cleartext HTTP, `allowBackup`, WebView JS 브릿지, 하드코딩 키, 클라이언트 측 인가, 그리고 업로드를 붙이며 생긴 두 개.

빌드하고 설치해서 실제로 도는지 확인했습니다.

```
POST /login  -> 200
GET  /memos  -> 200
POST /upload -> 201
```

![MemoVault 로그인 화면. 에뮬레이터 sec-api33에서 실행 중이며 아이디·비밀번호 입력란과 로그인 버튼, 하단에 접속 서버 주소 http://10.0.2.2:8099가 표시돼 있다](/assets/img/android-security-study/01-login.png)

로그인 후 메모 목록입니다. 여기서 한 가지가 바로 눈에 띕니다.

![메모 목록 화면. 상단에 "사용자: alice"로 로그인돼 있는데 목록에는 alice의 메모(장보기, 스터디 메모)뿐 아니라 bob의 메모(회의 요약, 비밀 메모)까지 함께 나열돼 있다](/assets/img/android-security-study/02-memo-list.png)

`alice`로 로그인했는데 `bob`의 메모까지 보입니다. 서버가 토큰 주인을 확인하지 않고 전체 목록을 내려주기 때문입니다. 일부러 남겨둔 인가 결함이고, 앱의 클라이언트 측 인가 문제와 짝을 이룹니다.

```
D MemoVault: submit credentials u=alice p=alice123 key=mv_live_7c1f9a3e...
```

첫 줄에서 비밀번호와 API 키가 그대로 logcat에 찍힙니다. 심어둔 대로입니다.

3~4주차 과제에 있던 파일 업로드도 붙였습니다. 메모 상세에서 첨부를 올리면 서버 저장 이름과 로컬 사본 경로가 함께 표시됩니다.

![메모 상세 화면에서 첨부 파일 업로드 버튼을 누른 결과. "업로드 완료: 0001-memo-1786235238359.txt (29 bytes)"와 로컬 사본 경로가 표시돼 있다](/assets/img/android-security-study/03-attach-upload.png)

---

## 7. 통과하는 테스트가 버그를 덮고 있었다

앱을 붙여보니 로그인이 401로 떨어졌습니다. 서버는 로그인 응답에 `is_admin`을 내려주는데 앱은 이렇게 읽고 있었습니다.

```kotlin
o.optBoolean("isAdmin", false)     // 서버는 is_admin 으로 보낸다
```

그리고 단위 테스트는 이렇게 쓰여 있었습니다.

```kotlin
ApiClient.parseLogin("""{"token":"tok","user":"alice","isAdmin":true}""")
```

**테스트가 코드와 같은 오타를 쓰고 있어서 초록불이 떴습니다.** 서버가 실제로 무엇을 보내는지 확인하지 않고 자기 자신을 검증한 셈입니다. 결과적으로 서버 경로로는 관리자 플래그가 영원히 false여서, 심어둔 클라이언트 측 인가 취약점이 반쪽짜리가 되어 있었습니다.

테스트를 서버가 실제로 보내는 페이로드 기준으로 다시 썼습니다. 통과 여부보다 **무엇을 기준으로 통과했는지**를 봐야 한다는 걸 실물로 확인했습니다.

---

## 8. 심각도를 낮춰 적어야 했던 항목

업로드한 첨부의 로컬 사본을 `getExternalFilesDir()` 아래 남기도록 만들어 놓고, "외부 저장소니까 다른 앱이 읽겠지"라고 생각했습니다. 확인해보니 읽히긴 했습니다.

```
$ adb shell cat /storage/emulated/0/Android/data/kr.wtcy.memovault/files/attachments/memo-*.txt
우유, 계란, 커피 원두
```

그런데 디렉터리 권한이 이랬습니다.

```
drwxrws--- 2 u0_a175 ext_data_rw 4096 .
```

그룹이 `ext_data_rw`입니다. `adb shell`이 읽을 수 있었던 건 shell이 마침 그 그룹에 속해 있어서였습니다.

```
$ adb shell id
... 1015(sdcard_rw),1028(sdcard_r),1078(ext_data_rw) ...
```

일반 앱은 이 그룹이 아닙니다. Scoped storage 이후 `Android/data/<pkg>/`는 다른 앱에서 접근이 막힙니다. 그러니 정확한 영향은 "다른 앱이 훔쳐본다"가 아니라 **"앱 샌드박스 바깥 볼륨에 평문으로 남아서 adb·백업·파일관리 권한을 가진 주체에게 노출된다"**입니다. 대조군으로 앱 전용 `shared_prefs`는 같은 shell로도 `Permission denied`였습니다.

한 단계 낮춰 적는 게 맞았습니다. 관측 결과가 있어도 **왜 그렇게 나왔는지**를 확인하지 않으면 결론이 틀어집니다.

---

## 9. 샌드박스는 안 뚫렸는데 데이터는 나갔다

가장 흥미로웠던 확인입니다. 메모 상세 화면이 `exported="true"`이고, 첨부할 파일 경로를 인텐트 extra로 그대로 받습니다. 외부에서 인텐트 하나 던지면:

```bash
adb shell am start -n kr.wtcy.memovault/.MemoDetailActivity \
  --es memo_id 1 \
  --es attach_path /data/data/kr.wtcy.memovault/shared_prefs/session.xml
```

서버에 `session.xml`이 올라왔습니다. 앱 화면이 그 결과를 그대로 보여줍니다.

![메모 상세 화면 하단에 "업로드 완료: 0002-session.xml (213 bytes)"와 로컬 사본 경로가 표시돼 있다. 외부 인텐트로 지정한 앱 내부 세션 파일이 서버로 전송된 결과](/assets/img/android-security-study/04-exfil-session.png)

올라간 파일 내용은 이렇습니다.

```xml
<string name="auth_token">mvt_alice_0001</string>
<string name="username">alice</string>
```

공격자 입장에서 `/data/data/kr.wtcy.memovault/`는 직접 못 읽습니다. 2장에서 확인한 그대로입니다. 그런데 **피해 앱에게 대신 읽어달라고 시킬 수는 있습니다.** 샌드박스는 뚫리지 않았고, 앱이 자기 권한을 남에게 빌려준 것입니다.

exported 컴포넌트가 왜 위험한지를 문장이 아니라 파일 하나로 확인했습니다.

---

## 10. 4주차 도달 상태

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~2주 | Android 구조 정리 | 완료 |
| 3~4주 | 테스트 앱 작성 | 완료 (빌드·설치·종단 동작 확인) |
| 5~6주 | 정적 분석 | 다음 |

로드맵에 적어둔 "다음 단계 판단 기준" 중 지금 충족한 건 재현성 항목 하나입니다. 스냅샷·빌드 지문·요청 로그로 실험을 되돌릴 수 있습니다. 나머지는 5주차 이후 항목이라 아직입니다.

심어둔 약점 10개 중 실제로 눌러본 건 4개입니다. 나머지는 소스와 매니페스트에서만 확인했고, 5~6주차에 정적 분석으로 전부 표로 만든 뒤 하나씩 동적으로 밟을 예정입니다. `sec-api36`에서 같은 절차를 돌려 API 레벨 차이를 비교하는 것도 남아 있습니다.

---

## 남은 기록

이번 구간에서 반복해서 나온 패턴이 하나 있습니다. **출력은 맞는데 해석이 틀리는 경우**입니다.

DEX 개수를 앞부분만 보고 셌고, `am kill`이 동작했다고 가정했고, 외부 저장소를 과대평가했고, 테스트가 통과했다고 코드가 맞다고 봤습니다. 네 번 다 도구는 정직했고 제가 잘못 읽었습니다.

로드맵에 "도구 결과는 결론이 아니다"라고 적어둔 게 추상적인 원칙인 줄 알았는데, 4주 만에 네 번 걸렸습니다. 다음 구간에서는 관측할 때마다 "이 출력이 다르게 해석될 여지가 있나"를 한 번씩 붙여볼 생각입니다.
