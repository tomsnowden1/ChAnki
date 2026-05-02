"""Hybrid sentence retrieval: Tatoeba primary, Gemini fallback (cached)."""
import logging
from typing import Dict, List

import jieba
from pypinyin import lazy_pinyin, Style
from sqlalchemy.orm import Session

from app.models import Sentence, SentenceWord, DictionaryEntry

logger = logging.getLogger(__name__)


class SentenceService:
    """Find example sentences for a Chinese word.

    Prefers Tatoeba (offline, free). Falls back to Gemini and persists the
    result so the same word never costs two API calls.
    """

    def __init__(self, db: Session, gemini):
        self.db = db
        self.gemini = gemini

    def find_sentences(
        self,
        hanzi: str,
        pinyin: str = "",
        definition: str = "",
        hsk_level: int = 3,
        count: int = 3,
    ) -> List[Dict[str, str]]:
        """Return up to `count` sentence dicts: {hanzi, pinyin, english, source}."""
        results = self._tatoeba_lookup(hanzi, hsk_level, count)

        if len(results) < count and self.gemini is not None:
            needed = count - len(results)
            results.extend(self._fallback_to_gemini(
                hanzi, pinyin, definition, hsk_level, needed
            ))

        return [self._row_to_dict(r) for r in results]

    async def find_sentences_async(
        self,
        hanzi: str,
        pinyin: str = "",
        definition: str = "",
        hsk_level: int = 3,
        count: int = 3,
    ) -> List[Dict[str, str]]:
        """Async variant — Tatoeba is sync SQL, only the Gemini fallback awaits."""
        results = self._tatoeba_lookup(hanzi, hsk_level, count)

        if len(results) < count and self.gemini is not None:
            needed = count - len(results)
            results.extend(await self._fallback_to_gemini_async(
                hanzi, pinyin, definition, hsk_level, needed
            ))

        return [self._row_to_dict(r) for r in results]

    def _tatoeba_lookup(self, hanzi: str, hsk_level: int, count: int) -> List[Sentence]:
        """Fast SQL-only path. Shared by sync and async."""
        # Length cap loosens with target HSK: 8 / 16 / 32 chars.
        max_len = 8 if hsk_level <= 2 else (16 if hsk_level <= 4 else 32)
        candidates = (
            self.db.query(Sentence)
            .join(SentenceWord, SentenceWord.sentence_id == Sentence.id)
            .filter(SentenceWord.word == hanzi)
            .filter(Sentence.char_length <= max_len)
            .order_by(Sentence.char_length.asc(), Sentence.hsk_score.asc())
            .limit(count * 4)
            .all()
        )
        # If the cap was too tight, retry without a length filter.
        if len(candidates) < count:
            candidates = (
                self.db.query(Sentence)
                .join(SentenceWord, SentenceWord.sentence_id == Sentence.id)
                .filter(SentenceWord.word == hanzi)
                .order_by(Sentence.char_length.asc(), Sentence.hsk_score.asc())
                .limit(count * 4)
                .all()
            )
        return self._pick_diverse(candidates, count)

    @staticmethod
    def _row_to_dict(r: Sentence) -> Dict[str, str]:
        return {
            "hanzi": r.hanzi,
            "pinyin": r.pinyin,
            "english": r.english,
            "source": r.source,
        }

    def _pick_diverse(self, rows: List[Sentence], count: int) -> List[Sentence]:
        """Bucket by length (short/med/long) and round-robin pick."""
        if len(rows) <= count:
            return list(rows)

        short, medium, long_ = [], [], []
        for r in rows:
            if r.char_length <= 8:
                short.append(r)
            elif r.char_length <= 16:
                medium.append(r)
            else:
                long_.append(r)

        picked: List[Sentence] = []
        buckets = [short, medium, long_]
        while len(picked) < count and any(buckets):
            for b in buckets:
                if b and len(picked) < count:
                    picked.append(b.pop(0))
        return picked

    def _fallback_to_gemini(
        self, hanzi: str, pinyin: str, definition: str, hsk_level: int, needed: int
    ) -> List[Sentence]:
        """Sync path — call Gemini, persist, return."""
        try:
            raw = self.gemini.generate_sentences(hanzi, pinyin, definition, hsk_level)
        except Exception as e:
            logger.error(f"Gemini fallback failed for '{hanzi}': {e}")
            return []
        return self._persist_gemini_results(hanzi, hsk_level, raw, needed)

    async def _fallback_to_gemini_async(
        self, hanzi: str, pinyin: str, definition: str, hsk_level: int, needed: int
    ) -> List[Sentence]:
        """Async path — same logic, but doesn't block the FastAPI worker."""
        try:
            raw = await self.gemini.generate_sentences_async(
                hanzi, pinyin, definition, hsk_level
            )
        except Exception as e:
            logger.error(f"Gemini async fallback failed for '{hanzi}': {e}")
            return []
        return self._persist_gemini_results(hanzi, hsk_level, raw, needed)

    def _persist_gemini_results(
        self, hanzi: str, hsk_level: int, raw, needed: int
    ) -> List[Sentence]:
        """Validate Gemini output, persist into Sentence/SentenceWord, return rows."""
        valid = [s for s in raw if isinstance(s, dict) and "hanzi" in s and "english" in s]
        if not valid:
            return []

        known_words = self._dict_words_set()
        cached_objs: List[Sentence] = []
        for s in valid[:needed]:
            sentence_hanzi = s["hanzi"]
            sentence_pinyin = s.get("pinyin") or self._to_pinyin(sentence_hanzi)
            tokens = [t for t in jieba.cut(sentence_hanzi) if t.strip() and t in known_words]
            obj = Sentence(
                hanzi=sentence_hanzi,
                pinyin=sentence_pinyin,
                english=s["english"],
                source="gemini",
                hsk_score=hsk_level,
                char_length=len(sentence_hanzi),
                tatoeba_id=None,
            )
            self.db.add(obj)
            self.db.flush()
            for tok in set(tokens):
                self.db.add(SentenceWord(word=tok, sentence_id=obj.id))
            # Always index under the queried word so future lookups for it hit cache.
            if hanzi not in tokens:
                self.db.add(SentenceWord(word=hanzi, sentence_id=obj.id))
            cached_objs.append(obj)

        self.db.commit()
        return cached_objs

    def _dict_words_set(self):
        """Set of all simplified entries — used to filter jieba noise tokens."""
        if not hasattr(self, "_dict_words"):
            rows = self.db.query(DictionaryEntry.simplified).all()
            self._dict_words = {r[0] for r in rows if r[0]}
        return self._dict_words

    @staticmethod
    def _to_pinyin(hanzi: str) -> str:
        return " ".join(
            s for s in lazy_pinyin(hanzi, style=Style.TONE3, neutral_tone_with_five=True) if s
        )
