FROM python:3.11-slim-bullseye

# Install system dependencies for psycopg2-binary and other packages
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /onchain-scout

# Copy requirements first for better layer caching
COPY requirements.txt /onchain-scout/

# Install uv and dependencies
RUN pip install uv && \
    uv pip install -r requirements.txt --system

# Install OpenTelemetry
RUN opentelemetry-bootstrap --action=install

# Copy application code
COPY . /onchain-scout

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /onchain-scout
USER appuser

# Expose port 8000 to match docker-compose
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use the correct port in the command and handle migration issues
CMD ["bash", "-c", "alembic stamp head || alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]
