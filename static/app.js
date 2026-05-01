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
            btn.textContent = '🔴';
            btn.setAttribute('aria-label', 'Stop voice search');
        };
        recognition.onend = () => {
            listening = false;
            btn.textContent = '🎤';
            btn.setAttribute('aria-label', 'Voice search');
        };
        recognition.onerror = () => {
            listening = false;
            btn.textContent = '🎤';
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
            document.getElementById('searchingIndicator').style.opacity = '0';
            return;
        }

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
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        const ankiOk = data.components.anki?.status === 'healthy';
        const geminiOk = data.components.gemini?.status === 'healthy';
        updateStatusDot('dictStatus', data.components.database?.status === 'healthy');
        updateStatusDot('geminiStatus', geminiOk);
        updateStatusDot('ankiStatus', ankiOk);
        updateAnkiPanels(ankiOk);
        updateGeminiSettingsPanel(geminiOk);

    } catch (error) {
        console.error('Health check failed:', error);
        updateStatusDot('dictStatus', false);
        updateStatusDot('geminiStatus', false);
        updateStatusDot('ankiStatus', false);
        updateAnkiPanels(false);
    }
}

function updateStatusDot(elementId, isConnected) {
    const dot = document.getElementById(elementId);
    if (dot) {
        dot.style.backgroundColor = isConnected ? '#22c55e' : '#9ca3af';
    }
}

function updateAnkiPanels(isConnected) {
    // Status bar tooltip
    const tooltipStatus = document.getElementById('ankiTooltipStatus');
    if (tooltipStatus) {
        tooltipStatus.textContent = isConnected ? '✅ Anki connected' : '⚪ Anki not detected';
        tooltipStatus.className = isConnected
            ? 'font-semibold text-sm mb-2 text-green-600'
            : 'font-semibold text-sm mb-2 text-gray-500';
    }

    // Settings panel
    const panel = document.getElementById('ankiSettingsPanel');
    const dot = document.getElementById('ankiSettingsDot');
    const label = document.getElementById('ankiSettingsLabel');
    const guide = document.getElementById('ankiSetupGuide');
    if (panel && dot && label && guide) {
        if (isConnected) {
            panel.className = 'rounded-xl border-2 border-green-200 bg-green-50 p-4';
            dot.style.backgroundColor = '#22c55e';
            label.textContent = 'connected';
            label.className = 'text-sm text-green-600';
            guide.classList.add('hidden');
        } else {
            panel.className = 'rounded-xl border-2 border-amber-200 bg-amber-50 p-4';
            dot.style.backgroundColor = '#9ca3af';
            label.textContent = 'not detected';
            label.className = 'text-sm text-gray-500';
            guide.classList.remove('hidden');
        }
    }
}

function updateGeminiSettingsPanel(isOk) {
    const dot = document.getElementById('geminiSettingsDot');
    const label = document.getElementById('geminiSettingsLabel');
    if (dot) dot.style.backgroundColor = isOk ? '#22c55e' : '#9ca3af';
    if (label) {
        label.textContent = isOk ? 'active' : 'not configured';
        label.className = isOk ? 'ml-2 text-sm text-green-600' : 'ml-2 text-sm text-gray-500';
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
            showSuccess(`Loaded ${data.decks.length} decks`);
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
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showSuccess('Settings saved successfully!');
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
    resultCount.textContent = `(${count} found)`;

    results.forEach(result => {
        const card = document.createElement('div');
        card.className = 'bg-white p-5 rounded-xl shadow hover:shadow-lg cursor-pointer transition-all border-2 border-transparent hover:border-purple-300';

        // Badges
        let badgeHtml = '';

        // AI Badge
        if (result.is_ai_generated) {
            badgeHtml += `<span class="ml-2 px-3 py-1 bg-gradient-to-r from-purple-500 to-indigo-600 text-white text-xs font-semibold rounded-full shadow">🤖 AI</span>`;
        }

        // Frequency/Common Badge
        // HSK 1-3 = Common (Orange)
        // HSK 4-6 = Advanced (Blue - let's add this for better distinction)
        // No HSK = Gray
        if (result.hsk_level && result.hsk_level <= 3) {
            badgeHtml += `<span class="ml-2 px-3 py-1 bg-orange-100 text-orange-700 text-xs font-bold rounded-full border border-orange-200">🔥 Common</span>`;
        } else if (result.hsk_level && result.hsk_level <= 6) {
            badgeHtml += `<span class="ml-2 px-3 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded-full border border-blue-200">HSK ${result.hsk_level}</span>`;
        }
        // No badge for unlabelled words — most CC-CEDICT entries lack HSK metadata

        card.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <div class="flex items-center">
                        <span class="text-4xl hanzi-text font-bold text-gray-800">${result.simplified}</span>
                        <span class="ml-3 text-lg text-purple-600">${result.pinyin}</span>
                        <div class="flex gap-1 ml-2">${badgeHtml}</div>
                    </div>
                </div>
            </div>
            <div class="mt-3 text-gray-700">${result.definitions.slice(0, 2).join('; ')}</div>
            ${result.hsk_level ? `<div class="mt-2 text-sm text-gray-500">HSK ${result.hsk_level}</div>` : ''}
        `;
        card.onclick = () => selectWord(result);
        resultsList.appendChild(card);
    });

    document.getElementById('resultsContainer').classList.remove('hidden');
}

function selectWord(word) {
    selectedWord = word;

    document.getElementById('selectedHanzi').textContent = word.simplified;
    document.getElementById('selectedPinyin').textContent = word.pinyin;
    document.getElementById('selectedDefinition').textContent = word.definitions.join('; ');

    // Reset state — show generate button, hide progress + results
    document.getElementById('generatePrompt').classList.remove('hidden');
    document.getElementById('generationProgress').classList.add('hidden');
    document.getElementById('generatedContent').classList.add('hidden');
    generatedSentences = [];

    const wordCard = document.getElementById('wordCard');
    wordCard.classList.remove('hidden');
    wordCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function startGenerating() {
    document.getElementById('generatePrompt').classList.add('hidden');
    document.getElementById('generationProgress').classList.remove('hidden');
    document.getElementById('progressText').textContent = 'Generating 3 distinct sentences with Gemini...';
    await generateSentencesForCard();
}

let generatedSentences = [];
let selectedSentenceIndex = 0;

async function generateSentencesForCard() {
    if (!selectedWord) return;

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

    generatedSentences.forEach((sentence, index) => {
        const div = document.createElement('div');
        // Check for error object
        if (sentence.error) {
            div.innerHTML = `<p class="text-red-500">${sentence.error}</p>`;
            list.appendChild(div);
            return;
        }

        const isSelected = index === 0;
        if (isSelected) selectedSentenceIndex = 0;

        div.className = `p-4 border-2 rounded-xl cursor-pointer transition-all ${isSelected ? 'border-purple-500 bg-purple-50' : 'border-gray-200 hover:border-purple-300'}`;
        div.innerHTML = `
            <div class="flex items-start gap-3">
                <input type="radio" name="sentenceChoice" value="${index}" 
                    ${isSelected ? 'checked' : ''}
                    class="mt-1 w-5 h-5 text-purple-600 cursor-pointer">
                <div class="flex-1">
                    <p class="text-xl hanzi-text font-semibold text-gray-800 mb-1">${sentence.hanzi || sentence.sentence_simplified}</p>
                    <p class="text-sm text-gray-600">${sentence.english || sentence.sentence_english}</p>
                </div>
            </div>
        `;

        div.onclick = (e) => {
            if (e.target.type !== 'radio') {
                div.querySelector('input').checked = true;
            }
            // Update styles
            Array.from(list.children).forEach(c => {
                c.className = c.className.replace('border-purple-500 bg-purple-50', 'border-gray-200');
            });
            div.className = div.className.replace('border-gray-200', 'border-purple-500 bg-purple-50');
            selectedSentenceIndex = index;
        };

        list.appendChild(div);
    });
}
function closeSentenceModal() { /* Deprecated */ }
function startSentenceSelection() { /* Deprecated in v2 */ }

async function confirmAndAddToAnki() {
    // Add to Anki with selected sentence
    await addToAnkiDirect(selectedSentenceIndex);
}

async function addToAnkiDirect(sentenceIndex) {

    const btn = document.getElementById('addToAnkiBtn');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    // Show progress again
    document.getElementById('generatedContent').classList.add('hidden');
    document.getElementById('generationProgress').classList.remove('hidden');
    document.getElementById('progressText').textContent = 'Adding to Anki...';

    const sentence = (generatedSentences && generatedSentences[sentenceIndex]) || {};

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
                hsk_level: selectedWord.hsk_level || null,
                part_of_speech: selectedWord.part_of_speech || null
            })
        });

        const data = await response.json();

        if (data.queued) {
            showSuccess('Card queued — will appear in Anki within 30s');
            btn.textContent = '✓ Queued for Anki';
            btn.disabled = true;
        } else {
            showError(data.message || 'Failed to queue card');
            btn.disabled = false;
            btn.textContent = 'Add to Anki';
        }

        document.getElementById('generationProgress').classList.add('hidden');

    } catch (error) {
        showError('Failed to queue card: ' + error.message);
        btn.disabled = false;
        btn.textContent = 'Add to Anki';
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
}

function openSettingsModal() {
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
    checkStatus();
}

// Test Gemini API Key
async function testGeminiKey() {
    const keyInput = document.getElementById('geminiKey');
    const testBtn = document.getElementById('testGeminiBtn');
    const statusDiv = document.getElementById('geminiTestStatus');

    const apiKey = keyInput.value.trim();

    if (!apiKey) {
        statusDiv.className = 'mt-2 text-sm text-yellow-600';
        statusDiv.textContent = 'Please enter an API key first';
        statusDiv.classList.remove('hidden');
        return;
    }

    // Update UI - testing state
    testBtn.disabled = true;
    testBtn.textContent = 'Testing...';
    statusDiv.className = 'mt-2 text-sm text-gray-600';
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
            statusDiv.className = 'mt-2 text-sm text-green-600 font-semibold';
            statusDiv.textContent = '✅ ' + result.message;

            // Update status bar
            const geminiStatus = document.getElementById('geminiStatus');
            geminiStatus.className = 'w-3 h-3 rounded-full bg-green-500';
        } else {
            statusDiv.className = 'mt-2 text-sm text-red-600 font-semibold';
            statusDiv.textContent = '❌ ' + result.message;

            // Update status bar
            const geminiStatus = document.getElementById('geminiStatus');
            geminiStatus.className = 'w-3 h-3 rounded-full bg-red-500';
        }
    } catch (error) {
        statusDiv.className = 'mt-2 text-sm text-red-600';
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
