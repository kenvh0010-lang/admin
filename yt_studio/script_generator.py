"""Quarantine-First Evidence News-Short Generator & Case Scaffolder (`content/drafts/`)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.request

from PIL import Image

from .config import ASSETS_DIR, CONTENT_DIR, PROJECT_ROOT
from .site_builder import SITE_BASE_URL

DRAFTS_DIR = CONTENT_DIR / "drafts"
BIO_URL = f"{SITE_BASE_URL}/bio/"

EVIDENCE_SYSTEM_PROMPT = f"""You are the executive documentary producer for 'Mind & Margin' (@MindAndMargin), an English investigative finance & regulatory YouTube Shorts channel.

STRICT EDITORIAL & BRAND RULES (mind-margin-brand):
1. Format purity: Output ONLY a 5-scene vertical News-Short ("format": "short", "voice": "en_authoritative").
2. 5-scene visual architecture:
   - Scenes 1-4 MUST use "visual_type": "evidence_image" with NO "bullets" key so the court filing / regulator exhibit fills the frame cleanly.
   - Scene 5 ("tag": "THE RULE") MUST use "visual_type": "comparison_split" with crisp "left_title", "left_body", "right_title", "right_body".
3. Citations & journalistic attribution:
   - Every scene MUST carry a specific primary "source" citation (court docket, agency order, report table).
   - Top-level "sources" MUST list >= 2 real "https://" URLs with clear labels.
   - Attribute unproven claims accurately ("The FTC alleges...", "Prosecutors allege...", "settled without admitting fault").
4. Pacing & zero AI tells:
   - Total narration across all 5 scenes: 75-110 words (~32-44 seconds). 15-24 words per scene.
   - Headlines: 3-5 punchy words (must fit <= 3 lines).
   - NEVER use forbidden glyphs: ✕ ✓ ▸ → — – (use ASCII hyphens -, colons :, or ->).
   - NEVER use < or > anywhere.
   - NEVER use banned buzzwords: unlock, delve, game-changer, tapestry, skyrocket, secretly, ruthlessly, "studies show", "Here is how" openers, or "..." cliffhangers.
5. Monetization:
   - Set "affiliate_cta.url_placeholder" to "{BIO_URL}".
   - Never disparage Amazon retail or Prime.

Return ONLY valid JSON matching this exact structure:
{{
  "title": "Sharp factual hook with exact dollar/stat under 68 chars",
  "alt_title_1": "Alternative factual angle",
  "alt_title_2": "Second alternative title",
  "format": "short",
  "voice": "en_authoritative",
  "description_hook": "Two-sentence factual summary citing the agency, court docket, and exact numbers.",
  "tags": ["ftc", "consumer protection", "fintech news", "personal finance", "corporate law"],
  "thumbnail": {{
    "hook_text": "3 TO 4 WORDS",
    "badge": "COURT FILING",
    "stat": "$100M"
  }},
  "affiliate_cta": {{
    "offer_name": "Free 5-Hour Asset Builder OS + reading list",
    "url_placeholder": "{BIO_URL}",
    "pinned_comment": "One-sentence personal wallet question? Every filing and source is linked in the description."
  }},
  "scenes": [
    {{
      "tag": "HOOK",
      "headline": "3-5 Word Factual Hook",
      "visual_type": "evidence_image",
      "evidence_image": "assets/evidence/topic/exhibit_1.png",
      "evidence_crop": [120, 180, 1140, 920],
      "highlight_words": ["exact", "number"],
      "narration": "15-22 word documentary voiceover with exact numbers.",
      "source": "Agency / Court Case No., p. 1 (Year)"
    }},
    {{
      "tag": "THE RULE",
      "headline": "Actionable Wallet Rule",
      "visual_type": "comparison_split",
      "left_title": "AD PITCH",
      "left_body": "Short contrast on left",
      "right_title": "REAL BILL",
      "right_body": "Short contrast on right",
      "highlight_words": ["rule", "word"],
      "narration": "15-22 word closing wallet rule.",
      "source": "Primary Order / Filing Citation"
    }}
  ],
  "sources": [
    {{"label": "Official Agency / Court Filing PDF", "url": "https://www.justice.gov/..."}},
    {{"label": "Official Press Release / Docket Summary", "url": "https://www.ftc.gov/..."}}
  ]
}}
"""


def resolve_draft_destination(
    output_json: Path,
    content_dir: Path = CONTENT_DIR,
    allow_active: bool = False,
) -> Path:
    """Quarantine generated/scaffolded storyboards inside content/drafts/ unless allow_active=True."""
    resolved = Path(output_json).resolve()
    content_resolved = content_dir.resolve()
    drafts_resolved = (content_dir / "drafts").resolve()
    if not allow_active and resolved.is_relative_to(content_resolved) and not resolved.is_relative_to(drafts_resolved):
        return drafts_resolved / resolved.name
    return resolved


def inspect_evidence_folder(
    evidence_dir: Optional[Path],
    project_root: Path = PROJECT_ROOT,
) -> List[Dict[str, Any]]:
    """Inspect real PNG/JPG exhibits in evidence_dir and compute safe default crop boxes."""
    if evidence_dir is None:
        return []
    ev_path = Path(evidence_dir)
    if not ev_path.is_absolute():
        ev_path = project_root / ev_path
    if not ev_path.is_dir():
        return []

    exhibits: List[Dict[str, Any]] = []
    for img_file in sorted(ev_path.iterdir()):
        if img_file.is_file() and img_file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            try:
                with Image.open(img_file) as im:
                    w, h = im.size
            except Exception:
                continue
            rel = img_file.resolve().relative_to(project_root.resolve()).as_posix()
            crop = [
                max(0, int(w * 0.08)),
                max(0, int(h * 0.12)),
                min(w, int(w * 0.92)),
                min(h, int(h * 0.78)),
            ]
            exhibits.append({"rel_path": rel, "width": w, "height": h, "default_crop": crop})
    return exhibits


def build_prompt_for_topic(
    topic: str,
    fmt: str = "short",
    affiliate_offer: str = "Free 5-Hour Asset Builder OS + reading list",
    exhibits: Optional[List[Dict[str, Any]]] = None,
    sources: Optional[List[Tuple[str, str]]] = None,
) -> str:
    exhibit_lines = ""
    if exhibits:
        rows = "\n".join(
            f"  - {ex['rel_path']} ({ex['width']}x{ex['height']} px, safe starter crop: {ex['default_crop']})"
            for ex in exhibits
        )
        exhibit_lines = f"\nAVAILABLE VERIFIED SCREENSHOTS ON DISK (USE THESE EXACT PATHS & STAY WITHIN PIXEL BOUNDS):\n{rows}\n"

    source_lines = ""
    if sources:
        srows = "\n".join(f"  - {lbl}: {url}" for lbl, url in sources)
        source_lines = f"\nVERIFIED PRIMARY SOURCE URLS TO INCLUDE IN 'sources':\n{srows}\n"

    return (
        f"{EVIDENCE_SYSTEM_PROMPT}\n"
        f"CASE TOPIC: {topic}\n"
        f"FORMAT: {fmt}\n"
        f"AFFILIATE OFFER NAME: {affiliate_offer}\n"
        f"{exhibit_lines}"
        f"{source_lines}"
    )


def scaffold_case_draft(
    slug: str,
    topic: str,
    evidence_dir: Optional[Path] = None,
    sources: Optional[List[Tuple[str, str]]] = None,
    output_json: Optional[Path] = None,
    content_dir: Path = CONTENT_DIR,
    project_root: Path = PROJECT_ROOT,
) -> Tuple[Path, Path]:
    """Create a quarantined 5-scene News-Short draft JSON + LLM prompt in content/drafts/."""
    clean_slug = re.sub(r"\.json$", "", slug.strip())
    dest = resolve_draft_destination(
        output_json or (content_dir / "drafts" / f"{clean_slug}.json"),
        content_dir=content_dir,
        allow_active=False,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)

    topic_slug = re.sub(r"^short_\d+_", "", clean_slug)
    inferred_ev_dir = evidence_dir or (ASSETS_DIR / "evidence" / topic_slug)
    exhibits = inspect_evidence_folder(inferred_ev_dir, project_root=project_root)

    def _pick_exhibit(idx: int) -> Tuple[str, List[int]]:
        if exhibits:
            chosen = exhibits[min(idx, len(exhibits) - 1)]
            return chosen["rel_path"], list(chosen["default_crop"])
        return f"assets/evidence/{topic_slug}/exhibit_{idx + 1:02d}.png", [120, 180, 1140, 920]

    tags_list = ["HOOK", "THE FILING", "THE EVIDENCE", "THE ORDER"]
    scenes: List[Dict[str, Any]] = []
    for idx, tag in enumerate(tags_list):
        ev_rel, crop = _pick_exhibit(idx)
        scenes.append(
            {
                "tag": tag,
                "headline": f"Draft Scene {idx + 1} Headline",
                "visual_type": "evidence_image",
                "evidence_image": ev_rel,
                "evidence_crop": crop,
                "highlight_words": [],
                "narration": (
                    f"Replace with 16 to 22 factual words for scene {idx + 1} citing exact filing numbers on {topic}."
                ),
                "source": "Primary Agency / Court Docket Citation (Year)",
            }
        )

    scenes.append(
        {
            "tag": "THE RULE",
            "headline": "Draft Closing Wallet Rule",
            "visual_type": "comparison_split",
            "left_title": "SALES PITCH",
            "left_body": "What the app promised up front",
            "right_title": "FILING REALITY",
            "right_body": "What regulators documented in court",
            "highlight_words": [],
            "narration": "Replace with a crisp 16 to 20 word practical wallet rule grounded in this case.",
            "source": "Primary Order / Court Filing Citation",
        }
    )

    src_entries = (
        [{"label": lbl, "url": url} for lbl, url in sources]
        if sources
        else [
            {"label": "Primary Court Complaint / Agency Order PDF", "url": "https://www.justice.gov/"},
            {"label": "Official Agency Press Release", "url": "https://www.ftc.gov/"},
        ]
    )

    draft_payload = {
        "title": topic[:68],
        "alt_title_1": f"Inside the Federal Filing: {topic[:42]}",
        "alt_title_2": f"The Exact Numbers Behind {topic[:42]}",
        "format": "short",
        "voice": "en_authoritative",
        "description_hook": f"Factual breakdown of {topic} using primary federal filings and exhibits.",
        "tags": ["consumer protection", "federal lawsuit", "fintech news", "personal finance", "corporate law"],
        "thumbnail": {
            "hook_text": "FEDERAL FILING",
            "badge": "ENFORCEMENT",
            "stat": "$0M",
        },
        "affiliate_cta": {
            "offer_name": "Free 5-Hour Asset Builder OS + reading list",
            "url_placeholder": BIO_URL,
            "pinned_comment": "Have you encountered this fee or app flow yourself? Primary filings are linked in the description.",
        },
        "scenes": scenes,
        "sources": src_entries,
    }
    dest.write_text(json.dumps(draft_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    prompt_path = dest.with_suffix(".prompt.txt")
    prompt_path.write_text(
        build_prompt_for_topic(topic=topic, fmt="short", exhibits=exhibits, sources=sources),
        encoding="utf-8",
    )
    return dest, prompt_path


def generate_storyboard_json(
    topic: str,
    output_json: Path,
    fmt: str = "short",
    affiliate_offer: str = "Free 5-Hour Asset Builder OS + reading list",
    evidence_dir: Optional[Path] = None,
    sources: Optional[List[Tuple[str, str]]] = None,
    allow_active: bool = False,
) -> Path:
    """Generate a quarantined 5-scene Evidence Short in content/drafts/ via Gemini/OpenAI or export prompt."""
    safe_dest = resolve_draft_destination(output_json, allow_active=allow_active)
    exhibits = inspect_evidence_folder(evidence_dir)
    prompt = build_prompt_for_topic(
        topic=topic,
        fmt=fmt,
        affiliate_offer=affiliate_offer,
        exhibits=exhibits,
        sources=sources,
    )
    safe_dest.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("GEMINI_API_KEY"):
        raw = _call_gemini(prompt, os.environ["GEMINI_API_KEY"])
        parsed = _extract_json(raw)
        safe_dest.write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return safe_dest

    if os.environ.get("OPENAI_API_KEY"):
        raw = _call_openai(prompt, os.environ["OPENAI_API_KEY"])
        parsed = _extract_json(raw)
        safe_dest.write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return safe_dest

    prompt_file = safe_dest.with_suffix(".prompt.txt")
    prompt_file.write_text(prompt, encoding="utf-8")
    raise EnvironmentError(
        f"No GEMINI_API_KEY or OPENAI_API_KEY set. Saved quarantined Evidence-Short prompt to: {prompt_file}"
    )


def _call_gemini(prompt: str, api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai(prompt: str, api_key: str) -> str:
    payload = json.dumps(
        {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }
    ).encode("utf-8")
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
