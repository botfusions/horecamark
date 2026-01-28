FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/browsers \
    PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net/builds

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy scraper code
COPY scraper /app/scraper

# Create directories for logs and reports
RUN mkdir -p /app/logs /app/reports

# Copy entrypoint script
COPY scraper/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "scraper.main"]
