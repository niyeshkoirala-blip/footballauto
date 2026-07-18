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


def mark_posted(story_id: str) -> None:
    tracker = _load()
    if story_id not in tracker["posted"]:
        tracker["posted"].append(story_id)
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
        print("OK")
    finally:
        TRACKER_FILE = orig


if __name__ == "__main__":
    _demo()
