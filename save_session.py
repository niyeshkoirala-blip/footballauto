#!/usr/bin/env python3
"""
One-time Facebook login helper.

Opens a VISIBLE browser using the SAME persistent profile that main.py uses.
Log in, complete any verification (email code, 2FA, etc.), then close the browser.
From that point on, python main.py reuses the saved profile — no login ever again.

Usage:
    source .venv/bin/activate
    python save_session.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

load_dotenv()

FB_PROFILE = str(Path(__file__).parent / ".facebook-profile")
email      = os.getenv("FB_EMAIL",    "").strip()
password   = os.getenv("FB_PASSWORD", "").strip()

if not email or not password:
    print("❌  Set FB_EMAIL and FB_PASSWORD in .env first.")
    sys.exit(1)

print("🌐  Opening browser to log in to Facebook.")
print("    Profile will be saved to .facebook-profile/")
print("    After login, main.py reuses this profile — no re-login needed.\n")

with sync_playwright() as pw:
    context = pw.chromium.launch_persistent_context(
        user_data_dir = FB_PROFILE,
        headless      = False,
        args          = ["--no-sandbox", "--start-maximized"],
        user_agent    = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport      = {"width": 1280, "height": 900},
        locale        = "en-US",
    )
    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    try:
        page.locator("#email").fill(email)
        page.locator("#pass").fill(password)
        page.locator('[name="login"]').click()
        print("✅  Credentials submitted.")
    except Exception as e:
        print(f"⚠️   Could not auto-fill ({e}). Fill them manually in the browser.\n")

    print()
    print("⏳  Waiting for you to finish (up to 3 minutes)…")
    print("    If Facebook asks for an email verification code:")
    print("    → Open Gmail in another browser tab, copy the code, paste it here.\n")

    try:
        page.wait_for_url(
            lambda url: "login" not in url and "checkpoint" not in url,
            timeout=180000,
        )
        print("✅  Logged in! Profile saved to .facebook-profile/")
        print("    Run:  python main.py --dry-run   to test")
    except Exception:
        print("⚠️   Timed out — saving whatever session exists.")

    page.wait_for_timeout(2000)
    context.close()
