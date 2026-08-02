import datetime as dt
import os
import re
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wp_auto_blog
from wp_auto_blog import Item, full_article_sections


class FullArticleSectionsTests(unittest.TestCase):
    def test_expands_short_source_material_into_longer_body(self) -> None:
        cluster = [
            Item(
                uid="1",
                source_name="Test Source",
                source_url="https://example.com",
                source_category="ai",
                source_quality=5,
                title="AI chips move closer to everyday devices",
                link="https://example.com/post",
                summary="A new chip reduces power usage and improves on-device processing for smaller devices.",
                published_at=dt.datetime.now(dt.timezone.utc),
                image_url=None,
            )
        ]

        body = full_article_sections(
            cluster,
            topic="AI chips move closer to everyday devices",
            categories=["ai", "gadgets"],
            source_count=1,
        )

        paragraph_count = body.count("<p>")
        text = re.sub(r"<[^>]+>", " ", body)
        word_count = len(text.split())

        self.assertGreaterEqual(paragraph_count, 4)
        self.assertGreaterEqual(word_count, 90)

    def test_article_enrichment_appends_sections_and_limits_tags(self) -> None:
        article = {
            "title": "AI assistants are changing everyday work",
            "excerpt": "A short excerpt about how AI assistants are reshaping workflows and attention.",
            "categories": ["Uncategorized", "Artificial Intelligence"],
            "tags": ["ai", "assistants", "productivity", "tools", "future", "work"],
            "html": "<p>Original article body.</p>",
        }

        enriched = wp_auto_blog.enrich_article_for_publication(article)

        self.assertNotIn("uncategorized", [value.lower() for value in enriched["categories"]])
        self.assertLessEqual(len(enriched["tags"]), 5)
        self.assertIn("Why This Matters", enriched["html"])
        self.assertIn("Chucky’s Analysis", enriched["html"])
        self.assertIn("Key Takeaways", enriched["html"])
        self.assertIn("Sources", enriched["html"])
        self.assertIn("meta_description", enriched)
        self.assertIn("seo_title", enriched)

    def test_article_enrichment_uses_polished_editorial_sections(self) -> None:
        article = {
            "title": "AI assistants are changing everyday work",
            "excerpt": "A short excerpt about how AI assistants are reshaping workflows and attention.",
            "categories": ["Artificial Intelligence"],
            "tags": ["ai", "assistants", "productivity"],
            "html": "<p>Original article body.</p>",
        }

        enriched = wp_auto_blog.enrich_article_for_publication(article)

        self.assertIn('<section class="editorial-section"', enriched["html"])
        self.assertIn("<h2>Why This Matters</h2>", enriched["html"])

    def test_publish_to_wordpress_uploads_hero_image_as_featured_media(self) -> None:
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as handle:
            handle.write(b"fake image")
            image_path = Path(handle.name)

        article = {
            "title": "Test post",
            "slug": "test-post",
            "excerpt": "A short excerpt",
            "html": '<p>Intro</p><figure><img src="__HERO_IMAGE_SRC__" alt="hero"></figure>',
            "categories": ["tech"],
            "tags": ["test"],
            "hero_image_path": str(image_path),
            "hero_image_alt": "A hero image",
        }

        captured: dict[str, object] = {}

        def fake_wp_request(path: str, payload: object = None, method: str = "GET") -> dict[str, object]:
            captured["path"] = path
            captured["payload"] = payload
            captured["method"] = method
            if path == "media":
                return {"id": 42, "source_url": "https://example.com/image.png"}
            return {"id": 99}

        from unittest.mock import patch

        with patch("wp_auto_blog.wp_request", side_effect=fake_wp_request):
            result = wp_auto_blog.publish_to_wordpress(article)

        self.assertEqual(captured["path"], "posts")
        self.assertEqual(captured["payload"]["featured_media"], 42)
        self.assertIn("https://example.com/image.png", str(captured["payload"]["content"]))
        self.assertEqual(result["id"], 99)

        image_path.unlink(missing_ok=True)

    def test_publish_to_wordpress_converts_more_tag_for_rest(self) -> None:
        article = {
            "title": "Test post",
            "slug": "test-post",
            "excerpt": "A short excerpt",
            "html": "<p>Teaser.</p>[more]<p>Body.</p>",
            "categories": ["tech"],
            "tags": ["test"],
        }

        captured: dict[str, object] = {}

        def fake_wp_request(path: str, payload: object = None, method: str = "GET") -> dict[str, object]:
            captured["path"] = path
            captured["payload"] = payload
            return {"id": 99}

        from unittest.mock import patch

        with patch("wp_auto_blog.wp_request", side_effect=fake_wp_request):
            wp_auto_blog.publish_to_wordpress(article)

        self.assertIn("<!--more-->", str(captured["payload"]["content"]))
        self.assertNotIn("[more]", str(captured["payload"]["content"]))

    def test_free_article_builds_fact_anchored_editorial_sections(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        cluster = [
            Item(
                uid="a",
                source_name="Alpha Reports",
                source_url="https://example.com",
                source_category="science",
                source_quality=5,
                title="New battery material doubles charging speed",
                link="https://example.com/post-a",
                summary="Researchers at MIT developed a solid-state battery that charges twice as fast and lasts 12 million cycles.",
                published_at=now,
            ),
            Item(
                uid="b",
                source_name="Beta News",
                source_url="https://example.org",
                source_category="science",
                source_quality=4,
                title="Battery breakthrough promises faster charging",
                link="https://example.org/post-b",
                summary="A university team reported that the new electrode design reduces charging time by 50 percent.",
                published_at=now,
            ),
        ]

        article = wp_auto_blog.free_article(cluster)

        self.assertLessEqual(len(article["tags"]), 5)
        self.assertFalse(any(tag.lower() == "uncategorized" for tag in article["tags"]))
        self.assertIn("Battery", article["tags"])
        self.assertIn("MIT", article["html"])
        self.assertIn("Why This Matters", article["html"])
        self.assertIn("Chucky’s Analysis", article["html"])
        self.assertIn("Key Takeaways", article["html"])
        self.assertIn("Sources", article["html"])
        self.assertIn("href=\"https://example.com/post-a\"", article["html"])

        analysis_section = article["html"][article["html"].index("Chucky’s Analysis"):]
        analysis_text = re.sub(r"<[^>]+>", " ", analysis_section)
        analysis_word_count = len(re.sub(r"\s+", " ", analysis_text).split())
        self.assertGreaterEqual(analysis_word_count, 200)

    def test_deliver_article_falls_back_to_email_without_rest_credentials(self) -> None:
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "WP_POST_METHOD": "rest",
                "WP_BASE_URL": "",
                "WP_USERNAME": "",
                "WP_APPLICATION_PASSWORD": "",
            },
            clear=False,
        ):
            article = {
                "title": "Fallback test",
                "slug": "fallback-test",
                "excerpt": "",
                "html": "<p>Body</p>",
                "categories": ["tech"],
                "tags": ["test"],
            }

            with patch("wp_auto_blog.send_article_by_email", return_value={"status": "sent"}) as send_email:
                result = wp_auto_blog.deliver_article(article)

        send_email.assert_called_once()
        self.assertEqual(result["status"], "sent")

    def test_deliver_article_falls_back_to_email_when_rest_publish_raises(self) -> None:
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "WP_POST_METHOD": "rest",
                "WP_BASE_URL": "https://example.test",
                "WP_USERNAME": "user",
                "WP_APPLICATION_PASSWORD": "bad password",
            },
            clear=False,
        ):
            article = {
                "title": "Fallback test",
                "slug": "fallback-test",
                "excerpt": "",
                "html": "<p>Body</p>",
                "categories": ["tech"],
                "tags": ["test"],
            }

            with patch("wp_auto_blog.publish_to_wordpress", side_effect=RuntimeError("401 unauthorized")):
                with patch("wp_auto_blog.send_article_by_email", return_value={"status": "sent"}) as send_email:
                    result = wp_auto_blog.deliver_article(article)

        send_email.assert_called_once()
        self.assertEqual(result["status"], "sent")

    def test_wp_request_uses_public_api_base_when_supplied(self) -> None:
        from unittest.mock import MagicMock, patch

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            return FakeResponse()

        with patch.dict(
            os.environ,
            {
                "WP_BASE_URL": "https://public-api.wordpress.com/wp/v2/sites/chuckyscarnage.tech.blog",
                "WP_USERNAME": "user",
                "WP_APPLICATION_PASSWORD": "app pass",
            },
            clear=False,
        ):
            with patch("wp_auto_blog.urllib.request.urlopen", side_effect=fake_urlopen):
                wp_auto_blog.wp_request("posts")

        self.assertEqual(
            captured["url"],
            "https://public-api.wordpress.com/wp/v2/sites/chuckyscarnage.tech.blog/posts",
        )

    def test_wp_request_appends_wp_json_for_site_root_base(self) -> None:
        from unittest.mock import patch

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            return FakeResponse()

        with patch.dict(
            os.environ,
            {
                "WP_BASE_URL": "https://example.test",
                "WP_USERNAME": "user",
                "WP_APPLICATION_PASSWORD": "app pass",
            },
            clear=False,
        ):
            with patch("wp_auto_blog.urllib.request.urlopen", side_effect=fake_urlopen):
                wp_auto_blog.wp_request("posts")

        self.assertEqual(captured["url"], "https://example.test/wp-json/wp/v2/posts")


if __name__ == "__main__":
    unittest.main()
