# ============================================================================
# Build Stage - Install dependencies and build wheels
# ============================================================================
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
# - gcc: C compiler for building Python packages
# - libpq-dev: PostgreSQL client library headers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies to /root/.local
# - --user: Install to user site-packages (portable)
# - --no-cache-dir: Don't cache downloaded packages (saves space)
# - --no-warn-script-location: Suppress warnings about bin directory
RUN pip install --user --no-cache-dir --no-warn-script-location -r requirements.txt

# ============================================================================
# Runtime Stage - Minimal production image
# ============================================================================
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies only (no build tools)
# - libpq5: PostgreSQL client library (runtime only, not headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Add .local/bin to PATH so installed scripts are available
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY sync_airbnb/ ./sync_airbnb/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY entrypoint.sh .
COPY create_account.py .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Set environment variable to distinguish prod vs local
ENV ENV=production

# Use entrypoint to run migrations before starting app
ENTRYPOINT ["./entrypoint.sh"]

# Default command - runs FastAPI service with scheduler
CMD ["uvicorn", "sync_airbnb.main:app", "--host", "0.0.0.0", "--port", "8000"]
