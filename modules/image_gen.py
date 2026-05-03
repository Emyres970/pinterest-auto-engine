import os
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "pin_template.html"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _build_headline_html(headline: str, blue_words: list) -> str:
    """Wrap accent words in <span class='accent'> and uppercase everything."""
    text = headline.upper()
    highlights = []

    for phrase in blue_words:
        pattern = re.compile(re.escape(phrase.upper()))
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
    brand_name = os.getenv("BRAND_NAME", "WRITE YOUR WORLD")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    headline_html = _build_headline_html(headline, blue_words)
    html = template.replace("{{HEADLINE_HTML}}", headline_html)
    html = html.replace("{{BRAND_NAME}}", brand_name)

    temp_html = OUTPUT_DIR / "_temp_pin.html"
    temp_html.write_text(html, encoding="utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1000, "height": 1500})
            page.goto(f"file:///{temp_html.absolute().as_posix()}")
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(800)
            page.screenshot(path=str(output_path), clip={"x": 0, "y": 0, "width": 1000, "height": 1500})
            browser.close()
    finally:
        if temp_html.exists():
            temp_html.unlink()

    return str(output_path)
