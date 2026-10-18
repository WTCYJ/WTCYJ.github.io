---
layout: post
title: "resource exhaustion·DoS RCA"
date: 2026-12-21 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, DoS, 자원고갈, RCA, ANR]
excerpt: "자원 고갈 DoS의 근본원인은 대개 '신뢰 경계에서 수량에 상한이 없다'로 압축된다. 함정 하나 — 스택이 가리키는 그 줄은 폴트 사이트일 뿐 근본원인이 아니고, 크래시가 곧 취약점도 아니다."
---

자원 고갈 DoS는 RCA 연습으로 좋은 소재다. 크래시가 눈에 확 보이고 재현이 쉬운 반면, 그 크래시가 **왜** 일어나는지와 **얼마나 심각한지**는 대충 넘기기 딱 좋기 때문이다. 스택 최상단 줄을 근본원인으로 착각하고, 자기 앱이 혼자 죽은 걸 취약점으로 부풀리는 실수가 이 클래스에서 제일 자주 나온다.

이 글은 자작 결함 앱을 OutOfMemoryError로 죽여 놓고, 그 하나의 크래시를 증상·트리거·폴트 사이트·근본원인으로 분해한 다음, 영향을 정직하게 매기는 과정을 정리한 기록이다. 무기화는 하지 않고 "프리미티브가 존재한다"까지만 본다.

> **한 줄 결론**: DoS RCA의 핵심은 증상·트리거·폴트 사이트·근본원인을 분리하는 것이다. 폴트 사이트(크래시 줄)를 막으면 증상은 사라지지만 근본원인(신뢰 경계의 무제한 수량)은 남고, 영향은 자기 DoS → 교차 DoS → 시스템 DoS → 지속 DoS의 사다리로 매겨야 한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 자원 고갈(메모리·CPU·핸들·Binder 버퍼)로 인한 DoS의 근본원인 분석 절차를 다룬다. RCA 방법론을 앞선 글에서 이어 온다 — 1장의 증상/트리거/폴트 사이트/근본원인 4계층, 7장의 crash와 exploitability 구분, 6장의 최소 재현·입력 축소가 밑에 깔린다. 자작 앱과 에뮬레이터만 쓰므로 특별한 선행 환경은 없고, `adb`·`logcat`·`dumpsys`를 다룰 줄 알면 된다.

전체 구조에서 이 장은 "메모리 손상이 아닌 결함"의 대표다. OOB(12장)·UAF(13장)·race(14장)가 메모리 안전성 위반이라면, 자원 고갈은 **메모리가 안전한데도** 무제한으로 소비돼 서비스가 멈추는 경우다. 그래서 익스플로잇 가능성 판정이 다르다 — 여기서 얻는 프리미티브는 대개 가용성(A) 하나뿐이고, 그 사실을 인정하는 게 RCA의 절반이다. 개념 배경이 필요하면 Atlas C04(프로세스·가상메모리)·Atlas C31(앱 샌드박스·컴포넌트 노출)을 참고할 수 있다.

## 핵심 개념 — 폴트 사이트는 근본원인이 아니다

RCA의 첫 갈림길은 "스택이 가리키는 줄"과 "근본원인"을 나누는 것이다. 자원 고갈에서 이 둘은 거의 항상 다르다.

```
증상(Symptom)      프로세스가 죽었다 / 기기가 재부팅됐다 / ANR이 떴다
   ▲  관측되는 현상 — 여기서 멈추면 "크래시 하나"로 끝난다
트리거(Trigger)    size=2_000_000_000 인텐트  ← 재현 가능한 최소 입력
   ▲
폴트 사이트(Fault) ByteArray(size)  ← 크래시 스택이 가리키는 바로 그 줄
   ▲  이 줄만 고치면(예: try/catch) 증상은 사라진다 — 근본원인은 남는다
근본원인(Root)     신뢰 경계에서 수량에 상한이 없다 + exported로 외부 노출
```

폴트 사이트만 손보는 건 증상 패치다. `ByteArray(size)`를 `try { } catch (e: OutOfMemoryError)`로 감싸면 그 줄은 안 죽지만, 무제한 수량은 여전히 다른 경로(파일 버퍼, 컬렉션, 압축 해제)로 새어 든다. 근본원인은 "신뢰 불가 입력이 상한 없이 자원 할당에 도달한다"이고, 진짜 수정은 경계에서 값을 검증하거나 애초에 노출을 없애는 것이다. `Inferred`

자원 고갈은 소비되는 자원 종류로 나뉘고, RCA에서 봐야 할 관측 지점도 종류마다 다르다.

| 자원 | 전형적 폴트 사이트 | 증상·관측 지점 | 근거 |
|--|--|--|--|
| 힙 메모리 | 신뢰 불가 크기의 할당, 압축 폭탄, 무한 컬렉션 증가, 누수 | `OutOfMemoryError`(단일 과대 할당은 ART가 힙 growth-limit에서 즉시 거절), `dumpsys meminfo` 힙 급증·lmkd 로그(점진 고갈 시) | `Source-confirmed` |
| CPU | 알고리즘 복잡도(ReDoS·2차 파싱), 무제한 루프 | ANR, `dumpsys cpuinfo`, `/data/anr/anr_*`(API 26+; 구버전만 단일 `/data/anr/traces.txt`) | `Source-confirmed` |
| 파일 디스크립터 | 안 닫힌 Cursor/Stream/소켓 | `Too many open files`, `/proc/<pid>/fd` 개수 | `Reported` |
| Binder 버퍼 | 과대 Parcel 전송 | `TransactionTooLargeException` | `Source-confirmed` |
| 저장소 | 무제한 파일 생성 | 쓰기 실패, `df` | `Reported` |

두 가지 숫자만 못 박아 두면 판독이 쉬워진다. **Binder 트랜잭션 버퍼는 프로세스당 약 1MB이고 진행 중인 모든 트랜잭션이 공유**하므로, 큰 Parcel 하나가 아니라 여러 개가 겹쳐도 `TransactionTooLargeException`이 난다. `Source-confirmed` 그리고 **메인 스레드가 일정 시간 막히면 ANR**이 뜬다 — 입력 디스패치 임계는 관례적으로 5초이고, 브로드캐스트·서비스는 더 길며 버전·포그라운드 여부에 따라 다르다(정확한 값은 버전 확인 필요). `Source-confirmed`

**신뢰 경계와 위협 모델.** 자원 고갈이 취약점이 되려면 세 조건이 함께여야 한다 — (1) 소비량을 **공격자가 통제**하고, (2) 그 경로가 **신뢰 경계를 넘어**(exported 컴포넌트·IPC·네트워크·파일) 도달하며, (3) 소비에 **상한이 없다**. 이 중 하나라도 빠지면 대개 버그이지 취약점이 아니다. 내 앱이 내 코드 때문에 혼자 OOM으로 죽는 건 세 번째만 만족하므로 취약점 축에 들지 않는다.

> **[그림 1]** 자작 앱을 OOM으로 죽인 순간의 logcat — `E AndroidRuntime: FATAL EXCEPTION`과 `java.lang.OutOfMemoryError` 스택이 잡힌 캡처. 단일 과대 할당은 ART가 힙 growth-limit 검사에서 물리 메모리를 커밋하기 전에 즉시 거절하므로, 물리 메모리 압박에 반응하는 `lowmemorykiller`/`lmkd` 로그는 함께 뜨지 않는다(그 로그는 점진적 고갈 변형에서만 관측) — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **로컬 에뮬레이터(AVD)와 자작 결함 앱**으로만 진행한다. 제3자 앱·실서비스·실기기는 대상이 아니다. 앱 `com.wtcy.dosdemo`는 의도적으로 `exported=true`인 브로드캐스트 리시버 하나를 두고, 외부 인텐트의 `size` 값을 검증 없이 그대로 할당에 넣는다. 이 앱의 크래시는 자기 프로세스 안에서 끝나고, 시스템에 지속 영향을 주지 않는다. 실험 전 `adb emu avd snapshot save clean`으로 기준선을 잡아 매 반복을 같은 상태에서 시작한다.

## 실습 절차와 관측

### 가설
- **가설 A** — `--ei size` 값을 힙 한계보다 크게 주면 폴트 사이트 `ByteArray(size)`에서 `OutOfMemoryError`가 나고, 스택은 그 정확한 줄을 가리킨다. `Inferred`
- **가설 B** — `try/catch(OutOfMemoryError)`로 그 줄을 감싸면 증상(크래시)은 사라지지만, 신뢰 경계의 무제한 수량이라는 근본원인은 그대로여서 다른 자원(예: FD·CPU)으로 옮기면 다시 재현된다. `Inferred`

### 절차
1. 결함 리시버를 최소 형태로 만든다(아래 코드).
2. 정상 크기(`size=1024`)로 한 번 보내 기준 동작을 확인한다.
3. 과대 크기(`size=2000000000`)로 보내 크래시를 유발한다.
4. `logcat -b crash`로 폴트 사이트 줄번호를 기록한다. 단일 과대 할당(2GB)은 ART가 힙 growth-limit 검사에서 물리 메모리 커밋 전에 즉시 거절하므로 `dumpsys meminfo`에 힙 급증이 찍히지 않고 lmkd도 관여하지 않는다 — meminfo 힙 급증·lmkd 압박은 중간 크기 할당을 참조 보유한 채 루프로 누적하는 점진적 고갈 변형에서만 관측된다.
5. 입력을 축소(6장)해 크래시를 내는 **최소 size 임계**를 이분 탐색으로 찾는다.

```kotlin
// AndroidManifest.xml (발췌) — 의도적으로 취약하게 노출
// <receiver android:name=".DosReceiver" android:exported="true">
//   <intent-filter><action android:name="com.wtcy.dos.ALLOC"/></intent-filter>
// </receiver>

class DosReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val size = intent.getIntExtra("size", 0)   // 신뢰 경계: 외부 인텐트
        val buf = ByteArray(size)                    // 폴트 사이트: 상한 없는 할당
        buf[0] = 1
    }
}
```

```bash
# 정상 → 과대. 두 번째가 OutOfMemoryError를 유발한다.
adb shell am broadcast -a com.wtcy.dos.ALLOC \
  -n com.wtcy.dosdemo/.DosReceiver --ei size 1024
adb shell am broadcast -a com.wtcy.dos.ALLOC \
  -n com.wtcy.dosdemo/.DosReceiver --ei size 2000000000
adb logcat -b crash -d            # 폴트 사이트 줄번호 확인
adb shell dumpsys meminfo com.wtcy.dosdemo   # 힙 상태
```

> **[그림 2]** `am broadcast`로 큰 `size` 값을 자작 앱에 전달하는 명령과, 그 직후 `logcat -b crash`에 찍힌 `OutOfMemoryError` 스택(폴트 사이트 `DosReceiver.kt` 줄번호 포함)을 나란히 담은 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
--------- beginning of crash
FATAL EXCEPTION: main
Process: com.wtcy.dosdemo, PID: 12931
java.lang.OutOfMemoryError: Failed to allocate a 2000000016 byte allocation
        with 25MB free; ...
        at com.wtcy.dosdemo.DosReceiver.onReceive(DosReceiver.kt:9)
```

스택 최상단이 정확히 `DosReceiver.kt:9`, 즉 `ByteArray(size)` 줄을 가리킨다. 이게 폴트 사이트다. 하지만 이 줄에는 잘못이 없다 — `size`가 정상 범위였다면 아무 문제가 없다. RCA는 여기서 한 칸 더 올라가야 한다.

## Root Cause

근본원인은 폴트 사이트 두 줄 위, `getIntExtra` 결과가 **아무 검증 없이** 할당으로 흘러 들어가는 데이터 흐름에 있다. 정리하면 세 요소의 결합이다.

- **무제한 수량** — `size`에 상한 검사가 없다. 자원 소비량을 입력이 그대로 결정한다.
- **신뢰 경계 통과** — 리시버가 `exported=true`라, 같은 기기의 아무 앱이나(권한 없이) 이 값을 넣을 수 있다.
- **증폭 여지** — 이 로직이 어디 사는가에 따라 영향이 달라진다.

세 번째가 영향 산정의 핵심이다. 같은 결함이라도 사는 곳에 따라 사다리를 오른다.

```
자기 DoS   내 코드가 내 프로세스만 죽인다            → 대개 버그, 취약점 아님
교차 DoS   exported 컴포넌트로 남이 내 앱을 죽인다     → 취약점(가용성), Medium권
시스템 DoS system_server 스레드를 죽여 프레임워크 재시작 → 기기 전체 소프트 리부트
지속 DoS   재부팅 때마다 읽는 값에 그 입력이 저장됨     → 부트루프, 사실상 영구
```

`system_server`는 예외를 못 잡으면 프로세스가 죽고 안드로이드가 프레임워크를 재시작한다(사용자에게는 재부팅으로 보인다). 또한 `system_server`에는 Watchdog이 있어 핵심 스레드가 일정 시간 이상 막히면 스스로 프로세스를 죽인다. `Reported` 그래서 "아무 앱이나 트리거 가능한 `system_server` 자원 고갈"은 교차 DoS보다 한 단계 위다. 그리고 그 크래시를 유발하는 입력이 어딘가에 **저장**돼 부팅 경로에서 다시 읽히면, 재부팅이 곧 재크래시가 되어 부트루프 — 초기화 없이는 못 벗어나는 지속 DoS가 된다. `Reported`

우리 자작 앱은 이 사다리의 **교차 DoS** 칸에 해당한다. 정직한 상한을 매기면 로컬 공격자(악성 앱)가 권한·상호작용 없이 대상 앱을 죽이는 가용성 영향뿐이다.

- 벡터: `CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`
- 점수: **6.2 (Medium)** — 로컬(AV:L), 기밀성·무결성 영향 없음(C:N/I:N), 가용성만 High. 스코프는 대상 앱 하나에 국한(S:U)이라 바뀌지 않는다.

여기서 흔한 과장을 잘라야 한다. 이건 RCE가 아니고, 정보 노출도 아니다. `ByteArray`는 힙에 안전하게 할당 실패했을 뿐 메모리 손상이 없으므로, "OOM이니 힙 그루밍으로 코드 실행"으로 이어지지 않는다. 크래시 ≠ 취약점, DoS ≠ RCE — 이 경계를 지키는 게 RCA의 신뢰도다.

## 방어와 회귀 검증

- **경계에서 상한을 건다.** 폴트 사이트가 아니라 신뢰 경계에서 `size`를 검증한다 — `require(size in 0..MAX)` 후 거절. 이게 근본원인 수정이다. 폴트 사이트를 `try/catch(OutOfMemoryError)`로 막는 건 권장되지 않는다: OOM은 어느 할당에서 터질지 불확실하고, 잡아도 프로세스가 이미 불안정할 수 있다.
- **노출을 없앤다.** IPC 트리거가 필요 없으면 `exported=false`로 신뢰 경계 자체를 지운다. 세 조건 중 (2)를 무너뜨리면 취약점이 버그로 내려간다.
- **회귀 테스트.** 악성 입력(`size=Int.MAX_VALUE`, 음수, 0)을 보내고 **프로세스가 살아 있으며 요청이 거절됨**을 단언하는 계측 테스트를 남긴다. 여기에 `size` 필드 퍼징을 붙이면 6장의 입력 축소로 찾은 임계 근처를 자동 회귀로 지킬 수 있다.
- **한계.** 자작·에뮬 관측은 단일 과대 할당의 힙 growth-limit 즉시 거절을 재현하지만(lmkd 압박은 점진적 고갈 변형에서만 나타난다), 실제 기기의 메모리 압박·`system_server` Watchdog 타이밍은 다르게 나타날 수 있다. 시스템 DoS·지속 DoS 시나리오는 개념으로만 다루고 실험하지 않았다 — 부트루프 유발은 안전 범위를 벗어난다. Binder·ANR의 정확한 임계 수치는 버전 확인 필요.

## 정리

- 자원 고갈 DoS의 폴트 사이트(크래시 줄)와 근본원인(신뢰 경계의 무제한 수량)은 거의 항상 다르다 — 폴트 사이트만 고치면 증상만 사라진다.
- 취약점 성립 조건은 셋의 결합이다: 공격자 통제 수량 + 신뢰 경계 통과 + 무상한. 하나라도 빠지면 대개 버그다.
- 영향은 자기 DoS → 교차 DoS → 시스템 DoS → 지속 DoS 사다리로 정직하게 매긴다. 크래시 ≠ 취약점, DoS ≠ RCE.
- 근본원인 수정은 경계에서의 상한 검증(또는 노출 제거)이고, 회귀는 악성 입력에도 프로세스 생존을 단언하는 테스트로 고정한다.

**점검 질문** — (1) 같은 `OutOfMemoryError`인데 폴트 사이트와 근본원인이 왜 다른가? (2) 자작 앱의 OOM 크래시가 취약점이 되려면 무엇이 더 필요한가? (3) 이 DoS를 RCE로 부풀리면 안 되는 근거는 무엇인가?

**참고** — [TransactionTooLargeException](https://developer.android.com/reference/android/os/TransactionTooLargeException) · [ANR 진단](https://developer.android.com/topic/performance/vitals/anr) · [메모리 개요](https://developer.android.com/topic/performance/memory-overview) · [lmkd (AOSP)](https://source.android.com/docs/core/perf/lmkd)

*다음 글: [patch diff·Patch Invariant](/posts/android-rca-p3c16/).*
