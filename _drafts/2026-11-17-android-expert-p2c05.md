---
layout: post
title: "Room·DataStore·WorkManager"
date: 2026-11-17 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Room, DataStore, WorkManager, Jetpack]
excerpt: "DataStore는 SharedPreferences의 동시성·일관성 문제를 고쳤을 뿐 암호화하지 않는다. Room·DataStore·WorkManager 세 저장소 모두 기본은 평문이고, WorkManager 입력 Data에 넣은 값은 내부 Room DB(androidx.work.workdb)에 평문으로 남아 재부팅 후에도 살아 있다."
---

Jetpack의 저장 3종 세트 — Room(구조화 DB), DataStore(키-값/타입 설정), WorkManager(지연·보장 백그라운드 작업) — 는 앱 개발자가 매일 쓰는 도구다. 그런데 이 셋을 보안 관점에서 볼 때 가장 자주 틀리는 문장이 하나 있다. "DataStore는 SharedPreferences보다 안전하다." 이 말은 절반만 맞다. DataStore가 고친 것은 동시성과 부분 쓰기(partial write)이지 기밀성이 아니다. 세 라이브러리 모두 데이터를 암호화하지 않는다.

이 글은 자작 앱을 AVD에 올려 Room·DataStore·WorkManager가 각각 디스크 어디에 무엇을 남기는지 직접 뽑아 확인한 기록이다. 세 저장소의 실제 파일 경로를 나열하고, WorkManager 입력 Data에 넣은 표식이 내부 Room DB에 평문으로 남는지, 재부팅 후에도 살아 있는지를 관측한다. 공격이 아니라 "내 앱 데이터가 어느 신뢰 경계 위에 얹혀 있나"를 구조로 이해하는 게 목적이다.

> **한 줄 결론**: 세 라이브러리는 데이터를 암호화하지 않는다. 격리는 커널 UID 샌드박스와 파일 기반 암호화(FBE)가 담당하고, 라이브러리는 앱 프라이빗 저장소 안에서 전부 평문으로 다룬다 — 기밀성이 필요하면 앱이 명시적으로 암호화를 얹어야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

Room·DataStore·WorkManager의 저장 위치와 저장 형식, 그리고 그것이 어떤 위협 모델에서 안전하고 어떤 모델에서 뚫리는지를 다룬다. 코드로 저장소를 만드는 방법이 아니라, 만들어진 데이터가 어디에 어떤 형태로 놓이는지가 초점이다.

선수 개념은 세 가지다. 이 파트 앞 장의 코루틴·Flow가 밑에 깔린다 — DataStore와 WorkManager는 둘 다 코루틴/Flow 기반 API라, 구조적 동시성을 모르면 트랜잭션 경계를 오해한다. 프로세스 격리와 앱 프라이빗 저장소(`/data/data/<pkg>/`)의 UID 샌드박스는 개념지도 Atlas C04에서 다룬 내용이고, 저장 시 암호화(FBE)는 이 격리를 "기기를 잃어버렸을 때"까지 확장한다. 마지막으로, WorkManager가 재부팅을 견디는 이유는 이 파트 뒤쪽에서 다룰 JobScheduler/system_server의 작업 스케줄링과 맞물린다.

전체 구조에서 이 셋은 **앱의 상태가 프로세스 수명을 넘어 살아남는 지점**이다. 화면·ViewModel은 프로세스가 죽으면 사라지지만, 이 세 저장소에 쓴 것은 남는다. 그래서 "무엇을 여기에 쓰느냐"가 곧 "무엇이 디스크에 평문으로 남느냐"가 된다.

## 핵심 개념 — 세 저장소의 위치와 형식

세 라이브러리는 목적이 다르지만, 물리적으로는 전부 앱 프라이빗 디렉터리 아래에 평문 파일로 앉는다.

| 라이브러리 | 물리 파일 | 형식 | 암호화 |
|--|--|--|--|
| Room | `databases/<name>.db` (+ `-wal`, `-shm`) | SQLite | 없음(기본) |
| DataStore(Preferences) | `files/datastore/<name>.preferences_pb` | 프로토버프 직렬화 | 없음 |
| DataStore(Proto) | `files/datastore/<name>.pb` | 사용자 정의 protobuf | 없음 |
| WorkManager | `databases/androidx.work.workdb` | SQLite(내부 Room) | 없음 |

Room은 SQLite 위의 컴파일타임 추상화다. `@Query`에 `:param`으로 넘긴 값은 파라미터 바인딩되고 SQL은 빌드 시 검증되므로 그 경로는 SQL 인젝션에 안전하다. `Source-confirmed` 반대로 `@RawQuery`는 컴파일타임 SQL 검증을 받지 않는다(바인딩 자체는 우회하지 않아 `SimpleSQLiteQuery`의 `bindArgs`로 인자를 그대로 넘길 수 있다). 여기에 사용자 입력을 쿼리 문자열로 직접 이어 붙일 때 SQL 인젝션이 생기며, 인자를 바인딩하면 안전하다 — "Room을 쓰면 SQLi가 막힌다"는 착각의 예외 구멍이 정확히 여기다. `Source-confirmed` Room은 기기가 지원하면 WAL(write-ahead logging) 저널 모드를 기본으로 쓰기 때문에 `.db` 옆에 `-wal`·`-shm` 파일이 함께 생긴다 — 백업·포렌식에서 이 사이드카 파일을 빼먹으면 최근 커밋을 놓친다. `Reported`

DataStore는 SharedPreferences를 대체하지만, 대체한 것은 **동시성과 일관성**이다. 코루틴 위에서 트랜잭션적으로 읽고 쓰며 부분 쓰기로 인한 손상을 막는다. 파일은 여전히 앱의 `files/datastore/`에 평문 protobuf로 앉는다. `Reported` Preferences DataStore는 타입 없는 키-값, Proto DataStore는 스키마를 가진 타입 세이프 저장이라는 차이만 있고 기밀성은 둘 다 제공하지 않는다.

WorkManager는 조금 다른 이유로 여기 낀다. 지연·보장 백그라운드 작업을 관리하려고 **내부에 Room 데이터베이스(`androidx.work.workdb`)를 두고** 작업 명세·상태·입출력 Data를 영속화한다. `Source-confirmed` 입력 `Data`는 크기 제한이 있는 작은 키-값 묶음(약 10KB, `MAX_DATA_BYTES`)인데, 이 값이 workdb에 평문으로 직렬화되어 저장된다. `Reported` 즉 WorkManager 작업에 토큰·식별자 같은 값을 넘기면 그게 디스크의 SQLite에 그대로 남는다.

> **[그림 1]** `adb shell run-as <pkg> ls -l databases files/datastore` 출력에서 Room `.db`(+`-wal`/`-shm`), `androidx.work.workdb`, `<name>.preferences_pb` 세 파일이 나란히 존재하는 터미널 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **로컬 AVD와 자작 앱**으로만 진행한다. 제3자 앱·실서비스·실데이터는 없다. 표식 문자열은 `PLAINTEXT_MARKER_123` 같은 더미이고 실제 비밀은 넣지 않는다. 계측용 이미지(`google_apis` userdebug, x86_64)를 쓰면 디버그 빌드 자작 앱에 `run-as`가 되어 앱 파일을 꺼낼 수 있다 — 남의 앱 데이터에 손대는 것이 아니라 내 앱이 무엇을 남기는지 보는 것이다.

`MAX_DATA_BYTES` 같은 상수와 저장 경로·직렬화 형식은 라이브러리 버전에 묶이므로, 아래 관측은 실측에 쓴 `androidx.work` `2.x.x` · `androidx.room` `2.x.x`(실제 사용 버전으로 교체) 기준이다. `확인 필요`

## 실습 절차와 관측

### 가설
- **가설 A** — Room `.db`, DataStore `.preferences_pb`, WorkManager `androidx.work.workdb` 세 파일 모두 앱 프라이빗 저장소 아래에 평문으로 존재한다. `Inferred`
- **가설 B** — WorkManager 입력 Data에 넣은 표식 문자열이 `strings`로 workdb에서 그대로 보이고, `adb reboot` 후에도 (작업이 아직 실행 안 됐다면) 남아 있다. `Inferred`

### 절차
1. 자작 앱에 Room 엔티티/DAO, Preferences DataStore, 표식을 담은 `OneTimeWorkRequest`를 넣는다.
2. 앱을 실행해 세 저장소에 각각 쓴다(WorkManager는 제약을 걸어 즉시 실행되지 않게 둔다).
3. `run-as`로 `databases/`·`files/datastore/`를 나열한다.
4. workdb와 `.preferences_pb`를 호스트로 뽑아 `strings`로 검사한다.
5. `adb reboot` 후 workdb를 다시 뽑아 표식이 남았는지 확인한다.

```kotlin
// 개념용 표식 — 실제 비밀 금지
val data = workDataOf("marker" to "PLAINTEXT_MARKER_123")
val req = OneTimeWorkRequestBuilder<SyncWorker>()
    .setInputData(data)
    .setConstraints(Constraints(requiredNetworkType = NetworkType.CONNECTED))
    .build()
WorkManager.getInstance(context).enqueue(req)

// Preferences DataStore 쓰기
val KEY = stringPreferencesKey("session")
context.dataStore.edit { it[KEY] = "PLAINTEXT_MARKER_123" }
```

```bash
# 앱 데이터 나열 (디버그 빌드 자작 앱)
adb shell run-as com.example.persistlab ls -l databases files/datastore
# 파일을 호스트로 뽑아 평문 확인
adb exec-out run-as com.example.persistlab cat databases/androidx.work.workdb > workdb.sqlite
strings workdb.sqlite | grep -i marker
adb exec-out run-as com.example.persistlab cat files/datastore/settings.preferences_pb > settings.pb
strings settings.pb
# 재부팅 후 잔존 확인
adb reboot && adb wait-for-device
adb exec-out run-as com.example.persistlab cat databases/androidx.work.workdb | strings | grep -i marker
```

> **[그림 2]** 호스트에서 `strings workdb.sqlite | grep marker`로 WorkManager 입력 Data의 표식이 평문으로 나오는 화면, 그리고 `adb reboot` 후 같은 grep이 여전히 표식을 찍는 대조 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
$ adb shell run-as com.example.persistlab ls -l databases files/datastore
databases:
-rw------- u0_a123 u0_a123  20480 app.db
-rw------- u0_a123 u0_a123  32768 app.db-wal
-rw------- u0_a123 u0_a123  32768 app.db-shm
-rw------- u0_a123 u0_a123  49152 androidx.work.workdb
files/datastore:
-rw------- u0_a123 u0_a123     44 settings.preferences_pb

$ strings workdb.sqlite | grep -i marker
PLAINTEXT_MARKER_123
$ strings settings.pb
session
PLAINTEXT_MARKER_123
```

세 파일이 예상대로 `600`(소유자만 rw) 권한으로 앱 UID(`u0_a123`) 소유 하에 앉아 있고, 표식은 workdb와 DataStore 파일 양쪽에서 평문으로 읽힌다. 재부팅 후에도 workdb의 표식이 그대로면 가설 B가 선다 — WorkManager가 상태를 파일로 영속화하기 때문이다.

## Root Cause — 왜 셋 다 평문인가

세 라이브러리가 암호화를 빼먹은 게 아니다. **책임 계층이 다르다.** 기밀성과 격리는 라이브러리 위가 아니라 아래 — 커널의 UID 샌드박스와 저장 시 FBE — 가 담당한다. 앱 프라이빗 디렉터리는 커널이 UID로 격리하므로 루팅되지 않은 기기에서 다른 앱은 이 파일을 읽지 못하고, 기기 분실 시에는 FBE가 잠금 화면 뒤에서 디스크를 암호화한다. 라이브러리는 이 경계 **안에서** 데이터를 다루므로 평문이 기본이다. "Room/DataStore가 데이터를 지켜준다"는 말은 계층을 착각한 것이다. `Source-confirmed`

WorkManager가 재부팅을 견디는 것도 같은 구조의 결과다. API 23+에서 실제 실행은 JobScheduler(system_server)에 위임한다. JobScheduler 자체는 `setPersisted(true)`로 등록한 job을 `/data/system/job/jobs.xml`에 영속화해 재부팅을 견디지만, WorkManager는 그 영속 플래그 없이 job을 등록하므로 이렇게 등록된 job은 재부팅 시 사라진다 — 대신 WorkManager는 자기 Room DB로 영속성을 직접 관리한다. `Source-confirmed` 즉 작업 명세를 그 DB에 적어 두고, 부팅 완료(`BOOT_COMPLETED`) 시 DB를 읽어 미완 작업을 다시 스케줄한다. `Source-confirmed` 그 대가로 입력 Data가 평문 SQLite에 남는다. 편의(재부팅 생존)와 잔존(평문 영속)은 같은 메커니즘의 앞뒷면이다.

## 방어와 회귀 검증

방어는 위협 모델에 종속된다. "루팅 안 된 내 기기, 백업 안 켬"이면 샌드박스로 충분하고 추가 암호화는 과설계다. 반대로 루팅·포렌식·클라우드 백업 유출을 위협으로 잡으면 앱이 명시적으로 얹어야 한다.

- **Room** — 기밀 DB는 SQLCipher(`SupportFactory`)로 파일 자체를 암호화하고, 키는 KeyStore/StrongBox에 둔다. 사용자 입력을 문자열로 이어 붙인 `@RawQuery`·`SupportSQLiteQuery`는 코드 리뷰에서 SQLi 후보로 잡는다(인자를 바인딩하면 안전하다).
- **WorkManager** — 입력 `Data`에 토큰·PII를 넣지 않는다. 필요하면 식별자만 넘기고 실제 비밀은 KeyStore로 보호되는 별도 저장에서 조회한다. `Data`가 평문 workdb에 남는다는 사실이 이 규칙의 근거다.
- **DataStore** — 민감 설정은 앱단에서 암호화해 넣는다. 참고로 `androidx.security`의 EncryptedFile/EncryptedSharedPreferences는 근래 deprecated 되었으니 채택 전 버전·대안(Tink 직접 사용 등) 확인이 필요하다. `Reported`
- **백업 경계** — `android:allowBackup`과 데이터 추출/백업 규칙을 점검한다. 세 저장소가 전부 평문이므로 자동 백업 범위가 곧 유출 표면이다.
- **회귀 검증** — "workdb에 표식이 평문으로 남는다"를 스냅샷 복원 후에도 재확인하고, 라이브러리 버전을 올린 뒤 저장 파일 경로·형식이 바뀌지 않았는지 `run-as` 나열로 다시 본다.

버전 차이도 있다. JobScheduler 위임은 API 23+ 기준이고 그 아래에서는 AlarmManager+BroadcastReceiver 조합을 쓰므로 잔존 파일 구성이 다를 수 있다. `Reported` `MAX_DATA_BYTES` 같은 상수와 내부 DB 스키마는 라이브러리 버전에 묶이니, 수치를 인용할 땐 사용한 버전을 표기하는 게 안전하다.

## 정리

- Room·DataStore·WorkManager는 전부 앱 프라이빗 저장소에 **평문**으로 앉는다. 격리는 커널 UID 샌드박스와 FBE가, 기밀성은 앱이 얹는 암호화가 담당한다.
- WorkManager는 상태를 내부 Room DB(`androidx.work.workdb`)에 영속화해 재부팅을 견디고, 그 대가로 입력 Data가 평문으로 남는다 — 여기에 비밀을 넣지 않는다.
- Room의 `@Query` 바인딩은 SQLi에 안전하지만 `@RawQuery`·문자열 결합은 예외 구멍이다. DataStore가 고친 것은 동시성이지 기밀성이 아니다.

**점검 질문** — (1) WorkManager 작업에 넘긴 값이 디스크 어디에 어떤 형태로 남는가? (2) "DataStore가 SharedPreferences보다 안전하다"는 어떤 의미에서 참이고 어떤 의미에서 거짓인가? (3) Room을 써도 SQL 인젝션이 뚫리는 경로는 무엇인가?

**참고** — [Room](https://developer.android.com/training/data-storage/room) · [DataStore](https://developer.android.com/topic/libraries/architecture/datastore) · [WorkManager](https://developer.android.com/topic/libraries/architecture/workmanager) · [AndroidX 소스](https://cs.android.com/androidx/platform/frameworks/support)

*다음 글: [OkHttp/Retrofit·모바일 API 설계](/posts/android-expert-p2c06/).*
