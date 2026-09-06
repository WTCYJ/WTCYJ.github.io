---
layout: post
title: "[Android 앱 보안 S12] 앱 권한과 AppOps"
date: 2026-09-02 20:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 권한, permission, AppOps, 최소권한, runtime, InsecureShop, 학습기록]
excerpt: "쇼핑 앱이 왜 연락처를 요구할까요. InsecureShop은 READ_CONTACTS를 선언해 두고 코드 어디에서도 쓰지 않습니다. 요청한 권한과 실제로 필요한 권한을 맞대 보고, adb로 런타임 권한을 revoke하고, 권한 위에 한 겹 더 있는 AppOps로 접근을 끄는 것까지 확인했습니다. 설정 화면엔 쇼핑 앱이 연락처를 '허용됨'으로 쥐고 있는 그림이 그대로 남았습니다."
---

> 지금까지 본 결함들이 값을 빼내는 문제였다면, 권한은 그 값에 처음부터 닿을 수 있는지의 문제입니다. 필요 없는 권한을 쥔 앱은, 그 자체로 공격 표면입니다.

권한은 최소로 요청하는 게 원칙입니다. 그런데 InsecureShop은 쇼핑 앱이면서 연락처 읽기 권한을 요청합니다. 코드를 뒤져도 연락처를 쓰는 곳이 없습니다. 요청만 하고 안 쓰는 권한은, 앱이 털렸을 때 공격자에게 그만큼의 접근을 공짜로 얹어 주는 것과 같습니다. 요청과 실제 필요를 맞대 보고, 런타임 권한과 그 위의 AppOps까지 손으로 만져 봤습니다.

---

## 실습 목표

- 요청한 권한과 실제로 코드가 쓰는 권한을 비교한다(과권한 확인).
- 런타임 권한을 adb로 grant/revoke 한다.
- 권한 위의 제어층 AppOps를 확인·조작한다.
- 최소권한으로 줄이는 방향을 정리한다.

---

## 윤리적 범위와 허가 조건

대상은 내가 소유한 InsecureShop이고, 모든 권한 조작(`pm`, `cmd appops`)은 내 `aas-api33` 에뮬레이터의 이 앱에 대해서만 했습니다.

---

## 환경 및 도구 버전

- 대상 기기: `aas-api33` (S01), 대상 앱: `com.insecureshop` (S02)
- `adb shell pm grant/revoke`, `adb shell cmd appops`, `dumpsys package`
- 정적 근거: S03 매니페스트, 디컴파일 결과

---

## 위협 모델 — 필요 이상으로 쥐고 있나

- 요청한 권한을 실제로 쓰는가? 안 쓰면 왜 요청하나?
- 사용자가 그 권한을 끌 수 있는가(런타임 revoke)?
- 권한이 켜져 있어도 접근을 막을 수단이 있는가(AppOps)?

---

## 재현 절차

### 1. 요청 vs 실제 사용

InsecureShop이 요청하는 위험 권한 중 하나가 `READ_CONTACTS`입니다. 그런데 디컴파일한 소스에는 `ContactsContract`도, 연락처 provider 질의도 없습니다.

```console
$ grep -rniE 'READ_CONTACTS|ContactsContract|content://com.android.contacts' sources/com/insecureshop
# (결과 없음) → 선언만 하고 쓰지 않음 = over-privilege
```

쇼핑 앱이 연락처를 요청할 이유가 없는데, 선언돼 있고 설치 시 목록에 오릅니다. 설정의 앱 권한 화면에도 그대로 나타납니다(스크린샷).

### 2. 런타임 권한 revoke

런타임 권한은 사용자가 언제든 끌 수 있어야 합니다. adb로 확인했습니다.

```console
$ adb shell dumpsys package com.insecureshop | grep 'READ_CONTACTS: granted'
    android.permission.READ_CONTACTS: granted=true
$ adb shell pm revoke com.insecureshop android.permission.READ_CONTACTS
$ adb shell dumpsys package com.insecureshop | grep 'READ_CONTACTS: granted'
    android.permission.READ_CONTACTS: granted=false
```

`granted=true`에서 `pm revoke` 한 번으로 `granted=false`가 됐습니다. 권한이 코드에 하드코딩된 게 아니라 런타임 상태라는 뜻입니다.

### 3. AppOps — 권한 위의 제어층

권한이 "부여됨"이어도, 그 위에 AppOps라는 제어층이 하나 더 있습니다. 같은 권한을 `allow`/`ignore`/`deny`로 세밀하게 제어합니다.

```console
$ adb shell cmd appops get com.insecureshop READ_CONTACTS
Uid mode: READ_CONTACTS: ignore
$ adb shell cmd appops set com.insecureshop READ_EXTERNAL_STORAGE ignore
$ adb shell cmd appops get com.insecureshop READ_EXTERNAL_STORAGE
...
```

권한을 revoke하면 AppOps 모드도 `ignore`로 내려갑니다. AppOps를 직접 `ignore`로 두면, 권한이 부여돼 있어도 그 동작만 막을 수 있습니다. one-time 권한("이번만 허용", Android 11+)도 이 층에서 세션이 끝나면 자동으로 회수되는 방식입니다.

---

## 스크린샷

설정의 앱 권한 화면입니다. 쇼핑 앱 InsecureShop이 "허용됨"에 연락처(Contacts)를 쥐고 있습니다. 코드에서 쓰지도 않는 권한이 그대로 허용 목록에 있는 것 — 이게 과권한의 얼굴입니다.

![InsecureShop 앱 권한 설정 화면 — 장바구니 아이콘 아래 "Allowed"에 Contacts, Music and audio, Notifications, Photos and videos, "Not allowed"는 "No permissions denied"](/assets/img/android-app-security/S12/01-permissions.png)

권한 비교·revoke·AppOps 원문은 `assets/evidence/android-app-security/S12/`에 남겼습니다.

---

## 관측 결과

- `READ_CONTACTS`가 선언·부여돼 있으나 코드에서 쓰지 않는다(과권한). 설정 화면에도 연락처가 허용됨으로 뜬다.
- 런타임 권한은 `pm revoke`로 `granted=true → false`가 된다.
- AppOps가 권한 위의 제어층으로 존재하며, revoke 시 `ignore`로 내려가고 직접 조작도 된다.

---

## 근본 원인과 보안 영향

- 최소권한 원칙 위반입니다. 안 쓰는 권한을 요청하면, 앱이 침해됐을 때(예: S07·S09의 임의 코드 실행 경로가 있었다면) 공격자가 그 권한만큼 더 많은 데이터에 닿습니다. 연락처는 그 자체로 민감 정보고요.
- 권한을 요청만 하고 안 쓰면 사용자 신뢰도 잃습니다. 스토어 정책·리뷰에서도 걸리는 항목입니다.
- 권한이 부여됐다고 무조건 접근되는 것도 아닙니다. AppOps·one-time 권한처럼 사용자가 세밀하게 끌 수 있으니, 앱은 권한이 없을 때를 항상 처리해야 합니다.

## 수정 방법

- 매니페스트에서 안 쓰는 권한을 제거한다(여기선 `READ_CONTACTS`). 필요할 때만, 필요한 최소 범위로 요청한다.
- 런타임 권한은 요청 시점을 기능 맥락에 맞추고, 거부·회수된 경우의 대체 흐름을 둔다.
- 저장소는 scoped storage/미디어 권한으로 필요한 것만, 사진·오디오처럼 세분된 권한을 쓴다.

수정 전후는 매니페스트 한 줄의 차이입니다.

```xml
<!-- 전: 쇼핑 앱인데 연락처 요청 -->
<uses-permission android:name="android.permission.READ_CONTACTS"/>
<!-- 후: 제거 (쓰지 않으므로) -->
```

---

## 재검증

`pm revoke` 후 `granted=false`, AppOps `ignore`로 내려간 것을 dumpsys/appops로 확인했고, 설정 화면에서 연락처가 허용 목록에 있는 것도 캡처했습니다. "요청했으나 안 쓰는 권한이 실제로 부여돼 있다"가 코드(미사용)·시스템 상태(granted)·설정 화면 세 지점에서 함께 확인됩니다.

---

## 참고 자료

- Android Developers — 권한 요청, 런타임 권한, one-time 권한
- Android Developers — AppOps(`cmd appops`)
- Android Developers — 최소권한 원칙과 권한 축소
