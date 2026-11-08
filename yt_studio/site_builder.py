"""Static Editorial Website + Sitemap + Affiliate Tag Synchronizer (`docs/`)."""

import html
import json
import shutil
from pathlib import Path
from typing import Optional

from .config import CONTENT_DIR, OUTPUT_DIR, PROJECT_ROOT

SITE_BASE_URL = "https://kenvh0010-lang.github.io/admin"

DISCLOSURE = (
    "Disclosure: As an Amazon Associate I earn from qualifying purchases. "
    "Mind & Margin participates in the Amazon Services LLC Associates Program, an affiliate advertising program "
    "designed to provide a means for sites to earn advertising fees by advertising and linking to Amazon.com and Audible.com."
)

CSS = """
:root { --bg:#0B1020; --card:#131C34; --border:#233259; --gold:#F5B942; --cyan:#22D3EE; --text:#F8FAFC; --muted:#94A3B8; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--text); line-height:1.7; }
a { color:var(--cyan); text-decoration:none; }
a:hover { text-decoration:underline; }
.wrap { max-width:940px; margin:0 auto; padding:0 20px; }
header { border-bottom:1px solid var(--border); background:#080c18; padding:18px 0; }
.nav { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:14px; }
.brand { font-size:1.25rem; font-weight:800; letter-spacing:0.03em; color:var(--text); }
.brand span { color:var(--gold); }
.nav-links { display:flex; gap:18px; font-size:0.92rem; }
.disclosure-bar { background:#101930; border-bottom:1px solid var(--border); font-size:0.82rem; color:var(--muted); padding:10px 0; }
.hero { padding:44px 0 28px; border-bottom:1px solid var(--border); }
.hero h1 { font-size:2.1rem; line-height:1.25; margin:0 0 12px; }
.hero p { color:var(--muted); max-width:720px; margin:0; font-size:1.05rem; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(285px,1fr)); gap:20px; padding:32px 0; }
.card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:22px; display:flex; flex-direction:column; justify-content:space-between; }
.badge { display:inline-block; font-size:0.75rem; font-weight:700; color:var(--gold); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:8px; }
.card h2 { font-size:1.15rem; line-height:1.35; margin:0 0 10px; }
.card p { font-size:0.92rem; color:var(--muted); margin:0 0 16px; }
.btn { display:inline-block; background:var(--gold); color:#0B1020; font-weight:700; padding:9px 16px; border-radius:8px; font-size:0.9rem; text-decoration:none !important; }
article { padding:36px 0; max-width:760px; }
article h1 { font-size:2rem; line-height:1.28; margin-bottom:12px; }
.scene-block { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px 24px; margin:20px 0; }
.scene-block h3 { margin:0 0 8px; color:var(--gold); font-size:1.1rem; }
.book-box { background:#162240; border-left:4px solid var(--gold); padding:18px 22px; border-radius:10px; margin:28px 0; }
footer { border-top:1px solid var(--border); padding:28px 0 44px; color:var(--muted); font-size:0.86rem; margin-top:40px; }
"""


DEFAULT_AMAZON_TAG = "mindandmarg06-20"


def build_public_site(amazon_tag: Optional[str] = DEFAULT_AMAZON_TAG) -> Path:
    """Rebuild docs/ static site, sync Bio + 5hr OS, and generate sitemap.xml & robots.txt."""
    docs = PROJECT_ROOT / "docs"
    articles_dir = docs / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    (docs / ".nojekyll").write_text("", encoding="utf-8")

    effective_tag = (amazon_tag if amazon_tag is not None else DEFAULT_AMAZON_TAG).strip()
    tag_query = f"?tag={effective_tag}" if effective_tag else ""
    audible_url = f"https://www.audible.com/ep/freetrial{tag_query}"
    amazon_books_url = f"https://www.amazon.com/b?node=283155{'&tag=' + effective_tag if effective_tag else ''}"

    # Sync products into docs/
    for sub_src, sub_dst in [
        (PROJECT_ROOT / "products/bio_funnel_page", docs / "bio"),
        (PROJECT_ROOT / "products/5_hour_asset_builder_os", docs / "5_hour_asset_builder_os"),
        (PROJECT_ROOT / "products/free_lead_magnet", docs / "free_lead_magnet"),
    ]:
        if sub_src.exists():
            if sub_dst.exists():
                shutil.rmtree(sub_dst)
            shutil.copytree(sub_src, sub_dst)

    if effective_tag:
        for bio_file in [PROJECT_ROOT / "products/bio_funnel_page/index.html", docs / "bio/index.html"]:
            if bio_file.is_file():
                btxt = bio_file.read_text(encoding="utf-8")
                import re
                btxt = re.sub(
                    r"https://www\.audible\.com/ep/freetrial(?:\?tag=[A-Za-z0-9_-]+)?",
                    audible_url,
                    btxt,
                )
                bio_file.write_text(btxt, encoding="utf-8")

        for seo_md in OUTPUT_DIR.glob("*/youtube_upload_pack.md"):
            mtxt = seo_md.read_text(encoding="utf-8")
            mtxt = mtxt.replace("https://yourlink.com/", f"{SITE_BASE_URL}/bio/?ref=")
            seo_md.write_text(mtxt, encoding="utf-8")

    storyboards = sorted(p for p in CONTENT_DIR.glob("*.json") if p.name != "published_ledger.json")
    cards_html = []
    sitemap_urls = [
        f"{SITE_BASE_URL}/",
        f"{SITE_BASE_URL}/bio/",
        f"{SITE_BASE_URL}/5_hour_asset_builder_os/",
        f"{SITE_BASE_URL}/about.html",
        f"{SITE_BASE_URL}/privacy.html",
    ]

    for idx, sb in enumerate(storyboards, start=1):
        d = json.loads(sb.read_text(encoding="utf-8"))
        slug = sb.stem
        title = html.escape(d["title"])
        desc = html.escape(d.get("description_hook", ""))
        is_long = d.get("format") == "long"
        fmt_key = "long" if is_long else "short"
        fmt_label = "Long-Form Visual Essay" if is_long else "Mental Model Breakdown"
        tags_str = ", ".join(html.escape(t) for t in d.get("tags", []))

        sections = []
        for s in d["scenes"]:
            sh = html.escape(s.get("headline", s.get("tag", "Key Insight")))
            nar = html.escape(s.get("narration", ""))
            bullets = s.get("bullets", [])
            b_html = "<ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in bullets) + "</ul>" if bullets else ""
            src = s.get("source")
            src_html = (
                f'<p style="font-size:0.82rem;color:var(--muted);margin:10px 0 0;"><em>Source: {html.escape(str(src))}</em></p>'
                if src else ""
            )
            sections.append(f'<div class="scene-block"><h3>{sh}</h3><p>{nar}</p>{b_html}{src_html}</div>')

        aff_name = html.escape(d.get("affiliate_cta", {}).get("offer_name", "Recommended Reading on Amazon & Audible"))
        art_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{desc}" />
  <title>{title} — Mind &amp; Margin</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="disclosure-bar"><div class="wrap">{DISCLOSURE}</div></div>
  <header>
    <div class="wrap nav">
      <a class="brand" href="../index.html">MIND <span>&amp;</span> MARGIN</a>
      <nav class="nav-links">
        <a href="../index.html">Essays &amp; Book Guides</a>
        <a href="../bio/index.html">Resources Hub</a>
        <a href="../about.html">About</a>
        <a href="../privacy.html">Privacy &amp; Disclosure</a>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <article>
      <span class="badge">{fmt_label} • Guide #{idx:02d}</span>
      <h1>{title}</h1>
      <p style="color:var(--muted);font-size:1.06rem;">{desc}</p>
      {"".join(sections)}
      <div class="book-box">
        <strong>Recommended Reading &amp; Companion Resource:</strong>
        <p style="margin:8px 0 14px;color:var(--muted);">{aff_name}. Check current edition availability directly on Amazon or explore Audible audiobook options.</p>
        <a class="btn" href="{amazon_books_url}" rel="nofollow sponsored" target="_blank">Check Availability on Amazon</a>
        <a class="btn" style="margin-left:10px;background:var(--cyan);" href="{audible_url}" rel="nofollow sponsored" target="_blank">Listen Free on Audible</a>
      </div>
      <p style="font-size:0.85rem;color:var(--muted);">Topics: {tags_str}</p>
    </article>
  </main>
  <footer>
    <div class="wrap">
      <p>{DISCLOSURE}</p>
      <p>&copy; 2026 Mind &amp; Margin Editorial. Educational analysis only — not personalized financial or legal advice. | <a href="../privacy.html">Privacy Policy</a> | <a href="../about.html">About &amp; Contact</a></p>
    </div>
  </footer>
</body>
</html>"""
        (articles_dir / f"{slug}.html").write_text(art_html, encoding="utf-8")
        sitemap_urls.append(f"{SITE_BASE_URL}/articles/{slug}.html")
        cards_html.append(f"""
    <div class="card" data-fmt="{fmt_key}" data-search="{title.lower()} {tags_str.lower()}">
      <div>
        <span class="badge">{fmt_label}</span>
        <h2><a href="articles/{slug}.html" style="color:var(--text);">{title}</a></h2>
        <p>{desc}</p>
      </div>
      <div><a class="btn" href="articles/{slug}.html">Read Full Breakdown &rarr;</a></div>
    </div>""")

    total_count = len(storyboards)
    long_count = sum(1 for p in storyboards if p.stem.startswith("long_"))
    short_count = total_count - long_count

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="Original visual essays, behavioral finance breakdowns, and curated non-fiction book guides by Mind & Margin." />
  <title>Mind &amp; Margin — Wealth Psychology, Book Summaries &amp; AI Leverage ({total_count} Guides)</title>
  <style>{CSS}
  .toolbar {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; justify-content:space-between; margin-top:22px; }}
  .tabs {{ display:flex; flex-wrap:wrap; gap:8px; }}
  .tab-btn {{ background:#131C34; color:var(--text); border:1px solid var(--border); border-radius:8px; padding:7px 14px; cursor:pointer; font-size:0.86rem; font-weight:600; }}
  .tab-btn.active {{ background:var(--gold); color:#0B1020; border-color:var(--gold); }}
  .search-input {{ background:#131C34; color:var(--text); border:1px solid var(--border); border-radius:8px; padding:8px 14px; min-width:240px; font-size:0.9rem; }}
  </style>
</head>
<body>
  <div class="disclosure-bar"><div class="wrap">{DISCLOSURE}</div></div>
  <header>
    <div class="wrap nav">
      <a class="brand" href="index.html">MIND <span>&amp;</span> MARGIN</a>
      <nav class="nav-links">
        <a href="index.html">Essays &amp; Book Guides ({total_count})</a>
        <a href="bio/index.html">Creator Resource Hub</a>
        <a href="5_hour_asset_builder_os/index.html">5-Hour Asset OS</a>
        <a href="about.html">About</a>
        <a href="privacy.html">Privacy Policy</a>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <section class="hero">
      <span class="badge">Editorial Publication &amp; Book Breakdowns • {total_count} Original Guides</span>
      <h1>Wealth Psychology, Timeless Mental Models &amp; Modern Leverage</h1>
      <p>Original visual essays, behavioral finance breakdowns, and curated non-fiction reading guides accompanying the Mind &amp; Margin YouTube channel.</p>
      <div class="toolbar">
        <div class="tabs">
          <button class="tab-btn active" onclick="filterCards('all', this)">All Guides ({total_count})</button>
          <button class="tab-btn" onclick="filterCards('long', this)">Long-Form Essays ({long_count})</button>
          <button class="tab-btn" onclick="filterCards('short', this)">Mental Model Breakdowns ({short_count})</button>
        </div>
        <input id="qInput" class="search-input" type="search" placeholder="Search mental models, books, AI..." oninput="applySearch()" />
      </div>
    </section>
    <section class="grid" id="articlesGrid">
      {"".join(cards_html)}
    </section>
  </main>
  <footer>
    <div class="wrap">
      <p>{DISCLOSURE}</p>
      <p>&copy; 2026 Mind &amp; Margin Editorial. All rights reserved. | <a href="privacy.html">Privacy Policy &amp; Terms</a> | <a href="about.html">About &amp; Contact</a></p>
    </div>
  </footer>
  <script>
    let activeFmt = 'all';
    function filterCards(fmt, btn) {{
      activeFmt = fmt;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applySearch();
    }}
    function applySearch() {{
      const q = (document.getElementById('qInput').value || '').toLowerCase().trim();
      document.querySelectorAll('#articlesGrid .card').forEach(c => {{
        const fmtOk = activeFmt === 'all' || c.dataset.fmt === activeFmt;
        const qOk = !q || (c.dataset.search || '').includes(q);
        c.style.display = (fmtOk && qOk) ? 'flex' : 'none';
      }});
    }}
  </script>
</body>
</html>"""
    (docs / "index.html").write_text(index_html, encoding="utf-8")

    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"  <url><loc>{u}</loc></url>" for u in sitemap_urls)
        + "\n</urlset>\n"
    )
    (docs / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    (docs / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n", encoding="utf-8")
    return docs
