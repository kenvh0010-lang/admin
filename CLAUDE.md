# CLAUDE.md — Mind & Margin (`@MindAndMargin`) Automated YouTube Studio SOP

This file defines the unified engineering, editorial, and QA workflow for **Claude Code** and **Antigravity** working together on the **Mind & Margin** high-RPM faceless YouTube ecosystem.

---

## 1. Project Overview & Live Architecture
- **Channel**: `Mind & Margin` (`@MindAndMargin`) — English behavioral economics, decision science, non-fiction book breakdowns, and solo AI leverage (`$15–$48` CPM).
- **Content Vault (`content/`)**: **96 complete storyboards** (Half-Year / 24 Weeks / 180 Days: `short_01`..`short_72` + `long_01`..`long_24`) mapped across **7 high-RPM trend clusters** in `yt_studio/trend_radar.py`.
- **Official Amazon Associates Tag**: **`mindandmarg06-20`** (wired as `DEFAULT_AMAZON_TAG` in `yt_studio/site_builder.py` and `.github/workflows/video_factory.yml`).
- **Live Public Website (96 SEO Articles)**: https://kenvh0010-lang.github.io/admin/
- **Day-1 Bio Funnel**: https://kenvh0010-lang.github.io/admin/bio/
- **Cloud Neural Video Releases (24 Weekly `.zip` Packs)**: https://github.com/kenvh0010-lang/admin/releases

---

## 2. Mandatory Editorial & Fact-Checking Rules (For All Storyboards in `content/*.json`)
1. **Every Claim & Number Needs a Real Source**:
   - Every factual or statistical scene MUST include an accurate `"source"` field citing the real paper, author, and year (e.g., `"Kahneman & Tversky, Econometrica (1979)"`, `"Gloria Mark et al., CHI (2008)"`).
   - Actionable frameworks invented by the channel must be labeled transparently (e.g., `"Mind & Margin system / rule of thumb (advice, not a study)"`).
   - Never invent statistics or misattribute quotes (e.g., 23-min task resumption = Gloria Mark 2008, Attention Residue = Sophie Leroy 2009; Goodhart target phrasing = Marilyn Strathern 1997).
2. **Zero AI-Writing Tells & Zero Forbidden Glyphs**:
   - **NEVER** use forbidden glyphs (`✕`, `✓`, `▸`, `→`, or `—` em-dash) anywhere in JSON — use ASCII `->`, colons, commas, or periods so Linux/DejaVu/Roboto fonts render cleanly without tofu boxes.
   - **NEVER** use AI buzzwords (`unlock`, `delve`, `game-changer`, `tapestry` outside Diderot's literal 1769 essay, `skyrocket`, `secretly`, `ruthlessly`, vague `"studies show"`), `"Here is how/the"` openers, or `"..."` cliffhanger endings.
3. **Visual Card & Thumbnail Bounds**:
   - Keep `"stat_value"` concise (`<= 12` characters recommended; `yt_studio/visual_composer.py` auto-scales fonts down to `64px` and wraps `Source:` to 2 lines, but punchy values look sharpest on `1080x1920` Shorts).
   - Keep `thumbnail.hook_text <= 20` chars, `thumbnail.badge <= 18` chars, and `thumbnail.stat <= 8` chars.
4. **Amazon Operating Agreement Compliance**:
   - Every public page, bio funnel, YouTube upload pack (`output/*/youtube_upload_pack.md`), and API upload (`yt_studio/youtube_uploader.py`) MUST retain the verbatim disclosure:
     `"As an Amazon Associate I earn from qualifying purchases."`

---

## 3. Mandatory Sync & QA Checklist Before Every Commit
Whenever you add or edit any storyboard JSON (`content/*.json`), title, or renderer code, **always run all 4 steps before committing** so downstream files never go stale:

1. **Sync Calendars (`content/calendar_30_days.csv`, `calendar_90_days.csv`, `calendar_180_days.csv`)**:
   - Always write CSVs via Python `csv.writer` (proper RFC-4180 quoting for commas like `"$1,000/Month"`) and keep `Video Title (English - High RPM)` 100% identical to `storyboard["title"]`.
2. **Regenerate Upload Packs, SRTs, Thumbnails & Public Site (`docs/`)**:
   ```bash
   python3 cli.py build-site --amazon-tag mindandmarg06-20
   ```
   *(And regenerate `output/<slug>/youtube_upload_pack.md`, `<slug>.srt`, and `<slug>_thumbnail.png` for any edited storyboards).*
3. **Keep Cloud Encoding Fast & Safe**:
   - In `yt_studio/video_renderer.py` (`_render_motion_clip`), keep `-preset veryfast` so 96-video GitHub Actions batch builds finish well inside runner limits.
   - Do NOT commit `.mp4` files or `release_bundles/` to Git (they belong on GitHub Releases via `.github/workflows/video_factory.yml`).
4. **Run the Full Automated QA Suite (Must Pass 100%)**:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
   This verifies all 96 JSON schemas, research `source` presence, zero forbidden glyphs, zero PIL `textbbox` card/source clipping across all 96 scripts, 7 Trend Radar clusters, Amazon tag sync, and 100% calendar title matching.
