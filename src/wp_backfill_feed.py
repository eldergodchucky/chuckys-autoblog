#!/usr/bin/env python3
"""Bring historic WordPress posts in line with the compact archive format."""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import wp_auto_blog as wp

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


IMAGE_RE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
PLACEHOLDERS = {"", "__HERO_IMAGE_SRC__", wp.HERO_IMAGE_PLACEHOLDER}


def retry_call(description: str, path: str, payload: dict | None = None, method: str = "GET", tries: int = 4) -> object:
    for attempt in range(1, tries + 1):
        try:
            return wp.wp_request(path, payload, method=method)
        except Exception as exc:
            if attempt >= tries:
                raise
            print(f"  {description} attempt {attempt}/{tries} failed ({type(exc).__name__}: {exc}); retrying")
            time.sleep(3 * attempt)


def post_content(post: dict) -> str:
    content = post.get("content", {})
    if isinstance(content, dict):
        return str(content.get("raw") or content.get("rendered") or "")
    return str(content or "")


def first_image_url(content: str) -> str:
    match = IMAGE_RE.search(content)
    return html.unescape(match.group(1).strip()) if match else ""


def download_image(url: str, title: str) -> Path | None:
    request = urllib.request.Request(url, headers={"User-Agent": wp.USER_AGENT, "Accept": "image/*"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                return None
            extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type, ".img")
            descriptor, name = tempfile.mkstemp(prefix="wp-featured-", suffix=extension)
            os.close(descriptor)
            path = Path(name)
            path.write_bytes(response.read())
            return path
    except Exception as exc:
        print(f"  Could not download image: {type(exc).__name__}: {exc}")
        return None


def generated_fallback(title: str) -> Path | None:
    keywords = wp.top_keywords([], 5) or [word.lower() for word in re.findall(r"[A-Za-z0-9]+", title)[:5]]
    return wp.create_hero_image(title, keywords, ["tech"], [])


def media_for_post(post_id: int) -> int | None:
    response = retry_call(f"media for post {post_id}", f"media?parent={post_id}&per_page=20")
    if not isinstance(response, list):
        return None
    for media in response:
        media_id = media.get("id") or media.get("ID")
        mime_type = str(media.get("mime_type", ""))
        if media_id and (not mime_type or mime_type.startswith("image/")):
            return int(media_id)
    return None


def backfill(apply: bool, limit: int) -> int:
    wp.load_env()
    page = 1
    checked = changed = featured = skipped = 0
    while True:
        # WordPress.com can time out on large authenticated edit responses.
        # Smaller pages keep the historic repair reliable as well.
        response = retry_call(f"fetch posts page {page}", f"posts?status=publish&per_page=20&page={page}&context=edit")
        if not isinstance(response, list) or not response:
            break
        for post in response:
            if limit and checked >= limit:
                break
            checked += 1
            post_id = int(post["id"])
            title = html.unescape(str(post.get("title", {}).get("raw") or post.get("title", {}).get("rendered") or "Untitled"))
            content = post_content(post)

            media_id = int(post.get("featured_media") or 0)
            if not media_id:
                media_id = media_for_post(post_id) or 0
            temporary: Path | None = None
            if not media_id and apply:
                image_url = first_image_url(content)
                if image_url not in PLACEHOLDERS:
                    temporary = download_image(image_url, title)
                if temporary is None:
                    temporary = generated_fallback(title)
                if temporary:
                    try:
                        media_id = wp.upload_media_multipart(temporary, title) or 0
                    except Exception as exc:
                        print(f"  Could not upload featured image: {type(exc).__name__}: {exc}")
                    finally:
                        if temporary.name.startswith("wp-featured-"):
                            temporary.unlink(missing_ok=True)

            compacted = wp.compact_feed_content(content, bool(media_id))
            payload: dict[str, object] = {}
            if compacted != content:
                payload["content"] = compacted
            if media_id:
                payload["featured_media"] = media_id

            if not payload:
                skipped += 1
                continue
            print(f"{'Would update' if not apply else 'Updating'} {post_id}: {title[:72]}")
            if apply:
                retry_call(f"update post {post_id}", f"posts/{post_id}", payload, method="POST")
                changed += 1
                if "featured_media" in payload:
                    featured += 1
                time.sleep(0.2)
        if limit and checked >= limit:
            break
        page += 1
    print(f"Checked {checked}; updated {changed}; featured images set {featured}; unchanged {skipped}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Make the changes. Omit for a read-only preview.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum posts to inspect; 0 means all published posts.")
    args = parser.parse_args()
    return backfill(args.apply, max(0, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
