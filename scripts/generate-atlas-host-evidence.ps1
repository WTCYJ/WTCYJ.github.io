$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
$buildTools = Join-Path $sdk 'build-tools\36.0.0'
$apk = Join-Path $repo 'labs\android-concept-atlas-evidence-app\build\atlas-evidence.apk'
$nativeLibrary = Join-Path $repo 'labs\android-concept-atlas-evidence-app\build\native\lib\x86_64\libatlasevidence.so'
$readelf = Join-Path $sdk 'ndk\27.3.13750724\toolchains\llvm\prebuilt\windows-x86_64\bin\llvm-readelf.exe'
$apkanalyzer = Join-Path $sdk 'cmdline-tools\latest\bin\apkanalyzer.bat'
$serial = 'emulator-5580'
$outputPath = Join-Path $repo 'assets\evidence\android-concept-atlas\host-verification.md'

foreach ($required in @($apk, $nativeLibrary, $readelf, $apkanalyzer)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required artifact not found: $required"
    }
}

$document = [Collections.Generic.List[string]]::new()
$document.Add('# Host-side build, runtime, and protocol verification')
$document.Add('')
$document.Add("Captured: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))")
$document.Add('')
$document.Add('이 문서는 전용 API 33 AVD와 로컬 빌드 도구에서 다시 실행한 결과만 기록한다. 물리 기기, TEE, StrongBox, 실제 AVB 퓨즈와 Play 백엔드는 검증 범위가 아니다.')

function Invoke-External([string]$command, [string[]]$arguments) {
    $captured = @(& $command @arguments 2>&1 | ForEach-Object { $_.ToString() })
    $exitCode = $LASTEXITCODE
    return @{ Output = $captured; ExitCode = $exitCode }
}

function Add-Section([string]$title, [string]$commandLine, [string[]]$output, [int]$exitCode) {
    $document.Add('')
    $document.Add("## $title")
    $document.Add('')
    $document.Add("명령: ``$commandLine``")
    $document.Add('')
    $document.Add('```text')
    foreach ($line in $output) { $document.Add($line.TrimEnd()) }
    $document.Add("[exit=$exitCode]")
    $document.Add('```')
    if ($exitCode -ne 0) { throw "$title failed with exit code $exitCode" }
}

$signature = Invoke-External (Join-Path $buildTools 'apksigner.bat') @('verify', '--verbose', '--print-certs', $apk)
Add-Section 'APK signature verification' 'apksigner verify --verbose --print-certs atlas-evidence.apk' $signature.Output $signature.ExitCode

$badging = Invoke-External (Join-Path $buildTools 'aapt.exe') @('dump', 'badging', $apk)
Add-Section 'APK manifest and package metadata' 'aapt dump badging atlas-evidence.apk' $badging.Output $badging.ExitCode

$files = Invoke-External $apkanalyzer @('files', 'list', $apk)
Add-Section 'APK file table' 'apkanalyzer files list atlas-evidence.apk' $files.Output $files.ExitCode

$applicationId = Invoke-External $apkanalyzer @('manifest', 'application-id', $apk)
Add-Section 'Manifest application id' 'apkanalyzer manifest application-id atlas-evidence.apk' $applicationId.Output $applicationId.ExitCode

$dex = Invoke-External $apkanalyzer @('dex', 'packages', $apk)
$dexSummary = @($dex.Output | Where-Object { $_ -match '<TOTAL>|com\.example|MainActivity' })
if ($dexSummary.Count -eq 0) { throw 'apkanalyzer produced no Atlas DEX rows' }
Add-Section 'DEX package summary' 'apkanalyzer dex packages atlas-evidence.apk (Atlas rows)' $dexSummary $dex.ExitCode

$elf = Invoke-External $readelf @('-h', '-l', '-d', '-n', $nativeLibrary)
Add-Section 'JNI ELF hardening metadata' 'llvm-readelf -h -l -d -n libatlasevidence.so' $elf.Output $elf.ExitCode

$install = Invoke-External (Join-Path $sdk 'platform-tools\adb.exe') @('-s', $serial, 'install', '-r', $apk)
Add-Section 'AVD APK installation' 'adb -s emulator-5580 install -r atlas-evidence.apk' $install.Output $install.ExitCode

& (Join-Path $sdk 'platform-tools\adb.exe') -s $serial logcat -c | Out-Null
$sweep = [Collections.Generic.List[string]]::new()
foreach ($section in @('environment','sandbox','kernel','boot','runtime','storage','binder','network','keystore','biometric','jni','package','parcel','identity','uri')) {
    & (Join-Path $sdk 'platform-tools\adb.exe') -s $serial shell am force-stop com.example.atlasreport | Out-Null
    $launch = @(& (Join-Path $sdk 'platform-tools\adb.exe') -s $serial shell am start -W -n com.example.atlasreport/.MainActivity --es section $section 2>&1 | ForEach-Object { $_.ToString() })
    if ($LASTEXITCODE -ne 0 -or -not ($launch -match '^Status: ok$')) { throw "Activity launch failed: $section" }
    $sweep.Add("$section : Status=ok")
    Start-Sleep -Milliseconds 250
}
$crash = @(& (Join-Path $sdk 'platform-tools\adb.exe') -s $serial logcat -d -b crash 2>&1 | ForEach-Object { $_.ToString() })
if (($crash -join "`n") -match 'FATAL EXCEPTION|AndroidRuntime') { throw 'Crash buffer contains an application crash' }
$sweep.Add('crash-buffer : PASS (no FATAL EXCEPTION)')
Add-Section '15-section AVD activity sweep' 'am start -W ... --es section <name>; logcat -b crash' $sweep 0

$tls = Invoke-External 'curl.exe' @('-sS', '-I', '--tlsv1.3', 'https://developer.android.com')
$tlsSummary = @($tls.Output | Select-Object -First 12)
Add-Section 'TLS 1.3 request to developer.android.com' 'curl -I --tlsv1.3 https://developer.android.com' $tlsSummary $tls.ExitCode

$powershell = (Get-Command pwsh.exe).Source
$ubsanScript = Join-Path $repo 'labs\android-concept-atlas-evidence-app\build-and-run-ubsan.ps1'
$ubsan = Invoke-External $powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ubsanScript)
if (($ubsan.Output -join "`n") -notmatch 'ubsan-verification=PASS') { throw 'UBSan verification marker missing' }
Add-Section 'UBSan safe/overflow control' 'build-and-run-ubsan.ps1' $ubsan.Output $ubsan.ExitCode

$matrixScript = Join-Path $repo 'labs\android-concept-atlas-research-method\run-matrix.ps1'
$matrix = Invoke-External $powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $matrixScript)
if (($matrix.Output -join "`n") -notmatch 'patch-diff-matrix=PASS') { throw 'Patch matrix PASS marker missing' }
Add-Section 'Patch-before/after matrix' 'run-matrix.ps1' $matrix.Output $matrix.ExitCode

$matrixSecond = Invoke-External $powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $matrixScript)
if (($matrixSecond.Output -join "`n") -notmatch 'patch-diff-matrix=PASS') { throw 'Second patch matrix PASS marker missing' }
$matrixText = ($matrix.Output -join "`n") + "`n"
$matrixSecondText = ($matrixSecond.Output -join "`n") + "`n"
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $firstHash = [Convert]::ToHexString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($matrixText))).ToLowerInvariant()
    $secondHash = [Convert]::ToHexString($sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes($matrixSecondText))).ToLowerInvariant()
} finally {
    $sha256.Dispose()
}
if ($firstHash -ne $secondHash) { throw 'Patch matrix output was not reproducible' }
$matrixEvidence = @(
    '# Patch-diff and reproducibility matrix',
    '',
    "Captured: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))",
    '',
    '```text'
) + @($matrix.Output | ForEach-Object { $_.TrimEnd() }) + @(
    '```',
    '',
    "run1_sha256=$firstHash",
    '',
    "run2_sha256=$secondHash",
    '',
    'reproducible=True'
)
$matrixEvidencePath = Join-Path $repo 'assets\evidence\android-concept-atlas\patch-diff-matrix.md'
[IO.File]::WriteAllLines($matrixEvidencePath, $matrixEvidence, [Text.UTF8Encoding]::new($false))

Push-Location $repo
try {
    $jekyll = Invoke-External (Get-Command bundle.bat).Source @('exec', 'jekyll', 'build')
} finally {
    Pop-Location
}
Add-Section 'Jekyll production build' 'bundle exec jekyll build' $jekyll.Output $jekyll.ExitCode

$document.Add('')
$document.Add('## Final verdict')
$document.Add('')
$document.Add('- `PASS`: APK v2/v3 서명, APK/DEX/ELF 구조, 설치, 15개 화면 실행, crash scan, TLS 1.3, UBSan 대조군, patch-before/after 행렬, Jekyll 빌드.')
$document.Add('- `EXPECTED DENY`: 앱 샌드박스가 막은 보호 파일·속성 접근은 격리 통제가 작동한 결과다.')
$document.Add('- `LIMIT`: AVD에 없는 TEE·StrongBox·Weaver·하드웨어 AVB/rollback fuse·Play Integrity 프로덕션 verdict는 성공으로 표시하지 않는다.')

[IO.File]::WriteAllLines($outputPath, $document, [Text.UTF8Encoding]::new($false))
Write-Output "Wrote $outputPath"
