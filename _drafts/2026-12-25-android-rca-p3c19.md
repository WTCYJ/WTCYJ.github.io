---
layout: post
title: "증거 등급·Confidence"
date: 2026-12-25 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RCA, 증거등급, Confidence, CVSS]
excerpt: "툼스톤·ASan·KASAN 리포트는 결론이 아니라 관측이다. 재현된 크래시는 '버그가 있다'는 증거지 '익스플로잇 가능하다'는 증거가 아니며, 증거 등급을 붙이지 않은 RCA는 가장 약한 추론이 가장 강한 관측의 확신을 물려받는다."
---

RCA는 결국 "이 크래시의 근본원인은 X다"라는 **주장의 묶음**이다. 그런데 주장마다 근거의 무게가 다르다. 내가 재현한 로그는 반박하기 어렵고, 벤더 어드바이저리 한 줄은 그보다 약하며, "이건 아마 RCE일 것"은 근거가 아니라 소망이다. 이 셋을 한 문단에 뭉쳐 같은 확신의 어투로 쓰면, 가장 약한 추론이 가장 강한 관측의 확신을 물려받는다. 보고서를 읽는 사람은 어디까지가 관측이고 어디부터가 해석인지 구분하지 못한다.

이 글은 RCA의 각 주장에 **증거 등급(evidence grade)**과 **confidence**를 붙이는 방법을 정리한 기록이다. 이 시리즈가 로드베어링 문장마다 달아 온 `Source-confirmed`/`Reported`/`Inferred` 라벨이 바로 그 도구인데, 여기서 그 규칙을 형식화하고 confidence 등급, 그리고 영향 산정(DoS/RCE 경계)이 어떻게 증거에 종속되는지를 하나로 묶는다.

> **한 줄 결론**: 증거 등급은 "그 주장이 무엇에 근거하는가"(관측/2차보고/추론)를, confidence는 "그 근본원인이 얼마나 확정적인가"를 나타내는 별개의 축이다. 인과 사슬의 confidence는 가장 약한 링크를 넘지 못하고, 영향 등급(CVSS)은 증거가 실증한 프리미티브를 넘어서면 안 된다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 RCA 결론에 등급을 붙이는 법을 다룬다. 세 가지를 구분한다 — (1) 증거 등급(주장이 기대는 근거의 종류), (2) confidence(근본원인 확정도), (3) 영향 confidence(익스플로잇 가능성·심각도의 근거). 세 축은 자주 하나로 뭉개지지만 서로 다른 것을 잰다.

선수 지식은 앞 장들에 깔려 있다. 1장에서 증상/트리거/폴트사이트/근본원인을 분리했고, 3장·4장에서 call graph·data-flow와 causal graph로 인과 사슬을 그렸으며, 5장에서 baseline/patched/negative control로 반례를 통제했고, 6장에서 최소 재현으로 관측을 반복 가능하게 만들었으며, 7장에서 크래시와 exploitability를 분리했다. 이 장은 그 위에 "그래서 각 주장을 얼마나 믿을 수 있는가"를 올린다. 다음 20장(제출 가능한 RCA 보고서)이 이 등급들을 문서 형식에 담는다.

전체 구조에서 이 장은 **정직성 게이트**다. 관측을 얼마나 모았든, 등급을 붙이지 않으면 보고서는 과장 아니면 과소평가로 흐른다. 특히 버그바운티처럼 심각도에 보상이 걸린 맥락에서는, 등급이 곧 자기 검열 장치다.

## 핵심 개념 — 두 개의 축, 하나의 규율

증거 등급과 confidence는 다른 축이다. 표로 분리한다.

**축 1 — 증거 등급(이 시리즈의 라벨 규약):**

| 라벨 | 정의 | 예시 아티팩트 | 재검증 |
|--|--|--|--|
| `Source-confirmed` | 직접 검증 가능한 1차 근거 | 내가 재현한 logcat/툼스톤, 소스·패치 커밋 원문, ASan/KASAN 리포트 | 재현·재대조 가능 |
| `Reported` | 신뢰할 만한 2차 보고(직접 검증 안 함) | 벤더 어드바이저리 서술, 연구자 발표, 불리틴 문구 | 원문 재확인 필요 |
| `Inferred` | 위 근거로부터의 논리적 추론 | "폴트사이트가 여기니 원인은 길이 검증 부재일 것" | 논리만, 관측 아님 |

핵심 착각 하나 — **툼스톤·ASan·KASAN 리포트는 `Source-confirmed` 관측이지 결론이 아니다.** 백트레이스는 "여기서 죽었다"를 말할 뿐, "왜 이게 취약점인지"는 그 위에 얹은 `Inferred` 해석이다. 도구 출력의 확실성을 해석까지 그대로 물려주는 게 가장 흔한 오류다. `Inferred`

**축 2 — confidence(근본원인 확정도):**

| 등급 | 조건 |
|--|--|
| Confirmed(확정) | 근본원인이 소스/패치로 직접 확인되고, 최소 재현으로 반복되며, patched build에서 재현이 사라짐(negative control 통과) |
| Probable(유력) | 관측과 일치하는 단일 가설이 있으나 소스 수준 확증 또는 반례 통제가 없음 |
| Possible(가능) | 관측으로 구분되지 않는 복수 가설이 남음 |
| Speculative(추정) | 관측 근거 없이 그럴듯한 서사 |

두 축은 직교한다. 어드바이저리만 읽고 쓴 근본원인은 근거가 `Reported`, confidence는 잘해야 Probable이다. 반대로 내가 재현·대조까지 마친 결론은 근거 `Source-confirmed`에 confidence Confirmed다.

> **[그림 1]** 실제 RCA 작업 노트에서 각 주장 줄에 `Source-confirmed`/`Reported`/`Inferred` 라벨과 confidence 등급을 달아 둔 화면 — 옆에 그 주장이 기대는 아티팩트(재현 logcat 또는 툼스톤)를 나란히 배치 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

증거 등급에서 "신뢰 경계"는 네트워크가 아니라 **네가 관측한 것과 추론한 것 사이의 선**이다. 이 RCA의 위협 모델에서 적은 외부 공격자가 아니라 **분석자 자신의 확증 편향**이다. 크래시를 하나 재현하면, 그게 대단한 취약점이길 바라는 관성이 붙는다. SIGSEGV를 보면 임의 쓰기로, DoS를 보면 RCE로 끌어올리고 싶어진다. 심각도에 보상이 걸려 있으면 이 편향은 경제적으로 강화된다.

증거 등급은 이 편향에 대한 방어선이다. 규율은 단순하다 — **아티팩트 없는 주장은 등급을 못 올린다.** confidence를 Confirmed로 쓰려면 재현 로그와 negative control이 있어야 하고, 영향을 RCE로 쓰려면 제어 가능한 프리미티브의 실증(7장)이 있어야 한다. 근거를 못 대면 등급을 내린다. 내리는 게 손해처럼 보이지만, 과장된 Confirmed 한 번이 보고서 전체의 신뢰를 깎는 것보다 싸다.

## 분석 — 재현된 크래시 하나를 줄 단위로 등급 매기기

자작 파서 앱(또는 이미 패치된 공개 CVE를 클래스 수준에서)에서 재현한 크래시를 예로, 결론을 한 문장씩 쪼개 등급을 붙인다. 이게 RCA를 "정직하게" 만드는 실제 작업이다.

| # | 주장 | 근거 | 증거 등급 | confidence |
|--|--|--|--|--|
| 1 | 입력 X를 주면 대상 프로세스가 SIGSEGV로 종료된다 | 재현 logcat + 툼스톤(반복 재현) | `Source-confirmed` | Confirmed |
| 2 | 폴트사이트는 `parseHeader`의 `memcpy` | 툼스톤 backtrace ↔ 소스 대조 | `Source-confirmed` | Confirmed |
| 3 | 근본원인은 복사 전 길이 검증 부재 | patch diff에 추가된 경계 검사 | `Source-confirmed` | Confirmed |
| 3′ | (패치 미공개라면) 원인은 길이 검증 부재일 것 | 폴트사이트로부터의 추론 | `Inferred` | Probable |
| 4 | 공격자가 오프셋을 제어할 수 있다 | 입력 필드→오프셋 데이터플로 추적(3장) | `Inferred` | Possible |
| 5 | 이 버그는 RCE로 이어진다 | (제어 쓰기 프리미티브 미실증) | — | **Speculative** |

여기서 3과 3′을 나눈 이유가 이 글의 요점이다. **patch diff가 있으면 근본원인은 `Source-confirmed`/Confirmed로 올라가지만, 없으면 같은 문장이 `Inferred`/Probable로 내려앉는다.** 근거가 바뀌면 등급이 바뀐다. 5는 프리미티브를 실증하지 못했으니 등급 자체가 없다 — 보고서에 넣으려면 "미실증 가설"로 명시하거나 빼야 한다. 크래시는 "버그가 있다"의 증거지 "익스플로잇 가능하다"의 증거가 아니다. `Inferred`

**인과 사슬의 confidence는 가장 약한 링크로 수렴한다.** 결론(5)이 4→3→2→1 사슬 위에 서 있고 4가 Possible이면, 앞이 아무리 Confirmed라도 최종 결론은 Possible을 넘지 못한다. 3장·4장에서 그린 causal graph의 각 엣지에 등급을 달면, 사슬 전체의 confidence는 자동으로 **가장 약한 엣지**로 수렴한다. `Inferred`

> **[그림 2]** 재현한 ASan(또는 툼스톤) 리포트를 patch diff와 나란히 띄우고, 위 표의 어느 주장이 `Source-confirmed`이고 어느 것이 `Inferred`인지 화살표로 대응시킨 화면 — *실측 스크린샷 자리*

**영향 등급도 증거에 종속된다.** 위 크래시를 증거가 실제로 뒷받침하는 만큼만 CVSS로 산정하면, 재현된 것은 가용성 손상뿐이다. 로컬 co-located 앱이 malformed 입력으로 대상 컴포넌트를 죽이는 DoS:

- `CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L` → Base **4.0**(Medium). `Source-confirmed`

여기서 프리미티브 실증 없이 "메모리 제어가 되니 RCE"라고 C/I/A를 전부 High로 올리면:

- `CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` → Base **8.4**(High) — 단, C/I/A:H는 프리미티브 미실증 가정. impact 값은 `Speculative`, 벡터→점수 산술만 `Source-confirmed`

4.0에서 8.4로의 도약은 **증거가 아니라 가정이 만든 4.4점**이다. 벡터를 공개하면 누구나 재계산해 그 도약이 무엇에 근거하는지 물을 수 있다. (두 점수의 벡터→점수 산술만 CVSS v3.1 공식으로 재계산 가능하다 — `Source-confirmed`. 8.4의 impact 값 자체는 미실증 가정이다.) 벡터 없이 "심각도 High"만 적으면 이 검증이 불가능해진다.

## Root Cause — 왜 등급 없는 RCA가 실패하는가

근본원인은 인지적이다. 사람은 "나는 X를 관측했다"와 "나는 X가 Y를 일으킨다고 믿는다"를 한 문장으로 압축하는 경향이 있다. 자연어는 관측과 해석을 같은 평서문으로 쓰기 때문에, 문장만 봐서는 둘이 구분되지 않는다. 등급을 명시적으로 붙이지 않으면, 해석은 관측의 겉보기 확실성을 **공짜로** 물려받는다. `Inferred`

여기에 두 힘이 겹친다. 첫째, 크래시 트리아지 도구(툼스톤·ASan·KASAN)는 강력한 관측을 주지만 결론은 주지 않는다 — 결론은 언제나 그 위에 얹은 추론이다. 도구가 "확실해 보이는" 출력을 뱉을수록 그 위의 추론도 확실해 보인다. 둘째, 심각도에 보상·평판이 걸리면 등급을 올리는 방향으로 편향이 쏠린다. 이 둘이 만나면 `Inferred`/Speculative가 `Source-confirmed`/Confirmed의 어투로 위장한다.

증거 등급은 이 압축을 강제로 되돌린다. 각 주장을 근거로 되돌아가 "이건 봤나, 읽었나, 생각했나"를 묻게 만든다. Project Zero의 in-the-wild 루트코즈 분석들이 관측과 추론을 분리해 서술하는 것도 같은 규율이다. `Reported`

## 방어와 회귀 검증

등급은 한 번 붙이고 끝이 아니다. 시간이 지나면 기억이 "아마"를 "확실히"로 바꾼다 — confidence는 방치하면 부풀어 오른다. 재검증 루틴으로 눌러 둔다.

- **아티팩트 첨부 강제.** 모든 Confirmed 주장 옆에 재현 가능한 아티팩트(로그, 커밋 해시, 툼스톤 파일)를 붙인다. 아티팩트를 못 대는 Confirmed는 Probable로 강등한다.
- **negative control로 승급(5장).** 근본원인을 Confirmed로 올리려면 patched build에서 재현이 사라지는 걸 확인해야 한다. 이 통제 없이는 "이 코드가 원인"이 아니라 "이 코드에서 죽는다"까지만 참이다.
- **최소 재현으로 관측 고정(6장).** 재현이 확률적이면 confidence도 확률적이다. 입력을 축소해 결정론적으로 재현되게 만든 뒤에야 Confirmed를 쓴다.
- **벡터·해시 공개.** CVSS는 점수가 아니라 벡터를, 커밋은 링크가 아니라 해시를 남긴다. 재계산·재대조가 되는 근거만 등급을 지탱한다.
- **제출 전 스윕.** 보고서의 모든 문장을 훑어 "이건 관측인가 해석인가"를 재분류하고, 라벨 없는 로드베어링 문장을 찾아 등급을 채운다. 20장의 체크리스트가 이 스윕을 형식화한다.

## 정리

- 증거 등급(`Source-confirmed`/`Reported`/`Inferred`)과 confidence(Confirmed/Probable/Possible/Speculative)는 **다른 축**이다. 전자는 근거의 종류를, 후자는 근본원인 확정도를 잰다.
- 인과 사슬의 confidence는 **가장 약한 링크**를 넘지 못한다. causal graph의 엣지마다 등급을 달면 최종 결론의 등급이 자동으로 정해진다.
- 영향(CVSS)은 증거가 실증한 프리미티브를 넘어서면 안 된다. 크래시=가용성(DoS), RCE는 제어 프리미티브 실증이 있을 때만. 벡터를 공개해 재계산 가능하게 남긴다.
- 툼스톤·ASan은 관측이지 결론이 아니다. 도구 출력의 확실성을 해석에 물려주지 말 것.

**점검 질문** — (1) 같은 "근본원인은 길이 검증 부재"라는 문장이 `Source-confirmed`가 되기도 `Inferred`가 되기도 하는데, 무엇이 그 등급을 가르는가? (2) 4→3→2→1 사슬에서 3·2·1이 Confirmed이고 4가 Possible이면 최종 결론의 confidence는? (3) 재현된 SIGSEGV만으로 CVSS의 C/I를 High로 올릴 수 없는 이유는?

**참고** — [CVSS v3.1 Specification (FIRST)](https://www.first.org/cvss/v3-1/specification-document) · [Google Project Zero — root cause analyses](https://googleprojectzero.github.io/0days-in-the-wild/rca.html) · [MITRE CWE](https://cwe.mitre.org/) · [Android Security Bulletins — severity](https://source.android.com/docs/security/overview/updates-resources)

*다음 글: [제출 가능한 RCA 보고서](/posts/android-rca-p3c20/).*
