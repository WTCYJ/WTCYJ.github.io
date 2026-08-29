---
layout: post
title: "Android 앱 보안 분석 5~6주차 - apktool·jadx 정적 분석과 자작 리포트 도구"
date: 2026-08-09 09:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 정적분석, jadx, apktool, aapt2, APK, DEX, AndroidManifest, WebView, addJavascriptInterface, 딥링크, exported, 데이터흐름, taint, Kotlin, Metadata, 취약점분석, 학습기록]
excerpt: "직접 만든 앱을 APK에서부터 다시 분석했습니다. 심어둔 약점 10개 중 자동 리포트가 잡은 것은 7개였고, 놓친 셋은 전부 데이터 흐름 문제였습니다. 첫 리포트의 하드코딩 문자열 표가 126행 노이즈였던 원인과, WebView 브릿지 노출을 정적 분석에서 동적 확인까지 이어붙인 과정을 정리했습니다."
---

> **진행 구간**: 24주 로드맵의 5~6주차 (정적 분석)
> **대상**: `kr.wtcy.memovault` debug APK · 5,945,029 bytes · SHA-256 `d1815d75…c71cdd01`
> **도구**: apktool · jadx 1.5.5 · aapt2 34.0.0 · 자작 리포트 스크립트
> **이전 글**: [1~4주차](/posts/android-security-study-week1-4/) · [24주 로드맵](/posts/android-security-study-roadmap/) · **다음** [7~8주차 동적 분석](/posts/android-security-study-week7-8/)

이 글은 24주 Android 보안 학습 로드맵의 5~6주차 기록입니다. 3~4주차에 직접 만들어둔 테스트 앱을 이번에는 개발자가 아니라 분석가의 자리에서 다시 열어봤습니다. 이 글에서는 정적 분석이 무엇인지, apktool과 jadx가 각각 어떤 일을 하는지를 먼저 정리한 뒤, 자작 리포트 스크립트가 무엇을 잡아냈고 무엇을 끝내 잡지 못했는지를 실제 산출물과 함께 살펴보겠습니다.

---

## 배경 개념 - 정적 분석, apktool과 jadx, 그리고 taint 분석

본격적으로 들어가기 전에 이번 구간에서 계속 등장할 용어를 먼저 짚겠습니다.

**정적 분석**이란 앱을 실행하지 않은 채 산출물만 놓고 판단하는 분석 방식을 말합니다. APK 파일 안의 매니페스트, 리소스, 코드를 읽어서 "이 앱은 이런 일을 할 수 있다"를 추정합니다. 반대로 앱을 실제로 구동시켜 놓고 통신과 로그, 파일 접근을 관찰하는 방식이 **동적 분석**이며, 이 학습 로드맵에서는 7~8주차 주제입니다.

Android 앱의 배포 단위인 **APK**는 사실상 zip 아카이브입니다. 다만 그 안의 내용물이 사람이 바로 읽을 수 있는 형태가 아닙니다. `AndroidManifest.xml`은 텍스트 XML이 아니라 바이너리로 인코딩돼 있고, 개발자가 작성한 Java·Kotlin 코드는 컴파일과 변환을 거쳐 `classes.dex`라는 **DEX**(Dalvik Executable) 바이트코드로 들어가 있습니다. 그래서 정적 분석의 첫 단계는 언제나 "읽을 수 있는 형태로 되돌리기"입니다. 여기서 도구가 둘로 갈립니다.

- **apktool**은 리소스 쪽을 담당합니다. 바이너리 매니페스트와 `resources.arsc`를 해석해 원본에 가까운 XML로 복원하고, 코드는 DEX에 가까운 저수준 표현인 smali로 풀어줍니다. 컴포넌트가 `exported`인지, 어떤 권한을 요구하는지, 어떤 딥링크를 받는지 같은 **선언 정보**를 볼 때 정확합니다.
- **jadx**는 코드 쪽을 담당합니다. DEX 바이트코드를 사람이 읽을 수 있는 Java 유사 소스로 역컴파일합니다. 원본과 완전히 같지는 않지만 로직을 따라가기에는 충분하며, **무엇을 어떤 순서로 하는지**를 볼 때 유용합니다.

용어 두 가지를 더 풀어두겠습니다. **exported 컴포넌트**란 다른 앱이 인텐트로 직접 호출할 수 있도록 공개된 컴포넌트를 말합니다. **딥링크**는 `memovault://notice`처럼 특정 URI를 앱의 특정 화면으로 연결해주는 진입 경로이고, 이 경로를 열어두면 외부 앱이나 웹 페이지가 그 화면을 띄울 수 있게 됩니다.

마지막으로 이번 구간의 핵심 개념인 **taint 분석**(오염 흐름 분석)입니다. 외부에서 들어온 값을 오염된 값으로 보고, 그 값이 프로그램 안에서 어디까지 흘러가는지를 추적하는 기법입니다. 값이 처음 들어오는 지점을 **source**, 그 값이 위험하게 쓰이는 지점을 **sink**라고 부릅니다. 예를 들어 인텐트로 받은 문자열이 source이고, 그 문자열로 파일을 여는 코드가 sink입니다.

여기서 grep의 한계가 드러납니다. grep은 한 줄씩 패턴을 대조하는 도구라서 "여기에 `new File(...)`이 있다"까지만 말할 수 있습니다. 그 인자가 상수인지, 외부에서 들어온 값이 변수 몇 개를 건너 도착한 것인지는 한 줄만 봐서는 알 수 없습니다. 오염 흐름은 여러 줄, 여러 함수, 때로는 여러 파일에 걸쳐 있기 때문에 **줄 단위 검색으로는 원리적으로 이어붙일 수 없습니다.** 이번 구간에서 자동 리포트가 놓친 항목들이 정확히 이 지점에 몰려 있었습니다.

---

## 1. 실습 환경과 준비 - 분석 대상과 이번 구간의 목표

3~4주차에 만든 앱에는 현실적인 실수 패턴 10개를 일부러 심어뒀습니다. 이번에는 그 앱을 **분석 대상으로만** 다뤘습니다. 소스를 보지 않고 APK에서 출발해 표를 만든 뒤, 마지막에 정답표와 대조했습니다.

궁금했던 것은 "취약점을 찾을 수 있나"가 아니라 **"자동 분석이 무엇을 못 찾나"**였습니다. 답을 아는 상태에서 도구를 돌려보는 경험은 이번이 아니면 하기 어렵습니다.

---

## 2. 자동 분석 파이프라인 구성과 실행

`static-analyze.sh <apk> <label>` 한 줄로 디코드 → 디컴파일 → 리포트까지 돕니다. 49초 걸렸고 jadx가 소스 2,972개를 뽑았습니다.

나온 표는 아홉 개입니다. 컴포넌트 노출, 권한, 앱 전역 플래그, 딥링크, 저장소 호출 지점, 네트워크 호출 지점, 로그 출력 지점, WebView 설정, 하드코딩 의심 문자열.

---

## 3. 관측 결과 - 매니페스트 표, 브릿지 실증, 정답표 대조

### 3-1. 컴포넌트 노출과 WebView 설정 표

컴포넌트 표부터 답이 보입니다. 아래는 매니페스트 선언을 정리한 표입니다.

| 컴포넌트 | exported | permission | intent-filter |
| --- | --- | --- | --- |
| `LoginActivity` | true | - | MAIN / LAUNCHER |
| `MemoListActivity` | true | - | OPEN_MEMOS / DEFAULT |
| `MemoDetailActivity` | true | - | VIEW_MEMO / DEFAULT |
| `WebViewActivity` | true | - | VIEW / DEFAULT, BROWSABLE, `memovault://notice` |
| `ProfileInstallReceiver` | true | `android.permission.DUMP` | (androidx가 넣음) |
| `InitializationProvider` | false | - | 내부 전용 |

액티비티 4개가 전부 exported인데 권한 가드가 없습니다. 런처는 정상이고 나머지 3개가 문제입니다.

`ProfileInstallReceiver`는 제가 쓴 것이 아니라 androidx가 넣은 것이고 `DUMP` 권한으로 막혀 있습니다. **빌드 도구가 합성한 항목과 내가 쓴 항목을 구분하지 않으면 남의 코드를 내 취약점으로 보고하게 됩니다.**

WebView 설정은 한 화면에 몰려 있었습니다. 아래는 리포트가 뽑아낸 WebView 설정 표입니다.

```
WebViewActivity.java:25  setJavaScriptEnabled     true
WebViewActivity.java:26  setAllowFileAccess       true
WebViewActivity.java:27  setAllowContentAccess    true
WebViewActivity.java:29  setMixedContentMode      0     (ALWAYS_ALLOW)
WebViewActivity.java:30  addJavascriptInterface   new NoticeBridge(this), "MemoVaultBridge"
WebViewActivity.java:41  loadUrl                  url   (검증 없음)
```

여기서 `addJavascriptInterface`는 앱의 Java 객체를 WebView 안의 자바스크립트에 그대로 노출시키는 API입니다. 이 객체에 붙은 메서드는 페이지의 자바스크립트가 `window.<등록이름>.<메서드>()` 형태로 직접 호출할 수 있습니다. 이 앱에서 브릿지에 붙은 메서드 이름은 `getSessionToken`, `getUsername`, `getApiKey`, `readFile`입니다. 딥링크로 임의 URL을 띄울 수 있으니 외부 페이지가 이 메서드들을 부를 수 있다는 뜻입니다.

### 3-2. 딥링크를 통한 JavaScript 브릿지 노출 실증

여기까지는 "그럴 수 있다"입니다. 실제로 되는지 확인했습니다. 딥링크 하나면 됩니다. 확인에 사용한 명령은 다음과 같습니다.

```bash
adb shell am start -a android.intent.action.VIEW -d "memovault://notice"
```

![WebView로 열린 공지 페이지. "브릿지 상태: 노출됨 → window.MemoVaultBridge : getApiKey, getSessionToken, getUsername, readFile" 이라고 표시돼 있습니다](/assets/img/android-security-study/05-webview-bridge.png)

페이지 안의 자바스크립트가 `window.MemoVaultBridge`를 찾아내고 메서드 네 개를 그대로 열거했습니다. 정적 분석에서 본 그 이름입니다.

그런데 "노출됐다"와 "호출해서 값을 꺼낼 수 있다"는 다른 주장입니다. 열거에서 멈추지 말고 실제로 불러봤습니다.

![공지 페이지의 "브릿지 호출 결과" 상자에 getSessionToken() → mvt_alice_0001, getUsername() → alice, getApiKey() → mv_live_7c1f9a3e42b8d05612ff8ab34c7e9d20, readFile('/proc/self/cmdline') → kr.wtcy.memovault 가 출력돼 있습니다](/assets/img/android-security-study/09-bridge-exfil.png)

딥링크로 연 웹페이지가 앱의 세션 토큰과 사용자명, API 키를 그대로 읽어냈습니다. `readFile`은 앱 권한으로 파일까지 읽어 돌려줍니다.

### 3-3. 정답표 대조 결과 7/10

심어둔 10개 중 자동 리포트가 잡은 것은 7개였습니다. 아래는 정답표와 리포트를 나란히 놓고 대조한 결과입니다.

| 약점 | 자동 탐지 | 어느 표에서 |
| --- | --- | --- |
| exported 컴포넌트 | ○ | 컴포넌트 노출 |
| 평문 토큰 저장 | △ | 저장소와 문자열이 따로 잡힘 |
| 로그 유출 | ○ | 로그 출력 지점 |
| cleartext HTTP | ○ | 전역 플래그 + 네트워크 |
| allowBackup | ○ | 전역 플래그 |
| WebView JS 브릿지 | ○ | WebView 설정 + 딥링크 |
| 하드코딩 키 | ○ | 하드코딩 문자열 |
| 클라이언트 측 인가 | **✗** | — |
| 서버 응답 파일명 사용 | **✗** | 싱크만 잡힘 |
| intent extra 임의 파일 읽기 | **✗** | — |

---

## 4. 결과 해석 - 데이터 흐름 미탐의 구조적 이유

### 4-1. grep이 원리적으로 볼 수 없는 것

놓친 셋의 공통점이 분명했습니다. **전부 데이터 흐름 문제입니다.**

- `optBoolean("is_admin")` → 세션 저장 → 관리자 버튼 노출
- 서버 응답 `raw_name` → `File(dir(), name)` → 쓰기
- `getStringExtra("attach_path")` → `File(path)` → `readBytes` → 업로드

앞에서 정리한 source와 sink의 구도가 그대로 나타납니다. grep은 "위험한 API가 여기 있다"까지만 말합니다. **"외부에서 들어온 값이 저기까지 흘러간다"는 말하지 못합니다.** 세 개 다 한 줄씩 떼어놓고 보면 지극히 평범한 코드입니다. `new File(path)`가 그 자체로 취약점일 리는 없으니까요.

이것이 도구를 신뢰할 때 가장 위험한 지점이라고 봅니다. 표가 깔끔하게 나오면 "다 봤다"는 느낌이 드는데, 정작 심각한 셋이 표에 없었습니다.

### 4-2. 취약점이 겹칠 때의 파급

3-2의 화면은 `addJavascriptInterface` 한 줄과 URL 검증 누락 한 줄이 겹치면 어떻게 되는지를 보여줍니다. 둘 중 하나만 있었으면 이 화면은 나오지 않았을 것입니다. 브릿지가 있어도 우리 페이지만 로드했다면, 혹은 URL이 자유로워도 브릿지가 없었다면 그렇습니다. **취약점이 하나씩 있을 때보다 겹칠 때 급이 달라진다**는 것을 화면으로 확인했습니다.

### 4-3. 완전한 흐름 분석 대신 입력·싱크 대조표

taint 분석을 제대로 붙이려면 값이 대입과 함수 호출을 건너다니는 것을 전부 따라가야 하는데, 이 단계에서는 과합니다. 대신 **입력 지점과 싱크를 같이 나열하고 사람이 대조하는** 표를 하나 추가했습니다. 자동 판정이라고 주장하지 않는 것이 중요합니다. 아래는 그 표의 실제 출력입니다.

```
입력과 싱크가 같은 파일에 있는 곳:
  ApiClient.java, MemoDetailActivity.java, WebViewActivity.java

MemoDetailActivity.java:44   입력  getStringExtra   getIntent().getStringExtra("attach_path")
MemoDetailActivity.java:53   입력  getBooleanExtra  getIntent().getBooleanExtra("owner_override", false)
MemoDetailActivity.java:106  싱크  new File         File src = $attachPath != null ? new File($attachPath) : null;
MemoDetailActivity.java:109  싱크  readBytes        bytes = FilesKt.readBytes(src);
```

임의 파일 읽기의 경로가 네 줄로 보입니다. 클라이언트 측 인가의 `owner_override`도 같은 표에 올라옵니다.

표가 결론을 내주지는 않지만 **어디를 읽어야 하는지는 알려줍니다.** 이것을 붙이고 나서 10개 전부가 직접 탐지 또는 대조 후보로 드러나게 됐습니다.

### 4-4. 도구 조합과 의존성 축소의 효과

**apktool과 jadx는 보는 것이 다릅니다.** 앞에서 정리한 대로 apktool은 리소스와 매니페스트를 원형에 가깝게 되돌리고, jadx는 DEX를 읽을 수 있는 Java로 만듭니다. 실제로도 매니페스트 속성은 apktool 산출물이, 코드 로직은 jadx 산출물이 정확했습니다. 둘 중 하나만 쓰면 반쪽입니다.

**의존성을 줄여둔 것이 도움이 됐습니다.** 소스 2,972개 중 제 코드는 12개뿐이라 패키지 프리픽스로 좁히면 바로 찾힙니다. 3~4주차에 코루틴도 Retrofit도 쓰지 않은 이유가 이것이었는데, 실제로 효과를 봤습니다.

---

## 5. 시행착오와 정정

### 5-1. 브릿지 이름 오인과 열거 방법

**여기서 한 번 잘못 결론 낼 뻔했습니다.** 처음 캡처에서는 "브릿지 상태: 없음"이라고 나왔습니다. 테스트 페이지가 `window.MemoBridge`를 찾고 있었는데 앱이 붙인 실제 이름은 `MemoVaultBridge`였습니다. 이름 하나가 맞지 않아서 "노출 안 됨"으로 읽힐 뻔했습니다.

탐지 스크립트가 이름 후보를 순회하도록 고치고 다시 찍은 것이 3-2의 화면입니다. `Object.keys()`로는 브릿지 멤버가 비어 나와서 `for..in`으로 프로토타입 체인까지 훑어야 했던 것도 이때 알았습니다. **없다는 결과는 "없다"가 아니라 "내 방법으로는 못 찾았다"입니다.**

### 5-2. 하드코딩 문자열 표의 노이즈 원인

첫 리포트의 하드코딩 문자열 표가 **126행**이었습니다. 진짜 비밀 두 개가 136~137번째 줄에 파묻혀 있었습니다. 표가 있어도 아무도 읽지 않으면 없는 것과 같습니다.

원인이 두 개였습니다.

**첫째, Kotlin 컴파일러입니다.** Kotlin은 리플렉션 등에 쓰려고 클래스의 메타데이터를 `@Metadata` 어노테이션에 함께 넣어두는데, 여기에 클래스의 모든 메서드·필드 이름이 문자열 리터럴로 박혀 들어가고 jadx가 그것을 그대로 뱉습니다. 아래는 실제 역컴파일 결과의 일부입니다.

```java
@Metadata(mv={2,0,0}, k=1, xi=48,
  d1={" @\n\n ..."},
  d2={"Lkr/wtcy/memovault/ApiClient;", "<init>", "BASE_URL", "API_KEY",
      "ADMIN_FALLBACK_PASSWORD", "getPool", "parseLogin", ...})
```

`API_KEY`, `ADMIN_FALLBACK_PASSWORD`, `password` 같은 문자열이 여기서 대량으로 잡혔습니다. Kotlin 앱을 스캔할 때는 이 블록을 통째로 걸러야 합니다.

**둘째, 제 휴리스틱입니다.** "줄에 비밀 키워드가 있으면 그 줄의 리터럴을 의심"이라는 규칙이라 로그 포맷 문자열이 전부 걸렸습니다. 아래가 대표적으로 오탐을 만든 줄입니다.

```java
Log.d(TAG, "login() username=" + username + " password=" + password);
```

이 줄의 `" password="`라는 **리터럴 안의** `password=`를 변수 대입으로 읽고 있었습니다. 판정 전에 문자열 리터럴을 지우고 코드만 남겨서 검사하도록 고쳤습니다. 수정 전후를 비교하면 다음과 같습니다.

| | 수정 전 | 수정 후 |
| --- | ---: | ---: |
| 하드코딩 의심 문자열 | 126행 | **28행** |
| 진짜 비밀의 순위 | 136~137번째 | **1~2번째** |

네트워크 표에서도 `import java.net.HttpURLConnection;`(선언일 뿐)과 Kotlin이 생성한 `"null cannot be cast to non-null type"` 문자열을 URL로 잡던 것을 뺐습니다.

**도구를 만드는 것과 쓸 만한 도구를 만드는 것은 다릅니다.** 첫 리포트도 "동작"은 했습니다.

### 5-3. 테스트 서버의 HTTP 본문 미소진 버그

스크린샷을 다시 찍으려고 앱을 돌리다가 이상한 에러를 만났습니다. 아래는 테스트 서버가 남긴 출력입니다.

```
Bad request syntax ('우유, 계란, 커피 원두POST /upload HTTP/1.1')
```

메모 본문이 HTTP 요청 라인에 섞여 있습니다. 원인은 테스트 서버였습니다. 토큰이 만료돼 401로 조기 반환할 때 **요청 본문을 읽지 않고 응답**해버렸고, 남은 바이트가 소켓에 그대로 있다가 keep-alive 연결의 다음 요청 라인으로 파싱된 것입니다.

라우팅 전에 본문을 무조건 한 번 비우도록 고치고, 401 뒤에 같은 연결로 요청을 하나 더 보내서 정상 처리되는지 확인하는 회귀 테스트를 넣었습니다. 학습용 테스트 더블이라도 프로토콜을 어기면 앱 쪽 디버깅이 엉뚱한 방향으로 갑니다.

### 5-4. 도구 종료 코드와 apktool의 uses-sdk 이동

**apktool과 jadx 둘 다 정상 산출물을 내고도 경고와 함께 non-zero로 끝납니다.** 그래서 스크립트는 종료 코드가 아니라 **기대한 파일이 생겼는지**로 성공을 판정합니다. 1~2주차에 공통 환경 파일의 `set -e`를 걷어낸 것이 여기서 값을 했습니다. 고치지 않았다면 이 스크립트도 첫 경고에서 죽었을 것입니다.

**apktool 3.0.2는 `uses-sdk`를 매니페스트에서 빼서 `apktool.yml`로 옮깁니다.** 처음에는 min/targetSdk가 `미상`으로 나왔습니다. 디코드 결과를 원본과 동일하게 취급하면 안 되고, 도구가 무엇을 어디로 옮겼는지 알아야 합니다.

---

## 6. 도달 상태와 다음 구간

아래는 로드맵 대비 현재 진행 상태입니다.

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~2주 | Android 구조 정리 | 완료 |
| 3~4주 | 테스트 앱 작성 | 완료 |
| 5~6주 | 정적 분석 (Manifest·문자열·저장소·네트워크 표) | 완료 |
| 7~8주 | 동적 분석 | 다음 |

로드맵의 "다음 단계 판단 기준" 중 이번에 하나가 더 채워졌습니다. APK 하나를 정적 분석해서 컴포넌트·저장소·네트워크 표를 만들 수 있게 됐습니다. 남은 것은 수정과 재검증인데 9~10주차 항목입니다.

다음 구간은 동적 분석입니다. 이번에 만든 표의 각 행을 `adb`와 logcat으로 하나씩 밟아 확인할 차례입니다.

---

## 마치며

지난 글 마지막에 "출력은 맞는데 해석이 틀리는" 패턴이 네 번 나왔다고 적었는데, 이번 구간에서도 두 번 더 나왔습니다. 브릿지가 "없음"으로 보인 것과, 표 126행을 만들어놓고 쓸 만하다고 여긴 것입니다.

다만 성격이 조금 달라졌습니다. 지난번에는 도구 출력을 잘못 읽은 것이었고, 이번에는 **도구가 애초에 볼 수 없는 것**이 있다는 것을 확인한 쪽입니다. 데이터 흐름 셋은 아무리 정확히 읽어도 grep으로는 나오지 않습니다.

답을 아는 앱으로 도구를 돌려본 것이 이번 구간에서 제일 값어치 있었습니다. 모르는 앱이었다면 7개를 찾고 끝냈을 텐데, 나머지가 남아 있다는 것을 알 방법이 없었을 것입니다.
