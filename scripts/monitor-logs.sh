#!/bin/bash
# HorecaMark Log Monitor
# Monitors log files and sends alerts on errors

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/scraper.log"

# Configuration
ALERT_EMAIL="${ALERT_EMAIL:-}"
ERROR_THRESHOLD="${ERROR_THRESHOLD:-5}"
WATCH_INTERVAL="${WATCH_INTERVAL:-60}"

# Log functions
log_info() { echo -e "${GREEN}[MONITOR]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[MONITOR]${NC} $1"; }
log_error() { echo -e "${RED}[MONITOR]${NC} $1"; }

# Show usage
usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  tail           Show last 50 lines of log (default)"
    echo "  follow         Follow log in real-time (like tail -f)"
    echo "  errors         Show recent errors"
    echo "  watch          Monitor for new errors (daemon mode)"
    echo "  stats          Show log statistics"
    echo "  test-email     Send test alert email"
    echo "  --help, -h     Show this help message"
    echo ""
    echo "Options:"
    echo "  --lines N      Number of lines to show (default: 50)"
    echo "  --since TIME   Show logs since time (e.g., 1h, 30m)"
    echo ""
    echo "Examples:"
    echo "  $0 tail                # Show last 50 lines"
    echo "  $0 tail --lines 100    # Show last 100 lines"
    echo "  $0 follow              # Follow log in real-time"
    echo "  $0 errors              # Show recent errors"
    echo "  $0 stats               # Show statistics"
}

# Check if log file exists
check_log_file() {
    if [ ! -f "$LOG_FILE" ]; then
        log_error "Log file not found: $LOG_FILE"
        log_info "Make sure the scraper has run at least once."
        return 1
    fi
    return 0
}

# Show recent logs
show_tail() {
    local lines="${1:-50}"
    check_log_file || return 1

    echo -e "${BLUE}=== Last $lines lines of scraper.log ===${NC}"
    tail -n "$lines" "$LOG_FILE"
}

# Follow log in real-time
follow_log() {
    check_log_file || return 1

    echo -e "${BLUE}=== Following scraper.log (Ctrl+C to exit) ===${NC}"
    tail -f "$LOG_FILE"
}

# Show recent errors
show_errors() {
    local since="${1:-}"

    check_log_file || return 1

    echo -e "${RED}=== Recent errors in scraper.log ===${NC}"
    echo ""

    if [ -n "$since" ]; then
        # Show errors from last N time
        grep -i --since="$since" "error\|exception\|critical" "$LOG_FILE" || echo "No errors found in last $since"
    else
        # Show last 20 errors
        grep -i "error\|exception\|critical" "$LOG_FILE" | tail -20 || echo "No errors found"
    fi
}

# Show log statistics
show_stats() {
    check_log_file || return 1

    echo -e "${BLUE}=== Log Statistics ===${NC}"
    echo ""

    local total_lines=$(wc -l < "$LOG_FILE")
    local error_count=$(grep -ci "error" "$LOG_FILE" || echo "0")
    local exception_count=$(grep -ci "exception" "$LOG_FILE" || echo "0")
    local critical_count=$(grep -ci "critical" "$LOG_FILE" || echo "0")
    local warn_count=$(grep -ci "warn" "$LOG_FILE" || echo "0")

    echo "Total lines:      $total_lines"
    echo -e "Errors:           ${RED}$error_count${NC}"
    echo -e "Exceptions:       ${RED}$exception_count${NC}"
    echo -e "Critical:         ${RED}$critical_count${NC}"
    echo -e "Warnings:         ${YELLOW}$warn_count${NC}"
    echo ""

    # Show last scrape time
    local last_scrape=$(grep -i "scraping\|tamamlandi" "$LOG_FILE" | tail -1)
    if [ -n "$last_scrape" ]; then
        echo -e "${GREEN}Last scrape:${NC}"
        echo "$last_scrape"
    fi
}

# Watch for new errors (daemon mode)
watch_errors() {
    check_log_file || return 1

    log_info "Monitoring log file for errors..."
    log_info "Press Ctrl+C to stop"
    log_info "Alert threshold: $ERROR_THRESHOLD errors"

    local error_count=0
    local last_position=$(wc -c < "$LOG_FILE")

    while true; do
        sleep "$WATCH_INTERVAL"

        # Get new content
        local current_position=$(wc -c < "$LOG_FILE")
        if [ "$current_position" -gt "$last_position" ]; then
            local new_content=$(tail -c +"$((last_position + 1))" "$LOG_FILE")
            local new_errors=$(echo "$new_content" | grep -ci "error\|exception\|critical" || echo "0")

            if [ "$new_errors" -gt 0 ]; then
                error_count=$((error_count + new_errors))
                log_warn "Detected $new_errors new error(s) (total: $error_count)"

                # Show recent errors
                echo "$new_content" | grep -i "error\|exception\|critical" | while read -r line; do
                    echo -e "${RED}$line${NC}"
                done

                # Send alert if threshold reached
                if [ "$error_count" -ge "$ERROR_THRESHOLD" ]; then
                    log_error "Error threshold reached ($ERROR_THRESHOLD errors)!"

                    if [ -n "$ALERT_EMAIL" ]; then
                        log_info "Sending alert email to $ALERT_EMAIL..."
                        # Email sending would be implemented here
                    fi

                    # Reset counter after alert
                    error_count=0
                fi
            fi

            last_position=$current_position
        fi
    done
}

# Send test email
test_email() {
    log_info "Sending test alert email..."

    if [ -z "$ALERT_EMAIL" ]; then
        log_error "ALERT_EMAIL environment variable not set"
        return 1
    fi

    # Use docker to send email
    docker exec horecemark-scraper python -m scraper.main test-email
}

# Parse arguments
COMMAND="${1:-tail}"
shift || true

case "$COMMAND" in
    tail)
        LINES=50
        while [[ $# -gt 0 ]]; do
            case $1 in
                --lines)
                    LINES="$2"
                    shift 2
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        show_tail "$LINES"
        ;;
    follow|f)
        follow_log
        ;;
    errors|e)
        show_errors
        ;;
    stats|s)
        show_stats
        ;;
    watch|w)
        watch_errors
        ;;
    test-email)
        test_email
        ;;
    --help|-h)
        usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
