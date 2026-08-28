param(
    [string]$Sdk = $(if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } elseif ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }),
    [string]$NdkVersion = '27.3.13750724',
    [string]$Serial = 'emulator-5580'
)

$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot 'build'
$clang = Join-Path $Sdk "ndk\$NdkVersion\toolchains\llvm\prebuilt\windows-x86_64\bin\clang.exe"
$runtime = Get-ChildItem (Join-Path $Sdk "ndk\$NdkVersion") -Recurse `
    -Filter 'libclang_rt.ubsan_standalone-x86_64-android.so' | Select-Object -First 1
$adb = Join-Path $Sdk 'platform-tools\adb.exe'
New-Item -ItemType Directory -Force -Path $out | Out-Null

foreach ($variant in @('before', 'after')) {
    & $clang '--target=x86_64-linux-android26' '-fsanitize=undefined' `
        '-fno-sanitize-recover=undefined' '-fPIE' '-pie' `
        (Join-Path $PSScriptRoot "length_check_$variant.c") '-o' (Join-Path $out $variant)
    if ($LASTEXITCODE) { throw "$variant compile failed: $LASTEXITCODE" }
    & $adb -s $Serial push (Join-Path $out $variant) "/data/local/tmp/atlas-$variant" 2>$null | Out-Null
    & $adb -s $Serial shell chmod 0755 "/data/local/tmp/atlas-$variant"
}
& $adb -s $Serial push $runtime.FullName '/data/local/tmp/libclang_rt.ubsan_standalone-x86_64-android.so' 2>$null | Out-Null

$cases = @(
    @{ name='normal'; offset=10; length=20; total=100 },
    @{ name='boundary'; offset=80; length=20; total=100 },
    @{ name='range-error'; offset=90; length=20; total=100 },
    @{ name='overflow'; offset=2147483640; length=16; total=4096 }
)

$transcript = New-Object Text.StringBuilder
foreach ($case in $cases) {
    [void]$transcript.AppendLine("## $($case.name)")
    foreach ($variant in @('before', 'after')) {
        $command = "LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/atlas-$variant $($case.offset) $($case.length) $($case.total)"
        $output = (& $adb -s $Serial shell $command 2>&1 | Out-String).Trim()
        $exitCode = $LASTEXITCODE
        [void]$transcript.AppendLine("$variant exit=$exitCode")
        [void]$transcript.AppendLine($output)
    }
}

$value = $transcript.ToString()
Write-Output $value
if ($value -notmatch 'runtime error: signed integer overflow') { throw 'Expected UBSan overflow was not observed.' }
if ($value -notmatch 'after offset=2147483640 length=16 total=4096 decision=REJECT') { throw 'Fixed variant did not reject overflow input.' }
Write-Output 'patch-diff-matrix=PASS'
