---
layout: post
title: "MASVS 요구사항을 MASTG 검증 절차로: 커버리지 매트릭스로 감사 재현하기"
date: 2026-11-10 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, MASVS, MASTG, OWASP, 커버리지매트릭스]
excerpt: "MASVS는 '무엇을 검증할지'만, MASTG는 '어떻게'만 말한다. 흔한 착각 — MASVS v2엔 L1/L2 레벨이 없고 PRIVACY 카테고리가 새로 생겼다. 요구사항·테스트·증거를 한 줄로 잇지 못하면 감사는 재현되지 않는다."
---

자동 스캐너를 아무리 돌려도 "이 앱은 안전한가"라는 질문에는 답이 나오지 않는다. 스캐너는 "여기 이런 패턴이 있다"만 말할 뿐, 무엇을 검증했어야 하고 무엇을 빠뜨렸는지는 말하지 않는다. 그 빈칸을 채우는 게 표준이다. OWASP MASVS는 "무엇을 검증할지"의 요구사항 목록이고, MASTG는 "그걸 어떻게 검증하는지"의 절차 모음이다. 이 둘을 자작 앱 위에 겹쳐야 비로소 "요구사항 → 테스트 → 증거"가 한 줄로 이어진다.

이 글은 자작 취약앱 하나를 MASVS 카테고리로 매핑하고, 각 요구사항을 MASTG 절차로 변환해 에뮬레이터에서 실행한 뒤, 24·25장의 도구 산출물을 각 항목의 증적으로 묶은 기록이다. 목표는 하나 — 남이 다시 돌려도 같은 결론이 나오는 **재현 가능한 감사**를 만드는 것이다.

> **한 줄 결론**: MASVS는 요구사항(무엇)만, MASTG는 절차(어떻게)만 준다. 둘을 `요구사항 ID · 테스트 절차 · 증적 · 판정` 네 칸으로 이어야 감사가 재현되고, 스캐너의 초록불은 특정 MASTG 테스트에 매핑될 때만 비로소 "커버됐다"가 된다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 것은 세 단계다. (1) 자작 앱을 MASVS 7~8개 카테고리(STORAGE·CRYPTO·AUTH·NETWORK·PLATFORM·CODE·RESILIENCE, 그리고 v2에서 추가된 PRIVACY)로 매핑하고, (2) 각 요구사항을 MASTG의 구체적 테스트 절차로 변환해 에뮬레이터에서 실행하며, (3) 24장(MobSF 수동검증)과 25장(커스텀 규칙)의 산출물을 각 항목의 증적으로 연결해 한 장의 커버리지 매트릭스로 고정한다.

선수 지식은 이렇게 깔린다. 이 감사의 재료는 앞 두 장에서 이미 만들었다 — 24장에서 자동 스캔 결과를 수동으로 걸러 오탐·미탐을 분류했고, 25장에서 기성 스캐너가 놓친 프로젝트 고유 결함을 커스텀 규칙으로 잡았다. 개념 축으로는 Atlas C02(인증·인가), Atlas C33(TLS·Network Security Config·pinning), Atlas C29(Keystore·KeyMint)가 각각 AUTH·NETWORK·CRYPTO 카테고리의 검증 기준을 잡아 주고, Atlas C55(위협모델·영향산정)가 "이 항목이 왜 중요한가"의 무게를 매긴다.

전체 구조에서 이 장은 **흩어진 증거를 하나의 표로 수렴시키는 지점**이다. 24·25장이 개별 발견을 만들었다면, 여기서 그것들을 요구사항에 못 박고, 다음 27장에서 그 발견들을 회귀 테스트로 굳혀 "변종으로 되살아나지 않게" 고정한다.

## 핵심 개념 — MASVS(요구사항)와 MASTG(절차)의 분업

가장 자주 틀리는 지점은 둘을 뭉뚱그리는 것이다. MASVS는 "저장 데이터는 앱 샌드박스에 두고 안전하게 보호해야 한다" 같은 **요구사항**만 규정한다. 그걸 실제로 어떻게 확인하는지 — `run-as`로 shared_prefs를 열어 평문 여부를 보고, `allowBackup`을 확인하고 — 는 MASTG의 절차가 담당한다. `Source-confirmed`(OWASP MASVS·MASTG)

| 표준 | 역할 | 산출물의 성격 |
|--|--|--|
| MASVS | "무엇을 검증할지" 요구사항 | 카테고리별 통제 목록(추상) |
| MASTG | "어떻게 검증할지" 절차 | 테스트 케이스·데모·기법·도구(구체) |
| 커버리지 매트릭스(이 장) | 둘의 연결 + 증적 | 요구사항 ID → 테스트 → 증거 → 판정 |

MASVS v2(2023 재편)의 카테고리는 아래 8개다. 매니페스트에 적힌 7개는 **PRIVACY가 빠진 구식 나열**이다. 이 착시부터 걷어내야 한다. `Source-confirmed`

- **MASVS-STORAGE** — 민감 데이터 저장·노출
- **MASVS-CRYPTO** — 암호 구현의 적절성
- **MASVS-AUTH** — 인증·인가·세션
- **MASVS-NETWORK** — 통신 보안(TLS·pinning)
- **MASVS-PLATFORM** — IPC·WebView·플랫폼 상호작용
- **MASVS-CODE** — 코드 품질·빌드 설정·의존성
- **MASVS-RESILIENCE** — 리버싱·변조 저항(방어심층)
- **MASVS-PRIVACY** — 프라이버시(v2 신규) `Source-confirmed`

여기서 두 번째 함정 — **RESILIENCE는 보안 경계가 아니라 방어심층(defense-in-depth)이다.** 루팅 탐지나 안티디버깅이 없다고 STORAGE·CRYPTO 결함이 상쇄되지 않는다. MASVS도 이를 명시한다. 리버싱 저항을 "보안 통제"로 착각하면 매트릭스의 심각도 산정이 통째로 뒤틀린다. `Reported`(원문 재확인 필요)

> **[그림 1]** MASVS v2 8개 카테고리를 자작 앱 화면에 매핑한 초안 시트 — 카테고리별 대표 요구사항과 대응 MASTG 테스트 ID를 적어 넣은 표 캡처 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **자작 취약앱과 로컬 에뮬레이터(AVD)로만** 진행한다. 상용 앱·제3자 앱에 이 체크리스트를 들이대지 않는다 — MASVS/MASTG를 남의 프로덕션 앱에 돌리는 건 감사가 아니라 무단 점검이다. 대상 앱은 디버그 빌드(`android:debuggable="true"`)로 두어 `run-as`가 열리게 하고, 계측용 이미지는 1장에서 만든 `google_apis` userdebug AVD를 쓴다. NETWORK 항목은 11장의 mitmproxy 랩을, STORAGE/PLATFORM은 6장 매니페스트·smali를 재사용한다.

MASTG 절차 중 일부는 실기기·하드웨어 신뢰뿌리를 전제한다(예: StrongBox 키 검증). 에뮬레이터엔 TEE가 없으므로 그런 항목은 "환경상 부분 검증"으로 판정하고 매트릭스에 명시한다. 관측 못 한 것을 "통과"로 적지 않는 게 재현성의 핵심이다.

## 실습 절차와 관측

### 가설

- **가설 A** — 스캐너(24·25장)의 초록불 자체는 커버리지가 아니다. 각 결과를 특정 MASTG 테스트에 매핑해야만 해당 요구사항이 "검증됨"으로 바뀐다. `Inferred`
- **가설 B** — 자작 앱은 STORAGE(평문 shared_prefs)·NETWORK(cleartext 허용)·CRYPTO(ECB/하드코딩 키)에서 실패하고, 그 실패가 매트릭스에서 요구사항 ID로 정확히 지목된다. `Inferred`
- **가설 C** — RESILIENCE 항목은 에뮬레이터에서 부분 검증에 그쳐 "N/A(환경)"로 남는다. `Inferred`

### 절차

1. MASVS 카테고리별로 대상 앱에 해당하는 요구사항을 골라 매트릭스 행을 만든다.
2. 각 행에 대응하는 MASTG 절차를 적고, 카테고리 대표 검증을 에뮬레이터에서 실행한다.
3. 실행 결과와 24·25장 산출물(jadx 스니펫·Semgrep 매치·MobSF 항목)을 증적으로 링크한다.
4. 각 행을 `통과 / 실패 / N/A(환경)`로 판정하고 근거 라벨을 붙인다.

```bash
# STORAGE — 앱 전용 저장소를 열어 평문 민감데이터 여부 확인 (디버그 빌드 한정)
adb shell run-as com.wtcy.vulnbank cat shared_prefs/creds.xml   # 평문 토큰이면 STORAGE 실패
adb shell run-as com.wtcy.vulnbank ls -l databases/             # 파일 모드·백업 대상 확인
aapt2 dump xmltree app-debug.apk --file AndroidManifest.xml | grep -i allowBackup  # allowBackup=true면 감점 (badging은 이 플래그를 안 뱉는다)

# NETWORK — cleartext 허용 여부(NSC) 확인, 실측은 11장 mitmproxy로
#   NSC는 APK 내부 리소스라 run-as의 데이터 디렉터리 경로로는 못 읽는다 — APK를 디코드해 정적 확인
aapt2 dump xmltree app-debug.apk --file res/xml/network_security_config.xml   # 이 파일 자체가 없으면 NSC 부재
# 또는: apktool d app-debug.apk 후 res/xml/network_security_config.xml 확인
# cleartextTrafficPermitted="true" 또는 NSC 부재(API<28 기본 허용) → NETWORK 실패 후보

# PLATFORM — exported 컴포넌트 표면 (6장 재사용)
aapt2 dump xmltree app-debug.apk --file AndroidManifest.xml | grep -i -A2 "exported"

# CRYPTO — 약한 모드/하드코딩 키는 정적으로 (24·25장 산출물 재사용)
#   jadx 디컴파일 결과에서 "AES/ECB" · SecretKeySpec 리터럴 매치를 증적으로 링크
```

> **[그림 2]** 위 절차 중 하나(예: `run-as ... cat shared_prefs`)를 에뮬레이터에서 실행해 평문 자격증명이 그대로 노출되는 출력과, 같은 발견이 24장 MobSF 항목·25장 Semgrep 매치로도 잡힌 화면을 나란히 둔 대조 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력(교체)` — 네 실제 실행으로 교체:

```
$ adb shell run-as com.wtcy.vulnbank cat shared_prefs/creds.xml
<map><string name="auth_token">eyJhbGciOi...</string>
     <string name="pin">1234</string></map>
$ aapt2 dump xmltree app-debug.apk --file AndroidManifest.xml | grep -i allowBackup
      A: android:allowBackup(0x0101000e)=true
```

이걸 매트릭스 한 행으로 옮기면 아래처럼 된다. **이 표 하나가 이 장의 산출물이다** — 요구사항에서 판정까지 한 줄로 읽힌다.

| MASVS 카테고리 | 요구사항(요지) | MASTG 절차(요지) | 증적 | 판정 |
|--|--|--|--|--|
| STORAGE | 민감데이터 평문 저장 금지 | shared_prefs/DB 덤프·백업 플래그 | 위 `creds.xml` 평문 + 24장 MobSF #S3 | **실패** |
| NETWORK | 평문 통신 금지·TLS 강제 | NSC 검사 + mitmproxy 가로채기(11장) | cleartext 허용 + 프록시 캡처 | **실패** |
| CRYPTO | 안전한 모드·키 관리 | 정적 grep(모드/키) | 25장 Semgrep `aes-ecb` 매치 | **실패** |
| PLATFORM | 불필요 exported 최소화 | 매니페스트 exported 열거(6장) | aapt2 exported 목록 | 조건부 |
| RESILIENCE | 리버싱·변조 저항 | 루팅탐지·안티디버깅 관측 | 에뮬레이터 TEE 부재 | **N/A(환경)** |

## Root Cause — 왜 이렇게 되는가

커버리지 매트릭스가 필요한 근본 이유는 **"스캐너 결과"와 "요구사항 충족"이 다른 층위이기 때문**이다. 스캐너는 코드/바이너리에서 패턴을 찾는 증거 생산기일 뿐, 그 증거가 어떤 요구사항을 검증하는지는 스스로 모른다. 24장에서 오탐/미탐을 걸러 봤듯, 초록불이 "도달 불가 코드라서 초록"일 수도 있고 "런타임 전용 결함이라 애초에 못 본 것"일 수도 있다. 그래서 초록불을 그대로 "STORAGE 통과"로 옮기면 미검증을 검증으로 위장하게 된다. `Inferred`

MASVS와 MASTG를 굳이 두 문서로 나눈 이유도 같다. 요구사항(무엇)은 앱 종류가 달라도 안정적이지만, 검증 절차(어떻게)는 OS 버전·API·도구에 따라 계속 바뀐다. 둘을 붙여 두면 절차가 낡을 때마다 요구사항까지 흔들린다. 매트릭스는 이 분업을 그대로 물려받아, 요구사항 칸은 고정하고 절차·증적 칸만 갱신하도록 만든 구조다. `Source-confirmed`

RESILIENCE가 매트릭스에서 자주 "N/A(환경)"로 남는 것도 버그가 아니다. 이 카테고리는 실기기의 신뢰뿌리·루트 탐지 우회 저항을 전제하는데, 에뮬레이터는 애초에 그 무대를 제공하지 않는다(1장에서 정리한 대로 TEE·StrongBox 미탑재). 관측 불가를 정직하게 "N/A"로 남기는 것이 "통과"로 적는 것보다 재현성에 이롭다. `Inferred`

## 버전 차이와 한계

- **MASVS v1 → v2 재편.** 구버전은 V1~V8 번호 카테고리(예: V2 Data Storage)였고, v2에서 `MASVS-STORAGE`처럼 이름 기반으로 바뀌며 PRIVACY가 추가됐다. 오래된 체크리스트를 그대로 쓰면 카테고리 매핑이 어긋난다. 매트릭스에는 반드시 **MASVS 버전을 명시**한다. `Source-confirmed`
- **검증 레벨(L1/L2/R)의 소멸.** v1에 있던 L1/L2 검증 레벨과 R(resilience) 표기는 v2에서 제거되고 테스트 프로파일 개념으로 옮겨졌다 — "우리 앱은 MASVS L2"라는 표현은 이제 낡았다. `Reported`(원문 재확인 필요)
- **MASTG의 원자적(atomic) 재편.** 최근 MASTG는 약점(MASWE) → 테스트(MASTG-TEST) → 데모(MASTG-DEMO) → 기법(MASTG-TECH) → 도구(MASTG-TOOL)로 잘게 나뉘는 방향으로 개편됐다. 증적을 링크할 때 구 `MSTG-STORAGE-1` 식 ID와 신 ID가 섞이지 않게 한다. 정확한 ID 체계는 원문 재확인 필요. `Reported`(원문 재확인 필요)
- **에뮬레이터 한계.** STORAGE·NETWORK·PLATFORM·CODE는 AVD로 충분히 검증되지만, RESILIENCE와 Keystore 하드웨어 부분(C29)은 부분 검증에 그친다. 이 한계는 매트릭스 판정 칸에 그대로 적는다.

## 정리

- MASVS는 요구사항, MASTG는 절차. 둘을 잇는 `요구사항 → 테스트 → 증적 → 판정` 한 줄이 재현 가능한 감사의 최소 단위다.
- 스캐너 초록불은 특정 MASTG 테스트에 매핑될 때만 "커버됨"이다 — 매핑 없는 초록불은 미검증이다.
- MASVS v2엔 L1/L2 레벨이 없고 PRIVACY 카테고리가 추가됐다. 버전을 매트릭스에 명시하지 않으면 감사가 재현되지 않는다.
- RESILIENCE는 방어심층이지 보안 경계가 아니며, 에뮬레이터에선 대개 "N/A(환경)"로 남긴다 — 관측 못 한 것을 통과로 적지 않는다.

**점검 질문** — (1) MobSF의 "STORAGE 이상 없음" 결과 하나만으로 MASVS-STORAGE를 "통과"로 적을 수 있는가, 없다면 무엇이 더 필요한가? (2) MASVS v2에서 사라진 개념과 새로 추가된 카테고리는 각각 무엇인가? (3) RESILIENCE 항목이 에뮬레이터에서 "N/A(환경)"가 되는 이유는?

**참고** — OWASP MASVS(mas.owasp.org/MASVS) · OWASP MASTG(mas.owasp.org/MASTG) · OWASP MAS Checklist(mas.owasp.org/checklists)

*다음 글: [방어 회귀 테스트 설계: 패치된 결함이 변종으로 되살아나지 않게 고정](/posts/android-lab-p1c27/).*
