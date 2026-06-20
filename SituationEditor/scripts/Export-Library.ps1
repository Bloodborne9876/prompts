<#
.SYNOPSIS
  situations.json から人間が読みやすい一覧 (library\プロンプトライブラリ.md) を再生成する。
  GUIで編集した後に実行すれば常に最新の可読版が手に入る。
#>
[CmdletBinding()]
param(
    [string]$DataDir = (Join-Path $PSScriptRoot '..\data'),
    [string]$OutFile = (Join-Path $PSScriptRoot '..\library\プロンプトライブラリ.md')
)

$ErrorActionPreference = 'Stop'
$doc = Get-Content (Join-Path $DataDir 'situations.json') -Raw -Encoding utf8 | ConvertFrom-Json
$phases = @('導入', '序盤', '中盤', '終盤', 'アフター', '演出', 'その他')

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine('# シチュエーションライブラリ（自動生成）')
[void]$sb.AppendLine()
[void]$sb.AppendLine(('生成日: {0} / 編集は editor.html で行い、このファイルは Export-Library.ps1 で再生成すること' -f (Get-Date -Format 'yyyy-MM-dd')))
[void]$sb.AppendLine()

foreach ($ph in $phases) {
    $items = @($doc.situations | Where-Object { ($_.phase ?? 'その他') -eq $ph })
    if (-not $items) { continue }
    [void]$sb.AppendLine("## $ph")
    [void]$sb.AppendLine()
    foreach ($s in $items) {
        [void]$sb.AppendLine(('### {0}  `{1}`' -f $s.name, $s.id))
        if ($s.notes) { [void]$sb.AppendLine("> $($s.notes)") }
        $meta = "服装: $($s.defaultOutfit) / サイズ: $($s.defaultSize)"
        if ($s.negativeExtra) { $meta += " / 追加neg: $($s.negativeExtra)" }
        [void]$sb.AppendLine("*$meta*")
        [void]$sb.AppendLine()
        if ($s.base) {
            [void]$sb.AppendLine('base:')
            [void]$sb.AppendLine('```')
            [void]$sb.AppendLine($s.base)
            [void]$sb.AppendLine('```')
        }
        [void]$sb.AppendLine("variations ($(@($s.variations).Count)):")
        [void]$sb.AppendLine('```')
        foreach ($v in $s.variations) { [void]$sb.AppendLine($v) }
        [void]$sb.AppendLine('```')
        [void]$sb.AppendLine()
    }
}

New-Item -ItemType Directory -Force (Split-Path $OutFile -Parent) | Out-Null
$sb.ToString() | Out-File $OutFile -Encoding utf8
Write-Host "出力: $(Resolve-Path $OutFile)" -ForegroundColor Green
