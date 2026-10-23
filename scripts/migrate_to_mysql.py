"""
Migrate data from local SQLite to remote MySQL via PHP API.

Usage: python migrate_to_mysql.py
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.remote_db import RemoteDB

SQLITE_DB = PROJECT_ROOT / 'data' / 'signals.db'


def migrate():
    print("=" * 60)
    print("GapFeed SQLite -> MySQL Migration")
    print("=" * 60)

    # Connect to MySQL via API
    db = RemoteDB()
    print("\n1. Testing MySQL API connection...")
    try:
        result = db.create_schema()
        print(f"   Schema: {result}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return

    # Connect to SQLite
    print(f"\n2. Reading SQLite: {SQLITE_DB}")
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row

    # Migrate signals
    print("\n3. Migrating signals...")
    signals = conn.execute("SELECT * FROM signals").fetchall()
    print(f"   Found {len(signals)} signals in SQLite")

    # Check existing in MySQL
    mysql_count = db.get_signal_count()
    print(f"   MySQL currently has: {mysql_count.get('total', 0)} signals")

    if len(signals) == 0:
        print("   No signals to migrate.")
    else:
        # Convert to dicts and clean up
        signal_dicts = []
        for row in signals:
            s = dict(row)
            # Ensure datetime fields are strings
            for field in ['created_at', 'collected_at']:
                if s.get(field) and not isinstance(s[field], str):
                    s[field] = str(s[field])
            # Ensure numeric fields are numbers
            for field in ['urgency_score', 'specificity_score', 'buyer_intent']:
                if s.get(field) is None:
                    s[field] = 0
                else:
                    s[field] = float(s[field])
            # Ensure int fields
            for field in ['is_processed', 'synthesized']:
                if s.get(field) is None:
                    s[field] = 0
            # JSON encode metadata
            if s.get('metadata') and not isinstance(s['metadata'], str):
                s['metadata'] = json.dumps(s['metadata'])
            signal_dicts.append(s)

        # Bulk insert in batches of 50
        batch_size = 50
        total_inserted = 0
        for i in range(0, len(signal_dicts), batch_size):
            batch = signal_dicts[i:i+batch_size]
            try:
                result = db.insert_signals_bulk(batch)
                inserted = result.get('inserted', 0)
                total_inserted += inserted
                print(f"   Batch {i//batch_size + 1}: {inserted} inserted")
            except Exception as e:
                print(f"   Batch {i//batch_size + 1} ERROR: {e}")
        print(f"   Total migrated: {total_inserted}")

    # Migrate briefs
    print("\n4. Migrating briefs...")
    briefs = conn.execute("SELECT * FROM briefs").fetchall()
    print(f"   Found {len(briefs)} briefs in SQLite")

    for row in briefs:
        b = dict(row)
        try:
            db.upsert_brief(
                vertical=b['vertical'],
                query=b['query'],
                brief_json=b['brief_json'],
                brief_md=b.get('brief_md'),
                signal_count=b.get('signal_count', 0),
                quality=b.get('quality', 'low')
            )
            print(f"   Brief: {b['query'][:50]}... OK")
        except Exception as e:
            print(f"   Brief ERROR: {e}")

    # Migrate scan_log
    print("\n5. Migrating scan logs...")
    scans = conn.execute("SELECT * FROM scan_log").fetchall()
    print(f"   Found {len(scans)} scan logs in SQLite")

    for row in scans:
        s = dict(row)
        try:
            scan_id = db.log_scan(s['vertical'], s['source'], s.get('category'))
            db.complete_scan(scan_id, s.get('signals_found', 0), s.get('signals_new', 0))
            print(f"   Scan: {s['source']} ({s['vertical']}) OK")
        except Exception as e:
            print(f"   Scan ERROR: {e}")

    conn.close()

    # Verify
    print("\n6. Verification...")
    final = db.get_signal_count()
    print(f"   MySQL total signals: {final.get('total', 0)}")
    briefs_final = db.get_briefs()
    print(f"   MySQL briefs: {len(briefs_final)}")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == '__main__':
    migrate()
