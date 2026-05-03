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

from modules.headline_gen import generate_headline
from modules.image_gen import generate_image
from modules.pinterest_post import post_pin
from modules.tracker import get_next_posts, log_result

PINS_PER_DAY = int(os.getenv("PINS_PER_DAY", "15"))
DELAY = int(os.getenv("DELAY_BETWEEN_PINS", "600"))  # seconds
BOARD = os.getenv("PINTEREST_BOARD_NAME", "")


def run():
    posts = get_next_posts(PINS_PER_DAY)
    log.info(f"Daily run — posting {len(posts)} pins")

    for i, post in enumerate(posts, start=1):
        idx = post["index"]
        title = post["title"]
        url = post["url"]
        body = post["body"]

        log.info(f"[{i}/{len(posts)}] Post #{idx}: {title[:70]}")

        try:
            # Step 1 — generate headline via Gemini
            result = generate_headline(title, body)
            headline = result["headline"]
            blue_words = result.get("blue_words", [])
            emotion = result.get("emotion", "")
            log.info(f"  Headline  : {headline}")
            log.info(f"  Accent    : {blue_words}  |  Emotion: {emotion}")

            # Step 2 — render pin image
            filename = f"pin_{idx}_{int(time.time())}.png"
            image_path = generate_image(headline, blue_words, filename)
            log.info(f"  Image     : {image_path}")

            # Step 3 — post to Pinterest
            post_pin(
                image_path=image_path,
                title=headline,
                description=headline,
                link=url,
                board_name=BOARD,
            )
            log.info(f"  Status    : posted")
            log_result(idx, title, url, headline, image_path, "success")

        except Exception as e:
            log.error(f"  FAILED: {e}")
            log_result(idx, title, url, "", "", f"failed: {e}")

        if i < len(posts):
            log.info(f"  Waiting {DELAY}s before next pin...")
            time.sleep(DELAY)

    log.info("Daily run complete.")


if __name__ == "__main__":
    run()
