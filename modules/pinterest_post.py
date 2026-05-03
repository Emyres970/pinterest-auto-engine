import os
import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

COOKIES_FILE = Path(__file__).parent.parent / ".pinterest_cookies.json"
log = logging.getLogger(__name__)

ANTI_DETECT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    window.chrome = { runtime: {} };
"""


def _make_browser(p, headless: bool):
    """Launch real Chrome if installed, fall back to bundled Chromium."""
    launch_args = {
        "headless": headless,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    try:
        return p.chromium.launch(channel="chrome", **launch_args)
    except Exception:
        return p.chromium.launch(**launch_args)


def _make_context(browser):
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    ctx.add_init_script(ANTI_DETECT_SCRIPT)
    return ctx


def _save_cookies(context):
    cookies = context.cookies()
    COOKIES_FILE.write_text(json.dumps(cookies), encoding="utf-8")


def _load_cookies(context):
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        context.add_cookies(cookies)
        return True
    return False


def _wait_load(page, timeout=30000):
    """Wait for 'load' then silently try networkidle — Pinterest never truly goes idle."""
    page.wait_for_load_state("load", timeout=timeout)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass


def _is_logged_in(page) -> bool:
    try:
        page.goto("https://www.pinterest.com/", timeout=30000)
        _wait_load(page)
        url = page.url
        if "login" in url or "signup" in url:
            return False
        if page.locator('[data-test-id="simple-login-button"]').count():
            return False
        if page.locator('[data-test-id="header-profile"]').count():
            return True
        return True
    except Exception:
        return False


def _login(page):
    log.info("Logging into Pinterest...")
    page.goto("https://www.pinterest.com/login/", timeout=30000)
    _wait_load(page)
    page.wait_for_timeout(2000)

    page.locator('[id="email"]').fill(os.getenv("PINTEREST_EMAIL", ""))
    page.wait_for_timeout(700)
    page.locator('[id="password"]').fill(os.getenv("PINTEREST_PASSWORD", ""))
    page.wait_for_timeout(700)
    page.locator('[data-test-id="registerFormSubmitButton"]').click()
    _wait_load(page, timeout=40000)
    page.wait_for_timeout(4000)
    log.info(f"Post-login URL: {page.url}")


def _upload_image(page, image_path: str):
    # Pinterest only injects the file input after the upload zone is interacted with.
    UPLOAD_TRIGGERS = [
        '[data-test-id="media-upload-button"]',
        '[data-test-id="storyboard-upload-button"]',
        'div[data-test-id="pin-draft-image"] button',
        'label[for*="file"]',
        'button[aria-label*="upload" i]',
        'div[role="button"]:has-text("upload")',
    ]
    for sel in UPLOAD_TRIGGERS:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible(timeout=1500):
                el.click()
                page.wait_for_timeout(1500)
                break
        except Exception:
            pass

    # Force hidden file inputs to be reachable
    page.evaluate("""
        document.querySelectorAll('input[type="file"]').forEach(el => {
            el.style.cssText = 'display:block!important;opacity:1!important;'
                             + 'position:fixed;top:0;left:0;width:1px;height:1px;z-index:9999;';
        });
    """)

    file_input = page.locator('input[type="file"]').first
    try:
        file_input.wait_for(state="attached", timeout=20000)
    except Exception:
        debug_path = Path(image_path).parent / "_debug_upload_fail.png"
        page.screenshot(path=str(debug_path))
        log.error(f"Upload input not found. Debug screenshot: {debug_path}")
        raise

    file_input.set_input_files(image_path)
    page.wait_for_timeout(4000)


def _fill_field(page, selectors: list, value: str, label: str, required=True):
    """Try each selector in order; raise only if required and all fail."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=6000)
            el.click()
            page.wait_for_timeout(300)
            el.fill(value)
            return
        except Exception:
            continue
    if required:
        debug = Path(__file__).parent.parent / "output" / f"_debug_{label}_fail.png"
        page.screenshot(path=str(debug))
        raise RuntimeError(f"Could not fill {label} field. Debug: {debug}")
    log.warning(f"Skipped optional field: {label}")


def _fill_pin_details(page, title: str, description: str, link: str, board_name: str):
    page.wait_for_timeout(1000)

    _fill_field(page, [
        '[data-test-id="pin-draft-title"]',
        'input[placeholder*="title" i]',
        'input[name="title"]',
    ], title[:100], "title")

    page.wait_for_timeout(500)

    _fill_field(page, [
        '[data-test-id="pin-draft-description"]',
        'div[data-test-id="pin-draft-description"] textarea',
        'textarea[placeholder*="description" i]',
        'textarea[placeholder*="about" i]',
        'textarea[placeholder*="tell" i]',
        'div[contenteditable="true"]',
        'textarea',
    ], description[:500], "description", required=False)

    page.wait_for_timeout(500)

    _fill_field(page, [
        '[data-test-id="pin-draft-link"]',
        'input[placeholder*="link" i]',
        'input[placeholder*="destination" i]',
        'input[placeholder*="url" i]',
        'input[name="link"]',
    ], link, "link", required=False)

    page.wait_for_timeout(500)


def _select_board(page, board_name: str):
    # Open board dropdown
    opened = False
    for sel in [
        '[data-test-id="board-dropdown-select-button"]',
        'button:has-text("Choose a board")',
        'button[aria-label*="board" i]',
        '[data-test-id="pin-draft-save-button"]',
    ]:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible(timeout=2000):
                el.click()
                opened = True
                break
        except Exception:
            continue

    page.wait_for_timeout(2000)

    # Try searching for the board
    for search_sel in ['[data-test-id="board-search-input"]', 'input[placeholder*="search" i]']:
        try:
            search = page.locator(search_sel).first
            if search.count() and search.is_visible(timeout=2000):
                search.fill(board_name)
                page.wait_for_timeout(1500)
                break
        except Exception:
            continue

    # Wait for dropdown results to render
    page.wait_for_timeout(2000)

    # Click the board row — try multiple selector patterns
    clicked = False
    for row_sel in [
        f'[data-test-id="board-row"]:has-text("{board_name}")',
        f'[data-test-id="board-dropdown-item"]:has-text("{board_name}")',
        f'[data-test-id="boardWithoutSection"]:has-text("{board_name}")',
        f'div[role="option"]:has-text("{board_name}")',
        f'li:has-text("{board_name}")',
        f'button:has-text("{board_name}")',
        # Generic: any element in the dropdown list containing the board name
        f'ul >> text="{board_name}"',
        f'[role="listbox"] >> text="{board_name}"',
    ]:
        try:
            el = page.locator(row_sel).first
            if el.count():
                el.scroll_into_view_if_needed()
                el.click(timeout=5000)
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        # Last resort: click whatever is first in the result list (the search already
        # filtered to the board name, so the first non-"Create board" item is ours)
        try:
            # The board thumbnail image is always present — click its parent row
            result = page.locator('img[alt*="' + board_name + '" i]').first
            if result.count():
                result.click(timeout=5000)
                clicked = True
        except Exception:
            pass

    if not clicked:
        debug = Path(__file__).parent.parent / "output" / "_debug_board_fail.png"
        page.screenshot(path=str(debug))
        log.error(f"Board '{board_name}' not found in dropdown. Debug: {debug}")
        raise RuntimeError(f"Board '{board_name}' not found")

    page.wait_for_timeout(1000)


def _publish(page):
    try:
        page.locator('[data-test-id="board-dropdown-save-button"]').click(timeout=8000)
    except PlaywrightTimeout:
        page.locator('button:has-text("Publish")').click()

    _wait_load(page, timeout=30000)
    page.wait_for_timeout(3000)


def post_pin(image_path: str, title: str, description: str, link: str, board_name: str):
    headless = os.getenv("PINTEREST_HEADLESS", "true").lower() == "true"
    with sync_playwright() as p:
        browser = _make_browser(p, headless)
        context = _make_context(browser)

        _load_cookies(context)
        page = context.new_page()

        if not _is_logged_in(page):
            _login(page)
            if not _is_logged_in(page):
                debug_path = Path(image_path).parent / "_debug_login_fail.png"
                page.screenshot(path=str(debug_path))
                raise RuntimeError(
                    "Pinterest login failed — run 'python login.py' to log in manually "
                    f"and save your session. Debug screenshot: {debug_path}"
                )
            _save_cookies(context)

        page.goto("https://www.pinterest.com/pin-creation-tool/", timeout=30000)
        _wait_load(page)
        page.wait_for_timeout(2000)

        _upload_image(page, image_path)
        _fill_pin_details(page, title, description, link, board_name)
        _select_board(page, board_name)
        _publish(page)

        _save_cookies(context)
        browser.close()
        log.info(f"Pin posted: {title[:60]}")
