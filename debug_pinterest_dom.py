"""
Run this locally (not in GitHub Actions) to inspect Pinterest's current
pin-creation-tool DOM with a real, visible browser.

It logs in with your saved cookies, opens the pin-builder, uploads a
placeholder image (so any fields that only render post-upload show up),
then pauses with the Playwright Inspector open. Use the Inspector's
"Pick locator" tool to click the title/description/link fields and copy
the selector it shows — paste those back so pinterest_post.py can be
updated with the real selectors instead of guesses.

Usage:
    python debug_pinterest_dom.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

from modules.pinterest_post import (
    _make_browser,
    _make_context,
    _load_cookies,
    _is_logged_in,
    _login,
    _save_cookies,
    _upload_image,
)

PLACEHOLDER_IMAGE = Path(__file__).parent / "output" / "_debug_placeholder.png"


def _ensure_placeholder_image():
    PLACEHOLDER_IMAGE.parent.mkdir(exist_ok=True)
    if not PLACEHOLDER_IMAGE.exists():
        # 1x1 white PNG
        import base64
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        PLACEHOLDER_IMAGE.write_bytes(png_bytes)


def main():
    _ensure_placeholder_image()
    with sync_playwright() as p:
        browser = _make_browser(p, headless=False)
        context = _make_context(browser)
        _load_cookies(context)
        page = context.new_page()

        if not _is_logged_in(page):
            _login(page)
            if not _is_logged_in(page):
                print("Login failed — check PINTEREST_EMAIL/PINTEREST_PASSWORD in .env")
                browser.close()
                return
            _save_cookies(context)

        page.goto("https://www.pinterest.com/pin-creation-tool/", timeout=45000)
        page.wait_for_timeout(2000)

        try:
            _upload_image(page, str(PLACEHOLDER_IMAGE))
        except Exception as e:
            print(f"Image upload step failed (continuing anyway): {e}")

        print("\n" + "=" * 70)
        print("Browser is open. Playwright Inspector should appear too.")
        print("In the Inspector, click 'Pick locator', then click the title field")
        print("(and description/link fields) in the browser to get their real selectors.")
        print("Close the Inspector window when done to end the script.")
        print("=" * 70 + "\n")

        page.pause()
        browser.close()


if __name__ == "__main__":
    main()
