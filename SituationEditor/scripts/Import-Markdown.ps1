<#
.SYNOPSIS
  既存のプロンプト資産 (Tentacle*.md 等) をシチュエーションライブラリ (situations.json) に変換する。

.DESCRIPTION
  パース規則:
    - ## / ### 見出し、<details><summary>名前</summary> を新しいシチュエーションの開始とみなす
    - ```コードブロック``` 内の各行・「- 」箇条書き・素のタグ行を variations に追加
    - [X] / [Y] を含む行はプレースホルダを除去して base に設定
    - <!-- HTMLコメント --> 内は無視
    - ASCII文字を含まない行 (日本語ラベルのみ等) はスキップ
  完全変換は狙わない。取り込み後に editor.html で整理する前提。

.EXAMPLE
  .\Import-Markdown.ps1                          # 既定ファイル群を取り込み
  .\Import-Markdown.ps1 -Path C:\temp\sell\Tentacle4.md
  .\Import-Markdown.ps1 -Replace                 # 既存の取り込み分を作り直す
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [string]$OutFile = (Join-Path $PSScriptRoot '..\data\situations.json'),
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'
$sellDir = 'C:\temp\sell'

if (-not $Path) {
    $Path = @('Tentacle5.md', 'Tentacle6.md', '連続.md', 'ランダム.md') |
        ForEach-Object { Join-Path $sellDir $_ } | Where-Object { Test-Path $_ }
}

function Clean-Tagline {
    param([string]$s)
    $s = $s -replace '\[X\]|\[Y\]', ''           # キャラ差し込みプレースホルダ除去
    $s = $s -replace '\s+', ' '                  # 連続空白を1つに
    $s = $s -replace '(\s*,\s*)+', ', '          # 連続カンマを1つに
    $s = $s.Trim().Trim(',').Trim()
    return $s
}

function New-Slug {
    param([string]$name, [hashtable]$used, [string]$prefix, [int]$index)
    $ascii = ($name -replace '[^a-zA-Z0-9]+', '_').Trim('_').ToLower()
    if ([string]::IsNullOrWhiteSpace($ascii)) { $ascii = '{0}_{1:00}' -f $prefix, $index }
    $slug = $ascii
    $n = 2
    while ($used.ContainsKey($slug)) { $slug = '{0}_{1}' -f $ascii, $n; $n++ }
    $used[$slug] = $true
    return $slug
}

# 既存ライブラリの読み込み
$existing = [System.Collections.Generic.List[object]]::new()
$usedIds = @{}
if ((Test-Path $OutFile) -and -not $Replace) {
    $doc = Get-Content $OutFile -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($s in $doc.situations) { $existing.Add($s); $usedIds[$s.id] = $true }
}

$imported = [System.Collections.Generic.List[object]]::new()

foreach ($file in $Path) {
    $prefix = [System.IO.Path]::GetFileNameWithoutExtension($file).ToLower() -replace '[^a-z0-9]', ''
    $lines = Get-Content $file -Encoding utf8
    Write-Host "取り込み中: $file" -ForegroundColor Cyan

    $inComment = $false
    $inFence = $false
    $curName = $null
    $curBase = ''
    $curVars = [System.Collections.Generic.List[string]]::new()
    $count = 0

    $flush = {
        if ($curName -and ($curVars.Count -gt 0 -or $curBase)) {
            $script:count++
            $imported.Add([pscustomobject]@{
                id            = New-Slug -name $curName -used $usedIds -prefix $prefix -index $script:count
                name          = $curName
                tags          = @($prefix)
                base          = $curBase
                variations    = @($curVars)
                defaultOutfit = 'normal'
                defaultSize   = 'portrait'
            })
        }
        $script:curBase = ''
        $script:curVars = [System.Collections.Generic.List[string]]::new()
    }

    foreach ($raw in $lines) {
        $line = $raw.Trim()

        # HTMLコメントの処理 (複数行対応)
        if ($inComment) {
            if ($line -match '-->') { $inComment = $false }
            continue
        }
        if ($line -match '<!--') {
            if ($line -notmatch '-->') { $inComment = $true }
            continue
        }

        # コードフェンス (``` の表記ゆれ `` も終端扱い)
        if ($line -match '^`{2,3}\s*\w*\s*$') { $inFence = -not $inFence; continue }

        # 見出し → 新シチュエーション
        $isHeading = $false
        if ($line -match '^#{1,4}\s+(.+)$') { $newName = $Matches[1].Trim(); $isHeading = $true }
        elseif ($line -match '<details><summary>(.+?)</summary>') { $newName = $Matches[1].Trim(); $isHeading = $true }
        if ($isHeading) {
            & $flush
            $curName = $newName
            continue
        }

        if ($line -match '^</?details>' -or $line -eq '---' -or [string]::IsNullOrWhiteSpace($line)) { continue }

        if (-not $curName) { $curName = "($prefix 冒頭)" }

        # base 行 (キャラ差し込みプレースホルダ付き)
        if ($line -match '\[X\]|\[Y\]') {
            $cleaned = Clean-Tagline $line
            if ($cleaned) {
                if ($curBase) { $curBase = "$curBase, $cleaned" } else { $curBase = $cleaned }
            }
            continue
        }

        # 箇条書き → 中身を取り出す
        if ($line -match '^-\s+(.*)$') { $line = $Matches[1] }

        # ASCII文字を含まない行 (日本語ラベル等) はスキップ
        if ($line -notmatch '[a-zA-Z]') { continue }

        $cleaned = Clean-Tagline $line
        if ($cleaned) { $curVars.Add($cleaned) }
    }
    & $flush
    Write-Host ("  → {0} シチュエーション" -f $count)
}

foreach ($s in $imported) { $existing.Add($s) }

$outDir = Split-Path $OutFile -Parent
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force $outDir | Out-Null }
@{ situations = @($existing) } | ConvertTo-Json -Depth 6 |
    Out-File $OutFile -Encoding utf8

Write-Host ("完了: 合計 {0} シチュエーション → {1}" -f $existing.Count, (Resolve-Path $OutFile)) -ForegroundColor Green
