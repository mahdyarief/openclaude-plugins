# install-binary.ps1 - Download codebase-memory-mcp.exe from the upstream
# DeusData/codebase-memory-mcp release and verify it against checksums.txt.
# The 282 MB binary is too large for GitHub's 100 MB per-file limit, so it is
# not committed to this repo. Run this script once before first use.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-binary.ps1

$ErrorActionPreference = "Stop"

$PluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = Join-Path $PluginRoot "bin"
$ExePath = Join-Path $BinDir "codebase-memory-mcp.exe"

if (Test-Path $ExePath) {
    Write-Host "codebase-memory-mcp.exe already present: $ExePath"
    exit 0
}

$ReleaseBase = "https://github.com/DeusData/codebase-memory-mcp/releases/latest/download"
$ZipUrl = "$ReleaseBase/codebase-memory-mcp-windows-amd64.zip"
$ChecksumsUrl = "$ReleaseBase/checksums.txt"

$TempDir = Join-Path $env:TEMP ("codebase-memory-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

try {
    $ZipPath = Join-Path $TempDir "codebase-memory-mcp-windows-amd64.zip"
    $ChecksumsPath = Join-Path $TempDir "checksums.txt"

    Write-Host "Downloading binary from $ZipUrl ..."
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath

    Write-Host "Downloading checksums.txt ..."
    Invoke-WebRequest -Uri $ChecksumsUrl -OutFile $ChecksumsPath

    Write-Host "Extracting ..."
    Expand-Archive -Path $ZipPath -DestinationPath $TempDir -Force

    $ExtractedExe = Get-ChildItem -Path $TempDir -Filter "*.exe" -Recurse | Select-Object -First 1
    if (-not $ExtractedExe) {
        throw "No .exe found inside the downloaded archive."
    }

    $Hash = (Get-FileHash -Path $ExtractedExe.FullName -Algorithm SHA256).Hash
    $Checksums = Get-Content -Path $ChecksumsPath -Raw
    if ($Checksums -notmatch $Hash) {
        throw "SHA-256 verification failed: $Hash does not match any entry in checksums.txt"
    }
    Write-Host "SHA-256 verified: $Hash"

    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    Copy-Item -Path $ExtractedExe.FullName -Destination $ExePath
    Write-Host "Installed: $ExePath"

    # Watcher + auto-index on large repos caused full-disk I/O saturation
    # (jbd2 stuck in D-state, host hang). Watcher registration is opt-in now;
    # re-index explicitly with index_repository instead.
    & $ExePath config set auto_watch false | Out-Null
    & $ExePath config set auto_index_limit 1000 | Out-Null
    Write-Host "Applied safe defaults: auto_watch=false, auto_index_limit=1000"
}
finally {
    Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}
