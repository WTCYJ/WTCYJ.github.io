---
layout: post
title: "저장소·log·clipboard·backup 점검 — 앱이 비밀을 흘리는 네 곳"
date: 2026-10-28 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Storage, Backup, Clipboard, DataLeak]
excerpt: "앱이 비밀을 어디에 흘리는지 네 곳을 본다 — 평문 shared_prefs·DB(/data/data는 root/run-as로), logcat에 남은 토큰, clipboard로 복사된 민감값(A12부터 읽으면 토스트), allowBackup=true로 클라우드/adb로 빠져나가는 데이터. FBE는 첫 잠금해제 전(BFU)만 지키니 켜져 도는 앱엔 투명하다는 게 핵심이다."
---

앱이 비밀을 흘리는 통로는 대체로 네 곳이다: 저장소, 로그, 클립보드, 백업. 이 글은 그 네 곳을 체계적으로 점검하는 방법과, FBE가 있는데도 왜 라이브 앱은 안 지켜지는지를 정리한 기록이다. 핵심은 `/data/data`가 UID 사설이라 root/run-as로만 열리고, FBE는 첫 잠금해제 전(BFU)만 지키므로 켜져 도는 앱엔 투명하다는 것이다.

> **한 줄 결론**: `/data/data`는 root/run-as로 열고, 평문 shared_prefs·DB·logcat 토큰·clipboard·allowBackup을 점검한다. FBE는 BFU만 지키니 비밀은 Keystore(14장)에 있어야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 저장소·로그·클립보드·백업에서 새는 비밀을 점검한다. 선수 개념은 [adb 증적(2장)](/posts/android-lab-p1c02-adb-evidence-collection/)의 run-as·logcat, [저장소·백업(C44)](/posts/android-concept-atlas-c44-secure-storage-backup/)·[FBE(C43)](/posts/android-concept-atlas-c43-fbe-direct-boot/)다.

## 핵심 개념 — 네 통로

- **내부 저장소**: `/data/data/<pkg>`(=`/data/user/0/<pkg>`) UID 사설(C09) — **root 또는 `run-as <debuggable pkg>`**로. `shared_prefs/*.xml`(평문 XML 기본)·`databases/*.db`. **sqlite3 바이너리는 production user 빌드엔 흔히 없으니** `.db`를 `adb pull` 후 호스트 sqlite3로. `Source-confirmed`
- **로그**: `adb logcat`에 토큰/PII가 남으면 유출(실제 흔한 발견).
- **클립보드**: `ClipboardManager`, **A10(API29) 백그라운드 읽기 차단**, **A12(API31) 읽으면 토스트**. 민감값 복사 여부 점검. `Source-confirmed`
- **백업**: `android:allowBackup` 기본 true → `adb backup -f app.ab <pkg>`로 추출(**게이트는 allowBackup=true**, 역사적으로 debuggable 무관; targetSdk 31+ 비-디버그는 사실상 무력, C44). `fullBackupContent`(pre-12) vs `dataExtractionRules`(A12+, cloud-backup/device-transfer 분리). Keystore 키는 비추출 → 백업에 안 실림. `Source-confirmed`

**신뢰 경계와 위협 모델.** FBE(C43)는 **첫 잠금해제 전(BFU)만** 지킨다 — 켜져 도는 앱/루팅엔 투명하다. 그래서 비밀은 Keystore(14장)에 있어야 한다.

> **[그림 1]** `run-as ... cat shared_prefs/auth.xml`에서 평문 토큰이 보이는 화면(값 마스킹) — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱(평문 토큰·로그·클립보드·allowBackup=true 취약 버전 + 방어 버전)을 대조한다. 유출물은 최소보관.

## 실습 절차와 관측

### 가설
취약 버전은 shared_prefs 평문 토큰·logcat 토큰·adb backup 추출이 성립하고, 방어 버전은 Keystore 래핑·로그 없음·allowBackup=false. `Inferred`

### 절차
1. `run-as`/`adb pull`로 내부 저장소를 열람한다.
2. `.db`를 호스트 sqlite3로 조회한다.
3. `logcat | grep`으로 로그 유출을 확인한다.
4. clipboard 복사 여부를 확인한다(앱 동작 + A12 토스트).
5. `adb backup`으로 백업 노출을 확인한다.

```bash
adb shell run-as com.example.app cat shared_prefs/auth.xml
adb pull /data/data/com.example.app/databases/app.db .; sqlite3 app.db .tables
adb logcat -d | grep -i -E 'token|password|Bearer'
adb backup -f app.ab com.example.app          # allowBackup=true면
```

> **[그림 2]** `adb backup`으로 추출한 백업에서 민감 파일이 보이는 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ adb shell run-as com.example.app cat shared_prefs/auth.xml
<string name="access_token">eyJ...</string>   # 평문 (C44 위반)
```

## Root Cause — 왜 이렇게 되는가

`/data/data` 접근이 root/run-as로 제한되는 것은 C09; FBE가 라이브 앱을 못 지키는 것은 CE 키가 잠금해제 후 상주하기 때문이다(C43). 그래서 저장 자체가 사설이어도 비밀엔 Keystore가 필요하다.

## 방어와 회귀 검증

- (개발자) Keystore 래핑·로그 금지·클립보드 회피·`allowBackup=false`/규칙 제외. 릴리스에서 "logcat에 토큰 없음 + prefs 평문 토큰 없음 + adb backup 비어있음"을 회귀로.
- (연구자) 유출물 최소보관.

**흔한 실패와 처리.** `run-as: not debuggable` → 릴리스 앱이면 root 이미지. `sqlite3: not found` → `.db`를 pull해 호스트에서. adb backup 빈 파일 → targetSdk 31+ 제한.

## 버전 차이와 한계

- 클립보드 A10 백그라운드 차단·A12 토스트, adb backup targetSdk 31+ 제한, EncryptedSharedPreferences deprecated(1.1.0-alpha06)(C44).
- 아키텍처 무관. 내부 저장소는 디버그/루팅 필요.

## 정리

- `/data/data`는 root/run-as, `.db`는 pull 후 호스트 sqlite3.
- FBE는 BFU만 → 비밀은 Keystore.
- adb backup 게이트는 debuggable이 아니라 allowBackup.

**점검 질문** — (1) `/data/data`를 읽는 두 방법은? (2) FBE가 있는데 라이브 앱 비밀이 왜 노출되나? (3) adb backup의 게이트는 debuggable인가 allowBackup인가?

**참고** — [보안 모범사례](https://developer.android.com/privacy-and-security/security-best-practices) · [Auto Backup](https://developer.android.com/guide/topics/data/autobackup) · [C44](/posts/android-concept-atlas-c44-secure-storage-backup/) · [C43](/posts/android-concept-atlas-c43-fbe-direct-boot/)

*다음 글: [Keystore와 BiometricPrompt 검증](/posts/android-lab-p1c14-keystore-biometricprompt/).*
