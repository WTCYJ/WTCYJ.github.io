---
layout: post
title: "ContentProvider·FileProvider 실습 — 열린 provider와 문자열 접두사 검사"
date: 2026-11-02 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ContentProvider, FileProvider, SQLiteQueryBuilder, PathTraversal, URIPermission]
excerpt: "Android 13 에뮬레이터에서 권한 없는 exported provider는 셸과 제3자 앱 모두에게 토큰 열까지 내줬고, 호출자가 쓴 selection과 projection은 UNION과 서브쿼리로 다른 테이블에 닿았다. 폴더 공유용 prefix grant를 받은 제3자 앱은 androidx.core 1.12.0 FileProvider에서 옆 폴더 docs-private의 파일을 읽었고, 1.16.0에서는 거부당했다."
---

[서비스](/posts/android-lab-p1c17-service-messenger-aidl/)는 Binder 트랜잭션마다 호출자 UID를 받아 스스로 판단해야 했다. ContentProvider는 그 판단의 상당 부분을 시스템이 대신 해 준다. provider를 여는 순간 `ActivityManagerService`가 exported 여부와 읽기·쓰기 권한을 따지고, 통과한 호출자에게만 provider의 Binder를 넘긴다. 관문이 비어 있으면(exported에 권한 없음) 호출자가 보낸 `selection`, `projection`, URI 경로가 그대로 provider 코드로 들어온다. provider가 그 값을 SQL 문자열이나 파일 경로에 붙이면 호출자는 provider가 열 수 있는 데이터베이스와 파일을 똑같이 열 수 있다.

개념 쪽 배경은 Atlas의 [컴포넌트와 Binder(C21)](/posts/android-concept-atlas-c21-components-binder/)와 [패키지 가시성과 URI 권한(C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)에 있다.

실험 기기는 Android 13 에뮬레이터(API 33, x86_64, userdebug, 빌드 TE1A.240213.009, 보안 패치 2024-03-01, SELinux Enforcing) 한 대다. 프레임워크 소스 링크는 `android-13.0.0_r84` 태그로, androidx 소스는 커밋 해시로 고정해 건다. 캡처의 `$S`는 에뮬레이터 시리얼이다.

## 실험 앱과 provider 구성

피해자 앱 `io.seika.cplab`(targetSdk 33)은 같은 `users.db`를 여러 방식으로 내놓는다. `users` 테이블에는 `_id, name, email, token` 열과 실습용 가짜 토큰 세 행이, `secrets` 테이블에는 `api_key=lab-apikey-0000-fake` 한 행이 있고, `shared_prefs/session.xml`에는 `auth_token=lab-session-token-fake`가 들어 있다. 화면에 나오는 값은 전부 이 실습용 값이라 가리지 않았다.

| authority | 매니페스트 | 코드 |
|---|---|---|
| `io.seika.cplab.users` | exported, 권한 없음 | selection·projection을 `SQLiteDatabase.query`에 그대로, 이름 경로는 SQL에 문자열 연결, `update` 허용 |
| `io.seika.cplab.users.strict` | exported, 권한 없음 | `SQLiteQueryBuilder.setStrict(true)`만 |
| `io.seika.cplab.users.grammar` | exported, 권한 없음 | projection map + `setStrict` + `setStrictColumns` + `setStrictGrammar` |
| `io.seika.cplab.users.guarded` | exported, signature 읽기·쓰기 권한 | grammar와 같은 코드 |
| `io.seika.cplab.users.private` | exported 아님 | 취약한 코드 그대로 |
| `io.seika.cplab.files` | exported, 권한 없음 | 커스텀 `openFile`, 경로 검사 없음 |
| `io.seika.cplab.files.safe` | exported, 권한 없음 | canonical 경로 검사 추가 |

공격 쪽은 다른 키로 서명한 `io.seika.cpattack`(권한 하나 없이 `<queries>`로 피해자 패키지만 선언)과, 같은 코드에서 `<queries>`만 뺀 `io.seika.cpblind`다. FileProvider 실험용으로 같은 코드를 androidx.core 1.12.0과 1.16.0에 각각 묶은 `io.seika.fpold`, `io.seika.fpnew`를 따로 만들었고, exported 기본값을 보려고 `android:exported`를 아예 적지 않은 provider를 targetSdk 16과 17로 빌드한 `io.seika.cpleg16`, `io.seika.cpleg17`도 설치했다.

외부 앱 입장에서 provider 목록은 APK 매니페스트에서 바로 나온다. 호스트에서 `aapt dump xmltree out/cplab.apk AndroidManifest.xml`의 provider 항목을 보면 `.users.private`만 `android:exported=(type 0x12)0x0`이고 나머지는 `0xffffffff`(true)이며, `.users.guarded`에만 `readPermission`과 `writePermission`이 붙어 있다.

측정 전에 한 가지를 먼저 해 둬야 했다. 이 실습 환경은 부팅 뒤 `adb root`로 adbd를 root로 올려 두는데(userdebug 이미지라 가능하다), root UID는 provider 권한 검사를 전부 건너뛴다. [`ActivityManager.checkComponentPermission`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityManager.java#4216)의 첫 분기가 root와 system UID에 무조건 `PERMISSION_GRANTED`를 돌려주고(4218~4222행), URI 권한 쪽도 [`UriGrantsManagerService`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/uri/UriGrantsManagerService.java#1275)가 1280~1283행에서 root(uid 0)에 한해 같은 일을 한다. 그래서 `adb unroot`로 셸을 uid 2000으로 내린 뒤에 모든 측정을 했다.

## 권한 없는 exported provider는 셸에서 그대로 읽힌다

`content` 명령은 셸 사용자로 provider를 여는 평범한 호출자다. [`Content.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/cmds/content/src/com/android/commands/content/Content.java#673)가 커서를 `Row: <n> 열=값, …` 형식으로 찍는다.

```bash
adb -s $S shell id
adb -s $S shell content query --uri content://io.seika.cplab.users/users
adb -s $S shell content query --uri content://io.seika.cplab.users.private/users 2>&1 | head -2
adb -s $S shell content query --uri content://io.seika.cplab.users.guarded/users 2>&1 | head -2
```

![셸 uid=2000(shell)에서 content query로 io.seika.cplab.users를 읽어 Row 0~2에 admin·alice·bob의 email과 token(tok-admin-7f3a 등)이 나오고, .users.private는 not exported from UID 10179, .users.guarded는 requires io.seika.cplab.permission.READ_USERS로 Permission Denial이 난 터미널](/assets/img/android-mastery/p1c18/03-device-shell-leak.png)

권한 없는 provider는 `token` 열까지 세 행을 전부 내줬다. 같은 코드를 쓰는 `.users.private`는 `that is not exported from UID 10179`로, `.users.guarded`는 `requires io.seika.cplab.permission.READ_USERS`로 막혔다. 메시지의 `from (null)`은 앱 프로세스가 아닌 외부 호출(셸의 `content`)이라 ProcessRecord가 없다는 표시다.

판정 순서는 `checkComponentPermission`에 그대로 적혀 있다. root·system이면 허용, 같은 앱이면 허용(4229~4231행), exported가 아니면 거부(4233~4241행), 요구 권한이 `null`이면 허용(4242~4244행)이다. 마지막 분기가 이번 취약 provider가 통과한 자리다. 권한 검사와 거부 메시지 조립은 [`ContentProviderHelper`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ContentProviderHelper.java#1508)의 1532~1579행에 있다.

다른 키로 서명하고 권한을 하나도 요청하지 않은 `cpattack`으로 같은 요청을 보내도 결과가 같았다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.cpattack/.Main --es mode query | grep -E "Status|Activity"
adb -s $S shell sleep 2
adb -s $S logcat -d -v tag -s CPATK:I CPLAB:I
```

![제3자 앱 io.seika.cpattack uid=10185가 content://io.seika.cplab.users/users에서 3 rows와 토큰 세 개를 읽고, guarded와 private provider에서는 ProcessRecord{… io.seika.cpattack/u0a185} 기준 Permission Denial을 받은 logcat](/assets/img/android-mastery/p1c18/06-device-attacker-query.png)

provider 쪽 로그 `I/CPLAB: vuln query, caller=io.seika.cpattack sql=SELECT * FROM users`가 호출자 패키지를 그대로 보여 준다. admin의 email이 `attacker@lab.test`로 바뀌어 있는 것은 아래 SQL 주입 실험의 `update`가 먼저 돌았기 때문이다.

"아무 앱이나"에는 단서가 하나 붙는다. targetSdk 30 이상인 앱은 패키지 가시성 때문에 `<queries>` 없이는 provider를 찾지도 못한다. `<queries>`만 뺀 `cpblind`(uid 10186)로 같은 요청을 보내면 세 authority 모두 `E/ActivityThread: Failed to find provider info for io.seika.cplab.users`가 찍히고 `ContentResolver.query`가 `null`을 돌려준다(실행은 `adb -s $S shell am start -S -W -n io.seika.cpblind/io.seika.cpattack.Main --es mode query`, [`ActivityThread.java` 7086행 부근](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/app/ActivityThread.java#7080)).

![<queries>가 없는 io.seika.cpblind uid=10186이 io.seika.cplab.users, .users.guarded, .users.private 각각에 대해 E/ActivityThread Failed to find provider info를 받고 query 결과가 null (provider not found)인 logcat](/assets/img/android-mastery/p1c18/12-device-blind.png)

`<queries>`가 막는 것은 provider를 찾는 단계뿐이다. 매니페스트에 `<package android:name="io.seika.cplab" />` 한 줄을 넣은 `cpattack`은 그 뒤 exported·권한 검사까지 통과해 위에서처럼 그대로 읽었다.

## 호출자가 WHERE 절을 쓰는 provider에서 SQL 주입이 뜻하는 것

처음에 SQL 주입 예로 떠올린 것은 `--where "name='a' OR '1'='1'"` 같은 조건 무력화였다. 그런데 exported provider에서는 이게 주입이 아니다. `content query --where`로 넘긴 문자열은 provider의 `selection` 인자이고, 취약 provider는 그걸 받아 `SQLiteDatabase.query`에 넘긴다. 호출자가 WHERE 절 전체를 처음부터 직접 쓰는 셈이라 "조건을 참으로 만든다"는 말이 성립하지 않는다. 그냥 `--where "1=1"`이면 된다.

취약 provider의 `query`는 이렇게 생겼다(`UserProvider.java` 실제 37~51행).

```java
        if (seg.size() == 3 && "name".equals(seg.get(1))) {
            String name = seg.get(2); // already percent-decoded by Uri
            if (qb == null) {
                String sql = "SELECT _id, name, email FROM users WHERE name = '" + name + "'";
                Log.i(TAG, label() + " query by name, caller=" + who + " sql=" + sql);
                return db.rawQuery(sql, null);
            }
            Log.i(TAG, label() + " query by name, caller=" + who + " name=? arg=" + name);
            return qb.query(db, projection, "name = ?", new String[] {name}, null, null, sortOrder);
        }
        if (qb == null) {
            String sql = SQLiteQueryBuilder.buildQueryString(false, "users", projection, selection,
                    null, null, sortOrder, null);
            Log.i(TAG, label() + " query, caller=" + who + " sql=" + sql);
            return db.query("users", projection, selection, selectionArgs, null, null, sortOrder);
```

`SQLiteDatabase.query`는 [`queryWithFactory`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/database/sqlite/SQLiteDatabase.java#1556)에서 [`SQLiteQueryBuilder.buildQueryString`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/database/sqlite/SQLiteQueryBuilder.java#373)으로 SQL을 만든다. 373~399행을 보면 projection의 열 이름은 `appendColumns`로, selection은 `" WHERE "` 뒤에 손대지 않고 붙는다. 로그에 찍히는 SQL은 provider가 같은 함수로 만든 문자열이라 실제 실행된 문장과 같다.

그래서 이 provider에서 문제가 되는 건 provider가 내주려던 범위 밖이다. `users`만 열어 둔 provider로 `secrets` 테이블을 읽을 수 있는지, URI 경로처럼 원래 값으로만 쓰여야 할 입력이 SQL 문법이 되는지를 봤다.

```bash
adb -s $S logcat -c
adb -s $S shell 'content query --uri content://io.seika.cplab.users/users --where "1=0 UNION SELECT _id,k,v,0 FROM secrets"'
adb -s $S shell 'content query --uri content://io.seika.cplab.users/users --projection "name:(SELECT v FROM secrets)"'
adb -s $S shell 'content query --uri content://io.seika.cplab.users/users/name/x%27%20UNION%20SELECT%20_id,k,v%20FROM%20secrets--'
adb -s $S shell 'content update --uri content://io.seika.cplab.users/users --bind email:s:attacker@lab.test --where "_id=1"'
adb -s $S shell 'content query --uri content://io.seika.cplab.users/users --projection _id:name:email --where "_id=1"'
adb -s $S logcat -d -v tag -s CPLAB:I
```

![selection의 UNION으로 name=api_key, email=lab-apikey-0000-fake 행이 나오고, projection 서브쿼리로 세 행 모두에 lab-apikey-0000-fake가 붙고, 이름 경로 주입으로 api_key 행이 나오고, content update 뒤 admin email이 attacker@lab.test로 바뀐 터미널과 CPLAB 로그의 실제 SQL](/assets/img/android-mastery/p1c18/04-device-sqli.png)

selection에 붙인 `UNION SELECT _id,k,v,0 FROM secrets`는 `users`의 열 이름을 빌려 `Row: 0 _id=1, name=api_key, email=lab-apikey-0000-fake, token=0`으로 돌아왔다. projection 쪽은 `content`가 `:`로 열을 나누므로([Content.java 393행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/cmds/content/src/com/android/commands/content/Content.java#393)) `name:(SELECT v FROM secrets)`가 열 두 개가 되고, 두 번째 열이 모든 행에 API 키를 실어 왔다.

세 번째가 고전적인 주입이다. 경로 세그먼트는 `Uri`가 퍼센트 디코딩해서 주므로 `x%27%20UNION…`은 provider 안에서 `x' UNION SELECT _id,k,v FROM secrets--`가 되고, 로그의 SQL은 `WHERE name = 'x' UNION SELECT _id,k,v FROM secrets--'`다. 끝의 따옴표는 주석으로 사라졌다. URI 경로로 이름 하나를 받는 코드라 selection처럼 SQL 입력으로 의식되지 않는다.

쓰기도 막혀 있지 않았다. `.users`에는 읽기·쓰기 권한이 하나도 없어서 `update`가 그대로 통과했고, admin의 email이 `attacker@lab.test`가 된 값은 이후 모든 캡처에 남아 있다. `readPermission`만 달고 `writePermission`을 빠뜨린 provider는 따로 만들어 재지 않았다. 소스로 보면 쓰기도 같은 결과일 것으로 보인다. provider를 여는 단계에서는 [`ContentProviderHelper` 1537~1541행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ContentProviderHelper.java#1537)이 `writePermission`이 `null`이면 읽기 권한 검사에 실패해도 provider를 열어 주고, [`ContentProvider.enforceWritePermissionInner`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/ContentProvider.java#885)는 쓰기 권한이 `null`이면 `allowDefaultWrite`를 참으로 두고(911행) 그대로 허용한다(935행).

## setStrict 하나로는 서브쿼리가 남았다

`SQLiteQueryBuilder`에는 이런 입력을 거르는 모드가 있다. 이름만 보면 `setStrict(true)`로 충분할 것 같아서 그것부터 켜 봤고, 이어서 projection map과 `setStrictColumns`, `setStrictGrammar`를 모두 켠 provider를 비교했다. 뒤의 두 메서드는 API 29에서 추가됐다. 두 provider의 설정 코드는 이렇다(`StrictProvider.java`, `GrammarProvider.java`의 `buildFor`).

```java
// StrictProvider
        SQLiteQueryBuilder qb = new SQLiteQueryBuilder();
        qb.setTables("users");
        qb.setStrict(true);
        return qb;

// GrammarProvider (publicColumns() = _id, name, email 세 열만 담은 projection map)
        SQLiteQueryBuilder qb = new SQLiteQueryBuilder();
        qb.setTables("users");
        qb.setProjectionMap(publicColumns());
        qb.setStrict(true);
        qb.setStrictColumns(true);
        qb.setStrictGrammar(true);
        return qb;
```

같은 공격을 두 provider에 차례로 보냈다. strict 쪽에는 서브쿼리 결과를 참·거짓으로만 돌려받는 길이 비교를 하나 더 넣었다.

```bash
adb -s $S shell 'content query --uri content://io.seika.cplab.users.strict/users --where "1=0 UNION SELECT _id,k,v,0 FROM secrets"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.strict/users --where "_id=1 AND (SELECT length(v) FROM secrets)=20"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.strict/users --where "_id=1 AND (SELECT length(v) FROM secrets)=19"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.strict/users --projection "name:(SELECT v FROM secrets)"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.grammar/users --where "1=0 UNION SELECT _id,k,v,0 FROM secrets"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.grammar/users --where "_id=1 AND (SELECT length(v) FROM secrets)=20"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.grammar/users --projection "name:(SELECT v FROM secrets)"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.grammar/users/name/x%27%20UNION%20SELECT%20_id,k,v%20FROM%20secrets--' 2>&1 | grep -m1 -E "Row:|Exception|No result"
adb -s $S shell 'content query --uri content://io.seika.cplab.users.grammar/users --where "_id=2"' 2>&1 | grep -m1 -E "Row:|Exception|No result"
```

![strict provider에서 UNION은 near "UNION": syntax error와 함께 WHERE (1=0 UNION …)로 괄호에 싸인 SQL이 보이지만 length 비교 =20은 admin 행, =19는 No result found, projection 서브쿼리는 lab-apikey-0000-fake를 돌려주고, grammar provider에서는 Invalid token SELECT 두 번, Invalid column (SELECT v FROM secrets), 이름 경로 No result found, _id=2는 name=alice, _id=2, email만 나온 터미널](/assets/img/android-mastery/p1c18/05-device-strict.png)

`setStrict`만 켠 provider에서 UNION은 `SQLiteException: near "UNION": syntax error`로 실패했다. 예외 메시지의 SQL이 `SELECT * FROM users WHERE (1=0 UNION SELECT _id,k,v,0 FROM secrets)`인 데서 동작 방식이 보인다. [`SQLiteQueryBuilder` 553~578행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/database/sqlite/SQLiteQueryBuilder.java#553)은 selection을 괄호 없이 한 번 검증하고, 실행은 괄호로 감싼 문장으로 한다. 괄호 안에서 문장을 끝내고 UNION을 이어 붙이면, 괄호 없는 검증 단계나 괄호로 감싼 실행 단계 중 한쪽에서 문법 오류가 난다.

괄호 안에 얌전히 머무는 서브쿼리는 문법이 깨지지 않는다. `(SELECT length(v) FROM secrets)=20`은 admin 행을 돌려줬고 `=19`는 `No result found.`였다. 행이 나오느냐 마느냐로 비밀 값에 대한 참·거짓 질문 하나에 답을 받는 구조다. 이번에는 길이만 확인했지만 `substr`로 한 글자씩 비교하면 같은 방식으로 값을 끌어낼 수 있다. projection 서브쿼리는 `setStrict`가 projection을 검사하지 않아서 API 키를 그대로 돌려줬다.

projection map과 strict 옵션을 모두 켠 provider는 다르게 반응했다. UNION과 길이 비교 모두 `IllegalArgumentException: Invalid token SELECT`로 거부됐다. 처음에는 UNION 쪽이 `Invalid token UNION`으로 걸릴 거라고 봤다. 실제로는 UNION은 차단 목록에 없는 키워드라 그대로 통과했고, 뒤따르는 `SELECT`에서 걸렸다. [`enforceStrictGrammar`와 `enforceStrictToken`(786~826행)](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/database/sqlite/SQLiteQueryBuilder.java#786)은 selection을 토큰으로 쪼개 검사하는데, 811~821행의 switch가 막는 키워드는 `SELECT`, `FROM`, `WHERE`, `GROUP`, `HAVING`, `WINDOW`, `VALUES`, `ORDER`, `LIMIT`뿐이다. projection 서브쿼리는 `Invalid column (SELECT v FROM secrets)`로 막혔고, 이름 경로는 `?`로 바인딩돼 `x' UNION …` 전체가 그냥 이름 문자열로 비교된 끝에 `No result found.`가 나왔다. 마지막 줄 `Row: 0 name=alice, _id=2, email=alice@lab.test`에는 `token`이 없다. projection map에 없는 열은 아예 고를 수 없어서다. 열 순서가 `name, _id, email`인 것은 `HashMap`으로 만든 map의 순회 순서로 보인다.

그래도 grammar provider는 `_id`, `name`, `email` 세 열을 누구에게나 전부 내준다. 이걸 막은 건 signature 권한을 단 `.users.guarded`뿐이었다.

## openFile의 경로 세그먼트는 %2F를 풀어서 준다

파일을 내주는 provider는 `openFile`에서 URI를 파일 경로로 바꾼다. 취약 버전 `FileShareProvider`는 마지막 경로 세그먼트를 기준 폴더에 이어 붙이기만 한다(실제 19~23행).

```java
    protected File resolve(Uri uri) throws FileNotFoundException {
        Db.get(getContext()); // make sure the lab files exist
        File base = new File(getContext().getFilesDir(), "public");
        return new File(base, uri.getLastPathSegment()); // getLastPathSegment() decodes %2F
    }
```

`/`로 나뉘는 URI에서 마지막 세그먼트 하나로는 상위 폴더로 못 갈 것 같지만, [`Uri`의 경로 세그먼트](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/net/Uri.java#2195)는 퍼센트 디코딩된 값이다(2210, 2218행). `..%2F..%2Fshared_prefs%2Fsession.xml`은 URI 수준에서는 세그먼트 하나이고, `getLastPathSegment()`가 돌려주는 값은 `../../shared_prefs/session.xml`이다.

```bash
adb -s $S shell content read --uri content://io.seika.cplab.files/readme.txt
adb -s $S shell content read --uri content://io.seika.cplab.files/..%2F..%2Fshared_prefs%2Fsession.xml
adb -s $S shell content read --uri content://io.seika.cplab.files.safe/..%2F..%2Fshared_prefs%2Fsession.xml 2>&1 | head -2
```

![셸에서 content read로 io.seika.cplab.files의 readme.txt를 읽고, ..%2F..%2Fshared_prefs%2Fsession.xml로 auth_token lab-session-token-fake가 든 session.xml 전체를 받고, files.safe에서는 SecurityException: outside /data/data/io.seika.cplab/files/public이 난 터미널](/assets/img/android-mastery/p1c18/08-device-shell-read.png)

셸이 `session.xml`을 통째로 받았다. 이때 provider 로그에는 `files-vuln openFile caller=com.android.shell seg=../../shared_prefs/session.xml -> /data/user/0/io.seika.cplab/files/public/../../shared_prefs/session.xml`이 찍혔다. 파일은 provider 프로세스가 자기 권한으로 열어 파일 디스크립터로 넘기므로 셸에게 그 파일의 접근 권한이 없어도 상관없다. 측정 전에는 셸 도메인이 다른 앱의 `app_data_file` fd를 받는 걸 SELinux가 막을 수도 있다고 봤는데, 읽기는 성공했고 실습 패키지에 대한 avc 거부도 로그에 없었다.

제3자 앱 `cpattack`에서도 똑같이 읽혔다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.cpattack/.Main --es mode file | grep -E "Status|Activity"
adb -s $S shell sleep 2
adb -s $S logcat -d -v tag -s CPATK:I CPLAB:I
```

![cpattack uid=10185 mode=file 로그: I/CPLAB files-vuln openFile seg=../../shared_prefs/session.xml이 /data/user/0/io.seika.cplab/files/public/../../shared_prefs/session.xml로 풀리고 이어서 CPATK가 auth_token lab-session-token-fake가 든 XML을 READ, files-safe는 W/CPLAB refused 줄과 함께 SecurityException outside /data/data/io.seika.cplab/files/public을 낸 터미널](/assets/img/android-mastery/p1c18/07-device-attacker-file.png)

호출자 패키지가 `io.seika.cpattack`으로 바뀐 것 말고는 셸 때와 같은 경로가 찍혔다. 취약 provider는 `/data/user/0/...`이 붙은 정규화 전 경로를, 고친 provider는 `/data/data/...`로 시작하는 canonical 경로를 남긴다. 앱 화면에도 결과를 그대로 찍게 해 두었다.

![CpAttack 앱 화면에 uid=10185 mode=file, readme.txt READ, ..%2F..%2Fshared_prefs%2Fsession.xml READ 결과로 auth_token lab-session-token-fake가 든 XML, files.safe의 readme READ와 traversal 시도의 SecurityException outside /data/data/io.seika.cplab/files/public이 출력된 에뮬레이터 화면](/assets/img/android-mastery/p1c18/07s-device-attacker-file-screen.png)

고친 버전은 경로를 canonical 형태로 풀고 나서 기준 폴더 아래인지 확인한다.

```java
        File f = super.resolve(uri);
        try {
            String base = new File(getContext().getFilesDir(), "public").getCanonicalPath();
            String path = f.getCanonicalPath();
            if (!path.startsWith(base + File.separator)) {
                throw new SecurityException("outside " + base + ": " + path);
            }
            return new File(path);
```

`base + File.separator`의 구분자가 중요하다. 이게 빠진 검사가 다음 절의 androidx 버그다. 위 로그에서 본 것처럼 `getFilesDir()`가 주는 `/data/user/0/...`은 canonical 경로로 풀면 `/data/data/...`가 된다. 한쪽만 canonical로 바꾸고 다른 쪽은 그대로 비교하면 정상 파일까지 거부하거나, 반대로 엉뚱한 쪽을 통과시키게 된다.

## androidx FileProvider는 1.12.0까지 문자열 접두사만 비교했다

직접 `openFile`을 짜지 말고 androidx `FileProvider`를 쓰라는 조언은 맞다. 다만 "FileProvider는 `getUriForFile`에서 canonical 경로로 정규화하니 `../`에 안전하다"는 설명은 틀린 데가 있다.

우선 들어오는 URI를 검사하는 함수는 `getFileForUri`다. `getUriForFile`은 앱이 자기 파일을 내보낼 때 URI를 만드는 쪽이고, 다른 앱이 보낸 URI를 `openFile`·`query`에서 파일로 바꾸는 쪽이 `getFileForUri`다. 그리고 그 검사는 오랫동안 구분자 없는 문자열 접두사 비교였다. 수정 직전 커밋의 [`getFileForUri`](https://android.googlesource.com/platform/frameworks/support/+/2a45e82338963ea50c1dffa659b8d54bc1e3b553/core/core/src/main/java/androidx/core/content/FileProvider.java#905)는 이렇다.

```java
// androidx FileProvider.java, 수정 전 2a45e823, 898~906행
            File file = new File(root, path);
            try {
                file = file.getCanonicalFile();
            } catch (IOException e) {
                throw new IllegalArgumentException("Failed to resolve canonical path for " + file);
            }

            if (!file.getPath().startsWith(root.getPath())) {
                throw new SecurityException("Resolved path jumped beyond configured root");
```

root가 `.../files/docs`면 `.../files/docs-private/secret.txt`도 이 문자열로 시작한다. 2023년 9월 커밋 [e4a912b4 "Address path transversal vulnerability in FileProvider"](https://android.googlesource.com/platform/frameworks/support/+/e4a912b47c78d13c476b36b98304479c3151fc7d)가 이걸 `belongsToRoot`로 바꿨다.

![googlesource의 androidx 커밋 e4a912b47c78 diff: 메시지 Address path transversal vulnerability in FileProvider와 Bug: 268225113, getUriForFile의 path.startsWith(rootPath)와 getFileForUri의 file.getPath().startsWith(root.getPath())가 belongsToRoot(...)로 바뀐 두 hunk, rootPath="files/data"와 filePath="files/data2" 예를 든 주석과 return filePath.equals(rootPath) 또는 filePath.startsWith(rootPath + '/')](/assets/img/android-mastery/p1c18/01-src-androidx-fileprovider-fix.png)

주석이 든 예(`files/data`와 `files/data2`)가 이번 실험의 `docs`와 `docs-private` 관계 그대로다. 이 수정이 어느 릴리스부터 들어갔는지는 Google Maven의 배포 AAR을 받아 `javap`로 확인했다.

```bash
for v in 1.12.0 1.13.0 1.15.0 1.16.0; do curl -sfO https://dl.google.com/android/maven2/androidx/core/core/$v/core-$v.aar && unzip -q -o core-$v.aar classes.jar -d core-$v; done
for v in 1.12.0 1.13.0 1.15.0 1.16.0; do echo "== core $v"; javap -p -c -constants -classpath core-$v/classes.jar 'androidx.core.content.FileProvider$SimplePathStrategy' | grep -E '(getUriForFile|getFileForUri|boolean belongsToRoot)\(|String\.(startsWith|equals)|Method belongsToRoot|Unable to find path|jumped beyond' | sed -E 's/ +\/\/ /  \/\/ /; s/#[0-9]+ +//'; done
```

![androidx.core 1.12.0·1.13.0·1.15.0·1.16.0 AAR의 FileProvider$SimplePathStrategy를 javap로 본 터미널: 1.12.0은 getUriForFile과 getFileForUri가 String.startsWith를 직접 호출하고, 1.13.0과 1.15.0은 belongsToRoot(String.equals와 String.startsWith)를 호출하며, 1.16.0은 belongsToRoot에 startsWith만 남고 Unable to find path from root: 문자열이 새로 생김](/assets/img/android-mastery/p1c18/02-host-fileprovider-bisect.png)

1.12.0은 두 메서드 모두 `String.startsWith`를 직접 부른다. 1.13.0부터 `belongsToRoot`가 생겼고 그 안에 `equals`와 `startsWith`가 있다. 1.16.0에서는 `equals`가 빠지고 `Unable to find path from root:` 문자열이 생겼는데, 2024년 10월의 후속 커밋 [2c4649c9](https://android.googlesource.com/platform/frameworks/support/+/2c4649c9baca7ee2a3a09619b95d1cf5c9bd74a3)가 root 폴더 자체를 가리키는 URI까지 거부하도록 바꾼 결과다. 현재 main의 [`getFileForUri`와 `belongsToRoot`(930~973행)](https://android.googlesource.com/platform/frameworks/support/+/09cc9cba1038cd29b8dd06d859cc69f8c121c113/core/core/src/main/java/androidx/core/content/FileProvider.java#930)는 `filePath.startsWith(rootPath + '/')`만 남겨 두었다.

기기에서 차이를 보려고 같은 앱을 1.12.0(`fpold`)과 1.16.0(`fpnew`)으로 빌드했다. 경로 설정은 둘 다 `files/docs/` 하나만 여는 좁은 설정이고, 비교용으로 `root-path`를 쓰는 두 번째 provider(`.wide`)를 붙였다.

```xml
<!-- res/xml/paths_narrow.xml -->
<paths>
    <files-path name="docs" path="docs/" />
</paths>
<!-- res/xml/paths_wide.xml -->
<paths>
    <root-path name="root" path="" />
</paths>
```

FileProvider는 exported로 둘 수 없다. [`attachInfo`](https://android.googlesource.com/platform/frameworks/support/+/09cc9cba1038cd29b8dd06d859cc69f8c121c113/core/core/src/main/java/androidx/core/content/FileProvider.java#626)가 exported면 `Provider must not be exported`, `grantUriPermissions`가 없으면 `Provider must grant uri permissions`를 던진다(632, 635행). 그래서 먼저 앱 자신이 자기 FileProvider를 부르는 `SelfTest` 액티비티로 경로 로직만 따로 봤다. 같은 앱이니 권한 검사는 통과하고, 결과를 가르는 건 FileProvider의 경로 처리뿐이다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.fpold/io.seika.fplab.SelfTest | grep -E "Status"
adb -s $S shell am start -S -W -n io.seika.fpnew/io.seika.fplab.SelfTest | grep -E "Status"
adb -s $S shell sleep 2
adb -s $S logcat -d -v tag -s FPLAB:I
```

![FPLAB 로그: androidx.core 1.12.0인 fpold는 docs/..%2Fdocs-private%2Fsecret.txt를 READ "secret.txt: PRIVATE, lives next to docs/"로 읽고, getUriForFile이 docs-private 파일을 content://io.seika.fpold.files/docs/private/secret.txt로 바꾸며, docs/..%2Fdocs는 EISDIR, 1.16.0인 fpnew는 같은 요청 셋을 Resolved path jumped beyond configured root로 거부하고, 두 버전 모두 wide(root-path)로 shared_prefs/session.xml을 읽은 터미널](/assets/img/android-mastery/p1c18/09-device-fileprovider-selftest.png)

결과를 나란히 놓으면 이렇다.

| 요청 | 1.12.0 (`fpold`) | 1.16.0 (`fpnew`) |
|---|---|---|
| open `docs/..%2Fdocs-private%2Fsecret.txt` | READ `secret.txt: PRIVATE, lives next to docs/` | `Resolved path jumped beyond configured root` |
| open `docs/..%2F..%2Fshared_prefs%2Fsession.xml` | `Resolved path jumped beyond configured root` | 같음 |
| open `docs/..%2Fdocs` (root 폴더 자체) | `IOException: read failed: EISDIR` | `Resolved path jumped beyond configured root` |
| `getUriForFile(files/docs-private/secret.txt)` | `content://io.seika.fpold.files/docs/private/secret.txt` | `Failed to find configured root that contains …` |

옆 폴더로 한 칸 빠지는 `..%2Fdocs-private`는 1.12.0에서 통과했고, 두 칸 올라가 `shared_prefs`로 가는 흔한 테스트는 두 버전 모두 막았다. root 폴더 자체는 1.12.0에서 열리기까지 하고 디렉터리라서 읽기에서 `EISDIR`로 실패했다.

`getUriForFile` 행은 같은 버그의 반대편이다. [수정 전 `getUriForFile`](https://android.googlesource.com/platform/frameworks/support/+/2a45e82338963ea50c1dffa659b8d54bc1e3b553/core/core/src/main/java/androidx/core/content/FileProvider.java#856)은 접두사로 root를 고른 다음 `path.substring(rootPath.length() + 1)`로 root 뒤를 잘라 낸다(856~877행). `docs-private/secret.txt`에서 `docs` 다음 글자인 `-`를 구분자로 여겨 잘라 버리니 `docs/private/secret.txt`라는, 존재하지 않는 파일을 가리키는 URI가 나왔다.

## 폴더 공유용 prefix grant 하나로 옆 폴더까지 읽혔다

같은 앱 안의 호출로는 버그가 있다는 것만 보인다. 제3자 앱이 여기에 닿으려면 URI 권한을 받아야 한다. 여기서 "이 폴더를 공유한다"는 흔한 패턴을 썼다. `ShareDocsActivity`는 `docs` URI에 읽기 권한과 prefix 플래그를 붙여 돌려준다(실제 18~20행).

```java
        Uri docs = Uri.parse("content://" + getPackageName() + ".files/docs");
        Intent r = new Intent().setData(docs).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
```

`cpattack`은 grant를 받기 전에 한 번 읽어 보고, `startActivityForResult`로 `ShareDocsActivity`를 부른 뒤, 받은 grant로 세 경로를 연다.

```bash
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.cpattack/.Main --es mode grant --es target io.seika.fpold | grep -E "Status"
adb -s $S shell sleep 3
adb -s $S shell am start -S -W -n io.seika.cpattack/.Main --es mode grant --es target io.seika.fpnew | grep -E "Status"
adb -s $S shell sleep 3
adb -s $S logcat -d -v tag -s CPATK:I FPLAB:I
```

![cpattack uid=10185이 grant 전에는 not exported from UID 10180/10181로 거부되고, ShareDocs prefix grant 뒤 result flags=0x81을 받은 다음 fpold에서는 report.txt와 옆 폴더 docs-private의 secret.txt를 READ하고 깊은 traversal은 거부되며, fpnew에서는 report.txt만 READ하고 옆 폴더와 깊은 traversal 모두 Resolved path jumped beyond configured root인 logcat](/assets/img/android-mastery/p1c18/10-device-prefix-grant.png)

grant 전에는 두 버전 모두 `not exported from UID 10180`(`10181`)로 막혔다. grant의 플래그는 `0x81`, `FLAG_GRANT_READ_URI_PERMISSION`(0x1)과 `FLAG_GRANT_PREFIX_URI_PERMISSION`(0x80)이다. 그 뒤 1.12.0 앱에서는 공유된 `docs/report.txt`와 함께 공유한 적 없는 `docs-private/secret.txt`까지 읽혔다. 1.16.0 앱은 공유한 파일만 내줬다.

시스템이 이 URI를 grant 범위 안으로 본 이유는 [`UriGrantsManagerService` 1294~1302행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/uri/UriGrantsManagerService.java#1294)에 있다.

```java
        // No exact match, look for prefixes
        final int N = perms.size();
        for (int i = 0; i < N; i++) {
            final UriPermission perm = perms.valueAt(i);
            if (perm.uri.prefix && grantUri.uri.isPathPrefixMatch(perm.uri.uri)
                    && perm.getStrength(modeFlags) >= minStrength) {
                return true;
            }
        }
```

[`isPathPrefixMatch`(Uri.java 2429~2446행)](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/net/Uri.java#2429)는 디코딩된 경로 세그먼트를 앞에서부터 비교한다. `docs/..%2Fdocs-private%2Fsecret.txt`의 세그먼트는 `docs`와 `../docs-private/secret.txt` 두 개이고, 첫 세그먼트가 grant의 `docs`와 같으니 통과다. 시스템은 세그먼트 안의 `../`를 해석하지 않으므로, 나머지 판정은 FileProvider의 `getFileForUri`가 맡는다.

grant 기록도 확인했다. 위 두 명령을 마친 직후의 `dumpsys activity permissions`에는 fpnew 쪽 `UriPermission{… content://io.seika.fpnew.files/docs [user 0] [prefix]}` 하나만 있었다. 이 grant는 받은 액티비티가 소유하는데, 두 번째 `am start -S`가 `cpattack`을 강제 종료하면서 fpold에서 받은 첫 grant가 함께 사라진 것으로 보인다. 그래서 fpold grant만 다시 받고 바로 덤프했다.

```bash
adb -s $S shell am start -S -W -n io.seika.cpattack/.Main --es mode grant --es target io.seika.fpold | grep Status
adb -s $S shell dumpsys activity permissions | tr -d '\r' | grep -B1 -A6 seika
```

```
  * UID 10185 holds:
    UriPermission{484fea1 content://io.seika.fpold.files/docs [user 0] [prefix]}
      targetUserId=0 sourcePkg=io.seika.fpold targetPkg=io.seika.cpattack
      mode=0x1 owned=0x1 global=0x0 persistable=0x0 persisted=0x0
      readOwners:
        * ActivityRecord{aecfc8d u0 io.seika.cpattack/.Main} t280}
```

grant가 걸린 URI는 `docs`까지이고 `[prefix]` 표시가 붙어 있다. `docs-private`에 대한 grant는 어디에도 없다. 그런데도 옆 폴더 파일이 열린 것은 시스템의 세그먼트 비교와 1.12.0 FileProvider의 문자열 접두사 검사가 둘 다 이 URI를 통과시켰기 때문이다.

`root-path`는 이 버그와 별개의 위험이다. androidx 문서의 [클래스 설명](https://developer.android.com/reference/androidx/core/content/FileProvider)에는 `files-path`, `cache-path`, `external-path` 같은 태그만 나오고 `root-path`는 없지만, 소스에는 [`TAG_ROOT_PATH = "root-path"`(358행)와 `DEVICE_ROOT = new File("/")`(371행)](https://android.googlesource.com/platform/frameworks/support/+/09cc9cba1038cd29b8dd06d859cc69f8c121c113/core/core/src/main/java/androidx/core/content/FileProvider.java#358)가 있다. 위 SelfTest 캡처에서 `.wide` provider는 두 버전 모두 `getUriForFile`로 `session.xml`을 `content://io.seika.fpnew.wide/root/data/data/io.seika.fpnew/shared_prefs/session.xml` 같은 URI로 바꿔 줬다. 읽기는 같은 꼴의 다른 URI, `…/root/data/user/0/io.seika.fpnew/shared_prefs/session.xml`로 했고 성공했다(`getUriForFile`이 돌려준 URI 자체를 열어 보지는 않았다). `root-path`의 root는 `/`라서 `belongsToRoot`를 고친 1.16.0도 이 URI를 통과시켰다. 그 URI가 밖으로 나가느냐는 앱이 grant를 어떻게 주느냐에 달렸다.

## exported 기본값을 정하는 건 targetSdk다

`android:exported`를 적지 않은 provider의 기본값을 "API 17 이전 기기는 true"라고 외워 두기 쉬운데, 현재 기기에서 그 값을 정하는 건 앱의 targetSdk다. [`ParsedProviderUtils` 87~93행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/component/ParsedProviderUtils.java#87)은 이렇다.

```java
            // For compatibility, applications targeting API level 16 or lower
            // should have their content providers exported by default, unless they
            // specify otherwise.
            provider.setSyncable(sa.getBoolean(
                    R.styleable.AndroidManifestProvider_syncable, false))
                    .setExported(sa.getBoolean(R.styleable.AndroidManifestProvider_exported,
                            targetSdkVersion < Build.VERSION_CODES.JELLY_BEAN_MR1));
```

그래서 API 33 기기에 `exported`를 적지 않은 같은 provider를 targetSdk 16과 17로 설치해 셸에서 읽어 봤다. 처음 결과는 예상과 달랐다.

```bash
adb -s $S shell dumpsys package io.seika.cpleg16 | grep -m1 targetSdk
adb -s $S shell content query --uri content://io.seika.cpleg16.data/x 2>&1 | head -2
adb -s $S shell dumpsys package io.seika.cpleg17 | grep -m1 targetSdk
adb -s $S shell content query --uri content://io.seika.cpleg17.data/x 2>&1 | head -2
```

![첫 실행: targetSdk=16인 cpleg16의 content query가 java.lang.IllegalStateException: Could not find provider: io.seika.cpleg16.data로 실패하고, targetSdk=17인 cpleg17은 not exported from UID 10184로 Permission Denial이 난 터미널](/assets/img/android-mastery/p1c18/11a-device-legacy-before-review.png)

targetSdk 17은 예상대로 `not exported`였지만 16에서는 권한 거부 대신 `Could not find provider`가 나왔다. provider는 `dumpsys package`에 등록돼 있었고 앱 프로세스는 아예 뜨지 않았다. 조회 직후 맨 위 액티비티는 PermissionController의 `ReviewPermissionsActivity`였다. targetSdk 23 미만 앱은 처음 실행하기 전에 권한 검토를 거쳐야 하는데, [`ContentProviderHelper` 410~416행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ContentProviderHelper.java#410)이 그 검토가 필요한 앱의 provider는 돌려주지 않고 검토 화면을 띄운다. 외부 호출(`r == null`)은 포그라운드로 취급돼 화면이 뜬다([같은 파일 1688~1718행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/am/ContentProviderHelper.java#1688)). targetSdk 17 앱도 검토 대상이지만 그 전에 exported 검사에서 먼저 막혔다.

![PermissionController 화면 "Choose what to allow CpLegacy 16 to access", Notifications 토글이 켜져 있고 아래에 Cancel과 Continue 버튼이 있는 에뮬레이터 화면](/assets/img/android-mastery/p1c18/11r-device-legacy-review-screen.png)

이 화면에서 Continue를 누른 뒤 같은 명령을 다시 돌렸다.

![검토 수락 뒤: cpleg16(targetSdk=16)은 Row: 0 pkg=io.seika.cpleg16, targetSdk=16, note=no android:exported in manifest를 돌려주고, cpleg17(targetSdk=17)은 여전히 not exported from UID 10184로 거부된 터미널](/assets/img/android-mastery/p1c18/11-device-legacy-exported.png)

검토를 마친 targetSdk 16 provider는 셸에 행을 내줬다. 매니페스트에 `exported`를 적지 않은 같은 코드가 targetSdk 한 단계 차이로 열리고 닫힌다. 오래된 앱을 다시 빌드하며 targetSdk를 17 이상으로 올리면 이 provider는 닫힌다. Android 14부터는 targetSdk 23 미만 앱의 설치 자체를 막는다고 [동작 변경 문서](https://developer.android.com/about/versions/14/behavior-changes-all#minimum-target-api-level)에 나와 있다. 이번 API 33 기기에서는 targetSdk 16 앱 설치가 `Success`로 끝났고, API 34 이상에서 설치가 막히는지는 확인하지 않았다.

## 막는 방법과 막혔는지 확인하는 방법

provider를 밖에 열 이유가 없으면 `android:exported="false"`를 명시한다. 기본값에 맡기면 위처럼 targetSdk에 따라 값이 바뀐다. 열어야 한다면 `readPermission`과 `writePermission`을 둘 다 단다. 같은 개발자의 앱끼리 나누는 데이터면 signature 권한이 맞다. 소스대로라면 쓰기 권한을 빠뜨린 provider는 읽기만 막고 쓰기는 열어 둔다. 데이터를 다른 앱에 한 건씩 넘겨야 하는 경우는 provider를 열지 말고 URI grant로 그 URI만 위임한다.

SQL 쪽은 입력이 어디서 오느냐로 나눠 생각한다. URI 경로나 extra처럼 값이어야 하는 입력은 `?`와 `selectionArgs`로 바인딩한다. 호출자에게 selection과 projection을 받는 provider라면 `SQLiteQueryBuilder`에 projection map을 주고 `setStrict`, `setStrictColumns`, `setStrictGrammar`를 함께 켠다(뒤의 둘은 API 29부터). `setStrict`만으로는 괄호 안 서브쿼리와 projection 주입이 남는다는 걸 위에서 봤다. 행 단위로 누가 읽을지는 권한으로 정한다.

파일 쪽은 직접 `openFile`을 짠다면 canonical 경로를 구한 뒤 `기준폴더 + "/"`로 시작하는지 본다. androidx `FileProvider`를 쓴다면 androidx.core를 1.13.0 이상, 가능하면 1.16.0 이상으로 올린다. `root-path`는 쓰지 않고, `<paths>`에는 실제로 공유할 폴더만 적는다. 폴더 단위로 공유하려고 `FLAG_GRANT_PREFIX_URI_PERMISSION`을 쓰는 앱은 특히 라이브러리 버전을 확인할 필요가 있다. prefix grant는 디코딩된 세그먼트만 비교하므로 grant 범위를 지키는 일이 전적으로 provider의 경로 검사에 달린다. 의존성 그래프에서 실제로 해석된 버전은 `./gradlew :app:dependencies`로, 이미 빌드된 APK에서는 함께 묶인 버전 파일을 본다(`unzip -p app.apk META-INF/androidx.core_core.version`). dex 문자열에서 `belongsToRoot`를 찾는 방법은 난독화하지 않은 빌드에서만 단서가 된다. private 메서드라 R8이 이름을 바꾸면 없어도 구버전이라는 뜻이 아니다. 이번에는 두 방법 모두 따로 돌려 보지 않았다.

막혔는지는 위 명령을 그대로 회귀 검사로 쓰면 된다. 확인할 것과 기대값을 모으면 이렇다.

| 확인할 것 | 명령 | 기대 결과 |
|---|---|---|
| 권한 없는 읽기 차단 | `content query --uri content://<authority>/...` (unroot 셸) | `Permission Denial` |
| 쓰기 차단 | `content update --uri ... --bind ...` | `Permission Denial` |
| 다른 테이블 접근 | `--where "1=0 UNION SELECT ..."`, `--projection "name:(SELECT ...)"` | `Invalid token SELECT`, `Invalid column ...` |
| 경로 탈출 | `content read --uri content://<authority>/..%2F..%2Fshared_prefs%2F...` | `SecurityException` |
| 옆 폴더 탈출 | prefix grant 뒤 `docs/..%2Fdocs-private%2F...` | `Resolved path jumped beyond configured root` |

어느 검사든 `adb unroot` 뒤의 셸(`uid=2000`)이나 별도 키로 서명한 앱에서 돌린다(이유는 위 `checkComponentPermission`의 root 분기).

*다음 글: [PendingIntent와 URI grant 실습](/posts/android-lab-p1c19-pendingintent-uri-grant/)*
