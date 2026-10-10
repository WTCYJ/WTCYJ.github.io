---
layout: post
title: "APK 수정·zipalign·재서명 — 왜 zipalign이 apksigner 전인가"
date: 2026-10-22 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, zipalign, apksigner, Repackaging]
excerpt: "수정한 APK를 설치하려면 순서가 중요하다 — zipalign을 apksigner '전에' 돌려야 한다. v2+ 서명은 정렬된 바이트 레이아웃을 서명하므로, 서명 후 zipalign하면 서명이 깨진다(구 jarsigner v1만 sign-then-align이 유효했다). 재서명은 서명자 정체성을 바꿔 원본 키 기반 signature 권한·Play 인식·pinning을 무너뜨린다."
---

정적으로 수정한 앱(5장)을 실행 가능하게 만드는 마지막 단계가 재서명이다. 그런데 여기엔 순서가 있다 — zipalign을 apksigner **전에** 돌려야 한다. 이 순서를 뒤집으면 설치 시 서명 검증이 실패한다. 그리고 재서명 자체가 서명자 정체성을 바꿔 원본 키 기반의 여러 보증을 무너뜨린다. 이 글은 수정→정렬→재서명 파이프라인을 올바른 순서로 돌리고, 변경을 문서화하며, 그 재서명의 함의를 정리한 기록이다.

> **한 줄 결론**: `zipalign -p 4` → `apksigner sign` 순서다. v2+ 서명은 정렬된 바이트를 서명하므로 서명 후 정렬은 서명을 깬다. 재서명은 서명자 정체성을 바꿔 signature 권한·PLAY_RECOGNIZED·pinning을 무너뜨린다(자작 랩에선 정상).

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 `apktool b`로 만든 unsigned APK를 정렬·재서명해 설치하는 파이프라인을 다룬다. 선수 개념은 [apktool/smali(5장)](/posts/android-lab-p1c05-apktool-smali/)의 unsigned 산출물, [서명 v1~v4(C08)](/posts/android-concept-atlas-c08-apk-signing/)의 서명 스킴·서명자 정체성, [Play Integrity(C48)](/posts/android-concept-atlas-c48-play-integrity/)의 PLAY_RECOGNIZED다.

## 핵심 개념 — 올바른 순서

1. **`zipalign -p 4 in.apk out.apk`** — 압축 안 된 데이터 4바이트 정렬, `-p 4`는 `.so`용 페이지 정렬. `Source-confirmed`
2. **`apksigner sign --ks debug.keystore out.apk`** — v2+ 서명. `Source-confirmed`

순서가 고정인 이유: apksigner의 v2+ 블록은 **정렬된 바이트 레이아웃을 서명**하므로, 서명 후 zipalign하면 그 바이트가 바뀌어 서명이 무효화된다. sign-then-align은 legacy jarsigner(v1)에서만 유효했다. `Source-confirmed`

**신뢰 경계와 위협 모델.** 재서명 = 새 서명자 정체성(C08). 원본 키 기반 signature 권한·sharedUserId·Play 인식(PLAY_RECOGNIZED, C48)·certificate pinning이 전부 깨진다 — 자작 랩에선 정상이지만, 이것이 "리패키징 탐지"의 근거이기도 하다([5부](/posts/android-security-mastery-series-index/)).

> **[그림 1]** `apksigner verify --print-certs`로 재서명 후 서명자 SHA-256이 원본과 달라진 것을 확인 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱만. 상용 앱 리패키징·보호 우회 금지. 디버그 키스토어로 재서명한다.

## 실습 절차와 관측

### 가설
sign 후 zipalign한 APK는 `apksigner verify`에 실패하고, zipalign 후 sign한 APK는 `Verified using v2 scheme: true`. `Inferred`

### 절차
1. `apktool b`로 unsigned APK.
2. `zipalign -p 4`.
3. `apksigner sign`.
4. `apksigner verify --print-certs`로 스킴·서명자 확인.
5. 원본과 서명자 SHA-256을 대조해 정체성 변경을 문서화.
6. (대조 실험) 순서를 뒤집어 verify 실패를 재현.

```bash
apktool b work                                          # work/dist/app.apk (unsigned)
zipalign -p 4 work/dist/app.apk aligned.apk
apksigner sign --ks debug.keystore --ks-pass pass:android aligned.apk
apksigner verify --print-certs aligned.apk
adb install -r aligned.apk
```

> **[그림 2]** 순서를 뒤집었을 때(sign→zipalign) `apksigner verify`가 실패하는 대조 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
$ apksigner verify --print-certs aligned.apk
Verified using v2 scheme (APK Signature Scheme v2): true
Signer #1 certificate SHA-256 digest: (원본과 다름 - 재서명됨)
```

## Root Cause — 왜 이렇게 되는가

zipalign-before-sign은 v2+가 **파일 전체 바이트를 서명**(C08)하기 때문이다 — 서명 후 정렬은 그 바이트를 바꿔 서명을 깬다. 재서명이 정체성을 바꾸는 것은 서명자 인증서가 곧 앱 정체성이기 때문이고, 그래서 같은 패키지를 다른 키로 업데이트하려 하면 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`이 난다.

## 방어와 회귀 검증

- (개발자) 리패키징 탐지: 런타임에 자기 서명자 인증서 해시를 확인(C08) — 단 루팅 기기선 우회 가능하므로 C48은 서버 검증. 수정 앱이 설치·기동되고 의도한 변경만 반영됐는지(smali diff + 동작)를 회귀로.
- (연구자) 재서명 함의(권한·pinning 붕괴)를 기록한다.

**흔한 실패와 처리.** `INSTALL_FAILED_UPDATE_INCOMPATIBLE` → 원본을 먼저 `uninstall` 후 설치(다른 서명). verify 실패 → 순서 확인(zipalign 먼저). v1만 검증됨 → `apksigner sign`이 build-tools 최신인지 확인.

## 버전 차이와 한계

- v2=API 24, v3=API 28, v4=API 30(.idsig). 최신 기기는 v2+를 요구한다(C08).
- 데스크톱에서 파이프라인, 설치·동작은 에뮬에서. 실제 Play App Signing 재서명은 관측 밖.

## 정리

- 순서는 `zipalign -p 4` → `apksigner sign` (v2+가 정렬 바이트를 서명).
- 재서명은 정체성을 바꿔 signature 권한·PLAY_RECOGNIZED·pinning을 무너뜨린다.
- 같은 패키지·다른 키 업데이트는 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`.

**점검 질문** — (1) 왜 zipalign이 apksigner 뒤에 오면 안 되는가? (2) 재서명이 깨뜨리는 것 3가지는? (3) `INSTALL_FAILED_UPDATE_INCOMPATIBLE`의 원인은?

**참고** — [zipalign](https://developer.android.com/tools/zipalign) · [apksigner](https://developer.android.com/tools/apksigner) · [C08 서명](/posts/android-concept-atlas-c08-apk-signing/) · [C48 Play Integrity](/posts/android-concept-atlas-c48-play-integrity/)

*다음 글: [Frida spawn/attach와 Java hook](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/).*
