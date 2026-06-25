"""
Persists a list of already-posted story IDs in posted_stories.json
so the bot never reposts the same news story.
"""

import json
import os

TRACKER_FILE = "posted_stories.json"
MAX_ENTRIES  = 1000   # keep file small; older IDs are evicted first


def _load() -> dict:
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f:
            return json.load(f)
    return {"posted": []}


def _save(tracker: dict) -> None:
    tracker["posted"] = tracker["posted"][-MAX_ENTRIES:]
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def is_posted(story_id: str) -> bool:
    return story_id in _load()["posted"]


def mark_posted(story_id: str) -> None:
    tracker = _load()
    if story_id not in tracker["posted"]:
        tracker["posted"].append(story_id)
    _save(tracker)
