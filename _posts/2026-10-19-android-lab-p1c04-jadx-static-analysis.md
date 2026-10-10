---
layout: post
title: "jadx로 Java/Kotlin 정적 분석 — 재구성의 한계를 알고 읽기"
date: 2026-10-19 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, jadx, StaticAnalysis, Decompiler]
excerpt: "jadx는 DEX를 Java로 '재구성'한다 — 원본이 아니라 근사치라, 일부 메서드는 실패해 명령 덤프로 떨어지고 R8 난독화된 이름은 --deobf로도 복원되지 않는다. 패커가 있으면 로더 stub만 보인다. 그래서 'jadx에 안 보인다 = 깨끗하다'가 아니라, 정적 한계가 동적 분석으로 넘어가는 지점이다."
---

정적 분석은 앱의 지도를 그리는 일이다. jadx로 DEX를 Java로 풀면 로직·하드코딩 비밀·엔트리포인트가 드러나고, 이후 동적 분석([Frida](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/))의 타깃이 여기서 정해진다. 다만 반드시 기억할 것이 있다 — jadx 출력은 **원본이 아니라 재구성**이라, 실패한 메서드는 조용히 빠지고 난독화된 이름은 복원되지 않으며 패커는 stub만 남긴다. 이 글은 jadx로 무엇을 어떻게 찾고, 어디서 한계에 부딪히는지를 정리한 기록이다.

> **한 줄 결론**: jadx의 Java는 근사 재구성이다. `--show-bad-code`로 실패 메서드까지 보고, R8 난독화 앞에선 이름이 아니라 검색·xref로 읽으며, 코드가 거의 없으면 패커를 의심해 동적으로 넘어간다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 jadx CLI/GUI로 exported 컴포넌트·크립토·WebView 브리지·하드코딩 키를 찾는 워크플로를 다룬다. 선수 개념은 [APK triage(3장)](/posts/android-lab-p1c03-apk-triage/)의 대상 확보, [ART DEX→OAT(C13)](/posts/android-concept-atlas-c13-art-dex-oat-vdex/)의 "DEX가 분석 원천", [ClassLoader·동적로딩(C14)](/posts/android-concept-atlas-c14-classloader-reflection/)의 "패커는 stub만 남긴다"이다.

## 핵심 개념 — 재구성 도구로서의 jadx

- jadx는 DEX→**근사 Java**로 재구성한다(원본 아님). 실패 메서드는 **jadx 자체 명령 덤프 + `/* JADX WARN */`** 주석(또는 "Method dump skipped, instructions count: N")으로 떨어지고, 진짜 smali는 `jadx-gui`의 Smali 탭에서만 본다. `Source-confirmed`
- **CLI**: `jadx -d out app.apk`(`-d`/`--output-dir`), `--show-bad-code`(불완전 메서드도 강제 출력 — 기본은 숨김), `--deobf`(난독 이름을 **일관된 합성 이름**으로 — 원본 복원 아님), `-e`/`--export-gradle`, `-r`/`--no-res`·`-s`/`--no-src`. `Source-confirmed`
- **입력**: apk/dex/jar/class/smali/aar/zip/aab/arsc. jadx가 매니페스트·resources.arsc도 디코드해 read-only 뷰어로도 쓰인다.
- **jadx-gui**: 전문 검색·`Find Usage`(xref)·rename 전파·매니페스트/리소스 렌더. 보안 워크플로의 주력.

**신뢰 경계와 위협 모델.** 정적 뷰가 곧 진실은 아니다. 재구성된 제어 흐름을 **모델**로 다뤄야 하고, 패커/동적 로딩이 있으면 실제 코드는 런타임에만 나타난다(C14). Kotlin은 같은 바이트코드로 컴파일되므로 jadx는 Java-ish로 풀고, Kotlin 구문은 불완전하게 복원된다.

> **[그림 1]** jadx-gui에서 매니페스트의 exported 컴포넌트 → 클래스로 점프하고 `Find Usage`로 참조를 추적하는 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 앱을 두 버전으로 만든다: 하드코딩 키·WebView 브리지를 일부러 넣은 취약 버전과, Keystore·브리지 제거의 안전 버전. 둘을 정적으로 대조한다.

## 실습 절차와 관측

### 가설
취약 버전엔 `SecretKeySpec("hardcoded".getBytes())` 류가 검색되고, 안전 버전엔 Keystore 사용만 보인다. `Inferred`

### 절차
1. `jadx -d out app.apk` 또는 `jadx-gui app.apk`.
2. 매니페스트에서 exported 컴포넌트 → 해당 클래스로 이동.
3. 검색: `Cipher`·`SecretKeySpec`·`IvParameterSpec`·`addJavascriptInterface`·`@JavascriptInterface`·`setJavaScriptEnabled`.
4. 하드코딩 후보(base64/hex/"KEY"/"SECRET") 검색 + `Find Usage`로 흐름 추적.
5. `--show-bad-code`로 재실행해 누락 메서드를 확인.

```bash
jadx -d out app.apk
jadx --show-bad-code -d out2 app.apk    # 불완전 메서드까지
grep -rniE 'SecretKeySpec|addJavascriptInterface|"[A-Za-z0-9+/]{16,}="' out/sources
```

> **[그림 2]** 검색으로 찾은 하드코딩 키 문자열과 그 `Find Usage` 결과 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
// out/sources/com/example/Crypto.java
SecretKeySpec key = new SecretKeySpec("0123456789abcdef".getBytes(), "AES"); // 하드코딩 (C44)
```

## Root Cause — 왜 이렇게 되는가

근사 재구성인 이유는 DEX→Java가 다대일 매핑이 많아 완벽한 역변환이 불가능하기 때문이다(C13). 그래서 정적 결론은 항상 "재구성 모델" 위에서 내려야 한다. `--deobf`가 원본 이름을 복원하지 못하는 것은 R8/ProGuard가 의미 이름을 영구히 지웠기 때문이고, 그래서 실전에선 이름이 아니라 문자열 검색과 xref로 읽는다.

## 방어와 회귀 검증

- (개발자) 하드코딩 키 금지·Keystore 사용(C44), 불필요한 WebView `addJavascriptInterface` 제거. 릴리스 APK를 jadx로 떠 "하드코딩 키 문자열이 없다"를 회귀로.
- (연구자) 정적으로 못 본 것은 "안 봤다"로 남기고 동적으로 넘긴다.

**흔한 실패와 처리.** 메서드가 비어 보임 → `--show-bad-code`. 이름이 전부 a/b/c → R8 난독, 검색·xref 중심으로 전환. 클래스가 거의 없음 → 패커 의심, C14/동적으로.

## 버전 차이와 한계

- 플래그(`-d`·`--show-bad-code`·`--deobf`·`-e`)는 jadx 1.4.x/1.5.x에서 안정. Kotlin metadata 기반 변수명은 실험적·버전별 상이 → `jadx --version` 표기.
- 네이티브 `.so`는 jadx 범위 밖(→[21장 Ghidra](/posts/android-lab-p1c21-ghidra-rizin-native/)). 아키텍처 무관(데스크톱).

## 정리

- jadx 출력은 재구성 모델이다 — 실패 메서드는 `--show-bad-code`로.
- R8 앞에선 이름이 아니라 검색·xref.
- 코드가 거의 없으면 패커 → 동적 분석.

**점검 질문** — (1) `--deobf`가 원본 이름을 복원하지 못하는 이유는? (2) jadx에 코드가 거의 없을 때 의심할 것은? (3) 실패 메서드를 강제로 보려면?

**참고** — [jadx](https://github.com/skylot/jadx) · [R8 shrink](https://developer.android.com/build/shrink-code) · [C13](/posts/android-concept-atlas-c13-art-dex-oat-vdex/) · [C14](/posts/android-concept-atlas-c14-classloader-reflection/) · [C44](/posts/android-concept-atlas-c44-secure-storage-backup/)

*다음 글: [apktool과 smali로 편집·재조립](/posts/android-lab-p1c05-apktool-smali/).*
