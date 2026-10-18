---
layout: post
title: "apktool과 smali — 다시 조립해도 명령은 그대로"
date: 2026-10-20 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, apktool, smali, baksmali, Dalvik, DEX, jadx, ART, VerifyError]
excerpt: "apktool 3.0.2로 손대지 않고 다시 묶은 dex는 2364바이트에서 2220바이트로 바뀌었지만 다시 푼 smali는 같았다. move-result 뒤의 const/4 한 줄은 화면을 UNLOCKED로 바꿨고 자리나 레지스터를 잘못 고른 패치는 smali 조립, apktool 빌드, d8 재변환, 서명을 모두 통과한 뒤(오류를 낸 것은 jadx 하나였다) 기기에서 ART 검증기의 VerifyError로 막혔다."
---

jadx가 다시 짜 준 Java로 앱을 읽다 보면([지난 글](/posts/android-lab-p1c04-jadx-static-analysis/)) 고쳐 보고 싶은 줄이 나온다. 라이선스 검사의 분기 하나, 루트 탐지 결과를 받는 변수 하나 같은 것들이다. 이런 수정은 보통 apktool로 푼 smali에서 한다. jadx의 Java는 다시 빌드할 수 없지만 smali는 바이트코드를 옮긴 것이라 재조립해도 안전하다는 설명이 늘 따라붙는다. 직접 풀고 묶고 고쳐 보니 재조립해도 명령이 바뀌지 않는다는 쪽은 맞았다. 그런데 넣을 자리나 레지스터를 잘못 고른 패치도 smali·apktool·d8이 모두 받아 줬고 jadx의 Java도 이 앱에서는 javac를 통과했다. jadx 쪽 함정은 다른 데 있었다. jadx는 구조를 세우지 못한 메서드를 예외만 던지는 코드로 바꿔 두고 javac는 그 코드도 오류 없이 컴파일한다.

도구는 apktool 3.0.2(안에 smali·baksmali 3.0.9-dev가 들어 있다), jadx 1.5.5, build-tools 36.0.0의 zipalign·apksigner 0.9·dexdump다. Java로 된 도구는 모두 Android Studio에 딸린 JBR 21.0.10에서 돌렸고 셸은 Windows의 Git Bash다. apktool은 3.0.0에서 aapt1을 `--use-aapt1` 옵션과 함께 뺐으니([Apktool 3.0.0](https://apktool.org/blog/apktool-3.0.0/)) 리소스는 늘 aapt2로 빌드되고 아래 출력에 찍히는 `Building resources with aapt2...`가 그 단계다. 고친 APK는 Android 13(API 33, 2024-03 보안 패치) x86_64 에뮬레이터에 깔아 확인했다.

## 늘 false를 돌려주는 라이선스 게이트

실험 대상은 직접 만든 `io.seika.smali`다. Gradle 없이 javac, d8, aapt, apksigner로 묶은 Java 앱이고 minSdk 26, targetSdk 33에 SDK의 debug 키로 서명했다. 게이트 클래스는 이것이 전부다.

```java
package io.seika.smali;

/** A client-side "license" gate: the kind of check smali patching flips. */
public class Gate {
    private final String key;

    public Gate(String key) {
        this.key = key;
    }

    public boolean isEnabled() {
        return key != null && key.startsWith("PRO-") && key.hashCode() == 0x5eca1ab;
    }

    public String label(long uses, String who) {
        return who + " / uses=" + uses;
    }
}
```

`isEnabled()`는 키가 `PRO-`로 시작하고 해시값까지 맞아야 true다. 앱에 박힌 키는 `FREE-0000`이라 언제나 false가 나온다. `label(long, String)`은 기능과 상관없는 메서드로, long 인자가 레지스터를 어떻게 차지하는지 보려고 넣었다. 액티비티는 게이트 결과로 화면 문구를 고르고 같은 내용을 `SmaliLab` 태그로 로그에 남긴다. 뒤에서 줄 번호를 맞춰 볼 일이 있어 파일 전체를 싣는다.

```java
package io.seika.smali;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Gate gate = new Gate("FREE-0000");
        String state;
        if (gate.isEnabled()) {
            state = "PRO features: UNLOCKED";
        } else {
            state = "PRO features: locked";
        }
        Log.i("SmaliLab", "isEnabled -> " + state + " (" + gate.label(3L, "seika") + ")");
        TextView tv = new TextView(this);
        tv.setTextSize(26);
        tv.setPadding(48, 160, 48, 48);
        tv.setText("Smali Lab\n\n" + state);
        setContentView(tv);
    }
}
```

아래 `adb` 명령의 `$S`에는 에뮬레이터 시리얼을 넣어 두었다. 원본 APK를 깔아 한 번 띄우면 게이트는 닫혀 있다.

```bash
export S=emulator-5602
adb -s $S install smalilab.apk
adb -s $S logcat -c
adb -s $S shell am start -W -n io.seika.smali/.MainActivity
sleep 2
adb -s $S logcat -d -s SmaliLab:I
```

```text
--------- beginning of main
10-15 01:51:58.672  3408  3408 I SmaliLab: isEnabled -> PRO features: locked (seika / uses=3)
```

![원본 smalilab.apk를 띄운 에뮬레이터 화면. 앱 바에 Smali Lab, 본문에 Smali Lab과 PRO features: locked가 큰 글씨로 보인다](/assets/img/android-mastery/p1c05/06-screen-before.png)

## apktool d가 펼쳐 놓는 것

```bash
apktool d -p fw smalilab.apk -o smalilab
find smalilab -type f | sort
unzip -p smalilab.apk AndroidManifest.xml | xxd | head -3
cat smalilab/AndroidManifest.xml
cat smalilab/apktool.yml
```

`-p fw`(`--frame-path`)는 apktool이 프레임워크 리소스 파일 `1.apk`를 꺼내 두고 읽는 폴더를 정한다. 지정하지 않으면 사용자 프로필 아래 기본 폴더를 쓰고 그 전체 경로를 로그에 찍는다. 실습 폴더 안에서 모든 것이 끝나게 하려고 여기 나오는 apktool 명령에는 전부 `-p fw`를 붙였는데 평소에는 빼도 된다.

![apktool d -p fw smalilab.apk -o smalilab 출력에 Using Apktool 3.0.2, Baksmaling classes.dex, fw 폴더의 1.apk에서 리소스 테이블을 읽는 줄이 있고, find 결과로 AndroidManifest.xml, apktool.yml, original/AndroidManifest.xml, original/META-INF/ANDROIDD.RSA·ANDROIDD.SF·MANIFEST.MF, res/values/public.xml·strings.xml, smali/io/seika/smali/Gate.smali·MainActivity.smali가 보이며, 원본 매니페스트 xxd 첫 줄이 0300 0800 3c07 0000, 텍스트로 풀린 매니페스트에는 uses-sdk가 없고, apktool.yml에 usesFramework ids 1, minSdkVersion 26, targetSdkVersion 33이 찍힌 터미널](/assets/img/android-mastery/p1c05/01-apktool-decode.png)

`smali/` 아래에는 클래스마다 `.smali` 파일이 하나씩 생겼고 `res/values/`에는 문자열 값을 담은 `strings.xml`과 리소스 ID를 고정하는 `public.xml`이 나왔다. `original/`에는 원본 APK의 바이너리 `AndroidManifest.xml`과 `META-INF` 서명 파일이 그대로 복사돼 있다. 이 폴더는 평소 빌드에는 쓰이지 않고 `--copy-original`을 줄 때만 APK에 다시 들어간다.

APK 안의 매니페스트는 텍스트가 아니다. `xxd` 첫 바이트 `03 00 08 00`은 little-endian으로 청크 타입 0x0003, 헤더 크기 8이다. 0x0003은 [`ResourceTypes.h`의 `RES_XML_TYPE`](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/libs/androidfw/include/androidfw/ResourceTypes.h#236)이다. 이어지는 `3c 07 00 00`은 청크 전체 크기 0x73c, 1852바이트다. apktool은 이 바이너리 XML을 리소스 테이블과 맞춰 텍스트로 풀어 트리 맨 위에 둔다.

풀린 매니페스트에는 `<uses-sdk>`가 없다. minSdk 26과 targetSdk 33은 `apktool.yml`의 `sdkInfo`로 옮겨졌고 빌드할 때 apktool이 이 파일을 다시 읽는다. smali 어셈블러에 넘길 API 레벨도 여기 적힌 minSdk에서 고른다([ApkBuilder.java L71-72](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/ApkBuilder.java#L71)). `usesFramework`의 `ids: 1`을 보면 이 앱이 참조하는 프레임워크 패키지는 패키지 ID 1인 `android` 하나뿐이다. 그래서 `fw` 폴더의 `1.apk` 하나로 디코드가 끝났다. 제조사 프레임워크를 참조하는 앱이라면 그 APK를 `apktool if`로 먼저 등록해야 한다([CLI parameters](https://apktool.org/docs/cli-parameters/)).

`apktool.yml`이 없으면 빌드는 시작도 못 한다. `smali/`만 옮겨 담은 폴더를 빌드하면 이렇게 끝난다.

```text
$ mkdir noyml && cp -r smalilab/smali noyml/
$ apktool b -p fw noyml -o x.apk 2>&1 | head -4
Exception in thread "main" brut.androlib.exceptions.AndrolibException: java.nio.file.NoSuchFileException: noyml\apktool.yml
	at brut.androlib.meta.ApkInfo.load(SourceFile:77)
	at brut.apktool.Main.main(SourceFile:70)
Caused by: java.nio.file.NoSuchFileException: noyml\apktool.yml
```

`AndrolibException`은 apktool 라이브러리(`brut.androlib`)가 던지는 예외이고 여기서는 `apktool.yml`을 읽는 `ApkInfo.load`에서 났다.

## jadx에서 찾은 분기를 smali에서 다시 찾기

위치는 jadx로 찾고 같은 자리를 smali에서 연다.

```bash
jadx -q -d jx smalilab.apk
grep -n 'isEnabled' jx/sources/io/seika/smali/MainActivity.java
grep -n . smalilab/smali/io/seika/smali/MainActivity.smali | sed -n '/onCreate/,/if-eqz/p'
grep -n . smalilab/smali/io/seika/smali/Gate.smali | sed -n '/label(J/,/end method/p'
```

`grep -n .`은 빈 줄을 건너뛰지만 줄 번호는 파일 그대로 붙인다. 뒤에서 `sed`로 몇 번째 줄 다음에 끼워 넣을지 정할 때 이 번호를 쓴다.

![jadx가 만든 MainActivity.java 15행 if (gate.isEnabled()) 와 20행 Log.i 호출, 같은 자리의 smali onCreate에서 19행 .locals 5, 22행 invoke-super {p0, p1}, 25행 new-instance p1, Lio/seika/smali/Gate;, 32행 invoke-virtual {p1} Gate;->isEnabled()Z, 34행 move-result v0, 36행 if-eqz v0, :cond_0, 그리고 Gate.smali 65행 label(JLjava/lang/String;)의 66행 .locals 1과 83행 invoke-virtual {p3, p1, p2} StringBuilder;->append(J)가 보이는 터미널](/assets/img/android-mastery/p1c05/02-jadx-vs-smali-registers.png)

jadx는 분기를 자기가 새로 쓴 `MainActivity.java`의 15행에 두었다. smali에서는 `.line 14` 아래 32~36행이 같은 자리다. `.line`은 dex 디버그 정보에 남은 원래 소스의 줄 번호라서 직접 쓴 `MainActivity.java`의 14행 `if (gate.isEnabled())`와 맞고, jadx의 15행은 jadx가 새로 쓴 파일 기준이라 한 줄 어긋난다.

smali에서 먼저 볼 곳은 레지스터 이름이다. `.locals 5`로 지역 레지스터 v0~v4를 잡는다. Dalvik에서는 메서드 인자 N개가 프레임의 마지막 N개 레지스터에 차례로 들어간다. wide 인자는 두 칸을 쓰고 인스턴스 메서드는 `this`를 첫 인자로 받는다([Dalvik bytecode format, General design](https://source.android.com/docs/core/runtime/dalvik-bytecode#design)). `onCreate(Bundle)`의 인자는 `this`와 `Bundle`이니 레지스터는 모두 7개가 되고 p0은 v5, p1은 v6이다. 고친 APK를 dexdump로 열었을 때도 이 메서드는 `registers : 7`, `ins : 2`였고 `invoke-super {p0, p1}`은 `invoke-super {v5, v6}`으로 찍혔다(아래 `const/4`를 넣은 뒤의 `dexdump -d` 출력에서 확인된다).

![source.android.com Dalvik bytecode format 문서의 General design 절. 마지막 하위 항목에 The N arguments to a method land in the last N registers of the method's invocation frame, in order. Wide arguments consume two registers. Instance methods are passed a this reference as their first argument.가 보인다](/assets/img/android-mastery/p1c05/11-src-dalvik-registers.png)

게이트 호출은 `invoke-virtual {p1}`이다. `this`를 떠올리고 `{p0}`을 쓰기 쉬운 자리인데 d8은 `super.onCreate()` 뒤로 다시 쓰이지 않는 Bundle 인자의 레지스터 p1에 새 `Gate` 객체를 담았다(`new-instance p1, Lio/seika/smali/Gate;`). p로 시작하는 이름이 붙어 있어도 보통 레지스터와 다를 게 없어서 덮어쓸 수 있다. 뒤에서 만든 badreg 패치가 바로 이 p1을 정수로 덮어쓴다.

`Gate.label(JLjava/lang/String;)`은 `.locals 1`이라 지역 레지스터가 v0 하나다. p0이 `this`, long 인자가 p1과 p2 두 칸, String이 p3이다. 83행 `invoke-virtual {p3, p1, p2}, ...->append(J)...`에서 long이 p1·p2 짝으로 넘어가고 그 앞뒤로 `move-result-object p3`, `move-result-object p1`처럼 다 쓴 인자 레지스터에 중간 결과를 받는 모습도 보인다.

인자 레지스터가 `pN`으로 나오는 것, `.locals`가 붙는 것, 라벨이 `:cond_0`처럼 순번으로 매겨지는 것은 apktool이 baksmali를 부를 때 켜는 옵션 때문이다. [SmaliDecoder.java L126-130](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/smali/SmaliDecoder.java#L126)에서 `parameterRegisters`, `localsDirective`, `sequentialLabels`를 true로 둔다.

## 손대지 않고 다시 묶은 dex

고치기 전에, 아무것도 바꾸지 않은 채 다시 묶으면 무엇이 달라지는지부터 봤다. 손댄 게 없어도 dex 해시가 바뀐다면 해시만 보고는 패치가 들어갔는지 알 수 없다.

```bash
apktool b -p fw smalilab -o roundtrip.apk
unzip -l roundtrip.apk
unzip -p smalilab.apk classes.dex > orig.dex
unzip -p roundtrip.apk classes.dex > rt.dex
sha256sum orig.dex rt.dex
python dexcmp.py orig.dex rt.dex
apktool d -q -p fw roundtrip.apk -o roundtrip
diff -r smalilab/smali roundtrip/smali && echo "smali: no difference"
```

`dexcmp.py`는 두 dex를 포맷 수준에서 견주려고 표준 라이브러리만으로 짠 스크립트다. 헤더에서 string_ids와 map_list 위치를 읽고 문자열 개수와 정렬 여부, 한쪽에만 있는 문자열, data 영역 항목의 배치 순서를 찍는다.

```python
"""Compare two dex files at the format level (stdlib only).
usage: python dexcmp.py a.dex b.dex
Prints: version, size, string count and whether each string table is sorted,
strings present in only one file, and the order of the data-section items (map_list)."""
import struct, sys

NAMES = {0x1001: 'type_list', 0x1003: 'annotation_set', 0x2000: 'class_data', 0x2001: 'code',
         0x2002: 'string_data', 0x2003: 'debug_info', 0x2004: 'annotation', 0x2006: 'annotations_dir'}


def load(path):
    b = open(path, 'rb').read()
    n, off = struct.unpack_from('<II', b, 0x38)
    strs = []
    for i in range(n):
        p = struct.unpack_from('<I', b, off + 4 * i)[0]
        while b[p] & 0x80:  # skip the uleb128 utf16 length
            p += 1
        p += 1
        strs.append(b[p:b.index(b'\0', p)].decode('utf-8', 'replace'))  # MUTF-8, ASCII here
    moff = struct.unpack_from('<I', b, 0x34)[0]
    items = [struct.unpack_from('<HHII', b, moff + 4 + 12 * i) for i in range(struct.unpack_from('<I', b, moff)[0])]
    data = [NAMES[t] for t, _, _, _ in sorted(items, key=lambda x: x[3]) if t in NAMES]
    return b[4:7].decode(), len(b), strs, data


a, b = sys.argv[1], sys.argv[2]
A, B = load(a), load(b)
for name, (ver, size, strs, data) in ((a, A), (b, B)):
    print(f'{name}: dex {ver}, {size} bytes, {len(strs)} strings, sorted={strs == sorted(strs)}')
for name, mine, other in ((a, A[2], B[2]), (b, B[2], A[2])):
    for s in sorted(set(mine) - set(other)):
        print(f'  only in {name}: {s}')
for name, (_, _, _, data) in ((a, A), (b, B)):
    print(f'{name} data order: ' + ' > '.join(data))
```

![apktool b -p fw smalilab -o roundtrip.apk 뒤 unzip -l에 AndroidManifest.xml 1952, classes.dex 2220, resources.arsc 572만 있고 META-INF가 없으며, orig.dex와 rt.dex의 sha256이 e5a51785로 시작하는 값과 63be3183으로 시작하는 값으로 다르고, dexcmp.py가 orig.dex dex 038 2364 bytes 54 strings sorted=True, rt.dex dex 038 2220 bytes 53 strings sorted=True, orig.dex에만 있는 ~~D8 마커 문자열, code > debug_info > type_list > string_data > class_data 와 string_data > type_list > annotation_set > debug_info > code > class_data 라는 서로 다른 data 순서를 찍고, 다시 디코드한 smali의 diff -r 결과가 smali: no difference 인 터미널](/assets/img/android-mastery/p1c05/03-roundtrip-dex-vs-smali.png)

바이트는 달랐다. 크기가 2364에서 2220으로 줄었고 해시도 당연히 다르다. 그런데 다시 풀어 낸 smali 트리는 `.line` 지시어까지 들어 있는데도 `diff -r`로 비교해 차이가 없었다.

`dexcmp.py`에 정렬 여부를 찍게 한 것은 문자열 순서부터 의심했기 때문이다. dex 포맷은 string_ids를 UTF-16 코드 포인트 순으로 중복 없이 두라고 정해 두었고([Dalvik executable format, File layout](https://source.android.com/docs/core/runtime/dex-format#file-layout)) 두 파일 모두 `sorted=True`였다.

원본에만 있는 문자열 하나는 d8이 남기는 `~~D8{...}` 마커다. 컴파일러 종류와 버전(`"version":"8.10.9-dev"`)을 적어 두는 문자열인데 코드 어디에서도 참조하지 않으니 baksmali가 smali로 옮길 거리가 없고 다시 조립한 dex에서는 빠진다. 문자열이 54개에서 53개가 됐다. data 영역의 배치 순서도 다르다. d8은 code를 앞에 두었고 smali의 dex 작성기(dexlib2 `DexWriter`)는 string_data를 앞에 두면서 빈 annotation_set 하나를 더 썼다. 이렇게 앞쪽이 달라지면 뒤에 오는 오프셋이 모두 움직이고 헤더의 checksum(adler32)과 signature(SHA-1)도 새로 계산된다. `dexdump -f`로 본 헤더가 그 결과다.

| 헤더 필드 | orig.dex | rt.dex |
|---|---|---|
| checksum | a5416503 | 75c63272 |
| file_size | 2364 | 2220 |
| string_ids_size | 54 | 53 |
| type_ids_off | 328 | 324 |
| data_size | 1544 | 1404 |

string_id 항목 하나가 4바이트이니 문자열이 하나 빠지자 type_ids가 정확히 4바이트 앞당겨졌다. dex 버전은 둘 다 038이다. apktool이 `apktool.yml`의 minSdk 26을 smali API 레벨로 넘기는데 이 값을 29 이하로 묶어 dex 버전이 039를 넘지 않게 한다([SmaliBuilder.java L51-52](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/smali/SmaliBuilder.java#L51)).

코드를 고칠 생각이 없고 리소스나 매니페스트만 바꾸려는 경우라면 `-s`(`--no-src`)로 디코드하면 된다. 이때는 dex를 smali로 풀지 않고 디코드한 폴더에 `classes.dex`로 들고 있다가 빌드할 때 그 파일을 넣는다. 다시 묶은 dex의 해시가 원본과 같았다.

```text
$ apktool d -q -s -p fw smalilab.apk -o nosrc
$ ls nosrc
AndroidManifest.xml
apktool.yml
classes.dex
original
res
$ apktool b -p fw nosrc -o nosrc.apk
I: Using Apktool 3.0.2 on smalilab.apk with 8 threads
I: Copying raw classes.dex...
I: Building resources with aapt2...
I: Building apk file...
I: Built apk into: nosrc.apk
$ unzip -p nosrc.apk classes.dex | sha256sum; unzip -p smalilab.apk classes.dex | sha256sum
e5a5178537dd9c887efb4355fb18eed5e89f4e35afc41debdb63d5702488c98c *-
e5a5178537dd9c887efb4355fb18eed5e89f4e35afc41debdb63d5702488c98c *-
```

## move-result 다음 줄에 넣은 const/4

`invoke-virtual`과 `move-result`를 지우고 `const/4 v0, 0x1`로 바꾸면 `isEnabled()` 호출 자체가 사라진다. 실제 앱의 검사 메서드라면 로그를 남기거나 카운터를 올리거나 서버에 무언가를 보낼 수 있고 그것도 같이 없어진다. 그래서 34행 `move-result v0` 바로 다음에 한 줄만 끼워 넣었다. 호출은 원래대로 일어나고 분기 직전에 결과만 1로 덮인다. `const/4 vA, #+B`는 4비트 부호 있는 리터럴을 32비트로 늘려 넣는 명령이라 0x1이 들어간다([Dalvik bytecode format](https://source.android.com/docs/core/runtime/dalvik-bytecode)).

```bash
cp -r smalilab/smali smali.orig
sed -i '34a\    const/4 v0, 0x1' smalilab/smali/io/seika/smali/MainActivity.smali
diff -u --strip-trailing-cr smali.orig/io/seika/smali/MainActivity.smali smalilab/smali/io/seika/smali/MainActivity.smali
apktool b -p fw smalilab
apksigner verify smalilab/dist/smalilab.apk
jadx -q -d jx-patched smalilab/dist/smalilab.apk
sed -n 14,17p jx-patched/sources/io/seika/smali/MainActivity.java
```

![cp -r smalilab/smali smali.orig 뒤 34행 다음에 const/4 v0, 0x1을 넣는 sed -i, diff -u --strip-trailing-cr의 @@ -32,6 +32,7 @@ 블록에서 invoke-virtual {p1} isEnabled()Z와 move-result v0 아래 추가된 const/4 v0, 0x1, 그 아래 if-eqz v0, :cond_0, apktool b -p fw smalilab이 Built apk into: smalilab\dist\smalilab.apk를 찍고, apksigner verify가 DOES NOT VERIFY와 ERROR: Missing META-INF/MANIFEST.MF를 내며, 고친 APK를 jadx로 푼 14~17행이 Gate gate = new Gate(FREE-0000); gate.isEnabled(); if (1 != 0) { str = PRO features: UNLOCKED; 인 터미널](/assets/img/android-mastery/p1c05/04-patch-diff-unsigned.png)

처음에는 `--strip-trailing-cr` 없이 `diff -u`를 돌렸다. 한 줄을 넣었는데 diff가 280줄이 나왔다. Windows에서 apktool 3.0.2가 쓴 smali는 CRLF 줄 끝이고 Git Bash의 `sed -i`는 고친 파일을 LF로 저장한다. 그래서 모든 줄이 바뀐 것으로 보였다.

```text
$ file smali.orig/io/seika/smali/MainActivity.smali smalilab/smali/io/seika/smali/MainActivity.smali
smali.orig/io/seika/smali/MainActivity.smali:     ASCII text, with CRLF line terminators
smalilab/smali/io/seika/smali/MainActivity.smali: disassembled Android DEX Java class (smali/baksmali), ASCII text
$ diff -u smali.orig/io/seika/smali/MainActivity.smali smalilab/smali/io/seika/smali/MainActivity.smali | wc -l
280
$ diff -u --strip-trailing-cr smali.orig/io/seika/smali/MainActivity.smali smalilab/smali/io/seika/smali/MainActivity.smali | wc -l
10
```

줄 끝을 무시하자 바뀐 것은 끼워 넣은 한 줄뿐이었다. 변경 기록을 남기거나 리뷰에 넘길 diff라면 이 옵션을 붙이는 편이 낫다.

같은 캡처 중간에서 `apksigner verify`는 dist APK에 `DOES NOT VERIFY`와 `ERROR: Missing META-INF/MANIFEST.MF`를 냈다. 서명 파일이 하나도 없다. 맨 아래처럼 고친 APK를 jadx로 다시 풀면 `gate.isEnabled();` 호출은 남고 조건이 `if (1 != 0)`으로 바뀌어 있다. 패치가 의도한 자리에 들어갔는지 빠르게 보는 데 쓸 만하다. dex 수준에서도 확인했다. dist APK의 dex를 꺼내 `dexdump -d`로 본 `onCreate` 앞부분이다(바이트 열은 줄였다).

```text
      registers     : 7
      ins           : 2
      outs          : 5
|0000: invoke-super {v5, v6}, Landroid/app/Activity;.onCreate:(Landroid/os/Bundle;)V // method@0001
|0003: new-instance v6, Lio/seika/smali/Gate; // type@0009
|0005: const-string v0, "FREE-0000" // string@0005
|0007: invoke-direct {v6, v0}, Lio/seika/smali/Gate;.<init>:(Ljava/lang/String;)V // method@0007
|000a: invoke-virtual {v6}, Lio/seika/smali/Gate;.isEnabled:()Z // method@0008
|000d: move-result v0
|000e: const/4 v0, #int 1 // #1
|000f: if-eqz v0, 0014 // +0005
```

apktool은 smali가 바뀌었는지를 파일 수정 시각으로 판단한다. `smali/` 아래에서 가장 최근에 바뀐 파일의 시각이 `build/apk/classes.dex`보다 늦을 때만 다시 조립한다([ApkBuilder.java L182-185](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/ApkBuilder.java#L182), [L438-440](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/ApkBuilder.java#L438)). 원본 APK를 `again`이라는 폴더에 한 번 더 풀어 연달아 두 번 빌드했더니 두 번째에는 smali를 다시 조립하지 않고 이전 빌드의 `build/apk/classes.dex`를 썼다. 처음에는 이미 빌드한 `smalilab` 트리를 `cp -r`로 복사해서 해 봤는데 `build/` 폴더까지 따라가는 데다 복사 순서에 따라 시각이 엇갈려 첫 빌드부터 `smali has not changed`가 나온 적도 있었다. 고친 내용이 빌드에 안 들어간 것 같으면 `-f`로 강제한다.

```text
$ apktool d -q -p fw smalilab.apk -o again
$ apktool b -p fw again
I: Using Apktool 3.0.2 on smalilab.apk with 8 threads
I: Smaling smali folder into classes.dex...
I: Building resources with aapt2...
I: Building apk file...
I: Built apk into: again\dist\smalilab.apk
$ apktool b -p fw again
I: Using Apktool 3.0.2 on smalilab.apk with 8 threads
I: smali has not changed.
I: Building resources with aapt2...
I: Building apk file...
I: Built apk into: again\dist\smalilab.apk
$ apktool b -f -p fw again
I: Using Apktool 3.0.2 on smalilab.apk with 8 threads
I: Smaling smali folder into classes.dex...
I: Building resources with aapt2...
I: Building apk file...
I: Built apk into: again\dist\smalilab.apk
```

## apktool b는 서명도 zipalign도 하지 않는다

`apktool b`는 출력 경로를 따로 주지 않으면 `dist/<원래 이름>.apk`에 쓴다([ApkBuilder.java L82](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/ApkBuilder.java#L82)). 서명은 하지 않는다. apktool [FAQ](https://apktool.org/docs/faq/)도 "Apktool builds unsigned APKs."라고 적어 둔다.

정렬도 되어 있지 않다. apktool은 결과물을 `java.util.zip.ZipOutputStream`으로 묶고 zipalign에 해당하는 단계가 없다([ApkBuilder.java L413](https://github.com/iBotPeaches/Apktool/blob/v3.0.2/brut.apktool/apktool-lib/src/main/java/brut/androlib/ApkBuilder.java#L413)). 손대지 않은 `roundtrip.apk`만 검사하면 정렬된 것처럼 보인다. 한 줄 고친 dist APK에 같은 검사를 하면 떨어진다. 두 APK를 검사한 다음 흔히 하는 순서대로 zipalign으로 정렬하고 apksigner로 서명했다. `debug.keystore`는 원본에 쓴 SDK debug 키 저장소를 실습 폴더로 복사해 둔 것이다.

```bash
zipalign -c -v -p 4 roundtrip.apk | tail -n 2
zipalign -c -v -p 4 smalilab/dist/smalilab.apk | tail -n 2
zipalign -p -f 4 smalilab/dist/smalilab.apk aligned.apk
apksigner sign --ks debug.keystore --ks-pass pass:android --out patched.apk aligned.apk
ls patched.apk*
apksigner verify -v patched.apk | head -4
apksigner verify --print-certs smalilab.apk | grep SHA-256
apksigner verify --print-certs patched.apk | grep SHA-256
```

![zipalign -c -v -p 4 roundtrip.apk 결과가 2140 resources.arsc (OK)와 Verification successful, 같은 검사를 smalilab/dist/smalilab.apk에 하면 2147 resources.arsc (BAD - 3)와 Verification FAILED, 이어서 zipalign -p -f 4로 aligned.apk를 만들고 apksigner sign으로 patched.apk를 만든 뒤 ls에 patched.apk와 patched.apk.idsig가 보이고, apksigner verify -v patched.apk가 Verifies, v1 false, v2 true, v3 true를 찍고, 원본 smalilab.apk와 patched.apk의 인증서 SHA-256 digest가 둘 다 766e4a4ce2ecb9bf로 시작하는 같은 값인 터미널](/assets/img/android-mastery/p1c05/14-host-align-sign.png)

갈린 곳은 `resources.arsc` 하나다. 이 파일은 `apktool.yml`의 `doNotCompress`에 올라 있어 압축 없이 저장되고 4바이트 경계에 놓여야 한다. `unzip -v`로 보면 두 APK의 classes.dex는 원래 크기가 2220바이트로 같은데 압축된 크기가 1229와 1236으로 7바이트 차이가 났다.

```text
$ unzip -v roundtrip.apk | grep classes.dex
    2220  Defl:N     1229  45% 2026-10-14 21:20 c22c5be6  classes.dex
$ unzip -v smalilab/dist/smalilab.apk | grep classes.dex
    2220  Defl:N     1236  44% 2026-10-14 21:20 28ee8c6f  classes.dex
```

그 뒤에 오는 `resources.arsc`가 같은 만큼 밀려 2140에서 2147로 옮겨 가면서 경계를 벗어났다. 손대지 않은 쪽이 통과한 것은 압축 결과가 마침 경계에 맞았기 때문이다. targetSdk 30 이상인 앱이 압축됐거나 정렬이 어긋난 `resources.arsc`를 들고 있으면 패키지 파서가 `INSTALL_PARSE_FAILED_RESOURCES_ARSC_COMPRESSED`로 설치를 막는다([ParsingPackageUtils.java L546-555](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java#546)). 이 오류는 여기서는 소스로만 확인했고 기기에서 막히는 모습은 [7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)에서 본다. dist APK는 서명도 없으니 기기에서는 두 문제 가운데 하나가 먼저 걸린다.

정렬하고 서명한 `patched.apk`는 v2와 v3 서명으로 검증됐고 옆에 v4용 `patched.apk.idsig` 파일이 따로 생겼다. 인증서 다이제스트는 원본 `smalilab.apk`와 같다. 캡처의 `v1 false`만 보면 JAR 서명이 없을 것 같지만 `unzip -l`로 열어 보면 apksigner는 `META-INF` 아래 JAR 서명 파일 세 개도 새로 넣었다.

```text
$ unzip -l patched.apk
Archive:  patched.apk
  Length      Date    Time    Name
---------  ---------- -----   ----
     1952  2026-10-14 21:20   AndroidManifest.xml
     2220  2026-10-14 21:20   classes.dex
      572  2026-10-14 21:20   resources.arsc
      412  2026-10-14 21:20   META-INF/ANDROIDD.SF
     1167  2026-10-14 21:20   META-INF/ANDROIDD.RSA
      285  2026-10-14 21:20   META-INF/MANIFEST.MF
---------                     -------
     6608                     6 files
```

apksigner의 `ApkVerifier`는 minSdk가 24 미만이거나 v2 이상 서명이 없을 때만 JAR 서명을 검사한다([ApkVerifier.java L340-344](https://android.googlesource.com/platform/tools/apksig/+/184702d9d18877edf9e5296c4e191cf0aa2b5fbb/src/main/java/com/android/apksig/ApkVerifier.java#340)). minSdk 26에 v2·v3 서명이 있는 이 APK에서 `v1 false`는 v1을 검사하지 않았다는 표시이고 v1이 없다는 말이 아니다. 서명을 마친 파일에 `zipalign -c -p 4`를 다시 돌려도 종료 코드 0이었고 classes.dex의 SHA-256(`b3d2cb02…`)은 dist APK의 것과 같았다. 서명은 `META-INF`의 JAR 서명 파일과 ZIP Central Directory 바로 앞에 놓이는 APK Signing Block([APK Signature Scheme v2](https://source.android.com/docs/security/features/apksigning/v2))을 덧붙이고 정렬을 위해 항목 사이 여백을 다시 맞출 뿐 항목의 내용은 다시 쓰지 않는다.

dist APK는 zipalign 없이 apksigner로 서명만 해도 `resources.arsc`가 2156으로 옮겨져 정렬 검사를 통과했다.

```text
$ apksigner sign --ks debug.keystore --ks-pass pass:android --out signed-only.apk smalilab/dist/smalilab.apk
$ zipalign -c -v -p 4 signed-only.apk | grep -E 'resources|Verification'
    2156 resources.arsc (OK)
Verification successful
```

지금 apksigner는 서명하면서 정렬까지 하는데 build-tools 버전별 차이와 `--alignment-preserved`는 [7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)에서 따로 본다. 아래 기기 실습은 앞에서처럼 zipalign 뒤에 서명한 APK로 했다.

원래 서명을 살릴 수는 없을까 해서 `--copy-original`도 돌려 봤다. 3.0부터는 짧은 `-c`가 빠지고 긴 이름만 남았다([Apktool 3.0.0](https://apktool.org/blog/apktool-3.0.0/)). 옵션을 주면 `original/`에 있던 바이너리 매니페스트와 `META-INF`가 그대로 들어간다.

```text
$ apktool b -p fw --copy-original again -o copyorig.apk
I: Using Apktool 3.0.2 on smalilab.apk with 8 threads
I: smali has not changed.
I: Building resources with aapt2...
I: Copying original files...
I: Building apk file...
I: Built apk into: copyorig.apk
$ unzip -l copyorig.apk | sed -n '4,12p'
     1852  2026-10-15 10:58   AndroidManifest.xml
     2220  2026-10-15 10:58   classes.dex
     1167  2026-10-15 10:58   META-INF/ANDROIDD.RSA
      412  2026-10-15 10:58   META-INF/ANDROIDD.SF
      285  2026-10-15 10:58   META-INF/MANIFEST.MF
      572  2026-10-15 10:58   resources.arsc
---------                     -------
     6508                     6 files
$ apksigner verify copyorig.apk
DOES NOT VERIFY
ERROR: JAR signer ANDROIDD.RSA: JAR signature META-INF/ANDROIDD.SF indicates the APK is signed using APK Signature Scheme v2 but no such signature was found. Signature stripped?
ERROR: JAR signer ANDROIDD.RSA: JAR signature META-INF/ANDROIDD.SF indicates the APK is signed using APK Signature Scheme v3 but no such signature was found. Signature stripped?
```

매니페스트 1852바이트는 앞에서 xxd로 읽은 원본 청크 크기 0x73c와 같다. dex는 smali에서 다시 만든 2220바이트짜리다. 옛 JAR 서명 파일은 따라 들어왔지만 그 `.SF`에는 이 APK가 v2·v3로도 서명됐었다는 표시가 남아 있다. v2·v3 서명 블록은 zip 항목이 아니라서 `original/`로 복사된 적이 없고 apksigner는 서명이 벗겨졌다고 판단한다. FAQ는 아직 `-c`로 적고 있지만 이 옵션이 v1 서명만 다룬다고 밝혀 둔다.

## 서명한 APK는 UNLOCKED, 서명 없는 APK는 null 배열 오류

원본이 깔려 `locked` 로그를 남긴 에뮬레이터에 서명 없는 dist APK와 `patched.apk`를 차례로 덮어 깔고 앱을 다시 띄웠다. 정렬과 서명 두 줄은 앞의 호스트 명령을 한 번 더 돌린 것이다.

```bash
adb -s $S logcat -d -s SmaliLab:I
adb -s $S install -r smalilab/dist/smalilab.apk
zipalign -p -f 4 smalilab/dist/smalilab.apk aligned.apk
apksigner sign --ks debug.keystore --ks-pass pass:android --out patched.apk aligned.apk
adb -s $S install -r patched.apk
adb -s $S logcat -c
adb -s $S shell am start -S -W -n io.seika.smali/.MainActivity | grep -E 'Status|Activity:'
adb -s $S logcat -d -s SmaliLab:I
```

![adb -s $S logcat -d -s SmaliLab:I가 원본의 isEnabled -> PRO features: locked (seika / uses=3)를 찍고, adb install -r smalilab/dist/smalilab.apk가 Failure INSTALL_PARSE_FAILED_NO_CERTIFICATES: Failed to collect certificates from /data/app/vmdl1374789211.tmp/base.apk: Attempt to get length of null array로 실패하며, zipalign -p -f 4와 apksigner sign으로 만든 patched.apk의 install -r는 Success, am start -S -W는 Status: ok와 Activity: io.seika.smali/.MainActivity, 다시 본 logcat은 isEnabled -> PRO features: UNLOCKED (seika / uses=3)인 터미널](/assets/img/android-mastery/p1c05/05-device-install-patched.png)

서명 없는 APK는 `INSTALL_PARSE_FAILED_NO_CERTIFICATES`로 거부됐다. `resources.arsc` 정렬까지 어긋난 APK인데도 먼저 걸린 쪽은 서명이다. 정렬은 우연히 맞고 서명만 없는 `roundtrip.apk`를 깔아도 문구가 같았다. 정렬하고 서명한 `patched.apk`는 `Success`로 깔렸다. 다시 띄운 앱의 로그에는 `PRO features: UNLOCKED (seika / uses=3)`이 찍혔다. 괄호 안의 `seika / uses=3`까지 나온 걸 보면 메서드의 나머지도 원래대로 돈 셈이다. `isEnabled()` 호출이 남아 있다는 것은 앞의 dexdump에서 봤으니 달라진 것은 분기 결과 하나다. 화면 문구도 바뀌었다.

![patched.apk를 깔아 띄운 에뮬레이터 화면. 같은 배치에 Smali Lab과 PRO features: UNLOCKED가 보인다](/assets/img/android-mastery/p1c05/07-screen-after.png)

거부 문구는 예상과 달랐다. targetSdk 33 앱이니 v2 서명이 없다는 `No APK Signature Scheme v2 signature in package`가 나올 줄 알았는데 실제로는 `Attempt to get length of null array`라는 NullPointerException 문구가 붙어 나왔다.

logcat에는 스택이 남지 않아서 Android 13 frameworks/base 소스로 자리를 찾았다. 측정한 에뮬레이터 빌드(TE1A.240213.009)에 대응하는 AOSP 태그가 없어 마지막 Android 13 태그인 android-13.0.0_r84 소스를 봤고, 기기가 낸 메시지 문구는 이 소스와 일치했다. `adb install`이 연 세션은 APK를 받으면 가벼운 파싱으로 인증서부터 모은다([PackageInstallerSession.java L2745-2746](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/services/core/java/com/android/server/pm/PackageInstallerSession.java#2745)). 이 단계는 targetSdk를 아직 몰라 0을 넘기고([ApkLiteParseUtils.java L77](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/parsing/ApkLiteParseUtils.java#77), [L364-373](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/content/pm/parsing/ApkLiteParseUtils.java#364)) targetSdk 30 미만에서 요구하는 최소 스킴은 v1(JAR)이다([ApkSignatureVerifier.java L514-519](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSignatureVerifier.java#514)). 그래서 v4·v3·v2 서명을 차례로 찾다가 못 찾아도 오류 없이 v1 검증까지 내려간다([L117-180](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSignatureVerifier.java#117)).

v1 검증은 `StrictJarFile`을 열면서 `META-INF/MANIFEST.MF`의 내용을 `StrictJarManifest`에 넘기는데 apksigner가 없다고 했던 바로 그 파일이라 null이 넘어간다. 받는 쪽은 첫 줄에서 `buf.length`를 읽다가 예외를 낸다([StrictJarFile.java L113-114](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/jar/StrictJarFile.java#113), [StrictJarManifest.java L195-196](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/jar/StrictJarManifest.java#195)). 이 RuntimeException을 `verifyV1Signature`가 받아 `Failed to collect certificates from ...`과 `INSTALL_PARSE_FAILED_NO_CERTIFICATES`로 바꿔 돌려준다([ApkSignatureVerifier.java L444-446](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r84/core/java/android/util/apk/ApkSignatureVerifier.java#444)). `resources.arsc` 정렬 검사는 그 뒤의 전체 파싱에서 돌기 때문에 dist APK는 거기까지 가지 못했다.

반대로 서명은 있되 v1뿐이면 어떻게 되는지도 봤다. 같은 `aligned.apk`를 apksigner로 v2·v3를 끄고 서명해 `v1only.apk`를 만들었다.

```bash
apksigner sign --ks debug.keystore --ks-pass pass:android --v2-signing-enabled false --v3-signing-enabled false --out v1only.apk aligned.apk
apksigner verify -v v1only.apk | head -4
adb -s $S install -r v1only.apk
```

```text
DOES NOT VERIFY
ERROR: Target SDK version 33 requires a minimum of signature scheme v2; the APK is not signed with this or a later signature scheme
Performing Streamed Install
adb.exe: failed to install v1only.apk: Failure [INSTALL_PARSE_FAILED_NO_CERTIFICATES: Scanning Failed.: No signature found in package of version 2 or newer for package io.seika.smali]
```

![apksigner sign에 --v2-signing-enabled false --v3-signing-enabled false를 주어 aligned.apk에서 v1only.apk를 만들고, apksigner verify -v v1only.apk가 DOES NOT VERIFY와 Target SDK version 33 requires a minimum of signature scheme v2를 찍고, adb install -r v1only.apk가 Failure INSTALL_PARSE_FAILED_NO_CERTIFICATES: Scanning Failed.: No signature found in package of version 2 or newer for package io.seika.smali로 실패한 터미널](/assets/img/android-mastery/p1c05/15-device-v1only.png)

apksigner는 targetSdk 33을 보고 서명 단계에서 이미 v2가 없다고 경고한다. 기기에서는 v1 서명이 온전하니 세션의 가벼운 파싱은 통과했고 패키지를 스캔하는 단계에서 `No signature found in package of version 2 or newer`로 막혔다. 문구는 같은 `INSTALL_PARSE_FAILED_NO_CERTIFICATES`지만 dist APK의 null 배열과는 다른 자리다. 같은 문구를 jarsigner로 서명한 APK와 targetSdk 29 대조군으로 다시 보는 것은 [7장](/posts/android-lab-p1c07-apk-modify-zipalign-resign/)에서 한다. 다른 키로 다시 서명했을 때 무엇이 깨지는지도 7장과 [APK 서명(C08)](/posts/android-concept-atlas-c08-apk-signing/)에서 다룬다.

## jadx의 Java로 다시 빌드하면 생기는 일

이 앱에서는 jadx가 내놓은 Java도 다시 빌드됐다. 앞에서 `jadx -q -d jx`로 푼 소스를 javac에 그대로 넣었다. `AJ`는 javac가 Android 클래스를 찾도록 SDK의 `platforms/android-34/android.jar` 경로를 Windows 형식으로 담은 변수다.

```text
$ export AJ="$(cygpath -w "$ANDROID_HOME/platforms/android-34/android.jar")"
$ javac -nowarn -cp "$AJ" -d jx-classes jx/sources/io/seika/smali/*.java && echo "javac: rc=0"
javac: rc=0
$ ls jx-classes/io/seika/smali
Gate.class
MainActivity.class
R$string.class
R.class
```

다시 빌드할 때 문제가 되는 것은 [4장](/posts/android-lab-p1c04-jadx-static-analysis/)에서 본 `Method not decompiled` stub이다.

jadx가 stub으로 바꿀 코드를 일부러 만들었다. 입구가 둘인 루프다. 인자가 0이면 루프 한가운데 `:b`로 뛰어들고 아니면 `:a`로 흘러 들어간다. Java의 구조화된 반복문에서 javac가 이런 모양을 만들 일은 없지만 Dalvik 바이트코드로는 문제없는 코드다. 직접 쓴 `Odd.smali`의 1~24행이다.

```smali
.class public Lio/seika/smali/Odd;
.super Ljava/lang/Object;


# A loop with two entry points: falling through enters at :a, the first branch enters at :b.
# javac never emits this shape, but it is valid Dalvik bytecode.
.method public static odd(I)I
    .locals 0

    if-eqz p0, :b

    :a
    add-int/lit8 p0, p0, -0x1

    if-lez p0, :end

    :b
    add-int/lit8 p0, p0, -0x2

    if-gtz p0, :a

    :end
    return p0
.end method
```

26~74행의 `report()`는 `Odd.odd(7)`과 `Odd.odd(0)`의 결과를 `SmaliLab` 태그로 찍는다.

```smali
.method public static report()V
    .locals 3

    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "Odd.odd(7) = "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    const/4 v1, 0x7

    invoke-static {v1}, Lio/seika/smali/Odd;->odd(I)I

    move-result v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v0

    const-string v1, ", Odd.odd(0) = "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    move-result-object v0

    const/4 v1, 0x0

    invoke-static {v1}, Lio/seika/smali/Odd;->odd(I)I

    move-result v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    move-result-object v0

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "SmaliLab"

    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method
```

이 파일을 앱의 smali 트리에 복사하고 `MainActivity.smali` 136행 `.line 25` 다음, 곧 `onCreate`의 `return-void` 바로 앞에 `report()` 호출을 넣어 빌드했다. 호스트 JVM에서 jadx 쪽 결과를 돌려 볼 때는 아래 `OddCheck.java`를 썼고 `AJ`는 앞에서 정한 android.jar 경로다.

```java
public class OddCheck {
    public static void main(String[] args) {
        System.out.println("Odd.odd(7) = " + io.seika.smali.Odd.odd(7));
    }
}
```

```bash
export AJ="$(cygpath -w "$ANDROID_HOME/platforms/android-34/android.jar")"
apktool d -q -p fw smalilab.apk -o oddlab
cp Odd.smali oddlab/smali/io/seika/smali/
sed -i '136a\    invoke-static {}, Lio/seika/smali/Odd;->report()V' oddlab/smali/io/seika/smali/MainActivity.smali
grep -n . oddlab/smali/io/seika/smali/Odd.smali | sed -n '/static odd/,/end method/p'
apktool b -q -p fw oddlab -o oddlab-unsigned.apk && echo "oddlab: built"
jadx -q -d jx-odd oddlab-unsigned.apk
grep -n -E 'multi-entry|decompiled incorrectly|throw new' jx-odd/sources/io/seika/smali/Odd.java
javac -nowarn -cp "$AJ" -d jx-odd-classes jx-odd/sources/io/seika/smali/*.java && echo "javac: jadx output compiled"
java -cp jx-odd-classes OddCheck.java 2>&1 | head -2
zipalign -p -f 4 oddlab-unsigned.apk oddlab-aligned.apk && apksigner sign --ks debug.keystore --ks-pass pass:android --out oddlab.apk oddlab-aligned.apk
```

![Odd.smali의 odd(I)I 7~24행(.locals 0, if-eqz p0, :b, :a의 add-int/lit8 p0, p0, -0x1과 if-lez p0, :end, :b의 add-int/lit8 p0, p0, -0x2와 if-gtz p0, :a, :end의 return p0)을 앱에 넣고 apktool b가 oddlab: built를 찍은 뒤, jadx가 만든 Odd.java 32행 JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:6:0x0008 -> B:3:0x0002), 34행 Code decompiled incorrectly, 49행 throw new UnsupportedOperationException(Method not decompiled: io.seika.smali.Odd.odd(int):int), javac: jadx output compiled, java -cp jx-odd-classes OddCheck.java가 UnsupportedOperationException at io.seika.smali.Odd.odd(Odd.java:49)로 끝나는 터미널](/assets/img/android-mastery/p1c05/09-jadx-multi-entry-loop.png)

jadx는 0x0008에서 0x0002로 돌아가는 back edge를 보고 다중 입구 루프 경고를 단 뒤 4장에서 본 것과 같은 stub으로 본문을 바꿨다. 이 stub은 문법상 멀쩡한 Java라서 javac는 오류 없이 컴파일했고 실행하자 49행에서 예외가 났다.

dex 쪽에는 손으로 쓴 루프가 그대로 들어갔다. dexdump로 본 조립 결과다(`.locals 0`이라 p0이 v0이다).

```text
|0000: if-eqz v0, 0006 // +0006
|0002: add-int/lit8 v0, v0, #int -1 // #ff
|0004: if-lez v0, 000a // +0006
|0006: add-int/lit8 v0, v0, #int -2 // #fe
|0008: if-gtz v0, 0002 // -0006
|000a: return v0
```

이 명령을 한 줄씩 따라가면 `odd(7)`은 7, 6, 4, 3, 1, 0을 거쳐 0을 돌려주고 `odd(0)`은 곧장 0x0006으로 뛰어 -2를 돌려준다. 정렬하고 서명해 둔 `oddlab.apk`를 에뮬레이터에 덮어 깔아 띄웠다.

```bash
adb -s $S install -r oddlab.apk
adb -s $S logcat -c
adb -s $S shell am start -S -n io.seika.smali/.MainActivity
sleep 3
adb -s $S logcat -d -s SmaliLab:I
```

![adb install -r oddlab.apk가 Success로 끝나고, am start -S로 다시 띄운 뒤 logcat -d -s SmaliLab:I에 isEnabled -> PRO features: locked (seika / uses=3)와 Odd.odd(7) = 0, Odd.odd(0) = -2 두 줄이 찍힌 터미널](/assets/img/android-mastery/p1c05/10b-device-oddlab.png)

ART에서는 `Odd.odd(7) = 0, Odd.odd(0) = -2`가 찍혔다. 손으로 따라간 값과 같다. 입구가 둘인 루프라도 ART 검증기는 문제 삼지 않았다. 게이트 줄이 `locked`인 것은 oddlab을 고치지 않은 원본 APK에서 만들었기 때문이다.

## 자리나 레지스터를 잘못 고른 const/4도 조립은 된다

같은 한 줄을 잘못 넣으면 어떻게 되는지도 봤다. `badorder`는 `const/4 v0, 0x1`을 `invoke-virtual`과 `move-result` 사이에 넣었다. `badreg`는 위치는 맞게 `move-result v0` 다음에 두되 대상 레지스터를 `p1`로 잘못 골랐다. 앞에서 본 대로 p1에는 `Gate` 객체가 들어 있다.

```bash
apktool d -q -p fw smalilab.apk -o badorder
apktool d -q -p fw smalilab.apk -o badreg
sed -i '32a\    const/4 v0, 0x1' badorder/smali/io/seika/smali/MainActivity.smali
sed -i '34a\    const/4 p1, 0x1' badreg/smali/io/seika/smali/MainActivity.smali
diff -u --strip-trailing-cr smali.orig/io/seika/smali/MainActivity.smali badorder/smali/io/seika/smali/MainActivity.smali
diff -u --strip-trailing-cr smali.orig/io/seika/smali/MainActivity.smali badreg/smali/io/seika/smali/MainActivity.smali
apktool b -q -p fw badorder -o badorder-unsigned.apk && echo "badorder: built"
apktool b -q -p fw badreg -o badreg-unsigned.apk && echo "badreg: built"
jadx -q -d jx-badorder badorder-unsigned.apk; grep -m1 'JADX ERROR' jx-badorder/sources/io/seika/smali/MainActivity.java
jadx -q -d jx-badreg badreg-unsigned.apk; grep -m1 'JADX ERROR' jx-badreg/sources/io/seika/smali/MainActivity.java
for v in badorder badreg; do zipalign -p -f 4 $v-unsigned.apk $v-aligned.apk && apksigner sign --ks debug.keystore --ks-pass pass:android --out $v.apk $v-aligned.apk; done
ls badorder.apk badreg.apk
for v in badorder badreg; do mkdir -p d8-$v; unzip -p $v.apk classes.dex > $v.dex; d8 --min-api 26 --output d8-$v $v.dex; echo "$v d8 rc=$?"; done
```

![badorder와 badreg로 따로 디코드한 뒤 sed -i로 각각 32행 다음에 const/4 v0, 0x1, 34행 다음에 const/4 p1, 0x1을 넣고, diff에서 badorder는 invoke-virtual {p1} isEnabled()Z와 move-result v0 사이에, badreg는 move-result v0 아래에 추가 줄이 보이며, apktool b가 badorder: built와 badreg: built를 찍고, jadx 결과 grep이 JADX ERROR: MOVE_RESULT instruction can be used only in fallback mode와 JADX ERROR: JadxRuntimeException in pass: ConstInlineVisitor를 내고, zipalign과 apksigner를 거쳐 ls에 badorder.apk와 badreg.apk가 나오는 터미널](/assets/img/android-mastery/p1c05/08-bad-patches-host.png)

캡처에 없는 마지막 줄은 서명한 APK에서 dex를 꺼내 d8로 다시 변환한다. 출력은 이 두 줄이 전부였다.

```text
badorder d8 rc=0
badreg d8 rc=0
```

둘 다 Dalvik 규칙을 어긴다. [Constraints](https://source.android.com/docs/core/runtime/constraints) 문서의 B19는 `move-result<kind>` 바로 앞 명령이 `invoke-<kind>`여야 한다고 정하고 B1은 명령의 인자 개수와 타입이 언제나 명령과 맞아야 한다고 정한다. smali 어셈블러는 이 규칙을 검사하지 않아 둘 다 조립했고 apktool도 묶어 냈다. 만들어진 dex를 d8로 dex→dex 변환해 봐도 위처럼 종료 코드 0에 경고 하나 없었고 서명까지 문제없이 됐으니 호스트에서 이상을 알린 도구는 jadx 하나였다. jadx가 badreg의 `MainActivity.java` 주석에 남긴 스택 트레이스에는 `Unexpected instance arg in invoke`라는 원인도 찍혔다.

dexdump로 보면 무엇이 틀렸는지 분명하다.

```text
### badorder
|000a: invoke-virtual {v6}, Lio/seika/smali/Gate;.isEnabled:()Z // method@0008
|000d: const/4 v0, #int 1 // #1
|000e: move-result v0
### badreg
|000d: move-result v0
|000e: const/4 v6, #int 1 // #1
...
|002f: invoke-virtual {v6, v2, v3, v4}, Lio/seika/smali/Gate;.label:(JLjava/lang/String;)Ljava/lang/String; // method@0009
```

badorder에서는 `move-result`가 invoke가 아닌 `const/4` 뒤에 온다. badreg에서는 p1, 곧 v6에 정수 1이 들어간 채로 0x2f에서 `Gate.label()`의 수신 객체로 쓰인다.

이런 코드를 잡는 곳은 기기의 ART 검증기다. Android 13의 ART 소스로 보면 검증기는 결과 레지스터를 채우는 invoke 류가 아닌 명령을 하나 처리할 때마다 결과 레지스터를 비운다([method_verifier.cc L3369-3376](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/runtime/verifier/method_verifier.cc#3369)). 그래서 badorder의 `move-result`가 결과를 꺼내려 할 때 타입이 맞지 않고 `CopyResultRegister1`이 `VERIFY_ERROR_BAD_CLASS_HARD`로 실패하며 `copyRes1 v0<- result0 type=...` 꼴의 메시지를 만든다([register_line.cc L167-172](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/runtime/verifier/register_line.cc#167)).

![ART 검증기 소스 register_line.cc의 161~187행 화면. 167행 void RegisterLine::CopyResultRegister1(MethodVerifier* verifier, uint32_t vdst, bool is_reference)가 강조돼 있고, 168~170행이 결과 레지스터의 타입이 category-1이나 참조 타입인지 검사하며, 171~172행이 verifier->Fail(VERIFY_ERROR_BAD_CLASS_HARD)로 copyRes1 v, vdst, result0, type= 를 이어 붙인 메시지를 만든다](/assets/img/android-mastery/p1c05/13-src-art-copyres1.png)

badreg는 같은 파일의 `GetInvocationThis`에 걸린다. 수신 객체 레지스터가 참조 타입이 아니면 `tried to get class from non-reference register` 메시지로 실패한다([register_line.cc L62-66](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r84/runtime/verifier/register_line.cc#62)). 둘 다 hard failure라서 ART는 `MainActivity` 클래스를 통째로 거부한다.

두 APK를 에뮬레이터에 덮어 깔고 띄웠다. badreg.apk도 같은 다섯 줄로 돌렸다.

```bash
adb -s $S install -r badorder.apk
adb -s $S logcat -c
adb -s $S shell am start -n io.seika.smali/.MainActivity
sleep 3
adb -s $S logcat -d | grep -m1 -oE 'VerifyError: .*'
```

![adb install -r badorder.apk와 badreg.apk가 각각 Success로 끝난 뒤 앱을 띄우고 logcat에서 VerifyError를 grep한 결과. badorder는 Verifier rejected class io.seika.smali.MainActivity ... onCreate(android.os.Bundle): 0xE copyRes1 v0<- result0 type=Undefined, badreg는 같은 앞부분에 0x2F tried to get class from non-reference register v6 (type=Precise Constant: 1)가 찍힌 터미널](/assets/img/android-mastery/p1c05/10-device-verifier.png)

둘 다 설치는 `Success`였다. 앱을 띄우자 badorder는 `[0xE] copyRes1 v0<- result0 type=Undefined`, badreg는 `[0x2F] tried to get class from non-reference register v6 (type=Precise Constant: 1)`를 달고 `VerifyError: Verifier rejected class io.seika.smali.MainActivity`로 죽었다. 0xE와 0x2F는 위 dexdump의 `move-result`와 `Gate.label()` 호출 위치와 같다. 크래시 버퍼의 스택 맨 위가 `AppComponentFactory.instantiateActivity` 안의 `Class.newInstance`이니 `loadClass`는 이미 지나갔고 액티비티 객체를 만들려고 그 클래스를 처음 쓰는 순간 거부됐다.

설치 단계에서 미리 알 수는 없는지 보려고 badorder를 한 번 더 깔았다. 이번에는 `logcat -c`를 설치 앞에 두었다. grep에 걸린 줄 가운데 검증 두 줄만 옮기고 installd 실행 줄, CPU 변형 경고, 실행 인자, GC·통계 줄은 `...`로 줄였다.

```text
$ adb -s $S logcat -c
$ adb -s $S install -r badorder.apk
Performing Incremental Install
Performing Streamed Install
Success
$ sleep 2
$ adb -s $S logcat -d | grep -iE 'verif|dex2oat|VerifyError' | head -20
...
10-15 01:54:50.341  6144  6151 W dex2oat64: Verification error in void io.seika.smali.MainActivity.onCreate(android.os.Bundle)
10-15 01:54:50.341  6144  6151 W dex2oat64: void io.seika.smali.MainActivity.onCreate(android.os.Bundle) failed to verify: void io.seika.smali.MainActivity.onCreate(android.os.Bundle): [0xE] copyRes1 v0<- result0 type=Undefined
...
```

dex2oat64가 설치 중에 `onCreate`를 검증하다 실행 때와 같은 메시지를 경고(`W`)로 남겼지만 설치는 `Success`로 끝났다. badreg를 같은 순서로 깔았을 때는 `[0x2F] tried to get class from non-reference register v6` 경고가 남았다.

## 클라이언트 게이트는 서버로

에뮬레이터 화면에서 본 대로 이 게이트는 `const/4` 한 줄에 열렸다. 클라이언트에서만 판단하는 라이선스, 유료 기능 플래그, 루트 탐지 결과는 같은 방법으로 뒤집힌다. 유료 기능이라면 판단을 서버로 옮기고 서버가 사용자 권한을 직접 확인한 뒤에만 기능에 필요한 데이터를 내려 줘야 한다([인증과 인가(C02)](/posts/android-concept-atlas-c02-authn-authz/)). 방어가 제대로 됐는지는 자기 앱에 위의 절차를 돌려 보면 안다. 게이트를 뒤집은 빌드를 만들어 기능이 서버 응답 없이도 열리는지 본다.

이번에는 원본과 같은 debug 키로 서명해서 서명자가 바뀌지 않았다. 남의 앱을 이렇게 고치는 사람은 원래 키가 없으니 자기 키로 서명해야 한다. 그러면 서명자가 달라진다. 서버가 이 차이를 알려면 기기 밖에서 앱 무결성을 확인해 줄 수단이 있어야 하고 [Play Integrity(C48)](/posts/android-concept-atlas-c48-play-integrity/) 같은 증명이 그 역할을 한다.

참고 자료: [Apktool CLI parameters](https://apktool.org/docs/cli-parameters/) · [Apktool FAQ](https://apktool.org/docs/faq/) · [Apktool v3.0.2 소스](https://github.com/iBotPeaches/Apktool/tree/v3.0.2) · [google/smali](https://github.com/google/smali) · [Dalvik bytecode format](https://source.android.com/docs/core/runtime/dalvik-bytecode) · [Dalvik executable format](https://source.android.com/docs/core/runtime/dex-format) · [Constraints](https://source.android.com/docs/core/runtime/constraints) · [ART: DEX→OAT→VDEX(C13)](/posts/android-concept-atlas-c13-art-dex-oat-vdex/) · [DEX·multidex·resources.arsc(C07)](/posts/android-concept-atlas-c07-dex-multidex-resources-arsc/)

*다음 글: [매니페스트 공격 표면 매핑](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)*
