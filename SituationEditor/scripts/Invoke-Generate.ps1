<#
.SYNOPSIS
  レシピ (recipes\*.json) を読み込み、SD WebUI API (txt2img) で一括生成する。

.DESCRIPTION
  プロンプト合成順:
    qualityHeader   <char.base>, <outfit>   <situation.base>, <variation>, <commonTail>
  Dynamic Prompts 拡張がサーバ側で {a|b} / __wildcard__ を毎回展開する。
  生成PNGには API レスポンスの infotext を parameters チャンクとして埋め込むため、
  WebUI の PNG Info および Export\extract_prompts.py と互換。

.EXAMPLE
  .\Invoke-Generate.ps1 -Recipe ..\recipes\yuuka_vol1.json -DryRun   # プロンプト確認のみ
  .\Invoke-Generate.ps1 -Recipe ..\recipes\yuuka_vol1.json -Test     # 各step 1枚を output\<title>\_test に生成し、完了後フォルダを開く
  .\Invoke-Generate.ps1 -Recipe ..\recipes\yuuka_vol1.json           # 本実行
  .\Invoke-Generate.ps1 -Recipe ..\recipes\yuuka_vol1.json -Resume   # 既存ファイルをスキップして再開
  .\Invoke-Generate.ps1 -Recipe ..\recipes\yuuka_vol1.json -From 3   # step 3 から実行

.NOTES
  シード: レシピの "seedMode" = random / fixed (全画像同一) / increment (通しで+1) + "seed"。
  step ごとに "seedMode" (inherit/fixed/increment/random) + "seed" で上書き可能。
  HiresFix: レシピの "hiresFix" (bool)。倍率・アップスケーラーは settings.json の generation。
  固定シードは同一プロンプト・同一設定で完全に再現されることを確認済み。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Recipe,
    [string]$DataDir = (Join-Path $PSScriptRoot '..\data'),
    [string]$OutDir = (Join-Path $PSScriptRoot '..\output'),
    [switch]$DryRun,
    [switch]$Resume,
    [switch]$Test,
    [int]$From = 1
)

$ErrorActionPreference = 'Stop'

# ---------- 設定・データ読み込み ----------
function Read-Json([string]$p) { Get-Content $p -Raw -Encoding utf8 | ConvertFrom-Json }

$settings   = Read-Json (Join-Path $DataDir 'settings.json')
$characters = (Read-Json (Join-Path $DataDir 'characters.json')).characters
$situations = (Read-Json (Join-Path $DataDir 'situations.json')).situations
$recipeDoc  = Read-Json $Recipe

$char = $characters | Where-Object id -eq $recipeDoc.character
if (-not $char) { throw "キャラ '$($recipeDoc.character)' が characters.json に見つかりません" }

$negName = if ($recipeDoc.negative) { $recipeDoc.negative } else { $settings.defaultNegative }
$negative = $settings.negativePresets.$negName
if ($null -eq $negative) { $negative = $negName }   # プリセット名でなければ生テキストとして扱う

$situMap = @{}
foreach ($s in $situations) { $situMap[$s.id] = $s }

# 表情プリセット (faces.json)
$faceMap = @{}
$facesFile = Join-Path $DataDir 'faces.json'
if (Test-Path $facesFile) {
    foreach ($f in (Read-Json $facesFile).faces) { $faceMap[$f.id] = $f.tags }
}

# シード設定
#   レシピ一括: seedMode = random / fixed (全画像同一) / increment (通しで+1) + seed
#   step上書き: seedMode = inherit (一括に従う) / fixed / increment (行内で+1) / random + seed
$recipeSeedVal = -1
if ($null -ne $recipeDoc.seed) { $recipeSeedVal = [long]$recipeDoc.seed }
$recipeSeedMode = if ($recipeDoc.seedMode) { $recipeDoc.seedMode }
                  elseif ($recipeSeedVal -ge 0) { 'increment' }   # 旧形式レシピとの互換
                  else { 'random' }

# HiresFix: レシピ単位の ON/OFF (未指定なら settings.generation.enable_hr)
$enableHr = if ($null -ne $recipeDoc.hiresFix) { [bool]$recipeDoc.hiresFix } else { [bool]$settings.generation.enable_hr }

# Calibrated Spectrum 拡張: レシピ単位の ON/OFF (未指定なら有効)
# 注意: alwayson_scripts で明示しない場合、API経由ではUI既定 (無効) になる
$specEnabled = if ($null -ne $recipeDoc.spectrum) { [bool]$recipeDoc.spectrum } else { $true }
$spec = $settings.generation.spectrum
if (-not $spec) {   # 旧 settings.json 互換
    $spec = [pscustomobject]@{ w = 0.25; m = 6; lam = 0.5; window_size = 2; flex_window = 0.0; warmup_steps = 6; stop_caching_step = 0.9; enable_calibration = $true; calibration_strength = 0.5 }
}
$spectrumArgs = @{
    'Calibrated Spectrum' = @{
        args = @($specEnabled, $spec.w, $spec.m, $spec.lam, $spec.window_size, $spec.flex_window,
                 $spec.warmup_steps, $spec.stop_caching_step, [bool]$spec.enable_calibration, $spec.calibration_strength)
    }
}

function Join-Tags { ($args | Where-Object { $_ -and $_.Trim() }) -join ', ' }

# ---------- プロンプト組み立て ----------
$jobs = [System.Collections.Generic.List[object]]::new()
$stepIndex = 0
foreach ($step in $recipeDoc.steps) {
    $stepIndex++
    $situ = $situMap[$step.situation]
    if (-not $situ) { throw "シチュエーション '$($step.situation)' が situations.json に見つかりません (step $stepIndex)" }

    $outfitKey = if ($step.outfit) { $step.outfit } else { $situ.defaultOutfit }
    $outfit = $char.outfits.$outfitKey
    if ($null -eq $outfit) { throw "キャラ '$($char.id)' に服装 '$outfitKey' がありません (step $stepIndex)" }

    $sizeKey = if ($step.size) { $step.size } else { $situ.defaultSize }
    $size = $settings.sizes.$sizeKey
    if (-not $size) { throw "サイズプリセット '$sizeKey' が settings.json にありません (step $stepIndex)" }

    $vars = @($situ.variations)
    if ($vars.Count -eq 0) { $vars = @('') }
    $mode = if ($step.variationMode) { $step.variationMode } else { 'cycle' }

    $nn = '{0:00}' -f $stepIndex
    $count = [int]$step.count
    if ($Test) { $count = 1 }   # テストモード: 各stepから1枚だけ
    for ($i = 0; $i -lt $count; $i++) {
        $variation = if ($mode -eq 'random') { $vars | Get-Random } else { $vars[$i % $vars.Count] }
        # 表情: step上書き ('inherit'/未指定=シチュエーション既定, 'none'=なし)。server.py と同一仕様
        $faceKey = if ($step.face) { $step.face } else { 'inherit' }
        if ($faceKey -eq 'inherit') { $faceKey = if ($situ.defaultFace) { $situ.defaultFace } else { 'none' } }
        $faceTags = ''
        if ($faceKey -ne 'none') {
            if (-not $faceMap.ContainsKey($faceKey)) { throw "表情 '$faceKey' が faces.json にありません (step $stepIndex)" }
            $faceTags = $faceMap[$faceKey]
        }

        # useBreak=false (既定) は WebUI と同じ改行区切り (server.py と同一仕様)
        $sep = if ($settings.useBreak) { "`nBREAK`n" } else { "`n" }
        $prompt = (@(
            $settings.qualityHeader,(Join-Tags $char.base $outfit),(Join-Tags $faceTags $situ.base $variation $settings.commonTail)
        ) | Where-Object { $_ -and $_.Trim() }) -join $sep

        # シチュエーション固有の追加ネガティブ (例: 騎乗位の 1boy, penis)
        $jobNegative = if ($situ.negativeExtra) { "$negative, $($situ.negativeExtra)" } else { $negative }

        # シード解決: step上書き > レシピ一括。increment は step指定なら行内+i、一括なら通し番号
        $stepOwn  = [bool]($step.seedMode -and $step.seedMode -ne 'inherit')
        $mode     = if ($stepOwn) { $step.seedMode } else { $recipeSeedMode }
        $seedBase = if ($stepOwn -and $null -ne $step.seed) { [long]$step.seed } else { $recipeSeedVal }
        $jobSeed  = -1
        if ($seedBase -ge 0) {
            switch ($mode) {
                'fixed'     { $jobSeed = $seedBase }
                'increment' { $jobSeed = $seedBase + $(if ($stepOwn) { $i } else { $jobs.Count }) }
            }
        }

        $jobs.Add([pscustomobject]@{
            step      = $stepIndex
            nn        = $nn
            situId    = $situ.id
            seq       = $i + 1
            width     = $size.width
            height    = $size.height
            prompt    = $prompt
            negative  = $jobNegative
            seed      = $jobSeed
            file      = ('{0}_{1}_{2:000}.png' -f $char.id, $nn, ($i + 1))
            folder    = ('{0}_{1}' -f $nn, $situ.id)
        })
    }
}

$title = $recipeDoc.title
$workDir = Join-Path $OutDir $title
if ($Test) { $workDir = Join-Path $workDir '_test' }
New-Item -ItemType Directory -Force $workDir | Out-Null

$seedLabel = switch ($recipeSeedMode) {
    'fixed'     { "固定 $recipeSeedVal" }
    'increment' { "インクリメント $recipeSeedVal〜" }
    default     { 'ランダム' }
}
$modeLabel = if ($Test) { ' [テスト: 各step 1枚]' } else { '' }
$hrLabel = if ($enableHr) { ' / HiresFix: ON' } else { '' }
$hrLabel += if ($specEnabled) { ' / Spectrum: ON' } else { ' / Spectrum: OFF' }
Write-Host ("レシピ: {0} / キャラ: {1} / 合計 {2} 枚 ({3} step) / シード一括: {4}{5}{6}" -f $title, $char.id, $jobs.Count, $stepIndex, $seedLabel, $hrLabel, $modeLabel) -ForegroundColor Cyan

# ---------- DryRun: plan.txt 出力のみ ----------
if ($DryRun) {
    $planFile = Join-Path $workDir 'plan.txt'
    $sb = [System.Text.StringBuilder]::new()
    foreach ($j in $jobs) {
        $negNote = if ($j.negative -ne $negative) { '  [+negativeExtra]' } else { '' }
        [void]$sb.AppendLine("===== $($j.folder)\$($j.file)  [$($j.width)x$($j.height)]$negNote")
        [void]$sb.AppendLine($j.prompt)
        [void]$sb.AppendLine()
    }
    [void]$sb.AppendLine("===== negative ($negName)")
    [void]$sb.AppendLine($negative)
    $sb.ToString() | Out-File $planFile -Encoding utf8
    Write-Host "DryRun: $planFile に合成プロンプトを出力しました" -ForegroundColor Green
    return
}

# ---------- PNG parameters チャンク埋め込み ----------
$crcTable = [uint32[]]::new(256)
for ($i = 0; $i -lt 256; $i++) {
    $c = [uint32]$i
    for ($k = 0; $k -lt 8; $k++) {
        if ($c -band 1) { $c = [uint32]3988292384 -bxor ($c -shr 1) } else { $c = $c -shr 1 }
    }
    $crcTable[$i] = $c
}
function Get-Crc32([byte[]]$data) {
    $c = [uint32]::MaxValue
    foreach ($b in $data) { $c = $crcTable[($c -bxor $b) -band 0xFF] -bxor ($c -shr 8) }
    return $c -bxor [uint32]::MaxValue
}
function Add-PngParameters([byte[]]$png, [string]$text) {
    # IHDR 直後 (offset 33) に parameters チャンクを挿入する
    $keyword = [System.Text.Encoding]::ASCII.GetBytes('parameters')
    $isLatin1 = -not ($text.ToCharArray() | Where-Object { [int]$_ -gt 255 } | Select-Object -First 1)
    if ($isLatin1) {
        $type = [System.Text.Encoding]::ASCII.GetBytes('tEXt')
        $body = $keyword + [byte]0 + [System.Text.Encoding]::Latin1.GetBytes($text)
    } else {
        $type = [System.Text.Encoding]::ASCII.GetBytes('iTXt')
        $body = $keyword + [byte[]]@(0, 0, 0, 0, 0) + [System.Text.Encoding]::UTF8.GetBytes($text)
    }
    $lenBytes = [BitConverter]::GetBytes([uint32]$body.Length)
    if ([BitConverter]::IsLittleEndian) { [array]::Reverse($lenBytes) }
    $crcBytes = [BitConverter]::GetBytes((Get-Crc32 ($type + $body)))
    if ([BitConverter]::IsLittleEndian) { [array]::Reverse($crcBytes) }

    $ms = [System.IO.MemoryStream]::new()
    $ms.Write($png, 0, 33)
    $ms.Write($lenBytes, 0, 4); $ms.Write($type, 0, 4)
    $ms.Write($body, 0, $body.Length); $ms.Write($crcBytes, 0, 4)
    $ms.Write($png, 33, $png.Length - 33)
    return $ms.ToArray()
}

# ---------- 生成ループ ----------
$gen = $settings.generation
$api = "$($settings.apiUrl)/sdapi/v1/txt2img"
$logFile = Join-Path $workDir 'generation_log.jsonl'

$targets = @($jobs | Where-Object { $_.step -ge $From })
$done = 0
$skipped = 0
$sw = [System.Diagnostics.Stopwatch]::StartNew()

foreach ($j in $targets) {
    $folder = Join-Path $workDir $j.folder
    New-Item -ItemType Directory -Force $folder | Out-Null
    $outFile = Join-Path $folder $j.file

    if ($Resume -and (Test-Path $outFile)) { $skipped++; $done++; continue }

    $payload = @{
        prompt                               = $j.prompt
        negative_prompt                      = $j.negative
        width                                = $j.width
        height                               = $j.height
        steps                                = $gen.steps
        cfg_scale                            = $gen.cfg_scale
        distilled_cfg_scale                  = if ($null -ne $gen.shift) { $gen.shift } else { 3.5 }   # Forge NeoのShift
        hr_distilled_cfg                     = if ($null -ne $gen.shift) { $gen.shift } else { 3.5 }
        sampler_name                         = $gen.sampler_name
        scheduler                            = $gen.scheduler
        seed                                 = $j.seed
        batch_size                           = 1
        n_iter                               = 1
        enable_hr                            = $enableHr
        hr_scale                             = $gen.hr_scale
        hr_upscaler                          = $gen.hr_upscaler
        hr_additional_modules                = @('Use same choices')   # Forge Neo: 未指定だと500、空配列だとモジュール(VAE等)が外れる
        denoising_strength                   = $gen.denoising_strength
        override_settings                    = @{ CLIP_stop_at_last_layers = $gen.clip_skip }
        override_settings_restore_afterwards = $true
        alwayson_scripts                     = $spectrumArgs
        save_images                          = $false
        send_images                          = $true
    } | ConvertTo-Json -Depth 5

    $resp = $null
    for ($try = 1; $try -le 3; $try++) {
        try {
            $resp = Invoke-RestMethod -Uri $api -Method Post -Body $payload -ContentType 'application/json' -TimeoutSec 900
            break
        } catch {
            Write-Warning ("{0} 失敗 (試行 {1}/3): {2}" -f $j.file, $try, $_.Exception.Message)
            if ($try -eq 3) { throw }
            Start-Sleep -Seconds (10 * $try)
        }
    }

    $info = $resp.info | ConvertFrom-Json
    $infotext = if ($info.infotexts) { $info.infotexts[0] } else { '' }
    $png = [Convert]::FromBase64String($resp.images[0])
    if ($infotext) { $png = Add-PngParameters $png $infotext }
    [System.IO.File]::WriteAllBytes($outFile, $png)

    @{ file = "$($j.folder)/$($j.file)"; seed = $info.seed; prompt = $j.prompt } |
        ConvertTo-Json -Compress -Depth 3 | Add-Content $logFile -Encoding utf8

    $done++
    $avg = $sw.Elapsed.TotalSeconds / [Math]::Max(1, ($done - $skipped))
    $eta = [TimeSpan]::FromSeconds($avg * ($targets.Count - $done))
    Write-Host ("[{0}/{1}] {2}  seed={3}  残り目安 {4:hh\:mm\:ss}" -f $done, $targets.Count, $j.file, $info.seed, $eta)
}

$sw.Stop()
Write-Host ("完了: {0} 枚 (スキップ {1}) / 所要 {2:hh\:mm\:ss} → {3}" -f $done, $skipped, $sw.Elapsed, $workDir) -ForegroundColor Green
if ($Test) { Invoke-Item $workDir }   # テスト結果をエクスプローラーで開く
