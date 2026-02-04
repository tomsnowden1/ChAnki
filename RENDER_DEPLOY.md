# ChAnki Free Deployment Guide (Render + Supabase)

## 💰 Total Cost: $0/month

This guide walks you through deploying ChAnki on completely free infrastructure.

---

## 📦 Step 1: Setup Database (Supabase)

### 1.1 Create Supabase Project

1. Visit **https://database.new**
2. Sign up with GitHub
3. Click "New Project"
4. Fill in:
   - **Name**: `ChAnki-DB`
   - **Database Password**: (generate a strong password and save it!)
   - **Region**: Choose closest to you
5. Click "Create Project" (takes ~2 minutes)

### 1.2 Get Connection String

1. Go to **Project Settings** (gear icon)
2. Click **Database** in sidebar
3. Scroll to **Connection String** section
4. Select **Transaction Pooler** (recommended for serverless)
5. Copy the connection string (looks like):
   ```
   postgresql://postgres.[ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
6. **Replace `[password]` with your actual password**
7. **Save this string** - you'll need it in Step 2

---

## 🚀 Step 2: Deploy to Render

### 2.1 Push Code to GitHub

```bash
cd /Users/jess/ChAnki

# Commit all changes
git add -A
git commit -m "Add Render + Supabase deployment config"
git push origin main
```

### 2.2 Deploy on Render

1. Visit **https://dashboard.render.com**
2. Sign up with GitHub
3. Click **New +** → **Web Service**
4. Click **Connect GitHub** → Select your repo: `tomsnowden1/ChAnki`
5. Configure:
   - **Name**: `chanki` (or whatever you want)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: (leave blank)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
   - **Instance Type**: **Free**

### 2.3 Set Environment Variables

Scroll to **Environment Variables** and add these 3 variables:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Paste your Supabase connection string from Step 1.2 |
| `GEMINI_API_KEY` | Your Gemini API key from https://aistudio.google.com/app/apikey |
| `SYNC_SECRET` | Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |

### 2.4 Deploy!

1. Click **Create Web Service**
2. Render will build and deploy (takes ~5 minutes)
3. Once live, you'll see: **"Your service is live at https://chanki.onrender.com"**
4. Visit the URL to verify it works!

---

## 🏠 Step 3: Setup Local Sync Agent

Now configure your home computer to auto-sync cards created on Render.

### 3.1 Create Config File

```bash
cd /Users/jess/ChAnki
cp sync_agent_config.json.example sync_agent_config.json
```

### 3.2 Edit Config

Open `sync_agent_config.json` and update:

```json
{
  "cloud_url": "https://chanki.onrender.com",
  "sync_secret": "<SAME_SECRET_FROM_STEP_2.3>",
  "anki_url": "http://localhost:8765",
  "poll_interval": 30,
  "deck_name": "Chinese::Mining"
}
```

### 3.3 Test the Agent

```bash
# Make sure Anki is running!
python3 local_sync_agent.py
```

You should see:
```
🚀 Sync Agent initialized
   Cloud: https://chanki.onrender.com
   Anki: http://localhost:8765
   Poll interval: 30s

🔄 Starting sync loop (every 30s)
   Press Ctrl+C to stop

✓ No pending cards
```

---

## ✅ Verification

### Test the Full Flow:

1. **Visit your Render URL** (e.g., `https://chanki.onrender.com`)
2. **Search for "hungry"**
3. **Click "Add to Anki"**
4. Should see: **"✅ Queued for sync (1 pending). Will sync when you're home!"**
5. **Check pending cards**:
   ```bash
   curl https://chanki.onrender.com/api/sync/stats
   ```
   Should show `"pending": 1`

6. **Make sure local sync agent is running** and **Anki is open**
7. Within 30 seconds, you should see:
   ```
   📥 Found 1 pending card(s)
      Syncing: 饿...
      ✓ Synced: 饿
   ✅ Acknowledged 1 card(s) to cloud
   ```

8. **Check Anki** - the card should be there!

---

## 🎯 How It Works

**Workflow:**

```
┌─────────────────────┐
│ You (anywhere)      │
│ Render URL          │────┐
└─────────────────────┘    │
                           │ Queue card
                           ▼
                    ┌──────────────┐
                    │ Supabase DB  │
                    │ (PostgreSQL) │
                    └──────────────┘
                           │
                           │ Poll every 30s
                           ▼
                   ┌─────────────────┐
                   │ Local Sync Agent│
                   │ (your laptop)   │
                   └─────────────────┘
                           │
                           │ Add card
                           ▼
                      ┌──────────┐
                      │   Anki   │
                      └──────────┘
```

---

## ⚡ Performance Notes

### Render Free Tier Limitations:

- **Spins down after 15 minutes of inactivity**
- First request after spin-down takes ~30 seconds to wake up
- **Solution**: Acceptable for personal use! Or ping it every 14 minutes with a cron job

### Supabase Free Tier:

- **500 MB database** (plenty for millions of dictionary entries)
- **Pauses after 7 days of inactivity** (just visit to wake it up)
- **Unlimited API requests**

---

## 🔧 Troubleshooting

### "Application failed to start"
- Check Render logs (Logs tab in dashboard)
- Verify `DATABASE_URL` is correct
- Ensure all env vars are set

### "Database connection failed"
- Verify Supabase connection string includes password
- Check if using **Transaction Pooler** URL (recommended)
- Try replacing `postgres://` with `postgresql://` in URL

### Agent can't reach cloud
- Verify `cloud_url` in config matches your Render URL
- Check `SYNC_SECRET` matches in both places
- Try accessing `https://your-url.onrender.com/api/health` in browser

---

## 💡 Pro Tips

### 1. Keep Render Awake (optional)

Use a free uptime monitor like UptimeRobot:
- Visit https://uptimerobot.com
- Add monitor: `https://chanki.onrender.com/api/health`
- Check interval: 5 minutes

This keeps your app warm and responsive!

### 2. Auto-Start Sync Agent

See `CLOUD_SYNC_GUIDE.md` for instructions on auto-starting the agent with launchd/systemd.

### 3. Backup Your Database

Supabase provides automatic backups, but you can also:
```bash
# Export dictionary entries
curl "https://chanki.onrender.com/api/export/dictionary" > backup.json
```

---

## 🎉 Success!

You now have:
- ✅ Free cloud hosting (Render)
- ✅ Free PostgreSQL database (Supabase)
- ✅ 124k+ dictionary entries
- ✅ AI sentence generation (Gemini)
- ✅ Auto-sync to local Anki
- ✅ **$0/month cost**

**Enjoy your supercharged Chinese learning!** 🚀
