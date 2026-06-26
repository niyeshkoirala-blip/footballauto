#!/usr/bin/env python3
"""
Get a permanent Facebook Page Access Token without the Graph API Explorer.

Run:  python get_token.py
It will guide you through the steps and save the token to .env automatically.
"""

import json
import os
import re
import sys
import webbrowser

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

ENV_FILE = ".env"

print("=" * 60)
print("  Facebook Page Token Setup")
print("=" * 60)
print()
print("You need two things from your Meta Developer App dashboard:")
print("  developers.facebook.com → Your App → Settings → Basic")
print()

app_id     = input("Paste your App ID:     ").strip()
app_secret = input("Paste your App Secret: ").strip()

if not app_id or not app_secret:
    print("❌  App ID and App Secret are required.")
    sys.exit(1)

# Build the OAuth URL — user visits this, logs in, allows permissions
oauth_url = (
    f"https://www.facebook.com/dialog/oauth"
    f"?client_id={app_id}"
    f"&redirect_uri=https://www.facebook.com/connect/login_success.html"
    f"&scope=pages_manage_posts,pages_read_engagement,pages_show_list"
    f"&response_type=token"
)

print()
print("─" * 60)
print("STEP 1 — Opening a browser window…")
print("  Log in if asked, then click 'Continue as ...' or 'Allow'.")
print("  You'll land on a blank page — that's normal.")
print("─" * 60)
webbrowser.open(oauth_url)

print()
print("After you click Allow, the browser URL bar will look like:")
print("  https://www.facebook.com/connect/login_success.html#access_token=EAA...")
print()
raw = input("Paste the FULL URL from your browser here:\n> ").strip()

# Extract token from the URL
m = re.search(r'access_token=([A-Za-z0-9_\-]+)', raw)
if not m:
    print("❌  Could not find access_token in that URL. Make sure you copied the full URL.")
    sys.exit(1)

short_token = m.group(1)
print(f"\n✅  Short-lived token captured.")

# Exchange for a long-lived user token (60-day)
print("   Exchanging for long-lived token…")
r = requests.get(
    "https://graph.facebook.com/oauth/access_token",
    params={
        "grant_type":       "fb_exchange_token",
        "client_id":        app_id,
        "client_secret":    app_secret,
        "fb_exchange_token": short_token,
    },
    timeout=15,
)
r.raise_for_status()
long_token = r.json()["access_token"]
print("✅  Long-lived user token obtained (valid 60 days).")

# Get the permanent Page Access Token
print("   Fetching permanent Page Access Token…")
r = requests.get(
    "https://graph.facebook.com/me/accounts",
    params={"access_token": long_token},
    timeout=15,
)
r.raise_for_status()
pages = r.json().get("data", [])

if not pages:
    print("❌  No pages found for this account. Make sure you granted pages_show_list.")
    sys.exit(1)

print()
print("Pages found on your account:")
for i, page in enumerate(pages):
    print(f"  [{i}]  {page['name']}  (ID: {page['id']})")

print()
if len(pages) == 1:
    choice = 0
else:
    choice = int(input("Enter the number of your PITCH SIDE News page: ").strip())

chosen = pages[choice]
page_id    = chosen["id"]
page_token = chosen["access_token"]

print()
print(f"✅  Permanent Page Access Token for: {chosen['name']}")
print(f"    Page ID: {page_id}")
print(f"    Token:   {page_token[:20]}…  (saved to .env)")

# Save to .env
set_key(ENV_FILE, "FB_PAGE_ID",           page_id)
set_key(ENV_FILE, "FB_PAGE_ACCESS_TOKEN", page_token)

print()
print("=" * 60)
print("  Done! Your .env now has:")
print(f"    FB_PAGE_ID           = {page_id}")
print(f"    FB_PAGE_ACCESS_TOKEN = (permanent, never expires)")
print()
print("  Run:  python main.py --dry-run   to test")
print("  Then: python main.py             to post for real")
print("=" * 60)
