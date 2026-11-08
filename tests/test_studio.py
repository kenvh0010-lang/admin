"""End-to-end QA tests across Content (Q1+Q2: 96 Scripts), Monetization, Visual, Audio, Autopilot & Web Studio."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from yt_studio.config import CONTENT_DIR, FORMATS, PROJECT_ROOT, resolve_font_path
from yt_studio.site_builder import DEFAULT_AMAZON_TAG
from yt_studio.subtitle_maker import build_scene_beats, export_srt
from yt_studio.tts_engine import estimate_speech_duration, generate_ambient_bed
from yt_studio.visual_composer import render_scene_beat_frame, render_thumbnail
from yt_studio.youtube_uploader import build_youtube_description, pick_next_unpublished_storyboard


class TestYouTubeStudioEcosystem(unittest.TestCase):
    def test_font_resolution(self) -> None:
        self.assertTrue(Path(resolve_font_path(bold=True)).is_file())
        self.assertTrue(Path(resolve_font_path(bold=False)).is_file())

    def test_all_112_storyboards_valid_cited_and_glyph_safe(self) -> None:
        storyboards = sorted(
            p for p in CONTENT_DIR.glob("*.json") if p.name != "published_ledger.json"
        )
        # 08/11/2026: bỏ thư viện 112 kịch bản cũ, kênh chuyển sang short tin tức có ảnh dẫn chứng.
        self.assertGreaterEqual(len(storyboards), 1, "Expected at least one storyboard in content/")
        required_keys = {"title", "format", "scenes", "tags", "thumbnail", "affiliate_cta"}
        forbidden_glyphs = {"✕", "✓", "▸", "→", "—"}
        for sb in storyboards:
            data = json.loads(sb.read_text(encoding="utf-8"))
            self.assertTrue(required_keys.issubset(data.keys()), f"Missing keys in {sb.name}")
            self.assertGreaterEqual(len(data["scenes"]), 3, f"Too few scenes in {sb.name}")
            has_source = any(bool(sc.get("source")) for sc in data["scenes"])
            self.assertTrue(has_source, f"Expected at least one research source citation in {sb.name}")
            for sc in data["scenes"]:
                card_blob = json.dumps(sc, ensure_ascii=False)
                for bad in forbidden_glyphs:
                    self.assertNotIn(bad, card_blob, f"Forbidden glyph {bad!r} found in {sb.name}")

    def test_trend_radar_intelligence_112_scripts(self) -> None:
        from yt_studio.trend_radar import build_trend_intelligence_report, score_topic_opportunity

        report = build_trend_intelligence_report(live_query="kelly criterion wealth")
        self.assertEqual(report["cluster_count"], 8)
        self.assertEqual(report["total_mapped_scripts"], 112)
        mapped_flat = [s for c in report["clusters"] for s in c["mapped_scripts"]]
        self.assertEqual(len(set(mapped_flat)), 112, "Duplicate or missing mapped script in trend_radar.py")
        scored = score_topic_opportunity("coase solo ai business wealth")
        self.assertGreaterEqual(scored["opportunity_score"], 85)
        self.assertIn("$", scored["estimated_rpm_usd"])

    def test_digital_products_and_youtube_autopilot_ready(self) -> None:
        self.assertTrue((PROJECT_ROOT / "products" / "5_hour_asset_builder_os" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "bio_funnel_page" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "free_lead_magnet" / "Wealth_and_Leverage_Playbook.md").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "youtube_autopilot_guide.md").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "real_world_events_dossier.md").is_file())
        self.assertTrue((PROJECT_ROOT / "web_studio" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "studio_server.py").is_file())

        next_sb = pick_next_unpublished_storyboard()
        self.assertIsNotNone(next_sb)
        sample_data = json.loads(next_sb.read_text(encoding="utf-8"))
        desc = build_youtube_description(sample_data, slug=next_sb.stem)
        self.assertIn("As an Amazon Associate I earn from qualifying purchases.", desc)
        self.assertIn("https://kenvh0010-lang.github.io/admin/bio/", desc)

    def test_subtitle_beats_and_srt(self) -> None:
        narration = "Nearly half of people earning six figures still live paycheck to paycheck. Here is why."
        dur = estimate_speech_duration(narration)
        beats = build_scene_beats(0, narration, scene_start_sec=0.0, scene_duration_sec=dur, max_words=6)
        self.assertGreaterEqual(len(beats), 2)
        self.assertAlmostEqual(beats[-1].end_sec, dur, places=2)

        with tempfile.TemporaryDirectory() as tmp:
            srt = export_srt(beats, Path(tmp) / "test.srt")
            content = srt.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 -->", content)
            self.assertIn("paycheck", content)

    def test_visual_and_audio_generators(self) -> None:
        scene = {
            "tag": "HOOK",
            "headline": "Test Visual Card",
            "visual_type": "compounding_curve",
            "stat_label": "COMPOUNDING CURVE",
            "highlight_words": ["leverage"],
            "narration": "Testing leverage frame rendering.",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame = render_scene_beat_frame(
                scene=scene,
                caption_text="Testing leverage frame rendering.",
                scene_idx=0,
                total_scenes=3,
                progress_ratio=0.33,
                fmt=FORMATS["short"],
                output_png=tmp_path / "frame.png",
            )
            thumb = render_thumbnail(
                hook_text="THE TIME TRAP",
                sub_badge="WEALTH",
                stat_highlight="10X",
                output_png=tmp_path / "thumb.png",
            )
            ambient = generate_ambient_bed(tmp_path / "ambient.wav", duration_sec=1.5)
            self.assertGreater(frame.stat().st_size, 5_000)
            self.assertGreater(thumb.stat().st_size, 5_000)
            self.assertGreater(ambient.stat().st_size, 20_000)

    def test_no_visual_card_or_source_clipping_across_112_storyboards(self) -> None:
        from PIL import Image, ImageDraw
        from yt_studio.visual_composer import _load_font, _wrap_text

        img = Image.new("RGB", (1920, 1920))
        draw = ImageDraw.Draw(img)
        for sb in sorted(p for p in CONTENT_DIR.glob("*.json") if p.name != "published_ledger.json"):
            data = json.loads(sb.read_text(encoding="utf-8"))
            is_vert = data.get("format", "short") == "short"
            w = 1080 if is_vert else 1920
            pad_x = int(w * (0.075 if is_vert else 0.06))
            cw = (w - pad_x - 40) - (pad_x + 40)
            max_src_w = w - 2 * pad_x - 16

            for s_idx, sc in enumerate(data["scenes"]):
                if sc.get("visual_type", "stat_callout") == "stat_callout":
                    stat_val = str(sc.get("stat_value", "1%"))
                    big_size = 196 if is_vert else 144
                    big_font = _load_font(big_size, bold=True)
                    while big_size > 64:
                        vb = draw.textbbox((0, 0), stat_val, font=big_font)
                        if (vb[2] - vb[0]) <= cw - 32:
                            break
                        big_size -= 8
                        big_font = _load_font(big_size, bold=True)
                    vb = draw.textbbox((0, 0), stat_val, font=big_font)
                    self.assertLessEqual(
                        vb[2] - vb[0], cw - 16,
                        f"Stat value {stat_val!r} clips card in {sb.name} scene {s_idx}",
                    )
                if sc.get("source"):
                    src_text = f"Source: {sc['source']}"
                    src_size = 25 if is_vert else 21
                    src_font = _load_font(src_size, bold=False)
                    while src_size > 17:
                        sbx = draw.textbbox((0, 0), src_text, font=src_font)
                        if (sbx[2] - sbx[0]) <= max_src_w:
                            break
                        src_size -= 2
                        src_font = _load_font(src_size, bold=False)
                    for sln in _wrap_text(draw, src_text, src_font, max_src_w)[:2]:
                        lbx = draw.textbbox((0, 0), sln, font=src_font)
                        self.assertLessEqual(
                            lbx[2] - lbx[0], max_src_w + 4,
                            f"Source line {sln!r} clips frame in {sb.name} scene {s_idx}",
                        )

    def test_calendar_csv_and_amazon_tag_sync(self) -> None:
        self.assertEqual(DEFAULT_AMAZON_TAG, "mindandmarg06-20")
        # Lịch CSV cố định đã bỏ cùng thư viện cũ; nếu có lịch mới thì mọi tiêu đề phải khớp kịch bản.
        sb_titles = {
            json.loads(p.read_text(encoding="utf-8"))["title"]
            for p in CONTENT_DIR.glob("*.json")
            if p.name != "published_ledger.json"
        }
        for csv_path in CONTENT_DIR.glob("calendar_*.csv"):
            for row in csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()):
                title = row["Video Title (English - High RPM)"]
                self.assertIn(title, sb_titles, f"Unmatched calendar title {title!r} in {csv_path.name}")


if __name__ == "__main__":
    unittest.main()
