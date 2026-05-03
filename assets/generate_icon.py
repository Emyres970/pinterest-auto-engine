from pathlib import Path
from playwright.sync_api import sync_playwright

template = Path(__file__).parent / "_icon_template.html"
output = Path(__file__).parent / "app_icon.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 512, "height": 512})
    page.goto(f"file:///{template.absolute().as_posix()}")
    page.wait_for_load_state("networkidle", timeout=10000)
    page.wait_for_timeout(1000)
    page.screenshot(path=str(output), clip={"x": 0, "y": 0, "width": 512, "height": 512})
    browser.close()

print(f"Icon saved: {output}")
