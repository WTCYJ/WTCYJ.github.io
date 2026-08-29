---
layout: post
title: "Android Security Concept Atlas C07 | 가상 실습 보고서 — DEX·multidex·resources.arsc, APK 안에서 코드와 리소스가 만나는 법"
date: 2026-10-17 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C07, DEX, Multidex, ResourcesARSC, APKAnalyzer, ReverseEngineering]
excerpt: "APK는 단일 코드 파일이 아닙니다. classes.dex 계열은 실행 코드와 타입 정보를, resources.arsc는 컴파일된 리소스 테이블을, Manifest는 컴포넌트와 권한 메타데이터를 담습니다. 분석 도구의 출력이 어느 파일에서 왔는지 구분해야 오판을 줄일 수 있습니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C07 · **Tier 1** · **선수 개념**: C06
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | 직접 만든 APK에는 AndroidManifest.xml, classes.dex, lib/x86_64/libatlasevidence.so가 들어갔고, dex packages 출력에서 MainActivity와 참조 API 테이블을 확인했습니다. 앱 내부에서도 자신의 APK ZIP 항목을 다시 읽어 같은 결과를 표시했습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C07 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-package.png)

## 1. 왜 이 개념이 필요한가

APK는 단일 코드 파일이 아닙니다. classes.dex 계열은 실행 코드와 타입 정보를, resources.arsc는 컴파일된 리소스 테이블을, Manifest는 컴포넌트와 권한 메타데이터를 담습니다. 분석 도구의 출력이 어느 파일에서 왔는지 구분해야 오판을 줄일 수 있습니다.

## 2. Android 구조에서의 위치와 신뢰 경계

빌드 시 javac/Kotlin 컴파일러의 바이트코드가 D8/R8을 거쳐 DEX가 되고, aapt2가 Manifest와 리소스를 패키징합니다. 메서드 참조 한계를 넘거나 분할이 필요하면 classes2.dex 같은 보조 DEX가 생기며 런타임의 클래스 로더가 이를 함께 다룹니다.

## 3. 정상 동작 흐름

1. 소스와 의존성을 JVM 바이트코드로 컴파일한다.
2. D8/R8이 검증 가능한 DEX 명령과 테이블로 변환한다.
3. aapt 계열 도구가 Manifest·리소스·DEX·네이티브 라이브러리를 APK에 묶는다.
4. Package Manager와 ART가 설치·검증·로드한다.

## 4. 실패가 보안 문제로 이어지는 조건

정적 분석에서 첫 DEX만 보거나 리소스 ID를 문자열처럼 해석하면 숨은 컴포넌트와 동적 참조를 놓칩니다. 반대로 APK에 문자열이 존재한다는 이유만으로 실행 가능 경로라고 단정해서도 안 됩니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
apkanalyzer files list atlas-evidence.apk
apkanalyzer dex packages atlas-evidence.apk
aapt dump badging atlas-evidence.apk
~~~

### 관측 결과

직접 만든 APK에는 AndroidManifest.xml, classes.dex, lib/x86_64/libatlasevidence.so가 들어갔고, dex packages 출력에서 MainActivity와 참조 API 테이블을 확인했습니다. 앱 내부에서도 자신의 APK ZIP 항목을 다시 읽어 같은 결과를 표시했습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

이 표본은 단일 DEX 소형 APK입니다. multidex와 AAB split 생성은 별도 대형 표본 또는 bundletool 환경에서 추가 검증해야 합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [AOSP DEX format](https://source.android.com/docs/core/runtime/dex-format)
- [AOSP DEX constraints](https://source.android.com/docs/core/runtime/constraints)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

DEX, 리소스, Manifest를 별도 증거원으로 읽고 마지막에 합쳐야 설치 구조와 실제 실행 경로를 혼동하지 않습니다.