# YouTube Unlisted Video Scanner 🕵️‍♂️

A robust Python 3 command-line tool that discovers and extracts unlisted YouTube videos from a specified channel. 

Since YouTube video IDs cannot be mathematically brute-forced, this script uses intelligent cross-referencing to find hidden content. It scans a channel's public playlists for unlisted entries, queries the Filmot database API, and searches the Internet Archive (Wayback Machine) CDX API for historical snapshots of the channel's RSS feeds and web pages.

## ✨ Features

* **Playlist Scanning:** Cross-references public video uploads against playlist items to identify unlisted content.
* **Filmot Database Integration:** Queries the Filmot API to discover historical unlisted videos associated with the channel.
* **Wayback Machine Integration:** Scrapes the Internet Archive's CDX API for historical channel snapshots and raw XML RSS feeds to find deleted or unlisted videos.
* **Smart URL Resolution:** Automatically resolves YouTube handles (e.g., `@ChannelName`) or custom URLs to their canonical `UC...` Channel IDs required for third-party querying.
* **Resilient API Handling:** Built-in exponential backoff and retry logic with jitter to handle transient `503 Service Unavailable` or `429 Too Many Requests` errors.
* **Verification Check:** Verifies ownership and current availability of all discovered candidate IDs using `yt-dlp` before adding them to the final output.
* **JSON Export:** Saves all discovered metadata (views, upload date, duration, discovery source) to a clean, structured JSON file.

## ⚙️ Prerequisites

* **Python 3.7+**
* **yt-dlp** (The only external dependency)

## 🚀 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/msebastien/youtube-unlisted-scanner.git
   cd youtube-unlisted-scanner
   ```

2. Install the required dependency:
   ```bash
   pip install yt-dlp
   ```

## 💻 Usage

Run the script by passing the target channel's Handle, ID, or full URL. 

```bash
python yt_unlisted_scanner.py <channel_url_or_handle> [options]
```

### Options

| Argument | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `channel_url` | | **(Required)** Target YouTube channel URL, handle (`@name`), or ID (`UC...`). | |
| `--output` | `-o` | Path to the output JSON file. | `unlisted_videos.json` |
| `--filmot-key` | | Your Filmot API key (prevents HTTP 401 Unauthorized errors). | `None` |
| `--skip-filmot` | | Skip searching the Filmot unlisted video database. | `False` |
| `--skip-wayback` | | Skip searching the Internet Archive / Wayback Machine CDX API. | `False` |
| `--max-retries` | | Maximum exponential backoff retry attempts for HTTP requests. | `5` |
| `--help` | `-h` | Show the help message and exit. | |

### Examples

**1. Basic scan using a channel handle and Filmot API key:**
```bash
python yt_unlisted_scanner.py "@ChannelName" --filmot-key "YOUR_FILMOT_API_KEY"
```

**2. Save results to a specific file:**
```bash
python yt_unlisted_scanner.py "https://www.youtube.com/@ChannelName" -o my_results.json
```

**3. Fast scan (Playlist only, skip Filmot and Wayback):**
```bash
python yt_unlisted_scanner.py UC1234567890abcdefghijklg --skip-filmot --skip-wayback
```

**4. Run with increased retries during high Internet Archive server load:**
```bash
python yt_unlisted_scanner.py "@ChannelName" --max-retries 10
```

## 📄 Output Format

The script outputs a comprehensive JSON file containing metadata for every unlisted video discovered, including exactly *how* the script found it (`discovery_source`):

```json
{
    "target_channel": "@ChannelName",
    "unlisted_video_count": 2,
    "videos": [
        {
            "video_id": "abc123XYZ00",
            "title": "Unlisted Webinar Recording",
            "url": "https://www.youtube.com/watch?v=abc123XYZ00",
            "availability": "unlisted",
            "channel_id": "UCxxxxxx",
            "channel_name": "Channel Name",
            "upload_date": "20230115",
            "duration_seconds": 1840,
            "view_count": 420,
            "discovery_source": "Filmot Database"
        },
        {
            "video_id": "def456UVW11",
            "title": "Unlisted Supplementary Material",
            "url": "https://www.youtube.com/watch?v=def456UVW11",
            "availability": "unlisted",
            "channel_id": "UCxxxxxx",
            "channel_name": "Channel Name",
            "upload_date": "20240310",
            "duration_seconds": 312,
            "view_count": 95,
            "discovery_source": "Playlist: Course Materials (PLxxxxxx)"
        }
    ]
}
```

## ❓ FAQ

**Q: Why am I getting an HTTP 401 error when querying Filmot?**  
**A:** Filmot requires an API key to query their endpoints. Register for a free account at [filmot.com](https://filmot.com/) to obtain an API key, then run the script with `--filmot-key "YOUR_KEY"`. You can also bypass Filmot using `--skip-filmot`.

**Q: Can I modify this to brute-force guess all possible video URLs for a channel?**  
**A:** No. A YouTube video ID is an 11-character Base64 string, meaning there are 64^11 (roughly 73.7 quintillion) possible combinations. Even if you could check 1 million URLs per second, it would take 2.3 million years to guess every combination. Furthermore, YouTube's Web Application Firewall will permanently IP-ban you within seconds if you attempt an online brute-force attack.

**Q: Why am I seeing `HTTP 503` or `Service Unavailable` errors from Wayback Machine?**  
**A:** The Internet Archive CDX API frequently experiences heavy load. The script automatically catches these errors and pauses before retrying using exponential backoff. If the service is down, pass the `--skip-wayback` flag.

## ⚠️ Disclaimer

This tool is designed for research, archival, and OSINT (Open Source Intelligence) purposes. It only accesses publicly available metadata and historical web archives. It does not bypass DRM, passwords, or authentication mechanisms. Users are responsible for complying with YouTube's Terms of Service and third-party API usage guidelines.

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

