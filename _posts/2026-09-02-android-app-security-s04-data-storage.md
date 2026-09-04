---
layout: post
title: "[Android 앱 보안 S04] 앱 데이터 저장소 분석"
date: 2026-09-02 12:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, SharedPreferences, run-as, 하드코딩, 자격증명, 저장소, InsecureShop, 학습기록]
excerpt: "앱이 자격증명을 어디에 두는지 봅니다. InsecureShop은 로그인 성공값을 SharedPreferences에 평문으로 저장하고, 애초에 그 자격증명 자체가 코드에 하드코딩돼 있었습니다. 정적으로 DEX에서 아이디·비밀번호를 그대로 뽑고, debuggable을 지렛대 삼아 run-as로 저장된 평문을 열어 확인했습니다. SQLite도 외부 저장도 쓰지 않아, 저장소 지도는 오히려 단순하고 분명했습니다."
---

> S02에서 확인한 `debuggable=true`가 여기서 지렛대가 됩니다. 디버그 가능 앱이라 `run-as`로 앱 프라이빗 저장소를 그대로 열 수 있습니다.

앱을 뜯을 때 가장 먼저 값이 나오는 곳이 저장소입니다. 개발자가 "잠깐 여기 두자"고 한 자리가 대개 평문이기 때문입니다. InsecureShop은 두 겹으로 걸립니다. 하나는 로그인 자격증명이 애초에 코드에 하드코딩돼 있다는 것, 다른 하나는 로그인에 성공하면 그 값을 SharedPreferences에 평문으로 다시 저장한다는 것입니다. 정적으로 코드에서 뽑고, 동적으로 저장된 파일을 열어 두 경로를 다 확인했습니다.

---

## 실습 목표

- 앱의 저장 방식(SharedPreferences·SQLite·Room·파일·외부저장)을 코드와 실제 파일 양쪽에서 확인한다.
- 하드코딩된 자격증명이 있으면 로그인 없이 DEX에서 추출한다.
- `run-as`로 앱 프라이빗 저장소를 열어 저장된 값이 평문인지 확인한다.
- 안전한 테스트 자격증명만 사용한다(교육용 앱의 기본 계정).

---

## 윤리적 범위와 허가 조건

대상은 교육용 앱 InsecureShop이고, 사용한 계정은 이 앱에 원래 박혀 있는 테스트 계정입니다. 모든 조작은 `aas-api33` 에뮬레이터 안에서만 하며, `run-as`도 내가 소유한 이 앱의 디버그 빌드에 대해서만 씁니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 대상 앱: `com.insecureshop` (S02, SHA-256 `a83298…d1bd`)
- 정적: `jadx` 1.5.5 디컴파일 결과(S03에서 생성), `grep -a`로 DEX 문자열 검색
- 동적: `adb`, `run-as`(디버그 빌드)

---

## 위협 모델 — 이 단계에서 답할 질문

- 앱은 자격증명을 어디에 두는가? 그 값은 평문인가?
- 로그인하지 않고도 자격증명을 알아낼 수 있는가(하드코딩)?
- SQLite·Room·파일·외부저장 중 무엇을 쓰는가? 민감 데이터가 새는 곳이 있는가?

---

## 재현 절차

### 1. 저장 로직과 하드코딩 자격증명 (정적)

jadx로 푼 소스에서 저장을 담당하는 `Prefs`와 로그인 검증을 담당하는 `Util`을 봤습니다. 먼저 자격증명 검증은 이렇게 생겼습니다.

```java
// com/insecureshop/util/Util.java
private final HashMap<String, String> getUserCreds() {
    HashMap<String, String> map = new HashMap<>();
    map.put("shopuser", "!ns3csh0p");        // 하드코딩된 아이디/비밀번호
    return map;
}
public final boolean verifyUserNamePassword(String username, String password) {
    ...
    return StringsKt.equals$default(getUserCreds().get(username), password, false, 2, null);
}
```

아이디와 비밀번호가 코드에 그대로 박혀 있습니다. 그리고 저장은 `Prefs`가 `SharedPreferences`에 평문으로 합니다.

```java
// com/insecureshop/util/Prefs.java
SharedPreferences sharedPreferences = context.getSharedPreferences("Prefs", 0);  // 파일명 "Prefs"
// setPassword(...) / setUsername(...) 로 평문 저장 (username, password, data, productList)
```

### 2. 로그인 없이 DEX에서 자격증명 추출 (정적)

코드에 박혀 있으니, 앱을 실행하거나 로그인할 필요조차 없습니다. APK에서 `classes.dex`만 꺼내 문자열을 훑으면 그대로 나옵니다.

```console
$ unzip -p InsecureShop.apk classes.dex > classes.dex
$ grep -aoE 'shopuser|!ns3csh0p' classes.dex | sort -u
!ns3csh0p
shopuser
```

DEX 안의 오프셋까지 확인했습니다(`shopuser` @ 0x5ab774, `ns3csh0p` @ 0x45768a). 이 지점에서 이미 로그인은 뚫린 것이나 다름없습니다.

### 3. 로그인 후 저장된 값 열기 (동적)

이제 그 자격증명으로 실제 로그인해서, 앱이 무엇을 저장하는지 봅니다. `aas-api33`에서 아이디 `shopuser`, 비밀번호 `!ns3csh0p`로 로그인하면 상품 목록으로 넘어갑니다. 그 순간 SharedPreferences에 값이 쓰입니다. `debuggable` 빌드라 `run-as`로 바로 열 수 있습니다.

```console
$ adb shell run-as com.insecureshop ls /data/data/com.insecureshop/shared_prefs/
Prefs.xml
WebViewChromiumPrefs.xml
$ adb shell run-as com.insecureshop cat /data/data/com.insecureshop/shared_prefs/Prefs.xml
<map>
    <string name="password">!ns3csh0p</string>
    <string name="username">shopuser</string>
    <string name="productList">[{"id":1,"name":"Laptop",...}]</string>
</map>
```

아이디도 비밀번호도 평문 그대로입니다. 정적으로 DEX에서 뽑은 값과 동적으로 저장소에서 읽은 값이 정확히 같습니다.

### 4. 나머지 저장소 훑기

앱 내부 디렉터리 전체를 봤습니다.

```console
$ adb shell run-as com.insecureshop ls /data/data/com.insecureshop/
app_webview  cache  code_cache  shared_prefs
$ adb shell run-as com.insecureshop ls /data/data/com.insecureshop/databases/
... No such file or directory
$ adb shell ls /sdcard/Android/data/com.insecureshop/
... No such file or directory
```

이 앱은 SQLite나 Room 데이터베이스를 쓰지 않고, `files/`도 없으며, 이 흐름에서 외부 저장소에 쓰는 것도 없었습니다(외부저장 권한은 선언돼 있지만 로그인~상품목록 경로에서는 쓰이지 않음). 민감 데이터는 오직 SharedPreferences 한 곳에 몰려 있습니다. `cache/`에는 WebView 캐시와 Glide 이미지 캐시만 있어 자격증명과는 무관했습니다. 저장소 지도가 단순해서, 팔 곳도 분명했습니다.

---

## 스크린샷

`shopuser`/`!ns3csh0p`로 로그인에 성공한 상품 목록 화면입니다. 이 세션이 만들어지는 순간, 위 코드블록의 평문 자격증명이 `Prefs.xml`에 쓰였습니다. 화면은 로그인이 성립했다는 확인이고, 저장의 증거는 그 아래 파일 내용입니다.

![shopuser 계정으로 로그인 성공 후 뜬 InsecureShop 상품 목록 — Laptop/Hat/Sunglasses/Watch/Camera/Perfumes 카드가 가격과 함께 표시됨](/assets/img/android-app-security/S04/01-loggedin.png)

`Prefs.xml`, 저장소 트리, DEX 추출 결과의 원시 출력은 `assets/evidence/android-app-security/S04/`에 남겼습니다.

---

## 관측 결과

- 자격증명이 코드에 하드코딩(`shopuser`/`!ns3csh0p`)돼 있어, 로그인 없이 DEX 문자열만으로 추출된다.
- 로그인 성공값을 SharedPreferences `Prefs`에 평문으로 저장한다. `run-as`로 아이디·비밀번호를 그대로 읽었다.
- SQLite·Room·`files/`·외부저장은 이 흐름에서 쓰이지 않는다. 민감 데이터는 SharedPreferences 한 곳.
- `debuggable`이 켜져 있어 `run-as` 접근이 성립한다(S02·S03에서 예고한 대로).

---

## 근본 원인과 보안 영향

- 자격증명 하드코딩은 앱 바이너리를 가진 누구에게나 노출됩니다. 클라이언트 측 인증 자체가 잘못된 설계고, 인증은 서버가 해야 합니다.
- SharedPreferences는 암호화되지 않은 XML입니다. `debuggable`·루팅·백업(S02의 `allowBackup=true`) 어느 경로로든 평문이 읽힙니다. 비밀번호를 여기 저장하는 것 자체가 문제입니다.
- 굳이 로컬에 자격 관련 값을 둬야 한다면, 비밀번호가 아니라 서버가 발급한 토큰을 두고, 그것도 EncryptedSharedPreferences나 Android Keystore로 보호해야 합니다.

## 수정 방법

- 자격증명을 코드에서 제거하고 인증을 서버로 옮긴다(하드코딩된 비교 로직 삭제).
- 비밀번호를 로컬에 저장하지 않는다. 세션은 서버 발급 토큰으로 관리하고, 토큰은 `EncryptedSharedPreferences`(Jetpack Security) 또는 Keystore로 보호한다.
- `allowBackup="false"`, 릴리스에서 `debuggable` 제거로 저장소 노출 경로를 함께 닫는다.

수정 후에는 같은 `run-as cat Prefs.xml`을 해도 비밀번호가 보이지 않아야 하고, DEX에서 자격증명 문자열이 나오지 않아야 합니다.

---

## 재검증

로그인 전에는 `Prefs.xml`이 `<map />`(빈 값)이었고, 로그인 직후 같은 파일에서 평문 아이디·비밀번호가 나왔습니다. 그리고 그 값은 로그인 없이 DEX에서 뽑은 하드코딩 값과 정확히 일치했습니다. 두 경로가 같은 결론을 가리키는 것으로 교차 확인했습니다.

---

## 참고 자료

- Android Developers — 데이터·파일 저장 개요, `run-as`
- Android Jetpack Security — `EncryptedSharedPreferences`
- OWASP MASVS — Storage(MSTG-STORAGE) 요구사항
