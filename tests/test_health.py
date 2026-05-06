"""Tests for GET /api/health"""

import pytest
from unittest.mock import patch


def test_health_returns_200(client):
    """Health endpoint is reachable and returns 200."""
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_health_response_structure(client):
    """Response contains overall_status, components, and timestamp."""
    data = client.get("/api/health").json()
    assert "overall_status" in data
    assert "components" in data
    assert "timestamp" in data


def test_health_has_required_components(client):
    """All three expected component keys are present."""
    components = client.get("/api/health").json()["components"]
    assert "database" in components
    assert "ai" in components
    assert "anki" in components


def test_health_component_schema(client):
    """Each component has name, status, message, and last_check."""
    components = client.get("/api/health").json()["components"]
    for key, comp in components.items():
        assert "name" in comp, f"{key} missing 'name'"
        assert "status" in comp, f"{key} missing 'status'"
        assert "message" in comp, f"{key} missing 'message'"
        assert "last_check" in comp, f"{key} missing 'last_check'"


def test_health_overall_status_is_valid(client):
    """overall_status is one of the three known values."""
    data = client.get("/api/health").json()
    assert data["overall_status"] in {"healthy", "degraded", "critical"}


def test_health_force_refresh(client):
    """force_refresh=true is accepted without error."""
    resp = client.get("/api/health?force_refresh=true")
    assert resp.status_code == 200


def test_health_anki_down_without_desktop(client):
    """AnkiConnect reports down when Anki is not running (expected in CI)."""
    components = client.get("/api/health").json()["components"]
    # In test environment Anki is never running
    assert components["anki"]["status"] == "down"
