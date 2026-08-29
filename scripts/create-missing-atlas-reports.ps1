$ErrorActionPreference = 'Stop'
$postsDir = (Resolve-Path (Join-Path $PSScriptRoot '..\_posts')).Path

$modules = @(
    @{
        id='C01'; date='2026-10-16'; slug='assets-subjects-trust-boundaries'; tier=0; prereq='없음'
        title='자산·주체·신뢰 경계·공격 표면, 보안 분석의 좌표계'
        tags='ThreatModel, Asset, Subject, TrustBoundary, AttackSurface'
        intro='보안 분석은 도구 목록이 아니라 자산, 주체, 경계, 진입점의 관계를 먼저 고정하는 작업입니다. 같은 기능도 무엇을 자산으로 두고 어떤 공격자를 가정하느냐에 따라 위험도가 달라집니다.'
        position='Android에서 앱 데이터와 사용자 자격 증명은 자산이고, 앱 UID·system_server·커널·TEE는 서로 다른 주체이자 신뢰 영역입니다. Binder, 파일, Intent, 소켓, JNI는 경계를 통과하는 입력 채널입니다. 공격 표면은 코드 양이 아니라 신뢰하지 않는 입력이 권한 있는 코드에 닿는 모든 경로의 집합으로 봅니다.'
        flow='자산을 기밀성·무결성·가용성 기준으로 적는다.;공격자 능력을 원격·로컬 앱·셸·커널 등으로 제한한다.;데이터 흐름마다 UID·SELinux·Binder·암호화 경계를 표시한다.;경계를 넘는 입력과 최종 보안 판정을 연결한다.'
        failure='자산이나 공격자 능력을 생략하면 재현된 크래시를 곧바로 취약점으로 오판하거나, 반대로 높은 권한 프로세스의 입력 검증 결함을 단순 오류로 축소할 수 있습니다. 경계마다 누가 값을 만들고 누가 검증하는지 기록해야 합니다.'
        commands='adb -s emulator-5580 shell id`nadb -s emulator-5580 shell getenforce`nadb -s emulator-5580 shell cat /proc/self/status'
        observed='셸 주체와 앱 주체가 서로 다른 UID·SELinux 컨텍스트를 갖고, 증거 앱은 untrusted_app과 CapEff=0, Seccomp=2로 실행됐습니다. 이 결과를 이후 모든 모듈의 기본 공격자 모델로 사용합니다.'
        limit='에뮬레이터 모델은 실제 사용자의 자산 가치나 조직의 서버 신뢰 경계를 대신하지 않습니다. 보고서마다 자산과 공격자 능력을 다시 선언해야 합니다.'
        image='evidence-environment.png'
        refs='- [Android platform security architecture](https://source.android.com/docs/security/overview)`n- [Android security implementation guidance](https://source.android.com/docs/security/overview/implement)'
        conclusion='무엇을 지키는지, 누가 접근하는지, 어디서 신뢰가 바뀌는지를 먼저 적으면 나머지 55개 개념이 같은 좌표계에 놓입니다.'
    },
    @{
        id='C07'; date='2026-10-17'; slug='dex-multidex-resources-arsc'; tier=1; prereq='C06'
        title='DEX·multidex·resources.arsc, APK 안에서 코드와 리소스가 만나는 법'
        tags='DEX, Multidex, ResourcesARSC, APKAnalyzer, ReverseEngineering'
        intro='APK는 단일 코드 파일이 아닙니다. classes.dex 계열은 실행 코드와 타입 정보를, resources.arsc는 컴파일된 리소스 테이블을, Manifest는 컴포넌트와 권한 메타데이터를 담습니다. 분석 도구의 출력이 어느 파일에서 왔는지 구분해야 오판을 줄일 수 있습니다.'
        position='빌드 시 javac/Kotlin 컴파일러의 바이트코드가 D8/R8을 거쳐 DEX가 되고, aapt2가 Manifest와 리소스를 패키징합니다. 메서드 참조 한계를 넘거나 분할이 필요하면 classes2.dex 같은 보조 DEX가 생기며 런타임의 클래스 로더가 이를 함께 다룹니다.'
        flow='소스와 의존성을 JVM 바이트코드로 컴파일한다.;D8/R8이 검증 가능한 DEX 명령과 테이블로 변환한다.;aapt 계열 도구가 Manifest·리소스·DEX·네이티브 라이브러리를 APK에 묶는다.;Package Manager와 ART가 설치·검증·로드한다.'
        failure='정적 분석에서 첫 DEX만 보거나 리소스 ID를 문자열처럼 해석하면 숨은 컴포넌트와 동적 참조를 놓칩니다. 반대로 APK에 문자열이 존재한다는 이유만으로 실행 가능 경로라고 단정해서도 안 됩니다.'
        commands='apkanalyzer files list atlas-evidence.apk`napkanalyzer dex packages atlas-evidence.apk`naapt dump badging atlas-evidence.apk'
        observed='직접 만든 APK에는 AndroidManifest.xml, classes.dex, lib/x86_64/libatlasevidence.so가 들어갔고, dex packages 출력에서 MainActivity와 참조 API 테이블을 확인했습니다. 앱 내부에서도 자신의 APK ZIP 항목을 다시 읽어 같은 결과를 표시했습니다.'
        limit='이 표본은 단일 DEX 소형 APK입니다. multidex와 AAB split 생성은 별도 대형 표본 또는 bundletool 환경에서 추가 검증해야 합니다.'
        image='evidence-package.png'
        refs='- [AOSP DEX format](https://source.android.com/docs/core/runtime/dex-format)`n- [AOSP DEX constraints](https://source.android.com/docs/core/runtime/constraints)'
        conclusion='DEX, 리소스, Manifest를 별도 증거원으로 읽고 마지막에 합쳐야 설치 구조와 실제 실행 경로를 혼동하지 않습니다.'
    },
    @{
        id='C15'; date='2026-10-18'; slug='jni-native-library-loading'; tier=2; prereq='C13, C33'
        title='JNI 경계·네이티브 라이브러리 로딩, 관리 코드와 C/C++ 사이의 계약'
        tags='JNI, NDK, NativeLibrary, Linker, ABI'
        intro='JNI는 Kotlin/Java와 C/C++ 사이의 호출 규약입니다. 객체 수명, 스레드별 JNIEnv, 예외 처리, 배열 길이와 문자 인코딩을 잘못 다루면 관리 런타임의 안전성이 네이티브 메모리 오류로 바뀝니다.'
        position='System.loadLibrary가 ABI에 맞는 .so를 동적 링커로 적재하고, 이름 기반 심볼 또는 RegisterNatives가 Java 선언과 네이티브 함수를 연결합니다. JNIEnv는 현재 스레드의 JNI 함수 테이블이며 다른 스레드에 그대로 보관해 재사용하면 안 됩니다.'
        flow='NDK clang이 목표 ABI용 ELF 공유 라이브러리를 만든다.;APK의 lib/ABI 디렉터리에 라이브러리를 넣는다.;Package Manager가 ABI에 맞는 파일을 설치한다.;System.loadLibrary와 JNI 바인딩 후 값을 왕복한다.'
        failure='길이·부호·소유권 계약이 양쪽에서 다르면 OOB, UAF, 로컬 참조 누수, 잘못된 스레드 사용이 됩니다. 라이브러리 경로와 ABI가 틀리면 코드 실행 전 UnsatisfiedLinkError로 종료됩니다.'
        commands='./build.ps1`nadb -s emulator-5580 install -r build/atlas-evidence.apk`nadb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section jni'
        observed='NDK 27.3으로 x86_64 .so를 RELRO/BIND_NOW/noexecstack 옵션과 함께 빌드했습니다. 표준 APK 경로로 수정한 뒤 Java→JNI→native→Java 왕복, JNIEnv non-null, 64-bit 포인터가 모두 PASS였습니다.'
        limit='이 결과는 x86_64 AVD의 ABI 계약을 검증합니다. ARM64 PAC/BTI와 벤더 라이브러리 로딩 동작은 별도 ARM64 가상 이미지나 공개 빌드 산출물이 필요합니다.'
        image='evidence-jni.png'
        refs='- [Android JNI tips](https://developer.android.com/ndk/guides/jni-tips)`n- [Android NDK concepts](https://developer.android.com/ndk/guides/concepts)'
        conclusion='JNI는 단순 함수 호출이 아니라 런타임·링커·ABI·메모리 수명 계약이 만나는 신뢰 경계입니다.'
    },
    @{
        id='C18'; date='2026-10-19'; slug='parcel-serialization-contract'; tier=3; prereq='C17'
        title='Parcel 직렬화 계약, write/read 순서가 어긋날 때 생기는 일'
        tags='Binder, Parcel, Serialization, AIDL, TypeConfusion'
        intro='Parcel은 Binder 경계를 넘는 바이트 컨테이너입니다. 송신자와 수신자가 필드 순서·타입·nullable 규칙을 동일하게 이해해야 하며, 한 칸의 불일치가 이후 모든 필드의 해석을 밀어낼 수 있습니다.'
        position='AIDL이 생성한 Stub/Proxy는 인터페이스 토큰과 인자를 정해진 순서로 쓰고 읽습니다. 수동 Parcel 코드나 버전이 다른 구현이 이 계약을 깨면 값 손실, 예외, 논리 타입 혼동이 생깁니다.'
        flow='송신자가 int와 String을 순서대로 기록한다.;dataPosition을 처음으로 돌린다.;수신자가 같은 타입·순서로 읽어 원본을 복원한다.;다른 타입으로 읽는 대조군과 결과를 비교한다.'
        failure='파서가 남은 크기와 타입을 검증하지 않거나 실패 뒤에도 진행하면 잘못된 길이와 객체가 권한 판정에 들어갈 수 있습니다. 단순 null이나 예외가 곧 취약점은 아니며, 공격자가 입력을 제어하고 보안 영향까지 이어져야 합니다.'
        commands='adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section parcel'
        observed='대칭 순서는 int 0x11223344와 문자열 atlas를 정확히 복원했습니다. 같은 버퍼를 String부터 읽은 불일치 대조군은 예외 대신 null을 돌려줬습니다. 즉 모든 mismatch가 명시적 크래시가 되는 것은 아닙니다.'
        limit='로컬 Parcel은 커널 Binder 전송과 원격 호출자 UID를 포함하지 않습니다. 실제 서비스 분석에서는 Stub의 enforceInterface와 길이 검사까지 함께 확인해야 합니다.'
        image='evidence-parcel.png'
        refs='- [Android Parcel API](https://developer.android.com/reference/android/os/Parcel)`n- [Android Binder overview](https://source.android.com/docs/core/architecture/ipc/binder-overview)'
        conclusion='직렬화는 형식보다 계약입니다. 정상 대조군과 불일치 대조군을 같이 두어야 조용한 값 손실과 명시적 거부를 구분할 수 있습니다.'
    },
    @{
        id='C22'; date='2026-10-20'; slug='binder-caller-identity-confused-deputy'; tier=3; prereq='C17, C19'
        title='Binder 호출자 UID·identity clearing·confused deputy'
        tags='Binder, CallingUID, ClearCallingIdentity, ConfusedDeputy, Authorization'
        intro='Binder 서비스는 요청 내용뿐 아니라 누가 호출했는지를 함께 판정해야 합니다. getCallingUid를 너무 늦게 읽거나 clearCallingIdentity 뒤의 자기 UID를 원래 호출자로 착각하면 confused deputy가 됩니다.'
        position='커널 Binder 드라이버가 트랜잭션 메타데이터에 호출자 PID/UID를 붙이고, 서비스 스레드는 Binder API로 이를 읽습니다. clearCallingIdentity는 중첩 호출에서 서비스 자신의 권한으로 작업할 때 쓰며 반환 토큰을 finally에서 반드시 복원해야 합니다.'
        flow='진입 직후 calling UID를 캡처한다.;그 UID에 대해 권한·소유권을 판정한다.;필요한 최소 구간에서만 identity를 clear한다.;finally에서 원래 identity를 복원한다.'
        failure='clear 뒤에 권한 검사를 수행하면 공격자의 요청이 서비스 UID 권한으로 승인될 수 있습니다. 호출자 UID와 데이터 내부의 userId를 같은 신원으로 믿는 것도 위험합니다.'
        commands='adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section identity'
        observed='수신 트랜잭션이 없는 앱 내부 대조군에서 process UID와 calling UID는 모두 10174였고, clear/restore 뒤에도 같은 값으로 복원돼 lifecycle이 PASS했습니다.'
        limit='이 대조군은 원격 Binder 호출이 없어 공격자 UID 전환을 증명하지 않습니다. 실제 서비스에서는 별도 클라이언트 프로세스와 instrumented Stub이 필요합니다.'
        image='evidence-identity.png'
        refs='- [android.os.Binder API](https://developer.android.com/reference/android/os/Binder)`n- [AOSP Binder overview](https://source.android.com/docs/core/architecture/ipc/binder-overview)'
        conclusion='호출자 identity는 데이터가 아니라 커널이 전달한 보안 문맥이며, clear 구간은 짧고 복원은 예외 안전해야 합니다.'
    },
    @{
        id='C26'; date='2026-10-21'; slug='uid-sandbox-vs-selinux'; tier=4; prereq='C09, C23, C24'
        title='UID 샌드박스와 SELinux, 서로 다른 두 겹의 역할'
        tags='Sandbox, UID, SELinux, DAC, MAC, Seccomp'
        intro='Android 앱 격리는 하나의 기능이 아닙니다. Linux UID/DAC는 소유권 기반 1차 경계이고, SELinux/MAC는 주체·객체 라벨과 정책에 따른 추가 경계입니다. seccomp와 capability는 시스템 콜과 커널 권한을 더 줄입니다.'
        position='앱 설치 시 Package Manager가 UID와 데이터 디렉터리를 배정하고, Zygote가 해당 UID·GID로 프로세스를 시작합니다. SELinux는 untrusted_app 도메인과 app_data_file 타입 사이의 allow 규칙을 별도로 판단합니다.'
        flow='고유 UID가 파일 소유권을 분리한다.;SELinux 도메인이 허용된 객체·행위를 제한한다.;capability를 비우고 seccomp가 syscall 집합을 줄인다.;Binder와 컴포넌트 계층이 명시적 공유 경로를 제공한다.'
        failure='같은 UID 공유, 지나치게 넓은 allow, permissive 도메인, 과도한 capability 중 하나만 있어도 폭발 반경이 커집니다. 두 겹이 같은 EL1 커널에 의존하므로 커널 장악에는 함께 무너질 수 있다는 한계도 있습니다.'
        commands='adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section sandbox'
        observed='앱은 UID 10174, SELinux untrusted_app, 데이터 타입 app_data_file, CapEff=0, Seccomp=2로 실행됐습니다. 한 화면에서 네 통제가 서로 다른 필드로 나타났습니다.'
        limit='하나의 앱만으로 앱 간 파일 접근 대조군까지 만들지는 않았습니다. 다만 각 통제의 활성 상태와 앱 데이터 라벨은 실제 프로세스에서 확인했습니다.'
        image='evidence-sandbox.png'
        refs='- [Android application sandbox](https://source.android.com/docs/security/app-sandbox)`n- [SELinux in Android](https://source.android.com/docs/security/features/selinux)'
        conclusion='UID와 SELinux를 같은 말로 쓰지 말고 소유권 경계와 정책 경계로 나누면 우회 조건과 방어 범위를 정확히 설명할 수 있습니다.'
    },
    @{
        id='C47'; date='2026-10-22'; slug='webview-deeplink-ipc-attack-surface'; tier=8; prereq='C11, C21, C46'
        title='WebView·딥링크·IPC 공격면, URI를 권한 있는 행동으로 바꾸기 전의 검증'
        tags='WebView, DeepLink, URI, AppLinks, IPC'
        intro='딥링크와 WebView는 웹의 문자열을 앱 내부 탐색·인증·파일·IPC 동작으로 바꾸는 경계입니다. 문자열 startsWith 검사는 URL 문법을 이해하지 못하므로 scheme과 정확한 host를 파싱한 뒤 허용해야 합니다.'
        position='외부 Intent가 exported 컴포넌트에 도착하고, 앱은 Uri를 파싱해 내부 라우트 또는 WebView로 전달합니다. 인증 상태와 객체 소유권 검사는 링크 검증과 별개이며 둘 다 통과해야 합니다.'
        flow='Uri.parse로 구조를 분리한다.;https 같은 허용 scheme을 확인한다.;정확한 host 또는 검증된 하위 도메인을 비교한다.;인증·인가·내부 라우트 allowlist를 통과한 뒤에만 실행한다.'
        failure='example.com.evil.test를 suffix/contains로 허용하거나 javascript·content scheme을 놓치면 피싱, 세션 악용, 로컬 파일 노출, JavaScript bridge 오용으로 이어질 수 있습니다.'
        commands='adb -s emulator-5580 shell am start -n com.example.atlasreport/.MainActivity --es section uri'
        observed='https://example.com/account만 ALLOW됐고 http, example.com.evil.test, javascript scheme은 모두 DENY됐습니다. 네 테스트의 기대 결과가 일치해 result=PASS였습니다.'
        limit='교육용 allowlist 검사이며 실제 WebView를 외부 사이트에 연결하거나 JavaScript bridge를 노출하지 않았습니다. 운영 앱은 App Links 검증과 서버 리다이렉트 정책도 확인해야 합니다.'
        image='evidence-uri.png'
        refs='- [Unsafe use of deep links](https://developer.android.com/privacy-and-security/risks/unsafe-use-of-deeplinks)`n- [WebView unsafe URI loading](https://developer.android.com/privacy-and-security/risks/unsafe-uri-loading)'
        conclusion='URI는 문자열이 아니라 구조화된 비신뢰 입력입니다. scheme·host·상태·권한을 독립적으로 확인한 뒤 행동으로 바꿔야 합니다.'
    },
    @{
        id='C51'; date='2026-10-23'; slug='crash-bug-vulnerability-exploit'; tier=9; prereq='C01'
        title='crash·bug·vulnerability·exploit, 재현 결과의 의미를 단계별로 구분하기'
        tags='Crash, Bug, Vulnerability, Exploit, UBSan'
        intro='크래시는 관측, 버그는 원인, 취약점은 보안 정책을 깨는 도달 가능한 결함, 익스플로잇은 그 결함을 의도한 보안 영향으로 전환하는 수단입니다. 네 단계를 섞으면 연구 결과가 과장됩니다.'
        position='동일한 signed overflow도 입력이 신뢰되거나 실패가 안전하게 종료되면 보안 영향이 없을 수 있습니다. 공격자가 값을 제어하고, 권한 있는 문맥에서 메모리·정책 위반으로 이어지며, 완화책을 고려해도 의미 있는 영향이 있어야 취약점 판정에 가까워집니다.'
        flow='재현 가능한 이상 동작을 기록한다.;최소 입력과 원인 코드를 분리한다.;공격자 제어·도달성·권한·영향을 확인한다.;완화와 신뢰 경계를 포함해 exploit 가능성을 별도 평가한다.'
        failure='크래시 한 번을 RCE로 부르거나 sanitizer 메시지만으로 CVE급 취약점이라 단정하는 것이 대표적 오판입니다. 반대로 무크래시 논리 버그도 인가를 우회하면 심각할 수 있습니다.'
        commands='./build-and-run-ubsan.ps1`n./run-matrix.ps1'
        observed='정상 입력은 42를 출력했고 overflow 입력은 UBSan이 signed integer overflow로 중단했습니다. 이 결과는 bug를 증명하지만, 실제 제품 자산이나 공격 경로가 없으므로 exploit 또는 CVE를 주장하지 않습니다.'
        limit='의도적으로 작은 교육용 하네스이며 실제 Android 구성요소 취약점이 아닙니다. 안전한 분류 연습을 위한 대조군입니다.'
        image='evidence-kernel.png'
        refs='- [MITRE CWE vulnerability theory](https://cwe.mitre.org/documents/vulnerability_theory/intro.html)`n- [Android security implementation guidance](https://source.android.com/docs/security/overview/implement)'
        conclusion='관측→원인→보안 영향→악용 가능성을 한 단계씩 증명해야 연구 보고서의 주장이 증거보다 앞서가지 않습니다.'
    },
    @{
        id='C52'; date='2026-10-24'; slug='cwe-cve-security-bulletin-reading'; tier=9; prereq='C51'
        title='CWE·CVE·Android Security Bulletin, 서로 다른 식별 체계를 읽는 법'
        tags='CWE, CVE, AndroidSecurityBulletin, PatchLevel, VulnerabilityResearch'
        intro='CWE는 약점 유형의 분류, CVE는 특정 제품 취약점 기록의 식별자, Android Security Bulletin은 패치 수준·영향 구성요소·심각도·수정 버전을 운영 관점에서 묶은 문서입니다.'
        position='한 CVE는 하나 이상의 CWE 원인을 가질 수 있고, Bulletin 한 항목은 플랫폼·커널·SoC 출처와 패치 수준에 연결됩니다. CVE 번호만으로 영향 버전이나 실제 기기 패치 여부를 판단할 수 없습니다.'
        flow='Bulletin 날짜와 security patch level을 구분한다.;CVE 행에서 구성요소·유형·심각도·수정 버전을 읽는다.;연결된 AOSP 변경과 부모 커밋을 확인한다.;CWE는 근본 약점 설명과 테스트 설계에 사용한다.'
        failure='게시 날짜를 패치 수준으로 오해하거나, CVE 존재를 모든 Android 기기의 취약 상태로 일반화하거나, CWE를 실제 취약점 ID처럼 쓰면 범위가 틀어집니다.'
        commands='curl -L https://source.android.com/docs/security/bulletin/2025-02-01`nrg -o "CVE-[0-9]{4}-[0-9]+" bulletin.html | sort -u'
        observed='공식 2025-02 Bulletin은 HTTP 200으로 내려받았고, 중복 제거한 CVE 식별자 46개를 추출했습니다. 이 숫자는 HTML에서의 식별자 수일 뿐 영향 기기 수나 취약점 심각도 합계가 아닙니다.'
        limit='벤더 비공개 이슈와 아직 공개되지 않은 패치는 Bulletin만으로 알 수 없습니다. 연구 시점에 공개된 원문과 변경 이력을 기준으로 범위를 적습니다.'
        image='evidence-environment.png'
        refs='- [Android Security Bulletins](https://source.android.com/docs/security/bulletin)`n- [Android February 2025 Bulletin](https://source.android.com/docs/security/bulletin/2025-02-01)`n- [MITRE CWE FAQ](https://cwe.mitre.org/about/faq.html)'
        conclusion='CWE는 원인의 언어, CVE는 사례의 ID, Bulletin은 패치 운영 문서입니다. 셋을 연결하되 서로 대신 쓰지 않습니다.'
    },
    @{
        id='C53'; date='2026-10-25'; slug='patch-diff-variant-analysis'; tier=9; prereq='C51, C52'
        title='patch diff·variant analysis, 수정 한 줄에서 보안 불변식을 복원하기'
        tags='PatchDiff, VariantAnalysis, RootCause, IntegerOverflow, UBSan'
        intro='패치 diff의 목적은 바뀐 줄을 외우는 것이 아니라 수정이 복원한 불변식을 찾는 것입니다. 그 불변식을 같은 코드베이스의 유사 함수와 다른 브랜치에 적용하면 variant analysis가 됩니다.'
        position='길이 검사의 before 버전은 offset+length를 먼저 계산해 overflow가 가능했고, after 버전은 offset과 length를 각각 검증한 뒤 length <= total-offset을 사용했습니다. 수정의 핵심은 덧셈 결과가 표현 가능하다고 가정하지 않는 것입니다.'
        flow='변경 전·후를 같은 컴파일 옵션으로 빌드한다.;정상·경계·범위 초과·overflow 입력을 양쪽에 동일 적용한다.;결과와 sanitizer 신호를 행렬로 비교한다.;복원된 불변식으로 유사 코드를 검색한다.'
        failure='패치의 상수나 함수 이름만 검색하면 다른 표현의 같은 원인을 놓칩니다. 반대로 문법이 비슷하다는 이유만으로 variant라 단정하면 실제 데이터 범위와 호출 문맥을 놓칩니다.'
        commands='./run-matrix.ps1`n# normal, boundary, range-error, overflow를 before/after에 동일 적용'
        observed='세 정상·경계 대조군에서 before/after 판정이 같았고, overflow에서 before는 UBSan exit 134, after는 안전한 REJECT exit 1이었습니다. 수정이 정상 기능을 유지하면서 undefined behavior만 제거했습니다.'
        limit='교육용 정수 검사 한 쌍이므로 실제 AOSP 패치의 동시성·수명·권한 문맥까지 대표하지 않습니다. 실제 variant 검색은 호출 그래프와 타입 범위를 추가해야 합니다.'
        image='evidence-kernel.png'
        refs='- [Android security implementation guidance](https://source.android.com/docs/security/overview/implement)`n- [MITRE CWE theory: chains and weaknesses](https://cwe.mitre.org/documents/vulnerability_theory/intro.html)'
        conclusion='좋은 patch diff는 변경 줄이 아니라 깨졌던 불변식, 대조군, 회귀 여부를 설명합니다.'
    },
    @{
        id='C54'; date='2026-10-26'; slug='reproducibility-control-design'; tier=9; prereq='C51, C53'
        title='재현성·대조군 설계, 한 번의 현상을 검증 가능한 결과로 바꾸기'
        tags='Reproducibility, ControlGroup, TestMatrix, Evidence, SHA256'
        intro='재현성은 명령을 다시 실행할 수 있다는 뜻을 넘어, 입력·환경·버전·예상 결과가 고정되고 대조군이 원인 가설을 구분하는 상태를 말합니다.'
        position='Android 보안 실험에서는 API 레벨, ABI, 빌드 지문, 패치 수준, 앱 UID, sanitizer 옵션이 모두 결과에 영향을 줍니다. 양성 대조군과 음성 대조군 없이 한 크래시만 남기면 환경 문제와 보안 결함을 구분하기 어렵습니다.'
        flow='환경 지문과 의존성 버전을 기록한다.;정상·경계·오류·공격 가설 입력을 표로 고정한다.;같은 스크립트를 독립적으로 두 번 실행한다.;정규화된 출력의 해시와 차이를 비교한다.'
        failure='스냅샷 상태, 랜덤 값, 시간, 네트워크 응답을 통제하지 않으면 재현 실패를 패치 효과로 오판할 수 있습니다. 실패 코드도 예상 결과라면 테스트 성공 조건에 명시해야 합니다.'
        commands='$run1 = ./run-matrix.ps1 | Out-String`n$run2 = ./run-matrix.ps1 | Out-String`nSHA256(run1) == SHA256(run2)'
        observed='동일 행렬을 두 번 실행한 출력 SHA-256이 모두 3aa7fd993937c3d27bfd23f5b1f60887152c2a6bcc5707ecc0db617b41a31721로 일치했습니다. 정상·경계·범위오류·overflow 네 대조군도 예상 판정과 일치했습니다.'
        limit='네트워크·스케줄링·주소값처럼 본질적으로 변하는 출력은 정규화 규칙을 별도 정의해야 합니다. 이번 하네스는 결정적 정수 검사만 다룹니다.'
        image='evidence-environment.png'
        refs='- [Android security testing guidance](https://source.android.com/docs/security/overview/implement)`n- [AOSP security reports](https://source.android.com/docs/security/overview/reports)'
        conclusion='재현 스크립트, 대조군 행렬, 종료 코드, 동일 출력 해시가 함께 있을 때 결과가 개인의 관찰에서 검증 가능한 기록으로 바뀝니다.'
    },
    @{
        id='C55'; date='2026-10-27'; slug='threat-model-impact-assessment'; tier=9; prereq='C01, C51, C54'
        title='위협 모델·실제 영향 산정, 기술적 결함을 위험도로 번역하기'
        tags='ThreatModel, Impact, Severity, Exploitability, RiskAssessment'
        intro='심각도는 크래시 모양이 아니라 공격자 능력, 도달성, 필요한 상호작용, 대상 권한, 자산 영향, 완화책을 함께 평가한 결과입니다. 같은 코드 결함도 실행 문맥이 달라지면 위험도가 달라집니다.'
        position='앱 sandbox 내부 로컬 파서, exported 고권한 서비스, 커널 드라이버, TEE는 각각 다른 신뢰 경계와 TCB를 갖습니다. 보고서는 어디서 실행되는지와 공격자가 어떤 입력을 제어하는지를 먼저 적어야 합니다.'
        flow='공격자 시작 권한과 접근 채널을 선언한다.;취약 코드의 프로세스·UID·SELinux·EL을 확인한다.;기밀성·무결성·가용성 영향을 분리한다.;완화와 사용자 상호작용을 반영해 현실적 최악 영향을 적는다.'
        failure='개발자 옵션·부트로더 unlock·물리 접근이 필요한 재현을 일반 원격 공격처럼 쓰거나, 커널 크래시를 자동으로 코드 실행이라 부르면 위험도가 부풀려집니다. 반대로 권한 있는 confused deputy는 크래시가 없어도 중요합니다.'
        commands='adb shell id`nadb shell getenforce`n./run-matrix.ps1`n# 결과를 공격자·권한·자산 표에 매핑'
        observed='교육용 overflow는 AVD 임시 실행 파일에서만 발생했고 보호 자산·권한 상승·지속성이 없었습니다. 따라서 확인한 것은 CWE 유형의 bug와 수정 효과이며, 실제 제품 vulnerability나 exploit 영향은 0으로 판정했습니다.'
        limit='실제 제품 위험도는 벤더 구성, 패치 수준, 배포 범위, 탐지 상태에 따라 달라집니다. 이 글의 결론은 교육용 하네스에만 적용됩니다.'
        image='evidence-sandbox.png'
        refs='- [Android security severity guidance](https://source.android.com/docs/security/overview/updates-resources)`n- [MITRE CWE glossary](https://cwe.mitre.org/documents/glossary/index)'
        conclusion='좋은 영향 산정은 기술적 가능성과 현실적 조건을 분리하고, 증명한 범위까지만 주장합니다.'
    }
)

foreach ($m in $modules) {
    $steps = ($m.flow -split ';' | ForEach-Object -Begin { $n = 1 } -Process { "$n. $_"; $n++ }) -join "`n"
    $body = @"
---
layout: post
title: "Android Security Concept Atlas $($m.id) | 가상 실습 보고서 — $($m.title)"
date: $($m.date) 21:00:00 +0900
category: Android
author: WTCY
series: Android Security Concept Atlas
document_type: virtual-lab-report
verification_date: 2026-08-29
tags: [Android, AndroidSecurity, 모바일보안, ConceptAtlas, $($m.id), $($m.tags)]
excerpt: "$($m.intro)"
---

> **가상 환경 전용**: 이 글은 전용 Android Emulator와 저장소의 교육용 하네스에서만 검증했습니다. 실물 기기, rooting, bootloader unlock, flashing, 타인 시스템은 사용하지 않았습니다. 하드웨어 전용 속성은 공개 문헌과 가상 환경 한계로 분리합니다.

> **Concept Atlas 모듈**: $($m.id) · **Tier $($m.tier)** · **선수 개념**: $($m.prereq)
> **문서 상태**: 개념 설명 + 실제 실행 결과 + 한계가 포함된 가상 실습 보고서

## 실행 요약

| 항목 | 결과 |
|---|---|
| 실행 환경 | Android 13/API 33 Google APIs x86_64, 전용 codex-atlas-api33 AVD |
| 실물 기기 | 사용하지 않음 |
| 핵심 관측 | $($m.observed) |
| 최종 판정 | 가상 환경 범위에서 PASS. 지원되지 않는 하드웨어 성질은 별도 LIMIT로 기록 |

![$($m.id) 실제 가상 실습 화면](/assets/img/android-concept-atlas/verified-api33/$($m.image))

## 1. 왜 이 개념이 필요한가

$($m.intro)

## 2. Android 구조에서의 위치와 신뢰 경계

$($m.position)

## 3. 정상 동작 흐름

$steps

## 4. 실패가 보안 문제로 이어지는 조건

$($m.failure)

중요한 판정 원칙은 **오류가 보였다는 사실**과 **보안 경계가 깨졌다는 결론**을 분리하는 것입니다. 공격자가 입력을 통제하는지, 보호 자산까지 도달하는지, 실행 권한과 완화책은 무엇인지가 함께 확인돼야 합니다.

## 5. 실제 가상 실습

다음 명령 또는 코드를 실제로 실행했습니다.

~~~text
$($m.commands -replace '`n', "`n")
~~~

### 관측 결과

$($m.observed)

### 해석

이 결과는 명령이 실행됐다는 증거와 보안 의미를 함께 기록합니다. 종료 코드 0은 정상 성공이고, 설계상 거부되어야 하는 입력의 비영 종료는 예상 결과로 취급합니다. 결과 전체는 [공통 API 33 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), [호스트 빌드 로그](/assets/evidence/android-concept-atlas/host-verification.md), [패치 diff 행렬](/assets/evidence/android-concept-atlas/patch-diff-matrix.md)에 보존했습니다.

## 6. 검증 범위와 한계

$($m.limit)

| 판정 | 의미 |
|---|---|
| PASS | 명령·코드가 AVD에서 기대 결과와 함께 실행됨 |
| EXPECTED DENY | Android 격리 때문에 접근이 거부됐고 이것이 대조군의 기대 결과임 |
| LIMIT | AVD에 실제 보안 칩·벤더 하드웨어·운영 서버가 없어 주장하지 않음 |

## 7. 공식 소스에서 더 확인할 곳

$($m.refs -replace '`n', "`n")

기술 문헌의 설명과 이번 한 번의 관측이 다를 때는 적용 버전·ABI·빌드 구성을 먼저 비교합니다. x86_64 AVD 결과를 ARM64 물리 단말의 하드웨어 보장으로 일반화하지 않습니다.

## 8. 결론

$($m.conclusion)
"@
    $file = Join-Path $postsDir "$($m.date)-android-concept-atlas-$($m.id.ToLower())-$($m.slug).md"
    [IO.File]::WriteAllText($file, $body, [Text.UTF8Encoding]::new($false))
    Write-Output (Split-Path $file -Leaf)
}
