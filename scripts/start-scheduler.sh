#!/bin/bash
# HorecaMark Scheduler - Start daemon script
# Runs the scheduler in daemon mode for daily execution

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Log functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if Docker is running
if ! docker info &> /dev/null; then
    log_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Parse arguments
ONCE=""
TIME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --once)
            ONCE="--once"
            shift
            ;;
        --time|-t)
            TIME="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --once           Run once and exit (for cron)"
            echo "  --time, -t       Schedule time (HH:MM format)"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0               # Start daemon mode"
            echo "  $0 --once        # Run report once"
            echo "  $0 --time 09:00  # Schedule for 09:00"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q '^horecemark-scraper$'; then
    log_error "Container horecemark-scraper not found."
    log_info "Run 'docker-compose up -d' first."
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q '^horecemark-scraper$'; then
    log_warn "Container is not running. Starting it..."
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" up -d scraper
    sleep 3
fi

# Build command
if [ -n "$ONCE" ]; then
    CMD="python -m scraper.main schedule --once"
    log_info "Running scheduler once..."
elif [ -n "$TIME" ]; then
    CMD="python -m scraper.main.utils.scheduler run_once --time $TIME"
    log_info "Running scheduler for time $TIME..."
else
    CMD="python -m scraper.main schedule"
    log_info "Starting scheduler daemon..."
    log_warn "Press Ctrl+C to stop the scheduler."
fi

# Run scheduler
docker exec -it horecemark-scraper $CMD
