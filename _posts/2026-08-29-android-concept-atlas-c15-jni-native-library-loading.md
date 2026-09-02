---
layout: post
title: "Android Security Concept Atlas C15 | 가상 실습 보고서 — JNI 경계·네이티브 라이브러리 로딩, 관리 코드와 C/C++ 사이의 계약"
date: 2026-08-29 23:09:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C15, JNI, NDK, NativeLibrary, Linker, ABI]
excerpt: "JNI는 Kotlin/Java와 C/C++ 사이의 호출 규약입니다. 객체 수명, 스레드별 JNIEnv, 예외 처리, 배열 길이와 문자 인코딩을 잘못 다루면 관리 런타임의 안전성이 네이티브 메모리 오류로 바뀝니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C15 · **Tier 2** · **선수 개념**: C13, C33
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | NDK 27.3으로 x86_64 .so를 RELRO/BIND_NOW/noexecstack 옵션과 함께 빌드했습니다. 표준 APK 경로로 수정한 뒤 Java→JNI→native→Java 왕복, JNIEnv non-null, 64-bit 포인터가 모두 PASS였습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C15 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-jni.png)

## 1. 왜 이 개념이 필요한가

JNI는 Kotlin/Java와 C/C++ 사이의 호출 규약입니다. 객체 수명, 스레드별 JNIEnv, 예외 처리, 배열 길이와 문자 인코딩을 잘못 다루면 관리 런타임의 안전성이 네이티브 메모리 오류로 바뀝니다.

## 2. Android 구조에서의 위치와 신뢰 경계

System.loadLibrary가 ABI에 맞는 .so를 동적 링커로 적재하고, 이름 기반 심볼 또는 RegisterNatives가 Java 선언과 네이티브 함수를 연결합니다. JNIEnv는 현재 스레드의 JNI 함수 테이블이며 다른 스레드에 그대로 보관해 재사용하면 안 됩니다.

## 3. 정상 동작 흐름

1. NDK clang이 목표 ABI용 ELF 공유 라이브러리를 만든다.
2. APK의 lib/ABI 디렉터리에 라이브러리를 넣는다.
3. Package Manager가 ABI에 맞는 파일을 설치한다.
4. System.loadLibrary와 JNI 바인딩 후 값을 왕복한다.

## 4. 실패가 보안 문제로 이어지는 조건

길이·부호·소유권 계약이 양쪽에서 다르면 OOB, UAF, 로컬 참조 누수, 잘못된 스레드 사용이 됩니다. 라이브러리 경로와 ABI가 틀리면 코드 실행 전 UnsatisfiedLinkError로 종료됩니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
./build.ps1
adb -s emulator-5580 install -r build/atlas-evidence.apk
adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section jni
~~~

### 관측 결과

NDK 27.3으로 x86_64 .so를 RELRO/BIND_NOW/noexecstack 옵션과 함께 빌드했습니다. 표준 APK 경로로 수정한 뒤 Java→JNI→native→Java 왕복, JNIEnv non-null, 64-bit 포인터가 모두 PASS였습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

이 결과는 x86_64 AVD의 ABI 계약을 검증합니다. ARM64 PAC/BTI와 벤더 라이브러리 로딩 동작은 별도 ARM64 가상 이미지나 공개 빌드 산출물이 필요합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Android JNI tips](https://developer.android.com/ndk/guides/jni-tips)
- [Android NDK concepts](https://developer.android.com/ndk/guides/concepts)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

JNI는 단순 함수 호출이 아니라 런타임·링커·ABI·메모리 수명 계약이 만나는 신뢰 경계입니다.