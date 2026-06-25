import os
import json
import re
import time
import logging

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Pinterest headline writer specialising in narcissistic abuse recovery
content for women. Your headlines perform at 10M+ monthly impressions because
they do one thing: they make a woman feel seen before she clicks.

VOICE RULES (non-negotiable):
- Write like Tim Denning crossed with Roxane Gay — emotionally precise,
  slightly devastating, never preachy
- Sentence case only. No hashtags. No emojis. No quotation marks around
  the headline
- 8–14 words. This is a hard ceiling, not a guideline
- The word "Narcissist," "Narcissistic," or "Narcissistic Abuse" must appear
  naturally in every headline — not bolted on, woven in
- Never write a listicle headline ("7 Ways To..."). Reframe the insight as
  a statement of truth
- Never use the words "journey," "toxic," or "empower"
- Mixed case always. Never all caps. Never fewer than 8 words.

WHAT SEPARATES A RECOGNITION FROM A SLOGAN:
- A slogan states a fact: "Narcissists can't love you"
- A recognition makes her feel witnessed: "The Love a Narcissist Keeps
  Promising Was Never Coming — It Was Just Keeping You In Place"
- The recognition names her specific experience, not the general category
- She should read it and think "how did they know" — not "yes that's true"
- Every headline must come from the emotional archaeology below — never
  from the post title directly

QUALITY TEST — before returning output, ask yourself:
- Would a woman who has never heard of this blog stop scrolling for this?
- Does it speak to how she felt BEFORE she understood what was happening?
- Is it a truth she knows somewhere in her body but has never heard said
  this plainly?
- Does it read like a recognition, not a slogan?
If any answer is no, rewrite before returning.

OUTPUT: Return only valid JSON. No preamble, no markdown fences,
no explanation outside the JSON."""

_USER_PROMPT_TEMPLATE = """POST TITLE: {title}

POST BODY (excerpt — first 2000 words):
{body}

PREVIOUSLY GENERATED HEADLINE (do not resemble this — use a completely different
emotional entry point and a different move):
{previous_headline}

---

STEP 1 — EMOTIONAL ARCHAEOLOGY (complete this fully before writing anything else)

Read the post body carefully. Then answer all three questions in full sentences
before moving on:

1. What specific experience is this woman having the morning she finds this post?
   Do not say "she is hurt" or "she is confused." Describe the specific texture
   of her situation — what she did this morning, what she told herself, what she
   is privately afraid is true about her.

2. What is the ONE thing she blames herself for that this post will reframe?
   Name it precisely.

3. What is she secretly afraid is true about herself — the belief she has never
   said out loud to anyone?

Write these three answers out in full. The headline must come from these answers,
not from the post title.

---

STEP 2 — HEADLINE CONSTRUCTION

Using your emotional archaeology answers from Step 1, write one headline that:

- Speaks directly to ONE of the three pre-insight emotions or self-beliefs you
  identified — choose whichever produces the most devastating recognition
- Contains the word "Narcissist" or a natural variation, embedded as though it
  belongs there
- Is 8–14 words, sentence case
- Reads like a truth she already knows somewhere in her body but has never heard
  said out loud
- Does NOT explain the post — it makes her feel the post already understands her
  before she reads a single word
- Is a recognition, not a slogan — specific to her experience, not the general
  category of her pain

The move the headline makes is completely free — there is no fixed style or
template to follow. The only constraint is that it must come from the emotional
archaeology above and it must make her feel seen.

---

STEP 3 — BLUE WORDS

Pick 2–4 words from the headline that carry the most emotional weight. These will
be rendered in an accent colour on the pin image. Choose the words that, if
highlighted, make the headline even more arresting — the words that carry the
specific wound. Avoid highlighting "a," "the," "is," "of," "and." Prefer the
words that would make her stomach drop.

---

Return this JSON and nothing else:
{{
  "dominant_emotions": ["emotion1", "emotion2", "emotion3"],
  "headline": "Your headline here",
  "blue_words": ["word1", "word2"],
  "emotion": "the single dominant emotion this headline targets"
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


def generate_headline(title: str, body: str, previous_headline: str = "") -> dict:
    prompt = _USER_PROMPT_TEMPLATE.format(
        title=title,
        body=body[:2000],
        previous_headline=previous_headline or "(none yet — this is the first headline of the batch)",
    )

    # Gemini disabled — this account's free tier is hard-capped at limit:0 (needs paid
    # billing to re-enable), so every call was wasting up to 180s in retries before
    # falling back to Groq anyway. Re-enable once Gemini billing is funded.
    # if os.getenv("GEMINI_API_KEY"):
    #     for attempt in range(3):
    #         try:
    #             return _try_gemini(prompt)
    #         except Exception as e:
    #             if "429" in str(e) and attempt < 2:
    #                 wait = 60 * (attempt + 1)
    #                 log.warning(f"Gemini rate limit — retrying in {wait}s")
    #                 time.sleep(wait)
    #             else:
    #                 log.warning(f"Gemini failed — falling back to Groq: {e}")
    #                 break

    # Groq — primary for now
    if os.getenv("GROQ_API_KEY"):
        return _try_groq(prompt)

    raise RuntimeError("No LLM available — set GEMINI_API_KEY or GROQ_API_KEY")
