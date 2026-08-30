---
layout: post
title: "Android Security Concept Atlas C43 | 가상 실습 보고서 — 파일 기반 암호화와 Direct Boot, 잠금 전과 후의 두 저장소"
date: 2026-09-01 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, FBE, FileBasedEncryption, fscrypt, DirectBoot, DeviceEncrypted, CredentialEncrypted, MetadataEncryption, dmdefaultkey, SyntheticPassword, ConceptAtlas, 학습기록]
excerpt: "Android FBE의 system/user DE·CE storage class와 Direct Boot를 구분하고, credential·synthetic password·KeyMint·metadata encryption이 정지 상태 데이터 보호에 기여하는 범위를 정리합니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | AndroidKeyStore EC 키 생성, attestation challenge, `KeyInfo`, certificate chain 조회 |
| 관측 결과 | EC 키 생성과 attestation 요청이 성공했고 인증서 체인 길이는 3이었다. 이 AVD의 키 보안 수준은 정확히 `SOFTWARE(0)`였다. |
| 검증 한계 | TEE·StrongBox·Weaver는 물리 보안 하드웨어가 없는 AVD에서 증명할 수 없다. SOFTWARE 결과를 하드웨어 보안으로 해석하지 않는다. |

![C43 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C43 — FBE(파일 기반 암호화)·Direct Boot
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 중급 · **선수 개념**: C40(KeyMint), C41(synthetic password → CE 키)
> **성격**: 공식 문서·공개 소스 기준 재검토. C28(무결성)의 짝인 정지 상태 **기밀성**.

C28은 "부팅된 게 진짜인가"라는 **무결성**이었습니다. C43은 그 짝인 **기밀성** — "정지 상태(꺼지거나 잠긴) 데이터가 안 읽히는가"입니다. 그리고 C41에서 synthetic password가 파생한다던 그 **CE 키**가 실제로 무엇을 여는지가 여기입니다.

한 문장으로: **FBE는 서로 다른 storage class의 key를 독립적으로 unlock하며, CE 접근은 사용자 credential과 platform key hierarchy에 연결되지만 보호 강도는 구현과 credential 품질에 달려 있습니다.**

## 배경 개념 - 파일마다 다른 키

- **FBE (File-Based Encryption)**: 커널 `fscrypt` 기반. 파일마다 클래스 마스터 키에서 파생한 키로 암호화. 옛 **FDE**(전체 디스크, `dm-crypt`, 단일 키)를 대체.
- **DE (Device-Encrypted)**: 하드웨어 바인딩 키. **첫 잠금해제 전**에도 읽힘. 자격증명 무관.
- **CE (Credential-Encrypted)**: 자격증명 + 하드웨어로 보호. **첫 잠금해제 후**에만. 앱 데이터 대부분.
- **Direct Boot**: 첫 잠금해제 전, DE만 있는 구간에서 특정 컴포넌트가 도는 것.
- **메타데이터 암호화(dm-default-key)**: FBE가 평문으로 남긴 것(디렉터리 구조·크기 등)까지 덮는 블록 계층.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**정지 상태 기밀성**입니다. C28(무결성)의 짝이고, 부팅 후 **어떤 데이터가 언제** 읽히는지(DE/CE)를 정합니다. C41의 synthetic password가 파생하는 CE 키의 도착지이며, C40(KeyMint)이 그 키를 봉인합니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **커널 `fscrypt`**가 파일별 키로 암호화/복호합니다(ext4/f2fs).
- **부팅 시** `vold`/`init`이 하드웨어 바인딩 DE 키로 DE 저장소를 마운트해 Direct Boot 컴포넌트를 띄웁니다.
- **첫 잠금해제 시** 자격증명이 SP를 열고(C41), KeyMint(TEE, C40)가 봉인을 풀어 CE 키가 나오면 CE 저장소가 마운트됩니다.
- **throttle**은 Gatekeeper/Weaver(C41)가 강제합니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **DE는 하드웨어에 묶이고 자격증명과 무관**합니다. 그래서 잠금해제 전에도 읽힙니다 — **비밀을 두면 안 됩니다.**
- **CE는 2요소입니다**: 자격증명이 SP를 열고(scrypt로 늘린 LSKF), 그 SP는 KeyMint 키로 봉인되며, 무차별 대입은 Gatekeeper/Weaver가 하드웨어에서 throttle합니다. **자격증명만으로도(특정 기기 없이), 플래시만으로도(자격증명 없이)** CE 데이터가 안 열립니다.
- **신뢰하면 안 되는 것들**:
  - **"FBE면 디스크에 평문이 없다"** — FBE는 파일 **메타데이터**(디렉터리 구조·크기·권한·타임스탬프)를 평문으로 남깁니다. 그걸 덮는 게 별도의 dm-default-key(질문 5).
  - **"CE key는 PIN을 한 번 KDF에 넣은 값일 뿐"** — synthetic password, Gatekeeper/Weaver rate limiting과 KeyMint binding을 빠뜨린 설명입니다. 다만 offline attack 저항을 절대값으로 단정하지 말고 실제 구현과 credential entropy를 함께 평가합니다.
  - **"DE는 평문이라 먼저 읽힌다"** — DE도 암호화돼 있습니다. 자격증명에 게이팅되지 않을 뿐입니다.
  - **"실행 중 기기도 지켜준다"** — 아닙니다. FBE는 **정지 상태** 기밀성이고, 실행/잠금해제 후 기기는 키가 RAM에 있습니다.
  - **"FBE = 무결성"** — 무결성은 C28(AVB)입니다. FBE는 기밀성으로, 서로 직교합니다.

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: 파일 쓰기, 그리고 CE는 자격증명.
- **출력**: 암호화된 파일. **내용은 AES-256-XTS**, **파일명은 AES-256-CBC-CTS**(가속 하드웨어의 Android 14+는 **AES-256-HCTR2** 선호), AES 가속이 없는 저사양은 **Adiantum**(XChaCha12 기반)으로 둘 다.

파일별 키는 클래스(DE 또는 CE) **마스터 키 + 각 inode의 nonce**로 **HKDF-SHA512**(fscrypt 정책 v2, Android 11+ 기본)로 파생됩니다. 마스터 키는 디렉터리마다가 아니라 **정책/클래스마다**이고, 여러 디렉터리가 같은 마스터 키를 참조할 수 있습니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

**FBE/메타데이터 암호화는 정지 상태 기밀성만** 줍니다.

- **실행/첫-잠금해제-후(AFU) 기기**: CE 키가 RAM에 있어 특권 코드나 cold-boot(RAM 잔류) 공격에 노출됩니다. 이건 AVB(C28, 무결성)와 **직교**합니다 — 서로 대체하지 못합니다.
- **오프라인 브루트포스는 온디바이스 throttle을 통과해야** 합니다(C41). 뽑아낸 플래시 이미지에 대한 병렬 추측이 안 되고, 매 추측이 기기에서 rate-limit됩니다. 그래서 약한 PIN도 정지 상태에서는 안전합니다.
- **DE에 비밀을 두면** 잠금해제 전에 노출됩니다(Direct Boot 구간).
- **메타데이터 암호화의 키는 부팅 시 살아 있어** — dm-default-key는 파일시스템 **아래**에서 userdata 블록 디바이스 **전체**를 한 키로 암호화합니다(FBE 암호문까지 이중으로). 그래서 FBE가 남긴 메타데이터까지 덮이지만, 그 키가 부팅 시 존재하므로 **전원-꺼짐 경우만** 보호합니다.

이 범위 구분이 핵심입니다. 제 CVE 시리즈가 "실행 중 메모리"를 다뤘다면, FBE는 "꺼진/잠긴 디스크"를 다룹니다 — 완전히 다른 위협 모델입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

| 시점 | 달라진 것 |
|------|----------|
| Android 7.0 | **FBE**(fscrypt) 도입(선택), **Direct Boot** 도입 |
| Android 9 | **메타데이터 암호화**(dm-default-key) 도입 |
| **Android 10** | FBE **의무**(신규 기기), **FDE 금지** |
| **Android 11** | fscrypt **정책 v2**(HKDF-SHA512) 기본, 메타데이터 암호화 **의무**(내부 저장소) |
| **Android 14** | 파일명 **AES-256-HCTR2** 선호(가속 하드웨어, Linux 6.1+) |

주의: "FBE 도입 = Android 10"은 틀립니다 — 7.0부터 있었고 **10에서 의무/기본**이 됐습니다. "메타데이터 암호화 의무 = 10"도 틀립니다 — 도입은 9, **의무는 11**입니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**온디바이스**
- `getprop ro.crypto.type`(=`file`이면 FBE), `/proc/mounts`의 dm 매핑, `fstab`의 `fileencryption=`·`metadata_encryption=` 플래그.
- 앱: `Context.createDeviceProtectedStorageContext()`(DE 컨텍스트, 기본 컨텍스트는 CE), `android:directBootAware="true"`, `UserManager.isUserUnlocked()`. 데이터 이전은 `moveSharedPreferencesFrom(Context, String)`/`moveDatabaseFrom(...)`(대상=DE 컨텍스트, 원본=CE).
- 브로드캐스트: `ACTION_LOCKED_BOOT_COMPLETED`(잠금해제 전, **directBootAware 리시버에만**) → `ACTION_BOOT_COMPLETED`(잠금해제 후).

**주의(이번엔 반가운): 에뮬레이터도 FBE를 소프트웨어로 지원**하므로 DE/CE와 Direct Boot 동작은 **관측 가능**합니다 — 하드웨어 키 바인딩만 소프트웨어일 뿐. (C40/C39/C41의 하드웨어 보증과 대비되는 지점.)

**소스**
- `source.android.com/docs/security/features/encryption/{file-based,metadata,full-disk}`
- 커널 `Documentation/filesystems/fscrypt.rst`, `dm-default-key`
- `developer.android.com/training/articles/direct-boot`

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C41(Gatekeeper·Weaver·SP)**: synthetic password가 여기서 **CE 키를 파생**합니다. 그리고 그 언랩이 Gatekeeper/Weaver의 **throttle**을 거치기에 오프라인 브루트포스가 막힙니다. 정상 PIN 변경이 데이터를 재암호화하지 않는 이유(SP 재래핑)도 여기서 결론납니다.
- **C40(KeyMint)**: CE 키를 봉인하는 하드웨어 키가 KeyMint 키입니다. DE 키도 하드웨어 바인딩입니다.
- **C39(TEE)**: 그 봉인/언랩이 시큐어 월드에서 일어납니다.
- **C28(Verified Boot)**: 메타데이터 암호화 키가 KeyMint에, KeyMint가 Verified Boot에 걸립니다 — 그런데 **FBE=기밀성, AVB=무결성**으로 직교합니다.
- 다음은 앱 통제 티어 **C44(안전한 저장소·백업)**나 **C48(Play Integrity)**로 이어집니다.

## 호출 흐름

```
[ 부팅에서 첫 잠금해제까지 — 두 저장소가 열리는 순서 ]

부팅 → vold: 하드웨어 바인딩 DE 키로 DE 마운트
   │
   ▼
Direct Boot 구간 (CE 는 아직 암호문)
   │  ACTION_LOCKED_BOOT_COMPLETED → directBootAware 컴포넌트만
   │  알람·접근성·전화/수신·메시지 수신·키보드
   ▼
사용자 첫 잠금해제(자격증명)
   │  자격증명 → scrypt → (Weaver/Gatekeeper throttle) → SP 열림
   │  SP → KeyMint(TEE) 봉인 해제 → CE 클래스 키
   ▼
CE 마운트 → ACTION_BOOT_COMPLETED → 일반 앱 데이터 사용 가능
```

```
[ CE 키를 뽑아낸 플래시로 못 여는 이유 (2요소) ]

플래시 이미지만  ──▶ 자격증명 없음 → SP 못 엶 → CE 키 없음
자격증명만       ──▶ 그 기기의 KeyMint 키 없음 + throttle → 오프라인 병렬추측 불가
둘 다 + 그 기기  ──▶ 매 추측이 온디바이스 rate-limit → 약한 PIN 도 실용상 안전
```

## 실측으로 확인한 것

이 AVD(`codex-atlas-api33` · Android 13/API 33 · x86_64)에서 실제로 캡처한 측정은 KeyStore/attestation 한 건이고, 그 값이 이 모듈이 그어 둔 하드웨어 경계를 그대로 확증합니다.

**1) 이 AVD의 키 보안 수준은 `SOFTWARE(0)`다 — CE 키를 봉인할 KeyMint가 여기선 하드웨어가 아니다.** 검증 블록의 명령(AndroidKeyStore EC 키 생성 → attestation challenge → `KeyInfo` → 인증서 체인 조회)은 모두 성공했고, `KeyInfo`가 보고한 보안 수준은 정확히 `SOFTWARE(0)`, attestation 인증서 체인 길이는 3이었습니다.

```console
$ # AndroidKeyStore EC 키 생성 + attestation challenge → KeyInfo/체인 조회
KeyInfo.getSecurityLevel()          = SOFTWARE (0)
attestation certificate chain length = 3
```

질문 2와 질문 8은 "CE 키를 봉인하는 하드웨어 키가 KeyMint 키"라고 못박습니다. 그런데 이 AVD의 KeyMint는 `SOFTWARE(0)`로 떨어집니다 — CE 클래스 키를 감쌀 TEE/StrongBox가 물리적으로 없다는 뜻입니다. 질문 7이 "하드웨어 키 바인딩만 소프트웨어일 뿐"이라고 미리 못박은 경계가, 상단 [검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-keystore.png)의 키 보안 수준 값으로 확인됩니다. attestation 자체는 소프트웨어 폴백에서도 인증서 체인(길이 3)을 만들어 내지만, 그 뿌리가 하드웨어가 아니므로 CE 봉인과 Gatekeeper/Weaver throttle의 **하드웨어 보증은 이 값으로 주장할 수 없습니다**.

**2) FBE의 클래스 분리와 키 파생 구조는 커널·AOSP 문서로 확정했다.** DE/CE storage class가 각각 다른 마스터 키로 독립 언랩된다는 점, 파일별 키가 클래스 마스터 키 + 각 inode의 nonce에서 HKDF-SHA512(fscrypt 정책 v2, Android 11+ 기본)로 파생된다는 점, 내용은 AES-256-XTS·파일명은 AES-256-CBC-CTS(Android 14+·가속 하드웨어에서 HCTR2 선호)라는 점은 커널 `fscrypt.rst`와 source.android.com의 file-based encryption 문서에서 대조해 확인했습니다. 이는 소스·문서 근거이며 이 AVD의 새 측정이 아닙니다.

**3) "CE = 2요소" 불변식은 봉인이 온디바이스라는 전제 위에 선다.** 뽑아낸 플래시 이미지만으로는 자격증명이 없어 SP를 못 열고, 자격증명만으로는 그 기기의 KeyMint 키가 없어 봉인을 못 풉니다(질문 3·5, 직접 그릴 수 있는 호출 흐름의 2요소 도식). 그런데 (1)에서 보듯 이 AVD의 봉인 뿌리는 `SOFTWARE(0)`이므로, 이 불변식이 실제로 성립하려면 필요한 것은 정확히 이 AVD에 **없는** 하드웨어 봉인·rate-limit라는 사실이 측정으로 드러납니다. 즉 x86_64 에뮬레이터는 이 2요소 중 "온디바이스 하드웨어" 쪽을 소프트웨어로 흉내 낼 뿐입니다.

## 가상환경 검증 한계

정직하게, 이 문서가 새로 캡처한 실측은 위 (1)의 KeyStore/attestation 한 건입니다. 나머지는 근거를 소스로 확정했으나 이 AVD 세션에서 라이브로 재현하지는 않았습니다.

- **하드웨어 TEE/StrongBox/Weaver 봉인과 Gatekeeper/Weaver throttle은 이 AVD에서 측정되지 않았다.** 이 x86_64 AVD의 KeyMint는 `SOFTWARE(0)`로 폴백하므로(검증 블록의 검증 한계 줄과 동일), CE 키의 하드웨어 봉인이나 오프라인 브루트포스를 막는 온디바이스 rate-limit은 소프트웨어 흉내일 뿐 하드웨어 보증으로 관측되지 않았습니다.
- **DE/CE 접근 차이와 Direct Boot broadcast는 이 세션에서 새로 캡처하지 않았다.** 에뮬레이터가 FBE를 소프트웨어로 지원해 `directBootAware` 리시버의 `ACTION_LOCKED_BOOT_COMPLETED` 도착이나 `createDeviceProtectedStorageContext()`의 잠금 전 접근 차이는 원리상 관측 가능하지만, 이 문서의 증적은 KeyStore attestation 한 건에 한정됩니다.
- **dm-default-key 메타데이터 암호화 계층과 부팅 시 키 존재 조건은 라이브로 재현하지 않았다.** userdata 블록 전체를 한 키로 덮는 dm-default-key의 동작과 "전원-꺼짐 경우만 보호"라는 부팅 경로 특성은 fstab/커널 문서 근거로만 서술했고, 이 AVD에서 블록 계층을 실측하지 않았습니다.

관련 근거: [AOSP File-Based Encryption](https://source.android.com/docs/security/features/encryption/file-based) · [AOSP Metadata Encryption](https://source.android.com/docs/security/features/encryption/metadata) · [Kernel fscrypt.rst](https://www.kernel.org/doc/html/latest/filesystems/fscrypt.html) · [Android Direct Boot 가이드](https://developer.android.com/training/articles/direct-boot)

## 마치며

C28이 "부팅된 게 진짜인가"였다면, C43은 "꺼지거나 잠긴 데이터가 안 읽히는가"입니다. FBE가 데이터를 DE(하드웨어 바인딩, 잠금 전 읽힘, 비밀 금지)와 CE(자격증명 + 온디바이스 하드웨어, 잠금 후, 앱 데이터 대부분)로 나눠서, 알람과 전화는 Direct Boot 구간에 뜨고 메시지 본문은 잠금해제까지 암호문으로 남습니다.

CE protection은 credential, synthetic password, rate limiting과 platform key hierarchy를 결합해 offline attack 비용을 높입니다. 구체적인 보장은 구현과 credential quality에 따라 달라지며, 실행 중 compromise나 boot integrity를 대신하지 않습니다. 다음은 **C44(안전한 저장소·백업)**와 **C48(Play Integrity)**로 이어집니다.
