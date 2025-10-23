#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Creating/updating account from environment..."
python create_account.py

echo "Starting application..."
exec "$@"
