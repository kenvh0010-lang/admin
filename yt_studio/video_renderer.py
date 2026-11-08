"""End-to-end FFmpeg Video Renderer + SEO Upload Pack Generator."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .config import DEFAULT_THEME, FORMATS
from .subtitle_maker import CaptionBeat, build_scene_beats, export_srt
from .tts_engine import generate_ambient_bed, synthesize_voice
from .visual_composer import render_scene_beat_frame, render_thumbnail


def render_project(
    storyboard_path: Path,
    output_dir: Path,
    tts_provider: str = "auto",
    voice: str = "en_authoritative",
) -> Dict[str, Path]:
    """
    Compile a JSON storyboard into:
      1. video.mp4 (H.264 + AAC, Shorts 9:16 or Long-form 16:9)
      2. captions.srt (synced subtitles for YouTube SEO)
      3. thumbnail.png (1280x720 high-CTR thumbnail)
      4. youtube_upload_pack.md (Titles, SEO Description, Timestamps, Affiliate Links, Tags)
    """
    data = json.loads(storyboard_path.read_text(encoding="utf-8"))
    project_slug = storyboard_path.stem
    proj_out = output_dir / project_slug
    proj_out.mkdir(parents=True, exist_ok=True)

    fmt_key = data.get("format", "short").lower()
    fmt = FORMATS.get(fmt_key, FORMATS["short"])
    scenes: List[Dict[str, Any]] = data["scenes"]
    if not scenes:
        raise ValueError("Storyboard must contain at least one scene.")

    work_dir = Path(tempfile.mkdtemp(prefix=f"yt_{project_slug}_"))
    try:
        scene_audio_files: List[Path] = []
        all_beats: List[CaptionBeat] = []
        beat_frames: List[Path] = []
        timeline_cursor = 0.0
        tts_used = ""

        # Step 1: Synthesize voiceover & compute exact beat timings per scene
        scene_durations: List[float] = []
        for idx, scene in enumerate(scenes):
            audio_file, dur, provider_label = synthesize_voice(
                text=scene["narration"],
                output_path=work_dir / f"voice_{idx:03d}",
                provider=tts_provider,
                voice=data.get("voice", voice),
            )
            tts_used = provider_label
            scene_audio_files.append(audio_file)
            scene_durations.append(dur)

        total_duration = sum(scene_durations)

        # Step 2: Build beats & render visual frames
        frame_counter = 0
        for idx, (scene, dur) in enumerate(zip(scenes, scene_durations)):
            beats = build_scene_beats(
                scene_index=idx,
                narration=scene["narration"],
                scene_start_sec=timeline_cursor,
                scene_duration_sec=dur,
                max_words=6 if fmt.is_vertical else 9,
            )
            for b in beats:
                progress = b.end_sec / max(0.1, total_duration)
                frame_png = work_dir / f"frame_{frame_counter:04d}.png"
                render_scene_beat_frame(
                    scene=scene,
                    caption_text=b.text,
                    scene_idx=idx,
                    total_scenes=len(scenes),
                    progress_ratio=progress,
                    fmt=fmt,
                    output_png=frame_png,
                )
                beat_frames.append(frame_png)
                all_beats.append(b)
                frame_counter += 1
            timeline_cursor += dur

        # Step 3: Concatenate scene voiceovers & mix with 100% original ambient soundtrack
        voice_concat_list = work_dir / "voice_list.txt"
        voice_concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in scene_audio_files) + "\n",
            encoding="utf-8",
        )
        combined_voice_wav = work_dir / "voice_combined.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(voice_concat_list),
                "-ar", "24000", "-ac", "1",
                str(combined_voice_wav),
            ],
            check=True,
            capture_output=True,
        )

        ambient_wav = generate_ambient_bed(work_dir / "ambient.wav", total_duration)
        mixed_audio_m4a = work_dir / "master_audio.m4a"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(combined_voice_wav),
                "-i", str(ambient_wav),
                "-filter_complex",
                "[0:a]volume=1.0[v];[1:a]volume=0.22[bg];[v][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "[aout]",
                "-c:a", "aac", "-b:a", "192k",
                str(mixed_audio_m4a),
            ],
            check=True,
            capture_output=True,
        )

        # Step 4: Each beat becomes a moving clip (slow push-in that continues across a
        # scene, fade-in on scene changes), then clips are joined losslessly.
        scene_starts: List[float] = []
        acc = 0.0
        for d in scene_durations:
            scene_starts.append(acc)
            acc += d
        clip_paths: List[Path] = []
        elapsed = 0.0
        frames_done = 0
        for i, (frame_png, beat) in enumerate(zip(beat_frames, all_beats)):
            # frame counts from the cumulative timeline so rounding never drifts from the audio
            elapsed += beat.duration
            n_frames = max(1, round(elapsed * fmt.fps) - frames_done)
            frames_done += n_frames
            clip = work_dir / f"clip_{i:04d}.mp4"
            _render_motion_clip(
                frame_png, clip, n_frames / fmt.fps,
                t_offset=beat.start_sec - scene_starts[beat.scene_index],
                scene_dur=scene_durations[beat.scene_index],
                first_in_scene=(beat.beat_index == 0),
                fmt=fmt,
            )
            clip_paths.append(clip)
        clips_list = work_dir / "clips_list.txt"
        clips_list.write_text("\n".join(f"file '{c.as_posix()}'" for c in clip_paths) + "\n", encoding="utf-8")

        output_mp4 = proj_out / f"{project_slug}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(clips_list),
                "-i", str(mixed_audio_m4a),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "copy",
                "-movflags", "+faststart",
                "-shortest",
                str(output_mp4),
            ],
            check=True,
            capture_output=True,
        )

        # Step 5: Export .srt captions, thumbnail.png, and SEO Upload Pack
        output_srt = export_srt(all_beats, proj_out / f"{project_slug}.srt")
        thumb_meta = data.get("thumbnail", {})
        output_thumb = render_thumbnail(
            hook_text=thumb_meta.get("hook_text", data.get("title", "THE LEVERAGE SHIFT")[:24]),
            sub_badge=thumb_meta.get("badge", "WEALTH PSYCHOLOGY"),
            stat_highlight=thumb_meta.get("stat", "10X"),
            output_png=proj_out / f"{project_slug}_thumbnail.png",
        )
        output_seo = _write_seo_upload_pack(data, scenes, scene_durations, tts_used, proj_out / "youtube_upload_pack.md")

        return {
            "video": output_mp4,
            "srt": output_srt,
            "thumbnail": output_thumb,
            "seo_pack": output_seo,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _render_motion_clip(
    frame_png: Path,
    out_mp4: Path,
    duration: float,
    t_offset: float,
    scene_dur: float,
    first_in_scene: bool,
    fmt,
    zoom_max: float = 0.05,
) -> None:
    """Turn one still frame into a clip with a slow push-in; zoom is tied to time in the
    scene so consecutive beats of the same scene continue the move without a jump."""
    fps = fmt.fps
    w, h = fmt.width, fmt.height
    n = max(1, round(duration * fps))
    sd = max(0.1, scene_dur)
    zoom = f"1+{zoom_max}*({t_offset:.4f}+on/{fps})/{sd:.4f}"
    vf = (
        f"scale={w * 2}:{h * 2},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"
    )
    if first_in_scene:
        vf += ",fade=t=in:st=0:d=0.3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(frame_png),
            "-vf", vf, "-frames:v", str(n),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(fps), str(out_mp4),
        ],
        check=True,
        capture_output=True,
    )


def _format_chapter_ts(seconds: float) -> str:
    total = int(seconds)
    mins, secs = divmod(total, 60)
    return f"{mins:02d}:{secs:02d}"


def _write_seo_upload_pack(
    data: Dict[str, Any],
    scenes: List[Dict[str, Any]],
    scene_durations: List[float],
    tts_used: str,
    out_md: Path,
) -> Path:
    chapters: List[str] = []
    acc = 0.0
    for sc, dur in zip(scenes, scene_durations):
        chapters.append(f"{_format_chapter_ts(acc)} - {sc.get('headline', sc.get('tag', 'Part'))}")
        acc += dur

    tags_csv = ", ".join(data.get("tags", ["wealth psychology", "mental models", "ai productivity", "personal finance"]))
    aff = data.get("affiliate_cta", {})
    aff_block = (
        f"🔗 **{aff.get('offer_name', 'Free Leverage System Notion Template')}**: {aff.get('url_placeholder', 'https://yourlink.com/resource')}"
        if aff else ""
    )

    synthetic_note = (
        "No (stylized motion-graphics & educational frameworks only — toggle 'Yes' in YouTube Studio ONLY if you add photorealistic AI scenes/people)."
    )

    md = f"""# YouTube Upload Pack — {data.get('title')}

- **Format**: `{data.get('format', 'short').upper()}`
- **Estimated Runtime**: `{acc:.1f}s`
- **Voice Engine Used**: `{tts_used}`
- **YouTube Studio 'Altered or Synthetic Content' Toggle**: {synthetic_note}

## 1. Title Options (Pick 1 or A/B Test in YouTube Studio)
1. **{data.get('title')}**
2. {data.get('alt_title_1', data.get('title') + ' (Most People Miss This)')}
3. {data.get('alt_title_2', 'The Quiet Rule Behind ' + data.get('title', ''))}

## 2. Copy-Paste SEO Description
```text
{data.get('description_hook', data.get('title'))}

{aff_block}

⏱️ Timestamps:
{chr(10).join(chapters)}

📚 About {DEFAULT_THEME.channel_name}:
We break down wealth psychology, timeless book frameworks, and modern AI leverage in visual essays designed for asymmetric thinkers.

⚠️ Disclaimer: Educational content & case studies only — not personalized financial or legal advice. As an Amazon Associate I earn from qualifying purchases.
```

## 3. Pinned Comment (Boosts Engagement + Early Affiliate Revenue!)
```text
{aff.get('pinned_comment', 'Quick question: Which mental model in this video hit closest to home for you? 👇 Plus I linked the free summary checklist right here: https://yourlink.com/checklist')}
```

## 4. Tags
`{tags_csv}`
"""
    out_md.write_text(md, encoding="utf-8")
    return out_md
