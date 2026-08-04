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
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="wp_auto_blog_test_")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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

    def test_free_article_places_more_tag_directly_below_thumbnail(self) -> None:
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
        html = article["html"]

        thumbnail_end = html.index("</figure>") + len("</figure>") if "<figure" in html else html.index("<p>")
        more_pos = html.index("[more]")
        self.assertGreater(more_pos, thumbnail_end)

        between = html[thumbnail_end:more_pos]
        self.assertNotIn("<p>", between)
        self.assertIn("[more]", html)
        self.assertNotIn("<p>", html[thumbnail_end:more_pos + len("[more]")].replace("[more]", ""))

    def test_deliver_article_falls_back_to_email_without_rest_credentials(self) -> None:
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "WP_POST_METHOD": "rest",
                "WP_BASE_URL": "",
                "WP_USERNAME": "",
                "WP_APPLICATION_PASSWORD": "",
                "PRE_PUBLISH_CHECKS": "false",
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
                "PRE_PUBLISH_CHECKS": "false",
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

    def _valid_article(self) -> dict[str, object]:
        body = (
            "<h2>What Changed</h2><p>Researchers at MIT reported a solid-state battery that lasts "
            "12 million cycles, recharges in under fifteen minutes, and costs 40 percent less than "
            "existing lithium cells. The new chemistry packs more energy per kilogram, which lets car "
            "makers install a lighter, smaller battery while keeping the same driving range.</p>"
            "<h2>Why It Matters</h2><p>Why This Matters for drivers who want longer range, faster "
            "charging, and lower prices. Analysts at Bloomberg New Energy Finance expect solid-state "
            "cells to reach mass production by 2028, and several automakers already have prototypes "
            "on the road. A cheaper, denser battery could make electric cars affordable for millions "
            "of households that currently buy gasoline vehicles.</p>"
            "<h2>Chucky's Analysis</h2><p>The details matter more than the headline. The 12 million "
            "cycle figure is far beyond what a typical driver will ever use, but it means the battery "
            "will not degrade the way today's cells do. Combined with the reported 40 percent cost "
            "reduction, the economics shift in favor of adoption, and legacy automakers will have to "
            "respond quickly to avoid losing market share to newer entrants that license the "
            "technology first.</p>"
            "<h2>Key Takeaways</h2><ul><li>Range improves without adding weight.</li><li>Cost drops "
            "by up to 40 percent.</li><li>Mass production expected by 2028.</li></ul>"
            "<h2>Known Details</h2><p>MIT researchers measured a 50 percent cost cut in a follow-up "
            "report, and the university has licensed the patent to two manufacturing partners in "
            "Asia. Public charging networks are also expanding, which addresses one of the biggest "
            "objections to ownership. Grid operators are studying how the faster charge times will "
            "affect peak demand on local substations.</p>"
        )
        filler = (
            "<h2>Background</h2><p>The automotive industry has experimented with several battery "
            "chemistries over the past decade, including nickel, cobalt, and solid ceramic options. "
            "Each approach balances energy density, cost, safety, and manufacturing complexity, and "
            "the winners are still being decided. Solid-state designs have long promised the best of "
            "both worlds, but scaling them from the lab to the factory floor has been the hardest "
            "part, so progress here matters. Regulators in Europe and California are pushing stricter "
            "emissions rules, which gives manufacturers a strong incentive to adopt newer chemistry "
            "sooner rather than later.</p>"
            "<h2>Industry Context</h2><p>Battery factories are being built at record pace around the "
            "world, and every new plant raises the question of which chemistry will dominate. The "
            "cells announced today would slot directly into existing assembly lines with only minor "
            "tooling changes, which lowers the risk for automakers that have already invested heavily "
            "in current lithium ion equipment. Suppliers are also watching closely, because a switch "
            "in chemistry changes which minerals are mined, refined, and shipped across the globe.</p>"
        )
        html = body + filler
        image_path = os.path.join(self.tmpdir, "hero.png")
        from PIL import Image
        img = Image.new("RGB", (1200, 630), "navy")
        img.save(image_path, format="PNG")
        return {
            "title": "Solid-state batteries double electric car range",
            "slug": "solid-state-batteries",
            "excerpt": "A solid-state battery from MIT doubles EV range to 600 miles per charge.",
            "html": html,
            "categories": ["Science"],
            "tags": ["Battery", "EV"],
            "hero_image_path": image_path,
            "fact_sentences": [
                "MIT researchers developed a solid-state battery that charges twice as fast and lasts 12 million cycles."
            ],
        }

    def test_pre_publish_checks_pass_for_complete_article(self) -> None:
        article = self._valid_article()
        failures = wp_auto_blog.pre_publish_checks(article)
        self.assertEqual(failures, [])

    def test_pre_publish_checks_accept_curly_apostrophe_in_section_names(self) -> None:
        article = self._valid_article()
        article["html"] = article["html"].replace("Chucky's Analysis", "Chucky\u2019s Analysis")
        article["html"] = article["html"].replace("Key Takeaways", "Key Takeaways")
        failures = wp_auto_blog.pre_publish_checks(article)
        self.assertEqual(failures, [])

    def test_pre_publish_checks_block_filler_and_missing_sections(self) -> None:
        article = self._valid_article()
        article["html"] = article["html"].replace(
            "<h2>Key Takeaways</h2><ul><li>Range improves without adding weight.</li><li>Cost drops "
            "by up to 40 percent.</li><li>Mass production expected by 2028.</li></ul>",
            "",
        )
        article["html"] += "<p>This is worth watching and points to big changes.</p>"
        failures = wp_auto_blog.pre_publish_checks(article)
        self.assertTrue(any("Key Takeaways" in failure for failure in failures))
        self.assertTrue(any("generic filler" in failure for failure in failures))

    def test_pre_publish_checks_block_short_article_without_facts(self) -> None:
        article = {
            "title": "Short post",
            "html": "<p>Nothing here.</p>",
            "categories": ["Tech"],
            "tags": [],
            "hero_image_path": "",
        }
        failures = wp_auto_blog.pre_publish_checks(article)
        self.assertTrue(any("only 0 subheadings" in failure for failure in failures))
        self.assertTrue(any("no concrete fact" in failure for failure in failures))
        self.assertTrue(any("no featured image" in failure for failure in failures))

    def test_deliver_article_blocks_low_quality_article(self) -> None:
        from unittest.mock import patch

        article = {
            "title": "Short post",
            "slug": "short-post",
            "excerpt": "",
            "html": "<p>Nothing here.</p>",
            "categories": ["Tech"],
            "tags": [],
            "hero_image_path": "",
        }
        with patch.dict(
            os.environ,
            {"WP_POST_METHOD": "rest", "PRE_PUBLISH_CHECKS": "true"},
            clear=False,
        ):
            with patch("wp_auto_blog.send_article_by_email") as send_email:
                result = wp_auto_blog.deliver_article(article)
        send_email.assert_not_called()
        self.assertTrue(result["blocked"])
        self.assertTrue(any("no concrete fact" in failure for failure in result["failures"]))

    def test_check_links_in_html_flags_broken_external_urls(self) -> None:
        from unittest.mock import patch

        html = (
            '<p>See <a href="https://example.com/ok">this</a> and '
            '<a href="https://example.com/dead">that</a>.</p>'
        )

        class FakeResponse:
            def __init__(self, status: int) -> None:
                self.status = status

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

        def fake_urlopen(request, timeout=None):
            url = request.full_url
            if url == "https://example.com/dead":
                return FakeResponse(404)
            return FakeResponse(200)

        with patch("wp_auto_blog.urllib.request.urlopen", side_effect=fake_urlopen):
            broken = wp_auto_blog.check_links_in_html(html)
        self.assertIn("https://example.com/dead", broken)
        self.assertNotIn("https://example.com/ok", broken)

    def test_title_similarity_detects_near_duplicates(self) -> None:
        self.assertGreater(
            wp_auto_blog.title_similarity(
                "MacBook Air shortage hits stores",
                "MacBook Air shortage is affecting store stock",
            ),
            0.4,
        )
        self.assertLess(
            wp_auto_blog.title_similarity(
                "New battery technology unveiled",
                "Roku raises streaming stick prices",
            ),
            0.3,
        )

    def test_guard_against_duplicate_title_blocks_similar(self) -> None:
        from unittest.mock import patch

        with patch(
            "wp_auto_blog.wp_recent_published_posts",
            return_value=[{"title": {"rendered": "MacBook Air shortage hits stores"}, "content": {"rendered": ""}}],
        ):
            result = wp_auto_blog.guard_against_duplicate_title(
                {"title": "MacBook Air shortage is affecting store stock"}
            )
        self.assertIsNotNone(result)
        self.assertTrue(result["already_exists"])

    def test_guard_against_duplicate_title_blocks_source_url_overlap(self) -> None:
        from unittest.mock import patch

        recent = [
            {
                "title": {"rendered": "Sony WH-1000XM6 new color"},
                "content": {
                    "rendered": '<p>Read the original <a href="https://www.gsmarena.com/sony_wh1000xm6_color-news.php?utm=1">here</a>.</p>'
                },
            }
        ]
        cluster = [
            wp_auto_blog.Item(
                uid="s1",
                source_name="GSMArena",
                source_url="https://example.com/feed",
                source_category="phones",
                source_quality=5,
                title="Sony WH-1000XM6 gets a gorgeous new color option",
                link="https://www.gsmarena.com/sony_wh1000xm6_color-news.php",
                summary="Sony adds a new color to the flagship headphone range.",
                published_at=None,
            )
        ]
        with patch("wp_auto_blog.wp_recent_published_posts", return_value=recent):
            result = wp_auto_blog.guard_against_duplicate_title(
                {"title": "Sony adds a fresh color to its premium headphones"}, cluster
            )
        self.assertIsNotNone(result)
        self.assertTrue(result["already_exists"])
        self.assertIn("source_url_matched", result)

    def test_guard_against_duplicate_title_allows_new_story(self) -> None:
        from unittest.mock import patch

        recent = [
            {
                "title": {"rendered": "Google Pixel camera teardown"},
                "content": {"rendered": '<a href="https://www.androidpolice.com/pixel-teardown/">link</a>'},
            }
        ]
        cluster = [
            wp_auto_blog.Item(
                uid="s2",
                source_name="MacRumors",
                source_url="https://example.com/feed",
                source_category="apple",
                source_quality=5,
                title="Apple Watch battery life update",
                link="https://www.macrumors.com/2026/08/apple-watch-battery/",
                summary="New watchOS battery tweak extends usage time.",
                published_at=None,
            )
        ]
        with patch("wp_auto_blog.wp_recent_published_posts", return_value=recent):
            result = wp_auto_blog.guard_against_duplicate_title(
                {"title": "Apple Watch gets a battery life boost"}, cluster
            )
        self.assertIsNone(result)

    def test_story_categories_reflects_actual_topic_not_ai_default(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        phone_cluster = [
            Item(
                uid="p1",
                source_name="GSMArena",
                source_url="https://example.com",
                source_category="phones",
                source_quality=5,
                title="Samsung Galaxy S26 camera upgrade details leak",
                link="https://example.com/phone",
                summary="The next Samsung flagship smartphone will get a larger main sensor and a brighter foldable display.",
                published_at=now,
            )
        ]
        categories = wp_auto_blog.story_categories(phone_cluster, phone_cluster[0].title, ["galaxy", "camera"])
        self.assertIn("phones", categories)
        self.assertNotIn("ai", categories)

    def test_meaningful_tags_reject_junk_words(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        cluster = [
            Item(
                uid="t1",
                source_name="Beta News",
                source_url="https://example.org",
                source_category="tech",
                source_quality=4,
                title="OpenAI launches ChatGPT app for older devices",
                link="https://example.org/chat",
                summary="ChatGPT now runs on older Android phones, giving more users access to the assistant.",
                published_at=now,
            )
        ]
        tags = wp_auto_blog.meaningful_tags(cluster, ["AI"], limit=5)
        self.assertLessEqual(len(tags), 5)
        for tag in tags:
            self.assertNotIn(tag.lower(), wp_auto_blog.JUNK_TAG_TOKENS)
            self.assertNotIn(tag.lower(), wp_auto_blog.STOPWORDS)

    def test_headline_case_capitalizes_mid_title_without_brand_mangling(self) -> None:
        self.assertEqual(
            wp_auto_blog.headline_case("nasa, spacex advance wind tunnel tests for starship rocket"),
            "NASA, SpaceX Advance Wind Tunnel Tests for Starship Rocket",
        )
        self.assertEqual(
            wp_auto_blog.headline_case("porous 3d-printed feet cut quadruped robot power use"),
            "Porous 3d-printed Feet Cut Quadruped Robot Power Use",
        )
        self.assertEqual(
            wp_auto_blog.headline_case("smarter, not thicker: targeted cooling improves liquid-hydrogen tank insulation"),
            "Smarter, Not Thicker: Targeted Cooling Improves Liquid-hydrogen Tank Insulation",
        )
        self.assertEqual(
            wp_auto_blog.headline_case("china's ev market is booming. there's just one problem"),
            "China's EV Market Is Booming. There's Just One Problem",
        )
        self.assertEqual(
            wp_auto_blog.headline_case("chuckys analysis of the ai boom: what comes next"),
            "Chuckys Analysis of the AI Boom: What Comes Next",
        )
        self.assertEqual(
            wp_auto_blog.headline_case("a guide to the web for beginners"),
            "A Guide to the Web for Beginners",
        )


class ParseFeedRdfTests(unittest.TestCase):
    def test_parse_feed_reads_namespaced_rdf_items(self) -> None:
        rdf_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel rdf:about="https://example.org/feed">
    <title>Example Health Research</title>
    <link>https://example.org</link>
    <description>Research news</description>
  </channel>
  <item rdf:about="https://example.org/breakthrough">
    <title>New therapy shows promise in early trials</title>
    <link>https://example.org/breakthrough</link>
    <description>Researchers report promising results from an early-stage trial of the therapy.</description>
    <dc:date>2026-07-01T12:00:00Z</dc:date>
  </item>
  <item rdf:about="https://example.org/second">
    <title>Second research update</title>
    <link>https://example.org/second</link>
    <description>Follow-up results confirm the earlier findings.</description>
  </item>
</rdf:RDF>
"""
        feed = wp_auto_blog.Feed(
            name="Example Health Research",
            url="https://example.org/feed",
            category="health",
            quality=5,
        )
        items = wp_auto_blog.parse_feed(feed, rdf_xml)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "New therapy shows promise in early trials")
        self.assertEqual(items[0].link, "https://example.org/breakthrough")
        self.assertEqual(items[0].source_category, "health")
        self.assertIsNotNone(items[0].published_at)


if __name__ == "__main__":
    unittest.main()
