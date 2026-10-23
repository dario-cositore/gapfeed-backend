"""
Reset all signals to unprocessed so Maya re-classifies them with the new LLM key.
Run once: python scripts/reset_classifications.py
"""
import os
import pymysql

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', ''),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', ''),
    'port': 3306,
    'charset': 'utf8mb4',
}

def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # Count current state
            cur.execute("SELECT COUNT(*) FROM signals WHERE is_processed = 1")
            processed = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM signals")
            total = cur.fetchone()[0]
            print(f"Total signals: {total}")
            print(f"Currently processed: {processed}")
            
            # Reset all to unprocessed
            cur.execute("UPDATE signals SET is_processed = 0, quality_tier = NULL")
            affected = cur.rowcount
            conn.commit()
            print(f"Reset {affected} signals to unprocessed")
            
            # Verify
            cur.execute("SELECT COUNT(*) FROM signals WHERE is_processed = 0")
            unprocessed = cur.fetchone()[0]
            print(f"Now unprocessed: {unprocessed}")
            print("\nMaya will pick these up on her next cycle.")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
