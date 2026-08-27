---
layout: post
title: "Android Security Concept Atlas - 전체 지도 (티어별 목차와 진행 현황)"
date: 2026-08-29 09:00:00 +0900
category: 블로그/기술문서
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, 목차, 로드맵, 학습기록]
excerpt: "파편적인 도구 사용법이 아니라 하나의 시스템 모델로 Android 보안을 잇는 개념 지도입니다. 56개 모듈을 10개 티어로 묶고, 각 모듈의 판정(충분/보완/미학습)·난이도·선수 개념·상태를 한눈에 정리했습니다. 이 글은 Atlas 전체의 항해도이자, 완주 동안 채워지는 진행 현황판입니다."
---

> **Concept Atlas 인덱스** — 전체 56개 모듈의 티어별 지도
> **읽는 법**: 각 모듈은 8개 필수 질문(전체 구조 위치 / 프로세스·권한 / 신뢰 경계 / 입출력 / 실패→취약점 / 버전 차이 / 소스 확인 / 기존 개념 연결)에 답하고, 호출 흐름·오개념 5·서술형 3·소스 탐색·블로그 초안 과제로 닫습니다.
> **상태 범례**: ✅완성 · ✍️집필 중 · 🧩진단편(내 블로그가 이미 다룸) · ⬜계획
> **판정 범례**: 🟢충분 · 🟡보완 · 🔴미학습

이 지도는 24주 스터디와 CVE 재현 10편에서 얻은 파편들을 **하나의 시스템 모델**로 잇습니다. 아래 표에서 "판정"은 내 기존 블로그 대비 학습 상태이고, "상태"는 Atlas 글의 집필 진행입니다. 우선순위 Top 5는 **C05·C37·C28·C23·C40**이었고 전부 완성했습니다.

## 티어별 허브 글

각 계층은 독립된 허브 글로도 정리했습니다 — 그 계층의 서사와 모듈 목록·핵심 한 줄·링크를 한 페이지에서 훑을 수 있습니다.

- [Tier 0 — 보안·시스템 기초](/posts/android-concept-atlas-tier0-foundations/)
- [Tier 1 — 앱·패키징](/posts/android-concept-atlas-tier1-app-packaging/)
- [Tier 2 — Android Runtime](/posts/android-concept-atlas-tier2-runtime/)
- [Tier 3 — IPC·프레임워크](/posts/android-concept-atlas-tier3-ipc-framework/)
- [Tier 4 — 플랫폼 격리](/posts/android-concept-atlas-tier4-platform-isolation/)
- [Tier 5 — 부팅·업데이트 체인](/posts/android-concept-atlas-tier5-boot-chain/)
- [Tier 6 — Native·커널](/posts/android-concept-atlas-tier6-native-kernel/)
- [Tier 7 — 하드웨어 기반 보안](/posts/android-concept-atlas-tier7-hardware-security/)
- [Tier 8 — 앱 보안 통제](/posts/android-concept-atlas-tier8-app-controls/)
- [Tier 9 — 취약점 연구](/posts/android-concept-atlas-tier9-vuln-research/)

---

## Tier 0 — 보안·시스템 기초 (Domain 1)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C01 | 자산·주체·신뢰경계·공격표면 | 🟡 | 기초 | 🧩 진단 10문(로드맵 글) | — |
| C02 | 인증 vs 인가 | 🟡 | 기초 | ✅ [글](/posts/android-concept-atlas-c02-authn-authz/) | C01 |
| C03 | 최소권한·완전중재·심층방어 | 🟡 | 기초 | ✅ [글](/posts/android-concept-atlas-c03-security-principles/) | C01 |
| C04 | 프로세스·가상메모리·시스템 콜 | 🔴 | 기초 | ✅ [글](/posts/android-concept-atlas-c04-process-vm-syscall/) | — |
| **C05** | **ARM64 예외 수준·메모리 보호** | 🔴 | 중급 | ✅ [글](/posts/android-concept-atlas-c05-arm64-exception-levels/) | C04 |

## Tier 1 — 앱·패키징 (Domain 3)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C06 | APK·AAB·Split APK | 🟡 | 기초 | ✅ [글](/posts/android-concept-atlas-c06-apk-aab-split/) | C01 |
| C07 | DEX·multidex·resources.arsc | 🟢 | 기초 | 🧩 진단 | C06 |
| C08 | 서명 v1~v4·키 순환 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c08-apk-signing/) | C07 |
| C09 | UID·sharedUserId·샌드박스 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c09-uid-sandbox/) | C05, C07 |
| C10 | permission·signature perm·AppOps | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c10-permissions-appops/) | C09 |
| C11 | package visibility·URI permission | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c11-package-visibility-uri-permission/) | C09 |

## Tier 2 — Android Runtime (Domain 4)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C12 | Zygote·앱 프로세스 생성 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c12-zygote/) | C04, C09 |
| C13 | ART: DEX→OAT→VDEX | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c13-art-dex-oat-vdex/) | C07 |
| C14 | class loading·reflection | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c14-classloader-reflection/) | C13 |
| C15 | JNI 경계·native lib loading | 🟢 | 중급 | 🧩 진단(13~14주차) | C13 |
| C16 | JIT/AOT와 분석 결과 차이 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c16-jit-aot-analysis/) | C13 |

## Tier 3 — IPC·프레임워크 (Domain 5)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C17 | Binder driver·handle·node·transaction | 🟡 | 고급 | ✅ [글](/posts/android-concept-atlas-c17-binder-driver/) | C04, C12 |
| C18 | Parcel 직렬화·read/write 불일치 | 🟢 | 고급 | 🧩 진단(CVE 재현 9) | C17 |
| C19 | servicemanager·system_server | 🟡 | 고급 | ✅ [글](/posts/android-concept-atlas-c19-servicemanager-systemserver/) | C17 |
| C20 | AIDL·HIDL·HAL | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c20-aidl-hidl-hal/) | C17 |
| C21 | 4대 컴포넌트↔Binder 연결 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c21-components-binder/) | C17 |
| C22 | caller UID/PID·identity clearing·confused deputy | 🟢 | 고급 | 🧩 진단(20~24주차) | C17 |

## Tier 4 — 플랫폼 격리 (Domain 6)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| **C23** | **SELinux domain·type·allow·neverallow** | 🟡 | 고급 | ✅ [글](/posts/android-concept-atlas-c23-selinux-policy/) | C05, C09 |
| C24 | seccomp·namespaces·cgroups·capabilities | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c24-seccomp-namespaces-cgroups-capabilities/) | C04 |
| C25 | isolatedProcess·app zygote | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c25-isolatedprocess-appzygote/) | C12, C24 |
| C26 | 샌드박스 vs SELinux 역할 구분 | 🟢 | 중급 | 🧩 진단(1~4주차) | C23 |

## Tier 5 — 부팅·업데이트 체인 (Domain 2)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C27 | Boot ROM·bootloader·boot.img·init | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c27-bootrom-bootloader-init/) | C05 |
| **C28** | **AVB·vbmeta·dm-verity** | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c28-verified-boot-avb/) | C27, C08 |
| C29 | rollback protection·롤백 인덱스 | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c29-rollback-protection/) | C28 |
| C30 | A/B OTA·dynamic partitions·super.img | 🔴 | 중급 | ✅ [글](/posts/android-concept-atlas-c30-ab-ota-dynamic-partitions/) | C27 |
| C31 | Treble·GSI·Mainline·APEX | 🔴 | 중급 | ✅ [글](/posts/android-concept-atlas-c31-treble-gsi-mainline-apex/) | C30 |
| C32 | system/vendor/product/odm 신뢰관계 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c32-partition-trust/) | C31, C23 |

## Tier 6 — Native·커널 (Domain 7)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| **C33** | **ELF·linker·PLT/GOT** | 🟡 | 고급 | ✅ [글](/posts/android-concept-atlas-c33-elf-linker-plt-got/) | C15 |
| C34 | ioctl·device node (Binder=ioctl) | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c34-ioctl-device-node/) | C17 |
| C35 | Android Common Kernel·GKI·KMI | 🟡 | 고급 | ✅ [글](/posts/android-concept-atlas-c35-gki-kmi/) | C27 |
| C36 | vendor driver·HAL 공격 표면 | 🔴 | 연구 | ✅ [글](/posts/android-concept-atlas-c36-vendor-driver-attack-surface/) | C34, C20 |
| **C37** | **ASLR·NX·canary·CFI·PAC·BTI·MTE** | 🔴 | 연구 | ✅ [글](/posts/android-concept-atlas-c37-exploit-mitigations/) | C05, C33 |
| C38 | ASan·HWASan·KASAN·UBSan | 🟡 | 고급 | ✅ [글](/posts/android-concept-atlas-c38-sanitizers/) | C33 |

## Tier 7 — 하드웨어 기반 보안 (Domain 8)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| **C39** | **TEE·Trusty·시큐어 월드** | 🔴 | 연구 | ✅ [글](/posts/android-concept-atlas-c39-tee-trusty-secure-world/) | C05, C27 |
| **C40** | **Keystore·KeyMint·StrongBox** | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c40-keystore-keymint-strongbox/) | C39 |
| C41 | Gatekeeper·Weaver·biometrics | 🔴 | 고급 | ✅ [글](/posts/android-concept-atlas-c41-gatekeeper-weaver-biometrics/) | C39 |
| C42 | key attestation·root of trust | 🔴 | 연구 | ✅ [글](/posts/android-concept-atlas-c42-key-attestation/) | C40, C28 |
| C43 | FBE(파일기반 암호화)·Direct Boot | 🔴 | 중급 | ✅ [글](/posts/android-concept-atlas-c43-fbe-direct-boot/) | C40 |

## Tier 8 — 앱 보안 통제 (Domain 9)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C44 | 안전한 저장소·백업·키 관리 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c44-secure-storage-backup/) | C40 |
| C45 | 인증·세션·OAuth/OIDC·passkey | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c45-auth-session-oauth-passkey/) | C10 |
| C46 | TLS·Network Security Config·pinning | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c46-tls-nsc-pinning/) | C09 |
| C47 | WebView·딥링크·IPC 공격면 | 🟢 | 중급 | 🧩 진단(5~8주차·Toss) | C11, C21 |
| C48 | Play Integrity·앱 무결성 | 🟡 | 중급 | ✅ [글](/posts/android-concept-atlas-c48-play-integrity/) | C08 |
| C49 | 서드파티 SDK·SBOM·공급망 | 🔴 | 중급 | ✅ [글](/posts/android-concept-atlas-c49-thirdparty-sdk-supplychain/) | C06 |
| C50 | 개인정보 최소화·권한 모델 변화 | 🟡 | 기초 | ✅ [글](/posts/android-concept-atlas-c50-privacy-minimization/) | C10, C11 |

## Tier 9 — 취약점 연구 (Domain 10)

| # | 개념 | 판정 | 난이도 | 상태 | 선수 |
|--|--|--|--|--|--|
| C51 | crash·bug·vuln·exploit 구분 | 🟢 | 기초 | 🧩 진단(CVE 시리즈) | — |
| C52 | CWE·CVE·Security Bulletin 판독 | 🟢 | 중급 | 🧩 진단(18주차·CVE 5) | — |
| C53 | patch diff·variant analysis | 🟢 | 고급 | 🧩 진단(CVE 7·8·10) | C52 |
| C54 | 재현성·대조군 설계 | 🟢 | 고급 | 🧩 진단(19~24주차) | — |
| C55 | 위협모델·실제 영향 산정 | 🟢 | 중급 | 🧩 진단 | C01 |
| C56 | responsible disclosure | 🟡 | 기초 | ✅ [글](/posts/android-concept-atlas-c56-responsible-disclosure/) | C55 |

---

## 진행 현황 — 완주(C56까지)

- **완성(✅) 44편**: 풀 아티클로 써야 할 모든 모듈을 완료했습니다 — C02·C03·C04·C05·C06·C08·C09·C10·C11·C12·C13·C14·C16·C17·C19·C20·C21·C23·C24·C25·C27·C28·C29·C30·C31·C32·C33·C34·C35·C36·C37·C38·C39·C40·C41·C42·C43·C44·C45·C46·C48·C49·C50·C56. **Tier 0~9 전 계층 완결**, 우선순위 Top 5(C05·C37·C28·C23·C40) 포함.
- **진단편(🧩) 11편**: 내 블로그가 이미 충분히 다룬 개념은 풀글 대신 진단 문제로 대체합니다(C01·C07·C15·C18·C22·C26·C47·C51·C52·C53·C54·C55).
- 부팅 첫 바이트(C27)부터 책임 있는 공개(C56)까지, 56개 모듈이 하나의 시스템 지도가 되었습니다.

## 완주 원칙

- 모든 글은 발행 전 **실제 명령 출력·스크린샷**으로 증적화합니다(개념편은 초안, 실측은 블로그 초안 과제에서).
- 실기기 필요 여부: C37·C33·C39·C40은 arm64 실기기(PAC/MTE=Pixel), C28은 실기기 또는 팩토리 이미지, **C23(SELinux)·C40 attestation 파싱은 에뮬(`sec-api33`)로도 가능**.
- 각 글은 앞 글의 검증된 사실 위에 서고, "이전 개념과 어떻게 연결되는가"로 지도를 촘촘히 엮습니다.
