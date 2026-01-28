#!/bin/bash
# HorecaMark Docker Entrypoint
# Waits for database, runs migrations, starts application

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Log functions
log_info() { echo -e "${GREEN}[ENTRYPOINT]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[ENTRYPOINT]${NC} $1"; }
log_error() { echo -e "${RED}[ENTRYPOINT]${NC} $1"; }

# Configuration
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-horecemark}"
DB_USER="${DB_USER:-horeca}"
MAX_WAIT="${DB_MAX_WAIT:-30}"

# Function to check if database is ready
wait_for_db() {
    local i=0
    log_info "Waiting for database at $DB_HOST:$DB_PORT..."

    while [ $i -lt $MAX_WAIT ]; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" &> /dev/null; then
            log_info "Database is ready!"
            return 0
        fi
        i=$((i + 1))
        echo -n "."
        sleep 1
    done

    log_error "Database connection timeout after ${MAX_WAIT}s"
    return 1
}

# Function to initialize database
init_database() {
    log_info "Initializing database..."

    # Run migrations if they exist
    if [ -d "/app/migrations" ] && [ -n "$(ls -A /app/migrations/*.sql 2>/dev/null)" ]; then
        log_info "Running database migrations..."
        for migration in /app/migrations/*.sql; do
            if [ -f "$migration" ]; then
                log_info "Applying $(basename "$migration")..."
                psql "postgresql://$DB_USER:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}" -f "$migration" || true
            fi
        done
    fi

    log_info "Database initialization complete"
}

# Function to install Playwright browsers at runtime
install_playwright_browsers() {
    log_info "Installing Playwright Chromium browser..."

    # Try up to 3 times with delays
    for attempt in 1 2 3; do
        if playwright install chromium; then
            log_info "Playwright Chromium installed successfully!"
            return 0
        fi

        log_warn "Attempt $attempt failed, retrying in ${attempt}0 seconds..."
        sleep ${attempt}0
    done

    log_error "Failed to install Playwright after 3 attempts"
    log_warn "Continuing anyway - scrapers that need browsers may fail"
    return 1
}

# Function to check if we should run scheduler
should_run_scheduler() {
    # Check if SCHEDULER_ENABLED is set to true
    if [ "${SCHEDULER_ENABLED:-false}" = "true" ]; then
        return 0
    fi

    # Check if command contains "schedule"
    if [ "${1:-}" = "schedule" ] || echo "${*:-}" | grep -q "schedule"; then
        return 0
    fi

    return 1
}

# Main entrypoint
main() {
    log_info "Starting HorecaMark Scraper..."
    log_info "Database: $DB_HOST:$DB_PORT/$DB_NAME"

    # Wait for database
    wait_for_db || exit 1

    # Initialize database (run migrations)
    init_database

    # Create necessary directories
    mkdir -p /app/logs /app/reports

    # Set permissions
    chmod 755 /app/logs /app/reports 2>/dev/null || true

    # Install Playwright browsers at runtime
    install_playwright_browsers

    log_info "Environment ready. Starting application..."

    # If no arguments provided, run default command
    if [ $# -eq 0 ]; then
        # Check if scheduler should be enabled
        if [ "${SCHEDULER_ENABLED:-false}" = "true" ]; then
            log_info "Starting scheduler daemon..."
            exec python -m scraper.main schedule
        else
            log_info "Starting default command..."
            exec python -m scraper.main
        fi
    else
        # Run provided command
        log_info "Running command: $*"
        exec "$@"
    fi
}

# Trap signals for graceful shutdown
trap 'log_info "Received shutdown signal"; exit 0' SIGTERM SIGINT

# Run main function
main "$@"
