"""High-retention caption chunker and SRT subtitle exporter."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List


@dataclass
class CaptionBeat:
    scene_index: int
    beat_index: int
    text: str
    start_sec: float
    end_sec: float

    @property
    def duration(self) -> float:
        return max(0.4, round(self.end_sec - self.start_sec, 3))


def split_into_beats(narration: str, max_words: int = 6) -> List[str]:
    """Split a scene narration into punchy 4-7 word phrases at natural punctuation boundaries."""
    clauses = [c.strip() for c in re.split(r"(?<=[.!?;:—–,])\s+", narration.strip()) if c.strip()]
    beats: List[str] = []
    for clause in clauses:
        words = clause.split()
        if len(words) <= max_words + 1:
            beats.append(clause)
        else:
            for idx in range(0, len(words), max_words):
                chunk = " ".join(words[idx : idx + max_words])
                if chunk:
                    beats.append(chunk)
    return beats or [narration.strip()]


def build_scene_beats(
    scene_index: int,
    narration: str,
    scene_start_sec: float,
    scene_duration_sec: float,
    max_words: int = 6,
) -> List[CaptionBeat]:
    """Allocate exact timestamps across beats weighted by character length."""
    phrases = split_into_beats(narration, max_words=max_words)
    weights = [max(4, len(p)) for p in phrases]
    total_weight = sum(weights)

    beats: List[CaptionBeat] = []
    cursor = scene_start_sec
    for i, (phrase, w) in enumerate(zip(phrases, weights)):
        if i == len(phrases) - 1:
            end = scene_start_sec + scene_duration_sec
        else:
            end = cursor + scene_duration_sec * (w / total_weight)
        beats.append(
            CaptionBeat(
                scene_index=scene_index,
                beat_index=i,
                text=phrase,
                start_sec=round(cursor, 3),
                end_sec=round(end, 3),
            )
        )
        cursor = end
    return beats


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hrs, rem = divmod(millis, 3_600_000)
    mins, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def export_srt(beats: List[CaptionBeat], output_srt: Path) -> Path:
    """Write standard SubRip (.srt) subtitle file for YouTube CC & multi-language SEO."""
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    for idx, beat in enumerate(beats, start=1):
        start_ts = _format_srt_timestamp(beat.start_sec)
        end_ts = _format_srt_timestamp(beat.end_sec)
        lines.append(f"{idx}\n{start_ts} --> {end_ts}\n{beat.text}\n")
    output_srt.write_text("\n".join(lines), encoding="utf-8")
    return output_srt
