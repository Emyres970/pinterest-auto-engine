import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules import tracker


class TrackerHeadlineHistoryTests(unittest.TestCase):
    def test_reads_recent_successful_headlines_for_one_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=tracker.HEADERS)
                writer.writeheader()
                writer.writerow({"post_index": 4, "headline": "First headline", "status": "success"})
                writer.writerow({"post_index": 5, "headline": "Other post", "status": "success"})
                writer.writerow({"post_index": 4, "headline": "Failed headline", "status": "failed"})
                writer.writerow({"post_index": 4, "headline": "Second headline", "status": "success"})
            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(
                    tracker.get_recent_headlines(4, limit=10),
                    ["Second headline", "First headline"],
                )

    def test_history_limit_returns_newest_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=tracker.HEADERS)
                writer.writeheader()
                for headline in ("One", "Two", "Three"):
                    writer.writerow({"post_index": 2, "headline": headline, "status": "success"})
            with patch.object(tracker, "TRACKER_FILE", path):
                self.assertEqual(tracker.get_recent_headlines(2, limit=2), ["Three", "Two"])


if __name__ == "__main__":
    unittest.main()
