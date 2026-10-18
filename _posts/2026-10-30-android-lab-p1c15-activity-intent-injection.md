---
layout: post
title: "Activity·Intent 주입 실습 — 중첩 Intent가 exported 경계를 넘는 길"
date: 2026-10-30 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Activity, Intent, IntentRedirection, ConfusedDeputy, StrictMode, Android16]
excerpt: "Android 13 에뮬레이터에서 권한 없는 앱이 피해자의 exported 포워더에 Intent를 담아 보내자 피해자 UID로 exported=false 액티비티가 열렸고, grant 플래그를 얹자 비공개 provider의 값까지 읽혔다. Android 16은 Parcelable로 담긴 Intent를 막았지만, 문자열 intent: URI와 보호를 끈 포워더, setPackage()를 덧댄 포워더는 그대로 통과했다."
---

[매니페스트 매핑](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)에서 다른 앱이 어느 컴포넌트까지 들어올 수 있는지 지도를 그렸다. 이번에는 그 지도에서 OPEN으로 찍힌 액티비티에 실제로 Intent를 밀어 넣어 본다. extra 몇 개로 관리 화면이 열리는 것부터 보고, 대부분의 시간은 받은 Intent 안에 든 또 다른 Intent를 그대로 `startActivity()`에 넘기는 액티비티에 썼다. 그런 액티비티가 하나 있으면 공격자는 피해자 앱의 UID를 빌려 `exported="false"`인 화면과 provider까지 닿는다.

실험은 두 대의 에뮬레이터에서 했다. 주 기기는 Android 13(API 33, x86_64, userdebug, 빌드 TE1A.240213.009, 보안 패치 2024-03-01)이고, Android 16의 방어를 보려고 Android 16(API 36, 빌드 BE2A.250530.026.F3, 패치 2025-07-05) 에뮬레이터를 따로 띄웠다. 루팅된 userdebug 에뮬레이터라 `adb unroot`로 셸을 uid 2000으로 돌려 놓고 시작했다. 화면에 나오는 `$S`는 에뮬레이터 시리얼이다. 소스 링크는 Android 13은 frameworks/base `android-13.0.0_r84`, Android 16은 `android-16.0.0_r1` 태그로 건다. Android 16 쪽은 측정한 BE2A.250530.026.F3와 같은 빌드가 아니고, 가장 가까운 공개 태그다.

## 피해자 앱과 공격자 앱

피해자 `io.seika.intentlab`(targetSdk 33, 디버그 키 서명)에는 일부러 문제를 심었다. `AdminActivity`는 extra의 `isAdmin` 값을 믿고 관리 화면을 띄운다. `PrivateActivity`와 `HelpActivity`는 `exported="false"`인 내부 화면이고, `SecretProvider`는 exported는 꺼져 있지만 `grantUriPermissions="true"`라 FileProvider처럼 URI grant를 받아 준다. 값은 가짜 토큰 `lab-secret-4821` 한 줄이다. 그리고 중첩 Intent를 다시 띄우는 포워더를 방식별로 여럿 두었다.

공격자 `io.seika.intentatk`는 다른 키로 서명했고 권한을 하나도 요청하지 않는다. 매니페스트에는 피해자와 InsecureShop을 볼 수 있게 `<queries>`만 넣었다. `am start -n io.seika.intentatk/.AttackActivity --es mode <모드>`로 실행하면 모드마다 다른 Intent를 만들어 보내고 결과를 `INTENTATK` 태그로 남긴다.

6장의 매퍼를 피해자 APK에 다시 돌린 결과다.

![apktool d -q -f -s -p fw -o decoded/intentlab out/intentlab.apk 후 python map_surface.py decoded/intentlab --platform aosp13-core-AndroidManifest.xml 출력. io.seika.intentlab minSdk 26 targetSdk 33, OPEN으로 MainActivity, AdminActivity, ForwardActivity, UriForwardActivity, OptOutForwardActivity, PkgForwardActivity, SafeForwardActivity가 모두 exported=true (explicit) perm: -, INTERNAL로 PrivateActivity와 HelpActivity exported=false, GUARDED ShellOnlyActivity perm: android.permission.DUMP (signature, privileged, development, platform), INTERNAL provider SecretProvider exported=false 표시 grantUriPermissions, 마지막 줄 debuggable=false allowBackup=false cleartext off](/assets/img/android-mastery/p1c15/01-host-map-lab.png)

지도는 OPEN 일곱 개를 똑같이 보여 준다. 그중 다섯이 받은 Intent를 다시 띄운다는 사실은 매니페스트 어디에도 없고 코드에만 있다. jadx로 풀어서 `getParcelableExtra`와 `parseUri`를 grep하면 그 다섯이 나온다. 같은 grep을 InsecureShop에도 돌려 봤다.

![jadx -q -d 로 intentlab.apk와 insecureshop.apk를 디컴파일한 뒤 grep -rn -o -E "(getParcelableExtra 또는 parseUri)" 결과. intentlab의 ForwardActivity.java:13, OptOutForwardActivity.java:13, PkgForwardActivity.java:13, SafeForwardActivity.java:18 getParcelableExtra("extra_intent"), UriForwardActivity.java:16 parseUri(stringExtra, 1), InsecureShop의 ChooserActivity.java:53 getParcelableExtra("android.intent.extra.STREAM")와 WebView2Activity.java:53 getParcelableExtra("extra_intent"). 아래에 WebView2Activity 53~57행 startActivity(extraIntent); finish(); 와 매니페스트의 intent-filter(action com.insecureshop.action.WEBVIEW, category DEFAULT와 BROWSABLE)](/assets/img/android-mastery/p1c15/02-host-jadx-sinks.png)

InsecureShop의 `WebView2Activity`는 exported 속성이 없지만 targetSdk 29에 intent-filter가 붙어 있어 파서가 exported로 채운다. exported를 반드시 적게 하는 규칙은 앱의 targetSdk가 31 이상일 때 설치 단계 파싱 오류로 강제된다([ParsedActivityUtils.java 464~476행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedActivityUtils.java#464), 자세한 건 [6장](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)). 53~57행은 받은 `extra_intent`를 검사 없이 띄운다. 뒤에서 이 액티비티도 실제로 써 본다.

## extra 하나로 열리는 관리 화면

`AdminActivity.java`는 이렇다.

```java
// AdminActivity.java 10~21행
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        boolean admin = getIntent().getBooleanExtra("isAdmin", false);
        String user = getIntent().getStringExtra("user");
        Log.i(Ui.TAG, "AdminActivity isAdmin=" + admin + " user=" + user
                + " referrer=" + getReferrer());
        if (admin) {
            Ui.show(this, "ADMIN PANEL\n\nuser: " + user + "\nreset token: " + Ui.TOKEN, 0xFFE65100);
        } else {
            Ui.show(this, "Access denied\n\nisAdmin=false\nuser: " + user, 0xFF455A64);
        }
    }
```

셸에서 `am start`로 extra를 넣었다. 처음에는 흔히 하는 실수대로 boolean을 `--es`로 넣었다.

![adb -s $S shell id -u 출력 2000. am start -n io.seika.intentlab/.AdminActivity --es isAdmin true --es user guest 후 logcat에 W/Bundle: Key isAdmin expected Boolean but value was a java.lang.String. The default value false was returned. 와 I/INTENTLAB: AdminActivity isAdmin=false user=guest referrer=android-app://com.android.shell. 이어서 am start -S -n ... --ez isAdmin true --es user guest 는 Stopping: io.seika.intentlab 후 Starting, 로그 AdminActivity isAdmin=true user=guest referrer=android-app://com.android.shell](/assets/img/android-mastery/p1c15/03-device-am-extras.png)

`--es`로 넣은 값은 문자열 `"true"`라서 `getBooleanExtra`가 기본값 false를 돌려준다. 그때 [BaseBundle.java 1076행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/os/BaseBundle.java#1076)의 `typeWarning`이 `Bundle` 태그로 경고를 찍으니, extra가 먹지 않을 때는 logcat에서 `expected Boolean`부터 찾으면 된다. `--ez`로 바꾸자 `isAdmin=true`가 되고 화면이 주황색 ADMIN PANEL로 바뀌었다.

두 번째 명령에 `-S`가 붙은 데는 이유가 있다. 처음에는 `-S` 없이 다시 `am start`를 했는데 `Warning: Activity not started, intent has been delivered to currently running top-most instance.`가 나오고 `onCreate`가 다시 돌지 않아 로그가 `isAdmin=false`에 머물렀다. `am start`는 `FLAG_ACTIVITY_NEW_TASK`로 띄우는데, 새 Intent가 기존 태스크의 루트 Intent와 extra만 다르면 시스템은 둘을 같은 Intent로 본다([ActivityStarter.java 2152행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityStarter.java#2152)의 `isSameIntentFilter`). 그러면 기존 태스크를 재사용하고 새 액티비티는 만들지 않는다. 태스크가 이미 맨 위에 있어 움직인 것이 없으니 [1980~1991행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityStarter.java#1980)은 `START_DELIVERED_TO_TOP`을 돌려준다(태스크를 앞으로 옮겼다면 `START_TASK_TO_FRONT`였다). `AdminActivity`는 singleTop이 아니어서 `onNewIntent`도 불리지 않고, 새 Intent와 그 extra는 액티비티에 닿지 않은 채 버려진다.

`am`이 찍은 "delivered" 문구는 이 반환값의 이름을 옮긴 것이고 실제로 배달된 것은 없다. `-S`로 앱을 먼저 멈추거나 `--activity-clear-task`를 줘야 새로 뜬다. 공격자 앱을 모드만 바꿔 연달아 실행할 때도 같은 일이 생겨서 이후 명령에는 전부 `--activity-clear-task`(출력의 `flg=0x8000`)를 붙였다.

`am`이 extra로 넣을 수 있는 타입은 [Intent.parseCommandArgs](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#8008)의 case 목록이 전부다. 문자열·정수·long·float·double(이 다섯은 배열과 리스트도), boolean, URI, ComponentName, null 문자열(`--esn`)까지는 있지만 Intent를 extra에 담는 옵션은 없다. 그래서 Parcelable Intent를 실어 보내는 공격에는 공격자 앱이 필요했다.

## DUMP 권한 하나로 갈린 셸과 앱

같은 일을 셸과 권한 없는 앱에서 각각 해 봤다. `ShellOnlyActivity`는 exported지만 `android:permission="android.permission.DUMP"`가 걸려 있다.

![셸(uid 2000)에서 am start -W ShellOnlyActivity는 Status: ok, PrivateActivity는 java.lang.SecurityException: Permission Denial: starting Intent { flg=0x10000000 cmp=io.seika.intentlab/.PrivateActivity } from null (pid=6109, uid=2000) not exported from uid 10179, content query는 opening provider io.seika.intentlab.SecretProvider ... that is not exported from UID 10179. 공격자 앱 uid=10180 mode=direct-all은 PrivateActivity not exported from uid 10179, ShellOnlyActivity requires android.permission.DUMP, provider not exported 세 SecurityException. mode=direct-admin은 start AdminActivity -> sent 후 AdminActivity isAdmin=true user=intentatk referrer=null](/assets/img/android-mastery/p1c15/05-device-shell-vs-app.png)

`exported="false"`는 셸과 앱 모두를 막았다. 거부 문구는 [ActivityTaskSupervisor.checkStartAnyActivityPermission](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityTaskSupervisor.java#1070)에서 나온다. 호출자가 `START_ANY_ACTIVITY`를 가졌으면 모든 검사를 건너뛰고, 아니면 1101~1105행이 "not exported from uid", 1106~1110행이 "requires <권한>"을 만든다. 셸은 `START_ANY_ACTIVITY`가 없어서 not exported에 걸린다.

`ShellOnlyActivity`에서는 결과가 갈렸다. 셸은 열었고 앱은 `requires android.permission.DUMP`로 막혔다. DUMP의 보호 수준은 signature, privileged, development인데 [Shell 앱 매니페스트 152행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/packages/Shell/AndroidManifest.xml#152)이 셸에 이 권한을 준다. 그래서 셸에서 열린 컴포넌트가 앱에서도 열리는지는 컴포넌트에 걸린 권한을 셸이 가졌는지까지 봐야 판단할 수 있다.

셸 UID를 굳이 2000으로 내린 이유도 여기 있다. [ActivityManager.checkComponentPermission](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityManager.java#4216)은 root와 system UID를 맨 앞에서 무조건 통과시킨다(4218~4222행). `adb root` 상태로 같은 명령을 치면 exported=false도 열리고, 그 결과는 실제 기기의 어떤 앱 상황과도 맞지 않는다. 그 아래로 같은 앱이면 통과, exported가 false면 거부, 권한이 없으면 허용 순서로 내려간다.

마지막 줄에서 예상이 하나 빗나갔다. 공격자 앱이 연 `AdminActivity`의 `getReferrer()`가 `android-app://io.seika.intentatk`일 줄 알았는데 `null`이었다. 시스템은 referrer 패키지가 받는 앱에게 보이지 않으면 null로 바꿔 넘긴다([ActivityRecord.getFilteredReferrer](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/wm/ActivityRecord.java#9894)). 피해자는 공격자 패키지를 `<queries>`에 두지 않았으니 못 보고, 셸은 보이니 앞 화면에서는 `com.android.shell`이 찍혔다. 게다가 [Activity.getReferrer](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/Activity.java#6532)는 Intent에 `EXTRA_REFERRER`나 `EXTRA_REFERRER_NAME`이 들어 있으면 그 값을 먼저 돌려준다. 이 값은 호출자가 Intent에 마음대로 적어 넣을 수 있어서, `getReferrer()`로 호출자를 확인하는 코드는 공격자가 원하는 패키지명을 보게 된다.

## 받은 Intent를 그대로 띄우는 포워더

`ForwardActivity.java` 전체다.

```java
package io.seika.intentlab;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

// Vulnerable on purpose: launches whatever Intent the caller put in "extra_intent".
public class ForwardActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent inner = getIntent().getParcelableExtra("extra_intent");
        Log.i(Ui.TAG, "ForwardActivity forwarding " + inner);
        if (inner != null) {
            try {
                startActivity(inner);
            } catch (RuntimeException e) {
                Log.w(Ui.TAG, "ForwardActivity startActivity failed: " + e);
            }
        }
        finish();
    }
}
```

공격자 쪽 `AttackActivity.java`는 피해자 컴포넌트를 가리키는 Intent를 만들어 `extra_intent`에 싸서 보낸다.

```java
// AttackActivity.java 25~32행
    static Intent victim(String cls) {
        return new Intent().setClassName(V, V + cls);
    }

    // outer intent to an exported forwarder of the victim, carrying the nested intent
    static Intent wrap(String forwarder, Intent inner) {
        return victim(forwarder).putExtra("extra_intent", inner);
    }

// AttackActivity.java 62~65행 (mode=redirect)
            case "redirect":
                tryStart("ForwardActivity(PrivateActivity)", wrap(".ForwardActivity",
                        victim(".PrivateActivity").putExtra("via", "ForwardActivity")));
                break;
```

바깥 Intent는 exported인 `ForwardActivity`로 가니 통과한다. 안쪽 Intent는 피해자가 자기 `startActivity()`로 띄운다. 시스템이 권한을 보는 대상은 지금 `startActivity`를 부른 쪽, 피해자다. 피해자 UID는 자기 `PrivateActivity`의 주인이라 `checkComponentPermission`의 같은 앱 분기에서 바로 허용된다.

![pm list packages -U io.seika 출력 package:io.seika.intentatk uid:10180, package:io.seika.intentlab uid:10179. 공격자 mode=redirect 실행 후 logcat: I/INTENTATK: uid=10180 mode=redirect, start ForwardActivity(PrivateActivity) -> sent, I/INTENTLAB: ForwardActivity forwarding Intent { cmp=io.seika.intentlab/.PrivateActivity (has extras) }, PrivateActivity reached via=ForwardActivity referrer=android-app://io.seika.intentlab myUid=10179. dumpsys activity activities 에서 launchedFromUid=10179 launchedFromPackage=io.seika.intentlab, app=ProcessRecord{... io.seika.intentlab/u0a179}, Intent { cmp=io.seika.intentlab/.PrivateActivity (has extras) }](/assets/img/android-mastery/p1c15/06-device-redirect.png)

uid 10180인 공격자가 보낸 Intent로 `PrivateActivity`가 열렸고, 시스템의 액티비티 기록에는 `launchedFromUid=10179 launchedFromPackage=io.seika.intentlab`이 남았다. 시스템 입장에서는 피해자가 자기 화면을 연 것과 구별되지 않는다. 피해자의 권한을 남이 빌려 쓰는 confused deputy 구조이고, Binder 호출자 신원 쪽 개념은 [Atlas C22](/posts/android-concept-atlas-c22-binder-caller-identity-confused-deputy/)에 있다.

## grant 플래그를 얹으면 provider가 넘어간다

이번에는 안쪽 Intent를 공격자 자기 앱의 `LeakActivity`로 향하게 하고, 피해자의 비공개 provider URI와 `FLAG_GRANT_READ_URI_PERMISSION`을 붙여 보냈다.

```java
// AttackActivity.java 34~39행
    // nested intent pointing back at this app, with the victim's private provider URI and a read grant
    Intent leak() {
        return new Intent().setClassName(getPackageName(), getPackageName() + ".LeakActivity")
                .setData(SECRET)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
    }
```

`SECRET`은 `content://io.seika.intentlab.secret/token`이다. 같은 앱이 provider에 직접 query하는 줄을 먼저 두어 비교했다.

![mode=direct-provider: query content://io.seika.intentlab.secret/token -> SecurityException: Permission Denial: opening provider io.seika.intentlab.SecretProvider from ProcessRecord{... io.seika.intentatk/u0a180} (pid=5515, uid=10180) that is not exported from UID 10179. mode=redirect-grant: ForwardActivity forwarding Intent { dat=content://io.seika.intentlab.secret/... flg=0x1 cmp=io.seika.intentatk/.LeakActivity }, LeakActivity uid=10180 data=content://io.seika.intentlab.secret/token flags=0x1 referrer=android-app://io.seika.intentlab, SecretProvider query ... callingUid=10180 callingPackage=io.seika.intentatk, LeakActivity query -> name=token value=lab-secret-4821. dumpsys activity permissions: UID 10180 holds: UriPermission{7c15fb4 content://io.seika.intentlab.secret/token user 0}, 그 아래 무관한 UID 10195 downloads grant](/assets/img/android-mastery/p1c15/08-device-redirect-grant.png)

직접 열면 not exported로 막히던 provider를, 피해자를 한 번 거치자 공격자 UID 10180이 직접 query했다. provider 쪽 로그의 `callingUid=10180`이 그걸 보여 주고, `dumpsys activity permissions`에는 UID 10180이 그 URI의 grant를 쥔 것으로 나온다. 아래의 UID 10195 줄은 이미지에 미리 깔린 다른 앱의 downloads grant라 이번 실험과 관계없다.

grant가 성립하는 조건은 [UriGrantsManagerService.java 1211~1238행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/uri/UriGrantsManagerService.java#1211)에 있다. provider가 `grantUriPermissions`를 허용해야 하고, 1242행부터는 grant를 거는 호출자 자신이 그 URI에 접근할 수 있어야 한다. 여기서 호출자는 피해자고, 자기 provider니 당연히 접근할 수 있다. exported=false인 provider라도 grant를 허용하면 포워더 하나로 밖에 새어 나간다. URI grant 자체는 [Atlas C11](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)에서 다룬다.

같은 사슬을 InsecureShop에 그대로 걸어 봤다. 디버그 빌드라 `run-as`로 앱 데이터 폴더에 표식 파일을 하나 만들고, 공격자가 `WebView2Activity`에 InsecureShop의 FileProvider URI를 담은 `LeakActivity` Intent를 보냈다. 이 FileProvider는 루트 경로 `/`를 매핑하고 grant를 허용한다.

![adb install apps/edu/insecureshop.apk Success, run-as com.insecureshop 으로 files/marker.txt 에 insecureshop-private-note 기록, am start ... --es mode insecureshop --es path /data/data/com.insecureshop/files/marker.txt 후 logcat: start InsecureShop WebView2Activity(LeakActivity+grant) -> sent, LeakActivity uid=10180 data=content://com.insecureshop.file_provider/root/data/data/com.insecureshop/files/marker.txt flags=0x1 referrer=android-app://com.insecureshop, LeakActivity query -> _display_name=marker.txt _size=26, LeakActivity file -> insecureshop-private-note](/assets/img/android-mastery/p1c15/12-device-insecureshop.png)

공격자 앱이 InsecureShop 내부 저장소의 파일을 읽었다. 시스템 로그(`pm list packages -U com.insecureshop`로 본 InsecureShop UID는 10181)에는 두 번째 실행이 InsecureShop에서 나간 것으로 찍혔다.

```text
10-15 12:05:52.360   515   642 I ActivityTaskManager: START u0 {cmp=com.insecureshop/.WebView2Activity (has extras)} from uid 10180
10-15 12:05:55.524   515  2136 I ActivityTaskManager: START u0 {dat=content://com.insecureshop.file_provider/... flg=0x1 cmp=io.seika.intentatk/.LeakActivity} from uid 10181
```

## 문자열로 온 intent: URI와 StrictMode

중첩 Intent가 꼭 Parcelable로 오지는 않는다. `UriForwardActivity`는 문자열 extra `next`를 `Intent.parseUri(next, Intent.URI_INTENT_SCHEME)`로 Intent로 만들어 띄운다. 이건 `am`만으로도 공격할 수 있다. 피해자 앱은 Application에서 `StrictMode.VmPolicy`에 `detectUnsafeIntentLaunch().penaltyLog()`를 켜 두었다.

![logcat -c 후 adb -s $S shell "am start -n io.seika.intentlab/.UriForwardActivity --es next 'intent:#Intent;component=io.seika.intentlab/.PrivateActivity;S.via=UriForwardActivity;end'", 이어서 공격자 mode=redirect. 로그: UriForwardActivity next=intent:#Intent;component=io.seika.intentlab/.PrivateActivity;..., D/StrictMode: StrictMode policy violation: android.os.strictmode.UnsafeIntentLaunchViolation: Launch of unsafe intent: Intent { act=android.intent.action.VIEW cmp=io.seika.intentlab/.PrivateActivity (has extras) }, PrivateActivity reached via=UriForwardActivity myUid=10179, ForwardActivity forwarding 다음 같은 violation, PrivateActivity reached via=ForwardActivity](/assets/img/android-mastery/p1c15/10-device-uri-strictmode.png)

uid 2000인 셸이 피해자를 거쳐 exported=false 액티비티를 열었다. URI로 만든 Intent에는 `act=android.intent.action.VIEW`가 붙어 있는데, `parseUri`가 `new Intent(ACTION_VIEW)`에서 시작하고([Intent.java 7639행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#7639)) URI에 `action=`이 없어서다. 문자열 경로에는 한계도 있다. URI의 `launchFlags=`로 grant 플래그를 넣어도 `URI_ALLOW_UNSAFE`가 없으면 지워지기 때문에([7685~7690행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#7685)) 기본적으로는 화면까지만 닿고 provider grant는 실어 나르지 못한다.

StrictMode는 두 방식 모두에서 violation을 찍었고, 순서는 포워더 줄, violation, `reached` 순이었다. 판정 조건은 [Intent.java 11944~11960행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/Intent.java#11944)에 있다. 다른 앱의 parcel에서 나온 Intent, 필터되지 않은 extra를 가진 Intent를 띄우면 걸리고, URI에서 만든 Intent는 BROWSABLE이 붙은 암시적 Intent가 아니면 걸린다(컴포넌트를 지정하면 BROWSABLE이 있어도 걸린다). 로그만 남기고 아무것도 막지 않으니 개발 중에 포워딩 지점을 찾는 탐지기로 쓰면 된다.

## 허용 목록 포워더와 setPackage 포워더

방어를 넣은 `SafeForwardActivity.java` 전체다.

```java
package io.seika.intentlab;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import java.util.Arrays;

// Defended forwarder: resolve the nested intent, allow only listed components of this app,
// and launch a fresh Intent so the data, flags (FLAG_GRANT_*) and extras of the nested one are dropped.
public class SafeForwardActivity extends Activity {
    static final String[] ALLOW = {"io.seika.intentlab.HelpActivity"};
    static final int GRANT_FLAGS = Intent.FLAG_GRANT_READ_URI_PERMISSION
            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent inner = getIntent().getParcelableExtra("extra_intent");
        if (inner == null) {
            finish();
            return;
        }
        ComponentName cn = inner.resolveActivity(getPackageManager());
        boolean ok = cn != null && getPackageName().equals(cn.getPackageName())
                && Arrays.asList(ALLOW).contains(cn.getClassName());
        if (!ok) {
            Log.w(Ui.TAG, "SafeForward blocked requested=" + Ui.name(inner.getComponent())
                    + " resolved=" + Ui.name(cn)
                    + " grantFlags=0x" + Integer.toHexString(inner.getFlags() & GRANT_FLAGS));
            finish();
            return;
        }
        Log.i(Ui.TAG, "SafeForward allowed " + Ui.name(cn));
        startActivity(new Intent().setComponent(cn));
        finish();
    }
}
```

허용 목록에 있는 자기 앱 컴포넌트만 받고, 받은 Intent를 그대로 쓰지 않고 컴포넌트만 옮긴 새 Intent를 띄운다. 공격자가 붙인 data, extra, grant 플래그는 새 Intent에 따라가지 않는다. 비교용으로 흔히 보이는 "고친" 버전 `PkgForwardActivity`도 만들었는데, 띄우기 전에 `inner.setPackage(getPackageName())`만 한다.

![공격자 mode=safe-redirect, safe-grant, safe-help, pkg-redirect 연속 실행 후 logcat: W/INTENTLAB: SafeForward blocked requested=io.seika.intentlab/.PrivateActivity resolved=io.seika.intentlab/.PrivateActivity grantFlags=0x0, SafeForward blocked requested=io.seika.intentatk/.LeakActivity resolved=io.seika.intentatk/.LeakActivity grantFlags=0x1, SafeForward allowed io.seika.intentlab/.HelpActivity, HelpActivity reached referrer=android-app://io.seika.intentlab, PkgForward forwarding Intent { pkg=io.seika.intentlab cmp=io.seika.intentlab/.PrivateActivity (has extras) }, PrivateActivity reached via=PkgForwardActivity myUid=10179](/assets/img/android-mastery/p1c15/11-device-safe-forward.png)

`SafeForwardActivity`는 `PrivateActivity`와 grant를 실은 `LeakActivity`를 둘 다 막았고, 정상 경로인 `HelpActivity`는 통과시켰다. `PkgForwardActivity`는 아무것도 막지 못했다. 공격자가 노린 `PrivateActivity`가 원래 피해자 패키지 안에 있으니 패키지를 피해자 것으로 고정해 봐야 목적지는 그대로다.

이 화면에서 예상과 다른 값이 하나 있었다. 피해자는 공격자 패키지를 볼 수 없으니 `LeakActivity`에 대한 `resolveActivity()`가 null을 돌려줄 거라고 봤는데 `resolved=io.seika.intentatk/.LeakActivity`가 찍혔다. 앞의 grant 실험에서 두 앱이 상호작용하며 서로 보이게 된 탓인가 싶어, 에뮬레이터를 깨끗하게 다시 부팅하고 두 앱을 새로 깐 상태에서 순서를 바꿔 돌렸다.

![새로 설치한 직후 dumpsys package queries 를 grep -A1 "io.seika.intentlab:" 하면 아무것도 안 나옴. mode=safe-grant 결과 W/INTENTLAB: SafeForward blocked requested=io.seika.intentatk/.LeakActivity resolved=io.seika.intentatk/.LeakActivity grantFlags=0x1. direct-provider와 redirect-grant 실행 뒤 같은 grep에 io.seika.intentlab: 아래 io.seika.intentatk 가 나오고, 다시 safe-grant 를 돌려도 resolved=io.seika.intentatk/.LeakActivity grantFlags=0x1](/assets/img/android-mastery/p1c15/15-device-safe-grant-fresh.png)

처음 grep이 빈 줄인 것으로 보아 피해자는 공격자를 전혀 못 보는 상태였는데도 `resolved=`는 공격자 컴포넌트였다. 가시성이 생긴 뒤에도 값은 같았다. 원인은 `Intent.resolveActivity(PackageManager)` 쪽에 있었다.

![cs.android.com android-13.0.0_r84 frameworks/base/core/java/android/content/Intent.java 9458~9497행, 9463행 강조. public ComponentName resolveActivity(PackageManager pm) 는 9464~9466행에서 mComponent != null 이면 mComponent를 그대로 반환하고, 그 다음에야 pm.resolveActivity(this, PackageManager.MATCH_DEFAULT_ONLY)를 부른다](/assets/img/android-mastery/p1c15/25-src-a13-intent-resolveactivity.png)

명시적 Intent면 `mComponent`를 그대로 돌려줄 뿐 PackageManager에 묻지 않는다. 패키지 가시성 필터는 [ComputerEngine.java 552~556행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/ComputerEngine.java#552)처럼 PackageManager 안에서 걸리는데, 여기까지 가지도 않는다. 그러니 `SafeForwardActivity`에서 `resolveActivity()` 호출은 명시적 Intent에 대해서는 아무 일도 하지 않고, 차단은 전적으로 패키지 이름 비교와 허용 목록에서 나왔다. resolve 단계에 무언가를 기대하려면 암시적 Intent를 다루거나 `PackageManager.resolveActivity()`를 직접 불러야 한다. 보이지 않는 패키지의 명시적 컴포넌트를 `PackageManager.resolveActivity()`나 `queryIntentActivities()`로 직접 조회하면 null이 나올 것으로 보이지만, 그 경로는 앱을 따로 고쳐야 해서 이번에 만들어 돌리지는 않았다.

방어를 검증할 때는 위 화면처럼 공격 모드를 그대로 다시 돌려 차단 로그가 나오고 정상 경로가 통과하는지 같이 본다. 차단만 확인하면 모든 포워딩을 끊어 버린 구현도 통과해 버린다. 다른 앱 Intent를 꼭 받아야 한다면 Intent 대신 PendingIntent를 받는 설계가 낫고, 그건 [PendingIntent 실습](/posts/android-lab-p1c19-pendingintent-uri-grant/)에서 다룬다. 공식 권고는 [Intent redirection 위험 문서](https://developer.android.com/privacy-and-security/risks/intent-redirection)에 있다.

## Android 16이 막는 것과 못 막는 것

Android 14에서 redirection 방어가 들어왔다고 기억하기 쉬운데, [Android 14 변경 사항](https://developer.android.com/about/versions/14/behavior-changes-14)의 Intent 항목은 targetSdk 34 이상 앱의 암시적 Intent를 exported 컴포넌트로만 배달한다는 내용이고 redirection은 언급하지 않는다. 플랫폼 차원의 redirection 방어는 [Android 16의 모든 앱 대상 변경](https://developer.android.com/about/versions/16/behavior-changes-all#intent-redirect-attacks)이고, 앱이 끄려면 `removeLaunchSecurityProtection()`을 부른다.

구조는 이렇다. 앱이 `startActivity`를 부르면 [ActivityTaskManagerService 1272행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/wm/ActivityTaskManagerService.java#1272)이 `addCreatorToken`을 호출하고, [ActivityManagerService 19415행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/am/ActivityManagerService.java#19415)은 보내는 패키지와 받는 패키지가 다르면 안에 든 Intent마다 보낸 쪽 UID가 적힌 토큰을 붙인다. 토큰의 키([19353행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/am/ActivityManagerService.java#19353))는 만든 쪽 UID와 패키지, 그리고 action, data, type, package, component, grant 플래그, ClipData URI다. extra는 키에 없다. 피해자가 나중에 그 Intent를 띄우면 [ActivityStarter 624~639행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/wm/ActivityStarter.java#624)이 토큰을 확인해 만든 사람의 UID를 꺼내고, 그 UID 기준으로 권한 검사를 다시 한다. 실제 검사는 [1262~1293행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/wm/ActivityStarter.java#1262)에 있다.

![android-16.0.0_r1 ActivityStarter.java 1262~1293행. if (intentCreatorUid != Request.DEFAULT_INTENT_CREATOR_UID) 안에서 mSupervisor.checkStartAnyActivityPermission(intent, aInfo, ..., intentCreatorUid, intentCreatorPackage, ...) 가 실패하면 INTENT_REDIRECT_ABORT_START_ANY_ACTIVITY_PERMISSION, SecurityException이면 logAndThrowExceptionForIntentRedirect, 이어 mIntentFirewall.checkStartActivity와 getPermissionPolicyInternal().checkStartActivity 도 intentCreatorUid로 검사, 마지막 1293행 intent.removeCreatorToken()](/assets/img/android-mastery/p1c15/21-src-a16-creator-check.png)

검사에 걸렸을 때 실제로 막을지는 [3664행 이후](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/wm/ActivityStarter.java#3664)에서 정해진다. 로그(`Slog.wtf`)는 항상 남기고, aconfig 플래그 `prevent_intent_redirect_abort_or_throw_exception`과 compat change 29623414가 모두 켜져 있을 때만 예외를 던진다. 이 플래그는 [선언](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/security/responsible_apis_flags.aconfig#84)만 보면 서버에서 바꿀 수 있는 값이라 기기에서 직접 확인했다.

![Android 16 에뮬레이터. getprop ro.build.version.release 16, aflags list 에서 prevent_intent_redirect, prevent_intent_redirect_abort_or_throw_exception, prevent_intent_redirect_collect_nested_keys_on_server_if_not_collected 세 플래그가 enabled - default read-only system, ChangeId(29623414; name=ENABLE_PREVENT_INTENT_REDIRECT_TAKE_ACTION; overridable). mode=redirect: ForwardActivity forwarding Intent { xflg=0x4 cmp=io.seika.intentlab/.PrivateActivity (has extras) }, E/ActivityTaskManager: IntentRedirect Hardening INTENT_REDIRECT_ABORT_START_ANY_ACTIVITY_PERMISSION intentCreatorUid: 10217; intentCreatorPackage: io.seika.intentatk; callingUid: 10216; callingPackage: io.seika.intentlab, W/INTENTLAB: ForwardActivity startActivity failed: java.lang.SecurityException 같은 문구. mode=redirect-grant: INTENT_REDIRECT_EXCEPTION_GRANT_URI_PERMISSION (Creator URI permission grant throw exception.)으로 실패](/assets/img/android-mastery/p1c15/13-aux36-redirect.png)

이 빌드에서는 차단 플래그가 enabled에 read-only로 고정돼 있었고, Android 13에서 통했던 두 공격이 모두 `[IntentRedirect Hardening]`으로 실패했다. `PrivateActivity`로 가는 쪽은 만든 사람(intentatk, 10217)이 `checkStartAnyActivityPermission`을 통과하지 못해서, grant를 실은 쪽은 만든 사람이 그 URI에 grant를 걸 자격이 없어서 막혔다. 피해자 UID 10216은 callingUid로만 적혔다. `LeakActivity`는 뜨지 않았고 공격자 UID에 남은 grant도 없었다.

첫 번째 로그는 이름이 ABORT인데 꼬리에 "throw exception"이 붙어 있다. 이 로그는 이미지의 1273~1277행 `catch (SecurityException e)` 분기에서 나온 코드 3이고, 1268~1269행 abort 분기와는 다르다. 만든 사람 UID로 돌린 `checkStartAnyActivityPermission`이 "not exported" 예외를 던졌고 `logAndThrowExceptionForIntentRedirect`가 그걸 다시 던졌다. 소스의 [메시지 표 3721행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/wm/ActivityStarter.java#3721)이 코드 3에 ABORT 이름을 그대로 재사용해서 생긴 혼동이다.

이 실험에서 앱이 보낸 Intent와 시스템 START 로그에는 `xflg=0x4`가 붙었는데, 중첩 Intent 키를 모았다는 확장 플래그(EXTENDED_FLAG_NESTED_INTENT_KEYS_COLLECTED)다. 방어 코드에는 토스트를 띄우는 분기도 있지만 이 빌드의 `aflags list`에는 `prevent_intent_redirect_show_toast` 플래그가 아예 없어 토스트는 보지 못했다.

토큰은 Intent 안에 Parcelable로 든 Intent에만 붙는다. 빈틈은 여기서 생긴다. 문자열 `intent:` URI는 피해자가 자기 손으로 만든 Intent라 토큰이 없다. 토큰 검증([AMS 19322행 `isValid`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/services/core/java/com/android/server/am/ActivityManagerService.java#19322))은 키 필드가 하나라도 바뀌면 실패하고, 그러면 `ActivityStarter`는 만든 사람 검사를 건너뛴다. `setPackage()`는 키에 든 package 필드를 바꾼다. 예상이 맞는지 Android 16에서 세 경로를 돌려 봤다.

![Android 16. adb shell "am start -n io.seika.intentlab/.UriForwardActivity --es next 'intent:#Intent;component=io.seika.intentlab/.PrivateActivity;S.via=UriForwardActivity;end'" 후 PrivateActivity reached via=UriForwardActivity myUid=10216. mode=optout-redirect: OptOutForward removeLaunchSecurityProtection() called, OptOutForward forwarding Intent { xflg=0x4 cmp=io.seika.intentlab/.PrivateActivity }, PrivateActivity reached via=OptOutForwardActivity. mode=pkg-redirect: PkgForward forwarding Intent { xflg=0x4 pkg=io.seika.intentlab cmp=io.seika.intentlab/.PrivateActivity }, PrivateActivity reached via=PkgForwardActivity. IntentRedirect Hardening 줄 없음](/assets/img/android-mastery/p1c15/14-aux36-uri-optout.png)

셋 다 `PrivateActivity`에 닿았고 hardening 로그는 한 줄도 없었다. `OptOutForwardActivity`는 [`removeLaunchSecurityProtection()`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r1/core/java/android/content/Intent.java#12649)으로 토큰을 지운 뒤 띄우는 포워더다(API 34로 컴파일했기 때문에 리플렉션으로 불렀다). 앞에서 아무것도 막지 못한 `setPackage()` 수정이 Android 16에서는 플랫폼 방어까지 꺼 버리는 셈이다. 같은 로그에서 StrictMode는 Android 16에서도 세 경우 모두 `UnsafeIntentLaunchViolation`을 남겼다.

Android 16 에뮬레이터는 `aflags`를 읽느라 adbd를 root로 둔 채 실험했다. 그래서 첫 줄의 `UriForwardActivity` 실행은 uid 0에서 나갔는데, 이 액티비티는 원래 exported라 결과에 영향이 없고 `PrivateActivity`를 띄운 호출은 시스템 로그에 피해자 UID 10216으로 남았다. 나머지 공격은 모두 앱끼리 주고받았다. 공격자 앱에 opt-out 포워더와 grant를 묶은 모드도 넣어 두었지만 이번에는 돌리지 않았다.

Android 16에서 막힌 건 Parcelable로 온 두 경로뿐이었다. 같은 기기에서 `SafeForwardActivity`는 다시 돌리지 않았지만, 허용 목록 비교는 토큰과 무관하게 앱 안에서 도는 코드라 결과가 달라질 이유가 없다.

*다음 글: [BroadcastReceiver와 ordered broadcast](/posts/android-lab-p1c16-broadcastreceiver-ordered-broadcast/)*
