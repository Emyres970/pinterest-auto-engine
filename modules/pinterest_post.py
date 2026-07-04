import os
import json
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

COOKIES_FILE = Path(__file__).parent.parent / ".pinterest_cookies.json"
log = logging.getLogger(__name__)

TAGS = [
    "Relationship Goals",
    "Relationship Advice",
    "Healthy Relationship Advice",
    "Relationship Quotes",
    "Love Quotes",
    "Inspirational Quotes",
    "Marriage Quotes",
    "Marriage Advice",
    "Successful Marriage",
    "Happy Marriage",
]

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
    page.wait_for_timeout(5000)


def _clear_draft_limit(page) -> bool:
    """Detect the 50-draft cap and bulk-delete all drafts to make room.

    Returns True if drafts were cleared (caller must retry the upload on a fresh
    page), False if no limit error was found.

    Each failed CI run leaves a draft behind (image uploaded but never published).
    After enough failures the account hits Pinterest's 50-draft ceiling and all
    subsequent uploads fail silently, showing a 50-draft error instead of the
    form — the root cause of the cascading CI failures.
    """
    if not page.locator('text="You have reached the limit of 50 drafts"').count():
        return False
    log.warning("Pinterest 50-draft limit hit — bulk-deleting all saved drafts")
    try:
        cb = page.locator('#storyboard-drafts-sidebar-bulk-select-checkbox')
        cb.wait_for(state="visible", timeout=6000)
        cb.click()
        page.wait_for_timeout(1500)

        deleted = False
        for del_sel in [
            'button:has-text("Delete all")',
            'button:has-text("Delete")',
            '[data-test-id="storyboard-bulk-delete-button"]',
            '[data-test-id*="delete"]',
            'button[aria-label*="delete" i]',
        ]:
            btn = page.locator(del_sel).first
            try:
                if btn.count() and btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(1000)
                    for confirm_sel in [
                        'button:has-text("Delete")',
                        'button:has-text("Yes")',
                        'button:has-text("Confirm")',
                        'button:has-text("OK")',
                    ]:
                        c = page.locator(confirm_sel).first
                        try:
                            if c.count() and c.is_visible(timeout=2000):
                                c.click()
                                break
                        except Exception:
                            pass
                    page.wait_for_timeout(4000)
                    deleted = True
                    break
            except Exception:
                continue

        if not deleted:
            raise RuntimeError(
                "Pinterest draft limit (50) reached but delete button not found. "
                "Delete old drafts manually at pinterest.com/idea-pin-builder/"
            )
        log.info("  Draft bulk-delete complete")
        return True
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Pinterest draft limit (50) reached; auto-clear failed ({e}). "
            "Delete old drafts manually at pinterest.com/idea-pin-builder/"
        )


def _click_next_if_present(page) -> bool:
    """Click 'Next' after image upload if Pinterest is in its two-step creation flow."""
    next_sels = [
        '[data-test-id="creation-next-button"]',
        'button:has-text("Next")',
        'div[role="button"]:has-text("Next")',
        'button:has-text("Continue")',
        '[aria-label="Next"]',
        'button[type="submit"]:has-text("Next")',
    ]
    for sel in next_sels:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible(timeout=2000):
                log.info("  Two-step flow detected — clicking Next")
                el.click()
                page.wait_for_timeout(3000)
                return True
        except Exception:
            continue
    return False


def _log_visible_inputs(page):
    """Enumerate visible inputs and log them — used to diagnose selector failures."""
    try:
        items = page.evaluate("""() =>
            Array.from(document.querySelectorAll(
                'input:not([type="file"]):not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea, [contenteditable="true"]'
            )).filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 10 && r.height > 10;
            }).map(el => [
                el.tagName,
                el.id,
                el.getAttribute('name') || '',
                el.getAttribute('type') || '',
                (el.getAttribute('placeholder') || '').slice(0, 40),
                (el.getAttribute('aria-label') || '').slice(0, 40),
                el.getAttribute('data-test-id') || '',
            ])
        """)
        log.info(f"  Visible inputs: {items}")
    except Exception as e:
        log.debug(f"Could not enumerate inputs: {e}")


def _dismiss_overlays(page):
    """Dismiss any modal or overlay that might block form interaction."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    except Exception:
        pass
    for sel in [
        'button[aria-label="Close"]',
        'button[aria-label="Dismiss"]',
        '[role="dialog"] button[aria-label*="close" i]',
        '[aria-modal="true"] button[aria-label*="close" i]',
        '[data-test-id*="closeup-close"]',
    ]:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible(timeout=800):
                el.click()
                page.wait_for_timeout(500)
                break
        except Exception:
            pass


def _js_fill(page, element_id: str, value: str) -> bool:
    """Fill a React-controlled input via JS — bypasses all Playwright actionability checks.

    Uses the native HTMLInputElement value setter so React's synthetic event
    system recognises the change and updates component state correctly.
    """
    try:
        return bool(page.evaluate("""([id, v]) => {
            const el = document.getElementById(id);
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(el, v);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return el.value === v;
        }""", [element_id, value]))
    except Exception as e:
        log.debug(f"JS fill failed for #{element_id}: {e}")
        return False


def _fill_contenteditable(page, el, value: str):
    """Fill a contenteditable/Draft.js div.

    Setting textContent directly breaks Draft.js state, so we click to focus,
    then use keyboard shortcuts to clear existing text and type new content.
    page.keyboard.type() is used instead of el.type() so that focus-delegation
    (common in Draft.js wrappers that are contenteditable="false") is handled
    by the browser naturally after the click.
    """
    el.scroll_into_view_if_needed()
    el.click()
    el.evaluate("(node) => node.focus()")
    page.wait_for_timeout(300)
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.type(value, delay=8)


def _fill_field(page, selectors: list, value: str, label: str, required=True):
    """Try each selector in order; raise only if required and all fail."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=6000)
            is_editable_div = el.evaluate(
                "(node) => node.tagName !== 'INPUT' && node.tagName !== 'TEXTAREA'"
            )
            if is_editable_div:
                _fill_contenteditable(page, el, value)
            else:
                try:
                    el.click(timeout=5000)
                except Exception:
                    # An overlay may block the click; focus via JS and fall through to fill().
                    el.evaluate("(node) => node.focus()")
                page.wait_for_timeout(300)
                el.fill(value, timeout=5000)
            return
        except Exception:
            continue
    if required:
        # Log URL and visible inputs before saving debug files — helps diagnose
        # without downloading the artifact.
        log.info(f"  Current URL: {page.url}")
        _log_visible_inputs(page)
        debug_png = Path(__file__).parent.parent / "output" / f"_debug_{label}_fail.png"
        debug_html = Path(__file__).parent.parent / "output" / f"_debug_{label}_fail.html"
        page.screenshot(path=str(debug_png))
        debug_html.write_text(page.content(), encoding="utf-8")
        raise RuntimeError(f"Could not fill {label} field. Debug: {debug_png}, {debug_html}")
    log.warning(f"Skipped optional field: {label}")


def _wait_for_draft_form(page, timeout=300000):
    """Wait for the pin-draft title input to be visible AND enabled.

    Pinterest processes the uploaded image server-side before enabling the form.
    The title input (input#storyboard-selector-title) appears in the DOM while
    still disabled=true during processing; waiting only for 'visible' causes all
    fill attempts to fail because React resets el.value on every re-render while
    the element is disabled. We must wait for !el.disabled before proceeding.
    300 s gives comfortable headroom for large images (processing takes 30–180 s).
    """
    page.wait_for_function(
        """() => {
            const el = document.getElementById('storyboard-selector-title');
            if (el) {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && !el.disabled;
            }
            // Fallback: a visible contenteditable means the form is ready
            const ce = document.querySelector('[aria-label="Describe your Pin"]');
            return !!(ce && ce.getBoundingClientRect().width > 0);
        }""",
        timeout=timeout,
    )


def _fill_tags(page, tags: list):
    """Add up to 10 interest tags via the combobox autocomplete.

    Pinterest's tag combobox is search-only: free-form entries are rejected.
    Tags that return no suggestion are silently skipped. Tags are private
    recommendation signals — the UI says "people won't see your tags".

    The suggestion list loads asynchronously; we wait up to 4 s per tag.
    Confirmation that a tag was accepted: the combobox value returns to "".
    """
    cb = None
    for sel in [
        '#combobox-storyboard-interest-tags',
        'input[placeholder*="Search for a tag" i]',
    ]:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=5000)
            cb = el
            break
        except Exception:
            continue

    if cb is None:
        log.warning("  Tag combobox not found — skipping tags")
        return

    added = 0
    for tag in tags:
        if added >= 10:
            break
        try:
            cb.scroll_into_view_if_needed()
            cb.click()
            page.wait_for_timeout(200)
            cb.fill(tag)

            # Suggestion list loads asynchronously — can take 2-4 s
            try:
                page.wait_for_selector('[role="option"]', timeout=4000, state="visible")
            except Exception:
                log.warning(f"  No Pinterest suggestion for '{tag}' — skipping")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                continue

            opt = page.locator('[role="option"]').first
            if not opt.count() or not opt.is_visible():
                log.warning(f"  Suggestion vanished for '{tag}' — skipping")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                continue

            matched = opt.inner_text().strip()
            opt.click()
            page.wait_for_timeout(600)

            # Combobox resets to "" when the tag is accepted by Pinterest
            val = page.evaluate(
                "() => { const e = document.getElementById('combobox-storyboard-interest-tags'); return e ? e.value : null; }"
            )
            if val == "":
                added += 1
                log.info(f"  Tag {added}/10: '{matched}'")
            else:
                log.warning(f"  Tag not accepted for '{tag}'")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

        except Exception as e:
            log.warning(f"  Error adding tag '{tag}': {e}")
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass

    total = min(10, len(tags))
    if added < total:
        log.warning(f"  Tags: {added}/{total} added ({total - added} skipped — not in Pinterest taxonomy)")
    else:
        log.info(f"  Tags: all {added}/{total} added")


def _fill_pin_details(page, title: str, description: str, link: str, board_name: str):
    try:
        _wait_for_draft_form(page)
    except Exception:
        pass
    page.wait_for_timeout(1000)

    # Dismiss any modal/overlay before touching the form
    _dismiss_overlays(page)

    # --- Title ---
    # Try Playwright's selector-based fill first. If every selector fails (e.g.
    # an image-processing overlay is blocking actionability checks), fall back to
    # a JS injection that bypasses those checks entirely.
    title_filled = False
    try:
        _fill_field(page, [
            'input#storyboard-selector-title',               # idea-pin-builder (confirmed 2026-06)
            'input[placeholder*="tell everyone" i]',         # idea-pin-builder fallback
            '[data-test-id="pin-draft-title"]',              # old pin-creation-tool
            'input[placeholder*="title" i]',
            'input[name="title"]',
            'textarea[placeholder*="title" i]',
            '[aria-label*="add your title" i]',
            '[aria-label*="title" i]',
            'div[data-test-id="pin-draft-title"] [contenteditable="true"]',
            'div[data-test-id="pin-draft-title"] textarea',
            '[role="textbox"][aria-label*="title" i]',
        ], title[:100], "title")
        title_filled = True
    except RuntimeError:
        log.warning("  Playwright fill failed for title — trying JS injection")
        # Guard: ensure the input is enabled before JS fill. _wait_for_draft_form
        # may have timed out while the element was still disabled (large image,
        # slow server-side processing). React resets el.value on every re-render
        # while disabled=true, so _js_fill would return False without this wait.
        try:
            page.wait_for_function(
                "() => { const el = document.getElementById('storyboard-selector-title'); return el && !el.disabled; }",
                timeout=120000,
            )
        except Exception:
            pass
        if _js_fill(page, 'storyboard-selector-title', title[:100]):
            log.info("  Title filled via JS injection")
            title_filled = True
        else:
            log.info(f"  Current URL: {page.url}")
            _log_visible_inputs(page)
            debug_png = Path(__file__).parent.parent / "output" / "_debug_title_fail.png"
            debug_html = Path(__file__).parent.parent / "output" / "_debug_title_fail.html"
            page.screenshot(path=str(debug_png))
            debug_html.write_text(page.content(), encoding="utf-8")
            raise RuntimeError(f"Could not fill title field. Debug: {debug_png}, {debug_html}")

    page.wait_for_timeout(500)

    _fill_field(page, [
        '[data-test-id="storyboard-description-field-container"] [aria-label="Describe your Pin"]',  # idea-pin-builder (confirmed 2026-06)
        '[aria-label="Describe your Pin"]',              # idea-pin-builder fallback
        '[data-test-id="pin-draft-description"]',        # old pin-creation-tool
        'div[data-test-id="pin-draft-description"] textarea',
        'div[data-test-id="pin-draft-description"] [contenteditable="true"]',
        'textarea[placeholder*="description" i]',
        'textarea[placeholder*="about" i]',
        'textarea[placeholder*="tell" i]',
        '[aria-label*="description" i]',
        '[role="textbox"][aria-label*="description" i]',
        'div[contenteditable="true"]',
        'textarea',
    ], description[:500], "description", required=False)

    page.wait_for_timeout(500)

    _fill_field(page, [
        'input#WebsiteField',                            # idea-pin-builder (confirmed 2026-06)
        'input[placeholder*="add a link" i]',            # idea-pin-builder fallback
        '[data-test-id="pin-draft-link"]',               # old pin-creation-tool
        'input[placeholder*="link" i]',
        'input[placeholder*="destination" i]',
        'input[placeholder*="url" i]',
        'input[name="link"]',
        '[aria-label*="link" i]',
    ], link, "link", required=False)

    page.wait_for_timeout(500)

    # --- Tags ---
    _fill_tags(page, TAGS)


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
    publish_sels = [
        '[data-test-id="board-dropdown-save-button"]',
        '[data-test-id="storyboard-publish-button"]',
        'button:has-text("Publish")',
        'div[role="button"]:has-text("Publish")',
        'button[aria-label*="publish" i]',
        'button:has-text("Done")',
        'button:has-text("Post")',
    ]
    clicked = False
    for sel in publish_sels:
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible(timeout=3000):
                el.click(timeout=8000)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        debug = Path(__file__).parent.parent / "output" / "_debug_publish_fail.png"
        page.screenshot(path=str(debug))
        raise RuntimeError(f"Could not find Publish button. Debug: {debug}")

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

        log.info(f"  Page URL  : {page.url}")
        _upload_image(page, image_path)

        # If the account hit the 50-draft ceiling, bulk-delete all drafts then
        # re-navigate and re-upload so the creation flow starts clean.
        if _clear_draft_limit(page):
            page.goto("https://www.pinterest.com/pin-creation-tool/", timeout=45000)
            _wait_load(page)
            page.wait_for_timeout(2000)
            _upload_image(page, image_path)

        _click_next_if_present(page)
        _fill_pin_details(page, title, description, link, board_name)
        _select_board(page, board_name)
        _publish(page)

        _save_cookies(context)
        browser.close()
        log.info(f"Pin posted: {title[:60]}")
