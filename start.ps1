# ============================================================
#  FleetGuard — One-command dev startup
#  Usage:  .\start.ps1
#          .\start.ps1 -Stop        (shut everything down)
#          .\start.ps1 -Reset       (wipe DB and restart fresh)
# ============================================================
param(
    [switch]$Stop,
    [switch]$Reset
)

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND = Join-Path $ROOT "backend"
$FRONTEND = Join-Path $ROOT "frontend"

# ── Colours ──────────────────────────────────────────────────
function Write-Step($msg)  { Write-Host "  => $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [!!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  FleetGuard Dev Launcher" -ForegroundColor White
Write-Host "  ========================" -ForegroundColor DarkGray
Write-Host ""

# ── STOP mode ─────────────────────────────────────────────────
if ($Stop) {
    Write-Step "Stopping Docker services..."
    Set-Location $ROOT
    docker compose down
    Write-OK "All services stopped."
    exit 0
}

# ── Ensure Docker is running ──────────────────────────────────
Write-Step "Starting Docker services (postgres, zookeeper, kafka)..."
Set-Location $ROOT
docker compose up -d postgres zookeeper kafka | Out-Null
Write-OK "Docker containers up."

# ── Optional DB reset ─────────────────────────────────────────
if ($Reset) {
    Write-Step "Resetting database to seed snapshot..."
    Start-Sleep -Seconds 2
    $env:PYTHONPATH = $ROOT
    Set-Location $BACKEND
    python -c "from app.database import engine; from app.models.db_models import Base; Base.metadata.drop_all(engine); Base.metadata.create_all(engine)" 2>$null
    python ..\setup_local.py 2>$null
    Write-OK "Database reset complete."
}

# ── Backend (new terminal window) ─────────────────────────────
Write-Step "Starting backend (FastAPI on :8000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$BACKEND'; Write-Host '[Backend]' -ForegroundColor Cyan; uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir . --reload-dir ..\simulator --reload-dir ..\streaming"
) -WindowStyle Normal

# ── Frontend (new terminal window) ────────────────────────────
Write-Step "Starting frontend (Vite on :5173)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$FRONTEND'; Write-Host '[Frontend]' -ForegroundColor Magenta; npm run dev"
) -WindowStyle Normal

# ── Wait for backend to be ready ─────────────────────────────
Write-Step "Waiting for backend to be ready..."
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Write-Host "    waiting... ($($i+1)s)" -ForegroundColor DarkGray
}

if ($ready) {
    Write-OK "Backend is ready."
} else {
    Write-Warn "Backend didn't respond in 20s — check the backend window."
}

Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host "   App:      http://localhost:5173" -ForegroundColor White
Write-Host "   API:      http://localhost:8000/docs" -ForegroundColor White
Write-Host "   Health:   http://localhost:8000/health" -ForegroundColor White
Write-Host "  =============================================" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  To stop:  .\start.ps1 -Stop" -ForegroundColor DarkGray
Write-Host "  To reset: .\start.ps1 -Reset" -ForegroundColor DarkGray
Write-Host ""
