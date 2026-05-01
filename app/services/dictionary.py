"""Dictionary search service — FTS5 for English, indexed pinyin_plain for pinyin, SQL for hanzi"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import engine
from app.models.dictionary import DictionaryEntry
from app.models.ai_cache import AICache
from typing import List, Tuple
import re
import logging

logger = logging.getLogger(__name__)

_USE_FTS = engine.dialect.name == "sqlite"

_TONE_STRIP = re.compile(r'[\d\s]')
_HAN_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
_PINYIN_CHARS = re.compile(r'^[a-zA-Z0-9\s\u0100-\u017e]+$')


def _pinyin_plain(text: str) -> str:
    """'Nǐ Hǎo' or 'ni3 hao3' → 'nihao'"""
    import unicodedata
    # Decompose unicode (strips combining diacritics — tone marks)
    nfd = unicodedata.normalize('NFD', text.lower())
    stripped = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return _TONE_STRIP.sub('', stripped)


class DictionaryService:
    """Service for searching the CC-CEDICT dictionary"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> List[DictionaryEntry]:
        """
        Search by Han characters, pinyin (any romanisation), or English.
        Returns at most `limit` results ordered by relevance.
        """
        query = query.strip()
        if not query:
            return []

        if _HAN_RE.search(query):
            return self._search_hanzi(query, limit)

        # Normalise for pinyin comparison before deciding strategy
        plain = _pinyin_plain(query)

        # Try pinyin first if it looks like it (has vowels, short, no spaces indicating multi-word EN)
        if self._looks_like_pinyin(query, plain):
            results = self._search_pinyin(plain, query, limit)
            if results:
                return results

        # English FTS search
        results = self._search_english_fts(query, limit)
        if results:
            return results

        # Last resort: partial pinyin LIKE (catches e.g. "mao" matching "mao2ze2dong1")
        return self._search_pinyin_like(plain, limit)

    def search_with_ai_fallback(self, query: str, gemini_service, limit: int = 20) -> Tuple[List[DictionaryEntry], bool]:
        """Search with AI fallback; returns (results, is_ai_generated)."""
        results = self.search(query, limit)
        if results:
            return results, False

        # Check AI cache first
        cached = self.db.query(AICache).filter(AICache.query_text == query.lower()).first()
        if cached:
            entry = self._ai_cache_to_entry(cached)
            return [entry], True

        # Call Gemini
        if not gemini_service or not getattr(gemini_service, 'model', None):
            return [], False

        try:
            ai_result = gemini_service.define_word(query)
            if ai_result and ai_result.get('hanzi'):
                # Persist to cache
                cache_row = AICache(
                    query_text=query.lower(),
                    hanzi=ai_result.get('hanzi', ''),
                    pinyin=ai_result.get('pinyin', ''),
                    definition=ai_result.get('definition', ''),
                    part_of_speech=ai_result.get('part_of_speech'),
                )
                self.db.add(cache_row)
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()

                entry = self._ai_result_to_entry(ai_result)
                return [entry], True
        except Exception as e:
            logger.error(f"AI fallback failed: {e}")

        return [], False

    def get_by_hanzi(self, hanzi: str) -> List[DictionaryEntry]:
        return self.db.query(DictionaryEntry).filter(
            (DictionaryEntry.simplified == hanzi) | (DictionaryEntry.traditional == hanzi)
        ).all()

    # ------------------------------------------------------------------
    # Private search strategies
    # ------------------------------------------------------------------

    def _search_hanzi(self, hanzi: str, limit: int) -> List[DictionaryEntry]:
        """Exact match first, then substring — both use indexed columns."""
        exact = self.db.query(DictionaryEntry).filter(
            (DictionaryEntry.simplified == hanzi) | (DictionaryEntry.traditional == hanzi)
        ).limit(limit).all()
        if exact:
            return exact

        return self.db.query(DictionaryEntry).filter(
            DictionaryEntry.simplified.contains(hanzi) | DictionaryEntry.traditional.contains(hanzi)
        ).limit(limit).all()

    def _search_pinyin(self, plain: str, original: str, limit: int) -> List[DictionaryEntry]:
        """Exact pinyin_plain match, then prefix, then original pinyin LIKE."""
        # 1. Exact pinyin_plain
        exact = self.db.query(DictionaryEntry).filter(
            DictionaryEntry.pinyin_plain == plain
        ).limit(limit).all()
        if exact:
            return exact

        # 2. Prefix match on pinyin_plain (e.g. "ni" matches "ni3")
        prefix = self.db.query(DictionaryEntry).filter(
            DictionaryEntry.pinyin_plain.like(f'{plain}%')
        ).order_by(DictionaryEntry.hsk_level).limit(limit).all()
        if prefix:
            return prefix

        # 3. Original query against stored pinyin (handles "nǐ hǎo" → "ni3 hao3")
        return self.db.query(DictionaryEntry).filter(
            DictionaryEntry.pinyin.ilike(f'%{original}%')
        ).limit(limit).all()

    def _search_pinyin_like(self, plain: str, limit: int) -> List[DictionaryEntry]:
        return self.db.query(DictionaryEntry).filter(
            DictionaryEntry.pinyin_plain.like(f'%{plain}%')
        ).limit(limit).all()

    def _search_english_fts(self, query: str, limit: int) -> List[DictionaryEntry]:
        """
        Word-boundary FTS5 search on English definitions.
        'dog' matches entries containing the token 'dog' but NOT 'dogged' or 'dogma'.
        On Postgres (no FTS5), falls back to case-insensitive substring match.
        """
        if not _USE_FTS:
            return self.db.query(DictionaryEntry).filter(
                DictionaryEntry.definitions.ilike(f'%{query.lower()}%')
            ).limit(limit).all()

        try:
            # Escape FTS5 special chars
            safe_q = re.sub(r'["\*\(\)\^\~\:\.]', ' ', query).strip()
            if not safe_q:
                return []

            rows = self.db.execute(
                text("""
                    SELECT d.*
                    FROM dictionary d
                    JOIN definitions_fts f ON f.rowid = d.id
                    WHERE definitions_fts MATCH :q
                    ORDER BY rank
                    LIMIT :lim
                """),
                {'q': safe_q, 'lim': limit}
            ).fetchall()

            if not rows:
                return []

            ids = [r[0] for r in rows]  # first column is d.id
            # Preserve FTS rank order
            entries_map = {
                e.id: e for e in self.db.query(DictionaryEntry).filter(DictionaryEntry.id.in_(ids)).all()
            }
            return [entries_map[i] for i in ids if i in entries_map]

        except Exception as e:
            logger.warning(f"FTS search failed ({e}), falling back to LIKE")
            return self.db.query(DictionaryEntry).filter(
                DictionaryEntry.definitions.ilike(f'%{query.lower()}%')
            ).limit(limit).all()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_pinyin(original: str, plain: str) -> bool:
        """True when the input is plausibly pinyin rather than English."""
        if not _PINYIN_CHARS.match(original):
            return False
        # Must contain a vowel
        if not re.search(r'[aeiouüāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]', original.lower()):
            return False
        # Contains tone digit → definitely pinyin
        if re.search(r'\d', original):
            return True
        # Multi-word English phrases unlikely to be pinyin
        words = original.split()
        if len(words) > 3 or len(original) > 25:
            return False
        return True

    @staticmethod
    def _ai_result_to_entry(ai_result: dict) -> DictionaryEntry:
        import json
        return DictionaryEntry(
            traditional=ai_result.get('hanzi', ''),
            simplified=ai_result.get('hanzi', ''),
            pinyin=ai_result.get('pinyin', ''),
            pinyin_plain=_pinyin_plain(ai_result.get('pinyin', '')),
            definitions=json.dumps([ai_result.get('definition', '')]),
            part_of_speech=ai_result.get('part_of_speech'),
        )

    @staticmethod
    def _ai_cache_to_entry(cached: AICache) -> DictionaryEntry:
        import json
        return DictionaryEntry(
            traditional=cached.hanzi,
            simplified=cached.hanzi,
            pinyin=cached.pinyin,
            pinyin_plain=_pinyin_plain(cached.pinyin),
            definitions=json.dumps([cached.definition]),
            part_of_speech=cached.part_of_speech,
        )
