"""
gapfeed - Shared Database Layer

Single source of truth for all signal data across verticals.
All verticals write to and read from the same signals.db.
"""
import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'signals.db'


def get_db() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database schema. Creates tables if they don't exist."""
    conn = get_db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_url TEXT,
            platform_id TEXT UNIQUE,
            subreddit TEXT,
            author TEXT,
            title TEXT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            vertical TEXT NOT NULL DEFAULT 'general',
            product_category TEXT,
            pain_category TEXT,
            signal_type TEXT DEFAULT NULL,
            location TEXT DEFAULT NULL,
            urgency_score REAL DEFAULT 0,
            specificity_score REAL DEFAULT 0,
            buyer_intent REAL DEFAULT 0,
            quality_tier TEXT DEFAULT 'noise',
            sentiment TEXT DEFAULT 'neutral',
            competitor_mentions TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}',
            is_processed INTEGER DEFAULT 0,
            synthesized INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vertical TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            query TEXT NOT NULL,
            brief_json TEXT NOT NULL,
            brief_md TEXT,
            signal_count INTEGER DEFAULT 0,
            quality TEXT DEFAULT 'low',
            generated_at TEXT NOT NULL,
            UNIQUE(vertical, query_hash)
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vertical TEXT NOT NULL,
            source TEXT NOT NULL,
            category TEXT,
            signals_found INTEGER DEFAULT 0,
            signals_new INTEGER DEFAULT 0,
            started_at TEXT NOT NULL,
            completed_at TEXT
        );
    """)

    # Indexes (ignore errors if they already exist)
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_signals_vertical ON signals(vertical)",
        "CREATE INDEX IF NOT EXISTS idx_signals_pain_category ON signals(pain_category)",
        "CREATE INDEX IF NOT EXISTS idx_signals_quality_tier ON signals(quality_tier)",
        "CREATE INDEX IF NOT EXISTS idx_signals_urgency ON signals(urgency_score)",
        "CREATE INDEX IF NOT EXISTS idx_signals_collected ON signals(collected_at)",
        "CREATE INDEX IF NOT EXISTS idx_signals_processed ON signals(is_processed)",
        "CREATE INDEX IF NOT EXISTS idx_signals_subreddit ON signals(subreddit)",
        "CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type)",
        "CREATE INDEX IF NOT EXISTS idx_signals_location ON signals(location)",
        "CREATE INDEX IF NOT EXISTS idx_briefs_vertical ON briefs(vertical)",
        "CREATE INDEX IF NOT EXISTS idx_briefs_hash ON briefs(query_hash)",
    ]:
        try:
            conn.execute(idx)
        except Exception:
            pass

    # Migrate: add signal_type column to existing databases
    try:
        conn.execute("ALTER TABLE signals ADD COLUMN signal_type TEXT DEFAULT NULL")
    except Exception:
        pass  # Column already exists

    # Migrate: add location column to existing databases
    try:
        conn.execute("ALTER TABLE signals ADD COLUMN location TEXT DEFAULT NULL")
    except Exception:
        pass  # Column already exists

    conn.commit()
    conn.close()


def bulk_insert_signals(signals: list) -> int:
    """Insert signals, skip duplicates by platform_id. Returns count of new signals."""
    if not signals:
        return 0

    conn = get_db()
    new_count = 0

    for sig in signals:
        platform_id = sig.get('platform_id', '')
        if platform_id:
            existing = conn.execute(
                "SELECT id FROM signals WHERE platform_id = ?", (platform_id,)
            ).fetchone()
            if existing:
                continue

        try:
            conn.execute("""
                INSERT INTO signals (
                    source, source_url, platform_id, subreddit, author,
                    title, content, created_at, collected_at, vertical,
                    product_category, pain_category, signal_type, location,
                    urgency_score, specificity_score, buyer_intent,
                    quality_tier, sentiment, competitor_mentions,
                    is_processed, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sig.get('source', 'reddit'),
                sig.get('source_url', ''),
                platform_id,
                sig.get('subreddit', ''),
                sig.get('author', ''),
                sig.get('title', ''),
                sig.get('content', ''),
                sig.get('created_at', ''),
                sig.get('collected_at', datetime.now(timezone.utc).isoformat()),
                sig.get('vertical', 'general'),
                sig.get('product_category', ''),
                sig.get('pain_category', 'uncategorized'),
                sig.get('signal_type', None),
                sig.get('location', None),
                sig.get('urgency_score', 0),
                sig.get('specificity_score', 0),
                sig.get('buyer_intent', 0),
                sig.get('quality_tier', 'noise'),
                sig.get('sentiment', 'neutral'),
                json.dumps(sig.get('competitor_mentions', [])),
                sig.get('is_processed', 0),
                json.dumps(sig.get('metadata', {}))
            ))
            new_count += 1
        except Exception as e:
            print(f"  Insert error: {e}")

    conn.commit()
    conn.close()
    return new_count


def search_signals(query: str, vertical: str = None, min_tier: str = 'bronze',
                   limit: int = 200) -> list:
    """Search signals by query across content/title, optionally filtered by vertical."""
    tier_order = {'noise': 0, 'bronze': 1, 'silver': 2, 'gold': 3}
    min_tier_val = tier_order.get(min_tier, 1)

    conn = get_db()

    query_like = f"%{query}%"
    sql = """
        SELECT * FROM signals
        WHERE quality_tier != 'noise'
          AND (title LIKE ? OR content LIKE ? OR product_category LIKE ? OR pain_category LIKE ?)
    """
    params = [query_like, query_like, query_like, query_like]

    if vertical:
        sql += " AND vertical = ?"
        params.append(vertical)

    sql += " ORDER BY urgency_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    # Filter by minimum tier
    return [dict(r) for r in rows if tier_order.get(r['quality_tier'], 0) >= min_tier_val]


def get_signal_count(vertical: str = None) -> dict:
    """Get signal counts by quality tier."""
    conn = get_db()

    where = ""
    params = []
    if vertical:
        where = "WHERE vertical = ?"
        params = [vertical]

    total = conn.execute(f"SELECT COUNT(*) FROM signals {where}", params).fetchone()[0]
    gold = conn.execute(f"SELECT COUNT(*) FROM signals {where} {'AND' if where else 'WHERE'} quality_tier='gold'", params).fetchone()[0]
    silver = conn.execute(f"SELECT COUNT(*) FROM signals {where} {'AND' if where else 'WHERE'} quality_tier='silver'", params).fetchone()[0]
    bronze = conn.execute(f"SELECT COUNT(*) FROM signals {where} {'AND' if where else 'WHERE'} quality_tier='bronze'", params).fetchone()[0]
    noise = conn.execute(f"SELECT COUNT(*) FROM signals {where} {'AND' if where else 'WHERE'} quality_tier='noise'", params).fetchone()[0]
    unprocessed = conn.execute(f"SELECT COUNT(*) FROM signals {where} {'AND' if where else 'WHERE'} is_processed=0", params).fetchone()[0]

    conn.close()
    return {
        'total': total, 'gold': gold, 'silver': silver,
        'bronze': bronze, 'noise': noise, 'unprocessed': unprocessed
    }


def log_scan(vertical: str, source: str, category: str = None) -> int:
    """Log a scan operation, return the scan ID."""
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO scan_log (vertical, source, category, started_at)
        VALUES (?, ?, ?, ?)
    """, (vertical, source, category, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    scan_id = cursor.lastrowid
    conn.close()
    return scan_id


def complete_scan(scan_id: int, signals_found: int, signals_new: int):
    """Mark a scan as complete."""
    conn = get_db()
    conn.execute("""
        UPDATE scan_log SET signals_found=?, signals_new=?, completed_at=?
        WHERE id=?
    """, (signals_found, signals_new, datetime.now(timezone.utc).isoformat(), scan_id))
    conn.commit()
    conn.close()


