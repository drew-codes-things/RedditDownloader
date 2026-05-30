import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

HEADERS = {'User-Agent': 'RedditDownloader/2.0 by Drew'}
MAX_THREADS = 10
RETRY_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 1.0


def request_with_retry(url, *, stream=False, timeout=15, headers=None, retries=RETRY_ATTEMPTS):
    """
    Perform a GET request with small exponential backoff.

    Retries transient network failures, HTTP 429, and 5xx responses.
    """
    headers = headers or HEADERS
    last_error = None

    for attempt in range(retries):
        try:
            resp = requests.get(url, stream=stream, headers=headers, timeout=timeout)
            if resp.status_code == 429 and attempt < retries - 1:
                retry_after = int(resp.headers.get('Retry-After', 0) or 0)
                wait = retry_after if retry_after > 0 else RETRY_BACKOFF_SECONDS * (2 ** attempt)
                print(f"[RETRY] Rate limited for {url} -> waiting {wait:.1f}s ({attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            if 500 <= resp.status_code < 600 and attempt < retries - 1:
                wait = RETRY_BACKOFF_SECONDS * (2 ** attempt)
                print(f"[RETRY] HTTP {resp.status_code} for {url} -> waiting {wait:.1f}s ({attempt + 1}/{retries})")
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            last_error = e
            if attempt == retries - 1:
                raise
            wait = RETRY_BACKOFF_SECONDS * (2 ** attempt)
            print(f"[RETRY] Network error for {url}: {e} -> waiting {wait:.1f}s ({attempt + 1}/{retries})")
            time.sleep(wait)

    if last_error:
        raise last_error
    raise requests.RequestException(f"Request failed for {url}")


def get_downloads_folder(content_type):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(script_dir, 'Reddit_downloads', content_type.capitalize())
    os.makedirs(folder, exist_ok=True)
    return folder


def download_file(url, filename, download_folder):
    # Convert .gifv (Imgur MP4 wrapper) to .mp4
    if url.lower().endswith('.gifv'):
        url = url[:-5] + '.mp4'
        filename = filename[:-5] + '.mp4'

    file_path = os.path.join(download_folder, filename)

    if os.path.exists(file_path):
        print(f"[SKIP] Already exists: {filename}")
        return 'skip'

    try:
        response = request_with_retry(url, stream=True, headers=HEADERS, timeout=30)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[OK]   Downloaded: {filename}")
        return True
    except requests.RequestException as e:
        print(f"[FAIL] {filename}: {e}")
        return False


def save_text(post, filename, download_folder):
    file_path = os.path.join(download_folder, filename)

    if os.path.exists(file_path):
        print(f"[SKIP] Already exists: {filename}")
        return 'skip'

    try:
        content = (
            f"Title:   {post.get('title', '')}\n"
            f"Author:  u/{post.get('author', '[deleted]')}\n"
            f"Score:   {post.get('score', 0)}\n"
            f"Flair:   {post.get('link_flair_text') or 'None'}\n"
            f"URL:     https://reddit.com{post.get('permalink', '')}\n"
            f"\n{post['selftext']}"
        )
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK]   Saved text: {filename}")
        return True
    except IOError as e:
        print(f"[FAIL] {filename}: {e}")
        return False


def fetch_posts(subreddit_name, limit, sort='hot', flair=None):
    """Fetch posts using Reddit's public JSON API - no credentials needed.

    When a flair filter is active, `fetched` tracks only the posts that
    actually passed the filter, not the raw children count returned by the
    API.  Previously, fetched counted every child (including flair-mismatches)
    so the loop exited before collecting `limit` matching posts.
    """
    valid_sorts = ('hot', 'new', 'top', 'rising')
    if sort not in valid_sorts:
        sort = 'hot'

    posts = []
    after = None
    fetched = 0

    while fetched < limit:
        batch = min(100, limit - fetched)
        url = f"https://www.reddit.com/r/{subreddit_name}/{sort}.json?limit={batch}"
        if after:
            url += f"&after={after}"

        try:
            resp = request_with_retry(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json().get('data', {})
            children = data.get('children', [])
            if not children:
                break
            for child in children:
                post = child.get('data', {})
                if flair and post.get('link_flair_text') != flair:
                    continue
                posts.append(post)
                # Only count posts that passed the flair filter so that the
                # loop keeps paginating until `limit` matching posts are found.
                fetched += 1
                if fetched >= limit:
                    break
            after = data.get('after')
            if not after:
                break
        except requests.RequestException as e:
            print(f"Error fetching posts: {e}")
            break

    return posts


def search_subreddits(query):
    """Search subreddits using the public JSON API."""
    url = f"https://www.reddit.com/subreddits/search.json?q={requests.utils.quote(query)}&limit=10"
    try:
        resp = request_with_retry(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        children = resp.json().get('data', {}).get('children', [])
        return [c['data'] for c in children]
    except requests.RequestException as e:
        print(f"Error searching subreddits: {e}")
        return []


def get_available_flairs(subreddit_name, scan_limit):
    """Scan hot posts to collect flair names, using the same limit the user asked for."""
    scan = max(scan_limit, 25)  # always scan at least 25 so low counts still find flairs
    posts = fetch_posts(subreddit_name, limit=scan)
    flairs = sorted({p['link_flair_text'] for p in posts if p.get('link_flair_text')})
    return flairs


def extract_gallery_images(post):
    """
    For gallery posts (is_gallery=True), return a list of the best-quality
    image URLs from media_metadata in gallery order.
    """
    if not post.get('is_gallery'):
        return []
    media_metadata = post.get('media_metadata') or {}
    gallery_data   = post.get('gallery_data') or {}
    urls = []
    for item in gallery_data.get('items', []):
        media_id = item.get('media_id')
        if not media_id or media_id not in media_metadata:
            continue
        meta   = media_metadata[media_id]
        if meta.get('status') != 'valid':
            continue
        # prefer largest preview; fall back to source
        previews = meta.get('p', [])
        if previews:
            best = previews[-1].get('u', '')
        else:
            best = (meta.get('s') or {}).get('u', '')
        if best:
            urls.append(best.replace('&amp;', '&'))
    return urls


def scrape_reddit(subreddit_name, count, num_threads, download_type, sort='hot', flair=None):
    print(f"\nFetching up to {count} posts from r/{subreddit_name} (sort: {sort})...")
    posts = fetch_posts(subreddit_name, count, sort, flair)
    print(f"Retrieved {len(posts)} posts.")

    total_downloads = 0
    total_skipped = 0
    total_failed = 0
    media_exts = ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.gifv', '.webp')

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for post in posts:
            if download_type in ['media', 'both']:
                # --- gallery posts ---
                gallery_urls = extract_gallery_images(post)
                if gallery_urls:
                    folder = get_downloads_folder('Media')
                    for idx, gurl in enumerate(gallery_urls, 1):
                        ext  = os.path.splitext(gurl.split('?')[0])[1] or '.jpg'
                        fname = f"{post['id']}_gallery_{idx:03d}{ext}"
                        futures.append(executor.submit(download_file, gurl, fname, folder))
                else:
                    scheduled_media_urls = set()

                    # --- direct image/video ---
                    # Prefix filename with the post ID so that two different
                    # posts linking the same CDN filename (e.g. abc123.jpg on
                    # Imgur) don't silently overwrite each other.
                    url = post.get('url', '')
                    if url.lower().endswith(media_exts):
                        raw_name = os.path.basename(url.split('?')[0])
                        if raw_name.lower().endswith('.gifv'):
                            raw_name = raw_name[:-5] + '.mp4'
                        filename = f"{post['id']}_{raw_name}"
                        folder = get_downloads_folder('Media')
                        futures.append(executor.submit(download_file, url, filename, folder))
                        scheduled_media_urls.add(url.split('?')[0].rstrip('/'))

                    # --- reddit-hosted video ---
                    reddit_video = post.get('media') or {}
                    rv = (reddit_video.get('reddit_video') or {})
                    fallback_url = rv.get('fallback_url')
                    if fallback_url:
                        fallback_norm = fallback_url.split('?')[0].rstrip('/')
                        if fallback_norm not in scheduled_media_urls:
                            filename = f"{post['id']}.mp4"
                            folder = get_downloads_folder('Media')
                            futures.append(executor.submit(download_file, fallback_url, filename, folder))

            if download_type in ['text', 'both'] and post.get('selftext', '').strip():
                filename = f"{post['id']}_text.txt"
                folder = get_downloads_folder('Text')
                futures.append(executor.submit(save_text, post, filename, folder))

        with tqdm(total=len(futures), desc="Processing", unit="file") as pbar:
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result == 'skip':
                        total_skipped += 1
                    elif result:
                        total_downloads += 1
                    else:
                        total_failed += 1
                except Exception as e:
                    print(f"Task error: {e}")
                    total_failed += 1
                pbar.update(1)

    print(f"\nDone. {total_downloads} downloaded, {total_skipped} skipped (already existed), {total_failed} failed.")


def print_title():
    title = r"""
 ____           _     _ _ _     ____                      _                 _           
|  _ \ ___   __| | __| (_) |_  |  _ \  _____      ___ __ | | ___   __ _  __| | ___ _ __ 
| |_) / _ \ / _` |/ _` | | __| | | | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
|  _ < (_) | (_| | (_| | | |_  | |_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   
|_| \_\___/ \__,_|\__,_|_|\__| |____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   
                                                                                        
                        - made by Drew  (v2 - no API key needed)
    """
    print(title)


def main():
    print_title()

    search_query = input("Search for a subreddit: ").strip()
    results = search_subreddits(search_query)

    if not results:
        print("No matching subreddits found.")
        return

    print("\nTop results:")
    for i, sub in enumerate(results, 1):
        print(f"  {i}. r/{sub['display_name']} - {sub.get('title', '')}")

    try:
        choice = int(input("\nPick a number: "))
        if not (1 <= choice <= len(results)):
            print("Invalid choice.")
            return
    except ValueError:
        print("Please enter a number.")
        return

    subreddit_name = results[choice - 1]['display_name']

    download_type = input("Download [M]edia, [T]ext or [B]oth? ").strip().lower()
    if download_type not in ['m', 't', 'b']:
        print("Invalid choice.")
        return
    download_type = {'m': 'media', 't': 'text', 'b': 'both'}[download_type]

    print("\nSort order:")
    print("  1. hot (default)")
    print("  2. new")
    print("  3. top")
    print("  4. rising")
    sort_map = {'1': 'hot', '2': 'new', '3': 'top', '4': 'rising'}
    sort_choice = input("Choose sort (1-4) [1]: ").strip() or '1'
    sort = sort_map.get(sort_choice, 'hot')

    try:
        count = int(input("How many posts? "))
        raw_threads = int(input(f"Concurrent downloads (max {MAX_THREADS}): "))
        if count <= 0 or raw_threads <= 0:
            raise ValueError
    except ValueError:
        print("Please enter positive integers.")
        return

    if raw_threads > MAX_THREADS:
        print(f"[WARNING] Clamping concurrent downloads from {raw_threads} to {MAX_THREADS} to avoid rate-limiting.")
        raw_threads = MAX_THREADS
    num_threads = raw_threads

    flairs = get_available_flairs(subreddit_name, count)
    flair = None
    if flairs:
        print("\nAvailable flairs:")
        # Renamed loop variable from `f` to `flair_name` to avoid shadowing
        # the built-in `f` string prefix / open() return value.
        for i, flair_name in enumerate(flairs, 1):
            print(f"  {i}. {flair_name}")
        fc = input("Filter by flair number (leave blank for all): ").strip()
        if fc.isdigit() and 1 <= int(fc) <= len(flairs):
            flair = flairs[int(fc) - 1]

    scrape_reddit(subreddit_name, count, num_threads, download_type, sort, flair)


if __name__ == '__main__':
    main()
