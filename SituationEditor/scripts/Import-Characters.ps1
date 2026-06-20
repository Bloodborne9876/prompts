<#
.SYNOPSIS
  キャラ\*.md (1行 = 1キャラのタグ列) を characters.json の雛形に変換する。

.DESCRIPTION
  - 行頭の見出し・空行はスキップ、重複IDはスキップ
  - outfits は settings.json の outfitTemplates を全キャラにコピー (GUIで個別調整する前提)
  - 未成年を示すタグ (loli 等) は取り込み時に除去する
  - LoRA タグや髪・目のタグは取り込み後に GUI の base 欄へ追記する運用

.EXAMPLE
  .\Import-Characters.ps1
  .\Import-Characters.ps1 -Path C:\temp\sell\キャラ\blue_archive.md
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [string]$OutFile = (Join-Path $PSScriptRoot '..\data\characters.json'),
    [string]$SettingsFile = (Join-Path $PSScriptRoot '..\data\settings.json'),
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'

if (-not $Path) {
    $Path = Get-ChildItem 'C:\temp\sell\キャラ\*.md' | Select-Object -ExpandProperty FullName
}

$settings = Get-Content $SettingsFile -Raw -Encoding utf8 | ConvertFrom-Json
$outfitTemplates = $settings.outfitTemplates

# 未成年表現タグの除去パターン
$minorTagPattern = '^(loli|shota|child|toddler|baby|\d+\s*yo)$'

$existing = [System.Collections.Generic.List[object]]::new()
$usedIds = @{}
if ((Test-Path $OutFile) -and -not $Replace) {
    $doc = Get-Content $OutFile -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($c in $doc.characters) { $existing.Add($c); $usedIds[$c.id] = $true }
}

$added = 0
$strippedTags = 0

foreach ($file in $Path) {
    $series = [System.IO.Path]::GetFileNameWithoutExtension($file)
    Write-Host "取り込み中: $file" -ForegroundColor Cyan

    foreach ($raw in (Get-Content $file -Encoding utf8)) {
        $line = $raw.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) { continue }
        if ($line -notmatch '[a-zA-Z]') { continue }

        # 未成年タグの除去
        $tokens = $line -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        $kept = @($tokens | Where-Object {
            if ($_ -match $minorTagPattern) { $script:strippedTags++; $false } else { $true }
        })
        if ($kept.Count -eq 0) { continue }
        $tagLine = $kept -join ', '

        # ID: 最初の括弧/カンマより前の部分をスラッグ化
        $nameRaw = ($tagLine -split '[,(\\]')[0].Trim()
        $slug = ($nameRaw -replace '[^a-zA-Z0-9]+', '_').Trim('_').ToLower()
        if (-not $slug) { continue }
        if ($usedIds.ContainsKey($slug)) { continue }   # 重複はスキップ
        $usedIds[$slug] = $true

        $existing.Add([pscustomobject]@{
            id      = $slug
            name    = $nameRaw
            series  = $series
            base    = "1girl, solo, $tagLine"
            outfits = [pscustomobject]@{
                normal    = $outfitTemplates.normal
                torn      = $outfitTemplates.torn
                underwear = $outfitTemplates.underwear
                nude      = $outfitTemplates.nude
            }
        })
        $added++
    }
}

@{ characters = @($existing) } | ConvertTo-Json -Depth 6 | Out-File $OutFile -Encoding utf8

Write-Host ("完了: {0} キャラ追加 (合計 {1}) → {2}" -f $added, $existing.Count, (Resolve-Path $OutFile)) -ForegroundColor Green
if ($strippedTags -gt 0) {
    Write-Host ("注: 未成年表現タグを {0} 件除去しました (販売規約・免責事項「登場人物は全員20歳以上」準拠)" -f $strippedTags) -ForegroundColor Yellow
}
