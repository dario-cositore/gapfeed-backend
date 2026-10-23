#!/usr/bin/env python
"""
Create MySQL analytics tables for GapFeed tracking.
Uses RemoteDB (PHP API) to run migration.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.remote_db import RemoteDB


def main():
    print("Creating GapFeed analytics tables via PHP API...")
    print("-" * 50)
    
    db = RemoteDB()
    try:
        result = db.create_schema()
        print("Schema creation result:", result)
        print("Raw results:", result.get('results', []))
        if result.get('ok'):
            print("\nTables created successfully:")
            for r in result.get('results', []):
                print(f"  - {r}")
        else:
            print("\nERROR: Schema creation failed")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    print("-" * 50)
    print("Done.")


if __name__ == '__main__':
    main()