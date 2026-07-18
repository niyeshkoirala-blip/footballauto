"""
Webhook-based Facebook posting via Make.com.

Sends the image/video as a multipart file upload directly to a Make.com webhook.
No external image host needed — works from GitHub Actions or anywhere.

MAKE_WEBHOOK_URL / MAKE_REEL_WEBHOOK_URL may hold MULTIPLE comma-separated URLs
(one per Make.com free-tier account). Each post picks a random one to spread
load across accounts, and falls through to the others if one errors — so five
free accounts give ~5x the monthly quota.

Make.com field mapping:
  Message  → {{1.message}}
  Photo    → {{1.photo}}   (binary file, not a URL)
"""

import os
import random
from io import BytesIO

import requests
from PIL import Image


def _webhooks(env_name: str) -> list[str]:
    raw = os.getenv(env_name, "").replace("\n", ",")
    return [u.strip() for u in raw.split(",") if u.strip()]


def _post(env_name: str, caption: str, field: str,
          filename: str, blob: bytes, mime: str, timeout: int) -> str:
    urls = _webhooks(env_name)
    if not urls:
        raise RuntimeError(f"{env_name} not set in .env.")
    random.shuffle(urls)  # spread posts evenly across accounts

    last_err = None
    for url in urls:
        try:
            r = requests.post(
                url,
                data={"message": caption},
                files={field: (filename, blob, mime)},  # bytes → reusable across retries
                timeout=timeout,
            )
            if r.status_code >= 400:
                # Make puts the reason in the body, e.g. "There is no scenario
                # listening for this webhook" (scenario OFF or out of operations)
                raise RuntimeError(f"{r.status_code}: {r.text[:150]}")
            return "posted"
        except Exception as e:  # ponytail: retries next account. Make returns 200 even
            last_err = e         # when out of ops, so this only catches hard errors —
            print(f"    webhook {url[:45]}… failed: {e}; trying next account")
    raise RuntimeError(f"all {len(urls)} webhook(s) failed: {last_err}")


def post_via_webhook(caption: str, image: Image.Image) -> str:
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90, optimize=True)
    print("    Sending image to Make.com…")
    return _post("MAKE_WEBHOOK_URL", caption, "photo",
                 "football_news.jpg", buf.getvalue(), "image/jpeg", 60)


def post_reel_via_webhook(caption: str, video_path: str) -> str:
    with open(video_path, "rb") as f:
        blob = f.read()
    print("    Sending video to Make.com…")
    return _post("MAKE_REEL_WEBHOOK_URL", caption, "video",
                 "football_reel.mp4", blob, "video/mp4", 120)


def _demo() -> None:
    os.environ["X"] = "https://a.test/1 ,\n https://b.test/2,https://c.test/3"
    assert _webhooks("X") == ["https://a.test/1", "https://b.test/2", "https://c.test/3"]
    os.environ["X"] = "https://only.test/1"
    assert _webhooks("X") == ["https://only.test/1"]
    assert _webhooks("MISSING_ENV_VAR") == []
    print("OK")


if __name__ == "__main__":
    _demo()
