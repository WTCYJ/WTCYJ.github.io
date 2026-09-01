---
layout: post
title: "What's in my container? — 이미지 레이어와 런타임 파일시스템의 차집합으로 봇넷 찾기"
date: 2026-07-16 21:00:00 +0900
category: 포렌식
author: WTCY
series: DFC 2026
tags: [DFC2026, 디지털포렌식, 컨테이너, Docker, OCI, ELF, 봇넷, Mirai, capstone, ChaCha20]
excerpt: "정상 빌드가 끝나고 13개월 뒤에 붙은 레이어가 시크릿을 평문 ENV로 심었고, 런타임에는 이미지에 없던 ELF 하나가 떨어져 있었다. C&C 포트를 '찾지 못했다'가 아니라 '바이너리에 없다'로 결론 내리기까지 세 갈래로 검증한 기록."
---

> **한 줄 결론**: 이미지 레이어 목록과 컨테이너 export 파일 목록의 **차집합** 이 런타임 투입 악성코드를 곧바로 드러냈고, C&C 포트는 문자열·디스어셈블·메모리 덤프 **세 방향에서 모두 부재**함을 확인해 "고정 포트 없음" 으로 확정했다.

## 무엇이 주어졌나

| 아티팩트 | 성격 |
|---|---|
| `webserver.tar` | OCI 이미지 아카이브 (레이어 + config blob) |
| `webserver_ts.tar` | 컨테이너 파일시스템 export |
| `memdump.14836` | 프로세스 메모리 덤프 |

`docker-artifacts.zip` 제공 MD5 는 `37c05eb7b64d411595cc0e0f6676dad2`.

이미지와 런타임 파일시스템이 **둘 다** 주어졌다는 점이 이 문제의 설계다. 하나만 있으면 "원래 있던 파일인지 나중에 떨어진 파일인지" 를 구분할 수 없다.

## 1. 이미지 히스토리 — 13개월의 공백

`webserver.tar` 의 `manifest.json` → image config blob(`blobs/sha256/3f22e85b…5bca3`)에서 `created` 와 `history` 배열을 읽었다. RepoTags 는 `webserver:latest`, author 는 `admin@cybercorp.com`.

| 시각 (UTC) | 레이어 명령 | 성격 |
|---|---|---|
| 2025-02-13 | node 22.14.0 / yarn 1.22.22 베이스 | 정상 베이스 |
| 2025-03-23 15:31:00 | `WORKDIR /app` | 정상 빌드 |
| 2025-03-27 14:38:33 | `COPY . .` | 정상 빌드 |
| 2025-03-27 14:39:27 | `RUN yarn && yarn build` | **정상 빌드의 마지막** |
| 2026-04-22 13:31:27 | `MAINTAINER admin@cybercorp.com` | 재빌드 구간 시작 |
| 2026-04-22 13:31:27 | `RUN apt-get update && apt-get install -y curl wget` | 다운로드 도구 확보 |
| 2026-04-22 13:31:27 | `ENV NODE_ENV / HOST / SUPABASE_SECRET_KEY` | **시크릿 평문 주입** |

정상 애플리케이션 빌드가 2025-03-27 에 끝나고, **약 13개월의 공백** 뒤에 세 개 레이어가 덧붙었다. image config 의 `created` 값도 이 마지막 레이어와 같다.

최종 빌드 시각은 `2026-04-22T13:31:27.931679448Z` — KST 로 2026-04-22 22:31:27.

레이어 히스토리는 Dockerfile 을 갖고 있지 않아도 **이미지 안에 그대로 보존된다.** 어떤 명령이, 어떤 순서로, 언제 실행됐는지가 다 남는다.

## 2. 차집합으로 악성코드 찾기

이미지 레이어 tar 의 파일 목록과 컨테이너 export 의 파일 목록을 대조해서, **이미지에는 없고 컨테이너에만 있는 파일**을 뽑았다.

| 파일 | 권한 / 크기 | 판정 |
|---|---|---|
| `tmp/manji.x86` | `-rwxrwxrwx` / 58,548 bytes | 이미지 레이어에 없음 → **런타임 투입** |
| `app/.next/*`, `opt/bitnami/*` | — | 이미지 레이어와 동일 → 정상 |

이 한 번의 비교로 후보가 하나로 좁혀졌다. 컨테이너 포렌식에서 이미지 원본을 같이 확보해야 하는 이유가 여기 있다 — **불변 기준선이 있으면 변조 탐지가 집합 연산이 된다.**

파일 식별:

```
헤더        : 7f 45 4c 46 (ELF)
아키텍처    : 32-bit little-endian Intel 80386
타입        : ET_EXEC
entry point : 0x08048164
SHA-256     : f68c42aa500783d6986c77a09c242ab345bda1ed7a1f1743df296631d2dae229
MD5         : ea841202db85f74ff8970ac004d541b3
```

문자열에 `joining botnet`, `attempting to connect to cnc`, `Starting attack`, raw socket 관련 메시지가 있어 ManjiBot 계열(Mirai 계통) DDoS 봇으로 판단했다.

## 3. 노출된 시크릿

image config 의 `config.Env` 배열:

```json
"Env": [
  "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
  "NODE_VERSION=22.14.0",
  "YARN_VERSION=1.22.22",
  "NODE_ENV=production",
  "HOST=0.0.0.0",
  "SUPABASE_SECRET_KEY=eyC73na0d0cm39cnd0a0dockmmadn"
]
```

`ENV` 는 이미지 메타데이터에 그대로 저장된다. 컨테이너를 실행하지 않아도, **이미지를 가진 사람은 누구나 평문으로 읽는다.** 이 레이어는 2026-04-22 재빌드 구간에 추가된 것으로, 2025-03-27 정상 빌드에는 없었다.

## 4. C&C 포트 — "못 찾음" 과 "없음" 의 차이

문자열에서 나온 것:

```
ManjiBot debug mode (t.me/syntraffic), (t.me/join_silence)
[main] ERROR: Failed to parse IP
[main] Using hardcoded IP: 94.156.152.67:%d      <-- IP는 리터럴, 포트는 %d
[main/conn]: attempting to connect to cnc
[main/conn]: timed out while connecting to C&C
[main/auth]: server authentication failed - disconnecting (honeypot detected)
```

로그 포맷이 `94.156.152.67:%d` 다. IP 만 하드코딩이고 포트는 런타임에 채워지는 포맷 변수다. 그런데 포트가 **다른 곳에** 하드코딩돼 있을 가능성이 남는다. 세 방향으로 확인했다.

**① 문자열 검색** — `:443`, `:1312` 같은 포트 리터럴이나 포트 설정 문자열은 없다. 존재하는 건 `esi port` 관련 오류 메시지뿐.

**② 디스어셈블 (capstone)** — 포트처럼 보이는 즉시값 두 개를 검토했다.

```asm
mov byte  ptr [ebx],   0x45      ; IPv4 version/IHL
mov word  ptr [ebx+2], 0x5865    ; <-- 포트로 오인하기 쉬운 값
mov byte  ptr [ebx+9], 6         ; protocol = TCP
```

주변 코드가 IP 헤더 필드를 직접 세팅하는 흐름이다. `sockaddr_in.sin_port` 가 아니라 **DDoS 모듈이 조립하는 raw IP/TCP 헤더** 였다. `0x3c00` 도 마찬가지.

이 구분이 이 문제에서 가장 조심스러웠던 부분이다. 16비트 즉시값은 포트로도, IP 헤더 필드로도, 그냥 상수로도 보인다. 주변 명령어를 같이 읽지 않으면 틀린 포트를 답으로 적게 된다.

**③ 메모리 덤프** — 런타임 확정 포트를 찾으려 `memdump.14836` 을 뒤졌다. 결과는 예상 밖이었다.

| 검색어 | 히트 |
|---|---|
| `node` | 10,000+ |
| `manji`, `ManjiBot`, `94.156.152.67` | **0** |

**이 덤프는 악성코드 프로세스가 아니라 Next.js/Node.js 웹서버 프로세스의 메모리다.** 파일명에 PID 가 붙어 있다고 그게 우리가 원하는 프로세스라는 보장은 없다. 여기서도 포트는 복구할 수 없었다.

그래서 답을 `94.156.152.67:%d` 로 적고, **"특정 포트 번호를 단정할 근거 없음"** 을 명시했다. 아무 포트나 찍는 것보다 이쪽이 맞다.

### 부가 확인 — 통신 암호화

문자열 테이블에 `expa` / `nd 3` / `2-by` / `te k` 가 4바이트씩 쪼개져 저장돼 있었다. 이어 붙이면 `expand 32-byte k` — ChaCha20 계열의 상수다. `Encrypted data`, `Decrypted data`, `encryption_initialized` 로그 문자열과 같이 보면 C&C 페이로드가 암호화돼 오간다.

## 종합 및 IOC

2025-03-27 에 정상 빌드된 Next.js 기반 SaaS 이미지가 2026-04-22 재빌드 단계에서 오염됐다. 이 재빌드에서 `curl`·`wget` 이 설치되고 Supabase 시크릿이 평문 ENV 로 주입됐으며, 컨테이너 런타임에는 이미지에 없던 ManjiBot 계열 봇넷이 투입돼 하드코딩된 C&C 로 접속을 시도한다.

| 구분 | IOC |
|---|---|
| 악성 파일 | `/tmp/manji.x86` (SHA-256 `f68c42aa…dae229`, MD5 `ea841202…41b3`) |
| C&C IP | `94.156.152.67` (포트는 런타임 `%d` — 고정 포트 아님) |
| Telegram 채널 | `t.me/syntraffic`, `t.me/join_silence` |
| 노출 자격증명 | `SUPABASE_SECRET_KEY=eyC73na0d0cm39cnd0a0dockmmadn` |
| 이미지 오염 시각 | `2026-04-22T13:31:27.931679448Z` (KST 22:31:27) |

## 정리 — 이 문제에서 남는 것

**이미지는 감사 로그다.** 레이어 히스토리에 명령과 시각이 그대로 남아 있어서, Dockerfile 없이도 "언제 무엇이 덧붙었는지" 가 복원된다. 13개월 공백은 육안으로 바로 보인다.

**컨테이너 포렌식의 기준선은 이미지다.** 런타임 파일시스템만 있으면 뭐가 원래 있던 건지 모른다. 이미지를 같이 확보하면 악성코드 탐지가 차집합 한 번으로 끝난다.

**메모리 덤프는 내용을 먼저 확인한다.** 파일명이 PID 를 달고 있어도 그게 분석 대상 프로세스라는 뜻은 아니다. 여기서는 문자열 카운트 한 번으로 잘못된 덤프임을 확인했다.

**없는 것은 없다고 쓴다.** 포트를 못 찾은 게 아니라 바이너리에 없다는 걸 세 방향으로 확인했다. `0x5865` 를 포트라고 우겼으면 그럴듯한 오답이 됐을 것이다.

---

*DFC 2026 출제 문제 103번에 대한 분석 기록. 2인 팀 참가 제출본을 블로그용으로 정리했다.*
