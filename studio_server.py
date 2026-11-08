#!/usr/bin/env python3
"""Mind & Margin — Local Web Command Center HTTP Server & Production REST API.

Pure Python 3 standard-library server (`http.server`) providing:
  - `/` & `/web_studio/...` -> Creator Command Center SPA (`web_studio/index.html`)
  - `/assets/...`           -> Channel branding & AI thumbnail assets
  - `/output/...`           -> Rendered MP4 videos (with HTTP Range 206 streaming), PNG thumbnails, SRTs & SEO packs
  - `/products/...`         -> Digital Products ($19 Asset Builder OS) & Bio Link Funnel pages
  - `GET /api/dashboard`    -> Real-time channel KPIs, storyboards, 30-day calendar, branding & product metadata
  - `POST /api/render`      -> Live FFmpeg + TTS storyboard rendering via `yt_studio.video_renderer.render_project`
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from yt_studio.config import ASSETS_DIR, CONTENT_DIR, DEFAULT_THEME, OUTPUT_DIR, discover_storyboards
from yt_studio.video_renderer import render_project

WEB_STUDIO_DIR = PROJECT_ROOT / "web_studio"
PRODUCTS_DIR = PROJECT_ROOT / "products"

CHUNK_SIZE = 64 * 1024
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}

EXTRA_MIME_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".srt": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".mp4": "video/mp4",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

_RENDER_LOCKS_GUARD = threading.Lock()
_RENDER_LOCKS: Dict[str, threading.Lock] = {}


def _get_render_lock(slug: str) -> threading.Lock:
    with _RENDER_LOCKS_GUARD:
        if slug not in _RENDER_LOCKS:
            _RENDER_LOCKS[slug] = threading.Lock()
        return _RENDER_LOCKS[slug]


def guess_content_type(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext in EXTRA_MIME_TYPES:
        return EXTRA_MIME_TYPES[ext]
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


def safe_resolve_under(base_dir: Path, relative_url_path: str) -> Optional[Path]:
    """Resolve `relative_url_path` strictly inside `base_dir` and `PROJECT_ROOT`."""
    if "\x00" in relative_url_path or "\\" in relative_url_path:
        return None
    try:
        project_resolved = PROJECT_ROOT.resolve()
        base_resolved = base_dir.resolve()
        rel_clean = relative_url_path.lstrip("/")
        candidate = (base_resolved / rel_clean).resolve()
        if not candidate.is_relative_to(base_resolved):
            return None
        if not candidate.is_relative_to(project_resolved):
            return None
        return candidate
    except (OSError, RuntimeError, ValueError):
        return None


def _storyboard_sort_key(path: Path) -> Tuple[int, List[Any]]:
    stem = path.stem.lower()
    group = 0 if stem.startswith("short") else (1 if stem.startswith("long") else 2)
    parts = [int(tok) if tok.isdigit() else tok for tok in re.split(r"(\d+)", stem)]
    return (group, parts)


def _extract_seo_description_from_pack(seo_pack_md: str) -> Optional[str]:
    match = re.search(
        r"##\s*2\.\s*Copy-Paste SEO Description\s*```(?:text)?\r?\n(.*?)\r?\n```",
        seo_pack_md,
        flags=re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return None


def _extract_runtime_from_pack(seo_pack_md: str) -> Optional[float]:
    match = re.search(r"\*\*Estimated Runtime\*\*:\s*`([0-9.]+)s`", seo_pack_md)
    if match:
        try:
            return round(float(match.group(1)), 1)
        except ValueError:
            return None
    return None


def _estimate_storyboard_runtime(scenes: List[Dict[str, Any]]) -> float:
    total = 0.0
    for sc in scenes:
        narration = str(sc.get("narration", ""))
        words = len(narration.split())
        pauses = narration.count(",") * 0.18 + (
            narration.count(".") + narration.count("?") + narration.count("!")
        ) * 0.32
        total += max(2.2, (words / (155.0 / 60.0)) + pauses)
    return round(total, 1)


def _build_fallback_seo_description(data: Dict[str, Any], scenes: List[Dict[str, Any]]) -> str:
    hook = data.get("description_hook") or data.get("title", "")
    aff = data.get("affiliate_cta") or {}
    aff_line = ""
    if aff:
        offer = aff.get("offer_name", "Free Leverage System Notion Template")
        url = aff.get("url_placeholder", "https://yourlink.com/resource")
        aff_line = f"\n🔗 **{offer}**: {url}\n"

    chapters = []
    acc = 0.0
    for sc in scenes:
        mins, secs = divmod(int(acc), 60)
        chapters.append(f"{mins:02d}:{secs:02d} - {sc.get('headline', sc.get('tag', 'Part'))}")
        words = len(str(sc.get("narration", "")).split())
        acc += max(2.5, words / 2.55)

    chapters_block = "\n".join(chapters)
    return (
        f"{hook}\n"
        f"{aff_line}\n"
        f"⏱️ Timestamps:\n{chapters_block}\n\n"
        f"📚 About {DEFAULT_THEME.channel_name}:\n"
        f"We break down wealth psychology, timeless book frameworks, and modern AI leverage "
        f"in visual essays designed for asymmetric thinkers.\n\n"
        f"⚠️ Disclaimer: Educational content & case studies only — not personalized financial "
        f"or legal advice. As an Amazon Associate I earn from qualifying purchases."
    ).strip()


def _find_matching_ai_thumbnail(slug: str) -> Optional[Path]:
    thumbs_dir = ASSETS_DIR / "thumbnails"
    if not thumbs_dir.is_dir():
        return None
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        cand = thumbs_dir / f"{slug}{ext}"
        if cand.is_file():
            return cand
    prefix_match = re.match(r"^((?:short|long)_\d+_)", slug.lower())
    if prefix_match:
        prefix = prefix_match.group(1)
        for cand in sorted(thumbs_dir.iterdir()):
            if cand.is_file() and cand.suffix.lower() in IMAGE_EXTENSIONS and cand.name.lower().startswith(prefix):
                return cand
    return None


def build_storyboard_item(sb_path: Path) -> Dict[str, Any]:
    """Read a storyboard JSON and enrich it with live output artifact status & URLs."""
    data = json.loads(sb_path.read_text(encoding="utf-8"))
    slug = sb_path.stem
    fmt = str(data.get("format", "short")).lower()
    scenes: List[Dict[str, Any]] = list(data.get("scenes") or [])

    proj_out = OUTPUT_DIR / slug
    mp4_path = proj_out / f"{slug}.mp4"
    thumb_out_path = proj_out / f"{slug}_thumbnail.png"
    srt_path = proj_out / f"{slug}.srt"
    seo_pack_path = proj_out / "youtube_upload_pack.md"

    mp4_exists = mp4_path.is_file()
    video_size_mb: Optional[float] = None
    video_mtime: Optional[int] = None
    rendered_at: Optional[str] = None
    if mp4_exists:
        st = mp4_path.stat()
        video_size_mb = round(st.st_size / (1024 * 1024), 2)
        video_mtime = int(st.st_mtime)
        rendered_at = dt.datetime.fromtimestamp(st.st_mtime, tz=dt.timezone.utc).isoformat()

    # Resolve thumbnail URL (prefer rendered output thumbnail, fallback to assets/thumbnails match)
    ai_thumb_file = _find_matching_ai_thumbnail(slug)
    ai_thumbnail_url = f"/assets/thumbnails/{ai_thumb_file.name}" if ai_thumb_file else None

    thumbnail_url: Optional[str] = None
    thumbnail_mtime: Optional[int] = None
    if thumb_out_path.is_file():
        thumbnail_url = f"/output/{slug}/{slug}_thumbnail.png"
        thumbnail_mtime = int(thumb_out_path.stat().st_mtime)
    elif ai_thumb_file is not None:
        thumbnail_url = ai_thumbnail_url
        thumbnail_mtime = int(ai_thumb_file.stat().st_mtime)

    seo_pack_text = ""
    if seo_pack_path.is_file():
        seo_pack_text = seo_pack_path.read_text(encoding="utf-8")

    seo_description = (
        _extract_seo_description_from_pack(seo_pack_text)
        if seo_pack_text
        else None
    ) or _build_fallback_seo_description(data, scenes)

    runtime_sec = (
        _extract_runtime_from_pack(seo_pack_text)
        if seo_pack_text
        else None
    ) or _estimate_storyboard_runtime(scenes)

    title = str(data.get("title", slug))
    alt_1 = str(data.get("alt_title_1") or f"{title} (Most People Miss This)")
    alt_2 = str(data.get("alt_title_2") or f"The Quiet Rule Behind {title}")
    tags: List[str] = [str(t) for t in (data.get("tags") or [])]
    aff: Dict[str, Any] = dict(data.get("affiliate_cta") or {})
    pinned_comment = str(
        aff.get(
            "pinned_comment",
            "Which mental model in this video hit closest to home for you? 👇",
        )
    )

    return {
        "slug": slug,
        "filename": sb_path.name,
        "format": fmt,
        "resolution": "1080x1920 (9:16)" if fmt == "short" else "1920x1080 (16:9)",
        "voice": str(data.get("voice", "en_authoritative")),
        "title": title,
        "alt_titles": [alt_1, alt_2],
        "alt_title_1": alt_1,
        "alt_title_2": alt_2,
        "description_hook": str(data.get("description_hook", "")),
        "description": seo_description,
        "tags": tags,
        "tags_csv": ", ".join(tags),
        "affiliate_cta": {
            "offer_name": str(aff.get("offer_name", "")),
            "url_placeholder": str(aff.get("url_placeholder", "")),
            "pinned_comment": pinned_comment,
        },
        "pinned_comment": pinned_comment,
        "thumbnail_meta": dict(data.get("thumbnail") or {}),
        "scene_count": len(scenes),
        "scenes": scenes,
        "estimated_runtime_sec": runtime_sec,
        "mp4_exists": mp4_exists,
        "rendered": mp4_exists,
        "rendered_at": rendered_at,
        "video_size_mb": video_size_mb,
        "video_mtime": video_mtime,
        "thumbnail_mtime": thumbnail_mtime,
        "video_url": f"/output/{slug}/{slug}.mp4" if mp4_exists else None,
        "thumbnail_url": thumbnail_url,
        "ai_thumbnail_url": ai_thumbnail_url,
        "srt_url": f"/output/{slug}/{slug}.srt" if srt_path.is_file() else None,
        "seo_pack_url": f"/output/{slug}/youtube_upload_pack.md" if seo_pack_path.is_file() else None,
        "youtube_upload_pack": seo_pack_text,
    }


def _tokenize_for_match(text: str) -> set[str]:
    stop = {"the", "and", "why", "how", "for", "you", "your", "still", "more", "what", "from", "with"}
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return {t for t in tokens if len(t) >= 3 and t not in stop}


def _match_calendar_row_to_storyboard(
    row_title: str,
    row_fmt: str,
    storyboards: List[Dict[str, Any]],
) -> Optional[str]:
    norm_row = row_title.strip().lower()
    if not norm_row:
        return None
    is_row_long = "long" in row_fmt.lower()
    for sb in storyboards:
        sb_title = sb["title"].strip().lower()
        if norm_row == sb_title or norm_row in sb_title or sb_title in norm_row:
            return sb["slug"]

    row_tokens = _tokenize_for_match(row_title)
    best_slug: Optional[str] = None
    best_score = 0
    for sb in storyboards:
        if (sb["format"] == "long") != is_row_long:
            continue
        sb_tokens = _tokenize_for_match(sb["title"] + " " + sb["slug"].replace("_", " "))
        overlap = len(row_tokens & sb_tokens)
        if overlap >= 2 and overlap > best_score:
            best_score = overlap
            best_slug = sb["slug"]
    return best_slug


def _load_calendar_rows(storyboards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    csv_path = CONTENT_DIR / "calendar_30_days.csv"
    if not csv_path.is_file():
        return []

    rows: List[Dict[str, Any]] = []
    sb_map = {sb["slug"]: sb for sb in storyboards}
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for idx, raw in enumerate(reader, start=1):
            day_str = (raw.get("Day") or f"Day {idx}").strip()
            day_num_match = re.search(r"(\d+)", day_str)
            day_num = int(day_num_match.group(1)) if day_num_match else idx
            fmt_str = (raw.get("Format") or "").strip()
            title_str = (raw.get("Video Title (English - High RPM)") or "").strip()
            est_raw = (raw.get("Est_Prod_Time_Mins") or "0").strip()
            try:
                est_mins = int(float(est_raw))
            except ValueError:
                est_mins = 0

            matched_slug = _match_calendar_row_to_storyboard(title_str, fmt_str, storyboards)
            matched_sb = sb_map.get(matched_slug) if matched_slug else None

            rows.append(
                {
                    "id": re.sub(r"[^a-z0-9]+", "_", day_str.lower()).strip("_") or f"row_{idx}",
                    "index": idx,
                    "day": day_str,
                    "day_num": day_num,
                    "week": (raw.get("Week") or "").strip(),
                    "format": fmt_str,
                    "is_long": "long" in fmt_str.lower(),
                    "pillar": (raw.get("Pillar") or "").strip(),
                    "title": title_str,
                    "hook": (raw.get("3-Second Retention Hook") or "").strip(),
                    "monetization": (raw.get("Primary Monetization (Day-1 Income)") or "").strip(),
                    "keyword": (raw.get("Target SEO Keyword") or "").strip(),
                    "est_prod_time_mins": est_mins,
                    "matched_slug": matched_slug,
                    "is_rendered": bool(matched_sb and matched_sb.get("mp4_exists")),
                }
            )
    return rows


def _scan_branding_and_thumbnails(storyboards: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    branding_dir = ASSETS_DIR / "branding"
    thumbs_dir = ASSETS_DIR / "thumbnails"

    branding_items: List[Dict[str, Any]] = []
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None

    if branding_dir.is_dir():
        for p in sorted(branding_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                st = p.stat()
                url = f"/assets/branding/{p.name}"
                stem_l = p.stem.lower()
                role = "branding"
                label = p.stem.replace("_", " ").title()
                if "avatar" in stem_l or "logo" in stem_l:
                    avatar_url = avatar_url or url
                    role = "avatar"
                    label = "Avatar Kênh Chính Thức (800×800)"
                elif "banner" in stem_l or "cover" in stem_l:
                    banner_url = banner_url or url
                    role = "banner"
                    label = "Banner Trang Chủ YouTube (2560×1440)"
                elif "thumb" in stem_l:
                    role = "sample_thumbnail"
                    label = "Thumbnail Mẫu Định Hình Phong Cách"

                branding_items.append(
                    {
                        "name": label,
                        "filename": p.name,
                        "role": role,
                        "url": url,
                        "size_kb": round(st.st_size / 1024, 1),
                        "mtime": int(st.st_mtime),
                    }
                )

    ai_thumbnails: List[Dict[str, Any]] = []
    if thumbs_dir.is_dir():
        for p in sorted(thumbs_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                st = p.stat()
                ai_thumbnails.append(
                    {
                        "title": p.stem.replace("_", " ").title(),
                        "filename": p.name,
                        "source": "AI / Assets Studio",
                        "source_type": "ai_asset",
                        "url": f"/assets/thumbnails/{p.name}",
                        "size_kb": round(st.st_size / 1024, 1),
                        "mtime": int(st.st_mtime),
                    }
                )

    # Also surface sample_thumbnail from assets/branding in AI concept thumbnails if present
    for b_item in branding_items:
        if b_item["role"] == "sample_thumbnail":
            ai_thumbnails.append(
                {
                    "title": b_item["name"],
                    "filename": b_item["filename"],
                    "source": "Brand Concept",
                    "source_type": "brand_sample",
                    "url": b_item["url"],
                    "size_kb": b_item["size_kb"],
                    "mtime": b_item["mtime"],
                }
            )

    sb_by_slug = {sb["slug"]: sb for sb in storyboards}
    rendered_thumbnails: List[Dict[str, Any]] = []
    if OUTPUT_DIR.is_dir():
        for p in sorted(OUTPUT_DIR.glob("*/*_thumbnail.png")):
            if p.is_file():
                st = p.stat()
                slug = p.parent.name
                sb = sb_by_slug.get(slug)
                meta = (sb or {}).get("thumbnail_meta") or {}
                rendered_thumbnails.append(
                    {
                        "slug": slug,
                        "title": sb["title"] if sb else slug.replace("_", " ").title(),
                        "hook_text": meta.get("hook_text", ""),
                        "badge": meta.get("badge", ""),
                        "stat": meta.get("stat", ""),
                        "filename": p.name,
                        "source": "Auto-Rendered (1280×720)",
                        "source_type": "rendered_output",
                        "url": f"/output/{slug}/{p.name}",
                        "size_kb": round(st.st_size / 1024, 1),
                        "mtime": int(st.st_mtime),
                    }
                )

    return (
        {
            "avatar_url": avatar_url,
            "banner_url": banner_url,
            "items": branding_items,
        },
        {
            "ai_assets": ai_thumbnails,
            "rendered_outputs": rendered_thumbnails,
            "all": ai_thumbnails + rendered_thumbnails,
        },
    )


def _scan_products() -> List[Dict[str, Any]]:
    known_specs = [
        {
            "slug": "5_hour_asset_builder_os",
            "title": "The 5-Hour Asset Builder OS",
            "vietnamese_label": "Sản Phẩm Số Chủ Lực ($19 Digital OS)",
            "price": "$19",
            "layer": "Layer 2 • Direct Digital Product (100% Margin)",
            "description": (
                "Hệ điều hành Notion / Interactive Web OS giúp người đi làm xây dựng thư viện "
                "tài sản số sinh lời dưới 5 giờ/tuần — bán trực tiếp ngay từ Ngày 1 không cần chờ AdSense."
            ),
            "entry_rel": "5_hour_asset_builder_os/index.html",
        },
        {
            "slug": "bio_funnel_page",
            "title": "Mind & Margin — Bio Link & Conversion Funnel",
            "vietnamese_label": "Trang Phễu Bio & Thu Lead (Link-in-Bio Hub)",
            "price": "Lead Magnet + Affiliate + $19 Upsell",
            "layer": "Layer 1 & 2 • High-Converting Traffic Router",
            "description": (
                "Trang đích gắn tại Bio YouTube, Pinned Comment và Mô tả Video để chuyển đổi "
                "lượt xem Shorts/Long thành email list, hoa hồng Affiliate Audible/Notion và đơn hàng $19 OS."
            ),
            "entry_rel": "bio_funnel_page/index.html",
        },
    ]

    results: List[Dict[str, Any]] = []
    seen_slugs = set()

    for spec in known_specs:
        slug = spec["slug"]
        seen_slugs.add(slug)
        folder = PRODUCTS_DIR / slug
        index_file = PRODUCTS_DIR / spec["entry_rel"]
        files: List[Dict[str, Any]] = []
        if folder.is_dir():
            for f in sorted(folder.rglob("*")):
                if f.is_file():
                    rel_to_products = f.relative_to(PRODUCTS_DIR).as_posix()
                    files.append(
                        {
                            "name": f.relative_to(folder).as_posix(),
                            "url": f"/products/{rel_to_products}",
                            "size_kb": round(f.stat().st_size / 1024, 1),
                        }
                    )
        results.append(
            {
                "slug": slug,
                "title": spec["title"],
                "vietnamese_label": spec["vietnamese_label"],
                "price": spec["price"],
                "layer": spec["layer"],
                "description": spec["description"],
                "url": f"/products/{spec['entry_rel']}",
                "exists": index_file.is_file(),
                "files": files,
            }
        )

    if PRODUCTS_DIR.is_dir():
        for sub in sorted(PRODUCTS_DIR.iterdir()):
            if sub.is_dir() and sub.name not in seen_slugs and not sub.name.startswith("."):
                idx_html = sub / "index.html"
                files = [
                    {
                        "name": f.relative_to(sub).as_posix(),
                        "url": f"/products/{f.relative_to(PRODUCTS_DIR).as_posix()}",
                        "size_kb": round(f.stat().st_size / 1024, 1),
                    }
                    for f in sorted(sub.rglob("*"))
                    if f.is_file()
                ]
                is_lead = "lead" in sub.name.lower() or "free" in sub.name.lower()
                results.append(
                    {
                        "slug": sub.name,
                        "title": (
                            "Free Lead Magnet — Wealth & Leverage Playbook"
                            if is_lead
                            else sub.name.replace("_", " ").title()
                        ),
                        "vietnamese_label": (
                            "Quà Tặng Thu Phễu Email Miễn Phí (Lead Magnet)"
                            if is_lead
                            else "Tài Nguyên Số Bổ Sung"
                        ),
                        "price": "FREE LEAD MAGNET" if is_lead else "Bonus Asset",
                        "layer": "Layer 1 • Email Capture & Trust Builder" if is_lead else "Digital Ecosystem",
                        "description": (
                            f"Tài liệu giá trị cao dùng để tặng miễn phí thu thập Email khách hàng tiềm năng ({files[0]['name']})."
                            if (is_lead and files)
                            else f"Tài nguyên số trong thư mục products/{sub.name}/"
                        ),
                        "url": (
                            f"/products/{sub.name}/index.html"
                            if idx_html.is_file()
                            else (files[0]["url"] if files else f"/products/{sub.name}/")
                        ),
                        "exists": idx_html.is_file() or bool(files),
                        "files": files,
                    }
                )

    return results


def build_dashboard_payload() -> Dict[str, Any]:
    """Assemble the complete real-time JSON payload for `GET /api/dashboard`."""
    from yt_studio.trend_radar import build_trend_intelligence_report

    storyboard_files = sorted(discover_storyboards(CONTENT_DIR), key=_storyboard_sort_key)
    storyboards = [build_storyboard_item(p) for p in storyboard_files]
    calendar_rows = _load_calendar_rows(storyboards)
    branding, thumbnails = _scan_branding_and_thumbnails(storyboards)
    products = _scan_products()
    trends = build_trend_intelligence_report()

    # Count MP4s across storyboards and output/*/*.mp4
    output_mp4_files = list(OUTPUT_DIR.glob("*/*.mp4")) if OUTPUT_DIR.is_dir() else []
    rendered_storyboards_count = sum(1 for sb in storyboards if sb["mp4_exists"])
    rendered_mp4_count = max(rendered_storyboards_count, len(output_mp4_files))

    unique_weeks = {r["week"] for r in calendar_rows if r["week"]}
    num_weeks = max(1, len(unique_weeks) or 4)
    total_monthly_mins = sum(r["est_prod_time_mins"] for r in calendar_rows)
    weekly_mins = round(total_monthly_mins / num_weeks) if total_monthly_mins else 255
    weekly_hours = round(weekly_mins / 60.0, 2)

    return {
        "ok": True,
        "generated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "channel": {
            "name": DEFAULT_THEME.channel_name,
            "handle": DEFAULT_THEME.channel_handle,
            "tagline": DEFAULT_THEME.tagline,
            "ypp_deadline": "2027-02-01",
        },
        "stats": {
            "total_scripts": len(storyboards),
            "rendered_mp4_count": rendered_mp4_count,
            "rendered_storyboards_count": rendered_storyboards_count,
            "short_count": sum(1 for sb in storyboards if sb["format"] == "short"),
            "long_count": sum(1 for sb in storyboards if sb["format"] == "long"),
            "calendar_rows": len(calendar_rows),
            "calendar_weeks": num_weeks,
            "total_monthly_minutes": total_monthly_mins,
            "estimated_weekly_minutes": weekly_mins,
            "estimated_weekly_hours": weekly_hours,
        },
        "storyboards": storyboards,
        "calendar": calendar_rows,
        "branding": branding,
        "thumbnails": thumbnails,
        "products": products,
        "trends": trends,
    }


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class StudioRequestHandler(BaseHTTPRequestHandler):
    server_version = "MindAndMarginStudio/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("STUDIO_QUIET") == "1":
            return
        super().log_message(fmt, *args)

    # ---- HTTP Verbs ----

    def do_GET(self) -> None:
        self._handle_read_request(send_body=True)

    def do_HEAD(self) -> None:
        self._handle_read_request(send_body=False)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        route = parsed.path.rstrip("/") or "/"
        if route == "/api/render":
            self._handle_api_render()
            return
        self._send_json({"ok": False, "error": f"Unknown API endpoint: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)

    # ---- Routing & Handlers ----

    def _handle_read_request(self, send_body: bool) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        raw_path = urllib.parse.unquote(parsed.path)

        if "\x00" in raw_path or "\\" in raw_path:
            self._send_json({"ok": False, "error": "Forbidden path."}, status=HTTPStatus.FORBIDDEN, send_body=send_body)
            return

        if raw_path in ("/", "/index.html"):
            index_file = WEB_STUDIO_DIR / "index.html"
            if not index_file.is_file():
                self._send_json(
                    {"ok": False, "error": "web_studio/index.html not found."},
                    status=HTTPStatus.NOT_FOUND,
                    send_body=send_body,
                )
                return
            self._serve_static_file(index_file, send_body=send_body)
            return

        if raw_path.rstrip("/") == "/api/dashboard":
            try:
                payload = build_dashboard_payload()
                self._send_json(payload, status=HTTPStatus.OK, send_body=send_body)
            except Exception as exc:
                self._send_json(
                    {"ok": False, "error": f"Failed to build dashboard payload: {exc}"},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    send_body=send_body,
                )
            return

        if raw_path.rstrip("/") == "/api/trends":
            from yt_studio.trend_radar import build_trend_intelligence_report
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or [None])[0]
            self._send_json(build_trend_intelligence_report(live_query=q), status=HTTPStatus.OK, send_body=send_body)
            return

        if raw_path.rstrip("/") == "/api/health":
            self._send_json({"ok": True, "service": "mind_and_margin_studio"}, status=HTTPStatus.OK, send_body=send_body)
            return

        # Static prefix mapping
        static_mounts: List[Tuple[str, Path]] = [
            ("/web_studio/", WEB_STUDIO_DIR),
            ("/assets/", ASSETS_DIR),
            ("/output/", OUTPUT_DIR),
            ("/products/", PRODUCTS_DIR),
        ]

        for prefix, mount_dir in static_mounts:
            prefix_bare = prefix.rstrip("/")
            if raw_path == prefix_bare or raw_path.startswith(prefix):
                # Reject explicit parent traversal attempts immediately with 403
                rel_part = raw_path[len(prefix_bare):]
                segments = [seg for seg in rel_part.split("/") if seg]
                if ".." in segments:
                    self._send_json(
                        {"ok": False, "error": "Path traversal denied."},
                        status=HTTPStatus.FORBIDDEN,
                        send_body=send_body,
                    )
                    return

                resolved = safe_resolve_under(mount_dir, rel_part)
                if resolved is None:
                    self._send_json(
                        {"ok": False, "error": "Path outside allowed directory."},
                        status=HTTPStatus.FORBIDDEN,
                        send_body=send_body,
                    )
                    return

                if resolved.is_dir():
                    if not raw_path.endswith("/"):
                        redirect_target = raw_path + "/"
                        if parsed.query:
                            redirect_target += f"?{parsed.query}"
                        self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                        self.send_header("Location", redirect_target)
                        self.end_headers()
                        return
                    index_in_dir = resolved / "index.html"
                    if index_in_dir.is_file():
                        self._serve_static_file(index_in_dir, send_body=send_body)
                        return

                if not resolved.is_file():
                    self._send_not_found(raw_path, send_body=send_body)
                    return

                self._serve_static_file(resolved, send_body=send_body)
                return

        # Catch root-level `..` traversal probes
        if ".." in raw_path.split("/"):
            self._send_json(
                {"ok": False, "error": "Path traversal denied."},
                status=HTTPStatus.FORBIDDEN,
                send_body=send_body,
            )
            return

        self._send_not_found(raw_path, send_body=send_body)

    def _handle_api_render(self) -> None:
        try:
            content_len = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_len = 0

        if content_len <= 0 or content_len > 64 * 1024:
            self._send_json(
                {"ok": False, "error": "Invalid or missing JSON request body."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        raw_body = self.rfile.read(content_len)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "Malformed JSON payload."}, status=HTTPStatus.BAD_REQUEST)
            return

        if not isinstance(body, dict):
            self._send_json({"ok": False, "error": "JSON body must be an object."}, status=HTTPStatus.BAD_REQUEST)
            return

        slug = str(body.get("slug", "")).strip()
        if slug.endswith(".json"):
            slug = slug[:-5]

        if not SLUG_PATTERN.fullmatch(slug):
            self._send_json(
                {"ok": False, "error": "Invalid storyboard slug."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        storyboard_path = safe_resolve_under(CONTENT_DIR, f"{slug}.json")
        if storyboard_path is None or not storyboard_path.is_file():
            matches = [p for p in discover_storyboards(CONTENT_DIR) if p.stem == slug]
            storyboard_path = matches[0] if matches else None
        if storyboard_path is None or not storyboard_path.is_file():
            self._send_json(
                {"ok": False, "error": f"Storyboard '{slug}.json' not found under content/."},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        tts_provider = str(body.get("tts", "auto")).strip() or "auto"
        if tts_provider not in {"auto", "edge", "openai", "elevenlabs", "offline"}:
            tts_provider = "auto"
        voice = str(body.get("voice", "en_authoritative")).strip() or "en_authoritative"

        lock = _get_render_lock(slug)
        t0 = time.monotonic()
        try:
            with lock:
                outputs = render_project(
                    storyboard_path=storyboard_path,
                    output_dir=OUTPUT_DIR,
                    tts_provider=tts_provider,
                    voice=voice,
                )
            elapsed_sec = round(time.monotonic() - t0, 2)
            updated_sb = build_storyboard_item(storyboard_path)

            rel_paths: Dict[str, str] = {}
            for k, out_p in outputs.items():
                rel_paths[k] = "/" + out_p.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()

            self._send_json(
                {
                    "ok": True,
                    "status": "rendered",
                    "slug": slug,
                    "elapsed_sec": elapsed_sec,
                    "paths": rel_paths,
                    "storyboard": updated_sb,
                },
                status=HTTPStatus.OK,
            )
        except Exception as exc:
            self._send_json(
                {
                    "ok": False,
                    "status": "error",
                    "slug": slug,
                    "error": str(exc),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    # ---- Response Helpers (JSON + HTTP Range Binary Streaming) ----

    def _send_json(self, data: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK, send_body: bool = True) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _send_not_found(self, path_str: str, send_body: bool = True) -> None:
        if path_str.startswith("/api/"):
            self._send_json({"ok": False, "error": f"Not found: {path_str}"}, status=HTTPStatus.NOT_FOUND, send_body=send_body)
            return
        html = (
            "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
            "<title>404 — Không tìm thấy tài nguyên</title>"
            "<style>body{background:#0B1020;color:#F8FAFC;font-family:system-ui,sans-serif;"
            "display:grid;place-items:center;min-height:90vh;margin:0}"
            ".box{background:#131C34;border:1px solid rgba(148,163,184,.2);padding:32px;border-radius:16px;max-width:520px;text-align:center}"
            "h1{color:#F5B942;margin:0 0 12px;font-size:22px}p{color:#94A3B8;line-height:1.6;margin:0 0 20px}"
            "a{color:#22D3EE;text-decoration:none;font-weight:600}</style></head>"
            f"<body><div class='box'><h1>404 — Chưa tìm thấy tệp</h1>"
            f"<p>Đường dẫn <code>{path_str}</code> hiện chưa tồn tại trong thư mục dự án.</p>"
            "<a href='/'>← Quay về Creator Command Center</a></div></body></html>"
        ).encode("utf-8")
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        if send_body:
            try:
                self.wfile.write(html)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _serve_static_file(self, file_path: Path, send_body: bool = True) -> None:
        st = file_path.stat()
        file_size = st.st_size
        content_type = guess_content_type(file_path)
        range_header = self.headers.get("Range")

        if range_header and file_size > 0:
            m = RANGE_PATTERN.match(range_header.strip())
            if m:
                start_str, end_str = m.group(1), m.group(2)
                start: Optional[int] = None
                end: Optional[int] = None

                if start_str == "" and end_str != "":
                    suffix_len = int(end_str)
                    if suffix_len > 0:
                        start = max(0, file_size - suffix_len)
                        end = file_size - 1
                elif start_str != "":
                    start = int(start_str)
                    end = int(end_str) if end_str != "" else file_size - 1
                    if end >= file_size:
                        end = file_size - 1

                if start is None or end is None or start < 0 or start > end or start >= file_size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                chunk_total = end - start + 1
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Type", content_type)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(chunk_total))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()

                if send_body:
                    self._stream_file_slice(file_path, start, chunk_total)
                return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        if send_body and file_size > 0:
            self._stream_file_slice(file_path, 0, file_size)

    def _stream_file_slice(self, file_path: Path, offset: int, length: int) -> None:
        remaining = length
        try:
            with file_path.open("rb") as fh:
                if offset > 0:
                    fh.seek(offset)
                while remaining > 0:
                    buf = fh.read(min(CHUNK_SIZE, remaining))
                    if not buf:
                        break
                    self.wfile.write(buf)
                    remaining -= len(buf)
        except (BrokenPipeError, ConnectionResetError):
            # Browser aborted range stream while seeking video; ignore cleanly.
            pass


def create_server(host: str = "0.0.0.0", port: int = 8765) -> ReusableThreadingHTTPServer:
    return ReusableThreadingHTTPServer((host, port), StudioRequestHandler)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mind & Margin — Local Web Command Center (Creator Studio Server)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("STUDIO_PORT", "8765")),
        help="HTTP port to bind (default: 8765)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("STUDIO_HOST", "0.0.0.0"),
        help="Host interface to bind (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    httpd = create_server(host=args.host, port=args.port)
    actual_port = httpd.server_address[1]
    print(f"🚀 Mind & Margin Creator Command Center running at: http://localhost:{actual_port}")
    print(f"   • Dashboard UI : http://localhost:{actual_port}/")
    print(f"   • REST API     : http://localhost:{actual_port}/api/dashboard")
    print("   Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down Studio Server...")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
