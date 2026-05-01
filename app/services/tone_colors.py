"""Tone colour utilities for Anki card HTML generation.

Maps each CJK character to its tone (via its pinyin syllable) and wraps it
in a <span style="color: ..."> tag so Anki renders standard tone colours.

Tone colour convention (user-specified):
    1st tone (flat)        → Red     #FF0000
    2nd tone (rising)      → Green   #00AA00
    3rd tone (dip/rising)  → Blue    #0000FF
    4th tone (falling)     → Purple  #800080
    5th / neutral          → Grey    #888888
"""
import re

TONE_COLORS: dict[int, str] = {
    1: "#FF0000",
    2: "#00AA00",
    3: "#0000FF",
    4: "#800080",
    5: "#888888",
}

# Map diacritic vowel characters → tone number
_DIACRITIC_TONE: dict[str, int] = {}
for _base, _marked in [
    ("a", "āáǎà"),
    ("e", "ēéěè"),
    ("i", "īíǐì"),
    ("o", "ōóǒò"),
    ("u", "ūúǔù"),
    ("ü", "ǖǘǚǜ"),
]:
    for _n, _ch in enumerate(_marked, start=1):
        _DIACRITIC_TONE[_ch] = _n


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or (0x20000 <= cp <= 0x2A6DF)


def _split_syllables(pinyin: str) -> list[str]:
    """Split a pinyin string into individual syllables."""
    return [s for s in re.split(r"[\s,.\[\]()/]+", pinyin.strip()) if s]


def _tone_of(syllable: str) -> int:
    """Return the tone number (1-5) of a single pinyin syllable."""
    # Numeric notation: "ni3" → 3
    for ch in reversed(syllable):
        if ch in "12345":
            return int(ch)
    # Diacritic notation: "nǐ" → 3
    for ch in syllable.lower():
        if ch in _DIACRITIC_TONE:
            return _DIACRITIC_TONE[ch]
    return 5  # neutral / unknown


def colorize(hanzi: str, pinyin: str) -> str:
    """Return HTML where each CJK character is wrapped in a tone-coloured span.

    Non-CJK characters (punctuation, spaces) are passed through uncoloured.

    Example::

        colorize('你好', 'ni3 hao3')
        # → '<span style="color:#0000FF">你</span>
        #    <span style="color:#0000FF">好</span>'
    """
    syllables = _split_syllables(pinyin)
    syl_idx = 0
    parts: list[str] = []

    for ch in hanzi:
        if _is_cjk(ch):
            tone = _tone_of(syllables[syl_idx]) if syl_idx < len(syllables) else 5
            syl_idx += 1
            parts.append(f'<span style="color:{TONE_COLORS[tone]}">{ch}</span>')
        else:
            parts.append(ch)

    return "".join(parts)


def colorize_with_cloze(sentence_hanzi: str, sentence_pinyin: str, target_hanzi: str) -> str:
    """Return tone-coloured HTML for *sentence_hanzi* with ``{{c1::...}}`` around
    the first occurrence of *target_hanzi*.

    Tone colours apply to both the surrounding sentence and the cloze target.

    Example::

        colorize_with_cloze('我喜欢狗', 'wo3 xi3 huan1 gou3', '狗')
        # → '<span style="color:#FF0000">我</span>
        #    <span style="color:#0000FF">喜</span>
        #    <span style="color:#00AA00">欢</span>
        #    {{c1::<span style="color:#FF0000">狗</span>}}'
    """
    syllables = _split_syllables(sentence_pinyin)
    target_len = len(target_hanzi)
    parts: list[str] = []
    syl_idx = 0
    i = 0
    cloze_inserted = False  # only wrap the first occurrence

    while i < len(sentence_hanzi):
        ch = sentence_hanzi[i]

        # Wrap the first occurrence of the target word in a cloze deletion
        if not cloze_inserted and sentence_hanzi[i : i + target_len] == target_hanzi:
            inner: list[str] = []
            for tch in target_hanzi:
                if _is_cjk(tch):
                    tone = _tone_of(syllables[syl_idx]) if syl_idx < len(syllables) else 5
                    syl_idx += 1
                    inner.append(f'<span style="color:{TONE_COLORS[tone]}">{tch}</span>')
                else:
                    inner.append(tch)
            parts.append("{{c1::" + "".join(inner) + "}}")
            cloze_inserted = True
            i += target_len

        elif _is_cjk(ch):
            tone = _tone_of(syllables[syl_idx]) if syl_idx < len(syllables) else 5
            syl_idx += 1
            parts.append(f'<span style="color:{TONE_COLORS[tone]}">{ch}</span>')
            i += 1

        else:
            parts.append(ch)
            i += 1

    # Fallback: target not found in sentence — wrap standalone word as cloze
    if not cloze_inserted and target_hanzi:
        parts = ["{{c1::" + colorize(target_hanzi, "") + "}}"]

    return "".join(parts)
