#!/usr/bin/env python3
"""
Automatic Football Facebook Page Bot
─────────────────────────────────────
Fetches the latest football news, creates a branded post image,
and publishes it to a Facebook Page — all using free services.

Usage:
  python main.py --daemon         # 24/7: poll every POLL_SECONDS, post fresh news
  python main.py                  # one pass: post whatever is new and qualifies
  python main.py --dry-run        # fetch + score + create image; skip the upload
  python main.py --preview        # show top 15 stories with scores; posts nothing
  python main.py --preview 30     # same but show top 30
  python main.py --preview --why  # also show which terms made each score
"""

import os
import random
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.news_fetcher      import (explain_story, fetch_news, same_event,
                                   score_story)
from src.match_fetcher     import fetch_matches
from src.content_formatter import format_caption, format_image_brief
from src.image_creator     import create_post_image, save_image
<<<<<<< HEAD
from src.webhook_poster    import post_via_webhook
from src.graph_poster      import post_reel
from src.reel_creator      import create_reel
from src.story_tracker     import (behind_pace, is_posted, mark_posted,
                                   mark_reel, posts_today, reels_today,
                                   relaxed_threshold)
=======
from src.webhook_poster    import post_via_webhook, post_reel_via_webhook
from src.reel_creator      import classify_mood, create_reel, select_song
from src.story_tracker     import behind_pace, is_posted, mark_posted, posts_today
>>>>>>> c43bd64 (feat: add sequential reel publishing and webhook setup tests)


def _threshold() -> int:
    """Score a story must reach to be posted. One reader so --preview can
    never disagree with what run() would actually do."""
    return int(os.getenv("BREAKING_THRESHOLD", "50"))


def _gather(max_stories: int) -> list[dict]:
    """RSS news plus imminent kick-offs and fresh full-times. Both sources
    yield the same story shape, so everything downstream is unchanged. One
    reader, again so --preview cannot disagree with run()."""
    news    = fetch_news(max_stories=max_stories)
    matches = fetch_matches()
    if matches:
        print(f"    +{len(matches)} live fixture/result card(s).")
    return news + matches


def validate_config(dry_run: bool) -> None:
    # A normal post is always the first publishing action. Reel configuration
    # is intentionally checked only after that post succeeds, so a missing Reel
    # account never prevents the existing photo pipeline from running.
    required = ["PEXELS_API_KEY", "MAKE_WEBHOOK_URL"]
    if dry_run:
        required = ["PEXELS_API_KEY"]

    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        print(f"\n❌  Missing environment variable(s): {', '.join(missing)}")
        print("    Copy .env.example → .env and fill in the values.\n")
        sys.exit(1)


def _publish(story: dict, dry_run: bool, pexels_api_key: str, page_name: str,
             dry_run_output_dir: Path | None = None) -> bool:
    """Create image and post (or save locally for dry-run). Returns True on success."""
    print(f"📰  {story['title'][:70]}")
    print(f"    Category : {story['category']}")
    print(f"    Score    : {story['score']}/100")
    print(f"    Source   : {story['source']}")

    caption    = format_caption(story)
    brief_text = format_image_brief(story)

    print("🎨  Creating image…")
    image = create_post_image(
        title          = story["title"],
        brief_text     = brief_text,
        category       = story["category"],
        story          = story,
        pexels_api_key = pexels_api_key,
        page_name      = page_name,
    )

    if dry_run:
        output_dir = dry_run_output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / ("post.jpg" if dry_run_output_dir else "dry_run_output.jpg")
    else:
        image_path = Path(tempfile.gettempdir()) / f"football-{story['id']}.jpg"
    reel_path = (image_path.parent / "reel.mp4") if dry_run_output_dir else image_path.with_suffix(".mp4")
    try:
        save_image(image, image_path)
        if dry_run:
            print(f"    [DRY RUN] Image saved to {image_path} — skipping post upload.")
        else:
            print("[POST] Publishing normal post…")
            post_via_webhook(caption, image)
            print("[POST] Published successfully")
            mark_posted(story["id"])

        _run_reel_pipeline(caption, image_path, reel_path, dry_run)
        return True
    except Exception as exc:
        print(f"[POST] Failed: {exc}")
        print("[REEL] SKIPPED — normal post was not published")
        return False
    finally:
        if not dry_run:
            for path in (image_path, reel_path):
                path.unlink(missing_ok=True)


def _run_reel_pipeline(caption: str, image_path: Path, reel_path: Path, dry_run: bool) -> None:
    """The second half of the pipeline; errors never undo a successful post."""
    print("[REEL] Starting Reel pipeline…")
    try:
        print("[REEL] Asking Groq AI for mood…")
        mood = classify_mood(caption)
        print(f"[REEL] Mood: {mood}")
        song = select_song(mood)
        print(f"[REEL] Song: {song.relative_to(Path.cwd()) if song.is_relative_to(Path.cwd()) else song}")
        print("[REEL] Creating 10-second video…")
        if not create_reel(image_path, reel_path, song):
            raise RuntimeError("video generation failed")
        if dry_run:
            print(f"[REEL] [DRY RUN] Video saved to {reel_path}; upload skipped")
            return
        print("[REEL] Publishing…")
        post_reel_via_webhook(caption, str(reel_path))
        print("[REEL] Reel published successfully")
    except Exception as exc:
        print(f"[REEL] Failed: {exc}")
        print("[PIPELINE] Post succeeded, Reel failed")


def _publication_order(stories: list[dict]) -> list[dict]:
    """Newest first, to the nearest 5 minutes. Feeds timestamp to the second,
    so without the bucket a filler item that beat a major story into the window
    by 30s leads the run. Anything genuinely fresher still goes first — news
    must never queue behind a stale high scorer."""
    return sorted(stories, key=lambda s: (int(s["age_hours"] * 60) // 5, -s["score"]))


def run(dry_run: bool = False) -> int:
    validate_config(dry_run)

    pexels_api_key    = os.getenv("PEXELS_API_KEY", "")
    page_name         = os.getenv("PAGE_NAME", "FOOTBALL NEWS")
    breaking_threshold = _threshold()

    print(f"⚽  Football Page Bot starting… [threshold={breaking_threshold}]\n")

    print("🔍  Fetching latest football news…")
    stories = _gather(200)   # cap must exceed a day's supply or later feeds starve

    if not stories:
        print("    No stories found. Will retry next run.")
        return 0

    # Best first — but this order only decides what SURVIVES the [:20] and
    # budget cuts below, never what goes out first. Publication order is put
    # back to newest-first at `to_post`, so a story that has been sitting in
    # the window for two hours still cannot queue ahead of one that just
    # landed; it is simply no longer the story we keep when something must go.
    new_stories = [s for s in stories if not is_posted(s["id"])]
    new_stories.sort(key=lambda s: -s["score"])

    print(f"    Found {len(stories)} stories, {len(new_stories)} new.\n")

    if not new_stories:
        print("📭  No new stories to post.")
        return 0

    # Randomised delay range between consecutive posts (seconds)
    delay_min = int(os.getenv("POST_DELAY_MIN", "25"))
    delay_max = int(os.getenv("POST_DELAY_MAX", "35"))

    # Daily budget — hard cap across all runs (counter lives in posted_stories.json)
    max_per_day = int(os.getenv("MAX_POSTS_PER_DAY", "60"))
    min_per_day = int(os.getenv("MIN_POSTS_PER_DAY", "10"))
    budget      = max_per_day - posts_today()
    if budget <= 0:
        print(f"📭  Daily budget reached ({max_per_day} posts today). Next run tomorrow.")
        return 0
    print(f"    Daily budget: {budget} of {max_per_day} posts remaining.")

    # Keyword score is the only filter. Behind the daily minimum we lower the
    # bar in proportion to the shortfall — never to zero, which published the
    # feed's lock-screen promos and quiz pages under our own brand.
    threshold = relaxed_threshold(breaking_threshold, behind_pace(min_per_day))
    if threshold < breaking_threshold:
        print(f"    Behind pace for {min_per_day} posts/day — "
              f"threshold {breaking_threshold} → {threshold}.")

    shortlist = [s for s in new_stories if s["score"] >= threshold][:20]

    # Collapse retellings of one event. BBC lists some stories under two URLs,
    # so the id (a hash of the link) differs while the headline is identical —
    # that is what put the same match on the page more than once.
    deduped: list[dict] = []
    for s in shortlist:
        if any(same_event(s["title"], kept["title"]) for kept in deduped):
            mark_posted(s["id"], count=False)   # suppress without spending budget
            continue
        deduped.append(s)
    if len(deduped) < len(shortlist):
        print(f"    Collapsed {len(shortlist) - len(deduped)} duplicate retelling(s).")
    shortlist = deduped

    # Everything that survived the cuts goes out this run, not one per poll,
    # and in publication order — newest first (see _publication_order).
    # Match cards are time-critical and score a flat 55, so ranking by score
    # buried them behind news on a busy matchday. They take the budget first;
    # `_gather` only ever emits a handful and they are worthless once stale.
    cards = [s for s in shortlist if s["id"].startswith(("fixture-", "result-"))]
    rest  = [s for s in shortlist if s not in cards]
    to_post = _publication_order((cards + rest)[:budget])
    print(f"    Queued {len(to_post)} story(s) to post.\n")

    posted_count = 0
    for story in to_post:
        if posted_count > 0 and not dry_run:
            delay = random.uniform(delay_min, delay_max)
            print(f"⏱   Waiting {delay:.1f}s before next post…")
            time.sleep(delay)

        try:
            ok = _publish(story, dry_run, pexels_api_key, page_name)
            if ok:
                posted_count += 1
        except Exception as exc:
            print(f"❌  Error: {exc}\n")

    if posted_count == 0:
        print("\n📭  Nothing was posted this run.")
    else:
        print(f"\n🎉  Done — published {posted_count} post(s).")
    return posted_count


def _commit_state() -> None:
    """On GitHub Actions, push posted_stories.json after each post so state
    survives even if the long-running job is cancelled mid-flight."""
    if not os.getenv("GITHUB_ACTIONS"):
        return
    os.system(  # ponytail: best-effort; the workflow's final commit step is the backstop
        "git add posted_stories.json && "
        'git -c user.name="github-actions[bot]" '
        '-c user.email="github-actions[bot]@users.noreply.github.com" '
        'commit -m "chore: update posted stories [skip ci]" && '
        "git pull --rebase --autostash && git push"
    )


def daemon() -> None:
    """Listen continuously: poll the feeds every POLL_SECONDS, post fresh
    worthy news immediately. Exits after MAX_RUNTIME_MIN so the next
    scheduled GitHub Actions job can take over (24/7 via chained jobs)."""
    poll    = int(os.getenv("POLL_SECONDS", "60"))
    max_min = int(os.getenv("MAX_RUNTIME_MIN", "290"))
    start   = time.time()

    print(f"👂  Daemon mode: polling every {poll}s for {max_min} min "
          f"(MAX_POSTS_PER_DAY is the only brake)\n")

    while time.time() - start < max_min * 60:
        try:
            if run() > 0:
                _commit_state()
        except Exception as exc:
            print(f"❌  Poll error: {exc}")
        time.sleep(poll)

    print("👋  Runtime limit reached — exiting so the next job takes over.")


def _why(story: dict) -> None:
    """Print which terms produced this story's score, title and description apart.

    ponytail: opt-in behind --why instead of always on. The breakdown is 1-6
    extra lines per story, which buries the ranked list it is meant to explain.
    """
    title, desc = story["title"], story.get("description", "")
    title_score = score_story(title)
    # The description's //3 lands on its sum, not per term, so take the discount
    # straight from score_story rather than restating the divisor here.
    desc_score  = score_story(title, desc) - title_score

    rows = explain_story(title, desc)
    for source, header in (("title", f"title {title_score:>4}"),
                           ("desc",  f"desc  {desc_score:>+4} (//3 of "
                                     f"{max(0, sum(p for p, _, _, s in rows if s == 'desc'))}"
                                     f"{', clamped' if sum(p for p, _, _, s in rows if s == 'desc') < 0 else ''})")):
        terms = [f"{t} {p:+}" + (f" “{ph}”" if ph and ph != t else "")
                 for p, ph, t, s in rows if s == source]
        if terms:
            print(f"       {header}  =  " + ",  ".join(terms))


def preview(count: int = 15, why: bool = False) -> None:
    """Show upcoming stories ranked by score. No images created, nothing posted."""
    breaking_threshold = _threshold()

    print(f"⚽  Football Page Bot — PREVIEW MODE  (threshold={breaking_threshold})\n")
    print("🔍  Fetching latest football news…")
    stories = _gather(100)

    if not stories:
        print("    No stories found.")
        return

    stories.sort(key=lambda s: s["score"], reverse=True)
    new_stories     = [s for s in stories if not is_posted(s["id"])]
    posted_stories  = [s for s in stories if     is_posted(s["id"])]

    print(f"    {len(stories)} stories fetched — "
          f"{len(new_stories)} new, {len(posted_stories)} already posted.\n")

    shown = new_stories[:count]
    sep   = "─" * 72

    print(sep)
    print(f"  TOP {len(shown)} NEW STORIES  (sorted by score)\n")

    for i, story in enumerate(shown, 1):
        passes    = story["score"] >= breaking_threshold
        label     = "✅  WOULD POST NOW" if passes else "⏭   would skip (score too low)"
        filled    = min(10, story["score"] // 10)   # bar caps at 10 blocks
        score_bar = "█" * filled + "░" * (10 - filled)

        print(f"  #{i:>2}  [{score_bar}] {story['score']:>4}  {label}")
        print(f"       {story['title']}")
        print(f"       {story['category']}  ·  {story['source']}")
        if why:
            _why(story)
        print()

    would_post = sum(1 for s in new_stories if s["score"] >= breaking_threshold)
    print(sep)
    print(f"  {would_post} of {len(new_stories)} new stories would be posted right now.")
    if len(new_stories) > count:
        print(f"  Showing {count} of {len(new_stories)} — run  --preview {count + 15}  to see more.")
    print()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv

    if "--daemon" in sys.argv:
        daemon()
    elif "--preview" in sys.argv:
        idx = sys.argv.index("--preview")
        try:
            count = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            count = 15
        preview(count, why="--why" in sys.argv)
    else:
        run(dry_run=dry)
