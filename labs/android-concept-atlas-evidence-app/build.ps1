param(
    [string]$Sdk = $(if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } elseif ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }),
    [string]$BuildTools = '36.0.0',
    [string]$CompileSdk = '34',
    [string]$NdkVersion = '27.3.13750724'
)

$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$out = Join-Path $project 'build'
$classes = Join-Path $out 'classes'
$dex = Join-Path $out 'dex'
$res = Join-Path $project 'res'
$androidJar = Join-Path $Sdk "platforms\android-$CompileSdk\android.jar"
$tools = Join-Path $Sdk "build-tools\$BuildTools"
$debugKey = Join-Path $env:USERPROFILE '.android\debug.keystore'
$ndk = Join-Path $Sdk "ndk\$NdkVersion"
$clang = Join-Path $ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin\clang.exe'
$nativeRoot = Join-Path $out 'native'
$nativeLibDir = Join-Path $nativeRoot 'lib\x86_64'

New-Item -ItemType Directory -Force -Path $classes, $dex, $res, $nativeLibDir | Out-Null

& $clang '--target=x86_64-linux-android26' '-fPIC' '-shared' '-O2' `
    '-Wl,-z,relro,-z,now,-z,noexecstack' `
    (Join-Path $project 'jni\atlas_evidence.c') `
    -o (Join-Path $nativeLibDir 'libatlasevidence.so')
if ($LASTEXITCODE) { throw "NDK clang failed: $LASTEXITCODE" }

& javac --release 8 -encoding UTF-8 -classpath $androidJar -d $classes `
    (Join-Path $project 'src\com\example\atlasreport\MainActivity.java')
if ($LASTEXITCODE) { throw "javac failed: $LASTEXITCODE" }

& (Join-Path $tools 'd8.bat') --lib $androidJar --output $dex `
    (Join-Path $classes 'com\example\atlasreport\MainActivity.class')
if ($LASTEXITCODE) { throw "d8 failed: $LASTEXITCODE" }

$unsigned = Join-Path $out 'atlas-evidence-unsigned.apk'
$unaligned = Join-Path $out 'atlas-evidence-unaligned.apk'
$apk = Join-Path $out 'atlas-evidence.apk'
& (Join-Path $tools 'aapt.exe') package -f -M (Join-Path $project 'AndroidManifest.xml') `
    -I $androidJar -S $res -F $unaligned
if ($LASTEXITCODE) { throw "aapt package failed: $LASTEXITCODE" }
Copy-Item -LiteralPath $unaligned -Destination $unsigned -Force
Push-Location $dex
try {
    & (Join-Path $tools 'aapt.exe') add $unsigned 'classes.dex'
    if ($LASTEXITCODE) { throw "aapt add failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
Push-Location $nativeRoot
try {
    & (Join-Path $tools 'aapt.exe') add $unsigned 'lib/x86_64/libatlasevidence.so'
    if ($LASTEXITCODE) { throw "aapt native add failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
& (Join-Path $tools 'zipalign.exe') -f 4 $unsigned $apk
if ($LASTEXITCODE) { throw "zipalign failed: $LASTEXITCODE" }
& (Join-Path $tools 'apksigner.bat') sign --ks $debugKey --ks-key-alias androiddebugkey `
    --ks-pass pass:android --key-pass pass:android $apk
if ($LASTEXITCODE) { throw "apksigner failed: $LASTEXITCODE" }
& (Join-Path $tools 'apksigner.bat') verify --verbose $apk
if ($LASTEXITCODE) { throw "apksigner verify failed: $LASTEXITCODE" }
Write-Output $apk
