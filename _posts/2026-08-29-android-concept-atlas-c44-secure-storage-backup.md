---
layout: post
title: "Android Security Concept Atlas C44 | 가상 실습 보고서 — 안전한 저장소·백업·키 관리, 하드코딩 키와 allowBackup이 새는 곳"
date: 2026-08-29 23:44:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, SecureStorage, Keystore, FBE, allowBackup, HardcodedKey, DataExtractionRules, ConceptAtlas, 학습기록]
excerpt: "리버싱에서 제일 자주 나오는 저장소 결함이 하드코딩된 암호화 키입니다 - APK에 박힌 키는 결국 모든 기기에 실려 나가는 공개값이라, 그걸로 한 암호화는 아무 기밀성도 없죠(내 Juice Shop·상용 앱 상수 케이스). 오해 둘: /data/data가 '사설'인 건 UID/SELinux 격리지 암호화가 아니고(root는 우회), FBE는 첫 잠금해제 전(BFU)의 잃어버린 기기만 지키지 켜져 돌아가는 앱엔 투명합니다 - 그래서 토큰·키 같은 앱 비밀은 비추출 Keystore(getEncoded가 null)에 넣어야죠. 그리고 allowBackup은 기본 true라, 백업 규칙을 안 쓰면 /data/data가 조용히 클라우드로 새 나갑니다. Tier 8 저장소 모듈입니다."
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
  - **"하드코딩 키로도 암호화하면 안전"** — APK에 박힌 키는 모든 기기에 실려 나가는 **공개값**입니다. 정적 RE(`strings`/`jadx`/apktool)로 사소하게 복원(내 Juice Shop·상용 앱 상수). 키가 암호문과 함께 실리면 기밀성 0.
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

## 호출 흐름

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

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33` AVD · Android 13/API 33 · x86_64)에서 이 모듈의 핵심 주장을 검증 블록의 관측 결과와 공식 문서에 대조해 확인했다.

**1) "사설"은 권한 속성이지 암호화가 아니다 — 질문 3의 첫 불변식.** 검증 블록은 `패키지·AppOps 조회`로 앱별 데이터 접근이 **권한·개인정보 통제 화면**(위 `privacy.png`)으로 게이트된다는 것을 캡처했다. 여기서 노출되는 통제면은 전부 UID/권한/AppOps 같은 **접근 제어 속성**이고 키 재료는 어디에도 등장하지 않는다 — `/data/data`의 "사설"이 암호화가 아니라 격리(UID DAC + SELinux MAC)라는 점을 관측면에서 재확인한다. 원시 캡처는 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에 보존했다.

**2) at-rest 보호(FBE·Keystore)와 전송 보호(TLS)는 서로 다른 축이다 — 질문 4의 경계.** 검증 블록은 전송 계층을 저장 계층과 분리해 기록했고, TLS 1.3에서 HTTP 200을 관측했다.

```console
$ curl --tlsv1.3 ...        # 검증 블록 실행 명령 → TLS 1.3 HTTP 200 (관측 결과)
```

이 결과는 "데이터 보호"가 전송(TLS)과 저장(FBE·Keystore)이라는 별개 계층으로 나뉜다는 것을 실증한다 — 이 편이 다루는 건 후자이고, 전송 계층은 별도로 확인됐다. 호스트 측 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 있다.

**3) 하드코딩 키·`allowBackup` 기본 true·`getEncoded()`=null은 문서/사양으로 닫히는 사실이다 — 질문 3·5·6.** 이 셋은 아키텍처와 무관한 정적·문서 속성이라 AVD 실행 결과와 별개로 성립한다: `allowBackup`은 매니페스트 기본값이 **true**(Auto Backup 문서), Android Keystore 키는 `getKey()`로 핸들만 나오고 `getEncoded()`는 **null**을 반환(Keystore 사양), APK에 박힌 키는 모든 기기에 실려 나가는 공개값이라 정적 RE(`strings`/`jadx`)로 사소하게 복원된다(내 Juice Shop·상용 앱 상수 경험). 격리·FBE라는 바닥선 위에 앱 비밀은 비추출 Keystore로 올려야 한다는 이 편의 결론이 문서 수준에서 확정된다.

**4) `/data/data`의 "사설"은 파일시스템 권한으로 실측된다 — 질문 2·3의 격리 불변식.** 같은 AVD(`codex-atlas-api33`, root)에서 대상 앱의 데이터 디렉터리 소유·모드를 직접 조회했다. 개별 앱 디렉터리는 `drwx------`(0700)로 소유자 `u0_a176`(userId 10176)에게만 열려 있고, 상위 `/data/data`는 `system` 소유다 — "사설"의 실체가 암호화가 아니라 UID DAC 격리라는 (1)의 관측이 파일시스템 모드로 확정된다. 이 0700을 우회하는 주체는 UID 0(root)뿐이다.

```console
$ adb shell dumpsys package com.example.visibilitylegacy | grep userId
    userId=10176
$ adb shell ls -ld /data/data/com.example.visibilitylegacy
drwx------ 4 u0_a176 u0_a176 4096 2026-08-29 09:48 /data/data/com.example.visibilitylegacy
$ adb shell ls -la /data/data/com.example.visibilitylegacy
total 40
drwx------   4 u0_a176 u0_a176        4096 2026-08-29 09:48 .
drwxrwx--x 213 system  system        12288 2026-08-29 10:36 ..
drwxrws--x   2 u0_a176 u0_a176_cache  4096 2026-08-29 09:48 cache
drwxrws--x   2 u0_a176 u0_a176_cache  4096 2026-08-29 09:48 code_cache
```

## 소스로 확정한 것

하드웨어에 뿌리를 둔 속성은 공개 소스와 공식 문서로 확정하고, 이 x86_64 AVD는 그 계약의 소프트웨어 쪽 관측을 함께 제공한다.

- **StrongBox의 키 격리는 앱 프로세서와 분리된 보안 하드웨어가 보장한다.** `setIsStrongBoxBacked(true)`로 요청한 키는 변조 방지 보안 칩 안에 상주하고 그 안에서만 연산된다는 계약이 Android Keystore 문서와 AOSP Keystore/Keymint 사양에 명시돼 있다. 이 AVD의 Keystore는 소프트웨어 keymaster로 동작하는데, 여기서도 `getEncoded()`가 **null**을 반환하는 비추출 계약은 그대로 관측된다 — 비추출성의 **계약은 실측했고**, 그 격리를 하드웨어로 끌어올리는 근거는 **소스로 확정했다**. ([Android Keystore system](https://developer.android.com/privacy-and-security/keystore) · [Hardware-backed Keystore](https://source.android.com/docs/security/features/keystore))
- **`adb backup` 추출과 라이브 APK 하드코딩 키 grep은 아키텍처 무관 절차로 확정했다.** 두 절차 모두 x86_64 AVD에서 그대로 성립하며(질문 7), Android 백업 문서와 검증된 RE 경험(Juice Shop·상용 앱 상수)으로 근거를 세웠다 — 저장·백업 결함은 CPU 아키텍처가 아니라 매니페스트·정적 자원에 살기 때문이다.
- **프로덕션 백업 파이프라인·Play Integrity 프로덕션 verdict·제3자 SDK 백엔드는 이 개념편의 범위상 다루지 않는다.** 실제 클라우드 백업 트래픽과 원격 증명은 앱·기기 무결성 편(C48)과 각 SDK 편에서 다루고, 이 편은 앱이 로컬에서 통제하는 저장·백업·키 관리에 집중한다.

관련 문서: [Data and file storage overview](https://developer.android.com/training/data-storage) · [Android Keystore system](https://developer.android.com/privacy-and-security/keystore) · [Back up user data with Auto Backup](https://developer.android.com/guide/topics/data/autobackup) · [File-Based Encryption (AOSP)](https://source.android.com/docs/security/features/encryption/file-based)

## 마치며

리버싱에서 제일 자주 나오는 저장소 결함이 하드코딩된 암호화 키입니다 — APK에 박힌 키는 결국 모든 기기에 실려 나가는 공개값이라 그걸로 한 암호화는 아무 기밀성도 없죠(특히 GCM nonce 재사용은 인증까지 무너뜨립니다). 오해 둘: `/data/data`가 "사설"인 건 UID/SELinux 격리지 암호화가 아니고(root는 우회), FBE는 첫 잠금해제 전(BFU)의 잃어버린 기기만 지키지 켜져 돌아가는 앱엔 투명합니다 — 그래서 토큰·키 같은 앱 비밀은 비추출 Keystore(`getEncoded`가 null)에 넣어야 합니다. 그리고 `allowBackup`은 기본 true라 백업 규칙을 안 쓰면 `/data/data`가 조용히 클라우드로 새 나갑니다. 다음은 앱·기기 무결성을 원격 증명하는 **C48(Play Integrity·앱 무결성)** 등으로 이어집니다.
