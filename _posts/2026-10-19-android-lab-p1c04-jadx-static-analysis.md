---
layout: post
title: "jadx 정적 분석 — 난독화된 이름과 복원에 실패한 메서드"
date: 2026-10-19 21:00:00 +0900
category: 블로그/기술문서
author: SeiKa
tags: [Android, AndroidSecurity, 모바일보안, jadx, R8, 난독화, Kotlin, 정적분석]
excerpt: "같은 Kotlin 앱을 디버그와 R8 릴리스로 빌드해 jadx 1.5.5로 풀었다. 이름이 a.a.a로 바뀐 빌드에서도 매니페스트와 사용처 검색으로 하드코딩 키와 JS 브리지에 닿았지만, jadx가 복원을 포기한 코루틴 메서드 속 토큰은 grep에 잡히지 않았다. XOR 패커로 숨긴 DEX는 Frida와 /proc/pid/mem 덤프로 원본과 같은 해시로 떠냈다."
---

[지난 글](/posts/android-lab-p1c03-apk-triage/)에서 서명과 매니페스트를 훑었으니 이번에는 코드를 연다. 앱을 받으면 습관처럼 jadx부터 돌리는데, jadx가 보여 주는 Java는 DEX 바이트코드를 보고 다시 지은 코드다. jadx README 맨 앞에도 대부분의 경우 코드를 100% 디컴파일하지는 못해 오류가 난다는 경고가 붙어 있다([README v1.5.5, 19행](https://github.com/skylot/jadx/blob/v1.5.5/README.md?plain=1#L19)).

다시 지은 코드라는 사실이 분석 중 언제 발목을 잡는지 직접 보고 싶었다. 그래서 정답을 아는 앱을 만들어 jadx 1.5.5에 넣었다. 같은 소스를 디버그와 R8 릴리스로 빌드해 이름이 어디까지 사라지는지 비교했고 일부러 꼬아 둔 코루틴 메서드가 디컴파일에서 어떻게 무너지는지, 장난감 패커를 씌우면 jadx에 무엇이 남고 숨긴 DEX를 메모리에서 어떻게 다시 꺼내는지도 확인했다. 디컴파일과 검색은 호스트(Windows, Git Bash)에서 했고 JDK는 Android Studio에 딸린 JBR 21이다. 디버그 APK를 실제로 돌린 에뮬레이터는 Android 13(API 33) x86_64 AVD였다. 패커 덤프도 같은 시리얼의 에뮬레이터에서 했지만 그때 어느 AVD였는지는 기록해 두지 않았다.

## 키와 JS 브리지를 일부러 심은 Kotlin 앱

실험 앱 `io.seika.jadxlab`은 AGP 8.5.2와 Kotlin 1.9.24로 빌드했고 릴리스 쪽에서는 R8 8.5.35가 돌았다. minSdk 26, targetSdk 33이다. flavor를 vuln과 safe로 나눠 아래 APK를 뽑았고 모두 debug 키로 서명했다.

| APK | flavor, build type | 차이 |
|---|---|---|
| `jadxlab-debug.apk` | vuln, debug | R8 없음, 디버그 정보 있음 |
| `jadxlab-release.apk` | vuln, release | R8 축소와 난독화 |
| `jadxlab-safe.apk` | safe, release | 같은 R8 설정, Keystore 키, JS 브리지 없음 |

릴리스 빌드의 R8 규칙은 기본 `proguard-android-optimize.txt`에 JavaScript가 이름으로 부르는 메서드를 지키는 keep 한 줄을 더했다. 빌드 뒤 R8이 받은 설정을 모은 `configuration.txt`를 보니 기본 파일에 같은 규칙이 이미 들어 있었다. 이 줄은 같은 말을 한 번 더 적은 셈이다.

```text
-keepclassmembers class * { @android.webkit.JavascriptInterface <methods>; }
```

vuln flavor의 `CryptoBox`는 16바이트 AES 키를 소스에 박아 두고 IV를 0으로 채운다. `TokenBridge`는 그 키로 세션 문자열을 봉인해 JavaScript에 돌려준다. 아래는 실제로 빌드한 소스이고 package·import 줄만 뺐다.

```kotlin
// src/vuln/java/io/seika/jadxlab/CryptoBox.kt
object CryptoBox {
    private val KEY = "k3y-for-jadx-lab".toByteArray() // hardcoded 16-byte AES key
    private val IV = ByteArray(16)                       // all-zero IV

    fun seal(plain: String): String {
        val c = Cipher.getInstance("AES/CBC/PKCS5Padding")
        c.init(Cipher.ENCRYPT_MODE, SecretKeySpec(KEY, "AES"), IvParameterSpec(IV))
        return Base64.encodeToString(c.doFinal(plain.toByteArray()), Base64.NO_WRAP)
    }
}

// src/vuln/java/io/seika/jadxlab/Bridges.kt
object Bridges {
    fun attach(web: WebView, ctx: Context) {
        web.addJavascriptInterface(TokenBridge(ctx), "SeikaBridge")
    }
}

class TokenBridge(private val ctx: Context) {
    @JavascriptInterface
    fun token(): String {
        val s = Session("u1001", "t-bridge", System.currentTimeMillis() + 60_000)
        return CryptoBox.seal(s.toString())
    }

    @JavascriptInterface
    fun packageName(): String = ctx.packageName
}
```

브리지를 붙이는 곳은 `seika://promo` 링크로 열리는 `PromoActivity`다. JavaScript를 켠 WebView에 브리지를 달고 링크의 `u` 파라미터를 그대로 연다. `Session`은 `data class Session(val userId: String, val token: String, val expiresAt: Long)` 한 줄짜리다.

```kotlin
// src/main/java/io/seika/jadxlab/PromoActivity.kt
class PromoActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val web = WebView(this)
        setContentView(web)
        web.settings.javaScriptEnabled = true
        Bridges.attach(web, this)
        val target = intent?.data?.getQueryParameter("u") ?: "about:blank"
        web.loadUrl(target)
    }
}
```

마지막으로 jadx를 괴롭히려고 `Sync.pullAll`을 넣었다. 재시도 루프 안에 try/catch/finally와 `delay()`를 여러 번 두었고 헤더 맵에는 업로드 토큰처럼 생긴 리터럴 `seika-upl-2c9e41d7`을 넣었다. `fakeFetch`는 id의 문자 코드 합에 헤더 개수 2를 더해 7의 배수면 예외를 던지고, 짝수면 200, 홀수면 429를 돌려준다. `MainActivity`는 이 함수를 `listOf("alpha", "echo", "papa", "delta")`와 재시도 3으로 부른다.

```kotlin
// src/main/java/io/seika/jadxlab/Sync.kt
object Sync {
    // A suspend function with retries, try/catch/finally and several suspension points.
    // kotlinc turns it into a state machine (invokeSuspend + label switch).
    suspend fun pullAll(ids: List<String>, retries: Int): Map<String, Int> {
        val out = LinkedHashMap<String, Int>()
        val headers = mapOf("X-Upload-Token" to "seika-upl-2c9e41d7", "User-Agent" to "jadxlab/1.0")
        for (id in ids) {
            var attempt = 0
            while (attempt < retries) {
                try {
                    delay(10L * (attempt + 1))
                    val code = fakeFetch(id, headers)
                    if (code == 200) {
                        out[id] = code
                        break
                    }
                    if (code == 429) {
                        delay(30)
                        continue
                    }
                    out[id] = code
                } catch (e: IllegalStateException) {
                    Log.w("jadxlab", "retry $id: ${e.message}")
                    delay(20)
                } finally {
                    attempt++
                }
            }
        }
        return out
    }

    private suspend fun fakeFetch(id: String, h: Map<String, String>): Int {
        delay(5)
        val sum = id.sumOf { it.code } + h.size
        if (sum % 7 == 0) throw IllegalStateException("flaky $id")
        return if (sum % 2 == 0) 200 else 429
    }
}
```

## 매니페스트에 적힌 진입점은 R8을 거쳐도 이름이 남는다

R8 빌드를 jadx-gui로 열었다. 소스코드 트리는 `a`부터 `s`까지의 한 글자 패키지와 `defpackage`가 거의 다 차지했고 긴 이름은 `kotlin.coroutines.jvm.internal`과 `io.seika.jadxlab` 둘뿐이었다. 원래 이름을 지킨 앱 클래스는 `io.seika.jadxlab` 아래 `MainActivity`와 `PromoActivity`뿐이다. 둘 다 매니페스트가 클래스 이름으로 부르는 컴포넌트다. 빌드가 남긴 매핑 파일에도 `io.seika.jadxlab.PromoActivity -> io.seika.jadxlab.PromoActivity:`처럼 제 이름 그대로 적혀 있다.

![jadx-gui 에 jadxlab-release.apk 를 연 화면. 왼쪽 소스코드 트리에 한 글자 패키지 a 부터 s 와 defpackage, 잘려 보이는 kotlin.coroutines.jvm.intern 패키지, 이름이 남은 io.seika.jadxlab 아래 MainActivity 와 PromoActivity 두 클래스가 보이고, 오른쪽 AndroidManifest.xml 탭에서 io.seika.jadxlab.PromoActivity 가 강조되어 있으며 android:exported=true, action VIEW, category DEFAULT 와 BROWSABLE, data scheme seika host promo 가 보인다](/assets/img/android-mastery/p1c04/01-jadxgui-manifest-promo-exported.png)

매니페스트에 적힌 클래스 이름을 누가 지켰는지는 R8이 실제로 받은 설정을 모아 둔 `configuration.txt`에 나온다. 끝 무렵 구간이 리소스를 처리한 AAPT2가 만든 `aapt_rules.txt`이고 거기에 `-keep class io.seika.jadxlab.MainActivity { <init>(); }`와 `-keep class io.seika.jadxlab.PromoActivity { <init>(); }` 두 줄이 있다. AAPT2는 매니페스트를 훑으면서 activity, service, receiver, provider의 `android:name`을 모으고([ProguardRules.cpp 303~328행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/tools/aapt2/java/ProguardRules.cpp#303)) 클래스마다 이 keep 규칙을 한 줄씩 쓴다([411행](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/tools/aapt2/java/ProguardRules.cpp#411)). 링크한 소스는 에뮬레이터 이미지에 맞춘 android-13.0.0_r1 태그이고 빌드에서 실제로 돈 AAPT2는 AGP 8.5.2에 딸린 판이다. 시스템이 매니페스트에 적힌 문자열로 클래스를 찾기 때문에, 이 이름까지 바꾸면 앱이 뜨지 않는다.

jadx는 바이너리 XML로 컴파일된 AndroidManifest.xml도 풀어 리소스 트리에 보여 준다. `PromoActivity`는 `android:exported="true"`에 VIEW, DEFAULT, BROWSABLE 필터로 `seika://promo`를 받으니 브라우저 링크로도 열리는 입구다. 매니페스트로 공격면 지도를 그리는 일은 [6장](/posts/android-lab-p1c06-manifest-attack-surface-mapping/)에서 따로 하고 여기서는 이 입구를 코드 읽기의 출발점으로 쓴다.

![jadx-gui 에서 R8 빌드의 PromoActivity 코드를 연 화면. 3행 import a.g, 19행 webView.getSettings().setJavaScriptEnabled(true), 강조된 20행 webView.addJavascriptInterface(new g(this), SeikaBridge), 25행 webView.loadUrl(queryParameter) 가 보이고 하단에 코드, Smali, Simple, Fallback 탭이 있다](/assets/img/android-mastery/p1c04/02-jadxgui-promo-bridge-r8.png)

`PromoActivity` 20행에 `addJavascriptInterface(new g(this), "SeikaBridge")`가 있다. 디버그 빌드의 같은 메서드와 나란히 놓으면 R8이 무엇을 했는지 보인다. 둘 다 jadx 출력 그대로다.

```java
// jadxlab-debug.apk, PromoActivity.onCreate
    protected void onCreate(Bundle savedInstanceState) {
        String target;
        Uri data;
        super.onCreate(savedInstanceState);
        WebView web = new WebView(this);
        setContentView(web);
        web.getSettings().setJavaScriptEnabled(true);
        Bridges.INSTANCE.attach(web, this);
        Intent intent = getIntent();
        if (intent == null || (data = intent.getData()) == null || (target = data.getQueryParameter("u")) == null) {
            target = "about:blank";
        }
        web.loadUrl(target);
    }

// jadxlab-release.apk, PromoActivity.onCreate
    public final void onCreate(Bundle bundle) {
        String queryParameter;
        Uri data;
        super.onCreate(bundle);
        WebView webView = new WebView(this);
        setContentView(webView);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.addJavascriptInterface(new g(this), "SeikaBridge");
        Intent intent = getIntent();
        if (intent == null || (data = intent.getData()) == null || (queryParameter = data.getQueryParameter("u")) == null) {
            queryParameter = "about:blank";
        }
        webView.loadUrl(queryParameter);
    }
```

R8이 `Bridges.attach`를 호출부에 인라인하고 `Bridges` 객체는 통째로 지웠다. 난독화가 걸리면 sink 찾기가 어려워질 줄 알았는데, 이 경우엔 오히려 sink가 진입점 클래스 안으로 끌려왔다. JavaScript 활성화, 브리지 등록, 인텐트에서 받은 `u` 값을 그대로 넘기는 `loadUrl`이 한 메서드에 모였으니, 코드만 보면 `seika://promo?u=` 링크 하나로 아무 페이지나 열어 `SeikaBridge`를 쥐여 주는 구조다. 기기에 띄워 확인하지는 않았다. 딥링크에서 WebView 브리지까지 실제로 따라가는 일은 [20장](/posts/android-lab-p1c20-deeplink-applink-webview/)에서 한다.

## 이름이 `a`뿐인 함수는 누가 부르는지부터 모은다

`new g(this)`를 따라 `a.g`로 가 보면 `@JavascriptInterface`가 붙은 `token()`과 `packageName()`은 이름이 그대로다. 기본 설정 파일에 든 그 keep 규칙이 지킨 메서드들이다. `token()`은 `a.a("Session(userId=u1001, token=t-bridge, expiresAt=" + jCurrentTimeMillis + ")")`를 돌려주는데, `a.a`라는 이름만으로는 무슨 함수인지 알 길이 없다. 이럴 때는 jadx-gui의 사용 검색(Find Usage)으로 호출부를 먼저 모은다.

![jadx-gui 의 사용 검색 창, 제목 사용 검색: a. 대상은 a.a.a(String) String 이고 결과는 a.g.token() 의 return a.a(Session(userId=u1001, token=t-bridge, expiresAt= ... 줄과 io.seika.jadxlab.MainActivity.onCreate 의 String strA = a.a.a(Session(userId=u1001, token= ... 줄 두 개, 아래에 2개 찾음 (검색 완료)](/assets/img/android-mastery/p1c04/03-jadxgui-usage-obfuscated-seal.png)

`a.a.a(String)`을 부르는 곳은 `a.g.token()`과 `MainActivity.onCreate` 두 군데였고 둘 다 `Session(userId=...` 틀의 문자열을 넘긴다. 원래 소스의 `Session`은 data class인데 R8 빌드에는 그 클래스가 아예 없다. data class가 만들어 준 `toString()`이 호출부마다 인라인되면서 클래스는 지워지고 틀 문자열만 남았다. 그 바람에 필드 이름 `userId`, `token`, `expiresAt`이 문자열로 고스란히 드러났다. 개발자 쪽에 남는 R8 매핑 파일(`mapping.txt`)을 열어 보면 이 일이 그대로 적혀 있다. 아래는 그 발췌다.

```text
io.seika.jadxlab.Session -> R8$$REMOVED$$CLASS$$1:
io.seika.jadxlab.Bridges -> R8$$REMOVED$$CLASS$$0:
io.seika.jadxlab.TokenBridge -> a.g:
    android.content.Context ctx -> a
    5:10:void <init>(android.content.Context):13:13 -> <init>
    0:11:java.lang.String packageName():21:21 -> packageName
    0:8:java.lang.String token():16:16 -> token
    9:10:java.lang.String token():17:17 -> token
    11:29:java.lang.String io.seika.jadxlab.Session.toString():0:0 -> token
```

jadx-gui에는 이름을 직접 바꾸는 rename 기능도 있다. 바꾼 이름이 사용처까지 따라가는지는 이번에 써 보지 않아 확인하지 못했다.

## 키 문자열은 `SecretKeySpec` 줄에 없었다

`a.a`가 암호화 함수라는 건 몸통의 `Cipher`와 `SecretKeySpec`만 봐도 안다. 하드코딩 키를 찾을 때 흔히 쓰는 grep을 R8 빌드 출력에 돌려 봤다. sink 이름과 16자 넘는 base64 꼴 문자열을 한 번에 찾는 식이다.

```bash
jadx -q -d j-release jadxlab-release.apk
grep -rniE 'SecretKeySpec|addJavascriptInterface|"[A-Za-z0-9+/]{16,}="' j-release/sources
```

```text
j-release/sources/a/a.java:10:import javax.crypto.spec.SecretKeySpec;
j-release/sources/a/a.java:31:        cipher.init(1, new SecretKeySpec(f0a, "AES"), new IvParameterSpec(f1b));
j-release/sources/io/seika/jadxlab/PromoActivity.java:20:        webView.addJavascriptInterface(new g(this), "SeikaBridge");
```

sink 두 곳과 import 한 줄은 잡혔는데 키는 없다. `SecretKeySpec`에 들어가는 것은 리터럴이 아닌 필드 `f0a`다. 키 `k3y-for-jadx-lab`은 하이픈이 섞여 base64 꼴 정규식에도 안 걸린다. Kotlin의 `private val KEY = "...".toByteArray()`는 클래스의 static 초기화 블록이 되므로, sink에서 필드를 거슬러 올라가 static 블록까지 가야 키가 나온다. 같은 클래스를 jadx가 두 빌드에서 어떻게 풀었는지 붙여 둔다(클래스 몸통만 옮겼다).

```java
// jadxlab-debug.apk: io/seika/jadxlab/CryptoBox.java
public final class CryptoBox {
    public static final CryptoBox INSTANCE = new CryptoBox();
    private static final byte[] IV;
    private static final byte[] KEY;

    private CryptoBox() {
    }

    static {
        byte[] bytes = "k3y-for-jadx-lab".getBytes(Charsets.UTF_8);
        Intrinsics.checkNotNullExpressionValue(bytes, "getBytes(...)");
        KEY = bytes;
        IV = new byte[16];
    }

    public final String seal(String plain) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, InvalidAlgorithmParameterException {
        Intrinsics.checkNotNullParameter(plain, "plain");
        Cipher c = Cipher.getInstance("AES/CBC/PKCS5Padding");
        c.init(1, new SecretKeySpec(KEY, "AES"), new IvParameterSpec(IV));
        byte[] bytes = plain.getBytes(Charsets.UTF_8);
        Intrinsics.checkNotNullExpressionValue(bytes, "getBytes(...)");
        String strEncodeToString = Base64.encodeToString(c.doFinal(bytes), 2);
        Intrinsics.checkNotNullExpressionValue(strEncodeToString, "encodeToString(...)");
        return strEncodeToString;
    }
}

// jadxlab-release.apk: a/a.java
public abstract class a {

    /* JADX INFO: renamed from: a, reason: collision with root package name */
    public static final byte[] f0a;

    /* JADX INFO: renamed from: b, reason: collision with root package name */
    public static final byte[] f1b;

    static {
        byte[] bytes = "k3y-for-jadx-lab".getBytes(o.a.f77a);
        k.d.d(bytes, "getBytes(...)");
        f0a = bytes;
        f1b = new byte[16];
    }

    public static String a(String str) throws NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, InvalidAlgorithmParameterException {
        k.d.e(str, "plain");
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(1, new SecretKeySpec(f0a, "AES"), new IvParameterSpec(f1b));
        byte[] bytes = str.getBytes(o.a.f77a);
        k.d.d(bytes, "getBytes(...)");
        String strEncodeToString = Base64.encodeToString(cipher.doFinal(bytes), 2);
        k.d.d(strEncodeToString, "encodeToString(...)");
        return strEncodeToString;
    }
}
```

두 빌드 모두 static 블록에 `"k3y-for-jadx-lab"`이 그대로 있다. 클래스와 멤버 이름을 바꾸는 난독화는 문자열 상수를 건드리지 않았다. 필드 이름 `f0a`는 jadx가 붙였다. R8이 준 이름 `a`가 루트 패키지 `a`와 겹치자 jadx가 `renamed from: a` 주석을 달고 바꿨다.

지역 변수 이름도 차이가 난다. 디버그 빌드의 `Cipher c`는 Kotlin 소스의 `val c`가 디버그 정보로 살아남은 것이다. 릴리스 쪽 `cipher`와 디버그 쪽에도 있는 `strEncodeToString`은 jadx가 타입과 메서드 이름으로 지은 이름이다. d8 문서는 릴리스용 DEX를 디버그 정보 없이 만들라고 안내하고([d8](https://developer.android.com/tools/d8)의 `--release`), R8 빌드도 지역 변수 이름을 남기지 않았다.

Kotlin의 흔적도 Java 모양으로 풀려 나온다. `object CryptoBox`는 `INSTANCE` 싱글턴 필드가 되고 `toByteArray()`는 `getBytes(Charsets.UTF_8)`와 `Intrinsics.checkNotNullExpressionValue`로, null이 될 수 없는 파라미터는 `Intrinsics.checkNotNullParameter(plain, "plain")` 검사로 바뀌었다. R8 빌드에서는 그 `Intrinsics`가 `k.d`, `Charsets.UTF_8`이 `o.a.f77a`가 됐다. 앱 클래스에 붙은 `@kotlin.Metadata` 애너테이션을 세어 보니 디버그 빌드 출력에서는 앱 클래스 10개(최상위 7개, 내부 클래스 3개)에 붙어 있었고 R8 빌드 출력에서는 0개였다. jadx 1.5.5의 `kotlin-metadata` 플러그인은 이 애너테이션으로 클래스·인자·필드 이름을 되살리는데, R8 빌드에는 그 재료가 남아 있지 않았다.

## `--deobf`가 지어 주는 이름, `mapping.txt`가 돌려주는 이름

이름을 되살리는 방법을 차례로 써 봤다. 아무 옵션 없이 푼 출력, `--deobf`를 켠 출력, 개발자의 매핑 파일을 먹인 출력에서 같은 키 문자열이 든 파일과 함수 시그니처를 뽑았다.

![터미널에서 jadxlab-release.apk 를 세 번 디컴파일한 결과. 기본 출력은 jr/sources 에 a b c d defpackage e f g h io j k kotlin l m n o p q r s 패키지가 있고 키가 든 파일은 jr/sources/a/a.java, 시그니처 String a(String str) 와 k.d.e(str, plain). --deobf 출력은 jr-deobf/sources/p001a/AbstractC0000a.java, String m0a(String str), AbstractC0063d.m46e(str, plain). --mappings-path mapping.txt -Prename-mappings.invert=yes 출력은 jr-map/sources/io/seika/jadxlab/CryptoBox.java, String a(String plain), Intrinsics.e(plain, plain)](/assets/img/android-mastery/p1c04/04-r8-names-deobf-mapping.png)

`--deobf`는 `a.a.a`를 `p001a.AbstractC0000a.m0a`로 바꿨다. 짧은 이름(기본 `--deobf-min` 3보다 짧은 것) 앞에 종류와 일련번호를 붙여 전역에서 겹치지 않게 만들 뿐이라 원래 이름 `CryptoBox.seal`은 나오지 않는다. 그래도 패키지, 클래스, 메서드, 필드가 모두 `a`로 겹쳐 나오는 기본 출력보다는 메모하고 grep 하기가 훨씬 낫다.

원래 이름은 APK에서는 사라졌지만 개발자 손에는 남는다. R8이 빌드마다 쓰는 `mapping.txt`가 원래 이름과 바뀐 이름의 대응표이고 스택 트레이스를 되돌리는 retrace도 이 파일로 일한다([retrace](https://developer.android.com/tools/retrace)). jadx 1.5.5는 `--mappings-path`로 매핑 파일을 읽는다. `--help`의 이 옵션 설명에는 Tiny와 Enigma 형식만 나오지만 `rename-mappings.format` 플러그인 옵션 목록에 `PROGUARD_FILE`이 있고 기본값 AUTO로 R8 매핑을 읽어 들였다. 처음에 `--mappings-path mapping.txt`만 줬을 때는 키가 든 `a/a.java`의 클래스 이름과 메서드 시그니처가 그대로였다. R8 매핑은 `io.seika.jadxlab.CryptoBox -> a.a:`처럼 원래 이름에서 난독 이름으로 가는 방향으로 적혀 있어서 거꾸로 읽게 하는 `-Prename-mappings.invert=yes`를 더해야 적용됐다.

```text
## --mappings-path mapping.txt (no invert)
a.java
public abstract class a {
    public static String a(String str)
## + -Prename-mappings.invert=yes
CryptoBox.java
public abstract class CryptoBox {
    public static final byte[] KEY;
    public static final byte[] IV;
    public static String a(String plain)
## mapping with line ranges stripped + invert
CryptoBox.java
public abstract class CryptoBox {
    public static String seal(String plain)
```

뒤집어 읽자 클래스 `CryptoBox`와 필드 `KEY`, `IV`는 돌아왔는데 메서드는 여전히 `a`였다. 매핑에서 `seal`은 줄 번호 범위가 붙은 줄로만 나온다. 바이트코드 구간마다 대응하는 소스 줄이 달라서 메서드 하나가 세 줄로 쪼개져 있다. 실험 삼아 앞뒤 범위를 지우고 같아진 줄을 하나로 합친 사본을 작은 스크립트로 만들었다.

```text
## mapping.txt (R8 8.5.35)
    5:10:java.lang.String seal(java.lang.String):13:13 -> a
    11:30:java.lang.String seal(java.lang.String):14:14 -> a
    31:56:java.lang.String seal(java.lang.String):15:15 -> a
## line ranges stripped
    java.lang.String seal(java.lang.String) -> a
```

이 사본을 주자 `seal(String plain)`까지 돌아왔다. jadx가 줄 범위가 붙은 메서드 줄을 왜 적용하지 않는지는 파고들지 않았다. 다만 이 사본을 분석에 그대로 쓰기는 어렵다. 범위를 지우면 인라인된 호출을 기록한 줄도 평범한 멤버 줄과 구별되지 않아서 `MainActivity` 아래에 `void io.seika.jadxlab.Session.<init>(java.lang.String,java.lang.String,long) -> onCreate` 같은 엉뚱한 대응이 생겼다.

파라미터 이름 `plain`은 매핑에 없는데도 나왔다. 기본 출력의 `k.d.e(str, "plain")`은 앞에서 본 `Intrinsics.checkNotNullParameter(plain, "plain")`이 이름만 바뀐 것이라, 둘째 인자로 파라미터 이름 문자열이 바이트코드에 남아 있다. 매핑 덕에 `k.d`가 `Intrinsics`라는 이름을 되찾자 jadx가 그 문자열로 파라미터 이름을 붙였다. Kotlin intrinsic 호출로 변수 이름을 짓는 `--use-kotlin-methods-for-var-names`(기본값 apply)가 작동한 것으로 보인다.

여기까지는 AGP 8.5.2와 R8 8.5.35에서 본 모습이다. Android의 [코드 축소 문서](https://developer.android.com/build/shrink-code) 버전 표에는 AGP 9.0부터 Kotlin null 검사를 기본으로 최적화하고(`-processkotlinnullchecks`), 9.1부터는 클래스를 최상위의 이름 없는 패키지로 옮기는 repackage가 기본이라고 적혀 있다. 최신 AGP로 빌드하면 `"plain"` 같은 문자열과 `a`부터 `s`까지의 패키지 구조가 달라질 수 있는데, AGP 9로는 빌드해 보지 않았다.

## 복원을 포기한 메서드는 예외 한 줄로 바뀐다

이제 디버그 빌드 전체를 풀었다. 디버그 정보가 다 있는 빌드인데도 마지막에 `ERROR - finished with errors, count: 28`이 찍혔다. `Sync.java`를 열어 보니 `pullAll`과 `fakeFetch` 몸통이 둘 다 사라지고 예외를 던지는 한 줄이 그 자리를 차지하고 있었다.

![터미널, 디버그 APK 분석. jadx --log-level error -d jd jadxlab-debug.apk 가 ERROR - finished with errors, count: 28 을 내고, Sync.java 87행 Method dump skipped, instruction units count: 642, 90행과 192행 throw new UnsupportedOperationException(Method not decompiled: io.seika.jadxlab.Sync.pullAll 과 fakeFetch 가 보인다. grep -rl seika-upl jd/ 결과를 wc -l 로 세면 0, --show-bad-code --single-class io.seika.jadxlab.Sync 로 다시 풀면 TuplesKt.to(X-Upload-Token, seika-upl-2c9e41d7) 이 잡히고, unzip -p jadxlab-debug.apk classes3.dex 를 grep -a 로 훑으면 seika-upl-2c9e41d7 이 나온다](/assets/img/android-mastery/p1c04/05-failed-method-grep-miss.png)

jadx는 실패한 메서드를 몰래 버리지 않는다. 메서드 머리에는 `Code decompiled incorrectly, please refer to instructions dump.` 주석과 `--show-bad-code`를 쓰라는 안내가 붙는다([MethodGen.java 119~132행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/codegen/MethodGen.java#L119-L132)). 몸통은 `throw new UnsupportedOperationException("Method not decompiled: ...")` 문장 하나로 대체된다([373~388행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/codegen/MethodGen.java#L373-L388)). `--show-bad-code`가 꺼져 있으면 이렇게 표시된 메서드는 처음부터 이 대체 코드 생성기로 넘어간다([ClassGen.java 397~406행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/codegen/ClassGen.java#L397-L406)). 예외 줄 위에는 jadx 자체 명령 덤프가 주석으로 붙는데, 명령 단위가 200을 넘으면 덤프도 생략하고 `Method dump skipped, instruction units count: N`만 남긴다([390~403행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/codegen/MethodGen.java#L390-L403)). `pullAll`은 642단위라 덤프가 없었고 200단위 아래인 `fakeFetch`에는 덤프가 주석으로 붙었다. `--show-bad-code`의 기본값은 false이고([JadxCLIArgs.java 111~112행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-cli/src/main/java/jadx/cli/JadxCLIArgs.java#L111-L112)), jadx-gui에서는 설정의 "Show inconsistent code"가 같은 역할을 한다.

요약 줄의 28은 실패한 메서드 수가 아니다. 같은 출력에서 `Method not decompiled` 예외 문장은 218개, `Code decompiled incorrectly` 주석은 200개였다(스크립트로 셌다). 주석 200개 중 183개가 `kotlinx.coroutines`였고 앱 코드는 `Sync`의 두 메서드뿐이었다.

## grep과 jadx-gui 검색이 놓친 토큰

출력에 표시가 남는다고 안심할 일은 아니다. 몸통이 throw 문으로 대체되면 그 안에 있던 문자열과 호출도 출력에서 함께 빠진다. 위 캡처에서 `grep -rl "seika-upl" jd/`는 0개 파일을 돌려줬다. jadx-gui의 코드 검색도 결과가 같았다. 전체 디컴파일이 끝날 때까지 기다린 뒤 검색했다.

![jadx-gui 텍스트 검색 창, 검색어 seika-upl, 정의 검색 범위는 코드만 체크되어 있고 결과 목록은 비어 있으며 아래에 0개 찾음 (검색 완료) 이 표시되어 있다](/assets/img/android-mastery/p1c04/06-jadxgui-search-miss-failed-method.png)

토큰은 APK 안에 멀쩡히 있다. `unzip -p jadxlab-debug.apk classes3.dex`를 `grep -a`로 훑으면 바로 나오고 `--show-bad-code`로 다시 풀면 `TuplesKt.to("X-Upload-Token", "seika-upl-2c9e41d7")`가 보인다. jadx-gui에서는 Java 대신 Smali 보기로 바꾸면 바이트코드의 `const-string`이 그대로 드러난다.

![jadx-gui 에 jadxlab-debug.apk 를 열고 io.seika.jadxlab.Sync 를 Smali 로 본 화면. 737행 const-string v11, X-Upload-Token, 강조된 739행 const-string v12, seika-upl-2c9e41d7, 741행 invoke-static TuplesKt->to, 728행 .local v8, ids:Ljava/util/List 같은 디버그 정보가 보이고 왼쪽 아래에 경고 22개가 표시되어 있다](/assets/img/android-mastery/p1c04/06b-jadxgui-smali-const-string.png)

CLI에는 Smali 출력이 없지만 `-m fallback`으로 jadx가 구조화하기 전의 명령을 그대로 찍게 할 수 있다. 같은 클래스를 이 모드로 풀자 `Sync.java` 362·363행에 리터럴이 나왔다.

```bash
jadx -q -m fallback --single-class io.seika.jadxlab.Sync -d jfb jadxlab-debug.apk
grep -rn "seika-upl\|X-Upload" jfb
```

```text
jfb/sources/io/seika/jadxlab/Sync.java:362:            java.lang.String r11 = "X-Upload-Token"
jfb/sources/io/seika/jadxlab/Sync.java:363:            java.lang.String r12 = "seika-upl-2c9e41d7"
```

R8 빌드에서도 같은 일이 벌어졌다. `Sync`는 `a.f`가 됐고 `pullAll`과 `fakeFetch`에 해당하는 `a.f.b`와 `a.f.a`가 둘 다 `Method not decompiled`로 바뀌었다. `a.f.b`에는 디버그 빌드처럼 다중 진입 루프 경고가 붙었고 명령 단위는 473이었다. 기본 출력에는 토큰이 없었고 `--show-bad-code`로 다시 풀자 `new b.b("X-Upload-Token", "seika-upl-2c9e41d7")`가 나왔다. 매핑을 보면 `kotlin.TuplesKt`는 지워졌고 `TuplesKt.to`가 `pullAll` 안으로 인라인되어 `kotlin.Pair`(`b.b`)의 생성자를 바로 부르는 꼴이 됐다.

jadx 출력만 grep 했다면 보고서에 "토큰 없음"이라고 적었을 것이다.

## 코루틴 상태 기계가 만든 입구 여럿인 루프

Kotlin 컴파일러는 suspend 함수를 상태 기계로 바꾼다. 중단 지점마다 상태가 하나씩 생기고 재개할 때는 상태 값으로 분기해 멈췄던 자리로 바로 뛰어든다([KEEP coroutines, State machines](https://github.com/Kotlin/KEEP/blob/master/proposals/coroutines.md#state-machines)). `pullAll`처럼 `while` 루프 한가운데 `delay()`가 여러 번 있으면 재개 지점마다 루프 안쪽으로 들어오는 입구가 생긴다. 머리 말고도 입구가 여럿인 루프는 Java의 `while`이나 `for`로 그대로 옮겨 적을 수 없다. jadx가 `pullAll` 머리에 남긴 경고가 바로 그 자리를 가리킨다.

```text
/* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:31:0x011c -> B:32:0x012c). Please report as a decompilation issue!!! */
/* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:53:0x01d6 -> B:32:0x012c). Please report as a decompilation issue!!! */
/* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:65:0x0251 -> B:66:0x025d). Please report as a decompilation issue!!! */
```

jadx가 이런 루프를 알아보는 방식은 [FixMultiEntryLoops.java](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/dex/visitors/blocks/FixMultiEntryLoops.java)에 있다. 블록 그래프를 깊이 우선으로 돌며 되돌아가는 간선(back edge)을 모으고, 루프 머리가 루프 끝을 지배하지 않으면 머리를 거치지 않고 루프 안으로 들어오는 길이 있다는 뜻이니 입구가 여럿인 루프로 친다([90~95행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/dex/visitors/blocks/FixMultiEntryLoops.java#L90-L95)). 그 옆길이 머리 바로 다음 블록이나 루프 끝 블록으로 들어오는 모양이면 블록을 복제해 고치고 다른 모양이면 [43~52행](https://github.com/skylot/jadx/blob/v1.5.5/jadx-core/src/main/java/jadx/core/dex/visitors/blocks/FixMultiEntryLoops.java#L43-L52)에서 이 경고를 남기고 손을 뗀다.

jadx가 구조화하지 못한 메서드가 실제로도 망가진 코드인지 보려고 디버그 APK를 에뮬레이터에 깔고 `MainActivity`를 띄운 뒤 logcat에서 `jadxlab` 태그만 걸러 봤다. `MainActivity`는 `CryptoBox.seal`로 봉인한 세션의 앞 24자와 길이를 남기고, 백그라운드 코루틴에서 `Sync.pullAll(listOf("alpha", "echo", "papa", "delta"), 3)`을 불러 그 결과를 남긴다.

![터미널, 에뮬레이터 실행. adb -s $S install -r jadxlab-debug.apk 가 Success, am start -W -n io.seika.jadxlab/.MainActivity 를 grep 한 결과 Status: ok 와 LaunchState: COLD, sleep 4 뒤 logcat -d -s jadxlab 출력으로 I sealed session: 6FqvDqAoWZyDGdavWv2kwt5v... (108 chars), W retry papa: flaky papa 세 줄, I sync done: {alpha=200, delta=200} 이 찍혀 있다](/assets/img/android-mastery/p1c04/09a-pullall-runs-on-art.png)

`papa`는 문자 코드 합 418에 헤더 개수 2를 더하면 420이고 7의 배수라 매번 예외를 던져 경고를 세 번 남겼다. `echo`는 같은 계산으로 417이 나와 홀수라 429만 세 번 받고 결과에서 빠졌다. `alpha`(520)와 `delta`(524)는 7로 나누어떨어지지 않는 짝수라 첫 시도에 200을 받았다. 소스로 미리 계산해 둔 값과 출력이 그대로 맞는다. jadx가 `Method not decompiled`로 덮어 버린 메서드가 ART 위에서는 재시도와 예외 경로까지 전부 돌았다.

d8의 DEX 변환이 이 실패에 끼어드는지도 궁금했다. 그래서 d8에 들어가기 전의 kotlinc 산출물 `Sync.class`, `Sync$pullAll$1.class`, `Sync$fakeFetch$1.class`를 jadx에 바로 넣었다. 그런데 작은따옴표로 감싸 넘겼는데도 jadx가 `Sync-d.class`라는 없는 파일을 찾다가 멈췄다. PATH에 잡힌 `jadx`가 sh 시작 스크립트라 인자를 한 번 더 해석하면서 `$pullAll`은 빈 문자열, `$1`은 첫 인자 `-d`가 된 것으로 보인다. 클래스 파일을 jar로 묶어 넘기자 이 문제는 사라졌다.

jar로 넘겨도 jadx는 `pullAll`과 `fakeFetch`를 풀지 못했다. `pullAll`은 실패한 이유가 달랐다. DEX에서는 다중 진입 루프 경고 뒤에 포기했고, 클래스 파일에서는 예외 핸들러 연결을 만드는 블록 분할 단계에서 예외로 멈췄다. `fakeFetch`는 두 입력 모두 별다른 경고 없이 실패 표시만 붙었다.

```text
/*  JADX ERROR: JadxRuntimeException in pass: BlockSplitter
    jadx.core.utils.exceptions.JadxRuntimeException: Unexpected missing predecessor for block: B:16:0x00bc
...
        Method dump skipped, instruction units count: 894
```

명령 단위도 DEX의 642와 달리 894였다. 입력 바이트코드 형식이 다르니 세는 단위도 달라진 것으로 보이는데 따져 보지는 않았다.

이 비교가 뜻을 가지려면 jar에 넣은 클래스 파일이 APK 속 `Sync`와 같은 코드여야 한다. 빌드 때와 같은 D8로 다시 변환해 보면 되는데, Gradle 캐시에서 이름에 r8이 들어간 jar를 찾으면 아무것도 나오지 않는다. AGP 8.5.2는 D8과 R8을 `builder-8.5.2.jar` 안에 넣어 두고 있었다. 이 jar를 클래스패스에 넣고 `com.android.tools.r8.D8 --version`을 부르면 `D8 8.5.35`가 찍히고 매핑 파일 머리의 `# compiler_version: 8.5.35`와 같다.

이 D8로 클래스 파일 세 개를 `--debug --min-api 26`으로 다시 DEX로 만들고 APK의 `classes3.dex`와 함께 `dexdump -d`로 풀어 `Sync` 세 클래스만 견줬다. 두 DEX는 문자열·메서드 인덱스 표가 달라 인덱스 번호는 지우고 비교했다. 정규화한 덤프는 양쪽 다 974줄이었고 다른 줄은 메서드 머리의 code_item 파일 오프셋 9줄뿐이었다. 그 오프셋까지 가리자 명령, 레지스터 수(`pullAll` 24개), 분기 대상, try/catch 표, 줄 번호와 지역 변수 정보, 문자열 상수, 호출 대상이 모두 같았다. `pullAll`은 642 코드 유닛으로 jadx가 보고한 값과도 맞는다. 같은 코드를 DEX로 넣어도 클래스 파일로 넣어도 jadx는 풀지 못했다. d8 변환은 이 실패와 상관이 없었다.

내친김에 같은 클래스 파일을 호스트 JVM에서도 돌렸다. `javap -v`로 보니 `Sync.class`가 부르는 Android API는 `android.util.Log.w` 하나뿐이라, `w`만 있는 `Log` 대역과 `MainActivity`와 같은 인자로 `pullAll`을 부르는 `RunSync`를 붙였다. `lib/`의 kotlin-stdlib 1.9.24와 kotlinx-coroutines-core-jvm 1.8.1 jar는 Gradle 캐시에서 복사해 둔 것이다. 경고 세 줄과 `sync done` 줄이 에뮬레이터 logcat과 똑같이 나왔다.

![터미널, 호스트 JVM 실행. ls 로 kc/io/seika/jadxlab 의 Sync$fakeFetch$1.class, Sync$pullAll$1.class, Sync.class 와 lib 의 kotlin-stdlib-1.9.24.jar, kotlinx-coroutines-core-jvm-1.8.1.jar 를 보이고, jar cf sync-classes.jar 뒤 jadx 가 ERROR - finished with errors, count: 1, Sync.java 85행과 99행에 Method not decompiled pullAll 과 fakeFetch. 이어서 Log.java 대역과 RunSync.java 소스, lib 폴더 jar 와 kc 를 클래스패스에 넣은 javac 컴파일, java 로 RunSync 를 돌린 결과로 W jadxlab: retry papa: flaky papa 세 줄과 I jadxlab: sync done: {alpha=200, delta=200} 이 찍혀 있다](/assets/img/android-mastery/p1c04/09-pullall-runs-on-host-jvm.png)

`Log` 대역과 `RunSync`는 아래와 같다.

```java
// stub/android/util/Log.java
package android.util;

public final class Log { // host stand-in for the only Android call in Sync.class
    public static int w(String tag, String msg) {
        System.out.println("W " + tag + ": " + msg);
        return 0;
    }
}

// RunSync.java
import io.seika.jadxlab.Sync;
import java.util.List;
import java.util.Map;
import kotlin.coroutines.EmptyCoroutineContext;
import kotlinx.coroutines.BuildersKt;

// Same call as MainActivity: Sync.pullAll(listOf("alpha","echo","papa","delta"), 3)
public class RunSync {
    public static void main(String[] args) throws Exception {
        Map<String, Integer> r = BuildersKt.<Map<String, Integer>>runBlocking(
                EmptyCoroutineContext.INSTANCE,
                (scope, cont) -> Sync.INSTANCE.pullAll(List.of("alpha", "echo", "papa", "delta"), 3, cont));
        System.out.println("I jadxlab: sync done: " + r);
    }
}
```

캡처의 클래스패스 구분자 `;`는 Windows용 `java`라서 쓴 것이다. 리눅스에서는 아래처럼 `:`로 바꾸면 되고 WSL Ubuntu의 OpenJDK 21.0.12.1에서 같은 파일로 돌렸을 때도 같은 네 줄이 나왔다.

```bash
javac -d out -cp "lib/*:kc" stub/android/util/Log.java RunSync.java
java -cp "out:kc:lib/*" RunSync
```

## 패커를 씌우면 jadx에는 스텁과 암호 덩어리만 남는다

코드가 아예 APK에 Java로 들어 있지 않으면 jadx는 더 할 일이 없다. 그걸 보려고 장난감 패커를 만들었다. 숨길 코드 `io.seika.payload.Hidden`을 d8로 1744바이트 DEX로 만든 뒤 키 `p1c04-stub`으로 XOR 해서 `assets/payload.bin`에 넣고 앱 `io.seika.packed`에는 그걸 풀어 메모리에서 올리는 스텁만 둔다(package·import 줄과 주석은 뺐다).

```java
// payload/src/io/seika/payload/Hidden.java
public final class Hidden {
    private static final String ADMIN_PIN = "PIN-4242-seika";
    private static final String ENDPOINT = "https://api.example.invalid/v2/redeem";

    public static String run(Context ctx) {
        String url = ENDPOINT + "?pkg=" + ctx.getPackageName() + "&pin=" + ADMIN_PIN;
        Log.i("packed", "hidden payload running in " + ctx.getPackageName());
        return "redeem url built (" + url.length() + " chars), class loader = "
                + Hidden.class.getClassLoader().getClass().getSimpleName();
    }
}

// packed/src/io/seika/packed/Loader.java
final class Loader {
    private static final byte[] K = "p1c04-stub".getBytes();

    static String boot(Context ctx) throws Exception {
        byte[] blob = read(ctx.getAssets().open("payload.bin"));
        for (int i = 0; i < blob.length; i++) blob[i] ^= K[i % K.length];
        ClassLoader cl = new InMemoryDexClassLoader(ByteBuffer.wrap(blob), ctx.getClassLoader());
        Class<?> c = cl.loadClass("io.seika.payload.Hidden");
        return (String) c.getMethod("run", Context.class).invoke(null, ctx);
    }

    private static byte[] read(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
        in.close();
        return out.toByteArray();
    }
}
```

![터미널, packed.apk 정적 분석. jadx -q -d jp packed.apk 뒤 find 결과는 AndroidManifest.xml, META-INF 의 ANDROIDD.RSA ANDROIDD.SF MANIFEST.MF, assets/payload.bin, io/seika/packed/Loader.java, MainActivity.java 뿐이다. Loader.java 17행 open(payload.bin), 19행 키 K 와의 XOR, 21행 new InMemoryDexClassLoader(ByteBuffer.wrap(bArr), ...), classes.dex 첫 8바이트 6465 780a 3033 3800 dex.038. 과 payload.bin 첫 8바이트 1454 1b3a 041e 4b74 비교, payload.bin 을 jadx 에 넣으면 WARN - No classes to decompile; decoding resources only](/assets/img/android-mastery/p1c04/07-packed-stub-static.png)

jadx 출력에는 `Loader`와 `MainActivity`, 그리고 리소스로 취급된 `assets/payload.bin`만 있다. `classes.dex`는 `dex\n038\0` 매직으로 시작하는데 `payload.bin`은 `14 54 1b 3a`로 시작하니 DEX로 보이지 않는다. jadx에 직접 넣어도 디컴파일할 클래스가 없다는 경고만 나온다. `Hidden`, `ADMIN_PIN`, `ENDPOINT`는 출력 어디에도 없다. 앞에서 R8 빌드의 키를 찾을 때 쓴 grep은 여기서 아무것도 못 건진다.

이 패커는 장난감이라 키가 스텁에 평문으로 있다. `Loader.java`에서 읽은 키로 호스트에서 `payload.bin`을 XOR 하면 `dex\n038\0`으로 시작하는 파일이 나왔고 빌드가 암호화했던 DEX와 바이트까지 같았다. 이걸 jadx에 넣자 `Hidden.java` 8·9행에 `ADMIN_PIN = "PIN-4242-seika"`와 `ENDPOINT = "https://api.example.invalid/v2/redeem"`가 보였다. 키를 네이티브 코드에서 만들거나 서버에서 받아 오는 패커라면 정적 분석은 여기서 멈춘다.

## 메모리에 올라간 DEX를 다시 떠내기

남은 길은 DEX가 메모리에 놓이는 순간을 잡는 것이다. `InMemoryDexClassLoader`([API 26부터](https://developer.android.com/reference/dalvik/system/InMemoryDexClassLoader))는 파일 시스템에 쓴 적 없는 DEX 버퍼에서 클래스를 올리는 로더다([InMemoryDexClassLoader.java, android-13.0.0_r1](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/InMemoryDexClassLoader.java#23)). ART는 넘겨받은 버퍼마다 `"DEX data"`라는 이름의 익명 매핑을 읽기·쓰기 권한으로 잡고([dalvik_system_DexFile.cc 202~216행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/native/dalvik_system_DexFile.cc#202)) 내용을 복사한 뒤 연다([268~298행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/native/dalvik_system_DexFile.cc#268)). 이 스텁처럼 `ByteBuffer.wrap`으로 배열을 감싸 넘기면 그중 `GetByteArrayRegion`으로 복사하는 갈래를 탄다. 매핑 이름은 앞에 `dalvik-`를 붙여 `PR_SET_VMA`가 정의된 빌드에서 prctl로 단다([mem_map.cc 287~297행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/libartbase/base/mem_map.cc#287)). DEX를 다 열고 나면 그 페이지에서 쓰기 권한을 거둔다([oat_file_manager.cc 456~463행](https://android.googlesource.com/platform/art/+/refs/tags/android-13.0.0_r1/runtime/oat_file_manager.cc#456)).

소스대로라면 생성자를 후킹해 넘어오는 `ByteBuffer`를 파일로 쓰거나, root로 `/proc/<pid>/maps`에서 `dalvik-DEX data` 매핑을 찾아 떠내면 원본 DEX가 나와야 한다. 에뮬레이터에서 둘 다 해 봤다.

[Frida](/posts/android-lab-p1c08-frida-spawn-attach-java-hook/) 스크립트는 `InMemoryDexClassLoader(ByteBuffer, ClassLoader)` 생성자를 바꿔치기해서 버퍼의 position부터 limit까지를 앱의 `files/` 폴더에 쓴 다음 원래 생성자를 부른다. `position()`과 `limit()`는 `java.nio.Buffer`에 정의된 메서드라 `Buffer` 쪽에서 꺼내 부르고 바이트는 위치를 움직이지 않는 `get(int)`로 하나씩 읽어 앱이 쓸 버퍼를 건드리지 않게 했다.

```javascript
// Dump every dex buffer handed to InMemoryDexClassLoader(ByteBuffer, ClassLoader) (API 26+)
// into the app's own files/ dir, then run the original constructor.
// Byte-by-byte absolute get(int): avoids the ambiguous zero-arg array()/duplicate() overloads
// (ByteBuffer vs Buffer) and does not move the caller's buffer position.
Java.perform(() => {
  const IMDCL = Java.use('dalvik.system.InMemoryDexClassLoader');
  const File = Java.use('java.io.File');
  const FOS = Java.use('java.io.FileOutputStream');
  const Buffer = Java.use('java.nio.Buffer'); // position()/limit() live on Buffer; ByteBuffer only exposes the (int) setters
  const dir = '/data/data/io.seika.packed/files';
  const ctor = IMDCL.$init.overload('java.nio.ByteBuffer', 'java.lang.ClassLoader');
  ctor.implementation = function (buf, parent) {
    const pos = Buffer.position.overload().call(buf);
    const lim = Buffer.limit.overload().call(buf);
    const get = buf.get.overload('int');
    const bytes = [];
    for (let i = pos; i < lim; i++) bytes.push(get.call(buf, i));
    File.$new(dir).mkdirs();
    const path = dir + '/dump-' + bytes.length + '.dex';
    const out = FOS.$new(path);
    out.write.overload('[B').call(out, Java.array('byte', bytes));
    out.close();
    console.log('[imdcl] ' + bytes.length + ' bytes -> ' + path);
    return ctor.call(this, buf, parent);
  };
});
```

에뮬레이터는 root 셸로 바꾸고 frida-server 17.17.0을 띄워 둔 상태에서 시작했다. `S`에는 에뮬레이터 시리얼이 들어 있다.

```bash
adb -s $S root
adb -s $S shell "pidof frida-server >/dev/null || /data/local/tmp/frida-server >/dev/null 2>&1 &"
```

`frida -f`로 앱을 새로 띄우게 했다. 프로세스를 멈춘 채 만들고 스크립트를 올린 뒤에 재개하므로, `MainActivity.onCreate`가 `Loader.boot`를 부르기 전에 후킹이 걸려 있다.

![터미널, 에뮬레이터에서 packed.apk 런타임 덤프. adb install -r packed.apk Success, frida -D $S -f io.seika.packed -l ../frida/dump-imdcl.js -q -t 5 가 Spawned io.seika.packed 와 imdcl 1744 bytes -> /data/data/io.seika.packed/files/dump-1744.dex 를 출력하고, logcat packed 태그에 hidden payload running in io.seika.packed 와 payload says: redeem url built (76 chars), class loader = InMemoryDexClassLoader, /proc/pid/maps 에 71e22a728000-71e22a729000 r--p 권한의 anon:dalvik-DEX data 매핑 한 줄, adb pull 로 dump-1744.dex 를 dumped.dex 로 받은 뒤 jadx 출력 jdump/sources/io/seika/payload/Hidden.java 의 8행 ADMIN_PIN = PIN-4242-seika, 9행 ENDPOINT = https://api.example.invalid/v2/redeem](/assets/img/android-mastery/p1c04/08-packed-runtime-dump.png)

Frida는 1744바이트짜리 버퍼 하나를 받아 `dump-1744.dex`로 썼다. logcat에는 숨은 클래스가 돌았다는 줄과, 그 클래스를 올린 로더가 `InMemoryDexClassLoader`라는 줄이 남았다. 76자는 `ENDPOINT`에 패키지 이름과 PIN을 이어 붙인 URL의 길이다. 프로세스의 maps에는 `[anon:dalvik-DEX data]` 매핑이 0x1000 크기로 하나 있었고 권한은 `r--p`였다. 이름 앞에 `dalvik-`가 붙고 쓰기 권한이 빠진 것까지 소스에서 읽은 그대로다. 떠낸 파일을 jadx에 넣자 정적 분석에서는 끝내 보이지 않던 `Hidden.java`가 나왔고 8·9행에 `ADMIN_PIN`과 `ENDPOINT`가 있었다.

Frida 없이 root만으로도 떠낼 수 있는지 보려고 스크립트를 따로 짰다. 아래 `memdex.sh`는 maps에서 `dalvik-DEX data` 매핑을 찾아 `/proc/<pid>/mem`을 `dd`로 페이지 단위로 떠내고 DEX 헤더 0x20 위치에 적힌 `file_size`만큼 잘라 `.dex`로 남긴다. packed 앱을 띄워 둔 채 `memdex.sh $S io.seika.packed memdump`처럼 부른다(`adb root` 상태여야 한다, 머리 주석은 뺐다).

```bash
#!/usr/bin/env bash
set -euo pipefail
S=$1; P=$2; out=$3; mkdir -p "$out"
pid=$(adb -s "$S" shell pidof "$P" </dev/null | tr -d '\r')
[ -n "$pid" ] || { echo "$P not running" >&2; exit 1; }
adb -s "$S" shell "grep 'dalvik-DEX data' /proc/$pid/maps" </dev/null | tr -d '\r' | while read -r range _; do
  s=$((16#${range%-*})); e=$((16#${range#*-}))
  f=/data/local/tmp/memdex-$pid-$(printf %x $s).bin
  adb -s "$S" shell "dd if=/proc/$pid/mem of=$f bs=4096 skip=$((s / 4096)) count=$(((e - s) / 4096)) 2>/dev/null" </dev/null
  adb -s "$S" pull "$f" "$out/" >/dev/null </dev/null
  # trim the page padding back to the size recorded in the dex header (file_size at 0x20)
  python -c "import struct,sys;d=open(sys.argv[1],'rb').read();n=struct.unpack('<I',d[32:36])[0];open(sys.argv[1][:-4]+'.dex','wb').write(d[:n]);print(sys.argv[1][:-4]+'.dex',d[:8],n,'bytes')" "$out/$(basename "$f")"
done
```

이렇게 뜬 4096바이트 페이지는 `dex\n038\0`으로 시작했고 헤더의 `file_size`는 1744였다. Frida로 받은 파일, `/proc/<pid>/mem`에서 떠낸 파일, 그리고 빌드 스크립트가 XOR 하기 전에 남겨 둔 원본 `payload-plain.dex`의 해시를 나란히 놓았다.

```text
f5e7d3cdae8f2a86afbe868c5db4ddeec198e7053e8493eb14c41660efaec489 *payload-plain.dex
f5e7d3cdae8f2a86afbe868c5db4ddeec198e7053e8493eb14c41660efaec489 *dumped.dex
f5e7d3cdae8f2a86afbe868c5db4ddeec198e7053e8493eb14c41660efaec489 *memdump/memdex-5674-71e22a728000.dex
```

두 덤프 모두 암호화 전 원본과 한 바이트도 다르지 않았다. 이 장난감처럼 DEX 전체를 한 번에 로더에 넘기는 패커라면, 키를 어디에 숨기든 이 자리에서 원본이 나온다. 이렇게 동작하지 않는 패커는 이번에 다루지 않았다. 동적 로딩 자체는 [9장](/posts/android-lab-p1c09-classloader-dynamic-loading/)과 [C14](/posts/android-concept-atlas-c14-classloader-reflection/)에서 다룬다. 네이티브 `.so` 안의 코드도 jadx가 디컴파일하는 범위가 아니라서 [21장](/posts/android-lab-p1c21-ghidra-rizin-native/)의 Ghidra와 rizin으로 넘긴다.

## 릴리스 APK에 jadx를 돌려 거는 회귀 게이트

고치는 쪽은 단순하다. safe flavor는 키를 소스에 두지 않고 AndroidKeyStore에서 만들고 WebView에 브리지를 붙이지 않는다(`Bridges.attach`가 아무것도 하지 않는다). 키 관리는 [14장](/posts/android-lab-p1c14-keystore-biometricprompt/)과 [C44](/posts/android-concept-atlas-c44-secure-storage-backup/)에서 자세히 다룬다.

```kotlin
// src/safe/java/io/seika/jadxlab/CryptoBox.kt
object CryptoBox {
    private const val ALIAS = "jadxlab-seal"

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val g = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        g.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return g.generateKey()
    }

    fun seal(plain: String): String {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, key())
        return Base64.encodeToString(c.iv + c.doFinal(plain.toByteArray()), Base64.NO_WRAP)
    }
}
```

safe 릴리스를 jadx로 풀면 키를 다루는 코드가 별도 클래스 없이 `MainActivity.onCreate` 안에 들어 있다. R8이 `CryptoBox` 객체 전체를 호출부로 인라인해서 `onCreate` 중간에 `Cipher.getInstance("AES/GCM/NoPadding")`, `KeyStore.getInstance("AndroidKeyStore")`, `KeyGenerator.getInstance("AES", "AndroidKeyStore")`가 줄지어 나온다. 클래스 이름에 기대는 검사는 R8 빌드에서 쓰기 어렵고 출력 전체에서 문자열을 세는 편이 낫다.

그래서 릴리스 산출물에 jadx를 돌려 sink 문자열이 있는 파일 수를 세는 스크립트를 만들었다. `--show-bad-code`를 쓰는 이유는 앞에서 본 검색 누락 때문이다. 복원에 실패한 메서드 안에 `SecretKeySpec`이 있어도 이 옵션이 없으면 출력에서 사라진다.

```bash
#!/usr/bin/env bash
# usage: check-release.sh APK [APK...]  regression gate over jadx output of release builds.
# --show-bad-code so methods jadx could not restructure are still searched.
for apk in "$@"; do
  d=$(mktemp -d)
  jadx -q --show-bad-code -d "$d" "$apk"
  ks=$(grep -rl 'new SecretKeySpec(' "$d/sources" | wc -l)
  br=$(grep -rl 'addJavascriptInterface(' "$d/sources" | wc -l)
  aks=$(grep -rl '"AndroidKeyStore"' "$d/sources" | wc -l)
  bad=$(grep -r 'Code decompiled incorrectly' "$d/sources" | wc -l)
  v=PASS; [ $((ks + br)) -gt 0 ] && v=FAIL
  printf '%-20s SecretKeySpec=%s addJavascriptInterface=%s AndroidKeyStore=%s inconsistent=%s -> %s\n' \
    "$(basename "$apk")" "$ks" "$br" "$aks" "$bad" "$v"
  rm -rf "$d"
done
```

![터미널, 회귀 게이트 실행. check-release.sh 의 grep 네 줄과 v=PASS 판정 줄을 보인 뒤 ../check-release.sh jadxlab-release.apk jadxlab-safe.apk 결과로 jadxlab-release.apk SecretKeySpec=1 addJavascriptInterface=1 AndroidKeyStore=0 inconsistent=12 -> FAIL, jadxlab-safe.apk SecretKeySpec=0 addJavascriptInterface=0 AndroidKeyStore=1 inconsistent=12 -> PASS 가 찍혀 있다](/assets/img/android-mastery/p1c04/10-regression-gate.png)

vuln 릴리스는 `SecretKeySpec`과 `addJavascriptInterface`가 한 파일씩 걸려 FAIL, safe 릴리스는 둘 다 0이고 `AndroidKeyStore`가 한 파일에 있어 PASS다. 두 빌드 모두 `inconsistent=12`, jadx가 제대로 못 푼 메서드가 12개씩 있었다. 그중 둘은 `Sync`의 두 메서드(vuln 빌드에서는 `a.f`, safe 빌드에서는 `a.e`)이고 나머지는 vuln 빌드 매핑으로 확인하니 전부 `kotlinx.coroutines` 클래스였다. 디버그 빌드에서 200개였던 것이 이만큼 줄어든 건 R8이 쓰지 않는 라이브러리 코드를 걷어 냈기 때문으로 보인다.

이 게이트는 jadx가 볼 수 있는 코드만 센다. 패커처럼 실행해야 나타나는 코드나 네이티브 코드 안의 키는 여기서 0으로 나온다.

참고 자료: [jadx v1.5.5](https://github.com/skylot/jadx/tree/v1.5.5) · [R8 코드 축소·난독화](https://developer.android.com/build/shrink-code) · [d8](https://developer.android.com/tools/d8) · [retrace](https://developer.android.com/tools/retrace) · [KEEP coroutines](https://github.com/Kotlin/KEEP/blob/master/proposals/coroutines.md) · [ART와 DEX(C13)](/posts/android-concept-atlas-c13-art-dex-oat-vdex/) · [ClassLoader와 리플렉션(C14)](/posts/android-concept-atlas-c14-classloader-reflection/) · [안전한 저장소(C44)](/posts/android-concept-atlas-c44-secure-storage-backup/)

*다음 글: [apktool과 smali로 편집·재조립](/posts/android-lab-p1c05-apktool-smali/)*
