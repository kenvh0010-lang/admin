"""Automated YouTube Data API v3 Uploader (Video + Thumbnail + SRT Captions + Top Comment + Ledger)."""

import json
import mimetypes
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone
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


def verify_youtube_channel(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Verify OAuth2 credentials and return connected YouTube channel metadata."""
    cid = (client_id or os.environ.get("YOUTUBE_CLIENT_ID", "")).strip()
    csec = (client_secret or os.environ.get("YOUTUBE_CLIENT_SECRET", "")).strip()
    rtok = (refresh_token or os.environ.get("YOUTUBE_REFRESH_TOKEN", "")).strip()

    if not (cid and csec and rtok):
        print("ℹ️  Missing YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN.")
        return None

    token = get_access_token(cid, csec, rtok)
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    items = data.get("items", [])
    if not items:
        raise RuntimeError("OAuth succeeded, but no YouTube channel was found on this Google account.")

    ch = items[0]
    info = {
        "channel_id": ch["id"],
        "title": ch["snippet"].get("title", ""),
        "custom_url": ch["snippet"].get("customUrl", ""),
        "subscribers": ch.get("statistics", {}).get("subscriberCount", "0"),
        "video_count": ch.get("statistics", {}).get("videoCount", "0"),
    }
    print(
        f"✅ Connected to YouTube Channel: {info['title']} ({info['custom_url'] or info['channel_id']}) "
        f"| Videos: {info['video_count']} | Subscribers: {info['subscribers']}"
    )
    return info


def build_youtube_description(storyboard: Dict[str, Any], slug: str = "") -> str:
    """Build a compliant, high-converting YouTube description with Bio & verbatim Amazon disclosure."""
    hook = storyboard.get("description_hook", storyboard.get("title", ""))
    aff = storyboard.get("affiliate_cta", {})
    offer_name = aff.get("offer_name", "Free Asymmetric Playbook & 5-Hour Asset Builder OS")
    article_url = f"{SITE_HOME_URL}articles/{slug}.html" if slug else SITE_HOME_URL

    chapters: List[str] = []
    for idx, sc in enumerate(storyboard.get("scenes", []), start=1):
        chapters.append(f"• Part {idx}: {sc.get('headline', sc.get('tag', 'Insight'))}")

    src_lines = "\n".join(f"• {s['label']}: {s['url']}" for s in storyboard.get("sources", []))
    sources_block = f"📰 Sources:\n{src_lines}\n\n" if src_lines else ""

    is_short = storyboard.get("format", "short") == "short"
    short_hashtags = "\n\n#shorts #wealthpsychology #mentalmodels #productivity" if is_short else ""

    return (
        f"{hook}\n\n"
        f"{sources_block}"
        f"⚡ {offer_name}:\n"
        f"👉 {SITE_BIO_URL}\n"
        f"📚 Full Written Breakdown, Citations & Book List:\n"
        f"👉 {article_url}\n\n"
        f"📌 Key Takeaways Covered:\n"
        f"{chr(10).join(chapters)}\n\n"
        f"⚠️ Disclosure: Educational content and historical/behavioral case studies only — not personalized "
        f"financial or legal advice. As an Amazon Associate I earn from qualifying purchases."
        f"{short_hashtags}"
    )


def upload_video_resumable(
    access_token: str,
    mp4_path: Path,
    storyboard: Dict[str, Any],
    slug: str = "",
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
            "description": build_youtube_description(storyboard, slug=slug),
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


def upload_srt_captions(access_token: str, video_id: str, srt_path: Path) -> None:
    """Upload English .srt closed captions for stronger YouTube Search SEO & accessibility."""
    if not srt_path.is_file():
        return
    boundary = "===============MindAndMarginCaptionBoundary=="
    meta_json = json.dumps({
        "snippet": {
            "videoId": video_id,
            "language": "en",
            "name": "English",
            "isDraft": False,
        }
    }).encode("utf-8")
    srt_bytes = srt_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode("utf-8") + meta_json + (
        f"\r\n--{boundary}\r\n"
        f"Content-Type: application/x-subrip\r\n\r\n"
    ).encode("utf-8") + srt_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/captions?uploadType=multipart&part=snippet",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60):
        pass


def post_top_affiliate_comment(access_token: str, video_id: str, storyboard: Dict[str, Any]) -> None:
    """Post the Day-1 monetization CTA + disclosure as the first top-level comment on the video."""
    aff = storyboard.get("affiliate_cta", {})
    raw_comment = aff.get("pinned_comment", "").strip()
    if not raw_comment:
        raw_comment = (
            f"📚 Grab the free Asymmetric Playbook, book list & 5-Hour Asset Builder OS here: {SITE_BIO_URL}"
        )
    if "Amazon Associate" not in raw_comment:
        raw_comment = f"{raw_comment}\n\n(Disclosure: As an Amazon Associate I earn from qualifying purchases.)"

    payload = json.dumps({
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {
                "snippet": {
                    "textOriginal": raw_comment,
                }
            },
        }
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30):
        pass


def load_ledger() -> Dict[str, Any]:
    if LEDGER_PATH.is_file():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {"published": {}}


def save_ledger(ledger: Dict[str, Any]) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pick_next_unpublished_storyboard() -> Optional[Path]:
    """Follow natural calendar order across all queued Shorts and Long-form storyboards."""
    from .config import discover_storyboards

    ledger = load_ledger()
    published = ledger.get("published", {})

    all_storyboards = discover_storyboards(CONTENT_DIR)
    shorts = [p for p in all_storyboards if p.stem.startswith("short_")]
    longs = [p for p in all_storyboards if p.stem.startswith("long_")]
    others = [p for p in all_storyboards if p not in shorts and p not in longs]

    ordered: List[Path] = []
    max_weeks = max(len(longs), (len(shorts) + 2) // 3)
    for w in range(max_weeks):
        ordered.extend(shorts[w * 3 : (w + 1) * 3])
        if w < len(longs):
            ordered.append(longs[w])
    ordered.extend(others)

    for sb in ordered:
        if sb.stem not in published:
            return sb
    return None


def _select_live_tts_provider() -> str:
    """Guarantee live YouTube uploads always use real neural speech rather than silent offline fallback."""
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if shutil.which("edge-tts"):
        return "edge"
    return "auto"


def publish_next_in_queue(privacy_status: str = "public") -> Optional[Dict[str, str]]:
    """Render (with guaranteed neural voice) and upload the next scheduled video + SRT + Thumbnail + Comment."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not (client_id and client_secret and refresh_token):
        print("ℹ️  YouTube OAuth secrets not set yet — skipping live YouTube API upload.")
        return None

    sb_path = pick_next_unpublished_storyboard()
    if not sb_path:
        print("🎉 All queued storyboards in content/ have already been published!")
        return None

    storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    tts_provider = _select_live_tts_provider()
    print(f"🎙️ Rendering next queued video '{sb_path.stem}' with TTS={tts_provider}...")
    outputs = render_project(storyboard_path=sb_path, output_dir=OUTPUT_DIR, tts_provider=tts_provider)
    access_token = get_access_token(client_id, client_secret, refresh_token)

    video_id = upload_video_resumable(
        access_token=access_token,
        mp4_path=outputs["video"],
        storyboard=storyboard,
        slug=sb_path.stem,
        privacy_status=privacy_status,
    )

    if storyboard.get("format") == "long":
        ai_thumbs = sorted((PROJECT_ROOT / "assets" / "thumbnails").glob(f"{sb_path.stem[:7]}*.jpg"))
        thumb_to_use = ai_thumbs[0] if ai_thumbs else outputs["thumbnail"]
        try:
            upload_custom_thumbnail(access_token, video_id, thumb_to_use)
        except Exception as exc:
            print(f"⚠️ Thumbnail upload skipped (verify phone number in YouTube Studio): {exc}")

    try:
        upload_srt_captions(access_token, video_id, outputs["srt"])
        print("   ✓ Uploaded English .srt closed captions.")
    except Exception as exc:
        print(f"⚠️ SRT caption upload skipped (optional youtube.force-ssl scope): {exc}")

    if privacy_status == "public":
        try:
            post_top_affiliate_comment(access_token, video_id, storyboard)
            print("   ✓ Posted Day-1 Affiliate CTA comment.")
        except Exception as exc:
            print(f"⚠️ Top comment skipped (enable youtube.force-ssl scope if desired): {exc}")

    ledger = load_ledger()
    ledger.setdefault("published", {})[sb_path.stem] = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": storyboard["title"],
        "privacy_status": privacy_status,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    save_ledger(ledger)
    print(f"✅ Auto-published to YouTube ({privacy_status}): https://youtu.be/{video_id}")
    return {"slug": sb_path.stem, "video_id": video_id, "url": f"https://youtu.be/{video_id}"}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "public"
    if arg in ("--verify", "verify"):
        verify_youtube_channel()
    else:
        publish_next_in_queue(privacy_status=arg)
