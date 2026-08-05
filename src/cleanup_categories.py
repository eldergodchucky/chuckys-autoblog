"""Category cleanup for ChuckysCarnage.

Reassigns straggler posts out of legacy categories, switches the default
category away from Uncategorized, and deletes the empty leftovers. Every
step is reported and idempotent, so the script is safe to re-run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wp_auto_blog import load_env, wp_request  # noqa: E402

ASSIGNMENTS = {
    "info": "science",
    "tips": "tech",
}

DROP_SLUGS = ["info", "tips", "nature", "uncategorized"]


def get_categories() -> dict[str, dict]:
    result: dict[str, dict] = {}
    page = 1
    while True:
        data = wp_request(f"categories?per_page=100&page={page}&_fields=id,name,slug,count")
        if not isinstance(data, list) or not data:
            break
        for category in data:
            result[str(category.get("slug") or "")] = category
        if len(data) < 100:
            break
        page += 1
    return result


def posts_in_category(category_id: int) -> list[dict]:
    posts: list[dict] = []
    page = 1
    while True:
        data = wp_request(
            f"posts?categories={category_id}&per_page=100&page={page}"
            "&status=publish,draft,pending,future,private&_fields=id,title,link,categories"
        )
        if not isinstance(data, list) or not data:
            break
        posts.extend(data)
        if len(data) < 100:
            break
        page += 1
    return posts


def main() -> int:
    load_env()
    categories = get_categories()
    print(f"Found {len(categories)} categories on the site.")

    for source_slug, target_slug in ASSIGNMENTS.items():
        source = categories.get(source_slug)
        target = categories.get(target_slug)
        if not source or not target:
            print(f"Missing category for reassignment: {source_slug} -> {target_slug}; skipping.")
            continue
        posts = posts_in_category(int(source["id"]))
        for post in posts:
            wp_request(f"posts/{int(post['id'])}", {"categories": [int(target["id"])]}, method="POST")
            print(f"Reassigned #{post['id']} ({str(post.get('title', {}).get('rendered') or '')[:40]}) to {target_slug}")
        print(f"Category '{source_slug}': {len(posts)} post(s) reassigned to '{target_slug}'.")

    settings = wp_request("settings", method="GET")
    if isinstance(settings, dict) and int(settings.get("default_category") or 0) == 1:
        wp_request("settings", {"default_category": 173}, method="POST")
        print("Switched default category from Uncategorized to Science.")

    for slug in DROP_SLUGS:
        category = categories.get(slug)
        if not category:
            print(f"Category '{slug}' not found; skipping.")
            continue
        try:
            result = wp_request(f"categories/{int(category['id'])}?force=true", method="DELETE")
            print(f"Deleted '{slug}' (#{category['id']}): {result}")
        except Exception as exc:
            print(f"Could not delete '{slug}' (#{category['id']}): {exc}")

    print("Category cleanup finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
