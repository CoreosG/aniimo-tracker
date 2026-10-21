$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    throw 'Run .\setup.ps1 first.'
}
if (-not (Test-Path -LiteralPath 'assets/simulator/layout-32.json')) {
    throw 'Map files are missing. Run .\setup.ps1 first.'
}
& ./.venv/Scripts/python.exe app.py
