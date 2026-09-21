FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install minimal system dependencies required for native compilation & health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root application user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# Install Python dependencies with Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create and configure upload directory with non-root ownership
RUN mkdir -p /app/data/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose backend port
EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI application using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
