#!/usr/bin/env python3
"""
Resume gap enrichment from where it left off
Processes remaining gaps to reach 50 total
"""

import os
import sqlite3
import json
import requests
from datetime import datetime

# Configuration
DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
OPENROUTER_KEY = os.environ.get('OPENROUTER_API_KEY', '')
MODEL = 'anthropic/claude-sonnet-4.6'
API_URL = 'https://openrouter.ai/api/v1/chat/completions'
OUTPUT_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'

# Prompts (same as before, with em dashes banned)
STAGE1_SYSTEM = """You are a sharp, battle-hardened startup founder who has built and sold multiple companies. You explain real painful market gaps to other smart founders over coffee - direct, slightly frustrated, no bullshit, human tone. NEVER use em dashes (—). Use hyphens (-), commas, or periods instead. This is a CRITICAL rule. Ban em dashes in all output. Never sound corporate, generic, or like AI."""

STAGE1_USER = """Gap title so far: {title}

Real user quotes from this gap (these are the only source of truth - use them verbatim when they fit naturally):

{quotes}

Write a high-quality gap page with:

- A sharp, natural title (max 12 words)
- 2-4 sentence description that clearly explains: who is hurting, what they tried, what they currently do instead, and why it sucks
- One clear "Why now" sentence (timing/context)
- 3-6 specific affected personas
- Main failed tools / substitutes mentioned in the quotes
- One strong sentence about the opportunity this creates

Be specific, grounded only in the quotes, and write like a frustrated founder talking to another founder.

CRITICAL: NEVER use em dashes (—). Always use hyphens (-), commas, or periods instead.

Return as JSON:
{{
  "title": "",
  "description": "",
  "why_now": "",
  "affected_personas": [],
  "failed_tools": [],
  "substitutes": [],
  "opportunity": ""
}}"""

STAGE2_SYSTEM = """You are an extremely harsh, precise, and ruthless editor. Your only job is to destroy anything that sounds like generic AI writing, corporate fluff, vagueness, or weak storytelling. Be brutal and specific. Check for and flag em dashes (—) as AI tells. Ban them from all output."""

STAGE2_USER = """Critique this draft very harshly. Point out every single problem:

- Generic AI language or corporate tone
- Vague or weak statements
- Sentences that don't sound like a real founder
- Irrelevant or weak quotes
- Anything boring or generic
- EM DASHES (—) - these are banned, flag any you find

Draft to critique:
{draft}

Return ONLY valid JSON:
{{
  "critique": "",
  "generic_ai_terms": [],
  "vague_statements": [],
  "weak_storytelling": [],
  "em_dashes_found": [],
  "improvements_needed": []
}}"""

STAGE3_SYSTEM = """You are a sharp, experienced startup founder. Rewrite the content to be direct, human, high-impact, and slightly angry about broken things. Remove every trace of AI or corporate speak. CRITICAL: NEVER use em dashes (—). Always use hyphens (-), commas, or periods instead. This is a hard rule that cannot be broken."""

STAGE3_USER = """Rewrite the following draft using the critique. Make it sharp, natural, founder-to-founder tone. Use the real quotes naturally where they strengthen the story. Make it feel like a real person wrote it. CRITICAL: Never use em dashes (—). Use hyphens (-), commas, or periods instead.

Original draft:
{draft}

Critique:
{critique}

Return as JSON:
{{
  "title": "",
  "description": "",
  "why_now": "",
  "affected_personas": [],
  "failed_tools": [],
  "substitutes": [],
  "opportunity": ""
}}"""

def extract_json_from_content(content: str):
    """Extract JSON from Claude's response."""
    if '```json' in content:
        parts = content.split('```json')
        if len(parts) > 1:
            content = parts[1].split('```')[0]
    elif '```' in content:
        content = content.split('```')[-2] if len(content.split('```')) > 2 else content.split('```')[1]
    
    start = content.find('{')
    end = content.rfind('}') + 1
    
    if start >= 0 and end > start:
        json_str = content[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            return {'_error': f'JSON decode error: {str(e)}', 'raw': json_str[:200]}
    
    return {'_error': 'No JSON found in response', 'raw': content[:200]}

def call_llm(system_prompt, user_prompt, max_tokens=1000, temperature=0.7):
    """Call OpenRouter API."""
    headers = {'Authorization': f'Bearer {OPENROUTER_KEY}', 'Content-Type': 'application/json'}
    payload = {
        'model': MODEL,
        'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
        'max_tokens': max_tokens, 'temperature': temperature, 'response_format': {'type': 'json_object'}
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            return extract_json_from_content(content)
        return {'_error': 'No response from LLM'}
    except Exception as e:
        return {'_error': str(e)}

def clean_em_dashes(text: str) -> str:
    """Remove em dashes from text."""
    if not text:
        return text
    return text.replace('—', '-').replace(' – ', ' - ')

def get_gap_with_signals(gap_id: int):
    """Get gap and signals."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gaps WHERE id = ? AND status = 'active'", (gap_id,))
    gap = cursor.fetchone()
    
    if not gap:
        conn.close()
        return None
    
    gap_dict = dict(gap)
    signal_ids = json.loads(gap_dict.get('signal_ids', '[]'))
    
    if signal_ids:
        placeholders = ','.join('?' * min(len(signal_ids), 15))
        cursor.execute(f"SELECT content, source, author FROM signals WHERE id IN ({placeholders}) LIMIT 15", signal_ids[:15])
    else:
        cursor.execute("SELECT content, source, author FROM signals WHERE gap_id = ? LIMIT 15", (gap_id,))
    
    signals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    gap_dict['signals'] = signals
    return gap_dict

def enrich_gap(gap_id: int, gap_num: int, total: int):
    """Enrich a single gap."""
    print(f"\n{'='*60}")
    print(f"Processing Gap #{gap_id} ({gap_num}/{total})")
    print(f"{'='*60}")
    
    gap_data = get_gap_with_signals(gap_id)
    if not gap_data:
        return None
    
    quotes = []
    for sig in gap_data.get('signals', []):
        content = sig.get('content', '')
        if content and len(content) > 20:
            quotes.append(f"- \"{content[:150]}...\" ({sig.get('source', 'unknown')})")
    
    if not quotes:
        return None
    
    print(f"Found {len(quotes)} quotes")
    
    # Stage 1: Draft
    print("📝 STAGE 1: Draft...")
    draft_prompt = STAGE1_USER.format(title=gap_data.get('title', 'Untitled'), quotes='\n'.join(quotes))
    draft = call_llm(STAGE1_SYSTEM, draft_prompt, max_tokens=1500, temperature=0.7)
    
    if '_error' in draft:
        print(f"  ❌ Draft failed: {draft['_error']}")
        return None
    
    draft = {k: clean_em_dashes(v) if isinstance(v, str) else v for k, v in draft.items()}
    print(f"  ✅ Title: {draft.get('title', 'N/A')[:50]}...")
    
    # Stage 2: Critique
    print("🔍 STAGE 2: Critique...")
    critique_prompt = STAGE2_USER.format(draft=json.dumps(draft, indent=2))
    critique = call_llm(STAGE2_SYSTEM, critique_prompt, max_tokens=1000, temperature=0.3)
    
    polished = draft
    if '_error' not in critique:
        print("  ✅ Critique complete")
        
        # Stage 3: Polish
        print("✨ STAGE 3: Polish...")
        polish_prompt = STAGE3_USER.format(draft=json.dumps(draft, indent=2), critique=json.dumps(critique, indent=2))
        polished = call_llm(STAGE3_SYSTEM, polish_prompt, max_tokens=1500, temperature=0.5)
        
        if '_error' not in polished:
            polished = {k: clean_em_dashes(v) if isinstance(v, str) else v for k, v in polished.items()}
            print(f"  ✅ Complete")
        else:
            print(f"  ⚠️  Polish failed, using draft")
    else:
        print(f"  ⚠️  Critique failed, using draft")
    
    # Merge
    enriched_gap = {**gap_data, **polished}
    del enriched_gap['signals']
    if 'signal_ids' in enriched_gap:
        enriched_gap['signal_ids'] = gap_data.get('signal_ids', '[]')
    
    # Display summary
    print(f"\n✅ Gap #{gap_id}: {enriched_gap.get('title', 'N/A')[:60]}...")
    
    return enriched_gap

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all active gaps sorted by heat score
    cursor.execute("SELECT id FROM gaps WHERE status = 'active' ORDER BY heat_score DESC")
    all_gaps = [row[0] for row in cursor.fetchall()]
    
    # Get gaps already processed (from the previous run)
    with open(OUTPUT_PATH, 'r') as f:
        existing_data = json.load(f)
    
    processed_ids = {gap['id'] for gap in existing_data['gaps']}
    print(f"Already processed: {len(processed_ids)} gaps")
    
    # Get remaining gaps to reach 50 total
    remaining_gaps = [gid for gid in all_gaps if gid not in processed_ids]
    gaps_to_process = remaining_gaps[:50 - len(processed_ids)]
    
    print(f"Remaining to process: {len(remaining_gaps)} gaps")
    print(f"Processing next {len(gaps_to_process)} gaps to reach 50 total\n")
    
    new_gaps = []
    for i, gap_id in enumerate(gaps_to_process, 1):
        result = enrich_gap(gap_id, len(processed_ids) + i, 50)
        if result:
            new_gaps.append(result)
    
    # Merge with existing gaps
    final_gaps = existing_data['gaps'] + new_gaps
    
    # Save updated data
    cursor.execute("SELECT COUNT(*) FROM signals")
    total_signals = cursor.fetchone()[0]
    
    final_data = {
        'gaps': final_gaps,
        'stats': {'signals': total_signals, 'gaps': len(final_gaps)},
        'total_signals_all': total_signals,
        'total_gaps': len(final_gaps),
        'exported_at': datetime.now().isoformat(),
        'enrichment_model': MODEL,
        'enrichment_method': '3-layer-claude-sonnet',
        'em_dashes_banned': True
    }
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(final_data, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Total gaps processed: {len(final_gaps)}")
    print(f"New gaps enriched: {len(new_gaps)}")
    print(f"Total signals: {total_signals:,}")
    print(f"Estimated cost: ${len(new_gaps) * 0.025:.2f}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"{'='*60}")
    
    # Show 3 example gaps (one best, one average, one from new batch)
    print(f"\nEXAMPLE GAPS:")
    
    # Best gap (highest heat score)
    best = sorted(final_gaps, key=lambda x: x.get('heat_score', 0), reverse=True)[0]
    print(f"\n1. BEST (Heat: {best.get('heat_score', 'N/A')}):")
    print(f"   {best.get('title', 'N/A')}")
    
    # Average gap (middle heat score)
    avg = sorted(final_gaps, key=lambda x: x.get('heat_score', 0))[len(final_gaps)//2]
    print(f"\n2. AVERAGE (Heat: {avg.get('heat_score', 'N/A')}):")
    print(f"   {avg.get('title', 'N/A')}")
    
    # One from new batch
    if new_gaps:
        new_ex = new_gaps[0]
        print(f"\n3. FROM NEW BATCH (Heat: {new_ex.get('heat_score', 'N/A')}):")
        print(f"   {new_ex.get('title', 'N/A')}")
    
    print(f"\n{'='*60}")

if __name__ == '__main__':
    main()
