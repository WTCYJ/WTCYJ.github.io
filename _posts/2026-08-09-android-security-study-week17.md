---
layout: post
title: "Android 앱 보안 분석 17주차 - AOSP 빌드 없이 패치 전·후 비교 하네스 만들기"
date: 2026-08-09 15:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, Cuttlefish, AOSP, WSL2, KVM, 에뮬레이터, 회귀비교, 측정오류, 대조군, InsecureShop, 딥링크, 학습기록]
excerpt: "로드맵 후반은 AOSP 빌드(공식 요구사항 400GB)를 전제로 설계했지만, 이 구간의 진짜 목적은 패치 전·후를 대조할 platform 을 확보하는 것이었습니다. 그 목적을 장비 범위 안에서 달성하려고, 보유한 두 에뮬레이터 이미지를 baseline/patched 역할로 놓는 비교 하네스를 설계·검증했습니다. 프로브를 만드는 동안 측정 오류를 세 번 잡아내 신뢰도를 끌어올린 정밀화 과정이 절반을 차지합니다."
---

> **진행 구간**: 24주 로드맵의 17주차 (원안: Cuttlefish 실습 → 장비 범위에 맞춰 비교 하네스로 대체 수행)
> **대상**: AVD `sec-api33`(Android 13, 패치 2024-03-01) / `sec-api36`(Android 16, 패치 2025-07-05)
> **프로브 대상**: InsecureShop `com.insecureshop` v1.0
> **이전 글**: [15~16주차 시스템 보안](/posts/android-security-study-week15-16/) · [13~14주차](/posts/android-security-study-week13-14/) · [24주 로드맵](/posts/android-security-study-roadmap/)

---

이 글은 24주 Android 보안 학습 로드맵의 17주차 기록입니다.

로드맵은 17주차를 "Linux/KVM 에서 Cuttlefish 를 띄우고 adb 연결·초기화·로그 수집을 자동화한다"로 잡아뒀습니다. 그런데 이 구간의 진짜 목적은 Cuttlefish 자체가 아니라, 19~21주차에서 쓸 **패치 전·후 비교 platform 을 확보하는 것**입니다. 이 글에서는 이 장비의 범위를 먼저 정확히 그은 뒤, 그 범위 안에서 원안의 목적을 달성하는 대체 하네스를 설계·검증하고, 나아가 교란 변수를 더 줄이는 후속 경로까지 확보한 과정을 살펴보겠습니다.

---

## 배경 개념 - Cuttlefish 와 baseline/patched 비교

[**Cuttlefish**](https://source.android.com/docs/devices/cuttlefish)는 AOSP 가 공식 제공하는 가상 기기입니다. Android Emulator 와 달리 AOSP 소스에서 직접 빌드한 이미지를 올릴 수 있어서, "패치 전 코드로 만든 이미지"와 "패치 후 코드로 만든 이미지"를 나란히 띄울 수 있습니다. 즉 프레임워크·SELinux 정책·기본값을 전부 고정한 채 **패치 커밋 하나만** 갈아끼운 쌍을 만들 수 있다는 뜻이고, 로드맵이 CVE 재현에 Cuttlefish 를 지정한 이유가 이것입니다.

**baseline / patched 비교**는 취약점 검증의 기본 구조입니다. 다른 조건을 전부 같게 두고 패치 유무만 다르게 한 두 환경에서 같은 시험을 돌려, 차이가 나오면 그 차이를 패치의 효과로 귀속시킵니다. 여기서 중요한 것은 **"다른 조건을 전부 같게"** 입니다. 이 전제가 깨지면 관측된 차이를 패치 탓으로 돌릴 수 없습니다.

[**KVM**](https://docs.kernel.org/virt/kvm/api.html)은 리눅스 커널이 CPU 가상화 확장(AMD-V/VT-x)을 사용자 공간에 노출하는 인터페이스이고, Cuttlefish 의 가상 기기는 이것 위에서 돕니다. Windows 에서 WSL2 를 쓰면 그 자체가 이미 경량 하이퍼바이저 위에서 도는 리눅스라, 그 안에서 다시 KVM 게스트를 돌리려면 중첩 가상화가 필요합니다 — 뒤에서 보듯 이 전제는 이 장비에서 이미 충족돼 있습니다.

---

## 1. 실습 환경 판정 - 장비 범위를 정확히 긋기

### 1-1. KVM 은 된다

WSL2 Ubuntu-24.04 에서 확인했습니다.

```
$ uname -r
6.6.87.2-microsoft-standard-WSL2
$ ls -l /dev/kvm
crw-rw---- 1 root kvm 10, 232 /dev/kvm
$ lsmod | grep kvm
kvm_amd    126976  0
kvm       970752  1 kvm_amd
```

`/dev/kvm` 이 있고 `kvm_amd` 가 로드돼 있습니다. **가상화 자체는 막혀 있지 않습니다.** 여기까지는 좋은 소식이었습니다.

### 1-2. 범위를 가르는 축은 디스크 용량이었다

| 항목 | 값 |
| --- | --- |
| C: 여유 공간 | **15.5 GB** |
| `.android/avd` 전체 | 26 GB |
| — 이 스터디용 두 대 | 11.4 GB |
| — 다른 프로젝트 AVD | 14.1 GB |

WSL2 파일시스템은 `df` 상 1TB 로 보이지만 실제로는 Windows 쪽 가상 디스크 파일을 키우는 구조라, 한계는 결국 C: 여유 공간입니다.

### 1-3. AOSP 풀 빌드는 설계상 장비 범위 밖 - 목적은 소스 분석으로 흡수한다

더 중요한 발견이 여기 있었습니다. 공식 요구사항입니다.

> "At least 400 GB of free disk space to check out and build the code (250 GB to check out + 150 GB to build)."
> "A minimum of 64 GB of RAM."
>
> — [AOSP Requirements](https://source.android.com/docs/setup/start/requirements)

**400 GB 와 RAM 64 GB.** 체크아웃 250 GB 에 빌드 산출물 150 GB 로, 여유 15.5 GB 와는 자릿수가 다릅니다. Cuttlefish 를 띄우느냐와 **무관한 별개의 축** — 하드웨어 사양이 그은 명확한 경계입니다. 그래서 19~20주차의 "AOSP 태그와 패치 커밋으로 baseline/patched 이미지 빌드"는, 빌드라는 **수단** 대신 그 빌드로 확인하려던 **목적**(패치 커밋이 코드에서 무엇을 바꿨는가)을 22주차의 소스 diff 분석으로 흡수하도록 설계를 조정했습니다. AOSP 소스는 [cs.android.com](https://cs.android.com/) 에서 태그·커밋 단위로 그대로 읽히니, 확인하려는 대상 자체는 이 장비 안에 있습니다.

### 1-4. 판정표

| 구간 | 원래 계획 | 판정 |
| --- | --- | --- |
| 17주 | Cuttlefish 구동 | KVM 전제 충족 → 두 이미지 비교 하네스로 목적 달성 |
| 18주 | CVE 선정·사전 조사 | 그대로 가능 (문서 작업) |
| 19~20주 | AOSP baseline/patched 빌드 | 장비 범위 밖(400 GB) → 22주 소스 diff 로 목적 흡수 |
| 21주 | 패치 전·후 안전한 검증 | 하네스로 달성 — 보장 범위·경계 명시 |
| 22주 | 패치 diff 근본 원인 분석 | 그대로 가능 (소스는 웹에서 읽음) |
| 23~24주 | 최종 보고서 | 그대로 가능 |

그래서 17주차 산출물을 Cuttlefish 구동이 아니라 **두 이미지를 baseline/patched 역할로 놓고 같은 프로브를 돌려 대조하는 하네스**로 정했습니다. 원안의 목적이었던 "패치 전·후 대조 platform"은 이 하네스로 그대로 확보합니다.

---

## 2. 수행 절차 - 하네스와 프로브

> **이후 변경**: 여기서 만든 `clean` 스냅샷 방식은 19주차에 **`-wipe-data` 냉부팅**으로 바꿨습니다. 2022년 API 31 이미지가 소프트웨어 렌더링으로 낙착되는데 그 환경에서 스냅샷은 지원되지 않고, 실제로 가짜 차이를 하나 만들어냈기 때문입니다. [19주차 4-1](/posts/android-security-study-week19/) 참조.

`compare-images.sh <프로브.sh>` 가 하는 일은 여섯 단계입니다. 이전 인스턴스를 종료하고, baseline 역할 AVD 를 **`clean` 스냅샷에서** 부팅하고, 빌드 지문과 패치 수준을 증적에 고정하고, logcat 을 비운 뒤 프로브를 실행해 표준출력을 저장하고, patched 역할로 같은 과정을 반복하고, 두 출력을 `diff` 합니다.

보장하는 것은 **절차 동일성과 초기 상태 동일성**입니다. 보장하지 못하는 것은 4장에서 따로 적습니다.

프로브는 11~12주차에 진단한 InsecureShop 을 대상으로 삼았습니다. 앱은 그대로 두고 플랫폼만 바뀔 때 같은 공격 경로가 어떻게 되는지 보는 구성입니다.

---

## 3. 관측 결과

| | baseline | patched |
| --- | --- | --- |
| AVD | `sec-api33` | `sec-api36` |
| 시작 상태 | clean 스냅샷 | clean 스냅샷 |
| Android | 13 | 16 |
| 보안 패치 | 2024-03-01 | 2025-07-05 |

프로브 출력 대조입니다.

```diff
 설치                                    성공
 커스텀 권한 protectionLevel             prot=normal
-앱 UID 호출 시도(AboutUs)               판정불가
+앱 UID 호출 시도(AboutUs)               측정불가: run-as+am 기법이 플랫폼에서 차단됨
 딥링크 file:// 로드 → WebView 진입      성공
   주입 URL 이 loadUrl 에 도달           예 (file:///system/etc/hosts)
 shell 의 앱 외부 디렉터리 접근          경로없음
 shell 의 앱 내부 디렉터리 접근          거부
 ALLOW_BACKUP 런타임 플래그              있음
```

**차이가 한 줄뿐이고, 그 한 줄은 앱 보안과 무관합니다.**

커스텀 권한은 여전히 `prot=normal` 입니다. 11~12주차에 "선언만 하면 어떤 앱이든 자동 부여받는다"고 적었던 그 상태 그대로입니다. 딥링크로 `file:///system/etc/hosts` 를 주입하면 검증 없이 `loadUrl` 까지 도달합니다 — exported WebView 가 외부에서 들어온 URL 을 그대로 로드하고 `setAllowFileAccess` 가 열려 있으면 로컬 파일이 그대로 렌더된다는, [WebView 취급 주의](https://developer.android.com/privacy-and-security/security-tips)와 [OWASP MASTG](https://mas.owasp.org/MASTG/)가 반복해서 경고하는 교과서적 사례입니다.

![Android 16 에서 InsecureShop 의 WebView 가 딥링크로 주입한 로컬 파일을 열어 XML 문서를 렌더링한 화면입니다](/assets/img/android-security-study/18-android16-same-exposure.png)

---

## 4. 결과 해석

### 4-1. 플랫폼은 앱의 설계 결함을 대신 막지 않는다

Android 13 → 16, 보안 패치 2024-03 → 2025-07. 메이저 버전 세 개와 16개월치 패치를 건너뛰었는데 **InsecureShop 의 취약점은 하나도 닫히지 않았습니다.**

생각해보면 당연합니다. 이 문제들은 플랫폼 버그가 아니라 앱의 설계 결함입니다. `protectionLevel` 을 안 적은 것도, URL 검증 없이 `loadUrl` 을 부른 것도 앱이 한 일입니다. [Application Sandbox](https://source.android.com/docs/security/app-sandbox)는 앱 **사이**의 경계를 UID 로 강제하지, 앱이 스스로 연 문 안쪽까지 대신 지켜 주지는 않습니다 — 플랫폼이 고칠 수 있는 종류가 아닙니다.

15~16주차에 "플랫폼의 방어 층들은 앱 밖에서 안으로 들어오는 것을 막는다. 앱이 스스로 문을 여는 것은 그 층들의 관심사가 아니다"라고 적었는데, 그 문장을 버전 대조로 확인한 셈입니다.

### 4-2. 이 하네스의 보장 범위와 경계

로드맵의 CVE 재현 성공 기준 첫 항목은 **"패치 전과 후가 동일한 실험 조건에서 비교되었다"** 입니다.

이 하네스가 **확실히 보장하는 것**은 절차 동일성과 초기 상태 동일성입니다. 다만 그 기준이 요구하는 "패치 하나만 다른" 쌍까지는 아닙니다 — 두 이미지는 API 레벨이 달라 프레임워크·커널·[SELinux 정책](https://source.android.com/docs/security/features/selinux)·기본값이 함께 바뀌기 때문입니다. 실제로 손에 있는 다른 API33 x86_64 이미지의 게스트 커널을 찍어 보면 `5.15.119-android13`(clang 14 로 빌드)인데, 상위 API 이미지는 이 커널부터가 다릅니다. 그래서 관측된 차이는 곧바로 패치 효과로 귀속되지 않습니다.

그래서 리포트에 경고 문구를 고정으로 넣었습니다. 차이가 보이면 결론이 아니라 **가설**로 두고 해당 변경의 소스 diff 로 설명되는지 확인해야 합니다. 이번처럼 차이가 거의 없는 경우에도 "패치와 무관함을 입증했다"가 아니라 "이 조건에서는 차이가 관측되지 않았다"까지만 말할 수 있습니다.

경계를 분명히 해두겠습니다. AOSP 를 빌드해 "패치 하나만 다른" 이미지 쌍을 만드는 것은 이 장비의 사양 밖입니다. 그런데 하네스를 다 만든 뒤에, 교란 변수를 크게 줄이는 **실현 가능한 경로**를 하나 찾았습니다. 다음 절에 적습니다.

### 4-3. 같은 API 레벨의 과거 리비전으로 교란을 줄일 수 있다

글을 쓰면서 "같은 API 레벨의 과거 시스템 이미지를 받을 수 있는가"를 확인해봤습니다. `sdkmanager` 는 저장소 XML 이 패키지당 최신 리비전 하나만 기술하고 리비전 지정 플래그도 없어, 과거 리비전을 직접 가리키지는 못합니다.

그런데 **과거 리비전 zip 은 서버에 그대로 남아 있습니다.** URL 규칙이 단순합니다.

```
https://dl.google.com/android/repository/sys-img/android/x86_64-<API>_r<NN>.zip
```

실제로 존재하는지, 그리고 패치 수준이 다른지 확인했습니다. 1.5 GB 를 다 받을 필요는 없고, HTTP Range 로 zip 중앙 디렉터리를 읽어 `build.prop` 엔트리만 뽑으면 수십 KB 로 끝납니다.

| 이미지 | 빌드 ID | `ro.build.version.security_patch` |
| --- | --- | --- |
| android-31 `default` **r03** | `SE1A.220621.001` | **2022-08-01** |
| android-31 `default` **r05** | `SE1A.220826.006.A1` | **2022-10-01** |

없는 리비전(`r99`)은 404 가 떨어지는 것도 확인했으니, 아무 URL 에나 200 을 주는 것은 아닙니다.

이 쌍은 **같은 API 레벨, 같은 SE1A 릴리스 브랜치, 불리틴 두 개 차이**입니다. GMS 가 없는 순수 AOSP 이미지라 소스 diff 와 대응시키기도 낫습니다. 압축 0.61 GB, 압축 해제 4.16 GB 로 두 장이면 8.3 GB 이니 현재 여유 안에 들어갑니다.

여전히 "CVE 패치 하나만 다른" 쌍은 아닙니다. 두 달치 변경이 통째로 들어 있으니까요. 그래도 **메이저 버전 세 개를 건너뛴 이번 비교보다는 원인 후보가 훨씬 좁습니다.** 18주차에 CVE 를 고를 때 이 구간에 해당하는 것을 고르면 19~21주차를 더 제대로 할 수 있습니다.

이 경로는 하네스를 다 만든 뒤에야 찾았습니다. 다음 조사부터는 "만들기 전에 더 정밀한 경로가 있는지부터 확인"하는 순서로 반영합니다 — 이번 구간이 남긴 실전 교훈입니다.

---

## 5. 정밀화 - 프로브 하나에서 측정 오류 세 번을 잡아내다

이번 구간에서 실제로 한 일의 절반은 프로브를 다듬는 것이었습니다. 세 번 모두 **버전 차이가 아닌 것을 버전 차이로 읽을 뻔한 것을, 리포트에 적기 전에 잡아냈습니다.** 비교 실험의 신뢰도는 이렇게 측정 도구 자체를 의심한 만큼 올라갑니다.

### 5-1. 측정 기법 자체가 버전에 따라 막힌다

첫 실행에서 exported 컴포넌트 호출이 API 33 은 "기타", API 36 은 "거부"로 나왔습니다. "새 버전이 더 엄격해졌다"로 읽힐 결과였습니다.

실제 출력을 보니 이랬습니다.

```
java.lang.SecurityException: Permission Denial:
  package=com.android.shell does not belong to uid=10217
```

컴포넌트가 보호됐다는 뜻이 아닙니다. Android 14+ 가 [`assertPackageMatchesCallingUid`](https://cs.android.com/search?q=assertPackageMatchesCallingUid) 를 넣으면서, 호출 uid 와 지정 패키지가 어긋나면 곧바로 튕겨내도록 바뀌었습니다. 그 결과 `run-as <pkg> am start` 로 앱의 uid 를 빌려 컴포넌트를 부르던 **측정 기법 자체가 막힌 것**입니다. 앱의 공격 표면은 그대로인데 제 측정 도구가 안 통하게 됐을 뿐입니다.

이 차단은 별도로 띄운 API33 x86_64 루트 이미지에서도 똑같이 관측됩니다. 거기서는 `run-as` 대신 `dumpsys` 로 우회해 값을 읽었는데, `userId=10176`, 그리고 `/data/data/<pkg>` 의 소유·모드가 `drwx------ u0_a176`(0700)이었습니다. **UID 샌드박스는 그대로 굳건하고, 막힌 것은 경계가 아니라 관측 도구**라는 점을 다른 이미지가 재확인해 준 셈입니다.

그래서 판정을 "거부"로 뭉뚱그리지 않고 사유를 분류해서 남기도록 고쳤습니다 — 이 구분이 5-1 을 "버전 간 보안 강화"라는 오독에서 구했습니다. **"측정불가"와 "거부"는 다른 말입니다.**

### 5-2. 고정 대기를 조건 폴링으로 바꿔 콜드 스타트를 흡수했다

딥링크 후 6초 기다렸다가 포커스를 확인했는데 baseline 은 성공, patched 는 실패로 나왔습니다.

수동으로 해보니 patched 에서도 정상 동작했습니다. 갓 부팅한 이미지라 콜드 스타트가 느려 6초 안에 못 올라온 것뿐이었습니다. 고정 `sleep` 을 조건 폴링으로 바꿔 해결했습니다.

부팅 스크립트에서는 `sys.boot_completed` 를 폴링하도록 이미 만들어뒀으면서, 프로브를 쓸 때는 그 교훈을 잊었습니다.

### 5-3. 구조화된 출력은 문자열 검색 대신 결정적 흔적으로 확인한다

"파일 내용이 화면에 렌더됐는가"를 uiautomator 덤프에서 `password` 로 찾았습니다. 두 이미지 모두 "예"가 나왔는데, 로그인을 안 한 상태라 자격증명이 있을 수 없었습니다.

원인은 덤프 XML 의 **모든 노드에 `password="false"` 속성이 붙는다**는 것이었습니다. 렌더된 텍스트가 아니라 속성 이름이 걸린 위양성입니다.

`text=` 값만 뽑아 다시 검색했더니 이번엔 실행마다 결과가 달라졌습니다. WebView 내용의 접근성 노드 노출이 타이밍에 좌우되기 때문입니다.

결국 렌더 확인을 포기하고 **결정적인 흔적**으로 바꿨습니다. `WebViewActivity` 는 로드한 URL 을 앱 설정에 저장하므로, 그 값이 주입한 URL 과 같으면 검증 없이 `loadUrl` 에 도달했다는 뜻입니다. 화면에 픽셀이 그려졌는지보다 이쪽이 증거로 낫습니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 상태 |
| --- | --- |
| 1~16주 | 완료 |
| 17주 (원안: Cuttlefish) | **대체 수행 완료** — 두 이미지 비교 하네스 |
| — 후속 | 같은 API 레벨 과거 리비전 쌍(31 r03 ↔ r05) 확보 경로 확인 |
| 18주 CVE 선정·사전 조사 | 다음 (환경 제약 없음) |
| 19~20주 AOSP 빌드 | 장비 범위 밖 — 22주차 소스 diff 분석으로 목적 흡수 |
| 21주 안전한 검증 | 하네스로 달성 — 보장 범위·경계 명시 |

경계를 정량으로 적어둡니다. Cuttlefish 는 이번 구간의 **목적이 아니라 수단**이었고, 그 목적(패치 전·후 대조 platform)은 대체 하네스로 달성했습니다. Cuttlefish 자체 구동으로 좁혀 보면 KVM 전제조건은 전부 충족돼 있고(`/dev/kvm`·`/dev/vhost-vsock`·`/dev/vhost-net` 모두 존재, systemd 활성) 남은 변수는 디스크 용량 하나뿐입니다. 필요량을 따져보니 이미지 zip 압축 해제 13.1 GB(`super.img` 7 GB + `userdata.img` 6 GB), 호스트 패키지 0.9 GB, 런타임 오버레이 2~5 GB 로 **대략 16.5~20.5 GB**, 여유가 15.5 GB. 막는 것이 기술적 결함이 아니라 용량 한 축이라는 것을 정량으로 확정한 것 자체가 이 판정의 성과입니다 — 디스크만 확보되면 그대로 부팅되는 상태까지 와 있습니다.

이번 하네스의 두 이미지가 동일 조건이 아니라는 것이 알려진 한계선이고, 그 한계선을 좁힐 실현 가능한 경로(4-3 의 같은 API 레벨 과거 리비전 쌍)까지 이미 확보해 뒀습니다. 다음 구간에서 그 경로로 정밀도를 끌어올립니다. 프로브가 다루는 항목도 지금은 여덟 개라, 18주차에 CVE 를 고른 뒤 그 CVE 에 맞춘 프로브를 하나 더 붙이면 됩니다.

---

## 참고 자료

- [AOSP 빌드 요구사항](https://source.android.com/docs/setup/start/requirements) — 400 GB / RAM 64 GB 의 출처
- [Cuttlefish](https://source.android.com/docs/devices/cuttlefish) — AOSP 공식 가상 기기
- [KVM API (kernel.org)](https://docs.kernel.org/virt/kvm/api.html) — Cuttlefish 가 요구하는 커널 가상화 인터페이스
- [Android Application Sandbox](https://source.android.com/docs/security/app-sandbox) · [SELinux](https://source.android.com/docs/security/features/selinux) — 앱 사이 경계의 근거와 API 레벨 간 변동 요인
- [Android Security Bulletins](https://source.android.com/docs/security/bulletin) — 보안 패치 수준(2024-03 ↔ 2025-07)이 무엇을 담는가
- [WebView 보안 취급](https://developer.android.com/privacy-and-security/security-tips) · [OWASP MASTG](https://mas.owasp.org/MASTG/) — file:// 딥링크·loadUrl 검증 관련
- [`assertPackageMatchesCallingUid` (cs.android.com)](https://cs.android.com/search?q=assertPackageMatchesCallingUid) — Android 14+ 가 run-as+am 측정 기법을 막은 근거

## 마치며

이번 구간은 **장비의 범위를 정확히 긋는 데** 시간을 많이 썼습니다. 400 GB 라는 숫자를 확인하기 전까지는 "어떻게든 되지 않을까" 하고 우회로를 뒤지고 있었는데, 공식 요구사항을 읽고 나니 빌드라는 수단은 접고 그 수단의 목적을 다른 길로 달성하면 된다는 게 분명해졌습니다. 경계를 확정하고 나서야 남은 자원으로 무엇을 지어야 하는지가 또렷해졌고, 실제로 대체 하네스와 후속 경로까지 손에 넣었습니다.

그리고 프로브 하나를 다듬으며 측정 오류를 세 번 잡아냈습니다. 세 번 다 그럴듯한 차이를 만들어냈고, 그대로 뒀으면 "버전 간 보안 차이"라고 적었을 것입니다. 버전을 가로질러 비교할 때는 **측정 도구 자체가 버전에 따라 다르게 동작한다**는 것을 이번에 제대로 배웠습니다.

결과적으로 이번 대조에서 나온 유일한 차이가 바로 그 측정 도구의 차이였다는 게, 이 구간을 요약하는 것 같습니다.
