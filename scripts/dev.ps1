<#
.SYNOPSIS
    All-in-one development & single-URL production launcher for SVNIT ClubDocs.

.DESCRIPTION
    1. Runs system doctor check (Python, Node, LibreOffice, DB)
    2. Ensures database migrations & demo data are seeded
    3. Starts backend and frontend:
       - Default: Launches Vite dev server & FastAPI uvicorn concurrently
       - Production flag: Builds React SPA and serves entire portal through single FastAPI URL

.PARAMETER Production
    Builds the frontend production bundle and serves via FastAPI on port 8000.

.EXAMPLE
    .\scripts\dev.ps1
    .\scripts\dev.ps1 -Production
#>

param(
    [switch]$Production
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       SVNIT ClubDocs - One-Click Launcher (PowerShell)                 " -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

# 1. Run Doctor Check
Write-Host "`n[1/3] Running System Doctor..." -ForegroundColor Yellow
python -m server.scripts.doctor
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Doctor reported warnings or errors. Ensure requirements.txt is installed."
}

# 2. Seed Database
Write-Host "`n[2/3] Verifying Database & Demo Seeds..." -ForegroundColor Yellow
python -m server.scripts.seed

# 3. Launch App
if ($Production) {
    Write-Host "`n[3/3] Building Frontend for Single-URL Production Mode..." -ForegroundColor Yellow
    Set-Location "$ProjectRoot\web"
    npm install
    npm run build
    Set-Location $ProjectRoot

    Write-Host "`nStarting Single-URL Production Server on http://localhost:8000..." -ForegroundColor Green
    python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
} else {
    Write-Host "`n[3/3] Starting Full-Stack Development Mode..." -ForegroundColor Yellow
    Write-Host "-> Backend: http://localhost:8000 (FastAPI Swagger: http://localhost:8000/docs)" -ForegroundColor Cyan
    Write-Host "-> Frontend: http://localhost:5173 (Vite Hot-Reload Dev Server)" -ForegroundColor Cyan

    # Ensure frontend node_modules installed
    if (-not (Test-Path "$ProjectRoot\web\node_modules")) {
        Write-Host "Installing web dependencies..." -ForegroundColor Gray
        Set-Location "$ProjectRoot\web"
        npm install
        Set-Location $ProjectRoot
    }

    # Start Vite in background job/process
    $ViteProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c cd web && npm run dev" -PassThru

    try {
        # Run FastAPI in foreground
        python -m uvicorn server.app.main:app --reload --port 8000
    }
    finally {
        if ($ViteProcess -and -not $ViteProcess.HasExited) {
            Stop-Process -Id $ViteProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
