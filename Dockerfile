# Playwright Official Image - Chromium pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scraper code
COPY scraper /app/scraper

# Copy database migrations
COPY database/migrations /app/migrations

# Create directories for logs and reports
RUN mkdir -p /app/logs /app/reports

# Copy entrypoint script
COPY scraper/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "scraper.main"]
