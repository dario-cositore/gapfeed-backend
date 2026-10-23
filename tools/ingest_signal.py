import sqlite3
import sys
import json
import os

def ingest_signal(signal_data):
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'gapfeed_unified.db')

    # Note: Using 'title' instead of 'post_title' to match DB schema
    required_keys = ['source', 'source_url', 'subreddit', 'author', 'content', 'title', 'created_at', 'status']
    if not all(key in signal_data for key in required_keys):
        print(f"Error: Input JSON is missing required keys. Missing: {set(required_keys) - set(signal_data.keys())}", file=sys.stderr)
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Check for duplicates manually instead of creating a unique index 
        # (since historical data might contain duplicate URLs)
        c.execute("SELECT id FROM signals WHERE source_url = ?", (signal_data['source_url'],))
        if c.fetchone():
            print("--- Ingestion Skipped ---")
            print(f"Signal with source_url {signal_data['source_url']} already exists in the database.")
            return

        c.execute(
            """INSERT INTO signals (source, source_url, subreddit, author, content, title, created_at, status)
            VALUES (:source, :source_url, :subreddit, :author, :content, :title, :created_at, :status)""",
            signal_data
        )
        conn.commit()
        print("--- Ingestion Success ---")
        print(f"Successfully ingested signal from {signal_data['source']} by user u/{signal_data['author']}.")
        print(f"URL: {signal_data['source_url']}")

    except sqlite3.Error as e:
        print(f"Database error during ingestion: {e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 ingest_signal.py <path_to_json_file>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            signal_json = json.load(f)
            
            # Map 'post_title' to 'title' if present
            if 'post_title' in signal_json and 'title' not in signal_json:
                signal_json['title'] = signal_json.pop('post_title')
                
        ingest_signal(signal_json)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file '{file_path}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
