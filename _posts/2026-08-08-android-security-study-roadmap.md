---
layout: post
title: "Android 보안·취약점 분석 24주 학습 로드맵 — 환경 구성부터 CVE 재현 프로토콜까지"
date: 2026-08-08
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 학습로드맵, AOSP, Cuttlefish, OWASP, MASTG, MASVS, CVE, SecurityBulletin, Frida, jadx, apktool, MobSF, adb, 에뮬레이터, SELinux, VerifiedBoot, Binder, 취약점분석, 정적분석, 동적분석]
excerpt: "Android 앱 보안 분석부터 공개 CVE의 패치 전·후 비교까지 24주로 끊어 설계한 학습 계획입니다. 앱 실습용 Windows 에뮬레이터 환경과 시스템 연구용 Linux/KVM Cuttlefish 환경을 분리한 이유, 공격 성공이 아니라 안전한 관찰 지표로 취약성을 입증하는 CVE 재현 프로토콜, 그리고 매 실험을 재현 가능하게 남기는 노트 템플릿을 정리했습니다."
---

> **성격**: 완료된 분석 기록이 아니라 **앞으로 24주간 따라갈 학습 계획**입니다. 진행하면서 이 글의 진행 기록 표를 갱신합니다.
> **범위**: 본인 소유의 에뮬레이터·테스트 기기·직접 작성한 앱, 또는 서면 허가를 받은 대상에만 적용합니다.
> **작성일**: 2026-08-08 · 권장 학습량 주 6~8시간 · 총 24주

---

## 0. 왜 계획부터 쓰는가

Android 보안은 "도구를 몇 개 설치했는가"로 진도가 나가지 않습니다. jadx로 APK를 열어보는 것과, 취약 조건을 가설로 세우고 최소한의 검증으로 확인한 뒤 수정과 회귀 검증까지 닫는 것은 완전히 다른 작업입니다. 후자를 습관으로 만들려면 순서와 기준선이 먼저 필요합니다.

또 하나, 앱 레벨 실습과 시스템/CVE 연구는 필요한 환경이 다릅니다. 앱 분석은 Windows + Android Emulator로 충분하지만, AOSP 코드와 패치 커밋을 놓고 패치 전·후 이미지를 비교하려면 KVM을 지원하는 Linux 호스트와 Cuttlefish가 필요합니다. 이 둘을 섞으면 실험 조건이 오염되므로 처음부터 분리해서 설계했습니다.

---

## 1. 도달 목표

24주 뒤 다음을 할 수 있는 상태를 목표로 합니다.

1. Android의 앱 샌드박스, UID, 권한, SELinux, Verified Boot, Binder의 역할을 설명한다.
2. APK를 정적·동적으로 분석해 저장소, 컴포넌트 노출, 네트워크, 인증 흐름의 보안 문제를 검증한다.
3. Android Emulator에서 취약 앱을 재현하고, 수정 후 같은 절차로 회귀 검증한다.
4. Android Security Bulletin에서 공개 CVE와 AOSP 패치를 추적하고, **비파괴적인 관찰 방식**으로 패치 전·후 동작을 비교한다.
5. 재현 조건, 증거, 영향, 수정 검증, 한계를 갖춘 보안 분석 보고서를 작성한다.

Android는 앱마다 Linux UID 기반 샌드박스를 두고, SELinux·seccomp 등으로 앱과 시스템의 경계를 강화합니다. 시스템 보안 연구를 하려면 이 경계를 먼저 이해해야 합니다. [AOSP Application Sandbox](https://source.android.com/docs/security/app-sandbox), [AOSP System and Kernel Security](https://source.android.com/docs/security/overview/kernel-security)

---

## 2. 안전·합법성 운영 원칙

가장 먼저 못 박아두는 부분입니다. 실습 대상과 금지 행위를 계획 단계에서 정해두지 않으면, 흥미로운 발견이 나왔을 때 선을 넘기 쉽습니다.

### 허용 범위

- 내가 만든 앱, 오픈소스 훈련 앱, CTF/버그바운티의 명시적 범위
- 로컬 Android Emulator 또는 고립된 Cuttlefish 가상 기기
- 별도 테스트 계정, 더미 데이터, 전용 테스트 Wi-Fi/가상 네트워크
- 공개 CVE의 패치 전·후 코드와 가상 빌드를 비교하는 비파괴적 재현

### 금지 범위

- 동의 없는 상용 앱·서버·기기·계정 테스트
- 실제 전화번호, 개인정보, 회사 계정, 주력 Google 계정을 실습 환경에 연결
- 권한 상승, 원격 코드 실행, 부트 체인 우회, 라디오/모뎀/벤더 드라이버 취약점의 공격 재현을 실제 기기에서 수행
- 패치 우회 수단이나 무기화 가능한 익스플로잇을 공유·자동화·배포

### 기본 습관

- 실습 전 스냅샷 생성, 실습 후 초기 상태로 복구한다.
- 실험마다 대상·버전·해시·실행 일시·관찰 결과를 기록한다.
- 프록시는 내 에뮬레이터와 내가 만든 로컬 테스트 서버 사이에만 둔다.
- 도구 결과는 결론이 아니다. OWASP도 자동화 도구 결과에는 오탐·미탐이 있을 수 있다고 명시합니다. [OWASP MASTG Testing Tools](https://mas.owasp.org/MASTG/tools/)

---

## 3. 실습 환경 구성

### 단계 A — 앱 보안 실습 환경 (처음 12주)

Windows PC에서 구축합니다. 실제 폰은 필요 없고 Android Emulator가 우선입니다.

| 구성 | 권장 역할 | 운영 원칙 |
| --- | --- | --- |
| Android Studio + Android SDK | 앱 작성·빌드·디버깅 | 최신 API AVD와 구버전 API AVD를 별도로 둔다. |
| Android Emulator / AVD | 안전한 Android 실행 대상 | 실습별 AVD 스냅샷을 만들고 끝나면 복구한다. |
| Android Platform Tools (`adb`) | 설치, 로그, 파일·프로세스 관찰 | 연결 대상을 항상 에뮬레이터 시리얼로 명시한다. |
| JADX | DEX 코드·리소스 읽기 | 소스가 공개됐거나 허가된 APK에만 사용한다. |
| apktool | 매니페스트·리소스 구조 확인 | 원본과 디코드 결과의 해시/버전을 기록한다. |
| MobSF | 정적/동적 분석 체크리스트 보조 | 로컬 컨테이너에서 실행하고 결과를 수동 검증한다. |
| Burp Suite Community 또는 OWASP ZAP | 내 테스트 앱의 HTTP(S) 흐름 관찰 | 외부 서비스가 아닌 로컬 백엔드만 대상으로 한다. |
| Frida / Objection | 내 앱 또는 훈련 앱의 런타임 관찰 | 초기에는 API 호출·값 흐름 관찰에만 사용한다. |

Android Emulator는 실제 기기 없이 앱을 개발·테스트할 수 있는 공식 가상 기기이며, `adb`로 설치와 테스트를 수행할 수 있습니다. [Android Emulator 명령행 문서](https://developer.android.com/studio/run/emulator-commandline)

### 단계 B — Android 시스템/CVE 연구 환경 (13주차 이후)

Windows의 앱 실습 환경과 분리해, **KVM을 지원하는 Linux 호스트**에 구축합니다. 시스템 CVE 재현은 Android Emulator보다 AOSP Cuttlefish가 적합합니다. Cuttlefish는 AOSP 가상 기기이며, 공식 문서상 가상화(KVM)가 필요합니다. [Cuttlefish 시작하기](https://source.android.com/docs/devices/cuttlefish/get-started)

| 구성 | 목적 |
| --- | --- |
| Linux 호스트 + KVM | AOSP/Cuttlefish 구동. 개인 메인 PC와 분리된 환경 권장. |
| AOSP 소스 트리 | 취약 버전·패치 버전의 코드 차이와 빌드 산출물 비교. |
| Cuttlefish `userdebug` 인스턴스 2개 | `baseline`(패치 전), `patched`(패치 후) 비교. |
| 전용 로컬 네트워크 | 실습 장비 외 통신을 막고, 필요한 경우 로컬 테스트 서버만 연결. |
| Git 저장소 + 실험 노트 | 패치 커밋, 빌드 설정, 관찰 결과, 재현성을 보관. |

두 환경의 데이터 흐름은 다음과 같이 완전히 분리합니다.

```text
[단계 A]  Windows — 앱 보안 실습
    Android Studio
          │
          ▼
    Android Emulator (AVD)  ◄── JADX · apktool · MobSF · Frida
          │
          ▼
       로컬 프록시
          │
          ▼
     내 로컬 테스트 API


[단계 B]  Linux + KVM — 시스템 / CVE 연구 (물리적으로 분리)
    AOSP 소스 트리 · 패치 커밋
          │
          ├──► Cuttlefish : baseline (패치 전) ──┐
          │                                      ├──► 로그 · 테스트 결과 · diff
          └──► Cuttlefish : patched  (패치 후) ──┘
```

### 환경 체크리스트

- ☐ 앱 실습 AVD: `clean` 스냅샷 생성
- ☐ 앱 실습 AVD: `instrumented` 스냅샷 생성
- ☐ 테스트용 Google 계정 또는 계정 미사용 원칙 결정
- ☐ 로컬 테스트 API의 더미 데이터 준비
- ☐ 실습 폴더에 날짜별 `notes`, `evidence`, `artifacts` 구조 생성
- ☐ 시스템 연구용 Linux/KVM 장비를 메인 업무·개인 데이터와 분리
- ☐ Cuttlefish baseline/patched 두 인스턴스와 초기화 절차 문서화

---

## 4. 24주 커리큘럼

| 기간 | 학습 주제 | 실습과 산출물 |
| --- | --- | --- |
| 1~2주 | Android 구조 | APK, DEX, Manifest, 앱 수명주기, UID·권한·Sandbox를 노트로 정리한다. |
| 3~4주 | Android 앱 개발 기초 | Kotlin으로 로그인·메모·파일 업로드 기능이 있는 **내 테스트 앱**을 작성한다. |
| 5~6주 | 정적 분석 | 내 앱 APK를 JADX/apktool로 분석하여 Manifest, 문자열, 저장소, 네트워크 구성을 표로 만든다. |
| 7~8주 | 동적 분석 | `adb logcat`, debugger, 프록시로 내 앱의 실행·요청·오류 흐름을 관찰한다. |
| 9~10주 | 취약점 유형 | 컴포넌트 노출, 민감정보 저장, 인증·세션, WebView/딥링크, TLS, 암호 사용을 각각 점검한다. |
| 11~12주 | 미니 모의진단 | 훈련 앱 하나를 MASTG 기준으로 진단하고 3~5쪽 보고서를 작성한다. |
| 13~14주 | 네이티브·런타임 기초 | JNI, ELF, 심볼, 앱 디버깅, 난독화가 분석에 미치는 영향을 학습한다. |
| 15~16주 | Android 시스템 보안 | Binder, system service, SELinux, Verified Boot, 보안 패치 수준을 학습한다. |
| 17주 | Cuttlefish 실습 | Linux/KVM에서 Cuttlefish를 띄우고 `adb` 연결·초기화·로그 수집을 자동화한다. |
| 18주 | CVE 선정·사전 조사 | Android Security Bulletin의 공개 CVE 하나를 선택하고 영향·버전·패치 링크를 표로 만든다. |
| 19~20주 | 패치 전·후 빌드 | AOSP 태그와 패치 커밋을 기준으로 baseline/patched 이미지를 준비한다. 빌드 재현 기록을 남긴다. |
| 21주 | 안전한 검증 | 로그·예외·테스트 결과·코드 경로로 차이를 검증한다. 파괴적 페이로드는 사용하지 않는다. |
| 22주 | 근본 원인 분석 | 패치 diff와 호출 흐름을 읽고 취약 조건·보안 경계·수정 원리를 설명한다. |
| 23~24주 | 최종 연구 보고서 | 재현성, 영향, 증거, 패치 검증, 한계, 완화책을 포함한 최종 보고서를 작성한다. |

학습의 기준점은 OWASP MAS 프로젝트의 MASTG와 MASVS를 사용합니다. MASTG는 Android 보안 기초, 테스트 케이스, 역공학·변조 방지까지 다룹니다. [OWASP MASTG 개요](https://mas.owasp.org/MASTG/0x03-Overview/)

---

## 5. 앱 취약점 분석 실습 순서

훈련 앱 또는 내가 만든 앱에 다음 순서로 적용합니다. 각 항목은 취약점을 "발견"하는 데서 멈추지 않고, 수정과 재검증까지 완료합니다.

1. **대상 식별**: 앱 이름, 패키지, 버전, APK SHA-256, 허가 범위를 기록한다.
2. **정적 분석**: `AndroidManifest.xml`, exported 컴포넌트, 권한, 딥링크, URL, API 키 흔적, 저장소 API, WebView 설정을 확인한다.
3. **실행 관찰**: 앱의 정상 기능을 먼저 실행해 사용자 흐름·서버 요청·로컬 파일·로그의 기준선을 만든다.
4. **가설 설정**: "이 Activity가 외부에서 불필요하게 호출될 수 있는가?", "토큰이 보호되지 않은 저장소에 남는가?"처럼 검증 가능한 한 문장으로 쓴다.
5. **최소 검증**: 피해를 만들지 않는 입력과 관찰로 가설을 확인한다. 필요 이상으로 우회·변조하지 않는다.
6. **수정**: 최소 권한, 비공개 컴포넌트, 안전한 저장소, 서버 측 검증, 입력 검증 등으로 원인을 제거한다.
7. **회귀 검증**: 동일한 테스트로 더 이상 문제가 재현되지 않는지 확인하고 정상 기능도 테스트한다.

3번의 "정상 흐름 기준선"이 실제로는 가장 자주 생략되는 단계입니다. 기준선 없이 이상 동작을 관찰하면 그게 취약점 때문인지 원래 그런 앱인지 구분할 수 없습니다.

### 초반에 다룰 분석 주제

- 컴포넌트 노출: Activity, Service, Receiver, Provider, Intent, deeplink
- 저장소: SharedPreferences, 파일, SQLite/Room, 백업 설정, 로그
- 인증·인가: 클라이언트 신뢰 금지, 토큰 수명, 서버 측 권한 검증
- 네트워크: 평문 통신, 인증서 검증, 민감정보 전송, 오류 메시지
- WebView: 외부 URL 입력, JavaScript bridge, 파일 접근, URL 검증
- 암호: 키 하드코딩, 약한 난수, 잘못된 암호 모드, Android Keystore 사용
- 공급망: 의존성 버전, 오래된 SDK, 비밀값이 포함된 빌드 설정

수정 단계의 기준은 Google의 [Android Security Checklist](https://developer.android.com/privacy-and-security/security-tips)와 [앱 보안 권장 사항](https://developer.android.com/privacy-and-security/security-best-practices)을 사용합니다.

---

## 6. CVE 재현·분석 프로토콜

### 6.1 첫 CVE의 선정 기준

처음에는 아래 조건을 **모두** 만족하는 공개 CVE만 선택합니다.

- Android Security Bulletin에 공개되어 있고, AOSP 패치 링크가 존재한다.
- 영향이 문서화되어 있으며 재현에 실제 사용자 데이터·외부 서비스·물리 장치가 필요하지 않다.
- Cuttlefish 또는 AOSP `userdebug` 이미지에서 관찰 가능한 Android framework/system component 관련 이슈다.
- 우선순위는 DoS·입력 검증·권한 검사·정보 노출처럼 비파괴적으로 확인 가능한 유형이다.
- RCE, EoP, 부트로더, baseband, vendor driver, hardware 경로는 충분한 연구 경험과 명시적 권한을 갖춘 뒤에만 다룬다.

Android Security Bulletin은 Android 기기에 영향을 줄 수 있는 이슈의 수정 사항을 제공하고, 항목별 CVE·심각도·패치된 AOSP 버전 및 참조를 제공합니다. [Android Security Bulletins](https://source.android.com/docs/security/bulletin/asb-overview)

### 6.2 재현 절차

1. **조사 카드 작성**
   CVE ID, Bulletin URL, 영향을 받는 버전, 보안 패치 수준, 컴포넌트, AOSP patch commit, 공개 분석 자료, 허용한 관찰 지표를 적는다.

2. **가설 정의**
   예: "특정 입력 검증 누락이 패치 전 이미지에서 예외/정책 위반을 유발하지만, 패치 후에는 거부 또는 안전하게 처리된다."
   권한 상승이나 데이터 탈취를 목표로 정의하지 않는다.

3. **동일 조건의 두 이미지 준비**
   동일한 장치 프로필·설정으로 `baseline`과 `patched` Cuttlefish를 만들고, 차이는 패치 유무만 남긴다.

4. **관찰 가능한 테스트 작성**
   안전한 입력, 단위/통합 테스트, logcat, tombstone, 서비스 상태, 반환 코드 등을 증거로 정한다. 테스트는 최대한 작은 범위로 만든다.

5. **baseline 실행 및 증거 보관**
   스냅샷에서 시작해 테스트 1회만 수행한다. 출력, 로그, 빌드 지문, 실행 시각을 보관한다.

6. **patched 실행 및 비교**
   동일 테스트·동일 설정으로 실행한다. 기대된 보안 검사가 동작하고 부작용이 없는지 확인한다.

7. **코드 중심 근본 원인 분석**
   패치 전/후 diff → 호출 위치 → 신뢰 경계 → 검증 누락 또는 수명 관리 오류 → 수정 논리 순으로 설명한다.

8. **초기화 및 정리**
   가상 기기를 powerwash/스냅샷 복구하고, 생성한 테스트 데이터와 로그의 민감정보 유무를 점검한다. Cuttlefish는 실험 절차 간 독립성을 위해 초기 상태로 재설정하는 방식을 제공합니다. [Cuttlefish 재시작·초기화](https://source.android.com/docs/devices/cuttlefish/restart)

### 6.3 성공 기준

- 패치 전과 후가 **동일한 실험 조건**에서 비교되었다.
- 취약성의 존재를 공격 성공이 아니라 안전한 관찰 지표로 입증했다.
- 코드 diff가 관찰 결과를 설명한다.
- 패치 후에는 문제 조건이 사라지고 정상 동작을 해치지 않는다.
- 제3자가 내 기록만으로 환경을 재구축하고 결과를 검증할 수 있다.

마지막 항목이 사실상 전부입니다. "내 환경에서만 되는 재현"은 분석이 아니라 일화입니다.

---

## 7. 연구 노트와 보고서 템플릿

### 실험 노트 (매회)

```text
제목:
날짜 / 연구자:
허가 범위:
대상: 앱/이미지 이름, 패키지·빌드 지문, SHA-256
환경: OS, Android API, AVD/Cuttlefish 설정, 네트워크 격리 상태
가설:
절차: 정상 동작 → 최소 검증 → 관찰
결과: 성공/실패, 로그·스크린샷·테스트 출력 위치
영향: 실습 환경에서 확인한 사실만 기록
수정/패치 검증:
한계 및 다음 실험:
초기화 완료 여부:
```

### 최종 취약점 분석 보고서 목차

1. 요약과 허가 범위
2. 대상·버전·실험 환경
3. 위협 모델과 보안 경계
4. 취약점/CVE 개요 및 영향 범위
5. 재현 조건과 안전한 검증 방법
6. 증거: 로그, 테스트 결과, 패치 전·후 비교표
7. 근본 원인: 코드 경로와 patch diff 설명
8. 수정/완화책과 재검증 결과
9. 한계, 재현성, 정리 절차
10. 참고자료와 변경 이력

---

## 8. 첫 7일 계획

### Day 1 — 범위와 폴더

- Android Studio와 최신 Android Emulator를 설치한다.
- `android-security-study/` 아래에 `notes/`, `evidence/`, `apps/`, `cve/` 폴더를 만든다.
- "내 앱과 공식 훈련 앱만 테스트한다"는 범위 문서를 5줄로 작성한다.

### Day 2 — Emulator와 `adb`

- 최신 API AVD 1개, 구버전 API AVD 1개를 만든다.
- 각각 `clean` 스냅샷을 만들고, `adb devices`, 앱 설치, logcat 수집을 연습한다.

### Day 3 — 작은 테스트 앱 작성

- Kotlin으로 로그인 화면과 메모 저장 화면을 구현한다.
- 네트워크는 가능하면 로컬 테스트 API 또는 mock 응답으로 시작한다.

### Day 4 — APK 읽기

- 내 앱의 debug APK를 JADX와 apktool로 열고 Manifest·문자열·저장소 호출 위치를 찾는다.
- 찾은 항목을 표로 정리한다.

### Day 5 — 정상 흐름 캡처

- 로그인·메모 작성·로그아웃을 정상 실행하고 logcat과 네트워크 흐름을 보관한다.

### Day 6 — 한 가지 방어 개선

- 예: 불필요한 exported 컴포넌트를 비공개로 바꾸거나, 민감한 값을 로그에 남기지 않도록 고친다.
- 수정 전/후를 다시 분석한다.

### Day 7 — 첫 미니 보고서

- 위 템플릿으로 1~2쪽 보고서를 작성한다.
- 핵심은 "어떤 도구를 썼나"가 아니라 "무엇을 관찰했고, 왜 문제이며, 어떻게 고쳤나"이다.

---

## 9. 진행 기록

진행하면서 이 표를 갱신합니다. 상세 기록은 구간별 글로 정리합니다 → [1~4주차](/posts/android-security-study-week1-4/) · [5~6주차](/posts/android-security-study-week5-6/)

| 구간 | 상태 | 갱신일 | 비고 |
| --- | --- | --- | --- |
| 환경 구성 (단계 A) | **완료** | 2026-08-08 | AVD `sec-api33`/`sec-api36`, `clean` 스냅샷, JBR 21 고정 |
| 1~2주 Android 구조 | **완료** | 2026-08-08 | DEX 헤더 실측 디코딩, UID/SELinux 두 겹 격리 확인 |
| 3~4주 테스트 앱 작성 | **완료** | 2026-08-08 | `kr.wtcy.memovault` (로그인·메모·파일 업로드), 약점 10개 배치 |
| 5~6주 정적 분석 | **완료** | 2026-08-09 | 표 9종 생성, 심어둔 약점 10개 중 7개 자동 탐지 |
| 7~8주 동적 분석 | 시작 전 | — | |
| 9~10주 취약점 유형 | 시작 전 | — | |
| 11~12주 미니 모의진단 | 시작 전 | — | |
| 13~14주 네이티브·런타임 | 시작 전 | — | |
| 15~16주 시스템 보안 | 시작 전 | — | |
| 환경 구성 (단계 B) | 시작 전 | — | Linux/KVM · Cuttlefish 2 인스턴스 |
| 17주 Cuttlefish 실습 | 시작 전 | — | |
| 18주 CVE 선정 | 시작 전 | — | |
| 19~20주 패치 전·후 빌드 | 시작 전 | — | |
| 21~22주 검증·근본 원인 | 시작 전 | — | |
| 23~24주 최종 보고서 | 시작 전 | — | |

---

## 10. 다음 단계 판단 기준

다음 단계로 넘어가도 되는 시점은 도구를 많이 설치했을 때가 아니라, 아래를 독립적으로 해냈을 때입니다.

- ☐ APK 하나를 정적 분석하고 Manifest·저장소·네트워크·컴포넌트 표를 만들 수 있다.
- ☐ 정상 동작의 기준선을 만든 뒤 최소 검증으로 가설을 확인할 수 있다.
- ☐ 문제를 수정하고 같은 테스트로 재발하지 않음을 보일 수 있다.
- ☐ 스냅샷·빌드 지문·로그를 이용해 실험을 재현할 수 있다.
- ☐ 공개 CVE 하나에 대해 "취약 조건 → 보안 경계 → 패치의 원리 → 패치 후 관찰"을 설명할 수 있다.

이 기준을 충족한 뒤에야 네이티브 라이브러리, Binder/system service, AOSP 코드 감사, 고급 CVE 연구로 확장합니다. 속도보다 재현성, 공격 성공보다 분석의 정확성을 우선합니다.

---

## 참고 자료

- [OWASP Mobile Application Security Testing Guide (MASTG)](https://mas.owasp.org/MASTG/0x03-Overview/) — 모바일 보안 테스트 방법론과 Android 테스트 항목
- [OWASP MASTG 도구 목록](https://mas.owasp.org/MASTG/tools/) — 정적·동적·네트워크 분석 도구를 테스트 항목과 연결해 볼 수 있음
- [OWASP MASTG Reference Applications](https://mas.owasp.org/MASTG/apps/) — 공식 훈련용 앱/크랙미 목록. MAS 프로젝트가 유지·테스트하는 항목을 우선 사용
- [Android Developers: Security Best Practices](https://developer.android.com/privacy-and-security/security-best-practices) — 앱 수정·방어 단계의 기준
- [AOSP Application Sandbox](https://source.android.com/docs/security/app-sandbox) — UID/SELinux 기반 앱 격리 이해
- [AOSP Verified Boot](https://source.android.com/docs/security/features/verifiedboot) — 부트 체인 무결성과 rollback protection 이해
- [Android Security Bulletins](https://source.android.com/docs/security/bulletin) — 공개 CVE와 AOSP 패치 추적의 출발점
- [AOSP Cuttlefish 시작하기](https://source.android.com/docs/devices/cuttlefish/get-started) — 시스템 연구용 가상 기기 환경
