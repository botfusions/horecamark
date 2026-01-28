# HorecaMark Automation Workflows

This directory contains n8n workflow definitions for automating HorecaMark scraping tasks.

## Workflows

### daily-scrape.json

Daily scraping workflow that runs at 08:00 and:

1. **Schedule Trigger**: Cron trigger at 08:00 daily
2. **Run Scraper**: Executes scraper via Docker
3. **Error Handling**: Sends error email if scraping fails
4. **Success Notification**: Sends report email on success
5. **Logging**: Logs results to tracking system

## Setup Instructions

### Option 1: Import to n8n

1. Open n8n dashboard
2. Click "Import from File"
3. Select `daily-scrape.json`
4. Configure credentials:
   - SMTP email settings
   - Optional Google Sheets for logging

### Option 2: Use Cron + Docker

Add to crontab (`crontab -e`):

```bash
# Run daily at 08:00
0 8 * * * cd /path/to/horecemark && ./scripts/start-scraper.sh
```

### Option 3: Use Docker Scheduler Daemon

Enable scheduler in `docker-compose.override.yml`:

```yaml
services:
  scraper:
    environment:
      - SCHEDULER_ENABLED=true
      - SCRAPE_TIME=08:00
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SCRAPE_TIME` | Time to run (HH:MM) | 08:00 |
| `EMAIL_FROM` | Sender email | - |
| `EMAIL_TO` | Recipient emails | - |
| `SMTP_HOST` | SMTP server | smtp.gmail.com |
| `SMTP_PORT` | SMTP port | 587 |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password | - |

## Manual Execution

```bash
# Run scraper once
./scripts/start-scraper.sh

# Run with verbose output
./scripts/start-scraper.sh --verbose

# Run specific site
./scripts/start-scraper.sh --site cafemarkt

# Dry run (no database save)
./scripts/start-scraper.sh --dry-run

# Run scheduler daemon
./scripts/start-scheduler.sh

# Run once (for cron)
./scripts/start-scheduler.sh --once

# Health check
./scripts/health-check.sh

# Monitor logs
./scripts/monitor-logs.sh tail
./scripts/monitor-logs.sh follow
./scripts/monitor-logs.sh errors
./scripts/monitor-logs.sh stats
```

## Troubleshooting

### Scraper not running

```bash
# Check container status
docker ps

# View logs
docker logs horecemark-scraper

# Run health check
./scripts/health-check.sh
```

### Emails not sending

```bash
# Test email configuration
docker exec horecemark-scraper python -m scraper.main test-email

# Check environment variables
docker exec horecemark-scraper env | grep SMTP
```

### Database connection issues

```bash
# Check database is ready
docker exec horecemark-db pg_isready -U horeca

# Check database logs
docker logs horecemark-db
```
