import json
import os
import glob
import sqlite3
import hashlib
import datetime
import shutil
from collections import defaultdict

# Auto-detect DB
db_files = glob.glob('/home/dario/gapfeed/**/gapfeed_unified.db', recursive=True)
db_path = db_files[0] if db_files else '/home/dario/gapfeed/code/data/gapfeed_unified.db'
print(f"Using DB: {db_path}")

# Backup
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_path = db_path + f'.backup.unblock.{timestamp}'
shutil.copy2(db_path, backup_path)
print(f"✅ FULL BACKUP CREATED: {backup_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get signals table columns
cursor.execute("PRAGMA table_info(signals)")
columns = [info[1] for info in cursor.fetchall()]
print(f"Signals columns ({len(columns)}): {columns[:15]}...")

# Existing dedup set (text hash)
existing_hashes = set()
cursor.execute("SELECT content FROM signals WHERE content IS NOT NULL")
for row in cursor.fetchall():
    if row[0]:
        h = hashlib.md5(row[0].strip().lower().encode('utf-8')).hexdigest()
        existing_hashes.add(h)
print(f"Loaded {len(existing_hashes):,} existing signal hashes for dedup")

def find_signals(obj, depth=0):
    """Recursively hunt for any list of dicts that look like signals"""
    if depth > 12:
        return []
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and any(k in obj[0] for k in ['text', 'body', 'content', 'selftext', 'post_text', 'description']):
            return obj
        for item in obj[:50]: # limit depth
            res = find_signals(item, depth + 1)
            if res:
                return res
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ['signals', 'new_signals', 'extracted_signals', 'pending_signals', 'items', 'results', 'data']:
                if isinstance(v, list) and v and isinstance(v[0], dict) and any(key in v[0] for key in ['text', 'body', 'content']):
                    return v
                res = find_signals(v, depth + 1)
                if res:
                    return res
    return []

# Find all round files
agent_dirs = glob.glob('/home/dario/gapfeed/TheRealAgents/*')
checkpoint_dirs = [os.path.join(ad, 'memory', 'checkpoints') for ad in agent_dirs if os.path.isdir(os.path.join(ad, 'memory', 'checkpoints'))]
all_rounds = []
for cp_dir in checkpoint_dirs:
 rounds = glob.glob(os.path.join(cp_dir, 'round_*.json'))
 all_rounds.extend(rounds)

print(f"Found {len(all_rounds):,} round_*.json files across {len(checkpoint_dirs)} agents")

inserted = 0
processed = 0
skipped_empty = 0
batch_size = 500
batch = []

print("\n--- Starting unblock (this will take 2-4 minutes) ---")
for i, fpath in enumerate(all_rounds):
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        signals_list = find_signals(data)
        if not signals_list:
            skipped_empty += 1
            continue
        
        for sig in signals_list:
            if not isinstance(sig, dict):
                continue
            text = sig.get('text') or sig.get('body') or sig.get('content') or sig.get('selftext') or sig.get('description')
            if not text or len(text.strip()) < 30:
                continue
            
            # Dedup
            h = hashlib.md5(text.strip().lower().encode('utf-8')).hexdigest()
            if h in existing_hashes:
                continue
            
            # Prepare insert dict (map only columns that exist)
            insert_data = {}
            for col in columns:
                if col == 'id':
                    continue
                val = sig.get(col)
                if val is None:
                    # Try common aliases
                    if col == 'content' and 'text' in sig:
                        val = sig['text']
                    elif col == 'source_url' and 'link' in sig:
                        val = sig['link']
                    elif col == 'created_at' and 'created_utc' in sig:
                        val = sig['created_utc']
                insert_data[col] = val
            
            batch.append(insert_data)
            existing_hashes.add(h) # prevent duplicates within this run
            
            processed += 1
            if len(batch) >= batch_size or i == len(all_rounds) - 1:
                if batch:
                    # Dynamic insert
                    cols = list(batch[0].keys())
                    placeholders = ','.join(['?'] * len(cols))
                    cursor.executemany(
                        f"INSERT INTO signals ({','.join(cols)}) VALUES ({placeholders})",
                        [tuple(d.get(c) for c in cols) for d in batch]
                    )
                    inserted += len(batch)
                    batch = []
                    conn.commit()
                    print(f" → Committed {inserted} new signals so far")
                
                # Mark as processed
                processed_path = fpath + '.processed'
                os.rename(fpath, processed_path)
    
    except Exception as e:
        print(f"⚠️ Failed on {os.path.basename(fpath)}: {e}")
        continue

conn.commit()
conn.close()

print("\n🎉 UNBLOCK COMPLETE")
print(f"Processed: {processed:,} round files")
print(f"Skipped (empty): {skipped_empty:,}")
print(f"NEW SIGNALS INSERTED: {inserted:,}")
print(f"All processed rounds renamed to *.processed.json")