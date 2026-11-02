
import json
import os
import time
import logging
from collections import Counter

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
from modules.tracker import (
    get_next_posts,
    get_recent_headlines,
    log_result,
)

PINS_PER_DAY = int(os.getenv("PINS_PER_DAY", "15"))
DELAY = int(os.getenv("DELAY_BETWEEN_PINS", "180"))
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


def _print_run_summary(stats: dict, failure_stages: Counter):
    """Print a readable summary without changing workflow success behaviour."""
    log.info("")
    log.info("=" * 60)
    log.info("PINTEREST AUTOMATION — RUN SUMMARY")
    log.info("=" * 60)

    log.info("Posts selected       : %s", stats["attempted"])
    log.info("Articles scraped     : %s", stats["scraped"])
    log.info("Headlines generated  : %s", stats["headline_generated"])
    log.info("Images generated     : %s", stats["images_generated"])
    log.info("Pins posted          : %s", stats["posted"])
    log.info("Posts skipped        : %s", stats["skipped"])
    log.info("Posts with failures  : %s", stats["failed"])

    if failure_stages:
        log.info("")
        log.info("FAILURES BY STAGE")

        for stage, count in sorted(failure_stages.items()):
            log.info("  %-24s : %s", stage, count)

    if stats["posted"] == stats["attempted"] and stats["attempted"] > 0:
        log.info("")
        log.info("Result: Every selected post completed the publishing flow.")
    elif stats["posted"] > 0:
        log.info("")
        log.info(
            "Result: Partial completion. %s pin(s) completed the publishing "
            "flow; %s post(s) were skipped or encountered errors.",
            stats["posted"],
            stats["skipped"] + stats["failed"],
        )
    elif stats["attempted"] == 0:
        log.info("")
        log.info("Result: No posts were selected for this run.")
    else:
        log.warning("")
        log.warning(
            "Result: No pins completed the publishing flow. "
            "Review the errors above."
        )

    log.info("=" * 60)


def run():
    posts = get_next_posts(PINS_PER_DAY)

    stats = {
        "attempted": len(posts),
        "scraped": 0,
        "headline_generated": 0,
        "images_generated": 0,
        "posted": 0,
        "skipped": 0,
        "failed": 0,
    }

    failure_stages = Counter()

    log.info("Daily run — posting %s pins", len(posts))

    for i, post in enumerate(posts, start=1):
        idx = post["index"]
        url = post["url"]
        friend_link = post.get("friend_link", "").strip()

        if not friend_link:
            stats["skipped"] += 1

            log.error(
                "[%s/%s] Post #%s — friend_link is empty.",
                i,
                len(posts),
                idx,
            )

            log_result(
                idx,
                "",
                url,
                "",
                "",
                "skipped: missing friend_link",
            )

            continue

        log.info("[%s/%s] Post #%s", i, len(posts), idx)

        title = ""
        headline = ""
        headline_recorded = False

        # This value lets the final summary identify where an exception
        # happened without changing the existing tracker CSV schema.
        current_stage = "scraping"

        try:
            # -----------------------------------------------------------
            # STAGE 1: SCRAPING
            # -----------------------------------------------------------

            scraped = scrape_medium_post(friend_link)

            title = scraped["title"]
            body = scraped["body"]

            stats["scraped"] += 1

            log.info(
                "  Extraction: %s | %s words | %s paragraphs",
                scraped.get("source", "unknown"),
                scraped.get("word_count", "unknown"),
                scraped.get("paragraph_count", "unknown"),
            )

            # -----------------------------------------------------------
            # STAGE 2: HEADLINE GENERATION
            # -----------------------------------------------------------

            current_stage = "headline_generation"

            recent_headlines = get_recent_headlines(idx)

            result = generate_headline(
                title,
                body,
                recent_headlines=recent_headlines,
            )

            headline = result["headline"]
            blue_words = result.get("blue_words", [])
            emotion = result.get("emotion", "")
            family = result.get("family", "")

            stats["headline_generated"] += 1

            log.info("  Headline  : %s", headline)
            log.info("  Family    : %s", family)

            log.info(
                "  Accent    : %s  |  Emotion: %s",
                blue_words,
                emotion,
            )

            if result.get("editorial_angle"):
                log.info("  Angle     : %s", result["editorial_angle"])

            log.info(
                "  Candidates: %s",
                len(result.get("candidates", [])),
            )

            # Record immediately. If image generation or Pinterest upload
            # fails, this exact headline is still excluded next time.
            log_result(
                idx,
                title,
                url,
                headline,
                "",
                "generated",
            )

            headline_recorded = True

            # -----------------------------------------------------------
            # STAGE 3: IMAGE GENERATION
            # -----------------------------------------------------------

            current_stage = "image_generation"

            filename = f"pin_{idx}_{int(time.time())}.png"

            image_path = generate_image(
                headline,
                blue_words,
                filename,
            )

            stats["images_generated"] += 1

            # -----------------------------------------------------------
            # STAGE 4: PINTEREST PUBLISHING
            # -----------------------------------------------------------

            current_stage = "pinterest_publishing"

            post_pin(
                image_path=image_path,
                title=headline,
                description=headline,
                link=url,
                board_name=_resolve_board(post),
            )

            # This count records successful completion of post_pin().
            # It does not independently verify the pin on Pinterest.
            stats["posted"] += 1

            log.info("  Status    : posted")

            log_result(
                idx,
                title,
                url,
                headline,
                image_path,
                "success",
            )

        except Exception as exc:
            stats["failed"] += 1
            failure_stages[current_stage] += 1

            log.exception(
                "  FAILED during %s: %s",
                current_stage,
                exc,
            )

            # If generation never succeeded, record the failure as before.
            # If a headline was already recorded, do not write a second
            # failed event containing an empty headline.
            if not headline_recorded:
                log_result(
                    idx,
                    title,
                    url,
                    "",
                    "",
                    f"failed: {exc}",
                )
            else:
                log_result(
                    idx,
                    title,
                    url,
                    headline,
                    "",
                    f"failed_after_generation: {exc}",
                )

        if i < len(posts):
            log.info("  Waiting %ss before next pin...", DELAY)
            time.sleep(DELAY)

    _print_run_summary(stats, failure_stages)

    log.info("Daily run complete.")


if __name__ == "__main__":
    run()
