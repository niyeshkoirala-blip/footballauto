"""Create a ten-second, 9:16 Reel from a completed football post image."""

import os
import random
import re
import subprocess
import time
from pathlib import Path

MOODS = {"happy", "energetic", "sad"}
REEL_DURATION = 10
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SONGS_DIR = PROJECT_ROOT / "songs"
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


def classify_mood(caption: str, retries: int = 3) -> str:
    """Ask Groq for one of the three supported moods, without guessing."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("    [REEL] GROQ_API_KEY is missing; using energetic fallback")
        return "energetic"
    try:
        from groq import Groq
    except Exception as exc:
        print(f"    [REEL] Groq client unavailable; using energetic fallback: {exc}")
        return "energetic"

    client = Groq(api_key=api_key)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            completion = client.chat.completions.create(
                # gpt-oss-20b is currently available through Groq and can be
                # overridden without code changes if the account has another model.
                model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
                messages=[
                    {"role": "user", "content": f"Football post to classify:\n{caption}"},
                    {"role": "user", "content": "Is it happy energetic or sad answer only with one"},
                ],
                # Reasoning-capable Groq models consume part of this budget
                # internally before emitting the required one-word response.
                max_tokens=512,
                temperature=0,
            )
            response = (completion.choices[0].message.content or "").strip().lower()
            mood = next((candidate for candidate in ("happy", "energetic", "sad")
                          if re.search(rf"\b{re.escape(candidate)}\b", response)), None)
            if mood:
                return mood
            last_error = RuntimeError(f"Groq returned invalid mood {response!r}")
        except Exception as exc:
            last_error = exc
        print(f"    [REEL] Mood classification attempt {attempt}/{retries} failed: {last_error}")
        if attempt < retries:
            time.sleep(attempt)
    print(f"    [REEL] Using energetic fallback after classification failure: {last_error}")
    return "energetic"


def select_song(mood: str) -> Path:
    """Select an audio file only from the requested mood directory."""
    mood = mood.strip().lower()
    if mood not in MOODS:
        raise ValueError(f"Unsupported Reel mood: {mood!r}")
    folder = SONGS_DIR / mood
    songs = ([path for path in folder.iterdir()
              if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS]
             if folder.is_dir() else [])
    if not songs:
        raise RuntimeError(f"No supported audio files found in {folder} for mood '{mood}'.")
    return random.choice(songs)


def create_reel(image_path: str | Path, output_path: str | Path, song_path: str | Path) -> bool:
    """Build a 1080x1920 MP4 with a preserved card and looping audio."""
    image_path, output_path, song_path = map(Path, (image_path, output_path, song_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video_filter = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=35:10[background];"
        "[0:v]scale=1040:1840:force_original_aspect_ratio=decrease[foreground];"
        "[background][foreground]overlay=(W-w)/2:(H-h)/2,format=yuv420p[out]"
    )
    command = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-stream_loop", "-1", "-i", str(song_path),
        "-filter_complex", video_filter, "-map", "[out]", "-map", "1:a:0",
        "-t", str(REEL_DURATION), "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        print("    [REEL] ffmpeg is not installed.")
        return False
    if result.returncode:
        print(f"    [REEL] ffmpeg failed: {result.stderr[-600:]}")
        return False
    return output_path.exists() and output_path.stat().st_size > 0
