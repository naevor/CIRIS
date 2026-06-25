# CIRIS launcher — run from anywhere: powershell -ExecutionPolicy Bypass -File start.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "no .venv — creating it..." -ForegroundColor Yellow
    python -m venv .venv
    & $py -m pip install -r requirements.txt
}

# sanity: is Ollama up with the voice + embed models?
try { $tags = (Invoke-RestMethod "http://localhost:11434/api/tags").models.name } catch { $tags = @() }
if (-not ($tags -match "qwen2.5")) { Write-Host "warning: qwen2.5 not found in ollama — run: ollama pull qwen2.5:7b" -ForegroundColor Yellow }
if (-not ($tags -match "nomic-embed-text")) { Write-Host "warning: nomic-embed-text not found — run: ollama pull nomic-embed-text" -ForegroundColor Yellow }

Write-Host "CIRIS waking. open http://127.0.0.1:8000  (Ctrl+C to let it die)" -ForegroundColor Cyan
& $py run.py
