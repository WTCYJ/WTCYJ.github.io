---
layout: post
title: "Android Security Concept Atlas C54 | 가상 실습 보고서 — 재현성·대조군 설계, 한 번의 현상을 검증 가능한 결과로 바꾸기"
date: 2026-10-26 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C54, Reproducibility, ControlGroup, TestMatrix, Evidence, SHA256]
excerpt: "재현성은 명령을 다시 실행할 수 있다는 뜻을 넘어, 입력·환경·버전·예상 결과가 고정되고 대조군이 원인 가설을 구분하는 상태를 말합니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C54 · **Tier 9** · **선수 개념**: C51, C53
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 동일 행렬을 두 번 실행한 출력 SHA-256이 모두 3aa7fd993937c3d27bfd23f5b1f60887152c2a6bcc5707ecc0db617b41a31721로 일치했습니다. 정상·경계·범위오류·overflow 네 대조군도 예상 판정과 일치했습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C54 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-environment.png)

## 1. 왜 이 개념이 필요한가

재현성은 명령을 다시 실행할 수 있다는 뜻을 넘어, 입력·환경·버전·예상 결과가 고정되고 대조군이 원인 가설을 구분하는 상태를 말합니다.

## 2. Android 구조에서의 위치와 신뢰 경계

Android 보안 실험에서는 API 레벨, ABI, 빌드 지문, 패치 수준, 앱 UID, sanitizer 옵션이 모두 결과에 영향을 줍니다. 양성 대조군과 음성 대조군 없이 한 크래시만 남기면 환경 문제와 보안 결함을 구분하기 어렵습니다.

## 3. 정상 동작 흐름

1. 환경 지문과 의존성 버전을 기록한다.
2. 정상·경계·오류·공격 가설 입력을 표로 고정한다.
3. 같은 스크립트를 독립적으로 두 번 실행한다.
4. 정규화된 출력의 해시와 차이를 비교한다.

## 4. 실패가 보안 문제로 이어지는 조건

스냅샷 상태, 랜덤 값, 시간, 네트워크 응답을 통제하지 않으면 재현 실패를 패치 효과로 오판할 수 있습니다. 실패 코드도 예상 결과라면 테스트 성공 조건에 명시해야 합니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
$run1 = ./run-matrix.ps1 | Out-String
$run2 = ./run-matrix.ps1 | Out-String
SHA256(run1) == SHA256(run2)
~~~

### 관측 결과

동일 행렬을 두 번 실행한 출력 SHA-256이 모두 3aa7fd993937c3d27bfd23f5b1f60887152c2a6bcc5707ecc0db617b41a31721로 일치했습니다. 정상·경계·범위오류·overflow 네 대조군도 예상 판정과 일치했습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

네트워크·스케줄링·주소값처럼 본질적으로 변하는 출력은 정규화 규칙을 별도 정의해야 합니다. 이번 하네스는 결정적 정수 검사만 다룹니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android security testing guidance](https://source.android.com/docs/security/overview/implement)
- [AOSP security reports](https://source.android.com/docs/security/overview/reports)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

재현 스크립트, 대조군 행렬, 종료 코드, 동일 출력 해시가 함께 있을 때 결과가 개인의 관찰에서 검증 가능한 기록으로 바뀝니다.