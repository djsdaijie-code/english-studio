param(
    [switch]$DebugBuild,
    [switch]$SkipTests,
    [switch]$SkipZip,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $ProjectRoot ".venv\Scripts\pyinstaller.exe"
$Spec = Join-Path $ProjectRoot "EnglishTypingTrainer.spec"
$DistRoot = Join-Path $ProjectRoot $(if ($DebugBuild) { "dist-debug" } else { "dist" })
$WorkRoot = Join-Path $ProjectRoot $(if ($DebugBuild) { "build-debug" } else { "build" })
$AppDir = Join-Path $DistRoot "EnglishTypingTrainer"
$Exe = Join-Path $AppDir "EnglishTypingTrainer.exe"
$ReleaseDir = Join-Path $ProjectRoot "release"
$ZipPath = Join-Path $ReleaseDir "EnglishTypingTrainer-0.1.0-windows-x64-portable.zip"

if (-not (Test-Path -LiteralPath $Python)) { throw "未找到 Python 3.14 虚拟环境：$Python" }
if (-not (Test-Path -LiteralPath $PyInstaller)) { throw "未找到 PyInstaller：$PyInstaller" }
if (-not (Test-Path -LiteralPath $Spec)) { throw "未找到 spec 文件：$Spec" }

$PythonVersion = & $Python --version
if ($LASTEXITCODE -ne 0 -or $PythonVersion -notmatch "Python 3\.14\.") {
    throw "打包必须使用 Python 3.14，当前版本：$PythonVersion"
}

$GitStatus = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw "Git 状态检查失败。" }
if ($GitStatus.Count -gt 0 -and -not $AllowDirty) {
    throw "Git 工作区不干净。请先提交改动，或仅在开发验证时显式使用 -AllowDirty。"
}
Write-Host "Git 状态检查完成。"

if (-not $SkipTests) {
    $PreviousDataDir = $env:ENGLISH_TYPING_TRAINER_DATA_DIR
    try {
        $env:ENGLISH_TYPING_TRAINER_DATA_DIR = Join-Path $ProjectRoot "phase5a_runtime\package-tests"
        & $Python -m pytest -v -p no:cacheprovider
        if ($LASTEXITCODE -ne 0) { throw "pytest 未通过，停止打包。" }
    }
    finally {
        $env:ENGLISH_TYPING_TRAINER_DATA_DIR = $PreviousDataDir
    }
}

$env:ETT_DEBUG_CONSOLE = $(if ($DebugBuild) { "1" } else { "0" })
& $PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $WorkRoot $Spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败。" }
if (-not (Test-Path -LiteralPath $Exe)) { throw "构建后未找到可执行文件：$Exe" }

$RequiredPatterns = @(
    "EnglishTypingTrainer.exe",
    "light.qss",
    "dark.qss",
    "qwindows.dll",
    "Qt6Charts.dll",
    "Qt6Svg.dll"
)
foreach ($Pattern in $RequiredPatterns) {
    if (-not (Get-ChildItem -LiteralPath $AppDir -Recurse -File | Where-Object Name -eq $Pattern | Select-Object -First 1)) {
        throw "发布目录缺少必要文件：$Pattern"
    }
}

$Forbidden = Get-ChildItem -LiteralPath $AppDir -Recurse -Force | Where-Object {
    $_.Name -in @(".git", ".venv", "tests", "src", "runtime_data", "workspace_data") -or
    (-not $_.PSIsContainer -and $_.Extension -in @(".db", ".log", ".py", ".pyc"))
}
if ($Forbidden) {
    $Forbidden | ForEach-Object { Write-Host "禁止文件：$($_.FullName)" }
    throw "发布目录包含禁止内容。"
}

if (-not $DebugBuild -and -not $SkipZip) {
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
    Compress-Archive -LiteralPath $AppDir -DestinationPath $ZipPath -CompressionLevel Optimal
    $Hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $HashLine = "$Hash  EnglishTypingTrainer-0.1.0-windows-x64-portable.zip`n"
    [IO.File]::WriteAllText((Join-Path $ReleaseDir "SHA256SUMS.txt"), $HashLine, (New-Object Text.UTF8Encoding($false)))
    Write-Host "ZIP SHA-256: $Hash"
}

$Files = @(Get-ChildItem -LiteralPath $AppDir -Recurse -File)
$Bytes = ($Files | Measure-Object Length -Sum).Sum
Write-Host "构建完成：$Exe"
Write-Host "文件数量：$($Files.Count)"
Write-Host "目录大小：$Bytes bytes"