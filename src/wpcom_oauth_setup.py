from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

TOKEN_URL = "https://public-api.wordpress.com/oauth2/token"
USER_AGENT = "WordPressAutoBlogWpComOAuth/0.1"

AUTH_HINT = (
    "WordPress.com hosted (free) sites do not accept HTTP Basic auth with an application "
    "password for REST write access. You must register a WordPress.com application to obtain "
    "an OAuth2 access token:\n\n"
    "1. Open https://developer.wordpress.com/apps/new/\n"
    "2. Name it (e.g. 'auto-blog'), set Redirect URL to http://127.0.0.1:9999/callback\n"
    "3. After creating it, copy the Client ID and Client Secret.\n"
    "4. Put them in .env as WPCOM_CLIENT_ID and WPCOM_CLIENT_SECRET.\n"
    "5. Re-run this script. It exchanges your username + application password for an OAuth2 "
    "token and saves WP_COM_ACCESS_TOKEN to .env."
)


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
        if key and key not in os.environ:
            os.environ[key] = value


def update_env_file(values: dict[str, str], path: Path = ENV_PATH) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
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


def token_exchange(client_id: str, client_secret: str, username: str, password: str) -> dict:
    form = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "password",
            "username": username,
            "password": password,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
    }
    request = urllib.request.Request(TOKEN_URL, data=form, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            pass
        raise RuntimeError(f"Token request failed with HTTP {exc.code}: {body[:400]}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exchange a WordPress.com username + application password for an OAuth2 token."
    )
    parser.add_argument("--client-id", help="WordPress.com OAuth2 Client ID (or WPCOM_CLIENT_ID in .env).")
    parser.add_argument("--client-secret", help="WordPress.com OAuth2 Client Secret (or WPCOM_CLIENT_SECRET in .env).")
    args = parser.parse_args()

    load_env()
    client_id = args.client_id or os.getenv("WPCOM_CLIENT_ID", "").strip()
    client_secret = args.client_secret or os.getenv("WPCOM_CLIENT_SECRET", "").strip()
    username = os.getenv("WP_USERNAME", "").strip()
    password = os.getenv("WP_APPLICATION_PASSWORD", "").strip()

    if not client_id or not client_secret:
        print(AUTH_HINT, file=sys.stderr)
        return 2
    if not username or not password:
        print("WP_USERNAME and WP_APPLICATION_PASSWORD must be set in .env.", file=sys.stderr)
        return 2

    print("Exchanging application password for an OAuth2 token...")
    result = token_exchange(client_id, client_secret, username, password)

    access_token = result.get("access_token")
    if not access_token:
        print("No access_token in response; token exchange failed.", file=sys.stderr)
        return 1

    updates: dict[str, str] = {"WP_COM_ACCESS_TOKEN": access_token}
    if result.get("refresh_token"):
        updates["WP_COM_REFRESH_TOKEN"] = str(result["refresh_token"])
    expires_in = result.get("expires_in")
    if expires_in:
        expiry = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=int(expires_in))
        updates["WP_COM_TOKEN_EXPIRES_AT"] = expiry.isoformat()

    update_env_file(updates, ENV_PATH)
    print("OAuth2 token saved to .env as WP_COM_ACCESS_TOKEN (not shown).")
    if result.get("blog_url"):
        print("Authorized blog:", result["blog_url"])
    if updates.get("WP_COM_TOKEN_EXPIRES_AT"):
        print("Token expires at:", updates["WP_COM_TOKEN_EXPIRES_AT"])
    if updates.get("WP_COM_REFRESH_TOKEN"):
        print("A refresh token was also saved (WP_COM_REFRESH_TOKEN).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
