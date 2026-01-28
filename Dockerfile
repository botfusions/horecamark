FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    wget \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy scraper code
COPY scraper /app/scraper

# Create directories for logs and reports
RUN mkdir -p /app/logs /app/reports

# Copy entrypoint script
COPY scraper/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Install Playwright browsers at runtime with retries
RUN playwright install --with-deps chromium || \
    (sleep 5 && playwright install --with-deps chromium) || \
    (sleep 10 && playwright install --with-deps chromium)

# Set the entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "scraper.main"]
