import subprocess
from pathlib import Path

from PIL import Image

from src import reel_creator


def test_song_routing(monkeypatch, tmp_path):
    songs = tmp_path / "songs"
    for mood in reel_creator.MOODS:
        folder = songs / mood
        folder.mkdir(parents=True)
        (folder / f"{mood}.wav").write_bytes(b"audio")
    monkeypatch.setattr(reel_creator, "SONGS_DIR", songs)
    for mood in reel_creator.MOODS:
        assert reel_creator.select_song(mood).parent.name == mood


def test_reel_is_vertical_ten_seconds_with_audio(tmp_path):
    image = tmp_path / "post.jpg"
    audio = tmp_path / "audio.wav"
    video = tmp_path / "reel.mp4"
    Image.new("RGB", (1080, 1350), "navy").save(image)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(audio)], check=True, capture_output=True)
    assert reel_creator.create_reel(image, video, audio)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "default=noprint_wrappers=1", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    assert "width=1080" in probe and "height=1920" in probe and "codec_type=audio" in probe
    assert 9.8 <= float(probe.split("duration=")[-1].splitlines()[0]) <= 10.2
