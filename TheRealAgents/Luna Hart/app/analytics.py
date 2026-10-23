import requests
import time
import logging
import json
from datetime import datetime
import os

class Analytics:
    """
    Handles statistics retrieval from TuXo API and performance tracking/analysis
    from the local content log.
    """
    
    TUXO_API_BASE = "https://tuxo.it/api/db.php"
    CONTENT_LOG_PATH = "C:\\Users\\cosit\\.openclaw\\workspace\\tuxo\\TheRealAgents\\Luna Hart\\memory\\content_log.json"

    def __init__(self, config: dict, logger: logging.Logger):
        """
        Initializes the Analytics module with configuration and a logger.
        """
        self.logger = logger
        try:
            # Support both top-level and nested config
            if "tuxo_api_key" in config:
                self.tuxo_key = config["tuxo_api_key"]
            elif "data" in config and "tuxo_api_key" in config["data"]:
                self.tuxo_key = config["data"]["tuxo_api_key"]
            else:
                raise KeyError("tuxo_api_key not found in config")
            
            self.content_log_dir = os.path.dirname(self.CONTENT_LOG_PATH)
            self.tuxo_headers = {
                "Authorization": "Bearer " + self.tuxo_key,
            }
        except KeyError as e:
            self.logger.error("Missing required configuration key for Analytics: " + str(e))
            self.tuxo_key = None
            self.tuxo_headers = {}

    def _tuxo_request(self, action: str):
        """Internal helper for making requests to the TuXo API."""
        params = {
            "action": action
        }
        url = f"{self.TUXO_API_BASE}"
        try:
            response = requests.get(
                url,
                headers=self.tuxo_headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            error_msg = f"TuXo API request failed (action={action}): {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" - Status: {e.response.status_code} - Text: {e.response.text}"
            self.logger.error(error_msg)
            return None

    def get_tuxo_stats(self):
        """
        GET live stats from TuXo API which includes signals count and gaps count.
        """
        self.logger.info("Fetching live stats from TuXo API for signals and gaps.")
        data = self._tuxo_request(action="stats")
        
        if data and data.get("ok"):
            return {
                "signal_count": data.get("signals", 0),
                "gap_count": data.get("gaps", 0)
            }
        else:
            self.logger.warning("Failed to get TuXo stats or API returned error.")
            return {"signal_count": 0, "gap_count": 0}
        return None

    def get_engagement_data(self, draft_id: str):
        """
        Get engagement metrics for a draft.
        Typefully currently does not expose this via public API, returning a placeholder.
        """
        self.logger.warning(f"Engagement data for draft {draft_id} is not available via Typefully API. Returning placeholder.")
        return {
            "draft_id": draft_id,
            "status": "placeholder",
            "interactions": 0,
            "impressions": 0,
            "error": "No engagement API available in Typefully v2."
        }

    def track_post_performance(self, post_data: dict):
        """
        Log post performance data to content_log.json.
        Data should include metrics like platform, content_id, engagement_score, etc.
        """
        if not os.path.exists(self.content_log_dir):
            os.makedirs(self.content_log_dir, exist_ok=True)
            
        log_entries = []
        try:
            if os.path.exists(self.CONTENT_LOG_PATH):
                with open(self.CONTENT_LOG_PATH, 'r') as f:
                    try:
                        log_entries = json.load(f)
                    except json.JSONDecodeError:
                        self.logger.warning("Content log file is corrupted or empty. Starting new log.")
            
            new_entry = post_data
            new_entry["timestamp"] = datetime.utcnow().isoformat()
            log_entries.append(new_entry)
            
            with open(self.CONTENT_LOG_PATH, 'w') as f:
                json.dump(log_entries, f, indent=4)
                
            self.logger.info(f"Tracked performance for post ID: {post_data.get('content_id', 'N/A')}")
            return True

        except Exception as e:
            self.logger.error(f"Error writing to content log file: {e}")
            return False

    def get_top_posts(self, limit: int = 10):
        """
        Read content_log.json and return top performing posts based on a calculated score.
        Placeholder scoring: (Engagement Score * 1.5) + Impressions / 1000.
        """
        try:
            with open(self.CONTENT_LOG_PATH, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.logger.warning("Content log file not found.")
            return []
        except json.JSONDecodeError:
            self.logger.warning("Content log file is empty or malformed.")
            return []
        
        # Handle both formats: list or {"posts": [...]}
        if isinstance(data, list):
            log_entries = data
        elif isinstance(data, dict) and "posts" in data:
            log_entries = data["posts"]
        else:
            log_entries = []
            
        if not log_entries:
            return []
            
        # Calculate score for sorting
        scored_posts = []
        for post in log_entries:
            if not isinstance(post, dict):
                continue
            engagement = post.get("engagement_score", 0)
            impressions = post.get("impressions", 0)
            
            # Placeholder complex scoring logic
            calculated_score = (engagement * 1.5) + (impressions / 1000.0)
            
            post["calculated_performance_score"] = calculated_score
            scored_posts.append(post)
            
        # Sort by score descending
        sorted_posts = sorted(scored_posts, key=lambda x: x["calculated_performance_score"], reverse=True)
        
        self.logger.info(f"Returning top {min(limit, len(sorted_posts))} posts from log.")
        return sorted_posts[:limit]

    def get_engagement_summary(self):
        """
        Generate a summary of all engagement metrics logged in content_log.json.
        """
        try:
            with open(self.CONTENT_LOG_PATH, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.logger.warning("Content log file missing or empty for summary generation.")
            return {"total_posts_logged": 0, "summary": "No data."}
        
        # Handle both formats: list or {"posts": [...]}
        if isinstance(data, list):
            log_entries = data
        elif isinstance(data, dict) and "posts" in data:
            log_entries = data["posts"]
        else:
            log_entries = []
            
        total_posts = len(log_entries)
        if total_posts == 0:
            return {"total_posts_logged": 0, "summary": "No data."}
            
        total_engagement = sum(p.get("engagement_score", 0) for p in log_entries if isinstance(p, dict))
        total_impressions = sum(p.get("impressions", 0) for p in log_entries if isinstance(p, dict))
        
        summary = {
            "total_posts_logged": total_posts,
            "average_engagement_score": total_engagement / total_posts if total_posts > 0 else 0,
            "total_impressions": total_impressions,
            "summary": "Logged " + str(total_posts) + " posts with average engagement score " + str(round(total_engagement / total_posts, 2)) + "."
        }
        
        return summary

    def get_signal_count(self):
        """
        Get current signal count from TuXo API.
        """
        self.logger.info("Fetching signal count from TuXo API.")
        stats = self.get_tuxo_stats()
        return stats.get("signal_count") if stats else None

    def get_gap_count(self):
        """
        Get current gap count from TuXo API.
        """
        self.logger.info("Fetching gap count from TuXo API.")
        stats = self.get_tuxo_stats()
        return stats.get("gap_count") if stats else None

# Ensure the class structure matches the request and no em dashes exist.
# End of analytics.py
