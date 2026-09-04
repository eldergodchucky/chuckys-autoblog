import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wp_auto_blog


class ArticleQualityGateTests(unittest.TestCase):
    def test_rejects_thin_article(self) -> None:
        failures = wp_auto_blog.article_quality_failures(
            {"html": "<p>Legora reviewed 41 documents in minutes.</p>"}
        )
        self.assertIn("article has only 6 words", failures)
        self.assertIn("article has only 1 paragraphs", failures)

    def test_rejects_repeated_sentence(self) -> None:
        paragraph = "The product launches today for readers. "
        body = "".join(
            f"<p>{paragraph}This paragraph adds a different factual detail about testing, pricing, support, and availability for customers today.</p>"
            for _ in range(6)
        )
        failures = wp_auto_blog.article_quality_failures({"html": body})
        self.assertIn("2 repeated sentence(s)", failures)

    def test_accepts_complete_unique_article(self) -> None:
        body = "".join(
            f"<p>Paragraph {index} explains a distinct factual detail about the product, including its testing results, launch timing, documented limits, practical use, support policy, availability for readers, regional rollout, compatibility requirements, security controls, maintenance schedule, documented customer impact in ordinary daily use, installation process, operating requirements, account controls, update policy, measured performance, known limitations, customer support route, pricing terms, data handling, and independent review evidence.</p>"
            for index in range(6)
        )
        self.assertEqual(wp_auto_blog.article_quality_failures({"html": body}), [])


if __name__ == "__main__":
    unittest.main()
