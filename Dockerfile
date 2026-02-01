# ===========================================
# Autonomous Scientific Research Platform
# Multi-stage Dockerfile
# ===========================================

# ===========================================
# BASE STAGE - Common dependencies
# ===========================================
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# ===========================================
# BUILDER STAGE - Build dependencies
# ===========================================
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Copy application code
COPY --chown=appuser:appgroup . .

# Install application in editable mode
RUN pip install -e .

# ===========================================
# DEVELOPMENT STAGE - Hot reload enabled
# ===========================================
FROM base AS development

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pytest-mock \
    httpx \
    watchfiles \
    debugpy

# Copy application code
COPY --chown=appuser:appgroup . .

# Environment for development
ENV DEBUG=true \
    LOG_LEVEL=DEBUG \
    RELOAD=true

# Expose ports (API + debugger)
EXPOSE 8000 5678

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with hot reload
CMD ["uvicorn", "platform.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/platform"]

# ===========================================
# PRODUCTION STAGE - Optimized for deployment
# ===========================================
FROM base AS production

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only necessary application files
COPY --from=builder --chown=appuser:appgroup /app/platform /app/platform
COPY --from=builder --chown=appuser:appgroup /app/pyproject.toml /app/
COPY --from=builder --chown=appuser:appgroup /app/requirements.txt /app/

# Install application
RUN pip install --no-cache-dir -e .

# Environment for production
ENV DEBUG=false \
    LOG_LEVEL=INFO \
    RELOAD=false \
    PYTHONOPTIMIZE=1

# Remove build tools to reduce image size
RUN apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache

# Expose API port
EXPOSE 8000

# Switch to non-root user
USER appuser

# Health check with shorter intervals for production
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run with production settings
CMD ["uvicorn", "platform.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]

# ===========================================
# TEST STAGE - For running tests in CI
# ===========================================
FROM development AS test

# Copy test files
COPY --chown=appuser:appgroup tests/ /app/tests/

# Set test environment
ENV ENVIRONMENT=test \
    TESTING=true

# Run tests as default command
CMD ["pytest", "tests/", "-v", "--cov=platform", "--cov-report=term-missing", "--cov-report=xml:/app/coverage.xml"]

# ===========================================
# LABELS
# ===========================================
LABEL org.opencontainers.image.title="Autonomous Scientific Research Platform" \
      org.opencontainers.image.description="AI agents autonomously conduct scientific research with automated verification" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="ASRP Team" \
      org.opencontainers.image.source="https://github.com/asrp/platform" \
      org.opencontainers.image.licenses="MIT"
