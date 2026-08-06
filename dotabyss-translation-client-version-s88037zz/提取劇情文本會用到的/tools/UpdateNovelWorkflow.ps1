$ErrorActionPreference = "Stop"

$offlineName = ([string][char]0x96E2) + ([string][char]0x7DDA) + ([string][char]0x677F)
$baseDir = Join-Path "E:\" $offlineName
$repoDir = "D:\dotabyss-translation\GITHUB-dotabyss-translation\-X-\novels"
$outputMerged = Join-Path $baseDir "output\bundle_novels_merged"
$reportDir = Join-Path $baseDir "output\empty_translations"
$reportHtml = Join-Path $reportDir "empty_translations.html"
$csv = Join-Path $reportDir "empty_translations.csv"
$pendingDir = Join-Path $baseDir "output\pending_novels"
$pendingIndex = Join-Path $pendingDir "index.md"
$pythonExe = "C:\Users\huang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$filesDir = Join-Path $baseDir "files"
$outputDir = Join-Path $baseDir "output"

if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

function Invoke-Python {
    & $pythonExe @args | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

function Test-PythonModule {
    param([string]$ModuleName)
    & $pythonExe -c "import $ModuleName" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Run-PendingNovelCopy {
    Invoke-Python CopyPendingNovelFolders.py `
        --csv "$csv" `
        --novels "$outputMerged" `
        --output "$pendingDir"
}

function Ensure-OutputInputs {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

    $filesMasterData = Join-Path $filesDir "MasterData.json"
    $outputMasterData = Join-Path $outputDir "MasterData.json"
    if ((-not (Test-Path $outputMasterData)) -and (Test-Path $filesMasterData)) {
        Copy-Item -Path $filesMasterData -Destination $outputMasterData -Force
    }

    $filesAssets = Join-Path $filesDir "assets.json"
    $outputAssets = Join-Path $outputDir "assets.json"
    if (-not (Test-Path $filesAssets)) {
        $catalogBin = Join-Path $filesDir "catalog_1.bin"
        if (Test-Path $catalogBin) {
            Invoke-Python UnityCatalogReader.py "$catalogBin" "$filesAssets"
        }
    }
    if ((-not (Test-Path $outputAssets)) -and (Test-Path $filesAssets)) {
        Copy-Item -Path $filesAssets -Destination $outputAssets -Force
    }

    $filesDownloads = Join-Path $filesDir "downloads"
    $outputDownloads = Join-Path $outputDir "downloads"
    if ((-not (Test-Path $outputDownloads)) -and (Test-Path $filesDownloads)) {
        New-Item -ItemType Directory -Force -Path $outputDownloads | Out-Null
        Copy-Item -Path (Join-Path $filesDownloads "*") -Destination $outputDownloads -Recurse -Force
    }

    foreach ($requiredPath in @($outputMasterData, $outputAssets, $outputDownloads)) {
        if (-not (Test-Path $requiredPath)) {
            throw "Required input is missing: $requiredPath"
        }
    }
}

function Run-EmptyReport {
    Invoke-Python FindEmptyNovelTranslations.py `
        --novels "$outputMerged" `
        --output "$reportDir" `
        --lang zh_Hant.json

    if (-not (Test-Path $csv)) {
        return 0
    }

    return ((Import-Csv $csv) | Measure-Object).Count
}

Write-Host "[1/5] Downloading latest official data..." -ForegroundColor Cyan
Set-Location $filesDir
Invoke-Python DotAbyss.py
Ensure-OutputInputs

Write-Host "[2/5] Exporting novels and merging existing translations..." -ForegroundColor Cyan
Invoke-Python ExportBundleNovels.py `
    --masterdata (Join-Path $baseDir "output\MasterData.json") `
    --assets (Join-Path $baseDir "output\assets.json") `
    --downloads (Join-Path $baseDir "output\downloads") `
    --output "$outputMerged" `
    --merge-existing "$repoDir" `
    --value-mode empty `
    --include-bundle-only `
    --prune-output `
    --lang zh_Hant.json

Write-Host "[3/5] Creating initial empty-translation report..." -ForegroundColor Cyan
$emptyCount = Run-EmptyReport
Write-Host "Empty translations: $emptyCount" -ForegroundColor Yellow

if ($emptyCount -gt 0) {
    Write-Host "[4/5] Copying pending novel folders..." -ForegroundColor Magenta
    Run-PendingNovelCopy
    if (Test-Path $reportHtml) { Start-Process $reportHtml }
    if (Test-Path $pendingIndex) { Start-Process $pendingIndex }
} else {
    Write-Host "[4/5] No empty translations. Skipping pending folder copy." -ForegroundColor Green
}

Write-Host "[5/5] Rechecking empty translations..." -ForegroundColor Cyan
$emptyCount = Run-EmptyReport

while ($emptyCount -gt 0) {
    Write-Host ""
    Write-Host "Still has $emptyCount empty translations." -ForegroundColor Yellow
    Write-Host "Opening report and pending folder list. Fill JSON values, then return here." -ForegroundColor Yellow
    Run-PendingNovelCopy
    if (Test-Path $reportHtml) { Start-Process $reportHtml }
    if (Test-Path $pendingIndex) { Start-Process $pendingIndex }

    Read-Host "Press Enter after manual translation is complete"
    $emptyCount = Run-EmptyReport
}

Write-Host ""
Write-Host "No empty translations remain." -ForegroundColor Green
if (Test-Path $reportHtml) {
    Write-Host "Opening report for final human review." -ForegroundColor Gray
    Start-Process $reportHtml
}
Read-Host "Press Enter to sync zh_Hant.json back to repo"

Write-Host ""
Write-Host "Syncing zh_Hant.json back to repo..." -ForegroundColor Cyan
Get-ChildItem "$outputMerged" -Directory | ForEach-Object {
    $src = Join-Path $_.FullName "zh_Hant.json"
    $dstDir = Join-Path $repoDir $_.Name
    $dst = Join-Path $dstDir "zh_Hant.json"

    if (Test-Path $src) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        Copy-Item -Path $src -Destination $dst -Force
    }
}

Write-Host "Done." -ForegroundColor Green
pause
