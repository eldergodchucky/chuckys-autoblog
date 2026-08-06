"""Tests for the failover freshness logic (RSS vs WordPress public API)."""

from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wp_failover_publish as failover  # noqa: E402


def make_post(minutes_ago: int, source: str) -> dict:
    published = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    return {
        "title": f"post-{minutes_ago}",
        "link": "https://chuckyscarnage.tech.blog/x",
        "published_at": published,
        "published_at_raw": published.isoformat(),
        "freshness_source": source,
    }


class FetchLatestPostTests(unittest.TestCase):
    @mock.patch.object(failover, "fetch_latest_post_from_wp_api")
    @mock.patch.object(failover, "fetch_latest_post_from_rss")
    def test_newest_source_wins_when_rss_stale(self, rss, api):
        rss.return_value = make_post(300, "rss")
        api.return_value = make_post(3, "wordpress_public_api")
        result = failover.fetch_latest_post("https://example.com/feed/")
        self.assertEqual(result["freshness_source"], "wordpress_public_api")
        self.assertEqual(result["title"], "post-3")
        self.assertEqual(result.get("rss_error", ""), "")

    @mock.patch.object(failover, "fetch_latest_post_from_wp_api")
    @mock.patch.object(failover, "fetch_latest_post_from_rss")
    def test_rss_wins_when_newer_than_api(self, rss, api):
        rss.return_value = make_post(2, "rss")
        api.return_value = make_post(300, "wordpress_public_api")
        result = failover.fetch_latest_post("https://example.com/feed/")
        self.assertEqual(result["freshness_source"], "rss")
        self.assertEqual(result["title"], "post-2")

    @mock.patch.object(failover, "fetch_latest_post_from_wp_api")
    @mock.patch.object(failover, "fetch_latest_post_from_rss")
    def test_records_rss_error_when_api_wins(self, rss, api):
        rss.side_effect = RuntimeError("feed is broken")
        api.return_value = make_post(1, "wordpress_public_api")
        result = failover.fetch_latest_post("https://example.com/feed/")
        self.assertEqual(result["freshness_source"], "wordpress_public_api")
        self.assertEqual(result["rss_error"], "feed is broken")

    @mock.patch.object(failover, "fetch_latest_post_from_wp_api")
    @mock.patch.object(failover, "fetch_latest_post_from_rss")
    def test_raises_when_both_sources_fail(self, rss, api):
        rss.side_effect = RuntimeError("feed down")
        api.side_effect = RuntimeError("api down")
        with self.assertRaises(RuntimeError):
            failover.fetch_latest_post("https://example.com/feed/")

    @mock.patch.object(failover, "fetch_latest_post_from_wp_api")
    @mock.patch.object(failover, "fetch_latest_post_from_rss")
    def test_single_source_works_alone(self, rss, api):
        api.side_effect = RuntimeError("api down")
        rss.return_value = make_post(10, "rss")
        result = failover.fetch_latest_post("https://example.com/feed/")
        self.assertEqual(result["freshness_source"], "rss")
        self.assertEqual(result["api_error"], "api down")


if __name__ == "__main__":
    unittest.main()
