---
layout: post
title: "[Android 앱 보안 S13] 패키지 가시성과 URI 권한"
date: 2026-09-02 21:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 패키지가시성, queries, FileProvider, URI권한, InsecureShop, 학습기록]
excerpt: "다른 앱을 볼 수 있는가, 그리고 파일을 어디까지 내줄 수 있는가. 최신 안드로이드는 다른 앱의 존재를 기본으로 숨깁니다. 직접 만든 앱으로, queries 없이는 자기 자신밖에 못 보다가 한 줄을 넣으면 InsecureShop이 보이는 걸 확인했습니다. 그리고 InsecureShop의 FileProvider가 파일시스템 루트 전체를 노출하도록 설정돼 있다는 것도 함께 정리했습니다."
---

> S06에서 공격 앱이 `<queries>` 없이는 InsecureShop의 provider를 못 봤습니다. 그 문턱의 정체가 패키지 가시성입니다. 이번엔 그걸 정면으로 재현하고, 파일을 내주는 FileProvider의 설정까지 봅니다.

앱 간 상호작용은 두 가지 질문으로 시작합니다. 상대 앱의 존재를 알 수 있는가(패키지 가시성), 그리고 파일을 얼마나·어떻게 내줄 수 있는가(URI 권한). 최신 안드로이드는 첫 번째를 기본으로 막고, 두 번째는 임시 권한으로 좁힙니다. 직접 만든 앱으로 첫 번째를 재현하고, InsecureShop의 FileProvider 설정으로 두 번째를 봤습니다.

---

## 실습 목표

- `<queries>` 없이 `getInstalledPackages()`가 어떻게 필터링되는지 확인한다.
- `<queries>`를 넣으면 특정 패키지가 보이게 되는지 확인한다.
- FileProvider가 어떤 경로를 노출하는지, `FLAG_GRANT_READ_URI_PERMISSION`이 무엇인지 정리한다.

---

## 윤리적 범위와 허가 조건

가시성 재현에 쓴 앱은 내가 직접 만든 `com.aas.pkgvis`, 파일 노출 분석 대상은 내가 소유한 InsecureShop입니다. 모든 조작은 `aas-api33` 에뮬레이터 안입니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01)
- 가시성 데모 앱: 직접 손빌드(`getPackageManager().getInstalledPackages()`), S05 툴체인
- 정적 근거: S03 디컴파일, `res/xml/provider_paths.xml`

---

## 위협 모델 — 보이는가, 내줄 수 있는가

- 다른 앱이 이 앱(또는 특정 앱)의 존재를 알 수 있는가?
- FileProvider가 노출하는 경로 범위가 적절한가?
- URI 권한이 임시로만, 필요한 파일에만 부여되는가?

---

## 재현 절차

### 1. 패키지 가시성 — queries 없음

targetSdk 30 이상 앱은 다른 패키지를 기본으로 볼 수 없습니다. `<queries>` 없이 만든 데모 앱에서 `getInstalledPackages()`를 불러 봤습니다.

```
manifest <queries>: NONE
getInstalledPackages(0) total = 75
  그중 non-system = 1
  (visible non-system 목록)
  com.aas.pkgvis          ← 자기 자신뿐
getPackageInfo("com.insecureshop") = NOT visible (NameNotFoundException)
```

시스템 패키지 몇십 개는 항상 보이지만, 사용자 앱 중에는 자기 자신 하나만 보입니다. `com.insecureshop`을 특정해 물어도 "그런 패키지 없음"으로 돌아옵니다. 실제로는 설치돼 있는데도요.

### 2. queries 한 줄을 넣으면

매니페스트에 대상 패키지를 선언하고 다시 빌드했습니다.

```xml
<queries>
    <package android:name="com.insecureshop"/>
</queries>
```

```
manifest <queries>: <package com.insecureshop>
getInstalledPackages(0) total = 76
  그중 non-system = 2
  com.insecureshop        ← 이제 보인다
  com.aas.pkgvis
getPackageInfo("com.insecureshop") = VISIBLE
```

한 줄로 `com.insecureshop`이 목록에 들어왔고, 특정 조회도 VISIBLE이 됐습니다. S06에서 공격 앱이 넘어야 했던 문턱이 바로 이것이고, 공격자에겐 매니페스트 한 줄이라는 것도 그대로 드러납니다. 가시성은 정보 노출을 줄이는 완화책이지, 접근을 막는 방어가 아닙니다.

### 3. FileProvider — 무엇을 내주는가

파일 공유는 `FileProvider`로, `content://` URI에 `FLAG_GRANT_READ_URI_PERMISSION`을 붙여 "이 파일만, 이번만" 내주는 게 정석입니다. 노출 범위는 `res/xml`의 경로 설정으로 정하는데, InsecureShop의 설정은 이렇습니다.

```xml
<!-- InsecureShop res/xml/provider_paths.xml -->
<paths>
    <root-path name="root" path="/" />
</paths>
```

`root-path`에 `path="/"`. 파일시스템 루트 전체를 FileProvider의 공유 대상으로 열어 둔 것입니다. FileProvider로 특정 파일 하나를 안전하게 공유하려던 취지와 정반대로, 앱이 읽을 수 있는 어떤 파일이든 `content://` URI로 가리킬 수 있게 됩니다. 여기에 임시 URI 권한이 얹히면, 경로만 바꿔 민감 파일(예: 앱의 `shared_prefs`)까지 가리키는 경로 순회가 열립니다. 이 FileProvider 자체는 `exported="false"`지만 `grantUriPermissions="true"`라, 앱이 URI를 넘겨주는 흐름이 있으면 그 URI의 범위가 곧 루트 전체가 됩니다.

---

## 스크린샷

같은 데모 앱을, `<queries>` 없이(왼쪽) 그리고 넣고(오른쪽) 실행한 결과입니다. 왼쪽은 사용자 앱 중 자기 자신만 보이고 `com.insecureshop`이 NOT visible, 오른쪽은 한 줄을 넣자 VISIBLE로 바뀌었습니다.

<div style="display:flex;gap:10px;flex-wrap:wrap">
  <img src="/assets/img/android-app-security/S13/01-visibility-noqueries.png" alt="queries 없는 데모 앱 — non-system 1개(자기 자신), com.insecureshop NOT visible" style="max-width:48%"/>
  <img src="/assets/img/android-app-security/S13/02-visibility-queries.png" alt="queries 넣은 데모 앱 — non-system 2개, com.insecureshop VISIBLE" style="max-width:48%"/>
</div>

데모 앱 소스, 두 결과, InsecureShop의 `provider_paths.xml`은 `assets/evidence/android-app-security/S13/`에 남겼습니다.

---

## 관측 결과

- `<queries>` 없이는 사용자 앱 중 자기 자신만 보이고, `com.insecureshop`은 조회 자체가 실패한다(NameNotFoundException).
- `<queries>`에 대상 패키지를 선언하면 그 앱이 목록·특정 조회에서 보인다.
- InsecureShop의 FileProvider는 `provider_paths.xml`에서 `root-path="/"`로 파일시스템 루트 전체를 공유 대상으로 열어 뒀다.

---

## 근본 원인과 보안 영향

- 패키지 가시성은 정보 수집(설치된 앱 목록으로 사용자 프로파일링 등)을 줄입니다. 다만 `<queries>` 한 줄로 특정 앱은 볼 수 있으니, 이건 최소 노출이지 접근 차단이 아닙니다. 민감 컴포넌트는 여전히 권한·서명으로 지켜야 합니다(S06).
- FileProvider의 `root-path="/"`는 심각한 오설정입니다. "특정 파일만 안전 공유"라는 FileProvider의 목적을 무력화하고, URI 경로 순회로 임의 파일 노출을 엽니다.

## 수정 방법

- FileProvider 경로는 공유가 꼭 필요한 하위 디렉터리로만 좁힌다. `root-path="/"`는 절대 쓰지 않는다.

```xml
<!-- 전: 루트 전체 -->
<root-path name="root" path="/" />
<!-- 후: 공유용 하위 디렉터리만 -->
<files-path name="shared" path="share/" />
```

- URI를 넘길 때만 `FLAG_GRANT_READ_URI_PERMISSION`으로 임시·최소 범위로 부여하고, 넘긴 경로가 공유 허용 범위 안인지 검증한다.
- 다른 앱을 조회할 필요가 있으면 `<queries>`에 필요한 것만 선언한다(광범위한 `QUERY_ALL_PACKAGES`는 지양).

---

## 재검증

같은 앱을 `<queries>` 유무만 바꿔 두 번 빌드했더니, `com.insecureshop`의 가시성이 NOT visible ↔ VISIBLE로 정확히 갈렸습니다. 필터링이 매니페스트 선언에 달려 있다는 게 두 실행으로 확인됩니다. FileProvider의 루트 노출은 앱의 `provider_paths.xml` 원문으로 확인했습니다.

---

## 참고 자료

- Android Developers — 패키지 가시성(`<queries>`, API 30+)
- Android Developers — `FileProvider`와 `FLAG_GRANT_READ_URI_PERMISSION`
- Android Developers — FileProvider 경로 설정(`<paths>`)
