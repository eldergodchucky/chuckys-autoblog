import datetime as dt
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import wp_auto_blog
from wp_auto_blog import Item, clean_editorial_title, is_deal_roundup, is_dense_academic_paper, article_quality_failures, publishable_cluster


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
            ("5 reasons I’m keeping my Fitbit Air and not buying a Fitbit Edge", "Comparing Fitbit Air and Fitbit Edge: Key Decision Factors"),
        ]
        for original, expected in cases:
            cleaned = clean_editorial_title(original)
            self.assertEqual(cleaned, expected)

    def test_dangling_conjunction_cutoff_stripped(self):
        title = "The DSA has a believability problem with older Black voters. But young"
        cleaned = clean_editorial_title(title)
        self.assertEqual(cleaned, "The DSA has a believability problem with older Black voters")

    def test_deal_filtering(self):
        deal_titles = [
            "Record-low deal cuts the Arlo Ultra 4K HDR 2-camera SmartHub bundle to $221",
            "Amazon Discounting 2026 MacBook Pro by as Much as $600 This Week",
            "Deals: Early Prime Day deals on Samsung foldables now live, Pixel",
            "Today’s 9to5Toys Lunch Break is headlined by Apple’s most affordable",
            "Amazon Takes $199 Off Nearly Every M5 MacBook Air, Starting at $899.99",
            "Amazon cuts $900 off the 2026 MacBook Pro with M5 Max chip",
            "Samsung’s latest 55-inch Frame TV is down to its lowest price yet",
            "Sony's WH-1000XM5 are at an all-time low price for Prime Day",
        ]
        for title in deal_titles:
            deal_item = Item(
                uid=f"item-deal-{hash(title)}",
                source_name="DealNews",
                source_url="https://dealnews.com",
                source_category="gadgets",
                source_quality=4,
                title=title,
                link="https://dealnews.com/deal",
                summary="Save big on this product today.",
                published_at=dt.datetime.now(dt.timezone.utc),
            )
            self.assertTrue(is_deal_roundup([deal_item]), f"Failed to filter deal: {title}")

    def test_podcast_and_linkdump_filtering(self):
        dump_titles = [
            "9to5Mac Daily: October 12",
            "Hackaday Links: October 11",
            "Morning Briefing: Global News Roundup",
        ]
        for title in dump_titles:
            item = Item(
                uid=f"item-dump-{hash(title)}",
                source_name="TechDaily",
                source_url="https://techdaily.com",
                source_category="tech",
                source_quality=4,
                title=title,
                link="https://techdaily.com/links",
                summary="Here are the top links and podcast highlights for today.",
                published_at=dt.datetime.now(dt.timezone.utc),
            )
            self.assertFalse(publishable_cluster([item]), f"Failed to filter linkdump/podcast: {title}")

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



    def test_health_who_false_positive_avoided(self):
        sports_item = Item(
            uid="item-sports-who",
            source_name="BBC Sport",
            source_url="https://bbc.com/sport",
            source_category="sports",
            source_quality=5,
            title="Who was right about Man Utd tactics: Carrick or Fernandes?",
            link="https://bbc.com/sport/football/1",
            summary="A tactical breakdown of the latest football match.",
            published_at=dt.datetime.now(dt.timezone.utc),
        )
        cats = wp_auto_blog.story_categories([sports_item], sports_item.title, [])
        self.assertNotIn("health", cats, "English question word 'Who' should not trigger health category")



    def test_international_dateline_prepended(self):
        item = Item(
            uid="item-test-dateline",
            source_name="Reuters",
            source_url="https://reuters.com",
            source_category="world",
            source_quality=5,
            title="Diplomats convene in Geneva for emergency trade talks",
            link="https://reuters.com/article/1",
            summary="Diplomats from 40 nations gathered in Geneva on Friday to negotiate a new global trade protocol.",
            published_at=dt.datetime.now(dt.timezone.utc),
        )
        art = wp_auto_blog.free_article([item])
        self.assertIn("<strong>GENEVA — </strong>", art["html"])

    def test_key_developments_box_present(self):
        item = Item(
            uid="item-test-glance",
            source_name="Nature",
            source_url="https://nature.com",
            source_category="science",
            source_quality=5,
            title="Scientists observe quantum coherence at room temperature",
            link="https://nature.com/article/2",
            summary="Researchers observed quantum coherence lasting several microseconds at room temperature. The breakthrough could accelerate the development of commercial quantum sensors.",
            published_at=dt.datetime.now(dt.timezone.utc),
        )
        art = wp_auto_blog.free_article([item])
        self.assertIn("Key Developments", art["html"])
        self.assertIn("article-at-a-glance", art["html"])


if __name__ == "__main__":
    unittest.main()
