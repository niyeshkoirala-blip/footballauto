#!/usr/bin/env python3
"""Run one randomly selected current article through the normal POST -> REEL flow."""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "result"
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


def run() -> int:
    dry_run = "--dry-run" in sys.argv
    main.validate_config(dry_run)
    stories = main._gather(200)
    if not stories:
        print("No available articles found for test run.")
        return 1
    story = random.choice(stories)
    print(f"[TEST] Random article selected: {story['title']}")
    print(f"[TEST] Saving generated artifacts to {RESULT_DIR}")
    return 0 if main._publish(
        story, dry_run, main.os.getenv("PEXELS_API_KEY", ""),
        main.os.getenv("PAGE_NAME", "FOOTBALL NEWS"), RESULT_DIR if dry_run else None,
    ) else 1


if __name__ == "__main__":
    raise SystemExit(run())
