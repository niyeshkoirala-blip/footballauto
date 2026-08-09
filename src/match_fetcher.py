"""
Fixtures and results from ESPN's public scoreboard API.

Returns story dicts in the *same shape* as news_fetcher.fetch_news(), so they
ride the existing dedup → image → caption → webhook pipeline untouched.

Two kinds, each gated by a time window rather than by keyword score — a match
is newsworthy because of when it is, not because of what words are in it:

  fixture — kicks off within FIXTURE_WINDOW_HOURS
  result  — final whistle within RESULT_WINDOW_HOURS

ESPN over TheSportsDB (which image_fetcher uses for player photos): TSDB's free
tier returns exactly one event per league per call, so a 10-game matchday came
back as 1 game. ESPN needs no key and returns the full card. football-data.org
is complete too but wants a signup token.

No match photo comes back in the scoreboard payload, so article_image is left
empty and image_fetcher falls through to its TheSportsDB team art / Pexels
chain — team names in the headline are what it matches on.
"""

import os
import time
from datetime import datetime, timedelta, timezone

import requests

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"

# ESPN league slug → category name. These must match the keys in
# content_formatter.CATEGORY_HASHTAGS so match posts get the right tags.
LEAGUES = {
    "eng.1":          "Premier League",
    "esp.1":          "La Liga",
    "ger.1":          "Bundesliga",
    "ita.1":          "Serie A",
    "fra.1":          "Ligue 1",
    "uefa.champions": "Champions League",
}

CACHE_TTL = 600          # 10 min; 6 calls per refresh, the daemon polls every 60s
_cache: tuple[float, list] = (0.0, [])


def _fetch(league: str, date_range: str) -> list[dict]:
    """Every match for one league over a date range, tagged with its category."""
    try:
        r = requests.get(SCOREBOARD.format(league=league),
                         params={"dates": date_range}, timeout=15)
        events = r.json().get("events") or []
    except Exception as e:                     # network hiccup must not kill a poll
        print(f"  [match_fetcher] {league}: {e}")
        return []

    for event in events:
        event["_category"] = LEAGUES[league]
    return events


def _all_events(now: datetime) -> list[dict]:
    """Yesterday through tomorrow across every tracked league, cached."""
    global _cache
    if time.time() - _cache[0] < CACHE_TTL:
        return _cache[1]

    span   = "{}-{}".format((now - timedelta(days=1)).strftime("%Y%m%d"),
                            (now + timedelta(days=1)).strftime("%Y%m%d"))
    events = [e for league in LEAGUES for e in _fetch(league, span)]
    _cache = (time.time(), events)
    return events


def _sides(event: dict) -> tuple[dict, dict]:
    """(home, away) — ESPN does not guarantee the competitor order."""
    teams = event["competitions"][0]["competitors"]
    home  = next(t for t in teams if t["homeAway"] == "home")
    away  = next(t for t in teams if t["homeAway"] == "away")
    return home, away


def _story(event: dict, kind: str, age_hours: float) -> dict:
    category   = event["_category"]
    home, away = _sides(event)
    home_name  = home["team"]["displayName"]
    away_name  = away["team"]["displayName"]
    venue      = event["competitions"][0].get("venue", {}).get("fullName", "")
    where      = f" at {venue}" if venue else ""
    kickoff    = datetime.fromisoformat(event["date"])

    if kind == "result":
        home_goals, away_goals = int(home["score"]), int(away["score"])
        title = f"{home_name} {home['score']}-{away['score']} {away_name}"
        brief = f"Full time{where}. {category}."
        # 70 base + 5 a goal: a 4-3 thriller outranks a goalless draw
        score = 70 + 5 * (home_goals + away_goals)
        # Show whoever won. Picking off the headline alone gave the losing
        # side's celebration photo; a draw keeps the hosts.
        subject = away_name if away_goals > home_goals else home_name
    else:
        title   = f"{home_name} vs {away_name}"
        brief   = f"Kick-off {kickoff.strftime('%H:%M UTC')}{where}. {category}."
        score   = 55
        subject = home_name

    if category == "Champions League":
        score += 15

    return {
        "id":             f"{kind}-{event['id']}",
        "title":          title,
        "description":    brief,
        "link":           "",          # no article; skips the og:image lookup
        "source":         category,
        "category":       category,
        "published":      event["date"],
        "age_hours":      age_hours,
        "score":          score,
        "article_image":  "",          # see module docstring
        "image_subject":  subject,     # steers image_fetcher's team lookup
        "image_keywords": [f"{subject} football", f"{category} football",
                           "football match action"],
    }


def fetch_matches(now: datetime | None = None) -> list[dict]:
    """Matches worth posting right now: imminent kick-offs and fresh full-times."""
    now            = now or datetime.now(timezone.utc)
    result_window  = float(os.getenv("RESULT_WINDOW_HOURS", "3"))
    fixture_window = float(os.getenv("FIXTURE_WINDOW_HOURS", "2"))

    stories = []
    for event in _all_events(now):
        try:
            status  = event["competitions"][0]["status"]["type"]
            kickoff = datetime.fromisoformat(event["date"])
        except (KeyError, IndexError, ValueError):
            continue

        # 'in' is a live match — never post a running score as full time
        if status["state"] == "post" and status.get("completed"):
            # ESPN dates the event by kick-off, so add a match's worth of time
            ended = kickoff + timedelta(minutes=115)
            age   = (now - ended).total_seconds() / 3600
            if 0 <= age <= result_window:
                stories.append(_story(event, "result", age))

        elif status["state"] == "pre":
            # age_hours 0 keeps fixtures first in _publication_order;
            # main.run() also exempts these cards from the score cut.
            minutes_out = (kickoff - now).total_seconds() / 60
            if 0 <= minutes_out <= fixture_window * 60:
                stories.append(_story(event, "fixture", 0.0))

    return stories


def _demo() -> None:
    """Windowing and status handling are the whole filter, so that is what
    gets checked — plus one live call to catch a payload shape change."""
    global _cache
    now = datetime(2026, 5, 24, 18, 0, tzinfo=timezone.utc)

    def event(hours_from_now: float, state: str, home="0", away="0", **extra):
        return {
            "id": f"e{hours_from_now}", "_category": extra.pop("cat", "Premier League"),
            "date": (now + timedelta(hours=hours_from_now)).isoformat(),
            "competitions": [{
                "status": {"type": {"state": state, "completed": state == "post"}},
                "venue": {"fullName": "Emirates Stadium"},
                "competitors": [
                    {"homeAway": "away", "score": away, "team": {"displayName": "Leeds United"}},
                    {"homeAway": "home", "score": home, "team": {"displayName": "Arsenal"}},
                ],
            }],
            **extra,
        }

    _cache = (time.time(), [
        event(1.0,  "pre"),                       # kicks off in an hour → post
        event(9.0,  "pre"),                       # tonight, too far out → skip
        event(-4,   "post", "3", "0"),            # finished 2h ago → post
        event(-30,  "post", "1", "1"),            # finished yesterday → skip
        event(-1,   "in",   "2", "0"),            # live right now → skip
    ])
    got = {s["id"]: s for s in fetch_matches(now)}

    assert set(got) == {"fixture-e1.0", "result-e-4"}, sorted(got)
    fixture, result = got["fixture-e1.0"], got["result-e-4"]

    # away listed first above, so this also proves homeAway beats list order
    assert result["title"] == "Arsenal 3-0 Leeds United", result["title"]
    assert result["score"] == 70 + 5 * 3, result["score"]
    assert fixture["title"] == "Arsenal vs Leeds United"
    assert "19:00 UTC at Emirates Stadium" in fixture["description"]

    # Champions League bonus (same id as result-e-4, so check it on its own)
    _cache = (time.time(), [event(-4, "post", "1", "1", cat="Champions League")])
    assert fetch_matches(now)[0]["score"] == 70 + 5 * 2 + 15

    # The image must show whoever won, not whoever the headline mentions first.
    for home, away, expect in (("3", "0", "Arsenal"),        # hosts win
                               ("0", "3", "Leeds United"),   # visitors win
                               ("1", "1", "Arsenal")):       # draw keeps hosts
        _cache = (time.time(), [event(-4, "post", home, away)])
        story = fetch_matches(now)[0]
        assert story["image_subject"] == expect, (home, away, story["image_subject"])

    # …and image_fetcher must actually honour that over the headline. Both
    # sides here are in its team map; unmapped clubs (Leeds above) just fall
    # through to the Pexels keywords, which is why this uses Chelsea.
    from src.image_fetcher import TEAM_FULL_NAMES, _earliest
    beaten = {"title": "Arsenal 0-3 Chelsea", "image_subject": "Chelsea"}
    assert _earliest(TEAM_FULL_NAMES, beaten["title"].lower()) == "arsenal"   # the loser
    assert _earliest(TEAM_FULL_NAMES, beaten["image_subject"].lower()) == "chelsea"

    # Live: proves the ESPN payload still has the keys _story() reaches into
    _cache = (0.0, [])
    events = _all_events(datetime.now(timezone.utc))
    for e in events[:5]:
        _story(e, "fixture", 0.0)
    print(f"OK — {len(events)} live events across {len(LEAGUES)} leagues, "
          f"{len(fetch_matches())} in window now")


if __name__ == "__main__":
    _demo()
