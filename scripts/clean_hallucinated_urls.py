import json
import os
import glob
import sqlite3

PRISTINE_DIR = "/home/dario/.openclaw/workspace/3. gapfeed/data/pristine_gaps"
MERGED_DB = "/home/dario/.openclaw/workspace/3. gapfeed/data/gapfeed_merged.db"

conn_merged = sqlite3.connect(MERGED_DB)
c_merged = conn_merged.cursor()

def is_url_real(url):
    if not url or url.strip() == "":
        return False
    c_merged.execute("SELECT 1 FROM signals WHERE source_url = ?", (url,))
    row = c_merged.fetchone()
    return row is not None

for filepath in glob.glob(os.path.join(PRISTINE_DIR, "*.json")):
    with open(filepath, 'r') as f:
        gap = json.load(f)
    
    modified = False
    if "sample_quotes" in gap:
        for quote in gap["sample_quotes"]:
            original_url = quote.get("url", "")
            if original_url and not is_url_real(original_url):
                print(f"Removing hallucinated URL in {gap.get('slug')}: {original_url}")
                quote["url"] = ""
                modified = True
                
    if modified:
        with open(filepath, 'w') as f:
            json.dump(gap, f, indent=2)

print("Finished checking and removing hallucinated URLs from pristine gaps.")