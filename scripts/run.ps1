$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    throw 'Run .\scripts\setup.ps1 first.'
}
if (-not (Test-Path -LiteralPath 'assets/simulator/layout-32.json')) {
    throw 'Map files are missing. Run .\scripts\setup.ps1 first.'
}
& ./.venv/Scripts/python.exe src/app.py
