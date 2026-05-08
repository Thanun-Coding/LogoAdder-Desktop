$ErrorActionPreference = "Stop"

$appName = "LogoAdder"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Set-Location $root

Write-Host "Using Python: $python"

$distRoot = Join-Path $root "dist"
Remove-Item -LiteralPath (Join-Path $distRoot "$appName.exe") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $distRoot $appName) -Recurse -Force -ErrorAction SilentlyContinue

& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $appName `
  --icon "assets\myicon.ico" `
  --add-data "assets\myicon.ico;assets" `
  --add-data "assets\Title Logo.png;assets" `
  --add-data "assets\KhmerOSmuollight.ttf;assets" `
  --add-data "assets\KhmerOSsiemreap.ttf;assets" `
  --hidden-import "PySide6" `
  --exclude-module "qt_material" `
  --exclude-module "PyQt6" `
  --exclude-module "PyQt5" `
  --exclude-module "PySide2" `
  --exclude-module "tkinter" `
  --exclude-module "numpy" `
  "LogoAdder.py"

Write-Host "Built: $root\dist\$appName.exe"
