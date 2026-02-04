# ChAnki v2.0

Chinese to Anki Bridge - A modern web app for learning Chinese with Anki integration.

## 🚀 Quick Start

### Start the Server
```bash
./start.sh
```

Then open your browser to: **http://localhost:5173**

### Stop the Server
```bash
./stop.sh
```

## ✨ Features

- 📚 **124,260+ Dictionary Entries** - Comprehensive CC-CEDICT database
- 🤖 **AI-Powered** - Gemini Flash for sentence generation
- 🃏 **Anki Integration** - Direct export to your Anki decks
- 🔍 **Smart Search** - English, Pinyin, or Chinese characters
- 🎯 **Self-Healing** - Auto-repairs database on startup
- 📊 **Health Monitoring** - Real-time system status

## 📋 Requirements

- Python 3.9+
- Anki with AnkiConnect add-on
- Gemini API key (free tier available)

## ⚙️ Configuration

1. **Gemini API Key**: Edit `.env` and add your key:
   ```bash
   GEMINI_API_KEY=your_key_here
   ```
   Get a free key: https://aistudio.google.com/app/apikey

2. **Anki**: Make sure Anki is running with AnkiConnect installed

## 🔍 System Health

Check system status: http://localhost:5173/api/health

- 🟢 Green indicators = All systems operational
- 🔴 Red indicators = Check configuration

## 🛠️ Troubleshooting

### Server won't start
```bash
# Stop any existing server
./stop.sh

# Start fresh
./start.sh
```

### Search not working
Hard refresh your browser: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+F5** (Windows)

### Database issues
The database auto-heals on startup. If issues persist, delete `data/chanki.db` and restart.

## 📝 Manual Commands

If you prefer manual control:

```bash
# Activate virtual environment
source venv/bin/activate

# Start server manually
uvicorn main:app --reload --host 0.0.0.0 --port 5173

# Run diagnostics
python3 system_audit.py
```

## 🎯 Current Status

- ✅ Database: 124,260 entries loaded
- ✅ Gemini AI: Connected (gemini-flash-latest)
- ✅ AnkiConnect: Integrated
- ✅ Self-healing: Enabled
- ✅ Health monitoring: Active

---

**Built with:** FastAPI, SQLAlchemy, Gemini API, AnkiConnect
