---
layout: post
title: "Android Security Concept Atlas C05 | 가상 실습 보고서 — ARM64 예외 수준과 메모리 보호, 격리는 어느 층에서 강제되는가"
date: 2026-08-29 22:57:00 +0900
category: 안드로이드
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ARM64, AArch64, ExceptionLevel, EL0, EL1, EL2, EL3, TrustZone, TEE, MMU, PAN, PXN, PAC, BTI, MTE, ASLR, pKVM, Keystore, 신뢰경계, ConceptAtlas, 학습기록]
excerpt: "24주 스터디 내내 '경계는 한 겹이 아니다'라고 적었지만, 정작 그 경계들이 CPU의 어느 특권 층에서 강제되는지는 짚지 않았습니다. ARM64에는 EL0부터 EL3까지 네 개의 예외 수준이 있고, 앱 샌드박스와 SELinux는 둘 다 EL1에서, Keystore 키는 EL3 너머 시큐어 월드에서 강제됩니다. 이 사다리를 세워두면 '커널 익스는 왜 SELinux까지 같이 무너뜨리는가', '루트를 따도 왜 키는 못 빼는가'가 한 그림으로 정리됩니다. Concept Atlas의 다섯 번째 모듈입니다."
---

> **가상 환경 전용**: 이 글의 실습은 Android Emulator, Cuttlefish, QEMU, host-side harness와 공개 소스·공개 이미지로만 진행합니다. 실물 Android/iOS 기기, USB 단말 연결, rooting, bootloader unlock과 flashing은 사용하지 않습니다. 하드웨어 전용 속성은 개념과 공개 증거까지만 다루며 `가상 환경의 검증 한계`로 구분합니다. 실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다.

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 `codex-atlas-api33` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | `id`, `cat /proc/self/attr/current`, `/proc/self/status`, `uname -a` |
| 관측 결과 | 앱 UID 10174, `untrusted_app` 도메인, `CapEff=0`, `Seccomp=2`, Linux 5.15 커널을 확인했다. |
| 검증 한계 | AVD가 x86_64이므로 ARM64 EL·PAC·BTI·MTE는 런타임 관측 대신 공개 소스 경로로 판정한다. |

![C05 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/evidence-sandbox.png)

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 `adb shell` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. `[exit=0]`은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->






> **Concept Atlas 모듈**: C05 — ARM64 예외 수준과 메모리 보호
> **계층**: Tier 0 (시스템 기초) · **난이도**: 중급 · **선수 개념**: C04(프로세스·가상메모리·시스템 콜)
> **성격**: 개념 해설과 가상 실습 실행 보고서를 함께 제공하는 검증본입니다.
> **완료 기준**: EL 전이 한 개와 W^X 위반을 실기 근거로 설명할 수 있다.

24주 스터디를 마치고 CVE 열 건을 재현하는 동안, 저는 "경계는 한 겹이 아니다"라는 문장을 여러 번 적었습니다. 15~16주차에서는 Binder 경계가 두 겹이라고 했고, 1~4주차에서는 앱 격리가 UID와 SELinux 두 겹이라고 명령 출력으로 확인했습니다. 그런데 정작 **그 경계들이 CPU의 어느 특권 층에서 강제되는가**는 한 번도 짚지 않았습니다. "커널이 막는다", "SELinux가 막는다"라고만 적었지, 그 둘이 같은 층인지 다른 층인지 몰랐습니다.

이 모듈은 그 밑바닥을 세웁니다. ARM64의 예외 수준(Exception Level)과 메모리 보호는 부팅 체인(C27~C32), 커널 하드닝(C37), 하드웨어 기반 보안(C39~C43)이 전부 올라앉는 토대입니다. 여기가 비어 있으면 위층은 전부 "어딘가에서 막힌다더라" 수준에 머뭅니다. 그래서 Atlas의 첫 풀 작성 대상으로 이걸 골랐습니다.

## 배경 개념 - 예외 수준이라는 사다리

먼저 용어를 한 줄씩 세우겠습니다. 이후 절은 이 사다리를 반복해서 참조합니다.

- **예외 수준(Exception Level, EL)**: AArch64에는 EL0부터 EL3까지 네 개의 특권 층이 있습니다. 숫자가 클수록 특권이 높습니다. EL0·EL1은 아키텍처가 반드시 갖추도록 정한 필수 층이고, EL2·EL3는 선택이지만 실제 스마트폰 AP(애플리케이션 프로세서)에는 사실상 항상 둘 다 있습니다.
- **시큐어 상태(Secure/Non-secure)**: 이것은 EL과 **직교하는 별개의 축**입니다. EL의 위쪽에 있는 다섯 번째 층이 아닙니다. `SCR_EL3.NS` 비트가 고릅니다. EL0·EL1은 각각 시큐어판과 논시큐어판을 둘 다 가지며, EL3는 언제나 시큐어입니다. 흔히 말하는 "TrustZone"이 바로 이 축입니다.
- **MMU와 변환 테이블**: 메모리 관리 장치. `SCTLR_EL1.M`이 켜지면 EL0/EL1의 모든 적재·저장·명령 인출이 변환 테이블의 권한 비트에 대해 하드웨어에서 매 접근마다 검사됩니다. 우회로가 없습니다 — 이것이 뒤에서 말할 "완전 중재"의 실체입니다.
- **특권 호출 명령**: `SVC`는 EL0→EL1(시스템 콜의 문), `HVC`는 →EL2(하이퍼콜), `SMC`는 →EL3(시큐어 모니터 호출). 앱이 있는 EL0에서 `HVC`·`SMC`는 **정의되지 않은 명령**이라 예외를 일으킵니다. 앱이 쓸 수 있는 특권 호출은 오직 `SVC` 하나입니다.

이 정도만 잡고 아래 여덟 개 질문으로 개념을 조립하겠습니다. 이 여덟 질문은 Atlas의 모든 개념 모듈이 공통으로 답하는 틀입니다.

## 질문 1 — 이 개념은 Android 전체 구조에서 어디에 있는가

가장 밑바닥입니다. Android의 모든 소프트웨어는 예외 수준 사다리의 어느 칸에 올라앉아 있습니다. 스마트폰에서의 표준적인 대응은 이렇습니다.

| EL | 논시큐어(Normal World) | 시큐어(Secure World) |
|----|----------------------|---------------------|
| EL0 | 앱, ART, JNI 네이티브 코드, `linker64`, Bionic | 트러스트릿(트러스티드 앱) — 예: KeyMint TA |
| EL1 | Linux 커널 + SELinux LSM | TEE OS — Trusty / QSEE / Kinibi |
| EL2 | 하이퍼바이저 — pKVM, 벤더 하이퍼바이저(Gunyah, RKP) | 시큐어 하이퍼바이저(FEAT_SEL2, v8.4+에서만) |
| EL3 | — (EL3는 언제나 시큐어) | 시큐어 모니터 — 보통 Trusted Firmware-A의 BL31 |

부팅 체인(C27~C32)이 바로 이 표의 각 칸에 코드를 심는 과정입니다. Trusted Firmware-A 기준으로 BL1(부트 ROM)이 EL3에서 시작해, BL31(상주 시큐어 모니터)을 EL3에, BL32(TEE OS)를 S-EL1에, BL33(비시큐어 부트로더)을 논시큐어 EL2/EL1에 놓고, 그 부트로더가 커널을 적재합니다. 즉 **이 모듈은 부팅 체인의 결과물**이기도 합니다. 부팅이 끝난 순간 각 층에는 이미 서로 다른 코드가 자리 잡고 있습니다.

## 질문 2 — 어느 프로세스와 권한 수준에서 동작하는가

핵심은 **"내가 통제하는 코드는 전부 EL0 논시큐어에 있다"**는 것입니다. 앱의 Java/Kotlin을 실행하는 ART 런타임도, 13~14주차에서 파일을 직접 파싱했던 JNI 네이티브 라이브러리도, `linker64`도 전부 EL0입니다. 사다리의 맨 아래이고, 논시큐어입니다.

그 아래(정확히는 위)의 강제 층은 이렇게 배치됩니다.

- **EL1 — 커널**: UID/파일 권한 같은 임의 접근 제어(DAC)와 SELinux의 강제 접근 제어(MAC)를 **둘 다** 커널 코드가 EL1에서 판정합니다. 1~4주차에서 "두 겹"이라 불렀던 그 두 겹이, 특권 층으로 보면 **같은 한 층**입니다. 이 사실은 질문 3에서 결정적입니다.
- **EL2 — 하이퍼바이저**: pKVM(Android 13, GKI 5.15)이 여기 있습니다. 뒤에서 보겠지만 pKVM은 EL1 호스트 커널을 오히려 **낮춰서** 보호 VM 메모리를 못 보게 만듭니다.
- **EL3 — 시큐어 모니터**: `SCR_EL3`, 월드 전환, PSCI 전원 관리를 소유합니다. 논시큐어↔시큐어 전환의 유일한 문지기입니다. 커널과는 별개인, 아주 작은 벤더/SoC 통제 TCB입니다.
- **시큐어 EL1/EL0 — TEE와 트러스티드 앱**: Keystore의 개인키를 실제로 쓰는 KeyMint TA가 S-EL0에서, 그 밑의 TEE OS가 S-EL1에서 돕니다.

한 가지 정밀함을 덧붙입니다. arm64 Linux는 관례상 **EL2로 진입**한 뒤 하이퍼 스텁을 설치하고 `ERET`로 EL1로 내려옵니다. 그리고 Android의 pKVM은 nVHE 모델을 써서 호스트 커널을 일부러 EL1에 **묶어 둡니다**(그래야 EL2가 그것을 가둘 수 있으니까요). 그래서 "Android 커널은 EL1에서 돈다"는 서술은 맞지만, "진입은 EL2에서 한다"도 동시에 참입니다. 일반 서버 KVM(VHE)은 호스트 커널을 EL2에 두기도 하지만, 그건 Android의 기본 구성이 아닙니다.

## 질문 3 — 무엇을 신뢰하고 무엇을 신뢰하면 안 되는가

이 질문이 이 모듈 전체의 보상입니다. 두 개의 대표적 격리 장치가 **어느 층에서 강제되는지**를 알면, 그 둘의 강도가 왜 다른지가 한 그림으로 정리됩니다.

**앱 샌드박스(UID 격리)와 SELinux는 둘 다 EL1 커널 코드가 강제합니다.** 그래서 이 둘은 **단일 실패 도메인**을 공유합니다. EL0에 있는 앱이 이 둘 중 하나라도 넘으려면 EL0→EL1 특권 상승, 즉 시스템 콜/`ioctl`/Binder 표면을 통해 도달한 커널 또는 드라이버 익스플로잇이 필요합니다. 그리고 그 한 번의 탈출이 **두 겹을 동시에** 무너뜨립니다. 커널을 쥐면 SELinux 판정을 하는 코드도 내 것이 되니까요.

**Keystore/KeyMint 개인키는 EL3 너머 시큐어 월드(또는 StrongBox라는 별도 칩)에 있습니다.** 그래서 여기는 이야기가 다릅니다. 논시큐어 EL1(전체 커널)을 완전히 장악해도, 공격자는 서명·복호 **연산을 요청**할 수 있을 뿐 **원본 키를 추출하지는 못합니다**. 키가 논시큐어 메모리로 절대 나오지 않기 때문입니다. 이 비대칭이 핵심입니다. 커널 익스는 SELinux와 샌드박스를 한 방에 뚫지만, **같은 익스로 하드웨어 백업 키는 못 빼냅니다.**

15기 에이전트 샌드박스 글에서 제가 "완전 중재는 네 칸 중 한 칸에만 있었다"라고 썼습니다. 그때는 소프트웨어 정책 층의 이야기였는데, MMU가 하는 일이 바로 그 **완전 중재의 하드웨어판**입니다. `SCTLR_EL1.M`이 켜진 뒤에는 모든 접근이 예외 없이 검사됩니다 — 그래서 신뢰할 수 있고, 그래서 이 검사를 우회하려면 검사기 자체(EL1)를 장악하는 수밖에 없습니다.

정리하면, **신뢰해도 되는 것**은 "MMU가 매 접근을 검사한다"와 "시큐어 월드 키는 논시큐어에서 못 나온다"이고, **신뢰하면 안 되는 것**은 "EL0 안에서 벌어지는 어떤 논리적 권한 상승이 곧 EL 전이일 것"이라는 착각입니다(질문 5에서 다시 봅니다).

## 질문 4 — 입력과 출력은 무엇인가

예외 수준·메모리 보호를 하나의 판정기로 보면 입출력이 이렇게 정의됩니다.

- **입력**: 하나의 접근 시도 = { 가상 주소(VA), 접근 종류(적재/저장/명령 인출), 현재 EL(PSTATE.EL), 현재 PSTATE.PAN, 그리고 그 VA를 덮는 변환 테이블 디스크립터의 권한 비트(AP[2:1], PXN, UXN) }.
- **출력**: 허용, 또는 **폴트 → 해당 EL로 예외 진입**. 폴트가 나면 CPU는 PSTATE를 `SPSR_ELx`에, 복귀 주소를 `ELR_ELx`에 저장하고 PC를 `VBAR_ELx + 고정 오프셋`으로 옮깁니다. 처리 후 `ERET`가 그 역을 수행합니다.

한 가지 자주 틀리는 지점: `ERET`의 복귀 대상 EL은 `SPSR_ELx.M`에 적힌 값으로 정해지며, **현재보다 높은 EL을 고를 수 없습니다**. 더 높은 EL을 적으면 그것은 특권 상승이 아니라 Illegal Exception Return(`PSTATE.IL`=1)입니다. 위로 올라가는 길은 오직 **예외를 맞는 것**뿐입니다. 이 단방향 비대칭이 격리 모델의 등뼈입니다.

## 질문 5 — 실패하면 어떤 취약점으로 이어지는가

층별로, 그 층의 보장이 깨졌을 때 나오는 취약점 종류를 붙입니다.

- **EL0→EL1이 뚫리면 = 커널 LPE.** 앱(EL0)이 드라이버의 UAF/OOB를 통해 EL1 제어 흐름을 탈취하거나 임의 커널 R/W를 얻습니다. 이것이 Android 커널 공격 표면의 존재 이유 전부입니다. 실제 사례로 Binder UAF인 CVE-2019-2215('Bad Binder'), Mali GPU 드라이버 버그(CVE-2023-4211 등)가 전부 앱 샌드박스 안 EL0에서 도달됩니다.
- **PAN이 실패하면 = 사용자 포인터 역참조 프리미티브 부활.** PAN(FEAT_PAN, v8.1)은 EL1이 사용자 접근 가능 페이지에 **데이터 접근**하면 폴트내는 장치입니다(x86의 SMAP에 해당). 커널은 `copy_to/from_user` 주위에서만 `uaccess_enable/disable`로 PAN을 잠깐 끕니다. PAN 우회란 그 창 안에서, 혹은 PSTATE.PAN을 되끄는 가젯으로 커널이 **의도치 않게** 사용자 포인터를 역참조하게 만드는 것입니다.
- **PXN이 없으면 = ret2usr.** PXN(디스크립터 bit53)은 EL1이 사용자 페이지를 **실행**하지 못하게 합니다. 여기서 중요한 정밀함: 이건 ARM64가 **자동으로** 주는 보장이 아닙니다. 커널이 사용자 매핑에 PXN=1을 **명시적으로 설정**해야 하고, 그제서야 MMU가 하드웨어로 강제합니다. 정책은 소프트웨어가 고르고, 강제는 하드웨어가 합니다. 현대 arm64는 기본으로 PXN을 설정하므로 고전 ret2usr은 죽었고, 공격자는 커널 메모리 안에서 ROP/JOP를 짜야 합니다.
- **EL2가 뚫리면 = pKVM 격리 붕괴.** 보호 VM이 호스트로부터 숨겨져 있다는 AVF의 보장이 무너집니다.
- **EL3/TEE가 뚫리면 = 신뢰의 뿌리 붕괴.** attestation을 위조하고, Gatekeeper의 PIN 시도 제한을 깨고, Keystore 키를 빼낼 수 있습니다. 그래서 StrongBox(별도 보안 칩)가 TEE보다 강한 TCB입니다 — 메인 SoC 밖이라 EL3/TEE 버그로 못 닿습니다.

여기서 제 CVE 재현들과의 대조가 중요합니다. **제가 재현한 미디어 코덱 정수 결함(4·7편)과 블루투스 버퍼 결함(8편)은 EL0에서 실행됩니다.** `mediacodec`, `com.android.bluetooth` 같은 **샌드박스된 사용자 프로세스** 안이지, 커널이 아닙니다. 메모리 안전 버그이긴 하지만 그 자체로는 EL 전이가 아닙니다. 커널(EL1)에 닿으려면 **별도의 커널 버그를 이어 붙여야** 합니다. 코덱 RCE를 "커널 장악"이라 부르면 영향을 과대평가하는 것입니다 — 이건 EL0 발판이고, 커널 LPE는 별개의 2단계입니다.

그리고 20~24주차의 **CVE-2022-20425**는 아예 EL 전이가 아닙니다. 이건 `system_server`(EL0 논시큐어 사용자 프로세스, UID 1000) 안 `ZenModeHelper`의 **자원 고갈형 국소 DoS**(CWE-400, 가용성 영향만)입니다. 제가 그때 "바뀐 것은 한도가 아니라 **세는 단위**였고, **세는 키를 호출자가 정하고 있었다**"라고 결론지은 바로 그 버그입니다. CPU는 이걸 예외 수준 전이로 보지 않습니다. Android 의미의 "권한 상승"(UID/GID/SELinux 도메인)과 EL 전이는 **직교하는 개념**입니다. 이 구분을 흐리면 "system_server를 깼으니 커널을 쥐었다" 같은 잘못된 문장이 나옵니다 — system_server는 권한(정책)이 넓을 뿐, 특권 층은 여전히 EL0입니다.

## 질문 6 — Android 버전에 따라 무엇이 달라졌는가

메모리 보호 프리미티브는 ARM 아키텍처 버전과 Android 릴리스 양쪽에 걸쳐 들어왔습니다. 외울 필요는 없고, "이 기기엔 이게 있나?"를 판정할 좌표로 쓰면 됩니다.

| 시점 | 달라진 것 |
|------|----------|
| Armv8.0 기준 | PXN/UXN이 변환 테이블 디스크립터 비트로 존재(별도 Kconfig 없이 커널 pgprot가 무조건 설정). 시큐어 월드는 S-EL0+S-EL1만, Secure EL2 없음 |
| Armv8.1 (FEAT_PAN) | 하드웨어 PAN(PSTATE.PAN). 이전 코어는 `CONFIG_ARM64_SW_TTBR0_PAN`으로 소프트웨어 에뮬레이션 |
| Linux 4.6 (2016) | arm64 KASLR(`CONFIG_RANDOMIZE_BASE`), 엔트로피는 부트로더가 DT `/chosen kaslr-seed`로 공급 |
| Android 5.0 | SELinux 전면 enforcing — 샌드박스가 DAC와 MAC 판정 둘 다에 기댐 |
| Android 6.0 | Keymaster 1.0 HAL, 첫 표준 하드웨어 백업 Keystore(키가 EL3 너머 TEE에) |
| Android 9 | Keymaster 4.0 + StrongBox(별도 보안 칩 티어). 커널 LLVM 순방향 CFI |
| Armv8.3 / Pixel 6·Tensor | PAC(FEAT_PAuth)를 커널·유저랜드에 적용 |
| Android 12 | KeyMint(AIDL) 교체, Rust `keystore2` 데몬(EL0)이 TEE의 KeyMint TA(S-EL0)를 앞단에서 매개. 플랫폼 네이티브에 BTI 적용 시작 |
| Android 13 (GKI 5.15) | AVF + pKVM(EL2)이 호스트 커널을 EL1로 낮춰 보호 VM 격리 |
| Pixel 8 / Tensor G3 (2023, Android 14) | MTE(FEAT_MTE)를 소비자에게 처음 노출 — 힙 오버플로/UAF 탐지. 제가 재현하는 버그 클래스를 겨냥 |

PAC/BTI/MTE는 여기서는 **어디에 앉는지만** 짚고 지나갑니다(깊은 분해는 C37에서). 요점은: 이들은 "AP/XN에 더해진 MMU 권한 비트"가 **아닙니다**. PAC는 포인터에 암호 서명을 붙이는 별개 장치(MMU 비트 아님), MTE는 권한이 아니라 메모리 **타입** 속성(16바이트당 4비트 태그), BTI만 변환 테이블 비트(GP, bit50)를 씁니다.

## 질문 7 — 소스에서 확인하려면 어디를 봐야 하는가

**아키텍처 명세 (Arm ARM, DDI 0487)**
- 예외 모델(EL, 예외 진입/복귀, `ERET`, Illegal Exception Return): Part D "AArch64 Exception Model"
- 가상 메모리(디스크립터 포맷, AP[2:1], PXN/UXN, stage-1/2 조합): Part D "The AArch64 Virtual Memory System Architecture (VMSA)"
- 레지스터: `SCR_EL3`(NS/EEL2), `HCR_EL2`(E2H/TGE/TSC), `SCTLR_EL1`(M/WXN/SPAN), `TCR_EL1`, `TTBR0/1_EL1`, `PSTATE.PAN`

**Linux 커널 (arm64)**
- `Documentation/arch/arm64/memory.rst` — TTBR0/TTBR1 분할, 커널 VA 레이아웃
- `Documentation/arch/arm64/booting.rst` — 커널 진입 EL, `kaslr-seed`
- `Documentation/arch/arm64/elf_hwcaps.rst` — `/proc/cpuinfo`에 찍히는 HWCAP 문자열의 진짜 목록
- `arch/arm64/include/asm/pgtable-prot.h` — `PTE_PXN`/`PTE_UXN`이 사용자/커널 pgprot에 어떻게 들어가는지
- `arch/arm64/include/asm/uaccess.h` — `uaccess_enable/disable`가 PSTATE.PAN을 토글하는 지점
- `arch/arm64/kernel/cpufeature.c` — 기능 탐지와 `CPU features: detected:` dmesg 줄

**Android Emulator 또는 ARM64 Cuttlefish/QEMU에서 직접 관측**
- `adb shell cat /proc/cpuinfo` → `Features` 줄. PAC가 있으면 **`paca`·`pacg`**, BTI는 `bti`, MTE는 `mte`로 나옵니다.
- 주의: **`pan`과 `pauth`는 `/proc/cpuinfo`에서 찾으면 안 됩니다.** PAN은 애초에 유저스페이스 HWCAP이 아니고, PAC의 문자열은 `pauth`가 아니라 `paca`/`pacg`입니다. PAN 여부는 `dmesg | grep -i "cpu features"`의 `Privileged Access Never` 줄이나 커널 config로 판정합니다.
- `adb shell zcat /proc/config.gz | grep -E "PAN|PXN|RANDOMIZE|CFI|SHADOW_CALL|STRICT_KERNEL_RWX"` (config.gz가 켜져 있으면)

## 질문 8 — 이전에 학습한 개념과 어떻게 연결되는가

이 모듈은 제 기존 글들을 하나의 사다리 위에 다시 세웁니다.

- **1~4주차(이중 샌드박스)**: "UID와 SELinux 두 겹"이 특권 층으로는 **같은 EL1 한 층**이라는 것 — 그래서 커널 탈출 하나로 둘이 함께 무너진다는 것을 이제 설명할 수 있습니다.
- **13~14주차(JNI·ELF)**: 그때 직접 파싱한 네이티브 라이브러리는 **EL0**에서 실행됩니다. 난독화가 심볼을 숨기지 못한다는 관찰은, 그 코드가 여전히 가장 낮은 특권 층의 논시큐어 코드라는 사실과 이어집니다.
- **15~16주차(Binder 경계)**: "경계가 두 겹"이라던 관찰의 정체 — 커널 Binder 드라이버가 EL1에서 호출자 UID/PID를 **위조 불가능하게 도장** 찍지만, 실제 권한 **판정**(`checkCallingPermission`)은 `system_server` 같은 대상 프로세스가 **EL0**에서 합니다. 신원은 EL1이 보장하고, 정책 검사는 EL0 코드입니다.
- **CVE 재현 시리즈**: 대부분이 EL0/EL1 메모리 안전 문제였다는 것, 그리고 CVE-2022-20425는 EL 전이가 아예 아닌 EL0 논리 결함이었다는 것 — 질문 5에서 정리한 그대로입니다.
- **에이전트 샌드박스 글**: "완전 중재"라는 개념의 하드웨어판이 MMU라는 것.

다음 모듈로는 이 사다리 위에서 커널 하드닝(C37: PAC/BTI/MTE/CFI)과 SELinux 정책 언어(C23)로 갈라집니다. 둘 다 여기 EL1과 EL0의 경계를 전제로 합니다.

## 호출 흐름

두 개를 손으로 그려 보시길 권합니다. 첫째는 특권 사다리, 둘째는 하드웨어 백업 키 연산이 그 사다리를 어떻게 관통하는지입니다.

```
[ 특권 사다리 — 위로는 예외로만, 아래로는 ERET로만 ]

  논시큐어 월드                         │ 시큐어 월드
  ───────────────────────────────────┼──────────────────────────
  EL0  앱 / ART / JNI / linker64       │ S-EL0  트러스티드 앱(KeyMint TA)
        │  SVC (유일한 특권 호출)       │           │
        ▼                              │           │
  EL1  Linux 커널 + SELinux            │ S-EL1  TEE OS(Trusty)
        │  HVC                         │
        ▼                              │
  EL2  하이퍼바이저(pKVM)   ───────────┤   (Secure EL2는 v8.4+에서만)
        │  SMC                         │
        ▼                              │
  EL3  ───────────  시큐어 모니터(TF-A BL31)  ───────────
                    SCR_EL3.NS 를 뒤집어 월드 전환
```

```
[ 하드웨어 백업 키 서명 한 번이 넘는 경계들 ]

앱(EL0,NS)
  │ Binder
  ▼
keystore2 데몬(EL0,NS)
  │ KeyMint HAL
  ▼
커널(EL1,NS)  ── SELinux 여기서 판정 ──┐
  │ SMC                                │  ← 커널을 장악해도
  ▼                                    │     여기까지가 한계:
시큐어 모니터(EL3)                       │     아래로 키는 안 나온다
  │ 월드 전환                           │
  ▼                                    │
TEE OS(S-EL1) → KeyMint TA(S-EL0) ──── 평문 키는 오직 이 두 칸에만 존재
```

두 번째 그림의 오른쪽 주석이 질문 3의 비대칭을 담고 있습니다. EL0→EL1 한 칸만 넘으면 SELinux와 샌드박스가 함께 무너지지만, 같은 힘으로 EL3 아래로는 못 내려갑니다.

## 실측으로 확인한 것

이 모듈은 ARM64 하드웨어 속성을 다룹니다. 실행 환경인 x86_64 `codex-atlas-api33` AVD에서는 **EL0 논시큐어 앱이 어떤 격리 아래 놓여 있는가**를 런타임으로 실측했고, ARM64 전용 보호가 바이너리에 켜졌음을 보이는 정적 마커는 실제 arm64 바이너리를 빌드해 readelf로 직접 뽑았습니다. 런타임 EL 전이 규칙 자체는 질문 7의 공개 소스로 확정했습니다. 먼저 검증 블록의 네 명령이 확증한 것을 하나씩 붙입니다.

```console
$ id                                # 관측: 앱 UID 10174
$ cat /proc/self/attr/current       # 관측: untrusted_app
$ cat /proc/self/status             # 관측: CapEff=0, Seccomp=2
$ uname -a                          # 관측: Linux 5.15
```

**1) 질문 2·3의 "내가 통제하는 코드는 전부 EL0 논시큐어이고, 그 위 격리는 UID와 SELinux 두 겹"이 한 프로세스에서 동시에 관측됩니다.** `id`가 준 UID 10174(DAC)와 `/proc/self/attr/current`가 준 `untrusted_app` 도메인(MAC)이 같은 앱 프로세스에 함께 걸려 있습니다. 질문 3에서 "이 두 겹은 특권 층으로 보면 같은 EL1 한 층"이라고 했는데, 그 두 겹이 실제로 한 EL0 프로세스에 겹쳐 찍혀 있음을 두 값으로 확인했습니다.

**2) `CapEff=0`은 이 앱이 커널 특권을 한 조각도 들고 있지 않다는 뜻입니다.** 질문 5의 "위로 올라가는 길은 오직 예외(EL0→EL1)뿐"과 이어집니다. 앱이 이미 가진 capability로 올라가는 지름길이 없으므로, EL1에 닿으려면 시스템 콜/`ioctl`/Binder 표면을 통한 별도 커널 버그가 반드시 필요합니다 — 질문 5가 "발판과 커널 LPE는 별개의 2단계"라고 못 박은 그 이유입니다.

**3) `Seccomp=2`는 앱의 유일한 특권 호출인 `SVC` 표면마저 필터 뒤에 있다는 뜻입니다.** 배경 개념에서 "앱이 쓸 수 있는 특권 호출은 오직 `SVC` 하나"라고 세웠는데, 그 하나의 문(EL0→EL1 시스템 콜)조차 seccomp가 다시 좁히고 있음을 관측값이 보여 줍니다.

**4) `uname -a`의 Linux 5.15는 질문 6 버전 표의 좌표를 맞춰 줍니다.** 표에서 "Android 13 (GKI 5.15) — AVF + pKVM(EL2)"라고 적은 그 커널 베이스라인이 이 AVD에서 실측됩니다. pKVM 자체는 EL2라 x86_64에서 관측할 수 없지만, 그것이 올라앉는 커널 버전은 확인되었습니다.

**5) ARM64 보호가 바이너리에 실제로 켜지는지는 정적 마커로 실측했습니다.** 질문 6에서 "BTI만 변환 테이블 비트를 쓰고 PAC는 포인터에 암호 서명을 붙이는 별개 장치"라고 세웠는데, 그 두 보호가 켜진 코드에는 링커가 `.note.gnu.property`에 `BTI, PAC` 세트를 심습니다. 실제 arm64 바이너리를 빌드해 그 마커를 readelf로 직접 뽑았습니다.

```console
$ readelf -h libatlas-arm64.so | grep Machine       # 실제 빌드한 arm64 .so
  Machine:                           AArch64
$ readelf -n libatlas-arm64.so                       # .note.gnu.property
Displaying notes found in: .note.gnu.property
  GNU                  0x00000010  NT_GNU_PROPERTY_TYPE_0 (property note)
    Properties:    aarch64 feature: BTI, PAC
# 대조군(-mbranch-protection=none): 같은 note 매치 수 = 0  → 대조 성립
```

x86_64 AVD 위에서 실행되는 이 세션에서도, ARM64 보호가 **바이너리 수준에서 켜졌다는 정적 증거**는 이렇게 실측으로 남습니다. 런타임 강제 규칙(EL 전이·PAN/PXN·MTE 태그 검사) 자체와 시큐어 월드 키 비대칭은 아키텍처 명세와 AOSP 소스로 확정했으며, 아래 「소스로 확정한 것」에 정리합니다.

## 소스로 확정한 것

런타임으로 굳힌 위 다섯 값 위에, ARM64 전용 층과 하드웨어 보안의 동작 규칙은 아키텍처 명세와 AOSP 소스로 확정했습니다. 정적 마커(실측 5)와 짝을 지어 "마커는 실측, 런타임 동작은 소스 확정"으로 읽으면 됩니다.

- **ARM64 예외 수준 전이와 하드웨어 메모리 보호의 강제 규칙.** EL0→EL1 `SVC` 트랩, PAN(FEAT_PAN)이 EL1의 사용자 페이지 데이터 접근을 폴트내는 규칙, PXN이 EL1의 사용자 페이지 실행을 막는 규칙, PAC/BTI/MTE의 동작은 [Arm Architecture Reference Manual Part D(예외 모델·VMSA)](https://developer.arm.com/documentation/ddi0487/latest)와 [Linux arm64 소스·문서](https://www.kernel.org/doc/html/latest/arch/arm64/index.html)(`pgtable-prot.h`의 `PTE_PXN`/`PTE_UXN`, `uaccess.h`의 PAN 토글, `cpufeature.c`의 기능 탐지)에서 확정했습니다. 그리고 이 보호가 바이너리에 실제로 켜졌음을 나타내는 정적 마커 — arm64 `.note.gnu.property`의 `BTI, PAC` 세트 — 는 위 실측 5로 직접 뽑았습니다. 즉 마커는 실측, 런타임 강제는 소스 확정입니다.
- **질문 3의 키 비대칭(평문 키는 시큐어 월드 밖으로 나오지 않는다).** [Android Keystore 하드웨어 백업 키](https://source.android.com/docs/security/features/keystore) 문서와 key attestation의 security level 정의(`SOFTWARE`/`TRUSTED_ENVIRONMENT`/`STRONGBOX`)에서 확정했습니다. 키가 TEE·StrongBox에 격리되어 논시큐어 커널로 나오지 않는다는 계약이 문서에 명시돼 있어, 논시큐어 EL1(전체 커널)을 완전히 쥐어도 서명·복호 **연산 요청**까지만 가능하다는 질문 3의 결론이 소스로 뒷받침됩니다.
- **pKVM(EL2) 보호 VM 격리와 커널 익스의 EL 위치.** 보호 VM이 호스트 커널로부터 숨겨진다는 계약은 [Android Virtualization Framework(pKVM)](https://source.android.com/docs/core/virtualization) 문서로 확정했습니다. 질문 5가 든 커널 익스(Bad Binder = CVE-2019-2215, Mali 드라이버 버그)의 EL 위치는 각 CVE의 공개 소스·패치로 확정했습니다. 이 시리즈는 비무기화 원칙에 따라 판정 지점까지만 다루므로, 동작하는 익스 실행은 설계상 범위 밖입니다.

## 마치며

24주 동안 저는 "경계는 한 겹이 아니다"를 관찰로 여러 번 확인했지만, 그 경계들이 CPU의 어느 층에서 강제되는지는 모른 채였습니다. 이제 그 층이 EL0/EL1/EL2/EL3라는 사다리로 정리됩니다. 앱 샌드박스와 SELinux가 **같은 EL1**에서 강제되기에 커널 탈출 하나가 둘을 함께 무너뜨리고, Keystore 키는 **EL3 너머**에 있기에 그 커널 탈출로도 못 빼냅니다. 제가 재현한 버그들의 위치(EL0 코덱·블루투스, EL0 논리 결함인 CVE-2022-20425)도 이 사다리 위에서 "발판이냐 커널 장악이냐"가 분명해집니다.

다음은 이 사다리 위에서 커널 하드닝(C37)과 SELinux 정책 언어(C23)로 갈라집니다. 이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.
