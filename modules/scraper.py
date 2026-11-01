"""
Blogger-first article scraper.

The public scrape_medium_post() name is retained for compatibility with
main.py. It now delegates to scrape_article(), which supports Blogger pages
and common article markup.

Extraction strategy:
1. Prefer Blogger/article-body containers over generic page wrappers.
2. Remove navigation, sidebars, comments, sharing widgets, and other chrome.
3. Extract readable paragraphs and headings without duplicating text.
4. Try Playwright if the HTTP response is incomplete or unusable.
"""

import copy
import logging
import os
import re

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
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# Keep the threshold modest. Some legitimate Blogger posts are short.
_MIN_BODY_CHARS = int(os.getenv("MIN_ARTICLE_CHARS", "300"))

# These selectors are checked in priority order.
_CONTENT_SELECTORS = (
    ".post-body",
    "[itemprop='articleBody']",
    ".entry-content",
    ".post-content",
    ".article-body",
    ".article-content",
    ".blog-post",
    "article",
    "main",
)

_REMOVE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "form",
    "nav",
    "footer",
    "header",
    "aside",
    ".sidebar",
    ".widget",
    ".post-footer",
    ".post-share-buttons",
    ".share-buttons",
    ".comments",
    "#comments",
    ".comment-thread",
    ".related-posts",
    ".popular-posts",
    ".blog-pager",
    ".post-labels",
    ".post-meta",
    ".author-profile",
    ".cookie-banner",
    ".cookie-notice",
    ".newsletter",
    ".subscription",
    ".subscribe-box",
    ".ad",
    ".ads",
    ".advertisement",
)


def _clean_text(value: str) -> str:
    """Normalize whitespace without flattening paragraph boundaries."""
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    return value.strip()


def _extract_title(soup: BeautifulSoup) -> str:
    """Find the most useful page/article title."""
    h1 = soup.find("h1")
    if h1:
        title = _clean_text(h1.get_text(" ", strip=True))
        if title:
            return title

    for attribute in (
        {"property": "og:title"},
        {"name": "twitter:title"},
        {"itemprop": "headline"},
    ):
        tag = soup.find("meta", attrs=attribute)
        if tag:
            title = _clean_text(tag.get("content", ""))
            if title:
                return title

    title_tag = soup.find("title")
    if title_tag:
        return _clean_text(title_tag.get_text(" ", strip=True))

    return ""


def _remove_page_chrome(container):
    """Remove elements that are not part of the article body."""
    for selector in _REMOVE_SELECTORS:
        try:
            for element in container.select(selector):
                element.decompose()
        except Exception:
            # A malformed selector or unusual HTML should not stop extraction.
            continue

    return container


def _extract_container_text(container, title: str = "") -> str:
    """
    Extract paragraphs and structural text from one candidate container.

    Paragraphs are preferred. Headings and blockquotes are retained because
    they often carry important article structure. List items are included
    when they contain meaningful text.
    """
    container = _remove_page_chrome(copy.deepcopy(container))

    elements = container.find_all(
        ["p", "h2", "h3", "h4", "blockquote", "li"]
    )

    parts = []
    seen = set()
    normalized_title = _clean_text(title).casefold()

    for element in elements:
        text = _clean_text(element.get_text(" ", strip=True))

        if not text or len(text) < 20:
            continue

        if text.casefold() == normalized_title:
            continue

        # Avoid repeated text caused by nested or duplicated markup.
        key = re.sub(r"\W+", " ", text.casefold()).strip()
        if not key or key in seen:
            continue

        seen.add(key)
        parts.append(text)

    # Some Blogger themes use divs instead of paragraphs.
    # Use plain container text only when structural extraction found nothing.
    if not parts:
        text = _clean_text(container.get_text(" ", strip=True))
        if text and text.casefold() != normalized_title:
            parts.append(text)

    return "\n\n".join(parts)


def _candidate_score(body: str, selector_priority: int) -> float:
    """
    Rank candidate containers.

    Longer, paragraph-rich containers score better. Selector priority gives
    Blogger's .post-body and articleBody markup an advantage over generic
    article/main wrappers.
    """
    if not body:
        return 0

    paragraphs = [p for p in body.split("\n\n") if len(p.strip()) >= 35]
    length_score = min(len(body), 12000) / 100
    paragraph_score = min(len(paragraphs), 30) * 2
    priority_bonus = max(0, 10 - selector_priority) * 3

    return length_score + paragraph_score + priority_bonus


def _parse_html(html: str) -> dict:
    """
    Parse a page and return:
        {"title": str, "body": str}

    A generic page <body> is deliberately not used as the article container.
    Doing so can silently feed navigation, widgets, and sidebar text to the
    headline model.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    title = _extract_title(soup)

    candidates = []
    seen_containers = set()

    for priority, selector in enumerate(_CONTENT_SELECTORS):
        for container in soup.select(selector):
            # Avoid evaluating the same underlying element more than once.
            identity = id(container)
            if identity in seen_containers:
                continue
            seen_containers.add(identity)

            body = _extract_container_text(container, title)
            if not body:
                continue

            score = _candidate_score(body, priority)
            candidates.append((score, body, selector))

    if not candidates:
        return {"title": title, "body": ""}

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, body, selected_selector = candidates[0]

    log.debug(
        "Article container selected: %s (%s characters)",
        selected_selector,
        len(body),
    )

    return {"title": title, "body": body}


def _is_usable(data: dict) -> bool:
    """Check whether the extracted page has enough usable article content."""
    return bool(
        data
        and data.get("title")
        and len(data.get("body", "").strip()) >= _MIN_BODY_CHARS
    )


def _scrape_with_requests(url: str):
    """Fast extraction path using requests."""
    try:
        response = requests.get(
            url,
            headers=_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()

        data = _parse_html(response.text)

        if _is_usable(data):
            log.info(
                "  HTTP extraction: %s characters",
                len(data["body"]),
            )
            return data

        log.warning(
            "  HTTP extraction looked incomplete (%s characters); "
            "trying browser rendering.",
            len(data.get("body", "")),
        )

    except Exception as exc:
        log.warning("  HTTP scraping failed: %s", exc)

    return None


def _scrape_with_playwright(url: str) -> dict:
    """Browser-rendered fallback for pages that need JavaScript."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

        try:
            context = browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )

            page = context.new_page()

            page.add_init_script(
                "Object.defineProperty("
                "navigator, 'webdriver', {get: () => undefined}"
                ")"
            )

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=45000,
            )

            # Give Blogger's theme and deferred content a moment to render.
            try:
                page.wait_for_selector(
                    ".post-body, [itemprop='articleBody'], "
                    ".entry-content, article",
                    timeout=10000,
                )
            except Exception:
                log.debug("No known article selector appeared before timeout.")

            page.wait_for_timeout(1500)

            # Trigger lazy-loaded content near the bottom of the article.
            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")

            html = page.content()
            return _parse_html(html)

        finally:
            browser.close()


def scrape_article(url: str) -> dict:
    """
    Scrape a Blogger/article URL.

    Returns:
        {
            "title": "Article title",
            "body": "Full extracted article text"
        }

    Raises ValueError when a usable title/body cannot be extracted.
    """
    if not url or not isinstance(url, str):
        raise ValueError("A valid article URL is required.")

    log.info("  Scraping  : %s", url[:120])

    data = _scrape_with_requests(url)
    extraction_method = "requests"

    if not data:
        log.info("  Switching to Playwright...")
        data = _scrape_with_playwright(url)
        extraction_method = "Playwright"

    if not data.get("title"):
        raise ValueError(
            f"Could not extract an article title from: {url}"
        )

    body = data.get("body", "").strip()

    if len(body) < _MIN_BODY_CHARS:
        raise ValueError(
            f"Article extraction returned only {len(body)} characters "
            f"(minimum: {_MIN_BODY_CHARS}). The page may be blocked, "
            f"the article markup may have changed, or the post may be short: "
            f"{url}"
        )

    log.info(
        "  Scraped   : '%s' via %s (%s characters)",
        data["title"][:70],
        extraction_method,
        len(body),
    )

    return {
        "title": data["title"].strip(),
        "body": body,
    }


def scrape_medium_post(friend_link: str) -> dict:
    """
    Backwards-compatible function name used by main.py.

    The argument is now a Blogger URL in the current pipeline. The old name
    remains so existing imports and callers do not need to change.
    """
    return scrape_article(friend_link)
