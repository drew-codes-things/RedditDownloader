# RedditDownloaderV2

A powerful Python-based Reddit media downloader that fetches images and videos from any subreddit of your choice using the official Reddit API.

## Features

- Download images and videos from subreddits
- Supports hot, new, top, and rising sorting
- Automatic handling of NSFW content (with toggle)
- Progress tracking and error handling
- Saves files with clean naming (including post title and ID)
- Configurable download limits and filters

## Requirements

- Python 3.8+
- Reddit API credentials (free)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/drew-codes-things/RedditDownloaderV2.git
   cd RedditDownloaderV2
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your Reddit API credentials:
   - Go to https://www.reddit.com/prefs/apps
   - Create a new "script" app
   - Copy your `client_id`, `client_secret`, and `user_agent`
   - Create a `.env` file (see `.env.example`)

## Usage

```bash
python main.py
```

Follow the prompts to choose a subreddit, sorting method, and number of posts to download.

## Configuration

Edit `config.py` or use environment variables for:
- Default subreddit
- Download limit
- NSFW filter
- Output directory

## License

MIT License

---

*Originally created to make bulk downloading from Reddit simple and reliable.*