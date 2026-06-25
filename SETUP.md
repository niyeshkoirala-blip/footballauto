# Setup Guide — Automatic Football Facebook Page Bot

Everything is **100% free**. No Facebook Developer account needed.

---

## What the bot does

Every 15 minutes the bot scans the top football news feeds (BBC Sport, ESPN, Sky Sports, Guardian, Goal.com), scores each story 0–100 for significance, and:

- **Immediately posts** any story that scores ≥ 55 (breaking news)
- **Always posts** the best new story at 08:00, 14:00, and 20:00 UTC regardless of score
- For every post it also publishes a **10-second Facebook Reel** — the same image in 9:16 vertical format with a slowed funk track underneath

Each post includes:
- A branded 1080×1080 image with the headline overlaid
- An AI-written caption (hook, context, fan question, hashtags, source credit)
- A reel version with background music from your `music/` folder

---

## What you need (all free)

| Service | What for | Link |
|---------|----------|------|
| **Pexels** | Football background photos | pexels.com/api |
| **Groq** *(optional)* | AI-written captions via Llama 3.1 | console.groq.com |
| **GitHub** | Free hosting + auto-scheduler | github.com |

Your normal **Facebook login** is used directly — no developer setup required.

---

## Step 1 — Get your Pexels API key

1. Go to **pexels.com/api** → Get Started
2. Sign up — no credit card
3. Your key appears on the dashboard immediately
4. Free tier: 200 requests/hour, 20,000/month

---

## Step 2 — Get your Groq API key *(optional but recommended)*

Without Groq the caption falls back to the raw RSS description. With it, Llama 3.1 writes a proper hook + context + fan question for every post.

1. Go to **console.groq.com** → sign in with Google
2. API Keys → Create API Key
3. Free tier: 14,400 requests/day

---

## Step 3 — Add background music for Reels

Drop `.mp3` or `.wav` files into the `music/` folder. The bot picks one at random for each reel. Any instrumental track works — the slowed-funk style fits well.

If the folder is empty a synthetic funky beat is generated automatically on first run.

---

## Step 4 — Configure your `.env`

```bash
cp .env.example .env
nano .env        # or open in your editor
```

```
# Required
FB_EMAIL=your_facebook_email@gmail.com
FB_PASSWORD=your_facebook_password
FB_PAGE_URL=https://www.facebook.com/YourPageName
PEXELS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# Optional
GROQ_API_KEY=gsk_xxxxx...

# Settings
PAGE_NAME=FOOTBALL NEWS
POSTS_PER_RUN=1
BREAKING_THRESHOLD=55
POST_DELAY_MIN=25
POST_DELAY_MAX=35
```

`FB_PAGE_URL` — copy the URL from your browser when you're on your Facebook page.

---

## Step 5 — Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright's browser (one-time, ~100 MB)
playwright install chromium
```

---

## Step 6 — Test before going live

### Preview mode — scores stories, nothing posted, no images created

```bash
python main.py --preview       # top 15
python main.py --preview 30    # top 30
```

Output:
```
  # 1  [████████░░]  80/100  ✅  WOULD POST NOW
       Arsenal beats Chelsea 2-1 in Premier League
       Premier League  ·  BBC Sport

  # 2  [████░░░░░░]  40/100  ⏭   would skip (score too low)
       Arsenal linked with new midfielder
       Transfer News  ·  Sky Sports
```

### Dry-run mode — creates image + reel, skips Facebook

```bash
python main.py --dry-run
xdg-open dry_run_output.jpg   # view the post image
xdg-open dry_run_reel.mp4     # view the reel
```

### Live run

```bash
python main.py
```

Playwright opens a headless Chrome, logs into Facebook with your credentials, saves the session to `fb_session.json` (reused on future runs), and publishes both the post and the reel.

> **Facebook security check:** If Facebook asks for a code on first run, log in manually in your regular browser once, complete the check, then run the bot again.

---

## Step 7 — How stories are scored

The bot scores every headline 0–100:

| Signal | Points |
|--------|--------|
| Confirmed transfer ("has signed", "officially unveiled") | +40 |
| Trophy / title won | +35 |
| Manager sacked or appointed | +35 |
| Serious injury or ban | +30 |
| Match result verb ("beats", "beat", "defeated", "drew") | +25 |
| Knockout stage (final, semi, quarter) | +25 |
| Big moment (hat-trick, comeback, penalty shootout) | +20 |
| Major league or competition name | +20 |
| Known club or national team name | +20 |
| Scoreline detected ("2-1", "3–0") | +15 |
| Milestone language ("older than", "first ever", "history") | +15 |
| Multiple top players mentioned | +10 per extra player |
| Rumour language ("linked", "could", "in talks") | −15 |

Player names are pulled live from TheSportsDB squad rosters for 29 top clubs and cached for 7 days — no manual maintenance needed.

A story must score **≥ 55** (set by `BREAKING_THRESHOLD`) to trigger an immediate post. Raise the number for fewer/bigger posts, lower it for more frequent posting.

---

## Step 8 — Schedule on GitHub Actions

1. Create a **public GitHub repository** (public = unlimited free Actions minutes)
2. Push the project:
   ```bash
   git init
   git add -A
   git commit -m "football bot"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```
3. Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

   | Secret | Value |
   |--------|-------|
   | `FB_EMAIL` | Your Facebook email |
   | `FB_PASSWORD` | Your Facebook password |
   | `FB_PAGE_URL` | e.g. `https://www.facebook.com/MyFootballPage` |
   | `PEXELS_API_KEY` | From Step 1 |
   | `GROQ_API_KEY` | From Step 2 *(optional)* |
   | `PAGE_NAME` | e.g. `FOOTBALL NEWS` |

4. The bot runs automatically:
   - **Every 15 minutes** — posts if a story scores ≥ 55
   - **08:00, 14:00, 20:00 UTC daily** — always posts the best new story

5. **Manual trigger:** Actions tab → Auto Post Football News → Run workflow

> **Note:** Music files in `music/` are not committed to GitHub by default (they're large). On GitHub Actions the bot will auto-generate the funky beat WAV instead. If you want your own tracks on Actions, either commit the `music/` folder or add a download step to the workflow.

---

## Run modes

| Command | What it does |
|---------|-------------|
| `python main.py --preview` | Score and rank stories — nothing posted |
| `python main.py --preview 30` | Same, show top 30 |
| `python main.py --dry-run` | Create image + reel, skip Facebook |
| `python main.py` | Breaking-news mode — post if score ≥ threshold |
| `python main.py --scheduled` | Scheduled mode — post best story regardless of score |

---

## Image sources (priority order)

The bot tries each source in order and uses the first one that works:

1. Photo embedded directly in the RSS feed (journalist's own image — most current)
2. `og:image` from the article page
3. Player photo from TheSportsDB
4. Team fan art from TheSportsDB
5. Wikipedia player headshot
6. Pexels keyword search
7. Solid green fallback

---

## Cost summary

| Item | Cost |
|------|------|
| Pexels API | Free |
| Groq API | Free |
| TheSportsDB API | Free |
| GitHub Actions | Free (public repo) |
| Facebook account | Already have it |
| **Total** | **$0** |
