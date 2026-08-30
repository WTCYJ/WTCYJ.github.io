---
layout: post
title: "Android 앱 보안 분석 9~10주차 - 취약점 10건 수정과 회귀 검증"
date: 2026-08-09 11:00:00 +0900
category: 안드로이드
author: WTCY
tags: [Android, AndroidSecurity, 모바일보안, 취약점수정, 회귀테스트, AndroidKeystore, TLS, NetworkSecurityConfig, exported, ScopedStorage, allowBackup, WebView, 서버측인가, 경로이탈, adb, 학습기록]
excerpt: "앞선 구간에서 재현해둔 약점 10건을 실제로 닫고, 7~8주차에 만든 검증 스크립트를 손대지 않고 다시 돌려 전부 '안전'으로 판정받았습니다. 수정이 공격 경로까지 닫아 시험을 정상 흐름으로 다시 설계한 일, `am start` 출력을 끝까지 읽어 판정을 정밀화한 일, 결과표를 서술에서 판정으로 끌어올린 일 — 측정의 엄밀함을 세 번 끌어올린 기록입니다."
---

> **진행 구간**: 24주 로드맵의 9~10주차 (취약점 유형별 점검·수정)
> **대상**: `kr.wtcy.memovault` · AVD `sec-api33` (Android 13, API 33)
> **구성**: 앱 → `https://10.0.2.2:8443` (자체 서명 인증서, network security config 로 고정)
> **이전 글**: [7~8주차](/posts/android-security-study-week7-8/) · [5~6주차](/posts/android-security-study-week5-6/) · [24주 로드맵](/posts/android-security-study-roadmap/) · **다음** [11~12주차 미니 모의진단](/posts/android-security-study-week11-12/)

---

이 글은 24주 Android 보안 학습 로드맵의 9~10주차, 취약점 수정 구간 기록입니다.

7~8주차까지는 "이 앱에 이런 문제가 있다"를 증명하는 작업이었습니다. 이번 구간에서는 그 10건을 실제로 닫고, 앞서 만들어둔 검증 스크립트를 손대지 않고 다시 돌려 열 항목 전부가 '안전'으로 판정되는 것을 확인했습니다. 이 글에서는 각 유형을 어떤 방식으로 닫았는지, 회귀 검증에서 무엇이 확인됐는지, 그리고 수정이 공격 경로 자체를 닫아버린 덕에 시험을 정상 사용자 흐름으로 다시 설계하게 된 과정을 순서대로 살펴보겠습니다. 마지막에는 판정을 세 번 더 엄밀하게 다듬은 정정 기록도 함께 남깁니다.

---

## 배경 개념 - 회귀 검증과 이번에 쓰는 방어 장치

먼저 이번 구간에서 반복해 등장하는 개념을 짧게 정리하겠습니다.

**회귀 검증(regression test)**이란 고친 뒤에 같은 시험을 다시 돌려, 문제가 정말 사라졌고 다른 것이 깨지지도 않았는지 확인하는 절차를 말합니다. 취약점 대응에서 특히 중요한 이유는, 수정이 "화면에서 안 보이게" 만드는 것에 그치는 경우가 흔하기 때문입니다. 시험이 남아 있으면 그 차이가 드러납니다.

**[Android Keystore](https://developer.android.com/privacy-and-security/keystore)**는 암호 키를 앱 프로세스 밖의 보안 영역(가능하면 TEE나 StrongBox 같은 하드웨어 지원 영역)에서 만들고 보관하는 시스템입니다. 앱은 키를 꺼내 쓰는 것이 아니라 "이 데이터를 이 키로 암호화해 달라"고 요청만 하고, 키 자체는 앱 메모리는 물론 커널 메모리에도 평문으로 올라오지 않습니다. 그래서 저장 파일을 통째로 빼내도, 심지어 백업을 복원해도 그 기기의 키 없이는 복호할 수 없습니다. 이 글의 W2가 노리는 지점이 바로 이것입니다.

**[network security config](https://developer.android.com/privacy-and-security/security-config)**는 앱이 어떤 통신을 허용할지 XML로 선언하는 Android 기능입니다. 평문 HTTP 차단(`cleartextTrafficPermitted="false"`), 도메인별 정책, 그리고 어떤 인증서를 신뢰할지(trust anchor)를 코드 수정 없이 지정할 수 있습니다. Android 9(API 28)부터 평문 통신은 기본으로 막히지만, 여기에 더해 신뢰 앵커에서 사용자 CA 스토어를 빼두면 기기에 임의 인증서를 심어도 그 앱의 트래픽은 가로채지지 않습니다. 7~8주차에 프록시로 전부 들여다봤던 경로가 이 선언 하나로 닫힙니다.

**앱 샌드박스(UID 격리)**는 위 두 방어가 딛고 서는 바탕입니다. Android는 앱마다 고유한 Linux UID를 주고, 그 앱의 [내부 저장소](https://developer.android.com/training/data-storage/app-specific) `/data/data/<패키지>`를 앱 UID 소유의 `0700`으로 둡니다. 다른 앱은 UID가 달라 애초에 그 디렉터리에 들어올 수 없습니다. 이번 구간과 별개로 돌려둔 다른 API 33 에뮬레이터에서 같은 구조를 교차 확인했는데, 한 앱은 `userId=10176`을 받고 `/data/data/<패키지>`가 `drwx------ u0_a176 u0_a176`(곧 `0700`, 소유자=앱 UID)로 잡혀 있었습니다. W2에서 토큰을 내부 저장소에 Keystore 암호문으로 쓰고, W9에서 첨부를 내부 저장소에 `0600`으로 쓰는 것이 안전한 이유가 이 격리입니다. 반대로 7~8주차에 문제가 됐던 외부 저장소(`/storage/emulated/0/Android/data/...`)는 이 UID 격리 밖이라 adb로도 읽혔습니다.

**서버 측 인가**는 "이 사용자가 이 데이터를 볼 자격이 있는가"를 서버가 판단하는 것을 말합니다. 클라이언트가 판단하면 클라이언트를 조작하는 순간 무너지므로, 인가는 원칙적으로 서버의 일입니다.

---

## 1. 실습 환경과 준비 - 회귀 도구를 먼저 확보한 상태

이번 구간의 출발점은 유리했습니다. 7~8주차에 `verify-dynamic.sh`를 만들어두었고, 그 스크립트가 약점 10건을 기기에서 재현하는 절차를 이미 담고 있었기 때문입니다. 고친 뒤 같은 것을 돌리면 그대로 회귀 테스트가 됩니다.

검증 절차를 먼저 만들어두면 수정이 훨씬 편해집니다. 무엇을 고쳐야 하는지가 목록으로 남아 있고, 다 고쳤는지도 명령 한 줄로 확인됩니다.

서버 쪽에는 TLS를 붙여야 했습니다. 실습 환경이라 정식 인증서를 받을 수 없으므로 자체 서명 인증서를 만들었습니다.

```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/server.key -out certs/server.crt -days 825 \
  -subj "/CN=MemoVault Dev CA/O=android-security-study" \
  -addext "subjectAltName=IP:10.0.2.2,IP:127.0.0.1,DNS:localhost"
```

에뮬레이터가 호스트를 보는 주소가 `10.0.2.2`이므로 SAN에 그 IP를 넣었습니다. 이 인증서는 앱의 `res/raw`에 넣고 `10.0.2.2` 도메인에 한해서만 신뢰하도록 지정했습니다.

---

## 2. 수정 내역 - 유형별로 닫은 방식

10건을 유형별로 정리하면 다음과 같습니다.

| ID | 약점 | 수정 방식 |
| --- | --- | --- |
| W1 | exported 컴포넌트 | 메모 목록·상세를 `exported="false"` 로. 공지 딥링크만 노출 유지 |
| W2 | 토큰 평문 저장 | Android Keystore AES/GCM 으로 암호화 후 저장 |
| W3 | 로그 자격증명 유출 | 비밀번호·토큰·API 키 로그 제거, 결과 코드만 기록 |
| W4 | 평문 통신 | HTTPS + network security config, cleartext 전면 차단 |
| W5 | allowBackup | `allowBackup="false"` + 백업·기기이전 규칙에서 세션 제외 |
| W6 | WebView 브릿지·URL 검증 | `addJavascriptInterface` 제거, 파일 접근 차단, URL 허용 목록 |
| W7 | 하드코딩 키·관리자 폴백 | 앱에서 삭제. 자격증명은 서버가 가진다 |
| W8 | 클라이언트 측 인가 | 인가를 서버로 이관, `owner_override` extra 제거 |
| W9 | 서버 응답 파일명 신뢰 | 파일명 정규화 후 내부 저장소에 저장, 정규 경로 재확인 |
| W10 | 인텐트 경유 임의 파일 읽기 | `attach_path` extra 제거. 첨부 대상은 앱이 정한다 |

### exported 를 닫는다는 것

W1은 메모 목록·상세 액티비티를 `android:exported="false"`로 바꾸는 일입니다. [API 31(Android 12)부터는](https://developer.android.com/about/versions/12/behavior-changes-12#exported) 인텐트 필터를 가진 컴포넌트에 `exported`를 명시하지 않으면 설치 자체가 거부되므로, 이 값은 이제 "빠뜨리면 안 되는" 항목이 됐습니다. 공지 딥링크 하나만 의도적으로 `true`로 남기고 나머지는 닫았습니다.

컴포넌트 노출과 짝을 이루는 것이 패키지 가시성입니다. Android 11(API 30)부터는 앱이 다른 앱 목록을 함부로 조회하지 못하는데, 다른 API 33 에뮬레이터에서 이를 확인해보면 비특권 앱 기준 `system apps queryable: false`, `forceQueryable=false`로 잡혀 있었습니다. 공격자 앱이 대상 컴포넌트를 겨냥하기 전에 그 존재를 아는 것부터 기본적으로 제한된다는 뜻입니다. W1은 이 기본 격리 위에 "내 화면은 나만 연다"를 한 겹 더 얹는 셈입니다.

### 의존성을 늘리지 않은 두 선택

**W2**의 교과서적 해법은 `EncryptedSharedPreferences`(androidx.security)입니다. 그런데 이 앱은 처음부터 의존성을 최소로 유지해왔습니다. 5~6주차에 jadx로 열었을 때 제 코드가 2,972개 소스 중 12개뿐이라 바로 찾을 수 있었던 것이 그 덕이었습니다. 그래서 라이브러리 대신 플랫폼 API인 Keystore와 `javax.crypto`를 직접 썼습니다. `AES/GCM/NoPadding`으로 암호화하고, 저장할 때마다 새로 생성한 12바이트 IV를 암호문 앞에 붙여 함께 보관합니다. GCM 인증 태그가 무결성까지 같이 검증하므로 별도 MAC이 필요 없습니다. 전체 40줄 남짓이고, 핵심 키가 Keystore 밖으로 나오지 않는다는 점은 라이브러리를 쓸 때와 동일합니다.

**W4**는 자체 서명 인증서를 `10.0.2.2` 전용 trust anchor로 등록하는 방식을 택했습니다. 특정 인증서만 신뢰 앵커로 지정하는 것은 사실상 인증서 고정(pinning)과 같은 효과를 내고, 앞서 설명한 대로 사용자 CA 스토어는 신뢰하지 않으므로 7~8주차에 프록시로 전부 들여다봤던 그 경로가 이제 막힙니다. 실습이라 자체 서명 인증서를 썼을 뿐, 실제 앱이라면 정식 CA 인증서 위에 도메인 한정 신뢰 앵커를 얹는 형태가 됩니다.

### 앱만 고쳐서는 닫히지 않는 것

W8은 앱 수정만으로 끝나지 않습니다. 서버가 여전히 전체 메모를 내려주면, 앱이 화면에 그리지 않을 뿐 데이터는 이미 기기에 도착해 있습니다. 그래서 서버도 함께 고쳤습니다.

- `GET /memos` — 토큰 주인의 메모만 반환
- `POST /memos` — 요청 본문의 `owner` 를 무시하고 토큰 주인으로 강제

---

## 3. 관측 결과

### 3-1. 회귀 검증 결과표

`bash tools/verify-dynamic.sh` 한 번의 출력입니다. W9만 자동 결과 옆에 3-3의 수동 입증을 함께 적었습니다.

| ID | 항목 | 판정 | 근거 |
|---|---|---|---|
| W1 | exported 컴포넌트 | 안전 | 메모 화면 2개 모두 `Permission Denial … not exported` |
| W2 | 토큰 평문 저장 | 안전 | Keystore AES/GCM 암호문 |
| W3 | 로그 자격증명 유출 | 안전 | 비밀번호·토큰·API 키 0행 |
| W4 | 평문 통신 | 안전 | 프록시가 자격증명 미포착, cleartext 허용 0건 |
| W5 | allowBackup | 안전 | 런타임 플래그에서 `ALLOW_BACKUP` 사라짐 |
| W6 | WebView 브릿지·URL 검증 | 안전 | 주입 URL 미로드, 브릿지 열거 불가 |
| W7 | 하드코딩 관리자 폴백 | 안전 | 세션 미생성 (서버가 거부) |
| W8 | 클라이언트 측 인가 우회 | 안전 | 목록에 남의 메모 없음, override 무효 |
| W9 | 서버 응답 파일명 신뢰 | 확인불가(자동) → 안전 | 자동 경로가 W1로 닫힘, 3-3에서 UI로 입증 |
| W10 | 인텐트 경유 임의 파일 읽기 | 안전 | 액티비티 비공개라 외부 호출 자체가 거부 |

### 3-2. 서버 측 인가 수정이 화면에 나타난 모습

가장 눈에 띄는 변화는 로그인 직후 화면이었습니다. 아래는 수정 전과 후를 나란히 놓은 것입니다.

![수정 전 메모 목록입니다. 상단에 "사용자: alice"로 로그인돼 있는데 목록에는 alice의 메모(장보기, 스터디 메모)뿐 아니라 bob의 메모(회의 요약, 비밀 메모)까지 4건이 함께 나열돼 있습니다](/assets/img/android-security-study/02-memo-list.png)

![수정 후 메모 목록입니다. 상태줄에 "메모 2건 동기화됨"이라고 표시되고 목록에는 alice 소유의 장보기, 스터디 메모 두 건만 남아 있습니다](/assets/img/android-security-study/10-authz-fixed.png)

상태 줄이 **"메모 2건 동기화됨"** 으로 바뀌었습니다. 이전에는 4건(alice 2 + bob 2)이 내려왔습니다. 서버가 토큰 주인의 것만 보내기 시작했으므로, 앱을 어떻게 조작하든 남의 메모는 애초에 기기에 도착하지 않습니다.

### 3-3. 적대적 서버로 입증한 파일명 처리

W9만 자동 스크립트가 '확인불가'를 냈습니다. 뒤(4장)에서 다루듯 W1 수정이 이 항목의 자동 시험 경로까지 함께 닫았기 때문인데, 미검증으로 둘 수는 없어 서버를 적대적 모드로 띄우고 정상 사용자 흐름 그대로 앱 UI에서 직접 입증했습니다. 서버가 경로 이탈 문자열을 파일명으로 돌려주도록 만든, 가장 불리한 조건을 걸었습니다.

```bash
python tools/testapi/server.py --port 8443 --tls \
  --hostile-rawname --hostile-value "../../../../hostile-marker.txt"
```

아래는 그때의 logcat과 저장소 상태입니다.

```
D MemoVault: uploadAttachment name=memo-1786240441551.txt size=29
D MemoVault: POST /upload -> 201
I MemoVault: attachment cached (29 bytes)

$ run-as kr.wtcy.memovault ls -laR /data/data/kr.wtcy.memovault/files/attachments
-rw------- 1 u0_a175 u0_a175 29 memo-1786240441551.txt

$ run-as kr.wtcy.memovault find /data/data/kr.wtcy.memovault -name "*hostile*"
(결과 없음)
```

서버가 무엇을 보내든 앱은 자기가 만든 이름으로 내부 저장소에만 씁니다. 화면에서도 로컬 사본 이름이 정규화된 것을 확인할 수 있습니다.

![메모 상세 화면입니다. "업로드 완료: 0002-memo-1786240441551.txt (42 bytes)"와 "로컬 사본: memo-1786240441551.txt"가 표시돼 있습니다](/assets/img/android-security-study/11-attach-sanitized.png)

외부 저장소 경로는 아예 사라졌습니다.

```
$ ls /storage/emulated/0/Android/data/kr.wtcy.memovault/files
No such file or directory
```

7~8주차에는 이 경로에 `0660`(`ext_data_rw` 그룹) 권한으로 파일이 남아 adb로 읽혔습니다. 지금은 내부 저장소에 `0600`으로 들어갑니다.

---

## 4. 결과 해석 - 수정이 공격 경로를 닫아 시험을 다시 설계하게 했다

W9의 자동 판정이 '확인불가'로 나온 것은 판정 로직이 틀려서가 아니라, 오히려 수정이 잘 됐다는 신호였습니다. **W1을 고치면서 W9의 자동 시험 경로가 함께 닫힌** 것이기 때문입니다.

기존 W9 절차는 `adb shell am start -n …/.MemoDetailActivity`로 상세 화면을 띄우고 첨부 버튼을 누르는 방식이었습니다. 그런데 그 액티비티가 비공개가 되면서 외부 호출에 `Permission Denial`이 납니다. 공격 경로로 화면을 억지로 띄우던 길이 막힌 것 자체가 W1 수정의 성공이고, 그 길에 얹혀 있던 W9 자동 시험은 실행될 자리를 잃습니다.

여기서 원칙 하나를 얻었습니다. 회귀 테스트를 **공격 경로에 의존해 만들면**, 공격 경로를 막는 것이 수정의 목적이므로 수정이 성공할수록 그 시험은 실행되지 않습니다. 그래서 정상 사용자 흐름(로그인 → 목록에서 항목 선택 → 첨부)으로 시험을 다시 짜 W9를 '안전'으로 입증했습니다. 시험은 공격이 아니라 기능에 붙어 있어야 오래간다는 것을, 수정이 성공한 바로 그 자리에서 배웠습니다.

한 가지 더 정리해두면, 이번 수정의 성격이 유형마다 달랐습니다. W3·W7처럼 **덜어내서** 닫은 것이 있고, W2·W4처럼 **장치를 더해서** 닫은 것이 있으며, W8처럼 **판단 주체를 옮겨서** 닫은 것이 있습니다. 마지막 유형이 제일 손이 많이 갔지만 가장 확실했습니다. 클라이언트에서 아무리 조작해도 데이터가 오지 않기 때문입니다.

---

## 5. 판정을 세 번 더 엄밀하게 - 정정 기록

아래 세 가지는 판정을 잘못 낼 뻔했다가 스스로 잡아낸 지점입니다. 셋 다 "고쳤는데 안 고쳐진 것처럼 보이거나, 안 고쳤는데 고쳐진 것처럼 보이는" 함정이었고, 근거를 끝까지 확인해 바로잡았습니다. 결과표를 믿을 수 있는 이유가 이 정정들에 있습니다.

### `am start` 출력을 끝까지 읽어 판정을 바로잡다

`exported="false"`로 바꾸고 확인했는데 액티비티가 그냥 떴습니다. 매니페스트를 다시 봐도 `exported=false`가 맞았습니다.

원인은 출력을 앞부분만 본 것이었습니다.

```
$ adb shell am start -n kr.wtcy.memovault/.MemoDetailActivity | head -2
Starting: Intent { cmp=kr.wtcy.memovault/.MemoDetailActivity }
```

`am start`는 **실패해도 첫 줄에 `Starting: Intent`를 찍습니다.** 전체를 보면 그 뒤에 예외가 있습니다.

```
java.lang.SecurityException: Permission Denial: starting Intent { ... }
  from null (pid=10072, uid=2000) not exported from uid 10175
```

7~8주차의 거짓 양성과 같은 종류입니다. 그때는 "거부 문구가 없으면 성공"이었고 이번에는 "출력 앞부분에 에러가 없으면 성공"이었습니다. 판정 근거를 부분 출력에 두면 반복해서 틀립니다.

덤으로 알게 된 것도 있습니다. `adb shell`은 uid 2000(`shell`)이고 이 계정은 `START_ANY_ACTIVITY` 권한을 가집니다. 위 사례는 거부됐으니 다행이지만, 일반적으로 `adb shell am start`가 성공한다고 해서 "제3자 앱도 호출할 수 있다"가 곧바로 성립하지는 않습니다. 엄밀히 하려면 권한 없는 앱 UID에서 호출해야 합니다.

### 결과표를 서술에서 판정으로 끌어올리다

수정 후 스크립트를 돌리니 이런 행이 나왔습니다.

```
| W2 | ... | 토큰 `DC6sqG6/VUFnzy7uAmC5yQv/...` 평문 저장 |
```

값은 암호문인데 설명은 "평문 저장"입니다. 관측은 정확한데 **라벨이 7~8주차의 결론에 묶여 있었습니다.**

그래서 각 항목이 서술이 아니라 판정(취약 / 안전 / 확인불가)을 내도록 다시 썼습니다. 판정 기준도 전부 긍정 증거로 통일했습니다. W1은 `Permission Denial` 문자열이 있는지, W6은 주입한 외부 URL이 화면에 나타나는지, W8은 목록 단계 유출과 상세 단계 유출을 따로 봅니다. 마지막에 `취약 N · 안전 N · 확인불가 N` 요약을 붙여, 다음 구간에서 무언가 되돌아가면 숫자로 바로 보이게 했습니다.

### 파이썬 문자열에 갇힌 JavaScript 를 raw 로 되살리다

공지 페이지 스크립트를 고쳤는데 JS가 통째로 실행되지 않았습니다. 화면에 "렌더링 시각: -"만 남았습니다.

HTML을 담은 파이썬 문자열이 일반 문자열이라, JS 안의 개행·널 이스케이프를 파이썬이 먼저 실제 문자로 바꿔버린 것이었습니다. 널 문자가 섞인 스크립트는 파싱 자체가 되지 않습니다. raw 문자열로 바꿔 해결했습니다. 증상이 "아무것도 동작하지 않음"이라 원인을 찾는 데 시간이 걸렸습니다.

---

## 6. 도달 상태와 다음 구간

| 커리큘럼 | 목표 | 상태 |
| --- | --- | --- |
| 1~2주 | Android 구조 | 완료 |
| 3~4주 | 테스트 앱 작성 | 완료 |
| 5~6주 | 정적 분석 | 완료 |
| 7~8주 | 동적 분석 | 완료 |
| 9~10주 | 취약점 유형별 점검·수정 | 완료 |
| 11~12주 | 미니 모의진단 | 다음 |

로드맵에 적어둔 "다음 단계 판단 기준" 중 이번에 하나가 더 채워졌습니다.

- ☑ APK 하나를 정적 분석하고 표를 만들 수 있다
- ☑ 정상 동작의 기준선을 만든 뒤 최소 검증으로 가설을 확인할 수 있다
- ☑ **문제를 수정하고 같은 테스트로 재발하지 않음을 보일 수 있다**
- ☑ 스냅샷·빌드 지문·로그로 실험을 재현할 수 있다
- ☐ 공개 CVE 하나를 설명할 수 있다 → 18주차 이후

이번 구간에서 확정한 것은 동적 회귀입니다. 열 항목을 고친 뒤 같은 시험으로 전부 '안전'을 받아냈고, W9는 정상 흐름으로 재설계해 입증까지 마쳤습니다. 여기서 다음 범위가 자연히 정해집니다. 정적 분석을 다시 돌려 5~6주차 표와 나란히 비교하는 일은 11~12주차 진단에서 이어가고, 자체 서명 인증서를 신뢰 앵커로 넣은 것은 실습 환경 한정이므로 실제 배포에서는 정식 CA 인증서 위에서 개발용 설정이 릴리스에 섞이지 않게 분리하는 것이 다음 과제입니다. Keystore 키에 생체·화면잠금 같은 [사용자 인증 조건](https://developer.android.com/identity/sign-in/biometric-auth)을 한 겹 더 거는 것도 그다음 단계로 남겨둡니다.

다음 구간은 미니 모의진단입니다. 이번까지는 답을 아는 제 앱이 대상이었지만, 다음은 훈련 앱 하나를 [OWASP MASTG](https://mas.owasp.org/) 기준으로 처음부터 진단합니다.

---

## 마치며

이번 구간에서 가장 크게 남은 것은 **검증 절차를 먼저 만들어둔 것의 값어치**였습니다. 7~8주차에 스크립트를 짜둔 덕분에 이번에는 고치고 한 줄 실행하는 것으로 끝났습니다. 그것이 없었다면 10건을 하나씩 손으로 다시 확인했을 것이고, 아마 몇 개는 "고쳤으니 됐겠지" 하고 넘어갔을 것입니다.

동시에 그 스크립트의 성격도 같은 구간에서 또렷해졌습니다. 공격 경로에 의존한 시험은 수정이 성공하는 순간 실행되지 않고, 결과표의 문구는 만든 시점의 결론을 그대로 안고 갑니다. 그래서 고칠 때마다 도구도 같이 손봤고, 그 손질 덕에 열 항목을 전부 '안전'으로 매듭지을 수 있었습니다. 수정과 검증 도구는 한 몸으로 자라야 한다는 것이 이번 구간의 결론입니다.

---

## 참고 자료

- Android Developers, [Android Keystore 시스템](https://developer.android.com/privacy-and-security/keystore) — 키를 앱 밖 보안 영역에 두는 방식 (W2)
- Android Developers, [네트워크 보안 구성](https://developer.android.com/privacy-and-security/security-config) — 평문 차단·신뢰 앵커 지정 (W4)
- Android Developers, [Android 12 동작 변경: 컴포넌트의 안전한 내보내기](https://developer.android.com/about/versions/12/behavior-changes-12#exported) — API 31+ `exported` 명시 의무화 (W1)
- Android Developers, [앱별(내부) 저장소](https://developer.android.com/training/data-storage/app-specific) — UID 소유 `0700` 격리 (W2·W9)
- Android Developers, [앱 데이터 자동 백업](https://developer.android.com/identity/data/autobackup) — `allowBackup`·백업 제외 규칙 (W5)
- OWASP, [Mobile Application Security Testing Guide (MASTG)](https://mas.owasp.org/) — 11~12주차 진단 기준
