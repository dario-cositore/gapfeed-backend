import sqlite3
import shutil
import datetime
import glob
import os

# Auto-detect DB path
db_files = glob.glob('/home/dario/gapfeed/**/gapfeed_unified.db', recursive=True)
db_path = db_files[0] if db_files else '/home/dario/gapfeed/code/data/gapfeed_unified.db'
print(f"Using DB: {db_path}")

# Full backup
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
backup_path = db_path + f'.backup.{timestamp}'
shutil.copy2(db_path, backup_path)
print(f"✅ FULL BACKUP CREATED: {backup_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create product_complaints table (exact same schema)
cursor.execute("CREATE TABLE IF NOT EXISTS product_complaints AS SELECT * FROM signals WHERE 1=0")
print("✅ product_complaints table ready")

# Get schema info
cursor.execute("PRAGMA table_info(signals)")
columns = [info[1] for info in cursor.fetchall()]
print("Signals columns:", columns)

# Detect text column
possible_text_cols = ['text', 'body', 'content', 'selftext', 'post_text', 'description', 'signal']
text_col = next((col for col in possible_text_cols if col in columns), None)
if not text_col:
 print("❌ No text column found. Update script manually.")
 conn.close()
 exit(1)
print(f"Using text column: {text_col}")

# Get known brands from pipeline_products
brands = set()
cursor.execute("PRAGMA table_info(pipeline_products)")
pp_cols = [info[1] for info in cursor.fetchall()]
possible_brand_cols = ['company', 'brand', 'product', 'name', 'title']
brand_col = next((col for col in possible_brand_cols if col in pp_cols), None)

if brand_col:
 cursor.execute(f"SELECT DISTINCT {brand_col} FROM pipeline_products WHERE {brand_col} IS NOT NULL")
 brands = {row[0].lower().strip() for row in cursor.fetchall() if row[0]}
 print(f"✅ Loaded {len(brands)} brands for matching")
else:
 print("⚠️ No brand column in pipeline_products – using keywords only")

# Classification rules
complaint_keywords = ['too ', "doesn't", "don't", "can't", "isn't", 'broken', 'loud', 'slow', 'expensive', 'bad', 'issue', 'problem', 'hate', 'frustrating', 'annoying', 'sucks', 'fails', 'crappy']
gap_keywords = ['wish ', 'need a tool', 'should exist', 'looking for a ', 'saas', 'platform for', 'app for']

moved_count = 0
cursor.execute(f"SELECT id, {text_col} FROM signals")
rows = cursor.fetchall()

for sig_id, text in rows:
    if not text:
        continue
    text_lower = text.lower()
    is_complaint = any(kw in text_lower for kw in complaint_keywords)
    mentions_brand = any(brand in text_lower for brand in brands)
    is_gap = any(kw in text_lower for kw in gap_keywords)
    
    if (is_complaint or mentions_brand) and not is_gap:
        # Move it
        cursor.execute(f"INSERT INTO product_complaints SELECT * FROM signals WHERE id = ?", (sig_id,))
        cursor.execute("DELETE FROM signals WHERE id = ?", (sig_id,))
        moved_count += 1
        if moved_count % 5000 == 0:
            conn.commit()
            print(f" ... moved {moved_count} so far")

conn.commit()
print(f"\n✅ CLEANUP COMPLETE")
print(f"Moved {moved_count} product complaints to product_complaints table")
print(f"Remaining signals (now clean SaaS gaps only): {cursor.execute('SELECT COUNT(*) FROM signals').fetchone()[0]}")
print(f"Product complaints table now has: {cursor.execute('SELECT COUNT(*) FROM product_complaints').fetchone()[0]}")

conn.close()
