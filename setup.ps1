param(
    [string]$PythonExe = 'python',
    [switch]$WithMaps,
    [switch]$Development
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $PythonExe -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'
        if ($LASTEXITCODE -ne 0) { throw 'Potreban je Python 3.12 ili noviji; preporuka je 3.13.' }
        & $PythonExe -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Kreiranje lokalnog .venv nije uspjelo.' }
    }
    $package = if ($Development) { '.[dev]' } else { '.' }
    & $venvPython -m pip install -e $package
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Pokusavam PyYAML bez opcione C ekstenzije (C++ compiler nije potreban za katalog).'
        $previousLibyaml = $env:PYYAML_FORCE_LIBYAML
        try {
            $env:PYYAML_FORCE_LIBYAML = '0'
            & $venvPython -m pip install -e $package
        }
        finally { $env:PYYAML_FORCE_LIBYAML = $previousLibyaml }
    }
    if ($LASTEXITCODE -ne 0) { throw 'Instalacija zavisnosti nije uspjela.' }
    if ($WithMaps) {
        & $venvPython tools/install_archify.py
        if ($LASTEXITCODE -ne 0) { throw 'Lokalna Archify instalacija nije uspjela.' }
        $bundledNode = Join-Path $PSScriptRoot '.venv\Lib\site-packages\playwright\driver\node.exe'
        $nodeExe = if (Test-Path -LiteralPath $bundledNode) { $bundledNode } else { 'node' }
        $env:ARCHIFY_UPDATE_CHECK_DISABLED = '1'
        & $nodeExe vendor/archify/archify/bin/archify.mjs doctor
        if ($LASTEXITCODE -ne 0) { throw 'Archify doctor nije prosao; za mape je potreban Node.js 18+.' }
    }
    if ($Development) {
        $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $PSScriptRoot '.playwright-browsers'
        & $venvPython -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Instalacija lokalnog test browsera nije uspjela.' }
    }
    & $venvPython -m atlas init
    if ($LASTEXITCODE -ne 0) { throw 'Init nije uspio.' }
    & $venvPython -m atlas refresh
    if ($LASTEXITCODE -notin @(0,2)) { throw 'Prvo skeniranje nije uspjelo.' }
    Write-Host 'Spremno. Otvori katalog: .\atlas.cmd open'
    Write-Host 'Ako izvori nisu dostupni, uredi config/sources.local.json pa pokreni .\atlas.cmd refresh.'
}
finally { Pop-Location }
