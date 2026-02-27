# Deploying to Hugging Face Spaces (Free)

## Why Hugging Face Spaces?

| Platform | Free RAM | Works? |
|----------|----------|--------|
| Hugging Face Spaces | **16 GB** | ✓ |
| Streamlit Cloud | 1 GB | ✗ (sentence-transformers alone needs ~600 MB) |
| Render free | 512 MB | ✗ |

---

## Step-by-Step Deployment

### Step 1 — Create a GitHub repository

1. Go to https://github.com/new
2. Name it `BNR-DS-Challenge` (or any name)
3. Set it to **Public**
4. Click **Create repository**

### Step 2 — Push the project to GitHub

Open a terminal **in the project folder**:

```bash
git init
git add .
git commit -m "Initial commit: BNR RAG System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/BNR-DS-Challenge.git
git push -u origin main
```

> **Important:** The `.env` file is in `.gitignore` — your API key will NOT be pushed.

### Step 3 — Create a Hugging Face account

Go to https://huggingface.co and sign up (free).

### Step 4 — Create a new Space

1. Go to https://huggingface.co/new-space
2. Fill in:
   - **Space name:** `BNR-Document-Intelligence` (or any name)
   - **License:** MIT
   - **SDK:** Streamlit
   - **Hardware:** CPU basic (Free)
3. Click **Create Space**

### Step 5 — Connect your GitHub repository

In your new Space:
1. Click **Files** tab → **Add file** → **Link to GitHub repository**
2. Authorize Hugging Face to access your GitHub
3. Select your `BNR-DS-Challenge` repository
4. Branch: `main`
5. Click **Link repository**

**Or** — push directly to the HF Space git remote:
```bash
# Clone the Space, copy your files, push
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/BNR-Document-Intelligence
git push hf main
```

### Step 6 — Add the required Space metadata

The Space's `README.md` needs YAML frontmatter so HF knows how to run it.
Add these lines at the very top of your `README.md`:

```
---
title: BNR Document Intelligence Assistant
emoji: 🏦
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.40.0
app_file: app.py
pinned: false
---
```

Then commit and push:
```bash
git add README.md
git commit -m "Add HF Spaces metadata"
git push
```

### Step 7 — Set secrets (API key)

In your HF Space:
1. Click **Settings** tab
2. Scroll to **Variables and secrets**
3. Click **New secret**
4. Add:

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (your key) |
| `CHROMADB_MODE` | `ephemeral` |

5. Click **Save**
6. The Space will automatically restart with the secrets injected.

### Step 8 — Wait for build

The Space will:
1. Install dependencies from `requirements.txt` (~3-5 min first time)
2. Start the Streamlit app

Your app will be live at:
```
https://huggingface.co/spaces/YOUR_HF_USERNAME/BNR-Document-Intelligence
```

---

## Cold Start Behaviour

On first visit (or after ~30 min of inactivity):
- The app rebuilds the vector index from the corpus (~20-30 s)
- Users see a spinner: *"Building knowledge index from corpus…"*
- Subsequent queries are fast (~2-6 s)

This is normal for free-tier Spaces — the container sleeps when idle.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Check `requirements.txt` — ensure all packages are listed |
| `ANTHROPIC_API_KEY not set` | Check you added it in Space Settings → Secrets |
| App crashes on startup | Check Space logs — likely a memory issue if RAM is exhausted |
| `PermissionError` on `chroma_db/` | Ensure `CHROMADB_MODE=ephemeral` is set in secrets |

---

## Local Development (unchanged)

```bash
pip install -r requirements.txt
cp .env.example .env   # add your API key
streamlit run app.py
```
