"""Multi-provider Text-to-Speech + 100% Copyright-Free Ambient Music Synthesizer."""

import json
import math
import os
import shutil
import struct
import subprocess
import urllib.request
import wave
from pathlib import Path
from typing import Tuple

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


def estimate_speech_duration(text: str, wpm: int = 155) -> float:
    """Estimate natural narration duration in seconds from word count and punctuation."""
    words = len(text.split())
    pauses = text.count(",") * 0.18 + (text.count(".") + text.count("?") + text.count("!")) * 0.32
    return max(2.2, round((words / (wpm / 60.0)) + pauses, 2))


def synthesize_voice(
    text: str,
    output_path: Path,
    provider: str = "auto",
    voice: str = "en_authoritative",
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

    if provider in ("auto", "openai") and os.environ.get("OPENAI_API_KEY"):
        try:
            mp3_path = output_path.with_suffix(".mp3")
            _synthesize_openai(text, mp3_path)
            return mp3_path, probe_audio_duration(mp3_path), "openai"
        except Exception as exc:
            if provider == "openai":
                raise RuntimeError(f"OpenAI TTS failed: {exc}") from exc

    if provider in ("auto", "elevenlabs") and os.environ.get("ELEVENLABS_API_KEY"):
        try:
            mp3_path = output_path.with_suffix(".mp3")
            _synthesize_elevenlabs(text, mp3_path)
            return mp3_path, probe_audio_duration(mp3_path), "elevenlabs"
        except Exception as exc:
            if provider == "elevenlabs":
                raise RuntimeError(f"ElevenLabs TTS failed: {exc}") from exc

    if provider in ("auto", "edge") and shutil.which("edge-tts"):
        mp3_path = output_path.with_suffix(".mp3")
        last_exc = None
        for attempt in range(3):
            try:
                subprocess.run(
                    ["edge-tts", "--voice", resolved_voice, "--rate=+4%", "--text", text, "--write-media", str(mp3_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=35,
                )
                if mp3_path.is_file() and mp3_path.stat().st_size > 512:
                    return mp3_path, probe_audio_duration(mp3_path), f"edge-tts ({resolved_voice})"
            except Exception as exc:
                last_exc = exc
                import time
                time.sleep(0.8 * (attempt + 1))
        if provider == "edge" and last_exc is not None:
            raise RuntimeError(f"edge-tts failed after 3 attempts: {last_exc}") from last_exc

    # Offline fallback: silent narration timing track (ambient music will carry audio during preview)
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
