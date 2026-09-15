"""Make.com webhook publishing with account rotation for photos and Reels."""

import os
import random
from io import BytesIO

import requests
from PIL import Image


def _webhooks(env_name: str) -> list[str]:
    """Read one or more comma/newline-separated webhook URLs from the environment."""
    raw = os.getenv(env_name, "").replace("\n", ",")
    return [url.strip() for url in raw.split(",") if url.strip()]


def _validate_response(response: requests.Response) -> None:
    """Apply the same success rules to production and manual setup uploads."""
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:150]}")
    response_text = response.text.lower()
    if any(term in response_text for term in ("credit exhausted", "quota exceeded", "operations exhausted")):
        raise RuntimeError(f"account quota failure: {response.text[:150]}")


def post_to_url(url: str, caption: str, field: str, filename: str,
                blob: bytes, mime: str, timeout: int) -> requests.Response:
    """Send one multipart upload using the exact production webhook contract.

    This deliberately does not consult environment variables or rotate URLs;
    setup utilities use it to verify precisely the URL supplied by the user.
    """
    response = requests.post(url, data={"message": caption},
                             files={field: (filename, blob, mime)}, timeout=timeout)
    _validate_response(response)
    return response


def _post(env_name: str, caption: str, field: str, filename: str,
          blob: bytes, mime: str, timeout: int) -> str:
    urls = _webhooks(env_name)
    if not urls:
        raise RuntimeError(f"{env_name} is not configured.")
    random.shuffle(urls)
    last_error: Exception | None = None
    for index, url in enumerate(urls, 1):
        try:
            post_to_url(url, caption, field, filename, blob, mime, timeout)
            return "posted"
        except Exception as exc:
            last_error = exc
            print(f"    Webhook account {index}/{len(urls)} failed: {exc}; trying next account.")
    raise RuntimeError(f"All {len(urls)} webhook account(s) failed: {last_error}")


def post_via_webhook(caption: str, image: Image.Image) -> str:
    """Publish the normal photo post through the configured account rotation."""
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90, optimize=True)
    return _post("MAKE_WEBHOOK_URL", caption, "photo", "football_news.jpg",
                 buffer.getvalue(), "image/jpeg", 60)


def post_reel_via_webhook(caption: str, video_path: str) -> str:
    """Publish a Reel through the matching, independently rotating accounts."""
    with open(video_path, "rb") as video:
        blob = video.read()
    return _post("MAKE_REEL_WEBHOOK_URL", caption, "video", "football_reel.mp4",
                 blob, "video/mp4", 180)
