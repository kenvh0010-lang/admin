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


def _normalize_oauth_secret(raw: str, field_name: str) -> str:
    """Strip accidental quotes/whitespace or extract field from pasted Google OAuth JSON."""
    val = (raw or "").strip()
    if val.startswith("{") and val.endswith("}"):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                for container in (parsed, parsed.get("web") or {}, parsed.get("installed") or {}):
                    if isinstance(container, dict) and container.get(field_name):
                        return str(container[field_name]).strip()
        except json.JSONDecodeError:
            pass
    return val.strip().strip('"').strip("'").strip()


def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Exchange OAuth2 refresh token for a fresh YouTube Data API v3 access token."""
    import urllib.error

    cid = _normalize_oauth_secret(client_id, "client_id")
    csec = _normalize_oauth_secret(client_secret, "client_secret")
    rtok = _normalize_oauth_secret(refresh_token, "refresh_token")

    payload = urllib.parse.urlencode({
        "client_id": cid,
        "client_secret": csec,
        "refresh_token": rtok,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["access_token"]
    except urllib.error.HTTPError as exc:
        err_code = "unknown"
        err_desc = ""
        try:
            err_json = json.loads(exc.read().decode("utf-8", errors="replace"))
            err_code = str(err_json.get("error", "unknown"))
            err_desc = str(err_json.get("error_description", ""))
        except Exception:
            pass
        placeholder_words = ("placeholder", "your_", "dummy", "example", "todo", "xxx", "changeme")
        has_placeholder = any(
            w in s.lower() for s in (cid, csec, rtok) for w in placeholder_words
        )
        diag = (
            f"OAuth token exchange failed (HTTP {exc.code}: {err_code}"
            f"{' - ' + err_desc if err_desc else ''}). "
            f"Format check: client_id_googleusercontent={cid.endswith('.apps.googleusercontent.com')}, "
            f"client_secret_gocspx={csec.startswith('GOCSPX-')}, "
            f"refresh_token_1slash={rtok.startswith('1//')}, "
            f"placeholder_detected={has_placeholder}, "
            f"lengths=({len(cid)}, {len(csec)}, {len(rtok)})."
        )
        raise RuntimeError(diag) from None


def _api_get_json(url: str, access_token: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_youtube_channel(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Verify OAuth2 credentials, audit internal channel/video/analytics stats, and sync empty channel bio."""
    import urllib.error

    cid = _normalize_oauth_secret(client_id or os.environ.get("YOUTUBE_CLIENT_ID", ""), "client_id")
    csec = _normalize_oauth_secret(client_secret or os.environ.get("YOUTUBE_CLIENT_SECRET", ""), "client_secret")
    rtok = _normalize_oauth_secret(refresh_token or os.environ.get("YOUTUBE_REFRESH_TOKEN", ""), "refresh_token")

    if not (cid and csec and rtok):
        print("ℹ️  Missing YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN.")
        return None

    token = get_access_token(cid, csec, rtok)

    scopes = "unknown"
    try:
        ti_url = f"https://oauth2.googleapis.com/tokeninfo?access_token={urllib.parse.quote(token)}"
        with urllib.request.urlopen(urllib.request.Request(ti_url, method="GET"), timeout=15) as resp:
            ti = json.loads(resp.read().decode("utf-8"))
        scopes = str(ti.get("scope", "none"))
    except Exception as exc:
        scopes = f"tokeninfo-unavailable ({type(exc).__name__})"
    print(f"🔑 OAuth Scopes: {scopes}")

    data = _api_get_json(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,status,brandingSettings&mine=true",
        token,
    )
    items = data.get("items", [])
    if not items:
        raise RuntimeError("OAuth succeeded, but no YouTube channel was found on this Google account.")

    ch = items[0]
    stats = ch.get("statistics", {})
    ch_status = ch.get("status", {})
    branding_ch = dict((ch.get("brandingSettings") or {}).get("channel") or {})
    desc = str(branding_ch.get("description") or "").strip()

    info = {
        "channel_id": ch["id"],
        "title": ch["snippet"].get("title", ""),
        "custom_url": ch["snippet"].get("customUrl", ""),
        "subscribers": stats.get("subscriberCount", "0"),
        "total_views": stats.get("viewCount", "0"),
        "video_count": stats.get("videoCount", "0"),
        "long_uploads_status": ch_status.get("longUploadsStatus", "unknown"),
        "is_linked": ch_status.get("isLinked"),
        "description_len": len(desc),
        "bio_link_in_channel_desc": "kenvh0010-lang.github.io" in desc,
    }
    print(
        f"✅ Connected to YouTube Channel: {info['title']} ({info['custom_url'] or info['channel_id']}) "
        f"| Videos: {info['video_count']} | Views: {info['total_views']} | Subscribers: {info['subscribers']}"
    )
    print(
        f"📋 Channel Status: longUploadsStatus={info['long_uploads_status']} | isLinked={info['is_linked']} "
        f"| madeForKids={ch_status.get('madeForKids')} | desc_len={info['description_len']} "
        f"| bio_link_in_desc={info['bio_link_in_channel_desc']}"
    )

    if not desc:
        default_desc = (
            "Documentary Shorts breaking down federal lawsuits, SEC/FTC/CFPB enforcement orders, "
            "and costly corporate blunders using primary court filings.\n\n"
            f"Primary Case Dossier & Resources: {SITE_BIO_URL}\n"
            f"Full Written Exhibits: {SITE_HOME_URL}\n\n"
            "Educational analysis only — not financial or legal advice. "
            "As an Amazon Associate I earn from qualifying purchases."
        )
        update_payload = json.dumps({
            "id": ch["id"],
            "brandingSettings": {
                "channel": {
                    "description": default_desc,
                    "keywords": '"federal lawsuits" "SEC enforcement" "FTC refunds" "CFPB orders" "financial forensics"',
                    "country": branding_ch.get("country") or "US",
                }
            },
        }).encode("utf-8")
        try:
            put_req = urllib.request.Request(
                "https://www.googleapis.com/youtube/v3/channels?part=brandingSettings",
                data=update_payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                method="PUT",
            )
            with urllib.request.urlopen(put_req, timeout=30):
                print("✏️ Updated empty YouTube channel description & keywords via brandingSettings.")
        except urllib.error.HTTPError as exc:
            print(f"ℹ️ Skipped channel description sync (HTTP {exc.code}).")
        except Exception as exc:
            print(f"ℹ️ Skipped channel description sync ({type(exc).__name__}).")

    ledger_pub = load_ledger().get("published", {})
    vid_ids = [str(e.get("video_id", "")).strip() for e in ledger_pub.values() if isinstance(e, dict) and e.get("video_id")]
    if vid_ids:
        v_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet,statistics,status,contentDetails&id={urllib.parse.quote(','.join(vid_ids))}"
        )
        try:
            v_data = _api_get_json(v_url, token)
            print("🎬 Published Video Internal Status:")
            for item in v_data.get("items", []):
                vs = item.get("statistics", {})
                vst = item.get("status", {})
                vcd = item.get("contentDetails", {})
                vsn = item.get("snippet", {})
                print(
                    f"  - {item['id']} | {vsn.get('publishedAt', '?')} | {vcd.get('duration', '?')} "
                    f"| views={vs.get('viewCount', '0')} likes={vs.get('likeCount', '0')} comments={vs.get('commentCount', '0')} "
                    f"| privacy={vst.get('privacyStatus')} upload={vst.get('uploadStatus')} "
                    f"madeForKids={vst.get('madeForKids')} synthetic={vst.get('containsSyntheticMedia')} "
                    f"licensed={vcd.get('licensedContent')}"
                )
        except Exception as exc:
            print(f"ℹ️ Could not fetch videos.list details ({type(exc).__name__}).")

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ana_url = (
        "https://youtubeanalytics.googleapis.com/v2/reports"
        f"?ids=channel%3D%3DMINE&startDate=2026-11-01&endDate={today_utc}"
        "&metrics=views,engagedViews,likes,comments,shares,subscribersGained,estimatedMinutesWatched,averageViewDuration,averageViewPercentage"
        "&dimensions=video&sort=-views"
    )
    try:
        ana = _api_get_json(ana_url, token)
        headers = [h.get("name") for h in ana.get("columnHeaders", [])]
        print(f"📊 YouTube Analytics ({len(ana.get('rows') or [])} rows): {headers}")
        for row in ana.get("rows") or []:
            print(f"  {row}")
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            print("ℹ️ YouTube Analytics API: token lacks yt-analytics.readonly scope (HTTP 403) — check Studio UI for swipe/retention.")
        else:
            print(f"ℹ️ YouTube Analytics API unavailable (HTTP {exc.code}).")
    except Exception as exc:
        print(f"ℹ️ YouTube Analytics API unavailable ({type(exc).__name__}).")

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
    short_hashtags = "\n\n#shorts #lawsuit #financenews #consumerprotection" if is_short else ""

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
            "tags": storyboard.get("tags", ["federal lawsuit", "sec enforcement", "consumer protection"]),
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
    """Follow natural calendar order and skip any storyboard matching a published slug, title, or case URL."""
    from .config import discover_storyboards
    from .deduper import normalize_source_url, normalize_title

    ledger = load_ledger()
    published = ledger.get("published", {})
    published_titles = {
        normalize_title(str(entry.get("title", "")))
        for entry in published.values()
        if isinstance(entry, dict) and entry.get("title")
    }
    published_urls = {
        normalize_source_url(str(u))
        for entry in published.values()
        if isinstance(entry, dict)
        for u in (entry.get("source_urls") or [])
        if u
    }

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
        if sb.stem in published:
            continue
        try:
            data = json.loads(sb.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        norm_t = normalize_title(str(data.get("title", "")))
        if norm_t and norm_t in published_titles:
            continue
        sb_urls = {
            normalize_source_url(str(s.get("url", "")))
            for s in (data.get("sources") or [])
            if isinstance(s, dict) and s.get("url")
        }
        if sb_urls and (sb_urls & published_urls):
            continue
        return sb
    return None


def _select_live_tts_provider() -> str:
    """Guarantee live YouTube uploads always use real neural speech rather than silent offline fallback."""
    from .tts_engine import EDGE_TTS_INSTALL_HINT, resolve_edge_tts_command

    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if resolve_edge_tts_command() is not None:
        return "edge"
    raise RuntimeError(f"Refusing live YouTube upload without neural voiceover. {EDGE_TTS_INSTALL_HINT}")


def publish_next_in_queue(privacy_status: str = "public") -> Optional[Dict[str, str]]:
    """Render (with guaranteed neural voice) and upload the next scheduled video + SRT + Thumbnail + Comment."""
    client_id = _normalize_oauth_secret(os.environ.get("YOUTUBE_CLIENT_ID", ""), "client_id")
    client_secret = _normalize_oauth_secret(os.environ.get("YOUTUBE_CLIENT_SECRET", ""), "client_secret")
    refresh_token = _normalize_oauth_secret(os.environ.get("YOUTUBE_REFRESH_TOKEN", ""), "refresh_token")

    if not (client_id and client_secret and refresh_token):
        print("ℹ️  YouTube OAuth secrets not set yet — skipping live YouTube API upload.")
        return None

    # Fail fast (<1s) if OAuth credentials are invalid before spending CPU rendering video
    access_token = get_access_token(client_id, client_secret, refresh_token)

    sb_path = pick_next_unpublished_storyboard()
    if not sb_path:
        print("🎉 All queued storyboards in content/ have already been published!")
        return None

    storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    tts_provider = _select_live_tts_provider()
    print(f"🎙️ Rendering next queued video '{sb_path.stem}' with TTS={tts_provider}...")
    outputs = render_project(
        storyboard_path=sb_path,
        output_dir=OUTPUT_DIR,
        tts_provider=tts_provider,
        skip_existing=True,
    )
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
        if os.environ.get("YT_ENABLE_AUTO_COMMENT", "").strip() == "1":
            try:
                post_top_affiliate_comment(access_token, video_id, storyboard)
                print("   ✓ Posted Day-1 Affiliate CTA comment.")
            except Exception as exc:
                print(f"⚠️ Top comment skipped (enable youtube.force-ssl scope if desired): {exc}")
        else:
            print("ℹ️ Skipping auto-comment on Shorts (set YT_ENABLE_AUTO_COMMENT=1 to re-enable).")

    ledger = load_ledger()
    ledger.setdefault("published", {})[sb_path.stem] = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": storyboard["title"],
        "privacy_status": privacy_status,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "source_urls": [str(s["url"]) for s in (storyboard.get("sources") or []) if isinstance(s, dict) and s.get("url")],
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
