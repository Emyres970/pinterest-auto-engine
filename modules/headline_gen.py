"""
Pinterest headline generation using a three-stage editorial system.

Stage 1: Understand the complete article.
Stage 2: Package it using the researched headline formulas.
Stage 3: Independently evaluate candidates against the researched style.

The public generate_headline() interface and returned dictionary remain
compatible with main.py and the existing image-generation workflow.
"""

import difflib
import json
import logging
import os
import re
import string

log = logging.getLogger(__name__)

NUMBER_WORDS = (
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve",
)

NUMBER_PATTERN = re.compile(
    r"^\s*(?:\d{1,2}|"
    + "|".join(NUMBER_WORDS)
    + r")\b",
    re.IGNORECASE,
)


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
- Claims, numbers, promises, or interpretations the article does NOT
  support and that a headline must therefore avoid.
- Distinct groups of material that could legitimately support a numbered
  headline.

Distinguish carefully between:
1. What the article explicitly says.
2. What can reasonably be inferred from its argument.
3. What would be an unsupported exaggeration.

Do not invent facts, signs, examples, statistics, diagnoses, or advice.

A numbered headline is useful only when the article contains genuinely
distinct material that can support the number. Identify that material
without inflating the count.

Return only valid JSON using this structure:

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
    "A genuinely distinct, countable group of signs, behaviours, reasons, or steps"
  ],
  "article_type": "Explanation, listicle, argument, practical guide, personal essay, or another accurate description"
}

If a field has no applicable material, return an empty string or empty list.
"""


# ---------------------------------------------------------------------------
# STAGE 2: FORMULA-BASED HEADLINE GENERATION
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are an experienced Pinterest editorial strategist.

You are not being asked to invent a new headline style. You are being taught
to adapt a specific blogger's researched headline instincts to new articles.

Your job is to package each article using the eight headline families below.
The article determines the subject and the promise. The formula determines
how that promise is packaged.

The examples are structural references. Learn their mechanics; do not copy
their wording.

============================================================
THE EIGHT RESEARCHED HEADLINE FAMILIES
============================================================

1. BEHAVIOURAL WARNING / INVENTORY

Core formulas:

[Number] Things [Person/Group] Do [Situation or Context]

[Number] Things [Person/Group] Say That [Consequence]

[Number] Ways [Person/Group] [Specific Behaviour]

Research examples:
- 7 Things Parents Should Never Do in Front of Their Children
- 9 Things Cheaters Always Do on Their Phones
- 5 Things Selfish Wives Do Every Day
- 8 Hurtful Things Husbands Say That Wives Never Forget

Narcissist adaptation anchors:
- 7 Things Narcissists Do When They Realize You're Pulling Away
- 8 Things Narcissists Say When They Want You to Feel Guilty
- 6 Things Narcissistic Husbands Do That Slowly Destroy Their Wives' Confidence

Use this family when the article contains recognisable actions, statements,
habits, tactics, or repeated patterns.

Do not turn an abstract argument into a fake list of behaviours.

2. HIDDEN-SIGN INTERPRETATION

Core formulas:

[Number] Signs [Relationship/Person/Situation] [Hidden Reality]

[Number] Signs Your [Person] [Unexpected Behaviour or Condition]

When [Person] [Condition], Watch for These [Number] Signs.

Research examples:
- 8 Signs Your Husband Enjoys Hurting You
- 7 Signs You're in a Parenting Marriage Without Even Realizing It
- 8 Signs of a Difficult Husband
- When a Man Is Embarrassed by His Wife, Watch for These 5 Signs

Narcissist adaptation anchors:
- 7 Signs Your Husband Resents You for Having a Mind of Your Own
- 8 Signs a Narcissist Is Punishing You for Setting Boundaries
- When a Narcissist Feels Threatened by You, Watch for These 6 Signs

Use this family when the article helps readers recognise or interpret
evidence of an underlying relationship reality.

A sign must be supported by the article. Do not diagnose from one isolated
behaviour.

3. CONDITIONAL REVELATION

Core formula:

When [Person] [Condition], They [Observable Behaviour] These [Number] Ways.

Also:

When [Person] [Condition], They Say These [Number] Things.

Research examples:
- When a Man Hates His Wife, He Says These 7 Things
- When a Woman Is Cheating on Her Husband, She'll Slip Up in These 6 Ways
- When a Man Is Done With the Marriage, He Does These 5 Things Silently

Narcissist adaptation anchors:
- When a Narcissist Knows You're Onto Them, They Start Doing These 6 Things
- When a Narcissist Is Losing Control of You, They Say These 7 Things
- When a Narcissist Wants You Back, They Often Use These 5 Tactics

Use this family when the article explores what someone does in a specific
condition, emotional state, or relationship situation.

The condition and behaviour must both be grounded in the article.

4. UNCOMFORTABLE TRUTH

Core formula:

The Dark Side of [Familiar Subject] No One Talks About.

Other valid forms:

The Hidden Cost of [Familiar Situation].

What [Accepted or Familiar Idea] Leaves Out About [Subject].

Research examples:
- The Dark Side of Being Married to a "Good Man" No One Talks About
- The Dark Side of Marriage No One Talks About

Narcissist adaptation anchors:
- The Dark Side of Being Married to a Charming Narcissist No One Talks About
- The Dark Side of Having a Narcissistic Mother No One Talks About

Use this family for deeper commentary, contradictions, overlooked costs,
and articles challenging a familiar assumption.

Do not use "no one talks about" as decoration. There must be a genuinely
overlooked or uncomfortable point.

5. HARSH TRUTHS

Core formula:

[Number] Harsh/Uncomfortable/Brutal Truths About [Specific Subject].

Research example:
- 6 Harsh Truths About Marriage

Narcissist adaptation anchors:
- 6 Harsh Truths About Loving a Narcissist
- 7 Harsh Truths About Loving Someone Who Only Wants to Be Adored

Use this family when the article makes several distinct, challenging
observations about a subject.

Do not use "truths" to disguise a list of unrelated tips.

6. UNEXPECTED REVERSAL

Core formulas:

If You Notice These [Number] Things, It Means [Supported Interpretation].

If You [Recognise/Experience] [Specific Evidence], [Unexpected Meaning].

[Number] Ways [Person] [Behaviour] Without Realising [Consequence].

Research examples:
- If You Notice These 5 Things in Your Husband, You're Emotionally Intelligent
- 7 Ways Women Hurt Men Without Realizing How Deeply It Cut

Narcissist adaptation anchors:
- If You Notice These 5 Patterns in a Narcissist, You're Starting to See Through Them
- If You No Longer Feel the Need to Explain Yourself to a Narcissist, You've Understood Something Important

Use this family when the article genuinely changes how a familiar
experience or behaviour should be interpreted.

The reversal must be supported, not manufactured for shock value.

7. RELATIONSHIP CONSEQUENCES / CAUSE AND EFFECT

Core formulas:

[Number] [Behaviours/Patterns] That Lead to [Specific Consequence].

[Number] Things [Person] Does That Slowly [Specific Consequence].

How [Specific Behaviour] Leads to [Specific Relationship Consequence].

Narcissist adaptation anchors:
- 6 Things Narcissists Do That Slowly Turn Love Into Submission
- 6 Things Narcissistic Husbands Do That Slowly Destroy Their Wives' Confidence

Use this family when the article explains what a recognisable behaviour
produces, damages, changes, or makes more difficult.

The consequence must be present in the article.

8. DIRECT INSTRUCTION / DISCOVERY

Core formulas:

If [Specific Problem], Do [Specific Action].

If [Person] [Specific Behaviour], Stop Doing This [Specific Thing].

[Specific Situation] — Here's Why It Happens / What It Means.

Narcissist adaptation anchors:
- If a Narcissist Keeps Rewriting Your Arguments, Stop Doing This One Thing
- If a Narcissist Uses Silence to Punish You, Do This Instead
- If a Narcissist Keeps Blaming You for Their Behaviour, Try This One Response

Use direct instruction only when the article actually provides a useful
action. Use discovery/explanation when it explains a specific situation
without prescribing a solution.

============================================================
HOW TO ADAPT THE FORMULAS
============================================================

Do not simply insert "narcissist" into a template.

For every article:

1. Identify its strongest reader-facing subject or situation.
2. Identify the most concrete material the article actually contains.
3. Decide which formula family makes that material most clickable and clear.
4. Identify the curiosity mechanism that naturally fits.
5. Build a headline around the article's actual promise.
6. Change the angle when generating another headline for an article that
   has already been used.

For example, an article about narcissists wanting worship rather than love
can be packaged through different supported angles:

- Their observable behaviours when they want admiration.
- Signs they value admiration more than intimacy.
- What they do when admiration disappears.
- The uncomfortable reality of loving someone who needs worship.
- How the need for admiration turns loyalty into submission.

These are different editorial entry points, not five cosmetic rewrites.

============================================================
NUMBERED HEADLINES: THE DEFAULT
============================================================

Approximately 90% of generated candidates should be numbered headlines.

Generate TEN candidates when the article supports sufficient countable
material. Aim for at least NINE numbered candidates and no more than ONE
non-numbered candidate.

Numbered structures should be your normal instinct:

- 5 Things...
- 7 Signs...
- 8 Ways...
- 6 Harsh Truths...
- When [condition], They Do These 5 Things...
- If [situation], Watch for These 7 Signs...

Use the number that the article can honestly support. Do not invent
additional points or split one idea into artificial sub-points.

If the article does not contain enough countable material, do not fabricate
a numbered list. In that case, use the strongest truthful non-numbered
formula.

When choosing the final headline, prefer a strong numbered candidate.
Choose a non-numbered candidate only when no numbered candidate passes
the editorial standard or when the article's strongest promise is genuinely
a single uncomfortable truth or explanation.

The 90% target is a strong editorial preference, not permission to mislead.

============================================================
CURIOSITY MECHANISMS
============================================================

Use these to decide why a reader would click:

1. RECOGNITION: "I have seen this behaviour. Is this what it means?"
2. INTERPRETATION: "I have experienced this, but have I understood it?"
3. DISCOVERY: "There is something about this pattern I have not noticed."
4. CONSEQUENCE: "What does this behaviour lead to or cost me?"
5. FORBIDDEN TRUTH: "What uncomfortable part of this familiar subject is
   people reluctant to say aloud?"

============================================================
STYLE RULES
============================================================

ARTICLE FIDELITY COMES FIRST.

- The complete article is the authority.
- Never invent signs, behaviours, advice, facts, or numbers.
- Never promise advice when the article only explains a problem.
- Never turn one specific behaviour into a sweeping claim about all men,
  all women, all marriages, or all narcissists.
- Do not diagnose a person from one isolated behaviour.
- Avoid unsupported absolutes such as "always", "never", and "every".

WRITE PINTEREST HEADLINES, NOT ESSAY EXCERPTS.

Reject the instinct to turn a memorable article sentence into a headline.

Do not write:
- Literary excerpts or poetic observations.
- Inspirational affirmations.
- Therapy-sounding declarations.
- Vague emotional fragments.
- Abstract metaphors that hide the subject.
- Quote-like lines that require the article's context.
- Generic statements about healing, worth, pain, or growth.
- Dramatic sentence fragments that sound like social-media quotes.

Avoid constructions such as:
- "It doesn't just hurt you; it steals..."
- "You were never broken..."
- "The truth is that..."
- "You don't need to understand..."
- "It was never about X; it was always about Y..."

A reader should understand the subject and the promised discovery without
needing to read the article first.

SUBJECT NAMING.

"Narcissist" and "narcissistic" are useful when they clarify the subject.
They are not mandatory.

Sometimes the behaviour or relationship reality is the stronger entry
point, and the article can reveal the narcissistic context.

Do not conceal the subject so thoroughly that the headline becomes vague.
Do not add "narcissist" to an article that does not support it.

VARIETY AND HISTORY.

- Generate ten meaningfully different candidates.
- Do not force all eight families into one article.
- Vary the angle, not just the wording.
- Do not repeat the article title as a headline.
- Do not repeat any headline in the supplied article history.
- Do not produce superficial rewrites of a previous headline.
- Reuse a formula when it fits; create a fresh angle and fresh wording.

Return only valid JSON:

{
  "candidates": [
    {
      "family": "behavioural_warning",
      "headline": "A complete headline",
      "score": 9,
      "angle": "The specific article angle"
    }
  ],
  "selected_headline": "An exact copy of one candidate",
  "selected_family": "behavioural_warning",
  "blue_words": ["meaningful phrase"],
  "emotion": "The main reader motivation",
  "editorial_angle": "One short sentence explaining the promise"
}
"""


# ---------------------------------------------------------------------------
# STAGE 3: INDEPENDENT EDITORIAL EVALUATION
# ---------------------------------------------------------------------------

EVALUATION_SYSTEM_PROMPT = """
You are an independent Pinterest headline editor.

You are evaluating headlines against a specific researched blogger style.
You are NOT being asked to invent a new style or rewrite the candidates.

The target style uses these eight families:
1. Behavioural warning / inventory.
2. Hidden-sign interpretation.
3. Conditional revelation.
4. Uncomfortable truth.
5. Harsh truths.
6. Unexpected reversal.
7. Relationship consequences / cause and effect.
8. Direct instruction / discovery.

Approximately 90% of headlines should be numbered when the article supports
genuinely countable material. Prefer a strong numbered candidate.

For every candidate, evaluate:

1. ARTICLE FIDELITY
   Does the complete article genuinely support the promise?

2. FORMULA FIT
   Does it follow one of the researched headline structures?

3. SUBJECT CLARITY
   Can a Pinterest reader immediately understand the person, behaviour,
   situation, or problem?

4. SPECIFICITY
   Does it promise identifiable signs, behaviours, truths, consequences,
   discoveries, or actions?

5. CURIOSITY
   Does it create a useful information gap?

6. PINTEREST READABILITY
   Does it sound like a clear, clickable headline rather than a sentence
   lifted from an essay?

7. ORIGINALITY
   Is it different from the post's previous headlines?

Reject:
- Quote-like article excerpts.
- Poetic or abstract slogans.
- Therapy affirmations.
- Vague emotional declarations.
- Unsupported dramatic claims.
- Invented numbered lists.
- Candidates that merely rearrange words from a previous headline.
- Candidates that do not fit any of the eight families.

The following is a negative anchor:
"Narcissistic Abuse Doesn't Just Hurt You; It Steals Your Right To Trust
Your Own Experience."

It sounds like a dramatic essay sentence, not the researched Pinterest
headline style. Reject this type of construction.

A positive structural anchor is:
"Understand The System: Why a Narcissist Can't Tolerate These 7 Aspects
of You."

It has a recognisable subject, a concrete promise, and a numbered structure.
The wording can be improved, but the packaging direction is closer to the
target style.

Do not rewrite candidates. Approve or reject the exact candidate wording.

Return only valid JSON:

{
  "evaluations": [
    {
      "headline": "Exact candidate wording",
      "approved": true,
      "score": 9,
      "reason": "Brief explanation"
    }
  ]
}
"""


# ---------------------------------------------------------------------------
# SHARED HELPERS
# ---------------------------------------------------------------------------

def _parse_response(response_text: str) -> dict:
    """Parse JSON returned by either model provider."""
    raw = (response_text or "").strip()

    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    raw = re.sub(r"\s*```$", "", raw)

    start = raw.find("{")
    end = raw.rfind("}")

    if start >= 0 and end > start:
        raw = raw[start:end + 1]

    parsed = json.loads(raw)

    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object.")

    return parsed


def _normalise_headline(headline: str) -> str:
    """Normalize punctuation, spacing and case for exact-wording checks."""
    value = (headline or "").casefold()
    value = value.translate(str.maketrans("", "", string.punctuation + "“”‘’—–"))
    return " ".join(value.split())


def _similarity(left: str, right: str) -> float:
    """Return normalized similarity between two headlines."""
    return difflib.SequenceMatcher(
        None,
        _normalise_headline(left),
        _normalise_headline(right),
    ).ratio()


def _is_numbered_headline(headline: str) -> bool:
    return bool(NUMBER_PATTERN.match((headline or "").strip()))


def _is_quote_like_or_slogan(headline: str) -> bool:
    """
    Reject a small set of obvious essay-excerpt/slogan constructions.

    This is intentionally conservative. The independent evaluator handles
    broader editorial judgment.
    """
    text = " ".join((headline or "").casefold().split())

    rejected_patterns = (
        r"\bdoesn't just\b",
        r"\bdoes not just\b",
        r"\bwasn't just\b",
        r"\bwas not just\b",
        r"\byou were never broken\b",
        r"\byou are not broken\b",
        r"\bit was never about\b",
        r"\bit's not about\b",
        r"\bit is not about\b",
        r"\bthe truth is\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in rejected_patterns
    )


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

    Both providers receive the same editorial instructions.
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
            log.warning(
                "Gemini request failed; checking Groq fallback: %s",
                exc,
            )

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

    raise RuntimeError("Model request failed. " + " | ".join(errors))


# ---------------------------------------------------------------------------
# ARTICLE ANALYSIS
# ---------------------------------------------------------------------------

def _build_analysis_prompt(title: str, body: str) -> str:
    """Pass the complete article to the analysis model without truncation."""
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

    analysis = _call_model(
        ANALYSIS_SYSTEM_PROMPT,
        _build_analysis_prompt(title, body),
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
# PROMPT BUILDERS
# ---------------------------------------------------------------------------

def _build_headline_prompt(
    title: str,
    body: str,
    analysis: dict,
    recent_headlines: list[str],
) -> str:
    """Build the formula-based candidate-generation prompt."""
    history_text = (
        "\n".join(f"- {headline}" for headline in recent_headlines)
        or "(No previous headlines recorded for this article.)"
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

COMPLETE PREVIOUS HEADLINE HISTORY FOR THIS ARTICLE:
{history_text}

GENERATION TASK

1. Understand the article's strongest concrete reader-facing promise.
2. Choose the most appropriate families from the eight researched families.
3. Generate TEN distinct candidates.
4. Aim for NINE numbered candidates and ONE non-numbered candidate,
   provided the article contains enough genuinely countable material.
5. Do not invent signs, behaviours, steps, reasons, or consequences to
   satisfy the numbered target.
6. Use different article angles, not superficial wording changes.
7. Use the narcissist adaptation anchors and research examples as
   structural guidance, not wording to copy.
8. Do not repeat or closely paraphrase any headline in the history above.
9. Reject quote-like, abstract, poetic, or slogan-like constructions.
10. Score candidates from 1 to 10 for fidelity, formula fit, clarity,
    specificity, curiosity, and Pinterest readability.
11. Select a strong numbered candidate when one genuinely fits.
12. Select a non-numbered candidate only when it is the stronger truthful
    promise or the article does not support a numbered list.
13. Select 2–4 accent phrases that actually appear in the selected headline.

The complete article is the authority. If the structured analysis overstates
something the article does not support, follow the article.

Return the JSON structure required by your system instructions.
"""


def _build_evaluation_prompt(
    title: str,
    body: str,
    analysis: dict,
    candidates: list[dict],
    recent_headlines: list[str],
) -> str:
    """Build the independent evaluation prompt."""
    return f"""
ARTICLE TITLE:
{title}

COMPLETE ARTICLE BODY:
{body}

ARTICLE ANALYSIS:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

CANDIDATES TO EVALUATE:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

PREVIOUS HEADLINES FOR THIS ARTICLE:
{json.dumps(recent_headlines, ensure_ascii=False, indent=2)}

Evaluate every candidate independently against the researched headline
families and the complete article.

Do not rewrite any candidate. Return an evaluation for every candidate.
A candidate must be rejected if it is unsupported, vague, quote-like,
abstract, slogan-like, or a superficial repeat of the article history.

Prefer strong numbered candidates when the article supports them.

Return only the JSON structure required by your system instructions.
"""


# ---------------------------------------------------------------------------
# CANDIDATE CLEANING AND EDITORIAL SELECTION
# ---------------------------------------------------------------------------

def _clean_candidates(data: dict) -> list[dict]:
    """Normalize candidate objects and remove duplicate wording."""
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

        if not headline:
            continue

        key = _normalise_headline(headline)

        if not key or key in seen:
            continue

        seen.add(key)

        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        cleaned.append({
            "family": str(item.get("family", "")).strip(),
            "headline": headline,
            "score": score,
            "angle": str(item.get("angle", "")).strip(),
        })

    return cleaned


def _evaluate_candidates(
    title: str,
    body: str,
    analysis: dict,
    candidates: list[dict],
    recent_headlines: list[str],
) -> list[dict]:
    """Run the independent editorial evaluation stage."""
    prompt = _build_evaluation_prompt(
        title,
        body,
        analysis,
        candidates,
        recent_headlines,
    )

    result = _call_model(
        EVALUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.1,
    )

    evaluations = result.get("evaluations")

    if not isinstance(evaluations, list):
        raise ValueError(
            "Editorial evaluator returned no valid evaluations."
        )

    return evaluations


def _select_valid_result(
    data: dict,
    recent_headlines: list[str],
    approved_headlines: list[str] | None = None,
) -> dict:
    """
    Select an approved, article-faithful and unused headline.

    The evaluator cannot introduce new wording. The selected headline must
    be one of the original generated candidates.
    """
    candidates = _clean_candidates(data)

    if not candidates:
        raise ValueError(
            "Headline model returned no usable candidates."
        )

    history = [
        str(headline).strip()
        for headline in recent_headlines
        if headline and str(headline).strip()
    ]

    history_keys = {
        _normalise_headline(headline)
        for headline in history
    }

    if approved_headlines is None:
        # Kept for compatibility with direct callers and unit tests.
        approved_keys = {
            _normalise_headline(candidate["headline"])
            for candidate in candidates
            if not _is_quote_like_or_slogan(candidate["headline"])
        }
    else:
        approved_keys = {
            _normalise_headline(headline)
            for headline in approved_headlines
        }

    available = []

    for candidate in candidates:
        headline = candidate["headline"]
        key = _normalise_headline(headline)

        if key in history_keys:
            continue

        if key not in approved_keys:
            continue

        if _is_quote_like_or_slogan(headline):
            continue

        # Avoid near-identical rewordings while allowing a formula to recur
        # with a genuinely different angle and wording.
        if any(
            _similarity(headline, old) >= 0.94
            for old in history
        ):
            continue

        available.append(candidate)

    if not available:
        raise ValueError(
            "No editorially approved, unused headline remains for this "
            "article. The system will not reuse a previous headline or "
            "select a rejected candidate."
        )

    # Numbered headlines are the default whenever an approved one exists.
    numbered = [
        candidate for candidate in available
        if _is_numbered_headline(candidate["headline"])
    ]

    selection_pool = numbered if numbered else available

    # Prefer the evaluator's score if supplied; otherwise retain generation
    # score. Candidate wording remains unchanged.
    selected = max(
        selection_pool,
        key=lambda candidate: candidate["score"],
    )

    blue_words = data.get("blue_words", [])

    if not isinstance(blue_words, list):
        blue_words = []

    selected_lower = selected["headline"].casefold()

    blue_words = [
        str(word).strip()
        for word in blue_words
        if str(word).strip()
        and str(word).strip().casefold() in selected_lower
    ][:4]

    return {
        "headline": selected["headline"],
        "blue_words": blue_words,
        "emotion": str(data.get("emotion", "")).strip(),
        "family": (
            selected["family"]
            or str(data.get("selected_family", "")).strip()
        ),
        "editorial_angle": (
            selected["angle"]
            or str(data.get("editorial_angle", "")).strip()
        ),
        "candidates": candidates,
    }


def _approved_candidate_headlines(
    candidates: list[dict],
    evaluations: list[dict],
) -> list[str]:
    """Match evaluator approvals to exact generated candidate wording."""
    candidate_by_key = {
        _normalise_headline(item["headline"]): item["headline"]
        for item in candidates
    }

    approved = []

    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue

        headline = str(evaluation.get("headline", "")).strip()
        key = _normalise_headline(headline)

        if key not in candidate_by_key:
            continue

        if evaluation.get("approved") is not True:
            continue

        try:
            score = float(evaluation.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        if score < 7:
            continue

        if _is_quote_like_or_slogan(headline):
            continue

        approved.append(candidate_by_key[key])

        # Keep the evaluator's score attached to the original candidate.
        for candidate in candidates:
            if _normalise_headline(candidate["headline"]) == key:
                candidate["score"] = score
                break

    return approved


# ---------------------------------------------------------------------------
# PUBLIC GENERATION FUNCTION
# ---------------------------------------------------------------------------

def generate_headline(
    title: str,
    body: str,
    previous_headline: str = "",
    recent_headlines: list[str] | None = None,
) -> dict:
    """
    Generate a Pinterest headline through analysis, generation and review.

    Returned keys remain compatible with main.py:
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

    # Remove duplicate history entries without losing newest-first ordering.
    deduplicated_history = []
    seen_history = set()

    for headline in history:
        if not headline:
            continue

        key = _normalise_headline(str(headline))

        if key and key not in seen_history:
            seen_history.add(key)
            deduplicated_history.append(str(headline).strip())

    history = deduplicated_history

    log.info(
        "  Editorial : analysing complete article (%s characters)",
        len(body),
    )

    # Stage 1: understand the article.
    analysis = _analyse_article(title, body)

    log.info(
        "  Article   : %s",
        str(analysis.get("central_subject", ""))[:120],
    )

    # Stage 2: generate candidates using the researched formulas.
    generation_prompt = _build_headline_prompt(
        title=title,
        body=body,
        analysis=analysis,
        recent_headlines=history,
    )

    generated = _call_model(
        SYSTEM_PROMPT,
        generation_prompt,
        temperature=0.8,
    )

    candidates = _clean_candidates(generated)

    if not candidates:
        raise ValueError("Headline generation returned no usable candidates.")

    log.info(
        "  Generated : %s candidates; %s numbered",
        len(candidates),
        sum(
            1 for item in candidates
            if _is_numbered_headline(item["headline"])
        ),
    )

    # Stage 3: independent editorial evaluation.
    evaluations = _evaluate_candidates(
        title=title,
        body=body,
        analysis=analysis,
        candidates=candidates,
        recent_headlines=history,
    )

    approved = _approved_candidate_headlines(
        candidates,
        evaluations,
    )
        generated["candidates"] = candidates

    log.info(
        "  Evaluated : %s approved out of %s",
        len(approved),
        len(candidates),
    )

    selected = _select_valid_result(
        generated,
        history,
        approved_headlines=approved,
    )

    log.info("  Selected  : %s", selected["headline"])

    return selected
