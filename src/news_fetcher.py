import re
import hashlib
import feedparser

# ── Breaking-news significance scoring ────────────────────────────────────────
# Each tuple: (list of trigger phrases, points awarded)
# Score is capped at 100. Threshold for immediate posting is set via
# BREAKING_THRESHOLD env var (default 60).

# ── All clubs from the top 5 leagues + major European/international sides ──────
_MAJOR_TEAMS: list[str] = [
    # Premier League (all 20 current + common alternates)
    "arsenal", "chelsea", "liverpool", "manchester city", "manchester united",
    "tottenham", "spurs", "newcastle", "aston villa", "west ham", "brighton",
    "everton", "nottingham forest", "brentford", "fulham", "crystal palace",
    "wolves", "wolverhampton", "bournemouth", "leicester", "ipswich", "southampton",
    "luton", "burnley", "sheffield united", "sheffield wednesday", "leeds",
    "sunderland", "middlesbrough", "coventry", "watford", "millwall",
    # La Liga (all 20 + alternates)
    "real madrid", "barcelona", "atletico madrid", "athletic bilbao", "athletic club",
    "villarreal", "real sociedad", "real betis", "sevilla", "valencia", "girona",
    "getafe", "celta vigo", "rayo vallecano", "osasuna", "alaves", "mallorca",
    "las palmas", "leganes", "espanyol", "valladolid", "deportivo", "racing santander",
    # Bundesliga (all 18 + alternates)
    "bayern munich", "bayer leverkusen", "rb leipzig", "borussia dortmund",
    "eintracht frankfurt", "vfb stuttgart", "sc freiburg", "wolfsburg",
    "werder bremen", "mainz", "augsburg", "hoffenheim", "monchengladbach",
    "borussia monchengladbach", "union berlin", "st. pauli", "holstein kiel",
    "heidenheim", "bochum", "hamburger", "schalke", "hertha berlin",
    # Serie A (all 20 + alternates)
    "inter milan", "ac milan", "juventus", "napoli", "atalanta", "roma", "as roma",
    "lazio", "fiorentina", "bologna", "torino", "genoa", "monza", "lecce",
    "udinese", "como", "empoli", "cagliari", "hellas verona", "parma", "venezia",
    "salernitana", "frosinone", "cremonese", "sassuolo",
    # Ligue 1 (all 18 + alternates)
    "psg", "paris saint-germain", "monaco", "as monaco", "marseille",
    "olympique marseille", "lyon", "olympique lyonnais", "brest", "rennes",
    "stade rennais", "reims", "strasbourg", "toulouse", "nantes", "le havre",
    "montpellier", "auxerre", "angers", "saint-etienne", "lens", "nice",
    "lorient", "metz", "clermont", "troyes",
    # Notable European clubs (UCL regulars + big names)
    "porto", "fc porto", "benfica", "sporting", "sporting cp", "ajax",
    "psv eindhoven", "psv", "club bruges", "anderlecht", "celtic", "rangers",
    "red bull salzburg", "galatasaray", "fenerbahce", "besiktas", "trabzonspor",
    "shakhtar", "dynamo kyiv", "red star belgrade", "feyenoord", "vitesse",
    "braga", "paok", "olympiakos", "panathinaikos", "ferencvaros",
    "rapid vienna", "sturm graz", "slavia prague", "sparta prague",
    "viktoria plzen", "lazio rome", "lech poznan", "legia warsaw",
    "rosenborg", "molde", "malmo", "aik", "ifk gothenburg",
    "zenit", "cska moscow", "spartak moscow", "locomotiv moscow",
    # Copa America — CONMEBOL
    "brazil", "argentina", "uruguay", "colombia", "chile", "ecuador",
    "peru", "bolivia", "paraguay", "venezuela",
    # Copa America — CONCACAF invitees
    "usa", "united states", "mexico", "canada", "jamaica", "panama",
    "costa rica", "honduras", "el salvador", "trinidad",
    # European Championship + World Cup nations
    "france", "england", "spain", "germany", "portugal", "italy",
    "netherlands", "belgium", "croatia", "poland", "ukraine", "turkey",
    "denmark", "austria", "switzerland", "scotland", "hungary", "serbia",
    "slovakia", "romania", "slovenia", "albania", "georgia", "czech republic",
    "czechia", "wales", "sweden", "norway", "greece", "russia",
    "finland", "northern ireland", "republic of ireland", "ireland",
    "israel", "armenia", "azerbaijan", "kazakhstan", "iceland",
    "north macedonia", "kosovo", "bosnia", "montenegro", "luxembourg",
    # Africa / Asia / rest of world (for international tournaments)
    "senegal", "nigeria", "ghana", "ivory coast", "morocco", "egypt",
    "south africa", "cameroon", "mali", "tunisia", "algeria",
    "japan", "south korea", "iran", "saudi arabia", "australia",
    "qatar", "uae", "china", "india",
]

_BREAKING_SIGNALS: list[tuple[list[str], int]] = [

    # ── CONFIRMED TRANSFERS & SIGNINGS (~60 phrases) ──────────────────────────
    (["has signed", "officially signed", "signs for", "sign for",
      "completes move", "completes transfer", "completes switch",
      "deal done", "done deal", "transfer confirmed", "transfer complete",
      "transfer completed", "move confirmed", "move completed",
      "joins", "joins on", "moves to", "switches to",
      "confirmed signing", "signing confirmed", "official signing",
      "unveiled", "unveiled as", "officially unveiled",
      "agrees personal terms", "agrees terms", "personal terms agreed",
      "medical completed", "passed medical", "undergoes medical",
      "medical done", "medical passed", "subject to medical",
      "puts pen to paper", "pen to paper", "ink on contract",
      "contract signed", "signs contract", "new contract signed",
      "announced signing", "officially announced", "official announcement",
      "new signing", "new recruit", "first signing", "latest signing",
      "seals move", "seals transfer", "seals deal", "seals signing",
      "secures signing", "wraps up signing", "wraps up deal",
      "lands", "snaps up", "swoops for", "clinches signing",
      "ties down", "loaned out", "loan confirmed", "loan completed",
      "loan deal", "loan move", "loan signing", "returns on loan",
      "permanent deal", "permanent transfer", "permanent switch",
      "rejoins", "re-signs", "returns to",
      "option to buy", "obligation to buy", "buy option triggered",
      "bumper deal", "long-term deal", "five-year deal", "four-year deal",
      "three-year deal", "two-year deal"], 40),

    # ── BIG MONEY / RECORD FEES (~50 phrases) ─────────────────────────────────
    (["world record", "record fee", "record transfer", "record deal",
      "british record", "club record", "most expensive",
      "highest fee ever", "largest fee", "biggest fee",
      "nine-figure", "eight-figure", "seven-figure",
      "mega deal", "mega money", "blockbuster deal", "eye-watering fee",
      "£50m", "£60m", "£70m", "£80m", "£90m", "£100m", "£110m",
      "£120m", "£130m", "£140m", "£150m", "£180m", "£200m",
      "€50m", "€60m", "€70m", "€80m", "€90m", "€100m", "€110m",
      "€120m", "€130m", "€150m", "€180m", "€200m", "€220m",
      "$50m", "$80m", "$100m", "$120m", "$150m", "$200m",
      "50 million", "60 million", "70 million", "80 million",
      "100 million", "150 million", "200 million",
      "release clause", "buyout clause", "activated clause"], 25),

    # ── TROPHY / TITLE MOMENTS (~60 phrases) ──────────────────────────────────
    (["wins the title", "wins title", "wins league", "wins the league",
      "wins the cup", "wins cup", "wins trophy", "wins the trophy",
      "claims title", "claims the title", "claims trophy",
      "title win", "title victory", "title triumph", "title clinched",
      "league winners", "cup winners", "trophy winners",
      "are champions", "crowned champions", "crowned as champions",
      "lifts the trophy", "lifts the cup", "lifts the title",
      "lifts trophy", "raises trophy", "collects trophy",
      "clinches title", "clinches league", "clinches the double",
      "clinches treble", "secures title", "seals title", "wraps up title",
      "retains title", "defends title", "defends successfully",
      "back-to-back", "three-peat", "four in a row",
      "successive title", "consecutive title", "consecutive win",
      "double winners", "treble winners", "quadruple",
      "historic win", "historic victory", "makes history", "creates history",
      "glory", "triumph", "triumphant", "victorious", "glorious",
      "perfect season", "unbeaten season", "invincible",
      "domestic title", "european title", "world champions",
      "ballon d'or", "golden boot", "player of the year",
      "manager of the year", "golden glove", "best player",
      "top scorer", "pichichi", "capocannoniere",
      "champions!", "title!", "glory!", "trophy!"], 35),

    # ── MANAGER / COACHING CHANGES (~60 phrases) ───────────────────────────────
    (["sacked", "fired", "dismissed", "axed", "relieved of duties",
      "shown the door", "let go", "parted ways", "mutual consent",
      "departure confirmed", "leaves the club", "exit confirmed",
      "out as manager", "out as coach", "manager leaves", "coach leaves",
      "head coach leaves", "boss leaves", "quits", "quit",
      "resigns", "resigned", "steps down", "steps aside",
      "walks away", "leaves by mutual consent",
      "appointed", "named as manager", "named head coach",
      "named as head coach", "named as boss", "new manager",
      "new head coach", "new boss", "new gaffer",
      "takes charge", "takes over", "in charge",
      "interim manager", "caretaker manager", "permanent manager",
      "coaching change", "managerial change", "management change",
      "replaces", "succeeds", "takes the reins",
      "under new management", "new era at", "revolution at",
      "press conference", "unveiled as manager", "signs as manager",
      "assistant manager appointed", "coaching staff changed",
      "director of football", "sporting director appointed",
      "technical director", "new backroom staff",
      "manager search over", "manager search", "seeking new manager",
      "new contract as manager", "extends as manager"], 35),

    # ── INJURIES, HEALTH & SUSPENSIONS (~80 phrases) ───────────────────────────
    (["ruled out", "ruled out for", "out for", "sidelined",
      "sidelined for", "season-ending", "career-threatening",
      "long-term injury", "serious injury", "significant injury",
      "lengthy absence", "lengthy spell out", "extended absence",
      "several months out", "months out", "weeks out", "month out",
      "indefinitely", "return date unknown",
      "hamstring injury", "hamstring problem", "hamstring strain",
      "knee injury", "knee problem", "knee surgery",
      "ankle injury", "ankle problem", "ankle surgery",
      "groin injury", "groin strain", "groin problem",
      "calf injury", "calf strain", "calf problem",
      "thigh injury", "thigh strain", "quad injury",
      "muscle injury", "muscle tear", "muscle strain",
      "back injury", "back problem", "back surgery",
      "hip injury", "shoulder injury", "shoulder surgery",
      "head injury", "concussion", "facial injury",
      "fractured", "fracture", "broken bone", "broken leg",
      "broken arm", "broken nose", "broken rib", "broken ankle",
      "dislocated", "torn ligament", "ligament damage", "ligament tear",
      "cruciate ligament", "acl tear", "torn acl", "acl injury",
      "mcl injury", "meniscus", "hernia",
      "surgery required", "undergoes surgery", "operation",
      "recovering from surgery", "post-surgery",
      "fitness doubt", "fitness concern", "fitness test",
      "failed fitness test", "misses match", "miss out",
      "banned for", "suspended for", "ban confirmed",
      "three-match ban", "five-match ban", "ten-match ban",
      "lifetime ban", "doping ban", "drugs ban",
      "tested positive", "failed drug test",
      "retrospective ban", "appeal ban",
      "red card", "sent off", "second yellow", "straight red",
      "violent conduct", "headbutt"], 30),

    # ── KNOCKOUT STAGES & COMPETITIONS (~60 phrases) ───────────────────────────
    (["final", "cup final", "league final", "grand final",
      "semi-final", "semifinals", "last four",
      "quarter-final", "quarterfinals", "last eight",
      "last 16", "round of 16", "last 32", "round of 32",
      "last 64", "group stage exit", "group stage elimination",
      "knocked out", "knocked out of", "knock out",
      "eliminated", "eliminate", "crash out", "crashes out",
      "bows out", "bow out", "exit",
      "advance to", "advances to", "progress to", "progresses to",
      "through to", "qualify for", "qualifies for", "qualification",
      "reaches the final", "reach the final", "into the final",
      "makes the final", "makes it to the final",
      "play-off", "playoff", "playoff final", "playoff winner",
      "fa cup", "carabao cup", "efl cup", "community shield",
      "copa del rey", "dfb-pokal", "coppa italia", "coupe de france",
      "supercopa", "supercoppa", "super cup", "club world cup",
      "intercontinental cup", "champions trophy",
      "afcon", "african cup", "gold cup", "concacaf gold cup",
      "u21 championship", "u23 championship",
      "world cup qualifier", "world cup qualifying",
      "european qualifier", "euro qualifier"], 25),

    # ── MATCH RESULTS (~80 phrases) ────────────────────────────────────────────
    (["beats", "beat", "beaten", "defeated", "defeats",
      "won", "win", "victory", "wins match", "wins game",
      "draws with", "drew", "draw", "stalemate", "goalless draw",
      "nil-nil", "all square", "share spoils", "share the points",
      "held to a draw", "held by",
      "equalises", "equalizer", "equalised",
      "thrash", "thrashes", "hammers", "hammer",
      "rout", "routed", "routing",
      "demolish", "demolishes", "demolished",
      "crush", "crushes", "crushed",
      "destroy", "destroys", "destroyed",
      "outclass", "outclasses", "outclassed",
      "overpower", "overpowers", "overpowered",
      "edge", "edges", "edged",
      "pip", "pips", "pipped",
      "snatch", "snatches", "snatched",
      "claim", "claims point", "claims all three points",
      "thumping win", "convincing win", "comfortable win",
      "narrow win", "hard-fought win",
      "last-minute winner", "late winner", "injury-time winner",
      "stoppage-time winner", "winner in injury time",
      "comeback win", "comeback victory", "stunning comeback",
      "penalty shootout", "on penalties", "won on penalties",
      "lost on penalties", "extra time", "aet",
      "five-star", "six-star", "seven-star",
      "clean sheet", "shutout", "kept clean sheet",
      "match report", "full-time result", "full time",
      "final score", "ft:", "result:"], 25),

    # ── IN-MATCH ACTION & GOALS (~70 phrases) ──────────────────────────────────
    (["scores", "scored", "goal", "goals",
      "leads", "lead", "takes the lead", "go ahead",
      "opener", "opens the scoring", "breaks the deadlock",
      "levels", "levelled", "equalises", "pulls level",
      "puts", "pounces", "taps in", "slots in",
      "finishes", "strikes", "fires", "blasts",
      "curls", "chips", "lobs", "flicks",
      "volley", "half-volley", "overhead kick", "bicycle kick",
      "header", "powerful header", "diving header",
      "screamer", "thunderbolt", "worldie", "wonder goal",
      "long-range", "long-range effort", "long-range strike",
      "close range", "tap-in", "rebound",
      "deflected", "deflection", "lucky goal",
      "assist", "assisted", "set up", "provided assist",
      "through ball", "through-ball",
      "free kick", "direct free kick", "indirect free kick",
      "free-kick goal", "free kick goal",
      "penalty", "spot kick", "penalty converted",
      "penalty saved", "penalty missed", "penalty stopped",
      "penalty retaken", "saved", "keeper saves",
      "own goal", "own-goal",
      "keeper error", "goalkeeper error", "howler", "blunder",
      "hat-trick", "brace", "double", "treble", "four goals",
      "five goals",
      "var", "var check", "var overturns", "var review",
      "goal given", "goal disallowed", "disallowed goal",
      "offside", "handball decision", "check complete"], 20),

    # ── MAJOR COMPETITION NAMES (~55 phrases) ──────────────────────────────────
    (["champions league", "ucl", "uefa champions league",
      "europa league", "uel", "conference league", "uecl",
      "premier league", "epl", "english premier league",
      "la liga", "laliga", "spanish league",
      "bundesliga", "german bundesliga", "german league",
      "serie a", "italian serie a", "italian league",
      "ligue 1", "ligue1", "french ligue 1", "french league",
      "world cup", "fifa world cup", "world cup 2026",
      "world cup qualifying", "world cup qualifier",
      "euro 2024", "euro 2025", "euro 2026", "euros",
      "european championship", "european championships",
      "copa america", "conmebol copa america",
      "nations league", "uefa nations league",
      "afcon", "africa cup of nations", "african cup",
      "asian cup", "afc asian cup",
      "gold cup", "concacaf gold cup",
      "copa libertadores", "copa sudamericana",
      "olympic football", "olympic qualifier",
      "women's world cup", "women's champions league",
      "women's euro", "women's super league", "wsl",
      "fa cup", "carabao cup", "efl cup",
      "copa del rey", "dfb-pokal", "coppa italia",
      "coupe de france", "community shield",
      "club world cup", "intercontinental cup",
      "super cup", "supercopa", "supercoppa",
      "mls cup", "saudi pro league", "j-league"], 20),

    # ── MAJOR LEAGUE TEAM MENTIONED ───────────────────────────────────────────
    (_MAJOR_TEAMS, 20),

    # ── TOP PLAYERS (~80 names) ───────────────────────────────────────────────
    (["mbappe", "haaland", "bellingham", "vinicius", "vinicius jr",
      "salah", "ronaldo", "cristiano", "messi", "lionel messi",
      "de bruyne", "kevin de bruyne", "rodri", "kane", "harry kane",
      "lewandowski", "robert lewandowski", "modric", "luka modric",
      "benzema", "karim benzema", "saka", "bukayo saka",
      "yamal", "lamine yamal", "pedri", "gavi",
      "ter stegen", "alisson", "ederson", "courtois",
      "neuer", "oblak", "donnarumma",
      "van dijk", "virgil van dijk", "trent", "trent alexander-arnold",
      "son", "son heung-min", "rashford", "marcus rashford",
      "foden", "phil foden", "palmer", "cole palmer",
      "neymar", "dembele", "ousmane dembele",
      "osimhen", "victor osimhen", "lukaku", "romelu lukaku",
      "vlahovic", "dusan vlahovic", "dybala", "paulo dybala",
      "chiesa", "federico chiesa", "pulisic", "christian pulisic",
      "theo hernandez", "maignan", "mike maignan",
      "kimmich", "joshua kimmich", "musiala", "jamal musiala",
      "wirtz", "florian wirtz", "gnabry", "sane", "leroy sane",
      "szoboszlai", "dominik szoboszlai",
      "kvaratskhelia", "kvara", "khvicha kvaratskhelia",
      "calhanoglu", "hakan calhanoglu", "barella", "nicolo barella",
      "goretzka", "muller", "thomas muller",
      "mac allister", "alexis mac allister",
      "gravenberch", "ryan gravenberch",
      "diaz", "luis diaz", "gakpo", "cody gakpo",
      "nunez", "darwin nunez", "watkins", "ollie watkins",
      "isak", "alexander isak", "gordon", "anthony gordon",
      "martinelli", "gabriel martinelli",
      "rice", "declan rice", "havertz", "kai havertz",
      "odegaard", "martin odegaard",
      "griezmann", "antoine griezmann",
      "thuram", "marcus thuram",
      "dimarco", "federico dimarco",
      "caicedo", "moises caicedo", "enzo", "enzo fernandez",
      "mainoo", "kobbie mainoo", "garnacho", "alejandro garnacho",
      "hojlund", "rasmus hojlund",
      "guimaraes", "bruno guimaraes",
      "trippier", "kieran trippier",
      "gabriel jesus", "gabriel", "gabriel magalhaes",
      "saliba", "william saliba",
      "maguire", "harry maguire",
      "pickford", "jordan pickford"], 10),

    # ── RUMOUR / SPECULATION — PENALTY (~35 phrases) ───────────────────────────
    (["could join", "could move", "could leave", "could sign",
      "might join", "might sign", "might leave", "might move",
      "rumour", "rumoured", "rumored", "reportedly",
      "according to reports", "reports suggest", "reports claim",
      "linked with", "linked to", "being linked",
      "interest in", "interested in", "showing interest",
      "eyeing", "eyeing up", "considering",
      "in talks", "in discussions", "in negotiations",
      "bid rejected", "bid turned down", "offer rejected",
      "set to join", "set to sign", "set to move",
      "close to", "nearing", "approaching",
      "could be heading", "may leave", "may join",
      "expected to", "tipped to", "likely to"], -15),
]

# Regex to detect a scoreline anywhere in the text, e.g. "2-1", "3–0"
_SCORELINE_RE = re.compile(r'\b\d{1,2}[-–]\d{1,2}\b')

def _known_players() -> list[str]:
    """
    Return a dynamically-built player token list sourced from TheSportsDB
    squad rosters for all top clubs. Cached for 7 days; auto-refreshes so
    new signings and emerging stars are picked up with no manual work.
    """
    try:
        from src.image_fetcher import get_known_player_tokens
        return get_known_player_tokens()
    except Exception:
        return []

# Milestone / feature story signals — highly shareable even without a match result
_MILESTONE_PHRASES: list[str] = [
    "oldest", "youngest", "first ever", "first time", "first time since",
    "history", "historic", "makes history", "creates history",
    "record", "record-breaking", "new record", "all-time record",
    "most goals", "most assists", "most appearances", "most caps",
    "most expensive", "richest", "highest paid",
    "never before", "only player", "only team", "only manager",
    "rare", "unique achievement", "incredible", "unbelievable",
    "legendary", "greatest", "best ever", "worst ever",
    "milestone", "century", "100th", "200th", "50th",
    "hat-trick of", "four goals", "five goals",
    "player of the tournament", "best player", "golden boot",
    "ballon d'or", "best in the world", "world class",
    "older than", "younger than", "more than", "fewer than",
    "surpasses", "overtakes", "breaks the record", "extends record",
    "unbeaten", "unbeaten run", "winning streak", "losing streak",
    "consecutive", "in a row", "back-to-back",
    "comeback", "miracle", "shock", "stunning", "sensational",
    "thriller", "dramatic", "last-gasp", "against all odds",
    "underdog", "giant killing", "upset", "surprise",
    "world cup star", "tournament top scorer", "tournament best",
]


def score_story(title: str, description: str = "") -> int:
    """
    Return a 0–100 significance score for the story.
    Higher = more breaking / important.
    """
    text = (title + " " + description).lower()
    score = 0

    for phrases, points in _BREAKING_SIGNALS:
        if any(p in text for p in phrases):
            score += points

    # Scoreline bonus
    if _SCORELINE_RE.search(text):
        score += 15

    # Multi-player bonus: +10 for each known player mentioned beyond the first
    player_hits = sum(1 for p in _known_players() if p in text)
    if player_hits >= 2:
        score += (player_hits - 1) * 10

    # Milestone / highly-shareable feature story bonus
    if any(p in text for p in _MILESTONE_PHRASES):
        score += 15

    return max(0, min(100, score))

RSS_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/sport/football/rss.xml",   "source": "BBC Sport"},
    {"url": "https://www.espn.com/espn/rss/soccer/news",          "source": "ESPN"},
    {"url": "https://www.theguardian.com/football/rss",           "source": "The Guardian"},
    {"url": "https://www.skysports.com/rss/12040",                "source": "Sky Sports"},
    {"url": "https://www.goal.com/feeds/en/news",                 "source": "Goal.com"},
]

# ── Category detection ─────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "Champions League":  ["champions league", "ucl", "europa league", "conference league", "uefa"],
    "Transfer News":     ["transfer", "signing", "signed", "deal", "bid", "fee", "contract", "loan", "move", "swap"],
    "Premier League":    ["premier league", "epl", "arsenal", "chelsea", "liverpool",
                          "manchester city", "manchester united", "tottenham", "newcastle", "aston villa"],
    "La Liga":           ["la liga", "real madrid", "barcelona", "atletico", "sevilla", "valencia"],
    "Bundesliga":        ["bundesliga", "bayern", "dortmund", "leverkusen", "rb leipzig"],
    "Serie A":           ["serie a", "juventus", "inter milan", "ac milan", "napoli", "roma", "lazio"],
    "Ligue 1":           ["ligue 1", "psg", "paris saint-germain", "marseille", "monaco", "lyon"],
    "International":     ["world cup", "euros", "euro 2024", "copa america", "nations league",
                          "international", "national team", "world cup qualifier"],
    "Top Players":       ["mbappe", "haaland", "bellingham", "vinicius", "salah",
                          "ronaldo", "messi", "de bruyne", "rodri", "modric"],
}

# ── Story-specific image keyword extraction ────────────────────────────────────

# Known player names → Pexels search term
PLAYER_SEARCHES = {
    "haaland":          "Erling Haaland football player",
    "mbappe":           "Kylian Mbappe football player",
    "vinicius":         "Vinicius football player Brazil",
    "bellingham":       "Jude Bellingham football player",
    "salah":            "Mohamed Salah football player",
    "ronaldo":          "Cristiano Ronaldo football player",
    "messi":            "Lionel Messi football player",
    "de bruyne":        "Kevin De Bruyne football player",
    "rodri":            "Rodri football player",
    "modric":           "Luka Modric football player",
    "kane":             "Harry Kane football player",
    "neymar":           "Neymar football player Brazil",
    "lewandowski":      "Robert Lewandowski football player",
    "benzema":          "Karim Benzema football player",
    "saka":             "Bukayo Saka Arsenal football",
    "foden":            "Phil Foden Manchester City football",
    "palmer":           "Cole Palmer Chelsea football",
    "rashford":         "Marcus Rashford Manchester United football",
    "odegaard":         "Martin Odegaard Arsenal football",
    "yamal":            "Lamine Yamal Barcelona football",
    "leao":             "Rafael Leao AC Milan football",
    "vlahovic":         "Dusan Vlahovic Juventus football",
    "lautaro":          "Lautaro Martinez Inter Milan football",
    "nunez":            "Darwin Nunez Liverpool football",
    "son":              "Son Heung-min Tottenham football",
}

# Known team names → Pexels search term
TEAM_SEARCHES = {
    "real madrid":          "Real Madrid football stadium",
    "barcelona":            "Barcelona football Camp Nou",
    "atletico":             "Atletico Madrid football",
    "manchester city":      "Manchester City Etihad football",
    "manchester united":    "Manchester United Old Trafford football",
    "liverpool":            "Liverpool Anfield football",
    "arsenal":              "Arsenal Emirates Stadium football",
    "chelsea":              "Chelsea Stamford Bridge football",
    "tottenham":            "Tottenham Spurs stadium football",
    "newcastle":            "Newcastle United football",
    "aston villa":          "Aston Villa Villa Park football",
    "west ham":             "West Ham football",
    "brighton":             "Brighton football",
    "everton":              "Everton football",
    "nottingham":           "Nottingham Forest football",
    "bayern":               "Bayern Munich Allianz Arena football",
    "dortmund":             "Borussia Dortmund football",
    "leverkusen":           "Bayer Leverkusen football",
    "rb leipzig":           "RB Leipzig football",
    "juventus":             "Juventus Turin football",
    "inter milan":          "Inter Milan San Siro football",
    "ac milan":             "AC Milan football Italy",
    "napoli":               "Napoli football Italy",
    "roma":                 "AS Roma football Italy",
    "lazio":                "Lazio football Italy",
    "psg":                  "Paris Saint-Germain football",
    "paris saint-germain":  "PSG Paris football stadium",
    "marseille":            "Marseille football France",
    "monaco":               "AS Monaco football",
    "lyon":                 "Olympique Lyonnais football",
    "sevilla":              "Sevilla football Spain",
    "valencia":             "Valencia football Spain",
    "ajax":                 "Ajax Amsterdam football",
    "porto":                "FC Porto football",
    "benfica":              "Benfica Lisbon football",
    "celtic":               "Celtic Park Glasgow football",
    "rangers":              "Rangers Ibrox football",
    "brazil":               "Brazil national football team",
    "argentina":            "Argentina national football team",
    "france":               "France national football team",
    "england":              "England national football team",
    "spain":                "Spain national football team",
    "germany":              "Germany national football team",
    "portugal":             "Portugal national football team",
    "italy":                "Italy national football team",
}

# Story type signals → action-specific Pexels terms appended as context
STORY_TYPE_HINTS = [
    (["won", "win", "beat", "victory", "champion", "title", "trophy"],
     "football victory celebration crowd"),
    (["goal", "scored", "hat-trick", "brace"],
     "football goal celebration player"),
    (["transfer", "signed", "signing", "deal", "fee", "bid"],
     "football player signing press conference"),
    (["injury", "injured", "ruled out", "surgery"],
     "football player injury treatment"),
    (["fired", "sacked", "resigned", "appointed", "manager", "coach"],
     "football manager coach touchline"),
    (["red card", "suspension", "banned", "sent off"],
     "football referee card foul"),
    (["final", "semi-final", "quarter-final"],
     "football stadium match final"),
    (["record", "history", "first ever", "most ever"],
     "football player record achievement"),
    (["contract", "extension", "renewal"],
     "football player contract signing"),
    (["relegation", "relegated", "promoted", "promotion"],
     "football crowd stadium match"),
]

FALLBACK_TERMS = [
    "football match action stadium",
    "soccer player running ball",
    "football crowd stadium atmosphere",
]

_STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "but", "with", "from", "by", "as", "is", "are", "was", "were", "has",
    "have", "had", "will", "would", "could", "should", "their", "they",
    "them", "he", "she", "it", "his", "her", "vs", "after", "before",
    "during", "over", "under", "still", "out", "up", "down", "back",
    "into", "that", "this", "says", "said", "new", "how", "why",
    "what", "who", "who", "do", "not", "no", "all", "be", "been",
}


def extract_pexels_queries(title: str, description: str = "") -> list[str]:
    """
    Build 2-3 story-specific Pexels search queries ranked from most to least specific.
    Tries: player name → team name → story type → key headline words → fallback.
    """
    text = (title + " " + description).lower()
    queries: list[str] = []

    # 1. Player names — most specific
    for player_key, player_query in PLAYER_SEARCHES.items():
        if player_key in text:
            queries.append(player_query)
            break

    # 2. Team names
    for team_key, team_query in TEAM_SEARCHES.items():
        if team_key in text:
            if team_query not in queries:
                queries.append(team_query)
            if len(queries) >= 2:
                break

    # 3. Story type (action context)
    for keywords, action_query in STORY_TYPE_HINTS:
        if any(kw in text for kw in keywords):
            if action_query not in queries:
                queries.append(action_query)
            break

    if queries:
        return queries[:3]

    # 4. Key words from the headline itself
    words = [
        w.strip(".,!?:;'\"()-")
        for w in title.split()
        if w.lower().strip(".,!?:;'\"()-") not in _STOP_WORDS and len(w) > 3
    ]
    if words:
        kw = " ".join(words[:3])
        queries.append(f"{kw} football")

    # 5. Always add a generic fallback last
    queries.append(FALLBACK_TERMS[hash(title) % len(FALLBACK_TERMS)])

    return queries[:3]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _story_id(entry: dict) -> str:
    key = entry.get("link") or entry.get("title") or ""
    return hashlib.md5(key.encode()).hexdigest()


def _categorize(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "Football News"


def _extract_rss_image(entry: dict) -> str:
    """
    Pull the article's own editorial image URL directly from the RSS entry.

    Priority per source:
      BBC Sport   → media_thumbnail   (upgrade /240/ → /976/ for high-res)
      Guardian    → media_content     (pick widest available)
      Sky Sports  → links[rel=enclosure, type=image/*]
      Generic     → enclosures / <img> in summary HTML
    """
    # BBC Sport — media_thumbnail
    thumbs = entry.get("media_thumbnail", [])
    if thumbs:
        url = thumbs[0].get("url", "")
        if url:
            # Upgrade BBC CDN resolution: /240/ → /976/
            url = re.sub(r'/\d{2,4}/', '/976/', url)
            return url

    # Guardian / ESPN — media_content; pick highest resolution
    media = entry.get("media_content", [])
    if media:
        def _w(m: dict) -> int:
            try:
                return int(m.get("width", 0))
            except (ValueError, TypeError):
                return 0
        best = max(media, key=_w)
        url  = best.get("url", "")
        if url:
            return url

    # Sky Sports — enclosure link in links[]
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and "image" in link.get("type", ""):
            href = link.get("href", "")
            if href:
                return href

    # Generic enclosure element
    for enc in entry.get("enclosures", []):
        url  = enc.get("url") or enc.get("href", "")
        mime = enc.get("type", "")
        if url and ("image" in mime or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            return url

    # Last resort: first <img src=…> inside the summary HTML
    summary = entry.get("summary", "") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    if m:
        return m.group(1)

    return ""


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_news(max_stories: int = 20) -> list[dict]:
    """Return a deduplicated list of football story dicts."""
    import socket
    stories: list[dict] = []
    seen_ids: set[str] = set()

    for feed_info in RSS_FEEDS:
        try:
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(10)
            try:
                feed = feedparser.parse(feed_info["url"])
            finally:
                socket.setdefaulttimeout(old_timeout)
        except Exception as e:
            print(f"  [news_fetcher] error fetching {feed_info['url']}: {e}")
            continue

        for entry in feed.entries:
            story_id = _story_id(entry)
            if story_id in seen_ids:
                continue
            seen_ids.add(story_id)

            title = entry.get("title", "").strip()
            if not title:
                continue

            description = _strip_html(
                entry.get("summary", entry.get("description", ""))
            ).strip()

            category = _categorize(title, description)

            stories.append(
                {
                    "id":            story_id,
                    "title":         title,
                    "description":   description,
                    "link":          entry.get("link", ""),
                    "source":        feed_info["source"],
                    "category":      category,
                    "published":     entry.get("published", ""),
                    "score":         score_story(title, description),
                    # Editorial image from the RSS feed itself (most accurate)
                    "article_image": _extract_rss_image(entry),
                    # Story-specific Pexels queries (most → least specific)
                    "image_keywords": extract_pexels_queries(title, description),
                }
            )

            if len(stories) >= max_stories:
                return stories

    return stories
