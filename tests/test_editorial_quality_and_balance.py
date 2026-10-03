import datetime as dt
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wp_auto_blog
from wp_auto_blog import Item, clean_editorial_title, is_deal_roundup, is_dense_academic_paper, article_quality_failures


class EditorialQualityAndBalanceTests(unittest.TestCase):
    def test_first_person_columnist_title_transformed(self):
        cases = [
            ("Here’s why I upgraded from the Apple Watch Series 10 to Series 12", "Why Upgrading from the Apple Watch Series 10 to Series 12 Makes Sense"),
            ("My Samsung phone was full of screenshots. This quick trick fixed it", "How to Fix Cluttered screenshots Storage on Samsung phone"),
            ("I hate when Android brands copy Apple — but the iPhone Duo is the exception", "Why the iPhone Duo Challenges Android brands-Apple  Rivalry"),
            ("These 9 Thunderbird features made me ditch Gmail for good", "9 Key Thunderbird Features Driving Users Away from Gmail"),
            ("What’s the best Snapdragon 8 Gen 5 series chip? I tested them all to find out", "What's the best Snapdragon 8 Gen 5 series chip? Performance and Benchmark Comparison"),
            ("I used Pixel’s new battery summaries for a week — and Google has work to do", "Testing Pixel's new battery summaries: Analysis and Key Observations"),
            ("T-Mobile’s leaked T-Mix plans are way more complicated than we thought", "T-Mobile's leaked T-Mix plans are More Complex Than Expected"),
            ("Here’s everything we know so far about Apple’s next entry-level iPad: A19 chip", "What to Expect from Apple's next entry-level iPad: A19 chip"),
        ]
        for original, expected in cases:
            cleaned = clean_editorial_title(original)
            self.assertEqual(cleaned, expected)

    def test_dangling_conjunction_cutoff_stripped(self):
        title = "The DSA has a believability problem with older Black voters. But young"
        cleaned = clean_editorial_title(title)
        self.assertEqual(cleaned, "The DSA has a believability problem with older Black voters")

    def test_deal_filtering(self):
        deal_item = Item(
            uid="item-deal-1",
            source_name="9to5Toys",
            source_url="https://9to5toys.com",
            source_category="gadgets",
            source_quality=4,
            title="Record-low deal cuts the Arlo Ultra 4K HDR 2-camera SmartHub bundle to $221",
            link="https://9to5toys.com/deal",
            summary="Save big on this security camera bundle today.",
            published_at=dt.datetime.now(dt.timezone.utc),
        )
        self.assertTrue(is_deal_roundup([deal_item]))

    def test_dense_academic_paper_filtering(self):
        paper_item = Item(
            uid="item-paper-1",
            source_name="BMC Medicine",
            source_url="https://bmcmedicine.biomedcentral.com",
            source_category="health",
            source_quality=4,
            title="Social support and HRQoL decline in cirrhosis: a 12-month cohort in China",
            link="https://bmcmedicine.biomedcentral.com/articles/123",
            summary="Download PDF Abstract. Health-related quality of life is evaluated.",
            published_at=dt.datetime.now(dt.timezone.utc),
        )
        self.assertTrue(is_dense_academic_paper([paper_item]))

    def test_minimum_article_words_gate(self):
        stub_article = {
            "title": "A short update",
            "html": "<p>This is a short post with very few words.</p>",
        }
        failures = article_quality_failures(stub_article)
        self.assertTrue(any("words" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
