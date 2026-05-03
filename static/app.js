/**
 * ChAnki v2 - Frontend JavaScript
 */

// State
let currentSettings = null;
let selectedWord = null;
let debounceTimer = null;
let searchAbortController = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    checkStatus();
    setupEventListeners();
    setupVoiceInput();
    setupKeyboard();
    renderRecent();
});

// Register service worker (PWA)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js').catch((err) => {
            console.warn('Service worker registration failed:', err);
        });
    });
}

// Voice input via Web Speech API (Mandarin)
function setupVoiceInput() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const btn = document.getElementById('voiceBtn');
    const input = document.getElementById('searchInput');
    if (!SR || !btn || !input) return;  // Unsupported → keep button hidden

    btn.classList.remove('hidden');

    let recognition = null;
    let listening = false;

    btn.addEventListener('click', () => {
        if (listening && recognition) {
            recognition.stop();
            return;
        }
        recognition = new SR();
        recognition.lang = 'zh-CN';
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => {
            listening = true;
            btn.classList.add('voice-btn--active');
            btn.setAttribute('aria-label', 'Stop voice search');
        };
        recognition.onend = () => {
            listening = false;
            btn.classList.remove('voice-btn--active');
            btn.setAttribute('aria-label', 'Voice search');
        };
        recognition.onerror = () => {
            listening = false;
            btn.classList.remove('voice-btn--active');
        };
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            input.value = transcript;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.focus();
        };

        try {
            recognition.start();
        } catch (e) {
            console.warn('Voice recognition failed to start:', e);
        }
    });
}

// Event Listeners
function setupEventListeners() {
    // Search with debounce + abort-on-new-input
    document.getElementById('searchInput').addEventListener('input', (e) => {
        const query = e.target.value.trim();

        if (!query) {
            hideResults();
            renderRecent();
            document.getElementById('searchingIndicator').style.opacity = '0';
            return;
        }

        // Hide the recent panel as soon as the user starts typing
        const recentWrap = document.getElementById('recentWrap');
        if (recentWrap) recentWrap.classList.add('hidden');

        document.getElementById('searchingIndicator').style.opacity = '1';

        clearTimeout(debounceTimer);
        if (searchAbortController) searchAbortController.abort();

        debounceTimer = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    // Settings modal
    document.getElementById('settingsBtn').addEventListener('click', openSettingsModal);
    document.getElementById('closeSettings').addEventListener('click', closeSettingsModal);
    document.getElementById('cancelSettings').addEventListener('click', closeSettingsModal);
    document.getElementById('settingsForm').addEventListener('submit', saveSettings);

    // Load Decks Button
    document.getElementById('loadDecksBtn').addEventListener('click', loadDecks);

    // Add to Anki (Confirm selection)
    const addBtn = document.getElementById('addToAnkiBtn');
    const newBtn = addBtn.cloneNode(true);
    addBtn.parentNode.replaceChild(newBtn, addBtn);
    newBtn.addEventListener('click', confirmAndAddToAnki);

    // Generate sentences button
    document.getElementById('generateSentencesBtn').addEventListener('click', startGenerating);
}

// Check health status and update UI indicators
async function checkStatus() {
    // Server health (dictionary, gemini)
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        const geminiOk = data.components.gemini?.status === 'healthy';
        updateStatusDot('dictStatus', data.components.database?.status === 'healthy');
        updateStatusDot('geminiStatus', geminiOk);
        updateGeminiSettingsPanel(geminiOk);
    } catch {
        updateStatusDot('dictStatus', false);
        updateStatusDot('geminiStatus', false);
    }

    // Anki: check localhost:8765 directly from the browser
    // (server can't reach the user's local AnkiConnect)
    const ankiOk = await checkAnkiLocal();
    updateStatusDot('ankiStatus', ankiOk);
    updateAnkiPanels(ankiOk);
}

async function checkAnkiLocal() {
    try {
        const res = await fetch('http://localhost:8765', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'version', version: 6 }),
            signal: AbortSignal.timeout(2000),
        });
        const data = await res.json();
        return (data.result ?? 0) >= 6;
    } catch {
        return false;
    }
}

function updateStatusDot(elementId, isConnected) {
    const dot = document.getElementById(elementId);
    if (dot) {
        // Use design-token colors: --success (oklch green) vs --ink-4 (muted)
        dot.style.background = isConnected
            ? 'var(--success)'
            : 'var(--ink-4)';
    }
}

function updateAnkiPanels(isConnected) {
    // Status bar note text
    const note = document.getElementById('ankiStatusNote');
    if (note) note.textContent = isConnected ? 'connected' : 'queued to cloud';

    // Tooltip title
    const tooltipStatus = document.getElementById('ankiTooltipStatus');
    if (tooltipStatus) {
        tooltipStatus.textContent = isConnected ? 'Anki connected' : 'Anki not detected';
        tooltipStatus.style.color = isConnected ? 'var(--success)' : 'var(--fg-2)';
    }

    // Settings panel
    const panel = document.getElementById('ankiSettingsPanel');
    const dot = document.getElementById('ankiSettingsDot');
    const label = document.getElementById('ankiSettingsLabel');
    const guide = document.getElementById('ankiSetupGuide');
    if (panel && dot && label && guide) {
        if (isConnected) {
            panel.className = 'setting-group setting-group--ok';
            dot.style.background = 'var(--success)';
            label.textContent = 'connected';
            label.className = 'setting-group__status setting-group__status--ok';
            guide.classList.add('hidden');
        } else {
            panel.className = 'setting-group setting-group--warn';
            dot.style.background = 'var(--ink-4)';
            label.textContent = 'not detected';
            label.className = 'setting-group__status';
            guide.classList.remove('hidden');
        }
    }
}

function updateGeminiSettingsPanel(isOk) {
    const dot = document.getElementById('geminiSettingsDot');
    const label = document.getElementById('geminiSettingsLabel');
    if (dot) dot.style.background = isOk ? 'var(--success)' : 'var(--ink-4)';
    if (label) {
        label.textContent = isOk ? 'active' : 'not configured';
        label.style.color = isOk ? 'var(--success)' : 'var(--fg-3)';
    }
}

// Anki status tooltip toggle
document.addEventListener('DOMContentLoaded', () => {
    const wrapper = document.getElementById('ankiStatusWrapper');
    const tooltip = document.getElementById('ankiTooltip');
    if (wrapper && tooltip) {
        wrapper.addEventListener('click', () => tooltip.classList.toggle('hidden'));
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) tooltip.classList.add('hidden');
        });
    }
});

async function loadDecks() {
    const btn = document.getElementById('loadDecksBtn');
    const originalText = btn.textContent;
    btn.textContent = 'Loading...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/get-decks', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            const list = document.getElementById('deckList');
            list.innerHTML = '';
            data.decks.forEach(deck => {
                const option = document.createElement('option');
                option.value = deck;
                list.appendChild(option);
            });
            showSuccess(`${data.decks.length} deck${data.decks.length !== 1 ? 's' : ''} loaded.`);
        } else {
            showError('Failed to load decks: ' + data.message);
        }
    } catch (e) {
        showError('Error loading decks: ' + e.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Load application settings
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        currentSettings = settings;

        const set = (id, val) => { const el = document.getElementById(id); if (el && val != null) el.value = val; };
        const check = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };

        // Show placeholder if key is configured, never display the real value
        const keyEl = document.getElementById('geminiKey');
        if (keyEl) keyEl.placeholder = settings.gemini_api_key ? 'API key configured' : 'Enter your Gemini API key';
        set('deckName', settings.anki_deck_name);
        set('modelName', settings.anki_model_name);
        set('hskLevel', settings.hsk_target_level);
        check('toneColors', settings.tone_colors_enabled);
        check('generateAudio', settings.generate_audio);
        check('strictMode', settings.strict_mode);

    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

// Save application settings
async function saveSettings(event) {
    event.preventDefault();

    const get = (id) => { const el = document.getElementById(id); return el ? el.value : null; };
    const getCheck = (id) => { const el = document.getElementById(id); return el ? el.checked : false; };

    const typedKey = get('geminiKey');
    const payload = {
        // Only send the key if the user actually typed a new value
        ...(typedKey ? { gemini_api_key: typedKey } : {}),
        anki_deck_name: get('deckName'),
        anki_model_name: get('modelName'),
        hsk_target_level: parseInt(get('hskLevel')) || 3,
        tone_colors_enabled: getCheck('toneColors'),
        generate_audio: getCheck('generateAudio'),
        strict_mode: getCheck('strictMode'),
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showSuccess('Settings saved.');
            currentSettings = await response.json();
            closeSettingsModal();
        } else {
            showError('Failed to save settings');
        }
    } catch (e) {
        showError('Error saving settings: ' + e.message);
    }
}

async function performSearch(query) {
    hideWordCard();
    hideError();
    hideSuccess();

    searchAbortController = new AbortController();

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {
            signal: searchAbortController.signal
        });
        const data = await response.json();
        displayResults(data.results || [], (data.results || []).length);
    } catch (e) {
        if (e.name !== 'AbortError') showError('Search failed: ' + e.message);
    } finally {
        document.getElementById('searchingIndicator').style.opacity = '0';
    }
}

function displayResults(results, count) {
    const resultsList = document.getElementById('resultsList');
    const resultCount = document.getElementById('resultCount');

    resultsList.innerHTML = '';
    resultCount.textContent = count === 1 ? '1 result' : `${count} results`;

    // Client-side stable sort by HSK ascending (null → 99) as a safety net.
    const sorted = [...results].sort((a, b) => (a.hsk_level ?? 99) - (b.hsk_level ?? 99));

    const T = window.ChAnkiTone;

    sorted.forEach((result, index) => {
        const card = document.createElement('div');

        // First result with an HSK level = the most common / best match
        const isTopMatch = index === 0 && result.hsk_level;
        card.className = isTopMatch ? 'result-card result-card--top' : 'result-card';

        // Tone-colored hanzi and pinyin
        const hanziHtml = T ? T.colorize(result.simplified, result.pinyin) : result.simplified;
        const pinyinHtml = T ? T.colorizePinyin(result.pinyin) : result.pinyin;

        // Badges, right-aligned in the row
        let badgeHtml = '';
        if (result.is_ai_generated) {
            badgeHtml += `<span class="badge badge--ai">AI</span>`;
        }
        // ★ Top match — only on the first result when it carries an HSK level,
        // meaning the ranking confidently identified a common word.
        if (isTopMatch) {
            badgeHtml += `<span class="badge badge--top">★ Top match</span>`;
        }
        // HSK badge: per-level color via .badge--hsk-N (mint→crimson, 1→6)
        if (result.hsk_level) {
            const h = result.hsk_level;
            badgeHtml += `<span class="badge badge--hsk badge--hsk-${h}">HSK ${h}</span>`;
        }

        card.innerHTML = `
            <div class="result-card__hanzi hanzi">${hanziHtml}</div>
            <div class="result-card__body">
                <div class="result-card__row">
                    <div class="result-card__pinyin pinyin">${pinyinHtml}</div>
                    ${badgeHtml ? `<div class="result-card__badges">${badgeHtml}</div>` : ''}
                </div>
                <div class="result-card__def">${result.definitions.slice(0, 2).join('; ')}</div>
            </div>
        `;
        card.onclick = () => selectWord(result);
        resultsList.appendChild(card);
    });

    document.getElementById('resultsContainer').classList.remove('hidden');
}

function selectWord(word) {
    selectedWord = word;
    recordRecent(word);

    const T = window.ChAnkiTone;

    // Tone-colored hanzi and pinyin
    document.getElementById('selectedHanzi').innerHTML =
        T ? T.colorize(word.simplified, word.pinyin) : word.simplified;
    document.getElementById('selectedPinyin').innerHTML =
        T ? T.colorizePinyin(word.pinyin) : word.pinyin;
    document.getElementById('selectedDefinition').textContent =
        word.definitions.join(' · ');

    // HSK + part-of-speech badges
    const badgesEl = document.getElementById('wordBadges');
    if (badgesEl) {
        let b = '';
        if (word.hsk_level) b += `<span class="badge badge--hsk">HSK ${word.hsk_level}</span>`;
        if (word.part_of_speech) b += `<span class="badge badge--default">${word.part_of_speech}</span>`;
        badgesEl.innerHTML = b;
    }

    // TTS button — always available now that audio is rendered server-side
    const ttsBtn = document.getElementById('ttsWordBtn');
    if (ttsBtn) {
        ttsBtn.classList.remove('hidden');
        ttsBtn.onclick = () => speakChinese(word.simplified);
    }

    // Reset generation state
    document.getElementById('generatePrompt').classList.remove('hidden');
    document.getElementById('generationProgress').classList.add('hidden');
    document.getElementById('generatedContent').classList.add('hidden');
    generatedSentences = [];

    // Reset Add to Anki button, then async-check if already queued
    const addBtn = document.getElementById('addToAnkiBtn');
    if (addBtn) {
        addBtn.disabled = false;
        addBtn.textContent = 'Add to Anki →';
    }
    _checkAlreadyQueued(word.simplified);

    // Show seal divider + word card
    document.getElementById('sealDivider').classList.remove('hidden');
    const wordCard = document.getElementById('wordCard');
    wordCard.classList.remove('hidden');
    wordCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/** Silently check whether this hanzi is already queued and update the button. */
async function _checkAlreadyQueued(hanzi) {
    try {
        const resp = await fetch(`/api/sync/check?hanzi=${encodeURIComponent(hanzi)}`);
        if (!resp.ok) return;
        const data = await resp.json();
        if (data.queued) {
            const btn = document.getElementById('addToAnkiBtn');
            if (btn && btn.textContent === 'Add to Anki →') {
                btn.disabled = true;
                btn.textContent = 'Already queued';
            }
        }
    } catch { /* non-fatal */ }
}

async function startGenerating() {
    document.getElementById('generatePrompt').classList.add('hidden');
    document.getElementById('generationProgress').classList.remove('hidden');
    document.getElementById('progressText').textContent = 'Generating 3 sentences with Gemini…';
    await generateSentencesForCard();
}

let generatedSentences = [];
let selectedSentenceIndex = 0;
let _activeEventSource = null;  // close any prior stream when starting a new one

async function generateSentencesForCard() {
    if (!selectedWord) return;

    // Prefer SSE streaming so each sentence appears as soon as Gemini emits it.
    // Fall back to the POST endpoint if EventSource isn't supported.
    if (typeof EventSource !== 'undefined') {
        return generateSentencesViaSSE();
    }
    return generateSentencesViaPost();
}

async function generateSentencesViaSSE() {
    if (_activeEventSource) {
        try { _activeEventSource.close(); } catch {}
    }
    generatedSentences = [];

    const params = new URLSearchParams({
        hanzi: selectedWord.simplified,
        pinyin: selectedWord.pinyin,
        definition: selectedWord.definitions[0],
        hsk_level: String(selectedWord.hsk_level || 3),
    });
    const es = new EventSource(`/api/generate-sentences/stream?${params.toString()}`);
    _activeEventSource = es;

    let gotAny = false;

    es.onmessage = (ev) => {
        // Heartbeats are comment lines (": ping") which EventSource silently
        // discards — only real `data:` events fire onmessage.
        if (!ev.data || ev.data === '{}') return;
        try {
            const sentence = JSON.parse(ev.data);
            generatedSentences.push(sentence);
            renderSentenceOptions();
            // First sentence — swap progress bar for the picker
            if (!gotAny) {
                gotAny = true;
                document.getElementById('generationProgress').classList.add('hidden');
                document.getElementById('generatedContent').classList.remove('hidden');
            }
        } catch (e) {
            console.warn('Bad SSE payload:', ev.data, e);
        }
    };

    es.addEventListener('done', () => {
        es.close();
        _activeEventSource = null;
        if (!gotAny) {
            document.getElementById('progressText').textContent =
                'No sentences found. Add a Gemini key in Settings to enable AI fallback.';
        }
    });

    es.addEventListener('error', (ev) => {
        // Could be either a transport error or our explicit `event: error` from the server
        try {
            const body = ev.data ? JSON.parse(ev.data) : null;
            if (body && body.error) {
                document.getElementById('progressText').textContent = body.error;
            } else if (!gotAny) {
                // Transport-level failure before any data arrived → fall back to POST
                console.warn('SSE failed before first event; falling back to POST');
                es.close();
                _activeEventSource = null;
                generateSentencesViaPost();
                return;
            }
        } catch {}
        try { es.close(); } catch {}
        _activeEventSource = null;
    });
}

async function generateSentencesViaPost() {
    try {
        const response = await fetch('/api/generate-sentences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                hanzi: selectedWord.simplified,
                pinyin: selectedWord.pinyin,
                definition: selectedWord.definitions[0],
                hsk_level: selectedWord.hsk_level || 3
            })
        });

        const data = await response.json();

        if (data.success && data.sentences) {
            generatedSentences = data.sentences;
            renderSentenceOptions();

            document.getElementById('generationProgress').classList.add('hidden');
            document.getElementById('generatedContent').classList.remove('hidden');
        } else {
            // Show error in the card
            document.getElementById('progressText').textContent = data.message || "Failed to generate.";
        }

    } catch (error) {
        document.getElementById('progressText').textContent = 'Error: ' + error.message;
    }
}

function renderSentenceOptions() {
    const list = document.getElementById('sentenceOptionsList');
    list.innerHTML = '';

    const T = window.ChAnkiTone;

    generatedSentences.forEach((sentence, index) => {
        const div = document.createElement('div');

        if (sentence.error) {
            div.style.cssText = 'padding:12px;color:var(--error);font-size:14px;';
            div.textContent = sentence.error;
            list.appendChild(div);
            return;
        }

        const isSelected = index === 0;
        if (isSelected) selectedSentenceIndex = 0;

        const hanziText = sentence.hanzi || sentence.sentence_simplified || '';
        const pinyinText = sentence.pinyin || '';
        const englishText = sentence.english || sentence.sentence_english || '';
        const hintText = sentence.hint || '';

        const hanziHtml = T ? T.colorize(hanziText, pinyinText) : hanziText;
        const pinyinHtml = T ? T.colorizePinyin(pinyinText) : pinyinText;

        div.className = `sentence-option${isSelected ? ' sentence-option--selected' : ''}`;
        div.innerHTML = `
            <div class="sentence-radio">
                <div class="sentence-radio__dot"></div>
            </div>
            <div class="sentence-body">
                <div class="sentence-hanzi hanzi">
                    <span>${hanziHtml}</span>
                    <button class="tts-sentence-btn tts-btn" aria-label="Listen" title="Listen">
                        <i data-lucide="volume-2"></i>
                    </button>
                </div>
                ${pinyinHtml ? `<div class="sentence-pinyin pinyin">${pinyinHtml}</div>` : ''}
                <div class="sentence-english">${englishText}</div>
                ${hintText ? `<div class="sentence-hint">${hintText}</div>` : ''}
            </div>
        `;

        // TTS — stop propagation so it doesn't toggle sentence selection
        const ttsBtn = div.querySelector('.tts-sentence-btn');
        if (ttsBtn) {
            ttsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                speakChinese(hanziText);
            });
        }

        div.onclick = (e) => {
            if (e.target.closest('.tts-sentence-btn')) return;
            // Update selection state
            Array.from(list.children).forEach(c => c.classList.remove('sentence-option--selected'));
            div.classList.add('sentence-option--selected');
            selectedSentenceIndex = index;
        };

        list.appendChild(div);
    });

    // Re-run Lucide icon init for the dynamically-created volume icons
    if (window.lucide) lucide.createIcons({ strokeWidth: 1.5 });
}
function closeSentenceModal() { /* Deprecated */ }
function startSentenceSelection() { /* Deprecated in v2 */ }

async function confirmAndAddToAnki() {
    const sentence = (generatedSentences && generatedSentences[selectedSentenceIndex]) || {};
    await addToAnkiDirect(sentence);
}

async function addToAnkiDirect(sentence) {
    const btn = document.getElementById('addToAnkiBtn');
    btn.disabled = true;
    btn.textContent = 'Queuing…';

    // Show progress bar while queuing
    document.getElementById('generatedContent').classList.add('hidden');
    document.getElementById('generationProgress').classList.remove('hidden');
    document.getElementById('progressText').textContent = 'Queuing cards…';

    try {
        const response = await fetch('/api/sync/queue', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                hanzi: selectedWord.simplified,
                pinyin: selectedWord.pinyin,
                definition: selectedWord.definitions[0],
                sentence_hanzi: sentence.hanzi || null,
                sentence_pinyin: sentence.pinyin || null,
                sentence_english: sentence.english || null,
                hint: sentence.hint || null,
                hsk_level: selectedWord.hsk_level || null,
                part_of_speech: selectedWord.part_of_speech || null,
            })
        });

        const data = await response.json();

        if (data.already_queued) {
            showSuccess(`'${selectedWord.simplified}' is already in your queue.`);
            btn.textContent = 'Already queued';
            btn.disabled = true;
            document.getElementById('generatedContent').classList.remove('hidden');
        } else if (data.queued) {
            const n = data.cards_created || 1;
            showSuccess(`${n} card${n !== 1 ? 's' : ''} queued. Will sync to Anki when it is open.`);
            btn.textContent = `${n} card${n !== 1 ? 's' : ''} queued`;
            btn.disabled = true;
            document.getElementById('generatedContent').classList.remove('hidden');
        } else {
            showError(data.message || 'Failed to queue card.');
            btn.disabled = false;
            btn.textContent = 'Add to Anki →';
            document.getElementById('generatedContent').classList.remove('hidden');
        }

        document.getElementById('generationProgress').classList.add('hidden');

    } catch (error) {
        showError('Failed to queue card: ' + error.message);
        btn.disabled = false;
        btn.textContent = 'Add to Anki →';
        document.getElementById('generatedContent').classList.remove('hidden');
        document.getElementById('generationProgress').classList.add('hidden');
    }
}


// UI Helper Functions
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.querySelector('p').textContent = message;
    errorDiv.classList.remove('hidden');
    setTimeout(() => errorDiv.classList.add('hidden'), 5000);
}

function showSuccess(message) {
    const successDiv = document.getElementById('successMessage');
    successDiv.querySelector('p').textContent = message;
    successDiv.classList.remove('hidden');
    setTimeout(() => successDiv.classList.add('hidden'), 5000);
}

function hideError() {
    document.getElementById('errorMessage').classList.add('hidden');
}

function hideSuccess() {
    document.getElementById('successMessage').classList.add('hidden');
}

function hideResults() {
    document.getElementById('resultsContainer').classList.add('hidden');
}

function hideWordCard() {
    document.getElementById('wordCard').classList.add('hidden');
    document.getElementById('generatedContent').classList.add('hidden');
    document.getElementById('sealDivider').classList.add('hidden');
}

function openSettingsModal() {
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
    checkStatus();
}

// ---------------------------------------------------------------------------
// Text-to-Speech via /api/tts (server-rendered with edge-tts)
//
// The browser's SpeechSynthesis API produces robotic Mandarin on most
// desktops and refuses zh-CN entirely on iOS Safari. We render audio
// server-side with edge-tts (Xiaoxiao neural voice) instead — same
// quality as Microsoft Edge's read-aloud feature.
//
// Browser caches the audio by URL, so repeat plays are instant.
// ---------------------------------------------------------------------------
let _ttsAudio = null;  // single shared <Audio> so a new play stops the prior one

async function speakChinese(text) {
    if (!text) return;
    try {
        // Stop anything already playing
        if (_ttsAudio) {
            _ttsAudio.pause();
            _ttsAudio.currentTime = 0;
        }
        _ttsAudio = new Audio(`/api/tts?text=${encodeURIComponent(text)}`);
        _ttsAudio.preload = 'auto';
        await _ttsAudio.play();
    } catch (err) {
        // Most likely cause: autoplay policy on iOS — must be triggered by
        // a user gesture, which our 🔊 click is. Fall back to SpeechSynthesis
        // if it's available; otherwise the click silently no-ops.
        console.warn('TTS playback failed:', err);
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'zh-CN';
            u.rate = 0.9;
            window.speechSynthesis.speak(u);
        }
    }
}

// Test Gemini API Key
async function testGeminiKey() {
    const keyInput = document.getElementById('geminiKey');
    const testBtn = document.getElementById('testGeminiBtn');
    const statusDiv = document.getElementById('geminiTestStatus');

    const apiKey = keyInput.value.trim();

    if (!apiKey) {
        statusDiv.className = 'api-test-msg api-test-msg--warn';
        statusDiv.textContent = 'Please enter an API key first';
        statusDiv.classList.remove('hidden');
        return;
    }

    // Update UI - testing state
    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';
    statusDiv.className = 'api-test-msg api-test-msg--info';
    statusDiv.textContent = 'Connecting to Gemini API...';
    statusDiv.classList.remove('hidden');

    try {
        const response = await fetch('/api/settings/test-gemini', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey })
        });

        const result = await response.json();

        if (result.success) {
            statusDiv.className = 'api-test-msg api-test-msg--ok';
            statusDiv.textContent = '✅ ' + result.message;
            updateStatusDot('geminiStatus', true);
        } else {
            statusDiv.className = 'api-test-msg api-test-msg--err';
            statusDiv.textContent = '❌ ' + result.message;
            updateStatusDot('geminiStatus', false);
        }
    } catch (error) {
        statusDiv.className = 'api-test-msg api-test-msg--err';
        statusDiv.textContent = '❌ Connection test failed: ' + error.message;
    } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Test';

        // Hide status after 10 seconds
        setTimeout(() => {
            statusDiv.classList.add('hidden');
        }, 10000);
    }
}

// ---------------------------------------------------------------------------
// Recent searches (localStorage, max 10, deduped by simplified hanzi)
// ---------------------------------------------------------------------------
const RECENT_KEY = 'chanki:recent';
const RECENT_MAX = 10;

function _readRecent() {
    try {
        const raw = localStorage.getItem(RECENT_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch { return []; }
}

function _writeRecent(items) {
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(items)); } catch {}
}

/** Save a word to the recent list when the user actually picks it. */
function recordRecent(word) {
    if (!word || !word.simplified) return;
    const entry = {
        simplified: word.simplified,
        pinyin: word.pinyin,
        hsk_level: word.hsk_level || null,
        definition: (word.definitions && word.definitions[0]) || '',
        ts: Date.now(),
    };
    const all = _readRecent().filter(e => e.simplified !== entry.simplified);
    all.unshift(entry);
    _writeRecent(all.slice(0, RECENT_MAX));
}

/** Render the recent list above search results, only when the input is empty. */
function renderRecent() {
    const wrap = document.getElementById('recentWrap');
    if (!wrap) return;
    const input = document.getElementById('searchInput');
    if (input && input.value.trim() !== '') {
        wrap.classList.add('hidden');
        return;
    }
    const items = _readRecent();
    if (items.length === 0) {
        wrap.classList.add('hidden');
        return;
    }
    const T = window.ChAnkiTone;
    const list = document.getElementById('recentList');
    list.innerHTML = '';
    items.forEach(it => {
        const card = document.createElement('div');
        card.className = 'recent-item';
        const hanziHtml = T ? T.colorize(it.simplified, it.pinyin) : it.simplified;
        const pinyinHtml = T ? T.colorizePinyin(it.pinyin) : it.pinyin;
        const hskBadge = it.hsk_level
            ? `<span class="badge badge--hsk badge--hsk-${it.hsk_level}">HSK ${it.hsk_level}</span>`
            : '';
        card.innerHTML = `
            <div class="recent-item__hanzi hanzi">${hanziHtml}</div>
            <div class="recent-item__body">
                <div class="recent-item__pinyin pinyin">${pinyinHtml}</div>
                <div class="recent-item__def">${it.definition}</div>
            </div>
            ${hskBadge}
        `;
        card.onclick = () => {
            // Re-trigger the search with this hanzi so the user can pick it again
            input.value = it.simplified;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        };
        list.appendChild(card);
    });
    wrap.classList.remove('hidden');
}

// ---------------------------------------------------------------------------
// Keyboard shortcuts: / focus search, Esc close/blur, ↑↓ navigate, Enter pick
// ---------------------------------------------------------------------------
let _focusedResultIdx = -1;

function setupKeyboard() {
    document.addEventListener('keydown', (e) => {
        const target = e.target;
        const inField = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT');
        const modal = document.getElementById('settingsModal');
        const modalOpen = modal && modal.classList.contains('active');

        // Esc — close modal first, otherwise blur active input
        if (e.key === 'Escape') {
            if (modalOpen) {
                closeSettingsModal();
                e.preventDefault();
                return;
            }
            if (inField) target.blur();
            return;
        }

        // / — focus the search input (only when not already in a field)
        if (e.key === '/' && !inField && !modalOpen) {
            e.preventDefault();
            document.getElementById('searchInput').focus();
            document.getElementById('searchInput').select();
            return;
        }

        // ↑ ↓ — navigate result cards (work both in and out of search input)
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !modalOpen) {
            const cards = Array.from(document.querySelectorAll('#resultsList .result-card'));
            if (cards.length === 0) return;
            e.preventDefault();
            cards.forEach(c => c.classList.remove('result-card--focused'));
            if (_focusedResultIdx < 0) {
                _focusedResultIdx = e.key === 'ArrowDown' ? 0 : cards.length - 1;
            } else {
                _focusedResultIdx += e.key === 'ArrowDown' ? 1 : -1;
                if (_focusedResultIdx < 0) _focusedResultIdx = cards.length - 1;
                if (_focusedResultIdx >= cards.length) _focusedResultIdx = 0;
            }
            const c = cards[_focusedResultIdx];
            c.classList.add('result-card--focused');
            c.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            return;
        }

        // Enter — when in search input with results visible, pick focused (or first)
        if (e.key === 'Enter' && target && target.id === 'searchInput' && !modalOpen) {
            const cards = document.querySelectorAll('#resultsList .result-card');
            if (cards.length === 0) return;
            const idx = _focusedResultIdx >= 0 ? _focusedResultIdx : 0;
            cards[idx].click();
            e.preventDefault();
            return;
        }
    });

    // Reset focus on each new search
    const input = document.getElementById('searchInput');
    if (input) input.addEventListener('input', () => { _focusedResultIdx = -1; });
}
