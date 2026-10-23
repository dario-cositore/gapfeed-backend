#!/usr/bin/env python3
"""Cluster unclustered signals into gaps using Gemini 2.5 Flash Lite."""
import sqlite3, json, requests, re, time
from collections import defaultdict

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

print(f"[{time.strftime('%H:%M:%S')}] Starting clustering of unclustered signals...")

conn = sqlite3.connect(LIVE)

# Get all signals without gap_id
unclustered = conn.execute('''
    SELECT id, source, source_url, title, content 
    FROM signals 
    WHERE gap_id IS NULL
''').fetchall()

print(f"Unclustered signals: {len(unclustered):,}")

existing_gaps = {}
for r in conn.execute('SELECT id, title, category FROM gaps'):
    existing_gaps[r[1].lower()] = (r[0], r[2])

print(f"Existing gaps: {len(existing_gaps):,}")

# Phase 1: Extract product + problem from each signal
print("\nPhase 1: Extracting product+problem from signals...")

def extract_product_problem(text):
    """Extract product name and problem type from a comment."""
    prompt = f'''From this text, identify:
1. The product/service being discussed (just the name)
2. The main problem category: pricing, support, bug, missing_feature, complexity, billing, other

Text: "{text[:200]}"

Return JSON: {{"product": "Name", "problem": "category"}}'''

    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'google/gemini-2.5-flash-lite',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.0, 'max_tokens': 50, 'response_format': {'type': 'json_object'}
            },
            timeout=15
        )
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            data = json.loads(content)
            return data.get('product', 'Unknown').strip(), data.get('problem', 'other').strip()
    except:
        pass
    return 'Unknown', 'other'

# Batch process 500 signals
batch_size = 20
processed = 0
clusters = defaultdict(list)
limit = 500  # First 500 for testing

for idx, (signal_id, source, url, title, content) in enumerate(unclustered[:limit]):
    text = (title or '') + ' ' + (content or '')
    if len(text.strip()) < 20:
        continue

    product, problem = extract_product_problem(text)
    cluster_key = f"{product}__{problem}"
    clusters[cluster_key].append(signal_id)
    
    processed += 1
    if processed % 50 == 0:
        print(f"  [{processed}/{limit}] Extracted product+problem")
    time.sleep(0.2)

print(f"\nPhase 1 complete: {processed} signals -> {len(clusters):,} unique product+problem combos")

# Phase 2: Show cluster breakdown
print("\nTop 20 clusters (by signal count):")
sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)
for key, signals in sorted_clusters[:20]:
    product, problem = key.split('__')
    print(f"  {product} — {problem:<15} {len(signals):>4,} signals")

# Phase 3: Create or update gaps
print(f"\nPhase 3: Creating/updating gaps...")
created = 0
updated = 0
new_signals_clustered = 0

for key, signal_ids in sorted_clusters:
    product, problem = key.split('__')
    gap_title = f"{product} — {problem.replace('_', ' ').title() + ' Issues'}"
    gap_key = gap_title.lower()
    
    if gap_key in existing_gaps:
        # Update existing gap
        gap_id, _ = existing_gaps[gap_key]
        updated += 1
        for sig_id in signal_ids:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gap_id, sig_id))
            new_signals_clustered += 1
    else:
        # Create new gap
        sample = conn.execute('SELECT content FROM signals WHERE id = ?', (signal_ids[0],)).fetchone()
        sample_quote = sample[0][:200] if sample and sample[0] else ''
        
        conn.execute('''
            INSERT INTO gaps (title, slug, evidence_count, heat_score, category, gap_validity, signal_ids, sample_quotes, source_types, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'active')
        ''', (
            gap_title,
            gap_title.lower().replace(' ', '-').replace('_', '-').replace('—', '-'),
            len(signal_ids),
            min(0.9, 0.3 + len(signal_ids) * 0.01),
            problem,
            'pending',
            json.dumps(signal_ids[:50]),
            json.dumps([sample_quote[:100]] if sample_quote else []),
            json.dumps(['reddit', 'github', 'hn']),
        ))
        gap_id = conn.lastrowid
        existing_gaps[gap_key] = (gap_id, problem)
        created += 1
        
        for sig_id in signal_ids:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gap_id, sig_id))
            new_signals_clustered += 1

conn.commit()

print(f"\n{'='*60}")
print(f"[{time.strftime('%H:%M:%S')}] CLUSTERING COMPLETE")
print(f"{'='*60}")
print(f"Signals processed:   {processed}")
print(f"Clusters found:      {len(clusters)}")
print(f"New gaps created:    {created}")
print(f"Gaps updated:        {updated}")
print(f"Signals clustered:   {new_signals_clustered}")

total_gaps = conn.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]
total_with_gap = conn.execute('SELECT COUNT(*) FROM signals WHERE gap_id IS NOT NULL').fetchone()[0]
print(f"\nStaging DB now:")
print(f"  Total gaps:       {total_gaps:,}")
print(f"  Signals in gaps:  {total_with_gap:,}")

conn.close()
