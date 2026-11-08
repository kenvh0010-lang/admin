"""Dark-Minimalist Visual Essay Scene Composer & High-CTR Thumbnail Generator."""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from .config import BrandTheme, DEFAULT_THEME, VideoFormat, resolve_font_path


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(resolve_font_path(bold=bold), size=size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if (bbox[2] - bbox[0]) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_scene_beat_frame(
    scene: Dict[str, Any],
    caption_text: str,
    scene_idx: int,
    total_scenes: int,
    progress_ratio: float,
    fmt: VideoFormat,
    output_png: Path,
    theme: BrandTheme = DEFAULT_THEME,
) -> Path:
    """
    Render a crisp visual-essay frame with:
      - Custom background image (if provided) OR architectural grid + glow backdrop
      - Dynamic infographic diagram (`stat_callout`, `comparison_split`, `compounding_curve`, `flywheel`)
      - Active kinetic subtitle card with keyword gold highlighting
      - Progress bar & brand watermark
    """
    output_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = fmt.width, fmt.height
    is_vert = fmt.is_vertical

    img = Image.new("RGB", (w, h), theme.bg_primary)
    bg_image_path = scene.get("image_path")
    if bg_image_path and Path(bg_image_path).is_file():
        bg = Image.open(bg_image_path).convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
        overlay = Image.new("RGB", (w, h), theme.bg_primary)
        img = Image.blend(bg, overlay, alpha=0.68)

    draw = ImageDraw.Draw(img)

    # 1. Subtle architectural grid
    grid_step = 72 if is_vert else 80
    for gx in range(0, w, grid_step):
        draw.line([(gx, 0), (gx, h)], fill=theme.grid_line, width=1)
    for gy in range(0, h, grid_step):
        draw.line([(0, gy), (w, gy)], fill=theme.grid_line, width=1)

    pad_x = int(w * 0.075)
    top_y = int(h * (0.065 if is_vert else 0.08))

    # 2. Top Brand & Chapter Header
    tag_font = _load_font(28 if is_vert else 24, bold=True)
    meta_font = _load_font(26 if is_vert else 22, bold=False)
    chapter_tag = str(scene.get("tag", "INSIGHT")).upper()

    tag_bbox = draw.textbbox((0, 0), chapter_tag, font=tag_font)
    pill_w = (tag_bbox[2] - tag_bbox[0]) + 36
    pill_h = (tag_bbox[3] - tag_bbox[1]) + 20
    tag_color = theme.accent_crimson if chapter_tag == "THE TRAP" or chapter_tag == "HOOK" else theme.accent_gold

    draw.rounded_rectangle(
        [pad_x, top_y, pad_x + pill_w, top_y + pill_h],
        radius=12,
        fill=theme.bg_card,
        outline=tag_color,
        width=2,
    )
    draw.text((pad_x + 18, top_y + 8), chapter_tag, font=tag_font, fill=tag_color)

    step_label = f"{theme.channel_handle}  •  {scene_idx + 1:02d}/{total_scenes:02d}"
    sb = draw.textbbox((0, 0), step_label, font=meta_font)
    draw.text((w - pad_x - (sb[2] - sb[0]), top_y + 10), step_label, font=meta_font, fill=theme.text_muted)

    # 3. Scene Headline
    headline = scene.get("headline", "")
    head_font = _load_font(56 if is_vert else 52, bold=True)
    head_y = top_y + pill_h + (42 if is_vert else 28)
    head_lines = _wrap_text(draw, headline, head_font, w - 2 * pad_x)
    for line in head_lines[:3]:
        draw.text((pad_x, head_y), line, font=head_font, fill=theme.text_primary)
        head_y += int((68 if is_vert else 62))

    # 4. Dynamic Visual Infographic Card (avoids generic template spam!)
    card_top = head_y + (34 if is_vert else 24)
    card_bottom = int(h * (0.64 if is_vert else 0.70))
    if card_bottom - card_top > 180:
        draw.rounded_rectangle(
            [pad_x, card_top, w - pad_x, card_bottom],
            radius=28,
            fill=theme.bg_card,
            outline=theme.grid_line,
            width=3,
        )
        _draw_visual_card_content(
            draw=draw,
            scene=scene,
            box=(pad_x + 40, card_top + 36, w - pad_x - 40, card_bottom - 36),
            is_vert=is_vert,
            theme=theme,
        )

    # 5. High-Retention Kinetic Caption Box (in Shorts safe zone!)
    cap_top = int(h * (0.68 if is_vert else 0.75))
    cap_font = _load_font(46 if is_vert else 40, bold=True)
    cap_lines = _wrap_text(draw, caption_text, cap_font, w - 2 * pad_x - 48)
    line_h = 58 if is_vert else 50
    box_h = len(cap_lines) * line_h + 44

    draw.rounded_rectangle(
        [pad_x, cap_top, w - pad_x, cap_top + box_h],
        radius=22,
        fill=(14, 21, 40),
        outline=theme.accent_cyan,
        width=2,
    )

    highlight_words = {
        w_clean.lower()
        for w_clean in scene.get("highlight_words", [])
    }

    curr_y = cap_top + 20
    for line in cap_lines:
        # Center each caption line and highlight key power words in gold
        words = line.split()
        word_widths = []
        space_w = draw.textbbox((0, 0), " ", font=cap_font)[2]
        for wd in words:
            wb = draw.textbbox((0, 0), wd, font=cap_font)
            word_widths.append(wb[2] - wb[0])
        total_line_w = sum(word_widths) + space_w * max(0, len(words) - 1)
        cursor_x = (w - total_line_w) // 2

        for wd, ww in zip(words, word_widths):
            stripped = wd.strip(".,!?:;\"'()$%").lower()
            is_num_or_key = stripped in highlight_words or any(ch.isdigit() for ch in wd)
            color = theme.accent_gold if is_num_or_key else theme.text_primary
            draw.text((cursor_x, curr_y), wd, font=cap_font, fill=color)
            cursor_x += ww + space_w
        curr_y += line_h

    # 6. Bottom Retention Progress Bar
    bar_y = int(h * (0.93 if is_vert else 0.94))
    bar_h = 10
    draw.rounded_rectangle([pad_x, bar_y, w - pad_x, bar_y + bar_h], radius=5, fill=theme.grid_line)
    fill_w = max(12, int((w - 2 * pad_x) * min(1.0, max(0.02, progress_ratio))))
    draw.rounded_rectangle([pad_x, bar_y, pad_x + fill_w, bar_y + bar_h], radius=5, fill=theme.accent_gold)

    img.save(output_png, format="PNG")
    return output_png


def _draw_visual_card_content(
    draw: ImageDraw.ImageDraw,
    scene: Dict[str, Any],
    box: Tuple[int, int, int, int],
    is_vert: bool,
    theme: BrandTheme,
) -> None:
    x1, y1, x2, y2 = box
    cw = x2 - x1
    ch = y2 - y1
    layout = scene.get("visual_type", "stat_callout")

    if layout == "comparison_split":
        left_label = scene.get("left_title", "LINEAR EFFORT")
        left_val = scene.get("left_body", "Trade hours for dollars")
        right_label = scene.get("right_title", "COMPOUND LEVERAGE")
        right_val = scene.get("right_body", "Build assets once, earn 24/7")

        lbl_font = _load_font(28 if is_vert else 24, bold=True)
        body_font = _load_font(34 if is_vert else 28, bold=False)

        if is_vert:
            mid_y = y1 + ch // 2
            draw.rounded_rectangle([x1, y1, x2, mid_y - 14], radius=18, fill=(28, 22, 38), outline=theme.accent_crimson, width=2)
            draw.text((x1 + 26, y1 + 22), f"[X]  {left_label}", font=lbl_font, fill=theme.accent_crimson)
            for idx, ln in enumerate(_wrap_text(draw, left_val, body_font, cw - 52)[:2]):
                draw.text((x1 + 26, y1 + 68 + idx * 42), ln, font=body_font, fill=theme.text_primary)

            draw.rounded_rectangle([x1, mid_y + 14, x2, y2], radius=18, fill=(16, 36, 52), outline=theme.accent_cyan, width=2)
            draw.text((x1 + 26, mid_y + 36), f"[+]  {right_label}", font=lbl_font, fill=theme.accent_cyan)
            for idx, ln in enumerate(_wrap_text(draw, right_val, body_font, cw - 52)[:2]):
                draw.text((x1 + 26, mid_y + 82 + idx * 42), ln, font=body_font, fill=theme.text_primary)
        else:
            mid_x = x1 + cw // 2
            draw.rounded_rectangle([x1, y1, mid_x - 16, y2], radius=18, fill=(28, 22, 38), outline=theme.accent_crimson, width=2)
            draw.text((x1 + 24, y1 + 24), f"[X]  {left_label}", font=lbl_font, fill=theme.accent_crimson)
            for idx, ln in enumerate(_wrap_text(draw, left_val, body_font, (cw // 2) - 64)[:3]):
                draw.text((x1 + 24, y1 + 74 + idx * 38), ln, font=body_font, fill=theme.text_primary)

            draw.rounded_rectangle([mid_x + 16, y1, x2, y2], radius=18, fill=(16, 36, 52), outline=theme.accent_cyan, width=2)
            draw.text((mid_x + 40, y1 + 24), f"[+]  {right_label}", font=lbl_font, fill=theme.accent_cyan)
            for idx, ln in enumerate(_wrap_text(draw, right_val, body_font, (cw // 2) - 64)[:3]):
                draw.text((mid_x + 40, y1 + 74 + idx * 38), ln, font=body_font, fill=theme.text_primary)

    elif layout == "compounding_curve":
        # Draw exponential vs linear curve diagram
        axis_left = x1 + 30
        axis_bottom = y2 - 50
        axis_right = x2 - 30
        axis_top = y1 + 50
        draw.line([(axis_left, axis_bottom), (axis_right, axis_bottom)], fill=theme.text_muted, width=3)
        draw.line([(axis_left, axis_bottom), (axis_left, axis_top)], fill=theme.text_muted, width=3)

        steps = 40
        lin_pts = []
        exp_pts = []
        plot_w = axis_right - axis_left
        plot_h = axis_bottom - axis_top
        for s in range(steps + 1):
            u = s / steps
            px = int(axis_left + u * plot_w)
            ly = int(axis_bottom - (0.32 * u) * plot_h)
            ey = int(axis_bottom - ((math.exp(3.2 * u) - 1) / (math.exp(3.2) - 1)) * 0.92 * plot_h)
            lin_pts.append((px, ly))
            exp_pts.append((px, ey))

        draw.line(lin_pts, fill=theme.text_muted, width=4)
        draw.line(exp_pts, fill=theme.accent_gold, width=7)
        ex, ey = exp_pts[-1]
        draw.ellipse([ex - 10, ey - 10, ex + 10, ey + 10], fill=theme.accent_gold)

        cap_f = _load_font(28 if is_vert else 24, bold=True)
        metric_note = scene.get("stat_label", "COMPOUNDING SYSTEM CURVE")
        draw.text((axis_left + 16, axis_top - 10), metric_note, font=cap_f, fill=theme.accent_gold)
        sub_f = _load_font(24 if is_vert else 20, bold=False)
        draw.text((axis_left + 16, axis_bottom + 14), scene.get("stat_subtext", "Time + Leverage -> Asymmetric Output"), font=sub_f, fill=theme.text_muted)

    else:
        # Default: High-impact Stat / Principle Callout + Bullet Takeaways
        stat_val = str(scene.get("stat_value", "1%"))
        stat_label = str(scene.get("stat_label", "CORE MENTAL MODEL"))
        bullets = scene.get("bullets", [])

        big_font = _load_font(108 if is_vert else 88, bold=True)
        lbl_font = _load_font(32 if is_vert else 28, bold=True)
        bul_font = _load_font(30 if is_vert else 25, bold=False)

        draw.text((x1 + 16, y1 + 10), stat_val, font=big_font, fill=theme.accent_gold)
        vb = draw.textbbox((x1 + 16, y1 + 10), stat_val, font=big_font)
        curr_y = vb[3] + 22
        draw.text((x1 + 16, curr_y), stat_label.upper(), font=lbl_font, fill=theme.accent_cyan)
        curr_y += 52

        for b_text in bullets[:3]:
            wrapped = _wrap_text(draw, f"•  {b_text}", bul_font, cw - 32)
            for ln in wrapped[:2]:
                if curr_y + 36 <= y2:
                    draw.text((x1 + 16, curr_y), ln, font=bul_font, fill=theme.text_primary)
                    curr_y += 38


def render_thumbnail(
    hook_text: str,
    sub_badge: str,
    stat_highlight: str,
    output_png: Path,
    bg_image: Optional[Path] = None,
    theme: BrandTheme = DEFAULT_THEME,
) -> Path:
    """Generate a high-contrast 1280x720 YouTube thumbnail programmatically."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), theme.bg_primary)
    if bg_image and bg_image.is_file():
        bg = Image.open(bg_image).convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
        img = Image.blend(bg, img, alpha=0.55)

    draw = ImageDraw.Draw(img)
    for gx in range(0, w, 64):
        draw.line([(gx, 0), (gx, h)], fill=theme.grid_line, width=1)

    # Badge
    badge_font = _load_font(30, bold=True)
    bb = draw.textbbox((0, 0), sub_badge.upper(), font=badge_font)
    bw = (bb[2] - bb[0]) + 44
    draw.rounded_rectangle([68, 64, 68 + bw, 124], radius=14, fill=theme.accent_crimson)
    draw.text((90, 76), sub_badge.upper(), font=badge_font, fill=theme.text_primary)

    # Giant Hook Text (3-5 words max for 10%+ CTR)
    hook_font = _load_font(112, bold=True)
    lines = _wrap_text(draw, hook_text.upper(), hook_font, 780)
    hy = 160
    for idx, ln in enumerate(lines[:3]):
        color = theme.accent_gold if idx == len(lines[:3]) - 1 else theme.text_primary
        draw.text((68, hy), ln, font=hook_font, fill=color)
        hy += 124

    # Right-side visual metric card
    draw.rounded_rectangle([860, 150, 1212, 570], radius=28, fill=theme.bg_card, outline=theme.accent_gold, width=4)
    stat_font = _load_font(96, bold=True)
    sb = draw.textbbox((0, 0), stat_highlight, font=stat_font)
    sx = 860 + (352 - (sb[2] - sb[0])) // 2
    draw.text((sx, 260), stat_highlight, font=stat_font, fill=theme.accent_gold)

    brand_f = _load_font(26, bold=True)
    hb = draw.textbbox((0, 0), theme.channel_handle.upper(), font=brand_f)
    hx = 860 + (352 - (hb[2] - hb[0])) // 2
    draw.text((hx, 420), theme.channel_handle.upper(), font=brand_f, fill=theme.accent_cyan)

    img.save(output_png, format="PNG")
    return output_png
