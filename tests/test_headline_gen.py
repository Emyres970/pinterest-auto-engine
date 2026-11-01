import unittest
from unittest.mock import patch

from modules.headline_gen import (
    ANALYSIS_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    EVALUATION_SYSTEM_PROMPT,
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
        "reader_problem": "Understanding the difference between love and admiration",
        "main_tension": "The desire for intimacy versus the demand for worship",
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
            "The relationship can become organised around protecting the narcissist's image",
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
            "Five distinct behaviours and relationship patterns described in the article",
        ],
        "article_type": "Relationship explanation",
    }


class HeadlineFrameworkTests(unittest.TestCase):

    def test_all_eight_researched_families_are_explicit(self):
        families = (
            "BEHAVIOURAL WARNING / INVENTORY",
            "HIDDEN-SIGN INTERPRETATION",
            "CONDITIONAL REVELATION",
            "UNCOMFORTABLE TRUTH",
            "HARSH TRUTHS",
            "UNEXPECTED REVERSAL",
            "RELATIONSHIP CONSEQUENCES / CAUSE AND EFFECT",
            "DIRECT INSTRUCTION / DISCOVERY",
        )

        for family in families:
            self.assertIn(family, SYSTEM_PROMPT)

    def test_research_examples_are_present(self):
        examples = (
            "7 Things Parents Should Never Do in Front of Their Children",
            "9 Things Cheaters Always Do on Their Phones",
            "5 Things Selfish Wives Do Every Day",
            "8 Hurtful Things Husbands Say That Wives Never Forget",
            "8 Signs Your Husband Enjoys Hurting You",
            "7 Signs You're in a Parenting Marriage Without Even Realizing It",
            "When a Man Hates His Wife, He Says These 7 Things",
            "The Dark Side of Marriage No One Talks About",
            "6 Harsh Truths About Marriage",
            "If You Notice These 5 Things in Your Husband, You're Emotionally Intelligent",
        )

        for example in examples:
            self.assertIn(example, SYSTEM_PROMPT)

    def test_narcissist_adaptation_anchors_are_present(self):
        anchors = (
            "7 Things Narcissists Do When They Realize You're Pulling Away",
            "8 Things Narcissists Say When They Want You to Feel Guilty",
            "8 Signs a Narcissist Is Punishing You for Setting Boundaries",
            "When a Narcissist Is Losing Control of You, They Say These 7 Things",
            "The Dark Side of Having a Narcissistic Mother No One Talks About",
            "6 Harsh Truths About Loving a Narcissist",
            "6 Things Narcissists Do That Slowly Turn Love Into Submission",
            "If a Narcissist Uses Silence to Punish You, Do This Instead",
        )

        for anchor in anchors:
            self.assertIn(anchor, SYSTEM_PROMPT)

    def test_numbered_candidates_are_the_ninety_percent_target(self):
        self.assertIn("Approximately 90% of generated candidates", SYSTEM_PROMPT)
        self.assertIn("Generate TEN candidates", SYSTEM_PROMPT)
        self.assertIn("NINE numbered candidates", SYSTEM_PROMPT)

    def test_numbered_headline_detector_accepts_digits_and_words(self):
        self.assertTrue(_is_numbered_headline("7 Things Narcissists Do"))
        self.assertTrue(_is_numbered_headline("Seven Signs of a Difficult Marriage"))
        self.assertTrue(_is_numbered_headline("Five Harsh Truths About Marriage"))

    def test_numbered_headline_detector_rejects_non_numbered_headlines(self):
        self.assertFalse(_is_numbered_headline("The Dark Side of Marriage"))
        self.assertFalse(_is_numbered_headline("When a Narcissist Wants You Back"))

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

    def test_evaluator_knows_positive_and_negative_anchors(self):
        self.assertIn(
            "Narcissistic Abuse Doesn't Just Hurt You",
            EVALUATION_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Understand The System",
            EVALUATION_SYSTEM_PROMPT,
        )

    def test_all_five_curiosity_mechanisms_are_present(self):
        for mechanism in (
            "RECOGNITION",
            "INTERPRETATION",
            "DISCOVERY",
            "CONSEQUENCE",
            "FORBIDDEN TRUTH",
        ):
            self.assertIn(mechanism, SYSTEM_PROMPT)

    def test_parse_json_fenced_response(self):
        parsed = _parse_response(
            '```json\n{"selected_headline":"A useful headline"}\n```'
        )

        self.assertEqual(
            parsed["selected_headline"],
            "A useful headline",
        )

    def test_parse_response_rejects_non_object_json(self):
        with self.assertRaises(ValueError):
            _parse_response('["not", "an", "object"]')

    def test_headline_normalisation_ignores_punctuation_and_case(self):
        self.assertEqual(
            _normalise_headline("Seven Things Narcissists Do!"),
            _normalise_headline("SEVEN THINGS NARCISSISTS DO"),
        )

    def test_selected_headline_must_be_an_approved_candidate(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Five Things a Narcissist Does After You Say No",
                    "score": 9,
                },
                {
                    "family": "hidden_sign_interpretation",
                    "headline": "Six Signs a Narcissist Is Punishing Your Boundaries",
                    "score": 8,
                },
            ],
            "selected_headline": "A made-up headline",
            "blue_words": ["say no"],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[
                "Five Things a Narcissist Does After You Say No",
            ],
        )

        self.assertEqual(
            result["headline"],
            "Five Things a Narcissist Does After You Say No",
        )

    def test_numbered_candidate_is_preferred_over_approved_non_numbered(self):
        data = {
            "candidates": [
                {
                    "family": "uncomfortable_truth",
                    "headline": "The Dark Side of Loving a Narcissist",
                    "score": 10,
                },
                {
                    "family": "behavioural_warning",
                    "headline": "Seven Things Narcissists Do When They Want Admiration",
                    "score": 8,
                },
            ],
            "selected_headline": "The Dark Side of Loving a Narcissist",
            "blue_words": ["Narcissists", "Admiration"],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[
                "The Dark Side of Loving a Narcissist",
                "Seven Things Narcissists Do When They Want Admiration",
            ],
        )

        self.assertEqual(
            result["headline"],
            "Seven Things Narcissists Do When They Want Admiration",
        )

    def test_non_numbered_can_be_selected_if_numbered_candidate_is_rejected(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Seven Things Narcissists Do When They Want Admiration",
                    "score": 10,
                },
                {
                    "family": "uncomfortable_truth",
                    "headline": "The Dark Side of Loving a Narcissist",
                    "score": 8,
                },
            ],
            "selected_headline": "",
            "blue_words": ["Narcissist"],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[
                "The Dark Side of Loving a Narcissist",
            ],
        )

        self.assertEqual(
            result["headline"],
            "The Dark Side of Loving a Narcissist",
        )

    def test_exact_previous_wording_is_never_selected_again(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Seven Things Narcissists Do When They Want Admiration",
                    "score": 10,
                },
                {
                    "family": "hidden_sign_interpretation",
                    "headline": "Six Signs a Narcissist Values Praise More Than Love",
                    "score": 8,
                },
            ],
            "selected_headline": (
                "Seven Things Narcissists Do When They Want Admiration"
            ),
        }

        result = _select_valid_result(
            data,
            ["SEVEN THINGS NARCISSISTS DO WHEN THEY WANT ADMIRATION!"],
            approved_headlines=[
                "Seven Things Narcissists Do When They Want Admiration",
                "Six Signs a Narcissist Values Praise More Than Love",
            ],
        )

        self.assertEqual(
            result["headline"],
            "Six Signs a Narcissist Values Praise More Than Love",
        )

    def test_fails_if_every_candidate_was_previously_used(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Seven Things Narcissists Do When They Want Admiration",
                    "score": 10,
                },
            ],
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                ["Seven Things Narcissists Do When They Want Admiration"],
                approved_headlines=[
                    "Seven Things Narcissists Do When They Want Admiration",
                ],
            )

    def test_fails_if_no_candidate_passes_editorial_evaluation(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Seven Things Narcissists Do When They Want Admiration",
                    "score": 10,
                },
            ],
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                [],
                approved_headlines=[],
            )

    def test_quote_like_candidate_is_rejected_even_if_approved(self):
        data = {
            "candidates": [
                {
                    "family": "relationship_consequences",
                    "headline": (
                        "Narcissistic Abuse Doesn't Just Hurt You; "
                        "It Steals Your Right To Trust Your Own Experience."
                    ),
                    "score": 10,
                },
            ],
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                [],
                approved_headlines=[
                    (
                        "Narcissistic Abuse Doesn't Just Hurt You; "
                        "It Steals Your Right To Trust Your Own Experience."
                    ),
                ],
            )

    def test_blue_words_must_appear_in_selected_headline(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Five Things a Narcissist Does After You Say No",
                    "score": 9,
                },
            ],
            "blue_words": [
                "Narcissist",
                "Say No",
                "unrelated phrase",
            ],
        }

        result = _select_valid_result(
            data,
            [],
            approved_headlines=[
                "Five Things a Narcissist Does After You Say No",
            ],
        )

        self.assertEqual(
            result["blue_words"],
            ["Narcissist", "Say No"],
        )

    def test_analysis_prompt_contains_complete_article(self):
        body = "This is the complete article text. " * 1500

        prompt = _build_analysis_prompt(
            "Article title",
            body,
        )

        self.assertIn(body, prompt)
        self.assertIn("COMPLETE ARTICLE BODY", prompt)

    def test_headline_prompt_contains_full_article_analysis_and_history(self):
        body = "Complete article content. " * 1500
        analysis = make_analysis()
        history = [
            "An older headline",
            "Another previously generated headline",
        ]

        prompt = _build_headline_prompt(
            title="Article title",
            body=body,
            analysis=analysis,
            recent_headlines=history,
        )

        self.assertIn(body, prompt)
        self.assertIn("Narcissistic relationship behaviour", prompt)
        self.assertIn("An older headline", prompt)
        self.assertIn("Another previously generated headline", prompt)

    def test_evaluation_prompt_contains_article_candidates_and_history(self):
        body = "Complete article content. " * 150
        analysis = make_analysis()
        candidates = [
            {
                "family": "behavioural_warning",
                "headline": "Seven Things Narcissists Do When They Want Admiration",
                "score": 9,
            },
        ]
        history = ["An older headline"]

        prompt = _build_evaluation_prompt(
            "Article title",
            body,
            analysis,
            candidates,
            history,
        )

        self.assertIn(body, prompt)
        self.assertIn("Seven Things Narcissists Do", prompt)
        self.assertIn("An older headline", prompt)

    def test_analysis_rejects_missing_central_argument(self):
        with patch(
            "modules.headline_gen._call_model",
            return_value={
                "central_subject": "Relationship behaviour",
                "central_argument": "",
            },
        ):
            with self.assertRaises(ValueError):
                _analyse_article(
                    "Article title",
                    "Article body",
                )

    def test_approval_matches_only_original_candidate_wording(self):
        candidates = [
            {
                "family": "behavioural_warning",
                "headline": "Seven Things Narcissists Do When They Want Admiration",
                "score": 8,
            },
        ]

        approved = _approved_candidate_headlines(
            candidates,
            [
                {
                    "headline": "A completely new headline invented by the evaluator",
                    "approved": True,
                    "score": 10,
                },
            ],
        )

        self.assertEqual(approved, [])

    def test_evaluator_rejects_scores_below_seven(self):
        candidates = [
            {
                "family": "behavioural_warning",
                "headline": "Seven Things Narcissists Do When They Want Admiration",
                "score": 8,
            },
        ]

        approved = _approved_candidate_headlines(
            candidates,
            [
                {
                    "headline": "Seven Things Narcissists Do When They Want Admiration",
                    "approved": True,
                    "score": 6,
                },
            ],
        )

        self.assertEqual(approved, [])

    def test_generation_uses_three_model_stages_and_complete_article(self):
        body = "A complete article paragraph with useful details. " * 120

        analysis = make_analysis()

        generated = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": (
                        "Seven Things Narcissists Do When They Want "
                        "You to Admire Them"
                    ),
                    "score": 9,
                    "angle": "Recognisable behaviours linked to admiration",
                },
                {
                    "family": "uncomfortable_truth",
                    "headline": (
                        "The Dark Side of Loving Someone Who Needs "
                        "to Be Worshipped"
                    ),
                    "score": 8,
                    "angle": "The uncomfortable cost of demanding worship",
                },
            ],
            "selected_headline": (
                "The Dark Side of Loving Someone Who Needs to Be Worshipped"
            ),
            "selected_family": "uncomfortable_truth",
            "blue_words": ["Narcissists", "Admire Them"],
            "emotion": "Recognition",
            "editorial_angle": "The article explains the demand for admiration.",
        }

        evaluations = {
            "evaluations": [
                {
                    "headline": (
                        "Seven Things Narcissists Do When They Want "
                        "You to Admire Them"
                    ),
                    "approved": True,
                    "score": 9,
                    "reason": "Clear numbered behavioural promise.",
                },
                {
                    "headline": (
                        "The Dark Side of Loving Someone Who Needs "
                        "to Be Worshipped"
                    ),
                    "approved": True,
                    "score": 8,
                    "reason": "Clear uncomfortable-truth promise.",
                },
            ],
        }

        with patch(
            "modules.headline_gen._call_model",
            side_effect=[analysis, generated, evaluations],
        ) as mocked_model:
            result = generate_headline(
                title="Why Narcissists Want Worship Instead of Love",
                body=body,
                recent_headlines=["An older headline"],
            )

        self.assertEqual(mocked_model.call_count, 3)

        analysis_prompt = mocked_model.call_args_list[0].args[1]
        generation_prompt = mocked_model.call_args_list[1].args[1]
        evaluation_prompt = mocked_model.call_args_list[2].args[1]

        self.assertIn(body, analysis_prompt)
        self.assertIn(body, generation_prompt)
        self.assertIn(body, evaluation_prompt)

        self.assertIn("An older headline", generation_prompt)
        self.assertIn("An older headline", evaluation_prompt)

        # The numbered candidate is preferred when it passes evaluation.
        self.assertEqual(
            result["headline"],
            "Seven Things Narcissists Do When They Want You to Admire Them",
        )
        self.assertEqual(result["family"], "behavioural_warning")
        self.assertIn("candidates", result)

    def test_generation_rejects_empty_article(self):
        with self.assertRaises(ValueError):
            generate_headline(
                title="Article title",
                body="",
            )


if __name__ == "__main__":
    unittest.main()
