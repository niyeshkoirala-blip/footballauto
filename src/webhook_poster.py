"""
Webhook-based Facebook posting via Make.com.

How it works:
  1. Uploads image/video to catbox.moe (free, no account or API key needed).
  2. POSTs the public URL + caption to your Make.com webhook.
  3. Make.com calls Facebook's Graph API and publishes the post/reel.

Required env vars:
  MAKE_WEBHOOK_URL       — Make.com scenario: Webhook → Facebook → Create Page Photo Post
  MAKE_REEL_WEBHOOK_URL  — Make.com scenario: Webhook → Facebook → Create Page Video Post
"""

import os
from io import BytesIO

import requests
from PIL import Image


def _upload_to_catbox(data: bytes, filename: str, mime: str) -> str:
    """Upload raw bytes to catbox.moe. Returns public URL."""
    r = requests.post(
        "https://catbox.moe/user/api.php",
        data={"reqtype": "fileupload"},
        files={"fileToUpload": (filename, data, mime)},
        timeout=60,
    )
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"catbox.moe upload failed: {url}")
    return url


def post_via_webhook(caption: str, image: Image.Image) -> str:
    webhook_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("MAKE_WEBHOOK_URL not set in .env.")

    print("    Uploading image to catbox.moe…")
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=95, optimize=True)
    image_url = _upload_to_catbox(buf.getvalue(), "football_news.jpg", "image/jpeg")
    print(f"    Image: {image_url}")

    print("    Sending to Make.com webhook…")
    r = requests.post(webhook_url, json={"message": caption, "photo_url": image_url}, timeout=30)
    r.raise_for_status()
    return image_url


def post_reel_via_webhook(caption: str, video_path: str) -> str:
    webhook_url = os.getenv("MAKE_REEL_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise RuntimeError("MAKE_REEL_WEBHOOK_URL not set in .env.")

    print("    Uploading reel to catbox.moe…")
    with open(video_path, "rb") as f:
        video_data = f.read()
    video_url = _upload_to_catbox(video_data, "football_reel.mp4", "video/mp4")
    print(f"    Video: {video_url}")

    print("    Sending reel to Make.com webhook…")
    r = requests.post(webhook_url, json={"message": caption, "video_url": video_url}, timeout=30)
    r.raise_for_status()
    return video_url
