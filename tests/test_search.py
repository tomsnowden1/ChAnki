"""Tests for GET /api/search"""

import pytest


def test_search_english_term(client):
    """Searching 'dog' returns at least one result."""
    resp = client.get("/api/search?q=dog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    hanzi_list = [r["simplified"] for r in data["results"]]
    assert "狗" in hanzi_list


def test_search_hanzi(client):
    """Searching by hanzi returns the matching entry."""
    resp = client.get("/api/search?q=你好")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(r["simplified"] == "你好" for r in data["results"])


def test_search_pinyin(client):
    """Searching by pinyin (ni3 hao3) returns 你好."""
    resp = client.get("/api/search?q=ni3+hao3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(r["simplified"] == "你好" for r in data["results"])


def test_search_no_match_returns_valid_response(client):
    """
    A nonsense query returns 200 with a well-formed response.
    The AI fallback may produce a result even for gibberish (that's by design);
    what we verify here is that the response shape is always correct.
    """
    resp = client.get("/api/search?q=xyzabc123notaword")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert "results" in data
    assert isinstance(data["results"], list)
    assert data["count"] == len(data["results"])


def test_search_missing_query_param(client):
    """Omitting q returns 422 Unprocessable Entity."""
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_search_result_schema(client):
    """Each result contains the expected fields."""
    data = client.get("/api/search?q=dog").json()
    assert data["count"] >= 1
    first = data["results"][0]
    for field in ("simplified", "traditional", "pinyin", "definitions"):
        assert field in first, f"result missing '{field}'"
    assert isinstance(first["definitions"], list)


def test_search_empty_string(client):
    """An empty q string is handled gracefully (200 or 422, not 500)."""
    resp = client.get("/api/search?q=")
    assert resp.status_code in (200, 422)
