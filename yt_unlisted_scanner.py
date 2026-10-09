# /usr/bin/env python3

import argparse
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Set, Optional
import yt_dlp

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def parse_args():
    epilog_text = """
Usage Examples:
  1. Scan a channel using a handle (includes Playlists, Filmot, and Wayback):
     python yt_unlisted_scanner.py "@thathalfazn7467" --filmot-key "YOUR_API_KEY"

  2. Save results to a custom JSON file path:
     python yt_unlisted_scanner.py "@thathalfazn7467" -o results/unlisted.json

  3. Scan using a direct Channel ID (starts with 'UC'):
     python yt_unlisted_scanner.py UC1234567890abcdefghijklg

  4. Skip Filmot or Wayback scans:
     python yt_unlisted_scanner.py "@thathalfazn7467" --skip-filmot
     python yt_unlisted_scanner.py "@thathalfazn7467" --skip-wayback

  5. Increase retry attempts for HTTP requests (e.g., during high server load):
     python yt_unlisted_scanner.py "@thathalfazn7467" --max-retries 10
"""
    parser = argparse.ArgumentParser(
        prog="yt_unlisted_scanner.py",
        description="Scan, discover, and export unlisted YouTube videos from playlists, Filmot, and Wayback Machine archives.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "channel_url",
        help="YouTube channel URL, handle, or ID.\nExamples: @ChannelName, UCxxxxxx, or https://www.youtube.com/@ChannelName",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="unlisted_videos.json",
        metavar="FILE",
        help="Path to the output JSON file (default: unlisted_videos.json)",
    )
    parser.add_argument(
        "--filmot-key",
        metavar="KEY",
        help="Your Filmot API key (required for querying Filmot without getting HTTP 401)",
    )
    parser.add_argument(
        "--skip-wayback",
        action="store_true",
        help="Skip searching the Internet Archive / Wayback Machine CDX API",
    )
    parser.add_argument(
        "--skip-filmot",
        action="store_true",
        help="Skip searching the Filmot unlisted video database",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        metavar="N",
        help="Maximum exponential backoff retry attempts for HTTP requests (default: 5)",
    )
    return parser.parse_args()


def fetch_url_with_retry(
    url: str,
    headers: dict = HEADERS,
    max_retries: int = 5,
    initial_backoff: float = 2.0,
    timeout: int = 15,
) -> Optional[bytes]:
    """Fetches content from a URL using exponential backoff and jitter for transient errors."""
    backoff = initial_backoff

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()

        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                if attempt == max_retries:
                    print(f"  [!] HTTP {e.code} for URL - max retries ({max_retries}) reached.")
                    return None

                jitter = random.uniform(0.0, 0.5)
                sleep_time = backoff + jitter
                print(
                    f"  [!] HTTP {e.code} (Rate Limit/Server Error). Retrying in {sleep_time:.1f}s (Attempt {attempt}/{max_retries})..."
                )
                time.sleep(sleep_time)
                backoff *= 2

            elif e.code == 401:
                if "filmot.com" in url:
                    print("  [!] HTTP 401 Unauthorized: Filmot API rejected the request.")
                    print(
                        "  [!] Please supply a valid Filmot API key using the --filmot-key argument."
                    )
                else:
                    print(f"  [!] HTTP 401 Unauthorized for URL: {url}")
                return None
            else:
                print(f"  [!] Non-retriable HTTP Error {e.code} for URL.")
                return None

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == max_retries:
                print(f"  [!] Connection failed: {e} - max retries ({max_retries}) reached.")
                return None

            jitter = random.uniform(0.0, 0.5)
            sleep_time = backoff + jitter
            print(
                f"  [!] Network/Timeout error ({e}). Retrying in {sleep_time:.1f}s (Attempt {attempt}/{max_retries})..."
            )
            time.sleep(sleep_time)
            backoff *= 2

    return None


def normalize_channel_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        if url.startswith("@"):
            url = f"https://www.youtube.com/{url}"
        elif url.startswith("UC"):
            url = f"https://www.youtube.com/channel/{url}"
        else:
            url = f"https://www.youtube.com/c/{url}"
    return url


def resolve_canonical_channel_id(channel_url: str) -> Optional[str]:
    """Resolves any YouTube URL or Handle to its canonical 'UC...' Channel ID."""
    clean_url = normalize_channel_url(channel_url)

    # 1. Direct match if a 24-character UC... ID was passed directly
    uc_match = re.search(r"^(UC[a-zA-Z0-9_-]{22})$", channel_url.strip())
    if uc_match:
        return uc_match.group(1)

    # 2. Try extraction using yt-dlp
    opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(clean_url, download=False)
        if info:
            ch_id = info.get("channel_id") or info.get("id")
            if ch_id and ch_id.startswith("UC") and len(ch_id) == 24:
                return ch_id

    # 3. Fallback HTML page regex scraper
    html_bytes = fetch_url_with_retry(clean_url, max_retries=2, timeout=10)
    if html_bytes:
        html = html_bytes.decode("utf-8", errors="ignore")
        patterns = [
            r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"',
            r'itemprop="channelId"\s+content="(UC[a-zA-Z0-9_-]{22})"',
            r"https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)

    return None


def extract_video_ids_from_text(text: str) -> Set[str]:
    """Extracts 11-character YouTube video IDs from text, HTML, XML, or JSON payloads."""
    patterns = [
        r"(?:v=|\/embed\/|\/v\/|watch\?v%3D|watch\?v=)([a-zA-Z0-9_-]{11})",
        r"<yt:videoId>([a-zA-Z0-9_-]{11})</yt:videoId>",
        r'"id"\s*:\s*"([a-zA-Z0-9_-]{11})"',
    ]
    found_ids = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        found_ids.update(matches)
    return found_ids


def fetch_filmot_candidate_ids(
    channel_id: str, api_key: Optional[str] = None, max_retries: int = 5
) -> Set[str]:
    """Queries the Filmot database API for unlisted video IDs associated with the Channel ID."""
    candidate_ids: Set[str] = set()
    print(f"[*] Querying Filmot database for Channel ID: {channel_id}...")

    if not api_key:
        print("  [!] Notice: No Filmot API key provided. Filmot query may return HTTP 401.")

    filmot_url = f"https://filmot.com/api/getchannelvideos?channelID={channel_id}&unlisted=1"
    if api_key:
        safe_key = urllib.parse.quote(api_key)
        filmot_url += f"&key={safe_key}"

    content_bytes = fetch_url_with_retry(filmot_url, max_retries=max_retries, timeout=20)

    # Fallback endpoint attempt if first fails and no explicit API key was supplied
    if not content_bytes and not api_key:
        filmot_url_alt = f"https://filmot.com/api/getchannelvideos?channel={channel_id}"
        content_bytes = fetch_url_with_retry(filmot_url_alt, max_retries=2, timeout=15)

    if content_bytes:
        text_content = content_bytes.decode("utf-8", errors="ignore")
        try:
            data = json.loads(text_content)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "id" in item:
                        candidate_ids.add(item["id"])
            elif isinstance(data, dict):
                for key in ("videos", "items", "results"):
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            if isinstance(item, dict) and "id" in item:
                                candidate_ids.add(item["id"])
        except Exception:
            pass

        candidate_ids.update(extract_video_ids_from_text(text_content))

    print(f"[+] Found {len(candidate_ids)} potential video candidate(s) via Filmot.")
    return candidate_ids


def fetch_wayback_cdx_candidate_ids(channel_id: str, max_retries: int = 5) -> Set[str]:
    """Queries the Wayback Machine CDX API with exponential retries."""
    candidate_ids: Set[str] = set()
    print(f"[*] Querying Wayback Machine CDX API for canonical Channel ID: {channel_id}...")

    cdx_base = "https://web.archive.org/cdx/search/cdx"

    queries = [
        f"{cdx_base}?url=www.youtube.com/channel/{channel_id}*&output=json&fl=original&collapse=urlkey&limit=1000",
        f"{cdx_base}?url=www.youtube.com/feeds/videos.xml?channel_id={channel_id}&output=json&fl=timestamp,original&collapse=timestamp:8&limit=50",
    ]

    rss_snapshots = []

    for query_url in queries:
        content_bytes = fetch_url_with_retry(query_url, max_retries=max_retries, timeout=20)
        if not content_bytes:
            continue

        try:
            data = json.loads(content_bytes.decode("utf-8"))
            if len(data) > 1:
                rows = data[1:]
                for row in rows:
                    row_text = " ".join(row)
                    candidate_ids.update(extract_video_ids_from_text(row_text))

                    if "feeds/videos.xml" in row_text and len(row) >= 2:
                        timestamp, orig_url = row[0], row[1]
                        rss_snapshots.append((timestamp, orig_url))
        except Exception as e:
            print(f"  [!] Notice: Failed to parse CDX JSON response: {e}")

    # Parse raw historical RSS feed snapshots
    if rss_snapshots:
        print(
            f"[*] Parsing {len(rss_snapshots)} historical RSS feed snapshots from Wayback Machine..."
        )
        for timestamp, orig_url in rss_snapshots[:10]:
            raw_wayback_url = f"https://web.archive.org/web/{timestamp}id_/{orig_url}"
            xml_bytes = fetch_url_with_retry(raw_wayback_url, max_retries=3, timeout=10)
            if xml_bytes:
                xml_content = xml_bytes.decode("utf-8", errors="ignore")
                candidate_ids.update(extract_video_ids_from_text(xml_content))

    print(f"[+] Found {len(candidate_ids)} potential video candidate(s) via Wayback Machine.")
    return candidate_ids


def scan_channel_for_unlisted(
    channel_input: str,
    skip_wayback: bool = False,
    skip_filmot: bool = False,
    filmot_key: Optional[str] = None,
    max_retries: int = 5,
) -> List[Dict]:
    base_url = normalize_channel_url(channel_input).rstrip("/")

    print(f"[*] Resolving canonical Channel ID for: {channel_input}")
    target_channel_id = resolve_canonical_channel_id(channel_input)

    if target_channel_id:
        print(f"[+] Successfully resolved Channel ID: {target_channel_id}")
        videos_tab_url = f"https://www.youtube.com/channel/{target_channel_id}/videos"
        playlists_tab_url = f"https://www.youtube.com/channel/{target_channel_id}/playlists"
    else:
        print(
            "  [!] Warning: Could not resolve 'UC...' Channel ID. Using direct URL for playlist scan."
        )
        videos_tab_url = f"{base_url}/videos"
        playlists_tab_url = f"{base_url}/playlists"

    flat_opts = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }

    # Step 1: Fetch public video uploads
    print(f"[*] Fetching public video list from: {videos_tab_url}")
    public_video_ids: Set[str] = set()

    with yt_dlp.YoutubeDL(flat_opts) as ydl:
        channel_videos = ydl.extract_info(videos_tab_url, download=False)
        if channel_videos and "entries" in channel_videos:
            for entry in channel_videos["entries"]:
                if entry and "id" in entry:
                    public_video_ids.add(entry["id"])

    print(f"[+] Identified {len(public_video_ids)} public video(s).")

    # Step 2: Retrieve public playlists
    print(f"[*] Fetching public playlists from: {playlists_tab_url}")
    playlists: List[Dict] = []

    with yt_dlp.YoutubeDL(flat_opts) as ydl:
        channel_playlists = ydl.extract_info(playlists_tab_url, download=False)
        if channel_playlists and "entries" in channel_playlists:
            for pl in channel_playlists["entries"]:
                if pl and "id" in pl:
                    playlists.append(pl)

    print(f"[+] Found {len(playlists)} public playlist(s).")

    unlisted_results: Dict[str, Dict] = {}
    candidate_sources: Dict[str, str] = {}

    # Step 3: Scan playlist items
    with yt_dlp.YoutubeDL(flat_opts) as ydl_pl:
        for pl in playlists:
            pl_id = pl.get("id")
            pl_title = pl.get("title", "Unknown Playlist")
            pl_url = f"https://www.youtube.com/playlist?list={pl_id}"

            print(f"[*] Scanning playlist: '{pl_title}' ({pl_id})...")
            pl_data = ydl_pl.extract_info(pl_url, download=False)

            if not pl_data or "entries" not in pl_data:
                continue

            for item in pl_data["entries"]:
                if item and "id" in item:
                    vid_id = item["id"]
                    if vid_id not in public_video_ids:
                        candidate_sources[vid_id] = f"Playlist: {pl_title} ({pl_id})"

    # Step 4: Scan Filmot Database
    if not skip_filmot:
        if target_channel_id:
            filmot_candidate_ids = fetch_filmot_candidate_ids(
                channel_id=target_channel_id, api_key=filmot_key, max_retries=max_retries
            )
            for vid_id in filmot_candidate_ids:
                if vid_id not in public_video_ids and vid_id not in candidate_sources:
                    candidate_sources[vid_id] = "Filmot Database"
        else:
            print(
                "  [!] Skipping Filmot scan because canonical Channel ID could not be determined."
            )

    # Step 5: Scan Wayback Machine
    if not skip_wayback:
        if target_channel_id:
            wb_candidate_ids = fetch_wayback_cdx_candidate_ids(
                channel_id=target_channel_id, max_retries=max_retries
            )
            for vid_id in wb_candidate_ids:
                if vid_id not in public_video_ids and vid_id not in candidate_sources:
                    candidate_sources[vid_id] = "Wayback Machine Archive"
        else:
            print(
                "  [!] Skipping Wayback Machine scan because canonical Channel ID could not be determined."
            )

    # Step 6: Verify candidate video IDs
    print(f"\n[*] Verifying {len(candidate_sources)} candidate video ID(s)...")
    detail_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }

    with yt_dlp.YoutubeDL(detail_opts) as ydl_detail:
        for vid_id, source in candidate_sources.items():
            vid_url = f"https://www.youtube.com/watch?v={vid_id}"
            info = ydl_detail.extract_info(vid_url, download=False)

            if not info:
                continue

            status = info.get("availability") or info.get("availability_status") or "unlisted"
            uploader_id = info.get("channel_id") or info.get("uploader_id")

            matches_channel = (target_channel_id is None) or (uploader_id == target_channel_id)
            is_unlisted = (status == "unlisted") or (vid_id not in public_video_ids)

            if matches_channel and is_unlisted:
                unlisted_results[vid_id] = {
                    "video_id": vid_id,
                    "title": info.get("title"),
                    "url": vid_url,
                    "availability": status,
                    "channel_id": uploader_id,
                    "channel_name": info.get("uploader"),
                    "upload_date": info.get("upload_date"),
                    "duration_seconds": info.get("duration"),
                    "view_count": info.get("view_count"),
                    "discovery_source": source,
                }
                print(
                    f"  [!] Confirmed unlisted video: {info.get('title')} ({vid_id}) via {source}"
                )

    return list(unlisted_results.values())


def main():
    args = parse_args()
    unlisted_videos = scan_channel_for_unlisted(
        args.channel_url,
        skip_wayback=args.skip_wayback,
        skip_filmot=args.skip_filmot,
        filmot_key=args.filmot_key,
        max_retries=args.max_retries,
    )

    print(f"\n[+] Total unlisted videos discovered: {len(unlisted_videos)}")

    output_data = {
        "target_channel": args.channel_url,
        "unlisted_video_count": len(unlisted_videos),
        "videos": unlisted_videos,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)

    print(f"[+] Results saved to: {args.output}")


if __name__ == "__main__":
    main()
