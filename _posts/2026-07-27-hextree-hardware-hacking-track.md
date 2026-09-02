---
layout: post
title: "전압 폴트 인젝션 입문 — HexTree Hardware Hacking 트랙 정리"
date: 2026-07-27
category: 시스템
author: WTCY
tags: [HexTree, 하드웨어해킹, FaultInjection, VoltageGlitching, 전압글리칭, CrowbarGlitch, nRF52, APPROTECT, STM32, ReadoutProtection, walletfail, AirTag, Faultier, 임베디드보안, 펌웨어보안]
excerpt: "코드에 결함이 없어도 칩의 전원을 수십 나노초 흔들면 명령 하나가 건너뛰어집니다. HexTree Hardware Hacking 트랙의 세 코스를 따라 전압 폴트 인젝션의 원리와 파라미터 구조, nRF52 APPROTECT·STM32 읽기보호가 무력화된 사례, 그리고 방어 설계를 정리했습니다."
---

> **대상**: [HexTree Hardware Hacking](https://app.hextree.io/map/hardware-hacking) 트랙 — 코스 3개
> **주제**: 전압 폴트 인젝션 기초 · nRF52 APPROTECT 우회 · STM32 읽기보호 우회
> **결과**: 세 코스 모두 이수(각 100%)
> **범위 제한**: 실습 랩은 Faultier·GlitchTag 등 전용 장비가 필요합니다. 이 글은 **원리와 사례 정리**이며, 글리칭을 직접 수행한 기록이 아닙니다.

---

## 1. Overview

[Android 트랙](/posts/hextree-android-track/)에 이어 같은 맵의 Hardware Hacking 트랙을 진행했습니다.
소프트웨어 취약점 분석이 "개발자가 신뢰 경계를 어디서 잘못 그었는가"를 찾는 작업이라면, 폴트 인젝션은
전제 자체가 다릅니다. **코드에 결함이 없어도 성립하는 공격**이기 때문입니다.

칩은 데이터시트가 규정한 전압·클럭·온도 범위 안에서만 정상 동작을 보장합니다. 이 범위를 아주 짧은
순간 벗어나게 만들면 연산 결과가 틀어지고, 그 틈에 인증 분기 하나가 통째로 건너뛰어집니다.

| 코스 | 주제 | 모듈 |
|---|---|---|
| Your first Glitch/Voltage Fault Injection | 폴트 인젝션 이론과 첫 실습 | 3 |
| Glitching the nRF52 APPROTECT protection | 디버그 보호 우회(AirTag 사례) | 3 |
| Glitching the STM32 (Conference Edition) | 읽기보호 우회(wallet.fail 재현) | 1 |

---

## 2. Course 1 — Your first Glitch/Voltage Fault Injection

이론 → 장비 → 첫 실습 순으로 구성된 입문 코스입니다.

| 모듈 | 구성 |
|---|---|
| Fault-injection Theory | Introduction · Trigger, Delay and Pulse · Chip Power Supplies · Crowbar Glitching |
| The Faultier | 하드웨어 소개 · 소프트웨어 소개 · OpenOCD 설치 · Jupyter 노트북 연동 |
| Performing our first glitch | GlitchTag 플래싱 · 펌웨어 분석 · 하드웨어 셋업 점검 · 글리치 수행 |

### 2.1 공격 방식의 분류

무엇을 흔드는지에 따라 기법이 나뉩니다.

| 방식 | 대상 | 특징 |
|---|---|---|
| 전압 글리칭 | 코어 전원(VCC)을 수십~수백 ns 강하 | 장비 비용이 낮고 진입장벽이 작음 |
| 클럭 글리칭 | 클럭 신호에 짧은 펄스 삽입 | 외부 클럭을 사용하는 칩에 한정 |
| EM 폴트 인젝션 | 코일을 통한 국소 전자기 펄스 | 패키지 개봉 불필요, 위치 선택 가능 |
| 레이저 | 다이에 직접 광 펄스 | 정밀도가 가장 높고 장비가 고가 |

성공 시 CPU 관점에서 나타나는 대표 증상은 **명령어 인출 실패**입니다. 실행하려던 명령이 `nop`처럼
지나가므로, 공격 지점은 대체로 다음 세 곳으로 수렴합니다.

- 비교문 직후의 분기 명령
- 루프 카운터 갱신
- 권한 검사 함수의 반환값 처리

### 2.2 파라미터 구조

전압 글리칭은 세 개의 값을 탐색하는 문제로 환원됩니다.

| 파라미터 | 의미 | 결정 요소 |
|---|---|---|
| Trigger | 계측을 시작할 기준점 | 리셋 해제, UART 명령 송신, GPIO 변화 등 재현 가능한 이벤트 |
| Delay | 트리거 이후 대기 시간 | 목표 명령이 실행되는 시점까지의 거리 |
| Pulse width | 전압을 강하시키는 시간 | 너무 짧으면 무반응, 너무 길면 리셋 |

실제 작업은 Delay와 Pulse width를 격자 형태로 탐색하며 결과를 네 가지로 분류하는 과정입니다.
정상 동작, 리셋, 무반응, 그리고 목표인 **이상 동작**입니다. 코스가 Jupyter 노트북 기반으로 구성된
이유도 여기에 있습니다. 수천 회 반복 후 성공 좌표의 분포를 통계로 확인해야 하는 작업입니다.

### 2.3 크로우바 글리칭

전압 강하는 정밀 가변 전원이 아니라 **크로우바(crowbar)** 방식으로 구현하는 것이 일반적입니다.
MOSFET으로 코어 전원 핀을 그라운드에 순간적으로 단락시키는 방법입니다.

이 방식이 성립하려면 보드의 전원부 조건이 맞아야 합니다. 칩 주변의 디커플링 커패시터가 순간 전류
변동을 흡수해 전압을 평탄하게 유지하기 때문에, 실전에서는 **디커플링 커패시터를 제거**하고 내부
레귤레이터를 거치지 않는 코어 전압 핀에 직접 접근합니다.

여기서 소프트웨어 취약점과 결정적으로 다른 성질이 드러납니다. 글리칭은 **동일 모델의 동일 칩이라도
개체마다 성공 파라미터가 달라집니다.** 전원 배선, 커패시터 잔량, 온도가 모두 변수입니다. 그래서 이
분야의 보고서는 단일 파라미터가 아니라 "해당 범위에서 N회 중 M회 성공"이라는 형태로 기술됩니다.

<p align="center"><img src="/assets/img/hextree-hardware-hacking/course-fault-injection-intro.jpg" alt="Your first Glitch/Voltage Fault Injection 코스 완료 카드" width="680" style="max-width:100%;height:auto;margin:6px 0"></p>

---

## 3. Course 2 — Glitching the nRF52 APPROTECT (AirTag Glitch)

공개된 실제 공격을 재현하는 코스입니다. 대상 분석 → 전력 소비 관찰 → 공격 수행 순으로 진행됩니다.

### 3.1 APPROTECT의 적용 시점

Nordic nRF52 시리즈의 APPROTECT는 활성화 시 SWD를 통한 펌웨어 읽기와 디버깅을 차단합니다. 제품
펌웨어를 보호하는 최종 방어선이며, 2020년 LimitedResult가 전압 글리칭을 통한 우회 기법을 공개했습니다.

핵심은 보호가 **상시 유지되는 상태가 아니라는 점**입니다. 칩은 리셋 해제 후 UICR 영역의 설정을 읽어
디버그 블록에 반영하는 초기화 과정을 거칩니다. 즉 전원 인가 시점부터 보호가 실제로 적용되기까지
**짧은 무방비 구간**이 존재합니다.

```
전원 인가 ─▶ [초기화: UICR 읽기 → 디버그 블록 반영] ─▶ 보호 적용 완료
                     ▲
                 이 구간에 글리치 → 반영 실패 → 디버그 포트 활성 상태로 부팅
```

이후에는 일반적인 SWD 접속으로 펌웨어 덤프가 가능합니다.

### 3.2 전력 소비 관찰의 역할

코스에 전력 소비 분석 모듈이 포함된 이유는 Delay 탐색 범위를 좁히기 위해서입니다. 칩의 내부 상태는
외부에서 보이지 않지만, 전류 파형은 부팅 단계마다 서로 다른 패턴을 형성합니다. 이를 기준으로 초기화
구간의 위치를 추정하면 전 구간을 무작위로 탐색할 때보다 시도 횟수를 크게 줄일 수 있습니다.

이 기법은 애플 AirTag 사례로 널리 알려졌습니다. AirTag의 메인 칩이 nRF52832이며, 동일한 방식으로
디버그 인터페이스를 복구해 펌웨어를 덤프하고 수정 펌웨어를 기록한 결과가 공개된 바 있습니다.

<p align="center"><img src="/assets/img/hextree-hardware-hacking/course-nrf52-approtect.jpg" alt="Glitching the nRF52 APPROTECT protection 코스 완료 카드" width="680" style="max-width:100%;height:auto;margin:6px 0"></p>

---

## 4. Course 3 — Glitching the STM32 (Conference Edition)

2018년 35C3에서 발표된 **wallet.fail**을 재현하는 단일 모듈 코스입니다. 대상은 Trezor One 하드웨어
지갑이며 칩은 STM32F205입니다.

### 4.1 RDP 레벨 다운그레이드

STM32의 RDP(Readout Protection)는 단계별 보호를 제공하며, 레벨 2에서는 디버그 인터페이스가 영구적으로
차단되는 것으로 알려져 있었습니다. 발표자들은 부팅 초기에 RDP 레벨을 판정하는 지점을 글리칭으로
교란해 **레벨 2를 레벨 1로 인식**하게 만들었습니다.

| RDP 레벨 | 정상 동작 | 글리칭 이후 |
|---|---|---|
| Level 2 | 디버그 인터페이스 영구 차단 | 판정 시점 교란으로 Level 1처럼 처리 |
| Level 1 | 플래시 읽기 차단, **SRAM 접근 가능** | 그대로 SRAM 접근 |

### 4.2 펌웨어 측 문제와의 결합

여기에 펌웨어의 데이터 취급 문제가 겹칩니다. 지갑 펌웨어는 업그레이드 과정에서 시드(복구 단어)를
**SRAM에 평문으로 적재**하는 구간을 두고 있었습니다. 결과적으로 글리칭으로 SRAM 접근을 확보한 뒤
시드를 그대로 추출할 수 있었습니다.

두 사례의 공통점은 분명합니다. 어느 쪽도 암호 알고리즘을 깨뜨리지 않았습니다. **보호가 적용되는
과도 구간**을 노렸을 뿐입니다. 알고리즘 강도만으로 방어를 평가하면 놓치게 되는 지점입니다.

<p align="center"><img src="/assets/img/hextree-hardware-hacking/course-stm32-conference.jpg" alt="Glitching the STM32 Conference Edition 코스 완료 카드" width="680" style="max-width:100%;height:auto;margin:6px 0"></p>

---

## 5. 방어 설계

세 코스에서 확인한 공격 패턴을 방어 관점으로 정리하면 다음과 같습니다.

| # | 대응 | 근거 |
|---|---|---|
| 1 | 중요한 판정은 서로 다른 방식으로 2회 이상 검사하고 결과가 일치할 때만 통과 | 글리치는 단일 명령 스킵에는 강하지만 이격된 두 지점을 동시에 적중시키기는 어려움 |
| 2 | 참/거짓을 `0`/`1`이 아닌 해밍 거리가 큰 매직 값으로 표현 (`0xA5A5A5A5` 등) | 비트 일부가 반전돼도 성공 값으로 변질되지 않음 |
| 3 | 실행 경로에 랜덤 딜레이 삽입 | 공격자가 Delay 파라미터를 고정하지 못함 |
| 4 | 브라운아웃·글리치 감지 회로 활성화 | 다수 MCU가 기능을 제공하나 기본값이 비활성인 경우가 많음 |
| 5 | 키는 보안 요소(SE)에 보관 | 메인 MCU가 뚫려도 키가 직접 노출되지 않음 |
| 6 | 민감 데이터의 메모리 체류 시간 최소화, 사용 후 즉시 소거 | wallet.fail의 SRAM 시드 추출이 대표 사례 |

---

## 6. 범위와 한계

세 코스의 강의는 모두 이수했으나 **실습 랩은 수행하지 못했습니다.** 해당 랩은 HexTree Faultier
글리칭 보드와 GlitchTag(nRF52832) 타깃이 필요하며, 현재 장비를 보유하고 있지 않습니다. 완료 카드의
`LAB PROGRESSION`이 `0 / 1`로 표시된 이유입니다.

| 코스 | 이수 | 실습 랩 |
|---|---|---|
| Your first Glitch/Voltage Fault Injection | 100% | 장비 필요 |
| Glitching the nRF52 APPROTECT (AirTag Glitch) | 100% | 장비 필요 |
| Glitching the STM32 (Conference Edition) | 100% | 랩 없음 |

같은 맵의 Web Security 트랙도 확인했으나, 무료 프리뷰 코스 1개를 제외한 전 코스와 모든 랩이 유료
구독 대상이었습니다. 프리뷰 코스 역시 영상만 무료이고 랩은 구독이 필요해, 해당 코스만 이수했습니다.

---

## 7. 정리

Android 트랙이 "앱이 외부 입력을 어디까지 신뢰하는가"를 다뤘다면, 이 트랙의 질문은
**"칩은 언제부터 안전해지는가"** 입니다. 보호 기능의 존재 여부가 아니라 그 기능이 적용되기까지의
과도 구간에 무엇이 열려 있는지를 확인하게 되며, 소프트웨어 보안의 TOCTOU와 구조적으로 동일한
문제입니다.

장비를 확보하면 파라미터 탐색을 직접 수행하고 성공률을 포함한 재현 기록을 별도로 정리할 예정입니다.

## References

- HexTree Hardware Hacking 트랙 — <https://app.hextree.io/map/hardware-hacking>
- LimitedResult, *nRF52 Debug Resurrection (APPROTECT Bypass)* — <https://limitedresults.com/2020/06/nrf52-debug-resurrection-approtect-bypass/>
- wallet.fail (35C3, 2018) — Thomas Roth · Dmitry Nedospasov · Josh Datko, <https://wallet.fail/>
- Colin O'Flynn — 폴트 인젝션·사이드채널 연구 자료, <https://www.colinoflynn.com/>
