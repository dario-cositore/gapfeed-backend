#!/usr/bin/env python3
"""
Daily aggregation script for GapFeed analytics.
Triggers aggregation via PHP API proxy and saves report locally.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

API_URL = "https://gapfeed.com/api/db.php"
API_KEY = "gapfeed-api-key-2026-secure"

def run_aggregation(date_str: str) -> dict:
    """Trigger aggregation via PHP API and return results."""
    print(f"Running aggregation for {date_str}...")

    resp = requests.post(
        f"{API_URL}?action=aggregate_analytics",
        json={"date": date_str},
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        timeout=30
    )

    if resp.status_code != 200:
        print(f"ERROR: API returned {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()
    if not data.get('ok'):
        print(f"ERROR: Aggregation failed: {data}")
        sys.exit(1)

    return data


def main():
    parser = argparse.ArgumentParser(description='Daily aggregation for GapFeed analytics')
    parser.add_argument('--date', type=str, help='Date to aggregate (YYYY-MM-DD), default: yesterday')
    args = parser.parse_args()

    if args.date:
        target_date = args.date
    else:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    result = run_aggregation(target_date)

    # Build report
    report = {
        'date': result['date'],
        'gaps_aggregated': result.get('gaps_aggregated', 0),
        'top_searches': result.get('top_searches', []),
        'zero_result_searches': result.get('zero_result_searches', []),
        'session_metrics': result.get('session_metrics', {}),
        'trending_gaps': result.get('trending_gaps', [])
    }

    print(json.dumps(report, indent=2))

    # Save to data/analytics/
    data_dir = Path('data/analytics')
    data_dir.mkdir(parents=True, exist_ok=True)
    report_path = data_dir / f"{target_date}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {report_path}")


if __name__ == '__main__':
    main()
