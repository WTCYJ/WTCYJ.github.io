---
layout: post
title: "Ghidra·Rizin native 분석 — 스트립된 JNI를 정적으로 복원하기"
date: 2026-11-05 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, Ghidra, Rizin, NativeRE, JNI]
excerpt: "네이티브 .so는 DEX 밖이라 Ghidra/Rizin으로 본다. 심볼이 스트립됐어도 RegisterNatives의 JNINativeMethod 배열({name,signature,fnPtr} 24바이트)을 정적으로 걸어가면 'Java native 이름 ↔ 함수 주소' 매핑을 복원할 수 있다 — arm64에서 JNIEnv*는 x0, RegisterNatives는 함수테이블 인덱스 215(0x6B8)라 그 간접호출을 찾는 게 정석이다."
---

네이티브 코드는 DEX 밖이라 정적 jadx로는 안 보인다. Ghidra나 Rizin으로 `.so`를 분석하는데, 심볼이 스트립됐어도 방법이 있다 — RegisterNatives의 `JNINativeMethod` 배열을 정적으로 걸어가면 Java native 이름과 C 함수 주소의 매핑을 복원할 수 있다. 이 글은 `.so`를 Ghidra/Rizin으로 분석하고 스트립된 JNI 매핑을 정적으로 복원하는 방법을, 내 VR native 분석(tinyobjloader·IrfanView)의 정적 짝으로 정리한 기록이다.

> **한 줄 결론**: arm64에서 JNIEnv*는 x0, RegisterNatives는 함수테이블 인덱스 215(0x6B8)다. `JNI_OnLoad`에서 그 간접호출을 찾아 `JNINativeMethod[]`({name,signature,fnPtr} 24B)를 걸어가면 스트립 lib에서도 이름↔주소를 복원한다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글은 Ghidra/Rizin native RE와 정적 JNI 복원을 다룬다. 선수 개념은 [JNI 동적(10장)](/posts/android-lab-p1c10-jni-native-observation/)의 RegisterNatives 동적 관찰, [ELF·linker(C33)](/posts/android-concept-atlas-c33-elf-linker-plt-got/)의 `.so`·심볼, 내 VR 분석이다.

## 핵심 개념 — 도구와 JNI 매핑

- **추출**: `lib/<abi>/*.so`(arm64-v8a 우세)를 unzip. **ABI 일치 .so를 봐야**(arm64는 JNIEnv 오프셋 0x6B8, 32bit ARM은 0x35C). `Source-confirmed`
- **Ghidra**(NSA, 무료): 자동분석·P-code 디컴파일러·Symbol Tree·xref·Function Graph·Data Type Manager. 스크립팅 Java/Jython 기본, **CPython3는 11.3+ 번들 PyGhidra**(또는 Ghidrathon). JDK 요구는 버전별(`버전 확인 필요`). `Source-confirmed`
- **Rizin/Cutter**(r2 fork): `aaa`(분석)·`afl`(함수)·`pdf`(디스어셈블)·`pdc`(내장 pseudo-C)·`pdg`(rz-ghidra 디컴파일러)·ESIL. `Source-confirmed`
- **JNI 매핑(스트립)**: `JNI_OnLoad`(export, System.loadLibrary가 호출) → `RegisterNatives`(JNIEnv 인덱스 215, arm64 0x6B8 간접호출)의 `JNINativeMethod[]`(`{name,signature,fnPtr}`, 24B/64bit)를 정적으로 걸어 이름↔주소 복원. `Java_<pkg>_<Class>_<method>` 심볼 방식이면 **ART 런타임이 첫 호출 시 dlsym으로** 결정(ELF lazy binding 아님). `Source-confirmed`

**신뢰 경계와 위협 모델.** 정적 RE는 소유/교육용·공개 소스 대상. OLLVM(제어흐름 평탄화)·문자열 암호화·네이티브 패커는 정적을 저항하니 동적으로 피벗한다.

> **[그림 1]** Ghidra에서 `JNI_OnLoad` → `RegisterNatives` 호출을 찾고 `JNINativeMethod` 배열을 라벨링한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

자작 JNI lib(스트립·RegisterNatives)로 매핑 복원을 연습한 뒤, 내 VR 케이스(공개 소스)를 재현한다.

## 실습 절차와 관측

### 가설
스트립 lib이라 함수명이 없지만, RegisterNatives 배열을 걸어가면 `nativeCheck`↔주소가 복원된다. `Inferred`

### 절차
1. ABI 일치 .so를 추출한다.
2. Ghidra/Rizin으로 자동분석한다.
3. `JNI_OnLoad`에서 RegisterNatives 호출을 찾는다(0x6B8 간접호출).
4. 3번째 인자(배열)·4번째(count)로 24B 엔트리를 순회 → 이름/시그니처/주소를 라벨한다.
5. 그 주소를 10장 Frida로 후킹해 정적↔동적을 상관짓는다.

```bash
unzip app.apk 'lib/arm64-v8a/*.so' -d out
rizin out/lib/arm64-v8a/libfoo.so
# rizin> aaa; s sym.JNI_OnLoad; pdf; pdg
```

> **[그림 2]** Rizin `pdg`(rz-ghidra)로 `JNI_OnLoad`를 디컴파일해 RegisterNatives 배열이 보이는 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(교체):

```
JNI_OnLoad -> RegisterNatives(clazz, methods=0x..., count=3)
  [0] name="nativeCheck" sig="(I)Z" fn=0x1240
```

## Root Cause — 왜 이렇게 되는가

스트립 lib에서 매핑이 데이터로만 남는 것은 RegisterNatives가 런타임 등록이기 때문이다 — 그래서 그 배열이 정적 복원의 열쇠다. 정적/동적이 상보인 것은 각자 사각을 덮기 때문이고(정적은 전체 커버, 동적은 런타임 계산값·난독 우회), 신뢰할 만한 워크플로는 정적으로 매핑한 뒤 그 주소를 동적으로 후킹하는 것이다.

## 방어와 회귀 검증

- (개발자) 네이티브 난독은 지연일 뿐, 비밀은 서버·하드웨어(C40). 자작 lib에서 "복원 매핑 == 소스의 네이티브 메서드 집합"을 회귀로.
- (연구자) 메모리 버그는 8부 최소재현으로.

**흔한 실패와 처리.** 디컴파일 난독 → OLLVM, 동적/ESIL로. `pdg` 없음 → rz-ghidra 미설치. PAC 명령이 이상 → A15+ arm64 정상(PACIASP 등).

## 버전 차이와 한계

- Ghidra 11.x JDK·PyGhidra(11.3+), Rizin/Cutter 버전. arm64 16KB 페이지·PAC(A15+).
- arm64 .so 우선(내 완화 관측은 실기기). 상용 보호 lib은 허가 대상만.

## 정리

- ABI 일치 .so를 Ghidra/Rizin으로.
- 스트립 심볼은 RegisterNatives 배열로 정적 복원.
- 정적 매핑 → 동적 후킹이 신뢰 워크플로.

**점검 질문** — (1) 스트립 lib에서 JNI 매핑을 어떻게 정적 복원하나? (2) arm64와 32bit ARM의 JNIEnv 오프셋 차이는? (3) `Java_*` 심볼은 누가 언제 결정하나?

**참고** — [Ghidra](https://github.com/NationalSecurityAgency/ghidra) · [Rizin Book](https://book.rizin.re) · [JNI Tips](https://developer.android.com/training/articles/perf-jni) · [C33 ELF·linker](/posts/android-concept-atlas-c33-elf-linker-plt-got/)

*다음 글: [ASan/HWASan/UBSan JNI 오류 분석](/posts/android-lab-p1c22-sanitizer-jni-analysis/).*
