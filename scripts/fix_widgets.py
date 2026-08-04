"""Fix sidebar/footer widgets: subscribe widget, footer legal links."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_pages import load_env, wp_request  # noqa: E402


def main() -> int:
    load_env()

    subscribe_content = (
        '<p><strong>Follow the publication</strong></p>'
        '<p><a href="/feed/">RSS feed</a> &middot; '
        '<a href="/contact/">Contact</a> &middot; '
        '<a href="/about/">About</a></p>'
    )
    try:
        result = wp_request(
            "widgets/block-66",
            payload={"instance": {"raw": {"content": subscribe_content}}},
            method="POST",
        )
        print(f"updated subscribe widget block-66: sidebar={result.get('sidebar')}")
    except Exception as exc:
        print(f"block-66 error: {exc}")

    legal_content = (
        '<p><strong>Legal</strong></p>'
        '<p><a href="/privacy/">Privacy Policy</a><br>'
        '<a href="/cookie-policy/">Cookie Policy</a><br>'
        '<a href="/editorial-policy/">Editorial Policy</a><br>'
        '<a href="/ai-policy/">AI Usage Policy</a><br>'
        '<a href="/affiliate-disclosure/">Affiliate Disclosure</a><br>'
        '<a href="/disclaimer/">Disclaimer</a><br>'
        '<a href="/copyright/">Copyright</a></p>'
    )
    try:
        result = wp_request(
            "widgets",
            payload={
                "id_base": "block",
                "sidebar": "sidebar-2",
                "instance": {"raw": {"content": legal_content}},
            },
            method="POST",
        )
        print(f"created legal widget: id={result.get('id')} sidebar={result.get('sidebar')}")
    except Exception as exc:
        print(f"legal widget error: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
