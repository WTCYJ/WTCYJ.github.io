---
layout: post
title: "새 완화기법 평가"
date: 2027-01-14 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, MTE, PAC, Scudo, 완화기법]
excerpt: "새 완화기법을 평가할 때 가장 흔한 착각은 '완화 = 수정'이다. MTE·PAC·Scudo 대부분은 메모리 손상을 안전한 abort(=DoS)로 바꿀 뿐 버그 자체를 없애지 않는다. 게다가 PAC/MTE는 x86 에뮬레이터에선 관측 자체가 불가능하다."
---

퍼저가 크래시를 하나 뱉으면 연구는 절반쯤 온 것이다. 나머지 절반은 "이 버그가 실제로 얼마나 위험한가", 그리고 "요즘 나온 완화기법이 이걸 막는가"를 따지는 일이다. 그런데 이 두 번째 질문에서 사람들이 자주 미끄러진다. "MTE 켜면 되잖아", "PAC 있으면 ROP 안 되잖아" 같은 말은 절반만 맞다. 대부분의 완화는 버그를 **없애는** 게 아니라, 메모리 손상을 **탐지해서 프로세스를 죽이는**(controlled abort) 쪽이다. 즉 RCE를 DoS로 강등할 뿐이다.

이 글은 새로 나온(또는 새로 켠) Android 완화기법을 어떻게 **체계적으로 평가**하는지를 정리하고, 자작 최소 PoC로 Scudo의 탐지 경계를 실측한 기록이다. 무기화가 아니라 "이 완화가 이 버그 클래스를 어느 조건에서 잡는가"를 재는 방법론이 목표다.

> **한 줄 결론**: 완화기법 평가의 기준은 "버그를 없애느냐"가 아니라 "어느 조건에서 손상을 안전한 abort로 바꾸느냐(=RCE→DoS), 그리고 남는 잔여 표면은 무엇이냐"다. 그리고 PAC/MTE는 ARM 하드웨어 확장이라 x86 에뮬레이터에선 평가 자체가 성립하지 않는다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 완화기법을 (1) 겨냥하는 버그 클래스, (2) 성격(탐지·예방·난이도↑), (3) 관측 조건(하드웨어/버전/빌드 플래그)의 세 축으로 분류하고, 자작 PoC를 완화 켬/끔으로 대조해 **탐지 경계와 잔여 표면**을 재는 절차를 다룬다. 무기화된 우회는 다루지 않는다.

선수 지식이 셋 깔린다. 이 시리즈 1장의 연구 환경 이야기에서 짚었듯 **x86_64 이미지엔 PAC/MTE 표시가 아예 없고 arm64-v8a에서만 보인다** — 완화를 평가하려면 이미지/아키텍처 선택부터 맞아야 한다. Atlas C37(익스플로잇 완화 개론)이 각 완화가 전방엣지/후방엣지 중 어디를 지키는지를, Atlas C05(ARM64 예외 수준)가 PAC/BTI/MTE가 왜 ARM 확장에만 존재하는지를 설명한다. 그리고 앞선 4부의 퍼징 장(하네스·크래시 최소화)에서 나온 크래시가 이 평가의 입력이 된다.

전체 구조에서 이 장은 취약점 연구의 **뒷단**이다. 버그를 찾고(퍼징) → 근본 원인을 밝히고(sanitizer) → **완화가 이걸 막는지 판정하고**(이 장) → 보고서에 실제 영향과 조건을 적는다(다음 장). 완화 평가를 건너뛰면 DoS를 RCE로 부풀리거나, 반대로 하드웨어에서만 막히는 걸 "안전하다"고 오판한다.

## 핵심 개념 — 완화의 세 가지 성격

완화를 볼 때 제일 먼저 나눌 것은 **탐지(detect)** / **예방(prevent)** / **난이도↑(raise the bar)** 다. 탐지형은 손상이 일어난 뒤 잡아서 죽인다(→DoS). 예방형은 특정 원시(primitive)를 애초에 못 쓰게 한다. 난이도↑형은 절대적이지 않고 확률·비용을 올린다. 이 구분을 흐리면 "MTE는 UAF를 없앤다" 같은 과장이 나온다.

| 완화 | 계층 | 겨냥 버그 클래스 | 성격 | 관측 조건 |
|--|--|--|--|--|
| Scudo (기본 할당자) | 사용자공간 힙 | double-free, invalid-free, 일부 힙 손상 | 탐지 → abort | Android 11+ 기본, 아키텍처 무관 |
| GWP-ASan | 사용자공간 힙(샘플링) | 힙 OOB/UAF | 탐지(확률적) | 저오버헤드, 대상 앱 opt-in/기본 |
| MTE | 하드웨어(ARMv8.5) | 공간+시간(OOB·UAF) | 탐지 → abort | Pixel 8+급 하드웨어, sync/async |
| PAC | 하드웨어(ARMv8.3) | 반환주소/포인터 위조(ROP) | 예방/난이도↑ | arm64, 하드웨어 지원 |
| BTI | 하드웨어(ARMv8.5) | 간접분기 착지(JOP) | 예방 | arm64, 하드웨어+빌드 플래그 |
| CFI (LLVM) | 컴파일러(전방엣지) | 간접호출 변조 | 예방(계측 코드 한정) | 시스템 구성요소 빌드 |
| Shadow Call Stack | 컴파일러(후방엣지) | 반환주소 변조 | 예방 | arm64, x18 레지스터 예약 |

Scudo는 Android 11(API 30)부터 Bionic의 기본 네이티브 할당자이며 아키텍처와 무관하게 적용된다. `Source-confirmed` MTE는 Pixel 8급 이후 하드웨어에서 쓸 수 있고 sync/async 모드가 있다(정확한 지원 기기 목록은 하드웨어 확인 필요). `Reported` PAC는 ARMv8.3, BTI/MTE는 ARMv8.5 확장이라 x86 명령 집합엔 애초에 없다. `Source-confirmed`

여기서 흔한 착각 하나 — CFI가 "켜져 있다"고 해서 모든 함수가 보호되는 게 아니다. LLVM CFI는 **계측된 코드의 간접 호출**만 지킨다. 계측 안 된 vendor 라이브러리, 데이터 전용(data-only) 공격, 전방엣지가 아닌 경로는 그대로 남는다. `Reported` 완화 평가의 핵심은 이 "지키지 않는 나머지"를 명시하는 일이다.

> **[그림 1]** 완화 3분류(탐지/예방/난이도↑)와 각 완화가 겨냥하는 버그 클래스를 한 장에 정리한 화이트보드/노트 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 최소 PoC**와 **로컬 AVD**로만 진행한다. 제3자·실서비스 앱 공격, 완성된 우회 익스플로잇, 실기기 flashing은 없다. PoC는 원리 이해용 최소 개념 수준(malloc 하나 + free 두 번)이고, 이미 잘 알려진 힙 버그 클래스만 다룬다.

하드웨어 완화(MTE/PAC/BTI)는 Pixel 8+급 실기기가 필요해 이 장의 실습 범위 밖이며 **추론·문서 기반으로만** 다룬다(하드웨어 확인 필요). 실측으로 돌리는 건 아키텍처 무관하게 켜지는 **Scudo** 하나로 좁힌다 — 여기서 "탐지형 완화가 무엇을 잡고 무엇을 흘리는가"의 원형을 볼 수 있다.

## 실습 절차와 관측

### 가설
- **가설 A** — Scudo는 double-free를 청크 상태 검사로 **결정적으로** 탐지해 `SIGABRT`로 죽인다(=DoS化). `Inferred`
- **가설 B** — Scudo는 free된 메모리에 대한 **접근 자체는 계측하지 않으므로** UAF write는 조용히 통과한다. 즉 할당자 경계(malloc/free)에서만 검사한다. `Inferred`

### 절차
1. 아래 자작 PoC를 NDK clang으로 크로스컴파일한다.
2. AVD에 push하고 `d`(double-free)와 `u`(use-after-free write) 두 케이스를 각각 실행한다.
3. 종료 코드/시그널과 logcat의 Scudo 진단을 기록한다.
4. 두 케이스의 관측 차이를 "탐지 경계"로 정리한다.

```c
// mit_eval.c — 자작 최소 개념 PoC. "완화가 이 버그를 잡느냐"만 본다.
#include <stdlib.h>
#include <stdio.h>

int main(int argc, char **argv) {
    char *p = malloc(16);
    char mode = (argc > 1) ? argv[1][0] : 'u';
    if (mode == 'd') {          // 케이스 d: double-free
        free(p);
        free(p);                // Scudo: 청크 상태 검사 → SIGABRT
    } else {                    // 케이스 u: use-after-free (write)
        free(p);
        p[0] = 'X';             // 접근은 계측되지 않음 → 조용히 통과
        printf("no abort\n");   // Scudo는 '접근'을 검사하지 않는다
    }
    return 0;
}
```

```bash
# 호스트 태그: Windows는 windows-x86_64 + .cmd 래퍼
NDK=~/Android/Sdk/ndk/26.1.10909125
$NDK/toolchains/llvm/prebuilt/<host>/bin/aarch64-linux-android34-clang mit_eval.c -o mit_eval
adb push mit_eval /data/local/tmp/ && adb shell chmod 755 /data/local/tmp/mit_eval
adb shell /data/local/tmp/mit_eval d   # double-free → abort 관측
adb shell /data/local/tmp/mit_eval u   # UAF write → 조용히 통과
```

> **[그림 2]** 같은 바이너리를 `d`(Scudo abort/SIGABRT)와 `u`(no abort로 정상 종료) 두 케이스로 실행한 대조 캡처, 그리고 `d`에서 `adb logcat`에 찍힌 Scudo 진단 라인 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체 — 정확한 Scudo 문구는 버전마다 다르다):

```
$ adb shell /data/local/tmp/mit_eval d
F Scudo: invalid chunk state (double free) at 0x...    # 문구는 실측 교체
F libc  : Fatal signal 6 (SIGABRT), code -6 ...
1|:/ $                                                  # 비정상 종료(시그널 6)

$ adb shell /data/local/tmp/mit_eval u
no abort                                                # UAF write는 조용히 통과
:/ $                                                    # 정상 종료(0)
```

한 줄로 요약하면: **double-free는 잡히고(→DoS), UAF write는 흘렀다.** 둘 다 "메모리 안전 버그"지만 Scudo가 서 있는 위치(할당자 경계) 밖의 사건은 못 본다. 이 잔여 표면이 바로 MTE/HWASan 같은 **접근 단위 계측**이 노리는 자리다.

## Root Cause — 왜 이렇게 되는가

Scudo가 double-free만 확실히 잡는 이유는 그 성격이 **할당자 수준(allocator-level) 검사**이기 때문이다. free 시 청크 헤더의 상태·체크섬을 보므로, 이미 free된 청크를 또 free하면 상태 불일치로 abort한다. 반면 free된 버퍼에 대한 read/write는 malloc/free 경로를 지나지 않으니 검사 지점 자체가 없다. `Source-confirmed` ASan/HWASan/MTE는 **접근 단위(access-level)** 계측·태그 검사라 이 접근을 잡지만, Scudo는 저오버헤드 상용 할당자라 그 비용을 지지 않는다.

여기서 완화 평가의 가장 중요한 개념이 나온다 — **탐지 = RCE를 DoS로 강등**이지 버그 제거가 아니다. 같은 메모리 손상 버그를 CVSS로 나란히 놓으면 방향이 보인다(예시, 재계산 가능):

- 완화 없이 원격 미디어 파일로 코드 실행: `AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H` → **8.8**
- 탐지형 완화가 손상을 잡아 프로세스만 죽는 경우(가용성만 영향): `AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:N/A:H` → **6.5**

즉 좋은 완화는 8.8을 6.5로 내린다. 크지만 **0으로 만들지는 않는다.** 보고서에서 "완화로 unexploitable"이라고 단정하는 건 대개 과장이다.

MTE가 확률적인 것도 같은 결이다. 태그가 4비트(16값)라 위조 포인터가 우연히 태그를 맞출 확률이 대략 1/16이다 — 단발 탐지율이 높아도(≈15/16) async 모드에서 반복 시도로 밀어붙이면 언젠가 통과할 여지가 남는다. `Reported` 그래서 MTE는 "예방"이 아니라 "탐지 + 난이도↑"로 분류해야 정직하다. PAC도 서명 비트 수가 VA 크기 설정에 종속되고(대략 십수 비트, 정확한 수는 설정 확인 필요), 서명 오라클·재사용 가젯이 있으면 우회 여지가 생긴다. `Inferred`

내 퍼징 경험에 대보면 이 판정이 구체화된다. tinyobjloader의 `parseLine` 스택 OOB write(f[16])는 스택 카나리가 **함수 반환 시점에** 인접 손상을 잡지만, Shadow Call Stack은 반환주소만 지키므로 인접 지역변수 덮어쓰기는 SCS로는 안 잡힌다 — 같은 크래시라도 완화별로 판정이 갈린다. libsoup Range 정수 오버플로→assert DoS는 UBSan(`-fsanitize=integer`)이 개발 단계에서 잡지만 그건 디버깅 sanitizer라 프로덕션 완화가 아니다. **어떤 완화가 어느 시점에 무엇을 잡는지**를 버그마다 짚는 게 이 장의 일이다.

## 버전 차이와 한계

- 완화는 **Android 버전 + 하드웨어 + 빌드 플래그**의 곱집합으로 갈린다. Scudo는 11+ 소프트웨어 기본이라 폭넓지만, MTE/PAC/BTI는 특정 ARM 하드웨어에서만 존재해 실제 배포 단말의 대다수는 그 보호가 없다 — "완화의 patch-gap"이다. 신형 폰 기준의 평가 결과를 전체 fleet에 일반화하면 안 된다.
- **x86_64 에뮬레이터에선 PAC/MTE/BTI를 평가할 수 없다.** 1장에서 짚었듯 x86엔 이 명령이 없다. arm64-v8a AVD로 가야 하고, MTE는 추가로 에뮬/호스트 지원이 필요하다(하드웨어 확인 필요). Scudo·CFI·SCS처럼 아키텍처 무관하거나 컴파일러 기반인 것만 에뮬에서 부분 관측된다.
- 컴파일러 완화(CFI/SCS)는 **계측된 빌드에서만** 유효하다. 계측 안 된 vendor 바이너리는 그 밖이다. 평가할 땐 "그 바이너리가 실제로 그 플래그로 빌드됐는가"를 먼저 확인해야 한다(가정 금지).
- 완화 성격을 표기할 때 탐지/예방/난이도↑를 뭉뚱그리지 말 것. "MTE=UAF 해결"이 아니라 "MTE(sync)=UAF를 확률적으로 탐지해 abort"가 정확한 표현이다.

## 정리

- 완화 평가는 세 축 — 겨냥 버그 클래스 / 성격(탐지·예방·난이도↑) / 관측 조건(하드웨어·버전·빌드) — 으로 나눠 판정한다.
- 대부분의 완화는 RCE를 DoS로 강등한다(예: 8.8→6.5). "완화로 unexploitable"은 대개 과장이다.
- Scudo는 할당자 경계(double-free)만 잡고 접근(UAF read/write)은 흘린다 — 그 잔여 표면이 MTE/HWASan의 몫이다.
- PAC/MTE는 x86 에뮬에선 평가 불가, arm64+하드웨어에서만 관측된다.

**점검 질문** — (1) "탐지형 완화가 이 버그를 막는다"는 문장을 CVSS로 옮기면 무엇이 어떻게 바뀌는가? (2) Scudo가 double-free는 잡고 UAF write는 흘리는 이유는? (3) MTE를 "예방"이 아니라 "탐지+난이도↑"로 분류해야 하는 근거는?

**참고** — AOSP Scudo(source.android.com/docs/security/test/scudo) · AOSP Arm MTE(source.android.com/docs/security/test/memory-safety/arm-mte) · AOSP CFI(source.android.com/docs/security/test/cfi) · NDK GWP-ASan(developer.android.com/ndk/guides/gwp-asan) · Arm Architecture Reference Manual — PAC/BTI(developer.arm.com)

*다음 글: [보고·수정안·공개 타임라인](/posts/android-vulnresearch-p4c20/).*
