"""
Stand-alone maintenance script: logs into Pinterest and bulk-deletes every
saved draft in the pin-creation-tool sidebar.

Run this before the daily automation so leftover drafts from failed CI runs
never build up toward Pinterest's 50-draft cap. main.py's own cleanup
(_clear_draft_limit) only fires reactively after that cap is already hit and
blocking uploads, which depends on matching Pinterest's current error banner
text/selectors — if those drift, cleanup gets silently skipped. This script
clears drafts unconditionally, every run, regardless of how many exist.

This is best-effort maintenance, not a prerequisite for posting: any failure
here (login hiccup, a slow/timed-out navigation, a changed selector) is
logged and swallowed so the daily automation still runs. A hard failure in
this step previously took the whole job down before main.py ever started —
see git history around 2026-09-04 for the incident this guards against.

Usage:
    python clear_drafts.py
"""
import logging
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from modules.pinterest_post import (
    _make_browser,
    _make_context,
    _load_cookies,
    _save_cookies,
    _is_logged_in,
    _login,
    _wait_load,
    _delete_all_drafts,
)


def _run():
    with sync_playwright() as p:
        browser = _make_browser(p, headless=True)
        context = _make_context(browser)
        _load_cookies(context)
        page = context.new_page()

        if not _is_logged_in(page):
            _login(page)
            if not _is_logged_in(page):
                log.warning(
                    "Pinterest login failed — skipping draft cleanup for this run. "
                    "Run 'python login.py' to refresh your session."
                )
                browser.close()
                return
            _save_cookies(context)

        for attempt in range(3):
            try:
                page.goto("https://www.pinterest.com/pin-creation-tool/", timeout=45000)
                break
            except PlaywrightTimeout:
                if attempt == 2:
                    raise
                log.warning(f"pin-creation-tool navigation timed out — retrying ({attempt + 1}/3)")
                page.wait_for_timeout(3000)
        _wait_load(page)
        page.wait_for_timeout(2000)

        if _delete_all_drafts(page):
            log.info("Drafts cleared.")
        else:
            log.info("No drafts found — nothing to clear.")

        _save_cookies(context)
        browser.close()


def main():
    try:
        _run()
    except Exception as e:
        log.warning(f"Draft cleanup failed, continuing anyway: {e}")


if __name__ == "__main__":
    main()

