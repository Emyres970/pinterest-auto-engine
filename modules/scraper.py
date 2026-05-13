import logging
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# Minimum body length to consider the scrape successful
_MIN_BODY_CHARS = 300


def _parse_html(html: str) -> dict:
    """Extract title and body text from a Medium article HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    # ── Title ──────────────────────────────────────────────────────────────
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        og = soup.find("meta", property="og:title")
        if og:
            title = (og.get("content") or "").strip()

    # ── Body ───────────────────────────────────────────────────────────────
    # Medium renders the article inside <article>; fall back to <body>.
    container = soup.find("article") or soup.find("body")
    seen = set()
    parts = []

    if container:
        for tag in container.find_all(["p", "h2", "h3", "h4", "blockquote", "li"]):
            text = tag.get_text(separator=" ", strip=True)
            # Skip duplicates, the title itself, and very short strings
            # (nav links, labels, author names, etc.)
            if text and text not in seen and text != title and len(text) > 30:
                parts.append(text)
                seen.add(text)

    return {"title": title, "body": "\n\n".join(parts)}


def _scrape_with_requests(url: str):
    """Fast path: plain HTTP request. Returns None if content looks insufficient."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        data = _parse_html(resp.text)
        if data["title"] and len(data["body"]) >= _MIN_BODY_CHARS:
            return data
    except Exception as e:
        log.debug(f"requests path error: {e}")
    return None


def _scrape_with_playwright(url: str) -> dict:
    """Reliable path: headless Chromium. Used when requests returns thin content."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Mask automation flag
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Scroll to trigger any lazy-loaded paragraphs then wait for JS to settle
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

    return _parse_html(html)


def scrape_medium_post(friend_link: str) -> dict:
    """
    Scrape a Medium article via its friend link and return:
        {"title": str, "body": str}

    Friend links bypass the Medium paywall so the full article is accessible.
    Tries a plain HTTP request first; falls back to Playwright if Medium
    serves a JS-gated page or the extracted content is too thin.
    """
    log.info(f"  Scraping  : {friend_link[:90]}")

    data = _scrape_with_requests(friend_link)
    if data:
        log.info(
            f"  Scraped   : '{data['title'][:60]}' "
            f"via requests ({len(data['body'])} chars)"
        )
        return data

    log.info("  requests returned thin content — switching to Playwright...")
    data = _scrape_with_playwright(friend_link)

    if not data["title"]:
        raise ValueError(f"Could not extract article title from: {friend_link}")
    if len(data["body"]) < _MIN_BODY_CHARS:
        raise ValueError(
            f"Article body too short ({len(data['body'])} chars) — "
            f"possible paywall or broken friend link: {friend_link}"
        )

    log.info(
        f"  Scraped   : '{data['title'][:60]}' "
        f"via Playwright ({len(data['body'])} chars)"
    )
    return data
