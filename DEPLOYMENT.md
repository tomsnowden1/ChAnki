# Deploying ChAnki to the Cloud

## ⚠️ Important: Vercel Limitations

**Vercel is NOT recommended for ChAnki** because:
- ❌ Vercel doesn't support long-running Python servers (FastAPI+Uvicorn)
- ❌ Vercel has read-only filesystem (SQLite database won't work)
- ❌ AnkiConnect won't be accessible (needs local Anki running)

## ✅ Recommended Deployment Platforms

### Option 1: Railway.app (EASIEST)

**Best for:** Production deployments with database

1. **Sign up**: https://railway.app
2. **Create new project** → Deploy from GitHub
3. **Connect your repo**: `tomsnowden1/ChAnki`
4. **Add environment variables**:
   ```
   GEMINI_API_KEY=your_key_here
   ANKI_CONNECT_URL=http://localhost:8765
   ```
5. **Railway auto-detects** Python and runs it!

**Limitations**: AnkiConnect won't work (needs local Anki)

---

### Option 2: Render.com

**Best for:** Free tier with persistent storage

1. **Sign up**: https://render.com
2. **New Web Service** → Connect GitHub
3. **Configure**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**:
   ```
   GEMINI_API_KEY=your_key_here
   ```

---

### Option 3: Fly.io

**Best for:** Global edge deployment

```bash
# Install Fly CLI
brew install flyctl

# Login
fly auth login

# Launch app
fly launch

# Set environment variables
fly secrets set GEMINI_API_KEY=your_key_here

# Deploy
fly deploy
```

---

## 🔧 Environment Variables Setup

All platforms need these environment variables:

| Variable | Value | Required |
|----------|-------|----------|
| `GEMINI_API_KEY` | Your Gemini API key | ✅ Yes |
| `ANKI_CONNECT_URL` | `http://localhost:8765` | Optional |
| `DATABASE_URL` | Auto-configured | Optional |

### Getting Your Gemini API Key

1. Visit: https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Add to your deployment platform's environment variables

---

## 📦 If You MUST Use Vercel

Vercel requires significant changes:

1. **Switch to serverless database** (not SQLite)
2. **Remove AnkiConnect** (won't work in serverless)
3. **Refactor to serverless functions**

I can help with this if needed, but I **strongly recommend Railway or Render** instead.

---

## 🎯 Quick Deploy to Railway (30 seconds)

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Initialize
cd /Users/jess/ChAnki
railway init

# 4. Set environment variable
railway variables set GEMINI_API_KEY=your_key_here

# 5. Deploy
railway up
```

Done! Railway gives you a URL like `chanki-production.up.railway.app`

---

## 🔍 Testing After Deployment

Once deployed, test these endpoints:

- `your-url.com/` - Frontend should load
- `your-url.com/api/health` - Should return JSON with status
- `your-url.com/api/search?q=dog` - Should return dictionary results

---

## ⚠️ Known Limitations for Cloud Deployments

1. **AnkiConnect**: Only works when Anki is running locally
   - Cloud deployments can search and generate sentences
   - But "Add to Anki" button won't work (needs local Anki)

2. **Database**: 
   - SQLite works fine for Railway/Render
   - On first deploy, dictionary auto-downloads (~2-3 minutes)

3. **API Costs**:
   - Gemini Flash: 15 requests/min free
   - Sufficient for personal use
