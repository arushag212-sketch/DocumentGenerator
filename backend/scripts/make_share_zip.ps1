# backend/scripts/make_share_zip.ps1
# Creates a safe shareable zip archive of the ClubDocs repository.
# Strictly excludes all secrets, databases, caches, virtual environments, node_modules, and sample documents.

param(
    [string]$OutFile = "clubdocs_share.zip"
)

$ErrorActionPreference = "Stop"
# Zip the whole repository (two levels up from backend/scripts)
$root = (Get-Item -Path $PSScriptRoot).Parent.Parent.FullName
$zipPath = Join-Path $root $OutFile

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Write-Host "Building safe share archive: $OutFile..." -ForegroundColor Cyan

# Gather files with strict exclusion rules
$files = Get-ChildItem -Path $root -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($root.Length).TrimStart('\', '/')
    $normRel = $rel -replace '\\', '/'

    # Exclude secrets, environments, dependencies, build artifacts, databases, and sample docs
    if (($normRel -like ".env*" -or $normRel -like "*/.env") -and $normRel -notlike "*.env.example") { return $false }
    if ($normRel -like ".git/*" -or $normRel -eq ".git") { return $false }
    if ($normRel -like ".venv/*" -or $normRel -eq ".venv") { return $false }
    if ($normRel -like "*node_modules/*") { return $false }
    if ($normRel -like "frontend/dist/*") { return $false }
    if ($normRel -like "backend/data/*") { return $false }
    if ($normRel -like "backend/storage/*") { return $false }
    if ($normRel -like "outputs/*") { return $false }
    if ($normRel -like "sample docs/*" -or $normRel -like "docs/samples/*") { return $false }
    if ($normRel -like "*.log") { return $false }
    if ($normRel -like "*__pycache__/*") { return $false }
    if ($normRel -like "*.egg-info/*") { return $false }
    if ($normRel -like "*.pytest_cache/*") { return $false }
    if ($normRel -eq $OutFile) { return $false }

    return $true
}

# Create Zip archive using .NET Compression
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zipStream = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::Create)
$archive = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)

try {
    foreach ($f in $files) {
        $relPath = $f.FullName.Substring($root.Length).TrimStart('\', '/') -replace '\\', '/'
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f.FullName, $relPath, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    }
} finally {
    $archive.Dispose()
    $zipStream.Dispose()
}

$zipItem = Get-Item $zipPath
$sizeMB = [math]::Round($zipItem.Length / 1MB, 2)
$sizeKB = [math]::Round($zipItem.Length / 1KB, 1)

Write-Host "Archive created successfully!" -ForegroundColor Green
Write-Host "Location: $($zipItem.FullName)"
Write-Host "Size: $sizeMB MB ($sizeKB KB, $($zipItem.Length) bytes)"
Write-Host "File count: $($files.Count) files"
