"""
Posts to a Facebook Page.

Automatically picks the right method based on env vars:

  MAKE_WEBHOOK_URL set  →  Webhook mode (Make.com + Imgur). Recommended.
                            No browser, no bot detection, runs on GitHub Actions.

  MAKE_WEBHOOK_URL unset →  Playwright mode (persistent browser profile).
                             Requires FB_EMAIL + FB_PASSWORD + FB_PAGE_URL.
                             Set FB_HEADLESS=1 after first login.
"""

import os
import tempfile
from pathlib import Path

from PIL import Image


# ── Webhook mode (Make.com) ────────────────────────────────────────────────────

def _post_webhook(caption: str, image: Image.Image) -> str:
    from src.webhook_poster import post_via_webhook
    return post_via_webhook(caption, image)


# ── Playwright mode (persistent browser profile) ───────────────────────────────

def _get_playwright_context(pw):
    from playwright_stealth import Stealth  # noqa: F401 (imported for side effects)

    FB_PROFILE = str(Path(__file__).parent.parent / ".facebook-profile")
    _HEADLESS   = bool(os.getenv("FB_HEADLESS"))

    return pw.chromium.launch_persistent_context(
        user_data_dir = FB_PROFILE,
        headless      = _HEADLESS,
        args          = ["--no-sandbox", "--disable-dev-shm-usage"],
        user_agent    = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport      = {"width": 1280, "height": 900},
        locale        = "en-US",
    )


def _is_logged_in(page) -> bool:
    try:
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return False
    page.wait_for_timeout(3000)
    if "login" in page.url or "checkpoint" in page.url:
        return False
    try:
        if page.locator('input[name="pass"], #pass').first.is_visible(timeout=2000):
            return False
    except Exception:
        pass
    return True


def _dismiss_popup(page) -> None:
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass
    for sel in [
        'button[data-cookiebanner="accept_button"]',
        '[aria-label="Allow all cookies"]',
        'button:has-text("Allow all cookies")',
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        '[aria-label="Close"]',
        'div[role="dialog"] button',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click(force=True)
                page.wait_for_timeout(700)
                return
        except Exception:
            continue


def _login(page, email: str, password: str) -> None:
    page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    _dismiss_popup(page)
    page.wait_for_timeout(800)

    email_sel = None
    for sel in ["#email", 'input[name="email"]', 'input[type="email"]']:
        try:
            page.locator(sel).first.wait_for(state="visible", timeout=15000)
            email_sel = sel
            break
        except Exception:
            continue

    if email_sel is None:
        page.screenshot(path="fb_login_debug.png")
        raise RuntimeError(f"Login form not found (URL: {page.url}). See fb_login_debug.png.")

    page.locator(email_sel).fill(email)
    for s in ['#pass', 'input[name="pass"]', 'input[type="password"]']:
        try:
            if page.locator(s).first.is_visible(timeout=3000):
                page.locator(s).first.fill(password)
                break
        except Exception:
            continue
    for s in ['[name="login"]', 'button[type="submit"]', 'button:has-text("Log in")']:
        try:
            if page.locator(s).first.is_visible(timeout=3000):
                page.locator(s).first.click()
                break
        except Exception:
            continue

    print("    Complete any verification in the browser window…")
    print("    If asked for an email code: open Gmail in another tab, copy + paste it.")
    try:
        page.wait_for_url(
            lambda url: "login" not in url and "checkpoint" not in url,
            timeout=180000,
        )
    except Exception:
        pass

    if "login" in page.url or "checkpoint" in page.url:
        page.screenshot(path="fb_login_debug.png")
        raise RuntimeError("Login failed — see fb_login_debug.png.")
    print("    Logged in. Profile saved — no login needed on future runs.")


def _click_composer(page) -> None:
    _dismiss_popup(page)
    page.wait_for_timeout(600)
    for sel in [
        '[aria-label="Create a public post…"]',
        '[placeholder*="Write something"]',
        '[placeholder*="What\'s on your mind"]',
        '[data-testid="status-attachment-mentions-input"]',
        'div[role="button"]:has-text("Write something")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(force=True)
                page.wait_for_timeout(1500)
                return
        except Exception:
            continue
    page.evaluate("""
        () => {
            const sels = ['[aria-label="Create a public post…"]',
                          '[placeholder*="Write something"]'];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el) { el.click(); return; }
            }
        }
    """)
    page.wait_for_timeout(1200)


def _type_caption(page, caption: str) -> None:
    page.evaluate(
        """(text) => {
            const el = document.querySelector('[data-lexical-editor="true"]')
                    || document.querySelector('[contenteditable="true"][role="textbox"]')
                    || document.querySelector('[contenteditable="true"]');
            if (el) { el.focus(); document.execCommand('insertText', false, text); }
        }""",
        caption,
    )
    page.wait_for_timeout(600)


def _upload_photo(page, image_path: str) -> None:
    for sel in ['[aria-label="Photo/video"]', '[aria-label*="Photo"]']:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            continue
    page.locator('input[type="file"]').first.set_input_files(image_path)
    page.wait_for_timeout(4000)


def _click_post(page) -> None:
    for sel in [
        '[aria-label="Post"]',
        'div[aria-label="Post"][role="button"]',
        'div[role="button"]:has-text("Post"):not([aria-label*="cancel"])',
        'button:has-text("Post")',
    ]:
        try:
            btn = page.locator(sel).last
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(5000)
                return
        except Exception:
            continue
    raise RuntimeError("Could not find the Post button.")


def _post_playwright(caption: str, image: Image.Image, page_id: str) -> str:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    fb_email    = os.getenv("FB_EMAIL",    "").strip()
    fb_password = os.getenv("FB_PASSWORD", "").strip()
    page_url    = os.getenv("FB_PAGE_URL", "").strip()
    target_url  = page_url or f"https://www.facebook.com/{page_id}"
    stealth     = Stealth()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image.save(tmp, format="JPEG", quality=95, optimize=True)
        image_path = tmp.name

    try:
        with sync_playwright() as pw:
            context = _get_playwright_context(pw)
            page    = context.new_page()
            stealth.apply_stealth_sync(page)

            if not _is_logged_in(page):
                print("    Not logged in — opening login page in browser…")
                _login(page, fb_email, fb_password)
            else:
                print("    Reusing saved profile session.")

            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            _dismiss_popup(page)

            try:
                _click_composer(page)
                _type_caption(page, caption)
                _upload_photo(page, image_path)
                _click_post(page)
            except Exception:
                page.screenshot(path="fb_post_debug.png")
                print("    Debug screenshot → fb_post_debug.png")
                raise

            result = page.url
            context.close()
        return result or "posted"
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass


# ── Public API (called by main.py) ────────────────────────────────────────────

def post_to_facebook(
    caption: str,
    image:   Image.Image,
    page_id: str       = "",
    access_token: str  = "",
) -> str:
    if os.getenv("MAKE_WEBHOOK_URL", "").strip():
        print("    Using Make.com webhook…")
        return _post_webhook(caption, image)
    print("    Using Playwright (persistent profile)…")
    return _post_playwright(caption, image, page_id)


def post_reel_to_facebook(
    caption:    str,
    video_path: str,
    page_id:    str = "",
    access_token: str = "",
) -> str:
    if os.getenv("MAKE_REEL_WEBHOOK_URL", "").strip():
        print("    Using Make.com webhook for reel…")
        from src.webhook_poster import post_reel_via_webhook
        return post_reel_via_webhook(caption, video_path)
    # Fallback to Playwright
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth

    page_url   = os.getenv("FB_PAGE_URL", "").strip()
    target_url = page_url or f"https://www.facebook.com/{page_id}"
    fb_email   = os.getenv("FB_EMAIL",    "").strip()
    fb_pass    = os.getenv("FB_PASSWORD", "").strip()
    stealth    = Stealth()

    with sync_playwright() as pw:
        context = _get_playwright_context(pw)
        page    = context.new_page()
        stealth.apply_stealth_sync(page)

        if not _is_logged_in(page):
            _login(page, fb_email, fb_pass)

        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        _dismiss_popup(page)

        _click_composer(page)
        for sel in ['[aria-label="Photo/video"]', '[aria-label*="Photo"]']:
            try:
                if page.locator(sel).first.is_visible(timeout=2000):
                    page.locator(sel).first.click()
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                continue
        page.locator('input[type="file"]').first.set_input_files(video_path)
        page.wait_for_timeout(8000)
        for sel in ['div[role="radio"]:has-text("Reel")',
                    'div[role="button"]:has-text("Share as a reel")',
                    'label:has-text("Reel")']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.click()
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                continue
        _type_caption(page, caption)
        _click_post(page)

        result = page.url
        context.close()
    return result or "reel posted"
