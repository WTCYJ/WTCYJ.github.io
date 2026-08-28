---
layout: post
title: "Android Security Concept Atlas C44 | 가상 실습 보고서 — 안전한 저장소·백업·키 관리, 하드코딩 키와 allowBackup이 새는 곳"
date: 2026-10-01 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, SecureStorage, Keystore, FBE, allowBackup, HardcodedKey, DataExtractionRules, ConceptAtlas, 학습기록]
excerpt: "리버싱에서 제일 자주 나오는 저장소 결함이 하드코딩된 암호화 키입니다 - APK에 박힌 키는 결국 모든 기기에 실려 나가는 공개값이라, 그걸로 한 암호화는 아무 기밀성도 없죠(내 Juice Shop·Toss 상수 케이스). 오해 둘: /data/data가 '사설'인 건 UID/SELinux 격리지 암호화가 아니고(root는 우회), FBE는 첫 잠금해제 전(BFU)의 잃어버린 기기만 지키지 켜져 돌아가는 앱엔 투명합니다 - 그래서 토큰·키 같은 앱 비밀은 비추출 Keystore(getEncoded가 null)에 넣어야죠. 그리고 allowBackup은 기본 true라, 백업 규칙을 안 쓰면 /data/data가 조용히 클라우드로 새 나갑니다. Tier 8 저장소 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | Android 개인정보·보안·네트워크 설정 캡처, `curl --tlsv1.3`, 패키지·AppOps 조회 |
| 관측 결과 | 권한·개인정보 통제 화면과 TLS 1.3 HTTP 200 응답을 확인했다. 앱·호스트 네트워크 관측을 분리해 기록했다. |
| 검증 한계 | Play Integrity의 프로덕션 verdict, 실제 OAuth 공급자, 제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다. |

![C44 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/privacy.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C44 — 안전한 저장소·백업·키 관리
> **계층**: Tier 8 (앱 보안 통제) · **난이도**: 중급 · **선수 개념**: C40(Keystore), C43(FBE)
> **성격**: 보완 편.

C40에서 Keystore를, C43에서 FBE를 봤습니다. 이 편은 앱이 **데이터를 어떻게 안전히 저장·백업·키관리하는가**, 그리고 어디서 새는가 — 내 RE 최다 발견인 하드코딩 키가 여기 삽니다.

한 문장으로: **/data/data 사설(UID/SELinux)과 FBE(정지 시 암호화)는 바닥선일 뿐, 앱 비밀은 비추출 Keystore에 넣어야 하고, allowBackup 기본 true는 데이터를 클라우드로 흘린다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념

- **내부 저장소**: `/data/data/<pkg>` = 앱 UID 소유, **UID DAC + SELinux**로 사설. + FBE 정지 시 암호화.
- **앱 비밀**: Keystore(비추출·TEE/StrongBox). 하드코딩 키 = #1 안티패턴.
- **백업**: `allowBackup` 기본 **true** → Auto Backup(Drive)/adb backup.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

앱 데이터 보호(저장·백업·키)의 **종합**입니다. C40(Keystore)·C43(FBE)·C09(UID)·C45(토큰 저장)이 여기서 만나고, 하드코딩 키가 내 RE·펜테스트 최다 발견.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **저장 위치**: 내부 `/data/data/<pkg>`(=`/data/user/0/<pkg>`, 멀티유저 `/data/user/<u>/`, 부팅 전 접근용 DE는 `/data/user_de/`) — 앱 UID 소유, **UID DAC + SELinux MAC**로 사설(C09/C23). 외부/공유는 넓고, **scoped storage**(A10 도입·A11 강제)로 자기 패키지 dir+MediaStore로 제한.
- **at-rest**: FBE(C43)로 암호화. **비밀**은 Keystore(C40): 키가 **비추출**·TEE/StrongBox, `setUserAuthenticationRequired`로 사용 게이트.
- **백업**: Auto Backup(~25MB, Drive) / Key-Value. `allowBackup` 기본 true.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **바닥선 vs 비밀 보호**: `/data/data` 사설 + FBE는 **바닥선**이지 고가치 비밀엔 불충분 → Keystore.
- **신뢰하면 안 되는 것들**:
  - **"`/data/data`가 사설이면 암호화된 것"** — 아닙니다. **UID/SELinux 격리**(권한 속성)지 암호화(암호 속성)가 아닙니다. root(UID 0)는 DAC를 우회.
  - **"FBE가 돌아가는 앱을 지킨다"** — FBE는 **BFU(첫 잠금해제 전)** 상태만 지킵니다(켜져 있어도 미해제면 CE 암호화 유지). AFU/라이브/루팅 프로세스엔 **투명하게 복호**됩니다 — 앱 비밀 방어가 아님.
  - **"하드코딩 키로도 암호화하면 안전"** — APK에 박힌 키는 모든 기기에 실려 나가는 **공개값**입니다. 정적 RE(`strings`/`jadx`/apktool)로 사소하게 복원(내 Juice Shop·Toss 상수). 키가 암호문과 함께 실리면 기밀성 0.
  - **"`allowBackup`은 신경 안 써도 된다"** — **기본 true**라, 백업 규칙을 안 쓰면 `/data/data`가 조용히 클라우드로. 민감 파일은 제외하거나 `allowBackup=false`.
  - **"Keystore는 `getEncoded()`로 키를 뽑을 수 있다"** — `getKey()`로 **핸들**은 얻지만 `getEncoded()`는 **null**(원본 바이트 안 나옴). 암호 연산은 시큐어 월드 내부에서.

## 질문 4 — 입력과 출력은 무엇인가

- **저장**: 데이터 → 내부(사설)/외부(scoped). 비밀 → Keystore 래핑(연산은 TEE 내부, `getEncoded`=null).
- **백업**: 데이터 → (제외 안 하면) Auto Backup으로 Drive. `fullBackupContent`(include/exclude) 또는 `dataExtractionRules`(A12+, cloud-backup vs device-transfer 분리)로 제어.
- **복원 캐비앗**: Keystore 키는 **비추출→백업에 안 실림**(기능) → 그 키로 암호화한 데이터는 **새 기기서 복호 불가**(재프로비저닝 필요).

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **하드코딩 키/IV**: 정적 RE로 복원 → "암호화"가 무의미. 특히 **GCM nonce 재사용은 치명**(같은 키에서 두 암호문 XOR로 평문 누출 + **GHASH 인증 서브키 H 복원 → 보편 위조**). CBC 고정 IV는 첫 블록 동일성 누출.
- **allowBackup=true + 민감 파일**: 클라우드/adb backup으로 토큰·DB 유출.
- **평문 토큰 저장**(C45): 루팅/백업/포렌식에서 유출.
- **FBE만 믿기**: 라이브/루팅 기기에서 비밀 노출.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **FBE**: A10부터 기본(FDE 대체). CE(첫 해제 후)/DE(부팅 시) 키 클래스.
- **scoped storage**: A10 도입·A11 강제.
- **StrongBox**: API28(`setIsStrongBoxBacked`).
- **`dataExtractionRules`**: A12/API31(targetSdk 31+); `fullBackupContent`는 12+에서도 동작(구버전/구타깃용).
- **adb backup 제한**: targetSdk **31+** 게이트(debuggable 오버라이드). security-crypto **deprecated**(마지막 1.1.0-alpha06).

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `jadx`/apktool/`strings`로 **하드코딩 키·IV** grep(base64/hex/`SECRET`/`KEY`, resources·`.so`·BuildConfig).
- manifest `android:allowBackup`·`fullBackupContent`·`dataExtractionRules`·`targetSdkVersion`, `adb backup -f app.ab <pkg>`로 노출 확인(디버그/구기기).
- `ls -Z /data/data/<pkg>`(DAC 권한 + SELinux 라벨), Keystore 사용에서 `getEncoded()`가 null인지.
- **소스**: developer.android.com data-storage·Keystore·Auto Backup, `source.android.com` FBE.

**주의**: 저장/백업은 아키텍처 무관 → **에뮬레이터로 하드코딩 키 grep·`adb backup`·manifest 실측 가능**(내부 파일은 디버그 앱/루팅).

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C40(Keystore)**: 비추출 키가 비밀 보호의 핵심.
- **C43(FBE)**: BFU at-rest — 바닥선.
- **C09(UID)·C23(SELinux)**: `/data/data` 격리.
- **C45(토큰)**: 토큰 저장이 이 편의 응용.
- 다음은 앱·기기 무결성 증명 **C48(Play Integrity)** 등으로.

## 직접 그릴 수 있는 호출 흐름

```
[ 저장 계층: 바닥선 vs 비밀 vs 백업 ]

  /data/data/<pkg> (앱 UID, UID DAC + SELinux 사설, C09/C23)
       + FBE 암호화 (단 BFU만! AFU/라이브/루팅엔 투명, C43)   ← 바닥선
       ✗ root는 DAC 우회 · FBE는 앱 비밀 방어 아님

  앱 비밀(토큰/키) ─▶ Android Keystore (비추출, TEE/StrongBox)
       연산은 시큐어 월드 · getKey()=핸들 / getEncoded()=null
       ✗ 하드코딩 키 = APK에 실린 공개값 = 기밀성 0 (RE로 복원)
       ✗ GCM nonce 재사용 = 치명(평문 XOR 누출 + GHASH H → 위조)

  백업: allowBackup 기본 true ─▶ Auto Backup(Drive)/adb backup
       제어 = fullBackupContent / dataExtractionRules(A12, 클라우드|전송 분리)
       Keystore 키는 백업에 안 실림(→새 기기서 복호 불가, 재프로비전)
```

## 오개념 판별 문제 5개

1. "`/data/data/<pkg>`는 앱 전용이라, 거기 저장하면 이미 암호화된 것이다."
2. "FBE가 켜져 있으면 실행 중인 앱의 파일도 저장 시 암호화돼 보호된다."
3. "암호화 키를 코드에 하드코딩해도, 암호화 자체는 안전하다."
4. "`android:allowBackup`을 명시하지 않으면 백업은 안 된다."
5. "Android Keystore 키는 `getEncoded()`로 원본 바이트를 꺼낼 수 있다."

<details><summary>판정 기준(펼치기)</summary>

1. **UID/SELinux 격리**지 암호화가 아닙니다. root는 우회하고, at-rest 암호화는 FBE가 별도로.
2. FBE는 **BFU(첫 잠금해제 전)**만 지킵니다. AFU/라이브/루팅엔 투명하게 복호됩니다.
3. APK에 박힌 키는 **공개값**입니다. 정적 RE로 복원돼 기밀성 0.
4. **기본 true**입니다. 규칙 없으면 `/data/data`가 클라우드로.
5. `getKey()`로 핸들만 얻고 `getEncoded()`는 **null**(원본 바이트 안 나옴).
</details>

## 서술형 문제 3개

1. `/data/data` 사설(UID/SELinux)과 FBE(BFU at-rest)가 왜 "바닥선"이고, 왜 앱 비밀엔 Keystore가 추가로 필요한지 서술하세요.
2. 하드코딩 키가 왜 기밀성을 0으로 만드는지, 특히 GCM nonce 재사용의 치명성(XOR 누출·GHASH H)을 서술하세요.
3. `allowBackup` 기본 true가 왜 유출 디폴트이며, `fullBackupContent`/`dataExtractionRules`로 어떻게 제어하는지 서술하세요.

## 소스·정적 검증 경로

- 소유/허가 앱을 `jadx`/apktool으로 열어 하드코딩 키·IV(base64/hex/`SECRET`)를 grep하세요.
- manifest의 `allowBackup`·백업 규칙·`targetSdk`를 확인하고, `adb backup`로 무엇이 노출되는지 보세요(디버그 앱).
- 앱이 토큰을 Keystore 래핑하는지 평문 prefs인지 점검하세요.

## 추가 심화 재현 절차

이 모듈을 **실측 글**로 승격하세요. 도식은 직접 그리지 말고 **실제 출력·화면만** 붙입니다.

1. **하드코딩 실측**: 디컴파일에서 하드코딩 키를(내 Juice Shop/Toss 경험 재서술, 상수 마스킹).
2. **백업 실측**: `adb backup`로 노출되는 파일을.
3. **저장 서술**: 사설(UID/SELinux) vs 암호화(FBE BFU) vs 비밀(Keystore)을 구분해.
4. **연결**: 토큰 저장(C45)을 이 틀로.

각 단계는 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

리버싱에서 제일 자주 나오는 저장소 결함이 하드코딩된 암호화 키입니다 — APK에 박힌 키는 결국 모든 기기에 실려 나가는 공개값이라 그걸로 한 암호화는 아무 기밀성도 없죠(특히 GCM nonce 재사용은 인증까지 무너뜨립니다). 오해 둘: `/data/data`가 "사설"인 건 UID/SELinux 격리지 암호화가 아니고(root는 우회), FBE는 첫 잠금해제 전(BFU)의 잃어버린 기기만 지키지 켜져 돌아가는 앱엔 투명합니다 — 그래서 토큰·키 같은 앱 비밀은 비추출 Keystore(`getEncoded`가 null)에 넣어야 합니다. 그리고 `allowBackup`은 기본 true라 백업 규칙을 안 쓰면 `/data/data`가 조용히 클라우드로 새 나갑니다. 다음은 앱·기기 무결성을 원격 증명하는 **C48(Play Integrity·앱 무결성)** 등으로 이어집니다.
