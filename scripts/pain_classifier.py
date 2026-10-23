#!/usr/bin/env python3
"""
HYBRID PAIN DETECTION + CLUSTERING
Step 1: Classify existing 5K signals for real pain
Step 2: Cluster into gaps with urgency/heat scores
"""
import sqlite3, json, hashlib, time, random
from datetime import datetime, timezone
import subprocess

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

# Step 1: Simple keyword pre-filter (keep 70%, discard 30%)
PAIN_WORDS = ['sucks', 'hate', 'terrible', 'broken', 'crash', 'expensive', 'complaint',
              'annoying', 'frustrating', 'worst', 'bad', 'issue', 'bug', 'problem', 
              'slow', 'lag', 'refund', 'cancel', 'rip', 'scam', 'trash', 'garbage',
              'useless', 'never', 'avoid', 'warning', 'nightmare', 'horrible', 'disaster',
              'waste', 'disappointing', 'confusing', 'complicated', 'difficult', 'error',
              'fails', 'fail', 'crash', 'freeze', 'stuck', 'useless', 'pointless']

def classify_simple(text):
    """Simple but effective pain classifier"""
    text_lower = text.lower()
    if not text_lower:
        return False, 0.0, 'empty'
    
    # Must be at least 15 chars
    if len(text_lower) < 15:
        return False, 0.0, 'too short'
    
    # Has pain words
    pain_count = sum(1 for w in PAIN_WORDS if w in text_lower)
    if pain_count == 0:
        return False, 0.0, 'no pain words'
    
    # Score based on pain intensity
    intensity_words = {
        'sucks': 0.9, 'terrible': 0.9, 'worst': 0.9, 'scam': 0.9, 'rip': 0.9,
        'trash': 0.8, 'nightmare': 0.8, 'horrible': 0.8, 'disaster': 0.8,
        'hate': 0.8, 'broken': 0.8, 'crash': 0.7, 'frustrating': 0.7,
        'expensive': 0.7, 'refund': 0.7, 'cancel': 0.6, 'avoid': 0.6,
        'never': 0.5, 'bad': 0.5, 'issue': 0.5, 'bug': 0.5, 'problem': 0.5,
        'slow': 0.5, 'error': 0.5, 'fail': 0.5
    }
    
    score = 0
    for word, val in intensity_words.items():
        if word in text_lower:
            score = max(score, val)
    
    # Bonus for multiple pain indicators
    if pain_count >= 2:
        score = min(score + 0.1, 0.95)
    
    # Must be about the product, not random
    # Check for complaint patterns
    patterns = ['don\'t', 'can\'t', 'won\'t', 'never', 'should', 'wish', 'why', 'but']
    pattern_count = sum(1 for p in patterns if p in text_lower)
    
    if pattern_count >= 1:
        score += 0.05
    
    if score < 0.5:
        return False, score, 'low pain score'
    
    return True, score, 'pain detected'

def get_conn():
    return sqlite3.connect(DB)

def main():
    conn = get_conn()
    c = conn.cursor()
    
    # Get all signals
    total = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    print(f'Total signals: {total}')
    print()
    
    # Sample and analyze
    pain_count = 0
    non_pain = 0
    pain_examples = []
    
    for row in c.execute('SELECT id, content, subreddit FROM signals'):
        sid, content, product = row
        is_pain, score, reason = classify_simple(content)
        
        if is_pain:
            pain_count += 1
            c.execute('''UPDATE signals SET quality_tier = ?, pain_category = ?
                         WHERE id = ?''', 
                     ('high' if score > 0.7 else 'medium', 
                      'general', sid))
            pain_examples.append((product, content[:80], score))
        else:
            non_pain += 1
            c.execute('''UPDATE signals SET quality_tier = 'low' WHERE id = ?''', (sid,))
        
        if pain_count + non_pain % 500 == 0:
            conn.commit()
            print(f'  Processed {pain_count + non_pain}: {pain_count} pain, {non_pain} non-pain')
    
    conn.commit()
    
    print()
    print(f'=== PAIN CLASSIFICATION RESULTS ===')
    print(f'Pain signals: {pain_count} ({pain_count/total*100:.1f}%)')
    print(f'Non-pain: {non_pain} ({non_pain/total*100:.1f}%)')
    print()
    
    # Now cluster the pain signals
    print('=== CLUSTERING PAIN SIGNALS ===')
    
    # Group by product + pain keywords
    pain_signals = c.execute('''
        SELECT id, content, subreddit, product_category 
        FROM signals WHERE quality_tier != 'low'
    ''').fetchall()
    
    print(f'Clustering {len(pain_signals)} pain signals...')
    
    clusters = {}
    for sid, content, product, category in pain_signals:
        text = content.lower()
        
        # Determine pain type
        pain_type = 'general'
        pain_categories = {
            'pricing': ['expensive', 'overpriced', 'cost', 'pricing', 'subscription', 'fee', 'charge', 'money'],
            'support': ['support', 'customer service', 'response', 'ticket', 'help', 'ignore'],
            'performance': ['slow', 'lag', 'crash', 'freeze', 'performance', 'timeout'],
            'complexity': ['complex', 'confusing', 'hard', 'difficult', 'complicated', 'learning'],
            'bug': ['bug', 'broken', 'error', 'glitch', 'work', 'issue', 'problem'],
            'missing': ['missing', 'lack', 'should have', 'need', 'wish', 'feature'],
            'alternative': ['alternative', 'switched', 'switching', 'vs', 'competitor']
        }
        for cat, kws in pain_categories.items():
            if any(kw in text for kw in kws):
                pain_type = cat
                break
        
        cluster_key = f'{product}|{pain_type}'
        if cluster_key not in clusters:
            clusters[cluster_key] = []
        clusters[cluster_key].append((sid, content))
    
    print(f'Found {len(clusters)} clusters')
    
    # Insert gaps
    gaps_created = 0
    for key, signals in sorted(clusters.items(), key=lambda x: -len(x[1])):
        product, pain_type = key.split('|')
        
        sample = random.choice(signals)[1][:120]
        heat = min(len(signals) / 20, 0.9)
        opp = round(1.0 - heat, 2)
        
        c.execute('''INSERT INTO gaps (
            gap_id, category, description, source_type,
            evidence_count, signal_ids, sample_quotes,
            heat_score, urgency_score, confidence,
            opportunity_score, status,
            created_at, updated_at, priority,
            pain_category, product_vertical
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            hashlib.sha256(key.encode()).hexdigest()[:16],
            pain_type,
            f'{product} users report {pain_type} issues',
            'youtube',
            len(signals),
            json.dumps([s[0] for s in signals[:50]]),
            json.dumps([sample]),
            heat,
            heat,
            min(len(signals) / 100, 0.95),
            opp,
            'confirmed',
            datetime.now(tz=timezone.utc).isoformat(),
            datetime.now(tz=timezone.utc).isoformat(),
            'high' if len(signals) > 5 else 'low',
            pain_type,
            product
        ))
        gaps_created += 1
    
    conn.commit()
    
    print()
    print('=== GAPS CREATED ===')
    print(f'Total gaps: {gaps_created}')
    print()
    print('Top 10 gaps by evidence count:')
    for row in c.execute('''
        SELECT category, description, evidence_count, heat_score 
        FROM gaps 
        ORDER BY evidence_count DESC 
        LIMIT 10
    '''):
        print(f'  {row[1]}: {row[2]} signals (heat: {row[3]:.2f})')
    
    conn.close()
    print()
    print('✅ DONE — Pain classification + clustering complete!')

if __name__ == '__main__':
    main()
