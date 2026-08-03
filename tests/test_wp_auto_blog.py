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
        self.assertNotIn("__HERO_IMAGE_SRC__", str(captured["payload"]["content"]))
        self.assertNotIn("https://example.com/image.png", str(captured["payload"]["content"]))
        self.assertEqual(result["id"], 99)

        image_path.unlink(missing_ok=True)

    def test_publish_to_wordpress_strips_inline_hero_when_featured_media_set(self) -> None:
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as handle:
            handle.write(b"fake image")
            image_path = Path(handle.name)

        article = {
            "title": "Test post",
            "slug": "test-post",
            "excerpt": "A short excerpt",
            "html": '<p>Intro</p><figure class="wp-block-image size-large"><img src="__HERO_IMAGE_SRC__" alt="hero"></figure><p>Body.</p>',
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
            wp_auto_blog.publish_to_wordpress(article)

        content = str(captured["payload"]["content"])
        self.assertNotIn("<figure", content)
        self.assertNotIn("__HERO_IMAGE_SRC__", content)
        self.assertNotIn("https://example.com/image.png", content)
        self.assertIn("<p>Intro</p>", content)
        self.assertIn("<p>Body.</p>", content)

        image_path.unlink(missing_ok=True)

    def test_publish_to_wordpress_strips_placeholder_when_hero_upload_fails(self) -> None:
        article = {
            "title": "Test post",
            "slug": "test-post",
            "excerpt": "A short excerpt",
            "html": '<p>Intro</p><figure class="wp-block-image size-large"><img src="__HERO_IMAGE_SRC__" alt="hero"></figure><p>Body.</p>',
            "categories": ["tech"],
            "tags": ["test"],
        }

        captured: dict[str, object] = {}

        def fake_wp_request(path: str, payload: object = None, method: str = "GET") -> dict[str, object]:
            captured["path"] = path
            captured["payload"] = payload
            captured["method"] = method
            if path == "media":
                raise RuntimeError("upload boom")
            return {"id": 99}

        from unittest.mock import patch

        with patch("wp_auto_blog.wp_request", side_effect=fake_wp_request):
            wp_auto_blog.publish_to_wordpress(article)

        content = str(captured["payload"]["content"])
        self.assertNotIn("__HERO_IMAGE_SRC__", content)
        self.assertNotIn("featured_media", captured["payload"])

        image_path = None

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

    def test_wp_request_uses_bearer_token_when_wpcom_access_token_set(self) -> None:
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
            captured["auth"] = request.get_header("Authorization")
            return FakeResponse()

        with patch.dict(
            os.environ,
            {
                "WP_BASE_URL": "https://public-api.wordpress.com/wp/v2/sites/chuckyscarnage.tech.blog",
                "WP_USERNAME": "user",
                "WP_APPLICATION_PASSWORD": "app pass",
                "WP_COM_ACCESS_TOKEN": "secret-token",
            },
            clear=False,
        ):
            with patch("wp_auto_blog.urllib.request.urlopen", side_effect=fake_urlopen):
                wp_auto_blog.wp_request("posts")

        self.assertEqual(captured["auth"], "Bearer secret-token")

    def test_wpcom_oauth_setup_exchanges_token_and_saves_env(self) -> None:
        import tempfile
        from unittest.mock import patch

        import wpcom_oauth_setup

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("WPCOM_CLIENT_ID=cid\nWPCOM_CLIENT_SECRET=cs\n", encoding="utf-8")

            response = {
                "access_token": "tok123",
                "blog_id": 204403701,
                "blog_url": "https://chuckyscarnage.tech.blog",
                "expires_in": 3600,
                "refresh_token": "refreshtok",
            }

            def fake_urlopen(request, timeout):
                class FakeResponse:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        return False

                    def read(self):
                        import json
                        return json.dumps(response).encode("utf-8")

                return FakeResponse()

            with patch.dict(
                os.environ,
                {
                    "WPCOM_CLIENT_ID": "cid",
                    "WPCOM_CLIENT_SECRET": "cs",
                    "WP_USERNAME": "eldergodchucky",
                    "WP_APPLICATION_PASSWORD": "app pass",
                },
                clear=False,
            ):
                with patch("sys.argv", ["wpcom_oauth_setup.py"]):
                    with patch("wpcom_oauth_setup.ENV_PATH", env_path):
                        with patch("wpcom_oauth_setup.urllib.request.urlopen", side_effect=fake_urlopen):
                            wpcom_oauth_setup.main()

            content = env_path.read_text(encoding="utf-8")
            self.assertIn("WP_COM_ACCESS_TOKEN=tok123", content)
            self.assertIn("WP_COM_REFRESH_TOKEN=refreshtok", content)

    def test_wp_existing_post_matches_by_title_when_slug_differs(self) -> None:
        from unittest.mock import patch

        hits = []

        def fake_urlopen(request, timeout):
            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self):
                    import json
                    return json.dumps(hits).encode("utf-8")

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
                hits[:] = [{"id": 1234, "status": "publish", "slug": "foo-2", "title": {"rendered": "Foo bar"}}]
                found = wp_auto_blog.wp_existing_post("foo", "Foo bar")
                self.assertIsNotNone(found)
                self.assertEqual(found["id"], 1234)

                hits[:] = [{"id": 1234, "status": "publish", "slug": "foo-2", "title": {"rendered": "Foo bar"}}]
                found = wp_auto_blog.wp_existing_post("other-slug", "Completely different title")
                self.assertIsNone(found)

                hits[:] = []
                found = wp_auto_blog.wp_existing_post("no-results", "Nothing here")
                self.assertIsNone(found)

    def test_wp_existing_post_failsafe_returns_none_on_network_error(self) -> None:
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "WP_BASE_URL": "https://example.test",
                "WP_USERNAME": "user",
                "WP_APPLICATION_PASSWORD": "bad password",
            },
            clear=False,
        ):
            with patch("wp_auto_blog.wp_request", side_effect=RuntimeError("boom")):
                found = wp_auto_blog.wp_existing_post("slug", "Title")
        self.assertIsNone(found)

    def test_publish_to_wordpress_skips_existing_post(self) -> None:
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "WP_POST_METHOD": "rest",
                "WP_BASE_URL": "https://public-api.wordpress.com/wp/v2/sites/chuckyscarnage.tech.blog",
                "WP_USERNAME": "user",
                "WP_APPLICATION_PASSWORD": "app pass",
                "POST_STATUS": "publish",
                "AUTO_PUBLISH_CONFIRM": "I_UNDERSTAND_POSTS_GO_LIVE",
            },
            clear=False,
        ):
            article = {
                "title": "Foo bar",
                "slug": "foo",
                "excerpt": "",
                "html": "<p>Body</p>",
                "categories": ["tech"],
                "tags": ["test"],
            }
            existing = {"id": 1234, "status": "publish", "slug": "foo", "title": {"rendered": "Foo bar"}}
            with patch("wp_auto_blog.wp_existing_post", return_value=existing):
                with patch("wp_auto_blog.wp_term_ids", return_value=[]):
                    result = wp_auto_blog.publish_to_wordpress(article)
        self.assertTrue(result.get("already_exists"))
        self.assertEqual(result["id"], 1234)

    def test_publicize_message_is_title_only_by_default(self) -> None:
        from unittest.mock import patch

        with patch.dict(os.environ, {"POST_BY_EMAIL_PUBLICIZE": ""}, clear=False):
            self.assertEqual(
                wp_auto_blog.publicize_message({"title": "My Great Post"}),
                "My Great Post",
            )

    def test_publicize_message_returns_none_when_off(self) -> None:
        from unittest.mock import patch

        with patch.dict(os.environ, {"POST_BY_EMAIL_PUBLICIZE": "off"}, clear=False):
            self.assertIsNone(wp_auto_blog.publicize_message({"title": "My Great Post"}))

    def test_publish_to_wordpress_sends_title_only_publicize_message(self) -> None:
        from unittest.mock import patch

        article = {
            "title": "Test post",
            "slug": "test-post",
            "excerpt": "A short excerpt",
            "html": "<p>Body.</p>",
            "categories": ["tech"],
            "tags": ["test"],
        }

        captured: dict[str, object] = {}

        def fake_wp_request(path: str, payload: object = None, method: str = "GET") -> dict[str, object]:
            captured["path"] = path
            captured["payload"] = payload
            return {"id": 99}

        with patch.dict(
            os.environ,
            {"POST_BY_EMAIL_PUBLICIZE": ""},
            clear=False,
        ):
            with patch("wp_auto_blog.wp_request", side_effect=fake_wp_request):
                with patch("wp_auto_blog.wp_existing_post", return_value=None):
                    with patch("wp_auto_blog.wp_term_ids", return_value=[]):
                        wp_auto_blog.publish_to_wordpress(article)

        self.assertEqual(captured["payload"]["publicize_message"], "Test post")
        self.assertNotIn("publicize", captured["payload"])

    def test_publish_to_wordpress_disables_publicize_when_off(self) -> None:
        from unittest.mock import patch

        article = {
            "title": "Test post",
            "slug": "test-post",
            "excerpt": "A short excerpt",
            "html": "<p>Body.</p>",
            "categories": ["tech"],
            "tags": ["test"],
        }

        captured: dict[str, object] = {}

        def fake_wp_request(path: str, payload: object = None, method: str = "GET") -> dict[str, object]:
            captured["path"] = path
            captured["payload"] = payload
            return {"id": 99}

        with patch.dict(
            os.environ,
            {"POST_BY_EMAIL_PUBLICIZE": "off"},
            clear=False,
        ):
            with patch("wp_auto_blog.wp_request", side_effect=fake_wp_request):
                with patch("wp_auto_blog.wp_existing_post", return_value=None):
                    with patch("wp_auto_blog.wp_term_ids", return_value=[]):
                        wp_auto_blog.publish_to_wordpress(article)

        self.assertFalse(captured["payload"]["publicize"])
        self.assertNotIn("publicize_message", captured["payload"])


if __name__ == "__main__":
    unittest.main()
