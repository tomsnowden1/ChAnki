#!/usr/bin/env python3
"""
ChAnki Local Sync Agent - "The Courier"

Polls the cloud ChAnki instance for pending cards and syncs them to local Anki.
Runs as a background service on your home computer.

Card types handled:
    en_to_zh    — Basic: English definition (front) → tone-coloured hanzi (back)
    zh_to_en    — Basic: tone-coloured hanzi (front) → pinyin + definition (back)
    en_sentence — Basic: English sentence (front) → tone-coloured Chinese sentence (back)
    zh_sentence — Cloze: Chinese sentence with {{c1::target}} (tone-coloured throughout)
    None/legacy — Old-style cloze (backward compat for cards queued before this update)
"""

import json
import re
import time
import requests
from datetime import datetime
from pathlib import Path
import sys


# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def log(message: str, color: str = Colors.RESET):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{color}[{timestamp}] {message}{Colors.RESET}", flush=True)


# ---------------------------------------------------------------------------
# Tone-colour helpers (self-contained so the agent has no app/ dependency)
# ---------------------------------------------------------------------------
_TONE_COLORS = {
    1: '#FF0000',  # Red    — 1st tone (flat)
    2: '#00AA00',  # Green  — 2nd tone (rising)
    3: '#0000FF',  # Blue   — 3rd tone (dip)
    4: '#800080',  # Purple — 4th tone (falling)
    5: '#888888',  # Grey   — neutral / unknown
}

_DIACRITIC_TONE: dict = {}
for _base, _tones in [
    ('a', 'āáǎà'), ('e', 'ēéěè'), ('i', 'īíǐì'),
    ('o', 'ōóǒò'), ('u', 'ūúǔù'), ('ü', 'ǖǘǚǜ'),
]:
    for _n, _c in enumerate(_tones, start=1):
        _DIACRITIC_TONE[_c] = _n


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF)


def _tone_of(syllable: str) -> int:
    for ch in reversed(syllable):
        if ch in '12345':
            return int(ch)
    for ch in syllable.lower():
        if ch in _DIACRITIC_TONE:
            return _DIACRITIC_TONE[ch]
    return 5


def _split_syllables(pinyin: str) -> list:
    return [s for s in re.split(r'[\s,.\[\]()/]+', pinyin.strip()) if s]


def _colorize(hanzi: str, pinyin: str) -> str:
    """Wrap each CJK character in a tone-coloured <span>."""
    syllables = _split_syllables(pinyin)
    syl_idx = 0
    parts = []
    for ch in hanzi:
        if _is_cjk(ch):
            tone = _tone_of(syllables[syl_idx]) if syl_idx < len(syllables) else 5
            syl_idx += 1
            color = _TONE_COLORS.get(tone, '#888888')
            parts.append(f'<span style="color:{color}">{ch}</span>')
        else:
            parts.append(ch)
    return ''.join(parts)


def _colorize_with_cloze(sentence_hanzi: str, sentence_pinyin: str, target_hanzi: str) -> str:
    """Tone-coloured sentence HTML with {{c1::...}} around the target word."""
    syllables = _split_syllables(sentence_pinyin)
    target_len = len(target_hanzi)
    parts = []
    syl_idx = 0
    i = 0
    cloze_done = False

    while i < len(sentence_hanzi):
        ch = sentence_hanzi[i]
        if not cloze_done and sentence_hanzi[i:i + target_len] == target_hanzi:
            inner = []
            for tch in target_hanzi:
                if _is_cjk(tch):
                    tone = _tone_of(syllables[syl_idx]) if syl_idx < len(syllables) else 5
                    syl_idx += 1
                    inner.append(f'<span style="color:{_TONE_COLORS.get(tone, "#888888")}">{tch}</span>')
                else:
                    inner.append(tch)
            parts.append('{{c1::' + ''.join(inner) + '}}')
            cloze_done = True
            i += target_len
        elif _is_cjk(ch):
            tone = _tone_of(syllables[syl_idx]) if syl_idx < len(syllables) else 5
            syl_idx += 1
            parts.append(f'<span style="color:{_TONE_COLORS.get(tone, "#888888")}">{ch}</span>')
            i += 1
        else:
            parts.append(ch)
            i += 1

    if not cloze_done and target_hanzi:
        # target word not found in sentence — use it standalone
        return '{{c1::' + _colorize(target_hanzi, '') + '}}'

    return ''.join(parts)


def _hanzi_div(colored_html: str, large: bool = True) -> str:
    """Wrap tone-coloured hanzi in a styled div for Anki display."""
    size = '2em' if large else '1.3em'
    return (
        f'<div style="font-size:{size};font-family:\'Noto Sans SC\','
        f'\'PingFang SC\',sans-serif;line-height:1.4">{colored_html}</div>'
    )


def _pinyin_div(pinyin: str) -> str:
    return f'<div style="color:#7c3aed;font-size:1.1em;margin-top:4px">{pinyin}</div>'


# ---------------------------------------------------------------------------
# Sync Agent
# ---------------------------------------------------------------------------
class SyncAgent:
    """Synchronization agent for cloud-to-local Anki card sync"""

    def __init__(self, config_path: str = "sync_agent_config.json"):
        self.config = self.load_config(config_path)
        self.cloud_url = self.config["cloud_url"].rstrip("/")
        self.sync_secret = self.config["sync_secret"]
        self.anki_url = self.config["anki_url"]
        self.poll_interval = self.config.get("poll_interval", 30)
        self.deck_name = self.config.get("deck_name", "Chinese::Mining")

        log(f"🚀 Sync Agent initialized", Colors.BLUE)
        log(f"   Cloud: {self.cloud_url}", Colors.BLUE)
        log(f"   Anki: {self.anki_url}", Colors.BLUE)
        log(f"   Poll interval: {self.poll_interval}s", Colors.BLUE)

    def load_config(self, config_path: str) -> dict:
        if not Path(config_path).exists():
            log(f"❌ Config file not found: {config_path}", Colors.RED)
            log(f"   Creating template config...", Colors.YELLOW)
            self.create_template_config(config_path)
            log(f"\n   Please edit {config_path} with your settings and restart.", Colors.YELLOW)
            sys.exit(1)
        with open(config_path, 'r') as f:
            return json.load(f)

    def create_template_config(self, config_path: str):
        template = {
            "cloud_url": "https://chanki.onrender.com",
            "sync_secret": "YOUR_SYNC_SECRET_HERE",
            "anki_url": "http://localhost:8765",
            "poll_interval": 30,
            "deck_name": "Chinese::Mining"
        }
        with open(config_path, 'w') as f:
            json.dump(template, f, indent=2)

    def check_anki_connection(self) -> bool:
        try:
            response = requests.post(
                self.anki_url,
                json={"action": "version", "version": 6},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def fetch_pending_cards(self) -> list:
        try:
            response = requests.get(
                f"{self.cloud_url}/api/sync/pending",
                headers={"X-Sync-Secret": self.sync_secret},
                timeout=10
            )
            if response.status_code == 401:
                log("❌ Authentication failed - check SYNC_SECRET", Colors.RED)
                return []
            if response.status_code != 200:
                log(f"⚠️  Cloud returned status {response.status_code}", Colors.YELLOW)
                return []
            return response.json().get("cards", [])
        except requests.exceptions.Timeout:
            log("⏱️  Cloud request timed out", Colors.YELLOW)
            return []
        except requests.exceptions.ConnectionError:
            log("🔌 Cannot reach cloud server", Colors.YELLOW)
            return []
        except Exception as e:
            log(f"⚠️  Error fetching cards: {e}", Colors.YELLOW)
            return []

    def ensure_deck_exists(self):
        """Create the deck if it doesn't exist yet (createDeck is idempotent)."""
        try:
            requests.post(
                self.anki_url,
                json={"action": "createDeck", "version": 6, "params": {"deck": self.deck_name}},
                timeout=5
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Note building — one method per card type
    # ------------------------------------------------------------------

    def _build_note(self, card: dict) -> dict | None:
        """
        Build an AnkiConnect note payload from a card dict.
        Returns None if the card should be silently skipped
        (e.g. a sentence card with no sentence data).
        """
        card_type = card.get("card_type") or "legacy"
        hanzi = card.get("hanzi", "")
        pinyin = card.get("pinyin", "")
        definition = card.get("definition", "")
        hint = card.get("hint", "")
        sentence_hanzi = card.get("sentence_hanzi", "") or ""
        sentence_pinyin = card.get("sentence_pinyin", "") or ""
        sentence_english = card.get("sentence_english", "") or ""
        hsk_tag = f"hsk{card.get('hsk_level', 0)}"
        base_tags = ["chanki", hsk_tag]

        colored_hanzi = _colorize(hanzi, pinyin) if pinyin else hanzi

        # ── EN → ZH ──────────────────────────────────────────────────
        if card_type == "en_to_zh":
            front = f"<div>{definition}</div>"
            if hint:
                front += (
                    f'<div style="color:#888;font-size:0.85em;margin-top:8px">'
                    f'💡 {hint}</div>'
                )
            back = _hanzi_div(colored_hanzi) + _pinyin_div(pinyin)
            return {
                "deckName": self.deck_name,
                "modelName": "Basic",
                "fields": {"Front": front, "Back": back},
                "tags": base_tags,
            }

        # ── ZH → EN ──────────────────────────────────────────────────
        if card_type == "zh_to_en":
            front = _hanzi_div(colored_hanzi)
            back = _pinyin_div(pinyin) + f'<div style="margin-top:6px">{definition}</div>'
            return {
                "deckName": self.deck_name,
                "modelName": "Basic",
                "fields": {"Front": front, "Back": back},
                "tags": base_tags,
            }

        # ── EN Sentence → ZH Sentence ────────────────────────────────
        if card_type == "en_sentence":
            if not sentence_english or not sentence_hanzi:
                return None
            colored_sentence = (
                _colorize(sentence_hanzi, sentence_pinyin)
                if sentence_pinyin else sentence_hanzi
            )
            front = f"<div>{sentence_english}</div>"
            back = (
                _hanzi_div(colored_sentence, large=False)
                + (f'<div style="color:#7c3aed;font-size:0.9em;margin-top:4px">'
                   f'{sentence_pinyin}</div>' if sentence_pinyin else "")
            )
            return {
                "deckName": self.deck_name,
                "modelName": "Basic",
                "fields": {"Front": front, "Back": back},
                "tags": base_tags + ["sentence"],
            }

        # ── ZH Sentence (Cloze) ──────────────────────────────────────
        if card_type == "zh_sentence":
            if not sentence_hanzi:
                return None
            if sentence_pinyin and hanzi:
                text = _colorize_with_cloze(sentence_hanzi, sentence_pinyin, hanzi)
            elif hanzi and hanzi in sentence_hanzi:
                text = sentence_hanzi.replace(
                    hanzi, f"{{{{c1::{_colorize(hanzi, pinyin) if pinyin else hanzi}}}}}", 1
                )
            else:
                text = f"{{{{c1::{_colorize(hanzi, pinyin) if pinyin else hanzi}}}}}"
            back_extra = sentence_english
            if sentence_pinyin:
                back_extra += (
                    f'<br><span style="color:#7c3aed;font-size:0.9em">{sentence_pinyin}</span>'
                )
            return {
                "deckName": self.deck_name,
                "modelName": "Cloze",
                "fields": {"Text": text, "Back Extra": back_extra},
                "tags": base_tags + ["sentence"],
            }

        # ── Legacy / fallback (old-style cloze) ─────────────────────
        sentence = sentence_hanzi
        if sentence and hanzi in sentence:
            sentence = sentence.replace(hanzi, f"{{{{c1::{hanzi}}}}}", 1)
        else:
            sentence = f"{{{{c1::{hanzi}}}}}"
        return {
            "deckName": self.deck_name,
            "modelName": "Cloze",
            "fields": {
                "Text": sentence,
                "Back Extra": (
                    f"{pinyin}<br>{definition}"
                    + (f"<br><br>{sentence_pinyin}<br>{sentence_english}"
                       if sentence_english else "")
                ),
            },
            "tags": ["chanki-synced", hsk_tag],
        }

    def add_card_to_anki(self, card: dict) -> bool:
        """Add a single card to Anki via AnkiConnect."""
        self.ensure_deck_exists()
        note = self._build_note(card)

        if note is None:
            # Intentionally skipped (e.g. sentence card with no sentence data)
            log(f"   ⏭  Skipped {card.get('card_type')} — no sentence data", Colors.YELLOW)
            return True  # not a failure; acknowledge so it clears the queue

        try:
            payload = {"action": "addNote", "version": 6, "params": {"note": note}}
            response = requests.post(self.anki_url, json=payload, timeout=10)
            result = response.json()

            if result.get("error"):
                log(f"   ⚠️  Anki error: {result['error']}", Colors.YELLOW)
                return False

            return bool(result.get("result"))

        except Exception as e:
            log(f"   ❌ Error adding card: {e}", Colors.RED)
            return False

    def acknowledge_synced_cards(self, card_ids: list) -> bool:
        if not card_ids:
            return True
        try:
            response = requests.post(
                f"{self.cloud_url}/api/sync/ack",
                headers={"X-Sync-Secret": self.sync_secret, "Content-Type": "application/json"},
                json={"ids": card_ids},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            log(f"⚠️  Failed to acknowledge: {e}", Colors.YELLOW)
            return False

    def sync_once(self):
        """Perform one sync cycle."""
        if not self.check_anki_connection():
            log("❌ Anki is not running or AnkiConnect is not installed", Colors.RED)
            return

        cards = self.fetch_pending_cards()
        if not cards:
            log("✓ No pending cards", Colors.GREEN)
            return

        log(f"📥 Found {len(cards)} pending card(s)", Colors.BLUE)

        synced_ids = []
        for card in cards:
            hanzi = card.get("hanzi", "?")
            card_type = card.get("card_type") or "legacy"
            log(f"   Syncing: {hanzi} [{card_type}]...", Colors.BLUE)

            if self.add_card_to_anki(card):
                log(f"   ✓ Synced: {hanzi} [{card_type}]", Colors.GREEN)
                synced_ids.append(card["id"])
            else:
                log(f"   ✗ Failed: {hanzi} [{card_type}]", Colors.RED)

        if synced_ids:
            if self.acknowledge_synced_cards(synced_ids):
                log(f"✅ Acknowledged {len(synced_ids)} card(s) to cloud", Colors.GREEN)
            else:
                log(f"⚠️  Could not acknowledge cards to cloud", Colors.YELLOW)

    def run_forever(self):
        """Main polling loop."""
        log(f"\n{'='*60}", Colors.BLUE)
        log(f"🔄 Starting sync loop (every {self.poll_interval}s)", Colors.BLUE)
        log(f"   Press Ctrl+C to stop", Colors.BLUE)
        log(f"{'='*60}\n", Colors.BLUE)

        while True:
            try:
                self.sync_once()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                log("\n\n👋 Sync agent stopped", Colors.YELLOW)
                break
            except Exception as e:
                log(f"💥 Unexpected error: {e}", Colors.RED)
                time.sleep(self.poll_interval)


def main():
    agent = SyncAgent()
    agent.run_forever()


if __name__ == "__main__":
    main()
