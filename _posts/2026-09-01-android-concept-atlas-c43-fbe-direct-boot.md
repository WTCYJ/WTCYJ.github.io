---
layout: post
title: "Android Security Concept Atlas C43 - 파일 기반 암호화와 Direct Boot, 잠금 전과 후의 두 저장소"
date: 2026-09-01 21:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, FBE, FileBasedEncryption, fscrypt, DirectBoot, DeviceEncrypted, CredentialEncrypted, MetadataEncryption, dmdefaultkey, SyntheticPassword, ConceptAtlas, 학습기록]
excerpt: "C28이 무결성(부팅된 게 진짜인가)이었다면, C43은 그 짝인 기밀성(정지 상태 데이터가 안 읽히는가)입니다. 파일 기반 암호화는 옛 전체 디스크 암호화를 대체하며 데이터를 두 등급으로 나눕니다 - 자격증명 없이 부팅 직후 읽히는 Device-Encrypted, 첫 잠금해제 후에만 열리는 Credential-Encrypted. 그래서 알람과 전화는 잠금 전에도 뜨고(Direct Boot), 메시지 본문은 잠금해제까지 암호문으로 남습니다. 그리고 CE 키는 PIN을 KDF에 넣은 게 아니라 자격증명과 온디바이스 하드웨어 둘 다를 요구해, 뽑아낸 플래시 이미지는 오프라인으로 못 뚫습니다. Concept Atlas의 열네 번째 모듈입니다."
---

> **Concept Atlas 모듈**: C43 — FBE(파일 기반 암호화)·Direct Boot
> **계층**: Tier 7 (하드웨어 기반 보안) · **난이도**: 중급 · **선수 개념**: C40(KeyMint), C41(synthetic password → CE 키)
> **성격**: 미학습 → 풀 작성. C28(무결성)의 짝인 정지 상태 **기밀성**.

C28은 "부팅된 게 진짜인가"라는 **무결성**이었습니다. C43은 그 짝인 **기밀성** — "정지 상태(꺼지거나 잠긴) 데이터가 안 읽히는가"입니다. 그리고 C41에서 synthetic password가 파생한다던 그 **CE 키**가 실제로 무엇을 여는지가 여기입니다.

한 문장으로: **데이터를 자격증명 없이 부팅 직후 읽히는 DE와 첫 잠금해제 후에만 열리는 CE로 나누고, CE는 자격증명과 온디바이스 하드웨어를 둘 다 요구해 뽑아낸 플래시로는 못 연다.** 🔴 미학습이라 처음부터 세웁니다.

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
  - **"CE 키는 PIN을 KDF에 넣은 것"** — 아닙니다. 온디바이스 KeyMint + throttle을 거쳐야 하므로 **오프라인 병렬 브루트포스가 불가**합니다.
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

## 직접 그릴 수 있는 호출 흐름

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

## 오개념 판별 문제 5개

1. "FBE는 FDE처럼 userdata 전체를 한 키로 암호화한다."
2. "DE 저장소는 암호화되지 않아서 잠금해제 전에 읽을 수 있다."
3. "CE 키는 PIN을 KDF에 통과시킨 것뿐이라, 뽑아낸 플래시 이미지를 오프라인 브루트포스할 수 있다."
4. "FBE가 켜지면 디스크에 평문으로 남는 것은 없다."
5. "화면을 잠그면 CE 키가 메모리에서 제거된다 / FBE는 Android 10에 도입됐다."

<details><summary>판정 기준(펼치기)</summary>

1. FBE는 **파일마다** 클래스 마스터 키에서 파생한 키로 암호화합니다(HKDF). 단일 볼륨 한 키는 FDE(대체됨)입니다.
2. DE도 하드웨어 바인딩 키로 **완전히 암호화**돼 있습니다. 자격증명에 게이팅되지 않아 먼저 읽힐 뿐이라, 비밀을 두면 안 됩니다.
3. CE 언랩은 온디바이스 KeyMint(봉인)와 Gatekeeper/Weaver(throttle)를 거칩니다. 매 추측이 기기에서 rate-limit돼 오프라인 병렬 대입이 불가능합니다.
4. FBE는 파일 메타데이터(구조·크기·권한·타임스탬프)를 평문으로 남깁니다. 그걸 덮는 건 별도의 dm-default-key(Android 9 도입, 11 의무)로, 블록 전체를 한 키로 암호화합니다.
5. 일반 단일 사용자 폰에서 화면 잠금은 CE 키를 제거하지 **않습니다**(재부팅해야 RAM이 지워짐). 잠금 시 키 제거는 work profile/멀티유저(Android 12+ 옵션)의 별개 기능입니다. 그리고 FBE는 7.0부터 있었고 10에서 의무가 됐습니다.
</details>

## 서술형 문제 3개

1. DE와 CE의 키 **보호**가 어떻게 다른지(하드웨어 바인딩 vs 자격증명+하드웨어)와, 그래서 왜 DE는 잠금해제 전에 읽히고 CE는 안 읽히는지 서술하세요.
2. CE가 "2요소(자격증명 + 온디바이스 하드웨어)"라는 것이 왜 **뽑아낸 플래시 이미지의 오프라인 브루트포스**를 막는지, C41의 Gatekeeper/Weaver throttle과 연결해 서술하세요.
3. FBE/메타데이터 암호화가 "정지 상태 기밀성"일 뿐 **실행 중 기기**·**무결성(C28)**과 어떻게 다른지, 각각을 무엇이 담당하는지 서술하세요.

## 소스 탐색 과제

`sec-api33` 에뮬(FBE를 소프트웨어로 지원)에서 다음을 수행하세요.

- `getprop ro.crypto.type`(=`file` 확인)과 `/proc/mounts`의 dm/verity/암호화 매핑을 캡처.
- `android:directBootAware="true"` 리시버를 만들어 **잠금해제 전** `ACTION_LOCKED_BOOT_COMPLETED`에 뜨는지, 일반 리시버는 `ACTION_BOOT_COMPLETED`까지 안 뜨는지 대조.
- `createDeviceProtectedStorageContext()`로 DE에 쓴 값이 잠금해제 전 읽히고, 기본(CE) 컨텍스트에 쓴 값은 잠금해제 전 안 읽히는지 대조.
- 왜 이 관측이 에뮬에서도 되는지(FBE 소프트웨어 지원), 그리고 **무엇이 안 되는지**(하드웨어 키 바인딩·throttle의 실측)를 적으세요.

## 블로그 초안 작성 과제

이 모듈을 **실측 글**로 승격하세요. 환경: 에뮬로 FBE/Direct Boot의 **동작**은 관측 가능(DE/CE·브로드캐스트·컨텍스트), 하드웨어 키 바인딩·throttle의 **보증**은 실기기 필요. 도식은 직접 그리지 말고 **실제 명령 출력·화면만** 붙입니다.

1. **FBE 상태**: `ro.crypto.type=file`·`/proc/mounts`를 실제 출력으로.
2. **Direct Boot 실증**: directBootAware 리시버가 `LOCKED_BOOT_COMPLETED`에 뜨는 로그와, DE/CE 컨텍스트의 잠금 전 접근 차이를 캡처.
3. **범위 서술**: DE에 비밀을 두면 안 되는 이유와, FBE가 실행 중 기기를 못 지키는 이유를 실물로.
4. **하드웨어 대조**(가능하면): 실기기에서 CE 키가 KeyMint에 봉인됨을 (attestation/키 속성으로) 간접 확인.

각 단계는 명령 출력·실제 스크린샷으로만 증적화하고, 미확인 항목은 "못 한 것"으로 남기세요.

## 마치며

C28이 "부팅된 게 진짜인가"였다면, C43은 "꺼지거나 잠긴 데이터가 안 읽히는가"입니다. FBE가 데이터를 DE(하드웨어 바인딩, 잠금 전 읽힘, 비밀 금지)와 CE(자격증명 + 온디바이스 하드웨어, 잠금 후, 앱 데이터 대부분)로 나눠서, 알람과 전화는 Direct Boot 구간에 뜨고 메시지 본문은 잠금해제까지 암호문으로 남습니다.

그리고 CE의 힘은 **2요소**에 있습니다 — 자격증명이 SP를 열지만, 그 SP는 KeyMint에 봉인되고 브루트포스는 Gatekeeper/Weaver가 하드웨어에서 막습니다. 그래서 뽑아낸 플래시는 오프라인으로 못 뚫립니다. 다만 이 모든 것은 **정지 상태** 기밀성이지 실행 중 기기 방어도, 무결성(C28)도 아닙니다 — 각자 다른 층이 담당합니다. 다음은 앱이 이 저장소·키를 어떻게 쓰는지의 **C44(안전한 저장소·백업)**, 또는 런타임 무결성의 **C48(Play Integrity)**로 이어집니다.
