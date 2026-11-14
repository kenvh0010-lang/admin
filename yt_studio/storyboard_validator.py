"""7-Gate Storyboard Pipeline Validator & Atomic Draft Promoter (`content/drafts/ -> content/`)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

from PIL import Image, ImageDraw

from .config import CONTENT_DIR, OUTPUT_DIR, PROJECT_ROOT, VOICE_PRESETS, discover_storyboards
from .deduper import (
    STOPWORDS,
    audit_and_dedupe_projects,
    normalize_source_url,
    normalize_title,
)
from .site_builder import DEFAULT_AMAZON_TAG, SITE_BASE_URL, build_public_site
from .subtitle_maker import build_scene_beats, export_srt
from .tts_engine import estimate_speech_duration
from .video_renderer import _write_seo_upload_pack, render_project
from .visual_composer import _load_font, _wrap_text, render_thumbnail
from .youtube_uploader import build_youtube_description, load_ledger

FORBIDDEN_GLYPHS: Set[str] = {"✕", "✓", "▸", "→", "—", "–"}
BANNED_AI_PHRASES: Tuple[str, ...] = (
    "unlock",
    "delve",
    "game-changer",
    "game changer",
    "tapestry",
    "skyrocket",
    "secretly",
    "ruthlessly",
    "studies show",
    "testament",
    "underscore",
    "underscores",
    "pivotal",
    "beacon",
    "symphony",
    "realm",
    "multifaceted",
    "intricate",
    "meticulous",
    "meticulously",
    "seamless",
    "seamlessly",
    "groundbreaking",
    "unleash",
    "supercharge",
    "in conclusion",
    "dive into",
)
PLACEHOLDER_DOMAINS: Tuple[str, ...] = (
    "example.com",
    "yourdomain.com",
    "yourlink.com",
    "localhost",
)
AMAZON_DISPARAGEMENT_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\bamazon\s+(?:scam|fraud|trap|rip[- ]?off|deceptive|lawsuit|sued)\b", re.I),
    re.compile(r"\bprime\s+(?:scam|trap|dark\s+pattern|cancel(?:lation)?\s+trap)\b", re.I),
)


def _topic_word_set(data: Dict[str, Any]) -> Set[str]:
    blob = " ".join(
        [str(data.get("title", "")), str(data.get("description_hook", ""))]
        + [str(sc.get("narration", "")) for sc in data.get("scenes", [])]
    ).lower()
    return set(re.findall(r"[a-z0-9]{4,}", blob)) - STOPWORDS


def next_short_slug_prefix(content_dir: Path = CONTENT_DIR) -> str:
    """Return the next sequential short_NN prefix based on active storyboards in content_dir."""
    max_num = -1
    for sb in discover_storyboards(content_dir):
        m = re.match(r"^short_(\d+)_", sb.stem)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"short_{max_num + 1:02d}"


def validate_storyboard(
    storyboard_path: Path,
    content_dir: Path = CONTENT_DIR,
    project_root: Path = PROJECT_ROOT,
    check_dedupe: bool = True,
    similarity_threshold: float = 0.30,
) -> Dict[str, Any]:
    """Validate a single storyboard JSON against all 7 Mind & Margin brand, exhibit, legal, and dedupe gates."""
    sb_path = Path(storyboard_path).resolve()
    errors: List[str] = []
    warnings: List[str] = []

    if not sb_path.is_file():
        return {
            "ok": False,
            "path": str(sb_path),
            "slug": sb_path.stem,
            "word_count": 0,
            "estimated_duration_sec": 0.0,
            "errors": [f"Storyboard file not found: {sb_path}"],
            "warnings": [],
        }

    try:
        data = json.loads(sb_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "path": str(sb_path),
            "slug": sb_path.stem,
            "word_count": 0,
            "estimated_duration_sec": 0.0,
            "errors": [f"Invalid JSON syntax: {exc}"],
            "warnings": [],
        }

    # Gate 1: Schema & Format Purity
    required_keys = {"title", "format", "scenes", "tags", "thumbnail", "affiliate_cta", "sources"}
    missing = sorted(required_keys - set(data.keys()))
    if missing:
        errors.append(f"[Gate 1: Schema] Missing required top-level keys: {missing}")

    fmt = str(data.get("format", "")).lower()
    if fmt != "short":
        errors.append(f"[Gate 1: Format] Active channel queue requires format='short', got {fmt!r}")

    voice = str(data.get("voice", "en_authoritative"))
    if voice not in VOICE_PRESETS and not voice.endswith("Neural"):
        errors.append(f"[Gate 1: Voice] Unknown voice preset {voice!r}")

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 4:
        errors.append("[Gate 1: Scenes] Storyboard must contain at least 4 scenes (5 scenes standard: 4 exhibits + 1 rule)")
        scenes = scenes if isinstance(scenes, list) else []

    # Gate 2: Primary Exhibits & Crop Bounds
    ev_scene_count = 0
    cand_crops: Set[Tuple[str, Tuple[int, ...]]] = set()
    for idx, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            errors.append(f"[Gate 2: Scene {idx + 1}] Scene must be a JSON object")
            continue
        vtype = str(sc.get("visual_type", "stat_callout"))
        if vtype == "evidence_image":
            ev_scene_count += 1
            if sc.get("bullets"):
                warnings.append(
                    f"[Gate 2: Scene {idx + 1}] Omit 'bullets' on evidence_image scenes so the court exhibit fills the frame"
                )
            ev_rel = str(sc.get("evidence_image", "")).strip()
            if not ev_rel:
                errors.append(f"[Gate 2: Scene {idx + 1}] Missing 'evidence_image' path")
            else:
                ev_file = Path(ev_rel) if Path(ev_rel).is_absolute() else (project_root / ev_rel)
                if not ev_file.is_file():
                    errors.append(f"[Gate 2: Scene {idx + 1}] Missing screenshot file on disk: {ev_rel}")
                else:
                    try:
                        with Image.open(ev_file) as im:
                            w, h = im.size
                    except Exception as exc:
                        errors.append(f"[Gate 2: Scene {idx + 1}] Unreadable image {ev_rel}: {exc}")
                        w, h = 0, 0
                    crop = sc.get("evidence_crop")
                    if not (isinstance(crop, list) and len(crop) == 4 and all(isinstance(v, (int, float)) for v in crop)):
                        errors.append(f"[Gate 2: Scene {idx + 1}] 'evidence_crop' must be [x1, y1, x2, y2]")
                    elif w > 0 and h > 0:
                        x1, y1, x2, y2 = [int(v) for v in crop]
                        if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
                            errors.append(
                                f"[Gate 2: Scene {idx + 1}] Crop {[x1, y1, x2, y2]} out of bounds for {w}x{h} image {ev_rel}"
                            )
                        elif (x2 - x1) < 180 or (y2 - y1) < 70:
                            errors.append(
                                f"[Gate 2: Scene {idx + 1}] Crop {[x1, y1, x2, y2]} too tiny ({x2 - x1}x{y2 - y1}px) to read cleanly"
                            )
                        elif (y2 - y1) > (x2 - x1) * 1.25:
                            warnings.append(
                                f"[Gate 2: Scene {idx + 1}] Crop {[x1, y1, x2, y2]} is tall ({x2 - x1}x{y2 - y1}px); verify text remains crisp when scaled to card height"
                            )
                        hl = sc.get("evidence_highlight")
                        if hl is not None:
                            if not (isinstance(hl, list) and len(hl) == 4 and all(isinstance(v, (int, float)) for v in hl)):
                                errors.append(f"[Gate 2: Scene {idx + 1}] 'evidence_highlight' must be [hx1, hy1, hx2, hy2]")
                            else:
                                hx1, hy1, hx2, hy2 = [int(v) for v in hl]
                                if not (x1 <= hx1 < hx2 <= x2 and y1 <= hy1 < hy2 <= y2):
                                    errors.append(
                                        f"[Gate 2: Scene {idx + 1}] evidence_highlight {[hx1, hy1, hx2, hy2]} must stay inside evidence_crop {[x1, y1, x2, y2]}"
                                    )
                                elif (hx2 - hx1) < 40 or (hy2 - hy1) < 12:
                                    errors.append(
                                        f"[Gate 2: Scene {idx + 1}] evidence_highlight {[hx1, hy1, hx2, hy2]} too narrow/thin"
                                    )
                        cand_crops.add((Path(ev_rel).as_posix(), (x1, y1, x2, y2)))
        elif vtype == "comparison_split":
            for req_split in ("left_title", "left_body", "right_title", "right_body"):
                if not str(sc.get(req_split, "")).strip():
                    errors.append(f"[Gate 2: Scene {idx + 1}] comparison_split missing {req_split!r}")

    if ev_scene_count < 3:
        errors.append(f"[Gate 2: Exhibits] Expected >= 3 'evidence_image' scenes, found {ev_scene_count}")

    # Gate 3: Primary Source Citations
    sources = data.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        errors.append("[Gate 3: Sources] Top-level 'sources' must list >= 2 primary HTTPS URLs")
        sources = sources if isinstance(sources, list) else []
    for s_idx, entry in enumerate(sources):
        if not isinstance(entry, dict):
            errors.append(f"[Gate 3: Source #{s_idx + 1}] Entry must be an object with 'label' and 'url'")
            continue
        lbl = str(entry.get("label", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not lbl or "todo" in lbl.lower():
            errors.append(f"[Gate 3: Source #{s_idx + 1}] Missing or placeholder source label: {lbl!r}")
        if not url.startswith("https://"):
            errors.append(f"[Gate 3: Source #{s_idx + 1}] Source URL must start with https://: {url!r}")
        if any(dom in url.lower() for dom in PLACEHOLDER_DOMAINS):
            errors.append(f"[Gate 3: Source #{s_idx + 1}] Placeholder domain not allowed: {url!r}")

    for idx, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        sc_src = str(sc.get("source", "")).strip()
        if not sc_src:
            errors.append(f"[Gate 3: Scene {idx + 1}] Missing scene 'source' citation")
        elif "mind & margin" in sc_src.lower() or "todo" in sc_src.lower():
            errors.append(f"[Gate 3: Scene {idx + 1}] Scene 'source' must cite a real primary document, not {sc_src!r}")

    # Gate 4: Glyphs, Angle Brackets & AI-Writing Tells (mind-margin-brand)
    raw_dump = json.dumps(data, ensure_ascii=False)
    for glyph in sorted(FORBIDDEN_GLYPHS):
        if glyph in raw_dump:
            errors.append(f"[Gate 4: Glyphs] Forbidden glyph {glyph!r} found — use ASCII hyphens/arrows instead")

    yt_desc = build_youtube_description(data, slug=sb_path.stem) if scenes else ""
    for field_name in ("title", "alt_title_1", "alt_title_2"):
        val = str(data.get(field_name, ""))
        for br in ("<", ">"):
            if br in val:
                errors.append(f"[Gate 4: YouTube API] Forbidden angle bracket {br!r} in {field_name}")
    for br in ("<", ">"):
        if br in yt_desc:
            errors.append(f"[Gate 4: YouTube API] Forbidden angle bracket {br!r} in rendered YouTube description")

    copy_fields: List[Tuple[str, str]] = [
        ("title", str(data.get("title", ""))),
        ("alt_title_1", str(data.get("alt_title_1", ""))),
        ("alt_title_2", str(data.get("alt_title_2", ""))),
        ("description_hook", str(data.get("description_hook", ""))),
    ]
    for idx, sc in enumerate(scenes):
        if isinstance(sc, dict):
            nar = str(sc.get("narration", ""))
            copy_fields.append((f"scene[{idx + 1}].narration", nar))
            copy_fields.append((f"scene[{idx + 1}].headline", str(sc.get("headline", ""))))
            if re.match(r"^\s*here\s+is\s+how\b", nar, flags=re.I):
                errors.append(f"[Gate 4: Brand Voice] 'Here is how' opener banned in scene {idx + 1}")
            if "..." in nar:
                errors.append(f"[Gate 4: Brand Voice] '...' cliffhanger banned in scene {idx + 1}")

    for loc, text_val in copy_fields:
        low_val = text_val.lower()
        for phrase in BANNED_AI_PHRASES:
            if re.search(r"\b" + re.escape(phrase) + r"\b", low_val):
                errors.append(f"[Gate 4: Brand Voice] Banned AI buzzword {phrase!r} in {loc}")

    # Gate 5: Pacing & Visual Frame Bounds
    total_words = sum(len(str(sc.get("narration", "")).split()) for sc in scenes if isinstance(sc, dict))
    est_dur = round(sum(estimate_speech_duration(str(sc.get("narration", ""))) for sc in scenes if isinstance(sc, dict)), 1)
    if total_words < 55 or total_words > 130:
        errors.append(
            f"[Gate 5: Pacing] Narration word count ({total_words} words, ~{est_dur}s) outside allowed 55-130 Short window"
        )
    elif total_words < 65 or total_words > 115:
        warnings.append(
            f"[Gate 5: Pacing] Narration is {total_words} words (~{est_dur}s); sweet spot in mind-margin-brand is 65-115 words"
        )

    canvas = Image.new("RGB", (1080, 1920))
    draw = ImageDraw.Draw(canvas)
    pad_x = int(1080 * 0.075)
    cw = (1080 - pad_x - 40) - (pad_x + 40)
    max_src_w = 1080 - 2 * pad_x - 16
    head_font = _load_font(56, bold=True)
    for idx, sc in enumerate(scenes):
        if not isinstance(sc, dict):
            continue
        headline = str(sc.get("headline", "")).strip()
        if not headline:
            errors.append(f"[Gate 5: Scene {idx + 1}] Missing 'headline'")
        else:
            wrapped_h = _wrap_text(draw, headline, head_font, 1080 - 2 * pad_x)
            if len(wrapped_h) > 3:
                errors.append(f"[Gate 5: Scene {idx + 1}] Headline wraps to {len(wrapped_h)} lines (max 3): {headline!r}")
        if sc.get("source"):
            src_text = f"Source: {sc['source']}"
            src_size = 25
            src_font = _load_font(src_size, bold=False)
            while src_size > 17:
                sbx = draw.textbbox((0, 0), src_text, font=src_font)
                if (sbx[2] - sbx[0]) <= max_src_w:
                    break
                src_size -= 2
                src_font = _load_font(src_size, bold=False)
            for sln in _wrap_text(draw, src_text, src_font, max_src_w)[:2]:
                lbx = draw.textbbox((0, 0), sln, font=src_font)
                if (lbx[2] - lbx[0]) > max_src_w + 4:
                    errors.append(f"[Gate 5: Scene {idx + 1}] Source citation clips frame width: {sc['source']!r}")

    # Gate 6: Monetization & Amazon Associates Compliance
    aff = data.get("affiliate_cta") if isinstance(data.get("affiliate_cta"), dict) else {}
    cta_url = str(aff.get("url_placeholder", "")).strip()
    expected_bio = f"{SITE_BASE_URL}/bio/"
    if cta_url != expected_bio:
        errors.append(f"[Gate 6: Monetization] affiliate_cta.url_placeholder must be {expected_bio!r}, got {cta_url!r}")
    if "As an Amazon Associate I earn from qualifying purchases." not in yt_desc:
        errors.append("[Gate 6: Monetization] Missing verbatim Amazon Associate disclosure in description")
    full_editorial = " ".join(v for _, v in copy_fields)
    for pat in AMAZON_DISPARAGEMENT_PATTERNS:
        if pat.search(full_editorial):
            errors.append(
                "[Gate 6: Amazon Policy] Avoid disparaging Amazon retail/Prime while participating in Amazon Associates"
            )
            break

    # Gate 7: Multi-Layer Deduplication Against Active Queue & Published Ledger
    if check_dedupe:
        cand_stem = sb_path.stem
        cand_titles = {
            normalize_title(str(data.get(k, "")))
            for k in ("title", "alt_title_1", "alt_title_2")
            if str(data.get(k, "")).strip()
        }
        cand_urls = {
            normalize_source_url(str(s.get("url", "")))
            for s in sources
            if isinstance(s, dict) and str(s.get("url", "")).strip()
        }
        cand_words = _topic_word_set(data)

        for other in discover_storyboards(content_dir):
            if other.resolve() == sb_path:
                continue
            if other.stem == cand_stem:
                errors.append(f"[Gate 7: Dedupe] Storyboard stem {cand_stem!r} already exists at {other}")
                continue
            try:
                odata = json.loads(other.read_text(encoding="utf-8"))
            except Exception:
                continue
            otitles = {
                normalize_title(str(odata.get(k, "")))
                for k in ("title", "alt_title_1", "alt_title_2")
                if str(odata.get(k, "")).strip()
            }
            shared_t = cand_titles & otitles
            if shared_t:
                errors.append(f"[Gate 7: Dedupe] Title collides with {other.name}: {sorted(shared_t)}")

            ourls = {
                normalize_source_url(str(s.get("url", "")))
                for s in (odata.get("sources") or [])
                if isinstance(s, dict) and str(s.get("url", "")).strip()
            }
            shared_u = cand_urls & ourls
            if shared_u:
                errors.append(f"[Gate 7: Dedupe] Primary source URL already covered in {other.name}: {sorted(shared_u)}")

            ocrops = {
                (Path(str(sc.get("evidence_image", ""))).as_posix(), tuple(int(v) for v in (sc.get("evidence_crop") or [])))
                for sc in (odata.get("scenes") or [])
                if isinstance(sc, dict) and sc.get("visual_type") == "evidence_image" and sc.get("evidence_image")
            }
            shared_c = cand_crops & ocrops
            if shared_c:
                errors.append(f"[Gate 7: Dedupe] Exact evidence crop reused from {other.name}: {sorted(shared_c)}")

            owords = _topic_word_set(odata)
            jac = len(cand_words & owords) / max(1, len(cand_words | owords))
            if jac >= similarity_threshold:
                errors.append(
                    f"[Gate 7: Dedupe] High topic overlap (Jaccard={jac:.3f}) with {other.name}: {sorted(cand_words & owords)[:8]}"
                )

        ledger = load_ledger().get("published", {})
        for pub_slug, entry in ledger.items():
            if pub_slug == cand_stem:
                # Allowed if validating an already-published active storyboard in content/
                if sb_path.parent.resolve() != content_dir.resolve():
                    errors.append(f"[Gate 7: Ledger] Slug {cand_stem!r} was already published to YouTube")
                continue
            if isinstance(entry, dict):
                pt = normalize_title(str(entry.get("title", "")))
                if pt and pt in cand_titles:
                    errors.append(f"[Gate 7: Ledger] Title matches published video {pub_slug} ({entry.get('url')})")
                purls = {normalize_source_url(str(u)) for u in (entry.get("source_urls") or []) if u}
                if cand_urls & purls:
                    errors.append(f"[Gate 7: Ledger] Source URL matches published video {pub_slug} ({entry.get('url')})")

    return {
        "ok": len(errors) == 0,
        "path": str(sb_path),
        "slug": sb_path.stem,
        "word_count": total_words,
        "estimated_duration_sec": est_dur,
        "errors": errors,
        "warnings": warnings,
    }


def promote_draft_to_queue(
    draft_path: Path,
    target_slug: Optional[str] = None,
    content_dir: Path = CONTENT_DIR,
    output_dir: Path = OUTPUT_DIR,
    project_root: Path = PROJECT_ROOT,
    render_video: bool = False,
    tts_provider: str = "edge",
    encoder: str = "auto",
    rebuild_site: bool = True,
) -> Dict[str, Any]:
    """Atomically validate a draft in content/drafts/, move it to content/, generate SEO/SRT/Thumb, and sync site."""
    src = Path(draft_path).resolve()
    report = validate_storyboard(src, content_dir=content_dir, project_root=project_root, check_dedupe=True)
    if not report["ok"]:
        joined = "\n  - ".join(report["errors"])
        raise ValueError(f"Draft failed validation gates and cannot enter publish queue:\n  - {joined}")

    raw_slug = (target_slug or src.stem).strip()
    if not re.match(r"^short_\d+_", raw_slug):
        clean_tail = re.sub(r"^(?:draft_|short_)", "", raw_slug)
        raw_slug = f"{next_short_slug_prefix(content_dir)}_{clean_tail}"

    dest = content_dir / f"{raw_slug}.json"
    if dest.exists() and dest.resolve() != src:
        raise FileExistsError(f"Target storyboard already exists in active queue: {dest}")

    content_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(src.read_text(encoding="utf-8"))
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if src != dest.resolve() and src.is_file():
        src.unlink()
        prompt_companion = src.with_suffix(".prompt.txt")
        if prompt_companion.is_file():
            prompt_companion.unlink()

    proj_out = output_dir / raw_slug
    proj_out.mkdir(parents=True, exist_ok=True)
    if render_video:
        render_res = render_project(
            storyboard_path=dest,
            output_dir=output_dir,
            tts_provider=tts_provider,
            voice=str(data.get("voice", "en_authoritative")),
            skip_existing=False,
            encoder=encoder,
        )
        video_path = str(render_res["video"])
    else:
        scenes = data["scenes"]
        durs = [estimate_speech_duration(sc["narration"]) for sc in scenes]
        beats = []
        cursor = 0.0
        for s_idx, (sc, dur) in enumerate(zip(scenes, durs)):
            beats.extend(build_scene_beats(s_idx, sc["narration"], cursor, dur, max_words=3))
            cursor += dur
        export_srt(beats, proj_out / f"{raw_slug}.srt")
        tm = data["thumbnail"]
        render_thumbnail(
            hook_text=tm["hook_text"],
            sub_badge=tm["badge"],
            stat_highlight=tm["stat"],
            output_png=proj_out / f"{raw_slug}_thumbnail.png",
        )
        _write_seo_upload_pack(
            data,
            scenes,
            durs,
            "edge-tts:en-US-ChristopherNeural (pending cloud render)",
            proj_out / "youtube_upload_pack.md",
        )
        video_path = None

    if rebuild_site and content_dir.resolve() == CONTENT_DIR.resolve():
        audit_and_dedupe_projects(apply_cleanup=True)
        build_public_site(amazon_tag=DEFAULT_AMAZON_TAG)

    return {
        "promoted_storyboard": str(dest),
        "slug": raw_slug,
        "output_dir": str(proj_out),
        "video": video_path,
        "validation": report,
    }
