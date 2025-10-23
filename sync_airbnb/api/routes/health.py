import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine

from sync_airbnb import config
from sync_airbnb.dependencies import get_db_engine

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    mode: str
    account_id: str | None


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        mode=config.MODE or "unknown",
        account_id=config.ACCOUNT_ID,
    )


@router.get(
    "/health/ready",
    summary="Readiness check with database connectivity",
    description="""
    Readiness check that verifies the service can handle requests.

    This endpoint:
    - Tests database connectivity with a simple SELECT 1 query
    - Returns 200 if all dependencies are healthy
    - Returns 503 if any dependency is unhealthy

    **Use Cases:**
    - Kubernetes readiness probe
    - Before routing traffic to a new instance
    - Monitoring database connection health
    """,
)
async def readiness_check(engine: Engine = Depends(get_db_engine)):
    """Readiness check with database connectivity test."""
    checks = {}

    # Check database connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        checks["database"] = f"error: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "unavailable", "checks": checks}
        )

    return {"status": "ready", "checks": checks}


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="""
    Prometheus metrics endpoint for monitoring and observability.

    **Metrics Categories:**
    - HTTP: Request counts, duration, status codes
    - Database: Query duration, connection pool, query counts
    - Sync Jobs: Job duration, listing success/failure, active jobs
    - Airbnb API: Request duration, retries, rate limits
    - Errors: Error counts by type and component
    """,
    response_class=PlainTextResponse,
)
async def metrics_endpoint():
    """Expose Prometheus metrics."""
    return PlainTextResponse(content=generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
