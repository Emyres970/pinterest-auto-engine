import csv
import json
from pathlib import Path
from datetime import datetime

POSTS_FILE = Path(__file__).parent.parent / "posts.json"
TRACKER_FILE = Path(__file__).parent.parent / "tracker.csv"

# Do not change this schema: existing tracker.csv files remain compatible.
HEADERS = [
    "post_index",
    "title",
    "url",
    "headline",
    "image_path",
    "date_posted",
    "status",
]


def _init_tracker():
    if not TRACKER_FILE.exists():
        with open(TRACKER_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()


def load_posts() -> list:
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def _get_last_posted_index() -> int:
    """
    Return the 1-based index of the last successfully posted post.

    Generated or failed headlines do not advance the posting rotation.
    """
    if not TRACKER_FILE.exists():
        return 0

    with open(TRACKER_FILE, "r", encoding="utf-8", newline="") as f:
        rows = [
            row for row in csv.DictReader(f)
            if row.get("status") == "success"
        ]

    if not rows:
        return 0

    return int(rows[-1]["post_index"])


def get_recent_headlines(
    post_index: int,
    limit: int | None = None,
) -> list[str]:
    """
    Return previously generated headlines for one post, newest first.

    All non-empty headlines are included, regardless of whether Pinterest
    ultimately accepted the pin. This prevents a failed image upload or
    posting attempt from causing the same headline to be generated again.

    limit=None means the complete history. A numeric limit is retained for
    backwards compatibility with existing callers.
    """
    if not TRACKER_FILE.exists():
        return []

    matches = []

    with open(TRACKER_FILE, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("post_index", "")) != str(post_index):
                continue

            headline = (row.get("headline") or "").strip()

            if headline:
                matches.append(headline)

    # Preserve first occurrence while scanning backwards (newest first).
    newest_first = []
    seen = set()

    for headline in reversed(matches):
        key = " ".join(headline.casefold().split())

        if key not in seen:
            seen.add(key)
            newest_first.append(headline)

    if limit is not None:
        return newest_first[:max(0, limit)]

    return newest_first


def get_next_posts(count: int) -> list:
    posts = load_posts()
    total = len(posts)

    if not total or count <= 0:
        return []

    last = _get_last_posted_index()
    result = []

    for i in range(count):
        idx = (last + i) % total
        result.append(posts[idx])

    return result


def log_result(
    post_index: int,
    title: str,
    url: str,
    headline: str,
    image_path: str,
    status: str,
):
    """
    Append one tracker event.

    The existing CSV is append-only. A generated headline can be recorded
    before image creation, then a separate success/failure event can follow.
    """
    _init_tracker()

    with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)

        writer.writerow({
            "post_index": post_index,
            "title": title,
            "url": url,
            "headline": headline,
            "image_path": image_path,
            "date_posted": datetime.now().isoformat(timespec="seconds"),
            "status": status,
        })
