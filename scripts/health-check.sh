#!/bin/bash
# HorecaMark Health Check Script
# Checks the health of all services

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Status tracking
STATUS=0
CHECKS=()

# Log functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_ok() { CHECKS+=("OK: $1"); }
log_fail() { CHECKS+=("FAIL: $1"); STATUS=1; }

echo "=========================================="
echo "   HorecaMark System Health Check"
echo "=========================================="
echo ""

# Check 1: Docker
echo "[1/6] Checking Docker..."
if docker info &> /dev/null; then
    log_ok "Docker is running"
else
    log_fail "Docker is not running"
fi
echo ""

# Check 2: Database container
echo "[2/6] Checking Database container..."
if docker ps --format '{{.Names}}' | grep -q '^horecemark-db$'; then
    log_ok "Database container is running"

    # Check database health
    if docker exec horecemark-db pg_isready -U horeca -d horecemark &> /dev/null; then
        log_ok "Database is accepting connections"
    else
        log_fail "Database is not ready"
    fi
else
    log_fail "Database container is not running"
fi
echo ""

# Check 3: Scraper container
echo "[3/6] Checking Scraper container..."
if docker ps --format '{{.Names}}' | grep -q '^horecemark-scraper$'; then
    log_ok "Scraper container is running"

    # Check Python health
    if docker exec horecemark-scraper python -c "import sys; sys.exit(0)" &> /dev/null; then
        log_ok "Python environment is healthy"
    else
        log_fail "Python environment error"
    fi
else
    log_fail "Scraper container is not running"
fi
echo ""

# Check 4: Database connection from scraper
echo "[4/6] Checking database connectivity..."
if docker exec horecemark-scraper python -m scraper.main health &> /dev/null; then
    log_ok "Scraper can connect to database"
else
    log_fail "Scraper cannot connect to database"
fi
echo ""

# Check 5: Logs
echo "[5/6] Checking recent logs..."
if [ -f "$PROJECT_DIR/logs/scraper.log" ]; then
    LOG_ERRORS=$(grep -i "error\|exception\|critical" "$PROJECT_DIR/logs/scraper.log" | tail -5 | wc -l)
    if [ "$LOG_ERRORS" -gt 0 ]; then
        log_warn "Found $LOG_ERRORS recent error(s) in logs"
        echo "Recent errors:"
        grep -i "error\|exception\|critical" "$PROJECT_DIR/logs/scraper.log" | tail -3
    else
        log_ok "No recent errors in logs"
    fi
else
    log_warn "Log file not found"
fi
echo ""

# Check 6: Disk space
echo "[6/6] Checking disk space..."
DISK_USAGE=$(df -h "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    log_ok "Disk usage: ${DISK_USAGE}%"
elif [ "$DISK_USAGE" -lt 90 ]; then
    log_warn "Disk usage: ${DISK_USAGE}% (getting high)"
else
    log_fail "Disk usage: ${DISK_USAGE}% (critically high)"
fi
echo ""

# Summary
echo "=========================================="
echo "   Summary"
echo "=========================================="
for check in "${CHECKS[@]}"; do
    if [[ $check == OK:* ]]; then
        echo -e "${GREEN}${check}${NC}"
    else
        echo -e "${RED}${check}${NC}"
    fi
done
echo ""

if [ $STATUS -eq 0 ]; then
    log_info "All checks passed!"
    echo ""
    echo "To start scraping:"
    echo "  ./scripts/start-scraper.sh"
    echo ""
    echo "To start scheduler:"
    echo "  ./scripts/start-scheduler.sh"
else
    log_error "Some checks failed. Please review the issues above."
fi

exit $STATUS
