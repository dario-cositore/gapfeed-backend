"""
gapfeed - Local API server.

Revives the Procfile target (`gunicorn ui.server:app`) and the documented
local UI port (docs/MASTER.md: server on port 5002). This is the local
backend tree consumers use until api.gapfeed.com has a DNS record — the
dead endpoint is never hardcoded anywhere.

Loopback only (127.0.0.1): the signals table holds market research, not
operator secrets, and nothing here is meant to leave the machine.

Endpoints:
    GET /api/health                      -> {"status": "ok", ...}
    GET /api/signals?...                 -> {"signals": [...], "count": n, "generated_at": ...}

/api/signals mirrors the response shape of the production dispatcher
`api/db.php?action=get_signals` ({"signals": [...], "count": n}) so a
consumer written against this endpoint can swap to production later by
changing the base URL only.

Query parameters (all optional):
    since         ISO timestamp; only signals collected after this (exclusive)
    vertical      exact vertical match, e.g. legal_tech, crm_ops, logistics
    min_urgency   0..1; minimum urgency_score (default 0)
    quality_tier  exact tier match: gold | silver | bronze | noise
    signal_type   exact signal_type match
    limit         max rows, capped at 500 (default 50)
"""

import json
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from shared.signals_db import get_db, init_db

app = Flask(__name__)

# Creates the schema on import, so both `gunicorn ui.server:app` and
# `python -m ui.server` come up ready to answer queries.
init_db()

VALID_TIERS = {"gold", "silver", "bronze", "noise"}


@app.get("/api/health")
def health():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    conn.close()
    return jsonify({
        "status": "ok",
        "signals_total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/api/signals")
def api_signals():
    args = request.args

    vertical = args.get("vertical") or None
    quality_tier = args.get("quality_tier") or None
    signal_type = args.get("signal_type") or None
    since = args.get("since") or None

    if quality_tier and quality_tier not in VALID_TIERS:
        return jsonify({"error": f"quality_tier must be one of {sorted(VALID_TIERS)}"}), 400

    try:
        min_urgency = max(0.0, min(1.0, float(args.get("min_urgency", 0))))
        limit = max(1, min(500, int(args.get("limit", 50))))
    except ValueError:
        return jsonify({"error": "min_urgency must be a number and limit an integer"}), 400

    sql = "SELECT * FROM signals WHERE urgency_score >= ?"
    params: list = [min_urgency]
    if since:
        sql += " AND collected_at > ?"
        params.append(since)
    if vertical:
        sql += " AND vertical = ?"
        params.append(vertical)
    if quality_tier:
        sql += " AND quality_tier = ?"
        params.append(quality_tier)
    if signal_type:
        sql += " AND signal_type = ?"
        params.append(signal_type)
    sql += " ORDER BY urgency_score DESC, collected_at DESC LIMIT ?"
    params.append(limit)

    conn = get_db()
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    conn.close()

    # The JSON columns travel as text; decode them so consumers get real
    # structures, matching what the production dispatcher returns.
    for row in rows:
        for key in ("competitor_mentions", "metadata"):
            try:
                row[key] = json.loads(row[key]) if row[key] else ([] if key == "competitor_mentions" else {})
            except (TypeError, ValueError):
                pass

    return jsonify({
        "signals": rows,
        "count": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    # Loopback by default; PORT respected for parity with the Procfile.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5002)))
