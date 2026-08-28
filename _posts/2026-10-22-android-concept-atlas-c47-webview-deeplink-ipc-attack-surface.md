---
layout: post
title: "Android Security Concept Atlas C47 | 가상 실습 보고서 — WebView·딥링크·IPC 공격면, URI를 권한 있는 행동으로 바꾸기 전의 검증"
date: 2026-10-22 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, C47, WebView, DeepLink, URI, AppLinks, IPC]
excerpt: "딥링크와 WebView는 웹의 문자열을 앱 내부 탐색·인증·파일·IPC 동작으로 바꾸는 경계입니다. 문자열 startsWith 검사는 URL 문법을 이해하지 못하므로 scheme과 정확한 host를 파싱한 뒤 허용해야 합니다."
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: C47 · **Tier 8** · **선수 개념**: C11, C21, C46
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | https://example.com/account만 ALLOW됐고 http, example.com.evil.test, javascript scheme은 모두 DENY됐습니다. 네 테스트의 기대 결과가 일치해 result=PASS였습니다. |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![C47 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/evidence-uri.png)

## 1. 왜 이 개념이 필요한가

딥링크와 WebView는 웹의 문자열을 앱 내부 탐색·인증·파일·IPC 동작으로 바꾸는 경계입니다. 문자열 startsWith 검사는 URL 문법을 이해하지 못하므로 scheme과 정확한 host를 파싱한 뒤 허용해야 합니다.

## 2. Android 구조에서의 위치와 신뢰 경계

외부 Intent가 exported 컴포넌트에 도착하고, 앱은 Uri를 파싱해 내부 라우트 또는 WebView로 전달합니다. 인증 상태와 객체 소유권 검사는 링크 검증과 별개이며 둘 다 통과해야 합니다.

## 3. 정상 동작 흐름

1. Uri.parse로 구조를 분리한다.
2. https 같은 허용 scheme을 확인한다.
3. 정확한 host 또는 검증된 하위 도메인을 비교한다.
4. 인증·인가·내부 라우트 allowlist를 통과한 뒤에만 실행한다.

## 4. 실패가 보안 문제로 이어지는 조건

example.com.evil.test를 suffix/contains로 허용하거나 javascript·content scheme을 놓치면 피싱, 세션 악용, 로컬 파일 노출, JavaScript bridge 오용으로 이어질 수 있습니다.

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section uri
~~~

### 관측 결과

https://example.com/account만 ALLOW됐고 http, example.com.evil.test, javascript scheme은 모두 DENY됐습니다. 네 테스트의 기대 결과가 일치해 result=PASS였습니다.

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

교육용 allowlist 검사이며 실제 WebView를 외부 사이트에 연결하거나 JavaScript bridge를 노출하지 않았습니다. 운영 앱은 App Links 검증과 서버 리다이렉트 정책도 확인해야 합니다.

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

- [Unsafe use of deep links](https://developer.android.com/privacy-and-security/risks/unsafe-use-of-deeplinks)
- [WebView unsafe URI loading](https://developer.android.com/privacy-and-security/risks/unsafe-uri-loading)

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

URI는 문자열이 아니라 구조화된 비신뢰 입력입니다. scheme·host·상태·권한을 독립적으로 확인한 뒤 행동으로 바꿔야 합니다.