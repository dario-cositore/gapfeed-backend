"""
Batch processor — groups signals for efficient LLM processing.

Combines signals into batches for the LLM to classify multiple
signals in a single call, reducing API costs and latency.
"""

import logging

logger = logging.getLogger(__name__)


def prepare_batches(signals: list[dict], batch_size: int = 5,
                    max_total_tokens: int = 6000) -> list[list[dict]]:
    """
    Group signals into batches for LLM processing.

    Args:
        signals: List of signal dicts with 'id', 'text', 'source'.
        batch_size: Maximum signals per batch.
        max_total_tokens: Rough token budget per batch (1 token ~ 4 chars).

    Returns:
        List of batches, each a list of signal dicts.
    """
    if not signals:
        return []

    max_chars = max_total_tokens * 4
    batches = []
    current_batch = []
    current_chars = 0

    for signal in signals:
        text = signal.get('text', '')
        text_len = len(text)

        # If adding this signal would exceed limits, start new batch
        if current_batch and (
            len(current_batch) >= batch_size or
            current_chars + text_len > max_chars
        ):
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        current_batch.append(signal)
        current_chars += text_len

    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)

    logger.info(f"Prepared {len(batches)} batches from {len(signals)} signals")
    return batches


def enrich_batch_with_rules(batch: list[dict], pre_classify_fn) -> list[dict]:
    """
    Add pre-classification results to each signal in a batch.

    Args:
        batch: List of signal dicts.
        pre_classify_fn: The pre_classify function from rules.py.

    Returns:
        Same batch with 'pre_classification' field added.
    """
    for signal in batch:
        text = signal.get('text', '')
        source = signal.get('source', '')
        signal['pre_classification'] = pre_classify_fn(text, source)

    return batch
