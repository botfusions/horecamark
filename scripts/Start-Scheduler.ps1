# HorecaMark Scheduler - Start daemon script for Windows
# Runs the scheduler in daemon mode for daily execution

#Requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$Once,
    [string]$Time,
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
    Write-Host "Usage: .\Start-Scheduler.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Once          Run once and exit (for cron)"
    Write-Host "  -Time VALUE    Schedule time (HH:MM format)"
    Write-Host "  -Help          Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\Start-Scheduler.ps1              # Start daemon mode"
    Write-Host "  .\Start-Scheduler.ps1 -Once        # Run report once"
    Write-Host "  .\Start-Scheduler.ps1 -Time 09:00  # Schedule for 09:00"
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
if ($Once) {
    $PythonCmd = "python -m scraper.main schedule --once"
    Write-Info "Running scheduler once..."
} elseif ($Time) {
    $PythonCmd = "python -m scraper.main.utils.scheduler run_once --time $Time"
    Write-Info "Running scheduler for time $Time..."
} else {
    $PythonCmd = "python -m scraper.main schedule"
    Write-Info "Starting scheduler daemon..."
    Write-Warn "Press Ctrl+C to stop the scheduler."
}

# Run scheduler
docker exec -it horecemark-scraper $PythonCmd.Split(" ")
