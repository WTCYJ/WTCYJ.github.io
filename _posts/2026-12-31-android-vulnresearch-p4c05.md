---
layout: post
title: "System Service 공격 표면"
date: 2026-12-31 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, system_server, Binder, AIDL, Parcel]
excerpt: "system service는 SELinux가 막아준다고 믿기 쉽지만, service_contexts의 find 권한과 메서드 진입부의 권한 검사는 서로 다른 계층이다 — 하나가 통과해도 다른 하나가 비어 있으면 거기가 공격 표면이다."
---

Android에서 가장 값진 공격 표면은 앱이 아니라 **앱이 부를 수 있는 특권 코드**다. 임의의 설치 앱은 UID system(1000)으로 도는 `system_server`의 수백 개 서비스 메서드에 Binder 트랜잭션을 던질 수 있다. 호출자는 권한이 거의 없고 피호출자는 사실상 프레임워크 전체를 만질 수 있으니, 모든 서비스 메서드는 신뢰 경계를 한 번씩 넘는 지점이다. 그래서 취약점 연구에서 "어디를 볼 것인가"의 답 대부분이 여기 있다.

이 글은 그 표면을 **어떻게 열거하고, 무엇이 그 표면을 지키며, 어디가 비면 버그가 되는지**를 공개 소스(AOSP)와 에뮬레이터 관측으로 분석·정리한 기록이다. 무기화된 익스플로잇은 없고, 이미 공개·패치된 버그 클래스만 원리 수준에서 다룬다.

> **한 줄 결론**: 시스템 서비스에 도달 가능한지는 SELinux `service_manager find`가 가르고, 그 서비스가 무엇을 허용하는지는 메서드 진입부의 권한 검사가 가른다 — 두 계층은 독립이고, 연구자가 노리는 건 둘 중 하나가 비어 있는 서비스다.

## 무엇을 다루고, 무엇을 알아야 하는가

다루는 범위는 세 가지다. (1) 시스템 서비스가 어디에 살고 어떻게 노출되는지, (2) 호출을 막는 게이트가 몇 겹이고 각각 어디에 있는지, (3) 그 게이트가 빌 때 나타나는 대표 버그 클래스(권한 검사 누락, Parcel 역직렬화 불일치)다. 실제 익스플로잇 작성은 이 부(4부)의 다음 장 "Binder/AIDL service fuzzing"으로 넘긴다. 이 장은 그 퍼징의 **표적 선정 지도**다.

선수 지식으로는 Binder가 커널 드라이버를 통해 프로세스 간에 Parcel(직렬화된 바이트 + 파일 디스크립터/바인더 참조)을 전달하는 IPC라는 것, AIDL이 그 Parcel의 읽기/쓰기 코드를 자동 생성한다는 것, 그리고 Android 권한이 매니페스트 선언과 런타임 enforce로 나뉜다는 것을 알아야 한다. 이 개념들은 개념 Atlas의 Binder·IPC 항목과 권한 모델 항목에 정리돼 있고, 실습 환경(계측 가능한 userdebug 에뮬레이터)은 1부에서 세운 그대로 쓴다. 3부에서 앱 쪽 IPC(exported 컴포넌트)를 봤다면, 이 장은 그 반대편 — 특권 프로세스가 받는 쪽 — 을 본다.

전체 구조에서 이 장은 4부의 **표적 정의** 단계다. 이후 장들의 하네스·코퍼스·크래시 분석이 전부 "여기서 고른 서비스"를 겨냥한다.

## 핵심 개념 — 서비스 하나에 걸린 게이트는 여러 겹이다

시스템 서비스는 대부분 `system_server` 프로세스 안에 사는 Java 객체이고, 부팅 시 `ServiceManager`에 이름으로 등록된다. 앱은 `Context.getSystemService(...)`나 (숨겨진) `ServiceManager.getService("name")`로 Binder 핸들을 얻어 `transact()`를 호출한다. AIDL 스텁이 이 트랜잭션을 메서드 호출로 풀어낸다. `Source-confirmed` (AOSP `frameworks/base` ServiceManager/AIDL 스텁 구조)

핵심은 **호출이 실제로 실행되기까지 통과하는 게이트가 여러 겹**이고, 각 겹이 다른 곳에 산다는 점이다.

| 게이트 | 어디에 있나 | 실패하면 | 근거 |
|--|--|--|--|
| SELinux `service_manager find` | `service_contexts` + sepolicy `allow` 규칙 | 핸들 획득 자체가 불가(`getService`가 null/거부) | `Source-confirmed` |
| Android permission | 서비스 메서드 진입부의 `enforceCallingPermission(...)` | `SecurityException` | `Source-confirmed` |
| AppOps | 런타임 `AppOpsManager` op 검사 | 조용히 무시 또는 거부 | `Reported` |
| Parcel 파싱 | AIDL 역직렬화 경로 | 크래시 / 로직 우회 | `Source-confirmed` |

여기서 연구자가 자주 헷갈리는 지점 세 개를 못 박아 둔다.

- **`service list`에 보인다 = 부를 수 있다, 가 아니다.** 서비스가 등록돼 있어도 내 도메인(`untrusted_app`)이 SELinux에서 그 서비스 타입을 `find`할 권한이 없으면 핸들조차 못 얻는다. 보이는 것과 도달 가능한 것은 다른 집합이다. `Source-confirmed`
- **매니페스트에 권한을 선언했다 ≠ 검사된다.** 권한은 서비스 메서드가 `enforceCallingPermission`을 **직접 호출해야** 강제된다. 선언만 있고 진입부 검사가 빠진 메서드가 전형적인 confused deputy 버그다. `Source-confirmed`
- **`clearCallingIdentity()` 이후는 안전하지 않다.** 오히려 위험하다. 이 호출은 이후 작업을 호출자가 아니라 system 신원으로 수행하므로, 권한 검사는 반드시 이 호출 **이전에** 끝나 있어야 한다. 순서가 뒤집히면 검사 없이 특권 작업이 실행된다. `Source-confirmed`

> **[그림 1]** userdebug 에뮬레이터에서 `adb shell service list`를 실행해 `system_server`에 등록된 Binder 서비스가 수백 개 나열된 터미널 — *실측 스크린샷 자리*

파서 퍼징을 해 본 사람에겐 이 그림이 익숙하게 읽힌다. libsoup의 Range 정수 오버플로를 찾을 때도, wabt 하네스를 짤 때도 첫 작업은 "외부 입력이 특권 파싱에 닿는 첫 함수"를 특정하는 것이었다. 시스템 서비스에서 그 첫 함수는 AIDL 스텁이 Parcel을 푸는 지점이고, 위 표는 그 지점에 도달하기까지의 관문 목록이다.

## 신뢰 경계와 위협 모델

위협 모델은 명확하다. 공격자는 **권한이 낮은 설치 앱**(`untrusted_app` 도메인, 임의 UID)이고, 목표는 `system_server`(UID system)나 다른 특권 서비스로 권한을 상승시키는 것이다. 공격자가 완전히 통제하는 것은 트랜잭션에 실리는 Parcel 바이트와 호출 순서다. 통제하지 못하는 것은 서비스 코드 자체와 커널 Binder 드라이버의 전달 방식이다.

여기서 커널 Binder 드라이버는 **바이트를 충실히 전달할 뿐 의미를 검증하지 않는다**. 즉 "잘 생긴 Parcel"인지, 필드가 말이 되는지는 전적으로 수신 측 AIDL 코드와 서비스 로직의 몫이다. 신뢰 경계는 커널이 아니라 서비스의 첫 줄에 그어진다. `Source-confirmed`

이 모델에서 공격 표면은 두 축으로 갈린다. **도달성 축**(SELinux가 이 서비스로 가는 길을 여는가)과 **권한 축**(도달한 뒤 이 메서드가 내 신원을 검사하는가). 연구 가치가 높은 표면은 도달은 되는데 권한 검사가 얇거나, 파싱이 복잡해 역직렬화 불일치가 숨을 여지가 큰 서비스다.

## 관측 — 에뮬레이터에서 서비스 표면 열거하기

계측 가능한 userdebug 에뮬레이터(1부 환경)에서 안전하게 표면을 열거해 본다. 전부 읽기 전용 관측이며, 상태를 바꾸거나 임의 서비스를 실제로 익스플로잇하지 않는다.

```bash
# 1) 등록된 바인더 서비스 열거
adb shell service list

# 2) 특정 서비스 상태 덤프(읽기 전용)
adb shell dumpsys package | head -n 40

# 3) 서비스가 어떤 SELinux 타입으로 라벨링됐는지 확인
adb shell cat /system_ext/etc/selinux/*_service_contexts 2>/dev/null
adb shell cat /system/etc/selinux/plat_service_contexts | head

# 4) 도달 실패 시 남는 SELinux 거부 관측(root 필요, userdebug)
adb root
adb shell dmesg | grep 'avc: denied' | grep service_manager
```

`예시 출력(교체 — 실제 실행으로 대체)`:

```
$ adb shell service list
Found 214 services:
0	accessibility: [android.view.accessibility.IAccessibilityManager]
1	account: [android.accounts.IAccountManager]
2	activity: [android.app.IActivityManager]
...
213	window: [android.view.IWindowManager]

$ adb shell cat /system/etc/selinux/plat_service_contexts | head
accessibility            u:object_r:accessibility_service:s0
account                  u:object_r:account_service:s0
activity                 u:object_r:activity_service:s0
```

여기서 표적 선정의 실제 절차는 두 목록을 **교차**하는 것이다. `service list`가 준 이름을 `service_contexts`의 SELinux 타입으로 매핑하고, sepolicy에서 `untrusted_app`이 그 타입을 `find`할 수 있는지 확인한다. `find`가 허용된 서비스만이 앱에서 실제로 도달 가능한 1차 표면이다. 도달 가능한 목록을 좁힌 뒤, 각 서비스의 AIDL 인터페이스에서 인자 파싱이 복잡한 메서드(중첩 `Bundle`, `Parcelable` 배열, 길이 필드로 반복 읽는 메서드)를 다음 장 퍼징 대상 후보로 남긴다.

> **[그림 2]** `service list`의 한 서비스 이름을 `plat_service_contexts`의 SELinux 타입과 나란히 놓고, 해당 타입이 `untrusted_app`에서 `find` 가능한지 대조한 화면(두 파일/명령 출력을 한 캡처에) — *실측 스크린샷 자리*

## Root Cause — 왜 이 표면이 위험한가

근본 원인은 아키텍처에 있다. Binder는 설계상 **권한이 낮은 프로세스가 특권 프로세스의 트랜잭션 핸들러에 임의 바이트를 직접 전달**하도록 허용한다. 이 비대칭(호출자는 UID 임의, 피호출자는 UID system) 자체가 표면을 만든다. 안전은 오직 서비스가 (a) 진입부에서 호출자 신원을 검사하고 (b) 입력을 방어적으로 파싱할 때만 성립한다. 커널은 이 둘 중 어느 것도 대신 해 주지 않는다. `Source-confirmed`

그래서 실패 모드는 두 가지로 수렴한다.

- **권한 검사 누락/오류 (confused deputy).** 메서드가 `Binder.getCallingUid()`/`enforceCallingPermission`으로 신원을 확인하지 않거나, `clearCallingIdentity()` 이후에 검사하면, 낮은 권한 앱이 system 권한으로 동작을 대신 수행시킬 수 있다. 이건 메모리 버그가 아니라 **로직 버그**이고, 종종 CVSS상 권한 상승으로 분류된다. `Source-confirmed` (AOSP의 권한 검사 관용구 기준)
- **Parcel/Bundle 역직렬화 불일치 (mismatch).** 어떤 객체를 Parcel에 **쓸 때와 읽을 때 소비하는 바이트 수가 달라지면**, 악의적 Parcel이 뒤따르는 데이터의 해석을 어긋나게 만들 수 있다. 대표적으로, 겉보기엔 무해한 중첩 `Bundle`이 특권 프로세스를 거쳐 다시 직렬화될 때 다른 객체로 재해석되어, 원래 없던 필드가 특권 컨텍스트에서 살아나는 형태다. 이 "self-changing Bundle" 계열은 2017년 `GateKeeperResponse` 사례(CVE-2017-0806, 정확한 귀속은 불리틴 재확인 필요)를 필두로 여러 차례 보고·수정됐다. `Reported`

두 실패 모드의 공통점은 **입력이 신뢰 경계를 넘는 첫 지점에서 검증이 비었다**는 것이다. 이 지점을 특정하는 훈련이 곧 파서 취약점 연구와 같다.

## 방어와 회귀 검증

방어는 게이트를 겹으로 세우고, 각 겹이 실제로 채워졌는지 검증하는 것이다.

- **진입부 권한 검사, 신원 삭제보다 먼저.** 서비스 메서드는 `enforceCallingPermission(...)` 또는 `Binder.getCallingUid()` 비교를 `clearCallingIdentity()` 이전에 수행해야 한다. 순서 검증이 회귀 테스트의 핵심 항목이다. `Source-confirmed`
- **SELinux를 2차 계층으로.** `service_contexts` 라벨과 `neverallow` 규칙으로 `untrusted_app`이 민감 서비스를 아예 `find`하지 못하게 막는다. 권한 검사와 **독립적**이므로 둘 다 있어야 방어가 완성된다. `Source-confirmed`
- **대칭 직렬화로 mismatch 차단.** 읽기/쓰기 바이트 수를 일치시키고(예: `LazyValue`류 지연 파싱), 프레임워크가 Parcel 소비량 불일치를 감지하도록 강화했다. 도입/동작 세부와 적용 API 레벨은 원문 재확인 필요. `Reported`
- **회귀 검증 절차.** 이미 패치된 공개 CVE에 대해, baseline 이미지와 patched 이미지에서 같은 호출을 재현해 "patched에서는 `SecurityException`을 던지거나 크래시하지 않는다"를 대조한다. 안전 범위 안에서 방어의 유효성을 확인하는 표준 워크플로다. 실제 자동화된 트랜잭션 퍼징은 다음 장에서 다룬다.

**버전에 따른 표면 변화(짧게).** API 28부터 강화된 hidden API 제한은 앱이 반사로 내부 서비스 인터페이스를 건드리는 경로를 좁혔고, seccomp/SELinux 정책도 버전마다 조여졌다. 즉 "옛 버전에서 되던 도달 경로"가 최신에서 막히는 일이 흔하니, 재현 실패를 곧바로 버그 부재로 읽지 말고 대상 API 레벨을 먼저 기록해야 한다. `Reported`

과장은 피한다. 여기서 다루는 대다수는 권한 상승 또는 DoS(크래시)이지 그 자체로 RCE가 아니다. system_server 크래시는 기기 재부팅 수준의 DoS이고, 이를 메모리 통제 가능한 손상으로 끌어올릴 수 있느냐는 별도 증명이 필요한 주장이다.

## 정리

- 시스템 서비스는 임의 앱이 UID system 코드에 임의 Parcel을 던지는 표면이며, 모든 서비스 메서드가 신뢰 경계 통과 지점이다.
- 도달성은 SELinux `service_manager find`가, 행위 허용은 메서드 진입부 권한 검사가 가른다 — 두 계층은 독립이고 연구 표적은 둘 중 하나가 빈 서비스다.
- 대표 버그 클래스는 권한 검사 누락(confused deputy)과 Parcel/Bundle 역직렬화 불일치이며, 둘 다 "경계를 넘는 첫 지점의 검증 부재"로 수렴한다.
- 커널 Binder는 바이트만 전달하고 의미를 검증하지 않는다 — 안전은 전적으로 수신 측 코드의 몫이다.

**점검 질문** — (1) `service list`에 보이는 서비스를 앱에서 부르지 못할 수 있는 이유는? (2) `clearCallingIdentity()` 앞이 아니라 뒤에서 권한을 검사하면 왜 위험한가? (3) Parcel 역직렬화 "불일치"가 로직 우회로 이어지는 기본 원리를 한 문장으로 말하면?

**참고** — [Android 보안(source.android.com)](https://source.android.com/docs/security) · [AIDL/Binder 개요](https://developer.android.com/develop/background-work/services/aidl) · [SELinux for Android](https://source.android.com/docs/security/features/selinux) · [Android Security Bulletins](https://source.android.com/docs/security/bulletin) · AOSP `frameworks/base`(ServiceManager·Parcel·Bundle), `system/sepolicy`(service_contexts)

*다음 글: [Binder/AIDL service fuzzing](/posts/android-vulnresearch-p4c06/).*
