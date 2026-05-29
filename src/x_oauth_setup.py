#!/usr/bin/env python3
"""Local OAuth setup for granting this automation permission to post to X."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
AUTH_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DEFAULT_SCOPES = "tweet.read tweet.write users.read offline.access"


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
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
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


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def token_request(data: dict[str, str], client_id: str, client_secret: str) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "WordPressAutoBlogXOAuth/0.1",
    }
    form = dict(data)
    if client_secret:
        token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    else:
        form["client_id"] = client_id

    request = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X token request failed: HTTP {error.code}: {body}") from error


def callback_server(expected_state: str, host: str, port: int) -> str:
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            state = query.get("state", [""])[0]
            code = query.get("code", [""])[0]
            error = query.get("error", [""])[0]

            if error:
                result["error"] = error
            elif state != expected_state:
                result["error"] = "state_mismatch"
            elif code:
                result["code"] = code
            else:
                result["error"] = "missing_code"

            message = "X authorization received. You can close this tab and return to Codex."
            if result.get("error"):
                message = f"X authorization failed: {html.escape(result['error'])}"

            body = f"<!doctype html><title>X OAuth</title><p>{message}</p>".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer((host, port), Handler) as server:
        print(f"Waiting for X callback on http://{host}:{port}/callback ...")
        server.handle_request()

    if result.get("error"):
        raise RuntimeError(f"Authorization failed: {result['error']}")
    if not result.get("code"):
        raise RuntimeError("Authorization failed: no code returned.")
    return result["code"]


def main() -> int:
    load_env()
    client_id = os.getenv("X_CLIENT_ID", "").strip()
    client_secret = os.getenv("X_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("X_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip() or DEFAULT_REDIRECT_URI
    scopes = os.getenv("X_OAUTH_SCOPES", DEFAULT_SCOPES).strip() or DEFAULT_SCOPES

    if not client_id:
        print("Add X_CLIENT_ID to .env first. You get it from your X Developer App's Keys and Tokens page.", file=sys.stderr)
        return 2

    parsed_redirect = urllib.parse.urlsplit(redirect_uri)
    if parsed_redirect.scheme != "http" or parsed_redirect.hostname not in {"127.0.0.1", "localhost"}:
        print("For this helper, set X_REDIRECT_URI to http://127.0.0.1:8765/callback", file=sys.stderr)
        return 2

    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("Opening X authorization page. Sign in to the X account that should post, then approve the app.")
    print()
    print(authorize_url)
    print()
    webbrowser.open(authorize_url)

    port = parsed_redirect.port or 8765
    code = callback_server(state, parsed_redirect.hostname or "127.0.0.1", port)
    token_response = token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        client_id,
        client_secret,
    )

    access_token = str(token_response.get("access_token", "")).strip()
    refresh_token = str(token_response.get("refresh_token", "")).strip()
    expires_in = int(token_response.get("expires_in", 0) or 0)
    if not access_token:
        raise RuntimeError(f"X did not return an access token: {token_response}")

    values = {
        "X_CLIENT_ID": client_id,
        "X_REDIRECT_URI": redirect_uri,
        "X_OAUTH_SCOPES": scopes,
        "X_USER_ACCESS_TOKEN": access_token,
    }
    if client_secret:
        values["X_CLIENT_SECRET"] = client_secret
    if refresh_token:
        values["X_REFRESH_TOKEN"] = refresh_token
    if expires_in:
        import datetime as dt

        expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=expires_in)
        values["X_TOKEN_EXPIRES_AT"] = expires_at.isoformat()

    update_env_file(values)
    print("X access was saved to .env. The blog sharer can now post future feed items automatically.")
    if not refresh_token:
        print("Warning: X did not return a refresh token. Confirm your app requested offline.access.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
