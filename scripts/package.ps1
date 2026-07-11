$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Recreate it first with Python 3.14."
}

if (-not (Test-Path ".\.venv\Scripts\pyinstaller.exe")) {
    Write-Error "PyInstaller is not installed in .venv yet."
}

Write-Host "Packaging is planned for phase 4. A .spec file has not been added yet."
