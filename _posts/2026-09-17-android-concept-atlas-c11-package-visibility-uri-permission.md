---
layout: post
title: "Android Security Concept Atlas C11 | 가상 실습 보고서 — package visibility·URI permission, 서로를 보고 데이터를 넘기는 법"
date: 2026-09-17 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, PackageVisibility, URIPermission, FileProvider, ContentProvider, queries, ConfusedDeputy, ConceptAtlas, 학습기록]
excerpt: "앱이 다른 앱을 '보는' 것과 다른 앱에 데이터를 '넘기는' 것은 둘 다 UID 경계(C09)를 건너는 일이라 통제됩니다. Android 11부터 설치 앱 목록 열거는 조용히 필터링되고(targetSdk 30 게이트, 예외가 아니라 빈 목록), 특정 앱을 보려면 <queries>를 선언하거나 QUERY_ALL_PACKAGES를 들어야 하죠. 데이터 공유는 전체 권한을 주는 대신 content:// URI 하나에만 임시로 위임하는 URI 권한(FLAG_GRANT_READ/WRITE)으로 - file:// 대신 FileProvider를 쓰는 이유입니다. 그리고 여기 confused-deputy가 삽니다: 악성 발신자가 URI를 피해자 자신의 사적 프로바이더로 겨누면 피해자가 제 파일을 대신 읽어 넘기죠. 내 WebView/딥링크 작업과 직결되는 Tier 1 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r` |
| 관측 결과 | 증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다. |
| 검증 한계 | AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다. |

![C11 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/apps.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C11 — package visibility·URI permission
> **계층**: Tier 1 (앱·패키징) · **난이도**: 중급 · **선수 개념**: C10(권한), C09(UID)
> **성격**: 보완 편.

C10에서 권한은 UID에 부여된다 했습니다. 그런데 앱이 서로를 **보고** 데이터를 **넘길** 때도 UID 경계(C09)를 건넙니다. 그 두 통로 — 가시성과 URI 권한 — 이 이 편이고, 내 WebView/딥링크 작업(C47)의 취약점이 정확히 여기 삽니다.

한 문장으로: **가시성은 "어떤 앱을 볼 수 있나"를, URI 권한은 "전체 권한 없이 URI 하나만 임시로 넘기는 법"을 정하며, 둘 다 UID 경계를 건너는 통제다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **package visibility**(A11/API30): 설치 앱 열거를 **필터링**. `<queries>` 또는 `QUERY_ALL_PACKAGES`.
- **URI permission**: `content://` URI **하나에만** 임시 위임(`FLAG_GRANT_READ/WRITE`). 프로바이더가 opt-in해야.
- **FileProvider**: `file://` 대신 `content://`로 파일 공유하는 표준 프로바이더.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

앱 간 **관찰**(가시성)과 **위임**(URI 권한)의 층입니다. C10(권한)의 위임 대안, C09(UID) 경계 넘기, C17(Binder/IPC) 시행, C47(WebView/딥링크) 공격면과 직결됩니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **가시성**(A11, **targetSdk 30+** 게이트): `getInstalledPackages()`·`queryIntentActivities()` 등이 **필터된 부분집합**을 반환. 특정 앱을 보려면 매니페스트 `<queries>`(형태 셋: `<package>`·`<intent>`·`<provider authorities>`, OR로 결합) 또는 `QUERY_ALL_PACKAGES`(protectionLevel=normal 자동부여지만 **Play 정책 제한**).
- **URI 권한**: 발신 앱이 Intent에 `FLAG_GRANT_READ_URI_PERMISSION`(0x1)/`FLAG_GRANT_WRITE_URI_PERMISSION`(0x2)를 붙이거나 `Context.grantUriPermission(pkg, uri, flags)`. 수신 앱은 그 `content://` URI만 접근. 시행은 Binder(C17)에서 UID별.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **URI 권한 = 한 URI에만 임시 위임**(전체 프로바이더 아님). 프로바이더가 **opt-in**해야: `android:grantUriPermissions="true"`(전체) 또는 `<grant-uri-permission android:path…>`(특정 경로). opt-in 없으면 `FLAG_GRANT_*`는 무효, `grantUriPermission()`은 `SecurityException`.
- **신뢰하면 안 되는 것들**:
  - **"가시성은 기기 OS 버전으로 걸린다"** — **앱의 targetSdk 30+**입니다. targetSdk≤29 앱은 A12/13에서도 전체를 봅니다.
  - **"열거가 막히면 예외가 난다"** — **조용히 필터링**됩니다(예외 없음). `getPackageInfo`만 `NameNotFoundException`(설치돼도 안 보이면) — "그 앱이 없다"로 오독하기 쉬움.
  - **"`FLAG_GRANT_*`만 붙이면 된다"** — 프로바이더 opt-in이 필요합니다.
  - **"그랜트는 영속한다"** — 기본 **임시**(수신 액티비티/태스크 종료 시 회수). 영속은 `FLAG_GRANT_PERSISTABLE_URI_PERMISSION`(0x40) + 수신측 `takePersistableUriPermission()`(SAF).
  - **"표준 FileProvider는 `../` 트래버설에 취약"** — androidx `FileProvider`는 `getCanonicalPath()`로 정규화해 `<paths>` 밖이면 던집니다. **위험은 과도한 `<paths>`(예: root-path)·커스텀 `openFile()`**에서.
  - **"`FLAG_GRANT_PREFIX_URI_PERMISSION`=0x10"** — **0x80**입니다(0x10은 `FLAG_EXCLUDE_STOPPED_PACKAGES`).

## 질문 4 — 입력과 출력은 무엇인가

- **가시성**: 입력=`<queries>`/상호작용(바인드·쿼리·startActivityForResult) → 출력=필터된 목록(상호작용한 앱은 자동 가시).
- **URI 권한**: 입력=Intent+`FLAG_GRANT_*`+`content://` → 출력=수신 앱이 그 URI만 읽기/쓰기(프로바이더가 잠겨 있어도).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **exported 프로바이더 무권한**: 누구나 데이터를 읽음(그랜트 불필요) — 고전 유출.
- **confused-deputy(자기 파일 대리 읽기)**: 악성 발신자가 딥링크/Intent의 URI를 **피해자 자신의 사적 프로바이더**로 겨누면, 피해자 앱이 그 URI를 무비판적으로 읽어 **제 파일을 공격자에게** 넘깁니다(C47 WebView/딥링크와 직결).
- **implicit-intent 그랜트 오배송**: 암시적 Intent가 엉뚱한 앱으로 해석돼 임시 그랜트가 공격자에게.
- **과도한 `<paths>`·커스텀 openFile 트래버설**: 의도 밖 디렉터리 노출.
- **QUERY_ALL_PACKAGES 지문채취**: 설치 앱 목록으로 사용자 프로파일링(Play 리젝 사유).

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **package visibility**: A11/API30(targetSdk 30+).
- **FileUriExposedException**(file:// 공유 시): A7.0/API24(StrictMode).
- **persistable URI 그랜트**: API19(KitKat, SAF)부터. persisted 그랜트 쿼터 128→512로 상향(후기 버전).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `dumpsys package <pkg>`(`queries`·granted-uri-permissions/uri-grants), 매니페스트 `<queries>`·`<provider android:exported / grantUriPermissions>`.
- `adb shell content query --uri content://<authority>/…`, StrictMode `FileUriExposedException`(logcat), `apktool`로 exported 프로바이더.
- **소스**: 개발자 문서 "Package visibility filtering"·"Sharing files"(FileProvider)·Storage Access Framework.

**주의**: 가시성/URI 권한은 아키텍처 무관 → **에뮬레이터로 `dumpsys package`·`content query`·`<queries>` 실측 가능**.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C09(UID)**: 가시성·URI 권한 둘 다 UID 경계를 건넘.
- **C10(권한)**: URI 권한은 전체 권한의 **위임 대안**(한 URI 임시).
- **C17(Binder)**: 그랜트/시행이 Binder에서 UID별.
- **C47(WebView·딥링크)**: confused-deputy·URI 취급 버그가 정확히 이 통로.
- 다음은 런타임 계층 **Tier 2**(C12 zygote 등)로 넘어갑니다.

## 직접 그릴 수 있는 호출 흐름

```
[ 가시성(보기) + URI 권한(넘기기), 둘 다 UID 경계 건너기 ]

  가시성(A11, targetSdk30+): getInstalledPackages() → 필터된 목록
     보려면: <queries>(package/intent/provider) 또는 QUERY_ALL_PACKAGES
     자동 가시: 상호작용한 앱(바인드/쿼리/startActivityForResult)

  URI 권한: 발신앱 ─ Intent + FLAG_GRANT_READ + content://A/파일 ─▶ 수신앱
     (프로바이더 opt-in: grantUriPermissions=true / <grant-uri-permission>)
     기본 임시(태스크 종료 시 회수) · 영속=PERSISTABLE + takePersistable

  ⚠ confused-deputy: 악성발신자가 URI를 [피해자 자신의 프로바이더]로 겨냥
     → 피해자가 제 사적 파일을 읽어 공격자에게 (C47)
```

## 오개념 판별 문제 5개

1. "패키지 가시성 제한은 기기의 Android 버전(11+)이면 무조건 적용된다."
2. "다른 앱을 열거하려다 막히면 `SecurityException`이 던져진다."
3. "Intent에 `FLAG_GRANT_READ_URI_PERMISSION`만 붙이면 어떤 프로바이더든 읽힌다."
4. "Intent로 준 URI 권한은 앱을 재시작해도 유지된다."
5. "표준 androidx `FileProvider`는 `../` 경로 트래버설에 취약하다."

<details><summary>판정 기준(펼치기)</summary>

1. **앱의 targetSdk 30+**가 게이트입니다. targetSdk≤29 앱은 A12/13에서도 전체를 봅니다.
2. **조용히 필터링**됩니다(예외 없음). `getPackageInfo`만 `NameNotFoundException`.
3. **프로바이더가 opt-in**(`grantUriPermissions`/`<grant-uri-permission>`)해야 합니다. 아니면 무효.
4. 기본 **임시**입니다. 영속은 `FLAG_GRANT_PERSISTABLE` + `takePersistableUriPermission`(SAF).
5. 표준 FileProvider는 `getCanonicalPath()` 정규화로 막습니다. 위험은 **과도한 `<paths>`·커스텀 `openFile()`**.
</details>

## 실측으로 확인한 것

이 모듈의 두 통로(가시성·URI 권한)는 모두 **UID 경계를 건너는 통제**(질문 1·8)이고, 그 경계 자체가 이 세션의 AVD에서 실제로 만들어지는지를 먼저 확인했다. `codex-atlas-api33`(Android 13/API 33, x86_64)에서 증거 앱을 직접 빌드·서명·설치했고, 그 결과 Package Manager가 앱을 **별도 UID로 등록**했다.

```console
$ apksigner verify --print-certs app.apk
$ adb install -r app.apk
```

**1) URI 권한·가시성이 겨누는 "UID 경계"가 실재한다.** 검증 블록의 관측 결과대로 Package Manager가 이 앱을 자신의 UID로 등록했다 — 질문 2에서 "그랜트/시행은 Binder에서 UID별"이라 한 그 UID가 프로세스 등록 수준에서 확인된 것이다. URI 권한이 "전체 권한 없이 한 URI만 임시로" 넘긴다는 주장(질문 3)도, 그 넘김이 바로 이 UID 경계를 넘기 때문에 의미가 있다.

**2) 필터링·그랜트의 대상은 "설치된 서명 패키지"다.** 검증 블록의 명령대로 `apksigner verify`로 v2/v3 서명을 검증한 뒤 `adb install -r`로 설치했다 — 가시성 필터링은 설치된 패키지 목록에 작동하고(질문 2), URI 그랜트는 대상 패키지에 발급된다(질문 3). 즉 이 build→sign→install 파이프라인이 두 통로가 다루는 "패키지"라는 단위를 이 AVD에서 실제로 성립시켰다.

## 가상환경 검증 한계

정직하게, 이 세션의 실측 캡처는 위 UID 등록·서명·설치까지다. 나머지는 근거(개발자 문서·질문 7의 관측 경로)는 확정했으나 이 AVD 세션에서 새로 캡처하지는 않았다.

- **`dumpsys package <pkg>`의 `queries`/`uri-grants`와 `adb shell content query` 출력은 이 세션에서 새로 캡처하지 않았다.** targetSdk 30+와 ≤29 앱의 가시성 목록 차이, URI 그랜트의 임시→회수 생애주기는 문서화된 동작으로 서술했을 뿐 이 문서에 원시 출력으로 남기지는 않았다.
- **confused-deputy·exported 프로바이더 유출은 개념으로만 다뤘다.** 악성 페이로드 없이 원리만 서술했고(질문 5), 피해자 프로바이더를 실제로 대리 호출하는 재현은 하지 않았다.
- **QUERY_ALL_PACKAGES의 Play 정책 리젝과 AAB의 Play App Signing 변환은 로컬 AVD로 재현하지 않았다.** 검증 블록의 한계 그대로, 서버·정책 측 동작이라 Google APIs 에뮬레이터만으로는 관측되지 않는다.

관련 근거: [Package visibility filtering](https://developer.android.com/training/package-visibility) · [Sharing files (FileProvider)](https://developer.android.com/training/secure-file-sharing) · [androidx FileProvider](https://developer.android.com/reference/androidx/core/content/FileProvider) · [Storage Access Framework](https://developer.android.com/guide/topics/providers/document-provider)

## 마치며

앱이 서로를 **보고**(가시성) 데이터를 **넘기는**(URI 권한) 것은 둘 다 UID 경계(C09)를 건너므로 통제됩니다: A11부터 설치 앱 열거는 조용히 필터링되고(targetSdk 30 게이트), 특정 앱을 보려면 `<queries>`나 `QUERY_ALL_PACKAGES`가 필요하며, 데이터 공유는 전체 권한 대신 `content://` URI 하나에만 임시 위임합니다(`file://` 대신 FileProvider). 그리고 여기 confused-deputy가 삽니다 — 악성 발신자가 URI를 피해자 자신의 사적 프로바이더로 겨누면 피해자가 제 파일을 대신 읽어 넘깁니다(C47과 직결). 이로써 Tier 1(앱·패키징)을 닫고, 다음은 앱이 실제로 실행되는 런타임 **Tier 2**(C12 zygote·C13 ART·C14 클래스 로딩)로 넘어갑니다.
