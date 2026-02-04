# ChAnki v2 - File Structure

```
ChAnki/
├── main.py                      # FastAPI application entry point
├── requirements_v2.txt          # Python dependencies
├── .env.example                 # Environment variables template
├── chanki.db                    # SQLite database (auto-created)
│
├── app/
│   ├── __init__.py
│   ├── config.py                # Pydantic Settings (loads from .env)
│   │
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── settings.py          # Settings table
│   │   ├── dictionary.py        # CC-CEDICT entries table
│   │   └── history.py           # User search/add history (optional)
│   │
│   ├── schemas/                 # Pydantic schemas for API validation
│   │   ├── __init__.py
│   │   ├── search.py            # SearchRequest, SearchResponse
│   │   ├── settings.py          # SettingsUpdate, SettingsResponse
│   │   └── anki.py              # AddToAnkiRequest, AddToAnkiResponse
│   │
│   ├── api/                     # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── search.py            # GET /api/search
│   │   ├── settings.py          # GET/PUT /api/settings
│   │   └── anki.py              # POST /api/add-to-anki, GET /api/anki/status
│   │
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── anki.py              # AnkiConnect wrapper (JSON-RPC)
│   │   ├── dictionary.py        # Dictionary search logic
│   │   ├── audio.py             # edge-tts audio generation
│   │   └── gemini.py            # Gemini API sentence generation
│   │
│   ├── db/                      # Database utilities
│   │   ├── __init__.py
│   │   ├── session.py           # SQLAlchemy session management
│   │   └── init_db.py           # DB initialization & CEDICT import
│   │
│   └── templates/               # Anki card templates
│       └── card_template.html   # ChAnki-Advanced card styling
│
├── static/                      # Frontend assets
│   ├── index.html               # Main SPA
│   ├── app.js                   # Frontend logic (vanilla JS or Vue CDN)
│   └── styles.css               # Custom CSS (+ Tailwind CDN)
│
├── scripts/                     # Utility scripts
│   └── seed_dictionary.py       # One-time CEDICT import to SQLite
│
└── tests/                       # Pytest test suite
    ├── __init__.py
    ├── test_api.py
    ├── test_anki_service.py
    └── test_dictionary.py
```

## Key Architecture Decisions

### 1. Database Schema

**Settings Table**
```sql
CREATE TABLE settings (
    id INTEGER PRIMARY KEY,
    anki_deck_name TEXT DEFAULT 'Chinese::Mining',
    anki_model_name TEXT DEFAULT 'ChAnki-Advanced',
    gemini_api_key TEXT,
    hsk_target_level INTEGER DEFAULT 3,
    tone_colors_enabled BOOLEAN DEFAULT TRUE,
    generate_audio BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP
);
```

**Dictionary Table**
```sql
CREATE TABLE dictionary (
    id INTEGER PRIMARY KEY,
    traditional TEXT,
    simplified TEXT,
    pinyin TEXT,
    definitions TEXT,  -- JSON array
    hsk_level INTEGER,
    UNIQUE(simplified, traditional)
);
CREATE INDEX idx_simplified ON dictionary(simplified);
CREATE INDEX idx_pinyin ON dictionary(pinyin);
```

### 2. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search?q={query}` | Search dictionary |
| GET | `/api/settings` | Get current settings |
| PUT | `/api/settings` | Update settings |
| POST | `/api/add-to-anki` | Generate & add card |
| GET | `/api/anki/status` | Check AnkiConnect connection |
| GET | `/` | Serve frontend SPA |

### 3. Background Task Flow (Add to Anki)

```
User clicks word
    ↓
POST /api/add-to-anki {hanzi, pinyin, definition}
    ↓
├─ Check duplicate (AnkiConnect)
│   ├─ If exists: return {"status": "duplicate"}
│   └─ If not: continue
├─ Generate sentence (Gemini API)
│   └─ Prompt: "HSK {level} sentence with {word}"
├─ Generate audio (edge-tts)
│   ├─ Word audio → base64
│   └─ Sentence audio → base64
├─ Create note type if missing (AnkiConnect)
└─ Add note (AnkiConnect)
    └─ return {"status": "success", "note_id": 123}
```

### 4. Error Handling Strategy

- **AnkiConnect offline**: Return `{"error": "anki_offline", "message": "..."}`
- **Gemini API failure**: Use fallback template sentence
- **Audio generation failure**: Add card without audio
- **Database errors**: Log and return 500 with generic message

### 5. Frontend Architecture

- **Single HTML file** with Tailwind CDN
- **Vanilla JS** with fetch API (or Vue 3 CDN for reactivity)
- **Components**:
  - SearchBar (debounced input)
  - ResultsGrid (clickable cards)
  - SettingsModal (slide-in panel)
  - StatusBar (Anki/Gemini connection indicators)

## Deployment

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements_v2.txt

# Initialize database
python scripts/seed_dictionary.py

# Configure
cp .env.example .env
# Edit .env with GEMINI_API_KEY

# Run
uvicorn main:app --reload --port 5173
```

## Success Criteria

- [ ] SQLite DB with 100K+ CEDICT entries
- [ ] Settings persist across restarts
- [ ] Audio files generate in <2 seconds
- [ ] Anki note type auto-created on first run
- [ ] Gemini fallback works when offline
- [ ] Frontend debounce prevents lag
- [ ] All errors handled gracefully
