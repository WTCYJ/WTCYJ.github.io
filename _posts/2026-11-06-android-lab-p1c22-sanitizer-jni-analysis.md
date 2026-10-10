---
layout: post
title: "ASan·HWASan·UBSan JNI 오류 분석 — 리포트 읽는 법"
date: 2026-11-06 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, ASan, HWASan, UBSan, JNI]
excerpt: "네이티브 JNI 메모리 버그는 새니타이저로 잡는다 — ASan은 1/8 섀도+리드존+격리로 OOB/UAF를, HWASan은 arm64 상위바이트 태그로, UBSan은 정수 오버플로를 탐지한다. 이건 테스트/디버그 도구지 프로덕션이 아니고(유저 폰엔 MTE·최소 IntSan만), ASan 리포트의 섀도 바이트(fa=리드존·fd=freed·f7=user-poisoned)를 읽는 법이 핵심이다."
---

네이티브 JNI 메모리 버그는 새니타이저로 잡는다. ASan은 OOB/UAF를, HWASan은 태그로, UBSan은 정수 오버플로를 탐지한다. 중요한 것은 이것이 테스트/디버그 도구지 프로덕션 완화가 아니라는 점(유저 폰엔 MTE·최소 IntSan만)과, ASan 리포트를 정확히 읽는 법이다. 이 글은 JNI 하네스에 새니타이저를 걸어 메모리/정수 버그를 탐지하고 리포트를 판독하는 방법을, 내 미디어 정수결함(UBSan 타깃)과 VR native OOB를 배경으로 정리한 기록이다.

> **한 줄 결론**: ASan은 1/8 섀도+리드존+격리로 OOB/UAF를 결정적으로 잡고, UBSan은 정수 오버플로를 abort시킨다. 리포트의 섀도 바이트(fa=리드존·fd=freed·f7=user-poisoned)를 읽고, UAF는 free 스택이 먼저 나온다. 이들은 탐지기지 프로덕션 완화가 아니다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 JNI 네이티브의 새니타이저 오류 분석을 다룬다. 선수 개념은 [새니타이저(C38)](/posts/android-concept-atlas-c38-sanitizers/)의 탐지기 vs 장벽, [native RE(21장)](/posts/android-lab-p1c21-ghidra-rizin-native/)의 버그 위치, 내 퍼징(afl)·VR native 작업이다.

## 핵심 개념 — 탐지기와 리포트

- **탐지기(테스트/디버그, C38)**: ASan(-fsanitize=address, 1/8 섀도+리드존+격리, heap/stack/global OOB·UAF·UAR·double-free, **~2배 CPU/~2배 메모리**), HWASan(arm64 TBI 상위바이트 태그, 16B 그래뉼, ~1/16 섀도, 확률적), UBSan(정수 오버플로·시프트·정렬·경계 — 내 미디어 정수결함 타깃). `Source-confirmed`
- **활성화**: `Android.bp`의 `sanitize:{address:true}`/`{hwaddress:true}`, 설치 앱은 APK의 **`wrap.sh`**로 ASan 런타임(`libclang_rt.asan-*-android.so`, NDK) preload. HWASan은 arm64 + **`_hwasan` userdebug 이미지**(A10+). `Source-confirmed`
- **리포트 판독**: 에러 유형(heap-buffer-overflow), faulting access(READ/WRITE size N), **UAF는 free 스택 먼저·이어 alloc 스택**, 섀도 바이트(1바이트=8앱바이트; **fa=heap 리드존(좌·우 공용)·fd=freed·f7=user-poisoned**). 심볼라이즈는 NDK `llvm-symbolizer`/`ndk-stack`. `Source-confirmed`

**신뢰 경계와 위협 모델.** 탐지기는 출시 전 버그를 잡는 도구다 — 유저 폰엔 MTE·최소 IntSan만(C38). 자작 하네스/앱에서 쓴다.

> **[그림 1]** 자작 하네스에서 heap OOB로 ASan `heap-buffer-overflow` 리포트가 뜬 콘솔 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 JNI 하네스에 의도적 OOB/UAF/정수결함을 넣어 ASan/HWASan/UBSan으로 각각 탐지·리포트 판독한다.

## 실습 절차와 관측

### 가설
의도적 heap OOB는 ASan `heap-buffer-overflow` + 리드존 섀도(fa), 정수 오버플로는 UBSan이 abort. `Inferred`

### 절차
1. 자작 하네스를 ASan 빌드(또는 wrap.sh)한다.
2. 버그 입력으로 크래시 → ASan 리포트를 캡처한다.
3. `ndk-stack`으로 심볼라이즈한다.
4. 섀도 바이트로 리드존/freed를 판정한다.
5. HWASan(arm64)·UBSan으로 재확인한다.

```bash
# 자작 하네스를 ASan으로 빌드하거나 wrap.sh로 런타임 preload
adb logcat | ndk-stack -sym out/obj/local/arm64-v8a
```

> **[그림 2]** UBSan이 미디어 정수 오버플로 지점에서 abort한 리포트 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
==ERROR: AddressSanitizer: heap-buffer-overflow ... WRITE of size 4
  #0 parseLine ...
freed by thread T0 here: ...       # UAF면 free 스택이 먼저
Shadow bytes: ...[fa]fa fa         # fa = heap 리드존
```

## Root Cause — 왜 이렇게 되는가

ASan이 인접 OOB를 결정적으로 잡는 것은 리드존, UAF는 격리 때문이다(C38). "탐지기"인 이유는 계측 오버헤드가 커 배포가 불가하기 때문이고 — 유저 폰은 하드웨어 후계자인 MTE가 그 역할을 한다. UAF 리포트에서 free 스택이 먼저 나오는 것은 "무엇이 이미 해제됐나"가 진단의 출발점이기 때문이다.

## 방어와 회귀 검증

- (개발자) CI에 ASan/UBSan, 프로덕션엔 MTE·최소 IntSan(C38). 수정 후 같은 입력에서 ASan 무보고를 회귀로(회귀 코퍼스에 PoC 포함).
- (연구자) 버그는 최소재현·정직 스코핑(8부).

**흔한 실패와 처리.** HWASan 미동작 → x86_64면 arm64/_hwasan 이미지로. 심볼 없음 → `ndk-stack -sym`. 런타임 로드 실패 → wrap.sh/ASan .so 경로 확인.

## 버전 차이와 한계

- HWASan _hwasan A10+, UBSan 미디어 IntSan A7 도입·A9 확장(C38).
- HWASan은 arm64 전용. 실제 프로덕션 완화(MTE)는 Pixel 8+ 실기기.

## 정리

- ASan=리드존/격리(OOB/UAF), HWASan=태그, UBSan=정수.
- 섀도 fa/fd/f7과 UAF의 free-먼저를 읽는다.
- 이들은 탐지기지 프로덕션 완화가 아니다.

**점검 질문** — (1) ASan 섀도 바이트 fa/fd/f7의 의미는? (2) UAF 리포트에서 어느 스택이 먼저 나오나? (3) 이 도구들이 프로덕션에 안 실리는 이유는?

**참고** — [HWASan](https://source.android.com/docs/security/test/hwasan) · [memory-safety](https://source.android.com/docs/security/test/memory-safety) · [ASan](https://clang.llvm.org/docs/AddressSanitizer.html) · [C38 새니타이저](/posts/android-concept-atlas-c38-sanitizers/)

*다음 글: [Flutter·React Native·Cordova 구조 비교](/posts/android-lab-p1c23-flutter-reactnative-cordova/).*
