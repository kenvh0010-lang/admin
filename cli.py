#!/usr/bin/env python3
"""Mind & Margin — Command-Line Studio for Automated Faceless YouTube Production."""

import argparse
import sys
from pathlib import Path

from concurrent.futures import ProcessPoolExecutor, as_completed
import json

from yt_studio.config import OUTPUT_DIR, PROJECT_ROOT, discover_storyboards
from yt_studio.script_generator import generate_storyboard_json
from yt_studio.trend_radar import build_trend_intelligence_report, export_trend_report_markdown
from yt_studio.video_renderer import render_project
from yt_studio.visual_composer import render_thumbnail


def _render_worker(args_tuple):
    sb_str, out_str, tts_provider, voice, skip_existing, encoder = args_tuple
    sb = Path(sb_str)
    outputs = render_project(
        storyboard_path=sb,
        output_dir=Path(out_str),
        tts_provider=tts_provider,
        voice=voice,
        skip_existing=skip_existing,
        encoder=encoder,
    )
    return sb.name, str(outputs["video"]), _render_note(outputs)


def _render_note(outputs) -> str:
    tts = str(outputs.get("tts_used", ""))
    note = f"voice={tts} | encoder={outputs.get('encoder', '?')}"
    if tts.startswith("offline-preview"):
        note += "  <-- SILENT: no voiceover (install edge-tts)"
    return note


def cmd_render(args: argparse.Namespace) -> int:
    storyboard = Path(args.storyboard).resolve()
    out_dir = Path(args.out).resolve()
    print(f"🎬 Rendering storyboard: {storyboard.name} -> {out_dir}")
    outputs = render_project(
        storyboard_path=storyboard,
        output_dir=out_dir,
        tts_provider=args.tts,
        voice=args.voice,
        skip_existing=bool(getattr(args, "skip_existing", False)),
        encoder=args.encoder,
    )
    print(f"✅ Production complete! ({_render_note(outputs)})")
    for key, path in outputs.items():
        print(f"   • {key:10s}: {path}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    folder = Path(args.folder).resolve()
    out_dir = Path(args.out).resolve()
    files = discover_storyboards(folder)
    if not files:
        print(f"No .json storyboards found in {folder}", file=sys.stderr)
        return 1
    workers = max(1, int(args.workers))
    skip_existing = bool(getattr(args, "skip_existing", False))
    print(f"🚀 Batch rendering {len(files)} storyboards from {folder} (workers={workers}, skip_existing={skip_existing})...")
    if workers == 1:
        for sb in files:
            print(f"\n--- [{sb.name}] ---")
            outputs = render_project(
                storyboard_path=sb,
                output_dir=out_dir,
                tts_provider=args.tts,
                voice=args.voice,
                skip_existing=skip_existing,
                encoder=args.encoder,
            )
            print(f"   ✓ Video: {outputs['video']} ({_render_note(outputs)})")
    else:
        tasks = [(str(sb), str(out_dir), args.tts, args.voice, skip_existing, args.encoder) for sb in files]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_render_worker, t): t[0] for t in tasks}
            done_count = 0
            for fut in as_completed(futs):
                sb_name, vid_path, note = fut.result()
                done_count += 1
                print(f"   [{done_count:02d}/{len(files):02d}] ✓ {sb_name} -> {vid_path} ({note})")
    print("\n🎉 Batch production finished!")
    return 0


def cmd_script(args: argparse.Namespace) -> int:
    out_json = Path(args.out).resolve()
    try:
        saved = generate_storyboard_json(
            topic=args.topic,
            output_json=out_json,
            fmt=args.format,
            affiliate_offer=args.affiliate,
        )
        print(f"✅ AI Storyboard saved to: {saved}")
        return 0
    except EnvironmentError as exc:
        print(f"ℹ️  {exc}")
        return 0


def cmd_thumbnail(args: argparse.Namespace) -> int:
    out_png = Path(args.out).resolve()
    bg = Path(args.bg).resolve() if args.bg else None
    saved = render_thumbnail(
        hook_text=args.hook,
        sub_badge=args.badge,
        stat_highlight=args.stat,
        output_png=out_png,
        bg_image=bg,
    )
    print(f"✅ Thumbnail saved to: {saved}")
    return 0


def cmd_trends(args: argparse.Namespace) -> int:
    report = build_trend_intelligence_report(live_query=args.query)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"🔥 {report['channel']} — {report['updated_for']}")
        print(f"   Clusters: {report['cluster_count']} | Mapped Scripts in Vault: {report['total_mapped_scripts']}\n")
        for idx, c in enumerate(report["clusters"], start=1):
            print(f"  [{idx}] {c['cluster_name']} ({c['cpm_range_usd']} CPM | {c['demand_velocity']})")
            print(f"      VN: {c['vi_name']}")
            print(f"      Scripts ({len(c['mapped_scripts'])}): {', '.join(c['mapped_scripts'][:4])} ...")
        if report["live_suggestions"]:
            print(f"\n🔎 Live Keyword Opportunities for '{args.query}':")
            for item in report["live_suggestions"]:
                print(
                    f"   • [{item['opportunity_score']}/99] {item['keyword']} "
                    f"-> Est RPM {item['estimated_rpm_usd']} | {item['day1_monetization']}"
                )
    if args.export_md:
        md_path = export_trend_report_markdown(Path(args.export_md).resolve())
        print(f"\n📄 Exported Trend Report Markdown to: {md_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mind & Margin — Automated Faceless YouTube Video & SEO Studio"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render", help="Render a single storyboard JSON into MP4 + SRT + Thumbnail + SEO Pack")
    p_render.add_argument("storyboard", help="Path to storyboard .json file")
    p_render.add_argument("--out", default=str(OUTPUT_DIR), help="Output directory (default: ./output)")
    p_render.add_argument("--tts", default="auto", choices=["auto", "edge", "openai", "elevenlabs", "offline"], help="TTS provider")
    p_render.add_argument("--voice", default="en_authoritative", help="Voice preset or Edge-TTS voice ID")
    p_render.add_argument("--skip-existing", action="store_true", help="Skip re-encoding when cached MP4 matches storyboard signature")
    p_render.add_argument("--encoder", default="auto", choices=["auto", "libx264", "h264_nvenc"], help="Video encoder: auto picks h264_nvenc on a working NVIDIA RTX GPU, else libx264")
    p_render.set_defaults(func=cmd_render)

    p_batch = sub.add_parser("batch", help="Batch render all storyboard .json files in a directory")
    p_batch.add_argument("folder", help="Directory containing .json storyboards")
    p_batch.add_argument("--out", default=str(OUTPUT_DIR), help="Output directory")
    p_batch.add_argument("--tts", default="auto", choices=["auto", "edge", "openai", "elevenlabs", "offline"])
    p_batch.add_argument("--voice", default="en_authoritative")
    p_batch.add_argument("--workers", type=int, default=4, help="Parallel worker processes (default: 4)")
    p_batch.add_argument("--skip-existing", action="store_true", help="Skip re-encoding unchanged storyboards")
    p_batch.add_argument("--encoder", default="auto", choices=["auto", "libx264", "h264_nvenc"], help="Video encoder: auto picks h264_nvenc on a working NVIDIA RTX GPU, else libx264")
    p_batch.set_defaults(func=cmd_batch)

    p_script = sub.add_parser("script", help="Generate a storyboard JSON from a topic (or export a $0 LLM prompt)")
    p_script.add_argument("--topic", required=True, help="Video topic or hook idea")
    p_script.add_argument("--format", default="short", choices=["short", "long"], help="Video format (9:16 short or 16:9 long)")
    p_script.add_argument("--affiliate", default="Audible Free Audiobook Trial + Notion Wealth System", help="Affiliate offer")
    p_script.add_argument("--out", required=True, help="Output storyboard .json path")
    p_script.set_defaults(func=cmd_script)

    p_thumb = sub.add_parser("thumbnail", help="Generate a 1280x720 high-CTR YouTube thumbnail")
    p_thumb.add_argument("--hook", required=True, help="3-5 word giant hook text")
    p_thumb.add_argument("--badge", default="WEALTH PSYCHOLOGY", help="Top category badge")
    p_thumb.add_argument("--stat", default="10X", help="Right-side big metric")
    p_thumb.add_argument("--bg", default=None, help="Optional background image path")
    p_thumb.add_argument("--out", default=str(OUTPUT_DIR / "custom_thumbnail.png"), help="Output PNG path")
    p_thumb.set_defaults(func=cmd_thumbnail)

    p_trends = sub.add_parser("trends", help="Explore high-RPM 2026 YouTube trend clusters & live keyword opportunities")
    p_trends.add_argument("--query", default=None, help="Optional seed keyword to mine live YouTube search suggestions")
    p_trends.add_argument("--json", action="store_true", help="Output raw JSON")
    p_trends.add_argument("--export-md", default=None, help="Optional path to export bilingual Markdown report")
    p_trends.set_defaults(func=cmd_trends)

    p_site = sub.add_parser("build-site", help="Rebuild docs/ public website, sitemap.xml & optionally inject Amazon Associate tag")
    p_site.add_argument("--amazon-tag", default=None, help="Amazon Associate tag (e.g., mindandmargin-20)")
    p_site.set_defaults(func=cmd_build_site)

    p_pub = sub.add_parser("publish-next", help="Auto-upload the next scheduled video in queue to YouTube Data API v3")
    p_pub.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    p_pub.set_defaults(func=cmd_publish_next)

    p_ver = sub.add_parser("verify-youtube", help="Verify YouTube OAuth2 secrets and print connected channel info")
    p_ver.set_defaults(func=cmd_verify_youtube)

    p_ded = sub.add_parser("dedupe", help="Audit all projects for duplicate titles/URLs/crops & prune orphaned outputs/assets")
    p_ded.add_argument("--apply", action="store_true", help="Remove orphaned output/ dirs and unreferenced evidence PNGs")
    p_ded.add_argument("--json", action="store_true", help="Print JSON report")
    p_ded.set_defaults(func=cmd_dedupe)

    args = parser.parse_args()
    return args.func(args)


def cmd_build_site(args: argparse.Namespace) -> int:
    from yt_studio.site_builder import build_public_site
    docs_path = build_public_site(amazon_tag=args.amazon_tag)
    print(f"✅ Public website + sitemap.xml rebuilt at: {docs_path}")
    return 0


def cmd_publish_next(args: argparse.Namespace) -> int:
    from yt_studio.youtube_uploader import publish_next_in_queue
    publish_next_in_queue(privacy_status=args.privacy)
    return 0


def cmd_verify_youtube(args: argparse.Namespace) -> int:
    from yt_studio.youtube_uploader import verify_youtube_channel
    info = verify_youtube_channel()
    return 0 if info else 1


def cmd_dedupe(args: argparse.Namespace) -> int:
    from yt_studio.deduper import audit_and_dedupe_projects
    report = audit_and_dedupe_projects(apply_cleanup=bool(args.apply))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "✅ CLEAN" if report["is_clean"] else "⚠️ ISSUES FOUND"
        print(
            f"{status} — Active Projects: {report['active_projects']} | "
            f"Referenced Exhibits: {report['referenced_evidence_files']}"
        )
        for key in (
            "duplicate_stems",
            "duplicate_titles",
            "duplicate_source_urls",
            "duplicate_scene_crops",
            "high_similarity_pairs",
            "orphaned_outputs",
            "unreferenced_evidence",
            "duplicate_asset_binaries",
            "removed_outputs",
            "removed_evidence",
        ):
            if report[key]:
                print(f"  • {key}: {report[key]}")
    return 0 if report["is_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
