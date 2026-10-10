---
layout: post
title: "apktool과 smali/baksmali — 편집은 왜 smali에서 하나"
date: 2026-10-20 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, apktool, smali, baksmali]
excerpt: "jadx의 Java는 읽기 전용 근사치라 되돌려 빌드할 수 없지만, apktool이 뽑는 smali(Dalvik 어셈블리)는 편집 후 재조립이 '의미상 무손실'로 된다 — 그래서 패치는 smali에서 한다. apktool d로 매니페스트까지 텍스트로 디코드되고, apktool b는 서명 안 된 APK를 dist/에 낸다(설치하려면 7장의 zipalign+재서명)."
---

정적으로 이해하는 것은 jadx(4장)로 하지만, 정확히 고치는 것은 smali로 한다. jadx의 Java는 근사·읽기전용이라 재빌드할 수 없는 반면, apktool이 뽑는 smali는 바이트코드 그대로라 편집 후 재조립이 신뢰된다. 이 글은 apktool로 디코드하고 smali를 읽고 최소 편집·재조립까지 하는 과정을, 그리고 그 재조립 산출물이 왜 서명이 없는지를 정리한 기록이다.

> **한 줄 결론**: smali 라운드트립은 바이트 동일은 아니지만 **의미상 무손실**이라 패치가 신뢰된다. `apktool d`는 매니페스트를 텍스트로 디코드하고, `apktool b`는 **서명 안 된** APK를 `dist/`에 낸다 — 설치하려면 [7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)의 zipalign+재서명이 필요하다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 apktool `d`/`b`와 smali/baksmali로 앱을 최소 편집하는 법을 다룬다. 선수 개념은 [jadx(4장)](/posts/android-lab-p1c04-jadx-static-analysis/)의 근사 Java 한계와 [ART/DEX(C13)](/posts/android-concept-atlas-c13-art-dex-oat-vdex/)의 Dalvik 바이트코드다. smali는 정적 이해와 **수정(7장)** 사이의 다리다.

## 핵심 개념 — apktool과 smali

- `apktool d app.apk -o work` → `smali/` 디렉터리 + **텍스트로 디코드된** `AndroidManifest.xml`·리소스 + `apktool.yml`(minSdk 등 메타). `apktool b <dir>` → **서명 안 된** APK를 `dist/`에. `Source-confirmed`
- 내부적으로 **baksmali**(dex→`.smali` 역어셈블)/**smali**(`.smali`→dex 어셈블). smali는 Dalvik 어셈블리: 지역 레지스터 `vN`, 파라미터 `pN`, `.method`/`.end method`, `invoke-virtual`/`invoke-static`, `const-string`, `if-*`, `move-result` 등. `Source-confirmed`
- **smali 라운드트립은 "의미상 무손실"**(명령·레지스터·라벨을 보존해 재조립이 신뢰됨) — 단 재빌드 DEX는 문자열풀 순서 등이 달라 **바이트 동일은 아니다**. 그래서 패치는 신뢰되지만 원본과의 바이트 비교는 무의미하고, 대신 smali diff로 비교한다. `Source-confirmed`

**신뢰 경계와 위협 모델.** apktool 편집은 **자작/교육용 앱**에서만(상용 앱 보호 우회 금지). 재조립 산출물은 서명이 없어 그대로는 설치되지 않는다.

> **[그림 1]** `apktool d`로 디코드된 트리(`smali/`·텍스트 `AndroidManifest.xml`·`apktool.yml`) — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱의 `isEnabled()` 같은 로직 게이트를 smali에서 `const/4 v0, 0x1`로 바꿔 동작 변화를 관측한다(교육용). 상용 앱 리패키징은 하지 않는다.

## 실습 절차와 관측

### 가설
`invoke`의 반환을 `move-result`로 받은 뒤 조건분기 전에 상수로 덮으면 자작 앱의 게이트가 우회된다. `Inferred`

### 절차
1. `apktool d`로 디코드.
2. jadx로 위치를 파악한 뒤 해당 `.smali` 메서드를 찾는다.
3. 최소 편집(한 줄).
4. `apktool b`로 재조립(unsigned).
5. 원본/수정 smali diff로 변경 범위를 문서화.

```bash
apktool d app.apk -o work
# work/smali/com/example/Gate.smali 편집
apktool b work                 # → work/dist/app.apk (unsigned)
diff -u orig/Gate.smali work/smali/com/example/Gate.smali
```

> **[그림 2]** 편집 전/후 smali diff(`invoke`+`move-result` → `const/4 v0, 0x1`) — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```smali
# 편집 전
    invoke-virtual {p0}, Lcom/example/Gate;->isEnabled()Z
    move-result v0
    if-eqz v0, :cond_0
# 편집 후 (자작 앱, 게이트 강제 true)
    const/4 v0, 0x1
    if-eqz v0, :cond_0
```

## Root Cause — 왜 이렇게 되는가

smali에서 패치하는 이유는 명확하다. jadx Java는 근사·읽기전용이라 재빌드가 불가하지만, smali는 바이트코드를 그대로 반영하므로 **의미상 무손실 재조립**이 된다(C13). 재빌드 DEX가 바이트 동일이 아닌 것은 재조립 과정에서 문자열풀 순서 등이 재배치되기 때문이라, 검증은 바이트가 아니라 smali diff로 한다.

## 방어와 회귀 검증

- (개발자) 클라이언트 로직 게이트를 신뢰하지 말 것 — smali 한 줄로 뒤집힌다. 인가는 서버에서(C02/C48). 수정 앱이 기능을 유지하고 의도한 게이트만 바뀌었는지 smali diff로 회귀.
- (연구자) 상용 앱 보호 우회는 범위 밖.

**흔한 실패와 처리.** `brut.androlib` 오류 → Java 버전 불일치(2.10+는 11+). 리소스 빌드 실패 → `apktool if`로 프레임워크 등록. 레지스터 오염 → `vN` 재사용 시 뒤 코드가 깨지니 여유 레지스터를 확인.

## 버전 차이와 한계

- apktool은 2.9.0+에서 aapt2 기본, **Java 요구: 2.9.x=Java 8 / 2.10.0+(2.11.x 포함)=Java 11+ 필수** — 버전 표기 필수.
- 데스크톱에서 디코드/재조립. 설치·실행 검증은 7장(재서명) 후 에뮬에서.

## 정리

- 이해는 jadx, 편집은 smali(의미상 무손실 재조립).
- `dist/` APK는 unsigned — 7장 필요.
- 검증은 바이트가 아니라 smali diff.

**점검 질문** — (1) `dist/`의 APK를 바로 설치 못 하는 이유는? (2) `vN`과 `pN`의 차이는? (3) smali 라운드트립이 "바이트 동일"이 아닌 이유는?

**참고** — [apktool.org](https://apktool.org) · [Apktool](https://github.com/iBotPeaches/Apktool) · [smali](https://github.com/google/smali) · [C13 ART/DEX](/posts/android-concept-atlas-c13-art-dex-oat-vdex/)

*다음 글: [Manifest 공격 표면 자동 매핑](/posts/android-lab-p1c06-manifest-attack-surface-mapping/).*
