import os
import json
import re
from google import genai
from google.genai import types

SYSTEM_PROMPT = """There's a particular pattern a blogger in my niche uses for her Pinterest Pin images.
Like the way she rephrases the headlines or texts she writes on the image that works well for her.
She averages over 10 million impressions on Pinterest.

For example, a post titled: "HOW TO BE A WOMAN A MAN IS AFRAID TO LOSE"
became this pin headline: "Men Are Always Afraid To Lose This Kind Of Woman"

The transformation pattern:
- Shift from instructional/research framing to an emotional revelation or identity statement
- Make the reader the subject being described or addressed
- Create identity-based curiosity — the reader wonders "Is this me?"
- Replace the blog's promise with a gut-punch emotional truth
- Embed a broad root keyword naturally for SEO
- Keep it under 12 words
- Write with the emotional rawness and mic-drop rhythm of Tim Denning

You always respond with valid JSON only. No markdown. No explanation. Just JSON."""

USER_PROMPT_TEMPLATE = """For a blog post titled: "{title}"

Here is the post content for context:
{body}

Think about three dominant emotions the intended audience feels BEFORE reading this post.
Generate the single most powerful Pinterest pin headline that:
1. Uses the emotional transformation pattern (like "Men Are Always Afraid To Lose This Kind Of Woman")
2. Is gut-punching, almost poetic, mic-drop and curiosity-infused like Tim Denning
3. Embeds a broad root SEO keyword naturally in the headline itself
4. Is 12 words maximum
5. Is appropriate for the dominant emotion

Also pick 2-4 words from the headline that should be highlighted in a contrasting color for visual emphasis — the most emotionally charged or keyword-rich words.

Respond with ONLY this JSON:
{{
  "headline": "the full pin headline here",
  "blue_words": ["word or phrase 1", "word or phrase 2"],
  "emotion": "the single dominant emotion being targeted"
}}"""


def generate_headline(title: str, body: str) -> dict:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        body=body[:2500]
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.9,
        ),
        contents=prompt,
    )

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)
