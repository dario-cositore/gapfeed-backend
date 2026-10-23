import json
import os
from glob import glob
from collections import Counter

# Find all agent checkpoint directories
agent_dirs = glob('/home/dario/gapfeed/TheRealAgents/*')
checkpoint_dirs = []
for ad in agent_dirs:
    if os.path.isdir(ad):
        cp = os.path.join(ad, 'memory', 'checkpoints')
        if os.path.isdir(cp):
            checkpoint_dirs.append(cp)

print(f"Found {len(checkpoint_dirs)} checkpoint directories")

all_rounds = []
for cp_dir in checkpoint_dirs:
    round_files = glob(os.path.join(cp_dir, 'round_*.json'))
    all_rounds.extend(round_files)

print(f"Total round_*.json files: {len(all_rounds)}")

stage_counter = Counter()
error_counter = Counter()
potential_signals = 0

print("\n--- Sampling structure of first 5 round files ---")
for f in all_rounds[:5]:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            print(f"\nFile: {os.path.basename(f)}")
            print("Top-level keys:", list(data.keys()))
            if 'stage' in data:
                stage_counter[data['stage']] += 1
                print("Stage:", data['stage'])
            if 'pending_signal_ids' in data:
                pids = data['pending_signal_ids']
                print("pending_signal_ids length:", len(pids) if isinstance(pids, list) else type(pids))
            sig_key = None
            if 'signals' in data:
                sig_key = 'signals'
            elif 'new_signals' in data:
                sig_key = 'new_signals'
            if sig_key:
                sigs = data[sig_key]
                num_sigs = len(sigs) if isinstance(sigs, list) else 0
                print(f"Has {sig_key}: {num_sigs}")
                potential_signals += num_sigs
            if 'error' in data or 'errors' in data:
                err = data.get('error') or data.get('errors')
                print("ERROR found:", str(err)[:200])
                error_counter[str(err)[:100]] += 1
    except Exception as e:
        print(f"Failed to read {f}: {e}")

print("\n--- SUMMARY ---")
print("Stage distribution:", dict(stage_counter))
print("Total potential stuck signals across sampled files:", potential_signals)
if error_counter:
 print("Common errors:", dict(error_counter))
else:
 print("No explicit errors detected in samples.")
