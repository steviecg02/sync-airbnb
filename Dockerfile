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
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable to distinguish prod vs local
ENV ENV=production

# Default command Render will run when the cron job fires
CMD ["python", "main.py"]