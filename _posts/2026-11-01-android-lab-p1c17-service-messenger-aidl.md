---
layout: post
title: "Service·Messenger·AIDL 실습 — 호출자 UID를 어디서 얻나"
date: 2026-11-01 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Service, AIDL, Messenger, Binder]
excerpt: "exported 서비스는 아무 앱이 바인드해 IBinder(Messenger 또는 AIDL)를 얻는다. 인가 검사는 요청에 담긴 uid 문자열이 아니라 트랜잭션의 진짜 호출자로 해야 하는데 — AIDL stub 메서드는 Binder.getCallingUid()(Binder 스레드)로, Messenger는 handleMessage가 off-transaction이라 Message.sendingUid로 봐야 한다. 이 차이를 틀리면 인가가 조용히 무너진다."
---

exported 서비스는 아무 앱이 바인드해 IBinder를 얻는다. 인가 검사의 핵심은 요청에 담긴 uid 문자열(공격자 제어)이 아니라 **트랜잭션의 진짜 호출자**로 하는 것인데, 그 진짜 호출자를 얻는 API가 Messenger와 AIDL에서 다르다. 이 차이를 틀리면 인가가 항상 통과한다. 이 글은 exported 서비스의 AIDL/Messenger 인가 검사 결함을 교육용 앱에서 재현·수정하는 기록이다.

> **한 줄 결론**: AIDL stub 메서드는 `Binder.getCallingUid()`(Binder 스레드)로, Messenger는 `handleMessage`가 off-transaction이라 `Message.sendingUid`로 호출자를 얻는다. 요청 페이로드의 uid는 절대 신뢰하지 않는다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 exported 서비스의 AIDL/Messenger 인가 결함을 다룬다. 선수 개념은 [Binder(C17)](/posts/android-concept-atlas-c17-binder-driver/)·[컴포넌트(C21)](/posts/android-concept-atlas-c21-components-binder/)·[인증 vs 인가(C02)](/posts/android-concept-atlas-c02-authn-authz/)의 호출자 UID다.

## 핵심 개념 — 바인드와 호출자 UID

- **바인드**: exported Service는 `startService`/`bindService`로 아무 앱이. `bindService`는 IBinder 반환 — **Messenger**(Handler 기반, 단일 스레드 직렬) 또는 **AIDL**(Binder 스레드 풀, 동시). `Source-confirmed`
- **호출자 UID(중요)**: 인가는 요청에 담긴 uid 문자열이 아니라 트랜잭션의 진짜 호출자로.
  - **AIDL stub 메서드**: `Binder.getCallingUid()`/`getCallingPid()`(Binder 스레드에서 유효, `clearCallingIdentity()` 전에). `Source-confirmed`
  - **Messenger `handleMessage`**: **off-transaction**이라 `getCallingUid()`가 **서비스 자기 uid**를 반환 → **`Message.sendingUid`**를 써야 한다. `Source-confirmed`
- **버그 클래스**: AIDL=동시라 race/TOCTOU + 메서드별 인가 누락; Messenger=단일 Handler라 `msg.what` 디스패치. `Source-confirmed`

**신뢰 경계와 위협 모델.** 요청 페이로드(주장된 uid/package)는 공격자 제어라 절대 신뢰 금지. 진짜 경계는 커널이 각인한 호출자 UID(C17/C22)다.

> **[그림 1]** Messenger `handleMessage`에서 `getCallingUid()`가 서비스 자기 uid(1000/self)를, `msg.sendingUid`가 실제 호출자를 보여주는 로그 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱: exported AIDL 서비스(인가 결함) + Messenger 서비스(getCallingUid 오용) + 방어 버전.

## 실습 절차와 관측

### 가설
취약 AIDL은 무권한 클라이언트가 `adminAction` 호출 성립, Messenger 취약은 sendingUid 미검사로 통과, 방어 버전은 진짜 호출자 UID 검사로 차단. `Inferred`

### 절차
1. 자작 클라이언트로 exported 서비스를 바인드한다.
2. AIDL 메서드를 무권한 호출 → 성립을 관측한다.
3. Messenger로 메시지를 전송, sendingUid 미검사를 관측한다.
4. 방어 버전(getCallingUid/sendingUid + 서명 검사)에서 차단을 확인한다.
5. AIDL 동시 호출로 race를 관측한다(자작).

```java
// 방어 (AIDL): Binder 스레드에서 진짜 호출자 검사
public void adminAction() {
  int caller = Binder.getCallingUid();            // clearCallingIdentity 전
  if (getPackageManager().checkSignatures(caller, myUid()) != SIGNATURE_MATCH)
    throw new SecurityException("unauthorized");
}
// 방어 (Messenger): handleMessage에서는 msg.sendingUid
public void handleMessage(Message msg) {
  int caller = msg.sendingUid;                    // getCallingUid()는 self를 반환
}
```

> **[그림 2]** 무권한 클라이언트가 취약 AIDL `adminAction`을 호출해 실행된 로그 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[AIDL] client(uid 10234) -> adminAction() executed (취약: 인가 없음)
[Messenger] handleMessage getCallingUid()=1000(self) vs msg.sendingUid=10234
```

## Root Cause — 왜 이렇게 되는가

Messenger에서 `getCallingUid`가 자기 uid를 주는 것은 `handleMessage`가 트랜잭션 밖에서 돌기 때문이다 — 그래서 `sendingUid`가 정답이다. 근본은 "인가 검사의 위치·소스 오류"다. 그리고 `clearCallingIdentity()` 후 `getCallingUid()`도 자기 uid를 주므로, 검사는 반드시 clear 전에 한다.

## 방어와 회귀 검증

- (개발자) AIDL은 메서드마다 `Binder.getCallingUid`(clear 전), Messenger는 `msg.sendingUid`, 서명/권한 검사, 페이로드 uid 불신. "무권한 클라이언트가 특권 AIDL/Messenger 동작 호출 불가"를 회귀로.
- (연구자) 자작만.

**흔한 실패와 처리.** 인가가 항상 통과 → Messenger getCallingUid를 sendingUid로. race 재현 안 됨 → 동시성 부족, 다중 스레드 클라이언트로.

## 버전 차이와 한계

- A14 암시적 Intent 제약이 서비스 시작에도 영향(같은 앱 비exported만).
- 에뮬/자작. 상용 서비스 공격 금지.

## 정리

- AIDL은 `Binder.getCallingUid()`(Binder 스레드), Messenger는 `Message.sendingUid`.
- `clearCallingIdentity()` 후엔 자기 uid가 나온다.
- 페이로드 uid는 신뢰 금지.

**점검 질문** — (1) AIDL과 Messenger에서 호출자 UID를 얻는 API 차이는? (2) `clearCallingIdentity()` 후 `getCallingUid()`가 위험한 이유는? (3) AIDL 동시성이 만드는 버그 클래스는?

**참고** — [bound-services](https://developer.android.com/develop/background-work/services/bound-services) · [AIDL](https://developer.android.com/develop/background-work/services/aidl) · [C17 Binder](/posts/android-concept-atlas-c17-binder-driver/) · [C21 컴포넌트](/posts/android-concept-atlas-c21-components-binder/)

*다음 글: [ContentProvider와 FileProvider 실습](/posts/android-lab-p1c18-contentprovider-fileprovider/).*
