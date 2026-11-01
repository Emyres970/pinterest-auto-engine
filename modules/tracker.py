import csv
import json
from pathlib import Path
from datetime import datetime

POSTS_FILE = Path(__file__).parent.parent / "posts.json"
TRACKER_FILE = Path(__file__).parent.parent / "tracker.csv"

HEADERS = ["post_index", "title", "url", "headline", "image_path", "date_posted", "status"]


def _init_tracker():
    if not TRACKER_FILE.exists():
        with open(TRACKER_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()


def load_posts() -> list:
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def _get_last_posted_index() -> int:
    """Returns the 1-based index of the last successfully posted post, or 0 if none."""
    if not TRACKER_FILE.exists():
        return 0
    with open(TRACKER_FILE, "r", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("status") == "success"]
    if not rows:
        return 0
    return int(rows[-1]["post_index"])


def get_recent_headlines(post_index: int, limit: int = 30) -> list[str]:
    """Return recent successful headlines for this article, newest first.

    Reads the existing append-only tracker, so no migration or destructive
    rewrite of the user's historical CSV is required.
    """
    if not TRACKER_FILE.exists():
        return []
    matches = []
    with open(TRACKER_FILE, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "success" and str(row.get("post_index", "")) == str(post_index):
                headline = (row.get("headline") or "").strip()
                if headline:
                    matches.append(headline)
    return list(reversed(matches[-limit:]))


def get_next_posts(count: int) -> list:
    posts = load_posts()
    total = len(posts)
    if not total or count <= 0:
        return []
    last = _get_last_posted_index()
    result = []
    for i in range(count):
        idx = (last + i) % total  # 0-based cycling from the last 1-based index
        result.append(posts[idx])
    return result


def log_result(post_index: int, title: str, url: str,
               headline: str, image_path: str, status: str):
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
