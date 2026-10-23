import os
import glob
import re
import sqlite3
import datetime

print("=== GAPFEED INGESTION DIAGNOSTIC - STORE FAILURE ===")
print(f"Run time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 1. Locate all relevant Python files
base = '/home/dario/gapfeed'
agent_dirs = glob.glob(f'{base}/TheRealAgents/*')
py_files = []
for ad in agent_dirs:
    for root, _, files in os.walk(ad):
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))

print(f"Found {len(py_files)} Python files across agents")

# 2. Search for STORE / writer / commit logic
keywords = ['STORE', 'store', 'writer', 'write_to_db', 'insert_into', 'signals', 'commit', 'executemany', 'INSERT INTO signals']
matches = []
for pf in py_files:
    try:
        with open(pf, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            for kw in keywords:
                if kw.lower() in content.lower():
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if kw.lower() in line.lower():
                            matches.append((pf, i+1, line.strip()))
                            break
    except:
        continue

print(f"\nFound {len(matches)} potential STORE-related lines:")
for fpath, lineno, line in matches[:30]: # first 30 only
    print(f" {os.path.basename(fpath)}:{lineno} → {line[:120]}")

# 3. Look for error logs and recent activity
log_files = []
for ad in agent_dirs:
    for pat in ['*.log', 'memory/*.log', 'logs/*.log', 'checkpoints/*.log', '*.txt']:
        log_files.extend(glob.glob(os.path.join(ad, '**', pat), recursive=True))

print(f"\nFound {len(log_files)} log files")
recent_logs = sorted(log_files, key=os.path.getmtime, reverse=True)[:10]
for lf in recent_logs:
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(lf))
    print(f" RECENT: {os.path.basename(lf)} (modified {mtime})")

# 4. Check DB schema vs expected insert columns
db_files = glob.glob(f'{base}/**/gapfeed_unified.db', recursive=True)
if db_files:
    db_path = db_files[0]
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(signals)")
    cols = [row[1] for row in cursor.fetchall()]
    print(f"\nCurrent signals table columns ({len(cols)}):")
    print(cols)
    conn.close()

# 5. Check for Reddit API / proxy config
config_hits = []
for pf in py_files:
    if 'reddit' in pf.lower() or 'direct' in pf.lower():
        try:
            with open(pf, 'r', encoding='utf-8', errors='ignore') as f:
                if any(x in f.read().lower() for x in ['praw', 'reddit', 'client_id', 'proxy', 'tor']):
                    config_hits.append(pf)
        except:
            pass
print(f"\nReddit-related files: {config_hits}")

print("\n✅ DIAGNOSTIC COMPLETE")
print("Paste the FULL output above back to me.")
print("It will contain the exact STORE code block that is failing + any hidden exceptions.")
