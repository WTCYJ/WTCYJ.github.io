---
layout: post
title: "adb·logcat·dumpsys로 Android 증적 수집하기"
date: 2026-10-17 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, adb, logcat, dumpsys, pm, am, 증적수집]
excerpt: "분석의 절반은 증적 수집이다. logcat 버퍼는 링이라 덮어써서 휘발성이 있고, dumpsys package는 컴포넌트·권한·서명·UID를, cmd appops는 실제 접근 이력을 준다. /data/data는 UID 사설이라 root나 run-as(디버그 앱)로만 열리고, pm grant/revoke는 런타임 권한에만 먹힌다."
---

앱을 뜯기 전에 먼저 확보해야 하는 것이 있다 — 무엇이 설치됐고, 어떤 권한을 쥐었으며, 런타임에 무엇에 접근했는지. 이 증적이 없으면 이후 정적·동적 분석은 근거 없는 추측이 된다. 이 글은 `adb`·`logcat`·`dumpsys`·`pm`·`am`으로 앱과 시스템 상태를 포렌식적으로 건전하게 수집하는 방법을, 그리고 그 수집을 제약하는 경계(버퍼 휘발성, `/data/data` 사설)를 정리한 기록이다.

> **한 줄 결론**: logcat은 덮어써서 휘발하므로 재현 직후 즉시 덤프하고, `/data/data`는 UID 사설이라 root나 `run-as`(디버그 앱)로만 열린다. 무엇을 수집할 수 있느냐는 앱의 debuggable 여부·기기 root 여부에 종속된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 다섯 도구의 보안 증적용 서브커맨드를 다룬다. 선수 개념은 [연구 환경(1장)](/posts/android-lab-p1c01-research-environment/)의 `adb root`가 되는 이미지, [UID 샌드박스(C09)](/posts/android-concept-atlas-c09-uid-sandbox/)의 `/data/data` 사설성, [permission·AppOps(C10)](/posts/android-concept-atlas-c10-permissions-appops/)의 `pm grant`·`appops` 대상이다.

전체 구조에서 증적 수집은 정적 분석([APK triage](/posts/android-lab-p1c03-apk-triage/)~)과 동적 분석([Frida](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/)~)의 **앞단**이다. 지도를 그리기 전에 좌표를 찍는 단계.

## 핵심 개념 — 다섯 도구의 요점

- **adb**: `adb devices`, `adb shell`, `adb pull/push`, `adb install [-r|-t|-g]`, `adb logcat`, `adb bugreport`. `adb root`는 userdebug/eng(비-Play) 빌드에서만. `Source-confirmed`
- **logcat**: 버퍼 `-b main|system|crash|events|radio|all`, 포맷 `-v time|threadtime`, 필터 `TAG:priority`(예 `ActivityManager:I *:S`)·`--pid`. **버퍼는 링(ring)이라 오래된 로그를 덮어쓴다** → 휘발성. 우선순위 문자(V/D/I/W/E/F/S)는 **대소문자 무관** — `*:s`와 `*:S`가 동일. `Source-confirmed`
- **dumpsys**: `dumpsys package <pkg>`(컴포넌트·권한·서명·UID), `cmd appops get <pkg>`(접근 이력·모드), `dumpsys activity`, `dumpsys meminfo`, 목록은 `dumpsys -l`. `dumpsys`는 각 시스템 서비스의 `dump()`를 호출한다(C19 system_server). `Source-confirmed`
- **pm**: `pm list packages [-f|-3|-s|-U]`, `pm path <pkg>`, `pm dump <pkg>`, `pm grant/revoke <pkg> <perm>`(**런타임 권한만**), `pm list permissions -g -d`. `Source-confirmed`
- **am / content**: `am start -n <comp> -a <action> -d <data> --es <k> <v>`, `am broadcast`, `am start-service`, `am force-stop <pkg>`, `content query --uri content://...`. `Source-confirmed`

**신뢰 경계와 위협 모델.** `/data/data/<pkg>`는 UID 사설(C09)이라 다른 앱은 물론 `adb shell`(UID shell)도 root나 `run-as <pkg>`(그 앱이 `android:debuggable=true`일 때만) 없이는 못 읽는다. `Source-confirmed` 그리고 logcat은 민감정보가 흐를 수 있는 공유 채널이라, 앱이 토큰을 로그에 남기면 여기서 새어나간다 — 수집 관점의 취약 지점이다.

> **[그림 1]** `adb shell dumpsys package <pkg>`에서 컴포넌트·권한·서명·UID가 나오는 부분 캡처 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

에뮬레이터 + 자작/교육용 디버그 앱. `run-as` 실습은 `android:debuggable=true`인 자작 앱으로만. 수집물에 PII가 있으면 즉시 마스킹·최소보관한다.

## 실습 절차와 관측

### 가설
자작 앱이 로그에 토큰을 남기면 `adb logcat`에서 평문으로 보이고, `dumpsys package`엔 그 앱의 `requested`/`install`/`runtime` 권한이 구분되어 나온다. `Inferred`

### 절차
1. 자작 디버그 앱을 설치한다(`adb install -t`).
2. 앱을 실행한 뒤 **즉시** 로그를 덤프한다(버퍼 휘발성 때문).
3. `dumpsys package`·`cmd appops get`으로 권한/접근 상태를 확보한다.
4. `run-as`로 사설 저장소를 열람한다.
5. 모든 명령과 타임스탬프를 수집 노트에 기록한다(chain of custody).

```bash
adb shell pm list packages -3                       # 서드파티 패키지
adb shell pm path com.example.app                   # base/split APK 경로
adb logcat -d -b all -v threadtime > log.txt        # 즉시 전체 버퍼 덤프
adb shell dumpsys package com.example.app | sed -n '/runtime permissions/,+8p'
adb shell cmd appops get com.example.app            # 접근 이력
adb shell run-as com.example.app cat shared_prefs/prefs.xml
```

> **[그림 2]** `adb logcat`에 자작 앱이 남긴 토큰이 평문으로 보이는 캡처(값 마스킹) — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ adb shell dumpsys package com.example.app | grep -A2 'runtime permissions'
    runtime permissions:
      android.permission.ACCESS_FINE_LOCATION: granted=true

$ adb shell run-as com.example.app cat shared_prefs/auth.xml
<string name="access_token">eyJ...</string>   # 평문 (C44 위반)
```

## Root Cause — 왜 이렇게 되는가

`/data/data` 접근이 root/run-as로 제한되는 것은 C09의 UID DAC 그대로다 — 수집조차 그 격리를 존중해야 하므로, "무엇을 수집할 수 있느냐"는 앱의 debuggable 여부·기기 root 여부에 종속된다. logcat이 링 버퍼라 휘발하는 것은 성능·메모리 절충이고, 그래서 재현과 덤프 사이의 시간이 곧 증적의 수명이다.

## 방어와 회귀 검증

- (개발자 방어) 토큰·PII를 logcat에 남기지 않는다 — 이 장의 수집이 곧 그 결함의 탐지법이다. 릴리스 빌드에서 `adb logcat | grep -i token`이 비어야 한다(회귀).
- (연구자) 수집물에 PII가 있으면 즉시 마스킹·최소보관.

**흔한 실패와 처리.** `run-as: package not debuggable` → 릴리스 앱 대상이면 root 이미지 필요. 로그가 비어 있음 → 버퍼가 덮였거나 `-b` 버퍼가 틀림, `-b all`로. 권한이 안 바뀜 → `pm grant`는 런타임 권한만이라 install-time/signature 권한엔 안 먹힌다.

## 버전 차이와 한계

- 최신 Android는 `cmd appops`/`cmd package`가 권장(구 `dumpsys`와 병존).
- `adb backup`은 최신 비-디버그 앱(targetSdk 31+)에서 사실상 무력, 구기기/디버그에서만 유효(→[C44](/posts/android-concept-atlas-c44-secure-storage-backup/)).
- 아키텍처 무관이라 에뮬로 전부 실측 가능하나, 실기기 특유 로그(벤더 데몬)는 관측되지 않는다.

## 정리

- logcat은 즉시 덤프(휘발), `/data/data`는 root/run-as로.
- `dumpsys package`는 컴포넌트·권한·서명·UID를, `cmd appops`는 접근 이력을 준다.
- 수집 가능성은 debuggable·root에 종속된다.

**점검 질문** — (1) logcat `*:E`와 `*:e`는 다른가? (2) `run-as`가 실패하는 두 조건은? (3) `pm grant`가 signature 권한에 안 먹히는 이유는(C10)?

**참고** — [adb](https://developer.android.com/tools/adb) · [logcat](https://developer.android.com/tools/logcat) · [C09 UID 샌드박스](/posts/android-concept-atlas-c09-uid-sandbox/) · [C10 permission·AppOps](/posts/android-concept-atlas-c10-permissions-appops/)

*다음 글: [apksigner·aapt2·bundletool로 APK triage](/posts/android-lab-p1c03-apk-triage/).*
