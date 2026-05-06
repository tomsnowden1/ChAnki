"""
Shared pytest fixtures for ChAnki tests.

Strategy
--------
- All tests use an isolated SQLite file DB (test_chanki_pytest.db) so they
  never touch the real chanki.db.
- The FastAPI `get_db_session` dependency is overridden to use that test DB.
- The heavy startup steps (dictionary seeding, sentence seeding) are mocked
  so the test suite boots in under a second.
- A minimal AppSettings row is seeded once per session.
- The SYNC_SECRET defaults to DEFAULT_DEV_SYNC_SECRET when ENVIRONMENT is
  not "production", so no env-var fiddling is needed.
"""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Test DB ──────────────────────────────────────────────────────────────────

TEST_DB_PATH = "./test_chanki_pytest.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """FastAPI dependency override — yields a test DB session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Session-scoped DB setup / teardown ───────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Create tables + seed minimal data before any test runs.
    Drop everything and delete the DB file after the session.
    """
    from app.models import Base
    from app.models.settings import AppSettings
    from app.models.dictionary import DictionaryEntry
    import json

    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()

    # Seed settings row
    if not db.query(AppSettings).first():
        db.add(AppSettings(
            anki_deck_name="Test::Deck",
            anki_model_name="ChAnki-Master",
            openai_api_key=None,
            hsk_target_level=3,
            tone_colors_enabled=False,
            generate_audio=False,
            strict_mode=False,
        ))

    # Seed a handful of dictionary entries for search tests
    if not db.query(DictionaryEntry).first():
        entries = [
            DictionaryEntry(
                traditional="狗", simplified="狗", pinyin="gou3",
                pinyin_plain="gou",
                definitions=json.dumps(["dog", "CL:隻|只[zhi1]"]),
                hsk_level=2,
            ),
            DictionaryEntry(
                traditional="你好", simplified="你好", pinyin="ni3 hao3",
                pinyin_plain="nihao",
                definitions=json.dumps(["hello", "hi"]),
                hsk_level=1,
            ),
            DictionaryEntry(
                traditional="學習", simplified="学习", pinyin="xue2 xi2",
                pinyin_plain="xuexi",
                definitions=json.dumps(["to study", "to learn"]),
                hsk_level=2,
            ),
        ]
        db.bulk_save_objects(entries)

    db.commit()
    db.close()

    yield  # tests run here

    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


# ── TestClient fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client(setup_test_db):
    """
    FastAPI TestClient with:
      - test DB injected via dependency override
      - heavy startup I/O mocked out
    """
    from main import app
    from app.db.session import get_db_session

    app.dependency_overrides[get_db_session] = override_get_db

    startup_mocks = {
        "app.db.init_db.initialize_database": None,
        "app.db.init_db.check_and_download_dictionary": {
            "ready": True, "message": "Test: 3 entries loaded", "count": 3,
        },
        "app.db.init_db.seed_hsk_levels": None,
        "app.db.init_db.check_and_seed_sentences": {
            "ready": True, "message": "Test: 0 sentences ready", "count": 0,
        },
    }

    patches = []
    for target, return_value in startup_mocks.items():
        if return_value is None:
            p = patch(target)
        else:
            rv = return_value  # capture for lambda
            p = patch(target, return_value=rv)
        patches.append(p)
        p.start()

    with TestClient(app) as c:
        yield c

    for p in patches:
        p.stop()

    app.dependency_overrides.clear()


# ── Convenience fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """Direct DB session for tests that need to inspect the DB."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# The default dev sync secret — same value as app/config.py DEFAULT_DEV_SYNC_SECRET
SYNC_SECRET = "development_secret_change_in_production"
