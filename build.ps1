$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path .venv\Scripts\python.exe)) { python -m venv .venv; if ($LASTEXITCODE) { throw 'venv failed' } }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install PyInstaller==6.22.3
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
Push-Location source
try { & $python -m unittest test_lab.py test_unit_names.py; if ($LASTEXITCODE) { throw 'Tests failed' } }
finally { Pop-Location }
& $python -m PyInstaller --noconfirm --onefile --windowed --name AoE4LocalLab source/app.py
if ($LASTEXITCODE) { throw 'Build failed' }
if (!(Test-Path dist\config)) { Copy-Item config dist\config -Recurse }
Copy-Item 使用说明.txt dist\使用说明.txt -Force
