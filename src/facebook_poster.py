"""
Posts an image + caption to a Facebook Page using Playwright browser automation.
No developer account or API key needed — only your normal FB email + password.

Session cookies are saved to fb_session.json after first login so the bot
does NOT re-login on every run (avoids triggering Facebook's security checks).
"""

import json
import os
import tempfile
import time
from io import BytesIO

from PIL import Image

SESSION_FILE = "fb_session.json"


# ── Session helpers ────────────────────────────────────────────────────────────

def _save_session(context) -> None:
    with open(SESSION_FILE, "w") as f:
        json.dump(context.cookies(), f)


def _load_session(context) -> bool:
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    return False


# ── Login ──────────────────────────────────────────────────────────────────────

def _login(page, email: str, password: str) -> None:
    page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
    page.locator("#email").fill(email)
    page.locator("#pass").fill(password)
    page.locator('[name="login"]').click()
    page.wait_for_timeout(4000)

    if "login" in page.url or "checkpoint" in page.url:
        raise RuntimeError(
            "Facebook login failed. Check your email/password in .env, "
            "or Facebook asked for a security check — log in manually first to clear it."
        )


def _is_logged_in(page) -> bool:
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    return "login" not in page.url and "checkpoint" not in page.url


# ── Post creation ──────────────────────────────────────────────────────────────

def _click_composer(page) -> None:
    """Click the 'Write something' post composer on the page."""
    selectors = [
        '[aria-label="Create a public post…"]',
        '[placeholder="Write something..."]',
        '[placeholder*="Write something"]',
        '[data-testid="status-attachment-mentions-input"]',
        'div[role="button"]:has-text("Write something")',
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(1200)
                return
        except Exception:
            continue
    # Last resort — click the top of the page's post box area
    page.locator('div[role="main"]').first.click()
    page.wait_for_timeout(1000)


def _type_caption(page, caption: str) -> None:
    """Type (or paste) the caption into the open composer."""
    # Use JavaScript clipboard injection — reliable for long text
    page.evaluate(
        """(text) => {
            const el = document.querySelector('[data-lexical-editor="true"]')
                    || document.querySelector('[contenteditable="true"][role="textbox"]')
                    || document.querySelector('[contenteditable="true"]');
            if (el) {
                el.focus();
                document.execCommand('insertText', false, text);
            }
        }""",
        caption,
    )
    page.wait_for_timeout(600)


def _upload_photo(page, image_path: str) -> None:
    """Attach a photo to the open composer."""
    # Click 'Photo/Video' button
    photo_btn_selectors = [
        '[aria-label="Photo/video"]',
        '[aria-label*="Photo"]',
        'div[role="button"]:has-text("Photo")',
        '[data-testid="photo-video"]',
    ]
    for sel in photo_btn_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            continue

    # Set file on the hidden <input type="file">
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(image_path)
    page.wait_for_timeout(4000)   # wait for upload + thumbnail


def _click_post(page) -> None:
    """Click the Post / Share button to publish."""
    post_btn_selectors = [
        '[aria-label="Post"]',
        'div[aria-label="Post"][role="button"]',
        'div[role="button"]:has-text("Post"):not([aria-label*="cancel"])',
        'button:has-text("Post")',
    ]
    for sel in post_btn_selectors:
        try:
            btn = page.locator(sel).last
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(5000)
                return
        except Exception:
            continue
    raise RuntimeError("Could not find the Post button. Facebook UI may have changed.")


# ── Reel upload ────────────────────────────────────────────────────────────────

def _upload_video_reel(page, video_path: str) -> None:
    """Upload a video file and elect to share as Reel when Facebook offers the choice."""
    photo_btn_selectors = [
        '[aria-label="Photo/video"]',
        '[aria-label*="Photo"]',
        'div[role="button"]:has-text("Photo")',
        'div[role="button"]:has-text("Video")',
    ]
    for sel in photo_btn_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            continue

    # Upload the video file
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(video_path)
    page.wait_for_timeout(8000)   # video processing takes longer than images

    # If Facebook shows a "Share as Reel" / "Reel" option, select it
    reel_selectors = [
        'div[role="radio"]:has-text("Reel")',
        'div[role="button"]:has-text("Share as a reel")',
        'label:has-text("Reel")',
        'span:has-text("Reel")',
    ]
    for sel in reel_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click()
                page.wait_for_timeout(1500)
                print("    Selected 'Reel' format.")
                break
        except Exception:
            continue


# ── Public API ─────────────────────────────────────────────────────────────────

def post_reel_to_facebook(
    caption: str,
    video_path: str,
    page_id: str,
    access_token: str = "",
) -> str:
    """Upload a short video as a Facebook Reel (reuses saved login session)."""
    from playwright.sync_api import sync_playwright

    fb_email    = os.getenv("FB_EMAIL", "").strip()
    fb_password = os.getenv("FB_PASSWORD", "").strip()
    page_url    = os.getenv("FB_PAGE_URL", "").strip()

    if not fb_email or not fb_password:
        raise RuntimeError("FB_EMAIL and FB_PASSWORD must be set in .env")
    if not page_url and not page_id:
        raise RuntimeError("Set FB_PAGE_URL in .env")

    target_url = page_url or f"https://www.facebook.com/{page_id}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        session_ok = _load_session(context)
        fb_page = context.new_page()

        if not session_ok or not _is_logged_in(fb_page):
            print("    Logging in to Facebook…")
            _login(fb_page, fb_email, fb_password)
            _save_session(context)
        else:
            print("    Reusing saved Facebook session.")

        fb_page.goto(target_url, wait_until="domcontentloaded")
        fb_page.wait_for_timeout(2500)

        _click_composer(fb_page)
        _upload_video_reel(fb_page, video_path)
        _type_caption(fb_page, caption)
        _click_post(fb_page)

        post_url = fb_page.url
        browser.close()

    return post_url or "reel posted"


def post_to_facebook(
    caption: str,
    image: Image.Image,
    page_id: str,          # Facebook page username or numeric ID
    access_token: str = "", # unused — kept for API compatibility
) -> str:
    """Log in to Facebook (reusing saved session) and publish the post."""
    from playwright.sync_api import sync_playwright

    fb_email    = os.getenv("FB_EMAIL", "").strip()
    fb_password = os.getenv("FB_PASSWORD", "").strip()
    page_url    = os.getenv("FB_PAGE_URL", "").strip()

    if not fb_email or not fb_password:
        raise RuntimeError(
            "FB_EMAIL and FB_PASSWORD must be set in .env for browser-based posting."
        )
    if not page_url and not page_id:
        raise RuntimeError("Set FB_PAGE_URL in .env (e.g. https://www.facebook.com/YourPageName)")

    target_url = page_url or f"https://www.facebook.com/{page_id}"

    # Save image to a temp file (Playwright needs a real file path)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image.save(tmp, format="JPEG", quality=95, optimize=True)
        image_path = tmp.name

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )

            # Try to reuse saved session
            session_ok = _load_session(context)
            fb_page = context.new_page()

            if not session_ok or not _is_logged_in(fb_page):
                print("    Logging in to Facebook…")
                _login(fb_page, fb_email, fb_password)
                _save_session(context)
                print("    Logged in. Session saved.")
            else:
                print("    Reusing saved Facebook session.")

            # Navigate to the target page
            print(f"    Opening page: {target_url}")
            fb_page.goto(target_url, wait_until="domcontentloaded")
            fb_page.wait_for_timeout(2500)

            # Compose and publish
            _click_composer(fb_page)
            _type_caption(fb_page, caption)
            _upload_photo(fb_page, image_path)
            _click_post(fb_page)

            # Grab URL of the new post as a rough "post ID"
            post_url = fb_page.url
            browser.close()

        return post_url or "posted"

    finally:
        os.unlink(image_path)
