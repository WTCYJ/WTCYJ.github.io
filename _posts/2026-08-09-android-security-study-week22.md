---
layout: post
title: "Android 앱 보안 분석 22주차 - 쿼터의 키를 누가 정하는가"
date: 2026-08-09 20:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, CVE-2022-20425, 근본원인분석, 신뢰경계, Binder, ZenModeHelper, CWE-400, 자원소모, 시큐어코딩, 학습기록]
excerpt: "재현도 했고 코드도 확인했으니 남은 것은 왜 이런 일이 생겼는지 설명하는 일입니다. 한도 검사 코드를 신뢰 경계 위에 올려놓고 보니 결함이 한 줄로 정리됐습니다. 개수를 세는 키를 호출자가 정하고 있었습니다. 그리고 제대로 셀 수 있는 값은 이미 같은 레코드에 저장돼 있었습니다."
---

> **진행 구간**: 24주 로드맵의 22주차 — 근본 원인 분석
> **대상**: CVE-2022-20425 (`ZenModeHelper.addAutomaticZenRule`)
> **이전 글**: [21주차 안전한 검증](/posts/android-security-study-week21/) · [20주차 CVE 재현](/posts/android-security-study-week20/) · [24주 로드맵](/posts/android-security-study-roadmap/)

20주차에 재현하고 21주차에 코드로 확정했습니다. 이제 남은 질문은 "무엇이 일어났는가"가 아니라 **"왜 이렇게 됐는가"** 입니다.

로드맵이 정한 순서가 있습니다. 패치 diff → 호출 위치 → 신뢰 경계 → 검증 누락 → 수정 논리. 이번 회차는 그 순서대로 따라가 봤고, 결함이 한 줄로 정리됐습니다.

이번 글의 근거 코드는 전부 **에뮬레이터 이미지에서 뽑아 디컴파일한 것**입니다. 소스 태그가 아니라 실제로 실행되는 빌드입니다. 18주차에 태그와 배포 이미지가 다르다는 것에 한 번 걸렸기 때문에 그 뒤로는 이미지 쪽을 봅니다.

---

## 배경 개념 - 자원 한도도 보안 통제다

권한 검사나 암호화만 보안 통제는 아닙니다. **개수 제한**도 통제입니다. 앱 하나가 시스템 자원을 무제한으로 쌓을 수 있으면 다른 앱과 사용자가 영향을 받습니다. CWE-400 이 그 범주(Uncontrolled Resource Consumption)입니다.

그런데 개수 제한에는 권한 검사에 없는 고민이 하나 더 붙습니다. **무엇을 단위로 셀 것인가** 입니다. "100개까지"라고 정해도 100개를 세는 단위가 무엇이냐에 따라 의미가 완전히 달라집니다. 앱당 100개와 이름당 100개는 다른 통제입니다.

이번 CVE 는 정확히 그 지점의 문제였습니다.

---

## 1. 호출 흐름

앱이 자동 Zen 규칙을 하나 등록할 때 지나가는 길입니다.

```
앱  NotificationManager.addAutomaticZenRule(rule)
      └ 프레임워크가 호출자 패키지명을 인자로 채워 Binder 로 보냅니다
─────────────────────── Binder 경계 ───────────────────────
system_server  NotificationManagerService.addAutomaticZenRule(rule, pkg)
      1) name / conditionId null 검사
      2) owner 와 configurationActivity 가 둘 다 null 이면 거부
      3) checkCallerIsSameApp(pkg)          ← 호출 UID 로 패키지 확인
      4) ZenPolicy 는 특정 필터에서만 허용
      5) enforcePolicyAccess(callingUid)
      └ ZenModeHelper.addAutomaticZenRule(pkg, rule, reason)
            6) 컴포넌트 해석 (owner 또는 configurationActivity)
            7) 앱이 선언한 한도를 컴포넌트 메타데이터에서 읽음
            8) ★ 개수 검사 ← 여기가 결함 지점
            9) populateZenRule(pkg, …)      ← rule.pkg = pkg 로 저장
           10) 설정 갱신 → notification_policy.xml 로 영속화
```

3번과 5번이 보안 검사입니다. 3번은 "네가 말한 그 패키지가 정말 너인가"를 확인하고, 5번은 "그 패키지에 정책 접근이 허용돼 있는가"를 확인합니다. 둘 다 제대로 걸려 있습니다.

문제는 8번이었습니다.

---

## 2. 신뢰 경계에서 값이 갈린다

Binder 를 건너오는 순간, 시스템이 다루는 값은 두 종류로 갈립니다.

![Binder 경계를 기준으로 인증된 신원(pkg)과 호출자가 정하는 값(ComponentName)이 갈리고, 패치 전에는 후자를 한도 계산의 키로 썼음을 보여주는 도식](/assets/img/android-security-study/25-trust-boundary.svg)

| 값 | 시스템이 믿을 수 있는가 |
| --- | --- |
| 호출 UID | **예** — 커널이 보증합니다 |
| 패키지명 `pkg` | **예** — `checkCallerIsSameApp(pkg)` 가 UID 와 대조합니다 |
| `rule.name` | 아니오 |
| `rule.owner` | 아니오 — 앱이 정합니다 |
| `rule.configurationActivity` | 아니오 — 앱이 정합니다 |
| `rule.conditionId` | 아니오 |

**인증된 신원은 `pkg` 하나입니다.** 나머지는 앱이 객체에 채워 보낸 데이터입니다.

---

## 3. 결함 — 세는 키를 호출자가 정했다

패치 전 검사식입니다.

```java
int newRuleInstanceCount = getCurrentInstanceCount(automaticZenRule.getOwner())
        + getCurrentInstanceCount(automaticZenRule.getConfigurationActivity()) + 1;
if (newRuleInstanceCount > 100 || (ruleInstanceLimit > 0 && ruleInstanceLimit < newRuleInstanceCount)) {
    throw new IllegalArgumentException("Rule instance limit exceeded");
}
```

그리고 세는 함수입니다.

```java
public int getCurrentInstanceCount(ComponentName cn) {
    if (cn == null) return 0;
    int count = 0;
    synchronized (this.mConfig) {
        for (ZenModeConfig.ZenRule rule : this.mConfig.automaticRules.values()) {
            if (cn.equals(rule.component) || cn.equals(rule.configurationActivity)) count++;
        }
    }
    return count;
}
```

카운팅 키가 `ComponentName` 입니다. 그리고 2장 표에서 봤듯 **그 값은 앱이 정합니다.**

그래서 한도의 의미가 "앱당 100개"가 아니라 **"앱이 대는 이름당 100개"** 가 됩니다. 새 이름을 만드는 비용은 사실상 0 입니다. 액티비티를 새로 구현할 필요도 없고 매니페스트 한 줄이면 됩니다.

```xml
<activity-alias android:name=".Alias1" android:targetActivity=".MainActivity" android:exported="false" />
```

20주차에 이 한 줄을 네 번 써서 컴포넌트를 5개로 만들었더니 한도가 그대로 5배가 됐습니다. 501번째에서 거부됐습니다.

---

## 4. 결과 해석

### 4-1. 왜 이런 코드가 됐을까

`ComponentName` 으로 세는 것이 처음부터 이상한 선택은 아니었다고 봅니다.

원래 이 자리에 있던 한도는 `ruleInstanceLimit` 하나였습니다. 이건 **앱이 자기 ConditionProviderService 에 메타데이터로 선언하는 값**입니다(`META_DATA_RULE_INSTANCE_LIMIT`). 그 한도의 주인이 컴포넌트이므로, 검사할 때 컴포넌트 기준으로 세는 것은 자연스럽습니다.

문제는 나중에 **시스템이 강제하는 상한이 같은 식에 얹혔을 때** 생겼습니다. 상수 이름은 `RULE_LIMIT_PER_PACKAGE` 인데, 비교 대상은 컴포넌트 단위로 센 변수였습니다.

```java
if (newRuleInstanceCount > RULE_LIMIT_PER_PACKAGE || …)
//     ^ 컴포넌트 단위          ^ 이름은 패키지 단위
```

이름과 실제가 어긋난 채로 남아 있었습니다. 새 통제를 기존 식에 얹으면서 단위가 맞는지 확인하지 않은 형태입니다.

### 4-2. 수정이 17줄로 끝난 이유

```java
int newPackageRuleCount = getPackageRuleCount(pkg) + 1;
if (newPackageRuleCount > RULE_LIMIT_PER_PACKAGE
        || (ruleInstanceLimit > 0 && ruleInstanceLimit < newRuleInstanceCount)) {
```

수정의 성격은 세 가지입니다.

**첫째, 키를 인증된 신원으로 바꿨습니다.** 시스템 상한은 `pkg` 로, 앱 선언 한도는 그대로 컴포넌트 기준으로 셉니다. 두 한도의 주인이 다르니 각자 맞는 키를 쓰게 된 것입니다.

**둘째, 새 상태를 만들지 않았습니다.** `rule.pkg` 는 9번 단계의 `populateZenRule` 이 이미 저장하고 있었습니다. 필요한 값이 레코드에 있었는데 계산에 쓰이지 않고 있었을 뿐입니다. 그래서 마이그레이션도, 새 필드도 필요 없었습니다.

**셋째, 기존 동작을 깨지 않았습니다.** 앱 선언 한도 검사를 지우지 않고 OR 로 나란히 뒀습니다. 자기 한도를 100보다 낮게 선언한 앱은 그대로 그 한도를 적용받습니다.

### 4-3. 부수 관찰 — 코드에서만 본 것

`getCurrentInstanceCount` 는 `cn` 이 **호출자 패키지에 속하는지 확인하지 않습니다.** 컴포넌트 해석을 하는 `getActivityInfo` 도 전역 조회라 자기 패키지로 제한되지 않습니다.

이 경로가 실제로 열려 있는지는 **확인하지 않았습니다.** CVE 재현에 필요하지 않았고, 확인하려면 다른 앱의 컴포넌트를 카운팅 키로 쓰는 실험을 해야 해서 범위 밖으로 뒀습니다. 코드를 읽다 보인 것이라 적어만 둡니다.

---

## 5. 일반화 — 다음에 같은 것을 찾으려면

이 결함의 형태는 Zen 규칙에 국한되지 않습니다. 한 문장으로 줄이면 이렇습니다.

> **쿼터의 키는 신뢰 경계에서 인증된 주체여야 합니다.**
> 호출자가 값을 바꿔 새 카운터를 만들 수 있으면 그 한도는 한도가 아닙니다.

점검 질문으로 바꾸면 코드를 볼 때 바로 쓸 수 있습니다.

1. 이 한도는 무엇을 단위로 세는가? 그 단위 값을 **누가 정하는가?**
2. 호출자가 그 값을 바꾸면 카운터가 갈라지는가? 바꾸는 비용은 얼마인가?
3. 인증된 신원이 이미 레코드에 저장돼 있는데 계산에는 안 쓰이고 있지 않은가?

이번 경우 세 번째 답이 "그렇다"였고, 그래서 수정이 17줄이었습니다. 필요한 값이 이미 있는데 안 쓰고 있는 상황은, 고치기는 쉽지만 눈에는 잘 안 띕니다.

한 가지 더 붙이면, **상수 이름과 실제 세는 단위가 맞는지 보는 것**만으로도 이 결함은 보였습니다. `RULE_LIMIT_PER_PACKAGE` 와 `newRuleInstanceCount` 가 한 줄에 있었습니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 상태 |
| --- | --- |
| 1~21주 | 완료 |
| **22주 근본 원인 분석** | **완료** — 호출 흐름·신뢰 경계·수정 논리 정리 |
| 23~24주 최종 보고서 | 다음 |

영향을 다시 정리해 둡니다.

- **필요 조건**: 정책 접근 부여. 매니페스트 권한 선언은 필요 없습니다.
- **얻는 것**: 규칙 개수 상한의 배수 증폭. 규칙은 영속화되므로 재부팅해도 남습니다.
- **얻지 못하는 것**: 권한 상승도 데이터 접근도 아닙니다. 자원 소모 계열입니다.
- **관측 범위**: 한도가 발동하는 경계값까지입니다. 기기를 사용 불능으로 만드는 실험은 하지 않았습니다.

한계도 적어둡니다. 4-1 의 "왜 이렇게 됐을까"는 **코드 형태에서 읽어낸 해석**입니다. 커밋 메시지나 설계 문서로 확인한 것이 아닙니다. 4-3 의 부수 관찰은 미검증입니다.

---

## 마치며

이번 회차는 새로 측정한 것이 없습니다. 이미 가진 코드를 신뢰 경계 위에 올려놓고 다시 읽은 것이 전부입니다.

그런데 그렇게 놓고 보니 결함이 훨씬 단순해졌습니다. "한도 검사가 잘못됐다"가 아니라 **"세는 키를 호출자가 정하고 있었다"** 입니다. 앞의 문장으로는 다른 코드에서 같은 것을 찾을 수 없지만, 뒤의 문장으로는 찾을 수 있습니다.

그리고 고치는 데 필요한 값이 이미 같은 레코드에 저장돼 있었다는 점이 오래 남습니다. 없어서 못 센 게 아니라, 있는데 안 쓰고 있었습니다.
