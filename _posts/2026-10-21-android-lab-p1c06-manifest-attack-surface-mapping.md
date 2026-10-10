---
layout: post
title: "Manifest 공격 표면 자동 매핑 — exported 목록을 스크립트로 뽑기"
date: 2026-10-21 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Manifest, AttackSurface, exported]
excerpt: "펜테스트에서 먼저 세는 건 매니페스트의 exported 공격면이다. 디코드된 AndroidManifest.xml에서 exported+무권한 컴포넌트, debuggable=true, allowBackup=true, cleartext 허용, 딥링크 data 스킴을 스크립트로 뽑으면 '타 앱이 닿을 수 있는 표면'이 한눈에 나온다 — 5부 공격의 타깃 목록이 여기서 나온다."
---

앱 공격면은 매니페스트에 선언적으로 드러난다. 그래서 코드 실행 전에 매니페스트만 파싱해도 "타 앱이 닿을 수 있는 표면"을 확정할 수 있다. 이 글은 디코드된 `AndroidManifest.xml`에서 exported+무권한 컴포넌트, `debuggable`·`allowBackup`·cleartext, 딥링크 스킴을 스크립트로 뽑아 공격면을 목록화하는 방법을 정리한 기록이다. 이 목록이 이후 [5부(해킹 기법)](/posts/android-security-mastery-series-index/)와 9부(Attack Surface Mapper 프로젝트)의 근거가 된다.

> **한 줄 결론**: `exported=true && !permission`인 컴포넌트가 타 앱이 닿는 공격면이다. targetSdk<31 앱은 intent-filter만 있어도 암시적 exported이므로, 명시가 없다고 안전한 게 아니다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 매니페스트를 파싱해 외부 도달 가능한 표면을 자동 목록화한다. 선수 개념은 [APK triage(3장)](/posts/android-lab-p1c03-apk-triage/)·[apktool(5장)](/posts/android-lab-p1c05-apktool-smali/)의 매니페스트 디코드, [컴포넌트↔Binder(C21)](/posts/android-concept-atlas-c21-components-binder/)의 exported 게이트, [가시성·URI(C11)](/posts/android-concept-atlas-c11-package-visibility-uri-permission/)의 딥링크·URI다.

## 핵심 개념 — 매핑할 필드

디코드된 `AndroidManifest.xml`(apktool 또는 `aapt2 dump xmltree`)에서 다음을 추출한다:

| 필드 | 의미 |
|--|--|
| `<activity\|service\|receiver\|provider android:exported>` | 타 앱 도달 가능(**API 31+는 intent-filter 있으면 명시 필수**) |
| `android:permission` | 컴포넌트 권한 가드 |
| `<intent-filter>` + `<data android:scheme>` | 암시적 도달 + 딥링크 |
| `android:debuggable` / `android:allowBackup` | 디버그·백업 노출 |
| `android:networkSecurityConfig` / `usesCleartextTraffic` | 전송 자세(cleartext는 API 28+ 기본 off) |
| `minSdkVersion` / `targetSdkVersion` / `<uses-permission>` | 버전·요청 권한 |

**신뢰 경계와 위협 모델.** `exported=true` + 무권한 컴포넌트가 타 앱이 닿는 표면(C21)이다. `exported=false`는 같은 UID만이라 표면 밖. `debuggable=true`·`allowBackup=true`·cleartext는 추가 위험 신호다.

> **[그림 1]** 매핑 스크립트가 exported+무권한/debuggable/allowBackup/cleartext를 플래그한 출력 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱에 exported/무권한 컴포넌트를 의도적으로 넣고 매핑 스크립트로 검출한 뒤, 방어 버전과 대조한다.

## 실습 절차와 관측

### 가설
취약 버전은 exported Activity 1개·`allowBackup=true`·`cleartext=true`가 플래그되고, 방어 버전은 0건. `Inferred`

### 절차
1. `apktool d`로 매니페스트를 디코드한다.
2. XML 파싱 스크립트로 위 필드를 추출한다.
3. `exported && !permission` 컴포넌트를 목록화한다.
4. debuggable/allowBackup/cleartext/딥링크를 플래그한다.
5. 방어 버전과 diff해 표면 축소를 확인한다.

```python
# map_surface.py (자작): 디코드된 매니페스트를 파싱해 표면 플래그
import xml.etree.ElementTree as ET
ns = '{http://schemas.android.com/apk/res/android}'
root = ET.parse('work/AndroidManifest.xml').getroot()
for tag in ('activity','service','receiver','provider'):
    for c in root.iter(tag):
        exported = c.get(ns+'exported')
        perm = c.get(ns+'permission')
        has_filter = c.find('intent-filter') is not None
        if exported == 'true' and not perm:
            print(f'[EXPORTED, NO PERMISSION] {tag} {c.get(ns+"name")}')
```
`검증 필요`(스크립트는 자작)

> **[그림 2]** targetSdk<31 앱에서 명시 exported 없이 intent-filter만으로 암시적 exported가 되는 예 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
[EXPORTED, NO PERMISSION] activity com.example.DebugActivity
[FLAG] android:debuggable=true
[FLAG] usesCleartextTraffic=true
[DEEPLINK] scheme=myapp host=cb  (App Link 검증 여부 확인 필요)
```

## Root Cause — 왜 이렇게 되는가

공격면이 매니페스트에 선언적으로 드러나는 것은 Android의 컴포넌트 모델(C21) 때문이다 — 그래서 코드 실행 전에 표면을 확정할 수 있다. 다만 targetSdk<31에서는 intent-filter가 있으면 암시적으로 exported=true가 되므로, "명시 exported가 없다 = 사설"이라는 오판이 false negative를 만든다.

## 방어와 회귀 검증

- (개발자) exported 최소화·권한 가드·`allowBackup=false`·cleartext 차단·App Link 검증. CI에서 "exported 컴포넌트에 permission이 있다 / debuggable=false / cleartext 불가"를 매니페스트 파싱으로 회귀.
- (연구자) 이 목록을 5부 공격의 타깃으로 넘긴다.

**흔한 실패와 처리.** 명시 exported가 없어 놓침 → targetSdk를 확인(<31이면 암시적 규칙 적용). `aapt2 dump xmltree` 빈 출력 → `--file AndroidManifest.xml` 누락.

## 버전 차이와 한계

- API 31: intent-filter 있는 컴포넌트에 exported 명시 필수. API 28: cleartext 기본 off.
- 정적 매핑은 "선언된" 표면만 본다 — 런타임 등록 리시버·동적 컴포넌트는 동적(8장)으로.

## 정리

- `exported && !permission`이 공격면의 핵심.
- targetSdk<31은 암시적 exported에 주의.
- 정적 매핑은 선언된 표면만 — 동적으로 보완.

**점검 질문** — (1) targetSdk 29 앱에서 exported 명시가 없어도 위험할 수 있는 이유는? (2) exported인데 permission이 없으면 왜 무방비인가? (3) 딥링크 `<data scheme>`만으로 왜 App Link 검증을 확인해야 하나?

**참고** — [manifest intro](https://developer.android.com/guide/topics/manifest/manifest-intro) · [C21](/posts/android-concept-atlas-c21-components-binder/) · [C11](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) · [C46](/posts/android-concept-atlas-c46-tls-nsc-pinning/)

*다음 글: [APK 수정·zipalign·재서명](/posts/android-lab-p1c07-apk-modify-zipalign-resign/).*
