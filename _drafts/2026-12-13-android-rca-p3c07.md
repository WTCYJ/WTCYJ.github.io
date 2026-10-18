---
layout: post
title: "crash와 exploitability 구분 — 크래시는 증상이지 취약점이 아니다"
date: 2026-12-13 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, RootCauseAnalysis, Tombstone, ASan, Exploitability]
excerpt: "널 역참조 SIGSEGV를 RCE라 부르지 마라. 크래시는 증상이고, 영향은 '어떤 프리미티브가 어느 신뢰 경계를 넘느냐'로만 정직하게 산정된다. 흔한 함정 하나 — fault addr 0x0은 거의 항상 DoS다."
---

퍼저나 자작 결함 앱이 크래시를 뱉으면 반쯤은 이미 흥분한다. 하지만 크래시는 **증상**일 뿐이다. 그 크래시가 보안 취약점인지, 취약점이라면 정보 노출인지 DoS인지 RCE인지는 완전히 별개의 판정이다. RCA에서 가장 자주 무너지는 지점이 바로 여기다 — 툼스톤 하나 보고 "메모리 손상 = RCE"로 건너뛰거나, 반대로 진짜 프리미티브를 DoS로 과소평가한다.

이 글은 크래시를 **증상 → 프리미티브 → 영향 상한 → 익스플로잇 가능성**의 네 단계로 분리해 정직하게 산정하는 방법을 정리하고, Android의 툼스톤·ASan·HWASan 리포트를 그 틀에 넣어 판독한 기록이다. 안전 범위는 자작 결함 앱과 에뮬레이터, 그리고 이미 공개·패치된 사례뿐이다. 무기화된 익스플로잇은 다루지 않고, "프리미티브가 존재한다"는 지점까지만 간다.

> **한 줄 결론**: 크래시 트라이아지의 결론은 "취약/비취약"이 아니라 "어떤 프리미티브가 어느 신뢰 경계를 넘느냐"다. fault addr가 0 근처인 read AV는 거의 DoS이고, 공격자가 크기·내용을 통제하는 write AV가 신뢰 경계를 넘을 때만 RCE 후보다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 하나의 크래시를 놓고 (1) 어떤 신호/리포트가 나왔는지 판독하고, (2) 거기서 어떤 메모리 프리미티브가 도출되는지 뽑고, (3) 그 프리미티브가 넘는 신뢰 경계를 기준으로 영향 상한을 정하고, (4) 익스플로잇 가능성을 등급으로 붙이는 절차를 다룬다. 실제 무기화(ROP 체인, 힙 그루밍)는 범위 밖이다.

선수 개념 세 가지가 밑에 깔린다. 증상과 근본원인을 분리하는 RCA의 기본 골격(이 파트 1장 "Symptom/Trigger/Fault Site/Root Cause 구분"), 프로세스·가상메모리 모델이 있어야 fault address와 매핑을 읽을 수 있고(Atlas C04), ASLR·CFI·PAC/BTI/MTE 같은 완화(Atlas C37)를 알아야 "이론상 RCE"가 왜 실무에서 DoS로 깎이는지 이해된다. 전체 구조에서 이 장은 RCA 파트의 **영향 산정 축**이다 — 앞 장들이 "어디서 왜 터지나"를 다뤘다면, 여기는 "그래서 그게 얼마나 위험한가"를 정직하게 매긴다.

## 핵심 개념 — 증상·프리미티브·영향의 분리

세 단어를 절대 뭉치지 않는 것이 이 장의 전부다.

- **증상(symptom)**: 관측된 사건. SIGSEGV, `FATAL EXCEPTION`, ASan 리포트, ANR. 눈에 보이는 것.
- **프리미티브(primitive)**: 그 증상이 노출하는 메모리/제어 능력. OOB read(정보 노출), OOB write(변조), UAF(수명 위반→타입 혼동), PC 제어(제어 흐름 탈취). 익스플로잇의 재료.
- **영향 상한(impact ceiling)**: 프리미티브가 넘는 신뢰 경계에 따라 결정되는 최악의 결과. DoS / 정보 노출 / 권한 상승 / RCE.

핵심 규칙 — **증상에서 영향으로 곧장 건너뛰지 않는다.** 반드시 프리미티브를 경유한다. "크래시가 났으니 위험"이 아니라 "이 크래시는 T0에서 16바이트 힙 청크 오른쪽으로 4바이트 WRITE 프리미티브를 준다"까지 내려가야 영향을 논할 자격이 생긴다. `Inferred`

| 증상(신호/리포트) | 전형적 프리미티브 | 영향 상한(경계 넘을 때) | 익스플로잇 버킷 |
|--|--|--|--|
| SIGSEGV, code 1(SEGV_MAPERR), fault addr≈0 | null 역참조(read/write) | DoS | probably not exploitable |
| SIGSEGV read AV, 통제된 원거리 주소 | OOB read | 정보 노출 | probably exploitable(누출 대상 따라) |
| SIGSEGV write AV, 통제된 주소·값 | OOB/임의 write | 변조→제어 흐름 | probably exploitable |
| SIGSEGV, PC=통제된 값 | 제어 흐름 탈취 | RCE 후보 | exploitable |
| SIGABRT(6), `abort_message`=stack canary/`fortify` | 스택 버퍼 오버플로 검출 | 완화가 이미 차단 | (완화 확인 필요) |
| SIGILL(4) on BTI landing | 간접 분기 위반 | 완화 발동 흔적 | 정황 증거 |
| ASan heap-use-after-free | UAF | 타입 혼동→제어 | exploitable 후보 |
| Java `FATAL EXCEPTION`(uncaught) | 로직/입력 검증 결함 | 앱/서비스 크래시(DoS) | 메모리 손상 아님 |

버킷 이름(exploitable / probably exploitable / probably not exploitable / unknown)은 역사적으로 MSEC의 `!exploitable` 분류에서 왔고, 지금도 크래시 트라이아지의 공통 어휘다. `Reported` 이 표의 오른쪽 두 칸은 **가설**이지 결론이 아니다 — 실제 등급은 신뢰 경계와 완화까지 확인해야 확정된다.

> **[그림 1]** 자작 결함 앱의 native 크래시가 logcat DEBUG 섹션에 남긴 툼스톤 헤더 — `signal`·`code`·`fault addr` 세 줄에 밑줄 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

같은 프리미티브도 **어느 경계를 넘느냐**에 따라 영향이 완전히 달라진다. 크래시가 난 위치가 아니라, 그 크래시를 유발한 입력이 어디서 왔는지가 핵심이다.

- **내 앱이 내 입력에 크래시** — 신뢰 경계를 넘지 않는다. 자기 자신에 대한 DoS는 보안 취약점이 아니라 안정성 버그다. RCA에서 이걸 취약점으로 올리면 신뢰를 잃는다. `Inferred`
- **내 앱이 외부(악성) 콘텐츠에 크래시** — 원격 입력이 앱 신뢰 경계를 넘어온다. 파싱 코드의 메모리 손상이면 원격 RCE 후보. Stagefright(2015, 공개·패치)가 미디어 파싱 OOB write가 원격 콘텐츠로 도달한 대표 사례다. `Reported`
- **제3자 앱 → 시스템 서비스(Binder) 크래시** — 로컬 앱이 system_server를 죽이면 soft reboot로 이어지는 로컬 DoS다. 실제 취약점이지만 보통 Moderate급이지 Critical이 아니다. `Inferred`
- **커널 컨텍스트 크래시(KASAN)** — 권한 경계를 넘는 프리미티브면 권한 상승/RCE 상한이 가장 높다.

Android 자체 심각도 기준도 이 축을 따른다 — "권한 있는 컨텍스트에서의 원격 코드 실행"이 Critical, 로컬 정보 노출·DoS는 아래 등급이다. `Source-confirmed`(Android Severity Ratings) 위협 모델을 먼저 고정하지 않고 크래시부터 보면, 자기 DoS를 RCE로 부풀리는 함정에 정확히 빠진다.

## 분석 — 크래시 트라이아지 결정 절차

한 크래시를 받았을 때 순서대로 묻는다. 각 질문의 답이 다음 질문을 정한다.

1. **신호가 무엇인가.** SIGSEGV(11)=매핑/권한 위반(비FPAC 환경의 PAC 인증 실패=오염된 상위 비트 포인터 역참조 포함), SIGABRT(6)=런타임 검출(canary·`fortify`·`__stack_chk_fail`·ASan abort), SIGILL(4)=잘못된 명령(BTI landing 위반, FPAC 환경의 PAC 인증 실패 포함), SIGTRAP(5)=브레이크포인트/`brk` 소프트웨어 트랩(UBSan trap 등). 신호가 이미 "이게 완화에 걸린 크래시인지, 순수 손상인지"를 절반 알려준다. `Reported`(debuggerd 툼스톤 포맷 — PAC↔신호 매핑은 커널 소스 재확인 필요)
2. **read AV인가 write AV인가.** write가 read보다 위험하다. 툼스톤의 접근 종류와 폴트 명령(disassembly)으로 구분한다.
3. **fault addr가 어디인가.** 0 근처(예: 0x0~낮은 수천 번대)는 null 역참조 계열로, `mmap_min_addr` 덕분에 그 페이지를 매핑할 수 없어 대개 DoS다. 반대로 공격자가 값을 통제하는 주소면 프리미티브가 산다. `Inferred`
4. **PC가 통제되는가.** 폴트가 통제된 주소를 **실행**하려다 났으면(backtrace 최상단이 이상한 주소) 제어 흐름 탈취 신호로 가장 높은 등급이다.
5. **입력이 신뢰 경계를 넘었는가.** 위 신뢰 경계 표로 영향 상한을 고정한다.
6. **완화가 이미 막았는가.** SIGABRT가 canary/`fortify`면 그 경로는 이미 방어된 것 — "손상은 있으나 완화로 DoS로 강등"이 정직한 결론이다.

이 절차의 산출물은 한 문장이어야 한다: *"[신뢰 경계]를 넘는 입력이 [폴트 사이트]에서 [프리미티브]를 만들고, 완화 [X]를 고려하면 영향 상한은 [등급]이다."* 이 문장을 못 쓰면 아직 트라이아지가 끝난 게 아니다.

## 관측 — 툼스톤과 ASan 판독

자작 결함 앱(NDK `libcrashy.so`, 의도적 null 역참조와 힙 오버플로 두 경로)을 에뮬레이터(userdebug)에서 돌려 두 종류의 리포트를 나란히 본다. 툼스톤은 `/data/tombstones/`에 남고 root 권한으로 읽거나 logcat의 DEBUG 태그로 본다. `Source-confirmed`(Android native crash 문서)

```bash
# 툼스톤 확인 (userdebug/AVD)
adb root
adb shell ls /data/tombstones/
adb logcat -b crash -d | sed -n '/*** ***/,/backtrace/p'
```

null 역참조 경로의 툼스톤 헤더 — `예시 출력(교체)`:

```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
ABI: 'arm64'
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0000000000000000
backtrace:
      #00 pc 00000000000008a4  libcrashy.so (deref_null+16)
      #01 pc 00000000000009b0  libcrashy.so (Java_com_example_crashy_Native_run+24)
```

판독: 신호 SIGSEGV, code=1(주소 미매핑), fault addr=0x0. → null 역참조 read/write. `mmap_min_addr` 때문에 0 페이지를 통제할 수 없다 → **probably not exploitable, 영향은 DoS**. 여기서 멈춰야 한다.

힙 오버플로 경로는 앱을 ASan으로 빌드(`-fsanitize=address`, `wrap.sh`)하면 훨씬 풍부한 리포트를 준다. ASan은 할당/해제 스택까지 붙여줘 프리미티브 판정이 쉬워진다. `Source-confirmed`(NDK ASan 가이드) — `예시 출력(교체)`:

```
=================================================================
==6721==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x0072a1c4b010
WRITE of size 8 at 0x0072a1c4b010 thread T0
    #0 0x72... in parse_header libcrashy.so
0x0072a1c4b010 is located 0 bytes to the right of 16-byte region [...b000,...b010)
allocated by thread T0 here:
    #0 0x72... in malloc
    #1 0x72... in parse_header libcrashy.so
```

판독: **WRITE**(read보다 위험), 16바이트 청크 오른쪽 경계 밖으로 8바이트 쓰기, 폴트 사이트=`parse_header`. 만약 이 `parse_header`가 외부 파일 입력을 파싱한다면 원격 write 프리미티브 후보다. 하지만 여기까지는 "프리미티브 존재" 확인이고, 크기·오프셋·인접 객체 통제 여부는 별도 분석이다 — 무기화는 하지 않는다.

> **[그림 2]** 같은 결함 앱을 기본 빌드(툼스톤)와 ASan 빌드(heap-buffer-overflow 리포트)로 각각 크래시시켜 logcat에 나란히 띄운 대조 캡처 — *실측 스크린샷 자리*

HWASan(arm64 전용, 태그 포인터)과 KASAN(커널, Cuttlefish/커스텀 빌드)도 같은 틀로 읽는다 — 리포트 형식만 다를 뿐 "WRITE/READ · 크기 · 인접 객체 · 할당/해제 스택"을 뽑는 목적은 동일하다. `Source-confirmed`(HWASan 문서)

## Root Cause — 왜 크래시가 곧 취약점이 아닌가

크래시는 프로그램이 **정의되지 않은 상태를 하드웨어/런타임이 검출한 순간**이다. 이 검출 자체는 방어의 성공일 수도, 실패의 신호일 수도 있다.

- SIGABRT(canary·`fortify`·ASan abort)는 손상을 **감지해서 프로세스를 죽인** 것이다. 즉 완화가 제 일을 한 흔적이다. 이걸 "취약점 확인"으로 읽으면 방향이 반대다 — 프리미티브는 있으나 그 경로는 이미 관측·차단됐다는 뜻이다. `Inferred`
- null 역참조 SIGSEGV가 DoS에 그치는 근본 원인은 `mmap_min_addr`다. 0번 페이지를 사용자가 매핑할 수 없으니, null을 역참조해도 공격자가 그 메모리 내용을 통제할 수 없다. 프리미티브가 "통제 가능한 read/write"로 승격되지 못한다. `Source-confirmed`(리눅스 `mmap_min_addr` 동작)
- 반대로 "크래시가 안 났다 = 안전"도 거짓이다. OOB read가 힙 레드존이 없는 기본 빌드에서는 조용히 인접 메모리를 읽고 지나갈 수 있다 — 크래시 없이 정보가 새는 것이다. 그래서 ASan/HWASan 같은 **레드존을 심는 계측**이 필요하다. 크래시의 유무가 아니라 프리미티브의 존재가 판정 기준이다. `Inferred`

결국 영향은 크래시의 화려함이 아니라 **프리미티브 × 신뢰 경계 × 완화**의 곱이다. 이 곱 중 하나라도 0이면(경계를 안 넘거나, 완화가 프리미티브를 무력화하면) 영향은 붕괴한다.

## 버전 차이와 한계

익스플로잇 가능성은 정적이지 않다 — 같은 프리미티브가 완화 세대에 따라 다른 등급을 받는다. 그래서 RCA 보고서엔 반드시 **어느 완화가 켜진 환경에서의 판정인지**를 적는다.

- **PAC/BTI**(ARMv8.3/8.5, arm64): PC 제어를 시도하면 PAC 인증 실패로 SIGSEGV(비FPAC)/SIGILL(FPAC), BTI landing 위반으로 SIGILL이 뜬다. "PC 제어=RCE"가 이 완화 위에서는 곧바로 성립하지 않는다. `Reported`
- **MTE**(ARMv8.5, 일부 최신 Pixel): 힙 UAF/OOB를 태그 불일치로 확률적/결정적으로 잡아 많은 프리미티브를 DoS로 강등한다. 구체적 기본 활성 범위·기기 세대는 **버전 확인 필요**. `Reported`
- **GWP-ASan**: 표본 기반으로 프로덕션에서도 일부 힙 버그를 크래시로 표면화한다 — 트라이아지엔 도움, 하지만 표본이라 재현이 확률적이다. `Reported`
- **CFI·SELinux·seccomp**: 제어 흐름·도달 가능한 시스템콜·프로세스 권한을 줄여 "RCE 후 무엇을 할 수 있나"의 상한을 낮춘다.

정직한 산정의 예 — 로컬 제3자 앱이 Binder로 system_server를 죽이는 크래시(가용성만 영향, 로컬·저권한 필요)는 CVSS 3.1로 `CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H` = **5.5(Medium)**다. Critical이 아니다. (재계산: Exploitability≈1.83, Impact≈3.60, Base=roundup(5.43)=5.5.) 벡터와 점수가 맞지 않는 CVSS는 그 자체로 신뢰를 깎는다. `Inferred`

한계 — 이 글의 버킷은 **정황 판정**이지 증명이 아니다. "exploitable 후보"와 "실제 익스플로잇 가능"은 다르다. 후자는 프리미티브의 통제 가능성(오프셋·값·인접 객체 그루밍)을 실증해야 하고, 그건 안전 범위(자작 앱·공개 CVE)와 무기화 금지선 안에서만, 프리미티브 존재 확인까지로 제한한다.

## 정리

- 크래시는 증상이다. **증상 → 프리미티브 → 영향 상한 → 익스플로잇 버킷**을 절대 건너뛰지 않는다.
- fault addr≈0의 read AV는 `mmap_min_addr` 때문에 거의 DoS다. 통제된 주소·값의 write AV나 PC 제어만이 RCE 후보다.
- 영향은 프리미티브 × 신뢰 경계 × 완화의 곱이다. 자기 앱 자기 입력 DoS는 취약점이 아니고, 완화가 잡은 SIGABRT는 방어의 성공 흔적이다.
- CVSS를 쓸 거면 벡터와 점수가 재계산으로 맞아야 한다. DoS를 RCE로, 크래시를 취약점으로 부풀리지 않는다.

**점검 질문** — (1) fault addr 0x0의 SIGSEGV를 곧장 RCE라 부르면 안 되는 근본 이유는? (2) 같은 힙 오버플로가 기본 빌드에선 크래시 없이 지나가고 ASan 빌드에선 잡히는 이유는? (3) 로컬 앱이 system_server를 죽이는 크래시가 왜 Critical이 아니라 Medium 근처인가?

**참고** — Android Native crash 진단(source.android.com/docs/core/tests/debug/native-crash) · AddressSanitizer on Android(developer.android.com/ndk/guides/asan) · HWAddressSanitizer(source.android.com/docs/security/test/hwasan) · Android Severity Ratings(source.android.com/docs/security/overview/severity) · CVSS v3.1 Specification(first.org/cvss/v3-1)

*다음 글: [Java exception·logic bug RCA](/posts/android-rca-p3c08/).*
