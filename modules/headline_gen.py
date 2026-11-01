"""
Pinterest headline generation using a two-stage editorial process.

Stage 1: Understand the complete article.
Stage 2: Develop and select article-faithful Pinterest headlines.

The public generate_headline() interface and returned dictionary remain
compatible with main.py and the existing tracker workflow.
"""

import difflib
import json
import logging
import os
import re

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# STAGE 1: ARTICLE UNDERSTANDING
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """
You are an attentive editorial analyst.

Your first job is to understand an article accurately before anyone attempts
to package it into a headline.

Do not write headlines in this stage. Do not turn the article into generic
self-help advice. Do not mistake a memorable sentence for the article's
central argument.

Read the complete article and identify:

- Its actual subject and central argument.
- The reader or audience it is primarily addressing.
- The specific problem, tension, or question the article explores.
- The article's distinct supporting points.
- Observable behaviours, statements, situations, or patterns.
- The consequences or costs described in the article.
- Any surprising interpretation or overlooked connection.
- Practical actions or advice, but only if the article actually gives them.
- The strongest concrete angles that could become useful headlines.
- Claims, numbers, promises, or interpretations that the article does NOT
  support and that a headline must therefore avoid.

Distinguish carefully between:
1. What the article explicitly says.
2. What can reasonably be inferred from its argument.
3. What would be an unsupported exaggeration.

Do not invent facts, signs, examples, statistics, diagnoses, or advice.

Return only valid JSON. Use this structure:

{
  "central_subject": "The article's actual subject",
  "central_argument": "The main point the article is making",
  "target_reader": "The reader most likely to find this useful",
  "reader_problem": "The concrete problem or question the reader brings",
  "main_tension": "The central conflict, contradiction, or uncertainty",
  "key_points": ["Point one", "Point two"],
  "observable_behaviours": ["Specific behaviour or situation"],
  "consequences": ["Specific consequence described in the article"],
  "surprising_insights": ["A supported but less obvious insight"],
  "practical_actions": ["Action actually recommended, if any"],
  "strongest_headline_angles": [
    "A concrete, article-supported angle"
  ],
  "unsupported_claims_to_avoid": [
    "A claim the article does not establish"
  ],
  "usable_numbered_material": [
    "A genuinely countable group of signs, behaviours, reasons, or steps"
  ],
  "article_type": "Explanation, listicle, argument, practical guide, personal essay, or another accurate description"
}

If a field has no applicable material, return an empty string or empty list.
"""


# ---------------------------------------------------------------------------
# STAGE 2: HEADLINE EDITORIAL FRAMEWORK
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an experienced Pinterest editorial strategist.

You package relationship, marriage, family, personal-development, and
narcissistic-abuse articles into compelling Pinterest headlines.

Your task is not to write literary summaries, inspirational slogans,
therapy affirmations, or dramatic excerpts from the article.

Your task is to find the clearest, most compelling article-backed promise
for a reader who is scrolling Pinterest.

A good headline makes the reader understand:
- What person, behaviour, situation, or problem this is about.
- What useful discovery or information the article offers.
- Why the subject matters to someone who recognises the situation.

The headline should create curiosity through a recognisable subject and a
specific promise, not through vagueness.

============================================================
REFERENCE HEADLINE SYSTEM
============================================================

Study the mechanics behind these examples. Do not copy their wording.

1. BEHAVIOURAL WARNING / INVENTORY

Mechanic:
[Number] + [Person or Group] + [Specific Behaviours]

Or:
[Number] + [Specific Things a Person Does] + [Emotional or Practical Context]

Examples:
- "7 Things Parents Should Never Do in Front of Their Children"
- "9 Things Cheaters Always Do on Their Phones"
- "5 Things Selfish Wives Do Every Day"
- "8 Hurtful Things Husbands Say That Wives Never Forget"

The promise is recognition: the reader can identify specific actions,
statements, habits, or patterns.

2. HIDDEN-SIGN INTERPRETATION

Mechanic:
[Number] Signs + [Person, Relationship, or Situation] + [Hidden Reality]

Or:
When [Person] [Behaviour], Watch for These [Number] Signs.

Examples:
- "8 Signs Your Husband Enjoys Hurting You"
- "7 Signs You're in a Parenting Marriage Without Even Realizing It"
- "8 Signs of a Difficult Husband"
- "When a Man Is Embarrassed by His Wife, Watch for These 5 Signs"

The promise is interpretation: the reader suspects something but wants to
understand what the pattern may mean.

3. CONDITIONAL REVELATION

Mechanic:
When/If [Person] [Condition], They [Observable Behaviour].

Examples:
- "When a Man Hates His Wife, He Says These 7 Things"
- "When a Woman Is Cheating on Her Husband, She'll Slip Up in These 6 Ways"
- "When a Man Is Done With the Marriage, He Does These 5 Things Silently"

The promise is discovery: a particular condition or moment reveals
recognisable behaviour.

4. UNCOMFORTABLE TRUTH

Mechanic:
The Dark Side of [Familiar Subject] No One Talks About.

Examples:
- "The Dark Side of Being Married to a 'Good Man' No One Talks About"
- "The Dark Side of Marriage No One Talks About"

The promise is an overlooked cost, contradiction, or uncomfortable reality.

5. HARSH TRUTHS

Mechanic:
[Number] Harsh/Uncomfortable/Brutal Truths About [Specific Subject].

Example:
- "6 Harsh Truths About Marriage"

The promise is direct explanation of difficult realities. Use this when the
article genuinely makes several distinct arguments or observations.

6. UNEXPECTED REVERSAL

Mechanic:
If You Notice/Experience [Specific Evidence], [Unexpected Interpretation].

Examples:
- "If You Notice These 5 Things in Your Husband, You're Emotionally Intelligent"
- "7 Ways Women Hurt Men Without Realizing How Deeply It Cut"

The promise is a fresh interpretation of something familiar. The reversal
must be supported by the article, not manufactured for shock value.

7. RELATIONSHIP CONSEQUENCES / CAUSE AND EFFECT

Mechanic:
[Behaviour or Pattern] + [Specific Consequence].

Or:
[Number] [Behaviours or Patterns] That Lead to [Consequence].

The promise is to explain what a recognisable behaviour produces, damages,
changes, or makes more difficult.

8. DIRECT INSTRUCTION / DISCOVERY

Mechanic:
If [Specific Problem], Do [Specific Action].

Or:
[Specific Situation] — Here's Why It Happens / What It Means.

Example:
- "If Your Wife Doesn't Want Physical Intimacy With You, Do This #1 Thing."

Use direct instruction only when the article actually gives a useful action.
Use discovery/explanation when the article explains a specific situation
without prescribing a solution.

============================================================
CURIOSITY MECHANISMS
============================================================

Use one or more of these mechanisms where they naturally fit:

1. RECOGNITION CURIOSITY
   "I have seen this behaviour. Is this what it means?"

2. INTERPRETATION CURIOSITY
   "I have felt this, but have I understood it correctly?"

3. DISCOVERY CURIOSITY
   "There is something about this pattern I have not noticed."

4. CONSEQUENCE CURIOSITY
   "What does this behaviour lead to, or what is it costing me?"

5. FORBIDDEN-TRUTH CURIOSITY
   "What uncomfortable part of this familiar subject are people reluctant
   to say aloud?"

Do not label curiosity artificially. Use it to decide what makes a headline
interesting and relevant.

============================================================
EDITORIAL JUDGMENT
============================================================

ARTICLE FIDELITY COMES FIRST.

- The article's actual argument determines the headline.
- Never invent a list of signs just because a numbered headline is clickable.
- Never promise advice when the article only explains a problem.
- Never turn an article about one specific behaviour into a sweeping claim
  about all men, all women, all marriages, or all narcissists.
- Do not diagnose a person from one isolated behaviour.
- Avoid unsupported absolutes such as "always", "never", and "every".
- Do not imply the article proves something it merely speculates about.
- Use the article's actual examples and distinctions.

CLARITY AND SPECIFICITY.

- Lead with the person, behaviour, relationship situation, or problem when
  that gives the reader a clearer reason to click.
- A headline must make sense without the reader seeing the article title.
- Prefer concrete actions, statements, situations, and consequences.
- Avoid abstract emotional language when a specific behaviour can be named.
- Avoid vague constructions such as "the thing you need to understand",
  "what nobody tells you", or "the truth you must face" unless the rest of
  the headline identifies the subject clearly.
- Do not use a clever metaphor as a substitute for explaining the subject.
- Do not make a headline sound like a sentence lifted from the middle of
  an essay.

DO NOT WRITE THESE KINDS OF HEADLINES.

- Literary excerpts or poetic observations.
- Inspirational affirmations.
- Therapy-sounding declarations.
- Vague emotional fragments.
- Abstract metaphors that hide the subject.
- Quote-like lines that require the article's context.
- Generic statements about healing, worth, pain, or growth.
- Dramatic claims that the article cannot substantiate.

SUBJECT NAMING.

- "Narcissist" and "narcissistic" are useful when they clarify the subject.
- They are not mandatory.
- Sometimes the behaviour or relationship reality is the stronger entry
  point, and the article can reveal the narcissistic pattern.
- Do not conceal the subject so thoroughly that the headline becomes vague.
- Do not add the word "narcissist" to an article that does not support it.

NUMBERS.

- Numbers are optional, not a default requirement.
- Use a number only when the article contains that many distinct signs,
  behaviours, reasons, lessons, examples, or steps.
- Do not count the same idea several different ways to justify a list.
- Do not force a numbered headline onto an article whose strongest angle
  is a single argument or uncomfortable truth.

VARIETY.

- Do not force candidates into a minimum number of headline families.
- Do not generate four weak families just to appear diverse.
- Generate 6–8 genuinely distinct candidates.
- Use only the families that fit the article.
- Vary the actual editorial angle, not just a few words.
- Avoid candidates that are superficial rewrites of one another.
- Most headlines should be concise, but clarity is more important than
  an arbitrary word count.

SELECTION.

Evaluate each candidate for:
1. Fidelity to the complete article.
2. Immediate comprehension.
3. Specificity and recognisable reader relevance.
4. Curiosity and strength of the information promise.
5. Natural, conversational wording.
6. Difference from the article's previous successful pins.

Choose the headline with the strongest overall editorial promise.
The most dramatic headline is not automatically the best headline.

The selected headline MUST exactly match one item in the candidate list.

Return only valid JSON in this structure:

{
  "candidates": [
    {
      "family": "behavioural_warning",
      "headline": "A complete headline",
      "score": 9
    }
  ],
  "selected_headline": "An exact copy of one candidate",
  "selected_family": "behavioural_warning",
  "blue_words": ["meaningful phrase"],
  "emotion": "The main reader motivation",
  "editorial_angle": "One short sentence explaining the promise"
}
"""


def _parse_response(response_text: str) -> dict:
    """Parse JSON returned by either model provider."""
    raw = (response_text or "").strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    start = raw.find("{")
    end = raw.rfind("}")

    if start >= 0 and end > start:
        raw = raw[start:end + 1]

    parsed = json.loads(raw)

    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object.")

    return parsed


def _similarity(left: str, right: str) -> float:
    """Return a normalized similarity score between two headlines."""
    return difflib.SequenceMatcher(
        None,
        left.casefold().strip(),
        right.casefold().strip(),
    ).ratio()


# ---------------------------------------------------------------------------
# PROVIDER CALLS
# ---------------------------------------------------------------------------

def _try_groq(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = 0.75,
) -> dict:
    """Call Groq and parse its JSON response."""
    from groq import Groq

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    return _parse_response(response.choices[0].message.content)


def _try_gemini(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
    temperature: float = 0.75,
) -> dict:
    """Call Gemini and parse its JSON response."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
        ),
        contents=prompt,
    )

    return _parse_response(response.text)


def _call_model(
    system_prompt: str,
    prompt: str,
    temperature: float = 0.75,
) -> dict:
    """
    Use Gemini first when configured, then fall back to Groq.

    A Gemini rate limit is not allowed to hold up the workflow with repeated
    long waits. If Gemini fails, Groq is tried immediately when available.
    """
    errors = []

    if os.getenv("GEMINI_API_KEY"):
        try:
            return _try_gemini(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
            )
        except Exception as exc:
            errors.append(f"Gemini: {exc}")
            log.warning("Gemini request failed; checking Groq fallback: %s", exc)

    if os.getenv("GROQ_API_KEY"):
        try:
            return _try_groq(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
            )
        except Exception as exc:
            errors.append(f"Groq: {exc}")

    if not errors:
        errors.append("Set GEMINI_API_KEY or GROQ_API_KEY.")

    raise RuntimeError(
        "Model request failed. " + " | ".join(errors)
    )


# ---------------------------------------------------------------------------
# ARTICLE ANALYSIS
# ---------------------------------------------------------------------------

def _build_analysis_prompt(title: str, body: str) -> str:
    """
    Build the first-stage prompt.

    The complete extracted article is passed without the old 12,000-character
    truncation.
    """
    return f"""
ARTICLE TITLE:
{title}

COMPLETE ARTICLE BODY:
{body}

Read the complete article before producing the structured analysis.

Do not generate headlines yet. Identify what the article actually argues,
what it demonstrates, and which specific reader-facing angles it supports.

Return the JSON structure required by your system instructions.
"""


def _analyse_article(title: str, body: str) -> dict:
    """Understand the article before headline generation."""
    if not body or not body.strip():
        raise ValueError("Cannot analyse an empty article body.")

    prompt = _build_analysis_prompt(title, body)

    analysis = _call_model(
        ANALYSIS_SYSTEM_PROMPT,
        prompt,
        temperature=0.2,
    )

    if not analysis.get("central_subject"):
        raise ValueError(
            "Article analysis did not identify a central subject."
        )

    if not analysis.get("central_argument"):
        raise ValueError(
            "Article analysis did not identify the central argument."
        )

    return analysis


# ---------------------------------------------------------------------------
# CANDIDATE VALIDATION AND SELECTION
# ---------------------------------------------------------------------------

def _select_valid_result(
    data: dict,
    recent_headlines: list[str],
) -> dict:
    """
    Clean candidates and ensure the selected headline is:
    - Present in the candidate list.
    - Not already used for this article.
    - Preferably the highest-scoring unused candidate when correction is needed.
    """
    candidates = data.get("candidates") or []

    cleaned = []
    seen = set()

    for item in candidates:
        if not isinstance(item, dict):
            continue

        headline = re.sub(
            r"\s+",
            " ",
            str(item.get("headline", "")),
        ).strip().strip('"“”')

        family = str(item.get("family", "")).strip()

        if not headline:
            continue

        key = headline.casefold()

        if key in seen:
            continue

        seen.add(key)

        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        cleaned.append({
            "family": family,
            "headline": headline,
            "score": score,
        })

    if not cleaned:
        raise ValueError(
            "Headline model returned no usable candidates."
        )

    history = [
        str(headline).strip()
        for headline in recent_headlines
        if headline and str(headline).strip()
    ]

    def is_recent(candidate: str) -> bool:
        return any(
            _similarity(candidate, old) >= 0.82
            for old in history
        )

    selected = re.sub(
        r"\s+",
        " ",
        str(data.get("selected_headline", "")),
    ).strip().strip('"“”')

    selected_item = next(
        (
            candidate
            for candidate in cleaned
            if candidate["headline"].casefold() == selected.casefold()
        ),
        None,
    )

    if selected_item is None or is_recent(selected_item["headline"]):
        available = [
            candidate
            for candidate in cleaned
            if not is_recent(candidate["headline"])
        ]

        if not available:
            raise ValueError(
                "All generated headline candidates duplicate recent pins "
                "for this article."
            )

        selected_item = max(
            available,
            key=lambda candidate: candidate["score"],
        )

    # Keep accent phrases relevant to the actual selected headline.
    blue_words = data.get("blue_words", [])

    if not isinstance(blue_words, list):
        blue_words = []

    selected_lower = selected_item["headline"].casefold()

    blue_words = [
        str(word).strip()
        for word in blue_words
        if str(word).strip()
        and str(word).strip().casefold() in selected_lower
    ][:4]

    return {
        "headline": selected_item["headline"],
        "blue_words": blue_words,
        "emotion": str(data.get("emotion", "")).strip(),
        "family": (
            selected_item["family"]
            or str(data.get("selected_family", "")).strip()
        ),
        "editorial_angle": str(
            data.get("editorial_angle", "")
        ).strip(),
        "candidates": cleaned,
    }


# ---------------------------------------------------------------------------
# HEADLINE GENERATION
# ---------------------------------------------------------------------------

def _build_headline_prompt(
    title: str,
    body: str,
    analysis: dict,
    recent_headlines: list[str],
) -> str:
    """Build the second-stage editorial prompt."""
    history_text = (
        "\n".join(f"- {headline}" for headline in recent_headlines[-30:])
        or "(No previous successful headlines recorded.)"
    )

    analysis_text = json.dumps(
        analysis,
        ensure_ascii=False,
        indent=2,
    )

    return f"""
ARTICLE TITLE:
{title}

COMPLETE ARTICLE BODY:
{body}

STRUCTURED ARTICLE ANALYSIS:
{analysis_text}

RECENT SUCCESSFUL HEADLINES ALREADY USED FOR THIS ARTICLE:
{history_text}

EDITORIAL TASK

1. Use the complete article and structured analysis together.
2. Identify the strongest specific reader-facing promise supported by the
   article.
3. Decide which reference headline families genuinely fit the article.
4. Generate 6–8 distinct candidate headlines. Do not force a minimum number
   of headline families.
5. Make the candidates meaningfully different in editorial angle, not merely
   superficial rewrites.
6. Use the article's strongest concrete behaviours, relationship situations,
   discoveries, consequences, or uncomfortable arguments.
7. Use numbers only when the article contains a genuinely countable set.
8. Avoid literary excerpts, poetic observations, therapy affirmations,
   vague emotional fragments, abstract metaphors, and unsupported promises.
9. Do not repeat or closely paraphrase the recent successful headlines.
10. Score each candidate from 1 to 10, considering fidelity, clarity,
    specificity, curiosity, and reader relevance together.
11. Select the strongest overall candidate. The selected headline must be
    copied exactly from the candidate list.
12. Select 2–4 meaningful words or short phrases from the selected headline
    for image accent styling. They must actually appear in that headline.

The complete article is the authority. If the structured analysis appears
to overstate something that the article does not support, follow the article.

Return the JSON structure required by your system instructions.
"""


def generate_headline(
    title: str,
    body: str,
    previous_headline: str = "",
    recent_headlines: list[str] | None = None,
) -> dict:
    """
    Generate a Pinterest headline using article analysis followed by
    candidate generation and editorial selection.

    The returned keys remain compatible with main.py:
        headline
        blue_words
        emotion
        family
        editorial_angle
        candidates
    """
    if not title or not title.strip():
        raise ValueError("Article title is required.")

    if not body or not body.strip():
        raise ValueError("Article body is required.")

    history = list(recent_headlines or [])

    if previous_headline and previous_headline not in history:
        history.append(previous_headline)

    log.info(
        "  Editorial : analysing complete article (%s characters)",
        len(body),
    )

    # Stage 1: Understand the article.
    analysis = _analyse_article(title, body)

    log.info(
        "  Article   : %s",
        str(analysis.get("central_subject", ""))[:120],
    )

    # Stage 2: Develop and select article-faithful headlines.
    prompt = _build_headline_prompt(
        title=title,
        body=body,
        analysis=analysis,
        recent_headlines=history,
    )

    result = _call_model(
        SYSTEM_PROMPT,
        prompt,
        temperature=0.75,
    )

    selected = _select_valid_result(result, history)

    log.info(
        "  Selected  : %s",
        selected["headline"],
    )

    return selected
