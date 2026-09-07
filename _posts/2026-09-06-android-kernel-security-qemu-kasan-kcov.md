---
layout: post
title: "Android Kernel Security 01 - QEMU에 내 커널을 올리고 KASAN·KCOV로 버그를 잡다"
date: 2026-09-06
category: 시스템
author: WTCY
tags: [AndroidKernel, LinuxKernel, QEMU, KVM, WSL2, KASAN, KCOV, UseAfterFree, 커널퍼징, 커널빌드, 학습기록]
excerpt: "개념으로만 알던 커널 보안을 손으로 돌려봤습니다. WSL2 안에서 커널을 직접 빌드해 QEMU-KVM으로 부팅하고, 첫 커널 모듈을 올리고, KASAN으로 use-after-free를 잡아 근본 원인까지 따라간 다음 고쳐서 회귀를 확인하고, 마지막엔 KCOV 커버리지로 안내되는 작은 퍼저가 스스로 heap out-of-bounds를 찾아내게 했습니다. 모든 로그는 제 랩에서 실제로 나온 출력입니다."
---

> 환경 고지. 이 글의 모든 실행은 제 PC의 WSL2 게스트(Ubuntu 24.04.4) 안에서만 했습니다. 대상은 제가 직접 빌드한 리눅스 v6.6 커널과 제가 작성한 교육용 드라이버뿐이고, 실기기나 남의 시스템은 건드리지 않았습니다. 취약점은 전부 제가 일부러 심은 것이며, 완성형 익스플로잇이 아니라 crash와 근본 원인, 패치까지만 다룹니다. 그리고 정직하게 밝히면, 이번 커널은 x86_64 제네릭 커널입니다. ARM64와 Android Common Kernel(GKI/KMI)로 넘어가는 건 다음 글의 몫입니다.

커널 보안 공부를 하면서 계속 걸리던 게 있었습니다. GKI가 뭔지, KASAN이 어떤 버그를 잡는지, use-after-free가 왜 위험한지는 글로 여러 번 읽었는데, 정작 커널을 직접 빌드해서 부팅하고, 계측을 켜서 crash를 내 눈으로 본 적은 없었다는 것이죠. 읽어서 아는 것과 손으로 아는 것 사이에는 늘 간극이 있습니다. 이번엔 그 간극을 메우기로 했습니다.

목표는 단순합니다. 커널을 하나 빌드해서 가상 머신에 올리고, 그 위에서 다음 한 바퀴를 직접 돌려보는 것.

<svg viewBox="0 0 760 90" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="커널 랩 루프">
  <g fill="currentColor" font-family="monospace" font-size="12" text-anchor="middle">
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="6"   y="30" width="86" height="30" rx="5"/>
      <rect x="116" y="30" width="86" height="30" rx="5"/>
      <rect x="226" y="30" width="96" height="30" rx="5"/>
      <rect x="346" y="30" width="96" height="30" rx="5"/>
      <rect x="466" y="30" width="86" height="30" rx="5"/>
      <rect x="576" y="30" width="76" height="30" rx="5"/>
      <rect x="676" y="30" width="78" height="30" rx="5"/>
    </g>
    <text x="49"  y="49">소스</text>
    <text x="159" y="49">빌드</text>
    <text x="274" y="49">QEMU 부팅</text>
    <text x="394" y="49">KASAN/KCOV</text>
    <text x="509" y="49">crash</text>
    <text x="614" y="49">RCA·패치</text>
    <text x="715" y="49">회귀</text>
    <g stroke="currentColor" fill="none">
      <path d="M92 45 h24"/><path d="M202 45 h24"/><path d="M322 45 h24"/>
      <path d="M442 45 h24"/><path d="M552 45 h24"/><path d="M652 45 h24"/>
    </g>
  </g>
</svg>

## 랩을 세운다

무거운 걸 받지 않는 게 원칙이었습니다. 전체 AOSP나 Cuttlefish는 디스크가 감당이 안 되고(제 노트북은 실질 여유가 60GB가 채 안 됩니다), 사실 커널 빌드·부팅의 기본기를 익히는 데는 필요하지도 않습니다. 그래서 스테이블 커널 하나를 단일 브랜치로 얕게 받아서 씁니다.

```console
$ git clone --depth 1 --branch v6.6 https://github.com/torvalds/linux.git
$ cd linux && make defconfig && make -j$(nproc) bzImage
Kernel: arch/x86/boot/bzImage is ready
```

루트 파일시스템은 busybox 하나로 만든 초기 램디스크면 충분합니다. 부팅해서 셸이 뜨는 것만 확인하면 되니까요. QEMU를 KVM 가속으로 띄우고, 우리가 만든 `/init`이 실행되는지 봅니다.

```console
[    0.000000] Linux version 6.6.0 (yejun@yejunhc) ... KST 2026
[    0.000000] Hypervisor detected: KVM
[    1.322208] x86/mm: Checked W+X mappings: passed, no W+X pages found.
[    1.322277] Run /init as init process
=== HELLO FROM OUR KERNEL (initramfs /init) ===
Linux (none) 6.6.0 ... x86_64 GNU/Linux
[    1.850758] reboot: Power down
```

`Hypervisor detected: KVM`이 보이면 하드웨어 가속으로 도는 겁니다. WSL2 안에서 `/dev/kvm`이 열려 있어(중첩 가상화) 부팅이 몇 초면 끝납니다. 여기서 작은 관찰 하나. 같은 커널에서 커널 심볼 주소를 봤을 때, WSL 셸에서 일반 사용자로 `/proc/kallsyms`를 읽으면 주소가 전부 0으로 가려져 있는데, 우리 게스트 안에서 root로 읽으면 진짜 주소가 나옵니다.

```console
# 게스트 안, root
ffffffff86c82970 T __x64_sys_openat
ffffffff87c001c0 D sys_call_table
```

주소를 0으로 가리는 건 커널 포인터를 함부로 노출하지 않으려는 완화(`kptr_restrict`)이고, 권한과 문맥에 따라 같은 인터페이스가 다른 걸 보여준다는 걸 눈으로 확인한 셈입니다.

## 첫 커널 모듈, 그리고 세 번 걸려 넘어진 곳

가장 먼저 한 실습은 아주 단순한 out-of-tree 모듈 하나를 빌드해서 올리는 것이었습니다. `printk` 한 줄 찍는 hello 모듈이요. 그런데 이 사소한 걸 하는 데서 세 번 걸렸고, 그 세 번이 오히려 커널 빌드의 실제를 알려줬습니다.

처음엔 모듈 빌드가 이렇게 실패했습니다.

```console
ERROR: modpost: "_printk" [hello.ko] undefined!
```

원인은 앞서 `bzImage`만 빌드했기 때문이었습니다. 그러면 커널이 내보내는 심볼 목록인 `Module.symvers`가 생기지 않아서, 외부 모듈이 `_printk` 같은 심볼을 연결하지 못합니다. 전체 `make`를 한 번 돌려 `Module.symvers`를 만들고 나서야 모듈이 붙었습니다.

두 번째는 초기 램디스크였습니다. `find | cpio | gzip`로 만들었더니 20바이트짜리 빈 파일이 나왔는데, 알고 보니 `cpio` 패키지 자체가 깔려 있지 않았습니다. 파이프 중간이 조용히 실패한 것이죠. 다행히 커널 소스가 자기 빌드 과정에서 `usr/gen_init_cpio`라는 도구를 만들어 두기 때문에, 패키지 없이 그걸로 초기 램디스크를 만들 수 있었습니다.

세 번째는 QEMU 옵션의 문법 착각이었습니다. `-accel kvm:tcg`라고 썼는데 그건 `-machine accel=` 쪽 문법이고, `-accel`에는 통하지 않습니다. `/dev/kvm`이 있으니 그냥 `-enable-kvm`으로 바꿔 해결했습니다.

세 번 다 사소하지만, 커널을 처음 손대는 사람이 정확히 밟는 지뢰들이라 그대로 적어 둡니다. 고치고 나니 모듈은 얌전히 올라오고 내려갔습니다.

```console
=== MODULE 3: clean LKM load ===
[    5.540918] hello: loading out-of-tree module taints kernel.
[    5.545861] aashello: LOADED — our first out-of-tree module
hello                  12288  0
[    5.556824] aashello: UNLOADED
```

## KASAN으로 use-after-free를 잡는다

이제 계측을 켤 차례입니다. 커널을 `CONFIG_KASAN=y`로 다시 빌드했습니다. KASAN(Kernel Address Sanitizer)은 할당된 메모리 주변에 레드존을 두고 섀도 메모리로 접근을 감시해서, 해제된 객체를 다시 쓰거나 경계를 넘는 접근을 그 자리에서 잡아내는 도구입니다.

버그는 제가 직접 심었습니다. misc 디바이스 하나를 만들어, open에서 버퍼를 하나 할당하고, write에서 그 버퍼를 해제하되 포인터는 그대로 두고, read에서 그 포인터를 다시 씁니다. 흔한 수명 관리 실수의 축소판입니다.

```c
static int aas_open(struct inode *ino, struct file *f){
    char *b = kmalloc(BUFSZ, GFP_KERNEL);   /* 여기서 할당 */
    memset(b, 0x41, BUFSZ);
    f->private_data = b;
    return 0;
}
static ssize_t aas_write(struct file *f, ...){
    kfree(f->private_data);   /* 해제하지만 포인터를 비우지 않음 = dangling */
    return n;
}
static ssize_t aas_read(struct file *f, ...){
    char *b = f->private_data;
    char c = b[0];            /* 이미 해제된 메모리를 읽음 = UAF */
    ...
}
```

같은 fd로 open → write → read를 한 번 부르는 작은 트리거를 돌리자, KASAN이 정확히 그 자리를 잡았습니다.

```console
BUG: KASAN: slab-use-after-free in aas_read+0x127/0x130 [aasbug]
Read of size 1 at addr ffff888001196b80 by task trigger/70
Allocated by task 70:
 aas_open+0x3a/0xb0 [aasbug]      <- 할당된 곳
Freed by task 70:
 aas_write+0x36/0x60 [aasbug]     <- 해제된 곳
The buggy address belongs to the object at ffff888001196b80
 which belongs to the cache kmalloc-64 of size 64
```

이 리포트가 좋은 이유는 세 지점을 한 번에 알려주기 때문입니다. 어디서 할당됐고(open), 어디서 해제됐고(write), 어디서 잘못 접근했는지(read). 커널 crash 분석에서 가장 먼저 익혀야 하는 구분이 바로 이겁니다. crash가 난 자리(fault site)와 버그의 원인(root cause)은 다릅니다. 여기서 KASAN이 불을 켠 곳은 read이지만, read는 피해자일 뿐입니다. 객체는 read가 실행되기 전에 이미 죽어 있었으니까요.

<svg viewBox="0 0 720 150" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="use-after-free 타임라인">
  <g font-family="monospace" font-size="12" fill="currentColor">
    <line x1="40" y1="40" x2="680" y2="40" stroke="currentColor"/>
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="60"  y="55" width="150" height="28" rx="5"/>
      <rect x="290" y="55" width="150" height="28" rx="5"/>
      <rect x="520" y="55" width="150" height="28" rx="5"/>
    </g>
    <g text-anchor="middle">
      <circle cx="70"  cy="40" r="4" fill="currentColor"/><text x="135" y="73">open: kmalloc-64</text>
      <circle cx="300" cy="40" r="4" fill="currentColor"/><text x="365" y="73">write: kfree (dangling)</text>
      <circle cx="530" cy="40" r="4" fill="currentColor"/><text x="595" y="73">read: b[0]  ← UAF</text>
      <text x="135" y="105" fill-opacity="0.75">alloc site</text>
      <text x="365" y="105" fill-opacity="0.75">root cause</text>
      <text x="595" y="105" fill-opacity="0.75">fault site</text>
    </g>
    <text x="40" y="130" fill-opacity="0.7">객체가 살아있는 구간은 open~write 사이뿐. read는 그 뒤라 이미 죽은 메모리를 만진다.</text>
  </g>
</svg>

근본 원인은 수명의 소유가 잘못됐다는 것입니다. `f->private_data`에 담긴 버퍼는 이 열린 파일이 소유하는 상태이고, 그 수명은 open부터 release(close)까지여야 합니다. 그런데 write가 그 버퍼를 중간에 해제해 버립니다. 데이터를 다루는 함수가, 파일 수명에 묶인 상태를 남의 일처럼 해제하고, 심지어 포인터도 비우지 않아 대롱대롱 매달린 채로 둡니다. 반대로 release는 아무것도 해제하지 않죠. 해제가 있어야 할 곳에는 없고, 없어야 할 곳에 있는 겁니다.

이 진단을 저 혼자 확신하고 싶지 않아서, 서로 다른 시각(객체 수명, 파일 오퍼레이션 계약, 동시성)으로 리포트와 소스를 독립적으로 분석하게 하고 각 결론을 다시 반박해 보게 했습니다. 세 시각이 같은 곳을 가리켰고, 동시성 관점에서는 한 발 더 나가는 지적이 나왔습니다. 만약 fd가 dup이나 fork로 여러 스레드에 공유되면, 해제를 write에 두는 한 read와 write가 겹쳐 돌면서 use-after-free나 이중 해제로 번질 수 있다는 것이죠. 그래서 흔히 떠올리는 "해제하고 포인터를 NULL로" 같은 반쪽 패치는 경쟁 조건 앞에서 안전하지 않습니다.

그 지적을 받아들여 택한 수정은 오히려 더 단순합니다. write는 애초에 이 버퍼를 해제하지 않게 하고, 해제는 오직 release에서 단 한 번 하도록 소유를 제자리로 돌립니다. 수명 중간에 해제하는 일이 사라지니, 경쟁 조건 자체가 성립하지 않아 잠금도 필요 없습니다. 게다가 원래 release가 아무것도 안 하던 탓에 숨어 있던 메모리 누수까지 같이 사라집니다.

고친 뒤 같은 트리거를, 이번엔 write를 두 번 부르는(원래 코드였다면 이중 해제가 났을) 버전으로 다시 돌렸습니다.

```console
=== MODULE 4 REGRESSION (patched driver) ===
trigger2: read r=1 c=0x41  (expect r=1 c=0x41 = buffer alive)
RESULT: PASS — no KASAN report (UAF fixed)
```

read가 살아있는 버퍼에서 원래 값 `0x41`을 돌려주고, KASAN은 조용합니다. 고치기 전에는 crash, 고친 뒤에는 무사. 이 대조가 있어야 비로소 "고쳤다"고 말할 수 있습니다.

## KCOV로, 이번엔 스스로 버그를 찾게

앞의 UAF는 제가 어디에 심었는지 아는 버그였습니다. 이번엔 반대로, 어디에 있는지 모르는 척하고 퍼저가 스스로 찾아내게 해봤습니다. 여기서 KCOV가 등장합니다. KCOV는 커널이 실행하면서 밟은 코드 경로(엣지)를 사용자 공간이 읽을 수 있게 해주는 커버리지 계측입니다. 퍼저는 이 커버리지를 나침반 삼아, 새로운 경로를 여는 입력을 남겨두고 거기서 변이를 이어갑니다.

<svg viewBox="0 0 700 170" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="KCOV 커버리지 가이드 루프">
  <g font-family="monospace" font-size="12" fill="currentColor" text-anchor="middle">
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="40"  y="20" width="120" height="30" rx="5"/>
      <rect x="290" y="20" width="150" height="30" rx="5"/>
      <rect x="560" y="20" width="110" height="30" rx="5"/>
      <rect x="290" y="115" width="150" height="30" rx="5"/>
    </g>
    <text x="100" y="39">입력 변이</text>
    <text x="365" y="39">ioctl 실행 + KCOV</text>
    <text x="615" y="39">KASAN 오라클</text>
    <text x="365" y="134">새 엣지면 코퍼스에 보관</text>
    <g stroke="currentColor" fill="none">
      <path d="M160 35 h130" marker-end="url(#a)"/>
      <path d="M440 35 h120" marker-end="url(#a)"/>
      <path d="M365 50 v65"  marker-end="url(#a)"/>
      <path d="M290 130 H120 V50" marker-end="url(#a)"/>
    </g>
    <defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="currentColor"/></marker></defs>
  </g>
</svg>

퍼징 대상으로 ioctl 하나를 가진 드라이버를 새로 만들었습니다. 명령 코드에 따라 네 갈래로 갈라지는데, 그중 두 갈래에 입력에 의존하는 heap out-of-bounds를 심었습니다. 하나는 사용자가 준 길이를 그대로 `memset`에 넘겨 64바이트 버퍼를 넘겨 쓰고, 다른 하나는 사용자가 준 인덱스를 검사 없이 씁니다. 핵심은, 이 버그가 아무 입력에서나 나는 게 아니라 특정 갈래에 특정 값이 들어가야만 난다는 것입니다. 그래서 커버리지 안내가 의미를 갖습니다.

퍼저는 `/sys/kernel/debug/kcov`를 mmap해서 매 실행의 엣지를 읽고, 새 엣지를 연 입력을 코퍼스에 남기며, `/dev/kmsg`에 KASAN 리포트가 뜨는지를 crash 신호로 삼습니다. 시드는 무해한 입력 하나뿐이었는데, 스물다섯 번째 시도에서 버그를 찾았습니다.

```console
kcovfuzz: coverage-guided fuzzing /dev/aasfuzz (KCOV edges, KASAN oracle)
  [it 1]  +185 edges (total 185, corpus 2) via op%4=0 ...
  [it 2]    +1 edges (total 186, corpus 3) via op%4=1 ...
  [it 25] +564 edges (total 752, corpus 6) via op%4=2 len=315 idx=0
CRASH: discovered crashing input: op=6 (op%4=2) len=315 idx=0  at iter 25, coverage 752 edges
BUG: KASAN: slab-out-of-bounds in aas_ioctl+0x1bd/0x220 [aasfuzz]
Write of size 315 at addr ffff8880019c8180 by task kcovfuzz/61
```

숫자에 이야기가 담겨 있습니다. 취약한 갈래(`op%4==2`)에 처음 들어간 순간 커버리지가 564엣지나 확 뛰었고, 바로 그 입력이 64바이트 버퍼에 315바이트를 써서 경계를 넘었습니다. 커버리지가 퍼저를 그 갈래로 끌고 갔고, KASAN이 넘어선 순간을 잡은 겁니다.

찾은 입력은 그대로 쓰기엔 큽니다(길이 315). 그래서 crash를 유지하는 선에서 최대한 줄였습니다. 원인은 "64보다 큰 길이"이므로, 최소 재현은 길이 65, 즉 딱 1바이트만 넘기는 것입니다.

```console
=== 최소 재현: op=2 len=65 ===
BUG: KASAN: slab-out-of-bounds in aas_ioctl+0x1bd/0x220 [aasfuzz]
Write of size 65 at addr ffff888001967d00 by task minrun/60
```

64바이트 객체에 65바이트. 1바이트 초과가 KASAN에게는 충분합니다. 이 최소 입력을 회귀 코퍼스로 남겨두면, 나중에 같은 실수가 다시 들어왔을 때 곧바로 잡힙니다.

## 남는 것

이번에 손에 익힌 건 결국 한 바퀴입니다. 소스를 받아 커널을 빌드하고, 가상 머신에 올리고, 계측을 켜서 crash를 내고, fault site와 root cause를 구분해 원인을 짚고, 고쳐서 회귀로 확인하고, 나아가 커버리지로 안내되는 퍼저가 스스로 버그를 찾게 하는 것. 개념으로 알던 것들이 로그 위에서 각자 제 위치를 찾아간 느낌입니다.

정직하게 한계도 적어 둡니다. 이번 커널은 x86_64 제네릭 커널이고, 버그는 제가 심은 것들입니다. 실제 Android 커널의 결은 여기서부터 달라집니다. ARM64라는 아키텍처, Android Common Kernel과 GKI/KMI라는 구조, 벤더 드라이버라는 넓은 공격면. 다음 글에서는 같은 루프를 ARM64와 Android Common Kernel 위에서 다시 돌려볼 생각입니다. 도구는 그대로 KASAN과 KCOV, syzkaller로 이어집니다.

## 참고

- The Linux Kernel documentation — [KASAN](https://docs.kernel.org/dev-tools/kasan.html)
- The Linux Kernel documentation — [KCOV: code coverage for fuzzing](https://docs.kernel.org/dev-tools/kcov.html)
- Google — [syzkaller: 커버리지 안내 커널 퍼저](https://github.com/google/syzkaller)
- The Linux Kernel documentation — [gen_init_cpio로 initramfs 만들기](https://docs.kernel.org/filesystems/ramfs-rootfs-initramfs.html)
