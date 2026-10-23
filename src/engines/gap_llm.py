"""
Dedicated LLM client for gap description generation.

Separate from shared/llm_client.py to allow model-specific tuning.
No fallback chain - uses exactly the model specified in config.
"""
import json
import os
import re
import logging
import requests

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("MIMO_API_KEY", "")
_MIMO_BASE = os.environ.get("MIMO_OPENAI_BASE_URL", "").rstrip("/")
OPENROUTER_URL = f"{_MIMO_BASE}/chat/completions" if _MIMO_BASE else "https://openrouter.ai/api/v1/chat/completions"

# Default model for gap descriptions (override via call parameter)
DEFAULT_GAP_MODEL = "mimo-v2.6-flash"


def gap_llm_call(prompt: str, system_prompt: str = None, model: str = None,
                 max_tokens: int = 2000, temperature: float = 0.3,
                 timeout: int = 30) -> dict:
    """
    Call LLM for gap description generation.
    
    Returns dict with:
        - text: raw response text
        - model: model used
        - tokens_in: input token count
        - tokens_out: output token count
        - elapsed: seconds
        - cost_est: estimated cost in USD
    """
    if not OPENROUTER_API_KEY:
        return {"text": "", "error": "No API key"}

    chosen_model = model or DEFAULT_GAP_MODEL
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    import time
    start = time.time()

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://elitza.life",
                "X-Title": "Elitza Agent",
            },
            json={
                "model": chosen_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=timeout
        )
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {
                "text": "",
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "model": chosen_model,
                "elapsed": elapsed,
            }

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return {
            "text": content.strip(),
            "model": chosen_model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "elapsed": round(elapsed, 2),
        }

    except requests.exceptions.Timeout:
        return {"text": "", "error": "Timeout", "model": chosen_model, "elapsed": timeout}
    except Exception as e:
        return {"text": "", "error": str(e), "model": chosen_model, "elapsed": time.time() - start}


def gap_llm_json(prompt: str, system_prompt: str = None, model: str = None,
                 max_tokens: int = 2000, temperature: float = 0.3,
                 timeout: int = 30) -> dict:
    """
    Call LLM and parse JSON from response.
    Returns dict with parsed result + metadata.
    """
    result = gap_llm_call(prompt, system_prompt, model, max_tokens, temperature, timeout)
    
    if result.get("error"):
        return {"_meta": result, "_error": result["error"]}

    text = result["text"]
    
    # Strip markdown code blocks if present
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    
    # Extract JSON object (not array)
    match = re.search(r'\{[\s\S]*\}', text)
    
    if not match:
        return {"_meta": result, "_error": "No JSON object found in response"}

    try:
        parsed = json.loads(match.group())
        parsed["_meta"] = result
        return parsed
    except json.JSONDecodeError as e:
        return {"_meta": result, "_error": f"JSON parse error: {e}"}


# Model pricing (USD per million tokens)
MODEL_PRICING = {
    "z-ai/glm-5": {"input": 0.72, "output": 2.30},
    "minimax/minimax-m2.7": {"input": 0.30, "output": 1.20},
    "openai/gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "moonshotai/kimi-k2.5": {"input": 0.42, "output": 2.20},
    "google/gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    # Existing models for comparison
    "mimo-v2.6-flash": {"input": 0.00, "output": 0.00},  # free
    "deepseek/deepseek-v3.2": {"input": 0.14, "output": 0.28},
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 3.0})
    cost = (tokens_in / 1_000_000) * pricing["input"] + (tokens_out / 1_000_000) * pricing["output"]
    return round(cost, 6)
