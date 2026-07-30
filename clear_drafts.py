"""
Stand-alone maintenance script: logs into Pinterest and bulk-deletes every
saved draft in the pin-creation-tool sidebar.

Run this before the daily automation so leftover drafts from failed CI runs
never build up toward Pinterest's 50-draft cap. main.py's own cleanup
(_clear_draft_limit) only fires reactively after that cap is already hit and
blocking uploads, which depends on matching Pinterest's current error banner
text/selectors — if those drift, cleanup gets silently skipped. This script
clears drafts unconditionally, every run, regardless of how many exist.

Usage:
    python clear_drafts.py
"""
import logging
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

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


def main():
    with sync_playwright() as p:
        browser = _make_browser(p, headless=True)
        context = _make_context(browser)
        _load_cookies(context)
        page = context.new_page()

        if not _is_logged_in(page):
            _login(page)
            if not _is_logged_in(page):
                log.error(
                    "Pinterest login failed — cannot clear drafts. "
                    "Run 'python login.py' to refresh your session."
                )
                browser.close()
                raise SystemExit(1)
            _save_cookies(context)

        page.goto("https://www.pinterest.com/pin-creation-tool/", timeout=45000)
        _wait_load(page)
        page.wait_for_timeout(2000)

        if _delete_all_drafts(page):
            log.info("Drafts cleared.")
        else:
            log.info("No drafts found — nothing to clear.")

        _save_cookies(context)
        browser.close()


if __name__ == "__main__":
    main()
