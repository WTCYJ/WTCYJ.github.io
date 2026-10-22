---
layout: post
title: "저장소·로그·클립보드·백업 점검 — 토큰이 앱 밖으로 나가는 길"
date: 2026-10-28 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, SharedPreferences, SQLite, Logcat, Clipboard, AutoBackup, FBE]
excerpt: "Android 13 에뮬레이터에서 자작 앱의 가짜 토큰을 shared_prefs, SQLite WAL 파일, logcat, 클립보드, 백업에서 차례로 꺼냈다. targetSdk 33 앱의 adb backup은 allowBackup 대신 debuggable을 보고 두 종류의 제외 규칙 파일을 모두 무시했고, 화면을 다시 잠가도 CE 저장소는 열린 채였다."
---

[지난 글](/posts/android-lab-p1c12-network-security-config/)은 앱이 네트워크로 내보내는 트래픽을 어디서 믿고 어디서 끊는지 봤다. 이번에는 기기 안에 남는 쪽이다. 로그인한 앱은 토큰을 어딘가에 저장하고, 디버그 로그에 찍고, 가끔은 클립보드에 올리고, 백업으로 기기 밖에 내보낸다. 각 경로에서 누가 그 값을 읽을 수 있는지를 직접 꺼내 보며 확인했다.

기기는 Android 13(API 33) x86_64 google_apis userdebug 에뮬레이터(`TE1A.240213.009`)이고 SELinux는 Enforcing, 암호화는 `ro.crypto.type=file`이다. 플랫폼 소스는 `android-13.0.0_r84` 태그에서 읽었다. 명령에 나오는 `$S`는 에뮬레이터 시리얼이다. `run-as`, logcat, adb backup의 기초는 [adb 증적 수집 글](/posts/android-lab-p1c02-adb-evidence-collection/)에서 다뤘고, UID 샌드박스와 FBE 개념은 Atlas [C09](/posts/android-concept-atlas-c09-uid-sandbox/), [C43](/posts/android-concept-atlas-c43-fbe-direct-boot/), [C44](/posts/android-concept-atlas-c44-secure-storage-backup/)에 있다.

## 같은 소스로 빌드한 피해 앱과 엿보는 앱

피해 앱은 `LeakActivity` 하나짜리 Java 앱이다. `onCreate`마다 많은 앱이 하는 방식으로 세션을 남긴다. `shared_prefs/auth.xml`에 이메일, 액세스 토큰, 리프레시 토큰을 쓰고, WAL 모드 SQLite `app.db`의 `session` 테이블에 같은 토큰을 한 줄 넣는다. 앱 전역 Room 인스턴스처럼 DB는 프로세스가 살아 있는 동안 닫지 않는다. 토큰은 `{"alg":"HS256"}.{"sub":"alice"}.seika-lab`을 base64로 만든 실습용 가짜 값이라 화면에 그대로 둔다.

로그와 클립보드 부분은 아래와 같다(`LeakActivity.java` 78~100행 발췌, 끝에서 두 번째 줄이 화면에 `(IS_SENSITIVE)`를 찍는다).

```java
            String tok = sp.getString("access_token", null);
            if (safe) {
                Log.d(TAG, "login ok");
            } else {
                Log.d(TAG, "login ok user=" + USER);
                Log.d(TAG, "GET https://api.seika.test/v1/me Authorization: Bearer " + tok);
                // println also lands in logcat (tag System.out); an R8 rule on android.util.Log does not touch it
                System.out.println("refresh ok rt=" + sp.getString("refresh_token", null));
            }
            out.append("log    tag " + TAG + "\n");

            String copy = getIntent().getStringExtra("copy");
            if (copy != null) {
                ClipData clip = ClipData.newPlainText("access_token", ACCESS);
                boolean sensitive = safe || "sensitive".equals(copy);
                if (sensitive) {
                    PersistableBundle extras = new PersistableBundle();
                    extras.putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true);
                    clip.getDescription().setExtras(extras);
                }
                ((ClipboardManager) getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(clip);
                out.append("clip   access_token copied" + (sensitive ? " (IS_SENSITIVE)" : "") + "\n");
            }
```

소스는 하나이고 매니페스트만 바꿔 패키지를 여러 벌 만들었다. 백업 실험에서는 debuggable, allowBackup, targetSdk의 조합이 결과를 가르므로 표로 둔다.

| 패키지 | debuggable | allowBackup | targetSdk | 비고 |
|---|---|---|---|---|
| `io.seika.leak` | true | true | 33 | 기본 취약 버전 |
| `io.seika.leak.rel` | false | true | 33 | |
| `io.seika.leak.t30` | false | true | 30 | |
| `io.seika.leak.nobk` | true | false | 33 | |
| `io.seika.leak.t30nobk` | false | false | 30 | |
| `io.seika.leak.rules` | true | true | 33 | 두 종류의 제외 규칙 XML |
| `io.seika.leak.safe` | false | false | 33 | Keystore 래핑, 로그·클립 방어 |
| `io.seika.leak.r8` | false | true | 33 | R8로 Log 호출 제거 |

`safe` 빌드는 토큰을 AndroidKeyStore의 비추출 AES-256-GCM 키로 감싸 `v1:<iv>:<암호문>` 형태로 저장하고, 로그에는 `login ok`만 남기고, 복사할 때 항상 `EXTRA_IS_SENSITIVE`를 붙인다. 에뮬레이터의 Keystore는 소프트웨어 구현이라 TEE가 없다. 래핑 동작은 같지만 하드웨어 보호까지 본 것은 아니다. Keystore 자체는 다음 글에서 다룬다.

다른 서명키로 서명한 `io.seika.peek`(라벨 Peek)은 공격자 역할이다. 피해 앱의 파일을 직접 열어 보고, 클립보드를 `onCreate`에서 한 번, 창이 포커스를 얻은 뒤(`onWindowFocusChanged(true)`) 한 번 읽는다. 백그라운드 읽기용으로 exported 리시버 `ClipReceiver`도 있다.

## /data/data는 셸도, 다른 앱도 못 연다

`adb unroot`로 셸 권한에서 시작했다.

![터미널. adb unroot 후 shell id 는 uid=2000(shell) context=u:r:shell:s0, ls /data/data/io.seika.leak 는 Permission denied. run-as io.seika.leak ls -l 에서 app.db -rw-rw---- 4096, app.db-shm -rw------- 32768, app.db-wal -rw------- 32992, auth.xml -rw-rw---- 284. run-as cat shared_prefs/auth.xml 에 access_token eyJhbGciOiJIUzI1NiJ9..., refresh_token rt_9f3a7c21d4e8b6a0, user_email alice@seika.test 평문(실습용 가짜 값). run-as io.seika.leak.rel 은 package not debuggable. Peek(uid=10188)의 파일 읽기는 둘 다 ENOENT, list 는 null](/assets/img/android-mastery/p1c13/04-runas-prefs.png)

셸 사용자(uid 2000)는 `/data/data/io.seika.leak`을 나열조차 못 한다. 앱 홈 디렉터리는 installd가 targetSdk 24 이상이면 0700으로 만든다([`InstalldNativeService.cpp:706`](https://android.googlesource.com/platform/frameworks/native/+/refs/tags/android-13.0.0_r84/cmds/installd/InstalldNativeService.cpp#706), 그 아래 targetSdk는 0751). 여기에 SELinux MLS 카테고리가 한 겹 더 있다. 그래서 셸에서 이 디렉터리를 여는 길은 root이거나 `run-as`인데, `run-as`는 debuggable 패키지에만 동작한다. `io.seika.leak.rel`에 대해 찍힌 `package not debuggable`은 [`run-as.cpp:231`](https://android.googlesource.com/platform/system/core/+/refs/tags/android-13.0.0_r84/run-as/run-as.cpp#231)의 메시지 그대로다. 셸에서 `adb pull /data/data/...`이 실패하는 이유도 같다. 디버그 빌드라면 `adb exec-out run-as <패키지> cat <파일>`로 꺼내면 된다.

`auth.xml`은 그냥 텍스트 XML이다. Android 12부터 시스템 쪽 XML 상당수가 바이너리 ABX로 바뀌었지만 앱의 SharedPreferences는 [`SharedPreferencesImpl.java:803`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/SharedPreferencesImpl.java#803)에서 `XmlUtils.writeMapXml`로 텍스트 직렬화를 거친다. 모드 `-rw-rw----`(0660)는 `MODE_PRIVATE`가 그룹 읽기·쓰기까지 주기 때문이다([`ContextImpl.java:3311`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ContextImpl.java#3311)).

예상과 다른 값이 하나 있었다. SQLite 빌드 옵션이 `SQLITE_DEFAULT_FILE_PERMISSIONS=0600`([`Android.bp:67`](https://android.googlesource.com/platform/external/sqlite/+/refs/tags/android-13.0.0_r84/dist/Android.bp#67))이라 `app.db`도 0600일 줄 알았는데 실제로는 `-rw-rw----`였고 `-wal`과 `-shm`만 0600이었다. 앱은 DB를 `SQLiteOpenHelper`로 여는데, 이 클래스가 DB를 연 뒤([375행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/database/sqlite/SQLiteOpenHelper.java#375)) `setFilePermissionsForDb`로 메인 파일 경로에만 0660을 입힌다([`SQLiteOpenHelper.java:443-445`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/database/sqlite/SQLiteOpenHelper.java#443), 주석은 "Keep pre-O-MR1 behavior"). `-wal`과 `-shm`은 그 호출 밖이라 SQLite 기본값 0600이 남는다. 그룹은 앱 자신의 UID 그룹이라 다른 앱이 읽게 되지는 않는다.

다른 앱이 직접 열면 어떻게 될까. 처음에는 `EACCES (Permission denied)`를 예상했다. Peek은 `ENOENT (No such file or directory)`를 받았고 디렉터리 목록은 `null`이었다. 권한 거부 대신 아예 없는 파일로 보인다는 뜻이라 Peek 프로세스의 마운트 네임스페이스를 들여다봤다.

![터미널. root 셸에서 ls /data/data 에는 io.seika.leak 부터 io.seika.peek 까지 아홉 개 디렉터리가 보이지만, Peek pid 5739 의 /proc/5739/root/data/data 에는 com.google.android.gms 와 io.seika.peek 둘만 있다. mountinfo 에서 /data/data 와 /data/user 가 tmpfs mode=751 로 마운트되고 /data/io.seika.peek 과 /data/com.google.android.gms 만 bind mount 되어 있다](/assets/img/android-mastery/p1c13/04b-peek-mount-ns.png)

전역 네임스페이스에는 `io.seika.*` 디렉터리가 모두 있지만 Peek이 보는 `/data/data`와 `/data/user`는 `mode=751`짜리 tmpfs이고, 그 안에는 Peek 자신과 GMS의 디렉터리만 bind mount돼 있다. Android 11에서 들어온 앱 데이터 격리가 이 이미지에서 기본값으로 켜져 있다. 그래서 다른 앱에게 피해 앱의 디렉터리는 아예 없는 것으로 보이고, 0700 퍼미션과 SELinux MLS 검사는 이 격리를 넘은 뒤에야 작동한다.

## DB를 꺼낼 때는 -wal까지 가져와야 한다

WAL 모드로 연 DB를 `.db` 파일 하나만 pull해서 열어 봤다. Room의 기본값 `JournalMode.AUTOMATIC`도 저메모리 기기가 아니면 WAL을 쓴다([RoomDatabase.Builder](https://developer.android.com/reference/kotlin/androidx/room/RoomDatabase.Builder)).

![터미널. 기기의 databases 에 app.db 4096, app.db-shm 32768, app.db-wal 32992. adb pull 로 app.db 만 받은 app-only.db 에 sqlite3 select 를 하면 Error: in prepare, no such table: session. 디렉터리째 pull 하면 3 files pulled 69856 bytes, grep -ac eyJhbGci 결과 app-only.db:0, db-full/app.db-wal:1. db-full/app.db 를 sqlite3 로 조회하면 alice@seika.test 와 토큰이 나오고, 그 뒤 wc -c 에는 16384 db-full/app.db 하나만 남는다](/assets/img/android-mastery/p1c13/05-wal-pull.png)

`app.db` 하나만 받으면 `no such table: session`이 나온다. 테이블 생성과 행 삽입이 아직 `app.db-wal`에만 있고 메인 파일로 체크포인트되지 않았기 때문이다. `grep`으로 봐도 토큰 문자열은 메인 파일에 0번, `-wal`에 1번 있다. 프레임워크의 자동 체크포인트 기준은 100페이지이고([`config.xml:2340`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/res/res/values/config.xml#2340)), 마지막 연결이 닫힐 때도 체크포인트가 일어난다. 앱이 DB를 열어 둔 채 쓰기가 적은 상태라면 최근 데이터는 계속 `-wal`에 머문다.

캡처의 pull은 `adb root`로 root가 된 뒤 databases 디렉터리를 통째로 받은 것이다. root가 없으면 앞 절처럼 debuggable 앱에 한해 `adb exec-out run-as <패키지> cat databases/app.db-wal > app.db-wal` 식으로 세 파일을 하나씩 꺼내야 한다. 디렉터리째 받은 사본은 잘 열린다. 마지막 `wc -c`를 보면 조회를 마친 sqlite3가 연결을 닫으면서 증거 사본을 체크포인트했고, `-wal`과 `-shm`이 사라지면서 `app.db`가 4096에서 16384바이트로 커졌다. 그러니 분석용으로 열기 전에 원본 사본을 따로 떠 두는 편이 좋다.

기기 쪽 sqlite3는 이 userdebug 이미지에 `/system/bin/sqlite3`로 있다. AOSP는 sqlite3를 `PRODUCT_PACKAGES_DEBUG`에 넣어 eng·userdebug 빌드에만 싣는다([`base_system.mk:389`](https://android.googlesource.com/platform/build/+/refs/tags/android-13.0.0_r84/target/product/base_system.mk#389), 372행에서 시작하는 목록). 같은 빌드 ID(`TE1A.240213.009`)의 user 빌드 에뮬레이터를 따로 띄워 보니 `adb root`는 `adbd cannot run as root in production builds`로 거부됐고 `/system/bin/sqlite3`와 `/system/xbin/sqlite3`가 둘 다 없었다. OEM 빌드는 또 다를 수 있으니, 호스트로 꺼내 여는 방식을 기본으로 두는 편이 낫다.

## debuggable=false는 Log.d를 지우지 않는다

같은 소스를 debuggable 빌드(`leak`), 릴리스 빌드(`rel`), R8을 거친 릴리스 빌드(`r8`), 방어 빌드(`safe`)로 띄우고 프로세스별로 로그를 걸렀다.

![터미널. logcat -c 후 네 패키지를 am start -S 로 다시 띄우고 pid 별로 LeakLab, System.out 태그를 거른 결과. io.seika.leak 과 io.seika.leak.rel 은 둘 다 D LeakLab login ok user=alice@seika.test, D LeakLab GET https://api.seika.test/v1/me Authorization: Bearer eyJ..., I System.out refresh ok rt=rt_9f3a7c21d4e8b6a0 세 줄을 남긴다. io.seika.leak.r8 은 System.out 의 refresh ok 한 줄, io.seika.leak.safe 는 D LeakLab login ok 한 줄](/assets/img/android-mastery/p1c13/06-logcat-r8.png)

`rel`은 debuggable이 false인데도 `Log.d`가 그대로 찍혔다. `Log.d`는 런타임에 디버그 여부를 보지 않는다. 릴리스에서 로그를 지우려면 빌드 단계에서 호출 자체를 없애야 하고, 공식 문서도 R8을 권한다([로그 정보 노출](https://developer.android.com/privacy-and-security/risks/log-info-disclosure)). 다만 그 문서의 예시 규칙은 메서드 시그니처 자리에 `TAG`와 문자열 리터럴을 넣어 두어서 적힌 그대로는 ProGuard 문법이 아니다. 실제로 쓴 규칙과 그 결과 dex는 이렇다.

![터미널. cat r8/log-rules.pro 에 -assumenosideeffects class android.util.Log 의 v(...), d(...), i(...) 와 io.seika.leak 패키지를 keep 하는 규칙과 -dontobfuscate. dexdump 로 d8 dex 를 grep 하면 Log;.d: 세 번, "GET https://api.seika.test/v1/me Authorization: Bearer ", "refresh ok rt=", PrintStream;.println, Log;.e: 가 나오고, R8 dex 에서는 "refresh ok rt=", PrintStream;.println, Log;.e: 만 남는다](/assets/img/android-mastery/p1c13/01-r8-dex.png)

R8은 `Log.d` 호출 세 개와 함께 Bearer 문자열 상수까지 없앴다. 메시지를 만드는 `StringBuilder` 연결도 쓰이지 않는 코드가 되어 함께 지워진 것으로 보인다. `System.out.println`과 `Log.e`는 규칙 밖이라 남았고, 기기에서도 `r8` 프로세스는 리프레시 토큰이 담긴 `System.out` 줄을 그대로 찍었다. 로그 제거 규칙을 넣은 뒤에도 `println`, `printStackTrace`, 서드파티 로거는 따로 찾아야 한다. dex에서 문자열을 grep하는 것과 별개로, 기기에서는 `adb logcat -d --pid=$(adb exec-out pidof <패키지>)`로 그 앱의 줄만 걸러 보면 된다. `safe`는 `login ok` 한 줄이었다.

logcat을 누가 읽을 수 있는지는 [adb 증적 글](/posts/android-lab-p1c02-adb-evidence-collection/)에서 측정했다. 일반 앱은 자기 UID 로그만 받는다. 일반 앱에는 `READ_LOGS`를 adb(`pm grant`)로만 줄 수 있고, Android 13에서는 그 권한을 받은 앱도 사용자 동의 대화상자를 거쳐야 다른 앱의 로그를 받는다. 그래도 USB 디버깅이 켜진 기기를 손에 쥔 사람, 버그 리포트를 받는 사람에게는 이 로그가 다 보인다.

## 클립보드에 올린 토큰은 화면에도, 포커스를 가진 앱에도 보인다

Android 13은 무언가 복사되면 화면 왼쪽 아래에 미리보기를 띄운다([복사·붙여넣기 문서](https://developer.android.com/develop/ui/views/touch-and-input/copy-paste)). 취약 빌드가 토큰을 복사했을 때와, 방어 빌드가 `EXTRA_IS_SENSITIVE`를 붙여 복사했을 때를 나란히 찍었다.

![Leak 앱 화면에 io.seika.leak, prefs shared_prefs/auth.xml, db databases/app.db rows=1, log tag LeakLab, clip access_token copied 가 표시되고, 왼쪽 아래 Android 13 복사 미리보기에 토큰 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.c2Vpa2EtbGFi 가 줄바꿈되어 그대로 보이며 옆에 공유 버튼과 기기 전송 버튼이 있다](/assets/img/android-mastery/p1c13/07-clip-overlay.png)

![Leak-safe 앱 화면에 io.seika.leak.safe (safe) 와 clip access_token copied (IS_SENSITIVE) 가 표시되고, 왼쪽 아래 복사 미리보기에는 토큰 대신 점 여섯 개가 보인다](/assets/img/android-mastery/p1c13/08-clip-overlay-sensitive.png)

플래그를 붙이면 미리보기가 점으로 가려진다. SystemUI의 [`ClipboardOverlayController.java:405-424`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/packages/SystemUI/src/com/android/systemui/clipboardoverlay/ClipboardOverlayController.java#405)가 이 플래그를 보고 미리보기 텍스트를 `clipboard_asterisks` 리소스(화면에서는 점 여섯 개)로 바꾼다. 이 플래그가 다른 앱의 읽기까지 막는지 보려고, 방어 빌드가 이렇게 복사한 상태에서 Peek으로 클립보드를 읽어 봤다.

![터미널. am broadcast 로 ClipReceiver 를 깨우면 E ClipboardService Denying clipboard access to io.seika.peek, application is not in focus nor is it a system service for user 0 과 PEEK background getPrimaryClip -> null. am start -S 로 PeekActivity 를 띄우면 onCreate 읽기에서 같은 Denying 줄과 null, 이어서 I ClipboardService Peek pasted from your clipboard 와 PEEK focused getPrimaryClip -> "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.c2Vpa2EtbGFi"](/assets/img/android-mastery/p1c13/09-clip-read.png)

리시버에서 읽은 것과 `onCreate`에서 읽은 것은 `null`이었고, 서버 쪽에는 `Denying clipboard access` 오류가 남았다. 창이 포커스를 얻은 뒤 읽은 값은 `IS_SENSITIVE`가 붙은 클립인데도 토큰 전체였다. 규칙은 [`ClipboardService.java:1063-1113`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/clipboard/ClipboardService.java#1063)에 있다. 읽기·쓰기 분기 앞에서 `READ_CLIPBOARD_IN_BACKGROUND` 권한을 가진 호출자(소스 주석대로 테스트용 셸 등)와 기본 IME를 먼저 통과시킨다. 그 밖의 앱에게 읽기(`OP_READ_CLIPBOARD`)는 창 포커스를 가진 경우(`mWm.isUidFocused(uid)` 또는 포커스를 가진 내부 시스템 창)와 콘텐츠 캡처, 증강 자동완성 서비스에만 허용되고, 쓰기는 주석대로 "Writing is allowed without focus"다.

![ClipboardService.java android-13.0.0_r84 1063~1113행. READ_CLIPBOARD_IN_BACKGROUND 권한 또는 isDefaultIme 이면 허용, OP_READ_CLIPBOARD 에서는 mWm.isUidFocused(uid) 또는 isInternalSysWindowAppWithWindowFocus, 이어서 콘텐츠 캡처와 증강 자동완성 서비스 검사, OP_WRITE_CLIPBOARD 는 Writing is allowed without focus 로 allowed = true, 거부 시 Slog.e Denying clipboard access to ... application is not in focus nor is it a system service](/assets/img/android-mastery/p1c13/03-src-clipboard-focus.png)

여기서 포커스는 창 포커스다. 액티비티가 앞에 떠 있어도 `onCreate` 시점에는 아직 포커스가 없어서 거부되고, `onWindowFocusChanged(true)` 뒤에는 통과한다. 이 제한은 Android 10에서 들어왔고([Android 10 개인정보 변경](https://developer.android.com/about/versions/10/privacy/changes)) 앱의 targetSdk와 상관없이 기기 버전을 따른다. Android 9 이하나 10~11 기기는 이번에 돌려 보지 않았다.

포커스 읽기와 같은 순간 `Peek pasted from your clipboard`라는 로그가 찍혔다. Android 12부터 다른 앱의 클립을 처음 읽으면 띄우는 토스트다([Android 12 동작 변경](https://developer.android.com/about/versions/12/behavior-changes-all)). 취약 빌드로 새로 복사한 뒤 Peek을 띄워 화면에서도 확인했다.

![Peek 앱 화면에 uid=10188 mode=clip, onCreate getPrimaryClip -> null, focused getPrimaryClip -> "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZSJ9.c2Vpa2EtbGFi" 가 찍혀 있고 아래쪽에 토스트 Peek pasted from your clipboard 가 떠 있다](/assets/img/android-mastery/p1c13/10-clip-toast.png)

토스트가 뜰 때 값은 이미 앱 손에 넘어가 있으니, 토스트는 읽기를 막는 장치로 볼 수 없다. 클립은 소스상 1시간 뒤 자동으로 비워지는데([`ClipboardService.java:110`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/clipboard/ClipboardService.java#110), 3600000ms) 이번에 한 시간을 기다려 확인하지는 않았다. 또 에뮬레이터에서는 `EmulatorClipboardMonitor`가 게스트 클립을 호스트 PC로 넘기는 경로가 소스에 있다([`ClipboardService.java:174`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/clipboard/ClipboardService.java#174), 클립을 넘기는 호출은 685행). 호스트 클립보드에 표식 문자열을 넣어 두고 기기에서 토큰을 복사한 뒤 다시 읽어 보니 표식 그대로였다. 다만 이 실습 에뮬레이터는 창 없이(`-no-window`) 띄운 것이라, 창을 띄우고 클립보드 공유를 켠 에뮬레이터에서도 그런지는 보지 않았다.

토큰 같은 값은 복사 버튼을 두지 않는 것이 가장 확실하다. 복구 코드처럼 사용자가 복사해야 하는 값이라면 `EXTRA_IS_SENSITIVE`를 붙여 어깨너머 노출만이라도 줄인다. 문서는 targetSdk와 상관없이 모든 앱이 그렇게 하라고 권한다.

## adb backup은 targetSdk에 따라 보는 플래그가 바뀐다

처음에는 adb backup이 allowBackup만 본다고 생각했다. 변형 앱마다 `adb backup -f backup/<이름>.ab <패키지>`를 걸고 기기 확인 화면에서 "Back up my data"를 눌렀다. adb는 매번 `WARNING: adb backup is deprecated and may be removed in a future release`를 먼저 찍는다. `abx.py`는 `.ab` 헤더 뒤의 zlib 스트림을 풀어 tar 목록을 보여 주고, 실습 토큰이 들어 있는 항목에 `[token]`을 붙이는 작은 스크립트다.

![터미널. wc -c backup/*.ab 결과 leak.ab 2110, nobk.ab 2130, rel.ab 47, rules.ab 2118, t30.ab 2117, t30nobk.ab 47 바이트. abx.py 목록에서 leak, nobk, t30 은 각각 5 entries 로 _manifest, db/app.db-shm, db/app.db-wal (토큰 표시), db/app.db, sp/auth.xml (토큰 표시) 을 담고, rel.ab 와 t30nobk.ab 는 0 entries](/assets/img/android-mastery/p1c13/11-adb-backup-matrix.png)

allowBackup이 false인 `nobk`가 토큰째 빠져나왔고, allowBackup이 true인 `rel`은 47바이트 빈 백업이었다. targetSdk 30으로 내리면 결과가 뒤집혀서 allowBackup이 true인 `t30`은 나오고 false인 `t30nobk`는 비었다. 둘 다 debuggable이 false인데도 그렇다. 백업 서비스 로그에도 같은 판정이 찍힌다.

![터미널. adb logcat -d -s BackupManagerService:I FullBackup:W 를 grep 한 결과. io.seika.leak, io.seika.leak.nobk, io.seika.leak.t30, io.seika.leak.rules 는 Performing full backup for package, io.seika.leak.rel 과 io.seika.leak.t30nobk 는 is not eligible for backup, removing. 마지막 줄은 W FullBackup: Given operation type isn't supported by backup scheme: 3](/assets/img/android-mastery/p1c13/11b-adb-backup-log.png)

판정 코드는 `BackupEligibilityRules.isAppBackupAllowed`다.

![BackupEligibilityRules.java android-13.0.0_r84 159~212행. MIGRATION 은 ignoreAllowBackup 또는 allowBackup 을 반환하고 ignoreAllowBackup 은 비시스템 앱에 IGNORE_ALLOW_BACKUP_IN_D2D 가 켜졌을 때 참. ADB_BACKUP 은 RESTRICT_ADB_BACKUP 이 꺼져 있으면 return allowBackup, 켜져 있으면 core 나 privileged 가 아닌 앱에 대해 주석 All other apps can use adb backup only when running in debuggable mode 와 return isDebuggable. BACKUP 은 return allowBackup](/assets/img/android-mastery/p1c13/14-src-adb-backup-gate.png)

[`BackupEligibilityRules.java:176-206`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/backup/java/com/android/server/backup/utils/BackupEligibilityRules.java#176)을 보면 `RESTRICT_ADB_BACKUP` 호환성 변경이 꺼진 앱, 곧 targetSdk 30 이하에는 `return allowBackup`이고, 켜진 앱(targetSdk 31 이상, [72행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/backup/java/com/android/server/backup/utils/BackupEligibilityRules.java#72))의 일반 앱에는 `return isDebuggable`이다. 이 분기에서는 allowBackup을 아예 읽지 않는다. Android 12 동작 변경 문서도 targetSdk 31 이상 앱의 데이터는 adb backup에서 빠지고 `android:debuggable="true"`로만 다시 넣을 수 있다고 적는다([Android 12 변경](https://developer.android.com/about/versions/12/behavior-changes-12)). 그러니 Android 12 이상 기기에서는 targetSdk 30 이하면 allowBackup이, 31 이상이면 debuggable이 게이트다. allowBackup만 false로 바꾼 디버그 빌드는 `nobk`처럼 그대로 빠져나간다.

빈 47바이트 `.ab`가 나왔다고 곧바로 "targetSdk 31+ 제한" 탓으로 돌릴 수도 없다. targetSdk 30 이하에서 allowBackup이 false인 경우에도 같은 결과가 나오고, 한 번도 실행되지 않았거나 강제 종료된 패키지는 [`PerformAdbBackupTask.java:296-297`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/backup/java/com/android/server/backup/fullbackup/PerformAdbBackupTask.java#296)에서 목록에서 빠진다. 실험 전에 모든 변형을 한 번씩 띄운 이유다. 테스터가 targetSdk 31 이상 앱의 데이터를 adb backup으로 받아야 한다면 필요한 것은 debuggable 빌드다.

## 제외 규칙은 백업 채널마다 다르게 적용된다

`rules` 빌드에는 두 종류의 규칙을 다 넣었다. `fullBackupContent`는 Android 11 이하 기기가 쓰던 옛 규칙이고, Android 12 이상에서는 `dataExtractionRules`에 해당 섹션이 없을 때 폴백으로만 읽히며, Android 12 문서는 이 옛 규칙이 D2D에는 영향을 주지 않는다고 적는다. `dataExtractionRules`는 클라우드 백업과 기기 간 전송(D2D)을 섹션으로 나눠 적는다.

```xml
<!-- res/xml/backup_rules.xml (android:fullBackupContent) -->
<full-backup-content>
    <exclude domain="sharedpref" path="auth.xml"/>
    <exclude domain="database" path="app.db"/>
</full-backup-content>

<!-- res/xml/data_extraction_rules.xml (android:dataExtractionRules) -->
<data-extraction-rules>
    <cloud-backup>
        <exclude domain="sharedpref" path="auth.xml"/>
        <exclude domain="database" path="app.db"/>
    </cloud-backup>
    <device-transfer>
        <exclude domain="database" path="app.db"/>
    </device-transfer>
</data-extraction-rules>
```

그런데 adb로 받은 `rules.ab`를 `abx.py`로 열어 보니 `sp/auth.xml [token]`과 `app.db-wal [token]`이 그대로 들어 있었다(목록은 뒤의 채널 비교 캡처 첫 칸에 다시 나온다). 규칙이 하나도 적용되지 않은 것이다. 앞의 백업 서비스 로그 캡처 마지막 줄 `Given operation type isn't supported by backup scheme: 3`이 그때 남은 것이다.

![FullBackup.java android-13.0.0_r84 579~627행. parseSchemeForOperationType 은 getConfigSectionForOperationType 이 null 이면 Slog.w Given operation type isn't supported by backup scheme 후 return, 이어서 mDataExtractionRules 섹션, MIGRATION 과 IGNORE_FULL_BACKUP_CONTENT_IN_D2D, mFullBackupContent 폴백 순. getConfigSectionForOperationType 은 BACKUP 이면 CLOUD_BACKUP, MIGRATION 이면 DEVICE_TRANSFER, default null](/assets/img/android-mastery/p1c13/02-src-fullbackup-section.png)

[`FullBackup.java:579-627`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/backup/FullBackup.java#579)은 백업 종류(operation type)로 규칙 섹션을 고른다. `BACKUP`은 `cloud-backup`, `MIGRATION`은 `device-transfer`이고 나머지는 `null`이다. adb backup의 `ADB_BACKUP`(3)은 `null`을 받아 경고를 남기고 바로 반환하므로 include도 exclude도 없이 앱 데이터 전체가 나간다. 이 분기는 `fullBackupContent` 폴백보다 앞에 있어서 옛 규칙 파일도 읽히지 않는다.

클라우드와 D2D는 Google Drive나 GMS 전송 없이 AOSP의 LocalTransport로 대신했다. 이 이미지는 GMS 백업 전송이 선택돼 있었는데, 계정으로 업로드되지 않도록 LocalTransport로 바꿨다. LocalTransport는 `backup_local_transport_parameters`에 `is_device_transfer=true`를 주면 자신을 D2D 전송으로 보고하고, 그러면 백업은 `MIGRATION`으로 돈다([`LocalTransportParameters.java:30`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/packages/LocalTransport/src/com/android/localtransport/LocalTransportParameters.java#30)의 `KEY_IS_DEVICE_TRANSFER`, [`LocalTransport.java:167-168`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/packages/LocalTransport/src/com/android/localtransport/LocalTransport.java#167)의 `FLAG_DEVICE_TO_DEVICE_TRANSFER`). 공식 [테스트 문서](https://developer.android.com/identity/data/testingbackup)는 D2D를 `backup_enable_d2d_test_mode`와 GMS의 D2D 전송으로 시험하는데, 이번에는 그 길을 쓰지 않았다. 실제 GMS 전송이 이것과 똑같이 동작하는지는 확인하지 않았다. 실행한 명령은 이렇다.

```bash
adb -s $S root
adb -s $S exec-out bmgr enable true
adb -s $S exec-out bmgr transport com.android.localtransport/.LocalTransport
mkdir -p transport/cloud transport/d2d

# 클라우드 백업: 파라미터를 지우고, 이전 tarball을 비운 뒤 백업
adb -s $S exec-out settings delete secure backup_local_transport_parameters
sleep 2
adb -s $S exec-out "rm -f /data/data/com.android.localtransport/files/1/_full/*"
adb -s $S exec-out bmgr backupnow io.seika.leak io.seika.leak.rules io.seika.leak.safe | tee transport/cloud/bmgr.txt
adb -s $S exec-out cat /data/data/com.android.localtransport/files/1/_full/io.seika.leak.rules > transport/cloud/io.seika.leak.rules

# D2D: is_device_transfer=true 로 바꾸고 같은 순서를 반복
adb -s $S exec-out settings put secure backup_local_transport_parameters is_device_transfer=true
sleep 2
adb -s $S exec-out "rm -f /data/data/com.android.localtransport/files/1/_full/*"
adb -s $S exec-out bmgr backupnow io.seika.leak io.seika.leak.rules io.seika.leak.safe | tee transport/d2d/bmgr.txt
adb -s $S exec-out cat /data/data/com.android.localtransport/files/1/_full/io.seika.leak.rules > transport/d2d/io.seika.leak.rules
adb -s $S exec-out cat /data/data/com.android.localtransport/files/1/_full/io.seika.leak.safe > transport/d2d/io.seika.leak.safe

# 끝나면 파라미터를 지워 둔다
adb -s $S exec-out settings delete secure backup_local_transport_parameters
```

패키지별 tarball은 `_full/<패키지>`에 생기고 다음 백업에서 덮어쓰이지 않은 파일이 남을 수 있어서, 매번 디렉터리를 비우고 시작했다.

![터미널. grep with result 결과 클라우드에서 io.seika.leak.safe 는 Backup is not allowed, io.seika.leak 과 io.seika.leak.rules 는 Success. D2D 에서는 leak, rules, safe 모두 Success. abx.py 목록에서 adb 로 받은 rules.ab 는 5 entries 에 db/app.db-wal (토큰 표시) 과 sp/auth.xml (토큰 표시), 클라우드 io.seika.leak.rules 는 _manifest 와 db/app.db-shm 2 entries, D2D io.seika.leak.rules 는 _manifest, db/app.db-shm, sp/auth.xml (토큰 표시) 3 entries, D2D io.seika.leak.safe 는 5 entries 로 db/app.db-wal 과 sp/auth.xml 에 (v1 암호문 표시) 표시](/assets/img/android-mastery/p1c13/12-rules-three-ways.png)

같은 `rules` 앱이 채널마다 다른 내용을 내보냈다. adb로는 전부, 클라우드로는 `_manifest`와 `app.db-shm`만, D2D로는 `device-transfer` 섹션이 DB만 막으니 토큰이 든 `auth.xml`이 따라갔다. `database` 제외가 `app.db-wal`과 `-journal`까지 함께 지우는 것은 [`FullBackup.java:747-768`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/backup/FullBackup.java#747)이 경로를 자동으로 덧붙이기 때문이고, `-shm`은 그 목록에 없어서 남았다. 그래서 규칙을 바꾼 뒤에는 adb backup, LocalTransport 클라우드, LocalTransport D2D로 각각 떠서 목록에 토큰 파일과 `-shm` 같은 부속 파일이 없는지 본다.

allowBackup이 false인 `safe`는 클라우드에서 `Backup is not allowed`였지만 D2D에서는 `Success`로 다섯 항목이 다 나갔다. 위 소스 캡처의 `MIGRATION` 분기에서 비시스템 앱은 `IGNORE_ALLOW_BACKUP_IN_D2D`가 켜지면(targetSdk 31 이상) allowBackup을 무시한다. 다만 이것은 재정의 가능한 호환성 변경이고, Android 12 문서도 "일부 제조사 기기에서" allowBackup=false가 Drive 백업은 막되 D2D는 막지 않는다고 적는다. AOSP 13인 이 에뮬레이터에서는 그렇게 동작했다고까지만 말할 수 있다.

`safe`의 D2D 사본에서 토큰은 `v1:` 암호문뿐이었다. 키는 앱 디렉터리 밖, keystore2가 관리하는 `/data/misc/keystore/persistent.sqlite`(이번 기기에서 122880바이트, 소유자 `keystore`)에 있어서 백업에 실리지 않는다. 새 기기로 옮겨진 암호문은 그쪽에서 풀 수 없으니 앱은 재로그인 흐름을 갖춰야 한다. 그리고 방어 빌드도 `user_email`은 평문으로 남겼고, D2D 사본에도 그 값이 그대로 실렸다.

## FBE는 첫 잠금해제 전까지만 지킨다

이 이미지는 파일 기반 암호화(FBE)다. 사용자 데이터는 잠금해제 후에만 쓸 수 있는 CE 저장소에 있다([FBE 문서](https://source.android.com/docs/security/features/encryption/file-based)). PIN을 걸고(`locksettings set-pin 1234`) 재부팅한 뒤 첫 잠금해제 전(BFU)부터 root로 들여다봤다.

![터미널. ro.crypto.type 은 file, am get-started-user-state 0 은 RUNNING_LOCKED. ls /data/user/0 의 이름은 --ABAEgAQALFWR8Junr... 같은 암호화된 이름이고 ls /data/user_de/0 에는 io.seika.leak 등 패키지 이름이 평문으로 보인다. cat auth.xml 은 No such file or directory. wm dismiss-keyguard, input text 1234, keyevent 66 으로 잠금해제한 뒤 RUNNING_UNLOCKED 와 access_token 줄이 보이고, keyevent 26 으로 화면을 끈 뒤 mKeyguardShowing=true 인데도 상태는 RUNNING_UNLOCKED 이고 access_token 이 그대로 읽힌다](/assets/img/android-mastery/p1c13/13-fbe-bfu.png)

BFU에서는 root도 CE 저장소의 이름을 암호화된 문자열로만 보고 `auth.xml`은 없는 파일이다. 같은 시점에 기기 보호(DE) 저장소인 `/data/user_de/0`의 패키지 이름은 평문이다. PIN을 넣은 뒤로는 상태가 `RUNNING_UNLOCKED`가 되고 토큰이 읽힌다. 전원 버튼으로 화면을 끄고 키가드가 다시 떠도(`mKeyguardShowing=true`) 상태는 그대로이고 토큰도 그대로 읽혔다.

화면 잠금으로는 CE 키가 내려가지 않는다. 키를 지우는 `dispatchUserLocking` → `lockUserKey`는 [`UserController.java:1207-1222`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/UserController.java#1207)에 있고, 이를 부르는 곳은 사용자 중지 경로(1012행, 1199행)뿐이다. vold 쪽 `evict_ce_key`도 [`fscrypt_lock_user_key`(FsCrypt.cpp:781-785)](https://android.googlesource.com/platform/system/vold/+/refs/tags/android-13.0.0_r84/FsCrypt.cpp#781)와 사용자 삭제 때의 [`fscrypt_destroy_user_key`(570행)](https://android.googlesource.com/platform/system/vold/+/refs/tags/android-13.0.0_r84/FsCrypt.cpp#570)에서만 불린다. 화면 잠금 경로는 없다. FBE가 막아 주는 상대는 꺼져 있다가 켜진 기기, 곧 BFU 상태의 기기를 손에 넣은 사람이다. 한 번이라도 잠금해제된 기기에서 root를 얻은 공격자나 실행 중인 앱에게 CE 저장소는 평문이다.

그래서 `safe` 빌드는 토큰을 Keystore 키로 감쌌고, 그 빌드의 `auth.xml`에는 `access_token`과 `refresh_token`이 `v1:rMmytQ4V/rWklyVI:zlQSV4sZ...` 같은 암호문으로만 남았다. 예전에 많이 쓰던 Jetpack EncryptedSharedPreferences는 security-crypto 1.1.0-alpha07(2025-04-09)에서 모든 API가 deprecated됐고, 릴리스 노트는 플랫폼 API와 Android Keystore를 직접 쓰라고 안내한다([릴리스 노트](https://developer.android.com/jetpack/androidx/releases/security)).

*다음 글: [Keystore와 BiometricPrompt 검증](/posts/android-lab-p1c14-keystore-biometricprompt/)*
