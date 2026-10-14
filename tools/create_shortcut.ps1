# Pravi precicu "AI Atlas" na Desktopu: dvoklik osvjezi katalog i otvori ga, bez terminala.
# Precica pokrece .venv\Scripts\pythonw.exe -m atlas launch (pythonw nema konzolni prozor).
param([string]$Name = 'AI Atlas')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw 'Nema .venv\Scripts\pythonw.exe; prvo pokreni setup.ps1.' }
$desktop = [Environment]::GetFolderPath('Desktop')
$path = Join-Path $desktop ($Name + '.lnk')
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($path)
$link.TargetPath = $pythonw
$link.Arguments = '-m atlas launch'
$link.WorkingDirectory = $root
$link.IconLocation = (Join-Path $env:SystemRoot 'System32\imageres.dll') + ',75'
$link.Description = 'Osvjezi i otvori lokalni katalog AI okruzenja'
$link.Save()
Write-Host "Precica napravljena: $path"
