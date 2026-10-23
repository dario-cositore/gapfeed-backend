import json
import os
import sys
import time
import random
from datetime import datetime

# Add parent paths for imports
ALEX_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ALEX_ROOT)
sys.path.insert(0, os.path.join(ALEX_ROOT, '..', 'shared'))

CACHE_FILE = os.path.join(ALEX_ROOT, 'state', 'cursors', 'query_generator_cache.json')
LLM_MODEL = "mimo-v2.6-flash"
MAX_TOKENS = 1000
TIMEOUT_SECONDS = 15

try:
    from llm_client import llm_call
except ImportError:
    def llm_call(prompt=None, system_prompt=None, model=None, max_tokens=None, timeout=None, **kwargs):
        raise RuntimeError("LLM client import failed")


def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return None, []
    try:
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
            # Check for temporal relevance (within 1 hour = 3600 seconds)
            last_run = datetime.fromisoformat(data['last_run'])
            if (datetime.now() - last_run).total_seconds() < 3600:
                return data.get('trends', []), data.get('queries', [])
            else:
                return None, []
    except Exception:
        return None, []

def _save_cache(trends, queries):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        data = {
            'last_run': datetime.now().isoformat(),
            'trends': trends,
            'queries': queries
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass # Fail silently on cache write

class QueryGenerator:
    def generate(self, tech_trends: list[dict], pain_seeds: list[str], n_queries: int = 20) -> list[str]:
        
        trend_titles = [t.get('title', 'Unknown Context') for t in tech_trends]
        
        trends_str = "\\n".join([f"- {t}" for t in trend_titles])
        seeds_str = "\\n".join([f"- {s}" for s in pain_seeds])
        
        system_prompt = (
            "You are an expert search query generator. Your task is to ingeniously combine real-world frustration patterns "
            "with current technology trends to create high-intent, dynamic pain queries that a frustrated user would actually type into a search engine. "
            "DO NOT output any text other than a JSON object."
        )
        
        user_prompt = f"""
        CURRENT TRENDING TOPICS TITLES (Use these product/tool names specifically when possible):
        {trends_str}

        PAIN SEED CATEGORIES/PATTERNS (Use these concepts to frame the query):
        {seeds_str}

        INSTRUCTIONS:
        1. Generate exactly {n_queries} queries.
        2. Each query must be a complete, natural-sounding question or search phrase.
        3. Make them compound queries combining a specific topic/tool name from the trending topics list with a specific pain pattern from the pain seed list.
        4. Be extremely specific. AVOID generic queries.
        5. Output ONLY a JSON object which is a list of strings under the key "queries": {{"queries": ["query 1", "query 2", ...]}}.
        """

        try:
            response_str = llm_call(
                model=LLM_MODEL,
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=MAX_TOKENS,
                timeout=TIMEOUT_SECONDS,
            )
            
            # Attempt to parse the JSON output
            try:
                data = json.loads(response_str)
                
                queries = []
                if isinstance(data, dict) and 'queries' in data and isinstance(data['queries'], list):
                    queries = [str(q) for q in data['queries'] if isinstance(q, str)]
                elif isinstance(data, list): # Handle bare list response if client doesn't wrap
                    queries = [str(q) for q in data if isinstance(q, str)]
                else:
                    raise ValueError("LLM response structure is unexpected.")
                    
            except json.JSONDecodeError:
                raise RuntimeError("Failed to decode JSON from LLM output.")
                
            final_queries = queries[:n_queries]
            
            _save_cache(tech_trends, final_queries)
            return final_queries

        except Exception:
            # LLM call failed (timeout, error, parsing issue)
            if pain_seeds:
                sample_size = min(n_queries, len(pain_seeds))
                # Fallback: return a random sample of pain seeds
                return random.sample(pain_seeds, sample_size)
            return []

    def get_cached_or_generate(self, tech_trends: list[dict], pain_seeds: list[str]) -> list[str]:
        cached_trends, cached_queries = _load_cache()
        
        # Simple heuristic: check if the set of trend titles matches the cached result.
        current_trend_titles = sorted([t.get('title', '').lower() for t in set(tuple(sorted(t.items())) for t in tech_trends)])
        cached_trend_titles = sorted([t.get('title', '').lower() for t in set(tuple(sorted(t.items())) for t in cached_trends)])

        if cached_queries and current_trend_titles == cached_trend_titles:
            return cached_queries
        
        # Cache miss or expired: Generate new queries
        return self.generate(tech_trends, pain_seeds)
        
# Final check: ensure the file is saved in the intended directory structure so relative import resolves.
# Need to make sure we are not writing this executable block below into the file content.

