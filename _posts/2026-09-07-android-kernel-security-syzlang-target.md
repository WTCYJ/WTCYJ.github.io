---
layout: post
title: "Android Kernel Security 05 - 내 드라이버를 syzkaller에 가르치기, syzlang 기술서로 내 버그를 되찾다"
date: 2026-09-07 15:00:00 +0900
category: 시스템
author: WTCY
tags: [AndroidKernel, LinuxKernel, syzkaller, syzlang, KCOV, KASAN, 커널퍼징, 커널드라이버, ioctl, 학습기록]
excerpt: "4편에서 syzkaller를 커널에 붙여 규모 있게 돌렸지만, 그건 커널이 원래 가진 시스템콜을 훑은 것이었습니다. 이번엔 syzkaller에게 우리 드라이버가 어떻게 생겼는지 syzlang으로 기술해, 우리 ioctl을 정확히 겨냥하게 했습니다. 그러자 1편에서 손수 짠 퍼저가 스물다섯 번 만에 찾던 그 heap out-of-bounds를, syzkaller가 기술서만 보고 첫 스무 번 실행 안에 되찾았습니다."
---

> 환경 고지. 모든 실행은 제 WSL2 게스트 안에서만 했고, 대상은 제가 직접 빌드한 커널과 제가 만든 교육용 드라이버(`aasfuzz`)뿐입니다. 취약점은 제가 일부러 심은 것이고, crash와 그 위치까지만 다룹니다.

[4편](/posts/android-kernel-security-syzkaller/)에서 syzkaller를 우리 커널에 붙여 10분간 4만 엣지를 훑었습니다. 그런데 그건 커널이 이미 가진 시스템콜들을 퍼징한 것이었죠. 만약 내가 만든 드라이버, 내가 노출한 ioctl을 겨냥하고 싶다면 어떻게 할까요. syzkaller에게 "내 인터페이스는 이렇게 생겼다"고 알려줘야 합니다. 그 언어가 syzlang입니다.

## 왜 기술서가 필요한가

우리 [1편](/posts/android-kernel-security-qemu-kasan-kcov/)의 손수 짠 퍼저를 떠올려 봅시다. 그건 우리가 직접 `struct`의 필드를 알고, 그 값을 흔들었습니다. syzkaller는 그 지식이 없습니다. `/dev/aasfuzz`에 `ioctl`이 있다는 것도, 그 명령 번호가 무엇인지도, 인자가 어떤 구조체인지도 모릅니다. 아무것도 안 알려주면 syzkaller는 그냥 무작위 바이트를 던질 뿐이고, 그러면 우리 드라이버의 `copy_from_user`조차 제대로 통과하지 못해 얕게 긁고 맙니다.

syzlang으로 기술하면 달라집니다. "이 파일을 열면 특정 자원(fd)이 나오고, 그 fd에 이 명령 번호로 이런 필드를 가진 구조체를 넘기는 ioctl이 있다"고 알려주면, syzkaller는 그 모양에 맞는 입력을 만들어 필드 값만 지능적으로 변이합니다.

<svg viewBox="0 0 720 210" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="기술서 유무에 따른 입력 차이">
  <g font-family="monospace" font-size="11.5" fill="currentColor">
    <text x="20" y="24" fill-opacity="0.7">기술 없이 (무작위 바이트):</text>
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06"><rect x="20" y="34" width="300" height="46" rx="5"/></g>
    <text x="34" y="53">ioctl(fd, 0x9a3f, 0x7f..rand)</text>
    <text x="34" y="70" fill-opacity="0.7">→ 잘못된 cmd/포인터, 얕게 튕김</text>
    <text x="20" y="118" fill-opacity="0.7">기술 있이 (타입 있는 프로그램):</text>
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06"><rect x="20" y="128" width="360" height="64" rx="5"/></g>
    <text x="34" y="147">r0 = openat$aasfuzz(AT_FDCWD, "/dev/aasfuzz", O_RDWR)</text>
    <text x="34" y="164">ioctl$AASFUZZ_RUN(r0, 0x4010f501,</text>
    <text x="48" y="181">&amp;{op, len, idx, val})   ← 필드만 변이</text>
    <g stroke="currentColor" fill="none" marker-end="url(#ar)">
      <path d="M400 160 h150"/>
    </g>
    <text x="470" y="150" text-anchor="middle" fill-opacity="0.75">우리 ioctl</text>
    <text x="470" y="178" text-anchor="middle" fill-opacity="0.75">경로를 깊이 판다</text>
    <defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="currentColor"/></marker></defs>
  </g>
</svg>

## 세 조각을 맞춘다

첫째, 드라이버를 커널에 붙박이로 넣었습니다. 모듈로 로드하는 대신 `drivers/misc/aasfuzz.c`로 커널에 컴파일해 넣어, 부팅하면 `/dev/aasfuzz`가 항상 있게 했습니다. 그리고 ioctl 번호를 유저스페이스와 공유하도록 uapi 헤더를 뒀습니다.

```c
/* include/uapi/linux/aasfuzz.h */
struct aasfuzz_cmd { __u32 op; __u32 len; __u32 idx; __u8 val; };
#define AASFUZZ_RUN _IOW(0xF5, 1, struct aasfuzz_cmd)
```

드라이버의 ioctl은 `op % 4`로 갈라지고, 그중 둘에 입력 의존 heap out-of-bounds를 심었습니다. 하나는 사용자가 준 길이로 64바이트 버퍼를 넘겨 `memset`, 하나는 사용자가 준 인덱스로 범위 밖에 씁니다.

둘째, syzlang 기술서를 썼습니다. 파일을 열면 `fd_aasfuzz`라는 자원이 나오고, 그 자원에 `AASFUZZ_RUN` 명령으로 구조체를 넘긴다고 기술합니다.

```
include <linux/fcntl.h>
include <linux/aasfuzz.h>

resource fd_aasfuzz[fd]
openat$aasfuzz(fd const[AT_FDCWD], file ptr[in, string["/dev/aasfuzz"]], flags flags[open_flags], mode const[0]) fd_aasfuzz
ioctl$AASFUZZ_RUN(fd fd_aasfuzz, cmd const[AASFUZZ_RUN], arg ptr[in, aasfuzz_cmd])
aasfuzz_cmd { op int32; len int32; idx int32; val int8 }
```

`resource fd_aasfuzz`가 핵심입니다. `openat$aasfuzz`가 이 자원을 만들고 `ioctl$AASFUZZ_RUN`이 그걸 받으니, syzkaller는 "먼저 열고 그 fd로 ioctl을 부른다"는 순서를 스스로 지킵니다.

셋째, 상수를 추출해 syzkaller를 다시 생성했습니다. syzlang의 `AASFUZZ_RUN`, `AT_FDCWD` 같은 이름은 실제 숫자로 바뀌어야 합니다. `syz-extract`가 커널 헤더에서 그 값을 뽑습니다.

```console
$ ./bin/syz-extract -os linux -arch amd64 -sourcedir <kernel> dev_aasfuzz.txt
AASFUZZ_RUN = amd64:1074853121     # = 0x4010f501
AT_FDCWD    = amd64:-100
```

여기서 세 번 걸렸는데, 셋 다 적어 둡니다. `syz-extract`는 `tools/`가 아니라 `sys/syz-extract`에 있고 기본 빌드에 안 들어가서 따로 빌드해야 했습니다. `<linux/fcntl.h>`를 빼먹었더니 `AT_FDCWD`가 `???`로 나오면서 그 상수를 쓰는 콜 전체가 조용히 빠져 버렸습니다. 그리고 `make generate`는 `clang-format`이 없어 실패했는데, 그건 C++ 정렬용 사족 단계라 `make descriptions`로 우회했습니다.

## 우리 ioctl만 겨냥해 돌리다

이제 매니저 설정에서 활성 시스템콜을 우리 둘로 좁혔습니다.

```
"enable_syscalls": ["openat$aasfuzz", "ioctl$AASFUZZ_RUN"]
```

syzkaller가 이렇게 확인해 줍니다 — `syscalls: 2/8303`. 8천 개 중 딱 우리 둘. 그리고 그 둘만 집요하게 두드리니, 첫 스무 번쯤 실행 안에 크래시가 터졌습니다.

```console
BUG: KASAN: slab-out-of-bounds in aas_ioctl+0x1e4/0x220 drivers/misc/aasfuzz.c:33
Write of size 1 at addr ffff8880038bf94a by task syz.4.9
 aas_ioctl drivers/misc/aasfuzz.c:33
 __x64_sys_ioctl fs/ioctl.c:857
 do_syscall_64 arch/x86/entry/common.c:80
RSI: 000000004010f501   RDI: 000000000000000a
```

`RSI`(ioctl의 두 번째 인자, 명령 번호)가 `0x4010f501`입니다. 우리가 헤더에 정의한 `AASFUZZ_RUN`과 정확히 같죠. 즉 syzkaller가 무작위가 아니라 우리 명령 번호로 정확히 ioctl을 불렀고, 그 안에서 KASAN이 out-of-bounds 쓰기를 잡은 겁니다. 같은 실행에서 더 큰 값이 들어간 경우엔 매핑되지 않은 주소로의 쓰기(page fault)까지 나왔습니다. 버그를 빨리 찾은 뒤 syzkaller는 남은 시간을 그 크래시를 재현하는 데 썼습니다.

## 같은 버그, 다른 격

1편의 손수 짠 퍼저도 이 버그를 찾았습니다. 스물다섯 번 만에요. 그런데 그때는 제가 `struct`의 필드를 코드로 직접 알고 흔들었습니다. 이번엔 syzkaller에게 인터페이스의 모양만 기술로 알려줬을 뿐, 값을 어떻게 흔들지는 도구가 알아서 했습니다. 그리고 이 방식은 우리 드라이버 하나에만 쓰이는 게 아닙니다. 똑같이 어떤 드라이버든 그 ioctl과 구조체를 syzlang으로 기술하면, syzkaller가 그걸 겨냥합니다. syzkaller가 매일 업스트림 커널에서 새 버그를 찾아내는 게 바로 이 방식입니다 — 수천 개 인터페이스의 기술서를 갖고, 타입에 맞는 입력을 커버리지에 이끌려 끝없이 변이하는 것.

우리가 심은 버그를 우리가 찾는 건 예정된 결말입니다. 하지만 그 과정에서 배운 것 — 커버리지 퍼저에게 인터페이스를 기술로 가르치는 방법 — 은 심지 않은 버그를 찾을 때 그대로 쓰입니다. 다음은 잘 다듬어진 mainline 대신, 덜 들여다본 코드에 이 방법을 겨누는 것입니다. 버그는 거기에 있으니까요.

## 참고

- google/syzkaller — [시스템콜 기술 문법(syzlang)](https://github.com/google/syzkaller/blob/master/docs/syscall_descriptions.md)
- google/syzkaller — [기술서에서 상수 추출(syz-extract)](https://github.com/google/syzkaller/blob/master/docs/syscall_descriptions_syntax.md)
- The Linux Kernel documentation — [KASAN](https://docs.kernel.org/dev-tools/kasan.html)
