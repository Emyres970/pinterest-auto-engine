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
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] == "success"]
    if not rows:
        return 0
    return int(rows[-1]["post_index"])


def get_next_posts(count: int) -> list:
    posts = load_posts()
    total = len(posts)
    last = _get_last_posted_index()
    result = []
    for i in range(count):
        idx = (last + i) % total  # 0-based cycling
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
