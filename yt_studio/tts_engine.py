"""Multi-provider Text-to-Speech + 100% Copyright-Free Ambient Music Synthesizer."""

import array
import json
import math
import os
import importlib.util
import shutil
import struct
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path
from typing import List, Optional, Tuple

from .config import VOICE_PRESETS


def probe_audio_duration(audio_path: Path) -> float:
    """Measure exact audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return max(0.5, float(res.stdout.strip()))


def estimate_speech_duration(text: str, wpm: int = 172) -> float:
    """Estimate natural narration duration in seconds from word count and punctuation."""
    words = len(text.split())
    pauses = text.count(",") * 0.12 + (text.count(".") + text.count("?") + text.count("!")) * 0.22
    return max(1.8, round((words / (wpm / 60.0)) + pauses, 2))


def _trim_speech_silence(
    audio_path: Path,
    out_wav: Path,
    tail_pad_sec: float = 0.10,
    sample_rate: int = 24000,
) -> Tuple[Path, float]:
    """Decode audio to PCM, trim leading/trailing digital dead air, and append a tight tail pause."""
    if not shutil.which("ffmpeg"):
        return audio_path, probe_audio_duration(audio_path)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le",
            str(out_wav),
        ],
        capture_output=True,
    )
    if res.returncode != 0 or not out_wav.is_file() or out_wav.stat().st_size < 128:
        return audio_path, probe_audio_duration(audio_path)

    with wave.open(str(out_wav), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()

    thresh = 180  # ~ -45 dBFS
    first_idx: Optional[int] = None
    last_idx: Optional[int] = None
    for idx, val in enumerate(samples):
        if abs(val) > thresh:
            if first_idx is None:
                first_idx = idx
            last_idx = idx

    if first_idx is None or last_idx is None:
        return out_wav, probe_audio_duration(out_wav)

    lead_samples = int(0.022 * sample_rate)
    trail_samples = int(0.025 * sample_rate)
    pad_samples = int(max(0.0, tail_pad_sec) * sample_rate)
    start_i = max(0, first_idx - lead_samples)
    end_i = min(len(samples), last_idx + trail_samples)
    trimmed = samples[start_i:end_i] + array.array("h", [0]) * pad_samples

    if len(trimmed) < int(0.35 * sample_rate):
        return out_wav, probe_audio_duration(out_wav)

    out_samples = array.array("h", trimmed)
    if sys.byteorder != "little":
        out_samples.byteswap()
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(out_samples.tobytes())
    return out_wav, round(len(trimmed) / sample_rate, 3)


def resolve_edge_tts_command() -> Optional[List[str]]:
    """Locate edge-tts: the console script on PATH, or the module through this interpreter.

    On Windows (typical RTX workstation) `pip install edge-tts` drops `edge-tts.exe` into a
    Scripts/ folder that is often not on PATH, so `shutil.which` alone misses it and the
    renderer used to fall back to a silent preview track without saying so.
    """
    exe = shutil.which("edge-tts")
    if exe:
        return [exe]
    if importlib.util.find_spec("edge_tts") is not None:
        return [sys.executable, "-m", "edge_tts"]
    return None


EDGE_TTS_INSTALL_HINT = (
    "edge-tts is not installed for this Python interpreter. Run "
    f"'{Path(sys.executable).name} -m pip install edge-tts' and re-render."
)


def synthesize_voice(
    text: str,
    output_path: Path,
    provider: str = "auto",
    voice: str = "en_authoritative",
    is_last_scene: bool = False,
) -> Tuple[Path, float, str]:
    """
    Generate voiceover audio for a scene.

    Provider priority when provider='auto':
      1. OpenAI TTS (if OPENAI_API_KEY is set)
      2. ElevenLabs (if ELEVENLABS_API_KEY is set)
      3. Microsoft Edge Neural TTS via edge-tts ($0 free, high quality)
      4. Offline timing placeholder WAV (for instant offline layout/video testing)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_voice = VOICE_PRESETS.get(voice, voice)
    tail_pad = 0.04 if is_last_scene else 0.10

    if provider in ("auto", "openai") and os.environ.get("OPENAI_API_KEY"):
        try:
            mp3_path = output_path.with_suffix(".mp3")
            _synthesize_openai(text, mp3_path)
            trimmed_wav, dur = _trim_speech_silence(
                mp3_path, output_path.with_suffix(".trimmed.wav"), tail_pad_sec=tail_pad
            )
            return trimmed_wav, dur, "openai"
        except Exception as exc:
            if provider == "openai":
                raise RuntimeError(f"OpenAI TTS failed: {exc}") from exc

    if provider in ("auto", "elevenlabs") and os.environ.get("ELEVENLABS_API_KEY"):
        try:
            mp3_path = output_path.with_suffix(".mp3")
            _synthesize_elevenlabs(text, mp3_path)
            trimmed_wav, dur = _trim_speech_silence(
                mp3_path, output_path.with_suffix(".trimmed.wav"), tail_pad_sec=tail_pad
            )
            return trimmed_wav, dur, "elevenlabs"
        except Exception as exc:
            if provider == "elevenlabs":
                raise RuntimeError(f"ElevenLabs TTS failed: {exc}") from exc

    edge_cmd = resolve_edge_tts_command() if provider in ("auto", "edge") else None
    if provider == "edge" and edge_cmd is None:
        raise RuntimeError(EDGE_TTS_INSTALL_HINT)
    if edge_cmd is not None:
        mp3_path = output_path.with_suffix(".mp3")
        last_exc = None
        for attempt in range(3):
            try:
                subprocess.run(
                    edge_cmd + ["--voice", resolved_voice, "--rate=+11%", "--text", text, "--write-media", str(mp3_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=35,
                )
                if mp3_path.is_file() and mp3_path.stat().st_size > 512:
                    trimmed_wav, dur = _trim_speech_silence(
                        mp3_path, output_path.with_suffix(".trimmed.wav"), tail_pad_sec=tail_pad
                    )
                    return trimmed_wav, dur, f"edge-tts ({resolved_voice})"
            except Exception as exc:
                last_exc = exc
                import time
                time.sleep(0.8 * (attempt + 1))
        if provider == "edge":
            raise RuntimeError(f"edge-tts failed after 3 attempts: {last_exc}") from last_exc

    # Offline fallback: silent narration timing track (ambient music will carry audio during preview)
    if provider != "offline":
        print(
            "WARNING: no TTS provider available -> rendering a SILENT offline preview "
            f"(no voiceover). {EDGE_TTS_INSTALL_HINT}",
            file=sys.stderr,
        )
    wav_path = output_path.with_suffix(".wav")
    duration = estimate_speech_duration(text)
    _write_transition_chime_track(wav_path, duration)
    return wav_path, duration, "offline-preview (install edge-tts for free neural voice)"


def _synthesize_openai(text: str, output_mp3: Path) -> None:
    payload = json.dumps({
        "model": "tts-1-hd",
        "voice": "onyx",
        "input": text,
        "speed": 1.03,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        output_mp3.write_bytes(resp.read())


def _synthesize_elevenlabs(text: str, output_mp3: Path) -> None:
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # George (authoritative storyteller)
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.78},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=payload,
        headers={
            "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        output_mp3.write_bytes(resp.read())


def _write_transition_chime_track(wav_path: Path, duration_sec: float, sample_rate: int = 24000) -> None:
    """Write a soft subtle scene-transition chime followed by clean silence matching speech timing."""
    total_samples = int(duration_sec * sample_rate)
    chime_samples = min(total_samples, int(0.28 * sample_rate))
    buf = bytearray()
    for i in range(chime_samples):
        t = i / sample_rate
        env = math.exp(-t * 14.0) * 0.14
        sample_val = env * (0.65 * math.sin(2 * math.pi * 528.0 * t) + 0.35 * math.sin(2 * math.pi * 792.0 * t))
        pcm = max(-32767, min(32767, int(sample_val * 32767)))
        buf.extend(struct.pack("<h", pcm))
    if total_samples > chime_samples:
        buf.extend(b"\x00\x00" * (total_samples - chime_samples))

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(buf))


def generate_ambient_bed(output_wav: Path, duration_sec: float, sample_rate: int = 24000) -> Path:
    """
    Synthesize a 100% original, Content-ID-safe deep ambient documentary pad.
    Uses a warm A-minor-9 harmonic bed (110Hz, 164.8Hz, 220Hz, 246.9Hz, 329.6Hz) with slow LFO breathing.
    """
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    dur = max(1.0, round(duration_sec + 0.5, 3))
    fade_out_start = max(0.2, round(dur - 1.4, 3))
    expr = (
        "0.16*(0.78+0.22*sin(2*PI*0.14*t))*(1.0+0.08*sin(2*PI*1.5*t))*"
        "(0.36*sin(2*PI*110*t)+0.24*sin(2*PI*164.81*t)+0.20*sin(2*PI*220*t)"
        "+0.11*sin(2*PI*246.94*t)+0.09*sin(2*PI*329.63*t))"
    )
    if shutil.which("ffmpeg"):
        res = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"aevalsrc='{expr}':s={sample_rate}:d={dur}",
                "-af", f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start}:d=1.4",
                "-ac", "1", "-ar", str(sample_rate),
                str(output_wav),
            ],
            capture_output=True,
        )
        if res.returncode == 0 and output_wav.is_file() and output_wav.stat().st_size > 1000:
            return output_wav

    total_samples = int(dur * sample_rate)
    freqs = [(110.0, 0.36), (164.81, 0.24), (220.0, 0.20), (246.94, 0.11), (329.63, 0.09)]
    fade_in = int(0.8 * sample_rate)
    fade_out = int(1.4 * sample_rate)

    buf = bytearray()
    two_pi = 2.0 * math.pi
    for i in range(total_samples):
        t = i / sample_rate
        lfo = 0.78 + 0.22 * math.sin(two_pi * 0.14 * t)
        pulse = 1.0 + 0.08 * math.sin(two_pi * 1.5 * t)
        val = 0.0
        for f, weight in freqs:
            val += weight * math.sin(two_pi * f * t)
        env = 0.16 * lfo * pulse
        if i < fade_in:
            env *= i / max(1, fade_in)
        elif i > total_samples - fade_out:
            env *= (total_samples - i) / max(1, fade_out)
        pcm = max(-32767, min(32767, int(val * env * 32767)))
        buf.extend(struct.pack("<h", pcm))

    with wave.open(str(output_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(buf))
    return output_wav


def generate_scene_sfx_track(
    output_wav: Path,
    scene_starts: List[float],
    duration_sec: float,
    sample_rate: int = 24000,
) -> Path:
    """Synthesize subtle Content-ID-safe documentary hook pulses and exhibit switch cues."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    total_samples = max(1, int(round(max(0.5, duration_sec) * sample_rate)))
    samples = array.array("h", [0]) * total_samples
    two_pi = 2.0 * math.pi

    for s_idx, start_t in enumerate(scene_starts):
        base_i = max(0, int(round(start_t * sample_rate)))
        if base_i >= total_samples:
            continue
        cue_len = int((0.065 if s_idx == 0 else 0.045) * sample_rate)
        for k in range(cue_len):
            pos = base_i + k
            if pos >= total_samples:
                break
            t = k / sample_rate
            if s_idx == 0:
                env = math.exp(-t * 42.0)
                val = (
                    0.42 * env * math.sin(two_pi * (96.0 - 38.0 * min(1.0, t * 15.0)) * t)
                    + 0.16 * math.exp(-t * 160.0) * math.sin(two_pi * 1750.0 * t)
                )
            else:
                env = math.exp(-t * 58.0)
                val = (
                    0.28 * env * math.sin(two_pi * 135.0 * t)
                    + 0.14 * math.exp(-t * 210.0) * math.sin(two_pi * 2150.0 * t)
                )
            mixed = samples[pos] + int(val * 32767)
            samples[pos] = max(-32767, min(32767, mixed))

    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(output_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return output_wav
