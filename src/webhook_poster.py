"""
Webhook-based Facebook posting via Make.com.

Sends the image as a multipart file upload directly to the Make.com webhook.
No external image host needed — works from GitHub Actions or anywhere.

Required env vars:
  MAKE_WEBHOOK_URL       — Make.com: Webhook → Facebook → Create Page Photo Post
  MAKE_REEL_WEBHOOK_URL  — Make.com: Webhook → Facebook → Create Page Video Post

Make.com field mapping:
  Message  → {{1.message}}
  Photo    → {{1.photo}}      (binary file, not a URL)
"""

import os
from io import BytesIO

import requests
from PIL import Image


def post_via_webhook(caption: str, image: Image.Image) -> str:
    webhook_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("MAKE_WEBHOOK_URL not set in .env.")

    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90, optimize=True)
    buf.seek(0)

    print("    Sending image directly to Make.com…")
    r = requests.post(
        webhook_url,
        data={"message": caption},
        files={"photo": ("football_news.jpg", buf, "image/jpeg")},
        timeout=60,
    )
    r.raise_for_status()
    return "posted"


def post_reel_via_webhook(caption: str, video_path: str) -> str:
    webhook_url = os.getenv("MAKE_REEL_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("MAKE_REEL_WEBHOOK_URL not set in .env.")

    with open(video_path, "rb") as f:
        print("    Sending video directly to Make.com…")
        r = requests.post(
            webhook_url,
            data={"message": caption},
            files={"video": ("football_reel.mp4", f, "video/mp4")},
            timeout=120,
        )
    r.raise_for_status()
    return "posted"
