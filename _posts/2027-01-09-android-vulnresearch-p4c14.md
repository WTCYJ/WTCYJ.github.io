---
layout: post
title: "이미지 baseline/patched 비교"
date: 2027-01-09 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, 패치분석, BinDiff, 팩토리이미지, APEX]
excerpt: "같은 CVE라도 고친 코드가 system.img가 아니라 media APEX 안에 들어 있을 수 있다. 그리고 몇 달 떨어진 두 빌드를 비교하면 한두 함수짜리 보안 수정이 컴파일러·리팩터 노이즈에 파묻힌다 — baseline/patched는 SPL을 사이에 끼운 인접 빌드로만 좁혀야 한다."
---

Security Bulletin은 "무엇을 고쳤다"를 CVE와 SPL로 알려주지만, **어디를 어떻게 고쳤는지**는 대개 알려주지 않는다. AOSP 오픈 컴포넌트면 링크된 커밋을 읽으면 되지만, 벤더 prebuilt·클로즈드 바이너리·그리고 "출하된 이미지가 정말 그 수정을 담고 있나"를 확인해야 할 때는 소스만으로 부족하다. 그래서 취약점 연구의 기본기 하나가 **같은 컴포넌트의 취약 버전(baseline)과 수정 버전(patched)을 나란히 놓고 diff** 하는 것이다.

이 글은 공개 Pixel 팩토리/OTA 이미지에서 baseline·patched 아티팩트를 꺼내고, 소스·바이너리 두 층위로 비교해 보안 수정의 위치와 성격을 좁히는 워크플로를 **정리·실습**한 기록이다. 대상은 전부 이미 패치되어 불리틴에 공개된 CVE와 Google이 공개 배포하는 이미지뿐이다.

> **한 줄 결론**: baseline/patched 비교의 성패는 **두 빌드를 얼마나 가깝게 잡느냐**로 갈린다. SPL 하나만 사이에 끼운 인접 빌드를 골라야 한두 함수짜리 보안 델타가 보이고, 그 델타가 어느 아티팩트(system.img인지 media APEX인지)에 있는지를 먼저 정해야 헛다이빙을 피한다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 세 가지다 — (1) 공개 이미지에서 아티팩트를 추출하는 파이프라인(sparse 해제·동적 파티션 분해·APEX 언팩), (2) 소스 diff와 바이너리 구조 diff의 선택 기준, (3) 인접 빌드 선정과 그 함정. 선수 지식으로는 Security Bulletin이 CVE를 SPL(예: `2024-XX-05`)로 묶어 배포한다는 점(이 파트 3장, patch provenance), 그리고 Android 10 이후 이미지가 정적 `system.img`에서 동적 파티션·Mainline 모듈로 쪼개졌다는 점을 알고 있어야 한다. 스트립·심볼 개념(Atlas의 네이티브 빌드 편)도 밑에 깔린다.

전체 구조에서 이 장은 "패치를 손에 넣는" 단계다. 다음 장(15장, patch-gap·backport 누락)이 "그 패치가 내 기기엔 실제로 왔나"를, 18장(보안 패치 회귀 검증)이 "고친 게 정말 안 터지나"를 다룬다. 이 셋은 전부 baseline/patched 두 이미지를 손에 쥐고 있어야 시작된다.

## 핵심 개념 — 무엇을, 어디에서, 무엇으로 비교하나

먼저 **어디에** 수정이 들어갔는지를 정해야 한다. Android는 하나의 통짜 이미지가 아니라 여러 아티팩트로 쪼개져 있고, 같은 CVE라도 컴포넌트에 따라 사는 곳이 다르다.

| 아티팩트 | 담기는 것 | 꺼내는 법 |
|--|--|--|
| `boot.img` | 커널·ramdisk | `unpack_bootimg`(AOSP) / abootimg |
| `super.img` (Android 10+) | system·vendor·product·system_ext 논리 파티션 | 팩토리 zip이면 개별 sparse 이미지 → `simg2img` → 마운트 / (populated `super.img`를 가진 경우) `simg2img` → `lpunpack` → 마운트 |
| `*.apex` / `*.capex` (Mainline) | 업데이트 가능 모듈(media, conscrypt, tzdata 등) | `deapexer` / apex 도구 |
| `*.apk` (framework prebuilt·앱) | DEX·리소스·prebuilt `.so` | `apktool` / `unzip` |

여기서 이 파트의 미디어 파서 표면과 직결되는 함정 하나 — Android 10의 Project Mainline 이후 미디어 관련 컴포넌트 상당수가 `system.img`가 아니라 **media APEX(예: com.android.media / com.android.media.swcodec)** 로 옮겨 갔고, 이 모듈들의 보안 수정은 월간 전체 OTA가 아니라 Google Play 시스템 업데이트로 따로 배포될 수 있다. `Reported` 그래서 미디어 CVE를 잡겠다고 `system.img`만 diff 하면 고친 코드가 아예 그 안에 없을 수 있다. 불리틴이 framework/system/Mainline 패치 레벨을 나눠 찍는 이유가 여기다. `Reported`

**어떤 도구로** 비교할지는 소스 유무로 갈린다.

- AOSP 오픈 컴포넌트 → 불리틴이 링크한 커밋을 소스 diff(`git show <commit>`)로 읽는 게 가장 정확하다. `Source-confirmed`
- 스트립된 벤더/prebuilt `.so` → 심볼이 없으니 이름 매칭이 안 된다. CFG·기본블록 구조로 함수를 매칭하는 **BinDiff·Diaphora·radiff2** 같은 구조 diff가 필요하다. `Source-confirmed`
- 목적이 "출하 이미지가 정말 고쳐졌나"(패치 검증)라면 소스가 있어도 **바이너리 diff가 필수**다. 소스와 실제 배포 바이너리는 다를 수 있다.

내 경험으로 얹자면, 소스가 있을 때 diff는 이보다 훨씬 친절하다. 예전에 wabt에 제보한 파서 버그는 수정 커밋 하나에 **고친 라인과 그걸 검증하는 회귀 테스트가 같이** 들어왔고, 그 테스트 입력이 내가 낸 PoC 그대로였다 — 커밋 한 개가 baseline/patched를 다 설명해 줬다. 바이너리 diff는 그 "커밋 한 개"를 소스 없이 재구성하는 작업이다.

> **[그림 1]** Pixel 팩토리 이미지 다운로드 페이지에서 대상 CVE의 SPL을 사이에 끼운 **인접 두 빌드**(빌드 ID와 각 빌드의 Security patch level 표기)를 나란히 표시한 화면 — *실측 스크린샷 자리*

## 실습 환경과 안전 범위

전부 **공개 배포물과 이미 패치된 CVE**로만 진행한다. 대상 이미지는 Google이 공개하는 Pixel 팩토리 이미지·전체 OTA뿐이고, 벤더 유출본·비공개 펌웨어는 쓰지 않는다. 산출물은 취약점의 위치와 성격을 이해하는 수준의 개념 분석이며, 완성형 익스플로잇·무기화는 다루지 않는다. 추출·마운트는 Windows에서 ext4 마운트·sparse 처리가 번거로워 **WSL/Linux**에서 돌린다.

## 실습 절차와 관측

### 가설
- **가설 A** — SPL 하나만 사이에 끼운 인접 두 빌드를 바이너리 구조 diff 하면, 대상 라이브러리에서 유사도 1.0 미만으로 떨어지는 함수가 **소수(한두 개)** 로 좁혀지고 그중 하나가 보안 수정이다. `Inferred`
- **가설 B** — 반대로 몇 달 떨어진 두 빌드를 비교하면 컴파일러·리팩터 변경까지 섞여 UNMATCH 함수가 수백 개로 불어나 신호가 파묻힌다. `Inferred`

### 절차
1. 대상 CVE의 SPL을 불리틴에서 확인하고, 그 SPL을 **사이에 끼운** 두 빌드(이전=baseline, 이후=patched)를 팩토리/OTA 목록에서 고른다.
2. 각 이미지에서 대상 아티팩트를 추출한다(아래).
3. 소스가 있으면 커밋 diff로 1차 확인, 스트립 prebuilt면 구조 diff로 변경 함수를 좁힌다.
4. 좁혀진 함수의 추가된 코드(경계 검사·길이 검증·null 체크 등)로 취약점 클래스를 읽는다.

```bash
# 팩토리 이미지 zip 안의 image-<build>.zip 을 먼저 푼다
# → super_empty.img(메타데이터만 든 빈 이미지) + 개별 sparse 파티션(system.img, vendor.img, product.img, system_ext.img)
unzip image-<build>.zip

# 개별 sparse 파티션을 raw 로 → 읽기전용 마운트
# (최신 빌드는 system/vendor/product 가 erofs 일 수 있음 — mount 는 파일시스템 자동 감지)
simg2img system.img system.raw.img
sudo mount -o ro,loop system.raw.img /mnt/sys    # 여기서 대상 .so/.apk 추출
# (미디어 CVE면 system.img 대신 media APEX: deapexer extract com.android.media.apex media_out/)

# [대안] 기기 super 파티션을 덤프했거나 통합(populated) super.img 를 가진 경우에만 lpunpack
#   simg2img super.img super.raw.img              # sparse 일 때만, 이미 raw 면 생략
#   lpunpack super.raw.img out/                   # → out/system.img ... (출력은 이미 raw, sparse 아님)
#   sudo mount -o ro,loop out/system.img /mnt/sys # raw 입력에 simg2img 다시 걸면 Bad magic 으로 실패

# 스트립된 prebuilt 라이브러리 구조 diff (baseline vs patched)
radiff2 -AC libtarget_base.so libtarget_patched.so
```

> **[그림 2]** `radiff2 -AC`(또는 BinDiff) 출력에서 유사도 1.0 미만으로 떨어진 단일 함수가 보안 수정 후보로 드러난 화면 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(네 실제 실행으로 교체 — 스트립 바이너리라 이름은 `fcn.*` 주소로 나온다):

```
$ radiff2 -AC libtarget_base.so libtarget_patched.so
fcn.00008a10   0x8a10 |   MATCH  (1.000000) | 0x8a10   fcn.00008a10
fcn.00009120   0x9120 | UNMATCH  (0.847458) | 0x9160   fcn.00009160
fcn.0000b3d0   0xb3d0 |   MATCH  (1.000000) | 0xb410   fcn.0000b410
...
(전체 함수 412개 중 UNMATCH 1개)
```

인접 빌드에서 UNMATCH가 **한 개**로 좁혀지면(가설 A) 그 함수 하나를 디컴파일해 추가된 검사만 읽으면 된다. 반대로 UNMATCH가 수백 개면(가설 B) 빌드를 잘못 벌려 잡은 것이니 더 가까운 쌍으로 다시 좁힌다. 즉 이 워크플로의 산출물은 "취약점 위치"가 아니라 **정확한 빌드 쌍**에서 먼저 나온다.

## Root Cause — 왜 이렇게 되는가

baseline/patched diff가 성립하는 근본 이유는, 월간 보안 릴리스가 **그 달에 바뀐 것만** 바꾸기 때문이다. SPL 하나를 사이에 둔 두 빌드의 차이는 이상적으로 그 SPL이 담은 수정들뿐이고, 특정 CVE 하나로 좁히면 대개 함수 한두 개의 델타로 수렴한다. 그래서 diff가 보안 수정을 **국소화**한다. 반대로 두 빌드를 멀리 벌리면 델타에 컴파일러 업그레이드·리팩터·무관한 기능 변경이 전부 섞여 들어와, 한두 함수짜리 보안 신호가 노이즈에 묻힌다. 이게 "인접 빌드로만 좁혀라"의 근거다. `Inferred`

스트립이 문제를 어렵게 만드는 것도 구조적이다. 출하 `.so`는 심볼이 제거돼 이름으로 함수를 짝지을 수 없다. 그래서 BinDiff·Diaphora는 함수의 제어흐름 그래프·기본블록·호출 관계 같은 **구조**로 두 바이너리의 같은 함수를 매칭하고, 매칭된 쌍의 유사도가 1.0에서 떨어지는 지점을 변경으로 읽는다. `Source-confirmed` 소스가 있으면 이 재구성이 통째로 생략되므로, 바이너리 diff는 어디까지나 **소스가 없거나 배포본을 못 믿을 때**의 도구다.

## 버전 차이와 한계

- **정적 → 동적 파티션**: Android 10 이전은 `system.img`를 직접 마운트하면 됐지만, 10 이후 동적 파티션에선 `super.img`를 `lpunpack`으로 논리 파티션으로 쪼갠 뒤에야 접근된다. sparse/raw 변환 단계도 여기서 추가된다. `Source-confirmed`
- **Project Mainline**: 미디어·conscrypt·tzdata 등은 APEX 모듈로 빠져 Google Play 시스템 업데이트로 갱신될 수 있어, 전체 OTA만 봐선 수정이 안 보인다. 대상 컴포넌트가 Mainline인지 먼저 확인해야 한다. `Reported`
- **압축 APEX(.capex)**: Android 12 이후 일부 APEX가 압축 형태로 배포돼, 언팩 전에 해제 단계가 하나 더 붙는다 — 정확한 도구·절차는 배포 버전별로 원문 재확인 필요.
- **벤더 이미지**: baseline/patched 쌍을 손쉽게 구할 수 있는 건 Google이 팩토리·OTA를 둘 다 공개하는 Pixel이라서다. 팩토리 이미지를 공개하지 않는 OEM은 두 시점 이미지를 확보하기가 어렵고, 그래서 patch-gap 연구(다음 장)의 표본이 Pixel에 치우친다. `Inferred`
- **한계**: diff는 "무엇이 바뀌었나"까지만 말해 준다. 그 변경이 정말 그 CVE인지, 재현되는지는 별개의 검증(18장)이 필요하고, 여기서 크래시를 봤다고 곧장 취약점·RCE로 부풀리면 안 된다.

## 정리

- baseline/patched는 **SPL 하나를 사이에 낀 인접 빌드**로만 좁혀야 신호가 산다 — 멀리 벌리면 diff가 노이즈로 덮인다.
- 비교 전에 **어디에** 수정이 사는지부터 정한다: system.img인지, 벤더 prebuilt인지, media 같은 **APEX**인지. Mainline이면 system.img엔 없다.
- 소스가 있으면 커밋 diff가 정답, 스트립 바이너리면 구조 diff(BinDiff/Diaphora/radiff2), 배포본 검증이 목적이면 소스가 있어도 바이너리 diff를 쓴다.
- diff의 산출물은 "취약점 위치"이자 그전에 "정확한 빌드 쌍"이다 — 변경 함수가 소수로 안 좁혀지면 빌드 선정을 의심한다.

**점검 질문** — (1) 미디어 CVE인데 `system.img`를 아무리 diff 해도 변경이 안 보인다. 어디를 대신 봐야 하나? (2) 왜 두 빌드를 멀리 벌리면 안 되는가? (3) 심볼이 없는 출하 `.so`를 이름 대신 무엇으로 매칭하나?

**참고** — [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · [Pixel 팩토리 이미지](https://developers.google.com/android/images) · [전체 OTA 이미지](https://developers.google.com/android/ota) · [AOSP 동적 파티션](https://source.android.com/docs/core/architecture/partitions) · [BinDiff(오픈소스)](https://github.com/google/bindiff) · [Diaphora](https://github.com/joxeankoret/diaphora)

*다음 글: [patch-gap·backport 누락](/posts/android-vulnresearch-p4c15/).*
