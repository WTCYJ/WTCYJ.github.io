---
layout: post
title: "Activity·Intent injection 실습 — exported와 intent redirection"
date: 2026-10-30 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Activity, Intent, IntentRedirection]
excerpt: "exported Activity는 am start 한 줄로 아무 앱이 실행할 수 있고, 조작된 extra로 내부 화면에 도달한다. 더 위험한 건 intent redirection — 권한 있는 컴포넌트가 extra에 담긴 Intent를 무비판적으로 startActivity하면, 공격자가 피해자 UID로 내부 비exported 컴포넌트에 도달한다(confused deputy)."
---

컴포넌트 IPC 공격의 첫 실습은 Activity다. exported Activity는 `am start` 한 줄로 아무 앱이 실행할 수 있고, 조작된 extra로 내부 화면에 도달한다. 그리고 더 위험한 패턴이 intent redirection이다 — 권한 있는 컴포넌트가 extra에 담긴 Intent를 무비판적으로 실행하면, 공격자가 피해자 UID로 내부 비exported 컴포넌트에 도달한다. 이 글은 자작 취약 앱에서 이를 재현하고 방어까지 보는 기록이다.

> **한 줄 결론**: `exported=true`(또는 pre-31 암시적 exported) Activity는 `am start`로 도달하고, `getParcelableExtra`한 Intent를 무검증 `startActivity`하면 intent redirection으로 exported 경계를 넘는다(C22 confused deputy).

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 exported Activity·Intent injection·redirection을 교육용 앱에서 재현·방어한다. 선수 개념은 [컴포넌트↔Binder(C21)](/posts/android-concept-atlas-c21-components-binder/)의 exported 게이트, [매니페스트 매핑(6장)](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)의 exported 목록이다.

## 핵심 개념 — am, exported, redirection

- **실행**: `adb shell am start -n pkg/.Comp -a ACTION -d content://uri --es k v --ez flag true`. extra 타입 플래그: `--es`(String)·`--ez`(boolean)·`--ei`(int)·`--el`(long)·`--ef`(float)·`--eu`(URI)·`--ecn`(ComponentName)·`--esa`/`--eia`(배열). `-a`(action)·`-d`(data)·`-c`(category)·`-f`(flags hex). `Source-confirmed`
- **exported**: API 31+는 intent-filter 있으면 명시 필수(pre-31 암시적 true, filter 없으면 all-version false). `Source-confirmed`
- **intent redirection**: 권한 있는 exported 컴포넌트가 `Intent inner = getParcelableExtra("extra_intent"); startActivity(inner);`처럼 중첩 Intent를 무검증 실행 → 공격자가 **내부 비exported 컴포넌트**를 피해자 UID로 도달(C22 confused deputy). `Source-confirmed`

**신뢰 경계와 위협 모델.** `exported=false`는 같은 UID만이다. adb shell(uid 2000)은 exported=false에 막힌다(`Permission Denial: ... not exported from uid`). **단 shell은 일반 앱보다 특권이 많아** signature/privileged 권한 가드가 걸린 컴포넌트는 shell에서 되어도 무권한 앱에선 안 될 수 있으니, PoC 시 그 권한을 명시한다.

> **[그림 1]** `am start`로 조작 extra를 주입해 내부 관리 화면에 도달한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱에 exported HiddenActivity + redirection 취약 컴포넌트 + 방어 버전을 둔다. 상용 앱 공격은 하지 않는다.

## 실습 절차와 관측

### 가설
취약 앱은 `am start`로 내부 화면 도달·redirection으로 비exported 도달, 방어 버전은 컴포넌트/패키지 검증으로 차단. `Inferred`

### 절차
1. 6장 매핑으로 exported Activity 목록을 얻는다.
2. `am start`로 조작 extra를 주입해 동작을 관측한다.
3. redirection 컴포넌트에 내부 Intent를 담아 전송한다.
4. 방어 버전(대상 검증)에서 차단을 확인한다.
5. targetSdk/기기 버전을 기록한다(A14 제약).

```bash
adb shell am start -n com.example.app/.HiddenActivity --ez isAdmin true
# intent redirection: extra_intent에 내부 컴포넌트를 겨냥한 Intent를 담아 전송
```

> **[그림 2]** intent redirection으로 비exported 내부 컴포넌트에 도달한 로그 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ am start -n com.example.app/.HiddenActivity --ez isAdmin true
Starting: Intent { cmp=com.example.app/.HiddenActivity (has extras) }
# 내부 관리 화면 도달 (취약)
```

## Root Cause — 왜 이렇게 되는가

redirection이 성립하는 것은 피해자 컴포넌트가 **공격자 제어 Intent를 자기 권한으로 실행**하기 때문이다(C22). 근본은 "입력(중첩 Intent) 검증 부재"다. 그리고 `am start`가 되는데 무권한 앱에선 안 될 수 있는 것은 shell이 일반 앱보다 특권이 많기 때문이라, 도달성을 주장할 땐 컴포넌트의 권한 가드를 함께 봐야 한다.

## 방어와 회귀 검증

- (개발자) 필요한 것만 export·권한 가드·중첩 Intent의 component/package 검증·`FLAG_GRANT_*` 금지. "exported Activity가 권한 없이 관리 기능에 도달 못 함", "중첩 Intent가 내부 컴포넌트로 안 감"을 회귀로.
- (연구자) 자작/교육용만.

**흔한 실패와 처리.** `Permission Denial: not exported` → 대상이 exported=false(정상 방어). extra 무시됨 → 타입 플래그 오류(boolean을 `--es`).

## 버전 차이와 한계

- API 31 명시 exported, A14 암시적 Intent 비exported(같은 앱만)·redirection 추가 보호.
- 에뮬/자작 앱. 상용 앱 공격 금지.

## 정리

- `am start`로 exported Activity 도달 + 조작 extra.
- intent redirection이 exported 경계를 confused-deputy로 넘는다.
- shell 성공이 곧 무권한 앱 도달은 아니다.

**점검 질문** — (1) `--ez`와 `--es`를 혼동하면? (2) intent redirection이 exported 경계를 넘는 원리는? (3) adb shell로 되는데 무권한 앱에선 안 될 수 있는 이유는?

**참고** — [adb](https://developer.android.com/tools/adb) · [intents-filters](https://developer.android.com/guide/components/intents-filters) · [C21 컴포넌트↔Binder](/posts/android-concept-atlas-c21-components-binder/)

*다음 글: [BroadcastReceiver와 ordered broadcast](/posts/android-lab-p1c16-broadcastreceiver-ordered-broadcast/).*
