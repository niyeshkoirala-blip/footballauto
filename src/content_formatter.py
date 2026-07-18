import os
import textwrap

CATEGORY_HASHTAGS = {
    "Champions League":  "#ChampionsLeague #UCL #UEFA #EuropeanFootball",
    "Transfer News":     "#TransferNews #FootballTransfers #Transfers #TransferWindow",
    "Premier League":    "#PremierLeague #EPL #EnglishFootball",
    "La Liga":           "#LaLiga #SpanishFootball #ElClasico",
    "Bundesliga":        "#Bundesliga #GermanFootball",
    "Serie A":           "#SerieA #ItalianFootball",
    "Ligue 1":           "#Ligue1 #FrenchFootball #PSG",
    "International":     "#Football #International #WorldCup #NationsLeague",
    "Top Players":       "#Football #Soccer #TopPlayers #GOAT",
    "Football News":     "#Football #Soccer #FootballNews",
}

CATEGORY_EMOJI = {
    "Champions League":  "🏆",
    "Transfer News":     "🔄",
    "Premier League":    "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "La Liga":           "🇪🇸",
    "Bundesliga":        "🇩🇪",
    "Serie A":           "🇮🇹",
    "Ligue 1":           "🇫🇷",
    "International":     "🌍",
    "Top Players":       "⭐",
    "Football News":     "⚽",
}


def _groq_caption(story: dict, api_key: str) -> str | None:
    """Use Groq's free Llama model to write an engaging caption."""
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = (
            "You are a social media manager for a hugely popular football Facebook page with millions of fans.\n\n"
            f"Write a detailed, engaging Facebook post caption for this story:\n"
            f"Title: {story['title']}\n"
            f"Category: {story['category']}\n"
            f"Summary: {story['description']}\n"
            f"Source: {story['source']}\n\n"
            "Structure the caption EXACTLY like this:\n"
            "1. HOOK LINE — one punchy sentence with a strong emoji (🔥⚽🚨🏆💥) that grabs attention immediately\n"
            "2. Blank line\n"
            "3. CONTEXT — 3 to 4 sentences expanding the story. Include relevant historical context, "
            "   stats, what it means for the teams/players/tournament, and why fans should care.\n"
            "4. Blank line\n"
            "5. ENGAGEMENT — one question to get fans talking (e.g. 'What do you think?', 'Who wins the title now?')\n"
            "6. Blank line\n"
            "7. HASHTAGS — 8 to 12 hashtags. They MUST include the specific players, teams, and competition "
            "   mentioned in the story (e.g. #ViniciusJr #Brazil #WorldCup2026). Add 2-3 broader tags "
            "   (#Football #Soccer) but keep the rest story-specific. All on one line.\n"
            "8. Blank line\n"
            "9. HASHTAGS only — no source line, that is added separately.\n\n"
            "Rules:\n"
            "- Do NOT use markdown bold (**text**) — plain text only\n"
            "- Tone: passionate, knowledgeable, fan-facing — like a real football supporter writing this\n"
            "- Keep total length under 500 words\n"
            "- Write ONLY the caption. No preamble, no 'Here is the caption:'."
        )
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.75,
        )
        caption = completion.choices[0].message.content.strip()
        return caption + f"\n\n📰 Source: {story['source']}"
    except Exception as e:
        print(f"  [content_formatter] Groq error (using fallback): {e}")
        return None


def judge_stories(stories: list[dict]) -> dict[str, int] | None:
    """
    One batched Groq call: rate each story 0-10 for post-worthiness.
    Returns {story_id: rating}, or None on any failure (caller falls
    back to keyword-score order).
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or not stories:
        return None
    try:
        import json
        import re

        from groq import Groq

        numbered = "\n".join(
            f"{i}. {s['title']} — {s.get('description', '')[:200]}"
            for i, s in enumerate(stories)
        )
        prompt = (
            "You run a hugely popular football fan Facebook page limited to a few "
            "posts per day, so only genuinely hot news makes the cut.\n\n"
            "Rate each story below 0-10 for post-worthiness:\n"
            "- 8-10: dramatic match results, major confirmed transfers, big-name "
            "player/manager news, title/elimination moments\n"
            "- 4-7: solid news fans care about but not unmissable\n"
            "- 0-3: quizzes, TV schedules, how-to guides, minor features, "
            "speculation, filler\n\n"
            f"Stories:\n{numbered}\n\n"
            'Reply with ONLY a JSON array like [{"i": 0, "rating": 9}, ...] '
            "covering every story. No other text."
        )
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0,
        )
        text = completion.choices[0].message.content
        match = re.search(r"\[.*\]", text, re.DOTALL)   # tolerate stray prose
        ratings = {}
        for item in json.loads(match.group(0)):
            i = int(item["i"])
            if 0 <= i < len(stories):
                ratings[stories[i]["id"]] = int(item["rating"])
        return ratings or None
    except Exception as e:
        print(f"  [content_formatter] Groq judge error (using keyword order): {e}")
        return None


def format_caption(story: dict) -> str:
    """Return a detailed Facebook post caption for the story."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key:
        result = _groq_caption(story, api_key)
        if result:
            return result

    # ── Fallback: structured caption from RSS data ──────────────────────
    emoji = CATEGORY_EMOJI.get(story["category"], "⚽")
    hashtags = CATEGORY_HASHTAGS.get(story["category"], "#Football #Soccer")

    lines = [f"{emoji} {story['title'].upper()}", ""]

    if story.get("description"):
        lines += [story["description"], ""]

    lines += [
        "What do you think? Drop your thoughts in the comments! 👇",
        "",
        hashtags + " #FootballNews #Football",
        "",
        f"📰 Source: {story['source']}",
    ]
    return "\n".join(lines)


def format_image_brief(story: dict) -> str:
    """Return a short (≤160 chars) description text to overlay on the image."""
    text = story.get("description", "") or story["title"]
    # Strip any leftover URL-like fragments
    import re
    text = re.sub(r"https?://\S+", "", text).strip()
    if len(text) <= 160:
        return text
    # Cut at the last word boundary before 160 chars
    return text[:160].rsplit(" ", 1)[0].rstrip(",.;:") + "..."
