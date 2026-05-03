"""
Run this once to log into Pinterest manually and save your session cookies.

    python login.py

A Chrome window will open. Log in however Pinterest asks (password, email code,
CAPTCHA, etc.). Once you see your home feed, the script detects it, saves cookies,
and exits. After that, main.py runs fully headless.
"""

import json
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

COOKIES_FILE = Path(__file__).parent / ".pinterest_cookies.json"

ANTI_DETECT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    window.chrome = { runtime: {} };
"""


def _make_browser(p):
    args = {"headless": False, "args": ["--disable-blink-features=AutomationControlled"]}
    try:
        return p.chromium.launch(channel="chrome", **args)
    except Exception:
        return p.chromium.launch(**args)


def _is_home_feed(page) -> bool:
    url = page.url
    if "login" in url or "signup" in url or "pinterest.com/" == url.rstrip("/") + "/":
        return False
    return (
        page.locator('[data-test-id="header-profile"]').count() > 0
        or "/feed" in url
        or "pinterest.com/home" in url
    )


def main():
    with sync_playwright() as p:
        browser = _make_browser(p)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(ANTI_DETECT_SCRIPT)
        page = context.new_page()

        print("Opening Pinterest login page...")
        page.goto("https://www.pinterest.com/login/", timeout=30000)

        print("\nLog into Pinterest in the browser window.")
        print("Complete any verification Pinterest asks for (email code, CAPTCHA, etc.).")
        print("Waiting for your home feed to appear...\n")

        deadline = time.time() + 300  # 5-minute window
        while time.time() < deadline:
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            if _is_home_feed(page):
                cookies = context.cookies()
                COOKIES_FILE.write_text(json.dumps(cookies), encoding="utf-8")
                print(f"Logged in! Cookies saved to {COOKIES_FILE}")
                print("You can now run:  python main.py")
                browser.close()
                return

            time.sleep(2)

        print("Timed out waiting for login. Please try again.")
        browser.close()


if __name__ == "__main__":
    main()
