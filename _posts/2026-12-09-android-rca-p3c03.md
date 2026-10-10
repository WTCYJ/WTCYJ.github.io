---
layout: post
title: "call graph·data-flow"
date: 2026-12-09 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RCA, CallGraph, DataFlow, TaintAnalysis]
excerpt: "결함 사이트가 존재한다고 취약점이 아니다. call graph는 '도달 가능한가'만, data-flow는 '무엇이 흐르는가'를 답한다 — 그리고 순수 Java call graph는 JNI 경계에서 조용히 끊긴다."
---

크래시 하나를 잡고 나면 두 개의 질문이 남는다. 이 결함 사이트에 공격자가 **도달**할 수 있는가, 그리고 도달한다면 거기서 **무엇을 조종**할 수 있는가. 이 둘을 뭉뚱그리는 순간 "크래시 = 취약점"이라는 가장 흔한 과장이 태어난다. 어떤 함수 안에 `memcpy` 하나가 위험해 보인다고 그것이 곧 익스플로잇 가능한 결함은 아니다. 그 지점까지 신뢰 경계 밖의 값이 실제로 흘러들어와야 한다.

근본 원인 분석(RCA)에서 이 두 질문을 각각 담당하는 도구가 call graph와 data-flow다. 하나는 "제어가 여기 닿을 수 있나"(reachability), 다른 하나는 "오염된 값이 여기까지 전파되나"(taint)를 답한다. 이 글은 폴트 사이트에서 신뢰 경계까지 거슬러 올라가는 이 두 축을, 자작 취약 앱과 이미 패치된 공개 결함 위에서 분석한 기록이다.

> **한 줄 결론**: call graph는 도달성을, data-flow는 오염 전파를 답한다. 결함 사이트가 신뢰 경계의 source에서 **도달 가능하고**, 공격자 제어 값이 그 사이트의 위험 피연산자까지 **흐를 때만** 근본 원인 후보다 — 도달성은 필요조건이지 충분조건이 아니다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 폴트 사이트를 시작점으로 잡고, (1) 그 지점으로 들어오는 호출 에지를 따라 신뢰 경계까지 거슬러 오르는 **call graph 분석**과 (2) 신뢰 경계의 source에서 위험 피연산자까지 값을 좇는 **data-flow(taint) 분석**을 어떻게 결합해 근본 원인을 국소화하는지를 다룬다. 목표는 무기화가 아니라 "프리미티브가 도달 가능한가"라는 판정까지다.

선수 지식은 이 파트 1장의 증상/트리거/폴트 사이트/근본 원인 4구분이다. call graph와 data-flow는 그 4구분을 실제 코드 위에 그리는 도구다 — 트리거(source)와 폴트 사이트를 잇는 것이 call graph, 그 사이로 흐르는 값이 있는지 확인하는 것이 data-flow, 폴트 사이트에서 근본 원인까지 역추적하는 것이 backward slice다. 여기에 Atlas의 신뢰 경계(익스포트 컴포넌트·Binder·Parcel·ContentProvider) 개념과 정적 분석의 기본기가 깔린다.

전체 구조에서 이 장은 RCA의 "지도 그리기" 단계다. 이후 4장의 상태 기계·인과 그래프, 6장의 최소 재현, 16장의 patch diff 가 모두 여기서 그린 source→sink 경로 위에서 움직인다.

## 핵심 개념 — 도달성과 오염은 다른 질문이다

call graph는 노드가 함수/메서드, 에지가 "A가 B를 호출한다"인 그래프다. 결함 사이트로 들어오는 에지(호출자, xref)를 역방향으로 따라가면 "어디서 여기 닿을 수 있나"를 얻는다. `Source-confirmed` data-flow(taint) 분석은 신뢰 경계의 **source**(비신뢰 입력)에서 **sink**(위험 연산)까지 def-use 사슬을 따라 값의 전파를 추적한다 — 중간에 검증/정화(sanitizer)가 있으면 오염이 끊긴다.

핵심은 이 둘이 **다른 질문**이라는 것이다. 표로 못 박는다.

| 질문 | 도구 | 답하는 것 | 답하지 못하는 것 |
|--|--|--|--|
| 이 결함 사이트에 제어가 닿나? | call graph(xref/callers) | 도달성(reachability) | 어떤 값이 흐르는지 |
| 공격자 값이 위험 피연산자에 닿나? | data-flow(taint) | source→sink 오염 전파 | 실제 실행 빈도·타이밍 |
| 어디서 불변식이 처음 깨지나? | backward slice | 근본 원인 후보 | 도달성만으로는 부족 |

1장의 4구분에 대입하면 이렇게 맞물린다. **증상**은 SIGSEGV, **트리거**는 익스포트 컴포넌트로 들어온 Intent, **폴트 사이트**는 크래시가 난 명령(예: `memcpy`), **근본 원인**은 그 위쪽 어딘가에서 "길이 ≤ 버퍼 크기" 같은 불변식이 처음 깨진 지점이다. call graph가 트리거→폴트 사이트를 잇고, data-flow가 그 사이로 공격자 값이 흐름을 확인하고, backward slice가 폴트 사이트→근본 원인을 되짚는다. `Inferred`

흔한 오개념 하나 — call graph에 경로가 보인다고 취약점이 아니다. 그 경로에 오염된 값이 흐르지 않거나, 흐르더라도 도중의 검증이 값을 정화하면 폴트 사이트는 공격자 손을 벗어난다. 반대로 오염은 확인됐는데 도달성이 특정 권한·설정에 막혀 있을 수도 있다. 두 축을 **모두** 통과한 경로만 근본 원인 후보다.

> **[그림 1]** jadx-gui의 Find Usages로 `getStringExtra` 호출부에서 helper 메서드를 거쳐 네이티브 브리지 메서드까지 이어지는 Java call graph 체인을 펼친 화면(네이티브 메서드에서 체인이 끊기는 지점 포함) — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

data-flow 분석은 source와 sink를 먼저 정의해야 시작된다. Android에서 source는 **공격자가 값을 넣을 수 있는 지점**이다.

- 익스포트된 Activity/Service/Receiver가 받는 Intent extra
- Binder 트랜잭션(`onTransact`, AIDL 스텁)이 언마샬하는 Parcel 데이터
- ContentProvider의 `query`/`insert` 인자
- 네트워크·파일·클립보드 등 외부 입력
- 네이티브 측: JNI 진입점이 받는 `jstring`/`jbyteArray`, 또는 파싱하는 비신뢰 바이트

sink는 폴트 사이트가 되는 위험 연산이다 — 경계 없는 `memcpy`/인덱스, 크기 계산 없는 할당, 쿼리 문자열 결합, `dlopen`/`exec` 등. 위협 모델은 단순하다. **공격자가 source를 제어한다. 질문은 source→sink 경로가 존재하고(call graph), 그 경로가 공격자 값을 정화 없이 sink까지 실어 나르느냐(data-flow)다.** 이 판정까지가 안전 범위이며, 여기서 프리미티브의 존재를 확인하면 멈춘다. 무기화된 익스플로잇 체인은 이 글의 범위 밖이다.

## 분석 — 자작 취약 앱에서 두 축을 겹치기

자작 앱 하나를 놓는다. 익스포트된 `MainActivity`가 Intent extra `payload`(String)를 읽어 helper를 거쳐 JNI로 네이티브 `copy()`에 넘기고, 네이티브에서 고정 크기 스택 버퍼에 길이 검증 없이 `memcpy`한다. 전형적인 스택 오버플로 결함이다.

```java
// 자작 취약 앱 — source: 익스포트 Activity의 Intent extra
public class MainActivity extends Activity {
  @Override protected void onCreate(Bundle b) {
    super.onCreate(b);
    String p = getIntent().getStringExtra("payload"); // <- taint source
    new NativeBridge().copy(p);                        // <- Java call graph, 여기서 끊김
  }
}
class NativeBridge { native void copy(String s); }     // 본문 없음(네이티브)
```

```c
// libnativebridge.so — sink: 길이 검증 없는 memcpy
JNIEXPORT void JNICALL
Java_com_example_NativeBridge_copy(JNIEnv* e, jobject o, jstring s) {
  const char* in = (*e)->GetStringUTFChars(e, s, 0);
  char buf[64];
  memcpy(buf, in, strlen(in));   // <- fault site: strlen(in) > 64 이면 OOB write
  (*e)->ReleaseStringUTFChars(e, s, in);
}
```

**Java 측 forward reachability.** FlowDroid(Arzt et al., PLDI 2014)로 source→sink taint를 돌린다. 사전 정의된 `SourcesAndSinks.txt`에 `getStringExtra`를 source로, `copy`(또는 그 바깥의 로그·쿼리)를 sink로 넣는다. SourcesAndSinks 형식과 CLI 플래그는 FlowDroid 버전마다 다르니 원문 문서를 재확인한다. `Inferred`

```bash
# FlowDroid CLI (jar/플래그는 버전 확인 필요)
java -jar soot-infoflow-cmd-jar-with-dependencies.jar \
  -a app-debug.apk -p platforms/android-34/android.jar \
  -s SourcesAndSinks.txt
```

`예시 출력(교체)`:

```
[main] INFO ...InfoflowResults - Found a flow to sink virtualinvoke $r.<...NativeBridge: void copy(java.lang.String)>,
    from the following sources:
    - $r = getIntent().getStringExtra("payload") (in ...MainActivity: void onCreate(...))
```

여기서 결정적인 한계가 드러난다. 순수 Java 도구는 `copy`가 **네이티브 메서드라 Java 본문이 없어**, call graph가 JNI 경계에서 끊긴다. FlowDroid는 "copy로 흐른다"까지만 말하고, 그 값이 `memcpy`까지 가는지는 모른다. `Reported` Java 쪽만 보고 "sink는 로깅뿐, 위험 없음"이라 결론 내리면 진짜 폴트 사이트를 놓친다.

**네이티브 측 backward reachability.** 그래서 경계를 넘어 `.so`를 따로 본다. 폴트 사이트(`memcpy`)로 들어오는 xref를 뽑아 도달성을 확인한다.

```bash
# 결함 사이트(memcpy)로 들어오는 call graph 에지(xref) 나열
r2 -A -q -c 'axt sym.imp.memcpy' libnativebridge.so
```

`예시 출력(교체)`:

```
Java_com_example_NativeBridge_copy 0x1180 [CALL:--x] call sym.imp.memcpy
```

`axt`(analyze xrefs to)가 `memcpy`의 호출자로 `Java_..._copy`를 짚어준다. `Source-confirmed` JNI 심볼 이름 규칙(`Java_<pkg>_<class>_<method>`)이 Java `NativeBridge.copy`와 대응하므로, Java 그래프의 끊긴 끝과 네이티브 그래프의 시작을 **수동으로 이어** 하나의 경로를 완성한다: `onCreate → copy(JNI) → memcpy`. 이 브리지가 없으면 도달성 증명이 반쪽이다.

> **[그림 2]** radare2 `axt sym.imp.memcpy` 실행으로 결함 사이트(memcpy)로 들어오는 네이티브 xref(호출자) 목록을 출력한 터미널 — *실측 스크린샷 자리*

**두 축 겹치기.** 이제 (1) 도달성: `onCreate`(source)→`memcpy`(sink) 경로가 call graph로 이어졌고, (2) 오염: `getStringExtra`의 String이 `GetStringUTFChars`로 `char*`가 되어 `memcpy`의 소스·길이(`strlen(in)`)에 그대로 쓰인다. 두 축이 겹치는 지점 — 길이 검증 없이 `strlen(in)`을 `buf[64]`에 복사하는 곳 — 이 근본 원인 후보다. backward slice로 `buf`의 크기(64)와 복사 길이(`strlen(in)`) 사이에 크기 관계를 강제하는 검증이 경로상에 **없음**을 확인하면 후보가 확정된다.

## Root Cause — 왜 도달성만으로는 부족한가

call graph 도달성이 취약점을 증명하지 못하는 이유는 그것이 **필요조건이지 충분조건이 아니기** 때문이다. 폴트 사이트가 취약점이 되려면 세 가지가 동시에 성립해야 한다.

1. **도달성** — source에서 sink까지 실행 경로가 존재한다(call graph).
2. **제어** — 공격자 값이 그 경로를 따라 sink의 위험 피연산자에 흘러든다(data-flow).
3. **정화 부재** — 경로 어디에도 그 값을 무해화하는 검증이 없다.

근본 원인은 이 세 조건이 처음으로 함께 깨지는 지점, 즉 **보안 불변식이 최초로 위반된 곳**이다. 위 예에서 불변식은 "복사 길이 ≤ 대상 버퍼 크기"이고, 그것이 깨진 곳은 크래시가 난 `memcpy` 그 자체가 아니라 — 크래시는 증상일 뿐 — 길이 검증을 넣었어야 할, `memcpy` 직전(혹은 입력을 받은 직후)이다. 폴트 사이트와 근본 원인이 물리적으로 같은 줄일 수도, 여러 프레임 위일 수도 있다. backward slice가 존재하는 이유가 바로 이 거리를 좁히기 위해서다. `Inferred`

이 프레임은 과장을 막는다. call graph에 `memcpy`가 보인다는 이유만으로 CVE를 부르는 것은 도달성 하나를 세 조건 전부로 착각하는 것이다. 반대로 data-flow가 오염을 확인했더라도, 그 경로가 특정 권한·설정·비익스포트로 막혀 신뢰 경계 밖에서 닿지 않으면 영향은 낮아진다. 두 축의 교집합만이 정직한 근본 원인이다.

## 방어와 회귀 검증

RCA의 관점에서 **패치의 임무는 source→sink 경로를 끊는 것**이다. 방법은 둘 중 하나다 — 경로상에 검증을 넣어 data-flow의 오염을 끊거나(예: `if (strlen(in) >= sizeof(buf)) return;`), 아예 호출 에지를 제거해 call graph에서 sink를 도달 불가로 만들거나. 그래서 회귀 검증 오라클은 단순하다: **패치 후 같은 taint 쿼리를 다시 돌려 "no flow found"가 나오면 통과**다. 이 조건은 재현 가능하게 기록해 둔다.

여기서 정직해야 할 한계가 두 겹이다.

- **정적 call graph는 "soundy"하다.** 리플렉션(`Class.forName`/`Method.invoke`), `DexClassLoader`, 동적 프록시는 정적 분석에 보이지 않는 에지를 만든다 → under-approximation(놓친 경로). `Reported` 따라서 순수 Java 도구의 "경로 없음"은 **안전 증명이 아니다**. JNI로 끊겼거나 리플렉션으로 우회됐을 수 있다.
- **과대 근사도 비용이다.** 가상 호출을 CHA로 풀면 불가능한 대상까지 에지로 잡혀(over-approximation) 트리아지가 늘어난다. 네이티브의 간접 호출(함수 포인터·vtable)은 반대로 해소가 안 돼 에지가 빠지기도 한다.

그래서 "정적으로 경로 없음"과 "실제로 도달 불가"를 같은 말로 쓰지 않는다. 애매하면 트리거를 실제로 실행해 커버리지로 경로를 확인하는 동적 검증이 정적 근사의 빈틈을 메운다. 회귀 검증은 정적 재실행과 동적 재현을 **둘 다** 남겨야 신뢰할 수 있다.

## 정리

- call graph는 도달성, data-flow는 오염 전파를 답하는 **다른 질문**이다. 둘을 겹친 교집합만 근본 원인 후보다.
- 결함 사이트가 보인다고 취약점이 아니다 — 도달성·제어·정화 부재 세 조건이 함께 깨진 곳이 근본 원인이다.
- 순수 Java call graph는 JNI 경계에서 끊긴다. Java↔native를 수동으로 브리지하지 않으면 도달성 증명이 반쪽이다.
- 정적 "경로 없음"은 안전 증명이 아니다(리플렉션·JNI·간접 호출). 패치는 경로를 끊고, 회귀는 "no flow"를 오라클로 재실행한다.

**점검 질문** — (1) call graph 도달성이 취약점의 충분조건이 아닌 이유를 세 조건으로 설명하라. (2) FlowDroid의 "copy로 흐른다"가 왜 폴트 사이트 확인에 부족한가? (3) 정적 도구의 "경로 없음"을 안전 증명으로 쓰면 안 되는 두 가지 이유는?

**참고** — FlowDroid(Arzt et al., "FlowDroid", PLDI 2014, https://www.bodden.de/pubs/far+14flowdroid.pdf) · Soot/Jimple(https://soot-oss.github.io/soot/) · CodeQL data-flow(https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/) · radare2 `axt`(https://book.rada.re/) · "In Defense of Soundiness"(Livshits et al., CACM 2015)

*다음 글: [state machine·causal graph](/posts/android-rca-p3c04/).*
