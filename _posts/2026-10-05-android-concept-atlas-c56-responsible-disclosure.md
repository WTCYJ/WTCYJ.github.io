---
layout: post
title: "Android Security Concept Atlas C56 | 가상 실습 보고서 — 책임 있는 공개(CVD), 발견을 세상에 안전하게 돌려주기"
date: 2026-10-05 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, CVD, ResponsibleDisclosure, ProjectZero, CVE, CNA, SecurityBulletin, BugBounty, ConceptAtlas, 학습기록]
excerpt: "Atlas의 56번째, 마지막 모듈입니다. 여기까지 배운 걸로 버그를 찾았다면 - 그다음은 어떻게 세상에 안전하게 돌려주느냐죠. 조율된 취약점 공개(CVD, '책임 있는 공개'의 현대 용어)는 벤더에 먼저 비공개로 알리고, 고칠 시간을 준 뒤, 수정이 나왔거나 데드라인이 지나면 공개하는 것입니다. 흔한 오해 셋: full disclosure는 블랙햇이 아니라 벤더가 무한정 뭉갤 때를 위한 정당한 트레이드오프고, Project Zero는 90일 데드라인에 14일 유예(30일은 패치 후 채택 창이라 별개)이며, 블로그에 쓴다고 CVE가 생기는 게 아니라 CNA가 배정합니다. Android 플랫폼 버그는 Google Bug Hunters로(공개 issuetracker 아님), 앱 버그는 HackerOne 같은 프로그램으로 - 그리고 좋은 리포트는 재현 가능한 최소 PoC와 정직한 영향입니다. Atlas를 닫는 캡스톤 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | 재현 환경 지문 수집, APK 빌드·서명·설치, Jekyll 빌드, 링크·이미지 감사 |
| 관측 결과 | 실행 환경·도구 버전·원시 출력을 보존하고 동일 명령을 재실행할 수 있는 증거 앱과 로그를 저장했다. |
| 검증 한계 | 실제 취약점 악용이나 타인 시스템 검사는 하지 않았다. 공개 연구와 소유한 가상환경의 안전한 관측만 포함한다. |

![C56 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-environment.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C56 — 책임 있는 공개(Coordinated Vulnerability Disclosure)
> **계층**: Tier 9 (취약점 연구) · **난이도**: 기초 · **선수 개념**: C51, C52, C55
> **성격**: 캡스톤 편 — 56모듈이 여기로 수렴.

Atlas의 마지막 모듈입니다. 지금까지 배운 걸로 버그를 찾았다면, 그다음은 **어떻게 세상에 안전하게 돌려주느냐** — 발견을 실제 제보로 잇는 것입니다.

한 문장으로: **CVD는 벤더에 먼저 비공개로 알리고 고칠 시간을 준 뒤 조율해 공개하는 것이고, 좋은 제보는 재현 가능한 최소 PoC와 정직한 영향이다.** 🟡 기초·캡스톤이라 원칙과 채널에 집중합니다.

## 배경 개념

- **CVD(Coordinated Vulnerability Disclosure)**: '책임 있는 공개'의 현대 용어. 비공개 제보 → 수정 시간 → 조율된 공개.
- **표준**: ISO/IEC 29147(공개) · 30111(처리) · CERT/CC 가이드.
- **CVE**: **CNA**(CVE Numbering Authority)가 배정. 데드라인/엠바고.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

Atlas의 **마지막 고리**입니다. C51(가진 게 크래시냐 익스플로잇 가능 취약점이냐)이 무엇을 가졌는지 말해주고, C52(CWE/CVE/불리틴)가 어휘를 주며, C56이 그걸 **행동**으로 — 유지자가 고칠 수 있는 것으로 바꿉니다.

## 질문 2 — 어떤 개념이며 무엇을 뜻하는가

- **CVD**: 벤더/유지자에 **먼저 비공개** 통지 → 합리적 수정 시간 → 수정 후(또는 합의 데드라인 후) 공개. '책임 있는 공개'는 옛 용어(공개를 "무책임"으로 함의해 CERT/CC·ISO가 CVD로 대체).
- **표준 분리**: **ISO/IEC 29147**=취약점 **공개**(벤더가 외부 제보 받고 권고문 발행 — 바깥 인터페이스) / **ISO/IEC 30111**=취약점 **처리**(내부 트리아지·수정·검증). CERT/CC "CVD 가이드"가 실무 참조.
- **모델 스펙트럼**: full disclosure(즉시 전면 공개) ↔ coordinated(비공개 후 수정 뒤 공개) ↔ 비공개/브로커 판매(책임 밖).
- **CVE**: **CNA**가 ID 배정(대형 벤더는 자기 제품 CNA, MITRE는 Top-Level Root 겸 최종수단 CNA 중 하나).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **데드라인이 책임성을 만든다**: 없으면 벤더가 무한정 뭉갤 수 있음 → 데드라인엔 "패치 여부와 무관하게 그날 공개" 규칙이 핵심.
- **신뢰하면 안 되는 것들**:
  - **"full disclosure는 블랙햇"** — 아닙니다. 벤더가 버그를 무한정 깔고 앉던 역사 때문에 생긴 **정당한 입장**(트레이드오프: 압박·방어자 인지 ↔ 패치 전 공격자 무장).
  - **"Project Zero는 90일 + 30일 유예"** — 유예는 **14일**(임박 패치 시). **30일은 별개** — 90일 **내 패치되면** 패치 후 30일(채택 창) 뒤 공개. **미패치면 90일에 공개**.
  - **"블로그에 쓰면 CVE가 생긴다"** — 아닙니다. **CNA가 배정**해야 인용 가능한 CVE. (Android 플랫폼 CVE는 Google이 배정.)
  - **"보안 버그를 공개 issuetracker에 올린다"** — **Google Bug Hunters**(비공개 접수)로. 공개 `issuetracker.google.com`은 기능 버그용(월드리더블) — 미공개 취약점을 올리면 CVD 위반.
  - **"safe harbor면 뭐든 테스트 가능"** — 범위 내 **good-faith** 테스트만 인가(CFAA류의 "무단 접근" 요소 제거). 범위 밖·제3자 시스템은 아님.
  - **"29147 = 30111"** — 공개(외부) vs 처리(내부)로 다릅니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 발견(C51로 무엇인지 판정, C52로 분류).
- **절차**: 채널 찾기(`security.txt`/`SECURITY.md`/프로그램 정책/PSIRT) → **범위 + safe harbor 확인** → 재현 가능 최소 리포트 → 조율 타임라인.
- **출력**: 수정 + (조율 후) 공개 + (해당 시) CVE. Android 플랫폼=Bug Hunters/ASR, 앱=벤더/HackerOne.

## 질문 5 — 실패하면 어떤 일이 벌어지나

- **나쁜 리포트가 유효한 발견을 죽인다**: 재현 불가/영향 모호. **"가끔 크래시"는 지고, "이 6바이트 → `parseLine`에서 OOB write, ASan 트레이스 첨부, 버전 X–Y"는 이깁니다.**
- **과대주장**: DoS를 RCE로 부풀리기 — 내 **정직 스코핑 교훈**(크래시 vs 익스플로잇 가능성 C51을 솔직히).
- **무단 테스트/데이터 유출**: 범위 밖 테스트나 실사용자 데이터 반출은 범죄가 될 수 있음(무단 접근). PoC는 **증명**만, 무기화·지속·서비스 훼손 금지.
- **잘못된 채널**: 공개 트래커에 취약점을 올려 0-day 노출.

## 질문 6 — Android 맥락에서 무엇이 다른가

- **채널**: 플랫폼/AOSP/커널 버그 → **Google Bug Hunters**(bughunters.google.com), **Android & Google Devices Security Reward Program**(구 ASR, 풀 익스플로잇 체인에 최고 보상).
- **불리틴**: 월간 **Android Security Bulletin**에 CVE+CWE+심각도(Critical/High/…)+영향 버전+패치 링크. **security_patch_level**: `-01`(프레임워크)·`-05`(+커널/벤더/SoC), `ro.build.version.security_patch`.
- **CNA**: AOSP-proper는 **Google**, 벤더/커널층은 **Qualcomm·MediaTek·(2024~)kernel.org** CNA가 배정.
- **패치 갭**(C29/C30/C36): AOSP 수정 → 불리틴 → **OEM → OTA → 기기**의 다단계 지연 = n-day가 미패치 기기에서 살아있는 이유.
- **앱 버그**: 앱 벤더/HackerOne(내 선호 — 정의된 범위·명시적 safe harbor·관리된 타임라인).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- 채널: `/.well-known/security.txt`, `SECURITY.md`, 프로그램 정책(범위·safe harbor·타임라인), 벤더 PSIRT.
- 테스트 전 **범위+safe harbor 확인**, 재현 최소 PoC 작성.
- **내 실제 제보**: wabt(GitHub 이슈/PR, 회귀테스트가 내 PoC 그대로 머지), GNOME libsoup(GitLab), VR tinyobjloader/IrfanView 리포트, HSPACE(버그바운티). 표준: ISO/IEC 29147/30111, CERT/CC CVD 가이드.

**주의**: 제보는 도구가 아니라 절차 — **어떤 대상이든 "채널·범위·safe harbor 확인 → 재현 최소 리포트 → 조율"** 로 실천 가능.

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C51(크래시 vs 취약점 vs 익스플로잇)**: 무엇을 가졌는지 정직히.
- **C52(CWE/CVE/불리틴)**: 분류 어휘.
- **C55(위협모델·영향)**: 리포트의 영향 진술.
- **C29/C30/C36(패치 갭)**: 불리틴이 곧 사용자 보호가 아닌 이유.
- **C02(인가)**: safe harbor가 그 인가.
- 이로써 Atlas 56모듈 전체가 여기 — **발견을 안전하게 돌려주기** — 로 수렴합니다.

## 직접 그릴 수 있는 호출 흐름

```
[ CVD: 발견 → 안전한 공개 ]

  발견(C51 판정 · C52 분류)
    │ 채널 찾기: security.txt / SECURITY.md / 프로그램 정책 / PSIRT
    │ 범위 + safe harbor 확인 (범위 밖·제3자 ✗)
    ▼
  비공개 제보 ─(재현 가능 최소 PoC + 정직한 영향)─▶ 벤더/유지자
    │ 수정 시간 (데드라인이 책임성: 미패치면 그날 공개)
    │   Project Zero: 90일 데드라인 + 14일 유예 · 90일내 패치→+30일(채택창)
    │   엠바고: 공유 라이브러리(libsoup류)는 다운스트림 동기화까지 보류
    ▼
  조율된 공개 + (CNA 배정 시) CVE
    Android: Bug Hunters/ASR → 월간 불리틴(CVE+심각도+패치레벨 -01/-05)
             → OEM → OTA → 기기 (패치 갭 C29/C30/C36)
    앱: 벤더 / HackerOne

  ✗ 무단 테스트 · 데이터 유출 · 과대주장 · 공개트래커에 0-day
```

## 오개념 판별 문제 5개

1. "full disclosure(즉시 전면 공개)는 곧 블랙햇 행위다."
2. "Project Zero 정책은 90일에 더해 30일의 유예를 준다."
3. "취약점을 블로그에 자세히 쓰면 그걸로 CVE가 생긴다."
4. "Android 플랫폼 보안 버그는 공개 issuetracker에 올리면 된다."
5. "버그바운티 safe harbor가 있으면 어떤 시스템이든 테스트해도 합법이다."

<details><summary>판정 기준(펼치기)</summary>

1. 아닙니다. 벤더가 무한정 뭉개던 역사 때문에 생긴 **정당한 입장**입니다(트레이드오프).
2. 유예는 **14일**(임박 패치 시). **30일**은 90일 내 패치된 버그의 **패치 후 채택 창**으로 별개. 미패치면 90일에 공개.
3. **CNA가 배정**해야 CVE입니다. 블로그 공개로 생기지 않습니다.
4. **Google Bug Hunters**(비공개)로. 공개 issuetracker는 기능 버그용 — 올리면 CVD 위반.
5. **범위 내 good-faith** 테스트만 인가됩니다. 범위 밖·제3자 시스템은 아닙니다.
</details>

## 서술형 문제 3개

1. CVD의 절차(비공개 제보 → 수정 시간 → 조율 공개)와 데드라인의 "패치 여부 무관 공개" 규칙이 왜 필요한지 서술하세요.
2. 데드라인(단일 벤더 카운트다운)과 엠바고(다자 동기화 보류)의 차이를, 공유 라이브러리(libsoup류) 예로 서술하세요.
3. 좋은 취약점 리포트의 요건(재현 가능 최소 PoC·정직한 영향·범위 준수)이 왜 유효한 발견을 살리는지, 과대주장/무단테스트의 위험과 함께 서술하세요.

## 소스·정적 검증 경로

- 임의 대상의 `security.txt`/`SECURITY.md`/프로그램 정책을 찾아 범위·safe harbor·타임라인을 정리하세요(테스트 전).
- Android Security Bulletin 한 편을 열어 CVE·CWE·심각도·패치레벨(-01/-05)·CNA를 판독하세요(C52).
- 내(또는 공개된) 실제 제보 하나를 CVD 절차 틀로 재서술하세요.

## 추가 심화 재현 절차

이 캡스톤을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 화면·리포트만** 붙입니다(공개 가능 범위에서).

1. **채널 실측**: 한 대상의 security.txt/정책·범위·safe harbor를.
2. **불리틴 판독**: 한 CVE의 CWE·심각도·패치레벨·CNA를.
3. **리포트 서술**: 내 wabt/libsoup/VR 제보를 CVD 틀로("가끔 크래시" vs 최소 PoC+영향).
4. **연결**: 패치 갭(C29/C30/C36)이 왜 "불리틴 = 보호 아님"인지.

각 단계는 화면·실제 리포트로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며 — Atlas를 닫으며

Atlas의 56번째, 마지막 모듈입니다. 여기까지 우리는 보안 원칙(C01~C03)에서 시작해 프로세스·UID·권한(C04·C09·C10), 패키징·서명(C06·C08), 런타임(C12~C16), IPC·프레임워크(C17~C21), 플랫폼 격리(C23~C25), 부팅·업데이트 체인(C27~C32), Native·커널(C33~C38), 하드웨어 보안(C39~C43), 앱 통제(C44~C50)를 거쳐 — 취약점 연구(C51~C56)로 왔습니다. 그 여정의 끝이 **책임 있는 공개**인 건 우연이 아닙니다: 이 모든 계층을 이해해 무언가를 발견하는 것은 절반이고, 나머지 절반은 그것을 세상에 **안전하게 돌려주는 일**이니까요.

CVD는 벤더에 먼저 비공개로 알리고, 고칠 시간을 준 뒤, 조율해 공개하는 것입니다. full disclosure는 블랙햇이 아니라 벤더가 무한정 뭉갤 때를 위한 정당한 트레이드오프고, Project Zero의 90일 데드라인엔 14일 유예가 붙으며(30일은 패치 후 채택 창으로 별개), CVE는 블로그가 아니라 CNA가 배정합니다. Android 플랫폼 버그는 Google Bug Hunters로(공개 트래커 아님), 앱 버그는 HackerOne 같은 프로그램으로 가고 — 좋은 리포트는 언제나 재현 가능한 최소 PoC와 정직한 영향입니다("가끔 크래시"는 지고, "6바이트 → `parseLine` OOB write, ASan 트레이스, 버전 X–Y"는 이깁니다). 그리고 불리틴에 CVE가 실려도 OEM→OTA 갭(C29/C30/C36) 때문에 그게 곧 사용자 보호는 아니라는 것 — 그 간극이 우리가 계속 찾고, 계속 제보하는 이유입니다.

이것으로 **Android Security Concept Atlas**를 닫습니다. 파편적 도구 사용법이 아니라 하나의 시스템 모델로, 부팅 첫 바이트부터 책임 있는 공개까지 — 56개 모듈이 한 지도가 되었습니다.
