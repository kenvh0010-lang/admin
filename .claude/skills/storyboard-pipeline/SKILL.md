---
name: storyboard-pipeline
description: Quarantine-first 5-stage storyboard processing pipeline (draft-case -> 7-gate validate -> promote) for Mind & Margin evidence-based Shorts. Use whenever drafting a new case script, validating storyboards in content/ or content/drafts/, promoting a draft into the daily YouTube Autopilot queue, or checking deduplication and exhibit gates.
---

# Mind & Margin — Storyboard Processing Pipeline (`Luồng Xử Lý Kịch Bản Mới`)

Never write raw or unverified scripts directly into `content/short_*.json` because the 20:00 VN daily GitHub Actions YouTube Autopilot (`cli.py publish-next`) automatically picks up `content/*.json` (`discover_storyboards()` explicitly ignores `content/drafts/`).

Every new case study MUST pass through this 5-stage pipeline:

## Stage 1 — Capture & Visually Verify Primary Exhibits (`assets/evidence/<topic>/`)
1. Download or screenshot (`1200x1400` or `150 DPI` `pdftoppm`) the official court filing (SDNY, N.D. Cal.), agency order (FTC, SEC, CFPB, DOJ), or research table into `assets/evidence/<topic>/*.png`.
2. Visually inspect **every** PNG to verify:
   - Zero CAPTCHAs, bot error screens, or cookie banners covering text.
   - Crisp legibility of exact dollar amounts, case numbers, and paragraphs.

## Stage 2 — Scaffold Quarantined Draft (`content/drafts/`)
Run `draft-case` (or `script`), which automatically quarantines files inside `content/drafts/` and computes safe starter pixel crops from your real PNG dimensions:

```bash
python3 cli.py draft-case \
  --slug ftc_case_slug \
  --topic "How a Fintech App Triggered a $50M Federal Refund Order" \
  --evidence-dir assets/evidence/ftc_case_slug \
  --source "FTC Federal Complaint PDF|https://www.ftc.gov/..." \
  --source "FTC Enforcement Order|https://www.ftc.gov/..."
```

Fill in the 5-scene News-Short structure following `mind-margin-brand`:
- **Scenes 1-4**: `"visual_type": "evidence_image"` (omit `"bullets"` so the exhibit fills the frame cleanly) + `"evidence_crop": [x1, y1, x2, y2]`.
- **Scene 5 (`THE RULE`)**: `"visual_type": "comparison_split"` (`left_title`, `left_body`, `right_title`, `right_body`).
- **Narration**: `75-110` words total (`~32-44s`), documentary attribution (`"The FTC alleges..."`, `"settled without admitting fault"`), zero forbidden glyphs (`✕ ✓ ▸ → — –`), zero `<` or `>`, zero AI buzzwords.

## Stage 3 — Run the 7-Gate Validator (`cli.py validate`)
Validate your quarantined draft (or the entire active queue):

```bash
python3 cli.py validate content/drafts/ftc_case_slug.json
python3 cli.py validate content/
```

`yt_studio/storyboard_validator.py` enforces all 7 gates:
1. **Gate 1 (Schema & Format Purity)**: Required keys, `format == "short"`, valid neural voice preset, `>= 4` scenes.
2. **Gate 2 (Primary Exhibits & Pixel Bounds)**: `>= 3` `evidence_image` scenes, PNG exists on disk, `0 <= x1 < x2 <= width` and `0 <= y1 < y2 <= height`, minimum readable crop size.
3. **Gate 3 (Primary Citations)**: `>= 2` real `https://` URLs in `sources`, specific primary document cited in every scene `source` (no placeholders).
4. **Gate 4 (`mind-margin-brand` Copy & Glyphs)**: Zero forbidden glyphs, zero `<`/`>` in YouTube titles/descriptions, zero banned AI buzzwords (`unlock`, `delve`, `secretly`, `skyrocket`, etc.), no `"Here is how"` openers or `"..."` cliffhangers.
5. **Gate 5 (Pacing & Frame Fit)**: Total narration within `55-130` words (warns outside `65-115`), headlines wrap `<= 3` lines, `Source:` line fits `1080px` width without clipping.
6. **Gate 6 (Monetization & Amazon Policy)**: `affiliate_cta.url_placeholder` points to `/bio/`, verbatim Amazon Associate disclosure present, zero Amazon/Prime disparagement.
7. **Gate 7 (Multi-Layer Deduplication)**: Zero collision on stem, normalized title/alt-titles, canonical source URLs, exact crop boxes, or topic Jaccard similarity (`< 0.30`) against both active `content/` and `content/published_ledger.json`.

## Stage 4 — Promote Atomically to Active Queue (`cli.py promote`)
Once `validate` reports `PASS` with `0` errors, promote the draft into `content/short_NN_<slug>.json`:

```bash
python3 cli.py promote content/drafts/ftc_case_slug.json
# Or also render neural-voiced MP4 immediately (auto-uses RTX h264_nvenc when available):
python3 cli.py promote content/drafts/ftc_case_slug.json --render --tts edge --encoder auto
```

`promote` atomically:
- Re-runs all 7 validation gates.
- Assigns the next sequential `short_NN_` prefix and moves the JSON from `content/drafts/` -> `content/`.
- Generates `output/<slug>/<slug>.srt`, `<slug>_thumbnail.png`, and `youtube_upload_pack.md` (plus `.mp4` if `--render`).
- Runs `dedupe --apply` and rebuilds `docs/` + `sitemap.xml` (`mindandmarg06-20`).

## Stage 5 — Final Pre-Commit QA
```bash
python3 cli.py validate content/
python3 -m unittest discover -s tests -v
```
