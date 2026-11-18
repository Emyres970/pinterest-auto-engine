import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules import tracker


class TrackerHeadlineHistoryTests(unittest.TestCase):

    def _write_tracker(self, path, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=tracker.HEADERS,
            )
            writer.writeheader()

            for row in rows:
                writer.writerow(row)

    def test_reads_all_headlines_for_one_post_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            self._write_tracker(path, [
                {
                    "post_index": 4,
                    "headline": "First headline",
                    "status": "success",
                },
                {
                    "post_index": 5,
                    "headline": "Other post",
                    "status": "success",
                },
                {
                    "post_index": 4,
                    "headline": "Second headline",
                    "status": "generated",
                },
                {
                    "post_index": 4,
                    "headline": "Third headline",
                    "status": "failed_after_generation",
                },
            ])

            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(
                    tracker.get_recent_headlines(4),
                    [
                        "Third headline",
                        "Second headline",
                        "First headline",
                    ],
                )

    def test_history_is_not_limited_to_thirty_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            rows = [
                {
                    "post_index": 12,
                    "headline": f"Unique headline number {i}",
                    "status": "generated",
                }
                for i in range(1, 46)
            ]

            self._write_tracker(path, rows)

            with patch.object(tracker, "TRACKER_FILE", path):
                history = tracker.get_recent_headlines(12)

            self.assertEqual(len(history), 45)
            self.assertEqual(
                history[0],
                "Unique headline number 45",
            )
            self.assertEqual(
                history[-1],
                "Unique headline number 1",
            )

    def test_optional_limit_remains_backwards_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            self._write_tracker(path, [
                {
                    "post_index": 2,
                    "headline": headline,
                    "status": "success",
                }
                for headline in ("One", "Two", "Three")
            ])

            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(
                    tracker.get_recent_headlines(2, limit=2),
                    ["Three", "Two"],
                )

    def test_duplicate_headlines_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            self._write_tracker(path, [
                {
                    "post_index": 7,
                    "headline": "Seven Things Narcissists Do",
                    "status": "generated",
                },
                {
                    "post_index": 7,
                    "headline": "Seven Things Narcissists Do",
                    "status": "success",
                },
            ])

            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(
                    tracker.get_recent_headlines(7),
                    ["Seven Things Narcissists Do"],
                )

    def test_other_posts_do_not_leak_into_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            self._write_tracker(path, [
                {
                    "post_index": 12,
                    "headline": "Post twelve headline",
                    "status": "generated",
                },
                {
                    "post_index": 13,
                    "headline": "Post thirteen headline",
                    "status": "success",
                },
            ])

            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(
                    tracker.get_recent_headlines(12),
                    ["Post twelve headline"],
                )

    def test_generated_status_does_not_advance_posting_rotation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            self._write_tracker(path, [
                {
                    "post_index": 12,
                    "headline": "Generated but not posted",
                    "status": "generated",
                },
                {
                    "post_index": 11,
                    "headline": "Previously posted",
                    "status": "success",
                },
            ])

            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(
                    tracker._get_last_posted_index(),
                    11,
                )

    def test_log_result_appends_generated_headline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"

            with patch.object(tracker, "TRACKER_FILE", path):
                tracker.log_result(
                    12,
                    "Article title",
                    "https://example.com/article",
                    "Seven Things Narcissists Do",
                    "",
                    "generated",
                )

                history = tracker.get_recent_headlines(12)

            self.assertEqual(
                history,
                ["Seven Things Narcissists Do"],
            )

            with path.open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["status"], "generated")
            self.assertEqual(
                rows[0]["headline"],
                "Seven Things Narcissists Do",
            )


if __name__ == "__main__":
    unittest.main()
