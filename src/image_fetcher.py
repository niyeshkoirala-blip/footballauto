"""
Fetches the most relevant image for a football news story.

Priority:
  1. RSS article image  – editorial photo from the news publisher (story-specific, current)
  2. og:image           – Open Graph image from the article page (high-res, story-specific)
  3. TheSportsDB player – actual photo of the named player (free, no key)
  4. TheSportsDB team   – atmospheric stadium/team imagery (free, no key)
  5. Wikipedia player   – fallback player headshot (free, no key)
  6. Pexels             – generic football photo (free key required)
  7. None               – image_creator falls back to solid green field
"""

import json
import os
import random
import re
import time
import urllib.parse
from io import BytesIO

import requests
from PIL import Image

TSDB = "https://www.thesportsdb.com/api/v1/json/3"   # free public key

# ── Dynamic player cache ───────────────────────────────────────────────────────
_PLAYER_CACHE_FILE = "player_cache.json"
_PLAYER_CACHE_TTL  = 7 * 24 * 3600   # rebuild from TheSportsDB every 7 days
_player_cache_mem: list[str] | None = None   # in-memory cache for current run

# Top clubs whose full rosters we pull each refresh cycle
_TOP_CLUBS: list[str] = [
    "Manchester City", "Real Madrid", "FC Barcelona", "Bayern Munich",
    "Arsenal", "Chelsea", "Liverpool", "Manchester United",
    "Juventus", "Inter Milan", "AC Milan", "Napoli", "Atletico Madrid",
    "Paris Saint-Germain", "Borussia Dortmund", "Bayer Leverkusen",
    "Tottenham Hotspur", "Newcastle United", "Aston Villa",
    "Feyenoord", "Benfica", "Sporting CP", "Porto", "Ajax",
    "Celtic", "Rangers", "PSV Eindhoven", "Galatasaray", "Fenerbahce",
]


def _fetch_club_player_tokens(club_name: str) -> set[str]:
    """Return lowercased name tokens for every player currently at a club."""
    try:
        # Step 1: resolve club name → team ID
        r = requests.get(
            f"{TSDB}/searchteams.php",
            params={"t": club_name},
            timeout=8,
        )
        teams = r.json().get("teams") or []
        if not teams:
            return set()
        team_id = teams[0].get("idTeam")
        if not team_id:
            return set()

        # Step 2: fetch full squad
        r2 = requests.get(
            f"{TSDB}/lookup_all_players.php",
            params={"id": team_id},
            timeout=12,
        )
        players = r2.json().get("player") or []

        tokens: set[str] = set()
        for p in players:
            full = (p.get("strPlayer") or "").strip().lower()
            if not full:
                continue
            for part in full.split():
                # Keep only alphabetic tokens 4+ chars (filters initials, "de", "van")
                if len(part) >= 4 and part.isalpha():
                    tokens.add(part)
        return tokens
    except Exception:
        return set()


def get_known_player_tokens() -> list[str]:
    """
    Return a dynamically-built, cached list of player name tokens.

    On first call (or after 7 days) it queries TheSportsDB for the full
    squads of all top clubs and writes player_cache.json.
    Subsequent calls within the same process return the in-memory list;
    calls within 7 days load from the JSON file.
    This means new signings and emerging stars are picked up automatically
    on the next weekly refresh — no manual list maintenance needed.
    """
    global _player_cache_mem
    if _player_cache_mem is not None:
        return _player_cache_mem

    # Try loading a fresh file cache
    if os.path.exists(_PLAYER_CACHE_FILE):
        try:
            with open(_PLAYER_CACHE_FILE) as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < _PLAYER_CACHE_TTL:
                _player_cache_mem = data["players"]
                return _player_cache_mem
        except Exception:
            pass

    # Cache stale or missing — rebuild from TheSportsDB
    print("  [players] Refreshing player cache from TheSportsDB squad rosters…")
    all_tokens: set[str] = set(PLAYER_FULL_NAMES.keys())   # baseline always included

    for club in _TOP_CLUBS:
        tokens = _fetch_club_player_tokens(club)
        all_tokens.update(tokens)

    # Exclude generic football words that leak in as name tokens
    _noise = {
        "goalkeeper", "defender", "midfielder", "forward", "striker",
        "captain", "player", "football", "soccer", "manager", "coach",
        "club", "team", "sport", "league", "season", "transfer",
    }
    all_tokens -= _noise

    player_list = sorted(all_tokens)
    _player_cache_mem = player_list

    try:
        with open(_PLAYER_CACHE_FILE, "w") as f:
            json.dump({"ts": time.time(), "players": player_list}, f)
        print(f"  [players] Cached {len(player_list)} tokens — refreshes in 7 days")
    except Exception:
        pass

    return player_list

# ── Canonical player names used for API lookups ────────────────────────────────
PLAYER_FULL_NAMES: dict[str, str] = {
    "haaland":      "Erling Haaland",
    "mbappe":       "Kylian Mbappe",
    "vinicius":     "Vinicius Junior",
    "bellingham":   "Jude Bellingham",
    "salah":        "Mohamed Salah",
    "ronaldo":      "Cristiano Ronaldo",
    "messi":        "Lionel Messi",
    "de bruyne":    "Kevin De Bruyne",
    "rodri":        "Rodrigo Hernandez",
    "modric":       "Luka Modric",
    "kane":         "Harry Kane",
    "neymar":       "Neymar",
    "lewandowski":  "Robert Lewandowski",
    "benzema":      "Karim Benzema",
    "saka":         "Bukayo Saka",
    "foden":        "Phil Foden",
    "palmer":       "Cole Palmer",
    "rashford":     "Marcus Rashford",
    "odegaard":     "Martin Odegaard",
    "yamal":        "Lamine Yamal",
    "leao":         "Rafael Leao",
    "vlahovic":     "Dusan Vlahovic",
    "lautaro":      "Lautaro Martinez",
    "nunez":        "Darwin Nunez",
    "son":          "Son Heung-min",
    "dembele":      "Ousmane Dembele",
    "pedri":        "Pedri",
    "gavi":         "Gavi",
    "ter stegen":   "Marc-Andre ter Stegen",
    "alisson":      "Alisson Becker",
    "ederson":      "Ederson",
    "courtois":     "Thibaut Courtois",
    "neuer":        "Manuel Neuer",
    "van dijk":     "Virgil van Dijk",
    "trent":        "Trent Alexander-Arnold",
    "rooney":       "Wayne Rooney",
    "gerrard":      "Steven Gerrard",
}

# ── Canonical team names for API lookups ───────────────────────────────────────
TEAM_FULL_NAMES: dict[str, str] = {
    # Premier League
    "real madrid":          "Real Madrid",
    "barcelona":            "FC Barcelona",
    "atletico":             "Atletico Madrid",
    "manchester city":      "Manchester City",
    "manchester united":    "Manchester United",
    "liverpool":            "Liverpool",
    "arsenal":              "Arsenal",
    "chelsea":              "Chelsea",
    "tottenham":            "Tottenham Hotspur",
    "newcastle":            "Newcastle United",
    "aston villa":          "Aston Villa",
    "west ham":             "West Ham United",
    "brighton":             "Brighton & Hove Albion",
    "everton":              "Everton",
    "nottingham forest":    "Nottingham Forest",
    "brentford":            "Brentford",
    "fulham":               "Fulham",
    "crystal palace":       "Crystal Palace",
    "wolves":               "Wolverhampton Wanderers",
    "wolverhampton":        "Wolverhampton Wanderers",
    "bournemouth":          "AFC Bournemouth",
    "leicester":            "Leicester City",
    "ipswich":              "Ipswich Town",
    "southampton":          "Southampton",
    # La Liga
    "villarreal":           "Villarreal",
    "real sociedad":        "Real Sociedad",
    "real betis":           "Real Betis",
    "sevilla":              "Sevilla",
    "valencia":             "Valencia",
    "athletic bilbao":      "Athletic Club",
    "girona":               "Girona",
    "celta vigo":           "Celta Vigo",
    # Bundesliga
    "bayern":               "Bayern Munich",
    "dortmund":             "Borussia Dortmund",
    "leverkusen":           "Bayer Leverkusen",
    "rb leipzig":           "RB Leipzig",
    "eintracht frankfurt":  "Eintracht Frankfurt",
    "wolfsburg":            "VfL Wolfsburg",
    "stuttgart":            "VfB Stuttgart",
    # Serie A
    "juventus":             "Juventus",
    "inter milan":          "Inter Milan",
    "ac milan":             "AC Milan",
    "napoli":               "Napoli",
    "atalanta":             "Atalanta",
    "roma":                 "AS Roma",
    "lazio":                "Lazio",
    "fiorentina":           "Fiorentina",
    # Ligue 1
    "psg":                  "Paris Saint-Germain",
    "paris saint-germain":  "Paris Saint-Germain",
    "marseille":            "Olympique Marseille",
    "monaco":               "AS Monaco",
    "lyon":                 "Olympique Lyonnais",
    "lille":                "Lille OSC",
    # Other European clubs
    "ajax":                 "Ajax",
    "porto":                "FC Porto",
    "benfica":              "Benfica",
    "sporting":             "Sporting CP",
    "celtic":               "Celtic",
    "rangers":              "Rangers",
    "galatasaray":          "Galatasaray",
    "fenerbahce":           "Fenerbahce",
    "feyenoord":            "Feyenoord",
    "psv":                  "PSV Eindhoven",
    # National teams — Copa America (CONMEBOL)
    "brazil":               "Brazil",
    "argentina":            "Argentina",
    "uruguay":              "Uruguay",
    "colombia":             "Colombia",
    "chile":                "Chile",
    "ecuador":              "Ecuador",
    "peru":                 "Peru",
    "paraguay":             "Paraguay",
    "venezuela":            "Venezuela",
    "bolivia":              "Bolivia",
    # National teams — Copa America (CONCACAF)
    "usa":                  "United States",
    "united states":        "United States",
    "mexico":               "Mexico",
    "canada":               "Canada",
    "jamaica":              "Jamaica",
    "panama":               "Panama",
    "costa rica":           "Costa Rica",
    # National teams — Europe (Euros + qualifiers)
    "france":               "France",
    "england":              "England",
    "spain":                "Spain",
    "germany":              "Germany",
    "portugal":             "Portugal",
    "italy":                "Italy",
    "netherlands":          "Netherlands",
    "belgium":              "Belgium",
    "croatia":              "Croatia",
    "poland":               "Poland",
    "ukraine":              "Ukraine",
    "turkey":               "Turkey",
    "denmark":              "Denmark",
    "austria":              "Austria",
    "switzerland":          "Switzerland",
    "scotland":             "Scotland",
    "hungary":              "Hungary",
    "serbia":               "Serbia",
    "slovakia":             "Slovakia",
    "romania":              "Romania",
    "slovenia":             "Slovenia",
    "albania":              "Albania",
    "georgia":              "Georgia",
    "czech republic":       "Czech Republic",
    "wales":                "Wales",
    "sweden":               "Sweden",
    "norway":               "Norway",
    "greece":               "Greece",
    "ireland":              "Republic of Ireland",
}


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ── Low-level download helper ──────────────────────────────────────────────────

def _download(url: str, timeout: int = 15) -> Image.Image | None:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": _BROWSER_UA})
        if r.status_code == 200 and len(r.content) > 5_000:
            return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        pass
    return None


# ── Source 1: RSS article's own editorial image ───────────────────────────────

def _rss_article_image(story: dict) -> Image.Image | None:
    """
    Download the editorial image that came directly from the RSS feed.
    This is the journalist's chosen photo for the article — always current
    and story-specific (no 2022 archive shots for a 2026 story).
    """
    url = story.get("article_image", "").strip()
    if not url:
        return None
    img = _download(url)
    if img:
        print(f"    [RSS] Got editorial image from feed")
        return img
    return None


# ── Source 2: og:image from the article page ──────────────────────────────────

_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    re.IGNORECASE,
)


def _og_image(article_url: str) -> Image.Image | None:
    """
    Fetch the article page and extract its og:image meta tag.
    Works well for Guardian (~95%) and Sky Sports (~95%).
    BBC is handled by RSS thumbnail; ESPN returns 403.
    """
    if not article_url:
        return None
    try:
        r = requests.get(
            article_url,
            timeout=12,
            headers={
                "User-Agent": _BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if r.status_code == 200:
            m = _OG_IMAGE_RE.search(r.text)
            if m:
                url = m.group(1) or m.group(2)
                if url:
                    img = _download(url)
                    if img:
                        print(f"    [og:image] Got editorial image from article page")
                        return img
    except Exception as e:
        print(f"    [og:image] skipped ({e})")
    return None


# ── Source 3: TheSportsDB player photos ──────────────────────────────────────

def _tsdb_player(full_name: str) -> Image.Image | None:
    """Return the player's actual photo from TheSportsDB."""
    try:
        r = requests.get(
            f"{TSDB}/searchplayers.php",
            params={"p": full_name},
            timeout=10,
        )
        players = r.json().get("player") or []
        for p in players[:3]:
            for field in ("strThumb", "strCutout", "strRender"):
                url = p.get(field)
                if url and url.startswith("http"):
                    img = _download(url)
                    if img:
                        print(f"    [TheSportsDB] Got player photo: {full_name}")
                        return img
    except Exception as e:
        print(f"    [TheSportsDB] player lookup failed ({full_name}): {e}")
    return None


# ── Source 4: TheSportsDB team fan art ───────────────────────────────────────

def _tsdb_team(full_name: str) -> Image.Image | None:
    """Return a team fan-art / stadium image from TheSportsDB."""
    try:
        r = requests.get(
            f"{TSDB}/searchteams.php",
            params={"t": full_name},
            timeout=10,
        )
        teams = r.json().get("teams") or []
        for t in teams[:2]:
            for field in ("strFanart1", "strFanart2", "strFanart3",
                          "strFanart4", "strStadiumThumb"):
                url = t.get(field)
                if url and url.startswith("http"):
                    img = _download(url)
                    if img:
                        print(f"    [TheSportsDB] Got team image: {full_name}")
                        return img
    except Exception as e:
        print(f"    [TheSportsDB] team lookup failed ({full_name}): {e}")
    return None


# ── Source 5: Wikipedia player photo ─────────────────────────────────────────

def _wikipedia_player(full_name: str) -> Image.Image | None:
    """Return player photo from Wikipedia (free, no key)."""
    # Try common Wikipedia naming patterns
    variants = [
        full_name.replace(" ", "_"),
        full_name.replace(" ", "_") + "_(footballer)",
        full_name.split()[-1],   # last name only
    ]
    for title in variants:
        try:
            title_enc = urllib.parse.quote(title)
            r = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{title_enc}",
                timeout=10,
                headers={"User-Agent": "FootballBot/1.0"},
            )
            data = r.json()
            # Make sure it's actually about a footballer, not something else
            desc = (data.get("description") or "").lower()
            extract = (data.get("extract") or "").lower()
            if not any(w in desc + extract for w in
                       ["football", "soccer", "footballer", "midfielder",
                        "striker", "goalkeeper", "defender", "forward"]):
                continue
            thumb = (data.get("thumbnail") or {}).get("source")
            if thumb:
                img = _download(thumb)
                if img:
                    print(f"    [Wikipedia] Got player photo: {full_name}")
                    return img
        except Exception:
            continue
    return None


# ── Source 6: Pexels fallback ────────────────────────────────────────────────

def _pexels(queries: list[str], api_key: str) -> Image.Image | None:
    headers = {"Authorization": api_key}
    for query in queries:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": query, "per_page": 15, "orientation": "landscape"},
                timeout=15,
            )
            photos = r.json().get("photos", [])
            if photos:
                photo = random.choice(photos[:10])
                img = _download(photo["src"]["large"])
                if img:
                    print(f"    [Pexels] Got image for: {query!r}")
                    return img
        except Exception as e:
            print(f"    [Pexels] error ({query!r}): {e}")
    return None


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_story_image(story: dict, pexels_api_key: str = "") -> Image.Image | None:
    """
    Return the most accurate, most current image for this story.
    Falls back through sources until one works.
    """
    text = (story["title"] + " " + story.get("description", "")).lower()

    player_key = next((k for k in PLAYER_FULL_NAMES if k in text), None)
    team_key   = next((k for k in TEAM_FULL_NAMES   if k in text), None)

    # ── 1. RSS editorial image — journalist's own photo for this article ───────
    img = _rss_article_image(story)
    if img:
        return img

    # ── 2. og:image from article page — high-res, story-specific ─────────────
    img = _og_image(story.get("link", ""))
    if img:
        return img

    # ── 3. TheSportsDB — player photo ─────────────────────────────────────────
    if player_key:
        img = _tsdb_player(PLAYER_FULL_NAMES[player_key])
        if img:
            return img

    # ── 4. TheSportsDB — team fan art ─────────────────────────────────────────
    if team_key:
        img = _tsdb_team(TEAM_FULL_NAMES[team_key])
        if img:
            return img

    # ── 5. Wikipedia — player headshot ────────────────────────────────────────
    if player_key:
        img = _wikipedia_player(PLAYER_FULL_NAMES[player_key])
        if img:
            return img

    # ── 6. Pexels — generic football photo ────────────────────────────────────
    if pexels_api_key:
        img = _pexels(story.get("image_keywords", ["football match action"]),
                      pexels_api_key)
        if img:
            return img

    # ── 7. Solid fallback handled in image_creator ────────────────────────────
    print("    [image_fetcher] No image found — using solid fallback.")
    return None
