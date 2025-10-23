#!/bin/bash
# Script to create account from .env file

set -a
source .env
set +a

# AIRBNB_COOKIE is already quoted in .env, so use it as-is
curl -X POST http://localhost:8000/api/v1/accounts \
  -H "Content-Type: application/json" \
  -d "{
  \"account_id\": \"${ACCOUNT_ID}\",
  \"airbnb_cookie\": ${AIRBNB_COOKIE},
  \"x_airbnb_client_trace_id\": \"${X_AIRBNB_CLIENT_TRACE_ID}\",
  \"x_client_version\": \"${X_CLIENT_VERSION}\",
  \"user_agent\": \"${USER_AGENT}\",
  \"is_active\": true
}"
