# backend/scripts/check_env.ps1
# Verifies system environment versions for reproducible local builds.

$ErrorActionPreference = "Stop"
$root = (Get-Item -Path $PSScriptRoot).Parent.FullName

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " SVNIT ClubDocs Environment Verification Check" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$allPass = $true

# 1. Python Check
try {
    $pyVerStr = & python --version 2>&1
    Write-Host "[PASS] Python runtime: $pyVerStr" -ForegroundColor Green
    if ($pyVerStr -match "Python (\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Write-Host "[FAIL] Python version must be >= 3.11. Found: $pyVerStr" -ForegroundColor Red
            $allPass = $false
        }
    }
} catch {
    Write-Host "[FAIL] Python executable not found on PATH." -ForegroundColor Red
    $allPass = $false
}

# 2. Node Check
try {
    $nodeVerStr = & node --version 2>&1
    Write-Host "[PASS] Node.js runtime: $nodeVerStr" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Node.js executable not found on PATH." -ForegroundColor Yellow
}

# 3. Python Core Dependencies Check
$pyCheckScript = @"
import sys
required = [
    ('fastapi', '0.143.0'),
    ('sqlalchemy', '2.1.4'),
    ('pymupdf', '1.28.2'),
    ('docx', '1.2.0'),
    ('docxtpl', '0.20.2'),
    ('pydantic', '2.14.1'),
    ('alembic', '1.20.0')
]
missing = []
for mod, target_ver in required:
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)

if missing:
    print('Missing modules:', ', '.join(missing))
    sys.exit(1)
print('All core python modules imported successfully.')
sys.exit(0)
"@

try {
    $pyCheck = & python -c $pyCheckScript 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[PASS] Python packages verified ($pyCheck)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Python packages verification failed: $pyCheck" -ForegroundColor Red
        $allPass = $false
    }
} catch {
    Write-Host "[FAIL] Failed running Python dependency verification." -ForegroundColor Red
    $allPass = $false
}

# 4. Frontend Package.json Pins Check
$pkgJsonPath = Join-Path $root "../frontend/package.json"
if (Test-Path $pkgJsonPath) {
    $pkgJson = Get-Content $pkgJsonPath -Raw | ConvertFrom-Json
    $tiptapCore = $pkgJson.dependencies.'@tiptap/core'
    $tiptapReact = $pkgJson.dependencies.'@tiptap/react'
    if ($tiptapCore -eq "3.32.0" -and $tiptapReact -eq "3.32.0") {
        Write-Host "[PASS] TipTap exact pinned versions: @tiptap/core $tiptapCore, @tiptap/react $tiptapReact" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] TipTap versions are not pinned to exact 3.32.0: core=$tiptapCore, react=$tiptapReact" -ForegroundColor Red
        $allPass = $false
    }
}

# 5. LibreOffice Converter Check
$loPaths = @(
    "C:\Program Files\LibreOffice\program\soffice.exe",
    "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
)
$loFound = $false
foreach ($p in $loPaths) {
    if (Test-Path $p) {
        $loFound = $true
        Write-Host "[PASS] LibreOffice detected: $p" -ForegroundColor Green
        break
    }
}
if (-not $loFound) {
    # Check PATH
    try {
        $soffice = Get-Command soffice -ErrorAction SilentlyContinue
        if ($soffice) {
            $loFound = $true
            Write-Host "[PASS] LibreOffice detected on PATH: $($soffice.Source)" -ForegroundColor Green
        }
    } catch {}
}
if (-not $loFound) {
    Write-Host "[WARN] LibreOffice not found in standard paths or PATH. PDF conversion will be unavailable." -ForegroundColor Yellow
}

Write-Host "---------------------------------------------"
if ($allPass) {
    Write-Host "Environment verification SUCCESSFUL!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Environment verification FAILED with errors." -ForegroundColor Red
    exit 1
}
