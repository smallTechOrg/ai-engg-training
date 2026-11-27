# Set up this repo on Windows. Needs no Python: uv downloads one.
#   setup            install the base (enough for the first modules)
#   setup -All       also install every optional framework
# Safe to run again at any time. Run it through setup.cmd (double-click or type `setup`).
param([switch]$All)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Say($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($step, $hint) { Write-Host "`nSETUP FAILED at: $step`n$hint" -ForegroundColor Red; exit 1 }

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($dir in @("$env:USERPROFILE\.local\bin", "$env:USERPROFILE\.cargo\bin")) {
        if (Test-Path "$dir\uv.exe") { return "$dir\uv.exe" }
    }
    return $null
}

Say "Step 1 of 3: uv (the tool that installs Python and the packages)"
$uv = Find-Uv
if ($uv) {
    Write-Host "Found: $uv"
} else {
    Write-Host "Not found. Installing into your user folder (no admin rights needed)..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    } catch {
        Fail "installing uv" "Check your internet connection or proxy. Manual install: https://docs.astral.sh/uv/getting-started/installation/"
    }
    $uv = Find-Uv
    if (-not $uv) { Fail "locating uv after install" "Open a new terminal and run setup again." }
}

Say "Step 2 of 3: Python and packages"
if ($All) { & $uv sync --all-extras } else { & $uv sync }
if ($LASTEXITCODE -ne 0) { Fail "installing packages" "Check your internet connection or proxy, then run setup again." }

Say "Step 3 of 3: settings file"
if (Test-Path ".env") {
    Write-Host ".env already exists: left untouched."
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example."
}

Write-Host @"

Setup complete. Next:
  1. Open .env and set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL.
  2. run doctor      check everything works
  3. run 01.1        run the first lesson
  4. run             browse all lessons
"@
