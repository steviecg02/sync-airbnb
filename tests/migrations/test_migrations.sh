#!/bin/bash
# Test database migrations (upgrade/downgrade)
#
# Usage:
#   ./tests/migrations/test_migrations.sh
#
# Requirements:
#   - Docker running
#   - alembic installed

set -e

echo "========================================="
echo "Testing Database Migrations"
echo "========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Start test database
echo "Starting test database..."
docker run -d --name sync-airbnb-migration-test \
    -e POSTGRES_PASSWORD=test \
    -e POSTGRES_USER=test \
    -e POSTGRES_DB=test \
    -p 5433:5432 \
    timescale/timescaledb:latest-pg15 > /dev/null

# Wait for database to be ready
echo "Waiting for database..."
sleep 5

# Set test database URL
export DATABASE_URL="postgresql://test:test@localhost:5433/test"

# Function to cleanup
cleanup() {
    echo "Cleaning up..."
    docker rm -f sync-airbnb-migration-test > /dev/null 2>&1 || true
}

# Trap cleanup on exit
trap cleanup EXIT

# Test 1: Apply all migrations
echo ""
echo "Test 1: Applying all migrations (upgrade head)..."
if alembic upgrade head; then
    echo -e "${GREEN}✓ Migrations applied successfully${NC}"
else
    echo -e "${RED}✗ Migration upgrade failed${NC}"
    exit 1
fi

# Test 2: Verify schema exists
echo ""
echo "Test 2: Verifying schema..."
if docker exec sync-airbnb-migration-test psql -U test -d test -c "\dn" | grep -q "airbnb"; then
    echo -e "${GREEN}✓ Schema 'airbnb' exists${NC}"
else
    echo -e "${RED}✗ Schema 'airbnb' not found${NC}"
    exit 1
fi

# Test 3: Verify tables exist
echo ""
echo "Test 3: Verifying tables..."
TABLES=$(docker exec sync-airbnb-migration-test psql -U test -d test -c "\dt airbnb.*" | grep airbnb || true)
if [ -n "$TABLES" ]; then
    echo -e "${GREEN}✓ Tables created:${NC}"
    echo "$TABLES"
else
    echo -e "${RED}✗ No tables found in airbnb schema${NC}"
    exit 1
fi

# Test 4: Rollback all migrations
echo ""
echo "Test 4: Rolling back all migrations (downgrade base)..."
if alembic downgrade base; then
    echo -e "${GREEN}✓ Migrations rolled back successfully${NC}"
else
    echo -e "${RED}✗ Migration downgrade failed${NC}"
    exit 1
fi

# Test 5: Verify schema is removed
echo ""
echo "Test 5: Verifying schema removed..."
if docker exec sync-airbnb-migration-test psql -U test -d test -c "\dn" | grep -q "airbnb"; then
    echo -e "${RED}✗ Schema 'airbnb' still exists after downgrade${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Schema removed after downgrade${NC}"
fi

# Test 6: Re-apply all migrations
echo ""
echo "Test 6: Re-applying migrations (upgrade head)..."
if alembic upgrade head; then
    echo -e "${GREEN}✓ Migrations re-applied successfully${NC}"
else
    echo -e "${RED}✗ Migration re-upgrade failed${NC}"
    exit 1
fi

# Success
echo ""
echo "========================================="
echo -e "${GREEN}All migration tests passed!${NC}"
echo "========================================="
