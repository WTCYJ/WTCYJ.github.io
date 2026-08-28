---
layout: post
title: "Android Security Concept Atlas C26 | 가상 실습 보고서 — UID 샌드박스와 SELinux, 서로 다른 두 겹의 역할"
date: 2026-10-21 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C26, Sandbox, UID, SELinux, DAC, MAC, Seccomp]
excerpt: "Android 앱 격리는 하나의 기능이 아닙니다. Linux UID/DAC는 소유권 기반 1차 경계이고, SELinux/MAC는 주체·객체 라벨과 정책에 따른 추가 경계입니다. seccomp와 capability는 시스템 콜과 커널 권한을 더 줄입니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C26 · **Tier 4** · **선수 개념**: C09, C23, C24
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 앱은 UID 10174, SELinux untrusted_app, 데이터 타입 app_data_file, CapEff=0, Seccomp=2로 실행됐습니다. 한 화면에서 네 통제가 서로 다른 필드로 나타났습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C26 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

## 1. 왜 이 개념이 필요한가

Android 앱 격리는 하나의 기능이 아닙니다. Linux UID/DAC는 소유권 기반 1차 경계이고, SELinux/MAC는 주체·객체 라벨과 정책에 따른 추가 경계입니다. seccomp와 capability는 시스템 콜과 커널 권한을 더 줄입니다.

## 2. Android 구조에서의 위치와 신뢰 경계

앱 설치 시 Package Manager가 UID와 데이터 디렉터리를 배정하고, Zygote가 해당 UID·GID로 프로세스를 시작합니다. SELinux는 untrusted_app 도메인과 app_data_file 타입 사이의 allow 규칙을 별도로 판단합니다.

## 3. 정상 동작 흐름

1. 고유 UID가 파일 소유권을 분리한다.
2. SELinux 도메인이 허용된 객체·행위를 제한한다.
3. capability를 비우고 seccomp가 syscall 집합을 줄인다.
4. Binder와 컴포넌트 계층이 명시적 공유 경로를 제공한다.

## 4. 실패가 보안 문제로 이어지는 조건

같은 UID 공유, 지나치게 넓은 allow, permissive 도메인, 과도한 capability 중 하나만 있어도 폭발 반경이 커집니다. 두 겹이 같은 EL1 커널에 의존하므로 커널 장악에는 함께 무너질 수 있다는 한계도 있습니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section sandbox
~~~

### 관측 결과

앱은 UID 10174, SELinux untrusted_app, 데이터 타입 app_data_file, CapEff=0, Seccomp=2로 실행됐습니다. 한 화면에서 네 통제가 서로 다른 필드로 나타났습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

하나의 앱만으로 앱 간 파일 접근 대조군까지 만들지는 않았습니다. 다만 각 통제의 활성 상태와 앱 데이터 라벨은 실제 프로세스에서 확인했습니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android application sandbox](https://source.android.com/docs/security/app-sandbox)
- [SELinux in Android](https://source.android.com/docs/security/features/selinux)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

UID와 SELinux를 같은 말로 쓰지 말고 소유권 경계와 정책 경계로 나누면 우회 조건과 방어 범위를 정확히 설명할 수 있습니다.