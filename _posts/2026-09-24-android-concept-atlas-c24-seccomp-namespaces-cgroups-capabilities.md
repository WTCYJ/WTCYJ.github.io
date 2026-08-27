---
layout: post
title: "Android Security Concept Atlas C24 - seccomp·namespaces·cgroups·capabilities, 샌드박스를 겹겹이 두르는 층"
date: 2026-09-24 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, seccomp, capabilities, namespaces, cgroups, AppFreezer, DefenseInDepth, ConceptAtlas, 학습기록]
excerpt: "앱 샌드박스의 1차 경계는 UID(C09)와 SELinux(C23)지만, 그 위에 리눅스 컨테이너 프리미티브가 겹겹이 얹힙니다: 앱 프로세스는 capability를 하나도 안 가지고(root의 힘을 ~40비트로 쪼갠 것 중 0개), seccomp-bpf가 시스템 콜을 allowlist로 걸러 커널 공격 표면을 줄이며(C36), mount 네임스페이스가 저장소 뷰를 가릅니다. 중요한 뉘앙스 - caps를 비우는 건 setuid 같은 '합법적' 권한 상승만 막지, 커널 메모리 손상 익스플로잇(cred 구조체 덮어쓰기)은 못 막습니다. 그래서 이건 대체가 아니라 심층방어 층이죠. seccomp는 포인터를 못 읽어 경로가 아니라 시스템 콜 번호로만 거르고, cgroups는 보안이 아니라 자원·앱 프리저용입니다. Tier 4 플랫폼 격리 모듈입니다."
---

> **Concept Atlas 모듈**: C24 — seccomp·namespaces·cgroups·capabilities
> **계층**: Tier 4 (플랫폼 격리) · **난이도**: 고급 · **선수 개념**: C04(시스템콜), C09(UID), C23(SELinux)
> **성격**: 미학습 편.

C09에서 UID DAC를, C23에서 SELinux MAC를 봤습니다. 이 편은 그 **1차 경계 위에 겹겹이 얹히는 리눅스 컨테이너 프리미티브** — 앱 샌드박스를 완성하는 심층방어 층입니다.

한 문장으로: **앱 샌드박스는 UID+SELinux(1차) 위에 capability 비움·seccomp 필터·mount 네임스페이스를 겹친 것이고, cgroups는 보안이 아니라 자원 관리다.** 🔴이지만 핵심에 집중합니다.

## 배경 개념

- **capabilities**: root의 힘을 ~40비트로 쪼갬. 앱은 **0개**.
- **seccomp-bpf**: 시스템 콜 allowlist 필터(번호+인자 값, **포인터맹**).
- **mount namespace**: 저장소 뷰 격리. (PID/NET ns는 앱에 거의 안 씀.)
- **cgroups**: 자원 제어·앱 프리저. **보안 경계 아님**.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**UID(C09)+SELinux(C23) 위의 심층방어 층**입니다. 런타임 앱 샌드박스 = 고유 UID + SELinux 도메인(untrusted_app) + seccomp allowlist + **caps 0** + 저장소용 mount ns. 어느 하나가 "샌드박스"가 아니라 **겹쳐서** 작동합니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **capabilities**: 리눅스가 root의 전능을 discrete 비트로 쪼갬(`CAP_SYS_ADMIN`=만능 catch-all, `CAP_NET_RAW`=raw/packet 소켓, `CAP_SYS_PTRACE`, `CAP_DAC_OVERRIDE`, `CAP_NET_BIND_SERVICE`<1024포트, `CAP_NET_ADMIN`). 스레드마다 **5개 세트**(permitted/effective/inheritable/ambient/bounding, **per-thread**), bounding=천장(빠지면 exec로도 재획득 불가). zygote specialization(C12)에서 자식의 bounding을 비워 앱은 **모든 세트 0**. 데몬은 최소권한으로 **소수 named caps**(init `.rc`).
- **seccomp-bpf**: `prctl(PR_SET_SECCOMP)`/`seccomp()`(`no_new_privs` 필요)로 BPF 설치, 커널이 **모든 시스템 콜 진입**에서 실행. 필터는 번호+arch+6인자를 **값으로만**(포인터 역참조 불가) 보고 ALLOW/ERRNO/TRAP/KILL/TRACE 반환. Android 앱 필터는 zygote가 설치(**A8.0**), ABI별 bionic allowlist(~250개 허용, 나머지 차단 → C36 커널 표면 축소).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **심층방어이지 1차 경계가 아님**: 앱↔앱 1차 경계는 여전히 UID+SELinux. 이 층들은 그 위의 추가 껍질.
- **seccomp는 한 방향 래칫**: 추가만 가능(재허용 불가), 프로세스 수명 동안 제거 불가 → zygote가 base 필터를 깔면 앱이 못 푼다(C25는 그 위에 더 조임).
- **신뢰하면 안 되는 것들**:
  - **"caps를 비우면 커널 익스플로잇도 못 한다"** — 아닙니다. caps 비움은 **합법적** 상승 경로(setuid-root execve·capset)만 막습니다. **커널 메모리 손상 익스플로잇은 cred 구조체를 직접 덮어써**(`commit_creds(prepare_kernel_cred(0))`) root를 얻으니, caps와 무관 — 그래서 SELinux(C23)·seccomp 표면축소(C36)가 함께 필요.
  - **"seccomp가 경로/버퍼 내용을 검사"** — **포인터맹**입니다. 시스템 콜 번호와 스칼라 인자로만 거릅니다(그래서 "어느 파일"은 SELinux가).
  - **"namespace가 앱 격리의 주력"** — Android는 앱에 **mount ns만**(저장소 뷰) 씁니다. PID/NET/UTS ns는 거의 안 쓰고(공유), 격리는 UID+SELinux+netd가.
  - **"cgroups가 보안 경계"** — 자원(CPU/메모리/IO)·**앱 프리저**(캐시 앱 동결)·배터리용이지 보안 경계 아님.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: zygote가 spawn 시 bounding 세트 비움 + ABI별 seccomp allowlist 설치(앱 코드 실행 전).
- **출력**: 앱 프로세스 = caps 0 + `Seccomp: 2`(필터 모드) + 자기 mount ns + **공유** net/pid ns. seccomp는 이후 못 푼다.

## 질문 5 — 실패하면 어떤 취약점으로/무엇을 각 층이 막나

- **caps 비움**: setuid·capset 같은 합법 상승 차단(커널 버그는 못 막음).
- **seccomp**: 드문/레거시 시스템 콜과 그를 통한 드라이버 도달을 차단 → **C36 커널 공격 표면 축소**(인가가 아니라 표면 감소).
- **mount ns**: 보이는 파일 자체를 제한(저장소 뷰).
- **cgroups**: 보안이 아님(자원·프리저).
- **층의 효과**: 한 층을 뚫어도 나머지가 남아 — 한 버그가 전면 장악이 드문 이유. 단 **커널 메모리 손상은 이 유저스페이스 층들을 우회**하므로 커널 자체 방어(C37·C36)가 별개로 중요.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **seccomp 앱 필터**: A8.0(Oreo), ABI별 bionic 생성.
- **앱 프리저**(cgroup freezer + binder freezer): A11 도입·A12 기본.
- **저장소**: pre-A11은 `/mnt/runtime/{default,read,write}` 3-뷰(sdcardfs), **A11+는 FUSE+MediaProvider·scoped storage**로 이동.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `cat /proc/<pid>/status | grep -E 'Cap|Seccomp'`(앱: `CapEff`…=`0000000000000000`, `Seccomp: 2`), `/proc/<pid>/ns/{mnt,net,pid}`(두 앱 비교: mnt 다름/net·pid 같음), `/proc/<pid>/cgroup`, `getcap`/`capsh --decode`.
- **소스**: AOSP `bionic/libc/seccomp/`(allowlist), `frameworks/base/core/jni/com_android_internal_os_Zygote.cpp`(`DropCapabilitiesBoundingSet`·`SetUpSeccompFilter`), `capabilities(7)`/`seccomp(2)`.

**주의**: 이 프리미티브들은 아키텍처 무관 → **에뮬레이터로 `/proc/pid/status`·`ns/`·`cgroup` 실측 가능**(단 seccomp 번호는 ABI별).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C04(시스템콜)**: seccomp가 그 시스템 콜 경로를 거름.
- **C09(UID)·C23(SELinux)**: 1차 경계 — 이 층들은 그 위에.
- **C12(zygote)**: caps 비움·seccomp를 specialization에서 적용.
- **C36(커널 표면)**: seccomp allowlist가 그 표면을 줄임.
- **C25(isolatedProcess)**: 같은 프리미티브를 더 조인 것 — 바로 다음.
- 다음은 이 층들을 극단으로 조인 **C25(isolatedProcess·app zygote)**로.

## 직접 그릴 수 있는 호출 흐름

```
[ 앱 샌드박스 = 겹쳐진 층 ]

  1차 경계:  UID DAC (C09)  +  SELinux MAC (C23)
  심층방어 층(zygote가 specialization에서 적용, C12):
     ├ capabilities: bounding 세트 비움 → 앱 caps 0 (per-thread)
     │     └ setuid/capset 합법 상승 차단 (커널 메모리손상은 못 막음)
     ├ seccomp-bpf: 시스템콜 allowlist(A8.0, 포인터맹, 번호+인자)
     │     └ 드문 시스템콜/드라이버 도달 차단 (C36 표면 축소)
     └ mount ns: 저장소 뷰 격리 (net/pid ns는 공유)

  cgroups: CPU/메모리/앱 프리저(동결)  ← 자원/배터리, 보안 아님

  관찰: /proc/pid/status → CapEff=0, Seccomp:2 · ns/mnt 다름, ns/net 같음
```

## 오개념 판별 문제 5개

1. "앱 프로세스는 capability가 전부 비어 있으니, 커널 익스플로잇으로도 root를 못 얻는다."
2. "seccomp 필터는 열리는 파일 경로나 버퍼 내용을 보고 시스템 콜을 막을 수 있다."
3. "Android는 컨테이너처럼 앱마다 PID·NET 네임스페이스를 따로 준다."
4. "cgroups는 앱을 서로 격리하는 보안 경계다."
5. "capability의 5개 세트는 프로세스 단위 속성이다."

<details><summary>판정 기준(펼치기)</summary>

1. caps 비움은 **합법적** 상승(setuid/capset)만 막습니다. 커널 메모리 손상은 cred를 직접 덮어써 root를 얻으니 무관 — SELinux/표면축소가 함께 필요.
2. seccomp는 **포인터맹**입니다. 시스템 콜 번호와 스칼라 인자로만. "어느 파일"은 SELinux.
3. Android는 앱에 **mount ns만** 씁니다(저장소). PID/NET은 공유, 격리는 UID+SELinux.
4. cgroups는 **자원·앱 프리저**용이지 보안 경계가 아닙니다.
5. **per-thread**입니다(5세트 전부, 커널 2.6.25+).
</details>

## 서술형 문제 3개

1. "앱 샌드박스 = UID+SELinux(1차) + seccomp+caps비움+mount ns(심층방어)"를, 각 층이 무엇을 막는지와 함께 서술하세요.
2. caps를 비우는 것이 왜 커널 메모리 손상 익스플로잇을 막지 못하는지(cred 덮어쓰기), 그래서 왜 SELinux·seccomp 표면축소가 함께 필요한지 서술하세요.
3. seccomp가 "포인터맹"이라 무엇을 못 하고(경로/버퍼), 그래서 왜 SELinux와 짝을 이루는지 서술하세요.

## 소스 탐색 과제

- 임의 앱의 `/proc/<pid>/status`에서 `CapEff`(=0)과 `Seccomp`(=2)를 확인하세요.
- 두 앱의 `/proc/<pid>/ns/mnt`(다름)와 `ns/net`(같음)을 대조해 mount ns만 분리됨을 확인하세요.
- 시스템 데몬 하나의 caps(`getcap`/`status`)를 앱(0)과 비교해 최소권한을 관찰하세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **caps/seccomp 실측**: 앱의 `CapEff=0`·`Seccomp:2`를.
2. **ns 실측**: 두 앱의 mnt 다름/net 같음을.
3. **층 서술**: 각 층이 막는 것과, 커널 익스플로잇이 왜 이를 우회하는지.
4. **연결**: seccomp allowlist가 C36 커널 표면을 어떻게 줄이는지.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

앱 샌드박스의 1차 경계는 UID(C09)·SELinux(C23)지만, 그 위에 리눅스 컨테이너 프리미티브가 겹겹이 얹힙니다: 앱은 capability를 하나도 안 가지고, seccomp-bpf가 시스템 콜을 allowlist로 걸러 커널 공격 표면을 줄이며(C36), mount 네임스페이스가 저장소 뷰를 가립니다. 중요한 건 — caps 비움은 setuid 같은 **합법적** 상승만 막지 커널 메모리 손상 익스플로잇(cred 덮어쓰기)은 못 막고, seccomp는 포인터맹이라 경로가 아니라 시스템 콜 번호로만 거르며, cgroups는 보안이 아니라 자원·앱 프리저용이라는 것입니다. 그래서 이건 대체가 아니라 **심층방어 층**입니다. 다음은 이 프리미티브들을 극단으로 조여 최강 인앱 샌드박스를 만드는 **C25(isolatedProcess·app zygote)**로 이어집니다.
