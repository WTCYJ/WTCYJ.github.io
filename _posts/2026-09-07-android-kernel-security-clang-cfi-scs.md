---
layout: post
title: "Android Kernel Security 03 - clang으로 다시 빌드해 CFI와 SCS를 켜고, 정말 도는지 확인하다"
date: 2026-09-07 09:00:00 +0900
category: 시스템
author: WTCY
tags: [AndroidKernel, ACK, ARM64, clang, LLVM, KCFI, CFI, ShadowCallStack, DynamicSCS, PAC, 커널하드닝, 학습기록]
excerpt: "지난 글의 ARM64 커널은 gcc로 빌드해서 CFI와 SCS가 꺼져 있었습니다. 이번엔 clang/LLVM로 다시 빌드해 둘을 켰습니다. 타입이 안 맞는 함수 포인터 호출로 KCFI가 실제로 패닉을 내는 걸 확인했고, SCS는 처음 해석이 틀렸다가 검증으로 바로잡았습니다. config에 y가 적혀 있다고 그 방어가 런타임에 도는 건 아니라는 걸, 특히 하드웨어에 기대는 기능에서 배웠습니다."
---

> 환경 고지. 모든 실행은 제 WSL2 게스트 안에서만 했고, 대상은 공개 Android Common Kernel(android15-6.6)을 직접 크로스빌드한 커널과 제가 쓴 교육용 모듈뿐입니다. 실기기는 없습니다. 여전히 `make` 기반 소스 빌드이지 Kleaf 공식 GKI 아티팩트는 아닙니다. 다만 이번엔 gcc가 아니라 clang/LLVM 툴체인으로 빌드했습니다.

[02편](/posts/android-kernel-security-arm64-ack-mte/)에서 Android Common Kernel을 ARM64로 올렸지만, 그때는 gcc로 빌드한 탓에 CFI와 Shadow Call Stack이 꺼져 있었습니다. 이 둘은 clang 전용 기능이라, gcc 빌드에서는 `make`가 설정을 자동으로 꺼 버립니다. 그래서 이번엔 clang/LLVM 툴체인으로 같은 커널을 다시 빌드해 둘을 켜기로 했습니다.

`LLVM=1` 빌드에는 링커로 `ld.lld`가 필요합니다. 그것만 설치하고, `gki_defconfig`가 원래 켜 두는 `CONFIG_CFI_CLANG`과 `CONFIG_SHADOW_CALL_STACK`을 그대로 살린 채(그리고 위반 시 경고가 아니라 패닉하도록 `CONFIG_CFI_PERMISSIVE`는 꺼서) 빌드했습니다.

```console
$ make ARCH=arm64 LLVM=1 gki_defconfig
$ make ARCH=arm64 LLVM=1 -j$(nproc) Image modules
$ grep -E 'CFI_CLANG|SHADOW_CALL_STACK|DYNAMIC_SCS' .config
CONFIG_CFI_CLANG=y
CONFIG_SHADOW_CALL_STACK=y
CONFIG_DYNAMIC_SCS=y
```

여기서부터가 이 글의 두 이야기입니다. 하나는 잘 풀렸고(CFI), 하나는 제가 처음에 틀렸습니다(SCS).

## CFI - 타입이 안 맞는 호출을 그 자리에서 막는다

커널 CFI(Control Flow Integrity)는 요즘 KCFI라는 방식으로 구현됩니다. 원리는 이렇습니다. 함수마다 그 시그니처(예: `void(void)`, `int(int)`)를 해시한 타입 식별자를 함수 바로 앞 4바이트에 심어 둡니다. 그리고 함수 포인터로 간접 호출을 할 때마다, 호출하는 쪽이 기대하는 타입 식별자와 실제 대상 함수의 타입 식별자를 비교합니다. 다르면 그 자리에서 트랩을 걸어 버립니다. 정상 코드에서는 타입이 늘 맞으니 조용하고, 공격자가 함수 포인터를 엉뚱한 함수로 덮어써서 흐름을 바꾸려 하면 타입이 어긋나 걸립니다.

이걸 눈으로 보려고, 일부러 타입을 어긋나게 부르는 모듈을 만들었습니다. `int`를 반환하는 함수를 `void(void)` 포인터로 부르는 겁니다.

```c
static int real_func(int x) { return x + 1; }   /* 타입: int(int) */
typedef void (*wrong_fn)(void);                   /* 타입: void(void) */
static volatile wrong_fn gf;                      /* volatile: 진짜 간접 호출 */
static int __init m_init(void)
{
	gf = (wrong_fn)(void *)real_func;
	gf();                                         /* 여기서 타입 불일치 */
	return 0;
}
```

`volatile`을 쓴 건 컴파일러가 캐스팅을 꿰뚫어 보고 직접 호출로 최적화하는 걸 막아, 진짜 간접 호출이 남게 하려는 것입니다. 컴파일된 모듈을 디스어셈블해 보면, 간접 호출 앞에 KCFI 검사가 그대로 박혀 있습니다.

```console
34: ldur w16, [x8, #-0x4]        ; 대상 함수 4바이트 앞의 타입 식별자를 읽는다
38: movk w17, #0x670c            ; 기대 타입 식별자 0xa540670c 를
3c: movk w17, #0xa540, lsl #16   ; 두 조각으로 만든다
40: cmp  w16, w17                ; 실제 vs 기대 비교
44: b.eq +8                      ; 같으면 통과
48: brk  #0x8228                 ; 다르면 트랩
4c: blr  x8                      ; 실제 간접 호출
```

<svg viewBox="0 0 700 150" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="KCFI 타입 검사 흐름">
  <g font-family="monospace" font-size="12" fill="currentColor" text-anchor="middle">
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="20" y="30" width="180" height="30" rx="5"/>
      <rect x="270" y="30" width="180" height="30" rx="5"/>
      <rect x="520" y="10" width="160" height="30" rx="5"/>
      <rect x="520" y="70" width="160" height="30" rx="5"/>
    </g>
    <text x="110" y="49">간접 호출 직전</text>
    <text x="360" y="49">타입 식별자 비교</text>
    <text x="600" y="29">같음 → blr(호출)</text>
    <text x="600" y="89">다름 → brk(트랩→패닉)</text>
    <g stroke="currentColor" fill="none">
      <path d="M200 45 h70"/><path d="M450 40 L520 25"/><path d="M450 50 L520 85"/>
    </g>
    <text x="360" y="130" fill-opacity="0.7">함수 앞 4바이트의 타입 해시가 어긋나면, 실제 호출(blr)에 닿기 전에 막는다.</text>
  </g>
</svg>

부팅해서 이 모듈을 올리자, 정확히 그 검사가 걸렸습니다.

```console
CFI failure at init_module+0x44 [aascfi] (target: real_func+0x0; expected type: 0xa540670c)
Internal error: Oops - CFI: 00000000f2008228 [#1]
Call trace: init_module <- __arm64_sys_finit_module
Kernel panic - not syncing: Oops - CFI: Fatal exception
```

리포트의 기대 타입 `0xa540670c`가 디스어셈블의 그 값과 같고, 오류 코드 `0xf2008228`의 끝자리가 트랩 명령 `brk #0x8228`과 맞아떨어집니다. `CFI_PERMISSIVE`를 껐으니 경고로 넘어가지 않고 커널이 패닉합니다. 타입이 어긋난 간접 호출이 실제 대상에 닿기 전에 죽은 겁니다. CFI는 이렇게, 정적 디스어셈블과 런타임 패닉 양쪽에서 깔끔하게 확인됩니다.

## SCS - 여기서 나는 처음에 틀렸다

Shadow Call Stack은 반환 주소를 일반 스택이 아니라 별도의 보호된 스택(ARM64에서는 x18 레지스터가 가리키는 곳)에 따로 보관해서, 스택 버퍼 오버플로로 반환 주소를 덮어써도 흐름을 못 바꾸게 하는 방어입니다.

그래서 저는 모듈 함수의 디스어셈블에서 x18에 반환 주소를 넣고 빼는 명령(`str x30, [x18], #8` / `ldr x30, [x18, #-8]`)이 보일 거라 예상했습니다. 그런데 아무리 찾아도 x18은 한 번도 나오지 않았습니다. 대신 프롤로그에는 `paciasp`, 에필로그에는 `autiasp`가 있었습니다. 이건 SCS가 아니라 PAC, 포인터 인증으로 반환 주소를 서명하는 다른 방어입니다.

처음엔 이렇게 생각했습니다. "`DYNAMIC_SCS`니까, PAC 명령을 자리표시로 컴파일해 두고 로드할 때 x18 SCS로 바꿔치기하는 거겠지. 그리고 PAC도 함께 서명하겠지." 반은 맞고 반은 틀린 생각이었습니다. 이 해석을 그대로 믿지 않으려고, 서로 다른 시각의 검토자들에게 이 증거를 던지고 반박해 보게 했더니, 세 검토자가 한목소리로 제 SCS 설명을 반박했습니다. 정리하면 이렇습니다.

`DYNAMIC_SCS`에서 PAC 프롤로그를 x18 SCS로 바꿔치기하는 건 맞습니다. 그런데 그건 **PAC 하드웨어가 없는 CPU에서만** 일어납니다. 커널은 로드 시점에 현재 CPU가 포인터 인증을 지원하는지 보고, 지원하면 `paciasp`를 그대로 둬서 PAC로 반환 주소를 보호하고, 지원하지 않을 때만 그 자리를 x18 SCS 밀어넣기로 덮어씁니다. 즉 PAC와 SCS는 같은 자리표시를 공유하는 **둘 중 하나**이지, 동시에 겹쳐 쓰는 게 아닙니다. "PAC도 함께 서명한다"는 제 말은 틀렸습니다.

그리고 더 중요한 것. 컴파일된 파일에 `paciasp`만 있고 x18이 없다는 사실만으로는 SCS가 실제로 도는지 증명되지 않습니다. 그 파일은 로드 전의 모습일 뿐이고, 실제로 무엇이 되는지는 부팅하는 CPU에 달렸습니다.

## 그래서 직접 부팅해서 확인했다

말로 정리하는 대신 부팅해서 봤습니다. 자기 함수의 첫 명령어를 런타임에 읽어 찍는 모듈을 만들어, 하나는 PAC가 없는 CPU로, 하나는 PAC가 있는 CPU로 올려 봤습니다.

```console
[cortex-a57, PAC 없음]  victim[0] = 0xf800865e   -> str x30, [x18], #8  (SCS 밀어넣기)
[cpu max,   PAC 있음]   victim[0] = 0xd503233f   -> paciasp             (PAC 그대로)
```

같은 모듈 파일인데, PAC 없는 CPU에서는 커널이 로드하면서 프롤로그를 x18 SCS로 바꿔치기했고, PAC 있는 CPU에서는 `paciasp`를 그대로 뒀습니다. 파일 안의 프롤로그는 두 경우 다 `paciasp`로 똑같습니다. 무엇이 반환 주소를 지키는지는 부팅해 봐야 비로소 갈립니다.

<svg viewBox="0 0 700 200" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="dynamic SCS가 CPU에 따라 갈리는 방식">
  <g font-family="monospace" font-size="12" fill="currentColor" text-anchor="middle">
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06"><rect x="250" y="15" width="200" height="34" rx="6"/></g>
    <text x="350" y="37">컴파일된 프롤로그: paciasp</text>
    <text x="350" y="80" fill-opacity="0.85">로드 시, 이 CPU에 PAC가 있나?</text>
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="60" y="120" width="250" height="56" rx="6"/>
      <rect x="390" y="120" width="250" height="56" rx="6"/>
    </g>
    <text x="185" y="142">있음 → paciasp 유지</text>
    <text x="185" y="162" fill-opacity="0.75">PAC가 반환 주소 서명</text>
    <text x="515" y="142">없음 → x18로 패치</text>
    <text x="515" y="162" fill-opacity="0.75">SCS 섀도 스택 사용</text>
    <g stroke="currentColor" fill="none">
      <path d="M350 49 V70"/><path d="M350 92 L185 120"/><path d="M350 92 L515 120"/>
    </g>
    <text x="350" y="195" fill-opacity="0.7">둘은 상호배타. 파일만 봐선 못 가리고, 부팅한 CPU가 정한다.</text>
  </g>
</svg>

## 남는 것

이번에 진짜로 배운 건 CFI나 SCS의 세부보다, 그 위의 한 가지였습니다. 설정 파일에 `CONFIG_..._=y`가 적혀 있다고 그 방어가 런타임에 실제로 작동하는 건 아니라는 것. CFI처럼 컴파일 시점에 코드에 박히는 방어는 디스어셈블로 바로 확인되지만, SCS처럼 하드웨어(여기서는 PAC 유무)에 기대어 로드 시점에 결정되는 방어는, 그 하드웨어와 그 순간까지 가 봐야 무엇이 켜졌는지 알 수 있습니다. 그래서 "켰다"고 말하려면 config가 아니라 런타임을 봐야 합니다.

한 가지 더. 제 첫 SCS 해석은 틀렸고, 그걸 스스로 우기지 않고 반박에 부친 덕에 바로잡았습니다. 방어를 분석할 때 가장 위험한 건 그럴듯한 오해를 검증 없이 확신하는 것이더군요.

다음 글에서는 지금까지 만든 KCOV 퍼징 타깃을 syzkaller에 연결해, 커버리지 안내 퍼징을 제대로 된 규모로 돌려 볼 생각입니다.

## 참고

- Android Open Source Project — [Kernel Control Flow Integrity (KCFI)](https://source.android.com/docs/security/test/kcfi)
- The Linux Kernel documentation — [Shadow Call Stack](https://docs.kernel.org/arch/arm64/shadow-call-stack.html)
- The Linux Kernel documentation — [Pointer Authentication (PAC)](https://docs.kernel.org/arch/arm64/pointer-authentication.html)
- Android Open Source Project — [Control Flow Integrity와 커널 하드닝](https://source.android.com/docs/security/test)
