# Use plain Python image
FROM python:3.11-slim

# Cache buster - change this to force rebuild
ARG CACHEBUST=8

# Install system dependencies for Chromium
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers - THIS IS CRITICAL
# Must happen AFTER pip install playwright
RUN echo "Installing Playwright Chromium browser..." && \
    playwright install chromium && \
    playwright install-deps chromium && \
    echo "Browser installation complete!"

# VERIFY the browser exists - FAIL BUILD if not
RUN echo "=== VERIFYING BROWSER INSTALLATION ===" && \
    ls -la /root/.cache/ms-playwright/ && \
    CHROME_PATH=$(find /root/.cache/ms-playwright -name "chrome" -type f | head -1) && \
    if [ -z "$CHROME_PATH" ]; then \
        echo "ERROR: Chrome executable NOT FOUND!" && \
        exit 1; \
    else \
        echo "SUCCESS: Found Chrome at: $CHROME_PATH"; \
    fi

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV RENDER=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
