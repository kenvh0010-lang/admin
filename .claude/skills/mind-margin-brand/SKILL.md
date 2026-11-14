---
name: mind-margin-brand
description: Mind & Margin (@MindMargin-t4k) channel brand - colors, fonts, frame layout, voice and editorial rules for evidence-based Shorts, thumbnails, the docs/ site and bio page. Use whenever creating or editing a storyboard in content/, a thumbnail, a visual in yt_studio/visual_composer.py, site styling in yt_studio/site_builder.py, or any channel-facing copy.
---

# Mind & Margin Brand

Documentary-style English Shorts about real lawsuits, regulator orders and corporate blunders,
shown with real primary exhibits. The look is a dark newsroom: calm navy, one gold highlight,
evidence first. This is the channel's own identity. Do not mix in another company's brand.

## Source of truth

The palette lives in code. If a value here disagrees with code, code wins and this file
must be updated. `tests/test_studio.py` checks that the hex values below match.

- Video and thumbnails: `BrandTheme` in `yt_studio/config.py`
- Website and bio: CSS variables in `yt_studio/site_builder.py`
- Editorial rules: `CLAUDE.md` section 2

## Colors

| Token | Hex | Code name | Use |
|---|---|---|---|
| Obsidian Navy | `#0B1020` | `bg_primary`, `--bg` | Frame and page background |
| Slate Card | `#131C34` | `bg_card`, `--card` | Evidence card, caption box, panels |
| Subtle Grid | `#1C2744` | `grid_line` | Background grid, progress track |
| Card Border | `#233259` | `--border` | Site card borders |
| Compounding Gold | `#F5B942` | `accent_gold`, `--gold` | Numbers, highlight words, evidence frame, progress fill |
| Leverage Cyan | `#22D3EE` | `accent_cyan`, `--cyan` | Caption box outline, labels, links |
| Hook Red | `#F43F5E` | `accent_crimson` | HOOK and THE TRAP tags, thumbnail badge only |
| Crisp White | `#F8FAFC` | `text_primary`, `--text` | Headlines, captions |
| Muted Slate | `#94A3B8` | `text_muted`, `--muted` | Source lines, handle, meta text |

Rules:
- Gold is the only highlight. Use it for dollar amounts, counts and `highlight_words`, not whole sentences.
- Red is for warning tags only. Never use it for body text.
- Keep backgrounds navy. No white or light frames except the evidence screenshot itself.

## Typography

- Bold: `assets/fonts/Inter-Bold.ttf`. Regular: `assets/fonts/Inter-Regular.ttf`.
- Fallbacks come from `resolve_font_path` in `yt_studio/config.py`: Roboto Condensed, DejaVu Sans, Liberation Sans, Arial.
- Website uses the system stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`.
- Sizes on a 1080x1920 Short: tag 28, headline 56, caption 46, source 25 down to 17.

## Short frame layout (1080x1920)

Top to bottom:
1. Tag pill with chapter tag, plus `@MindMargin-t4k` on the right.
2. Headline, at most 3 lines, white.
3. Evidence card on Slate Card with a gold frame around the cropped exhibit.
4. `Source: ...` line in Muted Slate under the card.
5. Caption box at 68% height, cyan outline, centered words, gold for numbers and highlight words.
6. Gold progress bar at 93% height.

Keep text out of the bottom 7% because the YouTube Shorts UI covers it.

## Thumbnail (1280x720)

- Red badge top left with the category in capitals.
- Hook of 3 to 5 words in capitals. Last line is gold, others white.
- Right card with one big gold stat and the handle in cyan.

## Voice and copy

- Narration voice: `en_authoritative`, which is `en-US-ChristopherNeural` through edge-tts.
- Render with `--tts edge`. A render that reports `offline-preview` has no voice and must not be published.
- 65 to 105 words over 5 scenes, about 28 to 42 seconds.
- Documentary tone. Say "alleged", "the suit says" or "settled without admitting fault" for unproven claims.
- Never use these glyphs in content JSON: `✕ ✓ ▸ → — –`. Use `->`, hyphens, colons, commas or periods.
- Never use: unlock, delve, game-changer, tapestry, skyrocket, secretly, ruthlessly, vague "studies show", "Here is how" openers, or "..." cliffhangers.

## Evidence and sources

- Every scene with `visual_type: "evidence_image"` points to a real PNG in `assets/evidence/<topic>/`.
- Inspect each PNG for CAPTCHAs, bot pages and cookie banners before use.
- `evidence_crop` must stay inside the image bounds.
- Every scene has a `source`. Every storyboard has a top-level `sources` list with label and url.

## Monetization text

- Amazon tag: `mindandmarg06-20`.
- Keep this disclosure word for word: "As an Amazon Associate I earn from qualifying purchases."
- Do not make videos that disparage Amazon retail or Prime.

## Checklist before commit

```bash
python3 cli.py build-site --amazon-tag mindandmarg06-20
```

```bash
python3 -m unittest discover -s tests -v
```
