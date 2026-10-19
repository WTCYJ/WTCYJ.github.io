---
layout: post
title: "Parcel Mismatch 논문 트렌드 분석"
date: 2026-10-19
category: 논문
author: SeiKa
tags: [논문리뷰, 안드로이드, Binder, Parcel, IPC, 권한상승, LaunchAnyWhere, 정적분석, CCS, NDSS, MobiSys]
excerpt: "검사한 데이터와 실제로 쓰이는 데이터가 달라지는 지점을 안드로이드 연구가 어떻게 좁혀 왔는지 다섯 편의 논문으로 따라갔다. 중심 논문은 CCS 2025의 Parcel Mismatch Demystified이고, Android 9와 13 에뮬레이터에서 Self-Changed Bundle을 직접 재현해 LazyValue 방어가 실제로 어떻게 동작하는지도 확인했다."
---

## 들어가며

안드로이드 앱 진단을 하다 보면 exported 컴포넌트에 인텐트를 던져 보는 일이 많다. 그때마다 "시스템은 이 인텐트를 어디서 검사하고, 검사한 그 객체를 그대로 쓰는가"가 궁금했다. 그 질문을 따라가다 보니 같은 문제를 체계적으로 파고든 CCS 2025 논문이 있었다. 이번 글은 그 논문을 중심에 두고 앞뒤 연구를 함께 읽은 기록이다.

다섯 편을 관통하는 질문은 하나다. 시스템 서비스가 무언가를 검사한 뒤에 실제로 쓰이는 데이터가, 검사한 그 데이터와 정말 같은가. 이 질문이 처음에는 "검사가 경로마다 다르다"는 형태로 나왔고, 다음에는 "검사가 앱이 보낸 입력을 너무 믿는다"로, 중심 논문에서는 "검사는 맞는데 직렬화를 한 번 거치면 데이터가 바뀐다"로 좁혀졌다.

| 구분 | 논문 | 게재처 |
|---|---|---|
| 선행 1 | Kratos: Discovering Inconsistent Security Policy Enforcement in the Android Framework | NDSS 2016 |
| 선행 2 | Invetter: Locating Insecure Input Validations in Android Services | ACM CCS 2018 |
| 중심 | Parcel Mismatch Demystified: Addressing a Decade-Old Security Challenge in Android | ACM CCS 2025 |
| 후속 1 | Fragile Deliveries: Inconsistencies in Android Parcel and Their Security Consequences | ACM MobiSys 2026 |
| 후속 2 | Towards LLM-Enhanced Android Taint Analysis | arXiv 2608.24269 (2026년 8월, 프리프린트) |

<svg viewBox="0 0 760 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="2014년부터 2026년까지 안드로이드 IPC 검사 불일치 연구 흐름 타임라인">
<style>
.pmt-axis{stroke:var(--rule-dark);stroke-width:2}
.pmt-tick{stroke:var(--rule-dark);stroke-width:1}
.pmt-yr{fill:var(--ink-faint);font:12px var(--mono)}
.pmt-paper{fill:var(--surface);stroke:var(--blue);stroke-width:1.5}
.pmt-core{fill:var(--surface);stroke:var(--red);stroke-width:2.5}
.pmt-ind{fill:none;stroke:var(--ink-faint);stroke-width:1;stroke-dasharray:4 3}
.pmt-t{fill:var(--ink);font:600 13px var(--sans)}
.pmt-s{fill:var(--ink-soft);font:11.5px var(--sans)}
.pmt-i{fill:var(--ink-faint);font:11px var(--sans)}
.pmt-lab{fill:var(--ink-soft);font:600 11px var(--sans)}
</style>
<text class="pmt-lab" x="20" y="22">학계 논문</text>
<rect class="pmt-paper" x="40" y="34" width="120" height="52" rx="6"/>
<text class="pmt-t" x="52" y="56">Kratos</text>
<text class="pmt-s" x="52" y="74">NDSS 2016</text>
<rect class="pmt-paper" x="150" y="96" width="120" height="52" rx="6"/>
<text class="pmt-t" x="162" y="118">Invetter</text>
<text class="pmt-s" x="162" y="136">CCS 2018</text>
<rect class="pmt-core" x="470" y="34" width="132" height="52" rx="6"/>
<text class="pmt-t" x="482" y="56">Parcel Mismatch</text>
<text class="pmt-s" x="482" y="74">CCS 2025 · 중심</text>
<rect class="pmt-paper" x="566" y="96" width="126" height="52" rx="6"/>
<text class="pmt-t" x="578" y="118">Fragile Deliveries</text>
<text class="pmt-s" x="578" y="136">MobiSys 2026</text>
<rect class="pmt-paper" x="610" y="158" width="130" height="52" rx="6"/>
<text class="pmt-t" x="622" y="180">LLM Taint</text>
<text class="pmt-s" x="622" y="198">arXiv 2026.08</text>
<line class="pmt-axis" x1="20" y1="232" x2="740" y2="232"/>
<line class="pmt-tick" x1="40" y1="226" x2="40" y2="238"/><text class="pmt-yr" x="26" y="254">2014</text>
<line class="pmt-tick" x1="100" y1="226" x2="100" y2="238"/><text class="pmt-yr" x="86" y="254">2016</text>
<line class="pmt-tick" x1="210" y1="226" x2="210" y2="238"/><text class="pmt-yr" x="196" y="254">2018</text>
<line class="pmt-tick" x1="420" y1="226" x2="420" y2="238"/><text class="pmt-yr" x="406" y="254">2022</text>
<line class="pmt-tick" x1="470" y1="226" x2="470" y2="238"/><text class="pmt-yr" x="456" y="254">2024</text>
<line class="pmt-tick" x1="530" y1="226" x2="530" y2="238"/><text class="pmt-yr" x="516" y="254">2025</text>
<line class="pmt-tick" x1="640" y1="226" x2="640" y2="238"/><text class="pmt-yr" x="626" y="254">2026</text>
<text class="pmt-lab" x="20" y="276">안드로이드</text>
<text class="pmt-i" x="88" y="276">2014 첫 Parcel Mismatch 보고</text>
<text class="pmt-i" x="300" y="276">2022 Android 13 LazyValue 도입</text>
<text class="pmt-i" x="500" y="276">2023 CVE-2023-20963 실제 악용</text>
</svg>

논문은 위쪽에, 중심 논문과 Fragile Deliveries가 배경으로 설명한 안드로이드 쪽 사건은 아래쪽에 적었다. 이 분야는 실제 취약점 보고가 논문보다 앞서 간 경우가 많아서 둘을 같이 봐야 흐름이 보인다.

## 1. 선행 논문: Kratos

| 항목 | 내용 |
|---|---|
| 논문 제목 | Kratos: Discovering Inconsistent Security Policy Enforcement in the Android Framework |
| 저자 | Yuru Shao, Jason Ott, Qi Alfred Chen, Zhiyun Qian, Z. Morley Mao |
| 게재처 | NDSS 2016. [저자 공개본 PDF](https://www.ics.uci.edu/~alfchen/pubs/roy_ndss16.pdf) |
| 연구 주제 | 안드로이드 프레임워크 안에서 같은 자원에 도달하는 경로들의 보안 검사가 서로 다른 문제 |
| 핵심 기여 | 프레임워크 전체 콜 그래프에 보안 검사를 표시하고, 경로끼리 비교해 불일치를 찾는 정적 분석 |

### 1-1 문제 정의

시스템 서비스는 AIDL 인터페이스로 앱에 기능을 연다. 같은 기능에 이르는 인터페이스가 여러 개일 때, 한쪽은 시스템 권한을 요구하고 다른 쪽은 일반 권한만 요구하면 공격자는 약한 쪽으로 들어가면 된다. 논문이 처음에 든 예가 Android 4.4의 Wi-Fi 서비스였다. `addOrUpdateNetwork()`는 시스템 전용 권한인 CONNECTIVITY_INTERNAL까지 확인하는데, `getWifiStateMachineMessenger()`로 메신저를 받아 메시지를 직접 보내면 그 검사를 건너뛰고 같은 하위 함수에 닿는다.

저자들이 보여 준 소스 주석도 인상적이었다. LockSettingsService에 "여기에 권한 검사가 필요한가?"라는 주석이 달린 채로 검사가 없었다. 구글 엔지니어들도 어떤 정책이 필요한지 정확히 알지 못했다는 근거로 쓰였다.

### 1-2 방법론

Kratos는 정책을 미리 알고 있다고 가정하지 않는다. 대신 이미 코드에 있는 검사(권한, UID, 패키지 이름, 스레드 상태)를 찾아 콜 그래프의 각 노드에 표시한다. 그다음 서비스 인터페이스 두 개가 같은 하위 메서드로 수렴하는지 보고, 수렴하는 경로끼리 거쳐 온 검사 집합이 다르면 후보로 올린다. Binder 호출, 메시지 핸들러, Messenger와 상태 기계를 따라가도록 PScout의 IPC 해석을 보강한 점이 구현상 핵심이었다.

### 1-3 결과와 한계

| 코드베이스 | 불일치 후보 | 참 양성 | 정밀도 | 악용 가능 |
|---|---|---|---|---|
| Android 4.4 | 21 | 16 | 76.2% | 8 |
| Android 5.0 | 61 | 50 | 82.0% | 11 |
| Android M Preview | 73 | 58 | 79.5% | 8 |
| T-Mobile Galaxy Note 3 (4.4.2) | 128 | 102 | 79.7% | 10 |

여섯 코드베이스 모두 불일치가 있었고, 서로 다른 서비스에서 악용 가능한 취약점 14개를 찾았다. 그중 11개가 숨겨진(@hide) 인터페이스였다. 같은 4.4 기반인데도 삼성 기기는 AOSP보다 서비스가 89개 많았고 불일치도 가장 많았는데, 벤더 커스터마이징이 공격면을 늘린다는 관찰은 이후 논문에서도 계속 나온다.

한계는 저자들도 분명히 적었다. 콜 그래프가 문맥에 둔감해서 오탐이 생기고, 네이티브 서비스는 분석하지 못하며, 후보가 실제로 악용 가능한지는 사람이 소스를 읽어 판단해야 했다. 내가 더 중요하게 본 한계는 전제 쪽이다. Kratos는 "검사가 경로 위에 있으면 그 경로는 보호된다"고 본다. 검사가 있더라도 검사한 데이터와 쓰는 데이터가 다를 수 있다는 가능성은 이 모델 바깥에 있다.

## 2. 선행 논문: Invetter

| 항목 | 내용 |
|---|---|
| 논문 제목 | Invetter: Locating Insecure Input Validations in Android Services |
| 저자 | Lei Zhang, Zhemin Yang, Yuyu He, Zhenyu Zhang, Zhiyun Qian, Geng Hong, Yuan Zhang, Min Yang |
| 게재처 | ACM CCS 2018. [ACM DL](https://dl.acm.org/doi/10.1145/3243734.3243843) |
| 연구 주제 | 시스템 서비스가 권한 검사 대신 쓰는 입력 검증(uid, 패키지 이름, URI 등)이 안전하지 않은 문제 |
| 핵심 기여 | 구조 분석으로 입력 검증을 찾고, 연관 규칙 학습으로 민감한 검증을 골라내 잘못 놓인 검증을 탐지 |

### 2-1 문제 정의

Kratos가 권한 검사를 비교했다면 Invetter는 권한이 아닌 검사로 시선을 옮겼다. 저자들 계산으로 프레임워크에는 권한보다 입력 검증이 훨씬 많다. 그런데 입력 검증은 정해진 API도 문서도 없고, 173개 클래스에 흩어져 있다. 그래서 무엇이 보안 검사인지부터 알기 어렵다.

논문이 정리한 실수의 유형은 내 진단 경험과도 맞닿아 있었다. 가장 흔한 것은 앱이 보낸 값으로 호출자를 확인하는 경우다. 퀄컴 CNEService가 `packageName` 인자를 보고 시스템 앱인지 판단한 사례가 대표적이다. 검증을 앱 프로세스에서 도는 SDK의 Manager 클래스 안에 넣어 둔 경우도 있었다. 앱은 Manager를 건너뛰고 Binder로 직접 호출할 수 있으니 그 검증은 의미가 없다. 벤더가 서비스를 고치면서 검증을 지워 버린 경우도 나오는데, 샤오미 이미지에서 `setRingerModeExternal()`의 검사가 빠진 예가 나온다.

### 2-2 방법론과 결과

종료 동작(예외, 상수 반환, 로그 후 반환, 자원 해제 후 반환)이 뒤따르는 조건문을 입력 검증으로 보고, 여기서 다시 연관 규칙 학습으로 민감한 검증을 골라냈다. uid와 packageName이 같은 메서드에서 같이 검사되는 경향을 이용해 소수의 라벨에서 나머지를 넓혀 가는 방식이다.

AOSP 네 버전과 벤더 이미지 네 개에서 입력 검증 1,865개를 찾았고 그중 앱 수준 권한으로 보호되는 것은 643개였다. 민감한 검증 749개에서 의심 사례 103개가 나왔고, 사람이 확인한 참 양성이 86개, 실제 악용을 구성한 것이 최소 20개였다. 권한 없는 앱이 백그라운드에서 피싱 창을 띄우거나 다른 앱의 비밀번호를 읽는 시연이 포함되어 있다.

### 2-3 한계

저자들은 "민감한 입력이 코드베이스 어디서도 한 번도 검증되지 않을 확률은 작다"는 가정 위에서 이미 있는 검증의 오용만 찾았다. 미탐을 측정할 정답 집합도 없었다. 그리고 Kratos와 마찬가지로, 검증 로직 자체가 옳다면 안전하다고 본다.

여기까지 읽고 나서 중심 논문을 읽으면 무엇이 달라졌는지가 선명해진다. 시스템 서비스가 Intent를 꺼내 대상 컴포넌트를 올바르게 검사했다고 하자. 그 Intent가 Bundle에 담겨 다시 직렬화되어 다른 프로세스로 넘어가는 순간 내용이 바뀐다면, Kratos와 Invetter의 모델에서는 아무 문제가 없는 코드가 된다.

## 3. 중심 논문: Parcel Mismatch Demystified

| 항목 | 내용 |
|---|---|
| 논문 제목 | Parcel Mismatch Demystified: Addressing a Decade-Old Security Challenge in Android |
| 저자 | Sheng Cao, Hao Zhou, Songzhou Shi, Yanjie Zhao, Haoyu Wang |
| 게재처 | ACM CCS 2025 (대만 타이베이). [ACM DL, 무료 공개](https://dl.acm.org/doi/10.1145/3719027.3765034) |
| 연구 주제 | 직렬화와 역직렬화가 어긋나 Bundle이 IPC 도중 스스로 바뀌는 취약점과, 그에 대한 구글 방어의 실효성 |
| 핵심 기여 | 불일치 유형 분류(MS1~MS3), 방어 세 가지의 약점 분석, 프로세스를 넘나드는 정적 오염 분석 도구 ParcelTaint, 신규 익스플로잇 9건 |

### 3-1 문제 정의와 배경

Parcel은 안드로이드 IPC 전용 직렬화 형식이다. 객체를 Parcel에 쓰려면 클래스가 `writeToParcel()`과 `createFromParcel()`을 직접 구현해야 하고, 쓰는 순서와 읽는 순서, 자료형이 정확히 맞아야 한다. Parcel은 데이터 사이에 구분자가 거의 없는 연속된 바이트 덩어리라서, 한 객체가 4바이트만 덜 읽어도 그 뒤의 키와 값이 전부 밀린다.

이것이 Bundle 안에서 일어나면 "Self-Changed Bundle"이 된다. 공격자가 만든 Bundle을 시스템 서비스가 받아서 검사할 때와, 그 Bundle을 다시 직렬화해 다른 프로세스로 넘긴 뒤 받는 쪽이 읽을 때 키와 값 구성이 달라진다. 전형적인 공격 체인(논문의 AC#0)은 AccountManagerService다. 서비스는 Bundle 속 Intent가 안전한지 검사하고 넘기는데, 받는 쪽인 Settings가 읽을 때는 다른 Intent가 나와서 시스템 권한으로 임의 액티비티가 열린다. 논문은 이런 공격을 LaunchAnywhere라고도 부른다.

2014년 첫 보고 뒤로 관련 CVE가 65개를 넘었고, 2023년에는 대형 쇼핑 앱 Pinduoduo가 이 계열 취약점(CVE-2023-20963)을 실제 사용자 기기 공격에 썼다는 분석이 나왔다. 구글은 오랫동안 클래스를 하나씩 고치다가 시스템 차원의 방어 세 가지를 도입했다.

| 방어 | 동작 | 논문이 지적한 약점 |
|---|---|---|
| M1 `checkKeyIntentParceledCorrectly` | AccountManagerService에서 Bundle을 한 번 더 직렬화·역직렬화해 보고 Intent 주요 필드가 같은지 비교 | ClipData와 Extras 객체의 실제 타입은 비교하지 않음. Android 11까지 백포트됐지만 12L 이하에서는 이것이 유일한 방어 |
| M2 LazyValue | Android 13부터 가변 길이 값 앞에 타입과 길이를 붙이고 접근할 때 역직렬화 | 깨진 데이터를 바로 버리지 않고 다음 IPC까지 들고 감(Data Retention). 길이가 안 맞아도 경고만 남기고 계속 파싱함(Length Without Validation) |
| M3 `enforceNoDataAvail` | Android 13부터 AIDL 호출 뒤 Parcel에 남은 데이터가 있으면 예외 | 다 소비했는지만 보고, 올바르게 읽었는지는 보지 않음 |

### 3-2 새로 찾은 불일치 유형

저자들은 기존의 고전적 불일치를 MS1로 두고, 방어가 들어온 뒤에도 통하는 두 유형을 새로 정리했다.

MS2(LazyValue Mismatch)는 M2의 약점을 이용한다. 첫 번째 기법은 역직렬화 중에 쓰기를 하는 Parcelable을 이용하는 것이다. AOSP의 한 클래스가 `createFromParcel()` 안에서 Parcel에 쓰기를 해서 내부 구조를 망가뜨리고, 망가진 데이터가 Data Retention 때문에 다음 IPC까지 살아남는다. 두 번째는 Bundle 내부의 ArrayMap이 직렬화할 때 키를 해시 순서로 정렬한다는 점을 이용한다. 해시가 큰 키를 앞에 두고 값을 두 조각으로 나눠 숨겨 두면, 정렬 뒤 두 조각이 붙으면서 길이 검증 없는 파서가 선언된 길이를 넘어 읽는다.

MS3(Creator Mismatch)는 AIDL이 다형성을 다루지 못하는 데서 나온다. 클라이언트가 Intent의 하위 클래스인 LabeledIntent를 보내면 하위 클래스 필드까지 직렬화된다. 그런데 서버는 `Intent.CREATOR`로만 읽으니 남은 바이트가 다음 인자로 흘러 들어간다. `startActivity`의 경우 그 다음 인자가 외부 앱이 건드리면 안 되는 `options` Bundle이고, Bundle은 가변 길이라 남은 데이터를 다 먹어 버리니 M3도 통과한다.

### 3-3 ParcelTaint 설계

익스플로잇은 불일치(MS)와 공격 체인(AC)의 조합이다. 불일치 클래스를 찾는 것만으로는 부족하고, 공격자가 통제하는 Bundle이 특권 프로세스 A를 거쳐 특권 프로세스 B로 다시 직렬화되어 넘어가는 경로가 있어야 한다. ParcelTaint는 이 경로를 찾는 도구다.

| 단계 | 하는 일 |
|---|---|
| 서비스 전처리 | Soot로 services.jar를 읽고 `IInterface` 상속 구조에서 Stub과 Proxy 쌍을 찾음. 진입점은 호출 가능한 서비스 메서드, 소스는 Bundle 같은 Parcel 계열 인자, 싱크는 `IBinder` 인자가 있는 프로세스 경계 메서드 |
| Intent 모델링 | Intent를 라우팅 정보(`@intentRef`)와 Extras(`@extras`) 두 접근 경로로 나눠 추적 |
| 컴포넌트 간 오염 분석 | `startActivity(intent)`의 상수 라우팅 값으로 대상 컴포넌트를 풀고, 그 컴포넌트의 `getIntent()` 반환값을 포인터 그래프에서 바로 연결(ICC 규칙) |
| 데이터 흐름 필터 | 경로 중간에 `Bundle#remove` 같은 수정 지점(MustPassed)을 반드시 지나는 흐름만 남김 |

구현은 ByteDance의 AppShark를 확장했다. FlowDroid보다 가볍고 규칙을 추가하기 쉬워서 골랐다고 한다. 내가 가장 납득한 설계는 Intent 모델링이다. Extras에서 문자열 배열을 꺼내 새 Intent에 담는 정상 코드를, 일반 오염 분석은 "외부 입력이 Intent로 흘러간다"고 오탐한다. 라우팅과 페이로드를 분리하면 이 차이를 구분할 수 있다.

### 3-4 평가

실험 대상은 당시 최신이던 Android 14 AOSP의 Settings.apk와 services.jar였다. 128코어, 512GB 메모리 서버에서 Settings는 16.9초, services.jar는 데이터 흐름 필터를 켜면 904.3초가 걸렸다.

| 연구 질문 | 결과 |
|---|---|
| RQ1 오탐 제거 | Intent 모델링을 끄면 Settings 컴포넌트 9개가 걸리는데 그중 7개가 오탐. 데이터 흐름 필터를 끄면 Bundle 경로가 17개, 켜면 4개(악용 가능 1개) |
| RQ2 새 공격 체인 | AC#1~AC#4 발견. AC#1(ContentService)은 권한 검사 때문에 오탐, AC#2(NotificationManagerService), AC#3(Settings 2단 화면 딥링크), AC#4(AppRestrictionsFragment)는 악용 가능 |
| RQ3 방어 우회 | 체인과 불일치 유형을 조합한 EXP#1~EXP#9. 대부분은 Android 12·12L에서 통하고, Android 13 이상에서 LazyValue를 뚫은 것은 MS2를 쓴 EXP#4·#5. MS3를 쓴 EXP#8은 이론상 모든 버전에 해당하지만 EXP#9 경로에 묶여 있음 |

NotificationManagerService 체인이 특히 흥미로웠다. 앱이 올린 알림을 NMS가 검사한 뒤 SystemUI 같은 리스너에게 다시 직렬화해 보내는데, 이 두 번째 직렬화에서 불일치가 터진다. M1은 AccountManagerService에만 들어가 있으니 이 체인은 처음부터 보호 밖이었다. 결과적으로 CVE-2024-43080, CVE-2024-49744, CVE-2025-32312, CVE-2025-48535와 화웨이 CVE-2025-31175가 나왔고, 논문에 따르면 구글은 개별 불일치를 막는 방식에서 근본 패턴을 다루는 쪽으로 대응 전략을 바꿨다.

### 3-5 에뮬레이터 재현

논문의 배경 설명 중 M2가 정말 고전적 불일치를 막는지, 그리고 Length Without Validation이 실제로 "경고만 하고 넘어가는" 동작인지 눈으로 보고 싶었다. ParcelTaint를 돌리려면 서버급 자원이 필요해서, 대신 불일치의 원리만 담은 작은 실험을 만들었다.

`Evil`이라는 Parcelable은 `id`를 int로 읽고 long으로 쓴다. 공격자는 `{evil, note}` 두 항목짜리 Bundle을 바이트 단위로 직접 만들고, 숨길 항목(`intent` 키와 Settings의 비밀번호 변경 화면을 가리키는 Intent)을 `Evil`의 byte 배열 안에 넣는다. 검사하는 쪽은 Bundle을 읽어 `intent` 키가 없는지 확인한 뒤 다시 직렬화하고, 받는 쪽이 그것을 다시 읽는다. 실제 시스템 서비스 두 개 대신 한 프로세스 안에서 Parcel을 한 번 왕복시킨 모의 실험이라는 점은 미리 밝혀 둔다.

```java
public Evil createFromParcel(Parcel in) {
    Evil e = new Evil();
    e.id = in.readInt();           // 4바이트 읽기
    e.ct = in.readInt();
    e.data = in.createByteArray();
    return e;
}

public void writeToParcel(Parcel out, int flags) {
    out.writeLong(id);             // 8바이트 쓰기: 여기서 어긋난다
    out.writeInt(ct);
    out.writeByteArray(data);
}
```

앱을 설치하지 않고 dex 파일 하나를 `app_process`로 실행했고, 아래 화면은 Windows Terminal에서 adb로 실행한 창을 그대로 캡처한 것이다. 실험용 AVD는 `-read-only` 모드로 띄워 기존 상태를 바꾸지 않았다.

![Windows Terminal에서 Android 9 에뮬레이터(보안 패치 2019-08-05)로 데모를 실행한 화면. 검사 단계 키는 evil, note이고 has intent는 false로 통과했지만, 전달 뒤 키가 evil, intent로 바뀌고 intent 값으로 com.android.settings/.password.ChooseLockPassword를 가리키는 Intent가 나타난다. 마지막 줄은 logcat의 ArrayMap 경고](/assets/img/parcel-mismatch-trends/01-android9-self-changed-bundle.png)

Android 9(보안 패치 2019-08-05)에서는 검사 시점의 키가 `[evil, note]`였는데 전달 뒤에는 `[evil, intent]`가 됐다. 검사 단계에서는 존재하지 않던 Intent가 받는 쪽에서 생긴 것이다. ArrayMap이 남긴 경고는 키가 해시 순서에 맞지 않게 들어왔다는 뜻일 뿐이고, 동작을 막지는 않았다.

<svg viewBox="0 0 760 250" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Evil 객체가 다시 쓰일 때 4바이트가 늘어나 두 번째 읽기에서 숨긴 intent 항목이 드러나는 바이트 배치">
<style>
.pmb-c{fill:var(--surface);stroke:var(--rule-dark);stroke-width:1}
.pmb-x{fill:var(--surface);stroke:var(--red);stroke-width:2}
.pmb-h{fill:var(--surface);stroke:var(--blue);stroke-width:1.5}
.pmb-n{fill:var(--surface);stroke:var(--ink-faint);stroke-width:1;stroke-dasharray:4 3}
.pmb-v{fill:var(--ink);font:12.5px var(--mono)}
.pmb-r{fill:var(--ink-soft);font:600 12px var(--sans)}
.pmb-b{stroke:var(--ink-soft);stroke-width:1;fill:none}
.pmb-k{fill:var(--ink-soft);font:11px var(--sans)}
.pmb-red{fill:var(--red);font:600 11px var(--sans)}
</style>
<text class="pmb-r" x="10" y="20">① 공격자가 보낸 바이트 (검사 쪽이 읽음)</text>
<rect class="pmb-c" x="10" y="30" width="60" height="30"/><text class="pmb-v" x="34" y="50">1</text>
<rect class="pmb-c" x="70" y="30" width="60" height="30"/><text class="pmb-v" x="94" y="50">1</text>
<rect class="pmb-c" x="130" y="30" width="60" height="30"/><text class="pmb-v" x="143" y="50">272</text>
<rect class="pmb-h" x="190" y="30" width="250" height="30"/><text class="pmb-v" x="200" y="50">"intent" → Intent(…)</text>
<rect class="pmb-n" x="440" y="30" width="200" height="30"/><text class="pmb-v" x="450" y="50">"note" → "benign"</text>
<path class="pmb-b" d="M10 66 v6 h50 v-6"/><text class="pmb-k" x="22" y="86">id</text>
<path class="pmb-b" d="M70 66 v6 h50 v-6"/><text class="pmb-k" x="82" y="86">ct</text>
<path class="pmb-b" d="M130 66 v6 h300 v-6"/><text class="pmb-k" x="200" y="86">data (byte[] 272바이트, 숨긴 항목은 여기 안에)</text>
<text class="pmb-r" x="10" y="122">② 검사 쪽이 다시 쓴 바이트 (id를 long으로 씀)</text>
<rect class="pmb-c" x="10" y="132" width="60" height="30"/><text class="pmb-v" x="34" y="152">1</text>
<rect class="pmb-x" x="70" y="132" width="60" height="30"/><text class="pmb-v" x="94" y="152">0</text>
<rect class="pmb-c" x="130" y="132" width="60" height="30"/><text class="pmb-v" x="154" y="152">1</text>
<rect class="pmb-c" x="190" y="132" width="60" height="30"/><text class="pmb-v" x="203" y="152">272</text>
<rect class="pmb-h" x="250" y="132" width="250" height="30"/><text class="pmb-v" x="260" y="152">"intent" → Intent(…)</text>
<rect class="pmb-n" x="500" y="132" width="200" height="30"/><text class="pmb-v" x="510" y="152">"note" → "benign"</text>
<text class="pmb-red" x="66" y="182">늘어난 4바이트</text>
<text class="pmb-r" x="10" y="212">③ 받는 쪽이 읽은 결과</text>
<text class="pmb-k" x="10" y="232">id=1, ct=0, data 길이=1 → 272가 1바이트 배열로 소비됨 → 다음 키로 "intent"가 읽힘 → 항목 수(2)를 채워 "note"는 버려짐</text>
</svg>

같은 코드를 Android 13(보안 패치 2024-03-01)에서 돌리면 결과가 달라진다.

![Windows Terminal에서 Android 13 에뮬레이터(보안 패치 2024-03-01)로 같은 데모를 실행한 화면. 검사와 전달 모두 키가 evil, note로 같고 intent는 null이다. Evil 객체만 id=1, ct=0, data.len=1로 깨져 있고, 마지막 줄 logcat에 E/Parcel Unparcelling of Evil of type VAL_PARCELABLE consumed 52 bytes, but 336 expected가 찍혀 있다](/assets/img/parcel-mismatch-trends/02-android13-lazyvalue.png)

전달 뒤에도 키는 `[evil, note]`이고 `intent`는 생기지 않았다. 대신 `Evil` 객체 하나만 `ct=0, data.len=1`로 깨졌다. LazyValue가 값마다 길이를 붙여 두었기 때문에, 한 값 안에서 생긴 어긋남이 다음 키로 번지지 않은 것이다. 논문이 말한 M2의 효과가 그대로 보인다.

더 눈에 띈 것은 logcat이었다. "52바이트를 소비했는데 336바이트가 와야 했다"는 오류가 `Log.wtf`로 찍혔지만 프로세스는 계속 실행되었고, 깨진 객체도 그대로 반환되었다. 논문이 Length Without Validation이라고 부른 약점이 바로 이 동작이다. 내 실험에서는 이 동작이 무해했지만, MS2의 키 정렬 기법은 바로 이 "선언된 길이를 넘어 읽어도 멈추지 않는" 성질을 이용한다. 방어가 들어온 버전에서도 바닥에는 같은 불안정성이 남아 있다는 것을 로그 한 줄로 확인한 셈이다.

### 3-6 한계

저자들은 분석 대상이 AOSP의 Settings와 services.jar뿐이라 OEM이 추가한 서비스와 시스템 앱은 다루지 못했다는 점, BroadcastReceiver와 Service 컴포넌트로 모델을 넓히는 일이 남았다는 점을 한계로 적었다.

읽으면서 내가 따로 적어 둔 점들도 있다.

평가의 무게가 사람에게 많이 실려 있다. AC#3은 1,326건이 걸렸는데, 대부분 Settings 컴포넌트가 같은 부모 클래스를 상속해서 생긴 중복이다. 미탐 평가도 RQ1에서 걸린 17개 컴포넌트와 과거 취약점 목록을 사람이 다시 본 정도라서, ParcelTaint가 무엇을 놓치는지는 정량적으로 알기 어렵다.

초록과 본문 숫자도 조금 다르다. 초록은 CVE 5건이라고 쓰고, 결론과 비교표는 구글 쪽 CVE 4건에 화웨이 1건을 따로 센다. 큰 문제는 아니지만 인용할 때는 구분해서 쓰는 편이 좋겠다.

## 4. 후속 논문: Fragile Deliveries

| 항목 | 내용 |
|---|---|
| 논문 제목 | Fragile Deliveries: Inconsistencies in Android Parcel and Their Security Consequences |
| 저자 | Hongkai Chen, Chao Wang, Yuqing Yang, Jennifer Miller, Tiffany Bao, Ruoyu Wang, Adam Doupé, Zhiqiang Lin, Yan Shoshitaishvili |
| 게재처 | ACM MobiSys 2026 (영국 케임브리지). [ACM DL](https://dl.acm.org/doi/10.1145/3745756.3809193), CC BY 4.0 |
| 연구 주제 | Parcelable 읽기·쓰기 불일치의 생태계 규모 측정과, 잘못된 Parcel로 앱을 계속 죽이는 서비스 거부 공격 |
| 핵심 기여 | 펌웨어 324개·앱 10,161개 대규모 분석, 값 제약 불일치라는 새 유형, Malformed Parcel DoS 공격 |

### 4-1 중심 논문과의 연결

중심 논문이 미래 과제로 남긴 "OEM으로 넓히기"를 정면으로 한 논문이다. 다만 연구 자체는 거의 같은 시기에 따로 진행된 것으로 보인다. 중심 논문은 관련 연구 목록에서 한 번 인용될 뿐이다.

새로 정리한 유형은 값 제약 불일치다. CVE-2023-20963(WorkSource, Pinduoduo가 쓴 그 취약점)을 단순화한 예에서, 읽는 쪽은 `count > 0`일 때만 목록을 읽고 쓰는 쪽은 목록이 비어 있어도 크기 0을 쓴다. 자료형은 모두 맞는데 `{1, -1, 1}`을 넣으면 한 번 왕복한 뒤 `{0, 0, 1}`이 되어 다음 필드가 밀린다. 자료형만 비교하는 도구로는 찾을 수 없는 불일치라서, 이 논문이 분석기에 조건 분기의 의미 구간 비교를 넣은 이유가 여기 있다.

### 4-2 방법론과 결과

9개 벤더, Android 6부터 14까지, 벤더·버전 조합마다 펌웨어 4개씩 총 324개를 분석했다. jadx로 디컴파일한 Java 소스를 AST로 읽어 Parcelable의 읽기·쓰기 메서드를 짝지어 비교하는 방식이라 펌웨어 하나에 평균 102초면 끝난다. 결과는 펌웨어의 87.35%에서 불일치가 나왔고, 고유 취약점 36개 중 25개가 새로 찾은 것이었다. 전체의 14.11%는 벤더가 추가한 코드에서 나왔다.

두 번째 축은 가용성이다. 공격자가 형식이 맞지 않는 Parcel을 넣은 Bundle을 보내면 받는 앱이 Bundle을 여는 순간 BadParcelableException으로 죽는다. 보내는 쪽이 먼저 죽는 문제는 빈 Bundle을 넣은 뒤 `replaceExtras()`로 바꿔치기하는 방법으로 피했다. 그리고 `sendBroadcast()`를 백그라운드에서 반복하고 부팅 완료 브로드캐스트에 등록해 재부팅 뒤에도 공격을 이어 간다. 앱 10,161개 중 37.97%가 취약했고, 픽셀 6a 기본 앱 중에서는 전화, 메시지, 런처, 설정, Play 스토어가 포함됐다. 런처를 계속 죽이면 기기를 사실상 쓸 수 없게 된다.

### 4-3 한계

오탐 169건 중 64.5%가 jadx 디컴파일 오류에서 나왔고, try-catch를 다루지 못해 CVE-2021-0928 같은 알려진 사례를 놓쳤다. 무엇보다 이 논문은 "불일치가 있는 클래스"를 세지, 그 클래스가 실제 공격 체인에 닿는지는 사람이 확인했다(36개 중 32개가 악용 가능). 중심 논문이 공격 체인을 자동으로 찾고 불일치는 사례 위주로 다룬 것과 정확히 반대 방향이다. 두 연구를 합치면 클래스 단위 탐지와 체인 단위 탐지가 맞물린다.

제안한 방어에서 흥미로운 긴장이 생긴다. 이 논문은 IPC를 보내기 전에 읽기, 쓰기, 다시 읽기를 미리 해 보고 결과를 비교하자고 제안했고, 구글이 일부 서비스에 이 방식을 쓰기 시작했다고 적었다. 그런데 이것은 M1(`checkKeyIntentParceledCorrectly`)을 일반화한 형태다. 중심 논문은 M1이 여러 번 우회된 근본 원인을 "모의 실행과 실제 실행 환경이 같다고 보장하기 어렵다"는 데서 찾았다. MS2처럼 역직렬화 중에 상태를 바꾸는 클래스나, MS3처럼 받는 쪽이 다른 CREATOR로 읽는 경우는 모의 왕복으로 재현되지 않을 수 있다. 두 논문을 같이 읽으면 시뮬레이션 기반 방어가 어디까지 믿을 만한지가 아직 열린 질문이라는 게 보인다.

## 5. 후속 논문: LLM 기반 안드로이드 오염 분석

| 항목 | 내용 |
|---|---|
| 논문 제목 | Towards LLM-Enhanced Android Taint Analysis |
| 저자 | Nicholas Miazzo, Marco Alecci, Jordan Samhi, Jacques Klein, Eleonora Losiouk |
| 공개 | [arXiv 2608.24269](https://arxiv.org/abs/2608.24269), 2026년 8월 25일. 학회 게재 전 프리프린트 |
| 연구 주제 | 프레임워크 모델 없이 LLM 에이전트가 안드로이드 앱의 오염 흐름을 추론할 수 있는가 |
| 핵심 기여 | JADX-MCP, Ghidra-MCP를 쓰는 에이전트형 분석과 다수결 투표, DroidBench와 실제 앱에서 FlowDroid와 비교 |

### 5-1 중심 논문과의 연결

이 논문은 중심 논문을 인용하지 않고, 대상도 시스템 서비스가 아니라 일반 앱이다. 그래도 후속으로 고른 이유가 있다. ParcelTaint에서 엔지니어링이 가장 많이 들어간 부분은 Intent를 라우팅과 페이로드로 나눈 모델, 그리고 `startActivity`와 `getIntent`를 잇는 ICC 규칙이었다. 사람이 프레임워크 의미를 하나하나 규칙으로 옮긴 것이다. 이 논문은 바로 그 작업을 LLM이 대신할 수 있는지 묻는다. 중심 논문이 기댄 분석 방법이 다음에 어디로 갈지를 보여 주는 연구라고 봤다.

### 5-2 방법론과 결과

APK를 JADX에 올리고, 네이티브 라이브러리가 있으면 Ghidra에 올린다. LLM은 MCP로 메서드와 교차 참조를 조회하며 소스에서 싱크까지의 흐름을 스스로 탐색하고, 결과를 JSON으로 낸다. 비결정성 때문에 같은 앱을 여러 번 돌려 과반이 보고한 흐름만 남긴다. 에이전트 실행에는 Claude Code와 Gemini CLI를 썼다.

| 비교 | FlowDroid | Gemini 3 Flash | Qwen3.5-27B |
|---|---|---|---|
| DroidBench 전체 F1 | 0.55 | 0.96 | 0.88 |
| ICC 범주 F1 | 0.17 | 0.95 | 0.97 |
| 암묵적 흐름 F1 | 0.00 | 0.94 | 0.22 |

실제 앱 5개에서는 FlowDroid가 못 본 흐름 17개를 더 찾았고, 사람이 확인한 결과 16개가 참이고 1개는 환각이었다.

### 5-3 한계

저자들 스스로 예비 연구라고 부른다. 비교 대상이 ICC 확장(IccTA)을 켜지 않은 기본 설정의 FlowDroid라서 ICC 범주 격차는 과장되었을 수 있다. 실제 앱 표본도 5개뿐이다. 오픈 모델(Qwen)은 ICC에서는 오히려 더 높았지만 암묵적 흐름에서 0.22에 그쳐, 범주와 모델에 따라 결과가 크게 갈렸다. 무엇보다 앱 하나 크기의 코드에서 얻은 결과라서, services.jar처럼 수만 개 클래스가 얽힌 시스템 서버에 그대로 통할지는 알 수 없다.

## 6. 연구 흐름 정리

| 논문 | 불일치를 어디서 봤나 | 방법 | 분석 대상 |
|---|---|---|---|
| Kratos (2016) | 같은 기능으로 가는 경로끼리 검사가 다름 | 콜 그래프 수렴 비교 | AOSP·벤더 프레임워크 |
| Invetter (2018) | 검사가 앱이 보낸 값을 믿음 | 구조 분석 + 연관 규칙 학습 | 시스템 서비스 입력 검증 |
| Parcel Mismatch (2025) | 검사한 객체와 직렬화 뒤 쓰이는 객체가 다름 | 프로세스 간 포인터·오염 분석 | services.jar, Settings |
| Fragile Deliveries (2026) | 같은 불일치가 생태계 전체에 얼마나 퍼졌나, 가용성까지 | AST 기반 읽기·쓰기 비교 | 펌웨어 324개, 앱 1만여 개 |
| LLM Taint (2026) | 사람이 짠 프레임워크 모델의 공백 | LLM 에이전트 + MCP 도구 | 일반 앱 |

나는 이 흐름을 "검사 지점과 사용 지점 사이의 거리"가 점점 멀어지는 과정으로 읽었다. Kratos에서는 한 프로세스 안의 두 경로를 비교했고, Invetter에서는 SDK와 서비스라는 두 신뢰 영역 사이로 넓어졌다. 중심 논문에 와서는 시간과 프로세스가 끼어든다. 검사한 시점과 쓰는 시점 사이에 직렬화가 한 번 있고, 그 사이에서 데이터가 바뀐다. 운영체제 수업에서 배운 TOCTOU가 IPC 직렬화 층에서 다시 나타난 셈이다.

연구가 바라보는 쪽도 바뀌었다. 초기 연구는 취약점을 찾는 데 집중했고, 중심 논문은 구글이 넣은 방어가 실제로 버티는지를 평가 대상으로 삼았다. 후속 연구는 측정 범위를 벤더 펌웨어와 앱 전체로 넓히면서 권한 상승 말고 가용성 피해까지 다뤘다. 분석 엔진은 Soot와 AppShark 위에 사람이 규칙을 얹던 방식에서, LLM이 코드를 직접 돌아다니는 방식으로 실험이 시작되었다.

벤더 문제는 2016년부터 2026년까지 모든 논문에 등장한다. Kratos의 삼성 기기, Invetter의 샤오미 이미지, 중심 논문의 화웨이 EMUI, Fragile Deliveries의 벤더 유래 14%까지. 구글이 Android 13에 넣은 방어는 Android 12 기반으로 머무는 OEM 기기에는 닿지 않는다. 이 분야에서 가장 오래 남을 숙제가 아닐까 싶다.

## 7. 앞으로의 방향

탐지보다 "손으로 짠 직렬화 코드를 없애는" 방향이 결국 근본 해법이 될 것 같다. 불일치는 개발자가 `writeToParcel`과 `createFromParcel`을 따로 손으로 쓰기 때문에 생긴다. AIDL의 구조화된 parcelable처럼 정의 하나에서 읽기와 쓰기 코드를 같이 생성하면 MS1은 구조적으로 생기기 어렵다. 다만 Fragile Deliveries에 따르면 Android 13 펌웨어 하나에 Parcelable 클래스가 1,500개를 넘는다. 이런 상황에서 기존 클래스를 모두 옮기는 일은 오래 걸릴 것이다. 그래서 당분간은 전환이 끝나지 않은 클래스만 골라 집중 감사하는 도구가 필요하다.

길이 검증은 경고가 아니라 실패여야 한다. 에뮬레이터에서 본 `consumed 52 bytes, but 336 expected` 로그는, 시스템이 이상을 알아차리고도 계속 진행한다는 뜻이다. 저자들도 호환성 때문에 이 수정이 늦어진다고 적었다. 앱 호환성 비용을 감수하고 엄격 모드를 기본값으로 바꾸는 시점이 언제 올지가 다음 안드로이드 버전에서 지켜볼 지점이다.

방어의 위치도 바뀌어야 한다. "보내기 전에 모의로 확인"하는 쪽보다 "쓰는 곳에서 다시 확인"하는 쪽으로 가야 한다고 생각한다. M1과 Fragile Deliveries의 시뮬레이션은 모두 검사하는 쪽이 받는 쪽의 해석을 흉내 내는 방식이다. 흉내는 받는 쪽 코드가 바뀌거나 다른 CREATOR를 쓰면 틀어진다. 반면 Intent를 실제로 실행하는 Settings나 SystemUI가 마지막에 호출자 권한과 대상 컴포넌트를 다시 확인하면 직렬화가 몇 번 끼어들든 상관없다. 중심 논문의 NMS 체인과 AppRestrictionsFragment 체인이 모두 받는 쪽 확인이 약했던 곳이라는 점도 이 생각을 뒷받침한다.

LLM은 정적 분석을 대체하기보다 정적 분석이 남긴 후보를 판정하는 자리에 먼저 들어올 것 같다. ParcelTaint의 오탐(AC#1)은 "실행을 끊는 복잡한 권한 검사"를 정적 분석이 모델링하지 못해서 생겼다. LLM 에이전트가 강한 영역이 바로 이런 의미 판단이다. 정적 분석으로 IPC 경계와 Bundle 수정 지점을 좁히고, 남은 후보마다 LLM이 "이 경로가 권한 검사에서 끊기는가, 바이트가 어떻게 밀리는가"를 따지는 하이브리드가 현실적이다. 다만 바이트 오프셋을 정확히 세는 일은 LLM이 틀리기 쉬운 영역이라, 내 실험처럼 에뮬레이터에서 실제 왕복을 돌려 보는 검증 단계가 같이 붙어야 할 것이다.

마지막으로 대상 플랫폼이 넓어질 것이다. Fragile Deliveries는 HarmonyOS NEXT도 같은 구조의 Parcelable을 갖고 있고, 읽기와 쓰기를 비대칭으로 구현하면 같은 불일치가 생긴다는 것을 확인했다. 안드로이드 코드를 쓰지 않는 새 모바일 OS도 같은 설계를 물려받았다는 뜻이다. 다음 몇 년의 논문은 아마 이 다른 운영체제들에서 같은 질문을 다시 던질 것이다.

## 참고 자료

- Yuru Shao 외, [Kratos: Discovering Inconsistent Security Policy Enforcement in the Android Framework](https://www.ics.uci.edu/~alfchen/pubs/roy_ndss16.pdf), NDSS 2016
- Lei Zhang 외, [Invetter: Locating Insecure Input Validations in Android Services](https://dl.acm.org/doi/10.1145/3243734.3243843), ACM CCS 2018
- Sheng Cao 외, [Parcel Mismatch Demystified: Addressing a Decade-Old Security Challenge in Android](https://dl.acm.org/doi/10.1145/3719027.3765034), ACM CCS 2025
- Hongkai Chen 외, [Fragile Deliveries: Inconsistencies in Android Parcel and Their Security Consequences](https://dl.acm.org/doi/10.1145/3745756.3809193), ACM MobiSys 2026
- Nicholas Miazzo 외, [Towards LLM-Enhanced Android Taint Analysis](https://arxiv.org/abs/2608.24269), arXiv 2026
