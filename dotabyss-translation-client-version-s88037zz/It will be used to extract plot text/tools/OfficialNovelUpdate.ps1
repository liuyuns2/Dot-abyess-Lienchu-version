[CmdletBinding()]
param(
    [string]$UpdateDate = (Get-Date -Format "yyyy-MM-dd"),
    # 輸出根目錄；預設放在 repo 外的同層 dotabyss-output，避免污染版控
    [string]$BaseDir = "",
    # 翻譯 repo 根（含 -X- 與 Dot-abyess-Lienchu-version 的那層）；預設自動推導
    [string]$RepoRoot = "",
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── 路徑自動推導（本腳本位於 <repo根>/Dot-abyess-Lienchu-version/
#    dotabyss-translation-client-version-s88037zz/It will be used to extract plot text/tools/） ──
$filesDir = $PSScriptRoot
if (-not $filesDir) { $filesDir = Split-Path -Parent $MyInvocation.MyCommand.Path }

if (-not $RepoRoot) {
    # 從 tools/ 往上 4 層即 repo 根（含 -X- 與 Dot-abyess-Lienchu-version 的那層）
    $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $filesDir "..\..\..\..")).Path
}
if (-not $BaseDir) {
    # 預設輸出到 repo 根的同層 dotabyss-output（不進版控）
    $BaseDir = Join-Path (Split-Path -Parent $RepoRoot) "dotabyss-output"
}

Write-Host "工具目錄 : $filesDir"
Write-Host "Repo 根  : $RepoRoot"
Write-Host "輸出根   : $BaseDir"
Write-Host ""
$outputRoot = Join-Path $BaseDir "output"
$outputDir = Join-Path $outputRoot ("official_update_" + $UpdateDate)
$assetsJson = Join-Path $outputDir "assets.json"
$baseUrlFile = Join-Path $outputDir "base_url.txt"
$manifest = Join-Path $outputDir "text_novel_manifest.csv"
$downloads = Join-Path $outputDir "text_novel_downloads"
$novelsAll = Join-Path $outputDir "novels_all"
$pendingDir = Join-Path $outputDir "pending_novels"
$newFoldersDir = Join-Path $outputDir "new_folders_only"
$reportDir = Join-Path $outputDir "empty_translations"
$reportCsv = Join-Path $reportDir "empty_translations.csv"
$statsCsv = Join-Path $outputDir "pending_translation_stats.csv"
$validationLog = Join-Path $outputDir "pending_validation.txt"
$l2dReport = Join-Path $outputDir "l2d_changes.txt"

$primaryNovels = Join-Path $RepoRoot "-X-\novels"
$clientRoot = Join-Path $RepoRoot "Dot-abyess-Lienchu-version\dotabyss-translation-client-version-s88037zz"
$clientNovels = Join-Path $clientRoot "novels"
$clientUntranslated = Join-Path $clientRoot "novels_untranslated_only"

function Resolve-Python {
    param([string]$Requested)

    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    # venv 建在工具目錄或其上層都認
    $candidates += (Join-Path $filesDir ".venv\Scripts\python.exe")
    $candidates += (Join-Path (Split-Path -Parent $filesDir) ".venv\Scripts\python.exe")

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    throw "找不到 Python。請先在工具目錄建立 .venv（見 README.md），或用 -PythonExe 指定。"
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & $script:PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python 執行失敗（exit code $LASTEXITCODE）：$($Arguments -join ' ')"
    }
}

function Assert-Directory {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label 不存在：$Path"
    }
}

function Get-L2DIds {
    param([string]$Path)
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $reader = [System.IO.StreamReader]::new($Path, [System.Text.Encoding]::UTF8, $true, 1048576)
    try {
        while (($line = $reader.ReadLine()) -ne $null) {
            foreach ($match in [regex]::Matches($line, '(?i)l2d[_-](\d{8,14})')) {
                [void]$set.Add($match.Groups[1].Value)
            }
        }
    }
    finally {
        $reader.Dispose()
    }
    return $set
}

function Write-L2DChanges {
    $previous = Get-ChildItem -LiteralPath $outputRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -ne $outputDir -and
            $_.Name -like "official_update_*" -and
            (Test-Path -LiteralPath (Join-Path $_.FullName "assets.json"))
        } |
        Sort-Object Name -Descending |
        Select-Object -First 1

    if (-not $previous) {
        @("No previous official_update folder was available for comparison.") |
            Set-Content -LiteralPath $l2dReport -Encoding UTF8
        return
    }

    $previousAssets = Join-Path $previous.FullName "assets.json"
    $oldIds = Get-L2DIds $previousAssets
    $newIds = Get-L2DIds $assetsJson
    $added = @($newIds | Where-Object { -not $oldIds.Contains($_) } | Sort-Object)
    $removed = @($oldIds | Where-Object { -not $newIds.Contains($_) } | Sort-Object)

    $lines = @(
        "Previous: $($previous.FullName)",
        "Current:  $outputDir",
        "Old L2D IDs: $($oldIds.Count)",
        "New L2D IDs: $($newIds.Count)",
        "Added: $($added.Count)",
        "Removed: $($removed.Count)",
        "",
        "[ADDED]"
    )
    $lines += $added
    $lines += @("", "[REMOVED]")
    $lines += $removed
    $lines | Set-Content -LiteralPath $l2dReport -Encoding UTF8
}

Assert-Directory $filesDir "工具資料夾"
Assert-Directory $primaryNovels "主要翻譯 novels"
Assert-Directory $clientNovels "客戶端 novels"
Assert-Directory $clientUntranslated "客戶端 novels_untranslated_only"

$script:PythonExe = Resolve-Python $PythonExe
$localPackages = Join-Path $filesDir ".python_packages"
if (Test-Path -LiteralPath $localPackages -PathType Container) {
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$localPackages;$($env:PYTHONPATH)"
    }
    else {
        $env:PYTHONPATH = $localPackages
    }
}

& $script:PythonExe -c "import requests, msgpack, Crypto, rich, UnityPy"
if ($LASTEXITCODE -ne 0) {
    throw "Python 缺少 requests/msgpack/pycryptodome/rich/UnityPy。請依交接手冊安裝。"
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
Set-Location $filesDir

Write-Host "[1/9] 抓取最新官方 R18 MasterData 與 catalog..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "FetchLatestCatalogOnly.py"),
    "--output", $outputDir
)

Write-Host "[2/9] 建立小說文本 bundle 清單..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "PrepareTextNovelDownloadManifest.py"),
    "--assets", $assetsJson,
    "--output", $manifest
)

Write-Host "[3/9] 下載小說文本 bundle..." -ForegroundColor Cyan
$baseUrl = (Get-Content -LiteralPath $baseUrlFile -Raw -Encoding UTF8).Trim()
Invoke-Python @(
    (Join-Path $filesDir "DownloadCatalogBundles.py"),
    "--manifest", $manifest,
    "--output", $downloads,
    "--base-url", $baseUrl,
    "--threads", "16",
    "--retries", "5"
)

Write-Host "[4/9] 解出 zh_Hant.json 與官方原始 TXT..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "ExportCatalogNovelTexts.py"),
    "--assets", $assetsJson,
    "--downloads", $downloads,
    "--output", $outputDir,
    "--value-mode", "empty",
    "--write-raw"
)

Write-Host "[5/9] 以日文 key 套用三個現有來源的既有翻譯..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "FillPendingFromTranslationMemory.py"),
    "--pending", $novelsAll,
    "--memory-dir", $primaryNovels,
    "--memory-dir", $clientNovels,
    "--memory-dir", $clientUntranslated,
    "--lang", "zh_Hant.json"
)

Write-Host "[6/9] 產生空值報告（包含既有資料夾內的新句子）..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "FindEmptyNovelTranslations.py"),
    "--novels", $novelsAll,
    "--output", $reportDir,
    "--lang", "zh_Hant.json"
)

Write-Host "[7/9] 複製所有仍需處理的資料夾..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "CopyPendingNovelFolders.py"),
    "--csv", $reportCsv,
    "--novels", $novelsAll,
    "--output", $pendingDir
)
Invoke-Python @(
    (Join-Path $filesDir "CopyNovelFoldersMissingFromRepo.py"),
    "--source", $novelsAll,
    "--repo", $primaryNovels,
    "--exclude", $clientNovels,
    "--exclude", $clientUntranslated,
    "--output", $newFoldersDir
)

Write-Host "[8/9] 統計與驗證 pending_novels..." -ForegroundColor Cyan
Invoke-Python @(
    (Join-Path $filesDir "AnalyzePendingNovelTranslations.py"),
    "--novels", $pendingDir,
    "--output", $statsCsv,
    "--lang", "zh_Hant.json"
)
$validation = & $script:PythonExe (Join-Path $filesDir "ValidatePendingNovelTranslations.py") --novels $pendingDir 2>&1
$validation | Set-Content -LiteralPath $validationLog -Encoding UTF8
if ($LASTEXITCODE -ne 0) {
    throw "pending 驗證腳本執行失敗，請查看：$validationLog"
}

Write-Host "[9/9] 比對上一版 L2D ID..." -ForegroundColor Cyan
Write-L2DChanges

$catalogInfo = Get-Content -LiteralPath (Join-Path $outputDir "latest_catalog_info.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$novelSummary = Get-Content -LiteralPath (Join-Path $outputDir "novel_export_summary.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$pendingIndex = Get-Content -LiteralPath (Join-Path $pendingDir "index.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$newIndex = Get-Content -LiteralPath (Join-Path $newFoldersDir "index.json") -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Host ""
Write-Host "更新完成" -ForegroundColor Green
Write-Host "Asset version : $($catalogInfo.asset_version)"
Write-Host "MasterData    : $($catalogInfo.master_data_version)"
Write-Host "Scripts       : $($novelSummary.exported_scripts)"
Write-Host "Text entries  : $($novelSummary.exported_text_entries)"
Write-Host "Pending folders / empty entries : $($pendingIndex.folders) / $($pendingIndex.empty_entries)"
Write-Host "Entirely new folders            : $($newIndex.missing_after_exclude)"
Write-Host ""
Write-Host "待處理：$pendingDir" -ForegroundColor Yellow
Write-Host "全新資料夾：$newFoldersDir"
Write-Host "空值報告：$(Join-Path $reportDir 'empty_translations.html')"
Write-Host "L2D 差異：$l2dReport"
Write-Host "本腳本不會呼叫翻譯 API、不會產生 zh_Hans，也不會自動同步或提交 repo。"
