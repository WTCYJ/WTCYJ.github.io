---
layout: post
title: "[Android 앱 보안 S18] 취약 앱 종합 모의진단"
date: 2026-09-03 11:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 모의진단, 펜테스트, CVSS, InsecureShop, 최종보고서, 학습기록]
excerpt: "S01부터 하나씩 판 InsecureShop의 결함들을 한 편으로 모았습니다. 공격 표면, 발견 12건, 심각도와 참고 CVSS, 재현 위치, 그리고 수정과 회귀 검증까지 — 하나의 모의진단 보고서로 정리했습니다. 마무리로, 직접 만든 공격 앱이 이 앱의 자격증명을 실제로 뽑아내는 걸 한 화면에 담았습니다."
---

> 이 시리즈의 마지막 편입니다. S02부터 S17까지 InsecureShop에서 찾은 것을 한 편의 모의진단 보고서로 묶고, 마지막으로 공격 앱이 자격증명을 실제로 털어 종합 증거를 남깁니다.

지금까지 한 챕터에 한 가지씩 팠습니다. 이번 편은 그걸 공격자 관점의 보고서 하나로 모읍니다. 개별 취약점보다 중요한 건, 이것들이 겹쳐 만드는 그림입니다 — 앱을 설치한 다른 앱 하나가 자격증명을 통째로 가져가고, 네트워크에 앉은 누군가가 트래픽을 읽고 바꾸며, 웹 링크 한 줄이 앱 안에서 임의 페이지를 띄웁니다.

---

## 실습 목표

- InsecureShop의 공격 표면과 발견 사항을 종합한다.
- 발견별 심각도와 참고 CVSS, 재현 위치를 정리한다.
- 대표 수정과 회귀 검증 방향을 제시한다.
- 공격 앱으로 자격증명 탈취를 실제로 재현해 종합 증거로 남긴다.

---

## 대상과 범위

- 대상 앱: InsecureShop `com.insecureshop` v1.0, SHA-256 `a83298…d1bd`(S02)
- 환경: `aas-api33` 에뮬레이터(S01), 내가 소유한 교육용 앱과 직접 만든 공격/데모 앱만 사용
- 범위: 저장소·컴포넌트·IPC·WebView·네트워크·인증·권한·동적 분석. 실서비스·타 계정 제외

---

## 공격 표면 (S03 요약)

- 앱 플래그: `debuggable=true`, `allowBackup=true`, `usesCleartextTraffic=true`, 디버그 키 서명
- exported: 액티비티(AboutUs·Result 등)·ContentProvider(자격증명)·Service, intent-filter로 암묵 exported(WebView·WebView2·Chooser)
- 진입점: 딥링크 `insecureshop://`, 커스텀 액션, extra_intent 리다이렉션
- 저장·네트워크: 평문 SharedPreferences, 평문 HTTP, SSL 검증 무력화, FileProvider `root-path="/"`

---

## 발견 사항 (12건)

| # | 발견 | 심각도 | 참고 CVSS 3.1 | 재현 |
|---|---|---|---|---|
| 1 | WebView가 모든 SSL 오류 무시(MITM) | Critical | 8.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N) | S09 |
| 2 | exported ContentProvider 자격증명 유출(권한 normal) | Critical | 8.8 (AV:L/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N) | S06 |
| 3 | 하드코딩 자격증명(DEX) | High | 7.5 | S04 |
| 4 | 평문 SharedPreferences 자격 저장 | High | 6.8 | S04 |
| 5 | intent redirection → 비공개 화면·URL 통제 | High | 7.1 | S07 |
| 6 | 딥링크 임의 URL 로드(검증 없음) | High | 7.4 | S08 |
| 7 | 평문 HTTP + NSC/pinning 없음 | High | 7.4 | S10 |
| 8 | FileProvider `root-path="/"` 파일시스템 노출 | High | 7.1 | S13 |
| 9 | 클라이언트 측 인증(런타임 우회) | High | 6.8 | S14 |
| 10 | `debuggable` + 디버그 서명 + `allowBackup` | Medium | 5.5 | S02·S03 |
| 11 | 안전하지 않은 로깅(비밀번호 logcat) | Medium | 4.0 | S04 |
| 12 | 과권한 `READ_CONTACTS`(미사용) | Low | 3.3 | S12 |

(CVSS는 학습용 참고 점수입니다. 실제 등급은 배포 맥락·데이터 민감도에 따라 달라집니다.)

---

## 겹쳐서 커지는 그림 (체인)

개별 발견도 문제지만, 겹치면 피해가 증폭됩니다.

- 자격증명 완전 노출: 하드코딩(#3) → 평문 저장(#4) → exported provider(#2). 앱을 설치한 다른 앱 하나가, 사용자 확인 없이 받은 normal 권한만으로 아이디·비밀번호를 가져갑니다(캡스톤 증거).
- 네트워크 완전 장악: 평문 HTTP(#7) + SSL 무시(#1). 평문은 읽고, HTTPS는 가짜 인증서로 가로챕니다.
- 웹→앱 침투: 딥링크 임의 URL(#6) → WebView(#1). 웹 링크 한 줄로 앱 안에서 공격자 페이지가 뜹니다.

---

## 스크린샷 (캡스톤 증거)

직접 만든 공격 앱 `com.aas.loot`가 exported ContentProvider에서 로그인 자격증명을 실제로 뽑아낸 화면입니다. 그 아래는 발견 12건을 심각도별로 정리한 것입니다. 이 앱이 가진 건 자동 부여된 normal 권한 하나뿐입니다.

![PentestLoot 앱 화면 — [Critical] exported ContentProvider로 STOLEN username=shopuser / password=!ns3csh0p, 그리고 발견 목록(Crit WebView SSL 무시 S09, Crit exported Provider S06, High 하드코딩/평문저장/intent redirection/딥링크/평문HTTP/FileProvider/클라이언트인증, Med debuggable, Low 과권한)](/assets/img/android-app-security/S18/01-loot.png)

발견 요약과 공격 앱 소스는 `assets/evidence/android-app-security/S18/`에 남겼습니다.

---

## 대표 수정과 회귀 검증

발견들은 결국 세 문장으로 수렴합니다.

- 비밀은 서버·Keystore로. 하드코딩 자격증명 제거(#3), 평문 저장 대신 서버 토큰 + `EncryptedSharedPreferences`/Keystore(#4, S05), 인증 판정을 서버로(#9).
- 컴포넌트는 닫고 권한은 좁게. `exported` 명시·`false`, 커스텀 권한 `protectionLevel="signature"`(#2), FileProvider 경로를 하위 디렉터리로(#8), 안 쓰는 권한 제거(#12).
- 네트워크는 HTTPS + 검증. `usesCleartextTraffic="false"` + NSC + pinning(#7), `onReceivedSslError`에서 `proceed()` 금지(#1), 딥링크 URL 화이트리스트(#6).

회귀 검증은 각 발견의 재현 절차를 그대로 다시 돌려 "이제 실패하는지"로 확인합니다. 예를 들어 #2는 수정 후 공격 앱 설치 시 권한이 자동 부여되지 않고(signature) provider 질의가 거부되어야 하며, #1은 자체 서명 HTTPS가 경고와 함께 차단되어야 하고, #9는 Frida로 반환을 바꿔도 서버가 최종 판정하므로 로그인이 통과하지 않아야 합니다.

---

## 관측 결과 / 마무리

- InsecureShop에서 Critical 2건을 포함해 12건을 확인했고, 특히 자격증명은 여러 결함이 겹쳐 다른 앱 하나로 완전히 노출됐다.
- 공격 앱이 normal 권한만으로 실제 자격증명(`shopuser`/`!ns3csh0p`)을 탈취하는 것을 캡스톤으로 재현했다.
- 반복해서 확인된 교훈은 하나였다 — 클라이언트는 신뢰 경계가 아니다. 저장·판정·검증을 클라이언트에 두는 순간, 그것은 뒤집히거나 읽힌다.

S01의 빈 에뮬레이터에서 시작해 여기까지 왔습니다. 취약점 하나하나보다, 그것들이 왜 생기고 어디서 막아야 하는지를 손으로 확인한 게 이 시리즈의 목적이었습니다. 긴 시리즈 함께 읽어 주셔서 감사합니다.

---

## 참고 자료

- OWASP MASVS / MASTG — 모바일 앱 보안 검증·테스트 표준
- FIRST — CVSS 3.1 명세
- Android Developers — 앱 보안 모범 사례
