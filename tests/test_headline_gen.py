
import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import modules.headline_gen as headline_gen

from modules.headline_gen import (
    ANALYSIS_SYSTEM_PROMPT,
    EVALUATION_SYSTEM_PROMPT,
    GENERATION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    _analyse_article,
    _approved_candidate_headlines,
    _build_analysis_prompt,
    _build_evaluation_prompt,
    _build_headline_prompt,
    _is_numbered_headline,
    _is_quote_like_or_slogan,
    _normalise_headline,
    _parse_response,
    _select_valid_result,
    _try_cerebras,
    generate_headline,
)


def make_analysis():
    return {
        "central_subject": "Narcissistic relationship behaviour",
        "central_argument": (
            "The article explains how a need for admiration can displace "
            "genuine intimacy."
        ),
        "target_reader": "People in relationships with narcissists",
        "reader_problem": (
            "Understanding the difference between love and admiration"
        ),
        "main_tension": (
            "The desire for intimacy versus the demand for worship"
        ),
        "key_points": [
            "The narcissist wants to be needed",
            "The narcissist mirrors the reader's dreams",
            "The narcissist expects admiration",
            "The narcissist punishes exposure",
            "The narcissist confuses loyalty with submission",
        ],
        "observable_behaviours": [
            "Mirroring the reader's dreams",
            "Demanding admiration",
            "Punishing criticism",
        ],
        "consequences": [
            "Loyalty becomes confused with submission",
        ],
        "surprising_insights": [
            "The relationship can become organised around protecting "
            "the narcissist's image",
        ],
        "practical_actions": [],
        "strongest_headline_angles": [
            "Behaviours that reveal a demand for worship",
            "Signs that admiration matters more than intimacy",
            "The consequences of confusing loyalty with submission",
        ],
        "unsupported_claims_to_avoid": [
            "Claims that every narcissist behaves identically",
        ],
        "usable_numbered_material": [
            "Five distinct behaviours and relationship patterns "
            "described in the article",
        ],
        "evidence_excerpts": [
            "The relationship becomes organised around admiration.",
        ],
        "article_type": "Relationship explanation",
        "numbered_headline_supported": True,
        "maximum_honest_count": 5,
    }


def make_dimensions(
    fidelity=9,
    formula_fit=9,
    clarity=9,
    specificity=9,
    curiosity=9,
    readability=9,
    distinctiveness=9,
):
    return {
        "article_fidelity": fidelity,
        "formula_fit": formula_fit,
        "subject_clarity": clarity,
        "specificity": specificity,
        "curiosity": curiosity,
        "pinterest_readability": readability,
        "distinctiveness": distinctiveness,
    }


def make_evaluation(
    headline,
    approved=True,
    score=9,
    dimensions=None,
):
    return {
        "headline": headline,
        "approved": approved,
        "score": score,
        "dimensions": dimensions or make_dimensions(),
        "reason": "Specific, readable and supported by the article.",
    }


def make_response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ],
        usage=None,
    )


def cerebras_test_modules(fake_sdk):
    return {
        "cerebras": types.ModuleType("cerebras"),
        "cerebras.cloud": types.ModuleType("cerebras.cloud"),
        "cerebras.cloud.sdk": fake_sdk,
    }


class HeadlineFrameworkTests(unittest.TestCase):

    def setUp(self):
        headline_gen.GROQ_DAILY_LIMIT_REACHED = False

    def tearDown(self):
        headline_gen.GROQ_DAILY_LIMIT_REACHED = False

    # ---------------------------------------------------------------
    # RESEARCHED HEADLINE FRAMEWORK
    # ---------------------------------------------------------------

    def test_researched_headline_families_are_present(self):
        families = (
            "BEHAVIOURAL WARNING / INVENTORY",
            "HIDDEN-SIGN INTERPRETATION",
            "WHEN",
            "IF",
            "UNCOMFORTABLE TRUTH",
            "HARSH TRUTHS",
            "UNEXPECTED REVERSAL",
            "RELATIONSHIP CONSEQUENCES",
            "DIRECT INSTRUCTION / DISCOVERY",
        )

        for family in families:
            with self.subTest(family=family):
                self.assertIn(family, GENERATION_SYSTEM_PROMPT)

    def test_when_and_if_have_distinct_family_identifiers(self):
        self.assertIn(
            "when_conditional_revelation",
            GENERATION_SYSTEM_PROMPT,
        )
        self.assertIn(
            "if_conditional_discovery",
            GENERATION_SYSTEM_PROMPT,
        )

    def test_when_is_not_restricted_to_behavioural_lists(self):
        prompt = GENERATION_SYSTEM_PROMPT.casefold()

        self.assertIn("relationship changes", prompt)
        self.assertIn("consequences", prompt)
        self.assertIn("unexpected outcomes", prompt)

    def test_if_is_not_restricted_to_checklists(self):
        prompt = GENERATION_SYSTEM_PROMPT.casefold()

        self.assertIn("interpretations", prompt)
        self.assertIn("implications", prompt)
        self.assertIn("experiences", prompt)
        self.assertIn("discoveries", prompt)

    def test_researched_headline_examples_are_present(self):
        examples = (
            "7 Things Parents Should Never Do In Front Of Their Children",
            "9 Things Cheaters Always Do On Their Phones",
            "5 Things Selfish Wives Do Every Day",
            "8 Hurtful Things Husbands Say That Wives Never Forget",
            "8 Signs Your Husband Enjoys Hurting You",
            "When A Man Hates His Wife, He Says These 7 Things",
            "The Dark Side Of Marriage No One Talks About",
            "6 Harsh Truths About Marriage",
            "How To Silence A Narcissist With Just One Text",
            "Narcissistic Husbands Share One Pattern, And It's Terrifying",
            (
                "If A Narcissist Is Cheating On You, "
                "These 14 Lines Will Always Show Up"
            ),
        )

        for example in examples:
            with self.subTest(example=example):
                self.assertIn(example, SYSTEM_PROMPT)

    def test_positive_headline_anchor_is_present(self):
        self.assertIn(
            "Understand The System: Why A Narcissist Can't",
            GENERATION_SYSTEM_PROMPT,
        )

    def test_quote_like_negative_style_is_explicitly_rejected(self):
        prompt = GENERATION_SYSTEM_PROMPT.casefold()

        self.assertIn(
            "doesn't just hurt you, it steals",
            prompt,
        )
        self.assertIn("poetic observations", prompt)
        self.assertIn("dramatic quote-like statements", prompt)

    def test_numbered_candidates_remain_the_approximate_ninety_percent_target(self):
        prompt = GENERATION_SYSTEM_PROMPT.casefold()

        self.assertIn("approximately 90%", prompt)
        self.assertIn("nine numbered candidates", prompt)
        self.assertIn(
            "not permission to invent lists or inflate counts",
            prompt,
        )

    def test_numbered_headline_detector_accepts_digits_and_words(self):
        self.assertTrue(_is_numbered_headline("7 Things Narcissists Do"))
        self.assertTrue(
            _is_numbered_headline("Seven Signs of a Difficult Marriage")
        )
        self.assertTrue(
            _is_numbered_headline("Five Harsh Truths About Marriage")
        )

    def test_numbered_headline_detector_rejects_non_numbered_headlines(self):
        self.assertFalse(
            _is_numbered_headline("The Dark Side of Marriage")
        )
        self.assertFalse(
            _is_numbered_headline(
                "When a Narcissist Wants You Back"
            )
        )

    def test_quote_like_negative_anchor_is_rejected(self):
        headline = (
            "Narcissistic Abuse Doesn't Just Hurt You; "
            "It Steals Your Right To Trust Your Own Experience."
        )

        self.assertTrue(_is_quote_like_or_slogan(headline))

    def test_positive_anchor_is_not_rejected_by_slogan_filter(self):
        headline = (
            "Understand The System: Why a Narcissist Can't "
            "Tolerate These 7 Aspects of You."
        )

        self.assertFalse(_is_quote_like_or_slogan(headline))

    # ---------------------------------------------------------------
    # JSON AND NORMALISATION
    # ---------------------------------------------------------------

    def test_parse_json_fenced_response(self):
        parsed = _parse_response(
            '```json\n{"selected_headline":"A useful headline"}\n```'
        )

        self.assertEqual(
            parsed["selected_headline"],
            "A useful headline",
        )

    def test_parse_response_accepts_json_surrounded_by_text(self):
        parsed = _parse_response(
            'Here is the result:\n{"central_subject":"Marriage"}\nDone.'
        )

        self.assertEqual(parsed["central_subject"], "Marriage")

    def test_parse_response_rejects_non_object_json(self):
        with self.assertRaises(ValueError):
            _parse_response('["not", "an", "object"]')

    def test_parse_response_rejects_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            _parse_response('{"headline": invalid}')

    def test_headline_normalisation_ignores_punctuation_and_case(self):
        self.assertEqual(
            _normalise_headline("Seven Things Narcissists Do!"),
            _normalise_headline("SEVEN THINGS NARCISSISTS DO"),
        )

    # ---------------------------------------------------------------
    # ARTICLE ANALYSIS AND PROMPT CONSTRUCTION
    # ---------------------------------------------------------------

    def test_analysis_prompt_contains_complete_article(self):
        body = "This is the complete article text. " * 1500

        prompt = _build_analysis_prompt("Article title", body)

        self.assertIn(body, prompt)
        self.assertIn("COMPLETE ARTICLE BODY", prompt)

    def test_analysis_prompt_instructs_model_not_to_generate_headlines(self):
        prompt = _build_analysis_prompt(
            "Article title",
            "Complete article body.",
        )

        self.assertIn("Do not generate headlines", prompt)

    def test_analysis_returns_compact_evidence_packet(self):
        with patch(
            "modules.headline_gen._call_model",
            return_value=make_analysis(),
        ):
            result = _analyse_article(
                "Article title",
                "Complete article body.",
            )

        self.assertEqual(
            result["central_subject"],
            "Narcissistic relationship behaviour",
        )
        self.assertEqual(result["maximum_honest_count"], 5)
        self.assertTrue(result["numbered_headline_supported"])
        self.assertIn("evidence_excerpts", result)

    def test_analysis_rejects_missing_central_subject(self):
        analysis = make_analysis()
        analysis["central_subject"] = ""

        with patch(
            "modules.headline_gen._call_model",
            return_value=analysis,
        ):
            with self.assertRaises(ValueError):
                _analyse_article("Article title", "Article body")

    def test_analysis_rejects_missing_central_argument(self):
        analysis = make_analysis()
        analysis["central_argument"] = ""

        with patch(
            "modules.headline_gen._call_model",
            return_value=analysis,
        ):
            with self.assertRaises(ValueError):
                _analyse_article("Article title", "Article body")

    def test_analysis_rejects_empty_article(self):
        with self.assertRaises(ValueError):
            _analyse_article("Article title", "")

    def test_headline_prompt_contains_analysis_and_history(self):
        history = [
            "An older headline",
            "Another previously generated headline",
        ]

        prompt = _build_headline_prompt(
            title="Article title",
            body="The article body is not repeated here.",
            analysis=make_analysis(),
            recent_headlines=history,
        )

        self.assertIn("Narcissistic relationship behaviour", prompt)
        self.assertIn("An older headline", prompt)
        self.assertIn("Another previously generated headline", prompt)

    def test_headline_prompt_uses_evidence_packet_not_full_article(self):
        body = "UNIQUE_FULL_ARTICLE_BODY_MARKER"

        prompt = _build_headline_prompt(
            title="Article title",
            body=body,
            analysis=make_analysis(),
            recent_headlines=[],
        )

        self.assertNotIn(body, prompt)
        self.assertIn("ARTICLE EVIDENCE PACKET", prompt)

    def test_evaluation_prompt_contains_analysis_candidates_and_history(self):
        candidates = [{
            "family": "behavioural_warning",
            "headline": (
                "Seven Things Narcissists Do When They Want Admiration"
            ),
            "score": 9,
        }]

        prompt = _build_evaluation_prompt(
            "Article title",
            "The full article is not repeated.",
            make_analysis(),
            candidates,
            ["An older headline"],
        )

        self.assertIn("Narcissistic relationship behaviour", prompt)
        self.assertIn("Seven Things Narcissists Do", prompt)
        self.assertIn("An older headline", prompt)
        self.assertNotIn("The full article is not repeated.", prompt)

    # ---------------------------------------------------------------
    # EDITORIAL APPROVAL
    # ---------------------------------------------------------------

    def test_approval_matches_only_original_candidate_wording(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 8,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(
                "A completely new headline invented by the evaluator"
            )],
        )

        self.assertEqual(approved, [])

    def test_approval_requires_evaluator_approval(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 8,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(headline, approved=False)],
        )

        self.assertEqual(approved, [])

    def test_evaluator_rejects_low_overall_score(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 8,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(headline, score=6)],
        )

        self.assertEqual(approved, [])

    def test_evaluator_rejects_low_article_fidelity(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 9,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(
                headline,
                dimensions=make_dimensions(fidelity=6),
            )],
        )

        self.assertEqual(approved, [])

    def test_evaluator_rejects_low_subject_clarity(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 9,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(
                headline,
                dimensions=make_dimensions(clarity=6),
            )],
        )

        self.assertEqual(approved, [])

    def test_evaluator_rejects_low_specificity(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 9,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(
                headline,
                dimensions=make_dimensions(specificity=6),
            )],
        )

        self.assertEqual(approved, [])

    def test_evaluator_rejects_low_readability(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 9,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(
                headline,
                dimensions=make_dimensions(readability=6),
            )],
        )

        self.assertEqual(approved, [])

    def test_evaluator_accepts_candidate_that_passes_all_quality_gates(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        candidates = [{
            "family": "behavioural_warning",
            "headline": headline,
            "score": 8,
        }]

        approved = _approved_candidate_headlines(
            candidates,
            [make_evaluation(headline)],
        )

        self.assertEqual(approved, [headline])

    # ---------------------------------------------------------------
    # HEADLINE SELECTION AND NUMBERED PREFERENCE
    # ---------------------------------------------------------------

    def test_selected_headline_must_be_an_approved_candidate(self):
        first = "Five Things a Narcissist Does After You Say No"
        second = "Six Signs a Narcissist Is Punishing Your Boundaries"

        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": first,
                    "score": 9,
                },
                {
                    "family": "hidden_sign_interpretation",
                    "headline": second,
                    "score": 8,
                },
            ],
            "selected_headline": "A made-up headline",
            "blue_words": ["say no"],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[first],
        )

        self.assertEqual(result["headline"], first)

    def test_numbered_preference_breaks_a_close_score_difference(self):
        non_numbered = "The Dark Side of Loving a Narcissist"
        numbered = (
            "Seven Things Narcissists Do When They Want Admiration"
        )

        data = {
            "candidates": [
                {
                    "family": "uncomfortable_truth",
                    "headline": non_numbered,
                    "score": 9,
                },
                {
                    "family": "behavioural_warning",
                    "headline": numbered,
                    "score": 8.8,
                },
            ],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[non_numbered, numbered],
        )

        self.assertEqual(result["headline"], numbered)

    def test_numbered_preference_does_not_override_a_large_quality_gap(self):
        non_numbered = "The Dark Side of Loving a Narcissist"
        numbered = (
            "Seven Things Narcissists Do When They Want Admiration"
        )

        data = {
            "candidates": [
                {
                    "family": "uncomfortable_truth",
                    "headline": non_numbered,
                    "score": 10,
                },
                {
                    "family": "behavioural_warning",
                    "headline": numbered,
                    "score": 8,
                },
            ],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[non_numbered, numbered],
        )

        self.assertEqual(result["headline"], non_numbered)

    def test_non_numbered_candidate_can_be_selected_if_numbered_is_rejected(self):
        numbered = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        non_numbered = "The Dark Side of Loving a Narcissist"

        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": numbered,
                    "score": 10,
                },
                {
                    "family": "uncomfortable_truth",
                    "headline": non_numbered,
                    "score": 8,
                },
            ],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[non_numbered],
        )

        self.assertEqual(result["headline"], non_numbered)

    def test_exact_previous_wording_is_never_selected_again(self):
        first = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        second = (
            "Six Signs a Narcissist Values Praise More Than Love"
        )

        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": first,
                    "score": 10,
                },
                {
                    "family": "hidden_sign_interpretation",
                    "headline": second,
                    "score": 8,
                },
            ],
        }

        result = _select_valid_result(
            data,
            [first.upper() + "!"],
            approved_headlines=[first, second],
        )

        self.assertEqual(result["headline"], second)

    def test_fails_if_every_candidate_was_previously_used(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        data = {
            "candidates": [{
                "family": "behavioural_warning",
                "headline": headline,
                "score": 10,
            }],
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                [headline],
                approved_headlines=[headline],
            )

    def test_fails_if_no_candidate_passes_editorial_evaluation(self):
        headline = (
            "Seven Things Narcissists Do When They Want Admiration"
        )
        data = {
            "candidates": [{
                "family": "behavioural_warning",
                "headline": headline,
                "score": 10,
            }],
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                [],
                approved_headlines=[],
            )

    def test_quote_like_candidate_is_rejected_even_if_approved(self):
        headline = (
            "Narcissistic Abuse Doesn't Just Hurt You; "
            "It Steals Your Right To Trust Your Own Experience."
        )
        data = {
            "candidates": [{
                "family": "relationship_consequences",
                "headline": headline,
                "score": 10,
            }],
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                [],
                approved_headlines=[headline],
            )

    def test_blue_words_must_appear_in_selected_headline(self):
        headline = "Five Things a Narcissist Does After You Say No"
        data = {
            "candidates": [{
                "family": "behavioural_warning",
                "headline": headline,
                "score": 9,
            }],
            "blue_words": [
                "Narcissist",
                "Say No",
                "unrelated phrase",
            ],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[headline],
        )

        self.assertEqual(
            result["blue_words"],
            ["Narcissist", "Say No"],
        )

    # ---------------------------------------------------------------
    # CEREBRAS RESPONSE RECOVERY
    # ---------------------------------------------------------------

    def test_cerebras_retries_once_after_malformed_json(self):
        valid_analysis = {
            "central_subject": "Marriage",
            "central_argument": (
                "The article explains a relationship pattern."
            ),
        }

        fake_sdk = types.ModuleType("cerebras.cloud.sdk")
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [
            make_response("{malformed json"),
            make_response(json.dumps(valid_analysis)),
        ]
        fake_sdk.Cerebras = MagicMock(return_value=fake_client)

        with patch.dict(
            sys.modules,
            cerebras_test_modules(fake_sdk),
        ), patch.dict(
            "os.environ",
            {"CEREBRAS_API_KEY": "test-key"},
        ):
            result = _try_cerebras(
                "Analyse this article.",
                ANALYSIS_SYSTEM_PROMPT,
                temperature=0.7,
                stage="analysis",
            )

        self.assertEqual(result["central_subject"], "Marriage")
        self.assertEqual(
            fake_client.chat.completions.create.call_count,
            2,
        )

        retry_call = (
            fake_client.chat.completions.create.call_args_list[1]
        )

        self.assertEqual(retry_call.kwargs["temperature"], 0.2)
        self.assertIn(
            "RECOVERY INSTRUCTION",
            retry_call.kwargs["messages"][0]["content"],
        )

    def test_cerebras_retries_after_structurally_invalid_json(self):
        valid_generation = {
            "candidates": [{
                "headline": "Seven Things That Change a Marriage",
                "family": "behavioural_warning",
            }]
        }

        fake_sdk = types.ModuleType("cerebras.cloud.sdk")
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [
            make_response('{"wrong_field": "No candidates"}'),
            make_response(json.dumps(valid_generation)),
        ]
        fake_sdk.Cerebras = MagicMock(return_value=fake_client)

        with patch.dict(
            sys.modules,
            cerebras_test_modules(fake_sdk),
        ), patch.dict(
            "os.environ",
            {"CEREBRAS_API_KEY": "test-key"},
        ):
            result = _try_cerebras(
                "Generate headlines.",
                GENERATION_SYSTEM_PROMPT,
                stage="generation",
            )

        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(
            fake_client.chat.completions.create.call_count,
            2,
        )

    def test_cerebras_fails_after_one_unsuccessful_recovery(self):
        fake_sdk = types.ModuleType("cerebras.cloud.sdk")
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = [
            make_response("{bad json"),
            make_response("{still bad json"),
        ]
        fake_sdk.Cerebras = MagicMock(return_value=fake_client)

        with patch.dict(
            sys.modules,
            cerebras_test_modules(fake_sdk),
        ), patch.dict(
            "os.environ",
            {"CEREBRAS_API_KEY": "test-key"},
        ):
            with self.assertRaises(RuntimeError):
                _try_cerebras(
                    "Analyse this article.",
                    ANALYSIS_SYSTEM_PROMPT,
                    stage="analysis",
                )

        self.assertEqual(
            fake_client.chat.completions.create.call_count,
            2,
        )

    def test_cerebras_does_not_retry_provider_api_errors(self):
        fake_sdk = types.ModuleType("cerebras.cloud.sdk")
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError(
            "Cerebras service unavailable"
        )
        fake_sdk.Cerebras = MagicMock(return_value=fake_client)

        with patch.dict(
            sys.modules,
            cerebras_test_modules(fake_sdk),
        ), patch.dict(
            "os.environ",
            {"CEREBRAS_API_KEY": "test-key"},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "service unavailable",
            ):
                _try_cerebras(
                    "Analyse this article.",
                    ANALYSIS_SYSTEM_PROMPT,
                    stage="analysis",
                )

        self.assertEqual(
            fake_client.chat.completions.create.call_count,
            1,
        )

    # ---------------------------------------------------------------
    # GROQ DAILY QUOTA CIRCUIT BREAKER
    # ---------------------------------------------------------------

    def test_daily_quota_error_marks_groq_as_exhausted(self):
        def simulate_groq_daily_limit(*args, **kwargs):
            # The real _try_groq() sets this process-level circuit breaker
            # before raising a daily-token-limit error.
            headline_gen.GROQ_DAILY_LIMIT_REACHED = True
            raise RuntimeError(
                "Rate limit reached: tokens per day exceeded"
            )

        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "groq-test-key",
                "CEREBRAS_API_KEY": "cerebras-test-key",
            },
        ), patch(
            "modules.headline_gen._try_groq",
            side_effect=simulate_groq_daily_limit,
        ), patch(
            "modules.headline_gen._try_cerebras",
            return_value={"central_subject": "Marriage"},
        ):
            result = headline_gen._call_model(
                ANALYSIS_SYSTEM_PROMPT,
                "Analyse the article.",
                stage="analysis",
            )

        self.assertEqual(result["central_subject"], "Marriage")
        self.assertTrue(headline_gen.GROQ_DAILY_LIMIT_REACHED)

    def test_groq_is_skipped_after_daily_quota_is_exhausted(self):
        headline_gen.GROQ_DAILY_LIMIT_REACHED = True

        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "groq-test-key",
                "CEREBRAS_API_KEY": "cerebras-test-key",
            },
        ), patch(
            "modules.headline_gen._try_groq"
        ) as groq_mock, patch(
            "modules.headline_gen._try_cerebras",
            return_value={"central_subject": "Marriage"},
        ) as cerebras_mock:
            result = headline_gen._call_model(
                ANALYSIS_SYSTEM_PROMPT,
                "Analyse the next article.",
                stage="analysis",
            )

        groq_mock.assert_not_called()
        cerebras_mock.assert_called_once()
        self.assertEqual(result["central_subject"], "Marriage")

    def test_temporary_groq_failure_does_not_mark_daily_quota_exhausted(self):
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "groq-test-key",
                "CEREBRAS_API_KEY": "cerebras-test-key",
            },
        ), patch(
            "modules.headline_gen._try_groq",
            side_effect=RuntimeError("Temporary connection failure"),
        ), patch(
            "modules.headline_gen._try_cerebras",
            return_value={"central_subject": "Marriage"},
        ):
            headline_gen._call_model(
                ANALYSIS_SYSTEM_PROMPT,
                "Analyse the article.",
                stage="analysis",
            )

        self.assertFalse(headline_gen.GROQ_DAILY_LIMIT_REACHED)

    # ---------------------------------------------------------------
    # THREE-STAGE PIPELINE AND PUBLIC INTERFACE
    # ---------------------------------------------------------------

    def test_generation_uses_three_model_stages(self):
        body = (
            "A complete article paragraph with useful details. " * 120
        )

        first_headline = (
            "Seven Things Narcissists Do When They Want You to Admire Them"
        )
        second_headline = (
            "The Dark Side of Loving Someone Who Needs to Be Worshipped"
        )

        generated = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": first_headline,
                    "generation_score": 9,
                    "angle": (
                        "Recognisable behaviours linked to admiration"
                    ),
                    "curiosity_mechanism": "recognition",
                },
                {
                    "family": "uncomfortable_truth",
                    "headline": second_headline,
                    "generation_score": 8,
                    "angle": (
                        "The uncomfortable cost of demanding worship"
                    ),
                    "curiosity_mechanism": "consequence",
                },
            ],
            "blue_words": ["Narcissists", "Admire Them"],
            "emotion": "Recognition",
            "editorial_angle": (
                "The article explains the demand for admiration."
            ),
        }

        evaluations = {
            "evaluations": [
                make_evaluation(first_headline, score=9),
                make_evaluation(second_headline, score=8),
            ]
        }

        with patch(
            "modules.headline_gen._call_model",
            side_effect=[
                make_analysis(),
                generated,
                evaluations,
            ],
        ) as mocked_model:
            result = generate_headline(
                title="Why Narcissists Want Worship Instead of Love",
                body=body,
                recent_headlines=["An older headline"],
            )

        self.assertEqual(mocked_model.call_count, 3)

        analysis_call = mocked_model.call_args_list[0]
        generation_call = mocked_model.call_args_list[1]
        evaluation_call = mocked_model.call_args_list[2]

        self.assertIn(body, analysis_call.args[1])
        self.assertNotIn(body, generation_call.args[1])
        self.assertNotIn(body, evaluation_call.args[1])

        self.assertIn("An older headline", generation_call.args[1])
        self.assertIn("An older headline", evaluation_call.args[1])

        self.assertEqual(result["headline"], first_headline)
        self.assertEqual(result["family"], "behavioural_warning")
        self.assertIn("candidates", result)
        self.assertIn("blue_words", result)
        self.assertIn("emotion", result)
        self.assertIn("editorial_angle", result)

    def test_generation_passes_correct_stage_names_to_model(self):
        first_headline = (
            "Seven Things Narcissists Do When They Want You to Admire Them"
        )

        generated = {
            "candidates": [{
                "family": "behavioural_warning",
                "headline": first_headline,
                "generation_score": 9,
                "angle": "Behavioural pattern",
            }]
        }

        evaluations = {
            "evaluations": [make_evaluation(first_headline)]
        }

        with patch(
            "modules.headline_gen._call_model",
            side_effect=[
                make_analysis(),
                generated,
                evaluations,
            ],
        ) as mocked_model:
            generate_headline(
                "Article title",
                "A complete article body.",
            )

        stages = [
            call.kwargs.get("stage")
            for call in mocked_model.call_args_list
        ]

        self.assertEqual(
            stages,
            ["analysis", "generation", "evaluation"],
        )

    def test_generation_rejects_empty_article(self):
        with self.assertRaises(ValueError):
            generate_headline(
                title="Article title",
                body="",
            )

    def test_generation_rejects_empty_title(self):
        with self.assertRaises(ValueError):
            generate_headline(
                title="",
                body="A complete article body.",
            )


if __name__ == "__main__":
    unittest.main()
