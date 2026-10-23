import sqlite3
import json
import os
import subprocess
import time
import config

def understand_signal(signal_text):
    """
    Uses Gemini Flash Lite via OpenClaw to extract structured meaning from a raw pain signal.
    """
    system_prompt = """You are a ruthless, high-precision SaaS data extraction engine. 
Your ONLY job is to read a raw user complaint and extract its core structural DNA so we can cluster it.

CRITICAL INSTRUCTIONS:
1. Respond EXACTLY with a valid JSON object.
2. DO NOT wrap your response in markdown code blocks (e.g. no ```json). Return RAW JSON ONLY.
3. No preambles, no explanations. 

Match this exact JSON schema:
{
  "core_problem": "A sharp, 1-sentence summary of the actual bottleneck or pain.",
  "tools_mentioned": ["Exact names of tools failing them (e.g. 'Stripe', 'Zapier'). Empty array if none."],
  "industry": "The overarching industry, e.g. 'Fintech', 'DevTools', 'E-commerce'.",
  "sentiment_intensity": 9
}"""
    
    full_prompt = f"System: {system_prompt}\n\nSignal:\n\"{signal_text}\""
    
    try:
        env = os.environ.copy()
        env['OPENCLAW_MODEL'] = config.FAST_MODEL
        
        result = subprocess.run(
            ['openclaw', 'agent', '--agent', 'main', '--local', '--thinking', 'off', '--json', '-m', full_prompt],
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )
        
        output = result.stdout.strip()
        try:
            start_idx = output.find('{')
            if start_idx != -1:
                envelope = json.loads(output[start_idx:])
                if 'payloads' in envelope and len(envelope['payloads']) > 0:
                    content = envelope['payloads'][0].get('text', '')
                    content = content.replace("```json", "").replace("```", "").strip()
                    return json.loads(content)
        except Exception as parse_err:
            pass
            
    except Exception as e:
        pass
    return None

def run_understanding_pipeline():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, content FROM signals WHERE status = 'new'")
    signals = c.fetchall()
    
    for s in signals:
        print(f"Processing Signal ID: {s['id']}")
        understanding_json = understand_signal(s['content'])
        
        if understanding_json:
            try:
                json_str = json.dumps(understanding_json)
                c.execute("UPDATE signals SET understanding = ?, status = 'understood' WHERE id = ?", (json_str, s['id']))
                conn.commit()
                print(f"  -> Extracted: {understanding_json.get('core_problem')}")
            except Exception as e:
                print(f"  -> Database update failed: {e}")
        time.sleep(1)
        
    conn.close()

if __name__ == '__main__':
    run_understanding_pipeline()
