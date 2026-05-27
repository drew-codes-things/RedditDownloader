# RedditDownloader V2

Download media and text posts from any subreddit — **no Reddit app registration required**.

Version 2 ditches PRAW and the old `App.txt` credentials entirely. It talks directly to Reddit's public JSON API (`reddit.com/r/{sub}/hot.json`), so you can clone and run immediately with zero setup.

---

## Requirements

- Python 3.8+
- `requests` (the only dependency)

```bash
pip install requests
```

---

## Usage

```bash
python main.py
```

You'll be prompted to:

1. **Search** for a subreddit by name or topic
2. **Pick** from the top 10 matching results
3. **Choose** what to download — Media, Text, or Both
4. **Set** how many posts to grab and how many parallel downloads to run
5. **Optionally filter** by post flair

Files are saved to `Reddit_downloads/Media/` and `Reddit_downloads/Text/` next to the script.

---

## What gets downloaded

| Type | What it saves |
|------|---------------|
| Media | Direct image/gif/mp4 links (`.jpg`, `.jpeg`, `.png`, `.gif`, `.mp4`, `.gifv`, `.webp`) and Reddit-hosted videos |
| Text | Self-post body saved as `{post_id}_text.txt`, with the title prepended |

> **Note:** Reddit only exposes direct media URLs in the post metadata. Embedded galleries and external video hosts (YouTube, Imgur albums, etc.) are not downloaded.

---

## Rate limiting

Reddit's public API allows roughly 60 requests per minute without authentication. If you hit the limit the script automatically waits 60 seconds and resumes — you don't need to do anything.

---

## Why no PRAW / no App.txt?

Reddit made registering a developer app increasingly awkward. This version uses the same public endpoints any browser hits when you add `.json` to a Reddit URL — no OAuth, no client ID, no secret.

---

## License

MIT
