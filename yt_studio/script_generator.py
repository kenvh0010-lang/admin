"""AI Storyboard & SEO Generator (Gemini / OpenAI API + $0 Prompt Export)."""

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict


SYSTEM_SCHEMA_PROMPT = """You are the head producer of 'Mind & Margin', a high-RPM English faceless YouTube channel covering Wealth Psychology, Book Mental Models, and AI Leverage.
Write original, deeply insightful, non-generic scripts that pass YouTube's 2026 originality policies (concrete examples, counter-intuitive hooks, varied visual card types).
Never give specific stock/medical/legal advice; frame as educational psychology, historical/business case studies, and productivity systems.

Return ONLY valid JSON matching this exact schema:
{
  "title": "High-CTR curiosity title under 62 chars",
  "alt_title_1": "Alternative title for YouTube A/B testing",
  "alt_title_2": "Second alternative title",
  "format": "short",
  "voice": "en_authoritative",
  "description_hook": "2-sentence SEO summary packed with search intent keywords.",
  "tags": ["wealth psychology", "mental models", "financial freedom", "productivity"],
  "thumbnail": {
    "hook_text": "3 WORD HOOK",
    "badge": "WEALTH TRAP",
    "stat": "95%"
  },
  "affiliate_cta": {
    "offer_name": "Audible Free Audiobook Trial / Notion Wealth Tracker",
    "url_placeholder": "https://yourdomain.com/free-guide",
    "pinned_comment": "Comment question + soft value link for early monetization"
  },
  "scenes": [
    {
      "tag": "HOOK",
      "headline": "Short punchy on-screen header",
      "visual_type": "stat_callout | comparison_split | compounding_curve",
      "stat_value": "91%",
      "stat_label": "SUBTITLE FOR METRIC",
      "bullets": ["Point 1", "Point 2"],
      "left_title": "OLD WAY (only if comparison_split)",
      "left_body": "Description",
      "right_title": "LEVERAGE WAY (only if comparison_split)",
      "right_body": "Description",
      "highlight_words": ["wealth", "leverage", "trap"],
      "narration": "Spoken voiceover text for this scene."
    }
  ]
}
"""


def build_prompt_for_topic(topic: str, fmt: str = "short", affiliate_offer: str = "Audible Free Trial + Notion System") -> str:
    scene_guide = (
        "Create 6 fast-paced scenes totaling 45–55 seconds (~120–145 words total). End the final scene with a seamless loop phrase connecting back to Scene 1!"
        if fmt == "short"
        else "Create 10–14 deep visual-essay scenes totaling 6–8 minutes (~950–1200 words total) with concrete historical or business examples."
    )
    return (
        f"{SYSTEM_SCHEMA_PROMPT}\n\n"
        f"TOPIC: {topic}\n"
        f"FORMAT: {fmt}\n"
        f"AFFILIATE OFFER TO INTEGRATE NATURALLY IN PINNED COMMENT/DESCRIPTION: {affiliate_offer}\n"
        f"PACING REQUIREMENT: {scene_guide}\n"
    )


def generate_storyboard_json(
    topic: str,
    output_json: Path,
    fmt: str = "short",
    affiliate_offer: str = "Audible Free Trial + Notion Leverage Template",
) -> Path:
    """Generate a storyboard JSON using GEMINI_API_KEY or OPENAI_API_KEY, or export a ready prompt file."""
    prompt = build_prompt_for_topic(topic=topic, fmt=fmt, affiliate_offer=affiliate_offer)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("GEMINI_API_KEY"):
        raw = _call_gemini(prompt, os.environ["GEMINI_API_KEY"])
        parsed = _extract_json(raw)
        output_json.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_json

    if os.environ.get("OPENAI_API_KEY"):
        raw = _call_openai(prompt, os.environ["OPENAI_API_KEY"])
        parsed = _extract_json(raw)
        output_json.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_json

    prompt_file = output_json.with_suffix(".prompt.txt")
    prompt_file.write_text(prompt, encoding="utf-8")
    raise EnvironmentError(
        f"No GEMINI_API_KEY or OPENAI_API_KEY set. Saved ready-to-paste ChatGPT/Gemini prompt to: {prompt_file}"
    )


def _call_gemini(prompt: str, api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai(prompt: str, api_key: str) -> str:
    payload = json.dumps({
        "model": "gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _extract_json(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(cleaned)
