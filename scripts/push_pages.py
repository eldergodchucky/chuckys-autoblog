from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

USER_AGENT = "ChuckysCarnagePages/1.0"

PAGES = [
    {
        "slug": "about",
        "title": "About ChuckysCarnage",
        "content": (
            "<h2>About</h2>\n"
            "<p>Technology never stands still, and neither should the way we understand it.</p>\n"
            "<p>ChuckysCarnage was created to make today's biggest breakthroughs in technology, artificial intelligence, "
            "cybersecurity, gaming, science, software, and innovation easier to understand without unnecessary jargon or "
            "clickbait.</p>\n"
            "<p>The internet is filled with headlines that tell you what happened. Our goal is to explain why it matters, "
            "how it works, and what could happen next.</p>\n"
            "<p>Whether it's a new AI model, a cybersecurity threat, a breakthrough in space exploration, or the latest "
            "gaming release, every article aims to provide clear explanations, practical insights, and thoughtful analysis "
            "that help readers stay informed in a rapidly changing world.</p>\n"
            "<p>We believe technology should be accessible to everyone, regardless of technical background.</p>\n"
            "<h2>Our Mission</h2>\n"
            "<p>Our mission is to simplify complex technology, deliver trustworthy information, and help readers understand "
            "the innovations shaping tomorrow.</p>\n"
            "<h2>Our Vision</h2>\n"
            "<p>To become one of the world's most trusted independent technology publications by making advanced technology "
            "understandable, useful, and engaging for everyone.</p>\n"
            "<h2>Our Values</h2>\n"
            "<ul>\n<li>Accuracy</li>\n<li>Transparency</li>\n<li>Curiosity</li>\n<li>Innovation</li>\n"
            "<li>Integrity</li>\n<li>Accessibility</li>\n</ul>\n"
            "<p>Thank you for being part of the ChuckysCarnage community. Welcome to the future.</p>"
        ),
    },
    {
        "slug": "contact",
        "title": "Contact",
        "content": (
            "<p>Have a question, suggestion, correction, partnership opportunity, or business inquiry? We'd love to hear "
            "from you. Reach out through the comments on our posts or via our official social media channels. We aim to "
            "respond as quickly as possible.</p>\n"
            "<h2>Corrections</h2>\n"
            "<p>Spot an error? Tell us and we will review it promptly and publish a correction where needed. See the "
            "<a href=\"/editorial-policy\">Editorial Policy</a> for how we handle accuracy.</p>"
        ),
    },
    {
        "slug": "privacy",
        "title": "Privacy Policy",
        "content": (
            "<p>ChuckysCarnage respects your privacy. We collect only the information needed to deliver content, process "
            "subscriptions, and improve the site experience.</p>\n"
            "<h2>Information we collect</h2>\n"
            "<p>We may collect limited technical information such as your IP address and browser type, as well as any "
            "information you voluntarily provide when you comment, subscribe, or contact us. We do not sell your personal "
            "data.</p>\n"
            "<h2>How we use information</h2>\n"
            "<p>Information is used to publish and improve content, moderate comments, respond to inquiries, and prevent "
            "abuse. Third-party services such as analytics or social platforms may process limited data under their own "
            "privacy policies.</p>\n"
            "<h2>Your choices</h2>\n"
            "<p>You can request access to, correction of, or deletion of personal data we hold by contacting us through "
            "the channels listed on the Contact page. See also the <a href=\"/cookie-policy\">Cookie Policy</a>.</p>"
        ),
    },
    {
        "slug": "disclaimer",
        "title": "Disclaimer",
        "content": (
            "<p>Published content is for informational purposes only and should not be considered financial, legal, "
            "medical, or professional advice.</p>\n"
            "<p>ChuckysCarnage reports on developments in technology, science, AI, cybersecurity, gaming, and software. "
            "Articles summarize and interpret information from public sources at the time of writing. Technology changes "
            "quickly, and details may be superseded. Always verify critical information against official sources before "
            "making decisions.</p>\n"
            "<p>Links to third-party sites are provided for convenience. We are not responsible for the content, accuracy, "
            "or availability of external sites.</p>"
        ),
    },
    {
        "slug": "editorial-policy",
        "title": "Editorial Policy",
        "content": (
            "<p>ChuckysCarnage values factual accuracy, transparency, source verification, balanced reporting, corrections "
            "when necessary, and editorial independence.</p>\n"
            "<h2>Accuracy and sourcing</h2>\n"
            "<p>Articles are grounded in publicly available source material, which is linked in each post. We explain what "
            "happened, why it matters, how it works, and what could happen next.</p>\n"
            "<h2>Corrections</h2>\n"
            "<p>When an error is identified, we correct the article promptly and note the change where significant. "
            "Readers can report errors through the Contact page.</p>\n"
            "<h2>Independence</h2>\n"
            "<p>Editorial content is independent. Any commercial or affiliate relationships are disclosed in the "
            "<a href=\"/affiliate-disclosure\">Affiliate Disclosure</a>.</p>"
        ),
    },
    {
        "slug": "affiliate-disclosure",
        "title": "Affiliate Disclosure",
        "content": (
            "<p>Some links on ChuckysCarnage may be affiliate links. If you buy something through one of those links, we "
            "may earn a small commission at no additional cost to you.</p>\n"
            "<p>Affiliate relationships never influence our coverage. Recommendations and analysis are based on editorial "
            "judgment, not on commissions. Where a link is promotional, it will be disclosed in the post itself.</p>"
        ),
    },
    {
        "slug": "ai-policy",
        "title": "AI Usage Policy",
        "content": (
            "<p>Artificial intelligence may assist with research, drafting, editing, grammar improvement, and formatting. "
            "All published content is reviewed before publication.</p>\n"
            "<p>Every article links to its underlying sources so readers can verify the claims. Our editorial standards "
            "require accuracy, transparency, and clear attribution, as described in the "
            "<a href=\"/editorial-policy\">Editorial Policy</a>.</p>"
        ),
    },
    {
        "slug": "cookie-policy",
        "title": "Cookie Policy",
        "content": (
            "<p>ChuckysCarnage uses cookies to remember theme preferences, improve performance, and support site "
            "analytics. You can manage or disable cookies through your browser settings.</p>\n"
            "<h2>What cookies we use</h2>\n"
            "<p>Essential cookies keep the site working and remember your preferences. Analytics cookies help us "
            "understand how the site is used so we can improve it. Third-party embeds and social widgets may set their "
            "own cookies.</p>\n"
            "<h2>Managing cookies</h2>\n"
            "<p>Most browsers let you block or delete cookies. Doing so may affect some site features. You can also opt "
            "out of third-party analytics through the providers' own controls.</p>"
        ),
    },
    {
        "slug": "copyright",
        "title": "Copyright and reuse",
        "content": (
            "<p>All original editorial content published by ChuckysCarnage is protected by copyright unless otherwise "
            "stated. Reuse requires permission or an explicit license.</p>\n"
            "<p>Readers may link to articles, quote brief excerpts for commentary, or share summaries when done "
            "responsibly and with attribution. Any broader reproduction, adaptation, or commercial use should be requested "
            "in advance through the Contact page.</p>"
        ),
    },
    {
        "slug": "social",
        "title": "Follow the publication",
        "content": (
            "<p>ChuckysCarnage is building a premium editorial network across major social channels, with concise "
            "analysis, timely updates, and conversation around important technology stories.</p>\n"
            "<h2>Social channels</h2>\n"
            "<ul>\n<li>X: breaking updates and quick commentary</li>\n<li>LinkedIn: deeper professional analysis</li>\n"
            "<li>Newsletter: curated roundups and priority stories</li>\n</ul>\n"
            "<h2>Community guidelines</h2>\n"
            "<p>We welcome thoughtful discussion and encourage comments that are respectful, informed, and grounded in "
            "evidence rather than hype.</p>"
        ),
    },
]


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def wp_request(path: str, payload: dict | None = None, method: str = "GET") -> dict | list:
    base_url = os.getenv("WP_BASE_URL", "").rstrip("/")
    username = os.getenv("WP_USERNAME", "")
    app_password = os.getenv("WP_APPLICATION_PASSWORD", "")
    if not base_url or not username or not app_password:
        raise RuntimeError(
            "WP_BASE_URL, WP_USERNAME, and WP_APPLICATION_PASSWORD must be set in .env (REST publishing)."
        )

    if "/wp-json/wp/v2/" in f"{base_url}/" or "/wp/v2/sites/" in f"{base_url}/":
        api_base = base_url
    else:
        api_base = f"{base_url}/wp-json/wp/v2"
    url = f"{api_base}/{path.lstrip('/')}"
    token = base64.b64encode(f"{username}:{app_password}".encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            pass
        raise RuntimeError(f"WordPress API {exc.code} on {method} {path}: {body[:400]}") from exc


def upsert_page(page: dict, dry_run: bool = False) -> str:
    slug = page["slug"]
    if dry_run:
        return f"would create or update page: {page['title']} (slug={slug})"
    found = wp_request(f"pages?slug={slug}&status=publish,draft&per_page=1")
    if found:
        page_id = found[0]["id"]
        updated = wp_request(
            f"pages/{page_id}",
            payload={
                "title": page["title"],
                "content": page["content"],
                "status": "publish",
            },
            method="POST",
        )
        return f"updated: {page['title']} (id={updated.get('id')}, link={updated.get('link')})"
    if dry_run:
        return f"would create page: {page['title']} (slug={slug})"
    created = wp_request(
        "pages",
        payload={
            "title": page["title"],
            "content": page["content"],
            "slug": slug,
            "status": "publish",
        },
        method="POST",
    )
    return f"created: {page['title']} (id={created.get('id')}, link={created.get('link')})"


STALE_PAGE_SLUGS = {"about-2", "contact-2", "home-2", "blog-2"}


def cleanup_stale_pages(dry_run: bool = False) -> list[str]:
    messages: list[str] = []
    pages = wp_request("pages?per_page=100&status=publish,draft")
    if not isinstance(pages, list):
        return ["Could not list pages for cleanup."]
    for page in pages:
        slug = str(page.get("slug") or "")
        if slug in STALE_PAGE_SLUGS:
            page_id = page["id"]
            title = str(page.get("title", {}).get("rendered", "")) if isinstance(page.get("title"), dict) else ""
            if dry_run:
                messages.append(f"would delete stale page: {title} (slug={slug}, id={page_id})")
                continue
            wp_request(f"pages/{page_id}", method="DELETE")
            messages.append(f"deleted stale page: {title} (slug={slug}, id={page_id})")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update ChuckysCarnage WordPress pages via the REST API.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without calling WordPress.")
    parser.add_argument("--slug", help="Only process this page slug.")
    parser.add_argument(
        "--cleanup-stale",
        action="store_true",
        help="Also delete duplicate/stale pages (about-2, contact-2, home-2, blog-2).",
    )
    args = parser.parse_args()

    load_env()
    selected = [p for p in PAGES if not args.slug or p["slug"] == args.slug]
    if not selected:
        print(f"No page definitions match slug {args.slug!r}.", file=sys.stderr)
        return 1

    if args.dry_run:
        print("DRY RUN — no changes made:")
    for page in selected:
        print(upsert_page(page, dry_run=args.dry_run))
    if args.cleanup_stale:
        for message in cleanup_stale_pages(dry_run=args.dry_run):
            print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
