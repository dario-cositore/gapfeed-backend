import requests
import time
import json
import os
import logging
from datetime import datetime, timedelta

# --- Configuration ---
# Base directory for context artifacts derived from the prompt
BASE_DIR = r"C:\Users\cosit\.openclaw\workspace\tuxo\TheRealAgents\Agent_5"
MEMORY_FILE_PATH = os.path.join(BASE_DIR, r"memory\trends.json")

# Default configuration structure
DEFAULT_CONFIG = {
    "alert_threshold": 0.7,
    "reddit_subreddits": ["technology", "programming", "futurology"],
    "hn_limit": 30,
    "reddit_limit": 25,
    "api_call_delay_s": 1.0
}

class TrendScout:
    """
    Scouts Reddit and Hacker News for trending topics, scores them,
    and identifies emerging trends relevant to TuXo gaps.
    """
    
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = DEFAULT_CONFIG.copy()
        self.config.update(config)
        self.logger = logger
        self.last_api_call_time = 0
        
        # Ensure memory directory exists as specified in requirements
        memory_dir = os.path.dirname(MEMORY_FILE_PATH)
        if not os.path.exists(memory_dir):
            os.makedirs(memory_dir, exist_ok=True)
            self.logger.info(f"Created memory directory: {memory_dir}")

    def _rate_limit(self):
        """Enforces the minimum delay between external API calls."""
        elapsed = time.time() - self.last_api_call_time
        delay = self.config["api_call_delay_s"]
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_api_call_time = time.time()

    def scout_reddit(self, subreddits: list = None, limit: int = None) -> list:
        """
        Search subreddits for trending topics.
        Returns list of dicts with title, score, num_comments, url, created_utc.
        """
        if subreddits is None:
            subreddits = self.config.get("reddit_subreddits", [])
        if limit is None:
            limit = self.config.get("reddit_limit", 25)
            
        all_posts = []
        
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json"
            self._rate_limit()
            
            self.logger.info(f"Scouting Reddit: r/{sub} with limit {limit}")
            try:
                # Use standard User-Agent as good practice
                response = requests.get(url, headers={'User-Agent': 'LunaHartScout/1.0'}, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                for item in data.get('data', {}).get('children', []):
                    post = item.get('data', {})
                    
                    cleaned_post = {
                        "title": post.get("title"),
                        "score": post.get("score"),
                        "num_comments": post.get("num_comments"),
                        "url": post.get("url"),
                        "created_utc": post.get("created_utc"),
                        "source": f"reddit:{sub}"
                    }
                    all_posts.append(cleaned_post)
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error scouting Reddit r/{sub}: {e}")
                
        return all_posts

    def scout_hackernews(self, limit: int = None) -> list:
        """
        Get HN front page stories.
        Returns list of dicts with title, score, url, time.
        """
        if limit is None:
            limit  = self.config.get("hn_limit", 30)
            
        hn_top_stories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        all_items = []
        
        self.logger.info(f"Scouting Hacker News for top {limit} stories.")
        
        try:
            self._rate_limit()
            story_ids_response = requests.get(hn_top_stories_url, timeout=10)
            story_ids_response.raise_for_status()
            story_ids = story_ids_response.json()[:limit]
            
            item_base_url = "https://hacker-news.firebaseio.com/v0/item/{}.json"
            
            for item_id in story_ids:
                item_url = item_base_url.format(item_id)
                self._rate_limit()
                
                item_response = requests.get(item_url, timeout=10)
                item_response.raise_for_status()
                item = item_response.json()
                
                if item and item.get("type") == "story":
                    cleaned_item = {
                        "title": item.get("title"),
                        "score": item.get("score", 0),
                        "url": item.get("url"),
                        "created_utc": item.get("time"), # HN timestamp provided as 'time'
                        "source": "hackernews"
                    }
                    all_items.append(cleaned_item)
                    
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error scouting Hacker News: {e}")
            
        return all_items

    def scout_all(self) -> list:
        """Run all scouts, combine results, deduplicate by URL."""
        reddit_trends = self.scout_reddit()
        hn_trends = self.scout_hackernews()
        
        combined_trends = reddit_trends + hn_trends
        
        # Deduplicate by URL
        unique_trends_map = {}
        for trend in combined_trends:
            url = trend.get("url")
            if url and url not in unique_trends_map:
                unique_trends_map[url] = trend
                
        self.logger.info(f"Combined {len(combined_trends)} raw items, {len(unique_trends_map)} unique URL records.")
        return list(unique_trends_map.values())

    def score_trend(self, topic_data: dict) -> float:
        """
        Score a topic's trend potential (0-1).
        Factors: score, comments, recency (relative to ~24h window), relevance (placeholder).
        """
        score = topic_data.get("score", 0)
        comments = topic_data.get("num_comments", 0)
        created_utc = topic_data.get("created_utc")
        
        # --- Recency Scoring ---
        recency_bias = 0.0
        if created_utc:
            try:
                now = datetime.utcnow()
                trend_time = datetime.fromtimestamp(created_utc)
                time_diff = now - trend_time
                
                if time_diff.total_seconds() < 3 * 3600: # Very new (last 3 hours) 
                    recency_bias = 1.0
                elif time_diff.total_seconds() < 24 * 3600: # Within 24 hours
                    # Linear scaling down from 1.0 at 0h to 0.5 at 24h
                    recency_bias = 1.0 - (time_diff.total_seconds() / (24 * 3600)) * 0.5
                else:
                    recency_bias = 0.1 # Stale after 24 hours
                    
            except (ValueError, TypeError):
                recency_bias = 0.3 # Default for bad timestamp
            
        # --- Volume Factor (Heuristic scaling based on typical high scores) ---
        # Scaled contribution: (score / 500) + (comments / 100). Capped contribution.
        engagement_factor = (score / 500.0) + (comments / 100.0)
        engagement_factor = min(0.7, engagement_factor * 0.5)

        # --- Final Score (Weighted average of recency and engagement) ---
        final_score = (0.5 * recency_bias) + (0.5 * engagement_factor)
        
        # Relevance to TuXo gaps is baked into source selection, so we use 1.0 multiplier here.
        return max(0.0, min(1.0, final_score))


    def identify_emerging(self, trends: list, threshold: float = None) -> list:
        """
        Filter trends that are emerging (high score, recent, growing) based on threshold.
        """
        if threshold is None:
            threshold = self.config["alert_threshold"]
            
        emerging_trends = []
        
        for trend in trends:
            # Score the trend first, adding score to the dict
            trend["trend_score"] = self.score_trend(trend)
            
            if trend["trend_score"] >= threshold:
                # Create a clean topic data structure for saving/passing downstream
                topic_data = {
                    "title": trend.get("title"),
                    "url": trend.get("url"),
                    "score": trend.get("score"),
                    "num_comments": trend.get("num_comments"),
                    "created_utc": trend.get("created_utc"),
                    "trend_score": trend["trend_score"],
                    "source": trend.get("source")
                }
                emerging_trends.append(topic_data)
                
        self.logger.info(f"Identified {len(emerging_trends)} emerging trends (score >= {threshold}).")
        return emerging_trends

    def save_trends(self, trends: list):
        """Save the current set of tracked trends to memory/trends.json."""
        
        data_to_save = {
            "last_scanned": datetime.now().isoformat(),
            "trends": trends
        }
        
        try:
            with open(MEMORY_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            self.logger.info(f"Successfully saved {len(trends)} trends to {MEMORY_FILE_PATH}")
        except IOError as e:
            self.logger.error(f"Failed to save trends to {MEMORY_FILE_PATH}: {e}")

    def load_trends(self) -> dict:
        """Load previously saved trends from memory/trends.json."""
        if not os.path.exists(MEMORY_FILE_PATH):
            self.logger.warning(f"Trend memory file not found at {MEMORY_FILE_PATH}. Returning empty data.")
            return {"last_scanned": None, "trends": []}
            
        try:
            with open(MEMORY_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.info(f"Loaded trends scanned on {data.get('last_scanned', 'Unknown Date')}.")
            return data
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load or parse trends from {MEMORY_FILE_PATH}: {e}")
            return {"last_scanned": None, "trends": []}

    def get_trending_now(self) -> list:
        """Return currently tracked trends above threshold, loaded from memory."""
        loaded_data = self.load_trends()
        # Trends saved here are those that passed the initial threshold filter.
        return loaded_data.get("trends", [])