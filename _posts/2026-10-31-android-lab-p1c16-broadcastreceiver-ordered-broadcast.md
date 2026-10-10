---
layout: post
title: "BroadcastReceiver와 ordered broadcast 실습 — 위조와 결과 조작"
date: 2026-10-31 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, BroadcastReceiver, OrderedBroadcast]
excerpt: "exported 리시버는 am broadcast로 위조된 브로드캐스트를 받고, 앱이 그 존재/extra를 인증으로 취급하면 아무 앱이나 트리거한다. ordered broadcast는 우선순위로 직렬 전달되며 각 리시버가 결과를 rewrite·abort할 수 있어, 높은 우선순위의 악성 리시버가 결과를 조작하거나 전달을 끊는다."
---

브로드캐스트는 앱의 무인증 제어 채널이 되기 쉬운 표면이다. exported 리시버는 `am broadcast`로 위조된 브로드캐스트를 받고, 앱이 그 존재/extra를 인증으로 취급하면 아무 앱이나 트리거한다. 그리고 ordered broadcast에는 일반 브로드캐스트에 없는 표면 — 결과 조작·abort — 이 있다. 이 글은 exported 리시버 위조와 ordered broadcast 결과 조작/차단을 교육용 앱에서 재현하는 기록이다.

> **한 줄 결론**: exported 리시버가 브로드캐스트의 존재/extra를 인증으로 취급하면 `am broadcast`로 무권한 트리거된다. ordered broadcast는 우선순위·결과·abort를 제공하므로, 높은 우선순위의 악성 리시버가 결과를 조작하거나 전달을 끊을 수 있다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 exported 리시버 위조와 ordered broadcast 조작을 다룬다. 선수 개념은 [Activity/Intent(15장)](/posts/android-lab-p1c15-activity-intent-injection/)와 [컴포넌트↔Binder(C21)](/posts/android-concept-atlas-c21-components-binder/)다.

## 핵심 개념 — 위조와 ordered

- **위조**: `adb shell am broadcast -a ACTION --es k v [-n pkg/.Receiver]`(-n 없으면 매칭 exported 전체). `--receiver-permission P`·`--user N`. 아무 앱이나 같은 브로드캐스트를 위조하므로, 리시버가 그 존재/extra를 **인증으로 취급하면** 무권한 트리거된다. `Source-confirmed`
- **ordered broadcast**: `sendOrderedBroadcast`는 `android:priority` 내림차순 직렬 전달, 각 리시버가 `getResultData`/`setResult(code,data,extras)`로 결과를 rewrite·`abortBroadcast()`로 하위 전달을 차단. 높은 우선순위 악성 리시버 = 결과 주입/억제. 일반 브로드캐스트엔 결과 파이프라인이 없다. `Source-confirmed`

**신뢰 경계와 위협 모델.** 브로드캐스트의 신뢰 경계는 **리시버 자신의 검증**이지 브로드캐스트가 아니다. exported+무검증 = 무인증 제어.

> **[그림 1]** `am broadcast`로 위조한 브로드캐스트가 exported 리시버의 기능을 트리거한 로그 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱: exported CtrlReceiver(무검증) + ordered 결과 파이프라인 + 방어 버전(권한·검증).

## 실습 절차와 관측

### 가설
취약 앱은 위조 브로드캐스트로 기능 트리거·ordered 결과 조작 성립, 방어 버전은 권한/서명 검증으로 차단. `Inferred`

### 절차
1. exported 리시버 목록을 얻는다(6장).
2. `am broadcast`로 위조 → 동작을 관측한다.
3. 자작 악성 리시버를 높은 우선순위로 등록해 ordered 결과를 조작/abort한다.
4. 방어 버전(receiver-permission·서명 검증)에서 차단을 확인한다.
5. A14 기기에서 컨텍스트 등록 플래그를 확인한다.

```bash
adb shell am broadcast -a com.example.UNLOCK --es code 1234 -n com.example.app/.CtrlReceiver
```

> **[그림 2]** 높은 우선순위 악성 리시버가 ordered broadcast 결과를 조작/abort한 로그 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ am broadcast -a com.example.UNLOCK --es code 1234
Broadcast completed: result=0
# 기능 잠금 해제 (취약)
```

## Root Cause — 왜 이렇게 되는가

결과 조작이 ordered에만 있는 것은 그 경로가 우선순위·결과·abort를 제공하기 때문이다 — "SMS/인증 브로드캐스트 가로채기"류의 기제다. 근본은 리시버가 브로드캐스트의 존재를 인증으로 취급한 것이다.

## 방어와 회귀 검증

- (개발자) 리시버에 permission·서명 검증, 민감 데이터는 명시적/대안 채널, ordered 결과 신뢰 금지. "위조 브로드캐스트로 기능 트리거 불가", "ordered 결과가 신뢰되지 않음"을 회귀로.
- (연구자) 자작만.

**흔한 실패와 처리.** 위조 무반응 → 리시버가 permission 요구(정상). A14 등록 오류 → `RECEIVER_EXPORTED/NOT_EXPORTED` 미지정.

## 버전 차이와 한계

- A13(API33) `RECEIVER_EXPORTED`/`RECEIVER_NOT_EXPORTED` 도입, A14(API34) 컨텍스트 등록 비시스템 리시버는 필수. 일부 암시적 브로드캐스트 접근 강화.
- 에뮬/자작. targetSdk·기기 버전 기록.

## 정리

- 리시버의 신뢰 경계는 자신의 검증(브로드캐스트가 아님).
- ordered만 결과 조작·abort 표면이 있다.
- A14는 컨텍스트 리시버 등록에 export 플래그 필수.

**점검 질문** — (1) 일반 브로드캐스트와 ordered의 표면 차이는? (2) 리시버의 신뢰 경계는 어디인가? (3) A14에서 컨텍스트 리시버 등록에 필요한 플래그는?

**참고** — [broadcasts](https://developer.android.com/develop/background-work/background-tasks/broadcasts) · [C21 컴포넌트↔Binder](/posts/android-concept-atlas-c21-components-binder/)

*다음 글: [Service·Messenger·AIDL 실습](/posts/android-lab-p1c17-service-messenger-aidl/).*
