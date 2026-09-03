<#
.SYNOPSIS
    프린터 드라이버 계열 취약 ACL 점검기 — CVE-2019-19363(Ricoh) 및 동일 패턴(CWE-732)

.DESCRIPTION
    SYSTEM 권한 프로세스(spoolsv.exe / PrintIsolationHost.exe)가 로드하는 실행 모듈을,
    저권한 사용자가 조작할 수 있는 경로를 찾아낸다.

    ── 이 스크립트가 두 등급을 구분하는 이유 ──────────────────────────────
    C:\ProgramData 의 '기본' ACL은 다음과 같다.

        BUILTIN\Users:(I)(OI)(CI)(RX)          ← 파일/폴더 읽기+실행
        BUILTIN\Users:(I)(CI)(WD,AD,WEA,WA)    ← '폴더에만'(CI) 새 항목 생성 허용

    두 번째 ACE에 OI(Object Inherit)가 없다는 점이 결정적이다. 사용자는 새 파일을
    만들 수는 있어도 '기존 파일'에 대한 쓰기 권한은 상속받지 못한다. 따라서 기본
    ProgramData 하위 폴더는 "새 DLL 심기(phantom DLL)"만 가능하고, 정품 DLL을
    덮어쓸 수는 없다.

    CVE-2019-19363의 Ricoh 드라이버는 여기서 한 단계 더 나갔다.

        C:\ProgramData\RICOH_DRV  Everyone:(OI)(CI)(F)
        → 하위 DLL 파일들이  Everyone:(I)(F)  를 상속

    OI가 붙고 권한이 Full Control이라, 이미 존재하는 정품 DLL을 누구나 통째로
    덮어쓸 수 있었다. 이것이 실제 익스플로잇을 성립시킨 차이다.

    그래서 결과를 두 단계로 나눈다.
      [CRITICAL] 이미 존재하는 .dll/.exe 자체가 저권한 사용자에게 쓰기/삭제 가능
                 → Ricoh 패턴. 정품 모듈 치환으로 즉시 코드 실행.
      [PLANT]    폴더에 새 파일만 생성 가능(기존 모듈은 보호됨)
                 → 특권 프로세스가 '없는' DLL을 찾을 때만 악용 가능(탐색 순서 하이재킹).

.PARAMETER Path
    점검할 루트 경로. 기본값은 프린터 드라이버가 흔히 자리잡는 경로들.

.PARAMETER Depth
    재귀 깊이 제한. ProgramData 전체를 무한 재귀하면 매우 느리다.

.PARAMETER CriticalOnly
    Ricoh 패턴(기존 모듈 덮어쓰기 가능)만 출력한다.

.PARAMETER Anonymize
    제3자 제품명을 결과에서 가린다. 여기서 걸리는 것은 '쓰기 가능'일 뿐 취약점이
    확정된 것이 아니므로(특권 프로세스가 그 모듈을 로드하는지 별도 확인 필요),
    공개 글에 결과 화면을 실을 때 벤더를 특정하지 않기 위한 옵션이다.
    ProgramData 바로 아래 폴더명을 벤더 토큰으로 보고 소프트웨어 A/B/C…로 치환하며,
    파일명 안에 들어간 같은 토큰도 함께 가린다.

.PARAMETER Redact
    폴더명과 다른 브랜드 문자열이 파일명에 들어 있을 때(예: 폴더는 Battle.net인데
    파일은 Blizzard Uninstaller.exe) 추가로 가릴 토큰을 직접 지정한다. -Anonymize와 함께 쓴다.

.EXAMPLE
    .\Find-WeakPrintDriverAcl.ps1

.EXAMPLE
    .\Find-WeakPrintDriverAcl.ps1 -Path 'C:\ProgramData' -Depth 5 -Csv report.csv -CriticalOnly

.NOTES
    읽기 전용. 어떤 파일도 수정하지 않는다.
    Windows PowerShell 5.1에서 실행하려면 이 파일이 UTF-8 BOM으로 저장되어야 한다.
#>
[CmdletBinding()]
param(
    [string[]] $Path = @(
        'C:\ProgramData',
        "$env:SystemRoot\System32\spool\drivers",
        "$env:SystemRoot\System32\spool\PRTPROCS",
        'C:\Program Files\Common Files',
        'C:\Program Files (x86)\Common Files'
    ),
    [int]    $Depth = 4,
    [string] $Csv,
    [switch] $CriticalOnly,
    [switch] $Anonymize,
    [string[]] $Redact
)

$ErrorActionPreference = 'SilentlyContinue'

# 저권한 사용자를 뜻하는 SID. 이름 표기는 환경에 따라 달라질 수 있고, 이름으로 비교하면
# 빗나가도 예외가 아니라 '해당 없음'으로 조용히 지나간다. 그래서 SID로 비교한다.
# (측정 호스트는 UI 언어가 ko-KR 인데도 icacls 는 Everyone / BUILTIN\Users 를 영문으로
#  찍었다. 반대로 같은 세션에서 이벤트 로그 메시지는 한국어로 번역돼 나온다. 표기 규칙이 한 축이 아니다.)
# EPSON CVE-2025-42598이 "영어가 아닌 Windows에서만" 터진 것도 같은 함정이었다.
$LowPrivSids = @{
    'S-1-1-0'      = 'Everyone'
    'S-1-5-32-545' = 'BUILTIN\Users'
    'S-1-5-11'     = 'Authenticated Users'
    'S-1-5-4'      = 'INTERACTIVE'
    'S-1-5-32-546' = 'BUILTIN\Guests'
    'S-1-5-7'      = 'ANONYMOUS LOGON'
}

# 권한 비트
$RIGHT_WRITEDATA   = 2       # 파일에 적용되면 '내용 덮어쓰기', 폴더면 '새 파일 생성'
$RIGHT_APPENDDATA  = 4       # 파일이면 이어쓰기, 폴더면 하위 폴더 생성
$RIGHT_DELETE      = 65536   # 기존 DLL을 지우고 자기 것으로 교체
$RIGHT_CHANGEPERM  = 262144  # ACL을 스스로 고쳐 권한 획득
$RIGHT_TAKEOWN     = 524288  # 소유권 탈취 후 전권 획득

$PlantMask = $RIGHT_WRITEDATA -bor $RIGHT_APPENDDATA -bor $RIGHT_DELETE -bor `
             $RIGHT_CHANGEPERM -bor $RIGHT_TAKEOWN

function Convert-MaskToNames {
    param([int] $Mask)
    $n = @()
    if ($Mask -band $RIGHT_WRITEDATA)  { $n += 'WriteData' }
    if ($Mask -band $RIGHT_APPENDDATA) { $n += 'AppendData' }
    if ($Mask -band $RIGHT_DELETE)     { $n += 'Delete' }
    if ($Mask -band $RIGHT_CHANGEPERM) { $n += 'ChangePermissions' }
    if ($Mask -band $RIGHT_TAKEOWN)    { $n += 'TakeOwnership' }
    return ($n -join ',')
}

function Test-WeakAcl {
    <#
      한 경로의 DACL을 훑어 저권한 SID가 쓰기 계열 권한을 갖는지 판정한다.
      Deny ACE가 Allow보다 우선하므로 Allow 마스크에서 Deny 마스크를 뺀다.
    #>
    param([string] $Target)

    try   { $acl = Get-Acl -LiteralPath $Target -ErrorAction Stop }
    catch { return @() }
    if (-not $acl) { return @() }

    $denyBySid = @{}
    foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne 'Deny') { continue }
        $sid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value }
               catch { $ace.IdentityReference.Value }
        if (-not $denyBySid.ContainsKey($sid)) { $denyBySid[$sid] = 0 }
        $denyBySid[$sid] = $denyBySid[$sid] -bor [int]$ace.FileSystemRights
    }

    $hits = @()
    foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne 'Allow') { continue }

        $sid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value }
               catch { $ace.IdentityReference.Value }
        if (-not $LowPrivSids.ContainsKey($sid)) { continue }

        $effective = [int]$ace.FileSystemRights
        if ($denyBySid.ContainsKey($sid)) { $effective = $effective -band (-bnot $denyBySid[$sid]) }

        $granted = $effective -band $PlantMask
        if ($granted -eq 0) { continue }

        $hits += [pscustomobject]@{
            Principal = $LowPrivSids[$sid]
            Sid       = $sid
            Mask      = $granted
            Rights    = Convert-MaskToNames $granted
            Inherited = $ace.IsInherited
        }
    }
    return $hits
}

# ---------------------------------------------------------------------------
# 1단계 — 실행 모듈을 품은 디렉터리 수집
#          쓰기 가능해도 로드되는 코드가 없으면 권한 상승으로 이어지지 않는다.
# ---------------------------------------------------------------------------
Write-Host "[*] 프린터 드라이버 취약 ACL 점검 (depth=$Depth)" -ForegroundColor Cyan

$candidates = New-Object System.Collections.Generic.HashSet[string]
foreach ($root in $Path) {
    if (-not (Test-Path -LiteralPath $root)) {
        Write-Host "    - 건너뜀(없음): $root" -ForegroundColor DarkGray
        continue
    }
    Write-Host "    - 스캔: $root" -ForegroundColor DarkGray
    Get-ChildItem -LiteralPath $root -Recurse -Depth $Depth -Include '*.dll', '*.exe' -File -Force |
        ForEach-Object { [void]$candidates.Add($_.DirectoryName) }
}
Write-Host "[*] 실행 모듈 포함 디렉터리 $($candidates.Count)개 → ACL 평가" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 2단계 — 폴더 ACL로 1차 선별한 뒤, 그 안의 '실제 모듈 파일' ACL을 확인해
#          Ricoh 패턴(기존 모듈 덮어쓰기 가능)인지 판정
# ---------------------------------------------------------------------------
$findings = @()
foreach ($dir in $candidates) {
    $dirHits = Test-WeakAcl -Target $dir
    if ($dirHits.Count -eq 0) { continue }

    # 주의: -Include는 -Recurse 나 경로 끝 와일드카드가 없으면 조용히 무시된다.
    # 그대로 두면 .log/.db 까지 '모듈'로 잡혀 오탐이 된다. 확장자로 직접 거른다.
    $modules   = @(Get-ChildItem -LiteralPath $dir -File -Force |
                   Where-Object { $_.Extension -eq '.dll' -or $_.Extension -eq '.exe' })
    $writable  = @()
    $fileMask  = 0
    $filePrins = @()

    foreach ($m in $modules) {
        $fh = Test-WeakAcl -Target $m.FullName
        if ($fh.Count -eq 0) { continue }
        $writable  += $m.Name
        $filePrins += $fh.Principal
        foreach ($h in $fh) { $fileMask = $fileMask -bor $h.Mask }
    }

    if ($writable.Count -gt 0) {
        # 기존 정품 모듈 자체가 저권한 쓰기 가능 → CVE-2019-19363과 동일 조건
        $findings += [pscustomobject]@{
            Risk           = 'CRITICAL'
            Pattern        = 'OverwriteExistingModule'
            Path           = $dir
            Principal      = (($filePrins | Select-Object -Unique) -join ',')
            Rights         = Convert-MaskToNames $fileMask
            ModuleCount    = $modules.Count
            WritableCount  = $writable.Count
            WritableSample = (($writable | Select-Object -First 3) -join ',')
        }
    } elseif (-not $CriticalOnly) {
        # 폴더에는 새 파일을 만들 수 있으나 기존 모듈은 보호됨 → ProgramData 기본값
        $findings += [pscustomobject]@{
            Risk           = 'PLANT'
            Pattern        = 'CreateNewFileOnly'
            Path           = $dir
            Principal      = (($dirHits.Principal | Select-Object -Unique) -join ',')
            Rights         = Convert-MaskToNames (($dirHits | Measure-Object -Property Mask -Maximum).Maximum)
            ModuleCount    = $modules.Count
            WritableCount  = 0
            WritableSample = ''
        }
    }
}

# @()로 감싸지 않으면 결과가 1건일 때 스칼라가 되어 .Count가 비어 나온다 (PS 5.1)
$order    = @{ 'CRITICAL' = 0; 'PLANT' = 1 }
$findings = @($findings | Sort-Object @{ Expression = { $order[$_.Risk] } }, Path)
$crit     = @($findings | Where-Object Risk -eq 'CRITICAL')
$plant    = @($findings | Where-Object Risk -eq 'PLANT')

if ($Anonymize) {
    # ProgramData 바로 아래 폴더명을 벤더 토큰으로 본다. 발견 순서대로 A, B, C… 를 준다.
    # 정규식을 쓰면 PS 문자열 안에서 역슬래시가 한 번 더 먹히므로 문자열 연산으로 자른다.
    $sep    = [char]92
    $pdRoot = 'C:' + $sep + 'ProgramData' + $sep
    $label  = @{}
    $next   = 0
    foreach ($f in $findings) {
        if ($f.Path.StartsWith($pdRoot, [StringComparison]::OrdinalIgnoreCase)) {
            $token = ($f.Path.Substring($pdRoot.Length)).Split($sep)[0]
            if ($token -and -not $label.ContainsKey($token.ToLower())) {
                $label[$token.ToLower()] = ('소프트웨어 ' + [char](65 + $next))
                $next++
            }
        }
    }
    # 폴더명과 다른 브랜드 문자열은 A/B/C 라벨을 새로 주지 않고 중립 표기로 가린다.
    # 같은 벤더에 서로 다른 라벨이 붙어 별개 소프트웨어처럼 보이는 것을 막는다.
    foreach ($r in $Redact) {
        if ($r) { $label[$r.ToLower()] = '벤더명' }
    }
    foreach ($f in $findings) {
        foreach ($tok in @($label.Keys)) {
            $rep = '<' + $label[$tok] + '>'
            $f.Path           = [regex]::Replace($f.Path,           [regex]::Escape($tok), $rep, 'IgnoreCase')
            $f.WritableSample = [regex]::Replace($f.WritableSample, [regex]::Escape($tok), $rep, 'IgnoreCase')
        }
    }
}


Write-Host ""
Write-Host "════ 결과 ════" -ForegroundColor Cyan
Write-Host "  CRITICAL (기존 모듈 덮어쓰기 가능 · Ricoh 패턴) : $($crit.Count)건" -ForegroundColor $(if ($crit.Count) { 'Red' } else { 'Green' })
Write-Host "  PLANT    (새 파일 생성만 가능 · ProgramData 기본): $($plant.Count)건" -ForegroundColor DarkYellow

if ($crit.Count) {
    Write-Host "`n[!] CRITICAL — SYSTEM 프로세스가 이 모듈을 로드하면 즉시 권한 상승" -ForegroundColor Red
    $crit | Format-Table Principal, Rights, WritableCount, WritableSample, Path -AutoSize -Wrap
}

# ---------------------------------------------------------------------------
# 3단계 — CVE-2019-19363 고유 지표(IoC)
# ---------------------------------------------------------------------------
$ricoh = 'C:\ProgramData\RICOH_DRV'
Write-Host "`n[*] CVE-2019-19363 고유 지표: $ricoh" -ForegroundColor Cyan
if (Test-Path -LiteralPath $ricoh) {
    $ricohHits = Test-WeakAcl -Target $ricoh
    if ($ricohHits.Count) {
        Write-Host "    [!] 취약 — Ricoh 드라이버 디렉터리가 저권한 쓰기 허용" -ForegroundColor Red
        $ricohHits | Format-Table Principal, Rights, Inherited -AutoSize
    } else {
        Write-Host "    [+] 디렉터리는 있으나 ACL 정상(저권한 쓰기 없음)" -ForegroundColor Green
    }
    $plugins = @('borderline.dll','headerfooter.dll','jobhook.dll','overlaywatermark.dll','popup.dll','watermark.dll')
    $found = @(Get-ChildItem -LiteralPath $ricoh -Recurse -Force -Include $plugins)
    if ($found.Count) {
        Write-Host "    표적 플러그인 DLL $($found.Count)개:" -ForegroundColor Yellow
        $found | Select-Object Name, Length, LastWriteTime, FullName | Format-Table -AutoSize
    }
} else {
    Write-Host "    [+] RICOH_DRV 없음 — 해당 드라이버 미설치" -ForegroundColor Green
}

if ($Csv -and $findings.Count) {
    $findings | Export-Csv -LiteralPath $Csv -NoTypeInformation -Encoding UTF8
    Write-Host "`n[*] CSV 저장: $Csv" -ForegroundColor Cyan
}
