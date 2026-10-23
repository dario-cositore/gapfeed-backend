"""
Summarizer — LLM-based summary generation.
"""
import sys
from pathlib import Path

# Add project root for shared module access
# Path: .../tuxo/TheRealAgents/Jamie Rivera/app/synthesizer/summarizer.py
# 5 levels up: tuxo
JAMIE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(JAMIE_ROOT))

from shared.llm_client import llm_call
from app.models.signal import Signal


def generate_summary(
    query: str,
    signals: List[Signal],
    pain_groups: dict,
    max_tokens: int = 800,
    temperature: float = 0.1,
) -> str:
    """
    Generate a natural language summary using LLM.
    """
    # Build signal summary
    total = len(signals)
    top_categories = sorted(pain_groups.items(), key=lambda x: len(x[1]['signals']), reverse=True)[:5]
    
    prompt = f"""Summarize the following signal data for the query "{query}":

TOTAL SIGNALS: {total}

TOP PAIN CATEGORIES:
{chr(10).join(f"- {cat}: {len(info['signals'])} signals" for cat, info in top_categories)}

INSTRUCTIONS:
- Write a 2-3 sentence summary of the main themes and pain points
- Focus on urgency and what users are looking for
- Be concise and actionable
- Do not invent details not in the data

Summary:
"""
    
    try:
        summary = llm_call(
            prompt,
            system_prompt="You are a synthesis assistant. Summarize the signal data accurately and concisely.",
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=30,
        )
        return summary if summary else "Unable to generate summary"
    except Exception as e:
        print(f"LLM summary error: {e}")
        # Fallback: rule-based summary
        cats = [cat for cat, _ in top_categories]
        return f"Found {total} signals related to '{query}'. Top pain categories: {', '.join(cats[:3])}."
