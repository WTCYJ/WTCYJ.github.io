---
layout: post
title: "race·TOCTOU RCA"
date: 2026-12-20 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, TOCTOU, RaceCondition, 동시성, RCA, ThreadSanitizer]
excerpt: "레이스는 재현이 안 된다고 없는 게 아니다. 데이터 레이스(메모리 UB)와 TOCTOU(검사-사용 논리 결함)는 서로 다른 층위이고, 크래시 없이 불변식만 조용히 깨는 레이스가 종종 더 위험하다."
---

레이스 버그는 근본원인분석(RCA)의 시금석이다. 한 번은 크래시가 나고 열 번은 멀쩡하니, 초심자는 "재현이 안 되면 버그가 없다"고 결론 내리고 넘어간다. 이게 가장 값비싼 오판이다. 레이스에서 재현 실패는 결함의 부재가 아니라 **승률(win rate)이 낮다는 것**일 뿐이고, 결함은 코드에 그대로 박혀 있다. RCA는 이 비결정성 아래에서 "검사와 사용 사이에 상태가 바뀔 수 있다"는 딱 하나의 구조적 사실을 끄집어내는 작업이다.

이 글은 race와 TOCTOU(Time-of-Check to Time-of-Use)를 이 파트의 4층위 프레임(증상/트리거/폴트 사이트/근본원인)에 얹어 형식화하고, 자작 결함 앱으로 논리 레이스를 관측한 뒤 그것이 커널 더블 페치로 어떻게 격상되는지를 정리한 기록이다. 무기화가 아니라 "프리미티브가 존재한다"까지만 간다.

> **한 줄 결론**: TOCTOU의 근본원인은 "검사와 사용 사이에 상태가 바뀔 수 있다"는 것 하나다. 그래서 진짜 증거는 크래시가 아니라 security invariant 위반이며, 재현은 존재 여부 문제가 아니라 승률 문제다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 것은 세 가지다. (1) 데이터 레이스·레이스 컨디션·TOCTOU·더블 페치의 층위 구분, (2) 비결정 버그를 결함으로 확정하는 관측 방법(스트레스 + 불변식 검증 + 인터리빙 창 확대), (3) 논리 레이스와 메모리 손상 레이스의 익스플로잇 가능성 경계를 정직하게 나누는 트라이아지.

선수 지식은 이 파트 안에서 이미 깔았다. **1장**의 증상/트리거/폴트 사이트/근본원인 구분이 이 글의 뼈대이고, **2장**의 security invariant 작성법이 레이스의 "진짜 증거"를 정의한다 — 레이스에서 관측할 것은 크래시가 아니라 깨진 불변식이다. **7장**의 crash와 exploitability 구분은 여기서 다시 결정적이다. 그리고 바로 앞 **13장**의 UAF도 상당수가 레이스가 원인인 lifetime 결함이라, 이 글은 그 원인 계층을 한 단계 위에서 다시 본다.

전체 구조에서 이 장은 "동시성 결함"이라는 원인 계열의 대표다. 이후 15장(자원 고갈·DoS)이 다른 계열로 갈라지고, 16장부터의 patch diff·variant 분석은 여기서 확정한 근본원인을 패치와 대조하는 단계로 이어진다.

## 핵심 개념 — 네 층위와 TOCTOU 창(window)

먼저 용어를 갈라야 트라이아지가 꼬이지 않는다. 흔히 뭉뚱그리는 네 단어는 서로 다른 층위다.

- **데이터 레이스(data race)**: 동기화 없는 동시 접근이고 최소 하나가 쓰기다. C/C++에선 정의상 정의되지 않은 동작(UB)이다. `Source-confirmed`
- **레이스 컨디션(race condition, CWE-362)**: 결과가 실행 순서·타이밍에 의존하는 상위 논리 결함이다. 원자적 자료형을 써서 데이터 레이스가 없어도, 논리 순서가 틀리면 여전히 레이스 컨디션이다. `Source-confirmed`
- **TOCTOU(CWE-367)**: 검사(time-of-check)와 사용(time-of-use)이 비원자적이고 그 사이에 상태가 바뀌는 특정 레이스 컨디션이다. `Source-confirmed`
- **더블 페치(double-fetch)**: 커널이 같은 유저 공간 주소를 두 번 `copy_from_user` 하고, 그 사이 유저가 값을 바꿔 크기/데이터가 불일치하는 TOCTOU의 커널판이다. 학계 조사에서 실제 취약점으로 이어진 사례가 다수 보고됐다. `Reported`

여기서 콕 집을 오개념: **모든 TOCTOU가 데이터 레이스는 아니고, 모든 데이터 레이스가 보안 결함도 아니다.** 데이터 레이스와 레이스 컨디션을 같은 말로 쓰면, "동기화 툴이 조용하니 문제없다"는 잘못된 안심에 빠진다. 툴이 잡는 것과 결함의 존재는 다른 축이다.

이제 4층위에 얹는다. 이 표 하나가 레이스 RCA의 채점표다.

| 층위 | race/TOCTOU에서의 의미 | 예 |
|--|--|--|
| 증상(Symptom) | 간헐적·부하 시에만·비결정적 | 가끔 음수 잔액, 드문 KASAN, 재부팅하면 사라짐 |
| 트리거(Trigger) | 동시 접근 + 특정 인터리빙 | 두 스레드가 check와 use 사이를 교차 통과 |
| 폴트 사이트(Fault Site) | 잘못된(낡은) 값이 실제로 쓰이는 지점 | `balance -= amount` 가 stale check로 실행 |
| 근본원인(Root Cause) | 검사-사용 비원자성 = 동기화 부재 | check 결과가 use 시점엔 이미 낡음 |

핵심은 폴트 사이트와 근본원인의 분리다. 크래시가 나는 줄(폴트 사이트)에 락을 걸어봐야, 진짜 원인인 "check와 use가 나뉘어 있다"를 고치지 못하면 창만 좁아질 뿐 결함은 남는다. `Inferred`

> **[그림 1]** 자작 `withdraw()` 소스에서 time-of-check 줄과 time-of-use 줄, 그리고 그 사이 인터리빙 창을 주석으로 표시한 에디터 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 결함 코드**로만 진행한다. 제3자 앱·실서비스·실기기 공격은 없다. 최소 개념용 논리 레이스를 호스트 JVM에서 스트레스로 드러내고(가장 빠른 재현기), 같은 결함 클래스가 Android ART·NDK·커널에서 어떻게 격상되는지는 관측 없이 서술로만 격리한다. 커널 더블 페치는 이미 공개·정리된 결함 클래스로만 다루고, 무기화된 완성 익스플로잇은 만들지 않는다.

## 실습 절차와 관측

### 가설
- **가설 A** — check-then-act가 비원자적인 `withdraw()`는, 두 스레드가 잔액 100에서 동시에 100을 인출하면 둘 다 검사를 통과해 `balance < 0`(불변식 위반)이 발생한다. `Inferred`
- **가설 B** — `Thread.yield()`로 인터리빙 창을 넓혀도 **새 버그를 만드는 게 아니라 승률만 올라간다**. 즉 창을 좁히면 위반이 드물어질 뿐 사라지지 않는다. `Inferred`

### 절차
1. 아래 최소 결함 코드를 저장한다(`balance >= 0` 이 security invariant).
2. `javac`로 컴파일하고, N회 스트레스 루프로 매 회 두 스레드를 경쟁시킨다.
3. 매 회 종료 후 `balance < 0` 을 세어 불변식 위반 횟수를 기록한다.
4. `yield()` 유무로 위반 횟수가 어떻게 변하는지 대조한다(창 크기 = 승률).

```java
// Vault.java — 자작 결함(개념용, 최소). 논리 레이스: check-then-act 비원자성.
final class Vault {
    private int balance = 100;              // security invariant: balance >= 0
    boolean withdraw(int amount) {
        if (balance >= amount) {            // (1) time-of-check
            Thread.yield();                 // 인터리빙 창 확대 — 버그 생성이 아니라 노출
            balance -= amount;              // (2) time-of-use : stale check로 실행 가능
            return true;
        }
        return false;
    }
    int balance() { return balance; }

    public static void main(String[] a) throws Exception {
        int neg = 0, N = 1000;
        for (int t = 0; t < N; t++) {
            Vault v = new Vault();
            Thread x = new Thread(() -> v.withdraw(100));
            Thread y = new Thread(() -> v.withdraw(100));
            x.start(); y.start(); x.join(); y.join();
            if (v.balance() < 0) neg++;     // 불변식 위반 카운트
        }
        System.out.printf("runs=%d invariant_violations(balance<0)=%d%n", N, neg);
    }
}
```

```bash
javac Vault.java
java Vault
```

> **[그림 2]** 스트레스 루프 실행 결과 — `invariant_violations` 가 0이 아니고, `yield()` 를 뺀 실행과 나란히 둔 대조 터미널 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
$ java Vault
runs=1000 invariant_violations(balance<0)=37
# yield() 제거 후
runs=1000 invariant_violations(balance<0)=2
```

정확한 숫자는 실행마다·기기마다 다르다 — 이게 레이스의 본질이다. 요점은 두 가지다. 첫째, 위반 횟수가 **0이 아니다**(결함 존재의 확정 증거는 크래시가 아니라 깨진 불변식). 둘째, 창을 좁히면(`yield` 제거) 관측값이 0에 수렴할 수 있으나, 이는 승률만 낮아진 것이지 실제 위반율이 0이 되거나 결함이 사라진 것은 아니다 — 표본에서 0을 봐도 '버그 없음'이 아니며, 재현 난이도는 승률의 문제이지 결함 존재의 문제가 아니다. `Inferred` 이 코드는 ART에서도 같은 결함 클래스라 동일하게 나타날 것으로 추정되며(관측 미수행), Android 앱에선 두 스레드를 `Service`에서 돌리고 `adb logcat` 으로 같은 위반을 확인할 수 있을 것으로 보인다. `Inferred`

## Root Cause — 왜 이렇게 되는가

근본원인은 폴트 사이트가 아니라 **검사와 사용이 하나의 원자적 단위가 아니라는 사실**이다. `if (balance >= amount)` 가 참을 반환한 순간의 `balance` 값은, `balance -= amount` 가 실행되는 시점엔 이미 다른 스레드가 갱신한 낡은 값(stale)일 수 있다. 두 스레드 모두 "잔액 100 ≥ 100"을 보고 통과한 뒤 각자 100을 빼면 -100이 된다. 락을 `balance -= amount` 한 줄에만 걸어도 소용없다 — 원인은 "검사~사용" 구간 전체의 비원자성이라, 그 구간을 통째로 원자화해야 낫는다. `Source-confirmed`

이 논리 레이스가 커널로 올라가면 성격이 바뀐다. 더블 페치에서 첫 번째 페치로 읽은 `size` 로 버퍼를 할당·검증하고, 두 번째 페치로 그 크기만큼 데이터를 복사하는 사이 유저가 `size` 를 키우면, 검증은 옛 값 기준이고 복사는 새 값 기준이라 **OOB write** 가 된다. 여기선 "낡은 값"이 산술 결과가 아니라 **메모리 경계**라, 논리 오류가 메모리 손상으로 격상된다. `Reported` 뿌리는 동일하다 — 검사 대상과 사용 대상이 같은 값이 아니게 되는 것.

**익스플로잇 가능성은 정직하게 나눠야 한다(7장 연장).** 자바판 불변식 위반은 메모리 안전성을 깨지 않는다. 영향은 그 불변식이 지키던 것에 종속된다 — 잔액·쿼터·인증 플래그라면 이중 인출·한도 우회 같은 **로직 취약점**이 될 수 있으나, RCE는 아니다. 커널 더블 페치는 메모리 손상 프리미티브(OOB 읽기→정보 노출, OOB 쓰기→LPE 후보)를 주지만, **레이스를 안정적으로 이겨야** 프리미티브가 성립한다. 승률이 낮으면 실질적으로 DoS·간헐적 크래시에 가깝다. RCA에서 "결함 존재(비원자 시퀀스가 코드에 있음)"는 결정적으로 증명되지만, "익스플로잇 가능성(레이스를 이기고 프리미티브를 제어로 전환)"은 확률과 프리미티브 품질의 별개 문제다. 이 둘을 붙여서 레이스를 곧장 RCE로 부르면 과장이다. `Inferred`

## 방어와 회귀 검증

방어는 "검사~사용" 구간을 원자화하는 것이다.

- **원자성 확보**: `synchronized`/`ReentrantLock` 으로 구간 전체를 감싸거나, `AtomicInteger.compareAndSet` 루프로 "읽은 값이 그대로일 때만 갱신"을 보장한다. DB 자원이면 트랜잭션(예: `SELECT ... FOR UPDATE`)으로 경합을 직렬화한다.
- **커널은 single-fetch**: 유저 값을 **한 번만** 복사해 로컬 복사본만 쓰고, 그 복사본으로 재검증한다. 두 번째 페치 자체를 없애는 게 정석이다.

회귀 검증은 비결정성을 다뤄야 하므로 일반 단위 테스트만으로는 부족하다.

- **스트레스 + 불변식 assert 를 CI에 고정**: 위 하네스처럼 반복 횟수와 인터리빙 창(`yield`·바쁜 대기)을 키워 승률을 올린 뒤 `assert balance >= 0` 로 위반을 잡는다. 통과 조건은 "1회 통과"가 아니라 "N회 위반 0"이어야 한다.
- **동시성 새니타이저 병행**: 네이티브(NDK)는 ThreadSanitizer(TSan), 커널은 KCSAN이 데이터 레이스를 잡는다. `Source-confirmed` 다만 **TSan은 데이터 레이스를 잡지, 원자 변수 위의 상위 레이스 컨디션(논리 순서 오류)은 못 잡는다** — 그래서 불변식 검증이 반드시 병행돼야 한다. `Source-confirmed`
- Android에서의 TSan 지원 범위·버전은 NDK/플랫폼에 따라 달라 **버전 확인 필요**. 자바/ART 레이어엔 TSan 같은 표준 데이터-레이스 탐지기가 없으므로 이 계층은 스트레스+불변식이 주력이다. `Inferred`

## 정리

- TOCTOU의 근본원인은 단 하나 — 검사와 사용이 비원자적이라 검사 결과가 사용 시점에 낡을 수 있다. 폴트 사이트가 아니라 이 구간을 원자화해야 낫는다.
- 레이스의 확정 증거는 크래시가 아니라 깨진 security invariant다. 재현 실패는 결함 부재가 아니라 낮은 승률이며, 인터리빙 창을 키우면 드러난다(창은 승률을 바꿀 뿐 결함을 만들지 않는다).
- 논리 레이스(불변식 위반, 대개 로직/DoS)와 메모리 손상 레이스(더블 페치, 프리미티브 후보)를 구분하고, 익스플로잇 가능성은 "레이스를 이길 확률"까지 계산에 넣어 정직하게 산정한다.
- 데이터 레이스 ≠ 레이스 컨디션. 새니타이저의 침묵은 논리 레이스의 무죄가 아니다.

**점검 질문** — (1) `balance -= amount` 한 줄에만 락을 걸면 왜 결함이 남는가? (2) 스트레스 테스트에서 위반이 0으로 나왔을 때, "버그 없음"이라 결론 낼 수 없는 이유는? (3) 커널 더블 페치가 자바 논리 레이스보다 영향이 큰 이유를, "낡는 값이 무엇인가"로 설명하라.

**참고** — CWE-367 TOCTOU(https://cwe.mitre.org/data/definitions/367.html) · CWE-362 Race Condition(https://cwe.mitre.org/data/definitions/362.html) · LLVM ThreadSanitizer(https://clang.llvm.org/docs/ThreadSanitizer.html) · Linux KCSAN(https://docs.kernel.org/dev-tools/kcsan.html) · Wang et al., "How Double-Fetch Situations turn into Double-Fetch Vulnerabilities", USENIX Security 2017

*다음 글: [resource exhaustion·DoS RCA](/posts/android-rca-p3c15/).*
