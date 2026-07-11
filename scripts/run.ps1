$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Recreate it first with Python 3.14."
}

& ".\.venv\Scripts\python.exe" ".\main.py"
