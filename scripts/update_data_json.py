import json
import os
import glob
import sqlite3

PRISTINE_GAP_DIR = "/home/dario/.openclaw/workspace/3. gapfeed/data/pristine_gaps"
DATA_JSON_PATH = "/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json"
DB_PATH = "/home/dario/.openclaw/workspace/3. gapfeed/data/gapfeed_merged.db"

def update_data_json():
    # Make sure we read from existing to preserve stats, else create skeleton
    if not os.path.exists(DATA_JSON_PATH):
        data = {"gaps": [], "stats": {}, "source_distribution": {}, "buyer_intent_distribution": {}, "sentiment_breakdown": {}}
    else:
        try:
            with open(DATA_JSON_PATH, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {"gaps": [], "stats": {}, "source_distribution": {}, "buyer_intent_distribution": {}, "sentiment_breakdown": {}}
            
    # Get total signals from the merged database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM signals;")
        total_signals = cursor.fetchone()[0]
        data['stats']['signals'] = total_signals
        data['stats']['total_signals'] = total_signals
    except Exception as e:
        print(f"Warning: Could not get total signals from DB: {e}")

    pristine_files = glob.glob(os.path.join(PRISTINE_GAP_DIR, "*.json"))
    pristine_files.sort()
    
    new_gaps = []
    current_id = 1001
    
    for filepath in pristine_files:
        with open(filepath, 'r') as f:
            try:
                gap = json.load(f)
                gap['id'] = current_id
                
                # Check for other required fields so they are definitely present
                if 'slug' not in gap:
                    gap['slug'] = f"gap-{current_id}"
                if 'title' not in gap:
                    gap['title'] = f"Pristine Gap {current_id}"
                    
                new_gaps.append(gap)
                current_id += 1
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
                
    # Overwrite the gaps list so only pristine gaps are in it!
    data['gaps'] = new_gaps
    
    with open(DATA_JSON_PATH, 'w') as f:
        json.dump(data, f, indent=2)
        
    print(f"Successfully wrote {len(new_gaps)} pristine gaps to {DATA_JSON_PATH}")
    if 'total_signals' in locals():
        print(f"Updated total signals to: {total_signals}")

if __name__ == "__main__":
    update_data_json()
