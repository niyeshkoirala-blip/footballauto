#!/usr/bin/env python3
"""Verify one Make post URL using the production multipart upload format."""

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw

from src.webhook_poster import post_to_url


def _url(argv: list[str]) -> str | None:
    if len(argv) != 2:
        return None
    value = argv[1].strip()
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "invalid-host"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}/…"


def main() -> int:
    url = _url(sys.argv)
    if not url:
        print("Usage:\n  python3 sendpostdata.py <POST_MAKE_URL>")
        return 2

    test_id = f"SETUP-TEST-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    caption = ("[TEST POST] Football Automation URL Verification\n"
               "This is a fake setup test, not football news.\n"
               f"Test ID: {test_id}")
    print("=" * 40 + "\nPOST URL TEST\n" + "=" * 40)
    print(f"URL: {_safe_url(url)}\nTest ID: {test_id}\nSending test payload…")
    try:
        with tempfile.TemporaryDirectory(prefix="football-post-test-") as directory:
            image_path = Path(directory) / "test-post.jpg"
            image = Image.new("RGB", (1080, 1350), "#123c75")
            draw = ImageDraw.Draw(image)
            draw.text((60, 90), "TEST POST\nNOT FOOTBALL NEWS", fill="white", spacing=18)
            image.save(image_path, format="JPEG", quality=90)
            response = post_to_url(url, caption, "photo", "football_setup_test.jpg",
                                   image_path.read_bytes(), "image/jpeg", 60)
        print(f"HTTP Status: {response.status_code}\nResult: SUCCESS")
        print("This URL appears compatible with the production post publisher.")
        return 0
    except Exception as exc:
        reason = str(exc).replace(url, _safe_url(url))
        print(f"Result: FAILED\nThe URL could not be verified.\nReason: {reason}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
