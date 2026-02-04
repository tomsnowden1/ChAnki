/**
 * ChAnki v2 - Frontend JavaScript
 */

// State
let currentSettings = null;
let selectedWord = null;
let debounceTimer = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    checkStatus();
    setupEventListeners();

    // Check status periodically
    setInterval(checkStatus, 10000);
});

// Event Listeners
function setupEventListeners() {
    // Search with debounce
    document.getElementById('searchInput').addEventListener('input', (e) => {
        const query = e.target.value.trim();

        if (!query) {
            hideResults();
            return;
        }

        // Show searching indicator
        document.getElementById('searchingIndicator').style.opacity = '1';

        // Debounce search (300ms)
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    // Settings modal
    document.getElementById('settingsBtn').addEventListener('click', openSettingsModal);
    document.getElementById('closeSettings').addEventListener('click', closeSettingsModal);
    document.getElementById('cancelSettings').addEventListener('click', closeSettingsModal);
    document.getElementById('settingsForm').addEventListener('submit', saveSettings);

    // Test Key Button
    document.getElementById('testGeminiBtn').addEventListener('click', testGeminiKey);

    // Load Decks Button
    document.getElementById('loadDecksBtn').addEventListener('click', loadDecks);

    // Add to Anki (Confirm selection)
    const addBtn = document.getElementById('addToAnkiBtn');
    // Remove old listeners to avoid duplicates if any
    const newBtn = addBtn.cloneNode(true);
    addBtn.parentNode.replaceChild(newBtn, addBtn);
    newBtn.addEventListener('click', confirmAndAddToAnki);
}

// Check health status and update UI indicators
async function checkStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        // Update status indicators
        updateStatusDot('dictStatus', data.components.database?.status === 'healthy');
        updateStatusDot('geminiStatus', data.components.gemini?.status === 'healthy');
        updateStatusDot('ankiStatus', data.components.anki?.status === 'healthy');

    } catch (error) {
        console.error('Health check failed:', error);
        // Set all indicators to disconnected on error
        updateStatusDot('dictStatus', false);
        updateStatusDot('geminiStatus', false);
        updateStatusDot('ankiStatus', false);
    }
}

function updateStatusDot(elementId, isConnected) {
    const dot = document.getElementById(elementId);
    if (dot) {
        // Set color directly - green for connected, gray for disconnected
        dot.style.backgroundColor = isConnected ? '#22c55e' : '#9ca3af';
    }
}

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

        // Store in global state
        currentSettings = settings;

        // Populate form if settings modal is visible
        if (settings.gemini_api_key) {
            const keyInput = document.getElementById('geminiKeyInput');
            if (keyInput) keyInput.value = settings.gemini_api_key;
        }

        if (settings.anki_deck_name) {
            const deckInput = document.getElementById('deckNameInput');
            if (deckInput) deckInput.value = settings.anki_deck_name;
        }

    } catch (e) {
        console.error('Failed to load settings:', e);
        // Continue silently - settings are optional for basic functionality
    }
}

// Save application settings
async function saveSettings(event) {
    event.preventDefault();

    const geminiKey = document.getElementById('geminiKeyInput').value;
    const deckName = document.getElementById('deckNameInput').value;

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gemini_api_key: geminiKey,
                anki_deck_name: deckName
            })
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

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.results) {
            displayResults(data.results, data.count || data.results.length);
        } else {
            // Handle empty/error
            displayResults([], 0);
        }
    } catch (e) {
        showError('Search failed: ' + e.message);
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
        } else {
            badgeHtml += `<span class="ml-2 px-3 py-1 bg-gray-100 text-gray-500 text-xs font-medium rounded-full border border-gray-200">Rare</span>`;
        }

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

async function selectWord(word) {
    selectedWord = word;

    // Update UI
    document.getElementById('selectedHanzi').textContent = word.simplified;
    document.getElementById('selectedPinyin').textContent = word.pinyin;
    document.getElementById('selectedDefinition').textContent = word.definitions.join('; ');

    // Show word card
    const wordCard = document.getElementById('wordCard');
    wordCard.classList.remove('hidden');
    wordCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Show progress
    document.getElementById('generationProgress').classList.remove('hidden');
    document.getElementById('generatedContent').classList.add('hidden');
    document.getElementById('progressText').textContent = 'Generating 3 distinct sentences with Gemini...';

    // Auto-generate sentences
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

        // Check format based on new strict JSON requirement
        // The backend now returns a list directly or an error list
        let sentences = [];
        if (Array.isArray(data)) {
            // It might be the list directly from our new endpoint logic if we changed it?
            // Wait, the API endpoint wrapper in `sentences.py` still wraps it in `GenerateSentencesResponse`
            // Let's check `sentences.py` response model.
        }

        // Actually, let's look at `sentences.py`. It returns `GenerateSentencesResponse(success=True, sentences=...)`.
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

    try {
        const response = await fetch('/api/add-to-anki', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                hanzi: selectedWord.simplified,
                pinyin: selectedWord.pinyin,
                definition: selectedWord.definitions[0],
                hsk_level: selectedWord.hsk_level || null,
                part_of_speech: selectedWord.part_of_speech || null,
                selected_sentence_index: sentenceIndex  // NEW: Pass selected index
            })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(data.message);
            btn.textContent = '✓ Added to Anki';
            btn.disabled = true;
        } else {
            if (data.status === 'duplicate') {
                showError(data.message);
                btn.textContent = 'Already in Anki';
            } else {
                showError(data.message);
                btn.disabled = false;
                btn.textContent = 'Add to Anki';
            }
        }

        document.getElementById('generationProgress').classList.add('hidden');

    } catch (error) {
        showError('Failed to add to Anki: ' + error.message);
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
