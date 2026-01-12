# Use official Playwright image - has browser dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Install curl for health check
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# EXPLICITLY install Playwright Chromium browser
# The base image has dependencies, but browser needs explicit install
RUN playwright install chromium

# Debug: Show where Chromium is installed
RUN echo "=== Playwright Browser Info ===" && \
    playwright --version && \
    find /ms-playwright -name "chrome" -o -name "chromium" 2>/dev/null | head -5 || true

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV RENDER=true

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
