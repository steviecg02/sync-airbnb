# Multi-Tenant Architecture

## Overview

The sync-airbnb service supports multi-tenant architecture through the `customer_id` field on accounts. This allows grouping multiple Airbnb accounts under a single customer or tenant for organizational purposes.

## Customer ID Field

### Purpose

The `customer_id` field is a UUID that associates an Airbnb account with an external customer or tenant. This enables:

- **SaaS platforms**: Manage accounts for multiple customers
- **Property management agencies**: Organize accounts by client
- **Internal teams**: Separate accounts by department or business unit
- **Resellers**: Group accounts by end customer

### Schema

```sql
CREATE TABLE airbnb.accounts (
    account_id VARCHAR(255) PRIMARY KEY,  -- Airbnb account ID
    customer_id UUID,                      -- External customer/tenant ID
    ...
);

CREATE INDEX idx_accounts_customer_id ON airbnb.accounts(customer_id);
```

## Setting Customer ID

### During Account Creation

When creating an account via the API, include the `customer_id` field:

```bash
POST /api/v1/accounts
Content-Type: application/json

{
  "account_id": "310316675",
  "customer_id": "550e8400-e29b-41d4-a716-446655440000",
  "airbnb_cookie": "...",
  "x_airbnb_client_trace_id": "...",
  "x_client_version": "...",
  "user_agent": "...",
  "is_active": true
}
```

**Response:**
```json
{
  "account_id": "310316675",
  "customer_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_active": true,
  "last_sync_at": null,
  "created_at": "2025-10-21T12:00:00Z",
  "updated_at": "2025-10-21T12:00:00Z",
  "deleted_at": null
}
```

### Updating Customer Assignment

You can reassign an account to a different customer:

```bash
PATCH /api/v1/accounts/310316675
Content-Type: application/json

{
  "customer_id": "660f9511-f3ac-52e5-b827-557766551111"
}
```

### Removing Customer Assignment

Set `customer_id` to `null` to unassign:

```bash
PATCH /api/v1/accounts/310316675
Content-Type: application/json

{
  "customer_id": null
}
```

## Querying by Customer

### Future API Enhancement (Not Implemented Yet)

The service will support filtering accounts by customer:

```bash
# Get all accounts for a customer
GET /api/v1/accounts?customer_id=550e8400-e29b-41d4-a716-446655440000

# Get active accounts for a customer
GET /api/v1/accounts?customer_id=550e8400-e29b-41d4-a716-446655440000&active_only=true
```

### Direct Database Queries

For now, query the database directly:

```sql
-- Get all accounts for a customer
SELECT *
FROM airbnb.accounts
WHERE customer_id = '550e8400-e29b-41d4-a716-446655440000'
  AND deleted_at IS NULL;

-- Get all active accounts for a customer
SELECT *
FROM airbnb.accounts
WHERE customer_id = '550e8400-e29b-41d4-a716-446655440000'
  AND is_active = true
  AND deleted_at IS NULL;

-- Count accounts per customer
SELECT customer_id, COUNT(*) as account_count
FROM airbnb.accounts
WHERE deleted_at IS NULL
GROUP BY customer_id;
```

## Metrics Queries by Customer

### Get All Metrics for a Customer

Query metrics across all accounts belonging to a customer:

```sql
-- Chart query metrics for customer
SELECT cq.*
FROM airbnb.chart_query cq
INNER JOIN airbnb.accounts a ON cq.account_id = a.account_id
WHERE a.customer_id = '550e8400-e29b-41d4-a716-446655440000'
  AND cq.time >= '2025-01-01'
  AND cq.time < '2025-02-01'
ORDER BY cq.time DESC;

-- List of metrics for customer
SELECT lm.*
FROM airbnb.list_of_metrics lm
INNER JOIN airbnb.accounts a ON lm.account_id = a.account_id
WHERE a.customer_id = '550e8400-e29b-41d4-a716-446655440000'
  AND lm.time >= '2025-01-01'
  AND lm.time < '2025-02-01'
ORDER BY lm.time DESC;
```

### Aggregate Metrics Across Customer Accounts

Calculate totals across all accounts:

```sql
-- Total views across all customer accounts per day
SELECT
    DATE(time) as date,
    SUM(home_page_views) as total_views,
    SUM(contact_host_clicks) as total_contact_clicks,
    SUM(visitors_views) as total_visitors
FROM airbnb.chart_query cq
INNER JOIN airbnb.accounts a ON cq.account_id = a.account_id
WHERE a.customer_id = '550e8400-e29b-41d4-a716-446655440000'
  AND cq.time >= '2025-01-01'
  AND cq.time < '2025-02-01'
GROUP BY DATE(time)
ORDER BY date DESC;

-- Average occupancy rate across customer accounts
SELECT
    AVG(avg_occupancy_rate) as avg_occupancy_rate,
    MIN(avg_occupancy_rate) as min_occupancy_rate,
    MAX(avg_occupancy_rate) as max_occupancy_rate
FROM airbnb.list_of_metrics lm
INNER JOIN airbnb.accounts a ON lm.account_id = a.account_id
WHERE a.customer_id = '550e8400-e29b-41d4-a716-446655440000'
  AND lm.time >= '2025-01-01'
  AND lm.time < '2025-02-01';
```

## Use Cases

### 1. SaaS Platform

A SaaS platform manages Airbnb accounts for multiple customers:

```python
# Customer onboarding flow
customer_id = str(uuid.uuid4())  # Generate new customer ID

# Create accounts for customer
for airbnb_account in customer_airbnb_accounts:
    create_account(
        account_id=airbnb_account.id,
        customer_id=customer_id,
        credentials=airbnb_account.credentials,
    )

# Query customer's metrics
metrics = query_metrics_by_customer(customer_id, start_date, end_date)
```

### 2. Property Management Agency

An agency manages properties for multiple clients:

```python
# Client structure
clients = {
    "acme_corp": "550e8400-e29b-41d4-a716-446655440000",
    "xyz_hotels": "660f9511-f3ac-52e5-b827-557766551111",
}

# Assign accounts to clients
for account in accounts:
    client_name = determine_client(account)
    update_account(
        account_id=account.account_id,
        customer_id=clients[client_name],
    )
```

### 3. Internal Teams

Separate accounts by department:

```python
# Department UUIDs
departments = {
    "marketing": "770fa622-g4bd-63f6-c938-668877662222",
    "sales": "880fb733-h5ce-74g7-d049-779988773333",
}

# Assign to departments
update_account(
    account_id="310316675",
    customer_id=departments["marketing"],
)
```

## Database Indexes

Ensure indexes exist for efficient queries:

```sql
-- Index on customer_id for fast filtering
CREATE INDEX IF NOT EXISTS idx_accounts_customer_id
ON airbnb.accounts(customer_id);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_accounts_customer_active
ON airbnb.accounts(customer_id, is_active)
WHERE deleted_at IS NULL;
```

## Best Practices

### 1. Generate Consistent Customer IDs

Use UUIDs (v4) for customer IDs to ensure uniqueness:

```python
import uuid

customer_id = str(uuid.uuid4())
# Example: "550e8400-e29b-41d4-a716-446655440000"
```

### 2. Maintain Mapping in Your System

Store the mapping between your internal customer ID and sync-airbnb customer_id:

```sql
-- Your application database
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    sync_airbnb_customer_id UUID,  -- Maps to airbnb.accounts.customer_id
    created_at TIMESTAMP
);
```

### 3. Handle Null Customer IDs

Some accounts may not belong to a customer (internal testing, demos):

```sql
-- Query accounts without customer assignment
SELECT *
FROM airbnb.accounts
WHERE customer_id IS NULL
  AND deleted_at IS NULL;
```

### 4. Audit Customer Changes

Log when accounts are reassigned to different customers:

```python
# Before updating
old_customer_id = get_account(account_id).customer_id

# Update
update_account(account_id, customer_id=new_customer_id)

# Log change
log_audit_event(
    event="customer_reassigned",
    account_id=account_id,
    old_customer_id=old_customer_id,
    new_customer_id=new_customer_id,
)
```

## Future Enhancements

The following features are planned but not yet implemented:

### API Filter by Customer (P3-27)

Add query parameter support:

```python
@router.get("/accounts")
async def list_accounts(
    customer_id: str | None = Query(None),
    ...
):
    if customer_id:
        accounts = get_accounts_by_customer(engine, customer_id)
    else:
        accounts = get_all_accounts(engine)
    return accounts
```

### Customer Metrics Aggregation Endpoint

Add endpoint to aggregate metrics across customer accounts:

```python
@router.get("/customers/{customer_id}/metrics/aggregate")
async def get_customer_metrics(
    customer_id: str,
    start_date: date,
    end_date: date,
):
    """Get aggregated metrics across all customer accounts."""
    return aggregate_metrics_by_customer(engine, customer_id, start_date, end_date)
```

### Customer Account Management

Add endpoints to manage customer accounts:

```python
# List accounts for customer
GET /api/v1/customers/{customer_id}/accounts

# Bulk assign accounts to customer
POST /api/v1/customers/{customer_id}/accounts/bulk-assign
```

## Summary

The `customer_id` field enables multi-tenant architecture for sync-airbnb:

- **Flexible**: Assign accounts to customers, teams, or clients
- **Scalable**: Efficiently query accounts and metrics by customer
- **Optional**: Accounts can exist without customer assignment
- **Future-proof**: Foundation for customer-level API features

For implementation questions or feature requests, see the main [ARCHITECTURE.md](ARCHITECTURE.md) documentation.
