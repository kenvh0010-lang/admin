"""Multi-layer project, storyboard, asset, and output deduplication engine."""

from __future__ import annotations

from collections import defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Set, Tuple
import urllib.parse

from .config import ASSETS_DIR, CONTENT_DIR, OUTPUT_DIR, PROJECT_ROOT, discover_storyboards

STOPWORDS: Set[str] = {
    "million", "billion", "dollars", "dollar", "court", "federal", "users",
    "percent", "settled", "without", "admitting", "alleged", "alleges",
    "company", "their", "about", "after", "before", "under", "these",
    "where", "while", "there", "which", "would", "could", "every", "never",
    "check", "first", "inside", "still", "order", "settlement", "lawsuit",
}


def normalize_title(text: str) -> str:
    """Normalize a video title for strict duplicate detection."""
    cleaned = re.sub(r"#shorts\b", "", (text or "").lower())
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned).strip()
    return cleaned


def normalize_source_url(url: str) -> str:
    """Canonicalize an HTTPS source URL so trailing slashes or fragments cannot hide duplicates."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlsplit(raw)
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def _topic_tokens(data: Dict[str, Any]) -> Set[str]:
    blob = " ".join(
        [str(data.get("title", "")), str(data.get("description_hook", ""))]
        + [str(sc.get("narration", "")) for sc in data.get("scenes", [])]
    ).lower()
    tokens = set(re.findall(r"[a-z0-9]{4,}", blob))
    return tokens - STOPWORDS


def collect_active_referenced_evidence(content_dir: Path = CONTENT_DIR) -> Set[str]:
    """Return relative POSIX paths (e.g. 'assets/evidence/suno/cbs.png') used by active storyboards."""
    used: Set[str] = set()
    for sb in discover_storyboards(content_dir):
        data = json.loads(sb.read_text(encoding="utf-8"))
        for sc in data.get("scenes", []):
            ev = str(sc.get("evidence_image", "")).strip()
            if ev:
                used.add(Path(ev).as_posix())
    return used


def audit_and_dedupe_projects(
    content_dir: Path = CONTENT_DIR,
    output_dir: Path = OUTPUT_DIR,
    assets_dir: Path = ASSETS_DIR,
    project_root: Path = PROJECT_ROOT,
    similarity_threshold: float = 0.30,
    apply_cleanup: bool = False,
) -> Dict[str, Any]:
    """Audit all active storyboards, outputs, and assets for duplicates or orphaned remnants."""
    storyboards = discover_storyboards(content_dir)

    stem_map: Dict[str, List[str]] = defaultdict(list)
    title_map: Dict[str, List[str]] = defaultdict(list)
    url_map: Dict[str, Set[str]] = defaultdict(set)
    crop_map: Dict[Tuple[str, Tuple[int, ...]], Set[str]] = defaultdict(set)
    token_sets: List[Tuple[str, Set[str]]] = []
    referenced_ev: Set[str] = set()

    for sb in storyboards:
        rel_sb = sb.relative_to(project_root).as_posix() if sb.is_relative_to(project_root) else sb.name
        stem_map[sb.stem].append(rel_sb)
        data = json.loads(sb.read_text(encoding="utf-8"))

        for key in ("title", "alt_title_1", "alt_title_2"):
            val = str(data.get(key, "")).strip()
            if val:
                norm_t = normalize_title(val)
                if norm_t:
                    title_map[norm_t].append(f"{sb.stem}:{key}")

        for src in data.get("sources", []):
            norm_u = normalize_source_url(str(src.get("url", "")))
            if norm_u:
                url_map[norm_u].add(sb.stem)

        for sc in data.get("scenes", []):
            ev = str(sc.get("evidence_image", "")).strip()
            if ev:
                ev_posix = Path(ev).as_posix()
                referenced_ev.add(ev_posix)
                crop = tuple(int(v) for v in (sc.get("evidence_crop") or []))
                crop_map[(ev_posix, crop)].add(sb.stem)

        token_sets.append((sb.stem, _topic_tokens(data)))

    duplicate_stems = {k: v for k, v in stem_map.items() if len(v) > 1}
    duplicate_titles = {k: v for k, v in title_map.items() if len(v) > 1}
    duplicate_source_urls = {k: sorted(v) for k, v in url_map.items() if len(v) > 1}
    duplicate_scene_crops = {
        f"{img}@{list(crop)}": sorted(stems)
        for (img, crop), stems in crop_map.items()
        if len(stems) > 1
    }

    high_similarity_pairs: List[Dict[str, Any]] = []
    for (s1, w1), (s2, w2) in combinations(token_sets, 2):
        jac = len(w1 & w2) / max(1, len(w1 | w2))
        if jac >= similarity_threshold:
            high_similarity_pairs.append(
                {
                    "pair": [s1, s2],
                    "jaccard": round(jac, 3),
                    "shared_terms": sorted(w1 & w2)[:12],
                }
            )

    active_stems = {sb.stem for sb in storyboards}
    orphaned_outputs: List[str] = []
    removed_outputs: List[str] = []
    if output_dir.is_dir():
        for child in sorted(output_dir.iterdir()):
            if child.is_dir() and child.name not in active_stems:
                rel_out = child.relative_to(project_root).as_posix() if child.is_relative_to(project_root) else child.name
                if apply_cleanup:
                    shutil.rmtree(child)
                    removed_outputs.append(rel_out)
                else:
                    orphaned_outputs.append(rel_out)

    unreferenced_evidence: List[str] = []
    removed_evidence: List[str] = []
    ev_root = assets_dir / "evidence"
    if ev_root.is_dir():
        for ev_file in sorted(p for p in ev_root.rglob("*") if p.is_file()):
            rel_ev = ev_file.relative_to(project_root).as_posix()
            if rel_ev not in referenced_ev:
                if apply_cleanup:
                    ev_file.unlink()
                    removed_evidence.append(rel_ev)
                else:
                    unreferenced_evidence.append(rel_ev)
        if apply_cleanup:
            for sub in sorted((d for d in ev_root.rglob("*") if d.is_dir()), reverse=True):
                if not any(sub.iterdir()):
                    sub.rmdir()

    hash_groups: Dict[str, List[str]] = defaultdict(list)
    if assets_dir.is_dir():
        for asset_file in sorted(p for p in assets_dir.rglob("*") if p.is_file()):
            digest = hashlib.sha256(asset_file.read_bytes()).hexdigest()
            rel_asset = asset_file.relative_to(project_root).as_posix()
            hash_groups[digest].append(rel_asset)
    duplicate_asset_binaries = [paths for paths in hash_groups.values() if len(paths) > 1]

    is_clean = not any(
        (
            duplicate_stems,
            duplicate_titles,
            duplicate_source_urls,
            duplicate_scene_crops,
            high_similarity_pairs,
            orphaned_outputs,
            unreferenced_evidence,
            duplicate_asset_binaries,
        )
    )

    return {
        "is_clean": is_clean,
        "active_projects": len(storyboards),
        "referenced_evidence_files": len(referenced_ev),
        "duplicate_stems": duplicate_stems,
        "duplicate_titles": duplicate_titles,
        "duplicate_source_urls": duplicate_source_urls,
        "duplicate_scene_crops": duplicate_scene_crops,
        "high_similarity_pairs": high_similarity_pairs,
        "orphaned_outputs": orphaned_outputs,
        "unreferenced_evidence": unreferenced_evidence,
        "duplicate_asset_binaries": duplicate_asset_binaries,
        "removed_outputs": removed_outputs,
        "removed_evidence": removed_evidence,
    }
