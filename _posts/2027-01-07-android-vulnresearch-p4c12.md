---
layout: post
title: "SELinux policy·service_contexts 감사"
date: 2027-01-07 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, SELinux, SEAndroid, service_contexts, sepolicy]
excerpt: "servicemanager는 SELinux service_manager 클래스의 객체 관리자다. 그래서 service_contexts의 타입과 untrusted_app의 find 규칙이 곧 '비특권 앱이 도달 가능한 IPC 공격 표면'을 정의한다. 함정 — allow 규칙이 있다고 취약점이 아니고, userdebug에서 permissive로 보이던 도메인이 user 빌드에선 enforcing이다."
---

시스템 서비스를 퍼징하려면(5장·6장) 먼저 "비특권 앱이 실제로 어느 서비스에 손을 댈 수 있나"를 알아야 한다. 이 답을 감으로 찍으면 안 된다. Android는 DAC(UID/GID) 위에 MAC(SELinux)을 한 겹 더 얹고, `servicemanager`가 그 MAC의 객체 관리자로 동작해서 서비스 조회 하나하나를 커널 SELinux에 물어본다. 그러니 "도달 가능한 서비스 집합"은 정책 파일에 명시돼 있다 — 읽어내면 된다.

이 글은 `service_contexts`와 sepolicy를 정적으로 감사해서, `untrusted_app` 도메인이 `find` 할 수 있는 서비스 타입 집합 = 퍼징 공격 표면을 뽑아내는 워크플로를 정리·분석한 기록이다. 정책 읽기는 그 자체가 읽기 전용이라 안전 범위 안에 있고, 익스플로잇은 하지 않는다.

> **한 줄 결론**: `sesearch -A -s untrusted_app -c service_manager -p find`가 앱이 도달 가능한 서비스 타입을 그대로 뽑아준다. 단, 규칙 대상은 대개 단일 타입이 아니라 `app_api_service` 같은 **속성(attribute)**이라 seinfo로 펼쳐야 실제 서비스 이름이 나오고, allow 규칙의 존재는 '도달성'일 뿐 취약점이 아니다.

## 무엇을 다루고, 무엇을 알아야 하는가

범위는 세 가지다 — (1) `service_contexts`가 서비스 이름을 SELinux 타입에 어떻게 매핑하는지, (2) `servicemanager`가 `service_manager` 클래스로 `add`/`find` 권한을 어떻게 강제하는지, (3) sesearch·seinfo·sepolicy-analyze로 앱 도메인의 도달 가능 서비스와 permissive 도메인을 감사하는 절차. 익스플로잇·우회는 다루지 않는다.

선수 지식이 몇 개 깔린다. Binder와 servicemanager의 등록/조회 흐름(5장 System Service 공격 표면, 6장 Binder/AIDL)을 알아야 "무엇을 감사하는지"가 잡힌다. Atlas의 SELinux(SEAndroid) 개념 — 타입 강제(TE), 도메인, permissive vs enforcing — 도 전제다. 그리고 DAC와 MAC이 **AND 관계**라는 것: 둘 다 허용해야 통과하고, 하나만 막아도 거부된다.

전체 구조에서 이 장은 "공격 표면 확정" 단계다. 앞의 5·6장이 서비스를 열거하고 퍼징 하네스를 세웠다면, 이 장은 그중 **비특권 앱이 진짜 도달 가능한 것**으로 표면을 좁힌다. 뒤의 13장(HAL·vendor boundary)은 여기서 나온 vendor 쪽 서비스로 이어진다.

## 핵심 개념 — service_contexts와 객체 관리자

`servicemanager`는 단순한 이름→핸들 디렉터리가 아니다. SELinux의 `service_manager` 클래스에 대한 **userspace 객체 관리자**로 등록돼 있어서, 프로세스가 `getService`/`checkService`(=find)나 `addService`(=add)를 호출할 때마다 `selinux_check_access`로 커널 AVC에 판정을 요청한다. `Source-confirmed`

- **주체(subject)**: 호출자 프로세스의 도메인. 앱은 `seapp_contexts` 규칙에 따라 `untrusted_app`(또는 targetSdk별 `untrusted_app_30` 등), 격리 프로세스는 `isolated_app`으로 라벨된다. `Source-confirmed`
- **객체(object)**: 서비스. `service_contexts`가 서비스 등록 이름을 타입으로 매핑한다(예: `activity → activity_service`). `Source-confirmed`
- **클래스/권한**: 클래스 `service_manager`, 권한 `add`·`find`·`list`. HAL 서비스는 별도 `hwservice_manager` 클래스와 `hwservice_contexts`를 쓴다. `Source-confirmed`

```
앱(untrusted_app) --getService("activity")--> servicemanager
      │                                            │
      │             selinux_check_access(sub=untrusted_app,
      │               obj=activity_service, cls=service_manager, perm=find)
      ▼                                            ▼
  Binder 핸들 반환 <---- 허용 ----  커널 AVC  ---- 거부 ----> null + avc: denied 로그
```

| 컨텍스트 파일 | 매핑 대상 | 클래스 | 온디바이스 위치(대략) |
|--|--|--|--|
| `plat_service_contexts` | AOSP 서비스 이름→타입 | `service_manager` | `/system/etc/selinux/` |
| `vendor_service_contexts` | OEM/vendor 서비스 | `service_manager` | `/vendor/etc/selinux/` |
| `plat_hwservice_contexts` | HAL 서비스 | `hwservice_manager` | `/system/etc/selinux/` |
| `seapp_contexts` | 앱 UID/seinfo→도메인 | (도메인 배정) | `/system/etc/selinux/` |

흔한 착각 하나 — "SELinux가 enforcing이면 앱이 시스템 서비스에 못 붙는다." 반대다. `untrusted_app`은 앱이 정상 동작하도록 **아주 많은** 서비스에 `find`가 허용돼 있고, 그게 정상이다. 감사의 목적은 "허용 여부"가 아니라 "허용된 표면이 무엇이고, 그중 vendor가 과도하게 연 게 있나"를 가려내는 것이다. `Inferred`

> **[그림 1]** `plat_service_contexts` 파일을 열어 `activity u:object_r:activity_service:s0`처럼 서비스 이름→타입 매핑 라인이 보이는 화면 — *실측 스크린샷 자리*

## 신뢰 경계와 위협 모델

위협 모델의 주체는 **비특권 앱**이다. 임의의 서드파티 앱은 `untrusted_app` 도메인에서 돌고, 이 도메인이 `find` 할 수 있는 서비스 타입이 곧 그 앱이 IPC로 두드릴 수 있는 커널 밖 공격 표면이다. 여기서 경계가 세 겹이다.

- **DAC**: Binder 자체는 UID 기반 접근 제어(서비스 내부 `checkCallingPermission` 등)를 별도로 건다. SELinux를 통과해도 서비스 코드가 UID/권한을 또 검사한다.
- **MAC(SELinux)**: `service_manager:find`. 이걸 통과 못 하면 조회 자체가 실패한다.
- **MLS 카테고리**: 같은 `untrusted_app` 타입이라도 앱마다 다른 MLS 카테고리(`c512` 등)가 붙어 앱 간 격리가 유지된다(`seapp_contexts`의 `levelFrom`). 그래서 "타입이 같다 = 서로 접근 가능"이 아니다. `Source-confirmed`

감사가 노리는 취약 지점은 AOSP 기준선이 아니라 **vendor 커스터마이징**이다. OEM이 `vendor_service_contexts`에 디버그·진단 서비스를 추가하면서 `untrusted_app`에 `find`를 열어두는 실수가 실제 표면 확장의 주된 출처다. `Inferred` AOSP `system/sepolicy`는 `neverallow` 규칙으로 위험한 조합을 컴파일 타임에 막지만(secilc/checkpolicy가 위반 시 빌드 실패), vendor 정책이 그 경계를 우회해 새 타입을 여는 건 별개다. `Source-confirmed`

## 관측

감사는 컴파일된 이진 정책을 기기에서 뽑아 setools로 질의하는 게 실무다. 전부 읽기 전용이고 상태를 바꾸지 않는다.

### 절차

1. 텍스트 컨텍스트 파일은 world-readable라 root 없이 가져온다.
2. 이진 정책은 userdebug 에뮬레이터에서 `adb root` 후 `/sys/fs/selinux/policy`를 뽑는다.
3. `sesearch`로 `untrusted_app`의 `service_manager:find` 규칙을 뽑고, 대상이 속성이면 `seinfo -a`로 펼친다.
4. `sepolicy-analyze permissive`로 permissive 도메인이 있는지 확인한다(있으면 그 도메인은 사실상 미강제).

```bash
# 1) 컨텍스트/CIL은 root 없이도 가능
adb pull /system/etc/selinux/plat_service_contexts
adb pull /vendor/etc/selinux/vendor_service_contexts 2>/dev/null

# 2) 이진 정책 (userdebug 에뮬레이터에서만)
adb root && adb pull /sys/fs/selinux/policy sepolicy.bin

# 3) untrusted_app이 find 가능한 서비스 타입
sesearch -A -s untrusted_app -c service_manager -p find sepolicy.bin

# 4) permissive 도메인 확인 (AOSP host tool)
sepolicy-analyze sepolicy.bin permissive
adb shell getenforce
```

> **[그림 2]** `sesearch -A -s untrusted_app -c service_manager -p find`의 출력과, 이어서 `seinfo -a app_api_service -x`로 속성을 펼친 화면을 한 프레임에 대조한 캡처 — *실측 스크린샷 자리*

### 관측 결과

`예시 출력`(실제 실행으로 교체):

```
$ sesearch -A -s untrusted_app -c service_manager -p find sepolicy.bin
allow untrusted_app app_api_service:service_manager find;
allow untrusted_app audioserver_service:service_manager find;
allow untrusted_app textclassification_service:service_manager find;

$ seinfo -a app_api_service -x sepolicy.bin
   app_api_service
      activity_service
      account_service
      clipboard_service
      package_service
      ...

$ sepolicy-analyze sepolicy.bin permissive
(빈 출력 = permissive 도메인 없음; userdebug에선 일부가 뜰 수 있다)

$ adb shell getenforce
Enforcing
```

여기서 핵심 함정 — 3행의 규칙 대부분은 **`app_api_service`라는 속성**을 가리킨다. 이 속성 하나에 수십 개 서비스 타입이 묶여 있어서, sesearch 출력만 보고 "앱이 접근 가능한 서비스는 셋뿐"이라고 세면 틀린다. seinfo로 속성을 펼쳐야 실제 도달 가능 서비스 명단이 나온다. `Source-confirmed` 그 명단을 `service_contexts`로 역매핑하면 6장의 Binder/AIDL 퍼징 대상 리스트가 확정된다.

두 번째 함정 — `getenforce`가 Enforcing이어도, `sepolicy-analyze permissive`에 뜬 도메인은 개별적으로 미강제다. userdebug 에뮬레이터에서 "막힐 줄 알았는데 통과"하는 경우 이 permissive 도메인이 원인일 때가 많고, 같은 도메인이 user(production) 빌드에선 enforcing이라 재현이 안 된다.

## Root Cause — 왜 이렇게 되는가

구조를 뜯어보면 이 감사가 왜 정적으로 가능한지가 보인다. servicemanager는 부팅 시 SELinux 콜백을 등록해 `service_manager` 클래스의 객체 관리자가 되고, 모든 `find`/`add` 요청에서 호출자 도메인과 대상 서비스 타입을 커널 AVC에 던진다. `Source-confirmed` 즉 "누가 무엇에 도달 가능한가"가 런타임 우연이 아니라 **컴파일된 정책에 완전히 명시**돼 있다 — 그래서 정책 이진만 있으면 표면을 전부 뽑아낼 수 있다.

표면 확장이 생기는 근본 원인은 정책이 조각나 있고 vendor가 자기 조각을 더한다는 데 있다. Treble(Android 8) 이후 정책은 CIL로 쪼개져 `plat_*`(AOSP)과 `vendor_*`(OEM)이 부팅 시 `secilc`로 합쳐진다. `Source-confirmed` AOSP 기준선은 `neverallow`로 조여 있지만, OEM이 새 서비스 타입을 정의하고 거기에 `untrusted_app find`를 붙이면 AOSP `neverallow`가 그 신규 타입을 알 리 없어 통과한다. 결국 위험은 baseline이 아니라 **vendor delta**에서 나오고, 14장의 baseline/patched 이미지 비교가 이 delta를 잡는 도구가 된다.

## 버전 차이와 한계

- **Treble 분할**: Android 8 이전은 단일(monolithic) 정책, 이후는 plat+vendor CIL 조합. 감사할 땐 두 조각을 모두 봐야 vendor 확장이 보인다. `Source-confirmed`
- **버전별 앱 도메인**: `untrusted_app_25`·`untrusted_app_27`·`untrusted_app_30`… targetSdkVersion에 따라 도메인이 갈린다. 하나만 보고 "앱 표면"을 단정하면 다른 targetSdk 앱의 표면을 놓친다. `Source-confirmed`
- **에뮬레이터 한계**: AVD의 AOSP 정책엔 OEM `vendor_service_contexts`가 없다. 즉 에뮬레이터로는 **baseline만** 감사되고, 실제 vendor 표면은 실기기 이미지(14장)에서 봐야 한다. `Inferred`
- **정적 과대추정**: 정적 `allow`는 도달 가능성일 뿐이다. 서비스가 미등록이거나, 서비스 코드가 UID/권한을 추가로 검사하면 실제 호출은 막힌다. 반대로 avc denied 로그가 뜬다고 그게 익스플로잇이 막힌 증거는 아니다 — 정상 동작 중에도 무해한 denied는 흔하다. `Inferred`
- **도구 버전**: setools 4.x는 `sesearch --allow`(=`-A`)를, 구버전은 다른 플래그를 쓴다. `sepolicy-analyze`는 AOSP 빌드에서 나오는 host prebuilt이며 서브커맨드(`permissive`·`neverallow`·`typecmp`)는 트리 버전에 따라 다를 수 있어, 정확한 서브커맨드는 원문(system/sepolicy/tools) 재확인 필요.

## 정리

- servicemanager는 `service_manager` 클래스의 객체 관리자다. `service_contexts`(타입 매핑) + `untrusted_app`의 `find` 규칙 = 비특권 앱의 IPC 공격 표면.
- 표면 열거는 `sesearch -A -s untrusted_app -c service_manager -p find` → 대상이 속성이면 `seinfo -a`로 펼쳐 실제 서비스 명단 확정. 이 명단이 퍼징 대상 리스트다.
- 위험은 AOSP baseline이 아니라 vendor delta에서 나온다. `sepolicy-analyze permissive`와 baseline/patched 정책 diff로 조인다.
- allow는 도달성일 뿐 취약점이 아니고, userdebug의 permissive는 user 빌드에서 사라진다 — 재현은 항상 빌드 타입을 명시하고 하라.

**점검 질문** — (1) 앱이 `getService("activity")`를 호출할 때 SELinux는 어떤 (subject, object, class, perm) 조합으로 판정하는가? (2) sesearch 출력에 서비스 이름이 아니라 `app_api_service`가 뜨면 다음에 무엇을 해야 하나? (3) 에뮬레이터 AOSP 정책으로 OEM 서비스 표면을 감사할 수 없는 이유는?

**참고** — [SELinux for Android](https://source.android.com/docs/security/features/selinux) · [Implementing SELinux(service_contexts/CIL)](https://source.android.com/docs/security/features/selinux/concepts) · [AOSP system/sepolicy](https://android.googlesource.com/platform/system/sepolicy/) · [SETools(sesearch/seinfo)](https://github.com/SELinuxProject/setools)

*다음 글: [HAL·vendor boundary](/posts/android-vulnresearch-p4c13/).*
