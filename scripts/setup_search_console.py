#!/usr/bin/env python3
"""Set up and verify sitemap submission for Google and Bing webmaster tools.

Manual login is always supported. API verification requires OAuth/API tokens;
this script never stores credentials or claims success without a verification
response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass


SITE_URL = "https://chuckyscarnage.tech.blog"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"
ROBOTS_URL = f"{SITE_URL}/robots.txt"
GSC_PROPERTY_URL = f"https://search.google.com/search-console?resource_id={urllib.parse.quote(SITE_URL, safe='')}"
GSC_SITEMAP_URL = f"{GSC_PROPERTY_URL}#/sitemaps"
BWT_SITE_URL = "https://www.bing.com/webmasters/home"
BWT_SITEMAP_URL = "https://www.bing.com/webmasters/sitemaps"
WP_GENERAL_URL = "https://wordpress.com/settings/general/chuckyscarnage.tech.blog"
WP_PRIVACY_URL = "https://wordpress.com/settings/privacy/chuckyscarnage.tech.blog"


@dataclass(frozen=True)
class Report:
    label: str
    ok: bool
    detail: str = ""


def print_checklist() -> None:
    print("ChuckysCarnage search-engine setup")
    print("==================================")
    print(f"Site:    {SITE_URL}")
    print(f"Sitemap: {SITEMAP_URL}")
    print(f"Robots:  {ROBOTS_URL}")
    print()
    print("1. WordPress.com visibility")
    print(f"   Open: {WP_GENERAL_URL}")
    print("   Sign in, confirm the site is Public, and save if changed.")
    print(f"   Open: {WP_PRIVACY_URL}")
    print('   Confirm "Discourage search engines from indexing this site" is unchecked, then save.')
    print()
    print("2. Google Search Console")
    print(f"   Open: {GSC_PROPERTY_URL}")
    print(f"   Add/verify the URL-prefix property: {SITE_URL}")
    print("   Choose Sitemaps, enter exactly: sitemap.xml")
    print("   Click Submit. The resulting row should show Success.")
    print()
    print("3. Bing Webmaster Tools")
    print(f"   Open: {BWT_SITE_URL}")
    print(f"   Add and verify the site: {SITE_URL}")
    print(f"   Open: {BWT_SITEMAP_URL}")
    print(f"   Submit exactly: {SITEMAP_URL}")
    print("   Confirm the sitemap appears with a processed/success status.")
    print()
    print("4. Public checks")
    print(f"   Open {SITEMAP_URL} and confirm it loads.")
    print(f"   Open {ROBOTS_URL} and confirm it does not disallow all crawlers.")
    print()
    print("No Google/Microsoft password is needed by this script. Keep 2FA enabled.")


def request_json(
    url: str,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    payload: bytes | None = None,
) -> tuple[int, object]:
    request = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def verify_public_files() -> list[Report]:
    reports: list[Report] = []
    for label, url, required in (
        ("Sitemap", SITEMAP_URL, "<"),
        ("robots.txt", ROBOTS_URL, ""),
    ):
        status, body = request_json(url)
        text = body if isinstance(body, str) else json.dumps(body)
        disallow_all = any(
            line.strip().lower().replace(" ", "") == "disallow:/"
            for line in text.splitlines()
        )
        ok = status == 200 and required in text and not disallow_all
        reports.append(Report(label, ok, f"HTTP {status}"))
    return reports


def submit_gsc(access_token: str) -> Report:
    encoded_site = urllib.parse.quote(SITE_URL, safe="")
    encoded_sitemap = urllib.parse.quote(SITEMAP_URL, safe="")
    url = (
        "https://searchconsole.googleapis.com/webmasters/v3/sites/"
        f"{encoded_site}/sitemaps/{encoded_sitemap}"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    status, body = request_json(url, headers, method="PUT")
    if status not in (200, 204):
        return Report("GSC sitemap submitted", False, f"API HTTP {status}: {body}")
    verify_status, verify_body = request_json(url, headers)
    if verify_status == 200:
        return Report("GSC sitemap submitted", True, "API accepted and returned the sitemap")
    return Report("GSC sitemap submitted", False, f"Submission accepted, verification HTTP {verify_status}: {verify_body}")


def submit_bwt(api_key: str) -> Report:
    query = urllib.parse.urlencode({"apikey": api_key, "siteUrl": SITE_URL, "feedUrl": SITEMAP_URL})
    submit_url = f"https://ssl.bing.com/webmaster/api.svc/json/SubmitSitemap?{query}"
    status, body = request_json(submit_url)
    if status != 200 or (isinstance(body, dict) and body.get("ErrorCode")):
        return Report("BWT sitemap submitted", False, f"API HTTP {status}: {body}")
    verify_query = urllib.parse.urlencode({"apikey": api_key, "siteUrl": SITE_URL})
    verify_url = f"https://ssl.bing.com/webmaster/api.svc/json/GetSitemaps?{verify_query}"
    verify_status, verify_body = request_json(verify_url)
    verified = verify_status == 200 and SITEMAP_URL.lower() in json.dumps(verify_body).lower()
    if verified:
        return Report("BWT sitemap submitted", True, "API accepted and listed the sitemap")
    return Report("BWT sitemap submitted", False, f"Submission accepted, but verification failed: HTTP {verify_status}: {verify_body}")


def browser_assist() -> None:
    """Open the manual pages, optionally pre-filling login forms in a headed browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠️ Browser assist unavailable: install Playwright separately; opening manual pages.")
        for url in (WP_GENERAL_URL, WP_PRIVACY_URL, GSC_SITEMAP_URL, BWT_SITEMAP_URL):
            webbrowser.open(url)
        return

    google_email = os.getenv("GOOGLE_EMAIL", os.getenv("SEARCH_CONSOLE_EMAIL", ""))
    google_password = os.getenv("GOOGLE_PASSWORD", os.getenv("SEARCH_CONSOLE_PASSWORD", ""))
    bing_email = os.getenv("MICROSOFT_EMAIL", google_email)
    bing_password = os.getenv("MICROSOFT_PASSWORD", google_password)
    if not google_email or not google_password or not bing_email or not bing_password:
        print("⚠️ Browser assist needs Google and Microsoft credentials; opening manual pages.")
        for url in (WP_GENERAL_URL, WP_PRIVACY_URL, GSC_SITEMAP_URL, BWT_SITEMAP_URL):
            webbrowser.open(url)
        return

    print("Opening a visible browser. Google/Microsoft may still require 2FA or CAPTCHA.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        for url, email, password in (
            (GSC_SITEMAP_URL, google_email, google_password),
            (BWT_SITEMAP_URL, bing_email, bing_password),
        ):
            page.goto(url)
            page.wait_for_timeout(1500)
            for selector in ('input[type="email"]', 'input[name="identifier"]', 'input[name="loginfmt"]'):
                if page.locator(selector).count():
                    page.locator(selector).first.fill(email)
                    page.keyboard.press("Enter")
                    break
            page.wait_for_timeout(1500)
            for selector in ('input[type="password"]', 'input[name="Passwd"]', 'input[name="passwd"]'):
                if page.locator(selector).count():
                    page.locator(selector).first.fill(password)
                    page.keyboard.press("Enter")
                    break
            page.wait_for_timeout(1500)
        print("Finish any 2FA/CAPTCHA and submit each sitemap manually in the open browser.")
        input("Press Enter here after both webmaster dashboards are complete...")
        browser.close()


def print_report(reports: list[Report]) -> None:
    for report in reports:
        if report.ok:
            print(f"✅ {report.label}")
        else:
            detail = f" ({report.detail})" if report.detail else ""
            print(f"⚠️ Manual step required: {report.label}{detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual-only", action="store_true", help="Print the complete click-through checklist and exit.")
    parser.add_argument("--browser", action="store_true", help="Open a headed browser; credentials come only from SEARCH_CONSOLE_EMAIL/PASSWORD.")
    args = parser.parse_args()

    if args.manual_only:
        print_checklist()
        return 0

    print_checklist()
    if args.browser:
        browser_assist()

    reports = verify_public_files()
    gsc_token = os.getenv("GSC_ACCESS_TOKEN", "").strip()
    bwt_key = os.getenv("BWT_API_KEY", "").strip()
    reports.append(submit_gsc(gsc_token) if gsc_token else Report("GSC sitemap submitted", False, "GSC_ACCESS_TOKEN not provided"))
    reports.append(submit_bwt(bwt_key) if bwt_key else Report("BWT sitemap submitted", False, "BWT_API_KEY not provided"))
    print()
    print_report(reports)
    return 0 if all(report.ok for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
