#!/usr/bin/env python3
"""
Model comparison test for Luna Hart LLM tasks.
Tests each model on each content type using real TuXo data.
"""
import sys
import json
import time
from pathlib import Path

# Add shared to path (tuxo root)
tuxo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(tuxo_root))
from shared.llm_client import llm_call

# Real TuXo data
TUXO_STATS = {"signals": 6739, "gaps": 53}

MODELS = [
    "mimo-v2.6-flash",
    "google/gemini-2.5-flash-lite-preview-09-2025",
    "deepseek/deepseek-v3.2",
]

# ============================================================
# TASK 1: plan_content() - Strategic reasoning
# ============================================================
def test_plan_content():
    prompt = f"""
    You are Luna Hart, the marketing AI for TuXo (a gap discovery platform).
    
    Current TuXo stats:
    - Signals collected: {TUXO_STATS['signals']}
    - Market gaps identified: {TUXO_STATS['gaps']}
    
    Recent trends: "AI agents are replacing SaaS tools", "Indie hackers want real-time market intel"
    
    Last content created: X post about signal classification 2 days ago.
    
    Decide the NEXT piece of content to create. Consider:
    - What would get engagement right now?
    - What showcases TuXo's value?
    - What hasn't been covered recently?
    
    Return ONLY a JSON object with this structure:
    {{"type": "x_post", "topic": "...", "style": "insight", "reason": "brief why"}}
    
    Types: x_post, x_thread, linkedin_post, blog_post
    Styles: insight, stat, gap, engagement, trend_take
    """
    return prompt

# ============================================================
# TASK 2: generate_x_post() - Short creative writing
# ============================================================
def test_x_post():
    prompt = f"""
    Generate a single X post (under 280 characters).
    
    Topic: "TuXo found 53 unsolved market problems this week by scanning 7 internet sources"
    
    Requirements:
    1. Start with a clear statement of the topic
    2. End with an engagement question
    3. Professional, energetic tone
    4. Under 280 characters total
    5. NO em dashes (use commas, periods, or hyphens only)
    """
    return prompt

# ============================================================
# TASK 3: generate_x_thread() - Narrative flow
# ============================================================
def test_x_thread():
    prompt = f"""
    Generate an X thread of exactly 3 tweets about: "How TuXo scans the internet to find unsolved problems"
    
    Structure:
    - Tweet 1: Strong hook about why guessing what to build is broken
    - Tweet 2: How TuXo works (7 sources, {TUXO_STATS['signals']} signals, LLM classification)
    - Tweet 3: What this means for builders, end with engagement question
    
    Each tweet must be under 280 characters. NO em dashes. Output as newline-separated list.
    """
    return prompt

# ============================================================
# TASK 4: generate_linkedin_post() - Longer creative writing
# ============================================================
def test_linkedin():
    prompt = f"""
    Generate a professional LinkedIn post (500-800 characters) about: "Why I stopped guessing what to build and built TuXo instead"
    
    Context:
    - TuXo scans 7 internet sources 24/7
    - Found {TUXO_STATS['signals']} signals and {TUXO_STATS['gaps']} market gaps in a week
    - This is a story about frustration leading to automation
    
    Requirements:
    1. Professional, reflective tone for B2B audience
    2. End with an open-ended engagement question
    3. NO em dashes (use commas, periods, or hyphens)
    4. Use line breaks for readability
    """
    return prompt

# ============================================================
# TASK 5: generate_blog_post() - Structured JSON output
# ============================================================
def test_blog():
    prompt = f"""
    Create a blog post outline for: "The problem with building SaaS in 2026"
    
    Context:
    - Gap focus: "Too many tools, not enough validated problems"
    - Based on {TUXO_STATS['signals']} signals across Reddit, HN, Stack Overflow, Dev.to
    - Found {TUXO_STATS['gaps']} unsolved market gaps
    
    Return ONLY a JSON object:
    {{
      "title": "SEO-friendly H1 title",
      "meta_description": "Under 160 chars",
      "sections": [
        {{"heading": "H2 title", "points": ["point 1", "point 2"]}}
      ]
    }}
    
    NO em dashes anywhere. If you cannot output valid JSON, return "JSON_FORMAT_ERROR".
    """
    return prompt


TASKS = [
    ("plan_content (reasoning)", test_plan_content, 800),
    ("generate_x_post (creative)", test_x_post, 300),
    ("generate_x_thread (narrative)", test_x_thread, 1200),
    ("generate_linkedin (long creative)", test_linkedin, 1500),
    ("generate_blog (structured JSON)", test_blog, 1500),
]


def main():
    print("=" * 70)
    print("LUNA HART - MODEL COMPARISON TEST")
    print(f"Data: {TUXO_STATS['signals']} signals, {TUXO_STATS['gaps']} gaps")
    print("=" * 70)
    
    for task_name, task_fn, max_tokens in TASKS:
        print(f"\n{'=' * 70}")
        print(f"TASK: {task_name}")
        print(f"{'=' * 70}")
        
        prompt = task_fn()
        
        for model in MODELS:
            print(f"\n--- Model: {model} ---")
            start = time.time()
            
            try:
                result = llm_call(
                    prompt=prompt,
                    system_prompt="You are Luna Hart, a marketing AI. Be direct, creative, and concise. NEVER use em dashes.",
                    model=model,
                    max_tokens=max_tokens,
                    temperature=0.7,
                    timeout=30
                )
                elapsed = time.time() - start
                
                if result:
                    print(f"Time: {elapsed:.1f}s")
                    print(f"Output ({len(result)} chars):")
                    print(result[:800])
                    if len(result) > 800:
                        print(f"... ({len(result) - 800} more chars)")
                else:
                    print(f"Time: {elapsed:.1f}s - FAILED (empty response)")
                    
            except Exception as e:
                elapsed = time.time() - start
                print(f"Time: {elapsed:.1f}s - ERROR: {e}")
            
            print()


if __name__ == "__main__":
    main()
