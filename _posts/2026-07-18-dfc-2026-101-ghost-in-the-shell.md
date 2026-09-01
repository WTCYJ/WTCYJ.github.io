---
layout: post
title: "Ghost in the Shell — 파일리스 PowerShell 로더를 레지스트리 조각에서 되살리기"
date: 2026-07-18 21:00:00 +0900
category: 포렌식
author: WTCY
series: DFC 2026
tags: [DFC2026, 디지털포렌식, PowerShell, Sysmon, EVTX, 파일리스, 난독화, 레지스트리, XOR, ATT&CK]
excerpt: "디스크에 아무것도 남기지 않은 3단계 PowerShell 로더가 HKCU 레지스트리를 임시 저장소로 썼다. 문제는 같은 키 아래에 미끼 값이 잔뜩 깔려 있었다는 것 — 진짜 조각을 고르는 기준은 값의 이름이 아니라 그 값을 쓴 PID였다."
---

> **한 줄 결론**: 파일리스 로더의 흔적은 파일이 아니라 **레지스트리에 흩어진 조각**으로 남았고, 미끼와 진짜를 가른 것은 값의 이름이 아니라 **그 값을 기록한 프로세스의 PID/ProcessGuid** 였다.

## 무엇이 주어졌나

증거는 EVTX 두 개뿐이다.

| 증거 파일 | 레코드 수 | SHA-256 |
|---|---|---|
| `PowerShell-Operational.evtx` | 128 | `e9ebfaff2352fbed74cbddfc1dd98f9b603e15d75bb6cf7cee041551e5c068a1` |
| `Sysmon-Operational.evtx` | 58 | `105130cc6fa7af618b0820f7d7fca8cb860e609f93d9eaf249f4ab1ab9d199f9` |

두 파일 모두 `Get-WinEvent -Path` 로만 읽어 원본을 마운트하거나 수정하지 않았다. 디스크 이미지도, 메모리 덤프도, 악성코드 샘플도 없다. 즉 **실행 파일이 존재한 적이 없는 사건**이라는 전제를 로그만으로 증명해야 한다.

## 1. 잡음 속에서 진짜 프로세스를 고르기

Sysmon Event ID 1(프로세스 생성)에서 PowerShell 만 필터링하면 여러 건이 나온다. 전체 명령줄을 비교했을 때 `-nop -w hidden -ep bypass -enc` 조합을 모두 갖춘 것은 **PID 5140(레코드 ID 110)** 하나뿐이었다.

```
ProcessGuid : {c2b4f1c1-6010-6a3b-4202-000000000300}
User        : DESKTOP-A1VIHBP\DFC2026
Integrity   : High
CWD         : C:\Users\DFC2026\Desktop\01b_noise\
Parent      : cmd.exe (PID 3132)
```

작업 디렉터리 이름이 `01b_noise` 다. 출제자가 대놓고 잡음을 깔아 뒀다는 뜻이고, 실제로 레지스트리에는 그럴듯한 값이 여덟 개 넘게 흩어져 있었다.

여기서 판단 기준을 하나로 고정했다. **이벤트를 값 이름이 아니라 작성 PID/ProcessGuid 로 상관분석한다.** 이 기준을 세운 뒤에야 무관한 PID 가 쓴 유사 값과 실제 로더가 쓴 값 3개가 분리됐다.

## 2. 타임라인 (KST, 2026-06-24 / 원본 로그는 UTC)

| 시각 | 소스 / RID | PID | 내용 |
|---|---|---|---|
| 13:41:38.114 | Sysmon/13 RID 66 | 3060 | 미끼 `CachePath` 레지스트리 쓰기 |
| 13:41:45.275 | Sysmon/13 RID 99 | 628 | 미끼 `InstallId` |
| 13:41:45.340 | Sysmon/13 RID 104 | 5200 | 미끼 `SessionGuid` |
| **13:41:52.176** | Sysmon/1 RID 110 | **5140** | 핵심 PowerShell 프로세스 생성 |
| 13:41:53.625 | PS/4104 RID 121 | 5140 | 1단계 — `DeviceId` 기록 후 `IEX(gunzip)` |
| 13:41:53.965 | Sysmon/13 RID 113 | 5140 | `OneDrive\Update\DeviceId` |
| 13:41:54.267 | PS/4104 RID 126 | 5140 | 2단계 — `SyncState` 기록 후 3단계 실행 |
| 13:41:54.269 | Sysmon/13 RID 114 | 5140 | `OneDrive\Update\SyncState` |
| 13:41:54.291 | PS/4104 RID 130 | 5140 | 3단계 — `TelemetryCache` 기록, 토큰 복원, DNS |
| 13:41:54.292 | Sysmon/13 RID 115 | 5140 | `OneDrive\Update\TelemetryCache` |
| 13:41:55.362 | Sysmon/22 RID 120 | 5140 | `cdn-sync-update.com` DNS 질의 |
| 13:41:55.944 | Sysmon/5 RID 116 | 5140 | 프로세스 종료 |

전체 사건이 **3.8초** 만에 끝난다. 미끼 세 건이 핵심 프로세스보다 앞선 시각에 배치돼 있어, 시간순으로만 훑으면 잘못된 값부터 집게 된다.

## 3. 3단계 실행 체인 복원

`-enc` 인자를 Base64 → UTF-16LE 로 디코딩하면 1단계 스크립트가 나온다. 각 단계는 같은 패턴을 반복한다.

1. **1단계** — `DeviceId` 를 레지스트리에 쓰고, Base64+GZip 페이로드를 `GzipStream` 으로 메모리에서 해제한 뒤 `IEX` 로 실행
2. **2단계** — `SyncState` 를 쓰고, 같은 방식으로 3단계를 메모리에서 실행
3. **3단계** — `TelemetryCache` 를 쓰고, 앞서 남긴 값 3개를 **다시 읽어** 반복 XOR 로 토큰을 복원한 뒤 `Resolve-DnsName` 수행

레지스트리가 단순한 지속성 수단이 아니라 **단계 간 데이터를 넘기는 임시 저장소**로 쓰였다. 디스크에 파일을 쓰지 않고도 상태를 유지하는 방법이고, 그래서 이 사건에서 레지스트리 값이 곧 페이로드다.

### ATT&CK 매핑

- **T1059.001** PowerShell — 인코딩된 명령
- **T1027 / T1140** 난독화 및 역난독화 — Base64/UTF-16LE + 중첩 GZip 메모리 해제
- **T1112** 레지스트리 변조 — `HKCU:\Software\OneDrive\Update` 를 OneDrive 데이터로 위장한 스테이징
- **T1564.003 / T1562.001** 창 은닉 및 실행 정책 우회 — `-w hidden`, `-ep bypass`
- **T1071.004** DNS — 토큰 조립 후 `cdn-sync-update.com` 질의

## 4. 미끼와 진짜를 가르는 선

PID 상관분석 결과, 다음 값들은 **다른 PID 가 쓴 미끼**였다.

```
CachePath, UploadToken, InstallId, SessionGuid,
Adobe\ARM\State, Google\Update\Cookie,
Run\EdgeUpdate, Run\Teams
```

PID 5140 이 쓰고 **동시에 최종 스크립트가 다시 읽는** 값은 딱 세 개다 — `DeviceId`, `SyncState`, `TelemetryCache`.

"쓴 주체"와 "읽는 주체"가 같은지를 확인하는 것이 미끼를 걸러 내는 유일한 기준이었다. 값 이름만 보면 `UploadToken` 이 훨씬 그럴듯해 보인다.

## 5. 복호화 — 순서가 정답을 가른다

- `DeviceId = UjNkVDM0bV9ERkM=` → Base64 디코딩하면 11바이트 XOR 키 `R3dT34m_DFC`
- `SyncState = FH8lE0hQXm8mIDYhUFAgAG` (암호문 조각 1)
- `TelemetryCache = sVbzYZIGJBFmdfABlsOQ==` (암호문 조각 2)

여기서 한 번 막혔다. `SyncState` 를 단독으로 Base64 디코딩하면 실패한다. 패딩이 완성되지 않은 조각이기 때문이다. 3단계 코드가 하는 일은 **두 조각을 먼저 이어 붙인 뒤 통째로 디코딩** 하는 것이다.

```powershell
$SyncState      = 'FH8lE0hQXm8mIDYhUFAgAG'
$TelemetryCache = 'sVbzYZIGJBFmdfABlsOQ=='
$DeviceId       = 'UjNkVDM0bV9ERkM='

$ct = [Convert]::FromBase64String($SyncState + $TelemetryCache)
$k  = [Convert]::FromBase64String($DeviceId)
-join (0..($ct.Length-1) | %{ [char]($ct[$_] -bxor $k[$_ % $k.Length]) })
# FLAG{d30bfusc4t3_x0r_c0rr3l4t3}
```

조각을 각각 디코딩해서 이어 붙이면 깨진 바이트가 나온다. "붙인 다음 디코딩" 과 "디코딩한 다음 붙이기" 는 Base64 에서 다른 연산이다.

## 정리 — 이 문제에서 남는 것

파일리스 공격이라고 흔적이 없는 게 아니다. 디스크에 파일을 쓰지 않는 대신 **레지스트리·이벤트 로그·DNS 질의로 흔적이 분산**될 뿐이다.

실전에서 가져갈 만한 것 세 가지.

1. **PID/ProcessGuid 상관분석이 값 이름보다 강하다.** 이름 기반 IOC 는 미끼에 그대로 걸린다.
2. **레지스트리를 지속성 수단으로만 보지 말 것.** 여기서는 단계 간 데이터 전달 통로였고, 프로세스가 종료된 뒤에도 페이로드가 남아 재현이 가능했다.
3. **디코딩 순서는 코드가 정한다.** 조각을 어떻게 합칠지는 추측이 아니라 3단계 스크립트를 읽어서 확정해야 했다.

---

*DFC 2026 출제 문제 101번에 대한 분석 기록. 2인 팀 참가 제출본을 블로그용으로 정리했다.*
