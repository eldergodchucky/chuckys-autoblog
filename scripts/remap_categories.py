"""Reassign posts out of 'info' and 'uncategorized' into real categories.

Strategy (deterministic, tag-driven):
1. A post whose tag IDs include a real category term (apple/ai/space/...) takes
   that category — on wp.com a term can be both a tag and a category with the
   same ID, so tag IDs like 291 (apple) map straight to the category.
2. Otherwise, tag names are matched against a keyword table.
3. Fallback: 'tech'.

Dry-run by default; --apply performs the updates in chunks (resumable via
--offset).
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_pages import load_env, wp_request  # noqa: E402

TAGS_FILE = Path(r"C:\Users\ELDERCHUCKY\AppData\Local\Temp\opencode\site_tags.json")
CHECKPOINT_FILE = Path(r"C:\Users\ELDERCHUCKY\AppData\Local\Temp\opencode\remap_checkpoint.json")

CATEGORIES = {
    "ai": 14067,
    "android": 641922,
    "apple": 291,
    "gadgets": 1559,
    "health": 337,
    "nature": 1099,
    "phone": 36914,
    "science": 173,
    "security": 801,
    "software": 581,
    "space": 174,
    "tech": 318,
    "tips": 1788,
}
INFO_CATEGORY = 2065
UNCATEGORIZED = 1

# tag-name keyword -> category slug (lowercase tag names)
TAG_KEYWORDS = {
    "ai": "ai", "artificial": "ai", "chatgpt": "ai", "openai": "ai",
    "claude": "ai", "anthropic": "ai", "gemini": "ai", "llm": "ai",
    "apple": "apple", "iphone": "apple", "ios": "apple", "ipad": "apple",
    "mac": "apple", "macbook": "apple", "airpods": "apple", "watch": "apple",
    "android": "android", "samsung": "android", "pixel": "android",
    "oneplus": "android", "xiaomi": "android",
    "space": "space", "nasa": "space", "mars": "space", "moon": "space",
    "telescope": "space", "astronomers": "space", "astronomy": "space",
    "galaxy": "space", "spacex": "space", "satellite": "space", "orbit": "space",
    "science": "science", "research": "science", "study": "science",
    "physics": "science", "biology": "science", "chemistry": "science",
    "climate": "science", "energy": "science", "brain": "science",
    "earth": "science",
    "health": "health", "medical": "health", "medicine": "health",
    "drug": "health", "vaccine": "health", "clinical": "health",
    "patient": "health",
    "phone": "phone", "phones": "phone", "smartphone": "phone",
    "mobile": "phone",
    "gadgets": "gadgets", "gadget": "gadgets", "smartwatch": "gadgets",
    "wearable": "gadgets", "earbuds": "gadgets", "drone": "gadgets",
    "software": "software", "app": "software", "apps": "software",
    "developer": "software", "api": "software",
    "security": "security", "cyber": "security", "malware": "security",
    "hacker": "security", "breach": "security", "password": "security",
    "nature": "nature", "environment": "nature", "wildlife": "nature",
    "tips": "tips", "tutorial": "tips", "how-to": "tips", "guide": "tips",
    "tech": "tech", "technology": "tech",
}


def load_tag_names() -> dict[int, str]:
    tags = json.loads(TAGS_FILE.read_text(encoding="utf-8"))
    return {int(t["id"]): str(t["name"]).strip().lower() for t in tags}


def target_category(tag_ids: list[int], tag_names: dict[int, str]) -> str:
    """Pick the best category for a post, preferring the most specific match.

    The old pipeline blanket-applied the 'ai' tag to many posts, so 'ai' must
    never beat device or topic categories when a more specific tag exists.
    Priority: device (android/apple/phone) > gadgets > science/space/health/
    security/software/nature/tips > ai > tech (fallback).
    """
    # 1) device-specific categories first
    device_order = ["android", "apple", "phone"]
    for slug in device_order:
        if CATEGORIES[slug] in tag_ids:
            return slug
    # 2) keyword names for device categories
    for slug, names in (
        ("android", ("android", "samsung", "pixel", "oneplus", "xiaomi")),
        ("apple", ("apple", "iphone", "ios", "ipad", "mac", "macbook", "airpods", "watch")),
        ("phone", ("phone", "phones", "smartphone", "mobile")),
    ):
        for name in names:
            if any(tag_names.get(tag_id) == name for tag_id in tag_ids):
                return slug
    # 3) everything else that is a real category term
    topic_order = [
        "gadgets", "science", "space", "health", "security", "software",
        "nature", "tips",
    ]
    for slug in topic_order:
        if CATEGORIES[slug] in tag_ids:
            return slug
    # 4) keyword names for topic categories (skip device/ai/tech handled above)
    names_by_slug: dict[str, set[str]] = {}
    for name, slug in TAG_KEYWORDS.items():
        names_by_slug.setdefault(slug, set()).add(name)
    for slug, names in names_by_slug.items():
        if slug in device_order or slug in ("ai", "tech"):
            continue
        if any(tag_names.get(tag_id) in names for tag_id in tag_ids):
            return slug
    # 5) the 'ai' tag as a last resort before the generic fallback
    if CATEGORIES["ai"] in tag_ids:
        return "ai"
    return "tech"


def fetch_posts(category_id: int, per_page: int = 100) -> list[dict]:
    posts: list[dict] = []
    page = 1
    while True:
        batch = wp_request(
            f"posts?categories={category_id}&per_page={per_page}&page={page}"
            f"&_fields=id,title,categories,tags"
        )
        if not isinstance(batch, list) or not batch:
            break
        posts.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(0.3)
    return posts


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually update posts.")
    parser.add_argument("--limit", type=int, default=0, help="Max posts to process (0 = all).")
    parser.add_argument("--offset", type=int, default=-1, help="Skip first N posts; -1 = resume from checkpoint.")
    args = parser.parse_args()

    load_env()
    tag_names = load_tag_names()
    posts = fetch_posts(INFO_CATEGORY) + fetch_posts(UNCATEGORIZED)
    print(f"Fetched {len(posts)} posts in info+uncategorized")

    # dedupe by id
    by_id: dict[int, dict] = {}
    for post in posts:
        by_id[int(post["id"])] = post
    posts = list(by_id.values())

    decisions: list[tuple[int, str, str]] = []
    for post in posts:
        raw_tags = post.get("tags") or []
        if isinstance(raw_tags, dict):
            tag_ids = [int(t) for t in raw_tags.keys()]
        else:
            tag_ids = [int(t) for t in raw_tags]
        slug = target_category(tag_ids, tag_names)
        title = (post.get("title") or {}).get("rendered", "")[:60]
        decisions.append((int(post["id"]), slug, title))

    from collections import Counter

    counts = Counter(slug for _pid, slug, _t in decisions)
    print("=== TARGET DISTRIBUTION ===")
    for slug, count in counts.most_common():
        print(f"{slug}: {count}")

    if not args.apply:
        sample = decisions[:15]
        for pid, slug, title in sample:
            print(f"  {pid} -> {slug}: {title}")
        print("\nDRY RUN — no changes made. Re-run with --apply to update.")
        return 0

    start = args.offset
    if start < 0:
        start = 0
        if CHECKPOINT_FILE.exists():
            start = int(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")).get("next", 0))
    window = decisions[start:]
    if args.limit:
        window = window[: args.limit]
    print(f"\nApplying updates to {len(window)} posts (offset={start})...")
    updated = 0
    failed: list[str] = []
    for index, (post_id, slug, title) in enumerate(window):
        ok = False
        for attempt in range(4):
            try:
                wp_request(
                    f"posts/{post_id}",
                    payload={"categories": [CATEGORIES[slug]]},
                    method="POST",
                )
                ok = True
                break
            except Exception as exc:
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                else:
                    failed.append(f"{post_id} ({slug}): {exc}")
        if ok:
            updated += 1
        if (index + 1) % 25 == 0:
            done = start + index + 1
            CHECKPOINT_FILE.write_text(json.dumps({"next": done}), encoding="utf-8")
            print(f"  ...{done}/{len(decisions)} updated (checkpoint={done})")
        time.sleep(0.45)

    print(f"\nDone: {updated} updated, {len(failed)} failed")
    for failure in failed[:10]:
        print(f"  FAILED {failure}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
