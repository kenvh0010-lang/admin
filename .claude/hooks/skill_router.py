#!/usr/bin/env python3
"""UserPromptSubmit hook: point Claude at the project skill that matches the prompt.

Reads the hook JSON on stdin, scans .claude/skills/*/SKILL.md frontmatter, scores each
skill by keyword overlap between the prompt and the skill's name + description, and
prints hookSpecificOutput.additionalContext telling Claude which skill(s) to invoke.
Never blocks the prompt: any error prints nothing and exits 0.
"""

import json
import os
import re
import sys
from pathlib import Path

STOP = {
    "the", "and", "for", "with", "use", "when", "any", "this", "that", "from", "into",
    "your", "you", "are", "all", "not", "but", "can", "will", "whenever", "editing",
    "creating", "file", "files", "page", "skill", "skills", "or", "of", "to", "in", "on",
    "a", "an", "is", "it", "be", "as", "by", "at", "if",
}
# Vietnamese / shorthand cues mapped to English description words
ALIASES = {
    "video": ["video", "shorts", "short", "render"],
    "thumbnail": ["thumbnail"], "anh bia": ["thumbnail"], "ảnh bìa": ["thumbnail"],
    "mau": ["colors"], "màu": ["colors"], "font": ["fonts"], "phong chu": ["fonts"],
    "thuong hieu": ["brand"], "thương hiệu": ["brand"], "kich ban": ["storyboard"],
    "kịch bản": ["storyboard"], "website": ["site"], "trang": ["site"], "bio": ["bio"],
    "giong doc": ["voice"], "giọng đọc": ["voice"], "kenh": ["channel"], "kênh": ["channel"],
}


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9_.-]{1,}", text.lower()) if w not in STOP}


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("\"'")
    return meta


def build_context(prompt: str, skills_dir: Path) -> str:
    skills = []
    for sk in sorted(skills_dir.glob("*/SKILL.md")):
        meta = _frontmatter(sk)
        name = meta.get("name") or sk.parent.name
        skills.append((name, meta.get("description", "")))
    if not skills:
        return ""

    low = prompt.lower()
    p_words = _words(prompt)
    for cue, extra in ALIASES.items():
        if cue in low:
            p_words.update(extra)

    scored = []
    for name, desc in skills:
        d_words = _words(name.replace("-", " ") + " " + desc)
        hits = sorted(p_words & d_words)
        if name.lower() in low:
            hits.insert(0, name)
        if hits:
            scored.append((len(hits), name, hits))
    scored.sort(reverse=True)

    lines = ["Project skills available (.claude/skills): " + ", ".join(n for n, _ in skills) + "."]
    if scored:
        best = ", ".join(f"{n} (matched: {', '.join(h[:5])})" for _, n, h in scored[:3])
        lines.append(
            f"This prompt matches: {best}. Before doing the work, invoke the matching "
            "skill with the Skill tool and follow it."
        )
    else:
        lines.append("If the request fits one of these skills, invoke it with the Skill tool before acting.")
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    prompt = str(payload.get("prompt", ""))
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or Path(__file__).resolve().parents[2])
    ctx = build_context(prompt, root / ".claude" / "skills")
    if ctx:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
