---
layout: post
title: "Android Security Concept Atlas C53 | 가상 실습 보고서 — patch diff·variant analysis, 수정 한 줄에서 보안 불변식을 복원하기"
date: 2026-10-25 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C53, PatchDiff, VariantAnalysis, RootCause, IntegerOverflow, UBSan]
excerpt: "패치 diff의 목적은 바뀐 줄을 외우는 것이 아니라 수정이 복원한 불변식을 찾는 것입니다. 그 불변식을 같은 코드베이스의 유사 함수와 다른 브랜치에 적용하면 variant analysis가 됩니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C53 · **Tier 9** · **선수 개념**: C51, C52
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 세 정상·경계 대조군에서 before/after 판정이 같았고, overflow에서 before는 UBSan exit 134, after는 안전한 REJECT exit 1이었습니다. 수정이 정상 기능을 유지하면서 undefined behavior만 제거했습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C53 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-kernel.png)

## 1. 왜 이 개념이 필요한가

패치 diff의 목적은 바뀐 줄을 외우는 것이 아니라 수정이 복원한 불변식을 찾는 것입니다. 그 불변식을 같은 코드베이스의 유사 함수와 다른 브랜치에 적용하면 variant analysis가 됩니다.

## 2. Android 구조에서의 위치와 신뢰 경계

길이 검사의 before 버전은 offset+length를 먼저 계산해 overflow가 가능했고, after 버전은 offset과 length를 각각 검증한 뒤 length <= total-offset을 사용했습니다. 수정의 핵심은 덧셈 결과가 표현 가능하다고 가정하지 않는 것입니다.

## 3. 정상 동작 흐름

1. 변경 전·후를 같은 컴파일 옵션으로 빌드한다.
2. 정상·경계·범위 초과·overflow 입력을 양쪽에 동일 적용한다.
3. 결과와 sanitizer 신호를 행렬로 비교한다.
4. 복원된 불변식으로 유사 코드를 검색한다.

## 4. 실패가 보안 문제로 이어지는 조건

패치의 상수나 함수 이름만 검색하면 다른 표현의 같은 원인을 놓칩니다. 반대로 문법이 비슷하다는 이유만으로 variant라 단정하면 실제 데이터 범위와 호출 문맥을 놓칩니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
./run-matrix.ps1
# normal, boundary, range-error, overflow를 before/after에 동일 적용
~~~

### 관측 결과

세 정상·경계 대조군에서 before/after 판정이 같았고, overflow에서 before는 UBSan exit 134, after는 안전한 REJECT exit 1이었습니다. 수정이 정상 기능을 유지하면서 undefined behavior만 제거했습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

교육용 정수 검사 한 쌍이므로 실제 AOSP 패치의 동시성·수명·권한 문맥까지 대표하지 않습니다. 실제 variant 검색은 호출 그래프와 타입 범위를 추가해야 합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android security implementation guidance](https://source.android.com/docs/security/overview/implement)
- [MITRE CWE theory: chains and weaknesses](https://cwe.mitre.org/documents/vulnerability_theory/intro.html)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

좋은 patch diff는 변경 줄이 아니라 깨졌던 불변식, 대조군, 회귀 여부를 설명합니다.