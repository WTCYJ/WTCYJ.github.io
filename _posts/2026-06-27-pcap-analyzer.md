---
layout: post
title: "라이브러리 없이 pcap 파일 직접 파싱하기 — 패킷 구조 분석기 만들기"
date: 2026-06-27
category: 개발
author: WTCY
tags: [Network, pcap, Python, Ethernet, IP, TCP, UDP, ICMP, 패킷분석]
excerpt: "scapy/dpkt 없이 순수 Python으로 pcap 파일을 바이트 단위로 파싱하여 Ethernet/IP/TCP/UDP/ICMP 헤더와 프로토콜별 통계를 분석하고, 트래픽이 들려주는 이야기를 해석한다."
---


## 미션 목표

pcap 파일을 **직접 분석하는 프로그램**을 작성하여 네트워크 패킷의 구조와 동작 원리를 이해한다.

- pcap 파일을 열고 패킷을 순서대로 읽는다.
- Ethernet, IP, TCP, UDP, ICMP 헤더를 분석한다.
- 출발지 IP, 목적지 IP, 포트 번호, 프로토콜 정보를 출력한다.
- 패킷 개수와 프로토콜별 통계를 계산한다.
- 네트워크 트래픽에서 어떤 통신이 발생했는지 해석한다.

### 사용 가능한 라이브러리
- **C** — libpcap / WinPcap / Npcap
- **Python** — scapy / dpkt

이번엔 **일부러 라이브러리를 쓰지 않았다.** `scapy`를 쓰면 `pkt[IP].src` 한 줄로 끝나지만, 그 한 줄 뒤의 동작은 배우지 못한다. 미션의 목적이 *구조의 이해*이므로, Python 표준 라이브러리(`struct`, `socket`)만으로 pcap을 처음부터 끝까지 직접 파싱했다.

### 수행 과정
1. PCAP 파일 구조 이해
2. PCAP 파일 읽기 프로그램 작성
3. 패킷 헤더 분석
4. 프로토콜별 통계 작성
5. 분석 결과 보고서 작성

---

## 1. PCAP 파일 구조

pcap 파일은 단순하다. **글로벌 헤더 1개 + (레코드 헤더 + 패킷 데이터)의 반복**이다.

```
+----------------------+
| Global Header (24B)  |  파일 전체에 1개
+----------------------+
| Record Header (16B)  |  패킷 #1
| Packet Data (가변)   |
+----------------------+
| Record Header (16B)  |  패킷 #2
| Packet Data (가변)   |
+----------------------+
```

### 글로벌 헤더 (24바이트)

| 필드 | 크기 | 의미 |
|------|------|------|
| magic_number | 4 | 바이트 순서(엔디안) + 타임스탬프 해상도 판별 |
| version major/minor | 2+2 | 버전 (보통 2.4) |
| thiszone / sigfigs | 4+4 | 타임존, 정밀도 |
| snaplen | 4 | 캡처 최대 길이 |
| network | 4 | 링크 타입 (1 = Ethernet) |

**매직 넘버가 핵심이다.** `0xA1B2C3D4`면 빅엔디안, `0xD4C3B2A1`이면 리틀엔디안이다. 이 값으로 이후 모든 정수를 어떤 바이트 순서로 읽을지 결정한다.

```python
if magic == b"\xa1\xb2\xc3\xd4":
    self.endian, self.ts_unit = ">", 1_000_000      # big-endian, microsec
elif magic == b"\xd4\xc3\xb2\xa1":
    self.endian, self.ts_unit = "<", 1_000_000      # little-endian, microsec
```

### 레코드 헤더 (16바이트)

각 패킷 앞에 붙는다: `ts_sec`(4) · `ts_usec`(4) · `incl_len`(4, 저장된 길이) · `orig_len`(4, 원본 길이). `incl_len`만큼 읽으면 실제 패킷 바이트가 나온다.

```python
def __iter__(self):
    while True:
        hdr = self.f.read(16)
        if len(hdr) < 16:
            break
        ts_sec, ts_frac, incl_len, orig_len = struct.unpack(self.endian + "IIII", hdr)
        data = self.f.read(incl_len)
        yield ts_sec + ts_frac / self.ts_unit, orig_len, data
```

---

## 2. 헤더 계층별 파싱

패킷 데이터는 양파처럼 **L2 → L3 → L4** 헤더가 겹겹이 싸여 있다.

```
[ Ethernet ][ IP ][ TCP/UDP/ICMP ][ data ]
   14B        20B+    가변
```

### L2 — Ethernet (14바이트)

이더타입으로 상위 프로토콜을 안다: `0x0800`=IPv4, `0x0806`=ARP.

```python
def parse_ethernet(data):
    dst, src, etype = struct.unpack(">6s6sH", data[:14])
    return mac_str(dst), mac_str(src), etype, data[14:]
```

### L3 — IPv4

함정은 **IHL(헤더 길이)**다. IPv4 헤더는 옵션 때문에 가변이라, 첫 바이트 하위 4비트(IHL) × 4가 실제 헤더 길이다.

```python
def parse_ipv4(data):
    ihl = (data[0] & 0x0F) * 4          # 헤더 길이 = IHL * 4
    ttl, proto = data[8], data[9]
    src = socket.inet_ntoa(data[12:16])
    dst = socket.inet_ntoa(data[16:20])
    return {"ihl": ihl, "ttl": ttl, "proto": proto, "src": src, "dst": dst, "payload": data[ihl:]}
```

`proto`로 L4를 분기한다: `1`=ICMP, `6`=TCP, `17`=UDP.

### L4 — TCP / UDP / ICMP

TCP는 **data offset**과 **플래그**가 한 16비트 필드에 함께 들어 있다. 상위 4비트가 헤더 길이, 하위 6비트가 SYN/ACK/FIN 등 플래그다.

```python
def parse_tcp(data):
    sport, dport, seq, ack, off_flags = struct.unpack(">HHIIH", data[:14])
    data_off = (off_flags >> 12) * 4    # 상위 4비트 = 헤더 길이(워드)
    flags = off_flags & 0x3F            # 하위 6비트 = 플래그
    return {"sport": sport, "dport": dport, "flags": flags, "hlen": data_off}
```

UDP(8B)는 포트와 길이를, ICMP(4B+)는 type/code를 뽑는다.

---

## 3. 실행 결과 — 출력과 프로토콜별 통계

실제 캡처 없이 **ARP·DNS·ICMP·TCP·HTTPS·NTP 패킷을 손으로 조립한** `sample.pcap`을 만들고 분석했다.

<img width="926" height="1078" alt="pcap-run" src="https://github.com/user-attachments/assets/316cc08a-86a7-4ca5-bacd-decf4f670546" />

*▲ `pcap_analyzer.py`를 `sample.pcap`에 직접 실행한 결과 화면*

요약 통계(아래)는 미션의 "패킷 개수 + 프로토콜별 통계"를 그대로 만족한다.

```
========================================================
 분석 요약 (Summary)
========================================================
 총 패킷 수      : 12
 총 바이트       : 696 bytes
 L2 (Ethertype)  : {'ARP': 1, 'IPv4': 11}
 L3 (IP proto)   : {'UDP': 3, 'ICMP': 2, 'TCP': 6}
 L4 분포         : {'UDP': 3, 'ICMP': 2, 'TCP': 6}

 [상위 목적지 포트]
   :80       4회  HTTP
   :53       1회  DNS
   :443      1회  HTTPS

 [상위 통신 쌍 (src -> dst)]
      192.168.0.10 -> 192.168.0.20      5 packets
      192.168.0.10 -> 192.168.0.1       2 packets
========================================================
```

---

## 4. 트래픽 해석 — 무슨 통신이 일어났나?

통계 숫자보다 중요한 건 **이 패킷들이 들려주는 이야기**다. 출력 순서를 읽으면 한 호스트(192.168.0.10)의 전형적인 활동이 보인다.

1. **ARP** — "게이트웨이 MAC이 뭐야?" 통신 시작 전 L2 주소 해석.
2. **DNS (UDP/53)** — 도메인 이름을 IP로 바꾸는 질의/응답.
3. **ICMP** — type 8(echo request) → type 0(echo reply), 즉 `ping`.
4. **TCP handshake** — `SYN` → `SYN,ACK` → `ACK`. 80번 포트(HTTP) 연결의 3-way handshake.
5. **PSH,ACK** — 실제 데이터(`GET / HTTP/1.1`) 전송.
6. **SYN ->443** — HTTPS 연결 시도.
7. **FIN,ACK** — 연결 종료. / **NTP(UDP/123)** — 시간 동기화.

**TCP 플래그만 읽어도 연결의 생애주기(시작 SYN → 데이터 PSH → 종료 FIN)를 복원할 수 있다는 것**이 이번 실습의 가장 큰 수확이었다.

---

## 5. 배운 점

- pcap 파일은 **글로벌 헤더 + (레코드 헤더 + 데이터) 반복**이라는 단순한 구조다.
- 매직 넘버로 **엔디안**을 먼저 정하지 않으면 모든 정수 해석이 깨진다.
- IPv4의 **IHL**, TCP의 **data offset** 같은 "가변 길이 필드"를 정확히 처리하는 것이 파싱의 핵심이다.
- 헤더는 **L2 → L3 → L4로 겹겹이 캡슐화**되어 있고, 각 계층을 벗기면 다음 페이로드가 나온다.
- 통계 숫자 + 플래그 추적으로 트래픽의 *흐름*을 해석할 수 있다.

표준 라이브러리만으로 200줄 남짓한 코드가 Wireshark가 하는 일의 *가장 핵심적인 한 조각*을 재현한다.

---

## 부록 — 실제 캡처 적용 & 코드 구성

Wireshark/`tcpdump`로 **본인 소유 환경에서** 캡처한 `.pcap`에 그대로 쓸 수 있다.

```bash
tcpdump -i eth0 -w mycapture.pcap -c 100     # 허가된 환경에서만
python pcap_analyzer.py mycapture.pcap --limit 30
```

| 파일 | 역할 |
|------|------|
| `pcap_analyzer.py` | pcap 파서 + 헤더 분석 + 통계 (순수 표준 라이브러리) |
| `make_sample.py` | 테스트용 sample.pcap 생성기 |

> 심화: 같은 주제를 C/libpcap로 다시 구현하여 TCP 트래픽의 HTTP 메시지까지 추출하는 버전도 별도로 작성했다.

> 패킷 캡처는 반드시 **본인 소유 네트워크 또는 허가된 환경**에서만. 타인 트래픽 무단 감청은 불법이다.

## 참고 자료

- [PCAP File Format (Wireshark Wiki)](https://wiki.wireshark.org/Development/LibpcapFileFormat)
- [RFC 791 — IPv4](https://www.rfc-editor.org/rfc/rfc791) · [RFC 793 — TCP](https://www.rfc-editor.org/rfc/rfc793)
- [IANA Protocol Numbers](https://www.iana.org/assignments/protocol-numbers/)
