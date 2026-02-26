# =============================================================================
# QAForge Backend — FastAPI + Python 3.11 + Playwright
# =============================================================================

FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg2, document processing, and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    wget \
    # Playwright Chromium dependencies
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only — keeps image smaller)
RUN playwright install chromium

# Copy application source
COPY . .

# Health check (using python since wget HEAD doesn't work with FastAPI)
HEALTHCHECK --interval=15s --timeout=10s --retries=5 --start-period=30s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
