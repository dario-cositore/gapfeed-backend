"""
Gap Description LLM Benchmark

Tests 5 candidate models on the same cluster data.
Outputs side-by-side comparison of quality and cost.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engines.gap_llm import gap_llm_json, estimate_cost, MODEL_PRICING
from src.engines.gap_detector import sanitize_text, GAP_SYSTEM_PROMPT
from src.engines.cluster_context_builder import build_cluster_context, format_context_for_llm
from shared.remote_db import RemoteDB

MODELS = [
    "z-ai/glm-5",
    "minimax/minimax-m2.7",
    "openai/gpt-5.4-mini",
    "moonshotai/kimi-k2.5",
    "google/gemini-3-flash-preview",
]

# Also test current baseline
BASELINES = [
    "xiaomi/mimo-v2-flash",
    "deepseek/deepseek-v3.2",
]


def get_test_cluster():
    """Fetch a real signal cluster for benchmarking."""
    db = RemoteDB()
    signals = db.get_signals(quality_tier='gold', limit=100)
    
    # Find the biggest cluster
    from collections import defaultdict
    clusters = defaultdict(list)
    for s in signals:
        cat = s.get('pain_category', '')
        if cat and cat != 'uncategorized':
            clusters[cat].append(s)
    
    # Pick the biggest cluster with 10+ signals
    best_cat = None
    best_count = 0
    for cat, sigs in clusters.items():
        if len(sigs) > best_count:
            best_count = len(sigs)
            best_cat = cat
    
    if not best_cat:
        print("ERROR: No clusters found")
        return None, None, None
    
    cluster_signals = clusters[best_cat][:20]
    context = build_cluster_context(best_cat, cluster_signals)
    evidence_block = format_context_for_llm(context)
    
    # Build a small signal sample
    signal_blocks = []
    for i, s in enumerate(cluster_signals[:8]):
        title = (s.get('title') or '')[:80]
        content = (s.get('content') or '')[:150]
        source = s.get('subreddit') or s.get('source', '')
        urgency = s.get('urgency_score', 0)
        signal_blocks.append(f"{i+1}. [{source}, u={urgency}] {title}: {content}")
    signals_text = '\n'.join(signal_blocks)
    
    prompt = f"""Analyze this market gap based on {len(cluster_signals)} user pain signals.

{evidence_block}

--- RAW SIGNAL SAMPLE (supplementary) ---
{signals_text}
--- END ---

Based on the evidence above, generate the gap JSON object.
IMPORTANT: Only name competitors/substitutes that appear in the evidence. Do not invent tool names.
If no named competitors exist, frame the gap around the substitutes people use instead."""
    
    return best_cat, prompt, context


def run_benchmark():
    """Run all models on the same prompt and collect results."""
    print("=" * 80)
    print("GAP DESCRIPTION LLM BENCHMARK")
    print("=" * 80)
    
    # Get test data
    category, prompt, context = get_test_cluster()
    if not category:
        return
    
    print(f"\nTest cluster: {category}")
    print(f"Signals: {context['signal_count']}")
    print(f"Competitors: {[c['name'] for c in context.get('competitors', [])[:5]]}")
    print(f"Substitutes: {[s['name'] for s in context.get('substitutes', [])[:3]]}")
    print(f"Confidence: {context['confidence']}")
    print()
    
    all_models = MODELS + BASELINES
    results = []
    
    for model in all_models:
        print(f"Testing {model}...", end=" ", flush=True)
        
        result = gap_llm_json(
            prompt=prompt,
            system_prompt=GAP_SYSTEM_PROMPT,
            model=model,
            max_tokens=2000,
            temperature=0.3,
            timeout=45,
        )
        
        meta = result.get("_meta", {})
        error = result.get("_error")
        
        # Extract gap fields
        title = result.get("title", "")
        description = result.get("description", "")
        failed_tools = result.get("failed_tools", [])
        substitutes = result.get("substitutes", [])
        why_now = result.get("why_now", "")
        heat = result.get("heat_score", "?")
        
        # Sanitize
        title_clean = sanitize_text(title)
        desc_clean = sanitize_text(description)
        
        # Count AI tells
        ai_tells = 0
        for text in [title, description]:
            ai_tells += text.count('\u2014') + text.count('\u2013')  # em/en dashes
            ai_tells += text.count('mobile-first') + text.count('end-to-end')
            ai_tells += text.count('data-driven') + text.count('pre-written')
            ai_tells += text.count('streamline') + text.count('leverage')
            ai_tells += text.count('empower') + text.count('co-pilot')
        
        # Calculate cost
        tokens_in = meta.get("tokens_in", 0)
        tokens_out = meta.get("tokens_out", 0)
        cost = estimate_cost(model, tokens_in, tokens_out)
        elapsed = meta.get("elapsed", 0)
        
        entry = {
            "model": model,
            "error": error,
            "title": title_clean,
            "description": desc_clean,
            "failed_tools": failed_tools,
            "substitutes": substitutes,
            "why_now": why_now,
            "heat_score": heat,
            "ai_tells": ai_tells,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": cost,
            "elapsed": elapsed,
        }
        results.append(entry)
        
        if error:
            print(f"ERROR: {error}")
        else:
            print(f"OK ({elapsed}s, ${cost:.5f})")
        
        time.sleep(1)  # Be nice to the API
    
    # Print comparison table
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)
    
    # Header
    print(f"\n{'Model':<35} {'Time':>6} {'Tokens':>10} {'Cost':>8} {'AI Tells':>9} {'Status':<10}")
    print("-" * 85)
    
    for r in results:
        model_short = r["model"].split("/")[-1]
        status = "ERROR" if r["error"] else "OK"
        tokens = f"{r['tokens_in']}+{r['tokens_out']}"
        print(f"{model_short:<35} {r['elapsed']:>5.1f}s {tokens:>10} ${r['cost']:>6.5f} {r['ai_tells']:>8} {status:<10}")
    
    # Show descriptions side by side
    print("\n" + "=" * 80)
    print("DESCRIPTIONS (sanitized)")
    print("=" * 80)
    
    for r in results:
        if r["error"]:
            continue
        print(f"\n--- {r['model']} ---")
        print(f"Title: {r['title']}")
        print(f"Description: {r['description'][:300]}")
        print(f"Competitors: {r['failed_tools']}")
        print(f"Substitutes: {r['substitutes']}")
        if r['why_now']:
            print(f"Why now: {r['why_now'][:100]}")
    
    # Save full results
    output_path = Path(__file__).parent.parent / "data" / "benchmark_results.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nFull results saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    run_benchmark()
