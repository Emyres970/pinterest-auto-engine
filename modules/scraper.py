"""
Blogger-first article scraper.

Extraction order:
1. Blogger Atom feed (full post content).
2. Existing requests/HTML extraction.
3. Existing Playwright/browser extraction.

Every source is checked for minimum completeness before its content is
returned to the headline generator. The legacy scrape_medium_post() name
is retained for compatibility with main.py.
"""

import copy
import html
import logging
import os
import re
from urllib.parse import urlparse, urlunparse

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
    "Accept": "text/html,application/xhtml+xml,application/atom+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

_MIN_BODY_CHARS = int(os.getenv("MIN_ARTICLE_CHARS", "300"))
_MIN_BODY_WORDS = int(os.getenv("MIN_ARTICLE_WORDS", "120"))
_MIN_PARAGRAPHS = int(os.getenv("MIN_ARTICLE_PARAGRAPHS", "3"))

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
    value = (value or "").replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    return value.strip()


def _word_count(body: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", body or ""))


def _paragraph_count(body: str) -> int:
    return len([
        part for part in re.split(r"\n\s*\n", body or "")
        if len(part.strip()) >= 25
    ])


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
            continue

    return container


def _extract_container_text(container, title: str = "") -> str:
    """Extract paragraphs and structural text from one article container."""
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

        key = re.sub(r"\W+", " ", text.casefold()).strip()
        if not key or key in seen:
            continue

        seen.add(key)
        parts.append(text)

    if not parts:
        text = _clean_text(container.get_text(" ", strip=True))
        if text and text.casefold() != normalized_title:
            parts.append(text)

    return "\n\n".join(parts)


def _candidate_score(body: str, selector_priority: int) -> float:
    """Prefer long, paragraph-rich Blogger article containers."""
    if not body:
        return 0

    paragraphs = [
        p for p in body.split("\n\n")
        if len(p.strip()) >= 35
    ]

    length_score = min(len(body), 20000) / 100
    paragraph_score = min(len(paragraphs), 40) * 2
    priority_bonus = max(0, 10 - selector_priority) * 3

    return length_score + paragraph_score + priority_bonus


def _parse_html(html_text: str) -> dict:
    """
    Parse a rendered Blogger page.

    A generic page <body> is deliberately not used as the article container.
    """
    soup = BeautifulSoup(html_text or "", "html.parser")
    title = _extract_title(soup)

    candidates = []
    seen_containers = set()

    for priority, selector in enumerate(_CONTENT_SELECTORS):
        for container in soup.select(selector):
            identity = id(container)
            if identity in seen_containers:
                continue

            seen_containers.add(identity)
            body = _extract_container_text(container, title)

            if not body:
                continue

            candidates.append((
                _candidate_score(body, priority),
                body,
                selector,
            ))

    if not candidates:
        return {"title": title, "body": ""}

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, body, selected_selector = candidates[0]

    log.debug(
        "HTML article container: %s; %s words; %s paragraphs",
        selected_selector,
        _word_count(body),
        _paragraph_count(body),
    )

    return {"title": title, "body": body}


def _normalise_article_url(url: str) -> str:
    """Normalize URLs for matching Blogger feed entries."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        "",
        "",
        "",
    ))


def _feed_url_for_article(article_url: str) -> str:
    """Build the Atom feed URL for the article's Blogger host."""
    parsed = urlparse(article_url)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Article URL must be an absolute HTTP(S) URL.")

    return (
        f"{parsed.scheme}://{parsed.netloc}"
        "/feeds/posts/default?alt=atom&max-results=500"
    )


def _extract_feed_entry_body(content_value: str) -> str:
    """Convert Blogger's Atom content HTML into readable article text."""
    decoded = html.unescape(content_value or "")
    soup = BeautifulSoup(decoded, "html.parser")

    _remove_page_chrome(soup)

    elements = soup.find_all(
        ["p", "h2", "h3", "h4", "blockquote", "li"]
    )

    parts = []
    seen = set()

    for element in elements:
        text = _clean_text(element.get_text(" ", strip=True))

        if not text or len(text) < 20:
            continue

        key = re.sub(r"\W+", " ", text.casefold()).strip()
        if key and key not in seen:
            seen.add(key)
            parts.append(text)

    if not parts:
        text = _clean_text(soup.get_text(" ", strip=True))
        if text:
            parts.append(text)

    return "\n\n".join(parts)


def _scrape_with_blogger_feed(url: str):
    """
    Retrieve the exact article from Blogger's Atom feed.

    Blogger's <content> element is used, not its <summary> element. A
    summary-only feed is therefore not mistaken for a complete article.
    """
    try:
        feed_url = _feed_url_for_article(url)

        response = requests.get(
            feed_url,
            headers=_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        entries = soup.find_all("entry")

        if not entries:
            log.warning("Blogger feed returned no entries: %s", feed_url)
            return None

        requested_url = _normalise_article_url(url)

        for entry in entries:
            alternate_links = entry.find_all(
                "link",
                attrs={"rel": "alternate"},
            )

            entry_urls = [
                _normalise_article_url(link.get("href", ""))
                for link in alternate_links
                if link.get("href")
            ]

            if requested_url not in entry_urls:
                continue

            title_tag = entry.find("title")
            title = _clean_text(
                title_tag.get_text(" ", strip=True) if title_tag else ""
            )

            content_tag = entry.find("content")
            if content_tag is None:
                log.warning(
                    "Blogger feed matched the post but contained no full "
                    "<content> element. It may be summary-only."
                )
                return None

            content_value = (
                content_tag.string
                if content_tag.string is not None
                else content_tag.get_text()
            )

            body = _extract_feed_entry_body(content_value)

            result = {
                "title": title,
                "body": body,
                "source": "blogger_atom_feed",
            }

            valid, reason = _validate_article(result)

            if not valid:
                log.warning(
                    "Blogger feed matched the post but failed completeness "
                    "validation: %s",
                    reason,
                )
                return None

            log.info(
                "Blogger feed extraction: %s words, %s paragraphs",
                _word_count(body),
                _paragraph_count(body),
            )
            return result

        log.warning(
            "Requested article was not found in Blogger feed: %s",
            requested_url,
        )

    except Exception as exc:
        log.warning("Blogger feed extraction failed: %s", exc)

    return None


def _validate_article(data: dict) -> tuple[bool, str]:
    """Reject empty, obviously truncated, or structurally incomplete text."""
    if not data:
        return False, "No extraction result."

    title = _clean_text(data.get("title", ""))
    body = (data.get("body") or "").strip()

    if not title:
        return False, "Article title is missing."

    if len(body) < _MIN_BODY_CHARS:
        return False, (
            f"Only {len(body)} characters; minimum is {_MIN_BODY_CHARS}."
        )

    words = _word_count(body)
    if words < _MIN_BODY_WORDS:
        return False, (
            f"Only {words} words; minimum is {_MIN_BODY_WORDS}."
        )

    paragraphs = _paragraph_count(body)
    if paragraphs < _MIN_PARAGRAPHS:
        return False, (
            f"Only {paragraphs} substantial paragraphs; "
            f"minimum is {_MIN_PARAGRAPHS}."
        )

    return True, "passed"


def _is_usable(data: dict) -> bool:
    valid, _ = _validate_article(data)
    return valid


def _scrape_with_requests(url: str):
    """Existing fast HTML extraction fallback."""
    try:
        response = requests.get(
            url,
            headers=_HEADERS,
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()

        data = _parse_html(response.text)
        valid, reason = _validate_article(data)

        if valid:
            data["source"] = "requests_html"
            log.info(
                "HTTP extraction passed: %s words, %s paragraphs",
                _word_count(data["body"]),
                _paragraph_count(data["body"]),
            )
            return data

        log.warning("HTTP extraction incomplete: %s", reason)

    except Exception as exc:
        log.warning("HTTP scraping failed: %s", exc)

    return None


def _scrape_with_playwright(url: str) -> dict:
    """Existing browser-rendered fallback."""
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

            try:
                page.wait_for_selector(
                    ".post-body, [itemprop='articleBody'], "
                    ".entry-content, article",
                    timeout=10000,
                )
            except Exception:
                log.debug("No known article selector appeared before timeout.")

            page.wait_for_timeout(1500)
            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, 0)")

            data = _parse_html(page.content())
            data["source"] = "playwright_html"
            return data

        finally:
            browser.close()


def scrape_article(url: str) -> dict:
    """
    Extract and validate a complete Blogger article.

    Returns title, body and extraction diagnostics. Raises ValueError if
    every extraction method fails validation.
    """
    if not url or not isinstance(url, str):
        raise ValueError("A valid article URL is required.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid article URL: {url}")

    log.info("  Scraping  : %s", url[:150])

    methods = (
        ("Blogger feed", _scrape_with_blogger_feed),
        ("HTTP", _scrape_with_requests),
        ("Playwright", _scrape_with_playwright),
    )

    failures = []

    for method_name, method in methods:
        try:
            data = method(url)

            if not data:
                failures.append(f"{method_name}: no article returned")
                continue

            valid, reason = _validate_article(data)

            if not valid:
                failures.append(f"{method_name}: {reason}")
                log.warning(
                    "%s result rejected: %s",
                    method_name,
                    reason,
                )
                continue

            body = data["body"].strip()
            words = _word_count(body)
            paragraphs = _paragraph_count(body)

            log.info(
                "  Scraped   : '%s' via %s (%s words, %s paragraphs)",
                data["title"][:70],
                data.get("source", method_name),
                words,
                paragraphs,
            )

            return {
                "title": data["title"].strip(),
                "body": body,
                "source": data.get("source", method_name),
                "word_count": words,
                "paragraph_count": paragraphs,
            }

        except Exception as exc:
            failures.append(f"{method_name}: {exc}")
            log.exception("%s extraction raised an exception.", method_name)

    detail = " | ".join(failures)

    raise ValueError(
        "No extraction method produced a sufficiently complete article. "
        "The headline generator was not called. "
        f"Diagnostics: {detail}. URL: {url}"
    )


def scrape_medium_post(friend_link: str) -> dict:
    """Backward-compatible name retained for the existing main.py import."""
    return scrape_article(friend_link)
