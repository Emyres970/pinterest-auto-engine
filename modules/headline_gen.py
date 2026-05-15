import os
import json
import re
import time
import logging

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write Pinterest pin headlines for a blogger in the narcissism/toxic relationships niche.

REFERENCE STANDARD: A blogger averaging 10M+ monthly Pinterest impressions writes headlines like "Men Are Always Afraid To Lose This Kind Of Woman." That is your bar. Study the energy — it is not informational, it is emotional. It lands like something a reader's wisest, most honest friend would whisper to them at 2 AM when no one else is watching.

YOUR WRITING VOICE: Tim Denning. Almost poetic. Mic-drop ending. Loaded with curiosity. The kind of line a distracted scroller reads once and cannot unread — something that names the exact thing they have been feeling but could not say out loud.

NON-NEGOTIABLE:
1. ROOT KEYWORD — narcissist, narcissists, toxic, or gaslighting must appear in every single headline, no exceptions
2. 12 WORDS MAXIMUM — every word earns its place or gets cut
3. PLAIN WORDS ONLY — a distracted brain must absorb it in under one second; no jargon, no complexity, no therapist-speak
4. NO LISTICLES — never write "7 Signs...", "Here's Why...", "How To...", or any numbered/instructional format

You always respond with valid JSON only. No markdown. No explanation. Just JSON."""

_TEMPLATES = [
    {
        "name": "The Reversal",
        "example": "The Narcissist Feels It Most When You've Already Moved On",
        "instruction": (
            "Write a headline about what the narcissist secretly feels, loses, or experiences "
            "when the reader reclaims their power, heals, or moves on. "
            "The narcissist's hidden reaction is the hook — it gives the reader quiet satisfaction. "
            "Pattern: [What the narcissist experiences] + [when the reader does the empowering thing]."
        ),
    },
    {
        "name": "The Unsettling Truth",
        "example": "The Scariest Thing About A Narcissist's Lie is How Normal it Sounds",
        "instruction": (
            "Write a headline that surfaces a deeply disturbing truth about narcissists that the reader "
            "has felt but couldn't name. The hook is the unsettling observation. "
            "Pattern: 'The [scariest / most painful / most confusing] thing about [narcissist behavior] "
            "is [the disturbing truth].'"
        ),
    },
    {
        "name": "The Secret",
        "example": "Narcissists Secretly Hate People Who Know These Things",
        "instruction": (
            "Write a headline about what narcissists secretly hate, fear, or avoid — specifically "
            "targeting people who are self-aware or have figured them out. "
            "The reader should feel a pull to become that person. "
            "Pattern: 'Narcissists Secretly [hate/fear/avoid] People Who [empowering trait or knowledge].'"
        ),
    },
    {
        "name": "The Unspoken Reality",
        "example": "People Don't Realize How Cruel The Narcissist's Silent Treatment Really Is",
        "instruction": (
            "Write a headline exposing what most people fail to understand about a narcissist behavior — "
            "validating that the reader's pain is real, serious, and not an overreaction. "
            "Pattern: 'People Don't Realize...' or 'Nobody Talks About...' or 'Most People Miss...'"
        ),
    },
    {
        "name": "The Liberating Reframe",
        "example": "Narcissists Never Truly Loved The 'Other Woman' Either",
        "instruction": (
            "Write a headline that delivers a liberating truth about narcissists — one that reframes "
            "the reader's pain, jealousy, shame, or confusion as the narcissist's limitation, not theirs. "
            "The reader should feel relieved, not blamed. "
            "Pattern: a revelation that recontextualizes their experience as proof of the narcissist's emptiness."
        ),
    },
]

_USER_PROMPT_TEMPLATE = """Blog post title: "{title}"

Post content:
{body}

---

STEP 1 — Before writing anything: identify the THREE dominant emotions this post's target reader carries BEFORE they have read it and achieved its outcome. These are the raw, unresolved feelings they bring to the scroll — the pain, the confusion, the quiet rage, the shame, the longing, the exhaustion. Name them precisely.

STEP 2 — Using the "{template_name}" style, write ONE headline that:
- Strikes the dominant emotion that makes this template hit hardest for THIS post
- Matches the energy of this style example: "{template_example}"
- Style guidance: {template_instruction}
- Feels emotionally gut-punching and almost poetic — Tim Denning quality, mic-drop ending
- Carries the pull of a secret being named for the first time
- Includes the root keyword naturally (narcissist, narcissists, toxic, gaslighting) — non-negotiable
- Stays under 12 words, uses plain everyday words only

Also pick 2-4 words to highlight in a contrasting color — the most emotionally charged or keyword-anchoring words in the headline.

Respond with ONLY this JSON:
{{
  "dominant_emotions": ["emotion 1", "emotion 2", "emotion 3"],
  "headline": "the full pin headline here",
  "blue_words": ["word or phrase 1", "word or phrase 2"],
  "emotion": "the specific dominant emotion this headline targets"
}}"""


def _parse_response(text: str) -> dict:
    raw = text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _try_groq(prompt: str) -> dict:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
    )
    return _parse_response(response.choices[0].message.content)


def _try_gemini(prompt: str) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.9,
        ),
        contents=prompt,
    )
    return _parse_response(response.text)


def generate_headline(title: str, body: str, template_index: int = 0) -> dict:
    template = _TEMPLATES[template_index % len(_TEMPLATES)]
    prompt = _USER_PROMPT_TEMPLATE.format(
        title=title,
        body=body[:2500],
        template_name=template["name"],
        template_example=template["example"],
        template_instruction=template["instruction"],
    )
    log.info(f"  Template  : {template['name']}")

    # Gemini first — stronger headline quality; at 15 pins/day we use ~1% of free RPM
    if os.getenv("GEMINI_API_KEY"):
        for attempt in range(3):
            try:
                return _try_gemini(prompt)
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait = 60 * (attempt + 1)
                    log.warning(f"Gemini rate limit — retrying in {wait}s")
                    time.sleep(wait)
                else:
                    log.warning(f"Gemini failed — falling back to Groq: {e}")
                    break

    # Groq fallback
    if os.getenv("GROQ_API_KEY"):
        return _try_groq(prompt)

    raise RuntimeError("No LLM available — set GEMINI_API_KEY or GROQ_API_KEY")
