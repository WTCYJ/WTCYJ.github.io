---
layout: post
title: "OWASP MASTG 안드로이드 크랙미 L1~L4"
date: 2026-10-04 13:00:00 +0900
category: 안드로이드
author: SeiKa
tags: [안드로이드, 리버싱, UnCrackable, r2pay, OWASP, MASTG, Frida, JNI, 루트탐지, 안티디버깅, 화이트박스암호, DCA, 실기기, 학습기록]
excerpt: "OWASP MASTG의 안드로이드 UnCrackable 네 문제를 순서대로 풀었습니다. L1~L3은 루트·디버거 탐지를 걷어내고 Java와 JNI 속에 숨은 secret을 꺼내는 전형적인 흐름이라 에뮬레이터로 끝났는데, L4(r2pay)는 달랐습니다. 네이티브 RASP가 Frida의 gum을 감지하면 그 자리에서 프로세스를 죽여서, 에뮬레이터에서는 계측이든 Gadget이든 전부 막혔습니다. 그래서 제 갤럭시 S24 FE를 USB로 꽂았습니다. 실기기에서는 안티에뮬레이터·안티프리다가 자연히 통과해 네이티브 검증이 멀쩡히 돌았고, 4자리 PIN을 브루트포스해 초록 r2coin을 띄웠습니다. 두 번째 플래그인 화이트박스 AES 마스터키까지 정리합니다."
---

안드로이드 리버싱을 배우다 보면 OWASP UnCrackable 시리즈는 한 번쯤 꼭 거치게 됩니다. MASTG 본문에서 "이 보호는 이렇게 뚫는다"를 설명할 때 단골로 끌려 나오는 예제거든요. 저도 네 개를 처음부터 끝까지 한 번 풀어 보고 싶어서, 이번에 L1부터 순서대로 잡았습니다.

앞의 세 개는 결이 비슷합니다. 앱이 루트나 디버거를 탐지해서 막으면 그걸 걷어내고, Java나 네이티브에 숨겨 둔 정답 문자열을 찾아 입력창에 넣는 거죠. 그러면 "Success"가 뜹니다. 난이도는 Java 디컴파일에서 JNI로, 다시 무결성 우회로 한 칸씩 올라갈 뿐이고요. 그런데 마지막 r2pay는 아예 다른 물건이었습니다. 결국 저는 책상 서랍에서 USB 케이블을 꺼내 제 폰을 꽂아야 했는데, 그 이야기까지 적겠습니다.

## L1

L1은 가장 교과서적인 Java 문제입니다. `MainActivity.onCreate`가 먼저 루트와 디버거를 확인하고, 하나라도 걸리면 "Root detected!" 다이얼로그를 띄운 뒤 `System.exit(0)`으로 앱을 닫아 버립니다. 루트 판정은 세 가지인데, 핵심은 `System.getenv("PATH")`의 디렉터리를 하나씩 돌며 `su` 바이너리가 있는지 보는 겁니다.

입력 검증은 `sg.vantagepoint.uncrackable1.a.a()`가 맡습니다. 하드코딩된 키로 AES 복호화를 한 다음, 그 결과를 입력과 `equals`로 그냥 비교하더군요.

![jadx로 디컴파일해 VS Code로 연 sg.vantagepoint.uncrackable1.a.a() — 하드코딩된 AES 키 8d12…와 Base64 암호문으로 복호한 결과를 입력과 equals로 비교하는 코드](/assets/img/mastg-crackmes/l1-analysis.png)

```java
bArrA = sg.vantagepoint.a.a.a(b("8d127684cbc37c17616d806cf50473cc"),
          Base64.decode("5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc=", 0));
return str.equals(new String(bArrA));
```

키도 암호문도 전부 코드 안에 있으니, 복호화만 그대로 재현하면 secret이 튀어나옵니다.

```python
from Crypto.Cipher import AES
import base64
key = bytes.fromhex("8d127684cbc37c17616d806cf50473cc")
ct  = base64.b64decode("5UJiFctbmgbDoLXmpL12mkno8HT4Lv8dlat8FxR2GOc=")
pt  = AES.new(key, AES.MODE_ECB).decrypt(ct)
print(pt[:-pt[-1]].decode())   # -> I want to believe
```

secret은 `I want to believe`입니다. 루트 탐지는 Frida로 세 판정 함수를 전부 `false`로 덮어 다이얼로그를 막고, 입력창에 그대로 넣었습니다. 제 폰에서 뜬 성공 화면이 아래입니다.

![L1 - 실기기(갤럭시)에서 Uncrackable1 입력창에 "I want to believe"를 넣자 "Success! This is the correct secret." 다이얼로그가 뜬 화면](/assets/img/mastg-crackmes/l1-phone-success.png)

## L2

L2는 Java에서 바로 비교하지 않습니다. `System.loadLibrary("foo")`로 `libfoo.so`를 올린 뒤 입력을 `CodeCheck.bar(byte[])`라는 네이티브 함수로 넘기죠. L1처럼 디컴파일만으로 끝나지 않고, JNI 경계를 넘어 `.so` 안까지 따라 들어가야 합니다.

`bar`를 디스어셈블해 보면 입력 길이가 23인지 확인한 다음 `strncmp`로 비교합니다. 그런데 비교 대상 문자열이 한 덩어리로 저장돼 있지 않더군요. 일부는 `.rodata`에 있고, 나머지는 스택에서 즉시값으로 조립됩니다. `strings`로는 `Thanks for all t`까지밖에 안 보이는 이유가 이겁니다. 나머지를 이어 붙이면 secret은 `Thanks for all the fish`입니다.

![libfoo.so에 strings를 걸면 "Thanks for all t"까지만 나오는 화면 — 나머지는 네이티브 스택에서 즉시값으로 조립되고, 이어 붙인 secret이 Thanks for all the fish](/assets/img/mastg-crackmes/l2-analysis.png)

메모 하나. 같은 APK를 제 갤럭시에 올렸더니 L2 액티비티가 뜨자마자 조용히 닫혔습니다. `am start`는 `ok`를 돌려주는데 WindowManager 로그를 보면 곧바로 `isExiting`으로 빠지더군요. 그래서 L2는 x86_64 에뮬레이터에서 성공을 확인했습니다.

![L2 - 에뮬레이터에서 "Thanks for all the fish"를 넣자 "Success! This is the correct secret." 다이얼로그가 뜬 화면](/assets/img/mastg-crackmes/l2-success.png)

## L3

L3는 L2의 JNI 구조 위에 변조(탬퍼) 방어가 한 겹 더 얹힙니다. `verifyLibs()`가 `classes.dex`와 ABI별 `libfoo.so`의 CRC를 미리 저장된 값과 맞춰 보고, 하나라도 어긋나면 `tampered = 31337`로 깃발을 세웁니다. 이후 루트·디버거·탬퍼 중 하나라도 걸리면 종료 흐름으로 들어가죠. secret 검증은 L2처럼 네이티브 `bar`가 맡는데, 이번엔 정답 마스크를 평문으로 들고 있지 않습니다. LCG로 런타임에 24바이트를 만든 다음 `input[i] == key[i] ^ mask[i]`로 비교하는데, 키는 `pizzapizza…`를 반복한 거였습니다.

![jadx로 디컴파일해 VS Code로 연 MainActivity — xorkey가 pizzapizza… 반복으로 박혀 있고, verifyLibs()가 ABI별 libfoo.so와 classes.dex의 CRC를 저장값과 맞춰 보다 어긋나면 tampered=31337로 세우는 코드](/assets/img/mastg-crackmes/l3-analysis.png)

APK를 건드리지 않고 그대로 돌리면 CRC가 맞으니 탬퍼 깃발은 서지 않습니다. 복원한 secret은 `making owasp great again`이고, 에뮬레이터에서 성공을 확인했습니다.

![L3 - 에뮬레이터에서 "making owasp great again"을 넣자 "Success! This is the correct secret." 다이얼로그가 뜬 화면](/assets/img/mastg-crackmes/l3-success.png)

## L4

r2pay는 앞의 셋과 종류가 다릅니다. "secret 문자열 맞히기"가 아니라 결제 앱을 흉내 낸 고난도 크랙미고, 목표도 둘입니다. 하나는 초록색 r2coin을 만들어 내는 4자리 master PIN과 salt, 다른 하나는 네이티브 화이트박스 암호 안에 묻힌 r2pay 마스터키입니다.

입력은 PIN(4자리)과 amount를 각각 `%08d`로 패딩해 이어 붙인 16바이트이고, 이걸 네이티브 함수로 넘깁니다.

```java
public native byte[] gXftm3iswpkVgBNDUp(byte[] bArr, byte b);
```

반환값 첫 바이트가 `0x51`이면 실패(빨간 토큰), 그 외면 성공이라 UI에 `r2c-…` 토큰이 초록색으로 뜹니다. PIN은 10000가지뿐이니, UI를 만 번 두드리는 대신 이 검증 함수에 입력만 바꿔 가며 반복 호출해 첫 바이트가 `0x51`이 아닌 걸 찾으면 됩니다.

문제는 그 "반복 호출"을 어디서 돌리느냐였습니다. r2pay에는 보호가 겹겹이 쌓여 있거든요.

- RootBeer 계열 루트 탐지. 걸리면 `onCreate`에서 `1337 / 0`으로 일부러 ArithmeticException 크래시를 냅니다.
- `libtool-checker.so` 기반 네이티브 루트 체크.
- 네이티브 안티디버깅, 안티-DBI, 코드 무결성 검사.
- OLLVM 난독화(제어흐름 평탄화 + 문자열 암호화).
- AES를 화이트박스 형태로 심어 둔 암호 구현.

에뮬레이터에서는 이 벽을 못 넘었습니다. 루트 탐지야 Frida로 끄면 되는데, 정작 Frida를 붙이는 순간 네이티브 RASP가 프로세스 안의 frida-gum을 알아채고 `libnative-lib.so`의 어느 한 지점에서 일부러 쓰레기 포인터를 역참조해 SIGSEGV로 죽였습니다. 매번 같은 오프셋, 같은 주소였으니 우연한 크래시가 아니라 작정하고 심어 둔 방어였죠. 그래서 gum이 아예 안 보이게 하려고 Frida Gadget을 APK에 심어 봤습니다. smali로 `MainActivity`가 네이티브 라이브러리를 올리기 직전에 gadget을 끼워 넣고, apktool로 다시 빌드해 재서명까지 한 뒤 gadget이 포트를 여는 것까지 확인했는데, 결과는 똑같았습니다. gadget도 결국 frida-gum이라, RASP는 그게 떠 있다는 것만으로 프로세스를 끝내 버렸습니다. r2pay는 "프리다가 붙어 있으면 무조건 죽인다"를 전제로 만든 앱이었습니다.

여기서 생각을 바꿨습니다. RASP가 싫어하는 건 에뮬레이터와 frida-gum입니다. 그럼 둘 다 없는 환경 — 그냥 진짜 폰 — 이면 어떨까. 제 갤럭시 S24 FE(SM-S721N, 언루팅)를 USB로 꽂고 디버깅을 허용했습니다. 실기기에서는 안티에뮬레이터 검사가 그냥 통과하고, 루트가 없으니 루트 탐지도 안 걸리고, Frida를 안 쓰니 안티프리다도 걸릴 게 없습니다. 네이티브 검증 함수가 그제서야 처음으로 깨끗하게 돌았습니다.

Frida를 못 쓰니 반복 호출은 앱 안에서 직접 돌리기로 했습니다. smali를 패치해 `onCreate` 끝에 PIN을 0부터 올리며 `gXftm3iswpkVgBNDUp`를 부르고, 첫 바이트가 `0x51`이 아닌 값을 로그로 남기는 루프를 넣었습니다(Play Protect가 재서명 APK 설치를 막길래 `settings put global verifier_verify_adb_installs 0`로 풀었습니다). 실기기에서 한 호출당 160밀리초 남짓, 크래시 없이 돌았고, 그렇게 걸린 master PIN이 `5971`입니다.

![MainActivity.smali에 직접 끼워 넣은 브루트 루프 — onCreate 끝에서 PIN을 올려 가며 %08d%08d로 16바이트 입력을 만들고 gXftm3iswpkVgBNDUp에 넘겨, 반환 첫 바이트가 0x51이 아닌 값을 찾는 smali 코드](/assets/img/mastg-crackmes/l4-analysis.png)

PIN 검증은 PBKDF2-HMAC-SHA256으로 정리됩니다. salt와 기대 해시를 뽑아 맞춰 보면 그대로 들어맞습니다.

```python
import hashlib
salt = bytes.fromhex("4ad891934b99c3a0445f66ad76eaa106")
expected = bytes.fromhex("b70e29f661f78dacf541787df59ba225e144628488b46b4c6047d4ced38a3af7")
print(hashlib.pbkdf2_hmac("sha256", b"5971", salt, 32, 32) == expected)   # True
```

그래서 첫 번째 플래그는 이렇습니다.

```text
r2con{5971:4ad891934b99c3a0445f66ad76eaa106}
```

마지막으로 패치 없는 원본 앱을 폰에 깔고, 직접 PIN `5971`과 amount `0`을 넣어 봤습니다. 초록색 r2coin 토큰이 떴습니다.

![L4 - 실기기(갤럭시) Radare2 Pay 화면. Enter Pin 5971, Enter Amount 0을 넣고 GENERATE R2COIN을 누르자 초록색으로 r2c-39e770cdadaa52e9dec803106b22c7cb 토큰이 생성된 화면](/assets/img/mastg-crackmes/l4-phone-success.png)

## 화이트박스 마스터키

PIN을 찾았다고 끝이 아닙니다. r2pay에는 하나가 더 남아 있죠. 토큰을 만드는 네이티브 코드 안에 화이트박스 AES로 숨겨진 마스터키입니다. 이건 문자열 검색이나 평범한 디컴파일로는 안 나옵니다. 키가 룩업 테이블과 난독화된 연산 흐름에 녹아 있어서, 코드 어디에도 키가 통째로 존재하지 않거든요.

화이트박스 구현을 깨는 공개된 방법은 DCA(Differential Computation Analysis)입니다. 전력분석의 소프트웨어 판이라고 보면 되는데, 흐름은 이렇습니다. 네이티브 함수 안에서 화이트박스 AES가 도는 구간을 찾고, 입력을 여러 개 바꿔 가며 `.data` 테이블을 읽는 메모리 접근 trace를 모으고, AES 마지막 라운드 중간값에 대한 누설 모델을 세운 뒤, 상관분석으로 last round key를 복원하고, 마지막으로 AES 키 스케줄을 역산해 원래 키를 얻습니다. r2pay는 이미 잘 정리된 공개 분석(RedFenec, Romain Thomas)이 있어서 그 절차에 제 분석을 맞춰 봤습니다.

복원된 last round key는 `768d19e17f62a01eb0cdd39a28e1798f`이고, 키 스케줄을 되돌린 마스터키는 `723270347931734e3077536563757233`, ASCII로 읽으면 `r2p4y1sN0wSecur3`입니다. 그래서 두 번째 플래그는 이렇습니다.

```text
r2con{r2p4y1sN0wSecur3}
```

## 마치며

네 문제를 한 줄로 줄이면, L1~L3은 "보호를 걷어내고 숨은 문자열을 꺼내는" 연습이고, L4는 "계측 자체를 거부하는 앱 앞에서, 계측을 포기하고 환경을 바꾸는" 연습이었습니다.

| Level | 핵심 보호 | 정답 | 어디서 |
| --- | --- | --- | --- |
| L1 | 루트·디버거 탐지 + Java AES | `I want to believe` | 실기기 |
| L2 | JNI libfoo.so 검증 | `Thanks for all the fish` | 에뮬레이터 |
| L3 | + CRC 무결성 검사 | `making owasp great again` | 에뮬레이터 |
| L4 | RootBeer·네이티브 RASP·화이트박스 | `r2con{5971:4ad891934b99c3a0445f66ad76eaa106}` / `r2con{r2p4y1sN0wSecur3}` | 실기기 |

제일 많이 배운 건 L4입니다. Frida가 막히면 Gadget, Gadget이 막히면 네이티브 후킹 — 저는 계속 같은 방향으로 더 세게만 밀었는데, 정작 답은 "이 앱은 에뮬레이터와 frida-gum을 죽이도록 만들어졌으니, 둘 다 없는 진짜 폰에서 그냥 돌리자"였습니다. 보호를 우회하는 가장 깔끔한 방법이, 그 보호가 노리는 조건을 애초에 안 만드는 것일 때가 있더군요. 서랍에서 케이블을 꺼낸 게 이번 세트에서 제일 결정적인 한 수였습니다.

참고 자료:

- OWASP Android Crackmes: [https://mas.owasp.org/crackmes/Android/](https://mas.owasp.org/crackmes/Android/)
- RedFenec, R2Pay Under the Microscope - Breaking White-Box Crypto: [https://redfenec.com/r2pay-under-the-microscope-breaking-white-box-crypto/](https://redfenec.com/r2pay-under-the-microscope-breaking-white-box-crypto/)
- Romain Thomas, r2pay: [https://github.com/romainthomas/r2pay](https://github.com/romainthomas/r2pay)
