"""Tests for health and metrics endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from sync_airbnb.dependencies import get_db_engine
from sync_airbnb.main import app


@pytest.fixture
def client():
    """Create test client with mocked database."""
    mock_engine = MagicMock()

    def override_get_db_engine():
        yield mock_engine

    app.dependency_overrides[get_db_engine] = override_get_db_engine
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_health_check_returns_200(client):
    """Test that /health returns 200 with status ok."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "mode" in data


def test_readiness_check_returns_200_when_db_healthy(client):
    """Test that /health/ready returns 200 when database is accessible."""
    response = client.get("/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"


def test_metrics_endpoint_returns_prometheus_format(client):
    """Test that /metrics returns Prometheus text format."""
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    # Check for some expected metrics
    content = response.text
    assert "# HELP" in content
    assert "# TYPE" in content
    # Should have at least one of our custom metrics
    assert "sync_airbnb" in content or "http_requests" in content
