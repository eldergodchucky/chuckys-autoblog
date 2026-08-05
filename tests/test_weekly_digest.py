import datetime as dt
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import weekly_digest


class BuildDigestArticleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = dt.date(2026, 8, 1)
        self.end = dt.date(2026, 8, 7)
        self.category_names = {1: "Uncategorized", 173: "Science", 318: "Tech"}
        self.posts = [
            {
                "id": 1,
                "date": "2026-08-05T10:00:00",
                "title": {"rendered": "Rocket <em>launch</em> succeeds"},
                "link": "https://example.test/p1",
                "excerpt": {"rendered": "<p>Short summary of the rocket story.</p>"},
                "categories": [173],
            },
            {
                "id": 2,
                "date": "2026-08-04T10:00:00",
                "title": {"rendered": "Chip design <strong>breakthrough</strong>"},
                "link": "https://example.test/p2",
                "excerpt": {"rendered": "<p>Another summary.</p>"},
                "categories": [318],
            },
            {
                "id": 3,
                "date": "2026-08-03T10:00:00",
                "title": {"rendered": "Uncategorized story"},
                "link": "https://example.test/p3",
                "excerpt": {"rendered": ""},
                "categories": [1],
            },
        ]

    def test_builds_article_with_grouped_sections(self) -> None:
        article = weekly_digest.build_digest_article(self.posts, self.category_names, self.start, self.end)
        self.assertIsNotNone(article)
        self.assertIn("Science", article["html"])
        self.assertIn("Tech", article["html"])
        self.assertIn('href="https://example.test/p1"', article["html"])
        self.assertEqual(article["slug"], "weekly-digest-2026-08-07")
        self.assertIn("3 articles went live", article["html"])
        self.assertIn("Aug 1 - Aug 7, 2026", article["title"])

    def test_returns_none_below_minimum_posts(self) -> None:
        article = weekly_digest.build_digest_article(self.posts[:2], self.category_names, self.start, self.end)
        self.assertIsNone(article)

    def test_strips_html_from_titles(self) -> None:
        article = weekly_digest.build_digest_article(self.posts, self.category_names, self.start, self.end)
        self.assertNotIn("Rocket <em>launch</em>", article["html"])
        self.assertIn("Rocket launch succeeds", article["html"])
        self.assertNotIn("Short summary", article["html"])

    def test_prefers_most_recent_posts_when_capped(self) -> None:
        posts = [
            {
                "id": i,
                "date": f"2026-08-0{day}T10:00:00",
                "title": {"rendered": f"Post {i}"},
                "link": f"https://example.test/{i}",
                "excerpt": {"rendered": ""},
                "categories": [173],
            }
            for i, day in [(1, 5), (2, 5), (3, 4), (4, 4), (5, 3), (6, 3)]
        ]
        with patch.dict(os.environ, {"DIGEST_MAX_ITEMS": "4"}):
            article = weekly_digest.build_digest_article(posts, self.category_names, self.start, self.end)
        self.assertEqual(article["html"].count("<li>"), 4)
        self.assertIn("Post 1", article["html"])
        self.assertIn("Post 2", article["html"])
        self.assertNotIn("Post 6", article["html"])

    def test_unknown_categories_group_under_other(self) -> None:
        mystery = {
            "id": 9,
            "date": "2026-08-05T10:00:00",
            "title": {"rendered": "Mystery post"},
            "link": "https://example.test/p9",
            "excerpt": {"rendered": ""},
            "categories": [9999],
        }
        article = weekly_digest.build_digest_article([mystery] * 3, self.category_names, self.start, self.end)
        self.assertIn("Other", article["html"])
        self.assertIn("3 articles went live", article["html"])

    def test_limits_total_items(self) -> None:
        posts = [
            {
                "id": i,
                "date": "2026-08-05T10:00:00",
                "title": {"rendered": f"Post {i}"},
                "link": f"https://example.test/{i}",
                "excerpt": {"rendered": ""},
                "categories": [173],
            }
            for i in range(20)
        ]
        with patch.dict(os.environ, {"DIGEST_MAX_ITEMS": "5"}):
            article = weekly_digest.build_digest_article(posts, self.category_names, self.start, self.end)
        self.assertEqual(article["html"].count("<li>"), 5)

    def test_deduplicates_same_title_posts(self) -> None:
        base = {
            "id": 1,
            "date": "2026-08-05T10:00:00",
            "title": {"rendered": "Dementia After Age 90: Study Clarifies Who May Be at Higher Risk"},
            "link": "https://example.test/p1",
            "excerpt": {"rendered": ""},
            "categories": [173],
        }
        duplicate = dict(base, id=2, link="https://example.test/p2")
        other = dict(base, id=3, link="https://example.test/p3", title={"rendered": "Unrelated story"})
        article = weekly_digest.build_digest_article([base, duplicate, other], self.category_names, self.start, self.end)
        self.assertIsNotNone(article)
        self.assertEqual(article["html"].count("<li>"), 2)

    def test_prefers_core_category_for_grouping(self) -> None:
        post = {
            "id": 1,
            "date": "2026-08-05T10:00:00",
            "title": {"rendered": "Core category wins"},
            "link": "https://example.test/p1",
            "excerpt": {"rendered": ""},
            "categories": [7682, 337],
        }
        with patch.dict(self.category_names, {7682: "Health News", 337: "Health"}):
            article = weekly_digest.build_digest_article([post] * 3, self.category_names, self.start, self.end)
        self.assertIn("<h2>Health</h2>", article["html"])
        self.assertNotIn("Health News</h2>", article["html"])


class FetchRecentPostsTests(unittest.TestCase):
    def test_paginates_until_short_page(self) -> None:
        pages = iter([[{"id": 1} for _ in range(100)], [{"id": 101}]])
        with patch("weekly_digest.wp_request", side_effect=lambda *args, **kwargs: next(pages)):
            posts = weekly_digest.fetch_recent_posts(dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(len(posts), 101)

    def test_stops_on_empty_page(self) -> None:
        with patch("weekly_digest.wp_request", return_value=[]):
            posts = weekly_digest.fetch_recent_posts(dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(posts, [])


class CategoryNameMapTests(unittest.TestCase):
    def test_maps_ids_from_api_response(self) -> None:
        with patch("weekly_digest.wp_request", return_value=[{"id": 173, "name": "Science"}, {"id": 318, "name": "Tech"}]):
            mapping = weekly_digest.category_name_map()
        self.assertEqual(mapping, {173: "Science", 318: "Tech"})

    def test_ignores_unnamed_categories(self) -> None:
        with patch("weekly_digest.wp_request", return_value=[{"id": 1, "name": " "}, {"id": 2}]):
            mapping = weekly_digest.category_name_map()
        self.assertEqual(mapping, {})


if __name__ == "__main__":
    unittest.main()
