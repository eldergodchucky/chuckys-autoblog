"""Replace the demo Home page content with a real front page."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_pages import load_env, wp_request  # noqa: E402

HOME_PAGE_ID = 1338

CONTENT = """<h2 style="text-align:center;">Big news, sharp analysis, and original reporting across tech, politics, culture, and the world</h2>
<p>ChuckysCarnage covers science, space, AI, gaming, future mobility, crypto, clean energy, defense, phones, gadgets, software, security, health research, politics, global affairs, culture, and entertainment. Every article is written from the day's reporting, links back to the original sources, and explains what the news actually means.</p>
<h3>Browse by topic</h3>
<ul>
<li><a href="/category/science/">Science</a></li>
<li><a href="/category/space/">Space</a></li>
<li><a href="/category/ai/">AI</a></li>
<li><a href="/category/gaming/">Gaming</a></li>
<li><a href="/category/mobility/">Mobility & EVs</a></li>
<li><a href="/category/crypto/">Crypto & Fintech</a></li>
<li><a href="/category/energy/">Clean Energy</a></li>
<li><a href="/category/defense/">Defense & Aerospace</a></li>
<li><a href="/category/politics/">Politics</a></li>
<li><a href="/category/world/">World</a></li>
<li><a href="/category/business/">Business</a></li>
<li><a href="/category/sports/">Sports</a></li>
<li><a href="/category/climate/">Climate</a></li>
<li><a href="/category/crime/">Crime & Justice</a></li>
<li><a href="/category/entertainment/">Entertainment</a></li>
<li><a href="/category/celebrities/">Celebrities</a></li>
<li><a href="/category/history/">History</a></li>
<li><a href="/category/phones/">Phones</a></li>
<li><a href="/category/apple/">Apple</a></li>
<li><a href="/category/android/">Android</a></li>
<li><a href="/category/gadgets/">Gadgets</a></li>
<li><a href="/category/health/">Health</a></li>
<li><a href="/category/software/">Software</a></li>
<li><a href="/category/security/">Security</a></li>
</ul>
<p><a href="/blog/">Read the latest posts</a> or check the <a href="/about/">About</a> page to see how articles are made.</p>
<p style="text-align:center;"><a class="wp-block-button__link" href="/blog/">View latest posts</a></p>"""


def main() -> int:
    load_env()
    result = wp_request(
        f"pages/{HOME_PAGE_ID}",
        payload={"title": "Home", "content": CONTENT, "status": "publish"},
        method="POST",
    )
    print(f"updated home page: id={result.get('id')} link={result.get('link')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
