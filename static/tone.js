/**
 * ChAnki — client-side tone coloring
 * Mirrors app/services/tone_colors.py
 *
 * Uses CSS classes .tone-1 … .tone-5 (softened OKLCH values from chanki.css)
 * for web UI display. Anki card output still uses canonical sRGB hex via the
 * Python colorize() function on the server.
 */
(function () {
  // Map diacritic vowels → tone number
  const DIACRITIC = {};
  [
    ['a', 'āáǎà'], ['e', 'ēéěè'], ['i', 'īíǐì'],
    ['o', 'ōóǒò'], ['u', 'ūúǔù'], ['ü', 'ǖǘǚǜ'],
  ].forEach(([, marks]) =>
    [...marks].forEach((ch, i) => { DIACRITIC[ch] = i + 1; })
  );

  function isCJK(ch) {
    const cp = ch.codePointAt(0);
    return (
      (cp >= 0x4e00 && cp <= 0x9fff) ||
      (cp >= 0x3400 && cp <= 0x4dbf) ||
      (cp >= 0x20000 && cp <= 0x2a6df)
    );
  }

  function splitSyllables(pinyin) {
    return (pinyin || '').trim().split(/[\s,.\[\]()/]+/).filter(Boolean);
  }

  function toneOf(syl) {
    // Numeric notation: "ni3" → 3
    for (let i = syl.length - 1; i >= 0; i--) {
      if ('12345'.includes(syl[i])) return parseInt(syl[i], 10);
    }
    // Diacritic notation: "nǐ" → 3
    for (const ch of syl.toLowerCase()) {
      if (DIACRITIC[ch]) return DIACRITIC[ch];
    }
    return 5; // neutral / unknown
  }

  /**
   * Wrap each CJK character in a <span class="tone-N"> for UI display.
   * Non-CJK characters (spaces, punctuation) pass through unchanged.
   */
  function colorize(hanzi, pinyin) {
    const syllables = splitSyllables(pinyin);
    let si = 0;
    return [...(hanzi || '')].map(ch => {
      if (isCJK(ch)) {
        const tone = si < syllables.length ? toneOf(syllables[si++]) : 5;
        return `<span class="tone-${tone}">${ch}</span>`;
      }
      return ch;
    }).join('');
  }

  /**
   * Wrap each pinyin syllable in a <span class="tone-N">.
   */
  function colorizePinyin(pinyin) {
    return splitSyllables(pinyin || '')
      .map(syl => `<span class="tone-${toneOf(syl)}">${syl}</span>`)
      .join(' ');
  }

  window.ChAnkiTone = { colorize, colorizePinyin, toneOf, splitSyllables };
})();
