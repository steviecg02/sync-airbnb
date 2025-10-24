#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

# Only create account in worker/hybrid mode (not in admin mode)
if [ "$MODE" = "worker" ] || [ "$MODE" = "hybrid" ]; then
    echo "Creating/updating account from environment..."
    python create_account.py
else
    echo "Skipping account creation (MODE=$MODE)"
fi

echo "Starting application..."
exec "$@"
