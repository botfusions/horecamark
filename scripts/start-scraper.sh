#!/bin/bash
# HorecaMark Scraper - Start script
# Runs the scraper once and exits

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

# Parse arguments
DRY_RUN=""
VERBOSE=""
SITE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run|-n)
            DRY_RUN="--dry-run"
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --site|-s)
            SITE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run, -n    Run without saving to database"
            echo "  --verbose, -v    Enable verbose output"
            echo "  --site, -s       Scrape only specified site"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build command
CMD="python -m scraper.main run $DRY_RUN $VERBOSE"

# Add site if specified
if [ -n "$SITE" ]; then
    CMD="python -m scraper.main scrape --site $SITE $DRY_RUN $VERBOSE"
fi

log_info "Starting scraper..."
log_info "Command: $CMD"

# Run scraper
docker exec -it horecemark-scraper $CMD

exit_code=$?

if [ $exit_code -eq 0 ]; then
    log_info "Scraping completed successfully."
else
    log_error "Scraping failed with exit code $exit_code."
fi

exit $exit_code
