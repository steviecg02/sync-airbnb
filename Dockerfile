# Use Python 3.10 slim base image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install Postgres client headers (for psycopg2/sqlalchemy)
RUN apt-get update && apt-get install -y \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy everything from your repo into the container
COPY . .

# Install dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variable to distinguish prod vs local
ENV ENV=production

# Use entrypoint to run migrations before starting app
ENTRYPOINT ["/entrypoint.sh"]

# Default command - runs FastAPI service with scheduler
CMD ["uvicorn", "sync_airbnb.main:app", "--host", "0.0.0.0", "--port", "8000"]