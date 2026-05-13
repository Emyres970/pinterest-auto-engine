# Pinterest Auto-Engine

Automated pipeline that turns Medium articles into Pinterest pins — from content scraping through AI headline generation, image rendering, and posting.

---

## How It Works

```
posts.json (url + friend_link)
        │
        ▼
[1] Scraper  ──── opens friend link ──► extracts title + body
        │
        ▼
[2] Gemini   ──── title + body ──────► Pinterest headline + accent words
        │
        ▼
[3] Image Gen ─── headline HTML ─────► 1000×1500 PNG pin image
        │
        ▼
[4] Pinterest ─── image + paywalled URL ► posted pin
        │
        ▼
tracker.csv  ──── logs every result (success / failure + error)
```

---

## posts.json — Adding Posts

Each entry needs only two URLs:

```json
{
  "index": 12,
  "url": "https://medium.com/@you/article-slug-paywall-hash",
  "friend_link": "https://medium.com/@you/article-slug?source=friends_link&sk=TOKEN"
}
```

| Field         | Purpose                                                      |
|---------------|--------------------------------------------------------------|
| `index`       | Unique integer ID (increment from the last entry)            |
| `url`         | The regular (paywalled) Medium URL — becomes the pin's link  |
| `friend_link` | Medium friend link — used to scrape the title and body       |

**Getting the friend link on Medium:**
1. Open your published article on Medium
2. Click the **share icon** → **"Copy friend link"**
3. Paste that URL as `friend_link`

The engine opens the friend link in a headless browser, reads the full article (bypassing the paywall), feeds the content to Gemini, then posts the pin with the paywalled `url` as the destination — so readers land on your article and Medium counts the view.

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

Create a `.env` file in the project root:

```
GEMINI_API_KEY=...
PINTEREST_EMAIL=...
PINTEREST_PASSWORD=...
PINTEREST_BOARD_NAME=Your Board Name
BRAND_NAME=WRITE YOUR WORLD      # appears at the bottom of every pin
PINS_PER_DAY=15                  # pins per run (default 15)
DELAY_BETWEEN_PINS=600           # seconds between posts (default 600)
```

### 3. Log in to Pinterest (first time only)

```bash
python login.py
```

A real Chrome window will open. Log in manually (handles CAPTCHAs, 2FA, etc.). The session is saved to `.pinterest_cookies.json` and reused on all subsequent runs.

### 4. Run

```bash
python main.py
```

---

## Module Reference

| File                          | Role                                                             |
|-------------------------------|------------------------------------------------------------------|
| `main.py`                     | Orchestrator — runs the full pipeline for each post             |
| `posts.json`                  | Content database — one entry per Medium article                 |
| `modules/scraper.py`          | Fetches title + body from a Medium friend link                  |
| `modules/headline_gen.py`     | Calls Gemini to produce a Pinterest-optimised headline          |
| `modules/image_gen.py`        | Renders the headline into a 1000×1500 PNG via Playwright        |
| `modules/pinterest_post.py`   | Automates Pinterest pin creation via headless Chrome            |
| `modules/tracker.py`          | Reads `posts.json`, cycles posts, logs results to `tracker.csv` |
| `templates/pin_template.html` | HTML/CSS template for the pin image                             |
| `login.py`                    | One-time interactive Pinterest login to capture session cookies |
| `tracker.csv`                 | Append-only log of every attempted pin (auto-created)           |

---

## Scraper Behaviour

`modules/scraper.py` uses a two-step approach:

1. **Plain HTTP request** (fast) — sends browser-like headers and parses the SSR HTML with BeautifulSoup. Works for most Medium articles.
2. **Playwright fallback** (reliable) — launches a headless Chromium instance, scrolls the page to trigger lazy-loaded content, then parses the rendered HTML. Used when the HTTP response is too thin (bot detection, JS-gated content).

Friend links are publicly accessible — no Medium account required — so the scraper does not need your credentials.

---

## Content Cycling

Posts are served in order from `posts.json` and cycle indefinitely using modulo arithmetic. The last successfully posted index is read from `tracker.csv`, so runs always continue from where they left off. With 179 posts and 15 pins per day, each article is reused roughly every 12 days with a fresh AI-generated headline each time.

---

## Pin Design

- **Dimensions:** 1000 × 1500 px (Pinterest vertical standard)
- **Font:** Anton (all-caps, bold)
- **Headline colour:** Dark (#111111) with 2–4 accent words in cyan (#4DBFE8)
- **Brand footer:** configurable via `BRAND_NAME` env var
- Font size auto-scales down if the headline overflows the canvas

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `skipped: missing friend_link` | Post has no friend link yet | Add `friend_link` to that entry in `posts.json` |
| `Article body too short` | Friend link expired or broken | Re-copy the friend link from Medium |
| Gemini quota error | Free-tier rate limit hit | Wait or upgrade Gemini plan |
| Pinterest board not found | Board name mismatch | Check `PINTEREST_BOARD_NAME` matches exactly |
| Pinterest login loop | Cookies expired | Re-run `python login.py` |
