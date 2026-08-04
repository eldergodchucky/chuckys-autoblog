"""Analyze tag inventory and propose a junk-tag deletion list (dry-run by default).

Junk rules:
- Tags that are pure numbers or years (2026, 150, 800, 000mah...)
- Tags with only digits plus unit-ish suffixes
- Single-word lowercase tags that are generic English words and used very few times
- Known spam/brand noise tags (9to5mac, a12, a13, etc.)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_pages import load_env, wp_request  # noqa: E402

TAGS_FILE = Path(r"C:\Users\ELDERCHUCKY\AppData\Local\Temp\opencode\site_tags.json")

GENERIC_WORDS = {
    "able", "ability", "abroad", "absorb", "access", "advanced", "agency", "air",
    "available", "black", "blue", "body", "brain", "build", "building", "center",
    "change", "changes", "chip", "chips", "color", "comes", "create", "current",
    "data", "day", "days", "design", "device", "devices", "display", "edge",
    "features", "firmware", "follow", "found", "free", "future", "game", "games",
    "give", "goes", "good", "great", "green", "group", "home", "hours", "inside",
    "issue", "issues", "keep", "known", "last", "latest", "life", "line", "look",
    "looks", "make", "makes", "making", "model", "models", "month", "months",
    "need", "needs", "new", "news", "next", "old", "one", "open", "options",
    "part", "parts", "people", "phone", "phones", "post", "power", "price",
    "prices", "read", "ready", "red", "report", "reports", "review", "reviews",
    "right", "sale", "sales", "save", "second", "service", "services", "show",
    "shows", "smart", "software", "something", "speed", "start", "state", "states",
    "still", "store", "support", "system", "systems", "tech", "test", "testing",
    "things", "time", "today", "top", "total", "trade", "update", "updates",
    "user", "users", "value", "video", "videos", "view", "ways", "week", "weeks",
    "white", "work", "works", "world", "year", "years",
}

PURE_NUMBER = re.compile(r"^\d+$")
YEAR = re.compile(r"^(?:19|20)\d\d$")
ORDINAL = re.compile(r"^\d+(?:st|nd|rd|th)$", re.IGNORECASE)
DECADE = re.compile(r"^\d{4}s$")
UNIT_SUFFIX = re.compile(r"^\d+(?:mah|gb|mb|tb|km|v|w|hz|mhz|ghz|bit|bit|core|mp|fps|kwh|wh)$", re.IGNORECASE)

EXPLICIT_JUNK = {
    "9to5mac", "hackaday", "bgr", "gsmarena", "ubergizmo",
    "a12", "a13",
    "able", "ability", "absorb", "aas", "abroad",
}


def load_tags() -> list[dict]:
    return json.loads(TAGS_FILE.read_text(encoding="utf-8"))


def main() -> int:
    load_env()
    tags = load_tags()
    name_to_id: dict[str, int] = {}
    for tag in tags:
        name_to_id[str(tag["name"]).strip().lower()] = int(tag["id"])

    junk: list[tuple[str, int]] = []
    for tag in tags:
        name = str(tag["name"]).strip()
        lower = name.lower()
        count = int(tag.get("count") or 0)
        if not name:
            continue
        if PURE_NUMBER.match(name) or YEAR.match(name) or ORDINAL.match(name) or DECADE.match(name):
            junk.append((name, count))
            continue
        if UNIT_SUFFIX.match(lower):
            junk.append((name, count))
            continue
        if lower in EXPLICIT_JUNK:
            junk.append((name, count))
            continue
        if (
            count <= 3
            and " " not in name
            and name.islower()
            and lower in GENERIC_WORDS
        ):
            junk.append((name, count))

    junk.sort(key=lambda entry: (-entry[1], entry[0]))
    print(f"Total tags: {len(tags)}  |  Junk candidates: {len(junk)}")
    print("\n=== JUNK LIST (name | count) ===")
    for name, count in junk:
        print(f"{name} | {count}")

    path = Path(r"C:\Users\ELDERCHUCKY\AppData\Local\Temp\opencode\junk_tags.json")
    path.write_text(json.dumps(junk, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
