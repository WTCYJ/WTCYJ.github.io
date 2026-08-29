---
layout: post
title: "[보안기초] 침입 탐지 및 방지 시스템(IDS/IPS) 완전 정복"
date: 2026-05-12 09:00:00 +0900
category: 시스템
author: yejunkim2000
tags: [IDS, IPS, Firewall, Snort, Suricata, Zeek, Wazuh, NIDS, HIDS, NIPS, HIPS]


---

## 목차

1. [IDS와 IPS의 정의 및 개요](#1-ids와-ips의-정의-및-개요)
2. [IDS vs IPS 주요 차이점 비교](#2-ids-vs-ips-주요-차이점-비교)
3. [IDS/IPS의 유형 분류](#3-idsips의-유형-분류)
4. [탐지 방법론](#4-탐지-방법론)
5. [IDS/IPS의 동작 원리 및 처리 흐름](#5-idsips의-동작-원리-및-처리-흐름)
6. [네트워크 배치 구조 및 아키텍처](#6-네트워크-배치-구조-및-아키텍처)
7. [장점과 단점](#7-장점과-단점)
8. [실제 공격 탐지 시나리오](#8-실제-공격-탐지-시나리오)
9. [IDS/IPS 우회 기법](#9-idsips-우회-기법)
10. [주요 오픈소스 도구 소개](#10-주요-오픈소스-도구-소개)
11. [Snort 룰 문법 및 예시](#11-snort-룰-문법-및-예시)
12. [실무 활용 및 운영 전략](#12-실무-활용-및-운영-전략)
13. [최신 보안 트렌드와 발전 방향](#13-최신-보안-트렌드와-발전-방향)
14. [결론 및 핵심 요약](#14-결론-및-핵심-요약)

---

## 1. IDS와 IPS의 정의 및 개요

네트워크 보안 솔루션인 IDS와 IPS는 **맬웨어, 무단 액세스, DoS 공격 등으로부터 네트워크를 보호하는 중요한 역할**을 수행한다.

### IDS (Intrusion Detection System, 침입 탐지 시스템)

- **정의:** 네트워크나 시스템에서 발생하는 비정상적이거나 악의적인 활동을 탐지하고 관리자에게 경고(Alert)를 보내는 시스템

**특징:**

1. 공격을 직접 차단하지 않음
2. 로그 기록 및 경고 생성 중심
3. 수동적(Passive) 보안 시스템
4. 실시간 모니터링 수행

**주요 역할:**

1. 비정상 로그인 탐지
2. 포트 스캔 탐지
3. DDoS 징후 탐지
4. 악성코드 통신 식별
5. 내부자 위협 탐지

> **비유:** 건물 내부를 감시하며 이상 상황 발생 시 경보를 울리는 **CCTV**와 유사하다.

---

### IPS (Intrusion Prevention System, 침입 방지 시스템)

- **정의:** IDS의 탐지 기능에 더해, 탐지된 위협을 실시간으로 차단하거나 연결을 종료하는 보안 시스템

**특징:**

1. 공격 패킷 차단
2. 세션 종료(TCP Reset)
3. IP 차단
4. 방화벽 정책 자동 수정 가능
5. 능동적(Active) 보안 시스템

**주요 역할:**

1. 악성 패킷 삭제(Drop)
2. 봇넷 통신 차단
3. 익스플로잇(Exploit) 방어
4. 웹 공격(SQL Injection, XSS 등) 차단
5. 악성 행위 세션 종료

> **비유:** 출입구에서 신원을 검사하고 위험 인물의 출입을 직접 막는 **경비원**과 유사하다.

---

## 2. IDS vs IPS 주요 차이점 비교

두 시스템은 목적은 비슷하지만 작동 방식과 네트워크상 위치에서 큰 차이를 보인다.

| 구분 | IDS (침입 탐지 시스템) | IPS (침입 방지 시스템) |
|---|---|---|
| **주요 목적** | 탐지 및 경보 발생 | 탐지 + 실시간 차단 |
| **동작 방식** | 수동적(Passive) | 능동적(Active) |
| **네트워크 배치** | 미러링(Out-of-band) | 인라인(In-line) |
| **자동 차단** | 없음 (수동 대응 필요) | 가능 (자동 차단) |
| **네트워크 영향** | 거의 없음 | 지연(레이턴시) 발생 가능 |
| **오탐 시 영향** | 불필요한 경보만 발생 | 정상 트래픽 차단 위험 |
| **Zero-Day 대응** | 탐지만 가능 | 설정에 따라 차단 가능 |
| **단일 장애점(SPOF)** | 해당 없음 | 인라인 특성상 위험 |
| **포렌식 적합성** | 높음 | 낮음 (트래픽 폐기) |
| **적합 환경** | 규정 준수, 로그 분석, 포렌식 | 실시간 보안 운영, 자동 방어 |
| **대표 솔루션** | Snort(탐지 모드), Zeek | Snort(방지 모드), Suricata |

> **False Positive vs False Negative**
>
> - **False Positive(오탐):** 정상 트래픽을 공격으로 판단해 경보를 발생시키는 것
> - **False Negative(미탐):** 실제 공격을 정상으로 판단해 놓치는 것
>
> IPS에서는 특히 오탐이 서비스 장애로 이어질 수 있으므로 튜닝이 매우 중요하다.

---

## 3. IDS/IPS의 유형 분류

### 3-1. 배치 위치에 따른 분류

#### NIDS / NIPS (Network-based IDS/IPS, 네트워크 기반)

- 네트워크 세그먼트 전체의 트래픽을 모니터링
- 스위치의 SPAN(포트 미러링) 포트 또는 TAP 장비를 통해 패킷 수집
- **장점:** 다수의 호스트를 동시에 보호, 설치 부담 적음
- **단점:** 암호화된 트래픽(TLS/SSL) 내부 분석 어려움, 스위치 환경에서 모든 트래픽 수집 한계
- **대표 도구:** Snort, Suricata, Zeek

#### HIDS / HIPS (Host-based IDS/IPS, 호스트 기반)

- 개별 호스트(서버, PC)에 에이전트(Agent)를 설치하여 동작
- 시스템 콜, 파일 무결성, 레지스트리, 프로세스, 로그 등을 모니터링
- **장점:** 암호화 트래픽도 복호화 후 분석 가능, 내부 위협 및 로컬 공격 탐지에 효과적
- **단점:** 에이전트 설치 및 관리 부담, 에이전트 자체가 공격 대상이 될 수 있음
- **대표 도구:** OSSEC, Wazuh, Tripwire, AIDE

#### WIDS / WIPS (Wireless-based IDS/IPS, 무선 네트워크 기반)

- 무선 LAN(Wi-Fi) 환경에 특화된 IDS/IPS
- 불법 액세스 포인트(Rogue AP), Evil Twin 공격, 무선 프로토콜 공격 탐지 및 차단
- **대표 도구:** AirMagnet, Cisco Adaptive Wireless IPS

#### NBA (Network Behavior Analysis, 네트워크 행동 분석)

- 트래픽 패턴 및 흐름(Flow) 데이터를 분석하여 이상 행동 탐지
- NetFlow, sFlow 등의 트래픽 요약 데이터 활용
- DDoS, 내부 스캔, 이상 트래픽 패턴 탐지에 효과적

---

### 3-2. 역할에 따른 분류

| 유형 | 설명 |
|---|---|
| **IDS 전용** | 탐지 및 경보만 수행. 포렌식 및 감사 목적에 적합 |
| **IPS 전용** | 탐지와 차단을 동시에 수행. 실시간 방어에 적합 |
| **IDPS** | IDS + IPS를 통합한 하이브리드 시스템 |
| **NGIPS** | 차세대 IPS. 애플리케이션 인식, SSL 복호화, 위협 인텔리전스 연동 등 포함 |

---

## 4. 탐지 방법론

IDS/IPS가 위협을 탐지하는 방식은 크게 4가지로 구분된다. 각 방법은 고유한 강점과 한계를 가지며, 실무에서는 이를 혼합하여 사용한다.

### 4-1. 시그니처 기반 탐지 (Signature-Based Detection)

알려진 공격 패턴(시그니처)의 데이터베이스와 트래픽을 비교하는 방식입니다.

**동작 원리:**

- 공격 패턴(문자열, 바이트 시퀀스, 정규식 등)을 룰(Rule) 형태로 정의
- 수신 패킷의 페이로드(Payload)와 룰을 매칭
- 일치 시 경보 발생 또는 차단

**장점:**

- 알려진 공격에 대해 오탐률(False Positive)이 매우 낮음
- 탐지 속도가 빠름
- 룰 기반이라 동작 예측이 쉬움

**단점:**

- 시그니처 DB에 없는 신규 공격(Zero-Day) 탐지 불가
- 시그니처 DB를 지속적으로 업데이트해야 함
- 변형된 공격(Polymorphic Attack)에 취약

**대표 도구:** Snort, Suricata

---

### 4-2. 이상 탐지 기반 (Anomaly-Based Detection)

정상 트래픽의 베이스라인(Baseline)을 학습한 후, 기준에서 벗어나는 행동을 탐지한다.

**동작 원리:**

- 학습 기간 동안 정상 트래픽 패턴(접속 시간, 데이터 양, 프로토콜 비율 등)을 모델링
- 실시간 트래픽과 베이스라인을 비교하여 임계값 초과 시 경보 발생

**장점:**

- Zero-Day 공격 및 알려지지 않은 위협 탐지 가능
- 내부자 위협(Insider Threat) 식별에 효과적
- 패턴 변형 공격에도 대응 가능

**단점:**

- 베이스라인 설정이 어렵고 시간이 필요함
- 오탐(False Positive) 비율이 시그니처 방식보다 높음
- 공격자가 학습 기간 중 트래픽에 영향을 미치면 베이스라인 오염 가능

---

### 4-3. 통계 기반 탐지 (Statistical-Based Detection)

트래픽의 통계적 특성(평균, 분산, 분포)을 분석하여 임계값을 초과하는 이상 현상을 탐지한다.

**동작 원리:**

- 시간대별 트래픽량, 연결 수, 패킷 크기 등의 통계 수집
- 평균에서 크게 벗어나는 수치 탐지(표준 편차, 포아송 분포 등 활용)

**활용 사례:**

- DDoS 공격 탐지: 단시간 내 트래픽량 급증
- 포트 스캔 탐지: 다수 포트에 대한 짧은 시간 내 연결 시도
- 브루트포스(Brute-Force) 탐지: 비정상적인 로그인 실패 횟수

---

### 4-4. 휴리스틱 / 행동 기반 탐지 (Heuristic / Behavior-Based Detection)

알려진 공격 기법의 일반적인 행동 패턴을 기반으로 변형 공격도 탐지한다.

**동작 원리:**

- 단일 패킷이 아닌 일련의 행동(Action Sequence)을 분석
- 악성코드의 전형적인 행동 패턴(파일 시스템 접근, 레지스트리 수정, 네트워크 통신 등)을 모델링
- 의심스러운 행동 조합을 탐지

**활용 사례:**

- 다형성 악성코드(Polymorphic Malware) 탐지
- APT(Advanced Persistent Threat) 공격의 측면 이동(Lateral Movement) 탐지
- 파일리스(Fileless) 악성코드 탐지

---

### 4-5. 탐지 방법론 비교

| 방법 | Zero-Day 탐지 | 오탐률 | 속도 | 운영 난이도 |
|---|---|---|---|---|
| 시그니처 기반 | 어려움 | 낮음 | 빠름 | 낮음 |
| 이상 탐지 기반 | 가능 | 높음 | 보통 | 높음 |
| 통계 기반 | 부분적 | 보통 | 빠름 | 보통 |
| 휴리스틱/행동 기반 | 가능 | 보통 | 보통 | 높음 |

---

## 5. IDS/IPS의 동작 원리 및 처리 흐름

### 5-1. IDS 처리 흐름

```text
트래픽 수신(미러링)
        ↓
패킷 캡처 (libpcap 등)
        ↓
패킷 파싱 및 재조합 (IP 단편화, TCP 스트림 재조합)
        ↓
프로토콜 디코딩 (HTTP, DNS, FTP 등)
        ↓
탐지 엔진 (시그니처 매칭 / 이상 탐지)
        ↓
이벤트 생성 (Alert, Log)
        ↓
경보 발송 (SIEM, 관리자 이메일/SMS)
        ↓
[원본 트래픽은 그대로 목적지에 전달됨]
```

### 5-2. IPS 처리 흐름

```text
트래픽 수신(인라인)
        ↓
패킷 캡처 및 버퍼링
        ↓
패킷 파싱 및 재조합
        ↓
프로토콜 디코딩
        ↓
탐지 엔진 (시그니처 매칭 / 이상 탐지)
        ↓
     [탐지됨?]
    ↙         ↘
 정상          악성
  ↓              ↓
전달            차단 (Drop / Reset / Shun)
              + 로그 기록
              + 경보 발송
```

### 5-3. 패킷 처리 핵심 기술

#### TCP 스트림 재조합 (Stream Reassembly)

TCP는 데이터를 여러 세그먼트로 분할하여 전송한다. 공격자는 이를 악용해 시그니처를 여러 패킷으로 분산시키는 방식으로 탐지를 우회하려고 한다.  
따라서 IDS/IPS는 TCP 스트림을 재조합해 완전한 페이로드를 분석해야 한다.

#### IP 단편화 재조합 (IP Defragmentation)

IP 패킷이 MTU 제한으로 분할(Fragment)된 경우, 이를 재조합해야 완전한 페이로드 분석이 가능하다.

#### 프로토콜 정규화 (Protocol Normalization)

동일한 의미를 가진 다양한 인코딩 방식(URL 인코딩, Unicode 우회 등)을 정규화해 시그니처와 비교한다.

---

## 6. 네트워크 배치 구조 및 아키텍처

### 6-1. IDS 배치: 미러링(Passive / Out-of-band)

```text
[인터넷] → [방화벽] → [스위치] → [내부 네트워크]
                          ↓ (SPAN 포트 / 네트워크 TAP)
                        [IDS]
                          ↓
                     (경보 발생만, 트래픽 차단 없음)
```

- 네트워크 스위치의 **포트 미러링(SPAN 포트)** 또는 **네트워크 TAP**을 통해 트래픽 사본 수신
- 실제 트래픽 경로에 위치하지 않으므로 **네트워크 성능에 영향 없음**
- 단점: 공격을 탐지해도 이미 패킷이 목적지에 전달된 후일 수 있음

### 6-2. IPS 배치: 인라인(Inline)

```text
[인터넷] → [방화벽] → [IPS] → [내부 네트워크]
                   (모든 트래픽이 IPS를 통과)
                   (악성 패킷 즉시 차단)
```

- 네트워크 경로에 **직접 삽입(인라인)**되어 모든 트래픽이 IPS를 통과
- 악성 패킷을 **실시간으로 폐기(Drop)** 가능
- **Fail-Open:** IPS 장애 시 트래픽 통과 허용 (가용성 우선)
- **Fail-Close:** IPS 장애 시 트래픽 전체 차단 (보안성 우선)

### 6-3. 일반적인 심층 방어(Defense in Depth) 구성

```text
[인터넷]
    ↓
[경계 라우터 / ACL]         ← 1차 필터링 (IP/포트 기반)
    ↓
[방화벽 (Firewall)]         ← 2차 필터링 (상태 기반 패킷 검사)
    ↓
[IPS (인라인)]              ← 3차 (실시간 위협 차단)
    ↓
[DMZ 구간]
    ↓
[내부 방화벽]
    ↓
[IDS (미러링)]              ← 내부 트래픽 모니터링
    ↓
[내부 네트워크 / 서버]
    ↓
[HIDS (호스트 에이전트)]     ← 개별 호스트 보호
```

---

## 7. 장점과 단점

### 7-1. IDS 장단점

**장점:**

- 네트워크 성능에 영향 없음 (패시브 모드)
- 오탐으로 인한 서비스 장애 위험 없음
- 포렌식 및 감사(Audit) 목적에 적합
- 광범위한 트래픽 가시성(Visibility) 확보
- 다양한 알림 연동(SIEM, 이메일, SMS) 용이

**단점:**

- 탐지 후 수동 대응 필요로 반응 속도가 느릴 수 있음
- 빠른 공격(수초 내 완료)에 대응 불가
- 대규모 알림 발생 시 관리 부담(Alert Fatigue)
- 전문 보안 인력 상시 필요

---

### 7-2. IPS 장단점

**장점:**

- 공격 실시간 자동 차단
- 보안 인력 개입 없이 24/7 방어 가능
- 공격 성공 전 피해 최소화
- DDoS, 웜(Worm) 확산 즉시 차단
- 자동화된 보안 정책 집행

**단점:**

- 오탐(False Positive) 시 정상 서비스 차단 위험
- 인라인 배치로 네트워크 레이턴시 증가
- 단일 장애점(Single Point of Failure) 가능성
- 초기 구축 및 운영 비용이 높음
- 지속적인 룰(Rule) 업데이트 및 튜닝 필요
- 암호화 트래픽(TLS 1.3 등) 분석에 한계

---

## 8. 실제 공격 탐지 시나리오

### 시나리오 1: SQL Injection 공격

**공격 과정:**

1. 공격자가 웹 폼에 `' OR '1'='1` 형태의 SQL 페이로드 입력
2. HTTP GET/POST 요청으로 웹 서버에 전송
3. IDS/IPS가 HTTP 페이로드에서 SQL Injection 패턴 탐지

**IDS 동작:**

- SQL Injection 시그니처와 매칭되어 경보(Alert) 발생
- SIEM으로 이벤트 전송 및 로그 기록
- 패킷은 이미 웹 서버에 전달된 상태

**IPS 동작:**

- SQL Injection 시그니처와 매칭되어 패킷 즉시 Drop
- 공격자 IP를 임시 차단 목록에 추가
- SIEM으로 이벤트 전송 및 로그 기록
- 웹 서버에는 패킷이 도달하지 않음

---

### 시나리오 2: 포트 스캔(Port Scan) 탐지

**공격 과정:**

공격자가 대상 서버의 열린 포트를 파악하기 위해 `nmap -sS 192.168.1.1` 을 실행하는 상황을 가정한다.

**탐지 원리:**

- 짧은 시간(예: 5초) 내에 동일 소스 IP에서 20개 이상의 포트에 SYN 패킷 전송
- 통계 기반 탐지 엔진이 비정상적인 연결 패턴 감지

**IDS/IPS 대응:**

- IDS: 포트 스캔 경보 발생, 소스 IP 및 스캔 포트 목록 기록
- IPS: 소스 IP 차단(Shun), TCP RST 패킷 전송으로 연결 강제 종료

---

### 시나리오 3: DDoS 공격 탐지

**공격 과정:**

다수의 봇넷(Botnet) 노드가 대상 서버에 대규모 UDP Flood 또는 HTTP Flood 트래픽 전송

**탐지 원리:**

- 초당 패킷/연결 수(PPS/CPS)가 정상 범위의 임계값을 초과
- 통계 기반 및 행동 기반 탐지 엔진이 트래픽 급증 감지

**IPS 대응:**

- 공격 트래픽 패턴과 일치하는 패킷에 대해 Rate Limiting 적용
- 블랙홀 라우팅(Blackhole Routing) 또는 스크러빙 센터로 트래픽 전환
- BGP Blackholing을 통한 공격 트래픽 원천 차단

---

### 시나리오 4: 랜섬웨어 C2(Command & Control) 통신 차단

**공격 과정:**

내부 감염 PC가 외부 C2 서버와 통신하여 랜섬웨어 명령 수신 및 암호화 키 교환 시도

**탐지 원리:**

- 알려진 C2 서버 IP/도메인 블랙리스트와 대조
- 비정상적인 DNS 쿼리 패턴(DGA - Domain Generation Algorithm) 탐지
- 비표준 포트를 통한 외부 통신 이상 감지

**IPS 대응:**

- C2 서버와의 연결 즉시 차단
- 감염 PC IP를 격리(Quarantine) 대상으로 표시
- SIEM을 통해 보안팀에 긴급 알림 발송

---

## 9. IDS/IPS 우회 기법

공격자들은 IDS/IPS를 우회하기 위한 다양한 기법을 사용한다. 이를 이해하는 것이 더 강력한 방어 체계 구축에 도움이 된다.

### 9-1. 단편화(Fragmentation) 공격

IP 패킷을 최소 크기로 단편화하여 IDS가 재조합하기 전에 시그니처 매칭을 회피한다.

```text
[공격 페이로드 전체: "SELECT * FROM users WHERE..."]
         ↓ 단편화
패킷 1: "SEL"
패킷 2: "ECT "
패킷 3: "* FROM..."
```

**대응:** TCP/IP 재조합 기능을 가진 IDS/IPS 사용, 단편화 비율 이상 탐지

---

### 9-2. 인코딩 및 난독화(Encoding / Obfuscation)

URL 인코딩, Unicode 인코딩, Base64 등을 이용해 악성 페이로드를 난독화한다.

```text
원본: /etc/passwd
URL 인코딩: %2fetc%2fpasswd
더블 인코딩: %252fetc%252fpasswd
Unicode: /etc%c0%afpasswd
```

**대응:** 프로토콜 정규화(Normalization) 엔진, 다중 디코딩 처리

---

### 9-3. 저속 공격(Slow Attack / Low-and-Slow)

탐지 임계값 이하로 아주 천천히 공격하여 통계 기반 탐지를 우회한다.

- **Slowloris:** HTTP 헤더를 아주 천천히 전송하여 서버 연결 소진
- **Slow Read:** TCP 수신 버퍼를 거의 읽지 않아 서버 자원 고갈

**대응:** 세션 타임아웃 설정, 비정상적으로 긴 세션 탐지

---

### 9-4. 암호화 트래픽 활용

TLS/SSL 암호화를 통해 악성 페이로드를 숨긴다. IDS/IPS는 암호화된 내용을 직접 볼 수 없다.

**대응:** TLS Inspection(SSL Interception) 구성으로 중간에서 복호화 후 검사하고 재암호화한다. 단, 개인정보 및 법적 이슈를 반드시 검토해야 한다.

---

### 9-5. 다형성 악성코드(Polymorphic Malware)

악성코드가 실행될 때마다 코드를 변형해 시그니처가 변경된다.

**대응:** 행동 기반 탐지(Behavior-Based), 머신러닝 기반 탐지, 샌드박스(Sandbox) 분석

---

### 9-6. 시그니처 삽입(Signature Insertion) / 이중성(Ambiguity)

잘못된 TTL 값의 패킷으로 IDS를 혼란시키거나, 대상 OS와 IDS가 다르게 해석하는 패킷 시퀀스를 이용한다.

---

## 10. 주요 오픈소스 도구 소개

### 10-1. Snort

- **개발:** Martin Roesch (1998), 현재 Cisco 지원
- **특징:** 가장 널리 쓰이는 오픈소스 NIDS/NIPS, 룰 기반 시그니처 탐지
- **모드:** Sniffer, Packet Logger, Network IDS/IPS
- **사용 환경:** Linux, Windows
- **공식 사이트:** [Snort](https://www.snort.org)

```bash
# IDS 모드 (탐지만)
snort -c /etc/snort/snort.conf -i eth0 -A alert_fast

# IPS 모드 (인라인 차단)
snort -c /etc/snort/snort.conf -i eth0 -Q --daq afpacket
```

---

### 10-2. Suricata

- **개발:** OISF (Open Information Security Foundation)
- **특징:** 멀티스레드 지원으로 고성능 환경에 적합, Snort 룰과 호환
- **추가 기능:** HTTP, TLS, DNS 등 프로토콜 분석, EVE JSON 로그 출력
- **공식 사이트:** [Suricata](https://suricata.io)

```bash
# IDS 모드
suricata -c /etc/suricata/suricata.yaml -i eth0

# IPS 모드 (NFQUEUE)
suricata -c /etc/suricata/suricata.yaml -q 0
```

---

### 10-3. Zeek (구 Bro)

- **특징:** 단순 탐지보다 **네트워크 행동 분석 및 포렌식**에 특화
- **출력:** 구조화된 로그(conn.log, http.log, dns.log 등)
- **활용:** SIEM 연동, 위협 헌팅(Threat Hunting), 이상 탐지 스크립트 작성
- **공식 사이트:** [Zeek](https://zeek.org)

---

### 10-4. OSSEC / Wazuh

- **특징:** 호스트 기반 IDS(HIDS) 대표 솔루션
- **기능:** 파일 무결성 모니터링(FIM), 로그 분석, 루트킷 탐지, 활성 대응
- **Wazuh:** OSSEC의 포크(Fork), Elasticsearch/Kibana 연동 지원
- **공식 사이트:** [Wazuh](https://wazuh.com)

---

### 10-5. 도구 비교

| 도구 | 유형 | 특징 | 적합 환경 |
|---|---|---|---|
| Snort | NIDS/NIPS | 룰 기반, 사용자층 넓음 | 중소 규모 네트워크 |
| Suricata | NIDS/NIPS | 멀티스레드, 고성능 | 대용량 트래픽 환경 |
| Zeek | NIDS (분석) | 행동 분석, 포렌식 | 위협 헌팅, SOC |
| OSSEC/Wazuh | HIDS | 호스트 중심, FIM | 서버 및 엔드포인트 보호 |

---

## 11. Snort 룰 문법 및 예시

### 11-1. 룰 기본 구조

```snort
[액션] [프로토콜] [출발지IP] [출발지포트] [방향] [목적지IP] [목적지포트] (옵션;)
```

| 구성 요소 | 설명 |
|---|---|
| **액션** | alert, log, pass, drop, reject, sdrop |
| **프로토콜** | tcp, udp, icmp, ip |
| **IP** | 단일 IP, CIDR, 변수($HOME_NET), any |
| **포트** | 숫자, 범위(1:1024), 변수($HTTP_PORTS), any |
| **방향** | `->` (단방향), `<>` (양방향) |
| **옵션** | msg, content, sid, rev, flow 등 |

### 11-2. 주요 액션

| 액션 | 설명 |
|---|---|
| `alert` | 경보 발생 + 로그 기록 (IDS 모드) |
| `log` | 로그 기록만 수행 |
| `pass` | 패킷 허용 (탐지 없이 통과) |
| `drop` | 패킷 폐기 + 경보 (IPS 모드) |
| `reject` | 패킷 폐기 + TCP RST 전송 + 경보 |
| `sdrop` | 패킷 조용히 폐기 (경보 없음) |

### 11-3. 룰 예시

**예시 1: SQL Injection 탐지**

```snort
alert tcp $EXTERNAL_NET any -> $HTTP_SERVERS $HTTP_PORTS (
    msg:"SQL Injection Attempt - OR 1=1";
    flow:to_server,established;
    content:"' OR '1'='1"; nocase;
    http_uri;
    classtype:web-application-attack;
    sid:1000001;
    rev:1;
)
```

**예시 2: 포트 스캔 차단 (IPS 모드)**

```snort
drop tcp $EXTERNAL_NET any -> $HOME_NET any (
    msg:"Port Scan Detected - SYN Flood";
    flags:S;
    detection_filter:track by_src, count 20, seconds 5;
    classtype:attempted-recon;
    sid:1000002;
    rev:1;
)
```

**예시 3: ICMP Ping Flood 탐지**

```snort
alert icmp $EXTERNAL_NET any -> $HOME_NET any (
    msg:"ICMP Ping Flood Detected";
    itype:8;
    detection_filter:track by_src, count 100, seconds 1;
    classtype:attempted-dos;
    sid:1000003;
    rev:1;
)
```

**예시 4: 악성 User-Agent 탐지**

```snort
alert http $EXTERNAL_NET any -> $HTTP_SERVERS $HTTP_PORTS (
    msg:"Malicious User-Agent - sqlmap";
    flow:to_server,established;
    http_header;
    content:"User-Agent|3a| sqlmap"; nocase;
    classtype:web-application-attack;
    sid:1000004;
    rev:1;
)
```

**예시 5: DNS 터널링 탐지**

```snort
alert udp $HOME_NET any -> any 53 (
    msg:"Possible DNS Tunneling - Long Query";
    content:"|00 01 00 00|";
    byte_test:1,>,50,0,relative;
    classtype:policy-violation;
    sid:1000005;
    rev:1;
)
```

### 11-4. 주요 룰 옵션 설명

| 옵션 | 설명 |
|---|---|
| `msg` | 경보 메시지 |
| `content` | 페이로드에서 검색할 문자열 |
| `nocase` | 대소문자 구분 없이 매칭 |
| `flow` | 트래픽 방향 (to_server, from_server, established 등) |
| `flags` | TCP 플래그 (S=SYN, A=ACK, F=FIN, R=RST 등) |
| `detection_filter` | 특정 횟수 이상 발생 시에만 경보 |
| `itype` | ICMP 타입 |
| `http_uri` | HTTP URI 부분에서만 content 검색 |
| `http_header` | HTTP 헤더 부분에서만 content 검색 |
| `classtype` | 공격 분류 유형 |
| `sid` | 시그니처 ID (사용자 정의 룰은 1,000,000 이상 권장) |
| `rev` | 룰 버전 |
| `priority` | 우선순위 (1=높음, 3=낮음) |

---

## 12. 실무 활용 및 운영 전략

### 12-1. 산업별 활용 사례

**금융 / 핀테크**

- 금융 거래 이상 탐지
- PCI-DSS 규정 준수 대응
- API 기반 금융 서비스 공격 방어

**의료 / 헬스케어**

- 환자 데이터 보호
- 의료 IoT 장비 네트워크 이상 탐지
- 랜섬웨어에 의한 의료 시스템 마비 예방

**산업 제어 시스템 (OT/ICS)**

- SCADA/DCS 시스템 사이버 공격 탐지
- 산업용 프로토콜(Modbus, DNP3) 이상 탐지
- 사이버-물리 공격 방어

**클라우드 환경**

- 컨테이너 및 마이크로서비스 네트워크 트래픽 모니터링
- 클라우드 네이티브 위협 탐지
- AWS GuardDuty, Azure Defender 등 관리형 IDS 활용

---

### 12-2. SIEM과의 연동

IDS/IPS 단독으로는 수많은 알림을 효과적으로 처리하기 어렵다. **SIEM(Security Information and Event Management)** 과 연동하면 다음을 구현할 수 있다.

- **로그 중앙화:** 다수 IDS/IPS 장비의 이벤트를 한 곳에 수집
- **상관 분석(Correlation):** 여러 이벤트를 조합하여 복합 공격 탐지
- **알림 우선순위화:** 위협 수준에 따라 경보를 분류해 Alert Fatigue 감소
- **자동 대응(SOAR):** 플레이북을 통한 자동화된 인시던트 대응

---

### 12-3. IDS/IPS 운영 모범 사례

1. **단계적 도입:** 처음에는 IDS(탐지 전용)로 시작한 뒤 환경 이해 후 IPS로 전환
2. **룰 튜닝:** 오탐이 많은 룰은 비활성화하거나 임계값 조정
3. **화이트리스트 관리:** 정상 업무 트래픽 예외 규칙 사전 정의
4. **정기적 시그니처 업데이트:** 새로운 공격 패턴 대응을 위해 자동 업데이트 구성
5. **로그 보존:** 규정 준수 및 포렌식을 위해 최소 90일에서 1년 이상 보존
6. **침투 테스트 연계:** 정기적 모의 해킹으로 IDS/IPS 탐지 성능 검증
7. **이중화 구성:** IPS는 인라인 배치 특성상 HA(High Availability) 구성 권장

---

## 13. 최신 보안 트렌드와 발전 방향

### 13-1. NGIPS (Next-Generation IPS)

기존 IPS에 다음 기능이 추가된 차세대 솔루션이다.

- **애플리케이션 인식(Application Awareness):** 포트 기반이 아닌 실제 애플리케이션 식별
- **사용자 인식(User Identity Awareness):** IP 주소가 아닌 사용자 계정과 연계
- **SSL/TLS Inspection:** 암호화 트래픽 복호화 후 검사
- **위협 인텔리전스 연동:** 알려진 악성 IP/도메인 즉시 차단
- **대표 솔루션:** Cisco Firepower, Palo Alto NGFW, Fortinet FortiGate

---

### 13-2. AI/ML 기반 탐지

머신러닝과 딥러닝을 활용해 기존 시그니처 방식의 한계를 보완한다.

- **비지도 학습(Unsupervised Learning):** 정상 트래픽 패턴을 자동으로 모델링해 이상 탐지
- **지도 학습(Supervised Learning):** 레이블이 붙은 공격/정상 트래픽 데이터로 분류 모델 훈련
- **강화 학습(Reinforcement Learning):** 탐지 결과 피드백을 반영해 지속적으로 모델 개선
- **한계:** 적대적 공격(Adversarial Attack)에 취약하고 설명 가능성이 부족할 수 있음

---

### 13-3. XDR (Extended Detection and Response)

IDS/IPS의 개념을 엔드포인트, 클라우드, 이메일 등 전체 IT 환경으로 확장한 접근입니다.

- **통합 가시성:** 네트워크 + 엔드포인트 + 클라우드 이벤트를 단일 플랫폼에서 분석
- **자동 상관 분석:** 여러 소스의 이벤트를 자동으로 연결해 공격 체인 파악
- **자동 대응:** 탐지 즉시 격리, 차단, 포렌식 수집 자동 수행

---

### 13-4. Zero Trust 아키텍처와 IDS/IPS

전통적인 경계 보안을 넘어 "신뢰하지 말고 항상 검증하라(Never Trust, Always Verify)"는 원칙 아래 다음과 같은 방향으로 운영된다.

- 내부 네트워크 트래픽도 IDS/IPS로 전수 검사
- 동서 방향(East-West) 트래픽 모니터링 강화
- 마이크로 세그멘테이션(Micro-Segmentation)과 연계

---

## 14. 결론 및 핵심 요약

### 핵심 정리

| 항목 | 내용 |
|---|---|
| **IDS** | 탐지 및 경보 전문, 수동적, 네트워크 영향 없음, 포렌식 적합 |
| **IPS** | 탐지 + 차단, 능동적, 인라인 배치, 실시간 방어 |
| **NIDS/NIPS** | 네트워크 전체 보호, 암호화 트래픽 분석 어려움 |
| **HIDS/HIPS** | 호스트 단위 보호, 암호화 내부 분석 가능 |
| **시그니처 기반** | 알려진 공격에 강함, Zero-Day에 약함 |
| **이상 탐지 기반** | Zero-Day 탐지 가능, 오탐률 높음 |
| **Snort/Suricata** | 대표 오픈소스 NIDS/NIPS |
| **Wazuh** | 대표 오픈소스 HIDS |

### 선택 기준

- **규정 준수 / 로그 분석 / 포렌식 목적** → **IDS** 우선 도입
- **실시간 공격 차단 / 자동 방어** → **IPS** 도입
- **대규모 트래픽 환경** → **Suricata**
- **네트워크 행동 분석 / 위협 헌팅** → **Zeek**
- **호스트 보안 / 파일 무결성** → **Wazuh**



---

### 마무리

IDS와 IPS는 서로 대체 관계가 아니라 **상호 보완 관계**이다.  
방화벽, WAF, EDR, SIEM과 함께 **심층 방어(Defense in Depth)** 전략의 핵심 요소로 활용할 때 가장 효과적이다.  
또한 AI/ML 기반 탐지와 XDR로 발전하는 최신 흐름을 이해하고, 조직의 보안 성숙도에 맞게 단계적으로 도입하는 것이 중요하다.



---

## 참고 자료

- [Snort 공식 문서](https://www.snort.org/documents)
- [Suricata 공식 문서](https://docs.suricata.io)
- [Zeek 공식 문서](https://docs.zeek.org)
- [Wazuh 공식 문서](https://documentation.wazuh.com)
- NIST SP 800-94: Guide to Intrusion Detection and Prevention Systems (IDPS)
