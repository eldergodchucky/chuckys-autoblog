from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wp_auto_blog

SEARCH_TERMS = [
    "hack", "hacking", "crack", "cracking", "cracked", "keygen", "torrent",
    "course", "courses", "udemy", "download", "downloads", "free download",
    "pirated", "mod apk", "cheat",
]

HARMLESS_WORDS = [
    "health", "healthcare", "hackathon", "safe", "security", "free software",
    "open source", "open-source", "legit", "legal", "lawful", "license",
    "tutorial for", "how to", "career", "job", "jobs", "training",
]

# Posts manually verified as legitimate that must never be trashed by this script.
KEEP_POST_IDS = [76, 127]


def load_env() -> None:
    wp_auto_blog.load_env()


def rendered(post: dict, key: str) -> str:
    value = post.get(key) or {}
    if isinstance(value, dict):
        return str(value.get("rendered") or "")
    return str(value)


def is_candidate(post: dict, terms: list[str], harmless: list[str]) -> tuple[bool, str | None]:
    text = " ".join(
        [
            rendered(post, "title"),
            rendered(post, "content"),
            rendered(post, "excerpt"),
        ]
    ).lower()
    if not text:
        return False, None
    lowered_terms = [term.lower() for term in terms]
    lowered_harmless = [word.lower() for word in harmless]
    matched = next((term for term in lowered_terms if term in text), None)
    if not matched:
        return False, None
    if any(word in text for word in lowered_harmless):
        return False, matched
    return True, matched


def fetch_posts(after: str, before: str, per_page: int = 100) -> list[dict]:
    results: list[dict] = []
    page = 1
    while True:
        params = [
            f"after={quote(after)}",
            f"before={quote(before)}",
            "status=publish,pending,draft",
            f"per_page={per_page}",
            f"page={page}",
            "_fields=id,date,status,title,link",
        ]
        url = "posts?" + "&".join(params)
        try:
            batch = wp_auto_blog.wp_request(url)
        except Exception as exc:
            print(f"  API error on page {page}: {exc}")
            break
        if not isinstance(batch, list) or not batch:
            break
        results.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return results


def quote(value: str) -> str:
    import urllib.parse
    return urllib.parse.quote(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find and trash old hacking/cracking/course/download posts (2020-2021)."
    )
    parser.add_argument("--trash", action="store_true", help="Actually move matching posts to trash (default: dry-run).")
    parser.add_argument("--after", default="2020-01-01T00:00:00", help="Start date (ISO).")
    parser.add_argument("--before", default="2021-07-01T00:00:00", help="End date (ISO).")
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds.")
    parser.add_argument("--enrich", action="store_true", help="Fetch full content for candidates before listing.")
    parser.add_argument("--json", action="store_true", help="Print results as JSON to stdout.")
    args = parser.parse_args()

    load_env()
    if not os.getenv("WP_BASE_URL"):
        print("WP_BASE_URL not set in .env.", file=sys.stderr)
        return 2
    os.environ["REQUEST_TIMEOUT_SECONDS"] = str(args.timeout)

    candidates: dict[str, dict] = {}
    all_posts = fetch_posts(args.after, args.before, args.per_page)
    for post in all_posts:
        post_id = post.get("id")
        if post_id in candidates:
            continue
        if post_id in KEEP_POST_IDS:
            continue
        ok, matched = is_candidate(post, SEARCH_TERMS, HARMLESS_WORDS)
        if ok:
            post["_matched_term"] = matched
            candidates[post_id] = post

    if args.enrich and candidates:
        print(f"Enriching {len(candidates)} candidate(s) with full content...")
        for post_id in list(candidates):
            try:
                full = wp_auto_blog.wp_request(f"posts/{post_id}")
                if isinstance(full, dict):
                    candidates[post_id].update(full)
            except Exception as exc:
                print(f"  Could not fetch content for #{post_id}: {exc}")

    ordered = sorted(
        candidates.values(),
        key=lambda p: (str((p.get("date") or "")), int(p.get("id") or 0)),
    )

    if args.json:
        summary = {
            "dry_run": not args.trash,
            "count": len(ordered),
            "posts": [
                {
                    "id": p.get("id"),
                    "date": p.get("date"),
                    "title": (p.get("title") or {}).get("rendered"),
                    "status": p.get("status"),
                    "link": p.get("link"),
                    "matched": p.get("_matched_term"),
                }
                for p in ordered
            ],
        }
        print(json.dumps(summary, indent=2))
        return 0

    print(f"Found {len(ordered)} candidate post(s) in {args.after}..{args.before}")
    for p in ordered:
        print(
            f"  #{p.get('id')} [{p.get('date')}] ({p.get('status')}) "
            f"matched:'{p.get('_matched_term')}' :: {(p.get('title') or {}).get('rendered')}"
        )

    if not args.trash:
        print("\nDry run. Re-run with --trash to move these to the trash bin.")
        return 0

    trashed: list[int] = []
    failed: list[tuple[int, str]] = []
    for p in ordered:
        post_id = p.get("id")
        try:
            result = wp_auto_blog.wp_request(f"posts/{post_id}", method="DELETE")
            trashed.append(post_id)
            print(f"  Trashed #{post_id}")
        except Exception as exc:
            failed.append((post_id, str(exc)))
            print(f"  FAILED #{post_id}: {exc}")

    print(f"\nTrashed {len(trashed)} post(s); {len(failed)} failed.")
    for post_id, error in failed:
        print(f"  #{post_id}: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
