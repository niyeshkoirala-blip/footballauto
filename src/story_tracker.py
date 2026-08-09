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
            tracker.setdefault("daily", {})   # older files lack the keys
            tracker.setdefault("reels", {})
            return tracker
    return {"posted": [], "daily": {}, "reels": {}}


def _save(tracker: dict) -> None:
    tracker["posted"] = tracker["posted"][-MAX_ENTRIES:]
    # keep only the newest DAILY_KEEP day-counters
    for counter in ("daily", "reels"):
        tracker[counter] = dict(sorted(tracker[counter].items())[-DAILY_KEEP:])
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def is_posted(story_id: str) -> bool:
    return story_id in _load()["posted"]


def posts_today() -> int:
    return _load()["daily"].get(_today(), 0)


def behind_pace(min_per_day: int) -> float:
    """How far today's count has fallen behind the pro-rata pace needed to
    reach min_per_day by midnight UTC, as a fraction of the whole day's quota:
    0.0 = on pace, 1.0 = nothing posted all day. A bare bool threw away the
    only number the caller needs — how *badly* we are behind. 0.0 is falsy, so
    `if behind_pace(...)` still reads the same."""
    if min_per_day <= 0:
        return 0.0
    now     = datetime.now(timezone.utc)
    elapsed = (now.hour * 60 + now.minute) / 1440
    return max(0.0, elapsed - posts_today() / min_per_day)


def relaxed_threshold(base: int, deficit: float) -> int:
    """Quality bar lowered in proportion to `deficit`, never past
    RELAX_FLOOR_PCT of base. Filler published under the page's own brand costs
    more than the post it replaces, so the floor is not negotiable — set
    RELAX_FLOOR_PCT=100 to disable relaxation, 0 for the old free-for-all."""
    try:
        pct = min(100, max(0, int(os.getenv("RELAX_FLOOR_PCT", "80"))))
    except ValueError:                  # a typo must not take the daemon down
        pct = 80
    floor = base * pct // 100
    # min(base, ...) because a negative deficit would otherwise raise the bar.
    return min(base, max(floor, round(base - deficit * (base - floor))))


def reels_today() -> int:
    return _load()["reels"].get(_today(), 0)


def mark_reel() -> None:
    """Reels are counted separately from photo posts — a reel spends a slot in
    both budgets, but REELS_PER_DAY is the tighter of the two."""
    tracker = _load()
    tracker["reels"][_today()] = tracker["reels"].get(_today(), 0) + 1
    _save(tracker)


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
        assert behind_pace(0) == 0.0    # no minimum → never behind (still falsy)
        deficit = behind_pace(1000)     # graded now, not a bool
        assert isinstance(deficit, float) and 0.0 <= deficit < 1.0

        # Relaxation is proportional and floored (floor = 60% of 50 = 30)
        os.environ["RELAX_FLOOR_PCT"] = "60"
        assert relaxed_threshold(50, 0.0) == 50    # on pace        → full bar
        assert relaxed_threshold(50, 0.1) == 48    # barely behind  → barely relaxed
        assert relaxed_threshold(50, 0.5) == 40    # half a day short
        assert relaxed_threshold(50, 1.0) == 30    # nothing all day → floor
        assert relaxed_threshold(50, 9.9) == 30    # never below the floor
        mark_posted("dup", count=False)               # suppressed, not published
        assert is_posted("dup") and posts_today() == 2

        # Reels count on their own budget, and never disturb the post counter
        assert reels_today() == 0
        mark_reel(); mark_reel()
        assert reels_today() == 2 and posts_today() == 2
        t = _load(); t["reels"].update({"2000-01-01": 9, "2000-01-02": 9, "2000-01-03": 9})
        _save(t)
        assert "2000-01-01" not in _load()["reels"]   # pruned like daily
        print("OK")
    finally:
        TRACKER_FILE = orig


if __name__ == "__main__":
    _demo()
