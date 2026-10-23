#!/usr/bin/env python3
import sqlite3, json, random
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

conn = sqlite3.connect(DB)
c = conn.cursor()

pain_signals = c.execute("""
    SELECT id, content, product_vertical, pain_category
    FROM signals WHERE quality_tier = 'high'
""").fetchall()

clusters = {}

for sid, content, product, cat in pain_signals:
    if not product: product = 'unknown'
    if not cat: cat = 'general'
    key = f'{product}||{cat}'
    if key not in clusters:
        clusters[key] = []
    clusters[key].append({'id': sid, 'content': content[:200]})

print(f'Found {len(clusters)} clusters from {len(pain_signals)} pain signals')

now = datetime.now(tz=timezone.utc).isoformat()
gaps_created = 0

for key in sorted(clusters, key=lambda k: -len(clusters[k])):
    sids = clusters[key]
    if len(sids) < 3:
        continue
        
    product, cat = key.split('||')
    evidence = len(sids)
    heat = round(min(evidence / 30, 0.95), 3)
    opp = round(1.0 - heat, 2)
    
    title = f"{product.title()} — {cat.title()} Pain"
    slug = f"{product.lower()}-{cat.lower()}-pain"
    desc = f"Users report {cat} issues with {product.title()}"
    
    quotes = [s['content'] for s in random.sample(sids, min(5, len(sids)))]
    signal_ids = [s['id'] for s in sids[:100]]
    
    c.execute('''INSERT INTO gaps (
        title, slug, description, evidence_count, heat_score,
        category, source_types, signal_ids, sample_quotes,
        competitors, gap_validity, last_validated_at,
        opportunity_score, status, created_at, updated_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        title, slug, desc, evidence, heat,
        cat, 'youtube', json.dumps(signal_ids), json.dumps(quotes),
        '[]', 'valid', now,
        opp, 'active', now, now
    ))
    gaps_created += 1

# Update signals with gap_id
gap_data = c.execute('SELECT id, signal_ids FROM gaps').fetchall()
for gid, sig_json in gap_data:
    sids = json.loads(sig_json)
    c.execute(f'UPDATE signals SET gap_id = ? WHERE id IN ({",".join("?" * len(sids))})',
              [gid] + sids)

conn.commit()

print(f'\nGaps created: {gaps_created}')
print('\nTOP 5 GAPS:')
for row in c.execute('SELECT title, evidence_count, heat_score FROM gaps ORDER BY evidence_count DESC LIMIT 5'):
    print(f'  {row[0]}: {row[1]} signals (heat: {row[2]})')

conn.close()
print('\n✅ Gaps created successfully')
