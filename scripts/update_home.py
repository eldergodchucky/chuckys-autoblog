"""Replace the demo Home page content with an international front page."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_pages import load_env, wp_request  # noqa: E402

HOME_PAGE_ID = 1338

CONTENT = """<h2 style="text-align:center;">Comprehensive international reporting, original analysis, and investigative coverage across global affairs, business, science, culture, and tech innovation</h2>
<p style="text-align:center; max-width:800px; margin:0 auto 24px;">ChuckysCarnage covers world news, diplomacy, macroeconomics, scientific breakthroughs, health research, climate solutions, culture, arts, and the latest in artificial intelligence and consumer technology. Every article is rigorously synthesized from verified international wires, cites original primary sources, and explains what the news actually means for the world.</p>

<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:20px; margin-top:24px;">

<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px;">
<h3 style="margin-top:0; color:#1e293b; border-bottom:2px solid #3b82f6; padding-bottom:6px;">🌍 Global Affairs</h3>
<ul style="padding-left:20px; margin-bottom:0;">
<li><a href="/category/world/"><strong>World News</strong></a> &mdash; Geopolitics & diplomacy</li>
<li><a href="/category/politics/"><strong>Politics</strong></a> &mdash; Elections & global governance</li>
<li><a href="/category/defense/"><strong>Defense &amp; Aerospace</strong></a> &mdash; Security & military</li>
<li><a href="/category/crime/"><strong>Crime &amp; Justice</strong></a> &mdash; Legal affairs & investigations</li>
</ul>
</div>

<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px;">
<h3 style="margin-top:0; color:#1e293b; border-bottom:2px solid #10b981; padding-bottom:6px;">📈 Business &amp; Economy</h3>
<ul style="padding-left:20px; margin-bottom:0;">
<li><a href="/category/business/"><strong>Business &amp; Markets</strong></a> &mdash; Global trade & finance</li>
<li><a href="/category/energy/"><strong>Clean Energy</strong></a> &mdash; Grid, renewables & nuclear</li>
<li><a href="/category/crypto/"><strong>Crypto &amp; Fintech</strong></a> &mdash; Digital assets & regulation</li>
</ul>
</div>

<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px;">
<h3 style="margin-top:0; color:#1e293b; border-bottom:2px solid #06b6d4; padding-bottom:6px;">🔬 Science &amp; Nature</h3>
<ul style="padding-left:20px; margin-bottom:0;">
<li><a href="/category/science/"><strong>Science</strong></a> &mdash; Lab breakthroughs & discoveries</li>
<li><a href="/category/health/"><strong>Health &amp; Medicine</strong></a> &mdash; Clinical research & care</li>
<li><a href="/category/space/"><strong>Space Exploration</strong></a> &mdash; NASA, ESA & astronomy</li>
<li><a href="/category/climate/"><strong>Climate &amp; Earth</strong></a> &mdash; Environment & weather</li>
</ul>
</div>

<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px;">
<h3 style="margin-top:0; color:#1e293b; border-bottom:2px solid #8b5cf6; padding-bottom:6px;">🎭 Culture &amp; Society</h3>
<ul style="padding-left:20px; margin-bottom:0;">
<li><a href="/category/culture/"><strong>Culture &amp; Arts</strong></a> &mdash; Architecture, design & cinema</li>
<li><a href="/category/sports/"><strong>International Sports</strong></a> &mdash; Global tournaments & F1</li>
<li><a href="/category/entertainment/"><strong>Entertainment</strong></a> &mdash; Media, film & streaming</li>
<li><a href="/category/history/"><strong>History &amp; Heritage</strong></a> &mdash; Archaeology & civilization</li>
</ul>
</div>

<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px;">
<h3 style="margin-top:0; color:#1e293b; border-bottom:2px solid #f59e0b; padding-bottom:6px;">💻 Tech &amp; Innovation</h3>
<ul style="padding-left:20px; margin-bottom:0;">
<li><a href="/category/ai/"><strong>Artificial Intelligence</strong></a> &mdash; Models, agents & LLMs</li>
<li><a href="/category/phones/"><strong>Phones &amp; Mobile</strong></a> &mdash; Hardware, cameras & foldables</li>
<li><a href="/category/apple/"><strong>Apple</strong></a> &mdash; iPhone, Mac & ecosystem</li>
<li><a href="/category/android/"><strong>Android</strong></a> &mdash; Pixel, Samsung & OS</li>
<li><a href="/category/gadgets/"><strong>Gadgets</strong></a> &mdash; Wearables & smart gear</li>
<li><a href="/category/software/"><strong>Software &amp; OS</strong></a> &mdash; Platforms & dev tools</li>
<li><a href="/category/security/"><strong>Cybersecurity</strong></a> &mdash; Hacks, privacy & threat intel</li>
<li><a href="/category/mobility/"><strong>Future Mobility</strong></a> &mdash; EVs, batteries & autonomous</li>
<li><a href="/category/gaming/"><strong>Gaming</strong></a> &mdash; Consoles, PC & studios</li>
</ul>
</div>

</div>

<p style="text-align:center; margin-top:32px;"><a class="wp-block-button__link" style="background:#2563eb; color:#ffffff; padding:12px 28px; border-radius:6px; text-decoration:none; font-weight:600;" href="/blog/">Read Latest Articles &rarr;</a></p>"""


def main() -> int:
    load_env()
    result = wp_request(
        f"pages/{HOME_PAGE_ID}",
        payload={"title": "Browse Topics & International Coverage", "content": CONTENT, "status": "publish"},
        method="POST",
    )
    print(f"updated home page: id={result.get('id')} link={result.get('link')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
