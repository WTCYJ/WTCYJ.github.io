---
layout: post
title: "Android Security Mastery — 전체 시리즈 목차 (9개 분야)"
date: 2026-10-15 09:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 시리즈목차, 로드맵, 학습기록]
excerpt: "Android 애플리케이션 보안·프레임워크·AOSP·커널·악성코드·취약점 연구·과거 제로데이 사례를 9개 분야로 나눈 실습·연구 시리즈의 전체 목차다. 각 분야의 모든 장을 한 페이지에서 나눠 볼 수 있다."
---

이 페이지는 Android 보안 실습·연구 시리즈 **9개 분야 전체의 항해도**다. 각 분야(부)를 접어놓지 않고 한 페이지에서 나눠 볼 수 있게 정리했다. 완성된 글은 링크가 걸리고(✅), 계획된 장은 제목만 둔다(⬜).

이 시리즈는 [Android Security Concept Atlas](/posts/android-concept-atlas-index/)(56개 개념 지도)를 **선수 지식**으로 삼는다. 개념(Atlas)에서 배운 것을 여기서 도구·실습·연구·사례로 확장한다.

> **읽는 법**: 각 글은 보고서 형식(요약 → 배경 → 개념 → 실습/관측 → 방어 → 정리)이며, 관측/주장에 근거 등급(`Observed`/`Source-confirmed`/`Reported`/`Inferred`)을 붙이고, 실습에는 실측 스크린샷 자리를 둔다.

---

## 1부 — Android 보안 기술 실습 (28장)

취약한 교육용 앱과 수정 버전을 함께 쓰며, 공격 재현에서 끝내지 않고 방어와 회귀 테스트까지 다룬다.

1. [연구 환경 — 계측 가능한 에뮬레이터 고르기](/posts/android-lab-p1c01-research-environment/) ✅
2. [adb·logcat·dumpsys·pm·am 증적 수집](/posts/android-lab-p1c02-adb-evidence-collection/) ✅
3. [apksigner·aapt2·bundletool APK triage](/posts/android-lab-p1c03-apk-triage/) ✅
4. [jadx 기반 Java/Kotlin 정적 분석](/posts/android-lab-p1c04-jadx-static-analysis/) ✅
5. [apktool과 smali/baksmali 분석](/posts/android-lab-p1c05-apktool-smali/) ✅
6. [Manifest 공격 표면 자동 매핑](/posts/android-lab-p1c06-manifest-attack-surface-mapping/) ✅
7. [APK 수정·zipalign·재서명과 비교](/posts/android-lab-p1c07-apk-modify-zipalign-resign/) ✅
8. [Frida spawn/attach 및 Java hook](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/) ✅
9. [ClassLoader·reflection·dynamic loading 관찰](/posts/android-lab-p1c09-classloader-dynamic-loading/) ✅
10. [JNI와 native function 동적 관찰](/posts/android-lab-p1c10-jni-native-observation/) ✅
11. [Burp Suite/mitmproxy 로컬 실습](/posts/android-lab-p1c11-burp-mitmproxy-intercept/) ✅
12. [Network Security Config 분석](/posts/android-lab-p1c12-network-security-config/) ✅
13. [저장소·log·clipboard·backup 점검](/posts/android-lab-p1c13-storage-log-clipboard-backup/) ✅
14. [Keystore와 BiometricPrompt 검증](/posts/android-lab-p1c14-keystore-biometricprompt/) ✅
15. [Activity와 Intent injection 실습](/posts/android-lab-p1c15-activity-intent-injection/) ✅
16. [BroadcastReceiver와 ordered broadcast 실습](/posts/android-lab-p1c16-broadcastreceiver-ordered-broadcast/) ✅
17. [Service·Messenger·AIDL 실습](/posts/android-lab-p1c17-service-messenger-aidl/) ✅
18. [ContentProvider와 FileProvider 실습](/posts/android-lab-p1c18-contentprovider-fileprovider/) ✅
19. [PendingIntent와 URI grant 실습](/posts/android-lab-p1c19-pendingintent-uri-grant/) ✅
20. [Deep Link·App Link·WebView 실습](/posts/android-lab-p1c20-deeplink-applink-webview/) ✅
21. [Ghidra 또는 Rizin native 분석](/posts/android-lab-p1c21-ghidra-rizin-native/) ✅
22. [ASan/HWASan/UBSan JNI 오류 분석](/posts/android-lab-p1c22-sanitizer-jni-analysis/) ✅
23. [Flutter·React Native·Cordova 구조 비교](/posts/android-lab-p1c23-flutter-reactnative-cordova/) ✅
24. [MobSF 자동 스캔 결과의 수동 검증](/posts/android-lab-p1c24/) ✅
25. [Semgrep·CodeQL·Androguard 커스텀 규칙](/posts/android-lab-p1c25/) ✅
26. [MASVS 요구사항을 MASTG 검증 절차로](/posts/android-lab-p1c26/) ✅
27. [방어 회귀 테스트 설계](/posts/android-lab-p1c27/) ✅
28. [최종 종합 보안 감사 리포트](/posts/android-lab-p1c28/) ✅

## 2부 — Android 전문 기술 (24장)

개발자·플랫폼 내부·보안 세 관점으로 `App → Framework → Binder → system_server → HAL → Kernel` 흐름을 소스와 함께.

1. Kotlin·coroutine·structured concurrency ⬜ · 2. Flow·StateFlow·lifecycle ⬜ · 3. Jetpack Compose state·recomposition ⬜ · 4. ViewModel·SavedState·process death ⬜ · 5. Room·DataStore·WorkManager ⬜ · 6. OkHttp/Retrofit·모바일 API 설계 ⬜ · 7. Gradle·multi-module·공급망 ⬜ · 8. ART interpreter/JIT/AOT/dex2oat ⬜ · 9. ClassLoader·dynamic code loading ⬜ · 10. AMS·ActivityTaskManagerService ⬜ · 11. PackageManagerService·설치/서명 검증 ⬜ · 12. PermissionManagerService·AppOpsService ⬜ · 13. WindowManagerService·UI 보안 ⬜ · 14. Binder proxy/stub·thread pool ⬜ · 15. Stable AIDL·Java/NDK/Rust backend ⬜ · 16. HAL·VINTF·VTS ⬜ · 17. AOSP repo·Android.bp·Soong ⬜ · 18. Cuttlefish·GSI·userdebug build ⬜ · 19. init rc·property service·SELinux policy ⬜ · 20. bionic·linker·ELF·JNI ⬜ · 21. Perfetto·simpleperf·관측 ⬜ · 22. CTS·VTS·STS ⬜ · 23. APEX·Mainline·모듈 업데이트 ⬜ · 24. KeyMint·TEE·Gatekeeper·Weaver ⬜

## 3부 — Root Cause Analysis (20장)

CVE 재현 10편 위에 RCA 방법론을 형식화한다.

1. Symptom/Trigger/Fault Site/Root Cause 구분 ⬜ · 2. Security Invariant 작성법 ⬜ · 3. call graph·data-flow ⬜ · 4. state machine·causal graph ⬜ · 5. baseline·patched·negative control ⬜ · 6. 최소 재현·입력 축소 ⬜ · 7. crash와 exploitability 구분 ⬜ · 8. Java exception·logic bug RCA ⬜ · 9. Binder caller identity 오류 RCA ⬜ · 10. Parcel read/write mismatch RCA ⬜ · 11. integer overflow/underflow RCA ⬜ · 12. OOB·buffer size RCA ⬜ · 13. UAF·object lifetime RCA ⬜ · 14. race·TOCTOU RCA ⬜ · 15. resource exhaustion·DoS RCA ⬜ · 16. patch diff·Patch Invariant ⬜ · 17. 불완전 패치·variant analysis ⬜ · 18. regression으로 되살아난 취약점 ⬜ · 19. 증거 등급·Confidence ⬜ · 20. 제출 가능한 RCA 보고서 ⬜

## 4부 — Android 심화 취약점 연구 (20장)

공개 소스와 안전한 하네스로 AOSP 연구 워크플로를 세운다.

1. AOSP 소스 트리·대상 선정 ⬜ · 2. git log/blame/tag·패치 계보 ⬜ · 3. Security Bulletin·patch provenance ⬜ · 4. API level/SPL/실제 코드 불일치 ⬜ · 5. System Service 공격 표면 ⬜ · 6. Binder/AIDL service fuzzing ⬜ · 7. Parser용 libFuzzer harness ⬜ · 8. corpus·dictionary·coverage ⬜ · 9. crash dedup·minimization ⬜ · 10. sanitizer 기반 native 연구 ⬜ · 11. compatibility layer·중복 구현 버그 ⬜ · 12. SELinux policy·service_contexts 감사 ⬜ · 13. HAL·vendor boundary ⬜ · 14. 이미지 baseline/patched 비교 ⬜ · 15. patch-gap·backport 누락 ⬜ · 16. semantic patch·정적 규칙 ⬜ · 17. sibling variant hunting ⬜ · 18. 보안 패치 회귀 검증 ⬜ · 19. 새 완화기법 평가 ⬜ · 20. 보고·수정안·공개 타임라인 ⬜

## 5부 — Android 해킹 기법 (22장)

교육용 앱에서만 재현하는 공격·방어.

1. APK 정찰·공격 표면 우선순위 ⬜ · 2. 리패키징·서명 변경 ⬜ · 3. exported Activity 직접 호출 ⬜ · 4. Intent injection·redirection ⬜ · 5. implicit Intent hijacking ⬜ · 6. BroadcastReceiver 노출·결과 조작 ⬜ · 7. Service·Messenger·AIDL 오용 ⬜ · 8. PendingIntent mutability·권한 위임 ⬜ · 9. ContentProvider query·권한 오류 ⬜ · 10. FileProvider path 오류 ⬜ · 11. Deep Link·URI parser 혼동 ⬜ · 12. WebView JS bridge·origin ⬜ · 13. 로컬 인증 우회·서버 인가 ⬜ · 14. 저장소·로그·백업 노출 ⬜ · 15. TLS 신뢰·pinning 한계 ⬜ · 16. 모바일 API BOLA/IDOR ⬜ · 17. Frida 기반 로직 관찰 ⬜ · 18. 난독화·분석 방해 원리 ⬜ · 19. JNI/native memory bug ⬜ · 20. Binder·Framework logic flaw ⬜ · 21. 공격 체인 전제조건 ⬜ · 22. 탐지·수정·회귀 ⬜

## 6부 — Android 악성코드·바이러스 분석 (24장)

제작이 아닌 분석·탐지·대응. 시뮬레이터는 가짜 데이터·localhost만.

1. malware와 virus의 차이 ⬜ · 2. Trojan·spyware·stalkerware 분류 ⬜ · 3. banking malware·credential phishing ⬜ · 4. adware·click/SMS fraud ⬜ · 5. dropper·loader·backdoor 분석 ⬜ · 6. ransomware·destructive 탐지 ⬜ · 7. malicious SDK·supply-chain ⬜ · 8. Play Protect PHA 분류 ⬜ · 9. 안전한 APK intake·chain of custody ⬜ · 10. Manifest·permission·component triage ⬜ · 11. 문자열·URL·DEX·asset 정적 분석 ⬜ · 12. APKiD packer/protector 판별 ⬜ · 13. 난독화·reflection·dynamic loading 흔적 ⬜ · 14. JNI_OnLoad·native payload ⬜ · 15. 격리 emulator 동적 분석 ⬜ · 16. process·service·job·file 변화 ⬜ · 17. localhost 네트워크 행위 ⬜ · 18. MITRE ATT&CK Mobile 매핑 ⬜ · 19. IOC·IOA 작성 ⬜ · 20. YARA·정적 탐지 규칙 ⬜ · 21. MobSF 오탐 검증 ⬜ · 22. 사고 대응·사용자 안내 ⬜ · 23. synthetic behavior simulator ⬜ · 24. 최종 malware 분석 보고서 ⬜

## 7부 — Android Kernel Security (36장)

Cuttlefish/QEMU 우선. 실기기 flashing·fuzzing은 위험 설명 후 기본 과정에서 생략.

1. Linux·Android kernel 관계 ⬜ · 2. C pointer/integer·kernel memory ⬜ · 3. ARM64 EL0~EL3·syscall ⬜ · 4. mainline/LTS/android-mainline/ACK ⬜ · 5. GKI·KMI·vendor module ⬜ · 6. kernel branch·source 선택 ⬜ · 7. Bazel/Kleaf GKI build ⬜ · 8. Cuttlefish/QEMU kernel 부팅 ⬜ · 9. boot/vendor_boot/init_boot·ramdisk ⬜ · 10. DTB/DTBO·device tree ⬜ · 11. process·task_struct·credential ⬜ · 12. capability·namespace·cgroup·seccomp ⬜ · 13. LSM·SELinux hook ⬜ · 14. syscall·ioctl·user pointer ⬜ · 15. copy_from/to_user·usercopy ⬜ · 16. page table·allocator·SLUB ⬜ · 17. refcount·RCU·lifetime ⬜ · 18. spinlock·mutex·race·TOCTOU ⬜ · 19. character device·file_operations ⬜ · 20. Binder kernel driver 구조 ⬜ · 21. binder_proc/thread/node/ref/buffer ⬜ · 22. dma-buf·shared memory ⬜ · 23. media/BT/Wi-Fi/GPU driver 표면 ⬜ · 24. GKI/vendor module·symbol list ⬜ · 25. KMI ABI monitoring ⬜ · 26. hardening: KASLR/CFI/PAC/BTI/MTE ⬜ · 27. KASAN/KFENCE/KCSAN/UBSan ⬜ · 28. KCOV·kernel coverage ⬜ · 29. syzkaller·안전한 가상 퍼징 ⬜ · 30. kernel panic/oops·call trace ⬜ · 31. vmlinux·System.map·symbolication ⬜ · 32. kernel CVE patch analysis ⬜ · 33. patch-gap·vendor backport ⬜ · 34. KUnit/selftest·회귀 ⬜ · 35. 교육용 driver 프로젝트 ⬜ · 36. kernel vuln report·patch ⬜

## 8부 — Android/iOS 과거 제로데이 사례 연구 (50장)

패치·공개된 사례만. zero-day/n-day/patch-gap을 정확히 구분한다.

**Android (1~15)**: zero/n-day/patch-gap 구분 · CVE-2019-2215 Binder UAF · 2019 in-the-wild Binder · CVE-2020-15999/16010 Chrome 체인 · Qualcomm Adreno GPU · ARM Mali GPU · CVE-2021-1048 · CVE-2021-0920 · CVE-2022-4262 · CVE-2023-0266 ALSA · CVE-2023-26083 Mali · compat layer variant · GPU 반복 표적 이유 · patch provenance · variant-hunting 가설 ⬜
**iOS (16~34)**: 보안 구조(code signing/sandbox/XPC/XNU) · CVE-2019-7286 CFPrefsDaemon · CVE-2019-7287 IOKit · 2019 watering-hole 체인 · JSC/WebKit foothold · CVE-2020-27930 font · CVE-2020-27950 Mach · CVE-2020-27932 turnstile · 2021 WebKit zero-day · 2021 XNU zero-day · FORCEDENTRY CVE-2021-30860 · FORCEDENTRY sandbox escape · BlastDoor · CVE-2022-22620 Zombie · 2023 GPU Process IPC · CVE-2023-28205/28206 · BLASTPASS · XNU/IOKit/WebKit 공개 소스 · ASRD ⬜
**비교·발견 (35~50)**: Binder↔XPC · GPU↔IOKit · parser 반복 표적 · Invariant 추출 · incomplete patch variant · refactoring regression · legacy 감사 · serialization pair · state/lifetime variant · sanitizer/coverage 전략 · differential fuzzing · crash→report · 영향 과장 금지 · VRP 범위 · 공개 타임라인 · 최종 pattern atlas ⬜

## 9부 — Android 보안 프로젝트 (20개)

설계·구현·검증. 큰 프로젝트는 요구사항/설계/구현/테스트/회고를 별도 장으로.

1. Vulnerable App·Secure Twin ⬜ · 2. APK Attack Surface Mapper ⬜ · 3. MASVS/MASTG Assessment Runner ⬜ · 4. Mobile API Security Lab ⬜ · 5. Android IPC Security Playground ⬜ · 6. WebView·Deep Link Security Lab ⬜ · 7. Keystore/KeyMint Demonstrator ⬜ · 8. Native JNI Memory Bug Lab ⬜ · 9. Binder/AIDL Fuzzing Lab ⬜ · 10. Android Patch Diff Atlas ⬜ · 11. Android System Image Inspector ⬜ · 12. Android Kernel Inventory Tool ⬜ · 13. KASAN Crash Triage Tool ⬜ · 14. GKI/KMI Compatibility Lab ⬜ · 15. Synthetic Malware Behavior Simulator ⬜ · 16. Android Malware IOC/YARA Toolkit ⬜ · 17. Historical Zero-day Pattern Database ⬜ · 18. Patch Provenance Tracker ⬜ · 19. Security Regression Test Corpus ⬜ · 20. Android Security Research Capstone ⬜

---

## 진행 현황

- **1부 실습**: 23/28 완성. 24~28장(MobSF·정적분석 자동화·MASVS·방어 회귀·최종 보고서) 진행 예정.
- **2~9부**: 계획. 추천 순서 — 1부(도구) → 2부 8~24장(플랫폼) → 3부(RCA) → 5부(공격) → 4부(연구) → 7부(커널) → 6부(악성코드) → 8부(사례) → 2부 1~7장·9부(프로젝트).
- 모든 실습 대상은 자작 앱·에뮬레이터·패치된 공개 CVE·허가된 프로그램으로 한정한다.

**선수 지식** → [Android Security Concept Atlas 전체 지도](/posts/android-concept-atlas-index/)
