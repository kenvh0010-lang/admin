"""End-to-end QA tests across Content, Monetization, Visual, Audio, and Web Studio departments."""

import json
from pathlib import Path
import tempfile
import unittest

from yt_studio.config import CONTENT_DIR, FORMATS, PROJECT_ROOT, resolve_font_path
from yt_studio.subtitle_maker import build_scene_beats, export_srt
from yt_studio.tts_engine import estimate_speech_duration, generate_ambient_bed
from yt_studio.visual_composer import render_scene_beat_frame, render_thumbnail


class TestYouTubeStudioEcosystem(unittest.TestCase):
    def test_font_resolution(self) -> None:
        self.assertTrue(Path(resolve_font_path(bold=True)).is_file())
        self.assertTrue(Path(resolve_font_path(bold=False)).is_file())

    def test_all_48_q1_storyboards_valid_and_glyph_safe(self) -> None:
        storyboards = sorted(
            p for p in CONTENT_DIR.glob("*.json") if p.name != "published_ledger.json"
        )
        self.assertEqual(len(storyboards), 48, "Expected all 48 Quarter-1 storyboards (36 Shorts + 12 Longs) in content/")
        required_keys = {"title", "format", "scenes", "tags", "thumbnail", "affiliate_cta"}
        forbidden_glyphs = {"✕", "✓", "▸", "→"}
        for sb in storyboards:
            data = json.loads(sb.read_text(encoding="utf-8"))
            self.assertTrue(required_keys.issubset(data.keys()), f"Missing keys in {sb.name}")
            self.assertGreaterEqual(len(data["scenes"]), 3, f"Too few scenes in {sb.name}")
            for sc in data["scenes"]:
                card_blob = json.dumps(sc, ensure_ascii=False)
                for bad in forbidden_glyphs:
                    self.assertNotIn(bad, card_blob, f"Forbidden glyph {bad!r} found in {sb.name}")

    def test_trend_radar_intelligence(self) -> None:
        from yt_studio.trend_radar import build_trend_intelligence_report, score_topic_opportunity
        report = build_trend_intelligence_report(live_query="mental accounting")
        self.assertEqual(report["cluster_count"], 5)
        self.assertEqual(report["total_mapped_scripts"], 48)
        scored = score_topic_opportunity("one person ai business wealth")
        self.assertGreaterEqual(scored["opportunity_score"], 85)
        self.assertIn("$", scored["estimated_rpm_usd"])

    def test_digital_products_and_branding_present(self) -> None:
        self.assertTrue((PROJECT_ROOT / "products" / "5_hour_asset_builder_os" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "bio_funnel_page" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "free_lead_magnet" / "Wealth_and_Leverage_Playbook.md").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "monetization_ops_guide.md").is_file())
        self.assertTrue((PROJECT_ROOT / "web_studio" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "studio_server.py").is_file())
        self.assertEqual(len(list((PROJECT_ROOT / "assets" / "thumbnails").glob("*.jpg"))), 4)

    def test_subtitle_beats_and_srt(self) -> None:
        narration = "Sixty-two percent of people earning six figures still live paycheck to paycheck. Here is why."
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


if __name__ == "__main__":
    unittest.main()
