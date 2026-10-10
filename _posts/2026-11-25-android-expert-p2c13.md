---
layout: post
title: "WindowManagerService·UI 보안"
date: 2026-11-25 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, WindowManagerService, Tapjacking, Overlay]
excerpt: "WMS는 system_server 안의 Java 정책 엔진이고 화면 합성은 별도 네이티브 SurfaceFlinger가 한다 — 둘을 뭉뚱그리면 오버레이 탭재킹의 방어선이 SYSTEM_ALERT_WINDOW 권한이 아니라 '받는 쪽 창'의 filterTouchesWhenObscured라는 사실을 놓친다."
---

화면은 앱 하나가 소유하지 않는다. 서로 다른 UID의 창들이 한 디스플레이 위에 Z 순서로 겹쳐 있고, 그 순서와 입력 라우팅을 심판하는 것이 system_server 안의 **WindowManagerService(WMS)**다. UI 보안 사고 — 탭재킹, 오버레이 피싱, 화면 캡처 유출 — 는 거의 전부 "사용자가 보는 창"과 "터치가 실제로 가는 창"이 어긋나는 데서 나온다. 이건 메모리 안전 문제가 아니라 **UI의 진실성(truth) 문제**다.

이 글은 App → `WindowManager.addView` → Binder(`IWindowSession`) → WMS → SurfaceFlinger/InputDispatcher로 이어지는 창·입력 경로를, AOSP 소스 위치와 함께 분석한 기록이다. 개발자·플랫폼·보안 세 관점에서 "누가 무엇을 신뢰하는가"를 따라간다.

> **한 줄 결론**: 오버레이 공격의 방어선은 오버레이를 '거는' 권한(SYSTEM_ALERT_WINDOW)이 아니라 터치를 '받는' 창의 정책이다. 앱은 `filterTouchesWhenObscured`로, 플랫폼은 Android 12의 기본 untrusted-touch 차단으로 이 경계를 지킨다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 (1) WMS와 SurfaceFlinger의 역할 분리, (2) 창 하나가 어떤 경로로 화면에 붙고 입력을 받는지, (3) FLAG_SECURE·오버레이·탭재킹의 신뢰 경계와 플랫폼 완화의 버전별 변화다. 공격 실습이 아니라 **구조와 소스 이해**가 목적이다.

선수 지식은 세 가지다. Binder가 프로세스 경계를 넘는 호출을 어떻게 나르는지(14장 예정), system_server가 여러 시스템 서비스를 담은 하나의 특권 프로세스라는 점(AMS를 다룬 10장), 그리고 앱과 시스템이 서로 다른 UID로 격리된다는 기본 샌드박스 모델이다. 전체 흐름에서 WMS는 "프레임워크 서비스" 층에 있고, 그 아래 네이티브 SurfaceFlinger·InputDispatcher가 실제 픽셀과 입력 이벤트를 처리한다.

## 핵심 개념 — WMS는 정책, SurfaceFlinger는 합성

가장 흔한 오개념부터 끊는다. **WMS가 화면을 그리지 않는다.** WMS는 `frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java`에 있는 Java 서비스로, 창의 Z 순서·포커스·가시성·입력 대상을 **결정**한다. 실제 서피스 합성은 별도 네이티브 프로세스 **SurfaceFlinger**가 하고, 입력 분배는 inputflinger의 **InputDispatcher**가 한다. `Source-confirmed`

| 구성요소 | 위치/프로세스 | 하는 일 |
|--|--|--|
| `WindowManager`(앱측) | 앱 프로세스 | `addView/updateViewLayout` API, `ViewRootImpl` 소유 |
| `IWindowSession` | Binder 인터페이스 | 앱 ↔ WMS 창 등록/갱신 채널 |
| `WindowManagerService` | system_server(Java) | Z 순서·포커스·입력 대상·정책 결정 |
| `SurfaceFlinger` | 독립 네이티브 프로세스 | `SurfaceControl` 서피스 합성 |
| `InputDispatcher` | inputflinger(네이티브) | 창 정보 기반 `MotionEvent` 라우팅·가림 플래그 부여 |

앱이 창을 하나 붙이는 경로: `WindowManager.addView` → `ViewRootImpl`이 `IWindowSession.addToDisplayAsUser`(레거시 오버로드 `addToDisplay`, 버전 의존적)를 Binder로 호출 → WMS가 `WindowState`를 만들고 정책(타입·플래그·권한)을 검사 → SurfaceFlinger에 서피스 생성을 요청 → 이후 터치는 InputDispatcher가 창 목록을 보고 대상 창에 `MotionEvent`를 보낸다. 이때 대상 창이 다른 창에 가려져 있으면 이벤트에 **가림 플래그**가 붙는다. `Source-confirmed`

- `MotionEvent.FLAG_WINDOW_IS_OBSCURED` — 이 창이 다른 창(다른 UID일 수 있음)에 **완전히** 가려진 지점의 터치. `Source-confirmed`
- `MotionEvent.FLAG_WINDOW_IS_PARTIALLY_OBSCURED` — 부분 가림(Android 10부터 구분 도입). `Reported`

이 플래그가 탭재킹 방어의 핵심 재료다. 오버레이가 위에 떠 있어도, 아래 창이 "나는 가려진 터치를 안 받는다"고 선언하면 속임수가 성립하지 않는다.

> **[그림 1]** `adb shell dumpsys window windows`로 자작 앱 두 개(정상 창 + TYPE_APPLICATION_OVERLAY 창)의 Z 순서·플래그·소유 UID를 나란히 확인한 터미널 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

한 디스플레이는 **여러 UID가 공유하는 자원**이다. WMS(system_server)만이 신뢰받는 심판이고, 각 앱의 창은 서로를 신뢰하지 않는다. 위협은 두 갈래다.

1. **입력 진실성 붕괴(탭재킹/오버레이 피싱).** 공격 앱이 자기 창을 피해 앱 위에 얹어, 사용자가 보는 것과 실제 터치 대상을 어긋나게 만든다. 목표는 "결제 승인"·"권한 허용" 같은 버튼을 모르게 누르게 하는 것.
2. **출력 기밀성 붕괴(화면 캡처).** 다른 앱·서비스가 민감 창의 픽셀을 스크린샷/화면 녹화(MediaProjection)로 읽어간다.

경계를 그리면: **입력 방향**의 신뢰 결정권은 터치를 받는 창(아래 앱)과 플랫폼에 있고, **출력 방향**의 기밀성은 창을 소유한 앱이 `FLAG_SECURE`로 선언한다. 두 방향 모두 "오버레이를 거는 쪽 권한"만으로는 못 막는다는 게 핵심이다.

여기서 두 번째 오개념 — `FLAG_SECURE`는 만능이 아니다. 이 플래그는 창 콘텐츠를 스크린샷·비보안 디스플레이·MediaProjection에서 제외해 검은 화면으로 만든다. `Source-confirmed` 하지만 (a) **창 단위**라 앱 전체가 아니며, (b) 루팅·물리 캡처·일부 접근성 경로까지 막지는 못한다. "FLAG_SECURE 걸었으니 안전"은 위협 모델을 절반만 본 것이다. `Inferred`

## 분석 — 오버레이가 터치를 훔치는(못 훔치는) 경로

무기화된 익스플로잇이 아니라, **왜 방어가 성립하는지**를 소스 흐름으로 본다. 안전 범위는 에뮬레이터(AVD)와 자작 앱 두 개뿐이다.

InputDispatcher는 터치가 발생한 좌표에서 대상 창 위에 다른 UID의 창이 겹쳐 있는지를 계산해 `MotionEvent`에 가림 플래그를 채운다. `Source-confirmed` 그 이벤트는 Binder를 타고 대상 앱의 `ViewRootImpl`로 가고, 프레임워크는 뷰에 넘기기 전에 `View.onFilterTouchEventForSecurity(...)`를 호출한다. 이 메서드는 `getFilterTouchesWhenObscured()`가 켜져 있고 `FLAG_WINDOW_IS_OBSCURED`가 붙었으면 이벤트를 **버린다**. `Source-confirmed` 아래 인용 코드가 검사하는 건 완전 가림 플래그 하나뿐이라, 부분 가림(`FLAG_WINDOW_IS_PARTIALLY_OBSCURED`)은 기본 필터가 잡지 못한다. 즉 "타깃 버튼은 보이게 두고 주변만 덮는" 흔한 탭재킹은 기본값으로 안 막히고, 앱이 `FLAG_WINDOW_IS_PARTIALLY_OBSCURED`를 직접 검사해야 방어된다. `Source-confirmed`

```java
// frameworks/base/core/java/android/view/View.java — 개념 요지(요약 인용)
public boolean onFilterTouchEventForSecurity(MotionEvent event) {
    if ((mViewFlags & FILTER_TOUCHES_WHEN_OBSCURED) != 0
            && (event.getFlags() & MotionEvent.FLAG_WINDOW_IS_OBSCURED) != 0) {
        return false; // 가려진 터치는 버린다
    }
    return true;
}
```

앱이 이 방어를 켜는 방법은 두 줄이다.

```xml
<!-- 레이아웃 XML: 민감한 버튼에 -->
<Button android:filterTouchesWhenObscured="true" ... />
```
```kotlin
// 또는 코드로
sensitiveButton.filterTouchesWhenObscured = true
```

즉 방어선은 오버레이를 거는 권한이 아니라 **받는 창의 한 줄**이다. 권한 게이팅(SYSTEM_ALERT_WINDOW)은 "오버레이를 못 만들게" 하려는 것이지, "오버레이가 있어도 속지 않게" 하려는 것이 아니다. 후자가 실제 방어다.

> **[그림 2]** `filterTouchesWhenObscured`를 끈 자작 창과 켠 자작 창 위에 각각 오버레이를 얹었을 때, 아래 버튼의 터치 소비 여부가 로그로 갈리는 대조 캡처(`adb logcat`) — *실측 스크린샷 자리*

관측 명령은 `adb shell dumpsys window windows`로, 각 `WindowState`의 타입·플래그·`ownerUid`와 Z 순서가 나온다. 오버레이 창은 `TYPE_APPLICATION_OVERLAY`로, FLAG_SECURE 창은 플래그 목록에서 확인된다. `예시 출력(교체)`:

```
Window #2 Window{... u0 com.example.overlay}:
    mOwnerUid=10234 type=TYPE_APPLICATION_OVERLAY
    ...
Window #3 Window{... u0 com.example.victim/.MainActivity}:
    mOwnerUid=10233 (flags=... FLAG_SECURE ...)
```

## Root Cause — 왜 이렇게 되는가

근본 원인은 **다중 UID가 하나의 디스플레이를 공유하는데, "위에 그릴 수 있는 능력"과 "믿을 수 있는 창"이 분리되지 않았던** 초기 설계에 있다. 초창기 오버레이 타입은 넓은 재량을 줬고, SYSTEM_ALERT_WINDOW는 한동안 Play 설치 앱에 사실상 자동 부여돼 오버레이 자체를 게이트로 쓰기 어려웠다. `Reported`

그래서 방어의 무게중심이 두 번 이동한다. 첫째, **판단을 받는 앱으로** — 가림 플래그 + `filterTouchesWhenObscured`로 "가려진 터치는 안 받는다"를 앱이 선언. 둘째, **판단을 플랫폼 기본값으로** — 앱이 깜빡해도 OS가 막도록 Android 12에서 기본 차단을 도입. 이 궤적은 "각 앱이 옵트인해야 하는 방어는 결국 새는 방어"라는 보안 일반 원칙의 실례다. `Inferred`

출력 방향(FLAG_SECURE)도 같은 결이다. 화면은 공유 자원이므로, 콘텐츠 소유자가 "이 서피스는 캡처 대상에서 빼라"고 명시해야 SurfaceFlinger/스크린 캡처 경로가 그 서피스를 블랭크 처리한다. 기밀성은 소유자의 선언에 종속된다. `Source-confirmed`

## 버전 차이와 한계

플랫폼 하드닝의 타임라인이 이 주제의 실용적 핵심이다. 버전 귀속은 알려진 것만 적고, 애매한 것은 라벨로 표시한다.

- **API 26(8.0)** — 오버레이 타입이 `TYPE_APPLICATION_OVERLAY` 하나로 통합. 이전의 `TYPE_SYSTEM_ALERT`/`TYPE_PHONE` 등 특권 타입은 앱에서 폐기. `Source-confirmed`
- **API 29(10)** — 완전 가림/부분 가림을 구분(`FLAG_WINDOW_IS_PARTIALLY_OBSCURED`), 백그라운드 액티비티 실행 제한 강화. `Reported`
- **API 30(11)** — 백그라운드 앱의 커스텀 뷰 토스트(오버레이 악용 통로였던) 제한. `Reported`
- **API 31(12)** — `HIDE_OVERLAY_WINDOWS` 권한과 `Window.setHideOverlayWindows(true)`: 민감 화면이 다른 앱의 SAW 오버레이를 자기 위에서 숨길 수 있음. 또한 **untrusted touch 기본 차단** — 다른 앱 창이 일정 불투명도(문서 기준 0.8) 이상으로 가린 지점의 터치는 기본적으로 차단. `Source-confirmed`

한계도 분명히 한다. 에뮬레이터로 창·입력 경로와 `dumpsys` 관측은 그대로 되지만, `FLAG_SECURE`가 막으려는 대상 중 **하드웨어 보호 디스플레이 경로**나 물리 캡처는 에뮬로 재현되지 않는다. 그리고 위 불투명도 임계값의 정확한 수치·버전별 세부는 대상 API에서 **원문 재확인 필요**다. 접근성 서비스가 콘텐츠를 읽는 경로는 별도 권한 모델이라 이 글의 창 경계와 다른 축이다.

## 정리

- WMS는 system_server의 **정책 엔진**(Z 순서·포커스·입력 대상)이고, 픽셀 합성은 SurfaceFlinger, 입력 분배는 InputDispatcher가 한다 — 셋을 구분해야 각 방어가 어디서 걸리는지 보인다.
- 탭재킹 방어선은 오버레이 권한이 아니라 **받는 창의 `filterTouchesWhenObscured` + 가림 플래그**, 그리고 Android 12의 기본 untrusted-touch 차단이다.
- `FLAG_SECURE`는 창 단위 출력 기밀성 선언일 뿐, 앱 전체·루팅·물리 캡처까지 막는 만능 스위치가 아니다.
- 방어 무게중심이 "앱 옵트인 → 플랫폼 기본값"으로 이동한 것이 이 영역의 핵심 흐름이다.

**점검 질문** — (1) `FLAG_SECURE`를 건 창의 콘텐츠가 스크린샷에서 어떻게 처리되며, 그 한계는 무엇인가? (2) 오버레이 위에서도 아래 앱이 속지 않으려면 어느 쪽에 무엇을 선언해야 하는가? (3) WMS와 SurfaceFlinger의 역할을 한 문장씩으로 구분하면?

**참고** — [WindowManager.LayoutParams(FLAG_SECURE·TYPE_APPLICATION_OVERLAY)](https://developer.android.com/reference/android/view/WindowManager.LayoutParams) · [View.setFilterTouchesWhenObscured](https://developer.android.com/reference/android/view/View#setFilterTouchesWhenObscured(boolean)) · [Android 12 동작 변경(untrusted touch·HIDE_OVERLAY_WINDOWS)](https://developer.android.com/about/versions/12/behavior-changes-all) · AOSP `services/core/java/com/android/server/wm/WindowManagerService.java`

*다음 글: [Binder proxy/stub·thread pool](/posts/android-expert-p2c14/).*
