#!/usr/bin/env python3
"""Share newly published blog feed items to X using the official API."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "x_shared_posts.json"
X_CREATE_POST_URL = "https://api.x.com/2/tweets"
X_TOKEN_URL = "https://api.x.com/2/oauth2/token"
USER_AGENT = "WordPressAutoBlogXShare/0.1 (+https://wordpress.org/)"
DEFAULT_BLOG_FEED_URL = "https://chuckyscarnage.tech.blog/feed/"
DEFAULT_TEMPLATE = "New on Chucky's Carnage: {title}\n{link}"


@dataclass(frozen=True)
class BlogPost:
    key: str
    title: str
    link: str
    published_at: dt.datetime | None

    @property
    def sort_time(self) -> dt.datetime:
        return self.published_at or dt.datetime.now(dt.timezone.utc)


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def update_env_file(values: dict[str, str], path: Path = ENV_PATH) -> None:
    for key, value in values.items():
        os.environ[key] = value
    if not path.exists():
        return

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    indexes: dict[str, int] = {}
    for index, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        indexes[key] = index

    for key, value in values.items():
        rendered = f"{key}={value}"
        if key in indexes:
            lines[indexes[key]] = rendered
        else:
            lines.append(rendered)

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_iso_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(html.unescape(url.strip()))
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    filtered = [(key, value) for key, value in query if not key.lower().startswith("utm_")]
    cleaned = parsed._replace(query=urllib.parse.urlencode(filtered), fragment="")
    return urllib.parse.urlunsplit(cleaned)


def stable_key(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    value = value.strip()
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


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if local_name(child.tag) in names and child.text:
            return html.unescape(child.text.strip())
    return ""


def entry_link(element: ET.Element) -> str:
    direct = child_text(element, {"link"})
    if direct:
        return canonical_url(direct)
    for child in list(element):
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "").strip()
        rel = child.attrib.get("rel", "alternate").lower()
        if href and rel in {"alternate", ""}:
            return canonical_url(href)
    return ""


def parse_feed(raw_xml: bytes) -> list[BlogPost]:
    root = ET.fromstring(raw_xml)
    root_tag = local_name(root.tag)
    if root_tag == "rss":
        channel = next((child for child in list(root) if local_name(child.tag) == "channel"), root)
        entries = [child for child in list(channel) if local_name(child.tag) == "item"]
    elif root_tag == "feed":
        entries = [child for child in list(root) if local_name(child.tag) == "entry"]
    else:
        entries = list(root)

    posts: list[BlogPost] = []
    for entry in entries:
        title = child_text(entry, {"title"}) or "New blog post"
        link = entry_link(entry)
        if not link:
            continue
        guid = child_text(entry, {"guid", "id"})
        published = parse_date(child_text(entry, {"pubdate", "published", "updated", "dc:date"}))
        key = stable_key(guid or link, link)
        posts.append(BlogPost(key=key, title=" ".join(title.split()), link=link, published_at=published))
    return posts


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    timeout = env_int("REQUEST_TIMEOUT_SECONDS", 25)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def feed_url_from_env() -> str:
    explicit = os.getenv("BLOG_FEED_URL", "").strip()
    if explicit:
        return explicit
    base_url = os.getenv("WP_BASE_URL", "").strip().rstrip("/")
    if base_url and "your-site.example" not in base_url:
        return f"{base_url}/feed/"
    return DEFAULT_BLOG_FEED_URL


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"initialized_at": "", "seen": {}, "shared": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"initialized_at": "", "seen": {}, "shared": {}}
    if not isinstance(state, dict):
        return {"initialized_at": "", "seen": {}, "shared": {}}
    state.setdefault("initialized_at", "")
    state.setdefault("seen", {})
    state.setdefault("shared", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as temp_file:
        json.dump(state, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
        temp_name = temp_file.name
    os.replace(temp_name, path)


def post_text_for(post: BlogPost) -> str:
    template = os.getenv("X_SHARE_TEMPLATE", DEFAULT_TEMPLATE).replace("\\n", "\n")
    max_chars = max(120, env_int("X_MAX_POST_CHARS", 280))
    text = template.format(title=post.title, link=post.link).strip()
    if len(text) <= max_chars:
        return text

    marker = "{title}"
    if marker not in template:
        return text[: max_chars - 3].rstrip() + "..."

    without_title = template.format(title="", link=post.link).strip()
    title_budget = max(12, max_chars - len(without_title) - 3)
    title = post.title[:title_budget].rstrip() + "..."
    return template.format(title=title, link=post.link).strip()


def post_to_x(access_token: str, text: str) -> dict[str, Any]:
    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        X_CREATE_POST_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=env_int("REQUEST_TIMEOUT_SECONDS", 25)) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X API returned HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach X API: {error}") from error


def refresh_x_access_token() -> str:
    client_id = os.getenv("X_CLIENT_ID", "").strip()
    client_secret = os.getenv("X_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("X_REFRESH_TOKEN", "").strip()
    if not client_id or not refresh_token:
        return ""

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
    }
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    if client_secret:
        token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    else:
        form["client_id"] = client_id

    request = urllib.request.Request(
        X_TOKEN_URL,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=env_int("REQUEST_TIMEOUT_SECONDS", 25)) as response:
            token_response = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X token refresh failed: HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not refresh X token: {error}") from error

    access_token = str(token_response.get("access_token", "")).strip()
    if not access_token:
        raise RuntimeError(f"X token refresh did not return an access token: {token_response}")

    values = {"X_USER_ACCESS_TOKEN": access_token}
    new_refresh_token = str(token_response.get("refresh_token", "")).strip()
    if new_refresh_token:
        values["X_REFRESH_TOKEN"] = new_refresh_token
    expires_in = int(token_response.get("expires_in", 0) or 0)
    if expires_in:
        expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=expires_in)
        values["X_TOKEN_EXPIRES_AT"] = expires_at.isoformat()
    update_env_file(values)
    return access_token


def x_access_token() -> str:
    access_token = os.getenv("X_USER_ACCESS_TOKEN", "").strip()
    expires_at = parse_iso_datetime(os.getenv("X_TOKEN_EXPIRES_AT", "").strip())
    refresh_token = os.getenv("X_REFRESH_TOKEN", "").strip()
    if refresh_token and (not access_token or (expires_at and expires_at <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5))):
        print("Refreshing X access token...")
        return refresh_x_access_token()
    return access_token


def handled_keys(state: dict[str, Any]) -> set[str]:
    return set(state.get("seen", {}).keys()) | set(state.get("shared", {}).keys())


def baseline_existing_posts(state: dict[str, Any], posts: list[BlogPost], reason: str) -> None:
    seen = state.setdefault("seen", {})
    for post in posts:
        seen.setdefault(
            post.key,
            {
                "title": post.title,
                "link": post.link,
                "seen_at": now_iso(),
                "reason": reason,
            },
        )
    state["initialized_at"] = state.get("initialized_at") or now_iso()


def share_posts(args: argparse.Namespace) -> int:
    load_env()
    raw_state_path = Path(os.getenv("X_SHARE_STATE_PATH", str(STATE_PATH))).expanduser()
    state_path = raw_state_path if raw_state_path.is_absolute() else ROOT / raw_state_path
    state_path = state_path.resolve()
    state = load_state(state_path)

    feed_url = args.feed_url or feed_url_from_env()
    print(f"Checking blog feed: {feed_url}")
    try:
        posts = parse_feed(request_bytes(feed_url))
    except (ET.ParseError, urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"Error: could not read blog feed: {error}", file=sys.stderr)
        return 1

    posts = sorted(posts, key=lambda post: post.sort_time)
    print(f"Feed contains {len(posts)} published posts.")

    if args.mark_existing:
        baseline_existing_posts(state, posts, "manual_baseline")
        if not args.dry_run:
            save_state(state_path, state)
        if args.dry_run:
            print(f"Would mark {len(posts)} feed posts as already handled.")
            print("Dry run only. State was not changed.")
        else:
            print(f"Marked {len(posts)} feed posts as already handled.")
        return 0

    if not state.get("initialized_at") and not env_bool("X_SHARE_BACKFILL", False):
        baseline_existing_posts(state, posts, "initial_feed_baseline")
        if not args.dry_run:
            save_state(state_path, state)
        if args.dry_run:
            print("Would save first-run baseline. Future feed posts would be shared to X.")
            print("Dry run only. State was not changed.")
        else:
            print("First run baseline saved. Future feed posts will be shared to X.")
        return 0

    unseen = [post for post in posts if post.key not in handled_keys(state)]
    if not unseen:
        print("No new blog posts to share.")
        return 0

    max_per_run = max(1, env_int("X_SHARE_MAX_PER_RUN", 2))
    selected = unseen[:max_per_run]
    if len(unseen) > len(selected):
        print(f"{len(unseen)} unseen posts found; sharing {len(selected)} this run.")

    if args.dry_run:
        for post in selected:
            print("---")
            print(post_text_for(post))
        print("Dry run only. Nothing was posted to X.")
        return 0

    access_token = x_access_token()
    if not access_token:
        print("X_USER_ACCESS_TOKEN is not set. X sharing is ready but disabled until the token is added.")
        return 0

    shared = state.setdefault("shared", {})
    for post in selected:
        text = post_text_for(post)
        print(f"Sharing to X: {post.title}")
        try:
            response = post_to_x(access_token, text)
        except RuntimeError as error:
            print(f"Error: {error}", file=sys.stderr)
            if "CreditsDepleted" in str(error) or "HTTP 402" in str(error):
                print(
                    "X rejected the post because the developer account has no API credits. "
                    "Add credits in the X Developer Portal, then run this script again.",
                    file=sys.stderr,
                )
            return 1
        post_id = str(response.get("data", {}).get("id", ""))
        shared[post.key] = {
            "title": post.title,
            "link": post.link,
            "shared_at": now_iso(),
            "x_post_id": post_id,
        }
        save_state(state_path, state)
        print(f"Shared: {post.link}" + (f" (X post {post_id})" if post_id else ""))

    state["initialized_at"] = state.get("initialized_at") or now_iso()
    save_state(state_path, state)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Share new WordPress feed posts to X/Twitter.")
    parser.add_argument("--feed-url", help="Override BLOG_FEED_URL for this run.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be shared without posting.")
    parser.add_argument("--mark-existing", action="store_true", help="Mark current feed posts handled without posting.")
    args = parser.parse_args(argv)
    return share_posts(args)


if __name__ == "__main__":
    sys.exit(main())
