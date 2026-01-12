# Combined Dockerfile for Profile Warmup (Frontend + Backend)
# For local development with docker-compose
FROM python:3.11-slim

# Set Playwright browser path EARLY
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Install system dependencies for Chromium + Node.js
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    # Chromium dependencies
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
    libpango-1.0-0 \
    libcairo2 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxshmfence1 \
    xdg-utils \
    # Node.js for frontend build
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Build Frontend first
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
ENV VITE_API_URL=""
RUN npm run build

# Setup Backend
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers BEFORE copying code
RUN mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
    playwright install chromium && \
    playwright install-deps chromium

# Copy backend code
COPY backend/ .

# Copy built frontend to static folder
RUN mkdir -p /app/static && cp -r /frontend/dist/* /app/static/

# Verify browser installation
RUN echo "=== VERIFYING BROWSER ===" && \
    find $PLAYWRIGHT_BROWSERS_PATH -name "chrome" -type f | head -1

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
