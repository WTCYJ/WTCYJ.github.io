---
layout: post
title: "Android Security Concept Atlas C22 | 가상 실습 보고서 — Binder 호출자 UID·identity clearing·confused deputy"
date: 2026-10-20 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C22, Binder, CallingUID, ClearCallingIdentity, ConfusedDeputy, Authorization]
excerpt: "Binder 서비스는 요청 내용뿐 아니라 누가 호출했는지를 함께 판정해야 합니다. getCallingUid를 너무 늦게 읽거나 clearCallingIdentity 뒤의 자기 UID를 원래 호출자로 착각하면 confused deputy가 됩니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C22 · **Tier 3** · **선수 개념**: C17, C19
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 수신 트랜잭션이 없는 앱 내부 대조군에서 process UID와 calling UID는 모두 10174였고, clear/restore 뒤에도 같은 값으로 복원돼 lifecycle이 PASS했습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C22 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-identity.png)

## 1. 왜 이 개념이 필요한가

Binder 서비스는 요청 내용뿐 아니라 누가 호출했는지를 함께 판정해야 합니다. getCallingUid를 너무 늦게 읽거나 clearCallingIdentity 뒤의 자기 UID를 원래 호출자로 착각하면 confused deputy가 됩니다.

## 2. Android 구조에서의 위치와 신뢰 경계

커널 Binder 드라이버가 트랜잭션 메타데이터에 호출자 PID/UID를 붙이고, 서비스 스레드는 Binder API로 이를 읽습니다. clearCallingIdentity는 중첩 호출에서 서비스 자신의 권한으로 작업할 때 쓰며 반환 토큰을 finally에서 반드시 복원해야 합니다.

## 3. 정상 동작 흐름

1. 진입 직후 calling UID를 캡처한다.
2. 그 UID에 대해 권한·소유권을 판정한다.
3. 필요한 최소 구간에서만 identity를 clear한다.
4. finally에서 원래 identity를 복원한다.

## 4. 실패가 보안 문제로 이어지는 조건

clear 뒤에 권한 검사를 수행하면 공격자의 요청이 서비스 UID 권한으로 승인될 수 있습니다. 호출자 UID와 데이터 내부의 userId를 같은 신원으로 믿는 것도 위험합니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section identity
~~~

### 관측 결과

수신 트랜잭션이 없는 앱 내부 대조군에서 process UID와 calling UID는 모두 10174였고, clear/restore 뒤에도 같은 값으로 복원돼 lifecycle이 PASS했습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

이 대조군은 원격 Binder 호출이 없어 공격자 UID 전환을 증명하지 않습니다. 실제 서비스에서는 별도 클라이언트 프로세스와 instrumented Stub이 필요합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [android.os.Binder API](https://developer.android.com/reference/android/os/Binder)
- [AOSP Binder overview](https://source.android.com/docs/core/architecture/ipc/binder-overview)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

호출자 identity는 데이터가 아니라 커널이 전달한 보안 문맥이며, clear 구간은 짧고 복원은 예외 안전해야 합니다.