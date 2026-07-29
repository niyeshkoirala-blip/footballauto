# Setup Guide — Automatic Football Facebook Page Bot

Everything is **100% free**. No Facebook Developer account, no browser automation.

---

## What the bot does

A daemon polls **BBC Sport football** once a minute. When a story appears that is
both **new** (published in the last 30 minutes) and **significant enough**
(keyword score ≥ 50), it builds a branded image and posts it to your Facebook
Page through a Make.com webhook — typically within a minute of the story landing
in the feed.

```
BBC RSS ──poll 60s──▶ filter ──▶ image + caption ──▶ Make.com ──▶ Facebook Page
                        │
                        ├─ published < 30 min ago?
                        ├─ actually football?
                        ├─ score ≥ BREAKING_THRESHOLD?
                        ├─ not already posted / not a retelling?
                        └─ daily budget left?
```

Every story that clears the filter in a given poll is queued, so two stories
landing in the same minute both go out (spaced 25–35 s apart).

Volume is bounded at both ends: **at least 10 posts/day** (if the bot falls
behind pace the score threshold drops to 0 so the floor is still met) and **at
most 60/day**. In practice BBC supplies ~22 qualifying stories/day.

Each post is a branded 1080×1350 image with the headline overlaid, plus an
AI-written caption (hook, context, fan question, hashtags, source credit).

---

## What you need (all free)

| Service | What for | Link |
|---------|----------|------|
| **Make.com** | Posts to your Facebook Page | make.com |
| **Pexels** | Fallback background photos | pexels.com/api |
| **Groq** *(optional)* | AI-written captions via Llama 3.1 | console.groq.com |
| **GitHub** | Free hosting + 24/7 scheduler | github.com |

---

## Step 1 — Set up the Make.com webhook

This is how posts reach Facebook. It is **required** — the bot exits at startup
without it.

1. Sign up at **make.com** (free tier: 1,000 operations/month)
2. Create a new scenario
3. First module: **Webhooks → Custom webhook** → Add → copy the URL
4. Second module: **Facebook Pages → Create a Post**, connected to your Page
5. Map the fields:

   | Facebook field | Value |
   |---|---|
   | Message | `{{1.message}}` |
   | Photo | `{{1.photo}}` *(the binary file, not a URL)* |

6. Set the scenario schedule to **Immediately** — on an interval it will batch
   your posts and nothing above will feel instant
7. Turn the scenario **ON**

> **More than 1,000 posts/month?** `MAKE_WEBHOOK_URL` accepts several
> comma-separated URLs, one per free Make account. Each post picks one at random
> and falls through to the others on a hard error, so five accounts give roughly
> 5× the quota.

> **Watch out:** Make returns HTTP 200 even when an account is out of
> operations, so an exhausted account looks like success and the post silently
> disappears. Rotation only protects against hard errors, not quota exhaustion.

---

## Step 2 — Get your Pexels API key

1. Go to **pexels.com/api** → Get Started
2. Sign up — no credit card
3. Free tier: 200 requests/hour, 20,000/month

Pexels is only the fallback. The bot prefers the journalist's own photo from the
RSS feed and the article's `og:image`, so most posts never touch it.

---

## Step 3 — Get your Groq API key *(optional but recommended)*

Without Groq the caption falls back to a structured version of the RSS
description. With it, Llama 3.1 writes a proper hook + context + fan question.

1. Go to **console.groq.com** → sign in with Google
2. API Keys → Create API Key
3. Free tier: 14,400 requests/day

---

## Step 4 — Configure your `.env`

```bash
cp .env.example .env
nano .env
```

```
# Required
MAKE_WEBHOOK_URL=https://hook.eu2.make.com/xxxxxxxx
PEXELS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# Optional
GROQ_API_KEY=gsk_xxxxx...
PAGE_NAME=FOOTBALL NEWS
```

### All settings

| Variable | Default | What it does |
|---|---|---|
| `MAKE_WEBHOOK_URL` | — | **Required.** One or more comma-separated Make webhook URLs |
| `PEXELS_API_KEY` | — | **Required.** Fallback photo search |
| `GROQ_API_KEY` | — | AI captions; falls back to RSS text if unset |
| `PAGE_NAME` | `FOOTBALL NEWS` | Branding printed on the image |
| `BREAKING_THRESHOLD` | `50` | Score a story must reach to post |
| `MAX_AGE_MINUTES` | `30` | How new a story must be. This is the freshness gate |
| `MIN_POSTS_PER_DAY` | `10` | Floor — threshold relaxes if behind pace |
| `MAX_POSTS_PER_DAY` | `60` | Hard daily cap, survives across runs |
| `POLL_SECONDS` | `60` | How often the daemon re-reads the feed |
| `POST_DELAY_MIN` / `MAX` | `25` / `35` | Seconds between posts within one run |
| `MAX_RUNTIME_MIN` | `290` | Daemon lifetime before it hands off to the next job |

---

## Step 5 — Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Six packages, no browser download.

---

## Step 6 — Test before going live

### Preview — scores and ranks stories, posts nothing, creates no images

```bash
python main.py --preview       # top 15
python main.py --preview 30    # top 30
```

### Dry run — builds the real image, skips the upload

```bash
python main.py --dry-run
xdg-open dry_run_output.jpg
```

### Live

```bash
python main.py            # one pass
python main.py --daemon   # continuous, this is what CI runs
```

---

## Step 7 — How stories are scored

The score is **uncapped** — a story matching several signals ranks well clear of
a one-signal story instead of everything tying at a ceiling.

| Signal | Points |
|--------|--------|
| World Cup mentioned | +200 |
| Match result ("beats", "drew", "on penalties", "knocked out") | +150 |
| Hall-of-Fame player named (Messi, Ronaldo, Mbappé…) | +40 each |
| Confirmed transfer ("has signed", "officially unveiled") | +40 |
| Trophy / title won | +35 |
| Manager sacked or appointed | +35 |
| Serious injury or ban | +30 |
| Big money / record fee | +25 |
| Knockout stage (final, semi, quarter) | +25 |
| Major league or competition name | +20 |
| Known club or national team | +20 |
| Goals and in-match action | +20 |
| Scoreline detected ("2-1", "3–0") | +15 |
| Milestone language ("first ever", "record", "history") | +15 |
| Current squad player named | +10 each |
| Rumour language ("linked", "could", "in talks") | −15 |

Squad names are pulled live from TheSportsDB and cached for 7 days — no manual
maintenance.

**Score decides *whether* a story posts. Publication time decides *when*.**
Stories go out newest-first; a high-scoring story from an hour ago never jumps
ahead of one published five minutes ago.

Non-football stories are rejected outright, so a horse race cannot score its way
onto your page.

---

## Step 8 — Deploy on GitHub Actions

1. Create a **public GitHub repository** (public = unlimited free Actions minutes)
2. Push the project
3. **Settings → Secrets and variables → Actions → New repository secret**:

   | Secret | Value |
   |--------|-------|
   | `MAKE_WEBHOOK_URL` | From Step 1 |
   | `PEXELS_API_KEY` | From Step 2 |
   | `GROQ_API_KEY` | From Step 3 *(optional)* |
   | `PAGE_NAME` | e.g. `FOOTBALL NEWS` |

   Everything else is set as plain `env:` values in the workflow file — edit
   `.github/workflows/auto_post.yml` to tune them.

4. **Actions tab → Auto Post Football News → Run workflow** to start the chain.

### How 24/7 works

Each job runs the daemon for `MAX_RUNTIME_MIN` (290), then dispatches its own
successor before exiting. `workflow_dispatch` fires within seconds, unlike cron
which GitHub can delay by hours. The `cron: "3 */5 * * *"` line is only a
backstop to revive the chain if it ever dies.

Two consequences worth knowing:

- There is a **~1–2 minute gap** at each handoff (checkout + pip install) where
  nothing is polling.
- Because the freshness window is 30 minutes and there is no backfill, **news
  published while the bot is down is lost permanently**. That is the deliberate
  trade for never posting stale news.

State (`posted_stories.json`) is committed back to the repo after each post, so
the bot never reposts and the daily counter survives restarts.

---

## Run modes

| Command | What it does |
|---------|-------------|
| `python main.py --preview` | Score and rank — nothing posted |
| `python main.py --preview 30` | Same, show top 30 |
| `python main.py --dry-run` | Build image, skip the upload |
| `python main.py` | One pass — post everything new that qualifies |
| `python main.py --daemon` | Continuous polling; what GitHub Actions runs |

---

## Image sources (priority order)

1. Photo embedded in the RSS entry (the journalist's own image)
2. `og:image` from the article page
3. Player photo from TheSportsDB
4. Team fan art from TheSportsDB
5. Wikipedia player headshot
6. Pexels keyword search
7. Solid green fallback

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `❌ Missing environment variable(s): MAKE_WEBHOOK_URL` | Secret not set. The bot refuses to start rather than fail silently |
| Nothing posts, no errors | Nothing scored ≥ `BREAKING_THRESHOLD` in the last 30 min. Run `--preview` to see scores |
| Posts appear minutes late | Make scenario is on an interval schedule, not "Immediately" |
| Posts stop mid-day | Daily cap hit, or the Make account ran out of operations (returns 200 regardless) |
| A story you saw on BBC never posted | It scored below threshold, or arrived during a job handoff |

---

## Cost summary

| Item | Cost |
|------|------|
| Make.com | Free (1,000 ops/month per account) |
| Pexels API | Free |
| Groq API | Free |
| TheSportsDB API | Free |
| GitHub Actions | Free (public repo) |
| **Total** | **$0** |
