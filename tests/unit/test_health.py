"""Unit tests for the health check endpoint."""

import pytest


@pytest.mark.unit
async def test_health_returns_200(client):
    """Health endpoint should return 200 with status fields."""
    resp = await client.get("/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "ok"
    assert "database" in body
    assert body["version"] == "0.1.0"
