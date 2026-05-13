import os
import json
import re
import time
import logging

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write Pinterest pin headlines for a high-performing blogger in the narcissism/relationships niche.

THE GOAL: A distracted scroller sees this headline for one second. Their brain absorbs it instantly, feels something real, and clicks. That is the only job.

THREE NON-NEGOTIABLE RULES:
1. FOLLOW THE TEMPLATE — each headline must match the specific template style given in the user message
2. SIMPLE WORDS — plain everyday language only. A distracted brain must absorb it in under one second. No jargon, no complexity.
3. KEYWORD PRESENT — narcissist, narcissists, toxic, or gaslighting must appear in every headline, no exceptions.

12 WORDS MAXIMUM — every word earns its place.

DO NOT write listicle or informational style headlines ("7 Signs...", "Here Is Why...").

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

_USER_PROMPT_TEMPLATE = """For a blog post titled: "{title}"

Post content:
{body}

HEADLINE STYLE TO USE: {template_name}
Example of this style: "{template_example}"
Instructions: {template_instruction}

Write one headline in exactly this style that:
- Captures the emotional core of this specific post
- Includes the root keyword naturally (narcissist, narcissists, toxic, gaslighting, etc.) — non-negotiable
- Uses plain, simple words a distracted scroller absorbs in under one second
- Is 12 words maximum

Also pick 2-4 words to highlight in a contrasting color — the most emotionally loaded or keyword-anchoring words.

Respond with ONLY this JSON:
{{
  "headline": "the full pin headline here",
  "blue_words": ["word or phrase 1", "word or phrase 2"],
  "emotion": "the specific emotion being targeted"
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

    # Groq first — 14,400 free RPD, effectively unlimited for 15 pins/day
    if os.getenv("GROQ_API_KEY"):
        try:
            return _try_groq(prompt)
        except Exception as e:
            log.warning(f"Groq failed — falling back to Gemini: {e}")

    # Gemini fallback
    for attempt in range(3):
        try:
            return _try_gemini(prompt)
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 60 * (attempt + 1)
                log.warning(f"Gemini rate limit — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise
