---
layout: post
title: "Android Security Concept Atlas C55 | 가상 실습 보고서 — 위협 모델·실제 영향 산정, 기술적 결함을 위험도로 번역하기"
date: 2026-10-27 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C55, ThreatModel, Impact, Severity, Exploitability, RiskAssessment]
excerpt: "심각도는 크래시 모양이 아니라 공격자 능력, 도달성, 필요한 상호작용, 대상 권한, 자산 영향, 완화책을 함께 평가한 결과입니다. 같은 코드 결함도 실행 문맥이 달라지면 위험도가 달라집니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C55 · **Tier 9** · **선수 개념**: C01, C51, C54
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 교육용 overflow는 AVD 임시 실행 파일에서만 발생했고 보호 자산·권한 상승·지속성이 없었습니다. 따라서 확인한 것은 CWE 유형의 bug와 수정 효과이며, 실제 제품 vulnerability나 exploit 영향은 0으로 판정했습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C55 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

## 1. 왜 이 개념이 필요한가

심각도는 크래시 모양이 아니라 공격자 능력, 도달성, 필요한 상호작용, 대상 권한, 자산 영향, 완화책을 함께 평가한 결과입니다. 같은 코드 결함도 실행 문맥이 달라지면 위험도가 달라집니다.

## 2. Android 구조에서의 위치와 신뢰 경계

앱 sandbox 내부 로컬 파서, exported 고권한 서비스, 커널 드라이버, TEE는 각각 다른 신뢰 경계와 TCB를 갖습니다. 보고서는 어디서 실행되는지와 공격자가 어떤 입력을 제어하는지를 먼저 적어야 합니다.

## 3. 정상 동작 흐름

1. 공격자 시작 권한과 접근 채널을 선언한다.
2. 취약 코드의 프로세스·UID·SELinux·EL을 확인한다.
3. 기밀성·무결성·가용성 영향을 분리한다.
4. 완화와 사용자 상호작용을 반영해 현실적 최악 영향을 적는다.

## 4. 실패가 보안 문제로 이어지는 조건

개발자 옵션·부트로더 unlock·물리 접근이 필요한 재현을 일반 원격 공격처럼 쓰거나, 커널 크래시를 자동으로 코드 실행이라 부르면 위험도가 부풀려집니다. 반대로 권한 있는 confused deputy는 크래시가 없어도 중요합니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
adb shell id
adb shell getenforce
./run-matrix.ps1
# 결과를 공격자·권한·자산 표에 매핑
~~~

### 관측 결과

교육용 overflow는 AVD 임시 실행 파일에서만 발생했고 보호 자산·권한 상승·지속성이 없었습니다. 따라서 확인한 것은 CWE 유형의 bug와 수정 효과이며, 실제 제품 vulnerability나 exploit 영향은 0으로 판정했습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

실제 제품 위험도는 벤더 구성, 패치 수준, 배포 범위, 탐지 상태에 따라 달라집니다. 이 글의 결론은 교육용 하네스에만 적용됩니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android security severity guidance](https://source.android.com/docs/security/overview/updates-resources)
- [MITRE CWE glossary](https://cwe.mitre.org/documents/glossary/index)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

좋은 영향 산정은 기술적 가능성과 현실적 조건을 분리하고, 증명한 범위까지만 주장합니다.