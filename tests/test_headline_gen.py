import unittest

from modules.headline_gen import _parse_response, _select_valid_result, SYSTEM_PROMPT


class HeadlineFrameworkTests(unittest.TestCase):
    def test_reference_families_are_explicit(self):
        for family in (
            "BEHAVIOURAL INVENTORY",
            "DIAGNOSTIC SIGNS",
            "CONDITIONAL REVELATION",
            "UNCOMFORTABLE TRUTH",
            "COUNTERINTUITIVE INTERPRETATION",
            "CONSEQUENCE / CAUSE AND EFFECT",
            "PRACTICAL RESPONSE",
        ):
            self.assertIn(family, SYSTEM_PROMPT)

    def test_parse_json_fenced_response(self):
        parsed = _parse_response('```json\n{"selected_headline":"A useful headline"}\n```')
        self.assertEqual(parsed["selected_headline"], "A useful headline")

    def test_selected_headline_must_be_from_candidates(self):
        data = {
            "candidates": [
                {"family": "diagnostic_signs", "headline": "Six signs a narcissist is punishing your boundaries", "score": 8},
                {"family": "behavioural_inventory", "headline": "Five things a narcissist does after you say no", "score": 9},
            ],
            "selected_headline": "A made-up headline",
            "blue_words": ["say no"],
        }
        result = _select_valid_result(data, [])
        self.assertEqual(result["headline"], "Five things a narcissist does after you say no")

    def test_recent_headline_is_not_selected_again(self):
        data = {
            "candidates": [
                {"family": "diagnostic_signs", "headline": "Six signs a narcissist is punishing your boundaries", "score": 10},
                {"family": "behavioural_inventory", "headline": "Five things a narcissist does after you say no", "score": 8},
            ],
            "selected_headline": "Six signs a narcissist is punishing your boundaries",
            "blue_words": ["punishing", "boundaries"],
        }
        result = _select_valid_result(data, ["Six signs a narcissist is punishing your boundaries"])
        self.assertEqual(result["headline"], "Five things a narcissist does after you say no")

    def test_fails_if_every_candidate_is_recent(self):
        data = {
            "candidates": [
                {"family": "diagnostic_signs", "headline": "Six signs a narcissist is punishing your boundaries", "score": 10},
            ],
            "selected_headline": "Six signs a narcissist is punishing your boundaries",
        }
        with self.assertRaises(ValueError):
            _select_valid_result(data, ["Six signs a narcissist is punishing your boundaries"])


if __name__ == "__main__":
    unittest.main()
