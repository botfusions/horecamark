# HorecaMark Scraper - Start script for Windows
# Runs the scraper once and exits

#Requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Verbose,
    [string]$Site,
    [switch]$Help
)

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

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

# Show help
if ($Help) {
    Write-Host "Usage: .\Start-Scraper.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -DryRun       Run without saving to database"
    Write-Host "  -Verbose      Enable verbose output"
    Write-Host "  -Site VALUE   Scrape only specified site"
    Write-Host "  -Help         Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\Start-Scraper.ps1"
    Write-Host "  .\Start-Scraper.ps1 -Verbose"
    Write-Host "  .\Start-Scraper.ps1 -Site cafemarkt"
    Write-Host "  .\Start-Scraper.ps1 -DryRun -Verbose"
    exit 0
}

# Check if Docker is running
try {
    $null = docker info 2>&1
} catch {
    Write-Error "Docker is not running. Please start Docker Desktop first."
    exit 1
}

# Check if container exists
$containers = docker ps -a --format "{{.Names}}" 2>&1
if ($containers -notcontains "horecemark-scraper") {
    Write-Error "Container horecemark-scraper not found."
    Write-Info "Run 'docker-compose up -d' first."
    exit 1
}

# Check if container is running
$running = docker ps --format "{{.Names}}" 2>&1
if ($running -notcontains "horecemark-scraper") {
    Write-Warn "Container is not running. Starting it..."
    Push-Location $ProjectDir
    docker-compose up -d scraper
    Pop-Location
    Start-Sleep -Seconds 3
}

# Build command
$CmdArgs = @()

if ($DryRun) {
    $CmdArgs += "--dry-run"
}

if ($Verbose) {
    $CmdArgs += "--verbose"
}

# Build Python command
if ($Site) {
    $PythonCmd = "python -m scraper.main scrape --site $Site $($CmdArgs -join ' ')"
} else {
    $PythonCmd = "python -m scraper.main run $($CmdArgs -join ' ')"
}

Write-Info "Starting scraper..."
Write-Info "Command: $PythonCmd"

# Run scraper
$Result = docker exec horecemark-scraper $PythonCmd.Split(" ")
$ExitCode = $LASTEXITCODE

if ($ExitCode -eq 0) {
    Write-Info "Scraping completed successfully."
} else {
    Write-Error "Scraping failed with exit code $ExitCode."
}

exit $ExitCode
