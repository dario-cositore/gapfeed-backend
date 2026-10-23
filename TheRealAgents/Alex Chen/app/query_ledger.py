import json
import os
from datetime import datetime, timedelta
import random

TIME_BUCKETS = {
    (6, 12): "morning",
    (12, 18): "afternoon",
    (18, 24): "evening",
    (0, 6): "night",
}
DECAY_HALF_LIFE_DAYS = 30


class QueryLedger:
    """Tracks query performance and biases future query selection."""

    def __init__(self, ledger_file: str = None):
        self.ledger_file = ledger_file or 'state/cursors/query_ledger.json'
        self.data = self._load()

    def _load(self):
        try:
            if os.path.exists(self.ledger_file):
                with open(self.ledger_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {"queries": {}, "time_patterns": {}}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.ledger_file), exist_ok=True)
            with open(self.ledger_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def get_time_bucket(self) -> str:
        hour = datetime.now().hour
        for (start, end), bucket in TIME_BUCKETS.items():
            if start <= hour < end:
                return bucket
        return "night"

    def record_outcome(self, query: str, source: str, signals_found: int,
                       high_relevance: int = 0, gaps_created: int = 0):
        now_iso = datetime.utcnow().isoformat() + "Z"

        if query not in self.data["queries"]:
            self.data["queries"][query] = {
                "total_runs": 0, "total_signals": 0, "high_relevance_signals": 0,
                "gaps_created": 0, "last_run": None, "source": source
            }

        entry = self.data["queries"][query]
        entry["total_runs"] += 1
        entry["total_signals"] += signals_found
        entry["high_relevance_signals"] += high_relevance
        entry["gaps_created"] += gaps_created
        entry["last_run"] = now_iso
        entry["source"] = source

        self._save()

    def _calculate_score(self, query_data: dict) -> float:
        """Calculates score with decay. Higher = better performer."""
        base_score = (
            query_data.get("high_relevance_signals", 0) * 5.0 +
            query_data.get("total_signals", 0) * 1.0 +
            query_data.get("gaps_created", 0) * 10.0  # Gaps are the goal
        )

        last_run_str = query_data.get("last_run")
        if not last_run_str or query_data.get("total_runs", 0) < 3:
            return max(0.1, base_score)

        try:
            if last_run_str.endswith('Z'):
                last_run = datetime.fromisoformat(last_run_str.replace('Z', '+00:00'))
            else:
                last_run = datetime.fromisoformat(last_run_str)

            now = datetime.utcnow().replace(tzinfo=last_run.tzinfo)
            days_since = (now - last_run).total_seconds() / 86400.0
            decay = 2.0 ** (-days_since / DECAY_HALF_LIFE_DAYS)
            return max(0.01, base_score * decay)
        except Exception:
            return max(0.01, base_score)

    def get_weighted_sample(self, source: str, n: int = 10) -> list:
        candidates = []
        weights = []

        for query, data in self.data["queries"].items():
            if data.get("source") == source:
                score = self._calculate_score(data)
                candidates.append(query)
                weights.append(max(0.1, score))

        if not candidates:
            return []

        k = min(n, len(candidates))
        return random.choices(candidates, weights=weights, k=k)

    def get_top_performers(self, source: str = None, limit: int = 20) -> list:
        results = []

        for query, data in self.data["queries"].items():
            if source is None or data.get("source") == source:
                metric = (
                    data.get("high_relevance_signals", 0) * 5.0 +
                    data.get("total_signals", 0) * 1.0 +
                    data.get("gaps_created", 0) * 10.0
                )
                results.append({
                    "query": query,
                    "score": metric,
                    "total_runs": data.get("total_runs", 0),
                    "total_signals": data.get("total_signals", 0),
                    "gaps_created": data.get("gaps_created", 0),
                    "source": data.get("source"),
                    "last_run": data.get("last_run"),
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
