"""Weekly digest post for ChuckysCarnage.

Builds a summary post of the blog's own published articles from the past
seven days and publishes it through the same WordPress.com pipeline as
regular posts. Safe to run any time: the digest slug embeds its end date,
so re-running the same week is a no-op, and the run is skipped entirely
when too few posts were published in the window.
"""

import argparse
import datetime as dt
import html
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wp_auto_blog import env_int, load_env, publish_to_wordpress, wp_request  # noqa: E402

DIGEST_CATEGORY = "Digest"
MIN_POSTS_FOR_DIGEST = 3
DEFAULT_WINDOW_DAYS = 7
DEFAULT_MAX_ITEMS = 10
CORE_CATEGORY_NAMES = {
    "Science",
    "Space",
    "AI",
    "Gadgets",
    "Phones",
    "Android",
    "Apple",
    "Software",
    "Security",
    "Tutorials",
    "Hacks",
    "Health",
    "Tech",
}


def category_name_map() -> dict[int, str]:
    """Fetch every category and return a mapping of id -> display name."""
    ids_to_names: dict[int, str] = {}
    page = 1
    while True:
        data = wp_request(f"categories?per_page=100&page={page}&_fields=id,name")
        if not isinstance(data, list) or not data:
            break
        for category in data:
            category_id = category.get("id")
            name = str(category.get("name") or "").strip()
            if category_id is not None and name:
                ids_to_names[int(category_id)] = name
        if len(data) < 100:
            break
        page += 1
    return ids_to_names


def fetch_recent_posts(after: dt.datetime) -> list[dict]:
    """Fetch published posts created after ``after``, paginating in chunks of 100."""
    after_iso = after.strftime("%Y-%m-%dT%H:%M:%S")
    posts: list[dict] = []
    page = 1
    while True:
        data = wp_request(
            f"posts?after={after_iso}&per_page=100&page={page}&status=publish&_fields=id,date,title,link,excerpt,categories"
        )
        if not isinstance(data, list) or not data:
            break
        posts.extend(data)
        if len(data) < 100:
            break
        page += 1
    return posts


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _date_label(start: dt.date, end: dt.date) -> str:
    return f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}, {end.year}"


def build_digest_article(
    posts: list[dict],
    category_names: dict[int, str],
    start: dt.date,
    end: dt.date,
) -> dict | None:
    """Return an article dict for the digest, or None when there is too little to summarize.

    The most recent posts are picked first (up to the digest cap), then grouped
    by their primary known category; posts without a known category land under
    "Other".
    """
    if len(posts) < MIN_POSTS_FOR_DIGEST:
        return None

    max_items = max(1, env_int("DIGEST_MAX_ITEMS", DEFAULT_MAX_ITEMS))
    ordered = sorted(posts, key=lambda post: str(post.get("date") or ""), reverse=True)

    grouped: dict[str, list[dict]] = {}
    seen_titles: set[str] = set()
    for post in ordered:
        title = _plain_text((post.get("title") or {}).get("rendered") or post.get("title") or "")
        title_key = title.lower()
        if not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        primary = "Other"
        category_ids = [int(category_id) for category_id in post.get("categories") or []]
        for category_id in category_ids:
            if category_names.get(category_id) in CORE_CATEGORY_NAMES:
                primary = category_names[category_id]
                break
        if primary == "Other":
            for category_id in category_ids:
                if category_names.get(category_id):
                    primary = category_names[category_id]
                    break
        grouped.setdefault(primary, []).append(post)
        if sum(len(items) for items in grouped.values()) >= max_items:
            break

    sections: list[str] = []
    for category_name, items in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rows = []
        for post in items:
            title = _plain_text((post.get("title") or {}).get("rendered") or post.get("title") or "")
            link = str(post.get("link") or "")
            published = str(post.get("date") or "")[:10]
            rows.append(f'<li><strong><a href="{link}">{html.escape(title)}</a></strong> ({published})</li>')
        sections.append(f"<h2>{html.escape(category_name)}</h2>\n<ul>\n" + "\n".join(rows) + "\n</ul>")

    label = _date_label(start, end)
    picked_total = sum(len(items) for items in grouped.values())
    intro = (
        f"<p>Every week we round up the stories published on ChuckysCarnage so you never "
        f"miss a highlight. {len(posts)} articles went live between {label}; here are the "
        f"{picked_total} most recent highlights.</p>"
    )
    footer = (
        f"<p><em>This digest covers {len(posts)} articles published between {label}. "
        f"Follow the blog or subscribe for the next roundup.</em></p>"
    )
    return {
        "title": f"Weekly Digest: {label}",
        "slug": f"weekly-digest-{end.strftime('%Y-%m-%d')}",
        "excerpt": f"Our weekly roundup of the most important stories on ChuckysCarnage, from {label}.",
        "html": "\n".join([intro] + sections + [footer]),
        "categories": [DIGEST_CATEGORY],
        "tags": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish the weekly digest of recent blog posts.")
    parser.add_argument("--dry-run", action="store_true", help="Print the digest without publishing.")
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS, help="Digest window in days.")
    args = parser.parse_args(argv)
    load_env()

    end = dt.date.today()
    start = end - dt.timedelta(days=args.days)
    after = dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc)
    posts = fetch_recent_posts(after)
    if not posts:
        print(f"No published posts since {start.isoformat()}; skipping digest.")
        return 0

    article = build_digest_article(posts, category_name_map(), start, end)
    if article is None:
        print(
            f"Only {len(posts)} published post(s) in the last {args.days} day(s); "
            f"below the {MIN_POSTS_FOR_DIGEST} minimum; skipping digest."
        )
        return 0

    if args.dry_run:
        print(f"Digest ready: {article['title']}")
        print(f"Slug: {article['slug']}")
        print(f"Posts covered: {len(posts)}")
        print(article["html"])
        return 0

    result = publish_to_wordpress(article)
    post_id = result.get("id")
    if result.get("already_exists"):
        print(f"Digest already exists as #{post_id}; nothing to do.")
        return 0
    print(f"Published weekly digest #{post_id}: {result.get('link', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
