$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path .venv\Scripts\python.exe)) { python -m venv .venv; if ($LASTEXITCODE) { throw 'venv failed' } }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install PyInstaller==6.22.3
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
Push-Location source
try { & $python -m unittest discover -p 'test_*.py'; if ($LASTEXITCODE) { throw 'Tests failed' } }
finally { Pop-Location }
& $python -m PyInstaller --noconfirm --onefile --windowed --name AoE4LocalLab source/app.py
if ($LASTEXITCODE) { throw 'Build failed' }
New-Item -ItemType Directory -Path dist\config -Force | Out-Null
foreach ($name in @('unit_names.json', 'settings.json')) {
    $destination = Join-Path 'dist\config' $name
    if (!(Test-Path -LiteralPath $destination)) { Copy-Item -LiteralPath (Join-Path 'config' $name) -Destination $destination }
}
New-Item -ItemType Directory -Path dist\docs -Force | Out-Null
Copy-Item README.md,AGENTS.md dist -Force
Copy-Item docs\AI_SETUP.md,docs\USAGE.md,docs\ASSISTANCE_WIP.md dist\docs -Force
Copy-Item 使用说明.txt dist\使用说明.txt -Force
