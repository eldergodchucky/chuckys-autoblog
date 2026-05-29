#!/usr/bin/env python3
"""Publish only when the public WordPress feed has gone stale."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DATA_DIR = ROOT / "data"
STATUS_PATH = DATA_DIR / "failover_status.json"
PUBLISH_MARKER_PATH = DATA_DIR / "failover_last_publish.json"
PUBLISHER_STATUS_PATH = DATA_DIR / "last_run_status.json"
LOCK_PATH = DATA_DIR / "failover.lock"

DEFAULT_FEED_URL = "https://chuckyscarnage.tech.blog/feed/"
DEFAULT_WP_PUBLIC_POSTS_API_URL = (
    "https://public-api.wordpress.com/rest/v1.1/sites/"
    "chuckyscarnage.tech.blog/posts/?number=1&fields=title,URL,date"
)
DEFAULT_STALE_MINUTES = 75
DEFAULT_COOLDOWN_MINUTES = 75
DEFAULT_LOCK_STALE_MINUTES = 30
USER_AGENT = "WordPressAutoBlogFailover/0.1 (+https://wordpress.org/)"
SECRET_PATTERNS = (
    re.compile(r"[\w.+-]+@post\.wordpress\.com", re.IGNORECASE),
)


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def write_status(state: str, message: str, **details: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "message": message,
        "finished_at": utc_now().isoformat(),
        **details,
    }
    temp_path = STATUS_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(STATUS_PATH)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_datetime(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def write_publish_marker(publisher_status: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    posts = publisher_status.get("posts") or []
    first_post = posts[0] if posts and isinstance(posts[0], dict) else {}
    payload = {
        "finished_at": utc_now().isoformat(),
        "publisher_finished_at": publisher_status.get("finished_at"),
        "title": first_post.get("title", ""),
        "state": publisher_status.get("state", ""),
    }
    temp_path = PUBLISH_MARKER_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(PUBLISH_MARKER_PATH)


def last_success_age_minutes() -> int | None:
    for path in (PUBLISH_MARKER_PATH, PUBLISHER_STATUS_PATH):
        status = read_json(path)
        if status.get("state") not in {"published", "publisher_succeeded"}:
            continue
        finished_at = parse_datetime(status.get("finished_at"))
        if finished_at is None:
            continue
        age = utc_now() - finished_at
        return max(0, int(age.total_seconds() // 60))
    return None


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


def existing_lock_is_alive() -> bool:
    try:
        payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    try:
        pid = int(payload.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    return process_exists(pid)


def acquire_lock(stale_minutes: int) -> bool:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if not existing_lock_is_alive():
            try:
                LOCK_PATH.unlink()
            except OSError:
                return False
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        else:
            try:
                age_seconds = utc_now().timestamp() - LOCK_PATH.stat().st_mtime
            except OSError:
                age_seconds = 0
            if age_seconds < stale_minutes * 60:
                return False
            try:
                LOCK_PATH.unlink()
            except OSError:
                return False
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "started_at": utc_now().isoformat()}))
    return True


def release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def redact(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_POST_BY_EMAIL]", redacted)
    return redacted


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_latest_post_from_rss(feed_url: str) -> dict[str, Any]:
    request = urllib.request.Request(feed_url, headers={"User-Agent": USER_AGENT})
    body = fetch_url(request.full_url)
    root = ET.fromstring(body)
    item = root.find("./channel/item")
    if item is None:
        raise RuntimeError("Feed has no items.")

    title = (item.findtext("title") or "").strip()
    link = (item.findtext("link") or "").strip()
    pub_date_raw = (item.findtext("pubDate") or "").strip()
    if not pub_date_raw:
        raise RuntimeError("Latest feed item has no pubDate.")

    pub_date = parsedate_to_datetime(pub_date_raw)
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=dt.timezone.utc)

    return {
        "title": title,
        "link": link,
        "published_at": pub_date.astimezone(dt.timezone.utc),
        "published_at_raw": pub_date_raw,
        "freshness_source": "rss",
    }


def fetch_latest_post_from_wp_api(api_url: str) -> dict[str, Any]:
    payload = json.loads(fetch_url(api_url).decode("utf-8"))
    posts = payload.get("posts") or []
    if not posts:
        raise RuntimeError("WordPress public API returned no posts.")

    post = posts[0]
    raw_title = post.get("title") or ""
    title = raw_title.get("rendered", "") if isinstance(raw_title, dict) else str(raw_title)
    link = str(post.get("URL") or post.get("url") or post.get("link") or "")
    raw_date = str(post.get("date") or post.get("date_gmt") or "")
    published_at = parse_datetime(raw_date)
    if published_at is None:
        raise RuntimeError("WordPress public API latest post has no parseable date.")

    return {
        "title": title.strip(),
        "link": link.strip(),
        "published_at": published_at,
        "published_at_raw": raw_date,
        "freshness_source": "wordpress_public_api",
    }


def fetch_latest_post(feed_url: str) -> dict[str, Any]:
    try:
        return fetch_latest_post_from_rss(feed_url)
    except (OSError, urllib.error.URLError, ET.ParseError, RuntimeError) as rss_exc:
        api_url = os.getenv("WP_PUBLIC_POSTS_API_URL", DEFAULT_WP_PUBLIC_POSTS_API_URL).strip()
        if not api_url:
            raise
        try:
            latest = fetch_latest_post_from_wp_api(api_url)
            latest["rss_error"] = str(rss_exc)
            return latest
        except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as api_exc:
            raise RuntimeError(f"RSS failed ({rss_exc}); WordPress public API failed ({api_exc})") from api_exc


def latest_post_age_minutes(latest: dict[str, Any]) -> int:
    published_at = latest["published_at"]
    age = utc_now() - published_at
    return max(0, int(age.total_seconds() // 60))


def run_publisher() -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / "src" / "wp_auto_blog.py"), "run"]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stale-feed failover for the WordPress auto blogger.")
    parser.add_argument("--check-only", action="store_true", help="Check feed freshness without publishing.")
    parser.add_argument("--stale-minutes", type=int, default=None, help="Minutes without a post before publishing.")
    args = parser.parse_args(argv)

    load_env()
    feed_url = os.getenv("BLOG_FEED_URL", DEFAULT_FEED_URL).strip() or DEFAULT_FEED_URL
    stale_minutes = args.stale_minutes or env_int("FAILOVER_STALE_MINUTES", DEFAULT_STALE_MINUTES)
    cooldown_minutes = env_int("FAILOVER_COOLDOWN_MINUTES", DEFAULT_COOLDOWN_MINUTES)
    lock_stale_minutes = env_int("FAILOVER_LOCK_STALE_MINUTES", DEFAULT_LOCK_STALE_MINUTES)

    try:
        latest = fetch_latest_post(feed_url)
        age_minutes = latest_post_age_minutes(latest)
    except (OSError, urllib.error.URLError, ET.ParseError, RuntimeError) as exc:
        write_status(
            "skipped",
            "Could not confirm feed freshness, so failover did not publish.",
        error=str(exc),
        feed_url=feed_url,
        api_url=os.getenv("WP_PUBLIC_POSTS_API_URL", DEFAULT_WP_PUBLIC_POSTS_API_URL).strip(),
        stale_minutes=stale_minutes,
        )
        print(f"Skipped: could not confirm feed freshness ({exc}).")
        return 1

    latest_details = {
        "latest_title": latest["title"],
        "latest_link": latest["link"],
        "latest_published_at": latest["published_at"].isoformat(),
        "latest_age_minutes": age_minutes,
        "freshness_source": latest.get("freshness_source", ""),
        "rss_error": latest.get("rss_error", ""),
        "stale_minutes": stale_minutes,
    }

    if age_minutes < stale_minutes:
        write_status("fresh", "Latest public post is still fresh; failover did not publish.", **latest_details)
        print(f"Fresh: latest post is {age_minutes} minutes old; threshold is {stale_minutes}.")
        return 0

    if args.check_only:
        write_status("stale_check_only", "Feed is stale, but check-only mode did not publish.", **latest_details)
        print(f"Stale: latest post is {age_minutes} minutes old; check-only mode enabled.")
        return 0

    cooldown_age = last_success_age_minutes()
    if cooldown_age is not None and cooldown_age < cooldown_minutes:
        write_status(
            "cooldown",
            "A publisher run succeeded recently; failover did not publish again yet.",
            last_success_age_minutes=cooldown_age,
            cooldown_minutes=cooldown_minutes,
            **latest_details,
        )
        print(f"Cooldown: last successful publisher run was {cooldown_age} minutes ago.")
        return 0

    if not acquire_lock(lock_stale_minutes):
        write_status("locked", "Another failover run is already active.", **latest_details)
        print("Locked: another failover run is already active.")
        return 0

    try:
        latest = fetch_latest_post(feed_url)
        age_minutes = latest_post_age_minutes(latest)
        latest_details.update(
            {
                "latest_title": latest["title"],
                "latest_link": latest["link"],
                "latest_published_at": latest["published_at"].isoformat(),
                "latest_age_minutes": age_minutes,
            }
        )
        if age_minutes < stale_minutes:
            write_status("fresh", "Latest public post became fresh before failover published.", **latest_details)
            print(f"Fresh: latest post is {age_minutes} minutes old; threshold is {stale_minutes}.")
            return 0

        result = run_publisher()
        publisher_status = read_json(PUBLISHER_STATUS_PATH)
        publisher_state = publisher_status.get("state", "")
        if result.returncode == 0 and publisher_state == "published":
            write_publish_marker(publisher_status)

        if result.returncode == 0 and publisher_state == "published":
            state = "publisher_succeeded"
        elif result.returncode == 0:
            state = "publisher_skipped"
        else:
            state = "publisher_failed"
        message = "Feed was stale, so failover ran the WordPress publisher."
        write_status(
            state,
            message,
            publisher_returncode=result.returncode,
            publisher_state=publisher_state,
            publisher_stdout=redact(result.stdout[-4000:]),
            publisher_stderr=redact(result.stderr[-4000:]),
            **latest_details,
        )
    finally:
        release_lock()

    if result.stdout:
        print(redact(result.stdout.rstrip()))
    if result.stderr:
        print(redact(result.stderr.rstrip()), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
