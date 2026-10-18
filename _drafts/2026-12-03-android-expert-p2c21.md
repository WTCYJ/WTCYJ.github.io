---
layout: post
title: "Perfetto·simpleperf·관측"
date: 2026-12-03 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Perfetto, simpleperf, tracing, 프로파일링]
excerpt: "시스템 전체 관측은 Perfetto(traced/traced_probes) 한 파이프로 모이고 CPU 핫스팟은 simpleperf가 샘플링한다. 그런데 무루트 기기에서 릴리스 앱을 재는 열쇠는 root가 아니라 매니페스트의 profileable 선언이고, 편하다고 debuggable 빌드를 재면 JIT/AOT가 달라 실제와 다른 런타임을 잰다."
---

성능 튜닝이든 악성 동작 관찰이든, 결국 "무슨 일이 언제 어느 스레드에서 일어났나"를 봐야 한다. Android에서 이걸 답하는 두 도구가 Perfetto와 simpleperf다. Perfetto는 커널 ftrace·프레임워크 atrace·시스템 카운터를 하나의 프로토콜 버퍼 트레이스로 모으고, simpleperf는 그 위에서 CPU 콜스택을 샘플링해 어느 함수가 시간을 먹는지를 짚는다. 앱→프레임워크→Binder→system_server→커널로 내려가는 호출이 한 타임라인에 겹쳐 보이는 게 이 파이프라인의 핵심이다.

문제는 이 관측 능력이 공짜가 아니라는 것이다. 무루트 기기에서 릴리스 앱을 프로파일링하려는 순간, root냐 아니냐가 아니라 매니페스트에 `profileable`을 선언했느냐, 빌드 타입이 무엇이냐, 커널 `perf_event` 하드닝이 걸렸느냐가 관측 경계를 가른다. 이 글은 Perfetto와 simpleperf의 구조를 AOSP 관점에서 정리하고, 자작 앱·에뮬레이터로 그 관측 경계를 직접 확인한 기록이다.

> **한 줄 결론**: 관측 능력은 root 유무가 아니라 빌드 타입·매니페스트 선언(`profileable`/`debuggable`)과 `perf_event` 하드닝에 종속된다 — Perfetto는 전 계층을 한 트레이스로 모으고, simpleperf는 그 위에서 콜스택을 샘플링한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Perfetto의 데몬 구조(`traced`/`traced_probes`)와 데이터 소스, simpleperf의 샘플링 방식, 그리고 둘의 관측 경계를 가르는 빌드 타입·`profileable`·`perf_event_paranoid`를 다룬다. 공격 실습이 아니라 "무엇을 어떤 조건에서 관측할 수 있나"의 구조 이해가 목표다.

선수 개념 셋이 밑에 깔린다. 1부에서 정리한 연구 환경 이야기 — userdebug vs user 빌드가 `adb root`를 가르듯 관측 능력이 빌드 타입에 종속된다는 그 논리가 여기서도 그대로 반복된다. 2부 8장의 ART interpreter/JIT/AOT는 왜 debuggable 빌드를 재면 안 되는지의 뿌리다(debuggable은 JIT/최적화 동작이 달라진다). 2부 14장의 Binder는 트레이스에서 `binder_transaction`/`binder_reply` 이벤트로 나타나므로, 그 구조를 알아야 IPC 지연을 읽을 수 있다.

전체 구조에서 이 장은 **관측 계층**이다. 지금까지 다룬 런타임·시스템서비스·HAL·커널이 실제로 어떻게 시간 위에서 움직이는지를 눈으로 확인하는 도구를 여기서 세운다.

## 핵심 개념 — 두 파이프, 하나의 시간축

Perfetto와 simpleperf는 경쟁 도구가 아니라 서로 다른 질문에 답한다.

| 도구 | 답하는 질문 | 수집 방식 | 산출물 |
|--|--|--|--|
| Perfetto | "언제 무엇이 일어났나"(시간순 이벤트) | ftrace/atrace/카운터를 **기록**(trace) | protobuf 트레이스 → ui.perfetto.dev |
| simpleperf | "어느 함수가 CPU를 먹나"(빈도) | `perf_event_open`으로 **주기 샘플링** | perf.data → 플레임그래프/report |

**Perfetto의 데몬 구조.** 온디바이스 트레이싱은 세 조각이다. `traced`가 중앙 트레이싱 서비스로 버퍼를 관리하고, `traced_probes`가 커널 ftrace와 `/proc` 카운터 등 시스템 데이터 소스를 읽어 넣고, 앱/프레임워크는 `libperfetto`(또는 atrace/`android.os.Trace`)로 producer가 되어 자기 이벤트를 흘려보낸다. 즉 커널·시스템서비스·앱이 각각 producer로 붙고 `traced`가 consumer에게 하나의 트레이스로 합쳐 준다. `Source-confirmed` `traced`는 Android 9 무렵부터 플랫폼에 상주하며 `persist.traced.enable`로 제어된다(정확한 도입 API는 원문 재확인 필요). `Inferred`

여기서 첫 번째 흔한 오해 — **systrace/atrace는 Perfetto의 경쟁자가 아니라 데이터 소스다.** 옛 `systrace` 파이썬 스크립트는 폐기됐고, `atrace` 카테고리(gfx·view·wm·am·`binder_driver`·sched 등)는 이제 Perfetto가 삼키는 여러 입력 중 하나일 뿐이다. `Source-confirmed` "systrace를 쓸까 Perfetto를 쓸까"라는 질문 자체가 낡았다.

**simpleperf의 위치.** simpleperf는 NDK에 들어 있는 네이티브 CPU 프로파일러로, 리눅스 `perf_event_open(2)` 위에 얹혀 주기적으로 스택을 채집한다. `Source-confirmed` ART가 낀 혼합 스택(Java 인터프리터/JIT/AOT + 네이티브 `.so`)도 dwarf/frame-pointer 언와인딩으로 풀어 심볼화할 수 있는 게 핵심 강점이다. Perfetto에도 콜스택 샘플링 데이터 소스(`traced_perf`, `linux.perf`)가 생겨 둘의 경계가 흐려지는 중이지만, 성숙한 플레임그래프 경로는 여전히 simpleperf 쪽이다(정확한 기능 대응은 버전 확인 필요). `Inferred`

> **[그림 1]** ui.perfetto.dev에 트레이스를 올려 sched·`binder_driver`·앱 슬라이스 트랙이 한 시간축에 겹쳐 보이는 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 앱과 에뮬레이터(AVD)**로만 진행한다. 제3자 앱·실서비스 프로파일링은 없다. 계측용 `google_apis` userdebug AVD를 기준으로 하되, 관측 경계를 대조하기 위해 자작 앱의 두 변형(debuggable 빌드와 release + `profileable` 빌드)을 나란히 둔다. 무루트 조건을 흉내 내려면 release 서명 + `profileable`만 켠 APK를 쓰면 된다.

## 실습 절차와 관측

### 가설

- **가설 A** — 무루트(user 상당) 조건에서 release 앱은 `debuggable`이든 `profileable`이든 하나를 선언해야 simpleperf로 잡히고, 아무것도 없으면 프로파일링이 거부된다. `Inferred`
- **가설 B** — 시스템 전체 샘플링(`simpleperf ... -a`)과 임의 앱의 상세 트레이스는 `perf_event`/atrace 하드닝 때문에 root(또는 userdebug)에서만 온전하다. `Inferred`

### 절차

1. atrace 카테고리와 `perf_event` 하드닝 상태를 먼저 기록한다.
2. Perfetto로 짧은 시스템 트레이스를 뜬다(atrace 카테고리 단축형).
3. 자작 앱을 debuggable / release+profileable 두 형태로 simpleperf 프로파일링해 성공/거부를 대조한다.
4. `report_html.py`로 플레임그래프를 만들어 핫 함수를 확인한다.

```bash
# 0) 관측 경계 사전 확인
adb shell atrace --list_categories | head
adb shell cat /proc/sys/kernel/perf_event_paranoid
adb shell getprop security.perf_harden

# 1) Perfetto 시스템 트레이스 (perfetto 바이너리는 atrace 카테고리 단축형을 받는다)
adb shell perfetto -o /data/misc/perfetto-traces/trace.pb -t 10s \
  sched freq idle am wm gfx view binder_driver dalvik input
adb pull /data/misc/perfetto-traces/trace.pb   # ui.perfetto.dev 로 열기

# 2) simpleperf: release 앱을 재려면 매니페스트에 아래가 있어야 한다
#    <application ...> <profileable android:shell="true" /> </application>
cd $ANDROID_NDK/simpleperf
python app_profiler.py -p com.wtcy.sampleapp -r "record -g --duration 10"
python report_html.py   # perf.data -> report.html (플레임그래프)
```

`profileable`을 켠 release 앱과 debuggable 앱은 겉보기 결과가 비슷해 보이지만, **재는 대상이 다르다.** debuggable 빌드는 ART가 JIT/AOT 최적화를 덜 하거나 다르게 하므로, 성능 수치가 출하 빌드와 어긋난다. 그래서 정확한 프로파일은 release 서명 그대로 `profileable`만 얹어 재는 게 정석이다.

> **[그림 2]** 같은 자작 앱을 debuggable 빌드와 release+profileable 빌드로 각각 `app_profiler.py`에 걸었을 때, 후자만 출하 런타임을 반영하는 report_html 플레임그래프 대조 — *실측 스크린샷 자리*

### 관측 결과

아래는 값의 조합을 보여 주는 예시 출력이다 — 게재본에서는 대상 이미지의 실제 실행 출력으로 교체한다:

```
$ adb shell cat /proc/sys/kernel/perf_event_paranoid
1
$ adb shell getprop security.perf_harden
0                      # userdebug/rooted: 완화됨. user 기기면 1

# release APK에 profileable/debuggable 둘 다 없을 때
$ python app_profiler.py -p com.wtcy.sampleapp
... error: failed to profile com.wtcy.sampleapp: not debuggable or profileable
```

관측 경계를 표로 정리하면 이 글의 실용적 결론이 나온다.

| 대상/조건 | Perfetto 앱 슬라이스 | simpleperf 앱 콜스택 | 시스템 전체(`-a`)/ftrace 전량 |
|--|--|--|--|
| release, 선언 없음 | 커널 이벤트만 보임 | **불가** | 불가(무루트) |
| release + `profileable` | 보임 | **가능** | 제한적 |
| debuggable | 보임(런타임 다름) | 가능(런타임 다름) | 제한적 |
| userdebug/root | 전부 | 전부 | **가능** |

## Root Cause — 왜 관측이 가로막히나

핵심은 `perf_event_open(2)`이 특권 인터페이스라는 사실이다. 이 시스콜은 하드웨어 성능 카운터와 커널 샘플링에 접근하는데, 역사적으로 커널 LPE 취약점이 대량으로 나온 공격면이고 카운터를 통한 교차 프로세스 사이드채널 우려도 있다. `Reported` 그래서 리눅스는 `perf_event_paranoid` sysctl로 접근을 조이고, Android는 그 위에 `security.perf_harden` 프로퍼티를 얹어 출하(user) 빌드에서 기본으로 `perf_event`를 잠근다. `Source-confirmed`

즉 관측은 "공짜 부가기능"이 아니라 **빌드 타입과 매니페스트 선언으로 게이팅되는 능력**이다. userdebug/root면 하드닝이 풀려 전부 보이고, 무루트 user 기기에서는 개발자가 자기 앱에 한해 `debuggable` 또는 `profileable`을 명시적으로 선언해야만 그 앱에 프로파일링을 허용한다. `Source-confirmed` 특히 `profileable`에 `android:shell="true"`(L72 코드의 그 속성)를 붙이면, `perf_harden`이 켜진 출하 기기에서도 shell(adb)이 그 앱에 한해 프로파일링을 개시할 수 있다 — 위 표의 `release + profileable` 행이 '가능'인데도 Root Cause가 '기본 잠금'이라 말하는 게 모순이 아닌 이유가 이 개별 허용 경로다. `Source-confirmed` 이건 1부 연구 환경에서 본 "관측 능력이 빌드 타입에 종속된다"는 명제의 성능 관측판이다 — 신뢰 경계를 낮춘 조건에서만 더 많이 보인다.

`profileable`이 `debuggable`과 분리돼 있는 이유도 여기서 나온다. `debuggable`은 디버깅·계측을 위해 ART 최적화를 느슨하게 바꿔 런타임 자체를 오염시킨다. 반면 `profileable`은 프로파일러의 스택 채집만 허용하고 최적화는 출하 그대로 둔다. `Source-confirmed` 그래서 "정확한 성능을 무루트에서 재는" 유일하게 옳은 길이 release + `profileable`이다.

## 버전 차이와 한계

- `systrace`(파이썬 스크립트)는 폐기됐고 Perfetto로 대체됐다. 지금 트레이스를 뜨는 표준은 `perfetto` 바이너리, `record_android_trace` 스크립트, 또는 ui.perfetto.dev의 record 페이지다. `Source-confirmed`
- `profileable` 매니페스트 태그는 비교적 최근(대략 Android 10대)에 도입됐다 — 오래된 API 레벨 대상에선 못 쓰니 정확한 최소 API는 원문 재확인 필요. `Inferred`
- Perfetto의 콜스택 샘플링(`traced_perf`)·네이티브 힙(`heapprofd`)·Java 힙 프로파일러는 도입 시점과 지원 조건이 제각각이라, 특정 데이터 소스를 쓸 땐 대상 이미지에서 실제로 뜨는지 먼저 확인해야 한다. `Inferred`
- **에뮬레이터의 함정 둘.** (1) 트레이스 버퍼는 링버퍼라 캡처가 길면 앞부분이 덮여 사라진다("왜 시작이 없지"의 정체는 `fill_policy`). 짧게 뜨거나 버퍼를 키운다. (2) 하드웨어 PMU 카운터(cache-miss 등)는 에뮬레이터에서 정확하지 않거나 안 잡힐 수 있다 — 사이클 정밀 측정은 실기기 몫이다.

## 정리

- Perfetto = 시간순 이벤트(traced/traced_probes가 커널·프레임워크·앱을 한 트레이스로 병합), simpleperf = CPU 콜스택 샘플링(`perf_event_open` 기반). 둘은 경쟁이 아니라 상호보완이다.
- 무루트에서 릴리스 앱을 재는 열쇠는 root가 아니라 매니페스트 `profileable` 선언이고, 편의로 `debuggable`을 재면 JIT/AOT가 달라 실제와 다른 런타임을 잰다.
- 관측 능력은 `perf_event` 하드닝(`security.perf_harden`)과 빌드 타입에 종속된다 — 이건 성능 관측판의 신뢰 경계다.

**점검 질문** — (1) `traced`와 `traced_probes`는 각각 무엇을 하며, 앱 이벤트는 어떤 경로로 트레이스에 들어가는가? (2) 무루트 기기에서 release 앱을 정확히 프로파일링하려면 매니페스트에 무엇을, 왜 `debuggable`이 아니라 그것을 선언해야 하는가? (3) `perf_event_open`이 출하 빌드에서 잠기는 보안상 이유는?

**참고** — Perfetto 문서(perfetto.dev) · simpleperf(developer.android.com/ndk/guides/simpleperf) · Android 트레이싱(developer.android.com/topic/performance/tracing) · AOSP `external/perfetto`, `system/extras/simpleperf` · `perf_event_paranoid`(리눅스 커널 문서)

*다음 글: [CTS·VTS·STS](/posts/android-expert-p2c22/).*
