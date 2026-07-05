import os
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Template rotation list.  Each entry:
#   html_file  – filename inside templates/
#   uppercase  – whether to force-uppercase the headline text
#
# Templates cycle by post_index % len(TEMPLATES), so posts are evenly
# spread across designs over time.  Add more entries here to grow the pool.
TEMPLATES = [
    {"html_file": "pin_template.html",           "uppercase": True},
    {"html_file": "pin_template_olive.html",     "uppercase": False},
    {"html_file": "pin_template_spotlight.html", "uppercase": False},
]


def _build_headline_html(headline: str, blue_words: list, uppercase: bool = True) -> str:
    """Wrap accent words in <span class='accent'>; optionally uppercase the text."""
    text = headline.upper() if uppercase else headline

    # Build a case-matched version of each blue_word to locate it in `text`
    highlights = []
    for phrase in blue_words:
        search_phrase = phrase.upper() if uppercase else phrase
        pattern = re.compile(re.escape(search_phrase), re.IGNORECASE)
        for match in pattern.finditer(text):
            highlights.append((match.start(), match.end(), match.group()))

    # Sort by position, remove overlaps
    highlights.sort(key=lambda x: x[0])
    deduped = []
    last_end = 0
    for start, end, word in highlights:
        if start >= last_end:
            deduped.append((start, end, word))
            last_end = end

    result = ""
    last_pos = 0
    for start, end, word in deduped:
        result += text[last_pos:start]
        result += f'<span class="accent">{word}</span>'
        last_pos = end
    result += text[last_pos:]

    return result


def generate_image(headline: str, blue_words: list, filename: str) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / filename

    brand_name = os.getenv("BRAND_NAME", "Narc Spotlight")
    brand_url  = os.getenv("BRAND_URL",  "narcspotlight.com")

    # Pick template by cycling on the post index embedded in the filename
    # (filename format: "pin_{post_index}_{timestamp}.png")
    post_idx = 0
    m = re.match(r"pin_(\d+)_", filename)
    if m:
        post_idx = int(m.group(1))

    tpl_cfg = TEMPLATES[post_idx % len(TEMPLATES)]
    template_path = TEMPLATES_DIR / tpl_cfg["html_file"]
    uppercase = tpl_cfg["uppercase"]

    template = template_path.read_text(encoding="utf-8")
    headline_html = _build_headline_html(headline, blue_words, uppercase=uppercase)
    html = template.replace("{{HEADLINE_HTML}}", headline_html)
    html = html.replace("{{BRAND_NAME}}", brand_name)
    html = html.replace("{{BRAND_URL}}",  brand_url)

    temp_html = OUTPUT_DIR / "_temp_pin.html"
    temp_html.write_text(html, encoding="utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1000, "height": 1500})
            page.goto(f"file:///{temp_html.absolute().as_posix()}")
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(800)
            page.screenshot(
                path=str(output_path),
                clip={"x": 0, "y": 0, "width": 1000, "height": 1500},
            )
            browser.close()
    finally:
        if temp_html.exists():
            temp_html.unlink()

    return str(output_path)
