import requests
import time
import logging
from datetime import datetime

class SocialManager:
    """
    Manages interactions with the Typefully API for draft creation, updates,
    and scheduling.
    """
    
    API_BASE = "https://api.typefully.com/v2"

    def __init__(self, config: dict, logger: logging.Logger):
        """
        Initializes the SocialManager with configuration and a logger.
        Loads API key and social set ID from the provided config.
        """
        self.logger = logger
        try:
            social_config = config.get("social", {})
            self.api_key = social_config["typefully_api_key"]
            self.social_set_id = social_config["social_set_id"]
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        except KeyError as e:
            self.logger.error(f"Missing required configuration key for Typefully: {e}")
            self.api_key = None
            self.headers = {}

    def _request(self, method: str, endpoint: str, data: dict = None):
        """Internal helper for making API requests."""
        url = f"{self.API_BASE}/{endpoint.lstrip('/')}"
        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                json=data,
                timeout=15
            )
            response.raise_for_status()
            
            if response.status_code == 204:
                return {"status": "success", "message": "No content returned"}
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Typefully API request failed ({method} {endpoint}): {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" - Status: {e.response.status_code} - Text: {e.response.text}"
            self.logger.error(error_msg)
            return None

    def list_drafts(self, limit: int = 50):
        """
        GET all drafts from Typefully.
        """
        self.logger.info(f"Listing up to {limit} drafts.")
        return self._request("GET", f"social-sets/{self.social_set_id}/drafts?limit={limit}")

    def create_draft(self, content, platforms: list, schedule_time: str = None, title: str = None):
        """
        POST new draft to Typefully (v2 API format).
        content can be a string (single post) or a list (thread).
        Platforms is a list like ["x"] or ["linkedin"].
        schedule_time (publish_at) must be a UTC ISO 8601 string.
        """
        if not content:
            self.logger.warning("Cannot create draft with empty content.")
            return None
        
        # Build platforms dict in v2 format
        platforms_dict = {}
        
        if "x" in platforms:
            if isinstance(content, list):
                posts = [{"text": str(t)} for t in content]
            else:
                posts = [{"text": str(content)}]
            platforms_dict["x"] = {"enabled": True, "posts": posts}
        
        if "linkedin" in platforms:
            li_content = content[0] if isinstance(content, list) else content
            platforms_dict["linkedin"] = {"enabled": True, "posts": [{"text": str(li_content)}]}
        
        if not platforms_dict:
            self.logger.warning(f"No valid platforms specified: {platforms}")
            return None
        
        payload = {"platforms": platforms_dict}
        
        if schedule_time:
            payload["publish_at"] = schedule_time

        self.logger.info(f"Creating draft for platforms: {platforms}")
        return self._request("POST", f"social-sets/{self.social_set_id}/drafts", data=payload)

    def update_draft(self, draft_id: str, content, platforms: list):
        """
        PATCH existing draft (v2 API format).
        """
        platforms_dict = {}
        
        if "x" in platforms:
            if isinstance(content, list):
                posts = [{"text": str(t)} for t in content]
            else:
                posts = [{"text": str(content)}]
            platforms_dict["x"] = {"enabled": True, "posts": posts}
        
        if "linkedin" in platforms:
            li_content = content[0] if isinstance(content, list) else content
            platforms_dict["linkedin"] = {"enabled": True, "posts": [{"text": str(li_content)}]}
        
        payload = {"platforms": platforms_dict}
        
        self.logger.info(f"Updating draft ID: {draft_id}")
        return self._request("PATCH", f"social-sets/{self.social_set_id}/drafts/{draft_id}", data=payload)

    def delete_draft(self, draft_id: str):
        """
        DELETE draft.
        """
        self.logger.info(f"Deleting draft ID: {draft_id}")
        result = self._request("DELETE", f"social-sets/{self.social_set_id}/drafts/{draft_id}")
        if result is not None:
            return True
        return False

    def get_drafts_for_date(self, date_str: str):
        """
        Get all drafts scheduled for a specific date.
        """
        self.logger.info(f"Fetching drafts and filtering for date: {date_str}")
        all_drafts_response = self.list_drafts(limit=500)
        
        if not all_drafts_response or "results" not in all_drafts_response:
            return []

        target_date = date_str.split('T')[0]
        
        filtered_drafts = []
        for draft in all_drafts_response["results"]:
            scheduled = draft.get("scheduled_date")
            if not scheduled:
                continue
            try:
                schedule_dt = datetime.fromisoformat(scheduled.replace('Z', '+00:00'))
                if schedule_dt.strftime('%Y-%m-%d') == target_date:
                    filtered_drafts.append(draft)
            except ValueError:
                self.logger.warning(f"Could not parse schedule date for draft {draft.get('id')}")
        
        self.logger.info(f"Found {len(filtered_drafts)} drafts scheduled for {date_str}")
        return filtered_drafts

    def update_numbers_in_drafts(self, draft_ids: list[str], old_numbers: list[str], new_numbers: list[str]):
        """
        Replace signal/gap counts in multiple drafts by patching.
        Applies a 0.5s delay between each update operation batch.
        """
        if not (len(draft_ids) == len(old_numbers) == len(new_numbers)):
            self.logger.error("Input lists for update_numbers_in_drafts must all be the same length.")
            return False
            
        success_count = 0
        for i, draft_id in enumerate(draft_ids):
            old_text = old_numbers[i]
            new_text = new_numbers[i]
            
            draft_response = self._request("GET", f"social-sets/{self.social_set_id}/drafts/{draft_id}")
            if not draft_response:
                self.logger.warning(f"Could not retrieve draft {draft_id} for update. Skipping.")
                continue
            
            # Extract text from first platform's first post
            platforms = draft_response.get("platforms", {})
            found_content = None
            platform_name = None
            for pname in ["x", "linkedin"]:
                if pname in platforms and platforms[pname].get("enabled"):
                    posts = platforms[pname].get("posts", [])
                    if posts and old_text in posts[0].get("text", ""):
                        found_content = posts[0]["text"]
                        platform_name = pname
                        break
            
            if found_content and platform_name:
                updated_content = found_content.replace(old_text, new_text)
                update_result = self.update_draft(draft_id, updated_content, [platform_name])
                if update_result is not None:
                    success_count += 1
                time.sleep(0.5)

        self.logger.info(f"Successfully updated {success_count}/{len(draft_ids)} drafts with new numbers.")
        return success_count == len(draft_ids)

    def schedule_daily_posts(self, posts_list: list[dict]):
        """
        Batch create drafts for a day. posts_list is a list of dicts with
        content, platforms, time (UTC ISO 8601 string), and title.
        Applies a 0.5s delay between each creation.
        """
        self.logger.info(f"Scheduling {len(posts_list)} posts for the day.")
        results = []
        for post_data in posts_list:
            result = self.create_draft(
                content=post_data["content"],
                platforms=post_data["platforms"],
                schedule_time=post_data["time"],
                title=post_data["title"]
            )
            results.append(result)
            
            # Enforce 0.5s delay between batch operations
            time.sleep(0.5)
            
        successful_creations = sum(1 for r in results if r is not None)
        self.logger.info(f"Batch creation complete. Successfully created {successful_creations} drafts.")
        return results

    def get_scheduled_counts_by_date(self, days_ahead: int = 2):
        """
        Count existing scheduled drafts per date for the next N days.
        Returns dict like {"2026-03-30": 2, "2026-03-31": 1}
        """
        from datetime import date, timedelta
        
        all_drafts = self.list_drafts(limit=200)
        if not all_drafts or "results" not in all_drafts:
            self.logger.warning("Could not fetch drafts for date counting.")
            return {}
        
        date_counts = {}
        for draft in all_drafts["results"]:
            scheduled_date = draft.get("scheduled_date")
            if not scheduled_date:
                continue
            try:
                draft_dt = datetime.fromisoformat(scheduled_date.replace("Z", "+00:00"))
                draft_date = draft_dt.date()
                date_str = draft_date.isoformat()
                if date_str not in date_counts:
                    date_counts[date_str] = 0
                date_counts[date_str] += 1
            except (ValueError, TypeError):
                continue
        
        self.logger.info(f"Draft counts by date: {date_counts}")
        return date_counts

    def get_available_slots_for_tomorrow(self, config: dict) -> list[str]:
        """
        Check Typefully for existing drafts on T+1 and return available
        posting time slots (as UTC ISO strings).
        """
        from datetime import date, timedelta
        
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_str = tomorrow.isoformat()
        
        # Get configured posting times for all platforms
        social_config = config.get("social", {})
        post_times = social_config.get("post_times_cet", {})
        max_posts = social_config.get("max_posts_per_day", 4)
        
        # Collect all configured slots (CET -> UTC)
        all_slots = []
        for platform, times in post_times.items():
            for time_str in times:
                hour, minute = map(int, time_str.split(":"))
                utc_hour = hour - 1  # CET = UTC+1
                if utc_hour < 0:
                    utc_hour += 24
                slot_iso = tomorrow.strftime(f"%Y-%m-%dT{utc_hour:02d}:{minute:02d}:00.000Z")
                all_slots.append(slot_iso)
        
        all_slots.sort()
        
        # Check existing scheduled drafts for tomorrow
        existing_drafts_response = self.list_drafts(limit=200)
        taken_times = set()
        if existing_drafts_response and "results" in existing_drafts_response:
            for draft in existing_drafts_response["results"]:
                scheduled_date = draft.get("scheduled_date")
                if not scheduled_date:
                    continue
                try:
                    dt = datetime.fromisoformat(scheduled_date.replace("Z", "+00:00"))
                    if dt.date() == tomorrow:
                        taken_times.add(dt.strftime("%H:%M"))
                except (ValueError, TypeError):
                    continue
        
        available = []
        for slot in all_slots:
            try:
                dt = datetime.fromisoformat(slot.replace("Z", "+00:00"))
                slot_key = dt.strftime("%H:%M")
                if slot_key not in taken_times:
                    available.append(slot)
            except (ValueError, TypeError):
                continue
        
        available = available[:max_posts]
        
        self.logger.info(f"Tomorrow ({tomorrow_str}): {len(taken_times)} taken, {len(available)} available slots: {available}")
        return available

# End of social_manager.py
