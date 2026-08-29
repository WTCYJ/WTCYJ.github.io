---
layout: post
title: "Android Security Concept Atlas C01 | 가상 실습 보고서 — 자산·주체·신뢰 경계·공격 표면, 보안 분석의 좌표계"
date: 2026-10-16 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C01, ThreatModel, Asset, Subject, TrustBoundary, AttackSurface]
excerpt: "보안 분석은 도구 목록이 아니라 자산, 주체, 경계, 진입점의 관계를 먼저 고정하는 작업입니다. 같은 기능도 무엇을 자산으로 두고 어떤 공격자를 가정하느냐에 따라 위험도가 달라집니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C01 · **Tier 0** · **선수 개념**: 없음
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 셸 주체와 앱 주체가 서로 다른 UID·SELinux 컨텍스트를 갖고, 증거 앱은 untrusted_app과 CapEff=0, Seccomp=2로 실행됐습니다. 이 결과를 이후 모든 모듈의 기본 공격자 모델로 사용합니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C01 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-environment.png)

## 1. 왜 이 개념이 필요한가

보안 분석은 도구 목록이 아니라 자산, 주체, 경계, 진입점의 관계를 먼저 고정하는 작업입니다. 같은 기능도 무엇을 자산으로 두고 어떤 공격자를 가정하느냐에 따라 위험도가 달라집니다.

## 2. Android 구조에서의 위치와 신뢰 경계

Android에서 앱 데이터와 사용자 자격 증명은 자산이고, 앱 UID·system_server·커널·TEE는 서로 다른 주체이자 신뢰 영역입니다. Binder, 파일, Intent, 소켓, JNI는 경계를 통과하는 입력 채널입니다. 공격 표면은 코드 양이 아니라 신뢰하지 않는 입력이 권한 있는 코드에 닿는 모든 경로의 집합으로 봅니다.

## 3. 정상 동작 흐름

1. 자산을 기밀성·무결성·가용성 기준으로 적는다.
2. 공격자 능력을 원격·로컬 앱·셸·커널 등으로 제한한다.
3. 데이터 흐름마다 UID·SELinux·Binder·암호화 경계를 표시한다.
4. 경계를 넘는 입력과 최종 보안 판정을 연결한다.

## 4. 실패가 보안 문제로 이어지는 조건

자산이나 공격자 능력을 생략하면 재현된 크래시를 곧바로 취약점으로 오판하거나, 반대로 높은 권한 프로세스의 입력 검증 결함을 단순 오류로 축소할 수 있습니다. 경계마다 누가 값을 만들고 누가 검증하는지 기록해야 합니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
adb -s emulator-5580 shell id
adb -s emulator-5580 shell getenforce
adb -s emulator-5580 shell cat /proc/self/status
~~~

### 관측 결과

셸 주체와 앱 주체가 서로 다른 UID·SELinux 컨텍스트를 갖고, 증거 앱은 untrusted_app과 CapEff=0, Seccomp=2로 실행됐습니다. 이 결과를 이후 모든 모듈의 기본 공격자 모델로 사용합니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

에뮬레이터 모델은 실제 사용자의 자산 가치나 조직의 서버 신뢰 경계를 대신하지 않습니다. 보고서마다 자산과 공격자 능력을 다시 선언해야 합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android platform security architecture](https://source.android.com/docs/security/overview)
- [Android security implementation guidance](https://source.android.com/docs/security/overview/implement)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

무엇을 지키는지, 누가 접근하는지, 어디서 신뢰가 바뀌는지를 먼저 적으면 나머지 55개 개념이 같은 좌표계에 놓입니다.