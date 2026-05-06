"""Database initialization and seeding utilities"""
from app.db.session import init_db, get_db, engine
from app.models import AppSettings, DictionaryEntry, Sentence
from app.db.cedict_downloader import CEDICTDownloader
from app.db.tatoeba_downloader import TatoebaDownloader
from sqlalchemy import text
from pathlib import Path
import re
import logging
import unicodedata

logger = logging.getLogger(__name__)


def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"

_TONE_STRIP = re.compile(r'[\d\s]')


def _pinyin_plain(pinyin: str) -> str:
    """Strip tone numbers and spaces: 'ni3 hao3' → 'nihao'"""
    return _TONE_STRIP.sub('', pinyin.lower())


def _pinyin_plain_from_marks(marked: str) -> str:
    """'àihào' → 'aihao' — decompose unicode and strip combining diacritics."""
    nfd = unicodedata.normalize('NFD', marked.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').replace(' ', '')


def run_schema_migrations():
    """
    Idempotent ALTER TABLE migrations for columns added after initial deploy.

    DDL is executed in AUTOCOMMIT mode so each statement is its own transaction
    and can never leave the session in an aborted-transaction state.
    Safe to call on every startup — duplicate-column errors are silently ignored.
    """
    if _is_sqlite():
        _run_migrations_sqlite()
    else:
        _run_migrations_postgres()


def _run_migrations_sqlite():
    """SQLite: no IF NOT EXISTS for ADD COLUMN; catch duplicate-column errors."""
    stmts = [
        "ALTER TABLE settings ADD COLUMN strict_mode BOOLEAN DEFAULT 0",
        "ALTER TABLE card_queue ADD COLUMN card_type TEXT",
        "ALTER TABLE card_queue ADD COLUMN hint TEXT",
        # OpenAI migration: add new column. SQLite can't drop columns easily,
        # so the legacy `gemini_api_key` column (if present) stays orphaned.
        "ALTER TABLE settings ADD COLUMN openai_api_key TEXT",
    ]
    with get_db() as db:
        for stmt in stmts:
            try:
                db.execute(text(stmt))
                db.commit()
            except Exception:
                db.rollback()  # column already exists → ignore


def _run_migrations_postgres():
    """Postgres: use AUTOCOMMIT so DDL never gets rolled back by session state."""
    stmts = [
        "ALTER TABLE settings   ADD COLUMN IF NOT EXISTS strict_mode BOOLEAN DEFAULT FALSE",
        "ALTER TABLE card_queue ADD COLUMN IF NOT EXISTS card_type   VARCHAR",
        "ALTER TABLE card_queue ADD COLUMN IF NOT EXISTS hint        VARCHAR",
        # OpenAI migration: add new key column, drop the legacy Gemini one.
        # Both IF [NOT] EXISTS so this is idempotent across redeploys.
        "ALTER TABLE settings ADD  COLUMN IF NOT EXISTS openai_api_key VARCHAR",
        "ALTER TABLE settings DROP COLUMN IF EXISTS gemini_api_key",
        # Composite index for the polling query (WHERE status='pending' ORDER BY created_at)
        "CREATE INDEX IF NOT EXISTS ix_card_queue_status_created ON card_queue (status, created_at)",
        # Generated tsvector column + GIN index for English full-text search.
        # Replaces the ILIKE '%query%' fallback (sequential-scans 124K rows) with
        # an indexed plainto_tsquery match — sub-millisecond on the same data.
        # ALTER + CREATE INDEX are both `IF NOT EXISTS` so this is idempotent.
        """ALTER TABLE dictionary
           ADD COLUMN IF NOT EXISTS definitions_ts tsvector
           GENERATED ALWAYS AS (to_tsvector('english', definitions)) STORED""",
        """CREATE INDEX IF NOT EXISTS ix_dictionary_definitions_ts
           ON dictionary USING gin (definitions_ts)""",
    ]
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for stmt in stmts:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    logger.warning(f"Migration skipped ({stmt[:40]}…): {e}")
    except Exception as e:
        logger.error(f"Schema migration connection failed: {e}")


def initialize_database():
    """Create all database tables"""
    print("Initializing database...")
    init_db()
    print("✓ Database tables created")

    run_schema_migrations()
    print("✓ Schema migrations applied")

    with get_db() as db:
        settings = db.query(AppSettings).first()
        if not settings:
            settings = AppSettings()
            db.add(settings)
            db.commit()
            print("✓ Default settings created")
        else:
            print("✓ Settings already exist")

    setup_fts(silent=False)


def setup_fts(silent: bool = True):
    """
    Idempotent migration: add pinyin_plain column, create FTS5 virtual table,
    backfill both for existing rows. SQLite-only — Postgres uses ILIKE fallback.
    """
    if not _is_sqlite():
        if not silent:
            print(f"✓ Skipping FTS5 setup on {engine.dialect.name} (uses ILIKE fallback)")
        return

    with get_db() as db:
        # 1. Add pinyin_plain column (no-op if already exists)
        try:
            db.execute(text("ALTER TABLE dictionary ADD COLUMN pinyin_plain TEXT DEFAULT ''"))
            db.commit()
            if not silent:
                print("✓ Added pinyin_plain column")
        except Exception:
            pass  # column already exists

        # 2. Create FTS5 virtual table for English definitions (word-boundary tokenisation)
        db.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS definitions_fts USING fts5(
                definitions_text,
                tokenize='unicode61',
                content='',
                contentless_delete=1
            )
        """))
        db.commit()

        # 3. Backfill pinyin_plain for rows that lack it
        missing = db.execute(text(
            "SELECT COUNT(*) FROM dictionary WHERE pinyin_plain IS NULL OR pinyin_plain = ''"
        )).scalar()

        if missing > 0:
            if not silent:
                print(f"  Backfilling pinyin_plain for {missing:,} rows...")
            rows = db.execute(text(
                "SELECT id, pinyin FROM dictionary WHERE pinyin_plain IS NULL OR pinyin_plain = ''"
            )).fetchall()
            for row in rows:
                plain = _pinyin_plain(row.pinyin)
                db.execute(
                    text("UPDATE dictionary SET pinyin_plain = :p WHERE id = :id"),
                    {'p': plain, 'id': row.id}
                )
            db.commit()
            if not silent:
                print(f"  ✓ pinyin_plain backfilled")

        # 4. Populate FTS5 if empty
        fts_count = db.execute(text("SELECT COUNT(*) FROM definitions_fts")).scalar()
        if fts_count == 0:
            if not silent:
                print("  Building FTS5 index for definitions...")
            db.execute(text("""
                INSERT INTO definitions_fts(rowid, definitions_text)
                SELECT id,
                       replace(replace(replace(replace(definitions,
                           '["', ''), '"]', ''), '", "', ' '), '\/', '')
                FROM dictionary
            """))
            db.commit()
            if not silent:
                new_count = db.execute(text("SELECT COUNT(*) FROM definitions_fts")).scalar()
                print(f"  ✓ FTS5 index built ({new_count:,} entries)")


def check_and_download_dictionary(auto_seed: bool = True) -> dict:
    """
    Check dictionary health and auto-heal if needed.

    Returns:
        {"ready": bool, "count": int, "message": str}
    """
    with get_db() as db:
        count = db.query(DictionaryEntry).count()

        if count >= 100000:
            logger.info(f"Dictionary healthy with {count:,} entries")
            return {"ready": True, "count": count, "message": f"Dictionary loaded ({count:,} entries)"}

        if 0 < count < 100000:
            logger.warning(f"Dictionary degraded: only {count:,} entries")
            return {
                "ready": False,
                "count": count,
                "message": f"Dictionary incomplete ({count:,} entries, need >100,000)"
            }

    # Empty — trigger auto-seed
    if not auto_seed:
        return {"ready": False, "count": 0, "message": "Dictionary empty (auto-seed disabled)"}

    logger.info("Self-Healing: Dictionary empty, initiating auto-download...")
    downloader = CEDICTDownloader()

    if not downloader.is_downloaded():
        print("\n" + "=" * 60)
        print("First-time setup: Downloading CC-CEDICT dictionary...")
        print("This may take 2-3 minutes...")
        print("=" * 60)

        if not downloader.download():
            logger.error("Auto-download failed")
            return {"ready": False, "count": 0, "message": "Auto-download failed. Please upload cedict_ts.u8 manually."}

    file_path = downloader.get_file_path()
    if file_path:
        logger.info(f"Seeding from {file_path}")
        seed_dictionary_from_cedict(file_path)

        with get_db() as db:
            final_count = db.query(DictionaryEntry).count()

        if final_count >= 100000:
            logger.info(f"✓ Self-healing complete: {final_count:,} entries loaded")
            return {"ready": True, "count": final_count, "message": f"Dictionary auto-seeded ({final_count:,} entries)"}
        else:
            logger.error(f"Seeding incomplete: only {final_count:,} entries")
            return {"ready": False, "count": final_count, "message": f"Seeding incomplete ({final_count:,} entries)"}

    return {"ready": False, "count": 0, "message": "Failed to locate dictionary file"}


def seed_dictionary_from_cedict(cedict_path: str):
    """Seed dictionary from CC-CEDICT file, including pinyin_plain and FTS5."""
    print(f"Seeding dictionary from {cedict_path}...")

    with get_db() as db:
        count = db.query(DictionaryEntry).count()
        if count > 0:
            print(f"✓ Dictionary already seeded with {count} entries")
            return

        entries_added = 0
        dict_batch = []
        fts_batch = []
        batch_size = 1000

        try:
            with open(cedict_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue

                    match = re.match(r'(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/', line)
                    if match:
                        traditional, simplified, pinyin_text, definitions = match.groups()
                        definitions_list = definitions.split('/')
                        plain = _pinyin_plain(pinyin_text)

                        entry = DictionaryEntry(
                            traditional=traditional,
                            simplified=simplified,
                            pinyin=pinyin_text,
                            pinyin_plain=plain,
                            definitions=__import__('json').dumps(definitions_list),
                        )
                        dict_batch.append(entry)
                        # FTS text: space-joined glosses
                        fts_batch.append(' '.join(definitions_list))
                        entries_added += 1

                        if len(dict_batch) >= batch_size:
                            db.bulk_save_objects(dict_batch)
                            db.commit()
                            # FTS inserts need the actual rowids — do after commit
                            _insert_fts_batch(db, dict_batch, fts_batch)
                            dict_batch = []
                            fts_batch = []
                            print(f"  Added {entries_added} entries...")

            if dict_batch:
                db.bulk_save_objects(dict_batch)
                db.commit()
                _insert_fts_batch(db, dict_batch, fts_batch)

            print(f"✓ Dictionary seeded with {entries_added} entries")

        except FileNotFoundError:
            print(f"✗ CEDICT file not found at {cedict_path}")
        except Exception as e:
            print(f"✗ Error seeding dictionary: {e}")
            db.rollback()


def _insert_fts_batch(db, dict_batch, fts_batch):
    """Insert a batch into definitions_fts using the assigned rowids. SQLite-only."""
    if not _is_sqlite():
        return
    # After bulk_save_objects + commit, entries have their IDs
    for entry, text_content in zip(dict_batch, fts_batch):
        if entry.id:
            db.execute(
                text("INSERT INTO definitions_fts(rowid, definitions_text) VALUES (:rid, :txt)"),
                {'rid': entry.id, 'txt': text_content}
            )
    db.commit()


def seed_hsk_levels():
    """
    Populate `dictionary.hsk_level` from the vendored HSK 1-6 word list at
    `data/hsk_levels.tsv` (sourced from krmanik/HSK-3.0, MIT-licensed, the
    HSK 2.0 sublist with levels 1-6).

    The list has format `simplified<TAB>pinyin<TAB>level`. We match against
    the existing `dictionary` table by simplified hanzi, with `pinyin_plain`
    as a tiebreaker for homographs (e.g. 行 xíng/háng have different levels).

    Idempotent: skips entirely when ≥4500 entries already carry an HSK level.

    Concurrency-safe: on Postgres uses pg_try_advisory_xact_lock() so that
    when multiple gunicorn workers all run startup simultaneously, only one
    performs the seeding — the rest skip immediately.

    Performance: builds all updates in memory then issues two bulk UPDATE …
    FROM (VALUES …) statements (one for pinyin-matched, one fallback).
    This replaces the old per-row loop (6 000+ individual UPDATEs) with two
    statements that complete in well under any reasonable Postgres timeout.
    """
    tsv_path = Path(__file__).resolve().parents[2] / "data" / "hsk_levels.tsv"
    if not tsv_path.exists():
        logger.warning(f"HSK levels file not found at {tsv_path}; skipping seed")
        return

    with get_db() as db:
        # ── Skip-if-already-seeded check ─────────────────────────────────────
        already = db.query(DictionaryEntry).filter(
            DictionaryEntry.hsk_level.isnot(None)
        ).count()
        if already >= 4500:
            logger.info(f"✓ HSK levels already seeded ({already:,} entries); skipping")
            return

        # ── Postgres concurrency guard ────────────────────────────────────────
        # With multiple gunicorn workers all running startup simultaneously,
        # only the worker that acquires this advisory lock does the seeding;
        # the rest return immediately.  The lock is released automatically
        # when this transaction ends (xact-level advisory lock).
        if not _is_sqlite():
            got_lock = db.execute(
                text("SELECT pg_try_advisory_xact_lock(8472638756)")
            ).scalar()
            if not got_lock:
                logger.info("HSK seed lock held by another worker — skipping")
                return
            # Re-check after acquiring the lock (another worker may have just finished)
            already = db.query(DictionaryEntry).filter(
                DictionaryEntry.hsk_level.isnot(None)
            ).count()
            if already >= 4500:
                logger.info(f"✓ HSK levels seeded by sibling worker ({already:,} entries)")
                return

        # ── Load TSV into memory ──────────────────────────────────────────────
        # rows: list of (simplified, pinyin_plain, level)
        rows: list = []
        with open(tsv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                simplified, pinyin_marked, level_str = parts[0], parts[1], parts[2]
                try:
                    level = int(level_str)
                except ValueError:
                    continue
                rows.append((simplified, _pinyin_plain_from_marks(pinyin_marked), level))

        if not rows:
            logger.warning("HSK TSV contained no parseable rows; skipping seed")
            return

        # ── Bulk UPDATE (fast path) ───────────────────────────────────────────
        # Instead of 6 000+ individual UPDATEs we build a temporary VALUES
        # table and let the DB engine do a single join-based update.
        # Batched in chunks of 500 to keep parameter lists manageable.
        updated = _bulk_update_hsk(db, rows)
        db.commit()
        logger.info(f"✓ HSK levels seeded: {updated:,} dictionary entries tagged")


def _bulk_update_hsk(db, rows: list) -> int:
    """
    Issue bulk UPDATE … FROM (VALUES …) statements for HSK level tagging.

    Strategy (same for SQLite and Postgres):
      1. Pinyin-exact pass: update rows where simplified AND pinyin_plain match.
      2. Simplified-fallback pass: update remaining NULL rows matched only by
         simplified (handles cases where pinyin_plain doesn't match).

    Batched in CHUNK-size groups so no single SQL statement becomes unwieldy.
    Returns total rows updated.
    """
    CHUNK = 500
    updated = 0

    if _is_sqlite():
        # SQLite has no VALUES-based UPDATE FROM; use individual updates but
        # commit every chunk to avoid a single massive transaction.
        with engine.begin() as conn:
            for simplified, pp, level in rows:
                r = conn.execute(
                    text(
                        "UPDATE dictionary SET hsk_level = :level "
                        "WHERE simplified = :s AND pinyin_plain = :pp "
                        "AND hsk_level IS NULL"
                    ),
                    {"level": level, "s": simplified, "pp": pp},
                )
                if r.rowcount == 0:
                    r = conn.execute(
                        text(
                            "UPDATE dictionary SET hsk_level = :level "
                            "WHERE simplified = :s AND hsk_level IS NULL"
                        ),
                        {"level": level, "s": simplified},
                    )
                updated += r.rowcount
        return updated

    # Postgres: VALUES-based bulk UPDATE (two passes per chunk)
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i: i + CHUNK]

        # Build VALUES placeholder: ($1,$2,$3), ($4,$5,$6), …
        placeholders = ", ".join(
            f"(:s{j}, :pp{j}, :lvl{j})" for j in range(len(chunk))
        )
        params = {}
        for j, (s, pp, lvl) in enumerate(chunk):
            params[f"s{j}"] = s
            params[f"pp{j}"] = pp
            params[f"lvl{j}"] = lvl

        # Pass 1: pinyin-exact match
        r = db.execute(text(f"""
            UPDATE dictionary AS d
            SET    hsk_level = v.lvl
            FROM   (VALUES {placeholders}) AS v(s, pp, lvl)
            WHERE  d.simplified  = v.s
            AND    d.pinyin_plain = v.pp
            AND    d.hsk_level IS NULL
        """), params)
        updated += r.rowcount

        # Pass 2: simplified-only fallback for unmatched rows in this chunk
        r = db.execute(text(f"""
            UPDATE dictionary AS d
            SET    hsk_level = v.lvl
            FROM   (VALUES {placeholders}) AS v(s, pp, lvl)
            WHERE  d.simplified = v.s
            AND    d.hsk_level IS NULL
        """), params)
        updated += r.rowcount

    return updated


SENTENCES_READY_THRESHOLD = 50_000


def check_and_seed_sentences(auto_seed: bool = True) -> dict:
    """Check sentence corpus and auto-download/seed Tatoeba if missing.

    Returns:
        {"ready": bool, "count": int, "message": str}
    """
    with get_db() as db:
        count = db.query(Sentence).count()

    if count >= SENTENCES_READY_THRESHOLD:
        logger.info(f"Sentences ready ({count:,} rows)")
        return {"ready": True, "count": count, "message": f"Sentences loaded ({count:,})"}

    if not auto_seed:
        return {"ready": False, "count": count, "message": "Sentence seed skipped"}

    logger.info("Self-Healing: Sentence corpus empty/incomplete, fetching Tatoeba...")
    downloader = TatoebaDownloader()
    if not downloader.is_downloaded():
        print("\n" + "=" * 60)
        print("First-time setup: Downloading Tatoeba sentence corpus...")
        print("(Three files, ~25 MB compressed total)")
        print("=" * 60)
        if not downloader.download():
            logger.error("Tatoeba download failed")
            return {"ready": False, "count": count, "message": "Tatoeba download failed"}

    paths = downloader.get_paths()
    if not paths:
        return {"ready": False, "count": count, "message": "Tatoeba files unavailable"}

    from app.db.seed_sentences import seed_sentences_from_tatoeba
    seed_sentences_from_tatoeba(paths["cmn"], paths["eng"], paths["links"])

    with get_db() as db:
        final = db.query(Sentence).count()
    if final >= SENTENCES_READY_THRESHOLD:
        logger.info(f"✓ Sentence seed complete: {final:,} rows")
        return {"ready": True, "count": final, "message": f"Sentences seeded ({final:,})"}
    return {"ready": False, "count": final, "message": f"Sentence seed incomplete ({final:,})"}
