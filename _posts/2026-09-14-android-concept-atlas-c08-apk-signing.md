---
layout: post
title: "Android Security Concept Atlas C08 | 가상 실습 보고서 — APK 서명 v1~v4·키 순환, 앱 정체성의 신뢰 뿌리"
date: 2026-09-14 21:00:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, APKSigning, v2SigningBlock, KeyRotation, SigningLineage, Janus, MasterKey, apksigner, ConceptAtlas, 학습기록]
excerpt: "앱의 안정적 정체성은 패키지 이름이 아니라 서명자 인증서입니다 - sharedUserId(C09)·signature 권한(C10)·업데이트가 전부 '같은 키인가'로 결정되죠. v1(JAR 서명)은 열거된 파일 내용만 보호해 ZIP 구조·앞에 붙인 바이트를 못 봤고, 그 갭이 Master Key와 Janus였습니다. v2(A7.0)는 APK Signing Block으로 파일 전체를 서명해 그 클래스를 닫았고, v3(A9)는 proof-of-rotation lineage로 키를 바꿔도 정체성을 잇고, v3.1(A13)은 순환을 SDK로 겨냥하며, v4(A11)는 .idsig Merkle 트리로 스트리밍 설치를 v2/v3 위에 얹습니다. Tier 1 앱·패키징의 신뢰 뿌리 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r` |
| 관측 결과 | 증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다. |
| 검증 한계 | AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다. |

![C08 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/apps.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C08 — APK 서명 v1~v4·키 순환
> **계층**: Tier 1 (앱·패키징) · **난이도**: 중급 · **선수 개념**: C06(APK/zip), C07(DEX)
> **성격**: 보완 편.

C09에서 sharedUserId가 "같은 서명 키"를 요구한다 했고, C10의 signature 권한도, 앱 업데이트도 전부 그렇습니다. 그 **"같은 키인가"의 뿌리**가 이 편입니다.

한 문장으로: **앱의 안정적 정체성은 패키지 이름이 아니라 서명자 인증서이고, v1(파일별)→v2(전체 파일)→v3(키 순환)→v4(스트리밍)로 그 서명이 진화해 왔다.** 🟡 보완이라 핵심에 집중합니다.

## 배경 개념 - 네 세대의 서명

- **v1**(Android 1.0): JAR 서명. `META-INF` 3종. 열거된 파일 내용만.
- **v2**(A7.0): APK Signing Block. **파일 전체** 서명.
- **v3**(A9): 키 순환(SigningCertificateLineage). / **v3.1**(A13): 순환 SDK 겨냥.
- **v4**(A11): `.idsig` Merkle 트리. 스트리밍 설치(v2/v3 위에).

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

**앱 정체성의 신뢰 뿌리**입니다. 서명자 인증서(그 해시)가 앱의 안정 정체성이 되어, C09(sharedUserId 같은 키)·C10(signature 권한 같은 키)·앱 업데이트(같은 키)·C42(키 증명)·C48(Play Integrity·Play App Signing)이 전부 이 위에서 "같은 서명자인가"를 판정합니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

- **설치 시** `PackageInstaller`/PMS가 서명을 검증. 앱은 그 뒤 자기 UID(C09)로 실행.
- **v1**: `META-INF/MANIFEST.MF`(파일별 SHA-256 다이제스트) → `META-INF/CERT.SF`(매니페스트의 다이제스트) → `META-INF/CERT.(RSA|DSA|EC)`(CERT.SF에 대한 PKCS#7 서명 + 인증서 체인).
- **v2**(A7.0/API24): `[ZIP 엔트리][APK Signing Block][Central Directory][EoCD]` — Block은 Central Directory 바로 앞. 서명은 **파일 전체**를 3구획(블록 앞 전부 / CD / EoCD, CD 오프셋 정규화)으로 해시.
- **v3**(A9/28)·**v3.1**(A13/33)·**v4**(A11/30, 별도 `.idsig`).

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

- **서명자 인증서 = 안정 정체성**. v1은 **열거된 파일의 내용만** 보호하고 ZIP 구조·중앙 디렉터리·미열거/앞에 붙인 바이트는 안 봅니다 — 이 갭이 Master Key·Janus. v2는 파일 전체를 봐서 이 클래스를 닫습니다.
- **신뢰하면 안 되는 것들**:
  - **"CERT.SF가 서명이다"** — CERT.SF는 **평문 다이제스트 파일**(`SHA-256-Digest-Manifest` + 섹션별 다이제스트)입니다. 실제 암호 서명은 **`CERT.(RSA|DSA|EC)`의 PKCS#7**에만.
  - **"anti-strip은 min-SDK 기반"** — v1 강등 방지는 **`X-Android-APK-Signed` 속성**(CERT.SF의 main attributes에, 서명된 스킴 ID 리스트 예 `"2","3"`)입니다. v2-지원 기기가 이걸 보면 v1 폴백을 거부합니다. (v3 서명자가 별도로 min/max-SDK를 기록하는 것과 혼동 금지.)
  - **"Master Key도 v2가 고쳤다"** — Master Key(버그 8219321)는 **2013년 타깃 패치**(검증기·설치기가 같은 ZIP 엔트리를 쓰게)로 수정됐고, v2는 그 3년 뒤(A7.0/2016)입니다. **Janus만** v2/v3가 구조적으로 닫습니다.
  - **"v4가 v3를 대체"** — v4는 **병행** 레이어(v2/v3 서명을 앵커로 요구)이지 후계자가 아닙니다.
  - **"블록이 자기 자신을 서명"** — 블록은 서명에서 **제외**되는 유일 구역(자기 바이트는 못 서명).

## 질문 4 — 입력과 출력은 무엇인가

- **입력**: APK + Signing Block(v2/v3) 또는 `.idsig`(v4).
- **검증 로직**: 검증기는 **지원하는 최고 스킴을 요구**하고, 능력 있는 기기는 v1으로 조용히 폴백하지 않습니다(강등 거부).
- **출력**: 확립된 **서명자 정체성** — signature 권한(C10)·sharedUserId(C09)·업데이트 동일키·증명(C42)에 사용.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

- **Master Key**(CVE-2013-4787): 중복 ZIP 파일명 → **검증기가 한 사본을, 설치기가 다른 사본을** 씀. (2013 패치로 수정.)
- **Janus**(CVE-2017-13156): 유효한 DEX와 유효한 ZIP/APK를 이어붙일 수 있어(앞=DEX 헤더, 뒤=ZIP), 악성 DEX를 v1-서명 APK **앞에 붙여도** v1은 통과(앞/미열거 바이트를 무시)하고 런타임은 주입된 DEX를 실행. → v2/v3 전체파일 서명이 닫음(v1-only만 취약).
- **키 순환 lineage 없이** 키를 바꾸면 signature 권한·sharedUserId 연속성·업데이트 자격이 깨집니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

- **스킴↔버전(검증기 이해 floor)**: v1(1.0) · **v2 A7.0/24** · **v3 A9/28** · **v3.1 A13/33** · **v4 A11/30**. (버전은 이해하는 최저선이지 사용 강제가 아님. 순서가 v4 다음 v3.1로 비단조.)
- **블록 ID**: v2=`0x7109871a`, v3=`0xf05368c0`, v3.1=`0x1b93ad61`, 매직 `APK Sig Block 42`. v2/v3 블록은 같은 컨테이너에 공존.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

- `apksigner verify --verbose --print-certs <apk>`(어느 스킴 v1/v2/v3/v4가 있는지, 서명자 인증서 SHA-256).
- `unzip -l app.apk "META-INF/*"`(v1 3종 — META-INF는 APK 안의 디렉터리라 이 형태로), `<apk>.idsig`(v4), `keytool`/`openssl`로 인증서.
- `PackageManager.GET_SIGNING_CERTIFICATES`(런타임 서명자 조회).
- **소스**: `source.android.com/docs/security/features/apksigning`(+v2/v3/v4 하위), `apksig` 라이브러리(블록 ID·해시 구획·lineage).

**주의**: 서명 검증은 아키텍처와 무관하므로 **host와 Android Emulator에서 `apksigner verify`로 검증할 수 있습니다.**

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

- **C06(APK/zip)·C07(DEX)**: v1 갭·Janus가 정확히 ZIP 구조와 DEX 이어붙이기.
- **C09(UID/sharedUserId)**: sharedUserId·업데이트가 "같은 서명 키"를 요구.
- **C10(권한)**: signature 권한이 선언 앱과 같은 키일 때만 부여 — 다음 편.
- **C42(키 증명)·C48(Play Integrity)**: 이 서명자 정체성 위에서 추론.
- 다음은 이 정체성으로 "무엇을 허가할지" 정하는 **C10(permission·AppOps)**로 이어집니다.

## 직접 그릴 수 있는 호출 흐름

```
[ APK 서명: 무엇을 얼마나 덮는가 ]

  v1(JAR):  MANIFEST.MF(파일별 다이제스트)
              → CERT.SF(매니페스트 다이제스트, 평문)
              → CERT.RSA(CERT.SF에 대한 PKCS#7 서명+인증서)
            덮는 범위 = 열거된 파일 내용만  ← ZIP구조/앞바이트 갭 → Janus

  v2/v3:  [ZIP엔트리][APK Signing Block][Central Dir][EoCD]
              서명 = 파일 전체 3구획 해시(블록만 제외)
              v3: lineage(구키→신키, 각 홉을 이전 키가 서명) = 키 순환
  v4:  base.apk.idsig (Merkle 트리) — 스트리밍, v2/v3를 앵커로

  검증: 최고 스킴 요구 · v1 강등 거부(X-Android-APK-Signed in CERT.SF)
```

## 오개념 판별 문제 5개

1. "`META-INF/CERT.SF`가 APK의 암호 서명을 담고 있다."
2. "v1 강등(스트리핑) 방지는 최소 SDK 값으로 이뤄진다."
3. "Master Key와 Janus 둘 다 v2 전체파일 서명이 도입되며 처음 막혔다."
4. "v4 서명은 v3보다 강한 후계자로, v3를 대체한다."
5. "v2 서명 블록은 자기 자신을 포함해 파일의 모든 바이트를 서명한다."

<details><summary>판정 기준(펼치기)</summary>

1. CERT.SF는 **평문 다이제스트 파일**입니다. 서명은 `CERT.(RSA|DSA|EC)`의 PKCS#7에만.
2. **`X-Android-APK-Signed`**(CERT.SF의 서명된 스킴 ID 리스트)입니다. min-SDK는 v3 순환 겨냥의 별개 개념.
3. **Janus만** v2/v3가 닫습니다. Master Key는 2013년 타깃 패치로(v2보다 3년 앞) 수정됐습니다.
4. v4는 **병행** 레이어로 v2/v3 서명을 앵커로 요구합니다 — 대체가 아닙니다.
5. 서명 블록 자신은 **제외**됩니다(자기 바이트는 못 서명).
</details>

## 실측으로 확인한 것

가상 실습 환경(`codex-atlas-api33`, x86_64, Android 13/API 33)에서 이 모듈의 핵심 주장을 실제 명령으로 확인했다. 서명 검증은 아키텍처와 무관하므로(질문 7의 "주의"), ARM64 실기기 없이 host·AVD만으로 스킴을 확증할 수 있다.

**1) v2/v3 서명 스킴을 직접 빌드해 검증했다.** 증거 앱 APK를 소스에서 `javac`→`d8`→`aapt`→`zipalign`으로 빌드한 뒤, `apksigner verify`로 서명을 검사했다.

```console
$ apksigner verify --verbose --print-certs <apk>
```

관측 결과대로 v2/v3 서명이 검증됐다 — 질문 2의 "v2는 APK Signing Block으로 파일 전체를 서명한다"는 스킴 구조가 x86_64 AVD에서 그대로 성립함을 이 실행이 확증한다.

**2) 검증된 서명자 정체성 위에서 Package Manager가 별도 UID를 부여했다.** 검증을 통과한 APK를 설치하자, 관측 결과대로 Package Manager가 앱을 별도 UID로 등록했다.

```console
$ adb install -r <apk>
```

이는 질문 4의 출력(확립된 서명자 정체성)과 질문 1의 신뢰 뿌리 주장을 잇는다: 설치 시 PMS가 서명을 검증하고 그 뒤 앱이 자기 UID(C09)로 실행된다는 질문 2의 흐름이, 설치와 앱 등록으로 확인된다. 등록된 앱 목록은 상단 검증 화면(`apps.png`)에서, 원시 출력은 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)·[API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 교차 확인했다.

**3) 전체파일 서명이 Janus를 닫는 구조는 문서로 확정했다.** v1이 열거된 파일 내용만 덮어 앞에 붙인 바이트를 무시하는 갭(질문 3)과, v2/v3가 서명 블록 하나만 제외하고 파일 전체를 3구획으로 해시해 그 클래스를 닫는다는 사실은 `apksig` 라이브러리와 source.android.com 서명 문서의 해시 구획·블록 ID 정의로 확인했다. 이 부분은 AVD 실측이 아니라 소스·문서 근거다.

## 가상환경 검증 한계

정직하게, 이 세션의 실측 캡처는 빌드·검증·설치(1·2)까지다. 나머지는 근거는 확정했으나 이 AVD에서 새로 캡처하지 않았다.

- **Play App Signing과 AAB의 Play 서버 측 서명 변환은 이 로컬 Google APIs AVD에서 재현하지 않았다.** 검증 블록의 한계와 동일하게, Play 인프라가 관여하는 재서명 경로는 오프라인 에뮬레이터만으로 관측할 수 없다.
- **v3 키 순환(SigningCertificateLineage)과 v3.1 rotation-min-sdk의 실제 순환은 이 세션에서 서로 다른 두 키로 lineage를 생성해 재검증하지 않았다.** 근거는 apksig의 lineage 정의로 확정했을 뿐, 순환 동작 자체를 실행으로 관측하지는 않았다.
- **Janus·Master Key의 실 익스플로잇은 재현하지 않았다.** 악성 DEX를 이어붙이는 실 페이로드 없이, "앞바이트 무시" 구조 갭과 v2/v3 전체파일 서명이 그것을 닫는 원리까지만 다뤘다.

관련 근거: [APK 서명 개요](https://source.android.com/docs/security/features/apksigning) · [v2 스킴](https://source.android.com/docs/security/features/apksigning/v2) · [v3 스킴(키 순환)](https://source.android.com/docs/security/features/apksigning/v3) · [CVE-2017-13156 (Janus)](https://nvd.nist.gov/vuln/detail/CVE-2017-13156)

## 마치며

앱의 안정적 정체성은 패키지 이름이 아니라 **서명자 인증서**입니다 — sharedUserId(C09)·signature 권한(C10)·업데이트가 전부 "같은 키인가"로 결정됩니다. v1(JAR)은 열거된 파일 내용만 덮어 ZIP 구조·앞바이트를 못 봤고(그 갭이 Janus), v2(A7.0)는 APK Signing Block으로 파일 전체를 서명해 그 클래스를 닫았으며, v3(A9)는 proof-of-rotation lineage로 키를 바꿔도 정체성을 잇고, v4(A11)는 `.idsig` Merkle 트리로 스트리밍 설치를 v2/v3 위에 얹습니다. 그리고 강등 방지는 min-SDK가 아니라 CERT.SF의 `X-Android-APK-Signed`입니다. 다음은 이 정체성으로 "무엇을 허가할지" 정하는 **C10(permission·AppOps)**로 이어집니다.
