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
"""

import os
import random
import sys
import tempfile
import time

from dotenv import load_dotenv

load_dotenv()

from src.news_fetcher      import fetch_news, same_event
from src.match_fetcher     import fetch_matches
from src.content_formatter import format_caption, format_image_brief
from src.image_creator     import create_post_image, save_image
from src.webhook_poster    import post_via_webhook
from src.graph_poster      import post_reel
from src.reel_creator      import create_reel
from src.story_tracker     import (behind_pace, is_posted, mark_posted,
                                   mark_reel, posts_today, reels_today)


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
    # Make.com is the only posting path now, so a missing webhook URL is fatal.
    # Checked at startup rather than at the first post, so the daemon dies
    # immediately instead of failing once a minute for five hours.
    required = ["PEXELS_API_KEY", "MAKE_WEBHOOK_URL"]
    if dry_run:
        required = ["PEXELS_API_KEY"]

    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        print(f"\n❌  Missing environment variable(s): {', '.join(missing)}")
        print("    Copy .env.example → .env and fill in the values.\n")
        sys.exit(1)


def _publish(story: dict, dry_run: bool, pexels_api_key: str, page_name: str) -> bool:
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
        out_path = "dry_run_output.jpg"
        save_image(image, out_path)
        print(f"    [DRY RUN] Image saved to {out_path} — skipping Facebook upload.")
        # Still build the reel so you can preview it
        print("🎬  Creating reel preview…")
        if create_reel(out_path, "dry_run_reel.mp4"):
            print("    [DRY RUN] Reel saved to dry_run_reel.mp4")
    elif not (_reel_wanted(story) and _publish_reel(caption, image)):
        print("📤  Posting to Facebook via Make.com…")
        print(f"✅  {post_via_webhook(caption, image)}\n")

    mark_posted(story["id"])
    return True


def _reel_wanted(story: dict) -> bool:
    """Reels out-reach photo posts, but only the strongest story of the day is
    worth the slot — and this needs a page token, since Make's free tier has no
    operations to spare for video."""
    if not (os.getenv("FB_PAGE_ID", "").strip()
            and os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()):
        return False
    return (reels_today() < int(os.getenv("REELS_PER_DAY", "2"))
            and story["score"] >= int(os.getenv("REEL_MIN_SCORE", "90")))


def _publish_reel(caption: str, image) -> bool:
    """Post the card as a Reel via the Graph API. False means the caller should
    fall back to a photo post rather than drop the story entirely."""
    tmp       = tempfile.gettempdir()
    reel_src  = os.path.join(tmp, "reel_source.jpg")
    reel_path = os.path.join(tmp, "reel.mp4")

    save_image(image, reel_src)
    print("🎬  Building reel…")
    if not create_reel(reel_src, reel_path):
        return False

    try:
        print("📤  Posting Reel to Facebook (Graph API — no Make ops)…")
        video_id = post_reel(caption, reel_path)
    except Exception as exc:
        print(f"    Reel failed: {exc}\n    Falling back to a photo post.")
        return False

    mark_reel()
    print(f"✅  Reel published (video {video_id})\n")
    return True


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

    # Newest first, strictly. Score decides *whether* a story is worth posting
    # (the threshold below); publication time decides the order. The daemon
    # re-polls every POLL_SECONDS, so a story that lands in the feed goes out
    # on the next poll — within the minute — rather than queueing behind a
    # higher-scoring item that has been sitting in the window for two hours.
    new_stories = [s for s in stories if not is_posted(s["id"])]
    new_stories.sort(key=lambda s: s["age_hours"])

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

    # Keyword score is the only filter. If we're behind the pace needed to hit
    # the daily minimum, drop the threshold and take the best available story.
    threshold = breaking_threshold
    if behind_pace(min_per_day):
        threshold = 0
        print(f"    Behind pace for {min_per_day} posts/day — threshold relaxed.")

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

    # Everything that qualifies goes out this run, not one per poll. Two
    # stories landing in the same minute both get queued here; the daily
    # budget is the only thing that trims the tail.
    to_post = shortlist[:budget]
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


def preview(count: int = 15) -> None:
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
        preview(count)
    else:
        run(dry_run=dry)
