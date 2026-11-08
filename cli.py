#!/usr/bin/env python3
"""Mind & Margin — Command-Line Studio for Automated Faceless YouTube Production."""

import argparse
import sys
from pathlib import Path

from yt_studio.config import OUTPUT_DIR
from yt_studio.script_generator import generate_storyboard_json
from yt_studio.video_renderer import render_project
from yt_studio.visual_composer import render_thumbnail


def cmd_render(args: argparse.Namespace) -> int:
    storyboard = Path(args.storyboard).resolve()
    out_dir = Path(args.out).resolve()
    print(f"🎬 Rendering storyboard: {storyboard.name} -> {out_dir}")
    outputs = render_project(
        storyboard_path=storyboard,
        output_dir=out_dir,
        tts_provider=args.tts,
        voice=args.voice,
    )
    print("✅ Production complete!")
    for key, path in outputs.items():
        print(f"   • {key:10s}: {path}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    folder = Path(args.folder).resolve()
    out_dir = Path(args.out).resolve()
    files = sorted(folder.glob("*.json"))
    if not files:
        print(f"No .json storyboards found in {folder}", file=sys.stderr)
        return 1
    print(f"🚀 Batch rendering {len(files)} storyboards from {folder}...")
    for sb in files:
        print(f"\n--- [{sb.name}] ---")
        outputs = render_project(
            storyboard_path=sb,
            output_dir=out_dir,
            tts_provider=args.tts,
            voice=args.voice,
        )
        print(f"   ✓ Video: {outputs['video']}")
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
    p_render.set_defaults(func=cmd_render)

    p_batch = sub.add_parser("batch", help="Batch render all storyboard .json files in a directory")
    p_batch.add_argument("folder", help="Directory containing .json storyboards")
    p_batch.add_argument("--out", default=str(OUTPUT_DIR), help="Output directory")
    p_batch.add_argument("--tts", default="auto", choices=["auto", "edge", "openai", "elevenlabs", "offline"])
    p_batch.add_argument("--voice", default="en_authoritative")
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

    p_site = sub.add_parser("build-site", help="Rebuild docs/ public website, sitemap.xml & optionally inject Amazon Associate tag")
    p_site.add_argument("--amazon-tag", default=None, help="Amazon Associate tag (e.g., mindandmargin-20)")
    p_site.set_defaults(func=cmd_build_site)

    p_pub = sub.add_parser("publish-next", help="Auto-upload the next scheduled video in queue to YouTube Data API v3")
    p_pub.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    p_pub.set_defaults(func=cmd_publish_next)

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


if __name__ == "__main__":
    raise SystemExit(main())
