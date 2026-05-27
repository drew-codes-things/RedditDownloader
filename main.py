import requests
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {'User-Agent': 'RedditDownloader/2.0 by Drew'}


def get_downloads_folder(content_type):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(script_dir, 'Reddit_downloads', content_type.capitalize())
    os.makedirs(folder, exist_ok=True)
    return folder


def download_file(url, filename, download_folder):
    try:
        response = requests.get(url, stream=True, headers=HEADERS, timeout=30)
        response.raise_for_status()
        file_path = os.path.join(download_folder, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {filename}")
        return True
    except requests.RequestException as e:
        print(f"Failed {filename}: {e}")
        return False


def save_text(text, filename, download_folder):
    try:
        file_path = os.path.join(download_folder, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Saved text: {filename}")
        return True
    except IOError as e:
        print(f"Failed to save {filename}: {e}")
        return False


def fetch_posts(subreddit_name, limit, flair=None):
    """Fetch posts using Reddit's public JSON API — no credentials needed."""
    posts = []
    after = None
    fetched = 0

    while fetched < limit:
        batch = min(100, limit - fetched)
        url = f"https://www.reddit.com/r/{subreddit_name}/hot.json?limit={batch}"
        if after:
            url += f"&after={after}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                print("Rate limited — waiting 60 seconds...")
                time.sleep(60)
                continue
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
            after = data.get('after')
            fetched += len(children)
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
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        children = resp.json().get('data', {}).get('children', [])
        return [c['data'] for c in children]
    except requests.RequestException as e:
        print(f"Error searching subreddits: {e}")
        return []


def get_available_flairs(subreddit_name):
    """Scan hot posts to collect flair names."""
    posts = fetch_posts(subreddit_name, limit=100)
    flairs = sorted({p['link_flair_text'] for p in posts if p.get('link_flair_text')})
    return flairs


def scrape_reddit(subreddit_name, count, num_threads, download_type, flair=None):
    print(f"\nFetching up to {count} posts from r/{subreddit_name}...")
    posts = fetch_posts(subreddit_name, count, flair)
    print(f"Retrieved {len(posts)} posts.")

    total_downloads = 0
    media_exts = ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.gifv', '.webp')

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for post in posts:
            # Media
            if download_type in ['media', 'both']:
                url = post.get('url', '')
                if url.lower().endswith(media_exts):
                    filename = os.path.basename(url.split('?')[0])
                    folder = get_downloads_folder('Media')
                    futures.append(executor.submit(download_file, url, filename, folder))
                # Reddit-hosted video
                reddit_video = post.get('media') or {}
                rv = (reddit_video.get('reddit_video') or {})
                if rv.get('fallback_url'):
                    filename = f"{post['id']}.mp4"
                    folder = get_downloads_folder('Media')
                    futures.append(executor.submit(download_file, rv['fallback_url'], filename, folder))

            # Text
            if download_type in ['text', 'both'] and post.get('selftext', '').strip():
                filename = f"{post['id']}_text.txt"
                folder = get_downloads_folder('Text')
                content = f"Title: {post.get('title', '')}\n\n{post['selftext']}"
                futures.append(executor.submit(save_text, content, filename, folder))

        for future in as_completed(futures):
            try:
                if future.result():
                    total_downloads += 1
            except Exception as e:
                print(f"Task error: {e}")

    print(f"\nDone. {total_downloads} files saved.")


def print_title():
    title = r"""
 ____           _     _ _ _     ____                      _                 _           
|  _ \ ___   __| | __| (_) |_  |  _ \  _____      ___ __ | | ___   __ _  __| | ___ _ __ 
| |_) / _ \ / _` |/ _` | | __| | | | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
|  _ < (_) | (_| | (_| | | |_  | |_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |   
|_| \_\___/ \__,_|\__,_|_|\__| |____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|   
                                                                                        
                        - made by Drew  (v2 — no API key needed)
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
        print(f"  {i}. r/{sub['display_name']} — {sub.get('title', '')}")

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

    try:
        count = int(input("How many posts? "))
        num_threads = int(input("Concurrent downloads: "))
        if count <= 0 or num_threads <= 0:
            raise ValueError
    except ValueError:
        print("Please enter positive integers.")
        return

    flairs = get_available_flairs(subreddit_name)
    flair = None
    if flairs:
        print("\nAvailable flairs:")
        for i, f in enumerate(flairs, 1):
            print(f"  {i}. {f}")
        fc = input("Filter by flair number (leave blank for all): ").strip()
        if fc.isdigit() and 1 <= int(fc) <= len(flairs):
            flair = flairs[int(fc) - 1]

    scrape_reddit(subreddit_name, count, num_threads, download_type, flair)


if __name__ == '__main__':
    main()
