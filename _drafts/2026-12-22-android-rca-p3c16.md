---
layout: post
title: "patch diff·Patch Invariant"
date: 2026-12-22 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RCA, PatchDiff, PatchInvariant, VariantAnalysis]
excerpt: "패치 diff에서 뽑을 것은 '추가된 검사'가 아니라 그 검사가 복원하는 불변식이다. 흔한 함정: 커널 두 태그를 diff해서 바뀐 줄 전부를 그 CVE의 수정으로 읽는 것 — 실제 수정은 불리틴이 링크한 커밋 하나뿐이다."
---

근본원인분석에서 패치 diff는 가장 등급이 높은 증거다. 다른 모든 관측(툼스톤, ASan 로그, 최소 재현)은 "밖에서 본 증상"인 반면, 패치는 **벤더 자신이 무엇을 틀렸다고 인정한 자백**이기 때문이다. 그런데 여기에 조용한 함정이 하나 있다. diff가 보여주는 것은 *고침*이지 *결함*이 아니다. 그리고 diff에 새로 추가된 `if` 검사는 근본원인이 아니라, 근본원인이 위반한 **불변식(invariant)의 한 구현**일 뿐이다. 이 둘을 뭉뚱그리면 "경계 검사가 추가됐으니 오프바이원이었네" 같은 얕은 결론에서 멈춘다.

이 글은 패치 diff를 읽어 그 뒤에 있는 **Patch Invariant**(패치가 복원·집행하는 불변식)를 형식화하는 방법을 자작 데모 코드로 정리한 기록이다. 무기화는 없다 — 이미 패치된 공개 결함과 내가 만든 결함 코드에서 "불변식이 어떻게 깨졌고, 패치가 무엇을 다시 참으로 만들었나"까지만 본다.

> **한 줄 결론**: 패치 diff에서 뽑아야 할 산출물은 "추가된 검사"가 아니라 그 검사가 복원하는 **불변식**이다. 검사는 불변식의 구현이고, 불변식이야말로 근본원인 진술의 반증 가능한 형태다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 (1) 불리틴에서 정확한 수정 커밋을 어떻게 찾고, (2) 그 diff에서 추가된 guard를 역으로 읽어 빠져 있던 전제조건을 복원하며, (3) 그것을 "항상 참이어야 하는 속성" 즉 Patch Invariant로 진술하는 절차를 다룬다. 무기화, 우회, 실서비스 공격은 범위 밖이다.

선수 지식이 세 가지 깔린다. 이 파트 1장에서 증상·트리거·폴트 사이트·근본원인을 나눠 진술하는 법을 세웠고, 2장에서 Security Invariant를 "코드로 확인 가능한 술어"로 쓰는 법을 다뤘으며, 5장에서 baseline·patched·negative control 세 벌을 나란히 두고 차이를 관측하는 골격을 잡았다. Patch Invariant는 그 셋의 교차점이다 — 패치 diff가 negative control(patched)을 공짜로 주고, 거기서 뽑은 불변식이 baseline에서만 깨지는지를 검증하면 근본원인이 닫힌다.

전체 구조에서 이 장은 **단일 CVE의 RCA를 끝내는 지점**이자 다음 장(variant analysis)으로 넘어가는 다리다. 불변식을 한 번 정확히 진술해두면, 같은 불변식을 위반하는 다른 위치를 찾는 것이 곧 변종 분석이 된다.

## 핵심 개념 — guard는 불변식이 아니다

패치를 읽을 때 층위를 섞지 않는 것이 전부다. 자작 데모(untrusted `Parcel`에서 개수 `n`을 읽어 배열을 할당하는 프레임워크 스타일 코드)로 다섯 층위를 나누면 이렇다.

| 층위 | 질문 | 예(자작 데모) |
|--|--|--|
| 증상(Symptom) | 무엇이 관측됐나 | `NegativeArraySizeException`, 또는 거대 할당에 의한 `OutOfMemoryError`(둘 다 Java 크래시 로그 — logcat의 FATAL EXCEPTION이지 네이티브 툼스톤이 아니다) |
| 트리거(Trigger) | 무슨 입력이 유발했나 | `n`에 음수/거대값을 담은 조작 `Parcel` |
| 폴트 사이트(Fault site) | 어디서 터졌나 | `new Entry[n]` 한 줄 |
| 근본원인(Root cause) | 왜 가능한가 | 미검증 untrusted `n`을 할당 크기로 그대로 사용 |
| 불변식(Invariant) | 무엇이 항상 참이어야 했나 | `0 ≤ n ≤ MAX ∧ n이 잔여 Parcel 데이터와 일치` |

패치가 넣는 `if (n < 0 || n > MAX) throw`는 이 표의 마지막 줄이 아니라 **그 줄의 부분 구현**이다 `Inferred`. 왜 부분이냐면, 불변식의 앞 절(`0 ≤ n ≤ MAX`)만 집행하고 뒤 절(`n이 실제 남은 데이터와 일치`)은 손대지 않을 수 있기 때문이다. 이 간극이 나중에 불완전 패치·변종 분석의 출발점이 된다.

정리하면 세 가지를 분리해서 기록한다. **추가된 guard**(diff의 `+` 줄), 그 guard가 **금지하는 값의 범위**(빠져 있던 전제조건), 그리고 그 전제조건을 일반화한 **불변식**(구현과 독립된 속성). 세 번째만이 다른 코드 위치에 이식 가능한 산출물이다.

> **[그림 1]** Android Security Bulletin의 한 CVE 항목에서 References 열의 AOSP 커밋 링크를 눌러 android.googlesource.com의 실제 커밋 diff로 이동한 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

이 방법론의 신뢰 경계는 **untrusted 입력이 처음 프로세스 안으로 들어오는 지점**이다. 데모에서는 `parcel.readInt()`가 그 경계다 — `Parcel`은 IPC로 다른 앱/프로세스가 채운 데이터고, 그 값은 서명·범위·자기일관성 어느 것도 보장되지 않는다. 위협 행위자는 이 경계에 임의의 `n`을 밀어 넣을 수 있는 로컬 앱이다. `Source-confirmed`(Android Platform Security Model — 아래 참고 링크)

여기서 위협 모델의 요점은 "누가 값을 통제하느냐"다. 불변식을 진술할 때 이 통제 관계를 명시해야 한다 — "`n`은 항상 유효하다"가 아니라 "**untrusted 경계를 넘어온** `n`은 사용 전에 `0 ≤ n ≤ MAX`로 검증돼야 한다"가 올바른 형태다. 통제 주체를 빼먹은 불변식은 자기 코드에선 늘 참으로 보여서, 변종을 찾을 때 무력하다.

## 분석

패치 diff에서 불변식을 뽑는 절차는 여섯 단계다. 자작 데모 저장소에서 그대로 밟는다.

### 절차

1. **불리틴에서 수정 커밋을 특정한다.** 두 릴리스 태그를 통째로 diff하지 말고, 불리틴이 그 CVE에 링크한 개별 커밋만 본다. 태그 diff는 수백 개의 무관한 변경을 함께 담아, 바뀐 줄 전부를 그 CVE 수정으로 오독하게 만든다. `Inferred`
2. **수정 커밋의 diff만 연다.** `+`/`-` 줄과 이동된 코드(할당이 검사 뒤로 밀렸는지)를 분리해 읽는다.
3. **guard를 역으로 읽는다.** 추가된 검사가 *금지*하는 값 범위가 곧 *빠져 있던 전제조건*이다. `n < 0 || n > MAX`를 던진다면 빠진 전제는 `0 ≤ n ≤ MAX`.
4. **guarded 값을 발원지까지 추적한다(taint).** `n`이 `parcel.readInt()`에서 왔음을 확인해 신뢰 경계를 고정한다. 이 추적이 위협 모델을 확정한다.
5. **불변식을 속성으로 진술한다.** 특정 검사 문장이 아니라 통제 주체를 포함한 술어로 쓴다.
6. **반증 가능한 술어로 옮긴다.** baseline에서 깨지고 patched에서 성립하는지 확인한다(5장의 negative control 골격).

```bash
# 자작 데모 저장소 — 태그 전체가 아니라 수정 커밋의 diff만 본다
git show --stat a1b2c3d
git show a1b2c3d -- framework/EntryList.java
```

예시 출력(교체):

```
    framework/EntryList.java | 3 +++
    1 file changed, 3 insertions(+)

@@ -41,6 +41,9 @@ public static EntryList createFromParcel(Parcel in) {
     int n = in.readInt();
+    if (n < 0 || n > MAX_ENTRIES) {
+        throw new BadParcelableException("bad count: " + n);
+    }
     Entry[] entries = new Entry[n];
     for (int i = 0; i < n; i++) {
         entries[i] = Entry.CREATOR.createFromParcel(in);
```

> **[그림 2]** 자작 취약 코드의 pre-patch/post-patch를 `git show`로 나란히 놓고, 추가된 guard와 그것이 복원하는 불변식을 주석으로 표기한 터미널 — *실측 스크린샷 자리*

### 관측 결과

diff에서 뽑은 세 산출물을 분리해 적으면 이렇게 된다.

- **추가된 guard**: `if (n < 0 || n > MAX_ENTRIES) throw`
- **금지된 범위 / 빠진 전제**: `n < 0` 및 `n > MAX_ENTRIES`
- **Patch Invariant**: *"untrusted `Parcel`에서 읽은 개수 `n`은 배열 할당 전에 `0 ≤ n ≤ MAX_ENTRIES`를 만족해야 하고, `n`은 잔여 데이터로 실제 읽을 수 있는 개수와 일치해야 한다."*

세 번째 줄의 뒷 절이 이 diff에 없다는 점이 관측의 핵심이다. guard는 상한/하한만 막았고, `n`이 잔여 바이트와 일치하는지는 여전히 검증되지 않는다 — 이는 취약점이 아직 남았다는 단정이 아니라, **변종 분석에서 확인할 열린 질문**이다. `Inferred`

## Root Cause — 왜 이렇게 되는가

왜 diff만 읽으면 틀리나. diff는 "무엇을 바꿨나"만 보여주고 "왜 그 값이 잘못될 수 있었나"는 보여주지 않기 때문이다. `new Entry[n]`이 폴트 사이트지만, 근본원인은 그 한 줄이 아니라 **untrusted 값이 검증 없이 신뢰 경계를 넘어 할당 크기로 흘러간 경로 전체**다. guard는 그 경로의 끝단에 마개를 하나 꽂았을 뿐이고, 근본원인 진술은 경로의 시작(taint origin)까지 포함해야 완결된다.

불리틴 자체도 근본원인을 알려주지 않는다. 불리틴 표는 CVE 번호·심각도·영향받는 컴포넌트만 요약하고, 실제 변경은 링크된 커밋에 있다. 게다가 불리틴은 게시 후에도 갱신될 수 있는데 그 갱신이 항상 눈에 띄게 표기되지는 않는다 — 그래서 표의 요약이 아니라 **링크된 커밋 자체**를 근거로 삼아야 한다. `Inferred` 표를 옮겨 적다 오집계하거나, 태그 diff를 CVE 수정으로 읽는 실수가 여기서 나온다.

정리하면 근본원인의 올바른 형태는 "패치가 검사를 추가했다"가 아니라 "**불변식 X가 신뢰 경계 B에서 집행되지 않아, untrusted 값이 폴트 사이트 F까지 도달했다**"이다. Patch Invariant는 이 X를 코드와 독립된 속성으로 고정한 것이다.

## 방어와 회귀 검증

Patch Invariant의 진짜 값은 **재사용 가능한 회귀 검증**이 된다는 데 있다. 한 번 술어로 써두면 세 가지로 곧장 쓰인다.

- **negative control 회귀 테스트**: baseline(pre-patch)에서 `0 ≤ n ≤ MAX` 위반 입력이 폴트를 일으키고, patched에서는 `BadParcelableException`으로 안전히 거부되는지 자동 확인. 5장 골격을 그대로 재활용한다.
- **변종 탐색의 검색어**: 불변식을 통제 주체 포함으로 써뒀으면, "`parcel.readInt()` 결과를 검증 없이 배열·버퍼 크기로 쓰는 다른 위치"가 곧 변종 후보다. 이것이 다음 장의 입력이 된다.
- **패치 완결성 점검**: 불변식의 모든 절이 diff에 반영됐는지 대조. 데모에서 뒷 절(잔여 데이터 일치)이 빠졌다는 관측이 여기서 나왔다.

주의할 함정. guard가 있다고 불변식이 완전히 집행됐다고 단정하지 말 것 — 검사의 범위(어느 절을 막는가)와 위치(경계에서 막는가, 아니면 폴트 사이트 직전에서만 막는가)를 따로 확인해야 한다. 그리고 영향 산정은 정직하게. 이 데모의 결함은 조작 `Parcel`로 예외/할당 폭주를 일으키는 **DoS·자원 고갈** 등급이지, 그 자체로 RCE가 아니다. 크래시를 취약점으로, DoS를 RCE로 부풀리는 것은 패치 diff 오독만큼 흔한 실수다.

## 정리

- 패치 diff는 최고 등급 증거이나, 보여주는 것은 *고침*이지 *결함*이 아니다 — 추가된 guard를 역으로 읽어 빠진 전제조건을 복원해야 한다.
- 산출물은 특정 검사가 아니라 **통제 주체를 포함한 불변식**이다. 이것만이 다른 위치로 이식 가능하고 변종 분석의 입력이 된다.
- 근거는 불리틴 표가 아니라 **링크된 커밋 자체**다. 두 태그 통 diff를 CVE 수정으로 읽지 말 것.
- 영향은 폴트 사이트가 아니라 불변식 위반 경로 전체로 진술하고, DoS/정보노출/RCE 경계를 부풀리지 말 것.

**점검 질문** — (1) 패치에 추가된 `if` 검사와 Patch Invariant는 왜 같은 것이 아닌가? (2) 불리틴에서 근본원인의 근거로 표가 아니라 커밋을 봐야 하는 이유는? (3) 불변식을 "통제 주체 포함"으로 진술해야 변종 분석에 쓸 수 있는 이유는?

**참고** — [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [AOSP 소스 브라우저(android.googlesource.com)](https://android.googlesource.com) · [Android Platform Security Model 문서](https://source.android.com/docs/security)

*다음 글: [불완전 패치·variant analysis](/posts/android-rca-p3c17/).*
