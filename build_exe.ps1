$ErrorActionPreference = "Stop"

$appName = "LogoAdder"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $root

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $appName `
  --icon "myicon.ico" `
  --add-data "myicon.ico;." `
  --add-data "Title Logo.png;." `
  --hidden-import "PySide6" `
  --hidden-import "qt_material" `
  --hidden-import "PIL._tkinter_finder" `
  "LogoAdder.py"

Write-Host "Built: $root\dist\$appName.exe"
