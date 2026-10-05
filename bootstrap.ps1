$ErrorActionPreference = "Stop"

Write-Host "[1/4] Checking Python..."
python --version

Write-Host "[2/4] Creating virtual environment..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

Write-Host "[3/4] Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

Write-Host "[4/4] Installing development dependencies..."
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Write-Host ""
Write-Host "Ready. Next:"
Write-Host "  codex"
Write-Host "Then ask Codex to read AGENTS.md and START_HERE_CODEX.md and implement TASK-001 only."
