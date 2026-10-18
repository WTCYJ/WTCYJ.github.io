---
layout: post
title: "APEX·Mainline·모듈 업데이트"
date: 2026-12-05 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, APEX, Mainline, apexd]
excerpt: "Mainline 모듈은 앱처럼 즉시 반영되지 않는다 — APEX는 재부팅 때 apexd가 dm-verity로 검증해 /apex에 마운트하는 staged 컨테이너이고, 서명 키가 pre-installed와 다르면 업데이트 자체가 거부된다."
---

Android의 보안 패치가 예전엔 OEM의 전체 OTA를 기다려야 도착했다. Project Mainline은 이 흐름을 바꿔서, 미디어 코덱·Conscrypt·PermissionController 같은 시스템 구성요소를 OS 전체를 갈아엎지 않고 Google Play를 통해 따로 갱신한다. 그 그릇이 APEX(Android Pony EXpress) 컨테이너다. 문제는 APEX가 이름만 APK를 닮았을 뿐, 설치·검증·활성화 방식이 전혀 다르다는 점이다 — 이 차이를 모르면 "왜 모듈 업데이트는 재부팅을 요구하지?"에서 막힌다.

이 글은 APEX 컨테이너의 구조와 apexd의 활성화 경로, 그리고 Mainline이 TCB(신뢰 컴퓨팅 기반) 일부를 어떻게 갱신 가능한 것으로 만드는지를 AOSP 1차 문서와 에뮬레이터 관측으로 정리한 기록이다.

> **한 줄 결론**: APEX는 앱이 아니라 dm-verity로 무결성 검증되어 `/apex`에 마운트되는 시스템 컨테이너다. Mainline이 전체 OTA 없이 TCB 일부를 교체할 수 있는 이유가 여기 있고, 그 안전의 축은 "pre-installed와 같은 키 서명 + 다운그레이드 금지 + staged 재부팅 활성화"다.

## 무엇을 다루고, 무엇을 알아야 하는가

이 글의 범위는 세 가지다. (1) APEX 파일이 내부에 무엇을 담는가, (2) apexd가 부팅 때 그것을 어떻게 검증·마운트하는가, (3) Mainline이 어떤 신뢰 경계 변화를 만드는가. 무기화된 익스플로잇이나 서명 우회 시도는 다루지 않는다 — 전부 공개 AOSP 소스와 자작 에뮬레이터 관측 수준이다.

선수 개념 셋이 밑에 깔린다. 11장(PackageManagerService)의 APK 서명 검증을 알아야 APEX의 "이중 서명"이 왜 다른지 보이고, dm-verity와 Verified Boot(Atlas C28 계열)를 알아야 APEX 페이로드가 어떻게 무결성을 얻는지 이해된다. 마지막으로 롤백 방지(Atlas C29)는 APEX 다운그레이드가 왜 막히는지와 직결된다.

전체 구조에서 APEX는 "빌드 산출물 → 설치·업데이트 → 런타임 마운트"를 잇는 중간층이다. 17장(Soong/Android.bp)이 만든 산출물이 Mainline 채널을 타고 내려와, 이 장에서 다루는 apexd에 의해 `/apex` 아래 마운트되고, 그 위에서 ART·미디어·네트워크 스택이 돈다.

## 핵심 개념 — APEX 컨테이너와 apexd 활성화

APEX 파일은 겉보기엔 zip이지만 APK와 담는 것이 다르다. `Source-confirmed`

| 구성요소 | 역할 |
|--|--|
| `apex_manifest.pb`(구 `.json`) | 모듈 이름·versionCode |
| `AndroidManifest.xml` | PackageManager가 인식하는 메타데이터 |
| `apex_payload.img` | ext4 파일시스템 이미지 + dm-verity 해시 트리/메타데이터 |
| `apex_pubkey` | 페이로드(root hash) 서명을 검증할 공개키 |

여기서 흔한 오개념 하나 — APEX는 **두 번 서명된다**. 컨테이너 전체(zip)는 apksigner(APK 서명 스킴)로, 그 안의 `apex_payload.img`는 dm-verity root hash가 `apex_pubkey`에 대응하는 키로 별도 서명된다. 업데이트는 이 **둘 다** pre-installed 버전과 같은 키여야 통과한다. `Source-confirmed`

`/apex/<name>`은 파일이 아니라 마운트 포인트다. apexd가 부팅 초기에 pre-installed APEX(`/system/apex/*.apex`)와 staged 업데이트(`/data/apex/active/*.apex`) 중 더 높은 버전을 골라, ① 공개키·컨테이너 서명 검증 → ② `apex_payload.img`에 loop 디바이스 연결 → ③ root hash로 dm-verity 설정 → ④ `/apex/<name>@<version>`에 마운트 → ⑤ `/apex/<name>`으로 bind-mount 한다. apexd는 zygote보다 먼저 떠서, 앱이 시작되기 전에 모듈 라이브러리가 준비되도록 한다. `Source-confirmed`

> **[그림 1]** 에뮬레이터에서 `adb shell ls -l /apex` 결과 — `com.android.*@NNN` 버전 접미사 디렉터리와 그것을 가리키는 접미사 없는 bind-mount 이름이 나란히 보이는 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

APEX가 바꾸는 것은 **신뢰 경계의 갱신 가능성**이다. Conscrypt(TLS)·미디어 코덱·DNS resolver 같은 모듈은 TCB의 일부다. 이들이 갱신 가능한 컨테이너가 되었다는 것은, 보안 패치가 OEM OTA를 기다리지 않고 도착할 수 있다는 뜻인 동시에, **업데이트 채널 자체가 새로운 신뢰 경로**가 되었다는 뜻이다.

이 경로의 방어는 세 겹이다. `Source-confirmed`

- **키 고정**: 업데이트는 pre-installed 모듈과 동일한 서명 키여야 한다. 임의 APEX를 밀어 넣을 수 없다.
- **다운그레이드 금지**: apexd는 versionCode가 현재보다 낮은 활성화를 거부한다 — 취약한 구버전으로 되돌리는 다운그레이드 공격 차단(Atlas C29 롤백 방지와 같은 결).
- **dm-verity**: 마운트된 페이로드는 읽기 전용이고 블록 단위로 해시 검증된다. 런타임에 내용을 조작하면 read 시 검증 실패한다.

위협 모델에서 이 글이 다루는 공격자는 "임의 시스템 컴포넌트를 교체하려는 자"다. 실기기 flashing·서명 우회·무기화는 범위 밖이고, 여기서는 왜 그 교체가 기본적으로 막히는지를 구조로 설명한다.

## 관측

에뮬레이터(userdebug)에서 읽기 전용으로 APEX 활성화 상태를 관측한다. 전부 자작 랩이고 시스템을 변경하지 않는다.

```bash
# 활성화된 APEX 모듈의 마운트 포인트
adb shell ls -l /apex
# 실제 마운트가 loop + dm-verity로 걸렸는지
adb shell mount | grep -E '/apex/'
# PackageManager가 인식하는 APEX 패키지 목록
adb shell pm list packages --apex-only
```

`예시 출력`(네 실제 실행으로 교체):

```
# adb shell mount | grep -E '/apex/'
/dev/block/dm-6 on /apex/com.android.tzdata@340090000 type ext4 (ro,seclabel,nodev,...)
# (loop↔dm 관계는 mount에 안 잡힌다 — `losetup -a` / `dmsetup ls`로 본다)
# adb shell pm list packages --apex-only
package:com.android.tzdata
package:com.android.conscrypt
package:com.android.mediaprovider
```

핵심은 마운트 소스가 일반 파티션이 아니라 `dm-*`(dm-verity 매핑 디바이스)라는 점이다. 이 한 줄이 "APEX 페이로드는 검증된 읽기 전용 이미지로 마운트된다"는 구조를 그대로 보여준다. 접미사 `@NNN`(예: `@340090000`)이 활성 버전이고, 재부팅 없이 이 숫자를 실시간으로 바꿀 수 없다는 것이 다음 절의 핵심이다.

> **[그림 2]** `adb shell mount | grep /apex/` 출력에서 마운트 소스가 `/dev/block/dm-N`(dm-verity)로 잡힌 줄을 강조한 화면 — *실측 스크린샷 자리*

## Root Cause — 왜 재부팅과 staged 설치가 필요한가

APEX 업데이트가 앱처럼 즉시 반영되지 않고 **staged**(재부팅 시 활성화)인 이유는 단순하다. APEX가 담는 것은 이미 실행 중인 시스템 구성요소 — 여러 프로세스에 로드된 네이티브 라이브러리, 부팅 초기에 뜬 서비스다. 이것을 실행 중에 바꿔치기하면 이미 매핑된 코드와 새 코드가 뒤섞여 일관성이 깨진다. 그래서 업데이트는 `/data/apex/active`에 staging 되고, 다음 부팅 때 apexd가 dm-verity 검증을 거쳐 **처음부터** 새 버전을 마운트한 뒤 의존 컴포넌트를 올린다. `Inferred`(문서화된 staged 모델로부터 추론)

여기에 안전망이 붙는다. staged APEX가 부팅 실패를 유발하면 RollbackManager/watchdog가 이전 상태로 되돌린다 — 그래서 원격 모듈 갱신이 기기를 벽돌로 만들 확률을 낮춘다. `Reported`

`/apex/<name>`이 파일이 아니라 bind-mount인 것도 같은 결의 설계다. 실제 페이로드는 버전 접미사가 붙은 `@<version>` 경로에 마운트되고, 접미사 없는 안정 경로는 거기로 bind-mount만 된다. 덕분에 코드는 항상 `/apex/com.android.conscrypt/...`라는 고정 경로를 참조하고, 그 뒤에서 어떤 버전이 실제로 마운트됐는지는 apexd가 갈아끼운다. `Source-confirmed`

## 버전 차이와 한계

- **도입 시점**: APEX와 Project Mainline은 Android 10(API 29)에서 도입됐다. `Source-confirmed` 이후 릴리스마다 Mainline 모듈 집합이 늘었으므로, "무엇이 Mainline 모듈인가"는 버전마다 다르다 — 특정 목록을 단언하려면 원문 재확인 필요.
- **Mainline 모듈 형식**: 모든 Mainline 모듈이 APEX는 아니다. 일부는 APK(예: PermissionController 계열), 일부는 APEX, 일부는 둘을 묶은 형태다. "Mainline = APEX"로 뭉뚱그리면 틀린다. `Reported`
- **Flattened APEX**: dm-verity·loop를 지원하지 않는 일부 구성(구형/일부 GSI·에뮬레이터)에서는 페이로드 이미지 대신 디렉터리로 펼쳐진 flattened APEX가 쓰였다. 이 경우 위에서 본 `dm-*` 마운트가 관측되지 않는다 — 에뮬레이터에서 검증이 "안 보인다"고 실기기에서도 없는 것으로 오해하면 안 된다. flattened의 지원 상태·폐기 시점은 버전 확인 필요. `Inferred`
- **관측의 한계**: 에뮬레이터에는 실제 하드웨어 신뢰 루트가 없다. APEX의 dm-verity root hash가 궁극적으로 Verified Boot 체인(vbmeta)에 묶이는 부분은 실기기에서만 온전히 관측된다. 서명 키의 하드웨어 보호는 다음 장의 KeyMint/TEE 주제로 넘어간다.

## 정리

- APEX는 앱이 아니라 dm-verity로 검증되어 `/apex`에 마운트되는 시스템 컨테이너다 — 컨테이너 서명과 페이로드 서명, 두 번 서명된다.
- Mainline은 이 컨테이너로 TCB 일부를 전체 OTA 없이 갱신한다. 방어의 축은 "같은 키 + 다운그레이드 금지 + staged 재부팅 활성화 + 실패 시 롤백"이다.
- `/apex/<name>`은 bind-mount, 실제 페이로드는 `@<version>` 경로 — 재부팅 없이 활성 버전을 바꿀 수 없는 것이 즉시 반영을 막는 근본 이유다.
- 모든 Mainline 모듈이 APEX는 아니며, flattened 구성에서는 dm-verity 마운트가 안 보인다.

**점검 질문** — (1) APEX가 "두 번 서명된다"는 것은 정확히 무엇과 무엇에 대한 서명인가? (2) Mainline 모듈 업데이트가 앱과 달리 재부팅을 요구하는 근본 이유는? (3) 에뮬레이터에서 `mount | grep /apex/`에 `dm-*`가 안 보인다면 무엇을 의심해야 하는가?

**참고** — [APEX 파일 형식](https://source.android.com/docs/core/ota/apex) · [모듈형 시스템 구성요소(Mainline)](https://source.android.com/docs/core/ota/modular-system) · [system/apex(apexd) AOSP 소스](https://android.googlesource.com/platform/system/apex/) · [Google Play 시스템 업데이트](https://support.google.com/android/answer/7680439)

*다음 글: [KeyMint·TEE·Gatekeeper·Weaver](/posts/android-expert-p2c24/).*
