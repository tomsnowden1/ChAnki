# ChAnki Cloud-Sync Quick Start

## ✨ New Feature: Cloud Queueing + Local Sync

Create Anki cards **anywhere** (on Railway) and they'll automatically sync to your local Anki when you get home!

---

## 🚀 Setup Instructions

### Step 1: Generate Sync Secret

```bash
cd /Users/jess/ChAnki
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Copy the output** - you'll need it for both Railway and local agent.

### Step 2: Deploy to Railway

1. **Push to GitHub** (already done):
   ```bash
   git push origin main
   ```

2. **Deploy on Railway**:
   - Go to https://railway.app
   - New Project → Deploy from GitHub
   - Select `tomsnowden1/ChAnki`
   - Railway auto-detects and deploys!

3. **Set Environment Variables** in Railway dashboard:
   ```
   GEMINI_API_KEY=<your_gemini_key>
   SYNC_SECRET=<paste_secret_from_step1>
   ```

4. **Add PostgreSQL**:
   - In Railway: "+ New" → "Database" → "PostgreSQL"
   - Railway automatically sets `DATABASE_URL`

5. **Done!** Your app is live at `your-app.up.railway.app`

### Step 3: Setup Local Sync Agent (Home Computer)

1. **Create config file**:
   ```bash
   cd /Users/jess/ChAnki
   cp sync_agent_config.json.example sync_agent_config.json
   ```

2. **Edit config**:
   ```json
   {
     "cloud_url": "https://your-app.up.railway.app",
     "sync_secret": "<paste_secret_from_step1>",
     "anki_url": "http://localhost:8765",
     "poll_interval": 30,
     "deck_name": "Chinese::Mining"
   }
   ```

3. **Run the agent**:
   ```bash
   python3 local_sync_agent.py
   ```

   You should see:
   ```
   🚀 Sync Agent initialized
      Cloud: https://your-app.up.railway.app
      Anki: http://localhost:8765
      Poll interval: 30s
   
   🔄 Starting sync loop (every 30s)
   ```

---

## 📱 How to Use

### When Away from Home (On Railway):
1. Visit your Railway app URL
2. Search for a word (e.g., "hungry")
3. Click "Add to Anki"
4. See message: **"✅ Queued for sync (3 pending). Will sync when you're home!"**

### When at Home:
1. Make sure **Anki is running** with AnkiConnect
2. Make sure **sync agent is running** (`python3 local_sync_agent.py`)
3. Agent automatically syncs cards every 30 seconds:
   ```
   📥 Found 3 pending card(s)
      Syncing: 你好...
      ✓ Synced: 你好
      Syncing: 谢谢...
      ✓ Synced: 谢谢
   ✅ Acknowledged 3 card(s) to cloud
   ```

---

## 🔧 Testing Locally First

Before deploying to Railway, test the queue system locally:

1. **Stop local server** if running:
   ```bash
   ./stop.sh
   ```

2. **Start server WITHOUT Anki running**:
   ```bash
   ./start.sh
   # Make sure Anki is closed!
   ```

3. **Add a card** - it should queue instead of syncing:
   - Visit http://localhost:5173
   - Search "dog" → Add to Anki
   - Should see: "✅ Queued for sync"

4. **Check pending cards**:
   ```bash
   curl http://localhost:5173/api/sync/stats | jq
   ```
   Should show `"pending": 1`

5. **Start Anki** and **run sync agent**:
   ```bash
   # Edit sync_agent_config.json first!
   python3 local_sync_agent.py
   ```

6. **Watch it sync**! Within 30 seconds, the card syncs to Anki.

---

## 🎯 Auto-Start Sync Agent (Optional)

### macOS (launchd):

Create `~/Library/LaunchAgents/com.chanki.syncagent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.chanki.syncagent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/jess/ChAnki/local_sync_agent.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/jess/ChAnki</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.chanki.syncagent.plist
```

Now the agent starts automatically when you log in!

---

## 🔍 Troubleshooting

### "Authentication failed - check SYNC_SECRET"
- Make sure `SYNC_SECRET` matches in both Railway and `sync_agent_config.json`

### "Anki is not running or AnkiConnect is not installed"
- Start Anki
- Install AnkiConnect: Tools → Add-ons → Get Add-ons → Code: `2055492159`

### Agent not syncing cards
- Check cloud URL is correct
- Verify Anki is running
- Check console for error messages

### Cards syncing but not showing in Anki
- Check deck name matches in `sync_agent_config.json`
- Verify deck exists in Anki
- Refresh Anki deck browser

---

## 📊 Monitoring

**Check sync statistics**:
```bash
curl https://your-app.up.railway.app/api/sync/stats
```

**View all pending cards**:
```bash
curl -H "X-Sync-Secret: YOUR_SECRET" \
  https://your-app.up.railway.app/api/sync/pending | jq
```

**Clear synced cards** (housekeeping):
```bash
curl -X DELETE -H "X-Sync-Secret: YOUR_SECRET" \
  https://your-app.up.railway.app/api/sync/clear-synced
```

---

## ✅ Success!

You now have a **cloud-first Anki workflow**:
- 📱 Queue cards from anywhere
- 🏠 Auto-sync when home
- ✨ Zero manual work

**Enjoy your new superpower!** 🚀
