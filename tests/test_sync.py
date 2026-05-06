"""Tests for the sync queue: /api/sync/*"""

import pytest
from tests.conftest import SYNC_SECRET

# ── Fixtures / helpers ────────────────────────────────────────────────────────

AUTH = {"x-sync-secret": SYNC_SECRET}
BAD_AUTH = {"x-sync-secret": "wrong-secret"}

WORD_PAYLOAD = {
    "hanzi": "学习",
    "pinyin": "xue2 xi2",
    "definition": "to study; to learn",
    "sentence_hanzi": "我每天学习中文。",
    "sentence_pinyin": "Wo3 mei3 tian1 xue2 xi2 Zhong1 wen2.",
    "sentence_english": "I study Chinese every day.",
    "hsk_level": 2,
    "part_of_speech": "verb",
}

WORD_PAYLOAD_2 = {
    "hanzi": "工作",
    "pinyin": "gong1 zuo4",
    "definition": "work; job",
    "hsk_level": 2,
}


@pytest.fixture(autouse=True)
def clear_queue(db_session):
    """
    Wipe the card_queue table before each test so tests don't bleed into each other.
    """
    from app.models.card_queue import CardQueue
    db_session.query(CardQueue).delete()
    db_session.commit()
    yield


# ── POST /api/sync/queue ──────────────────────────────────────────────────────

def test_queue_card_returns_queued_true(client):
    """Queueing a new word returns queued=True."""
    resp = client.post("/api/sync/queue", json=WORD_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued"] is True


def test_queue_card_creates_4_cards_normal_mode(client, db_session):
    """Normal mode (strict_mode=False) creates 4 card rows."""
    from app.models.card_queue import CardQueue
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    count = db_session.query(CardQueue).filter(CardQueue.hanzi == "学习").count()
    assert count == 4


def test_queue_card_creates_2_cards_strict_mode(client, db_session):
    """Strict mode creates only 2 card rows (zh_to_en + zh_sentence)."""
    from app.models.settings import AppSettings
    from app.services.service_cache import invalidate_settings

    # Enable strict mode and flush the settings cache so the next request picks
    # up the new value rather than the previously-expunged stale copy.
    s = db_session.query(AppSettings).first()
    s.strict_mode = True
    db_session.commit()
    invalidate_settings()

    try:
        from app.models.card_queue import CardQueue
        resp = client.post("/api/sync/queue", json=WORD_PAYLOAD)
        assert resp.json()["queued"] is True
        count = db_session.query(CardQueue).filter(CardQueue.hanzi == "学习").count()
        assert count == 2
    finally:
        s.strict_mode = False
        db_session.commit()
        invalidate_settings()


def test_queue_card_no_sentence_skips_sentence_cards(client, db_session):
    """When no sentence is provided, sentence card types are skipped."""
    from app.models.card_queue import CardQueue
    payload = {k: v for k, v in WORD_PAYLOAD.items()
               if k not in ("sentence_hanzi", "sentence_pinyin", "sentence_english")}
    client.post("/api/sync/queue", json=payload)
    cards = db_session.query(CardQueue).filter(CardQueue.hanzi == "学习").all()
    types = {c.card_type for c in cards}
    assert not any("sentence" in t for t in types)


def test_queue_card_duplicate_returns_already_queued(client):
    """Queueing the same hanzi twice returns already_queued=True on the second call."""
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    resp = client.post("/api/sync/queue", json=WORD_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["queued"] is False
    assert data["already_queued"] is True


def test_queue_card_duplicate_does_not_add_rows(client, db_session):
    """A duplicate queue request does not add new rows to card_queue."""
    from app.models.card_queue import CardQueue
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    before = db_session.query(CardQueue).filter(CardQueue.hanzi == "学习").count()
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    after = db_session.query(CardQueue).filter(CardQueue.hanzi == "学习").count()
    assert before == after


def test_queue_card_missing_required_fields(client):
    """Missing required fields returns 422."""
    resp = client.post("/api/sync/queue", json={"hanzi": "学习"})  # missing pinyin + definition
    assert resp.status_code == 422


# ── GET /api/sync/check ───────────────────────────────────────────────────────

def test_check_not_queued(client):
    """A word not in the queue returns queued=False."""
    resp = client.get("/api/sync/check?hanzi=未知")
    assert resp.status_code == 200
    assert resp.json()["queued"] is False


def test_check_queued_after_add(client):
    """A word shows queued=True after being added."""
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    resp = client.get("/api/sync/check?hanzi=学习")
    assert resp.status_code == 200
    assert resp.json()["queued"] is True


# ── GET /api/sync/pending ─────────────────────────────────────────────────────

def test_pending_requires_auth(client):
    """GET /pending returns 401 without the sync secret header."""
    resp = client.get("/api/sync/pending")
    assert resp.status_code == 401


def test_pending_wrong_secret(client):
    """GET /pending returns 401 with a wrong secret."""
    resp = client.get("/api/sync/pending", headers=BAD_AUTH)
    assert resp.status_code == 401


def test_pending_with_valid_auth_returns_200(client):
    """GET /pending returns 200 with the correct sync secret."""
    resp = client.get("/api/sync/pending", headers=AUTH)
    assert resp.status_code == 200


def test_pending_lists_queued_cards(client):
    """After queueing a word, it appears in /pending."""
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    data = client.get("/api/sync/pending", headers=AUTH).json()
    assert data["pending_count"] >= 1
    hanzi_list = [c["hanzi"] for c in data["cards"]]
    assert "学习" in hanzi_list


# ── POST /api/sync/ack ────────────────────────────────────────────────────────

def test_ack_requires_auth(client):
    """POST /ack returns 401 without auth."""
    resp = client.post("/api/sync/ack", json={"ids": []})
    assert resp.status_code == 401


def test_ack_marks_cards_synced(client, db_session):
    """ACKing pending card IDs marks them as synced."""
    from app.models.card_queue import CardQueue

    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    pending = client.get("/api/sync/pending", headers=AUTH).json()
    ids = [c["id"] for c in pending["cards"]]
    assert ids  # sanity

    resp = client.post("/api/sync/ack", json={"ids": ids}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == len(ids)

    # Confirm status in DB
    for card_id in ids:
        card = db_session.query(CardQueue).filter(CardQueue.id == card_id).first()
        db_session.refresh(card)
        assert card.status == "synced"


def test_ack_synced_cards_dont_appear_in_check(client):
    """Once synced, the hanzi still reports queued=True (prevents re-add)."""
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    pending = client.get("/api/sync/pending", headers=AUTH).json()
    ids = [c["id"] for c in pending["cards"]]
    client.post("/api/sync/ack", json={"ids": ids}, headers=AUTH)

    # Should still show as queued (synced cards block re-adds)
    check = client.get("/api/sync/check?hanzi=学习").json()
    assert check["queued"] is True


# ── GET /api/sync/stats ───────────────────────────────────────────────────────

def test_stats_returns_counts(client):
    """Stats endpoint returns pending/synced/failed/total."""
    resp = client.get("/api/sync/stats")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("pending", "synced", "failed", "total"):
        assert key in data


def test_stats_pending_increments_on_queue(client):
    """Pending count increases after queueing a word."""
    before = client.get("/api/sync/stats").json()["pending"]
    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    after = client.get("/api/sync/stats").json()["pending"]
    assert after > before


# ── DELETE /api/sync/clear-synced ────────────────────────────────────────────

def test_clear_synced_requires_auth(client):
    """DELETE /clear-synced returns 401 without auth."""
    resp = client.delete("/api/sync/clear-synced")
    assert resp.status_code == 401


def test_clear_synced_removes_synced_rows(client, db_session):
    """After ACK + clear-synced, synced rows are gone."""
    from app.models.card_queue import CardQueue

    client.post("/api/sync/queue", json=WORD_PAYLOAD)
    pending = client.get("/api/sync/pending", headers=AUTH).json()
    ids = [c["id"] for c in pending["cards"]]
    client.post("/api/sync/ack", json={"ids": ids}, headers=AUTH)

    resp = client.delete("/api/sync/clear-synced", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == len(ids)

    remaining = db_session.query(CardQueue).filter(CardQueue.status == "synced").count()
    assert remaining == 0
