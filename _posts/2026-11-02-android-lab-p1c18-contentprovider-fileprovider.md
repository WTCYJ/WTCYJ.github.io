---
layout: post
title: "ContentProvider·FileProvider 실습 — 데이터 유출·SQLi·traversal"
date: 2026-11-02 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ContentProvider, FileProvider, SQLi]
excerpt: "exported ContentProvider가 무권한이면 아무 앱이 query/insert/openFile로 데이터를 읽고, selection에 입력을 이어붙이면 SQL injection, 커스텀 openFile이면 path traversal이 된다. 반면 표준 androidx FileProvider의 getUriForFile은 정규화해서 ../를 막으니, 진짜 위험은 지나치게 넓은 <paths>(root-path) 설정이다."
---

ContentProvider는 앱 데이터의 직접 표면이다. exported provider가 무권한이면 아무 앱이 데이터를 읽고, selection에 입력을 이어붙이면 SQLi, 커스텀 openFile이면 path traversal이 된다. 반면 표준 FileProvider는 정규화로 `../`를 막으니 위험이 코드가 아니라 설정에 있다. 이 글은 exported provider의 데이터 유출·SQLi·traversal과 FileProvider 오설정을 교육용 앱에서 재현하는 기록이다.

> **한 줄 결론**: exported+무권한 provider는 `content query`로 직접 읽히고, selection 이어붙이기는 SQLi, 커스텀 openFile은 traversal이 된다. 표준 FileProvider는 정규화로 안전하니 진짜 위험은 과도한 `<paths>`다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 provider 유출·SQLi·traversal과 FileProvider 오설정을 다룬다. 선수 개념은 [가시성·URI(C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)·[컴포넌트(C21)](/posts/android-concept-atlas-c21-components-binder/)다.

## 핵심 개념 — provider와 FileProvider

- **exported provider**: 기본 exported가 **API 17 이전은 true, 이후 false**. exported+무권한 = 아무 앱이 `query/insert/update/delete/openFile`. `adb shell content query --uri content://authority/path`. `Source-confirmed`
- **SQLi**: `selection`에 미신뢰 입력을 이어붙이면 주입 — selectionArgs 파라미터화가 방어.
- **path traversal**: **커스텀 `openFile`**에서 경로 검증이 없으면 `../`로 의도 밖 파일. **표준 androidx `FileProvider.getUriForFile`은 `getCanonicalPath` 정규화로 escape를 거부** → 진짜 위험은 **과도한 `<paths>`**(예: root-path). `Source-confirmed`

**신뢰 경계와 위협 모델.** provider의 신뢰 경계는 exported+permission+입력 검증이다. 표준 FileProvider는 안전하나 설정(`<paths>`)이 넓으면 노출된다.

> **[그림 1]** `content query`로 exported 무권한 provider의 전체 사용자 데이터를 읽은 화면(값 마스킹) — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱: exported provider(무권한·SQLi·커스텀 openFile traversal) + 과도한 `<paths>` + 방어 버전(권한·parameterized·표준 FileProvider·좁은 paths).

## 실습 절차와 관측

### 가설
취약 provider는 `content query`로 전 사용자 유출·SQLi·traversal 성립, 방어 버전은 권한/파라미터화/표준 FileProvider로 차단. `Inferred`

### 절차
1. exported provider 목록을 얻는다(6장).
2. `content query`로 무권한 읽기를 확인한다.
3. selection 주입으로 SQLi를 시도한다.
4. 커스텀 openFile에 `../` traversal을 시도한다.
5. 방어 버전에서 전부 차단을 확인한다.

```bash
adb shell content query --uri content://com.example.app.provider/users
adb shell content query --uri "content://com.example.app.provider/users" --where "name='a' OR '1'='1'"
```

> **[그림 2]** selection 주입(SQLi)으로 조건이 무력화돼 전체 행이 반환된 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ content query --uri content://com.example.app.provider/users --where "1=1"
Row: 0 id=1, name=admin, token=...   # 무권한 유출 (취약)
```

## Root Cause — 왜 이렇게 되는가

표준 FileProvider가 안전한 것은 정규화가 escape를 막기 때문이다 — 그래서 취약점은 코드가 아니라 **설정(넓은 paths)·커스텀 구현**에서 나온다. SQLi는 입력을 코드로 취급한 것이고, exported 무권한은 애초에 경계가 없는 것이다.

## 방어와 회귀 검증

- (개발자) exported 최소·권한·parameterized selection·표준 FileProvider·좁은 `<paths>`·URI 권한 위임. "무권한 provider 읽기 불가", "SQLi 미성립", "content:// 가 의도 파일만"을 회귀로.
- (연구자) 자작만.

**흔한 실패와 처리.** `Permission Denial` → provider 권한 있음(방어). traversal 실패 → 표준 FileProvider(정규화)이니 커스텀/paths를 확인.

## 버전 차이와 한계

- API 17 provider 기본 false. scoped storage(A10/11)로 외부 접근 축소(C43/C44).
- 에뮬/자작. 상용 provider 공격 금지.

## 정리

- exported+무권한 provider는 직접 유출.
- SQLi는 parameterized로, traversal은 커스텀/넓은 paths에서만.
- 표준 FileProvider는 정규화로 안전.

**점검 질문** — (1) provider exported 기본값은 API 17 전후로? (2) 표준 FileProvider가 `../`에 안전한 이유는? (3) FileProvider의 진짜 위험 설정은?

**참고** — [content-provider](https://developer.android.com/guide/topics/providers/content-provider-basics) · [FileProvider](https://developer.android.com/reference/androidx/core/content/FileProvider) · [C11 가시성·URI](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)

*다음 글: [PendingIntent와 URI grant 실습](/posts/android-lab-p1c19-pendingintent-uri-grant/).*
