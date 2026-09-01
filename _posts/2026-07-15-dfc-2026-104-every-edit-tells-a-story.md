---
layout: post
title: "Every Edit Tells a Story — 안드로이드 아티팩트로 AI 생성 영상의 출처를 되짚기"
date: 2026-07-15 21:00:00 +0900
category: 포렌식
author: WTCY
series: DFC 2026
tags: [DFC2026, 디지털포렌식, 모바일포렌식, Android, WebView, HTTP캐시, SQLite, MHTML, MediaStore, AI]
excerpt: "생성형 AI로 만든 영상이 남의 작품을 베낀 것인지 물어보는 문제. WebView HTTP 캐시에서 프롬프트 원문이 그대로 나왔지만, 요청 필드의 referenceBlobs 는 비어 있었다 — '정황은 강하지만 직접 첨부는 미확인'으로 답을 끊은 이유."
---

> **한 줄 결론**: Firefly WebView HTTP 캐시에서 **프롬프트 원문·모델·시드까지** 복원했고 브라우저 DB 로 사전 수집 경로도 재구성했지만, 생성 요청의 `referenceBlobs` 가 빈 배열이라 **"수집은 입증, 직접 첨부는 미확인"** 으로 결론을 끊었다.

## 사건과 증거

안드로이드 기기 이미지 하나. 인물 C 가 생성형 AI 로 티저 영상을 만들었는데, 그 영상이 인물 H 의 창작물을 무단으로 활용한 것인지가 쟁점이다.

> **개인정보 처리**: 사건에 등장하는 SNS 계정 식별자와 계정 ID 는 이 글에서 `@[H계정]` 으로 대체했다. 분석 절차와 아티팩트 경로는 원본 그대로다.

도구는 WSL 위의 표준 조합 — `rg`, `file`, Python 3.12 의 `sqlite3` 모듈, coreutils/findutils.

## 1. 어떤 AI 서비스를 썼나

기기 앱 디렉터리를 훑으면 결론이 빨리 난다.

```bash
find /Android/data/data -maxdepth 1 -type d
```

ChatGPT·Claude·Canva 등 다른 AI 앱 데이터는 **전혀 없고** `com.adobe.firefly` 만 있다. Firefly 는 내부적으로 두 백엔드 모델을 호출했다.

| 용도 | modelId | modelVersion |
|---|---|---|
| 영상 생성 | `veo` | `3.1-fast-generate` (Google Veo 3.1) |
| 이미지 합성 | `gemini-flash` | Gemini Flash (nano-banana) |

근거는 WebView HTTP 캐시다.

```
/data/data/com.adobe.firefly/cache/WebView/Default/HTTP Cache/Cache_Data/c6d406397e97ba61_0
```

여기에 `platform-cs-edge*.adobe.io`, `bks-epo8552.adobe.io/v2/jobs/result/...` 요청/응답이 통째로 남아 있다. **앱이 WebView 로 API 를 호출하면 요청 본문과 응답이 디스크 캐시에 그대로 떨어진다** — 모바일에서 "무엇을 서버에 보냈나" 를 복원할 수 있는 몇 안 되는 경로다.

## 2. 프롬프트 원문 복원

같은 캐시 파일을 UTF-8 로 읽으면 요청 파라미터가 전부 나온다.

| 항목 | 값 |
|---|---|
| 콘텐츠 유형 | `application/vnd.adobe.firefly-generation-video+dcx` |
| 모듈 | `text2video` / `ff-video-generate` |
| 프롬프트 | `나비가 날개를 펄럭이며 날아가는 영상 제작해줘` |
| Negative prompt | `cartoon, vector art, & bad aesthetics & poor aesthetic` |
| 생성 파라미터 | duration 8초, generateAudio false, seed 493171, 720x1280, n 1 |
| **referenceBlobs** | **`[]`** |
| HTTP Date | Fri, 26 Jun 2026 02:12:10 GMT (KST 11:12:10) |

결과물은 공유 저장소와 앱 내부 캐시 양쪽에 있다.

```
/data/media/0/Movies/Firefly 나비가 날개를 펄럭이며 날아가는 영상 제작해줘 493171.mp4
/data/data/com.adobe.firefly/cache/Firefly …493171.mp4
```

두 파일의 MD5 가 `18816e9946085ecc36898e12759c00ac` 로 동일하다. 파일명에 프롬프트와 시드가 그대로 박히는 Firefly 의 명명 규칙 덕분에, MP4 파일 하나만 봐도 어떤 요청의 산출물인지 알 수 있다.

## 3. H 의 작품은 언제 수집됐나

여기서부터 브라우저 아티팩트가 일한다. Samsung Internet(`com.sec.android.app.sbrowser`)의 History DB 를 SQLite 로 읽었다.

```
/data/data/com.sec.android.app.sbrowser/app_sbrowser/Default/History
→ urls, downloads, downloads_url_chains
```

`downloads_url_chains` 에 Instagram CDN(`scontent-ssn1-1.cdninstagram.com`)의 `.webp` URL 이 남았고, 두 다운로드의 `tab_url` 은 브라우저 reading list MHTML 스냅샷으로 연결된다.

```
content://com.sec.android.app.sbrowser/readinglist/0623145459.mhtml
content://com.sec.android.app.sbrowser/readinglist/0623150713.mhtml
```

MHTML 안에는 `Snapshot-Content-Location`(Instagram 게시물 URL)과 `Content-Location`(이미지 CDN URL)이 둘 다 들어 있다. **"어떤 페이지를 보다가 어떤 이미지를 받았는지" 가 스냅샷 파일 하나에 봉인된다.**

## 4. 타임라인 (KST)

| 시각 | 증거 | 의미 |
|---|---|---|
| 06-23 14:44:09 | Instagram `USER_PREFERENCES.xml` 의 `recent_user_searches_with_ts` | 앱에서 H 계정 검색 |
| 06-23 14:51:34 | Samsung Internet History — H 프로필 | 브라우저로 프로필 열람 |
| 06-23 14:52:47 | History — H 게시물 | 게시물 열람 |
| 06-23 14:55:20 | downloads id 2, CDN `728186683…webp` | **작품 1 다운로드 시작** |
| 06-23 14:55:24 | `/data/media/0/Download/728186683…webp` mtime | 작품 1 저장 완료 |
| 06-23 15:06:57 | History — 다른 H 게시물 | 열람 |
| 06-23 15:07:27 | downloads id 4, CDN `727501805…webp` | **작품 2 다운로드 시작** |
| 06-23 15:07:30 | 파일 mtime | 작품 2 저장 완료 |
| **06-26 11:12:10** | Firefly HTTP Cache `Date` 헤더 | **영상 생성 요청** |
| 06-26 11:12:28 | `/data/media/0/Movies/…493171.mp4` | 생성 영상 저장 |
| 06-26 11:17:31~ | History — `fastdl.app/en2`, downloads id 6–9 | 영상 생성 후에도 같은 주제 수집 지속 |

H 의 작품 수집이 영상 생성보다 **사흘 앞선다.** 순서 자체가 정황의 핵심이다.

Instagram 앱 `shared_prefs` 는 이걸 보강한다 — `BanyanCache.xml`·`usersBootstrapService.xml` 에 H 계정이 `PrivacyStatusPrivate`(비공개) 이면서 `FollowStatusFollowing`(팔로우 중) 으로 기록돼 있다. 비공개 계정을 팔로우한 상태에서 접근했다는 뜻이다.

## 5. 수집 방법이 두 갈래였다

Android MediaStore(`external.db`)의 레코드에 답이 있다.

```
owner_package_name = com.sec.android.app.sbrowser
referer_uri        = https://fastdl.app/
```

- **06-23 (작품 1·2)**: Samsung Internet 으로 Instagram 게시물을 직접 열람 → 브라우저 다운로드
- **06-26 (영상 생성 이후)**: `fastdl.app` 이라는 인스타그램 다운로더 사이트에 게시물 URL 을 넣어 원본 이미지 확보

MediaStore 는 파일 자체가 아니라 **"누가 이 파일을 넣었고 어떤 페이지에서 왔는지"** 를 기록한다. `owner_package_name` 과 `referer_uri` 두 컬럼이 수집 경로를 그대로 말해 준다.

## 6. 결론을 어디서 끊을 것인가

여기까지 확정된 것:

- C 가 Adobe Firefly text-to-video 로 8초 720x1280 영상을 생성했다 — **입증**
- 프롬프트가 `나비가 날개를 펄럭이며 날아가는 영상 제작해줘` 였다 — **입증**
- 영상 생성 사흘 전에 H 의 나비 작품 2점을 다운로드해 보관했다 — **입증**
- 영상 생성 이후에도 같은 주제 이미지를 계속 수집했다 — **입증**

확정되지 **않은** 것:

- 다운로드한 H 의 작품이 Firefly 요청에 **첨부**됐는가 — **미확인**

생성 요청의 `referenceBlobs` 가 빈 배열이다. image-to-video 나 참조 이미지 기반 생성이었다면 여기에 blob 참조가 들어간다. 순수 text-to-video 요청이었다는 뜻이다.

그래서 최종 판단을 이렇게 적었다.

> **"AI 서비스 사용은 입증, H 창작물 수집 및 동일 주제 활용 정황은 강함, 영상 요청에 대한 직접 첨부는 미확인."**

정황이 아무리 강해도 — 사흘 전 수집, 같은 주제, 계속되는 수집 행위 — `referenceBlobs: []` 를 무시하고 "AI 에 넣었다" 고 쓸 수는 없다. 요청 필드가 명시적으로 비어 있다는 것은 침묵이 아니라 **반대 방향의 증거**다.

## 7. 증거 추출 자동화

문서에 적은 원본 증거 파일 15개를 복사하고 매니페스트를 만드는 스크립트를 따로 뒀다. 각 파일에 대해 원본 경로, 크기, KST mtime, MD5, SHA-256 을 TSV 로 남긴다.

```python
rows.append({
    "id": item["id"],
    "category": item["category"],
    "description": item["description"],
    "original_path": str(source),
    "extracted_path": str(dest),
    "size_bytes": source.stat().st_size,
    "mtime_kst": kst_mtime(source),
    "md5": file_hash(source, "md5"),
    "sha256": file_hash(source, "sha256"),
})
```

Chrome 계열 타임스탬프(1601-01-01 기준 마이크로초)를 KST 로 바꾸는 변환도 같이 넣었다. Samsung Internet 은 Chromium 기반이라 History DB 의 시간이 전부 이 형식이다.

```python
def chrome_ts(us):
    epoch = dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc)
    return (epoch + dt.timedelta(microseconds=int(us))).astimezone(KST)
```

스크립트 복사본을 결과 폴더 안에 같이 넣어 뒀다. 다른 조사관이 매니페스트만 보고 같은 결과를 재현할 수 있어야 하기 때문이다.

## 정리 — 이 문제에서 남는 것

**WebView 캐시는 모바일에서 요청 본문을 볼 수 있는 창구다.** 앱이 네이티브 HTTP 를 쓰면 이런 게 안 남지만, WebView 로 API 를 부르는 앱은 프롬프트·모델·파라미터가 통째로 디스크에 남는다.

**브라우저 아티팩트는 세 겹으로 겹친다.** History `urls`(무엇을 봤나) → `downloads`/`downloads_url_chains`(무엇을 받았나) → reading list MHTML(그때 페이지가 어떻게 생겼나). 어느 하나가 지워져도 나머지로 재구성된다.

**MediaStore 의 메타데이터가 파일 자체보다 많은 걸 말한다.** `owner_package_name` 과 `referer_uri` 만으로 수집 경로 두 갈래가 갈렸다.

**빈 필드도 증거다.** `referenceBlobs: []` 하나가 "정황상 확실" 을 "미확인" 으로 되돌렸다. 결론을 정황이 아니라 데이터가 허용하는 지점에서 끊는 것이 포렌식이다.

---

*DFC 2026 출제 문제 104번에 대한 분석 기록. 2인 팀 참가 제출본을 블로그용으로 정리했다.*
