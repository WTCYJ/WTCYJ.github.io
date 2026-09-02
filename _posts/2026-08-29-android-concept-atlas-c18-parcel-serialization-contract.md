---
layout: post
title: "Android Security Concept Atlas C18 | 가상 실습 보고서 — Parcel 직렬화 계약, write/read 순서가 어긋날 때 생기는 일"
date: 2026-08-29 23:13:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C18, Binder, Parcel, Serialization, AIDL, TypeConfusion]
excerpt: "Parcel은 Binder 경계를 넘는 바이트 컨테이너입니다. 송신자와 수신자가 필드 순서·타입·nullable 규칙을 동일하게 이해해야 하며, 한 칸의 불일치가 이후 모든 필드의 해석을 밀어낼 수 있습니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C18 · **Tier 3** · **선수 개념**: C17
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 대칭 순서는 int 0x11223344와 문자열 atlas를 정확히 복원했습니다. 같은 버퍼를 String부터 읽은 불일치 대조군은 예외 대신 null을 돌려줬습니다. 즉 모든 mismatch가 명시적 크래시가 되는 것은 아닙니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C18 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-parcel.png)

## 1. 왜 이 개념이 필요한가

Parcel은 Binder 경계를 넘는 바이트 컨테이너입니다. 송신자와 수신자가 필드 순서·타입·nullable 규칙을 동일하게 이해해야 하며, 한 칸의 불일치가 이후 모든 필드의 해석을 밀어낼 수 있습니다.

## 2. Android 구조에서의 위치와 신뢰 경계

AIDL이 생성한 Stub/Proxy는 인터페이스 토큰과 인자를 정해진 순서로 쓰고 읽습니다. 수동 Parcel 코드나 버전이 다른 구현이 이 계약을 깨면 값 손실, 예외, 논리 타입 혼동이 생깁니다.

## 3. 정상 동작 흐름

1. 송신자가 int와 String을 순서대로 기록한다.
2. dataPosition을 처음으로 돌린다.
3. 수신자가 같은 타입·순서로 읽어 원본을 복원한다.
4. 다른 타입으로 읽는 대조군과 결과를 비교한다.

## 4. 실패가 보안 문제로 이어지는 조건

파서가 남은 크기와 타입을 검증하지 않거나 실패 뒤에도 진행하면 잘못된 길이와 객체가 권한 판정에 들어갈 수 있습니다. 단순 null이나 예외가 곧 취약점은 아니며, 공격자가 입력을 제어하고 보안 영향까지 이어져야 합니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section parcel
~~~

### 관측 결과

대칭 순서는 int 0x11223344와 문자열 atlas를 정확히 복원했습니다. 같은 버퍼를 String부터 읽은 불일치 대조군은 예외 대신 null을 돌려줬습니다. 즉 모든 mismatch가 명시적 크래시가 되는 것은 아닙니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

로컬 Parcel은 커널 Binder 전송과 원격 호출자 UID를 포함하지 않습니다. 실제 서비스 분석에서는 Stub의 enforceInterface와 길이 검사까지 함께 확인해야 합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android Parcel API](https://developer.android.com/reference/android/os/Parcel)
- [Android Binder overview](https://source.android.com/docs/core/architecture/ipc/binder-overview)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

직렬화는 형식보다 계약입니다. 정상 대조군과 불일치 대조군을 같이 두어야 조용한 값 손실과 명시적 거부를 구분할 수 있습니다.