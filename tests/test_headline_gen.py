import unittest
from unittest.mock import patch

from modules.headline_gen import (
    ANALYSIS_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    _analyse_article,
    _build_analysis_prompt,
    _build_headline_prompt,
    _parse_response,
    _select_valid_result,
    generate_headline,
)


class HeadlineFrameworkTests(unittest.TestCase):

    def test_all_reference_families_are_explicit(self):
        for family in (
            "BEHAVIOURAL WARNING / INVENTORY",
            "HIDDEN-SIGN INTERPRETATION",
            "CONDITIONAL REVELATION",
            "UNCOMFORTABLE TRUTH",
            "HARSH TRUTHS",
            "UNEXPECTED REVERSAL",
            "RELATIONSHIP CONSEQUENCES",
            "DIRECT INSTRUCTION / DISCOVERY",
        ):
            self.assertIn(family, SYSTEM_PROMPT)

    def test_all_curiosity_mechanisms_are_explicit(self):
        for mechanism in (
            "RECOGNITION CURIOSITY",
            "INTERPRETATION CURIOSITY",
            "DISCOVERY CURIOSITY",
            "CONSEQUENCE CURIOSITY",
            "FORBIDDEN-TRUTH CURIOSITY",
        ):
            self.assertIn(mechanism, SYSTEM_PROMPT)

    def test_research_examples_are_included(self):
        examples = (
            "7 Things Parents Should Never Do in Front of Their Children",
            "9 Things Cheaters Always Do on Their Phones",
            "8 Signs Your Husband Enjoys Hurting You",
            "7 Signs You're in a Parenting Marriage Without Even Realizing It",
            "When a Man Hates His Wife, He Says These 7 Things",
            "The Dark Side of Marriage No One Talks About",
            "6 Harsh Truths About Marriage",
            "If You Notice These 5 Things in Your Husband, You're Emotionally Intelligent",
        )

        for example in examples:
            self.assertIn(example, SYSTEM_PROMPT)

    def test_framework_does_not_force_four_families(self):
        self.assertIn(
            "Do not force candidates into a minimum number of headline families",
            SYSTEM_PROMPT,
        )

    def test_numbers_are_optional(self):
        self.assertIn(
            "Numbers are optional, not a default requirement",
            SYSTEM_PROMPT,
        )

    def test_article_analysis_is_separate_from_headline_writing(self):
        self.assertIn("Do not write headlines in this stage", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("central_argument", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("observable_behaviours", ANALYSIS_SYSTEM_PROMPT)
        self.assertIn("unsupported_claims_to_avoid", ANALYSIS_SYSTEM_PROMPT)

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

    def test_selected_headline_must_be_from_candidates(self):
        data = {
            "candidates": [
                {
                    "family": "hidden_sign_interpretation",
                    "headline": "Six signs a narcissist is punishing your boundaries",
                    "score": 8,
                },
                {
                    "family": "behavioural_warning",
                    "headline": "Five things a narcissist does after you say no",
                    "score": 9,
                },
            ],
            "selected_headline": "A made-up headline",
            "blue_words": ["say no"],
        }

        result = _select_valid_result(data, [])

        self.assertEqual(
            result["headline"],
            "Five things a narcissist does after you say no",
        )

    def test_recent_headline_is_not_selected_again(self):
        data = {
            "candidates": [
                {
                    "family": "hidden_sign_interpretation",
                    "headline": "Six signs a narcissist is punishing your boundaries",
                    "score": 10,
                },
                {
                    "family": "behavioural_warning",
                    "headline": "Five things a narcissist does after you say no",
                    "score": 8,
                },
            ],
            "selected_headline": (
                "Six signs a narcissist is punishing your boundaries"
            ),
            "blue_words": ["punishing", "boundaries"],
        }

        result = _select_valid_result(
            data,
            ["Six signs a narcissist is punishing your boundaries"],
        )

        self.assertEqual(
            result["headline"],
            "Five things a narcissist does after you say no",
        )

    def test_fails_if_every_candidate_is_recent(self):
        data = {
            "candidates": [
                {
                    "family": "hidden_sign_interpretation",
                    "headline": "Six signs a narcissist is punishing your boundaries",
                    "score": 10,
                },
            ],
            "selected_headline": (
                "Six signs a narcissist is punishing your boundaries"
            ),
        }

        with self.assertRaises(ValueError):
            _select_valid_result(
                data,
                ["Six signs a narcissist is punishing your boundaries"],
            )

    def test_blue_words_must_appear_in_selected_headline(self):
        data = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Five things a narcissist does after you say no",
                    "score": 9,
                },
            ],
            "selected_headline": (
                "Five things a narcissist does after you say no"
            ),
            "blue_words": [
                "narcissist",
                "say no",
                "unrelated phrase",
            ],
        }

        result = _select_valid_result(data, [])

        self.assertEqual(
            result["blue_words"],
            ["narcissist", "say no"],
        )

    def test_analysis_prompt_contains_complete_article(self):
        body = (
            "This is the complete article text. "
            * 1500
        )

        prompt = _build_analysis_prompt(
            "Article title",
            body,
        )

        self.assertIn(body, prompt)
        self.assertIn("COMPLETE ARTICLE BODY", prompt)

    def test_headline_prompt_contains_complete_article_and_analysis(self):
        body = "Complete article content. " * 1500

        analysis = {
            "central_subject": "Relationship behaviour",
            "central_argument": "Repeated behaviour can undermine trust.",
            "key_points": ["Repeated denial", "Blame shifting"],
        }

        prompt = _build_headline_prompt(
            title="Article title",
            body=body,
            analysis=analysis,
            recent_headlines=["An older headline"],
        )

        self.assertIn(body, prompt)
        self.assertIn("Relationship behaviour", prompt)
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

    def test_generation_uses_two_model_stages_and_full_article(self):
        body = "A complete article paragraph. " * 1500

        analysis = {
            "central_subject": "Relationship behaviour",
            "central_argument": "Repeated behaviour can undermine trust.",
            "target_reader": "People in difficult relationships",
            "reader_problem": "Understanding confusing behaviour",
            "main_tension": "Conflicting accounts of events",
            "key_points": ["Denial", "Blame shifting"],
            "observable_behaviours": ["Repeated denial"],
            "consequences": ["Loss of confidence"],
            "surprising_insights": ["The argument shifts away from the event"],
            "practical_actions": [],
            "strongest_headline_angles": ["Recognisable patterns"],
            "unsupported_claims_to_avoid": [],
            "usable_numbered_material": [],
            "article_type": "Explanation",
        }

        headline_result = {
            "candidates": [
                {
                    "family": "behavioural_warning",
                    "headline": "Five ways repeated denial changes a relationship",
                    "score": 9,
                },
                {
                    "family": "uncomfortable_truth",
                    "headline": "The hidden cost of constantly defending your memory",
                    "score": 8,
                },
            ],
            "selected_headline": (
                "Five ways repeated denial changes a relationship"
            ),
            "selected_family": "behavioural_warning",
            "blue_words": ["repeated denial"],
            "emotion": "Recognition",
            "editorial_angle": "It connects a recognisable behaviour to its cost.",
        }

        with patch(
            "modules.headline_gen._call_model",
            side_effect=[analysis, headline_result],
        ) as mocked_model:
            result = generate_headline(
                title="Understanding Repeated Relationship Patterns",
                body=body,
            )

        self.assertEqual(mocked_model.call_count, 2)

        first_prompt = mocked_model.call_args_list[0].args[1]
        second_prompt = mocked_model.call_args_list[1].args[1]

        self.assertIn(body, first_prompt)
        self.assertIn(body, second_prompt)

        self.assertEqual(
            result["headline"],
            "Five ways repeated denial changes a relationship",
        )
        self.assertEqual(
            result["family"],
            "behavioural_warning",
        )
        self.assertIn("candidates", result)

    def test_generation_rejects_empty_article(self):
        with self.assertRaises(ValueError):
            generate_headline(
                title="Article title",
                body="",
            )


if __name__ == "__main__":
    unittest.main()
