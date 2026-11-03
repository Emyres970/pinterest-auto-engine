"""
Pinterest headline generation: research-led, three-stage editorial system.

Stage 1: Read and understand the complete article.
Stage 2: Generate distinct Pinterest headline angles from the evidence packet.
Stage 3: Independently score and approve the exact candidate wording.

The public generate_headline() interface and return keys remain compatible
with main.py.
"""

import difflib
import json
import logging
import os
import re
import string

log = logging.getLogger(__name__)

GROQ_MODEL = "openai/gpt-oss-120b"

NUMBER_WORDS = (
    "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "eleven", "twelve",
)

NUMBER_PATTERN = re.compile(
    r"^\s*(?:\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\b",
    re.IGNORECASE,
)

# These are research anchors, not templates to copy mechanically.
RESEARCH_ANCHORS = [
    "Men Are Always Afraid To Lose This Kind Of Woman",
    "7 Things Parents Should Never Do In Front Of Their Children",
    "9 Things Cheaters Always Do On Their Phones",
    "5 Things Selfish Wives Do Every Day",
    "8 Hurtful Things Husbands Say That Wives Never Forget",
    "8 Signs Your Husband Enjoys Hurting You",
    "7 Signs You're In A Parenting Marriage Without Even Realizing It",
    "The Dark Side Of Marriage No One Talks About",
    "6 Harsh Truths About Marriage",
    "When A Man Hates His Wife, He Says These 7 Things",
    "When A Woman Is Cheating On Her Husband, She'll Slip Up In These 6 Ways",
    "When A Man Is Done With The Marriage, He Does These 5 Things Silently",
    "If You Notice These 5 Things In Your Husband, You're Emotionally Intelligent",
    "7 Ways Women Hurt Men Without Realizing How Deeply It Cut",
    "How To Silence A Narcissist With Just One Text",
    "Narcissistic Husbands Share One Pattern, And It's Terrifying",
    "If A Narcissist Is Cheating On You, These 14 Lines Will Always Show Up",
]

FAMILIES = """
1. BEHAVIOURAL WARNING / INVENTORY
   "[Number] Things [Person] Do [Situation/Context]"
   "[Number] Things [Person] Say That [Consequence]"
   Use for recognisable actions, statements, habits, tactics and patterns.

2. HIDDEN-SIGN INTERPRETATION
   "[Number] Signs [Person/Relationship] [Hidden Reality]"
   "When [Person] [Condition], Watch For These [Number] Signs."
   Use when the article helps readers recognise evidence of an underlying
   relationship reality. Do not diagnose from one isolated behaviour.

3. CONDITIONAL REVELATION
   "When [Person] [Condition], They [Observable Behaviour] These [Number] Ways."
   "When [Person] [Condition], They Say These [Number] Things."
   Use when a specific condition is linked to observable behaviour.

4. UNCOMFORTABLE TRUTH
   "The Dark Side Of [Familiar Subject] No One Talks About."
   "The Hidden Cost Of [Familiar Situation]."
   "What [Accepted Idea] Leaves Out About [Subject]."
   Use for a genuine overlooked cost, contradiction or uncomfortable reality.

5. HARSH TRUTHS
   "[Number] Harsh/Uncomfortable Truths About [Specific Subject]."
   Use only when the article contains several distinct, challenging insights.

6. UNEXPECTED REVERSAL
   "If You Notice These [Number] Things, It Means [Supported Interpretation]."
   "[Number] Ways [Person] [Behaviour] Without Realising [Consequence]."
   Use when the article changes how a familiar experience should be understood.

7. RELATIONSHIP CONSEQUENCES / CAUSE AND EFFECT
   "[Number] [Behaviours/Patterns] That Lead To [Specific Consequence]."
   "[Number] Things [Person] Does That Slowly [Specific Consequence]."
   Use when the article explains what a behaviour produces, damages or changes.

8. DIRECT INSTRUCTION / DISCOVERY
   "If [Specific Problem], Do [Specific Action]."
   "If [Person] [Behaviour], Stop Doing This [Specific Thing]."
   "[Specific Situation] — Here's Why It Happens / What It Means."
   Promise an action only when the article actually gives useful advice.
"""

EDITORIAL_DNA = """
The target blogger's headline instincts are:

- Start with a recognisable person, relationship, behaviour or situation.
- Make the reader understand the subject immediately.
- Promise a concrete inventory, sign, explanation, consequence or discovery.
- Create curiosity through recognition and interpretation, not vague drama.
- Use direct, plain language with a strong reader-facing angle.
- Prefer specific relationship nouns and verbs over abstract emotional language.
- Make the headline feel like a useful discovery, not a sentence lifted from
  an essay.
- Numbered packaging is the default when the article supports a real count.
- A strong headline can be uncomfortable, but it must remain accurate.
- Do not copy the research examples. Reproduce their editorial instincts.

The headline should make a reader think:
"I recognise this situation. I want to know which behaviours, signs,
truths or consequences the article explains."
"""

ANALYSIS_SYSTEM_PROMPT = """
You are an exacting editorial analyst. Read the complete article and identify
what it actually says before anyone writes a headline.

Do not write headlines in this stage. Do not turn the article into generic
self-help advice. Do not mistake one memorable sentence for the central point.

Identify:
- The actual subject and central argument.
- The reader and concrete problem.
- The main tension or contradiction.
- Distinct supporting points.
- Observable behaviours, statements and situations.
- Consequences described by the article.
- Surprising but supported interpretations.
- Practical actions, only if actually recommended.
- The strongest concrete reader-facing angles.
- Unsupported claims, promises and exaggerations to avoid.
- Countable groups that could honestly support numbered headlines.
- Short exact evidence excerpts supporting the most useful points.

Separate explicit claims from reasonable inferences. Never invent examples,
numbers, signs, diagnoses, advice or claims.

A numbered headline is appropriate only if the article contains enough
genuinely distinct material. State the countable material and the maximum
honest count where possible.

Return only valid JSON:
{
  "central_subject": "",
  "central_argument": "",
  "target_reader": "",
  "reader_problem": "",
  "main_tension": "",
  "key_points": [],
  "observable_behaviours": [],
  "consequences": [],
  "surprising_insights": [],
  "practical_actions": [],
  "strongest_headline_angles": [],
  "unsupported_claims_to_avoid": [],
  "usable_numbered_material": [],
  "evidence_excerpts": [],
  "article_type": "",
  "numbered_headline_supported": true,
  "maximum_honest_count": 0
}
"""

GENERATION_SYSTEM_PROMPT = f"""
You are a senior Pinterest editorial strategist. Your task is to package
articles using a specific blogger's researched headline instincts, not to
invent a new style.

{EDITORIAL_DNA}

THE EIGHT HEADLINE FAMILIES:
{FAMILIES}

RESEARCH ANCHORS — STUDY THE MECHANICS, DO NOT COPY THE WORDING:
{json.dumps(RESEARCH_ANCHORS, ensure_ascii=False)}

HOW TO THINK:
1. Identify the strongest reader-facing subject or situation.
2. Identify the most concrete article-supported material.
3. Choose the formula family that makes that material most compelling.
4. Choose a curiosity mechanism: recognition, interpretation, discovery,
   consequence or uncomfortable truth.
5. Make the promise specific enough to understand without reading the article.
6. Create genuinely different editorial entry points, not cosmetic rewrites.

NUMBERED HEADLINES:
Aim for approximately 90% numbered candidates when the article supports
genuinely countable material. For ten candidates, aim for nine numbered
candidates when the evidence supports that many. This is a target for the
candidate mix, not permission to invent lists or inflate counts.
If the article does not support a number, do not force one.

CANDIDATE DIVERSITY:
Generate ten candidates with meaningfully different angles. Where supported,
explore several of these:
- What the person does.
- What the person says.
- Signs that reveal a hidden reality.
- What happens under a particular condition.
- The consequence of a repeated behaviour.
- An uncomfortable truth about the situation.
- An unexpected interpretation.
- A practical response or discovery.

Do not force every family into every article. Do not generate ten versions
of the same promise.

REJECT THESE STYLES:
- Essay excerpts and poetic observations.
- Inspirational or therapy-sounding affirmations.
- Vague emotional fragments.
- Abstract metaphors that conceal the subject.
- Dramatic quote-like statements.
- Generic claims about healing, worth, pain or growth.
- Constructions such as "doesn't just hurt you, it steals...",
  "you were never broken", "it was never about...", or "the truth is...".
- Headlines that repeat the article title without adding a reader-facing angle.
- Unsupported absolutes such as always, never and every.
- Claims that make one behaviour sound universal.

SUBJECT CLARITY:
Name the person, relationship, behaviour or situation clearly. "Narcissist"
is useful only when the article supports that subject. Do not add it merely
because the account's niche often discusses narcissism.

OUTPUT:
Return exactly ten candidates if possible. Each candidate must include:
family, headline, angle, curiosity_mechanism, and generation_score.
generation_score is an initial estimate, not the final editorial decision.

Return only valid JSON:
{{
  "candidates": [
    {{
      "family": "behavioural_warning",
      "headline": "Complete headline",
      "angle": "Distinct article-supported angle",
      "curiosity_mechanism": "recognition",
      "generation_score": 8
    }}
  ],
  "blue_words": [],
  "emotion": "",
  "editorial_angle": ""
}}
"""

EVALUATION_SYSTEM_PROMPT = f"""
You are an independent, demanding Pinterest headline editor. You are not
the generator. Do not rewrite candidate wording.

{EDITORIAL_DNA}

RESEARCHED FAMILIES:
{FAMILIES}

Evaluate each candidate against the article evidence packet and the exact
headline research anchors. The examples are evidence of the target style;
do not demand that every candidate copy their wording.

SCORE EACH DIMENSION FROM 1 TO 10:
1. article_fidelity: Is the promise genuinely supported?
2. formula_fit: Does it use one of the researched headline families?
3. subject_clarity: Is the person, behaviour or situation immediately clear?
4. specificity: Does it promise identifiable signs, actions, truths,
   consequences, discoveries or advice?
5. curiosity: Does it create a compelling information gap?
6. pinterest_readability: Is it direct, natural and easy to understand?
7. distinctiveness: Is the angle meaningfully different from the other
   candidates and previous headlines?

Be demanding. A fluent sentence is not automatically a good Pinterest
headline. Reject vague, generic, essay-like, poetic, slogan-like, awkward,
unsupported or misleading headlines.

Reject candidates that:
- Hide the subject behind abstract language.
- Use an unsupported number or promise.
- Make a general claim from one isolated example.
- Promise a solution the article does not provide.
- Merely repeat the article title.
- Closely imitate a previous headline.
- Sound like a quote from a reflective essay.
- Use a formula mechanically when it does not fit the article.

A numbered headline is preferred when the article supports a real list.
However, do not approve a weak numbered headline merely because it is
numbered. A strong non-numbered headline may be better.

A candidate should normally be approved only when:
- article_fidelity is at least 8;
- subject_clarity is at least 7;
- specificity is at least 7;
- pinterest_readability is at least 7;
- the overall score is at least 8.

Do not approve all candidates to be agreeable. Be selective.

Return only valid JSON:
{{
  "evaluations": [
    {{
      "headline": "Exact original candidate wording",
      "approved": true,
      "score": 8.5,
      "dimensions": {{
        "article_fidelity": 9,
        "formula_fit": 8,
        "subject_clarity": 9,
        "specificity": 8,
        "curiosity": 8,
        "pinterest_readability": 9,
        "distinctiveness": 8
      }},
      "reason": "Brief, specific editorial explanation"
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# JSON AND TEXT HELPERS
# ---------------------------------------------------------------------------

def _parse_response(response_text: str) -> dict:
    raw = (response_text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object.")
    return parsed


def _normalise_headline(headline: str) -> str:
    value = (headline or "").casefold()
    value = value.translate(
        str.maketrans("", "", string.punctuation + "“”‘’—–")
    )
    return " ".join(value.split())


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(
        None, _normalise_headline(left), _normalise_headline(right)
    ).ratio()


def _is_numbered_headline(headline: str) -> bool:
    return bool(NUMBER_PATTERN.match((headline or "").strip()))


def _is_quote_like_or_slogan(headline: str) -> bool:
    text = " ".join((headline or "").casefold().split())
    patterns = (
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
    return any(re.search(pattern, text) for pattern in patterns)


def _compact_analysis(analysis: dict) -> dict:
    """
    Keep the evidence packet useful but compact. The full article is sent
    only to Stage 1; these limits prevent later stages repeating it.
    """
    limits = {
        "central_subject": 350,
        "central_argument": 650,
        "target_reader": 300,
        "reader_problem": 450,
        "main_tension": 450,
        "article_type": 120,
    }
    packet = {}
    for key, limit in limits.items():
        value = analysis.get(key, "")
        packet[key] = str(value or "")[:limit]

    list_limits = {
        "key_points": (10, 240),
        "observable_behaviours": (10, 220),
        "consequences": (8, 220),
        "surprising_insights": (6, 220),
        "practical_actions": (8, 180),
        "strongest_headline_angles": (8, 220),
        "unsupported_claims_to_avoid": (10, 180),
        "usable_numbered_material": (8, 220),
        "evidence_excerpts": (8, 260),
    }
    for key, (count, length) in list_limits.items():
        values = analysis.get(key, [])
        if not isinstance(values, list):
            values = []
        packet[key] = [
            str(value).strip()[:length]
            for value in values[:count]
            if str(value).strip()
        ]

    packet["numbered_headline_supported"] = bool(
        analysis.get("numbered_headline_supported", False)
    )
    try:
        packet["maximum_honest_count"] = max(
            0, min(20, int(analysis.get("maximum_honest_count", 0)))
        )
    except (TypeError, ValueError):
        packet["maximum_honest_count"] = 0

    return packet


# ---------------------------------------------------------------------------
# GROQ PROVIDER
# ---------------------------------------------------------------------------

def _try_groq(
    prompt: str,
    system_prompt: str,
    temperature: float = 0.7,
) -> dict:
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    client = Groq(api_key=api_key)
    combined_prompt = (
        system_prompt.strip()
        + "\n\n"
        + "=" * 60
        + "\nTASK\n"
        + "=" * 60
        + "\n"
        + prompt.strip()
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": combined_prompt}],
        temperature=temperature,
        max_completion_tokens=8192,
        response_format={"type": "json_object"},
        reasoning_effort="medium",
        include_reasoning=False,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Groq returned an empty response.")
    return _parse_response(content)


def _call_model(
    system_prompt: str,
    prompt: str,
    temperature: float = 0.7,
) -> dict:
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not configured.")

    log.info("  AI provider: Groq / %s", GROQ_MODEL)
    try:
        return _try_groq(prompt, system_prompt, temperature)
    except Exception as exc:
        log.exception("Groq model request failed.")
        raise RuntimeError(
            f"Groq model request failed ({GROQ_MODEL}): {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# STAGE 1: COMPLETE ARTICLE ANALYSIS
# ---------------------------------------------------------------------------

def _build_analysis_prompt(title: str, body: str) -> str:
    return f"""
ARTICLE TITLE:
{title}

COMPLETE ARTICLE BODY:
{body}

Read the complete article. Do not generate headlines.
Identify its real argument, evidence, concrete reader-facing angles,
unsupported claims and any genuinely countable material.

Include short exact evidence excerpts that support your analysis.
Return the JSON structure specified in your instructions.
"""


def _analyse_article(title: str, body: str) -> dict:
    if not body or not body.strip():
        raise ValueError("Cannot analyse an empty article body.")

    result = _call_model(
        ANALYSIS_SYSTEM_PROMPT,
        _build_analysis_prompt(title, body),
        temperature=0.2,
    )
    if not result.get("central_subject"):
        raise ValueError("Article analysis did not identify a central subject.")
    if not result.get("central_argument"):
        raise ValueError("Article analysis did not identify its central argument.")

    return _compact_analysis(result)


# ---------------------------------------------------------------------------
# STAGES 2 AND 3: EVIDENCE-PACKET PROMPTS
# ---------------------------------------------------------------------------

def _build_headline_prompt(
    title: str,
    body: str,
    analysis: dict,
    recent_headlines: list[str],
) -> str:
    # body remains in the function signature for compatibility, but is
    # deliberately not sent again. Stage 1 already read the full article.
    del body

    return f"""
ARTICLE TITLE:
{title}

ARTICLE EVIDENCE PACKET:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

PREVIOUS HEADLINES FOR THIS ARTICLE:
{json.dumps(recent_headlines, ensure_ascii=False, indent=2)}

Generate ten distinct Pinterest headline candidates from the evidence packet.
Use different editorial angles, not cosmetic rewrites.
Aim for approximately nine numbered candidates only if the evidence supports
genuinely countable material. If it does not, use truthful alternatives.

Use the eight researched families and editorial instincts in your instructions.
Do not copy research examples. Do not invent evidence, numbers, behaviours,
signs, consequences or advice. Do not repeat the title or previous headlines.

Every headline must be immediately understandable and must sound like a
Pinterest headline, not a poetic or reflective essay sentence.

Return the required JSON.
"""


def _build_evaluation_prompt(
    title: str,
    body: str,
    analysis: dict,
    candidates: list[dict],
    recent_headlines: list[str],
) -> str:
    # body is deliberately not sent again; the evaluator receives the
    # compact evidence packet produced after the complete article was read.
    del body

    return f"""
ARTICLE TITLE:
{title}

ARTICLE EVIDENCE PACKET:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

CANDIDATES TO EVALUATE:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

PREVIOUS HEADLINES:
{json.dumps(recent_headlines, ensure_ascii=False, indent=2)}

Evaluate every candidate independently. Score all seven dimensions.
Do not rewrite candidates. Do not approve weak headlines to fill a quota.
A candidate must be rejected if the packet does not support its promise.

Return one evaluation for every candidate using the required JSON structure.
"""


# ---------------------------------------------------------------------------
# CANDIDATE CLEANING AND INDEPENDENT EVALUATION
# ---------------------------------------------------------------------------

def _clean_candidates(data: dict) -> list[dict]:
    raw_candidates = data.get("candidates") or []
    cleaned = []
    seen = set()

    for item in raw_candidates:
        if not isinstance(item, dict):
            continue

        headline = re.sub(
            r"\s+", " ", str(item.get("headline", ""))
        ).strip().strip('"“”')
        if not headline:
            continue

        key = _normalise_headline(headline)
        if not key or key in seen:
            continue
        seen.add(key)

        try:
            score = float(
                item.get("generation_score", item.get("score", 0))
            )
        except (TypeError, ValueError):
            score = 0.0

        cleaned.append({
            "family": str(item.get("family", "")).strip(),
            "headline": headline,
            "score": score,
            "angle": str(item.get("angle", "")).strip(),
            "curiosity_mechanism": str(
                item.get("curiosity_mechanism", "")
            ).strip(),
        })

    return cleaned


def _evaluate_candidates(
    title: str,
    body: str,
    analysis: dict,
    candidates: list[dict],
    recent_headlines: list[str],
) -> list[dict]:
    prompt = _build_evaluation_prompt(
        title, body, analysis, candidates, recent_headlines
    )
    result = _call_model(
        EVALUATION_SYSTEM_PROMPT, prompt, temperature=0.1
    )
    evaluations = result.get("evaluations")
    if not isinstance(evaluations, list):
        raise ValueError("Editorial evaluator returned no valid evaluations.")
    return evaluations


def _approved_candidate_headlines(
    candidates: list[dict],
    evaluations: list[dict],
) -> list[str]:
    candidate_by_key = {
        _normalise_headline(item["headline"]): item
        for item in candidates
    }
    approved = []

    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue

        key = _normalise_headline(
            str(evaluation.get("headline", "")).strip()
        )
        candidate = candidate_by_key.get(key)
        if not candidate or evaluation.get("approved") is not True:
            continue

        if _is_quote_like_or_slogan(candidate["headline"]):
            continue

        try:
            score = float(evaluation.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0

        dimensions = evaluation.get("dimensions") or {}
        if not isinstance(dimensions, dict):
            dimensions = {}

        try:
            fidelity = float(dimensions.get("article_fidelity", 0))
            clarity = float(dimensions.get("subject_clarity", 0))
            specificity = float(dimensions.get("specificity", 0))
            readability = float(
                dimensions.get("pinterest_readability", 0)
            )
        except (TypeError, ValueError):
            fidelity = clarity = specificity = readability = 0

        # Do not accept a high average score that hides a serious weakness.
        if (
            score < 8
            or fidelity < 8
            or clarity < 7
            or specificity < 7
            or readability < 7
        ):
            continue

        candidate["score"] = score
        candidate["evaluation_reason"] = str(
            evaluation.get("reason", "")
        ).strip()
        candidate["dimensions"] = dimensions
        approved.append(candidate["headline"])

    return approved


def _select_valid_result(
    data: dict,
    recent_headlines: list[str],
    approved_headlines: list[str] | None = None,
) -> dict:
    candidates = _clean_candidates(data)
    if not candidates:
        raise ValueError("Headline model returned no usable candidates.")

    history = [
        str(item).strip()
        for item in recent_headlines
        if item and str(item).strip()
    ]
    history_keys = {_normalise_headline(item) for item in history}

    if approved_headlines is None:
        approved_keys = {
            _normalise_headline(item["headline"])
            for item in candidates
            if not _is_quote_like_or_slogan(item["headline"])
        }
    else:
        approved_keys = {
            _normalise_headline(item) for item in approved_headlines
        }

    available = []
    for candidate in candidates:
        headline = candidate["headline"]
        key = _normalise_headline(headline)

        if key in history_keys or key not in approved_keys:
            continue
        if _is_quote_like_or_slogan(headline):
            continue
        if any(_similarity(headline, old) >= 0.90 for old in history):
            continue

        available.append(candidate)

    if not available:
        raise ValueError(
            "No sufficiently strong, approved and unused headline remains. "
            "The system will not select a rejected candidate or reuse a "
            "previous headline."
        )

    # Numbering is a preference, not an override. A numbered candidate gets
    # a small tie-break advantage; a clearly stronger non-numbered headline
    # can still win.
    selected = max(
        available,
        key=lambda item: (
            item["score"]
            + (0.35 if _is_numbered_headline(item["headline"]) else 0)
        ),
    )

    blue_words = data.get("blue_words", [])
    if not isinstance(blue_words, list):
        blue_words = []

    headline_lower = selected["headline"].casefold()
    blue_words = [
        str(word).strip()
        for word in blue_words
        if str(word).strip()
        and str(word).strip().casefold() in headline_lower
    ][:4]

    return {
        "headline": selected["headline"],
        "blue_words": blue_words,
        "emotion": str(data.get("emotion", "")).strip(),
        "family": selected["family"] or str(
            data.get("selected_family", "")
        ).strip(),
        "editorial_angle": selected["angle"] or str(
            data.get("editorial_angle", "")
        ).strip(),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# PUBLIC FUNCTION — KEEP THIS INTERFACE COMPATIBLE WITH main.py
# ---------------------------------------------------------------------------

def generate_headline(
    title: str,
    body: str,
    previous_headline: str = "",
    recent_headlines: list[str] | None = None,
) -> dict:
    if not title or not title.strip():
        raise ValueError("Article title is required.")
    if not body or not body.strip():
        raise ValueError("Article body is required.")

    history = list(recent_headlines or [])
    if previous_headline and previous_headline not in history:
        history.append(previous_headline)

    deduplicated = []
    seen = set()
    for item in history:
        if not item:
            continue
        key = _normalise_headline(str(item))
        if key and key not in seen:
            seen.add(key)
            deduplicated.append(str(item).strip())
    history = deduplicated

    log.info(
        "  Editorial : analysing complete article (%s characters)",
        len(body),
    )

    # Stage 1: the only stage that receives the complete article.
    analysis = _analyse_article(title, body)

    log.info(
        "  Article   : %s",
        str(analysis.get("central_subject", ""))[:120],
    )
    log.info(
        "  Numbering : supported=%s; maximum honest count=%s",
        analysis.get("numbered_headline_supported"),
        analysis.get("maximum_honest_count"),
    )

    # Stage 2: generate ten distinct angles from the compact evidence packet.
    generated = _call_model(
        GENERATION_SYSTEM_PROMPT,
        _build_headline_prompt(title, body, analysis, history),
        temperature=0.8,
    )
    candidates = _clean_candidates(generated)
    if not candidates:
        raise ValueError("Headline generation returned no usable candidates.")

    numbered_count = sum(
        1 for item in candidates
        if _is_numbered_headline(item["headline"])
    )
    log.info(
        "  Generated : %s candidates; %s numbered",
        len(candidates),
        numbered_count,
    )

    # Stage 3: independently score the exact candidate wording.
    evaluations = _evaluate_candidates(
        title, body, analysis, candidates, history
    )
    approved = _approved_candidate_headlines(candidates, evaluations)

    generated["candidates"] = candidates
    log.info(
        "  Evaluated : %s approved out of %s",
        len(approved),
        len(candidates),
    )

    selected = _select_valid_result(
        generated, history, approved_headlines=approved
    )

    log.info("  Selected  : %s", selected["headline"])
    return selected
