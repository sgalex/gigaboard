# Backend Dockerfile for GigaBoard
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy pyproject.toml and uv.lock first for better caching
COPY apps/backend/pyproject.toml apps/backend/uv.lock* ./

# Install Python dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Ensure asyncpg is installed (PostgreSQL async driver)
RUN uv pip install --system asyncpg==0.30.0

# Copy backend application code
COPY apps/backend/app ./app
COPY apps/backend/migrations ./migrations

# Create directory for uploads
RUN mkdir -p /app/uploads && chmod 755 /app/uploads

# Set PYTHONPATH to include /app for imports
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run Alembic migrations and start server
# Skip migrations for now - run them manually if needed
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
