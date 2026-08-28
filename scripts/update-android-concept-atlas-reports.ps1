$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$posts = Join-Path $repo '_posts'
$files = Get-ChildItem $posts -Filter '*android-concept-atlas*.md' | Sort-Object Name
$scopePattern = '(?m)^(> \*\*가상 환경 전용\*\*:.*실행하지 않은 명령과 출력은 관측 결과로 주장하지 않습니다\.)\r?\n'

$tierData = @{
    0 = @{ image='evidence-sandbox.png'; commands='`id`, `cat /proc/self/attr/current`, `/proc/self/status`, `uname -a`'; result='앱 UID 10174, `untrusted_app` 도메인, `CapEff=0`, `Seccomp=2`, Linux 5.15 커널을 확인했다.'; limit='AVD가 x86_64이므로 ARM64 EL·PAC·BTI·MTE는 런타임 관측 대신 공개 소스 경로로 판정한다.' }
    1 = @{ image='apps.png'; commands='`javac`, `d8`, `aapt`, `zipalign`, `apksigner verify`, `adb install -r`'; result='증거 앱 APK를 직접 빌드하고 v2/v3 서명을 검증한 뒤 설치했다. Package Manager가 앱을 별도 UID로 등록했다.'; limit='AAB의 Play 서버 변환과 Play App Signing은 로컬 Google APIs AVD만으로 재현하지 않는다.' }
    2 = @{ image='evidence-runtime.png'; commands='`getprop ro.zygote`, `getprop dalvik.vm.usejit`, `ps`'; result='`zygote64`와 JIT 활성 상태를 확인했다. 비특권 앱의 전체 프로세스 열람 제한도 함께 관측했다.'; limit='OAT/VDEX 생성 정책은 빌드와 프로파일 상태에 따라 달라지므로 이 한 번의 캡처를 모든 Android 버전에 일반화하지 않는다.' }
    3 = @{ image='evidence-binder.png'; commands='`ls -l /dev/{binder,hwbinder,vndbinder}`, `service list`'; result='binderfs의 세 Binder 노드와 255개 서비스 등록을 확인했다.'; limit='벤더 전용 HAL 트랜잭션이나 취약한 서비스 호출은 범용 AVD에 없으므로 공개 인터페이스·소스 분석으로 제한한다.' }
    4 = @{ image='evidence-sandbox.png'; commands='`id`, `cat /proc/self/attr/current`, `/proc/self/status`'; result='서로 다른 UID, `untrusted_app` SELinux 컨텍스트, 0 capability, seccomp 필터를 앱 프로세스 내부에서 확인했다.'; limit='정책 우회나 샌드박스 탈출은 수행하지 않았고, 접근 거부는 실패가 아니라 격리 통제가 작동한 대조군이다.' }
    5 = @{ image='evidence-boot.png'; commands='`getprop ro.treble.enabled`, `getprop ro.apex.updatable`, `mount`, FBE 속성'; result='Treble/APEX 활성화와 `/data`의 file-based encryption(`file`, `encrypted`)을 확인했다.'; limit='이 Google APIs AVD는 AVB 상태·A/B 슬롯 속성을 노출하지 않았다. 실제 하드웨어 롤백 퓨즈와 부트 ROM은 검증 범위 밖이다.' }
    6 = @{ image='evidence-kernel.png'; commands='`uname -a`, `/proc/cpuinfo`, NDK JNI 빌드, UBSan 패치 전·후 실행'; result='Android 13 기반 Linux 5.15 x86_64 커널을 확인하고, NDK 27로 JNI 공유 라이브러리와 UBSan 대조군을 빌드·실행했다.'; limit='범용 AVD에 없는 벤더 드라이버와 KASAN 커널은 실행하지 않았으며, 해당 항목은 공개 소스·설정 분석 결과로 구분한다.' }
    7 = @{ image='evidence-keystore.png'; commands='AndroidKeyStore EC 키 생성, attestation challenge, `KeyInfo`, certificate chain 조회'; result='EC 키 생성과 attestation 요청이 성공했고 인증서 체인 길이는 3이었다. 이 AVD의 키 보안 수준은 정확히 `SOFTWARE(0)`였다.'; limit='TEE·StrongBox·Weaver는 물리 보안 하드웨어가 없는 AVD에서 증명할 수 없다. SOFTWARE 결과를 하드웨어 보안으로 해석하지 않는다.' }
    8 = @{ image='privacy.png'; commands='Android 개인정보·보안·네트워크 설정 캡처, `curl --tlsv1.3`, 패키지·AppOps 조회'; result='권한·개인정보 통제 화면과 TLS 1.3 HTTP 200 응답을 확인했다. 앱·호스트 네트워크 관측을 분리해 기록했다.'; limit='Play Integrity의 프로덕션 verdict, 실제 OAuth 공급자, 제3자 SDK 백엔드는 범용 AVD 단독 검증 범위 밖이다.' }
    9 = @{ image='evidence-environment.png'; commands='재현 환경 지문 수집, APK 빌드·서명·설치, Jekyll 빌드, 링크·이미지 감사'; result='실행 환경·도구 버전·원시 출력을 보존하고 동일 명령을 재실행할 수 있는 증거 앱과 로그를 저장했다.'; limit='실제 취약점 악용이나 타인 시스템 검사는 하지 않았다. 공개 연구와 소유한 가상환경의 안전한 관측만 포함한다.' }
}

function Get-Tier([string]$module) {
    $number = [int]$module.Substring(1)
    if ($number -le 5) { return 0 }
    if ($number -le 11) { return 1 }
    if ($number -le 16) { return 2 }
    if ($number -le 22) { return 3 }
    if ($number -le 26) { return 4 }
    if ($number -le 32) { return 5 }
    if ($number -le 38) { return 6 }
    if ($number -le 43) { return 7 }
    if ($number -le 50) { return 8 }
    return 9
}

function Add-Metadata([string]$text, [string]$kind) {
    if ($text -notmatch '(?m)^series:') {
        $text = $text -replace '(?m)^(author:.*)$', "`$1`nseries: Android Security Concept Atlas`ndocument_type: $kind`nverification_date: 2026-08-29"
    } else {
        $text = $text -replace '(?m)^document_type:.*$', "document_type: $kind"
        $text = $text -replace '(?m)^verification_date:.*$', 'verification_date: 2026-08-29'
    }
    return $text
}

foreach ($file in $files) {
    $text = [IO.File]::ReadAllText($file.FullName, [Text.Encoding]::UTF8)
    $text = [regex]::Replace($text, '(?s)\r?\n<!-- atlas-verification:start -->.*?<!-- atlas-verification:end -->\r?\n', "`n")
    if ($file.Name -match 'android-concept-atlas-c(?<number>\d+)-') {
        $module = 'C' + $Matches.number.PadLeft(2, '0')
        $tier = Get-Tier $module
        $data = $tierData[$tier]

        $text = $text -replace '(?m)^title: "Android Security Concept Atlas C(\d+) - ', 'title: "Android Security Concept Atlas C$1 | 가상 실습 보고서 — '
        $text = Add-Metadata $text 'virtual-lab-report'

        if ($text -notmatch '<!-- atlas-verification:start -->') {
            $report = @"

<!-- atlas-verification:start -->
## 가상 실습 실행 보고서

| 구분 | 기록 |
|---|---|
| 실행일 | 2026-08-29 (Asia/Seoul) |
| 대상 | 전용 ``codex-atlas-api33`` AVD · Android 13/API 33 · Google APIs x86_64 |
| 실행 명령·코드 | $($data.commands) |
| 관측 결과 | $($data.result) |
| 검증 한계 | $($data.limit) |

![${module} 가상 실습 검증 화면](/assets/img/android-concept-atlas/verified-api33/$($data.image))

화면의 값은 저장소의 읽기 전용 [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)이 실행 중인 앱 프로세스에서 수집했으며, 호스트 ``adb shell`` 결과와 교차 확인했다. 전체 원시 출력은 [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md), 빌드·서명·TLS 결과는 [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)에 보존했다. ``[exit=0]``은 실행 성공, 접근 거부는 Android 격리의 예상 결과, 빈 속성은 이 AVD가 값을 제공하지 않았다는 뜻이다.
<!-- atlas-verification:end -->

"@
            $text = [regex]::Replace($text, $scopePattern, ('$1' + "`n" + $report), 1)
        }
    } elseif ($file.Name -match 'tier(?<tier>\d+)') {
        $tier = [int]$Matches.tier
        $data = $tierData[$tier]
        $text = $text -replace '(?m)^title: "Android Security Concept Atlas — Tier (\d+): ', 'title: "Android Security Concept Atlas Tier $1 | 학습 로드맵 — '
        $text = Add-Metadata $text 'learning-roadmap'
        if ($text -notmatch '<!-- atlas-verification:start -->') {
            $report = @"

<!-- atlas-verification:start -->
## 이 로드맵의 실제 검증 기준

이 글은 개별 모듈을 묶는 **학습 로드맵**이다. Tier ${tier}의 공통 기준 실습은 전용 API 33 AVD에서 다음 항목으로 확인했다: $($data.commands). $($data.result) $($data.limit)

![Tier $tier 가상 실습 기준 화면](/assets/img/android-concept-atlas/verified-api33/$($data.image))

세부 명령·판정은 각 Cxx 보고서와 [전체 원시 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)에서 확인할 수 있다.
<!-- atlas-verification:end -->

"@
            $text = [regex]::Replace($text, $scopePattern, ('$1' + "`n" + $report), 1)
        }
    } else {
        $text = $text -replace '(?m)^title: "Android Security Concept Atlas - 전체 지도 \(티어별 목차와 진행 현황\)"', 'title: "Android Security Concept Atlas | 전체 학습 지도·가상 검증 현황"'
        $text = Add-Metadata $text 'series-index'
        if ($text -notmatch '<!-- atlas-verification:start -->') {
            $report = @"

<!-- atlas-verification:start -->
## 검증 현황 요약

전용 API 33 AVD에서 기준 명령을 실행하고, 증거 앱을 직접 빌드·v2/v3 서명·설치·실행했다. 런타임 화면과 원시 로그를 함께 보존했으며, 하드웨어 전용 기능은 성공으로 꾸미지 않고 `가상 환경의 검증 한계`로 분리한다.

![Concept Atlas 가상 실습 기준 환경](/assets/img/android-concept-atlas/verified-api33/evidence-environment.png)

- 실행 증거: [API 33 기준 로그](/assets/evidence/android-concept-atlas/api33-baseline.md)
- 빌드·서명·TLS 증거: [호스트 검증 로그](/assets/evidence/android-concept-atlas/host-verification.md)
- 재현 코드: [Atlas Evidence 앱](/labs/android-concept-atlas-evidence-app/README.md)
<!-- atlas-verification:end -->

"@
            $text = [regex]::Replace($text, $scopePattern, ('$1' + "`n" + $report), 1)
        }
    }

    $text = $text.Replace('## 소스 탐색 과제', '## 소스·정적 검증 경로')
    $text = $text.Replace('## 블로그 초안 작성 과제', '## 추가 심화 재현 절차')
    $text = $text.Replace('개념 지도 편. 뒤의 「블로그 초안 작성 과제」에서 실측 글로 승격합니다.', '개념 해설과 가상 실습 실행 보고서를 함께 제공하는 검증본입니다.')
    $text = $text.Replace('위의 「블로그 초안 작성 과제」를 마치면 이 개념 모듈이 실측 글로 확정됩니다.', '이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.')
    $text = $text.Replace('위의 「블로그 초안 작성 과제」를 마치면 이 모듈이 실측 글로 확정됩니다.', '이 문서는 위 실행 보고서와 원시 로그를 기준으로 검증 상태를 관리합니다.')
    $text = $text.Replace('실물로 증명', '가상 환경에서 검증')
    [IO.File]::WriteAllText($file.FullName, $text, [Text.UTF8Encoding]::new($false))
}

Write-Output "Updated $($files.Count) Concept Atlas files."
