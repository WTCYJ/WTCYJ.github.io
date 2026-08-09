---
layout: post
title: "Android 보안 스터디 5~6주차 — 정적 분석이 못 잡는 것을 확인했다"
date: 2026-08-09
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 정적분석, jadx, apktool, aapt2, APK, DEX, AndroidManifest, WebView, addJavascriptInterface, 딥링크, exported, 데이터흐름, taint, Kotlin, Metadata, 취약점분석, 학습기록]
excerpt: "직접 만든 앱을 APK에서부터 다시 분석했습니다. 심어둔 약점 10개 중 자동 리포트가 잡은 건 7개였고, 못 잡은 셋은 전부 데이터 흐름 문제였습니다. 첫 리포트의 하드코딩 문자열 표가 126행 노이즈였던 원인과, WebView 브릿지 노출을 정적 분석에서 동적 확인까지 이어붙인 과정을 정리했습니다."
---

> **진행 구간**: 24주 로드맵의 5~6주차 (정적 분석)
> **대상**: `kr.wtcy.memovault` debug APK · 5,945,029 bytes · SHA-256 `d1815d75…c71cdd01`
> **도구**: apktool · jadx 1.5.5 · aapt2 34.0.0 · 자작 리포트 스크립트
> **이전 글**: [1~4주차 진행 기록](/posts/android-security-study-week1-4/) · [24주 로드맵](/posts/android-security-study-roadmap/)

---

## 0. 이번 구간의 질문

3~4주차에 만든 앱에는 현실적인 실수 패턴 10개를 일부러 심어뒀습니다. 이번엔 그 앱을 **분석 대상으로만** 다뤘습니다. 소스를 안 보고 APK에서 출발해 표를 만든 뒤, 마지막에 정답표와 대조했습니다.

궁금했던 건 "취약점을 찾을 수 있나"가 아니라 **"자동 분석이 무엇을 못 찾나"**였습니다. 답을 아는 상태에서 도구를 돌려보는 건 이번이 아니면 하기 어렵습니다.

---

## 1. 파이프라인

`static-analyze.sh <apk> <label>` 한 줄로 디코드 → 디컴파일 → 리포트까지 돕니다. 49초 걸렸고 jadx가 소스 2,972개를 뽑았습니다.

나온 표는 아홉 개입니다. 컴포넌트 노출, 권한, 앱 전역 플래그, 딥링크, 저장소 호출 지점, 네트워크 호출 지점, 로그 출력 지점, WebView 설정, 하드코딩 의심 문자열.

컴포넌트 표부터 답이 보입니다.

| 컴포넌트 | exported | permission | intent-filter |
| --- | --- | --- | --- |
| `LoginActivity` | true | - | MAIN / LAUNCHER |
| `MemoListActivity` | true | - | OPEN_MEMOS / DEFAULT |
| `MemoDetailActivity` | true | - | VIEW_MEMO / DEFAULT |
| `WebViewActivity` | true | - | VIEW / DEFAULT, BROWSABLE, `memovault://notice` |
| `ProfileInstallReceiver` | true | `android.permission.DUMP` | (androidx가 넣음) |
| `InitializationProvider` | false | - | 내부 전용 |

액티비티 4개가 전부 exported인데 권한 가드가 없습니다. 런처는 정상이고 나머지 3개가 문제입니다.

`ProfileInstallReceiver`는 제가 쓴 게 아니라 androidx가 넣은 것이고 `DUMP` 권한으로 막혀 있습니다. **빌드 도구가 합성한 항목과 내가 쓴 항목을 구분하지 않으면 남의 코드를 내 취약점으로 보고하게 됩니다.**

WebView 설정은 한 화면에 몰려 있었습니다.

```
WebViewActivity.java:25  setJavaScriptEnabled     true
WebViewActivity.java:26  setAllowFileAccess       true
WebViewActivity.java:27  setAllowContentAccess    true
WebViewActivity.java:29  setMixedContentMode      0     (ALWAYS_ALLOW)
WebViewActivity.java:30  addJavascriptInterface   new NoticeBridge(this), "MemoVaultBridge"
WebViewActivity.java:41  loadUrl                  url   (검증 없음)
```

브릿지에 붙은 메서드 이름이 `getSessionToken`, `getUsername`, `getApiKey`, `readFile`입니다. 딥링크로 임의 URL을 띄울 수 있으니 외부 페이지가 이걸 부를 수 있다는 뜻입니다.

---

## 2. 정적에서 끝내지 않고 눌러봤다

여기까지는 "그럴 수 있다"입니다. 실제로 되는지 확인했습니다. 딥링크 하나면 됩니다.

```bash
adb shell am start -a android.intent.action.VIEW -d "memovault://notice"
```

![WebView로 열린 공지 페이지. "브릿지 상태: 노출됨 → window.MemoVaultBridge : getApiKey, getSessionToken, getUsername, readFile" 이라고 표시돼 있다](/assets/img/android-security-study/05-webview-bridge.png)

페이지 안의 자바스크립트가 `window.MemoVaultBridge`를 찾아내고 메서드 네 개를 그대로 열거했습니다. 정적 분석에서 본 그 이름입니다.

**여기서 한 번 잘못 결론 낼 뻔했습니다.** 처음 캡처에서는 "브릿지 상태: 없음"이라고 나왔습니다. 테스트 페이지가 `window.MemoBridge`를 찾고 있었는데 앱이 붙인 실제 이름은 `MemoVaultBridge`였습니다. 이름 하나 안 맞아서 "노출 안 됨"으로 읽힐 뻔했습니다.

탐지 스크립트가 이름 후보를 순회하도록 고치고 다시 찍으니 위 화면이 나왔습니다. `Object.keys()`로는 브릿지 멤버가 비어 나와서 `for..in`으로 프로토타입 체인까지 훑어야 했던 것도 이때 알았습니다. **없다는 결과는 "없다"가 아니라 "내 방법으로는 못 찾았다"입니다.**

---

## 3. 정답표와 대조 — 7/10

심어둔 10개 중 자동 리포트가 잡은 건 7개였습니다.

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

못 잡은 셋의 공통점이 분명했습니다. **전부 데이터 흐름 문제입니다.**

- `optBoolean("is_admin")` → 세션 저장 → 관리자 버튼 노출
- 서버 응답 `raw_name` → `File(dir(), name)` → 쓰기
- `getStringExtra("attach_path")` → `File(path)` → `readBytes` → 업로드

grep은 "위험한 API가 여기 있다"까지만 말합니다. **"외부에서 들어온 값이 저기까지 흘러간다"는 못 말합니다.** 세 개 다 한 줄씩 떼어놓고 보면 지극히 평범한 코드입니다. `new File(path)`가 그 자체로 취약점일 리는 없으니까요.

이게 도구를 신뢰할 때 가장 위험한 지점이라고 봅니다. 표가 깔끔하게 나오면 "다 봤다"는 느낌이 드는데, 정작 심각한 셋이 표에 없었습니다.

---

## 4. 완전한 흐름 분석 대신 대조표

taint 분석을 제대로 붙이는 건 이 단계에서 과합니다. 대신 **입력 지점과 싱크를 같이 나열하고 사람이 대조하는** 표를 하나 추가했습니다. 자동 판정이라고 주장하지 않는 게 중요합니다.

```
입력과 싱크가 같은 파일에 있는 곳:
  ApiClient.java, MemoDetailActivity.java, WebViewActivity.java

MemoDetailActivity.java:44   입력  getStringExtra   getIntent().getStringExtra("attach_path")
MemoDetailActivity.java:53   입력  getBooleanExtra  getIntent().getBooleanExtra("owner_override", false)
MemoDetailActivity.java:106  싱크  new File         File src = $attachPath != null ? new File($attachPath) : null;
MemoDetailActivity.java:109  싱크  readBytes        bytes = FilesKt.readBytes(src);
```

임의 파일 읽기의 경로가 네 줄로 보입니다. 클라이언트 측 인가의 `owner_override`도 같은 표에 올라옵니다.

표가 결론을 내주진 않지만 **어디를 읽어야 하는지는 알려줍니다.** 이걸 붙이고 나서 10개 전부가 직접 탐지 또는 대조 후보로 드러나게 됐습니다.

---

## 5. 리포트가 안 읽힐 뻔한 이유

첫 리포트의 하드코딩 문자열 표가 **126행**이었습니다. 진짜 비밀 두 개가 136~137번째 줄에 파묻혀 있었습니다. 표가 있어도 아무도 안 읽으면 없는 것과 같습니다.

원인이 두 개였습니다.

**첫째, Kotlin 컴파일러.** `@Metadata` 어노테이션에 클래스의 모든 메서드·필드 이름이 문자열 리터럴로 박혀 들어가고, jadx가 그걸 그대로 뱉습니다.

```java
@Metadata(mv={2,0,0}, k=1, xi=48,
  d1={" @\n\n ..."},
  d2={"Lkr/wtcy/memovault/ApiClient;", "<init>", "BASE_URL", "API_KEY",
      "ADMIN_FALLBACK_PASSWORD", "getPool", "parseLogin", ...})
```

`API_KEY`, `ADMIN_FALLBACK_PASSWORD`, `password` 같은 문자열이 여기서 대량으로 잡혔습니다. Kotlin 앱을 스캔할 땐 이 블록을 통째로 걸러야 합니다.

**둘째, 제 휴리스틱.** "줄에 비밀 키워드가 있으면 그 줄의 리터럴을 의심"이라는 규칙이라 로그 포맷 문자열이 전부 걸렸습니다.

```java
Log.d(TAG, "login() username=" + username + " password=" + password);
```

이 줄의 `" password="`라는 **리터럴 안의** `password=`를 변수 대입으로 읽고 있었습니다. 판정 전에 문자열 리터럴을 지우고 코드만 남겨서 검사하도록 고쳤습니다.

| | 수정 전 | 수정 후 |
| --- | ---: | ---: |
| 하드코딩 의심 문자열 | 126행 | **28행** |
| 진짜 비밀의 순위 | 136~137번째 | **1~2번째** |

네트워크 표에서도 `import java.net.HttpURLConnection;`(선언일 뿐)과 Kotlin이 생성한 `"null cannot be cast to non-null type"` 문자열을 URL로 잡던 걸 뺐습니다.

**도구를 만드는 것과 쓸 만한 도구를 만드는 건 다릅니다.** 첫 리포트도 "동작"은 했습니다.

---

## 6. 덤으로 잡은 서버 버그

스크린샷을 다시 찍으려고 앱을 돌리다가 이상한 에러를 만났습니다.

```
Bad request syntax ('우유, 계란, 커피 원두POST /upload HTTP/1.1')
```

메모 본문이 HTTP 요청 라인에 섞여 있습니다. 원인은 테스트 서버였습니다. 토큰이 만료돼 401로 조기 반환할 때 **요청 본문을 읽지 않고 응답**해버렸고, 남은 바이트가 소켓에 그대로 있다가 keep-alive 연결의 다음 요청 라인으로 파싱된 겁니다.

라우팅 전에 본문을 무조건 한 번 비우도록 고치고, 401 뒤에 같은 연결로 요청을 하나 더 보내서 정상 처리되는지 확인하는 회귀 테스트를 넣었습니다. 학습용 테스트 더블이라도 프로토콜을 어기면 앱 쪽 디버깅이 엉뚱한 방향으로 갑니다.

---

## 7. 그 밖에

**apktool과 jadx는 보는 게 다릅니다.** apktool은 리소스와 매니페스트를 원형에 가깝게 되돌리고, jadx는 DEX를 읽을 수 있는 Java로 만듭니다. 매니페스트 속성은 apktool 산출물이, 코드 로직은 jadx 산출물이 정확했습니다. 둘 중 하나만 쓰면 반쪽입니다.

**둘 다 정상 산출물을 내고도 경고와 함께 non-zero로 끝납니다.** 그래서 스크립트는 종료 코드가 아니라 **기대한 파일이 생겼는지**로 성공을 판정합니다. 1~2주차에 공통 환경 파일의 `set -e`를 걷어낸 게 여기서 값을 했습니다. 안 고쳤으면 이 스크립트도 첫 경고에서 죽었을 겁니다.

**apktool 3.0.2는 `uses-sdk`를 매니페스트에서 빼서 `apktool.yml`로 옮깁니다.** 처음엔 min/targetSdk가 `미상`으로 나왔습니다. 디코드 결과를 원본과 동일하게 취급하면 안 되고, 도구가 무엇을 어디로 옮겼는지 알아야 합니다.

**의존성을 줄여둔 게 도움이 됐습니다.** 소스 2,972개 중 제 코드는 12개뿐이라 패키지 프리픽스로 좁히면 바로 찾힙니다. 3~4주차에 코루틴도 Retrofit도 안 쓴 이유가 이거였는데, 실제로 효과를 봤습니다.

---

## 8. 6주차 도달 상태

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~2주 | Android 구조 정리 | 완료 |
| 3~4주 | 테스트 앱 작성 | 완료 |
| 5~6주 | 정적 분석 (Manifest·문자열·저장소·네트워크 표) | 완료 |
| 7~8주 | 동적 분석 | 다음 |

로드맵의 "다음 단계 판단 기준" 중 이번에 하나가 더 채워졌습니다. APK 하나를 정적 분석해서 컴포넌트·저장소·네트워크 표를 만들 수 있게 됐습니다. 남은 건 수정과 재검증인데 9~10주차 항목입니다.

다음 구간은 동적 분석입니다. 이번에 만든 표의 각 행을 `adb`와 logcat으로 하나씩 밟아 확인할 차례입니다.

---

## 남은 기록

지난 글 마지막에 "출력은 맞는데 해석이 틀리는" 패턴이 네 번 나왔다고 적었는데, 이번 구간에서도 두 번 더 나왔습니다. 브릿지가 "없음"으로 보인 것과, 표 126행을 만들어놓고 쓸 만하다고 여긴 것입니다.

다만 성격이 조금 달라졌습니다. 지난번엔 도구 출력을 잘못 읽은 거였고, 이번엔 **도구가 애초에 볼 수 없는 것**이 있다는 걸 확인한 쪽입니다. 데이터 흐름 셋은 아무리 정확히 읽어도 grep으로는 안 나옵니다.

답을 아는 앱으로 도구를 돌려본 게 이번 구간에서 제일 값어치 있었습니다. 모르는 앱이었으면 7개 찾고 끝냈을 텐데, 3개가 남아 있다는 걸 알 방법이 없었을 겁니다.
