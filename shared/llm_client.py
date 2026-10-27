"""
gapfeed - Shared LLM Client

All LLM calls go through here. Auto-falls back from mimo-v2.6-flash to gemini-2.5-flash-lite
when the primary model hits rate limits (403/429/500/503).
"""
import json
import os
import re
import logging
import requests

logger = logging.getLogger(__name__)

MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
# Default to the Mimo TOKEN PLAN (fixed subscription) endpoint when a tp-/ttp- key is
# provided but no explicit base URL is set, so the subscription quota is used first.
_default_base = os.environ.get("MIMO_OPENAI_BASE_URL", "").rstrip("/")
if not _default_base and MIMO_API_KEY.startswith(("tp-", "ttp-")):
    _default_base = "https://token-plan-ams.xiaomimimo.com/v1"
MIMO_BASE_URL = _default_base
OPENROUTER_API_KEY = MIMO_API_KEY
OPENROUTER_URL = f"{MIMO_BASE_URL}/chat/completions" if MIMO_BASE_URL else "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "mimo-v2.6-flash"
FALLBACK_MODEL = "mimo-v2.6-flash"

# ---- Cost controls ----
DAILY_COST_CAP = float(os.environ.get("MIMO_DAILY_COST_CAP", "0"))  # 0 = disabled
MAX_COST_PER_CALL = float(os.environ.get("MIMO_MAX_COST_PER_CALL", "0"))  # 0 = disabled
_daily_spend = 0.0
_daily_spend_date = None
_cost_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "mimo_cost_log.json")

# Track model failures for auto-fallback
_model_failures = 0
_model_max_failures = 3
_using_fallback = False
_fallback_successes = 0
_fallback_reset_after = 20  # try primary again after 20 successful fallback calls


def _get_active_model() -> str:
    """Get the current active model (primary or fallback)."""
    return FALLBACK_MODEL if _using_fallback else DEFAULT_MODEL


def _switch_to_fallback():
    """Switch to fallback model after repeated failures."""
    global _using_fallback, _model_failures
    if not _using_fallback:
        _using_fallback = True
        _model_failures = 0
        logger.warning(f"Primary model failed {_model_max_failures}x, switching to fallback: {FALLBACK_MODEL}")


def _switch_to_primary():
    """Switch back to primary model on success."""
    global _using_fallback, _model_failures
    if _using_fallback:
        _using_fallback = False
        _model_failures = 0
        logger.info(f"Fallback model succeeded, switching back to primary: {DEFAULT_MODEL}")


def _record_failure(status_code: int):
    """Track failures and switch model if needed."""
    global _model_failures
    if status_code in (403, 429, 500, 503):
        _model_failures += 1
        if _model_failures >= _model_max_failures:
            _switch_to_fallback()
    else:
        _model_failures = 0


def _record_success():
    """Reset failure counter on success. Try primary again after enough fallback successes."""
    global _model_failures, _fallback_successes
    _model_failures = 0
    if _using_fallback:
        _fallback_successes += 1
        if _fallback_successes >= _fallback_reset_after:
            _switch_to_primary()


def _switch_to_primary():
    """Switch back to primary model after cooldown."""
    global _using_fallback, _model_failures, _fallback_successes
    if _using_fallback:
        _using_fallback = False
        _model_failures = 0
        _fallback_successes = 0
        logger.info(f"Switching back to primary model: {DEFAULT_MODEL}")


def _load_daily_spend():
    """Load persisted daily spend from cost log file."""
    global _daily_spend, _daily_spend_date
    import datetime as _dt
    import json as _json
    today = _dt.date.today().isoformat()
    try:
        with open(_cost_log, "r") as f:
            data = _json.load(f)
        if data.get("date") == today:
            _daily_spend = float(data.get("spend", 0.0))
            _daily_spend_date = today
        else:
            _daily_spend = 0.0
            _daily_spend_date = today
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        _daily_spend = 0.0
        _daily_spend_date = today


def _save_daily_spend():
    """Persist daily spend to cost log file."""
    import json as _json
    import os as _os
    try:
        _os.makedirs(os.path.dirname(_cost_log), exist_ok=True)
        with open(_cost_log, "w") as f:
            _json.dump({"date": _daily_spend_date, "spend": round(_daily_spend, 6)}, f)
    except Exception:
        pass


def _accrue_cost(response_data: dict):
    """Add estimated cost of this call to the daily spend tracker."""
    global _daily_spend
    if DAILY_COST_CAP <= 0 and MAX_COST_PER_CALL <= 0:
        return
    usage = response_data.get("usage", {}) or {}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    cost_per_call = float(os.environ.get("MIMO_COST_PER_CALL", "0.001"))
    # Rough token-based estimate when usage is present, else flat per-call cost.
    if total_tokens:
        cost = total_tokens * float(os.environ.get("MIMO_COST_PER_TOKEN", "0.000002"))
    else:
        cost = cost_per_call
    _daily_spend += cost
    _save_daily_spend()


def llm_call(prompt: str = None, system_prompt: str = None, model: str = None,
             max_tokens: int = 5000, temperature: float = 0.2,
             timeout: int = 30, messages: list = None) -> str:
    """Call LLM and return raw text response.

    Auto-falls back from mimo-v2.6-flash to gemini-2.5-flash-lite on rate limits.
    Either provide `prompt` (with optional `system_prompt`) OR `messages` (full chat history in OpenAI format).
    """
    if not OPENROUTER_API_KEY:
        logger.warning("LLM call skipped: no API key set (MIMO_API_KEY / OPENROUTER_API_KEY).")
        return ""

    # Enforce daily cost cap
    global _daily_spend, _daily_spend_date
    import datetime as _dt
    today = _dt.date.today().isoformat()
    if _daily_spend_date != today:
        _daily_spend = 0.0
        _daily_spend_date = today
    if DAILY_COST_CAP > 0 and _daily_spend >= DAILY_COST_CAP:
        logger.warning(f"LLM call blocked: daily cost cap {DAILY_COST_CAP} reached (spent {_daily_spend:.4f}).")
        return ""

    # Build messages array
    if messages is None:
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        if prompt is None:
            raise ValueError("Either prompt or messages must be provided")
        messages.append({'role': 'user', 'content': prompt})

    # Determine model: explicit override > active model (with fallback)
    chosen_model = model or _get_active_model()

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
"HTTP-Referer": "https://elitza.life",
                "X-Title": "Elitza Agent",
            },
            json={
                'model': chosen_model,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
            },
            timeout=timeout
        )

        if response.status_code == 200:
            _record_success()
            data = response.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            _accrue_cost(data)
            return content.strip()

        # Failed - record and try fallback model if not already using it
        _record_failure(response.status_code)
        if not _using_fallback and response.status_code in (403, 429, 500, 503):
            logger.warning(f"Primary model {chosen_model} failed ({response.status_code}), trying fallback {FALLBACK_MODEL}")
            try:
                resp2 = requests.post(
                    OPENROUTER_URL,
                    headers={
                        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                        'Content-Type': 'application/json',
"HTTP-Referer": "https://elitza.life",
                "X-Title": "Elitza Agent",
                    },
                    json={
                        'model': FALLBACK_MODEL,
                        'messages': messages,
                        'max_tokens': max_tokens,
                        'temperature': temperature,
                    },
                    timeout=timeout
                )
                if resp2.status_code == 200:
                    data = resp2.json()
                    return data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            except Exception:
                pass

        return ""

    except Exception:
        return ""


def llm_json(prompt: str, system_prompt: str = None, model: str = None,
             max_tokens: int = 5000, temperature: float = 0.2,
             timeout: int = 30) -> dict:
    """Call LLM and parse JSON from response."""
    text = llm_call(prompt, system_prompt, model, max_tokens, temperature, timeout)
    if not text:
        return {}

    # Extract JSON from response (may have surrounding text)
    # Try array first (greedy is safe for [], non-greedy for {})
    match = re.search(r'\[[\s\S]*\]', text)
    if not match:
        match = re.search(r'\{[\s\S]*?\}', text)
    if not match:
        return {}

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}

