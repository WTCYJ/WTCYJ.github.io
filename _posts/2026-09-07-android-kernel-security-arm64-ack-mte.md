---
layout: post
title: "Android Kernel Security 02 - Android Common Kernel을 ARM64로 올리고, MTE 태그로 UAF를 잡다"
date: 2026-09-07
category: 시스템
author: WTCY
tags: [AndroidKernel, ACK, GKI, ARM64, MTE, KASAN, HW_TAGS, QEMU, UseAfterFree, 커널빌드, 학습기록]
excerpt: "지난 글에서 x86 제네릭 커널로 익힌 루프를, 이번엔 진짜 Android Common Kernel(android15-6.6) 소스를 받아 ARM64로 크로스빌드해 QEMU에 올렸습니다. 같은 use-after-free 드라이버를 다시 넣었더니, 이번엔 소프트웨어 섀도가 아니라 MTE 하드웨어 태그가 포인터 태그와 메모리 태그의 불일치로 잡아냈습니다. 실제 안드로이드 기기가 쓰는 바로 그 방식입니다."
---

> 환경 고지. 모든 실행은 제 WSL2 게스트 안에서만 했습니다. 대상은 공개된 Android Common Kernel 소스(android.googlesource.com/kernel/common, android15-6.6)를 직접 크로스빌드한 커널과, 제가 작성한 교육용 드라이버뿐입니다. 실기기나 부트로더는 건드리지 않았습니다. 그리고 정직하게 밝히면, 이건 `make` 기반의 소스 빌드이지 Kleaf/Bazel로 만드는 공식 GKI 아티팩트가 아닙니다. 크로스 컴파일러도 gcc라, CFI나 Shadow Call Stack 같은 clang 전용 하드닝은 이번엔 꺼져 있습니다.

[지난 글](/posts/android-kernel-security-qemu-kasan-kcov/)에서는 x86 제네릭 커널을 직접 빌드해 QEMU에 올리고, KASAN으로 use-after-free를 잡고, KCOV로 퍼징까지 한 바퀴를 돌렸습니다. 그런데 그 커널은 x86_64였고, KASAN도 소프트웨어 방식이었죠. 실제 Android 커널의 결은 거기서부터 갈라집니다. 아키텍처가 ARM64이고, 구조가 Android Common Kernel과 GKI이며, 요즘 기기의 KASAN은 소프트웨어 섀도가 아니라 하드웨어 메모리 태깅(MTE)을 씁니다. 이번엔 그 셋을 다 밟아보기로 했습니다.

## Android Common Kernel을 소스로 받는다

Android 커널이라고 별세계는 아닙니다. 뿌리는 리눅스 LTS이고, 거기에 Android 패치가 얹힌 것이 Android Common Kernel(ACK)입니다. 브랜치 이름이 계보를 그대로 말해줍니다. `android15-6.6`은 Android 15과 함께 나온, 6.6 LTS 기반 커널이라는 뜻입니다.

전체 AOSP나 Kleaf 빌드 환경은 디스크가 감당이 안 되니, 커널 소스만 단일 브랜치로 얕게 받습니다.

```console
$ git clone --depth 1 -b android15-6.6 https://android.googlesource.com/kernel/common ackarm64
$ cd ackarm64
$ make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- gki_defconfig
$ make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j$(nproc) Image modules
```

여기서 세 번 걸려 넘어졌는데, 셋 다 x86에서는 못 보던 ACK 특유의 벽이라 그대로 적어 둡니다.

첫째, 빌드가 엉뚱한 데서 멈췄습니다. 커널 코드가 아니라 호스트 도구인 `certs/extract-cert`가 `key_pass' undeclared`로 컴파일에 실패했습니다. GKI 설정이 신뢰 키링(trusted keyring) 도구를 끌어들이는데, 그게 요즘 배포판의 OpenSSL 3과 맞지 않아 생기는 문제입니다. 모듈 서명을 꺼도 이 도구는 여전히 빌드되려 하더군요. 랩 커널에는 신뢰 키링이 필요 없으니 `SYSTEM_TRUSTED_KEYRING`과 취소 목록, `IKHEADERS`를 꺼서 아예 이 경로를 지웠습니다.

둘째, 내 드라이버를 외부 모듈로 빌드하는데 이번엔 경고 하나가 빌드를 죽였습니다.

```console
aasbug.c: error: this 'if' clause does not guard... [-Werror=misleading-indentation]
```

GKI는 `-Werror`로 빌드해서, x86에서는 그냥 넘어가던 들여쓰기 경고가 여기서는 곧 에러입니다. `if (...) return;`을 한 줄에 몰아 쓴 게 문제였고, 커널 코딩 스타일대로 줄을 나누자 통과했습니다. 사소하지만, 대상 커널의 빌드 엄격도가 다르면 같은 코드도 다르게 취급된다는 걸 몸으로 배웁니다.

셋째는 조금 더 흥미로운 벽이었는데, 뒤에서 따로 다룹니다.

## 부팅, 그리고 아키텍처가 바뀌었다는 증거

크로스아키텍처라 KVM 가속은 못 씁니다(호스트가 x86이니 ARM64 게스트는 순수 에뮬레이션입니다). 그래서 부팅이 느리지만, 도는 건 확실히 돕니다. busybox가 x86이라 못 쓰니, 관찰용 `/init`을 arm64 정적 바이너리로 하나 만들어 넣었습니다.

```console
=== ARM64 ACK BOOT ===
uname: Linux 6.6.142-4k-ge19fb465168c (aarch64)
version: Linux version 6.6.142-4k-ge19fb465168c ... aarch64-linux-gnu-gcc ... #1 SMP PREEMPT
--- arm64 syscall symbols ---
ffffffe2b2fa9300 T __arm64_sys_openat
ffffffe2b2fa93ac T __arm64_sys_openat2
```

`aarch64`, 그리고 버전 문자열의 `6.6.142-...-android15`가 이게 진짜 Android Common Kernel임을 말해줍니다. 심볼 이름도 바뀌었습니다. x86에서 `__x64_sys_openat`이던 것이 여기서는 `__arm64_sys_openat`입니다. 같은 openat 시스템콜인데, 유저에서 커널로 넘어가는 관문이 아키텍처마다 다르기 때문입니다.

<svg viewBox="0 0 720 170" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="x86와 arm64의 syscall 진입 대비">
  <g font-family="monospace" font-size="12" fill="currentColor">
    <text x="10" y="20" fill-opacity="0.7">x86_64</text>
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="10" y="30" width="150" height="28" rx="5"/><rect x="210" y="30" width="120" height="28" rx="5"/><rect x="380" y="30" width="230" height="28" rx="5"/>
    </g>
    <g text-anchor="middle"><text x="85" y="48">유저(ring3)</text><text x="270" y="48">syscall 명령</text><text x="495" y="48">__x64_sys_openat</text></g>
    <text x="10" y="100" fill-opacity="0.7">arm64</text>
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="10" y="110" width="150" height="28" rx="5"/><rect x="210" y="110" width="120" height="28" rx="5"/><rect x="380" y="110" width="230" height="28" rx="5"/>
    </g>
    <g text-anchor="middle"><text x="85" y="128">유저(EL0)</text><text x="270" y="128">svc → EL1</text><text x="495" y="128">__arm64_sys_openat</text></g>
    <g stroke="currentColor" fill="none"><path d="M160 44 h50"/><path d="M330 44 h50"/><path d="M160 124 h50"/><path d="M330 124 h50"/></g>
    <text x="10" y="162" fill-opacity="0.7">같은 openat, 다른 관문: 명령(syscall vs svc)도 특권 레벨 표기(ring vs EL)도 심볼 이름도 다르다.</text>
  </g>
</svg>

## 같은 버그, 다른 잡는 법

여기서부터가 이 글의 핵심입니다. 지난번 x86에서 쓴 use-after-free 드라이버를 그대로 arm64로 옮겨 넣었습니다. open에서 버퍼를 할당하고, write에서 해제하되 포인터는 그대로 두고, read에서 그 포인터를 다시 읽는 그 드라이버요. 같은 순서로 트리거를 돌렸습니다.

그런데 리포트가 x86과 달랐습니다.

```console
[    3.520674] aasbug(arm64): loaded
[    3.531775] BUG: KASAN: invalid-access in aas_read+0x64/0x140 [aasbug]
[    3.533795] Pointer tag: [f9], memory tag: [fe]
[    3.539378]  kasan_report+0x84/0xb0
[    3.539378]  do_tag_check_fault+0x78/0x8c
[    3.540894]  aas_read+0x64/0x140 [aasbug]
[    3.542287]  __arm64_sys_read+0x1c/0x28
[    3.545955] The buggy address belongs to the object at ffffff80034751c0
[    3.545955]  which belongs to the cache kmalloc-64 of size 64
```

`slab-use-after-free`가 아니라 `invalid-access`, 그리고 `Pointer tag: [f9], memory tag: [fe]`라는 낯선 줄. 이게 MTE, 메모리 태깅 익스텐션입니다.

지난 글의 x86 KASAN은 소프트웨어 방식이었습니다. 컴파일러가 모든 메모리 접근 앞에 검사 코드를 심고, 별도의 섀도 메모리에 "이 바이트가 유효한가"를 기록해두고 대조합니다. 반면 ARM64의 하드웨어 태그 KASAN은 컴퓨터의 도움을 받습니다. 할당된 메모리 한 덩어리마다 4비트 태그를 붙이고, 그 메모리를 가리키는 포인터의 상위 비트에도 같은 태그를 넣습니다. 접근할 때마다 CPU가 포인터의 태그와 메모리의 태그를 하드웨어로 비교해서, 다르면 그 자리에서 폴트를 냅니다.

use-after-free가 왜 잡히는지가 여기서 선명해집니다. 해제하는 순간 그 메모리에는 새 태그가 매겨지는데, 이미 나가 있던 포인터는 옛 태그를 그대로 들고 있습니다. 그래서 그 포인터로 다시 접근하면 태그가 어긋나고, CPU가 즉시 잡습니다. 리포트의 `Pointer tag [f9]`가 옛 포인터의 태그, `memory tag [fe]`가 해제 후 다시 매겨진 메모리의 태그입니다. 둘이 다르니 `do_tag_check_fault`가 울린 것이죠.

<svg viewBox="0 0 720 180" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="MTE 태그로 use-after-free를 잡는 원리">
  <g font-family="monospace" font-size="12" fill="currentColor" text-anchor="middle">
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="20"  y="40" width="200" height="60" rx="6"/>
      <rect x="260" y="40" width="200" height="60" rx="6"/>
      <rect x="500" y="40" width="200" height="60" rx="6"/>
    </g>
    <text x="120" y="30">할당(open)</text>
    <text x="360" y="30">해제(write)</text>
    <text x="600" y="30">재사용(read)</text>
    <text x="120" y="66">포인터 태그 f9</text><text x="120" y="86">메모리 태그 f9  ✓</text>
    <text x="360" y="66">포인터 태그 f9</text><text x="360" y="86">메모리 태그 → fe</text>
    <text x="600" y="66">포인터 f9 ≠ 메모리 fe</text><text x="600" y="86">태그 불일치 → 폴트</text>
    <g stroke="currentColor" fill="none"><path d="M220 70 h40"/><path d="M460 70 h40"/></g>
    <text x="360" y="140" fill-opacity="0.7">해제하면 메모리 태그만 바뀌고, 나가 있던 포인터는 옛 태그를 그대로 든다.</text>
    <text x="360" y="158" fill-opacity="0.7">그 포인터로 접근하는 순간 CPU가 하드웨어로 불일치를 잡는다.</text>
  </g>
</svg>

세 번째로 걸렸던 벽이 바로 이 MTE였습니다. Android GKI 설정은 KASAN을 소프트웨어가 아니라 이 하드웨어 태그 방식으로 기본 선택합니다. 그런데 MTE는 CPU가 지원해야 도는 기능이라, 처음에 평범한 에뮬레이션 CPU로 부팅했더니 KASAN이 켜져 있는데도 아무것도 잡지 못했습니다. MTE 없는 CPU에서는 태그 검사가 그냥 무력해지는 것이죠. QEMU에 MTE를 지원하는 CPU를 주고 커널에 동기 모드를 켜라고 하자, 비로소 부팅 로그에 이렇게 떴습니다.

```console
CPU features: detected: Memory Tagging Extension
MTE: enabled in synchronous mode at EL1
kasan: KernelAddressSanitizer initialized (hw-tags, mode=sync, ...)
```

그러고 나서야 위의 태그 불일치 리포트가 나왔습니다. 소프트웨어 KASAN은 아무 CPU에서나 돌지만, 하드웨어 태그 KASAN은 그걸 받쳐줄 하드웨어가 있어야 의미가 생긴다는 걸, 켜고 끄며 확인한 셈입니다.

## 무엇이 남나

이번에 확인한 건 결국 하나입니다. 커널 보안의 기본 루프(빌드, 부팅, 계측, crash, 원인)는 아키텍처가 바뀌어도 그대로 옮겨간다는 것. 다만 각 단계의 구체가 달라집니다. 심볼 이름이 바뀌고, 특권 레벨의 이름이 바뀌고, 무엇보다 버그를 잡는 장치가 소프트웨어 섀도에서 하드웨어 태그로 바뀝니다. 그리고 그 하드웨어 태그 방식이야말로 요즘 실제 안드로이드 기기가 커널 메모리 버그를 방어하는 방식입니다.

한계도 다시 적어 둡니다. 이건 ACK 소스를 `make`로 빌드한 것이지 공식 GKI 아티팩트가 아니고, gcc 빌드라 CFI와 Shadow Call Stack은 꺼져 있습니다. 다음 글에서는 clang/LLVM 툴체인으로 넘어가 그 두 하드닝을 실제로 켜서 관측하고, KCOV 퍼저를 syzkaller로 확장하는 쪽으로 가볼 생각입니다.

## 참고

- The Linux Kernel documentation — [Hardware tag-based KASAN](https://docs.kernel.org/dev-tools/kasan.html)
- ARM — [Memory Tagging Extension 개요](https://developer.arm.com/documentation/108035/latest/)
- Android Open Source Project — [Generic Kernel Image (GKI)](https://source.android.com/docs/core/architecture/kernel/generic-kernel-image)
- QEMU documentation — [Arm ‘virt’ 머신과 MTE](https://www.qemu.org/docs/master/system/arm/virt.html)
