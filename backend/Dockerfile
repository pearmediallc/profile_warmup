# Backend Dockerfile for Profile Warmup
FROM python:3.11-slim

# Install Chrome and dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    # Chrome dependencies
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome (using modern GPG key method - apt-key is deprecated)
RUN mkdir -p /etc/apt/keyrings \
    && wget -q -O /tmp/google-chrome.pub https://dl-ssl.google.com/linux/linux_signing_key.pub \
    && gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg /tmp/google-chrome.pub \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/google-chrome.pub

# Install matching ChromeDriver
RUN CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+' | head -1) \
    && echo "Chrome version: $CHROME_VERSION" \
    && DRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}.0/linux64/chromedriver-linux64.zip" \
    && echo "Downloading chromedriver from: $DRIVER_URL" \
    && wget -q -O /tmp/chromedriver.zip "$DRIVER_URL" || { \
        # Fallback: get latest chromedriver version for this major Chrome version
        CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d. -f1) \
        && LATEST_DRIVER=$(wget -qO- "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_MAJOR}") \
        && wget -q -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${LATEST_DRIVER}/linux64/chromedriver-linux64.zip"; \
    } \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64 \
    && chromedriver --version

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
