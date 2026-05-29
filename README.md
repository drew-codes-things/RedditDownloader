# RedditDownloaderV2

A powerful Python-based Reddit media downloader that fetches images, videos, and text posts from any subreddit using Reddit's public JSON API (no API key required).

## What it does

Downloads media (images, videos, GIFs) and/or text posts from subreddits in bulk, with support for flair filtering, concurrent downloads, and organised folder output.

## Key Technical Features

- Uses Reddit's **public JSON API** (`/hot.json`) - no credentials or API key needed
- Multi-threaded downloading with `ThreadPoolExecutor`
- Automatic rate-limit handling (waits 60s on 429)
- Resume support - already downloaded files are skipped on re-run
- Flair filtering (scans first 100 posts to list available flairs)
- Smart media detection (jpg, jpeg, png, gif, mp4, gifv, webp + Reddit video fallback)
- Separate folders for Media and Text downloads
- Subreddit search with interactive selection

## File Structure

```
RedditDownloaderV2/
    main.py              # Full application logic (entry point)
    requirements.txt
    .env.example         # (optional) for future authenticated features
    config.py            # Default settings (download limit, NSFW, output dir)
    LICENSE
```

## Installation

### Linux (Recommended - Virtual Environment)

```bash
git clone https://github.com/drew-codes-things/RedditDownloaderV2.git
cd RedditDownloaderV2

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### macOS / Windows (Simple Method)

```bash
git clone https://github.com/drew-codes-things/RedditDownloaderV2.git
cd RedditDownloaderV2

pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

The script will:
1. Ask you to search for a subreddit
2. Let you pick from top results
3. Choose Media / Text / Both
4. Set download count and concurrency level
5. Optionally filter by flair

## Technical Details

- **No authentication required** - uses public unauthenticated endpoints
- **Headers**: Custom User-Agent (`RedditDownloader/2.0 by Drew`)
- **Concurrency**: User-defined thread count
- **Output**: `Reddit_downloads/Media/` and `Reddit_downloads/Text/`
- **Error handling**: Graceful failures per file with logging

## Requirements

- Python 3.8+
- Internet connection

## License

MIT License
