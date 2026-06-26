#!/usr/bin/env python3
"""
Automatic Football Facebook Page Bot
─────────────────────────────────────
Fetches the latest football news, creates a branded post image,
and publishes it to a Facebook Page — all using free services.

Usage:
  python main.py                  # breaking-news mode: only post if score ≥ BREAKING_THRESHOLD
  python main.py --scheduled      # scheduled mode: post best new story regardless of score
  python main.py --dry-run        # fetch + score + create image; skip Facebook upload
  python main.py --scheduled --dry-run
  python main.py --preview        # show top 15 stories with scores; no posting, no images
  python main.py --preview 30     # same but show top 30
"""

import os
import random
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from src.news_fetcher      import fetch_news
from src.content_formatter import format_caption, format_image_brief
from src.image_creator     import create_post_image, save_image
from src.facebook_poster   import post_to_facebook, post_reel_to_facebook
from src.reel_creator      import create_reel
from src.story_tracker     import is_posted, mark_posted


def validate_config(dry_run: bool) -> None:
    required = ["FB_PAGE_URL", "PEXELS_API_KEY"]
    if dry_run:
        required = ["PEXELS_API_KEY"]

    missing = [k for k in required if not os.getenv(k, "").strip()]
    if missing:
        print(f"\n❌  Missing environment variable(s): {', '.join(missing)}")
        print("    Copy .env.example → .env and fill in the values.\n")
        sys.exit(1)


def _publish(story: dict, dry_run: bool, pexels_api_key: str,
             page_name: str, fb_page_id: str, fb_access_token: str) -> bool:
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
    else:
        print("📤  Posting to Facebook…")
        post_id = post_to_facebook(caption, image, fb_page_id, fb_access_token)
        print(f"✅  Posted! Post ID: {post_id}\n")

        # Reel posting disabled for now

    mark_posted(story["id"])
    return True


def run(dry_run: bool = False, scheduled: bool = False) -> None:
    validate_config(dry_run)

    fb_page_id        = os.getenv("FB_PAGE_ID", "")
    fb_access_token   = os.getenv("FB_ACCESS_TOKEN", "")
    pexels_api_key    = os.getenv("PEXELS_API_KEY", "")
    page_name         = os.getenv("PAGE_NAME", "FOOTBALL NEWS")
    posts_per_run     = int(os.getenv("POSTS_PER_RUN", "1"))
    breaking_threshold = int(os.getenv("BREAKING_THRESHOLD", "60"))

    mode = "scheduled" if scheduled else f"breaking-news (threshold={breaking_threshold})"
    print(f"⚽  Football Page Bot starting… [{mode}]\n")

    print("🔍  Fetching latest football news…")
    stories = fetch_news(max_stories=50)

    if not stories:
        print("    No stories found. Will retry next run.")
        return

    # Filter to unseen stories only, sorted by score descending
    new_stories = [s for s in stories if not is_posted(s["id"])]
    new_stories.sort(key=lambda s: s["score"], reverse=True)

    print(f"    Found {len(stories)} stories, {len(new_stories)} new.\n")

    if not new_stories:
        print("📭  No new stories to post.")
        return

    # Randomised delay range between consecutive posts (seconds)
    delay_min = int(os.getenv("POST_DELAY_MIN", "25"))
    delay_max = int(os.getenv("POST_DELAY_MAX", "35"))

    # Only post stories that meet the threshold
    to_post = [s for s in new_stories
               if s["score"] >= breaking_threshold][:posts_per_run]

    print(f"    Selected {len(to_post)} stories above threshold={breaking_threshold}.\n")

    posted_count = 0
    for story in to_post:
        if posted_count > 0 and not dry_run:
            delay = random.uniform(delay_min, delay_max)
            print(f"⏱   Waiting {delay:.1f}s before next post…")
            time.sleep(delay)

        try:
            ok = _publish(story, dry_run, pexels_api_key,
                          page_name, fb_page_id, fb_access_token)
            if ok:
                posted_count += 1
        except Exception as exc:
            print(f"❌  Error: {exc}\n")

    if posted_count == 0:
        print("\n📭  Nothing was posted this run.")
    else:
        print(f"\n🎉  Done — published {posted_count} post(s).")


def preview(count: int = 15) -> None:
    """Show upcoming stories ranked by score. No images created, nothing posted."""
    breaking_threshold = int(os.getenv("BREAKING_THRESHOLD", "55"))

    print(f"⚽  Football Page Bot — PREVIEW MODE  (threshold={breaking_threshold})\n")
    print("🔍  Fetching latest football news…")
    stories = fetch_news(max_stories=100)

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
    dry       = "--dry-run"   in sys.argv
    scheduled = "--scheduled" in sys.argv

    if "--preview" in sys.argv:
        idx = sys.argv.index("--preview")
        try:
            count = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            count = 15
        preview(count)
    else:
        run(dry_run=dry, scheduled=scheduled)
