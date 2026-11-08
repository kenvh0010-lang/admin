"""End-to-end QA tests across Evidence-Based Storyboards, Exhibits, Monetization, Visual, Audio, Autopilot & Web Studio."""

import csv
import json
import os
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from yt_studio.config import (
    CONTENT_DIR,
    FORMATS,
    PROJECT_ROOT,
    discover_storyboards,
    natural_sort_key,
    resolve_font_path,
)
from yt_studio.site_builder import DEFAULT_AMAZON_TAG, build_public_site
from yt_studio.subtitle_maker import build_scene_beats, export_srt
from yt_studio.tts_engine import estimate_speech_duration, generate_ambient_bed
from yt_studio.video_renderer import compute_storyboard_signature
from yt_studio.visual_composer import _load_font, _wrap_text, render_scene_beat_frame, render_thumbnail
from yt_studio.youtube_uploader import build_youtube_description, pick_next_unpublished_storyboard


class TestYouTubeStudioEcosystem(unittest.TestCase):
    def test_font_resolution_and_natural_sort(self) -> None:
        self.assertTrue(Path(resolve_font_path(bold=True)).is_file())
        self.assertTrue(Path(resolve_font_path(bold=False)).is_file())
        sample = [Path("short_10.json"), Path("short_2.json"), Path("short_100.json"), Path("short_00.json")]
        ordered = [p.name for p in sorted(sample, key=natural_sort_key)]
        self.assertEqual(ordered, ["short_00.json", "short_2.json", "short_10.json", "short_100.json"])

    def test_drafts_folder_never_enters_publish_queue(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drafts").mkdir()
            (root / "drafts" / "draft_x.json").write_text("{}", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "short_09.json").write_text("{}", encoding="utf-8")
            (root / "short_01.json").write_text("{}", encoding="utf-8")
            self.assertEqual([p.name for p in discover_storyboards(root)], ["short_01.json", "short_09.json"])

    def test_all_evidence_storyboards_valid_cited_and_glyph_safe(self) -> None:
        storyboards = discover_storyboards(CONTENT_DIR)
        # 09/11/2026: batch_02_ai_earn moved to archive/ (off-format), 5 news shorts remain in the queue.
        self.assertGreaterEqual(len(storyboards), 5, "Expected at least 5 evidence-based storyboards in content/**")
        self.assertEqual(
            len({p.stem for p in storyboards}),
            len(storyboards),
            "Storyboard stems must be unique across content/ subdirectories",
        )
        required_keys = {"title", "format", "scenes", "tags", "thumbnail", "affiliate_cta", "sources"}
        forbidden_glyphs = {"✕", "✓", "▸", "→", "—", "–"}
        for sb in storyboards:
            data = json.loads(sb.read_text(encoding="utf-8"))
            self.assertTrue(required_keys.issubset(data.keys()), f"Missing keys in {sb.name}")
            self.assertGreaterEqual(len(data["scenes"]), 4, f"Too few scenes in {sb.name}")
            self.assertGreaterEqual(len(data["sources"]), 2, f"Expected >=2 primary source URLs in {sb.name}")
            for src_entry in data["sources"]:
                self.assertTrue(src_entry.get("label"), f"Empty source label in {sb.name}")
                self.assertTrue(
                    str(src_entry.get("url", "")).startswith("https://"),
                    f"Non-HTTPS source URL in {sb.name}: {src_entry}",
                )

            ev_scene_count = 0
            for s_idx, sc in enumerate(data["scenes"]):
                self.assertTrue(bool(sc.get("source")), f"Missing scene source in {sb.name} scene {s_idx}")
                card_blob = json.dumps(sc, ensure_ascii=False)
                for bad in forbidden_glyphs:
                    self.assertNotIn(bad, card_blob, f"Forbidden glyph {bad!r} found in {sb.name}")

                if sc.get("visual_type") == "evidence_image":
                    ev_scene_count += 1
                    ev_rel = sc.get("evidence_image", "")
                    ev_file = PROJECT_ROOT / ev_rel
                    self.assertTrue(ev_file.is_file(), f"Missing evidence screenshot {ev_rel!r} in {sb.name}")
                    with Image.open(ev_file) as im:
                        w, h = im.size
                    crop = sc.get("evidence_crop")
                    self.assertIsInstance(crop, list, f"Missing evidence_crop in {sb.name} scene {s_idx}")
                    self.assertEqual(len(crop), 4, f"Invalid evidence_crop length in {sb.name} scene {s_idx}")
                    x1, y1, x2, y2 = crop
                    self.assertTrue(
                        0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h,
                        f"Out-of-bounds crop {crop} for {w}x{h} image {ev_rel} in {sb.name}",
                    )
            self.assertGreaterEqual(ev_scene_count, 3, f"Expected >=3 evidence_image scenes in {sb.name}")

    def test_evidence_frame_renders_outside_repo_cwd_and_signature_tracks_changes(self) -> None:
        sb = CONTENT_DIR / "short_01_ftc_cleo_ai_refunds.json"
        data = json.loads(sb.read_text(encoding="utf-8"))
        orig_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                os.chdir(tmp_path)
                out_png = render_scene_beat_frame(
                    scene=data["scenes"][0],
                    caption_text="Over 2.1 million people",
                    scene_idx=0,
                    total_scenes=len(data["scenes"]),
                    progress_ratio=0.2,
                    fmt=FORMATS["short"],
                    output_png=tmp_path / "ev_frame.png",
                )
                self.assertGreater(out_png.stat().st_size, 50_000)
            finally:
                os.chdir(orig_cwd)

            sb_copy = tmp_path / "copy.json"
            sb_copy.write_text(json.dumps(data), encoding="utf-8")
            sig1 = compute_storyboard_signature(sb_copy)
            data["scenes"][0]["evidence_crop"][1] += 5
            sb_copy.write_text(json.dumps(data), encoding="utf-8")
            sig2 = compute_storyboard_signature(sb_copy)
            self.assertNotEqual(sig1, sig2)

    def test_trend_radar_intelligence_engine(self) -> None:
        from yt_studio.trend_radar import build_trend_intelligence_report, score_topic_opportunity

        report = build_trend_intelligence_report(live_query="kelly criterion wealth")
        self.assertEqual(report["cluster_count"], 8)
        scored = score_topic_opportunity("coase solo ai business wealth")
        self.assertGreaterEqual(scored["opportunity_score"], 85)
        self.assertIn("$", scored["estimated_rpm_usd"])

    def test_digital_products_public_site_and_youtube_autopilot_ready(self) -> None:
        import studio_server

        self.assertTrue((PROJECT_ROOT / "products" / "5_hour_asset_builder_os" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "bio_funnel_page" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "free_lead_magnet" / "Wealth_and_Leverage_Playbook.md").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "youtube_autopilot_guide.md").is_file())
        self.assertTrue((PROJECT_ROOT / "products" / "real_world_events_dossier.md").is_file())
        self.assertTrue((PROJECT_ROOT / "web_studio" / "index.html").is_file())
        self.assertTrue((PROJECT_ROOT / "studio_server.py").is_file())

        docs_dir = build_public_site(amazon_tag=DEFAULT_AMAZON_TAG)
        self.assertTrue((docs_dir / "dossier.html").is_file())
        self.assertTrue((docs_dir / "assets" / "evidence" / "citibank" / "sdny_flexcube_p13.png").is_file())
        self.assertTrue((docs_dir / "articles" / "short_00_suno_ai_lawsuit.html").is_file())
        citi_article = (docs_dir / "articles" / "short_03_citibank_900m_wire_blunder.html").read_text(encoding="utf-8")
        self.assertIn("Verified Primary Sources", citi_article)
        self.assertIn("sdny_flexcube_p13.png", citi_article)
        self.assertIn("As an Amazon Associate I earn from qualifying purchases.", citi_article)

        dash = studio_server.build_dashboard_payload()
        self.assertGreaterEqual(dash["stats"]["total_scripts"], 5)
        self.assertGreaterEqual(dash["stats"]["short_count"], 5)

        next_sb = pick_next_unpublished_storyboard()
        self.assertIsNotNone(next_sb)
        sample_data = json.loads(next_sb.read_text(encoding="utf-8"))
        desc = build_youtube_description(sample_data, slug=next_sb.stem)
        self.assertIn("As an Amazon Associate I earn from qualifying purchases.", desc)
        self.assertIn("Sources:", desc)
        self.assertIn("https://kenvh0010-lang.github.io/admin/bio/", desc)

    def test_subtitle_beats_and_srt(self) -> None:
        narration = "Nearly half of people earning six figures still live paycheck to paycheck. Look at the numbers."
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

    def test_no_visual_card_or_source_clipping_across_storyboards(self) -> None:
        img = Image.new("RGB", (1920, 1920))
        draw = ImageDraw.Draw(img)
        for sb in discover_storyboards(CONTENT_DIR):
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
        sb_titles = {
            json.loads(p.read_text(encoding="utf-8"))["title"]
            for p in discover_storyboards(CONTENT_DIR)
        }
        for csv_path in CONTENT_DIR.glob("calendar_*.csv"):
            for row in csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()):
                title = row["Video Title (English - High RPM)"]
                self.assertIn(title, sb_titles, f"Unmatched calendar title {title!r} in {csv_path.name}")


if __name__ == "__main__":
    unittest.main()
