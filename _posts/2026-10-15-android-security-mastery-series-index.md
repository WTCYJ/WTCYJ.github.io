---
layout: post
title: "Android Security Mastery 시리즈 목차"
date: 2026-10-15 09:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 시리즈목차, 로드맵, 학습기록]
excerpt: "Android 보안 실습·연구 시리즈의 목차다. 에뮬레이터에서 직접 돌려 캡처한 글만 링크를 걸어 두었고, 나머지 장은 실측을 마치는 대로 공개한다."
---

에뮬레이터와 직접 만든 앱으로 돌려 본 결과를 바탕으로 쓰는 Android 보안 시리즈다. 개념 쪽 바탕은 [Android Security Concept Atlas](/posts/android-concept-atlas-index/)에 정리해 두었다. 링크가 걸린 장은 실측과 캡처, 검토까지 마친 글이다. 링크가 없는 장은 지금 실측을 다시 하고 있어서 잠시 내려 두었다.

## 1부 · Android 보안 기술 실습

1. [Android 연구용 에뮬레이터 — 빌드 타입과 ABI가 가르는 것](/posts/android-lab-p1c01-research-environment/)
2. [adb·logcat·dumpsys 증적 수집 — 링 버퍼가 덮어쓰기 전에](/posts/android-lab-p1c02-adb-evidence-collection/)
3. [APK triage — META-INF에 있는데 false로 찍힌 v1 서명](/posts/android-lab-p1c03-apk-triage/)
4. [jadx 정적 분석 — 난독화된 이름과 복원에 실패한 메서드](/posts/android-lab-p1c04-jadx-static-analysis/)
5. [apktool과 smali — 다시 조립해도 명령은 그대로](/posts/android-lab-p1c05-apktool-smali/)
6. [매니페스트 공격 표면 매핑 — exported만 세면 놓치는 것들](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)
7. [APK 재서명과 zipalign — 서명 뒤 정렬은 서명 블록을 버린다](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)
8. [Frida spawn·attach와 Java 훅 — 붙는 시점과 훅이 새는 길](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)
9. [ClassLoader와 동적 로딩 — 패커가 ART에 넘기는 dex를 입구에서 꺼내기](/posts/android-lab-p1c09-classloader-dynamic-loading/)
10. [JNI·native 함수 동적 관찰 — 스트립된 함수를 RegisterNatives로 찾기](/posts/android-lab-p1c10-jni-native-observation/)
11. [mitmproxy 로컬 인터셉션 — 유저 CA가 막히는 곳, 핀이 막는 곳](/posts/android-lab-p1c11-burp-mitmproxy-intercept/)
12. [Network Security Config 분석 — 정적으로 만든 호스트 표를 기기에서 맞춰 보기](/posts/android-lab-p1c12-network-security-config/)
13. [저장소·로그·클립보드·백업 점검 — 토큰이 앱 밖으로 나가는 길](/posts/android-lab-p1c13-storage-log-clipboard-backup/)
14. [Keystore와 BiometricPrompt — 콜백을 속여도 열리지 않는 키](/posts/android-lab-p1c14-keystore-biometricprompt/)
15. [Activity·Intent 주입 실습 — 중첩 Intent가 exported 경계를 넘는 길](/posts/android-lab-p1c15-activity-intent-injection/)
16. [BroadcastReceiver와 ordered broadcast 실습 — 남의 앱이 결과를 고쳐 쓰는 길](/posts/android-lab-p1c16-broadcastreceiver-ordered-broadcast/)
17. [Service·Messenger·AIDL 실습 — 호출자 UID를 읽는 자리](/posts/android-lab-p1c17-service-messenger-aidl/)
18. [ContentProvider·FileProvider 실습 — 열린 provider와 문자열 접두사 검사](/posts/android-lab-p1c18-contentprovider-fileprovider/)
19. [PendingIntent와 URI grant — 피해자 이름으로 발급된 읽기 권한](/posts/android-lab-p1c19-pendingintent-uri-grant/)
20. [딥링크·App Link·WebView — 콜백 가로채기와 JS 브리지 실측](/posts/android-lab-p1c20-deeplink-applink-webview/)
21. [Ghidra·Rizin native 분석 — 스트립된 JNI 표를 파일에서 읽기](/posts/android-lab-p1c21-ghidra-rizin-native/)
22. [ASan·IntSan으로 JNI 버그 읽기 — 섀도 바이트에서 tombstone까지](/posts/android-lab-p1c22-sanitizer-jni-analysis/)
23. [Flutter·React Native·Cordova — 로직이 DEX 밖에 있는 앱](/posts/android-lab-p1c23-flutter-reactnative-cordova/)
24. [MobSF 결과 손으로 검증하기 — 정답을 아는 앱으로 오탐과 미탐 가르기](/posts/android-lab-p1c24/)
25. Semgrep·CodeQL·Androguard 커스텀 규칙 작성: 데이터플로우 taint로 프로젝트 고유 결함 잡기
26. MASVS 요구사항을 MASTG 검증 절차로: 커버리지 매트릭스로 감사 재현하기
27. 방어 회귀 테스트 — WorkSource의 4바이트를 취약 이미지에서 먼저 빨갛게
28. 최종 종합 보안 감사 리포트: 증적·CVSS 심각도·책임공개 타임라인 통합

## 2부 · Android 전문 기술

1. [Kotlin 코루틴과 structured concurrency — 취소를 삼키는 catch](/posts/android-expert-p2c01/)
2. Flow·StateFlow·lifecycle
3. Jetpack Compose state·recomposition
4. ViewModel·SavedState·process death
5. Room·DataStore·WorkManager
6. OkHttp/Retrofit·모바일 API 설계
7. Gradle·multi-module·공급망
8. ART interpreter/JIT/AOT/dex2oat
9. ClassLoader·dynamic code loading
10. AMS·ActivityTaskManagerService
11. PackageManagerService·설치/서명 검증
12. PermissionManagerService·AppOpsService
13. WindowManagerService·UI 보안
14. Binder proxy/stub·thread pool
15. Stable AIDL·Java/NDK/Rust backend
16. HAL·VINTF·VTS
17. AOSP repo·Android.bp·Soong
18. Cuttlefish·GSI·userdebug build
19. init rc·property service·SELinux policy
20. bionic·linker·ELF·JNI
21. Perfetto·simpleperf·관측
22. CTS·VTS·STS
23. APEX·Mainline·모듈 업데이트
24. KeyMint·TEE·Gatekeeper·Weaver

## 3부 · Root Cause Analysis

1. Symptom/Trigger/Fault Site/Root Cause 구분
2. Security Invariant 작성법
3. call graph·data-flow
4. state machine·causal graph
5. baseline·patched·negative control — 재현을 인과로 바꾸는 세 대조
6. 최소 재현·입력 축소
7. crash와 exploitability 구분 — 크래시는 증상이지 취약점이 아니다
8. Java exception·logic bug RCA
9. Binder caller identity 오류 RCA
10. Parcel read/write mismatch RCA
11. [정수 오버플로·절단 RCA — UBSan과 ASan이 가리킨 서로 다른 줄](/posts/android-rca-p3c11/)
12. OOB·buffer size RCA
13. UAF·object lifetime RCA
14. race·TOCTOU RCA
15. resource exhaustion·DoS RCA
16. patch diff·Patch Invariant
17. 불완전 패치·variant analysis
18. regression으로 되살아난 취약점
19. 증거 등급·Confidence
20. 제출 가능한 RCA 보고서

## 4부 · Android 심화 취약점 연구

1. AOSP 소스 트리·대상 선정
2. git log/blame/tag·패치 계보
3. Security Bulletin·patch provenance
4. API level/SPL/실제 코드 불일치
5. System Service 공격 표면
6. Binder/AIDL service fuzzing
7. Parser용 libFuzzer harness
8. corpus·dictionary·coverage
9. crash dedup·minimization
10. sanitizer 기반 native 연구
11. compatibility layer·중복 구현 버그
12. SELinux policy·service_contexts 감사
13. HAL·vendor boundary
14. 이미지 baseline/patched 비교
15. patch-gap·backport 누락 — SPL이 약속한 패치와 이미지에 실제로 있는 코드
16. semantic patch·정적 규칙
17. sibling variant hunting
18. 보안 패치 회귀 검증
19. 새 완화기법 평가
20. 보고·수정안·공개 타임라인

## 5부 · Android 해킹 기법

1. APK 정찰·공격 표면 우선순위
2. 리패키징·서명 변경
3. exported Activity 직접 호출
4. Intent injection·redirection
5. implicit Intent hijacking
6. BroadcastReceiver 노출·결과 조작
7. Service·Messenger·AIDL 오용
8. PendingIntent mutability·권한 위임
9. ContentProvider query·권한 오류
10. FileProvider path 오류
11. Deep Link·URI parser 혼동
12. WebView JS bridge·origin
13. 로컬 인증 우회·서버 인가
14. 저장소·로그·백업 노출
15. TLS 신뢰·pinning 한계
16. 모바일 API BOLA/IDOR
17. Frida 기반 로직 관찰
18. 난독화·분석 방해 원리
19. JNI/native memory bug
20. Binder·Framework logic flaw
21. 공격 체인 전제조건
22. 탐지·수정·회귀
