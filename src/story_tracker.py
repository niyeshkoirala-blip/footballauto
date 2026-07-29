"""
Persists a list of already-posted story IDs in posted_stories.json
so the bot never reposts the same news story, plus a per-day post
counter so the daily budget (MAX_POSTS_PER_DAY) survives across runs.
"""

import json
import os
from datetime import datetime, timezone

TRACKER_FILE = "posted_stories.json"
MAX_ENTRIES  = 1000   # keep file small; older IDs are evicted first
DAILY_KEEP   = 3      # days of daily counters to retain


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load() -> dict:
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f:
            tracker = json.load(f)
            tracker.setdefault("daily", {})   # older files lack the key
            return tracker
    return {"posted": [], "daily": {}}


def _save(tracker: dict) -> None:
    tracker["posted"] = tracker["posted"][-MAX_ENTRIES:]
    # keep only the newest DAILY_KEEP day-counters
    tracker["daily"] = dict(sorted(tracker["daily"].items())[-DAILY_KEEP:])
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def is_posted(story_id: str) -> bool:
    return story_id in _load()["posted"]


def posts_today() -> int:
    return _load()["daily"].get(_today(), 0)


def behind_pace(min_per_day: int) -> bool:
    """True when today's count is behind the pro-rata pace needed to reach
    min_per_day by midnight UTC. The caller then drops the quality threshold
    so the daily minimum is still met on quiet news days."""
    now     = datetime.now(timezone.utc)
    elapsed = (now.hour * 60 + now.minute) / 1440
    return posts_today() < min_per_day * elapsed


def mark_posted(story_id: str, count: bool = True) -> None:
    """Record a story as seen. count=False suppresses it without spending
    daily budget — used for duplicate retellings we deliberately skip."""
    tracker = _load()
    if story_id not in tracker["posted"]:
        tracker["posted"].append(story_id)
        if count:
            tracker["daily"][_today()] = tracker["daily"].get(_today(), 0) + 1
    _save(tracker)


def _demo() -> None:
    import tempfile
    global TRACKER_FILE
    orig, TRACKER_FILE = TRACKER_FILE, os.path.join(tempfile.mkdtemp(), "t.json")
    try:
        assert posts_today() == 0
        mark_posted("a"); mark_posted("b")
        mark_posted("a")                      # duplicate — must not double-count
        assert posts_today() == 2
        assert is_posted("a") and not is_posted("c")
        # old day-counters get pruned
        t = _load(); t["daily"].update({"2000-01-01": 9, "2000-01-02": 9, "2000-01-03": 9})
        _save(t)
        assert "2000-01-01" not in _load()["daily"]
        assert posts_today() == 2
        assert behind_pace(1000)        # 2 posts is behind any sane pace
        assert not behind_pace(0)       # no minimum → never behind
        mark_posted("dup", count=False)               # suppressed, not published
        assert is_posted("dup") and posts_today() == 2
        print("OK")
    finally:
        TRACKER_FILE = orig


if __name__ == "__main__":
    _demo()
