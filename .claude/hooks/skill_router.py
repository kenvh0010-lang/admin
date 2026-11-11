#!/usr/bin/env python3
"""UserPromptSubmit hook: point Claude at the project skill that matches the prompt.

Reads the hook JSON on stdin, scans skill frontmatter, scores each skill by keyword
overlap between the prompt and the skill's name + description, and prints
hookSpecificOutput.additionalContext telling Claude which skill(s) to invoke.

Sources, in priority order:
  1. Project skills: <repo>/.claude/skills/*/SKILL.md (one keyword hit is enough)
  2. Account skills synced from claude.ai: ~/.claude/skills/synced/*/*/SKILL.md,
     invoked as "anthropic-skills:<name>" (need two keyword hits)
  3. Personal skills: ~/.claude/skills/*/SKILL.md (need two keyword hits)
Skills listed under "exclude" in <repo>/.claude/skill_router.json are never suggested.
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
    "a", "an", "is", "it", "be", "as", "by", "at", "if", "user", "users", "create",
    "make", "claude", "claude's", "read", "before", "first", "step", "also", "other",
    "only", "even", "does", "do", "no", "new", "own", "via", "such", "like", "want",
    "wants", "asks", "ask", "named", "using", "them", "their", "they", "its", "has",
    "have", "should", "which", "what", "how", "then", "than", "over", "out", "about",
    "including", "includes", "trigger", "triggers", "skill.md", "tools", "tool", "so",
}
# Vietnamese / shorthand cues mapped to English description words
ALIASES = {
    "video": ["video", "shorts", "short", "render"],
    "thumbnail": ["thumbnail"], "anh bia": ["thumbnail"], "ảnh bìa": ["thumbnail"],
    "mau": ["colors"], "màu": ["colors"], "font": ["fonts"], "phong chu": ["fonts"],
    "thuong hieu": ["brand"], "thương hiệu": ["brand"], "kich ban": ["storyboard"],
    "kịch bản": ["storyboard"], "website": ["site"], "trang": ["site"], "bio": ["bio"],
    "giong doc": ["voice"], "giọng đọc": ["voice"], "kenh": ["channel"], "kênh": ["channel"],
    "tài liệu": ["document", "docs"], "tai lieu": ["document", "docs"], "văn bản": ["document"],
    "báo cáo": ["report", "document"], "bao cao": ["report", "document"],
    "bảng tính": ["spreadsheet", "xlsx"], "excel": ["spreadsheet", "xlsx"],
    "trình chiếu": ["slides", "presentation", "pptx"], "slide": ["slides", "presentation", "pptx"],
    "powerpoint": ["pptx", "presentation"], "word": ["docx", "word"], "pdf": ["pdf"],
    "nghiên cứu": ["research", "researching"], "nghien cuu": ["research", "researching"],
    "so sánh": ["comparing", "research"], "giải thích": ["explain", "understanding"],
    "dạy": ["teach", "explain"], "áp phích": ["poster", "design"], "poster": ["poster", "design"],
    "gif": ["gif", "gifs"], "trình duyệt": ["browser"], "máy tính": ["computer", "desktop"],
    "tạo skill": ["skill-creator", "skills"], "skill mới": ["skill-creator", "skills"],
    "mcp": ["mcp"], "google": ["google"], "sheets": ["sheets", "google"],
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


def _load_dir(pattern_root: Path, glob: str, prefix: str, min_hits: int, source: str) -> list:
    out = []
    for sk in sorted(pattern_root.glob(glob)):
        try:
            meta = _frontmatter(sk)
        except Exception:
            continue
        name = meta.get("name") or sk.parent.name
        out.append({"name": name, "call": prefix + name, "desc": meta.get("description", ""),
                    "min_hits": min_hits, "source": source})
    return out


def _excluded(repo: Path) -> set:
    cfg = repo / ".claude" / "skill_router.json"
    try:
        return {str(x) for x in json.loads(cfg.read_text(encoding="utf-8")).get("exclude", [])}
    except Exception:
        return set()


def collect_skills(repo: Path, home: Path) -> list:
    skills = _load_dir(repo / ".claude" / "skills", "*/SKILL.md", "", 1, "project")
    seen = {s["name"] for s in skills}
    user_dir = home / ".claude" / "skills"
    extra = _load_dir(user_dir / "synced", "*/*/SKILL.md", "anthropic-skills:", 2, "account")
    extra += [s for s in _load_dir(user_dir, "*/SKILL.md", "", 2, "personal") if s["name"] != "synced"]
    for s in extra:
        if s["name"] not in seen:
            skills.append(s)
            seen.add(s["name"])
    skip = _excluded(repo)
    return [s for s in skills if s["name"] not in skip and s["call"] not in skip]


def build_context(prompt: str, skills_dir: Path, home: Path = None) -> str:
    repo = skills_dir.parent.parent
    skills = collect_skills(repo, home if home is not None else Path.home())
    if not skills:
        return ""

    low = prompt.lower()
    p_words = _words(prompt)
    for cue, extra in ALIASES.items():
        if cue in low:
            p_words.update(extra)

    scored = []
    for sk in skills:
        d_words = _words(sk["name"].replace("-", " ") + " " + sk["name"] + " " + sk["desc"])
        hits = sorted(p_words & d_words)
        named = sk["name"].lower() in p_words or sk["name"].lower() in low
        if named and sk["name"] not in hits:
            hits.insert(0, sk["name"])
        if named or len(hits) >= sk["min_hits"]:
            # project skills first, then skills named outright, then by keyword overlap
            # a project skill jumps the queue only on a solid match (named, or 2+ keywords),
            # so one stray word cannot bury a better fit among hundreds of personal skills
            strong_project = sk["source"] == "project" and (named or len(hits) >= 2)
            rank = (1 if strong_project else 0, 1 if named else 0, len(hits))
            scored.append((rank, sk, hits))
    scored.sort(key=lambda t: t[0], reverse=True)

    project = [s["call"] for s in skills if s["source"] == "project"]
    lines = ["Project skills (.claude/skills): " + (", ".join(project) or "none") + "."]
    if scored:
        best = "; ".join(f"{sk['call']} (matched: {', '.join(h[:5])})" for _, sk, h in scored[:3])
        lines.append(
            f"This prompt matches: {best}. Before doing the work, invoke the best-fitting "
            "skill with the Skill tool and follow it. Project skills win over account skills "
            "on the same topic."
        )
    else:
        lines.append("If the request fits a project or account skill, invoke it with the Skill tool before acting.")
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
