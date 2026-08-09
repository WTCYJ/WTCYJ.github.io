---
layout: post
title: "Android 앱 보안 분석 11~12주차 - InsecureShop 미니 모의진단"
date: 2026-08-09
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 모의진단, MASVS, MASTG, OWASP, InsecureShop, 딥링크, WebView, ContentProvider, protectionLevel, 하드코딩자격증명, 취약점진단, 보고서, 학습기록]
excerpt: "지금까지는 답을 아는 제 앱이 대상이었습니다. 이번에는 처음 보는 훈련 앱을 MASVS 기준으로 진단했습니다. 딥링크 한 번으로 앱이 자기 자격증명 저장소를 화면에 렌더한 경로, 보호된 것처럼 보이지만 사실상 열려 있던 커스텀 권한, 그리고 재현한 것과 못 한 것을 구분해 적는 문제를 정리했습니다."
---

> **진행 구간**: 24주 로드맵의 11~12주차 (미니 모의진단)
> **대상**: InsecureShop `com.insecureshop` v1.0 · SHA-256 `a83298ae…07d4d1bd`
> **환경**: AVD `sec-api33` (Android 13, API 33) · apktool · jadx 1.5.5 · adb
> **이전 글**: [9~10주차 취약점 수정](/posts/android-security-study-week9-10/) · [7~8주차](/posts/android-security-study-week7-8/) · [24주 로드맵](/posts/android-security-study-roadmap/)

---

이 글은 24주 Android 보안 학습 로드맵의 11~12주차, 미니 모의진단 구간 기록입니다.

지금까지 다섯 구간은 제가 직접 만든 앱이 대상이었습니다. 약점을 심은 사람도 저였으니 정답표를 들고 도구를 검증하는 셈이었습니다. 이번에는 처음 보는 훈련 앱을 놓고 MASVS 기준으로 진단하고 보고서를 썼습니다. 이 글에서는 진단 절차를 어떻게 잡았는지, 무엇이 나왔는지, 그리고 "재현한 것"과 "코드만 보고 판단한 것"을 어떻게 갈라 적었는지를 살펴보겠습니다.

---

## 배경 개념 - MASVS와 모의진단의 범위

먼저 이번 구간의 기준을 정리하겠습니다.

**MASVS**(Mobile Application Security Verification Standard)는 OWASP가 정리한 모바일 앱 보안 검증 표준으로, 확인해야 할 항목을 통제 그룹으로 묶어둔 목록입니다. MASVS-STORAGE(저장), MASVS-NETWORK(통신), MASVS-AUTH(인증), MASVS-PLATFORM(플랫폼 상호작용), MASVS-CODE(코드 품질), MASVS-RESILIENCE(변조 저항) 같은 그룹으로 나뉩니다. **MASTG**는 그 각 항목을 실제로 어떻게 시험하는지 적어둔 테스트 가이드입니다.

진단에서 이 기준이 필요한 이유는 빠뜨림을 줄이기 위해서입니다. 눈에 띄는 것부터 파고들면 흥미로운 하나에 시간을 다 쓰고 저장소나 통신 쪽은 손도 못 댄 채 끝나기 쉽습니다.

**모의진단**은 실제 공격자의 관점에서 대상을 점검하되, 사전에 합의된 범위 안에서만 수행하는 작업입니다. 범위를 문서로 못 박는 것이 첫 단계입니다. 이번 대상은 학습 목적으로 공개된 의도적 취약 앱이므로 분석이 허용되지만, 그 앱이 참조하는 **외부 도메인은 남의 서버**입니다. 그래서 앱 바이너리와 제 에뮬레이터로만 범위를 한정하고 외부 서비스에는 요청 한 번 보내지 않았습니다.

---

## 1. 실습 환경과 준비 - 대상 선정과 범위 설정

로드맵은 "훈련 앱 하나를 MASTG 기준으로 진단하고 3~5쪽 보고서를 작성한다"로 이 구간을 정의해뒀습니다.

대상은 **InsecureShop**을 골랐습니다. OWASP MAS 프로젝트가 유지하는 크랙미들은 역공학 챌린지 성격이라 전체 앱 진단 연습에는 맞지 않았고, InsecureShop은 로그인·상품목록·장바구니·WebView·ContentProvider를 갖춘 온전한 앱이면서 의도적으로 취약하게 만들어져 있어 이 목적에 맞았습니다.

| 항목 | 값 |
| --- | --- |
| 앱 | InsecureShop `com.insecureshop` v1.0 |
| APK | 4,754,534 bytes |
| SHA-256 | `a83298ae4a37fcab8101e8b41e513dd2199af71a94ea537d556a318e07d4d1bd` |
| minSdk / targetSdk | 16 / 29 |
| 서명 | debug 서명, `debuggable="true"` |

![InsecureShop 앱의 상품 목록 화면입니다. 상단에 InsecureShop 제목 표시줄이 있고 그 아래에 Laptop $80, Hat $10, Sunglasses $10, Watch $30, Camera, Perfumes 상품 카드가 2열 격자로 배열돼 있습니다](/assets/img/android-security-study/13-insecureshop-app.png)

범위는 이렇게 정했습니다. 앱 바이너리와 제 로컬 에뮬레이터만 대상이고, 앱이 참조하는 `insecureshopapp.com`·`images.pexels.com` 같은 외부 도메인에는 어떤 테스트도 하지 않습니다. 기기 루팅이나 물리 탈취는 상정하지 않고, **Android 앱 샌드박스가 정상 동작하는 전제에서 앱이 스스로 열어둔 경로만** 봅니다.

위협 모델로 상정한 공격자는 둘입니다. 특별한 권한 없이 같은 기기에 설치된 악성 앱, 그리고 사용자가 클릭하는 링크입니다.

---

## 2. 진단 절차 - 정적으로 표를 만들고 하나씩 밟기

5~6주차와 7~8주차에 만들어둔 도구를 그대로 썼습니다.

```bash
bash tools/static-analyze.sh apps/targets/InsecureShop.apk insecureshop
```

35초 만에 apktool 디코드, jadx 역컴파일(소스 2,179개), 그리고 표 아홉 개가 나왔습니다. 컴포넌트 노출, 권한, 전역 플래그, 딥링크, 저장소·네트워크·로그 호출 지점, WebView 설정, 하드코딩 의심 문자열입니다.

여기서 도구를 한 번 더 손봐야 했습니다. 하드코딩 문자열 표가 DataBinding이 생성한 `layout/activity_login_0` 같은 리소스 경로로 가득 찼습니다. 엔트로피는 높지만 비밀이 아닙니다. 제외 규칙을 한 줄 추가해 19행으로 줄였습니다. 5~6주차에 Kotlin `@Metadata`를 걸러낸 것과 같은 종류의 작업입니다. **처음 보는 앱에 도구를 대면 그 앱이 쓰는 빌드 도구에 맞춰 잡음이 새로 생깁니다.**

그다음은 표의 각 행을 기기에서 밟는 순서입니다. 앱을 설치하고 로그인부터 시작해, 딥링크·ContentProvider·저장소를 차례로 확인했습니다.

---

## 3. 관측 결과

12건을 확인했고 그중 8건을 기기에서 재현했습니다. 전체 목록과 근거는 별도 진단 보고서로 정리했고, 여기서는 인상적이었던 넷만 적습니다.

### 3-1. 딥링크 한 번으로 자격증명이 화면에 뜬다

`WebViewActivity`는 딥링크 경로에 따라 두 갈래로 동작합니다. `/webview` 경로는 URL을 검증하는데, **`/web` 경로는 검증 없이 `url` 파라미터를 그대로 로드합니다.**

```java
if (!StringsKt.equals$default(uri.getPath(), "/web", false, 2, null)) {
    if (StringsKt.equals$default(uri.getPath(), "/webview", ...)) {
        ... endsWith("insecureshopapp.com") 검사 ...
    }
} else {
    data = data4 != null ? data4.getQueryParameter("url") : null;   // 검증 없음
}
webview.loadUrl(data);
```

확인에 사용한 명령은 다음과 같습니다.

```bash
adb shell am start -a android.intent.action.VIEW \
  -d "insecureshop://com.insecureshop/web?url=file:///data/data/com.insecureshop/shared_prefs/Prefs.xml"
```

![WebView 화면에 XML 문서가 렌더링돼 있습니다. string name="password"의 값으로 !ns3csh0p, string name="username"의 값으로 shopuser가 그대로 표시됩니다](/assets/img/android-security-study/12-deeplink-file-read.png)

앱이 자기 SharedPreferences 파일을 렌더링했고, 비밀번호와 사용자명이 화면에 그대로 나왔습니다. 권한도 루팅도 필요 없고, 브라우저나 다른 앱이 URI 하나를 던지면 됩니다.

### 3-2. 인증이 앱 안의 해시맵 대조

```java
private final HashMap<String, String> getUserCreds() {
    HashMap<String, String> map = new HashMap<>();
    map.put("shopuser", "!ns3csh0p");
    return map;
}
```

디컴파일로 얻은 이 값으로 실제 로그인에 성공했습니다. 그리고 로그인하는 순간 logcat에 이렇게 찍혔습니다.

```
D userName: shopuser
D password: !ns3csh0p
```

저장된 값도 평문이었습니다.

```
$ adb shell run-as com.insecureshop cat /data/data/com.insecureshop/shared_prefs/Prefs.xml
<string name="password">!ns3csh0p</string>
<string name="username">shopuser</string>
```

### 3-3. 보호된 것처럼 보이는 ContentProvider

`InsecureShopProvider`는 커스텀 권한 `com.insecureshop.permission.READ` 로 보호돼 있습니다. 매니페스트만 훑으면 잘 막아둔 것처럼 보입니다.

그런데 그 권한 선언에 **`protectionLevel` 속성이 없습니다.**

```
$ adb shell dumpsys package com.insecureshop | grep -A3 "permission.READ"
  Permission [com.insecureshop.permission.READ]:
    sourcePackage=com.insecureshop
    uid=10176 gids=[] type=0 prot=normal
```

`prot=normal` 은 어떤 앱이든 `<uses-permission>` 한 줄을 넣으면 **설치 시 자동으로 부여**된다는 뜻입니다. 사용자에게 묻지도 않습니다. 권한 이름이 붙어 있을 뿐 사실상 열려 있습니다.

### 3-4. 검증이 있는데 우회되는 경로

`/webview` 경로의 URL 검증은 **URL 문자열 전체에 대한 `endsWith("insecureshopapp.com")`** 입니다. 호스트를 파싱하지 않습니다.

| 입력 URL | 결과 |
| --- | --- |
| `https://example.com/` | 거부됨 |
| `https://example.com/#insecureshopapp.com` | **통과** |

프래그먼트를 하나 붙이는 것으로 통과합니다.

---

## 4. 결과 해석 - 개별 결함보다 조합

이 앱에서 배운 것은 **결함이 겹칠 때 급이 달라진다**는 점입니다.

비밀번호를 평문으로 저장하는 것(3-2)만 놓고 보면 심각도는 보통입니다. 샌드박스가 정상 동작하는 한 다른 앱이 그 파일을 직접 읽지 못하니까요. WebView가 임의 URL을 로드하는 것(3-1)도 그 자체로는 피싱 페이지를 띄우는 정도입니다.

그런데 둘이 만나면 **외부 앱이 URI 하나로 자격증명을 꺼내 보는 경로**가 됩니다. 여기에 `setAllowUniversalAccessFromFileURLs(true)` 가 더해지면 렌더링에서 그치지 않고 스크립트로 읽어 외부로 보내는 구조까지 갖춰집니다.

그래서 보고서에서는 F-04(평문 저장)의 심각도를 보통으로 두되 "단독 심각도는 보통이지만 다른 결함의 연료가 된다"고 명시했습니다. 심각도 숫자만 나열하면 이 관계가 보이지 않습니다.

두 번째로, **"보호돼 있다"와 "보호가 동작한다"는 다릅니다.** ContentProvider를 `adb shell` 로 조회했더니 `Permission Denial` 이 났습니다. 여기서 "권한이 잘 걸려 있구나" 하고 넘어갈 수 있었습니다. 그런데 거부된 이유는 보호가 견고해서가 아니라 **`adb shell` 이 그 권한을 요청하지 않았기 때문**입니다. `prot=normal` 을 확인하고 나서야 실제 상태를 알았습니다. 거부 결과 하나로 판단을 끝내면 안 됩니다.

세 번째로, 컴포넌트 노출 표에 `net.gotev.uploadservice.UploadService` 가 있었습니다. exported이고 권한이 없습니다. 그런데 이건 개발자가 쓴 것이 아니라 라이브러리가 자기 매니페스트에 선언한 것입니다. 5~6주차에 androidx의 `ProfileInstallReceiver` 를 두고 같은 구분을 했었는데, 진단 보고서에서는 이 구분이 더 중요합니다. **남의 코드를 대상 앱의 취약점으로 올리면 보고서 전체의 신뢰가 깎입니다.**

---

## 5. 시행착오와 정정

### 재현한 것과 안 한 것을 섞을 뻔했다

보고서 초안에서 12건을 같은 형식으로 나열했습니다. 다시 읽어보니 문제가 있었습니다. 딥링크로 자격증명을 화면에 띄운 것은 제가 직접 실행해 스크린샷까지 있는데, 외부 패키지 코드 로드(`createPackageContext` 로 다른 앱의 클래스를 실행하는 경로)는 **코드만 읽고 판단한 것**이었습니다. 재현하려면 공격 측 앱을 따로 만들어야 하는데 그러지 않았습니다.

둘을 같은 톤으로 적으면 읽는 사람은 전부 확인된 것으로 받아들입니다. 그래서 각 항목에 **"기기 확인" / "정적 근거만"** 을 붙이고, 마지막에 재현 요약 표를 따로 뒀습니다. 12건 중 8건이 기기 확인, 4건이 정적 근거만입니다.

이렇게 적고 나니 보고서가 약해 보일까 걱정했는데, 오히려 반대라고 생각을 바꿨습니다. 확인 범위를 명시한 8건이, 전부 확인한 척한 12건보다 신뢰가 갑니다. **한계를 적는 것이 결과를 깎는 게 아니라 나머지의 무게를 올립니다.**

### 입력이 전부 아이디 칸에 들어갔다

로그인을 자동화하려고 `input tap` 으로 아이디 칸을 누르고 텍스트를 넣은 뒤, 다시 비밀번호 칸을 눌러 입력했습니다. 화면을 확인해보니 아이디 칸에 `shopuser !ns3csh0p` 가 한꺼번에 들어가 있었습니다. 키보드가 올라와 비밀번호 칸을 덮고 있어서 두 번째 탭이 다른 곳을 누른 것이었습니다.

`KEYCODE_TAB` 으로 포커스를 옮기도록 바꿔서 해결했습니다. 그리고 `input text` 는 `%s` 를 공백으로 해석하기 때문에, 비밀번호 앞에 공백이 하나 붙어 또 한 번 실패했습니다.

사소한 문제지만 짚어둘 만한 지점이 있습니다. **화면을 확인하지 않고 탭 좌표만 믿으면 조용히 틀립니다.** 로그인이 실패했을 때 "자격증명이 틀렸나" 부터 의심했는데 실제로는 입력 자체가 안 들어간 것이었습니다. 7~8주차의 거짓 양성과 뿌리가 같습니다.

### 도구가 새 잡음을 만든다

하드코딩 문자열 표가 DataBinding 생성 코드로 가득 찼습니다. 제 앱을 분석할 때는 없던 잡음입니다. 그 앱이 DataBinding을 안 썼기 때문입니다.

**도구는 지금까지 본 앱에 맞춰 조율돼 있습니다.** 처음 보는 앱에 대면 그 앱이 쓰는 빌드 도구·라이브러리에 맞춰 새로 걸러야 할 것이 생깁니다. 진단 시간의 일부는 이 조율에 쓰인다고 잡아두는 편이 맞겠습니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~2주 | Android 구조 | 완료 |
| 3~4주 | 테스트 앱 작성 | 완료 |
| 5~6주 | 정적 분석 | 완료 |
| 7~8주 | 동적 분석 | 완료 |
| 9~10주 | 취약점 유형별 점검·수정 | 완료 |
| 11~12주 | 미니 모의진단 | 완료 |
| 13~14주 | 네이티브·런타임 기초 | 다음 |

로드맵이 앞 12주에 배치한 항목이 모두 끝났습니다. 판단 기준 다섯 가지 중 넷이 채워졌고, 남은 하나는 CVE 구간 항목입니다.

- ☑ APK 하나를 정적 분석하고 표를 만들 수 있다
- ☑ 정상 동작의 기준선을 만든 뒤 최소 검증으로 가설을 확인할 수 있다
- ☑ 문제를 수정하고 같은 테스트로 재발하지 않음을 보일 수 있다
- ☑ 스냅샷·빌드 지문·로그를 이용해 실험을 재현할 수 있다
- ☐ 공개 CVE 하나를 설명할 수 있다 → 18주차 이후

한계도 적어둡니다. 공격 측 앱을 만들지 않아 4건은 정적 근거에 머물렀고, 네이티브 라이브러리와 난독화는 보지 않았습니다. API 33 한 대에서만 진단했으므로 targetSdk 29 앱의 다른 API 레벨 동작은 확인하지 못했습니다. 그리고 5~6주차에 자동 분석이 데이터 흐름 문제를 놓친다는 것을 확인했으므로, 이 12건이 전부라고 주장하지 않습니다.

다음은 13~14주차 네이티브·런타임 기초입니다. JNI와 ELF, 난독화가 분석에 어떤 영향을 주는지 다룹니다. 이번에 미룬 항목들이 그 구간과 이어집니다.

---

## 마치며

여섯 구간 만에 처음으로 제가 만들지 않은 앱을 봤습니다. 정답표 없이 진단해보니 앞의 다섯 구간이 무엇을 위한 것이었는지가 분명해졌습니다. 도구를 만든 것도, 검증 절차를 스크립트로 남긴 것도, 실수를 기록한 것도 결국 이 작업을 위한 준비였습니다.

가장 크게 남은 것은 보고서 쓰는 방식이었습니다. 취약점을 찾는 것보다 **찾은 것과 찾았다고 생각한 것을 구분해 적는 일**이 어려웠습니다. 12건을 나란히 놓으면 그럴듯해 보이는데, 하나씩 "이건 내가 눌러봤나"를 물으니 넷이 떨어져 나갔습니다. 그 넷을 지우지 않고 표시만 바꿔 남긴 것이 이번 보고서에서 제일 잘한 선택이라고 생각합니다.
