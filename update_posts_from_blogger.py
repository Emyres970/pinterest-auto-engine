"""
Run this locally to replace posts.json (currently ~80 Medium posts) with the
Narc Spotlight blog post list. Fetches each URL, extracts the title and any
Blogger labels/categories, and writes a fresh posts.json. The old posts.json
is backed up to posts_medium_archive.json first so nothing is lost.

Usage:
    python update_posts_from_blogger.py
"""
import json
import shutil
from pathlib import Path

import requests
from bs4 import BeautifulSoup

POSTS_FILE = Path(__file__).parent / "posts.json"
ARCHIVE_FILE = Path(__file__).parent / "posts_medium_archive.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

URLS = [
    "https://narcspotlight.blogspot.com/2025/08/youre-not-broken-youve-just-forgotten.html",
    "https://narcspotlight.blogspot.com/2025/08/7-little-habits-that-make-you-instantly.html",
    "https://narcspotlight.blogspot.com/2025/08/10-everyday-clues-that-prove-youre-not.html",
    "https://narcspotlight.blogspot.com/2025/08/the-church-lady-narcissist-when.html",
    "https://narcspotlight.blogspot.com/2025/09/14-brutal-truths-about-healing-after.html",
    "https://narcspotlight.blogspot.com/2025/09/how-to-build-future-youd-swipe-right.html",
    "https://narcspotlight.blogspot.com/2025/10/society-cant-tell-difference-between.html",
    "https://narcspotlight.blogspot.com/2025/10/im-unstoppable.html",
    "https://narcspotlight.blogspot.com/2025/10/the-loud-silence.html",
    "https://narcspotlight.blogspot.com/2025/10/pulling-strings.html",
    "https://narcspotlight.blogspot.com/2025/10/7-boundaries-narcissists-hate-and-why.html",
    "https://narcspotlight.blogspot.com/2025/10/the-painful-double-standards.html",
    "https://narcspotlight.blogspot.com/2025/10/why-narcissist-needs-audience-more-than.html",
    "https://narcspotlight.blogspot.com/2025/10/the-moment-you-realize-you-were-never.html",
    "https://narcspotlight.blogspot.com/2025/10/7-subtle-things-you-start-doing-after.html",
    "https://narcspotlight.blogspot.com/2025/11/the-lie-no-one-warned-you-about.html",
    "https://narcspotlight.blogspot.com/2025/11/the-narcissists-wallet-why-image.html",
    "https://narcspotlight.blogspot.com/2025/11/gaslighting-starts-at-home-how.html",
    "https://narcspotlight.blogspot.com/2025/11/7-things-that-help-you-trust-your-own.html",
    "https://narcspotlight.blogspot.com/2025/11/is-marriage-partnership-or-financial.html",
    "https://narcspotlight.blogspot.com/2025/11/you-can-live-with-narcissist-and-still.html",
    "https://narcspotlight.blogspot.com/2025/11/the-narcissists-love-bombing-is.html",
    "https://narcspotlight.blogspot.com/2025/12/how-narcissists-use-reactive-abuse-to.html",
    "https://narcspotlight.blogspot.com/2025/12/the-discard-phasehow-assumptions-blind.html",
    "https://narcspotlight.blogspot.com/2025/12/how-narcissists-keep-you-hoping-for.html",
    "https://narcspotlight.blogspot.com/2025/12/the-5-journals-that-help-you-untangle.html",
    "https://narcspotlight.blogspot.com/2025/12/7-signs-youre-dealing-with-nice-guygirl.html",
    "https://narcspotlight.blogspot.com/2025/12/the-narcissist-left-malware-in-your.html",
    "https://narcspotlight.blogspot.com/2025/12/why-nice-narcissist-is-hardest-to-leave.html",
    "https://narcspotlight.blogspot.com/2025/12/6-lessons-that-teach-you-how-power.html",
    "https://narcspotlight.blogspot.com/2026/01/5-daily-grounding-rituals-that-help-you.html",
    "https://narcspotlight.blogspot.com/2026/01/7-conversation-shifts-narcissists-cant.html",
    "https://narcspotlight.blogspot.com/2026/01/if-you-had-to-fall-apart-to-matter-to.html",
    "https://narcspotlight.blogspot.com/2026/01/7-signs-youre-dealing-with-theological.html",
    "https://narcspotlight.blogspot.com/2026/02/7-reasons-why-your-silence-is.html",
    "https://narcspotlight.blogspot.com/2026/02/the-quiet-emotional-shift-that-makes.html",
    "https://narcspotlight.blogspot.com/2026/02/the-brutal-truth-about-winning-against.html",
    "https://narcspotlight.blogspot.com/2026/05/i-thought-i-was-missing-him-i-was.html",
]


def _extract(url: str) -> dict:
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        og = soup.find("meta", property="og:title")
        if og:
            title = (og.get("content") or "").strip()

    # Blogger renders labels as <a rel="tag">, or inside .post-labels / .label-content
    labels = []
    for a in soup.select('a[rel="tag"]'):
        text = a.get_text(strip=True)
        if text and text not in labels:
            labels.append(text)
    if not labels:
        for el in soup.select(".post-labels a, .label-content a, .labels a"):
            text = el.get_text(strip=True)
            if text and text not in labels:
                labels.append(text)

    # Sanity check the post body extracted cleanly (mirrors modules/scraper.py's logic)
    container = soup.find("article") or soup.select_one(".post-body") or soup.find("body")
    body_len = 0
    if container:
        body_len = len(container.get_text(strip=True))

    return {"title": title, "category": ", ".join(labels), "body_len": body_len}


def main():
    if not URLS:
        print("URLS list is empty — nothing to do.")
        return

    if POSTS_FILE.exists():
        shutil.copy(POSTS_FILE, ARCHIVE_FILE)
        print(f"Backed up existing posts.json -> {ARCHIVE_FILE.name}")

    new_posts = []
    for i, url in enumerate(URLS, start=1):
        try:
            data = _extract(url)
            print(f"[{i}/{len(URLS)}] {data['title'][:60]!r}  "
                  f"category={data['category'] or '(none found)'}  "
                  f"body_chars={data['body_len']}")
            if data["body_len"] < 300:
                print(f"    WARNING: body looks thin — check this page's markup manually: {url}")
            new_posts.append({
                "index": i,
                "url": url,
                "friend_link": url,  # no paywall on the blog — same link for scraping and destination
                "title": data["title"],
                "category": data["category"],
            })
        except Exception as e:
            print(f"[{i}/{len(URLS)}] FAILED on {url}: {e}")
            new_posts.append({
                "index": i,
                "url": url,
                "friend_link": url,
                "title": "",
                "category": "",
            })

    POSTS_FILE.write_text(json.dumps(new_posts, indent=2), encoding="utf-8")
    print(f"\nWrote {len(new_posts)} posts to posts.json")


if __name__ == "__main__":
    main()
