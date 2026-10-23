import sqlite3
import json
import os
import subprocess
import config

DB_PATH = config.DB_PATH

def synthesize_gap(topic="Stripe"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Grab un-synthesized signals
    c.execute("SELECT id, source_url, author, content FROM signals WHERE status = 'new' AND (content LIKE ? OR title LIKE ?) LIMIT 5", (f'%{topic}%', f'%{topic}%'))
    signals = c.fetchall()
    
    if not signals:
        print(f"No new signals found for topic: {topic}")
        return
        
    signal_ids = [s['id'] for s in signals]
    signal_text = "\n\n".join([f"Signal {i+1} (u/{s['author']}): {s['content']}" for i, s in enumerate(signals)])
    
    prompt = f"""You are an expert SaaS analyst creating a 'Pristine Gap Briefing' for founders based on the following raw signals complaining about a specific business pain point:

{signal_text}

Extract the core problem and format your response STRICTLY as a JSON object matching this exact schema:
{{
  "title": "A short, high-impact headline describing the problem",
  "slug": "url-friendly-version-of-title",
  "category": "The industry tag (e.g. devtools, fintech, e-commerce)",
  "heat_score": 0.85, 
  "the_opportunity": "Exactly what to build right now to solve this pain. Be direct.",
  "the_gap": "The actual missing piece in the market.",
  "description": "High-level summary of the pain.",
  "why_now": "The specific catalyst making this urgent today.",
  "monetization_models": "Suggested ways to charge for this solution.",
  "tam_estimate": "Qualitative size of the opportunity.",
  "who_is_affected": "The specific target audience.",
  "substitutes": "Organic workarounds currently being used.",
  "failed_tools": "Tools failing hard at this specific nuance.",
  "existing_solutions": "Competitors proactively trying to solve this.",
  "sample_quotes": [
    {{"text": "quote 1", "author": "author 1", "source_url": "url 1"}}
  ]
}}

Ensure valid JSON, do not include markdown blocks, just the raw JSON object."""

    try:
        env = os.environ.copy()
        env['OPENCLAW_MODEL'] = config.REASONING_MODEL # Heavy lifter
        
        result = subprocess.run(
            ['openclaw', 'agent', '--agent', 'main', '--local', '--json', '-m', prompt],
            capture_output=True,
            text=True,
            env=env,
            timeout=180
        )
        
        output = result.stdout.strip()
        gap_data = None # Initialize
        try:
            # Find the start of the JSON envelope
            start_idx = output.find('{')
            if start_idx != -1:
                json_str = output[start_idx:]
                envelope = json.loads(json_str)
                if 'payloads' in envelope and len(envelope['payloads']) > 0:
                    content = envelope['payloads'][0].get('text', '')
                    # Clean markdown from the actual content
                    content = content.replace("```json", "").replace("```", "").strip()
                    gap_data = json.loads(content)
        except Exception as parse_err:
            print(f"      [Parsing Error]: Failed to parse model output. Details: {parse_err}")
            # gap_data will be None, causing the script to report a synthesis error, which is correct.

        gap_data['signal_ids'] = json.dumps(signal_ids)
        
        # Insert the gap
        cols = ', '.join(gap_data.keys())
        placeholders = ', '.join(':' + k for k in gap_data.keys())
        c.execute(f"INSERT INTO gaps ({cols}) VALUES ({placeholders})", gap_data)
        
        # Mark signals as synthesized
        c.execute(f"UPDATE signals SET status = 'synthesized' WHERE id IN ({','.join('?' * len(signal_ids))})", signal_ids)
        
        conn.commit()
        print(f"SUCCESS: Synthesized new gap '{gap_data['title']}' from {len(signals)} signals.")
        print(json.dumps(gap_data, indent=2))
        
    except Exception as e:
        print(f"Error during synthesis: {e}")
        print(f"Model output: {result.stdout if 'result' in locals() else 'None'}")
    finally:
        conn.close()

if __name__ == '__main__':
    synthesize_gap()
