---
layout: post
title: "[Android 앱 보안 S15] 루팅·디버깅 탐지의 한계"
date: 2026-09-02 23:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 루팅탐지, 디버깅탐지, PlayIntegrity, 방어설계, 학습기록]
excerpt: "많은 앱이 루팅·디버깅을 탐지해 자신을 지키려 합니다. 그런데 그 판정이 전부 앱 안에서 난다면, 얼마나 믿을 수 있을까요. 직접 만든 탐지 데모로 흔한 체크들을 돌려 보니, 평범한 에뮬레이터가 COMPROMISED로 찍히고(false positive) 정작 켜져 있는 신호는 놓쳤습니다(false negative). 우회 경쟁이 아니라, 왜 클라이언트 측 탐지가 방어가 될 수 없는지를 정리했습니다."
---

> S14에서 클라이언트 판정은 실행 중에 뒤집힌다는 걸 봤습니다. 루팅·디버깅 탐지도 결국 클라이언트 판정입니다. 이번 편은 그 한계를 탐지 로직의 구조로 짚습니다.

루팅·디버깅 탐지는 "이 기기가 변조됐으면 앱을 막자"는 방어입니다. 취지는 이해되지만, 그 판정이 앱 프로세스 안에서 나는 이상 두 가지 문제를 피할 수 없습니다. 오탐(멀쩡한 환경을 위험으로)과 미탐(진짜 신호를 놓침), 그리고 S14에서 본 것처럼 판정 자체를 뒤집을 수 있다는 것. 직접 만든 탐지 데모로 이걸 눈으로 확인하고, 방어를 어디에 둬야 하는지 정리했습니다.

---

## 실습 목표

- 흔한 루팅·디버깅 탐지 체크의 구조를 만들어 돌려 본다.
- 오탐(false positive)과 미탐(false negative)을 실제로 관찰한다.
- 클라이언트 측 탐지의 근본 한계와, 서버 검증의 필요를 정리한다.

---

## 윤리적 범위와 허가 조건

탐지 로직은 내가 직접 작성한 데모 앱(`com.aas.rootdetect`)이고, 모든 실행은 `aas-api33` 에뮬레이터 안입니다. 이 편은 우회 기법 전시가 아니라 탐지의 한계와 방어 설계를 다룹니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01, userdebug/dev-keys)
- 탐지 데모 앱: 직접 손빌드, S05 툴체인

---

## 위협 모델 — 탐지는 무엇을 지키나

- 탐지가 위험 기기를 정확히 가려내는가(오탐·미탐)?
- 판정이 어디서 나는가(클라이언트 vs 서버)?
- 판정을 뒤집을 수 있는가?

---

## 재현 절차

### 1. 흔한 체크들

데모 앱에 실무에서 자주 쓰는 체크들을 넣었습니다. su 바이너리, 빌드 태그, 디버그 속성, 디버거 연결, Frida 흔적 등입니다.

```java
suOnPath()        // /system/bin/su 등 알려진 경로에 su 있나
Build.TAGS.contains("test-keys")
getProp("ro.debuggable").equals("1")
Debug.isDebuggerConnected()
/proc/self/maps 에 "frida"/"gum-js" 문자열
```

### 2. 돌린 결과 — 오탐과 미탐

에뮬레이터에서(테스트로 `/data/local/su`를 하나 심은 상태) 돌린 결과입니다.

```
device = sdk_gphone64_x86_64 / TAGS = dev-keys
[X] su binary on known paths
[ ] Build.TAGS = test-keys  (dev-keys)
[ ] ro.debuggable = 1
[ ] ro.secure = 0
[ ] debugger attached
[ ] frida in /proc/self/maps
=> flagged 1 / 6  ->  verdict: COMPROMISED (client-side)
```

두 가지가 동시에 드러납니다.

- 오탐: 이 기기는 그냥 개발용 에뮬레이터입니다. 실제 위협이 아닌데도 su 체크 하나로 COMPROMISED로 찍혔습니다. 실기기에서도 커스텀 ROM·개발자 기기가 이렇게 걸려, 정상 사용자를 막는 오탐이 됩니다.
- 미탐: 이 에뮬레이터는 `ro.debuggable=1`입니다(셸에서 확인됨). 그런데 체크는 그걸 놓쳤습니다. 앱이 앱 샌드박스(untrusted_app) 안에서 `getprop`을 실행하려다 값을 못 읽었기 때문입니다. 진짜 신호가 있는데도 앱의 관측 위치 때문에 놓친 것 — 미탐입니다.

### 3. 그리고 판정은 뒤집힌다

각 체크는 결국 boolean 하나로 모입니다. S14에서 본 대로, 그 반환을 Frida로 `false`로 바꾸면 탐지는 통과로 바뀝니다. 탐지 로직을 아무리 늘려도, 마지막 판정이 클라이언트에 있는 한 그 지점을 뒤집으면 끝입니다. 이건 방어와 우회의 무한 경쟁이지, 방어의 승리가 아닙니다.

---

## 스크린샷

데모 앱의 탐지 결과 화면입니다. su 체크 하나로 COMPROMISED 판정이 나고, `ro.debuggable=1`은 놓쳤습니다. 오탐과 미탐이 한 화면에 있습니다.

![RootDetectDemo 실행 화면 — su binary 체크만 [X], ro.debuggable 등은 [ ], flagged 1/6, verdict COMPROMISED (client-side), 그리고 오탐·미탐·Frida 우회에 대한 주의 문구](/assets/img/android-app-security/S15/01-rootdetect.png)

탐지 데모 소스와 결과 원문은 `assets/evidence/android-app-security/S15/`에 남겼습니다.

---

## 관측 결과

- 평범한 에뮬레이터가 su 체크 하나로 COMPROMISED로 판정됐다(오탐).
- `ro.debuggable=1`이라는 실제 신호는 앱 샌드박스 제약으로 놓쳤다(미탐).
- 모든 판정이 앱 프로세스 안에서 났고, 그 반환은 S14의 방식으로 뒤집을 수 있다.

---

## 근본 원인과 보안 영향

- 클라이언트 측 탐지는 관측 위치가 앱 안이라, 환경 차이에 따라 오탐·미탐이 불가피합니다. 정상 사용자를 막거나, 진짜 위협을 놓칩니다.
- 판정이 클라이언트에 있으면 그 판정은 뒤집힙니다(S14). 탐지 체크를 늘리는 건 우회 비용을 조금 올릴 뿐, 방어의 근거가 되지 못합니다.
- 그래서 탐지 결과를 "이 기기는 안전하다"의 근거로 삼으면 안 됩니다. 그건 신뢰할 수 없는 클라이언트의 자기 신고일 뿐입니다.

## 수정 방법 / 방어 설계

- 신뢰는 서버에 둡니다. 민감한 동작은 서버가 승인하고, 클라이언트 판정을 그대로 믿지 않습니다.
- 기기 무결성이 필요하면 서버가 검증 가능한 신호를 씁니다 — Play Integrity API처럼, 구글이 서명한 검증 토큰을 서버가 확인하는 방식. 앱 안 boolean이 아니라, 서버가 확인하는 증명이어야 합니다.
- 클라이언트 탐지를 아예 안 쓰는 게 아니라, 그것을 "차단의 근거"가 아니라 "부가 신호"로만 씁니다. 최종 결정과 신뢰는 서버에.

---

## 재검증

같은 에뮬레이터에서 탐지는 COMPROMISED(오탐)를 냈고, 동시에 `ro.debuggable=1`을 놓쳤습니다(미탐). 두 오류가 한 실행에 함께 나타나, 클라이언트 측 탐지가 신뢰의 근거가 될 수 없음을 보여 줍니다. 판정을 뒤집는 것은 S14에서 이미 확인했습니다.

---

## 참고 자료

- Android Developers — Play Integrity API(서버 측 검증)
- OWASP MASVS — Resilience: 클라이언트 측 방어의 한계
- Android Developers — 하드웨어 보증(key attestation)
