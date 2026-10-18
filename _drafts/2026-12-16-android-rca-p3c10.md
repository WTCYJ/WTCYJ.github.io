---
layout: post
title: "Parcel read/write mismatch RCA"
date: 2026-12-16 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Parcel, Binder, Serialization]
excerpt: "Parcel은 필드 이름이 아니라 위치로 읽는다. writeToParcel이 int 2개를 쓰고 createFromParcel이 1개만 읽으면, 예외가 아니라 '그 다음 값'이 조용히 어긋난다 — 크래시가 나면 차라리 운이 좋은 것이다."
---

Android의 모든 IPC는 결국 `Parcel`이라는 평평한 바이트 버퍼를 지난다. Intent, Bundle, AIDL 인자, 콜백 결과 — 전부 `writeToParcel`로 직렬화되어 Binder를 건너가고, 반대편에서 `createFromParcel`로 복원된다. 이 두 함수가 **정확히 같은 순서·같은 바이트 수**로 맞물려야만 데이터가 온전히 건너간다. 한쪽이 4바이트를 더 쓰거나 덜 읽으면, 그 뒤에 오는 모든 필드의 읽기 위치가 밀린다.

문제는 이 어긋남이 대개 **소리 없이** 일어난다는 점이다. 운이 좋으면 `BadParcelableException`으로 크래시가 나고, 운이 나쁘면 아무 예외 없이 "그 다음 값"이 다른 값으로 읽힌다. system_server가 Bundle을 재직렬화하는 경계에서 이 어긋남이 발생하면 type confusion으로 번진다. 이 글은 자작 결함 앱과 로컬 `Parcel` 왕복 실험으로 write/read mismatch가 어떤 증상으로 드러나고, fault site와 root cause를 어떻게 갈라 짚는지를 정리한 기록이다.

> **한 줄 결론**: Parcel은 위치 기반이라 read는 write와 순서·개수가 완전히 대칭이어야 하고, 어긋나면 **fault site(잘못 읽는 곳)가 아니라 비대칭 그 자체가 root cause**다 — 그리고 그 결과는 예외보다 "조용한 drift"일 때가 더 위험하다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 `Parcelable`의 write/read 불일치를 RCA(근본원인분석) 관점에서 해부한다. 자작 `Parcelable` 하나로 어긋남을 결정적으로 재현하고, 그 현상을 3부 1장에서 세운 Symptom/Trigger/Fault Site/Root Cause 4구분에 대입한 뒤, 3부 7장에서 정리한 crash와 exploitability의 경계를 이 클래스에 적용한다. 무기화 없이 "어떤 프리미티브가 존재하는가"까지만 본다.

선수 지식은 두 갈래다. 첫째, Binder와 Parcel의 기초 — Parcel은 필드 이름이나 타입 태그가 붙은 구조체가 아니라, 쓴 순서대로 이어 붙인 **평면 버퍼**이며 `dataPosition`이라는 커서 하나로 읽고 쓴다(Atlas의 Binder/IPC 장). 둘째, Bundle이 왜 특별한가 — Bundle은 즉시 풀리지 않고 필요할 때 지연(lazy) unparcel(역직렬화)되고, 이후 다른 컴포넌트로 전달될 때 재직렬화(re-parcel)된다. 이 지연 unparcel과 전달 시 재직렬화가 mismatch를 단순 버그에서 보안 문제로 끌어올린다.

전체 구조에서 이 장은 3부(RCA)의 열 번째다. 앞의 3부 9장(Binder caller identity 오류)이 "누가 부르는가"를 틀리는 경우였다면, 이 장은 "무엇이 건너오는가"를 틀리는 경우다. 둘 다 신뢰 경계를 넘는 데이터에 대한 오해에서 나온다.

## 핵심 개념 — Parcel은 위치로 읽는다

Parcel의 계약은 단순하다. `writeToParcel`이 쓴 값을, `createFromParcel`이 **같은 순서로, 같은 타입으로, 같은 개수만큼** 읽어야 한다. 필드 이름 대조도, 자동 타입 검사도 없다. `readInt()`는 그저 현재 커서에서 4바이트를 읽어 int로 해석할 뿐이다. `Source-confirmed` (Android `Parcel`/`Parcelable` 레퍼런스)

그래서 어긋남은 네 가지 얼굴로 나타난다.

| 어긋남 유형 | 무엇이 어긋나나 | 겉으로 드러나는 증상 |
|--|--|--|
| under-read | write 3필드 / read 2필드 | 다음 값이 남은 바이트로 밀려 읽힘(drift) |
| over-read | write 2필드 / read 3필드 | 버퍼 끝 초과 → 기본값/0 또는 예외 |
| 순서 불일치 | int↔String 순서 뒤바뀜 | int 값이 문자열 길이로 오해석 → 대형 할당/`OOM`/예외 |
| 조건부 비대칭 | `if`로 쓰고 무조건 읽음 | 입력에 따라 될 때도, 안 될 때도 |

여기서 가장 흔한 오개념 하나 — "예외가 안 나면 통과한 것"이라는 착각이다. under-read는 **예외를 던지지 않는다**. 커서가 4바이트 덜 전진했을 뿐, 그 뒤의 `readInt()`는 정상적으로 성공한다. 다만 원래 의도한 값이 아니라, 앞 객체가 남긴 바이트를 읽는다. 조용한 drift가 시끄러운 크래시보다 위험한 이유다. `Inferred`

또 하나 — "createFromParcel만 고치면 된다"는 착각. 잘못 읽는 곳(read)은 fault site일 뿐이다. write가 규격을 어겼는데 read를 write에 맞추면, 이번엔 반대편 writer/reader 짝(예: 벤더 확장, 구버전 클라이언트)이 깨진다. root cause는 **두 함수의 비대칭 자체**이지 한쪽 함수가 아니다. `Inferred`

**신뢰 경계와 위협 모델.** 위험한 것은 내 프로세스 안에서의 왕복이 아니라, **신뢰 경계를 넘는 재직렬화**다. 앱이 만든 Bundle이 system_server로 건너가 unparcel되고, 다시 parcel되어 또 다른 권한 있는 컴포넌트로 전달될 때, 중간에 낀 mismatch 하나가 그 뒤 필드 전체를 밀어버린다. 그러면 같은 바이트열이 앱에서 읽을 때와 system_server가 읽을 때 **다른 값**으로 해석될 수 있다. 이것이 이른바 self-changing Bundle 계열의 핵심이며, Michał Bednarski의 Parcel 직렬화 연구가 여러 패치된 CVE로 정리한 클래스다(정확한 CVE 번호·버전은 불리틴 원문 재확인). `Reported`

> **[그림 1]** Android Studio 디버거에서 `createFromParcel` 진입 직전과 직후의 `Parcel.dataPosition()` 값을 나란히 잡아, write가 소비를 기대한 바이트 수와 실제 read가 전진한 바이트 수의 차이(예: 8 vs 4)를 보여주는 캡처 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **로컬 에뮬레이터(AVD)와 자작 앱**으로만 진행한다. 제3자 앱·실서비스·system_server 실공격은 없다. 재현은 내 프로세스 안에서 `Parcel.obtain()`으로 버퍼를 직접 만들고 되읽는 순수 개념 수준이며, Binder를 실제로 건너가지 않아도 mismatch의 본질은 동일하게 드러난다. 목표는 무기화가 아니라 "drift라는 프리미티브가 존재함"을 눈으로 확인하는 것까지다.

## 실습 절차와 관측

### 가설
- **가설 A** — writeToParcel이 int 2개(8바이트)를 쓰고 createFromParcel이 1개(4바이트)만 읽는 `Parcelable`을 만들면, 그 뒤에 쓴 marker int가 원래 값이 아니라 **남은 두 번째 int로 읽힌다**(예외 없는 drift). `Inferred`
- **가설 B** — 반대로 read가 write보다 더 읽어 버퍼 끝을 넘으면, 조용한 drift 대신 **예외 또는 기본값(0)** 이 관측된다. `Inferred`

### 절차
1. 아래 `Drifter`처럼 write 2필드 / read 1필드로 **의도적으로 비대칭**인 자작 `Parcelable`을 만든다.
2. `Parcel`에 `Drifter`를 쓰고, 바로 뒤에 눈에 띄는 marker(`0xCAFEBABE`)를 쓴다.
3. `setDataPosition(0)`으로 커서를 되감고, `Drifter`를 읽은 뒤 marker를 읽어 값을 로그로 남긴다.
4. `adb logcat`으로 marker가 원래 값인지, 밀려서 다른 값이 됐는지 기록한다.

```java
// 자작 결함 Parcelable — 개념 이해용 최소 예시
static class Drifter implements Parcelable {
    final int a, b;
    Drifter(int a, int b) { this.a = a; this.b = b; }
    public int describeContents() { return 0; }
    public void writeToParcel(Parcel p, int flags) {
        p.writeInt(a);
        p.writeInt(b);          // 8바이트를 쓴다
    }
    public static final Creator<Drifter> CREATOR = new Creator<Drifter>() {
        public Drifter createFromParcel(Parcel p) {
            int a = p.readInt();  // 4바이트만 읽는다 — 여기가 fault site
            return new Drifter(a, -1);
        }
        public Drifter[] newArray(int n) { return new Drifter[n]; }
    };
}

// 왕복 실험 (instrumented test 안에서)
Parcel p = Parcel.obtain();
p.writeParcelable(new Drifter(0x11111111, 0x22222222), 0);
p.writeInt(0xCAFEBABE);                      // 다음에 읽혀야 할 marker
p.setDataPosition(0);
Drifter d = p.readParcelable(getClass().getClassLoader());
int marker = p.readInt();                    // 기대: CAFEBABE
Log.i("RCA", "d.a=" + Integer.toHexString(d.a) + " d.b=" + d.b);
Log.i("RCA", "marker expected=cafebabe got=" + Integer.toHexString(marker));
p.recycle();
```

> **[그림 2]** 위 테스트를 AVD에서 돌린 뒤 `adb logcat -s RCA:I` 출력 — marker가 `cafebabe`가 아니라 `22222222`로 찍혀 drift가 발생한 순간을 잡은 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체):

```
$ adb logcat -s RCA:I
I RCA: d.a=11111111 d.b=-1
I RCA: marker expected=cafebabe got=22222222
```

marker가 `cafebabe`가 아니라 `22222222`로 읽혔다. `createFromParcel`이 두 번째 int(`0x22222222`)를 소비하지 않고 남겼기 때문에, 커서가 4바이트 뒤처진 채 `readInt()`가 그 남은 값을 집어간 것이다. 예외는 없었다. 이것이 가설 A가 말한 **조용한 drift**다.

여기서 주의 — 위 왕복은 `writeParcelable`이 클래스명 뒤에 int 2개를, 이어 `writeInt(marker)`가 int 1개를 써서 총 int 3개다. `createFromParcel`을 단순히 `p.readInt()` 두 번으로 바꾸면 a·b를 소비하고 바깥 `readInt()`가 marker를 읽어 **3개 쓰고 3개 읽음**이라 완전 대칭이 되어 버퍼 끝을 넘지 않는다. over-read를 재현하려면 **쓴 개수보다 한 번 더 읽어** 버퍼 끝을 넘겨야 한다 — 예를 들어 marker를 빼고 int 2개만 쓴 뒤 `createFromParcel`에서 `readInt()`를 3번 부른다. 그러면 결과가 달라진다. 네이티브 Parcel은 끝을 넘는 primitive read에서 **경고 없이 기본값(0)을 조용히 돌려준다**. 예외·경고(`Reading a NULL string not supported here`류)는 primitive가 아니라 객체·문자열 read 경로에서 나온다 — 가설 B의 얼굴이다. 즉 **같은 비대칭이라도 under-read냐 over-read냐에 따라 증상 등급이 다르다.** `Inferred`

## Root Cause — 왜 이렇게 되는가

RCA의 핵심은 증상과 근본원인을 헷갈리지 않는 것이다. 이 클래스를 4구분으로 갈라 보면 다음과 같다.

| 구분 | 이 사례에서 | 흔한 오진 |
|--|--|--|
| Symptom | marker가 다른 값으로 읽힘 / `BadParcelableException` / system_server 재시작 | "그냥 앱 크래시" |
| Trigger | 비대칭 객체가 다른 필드 **앞에** 놓여 unparcel됨(특히 Bundle 재직렬화) | "특정 기기 문제" |
| Fault site | `createFromParcel`의 under-read 지점 | 여기를 root cause로 착각 |
| Root cause | write와 read의 **바이트 수 비대칭 그 자체** | read만 수정하고 종료 |

근본원인은 커서 하나로 돌아가는 위치 기반 직렬화에서, writer와 reader가 **서로 독립적으로 유지보수되기 때문**이다. 필드를 하나 추가하며 `writeToParcel`만 고치고 `createFromParcel`을 놓치거나, 조건부로 쓴 필드(`if (x != null) p.writeInt(...)`)를 무조건 읽거나, 버전이 다른 writer·reader가 섞이면 비대칭이 태어난다. 컴파일러는 이 계약을 검사하지 않는다 — 두 함수는 타입으로 묶여 있지 않고, 오직 개발자의 규율로만 대칭이 유지된다. `Source-confirmed` (Parcel의 위치 기반 계약)

**exploitability는 정직하게.** mismatch 자체는 직렬화 버그이지 곧바로 RCE가 아니다. 영향은 이렇게 갈린다.
- **DoS** — system_server가 defusable하지 않은 Bundle을 풀다 예외를 던지면 프로세스가 죽고 기기가 재시작될 수 있다. 가장 흔한 결말.
- **Type confusion / EoP** — drift로 인해 권한 있는 쪽이 attacker가 심은 값을 **다른 타입/객체로** 신뢰해 읽으면, 검사 우회나 특권 컴포넌트로의 객체 스머글링(예: 예상치 못한 Intent)이 가능해진다. self-changing Bundle 계열이 EoP로 분류된 이유다. `Reported`
- **하지만** 여기까지 가려면 **drift된 값을 특권 맥락에서 신뢰하는 하위 sink**가 있어야 한다. 그 sink가 없으면 프리미티브는 drift/DoS에 머문다. crash를 취약점으로, DoS를 RCE로 부풀리지 않는다.

## 방어와 회귀 검증

- **대칭을 코드가 아니라 테스트로 보장한다.** `writeToParcel` → `marshall()` → `unmarshall()` → `createFromParcel` 왕복 후 `dataPosition()`이 `dataSize()`와 같은지 assert하는 라운드트립 테스트를 붙인다. 남은 바이트가 0이 아니면 비대칭이다. 이 한 줄짜리 검사가 회귀를 잡는다.
- **길이 접두(length-prefix)와 defusable Bundle.** 플랫폼은 Bundle 항목 앞에 길이를 기록하거나, unparcel 중 예외를 삼켜 커서를 안전 지점으로 복구하는 방향으로 이 클래스를 완화해 왔다(`Bundle.setDefusable` 계열). 다만 어떤 완화가 어느 API 레벨부터 기본으로 켜졌는지는 **버전 확인 필요** — 문서화할 땐 대상 API를 명시한다. `Reported`
- **입력을 좁혀 최소 재현으로.** 3부 6장의 입력 축소를 적용해, drift를 만드는 최소 필드 구성만 남긴 뒤 그것을 회귀 테스트로 고정한다. "왜 이 기기에서만"이라는 착각은 대개 조건부 비대칭(가설의 4번째 유형)이며, 최소 재현이 조건을 드러낸다.
- **AIDL을 우선한다.** 손으로 짠 `Parcelable`은 비대칭을 사람이 관리해야 하지만, AIDL이 생성한 stub은 write/read를 함께 만들어 대칭을 강제한다. 손으로 짤 이유가 없다면 도구가 짜게 둔다.

## 정리

- Parcel은 필드 이름 없는 위치 기반 버퍼다 — read는 write와 순서·타입·개수가 완전히 대칭이어야 하고, 어긋나면 커서가 밀린다.
- under-read는 예외 없이 **다음 값을 조용히 오염**시킨다. 크래시가 나면 오히려 발견이 쉬운 편이다.
- fault site(잘못 읽는 함수)와 root cause(write/read 비대칭)는 다르다 — read만 고치고 끝내면 반대편 짝이 깨진다.
- 영향은 DoS부터 type confusion→EoP까지 갈리지만, 특권 sink 없이는 자동 RCE가 아니다. 경계를 지켜 산정한다.

**점검 질문** — (1) under-read와 over-read는 각각 어떤 증상으로 드러나며 왜 다른가? (2) 이 클래스에서 fault site와 root cause가 다르다는 말은 구체적으로 무슨 뜻인가? (3) mismatch가 DoS를 넘어 EoP가 되려면 추가로 무엇이 필요한가?

**참고** — [Android Parcel 레퍼런스](https://developer.android.com/reference/android/os/Parcel) · [Parcelable 레퍼런스](https://developer.android.com/reference/android/os/Parcelable) · [Michał Bednarski, Parcel 직렬화 연구](https://github.com/michalbednarski) · Android Security Bulletin(해당 CVE 항목은 원문 재확인)

*다음 글: [integer overflow/underflow RCA](/posts/android-rca-p3c11/).*
