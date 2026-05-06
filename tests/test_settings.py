"""Tests for GET/PUT /api/settings and POST /api/settings/test-openai"""

import pytest


# ── GET /api/settings ─────────────────────────────────────────────────────────

def test_get_settings_returns_200(client):
    """GET /api/settings returns 200."""
    resp = client.get("/api/settings")
    assert resp.status_code == 200


def test_get_settings_schema(client):
    """Settings response contains all expected fields."""
    data = client.get("/api/settings").json()
    for field in (
        "anki_deck_name", "anki_model_name", "openai_api_key",
        "hsk_target_level", "tone_colors_enabled", "generate_audio", "strict_mode",
    ):
        assert field in data, f"settings missing '{field}'"


def test_get_settings_openai_key_is_masked_or_empty(client):
    """openai_api_key is never returned in plaintext — either empty or sentinel."""
    data = client.get("/api/settings").json()
    key_val = data["openai_api_key"]
    # Either empty (no key set) or the sentinel value
    assert key_val == "" or key_val == "••••••••"


# ── PUT /api/settings ─────────────────────────────────────────────────────────

def test_update_deck_name(client):
    """PUT /api/settings updates anki_deck_name."""
    resp = client.put("/api/settings", json={"anki_deck_name": "NewDeck::Test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["anki_deck_name"] == "NewDeck::Test"


def test_update_hsk_level(client):
    """PUT /api/settings updates hsk_target_level."""
    resp = client.put("/api/settings", json={"hsk_target_level": 4})
    assert resp.status_code == 200
    assert resp.json()["hsk_target_level"] == 4


def test_update_strict_mode_toggle(client):
    """PUT /api/settings toggles strict_mode."""
    # Enable
    resp = client.put("/api/settings", json={"strict_mode": True})
    assert resp.status_code == 200
    assert resp.json()["strict_mode"] is True

    # Disable
    resp = client.put("/api/settings", json={"strict_mode": False})
    assert resp.status_code == 200
    assert resp.json()["strict_mode"] is False


def test_update_invalid_hsk_level(client):
    """HSK level outside 1-6 is rejected with 422."""
    resp = client.put("/api/settings", json={"hsk_target_level": 99})
    assert resp.status_code == 422


def test_sentinel_key_not_saved(client, db_session):
    """Sending the sentinel value for openai_api_key does not overwrite the DB."""
    from app.models.settings import AppSettings

    # Set a real key first
    db = db_session
    s = db.query(AppSettings).first()
    original_key = s.openai_api_key
    s.openai_api_key = "sk-test-key"
    db.commit()

    try:
        # Send sentinel — should be a no-op
        client.put("/api/settings", json={"openai_api_key": "••••••••"})
        db.refresh(s)
        assert s.openai_api_key == "sk-test-key"
    finally:
        s.openai_api_key = original_key
        db.commit()


# ── POST /api/settings/test-openai ───────────────────────────────────────────

def test_test_openai_empty_key_returns_failure(client):
    """Testing an empty key returns success=False without hitting the API."""
    resp = client.post("/api/settings/test-openai", json={"api_key": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


def test_test_openai_invalid_key_returns_failure(client):
    """Testing a clearly invalid key returns success=False."""
    resp = client.post("/api/settings/test-openai", json={"api_key": "not-a-real-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "message" in data


def test_test_openai_missing_body(client):
    """Missing request body returns 422."""
    resp = client.post("/api/settings/test-openai")
    assert resp.status_code == 422
