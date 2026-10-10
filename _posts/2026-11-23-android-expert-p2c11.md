---
layout: post
title: "PackageManagerService·설치/서명 검증"
date: 2026-11-23 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, PackageManagerService, APK서명, 코드서명, 서명검증]
excerpt: "APK 서명 검증은 '누가 만들었나'가 아니라 '설치된 것과 같은 서명자인가'를 본다. 대부분 self-signed라 신원 증명은 없고, v2 이후 검증 대상은 파일 목록(v1/JAR)이 아니라 APK 바이트 전체다 — Janus·Master Key가 그 경계에서 갈렸다."
---

앱 하나가 기기에 자리 잡기까지 사용자가 보는 건 "설치" 버튼 하나다. 그 뒤에서는 APK 바이트가 파싱되고, 서명이 검증되고, 같은 이름의 앱이 이미 있다면 "같은 서명자인가"라는 질문이 다시 걸린다. 이 질문에 어떻게 답하느냐가 Android 앱 신뢰 모델의 바닥이다 — 서명이 곧 앱의 정체성이기 때문이다. 이 글은 PackageManagerService(이하 PMS)가 App→Binder→system_server 경로에서 APK를 설치·검증하는 흐름과, v1~v4 서명 스킴이 각각 무엇을 지키는지를 AOSP 소스 경로와 함께 정리한 기록이다.

흔한 오개념부터 짚는다. "서명이 유효하다"는 "믿을 만한 앱이다"가 아니다. Android 앱 서명은 대부분 self-signed라, 서명은 무결성과 동일 출처를 증명할 뿐 서명자가 **누구인지**는 증명하지 않는다. 그리고 검증은 설치 때 한 번이 아니라 업데이트마다 반복된다.

> **한 줄 결론**: APK 서명은 신원이 아니라 "무결성 + 동일 서명자 연속성"을 증명한다. v2 이후 검증 대상은 파일 목록(v1/JAR)이 아니라 APK 바이트 전체이고, 업데이트는 기존 설치본과 같은 서명자(또는 회전 계보)여야만 통과한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 두 가지다. 하나, PackageInstaller 클라이언트 API가 세션을 만들고 커밋하면 system_server의 PackageInstallerService/PMS가 APK를 파싱→서명 검증→설치 확정하는 경로. 둘, v1(JAR)·v2·v3·v4 서명 스킴이 각각 무엇을 무결성 대상으로 삼는지. 공격 실습이 아니라 구조·소스 이해다.

선수 개념은 가볍다. 앱이 Binder IPC로 system_server의 서비스를 호출한다는 것(2부 14장 Binder proxy/stub), system_server가 특권 프로세스라는 것, 그리고 공개키 서명의 기본(해시→개인키 서명→공개키 검증)을 알면 충분하다. APK가 실은 ZIP 컨테이너라는 사실도 밑에 깔린다.

전체 구조에서 이 장은 "앱이 기기에 존재하기 위한 관문"이다. 다음 장(2부 12장)의 권한(PermissionManagerService·AppOpsService)은 여기서 설치·기록된 패키지를 전제로 하고, 서명은 signature-level 권한·sharedUserId·업데이트 신뢰가 모두 딛고 서는 뿌리가 된다.

## 핵심 개념 — 설치 파이프라인과 서명 스킴

설치 흐름을 App→Framework→Binder→system_server로 따라가면 이렇다.

1. 설치 관리자 역할 앱이 `PackageInstaller.Session`을 열고 APK 바이트를 스트리밍으로 쓴다.
2. `session.commit()` → Binder를 통해 system_server의 `PackageInstallerService`로 넘어간다.
3. 특권 설치자(`INSTALL_PACKAGES` 보유)가 아니면 사용자 확인 다이얼로그가 뜬다 — 신뢰 경계 = 사용자 동의.
4. system_server가 APK를 파싱하고, 서명을 검증하고, 기존 패키지가 있으면 서명 일치를 확인한 뒤 `/data/app/...`로 확정한다.
5. 결과 상태는 `/data/system/packages.xml`에 기록된다. `Source-confirmed`

파싱·설치 로직은 `frameworks/base/services/core/java/com/android/server/pm/` 아래에 있고, 서명 검증의 입구는 `frameworks/base/core/java/android/util/apk/`의 `ApkSignatureVerifier`다(스킴별로 `V2SchemeVerifier`·`V3SchemeVerifier` 등으로 분기). 클래스는 버전에 따라 위치·이름이 바뀌니 인용 시 브랜치 확인이 필요하다. `Source-confirmed`

서명 스킴이 각각 무엇을 지키는지 정리하면 아래와 같다.

| 스킴 | 도입 | 무결성 대상 | 핵심 |
|--|--|--|--|
| v1 (JAR) | 최초 | `META-INF`의 파일별 다이제스트 | ZIP 메타데이터·미포함 바이트는 무보호 |
| v2 | Android 7.0 (API 24) | Signing Block을 뺀 APK 바이트 전체 | whole-file 무결성 |
| v3 | Android 9 (API 28) | v2 + 키 회전 계보(proof-of-rotation) | 서명키 교체 허용 |
| v3.1 | Android 13 (API 33) | v3 회전을 SDK 버전으로 타깃팅 | 신·구 기기 분리 회전 |
| v4 | Android 11 (API 30) | fs-verity Merkle 트리(별도 `.idsig`) | 증분 설치 |

`Source-confirmed`

핵심은 v1→v2의 도약이다. v1은 "각 파일이 서명됐나"를 보고, v2는 "APK라는 바이트 덩어리 전체가 서명됐나"를 본다. v2 이후 서명 정보는 ZIP의 Central Directory 바로 앞 **APK Signing Block**에 들어가며, 블록 끝 마법값은 `APK Sig Block 42`, v2 블록 ID는 `0x7109871a`다. `Source-confirmed`

> **[그림 1]** 에뮬레이터에서 파일 관리자로 자작 APK를 탭했을 때 뜨는 PackageInstaller 확인 다이얼로그 — 설치 파이프라인이 사용자 동의를 거치는 지점. (`adb install`은 shell(uid 2000)이 `INSTALL_PACKAGES`를 쥔 특권 경로라 이 다이얼로그 없이 무음 설치되므로, 이 화면은 비특권 경로에서만 나온다.) — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

경계는 둘이다. **설치 시점** — system_server가 서명을 검증하고, 특권 설치자가 아니면 사용자 동의를 확인한다. **업데이트 시점** — 새 APK가 기존 설치본과 같은 서명자인지 다시 확인한다.

공격자가 노리는 것은 "정상 앱을 조용히 악성 버전으로 대체"하거나 "다른 앱의 서명을 위조해 그 앱 행세"하는 것이다. 방어는 서명이다 — 같은 패키지명이라도 서명자가 다르면 업데이트는 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`(서명 불일치)로 거부된다. `Source-confirmed` `sharedUserId`와 signature 권한도 같은 뿌리를 쓴다: 같은 서명자만 UID·권한을 공유할 수 있다.

한계이자 오개념 교정 하나 — 서명은 self-signed라 "이 서명자가 신뢰할 만한 개발자다"를 증명하지 않는다. 그건 Play 프로텍트·설치 출처·평판의 영역이다. 서명이 보장하는 건 딱 "설치된 그 앱과 같은 손에서 나왔다"까지다.

## 분석 — 서명 블록과 검증 코드 경로

검증 순서는 `ApkSignatureVerifier`가 정한다: 사용 가능한 **최고 스킴부터** 시도한다. v3/v3.1이 있으면 그것으로, 없으면 v2, 그것도 없으면 v1(JAR)로 내려간다. 최소 요구 스킴은 targetSdk에 종속되며, targetSdk 30(R) 이상 앱은 v2 이상 서명이 요구된다 — 정확한 경계는 원문 재확인 권장. `Reported`

관측은 안전 범위(자작 앱)에서 `apksigner`로 한다. `apksigner verify -v --print-certs`가 어떤 스킴으로 검증됐는지와 서명자 인증서 지문을 그대로 보여준다.

```bash
apksigner verify -v --print-certs app-release.apk
```

`예시 출력(교체)`:

```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Number of signers: 1
Signer #1 certificate SHA-256 digest: <hex>
```

설치 후 기록은 `adb shell dumpsys package <패키지명>`으로 교차 확인한다 — versionCode·installerPackageName·서명 요약이 나오고, 서명 지문이 `apksigner`의 것과 일치해야 한다.

> **[그림 2]** 자작 앱을 v1은 끄고 v2/v3만 켜서 서명한 뒤 `apksigner verify -v --print-certs`로 스킴별 true/false와 인증서 SHA-256을 확인한 터미널 캡처 — *실측 스크린샷 자리*

## Root Cause — 왜 이렇게 되는가

v1이 파일 단위로만 서명한 게 근본 원인이었다. ZIP은 로컬 파일 엔트리와 중앙 디렉터리로 이중 기술되는데, v1은 파일 **내용**만 해시했지 이 구조·중복·미포함 바이트를 지키지 못했다. 그래서 두 계열의 우회가 나왔다(둘 다 공개·패치 완료된 과거 사례).

- **Master Key(CVE-2013-4787)**: ZIP에 같은 이름 파일을 둘 넣어, 검증기는 서명된 쪽을·설치기는 악성 쪽을 읽게 만드는 TOCTOU. `Reported`
- **Janus(CVE-2017-13156)**: 유효한 APK 앞에 DEX를 이어 붙여도 v1 검증은 통과하고 ART는 앞의 DEX를 실행. v2가 whole-file을 지키면서 막혔다. `Reported`

v2의 설계가 바로 이 교훈의 결정체다: 검증 대상을 "파일 목록"이 아니라 "Signing Block을 제외한 APK 바이트 전체 + Central Directory + EOCD"로 바꿔, 한 바이트라도 손대면 실패하게 했다. `Source-confirmed` 업데이트의 "같은 서명자" 규칙도 같은 논리다 — 무결성만으론 "누가 이걸 대체했나"를 못 막으니, 연속성(같은 키, 또는 v3 회전 계보)을 별도로 요구한다.

## 버전 차이와 한계

- 스킴은 누적된다: v3 서명 APK는 보통 v2 블록도 함께 담아 구형 기기와 호환하며, 상위 스킴을 아는 기기는 상위 블록을 우선 검증해 다운그레이드를 막는다. `Source-confirmed`
- v4는 서명을 APK 안이 아니라 별도 `.apk.idsig`에 두고 fs-verity Merkle 트리를 쓴다 — 증분 설치(Incremental installation / "Play as you download")용이라 일반 사이드로드 관측과는 결이 다르다. `Source-confirmed`
- PMS 설치 로직은 Android 12~13 즈음 `InstallPackageHelper` 등 헬퍼 클래스로 크게 리팩터링됐다. 소스 경로/메서드명을 인용할 땐 브랜치(예: `android-14.0.0_r…`)를 명시해야 오해가 없다. `Inferred`
- 에뮬레이터에서도 서명 검증·설치 파이프라인은 그대로 관측되지만, 하드웨어에 묶인 신뢰(예: 검증 부팅의 vbmeta 서명)는 이 장의 범위 밖이다.

## 정리

- APK 서명 = 무결성 + 동일 서명자 연속성. 신원 증명이 아니다(대부분 self-signed).
- v1은 파일 단위, v2+는 whole-file. Janus·Master Key가 그 경계를 만든 사건이다.
- 업데이트·`sharedUserId`·signature 권한은 모두 "같은 서명자"라는 한 뿌리를 공유한다.

**점검 질문** — (1) v2가 v1과 달리 무엇을 무결성 대상으로 삼는가? (2) 같은 패키지명·다른 서명자 APK로 업데이트하면 무엇이 거부하는가? (3) "서명이 유효함"이 증명하지 **못하는** 것은?

**참고** — [Android 앱 서명](https://source.android.com/docs/security/features/apksigning) · [v2 스킴](https://source.android.com/docs/security/features/apksigning/v2) · [v3 스킴](https://source.android.com/docs/security/features/apksigning/v3) · [apksigner](https://developer.android.com/tools/apksigner) · [PackageInstaller](https://developer.android.com/reference/android/content/pm/PackageInstaller) · AOSP `frameworks/base/services/core/java/com/android/server/pm/`

*다음 글: [PermissionManagerService·AppOpsService](/posts/android-expert-p2c12/).*
