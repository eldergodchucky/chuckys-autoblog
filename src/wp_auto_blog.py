#!/usr/bin/env python3
"""Fetch RSS sources, generate original cited articles, and post to WordPress."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import smtplib
import sqlite3
import sys
import time
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
ENV_PATH = ROOT / ".env"
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
IMAGE_DIR = OUT_DIR / "images"
DB_PATH = DATA_DIR / "autoblog.sqlite3"
RUN_STATUS_PATH = DATA_DIR / "last_run_status.json"
RUN_LOCK_PATH = DATA_DIR / "autoblog.lock"

USER_AGENT = "WordPressAutoBlog/0.1 (+https://wordpress.org/)"
DEFAULT_MODEL = "gpt-5-mini"
GENERATOR_FREE = "free"
GENERATOR_OPENAI = "openai"
POST_METHOD_EMAIL = "email"
POST_METHOD_REST = "rest"
HERO_IMAGE_PLACEHOLDER = "__HERO_IMAGE_SRC__"

STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "among",
    "and",
    "are",
    "because",
    "before",
    "being",
    "between",
    "best",
    "can",
    "called",
    "could",
    "daily",
    "delusion",
    "especially",
    "first",
    "for",
    "free",
    "from",
    "get",
    "gets",
    "got",
    "has",
    "have",
    "how",
    "into",
    "its",
    "just",
    "latest",
    "last",
    "like",
    "made",
    "make",
    "may",
    "might",
    "more",
    "most",
    "near",
    "new",
    "now",
    "one",
    "out",
    "over",
    "plus",
    "pro",
    "reality",
    "researchers",
    "says",
    "than",
    "that",
    "the",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "top",
    "two",
    "under",
    "use",
    "using",
    "what",
    "when",
    "where",
    "who",
    "why",
    "will",
    "with",
    "would",
    "your",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    category: str
    quality: int


@dataclass(frozen=True)
class Item:
    uid: str
    source_name: str
    source_url: str
    source_category: str
    source_quality: int
    title: str
    link: str
    summary: str
    published_at: dt.datetime | None
    image_url: str | None = None

    @property
    def sort_time(self) -> dt.datetime:
        return self.published_at or dt.datetime.now(dt.timezone.utc)


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


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_run_status(state: str, message: str, **details: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "message": message,
        "finished_at": utc_now_iso(),
        **details,
    }
    temp_path = RUN_STATUS_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(RUN_STATUS_PATH)


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def process_exists(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire_run_lock() -> tuple[bool, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stale_after = max(300, env_int("RUN_LOCK_STALE_SECONDS", 1800))
    now = time.time()
    if RUN_LOCK_PATH.exists():
        lock_info = read_json_file(RUN_LOCK_PATH)
        try:
            lock_pid = int(lock_info.get("pid") or 0)
        except (TypeError, ValueError):
            lock_pid = 0
        created_epoch = float(lock_info.get("created_at_epoch") or 0)
        age = now - created_epoch if created_epoch else stale_after + 1
        if age < stale_after and process_exists(lock_pid):
            return False, f"Another publisher run appears active; lock age is {int(age)} seconds."
        try:
            RUN_LOCK_PATH.unlink()
        except OSError as exc:
            return False, f"Stale publisher lock could not be cleared: {exc}"

    payload = {
        "pid": os.getpid(),
        "created_at": utc_now_iso(),
        "created_at_epoch": now,
    }
    try:
        fd = os.open(str(RUN_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False, "Another publisher run started first."
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return True, "Publisher lock acquired."


def release_run_lock() -> None:
    lock_info = read_json_file(RUN_LOCK_PATH)
    if lock_info.get("pid") != os.getpid():
        return
    try:
        RUN_LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def strip_html(value: str) -> str:
    parser = TextExtractor()
    parser.feed(html.unescape(value or ""))
    return parser.text()


def fix_mojibake(value: str) -> str:
    if "Ã¢" in value or "Ãƒ" in value:
        try:
            value = value.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
    replacements = {
        "Ã¢â‚¬â„¢": "'",
        "Ã¢â‚¬Ëœ": "'",
        "Ã¢â‚¬Å“": '"',
        "Ã¢â‚¬Â": '"',
        "Ã¢â‚¬â€œ": "-",
        "Ã¢â‚¬â€": "-",
        "Ã¢â‚¬Â¦": "...",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return value


def clean_text(value: str, max_len: int = 500) -> str:
    value = fix_mojibake(strip_html(value))
    for bad, good in {
        "Ã¢â‚¬â„¢": "'",
        "Ã¢â‚¬Ëœ": "'",
        "Ã¢â‚¬Å“": '"',
        "Ã¢â‚¬Â": '"',
        "Ã¢â‚¬â€œ": "-",
        "Ã¢â‚¬â€": "-",
        "Ã¢â‚¬Â¦": "...",
        "\u00e2\u20ac\u2122": "'",
        "\u00e2\u20ac\u02dc": "'",
        "\u00e2\u20ac\u0153": '"',
        "\u00e2\u20ac\u009d": '"',
        "\u00e2\u20ac\u201c": "-",
        "\u00e2\u20ac\u201d": "-",
        "\u00e2\u20ac\u00a6": "...",
    }.items():
        value = value.replace(bad, good)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rsplit(" ", 1)[0] + "..."


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
    query = [(k, v) for k, v in query if k.lower() not in {"fbclid", "gclid"}]
    cleaned = parsed._replace(query=urllib.parse.urlencode(query), fragment="")
    return urllib.parse.urlunsplit(cleaned)


def stable_id(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def request_bytes(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and child.text:
            return child.text.strip()
    return ""


def child_attr(element: ET.Element, name: str, attr: str) -> str:
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag == name and child.attrib.get(attr):
            return child.attrib[attr].strip()
    return ""


def item_image_url(element: ET.Element) -> str | None:
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1].lower()
        url = child.attrib.get("url", "").strip()
        media_type = child.attrib.get("type", "").lower()
        if tag in {"thumbnail", "image"} and url:
            return canonical_url(url)
        if tag in {"content", "enclosure"} and url and media_type.startswith("image/"):
            return canonical_url(url)
    return None


def parse_feed(feed: Feed, raw_xml: bytes) -> list[Item]:
    root = ET.fromstring(raw_xml)
    root_tag = root.tag.rsplit("}", 1)[-1].lower()

    if root_tag == "rss":
        entries = root.findall("./channel/item")
    elif root_tag == "feed":
        entries = [child for child in list(root) if child.tag.rsplit("}", 1)[-1].lower() == "entry"]
    else:
        entries = root.findall(".//item")

    items: list[Item] = []
    for entry in entries:
        title = clean_text(child_text(entry, ("title",)), max_len=180)
        link = child_text(entry, ("link",))
        if not link:
            link = child_attr(entry, "link", "href")
        link = canonical_url(link)
        summary = clean_text(
            child_text(entry, ("description", "summary", "content", "encoded")),
            max_len=700,
        )
        published = parse_date(child_text(entry, ("pubdate", "published", "updated", "dc:date")))
        guid = child_text(entry, ("guid", "id")) or link or title
        if not title or not link:
            continue
        items.append(
            Item(
                uid=stable_id(feed.name, guid, link),
                source_name=feed.name,
                source_url=feed.url,
                source_category=feed.category,
                source_quality=feed.quality,
                title=title,
                link=link,
                summary=summary,
                published_at=published,
                image_url=item_image_url(entry),
            )
        )
    return items


def load_config(path: Path = CONFIG_PATH) -> list[Feed]:
    data = json.loads(path.read_text(encoding="utf-8"))
    blocklist = {
        domain.strip().lower()
        for domain in os.getenv("BLOCKLIST_DOMAINS", "").split(",")
        if domain.strip()
    }
    feeds = []
    for item in data.get("feeds", []):
        if not item.get("enabled", True):
            continue
        domain = urllib.parse.urlsplit(item["url"]).netloc.lower()
        if domain in blocklist:
            continue
        feeds.append(
            Feed(
                name=item["name"],
                url=item["url"],
                category=item.get("category", "tech"),
                quality=int(item.get("quality", 3)),
            )
        )
    return feeds


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            uid TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_category TEXT NOT NULL,
            source_quality INTEGER NOT NULL DEFAULT 3,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT NOT NULL,
            published_at TEXT,
            image_url TEXT,
            first_seen_at TEXT NOT NULL,
            used_at TEXT
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    if "source_quality" not in columns:
        conn.execute("ALTER TABLE items ADD COLUMN source_quality INTEGER NOT NULL DEFAULT 3")
    if "image_url" not in columns:
        conn.execute("ALTER TABLE items ADD COLUMN image_url TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_key TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            wp_id INTEGER,
            categories_json TEXT,
            source_links_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    post_columns = {row[1] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
    if "categories_json" not in post_columns:
        conn.execute("ALTER TABLE posts ADD COLUMN categories_json TEXT")
    conn.commit()
    return conn


def save_items(conn: sqlite3.Connection, items: list[Item]) -> int:
    inserted = 0
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for item in items:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO items (
                uid, source_name, source_url, source_category, source_quality, title, link, summary,
                published_at, image_url, first_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.uid,
                item.source_name,
                item.source_url,
                item.source_category,
                item.source_quality,
                item.title,
                item.link,
                item.summary,
                item.published_at.isoformat() if item.published_at else None,
                item.image_url,
                now,
            ),
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted


def fetch_all(feeds: list[Feed], timeout: int) -> tuple[list[Item], list[str]]:
    items: list[Item] = []
    errors: list[str] = []
    for feed in feeds:
        try:
            raw_xml = request_bytes(feed.url, timeout)
            items.extend(parse_feed(feed, raw_xml))
        except (ET.ParseError, urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{feed.name}: {exc}")
    return items, errors


def recent_unused_items(conn: sqlite3.Connection, lookback_hours: int) -> list[Item]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    rows = conn.execute(
        """
        SELECT uid, source_name, source_url, source_category, source_quality, title, link, summary, published_at, image_url
        FROM items
        WHERE used_at IS NULL
        ORDER BY COALESCE(published_at, first_seen_at) DESC
        LIMIT 250
        """
    ).fetchall()
    items = []
    for row in rows:
        published = dt.datetime.fromisoformat(row[8]) if row[8] else None
        if published and published < cutoff:
            continue
        items.append(
            Item(
                uid=row[0],
                source_name=row[1],
                source_url=row[2],
                source_category=row[3],
                source_quality=int(row[4]),
                title=clean_text(row[5], max_len=180),
                link=row[6],
                summary=clean_text(row[7], max_len=700),
                published_at=published,
                image_url=row[9],
            )
        )
    return items


def tokens_for(item: Item) -> set[str]:
    text = f"{item.title} {item.summary}".lower()
    tokens = re.findall(r"[a-z][a-z0-9]{2,}", text)
    return {token for token in tokens if token not in STOPWORDS and len(token) > 2}


def item_domain(item: Item) -> str:
    domain = urllib.parse.urlsplit(item.link).netloc.lower()
    return domain[4:] if domain.startswith("www.") else domain


def focus_keywords() -> list[str]:
    raw = os.getenv(
        "TOPIC_FOCUS_KEYWORDS",
        (
            "science,scientists,research,researchers,breakthrough,discovery,experiment,study,physics,biology,"
            "chemistry,climate,energy,robotics,space,nasa,astronomy,planet,moon,mars,telescope,galaxy,"
            "phone,phones,iphone,ios,android,apple,samsung,pixel,gadget,gadgets,ai,software,apps,innovation"
        ),
    )
    return [value.strip().lower() for value in raw.split(",") if value.strip()]


def env_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [value.strip().lower() for value in raw.split(",") if value.strip()]


def focus_score(cluster: list[Item]) -> int:
    haystack = " ".join(
        f"{item.source_category} {item.source_name} {item.title} {item.summary}"
        for item in cluster
    ).lower()
    score = 0
    for keyword in focus_keywords():
        if keyword in haystack:
            score += 1
    return score


def single_source_categories() -> set[str]:
    return set(env_list("SINGLE_SOURCE_PRIORITY_CATEGORIES", "science,space"))


def can_use_single_source_cluster(item: Item) -> bool:
    if not env_bool("ALLOW_SINGLE_SOURCE_PRIORITY_POSTS", True):
        return False
    if item.source_quality < env_int("SINGLE_SOURCE_MIN_QUALITY", 4):
        return False
    categories = set(story_categories([item], item.title, list(tokens_for(item))[:6]))
    categories.add(item.source_category.lower())
    return bool(categories & single_source_categories())


def env_weight_map(name: str, default: dict[str, int]) -> dict[str, int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    weights = default.copy()
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        try:
            weights[key.strip().lower()] = int(value.strip())
        except ValueError:
            continue
    return weights


def category_weights() -> dict[str, int]:
    return env_weight_map(
        "CATEGORY_WEIGHTS",
        {
            "science": 6,
            "space": 6,
            "ai": 6,
            "gadgets": 6,
            "security": 6,
            "tutorials": 6,
            "hacks": 6,
            "phones": 6,
            "apple": 6,
            "android": 6,
            "software": 6,
            "health": 6,
            "tech": 4,
        },
    )


def category_rotation() -> list[str]:
    rotation = env_list(
        "CATEGORY_ROTATION",
        "science,space,ai,gadgets,phones,android,apple,software,security,tutorials,hacks,health",
    )
    return rotation


def cluster_categories(cluster: list[Item]) -> list[str]:
    return story_categories(cluster, topic_from_cluster(cluster), top_keywords(cluster, 6))


def editorial_priority_score(cluster: list[Item]) -> int:
    weights = category_weights()
    categories = cluster_categories(cluster)
    score = sum(weights.get(category, 0) for category in categories)
    text = " ".join(f"{item.title} {item.summary} {item.source_category}" for item in cluster).lower()
    for keyword in ("breakthrough", "discovery", "scientists", "researchers", "study", "nasa", "space", "astronomy"):
        if keyword in text:
            score += 2
    return score


def is_deal_roundup(cluster: list[Item]) -> bool:
    text = story_text(cluster)
    deal_terms = ("prime day", "black friday", "cyber monday", "deal", "deals", "discount", "sale", "coupon", "bargain")
    roundup_terms = ("best of", "favorite", "favorites", "roundup", "we found", "worth shopping", "shopping now")
    return has_term(text, deal_terms) and has_term(text, roundup_terms)


def cluster_detail_score(cluster: list[Item]) -> int:
    score = 0
    text = story_text(cluster)
    score += min(6, len({item.source_name for item in cluster}) * 2)
    for item in cluster:
        title = clean_text(item.title, max_len=180)
        summary = clean_text(item.summary, max_len=360)
        if len(summary.split()) >= 18 and summary.lower() != title.lower():
            score += 2
        if re.search(r"\d", title + " " + summary):
            score += 1
    for term in (
        "research",
        "study",
        "announced",
        "launched",
        "released",
        "reported",
        "update",
        "security",
        "vulnerability",
        "mission",
        "experiment",
        "clinical",
        "trial",
        "feature",
        "policy",
        "price",
    ):
        if term in text:
            score += 1
    return score


def publishable_cluster(cluster: list[Item]) -> bool:
    if is_deal_roundup(cluster):
        return False
    return cluster_detail_score(cluster) >= env_int("MIN_CLUSTER_DETAIL_SCORE", 5)


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def build_clusters(items: list[Item], min_sources: int) -> list[list[Item]]:
    scored = sorted(items, key=lambda item: (item.sort_time, item.source_name), reverse=True)
    item_tokens = {item.uid: tokens_for(item) for item in scored}
    clusters: list[list[Item]] = []
    used: set[str] = set()

    for item in scored:
        if item.uid in used:
            continue
        cluster = [item]
        used.add(item.uid)
        cluster_links = {item.link}
        cluster_domains = {item_domain(item)}
        for candidate in scored:
            if candidate.uid in used:
                continue
            if candidate.link in cluster_links:
                continue
            candidate_domain = item_domain(candidate)
            if candidate_domain in cluster_domains:
                continue
            if candidate.source_name == item.source_name and len(cluster) < min_sources:
                continue
            shared_terms = item_tokens[item.uid] & item_tokens[candidate.uid]
            if len(shared_terms) < 2:
                continue
            similarity = jaccard(item_tokens[item.uid], item_tokens[candidate.uid])
            same_category = item.source_category == candidate.source_category
            if similarity >= 0.16 or (same_category and similarity >= 0.10):
                cluster.append(candidate)
                used.add(candidate.uid)
                cluster_links.add(candidate.link)
                cluster_domains.add(candidate_domain)
            if len(cluster) >= 4:
                break
        unique_domains = {item_domain(member) for member in cluster}
        if len(unique_domains) >= min_sources and publishable_cluster(cluster):
            clusters.append(cluster)
        elif len(cluster) == 1 and can_use_single_source_cluster(cluster[0]) and publishable_cluster(cluster):
            clusters.append(cluster)

    return sorted(
        clusters,
        key=lambda cluster: (
            editorial_priority_score(cluster),
            focus_score(cluster),
            len({item.source_name for item in cluster}),
            sum(item.source_quality for item in cluster),
            max(item.sort_time for item in cluster),
        ),
        reverse=True,
    )


def topic_key(cluster: list[Item]) -> str:
    tokens = []
    for item in cluster:
        tokens.extend(sorted(tokens_for(item)))
    top = sorted(set(tokens), key=tokens.count, reverse=True)[:8]
    return stable_id(*top, *sorted(item.link for item in cluster))


def build_generation_prompt(cluster: list[Item]) -> str:
    source_blocks = []
    for idx, item in enumerate(cluster, start=1):
        source_blocks.append(
            "\n".join(
                [
                    f"Source {idx}: {item.source_name}",
                    f"Category: {item.source_category}",
                    f"Published: {item.published_at.isoformat() if item.published_at else 'unknown'}",
                    f"Title: {item.title}",
                    f"URL: {item.link}",
                    f"Summary: {item.summary or 'No summary provided.'}",
                ]
            )
        )

    return f"""
Write one original, comprehensive, and straight professional news/analysis article for a high-quality publication covering technology, science, health research, gadgets, tutorials, or practical insights.

Use the source briefs below as reporting inputs. Synthesize the shared theme, add substantial facts/context, and keep claims tied to the sources. The article must be a straight, professional piece.

DO NOT use formulaic, repetitive, or generic section labels like "What Happened", "Why It Matters", "What Readers Learn", "What to Watch", "The Catch", "Bottom Line", "Known Details", or any other generic "AI slop" headers. Instead, structure the article using natural, descriptive, and topical subheadings (h2 and h3) that flow directly from the subject matter itself (for example, refer to specific technologies, organizations, clinical methods, or market forces).

Editorial voice:
- Write in a premium editorial voice: sophisticated, analytical, nuanced, authoritative, straight-forward, and polished.
- Do not use generic filler, AI buzzwords, or repetitive introductory phrases.
- Every paragraph must be elaborative and contain concrete facts, technical details, named actors, or reader-facing implications.
- For health and medical topics, maintain factual objectivity, cite clinical details/organizations from the sources, and include a standard medical disclaimer at the end of the text.
- The article should be significantly longer, reading like a real, detailed professional article.

Return valid JSON only with these keys:
- title: string (compelling, professional headline)
- slug: lowercase URL slug
- excerpt: comprehensive 2-3 sentence summary (keep it straight and factual, no "why it matters" or "what readers learn")
- categories: array of 1-3 broad category names
- tags: array of 8-12 specific, relevant tags
- html: WordPress-ready HTML string
- meta_description: string (155-160 characters for SEO, straight and factual)
- focus_keyword: string (primary SEO keyword)

HTML requirements:
- 1000 to 1500 words for comprehensive coverage.
- Use h2 and h3 headings for clear structure, using natural topical titles.
- Use natural inline attribution when needed; do not add a source-list section.
- Do not include scripts, iframes, tracking pixels, or affiliate links.
- For health content, include appropriate medical disclaimer at the end.

SEO requirements:
- Include the focus keyword naturally in the title, first paragraph, and at least one subheading.
- Write a straight and factual meta_description that includes the focus keyword.
- Use semantic HTML with proper heading hierarchy.

Sources:

{chr(10).join(source_blocks)}
""".strip()


def openai_generate_article(cluster: list[Item]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to generate article text.")

    payload = {
        "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        "instructions": (
            "You are a careful technology editor writing polished analytical news features. "
            "Create original, cited posts with clear judgement, restrained prose, and useful context. "
            "Do not imitate any named publication directly. Do not plagiarize, fabricate, or overstate source claims."
        ),
        "input": build_generation_prompt(cluster),
        "max_output_tokens": env_int("OPENAI_MAX_OUTPUT_TOKENS", 2400),
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    timeout = env_int("REQUEST_TIMEOUT_SECONDS", 25)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed: HTTP {exc.code}: {body}") from exc

    text = extract_response_text(data)
    return parse_article_json(text)


def extract_response_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"])
    parts: list[str] = []
    for output in data.get("output", []):
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenAI response did not contain output text.")
    return text


def parse_article_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise RuntimeError("Generated article was not JSON.")
    article = json.loads(match.group(0))
    required = {"title", "slug", "excerpt", "categories", "tags", "html"}
    optional = {"meta_description", "focus_keyword"}
    missing = required - set(article)
    if missing:
        raise RuntimeError(f"Generated article missing keys: {', '.join(sorted(missing))}")
    # Add optional fields with defaults if missing
    if "meta_description" not in article:
        article["meta_description"] = article["excerpt"][:155]
    if "focus_keyword" not in article:
        article["focus_keyword"] = top_keywords_from_text(article["title"] + " " + article["excerpt"], 1)[0] if article.get("excerpt") else "technology"
    return article


def top_keywords_from_text(text: str, limit: int = 5) -> list[str]:
    text_lower = text.lower()
    tokens = re.findall(r"[a-z][a-z0-9]{2,}", text_lower)
    counts: dict[str, int] = {}
    for token in tokens:
        if token not in STOPWORDS and len(token) > 2:
            counts[token] = counts.get(token, 0) + 1
    return [
        token
        for token, _count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
    ]


def top_keywords(cluster: list[Item], limit: int = 5) -> list[str]:
    counts: dict[str, int] = {}
    for item in cluster:
        for token in tokens_for(item):
            counts[token] = counts.get(token, 0) + 1
    return [
        token
        for token, _count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
    ]


def title_case_keywords(words: list[str]) -> str:
    if not words:
        return "Tech Signals"
    clean_words = [word for word in words if word not in {"called", "coming", "latest", "powered"}]
    if not clean_words:
        clean_words = words
    return " ".join(word.upper() if len(word) <= 3 else word.capitalize() for word in clean_words[:4])


def compact_topic_from_title(title: str) -> str:
    text = clean_text(title, max_len=110)
    text = re.sub(r"\s+", " ", text).strip(" .,:;|-")
    for separator in (" - ", " -- ", " | ", ","):
        if separator not in text:
            continue
        candidate = text.split(separator, 1)[0].strip(" .,:;|-")
        if candidate and len(candidate.split()) >= 4:
            text = candidate
            break
    words = text.split()
    if len(words) > 12:
        text = " ".join(words[:12]).strip(" .,:;|-")
    bad_end_words = {"a", "an", "and", "as", "at", "for", "from", "if", "in", "of", "on", "or", "the", "to", "with", "you"}
    words = text.split()
    while len(words) > 4 and words[-1].lower().strip(".,:;!?") in bad_end_words:
        words.pop()
    text = " ".join(words).strip(" .,:;|-")
    return text or "Tech Signals"


def topic_from_cluster(cluster: list[Item]) -> str:
    candidates = [compact_topic_from_title(item.title) for item in cluster]
    clean = [candidate for candidate in candidates if 4 <= len(candidate.split()) <= 12]
    if not clean:
        return candidates[0] if candidates else "Tech Signals"
    return sorted(clean, key=lambda value: (abs(len(value.split()) - 8), len(value)))[0]


def load_image_font(size: int, bold: bool = False) -> Any:
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_for_image(draw: Any, text: str, font: Any, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        left, top, right, bottom = draw.textbbox((0, 0), candidate, font=font)
        if right - left <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".") + "..."
    return lines


def create_hero_image(title: str, keywords: list[str], categories: list[str], source_image_urls: list[str] | None = None) -> Path | None:
    image_mode = os.getenv("HERO_IMAGE_MODE", "real").strip().lower()
    if image_mode == "off":
        return None
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return None

    def hex_to_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

    def cover_resize(image: Any, width: int, height: int) -> Any:
        image = image.convert("RGB")
        source_w, source_h = image.size
        target_ratio = width / height
        source_ratio = source_w / source_h
        if source_ratio > target_ratio:
            crop_w = int(source_h * target_ratio)
            left = max(0, (source_w - crop_w) // 2)
            image = image.crop((left, 0, left + crop_w, source_h))
        else:
            crop_h = int(source_w / target_ratio)
            top = max(0, (source_h - crop_h) // 2)
            image = image.crop((0, top, source_w, top + crop_h))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    def download_source_image(urls: list[str] | None) -> Any | None:
        if not urls:
            return None
        timeout = env_int("REQUEST_TIMEOUT_SECONDS", 25)
        for url in urls:
            if not url or not url.startswith(("http://", "https://")):
                continue
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read(8_000_000)
                image = Image.open(io.BytesIO(raw))
                if image.width < 360 or image.height < 220:
                    continue
                return image
            except (OSError, urllib.error.URLError, TimeoutError):
                continue
        return None

    def save_real_thumbnail(source_image: Any, theme: str, accent: str, text_color: str) -> Path:
        background = cover_resize(source_image, width, height).convert("RGBA")
        dim = Image.new("RGBA", (width, height), (0, 0, 0, 36))
        background.alpha_composite(dim)
        draw_local = ImageDraw.Draw(background)
        shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shade_draw = ImageDraw.Draw(shade)
        shade_draw.rectangle((0, 0, width, 120), fill=(0, 0, 0, 92))
        shade_draw.rectangle((0, height - 150, width, height), fill=(0, 0, 0, 245))
        background.alpha_composite(shade)

        kicker_font = load_image_font(28, bold=True)
        meta_font = load_image_font(28, bold=True)
        draw_local.rounded_rectangle((58, 52, 360, 104), radius=16, fill=(2, 6, 23, 205), outline=(255, 255, 255, 48), width=1)
        draw_local.text((82, 65), "CHUCKYSCARNAGE", font=kicker_font, fill=accent)
        label = " / ".join(value.upper() for value in categories[:3]) or theme.upper()
        label_width = min(640, max(260, 28 * len(label)))
        draw_local.rounded_rectangle((58, 552, 58 + label_width, 612), radius=16, fill=(2, 6, 23, 218), outline=(255, 255, 255, 66), width=1)
        draw_local.text((82, 569), label, font=meta_font, fill="#f8fafc")
        path = IMAGE_DIR / f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slugify(title)}.png"
        background.convert("RGB").save(path, "PNG", optimize=True)
        return path

    def draw_gradient(draw: Any, width: int, height: int, start: str, end: str) -> None:
        start_rgb = hex_to_rgb(start)
        end_rgb = hex_to_rgb(end)
        for y in range(height):
            blend = y / max(1, height - 1)
            color = tuple(int(start_rgb[i] * (1 - blend) + end_rgb[i] * blend) for i in range(3))
            draw.line([(0, y), (width, y)], fill=color)

    def theme_for() -> str:
        text = " ".join([title, *keywords, *categories]).lower()
        if any(word in text for word in ("iphone", "ios", "airpods", "apple", "ipad", "mac")):
            return "apple"
        if any(word in text for word in ("android", "pixel", "samsung", "galaxy", "googlebook")):
            return "android"
        if any(word in text for word in ("ai", "chatgpt", "openai", "gemini", "model", "robot")):
            return "ai"
        if any(word in text for word in ("space", "nasa", "mars", "moon", "galaxy", "telescope", "astronom")):
            return "space"
        if any(word in text for word in ("security", "hack", "breach", "malware", "password")):
            return "security"
        if any(word in text for word in ("app", "software", "update", "developer")):
            return "software"
        if any(word in text for word in ("phone", "fold", "mobile")):
            return "phones"
        if any(word in text for word in ("watch", "wearable", "earbuds", "gadget", "device")):
            return "gadgets"
        return categories[0] if categories else "tech"

    def paste_shadowed(layer: Any, item: Any, xy: tuple[int, int], blur: int = 24) -> None:
        shadow = Image.new("RGBA", item.size, (0, 0, 0, 0))
        alpha = item.getchannel("A")
        shadow.putalpha(alpha)
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        layer.alpha_composite(shadow, (xy[0] + 18, xy[1] + 22))
        layer.alpha_composite(item, xy)

    def rounded_panel(size: tuple[int, int], radius: int, fill: str, outline: str = "#ffffff22") -> Any:
        panel = Image.new("RGBA", size, (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=fill, outline=outline, width=2)
        return panel

    def draw_phone(layer: Any, x: int, y: int, w: int, h: int, accent: str, mode: str) -> None:
        phone = rounded_panel((w, h), 52, "#0b1020", "#ffffff55")
        phone_draw = ImageDraw.Draw(phone)
        phone_draw.rounded_rectangle((16, 16, w - 16, h - 16), radius=42, fill="#111827")
        phone_draw.rounded_rectangle((w // 2 - 54, 28, w // 2 + 54, 48), radius=12, fill="#020617")
        if mode == "apple":
            colors = ["#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ef4444", "#14b8a6"]
        elif mode == "android":
            colors = ["#22c55e", "#84cc16", "#06b6d4", "#facc15", "#34d399", "#60a5fa"]
        else:
            colors = ["#38bdf8", "#a78bfa", "#34d399", "#f472b6", "#facc15", "#60a5fa"]
        for row in range(4):
            for col in range(3):
                left = 42 + col * 76
                top = 86 + row * 76
                color = colors[(row * 3 + col) % len(colors)]
                phone_draw.rounded_rectangle((left, top, left + 50, top + 50), radius=14, fill=color)
        phone_draw.rounded_rectangle((52, h - 142, w - 52, h - 78), radius=22, fill=accent)
        phone_draw.ellipse((w - 92, 72, w - 44, 120), fill="#020617", outline="#ffffff66", width=3)
        phone_draw.ellipse((w - 86, 78, w - 50, 114), fill="#172033")
        paste_shadowed(layer, phone.rotate(-8, expand=True, resample=Image.Resampling.BICUBIC), (x, y), 24)

    def draw_laptop(layer: Any, x: int, y: int, w: int, h: int, accent: str) -> None:
        laptop = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        laptop_draw = ImageDraw.Draw(laptop)
        laptop_draw.rounded_rectangle((40, 0, w - 40, h - 70), radius=26, fill="#101827", outline="#ffffff44", width=2)
        laptop_draw.rounded_rectangle((64, 28, w - 64, h - 104), radius=14, fill="#06101f")
        for idx in range(6):
            y_line = 58 + idx * 28
            laptop_draw.rounded_rectangle((92, y_line, 180 + idx * 34, y_line + 12), radius=6, fill=accent)
            laptop_draw.rounded_rectangle((240, y_line, w - 118, y_line + 12), radius=6, fill="#ffffff55")
        laptop_draw.polygon([(0, h - 70), (w, h - 70), (w - 90, h), (90, h)], fill="#1f2937")
        paste_shadowed(layer, laptop, (x, y), 18)

    def draw_ai_nodes(layer: Any, x: int, y: int, accent: str) -> None:
        node_layer = Image.new("RGBA", (430, 330), (0, 0, 0, 0))
        node_draw = ImageDraw.Draw(node_layer)
        nodes = [(80, 70), (210, 42), (330, 95), (120, 190), (260, 185), (350, 260)]
        for a, b in [(0, 1), (1, 2), (0, 3), (1, 4), (2, 4), (3, 4), (4, 5)]:
            node_draw.line((nodes[a], nodes[b]), fill="#ffffff66", width=4)
        for idx, (cx, cy) in enumerate(nodes):
            fill = accent if idx % 2 == 0 else "#f8fafc"
            node_draw.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=fill)
        paste_shadowed(layer, node_layer, (x, y), 14)

    def draw_space(layer: Any, x: int, y: int, accent: str) -> None:
        space = Image.new("RGBA", (430, 360), (0, 0, 0, 0))
        space_draw = ImageDraw.Draw(space)
        space_draw.ellipse((126, 72, 328, 274), fill="#1d4ed8", outline="#93c5fd", width=4)
        space_draw.arc((58, 120, 394, 246), start=12, end=170, fill=accent, width=8)
        space_draw.arc((52, 116, 400, 250), start=192, end=350, fill="#ffffff99", width=3)
        for sx, sy in [(42, 42), (360, 38), (82, 298), (382, 304), (250, 22)]:
            space_draw.ellipse((sx, sy, sx + 8, sy + 8), fill="#f8fafc")
        paste_shadowed(layer, space, (x, y), 18)

    def draw_gadgets(layer: Any, x: int, y: int, accent: str) -> None:
        gadgets = Image.new("RGBA", (450, 360), (0, 0, 0, 0))
        gadgets_draw = ImageDraw.Draw(gadgets)
        gadgets_draw.rounded_rectangle((70, 44, 250, 260), radius=44, fill="#111827", outline="#ffffff55", width=3)
        gadgets_draw.rounded_rectangle((92, 76, 228, 212), radius=24, fill="#020617")
        gadgets_draw.arc((122, 108, 198, 184), start=210, end=510, fill=accent, width=9)
        gadgets_draw.rounded_rectangle((300, 68, 360, 210), radius=28, fill="#f8fafc")
        gadgets_draw.ellipse((320, 198, 386, 264), fill="#f8fafc")
        gadgets_draw.rounded_rectangle((332, 206, 374, 246), radius=16, fill=accent)
        gadgets_draw.rounded_rectangle((142, 282, 330, 326), radius=16, fill="#1f2937")
        for idx in range(6):
            gadgets_draw.line((164 + idx * 28, 292, 178 + idx * 28, 316), fill=accent, width=3)
        paste_shadowed(layer, gadgets, (x, y), 18)

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 675
    base = Image.new("RGBA", (width, height), "#111827")
    draw = ImageDraw.Draw(base)
    theme = theme_for()
    palettes = {
        "apple": ("#f8fafc", "#cbd5e1", "#f8fafc", "#2563eb", "#111827"),
        "android": ("#052e16", "#0f766e", "#f8fafc", "#a3e635", "#06130d"),
        "phones": ("#172554", "#0f766e", "#f8fafc", "#38bdf8", "#06111f"),
        "ai": ("#111827", "#312e81", "#f8fafc", "#a78bfa", "#070a18"),
        "space": ("#020617", "#1e1b4b", "#f8fafc", "#38bdf8", "#020617"),
        "security": ("#111827", "#7f1d1d", "#f8fafc", "#fb7185", "#16070a"),
        "software": ("#0f172a", "#155e75", "#f8fafc", "#22d3ee", "#07121c"),
        "gadgets": ("#172554", "#14532d", "#f8fafc", "#facc15", "#08111d"),
        "science": ("#0f172a", "#164e63", "#f8fafc", "#38bdf8", "#08111d"),
        "tech": ("#111827", "#0f766e", "#f8fafc", "#22d3ee", "#07121c"),
    }
    start, end, text_color, accent, panel = palettes.get(theme, palettes["tech"])
    source_image = download_source_image(source_image_urls)
    if source_image and image_mode in {"real", "source", "auto"}:
        return save_real_thumbnail(source_image, theme, accent, "#f8fafc")

    draw_gradient(draw, width, height, start, end)

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle((48, 54, 720, 620), radius=34, fill=panel + "dd", outline="#ffffff22", width=2)
    for x_pos, y_pos, radius in [(790, 78, 300), (938, 286, 260), (728, 412, 180)]:
        overlay_draw.ellipse((x_pos, y_pos, x_pos + radius, y_pos + radius), outline=accent + "66", width=4)

    if theme in {"apple", "phones"}:
        draw_phone(overlay, 780, 106, 250, 460, accent, "apple")
        draw_phone(overlay, 940, 156, 210, 390, "#ffffff", "apple")
    elif theme == "android":
        draw_phone(overlay, 800, 104, 260, 470, accent, "android")
        draw_laptop(overlay, 708, 358, 430, 220, accent)
    elif theme == "ai":
        draw_laptop(overlay, 730, 284, 430, 230, accent)
        draw_ai_nodes(overlay, 760, 94, accent)
    elif theme == "space":
        draw_space(overlay, 730, 128, accent)
        draw_laptop(overlay, 760, 382, 370, 190, accent)
    elif theme == "software":
        draw_laptop(overlay, 720, 168, 440, 260, accent)
        draw_phone(overlay, 932, 286, 178, 320, accent, "generic")
    else:
        draw_gadgets(overlay, 725, 158, accent)
        draw_phone(overlay, 942, 126, 190, 350, accent, "generic")

    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)
    kicker_font = load_image_font(30, bold=True)
    title_font = load_image_font(50, bold=True)
    meta_font = load_image_font(28, bold=True)
    small_font = load_image_font(22)

    draw.text((82, 88), "CHUCKYSCARNAGE", font=kicker_font, fill=accent)
    lines = wrap_for_image(draw, title, title_font, 575, 5)
    y = 150
    for line in lines:
        draw.text((82, y), line, font=title_font, fill=text_color)
        y += 60

    label = " / ".join(value.upper() for value in categories[:3]) or theme.upper()
    draw.rounded_rectangle((82, 506, 606, 566), radius=16, fill="#020617cc", outline="#ffffff22", width=1)
    draw.text((104, 523), label, font=meta_font, fill=text_color)
    path = IMAGE_DIR / f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slugify(title)}.png"
    base.convert("RGB").save(path, "PNG", optimize=True)
    return path


def category_takeaway(categories: set[str]) -> str:
    if "health" in categories:
        return (
            "Health-tech stories should be read with extra care: useful data can help readers ask better questions, "
            "but it should not be treated as diagnosis or treatment advice without professional medical context."
        )
    notes = []
    if "phones" in categories:
        notes.append("phone news can shape upgrade timing, buying choices, app support, and how long older devices stay useful")
    if "apple" in categories:
        notes.append("Apple ecosystem updates often affect iPhone, iPad, Mac, iOS, app developers, and accessory buyers at the same time")
    if "android" in categories:
        notes.append("Android updates matter because they ripple across phones, tablets, foldables, apps, and device makers")
    if "ai" in categories:
        notes.append("AI stories can quickly move from research demos into apps, phones, search, productivity tools, and policy debates")
    if "software" in categories:
        notes.append("software changes often decide which features, workflows, and devices feel useful day to day")
    if "security" in categories:
        notes.append("security stories usually deserve quick attention because small updates can become urgent maintenance work")
    if "gadgets" in categories:
        notes.append("gadget coverage can affect buying decisions, repair choices, and the useful life of devices people already own")
    if "science" in categories:
        notes.append("science updates often start as research signals before they turn into products, tools, or policy questions")
    if "tutorials" in categories or "hacks" in categories:
        notes.append("hands-on posts are useful when they point to experiments readers can safely try, adapt, or learn from")
    if "tech" in categories:
        notes.append("platform and software shifts can change what developers, creators, and everyday users are able to build")
    if not notes:
        notes.append("the common thread is worth tracking because it may turn into a practical change for readers")
    sentence = "; ".join(notes) + "."
    return sentence[:1].upper() + sentence[1:]


def category_reader_angle(category: str) -> str:
    angles = {
        "health": "health and medical news should be read with careful attention to source credibility, peer-reviewed evidence, and appropriate disclaimers; readers should consult healthcare professionals before making medical decisions based on news reports",
        "phones": "buyers should watch upgrade timing, carrier availability, battery claims, camera changes, software support, and whether the news affects current devices",
        "apple": "iPhone, iPad, Mac, and iOS users should watch compatibility, rollout timing, app support, and whether the change is limited to newer hardware",
        "android": "Android users should watch device support, manufacturer rollout schedules, app compatibility, privacy controls, and whether features arrive through system updates or apps",
        "gadgets": "gadget buyers should separate useful hardware changes from hype, especially around price, battery life, repairability, and long-term support",
        "ai": "AI updates should be judged by usefulness, accuracy, privacy impact, cost, and how tightly they are being built into everyday apps and devices",
        "software": "software stories matter most when they change workflows, security, app compatibility, or the way people create and share content",
        "science": "science stories are worth tracking when they point toward practical tools, policy changes, future products, or a better understanding of how the world works",
        "space": "space stories matter when they improve exploration, communications, Earth observation, scientific measurement, or the technologies that later reach everyday life",
        "security": "security stories need attention because a small warning can turn into an urgent update, password change, or device maintenance task",
        "tutorials": "tutorials are useful when they give readers a practical thing to test, build, fix, or understand more clearly",
        "hacks": "hacks are strongest when they teach a reusable technique rather than a one-off trick",
        "tech": "platform stories matter when they shift what developers, creators, businesses, or ordinary users can do next",
    }
    return angles.get(category, "readers should watch what changes in real products, real tools, and real daily use")


def story_categories(cluster: list[Item], topic: str, keywords: list[str]) -> list[str]:
    text = " ".join([topic, *keywords, *(item.title for item in cluster), *(item.summary for item in cluster)]).lower()
    inferred: list[str] = []

    def matches_needle(haystack: str, needle: str) -> bool:
        clean = needle.strip()
        if not clean:
            return False
        if " " in clean:
            return clean in haystack
        if len(clean) <= 4:
            return re.search(rf"\b{re.escape(clean)}\b", haystack) is not None
        return clean in haystack

    checks = [
        ("health", ("health", "medical", "medicine", "doctor", "hospital", "patient", "treatment", "disease", "virus", "vaccine", "clinical", "drug", "pharmaceutical", "nutrition", "fitness", "mental health", "wellness", "cancer", "diabetes", "heart", "blood pressure", "cholesterol", "obesity", "exercise", "diet", "supplement", "therapy", "symptom", "diagnosis", "cdc", "who", "nih", "fda", "harvard health", "mayo clinic", "webmd", "healthline")),
        ("ai", ("chatgpt", "openai", "artificial intelligence", "ai", "gemini", "ai model", "llm", "assistant", "chatbot")),
        ("apple", ("iphone", "ios", "airpods", "apple", "ipad", "mac")),
        ("android", ("android", "pixel", "samsung", "googlebook")),
        ("phones", ("phone", "phones", "smartphone", "mobile", "foldable")),
        ("space", ("nasa", "mars", "moon", "galaxies", "seyfert", "exoplanet", "telescope", "astronomy", "astronomer", "astronomers", "spacecraft", "space station", "spacex", "rocket", "satellite")),
        ("science", ("study", "research", "scientists", "science", "researchers")),
        ("software", ("app", "apps", "software", "update", "developer")),
        ("security", ("security", "hack", "breach", "malware", "password", "vulnerability")),
        ("gadgets", ("gadget", "device", "smartwatch", "wearable", "earbuds", "laptop", "glasses", "robotaxi", "robotaxis")),
    ]
    padded = f" {text} "
    for category, needles in checks:
        if any(matches_needle(padded, needle) for needle in needles):
            inferred.append(category)
    if inferred:
        if inferred == ["ai"]:
            inferred.append("software")
        if inferred == ["health"]:
            inferred.append("science")
        return inferred[:3]
    for item in cluster:
        if item.source_category not in inferred:
            inferred.append(item.source_category)
    return inferred[:3] or ["tech"]


def meta_image_from_page(url: str) -> str | None:
    if not url.startswith(("http://", "https://")):
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=env_int("REQUEST_TIMEOUT_SECONDS", 25)) as response:
            raw = response.read(1_500_000).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError, TimeoutError):
        return None
    patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return canonical_url(html.unescape(match.group(1)))
    return None


def source_image_candidates(cluster: list[Item]) -> list[str]:
    candidates: list[str] = []
    for item in cluster:
        if item.image_url and item.image_url not in candidates:
            candidates.append(item.image_url)
    if len(candidates) >= 2:
        return candidates
    for item in cluster[:3]:
        discovered = meta_image_from_page(item.link)
        if discovered and discovered not in candidates:
            candidates.append(discovered)
    return candidates


def category_for_item(item: Item) -> str:
    return story_categories([item], item.title, list(tokens_for(item))[:6])[0]


def source_analysis_paragraphs(cluster: list[Item]) -> str:
    paragraphs = []
    for index, item in enumerate(cluster):
        title = html.escape(item.title)
        source = html.escape(item.source_name)
        item_category = category_for_item(item)
        category = html.escape(item_category)
        angle = html.escape(category_reader_angle(item_category))
        summary = clean_text(item.summary, max_len=420)
        summary_sentence = "The feed does not provide much extra detail, so the headline itself is being treated as the main signal."
        if summary and summary.lower() != item.title.lower():
            summary_sentence = f"The feed summary adds useful context: {html.escape(summary)}"
        if index == 0:
            report_intro = f"According to <strong>{source}</strong>, the story centers on <strong>{title}</strong>."
        else:
            report_intro = f"<strong>{source}</strong> adds another piece of the picture with <strong>{title}</strong>."
        paragraphs.append(
            f"<p>{report_intro} "
            f"{summary_sentence} This puts the story in the <strong>{category}</strong> lane, where {angle}. "
            "That matters because one isolated report is easy to miss, but repeated coverage across sources can show that the topic has real momentum.</p>"
        )
    return "\n".join(paragraphs)


def legacy_full_article_sections(cluster: list[Item], topic: str, categories: list[str], source_count: int) -> str:
    category_text = ", ".join(categories)
    primary_angle = category_reader_angle(categories[0] if categories else "tech")
    takeaway = category_takeaway(set(categories))
    source_paragraphs = source_analysis_paragraphs(cluster)
    practical_focus = {
        "phones": "If you are thinking about a new phone, watch whether this news affects battery life, cameras, storage, repairability, trade-in value, or how many years of updates the device is likely to receive.",
        "apple": "For Apple users, the key is whether the change reaches older iPhones and iPads or stays locked to newer devices. That detail often matters more than the headline itself.",
        "android": "For Android users, the rollout path matters. A feature announced for Android does not always arrive at the same time on Samsung, Pixel, OnePlus, Xiaomi, or budget devices.",
        "ai": "For AI stories, the practical test is simple: does it save time, improve accuracy, protect privacy, or make an existing app easier to use?",
        "gadgets": "For gadget news, the real question is whether the product solves a daily problem or just adds another spec to a box.",
        "science": "For science and space stories, the value is often in the direction of travel: what this discovery, mission, or experiment could make possible next.",
        "software": "For software stories, watch whether the change is optional, forced, free, subscription-based, or tied to a specific device or operating system.",
    }
    practical = practical_focus.get(categories[0] if categories else "tech", "The practical move is to watch what changes for real users, real devices, and real workflows.")
    watch_items = [
        "whether official documentation, changelogs, launch notes, or product pages confirm the details",
        "how quickly the update reaches regular users rather than only early testers or limited regions",
        "whether the change affects price, compatibility, battery life, privacy, repairability, or long-term support",
        "which companies, developers, or device makers respond next",
    ]
    watch_html = "\n".join(f"<li>{html.escape(item)}</li>" for item in watch_items)
    return f"""
<h2>What happened</h2>
<p>The latest cluster of reports is centered on <strong>{html.escape(topic)}</strong>. The common thread is not just that another tech story appeared online; it is that multiple reliable feeds are pointing toward a theme that could matter to people who follow {html.escape(category_text)} news.</p>
{source_paragraphs}
<h2>The bigger picture</h2>
<p>This kind of story is worth reading as part of a wider trend. Tech, phone, AI, and science news often starts as scattered signals: a product detail here, a software change there, a research update somewhere else. When those signals line up, they can show where the industry is moving before the change becomes obvious to everyone.</p>
<p>For readers, the useful question is not only â€œwhat happened?â€ It is also â€œwhat changes because of it?â€ In this case, the important angle is that {html.escape(primary_angle)}. That is the difference between a quick headline and something worth saving, comparing, or acting on later.</p>
<h2>Why readers should care</h2>
<p>If this story develops further, it could affect upgrade choices, app behavior, buying decisions, developer priorities, or the way people use devices day to day. Even when a report is early, it can still help readers notice which features, companies, or platforms are becoming more important.</p>
<p>The smart approach is to avoid treating any single report as the final word. A stronger picture comes from checking whether the same facts keep showing up elsewhere and watching for official confirmation as the story develops.</p>
<h2>Practical takeaway</h2>
<p>{html.escape(practical)}</p>
<p>Readers should also pay attention to what is missing. If reporting does not yet mention pricing, region availability, device support, privacy details, or release timing, those gaps are not footnotes; they are often the facts that decide whether a story becomes useful in everyday life or stays as background noise.</p>
<h2>What to watch next</h2>
<ul>
{watch_html}
</ul>
<h2>Bottom line</h2>
<p>This is a developing tech signal, not a final verdict. The story is strong enough to watch because it connects {html.escape(category_text)} coverage across {source_count} independent sources. If more reporting confirms the same direction, this could become more than a quick news item and turn into something that affects real devices, apps, services, or user choices.</p>
""".strip()


def inline_source_phrase(cluster: list[Item]) -> str:
    seen: set[str] = set()
    links: list[str] = []
    for item in cluster:
        if item.source_name in seen:
            continue
        seen.add(item.source_name)
        links.append(f'<a href="{html.escape(item.link)}">{html.escape(item.source_name)}</a>')
    if not links:
        return "industry reports"
    if len(links) == 1:
        return links[0]
    if len(links) == 2:
        return f"{links[0]} and {links[1]}"
    return f"{', '.join(links[:-1])}, and {links[-1]}"


def source_report_paragraphs(cluster: list[Item]) -> str:
    paragraphs: list[str] = []
    categories = cluster_categories(cluster)
    text = story_text(cluster)
    consequence = source_consequence_sentence(categories, text)
    for index, item in enumerate(cluster[:4], start=1):
        title = clean_text(item.title, max_len=170)
        summary = clean_text(item.summary, max_len=360)
        source = html.escape(item.source_name)
        link = html.escape(item.link)
        title_html = html.escape(title)
        if summary and summary.lower() != title.lower():
            paragraphs.append(
                f'<p><a href="{link}">{source}</a> reports that <strong>{title_html}</strong>. '
                f'{html.escape(summary)} {html.escape(consequence)}</p>'
            )
        else:
            paragraphs.append(
                f'<p><a href="{link}">{source}</a> reports <strong>{title_html}</strong>. '
                "The feed gives limited detail beyond the headline, so the safest reading is to treat the report as an early signal and separate confirmed facts from likely implications.</p>"
            )
    return "\n".join(paragraphs)


def source_consequence_sentence(categories: list[str], text: str) -> str:
    kind = story_kind(categories, text)
    if kind == "health":
        return "The key issue is evidence: what the device measures, how reliable the measurement is, who can safely use it, and where medical guidance is still needed."
    if kind == "ai":
        return "The key issue is whether the feature improves real work without creating new problems around accuracy, privacy, cost, or user control."
    if kind == "phones":
        return "The key issue is whether the detail changes buying decisions, update support, battery life, camera value, pricing, or everyday use."
    if kind == "science":
        return "The key issue is whether the finding is strong enough to guide follow-up research, better tools, safer systems, or real-world applications."
    if kind == "space":
        return "The key issue is what the mission or observation makes possible next: better data, stronger hardware, new experiments, or clearer science."
    if kind == "security":
        return "The key issue is what readers, companies, or platform owners should do before a technical warning becomes a personal or business problem."
    return "The key issue is what changes after the announcement: price, access, timing, compatibility, reliability, or reader impact."


def known_details(cluster: list[Item]) -> list[str]:
    details: list[str] = []
    for item in cluster[:4]:
        title = clean_text(item.title, max_len=150)
        summary = clean_text(item.summary, max_len=190)
        if title:
            details.append(f"{item.source_name}: {title}")
        if summary and summary.lower() != title.lower():
            details.append(summary)
    details.extend(extracted_details(cluster))

    cleaned: list[str] = []
    seen: set[str] = set()
    for detail in details:
        detail = clean_text(detail, max_len=210).strip(" .")
        key = re.sub(r"[^a-z0-9]+", " ", detail.lower()).strip()
        if len(detail) < 8 or key in seen:
            continue
        seen.add(key)
        cleaned.append(detail)
    return cleaned[:7]


def known_details_html(cluster: list[Item]) -> str:
    details = known_details(cluster)
    if not details:
        return "<p>The available source briefs are thin, so the article treats this as an early report rather than a settled conclusion.</p>"
    return "<ul>\n" + "\n".join(f"<li>{html.escape(detail)}</li>" for detail in details) + "\n</ul>"


def reader_impact_paragraph(categories: list[str], text: str) -> str:
    kind = story_kind(categories, text)
    if kind == "health":
        return (
            "<p>For readers, the practical question is whether the product or research helps people understand their health more clearly without encouraging self-diagnosis. Measurement, accuracy, access, price, privacy, and medical context matter more than the novelty of another wearable sensor.</p>"
        )
    if kind == "ai":
        return (
            "<p>For readers, the practical question is whether the feature or research changes the tools they already use: search, video, writing, coding, customer support, image creation, privacy controls, or workplace software. AI stories deserve attention when they alter reliability, cost, access, or trust, not merely when they add another demo.</p>"
        )
    if kind == "phones":
        return (
            "<p>For phone buyers, the impact is usually concrete: upgrade timing, battery life, camera value, resale prices, repair options, software support, or whether older devices are left behind. A good phone story should help readers decide whether to wait, upgrade, ignore the noise, or watch for a better deal.</p>"
        )
    if kind == "science":
        return (
            "<p>For readers, the value is in knowing what the finding can and cannot prove. Strong science coverage should explain the evidence, the limit of the claim, and whether the work is likely to influence tools, medicine, energy, materials, computing, climate work, or future research.</p>"
        )
    if kind == "space":
        return (
            "<p>For readers, the payoff is usually downstream: better instruments, cleaner data, more durable spacecraft, new experiments, and mission lessons that make the next attempt less uncertain. The visible moment matters, but the useful story is what engineers and scientists can do with it afterward.</p>"
        )
    if kind == "security":
        return (
            "<p>For readers, security news matters when it changes behavior: update now, change a password, avoid a scam, check a device, or understand why a company or platform has become risky. The best security writing turns technical danger into plain decisions.</p>"
        )
    return (
        "<p>For readers, the question is practical: does this change price, access, safety, privacy, convenience, reliability, compatibility, or the way a product fits into daily life? If it does not, the story is probably less urgent than the headline suggests.</p>"
    )


def story_text(cluster: list[Item]) -> str:
    return " ".join(f"{item.title} {item.summary}" for item in cluster).lower()


def has_term(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        clean = term.strip().lower()
        if not clean:
            continue
        if " " in clean or len(clean) <= 4:
            if re.search(rf"\b{re.escape(clean)}\b", text):
                return True
        elif clean in text:
            return True
    return False


def professional_angle(topic: str, categories: list[str], text: str) -> str:
    kind = story_kind(categories, text)
    if "health" in categories or has_term(text, ("glucose", "biosensor", "metabolic", "medical", "health", "clinical", "patient", "treatment")):
        return (
            "The important question is whether the health claim is supported by reliable measurement and sensible guidance. "
            "Consumer health technology can be useful, but it becomes risky when numbers are treated like medical advice without context."
        )
    if kind == "health" or "health" in categories:
        watch_items = [
            "independent accuracy or validation data for the sensor",
            "privacy terms covering health and biometric data",
            "subscription pricing, device compatibility, and regional availability",
            "clear guidance about when users should consult a healthcare professional",
        ]
    elif has_term(text, ("robotaxi", "robotaxis", "self-driving", "autonomous", "driverless", "tesla")):
        return (
            "Crash data matters because autonomous driving is judged on public roads, not on launch-stage promises. "
            "Every incident report, safety-driver detail, and slow rollout makes it clearer how much work remains before robotaxis feel normal instead of experimental."
        )
    if "iphone" in text and any(word in text for word in ("price", "discount", "slash", "deal", "trade-in", "china")):
        return (
            "The move suggests a more aggressive retail strategy around the iPhone, especially in markets where "
            "premium phones have to fight harder for attention, upgrade cycles are stretching, and buyers are more sensitive to price."
        )
    if has_term(text, ("spacex", "dragon", "space station", "resupply", "station", "nasa")):
        return (
            "The wider importance is in the science payload, not just the docking itself. Every resupply mission can turn the space station "
            "into a temporary laboratory for biology, materials research, physics, medicine, and technologies that are difficult to test on Earth."
        )
    if has_term(text, ("residual stress", "aircraft", "engine blades", "materials", "reliability", "manufacturing")):
        return (
            "The bigger point is reliability. Research like this can sound niche, but better ways to measure stress inside critical parts "
            "can lead to safer aircraft, longer-lasting components, fewer unexpected failures, and smarter manufacturing decisions."
        )
    if "science" in categories or has_term(text, ("research", "study", "scientists", "experiment", "breakthrough", "discovery")):
        return (
            "The value of this kind of science story is not always immediate. Its importance comes from the way a finding can improve tools, "
            "change engineering decisions, guide future research, or eventually become part of real products and systems."
        )
    if has_term(text, ("chatgpt", "openai", "ai", "artificial intelligence", "gemini")):
        return (
            "The bigger shift is that AI is moving deeper into everyday software instead of staying separate as a chatbot window. "
            "That makes usefulness, accuracy, privacy, and user trust just as important as the headline feature itself."
        )
    if any(word in text for word in ("android", "samsung", "pixel", "galaxy")):
        return (
            "For Android users, the key issue is rollout. A feature can be announced broadly and still arrive differently across Pixel, "
            "Samsung, foldables, budget phones, and carrier-locked devices."
        )
    if has_term(text, ("space", "nasa", "mars", "moon", "telescope", "astronomy")):
        return (
            "The wider importance is in what the work can unlock next: better measurement, stronger missions, new research tools, "
            "or a clearer view of systems that are difficult to study from Earth."
        )
    if any(word in text for word in ("security", "breach", "malware", "password", "vulnerability", "hack")):
        return (
            "The practical importance is security hygiene. The details may sound technical, but the result can become a real-world "
            "update, password change, device check, or business risk."
        )
    if "apple" in categories:
        return (
            "For Apple users, the real question is whether this becomes a broad ecosystem change or a narrower update tied to specific "
            "devices, markets, services, or release timing."
        )
    if "phones" in categories:
        return (
            "For phone buyers, the useful question is whether the news changes upgrade timing, pricing, battery expectations, camera value, "
            "repairability, or long-term software support."
        )
    return (
        "The larger point is that tech shifts rarely matter because of one announcement alone. They matter when they change what people can buy, "
        "what developers build, or how existing devices and apps feel in daily use."
    )


def professional_lead(topic: str, categories: list[str], text: str) -> str:
    return f"<strong>{html.escape(topic)}</strong>."


def legacy_detail_paragraph(topic: str, cluster: list[Item]) -> str:
    text = story_text(cluster)
    details: list[str] = []
    if "china" in text:
        details.append("China")
    if "618" in text:
        details.append("the 618 shopping festival")
    if "jd.com" in text:
        details.append("JD.com")
    if "tmall" in text:
        details.append("Tmall")
    if "trade-in" in text or "trade in" in text:
        details.append("trade-in offers")
    amounts = re.findall(r"(?:\$|Â£|â‚¬)?\d[\d,]*(?:\.\d+)?\s?(?:yuan|%|percent|gb|tb|mp|mah|hours|days|weeks|months|years)?", text, flags=re.IGNORECASE)
    for amount in amounts[:3]:
        clean_amount = amount.strip()
        if clean_amount and clean_amount.lower() not in {value.lower() for value in details}:
            details.append(clean_amount)
    if details:
        detail_text = ", ".join(details[:6])
        return (
            f"<p>The detail that matters is the shape of the move: <strong>{html.escape(detail_text)}</strong>. "
            "Those pieces give the story more weight than a normal product rumor or routine update because they point to timing, market pressure, and user impact.</p>"
        )
    return (
        "<p>The detail that matters is how the development connects product decisions, user expectations, and what could change once the news reaches ordinary users.</p>"
    )


def human_join(values: list[str]) -> str:
    values = [value for value in values if value]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def extracted_details(cluster: list[Item]) -> list[str]:
    text = story_text(cluster)
    details: list[str] = []
    checks = [
        ("chatgpt plus", "ChatGPT Plus access"),
        ("all citizens", "nationwide citizen access"),
        ("citizens", "citizen access"),
        ("residents", "resident access"),
        ("course", "a training requirement"),
        ("training", "AI training"),
        ("responsibly", "responsible AI use"),
        ("practical ai skills", "practical AI skills"),
        ("spacex", "SpaceX Dragon"),
        ("dragon", "Dragon spacecraft"),
        ("space station", "International Space Station"),
        ("station", "space station research"),
        ("science experiments", "new science experiments"),
        ("experiments", "new experiments"),
        ("cargo", "research cargo"),
        ("resupply", "resupply mission"),
        ("residual stress", "residual stress measurement"),
        ("aircraft", "aircraft components"),
        ("engine blades", "engine blade reliability"),
        ("multiscale", "multiscale evaluation"),
        ("reliability", "reliability testing"),
        ("china", "China"),
        ("618", "the 618 shopping festival"),
        ("jd.com", "JD.com"),
        ("tmall", "Tmall"),
        ("trade-in", "trade-in offers"),
        ("trade in", "trade-in offers"),
        ("discount", "discounting"),
        ("price", "pricing pressure"),
        ("subscription", "subscription access"),
        ("robotaxi", "robotaxi testing"),
        ("robotaxis", "robotaxi testing"),
        ("crash", "crash data"),
        ("autonomous", "autonomous driving"),
        ("self-driving", "self-driving software"),
        ("tesla", "Tesla's rollout"),
    ]
    for needle, label in checks:
        if label in {"citizen access", "resident access"} and "nationwide citizen access" in details:
            continue
        if needle in text and label not in details:
            details.append(label)
    amounts = re.findall(
        r"(?:\$\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:yuan|%|percent|gb|tb|mp|mah|hours|days|weeks|months|years))",
        text,
        flags=re.IGNORECASE,
    )
    for amount in amounts[:4]:
        clean_amount = amount.strip()
        if clean_amount and clean_amount.lower() not in {value.lower() for value in details}:
            details.append(clean_amount)
    return details[:8]


def detail_paragraph(topic: str, cluster: list[Item]) -> str:
    return ""


def direction_paragraph(categories: list[str], text: str) -> str:
    return ""


def bigger_picture_paragraphs(categories: list[str], text: str) -> str:
    return ""


def why_extra_paragraph(categories: list[str], text: str) -> str:
    return ""


def practical_question_paragraph(categories: list[str], text: str) -> str:
    return ""


def missing_details_paragraph(categories: list[str], text: str) -> str:
    return ""


def bottom_line_paragraph(topic: str, categories: list[str], text: str) -> str:
    return ""


def real_world_effect_paragraph(categories: list[str], text: str) -> str:
    return ""


def story_kind(categories: list[str], text: str) -> str:
    if "health" in categories or has_term(text, ("glucose", "biosensor", "metabolic", "medical", "medicine", "clinical", "patient", "treatment", "health platform", "blood pressure")):
        return "health"
    if has_term(text, ("robotaxi", "robotaxis", "self-driving", "autonomous", "driverless", "tesla")):
        return "autonomous"
    if "space" in categories or has_term(text, ("spacex", "dragon", "space station", "nasa", "resupply", "mars", "moon", "telescope", "astronomy")):
        return "space"
    if "science" in categories or has_term(text, ("research", "study", "scientists", "experiment", "breakthrough", "discovery", "residual stress")):
        return "science"
    if "ai" in categories or has_term(text, ("chatgpt", "openai", "artificial intelligence", "gemini", "llm")):
        return "ai"
    if "security" in categories:
        return "security"
    if "gadgets" in categories:
        return "gadgets"
    if "phones" in categories or "android" in categories or "apple" in categories:
        return "phones"
    if "tutorials" in categories or "hacks" in categories:
        return "tutorials"
    if "software" in categories:
        return "software"
    return "tech"


def section_titles(categories: list[str], text: str) -> dict[str, str]:
    kind = story_kind(categories, text)
    titles = {
        "health": {
            "what": "What Happened",
            "why": "Why It Matters",
            "picture": "The Health-Tech Context",
            "takeaway": "What Readers Should Know",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
        "space": {
            "what": "The Mission Update",
            "why": "The Mission Context",
            "picture": "The Bigger Picture",
            "takeaway": "What To Take From It",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
        "science": {
            "what": "The Research",
            "why": "The Scientific Context",
            "picture": "The Bigger Picture",
            "takeaway": "What This Could Change",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
        "security": {
            "what": "The Warning",
            "why": "The Risk Context",
            "picture": "The Bigger Picture",
            "takeaway": "What Readers Should Do",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
        "gadgets": {
            "what": "The Story",
            "why": "The Product Context",
            "picture": "The Bigger Picture",
            "takeaway": "What Buyers Should Notice",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
        "autonomous": {
            "what": "The Road Test",
            "why": "The Safety Context",
            "picture": "The Bigger Picture",
            "takeaway": "What To Watch Closely",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
    }
    return titles.get(
        kind,
        {
            "what": "What Happened",
            "why": "The Context",
            "picture": "The Bigger Picture",
            "takeaway": "What Readers Should Take From It",
            "watch": "What To Watch Next",
            "bottom": "Bottom Line",
        },
    )


def human_story_intro(topic: str, categories: list[str], text: str, source_phrase: str, source_verb: str) -> str:
    kind = story_kind(categories, text)
    if kind == "space":
        return (
            f"<p>{source_phrase} {source_verb} a space story whose importance lies less in spectacle than in the patient engineering, measurement, and risk reduction that make space science useful.</p>"
        )
    if kind == "science":
        return (
            f"<p>{source_phrase} {source_verb} research whose value will depend on what it lets scientists measure, build, or prove next. That is often how important science begins: not with drama, but with a better tool for seeing the problem.</p>"
        )
    if kind == "security":
        return (
            f"<p>{source_phrase} {source_verb} a practical security question: who is exposed, what can be done now, and how expensive delay could become.</p>"
        )
    if kind == "gadgets":
        return (
            f"<p>{source_phrase} {source_verb} a product story that should be judged by usefulness, not novelty. The test is whether it removes friction from daily life or merely adds another specification to admire.</p>"
        )
    if kind == "autonomous":
        return (
            f"<p>{source_phrase} {source_verb} the awkward stage of autonomous driving: impressive enough to expand, still fragile enough to demand evidence. The data matters more than another polished demo.</p>"
        )
    if kind == "phones":
        return (
            f"<p>{source_phrase} {source_verb} the sort of phone-industry detail that can alter upgrade timing, platform loyalty, and the everyday feel of a device.</p>"
        )
    if kind == "ai":
        return (
            f"<p>{source_phrase} {source_verb} the plain question now facing AI: does the technology make software better, or merely more decorated?</p>"
        )
    return (
        f"<p>{source_phrase} {source_verb} a development whose importance depends on what changes after the announcement passes: costs, habits, trust, support, or the way people use the technology.</p>"
    )


def human_aside_paragraph(categories: list[str], text: str) -> str:
    kind = story_kind(categories, text)
    if kind == "health":
        return "<p>The best health-tech products are careful with their claims: useful enough to inform people, modest enough not to pretend that a sensor can replace a clinician.</p>"
    if kind == "space":
        return "<p>The theatre of space is useful, but the ledger matters more: what survived, what was measured, what failed, and what can now be tried again with better odds.</p>"
    if kind == "science":
        return "<p>This is how much of science actually moves: not in thunderclaps, but in careful improvements that make the next experiment less blind than the last.</p>"
    if kind == "security":
        return "<p>The dull advice is still the best advice: patch early, distrust urgency, and assume that convenience is often where risk hides.</p>"
    if kind == "gadgets":
        return "<p>Clever hardware often fails on boring details: price, batteries, reliability, repairs, software support and whether anyone wants to use it twice.</p>"
    if kind == "autonomous":
        return "<p>For robotaxis, the most convincing progress will look almost dull: fewer strange decisions, fewer interventions, fewer crashes, and more miles where nothing dramatic happens.</p>"
    if kind == "phones":
        return "<p>Manufacturers are skilled at turning modest changes into urgent-sounding reasons to upgrade. The better test is whether the change improves life after six months, not after six minutes.</p>"
    if kind == "ai":
        return "<p>A little skepticism is not cynicism here; it is basic hygiene. AI headlines often inflate the demo and shrink the caveats.</p>"
    return "<p>Novelty is cheap in technology. Consequence is rarer, and that is what separates a useful story from a shiny distraction.</p>"


def editorial_nut_graph(categories: list[str], text: str) -> str:
    kind = story_kind(categories, text)
    if kind == "health":
        return "Health technology is useful when it makes signals easier to understand without turning uncertain data into false certainty. Accuracy, privacy, context, and medical caution matter as much as the hardware."
    if kind == "science":
        return "The test is not whether the discovery sounds impressive on first reading. It is whether the evidence is strong, the limits are clear, and the work gives other researchers a firmer platform for the next step."
    if kind == "space":
        return "The public sees the launch, the docking, or the image. The deeper story is usually slower: instruments gathering cleaner data, hardware surviving hostile conditions, and teams learning which assumptions were right."
    if kind == "ai":
        return "AI is now past the stage where novelty alone is enough. The useful tools will be reliable, legible, private enough for ordinary use, and valuable after the first burst of curiosity fades."
    if kind == "phones":
        return "Modern phones are mature products, which makes small changes more important rather than less. A better sensor, longer support window, improved repair path, or smarter software choice can shift real buying decisions."
    if kind == "security":
        return "Security stories are easy to ignore until they become personal. The better habit is to treat them as early warnings about incentives, weak defaults, and systems that need maintenance."
    if kind == "gadgets":
        return "A good gadget story is not about whether a product exists. It is about whether it solves a real irritation elegantly enough to become part of daily life."
    return "The real question is not whether the news is interesting for a day. It is whether it changes incentives, habits, products, or expectations in a way that lasts."


def collect_source_sentences(cluster: list[Item]) -> list[tuple[str, list[str]]]:
    """Split each item's summary into clean sentences, grouped by source.

    Uses both item.title and item.summary to maximize content when summaries are short.
    """
    grouped: dict[str, list[str]] = {}
    # Sentence splitter: split after . ! ? that are followed by whitespace+uppercase,
    # but NOT after decimal numbers like 7800.5 or abbreviations followed by lowercase.
    _sent_re = re.compile(r'(?<=[.!?])(?=\s+[A-Z])')
    # RSS branding patterns to strip
    _branding_re = re.compile(
        r'(?:The post\s+.+?\s+appeared first on\s+.+?\.?)'
        r'|(?:\bRead more\b.*$)'
        r'|(?:\bRead the full article\b.*$)',
        re.IGNORECASE | re.DOTALL,
    )
    for item in cluster:
        # Use both title and summary to get more content
        raw = f"{item.title or ''} {item.summary or ''}"
        raw = _branding_re.sub("", raw).strip()
        raw = fix_mojibake(strip_html(raw))
        raw = re.sub(r"\s+", " ", raw).strip()
        sentences = [s.strip() for s in _sent_re.split(raw) if len(s.strip()) >= 8]
        if item.source_name not in grouped:
            grouped[item.source_name] = []
        grouped[item.source_name].extend(sentences)
    return list(grouped.items())


def paragraphize_sentences(sentences: list[str], size: int = 3, max_paragraphs: int = 40) -> list[str]:
    paragraphs = []
    for i in range(0, len(sentences), size):
        if len(paragraphs) >= max_paragraphs:
            break
        chunk = sentences[i:i+size]
        if chunk:
            paragraphs.append(" ".join(chunk))
    return paragraphs


def extract_numeric_facts(text: str) -> str:
    facts = re.findall(r'\$[\d,]+(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s*(?:percent|gb|tb|mp|mah|hours|days|weeks|months|years|yuan)', text, flags=re.IGNORECASE)
    if facts:
        return " ".join(facts[:5])
    return ""


def full_article_sections(cluster: list[Item], topic: str, categories: list[str], source_count: int) -> str:
    """Build the main article body from the cluster's source summaries.

    Produces clean, professional paragraphs extracted from the RSS summaries
    without any formulaic section headers, analytical filler, or repeated
    injections of the article title.
    """
    full_text = " ".join(f"{item.title} {item.summary}" for item in cluster)
    grouped = collect_source_sentences(cluster)
    if not grouped:
        return f'<p>{html.escape(clean_text(topic, max_len=5000))}.</p>'

    # For single-source posts, use simpler approach with less filtering
    if source_count == 1:
        all_sentences = []
        for _source_name, sentences in grouped:
            for s in sentences:
                s = s.strip()
                if s and len(s) >= 8:
                    # Basic cleanup
                    s = re.sub(r'[,\s.]+$', '', s).strip()
                    if s:
                        all_sentences.append(s + ".")
        
        if not all_sentences:
            # Ultimate fallback
            fallback_sentences = re.split(r'(?<=[.!?])\s+', full_text)
            for sent in fallback_sentences:
                sent = sent.strip()
                if sent and len(sent) >= 8:
                    all_sentences.append(sent + ".")
        
        if all_sentences:
            # Group into paragraphs of 2-3 sentences
            paragraphs = []
            for i in range(0, len(all_sentences), 2):
                chunk = all_sentences[i:i+2]
                paragraphs.append(" ".join(chunk))
            
            # Add numeric facts if available
            numeric_facts = extract_numeric_facts(full_text)
            if numeric_facts:
                paragraphs.append(f"{numeric_facts}.")
            
            return "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip())
        
        return f'<p>{html.escape(clean_text(topic, max_len=5000))}.</p>'

    # Multi-source posts: use filtering logic
    all_sentences: list[str] = []
    seen_keys: set[str] = set()

    # Normalised topic for near-duplicate filtering
    _topic_key = re.sub(r'[^a-z0-9]', '', topic.lower())[:70]

    def _add(sent: str) -> None:
        sent = sent.strip()
        if not sent or len(sent) < 8:
            return
        # Strip trailing punctuation/ellipsis artifacts (incl. comma-period combos)
        sent = re.sub(r'[,\s.]+$', '', sent).strip()
        if not sent or len(sent) < 8:
            return
        # Capitalise first letter if needed
        if not sent[0].isupper():
            sent = sent[0].upper() + sent[1:]
        # Reject sentences that are essentially a restatement of the title
        sent_key = re.sub(r'[^a-z0-9]', '', sent.lower())[:70]
        if _topic_key and len(_topic_key) > 20 and sent_key.startswith(_topic_key[:50]):
            return
        key = re.sub(r'[^a-z0-9]', '', sent.lower())[:90]
        if key in seen_keys:
            return
        seen_keys.add(key)
        all_sentences.append(sent + ".")

    for _source_name, sentences in grouped:
        for s in sentences:
            _add(s)

    if not all_sentences:
        # Fallback: use the full summary text split into sentences
        fallback_sentences = re.split(r'(?<=[.!?])\s+', full_text)
        for sent in fallback_sentences:
            sent = sent.strip()
            if sent and len(sent) >= 8:
                all_sentences.append(sent + ".")
        if not all_sentences:
            return f'<p>{html.escape(clean_text(topic, max_len=5000))}.</p>'

    # Build HTML paragraphs: 2-3 sentences for the opener, then 3-4 each for longer articles
    paragraphs: list[str] = []
    remaining = list(all_sentences)

    first_chunk = remaining[:2]
    remaining = remaining[2:]
    paragraphs.append(" ".join(first_chunk))

    while remaining:
        size = min(4, len(remaining))
        paragraphs.append(" ".join(remaining[:size]))
        remaining = remaining[size:]

    # Numeric facts as a closing factual note
    numeric_facts = extract_numeric_facts(full_text)
    if numeric_facts:
        paragraphs.append(f"{numeric_facts}.")

    return "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip())


def free_article(cluster: list[Item]) -> dict[str, Any]:
    lead = cluster[0]
    keywords = top_keywords(cluster, 8)
    topic = topic_from_cluster(cluster)
    categories = story_categories(cluster, topic, keywords)
    source_count = len({item.source_name for item in cluster})
    title = topic
    source_image_urls = source_image_candidates(cluster)
    hero_path = create_hero_image(title, keywords, categories, source_image_urls)
    text = story_text(cluster)
    kind = story_kind(categories, text)

    image_block = ""
    if hero_path:
        image_block = f"""
<figure class="wp-block-image size-large">
<img src="{HERO_IMAGE_PLACEHOLDER}" alt="{html.escape(title)} illustration">
</figure>
""".strip()

    # Medical disclaimer for health content
    medical_disclaimer = ""
    if "health" in categories or kind == "health":
        medical_disclaimer = """
<blockquote><p><strong>Medical Disclaimer:</strong> This article is for informational purposes only and does not constitute medical advice. Always consult with qualified healthcare professionals for medical decisions and treatment options.</p></blockquote>
""".strip()

    # Generate meta description and focus keyword
    focus_keyword = keywords[0] if keywords else "technology"
    meta_description = clean_text(topic, max_len=160)
    excerpt = ""

    # Build professional straight article layout
    body = f"""
{image_block}
<p>[more]</p>
{full_article_sections(cluster, topic, categories, source_count)}
{medical_disclaimer}
""".strip()

    return {
        "title": title,
        "slug": slugify(topic),
        "excerpt": "",
        "categories": categories[:3],
        "tags": sorted(set(categories + keywords))[:12],
        "html": body,
        "hero_image_path": str(hero_path) if hero_path else "",
        "hero_image_alt": f"{title} illustration",
        "meta_description": meta_description[:160],
        "focus_keyword": focus_keyword,
    }


def generate_article(cluster: list[Item]) -> dict[str, Any]:
    generator = os.getenv("ARTICLE_GENERATOR", GENERATOR_FREE).strip().lower() or GENERATOR_FREE
    if generator == GENERATOR_OPENAI:
        return openai_generate_article(cluster)
    if generator == "auto" and os.getenv("OPENAI_API_KEY", "").strip():
        return openai_generate_article(cluster)
    if generator in {GENERATOR_FREE, "auto"}:
        return free_article(cluster)
    raise RuntimeError(f"Unsupported ARTICLE_GENERATOR: {generator}")


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "generated-post"


def wp_request(path: str, payload: dict[str, Any] | None = None, method: str = "GET") -> dict[str, Any] | list[Any]:
    base_url = os.getenv("WP_BASE_URL", "").rstrip("/")
    username = os.getenv("WP_USERNAME", "")
    app_password = os.getenv("WP_APPLICATION_PASSWORD", "")
    if not base_url or not username or not app_password:
        raise RuntimeError("WP_BASE_URL, WP_USERNAME, and WP_APPLICATION_PASSWORD are required.")

    url = f"{base_url}/wp-json/wp/v2/{path.lstrip('/')}"
    token = base64.b64encode(f"{username}:{app_password}".encode("utf-8")).decode("ascii")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method=method,
    )
    timeout = env_int("REQUEST_TIMEOUT_SECONDS", 25)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WordPress request failed: HTTP {exc.code}: {body}") from exc


def wp_term_ids(kind: str, names: list[str]) -> list[int]:
    if not names:
        return []
    endpoint = "categories" if kind == "category" else "tags"
    ids: list[int] = []
    create_terms = env_bool("WP_CREATE_TERMS", False)
    for name in names:
        name = str(name).strip()
        if not name:
            continue
        search = urllib.parse.urlencode({"search": name, "per_page": 20})
        matches = wp_request(f"{endpoint}?{search}")
        if isinstance(matches, list):
            exact = next((item for item in matches if item.get("name", "").lower() == name.lower()), None)
            if exact:
                ids.append(int(exact["id"]))
                continue
        if create_terms:
            created = wp_request(endpoint, {"name": name}, method="POST")
            if isinstance(created, dict) and created.get("id"):
                ids.append(int(created["id"]))
    return ids


def publish_to_wordpress(article: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": article["title"],
        "slug": article.get("slug") or slugify(article["title"]),
        "excerpt": article.get("excerpt", ""),
        "content": article["html"],
        "status": post_status(),
    }
    category_ids = wp_term_ids("category", [str(v) for v in article.get("categories", [])])
    tag_ids = wp_term_ids("tag", [str(v) for v in article.get("tags", [])])
    if category_ids:
        payload["categories"] = category_ids
    if tag_ids:
        payload["tags"] = tag_ids
    result = wp_request("posts", payload, method="POST")
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected WordPress response while creating post.")
    return result


def post_status() -> str:
    status = os.getenv("POST_STATUS", "draft").strip().lower() or "draft"
    if status == "publish" and os.getenv("AUTO_PUBLISH_CONFIRM") != "I_UNDERSTAND_POSTS_GO_LIVE":
        raise RuntimeError(
            "POST_STATUS=publish requires AUTO_PUBLISH_CONFIRM=I_UNDERSTAND_POSTS_GO_LIVE."
        )
    if status not in {"draft", "pending", "publish", "future", "private"}:
        raise RuntimeError(f"Unsupported POST_STATUS: {status}")
    return status


def article_text_fallback(article: dict[str, Any]) -> str:
    title = str(article.get("title", "Generated post"))
    excerpt = str(article.get("excerpt", ""))
    body = strip_html(str(article.get("html", "")))
    return "\n\n".join(part for part in [title, excerpt, body] if part)


def email_shortcodes(article: dict[str, Any]) -> list[str]:
    shortcodes = [
        f"[title {str(article.get('title', 'Generated post'))}]",
        f"[slug {str(article.get('slug') or slugify(str(article.get('title', 'Generated post'))))}]",
        f"[status {post_status()}]",
    ]
    # Skip excerpt entirely to prevent double title on social media
    categories = [str(value).strip() for value in article.get("categories", []) if str(value).strip()]
    tags = [str(value).strip() for value in article.get("tags", []) if str(value).strip()]
    if categories:
        shortcodes.append(f"[category {', '.join(categories)}]")
    if tags:
        shortcodes.append(f"[tags {', '.join(tags)}]")
    publicize = os.getenv("POST_BY_EMAIL_PUBLICIZE", "").strip().lower()
    if publicize == "off":
        # Explicit opt-out: disable all social sharing for this post
        shortcodes.append("[publicize off]")
    else:
        # Default: share with title-only message to ALL connected social platforms
        # (Bluesky, Mastodon, Facebook, Tumblr, etc.) via Jetpack Social / Publicize.
        # [publicize]...[/publicize] sets a custom message for every connected service.
        # Title-only keeps shares clean and uncluttered across all platforms.
        title = str(article.get("title", "")).strip()
        if title:
            shortcodes.append(f"[publicize]{title}[/publicize]")
    return shortcodes


def render_article_html(article: dict[str, Any], hero_src: str = "") -> str:
    body_html = str(article["html"])
    if HERO_IMAGE_PLACEHOLDER in body_html:
        body_html = body_html.replace(HERO_IMAGE_PLACEHOLDER, html.escape(hero_src, quote=True))
    return body_html


def article_hero_path(article: dict[str, Any]) -> Path | None:
    raw_path = str(article.get("hero_image_path", "")).strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    return path if path.exists() else None


def build_post_email(article: dict[str, Any]) -> EmailMessage:
    recipient = os.getenv("POST_BY_EMAIL_ADDRESS", "").strip()
    if not recipient:
        raise RuntimeError("POST_BY_EMAIL_ADDRESS is required when WP_POST_METHOD=email.")

    smtp_from = os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USERNAME", "").strip()
    if not smtp_from:
        raise RuntimeError("SMTP_FROM or SMTP_USERNAME is required when WP_POST_METHOD=email.")

    title = str(article["title"])
    shortcodes = email_shortcodes(article)
    shortcode_text = "\n".join(shortcodes)
    plain = f"{shortcode_text}\n\n{article_text_fallback(article)}\n\n[end]\n"
    shortcode_html = "<br>\n".join(html.escape(code) for code in shortcodes)
    hero_path = article_hero_path(article)
    hero_cid = make_msgid()[1:-1] if hero_path else ""
    body_html = render_article_html(article, f"cid:{hero_cid}" if hero_cid else "")
    html_body = f"""<!doctype html>
<html>
<body>
<p>{shortcode_html}</p>
{body_html}
<p>[end]</p>
</body>
</html>
"""

    message = EmailMessage()
    message["Subject"] = title
    message["From"] = smtp_from
    message["To"] = recipient
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=urllib.parse.urlsplit(os.getenv("WP_BASE_URL", "")).netloc or None)
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")
    if hero_path and hero_cid:
        html_part = message.get_payload()[-1]
        html_part.add_related(
            hero_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid=f"<{hero_cid}>",
            filename=hero_path.name,
        )
    return message


def send_article_by_email(article: dict[str, Any]) -> dict[str, Any]:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = env_int("SMTP_PORT", 587)
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    use_tls = env_bool("SMTP_USE_TLS", True)
    use_ssl = env_bool("SMTP_USE_SSL", False)
    timeout = env_int("REQUEST_TIMEOUT_SECONDS", 25)

    if not smtp_host:
        raise RuntimeError("SMTP_HOST is required when WP_POST_METHOD=email.")
    if not smtp_username or not smtp_password:
        raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD are required when WP_POST_METHOD=email.")

    message = build_post_email(article)
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(smtp_host, smtp_port, timeout=timeout) as server:
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        server.login(smtp_username, smtp_password)
        server.send_message(message)

    return {
        "id": None,
        "status": post_status(),
        "link": f"sent to {os.getenv('POST_BY_EMAIL_ADDRESS', '').strip()}",
    }


def deliver_article(article: dict[str, Any]) -> dict[str, Any]:
    method = os.getenv("WP_POST_METHOD", POST_METHOD_EMAIL).strip().lower() or POST_METHOD_EMAIL
    if method == POST_METHOD_EMAIL:
        return send_article_by_email(article)
    if method == POST_METHOD_REST:
        return publish_to_wordpress(article)
    raise RuntimeError(f"Unsupported WP_POST_METHOD: {method}")


def save_preview(article: dict[str, Any], cluster: list[Item]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = article.get("slug") or slugify(article["title"])
    path = OUT_DIR / f"{timestamp}-{slug}.html"
    source_comment = "\n".join(f"<!-- source: {item.link} -->" for item in cluster)
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(article["title"])}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
{source_comment}
<h1>{html.escape(article["title"])}</h1>
{render_article_html(article, article_hero_path(article).as_uri() if article_hero_path(article) else "")}
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")
    return path


def mark_used(conn: sqlite3.Connection, cluster: list[Item], article: dict[str, Any], wp_id: int | None, status: str) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for item in cluster:
        conn.execute("UPDATE items SET used_at = ? WHERE uid = ?", (now, item.uid))
    conn.execute(
        """
        INSERT INTO posts (topic_key, title, status, wp_id, categories_json, source_links_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            topic_key(cluster),
            article["title"],
            status,
            wp_id,
            json.dumps([str(value) for value in article.get("categories", [])]),
            json.dumps([item.link for item in cluster]),
            now,
        ),
    )
    conn.commit()


def todays_post_count(conn: sqlite3.Connection) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM posts
        WHERE created_at >= ?
        AND status IN ('publish', 'sent', 'future')
        """,
        (start.isoformat(),),
    ).fetchone()
    return int(row[0] if row else 0)


def infer_categories_from_title(title: str) -> list[str]:
    synthetic = Item(
        uid=stable_id("title", title),
        source_name="post",
        source_url="",
        source_category="tech",
        source_quality=3,
        title=title,
        link="",
        summary="",
        published_at=None,
    )
    return story_categories([synthetic], title, list(tokens_for(synthetic))[:6])


def recent_category_counts(conn: sqlite3.Connection) -> dict[str, int]:
    limit = max(0, env_int("RECENT_CATEGORY_WINDOW", 8))
    if limit <= 0:
        return {}
    rows = conn.execute(
        """
        SELECT title, categories_json
        FROM posts
        WHERE status IN ('publish', 'sent', 'future')
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    counts: dict[str, int] = {}
    for title, categories_json in rows:
        categories = categories_from_post_row(str(title), categories_json)
        for category in categories:
            counts[category] = counts.get(category, 0) + 1
    return counts


def categories_from_post_row(title: str, categories_json: str | None) -> list[str]:
    categories: list[str] = []
    if categories_json:
        try:
            categories = [str(value).lower() for value in json.loads(categories_json)]
        except json.JSONDecodeError:
            categories = []
    return categories or infer_categories_from_title(str(title))


def last_rotation_category(conn: sqlite3.Connection, rotation: list[str]) -> str | None:
    if not rotation:
        return None
    rows = conn.execute(
        """
        SELECT title, categories_json
        FROM posts
        WHERE status IN ('publish', 'sent', 'future')
        ORDER BY created_at DESC
        LIMIT 20
        """
    ).fetchall()
    for title, categories_json in rows:
        categories = categories_from_post_row(str(title), categories_json)
        for category in categories:
            if category in rotation:
                return category
    return None


def next_rotation_order(conn: sqlite3.Connection) -> list[str]:
    rotation = category_rotation()
    if not rotation:
        return []
    last_category = last_rotation_category(conn, rotation)
    if last_category not in rotation:
        return rotation
    next_index = (rotation.index(last_category) + 1) % len(rotation)
    return rotation[next_index:] + rotation[:next_index]


def rotation_bucket(categories: list[str], order: list[str]) -> int:
    if not order:
        return 0
    indexes = [order.index(category) for category in categories if category in order]
    return min(indexes) if indexes else len(order)


def category_diversity_penalty(categories: list[str], recent_counts: dict[str, int]) -> int:
    penalty_unit = max(0, env_int("RECENT_CATEGORY_PENALTY", 4))
    return sum(recent_counts.get(category, 0) * penalty_unit for category in categories[:3])


def ranked_clusters(conn: sqlite3.Connection, clusters: list[list[Item]]) -> list[list[Item]]:
    recent_counts = recent_category_counts(conn)
    rotation_order = next_rotation_order(conn)

    def rank(cluster: list[Item]) -> tuple[int, int, int, int, int, dt.datetime]:
        categories = cluster_categories(cluster)
        priority = editorial_priority_score(cluster) - category_diversity_penalty(categories, recent_counts)
        return (
            -rotation_bucket(categories, rotation_order),
            priority,
            focus_score(cluster),
            len({item.source_name for item in cluster}),
            sum(item.source_quality for item in cluster),
            max(item.sort_time for item in cluster),
        )

    return sorted(clusters, key=rank, reverse=True)


def run_once(args: argparse.Namespace) -> int:
    load_env()
    lock_acquired = False
    if not args.dry_run:
        lock_acquired, lock_message = acquire_run_lock()
        if not lock_acquired:
            print(lock_message)
            write_run_status("skipped", lock_message, dry_run=False)
            return 0

    delivered_posts: list[dict[str, Any]] = []
    preview_paths: list[str] = []
    timeout = env_int("REQUEST_TIMEOUT_SECONDS", 25)
    try:
        feeds = load_config()
        conn = init_db()
        if not args.dry_run:
            max_posts_per_day = max(1, env_int("MAX_POSTS_PER_DAY", 24))
            posted_today = todays_post_count(conn)
            if posted_today >= max_posts_per_day:
                message = f"Daily cap reached: {posted_today}/{max_posts_per_day} posts already sent today."
                print(message)
                write_run_status(
                    "skipped",
                    message,
                    dry_run=False,
                    posted_today=posted_today,
                    max_posts_per_day=max_posts_per_day,
                )
                return 0

        print(f"Fetching {len(feeds)} enabled feeds...")
        items, errors = fetch_all(feeds, timeout)
        inserted = save_items(conn, items)
        print(f"Fetched {len(items)} items; {inserted} new.")
        if errors:
            print("Feed warnings:")
            for error in errors[:12]:
                print(f"  - {error}")
            if len(errors) > 12:
                print(f"  - ...and {len(errors) - 12} more")

        recent = recent_unused_items(conn, env_int("LOOKBACK_HOURS", 96))
        clusters = ranked_clusters(conn, build_clusters(recent, env_int("MIN_SOURCES_PER_POST", 2)))
        if not clusters:
            message = "No usable multi-source clusters found."
            print(message)
            write_run_status(
                "skipped",
                message,
                dry_run=args.dry_run,
                feeds=len(feeds),
                fetched=len(items),
                inserted=inserted,
                feed_warnings=len(errors),
            )
            return 0

        rotation_order = next_rotation_order(conn)
        if rotation_order:
            print(f"Category rotation target order: {', '.join(rotation_order[:5])}")

        max_posts = max(1, env_int("MAX_POSTS_PER_RUN", 1))
        selected = clusters[:max_posts]
        for cluster in selected:
            unique_sources = sorted({item.source_name for item in cluster})
            source_names = ", ".join(unique_sources)
            category_names = ", ".join(cluster_categories(cluster))
            print(f"Generating {category_names} post from {len(cluster)} items across {len(unique_sources)} sources: {source_names}")
            article = generate_article(cluster)

            if args.dry_run:
                preview = save_preview(article, cluster)
                preview_paths.append(str(preview))
                print(f"Dry-run preview written: {preview}")
                continue

            result = deliver_article(article)
            raw_wp_id = result.get("id")
            wp_id = int(raw_wp_id) if raw_wp_id not in {None, ""} else None
            status = str(result.get("status", os.getenv("POST_STATUS", "draft")))
            mark_used(conn, cluster, article, wp_id, status)
            delivered_posts.append(
                {
                    "title": article["title"],
                    "status": status,
                    "wp_id": wp_id,
                    "categories": article.get("categories", []),
                    "sources": unique_sources,
                }
            )
            if wp_id:
                print(f"Created WordPress post {wp_id} with status={status}: {result.get('link', '')}")
            else:
                print(f"Delivered post with status={status}: {result.get('link', '')}")

            time.sleep(1)

        if args.dry_run:
            write_run_status(
                "dry_run_ok",
                f"Dry run generated {len(preview_paths)} preview file(s).",
                dry_run=True,
                feeds=len(feeds),
                fetched=len(items),
                inserted=inserted,
                feed_warnings=len(errors),
                previews=preview_paths,
            )
        else:
            write_run_status(
                "published",
                f"Published {len(delivered_posts)} post(s).",
                dry_run=False,
                feeds=len(feeds),
                fetched=len(items),
                inserted=inserted,
                feed_warnings=len(errors),
                posts=delivered_posts,
            )
        return 0
    except Exception as exc:
        write_run_status(
            "failed",
            f"{type(exc).__name__}: {exc}",
            dry_run=args.dry_run,
        )
        raise
    finally:
        if lock_acquired:
            release_run_lock()


def print_status() -> int:
    load_env()
    status = read_json_file(RUN_STATUS_PATH)
    if status:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print("No last-run status file found yet.")
    if RUN_LOCK_PATH.exists():
        print("Active lock:")
        print(json.dumps(read_json_file(RUN_LOCK_PATH), indent=2, sort_keys=True))
    conn = init_db()
    print(f"Posts today: {todays_post_count(conn)}/{max(1, env_int('MAX_POSTS_PER_DAY', 24))}")
    rows = conn.execute(
        """
        SELECT title, status, created_at
        FROM posts
        ORDER BY created_at DESC
        LIMIT 5
        """
    ).fetchall()
    if rows:
        print("Recent posts:")
        for title, status, created_at in rows:
            print(f"- {created_at} [{status}] {title}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated original WordPress posts from curated feeds.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Fetch feeds, generate a post, and draft/publish it.")
    run_parser.add_argument("--dry-run", action="store_true", help="Write preview files only; do not call WordPress.")
    subparsers.add_parser("status", help="Show the last run status and recent posting memory.")
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_once(args)
    if args.command == "status":
        return print_status()
    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
