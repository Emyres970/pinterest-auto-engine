"""Pinterest headline generation based on the reference headline framework.

The model creates a varied candidate set, then selects one article-faithful
headline. Recent successful headlines for the same post are supplied by the
tracker so repeat pins use a new angle rather than a superficial rewrite.
"""

import difflib
import json
import logging
import os
import re
import time

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an editorial strategist who packages relationship and
narcissistic-abuse articles into clear, high-curiosity Pinterest pin headlines.

Your job is NOT to write literary summaries, inspirational slogans, or generic
emotional observations. Your job is to identify a concrete article-backed
reader question, behaviour, relationship situation, discovery, consequence, or
practical outcome and package it in a familiar Pinterest headline structure.

REFERENCE HEADLINE SYSTEM
Study the underlying mechanics of these structures. Reproduce the mechanics,
not the exact wording:

1. BEHAVIOURAL INVENTORY
   Structure: [Number] [specific behaviours] [person/group] [often/always] do.
   Reader promise: recognizable actions they can check against real life.
   Example pattern: "9 Things Cheaters Always Do On Their Phones."

2. DIAGNOSTIC SIGNS
   Structure: [Number] Signs [person/relationship] [hidden condition or reality].
   Reader promise: identify a situation they suspect but cannot interpret.
   Example pattern: "8 Signs Your Husband Enjoys Hurting You."

3. CONDITIONAL REVELATION
   Structure: When/If [specific situation], [person] [observable response] —
   often followed by [number] Things/Signs/Ways.
   Reader promise: explain what happens in a particular moment or condition.
   Example pattern: "When A Man Hates His Wife, He Says These 7 Things."

4. UNCOMFORTABLE TRUTH
   Structure: The Dark Side of [familiar subject] No One Talks About; or
   [Number] Harsh/Uncomfortable Truths About [subject].
   Reader promise: expose an overlooked cost, contradiction, or reality.

5. COUNTERINTUITIVE INTERPRETATION
   Structure: If you [notice/experience/recognize] [specific evidence],
   [unexpected but article-supported meaning].
   Reader promise: reinterpret an experience or observation.
   Example pattern: "If You Notice These 5 Things..., You're [interpretation]."

6. CONSEQUENCE / CAUSE AND EFFECT
   Structure: [Number] Types/Behaviours/Patterns That Lead to [consequence];
   or Every [group] Who [behaviour] [consequence].
   Reader promise: connect a recognizable pattern to a meaningful outcome.

7. PRACTICAL RESPONSE
   Structure: If [specific problem], Do [specific action] / Try [specific response].
   Reader promise: one useful next step. Use only when the article actually
   provides an actionable response.

EDITORIAL RULES
- Generate a varied set of 8–10 candidates using at least 4 genuinely suitable
  families. Do not force a family that the article cannot support.
- Prefer concrete relationship situations, observable behaviour, recognizable
  phrases, specific consequences, and useful discoveries over abstract pain.
- The reader should immediately understand who/what the pin is about and why
  the information matters.
- Use numbers only when the article contains that many distinct signs, actions,
  examples, reasons, or steps. Never invent a count to make a headline clickable.
- Use "narcissist" or "narcissistic" when it improves clarity and accurately
  describes the article. It is NOT mandatory in every headline. Do not hide the
  subject when doing so would make the headline vague or misleading.
- Do not force every headline to begin with "If" or "When". Vary openings,
  sentence shapes, lengths, and curiosity mechanisms.
- Use plain, conversational language. Avoid ornate metaphors, vague emotional
  fragments, fake profundity, and headlines that sound like essay excerpts.
- Emotional force is welcome, but the headline must make a clear promise.
- No unsupported absolutes ("always", "never", "every") unless the article
  itself supports that claim. Do not diagnose a real person from one behaviour.
- Do not copy reference headlines. Do not use Tim Denning's exact voice; use
  original, direct, provocative, conversational editorial writing.
- Keep most headlines between 6 and 16 words. Clarity beats an arbitrary limit.
- Do not invent facts, advice, signs, statistics, or outcomes absent from the
  article.
- Avoid near-duplicates within the candidate set and against supplied history.

SELECTION
Compare candidates for: article fidelity, immediate clarity, specificity,
curiosity, emotional relevance, and variety from the article's previous pins.
Select the strongest overall candidate, not merely the most dramatic one.
The selected headline MUST exactly match one item in candidates.

OUTPUT
Return only valid JSON in this schema:
{
  "candidates": [
    {"family": "behavioural_inventory", "headline": "...", "score": 1-10},
    {"family": "diagnostic_signs", "headline": "...", "score": 1-10}
  ],
  "selected_headline": "...",
  "selected_family": "...",
  "blue_words": ["word", "phrase"],
  "emotion": "the main reader motivation or emotion",
  "editorial_angle": "one short sentence explaining the selected promise"
}
"""

_USER_PROMPT_TEMPLATE = """ARTICLE TITLE:
{title}

ARTICLE BODY:
{body}

RECENT SUCCESSFUL HEADLINES ALREADY USED FOR THIS SAME ARTICLE.
Do not repeat or closely paraphrase these. Find a genuinely different angle:
{recent_headlines}

TASK
1. Identify the article's actual subject, central argument, distinct points,
   observable behaviours, reader problem, practical advice, and consequences.
2. Decide which reference headline families genuinely fit this article.
3. Generate 8–10 distinct candidate headlines across at least 4 suitable
   families. A family may have more than one candidate if the article supports
   different angles. Do not pad the list with weak or irrelevant candidates.
4. Give each candidate a score from 1 to 10 for article fidelity, clarity,
   specificity, curiosity, and reader relevance considered together.
5. Select the strongest candidate. It must be an exact copy of one candidate.
6. Choose 2–4 meaningful words or short phrases from the selected headline
   for image accent styling. Do not choose articles or filler words.

Return the JSON schema from the system instructions. The article's substance
always takes priority over fitting a template.
"""


def _parse_response(response_text: str) -> dict:
    raw = (response_text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Recover a JSON object if a provider adds a short preamble despite the rule.
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    return json.loads(raw)


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio()


def _select_valid_result(data: dict, recent_headlines: list[str]) -> dict:
    candidates = data.get("candidates") or []
    cleaned = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        headline = re.sub(r"\s+", " ", str(item.get("headline", ""))).strip().strip('"“”')
        family = str(item.get("family", "")).strip()
        if not headline or headline.casefold() in seen:
            continue
        seen.add(headline.casefold())
        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        cleaned.append({"family": family, "headline": headline, "score": score})

    if not cleaned:
        raise ValueError("Headline model returned no usable candidates")

    selected = re.sub(r"\s+", " ", str(data.get("selected_headline", ""))).strip().strip('"“”')
    selected_item = next((c for c in cleaned if c["headline"].casefold() == selected.casefold()), None)

    # If the model selected a headline already used for this article, choose its
    # highest-scoring genuinely different alternative instead.
    history = [h for h in recent_headlines if h]
    def is_recent(candidate: str) -> bool:
        return any(_similarity(candidate, old) >= 0.82 for old in history)

    if selected_item is None or is_recent(selected_item["headline"]):
        available = [c for c in cleaned if not is_recent(c["headline"])]
        if not available:
            raise ValueError("All generated headline candidates duplicate recent pins for this article")
        selected_item = max(available, key=lambda c: c["score"])

    blue_words = data.get("blue_words", [])
    if not isinstance(blue_words, list):
        blue_words = []
    blue_words = [str(w).strip() for w in blue_words if str(w).strip()][:4]

    return {
        "headline": selected_item["headline"],
        "blue_words": blue_words,
        "emotion": str(data.get("emotion", "")).strip(),
        "family": selected_item["family"] or str(data.get("selected_family", "")).strip(),
        "editorial_angle": str(data.get("editorial_angle", "")).strip(),
        "candidates": cleaned,
    }


def _try_groq(prompt: str) -> dict:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.85,
        response_format={"type": "json_object"},
    )
    return _parse_response(response.choices[0].message.content)


def _try_gemini(prompt: str) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.85,
            response_mime_type="application/json",
        ),
        contents=prompt,
    )
    return _parse_response(response.text)


def generate_headline(
    title: str,
    body: str,
    previous_headline: str = "",
    recent_headlines: list[str] | None = None,
) -> dict:
    """Generate a diverse candidate set and return the strongest unused pin headline."""
    history = list(recent_headlines or [])
    if previous_headline and previous_headline not in history:
        history.append(previous_headline)
    prompt = _USER_PROMPT_TEMPLATE.format(
        title=title,
        body=body[:12000],
        recent_headlines="\n".join(f"- {h}" for h in history[-30:]) or "(none recorded yet)",
    )

    errors = []
    if os.getenv("GEMINI_API_KEY"):
        for attempt in range(3):
            try:
                data = _try_gemini(prompt)
                return _select_valid_result(data, history)
            except Exception as exc:
                errors.append(f"Gemini: {exc}")
                if "429" in str(exc) and attempt < 2:
                    wait = 60 * (attempt + 1)
                    log.warning("Gemini rate limit — retrying in %ss", wait)
                    time.sleep(wait)
                else:
                    log.warning("Gemini failed — trying Groq: %s", exc)
                    break

    if os.getenv("GROQ_API_KEY"):
        try:
            return _select_valid_result(_try_groq(prompt), history)
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    raise RuntimeError("Headline generation failed. " + " | ".join(errors or ["Set GEMINI_API_KEY or GROQ_API_KEY"]))
