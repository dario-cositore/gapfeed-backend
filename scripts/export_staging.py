#!/usr/bin/env python3
"""Push staging DB to server DB."""
import sqlite3, json, time

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

conn = sqlite3.connect(LIVE, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")

# Export to JSON for safe transfer
print("Exporting staging DB...")

# Export signals
signals = conn.execute('''
    SELECT source, source_url, platform_id, subreddit, author, title, content, 
           created_at, collected_at, vertical, product_category, pain_category, 
           display_category, signal_type, location, urgency_score, specificity_score, 
           buyer_intent, quality_tier, gap_id, category, sentiment, competitor_mentions,
           metadata, is_processed, synthesized, confidence, actionability, urgency,
           product_vertical
    FROM signals
''').fetchall()
print(f"Signals to export: {len(signals):,}")

# Export gaps
gaps = conn.execute('''
    SELECT title, slug, description, evidence_count, heat_score, category, 
           source_types, signal_ids, sample_quotes, competitors, gap_validity,
           last_validated_at, opportunity_score, status
    FROM gaps
''').fetchall()
print(f"Gaps to export: {len(gaps):,}")

# Write to files for SCP
with open('/tmp/staging_signals.json', 'w') as f:
    json.dump(signals, f)
    
with open('/tmp/staging_gaps.json', 'w') as f:
    json.dump(gaps, f)

print(f"\nReady:")
print(f"  Signals: /tmp/staging_signals.json ({len(signals):,} rows)")
print(f"  Gaps: /tmp/staging_gaps.json ({len(gaps):,} rows)")
conn.close()
