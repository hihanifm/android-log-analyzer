$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$componentDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent (Split-Path -Parent $componentDir)
$venvDir = Join-Path $repoRoot ".venv"

Write-Host "==> Component dir: $componentDir"
Write-Host "==> Repo root: $repoRoot"

if (-not (Test-Path $venvDir)) {
    Write-Host "==> Creating virtual environment at $venvDir"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv $venvDir
    } else {
        python -m venv $venvDir
    }
} else {
    Write-Host "==> Reusing existing virtual environment at $venvDir"
}

$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    throw "Virtual environment activation script not found: $activateScript"
}

. $activateScript

Write-Host "==> Upgrading pip"
python -m pip install --upgrade pip

Write-Host "==> Installing android-log-browser in editable mode"
pip install -e $componentDir

Write-Host "==> Installing shell completion (best effort)"
try {
    android-log-browser --install-completion powershell | Out-Null
} catch {
    Write-Warning "Shell completion install was skipped: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "To use immediately in current terminal, run:"
Write-Host "  . `"$activateScript`""
