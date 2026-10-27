#!/usr/bin/env python3
"""
Enrich gaps with Xiaomi Mimo (token plan) via the OpenAI-compatible endpoint.
3-Layer Process: Draft → Critique → Polish

CRITICAL: All prompts ban em dashes (—) - never use them.
"""

import os
import sqlite3
import json
import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Any

# ══════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/gapfeed/data/signals.db'
# Use the Mimo TOKEN PLAN (fixed subscription) endpoint, not the pay-as-you-go API key.
# Set MIMO_API_KEY to your tp-/ttp- token plan key and MIMO_OPENAI_BASE_URL to the
# regional token-plan host (e.g. https://token-plan-ams.xiaomimimo.com/v1).
MIMO_API_KEY = os.environ.get('MIMO_API_KEY', '') or os.environ.get('OPENROUTER_API_KEY', '')
MIMO_BASE_URL = os.environ.get('MIMO_OPENAI_BASE_URL', 'https://token-plan-ams.xiaomimimo.com/v1').rstrip('/')
DEFAULT_MODEL = os.environ.get('MIMO_MODEL', 'mimo-v2.6-flash')
API_URL = f'{MIMO_BASE_URL}/chat/completions'

OUTPUT_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'

MODEL = DEFAULT_MODEL

# ══════════════════════════════════════════════════════════
# PROMPTS (ALL BAN EM DASHES)
# ══════════════════════════════════════════════════════════

STAGE1_SYSTEM = """You are a sharp, battle-hardened startup founder who has built and sold multiple companies. You explain real painful market gaps to other smart founders over coffee - direct, slightly frustrated, no bullshit, human tone.

NEVER use em dashes (—). Use hyphens (-), commas, or periods instead. This is a CRITICAL rule. Ban em dashes in all output.

Never sound corporate, generic, or like AI. Avoid words like leverage, streamline, unlock, ecosystem, paradigm, etc."""

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

STAGE2_SYSTEM = """You are an extremely harsh, precise, and ruthless editor. Your only job is to destroy anything that sounds like generic AI writing, corporate fluff, vagueness, or weak storytelling. Be brutal and specific.

Check for and flag em dashes (—) as AI tells. Ban them from all output."""

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

STAGE3_SYSTEM = """You are a sharp, experienced startup founder. Rewrite the content to be direct, human, high-impact, and slightly angry about broken things. Remove every trace of AI or corporate speak.

CRITICAL: NEVER use em dashes (—). Always use hyphens (-), commas, or periods instead. This is a hard rule that cannot be broken."""

STAGE3_USER = """Rewrite the following draft using the critique. Make it sharp, natural, founder-to-founder tone. Use the real quotes naturally where they strengthen the story. Make it feel like a real person wrote it.

CRITICAL: Never use em dashes (—). Use hyphens (-), commas, or periods instead. Check your work.

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

# ══════════════════════════════════════════════════════════
# LLM CLIENT
# ══════════════════════════════════════════════════════════

def extract_json_from_content(content: str) -> Dict[str, Any]:
    """Extract JSON from Claude's response."""
    # Remove markdown code blocks
    if '```json' in content:
        parts = content.split('```json')
        if len(parts) > 1:
            content = parts[1].split('```')[0]
    elif '```' in content:
        content = content.split('```')[-2] if len(content.split('```')) > 2 else content.split('```')[1]
    
    # Find JSON start and end
    start = content.find('{')
    end = content.rfind('}') + 1
    
    if start >= 0 and end > start:
        json_str = content[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            return {'_error': f'JSON decode error: {str(e)}', 'raw': json_str[:200]}
    
    return {'_error': 'No JSON found in response', 'raw': content[:200]}

def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> Dict[str, Any]:
    """Call the Mimo TOKEN PLAN endpoint (OpenAI-compatible)."""
    if not MIMO_API_KEY:
        return {'_error': 'No MIMO_API_KEY set (token plan key).'}
    headers = {
        'Authorization': f'Bearer {MIMO_API_KEY}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            return extract_json_from_content(content)
        else:
            return {'_error': 'No response from LLM'}
            
    except Exception as e:
        return {'_error': str(e)}

# ══════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_gap_with_signals(gap_id: int) -> Dict[str, Any]:
    """Get gap and its linked signals from database."""
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

def get_all_active_gaps() -> List[Dict[str, Any]]:
    """Get all active gaps from database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, slug, category, heat_score, evidence_count FROM gaps WHERE status = 'active' ORDER BY heat_score DESC")
    
    gaps = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return gaps

# ══════════════════════════════════════════════════════════
# ENRICHMENT PROCESS
# ══════════════════════════════════════════════════════════

def clean_em_dashes(text: str) -> str:
    """Remove em dashes from text."""
    if not text:
        return text
    return text.replace('—', '-').replace(' – ', ' - ')

def enrich_gap(gap_id: int) -> Dict[str, Any]:
    """Enrich a single gap using 3-layer LLM process."""
    print(f"\n{'='*60}")
    print(f"Processing Gap #{gap_id}")
    print(f"{'='*60}")
    
    gap_data = get_gap_with_signals(gap_id)
    if not gap_data:
        return {'error': 'Gap not found'}
    
    quotes = []
    for sig in gap_data.get('signals', []):
        content = sig.get('content', '')
        if content and len(content) > 20:
            quotes.append(f"- \"{content[:150]}...\" ({sig.get('source', 'unknown')})")
    
    if not quotes:
        return {'error': 'No quotes found for this gap'}
    
    print(f"Found {len(quotes)} quotes from signals")
    
    # Stage 1: Draft
    print("\n📝 STAGE 1: Draft (Claude Sonnet)")
    draft_prompt = STAGE1_USER.format(
        title=gap_data.get('title', 'Untitled'),
        quotes='\n'.join(quotes)
    )
    
    draft = call_llm(STAGE1_SYSTEM, draft_prompt, max_tokens=1500, temperature=0.7)
    if '_error' in draft:
        print(f"  ❌ Draft failed: {draft['_error']}")
        return {'error': f'Draft failed: {draft["_error"]}'}
    
    # Clean em dashes from draft
    draft = {k: clean_em_dashes(v) if isinstance(v, str) else v for k, v in draft.items()}
    
    print(f"  ✅ Draft complete")
    print(f"  Title: {draft.get('title', 'N/A')[:60]}...")
    
    # Stage 2: Critique
    print("\n🔍 STAGE 2: Critique (Claude Sonnet)")
    critique_prompt = STAGE2_USER.format(draft=json.dumps(draft, indent=2))
    
    critique = call_llm(STAGE2_SYSTEM, critique_prompt, max_tokens=1000, temperature=0.3)
    if '_error' in critique:
        print(f"  ⚠️  Critique failed: {critique['_error']}")
        print(f"  Continuing with draft only...")
        polished = draft
    else:
        print(f"  ✅ Critique complete")
        if critique.get('em_dashes_found'):
            print(f"  Em dashes found: {len(critique['em_dashes_found'])}")
        
        # Stage 3: Polish
        print("\n✨ STAGE 3: Polish (Claude Sonnet)")
        polish_prompt = STAGE3_USER.format(
            draft=json.dumps(draft, indent=2),
            critique=json.dumps(critique, indent=2)
        )
        
        polished = call_llm(STAGE3_SYSTEM, polish_prompt, max_tokens=1500, temperature=0.5)
        if '_error' in polished:
            print(f"  ⚠️  Polish failed: {polished['_error']}")
            print(f"  Using draft as fallback...")
            polished = draft
        else:
            # Clean em dashes from final polish
            polished = {k: clean_em_dashes(v) if isinstance(v, str) else v for k, v in polished.items()}
            print(f"  ✅ Polish complete")
    
    # Display final output
    print(f"\n{'='*60}")
    print(f"FINAL ENRICHED GAP #{gap_id}")
    print(f"{'='*60}")
    print(f"\nTITLE: {polished.get('title', 'N/A')}")
    print(f"\nDESCRIPTION:")
    print(f"{polished.get('description', 'N/A')}")
    print(f"\nWHY NOW:")
    print(f"{polished.get('why_now', 'N/A')}")
    print(f"\nAFFECTED PERSONAS:")
    for persona in polished.get('affected_personas', []):
        print(f"  - {persona}")
    print(f"\nFAILED TOOLS:")
    for tool in polished.get('failed_tools', []):
        print(f"  - {tool}")
    print(f"\nSUBSTITUTES:")
    for sub in polished.get('substitutes', []):
        print(f"  - {sub}")
    print(f"\nOPPORTUNITY:")
    print(f"{polished.get('opportunity', 'N/A')}")
    print(f"\nCATEGORY: {polished.get('category', gap_data.get('category', 'N/A'))}")
    print(f"HEAT SCORE: {polished.get('heat_score', gap_data.get('heat_score', 'N/A'))}")
    print(f"{'='*60}")
    
    # Merge enriched data back
    enriched_gap = {**gap_data, **polished}
    del enriched_gap['signals']
    if 'signal_ids' in enriched_gap:
        enriched_gap['signal_ids'] = gap_data.get('signal_ids', '[]')
    
    return enriched_gap

def save_to_astro(gaps: List[Dict[str, Any]]):
    """Save enriched gaps to Astro data.json format."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM signals")
    total_signals = cursor.fetchone()[0]
    conn.close()
    
    # Double-check for any remaining em dashes
    for gap in gaps:
        for key in ['title', 'description', 'why_now', 'opportunity']:
            if key in gap and isinstance(gap[key], str):
                gap[key] = clean_em_dashes(gap[key])
    
    data = {
        'gaps': gaps,
        'stats': {'signals': total_signals, 'gaps': len(gaps)},
        'total_signals_all': total_signals,
        'total_gaps': len(gaps),
        'exported_at': datetime.now().isoformat(),
        'enrichment_model': MODEL,
        'enrichment_method': '3-layer-claude-sonnet',
        'em_dashes_banned': True
    }
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\n✅ Saved {len(gaps)} enriched gaps to {OUTPUT_PATH}")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich gaps with Claude Sonnet')
    parser.add_argument('--test', action='store_true', help='Test on 1 gap only')
    parser.add_argument('--gap-id', type=int, help='Enrich a specific gap by ID')
    parser.add_argument('--limit', type=int, default=50, help='Max gaps to process')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL, help=f'Model to use (default: {DEFAULT_MODEL})')
    
    args = parser.parse_args()
    
    global MODEL
    MODEL = args.model
    
    print(f"{'='*60}")
    print(f"GAP ENRICHMENT SCRIPT")
    print(f"{'='*60}")
    print(f"Database: {DB_PATH}")
    print(f"Model: {MODEL}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"EM DASHES BANNED: YES")
    print(f"{'='*60}\n")
    
    if args.test:
        print("🧪 TEST MODE: Processing 1 gap only\n")
        if args.gap_id:
            gaps_to_process = [{'id': args.gap_id}]
        else:
            gaps_to_process = get_all_active_gaps()[:1]
    elif args.gap_id:
        print(f"🎯 SPECIFIC GAP: Processing gap #{args.gap_id}\n")
        gaps_to_process = [{'id': args.gap_id}]
    else:
        all_gaps = get_all_active_gaps()
        print(f"📊 FULL MODE: Found {len(all_gaps)} active gaps")
        print(f"   Processing up to {args.limit} gaps\n")
        gaps_to_process = all_gaps[:args.limit]
    
    enriched_gaps = []
    errors = []
    
    for gap in gaps_to_process:
        try:
            result = enrich_gap(gap['id'])
            if 'error' in result:
                errors.append(f"Gap #{gap['id']}: {result['error']}")
            else:
                enriched_gaps.append(result)
        except Exception as e:
            errors.append(f"Gap #{gap['id']}: {str(e)}")
    
    if enriched_gaps:
        save_to_astro(enriched_gaps)
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Enriched: {len(enriched_gaps)} gaps")
    print(f"Errors: {len(errors)} gaps")
    
    if errors:
        print(f"\nErrors:")
        for err in errors[:5]:
            print(f"  - {err}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")
    
    print(f"\n{'='*60}")
    print(f"READY: {OUTPUT_PATH}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
