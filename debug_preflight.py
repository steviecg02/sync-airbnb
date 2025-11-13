#!/usr/bin/env python3
"""Debug script to test preflight and examine response."""

from curl_cffi import requests as curl_requests

from sync_airbnb.config import get_env
from sync_airbnb.utils.cookie_utils import filter_auth_cookies_only, parse_cookie_string

# Get credentials from .env
cookie_string = get_env("AIRBNB_COOKIE") or ""
user_agent = get_env("USER_AGENT") or "Mozilla/5.0"

print(f"User-Agent: {user_agent[:50]}...")
print(f"Cookie length: {len(cookie_string)} chars")

# Parse and filter cookies
all_cookies = parse_cookie_string(cookie_string)
auth_cookies = filter_auth_cookies_only(all_cookies)
print(f"\nAuth cookies ({len(auth_cookies)}): {list(auth_cookies.keys())}")

# Create session
print("\n=== Creating Session ===")
session = curl_requests.Session(impersonate="chrome110")

session.headers.update(
    {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }
)

# Load cookies
for name, value in auth_cookies.items():
    session.cookies.set(name, value, domain=".airbnb.com")

print(f"Session has {len(session.cookies)} cookies before request")

# Make preflight request
print("\n=== Making Preflight Request ===")
url = "https://www.airbnb.com/hosting/insights"
response = session.get(url, allow_redirects=True, timeout=30)

print(f"\nStatus: {response.status_code}")
print(f"Final URL: {response.url}")
print(f"Redirected: {response.url != url}")

# Check Set-Cookie headers
try:
    set_cookie_list = response.headers.get_list("set-cookie")
    if set_cookie_list:
        cookie_names = [cookie.split("=")[0] for cookie in set_cookie_list]
        print(f"\nSet-Cookie headers ({len(set_cookie_list)}): {cookie_names}")
    else:
        print("\nNo Set-Cookie headers")
except Exception as e:
    print(f"\nCouldn't parse Set-Cookie: {e}")

print(f"\nSession now has {len(session.cookies)} cookies after request")

# Save response HTML
output_file = "preflight_response.html"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(response.text)

print(f"\n=== Response saved to {output_file} ===")
print(f"Response length: {len(response.text)} chars")

# Check for indicators
if "login" in response.url.lower() or "authenticate" in response.url.lower():
    print("\n⚠️  WARNING: Redirected to login page!")
elif "hosting/insights" in response.url.lower():
    print("\n✓ Stayed on hosting/insights page")
elif "performance" in response.url.lower():
    print("\n✓ Redirected to performance page (expected)")

# Check response content for clues
if "Please log in" in response.text or "Sign up" in response.text:
    print("⚠️  Response contains login prompts")
if "data-page-container" in response.text:
    print("✓ Response contains React container (valid page)")
