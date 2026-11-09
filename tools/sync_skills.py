#!/usr/bin/env python3
"""Copy agent skills (Antigravity, Gemini, Codex, any folder) into Claude Code's skill folder.

A skill is any directory that contains a SKILL.md whose YAML frontmatter has `name` and
`description`. Sources are scanned recursively, so skill packs nested a few levels deep
are found too.

Default is a DRY RUN that only reports what would happen. Add --apply to copy.

Examples (Windows PowerShell, from the repo folder):
  python tools/sync_skills.py                       # dry run: Antigravity -> %USERPROFILE%\\.claude\\skills
  python tools/sync_skills.py --apply               # copy for every Claude Code project on this PC
  python tools/sync_skills.py --to path\\to\\skills-repo\\.claude\\skills --apply   # for cloud sessions
"""

import argparse
import filecmp
import json
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
DEFAULT_SOURCES = [
    HOME / ".gemini" / "config" / "skills",
    HOME / ".gemini" / "antigravity" / "skills",
    HOME / ".gemini" / "skills",
    HOME / ".agents" / "skills",
    HOME / ".agent" / "skills",
]
DEFAULT_DEST = HOME / ".claude" / "skills"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "synced"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_SKILL_BYTES = 20 * 1024 * 1024


def read_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^﻿?---\s*\r?\n(.*?)\r?\n---", text, re.S)
    meta = {}
    if not m:
        return meta
    key = None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            meta[key] = val.strip("\"'") if val not in ("|", ">", "|-", ">-") else ""
        elif key and line.startswith((" ", "\t")):
            meta[key] = (meta[key] + " " + line.strip()).strip()
    return meta


def safe_name(raw: str) -> str:
    name = re.sub(r"[^a-z0-9-]+", "-", raw.strip().lower()).strip("-")
    return re.sub(r"-{2,}", "-", name)[:64]


def find_skills(root: Path, max_depth: int = 4):
    if not root.is_dir():
        return
    stack = [(root, 0)]
    while stack:
        d, depth = stack.pop()
        if (d / "SKILL.md").is_file():
            yield d
            continue  # a skill's own sub-folders are its resources, not more skills
        if depth >= max_depth:
            continue
        try:
            children = sorted(p for p in d.iterdir() if p.is_dir() and p.name not in SKIP_DIRS)
        except OSError:
            continue
        stack.extend((c, depth + 1) for c in reversed(children))


def _same_after_rename(src: Path, target: Path, name: str) -> bool:
    try:
        a = re.sub(r"(?m)^(name\s*:\s*).*$", lambda m: m.group(1) + name, (src / "SKILL.md").read_text(encoding="utf-8", errors="replace"), count=1)
        if a != (target / "SKILL.md").read_text(encoding="utf-8", errors="replace"):
            return False
        cmp = filecmp.dircmp(src, target, ignore=list(SKIP_DIRS) + ["SKILL.md"])
        return not (cmp.left_only or cmp.right_only or cmp.diff_files) and all(
            same_tree(src / d, target / d) for d in cmp.common_dirs)
    except OSError:
        return False


def dir_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


def same_tree(a: Path, b: Path) -> bool:
    cmp = filecmp.dircmp(a, b, ignore=list(SKIP_DIRS))
    if cmp.left_only or cmp.right_only or cmp.diff_files or cmp.funny_files:
        return False
    return all(same_tree(a / s, b / s) for s in cmp.common_dirs)


def _copy_skill(src: Path, target: Path, name: str) -> None:
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    md = target / "SKILL.md"
    text = md.read_text(encoding="utf-8", errors="replace")
    # Claude Code invokes a skill by its frontmatter name: make it match the folder name.
    fixed = re.sub(r"(?m)^(name\s*:\s*).*$", lambda m: m.group(1) + name, text, count=1)
    if fixed != text:
        md.write_text(fixed, encoding="utf-8")


def sync(sources, dest: Path, apply: bool, overwrite: bool) -> dict:
    report = {"dest": str(dest), "applied": apply, "sources": {}, "copied": [], "updated": [],
              "unchanged": [], "conflicts": [], "invalid": [], "too_big": []}
    planned = {}
    for src in sources:
        found = list(find_skills(Path(src)))
        report["sources"][str(src)] = len(found)
        for sk in found:
            meta = read_frontmatter(sk / "SKILL.md")
            raw_name = meta.get("name") or sk.name
            name = safe_name(raw_name)
            if not meta.get("description") or not NAME_RE.match(name):
                report["invalid"].append({"path": str(sk), "reason": "missing name/description in frontmatter"})
                continue
            if dir_size(sk) > MAX_SKILL_BYTES:
                report["too_big"].append(str(sk))
                continue
            if name in planned:
                if not same_tree(planned[name], sk):
                    report["conflicts"].append({"name": name, "kept": str(planned[name]), "skipped": str(sk)})
                continue
            planned[name] = sk

    if apply:
        dest.mkdir(parents=True, exist_ok=True)
    for name, sk in sorted(planned.items()):
        target = dest / name
        if target.exists():
            if same_tree(sk, target) or _same_after_rename(sk, target, name):
                report["unchanged"].append(name)
                continue
            if not overwrite:
                report["conflicts"].append({"name": name, "kept": str(target), "skipped": str(sk),
                                            "hint": "already in destination with different content; use --overwrite"})
                continue
            if apply:
                shutil.rmtree(target)
                _copy_skill(sk, target, name)
            report["updated"].append(name)
        else:
            if apply:
                _copy_skill(sk, target, name)
            report["copied"].append(name)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="sources", action="append", help="Source folder (repeatable). Default: Antigravity/Gemini skill folders.")
    ap.add_argument("--to", dest="dest", default=str(DEFAULT_DEST), help=f"Destination (default: {DEFAULT_DEST})")
    ap.add_argument("--apply", action="store_true", help="Actually copy. Without it this is a dry run.")
    ap.add_argument("--overwrite", action="store_true", help="Replace destination skills whose content differs.")
    ap.add_argument("--report", default=None, help="Write the full JSON report to this file.")
    args = ap.parse_args(argv)

    sources = [Path(s).expanduser() for s in (args.sources or DEFAULT_SOURCES)]
    rep = sync(sources, Path(args.dest).expanduser(), args.apply, args.overwrite)

    print(("APPLIED" if args.apply else "DRY RUN (add --apply to copy)") + f" -> {rep['dest']}")
    for src, n in rep["sources"].items():
        print(f"  source {src}: {n} skill folders" + ("" if Path(src).is_dir() else " (not found)"))
    for key in ("copied", "updated", "unchanged", "conflicts", "invalid", "too_big"):
        print(f"  {key:9s}: {len(rep[key])}")
    for c in rep["conflicts"][:10]:
        print(f"    conflict {c['name']}: kept {c['kept']}, skipped {c['skipped']}")
    for i in rep["invalid"][:10]:
        print(f"    invalid  {i['path']}: {i['reason']}")
    if args.report:
        Path(args.report).write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  full report: {args.report}")
    if not any(Path(s).is_dir() for s in sources):
        print("No source folder found. Pass your skills folder with --from <path>.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
