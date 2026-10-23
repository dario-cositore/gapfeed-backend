#!/usr/bin/env python3
"""
PAIN CLASSIFIER + GAP CLUSTERING
"""
import sqlite3, json, hashlib, random, re
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

PAIN_WORDS = ['sucks', 'hate', 'terrible', 'broken', 'crash', 'expensive', 
              'complaint', 'annoying', 'frustrating', 'worst', 'bad', 
              'issue', 'bug', 'problem', 'slow', 'lag', 'refund', 'cancel', 
              'rip', 'scam', 'trash', 'garbage', 'useless', 'never', 
              'avoid', 'warning', 'nightmare', 'horrible', 'disaster',
              'waste', 'disappointing', 'confusing', 'complicated', 
              'difficult', 'error', 'fails', 'fail', 'freeze', 'stuck']

INTENSITY = {
    'sucks': 0.9, 'terrible': 0.9, 'worst': 0.9, 'scam': 0.9, 
    'trash': 0.8, 'nightmare': 0.8, 'horrible': 0.8, 'hate': 0.8,
    'broken': 0.8, 'crash': 0.7, 'frustrating': 0.7, 'expensive': 0.7,
    'refund': 0.7, 'cancel': 0.6, 'avoid': 0.6, 'bad': 0.5,
    'issue': 0.5, 'bug': 0.5, 'problem': 0.5, 'slow': 0.5,
    'error': 0.5, 'fail': 0.5, 'freeze': 0.6, 'bug': 0.5
}

PAIN_CATS = {
    'pricing': ['expensive', 'overpriced', 'cost', 'pricing', 'subscription', 'fee', 'charge', 'money', 'price'],
    'support': ['support', 'customer service', 'response', 'ticket', 'help', 'ignore', 'email'],
    'performance': ['slow', 'lag', 'crash', 'freeze', 'performance', 'timeout', 'stuck', 'hanging'],
    'complexity': ['complex', 'confusing', 'hard', 'difficult', 'complicated', 'learning'],
    'bug': ['bug', 'broken', 'error', 'glitch', 'issue', 'problem'],
    'missing': ['missing', 'lack', 'should have', 'need', 'wish', 'feature'],
    'competitor': ['alternative', 'switched', 'switching', 'vs', 'competitor', 'instead'],
    'usability': ['interface', 'ux', 'ui', 'design', 'workflow', 'navigation'],
}

conn = sqlite3.connect(DB)
c = conn.cursor()

print('=== CLASSIFYING SIGNALS ===')
total = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
print(f'Total: {total:,}')

pain_count = 0
for row in c.execute('SELECT id, content FROM signals'):
    sid, text = row
    text_lower = text.lower()
    
    if len(text_lower) < 10:
        c.execute('UPDATE signals SET quality_tier = ? WHERE id = ?', ('low', sid))
        continue
    
    pain_matches = sum(1 for w in PAIN_WORDS if w in text_lower)
    if pain_matches == 0:
        c.execute('UPDATE signals SET quality_tier = ? WHERE id = ?', ('low', sid))
        continue
    
    score = max(INTENSITY.get(w, 0.5) for w in PAIN_WORDS if w in text_lower)
    if pain_matches >= 2:
        score = min(score + 0.1, 0.95)
    
    if score < 0.5:
        c.execute('UPDATE signals SET quality_tier = ? WHERE id = ?', ('low', sid))
        continue
    
    tier = 'high' if score > 0.7 else 'medium'
    
    # Pain category
    cat = 'general'
    for pain_cat, kws in PAIN_CATS.items():
        if any(kw in text_lower for kw in kws):
            cat = pain_cat
            break
    
    c.execute('UPDATE signals SET quality_tier = ?, pain_category = ?, urgency_score = ?, buyer_intent = ? WHERE id = ?',
              (tier, cat, score, score, sid))
    pain_count += 1
    
    if pain_count % 1000 == 0:
        conn.commit()
        print(f'  {pain_count} pain signals found...')

conn.commit()
print(f'Total pain signals: {pain_count} ({pain_count/total*100:.1f}%)')

print('\n=== CLUSTERING ===')

signals = c.execute('''
    SELECT id, content, product_category, pain_category 
    FROM signals WHERE quality_tier IN ('high', 'medium')
''').fetchall()

clusters = {}
for sid, content, product, pain_cat in signals:
    text = content.lower()
    for pc, kws in PAIN_CATS.items():
        if any(kw in text for kw in kws):
            pain_cat = pc
            break
    
    key = f'{product}||{pain_cat}'
    if key not in clusters:
        clusters[key] = []
    clusters[key].append({'id': sid, 'text': content[:200]})

print(f'Found {len(clusters)} clusters')

# Create gaps
now = datetime.now(tz=timezone.utc).isoformat()
gaps_created = 0

for key in sorted(clusters, key=lambda k: -len(clusters[k])):
    sids = clusters[key]
    if len(sids) < 3:
        continue
        
    product, pain_cat = key.split('||')
    evidence = len(sids)
    heat = min(evidence / 30, 0.95)
    opp = round(1.0 - heat, 2)
    
    title = f"{product.title()} - {pain_cat.title()} Pain"
    slug = f"{product.lower()}-{pain_cat.lower()}-pain"
    desc = f"Users report {pain_cat} issues with {product.title()}"
    
    quotes = [s['text'] for s in random.sample(sids, min(5, len(sids)))]
    signal_ids = [s['id'] for s in sids[:100]]
    
    c.execute('''INSERT INTO gaps (
        title, slug, description, evidence_count, heat_score,
        category, source_types, signal_ids, sample_quotes,
        competitors, gap_validity, last_validated_at,
        opportunity_score, status, created_at, updated_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
        title, slug, desc, evidence, round(heat, 3),
        pain_cat, 'youtube', json.dumps(signal_ids), json.dumps(quotes),
        '[]', 'valid', now,
        round(opp, 2), 'active', now, now
    ))
    gaps_created += 1

# Update signals with gap_id
gap_signals = c.execute('SELECT id, signal_ids FROM gaps WHERE evidence_count > 0').fetchall()
for gid, sig_json in gap_signals:
    sids = json.loads(sig_json)
    c.execute('UPDATE signals SET gap_id = ? WHERE id IN ({})'.format(','.join('?' * len(sids))),
              [gid] + sids)

conn.commit()

print(f'\nGaps created: {gaps_created}')
print('\nTop gaps:')
for row in c.execute('SELECT title, evidence_count, heat_score FROM gaps ORDER BY evidence_count DESC LIMIT 10'):
    print(f'  {row[0]}: {row[1]} (heat: {row[2]})')

conn.close()
print('\n✅ DONE')