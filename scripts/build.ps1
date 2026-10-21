$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    throw 'Run scripts/setup.ps1 and install PyInstaller in .venv first.'
}
& ./.venv/Scripts/python.exe -m PyInstaller --noconfirm 'packaging/Aniimo Tracker.spec'
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Write-Host 'Built dist/AniimoTracker.exe'
