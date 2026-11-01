import json
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from modules.scraper import scrape_medium_post
from modules.headline_gen import generate_headline
from modules.image_gen import generate_image
from modules.pinterest_post import post_pin
from modules.tracker import get_next_posts, get_recent_headlines, log_result

PINS_PER_DAY = int(os.getenv("PINS_PER_DAY", "15"))
DELAY = int(os.getenv("DELAY_BETWEEN_PINS", "180"))  # seconds
BOARD = os.getenv("PINTEREST_BOARD_NAME", "")

_raw_map = os.getenv("PINTEREST_BOARD_MAP", "")
BOARD_MAP: dict = json.loads(_raw_map) if _raw_map else {}


def _resolve_board(post: dict) -> str:
    """Return the correct board name for this post."""
    if not BOARD_MAP:
        return BOARD
    for cat in post.get("categories", []):
        if cat in BOARD_MAP:
            return BOARD_MAP[cat]
    return next(iter(BOARD_MAP.values()))


def run():
    posts = get_next_posts(PINS_PER_DAY)
    log.info("Daily run — posting %s pins", len(posts))

    for i, post in enumerate(posts, start=1):
        idx = post["index"]
        url = post["url"]
        friend_link = post.get("friend_link", "").strip()

        if not friend_link:
            log.error("[%s/%s] Post #%s — friend_link is empty.", i, len(posts), idx)
            log_result(idx, "", url, "", "", "skipped: missing friend_link")
            continue

        log.info("[%s/%s] Post #%s", i, len(posts), idx)
        title = ""

        try:
            scraped = scrape_medium_post(friend_link)
            title = scraped["title"]
            body = scraped["body"]

            # Article-specific history restores the manual workflow's variety:
            # the same post can return later with a different editorial angle.
            recent_headlines = get_recent_headlines(idx, limit=30)
            result = generate_headline(
                title,
                body,
                recent_headlines=recent_headlines,
            )
            headline = result["headline"]
            blue_words = result.get("blue_words", [])
            emotion = result.get("emotion", "")
            family = result.get("family", "")
            log.info("  Headline  : %s", headline)
            log.info("  Family    : %s", family)
            log.info("  Accent    : %s  |  Emotion: %s", blue_words, emotion)
            if result.get("editorial_angle"):
                log.info("  Angle     : %s", result["editorial_angle"])
            log.info("  Candidates: %s", len(result.get("candidates", [])))

            filename = f"pin_{idx}_{int(time.time())}.png"
            image_path = generate_image(headline, blue_words, filename)

            post_pin(
                image_path=image_path,
                title=headline,
                description=headline,
                link=url,
                board_name=_resolve_board(post),
            )
            log.info("  Status    : posted")
            log_result(idx, title, url, headline, image_path, "success")

        except Exception as exc:
            log.exception("  FAILED: %s", exc)
            log_result(idx, title, url, "", "", f"failed: {exc}")

        if i < len(posts):
            log.info("  Waiting %ss before next pin...", DELAY)
            time.sleep(DELAY)

    log.info("Daily run complete.")


if __name__ == "__main__":
    run()
