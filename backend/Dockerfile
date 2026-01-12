# Use plain Python image
FROM python:3.11-slim

# Cache buster - change this to force rebuild
ARG CACHEBUST=12

# Set Playwright browser path EARLY - must be set before playwright install
# Using default path that Playwright expects
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Install ALL system dependencies for Chromium manually
# (playwright install-deps uses outdated package names for Debian trixie)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    # Chromium core dependencies
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
    # Font packages (with correct names for Debian trixie)
    fonts-liberation \
    fonts-unifont \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-tlwg-loma-otf \
    fonts-freefont-ttf \
    # Additional dependencies Playwright may need
    libglib2.0-0 \
    libexpat1 \
    libxcb-shm0 \
    libx11-xcb1 \
    libxcursor1 \
    libxi6 \
    libxtst6 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies FIRST
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser only (skip install-deps - we installed deps above)
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    echo "Installing Playwright Chromium to $PLAYWRIGHT_BROWSERS_PATH..." && \
    playwright install chromium && \
    echo "Browser installation complete!" && \
    echo "=== VERIFYING BROWSER INSTALLATION ===" && \
    find $PLAYWRIGHT_BROWSERS_PATH -name "chrome" -type f 2>/dev/null | head -5

# Now copy application code AFTER browser is installed
COPY . .

# Final verification - FAIL BUILD if browser not found
RUN echo "=== FINAL BROWSER VERIFICATION ===" && \
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

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV RENDER=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
