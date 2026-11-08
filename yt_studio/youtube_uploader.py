"""Automated YouTube Data API v3 Uploader (Video + Thumbnail + SRT Captions + Ledger)."""

import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .config import CONTENT_DIR, OUTPUT_DIR, PROJECT_ROOT
from .video_renderer import render_project

LEDGER_PATH = CONTENT_DIR / "published_ledger.json"
SITE_BIO_URL = "https://kenvh0010-lang.github.io/admin/bio/"
SITE_HOME_URL = "https://kenvh0010-lang.github.io/admin/"


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange OAuth2 refresh token for a fresh YouTube Data API v3 access token."""
    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["access_token"]


def build_youtube_description(storyboard: Dict[str, Any]) -> str:
    """Build a compliant, high-converting YouTube description with Bio & Amazon disclosures."""
    hook = storyboard.get("description_hook", storyboard.get("title", ""))
    aff = storyboard.get("affiliate_cta", {})
    offer_name = aff.get("offer_name", "Free Asymmetric Playbook & 5-Hour Asset Builder OS")

    chapters: List[str] = []
    for idx, sc in enumerate(storyboard.get("scenes", []), start=1):
        chapters.append(f"• Part {idx}: {sc.get('headline', sc.get('tag', 'Insight'))}")

    is_short = storyboard.get("format", "short") == "short"
    short_hashtags = "\n\n#shorts #wealthpsychology #mentalmodels #productivity" if is_short else ""

    return (
        f"{hook}\n\n"
        f"⚡ {offer_name}:\n"
        f"👉 {SITE_BIO_URL}\n"
        f"📚 Full Written Breakdown & Book List:\n"
        f"👉 {SITE_HOME_URL}\n\n"
        f"📌 Key Takeaways Covered:\n"
        f"{chr(10).join(chapters)}\n\n"
        f"⚠️ Disclosure: Educational content and historical/behavioral case studies only — not personalized "
        f"financial or legal advice. As an Amazon Associate I earn from qualifying purchases at no extra cost to you."
        f"{short_hashtags}"
    )


def upload_video_resumable(
    access_token: str,
    mp4_path: Path,
    storyboard: Dict[str, Any],
    privacy_status: str = "public",
) -> str:
    """Upload MP4 to YouTube via Resumable Upload protocol and return videoId."""
    is_short = storyboard.get("format", "short") == "short"
    raw_title = storyboard["title"]
    if is_short and "#shorts" not in raw_title.lower() and len(raw_title) <= 90:
        title = f"{raw_title} #Shorts"
    else:
        title = raw_title[:100]

    metadata = {
        "snippet": {
            "title": title,
            "description": build_youtube_description(storyboard),
            "tags": storyboard.get("tags", ["wealth psychology", "mental models", "self improvement"]),
            "categoryId": "27",  # Education (high-CPM advertiser safe)
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    body_bytes = json.dumps(metadata).encode("utf-8")
    mp4_size = mp4_path.stat().st_size

    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=body_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(mp4_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        method="POST",
    )
    with urllib.request.urlopen(init_req, timeout=45) as init_resp:
        upload_url = init_resp.headers["Location"]

    video_bytes = mp4_path.read_bytes()
    put_req = urllib.request.Request(
        upload_url,
        data=video_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Length": str(mp4_size),
            "Content-Type": "video/mp4",
        },
        method="PUT",
    )
    with urllib.request.urlopen(put_req, timeout=300) as put_resp:
        result = json.loads(put_resp.read().decode("utf-8"))
    return result["id"]


def upload_custom_thumbnail(access_token: str, video_id: str, thumb_path: Path) -> None:
    """Set custom thumbnail for long-form videos (requires phone-verified YouTube channel)."""
    if not thumb_path.is_file():
        return
    mime = mimetypes.guess_type(str(thumb_path))[0] or "image/png"
    img_bytes = thumb_path.read_bytes()
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
        data=img_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": mime,
            "Content-Length": str(len(img_bytes)),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60):
        pass


def load_ledger() -> Dict[str, Any]:
    if LEDGER_PATH.is_file():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {"published": {}}


def save_ledger(ledger: Dict[str, Any]) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pick_next_unpublished_storyboard() -> Optional[Path]:
    """Follow calendar order: 3 Shorts then 1 Long-form per week."""
    ledger = load_ledger()
    published = ledger.get("published", {})

    shorts = sorted(CONTENT_DIR.glob("short_*.json"))
    longs = sorted(CONTENT_DIR.glob("long_*.json"))

    ordered: List[Path] = []
    max_weeks = max(len(longs), (len(shorts) + 2) // 3)
    for w in range(max_weeks):
        ordered.extend(shorts[w * 3 : (w + 1) * 3])
        if w < len(longs):
            ordered.append(longs[w])

    for sb in ordered:
        if sb.stem not in published:
            return sb
    return None


def publish_next_in_queue(privacy_status: str = "public") -> Optional[Dict[str, str]]:
    """Render (with neural voice if available) and upload the next scheduled video."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not (client_id and client_secret and refresh_token):
        print("ℹ️  YouTube OAuth secrets not set yet — skipping live YouTube API upload (videos still rendered).")
        return None

    sb_path = pick_next_unpublished_storyboard()
    if not sb_path:
        print("🎉 All queued storyboards in content/ have already been published!")
        return None

    storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    outputs = render_project(storyboard_path=sb_path, output_dir=OUTPUT_DIR, tts_provider="auto")
    access_token = get_access_token(client_id, client_secret, refresh_token)

    video_id = upload_video_resumable(
        access_token=access_token,
        mp4_path=outputs["video"],
        storyboard=storyboard,
        privacy_status=privacy_status,
    )

    if storyboard.get("format") == "long":
        ai_thumbs = sorted((PROJECT_ROOT / "assets" / "thumbnails").glob(f"{sb_path.stem[:7]}*.jpg"))
        thumb_to_use = ai_thumbs[0] if ai_thumbs else outputs["thumbnail"]
        try:
            upload_custom_thumbnail(access_token, video_id, thumb_to_use)
        except Exception as exc:
            print(f"⚠️ Thumbnail upload skipped (verify phone number in YouTube Studio): {exc}")

    ledger = load_ledger()
    ledger.setdefault("published", {})[sb_path.stem] = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": storyboard["title"],
    }
    save_ledger(ledger)
    print(f"✅ Auto-published to YouTube: https://youtu.be/{video_id}")
    return {"slug": sb_path.stem, "video_id": video_id, "url": f"https://youtu.be/{video_id}"}


if __name__ == "__main__":
    privacy = sys.argv[1] if len(sys.argv) > 1 else "public"
    publish_next_in_queue(privacy_status=privacy)
