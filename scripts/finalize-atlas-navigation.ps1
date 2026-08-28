$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$postDir = Join-Path $repo '_posts'
$routes = @{
    C01='android-concept-atlas-c01-assets-subjects-trust-boundaries'
    C07='android-concept-atlas-c07-dex-multidex-resources-arsc'
    C15='android-concept-atlas-c15-jni-native-library-loading'
    C18='android-concept-atlas-c18-parcel-serialization-contract'
    C22='android-concept-atlas-c22-binder-caller-identity-confused-deputy'
    C26='android-concept-atlas-c26-uid-sandbox-vs-selinux'
    C47='android-concept-atlas-c47-webview-deeplink-ipc-attack-surface'
    C51='android-concept-atlas-c51-crash-bug-vulnerability-exploit'
    C52='android-concept-atlas-c52-cwe-cve-security-bulletin-reading'
    C53='android-concept-atlas-c53-patch-diff-variant-analysis'
    C54='android-concept-atlas-c54-reproducibility-control-design'
    C55='android-concept-atlas-c55-threat-model-impact-assessment'
}

$targets = @((Join-Path $postDir '2026-08-29-android-concept-atlas-index.md'))
$targets += Get-ChildItem $postDir -Filter '*android-concept-atlas-tier*.md' | ForEach-Object FullName

foreach ($path in $targets) {
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines($path, [Text.Encoding]::UTF8)) {
        if ($line -match '^\| (C\d{2}) \|') {
            $id = $Matches[1]
            if ($routes.ContainsKey($id)) {
                $cells = $line.Split('|')
                $concept = $cells[2].Trim()
                if ($concept -notmatch '^\[') {
                    $cells[2] = " [$concept](/posts/$($routes[$id])/) "
                }
                $statusIndex = if ($cells.Count -ge 8) { 5 } else { 4 }
                $cells[$statusIndex] = ' ✅ '
                $line = $cells -join '|'
            }
        }
        $lines.Add($line)
    }
    $text = ($lines -join "`n") + "`n"
    $text = $text.Replace('**상태 범례**: ✅완성 · ✍️집필 중 · 🧩진단편(내 블로그가 이미 다룸) · ⬜계획', '**상태 범례**: ✅가상 실습 보고서 완성 · LIMIT=가상환경에서 직접 증명할 수 없는 하드웨어·외부 서비스 항목')
    $text = [regex]::Replace($text, '- \*\*완성\(✅\) 44편\*\*:.*?(?=\n- \*\*진단편)', '- **완성(✅) 56편**: C01~C56 전 모듈을 개별 가상 실습 보고서로 연결했습니다. 기존 44편을 재검증하고 진단편 12편도 정식 글로 작성했습니다.', 'Singleline')
    $text = [regex]::Replace($text, '- \*\*진단편\(🧩\) 11편\*\*:.*?\.', '- **실행 증거**: API 33 AVD, 재현용 APK/JNI 앱, UBSan 패치 전·후 행렬, 원시 로그와 스크린샷을 저장소에 포함했습니다.')
    $text = $text.Replace('진단편', '가상 실습 보고서')
    $text = $text.Replace('진단 대체 예정', '[C26 보고서](/posts/android-concept-atlas-c26-uid-sandbox-vs-selinux/)')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C01\(.*$', '> **완성 보고서**: C01은 자산·주체·신뢰경계·공격표면을 전용 글과 실행 증거로 정리했습니다.')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C07\(.*$', '> **완성 보고서**: C07은 DEX·multidex·resources.arsc를 APK 정적 분석 결과와 함께 정리했습니다.')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C15\(.*$', '> **완성 보고서**: C15는 Java→JNI→x86_64 네이티브 라이브러리 왕복 호출을 실제 앱으로 검증했습니다.')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C18\(.*$', '> **완성 보고서**: C18과 C22는 Parcel 계약 및 Binder 호출자 identity를 증거 앱의 대조군으로 검증했습니다.')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C26\(.*$', '> **완성 보고서**: C26은 UID 샌드박스와 SELinux가 서로 다른 계층에서 강제되는 모습을 앱 UID·도메인·접근 거부로 확인했습니다.')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C47\(.*$', '> **완성 보고서**: C47은 HTTPS 호스트 allowlist의 허용·거부 대조군으로 WebView·딥링크 입력 검증을 정리했습니다.')
    $text = [regex]::Replace($text, '(?m)^> \*\*가상 실습 보고서\*\*: C51~C55.*$', '> **완성 보고서**: C51~C55는 공개 불리틴 판독, patch diff, 재현성 대조군, 위협 모델과 영향 산정을 각각 독립 보고서로 작성했습니다.')
    [IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
}

# Update the one cross-reference outside a hub that still said C26 was pending.
$c23 = Join-Path $postDir '2026-08-25-android-concept-atlas-c23-selinux-policy.md'
$text = [IO.File]::ReadAllText($c23, [Text.Encoding]::UTF8)
$text = $text.Replace('**C26(샌드박스 vs SELinux 역할 구분)**(진단 대체 예정)', '[**C26(샌드박스 vs SELinux 역할 구분)**](/posts/android-concept-atlas-c26-uid-sandbox-vs-selinux/)')
[IO.File]::WriteAllText($c23, $text, [Text.UTF8Encoding]::new($false))

Write-Output 'Atlas navigation finalized.'
