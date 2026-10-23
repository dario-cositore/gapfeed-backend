import sqlite3
import sys
import json
import os
import time
import datetime
import subprocess
from urllib.parse import quote_plus
import requests
import config

# --- CONFIGURATION ---
TARGET_SUBREDDITS = [
    'SaaS', 'Entrepreneur', 'ProductManagement', 'startups', 
    'sysadmin', 'devops', 'programming', 'indiehackers', 'webdev'
]

PAIN_KEYWORDS = [
    "i wish there was a tool for", "is there an app that", "i hate how", 
    "the most frustrating part", "manual process for", "zapier alternative for",
    "still using a spreadsheet for", "my biggest workflow bottleneck", "i'm so tired of",
    "is driving me insane", "why is this still a problem", "i've wasted hours on",
    "a complete nightmare"
]

MAX_POSTS_PER_KEYWORD = 3 
DB_PATH = config.DB_PATH

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

def get_json_from_url(url):
    print(f"  [GET] {url[:60]}...", end=" ", flush=True)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 429:
            print("RATE LIMITED (429). Sleeping for 15s to cool off.")
            time.sleep(15)
            return None
        response.raise_for_status()
        print("OK")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"FAIL ({type(e).__name__})")
        time.sleep(5)
        return None

def brutal_filter(text):
    system_prompt = """You are the Brutal Filter for gapfeed. Your ONLY job is to read a signal and decide if it describes a painful, unsolved business or professional workflow problem that someone would pay to solve. Respond with EXACTLY one word: "YES" or "NO"."""
    
    full_prompt = f"System: {system_prompt}\n\nSignal to evaluate:\n\"{text}\"\n\nRespond YES or NO."
    
    try:
        env = os.environ.copy()
        env['OPENCLAW_MODEL'] = config.FAST_MODEL
        
        result = subprocess.run(
            ['openclaw', 'agent', '--agent', 'main', '--local', '-m', full_prompt],
            capture_output=True,
            text=True,
            env=env,
            timeout=15
        )
        
        output = result.stdout.strip().upper()
        if "YES" in output.split('\n')[-1]:
            return "YES"
        return "NO"
        
    except Exception as e:
        print(f"      [Filter Error]: {e}")
        return "ERROR"

def ingest_signal(signal_data):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT id FROM signals WHERE source_url = ?", (signal_data['source_url'],))
        if c.fetchone():
            print("      [Ingest] Skipped: URL already in database.")
            return False

        c.execute(
            """INSERT INTO signals (source, source_url, subreddit, author, content, title, created_at, status)
            VALUES (:source, :source_url, :subreddit, :author, :content, :title, :created_at, :status)""",
            signal_data
        )
        conn.commit()
        print(f"      [Ingest] SUCCESS: Inserted signal by u/{signal_data['author']}")
        return True
    except sqlite3.Error as e:
        print(f"      [Ingest Error]: {e}")
        return False
    finally:
        if conn:
            conn.close()

def hunt_comments_and_filter(post_permalink, keywords):
    post_url = f"https://www.reddit.com{post_permalink}.json"
    post_json = get_json_from_url(post_url)
    
    if not post_json or len(post_json) < 2:
        return 0

    comments_data = post_json[1]['data']['children']
    ingested_count = 0
    
    def process_comments(comments):
        nonlocal ingested_count
        for comment_obj in comments:
            if comment_obj['kind'] == 't1':
                comment_body = comment_obj['data'].get('body', '').lower()
                
                if any(keyword in comment_body for keyword in keywords):
                    comment_data = comment_obj['data']
                    raw_text = comment_data.get('body')
                    author = comment_data.get('author', '[deleted]')
                    
                    print(f"    *** Keyword Match Found (u/{author}) ***")
                    print(f"    Text: {raw_text[:80]}...")
                    
                    print("      [Filter] Analyzing via OpenClaw/Vertex AI...")
                    verdict = brutal_filter(raw_text)
                    print(f"      [Filter] Verdict: {verdict}")
                    
                    if verdict == "YES":
                        signal = {
                            'source': 'Reddit',
                            'source_url': f"https://www.reddit.com{comment_data.get('permalink')}",
                            'subreddit': comment_data.get('subreddit'),
                            'author': author,
                            'content': raw_text,
                            'title': post_json[0]['data']['children'][0]['data'].get('title'),
                            'created_at': datetime.datetime.fromtimestamp(comment_data.get('created_utc', 0)).isoformat(),
                            'status': 'new'
                        }
                        if ingest_signal(signal):
                            ingested_count += 1
                
                if 'replies' in comment_obj['data'] and comment_obj['data']['replies'] and 'data' in comment_obj['data']['replies']:
                    process_comments(comment_obj['data']['replies']['data']['children'])

    process_comments(comments_data)
    return ingested_count

def run_swarm():
    print("=== GAPFEED AUTONOMOUS SWARM ONLINE ===")
    
    total_ingested = 0
    # Let's run a hard harvest for 15 minutes straight
    run_duration_minutes = 15
    end_time = time.time() + (run_duration_minutes * 60)

    for subreddit in TARGET_SUBREDDITS:
        for keyword in PAIN_KEYWORDS:
            if time.time() > end_time:
                print("\n=== SWARM CYCLE COMPLETE (Time Limit) ===")
                return
                
            print(f"\nTarget: r/{subreddit} | Bait: '{keyword}'")
            search_url = f"https://www.reddit.com/r/{subreddit}/search.json?q={quote_plus(keyword)}&restrict_sr=1&sort=new&limit={MAX_POSTS_PER_KEYWORD}"
            
            search_json = get_json_from_url(search_url)

            if search_json and 'data' in search_json and 'children' in search_json['data']:
                posts = search_json['data']['children']
                if posts:
                    print(f"  Found {len(posts)} potential threads.")
                    for post in posts:
                        if post['kind'] == 't3':
                            permalink = post['data'].get('permalink')
                            if permalink:
                                added = hunt_comments_and_filter(permalink, PAIN_KEYWORDS)
                                total_ingested += added
                else:
                    print("  No threads matched bait.")
            
            time.sleep(3) # Slower paced direct access

    print(f"\n=== SWARM CYCLE COMPLETE ===")
    print(f"Total new pristine signals injected into database: {total_ingested}")

if __name__ == '__main__':
    run_swarm()
