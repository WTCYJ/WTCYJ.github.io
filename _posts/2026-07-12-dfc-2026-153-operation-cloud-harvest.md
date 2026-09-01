---
layout: post
title: "Operation Cloud Harvest — CloudTrail 11,562건에서 진짜 침해만 골라내기"
date: 2026-07-12 21:00:00 +0900
category: 포렌식
author: WTCY
series: DFC 2026
tags: [DFC2026, 디지털포렌식, 클라우드포렌식, AWS, CloudTrail, GuardDuty, VPCFlowLog, S3, IAM, 오탐]
excerpt: "GuardDuty 알림 11건 중 7건이 오탐이었다. 가장 이른 '악성 IP' 알림은 정상 컴플라이언스 스캐너였고, 진짜 최초 침투는 그 나흘 뒤 Tor에서 왔다. 시각순으로 읽으면 틀리는 사건."
---

> **한 줄 결론**: 알림을 시각순으로 읽으면 최초 침투를 나흘 앞당겨 오답한다. **알림 → CloudTrail 역추적 → userAgent·세션명 확인**의 순서로 검증해야 오탐 7건이 걸러지고, 유출 규모는 요청 수가 아니라 **HTTP 200 응답 수**로 세야 한다.

## 무엇이 주어졌나

| 파일 | 제공 MD5 |
|---|---|
| `cloudtrail.json` | `BE026659D4EE10B249501D062DE21682` |
| `guardduty_findings.json` | `030AE2E3DC135C74FDD5AD6795012962` |
| `route53_resolver_logs.json` | `027061385FAFC86BCB7D9AB110B1EBEC` |
| `s3_access_logs.log` | `0BD73BAC95420F9634F838E1C1A499FD` |
| `vpc_flow_logs.csv` | `F8560106849E013C034641E88F96CD47` |

CloudTrail 만 **11,562건**이다. 대부분 정상 운영 이벤트라 전수 조사는 의미가 없다. 의심 IP · 의심 자격증명 · 권한 변경 계열 API 를 축으로 잡고 필터링했다. 시각은 로그 원본 표기대로 UTC.

## 1. 최초 접근 — AKIA 냐 ASIA 냐

GuardDuty 에서 심각도 8.0 이상만 먼저 보고, 그 알림의 주체를 CloudTrail 에서 역추적했다. 자격증명 성격은 접두사로 갈린다 — **`AKIA` = 장기(사용자) 키, `ASIA` = STS 임시 키.**

| 시각 (UTC) | 이벤트 | 주체 / 키 | Source IP |
|---|---|---|---|
| 2024-03-12 01:23:11 | `GetCallerIdentity` | `ji.hyun.park` / `AKIAIOSFODNN7PARK01` | 185.220.101.34 |
| 2024-03-12 01:24:28 | `ListBuckets` | 동일 | 동일 |
| 2024-03-12 01:27:30 | `ListUsers` (AccessDenied) | 동일 | 동일 |

`GetCallerIdentity` → `ListBuckets` → `ListUsers` 는 훔친 키를 손에 넣은 사람의 교과서적인 첫 세 수다. 내가 누구인지 확인하고, 뭘 볼 수 있는지 보고, 권한을 확인한다.

**최초 접근에 악용된 것은 IAM 사용자 `ji.hyun.park` 의 장기 액세스 키 `AKIAIOSFODNN7PARK01`.**

## 2. 익명화 인프라, 그리고 첫 번째 함정

GuardDuty 의 `UnauthorizedAccess:IAMUser/TorIPCaller` 가 `185.220.101.34` 를 알려진 Tor 출구 노드로 지목한다. 이 IP 가 `ji.hyun.park` 의 첫 API 호출 지점이고, 이후 `185.220.101.52` 등 같은 대역이 추가로 등장한다.

그런데 **더 이른 알림이 있다.** 2024-03-08, `62.210.115.149`, `UnauthorizedAccess:IAMUser/MaliciousIPCaller`. 나흘이나 앞선다.

CloudTrail 에서 이 IP 의 호출을 확인했다.

```
userAgent   : aws-cli/2.11.0 … compliance-scanner
sessionName : AuditSession-2024Q1
```

정상 컴플라이언스 스캐너다. 공격자 툴링(`Boto3 … Linux/5.15.0-pwn`, `python-requests`)과 userAgent 가 뚜렷이 다르다. **알림 시각만 보고 최초 침투를 정했다면 나흘 틀렸다.**

## 3. 권한 상승 — 거절당한 목록이 더 많은 걸 말한다

`AssumeRole` 을 시간순으로 정렬하고 `errorCode` 유무로 성공/실패를 갈랐다.

| 시각 (UTC) | 대상 역할 | 세션명 | 결과 |
|---|---|---|---|
| 2024-03-13 04:06:36 | `role/admin` | `s` | AccessDenied |
| 2024-03-13 04:07:24 | `role/AdministratorRole` | `s` | AccessDenied |
| 2024-03-13 04:08:25 | `role/OrganizationAccountAccessRole` | `s` | AccessDenied |
| 2024-03-13 16:40:33 | `role/lambda-exec-role` | `s` | AccessDenied |
| **2024-03-13 16:41:41** | **`role/ci-deploy-role`** | **`deploy-temp`** | **성공** |

실패 목록이 공격자의 시야를 보여 준다. 관리자 계열 이름을 차례로 찔러 보다가 CI 배포 역할에서 뚫렸다. 세션명이 실패 구간에는 전부 `s` 였다가 성공한 순간 `deploy-temp` 로 바뀐 것도 눈에 띈다.

선행 단계로 역할 체이닝도 있었다 — 03-12 01:38:44 `dev-role`(세션 `dev-session-jhpark`), 01:50:18 `cross-prod-role`(세션 `prod-session-maint`). 다만 **실제 데이터 접근 권한을 준 결정적 상승은 `ci-deploy-role` 탈취**다.

## 4. 지속성

| 시각 (UTC) | 이벤트 | 내용 | 결과 |
|---|---|---|---|
| 2024-03-13 05:41:57 | `CreateAccessKey` | `ji.hyun.park` 본인 계정에 2차 키 발급 | 성공 |
| 2024-03-15 03:22:18 | `CreateUser` | 백도어 IAM 사용자 `svc-backup-restore` | 성공 |
| 2024-03-15 03:23:04 | `AttachUserPolicy` | `PowerUserAccess` 부여 | 성공 |
| 2024-03-15 03:24:51 | `CreateAccessKey` | 키 `AKIAIOSFODNN7BCK099` 발급 | 성공 |

두 겹이다. 백도어 계정 하나와, 원 계정에 몰래 추가한 2차 키 하나. **유출된 원래 키를 회수해도 2차 키가 살아 있다.** 03-16 06:40 이후에도 Tor 에서 접근이 관측되므로 현재도 재침투가 가능한 상태다.

## 5. 유출 규모 — 요청 수가 아니라 성공 수

S3 서버 액세스 로그에서 원격 IP 별 `REST.GET.OBJECT` 를 집계하되 **HTTP 상태 코드를 같이 셌다.**

| 원격 IP | 버킷 | GET 요청 | 성공(200) | 전송 바이트 |
|---|---|---|---|---|
| 45.155.205.233 | `nexabridge-customer-data` | 20 | 19 (404 1건) | 1,423,360,817 |
| 45.155.205.233 | `nexabridge-db-backups` | 10 | 10 | 1,010,148,152 |
| 45.155.205.233 | `nexabridge-logs` | 4 | **0** (403 4건) | 0 |

요청 수만 세면 34건이 다 유출된 것처럼 보이지만, `nexabridge-logs` 4건은 전부 403 이라 **한 바이트도 안 나갔다.** 실제 유출은 29건, 약 2.4 GB.

CloudTrail 에서 같은 시간대(03-13 17:02~17:08)에 `ci-deploy-role`/`deploy-temp` 세션이 `nexabridge-customer-data` 의 `pii/raw/` 와 `nexabridge-db-backups` 의 `pg/` 를 `ListObjectsV2` 후 연속 `GetObject` 하는 흐름이 확인돼, 두 로그가 서로를 검증한다.

## 6. 내부 피벗 — srcids 가 IP 를 인스턴스에 붙인다

Route 53 Resolver 로그의 `srcids` 필드는 질의를 발생시킨 **인스턴스 ID** 를 담는다. 내부 IP 와 인스턴스를 직접 연결할 수 있는 몇 안 되는 경로다.

| 항목 | 값 |
|---|---|
| 피벗 호스트 IP | `10.0.7.66` |
| 인스턴스 ID | `i-0pivot66compromise` |

VPC Flow Log 에서 `10.0.7.66` 은 `10.0.x.x` 대역의 다수 호스트를 향해 22, 3306, 5432, 6379, 8080, 9200 으로 접속을 시도했다. 내부 서비스 식별 스캔이고, GuardDuty 의 `Backdoor:EC2/C&CActivity` 알림 대상과 같은 호스트다.

## 7. 인프라가 하나로 모인다

| 구분 | 도메인 | 응답 IP | 관측 포트 |
|---|---|---|---|
| C2 | `cdn-update.duckdns.org` | 45.155.205.233 | 443/tcp |
| 마이닝 풀 | `pool.supportxmr-eu.example.com` | 45.155.205.233 | 4444/tcp |
| 보조 채널 | `data-sync.r2-cf.example.net` | 45.155.205.233 | — |

세 도메인이 전부 **`45.155.205.233`** 으로 해석된다. 그리고 이 IP 는 6절의 S3 유출 수신 IP 와 같다.

데이터 유출·C2·마이닝이 **하나의 인프라**에서 운영됐다는 것을, S3 액세스 로그 / Route 53 / VPC Flow Log 세 개의 서로 다른 로그로 교차 확인한 셈이다. 마이닝 풀 질의 일부는 Route 53 Resolver DNS Firewall 에서 BLOCK 됐다.

## 8. 오탐 7건

| 알림 (시각) | 오탐 판단 근거 |
|---|---|
| `Recon:EC2/PortProbeUnprotectedPort` (03-05) | 인터넷 배경 스캐너의 상시 노이즈, 후속 침해 없음 |
| `UnauthorizedAccess:EC2/SSHBruteForce` (03-07) | 보안 그룹에서 전량 차단, 인증 성공 0건 |
| `UnauthorizedAccess:IAMUser/MaliciousIPCaller` (03-08) | userAgent `compliance-scanner`, 세션명 `AuditSession-2024Q1` |
| `Trojan:EC2/DNSDataExfiltration` (03-09) | 질의 대상이 `api.datadoghq.com` — 모니터링 에이전트 health-check |
| `Behavior:EC2/NetworkPortUnusual` (03-10) | 정상 사용자가 회사 IP `203.0.113.30` 에서 기동 후 2시간 뒤 종료 |
| `Discovery:S3/AnomalousBehavior` (03-11) | 내부 서비스 계정이 내부 IP 에서 자기 분석 버킷 대량 조회 (볼륨 이상일 뿐) |
| `Impact:S3/MaliciousIPCaller.Custom` (03-13) | 출장 직원이 쓴 사내 VPN egress IP |

반대로 실제 침해에 직접 대응되는 것은 4건 — `TorIPCaller`, `Backdoor:EC2/C&CActivity.B!DNS`, `CryptoCurrency:EC2/BitcoinTool.B!DNS`, `Stealth:IAMUser/CloudTrailLoggingDisabled`.

**알림 11건 중 7건이 오탐이다.** GuardDuty 를 트리거로 쓰되 결론으로 쓰면 안 된다는 게 이 문제의 설계 의도로 보인다.

## 9. 로깅 무력화 — eventSource 로 갈라야 한다

로그 무력화 API 를 `eventName` 만으로 묶으면 S3 버킷 설정 변경까지 섞인다. `eventSource` 로 분리했다.

| 시각 (UTC) | eventSource | API | 주체 | 결과 |
|---|---|---|---|---|
| 03-15 03:11:00 | `cloudtrail.amazonaws.com` | `StopLogging` | `ji.hyun.park` | AccessDenied |
| 03-15 03:11:29 | `cloudtrail.amazonaws.com` | `StopLogging` | `prod-session-maint` | AccessDenied |
| 03-15 03:11:55 | `cloudtrail.amazonaws.com` | `DeleteTrail` | `ji.hyun.park` | AccessDenied |
| 03-15 03:12:30 | `cloudtrail.amazonaws.com` | `PutEventSelectors` | `ji.hyun.park` | AccessDenied |
| 03-15 03:12:59 | `s3.amazonaws.com` | `PutBucketLifecycle` | `deploy-temp` | AccessDenied |
| 03-15 03:14:07 | `s3.amazonaws.com` | `PutBucketLogging` | `prod-session-maint` | AccessDenied |

**CloudTrail API 는 4건** — `StopLogging` 2회, `DeleteTrail`, `PutEventSelectors`. 대상 트레일은 `nexabridge-prod-trail`, 전부 권한 부족으로 실패했다.

같은 시간대의 `PutBucketLifecycle`·`PutBucketLogging` 은 **로그 저장 버킷을 조작하려는 별개의 시도**라 CloudTrail API 답변에 넣지 않았다(이것도 전부 AccessDenied). 목적이 같다고 API 가 같은 건 아니다.

## 종합 및 IOC

유출된 장기 액세스 키가 Tor 를 통해 악용돼 역할 체이닝으로 프로덕션 권한이 확보됐고, `ci-deploy-role` 탈취 후 고객 데이터와 DB 백업이 반출됐다. 이어 VPC 내부 피벗 호스트를 이용한 내부 스캔과 크립토마이닝이 진행됐다. CloudTrail 무력화 시도는 실패했지만 백도어 IAM 계정이 남아 재침투가 가능한 상태다.

| 구분 | IOC |
|---|---|
| 침해 계정 / 키 | `ji.hyun.park` / `AKIAIOSFODNN7PARK01`, `svc-backup-restore` / `AKIAIOSFODNN7BCK099` |
| 공격자 IP | `185.220.101.34`, `185.220.101.52` (Tor), `45.155.205.233`, `94.102.49.190`, `45.155.205.240` |
| 탈취 세션 | `deploy-temp` (ci-deploy-role), `prod-session-maint` (cross-prod-role) |
| 피벗 호스트 | `10.0.7.66` / `i-0pivot66compromise` |
| 악성 도메인 | `cdn-update.duckdns.org`, `pool.supportxmr-eu.example.com` |
| 유출 버킷 | `nexabridge-customer-data`, `nexabridge-db-backups` |

## 정리 — 이 문제에서 남는 것

**탐지 알림은 시작점이지 결론이 아니다.** 11건 중 7건이 오탐이었고, 가장 이른 "악성 IP" 알림은 컴플라이언스 스캐너였다. userAgent 와 세션명 두 필드가 진짜와 가짜를 갈랐다.

**응답 코드를 세지 않으면 유출 규모가 부풀려진다.** 403·404 를 빼야 실제 반출 건수가 나온다.

**클라우드 로그는 서로를 검증하도록 설계돼 있다.** S3 액세스 로그(무엇이 나갔나) ↔ CloudTrail(누가 불렀나) ↔ Route 53 Resolver(어디로 물었나) ↔ VPC Flow(어디로 붙었나). 하나로 답을 만들고 다른 하나로 확인하는 게 기본기다.

**같은 목적이어도 API 는 구분해서 센다.** `eventSource` 를 무시하면 CloudTrail 무력화 4건이 6건이 된다.

---

*DFC 2026 출제 문제 153번에 대한 분석 기록. 2인 팀 참가 제출본을 블로그용으로 정리했다.*
