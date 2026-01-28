# HorecaMark Automation Setup Guide

This guide explains how to set up automated daily scraping for HorecaMark.

## Quick Start

### Option 1: Docker Scheduler (Recommended)

1. **Configure environment variables:**

   ```bash
   cp .env.automation.example .env
   # Edit .env with your settings
   ```

2. **Enable the scheduler:**

   ```bash
   # In .env, set:
   SCHEDULER_ENABLED=true
   SCRAPE_TIME=08:00
   ```

3. **Start the services:**

   ```bash
   docker-compose up -d
   ```

   The scraper will now run daily at the configured time.

### Option 2: Cron Job (Linux)

1. **Create a crontab entry:**

   ```bash
   crontab -e
   ```

2. **Add the following line:**

   ```cron
   # Run HorecaMark scraper daily at 08:00
   0 8 * * * cd /path/to/horecemark && ./scripts/start-scraper.sh >> /var/log/horecemark.log 2>&1
   ```

### Option 3: Task Scheduler (Windows)

1. **Open Task Scheduler** (taskschd.msc)

2. **Create Basic Task:**
   - Name: HorecaMark Daily Scrape
   - Trigger: Daily at 08:00
   - Action: Start a program
   - Program: powershell.exe
   - Arguments: -File "C:\path\to\horecemark\scripts\Start-Scraper.ps1"

### Option 4: n8n Workflow

1. **Import the workflow:**
   ```bash
   # Import n8n-workflows/daily-scrape.json into n8n
   ```

2. **Configure credentials:**
   - SMTP email settings
   - Optional Google Sheets for logging

## Scripts Reference

| Script | Description |
|--------|-------------|
| `scripts/start-scraper.sh` | Run scraper once (Linux/Mac) |
| `scripts/start-scheduler.sh` | Run scheduler daemon (Linux/Mac) |
| `scripts/health-check.sh` | Check system health (Linux/Mac) |
| `scripts/monitor-logs.sh` | Monitor log files (Linux/Mac) |
| `scripts/Start-Scraper.ps1` | Run scraper once (Windows) |
| `scripts/Start-Scheduler.ps1` | Run scheduler daemon (Windows) |
| `scripts/Get-Health.ps1` | Check system health (Windows) |

## Manual Execution

### Linux/Mac

```bash
# Run scraper once
./scripts/start-scraper.sh

# Run with verbose output
./scripts/start-scraper.sh --verbose

# Run specific site
./scripts/start-scraper.sh --site cafemarkt

# Dry run (no database save)
./scripts/start-scraper.sh --dry-run

# Health check
./scripts/health-check.sh

# Monitor logs
./scripts/monitor-logs.sh tail
./scripts/monitor-logs.sh follow
./scripts/monitor-logs.sh errors
./scripts/monitor-logs.sh stats
```

### Windows (PowerShell)

```powershell
# Run scraper once
.\scripts\Start-Scraper.ps1

# Run with verbose output
.\scripts\Start-Scraper.ps1 -Verbose

# Run specific site
.\scripts\Start-Scraper.ps1 -Site cafemarkt

# Dry run (no database save)
.\scripts\Start-Scraper.ps1 -DryRun

# Health check
.\scripts\Get-Health.ps1
```

## Troubleshooting

### Container not running

```bash
# Check container status
docker ps

# View logs
docker logs horecemark-scraper
docker logs horecemark-db

# Restart services
docker-compose restart
```

### Database connection issues

```bash
# Check database is ready
docker exec horecemark-db pg_isready -U horeca

# Test connection from scraper
docker exec horecemark-scraper python -m scraper.main health
```

### Emails not sending

```bash
# Test email configuration
docker exec horecemark-scraper python -m scraper.main test-email

# Check environment variables
docker exec horecemark-scraper env | grep SMTP
```

### View recent errors

```bash
# Using monitor script
./scripts/monitor-logs.sh errors

# Direct log view
tail -100 logs/scraper.log | grep -i error
```

## Production Deployment

For production, use `docker-compose.override.yml`:

1. **Copy the example:**
   ```bash
   cp docker-compose.override.yml.example docker-compose.override.yml
   ```

2. **Configure settings:**
   - Resource limits
   - Backup schedules
   - Log retention

3. **Start with override:**
   ```bash
   docker-compose up -d
   ```

## Monitoring Recommendations

1. **Set up log rotation** to prevent disk filling
2. **Monitor disk space** weekly
3. **Check email delivery** regularly
4. **Review reports** for data quality
5. **Update dependencies** monthly

## Security Notes

1. **Never commit .env files** to version control
2. **Use strong passwords** for database
3. **Use app-specific passwords** for Gmail
4. **Restrict database port** in production (don't expose 5432)
5. **Keep containers updated** with security patches

## Support

For issues or questions:
- Check logs in `logs/scraper.log`
- Run health check script
- Review container logs
