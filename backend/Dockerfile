# Use plain Python image
FROM python:3.11-slim

# Cache buster - change this to force rebuild
ARG CACHEBUST=9

# Set Playwright browser path to a fixed location INSIDE /app
# This ensures browsers are found regardless of user/home directory
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright-browsers

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

# Install Playwright browsers to the fixed path
# PLAYWRIGHT_BROWSERS_PATH is already set above
RUN echo "Installing Playwright Chromium to $PLAYWRIGHT_BROWSERS_PATH..." && \
    playwright install chromium && \
    playwright install-deps chromium && \
    echo "Browser installation complete!"

# VERIFY the browser exists - FAIL BUILD if not
RUN echo "=== VERIFYING BROWSER INSTALLATION ===" && \
    echo "Browser path: $PLAYWRIGHT_BROWSERS_PATH" && \
    ls -la $PLAYWRIGHT_BROWSERS_PATH/ && \
    CHROME_PATH=$(find $PLAYWRIGHT_BROWSERS_PATH -name "chrome" -type f 2>/dev/null | head -1) && \
    if [ -z "$CHROME_PATH" ]; then \
        echo "ERROR: Chrome executable NOT FOUND!" && \
        find $PLAYWRIGHT_BROWSERS_PATH -type f -name "*chrom*" 2>/dev/null && \
        exit 1; \
    else \
        echo "SUCCESS: Found Chrome at: $CHROME_PATH" && \
        ls -la "$CHROME_PATH"; \
    fi

# Copy application code
COPY . .

# Environment variables (PLAYWRIGHT_BROWSERS_PATH already set above)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV RENDER=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
