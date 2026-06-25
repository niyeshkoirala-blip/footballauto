"""
Creates a 10-second Facebook Reel video from the post image.

Layout: 1080×1920 (9:16 vertical)
  ┌──────────────────┐
  │ blurred image bg │  ← full canvas, boxblur fill
  │   ┌──────────┐   │
  │   │ original │   │  ← sharp 1060×1060 centered
  │   │  image   │   │
  │   └──────────┘   │
  │                  │
  └──────────────────┘

Background music: funky groove generated offline with Python's wave module
(kick drum, snare, hi-hat, G-minor bass line — no downloads, no API keys needed).
Drop your own .mp3 / .wav files into the music/ folder to override with real tracks.
"""

import math
import random
import struct
import subprocess  # used by create_reel (ffmpeg)
import wave as _wave
from pathlib import Path

MUSIC_DIR     = Path("music")
REEL_DURATION = 10   # seconds


# ── Funky beat generator ───────────────────────────────────────────────────────

def _generate_funky_beat(path: str, duration: int = 15) -> bool:
    """
    Synthesise a drum-machine + bass-line groove and write it as a WAV file.
    BPM: 108  |  Key: G minor pentatonic  |  Pure Python — zero dependencies.
    """
    RATE  = 44100
    BPM   = 108
    step  = int(RATE * 60 / BPM / 4)   # samples per 16th note

    def kick(j: int) -> float:
        t = j / RATE
        freq = 80 * math.exp(-t * 8)
        return math.exp(-t * 10) * math.sin(2 * math.pi * freq * t) * 0.85

    def snare(j: int) -> float:
        t = j / RATE
        return math.exp(-t * 20) * (random.random() * 2 - 1) * 0.55

    def hat(j: int, closed: bool = True) -> float:
        t = j / RATE
        return math.exp(-t * (40 if closed else 8)) * (random.random() * 2 - 1) * 0.28

    def bass(j: int, freq: float) -> float:
        t = j / RATE
        env = min(1.0, t * 120) * math.exp(-t * 4)
        return env * (
            math.sin(2 * math.pi * freq * t) * 0.55
            + math.sin(2 * math.pi * freq * 2 * t) * 0.28
            + math.sin(2 * math.pi * freq * 3 * t) * 0.10
        ) * 0.45

    # 16-step patterns (one bar of 4/4)
    kicks  = [1,0,0,0, 0,0,1,0, 1,0,0,0, 0,0,1,0]
    snares = [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0]
    hats   = [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,1]
    # G minor pentatonic: G2=98 Hz, Bb2=117, C3=131, D3=147
    basses = [98,0,0,131, 98,0,117,0, 131,0,0,147, 98,0,0,0]

    total   = RATE * duration
    out     = [0.0] * total
    bar_len = step * 16

    for bar_start in range(0, total, bar_len):
        for si in range(16):
            s0 = bar_start + si * step
            for j in range(step):
                idx = s0 + j
                if idx >= total:
                    break
                v = 0.0
                if kicks[si]:
                    v += kick(j)
                if snares[si]:
                    v += snare(j)
                if hats[si]:
                    v += hat(j)
                if basses[si]:
                    v += bass(j, basses[si])
                out[idx] += v

    peak  = max(abs(s) for s in out) or 1.0
    scale = min(0.95, 0.78 / peak)
    data  = struct.pack(f"<{total}h", *(int(s * scale * 32767) for s in out))

    with _wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(data)
    return True


def _pick_track() -> Path | None:
    """
    Return a music file to use.
    Priority: user-added files in music/ → generated funky beat.
    """
    MUSIC_DIR.mkdir(exist_ok=True)
    user_tracks = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))
    if user_tracks:
        return random.choice(user_tracks)

    generated = MUSIC_DIR / "funky_beat.wav"
    if not generated.exists():
        print("  [reel] Generating funky groove track…")
        _generate_funky_beat(str(generated), duration=20)
        print(f"  [reel] Beat generated → {generated}")
    return generated


def create_reel(image_path: str, output_path: str = "reel_output.mp4") -> bool:
    """
    Build a 10-second 1080×1920 Reel MP4 from a JPEG image.
    Returns True on success.
    """
    # Blurred image fills the vertical canvas; sharp image sits centred on top
    vf = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=35:10[bg];"
        "[0:v]scale=1060:1060[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
    )

    track = _pick_track()

    if track:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", str(track),
            "-filter_complex", vf,
            "-map", "[out]", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-t", str(REEL_DURATION),
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            output_path,
        ]
        print(f"  [reel] Building reel with track: {track.stem}")
    else:
        # No music available — silent reel still works
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-filter_complex", vf,
            "-map", "[out]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-t", str(REEL_DURATION),
            output_path,
        ]
        print("  [reel] No music tracks found — building silent reel")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [reel] ffmpeg failed:\n{result.stderr[-600:]}")
        return False

    size_kb = Path(output_path).stat().st_size // 1024
    print(f"  [reel] Created {output_path} ({size_kb} KB)")
    return True
