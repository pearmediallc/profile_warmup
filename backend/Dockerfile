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

# CRITICAL: Install Chromium browser with all dependencies
# --with-deps ensures all system libraries are installed
RUN playwright install chromium --with-deps

# Debug: Verify Chromium is installed (check both possible locations)
RUN echo "=== Playwright Browser Info ===" && \
    playwright --version && \
    echo "Checking /root/.cache/ms-playwright:" && \
    find /root/.cache/ms-playwright -name "chrome" -type f 2>/dev/null | head -3 || echo "Not in /root/.cache" && \
    echo "Checking /ms-playwright:" && \
    find /ms-playwright -name "chrome" -type f 2>/dev/null | head -3 || echo "Not in /ms-playwright"

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
