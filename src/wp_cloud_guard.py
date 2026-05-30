#!/usr/bin/env python3
"""Independent GitHub Actions rescue guard for the WordPress publisher."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from wp_failover_publish import (
    DATA_DIR,
    DEFAULT_FEED_URL,
    fetch_latest_post,
    latest_post_age_minutes,
    load_env,
    redact,
    utc_now,
)


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = DATA_DIR / "cloud_guard_status.json"
DEFAULT_MAIN_WORKFLOW_FILE = "wordpress-autoblog.yml"
DEFAULT_MAIN_RUN_STALE_MINUTES = 95
DEFAULT_RESCUE_STALE_MINUTES = 35
DEFAULT_RESCUE_FORCE_STALE_MINUTES = 50
DEFAULT_RESCUE_EMERGENCY_STALE_MINUTES = 90
GITHUB_API = "https://api.github.com"


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


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


def parse_github_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc)


def run_age_minutes(run: dict[str, Any]) -> int | None:
    created = parse_github_time(str(run.get("created_at") or ""))
    if created is None:
        return None
    return max(0, int((utc_now() - created).total_seconds() // 60))


def github_request(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{GITHUB_API}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "WordPressAutoBlogCloudGuard/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def list_workflow_runs(repo: str, workflow_file: str, token: str, status: str) -> list[dict[str, Any]]:
    workflow = urllib.parse.quote(workflow_file, safe="")
    path = f"/repos/{repo}/actions/workflows/{workflow}/runs?status={status}&per_page=20"
    payload = github_request("GET", path, token)
    if not payload:
        return []
    runs = payload.get("workflow_runs")
    return runs if isinstance(runs, list) else []


def active_main_runs(repo: str, workflow_file: str, token: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for status in ("in_progress", "queued", "waiting", "requested"):
        try:
            runs.extend(list_workflow_runs(repo, workflow_file, token, status))
        except urllib.error.HTTPError as exc:
            if exc.code != 422:
                raise
    seen: set[int] = set()
    unique_runs: list[dict[str, Any]] = []
    for run in runs:
        run_id = int(run.get("id") or 0)
        if run_id and run_id not in seen:
            unique_runs.append(run)
            seen.add(run_id)
    return unique_runs


def cancel_run(repo: str, run_id: int, token: str) -> None:
    github_request("POST", f"/repos/{repo}/actions/runs/{run_id}/cancel", token)


def run_publisher() -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / "src" / "wp_failover_publish.py")]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=650)


def compact_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for run in runs:
        compact.append(
            {
                "id": run.get("id"),
                "status": run.get("status"),
                "event": run.get("event"),
                "created_at": run.get("created_at"),
                "age_minutes": run_age_minutes(run),
                "html_url": run.get("html_url"),
            }
        )
    return compact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rescue guard for the WordPress cloud watchdog.")
    parser.add_argument("--publish", action="store_true", help="Run the failover publisher when rescue rules allow it.")
    args = parser.parse_args(argv)

    load_env()
    feed_url = os.getenv("BLOG_FEED_URL", DEFAULT_FEED_URL).strip() or DEFAULT_FEED_URL
    rescue_stale_minutes = env_int("RESCUE_STALE_MINUTES", DEFAULT_RESCUE_STALE_MINUTES)
    force_stale_minutes = env_int("RESCUE_FORCE_STALE_MINUTES", DEFAULT_RESCUE_FORCE_STALE_MINUTES)
    emergency_stale_minutes = env_int("RESCUE_EMERGENCY_STALE_MINUTES", DEFAULT_RESCUE_EMERGENCY_STALE_MINUTES)
    main_run_stale_minutes = env_int("MAIN_WATCHDOG_STALE_MINUTES", DEFAULT_MAIN_RUN_STALE_MINUTES)
    workflow_file = os.getenv("MAIN_WORKFLOW_FILE", DEFAULT_MAIN_WORKFLOW_FILE).strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or ""

    try:
        latest = fetch_latest_post(feed_url)
        age_minutes = latest_post_age_minutes(latest)
    except Exception as exc:  # noqa: BLE001 - guard status needs the exact failure text.
        write_status(
            "feed_check_failed",
            "Rescue did not publish because public feed freshness could not be confirmed.",
            error=str(exc),
            feed_url=feed_url,
        )
        print(f"Feed check failed: {exc}")
        return 1

    github_error = ""
    active_runs: list[dict[str, Any]] = []
    stale_runs: list[dict[str, Any]] = []
    fresh_runs: list[dict[str, Any]] = []
    if repo and token and workflow_file:
        try:
            active_runs = active_main_runs(repo, workflow_file, token)
            for run in active_runs:
                age = run_age_minutes(run)
                if age is not None and age >= main_run_stale_minutes:
                    stale_runs.append(run)
                else:
                    fresh_runs.append(run)
            for run in stale_runs:
                run_id = int(run.get("id") or 0)
                if run_id:
                    cancel_run(repo, run_id, token)
        except Exception as exc:  # noqa: BLE001 - status artifact should record API failure.
            github_error = str(exc)
    else:
        github_error = "Missing GITHUB_REPOSITORY or GH_TOKEN/GITHUB_TOKEN."

    latest_details = {
        "latest_title": latest.get("title", ""),
        "latest_link": latest.get("link", ""),
        "latest_published_at": latest["published_at"].isoformat(),
        "latest_age_minutes": age_minutes,
        "rescue_stale_minutes": rescue_stale_minutes,
        "rescue_force_stale_minutes": force_stale_minutes,
        "rescue_emergency_stale_minutes": emergency_stale_minutes,
        "main_run_stale_minutes": main_run_stale_minutes,
        "active_main_runs": compact_runs(active_runs),
        "fresh_main_runs": compact_runs(fresh_runs),
        "cancelled_stale_main_runs": compact_runs(stale_runs),
        "github_error": github_error,
    }

    if age_minutes < rescue_stale_minutes:
        write_status("fresh", "Latest post is fresh; rescue did not publish.", **latest_details)
        print(f"Fresh: latest post is {age_minutes} minutes old; rescue threshold is {rescue_stale_minutes}.")
        return 0

    if fresh_runs and age_minutes < force_stale_minutes:
        write_status("main_watchdog_active", "Main watchdog is active; rescue stood down.", **latest_details)
        print(
            "Main watchdog active: latest post is "
            f"{age_minutes} minutes old; force threshold is {force_stale_minutes}."
        )
        return 0

    if github_error and age_minutes < emergency_stale_minutes:
        write_status(
            "github_check_failed",
            "Could not verify main watchdog, and feed is not old enough for emergency publishing.",
            **latest_details,
        )
        print(f"GitHub check failed and latest post is only {age_minutes} minutes old: {github_error}")
        return 1

    if not args.publish:
        write_status("rescue_ready", "Feed is stale enough for rescue, but publish mode was not enabled.", **latest_details)
        print(f"Rescue ready: latest post is {age_minutes} minutes old.")
        return 0

    result = run_publisher()
    stdout = redact(result.stdout[-4000:])
    stderr = redact(result.stderr[-4000:])
    state = "publisher_succeeded" if result.returncode == 0 else "publisher_failed"
    write_status(
        state,
        "Rescue guard ran the stale-feed publisher.",
        publisher_returncode=result.returncode,
        publisher_stdout=stdout,
        publisher_stderr=stderr,
        **latest_details,
    )
    if stdout:
        print(stdout.rstrip())
    if stderr:
        print(stderr.rstrip(), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
