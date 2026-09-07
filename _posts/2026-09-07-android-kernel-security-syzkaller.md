---
layout: post
title: "Android Kernel Security 04 - 손으로 만든 KCOV 퍼저에서 syzkaller로, 진짜 규모의 커버리지 퍼징"
date: 2026-09-07 12:00:00 +0900
category: 시스템
author: WTCY
tags: [AndroidKernel, LinuxKernel, syzkaller, KCOV, KASAN, 커널퍼징, QEMU, KVM, coverage, 학습기록]
excerpt: "1편에서 KCOV로 손수 짠 작은 퍼저는 스물다섯 번 만에 제가 심어둔 버그 하나를 찾았습니다. 이번엔 그걸 진짜 도구로 갈아탑니다 — syzkaller를 우리 커널에 붙여 KVM 가상머신 여러 대에서 돌렸습니다. 붙이는 과정에서 세 번 넘어졌고(파이프라인이 프로세스를 죽이고, NIC 이름이 바뀌고, 커널에 없는 파일시스템을 이미지가 마운트하려다 응급모드로 빠지고), 고치고 나니 10분 만에 2,357개 시스템콜을 넘나들며 4만 3천 엣지의 커버리지를 쌓았습니다."
---

> 환경 고지. 모든 실행은 제 WSL2 게스트 안에서만 했습니다. 대상은 제가 직접 빌드한 리눅스 v6.6(KCOV+KASAN) 커널과, 로컬에서 debootstrap으로 만든 Debian 이미지뿐입니다. 실기기·외부 시스템은 건드리지 않았습니다. 실제 버그를 찾아 제보한 것은 없고(스톡 mainline을 10분 돌린 것뿐입니다), 이 글은 도구를 붙이고 규모를 키우는 과정과 실측 지표에 대한 기록입니다.

[1편](/posts/android-kernel-security-qemu-kasan-kcov/)에서 KCOV로 아주 작은 커버리지 퍼저를 손으로 짰습니다. `/dev/kcov`를 mmap해서 한 ioctl의 인자를 변이하고, 새 엣지를 여는 입력만 남기는 방식이었죠. 스물다섯 번 만에 제가 심어둔 heap out-of-bounds를 찾았습니다. 원리를 이해하기엔 좋았지만, 그건 장난감입니다. syscall 하나만, 인자 몇 개만 흔들었으니까요.

진짜 커널 퍼징은 syzkaller로 합니다. syzkaller는 시스템콜을 타입까지 기술한 문법(syzlang)으로 프로그램(시스템콜의 시퀀스)을 만들고, 그걸 가상머신 여러 대에서 병렬로 실행하며, KCOV 커버리지를 피드백 삼아 코퍼스를 키우고 최소화하는 분산 퍼저입니다. 이번엔 이걸 우리 커널에 붙였습니다.

## 어떻게 도는가

syzkaller는 호스트에서 `syz-manager`가 지휘합니다. 매니저가 가상머신 여러 대를 띄우고, 각 VM에 ssh로 들어가 `syz-executor`를 실행시킵니다. executor는 매니저가 보낸 프로그램을 커널에 실행하고, 그때 KCOV가 기록한 커버리지를 매니저로 돌려보냅니다. 매니저는 새 커버리지를 연 프로그램을 코퍼스에 남기고, 그걸 변이해 다음 프로그램을 만듭니다. KASAN이 크래시 오라클이 되어, 실행 중 메모리 오류가 나면 매니저가 그 프로그램을 재현·최소화합니다.

<svg viewBox="0 0 720 220" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="syzkaller 구조">
  <g font-family="monospace" font-size="12" fill="currentColor" text-anchor="middle">
    <g stroke="currentColor" fill="currentColor" fill-opacity="0.06">
      <rect x="20" y="80" width="150" height="60" rx="6"/>
      <rect x="290" y="20" width="180" height="50" rx="6"/>
      <rect x="290" y="150" width="180" height="50" rx="6"/>
      <rect x="560" y="85" width="140" height="50" rx="6"/>
    </g>
    <text x="95" y="105">syz-manager</text>
    <text x="95" y="123" fill-opacity="0.7">(호스트)</text>
    <text x="380" y="40">VM 0 (KVM)</text>
    <text x="380" y="58" fill-opacity="0.7">syz-executor + KCOV</text>
    <text x="380" y="170">VM 1 (KVM)</text>
    <text x="380" y="188" fill-opacity="0.7">syz-executor + KCOV</text>
    <text x="630" y="105">코퍼스</text>
    <text x="630" y="123" fill-opacity="0.7">+ 변이</text>
    <g stroke="currentColor" fill="none">
      <path d="M170 100 L290 45"/><path d="M170 120 L290 175"/>
      <path d="M470 45 L560 100"/><path d="M470 175 L560 120"/>
      <path d="M560 110 L490 110" stroke-dasharray="3 3"/>
    </g>
    <text x="230" y="80" fill-opacity="0.7" font-size="10">ssh: 프로그램</text>
    <text x="520" y="70" fill-opacity="0.7" font-size="10">커버리지</text>
    <text x="360" y="208" fill-opacity="0.7">새 엣지를 연 프로그램만 코퍼스에 남고, 거기서 다시 변이된다</text>
  </g>
</svg>

우리 장난감 퍼저와의 차이가 여기서 분명해집니다. 우리 건 ioctl 하나의 인자만 흔들었지만, syzkaller는 2천 개가 넘는 시스템콜을 타입 기술에 따라 조합하고, 자원(fd 같은)을 이어 붙이며, 커버리지가 정체되면 코퍼스를 최소화하고 새 방향으로 변이합니다. 규모와 지능이 다릅니다.

## 붙이면서 세 번 넘어졌다

솔직히 말하면, syzkaller를 처음 돌렸을 때 곧바로 죽었습니다. 세 번을 연달아 넘어졌는데, 셋 다 기록해 둘 값어치가 있습니다.

첫째, `syz-manager`가 시작한 지 2초 만에 SIGINT로 죽었습니다. 원인은 제가 실행을 `syz-manager … | tee | grep | tail`처럼 파이프로 묶은 것이었습니다. 파이프 끝의 소비자가 매니저의 수명을 좌우해 버린 것이죠. 출력을 파이프 대신 파일로 리다이렉트하고 표준입력을 `/dev/null`로 막자 매니저가 온전히 살아남았습니다.

둘째, 이번엔 VM이 부팅은 하는데 syz-manager가 ssh로 못 들어가고 멈췄습니다. VM 콘솔을 직접 뽑아 보니, 커널이 네트워크 카드를 `eth0`에서 `ens3`로 바꿔 이름 붙였는데(systemd의 예측 가능 인터페이스 이름), 이미지의 네트워크 설정은 `eth0`을 기대하고 있었습니다. 커널 커맨드라인에 `net.ifnames=0`을 줘서 이름을 `eth0`으로 고정했습니다.

셋째, 그런데도 여전히 응급모드(emergency mode)로 빠졌습니다. 처음엔 네트워크 탓인 줄, 다음엔 SELinux 탓인 줄 알았는데 둘 다 아니었습니다. 콘솔을 끝까지 읽으니 진짜 원인은 이거였습니다.

```console
systemd[1]: Dependency failed for local-fs.target - Local File Systems.
systemd[1]: Failed to start systemd-remount-fs.service ...
systemd[1]: Reached target emergency.target - Emergency Mode.
```

이미지의 `/etc/fstab`이 `securityfs`와 `configfs`를 마운트하는데, 정작 우리 커널은 `CONFIG_SECURITYFS`와 `CONFIG_CONFIGFS_FS` 없이 defconfig로 빌드돼 있었습니다. 없는 파일시스템을 마운트하려다 실패하고, 그게 `local-fs.target`을 무너뜨려 응급모드로 빠진 겁니다. 커널·이미지 설정 불일치였죠. 두 옵션을 켜고 커널을 다시 빌드하자(마침 syzkaller가 권장하는 옵션이기도 합니다), VM이 정상 부팅해 10초 만에 ssh가 열렸습니다.

세 번의 실패가 각각 다른 층이었다는 게 흥미롭습니다 — 프로세스 수명(파이프), 네트워크 이름(커널 파라미터), 커널·이미지 설정 불일치(파일시스템). 퍼저를 붙이는 일의 절반은 이런 배관 작업이더군요.

## 10분 동안 무슨 일이 있었나

고치고 나서, KVM 가속으로 VM 두 대에 각 4개 프로세스를 두고 10분 반을 돌렸습니다. 커버리지가 이렇게 자랐습니다.

<svg viewBox="0 0 720 280" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;height:auto;color:inherit" role="img" aria-label="10분간 커버리지 성장">
  <g font-family="monospace" font-size="11" fill="currentColor">
    <line x1="60" y1="30" x2="60" y2="240" stroke="currentColor"/>
    <line x1="60" y1="240" x2="680" y2="240" stroke="currentColor"/>
    <polyline points="60,240 100,141 117,124 174,127 350,95 529,74 620,52 680,46" fill="none" stroke="currentColor" stroke-width="2"/>
    <g fill="currentColor">
      <circle cx="100" cy="141" r="3"/><circle cx="174" cy="127" r="3"/><circle cx="529" cy="74" r="3"/><circle cx="680" cy="46" r="3"/>
    </g>
    <text x="30" y="46" text-anchor="end">44k</text>
    <text x="30" y="240" text-anchor="end">0</text>
    <text x="60" y="258" text-anchor="middle">0</text>
    <text x="680" y="258" text-anchor="middle">10.5분</text>
    <text x="112" y="136">16,117</text>
    <text x="360" y="70" fill-opacity="0.75">40,108</text>
    <text x="600" y="42">43,868 edges</text>
    <text x="370" y="278" text-anchor="middle" fill-opacity="0.7">시간 →   (초반 급상승, 이후 완만한 정체 — 전형적인 커버리지 곡선)</text>
  </g>
</svg>

숫자로 정리하면 이렇습니다.

```
가상머신        : 2대 (KVM 가속) × 각 4 프로세스
활성 시스템콜   : 2,357 / 8,301
커버리지        : 43,868 엣지 (0 → 16k → 23k → 43,868)
코퍼스          : 2,293 프로그램 (시드 266개에서 출발)
총 실행         : 52,080 프로그램 (~80 프로그램/초)
크래시          : 0
```

크래시가 0인 건 실망스러운 게 아니라 예상된 결과입니다. 이건 잘 관리되는 mainline v6.6 커널이고, 업스트림에서 이미 수없이 퍼징된 코드입니다. 10분으로 새 버그가 나올 리 없죠. syzkaller의 진짜 값어치는 두 곳에서 나옵니다. 하나는 몇 시간~며칠을 돌리며 커버리지를 계속 넓히는 지속성, 다른 하나는 덜 다듬어진 코드 — 벤더 드라이버나 새 서브시스템처럼 — 를 겨냥할 때입니다. 우리 장난감 퍼저가 25번 만에 찾은 건 제가 그 자리에 심어둔 버그였고, syzkaller가 10분간 4만 엣지를 훑고도 조용한 건, 그 코드에 (아직) 그런 버그가 없기 때문입니다. 둘 다 정직한 결과입니다.

## 남는 것과 다음

1편의 손수 짠 퍼저에서 시작해, 같은 KCOV 피드백 원리를 진짜 규모의 도구로 옮겼습니다. 이제 초당 수십 개 프로그램을, 이천 개가 넘는 시스템콜 위에서, 커버리지에 이끌려 돌립니다. 이게 커널 퍼징의 실제 모습입니다.

다음 두 방향이 자연스럽습니다. 하나는 우리가 만든 `aasfuzz` 드라이버의 ioctl을 syzlang으로 기술해 syzkaller가 그걸 직접 겨냥하게 하는 것 — 그러면 1편에서 심은 그 out-of-bounds를 이 도구가 다시 찾아내는 걸 볼 수 있습니다. 다른 하나는, 잘 퍼징된 mainline 대신 덜 다듬어진 코드로 조준을 옮기는 것입니다. 버그는 사람들이 덜 들여다본 곳에 있으니까요.

## 참고

- google/syzkaller — [설치와 QEMU 실행](https://github.com/google/syzkaller/blob/master/docs/linux/setup.md)
- google/syzkaller — [시스템콜 기술 문법(syzlang)](https://github.com/google/syzkaller/blob/master/docs/syscall_descriptions.md)
- The Linux Kernel documentation — [KCOV](https://docs.kernel.org/dev-tools/kcov.html)
