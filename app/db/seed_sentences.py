"""Seed Sentence/SentenceWord tables from Tatoeba TSV exports."""
import logging
from typing import Dict

import jieba
from pypinyin import lazy_pinyin, Style
from sqlalchemy import text

from app.db.session import get_db
from app.models import Sentence, SentenceWord, DictionaryEntry

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
UNKNOWN_HSK = 7


def _to_pinyin(hanzi: str) -> str:
    """Generate space-separated tone-numbered pinyin for a Chinese sentence."""
    syllables = lazy_pinyin(hanzi, style=Style.TONE3, neutral_tone_with_five=True)
    return " ".join(s for s in syllables if s)


def _load_dictionary_index(db) -> Dict[str, int]:
    """Build {simplified_word -> hsk_level} from the dictionary table."""
    rows = db.query(DictionaryEntry.simplified, DictionaryEntry.hsk_level).all()
    index = {}
    for simplified, hsk in rows:
        if not simplified:
            continue
        existing = index.get(simplified)
        new_hsk = hsk if hsk is not None else UNKNOWN_HSK
        if existing is None or new_hsk < existing:
            index[simplified] = new_hsk
    return index


def _load_eng_sentences(eng_path: str) -> Dict[int, str]:
    """Load English sentences as {id -> text}."""
    out: Dict[int, str] = {}
    with open(eng_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                try:
                    out[int(parts[0])] = parts[2]
                except ValueError:
                    continue
    return out


def _load_links(links_path: str) -> Dict[int, int]:
    """Load cmn->eng translation pairs as {cmn_id -> eng_id}."""
    out: Dict[int, int] = {}
    with open(links_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                try:
                    out[int(parts[0])] = int(parts[1])
                except ValueError:
                    continue
    return out


def seed_sentences_from_tatoeba(cmn_path: str, eng_path: str, links_path: str) -> int:
    """Seed sentences and inverted-index tables from Tatoeba TSV files.

    Returns the number of sentences inserted.
    """
    print(f"Seeding sentences from {cmn_path}...")

    with get_db() as db:
        existing = db.query(Sentence).filter(Sentence.source == "tatoeba").count()
        if existing > 0:
            print(f"✓ Sentences already seeded with {existing} Tatoeba rows")
            return existing

        print("  Loading dictionary index...")
        word_hsk = _load_dictionary_index(db)
        print(f"  Dictionary index: {len(word_hsk):,} entries")

        print("  Loading English sentences...")
        eng = _load_eng_sentences(eng_path)
        print(f"  English sentences: {len(eng):,}")

        print("  Loading translation links...")
        links = _load_links(links_path)
        print(f"  cmn-eng links: {len(links):,}")

        sentence_batch = []
        word_batch_pending = []
        inserted = 0

        with open(cmn_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                try:
                    cmn_id = int(parts[0])
                except ValueError:
                    continue
                hanzi = parts[2]
                if not hanzi:
                    continue

                eng_id = links.get(cmn_id)
                if eng_id is None:
                    continue
                english = eng.get(eng_id)
                if not english:
                    continue

                tokens = [t for t in jieba.cut(hanzi) if t.strip() and t in word_hsk]
                if not tokens:
                    continue

                hsk_score = max((word_hsk[t] for t in tokens), default=UNKNOWN_HSK)
                pinyin = _to_pinyin(hanzi)

                sentence_batch.append({
                    "hanzi": hanzi,
                    "pinyin": pinyin,
                    "english": english,
                    "source": "tatoeba",
                    "hsk_score": hsk_score,
                    "char_length": len(hanzi),
                    "tatoeba_id": cmn_id,
                })
                word_batch_pending.append(set(tokens))

                if len(sentence_batch) >= BATCH_SIZE:
                    inserted += _flush_batch(db, sentence_batch, word_batch_pending)
                    sentence_batch = []
                    word_batch_pending = []
                    print(f"  Inserted {inserted:,} sentences...")

        if sentence_batch:
            inserted += _flush_batch(db, sentence_batch, word_batch_pending)

        print(f"✓ Sentences seeded with {inserted:,} Tatoeba rows")
        return inserted


def _flush_batch(db, sentence_batch, word_batch_pending) -> int:
    """Insert a batch of sentences, then their inverted-index rows."""
    objects = [Sentence(**data) for data in sentence_batch]
    db.add_all(objects)
    db.flush()  # populates IDs without committing

    word_rows = []
    for sentence_obj, tokens in zip(objects, word_batch_pending):
        for tok in tokens:
            word_rows.append({"word": tok, "sentence_id": sentence_obj.id})

    if word_rows:
        db.bulk_insert_mappings(SentenceWord, word_rows)

    db.commit()
    return len(objects)
