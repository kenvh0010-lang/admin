# CLAUDE.md — Mind & Margin (`@MindAndMargin`) Automated YouTube Studio SOP

This file defines the unified engineering, editorial, and QA workflow for **Claude Code** and **Antigravity** working together on the **Mind & Margin** high-RPM faceless YouTube ecosystem.

---

## 1. Project Overview & Live Architecture (Evidence-Based Shorts Pivot — Nov 2026)
- **Channel**: `Mind & Margin` (`@MindAndMargin`) — Documentary-style English Shorts (`1080x1920`) breaking down real lawsuits, federal regulatory actions, corporate blunders, and AI copyright collisions with **real primary screenshots & court exhibits** (`$15–$48` CPM).
- **Content Vault (`content/`)**: Active evidence-based news & case-study Shorts (`short_00_suno_ai_lawsuit.json`, `short_01_ftc_cleo_ai_refunds.json`, `short_02_anthropic_1_5b_book_settlement.json`, `short_03_citibank_900m_wire_blunder.json`, `short_04_knight_capital_440m_sec_order.json`, ...) backed by primary screenshots in `assets/evidence/<topic>/*.png` and the **48-Event Primary Research Dossier** in `products/real_world_events_dossier.md`.
  - *Note*: The legacy 112 generic-card library and fixed CSV calendars were retired in commit `bbf6416` (`08/11/2026`). Do **not** restore generic stat-only scripts without real primary exhibits.
- **Official Amazon Associates Tag**: **`mindandmarg06-20`** (`DEFAULT_AMAZON_TAG` in `yt_studio/site_builder.py`).
- **Live Public Website + Exhibits + 48-Event Dossier**: https://kenvh0010-lang.github.io/admin/ (`dossier.html` for full research vault)
- **Day-1 Bio Funnel**: https://kenvh0010-lang.github.io/admin/bio/
- **Cloud Neural Video Releases**: https://github.com/kenvh0010-lang/admin/releases (`evidence-shorts-vault`)

---

## 2. Mandatory Editorial, Screenshot & Fact-Checking Rules (`content/*.json`)
1. **Real Primary Screenshots (`visual_type: "evidence_image"`)**:
   - Capture real browser screenshots (`1200x1400`) or `150 DPI` `pdftoppm` renders of official court complaints, SEC/FTC orders, or reputable news reporting into `assets/evidence/<topic>/<name>.png`.
   - Visually inspect **every** PNG to confirm zero CAPTCHAs, zero anti-bot error pages, and zero cookie/disclaimer modals blocking text.
   - Set `"evidence_crop": [x1, y1, x2, y2]` inside image bounds (`0 <= x1 < x2 <= width`, `0 <= y1 < y2 <= height`) to frame the exact headline, paragraph, or exhibit table cleanly.
2. **Primary Citations & Top-Level `sources` Array**:
   - Every scene MUST include a concise `"source"` citation (e.g., `"SEC Release No. 34-70694, para. 1, p. 2"`).
   - Every storyboard MUST include a top-level `"sources": [{"label": "...", "url": "https://..."}]` list so `yt_studio/video_renderer.py`, `yt_studio/youtube_uploader.py`, and `yt_studio/site_builder.py` automatically embed clickable source links in YouTube descriptions and web articles.
   - Distinguish unproven lawsuit allegations (`"alleged"`, `"the suit says"`, `"settled without admitting fault"`) from final court findings.
3. **Zero AI-Writing Tells & Zero Forbidden Glyphs**:
   - **NEVER** use forbidden glyphs (`✕`, `✓`, `▸`, `→`, `—`, or `–`) anywhere in JSON — use ASCII `->`, hyphens `-`, colons, commas, or periods.
   - **NEVER** use AI buzzwords (`unlock`, `delve`, `game-changer`, `tapestry`, `skyrocket`, `secretly`, `ruthlessly`, vague `"studies show"`), `"Here is how"` openers, or `"..."` cliffhangers.
   - Keep narration tight and documentary-crisp (`~65–105` words across 5 scenes = `~28–42s` high-retention Short).
4. **Amazon Operating Agreement Compliance**:
   - Retain the verbatim disclosure `"As an Amazon Associate I earn from qualifying purchases."` across `docs/`, `bio/`, `youtube_upload_pack.md`, and `yt_studio/youtube_uploader.py` (`mindandmarg06-20`). Avoid making videos that disparage Amazon retail/Prime while participating in Amazon Associates.

---

## 3. Mandatory Sync & QA Checklist Before Every Commit
1. **Rebuild Public Site, Exhibits, Dossier & Upload Packs**:
   ```bash
   python3 cli.py build-site --amazon-tag mindandmarg06-20
   ```
2. **Incremental Render / Smoke Test**:
   - Use `--skip-existing` (`python3 cli.py batch content/ --tts edge --voice en_authoritative --workers 4 --skip-existing`) so unchanged videos reuse `.render_manifest.json` SHA-256 signatures.
   - Never commit `.mp4`, `.render_manifest.json`, or `release_bundles/` to Git.
3. **Run the Full Automated QA Suite (Must Pass 100%)**:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
