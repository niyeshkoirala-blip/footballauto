import re
import hashlib
import feedparser

# ── Breaking-news significance scoring ────────────────────────────────────────
# Each tuple: (list of trigger phrases, points awarded)
# Each bucket fires at most once; the two name terms are deduped and taper
# (see _name_points). Threshold for immediate posting is BREAKING_THRESHOLD
# (default 50, main.py).

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

    # ── WORLD CUP MATCH — TOP PRIORITY (+200) ─────────────────────────────────
    # Only an actual World Cup fixture dominates. Bare "world cup" fired on 8 of
    # 63 live BBC stories and not one was a match: a prize-money explainer, a
    # quiz, "how to follow the season". A passing mention is already worth +20
    # under MAJOR COMPETITION NAMES; that is what a mention is worth.
    (["wc clash", "world cup match", "world cup final", "world cup knockout",
      "world cup group", "world cup round", "world cup last 16",
      "world cup glory", "wc round", "wc final"], 200),

    # ── MATCH RESULT — HIGH PRIORITY (+150) ───────────────────────────────────
    # An actual finished game (one team beats another / a draw) ranks near the top.
    # Exhaustive phrasing so no result slips through.
    ([
      # — win verbs —
      "beats", "beat", "beaten", "defeated", "defeats", "defeat",
      "won", "wins", "win over", "wins over", "won against", "win against",
      # bare "win" is a whole-page false positive ("must-win", "win the race for
      # his signature"); "winning" is "winning streak/mentality". Spell out the
      # forms that only a finished game produces.
      "win at", "win the final", "win the cup", "win the league", "win the title",
      "victory", "victories", "victorious", "victory over",
      "overcome", "overcomes", "overcame",
      "triumph", "triumphs", "triumphed", "triumphant",
      "conquer", "conquers", "conquered",
      "topple", "topples", "toppled",
      "see off", "sees off", "saw off", "seen off",
      "dispatch", "dispatches", "dispatched",
      "stun", "stuns", "stunned",
      # "shock"/"upset"/"down" alone are not results: "shock move", "upset fans",
      # and "break down" — which is what handed a World Cup prize-money quiz +150.
      "shock win", "shock defeat", "shock result", "downed",
      "run riot",
      # — beat 'past' phrasings —
      "ease past", "eases past", "eased past",
      "breeze past", "breezes past", "breezed past",
      "cruise past", "cruises past", "cruised past",
      "sail past", "sails past", "sailed past",
      "power past", "powers past", "powered past",
      "march past", "marches past", "marched past",
      "squeeze past", "squeezes past", "squeezed past",
      "get past", "gets past", "got past",
      "edge past", "edges past", "edged past",
      "battle past", "scrape past", "scrapes past", "scraped past",
      "brush aside", "brushes aside", "brushed aside",
      "sweep aside", "sweeps aside", "swept aside",
      "put to the sword",
      # — narrow win —
      # bare "edge(s)" is "edge closer to a deal" — a rumour, scoring +150.
      "edged", "edge out", "edges out", "edged out",
      "pip", "pips", "pipped", "nick", "nicks", "nicked",
      "snatch", "snatches", "snatched", "snatch win", "snatch victory",
      "late win", "late winner", "last-minute winner",
      "injury-time winner", "stoppage-time winner", "last-gasp",
      "grab win", "grab victory", "grab all three points",
      # — comeback —
      "comeback win", "comeback victory", "comeback", "fightback",
      "fight back", "fights back", "fought back", "come from behind",
      "rescue", "rescues", "rescued", "salvage", "salvages", "salvaged",
      "claim win", "claim victory", "claims win", "claims victory",
      "claim all three points", "claim three points", "claim a point",
      "earn win", "earns win", "earn victory", "earn a point", "earns point",
      "secure win", "secures win", "secure victory", "secure three points",
      "seal win", "seals win", "seal victory", "clinch win", "clinch victory",
      # — thrashings / big wins —
      "thrash", "thrashes", "thrashed", "thrashing",
      "hammer", "hammers", "hammered", "hammering",
      "rout", "routs", "routed", "routing",
      "demolish", "demolishes", "demolished",
      "crush", "crushes", "crushed",
      "destroy", "destroys", "destroyed",
      "batter", "batters", "battered",
      "maul", "mauls", "mauled",
      "thump", "thumps", "thumped", "thumping",
      "wallop", "wallops", "walloped",
      "humiliate", "humiliates", "humiliated",
      "humble", "humbles", "humbled",
      "annihilate", "annihilates", "annihilated",
      "trounce", "trounces", "trounced",
      "blitz", "blitzes", "blitzed",
      "spank", "spanks", "spanked",
      "pummel", "pummels", "pummelled", "pummeled",
      "steamroll", "whitewash",
      "outclass", "outclasses", "outclassed",
      "outplay", "outplays", "outplayed",
      "overpower", "overpowers", "overpowered",
      "overwhelm", "overwhelms", "overwhelmed",
      "dominate", "dominates", "dominated",
      "ran riot", "five-star", "six-star", "seven-star",
      "put four past", "put five past", "put six past",
      # — draws — (bare "draw" is the cup draw: "EFL Cup second-round draw" +150)
      "drew", "draw with", "drew with", "draws with",
      "stalemate", "goalless", "goalless draw",
      "nil-nil", "all square", "honours even", "honours shared",
      "share spoils", "share the spoils", "share points", "share the points",
      "held to a draw", "held to",   # bare "held": "talks held", "record held by"
      "shared the points", "deadlock", "deadlocked",
      # — losses (still a result) —
      "lose", "loses", "lose to", "loses to", "lost to",
      # "lost"/"loss"/"losing" are not results: "lost its shine", "loss of form".
      "suffer defeat", "suffers defeat", "suffer loss", "suffers loss",
      "go down", "goes down", "went down",
      "fall to", "falls to", "fell to",
      "slump to", "slumps to", "slumped to",
      "crash to", "crashes to", "crashed to",
      "succumb", "succumbs", "succumbed",
      "beaten by", "defeated by", "downed by",
      # — result markers —
      "full-time", "full time", "final whistle", "final score",
      "ft:", "ft ", "result:", "match report", "report:", "recap",
      "scoreline", "as it happened", "as it stood",
      "on penalties", "penalty shootout", "penalty shootouts", "shootout", "shootouts",   # bare "penalties": features
      "after extra time", "extra time", "aet",
      "wins on penalties", "won on penalties", "lost on penalties",
      "win on penalties", "spot-kicks", "spot kicks",
      # — progression / knockout (a tie was decided) —
      "advance", "advances", "advanced", "advance to",
      "progress", "progresses", "progressed", "progress to",
      "through to", "go through", "goes through", "went through",
      # "booked" is a yellow card and "book" is a betting book — only the idiom
      # means a team went through, and it is always written with a possessive.
      "book their place", "books their place", "booked their place", "book a place",
      "reach final", "reaches final", "reached final",
      "reach the final", "into the final", "into the last",
      "qualify", "qualifies", "qualified",
      "seal spot", "seal place", "seal qualification",
      "knocked out", "knock out", "knocks out",
      "crash out", "crashes out", "crashed out",
      "bow out", "bows out", "bowed out",
      "dumped out", "dump out", "knocked out of",
      "eliminated", "eliminate", "eliminates", "elimination",
      "sent packing", "sent home",   # "exit": "Who will exit Chelsea?" is a rumour
      "out of the world cup", "out of the cup", "out of the competition",
     ], 150),

    # ── CONFIRMED TRANSFERS & SIGNINGS (~60 phrases) ──────────────────────────
    # "X sign Y" / "X buy Y" is how a confirmed deal is actually written, and
    # the -120 rumour penalty below is what stops "could sign" scoring here.
    (["sign", "signs", "signing", "buy", "buys", "agree deal", "agrees deal", "agree a deal",
      "has signed", "officially signed", "signs for", "sign for",
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
      "snaps up", "swoops for", "clinches signing",   # "lands": "lands in trouble"
      "ties down", "loaned out", "loan confirmed", "loan completed",
      "loan deal", "loan move", "loan signing", "returns on loan",
      "permanent deal", "permanent transfer", "permanent switch",
      "rejoins", "re-signs",   # "returns to" is "returns to training/form/fitness"
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
      "three-peat", "four in a row",   # "back-to-back defeats/fixtures" too
      "successive title", "consecutive title", "consecutive win",
      "double winners", "treble winners", "quadruple",
      "historic win", "historic victory", "makes history", "creates history",
      "glory", "glorious",   # triumph/triumphant/victorious are in the +150 bucket
      "perfect season", "unbeaten season", "invincible",
      "domestic title", "european title", "world champions",
      "ballon d'or", "golden boot", "player of the year",
      "manager of the year", "golden glove", "best player",
      "top scorer", "pichichi", "capocannoniere",
      "champions!", "title!", "glory!", "trophy!"], 35),

    # ── MANAGER / COACHING CHANGES (~60 phrases) ───────────────────────────────
    (["sack", "sacks", "sacked", "fired", "dismissed", "axed", "relieved of duties",
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

    # ── KNOCKOUT ROUND REACHED (~20 phrases) ───────────────────────────────────
    # Round names only. Every progression verb this used to hold ("knocked out",
    # "crash out", "advance to", "through to", "exit") is verbatim in the +150
    # result bucket, and its 19 cup names are verbatim in MAJOR COMPETITION
    # NAMES below — so one knockout tie used to collect 25 points three times.
    # Bare "final" and "play-off" are gone too: they scored a World Cup
    # third-place-play-off quiz.
    (["cup final", "league final", "grand final",
      "play-off final", "playoff final", "playoff winner",
      "semi-final", "semifinals", "last four",
      "quarter-final", "quarterfinals", "last eight",
      "last 16", "round of 16", "last 32", "round of 32", "last 64",
      "group stage exit", "group stage elimination"], 25),

    # (a second MATCH RESULTS bucket lived here. 69 of its 89 phrases were
    #  verbatim copies from the +150 bucket above, so 62% of the stories that
    #  scored a result scored it twice — 175, not 150 — and the leftovers were
    #  "win", "claim", "draw", which fire on any football sentence at all.)

    # ── IN-MATCH ACTION & GOALS (~70 phrases) ──────────────────────────────────
    # No bare "goal(s)"/"lead(s)"/"puts"/"saved"/"double": they fire on ordinary
    # football prose — "our goal is", "leads tributes", "puts pressure on",
    # "saved his job", "the Double" — and paid every story the same 20 points.
    (["scores", "scored", "takes the lead", "go ahead",
      "opener", "opens the scoring", "breaks the deadlock",
      "levels", "levelled", "equalises", "pulls level",
      "pounces", "taps in", "slots in",
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
      "penalty retaken", "keeper saves",
      "own goal", "own-goal",
      "keeper error", "goalkeeper error", "howler", "blunder",
      "hat-trick", "brace", "treble", "four goals",
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
      "de bruyne", "kevin de bruyne", "rodri", "harry kane",
      "lewandowski", "robert lewandowski", "modric", "luka modric",
      "benzema", "karim benzema", "saka", "bukayo saka",
      "yamal", "lamine yamal", "pedri", "gavi",
      "ter stegen", "alisson", "ederson", "courtois",
      "neuer", "oblak", "donnarumma",
      "van dijk", "virgil van dijk", "trent", "trent alexander-arnold",
      "son heung-min", "rashford", "marcus rashford",
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
      "luis diaz", "gakpo", "cody gakpo",
      "nunez", "darwin nunez", "watkins", "ollie watkins",
      "isak", "alexander isak", "gordon", "anthony gordon",
      "martinelli", "gabriel martinelli",
      "declan rice", "havertz", "kai havertz",
      "odegaard", "martin odegaard",
      "griezmann", "antoine griezmann",
      "thuram", "marcus thuram",
      "dimarco", "federico dimarco",
      "caicedo", "moises caicedo", "enzo", "enzo fernandez",
      "mainoo", "kobbie mainoo", "garnacho", "alejandro garnacho",
      "hojlund", "rasmus hojlund",
      "guimaraes", "bruno guimaraes",
      "trippier", "kieran trippier",
      "gabriel jesus", "gabriel magalhaes",
      "saliba", "william saliba",
      "maguire", "harry maguire",
      "pickford", "jordan pickford"], 10),

    # ── PLAYER / MANAGER INTERVIEWS & QUOTES (~50 phrases) ────────────────────
    (["reveals", "reveals all", "reveals plans", "reveals future",
      "admits", "admits he", "admits she", "admits they",
      "exclusive interview", "exclusive", "speaks out", "opens up",
      "breaks silence", "addresses", "responds to", "reacts to",
      "tells reporters", "tells press", "tells media",
      "press conference", "post-match interview", "pre-match interview",
      "insists", "confirms", "denies",   # "says"/"claims": every quote sentence
      "comments on", "speaks about", "talks about", "discusses",
      "shares thoughts", "gives update", "provides update",
      "statement from", "official statement",
      "explains why", "explains how", "explains decision",
      "warns", "urges", "calls for", "demands",
      "backs", "defends", "criticises", "praises",
      "optimistic", "confident", "hopeful", "disappointed",
      "frustrated", "delighted", "proud", "angry",
      "reaction", "responds", "reply"], 20),

    # ── MATCH PREVIEWS & UPCOMING FIXTURES (~40 phrases) ───────────────────────
    (["preview", "match preview", "game preview", "fixture preview",
      "preview:", "ahead of", "ahead of the match", "ahead of the game",
      "face", "faces", "take on", "takes on",
      "host", "hosts", "visit", "visits", "travel to", "travels to",
      "clash", "clash with", "meet", "meets",
      "upcoming fixture", "upcoming match", "upcoming game",
      "next match", "next game", "next fixture",
      "kick off", "kick-off", "ko:", "ko time",
      "how to watch", "where to watch", "live on",
      "tv schedule", "broadcast", "stream live",
      "team news", "predicted lineup", "predicted starting xi",
      "expected lineup", "starting xi", "who will start",
      "form guide", "head to head", "h2h",
      # No weekday names: they gave +20 to "Sunday's gossip" and to any story
      # that happens to mention when something takes place.
      "prediction", "tips", "betting odds"], 20),

    # ── ANALYSIS, FEATURES & RANKINGS (~45 phrases) ────────────────────────────
    (["ranked", "ranking", "rankings", "best of",
      "top 5", "top 10", "top 10", "top 20",
      "rated", "rating", "ratings", "player ratings",
      "analysis", "tactical analysis", "in-depth",
      "explained", "how it works", "guide",
      "verdict", "review", "assessed",
      "quiz", "test yourself", "how well do you know",
      "who is", "profile", "spotlight",
      "the story of", "behind the scenes",
      "facts about", "things you didn't know",
      "comparison", "compared",
      "watch:", "video:", "highlights",
      "gallery", "photos", "picture",
      "poll", "vote", "your say",
      "opinion", "column", "feature",
      "weekly", "monthly", "annual",
      "best moments", "worst moments",
      "season review", "year in review",
      "winners and losers", "talking points",
      "five things", "three things", "key moments"], 20),

    # ── PLAYER FORM, FITNESS & GENERAL NEWS (~35 phrases) ──────────────────────
    (["in form", "out of form", "good form", "poor form",
      "returns from injury", "return from injury", "back in action",
      "fit again", "passed fit", "cleared to play",
      "debut", "first goal", "first appearance",
      "career", "future plans", "future unclear",
      "transfer target", "on the radar", "being monitored",
      "first team", "dropped to bench", "dropped from squad",   # bare "squad"
      "called up", "international call-up", "recalled",
      "rested", "given time off",
      "training ground", "in training", "returns to training",
      "contract situation", "contract running out", "contract expires",
      "free agent", "out of contract",
      "wage demands", "salary", "pay rise",
      "retiring", "retirement", "calls time", "hangs up boots"], 20),

    # ── SOCIAL & VIRAL MOMENTS (~20 phrases) ───────────────────────────────────
    (["viral", "trending", "goes viral", "social media",
      "fans react", "fans slam", "fans praise", "fans divided",
      "twitter reacts", "internet reacts",
      "celebration", "goal celebration",
      "shocking", "controversial", "bizarre", "funny",
      "crowd trouble", "fan trouble", "crowd incident",
      "pitch invasion", "streaker",
      "must see", "watch this"], 15),

    # ── RUMOUR / SPECULATION — PENALTY (~35 phrases) ───────────────────────────
    # -120, not -15. Gossip is the lowest-value thing this page can post, but
    # any club story collects an ambient 90 for free (major team 20 + competition
    # 20 + squad player 10 + transfer wording 40) plus 40 per famous name, so a
    # penalty smaller than that cannot pull a rumour under the 50 threshold.
    # -120 sinks "close to signing" and the daily gossip column to 0 while a
    # story with real reporting behind it still clears 50.
    (["could join", "could move", "could leave", "could sign",
      "might join", "might sign", "might leave", "might move",
      "rumour", "rumoured", "rumored", "reportedly",
      "according to reports", "reports suggest", "reports claim",
      "linked with", "linked to", "being linked",
      "eyeing", "eyeing up",
      "bid rejected", "bid turned down", "offer rejected",
      "set to join", "set to sign", "set to move",
      "could be heading", "may leave", "may join",
      "tipped to",
      "gossip", "transfer gossip"], -120),

    # ── HEDGED REPORTING — MILD PENALTY ───────────────────────────────────────
    # These four read as gossip in a transfer headline but are ordinary English
    # in real reporting: "ruled out ... expected to miss the World Cup" is a
    # confirmed injury, "confirm interest in X has ended" is a completed deal.
    # At -120 they zeroed both. -30 still ranks a hedge below a plain statement.
    (["interest in", "interested in", "showing interest",
      "in talks", "in discussions", "in negotiations",
      "close to", "nearing", "approaching",
      "expected to", "likely to", "considering"], -30),
]

# Regex to detect a scoreline anywhere in the text, e.g. "2-1", "3–0"
_SCORELINE_RE = re.compile(r'\b\d{1,2}[-–]\d{1,2}\b')

from functools import lru_cache

_WORD_EDGE = re.compile(r"\w").match


def _phrase_re(phrases) -> re.Pattern:
    r"""Compile one bucket of phrases into a single alternation.

    Bare `in` matched inside words: "son" scored Son Heung-min on "season",
    "win" on "winger", "lose" on "close", "final" on "finally". \b is added
    only where the phrase edge is a word char — "£50m", "ft:" and "champions!"
    have non-word edges and \bft:\b can never match anything.
    Longest phrase first so "cristiano ronaldo" wins over "ronaldo" and the
    pair counts as one name instead of two.
    """
    body = "|".join(
        (r"\b" if _WORD_EDGE(p) else "") + re.escape(p)
        + (r"\b" if _WORD_EDGE(p[-1]) else "")
        for p in sorted({p for p in phrases if p}, key=len, reverse=True)
    )
    # An empty bucket (the squad cache when its refresh failed) must match
    # nothing — an empty pattern matches at every position instead.
    return re.compile(body or r"(?!)")


_SIGNAL_RES: list[tuple[re.Pattern, int]] = [
    (_phrase_re(phrases), points) for phrases, points in _BREAKING_SIGNALS
]

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

# ── Hall of Fame: historically famous / globally recognised players ────────────
# First name mentioned is worth +40, each extra one half the last (max +80).
# Covers all-time greats, 2000s–2020s legends, and current world-class superstars.
_HALL_OF_FAME: frozenset[str] = frozenset({
    # ── All-time greats ────────────────────────────────────────────────────────
    "pele",
    "maradona", "diego maradona",
    "cruyff", "johan cruyff",
    "platini", "michel platini",
    "eusebio",
    "puskas", "ferenc puskas",
    "di stefano", "alfredo di stefano",
    "george best",
    "bobby charlton",
    "kenny dalglish",
    "alan shearer",
    "michael owen",
    "dennis bergkamp",
    "patrick vieira",
    "van basten", "marco van basten",
    "gullit", "ruud gullit",
    "matthaus", "lothar matthaus",
    "maldini", "paolo maldini",
    "baresi", "franco baresi",
    "baggio", "roberto baggio",
    "totti", "francesco totti",
    "del piero", "alessandro del piero",
    "shevchenko", "andriy shevchenko",
    "ronaldo nazario", "r9",
    "rivaldo",
    "roberto carlos",
    "cafu",
    "romario",
    "bebeto",
    "zico",
    "socrates",
    "garrincha",
    # ── 2000s–2020s legends ────────────────────────────────────────────────────
    "zidane", "zinedine zidane",
    "ronaldinho",
    "kaka",
    "henry", "thierry henry",
    "beckham", "david beckham",
    "rooney", "wayne rooney",
    "lampard", "frank lampard",
    "gerrard", "steven gerrard",
    "ferdinand", "rio ferdinand",
    "terry", "john terry",
    "scholes", "paul scholes",
    "giggs", "ryan giggs",
    "cantona", "eric cantona",
    "owen", "michael owen",
    "shearer", "alan shearer",
    "drogba", "didier drogba",
    "eto'o", "samuel eto'o",
    "xavi", "xavi hernandez",
    "iniesta", "andres iniesta",
    "puyol", "carles puyol",
    "casillas", "iker casillas",
    "buffon", "gianluigi buffon",
    "pirlo", "andrea pirlo",
    "van nistelrooy", "ruud van nistelrooy",
    "robben", "arjen robben",
    "sneijder", "wesley sneijder",
    "ribery", "franck ribery",
    "schweinsteiger", "bastian schweinsteiger",
    "ballack", "michael ballack",
    "klose", "miroslav klose",
    "fabregas", "cesc fabregas",
    "vieira", "patrick vieira",
    "bergkamp", "dennis bergkamp",
    "ibrahimovic", "zlatan ibrahimovic",
    "suarez", "luis suarez",
    "aguero", "sergio aguero", "kun aguero",
    "ozil", "mesut ozil",
    "reus", "marco reus",
    "neuer", "manuel neuer",
    "kroos", "toni kroos",
    "muller", "thomas muller",
    "podolski", "lukas podolski",
    "pogba", "paul pogba",
    "kante", "ngolo kante",
    "giroud", "olivier giroud",
    "varane", "raphael varane",
    "lloris", "hugo lloris",
    "maldini",
    # ── Current world-class superstars ────────────────────────────────────────
    "messi", "lionel messi",
    "ronaldo", "cristiano ronaldo", "cr7",
    "neymar", "neymar jr",
    "mbappe", "kylian mbappe",
    "haaland", "erling haaland",
    "bellingham", "jude bellingham",
    "vinicius", "vinicius jr",
    "salah", "mohamed salah",
    "de bruyne", "kevin de bruyne",
    "lewandowski", "robert lewandowski",
    "modric", "luka modric",
    "benzema", "karim benzema",
    "kane", "harry kane",
    "saka", "bukayo saka",
    "yamal", "lamine yamal",
    "pedri", "gavi",
    "osimhen", "victor osimhen",
    "musiala", "jamal musiala",
    "wirtz", "florian wirtz",
    "kvaratskhelia", "kvara",
    "joao felix",
    "rafael leao",
    "griezmann", "antoine griezmann",
    "son heung-min",
    "rashford", "marcus rashford",
    "foden", "phil foden",
    "cole palmer",
    "odegaard", "martin odegaard",
    "declan rice",
    "alexander isak",
    "vlahovic", "dusan vlahovic",
    "lukaku", "romelu lukaku",
    "thuram", "marcus thuram",
    "camavinga",
    "dembele", "ousmane dembele",
    "bernardo silva",
    "ruben dias",
    "kimmich", "joshua kimmich",
    "goretzka", "leon goretzka",
    "szoboszlai", "dominik szoboszlai",
    "calhanoglu", "hakan calhanoglu",
    "barella", "nicolo barella",
    "lautaro", "lautaro martinez",
    "diaz", "luis diaz",
    "nunez", "darwin nunez",
    "watkins", "ollie watkins",
    "martinelli", "gabriel martinelli",
    "havertz", "kai havertz",
    "mac allister", "alexis mac allister",
    "dimarco", "federico dimarco",
    "caicedo", "moises caicedo",
    "enzo fernandez",
    "mainoo", "kobbie mainoo",
    "garnacho", "alejandro garnacho",
    "hojlund", "rasmus hojlund",
    "guimaraes", "bruno guimaraes",
    "trippier", "kieran trippier",
    "gabriel jesus",
    "saliba", "william saliba",
    "pickford", "jordan pickford",
    "pulisic", "christian pulisic",
    "dybala", "paulo dybala",
    "chiesa", "federico chiesa",
})

# Milestone / feature story signals — highly shareable even without a match result
# Flat +15 for ANY hit, so every phrase has to be genuinely rare. "more than",
# "record", "history", "first time", "stunning", "shock", "in a row" are not —
# they are ordinary English and were handing the bonus to filler. What is left
# only appears when a story really is about a record or a first.
_MILESTONE_PHRASES: list[str] = [
    "oldest", "youngest", "first ever", "first time since",
    "makes history", "creates history",
    "record-breaking", "new record", "all-time record",
    "breaks the record", "extends record", "surpasses", "overtakes",
    "most goals", "most assists", "most appearances", "most caps",
    "never before", "only player", "only team", "only manager",
    "milestone", "100th", "200th", "50th", "hat-trick of",
    "winning streak", "losing streak", "unbeaten run",
    "giant killing", "against all odds",
    "player of the tournament", "tournament top scorer",
]


_HOF_RE = _phrase_re(_HALL_OF_FAME)
_MILESTONE_RE = _phrase_re(_MILESTONE_PHRASES)


# The squad cache refreshes weekly, so this one can only be built at call time.
@lru_cache(maxsize=1)
def _players_re(tokens: tuple[str, ...]) -> re.Pattern:
    return _phrase_re(tokens)


def _name_points(hits: set[str], first: int) -> int:
    """Points for a set of matched name aliases, replacing `len(hits) * first`.

    Dedupe first: _HALL_OF_FAME lists both "ronaldo" and "cristiano ronaldo",
    so one player scored twice — 5 of the 6 name-matching stories on a live BBC
    pull hit this. Then halve every extra person, which caps the whole term at
    2 * first no matter how many names a listicle crams in.

    ponytail: "alias contained in a longer alias" is the entire dedup. It misses
    unrelated aliases for one player ("cr7" vs "ronaldo"); canonical ids are the
    upgrade, worth it only when double-counted CR7 headlines actually turn up.
    """
    # Token boundary, not bare containment: "son" is a substring of "alisson"
    # but Son and Alisson are two players. "ronaldo" ⊂ "cristiano ronaldo" is a
    # real alias because it sits on a word edge.
    people = hits - {a for a in hits for b in hits
                     if a != b and (b.startswith(a + " ") or b.endswith(" " + a)
                                    or " " + a + " " in b)}
    return int(2 * first * (1 - 0.5 ** len(people)))


# Off on the hot path (60s poll, 200 stories): each term costs one `is not None`
# and nothing else. explain_story() switches it on for one call.
_TRACE: list | None = None


def score_story(title: str, description: str = "") -> int:
    """
    Return a significance score for the story (minimum 0).
    Higher = more breaking / important. Buckets still stack without a global
    ceiling, but every individual term is bounded, so no one signal type can
    carry a story alone. That was the real cost of dropping the old 100 cap:
    a season-review listicle naming twelve stars scored 700 while
    "Arsenal beat Chelsea 2-1" scored 210.
    """
    # The page posts a card whose headline is the title, so title signal is what
    # actually matters. BBC standfirsts are real prose (median 128 chars, only
    # ~21% word overlap with the title), so they do carry independent signal —
    # but it is body-copy signal: one passing "World Cup" in a history feature
    # bought +240 and outranked every real result on the feed. Score the two
    # separately and discount the description. Anything in 0.25–0.5 gives the
    # same ordering on live data, so //3 — no float, no cast, always an int.
    # ponytail: recursion, not a helper — keeps the single scoring body that the
    # regex and caps patches also edit, so this stays a 3-line diff.
    if description:
        return score_story(title) + score_story(description) // 3

    text = title.lower()
    score = 0

    for rx, points in _SIGNAL_RES:
        m = rx.search(text)
        if m:
            score += points
            if _TRACE is not None: _TRACE.append((points, m.group(), "signal"))

    # Scoreline bonus
    if _SCORELINE_RE.search(text):
        score += 15
        if _TRACE is not None: _TRACE.append((15, "", "scoreline"))

    # Hall-of-Fame superstars: first name +40, each extra one half the last
    hof = set(_HOF_RE.findall(text))
    score += _name_points(hof, 40)
    if _TRACE is not None and hof: _TRACE.append((_name_points(hof, 40), ", ".join(sorted(hof)), "hall-of-fame"))

    # Dynamic squad cache: first +10, tapering the same way
    squad = set(_players_re(tuple(_known_players())).findall(text))
    score += _name_points(squad, 10)
    if _TRACE is not None and squad: _TRACE.append((_name_points(squad, 10), ", ".join(sorted(squad)), "squad-cache"))

    # Milestone / highly-shareable feature story bonus
    if _MILESTONE_RE.search(text):
        score += 15
        if _TRACE is not None: _TRACE.append((15, _MILESTONE_RE.search(text).group(), "milestone"))

    return max(0, score)


def explain_story(title: str, description: str = "") -> list[tuple[int, str, str, str]]:
    """(points, matched phrase, term, "title"|"desc") for everything score_story counted.

    Not a second scorer — it runs score_story itself with the trace sink on, so
    a bucket's points changing shows up here for free. Description rows carry
    their pre-//3 points; the //3 lands on the sum, so callers should show the
    discounted total as score_story(title, desc) - score_story(title).

    ponytail: one module global, no lock — this is a single-threaded CLI. If the
    poll ever goes concurrent, make _TRACE a contextvar.
    """
    global _TRACE
    rows = []
    for source, text in (("title", title), ("desc", description)):
        if not text:
            continue
        _TRACE = []
        try:
            score_story(text)
        finally:
            hits, _TRACE = _TRACE, None
        rows += [(p, ph, _bucket_label(ph) if t == "signal" else t, source)
                 for p, ph, t in hits]
    return rows


def _bucket_label(phrase: str) -> str:
    """Buckets are bare tuples with only comment headers, so name each one after
    its own first phrase — enough for a tuner to grep _BREAKING_SIGNALS and land
    on the right one. Preview-only, so the linear scan is free."""
    return next((p[0] for p, _ in _BREAKING_SIGNALS if phrase in p), "signal")

# Single source by choice: BBC Sport football. Every entry is reliably dated,
# football-only, never paywalled, and carries a high-res editorial image we can
# upgrade to /976/. Multi-source meant the same match posted five times over.
RSS_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/sport/football/rss.xml",   "source": "BBC Sport"},
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


_CATEGORY_RES = [(c, _phrase_re(kws)) for c, kws in CATEGORY_KEYWORDS.items()]
_PLAYER_RES = [(_phrase_re([k]), q) for k, q in PLAYER_SEARCHES.items()]
_TEAM_RES = [(_phrase_re([k]), q) for k, q in TEAM_SEARCHES.items()]
_HINT_RES = [(_phrase_re(kws), q) for kws, q in STORY_TYPE_HINTS]


def extract_pexels_queries(title: str, description: str = "") -> list[str]:
    """
    Build 2-3 story-specific Pexels search queries ranked from most to least specific.
    Tries: player name → team name → story type → key headline words → fallback.
    """
    text = (title + " " + description).lower()
    queries: list[str] = []

    # 1. Player names — most specific
    for rx, player_query in _PLAYER_RES:
        if rx.search(text):
            queries.append(player_query)
            break

    # 2. Team names
    for rx, team_query in _TEAM_RES:
        if rx.search(text):
            if team_query not in queries:
                queries.append(team_query)
            if len(queries) >= 2:
                break

    # 3. Story type (action context)
    for rx, action_query in _HINT_RES:
        if rx.search(text):
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


def _age_hours(entry: dict) -> float:
    """Hours since publication. 0.0 for undated or future-dated entries
    (Sky timestamps some posts a few minutes ahead of the clock)."""
    import calendar, time
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return 0.0  # ponytail: BBC/ESPN always date entries; keep the rare undated one
    return max(0.0, (time.time() - calendar.timegm(t)) / 3600)


def _too_old(entry: dict, max_age_minutes: int | None = None) -> bool:
    """True if the entry is older than MAX_AGE_MINUTES (default 30).

    Only genuinely new news gets posted. The daemon polls once a minute, so a
    story is normally 0-2 minutes old when it is picked up; the window only
    needs enough slack to survive a job handoff (~1-2 min) or a brief outage.
    Anything older than that is stale by the time it would reach the page, so
    it is dropped rather than queued.
    """
    import os
    if max_age_minutes is None:
        max_age_minutes = int(os.getenv("MAX_AGE_MINUTES", "30"))
    return _age_hours(entry) * 60 > max_age_minutes


# Other-sport rejects. Matched on word boundaries, never as substrings —
# plain "in" tests wrongly killed football stories: "the open" fires on "the
# opening goal", "gaa" on "van Gaal", "boxing" on Boxing Day fixtures.
# Terms stay sport-specific for the same reason: bare "stakes" rejected a
# World Cup story for the phrase "high stakes".
_NOT_FOOTBALL_RE = re.compile(
    r"\b("
    r"horse racing|racecourse|jockey|gelding|filly|furlong|nassau stakes|"
    r"golf|golfer|ryder cup|pga|lpga|birdie|the masters|"
    r"cricket|test match|the ashes|wicket|t20|"
    r"formula 1|grand prix|pole position|"
    r"nfl|nba|mlb|nhl|super bowl|"
    r"tennis|wimbledon|atp tour|wta|"
    r"heavyweight|ufc|mma|"
    r"rugby|six nations|snooker|tour de france|"
    r"netball|hurling abuse"
    r")\b"
)


def _is_football(title: str, description: str = "") -> bool:
    return not _NOT_FOOTBALL_RE.search((title + " " + description).lower())


# Non-postable FORMATS. A quiz, a TV listing, a live blog or a video stub has
# no standalone image card in it, yet scores well: "how to watch" and "live on"
# are +20 preview signals and "as it happened" is a +150 result signal, so a BBC
# TV promo scored 230 and a live blog 170 against a threshold of 50.
#
# TITLE ONLY, deliberately. BBC opens the *summary* of ordinary match reports
# with "Watch highlights as ...", so reading the description dropped two real
# results in a single live feed ("Chelsea lose friendly as Juventus score
# stunning winner", "Nygren header earns Celtic opening victory").
#
# Word boundaries only, same lesson as the reject list above: bare "live" kills
# "Live wire Saka", bare "watch" kills "Watch out for Haaland", bare "video"
# kills "video review", bare "vote" kills "vote of confidence", bare
# "highlights" kills "Liverpool highlights their defensive frailty". Every
# ambiguous word is anchored to a colon, a following word, or the title start.
#
# Narrowed after a false-positive audit: bare "vote for" killed governance votes
# ("Fifa members vote for Infantino"), bare "podcast"/"on tv" killed stories
# ABOUT podcasts and punditry, bare "sign up" killed "Arsenal sign up to
# charter", bare "quiz" killed "Police quiz player", bare "gossip" killed
# "Klopp dismisses transfer gossip". A hard delete has to be sure.
_NOT_POSTABLE_RE = re.compile(
    # Title-initial "Watch ..." is always a video stub; "Watch out ..." is news.
    r"^watch (?!out\b)"
    # Colon-labelled media items: "Watch:", "Video:", "Listen:", "Highlights:".
    r"|\b(watch|video|listen|highlights|gallery|pictures|photos)\s*:"
    # "Live:" / "Highlights -" were the two junk shapes that walked through.
    r"|^(live|highlights)\s*[:\-–]"
    r"|\b("
    r"quiz (of|answers)|how well do you know|test yourself|who am i|guess the|"
    r"how to watch|where to watch|how to follow|what channel|tv schedule|tv guide|"
    r"live on (bbc|sky|itv|tnt|amazon|prime|dazn)|"
    r"live (text|blog|updates?|coverage)|as it happened|minute-by-minute|"
    r"(subscribe|sign up) (for|to) (our|the|bbc)|newsletter|"
    r"(transfer|football|saturday's|sunday's|monday's) gossip|gossip column|rumour mill|"
    r"transfer round-?up|"
    r"betting (tips|odds|preview)|bet builder|best bets|accumulator|"
    r"have your say|vote (now|in our)|pick your"
    r")\b"
)


def _is_postable(title: str) -> bool:
    return not _NOT_POSTABLE_RE.search(title.lower())


def _categorize(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    for category, rx in _CATEGORY_RES:
        if rx.search(text):
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
            # Only the FIRST 2-4 digit segment is the size — the next one is
            # the CPS asset bucket, and rewriting it 404s 16% of the feed.
            # 1536 not 976: the photo box is 1080x760, so 976 came out upscaled.
            url = re.sub(r'/\d{2,4}/', '/1536/', url, count=1)
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


# Longest alias first so "real sociedad" is never read as "real madrid" and
# "manchester city" never degrades to a bare "manchester".
_TEAM_RE = re.compile(
    r'\b(' + '|'.join(sorted(map(re.escape, _MAJOR_TEAMS), key=len, reverse=True)) + r')\b')


def _event_key(t: str) -> tuple[frozenset, frozenset]:
    """(teams named, scorelines) — the cheap identity of one football event."""
    low = t.lower()
    # Scores sorted: "Arsenal 2-1 Chelsea" and "Chelsea 1-2 Arsenal" are one game.
    return (frozenset(_TEAM_RE.findall(low)),
            frozenset(tuple(sorted(map(int, re.split(r'[-–]', s))))
                      for s in _SCORELINE_RE.findall(low)))


def same_event(a: str, b: str) -> bool:
    """True if two headlines from different outlets cover the same story.

    Every source runs its own piece on a big match or transfer, and each gets
    a different id (the id is a hash of the link), so without this the page
    posts the same news five times in five minutes.
    """
    def tokens(t: str) -> set[str]:
        words = re.findall(r"[a-z0-9']+", t.lower())
        return {w for w in words if w not in _STOP_WORDS and len(w) > 2}

    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    # Word overlap alone cannot tell "beat Chelsea 2-1" from "beat Chelsea 3-0",
    # so decide on the event key first and only fall back to overlap.
    (team_a, score_a), (team_b, score_b) = _event_key(a), _event_key(b)
    if score_a and score_b and score_a.isdisjoint(score_b):
        return False                       # two different games
    # The team key alone is not an event: "Arsenal beat Chelsea" and "Arsenal
    # charged by FA over Chelsea tunnel clash" name the same two clubs and are
    # different stories. Since a collapse here deletes a story permanently,
    # require the wording to agree too — or both sides to carry the same score.
    overlap = len(ta & tb) / min(len(ta), len(tb))
    if team_a == team_b and team_a and (
            (len(team_a) > 1 and overlap >= 0.5) or (score_a and score_b)):
        return True                        # same cast, no contradicting score
    if (team_a - team_b) and (team_b - team_a):
        return False                       # each names a club the other doesn't
    if len(ta - tb) == 1 and len(tb - ta) == 1:
        return False                       # one swapped word each: sign a striker
                                           # vs sign a goalkeeper is two transfers
    # Jaccard over the smaller headline: tolerates one outlet being wordier.
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.5


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

            if _too_old(entry):
                continue

            description = _strip_html(
                entry.get("summary", entry.get("description", ""))
            ).strip()

            if not _is_football(title, description):
                continue

            if not _is_postable(title):
                continue

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
                    "age_hours":     _age_hours(entry),
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


def _demo() -> None:
    """Regressions the reject-list and dedup have already caused once."""
    # football stories that earlier substring matching wrongly dropped
    assert _is_football("Is World Cup sell-off a step too far?", "a high stakes plan")
    assert _is_football("Arsenal score the opening goal at the Emirates")
    assert _is_football("Van Gaal returns to management")
    assert _is_football("Boxing Day fixtures confirmed for the Premier League")
    assert _is_football("Rangers hurling abuse at referee is unacceptable") is False
    # genuine other-sport stories must still go
    assert not _is_football("Doyle: Diamond Necklace to sparkle in Nassau Stakes")
    assert not _is_football("Who will win the AIG Women's Open?", "golf major preview")
    assert not _is_football("England name Ashes squad", "test match cricket")

    # freshness window: only genuinely new news is eligible
    import time as _t, calendar as _c
    def _entry(minutes_old: float) -> dict:
        return {"published_parsed": _t.gmtime(_c.timegm(_t.gmtime()) - minutes_old * 60)}
    assert not _too_old(_entry(0))        # just published
    assert not _too_old(_entry(29))       # inside the 30-min default
    assert _too_old(_entry(31))           # stale
    assert _too_old(_entry(120))          # the 2h backlog that used to post
    assert not _too_old(_entry(-5))       # future-dated clocks skew, treat as now
    assert not _too_old({})               # undated entries are kept

    # same-event collapse
    assert same_event("Spain beat Portugal in Nations League final",
                      "Spain beat Portugal in the Nations League final")
    assert not same_event("Spain beat Portugal in final",
                          "Liverpool preparing opening bid for Barcola")
    assert not same_event("", "anything")
    # reversed subject order and a different verb still describe one event
    assert same_event("Arsenal 2-1 Chelsea", "Chelsea lose to Arsenal in thriller")
    assert same_event("Arsenal 2-1 Chelsea", "Chelsea 1-2 Arsenal")
    assert same_event("Spain beat Portugal in final", "Portugal beaten by Spain to lose final")
    # Deliberately NOT collapsed any more: one scoreline plus one shared club
    # also matched "Everton 3-0 Wigan" / "Everton sack their manager", and a
    # wrong collapse is permanent (mark_posted) while a miss costs one post.
    assert not same_event("Man City 3-0 Everton", "Haaland hat-trick sinks Everton")
    # ("Everton 3-0 Wigan" / "Everton sack their manager" still collapses, on the
    #  pre-existing 0.5 Jaccard fallback — not the team key. Raising that
    #  threshold also breaks "Liverpool sign Isak"/"Isak completes move", which
    #  sits at exactly 0.50, so it is left alone deliberately.)
    assert not same_event("Arsenal beat Chelsea in the Premier League",
                          "Arsenal charged by FA over Chelsea tunnel clash")
    assert same_event("Liverpool sign Isak for \u00a3120m", "Isak completes Liverpool move")
    # a different scoreline, opponent or object is a different event
    assert not same_event("Arsenal beat Chelsea 2-1", "Arsenal beat Chelsea 3-0")
    assert not same_event("Arsenal beat Chelsea", "Arsenal beat Tottenham")
    assert not same_event("Man Utd sign a striker", "Man Utd sign a goalkeeper")
    assert not same_event("Liverpool win the league", "Liverpool win the cup")
    # longest alias first: "Real Sociedad" is its own club, not "Real Madrid"
    assert _event_key("Real Madrid beat Real Sociedad")[0] == {"real madrid", "real sociedad"}
    assert same_event("Real Madrid beat Real Sociedad", "Real Sociedad lose to Real Madrid")
    assert not same_event("Inter Milan beat Napoli", "AC Milan beat Napoli")

    # keyword matching is on word boundaries: bare `in` scored "son" inside
    # "season", "win" inside "winger", "lose" inside "close"
    assert not _phrase_re(["son"]).search("a long season at anfield")
    assert not _phrase_re(["win"]).search("the new winger arrives")
    assert not _phrase_re(["down"]).search("memories of lockdown")
    assert not _phrase_re(["final"]).search("he finally scored")
    assert not _phrase_re(["lose", "ft "]).search("close to a deal, he left")
    assert _phrase_re(["son"]).search("son heung-min scores")
    assert _phrase_re(["win"]).search("spurs win late")
    assert not _phrase_re([]).search("anything")   # empty bucket matches nothing

    # phrases with non-word edges must not get a \b they can never satisfy
    for _p, _s in [("ft:", "ft: arsenal 2-1 chelsea"), ("\u00a350m", "a \u00a350m deal"),
                   ("\u20ac100m", "a \u20ac100m bid"), ("eto'o", "samuel eto'o scored"),
                   ("st. pauli", "st. pauli stun bayern"), ("nil-nil", "a dull nil-nil"),
                   ("champions!", "liverpool are champions!"),
                   ("u21 championship", "england win the u21 championship"),
                   ("spot-kicks", "decided on spot-kicks"),
                   ("back-to-back", "back-to-back titles"),
                   ("$100m", "a $100m package"), ("ko:", "ko: 20:00 bst"),
                   ("h2h", "the h2h record"), ("3-0", "united win 3-0")]:
        assert _phrase_re([_p]).search(_s), _p
    assert not _phrase_re(["3-0"]).search("a 13-0 rout")
    assert not _phrase_re(["ko:"]).search("tko: not football")

    # "ronaldo" and "cristiano ronaldo" are both listed - one man, one hit
    assert len(set(_HOF_RE.findall("cristiano ronaldo scores again"))) == 1
    assert len(set(_HOF_RE.findall("messi and ronaldo meet again"))) == 2

    # end to end: "season" picked a Son Heung-min photo, "feels" read as a
    # transfer "fee", "wonder goal" as a "won"
    assert "Son Heung-min Tottenham football" not in extract_pexels_queries(
        "Klopp reflects on a long season at Anfield")
    assert _categorize("Guardiola feels the pressure", "") == "Football News"
    assert extract_pexels_queries("A wonder goal from 30 yards")[0] == \
        "football goal celebration player"

    # score aggregation: one player named two ways is one hit, and keyword
    # density must not out-rank a terse real result (both were live bugs)
    assert _name_points(set(), 40) == 0
    assert _name_points({"ronaldo"}, 40) == 40
    assert _name_points({"ronaldo", "cristiano ronaldo"}, 40) == 40  # one man
    assert _name_points({"messi", "haaland"}, 40) == 60              # two men
    assert _name_points({str(i) for i in range(12)}, 40) < 80          # capped
    assert isinstance(score_story("Arsenal beat Chelsea 2-1"), int)
    assert score_story("") == 0
    assert score_story("Arsenal beat Chelsea 2-1") > score_story(
        "Ranked: the 20 best players - Messi, Ronaldo, Mbappe, Haaland, "
        "Bellingham, Salah, Kane, Modric, Neymar, Lewandowski, Benzema, Zidane")

    # Title signal beats the identical signal buried in a description: the card
    # is built from the headline, so that is what the score has to track.
    assert (score_story("Liverpool beat Arsenal 2-1", "")
            > score_story("A quiet day at the training ground",
                          "Liverpool beat Arsenal 2-1"))
    # ...but the description is discounted, not discarded.
    assert (score_story("A quiet day at the training ground",
                        "Liverpool beat Arsenal 2-1")
            > score_story("A quiet day at the training ground"))
    # The default is a no-op fast path.
    assert (score_story("Arsenal sign Guimaraes from Newcastle in \u00a375m deal")
            == score_story("Arsenal sign Guimaraes from Newcastle in \u00a375m deal", ""))
    assert isinstance(score_story("Chelsea beat Juventus", "Full time."), int)

    # explain_story must add up to what score_story returned, or --preview lies.
    _t, _d = "Liverpool beat Arsenal 2-1", "Messi scores a hat-trick of goals"
    assert sum(p for p, _, _, s in explain_story(_t, _d) if s == "title") \
        == score_story(_t)
    assert sum(p for p, _, _, s in explain_story(_t, _d) if s == "desc") \
        == score_story(_d)
    # buckets are labelled by their own first phrase, not by what matched
    assert {t for _, _, t, _ in explain_story(_t, _d)} >= {"beats", "scoreline",
                                                           "hall-of-fame"}
    assert explain_story("") == []
    assert _TRACE is None                     # sink never left on for the poll

    # non-postable formats: no standalone image card exists in these
    assert not _is_postable("How to watch: Liverpool v Spurs on TV")
    assert not _is_postable("Quiz: how well do you know the Premier League?")
    assert not _is_postable("Who am I? Guess Premier League star No 20")
    assert not _is_postable("Arsenal v Chelsea - as it happened")
    assert not _is_postable("Premier League live updates: Saturday's games")
    assert not _is_postable("Barca make second bid for Rodri - Sunday's gossip")
    assert not _is_postable("Watch: Haaland's hat-trick against Wolves")
    assert not _is_postable("Watch Guimaraes' best moments after Arsenal sign him")
    assert not _is_postable("Highlights: Arsenal 3-0 Leeds United")
    assert not _is_postable("Betting tips: best odds for Saturday's games")
    assert not _is_postable("Have your say: who was the player of the month?")
    assert not _is_postable("Subscribe to the Match of the Day podcast")
    # word-boundary traps - each of these killed real news when tried as substrings
    assert _is_postable("Live wire Saka fires Arsenal to victory")
    assert _is_postable("Watch out for Haaland, warns Guardiola")
    assert _is_postable("Real Madrid's video review controversy")
    assert _is_postable("Vote of confidence for under-fire boss")
    assert _is_postable("Liverpool highlights their defensive frailty")
    assert _is_postable("Arsenal sign up-and-coming striker from Reims")
    assert _is_postable("Guardiola quizzed on Haaland future")
    assert _is_postable("A youngster to watch at each Premier League club")
    # match_fetcher's synthetic cards must survive
    assert _is_postable("Arsenal 3-0 Leeds United")
    assert _is_postable("Arsenal vs Leeds United")

    # BBC ichef urls carry TWO 2-4 digit segments - the size and the CPS asset
    # bucket. A greedy sub rewrote both and 404'd 10 of 63 live entries.
    two = {"media_thumbnail": [{"url":
        "https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/7161/live/b7e91bd0.jpg"}]}
    assert _extract_rss_image(two) == (
        "https://ichef.bbci.co.uk/ace/standard/1536/cpsprodpb/7161/live/b7e91bd0.jpg")
    one = {"media_thumbnail": [{"url":
        "https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/de50/live/00229450.jpg"}]}
    assert _extract_rss_image(one) == (
        "https://ichef.bbci.co.uk/ace/standard/1536/cpsprodpb/de50/live/00229450.jpg")
    # An imageless story is not an error - match_fetcher emits article_image=""
    # for every fixture and result card, and image_fetcher has six more rungs.
    assert _extract_rss_image({}) == ""

    # post filter: real news outranks filler
    _T = 50   # BREAKING_THRESHOLD default, see main.py:_threshold
    assert score_story("Real Madrid thrash Barcelona 4-0 in El Clasico") > 100
    assert score_story("Nygren header earns Celtic opening victory against Dundee") > _T
    assert score_story("Argentina beat France on penalties to win the World Cup final") > 200
    assert score_story("Birmingham sign striker Effa Effa from Le Havre") > _T
    assert score_story("Man City agree deal to sign Marseille keeper Rulli") > _T
    # transfer speculation is the lowest-value content type and must not post
    assert score_story("Barca make second bid for Rodri - Sunday's gossip") < _T
    assert score_story("Chelsea reportedly eyeing a move for Osimhen") < _T
    assert score_story("Liverpool linked with a move for Araujo, reports suggest") < _T
    assert (score_story("Nygren header earns Celtic opening victory against Dundee")
            > score_story("Barca make second bid for Rodri - Sunday's gossip"))
    # quizzes, explainers and fixture-list pieces are not breaking news
    assert score_story("What is the World Cup prize money?") < _T          # was 370
    assert score_story("When is the EFL Cup second-round draw?") < _T      # "draw" was +175
    assert score_story("Who will exit Chelsea? How Blues could cut 41-man squad") < _T
    assert score_story("How to follow the new football season on BBC Sport") < _T
    assert score_story("What are the key dates for the 2026-27 football season?") < _T
    # structural: one result bucket, and the generic phrases stay deleted
    assert sum(1 for phrases, _ in _BREAKING_SIGNALS if "beat" in phrases) == 1
    assert sum(1 for phrases, _ in _BREAKING_SIGNALS if "victory" in phrases) == 1
    for _p in ("win", "draw", "exit", "down", "goal", "final", "says", "claims",
               "book", "held", "lost", "son", "gabriel", "kane", "rice", "diaz"):
        assert not any(_p in phrases for phrases, _ in _BREAKING_SIGNALS), _p
    print("OK")


if __name__ == "__main__":
    _demo()
