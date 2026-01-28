# HorecaMark Health Check Script for Windows
# Checks the health of all services

#Requires -Version 5.1

[CmdletBinding()]

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# Status tracking
$Script:Status = 0
$Script:Checks = @()

# Helper functions
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Info { Write-ColorOutput "[INFO] $args" -Color Green }
function Write-Warn { Write-ColorOutput "[WARN] $args" -Color Yellow }
function Write-Error { Write-ColorOutput "[ERROR] $args" -Color Red }

function Add-CheckOk {
    param([string]$Message)
    $Script:Checks += @{ Status = "OK"; Message = $Message }
    Write-ColorOutput "[OK] $Message" -Color Green
}

function Add-CheckFail {
    param([string]$Message)
    $Script:Checks += @{ Status = "FAIL"; Message = $Message }
    Write-ColorOutput "[FAIL] $Message" -Color Red
    $Script:Status = 1
}

function Add-CheckWarn {
    param([string]$Message)
    $Script:Checks += @{ Status = "WARN"; Message = $Message }
    Write-ColorOutput "[WARN] $Message" -Color Yellow
}

Write-Host "=========================================="
Write-Host "   HorecaMark System Health Check"
Write-Host "=========================================="
Write-Host ""

# Check 1: Docker
Write-Host "[1/6] Checking Docker..."
try {
    $null = docker info 2>&1
    Add-CheckOk "Docker is running"
} catch {
    Add-CheckFail "Docker is not running"
}
Write-Host ""

# Check 2: Database container
Write-Host "[2/6] Checking Database container..."
$containers = docker ps --format "{{.Names}}" 2>&1
if ($containers -contains "horecemark-db") {
    Add-CheckOk "Database container is running"

    # Check database health
    $dbReady = docker exec horecemark-db pg_isready -U horeca -d horecemark 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-CheckOk "Database is accepting connections"
    } else {
        Add-CheckFail "Database is not ready"
    }
} else {
    Add-CheckFail "Database container is not running"
}
Write-Host ""

# Check 3: Scraper container
Write-Host "[3/6] Checking Scraper container..."
if ($containers -contains "horecemark-scraper") {
    Add-CheckOk "Scraper container is running"

    # Check Python health
    $null = docker exec horecemark-scraper python -c "exit(0)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-CheckOk "Python environment is healthy"
    } else {
        Add-CheckFail "Python environment error"
    }
} else {
    Add-CheckFail "Scraper container is not running"
}
Write-Host ""

# Check 4: Database connection from scraper
Write-Host "[4/6] Checking database connectivity..."
$healthResult = docker exec horecemark-scraper python -m scraper.main health 2>&1
if ($LASTEXITCODE -eq 0) {
    Add-CheckOk "Scraper can connect to database"
} else {
    Add-CheckFail "Scraper cannot connect to database"
}
Write-Host ""

# Check 5: Logs
Write-Host "[5/6] Checking recent logs..."
$LogPath = Join-Path $ProjectDir "logs\scraper.log"
if (Test-Path $LogPath) {
    $logContent = Get-Content $LogPath -Tail 100 -ErrorAction SilentlyContinue
    $errorCount = 0
    foreach ($line in $logContent) {
        if ($line -match "error|exception|critical") {
            $errorCount++
        }
    }

    if ($errorCount -gt 0) {
        Add-CheckWarn "Found $errorCount recent error(s) in logs"
    } else {
        Add-CheckOk "No recent errors in logs"
    }
} else {
    Add-CheckWarn "Log file not found"
}
Write-Host ""

# Check 6: Disk space
Write-Host "[6/6] Checking disk space..."
$drive = (Get-Item $ProjectDir).PSDrive
$usage = [math]::Round((1 - $drive.Free / $drive.Maximum) * 100, 1)

if ($usage -lt 80) {
    Add-CheckOk "Disk usage: $usage%"
} elseif ($usage -lt 90) {
    Add-CheckWarn "Disk usage: $usage% (getting high)"
} else {
    Add-CheckFail "Disk usage: $usage% (critically high)"
}
Write-Host ""

# Summary
Write-Host "=========================================="
Write-Host "   Summary"
Write-Host "=========================================="

foreach ($check in $Script:Checks) {
    switch ($check.Status) {
        "OK" { Write-ColorOutput "$($check.Status): $($check.Message)" -Color Green }
        "WARN" { Write-ColorOutput "$($check.Status): $($check.Message)" -Color Yellow }
        "FAIL" { Write-ColorOutput "$($check.Status): $($check.Message)" -Color Red }
    }
}
Write-Host ""

if ($Script:Status -eq 0) {
    Write-Info "All checks passed!"
    Write-Host ""
    Write-Host "To start scraping:"
    Write-Host "  .\Start-Scraper.ps1"
    Write-Host ""
    Write-Host "To start scheduler:"
    Write-Host "  .\Start-Scheduler.ps1"
} else {
    Write-Error "Some checks failed. Please review the issues above."
}

exit $Script:Status
