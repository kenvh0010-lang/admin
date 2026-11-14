"""End-to-end QA tests across Evidence-Based Storyboards, Exhibits, Monetization, Visual, Audio, Autopilot & Web Studio."""

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave

from PIL import Image, ImageDraw, ImageStat

from yt_studio.config import (
    CONTENT_DIR,
    FORMATS,
    PROJECT_ROOT,
    discover_storyboards,
    natural_sort_key,
    resolve_font_path,
)
from yt_studio.site_builder import DEFAULT_AMAZON_TAG, build_public_site
from yt_studio.storyboard_validator import validate_storyboard
from yt_studio.subtitle_maker import build_scene_beats, export_srt, split_into_beats
from yt_studio.tts_engine import estimate_speech_duration, generate_ambient_bed, generate_scene_sfx_track
from yt_studio.video_renderer import _render_motion_clip, compute_storyboard_signature
from yt_studio.visual_composer import (
    _load_font,
    _wrap_text,
    compute_card_inner_box,
    render_scene_beat_frame,
    render_scene_exhibit_canvas,
    render_thumbnail,
)
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
        # 11 active news shorts in content/ (1 published + 10 queued for daily autopilot; batch_02_ai_earn archived).
        self.assertGreaterEqual(len(storyboards), 11, "Expected at least 11 evidence-based storyboards in content/**")
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
            self.assertEqual(data.get("format"), "short", f"Active queue must stay 100% pure News-Shorts: {sb.name}")
            yt_desc = build_youtube_description(data, slug=sb.stem)
            for bracket in ("<", ">"):
                self.assertNotIn(bracket, data["title"], f"Forbidden YouTube bracket {bracket!r} in title of {sb.name}")
                self.assertNotIn(bracket, yt_desc, f"Forbidden YouTube bracket {bracket!r} in description of {sb.name}")
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
        self.assertTrue((docs_dir / "articles" / "short_05_uber_one_23_screen_cancel.html").is_file())
        self.assertTrue((docs_dir / "articles" / "short_10_cash_app_175m_cfpb_order.html").is_file())
        citi_article = (docs_dir / "articles" / "short_03_citibank_900m_wire_blunder.html").read_text(encoding="utf-8")
        self.assertIn("Verified Primary Sources", citi_article)
        self.assertIn("sdny_flexcube_p13.png", citi_article)
        self.assertIn("As an Amazon Associate I earn from qualifying purchases.", citi_article)

        dash = studio_server.build_dashboard_payload()
        self.assertGreaterEqual(dash["stats"]["total_scripts"], 11)
        self.assertGreaterEqual(dash["stats"]["short_count"], 11)

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

    def test_project_deduplication_and_upload_guard(self) -> None:
        from unittest.mock import patch
        from yt_studio.deduper import audit_and_dedupe_projects

        report = audit_and_dedupe_projects(apply_cleanup=False)
        self.assertTrue(report["is_clean"], f"Deduplication audit found issues: {report}")
        self.assertEqual(report["active_projects"], 11)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sb1 = root / "short_01_alpha.json"
            sb2 = root / "short_02_renamed_dup.json"
            sb3 = root / "short_03_fresh.json"
            sb1.write_text(json.dumps({"title": "Case Alpha", "sources": [{"url": "https://sec.gov/a"}]}), encoding="utf-8")
            sb2.write_text(json.dumps({"title": "Different Title", "sources": [{"url": "https://sec.gov/a/"}]}), encoding="utf-8")
            sb3.write_text(json.dumps({"title": "Case Gamma", "sources": [{"url": "https://ftc.gov/c"}]}), encoding="utf-8")
            fake_ledger = {
                "published": {
                    "short_01_old_slug": {
                        "video_id": "abc",
                        "title": "Case Alpha #Shorts",
                        "source_urls": ["https://sec.gov/a"],
                    }
                }
            }
            with patch("yt_studio.youtube_uploader.CONTENT_DIR", root), patch(
                "yt_studio.youtube_uploader.load_ledger", return_value=fake_ledger
            ):
                picked = pick_next_unpublished_storyboard()
                self.assertEqual(picked, sb3)


    def test_edge_tts_missing_fails_loudly_instead_of_silent_video(self) -> None:
        """--tts edge must raise when edge-tts is absent; auto mode warns before going silent."""
        import io
        from contextlib import redirect_stderr
        from unittest.mock import patch
        from yt_studio import tts_engine

        with tempfile.TemporaryDirectory() as td, patch.object(tts_engine, "resolve_edge_tts_command", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                tts_engine.synthesize_voice("Hello there.", Path(td) / "v", provider="edge")
            self.assertIn("pip install edge-tts", str(ctx.exception))
            err = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ELEVENLABS_API_KEY": ""}), redirect_stderr(err):
                _, _, label = tts_engine.synthesize_voice("Hello there.", Path(td) / "v2", provider="auto")
            self.assertTrue(label.startswith("offline-preview"))
            self.assertIn("SILENT", err.getvalue())

    def test_skip_existing_never_reuses_silent_offline_render(self) -> None:
        from unittest.mock import patch
        from yt_studio import video_renderer

        sb_src = sorted(CONTENT_DIR.glob("short_*.json"))[0]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            proj = out / sb_src.stem
            proj.mkdir()
            for name in (f"{sb_src.stem}.mp4", f"{sb_src.stem}.srt", f"{sb_src.stem}_thumbnail.png", "youtube_upload_pack.md"):
                (proj / name).write_bytes(b"x")
            sig = compute_storyboard_signature(sb_src, tts_provider="auto")
            manifest = proj / ".render_manifest.json"

            class _Stop(Exception):
                pass

            def _boom(*a, **k):
                raise _Stop()

            manifest.write_text(json.dumps({"signature": sig, "tts_used": "offline-preview (x)"}), encoding="utf-8")
            with patch.object(video_renderer, "select_video_encoder", side_effect=_boom):
                with self.assertRaises(_Stop):
                    video_renderer.render_project(sb_src, out, tts_provider="auto", skip_existing=True)

            manifest.write_text(json.dumps({"signature": sig, "tts_used": "edge-tts (en-US-ChristopherNeural)"}), encoding="utf-8")
            with patch.object(video_renderer, "select_video_encoder", side_effect=_boom):
                res = video_renderer.render_project(sb_src, out, tts_provider="auto", skip_existing=True)
            self.assertEqual(res["video"], proj / f"{sb_src.stem}.mp4")

    def test_video_encoder_selection_falls_back_to_libx264(self) -> None:
        from unittest.mock import patch
        from yt_studio import video_renderer

        video_renderer._ENCODER_CACHE.clear()
        with patch.object(video_renderer, "_ffmpeg_lists_encoder", return_value=True), patch.object(
            video_renderer, "_nvenc_probe_ok", return_value=False
        ):
            self.assertEqual(video_renderer.select_video_encoder("auto"), "libx264")
        video_renderer._ENCODER_CACHE.clear()
        with patch.object(video_renderer, "_ffmpeg_lists_encoder", return_value=True), patch.object(
            video_renderer, "_nvenc_probe_ok", return_value=True
        ):
            self.assertEqual(video_renderer.select_video_encoder("auto"), "h264_nvenc")
            self.assertEqual(video_renderer.select_video_encoder("libx264"), "libx264")
        video_renderer._ENCODER_CACHE.clear()
        args = video_renderer._encoder_args("h264_nvenc")
        self.assertIn("-cq", args)
        self.assertIn("yuv420p", args)

    def test_brand_skill_stays_in_sync_with_code(self) -> None:
        """The project brand skill must list the exact hex values used by video and site."""
        import re
        from yt_studio.config import DEFAULT_THEME

        skill = (PROJECT_ROOT / ".claude" / "skills" / "mind-margin-brand" / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: mind-margin-brand\n"))
        skill_hex = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", skill)}
        for field_name in ("bg_primary", "bg_card", "grid_line", "accent_gold", "accent_cyan",
                           "accent_crimson", "text_primary", "text_muted"):
            rgb = getattr(DEFAULT_THEME, field_name)
            self.assertIn("#%02X%02X%02X" % rgb, skill_hex, f"{field_name} missing from brand skill")
        site_src = (PROJECT_ROOT / "yt_studio" / "site_builder.py").read_text(encoding="utf-8")
        for var, hx in re.findall(r"--(bg|card|border|gold|cyan|muted|text):(#[0-9A-Fa-f]{6})", site_src):
            self.assertIn(hx.upper(), skill_hex, f"site --{var} missing from brand skill")
        self.assertIn("mindandmarg06-20", skill)
        self.assertIn("As an Amazon Associate I earn from qualifying purchases.", skill)
        # Claude Code reads .claude/skills, Antigravity reads .agents/skills: both copies must match.
        ag_copy = PROJECT_ROOT / ".agents" / "skills" / "mind-margin-brand" / "SKILL.md"
        self.assertTrue(ag_copy.is_file(), "Antigravity copy of the brand skill is missing")
        self.assertEqual(ag_copy.read_text(encoding="utf-8"), skill, "Run: cp .claude/skills/mind-margin-brand/SKILL.md .agents/skills/mind-margin-brand/SKILL.md")

    def test_skill_router_hook_names_matching_skill(self) -> None:
        import subprocess
        import sys

        hook = PROJECT_ROOT / ".claude" / "hooks" / "skill_router.py"
        settings = json.loads((PROJECT_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cmd = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertIn("skill_router.py", cmd)

        def run(prompt: str) -> str:
            res = subprocess.run([sys.executable, str(hook)], input=json.dumps({"prompt": prompt, "cwd": str(PROJECT_ROOT)}),
                                 capture_output=True, text=True, timeout=20, env={**os.environ, "CLAUDE_PROJECT_DIR": str(PROJECT_ROOT)})
            self.assertEqual(res.returncode, 0)
            return json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"] if res.stdout.strip() else ""

        self.assertIn("This prompt matches: mind-margin-brand", run("làm thumbnail mới cho kênh"))
        self.assertIn("storyboard-pipeline", run("kiểm tra luồng xử lý kịch bản mới"))
        self.assertIn("vao-rtx", run("vao rtx kiểm tra gpu"))
        self.assertNotIn("This prompt matches", run("git status"))
        bad = subprocess.run([sys.executable, str(hook)], input="not json", capture_output=True, text=True, timeout=20)
        self.assertEqual((bad.returncode, bad.stdout), (0, ""))
        rule = (PROJECT_ROOT / ".agents" / "rules" / "use-skills.md").read_text(encoding="utf-8")
        for sk in (PROJECT_ROOT / ".claude" / "skills").glob("*/SKILL.md"):
            self.assertIn(sk.parent.name, rule, f"{sk.parent.name} missing from Antigravity use-skills rule")
            ag_mirror = PROJECT_ROOT / ".agents" / "skills" / sk.parent.name / "SKILL.md"
            self.assertTrue(ag_mirror.is_file(), f"Missing .agents mirror for skill {sk.parent.name}")
            self.assertEqual(
                ag_mirror.read_text(encoding="utf-8"),
                sk.read_text(encoding="utf-8"),
                f"Skill {sk.parent.name} differs between .claude/skills and .agents/skills",
            )

    def test_skill_router_covers_account_skills_and_exclusions(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("skill_router", PROJECT_ROOT / ".claude" / "hooks" / "skill_router.py")
        router = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(router)
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            synced = home / ".claude" / "skills" / "synced" / "org_x"
            for name, desc in (("pdf", "Use this skill whenever the user wants to do anything with PDF files."),
                               ("brand-guidelines", "Applies official brand colors and typography fonts."),
                               ("pptx", "Use for slide decks and presentations as PowerPoint pptx files.")):
                (synced / name).mkdir(parents=True)
                (synced / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n", encoding="utf-8")
            skills_dir = PROJECT_ROOT / ".claude" / "skills"
            self.assertIn("anthropic-skills:pdf", router.build_context("đọc file pdf đơn kiện này", skills_dir, home))
            self.assertIn("anthropic-skills:pptx", router.build_context("tạo slide trình chiếu", skills_dir, home))
            brand = router.build_context("đổi màu và font thương hiệu", skills_dir, home)
            self.assertIn("This prompt matches: mind-margin-brand", brand)
            self.assertNotIn("brand-guidelines", brand)

    def test_sync_skills_tool_copies_validates_and_is_idempotent(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("sync_skills", PROJECT_ROOT / "tools" / "sync_skills.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ag" / "pack" / "alpha").mkdir(parents=True)
            (root / "ag" / "pack" / "alpha" / "SKILL.md").write_text("---\nname: alpha\ndescription: A.\n---\n", encoding="utf-8")
            (root / "ag" / "beta" / "scripts").mkdir(parents=True)
            (root / "ag" / "beta" / "SKILL.md").write_text("---\nname: Beta Tool\ndescription: >\n  B.\n---\n", encoding="utf-8")
            (root / "ag" / "beta" / "scripts" / "run.py").write_text("print(1)\n", encoding="utf-8")
            (root / "ag" / "bad").mkdir()
            (root / "ag" / "bad" / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
            (root / "ag2" / "alpha").mkdir(parents=True)
            (root / "ag2" / "alpha" / "SKILL.md").write_text("---\nname: alpha\ndescription: Other.\n---\n", encoding="utf-8")
            dest = root / "dest"

            dry = tool.sync([root / "ag", root / "ag2"], dest, apply=False, overwrite=False)
            self.assertEqual(sorted(dry["copied"]), ["alpha", "beta-tool"])
            self.assertFalse(dest.exists(), "dry run must not write")
            self.assertEqual(len(dry["invalid"]), 1)
            self.assertEqual(len(dry["conflicts"]), 1)

            tool.sync([root / "ag"], dest, apply=True, overwrite=False)
            self.assertIn("name: beta-tool", (dest / "beta-tool" / "SKILL.md").read_text(encoding="utf-8"))
            self.assertTrue((dest / "beta-tool" / "scripts" / "run.py").is_file())
            again = tool.sync([root / "ag"], dest, apply=True, overwrite=False)
            self.assertEqual((again["copied"], sorted(again["unchanged"])), ([], ["alpha", "beta-tool"]))

    def test_all_active_storyboards_pass_7_gate_validator(self) -> None:
        from yt_studio.storyboard_validator import validate_storyboard

        storyboards = discover_storyboards(CONTENT_DIR)
        self.assertEqual(len(storyboards), 11)
        for sb in storyboards:
            report = validate_storyboard(sb)
            self.assertTrue(report["ok"], f"{sb.name} failed 7-gate validator: {report['errors']}")

    def test_storyboard_pipeline_draft_quarantine_validate_and_promote(self) -> None:
        from unittest.mock import patch
        from yt_studio.script_generator import resolve_draft_destination, scaffold_case_draft
        from yt_studio.storyboard_validator import promote_draft_to_queue, validate_storyboard

        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            cdir = proj / "content"
            odir = proj / "output"
            ev_dir = proj / "assets" / "evidence" / "cfpb_zelle"
            cdir.mkdir(parents=True)
            ev_dir.mkdir(parents=True)

            # Quarantine guard redirects content/foo.json -> content/drafts/foo.json
            quarantined = resolve_draft_destination(cdir / "short_99_raw.json", content_dir=cdir, allow_active=False)
            self.assertEqual(quarantined, (cdir / "drafts" / "short_99_raw.json").resolve())

            # Seed one existing active storyboard (short_04) to verify auto-numbering -> short_05_... and dedupe
            existing = cdir / "short_04_existing_case.json"
            existing.write_text(
                json.dumps(
                    {
                        "title": "How a Broker Triggered a $12M SEC Penalty",
                        "sources": [{"label": "SEC Order", "url": "https://www.sec.gov/litigation/admin/2025/34-99999.pdf"}],
                        "scenes": [],
                    }
                ),
                encoding="utf-8",
            )

            # Create 4 real primary exhibit PNGs on disk
            for i in range(1, 5):
                im = Image.new("RGB", (1200, 1400), color=(245, 247, 250))
                im.save(ev_dir / f"exhibit_{i:02d}.png")

            draft_json, prompt_txt = scaffold_case_draft(
                slug="cfpb_zelle_inquiry",
                topic="Why Federal Regulators Investigated $870M in Disputed Bank Transfers",
                evidence_dir=ev_dir,
                sources=[
                    ("Senate PSI Majority Staff Report PDF", "https://www.hsgac.senate.gov/wp-content/uploads/zelle-report.pdf"),
                    ("CFPB Enforcement Docket Filing", "https://www.consumerfinance.gov/enforcement/actions/zelle-2025/"),
                ],
                content_dir=cdir,
                project_root=proj,
            )
            self.assertTrue(draft_json.is_file())
            self.assertTrue(prompt_txt.is_file())
            self.assertEqual(draft_json.parent, (cdir / "drafts").resolve())
            self.assertEqual([p.name for p in discover_storyboards(cdir)], ["short_04_existing_case.json"])

            # Injecting a banned buzzword ("secretly") or duplicate source URL must block promotion
            bad_payload = json.loads(draft_json.read_text(encoding="utf-8"))
            bad_payload["title"] = "Banks Secretly Ignored $870M in App Transfers"
            bad_payload["sources"][0]["url"] = "https://www.sec.gov/litigation/admin/2025/34-99999.pdf"
            draft_json.write_text(json.dumps(bad_payload, indent=2), encoding="utf-8")

            with patch("yt_studio.storyboard_validator.load_ledger", return_value={"published": {}}):
                bad_rep = validate_storyboard(draft_json, content_dir=cdir, project_root=proj)
                self.assertFalse(bad_rep["ok"])
                joined_errs = " | ".join(bad_rep["errors"])
                self.assertIn("secretly", joined_errs)
                self.assertIn("Gate 7: Dedupe", joined_errs)
                with self.assertRaises(ValueError):
                    promote_draft_to_queue(
                        draft_json, content_dir=cdir, output_dir=odir, project_root=proj, rebuild_site=False
                    )

                # Fix copy & citations to documentary standard -> passes all 7 gates & promotes to short_05_...
                clean_payload = json.loads(draft_json.read_text(encoding="utf-8"))
                clean_payload["title"] = "Senate Report: $870M in Disputed Instant Bank App Transfers"
                clean_payload["sources"][0]["url"] = "https://www.hsgac.senate.gov/wp-content/uploads/zelle-report.pdf"
                narrations = [
                    "A Senate subcommittee report found three giant US banks reimbursed just fractionally on 870 million dollars in disputed instant transfers.",
                    "Investigators documented that customers tricked into authorizing instant bank transfers received refunds in under twelve percent of reported scam claims.",
                    "Internal bank tables in the Senate report showed hundreds of millions in disputed peer-to-peer transfers went unreturned between 2021 and 2023.",
                    "Federal regulators subsequently sued to examine how network operators handled fraud alerts across linked checking accounts.",
                    "Treat instant bank transfers like handing over physical cash: use credit cards with statutory chargeback rights whenever paying strangers.",
                ]
                headlines = [
                    "$870M in Disputed Transfers",
                    "Under 12% Refunded in Scams",
                    "Senate Subcommittee Tables",
                    "Federal Oversight Action",
                    "Use Chargeback Rails",
                ]
                for idx, sc in enumerate(clean_payload["scenes"]):
                    sc["headline"] = headlines[idx]
                    sc["narration"] = narrations[idx]
                    sc["source"] = f"U.S. Senate PSI Staff Report, p. {idx + 4} (2024)"
                draft_json.write_text(json.dumps(clean_payload, indent=2), encoding="utf-8")

                ok_rep = validate_storyboard(draft_json, content_dir=cdir, project_root=proj)
                self.assertTrue(ok_rep["ok"], f"Expected clean validation, got: {ok_rep['errors']}")

                promoted = promote_draft_to_queue(
                    draft_json, content_dir=cdir, output_dir=odir, project_root=proj, rebuild_site=False
                )
                self.assertEqual(promoted["slug"], "short_05_cfpb_zelle_inquiry")
                self.assertFalse(draft_json.exists())
                self.assertFalse(prompt_txt.exists())
                self.assertTrue((cdir / "short_05_cfpb_zelle_inquiry.json").is_file())
                self.assertTrue((odir / "short_05_cfpb_zelle_inquiry" / "short_05_cfpb_zelle_inquiry.srt").is_file())
                self.assertTrue((odir / "short_05_cfpb_zelle_inquiry" / "short_05_cfpb_zelle_inquiry_thumbnail.png").is_file())
                self.assertTrue((odir / "short_05_cfpb_zelle_inquiry" / "youtube_upload_pack.md").is_file())

    def test_tall_evidence_exhibit_never_clips_bottom_and_handle_matches_live_channel(self) -> None:
        from yt_studio.config import DEFAULT_THEME
        from yt_studio.visual_composer import _paste_evidence

        self.assertEqual(DEFAULT_THEME.channel_handle, "@MindMargin-t4k")
        bio_html = (PROJECT_ROOT / "products" / "bio_funnel_page" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("mindandmargin.gumroad.com/l/5-hour-asset-os", bio_html)

        with tempfile.TemporaryDirectory() as td:
            exhibit_path = Path(td) / "tall_exhibit.png"
            src = Image.new("RGB", (1000, 1200), color=(255, 255, 255))
            for y in range(1185, 1200):
                for x in range(100, 900):
                    src.putpixel((x, y), (255, 0, 0))
            src.save(exhibit_path)

            canvas = Image.new("RGB", (1080, 1920), color=DEFAULT_THEME.bg_primary)
            draw = ImageDraw.Draw(canvas)
            _paste_evidence(canvas, draw, exhibit_path, [0, 0, 1000, 1200], (105, 408, 975, 1204), DEFAULT_THEME)

            has_bottom_red = any(
                canvas.getpixel((px, py))[0] > 200 and canvas.getpixel((px, py))[1] < 80
                for py in range(1180, 1205)
                for px in range(450, 630, 10)
            )
            self.assertTrue(has_bottom_red, "Tall exhibit bottom stripe was clipped instead of scaled to fit card height")

    def test_legacy_video_pruner_protects_ledger_and_targets_only_productivity_videos(self) -> None:
        from yt_studio.youtube_uploader import (
            LEGACY_PRODUCTIVITY_VIDEO_IDS,
            select_legacy_videos_to_delete,
        )

        protected = {"75cTEO_NKdo", "GeEbilkyHxE", "lKDVAS6FmF4", "tkQ_qEfx1P8"}
        candidates = [
            {"id": "gPdWuLKZNY8", "title": "You're Only Productive 2h 53m a Day. Try 90-Minute Blocks"},
            {"id": "Tf9gtJWLvQ0", "title": "The Time Trap: Why Hard Work Stopped Building Wealth (And What Does)"},
            {"id": "XlS3gq6vGas", "title": "Why Hard Work Has a Ceiling (And Leverage Doesn't) #Shorts"},
            {"id": "9adaLgt-ZTQ", "title": "Why Earning More Still Keeps You Broke (The Diderot Trap) #Shorts"},
            {"id": "draft_diderot_99", "title": "Why Earning More Still Keeps You Broke (The Diderot Trap)"},
            {"id": "75cTEO_NKdo", "title": "Eminem and Elvis vs. the $5.4 Billion AI Song App #Shorts"},
            {"id": "GeEbilkyHxE", "title": "2.1 Million Cleo AI Users Are Getting FTC Refunds via PayPal #Shorts"},
            {"id": "lKDVAS6FmF4", "title": "Why Anthropic Is Paying Book Authors $1.5 Billion This Month #Shorts"},
            {"id": "tkQ_qEfx1P8", "title": "Why Earning More Still Keeps You Broke (The Diderot Trap)"},
            {"id": "new_lawsuit_01", "title": "FTC Sues Uber Over 23-Screen Cancel Maze"},
        ]
        selected = select_legacy_videos_to_delete(candidates, protected)
        selected_ids = [item["id"] for item in selected]
        self.assertEqual(selected_ids, [*LEGACY_PRODUCTIVITY_VIDEO_IDS, "draft_diderot_99"])
        for pid in protected:
            self.assertNotIn(pid, selected_ids)
        self.assertNotIn("new_lawsuit_01", selected_ids)

    def test_short_beats_balanced_two_to_three_words_without_orphan(self) -> None:
        self.assertEqual(split_into_beats("One two three four", max_words=3), ["One two", "three four"])
        seven = split_into_beats("Alpha beta gamma delta epsilon zeta eta", max_words=3)
        self.assertGreaterEqual(min(len(b.split()) for b in seven), 2)
        self.assertLessEqual(max(len(b.split()) for b in seven), 3)

        beats = build_scene_beats(0, "One two three four. Five six seven eight.", 0.0, 4.0, max_words=3)
        self.assertEqual(len(beats), 4)
        self.assertTrue(all(len(b.text.split()) == 2 for b in beats))
        self.assertAlmostEqual(beats[0].start_sec, 0.0, places=3)
        self.assertAlmostEqual(beats[-1].end_sec, 4.0, places=3)

    def test_evidence_highlight_renders_gold_band_and_validates_bounds(self) -> None:
        sb_path = CONTENT_DIR / "short_04_knight_capital_440m_sec_order.json"
        rep = validate_storyboard(sb_path, check_dedupe=True)
        self.assertTrue(rep["ok"], f"Unexpected validation errors: {rep['errors']}")
        self.assertEqual(rep["warnings"], [], f"Unexpected validation warnings: {rep['warnings']}")

        data = json.loads(sb_path.read_text(encoding="utf-8"))
        scene = dict(data["scenes"][0])
        scene_plain = {k: v for k, v in scene.items() if k != "evidence_highlight"}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            p_hl = render_scene_beat_frame(
                scene=scene,
                caption_text="Over 460 million",
                scene_idx=0,
                total_scenes=len(data["scenes"]),
                progress_ratio=0.2,
                fmt=FORMATS["short"],
                output_png=tmp_path / "hl.png",
            )
            p_plain = render_scene_beat_frame(
                scene=scene_plain,
                caption_text="Over 460 million",
                scene_idx=0,
                total_scenes=len(data["scenes"]),
                progress_ratio=0.2,
                fmt=FORMATS["short"],
                output_png=tmp_path / "plain.png",
            )
            with Image.open(p_hl) as im_hl, Image.open(p_plain) as im_plain:
                self.assertNotEqual(im_hl.tobytes(), im_plain.tobytes())

            bad = json.loads(json.dumps(data))
            bad["scenes"][0]["evidence_highlight"] = [0, 0, 500, 40]
            bad_path = tmp_path / "bad_hl.json"
            bad_path.write_text(json.dumps(bad), encoding="utf-8")
            bad_rep = validate_storyboard(bad_path, check_dedupe=False)
            self.assertFalse(bad_rep["ok"])
            self.assertTrue(any("evidence_highlight" in e for e in bad_rep["errors"]))

    def test_motion_clip_first_frame_not_black_and_sfx_track_generated(self) -> None:
        data = json.loads((CONTENT_DIR / "short_04_knight_capital_440m_sec_order.json").read_text(encoding="utf-8"))
        scene = data["scenes"][0]
        fmt = FORMATS["short"]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sfx_wav = generate_scene_sfx_track(tmp_path / "sfx.wav", [0.0, 4.0, 8.0], 10.0)
            with wave.open(str(sfx_wav), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getframerate(), 24000)
                self.assertGreater(wf.getnframes(), 200_000)
                raw = wf.readframes(wf.getnframes())
                self.assertTrue(any(b != 0 for b in raw))

            if shutil.which("ffmpeg"):
                frame_png = render_scene_beat_frame(
                    scene=scene,
                    caption_text="Over 460 million",
                    scene_idx=0,
                    total_scenes=len(data["scenes"]),
                    progress_ratio=0.2,
                    fmt=fmt,
                    output_png=tmp_path / "frame.png",
                )
                card_box = compute_card_inner_box(scene, fmt)
                self.assertIsNotNone(card_box)
                ex_png = render_scene_exhibit_canvas(scene, card_box, tmp_path / "ex.png")
                self.assertIsNotNone(ex_png)
                clip_mp4 = tmp_path / "clip.mp4"
                _render_motion_clip(
                    frame_png=frame_png,
                    out_mp4=clip_mp4,
                    duration=0.25,
                    t_offset=0.0,
                    scene_dur=4.0,
                    first_in_scene=True,
                    fmt=fmt,
                    exhibit_png=ex_png,
                    card_box=card_box,
                )
                f0_png = tmp_path / "f0.png"
                subprocess.run(
                    ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip_mp4), "-vframes", "1", str(f0_png)],
                    check=True,
                )
                with Image.open(f0_png) as im0:
                    mean_luma = ImageStat.Stat(im0.convert("L")).mean[0]
                    self.assertGreater(mean_luma, 10.0)


if __name__ == "__main__":
    unittest.main()
