import os
import glob
import datetime

print("=== GAPFEED LIVE LOG ERROR EXTRACTOR ===")
print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Find all agent log files (most recent first)
agent_base = '/home/dario/gapfeed/TheRealAgents'
log_files = []
for agent_dir in glob.glob(f'{agent_base}/*'):
    for pattern in ['*.log', 'logs/*.log', 'memory/*.log', '**/*.log']:
        log_files.extend(glob.glob(os.path.join(agent_dir, pattern), recursive=True))

# Sort by modification time (newest first)
log_files = sorted(log_files, key=os.path.getmtime, reverse=True)

print(f"Found {len(log_files)} log files. Checking the 6 most recent...\n")

keywords = ['ERROR', 'error', 'EXCEPTION', 'exception', 'supabase', 'store', 'writer', 'INSERT', 'commit', 'failed', 'dedup', 'pending_signal_ids', 'schema', 'connection', 'auth']

for lf in log_files[:6]:
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(lf))
    print(f"📄 {os.path.basename(lf)} (modified {mtime})")
    try:
        with open(lf, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-800:] # last 800 lines only
            relevant = [line.strip() for line in lines if any(kw.lower() in line.lower() for kw in keywords)]
            if relevant:
                print(" → LAST RELEVANT LINES:")
                for line in relevant[-15:]: # last 15 matches
                    print(f" {line[:180]}")
            else:
                print(" → No matching errors in last 800 lines.")
    except Exception as e:
        print(f" → Could not read: {e}")
    print("-" * 60)

print("\n✅ EXTRACTION COMPLETE")
print("Paste the FULL output (especially any Supabase connection errors, schema mismatches, or STORE failures) back here.")
