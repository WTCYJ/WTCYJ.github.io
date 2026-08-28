param(
    [string]$Sdk = $(if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } elseif ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }),
    [string]$NdkVersion = '27.3.13750724',
    [string]$Serial = 'emulator-5580'
)

$ErrorActionPreference = 'Stop'
$out = Join-Path $PSScriptRoot 'build\ubsan'
$binary = Join-Path $out 'ubsan_probe'
$clang = Join-Path $Sdk "ndk\$NdkVersion\toolchains\llvm\prebuilt\windows-x86_64\bin\clang.exe"
$runtime = Get-ChildItem (Join-Path $Sdk "ndk\$NdkVersion") -Recurse `
    -Filter 'libclang_rt.ubsan_standalone-x86_64-android.so' | Select-Object -First 1
$adb = Join-Path $Sdk 'platform-tools\adb.exe'
New-Item -ItemType Directory -Force -Path $out | Out-Null

& $clang '--target=x86_64-linux-android26' '-fsanitize=undefined' `
    '-fno-sanitize-recover=undefined' '-fPIE' '-pie' `
    (Join-Path $PSScriptRoot 'jni\ubsan_probe.c') '-o' $binary
if ($LASTEXITCODE) { throw "UBSan compile failed: $LASTEXITCODE" }

$remote = '/data/local/tmp/atlas-ubsan-probe'
$remoteRuntime = '/data/local/tmp/libclang_rt.ubsan_standalone-x86_64-android.so'
& $adb -s $Serial push $binary $remote | Out-Null
if ($LASTEXITCODE) { throw "adb push failed: $LASTEXITCODE" }
if (-not $runtime) { throw 'UBSan runtime library was not found in the NDK.' }
& $adb -s $Serial push $runtime.FullName $remoteRuntime | Out-Null
if ($LASTEXITCODE) { throw "UBSan runtime push failed: $LASTEXITCODE" }
& $adb -s $Serial shell chmod 0755 $remote

$safe = (& $adb -s $Serial shell "LD_LIBRARY_PATH=/data/local/tmp $remote safe" 2>&1 | Out-String).Trim()
$safeExit = $LASTEXITCODE
$overflow = (& $adb -s $Serial shell "LD_LIBRARY_PATH=/data/local/tmp $remote overflow" 2>&1 | Out-String).Trim()
$overflowExit = $LASTEXITCODE

Write-Output "[safe exit=$safeExit]"
Write-Output $safe
Write-Output "[overflow exit=$overflowExit]"
Write-Output $overflow

if ($safeExit -ne 0 -or $safe -notmatch 'safe-result=42') {
    throw 'Safe control did not pass.'
}
if ($overflowExit -eq 0 -or $overflow -notmatch 'runtime error: signed integer overflow') {
    throw 'UBSan did not reject the overflow case as expected.'
}
Write-Output 'ubsan-verification=PASS'
