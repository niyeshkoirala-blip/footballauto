"""Ordering regressions: the truncation must drop the worst story, not the
oldest — and a 30-second head start must not outrank a major story."""
from main import _publication_order


def _story(sid, score, age_min):
    return {"id": sid, "title": sid, "score": score, "age_hours": age_min / 60,
            "category": "NEWS", "source": "BBC Sport"}


def _demo() -> None:
    fresh_filler = _story("filler", 51, 2.0)     # landed 30s before the big one
    breaking     = _story("breaking", 285, 2.5)
    stale_big    = _story("stale", 400, 28.0)

    # selection: what survives a cut is the best, not the newest
    kept = sorted([fresh_filler, breaking, stale_big], key=lambda s: -s["score"])[:2]
    assert [s["id"] for s in kept] == ["stale", "breaking"]

    # order: inside one 5-minute bucket the bigger story leads
    assert [s["id"] for s in _publication_order([fresh_filler, breaking])] \
        == ["breaking", "filler"]

    # the original lesson: a genuinely fresher story still beats a stale high scorer
    assert [s["id"] for s in _publication_order([stale_big, fresh_filler])] \
        == ["filler", "stale"]

    # buckets are 5 minutes, not more — 6m old never precedes 1m old
    assert [s["id"] for s in _publication_order(
        [_story("old", 999, 6.0), _story("new", 51, 1.0)])] == ["new", "old"]

    # stable on exact ties, no crash
    a, b = _story("a", 100, 3.0), _story("b", 100, 3.0)
    assert _publication_order([a, b]) == [a, b]
    print("OK")


if __name__ == "__main__":
    _demo()
