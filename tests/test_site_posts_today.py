import datetime as dt
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wp_auto_blog


class SitePostsTodayTests(unittest.TestCase):
    def test_counts_paginated_results(self) -> None:
        pages = iter([[{"id": i} for i in range(100)], [{"id": 100}]])
        with patch("wp_auto_blog.wp_request", side_effect=lambda *a, **k: next(pages)):
            self.assertEqual(wp_auto_blog.site_posts_today(), 101)

    def test_returns_zero_for_no_posts(self) -> None:
        with patch("wp_auto_blog.wp_request", return_value=[]):
            self.assertEqual(wp_auto_blog.site_posts_today(), 0)

    def test_returns_minus_one_on_api_failure(self) -> None:
        def boom(*args, **kwargs) -> None:
            raise RuntimeError("network down")

        with patch("wp_auto_blog.wp_request", side_effect=boom):
            self.assertEqual(wp_auto_blog.site_posts_today(), -1)

    def test_queries_since_utc_midnight(self) -> None:
        captured: dict[str, str] = {}

        def capture(path: str, *args, **kwargs) -> list:
            captured["path"] = path
            return []

        with patch("wp_auto_blog.wp_request", side_effect=capture):
            wp_auto_blog.site_posts_today()
        after = None
        for part in captured["path"].split("&"):
            if "after=" in part:
                after = part.split("after=", 1)[1]
        self.assertIsNotNone(after)
        parsed = dt.datetime.fromisoformat(after.replace("+00:00", ""))
        self.assertEqual((parsed.hour, parsed.minute, parsed.second), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
